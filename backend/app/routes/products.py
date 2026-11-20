import csv, io, os, uuid
from flask import Blueprint, request, current_app, send_file
from sqlalchemy import or_, func
from werkzeug.utils import secure_filename
from openpyxl import Workbook, load_workbook
from ..extensions import db
from ..models import Product, ProductVariant, Category, Supplier, Inventory, Warehouse
from ..schemas import ProductSchema, VariantSchema, CategorySchema
from ..utils import ok, load, paginate, audit, permission_required, BusinessError
from ..services import inventory_service as inv
from ..services.notification_service import get_setting
from ..repositories import product_repository
from .crud import register_crud

bp = Blueprint("products", __name__, url_prefix="/api/products")
cat_bp = Blueprint("categories", __name__, url_prefix="/api/categories")
register_crud(cat_bp, Category, CategorySchema, view="products.view", manage="products.manage", entity="category", search=("name",),
              filters=("parent_id",), sorts=("id", "name"), default_sort="name")
EXPORT_COLS = ["sku", "barcode", "name", "description", "category", "brand", "supplier_code", "unit", "purchase_price", "selling_price",
               "tax_rate", "discount", "min_stock", "max_stock", "reorder_qty", "status"]


@bp.get("")
@permission_required("products.view")
def list_products():
    res = inv.reserved_map()
    return paginate(product_repository.filtered_products(request.args), lambda r: {**r[0].to_dict(), "stock": int(r[1]), "reserved": res.get(r[0].id, 0),
                                            "stock_status": "out" if r[1] <= 0 else ("low" if r[0].min_stock and r[1] <= r[0].min_stock else "ok")})


@bp.get("/lookup")
@permission_required("products.view")
def lookup():
    code = (request.args.get("code") or "").strip()
    p = product_repository.find_by_code(code) if code else None
    if not p:
        raise BusinessError("No product with that barcode or SKU", 404)
    return ok({**p.to_dict(), "stock": inv.on_hand(p.id), "reserved": inv.reserved_qty(p.id)})


@bp.post("/generate-barcodes")
@permission_required("products.manage")
def generate_barcodes():
    """Assign a valid EAN-13 (in-store prefix 200) to every product that has no barcode."""
    n = 0
    for p in product_repository.products_without_barcode():
        code = product_repository.ean13_with_check("200" + f"{p.id:09d}")
        if not Product.query.filter_by(barcode=code).first():
            p.barcode, n = code, n + 1
    audit("product.generate_barcodes", "product", None, {"count": n})
    db.session.commit()
    return ok({"count": n}, f"{n} barcodes generated")


@bp.get("/<int:pid>")
@permission_required("products.view")
def get_product(pid):
    p = db.get_or_404(Product, pid)
    rows = (db.session.query(Warehouse.id, Warehouse.name, func.sum(Inventory.quantity)).join(Inventory, Inventory.warehouse_id == Warehouse.id)
            .filter(Inventory.product_id == pid).group_by(Warehouse.id).all())
    d = p.to_dict()
    d["variants"] = [v.to_dict() for v in p.variants]
    d["stock"] = inv.on_hand(pid)
    d["reserved"] = inv.reserved_qty(pid)
    d["warehouse_stock"] = [{"warehouse_id": i, "warehouse_name": n, "quantity": int(q)} for i, n, q in rows]
    return ok(d)


@bp.post("")
@permission_required("products.manage")
def create_product():
    data = {k: v for k, v in load(ProductSchema).items() if v is not None}
    if "tax_rate" not in data:  # company defaults from Settings
        data["tax_rate"] = float(get_setting("default_tax_rate", "0"))
    if "min_stock" not in data:
        data["min_stock"] = int(float(get_setting("default_min_stock", "0")))
    p = Product(**data)
    db.session.add(p)
    db.session.flush()
    audit("product.create", "product", p.id, {"sku": p.sku})
    db.session.commit()
    return ok(p.to_dict(), "Product created", 201)


@bp.put("/<int:pid>")
@permission_required("products.manage")
def update_product(pid):
    p = db.get_or_404(Product, pid)
    for k, v in load(ProductSchema, partial=True).items():
        if v is None and not Product.__table__.c[k].nullable:
            continue
        setattr(p, k, v)
    audit("product.update", "product", pid)
    db.session.commit()
    return ok(p.to_dict(), "Product updated")


@bp.delete("/<int:pid>")
@permission_required("products.manage")
def delete_product(pid):
    p = db.get_or_404(Product, pid)
    db.session.delete(p)
    audit("product.delete", "product", pid, {"sku": p.sku})
    db.session.commit()
    return ok(None, "Product deleted")


@bp.post("/<int:pid>/variants")
@permission_required("products.manage")
def add_variant(pid):
    db.get_or_404(Product, pid)
    v = ProductVariant(product_id=pid, **{k: x for k, x in load(VariantSchema).items() if x is not None})
    db.session.add(v)
    audit("product.variant_add", "product", pid)
    db.session.commit()
    return ok(v.to_dict(), "Variant added", 201)


@bp.delete("/variants/<int:vid>")
@permission_required("products.manage")
def delete_variant(vid):
    db.session.delete(db.get_or_404(ProductVariant, vid))
    db.session.commit()
    return ok(None, "Variant removed")


@bp.post("/<int:pid>/image")
@permission_required("products.manage")
def upload_image(pid):
    p = db.get_or_404(Product, pid)
    f = request.files.get("image")
    if not f or not f.filename:
        raise BusinessError("Choose an image file", 422)
    ext = os.path.splitext(secure_filename(f.filename))[1].lower()
    if ext not in (".png", ".jpg", ".jpeg", ".webp", ".gif"):
        raise BusinessError("Only PNG, JPG, WEBP or GIF images are allowed", 422)
    name = f"{uuid.uuid4().hex}{ext}"
    f.save(os.path.join(current_app.config["UPLOAD_FOLDER"], name))
    p.image_url = f"/uploads/{name}"
    audit("product.image", "product", pid)
    db.session.commit()
    return ok(p.to_dict(), "Image uploaded")


def _export_rows():
    return [[p.sku, p.barcode, p.name, p.description, p.category.name if p.category else "", p.brand, p.supplier.code if p.supplier else "", p.unit,
             p.purchase_price, p.selling_price, p.tax_rate, p.discount, p.min_stock, p.max_stock, p.reorder_qty, p.status]
            for p in Product.query.order_by(Product.name)]


@bp.get("/export")
@permission_required("products.view")
def export_products():
    fmt = request.args.get("format", "csv")
    rows = _export_rows()
    if fmt == "xlsx":
        wb = Workbook()
        ws = wb.active
        ws.append(EXPORT_COLS)
        for r in rows:
            ws.append(r)
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        return send_file(buf, as_attachment=True, download_name="products.xlsx", mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(EXPORT_COLS)
    w.writerows(rows)
    return send_file(io.BytesIO(out.getvalue().encode("utf-8-sig")), as_attachment=True, download_name="products.csv", mimetype="text/csv")


@bp.get("/import-template")
@permission_required("products.manage")
def import_template():
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(EXPORT_COLS)
    w.writerow(["SKU-1001", "8901234567890", "Sample product", "Description", "Electronics", "BrandX", "SUP-001", "pcs", 10, 15, 5, 0, 10, 100, 50, "active"])
    return send_file(io.BytesIO(out.getvalue().encode("utf-8-sig")), as_attachment=True, download_name="product_import_template.csv", mimetype="text/csv")


@bp.post("/import")
@permission_required("products.manage")
def import_products():
    f = request.files.get("file")
    if not f or not f.filename:
        raise BusinessError("Upload a .csv or .xlsx file", 422)
    name = f.filename.lower()
    if name.endswith(".csv"):
        reader = list(csv.DictReader(io.StringIO(f.read().decode("utf-8-sig"))))
    elif name.endswith(".xlsx"):
        ws = load_workbook(f, read_only=True, data_only=True).active
        rows = list(ws.iter_rows(values_only=True))
        head = [str(h or "").strip().lower() for h in rows[0]] if rows else []
        reader = [dict(zip(head, r)) for r in rows[1:]]
    else:
        raise BusinessError("Only .csv and .xlsx files are supported", 422)
    created = updated = 0
    errors = []
    for n, raw in enumerate(reader, start=2):
        raw = {str(k).strip().lower(): (str(v).strip() if v is not None else "") for k, v in raw.items() if k}
        try:
            row = {k: raw.get(k, "") for k in ProductSchema().fields if raw.get(k, "") != ""}
            if raw.get("category"):
                c = Category.query.filter_by(name=raw["category"], parent_id=None).first()
                if not c:
                    c = Category(name=raw["category"])
                    db.session.add(c)
                    db.session.flush()
                row["category_id"] = c.id
            if raw.get("supplier_code"):
                s = Supplier.query.filter_by(code=raw["supplier_code"]).first()
                if not s:
                    raise BusinessError(f"Unknown supplier code {raw['supplier_code']}")
                row["supplier_id"] = s.id
            existing = Product.query.filter_by(sku=row.get("sku")).first()
            data = load(ProductSchema, partial=bool(existing), data=row)
            with db.session.begin_nested():  # savepoint per row: one bad row never poisons the rest
                if existing:
                    for k, v in data.items():
                        setattr(existing, k, v)
                    updated += 1
                else:
                    db.session.add(Product(**{k: v for k, v in data.items() if v is not None}))
                    created += 1
                db.session.flush()
        except BusinessError as e:
            errors.append({"row": n, "error": e.message if not e.details else str(e.details)})
        except Exception as e:  # duplicate barcode etc.
            errors.append({"row": n, "error": str(getattr(e, "orig", e))})
    audit("product.import", "product", None, {"created": created, "updated": updated, "errors": len(errors)})
    db.session.commit()
    return ok({"created": created, "updated": updated, "errors": errors}, f"Import finished: {created} created, {updated} updated, {len(errors)} errors")
