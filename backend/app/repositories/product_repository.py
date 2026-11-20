"""Data access for products and categories."""
from sqlalchemy import or_, func
from ..extensions import db
from ..models import Product, Category, Inventory


def category_tree_ids(category_id):
    ids, frontier = {category_id}, [category_id]
    while frontier:
        kids = [c.id for c in Category.query.filter(Category.parent_id.in_(frontier)).all()]
        frontier = [k for k in kids if k not in ids]
        ids.update(frontier)
    return ids


def filtered_products(args):
    """Products + total stock, with search / filters / sorting. Returns a query of (Product, qty)."""
    sq = db.session.query(Inventory.product_id.label("pid"), func.sum(Inventory.quantity).label("qty")).group_by(Inventory.product_id).subquery()
    qty = func.coalesce(sq.c.qty, 0)
    q = db.session.query(Product, qty.label("qty")).outerjoin(sq, sq.c.pid == Product.id)
    s = (args.get("q") or "").strip()
    if s:
        like = f"%{s}%"
        q = q.filter(or_(Product.name.ilike(like), Product.sku.ilike(like), Product.barcode.ilike(like), Product.brand.ilike(like)))
    if args.get("category_id"):
        q = q.filter(Product.category_id.in_(category_tree_ids(int(args["category_id"]))))
    for f in ("supplier_id", "status", "brand"):
        if args.get(f):
            q = q.filter(getattr(Product, f) == args[f])
    st = args.get("stock")
    if st == "out":
        q = q.filter(qty <= 0)
    elif st == "low":
        q = q.filter(qty > 0, Product.min_stock > 0, qty <= Product.min_stock)
    elif st == "ok":
        q = q.filter(qty > 0, or_(Product.min_stock == 0, qty > Product.min_stock))
    cols = {"name": Product.name, "sku": Product.sku, "selling_price": Product.selling_price, "purchase_price": Product.purchase_price,
            "created_at": Product.created_at, "stock": qty}
    col = cols.get(args.get("sort") or "created_at", Product.created_at)
    return q.order_by(col.desc() if (args.get("order") or "desc") == "desc" else col.asc())


def find_by_code(code):
    """Look a product up by barcode or SKU (exact match)."""
    return Product.query.filter(or_(Product.barcode == code, Product.sku == code)).first()


def ean13_with_check(body12):
    digits = [int(c) for c in body12]
    total = sum(d * (3 if i % 2 else 1) for i, d in enumerate(digits))
    return body12 + str((10 - total % 10) % 10)


def products_without_barcode():
    return Product.query.filter(or_(Product.barcode.is_(None), Product.barcode == "")).order_by(Product.id).all()
