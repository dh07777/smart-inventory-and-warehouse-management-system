from flask import Blueprint, request
from ..extensions import db
from ..models import Notification
from ..utils import ok, paginate, permission_required, current_user, BusinessError
from ..services.notification_service import scan_alerts

bp = Blueprint("notifications", __name__, url_prefix="/api/notifications")


@bp.get("")
@permission_required()
def list_n():
    q = Notification.query.filter_by(user_id=current_user().id)
    if request.args.get("unread") == "true":
        q = q.filter_by(is_read=False)
    if request.args.get("type"):
        q = q.filter_by(type=request.args["type"])
    return paginate(q.order_by(Notification.id.desc()))


@bp.get("/unread-count")
@permission_required()
def unread():
    return ok({"count": Notification.query.filter_by(user_id=current_user().id, is_read=False).count()})


@bp.post("/<int:nid>/read")
@permission_required()
def read(nid):
    n = db.get_or_404(Notification, nid)
    if n.user_id != current_user().id:
        raise BusinessError("Not found", 404)
    n.is_read = True
    db.session.commit()
    return ok(n.to_dict())


@bp.post("/read-all")
@permission_required()
def read_all():
    Notification.query.filter_by(user_id=current_user().id, is_read=False).update({"is_read": True})
    db.session.commit()
    return ok(None, "All notifications marked as read")


@bp.delete("/<int:nid>")
@permission_required()
def delete(nid):
    n = db.get_or_404(Notification, nid)
    if n.user_id != current_user().id:
        raise BusinessError("Not found", 404)
    db.session.delete(n)
    db.session.commit()
    return ok(None, "Deleted")


@bp.post("/scan")
@permission_required("inventory.view")
def scan():
    res = scan_alerts()
    db.session.commit()
    return ok(res, "Alert scan complete")
