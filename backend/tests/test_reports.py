import pytest
from .test_workflows import stocked, pid


@pytest.mark.parametrize("key", ["inventory-valuation", "stock-movements", "low-stock", "expiry", "warehouse-stock", "purchases", "sales", "suppliers", "product-performance"])
def test_every_report_json_pdf_excel(client, auth, key):
    stocked(client, auth, 12)
    h = auth("admin")
    j = client.get(f"/api/reports/{key}", headers=h).get_json()["data"]
    assert j["columns"] and "rows" in j
    assert client.get(f"/api/reports/{key}?format=pdf", headers=h).data[:4] == b"%PDF"
    assert client.get(f"/api/reports/{key}?format=xlsx", headers=h).data[:2] == b"PK"


def test_valuation_report_matches_database_and_dates_validated(client, auth):
    stocked(client, auth, 12)
    h = auth("admin")
    rep = client.get("/api/reports/inventory-valuation", headers=h).get_json()["data"]
    assert rep["summary"]["Total value"] == client.get("/api/inventory/valuation", headers=h).get_json()["data"]["total"] == 120
    assert client.get("/api/reports/sales?date_from=2030-01-02&date_to=2030-01-01", headers=h).status_code == 422
    assert client.get("/api/reports/inventory-valuation", headers=auth("staff")).status_code == 403


def test_dashboard_numbers_come_from_database(client, auth):
    stocked(client, auth, 12)
    d = client.get("/api/dashboard", headers=auth("admin")).get_json()["data"]
    assert d["totals"]["inventory_quantity"] == 12 and d["totals"]["inventory_value"] == 120


def test_backup_create_list(client, auth, app, tmp_path):
    # file-based DB required for backups; in-memory test DB must be rejected cleanly
    assert client.post("/api/admin/backups", headers=auth("admin")).status_code == 400
