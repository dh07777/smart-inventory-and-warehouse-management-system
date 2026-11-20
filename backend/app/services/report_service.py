"""Report registry + PDF / Excel export + invoice PDFs. Every figure is computed from the database."""
import io
from xml.sax.saxutils import escape
from datetime import datetime, timedelta, date
from sqlalchemy import func
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from ..extensions import db
from ..models import (Inventory, Batch, Product, Warehouse, StockMovement, PurchaseOrder, PurchaseOrderItem, SalesOrder, SalesOrderItem,
                      Supplier, SupplierPayment)
from ..utils import now
from . import inventory_service as inv
from .notification_service import get_setting


def _range(f, t):
    start = datetime.combine(f, datetime.min.time()) if f else None
    end = datetime.combine(t + timedelta(days=1), datetime.min.time()) if t else None
    return start, end


def _cols(*pairs):
    return [{"key": k, "label": l} for k, l in pairs]


def inventory_valuation(f, t, wh):
    q = (db.session.query(Product.sku, Product.name, Warehouse.name, func.sum(Inventory.quantity), func.sum(Inventory.quantity * Batch.unit_cost))
         .join(Inventory, Inventory.product_id == Product.id).join(Batch, Inventory.batch_id == Batch.id)
         .join(Warehouse, Inventory.warehouse_id == Warehouse.id).group_by(Product.id, Warehouse.id).having(func.sum(Inventory.quantity) != 0))
    if wh:
        q = q.filter(Inventory.warehouse_id == wh)
    rows = [{"sku": s, "product": n, "warehouse": w, "quantity": int(qty), "avg_cost": round(v / qty, 2) if qty else 0, "value": round(v, 2)}
            for s, n, w, qty, v in q.order_by(Product.name)]
    return {"title": "Inventory Valuation (FIFO)", "columns": _cols(("sku", "SKU"), ("product", "Product"), ("warehouse", "Warehouse"),
            ("quantity", "Qty"), ("avg_cost", "Avg Cost"), ("value", "Value")), "rows": rows,
            "summary": {"Total units": sum(r["quantity"] for r in rows), "Total value": round(sum(r["value"] for r in rows), 2)},
            "chart": {"label": "product", "value": "value"}}


def stock_movements(f, t, wh):
    s, e = _range(f, t)
    q = StockMovement.query
    if s:
        q = q.filter(StockMovement.created_at >= s)
    if e:
        q = q.filter(StockMovement.created_at < e)
    if wh:
        q = q.filter(StockMovement.warehouse_id == wh)
    rows = [{"date": m.created_at.strftime("%Y-%m-%d %H:%M"), "type": m.movement_type, "sku": m.product.sku, "product": m.product.name,
             "warehouse": m.warehouse.name, "batch": m.batch.batch_no if m.batch else "", "quantity": m.quantity,
             "value": round(m.quantity * (m.unit_cost or 0), 2), "user": m.user.name if m.user else ""}
            for m in q.order_by(StockMovement.created_at.desc()).limit(5000)]
    by = {}
    for r in rows:
        by[r["type"]] = by.get(r["type"], 0) + abs(r["quantity"])
    return {"title": "Stock Movements", "columns": _cols(("date", "Date"), ("type", "Type"), ("sku", "SKU"), ("product", "Product"),
            ("warehouse", "Warehouse"), ("batch", "Batch"), ("quantity", "Qty"), ("value", "Value"), ("user", "User")), "rows": rows,
            "summary": {"Movements": len(rows)}, "chart_rows": [{"type": k, "units": v} for k, v in by.items()],
            "chart": {"label": "type", "value": "units", "use_chart_rows": True}}


def low_stock(f, t, wh):
    stock = inv.stock_map(wh)
    rows = []
    for p in Product.query.filter_by(status="active").order_by(Product.name):
        q = stock.get(p.id, 0)
        if q <= 0 or (p.min_stock > 0 and q <= p.min_stock):
            rows.append({"sku": p.sku, "product": p.name, "on_hand": q, "min_stock": p.min_stock, "status": "Out of stock" if q <= 0 else "Low stock",
                         "reorder_qty": max(p.reorder_qty, (p.max_stock or p.min_stock * 3) - q)})
    return {"title": "Low & Out-of-Stock", "columns": _cols(("sku", "SKU"), ("product", "Product"), ("on_hand", "On hand"), ("min_stock", "Min"),
            ("status", "Status"), ("reorder_qty", "Suggested reorder")), "rows": rows, "summary": {"Products": len(rows)},
            "chart": {"label": "product", "value": "on_hand"}}


def expiry(f, t, wh):
    limit = t or (now().date() + timedelta(days=90))
    q = (db.session.query(Batch, Warehouse.name, func.sum(Inventory.quantity)).join(Inventory, Inventory.batch_id == Batch.id)
         .join(Warehouse, Warehouse.id == Inventory.warehouse_id).filter(Batch.expiry_date.isnot(None), Batch.expiry_date <= limit)
         .group_by(Batch.id, Warehouse.id).having(func.sum(Inventory.quantity) > 0))
    if wh:
        q = q.filter(Inventory.warehouse_id == wh)
    rows = []
    for b, w, qty in q.order_by(Batch.expiry_date):
        p = db.session.get(Product, b.product_id)
        days = (b.expiry_date - now().date()).days
        rows.append({"sku": p.sku, "product": p.name, "batch": b.batch_no, "warehouse": w, "quantity": int(qty), "expiry": b.expiry_date.isoformat(),
                     "days_left": days, "status": "Expired" if days < 0 else ("Expiring soon" if days <= 30 else "OK")})
    return {"title": f"Expiry Report (up to {limit})", "columns": _cols(("sku", "SKU"), ("product", "Product"), ("batch", "Batch"),
            ("warehouse", "Warehouse"), ("quantity", "Qty"), ("expiry", "Expiry"), ("days_left", "Days left"), ("status", "Status")),
            "rows": rows, "summary": {"Batches": len(rows)}, "chart": {"label": "batch", "value": "quantity"}}


def warehouse_stock(f, t, wh):
    rows = []
    q = Warehouse.query.order_by(Warehouse.name)
    if wh:
        q = q.filter(Warehouse.id == wh)
    for w in q:
        units = int(db.session.query(func.coalesce(func.sum(Inventory.quantity), 0)).filter(Inventory.warehouse_id == w.id).scalar())
        prods = db.session.query(func.count(func.distinct(Inventory.product_id))).filter(Inventory.warehouse_id == w.id, Inventory.quantity > 0).scalar()
        rows.append({"code": w.code, "warehouse": w.name, "products": prods, "units": units, "value": inv.valuation(w.id), "capacity": w.capacity,
                     "utilization": round(units * 100 / w.capacity, 1) if w.capacity else 0})
    return {"title": "Warehouse-wise Stock", "columns": _cols(("code", "Code"), ("warehouse", "Warehouse"), ("products", "Products"), ("units", "Units"),
            ("value", "Value"), ("capacity", "Capacity"), ("utilization", "Utilization %")), "rows": rows,
            "summary": {"Units": sum(r["units"] for r in rows), "Value": round(sum(r["value"] for r in rows), 2)}, "chart": {"label": "warehouse", "value": "units"}}


def purchases(f, t, wh):
    s, e = _range(f, t)
    q = PurchaseOrder.query
    if s:
        q = q.filter(PurchaseOrder.order_date >= s)
    if e:
        q = q.filter(PurchaseOrder.order_date < e)
    if wh:
        q = q.filter(PurchaseOrder.warehouse_id == wh)
    rows = [{"po": p.po_number, "date": p.order_date.strftime("%Y-%m-%d"), "supplier": p.supplier.name, "status": p.status, "total": p.total,
             "received_pct": p.extra()["received_pct"]} for p in q.order_by(PurchaseOrder.order_date.desc())]
    valid = [r for r in rows if r["status"] not in ("rejected", "cancelled")]
    return {"title": "Purchase Report", "columns": _cols(("po", "PO #"), ("date", "Date"), ("supplier", "Supplier"), ("status", "Status"),
            ("total", "Total"), ("received_pct", "Received %")), "rows": rows,
            "summary": {"Orders": len(rows), "Total purchased": round(sum(r["total"] for r in valid), 2)}, "chart": {"label": "po", "value": "total"}}


def sales(f, t, wh):
    s, e = _range(f, t)
    q = SalesOrder.query
    if s:
        q = q.filter(SalesOrder.order_date >= s)
    if e:
        q = q.filter(SalesOrder.order_date < e)
    if wh:
        q = q.filter(SalesOrder.warehouse_id == wh)
    rows = [{"so": o.so_number, "date": o.order_date.strftime("%Y-%m-%d"), "customer": o.customer.name, "status": o.status, "total": o.total,
             "cogs": o.cogs_total, "margin": round(o.total - o.tax_total - o.cogs_total, 2) if o.cogs_total else 0} for o in q.order_by(SalesOrder.order_date.desc())]
    valid = [r for r in rows if r["status"] in ("dispatched", "delivered", "returned")]
    return {"title": "Sales Report", "columns": _cols(("so", "SO #"), ("date", "Date"), ("customer", "Customer"), ("status", "Status"),
            ("total", "Total"), ("cogs", "COGS"), ("margin", "Margin")), "rows": rows,
            "summary": {"Orders": len(rows), "Fulfilled revenue": round(sum(r["total"] for r in valid), 2), "Gross margin": round(sum(r["margin"] for r in valid), 2)},
            "chart": {"label": "so", "value": "total"}}


def suppliers(f, t, wh):
    rows = []
    for s in Supplier.query.order_by(Supplier.name):
        pos = PurchaseOrder.query.filter(PurchaseOrder.supplier_id == s.id, PurchaseOrder.status.notin_(["rejected", "cancelled"])).all()
        done = [p for p in pos if p.status == "received"]
        dated = [p for p in done if p.expected_date and p.received_at]
        ontime = [p for p in dated if p.received_at.date() <= p.expected_date]
        ordered = sum(i.quantity for p in pos if p.status in ("approved", "partially_received", "received") for i in p.items)
        got = sum(i.received_qty for p in pos for i in p.items)
        total = round(sum(p.total for p in pos), 2)
        paid = round(db.session.query(func.coalesce(func.sum(SupplierPayment.amount), 0)).filter(SupplierPayment.supplier_id == s.id).scalar(), 2)
        rows.append({"code": s.code, "supplier": s.name, "orders": len(pos), "purchased": total, "paid": paid, "outstanding": round(total - paid, 2),
                     "on_time_pct": round(len(ontime) * 100 / len(dated), 1) if dated else 0,
                     "avg_delay_days": round(sum((p.received_at.date() - p.expected_date).days for p in dated) / len(dated), 1) if dated else 0,
                     "fill_rate_pct": round(got * 100 / ordered, 1) if ordered else 0, "rating": s.rating})
    return {"title": "Supplier Report", "columns": _cols(("code", "Code"), ("supplier", "Supplier"), ("orders", "Orders"), ("purchased", "Purchased"),
            ("paid", "Paid"), ("outstanding", "Outstanding"), ("on_time_pct", "On-time %"), ("avg_delay_days", "Avg delay (d)"), ("fill_rate_pct", "Fill rate %"), ("rating", "Rating")), "rows": rows,
            "summary": {"Suppliers": len(rows)}, "chart": {"label": "supplier", "value": "purchased"}}


def product_performance(f, t, wh):
    s, e = _range(f, t)
    q = (db.session.query(Product.sku, Product.name, func.sum(SalesOrderItem.quantity),
                          func.sum(SalesOrderItem.quantity * SalesOrderItem.unit_price * (1 - SalesOrderItem.discount / 100)), func.sum(SalesOrderItem.cogs))
         .join(SalesOrderItem, SalesOrderItem.product_id == Product.id).join(SalesOrder, SalesOrder.id == SalesOrderItem.sales_order_id)
         .filter(SalesOrder.status.in_(["dispatched", "delivered", "returned"])))
    if s:
        q = q.filter(SalesOrder.order_date >= s)
    if e:
        q = q.filter(SalesOrder.order_date < e)
    stock = inv.stock_map(wh)
    rows = []
    for sku, name, units, rev, cogs in q.group_by(Product.id).order_by(func.sum(SalesOrderItem.quantity).desc()):
        pid = db.session.query(Product.id).filter_by(sku=sku).scalar()
        rows.append({"sku": sku, "product": name, "units_sold": int(units), "revenue": round(rev, 2), "cogs": round(cogs or 0, 2),
                     "profit": round(rev - (cogs or 0), 2), "on_hand": stock.get(pid, 0)})
    return {"title": "Product Performance", "columns": _cols(("sku", "SKU"), ("product", "Product"), ("units_sold", "Units sold"), ("revenue", "Revenue"),
            ("cogs", "COGS"), ("profit", "Profit"), ("on_hand", "On hand")), "rows": rows, "summary": {"Products sold": len(rows)},
            "chart": {"label": "product", "value": "units_sold"}}


REPORTS = {
    "inventory-valuation": (inventory_valuation, "Inventory valuation"), "stock-movements": (stock_movements, "Stock movements"),
    "low-stock": (low_stock, "Low stock"), "expiry": (expiry, "Expiry"), "warehouse-stock": (warehouse_stock, "Warehouse-wise stock"),
    "purchases": (purchases, "Purchases"), "sales": (sales, "Sales"), "suppliers": (suppliers, "Suppliers"),
    "product-performance": (product_performance, "Product performance"),
}


def run(key, f=None, t=None, wh=None):
    fn = REPORTS[key][0]
    out = fn(f, t, wh)
    out["key"], out["generated_at"] = key, now().strftime("%Y-%m-%d %H:%M")
    out["date_from"], out["date_to"] = (f.isoformat() if f else None), (t.isoformat() if t else None)
    return out


def to_xlsx(rep):
    wb = Workbook()
    ws = wb.active
    ws.title = rep["title"][:31]
    ws.append([get_setting("company_name", "StockPilot")])
    ws.append([rep["title"], f"Generated {rep['generated_at']}"])
    ws.append([])
    ws.append([c["label"] for c in rep["columns"]])
    for cell in ws[4]:
        cell.font, cell.fill = Font(bold=True, color="FFFFFF"), PatternFill("solid", fgColor="1E40AF")
        cell.alignment = Alignment(horizontal="center")
    ws["A1"].font = Font(bold=True, size=14)
    for r in rep["rows"]:
        ws.append([r.get(c["key"]) for c in rep["columns"]])
    for k, v in rep["summary"].items():
        ws.append([])
        ws.append([k, v])
    for i, c in enumerate(rep["columns"], 1):
        width = max([len(str(c["label"]))] + [len(str(r.get(c["key"], ""))) for r in rep["rows"][:200]]) + 2
        ws.column_dimensions[ws.cell(row=4, column=i).column_letter].width = min(width, 45)
    ws.freeze_panes = "A5"
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def to_pdf(rep):
    buf = io.BytesIO()
    wide = len(rep["columns"]) > 6
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4) if wide else A4, leftMargin=12 * mm, rightMargin=12 * mm, topMargin=12 * mm, bottomMargin=12 * mm,
                            title=rep["title"])
    st = getSampleStyleSheet()
    el = [Paragraph(f"<b>{escape(get_setting('company_name', 'StockPilot'))}</b>", st["Title"]), Paragraph(escape(rep["title"]), st["Heading2"]),
          Paragraph(f"Generated {rep['generated_at']} | Range: {rep['date_from'] or 'start'} to {rep['date_to'] or 'today'}", st["Normal"]), Spacer(1, 6 * mm)]
    data = [[c["label"] for c in rep["columns"]]] + [[str(r.get(c["key"], "")) for c in rep["columns"]] for r in rep["rows"][:1500]]
    tbl = Table(data, repeatRows=1)
    tbl.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e40af")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                             ("FONTSIZE", (0, 0), (-1, -1), 7.5), ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                             ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f1f5f9")])]))
    el += [tbl, Spacer(1, 5 * mm)] + [Paragraph(f"<b>{k}:</b> {v}", st["Normal"]) for k, v in rep["summary"].items()]
    doc.build(el)
    buf.seek(0)
    return buf


def invoice_pdf(kind, order):
    """kind = 'purchase' | 'sales'"""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=15 * mm, bottomMargin=15 * mm)
    st = getSampleStyleSheet()
    sym = get_setting("currency_symbol", "$")
    sales_ = kind == "sales"
    party = order.customer if sales_ else order.supplier
    el = [Paragraph(f"<b>{escape(get_setting('company_name', 'StockPilot'))}</b>", st["Title"]),
          Paragraph(("SALES INVOICE " if sales_ else "PURCHASE INVOICE ") + (order.invoice_no or ""), st["Heading2"]),
          Paragraph(f"{'Order' if sales_ else 'PO'}: {order.so_number if sales_ else order.po_number} | Date: {order.order_date:%Y-%m-%d} | "
                    f"{'Customer' if sales_ else 'Supplier'}: {escape(party.name)}", st["Normal"]), Spacer(1, 6 * mm)]
    data = [["SKU", "Product", "Qty", "Unit price", "Tax %", "Total"]]
    for i in order.items:
        data.append([i.product.sku, i.product.name, i.quantity, f"{sym}{i.unit_price:.2f}", f"{i.tax_rate:g}", f"{sym}{i.extra()['line_total']:.2f}"])
    t = Table(data, repeatRows=1, colWidths=[28 * mm, 66 * mm, 15 * mm, 25 * mm, 15 * mm, 28 * mm])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e40af")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                           ("GRID", (0, 0), (-1, -1), 0.25, colors.grey), ("FONTSIZE", (0, 0), (-1, -1), 8)]))
    el += [t, Spacer(1, 5 * mm), Paragraph(f"Subtotal: {sym}{order.subtotal:.2f}", st["Normal"])]
    if sales_:
        el.append(Paragraph(f"Discount: {sym}{order.discount_total:.2f}", st["Normal"]))
    el += [Paragraph(f"Tax: {sym}{order.tax_total:.2f}", st["Normal"]), Paragraph(f"<b>Total: {sym}{order.total:.2f}</b>", st["Heading3"])]
    doc.build(el)
    buf.seek(0)
    return buf
