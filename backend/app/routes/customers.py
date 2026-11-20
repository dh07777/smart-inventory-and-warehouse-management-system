from flask import Blueprint
from sqlalchemy import func
from ..extensions import db
from ..models import Customer, SalesOrder
from ..schemas import CustomerSchema
from ..utils import ok, paginate, permission_required
from .crud import register_crud

bp = Blueprint("customers", __name__, url_prefix="/api/customers")
register_crud(bp, Customer, CustomerSchema, view="customers.view", manage="customers.manage", entity="customer",
              search=("name", "code", "email", "phone", "company"), filters=("is_active", "city"), sorts=("id", "name", "code", "created_at"), default_sort="name")


@bp.get("/<int:cid>/profile")
@permission_required("customers.view")
def profile(cid):
    c = db.get_or_404(Customer, cid)
    valid = SalesOrder.query.filter(SalesOrder.customer_id == cid, SalesOrder.status.in_(["dispatched", "delivered", "returned"]))
    total = db.session.query(func.coalesce(func.sum(SalesOrder.total - SalesOrder.refunded_amount), 0)).filter(
        SalesOrder.customer_id == cid, SalesOrder.status.in_(["dispatched", "delivered", "returned"])).scalar()
    n = valid.count()
    last = valid.order_by(SalesOrder.order_date.desc()).first()
    return ok({**c.to_dict(), "stats": {"orders": SalesOrder.query.filter_by(customer_id=cid).count(), "fulfilled_orders": n,
                                        "total_spent": round(total, 2), "average_order": round(total / n, 2) if n else 0,
                                        "last_order": last.order_date.isoformat() if last else None}})


@bp.get("/<int:cid>/orders")
@permission_required("customers.view")
def orders(cid):
    return paginate(SalesOrder.query.filter_by(customer_id=cid).order_by(SalesOrder.order_date.desc()))
