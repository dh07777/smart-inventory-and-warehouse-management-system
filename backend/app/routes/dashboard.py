from datetime import timedelta
from flask import Blueprint
from sqlalchemy import func
from ..extensions import db
from ..models import (Product, Warehouse, Inventory, PurchaseOrder, SalesOrder, SalesOrderItem, StockMovement, Setting, Batch)
from ..utils import ok, permission_required, now
from ..services import inventory_service as inv
from ..services.notification_service import scan_alerts, get_setting

bp = Blueprint("dashboard", __name__, url_prefix="/api/dashboard")


def _months(n=6):
    y, m, out = now().year, now().month, []
    for _ in range(n):
        out.append(f"{y:04d}-{m:02d}")
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return out[::-1]


@bp.get("")
@permission_required("dashboard.view")
def dashboard():
    last = get_setting("last_alert_scan")
    if not last or (now() - __import__("datetime").datetime.fromisoformat(last)) > timedelta(hours=1):
        scan_alerts()
        s = db.session.get(Setting, "last_alert_scan") or Setting(key="last_alert_scan")
        s.value = now().isoformat()
        db.session.add(s)
        db.session.commit()
    low, out = inv.low_and_out_products()
    months = _months()
    pm = func.strftime("%Y-%m", PurchaseOrder.order_date)
    purchases = dict(db.session.query(pm, func.sum(PurchaseOrder.total)).filter(PurchaseOrder.status.notin_(["rejected", "cancelled", "pending_approval"])).group_by(pm).all())
    sm = func.strftime("%Y-%m", SalesOrder.order_date)
    sales = dict(db.session.query(sm, func.sum(SalesOrder.total)).filter(SalesOrder.status.in_(["dispatched", "delivered", "returned"])).group_by(sm).all())
    mm = func.strftime("%Y-%m", StockMovement.created_at)
    net = dict(db.session.query(mm, func.sum(StockMovement.quantity)).group_by(mm).all())
    running = sum(v for k, v in net.items() if k < months[0]) or 0
    trend = []
    for m in months:
        running += net.get(m, 0) or 0
        trend.append({"month": m, "quantity": int(running)})
    since = now() - timedelta(days=30)
    wh_perf = []
    for w in Warehouse.query.filter_by(is_active=True):
        units = int(db.session.query(func.coalesce(func.sum(Inventory.quantity), 0)).filter(Inventory.warehouse_id == w.id).scalar())
        moves = StockMovement.query.filter(StockMovement.warehouse_id == w.id, StockMovement.created_at >= since).count()
        wh_perf.append({"warehouse": w.name, "units": units, "capacity": w.capacity, "utilization": round(units * 100 / w.capacity, 1) if w.capacity else 0,
                        "movements_30d": moves})
    top = (db.session.query(Product.name, func.sum(SalesOrderItem.quantity)).join(SalesOrderItem, SalesOrderItem.product_id == Product.id)
           .join(SalesOrder, SalesOrder.id == SalesOrderItem.sales_order_id).filter(SalesOrder.status.in_(["dispatched", "delivered", "returned"]))
           .group_by(Product.id).order_by(func.sum(SalesOrderItem.quantity).desc()).limit(5).all())
    expiring = (db.session.query(func.count(func.distinct(Batch.id))).join(Inventory, Inventory.batch_id == Batch.id)
                .filter(Batch.expiry_date.isnot(None), Batch.expiry_date <= now().date() + timedelta(days=int(get_setting("expiry_alert_days", "30"))),
                        Inventory.quantity > 0).scalar())
    return ok({
        "totals": {"products": Product.query.filter_by(status="active").count(), "warehouses": Warehouse.query.filter_by(is_active=True).count(),
                   "inventory_quantity": int(db.session.query(func.coalesce(func.sum(Inventory.quantity), 0)).scalar()),
                   "inventory_value": inv.valuation(), "low_stock": len(low), "out_of_stock": len(out), "expiring_batches": expiring,
                   "pending_purchase_orders": PurchaseOrder.query.filter(PurchaseOrder.status.in_(["pending_approval", "approved", "partially_received"])).count(),
                   "pending_sales_orders": SalesOrder.query.filter(SalesOrder.status.in_(["pending", "confirmed"])).count()},
        "monthly": [{"month": m, "purchases": round(purchases.get(m, 0) or 0, 2), "sales": round(sales.get(m, 0) or 0, 2)} for m in months],
        "inventory_trend": trend, "warehouse_performance": wh_perf, "top_products": [{"name": n, "units": int(u)} for n, u in top],
        "recent_movements": [m.to_dict() for m in StockMovement.query.order_by(StockMovement.id.desc()).limit(8)],
        "alerts": {"low": [{"id": p.id, "name": p.name, "on_hand": q, "min_stock": p.min_stock} for p, q in low[:5]],
                   "out": [{"id": p.id, "name": p.name} for p, q in out[:5]]}})
