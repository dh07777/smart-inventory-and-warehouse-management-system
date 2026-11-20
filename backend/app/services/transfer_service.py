import json
from ..extensions import db
from ..models import Transfer, TransferItem, Product, Warehouse, Batch
from ..utils import BusinessError, now, next_number
from . import inventory_service as inv
from .notification_service import notify


def create(data, user, demo=False):
    if data["from_warehouse_id"] == data["to_warehouse_id"]:
        raise BusinessError("Source and destination warehouses must differ", 422)
    for wid in (data["from_warehouse_id"], data["to_warehouse_id"]):
        w = db.session.get(Warehouse, wid)
        if not w or not w.is_active:
            raise BusinessError("Warehouse not found or inactive", 422)
    t = Transfer(transfer_number=next_number("TRF", Transfer), from_warehouse_id=data["from_warehouse_id"],
                 to_warehouse_id=data["to_warehouse_id"], notes=data.get("notes"), requested_by=user.id, is_demo=demo)
    merged = {}
    for it in data["items"]:
        merged[it["product_id"]] = merged.get(it["product_id"], 0) + it["quantity"]
    for pid, qty in merged.items():
        if not db.session.get(Product, pid):
            raise BusinessError(f"Product {pid} not found", 422)
        t.items.append(TransferItem(product_id=pid, quantity=qty))
    db.session.add(t)
    db.session.flush()
    notify("transfer", f"Transfer {t.transfer_number} requested", f"{t.from_warehouse.name} -> {t.to_warehouse.name}", "/transfers")
    return t


def approve(t, user):
    if t.status != "requested":
        raise BusinessError(f"Only requested transfers can be approved (current: {t.status})", 409)
    for i in t.items:
        av = inv.available(i.product_id, t.from_warehouse_id)
        if av < i.quantity:
            raise BusinessError(f"Source warehouse has only {max(av, 0)} available of {i.product.name}", 409)
    t.status, t.approved_by = "approved", user.id
    notify("transfer", f"Transfer {t.transfer_number} approved", "Ready to dispatch.", "/transfers")


def reject(t, user, reason):
    if t.status != "requested":
        raise BusinessError("Only requested transfers can be rejected", 409)
    t.status, t.approved_by, t.rejection_reason = "rejected", user.id, reason


def cancel(t):
    if t.status not in ("requested", "approved"):
        raise BusinessError("Only requested or approved transfers can be cancelled", 409)
    t.status = "cancelled"


def dispatch(t, lines, user, key=None):
    if t.status != "approved":
        raise BusinessError("Transfer must be approved before dispatch", 409)
    inv.claim_operation(key, f"trf-dispatch-{t.id}")
    qty_by_item = {l["item_id"]: l["quantity"] for l in (lines or [])}
    moved = 0
    for i in t.items:
        qty = qty_by_item.get(i.id, i.quantity)
        if qty < 0 or qty > i.quantity:
            raise BusinessError(f"Dispatch quantity for {i.product.name} must be between 0 and {i.quantity}", 422)
        if qty == 0:
            continue
        _, used = inv.stock_out(i.product_id, t.from_warehouse_id, qty, movement_type="TRANSFER_OUT", ref_type="transfer", ref_id=t.id,
                                note=f"Transfer {t.transfer_number}", user_id=user.id)
        i.dispatched_qty, i.layers = qty, json.dumps(used)
        moved += qty
    if moved == 0:
        raise BusinessError("Nothing dispatched", 422)
    t.status, t.dispatched_at = "in_transit", now()


def receive(t, lines, user, note=None, key=None):
    if t.status != "in_transit":
        raise BusinessError("Only in-transit transfers can be received", 409)
    inv.claim_operation(key, f"trf-receive-{t.id}")
    rec = {l["item_id"]: l["received_qty"] for l in (lines or [])}
    discrepancy = False
    for i in t.items:
        if not i.dispatched_qty:
            continue
        qty = rec.get(i.id, i.dispatched_qty)
        if qty < 0 or qty > i.dispatched_qty:
            raise BusinessError(f"Received quantity for {i.product.name} must be between 0 and {i.dispatched_qty}", 422)
        remaining = qty
        for layer in json.loads(i.layers or "[]"):  # keep FIFO cost layers intact at destination
            take = min(layer["quantity"], remaining)
            if take > 0:
                inv.stock_in(i.product_id, t.to_warehouse_id, take, layer["unit_cost"], batch=db.session.get(Batch, layer["batch_id"]),
                             movement_type="TRANSFER_IN", ref_type="transfer", ref_id=t.id, note=f"Transfer {t.transfer_number}", user_id=user.id)
                remaining -= take
        i.received_qty = qty
        if qty != i.dispatched_qty:
            discrepancy = True
    t.status, t.received_at = "received", now()
    if discrepancy:
        t.discrepancy_status = "open"
        t.notes = ((t.notes or "") + f" | Receipt note: {note}").strip(" |") if note else t.notes
        notify("transfer", f"Transfer {t.transfer_number} has a discrepancy", "Received quantity differs from dispatched.", "/transfers")
    else:
        notify("transfer", f"Transfer {t.transfer_number} received", "", "/transfers")


def resolve_discrepancy(t, note):
    if t.discrepancy_status != "open":
        raise BusinessError("No open discrepancy on this transfer", 409)
    t.discrepancy_status, t.resolution_note = "resolved", note
