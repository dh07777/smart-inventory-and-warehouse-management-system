import io


def test_product_crud_search_and_filters(client, auth):
    h = auth("admin")
    r = client.post("/api/products", json={"sku": "P2", "name": "Gadget", "barcode": "123", "purchase_price": 5, "selling_price": 9}, headers=h)
    assert r.status_code == 201
    assert client.post("/api/products", json={"sku": "P2", "name": "Dup"}, headers=h).status_code == 409
    assert client.post("/api/products", json={"sku": "P3", "name": "Bad", "tax_rate": 500}, headers=h).status_code == 422
    res = client.get("/api/products?q=gadg&sort=name&order=asc", headers=h).get_json()
    assert res["meta"]["total"] == 1 and res["data"][0]["stock_status"] == "out"
    pid = r.get_json()["data"]["id"]
    assert client.put(f"/api/products/{pid}", json={"name": "Gadget 2"}, headers=h).get_json()["data"]["name"] == "Gadget 2"
    assert client.delete(f"/api/products/{pid}", headers=h).status_code == 200


def test_csv_import_export(client, auth):
    h = auth("admin")
    csv = "sku,name,category,purchase_price,selling_price\nIMP1,Imported One,Gadgets,3,6\n,Missing sku,,1,2\n"
    r = client.post("/api/products/import", data={"file": (io.BytesIO(csv.encode()), "p.csv")}, headers=h, content_type="multipart/form-data")
    d = r.get_json()["data"]
    assert d["created"] == 1 and len(d["errors"]) == 1
    exp = client.get("/api/products/export?format=csv", headers=h)
    assert b"IMP1" in exp.data
    assert client.get("/api/products/export?format=xlsx", headers=h).status_code == 200
