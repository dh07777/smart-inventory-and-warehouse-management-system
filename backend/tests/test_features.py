import io
from .conftest import PW
from .test_workflows import pid, make_po


def H(client, email):
    r = client.post("/api/auth/login", json={"email": email, "password": PW})
    return {"Authorization": "Bearer " + r.get_json()["data"]["access_token"]}


# ---------------- purchase requests ----------------
def test_purchase_request_to_po_flow(client, auth):
    p = pid(client, auth("admin"))
    body = {"warehouse_id": 1, "priority": "high", "reason": "restock", "items": [{"product_id": p, "quantity": 5}]}
    assert client.post("/api/purchases/requests", json=body, headers=auth("staff")).status_code == 403
    r = client.post("/api/purchases/requests", json=body, headers=auth("buy")).get_json()["data"]
    assert r["status"] == "pending" and r["request_number"].startswith("PR-")
    assert client.post(f"/api/purchases/requests/{r['id']}/convert", json={"supplier_id": 1}, headers=auth("buy")).status_code == 409   # not approved yet
    assert client.post(f"/api/purchases/requests/{r['id']}/approve", headers=auth("sales")).status_code == 403
    assert client.post(f"/api/purchases/requests/{r['id']}/approve", headers=auth("admin")).status_code == 200
    out = client.post(f"/api/purchases/requests/{r['id']}/convert", json={"supplier_id": 1}, headers=auth("buy")).get_json()["data"]
    assert out["request"]["status"] == "converted" and out["request"]["po_number"] == out["purchase_order"]["po_number"]
    assert out["purchase_order"]["status"] == "approved" and out["purchase_order"]["total"] == 55.0
    assert client.post(f"/api/purchases/requests/{r['id']}/convert", json={"supplier_id": 1}, headers=auth("buy")).status_code == 409  # only once


def test_purchase_request_rejection(client, auth):
    p = pid(client, auth("admin"))
    r = client.post("/api/purchases/requests", json={"warehouse_id": 1, "items": [{"product_id": p, "quantity": 1}]}, headers=auth("buy")).get_json()["data"]
    rej = client.post(f"/api/purchases/requests/{r['id']}/reject", json={"reason": "No budget"}, headers=auth("admin")).get_json()["data"]
    assert rej["status"] == "rejected" and rej["rejection_reason"] == "No budget"
    assert client.get("/api/purchases/requests?status=rejected", headers=auth("buy")).get_json()["meta"]["total"] == 1


# ---------------- settings drive behaviour ----------------
def test_settings_defaults_applied_to_new_products(client, auth):
    h = auth("admin")
    assert client.put("/api/admin/settings", json={"default_tax_rate": 7, "default_min_stock": 9}, headers=h).status_code == 200
    assert client.put("/api/admin/settings", json={"default_min_stock": -1}, headers=h).status_code == 422
    assert client.put("/api/admin/settings", json={"default_warehouse_id": 999}, headers=h).status_code == 422
    p = client.post("/api/products", json={"sku": "DEF1", "name": "Defaulted"}, headers=h).get_json()["data"]
    assert p["tax_rate"] == 7 and p["min_stock"] == 9
    pub = client.get("/api/settings/public", headers=auth("staff")).get_json()["data"]
    assert pub["default_tax_rate"] == "7"
    assert client.get("/api/admin/settings", headers=auth("staff")).status_code == 403


# ---------------- capacity / overstock warnings ----------------
def test_capacity_and_overstock_warnings(client, auth):
    h = auth("admin")
    p = pid(client, h)
    client.put(f"/api/products/{p}", json={"max_stock": 100}, headers=h)
    r = client.post("/api/inventory/stock-in", json={"product_id": p, "warehouse_id": 2, "quantity": 600, "unit_cost": 1, "batch_no": "BIG"}, headers=h).get_json()["data"]
    assert any("over capacity" in w for w in r["warnings"]) and any("maximum stock" in w for w in r["warnings"])
    titles = [n["title"] for n in client.get("/api/notifications?per_page=50", headers=h).get_json()["data"]]
    assert any("over capacity" in t for t in titles) and any("Overstock" in t for t in titles)


# ---------------- supplier KPIs ----------------
def test_supplier_performance_metrics(client, auth):
    p = pid(client, auth("admin"))
    po = client.post("/api/purchases", json={"supplier_id": 1, "warehouse_id": 1, "expected_date": "2020-01-01", "items": [{"product_id": p, "quantity": 10}]}, headers=auth("buy")).get_json()["data"]
    client.post(f"/api/purchases/{po['id']}/approve", headers=auth("admin"))
    client.post(f"/api/purchases/{po['id']}/receive", json={"items": [{"item_id": po["items"][0]["id"], "quantity": 10}]}, headers=auth("wh"))
    st = client.get("/api/suppliers/1/profile", headers=auth("buy")).get_json()["data"]["stats"]
    assert st["on_time_pct"] == 0.0 and st["avg_delay_days"] > 0 and st["fill_rate_pct"] == 100.0
    rep = client.get("/api/reports/suppliers", headers=auth("admin")).get_json()["data"]
    assert rep["rows"][0]["fill_rate_pct"] == 100.0


# ---------------- barcodes ----------------
def test_barcode_generation_and_lookup(client, auth):
    from app.repositories.product_repository import ean13_with_check
    assert ean13_with_check("400638133393") == "4006381333931"          # known valid EAN-13
    h = auth("admin")
    assert client.post("/api/products/generate-barcodes", headers=auth("sales")).status_code == 403
    assert client.post("/api/products/generate-barcodes", headers=h).get_json()["data"]["count"] >= 1
    code = client.get("/api/products?q=P1", headers=h).get_json()["data"][0]["barcode"]
    assert len(code) == 13 and ean13_with_check(code[:12]) == code
    assert client.get(f"/api/products/lookup?code={code}", headers=auth("staff")).get_json()["data"]["sku"] == "P1"
    assert client.get("/api/products/lookup?code=P1", headers=h).status_code == 200
    assert client.get("/api/products/lookup?code=nope", headers=h).status_code == 404


# ---------------- variants, images ----------------
def test_variants_and_image_upload(client, auth):
    h = auth("admin")
    p = pid(client, h)
    assert client.post(f"/api/products/{p}/variants", json={"name": "Red", "sku": "P1-RED", "price_diff": 2}, headers=h).status_code == 201
    assert client.post(f"/api/products/{p}/variants", json={"name": "Red2", "sku": "P1-RED"}, headers=h).status_code == 409
    assert len(client.get(f"/api/products/{p}", headers=h).get_json()["data"]["variants"]) == 1
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 20
    r = client.post(f"/api/products/{p}/image", data={"image": (io.BytesIO(png), "a.png")}, headers=h, content_type="multipart/form-data")
    url = r.get_json()["data"]["image_url"]
    assert url.startswith("/uploads/") and client.get(url).status_code == 200
    bad = client.post(f"/api/products/{p}/image", data={"image": (io.BytesIO(b"x"), "evil.exe")}, headers=h, content_type="multipart/form-data")
    assert bad.status_code == 422


# ---------------- master data modules ----------------
def test_customers_suppliers_warehouses(client, auth):
    c = client.post("/api/customers", json={"code": "C9", "name": "Nine Ltd", "email": "n@x.io"}, headers=auth("sales"))
    assert c.status_code == 201
    assert client.post("/api/customers", json={"code": "C9", "name": "Dup"}, headers=auth("sales")).status_code == 409
    assert client.post("/api/customers", json={"code": "C8", "name": "No"}, headers=auth("staff")).status_code == 403
    cid = c.get_json()["data"]["id"]
    assert client.get(f"/api/customers/{cid}/profile", headers=auth("staff")).get_json()["data"]["stats"]["orders"] == 0
    assert client.get("/api/customers?q=nine", headers=auth("staff")).get_json()["meta"]["total"] == 1
    p = pid(client, auth("admin"))
    assert client.post("/api/suppliers/1/catalog", json={"product_id": p, "price": 9.5, "lead_time_days": 3}, headers=auth("buy")).status_code == 201
    assert client.get("/api/suppliers/1/catalog", headers=auth("buy")).get_json()["data"][0]["price"] == 9.5
    assert client.post("/api/warehouses/1/locations", json={"zone": "A", "rack": "R1", "shelf": "S1"}, headers=auth("wh")).status_code == 201
    assert client.get("/api/warehouses/1/locations", headers=auth("wh")).get_json()["data"][0]["label"] == "A-R1-S1"
    util = client.get("/api/warehouses/utilization", headers=auth("wh")).get_json()["data"]
    assert {u["code"] for u in util} == {"W1", "W2"}
    assert client.post("/api/warehouses", json={"code": "W9", "name": "X"}, headers=auth("sales")).status_code == 403


def test_category_tree_filter(client, auth):
    h = auth("admin")
    parent = client.post("/api/categories", json={"name": "Parent"}, headers=h).get_json()["data"]["id"]
    child = client.post("/api/categories", json={"name": "Child", "parent_id": parent}, headers=h).get_json()["data"]["id"]
    client.post("/api/products", json={"sku": "CH1", "name": "Child item", "category_id": child}, headers=h)
    res = client.get(f"/api/products?category_id={parent}", headers=h).get_json()
    assert res["meta"]["total"] == 1                                    # parent filter includes subcategory products


# ---------------- notifications, roles, audit ----------------
def test_notifications_lifecycle(client, auth):
    p = pid(client, auth("admin"))
    client.post("/api/purchases/requests", json={"warehouse_id": 1, "items": [{"product_id": p, "quantity": 1}]}, headers=auth("buy"))
    h = auth("admin")
    n = client.get("/api/notifications/unread-count", headers=h).get_json()["data"]["count"]
    assert n >= 1
    first = client.get("/api/notifications?unread=true", headers=h).get_json()["data"][0]
    assert client.post(f"/api/notifications/{first['id']}/read", headers=h).get_json()["data"]["is_read"] is True
    assert client.post(f"/api/notifications/{first['id']}/read", headers=auth("buy")).status_code == 404     # not someone else's
    client.post("/api/notifications/read-all", headers=h)
    assert client.get("/api/notifications/unread-count", headers=h).get_json()["data"]["count"] == 0
    client.put("/api/auth/me/preferences", json={"purchase": False}, headers=auth("buy"))
    assert client.get("/api/auth/me", headers=auth("buy")).get_json()["data"]["notification_prefs"]["purchase"] is False


def test_role_permissions_editable_and_audited(client, auth):
    h = auth("admin")
    roles = {r["name"]: r for r in client.get("/api/admin/roles", headers=h).get_json()["data"]}
    assert client.put(f"/api/admin/roles/{roles['Super Admin']['id']}/permissions", json={"permissions": []}, headers=h).status_code == 409
    assert client.post("/api/products", json={"sku": "S1X", "name": "x"}, headers=auth("staff")).status_code == 403
    perms = roles["Staff"]["permissions"] + ["products.manage"]
    assert client.put(f"/api/admin/roles/{roles['Staff']['id']}/permissions", json={"permissions": perms}, headers=h).status_code == 200
    assert client.post("/api/products", json={"sku": "S1X", "name": "x"}, headers=auth("staff")).status_code == 201
    logs = client.get("/api/admin/audit-logs?q=role.permissions", headers=h).get_json()
    assert logs["meta"]["total"] == 1 and logs["data"][0]["user_name"] == "Super Admin"
    assert client.get("/api/admin/audit-logs", headers=auth("staff")).status_code == 403


def test_cannot_remove_last_super_admin_or_self_lockout(client, auth):
    h = auth("admin")
    me = client.get("/api/auth/me", headers=h).get_json()["data"]
    assert client.put(f"/api/admin/users/{me['id']}", json={"is_active": False}, headers=h).status_code == 409
    staff_role = [r for r in client.get("/api/admin/roles", headers=h).get_json()["data"] if r["name"] == "Staff"][0]["id"]
    assert client.put(f"/api/admin/users/{me['id']}", json={"role_id": staff_role}, headers=h).status_code == 409


# ---------------- platform behaviour ----------------
def test_openapi_security_headers_and_error_shape(client, auth):
    spec = client.get("/api/openapi.json").get_json()
    assert "/api/products" in spec["paths"] and "/api/purchases/requests" in spec["paths"]
    assert "security" in spec["paths"]["/api/products"]["get"] and "security" not in spec["paths"]["/api/auth/login"]["post"]
    r = client.get("/api/health")
    assert r.headers["X-Content-Type-Options"] == "nosniff" and r.headers["X-Frame-Options"] == "DENY"
    e = client.get("/api/products/99999", headers=auth("admin"))
    assert e.status_code == 404 and e.get_json()["success"] is False and "message" in e.get_json()["error"]
    assert client.post("/api/products", data="not json", headers=auth("admin")).status_code == 400


def test_pagination_meta_and_per_page_cap(client, auth):
    h = auth("admin")
    for i in range(12):
        client.post("/api/products", json={"sku": f"PG{i}", "name": f"Page item {i}"}, headers=h)
    r = client.get("/api/products?per_page=5&page=2&q=Page", headers=h).get_json()
    assert r["meta"] == {"page": 2, "per_page": 5, "total": 12, "pages": 3} and len(r["data"]) == 5


# ---------------- backup / restore on a real file database ----------------
def test_backup_and_restore_roundtrip(file_client):
    h = H(file_client, "admin@t.io")
    file_client.post("/api/products", json={"sku": "KEEP", "name": "Keep me"}, headers=h)
    name = file_client.post("/api/admin/backups", headers=h).get_json()["data"]["name"]
    file_client.post("/api/products", json={"sku": "LOSE", "name": "Lose me"}, headers=h)
    assert file_client.get("/api/products?q=Lose", headers=h).get_json()["meta"]["total"] == 1
    assert file_client.get(f"/api/admin/backups/{name}/download", headers=h).status_code == 200
    assert file_client.post(f"/api/admin/backups/{name}/restore", headers=h).status_code == 200
    assert file_client.get("/api/products?q=Lose", headers=h).get_json()["meta"]["total"] == 0
    assert file_client.get("/api/products?q=Keep", headers=h).get_json()["meta"]["total"] == 1
    names = [b["name"] for b in file_client.get("/api/admin/backups", headers=h).get_json()["data"]]
    assert any("prerestore" in n for n in names)                         # automatic safety copy
    assert file_client.post("/api/admin/backups/../../etc/passwd/restore", headers=h).status_code == 404
    assert file_client.post("/api/admin/backups/evil.db/restore", headers=h).status_code == 400
