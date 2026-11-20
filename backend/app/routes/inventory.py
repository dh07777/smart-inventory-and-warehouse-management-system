from datetime import timedelta
from flask import Blueprint, request
from sqlalchemy import func
from ..extensions import db
from ..models import Inventory, Batch, Product, Warehouse, StockMovement, Reservation
from ..schemas import StockOpSchema, AdjustSchema, WriteOffSchema, ReserveSchema, ReconcileSchema
from ..utils import ok, load, paginate, audit, permission_required, current_user, BusinessError, now, parse_date
from ..services import inventory_service as inv
from ..repositories import inventory_repository as repo
from ..services.notification_service import get_setting, scan_alerts

bp = Blueprint("inventory", __name__, url_prefix="/api/inventory")


def _override_ok(flag):
    if not flag:
        return False
    if not current_user().has_permission("inventory.override") or not inv.setting_bool("allow_negative_override", False):
        raise BusinessError("Negative-stock override is not enabled or you are not authorised to use it", 403)
    return True


@bp.get("/stock")
@permission_required("inventory.view")
def stock():
    res = repo.reserved_by_location()
    return paginate(repo.stock_rows(request.args), lambda r: {
        "product_id": r[0].id, "sku": r[0].sku, "name": r[0].name, "unit": r[0].unit, "warehouse_id": r[1].id, "warehouse_name": r[1].name,
        "on_hand": int(r[2]), "reserved": res.get((r[0].id, r[1].id), 0), "available": int(r[2]) - res.get((r[0].id, r[1].id), 0),
        "min_stock": r[0].min_stock, "value": round(r[3], 2)})


@bp.get("/batches")
@permission_required("inventory.view")
def batches():
    return paginate(repo.batch_rows(request.args, now().date()))


@bp.get("/movements")
@permission_required("inventory.view")
def movements():
    return paginate(repo.movement_rows(request.args, parse_date(request.args.get("date_from")), parse_date(request.args.get("date_to"))))


@bp.post("/stock-in")
@permission_required("inventory.manage")
def stock_in():
    d = load(StockOpSchema)
    p = db.get_or_404(Product, d["product_id"])
    db.get_or_404(Warehouse, d["warehouse_id"])
    b = inv.stock_in(p.id, d["warehouse_id"], d["quantity"], d["unit_cost"] if d.get("unit_cost") is not None else p.purchase_price,
                     batch_no=d.get("batch_no"), expiry_date=d.get("expiry_date"), mfg_date=d.get("mfg_date"), ref_type="manual",
                     note=d.get("reason") or "Manual stock-in", user_id=current_user().id)
    audit("inventory.stock_in", "product", p.id, d)
    db.session.commit()
    return ok({"batch_id": b.id, "on_hand": inv.on_hand(p.id, d["warehouse_id"]), "warnings": inv.stock_warnings(p.id, d["warehouse_id"])}, "Stock added", 201)


@bp.post("/stock-out")
@permission_required("inventory.manage")
def stock_out():
    d = load(StockOpSchema)
    override = _override_ok(d.get("override"))
    cogs, _ = inv.stock_out(d["product_id"], d["warehouse_id"], d["quantity"], ref_type="manual", note=d.get("reason") or "Manual stock-out",
                            user_id=current_user().id, override=override)
    audit("inventory.stock_out", "product", d["product_id"], d)
    db.session.commit()
    return ok({"cogs": cogs, "on_hand": inv.on_hand(d["product_id"], d["warehouse_id"])}, "Stock removed")


@bp.post("/adjust")
@permission_required("inventory.manage")
def adjust():
    d = load(AdjustSchema)
    if d.get("delta") is None and d.get("new_quantity") is None:
        raise BusinessError("Provide either delta or new_quantity", 422)
    override = _override_ok(d.get("override"))
    change = inv.adjust(d["product_id"], d["warehouse_id"], delta=d.get("delta"), new_quantity=d.get("new_quantity"), reason=d["reason"],
                        user_id=current_user().id, override=override)
    audit("inventory.adjust", "product", d["product_id"], {**d, "applied": change})
    db.session.commit()
    return ok({"change": change, "on_hand": inv.on_hand(d["product_id"], d["warehouse_id"])}, "Stock adjusted")


@bp.post("/write-off")
@permission_required("inventory.manage")
def write_off():
    d = load(WriteOffSchema)
    inv.stock_out(d["product_id"], d["warehouse_id"], d["quantity"], movement_type=d["reason"].upper(), ref_type="write_off", batch_id=d["batch_id"],
                  note=d.get("note") or f"Written off as {d['reason']}", user_id=current_user().id)
    audit("inventory.write_off", "product", d["product_id"], d)
    db.session.commit()
    return ok(None, f"Stock written off as {d['reason']}")


@bp.post("/reconcile")
@permission_required("inventory.manage")
def reconcile():
    d = load(ReconcileSchema)
    results = []
    for c in d["counts"]:
        before = inv.on_hand(c["product_id"], d["warehouse_id"])
        diff = inv.adjust(c["product_id"], d["warehouse_id"], new_quantity=c["counted"], reason=d.get("note") or "Stock reconciliation",
                          user_id=current_user().id, movement_type="RECONCILE", ref_type="reconciliation")
        results.append({"product_id": c["product_id"], "system": before, "counted": c["counted"], "difference": diff})
    audit("inventory.reconcile", "warehouse", d["warehouse_id"], results)
    db.session.commit()
    return ok(results, "Reconciliation complete")


@bp.get("/reservations")
@permission_required("inventory.view")
def reservations():
    q = Reservation.query
    if request.args.get("status"):
        q = q.filter_by(status=request.args["status"])
    return paginate(q.order_by(Reservation.id.desc()))


@bp.post("/reservations")
@permission_required("inventory.manage")
def reserve():
    d = load(ReserveSchema)
    r = inv.reserve(d["product_id"], d["warehouse_id"], d["quantity"], "manual", None, current_user().id, d.get("note"))
    audit("inventory.reserve", "product", d["product_id"], d)
    db.session.commit()
    return ok(r.to_dict(), "Stock reserved", 201)


@bp.post("/reservations/<int:rid>/release")
@permission_required("inventory.manage")
def release(rid):
    r = db.get_or_404(Reservation, rid)
    if r.status != "active":
        raise BusinessError("Reservation is not active", 409)
    r.status = "released"
    db.session.commit()
    return ok(r.to_dict(), "Reservation released")


@bp.get("/reorder")
@permission_required("inventory.view")
def reorder():
    return ok(inv.reorder_recommendations())


@bp.get("/valuation")
@permission_required("inventory.view")
def valuation():
    return ok({"total": inv.valuation(), "by_warehouse": [{"warehouse": w.name, "value": inv.valuation(w.id)} for w in Warehouse.query.all()]})


@bp.get("/alerts")
@permission_required("inventory.view")
def alerts():
    low, out = inv.low_and_out_products()
    days = int(get_setting("expiry_alert_days", "30"))
    exp = repo.expiring_batches(now().date() + timedelta(days=days))
    return ok({"low_stock": [{"product_id": p.id, "sku": p.sku, "name": p.name, "on_hand": q, "min_stock": p.min_stock} for p, q in low],
               "out_of_stock": [{"product_id": p.id, "sku": p.sku, "name": p.name} for p, q in out],
               "expiring": [{"batch_id": b.id, "batch_no": b.batch_no, "product_id": b.product_id, "expiry_date": b.expiry_date.isoformat(),
                             "quantity": int(q), "expired": b.expiry_date < now().date()} for b, q in exp]})
