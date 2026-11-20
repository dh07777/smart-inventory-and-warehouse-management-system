"""Generic list/get/create/update/delete route factory used by simple master-data modules."""
from flask import request
from sqlalchemy import or_
from ..extensions import db
from ..utils import ok, load, paginate, apply_sort, audit, permission_required, BusinessError


def _coerce(v):
    if v in ("true", "false"):
        return v == "true"
    return int(v) if v.isdigit() else v


def register_crud(bp, Model, Schema, *, view, manage, entity, search=(), filters=(), sorts=("id",), default_sort="id", before_save=None):
    @bp.get("")
    @permission_required(view)
    def list_():
        q = Model.query
        s = request.args.get("q", "").strip()
        if s and search:
            q = q.filter(or_(*[getattr(Model, f).ilike(f"%{s}%") for f in search]))
        for f in filters:
            v = request.args.get(f)
            if v not in (None, ""):
                q = q.filter(getattr(Model, f) == _coerce(v))
        return paginate(apply_sort(q, Model, sorts, default_sort))

    @bp.get("/<int:oid>")
    @permission_required(view)
    def get_(oid):
        return ok(db.get_or_404(Model, oid).to_dict())

    @bp.post("")
    @permission_required(manage)
    def create_():
        data = {k: v for k, v in load(Schema).items() if v is not None}
        obj = Model(**data)
        if before_save:
            before_save(obj, data, True)
        db.session.add(obj)
        db.session.flush()
        audit(f"{entity}.create", entity, obj.id, data)
        db.session.commit()
        return ok(obj.to_dict(), f"{entity.title()} created", 201)

    @bp.put("/<int:oid>")
    @permission_required(manage)
    def update_(oid):
        obj = db.get_or_404(Model, oid)
        data = load(Schema, partial=True)
        for k, v in data.items():
            if v is None and not Model.__table__.c[k].nullable:
                continue
            setattr(obj, k, v)
        if before_save:
            before_save(obj, data, False)
        audit(f"{entity}.update", entity, obj.id, data)
        db.session.commit()
        return ok(obj.to_dict(), f"{entity.title()} updated")

    @bp.delete("/<int:oid>")
    @permission_required(manage)
    def delete_(oid):
        obj = db.get_or_404(Model, oid)
        db.session.delete(obj)
        audit(f"{entity}.delete", entity, oid)
        db.session.commit()
        return ok(None, f"{entity.title()} deleted")
