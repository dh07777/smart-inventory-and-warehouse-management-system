"""Data access for stock: all inventory/movement/batch queries live here (no business rules, no Flask objects)."""
from datetime import timedelta, datetime
from sqlalchemy import func
from ..extensions import db
from ..models import Inventory, Batch, Product, Warehouse, StockMovement, Reservation


def on_hand(product_id, warehouse_id=None):
    q = db.session.query(func.coalesce(func.sum(Inventory.quantity), 0)).filter(Inventory.product_id == product_id)
    if warehouse_id:
        q = q.filter(Inventory.warehouse_id == warehouse_id)
    return int(q.scalar())


def warehouse_units(warehouse_id):
    return int(db.session.query(func.coalesce(func.sum(Inventory.quantity), 0)).filter(Inventory.warehouse_id == warehouse_id).scalar())


def reserved_qty(product_id, warehouse_id=None):
    q = db.session.query(func.coalesce(func.sum(Reservation.quantity), 0)).filter(
        Reservation.product_id == product_id, Reservation.status == "active")
    if warehouse_id:
        q = q.filter(Reservation.warehouse_id == warehouse_id)
    return int(q.scalar())


def available(product_id, warehouse_id=None):
    return on_hand(product_id, warehouse_id) - reserved_qty(product_id, warehouse_id)


def stock_map(warehouse_id=None):
    q = db.session.query(Inventory.product_id, func.sum(Inventory.quantity)).group_by(Inventory.product_id)
    if warehouse_id:
        q = q.filter(Inventory.warehouse_id == warehouse_id)
    return {p: int(s or 0) for p, s in q}


def reserved_map(warehouse_id=None):
    q = db.session.query(Reservation.product_id, func.sum(Reservation.quantity)).filter(Reservation.status == "active").group_by(Reservation.product_id)
    if warehouse_id:
        q = q.filter(Reservation.warehouse_id == warehouse_id)
    return {p: int(s or 0) for p, s in q}


def reserved_by_location():
    return {(p, w): int(n) for p, w, n in db.session.query(Reservation.product_id, Reservation.warehouse_id, func.sum(Reservation.quantity))
            .filter(Reservation.status == "active").group_by(Reservation.product_id, Reservation.warehouse_id)}


def valuation(warehouse_id=None):
    """FIFO valuation = sum(layer qty x layer cost)."""
    q = db.session.query(func.coalesce(func.sum(Inventory.quantity * Batch.unit_cost), 0)).join(Batch, Inventory.batch_id == Batch.id)
    if warehouse_id:
        q = q.filter(Inventory.warehouse_id == warehouse_id)
    return round(float(q.scalar()), 2)


def fifo_layers(product_id, warehouse_id, batch_id=None):
    """Positive stock layers, oldest first (FIFO)."""
    q = (Inventory.query.join(Batch, Inventory.batch_id == Batch.id)
         .filter(Inventory.product_id == product_id, Inventory.warehouse_id == warehouse_id, Inventory.quantity > 0)
         .order_by(Batch.received_at, Batch.id))
    if batch_id:
        q = q.filter(Inventory.batch_id == batch_id)
    return q.all()


def low_and_out_products():
    stock = stock_map()
    low, out = [], []
    for p in Product.query.filter_by(status="active").all():
        qty = stock.get(p.id, 0)
        if qty <= 0:
            out.append((p, qty))
        elif p.min_stock > 0 and qty <= p.min_stock:
            low.append((p, qty))
    return low, out


def stock_rows(args):
    """Stock per product x warehouse (with FIFO value). `args` is any mapping of filters."""
    q = (db.session.query(Product, Warehouse, func.sum(Inventory.quantity), func.sum(Inventory.quantity * Batch.unit_cost))
         .join(Inventory, Inventory.product_id == Product.id).join(Warehouse, Warehouse.id == Inventory.warehouse_id)
         .join(Batch, Batch.id == Inventory.batch_id).group_by(Product.id, Warehouse.id).having(func.sum(Inventory.quantity) != 0))
    for f, col in (("warehouse_id", Inventory.warehouse_id), ("product_id", Inventory.product_id), ("category_id", Product.category_id)):
        if args.get(f):
            q = q.filter(col == int(args[f]))
    s = (args.get("q") or "").strip()
    if s:
        q = q.filter(Product.name.ilike(f"%{s}%") | Product.sku.ilike(f"%{s}%"))
    if args.get("status") == "low":
        q = q.having(func.sum(Inventory.quantity) <= Product.min_stock)
    return q.order_by(Product.name, Warehouse.name)


def batch_rows(args, today):
    q = Inventory.query.join(Batch).filter(Inventory.quantity != 0)
    for f in ("warehouse_id", "product_id"):
        if args.get(f):
            q = q.filter(getattr(Inventory, f) == int(args[f]))
    if args.get("expiring_in_days") not in (None, ""):
        q = q.filter(Batch.expiry_date.isnot(None), Batch.expiry_date <= today + timedelta(days=int(args["expiring_in_days"])))
    return q.order_by(Batch.expiry_date.is_(None), Batch.expiry_date, Batch.received_at)


def movement_rows(args, date_from=None, date_to=None):
    q = StockMovement.query
    for f in ("warehouse_id", "product_id"):
        if args.get(f):
            q = q.filter(getattr(StockMovement, f) == int(args[f]))
    if args.get("type"):
        q = q.filter(StockMovement.movement_type == args["type"])
    if date_from:
        q = q.filter(StockMovement.created_at >= datetime.combine(date_from, datetime.min.time()))
    if date_to:
        q = q.filter(StockMovement.created_at < datetime.combine(date_to + timedelta(days=1), datetime.min.time()))
    return q.order_by(StockMovement.created_at.desc(), StockMovement.id.desc())


def expiring_batches(limit_date):
    return (db.session.query(Batch, func.sum(Inventory.quantity)).join(Inventory, Inventory.batch_id == Batch.id)
            .filter(Batch.expiry_date.isnot(None), Batch.expiry_date <= limit_date).group_by(Batch.id)
            .having(func.sum(Inventory.quantity) > 0).order_by(Batch.expiry_date).all())
