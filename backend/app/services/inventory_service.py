"""Core stock engine. All quantity changes go through stock_in / stock_out so history and FIFO layers stay consistent.
Functions only flush; the calling route commits once, so every business operation is one atomic transaction."""
from datetime import timedelta
from sqlalchemy.exc import IntegrityError
from ..extensions import db
from ..models import (Inventory, Batch, StockMovement, Reservation, Product, ProcessedOperation, Warehouse)
from ..utils import BusinessError, now
from .notification_service import get_setting, notify


def setting_bool(key, default=False):
    return str(get_setting(key, str(default))).lower() in ("1", "true", "yes", "on")


def claim_operation(key, scope):
    """Idempotency guard against duplicate processing (double clicks, retries)."""
    if not key:
        return
    db.session.add(ProcessedOperation(key=f"{scope}:{key}"[:120]))
    try:
        db.session.flush()
    except IntegrityError:
        db.session.rollback()
        raise BusinessError("This operation was already processed (duplicate request ignored)", 409, code="duplicate")


from ..repositories.inventory_repository import (  # noqa: E402,F401  (re-exported for callers of the service)
    on_hand, reserved_qty, available, stock_map, reserved_map, valuation, low_and_out_products, fifo_layers, warehouse_units)


def stock_in(product_id, warehouse_id, qty, unit_cost, *, batch_no=None, expiry_date=None, mfg_date=None, movement_type="IN",
             ref_type=None, ref_id=None, note=None, user_id=None, supplier_id=None, at=None, batch=None):
    if qty is None or qty <= 0:
        raise BusinessError("Quantity must be greater than zero", 422)
    at = at or now()
    if batch is None:
        base = batch_no or f"LOT-{at:%Y%m%d}"
        batch_no, n = base, 1
        while True:  # same lot number but different cost => separate FIFO layer
            batch = Batch.query.filter_by(product_id=product_id, batch_no=batch_no).first()
            if batch is None or abs(batch.unit_cost - unit_cost) < 1e-6:
                break
            n += 1
            batch_no = f"{base}-{n}"
        if batch is None:
            batch = Batch(product_id=product_id, batch_no=batch_no, expiry_date=expiry_date, mfg_date=mfg_date,
                          unit_cost=round(unit_cost, 4), received_at=at, supplier_id=supplier_id)
            db.session.add(batch)
            db.session.flush()
        elif expiry_date and not batch.expiry_date:
            batch.expiry_date = expiry_date
    inv = Inventory.query.filter_by(product_id=product_id, warehouse_id=warehouse_id, batch_id=batch.id).first()
    if inv is None:
        inv = Inventory(product_id=product_id, warehouse_id=warehouse_id, batch_id=batch.id, quantity=0)
        db.session.add(inv)
    inv.quantity += qty
    db.session.add(StockMovement(product_id=product_id, warehouse_id=warehouse_id, batch_id=batch.id, movement_type=movement_type,
                                 quantity=qty, unit_cost=batch.unit_cost, reference_type=ref_type, reference_id=ref_id,
                                 note=note, user_id=user_id, created_at=at))
    db.session.flush()
    stock_warnings(product_id, warehouse_id, notify_users=True)
    return batch


def stock_warnings(product_id, warehouse_id, notify_users=False):
    """Non-blocking warnings: warehouse over capacity, product above its maximum stock level."""
    out = []
    w, p = db.session.get(Warehouse, warehouse_id), db.session.get(Product, product_id)
    if w and w.capacity and warehouse_units(warehouse_id) > w.capacity:
        out.append(f"{w.name} is over capacity ({warehouse_units(warehouse_id)} / {w.capacity} units)")
        if notify_users:
            notify("low_stock", f"Warehouse over capacity: {w.name}", out[-1], "/warehouses")
    if p and p.max_stock and on_hand(product_id) > p.max_stock:
        out.append(f"{p.name} is above its maximum stock level ({on_hand(product_id)} / {p.max_stock})")
        if notify_users:
            notify("low_stock", f"Overstock: {p.name}", out[-1], "/inventory")
    return out


def stock_out(product_id, warehouse_id, qty, *, movement_type="OUT", ref_type=None, ref_id=None, note=None, user_id=None,
              override=False, at=None, batch_id=None, check_low=True):
    """Remove stock FIFO (oldest layer first). Returns (cogs, layers_used). Blocks negative stock unless override=True."""
    if qty is None or qty <= 0:
        raise BusinessError("Quantity must be greater than zero", 422)
    at = at or now()
    layers = fifo_layers(product_id, warehouse_id, batch_id)
    on = sum(l.quantity for l in layers)
    avail = on - (0 if batch_id else reserved_qty(product_id, warehouse_id))
    if qty > avail and not override:
        p = db.session.get(Product, product_id)
        raise BusinessError(f"Insufficient stock for {p.name}: available {max(avail, 0)}, requested {qty}", 409, code="insufficient_stock")
    remaining, cogs, used = qty, 0.0, []
    for l in layers:
        if remaining <= 0:
            break
        take = min(l.quantity, remaining)
        l.quantity -= take
        remaining -= take
        cogs += take * l.batch.unit_cost
        used.append({"batch_id": l.batch_id, "quantity": take, "unit_cost": l.batch.unit_cost})
        db.session.add(StockMovement(product_id=product_id, warehouse_id=warehouse_id, batch_id=l.batch_id, movement_type=movement_type,
                                     quantity=-take, unit_cost=l.batch.unit_cost, reference_type=ref_type, reference_id=ref_id,
                                     note=note, user_id=user_id, created_at=at))
    if remaining > 0:  # authorised override: record negative stock on a dedicated layer
        if batch_id:
            raise BusinessError("Selected batch does not hold enough stock", 409)
        p = db.session.get(Product, product_id)
        b = Batch.query.filter_by(product_id=product_id, batch_no="NEG-OVERRIDE").first()
        if b is None:
            b = Batch(product_id=product_id, batch_no="NEG-OVERRIDE", unit_cost=p.purchase_price, received_at=at)
            db.session.add(b)
            db.session.flush()
        inv = Inventory.query.filter_by(product_id=product_id, warehouse_id=warehouse_id, batch_id=b.id).first()
        if inv is None:
            inv = Inventory(product_id=product_id, warehouse_id=warehouse_id, batch_id=b.id, quantity=0)
            db.session.add(inv)
        inv.quantity -= remaining
        cogs += remaining * b.unit_cost
        used.append({"batch_id": b.id, "quantity": remaining, "unit_cost": b.unit_cost})
        db.session.add(StockMovement(product_id=product_id, warehouse_id=warehouse_id, batch_id=b.id, movement_type=movement_type,
                                     quantity=-remaining, unit_cost=b.unit_cost, reference_type=ref_type, reference_id=ref_id,
                                     note=(note or "") + " [negative stock override]", user_id=user_id, created_at=at))
    db.session.flush()
    if check_low:
        check_low_stock(product_id)
    return round(cogs, 2), used


def check_low_stock(product_id):
    p = db.session.get(Product, product_id)
    if not p or p.status != "active":
        return
    qty = on_hand(product_id)
    if qty <= 0:
        notify("low_stock", f"Out of stock: {p.name}", f"{p.sku} has no stock on hand.", "/inventory")
    elif p.min_stock > 0 and qty <= p.min_stock:
        notify("low_stock", f"Low stock: {p.name}", f"{qty} {p.unit} left (minimum {p.min_stock}).", "/inventory")


def reserve(product_id, warehouse_id, qty, ref_type, ref_id, user_id=None, note=None):
    if qty <= 0:
        raise BusinessError("Quantity must be greater than zero", 422)
    av = available(product_id, warehouse_id)
    if qty > av:
        p = db.session.get(Product, product_id)
        raise BusinessError(f"Cannot reserve {qty} of {p.name}: only {max(av, 0)} available", 409, code="insufficient_stock")
    r = Reservation(product_id=product_id, warehouse_id=warehouse_id, quantity=qty, reference_type=ref_type,
                    reference_id=ref_id, created_by=user_id, note=note)
    db.session.add(r)
    db.session.flush()
    return r


def close_reservations(ref_type, ref_id, status="released"):
    for r in Reservation.query.filter_by(reference_type=ref_type, reference_id=ref_id, status="active").all():
        r.status = status
    db.session.flush()


def adjust(product_id, warehouse_id, *, delta=None, new_quantity=None, reason="Stock adjustment", user_id=None, override=False,
           movement_type="ADJUST", ref_type="adjustment", ref_id=None):
    cur = on_hand(product_id, warehouse_id)
    if new_quantity is not None:
        delta = new_quantity - cur
    if not delta:
        return 0
    p = db.session.get(Product, product_id)
    if delta > 0:
        stock_in(product_id, warehouse_id, delta, p.purchase_price, batch_no=f"ADJ-{now():%Y%m%d}", movement_type=movement_type,
                 ref_type=ref_type, ref_id=ref_id, note=reason, user_id=user_id)
    else:
        stock_out(product_id, warehouse_id, -delta, movement_type=movement_type, ref_type=ref_type, ref_id=ref_id, note=reason,
                  user_id=user_id, override=override)
    return delta


def reorder_recommendations():
    stock, res = stock_map(), reserved_map()
    out = []
    for p in Product.query.filter_by(status="active").all():
        qty, r = stock.get(p.id, 0), res.get(p.id, 0)
        avail = qty - r
        if p.min_stock > 0 and avail <= p.min_stock or avail <= 0:
            target = p.max_stock or max(p.min_stock * 3, 1)
            suggested = max(p.reorder_qty or 0, target - avail)
            out.append({"product_id": p.id, "sku": p.sku, "name": p.name, "on_hand": qty, "reserved": r, "available": avail,
                        "min_stock": p.min_stock, "max_stock": p.max_stock, "suggested_qty": int(suggested),
                        "supplier_id": p.supplier_id, "supplier_name": p.supplier.name if p.supplier else None,
                        "estimated_cost": round(suggested * p.purchase_price, 2)})
    return sorted(out, key=lambda x: x["available"])
