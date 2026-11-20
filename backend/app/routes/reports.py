from flask import Blueprint, request, send_file
from ..utils import ok, permission_required, parse_date, BusinessError
from ..services import report_service as svc

bp = Blueprint("reports", __name__, url_prefix="/api/reports")


@bp.get("")
@permission_required("reports.view")
def catalogue():
    return ok([{"key": k, "title": v[1]} for k, v in svc.REPORTS.items()])


@bp.get("/<key>")
@permission_required("reports.view")
def report(key):
    if key not in svc.REPORTS:
        raise BusinessError("Unknown report", 404)
    f, t = parse_date(request.args.get("date_from")), parse_date(request.args.get("date_to"))
    if f and t and f > t:
        raise BusinessError("Start date must be before end date", 422)
    rep = svc.run(key, f, t, request.args.get("warehouse_id", type=int))
    fmt = request.args.get("format", "json")
    if fmt == "xlsx":
        return send_file(svc.to_xlsx(rep), as_attachment=True, download_name=f"{key}.xlsx",
                         mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    if fmt == "pdf":
        return send_file(svc.to_pdf(rep), as_attachment=True, download_name=f"{key}.pdf", mimetype="application/pdf")
    return ok(rep)
