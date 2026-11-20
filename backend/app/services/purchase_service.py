from datetime import date
from ..extensions import db
from ..models import PurchaseOrder, PurchaseOrderItem, PurchaseRequest, PurchaseRequestItem, Product, Supplier, Warehouse
from ..utils import BusinessError, now, next_number
from . import inventory_service as inv
from .notification_service import notify


def _merge_items(items):
    merged = {}
    for it in items:
        merged[it["product_id"]] = merged.get(it["product_id"], 0) + it["quantity"]
    return merged


def create_po(data, user, at=None, demo=False):
    sup = db.session.get(Supplier, data["supplier_id"])
    wh = db.session.get(Warehouse, data["warehouse_id"])
    if not sup or not sup.is_active:
        raise BusinessError("Supplier not found or inactive", 422)
    if not wh or not wh.is_active:
        raise BusinessError("Warehouse not found or inactive", 422)
    po = PurchaseOrder(po_number=next_number("PO", PurchaseOrder), supplier_id=sup.id, warehouse_id=wh.id, status="pending_approval",
                       expected_date=data.get("expected_date"), notes=data.get("notes"), created_by=user.id,
                       order_date=at or now(), is_demo=demo)
    prices = {i["product_id"]: i.get("unit_price") for i in data["items"]}
    for pid, qty in _merge_items(data["items"]).items():
        p = db.session.get(Product, pid)
        if not p:
            raise BusinessError(f"Product {pid} not found", 422)
        price = prices.get(pid)
        po.items.append(PurchaseOrderItem(product_id=pid, quantity=qty, unit_price=price if price is not None else p.purchase_price,
                                          tax_rate=p.tax_rate))
    po.recalc()
    db.session.add(po)
    db.session.flush()
    notify("purchase", f"PO {po.po_number} awaiting approval", f"{sup.name} - total {po.total}", "/purchases")
    return po


def approve(po, user, at=None):
    if po.status != "pending_approval":
        raise BusinessError(f"Only pending orders can be approved (current: {po.status})", 409)
    po.status, po.approved_by, po.approved_at = "approved", user.id, at or now()
    notify("purchase", f"PO {po.po_number} approved", "Ready to receive goods.", "/purchases")


def reject(po, user, reason):
    if po.status != "pending_approval":
        raise BusinessError(f"Only pending orders can be rejected (current: {po.status})", 409)
    po.status, po.approved_by, po.approved_at, po.rejection_reason = "rejected", user.id, now(), reason
    notify("purchase", f"PO {po.po_number} rejected", reason or "", "/purchases")


def cancel(po):
    if po.status not in ("pending_approval", "approved"):
        raise BusinessError("Only pending or approved orders without receipts can be cancelled", 409)
    if any(i.received_qty for i in po.items):
        raise BusinessError("Goods were already received against this order", 409)
    po.status = "cancelled"


def receive(po, lines, user, key=None, at=None):
    """Receive goods (partial deliveries supported). Creates FIFO layers and movement history."""
    if po.status not in ("approved", "partially_received"):
        raise BusinessError(f"Order must be approved before receiving (current: {po.status})", 409)
    inv.claim_operation(key, f"po-receive-{po.id}")
    by_id = {i.id: i for i in po.items}
    got = 0
    for ln in lines:
        item = by_id.get(ln["item_id"])
        if not item:
            raise BusinessError(f"Item {ln['item_id']} does not belong to {po.po_number}", 422)
        qty = ln["quantity"]
        if qty <= 0:
            continue
        if qty > item.quantity - item.received_qty:
            raise BusinessError(f"Cannot receive {qty} of {item.product.name}: only {item.quantity - item.received_qty} outstanding", 409)
        inv.stock_in(item.product_id, po.warehouse_id, qty, item.unit_price, batch_no=ln.get("batch_no") or f"{po.po_number}-{item.id}",
                     expiry_date=ln.get("expiry_date"), mfg_date=ln.get("mfg_date"), movement_type="IN",
                     ref_type="purchase_order", ref_id=po.id, note=f"Received against {po.po_number}", user_id=user.id,
                     supplier_id=po.supplier_id, at=at)
        item.received_qty += qty
        got += qty
    if got == 0:
        raise BusinessError("Nothing to receive: enter at least one quantity", 422)
    if all(i.received_qty >= i.quantity for i in po.items):
        po.status, po.received_at = "received", at or now()
    else:
        po.status = "partially_received"
    notify("purchase", f"PO {po.po_number} {po.status.replace('_', ' ')}", f"{got} units added to stock.", "/purchases")
    return got


def make_invoice(po):
    if po.status not in ("received", "partially_received"):
        raise BusinessError("Invoices can be generated once goods have been received", 409)
    if not po.invoice_no:
        po.invoice_no = f"PINV-{po.po_number[3:]}"
        po.invoice_date = now()
    return po


# ---- purchase requests (request -> approval -> purchase order) ----
def create_request(data, user, demo=False):
    wh = db.session.get(Warehouse, data["warehouse_id"])
    if not wh or not wh.is_active:
        raise BusinessError("Warehouse not found or inactive", 422)
    req = PurchaseRequest(request_number=next_number("PR", PurchaseRequest), warehouse_id=wh.id, reason=data.get("reason"),
                          priority=data.get("priority") or "normal", needed_by=data.get("needed_by"), requested_by=user.id, is_demo=demo)
    notes = {i["product_id"]: i.get("note") for i in data["items"]}
    for pid, qty in _merge_items(data["items"]).items():
        if not db.session.get(Product, pid):
            raise BusinessError(f"Product {pid} not found", 422)
        req.items.append(PurchaseRequestItem(product_id=pid, quantity=qty, note=notes.get(pid)))
    db.session.add(req)
    db.session.flush()
    notify("purchase", f"Purchase request {req.request_number} needs review", f"{req.priority.title()} priority - {len(req.items)} item(s)", "/purchases")
    return req


def review_request(req, user, approve, reason=None):
    if req.status != "pending":
        raise BusinessError(f"Only pending requests can be reviewed (current: {req.status})", 409)
    req.status = "approved" if approve else "rejected"
    req.reviewed_by, req.reviewed_at, req.rejection_reason = user.id, now(), (None if approve else reason)
    notify("purchase", f"Purchase request {req.request_number} {req.status}", reason or "", "/purchases")


def cancel_request(req):
    if req.status not in ("pending", "approved"):
        raise BusinessError("Only pending or approved requests can be cancelled", 409)
    req.status = "cancelled"


def convert_request(req, data, user):
    """Generate a purchase order from an approved request. The PO starts as approved because the request already was."""
    if req.status != "approved":
        raise BusinessError("Only approved requests can be converted to a purchase order", 409)
    po = create_po({"supplier_id": data["supplier_id"], "warehouse_id": req.warehouse_id, "expected_date": data.get("expected_date") or req.needed_by,
                    "notes": data.get("notes") or f"Generated from {req.request_number}",
                    "items": [{"product_id": i.product_id, "quantity": i.quantity} for i in req.items]}, user, demo=req.is_demo)
    po.status, po.approved_by, po.approved_at = "approved", req.reviewed_by or user.id, now()
    req.status, req.purchase_order_id = "converted", po.id
    return po
