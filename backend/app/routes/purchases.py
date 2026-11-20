from flask import Blueprint, request, send_file
from sqlalchemy import func
from ..extensions import db
from ..models import PurchaseOrder, PurchaseOrderItem, PurchaseRequest, Product
from ..schemas import POSchema, ReceiveSchema, ReasonSchema, PurchaseRequestSchema, ConvertSchema
from ..utils import ok, load, paginate, audit, permission_required, current_user, BusinessError, parse_date
from ..services import purchase_service as svc
from ..repositories import order_repository as orders
from ..services.report_service import invoice_pdf

bp = Blueprint("purchases", __name__, url_prefix="/api/purchases")


@bp.get("")
@permission_required("purchases.view")
def list_pos():
    return paginate(orders.purchase_orders(request.args, parse_date(request.args.get("date_from")), parse_date(request.args.get("date_to"))))


@bp.get("/analytics")
@permission_required("purchases.view")
def analytics():
    return ok({"monthly": [{"month": m, "total": round(t, 2), "orders": c} for m, t, c in orders.purchase_monthly()],
               "by_status": [{"status": s, "count": c} for s, c in orders.purchase_by_status()],
               "top_suppliers": [{"supplier": n, "total": round(t, 2)} for n, t in orders.top_suppliers()]})


@bp.get("/<int:oid>")
@permission_required("purchases.view")
def get_po(oid):
    return ok(db.get_or_404(PurchaseOrder, oid).detail())


@bp.post("")
@permission_required("purchases.create")
def create_po():
    po = svc.create_po(load(POSchema), current_user())
    audit("purchase.create", "purchase_order", po.id, {"po": po.po_number, "total": po.total})
    db.session.commit()
    return ok(po.detail(), "Purchase request created and sent for approval", 201)


@bp.put("/<int:oid>")
@permission_required("purchases.create")
def update_po(oid):
    po = db.get_or_404(PurchaseOrder, oid)
    if po.status != "pending_approval":
        raise BusinessError("Only orders awaiting approval can be edited", 409)
    d = load(POSchema)
    po.supplier_id, po.warehouse_id, po.expected_date, po.notes = d["supplier_id"], d["warehouse_id"], d.get("expected_date"), d.get("notes")
    po.items.clear()
    merged = {}
    for it in d["items"]:
        merged.setdefault(it["product_id"], {"q": 0, "p": it.get("unit_price")})["q"] += it["quantity"]
    for pid, v in merged.items():
        p = db.get_or_404(Product, pid)
        po.items.append(PurchaseOrderItem(product_id=pid, quantity=v["q"], unit_price=v["p"] if v["p"] is not None else p.purchase_price, tax_rate=p.tax_rate))
    po.recalc()
    audit("purchase.update", "purchase_order", oid)
    db.session.commit()
    return ok(po.detail(), "Purchase order updated")


@bp.post("/<int:oid>/approve")
@permission_required("purchases.approve")
def approve(oid):
    po = db.get_or_404(PurchaseOrder, oid)
    svc.approve(po, current_user())
    audit("purchase.approve", "purchase_order", oid)
    db.session.commit()
    return ok(po.detail(), "Purchase order approved")


@bp.post("/<int:oid>/reject")
@permission_required("purchases.approve")
def reject(oid):
    po = db.get_or_404(PurchaseOrder, oid)
    svc.reject(po, current_user(), load(ReasonSchema).get("reason"))
    audit("purchase.reject", "purchase_order", oid)
    db.session.commit()
    return ok(po.detail(), "Purchase order rejected")


@bp.post("/<int:oid>/cancel")
@permission_required("purchases.create", "purchases.approve")
def cancel(oid):
    po = db.get_or_404(PurchaseOrder, oid)
    svc.cancel(po)
    audit("purchase.cancel", "purchase_order", oid)
    db.session.commit()
    return ok(po.detail(), "Purchase order cancelled")


@bp.post("/<int:oid>/receive")
@permission_required("purchases.receive")
def receive(oid):
    po = db.get_or_404(PurchaseOrder, oid)
    d = load(ReceiveSchema)
    got = svc.receive(po, d["items"], current_user(), d.get("idempotency_key"))
    audit("purchase.receive", "purchase_order", oid, {"units": got})
    db.session.commit()
    return ok(po.detail(), f"{got} units received into stock")


@bp.post("/<int:oid>/invoice")
@permission_required("purchases.view")
def make_invoice(oid):
    po = svc.make_invoice(db.get_or_404(PurchaseOrder, oid))
    db.session.commit()
    return ok(po.detail(), "Invoice generated")


@bp.get("/<int:oid>/invoice.pdf")
@permission_required("purchases.view")
def invoice(oid):
    po = db.get_or_404(PurchaseOrder, oid)
    if not po.invoice_no:
        raise BusinessError("Generate the invoice first", 409)
    return send_file(invoice_pdf("purchase", po), mimetype="application/pdf", download_name=f"{po.invoice_no}.pdf")


# ---- purchase requests ----
@bp.get("/requests")
@permission_required("purchases.view")
def list_requests():
    q = PurchaseRequest.query
    if request.args.get("status"):
        q = q.filter_by(status=request.args["status"])
    if (request.args.get("q") or "").strip():
        q = q.filter(PurchaseRequest.request_number.ilike(f"%{request.args['q'].strip()}%"))
    return paginate(q.order_by(PurchaseRequest.id.desc()))


@bp.post("/requests")
@permission_required("purchases.create")
def create_request():
    r = svc.create_request(load(PurchaseRequestSchema), current_user())
    audit("purchase_request.create", "purchase_request", r.id)
    db.session.commit()
    return ok(r.detail(), "Purchase request submitted for approval", 201)


@bp.get("/requests/<int:rid>")
@permission_required("purchases.view")
def get_request(rid):
    return ok(db.get_or_404(PurchaseRequest, rid).detail())


@bp.post("/requests/<int:rid>/approve")
@permission_required("purchases.approve")
def approve_request(rid):
    r = db.get_or_404(PurchaseRequest, rid)
    svc.review_request(r, current_user(), True)
    audit("purchase_request.approve", "purchase_request", rid)
    db.session.commit()
    return ok(r.detail(), "Request approved")


@bp.post("/requests/<int:rid>/reject")
@permission_required("purchases.approve")
def reject_request(rid):
    r = db.get_or_404(PurchaseRequest, rid)
    svc.review_request(r, current_user(), False, load(ReasonSchema).get("reason"))
    audit("purchase_request.reject", "purchase_request", rid)
    db.session.commit()
    return ok(r.detail(), "Request rejected")


@bp.post("/requests/<int:rid>/cancel")
@permission_required("purchases.create", "purchases.approve")
def cancel_request(rid):
    r = db.get_or_404(PurchaseRequest, rid)
    svc.cancel_request(r)
    audit("purchase_request.cancel", "purchase_request", rid)
    db.session.commit()
    return ok(r.detail(), "Request cancelled")


@bp.post("/requests/<int:rid>/convert")
@permission_required("purchases.create")
def convert_request(rid):
    r = db.get_or_404(PurchaseRequest, rid)
    po = svc.convert_request(r, load(ConvertSchema), current_user())
    audit("purchase_request.convert", "purchase_request", rid, {"po": po.po_number})
    db.session.commit()
    return ok({"request": r.detail(), "purchase_order": po.detail()}, f"Purchase order {po.po_number} generated", 201)
