from flask import Blueprint, request, send_file
from sqlalchemy import func
from ..extensions import db
from ..models import SalesOrder, SalesOrderItem, SalesReturn, Product, Customer
from ..schemas import SOSchema, DispatchSchema, SOPaymentSchema, ReturnSchema
from ..utils import ok, load, paginate, audit, permission_required, current_user, BusinessError, parse_date
from ..services import sales_service as svc
from ..repositories import order_repository as orders
from ..services.report_service import invoice_pdf

bp = Blueprint("sales", __name__, url_prefix="/api/sales")
FULFILLED = ["dispatched", "delivered", "returned"]


@bp.get("")
@permission_required("sales.view")
def list_sos():
    return paginate(orders.sales_orders(request.args, parse_date(request.args.get("date_from")), parse_date(request.args.get("date_to"))))


@bp.get("/analytics")
@permission_required("sales.view")
def analytics():
    return ok({"monthly": [{"month": a, "revenue": round(r, 2), "cogs": round(c or 0, 2), "orders": n} for a, r, c, n in orders.sales_monthly()],
               "by_status": [{"status": s, "count": c} for s, c in orders.sales_by_status()],
               "top_customers": [{"customer": n, "total": round(t, 2)} for n, t in orders.top_customers()]})


@bp.get("/returns")
@permission_required("sales.view")
def list_returns():
    q = SalesReturn.query
    if request.args.get("status"):
        q = q.filter_by(status=request.args["status"])
    return paginate(q.order_by(SalesReturn.id.desc()))


@bp.post("/returns/<int:rid>/approve")
@permission_required("sales.process")
def approve_return(rid):
    r = db.get_or_404(SalesReturn, rid)
    svc.approve_return(r, current_user())
    audit("sales.return_approve", "sales_return", rid, {"refund": r.refund_amount})
    db.session.commit()
    return ok(r.to_dict(), "Return approved, stock updated and refund recorded")


@bp.post("/returns/<int:rid>/reject")
@permission_required("sales.process")
def reject_return(rid):
    r = db.get_or_404(SalesReturn, rid)
    svc.reject_return(r, current_user())
    audit("sales.return_reject", "sales_return", rid)
    db.session.commit()
    return ok(r.to_dict(), "Return rejected")


@bp.get("/<int:oid>")
@permission_required("sales.view")
def get_so(oid):
    so = db.get_or_404(SalesOrder, oid)
    d = so.detail()
    d["returns"] = [r.to_dict() for r in SalesReturn.query.filter_by(sales_order_id=oid)]
    return ok(d)


@bp.post("")
@permission_required("sales.create")
def create_so():
    so = svc.create_so(load(SOSchema), current_user())
    audit("sales.create", "sales_order", so.id, {"so": so.so_number, "total": so.total})
    db.session.commit()
    return ok(so.detail(), "Sales order created", 201)


@bp.post("/<int:oid>/confirm")
@permission_required("sales.process")
def confirm(oid):
    so = db.get_or_404(SalesOrder, oid)
    svc.confirm(so, current_user())
    audit("sales.confirm", "sales_order", oid)
    db.session.commit()
    return ok(so.detail(), "Order confirmed and stock reserved")


@bp.post("/<int:oid>/dispatch")
@permission_required("sales.process")
def dispatch(oid):
    so = db.get_or_404(SalesOrder, oid)
    d = load(DispatchSchema)
    svc.dispatch(so, current_user(), d.get("carrier"), d.get("tracking_no"), d.get("idempotency_key"))
    audit("sales.dispatch", "sales_order", oid, d)
    db.session.commit()
    return ok(so.detail(), "Order dispatched and stock deducted")


@bp.post("/<int:oid>/deliver")
@permission_required("sales.process")
def deliver(oid):
    so = db.get_or_404(SalesOrder, oid)
    svc.deliver(so)
    audit("sales.deliver", "sales_order", oid)
    db.session.commit()
    return ok(so.detail(), "Order marked as delivered")


@bp.post("/<int:oid>/cancel")
@permission_required("sales.create", "sales.process")
def cancel(oid):
    so = db.get_or_404(SalesOrder, oid)
    svc.cancel(so)
    audit("sales.cancel", "sales_order", oid)
    db.session.commit()
    return ok(so.detail(), "Order cancelled")


@bp.post("/<int:oid>/payment")
@permission_required("sales.process")
def payment(oid):
    so = db.get_or_404(SalesOrder, oid)
    svc.record_payment(so, load(SOPaymentSchema)["amount"])
    audit("sales.payment", "sales_order", oid)
    db.session.commit()
    return ok(so.detail(), "Payment recorded")


@bp.post("/<int:oid>/returns")
@permission_required("sales.process")
def create_return(oid):
    so = db.get_or_404(SalesOrder, oid)
    r = svc.create_return(so, load(ReturnSchema), current_user())
    audit("sales.return_request", "sales_return", r.id)
    db.session.commit()
    return ok(r.to_dict(), "Return requested", 201)


@bp.get("/<int:oid>/invoice.pdf")
@permission_required("sales.view")
def invoice(oid):
    so = db.get_or_404(SalesOrder, oid)
    if not so.invoice_no:
        raise BusinessError("Invoice is available once the order is dispatched", 409)
    return send_file(invoice_pdf("sales", so), mimetype="application/pdf", download_name=f"{so.invoice_no}.pdf")
