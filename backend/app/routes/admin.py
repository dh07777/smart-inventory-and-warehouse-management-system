import os, re, shutil, sqlite3
from flask import Blueprint, request, current_app, send_from_directory
from ..extensions import db
from ..models import User, Role, Permission, AuditLog, LoginHistory, Setting
from ..permissions import PERMISSIONS
from ..schemas import UserCreateSchema, UserUpdateSchema, RolePermsSchema
from ..utils import ok, load, paginate, audit, permission_required, current_user, BusinessError, now, parse_date
from datetime import timedelta
from sqlalchemy import or_

bp = Blueprint("admin", __name__, url_prefix="/api")
DEFAULT_SETTINGS = {"company_name": "StockPilot Demo Co.", "company_address": "", "company_email": "", "company_phone": "", "currency_code": "USD",
                    "currency_symbol": "$", "default_tax_rate": "0", "allow_negative_override": "false", "expiry_alert_days": "30",
                    "allow_registration": "true", "demo_data": "false", "default_min_stock": "0", "default_warehouse_id": ""}
READONLY = {"demo_data", "last_alert_scan"}


def _settings():
    out = dict(DEFAULT_SETTINGS)
    out.update({s.key: s.value for s in Setting.query.all() if s.key in DEFAULT_SETTINGS})
    return out


@bp.get("/settings/public")
@permission_required()
def public_settings():
    s = _settings()
    return ok({k: s[k] for k in ("company_name", "currency_code", "currency_symbol", "default_tax_rate", "demo_data", "expiry_alert_days", "default_warehouse_id", "default_min_stock")})


@bp.get("/admin/settings")
@permission_required("settings.manage")
def get_settings():
    return ok(_settings())


@bp.put("/admin/settings")
@permission_required("settings.manage")
def put_settings():
    data = request.get_json(silent=True) or {}
    for k, v in data.items():
        if k not in DEFAULT_SETTINGS or k in READONLY:
            continue
        if k == "default_warehouse_id":
            from ..models import Warehouse
            if v not in ("", None) and not db.session.get(Warehouse, int(v)):
                raise BusinessError("Default warehouse not found", 422)
            v = "" if v in (None, "") else str(int(v))
        if k in ("default_tax_rate", "expiry_alert_days", "default_min_stock"):
            try:
                if float(v) < 0:
                    raise ValueError
            except (TypeError, ValueError):
                raise BusinessError(f"{k} must be a non-negative number", 422)
        row = db.session.get(Setting, k) or Setting(key=k)
        row.value = str(v).lower() if isinstance(v, bool) else str(v)
        db.session.add(row)
    audit("settings.update", "settings", None, {k: v for k, v in data.items() if k in DEFAULT_SETTINGS})
    db.session.commit()
    return ok(_settings(), "Settings saved")


@bp.get("/admin/users")
@permission_required("users.manage")
def list_users():
    q = User.query
    s = request.args.get("q", "").strip()
    if s:
        q = q.filter(or_(User.name.ilike(f"%{s}%"), User.email.ilike(f"%{s}%")))
    if request.args.get("role_id"):
        q = q.filter(User.role_id == request.args.get("role_id", type=int))
    if request.args.get("is_active") in ("true", "false"):
        q = q.filter(User.is_active.is_(request.args["is_active"] == "true"))
    return paginate(q.order_by(User.name))


@bp.get("/admin/users/options")
@permission_required("warehouses.manage", "users.manage")
def user_options():
    return ok([{"id": u.id, "name": u.name, "role": u.role.name} for u in User.query.filter_by(is_active=True).order_by(User.name)])


@bp.post("/admin/users")
@permission_required("users.manage")
def create_user():
    d = load(UserCreateSchema)
    if User.query.filter_by(email=d["email"].lower()).first():
        raise BusinessError("Email already in use", 409)
    if not db.session.get(Role, d["role_id"]):
        raise BusinessError("Role not found", 422)
    u = User(name=d["name"], email=d["email"].lower(), role_id=d["role_id"], phone=d.get("phone"), is_active=d.get("is_active", True))
    u.set_password(d["password"])
    db.session.add(u)
    db.session.flush()
    audit("user.create", "user", u.id, {"email": u.email, "role": u.role.name})
    db.session.commit()
    return ok(u.to_dict(), "User created", 201)


@bp.put("/admin/users/<int:uid>")
@permission_required("users.manage")
def update_user(uid):
    u = db.get_or_404(User, uid)
    d = load(UserUpdateSchema, partial=True)
    me = current_user()
    if u.id == me.id and (d.get("is_active") is False or ("role_id" in d and d["role_id"] != u.role_id)):
        raise BusinessError("You cannot deactivate or change the role of your own account", 409)
    if "role_id" in d and not db.session.get(Role, d["role_id"]):
        raise BusinessError("Role not found", 422)
    if u.role.name == "Super Admin" and (d.get("is_active") is False or ("role_id" in d and d["role_id"] != u.role_id)):
        if User.query.join(Role).filter(Role.name == "Super Admin", User.is_active.is_(True)).count() <= 1:
            raise BusinessError("At least one active Super Admin is required", 409)
    pw = d.pop("password", None)
    for k, v in d.items():
        if v is not None or k == "phone":
            setattr(u, k, v)
    if pw:
        u.set_password(pw)
    audit("user.update", "user", uid, {k: v for k, v in d.items()})
    db.session.commit()
    return ok(u.to_dict(), "User updated")


@bp.get("/admin/roles")
@permission_required("users.manage", "warehouses.manage")
def roles():
    return ok([r.to_dict() for r in Role.query.order_by(Role.id)])


@bp.get("/admin/permissions")
@permission_required("users.manage")
def permissions():
    return ok([{"code": c, "description": d} for c, d in PERMISSIONS.items()])


@bp.put("/admin/roles/<int:rid>/permissions")
@permission_required("users.manage")
def set_role_permissions(rid):
    role = db.get_or_404(Role, rid)
    if role.name == "Super Admin":
        raise BusinessError("Super Admin permissions cannot be changed", 409)
    codes = load(RolePermsSchema)["permissions"]
    perms = Permission.query.filter(Permission.code.in_(codes)).all()
    role.permissions = perms
    audit("role.permissions", "role", rid, codes)
    db.session.commit()
    return ok(role.to_dict(), "Role permissions updated")


@bp.get("/admin/audit-logs")
@permission_required("audit.view")
def audit_logs():
    q = AuditLog.query
    for f in ("user_id", "entity", "action"):
        if request.args.get(f):
            q = q.filter(getattr(AuditLog, f) == request.args[f])
    s = request.args.get("q", "").strip()
    if s:
        q = q.filter(or_(AuditLog.action.ilike(f"%{s}%"), AuditLog.details.ilike(f"%{s}%")))
    df, dt = parse_date(request.args.get("date_from")), parse_date(request.args.get("date_to"))
    if df:
        q = q.filter(AuditLog.created_at >= df)
    if dt:
        q = q.filter(AuditLog.created_at < dt + timedelta(days=1))
    return paginate(q.order_by(AuditLog.id.desc()))


@bp.get("/admin/login-history")
@permission_required("audit.view")
def login_history():
    q = LoginHistory.query
    if request.args.get("success") in ("true", "false"):
        q = q.filter(LoginHistory.success.is_(request.args["success"] == "true"))
    return paginate(q.order_by(LoginHistory.id.desc()))


# ---- Backup & restore (SQLite online backup API) ----
def _db_path():
    url = db.engine.url
    if url.get_backend_name() != "sqlite" or not url.database or url.database == ":memory:":
        raise BusinessError("Backup is only available for file-based SQLite databases", 400)
    return url.database


def _backup_dir():
    os.makedirs(current_app.config["BACKUP_FOLDER"], exist_ok=True)
    return current_app.config["BACKUP_FOLDER"]


def _safe(name):
    if not re.fullmatch(r"stockpilot-[\w-]+\.db", name or ""):
        raise BusinessError("Invalid backup name", 400)
    path = os.path.join(_backup_dir(), name)
    if not os.path.isfile(path):
        raise BusinessError("Backup not found", 404)
    return path


def _copy(src_path, dst_path):
    src, dst = sqlite3.connect(src_path), sqlite3.connect(dst_path)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()


def make_backup(prefix="stockpilot"):
    name = f"{prefix}-{now():%Y%m%d-%H%M%S}.db"
    _copy(_db_path(), os.path.join(_backup_dir(), name))
    return name


@bp.get("/admin/backups")
@permission_required("settings.manage")
def list_backups():
    files = []
    for f in sorted(os.listdir(_backup_dir()), reverse=True):
        if f.endswith(".db"):
            st = os.stat(os.path.join(_backup_dir(), f))
            files.append({"name": f, "size_kb": round(st.st_size / 1024, 1), "created_at": __import__("datetime").datetime.fromtimestamp(st.st_mtime).isoformat()})
    return ok(files)


@bp.post("/admin/backups")
@permission_required("settings.manage")
def create_backup():
    name = make_backup()
    audit("backup.create", "backup", name)
    db.session.commit()
    return ok({"name": name}, "Backup created", 201)


@bp.get("/admin/backups/<name>/download")
@permission_required("settings.manage")
def download_backup(name):
    _safe(name)
    return send_from_directory(_backup_dir(), name, as_attachment=True)


@bp.delete("/admin/backups/<name>")
@permission_required("settings.manage")
def delete_backup(name):
    os.remove(_safe(name))
    audit("backup.delete", "backup", name)
    db.session.commit()
    return ok(None, "Backup deleted")


@bp.post("/admin/backups/<name>/restore")
@permission_required("settings.manage")
def restore_backup(name):
    src = _safe(name)
    uid = current_user().id
    path = _db_path()
    make_backup("stockpilot-prerestore")  # safety copy of the current database
    db.session.remove()
    db.engine.dispose()
    _copy(src, path)
    try:
        audit("backup.restore", "backup", name, user_id=uid)
        db.session.commit()
    except Exception:  # the restored database may not contain this user; the restore itself already succeeded
        db.session.rollback()
    return ok(None, "Database restored. Please sign in again if your account no longer exists in the backup.")
