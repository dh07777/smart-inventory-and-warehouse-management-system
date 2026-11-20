"""Seed StockPilot with clearly-labelled DEMO data (not real business transactions).

    python seed.py --create-tables     # quick start: create tables + demo data
    python seed.py                     # after `flask db upgrade`
    python seed.py --reset             # wipe everything and re-seed
"""
import os, random, sys, zlib
from datetime import datetime, timedelta
from app import create_app
from app.extensions import db
from app.models import *  # noqa
from app.bootstrap import seed_core
from app.services import inventory_service as inv, purchase_service as ps, sales_service as ss, transfer_service as ts
from app.services.notification_service import scan_alerts

PASSWORD = os.getenv("DEMO_PASSWORD", "Demo@12345")
rng = random.Random(7)
img = lambda sku: f"https://picsum.photos/seed/{sku}/400/300"

CATS = {"Electronics": ["Laptops", "Accessories", "Mobile"], "Office Supplies": ["Stationery", "Furniture"], "Food & Beverages": ["Packaged Foods", "Beverages"],
        "Health & Hygiene": []}
SUPPLIERS = [("SUP-001", "TechSource Distribution", "Maya Chen", "USA"), ("SUP-002", "Global Office Depot", "Liam Carter", "USA"),
             ("SUP-003", "FreshFarm Wholesale", "Sofia Rossi", "Italy"), ("SUP-004", "MediCare Supplies", "Arjun Mehta", "India"),
             ("SUP-005", "Nordic Furniture AB", "Erik Lund", "Sweden"), ("SUP-006", "PowerGear Imports", "Hana Sato", "Japan")]
# sku, name, subcategory/category, brand, cost, price, tax, min, max, unit, supplier index, shelf_life_days
PRODUCTS = [
    ("LAP-1001", "UltraBook 14 Laptop", "Laptops", "Zenith", 540, 749, 8, 8, 60, "pcs", 0, None), ("LAP-1002", "ProBook 15 Laptop", "Laptops", "Zenith", 690, 949, 8, 6, 40, "pcs", 0, None),
    ("ACC-2001", "Wireless Mouse", "Accessories", "Clickr", 9, 19.9, 8, 40, 400, "pcs", 5, None), ("ACC-2002", "Mechanical Keyboard", "Accessories", "Clickr", 32, 64, 8, 25, 250, "pcs", 5, None),
    ("ACC-2003", "USB-C Hub 7-in-1", "Accessories", "PortMax", 18, 39, 8, 30, 300, "pcs", 5, None), ("ACC-2004", "27in Monitor", "Accessories", "ViewPro", 120, 189, 8, 10, 100, "pcs", 0, None),
    ("MOB-3001", "Smartphone X10", "Mobile", "Nova", 260, 399, 8, 15, 150, "pcs", 0, None), ("MOB-3002", "Phone Case Pack", "Mobile", "ShieldIt", 2.5, 7.9, 8, 80, 800, "pcs", 5, None),
    ("MOB-3003", "Fast Charger 65W", "Mobile", "PowerGo", 11, 24, 8, 50, 500, "pcs", 5, None), ("STA-4001", "A4 Copy Paper (500 sheets)", "Stationery", "PaperOne", 3.2, 6.5, 5, 100, 1500, "ream", 1, None),
    ("STA-4002", "Ballpoint Pens (box of 50)", "Stationery", "WriteWell", 4.1, 9.5, 5, 60, 600, "box", 1, None), ("STA-4003", "Stapler Heavy Duty", "Stationery", "BindIt", 5, 12, 5, 30, 300, "pcs", 1, None),
    ("STA-4004", "Sticky Notes (12 pack)", "Stationery", "NoteMe", 2.2, 5.5, 5, 80, 800, "pack", 1, None), ("FUR-5001", "Ergonomic Office Chair", "Furniture", "SitWell", 85, 159, 10, 10, 80, "pcs", 4, None),
    ("FUR-5002", "Standing Desk", "Furniture", "SitWell", 190, 329, 10, 6, 50, "pcs", 4, None), ("FUR-5003", "Filing Cabinet 3-Drawer", "Furniture", "SafeStore", 60, 109, 10, 8, 60, "pcs", 4, None),
    ("FOO-6001", "Organic Granola 500g", "Packaged Foods", "GoodMorn", 2.8, 5.99, 4, 60, 600, "pack", 2, 180), ("FOO-6002", "Basmati Rice 5kg", "Packaged Foods", "RiceKing", 6.5, 11.5, 4, 40, 400, "bag", 2, 365),
    ("FOO-6003", "Extra Virgin Olive Oil 1L", "Packaged Foods", "Olivia", 5.9, 12.9, 4, 30, 300, "bottle", 2, 365), ("FOO-6004", "Instant Noodles (carton 24)", "Packaged Foods", "QuickBite", 8, 15.5, 4, 25, 250, "carton", 2, 240),
    ("BEV-7001", "Sparkling Water 12-pack", "Beverages", "AquaFizz", 3.4, 7.2, 4, 80, 800, "pack", 2, 120), ("BEV-7002", "Orange Juice 1L (carton of 12)", "Beverages", "SunPress", 9.5, 18.5, 4, 40, 400, "carton", 2, 60),
    ("BEV-7003", "Ground Coffee 1kg", "Beverages", "BeanCo", 7.8, 16.9, 4, 35, 350, "bag", 2, 270), ("HLT-8001", "Hand Sanitizer 500ml", "Health & Hygiene", "CleanHand", 1.9, 4.5, 6, 100, 1000, "bottle", 3, 540),
    ("HLT-8002", "Disposable Masks (box of 50)", "Health & Hygiene", "SafeBreath", 2.4, 6.5, 6, 60, 600, "box", 3, 720), ("HLT-8003", "First Aid Kit", "Health & Hygiene", "MediPack", 9, 21, 6, 20, 200, "kit", 3, 900),
    ("HLT-8004", "Vitamin C Tablets (100)", "Health & Hygiene", "VitaPlus", 3.6, 8.9, 6, 40, 400, "bottle", 3, 300), ("ACC-2005", "Laptop Backpack", "Accessories", "CarryOn", 14, 34, 8, 25, 250, "pcs", 5, None),
    ("ACC-2006", "Webcam 1080p", "Accessories", "ViewPro", 16, 38, 8, 20, 200, "pcs", 0, None), ("STA-4005", "Whiteboard Markers (8)", "Stationery", "WriteWell", 3, 7.9, 5, 40, 400, "pack", 1, None),
]
OUT_OF_STOCK = {"ACC-2006", "STA-4005"}           # never purchased -> out of stock
LOW_STOCK = {"LAP-1002": 3, "FUR-5002": 4, "MOB-3001": 9}  # purchased in tiny quantities -> low stock


def reset():
    db.drop_all()
    db.create_all()


def run(create_tables=False, wipe=False):
    if wipe:
        reset()
    elif create_tables:
        db.create_all()
    if User.query.first():
        print("Database already contains data. Use --reset to wipe and re-seed.")
        return
    roles = seed_core()
    users = {}
    for email, name, role in [("admin@stockpilot.demo", "Alex Morgan", "Super Admin"), ("warehouse@stockpilot.demo", "Wendy Brooks", "Warehouse Manager"),
                              ("inventory@stockpilot.demo", "Ian Walker", "Inventory Manager"), ("purchase@stockpilot.demo", "Priya Nair", "Purchase Manager"),
                              ("sales@stockpilot.demo", "Sam Taylor", "Sales Manager"), ("staff@stockpilot.demo", "Sara Lopez", "Staff")]:
        u = User(name=name, email=email, role_id=roles[role].id)
        u.set_password(PASSWORD)
        db.session.add(u)
        users[role] = u
    db.session.flush()
    admin, buyer, seller, whm = users["Super Admin"], users["Purchase Manager"], users["Sales Manager"], users["Warehouse Manager"]

    cats = {}
    for parent, subs in CATS.items():
        p = Category(name=parent, description="DEMO category")
        db.session.add(p)
        db.session.flush()
        cats[parent] = p
        for s in subs:
            c = Category(name=s, parent_id=p.id)
            db.session.add(c)
            db.session.flush()
            cats[s] = c
    sups = []
    for code, name, contact, country in SUPPLIERS:
        s = Supplier(code=code, name=name, contact_person=contact, country=country, email=f"sales@{name.split()[0].lower()}.example.com", phone="+1 555 01" + code[-2:],
                     payment_terms="Net 30", rating=round(rng.uniform(3.6, 4.9), 1), notes="DEMO supplier - not a real company")
        db.session.add(s)
        sups.append(s)
    whs = []
    for code, name, city, cap in [("WH-NYC", "New York Central Warehouse", "New York", 6000), ("WH-CHI", "Chicago Distribution Hub", "Chicago", 4500),
                                  ("WH-LAX", "Los Angeles Fulfilment Center", "Los Angeles", 3500)]:
        w = Warehouse(code=code, name=name, city=city, address=f"{rng.randint(10, 999)} Logistics Way, {city}", capacity=cap, manager_id=whm.id, phone="+1 555 0100")
        db.session.add(w)
        whs.append(w)
    db.session.flush()
    for w in whs:
        for zone in ("A", "B"):
            for rack in ("R1", "R2"):
                db.session.add(WarehouseLocation(warehouse_id=w.id, zone=zone, rack=rack, shelf="S1", bin="B1"))
    prods = {}
    for sku, name, cat, brand, cost, price, tax, mn, mx, unit, si, shelf in PRODUCTS:
        p = Product(sku=sku, barcode="89" + str(zlib.crc32(sku.encode())).zfill(11), name=name, category_id=cats[cat].id, brand=brand, supplier_id=sups[si].id, unit=unit,
                    purchase_price=cost, selling_price=price, tax_rate=tax, min_stock=mn, max_stock=mx, reorder_qty=max(mn * 2, 10), image_url=img(sku),
                    description=f"DEMO product: {name}. Sample record for demonstration only.", is_demo=True)
        db.session.add(p)
        prods[sku] = (p, shelf)
    customers = []
    for i, (n, c) in enumerate([("Northwind Retail", "Boston"), ("Blue Harbor Cafe", "Seattle"), ("Summit Offices Ltd", "Denver"), ("Greenleaf Clinics", "Austin"),
                                ("Orbit Electronics Store", "Miami"), ("Maple School District", "Portland"), ("Riverside Hotel Group", "Chicago"), ("Pixel Co-working", "San Diego")], 1):
        cu = Customer(code=f"CUS-{i:03d}", name=n, company=n, city=c, email=f"orders@{n.split()[0].lower()}.example.com", phone=f"+1 555 02{i:02d}", notes="DEMO customer")
        db.session.add(cu)
        customers.append(cu)
    db.session.flush()

    today = datetime.utcnow()
    months = []
    y, m = today.year, today.month
    for _ in range(6):
        months.append((y, m))
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    months.reverse()

    def when(y, m, d, h=10):
        return min(datetime(y, m, d, h), today - timedelta(minutes=5))

    buyable = [s for s in prods if s not in OUT_OF_STOCK]
    pay_candidates, bought_low = [], set()
    for idx, (y, m) in enumerate(months):
        for _ in range(3):  # purchases early in the month
            sup = rng.choice(sups)
            skus = [s for s in buyable if prods[s][0].supplier_id == sup.id] or buyable[:3]
            picks = rng.sample(skus, min(len(skus), rng.randint(2, 5)))
            items = []
            for s in picks:
                if s in LOW_STOCK:
                    if s in bought_low:
                        continue
                    bought_low.add(s)
                items.append({"product_id": prods[s][0].id, "quantity": LOW_STOCK.get(s, rng.randint(40, 160))})
            if not items:
                continue
            at = when(y, m, rng.randint(2, 8))
            wh = rng.choice(whs)
            po = ps.create_po({"supplier_id": sup.id, "warehouse_id": wh.id, "items": items, "notes": "DEMO purchase order",
                               "expected_date": (at + timedelta(days=5)).date()}, buyer, at=at, demo=True)
            ps.approve(po, admin, at=at)
            rat = at + timedelta(days=rng.randint(2, 7))
            rat = min(rat, today - timedelta(minutes=1))
            lines = []
            for it in po.items:
                shelf = prods[it.product.sku][1]
                exp = None
                if shelf:
                    exp = (rat + timedelta(days=shelf)).date()
                lines.append({"item_id": it.id, "quantity": it.quantity, "batch_no": f"{it.product.sku}-{rat:%y%m}", "expiry_date": exp})
            ps.receive(po, lines, whm, at=rat)
            pay_candidates.append(po)
        for _ in range(rng.randint(5, 9)):  # sales later in the month
            wh, cust = rng.choice(whs), rng.choice(customers)
            items = []
            for s in rng.sample(buyable, rng.randint(1, 4)):
                p = prods[s][0]
                q = rng.randint(1, 12)
                if s in LOW_STOCK:
                    continue
                if inv.available(p.id, wh.id) >= q:
                    items.append({"product_id": p.id, "quantity": q})
            if not items:
                continue
            at = when(y, m, rng.randint(10, 26), 14)
            so = ss.create_so({"customer_id": cust.id, "warehouse_id": wh.id, "items": items, "notes": "DEMO sales order"}, seller, at=at, demo=True)
            ss.confirm(so, seller)
            ss.dispatch(so, whm, rng.choice(["DHL", "FedEx", "UPS"]), f"TRK{rng.randint(10**8, 10**9 - 1)}", at=at)
            if at < today - timedelta(days=3):
                ss.deliver(so, at=at + timedelta(days=2))
                so.paid_amount = so.total if rng.random() < 0.8 else round(so.total / 2, 2)
    db.session.flush()

    for po in pay_candidates[:8]:  # a few supplier payments
        db.session.add(SupplierPayment(supplier_id=po.supplier_id, purchase_order_id=po.id, amount=round(po.total * rng.choice([1, 0.5]), 2), method="bank_transfer",
                                       reference=f"PAY-{po.po_number}", note="DEMO payment", created_by=buyer.id))
    # open workflow examples ------------------------------------------------
    first = lambda sku: prods[sku][0].id
    ps.create_po({"supplier_id": sups[0].id, "warehouse_id": whs[0].id, "items": [{"product_id": first("LAP-1002"), "quantity": 20}, {"product_id": first("MOB-3001"), "quantity": 30}],
                  "notes": "DEMO - restock low items"}, buyer, demo=True)
    po2 = ps.create_po({"supplier_id": sups[5].id, "warehouse_id": whs[1].id, "items": [{"product_id": first("ACC-2006"), "quantity": 60}], "notes": "DEMO - awaiting delivery"}, buyer, demo=True)
    ps.approve(po2, admin)
    so_open = ss.create_so({"customer_id": customers[0].id, "warehouse_id": whs[0].id, "items": [{"product_id": first("ACC-2001"), "quantity": 5}]}, seller, demo=True)
    so_conf = ss.create_so({"customer_id": customers[2].id, "warehouse_id": whs[0].id, "items": [{"product_id": first("STA-4001"), "quantity": 20}]}, seller, demo=True)
    ss.confirm(so_conf, seller)
    # purchase requests in each state (request -> approval -> PO) ---------------
    pr1 = ps.create_request({"warehouse_id": whs[0].id, "reason": "DEMO: low stock on laptops", "priority": "high",
                             "items": [{"product_id": first("LAP-1002"), "quantity": 15, "note": "urgent"}]}, whm, demo=True)
    pr2 = ps.create_request({"warehouse_id": whs[1].id, "reason": "DEMO: quarterly office restock", "priority": "normal",
                             "items": [{"product_id": first("STA-4003"), "quantity": 100}, {"product_id": first("STA-4004"), "quantity": 150}]}, whm, demo=True)
    ps.review_request(pr2, admin, True)
    pr3 = ps.create_request({"warehouse_id": whs[2].id, "reason": "DEMO: beverages promo", "priority": "low",
                             "items": [{"product_id": first("BEV-7001"), "quantity": 120}]}, whm, demo=True)
    ps.review_request(pr3, admin, True)
    ps.convert_request(pr3, {"supplier_id": sups[2].id}, buyer)
    pr4 = ps.create_request({"warehouse_id": whs[0].id, "reason": "DEMO: not needed", "items": [{"product_id": first("FUR-5003"), "quantity": 50}]}, whm, demo=True)
    ps.review_request(pr4, admin, False, "Budget frozen this quarter")
    delivered = SalesOrder.query.filter_by(status="delivered").first()
    if delivered:
        it = delivered.items[0]
        r1 = ss.create_return(delivered, {"reason": "DEMO: customer changed mind", "restock": True, "items": [{"product_id": it.product_id, "quantity": 1, "condition": "good"}]}, seller)
        ss.approve_return(r1, admin)
        ss.create_return(delivered, {"reason": "DEMO: damaged in transit", "restock": False, "items": [{"product_id": it.product_id, "quantity": 1, "condition": "damaged"}]}, seller)
    cand = [s for s in buyable if s not in LOW_STOCK and inv.available(prods[s][0].id, whs[0].id) >= 30][:4]
    if len(cand) >= 3:
        t1 = ts.create({"from_warehouse_id": whs[0].id, "to_warehouse_id": whs[1].id, "items": [{"product_id": prods[cand[0]][0].id, "quantity": 10}, {"product_id": prods[cand[1]][0].id, "quantity": 12}], "notes": "DEMO rebalancing"}, whm, demo=True)
        ts.approve(t1, admin)
        ts.dispatch(t1, None, whm)
        ts.receive(t1, [{"item_id": t1.items[0].id, "received_qty": 9}, {"item_id": t1.items[1].id, "received_qty": 12}], whm, note="One unit damaged on arrival")
        t2 = ts.create({"from_warehouse_id": whs[0].id, "to_warehouse_id": whs[2].id, "items": [{"product_id": prods[cand[2]][0].id, "quantity": 8}], "notes": "DEMO in transit"}, whm, demo=True)
        ts.approve(t2, admin)
        ts.dispatch(t2, None, whm)
        t3 = ts.create({"from_warehouse_id": whs[1].id, "to_warehouse_id": whs[0].id, "items": [{"product_id": prods[cand[0]][0].id, "quantity": 3}], "notes": "DEMO pending approval"}, whm, demo=True)
    expired_sku = "FOO-6001"
    p = prods[expired_sku][0]
    inv.stock_in(p.id, whs[2].id, 12, p.purchase_price, batch_no="GRAN-OLD", expiry_date=(today - timedelta(days=9)).date(), ref_type="seed", note="DEMO expired lot", user_id=admin.id,
                 at=today - timedelta(days=200))
    inv.stock_in(p.id, whs[2].id, 15, p.purchase_price, batch_no="GRAN-SOON", expiry_date=(today + timedelta(days=12)).date(), ref_type="seed", note="DEMO soon-to-expire lot", user_id=admin.id,
                 at=today - timedelta(days=150))
    for k, v in (("demo_data", "true"), ("company_name", "StockPilot Demo Co.")):
        row = db.session.get(Setting, k)
        row.value = v
    scan_alerts()
    db.session.commit()
    print("Demo data created.\n  Password for every demo account:", PASSWORD)
    for r, u in users.items():
        print(f"  {r:18s} {u.email}")
    print(f"  Products: {Product.query.count()} | Orders: PO {PurchaseOrder.query.count()} / SO {SalesOrder.query.count()} | Stock value: {inv.valuation()}")


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        run(create_tables="--create-tables" in sys.argv, wipe="--reset" in sys.argv)
