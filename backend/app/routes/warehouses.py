from flask import Blueprint
from sqlalchemy import func
from ..extensions import db
from ..models import Warehouse, WarehouseLocation, Inventory, Batch, Product
from ..schemas import WarehouseSchema, LocationSchema
from ..utils import ok, load, paginate, audit, permission_required, request
from ..services import inventory_service as inv
from .crud import register_crud

bp = Blueprint("warehouses", __name__, url_prefix="/api/warehouses")
register_crud(bp, Warehouse, WarehouseSchema, view="warehouses.view", manage="warehouses.manage", entity="warehouse",
              search=("name", "code", "city"), filters=("is_active",), sorts=("id", "name", "code", "capacity"), default_sort="name")


def _util(w):
    units = int(db.session.query(func.coalesce(func.sum(Inventory.quantity), 0)).filter(Inventory.warehouse_id == w.id).scalar())
    return {"warehouse_id": w.id, "code": w.code, "name": w.name, "capacity": w.capacity, "units": units, "value": inv.valuation(w.id),
            "utilization": round(units * 100 / w.capacity, 1) if w.capacity else 0}


@bp.get("/utilization")
@permission_required("warehouses.view")
def utilization():
    return ok([_util(w) for w in Warehouse.query.filter_by(is_active=True).order_by(Warehouse.name)])


@bp.get("/<int:wid>/stock")
@permission_required("warehouses.view")
def stock(wid):
    db.get_or_404(Warehouse, wid)
    q = (db.session.query(Product, func.sum(Inventory.quantity), func.sum(Inventory.quantity * Batch.unit_cost))
         .join(Inventory, Inventory.product_id == Product.id).join(Batch, Batch.id == Inventory.batch_id)
         .filter(Inventory.warehouse_id == wid).group_by(Product.id).having(func.sum(Inventory.quantity) != 0).order_by(Product.name))
    s = request.args.get("q", "").strip()
    if s:
        q = q.filter(Product.name.ilike(f"%{s}%") | Product.sku.ilike(f"%{s}%"))
    return paginate(q, lambda r: {"product_id": r[0].id, "sku": r[0].sku, "name": r[0].name, "unit": r[0].unit, "quantity": int(r[1]), "value": round(r[2], 2)})


@bp.get("/<int:wid>/summary")
@permission_required("warehouses.view")
def summary(wid):
    w = db.get_or_404(Warehouse, wid)
    return ok({**w.to_dict(), **_util(w), "locations": [l.to_dict() for l in WarehouseLocation.query.filter_by(warehouse_id=wid)]})


@bp.get("/<int:wid>/locations")
@permission_required("warehouses.view")
def locations(wid):
    return ok([l.to_dict() for l in WarehouseLocation.query.filter_by(warehouse_id=wid).order_by(WarehouseLocation.zone, WarehouseLocation.rack)])


@bp.post("/<int:wid>/locations")
@permission_required("warehouses.manage")
def add_location(wid):
    db.get_or_404(Warehouse, wid)
    loc = WarehouseLocation(warehouse_id=wid, **{k: v for k, v in load(LocationSchema).items() if v is not None})
    db.session.add(loc)
    audit("warehouse.location_add", "warehouse", wid)
    db.session.commit()
    return ok(loc.to_dict(), "Location added", 201)


@bp.delete("/locations/<int:lid>")
@permission_required("warehouses.manage")
def delete_location(lid):
    db.session.delete(db.get_or_404(WarehouseLocation, lid))
    db.session.commit()
    return ok(None, "Location removed")
