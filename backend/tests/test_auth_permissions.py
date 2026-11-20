from .conftest import PW


def test_register_login_and_me(client):
    r = client.post("/api/auth/register", json={"name": "New User", "email": "new@t.io", "password": "Abcdef12"})
    assert r.status_code == 201
    assert client.post("/api/auth/register", json={"name": "New User", "email": "new@t.io", "password": "Abcdef12"}).status_code == 409
    assert client.post("/api/auth/register", json={"name": "X Y", "email": "w@t.io", "password": "weak"}).status_code == 422
    tok = client.post("/api/auth/login", json={"email": "new@t.io", "password": "Abcdef12"}).get_json()["data"]["access_token"]
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {tok}"}).get_json()["data"]
    assert me["role_name"] == "Staff" and "products.manage" not in me["permissions"]


def test_login_failure_and_lockout(client):
    for _ in range(5):
        assert client.post("/api/auth/login", json={"email": "admin@t.io", "password": "bad"}).status_code == 401
    assert client.post("/api/auth/login", json={"email": "admin@t.io", "password": PW}).status_code == 429


def test_protected_routes_require_token(client):
    assert client.get("/api/products").status_code == 401


def test_rbac_enforced_on_server(client, auth):
    body = {"sku": "X1", "name": "Blocked"}
    assert client.post("/api/products", json=body, headers=auth("staff")).status_code == 403
    assert client.post("/api/products", json=body, headers=auth("sales")).status_code == 403
    assert client.post("/api/products", json=body, headers=auth("inv")).status_code == 201
    assert client.get("/api/admin/users", headers=auth("inv")).status_code == 403
    assert client.get("/api/admin/users", headers=auth("admin")).status_code == 200


def test_logout_revokes_token(client, auth):
    h = auth("admin")
    assert client.post("/api/auth/logout", json={}, headers=h).status_code == 200
    assert client.get("/api/auth/me", headers=h).status_code == 401


def test_password_reset_flow(client):
    r = client.post("/api/auth/forgot-password", json={"email": "staff@t.io"}).get_json()["data"]
    token = r["dev_reset_link"].split("token=")[1].split("&")[0]
    assert client.post("/api/auth/reset-password", json={"email": "staff@t.io", "token": "wrong", "password": "Newpass123"}).status_code == 400
    assert client.post("/api/auth/reset-password", json={"email": "staff@t.io", "token": token, "password": "Newpass123"}).status_code == 200
    assert client.post("/api/auth/login", json={"email": "staff@t.io", "password": "Newpass123"}).status_code == 200


def test_deactivated_user_cannot_login(client, auth):
    uid = client.get("/api/admin/users?q=staff@t.io", headers=auth("admin")).get_json()["data"][0]["id"]
    assert client.put(f"/api/admin/users/{uid}", json={"is_active": False}, headers=auth("admin")).status_code == 200
    assert client.post("/api/auth/login", json={"email": "staff@t.io", "password": PW}).status_code == 403
