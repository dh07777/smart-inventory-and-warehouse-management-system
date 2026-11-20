import pytest


def pid(client, h):
    return client.get("/api/products?q=P1", headers=h).get_json()["data"][0]["id"]


def make_po(client, auth, qty=10):
    r = client.post("/api/purchases", json={"supplier_id": 1, "warehouse_id": 1, "items": [{"product_id": pid(client, auth("admin")), "quantity": qty}]}, headers=auth("buy"))
    assert r.status_code == 201, r.get_json()
    return r.get_json()["data"]


def test_purchase_flow_partial_receipt_and_duplicates(client, auth):
    po = make_po(client, auth, 10)
    assert po["status"] == "pending_approval" and po["total"] == 110.0   # 10 x 10 + 10% tax
    assert client.post(f"/api/purchases/{po['id']}/receive", json={"items": [{"item_id": po["items"][0]["id"], "quantity": 1}]}, headers=auth("wh")).status_code == 409
    assert client.post(f"/api/purchases/{po['id']}/approve", headers=auth("sales")).status_code == 403
    assert client.post(f"/api/purchases/{po['id']}/approve", headers=auth("admin")).status_code == 200
    item = po["items"][0]["id"]
    r = client.post(f"/api/purchases/{po['id']}/receive", json={"items": [{"item_id": item, "quantity": 4}], "idempotency_key": "k1"}, headers=auth("wh"))
    assert r.get_json()["data"]["status"] == "partially_received"
    dup = client.post(f"/api/purchases/{po['id']}/receive", json={"items": [{"item_id": item, "quantity": 4}], "idempotency_key": "k1"}, headers=auth("wh"))
    assert dup.status_code == 409                                           # duplicate processing prevented
    assert client.post(f"/api/purchases/{po['id']}/receive", json={"items": [{"item_id": item, "quantity": 7}]}, headers=auth("wh")).status_code == 409
    r = client.post(f"/api/purchases/{po['id']}/receive", json={"items": [{"item_id": item, "quantity": 6}]}, headers=auth("wh"))
    assert r.get_json()["data"]["status"] == "received"
    assert client.get("/api/inventory/stock", headers=auth("admin")).get_json()["data"][0]["on_hand"] == 10
    assert client.post(f"/api/purchases/{po['id']}/invoice", headers=auth("buy")).status_code == 200
    pdf = client.get(f"/api/purchases/{po['id']}/invoice.pdf", headers=auth("buy"))
    assert pdf.data[:4] == b"%PDF"
    sup = client.get("/api/suppliers/1/profile", headers=auth("buy")).get_json()["data"]["stats"]
    assert sup["outstanding"] == 110.0
    assert client.post("/api/suppliers/1/payments", json={"amount": 500}, headers=auth("buy")).status_code == 409
    assert client.post("/api/suppliers/1/payments", json={"amount": 110}, headers=auth("buy")).status_code == 201


def stocked(client, auth, qty=20):
    po = make_po(client, auth, qty)
    client.post(f"/api/purchases/{po['id']}/approve", headers=auth("admin"))
    client.post(f"/api/purchases/{po['id']}/receive", json={"items": [{"item_id": po["items"][0]["id"], "quantity": qty}]}, headers=auth("wh"))


def test_sales_flow_reserve_dispatch_return(client, auth):
    stocked(client, auth, 20)
    p = pid(client, auth("admin"))
    so = client.post("/api/sales", json={"customer_id": 1, "warehouse_id": 1, "items": [{"product_id": p, "quantity": 5}]}, headers=auth("sales")).get_json()["data"]
    assert so["total"] == 110.0
    assert client.post(f"/api/sales/{so['id']}/dispatch", json={}, headers=auth("sales")).status_code == 409      # must confirm first
    assert client.post(f"/api/sales/{so['id']}/confirm", headers=auth("sales")).status_code == 200
    assert client.get("/api/inventory/stock", headers=auth("admin")).get_json()["data"][0]["available"] == 15
    d = client.post(f"/api/sales/{so['id']}/dispatch", json={"carrier": "DHL", "idempotency_key": "d1"}, headers=auth("wh")).get_json()["data"]
    assert d["status"] == "dispatched" and d["cogs_total"] == 50.0
    assert client.post(f"/api/sales/{so['id']}/dispatch", json={"idempotency_key": "d1"}, headers=auth("wh")).status_code == 409
    assert client.get("/api/inventory/stock", headers=auth("admin")).get_json()["data"][0]["on_hand"] == 15
    ret = client.post(f"/api/sales/{so['id']}/returns", json={"reason": "wrong item", "items": [{"product_id": p, "quantity": 2}]}, headers=auth("sales")).get_json()["data"]
    assert ret["refund_amount"] == 44.0
    assert client.post(f"/api/sales/{so['id']}/returns", json={"reason": "x", "items": [{"product_id": p, "quantity": 4}]}, headers=auth("sales")).status_code == 409
    assert client.post(f"/api/sales/returns/{ret['id']}/approve", headers=auth("sales")).status_code == 200
    assert client.get("/api/inventory/stock", headers=auth("admin")).get_json()["data"][0]["on_hand"] == 17
    assert client.get(f"/api/sales/{so['id']}/invoice.pdf", headers=auth("sales")).data[:4] == b"%PDF"


def test_cannot_oversell(client, auth):
    stocked(client, auth, 3)
    p = pid(client, auth("admin"))
    so = client.post("/api/sales", json={"customer_id": 1, "warehouse_id": 1, "items": [{"product_id": p, "quantity": 5}]}, headers=auth("sales")).get_json()["data"]
    assert client.post(f"/api/sales/{so['id']}/confirm", headers=auth("sales")).status_code == 409


def test_transfer_flow_with_discrepancy(client, auth):
    stocked(client, auth, 20)
    p = pid(client, auth("admin"))
    t = client.post("/api/transfers", json={"from_warehouse_id": 1, "to_warehouse_id": 2, "items": [{"product_id": p, "quantity": 8}]}, headers=auth("wh")).get_json()["data"]
    assert client.post("/api/transfers", json={"from_warehouse_id": 1, "to_warehouse_id": 1, "items": [{"product_id": p, "quantity": 1}]}, headers=auth("wh")).status_code == 422
    assert client.post(f"/api/transfers/{t['id']}/dispatch", json={}, headers=auth("wh")).status_code == 409   # not approved yet
    assert client.post(f"/api/transfers/{t['id']}/approve", headers=auth("wh")).status_code == 200
    assert client.post(f"/api/transfers/{t['id']}/dispatch", json={"items": [{"item_id": t["items"][0]["id"], "quantity": 6}]}, headers=auth("wh")).status_code == 200
    rows = {r["warehouse_id"]: r["on_hand"] for r in client.get("/api/inventory/stock", headers=auth("admin")).get_json()["data"]}
    assert rows == {1: 14}                                                     # 6 are in transit, not yet at destination
    r = client.post(f"/api/transfers/{t['id']}/receive", json={"items": [{"item_id": t["items"][0]["id"], "received_qty": 5}], "note": "1 broken"}, headers=auth("wh")).get_json()["data"]
    assert r["status"] == "received" and r["discrepancy_status"] == "open"
    rows = {r["warehouse_id"]: r["on_hand"] for r in client.get("/api/inventory/stock", headers=auth("admin")).get_json()["data"]}
    assert rows == {1: 14, 2: 5}
    assert client.post(f"/api/transfers/{t['id']}/resolve", json={"note": "Insurance claim filed"}, headers=auth("wh")).status_code == 200
