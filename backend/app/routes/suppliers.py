from flask import Blueprint, request
from sqlalchemy import func
from ..extensions import db
from ..models import Supplier, SupplierProduct, SupplierPayment, PurchaseOrder
from ..schemas import SupplierSchema, SupplierProductSchema, PaymentSchema
from ..utils import ok, load, paginate, audit, permission_required, current_user, BusinessError
from .crud import register_crud

bp = Blueprint("suppliers", __name__, url_prefix="/api/suppliers")
register_crud(bp, Supplier, SupplierSchema, view="suppliers.view", manage="suppliers.manage", entity="supplier",
              search=("name", "code", "contact_person", "email"), filters=("is_active",), sorts=("id", "name", "code", "rating"), default_sort="name")


def _stats(s):
    pos = PurchaseOrder.query.filter(PurchaseOrder.supplier_id == s.id, PurchaseOrder.status.notin_(["rejected", "cancelled"])).all()
    done = [p for p in pos if p.status == "received"]
    dated = [p for p in done if p.expected_date and p.received_at]
    ontime = [p for p in dated if p.received_at.date() <= p.expected_date]
    open_pos = [p for p in pos if p.status in ("approved", "partially_received", "received")]
    ordered = sum(i.quantity for p in open_pos for i in p.items)
    got = sum(i.received_qty for p in open_pos for i in p.items)
    total = round(sum(p.total for p in pos), 2)
    paid = round(db.session.query(func.coalesce(func.sum(SupplierPayment.amount), 0)).filter(SupplierPayment.supplier_id == s.id).scalar(), 2)
    return {"orders": len(pos), "total_purchased": total, "total_paid": paid, "outstanding": round(total - paid, 2),
            "on_time_pct": round(len(ontime) * 100 / len(dated), 1) if dated else None,
            "avg_delay_days": round(sum((p.received_at.date() - p.expected_date).days for p in dated) / len(dated), 1) if dated else None,
            "fill_rate_pct": round(got * 100 / ordered, 1) if ordered else None}


@bp.get("/<int:sid>/profile")
@permission_required("suppliers.view")
def profile(sid):
    s = db.get_or_404(Supplier, sid)
    return ok({**s.to_dict(), "stats": _stats(s)})


@bp.get("/<int:sid>/catalog")
@permission_required("suppliers.view")
def catalog(sid):
    return ok([c.to_dict() for c in SupplierProduct.query.filter_by(supplier_id=sid)])


@bp.post("/<int:sid>/catalog")
@permission_required("suppliers.manage")
def add_catalog(sid):
    db.get_or_404(Supplier, sid)
    d = load(SupplierProductSchema)
    row = SupplierProduct.query.filter_by(supplier_id=sid, product_id=d["product_id"]).first() or SupplierProduct(supplier_id=sid, product_id=d["product_id"])
    for k, v in d.items():
        if v is not None:
            setattr(row, k, v)
    db.session.add(row)
    audit("supplier.catalog", "supplier", sid, d)
    db.session.commit()
    return ok(row.to_dict(), "Catalog updated", 201)


@bp.delete("/catalog/<int:cid>")
@permission_required("suppliers.manage")
def del_catalog(cid):
    db.session.delete(db.get_or_404(SupplierProduct, cid))
    db.session.commit()
    return ok(None, "Removed from catalog")


@bp.get("/<int:sid>/purchases")
@permission_required("suppliers.view")
def purchases(sid):
    return paginate(PurchaseOrder.query.filter_by(supplier_id=sid).order_by(PurchaseOrder.order_date.desc()))


@bp.get("/<int:sid>/payments")
@permission_required("suppliers.view")
def payments(sid):
    return paginate(SupplierPayment.query.filter_by(supplier_id=sid).order_by(SupplierPayment.paid_at.desc()))


@bp.post("/<int:sid>/payments")
@permission_required("suppliers.manage")
def add_payment(sid):
    s = db.get_or_404(Supplier, sid)
    d = load(PaymentSchema)
    st = _stats(s)
    if d["amount"] > st["outstanding"] + 0.005:
        raise BusinessError(f"Payment exceeds outstanding balance ({st['outstanding']})", 409)
    pay = SupplierPayment(supplier_id=sid, created_by=current_user().id, **{k: v for k, v in d.items() if v is not None})
    db.session.add(pay)
    audit("supplier.payment", "supplier", sid, d)
    db.session.commit()
    return ok(pay.to_dict(), "Payment recorded", 201)
