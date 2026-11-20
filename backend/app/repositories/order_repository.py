"""Data access for purchase orders, sales orders and transfers (list filters + aggregate queries)."""
from sqlalchemy import func
from ..extensions import db
from ..models import PurchaseOrder, SalesOrder, Transfer, Supplier, Customer


def _date_filter(q, col, date_from, date_to):
    if date_from:
        q = q.filter(func.date(col) >= date_from.isoformat())
    if date_to:
        q = q.filter(func.date(col) <= date_to.isoformat())
    return q


def purchase_orders(args, date_from=None, date_to=None):
    q = PurchaseOrder.query
    for f in ("status", "supplier_id", "warehouse_id"):
        if args.get(f):
            q = q.filter(getattr(PurchaseOrder, f) == args[f])
    if (args.get("q") or "").strip():
        q = q.filter(PurchaseOrder.po_number.ilike(f"%{args['q'].strip()}%"))
    return _date_filter(q, PurchaseOrder.order_date, date_from, date_to).order_by(PurchaseOrder.id.desc())


def sales_orders(args, date_from=None, date_to=None):
    q = SalesOrder.query
    for f in ("status", "customer_id", "warehouse_id"):
        if args.get(f):
            q = q.filter(getattr(SalesOrder, f) == args[f])
    if (args.get("q") or "").strip():
        q = q.filter(SalesOrder.so_number.ilike(f"%{args['q'].strip()}%"))
    return _date_filter(q, SalesOrder.order_date, date_from, date_to).order_by(SalesOrder.id.desc())


def transfers(args):
    q = Transfer.query
    for f in ("status", "from_warehouse_id", "to_warehouse_id", "discrepancy_status"):
        if args.get(f):
            q = q.filter(getattr(Transfer, f) == args[f])
    if (args.get("q") or "").strip():
        q = q.filter(Transfer.transfer_number.ilike(f"%{args['q'].strip()}%"))
    return q.order_by(Transfer.id.desc())


def purchase_monthly():
    m = func.strftime("%Y-%m", PurchaseOrder.order_date)
    return (db.session.query(m, func.sum(PurchaseOrder.total), func.count(PurchaseOrder.id))
            .filter(PurchaseOrder.status.notin_(["rejected", "cancelled", "pending_approval"])).group_by(m).order_by(m).all())


def purchase_by_status():
    return db.session.query(PurchaseOrder.status, func.count(PurchaseOrder.id)).group_by(PurchaseOrder.status).all()


def top_suppliers(limit=5):
    return (db.session.query(Supplier.name, func.sum(PurchaseOrder.total)).join(PurchaseOrder, PurchaseOrder.supplier_id == Supplier.id)
            .filter(PurchaseOrder.status.notin_(["rejected", "cancelled", "pending_approval"])).group_by(Supplier.id)
            .order_by(func.sum(PurchaseOrder.total).desc()).limit(limit).all())


FULFILLED = ["dispatched", "delivered", "returned"]


def sales_monthly():
    m = func.strftime("%Y-%m", SalesOrder.order_date)
    return (db.session.query(m, func.sum(SalesOrder.total), func.sum(SalesOrder.cogs_total), func.count(SalesOrder.id))
            .filter(SalesOrder.status.in_(FULFILLED)).group_by(m).order_by(m).all())


def sales_by_status():
    return db.session.query(SalesOrder.status, func.count(SalesOrder.id)).group_by(SalesOrder.status).all()


def top_customers(limit=5):
    return (db.session.query(Customer.name, func.sum(SalesOrder.total)).join(SalesOrder, SalesOrder.customer_id == Customer.id)
            .filter(SalesOrder.status.in_(FULFILLED)).group_by(Customer.id).order_by(func.sum(SalesOrder.total).desc()).limit(limit).all())
