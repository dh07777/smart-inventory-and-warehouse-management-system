import hashlib, hmac, json, secrets, smtplib
from datetime import timedelta
from email.message import EmailMessage
from flask import Blueprint, current_app, request
from flask_jwt_extended import (create_access_token, create_refresh_token, jwt_required, get_jwt, get_jwt_identity, decode_token)
from ..extensions import db, limiter
from ..models import User, Role, LoginHistory, TokenBlocklist
from ..schemas import (RegisterSchema, LoginSchema, ForgotSchema, ResetSchema, ChangePasswordSchema, ProfileSchema, PrefsSchema)
from ..utils import ok, load, BusinessError, audit, now, permission_required, paginate, current_user
from ..services.inventory_service import setting_bool

bp = Blueprint("auth", __name__, url_prefix="/api/auth")
DEMO_ACCOUNTS = [("admin@stockpilot.demo", "Super Admin"), ("warehouse@stockpilot.demo", "Warehouse Manager"),
                 ("inventory@stockpilot.demo", "Inventory Manager"), ("purchase@stockpilot.demo", "Purchase Manager"),
                 ("sales@stockpilot.demo", "Sales Manager"), ("staff@stockpilot.demo", "Staff")]


def user_payload(u):
    d = u.to_dict()
    d["permissions"] = sorted(u.role.codes())
    d["notification_prefs"] = u.prefs()
    return d


def send_mail(to, subject, body):
    cfg = current_app.config
    if not cfg.get("MAIL_SERVER"):
        current_app.logger.warning("MAIL_SERVER not configured. Message for %s: %s", to, body)
        return False
    try:
        m = EmailMessage()
        m["From"], m["To"], m["Subject"] = cfg["MAIL_FROM"], to, subject
        m.set_content(body)
        with smtplib.SMTP(cfg["MAIL_SERVER"], cfg["MAIL_PORT"], timeout=10) as s:
            s.starttls()
            if cfg.get("MAIL_USERNAME"):
                s.login(cfg["MAIL_USERNAME"], cfg["MAIL_PASSWORD"])
            s.send_message(m)
        return True
    except Exception as exc:  # pragma: no cover
        current_app.logger.error("Mail failed: %s", exc)
        return False


@bp.post("/register")
@limiter.limit("10 per hour")
def register():
    if not setting_bool("allow_registration", True):
        raise BusinessError("Self-registration is disabled", 403)
    data = load(RegisterSchema)
    email = data["email"].lower()
    if User.query.filter_by(email=email).first():
        raise BusinessError("An account with this email already exists", 409)
    u = User(name=data["name"], email=email, role_id=Role.query.filter_by(name="Staff").one().id)
    u.set_password(data["password"])
    db.session.add(u)
    db.session.flush()
    audit("auth.register", "user", u.id, user_id=u.id)
    db.session.commit()
    return ok(user_payload(u), "Account created. You can now sign in.", 201)


@bp.post("/login")
@limiter.limit("20 per minute")
def login():
    data = load(LoginSchema)
    email = data["email"].lower()
    since = now() - timedelta(minutes=15)
    fails = LoginHistory.query.filter(LoginHistory.email == email, LoginHistory.success.is_(False), LoginHistory.created_at >= since).count()
    if fails >= 5:
        raise BusinessError("Too many failed attempts. Try again in 15 minutes.", 429, code="locked")
    u = User.query.filter_by(email=email).first()
    good = bool(u and u.check_password(data["password"]))
    db.session.add(LoginHistory(user_id=u.id if u else None, email=email, success=good and u.is_active, ip_address=request.remote_addr,
                                user_agent=(request.user_agent.string or "")[:250]))
    if not good:
        db.session.commit()
        raise BusinessError("Invalid email or password", 401, code="invalid_credentials")
    if not u.is_active:
        db.session.commit()
        raise BusinessError("This account has been deactivated. Contact an administrator.", 403)
    u.last_login = now()
    audit("auth.login", "user", u.id, user_id=u.id)
    db.session.commit()
    return ok({"access_token": create_access_token(identity=str(u.id)), "refresh_token": create_refresh_token(identity=str(u.id)),
               "user": user_payload(u)}, "Signed in")


@bp.post("/refresh")
@jwt_required(refresh=True)
def refresh():
    u = db.session.get(User, int(get_jwt_identity()))
    if not u or not u.is_active:
        raise BusinessError("Account inactive", 403)
    return ok({"access_token": create_access_token(identity=str(u.id))})


@bp.post("/logout")
@jwt_required()
def logout():
    db.session.add(TokenBlocklist(jti=get_jwt()["jti"]))
    refresh_token = (request.get_json(silent=True) or {}).get("refresh_token")
    if refresh_token:
        try:
            db.session.add(TokenBlocklist(jti=decode_token(refresh_token)["jti"]))
        except Exception:
            pass
    db.session.commit()
    return ok(None, "Signed out")


@bp.post("/forgot-password")
@limiter.limit("5 per hour")
def forgot():
    data = load(ForgotSchema)
    u = User.query.filter_by(email=data["email"].lower()).first()
    resp = {"message": "If that email exists, a reset link has been sent."}
    if u and u.is_active:
        token = secrets.token_urlsafe(32)
        u.reset_token_hash = hashlib.sha256(token.encode()).hexdigest()
        u.reset_expires = now() + timedelta(minutes=30)
        db.session.commit()
        link = f"{current_app.config['FRONTEND_URL']}/reset-password?token={token}&email={u.email}"
        sent = send_mail(u.email, "StockPilot password reset", f"Use this link within 30 minutes:\n{link}")
        if not sent and (current_app.debug or current_app.testing):
            resp["dev_reset_link"] = link  # only exposed in development when no SMTP server is configured
    return ok(resp, resp["message"])


@bp.post("/reset-password")
@limiter.limit("10 per hour")
def reset():
    data = load(ResetSchema)
    u = User.query.filter_by(email=data["email"].lower()).first()
    bad = BusinessError("Reset link is invalid or has expired", 400)
    if not u or not u.reset_token_hash or not u.reset_expires or u.reset_expires < now():
        raise bad
    if not hmac.compare_digest(u.reset_token_hash, hashlib.sha256(data["token"].encode()).hexdigest()):
        raise bad
    u.set_password(data["password"])
    u.reset_token_hash = u.reset_expires = None
    audit("auth.password_reset", "user", u.id, user_id=u.id)
    db.session.commit()
    return ok(None, "Password updated. You can now sign in.")


@bp.get("/demo-accounts")
def demo_accounts():
    if not setting_bool("demo_data", False):
        return ok([])
    return ok([{"email": e, "role": r} for e, r in DEMO_ACCOUNTS], meta={"password": "Demo@12345"})


@bp.get("/me")
@permission_required()
def me():
    return ok(user_payload(current_user()))


@bp.put("/me")
@permission_required()
def update_me():
    u = current_user()
    for k, v in load(ProfileSchema, partial=True).items():
        setattr(u, k, v)
    audit("auth.profile_update", "user", u.id)
    db.session.commit()
    return ok(user_payload(u), "Profile updated")


@bp.put("/me/preferences")
@permission_required()
def prefs():
    u = current_user()
    u.notification_prefs = json.dumps({**u.prefs(), **load(PrefsSchema, partial=True)})
    db.session.commit()
    return ok(user_payload(u), "Preferences saved")


@bp.post("/change-password")
@permission_required()
def change_password():
    u = current_user()
    data = load(ChangePasswordSchema)
    if not u.check_password(data["current_password"]):
        raise BusinessError("Current password is incorrect", 400)
    u.set_password(data["new_password"])
    audit("auth.password_change", "user", u.id)
    db.session.commit()
    return ok(None, "Password changed")


@bp.get("/me/login-history")
@permission_required()
def my_history():
    return paginate(LoginHistory.query.filter_by(user_id=current_user().id).order_by(LoginHistory.id.desc()))
