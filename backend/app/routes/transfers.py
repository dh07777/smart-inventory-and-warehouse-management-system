from flask import Blueprint, request
from ..extensions import db
from ..models import Transfer
from ..schemas import TransferSchema, TrfDispatchSchema, TrfReceiveSchema, ReasonSchema, NoteSchema
from ..utils import ok, load, paginate, audit, permission_required, current_user
from ..services import transfer_service as svc
from ..repositories import order_repository as orders

bp = Blueprint("transfers", __name__, url_prefix="/api/transfers")


@bp.get("")
@permission_required("transfers.view")
def list_transfers():
    return paginate(orders.transfers(request.args))


@bp.get("/<int:tid>")
@permission_required("transfers.view")
def get_transfer(tid):
    return ok(db.get_or_404(Transfer, tid).detail())


def _act(tid, fn, perm_msg, action, *args):
    t = db.get_or_404(Transfer, tid)
    fn(t, *args)
    audit(f"transfer.{action}", "transfer", tid)
    db.session.commit()
    return ok(t.detail(), perm_msg)


@bp.post("")
@permission_required("transfers.create")
def create():
    t = svc.create(load(TransferSchema), current_user())
    audit("transfer.create", "transfer", t.id)
    db.session.commit()
    return ok(t.detail(), "Transfer requested", 201)


@bp.post("/<int:tid>/approve")
@permission_required("transfers.approve")
def approve(tid):
    return _act(tid, svc.approve, "Transfer approved", "approve", current_user())


@bp.post("/<int:tid>/reject")
@permission_required("transfers.approve")
def reject(tid):
    return _act(tid, svc.reject, "Transfer rejected", "reject", current_user(), load(ReasonSchema).get("reason"))


@bp.post("/<int:tid>/cancel")
@permission_required("transfers.create", "transfers.approve")
def cancel(tid):
    return _act(tid, svc.cancel, "Transfer cancelled", "cancel")


@bp.post("/<int:tid>/dispatch")
@permission_required("transfers.process")
def dispatch(tid):
    d = load(TrfDispatchSchema)
    return _act(tid, svc.dispatch, "Transfer dispatched - stock is now in transit", "dispatch", d.get("items"), current_user(), d.get("idempotency_key"))


@bp.post("/<int:tid>/receive")
@permission_required("transfers.process")
def receive(tid):
    d = load(TrfReceiveSchema)
    return _act(tid, svc.receive, "Transfer received into destination warehouse", "receive", d.get("items"), current_user(), d.get("note"), d.get("idempotency_key"))


@bp.post("/<int:tid>/resolve")
@permission_required("transfers.approve")
def resolve(tid):
    return _act(tid, svc.resolve_discrepancy, "Discrepancy resolved", "resolve", load(NoteSchema)["note"])
