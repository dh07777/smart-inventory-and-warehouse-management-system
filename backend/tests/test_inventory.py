from datetime import date, timedelta


def pid(client, h):
    return client.get("/api/products?q=P1", headers=h).get_json()["data"][0]["id"]


def stock_in(client, h, p, qty, cost, batch):
    return client.post("/api/inventory/stock-in", json={"product_id": p, "warehouse_id": 1, "quantity": qty, "unit_cost": cost, "batch_no": batch}, headers=h)


def test_fifo_valuation_and_cogs(client, auth):
    h = auth("admin")
    p = pid(client, h)
    assert stock_in(client, h, p, 10, 10, "B1").status_code == 201
    assert stock_in(client, h, p, 10, 20, "B2").status_code == 201
    assert client.get("/api/inventory/valuation", headers=h).get_json()["data"]["total"] == 300
    r = client.post("/api/inventory/stock-out", json={"product_id": p, "warehouse_id": 1, "quantity": 15}, headers=h).get_json()["data"]
    assert r["cogs"] == 10 * 10 + 5 * 20          # oldest layer consumed first
    assert client.get("/api/inventory/valuation", headers=h).get_json()["data"]["total"] == 100


def test_negative_stock_blocked_and_override_requires_setting(client, auth):
    h = auth("admin")
    p = pid(client, h)
    stock_in(client, h, p, 5, 10, "B1")
    r = client.post("/api/inventory/stock-out", json={"product_id": p, "warehouse_id": 1, "quantity": 6}, headers=h)
    assert r.status_code == 409
    assert client.post("/api/inventory/stock-out", json={"product_id": p, "warehouse_id": 1, "quantity": 6, "override": True}, headers=h).status_code == 403
    client.put("/api/admin/settings", json={"allow_negative_override": True}, headers=h)
    r = client.post("/api/inventory/stock-out", json={"product_id": p, "warehouse_id": 1, "quantity": 6, "override": True}, headers=h)
    assert r.status_code == 200 and r.get_json()["data"]["on_hand"] == -1
    assert client.post("/api/inventory/stock-out", json={"product_id": p, "warehouse_id": 1, "quantity": 1, "override": True}, headers=auth("inv")).status_code == 403


def test_adjust_reconcile_writeoff_and_history(client, auth):
    h = auth("admin")
    p = pid(client, h)
    stock_in(client, h, p, 20, 10, "B1")
    client.post("/api/inventory/adjust", json={"product_id": p, "warehouse_id": 1, "new_quantity": 18, "reason": "count"}, headers=h)
    rec = client.post("/api/inventory/reconcile", json={"warehouse_id": 1, "counts": [{"product_id": p, "counted": 17}]}, headers=h).get_json()["data"]
    assert rec[0]["difference"] == -1
    batch = client.get("/api/inventory/batches", headers=h).get_json()["data"][0]["batch_id"]
    assert client.post("/api/inventory/write-off", json={"product_id": p, "warehouse_id": 1, "batch_id": batch, "quantity": 2, "reason": "damaged"}, headers=h).status_code == 200
    mv = client.get("/api/inventory/movements?type=DAMAGED", headers=h).get_json()
    assert mv["meta"]["total"] == 1
    assert client.get("/api/inventory/stock", headers=h).get_json()["data"][0]["on_hand"] == 15


def test_reservation_reduces_available_and_alerts(client, auth):
    h = auth("admin")
    p = pid(client, h)
    stock_in(client, h, p, 10, 10, "B1")
    assert client.post("/api/inventory/reservations", json={"product_id": p, "warehouse_id": 1, "quantity": 8}, headers=h).status_code == 201
    assert client.post("/api/inventory/reservations", json={"product_id": p, "warehouse_id": 1, "quantity": 5}, headers=h).status_code == 409
    row = client.get("/api/inventory/stock", headers=h).get_json()["data"][0]
    assert (row["on_hand"], row["reserved"], row["available"]) == (10, 8, 2)
    alerts = client.get("/api/inventory/alerts", headers=h).get_json()["data"]
    assert alerts["low_stock"] == [] and alerts["out_of_stock"] == []
    client.post("/api/inventory/stock-in", json={"product_id": p, "warehouse_id": 1, "quantity": 1, "unit_cost": 1, "batch_no": "EXP",
                "expiry_date": (date.today() + timedelta(days=3)).isoformat()}, headers=h)
    assert len(client.get("/api/inventory/alerts", headers=h).get_json()["data"]["expiring"]) == 1
