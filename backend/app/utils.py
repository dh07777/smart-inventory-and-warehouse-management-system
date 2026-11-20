"""Shared helpers: responses, errors, auth decorators, pagination, validation, audit."""
import json
from datetime import datetime, timezone, date
from functools import wraps

from flask import jsonify, request, g
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
from marshmallow import Schema, EXCLUDE, ValidationError, pre_load

from .extensions import db


class BusinessError(Exception):
    def __init__(self, message, status=400, details=None, code="business_error"):
        super().__init__(message)
        self.message, self.status, self.details, self.code = message, status, details, code


def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def ok(data=None, message=None, status=200, meta=None):
    body = {"success": True, "data": data}
    if message:
        body["message"] = message
    if meta is not None:
        body["meta"] = meta
    return jsonify(body), status


def error_response(message, status=400, code="error", details=None):
    return jsonify({"success": False, "error": {"code": code, "message": message, "details": details}}), status


class BaseSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    @pre_load
    def _blank_to_none(self, data, **kw):
        return {k: (None if isinstance(v, str) and v.strip() == "" else (v.strip() if isinstance(v, str) else v))
                for k, v in (data or {}).items()}


def load(schema_cls, partial=False, data=None):
    payload = request.get_json(silent=True) if data is None else data
    if not isinstance(payload, dict):
        raise BusinessError("A JSON object body is required", 400)
    try:
        return schema_cls().load(payload, partial=partial)
    except ValidationError as e:
        raise BusinessError("Validation failed", 422, e.messages, "validation_error")


def parse_date(value, name="date"):
    if not value:
        return None
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except ValueError:
        raise BusinessError(f"Invalid {name}; use YYYY-MM-DD", 422)


def current_user():
    from .models import User
    if "user" not in g:
        uid = get_jwt_identity()
        g.user = db.session.get(User, int(uid)) if uid else None
    return g.user


def permission_required(*codes):
    """Server-side RBAC: user must hold at least one of the given permission codes."""
    def deco(fn):
        @wraps(fn)
        def wrapper(*a, **kw):
            verify_jwt_in_request()
            u = current_user()
            if not u or not u.is_active:
                raise BusinessError("Account is inactive or missing", 403, code="forbidden")
            if codes and not any(u.has_permission(c) for c in codes):
                raise BusinessError("You do not have permission to perform this action", 403, code="forbidden")
            return fn(*a, **kw)
        wrapper.required_permissions = codes
        return wrapper
    return deco


def login_required_any(fn):
    return permission_required()(fn)


def paginate(query, serialize=None):
    page = max(request.args.get("page", 1, type=int), 1)
    per = min(max(request.args.get("per_page", 10, type=int), 1), 200)
    p = query.paginate(page=page, per_page=per, error_out=False)
    ser = serialize or (lambda o: o.to_dict())
    return ok([ser(i) for i in p.items], meta={"page": p.page, "per_page": per, "total": p.total, "pages": p.pages})


def apply_sort(query, model, allowed, default="id"):
    col = request.args.get("sort", default)
    if col not in allowed:
        col = default
    column = getattr(model, col)
    return query.order_by(column.desc() if request.args.get("order", "desc" if default == "id" else "asc") == "desc" else column.asc())


def audit(action, entity, entity_id=None, details=None, user_id=None):
    from .models import AuditLog
    uid = user_id
    if uid is None:
        try:
            u = current_user()
            uid = u.id if u else None
        except Exception:
            uid = None
    db.session.add(AuditLog(user_id=uid, action=action, entity=entity, entity_id=str(entity_id) if entity_id is not None else None,
                            details=json.dumps(details, default=str) if details is not None else None,
                            ip_address=request.remote_addr if request else None))


def next_number(prefix, model):
    last = db.session.query(db.func.max(model.id)).scalar() or 0
    return f"{prefix}-{now():%y%m}-{last + 1:05d}"
