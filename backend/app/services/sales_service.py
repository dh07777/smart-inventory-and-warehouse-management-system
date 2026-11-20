from ..extensions import db
from ..models import SalesOrder, SalesOrderItem, SalesReturn, SalesReturnItem, Product, Customer, Warehouse
from ..utils import BusinessError, now, next_number
from . import inventory_service as inv
from .notification_service import notify


def create_so(data, user, at=None, demo=False):
    cust = db.session.get(Customer, data["customer_id"])
    wh = db.session.get(Warehouse, data["warehouse_id"])
    if not cust or not cust.is_active:
        raise BusinessError("Customer not found or inactive", 422)
    if not wh or not wh.is_active:
        raise BusinessError("Warehouse not found or inactive", 422)
    so = SalesOrder(so_number=next_number("SO", SalesOrder), customer_id=cust.id, warehouse_id=wh.id, notes=data.get("notes"),
                    created_by=user.id, order_date=at or now(), is_demo=demo)
    seen = {}
    for it in data["items"]:
        if it["product_id"] in seen:
            seen[it["product_id"]]["quantity"] += it["quantity"]
        else:
            seen[it["product_id"]] = dict(it)
    for pid, it in seen.items():
        p = db.session.get(Product, pid)
        if not p or p.status != "active":
            raise BusinessError(f"Product {pid} not found or not active", 422)
        so.items.append(SalesOrderItem(product_id=pid, quantity=it["quantity"],
                                       unit_price=it["unit_price"] if it.get("unit_price") is not None else p.selling_price,
                                       discount=it["discount"] if it.get("discount") is not None else p.discount, tax_rate=p.tax_rate))
    so.recalc()
    db.session.add(so)
    db.session.flush()
    notify("sales", f"New sales order {so.so_number}", f"{cust.name} - total {so.total}", "/sales")
    return so


def confirm(so, user):
    if so.status != "pending":
        raise BusinessError(f"Only pending orders can be confirmed (current: {so.status})", 409)
    for i in so.items:
        inv.reserve(i.product_id, so.warehouse_id, i.quantity, "sales_order", so.id, user.id)
    so.status = "confirmed"


def dispatch(so, user, carrier=None, tracking_no=None, key=None, at=None):
    if so.status != "confirmed":
        raise BusinessError("Order must be confirmed (stock reserved) before dispatch", 409)
    inv.claim_operation(key, f"so-dispatch-{so.id}")
    inv.close_reservations("sales_order", so.id, "consumed")
    total = 0.0
    for i in so.items:
        cogs, _ = inv.stock_out(i.product_id, so.warehouse_id, i.quantity, movement_type="OUT", ref_type="sales_order", ref_id=so.id,
                                note=f"Dispatched {so.so_number}", user_id=user.id, at=at)
        i.cogs = cogs
        total += cogs
    so.cogs_total = round(total, 2)
    so.status, so.carrier, so.tracking_no, so.dispatched_at = "dispatched", carrier, tracking_no, at or now()
    if not so.invoice_no:
        so.invoice_no = f"SINV-{so.so_number[3:]}"
    notify("sales", f"{so.so_number} dispatched", carrier or "", "/sales")


def deliver(so, at=None):
    if so.status != "dispatched":
        raise BusinessError("Only dispatched orders can be marked delivered", 409)
    so.status, so.delivered_at = "delivered", at or now()


def cancel(so):
    if so.status not in ("pending", "confirmed"):
        raise BusinessError("Dispatched orders cannot be cancelled; create a return instead", 409)
    inv.close_reservations("sales_order", so.id, "released")
    so.status = "cancelled"


def record_payment(so, amount):
    due = round(so.total - so.refunded_amount - so.paid_amount, 2)
    if amount <= 0 or amount > due + 0.005:
        raise BusinessError(f"Payment must be between 0 and the outstanding amount ({due})", 422)
    so.paid_amount = round(so.paid_amount + amount, 2)


def _already_returned(so, product_id):
    n = 0
    for r in SalesReturn.query.filter(SalesReturn.sales_order_id == so.id, SalesReturn.status != "rejected").all():
        n += sum(i.quantity for i in r.items if i.product_id == product_id)
    return n


def create_return(so, data, user):
    if so.status not in ("dispatched", "delivered", "returned"):
        raise BusinessError("Only dispatched or delivered orders can be returned", 409)
    ret = SalesReturn(return_number=next_number("RET", SalesReturn), sales_order_id=so.id, reason=data.get("reason"),
                      restock=data.get("restock", True), created_by=user.id)
    refund = 0.0
    sold = {i.product_id: i for i in so.items}
    for ln in data["items"]:
        item = sold.get(ln["product_id"])
        if not item:
            raise BusinessError("Product is not part of this order", 422)
        if ln["quantity"] + _already_returned(so, item.product_id) > item.quantity:
            raise BusinessError(f"Return quantity exceeds quantity sold for {item.product.name}", 409)
        ret.items.append(SalesReturnItem(product_id=item.product_id, quantity=ln["quantity"], condition=ln.get("condition") or "good"))
        refund += ln["quantity"] * item.unit_price * (1 - item.discount / 100) * (1 + item.tax_rate / 100)
    ret.refund_amount = round(refund, 2)
    db.session.add(ret)
    db.session.flush()
    notify("sales", f"Return requested {ret.return_number}", f"For {so.so_number}", "/sales")
    return ret


def approve_return(ret, user):
    if ret.status != "requested":
        raise BusinessError("Return was already processed", 409)
    so = ret.order
    sold = {i.product_id: i for i in so.items}
    for ln in ret.items:
        if ret.restock and ln.condition == "good":
            item = sold[ln.product_id]
            unit_cost = (item.cogs / item.quantity) if item.quantity else ln.product.purchase_price
            inv.stock_in(ln.product_id, so.warehouse_id, ln.quantity, unit_cost, batch_no=f"{ret.return_number}", movement_type="RETURN_IN",
                         ref_type="sales_return", ref_id=ret.id, note=f"Return {ret.return_number}", user_id=user.id)
    ret.status, ret.processed_by = "refunded", user.id
    so.refunded_amount = round(so.refunded_amount + ret.refund_amount, 2)
    if all(_already_returned(so, i.product_id) >= i.quantity for i in so.items):
        so.status = "returned"


def reject_return(ret, user):
    if ret.status != "requested":
        raise BusinessError("Return was already processed", 409)
    ret.status, ret.processed_by = "rejected", user.id
