import os, sys
import pytest
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from app import create_app
from app.config import TestConfig
from app.extensions import db
from app.bootstrap import seed_core
from app.models import User, Category, Supplier, Warehouse, Product, Customer

PW = "Test@12345"


def build_app(tmp_path, file_db=False):
    class Cfg(TestConfig):
        UPLOAD_FOLDER = str(tmp_path / "up")
        BACKUP_FOLDER = str(tmp_path / "bk")
        if file_db:
            SQLALCHEMY_DATABASE_URI = "sqlite:///" + str(tmp_path / "test.db").replace("\\", "/")
    app = create_app(Cfg)
    with app.app_context():  # context is closed before the tests run so flask.g never leaks between requests
        db.create_all()
        roles = seed_core()
        for email, role in [("admin@t.io", "Super Admin"), ("wh@t.io", "Warehouse Manager"), ("inv@t.io", "Inventory Manager"),
                            ("buy@t.io", "Purchase Manager"), ("sales@t.io", "Sales Manager"), ("staff@t.io", "Staff")]:
            u = User(name=role, email=email, role_id=roles[role].id)
            u.set_password(PW)
            db.session.add(u)
        cat = Category(name="General")
        db.session.add(cat)
        db.session.flush()
        sup = Supplier(code="S1", name="Supplier One")
        db.session.add_all([sup, Warehouse(code="W1", name="Main", capacity=1000), Warehouse(code="W2", name="Second", capacity=500),
                            Customer(code="C1", name="Customer One")])
        db.session.flush()
        db.session.add(Product(sku="P1", name="Widget", category_id=cat.id, supplier_id=sup.id, purchase_price=10, selling_price=20, tax_rate=10, min_stock=5))
        db.session.commit()
        db.session.remove()
    return app


@pytest.fixture()
def app(tmp_path):
    app = build_app(tmp_path)
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def file_app(tmp_path):
    app = build_app(tmp_path, file_db=True)
    yield app
    with app.app_context():
        db.session.remove()
        db.engine.dispose()


@pytest.fixture()
def file_client(file_app):
    return file_app.test_client()


@pytest.fixture()
def client(app):
    return app.test_client()


def _login(client, email):
    r = client.post("/api/auth/login", json={"email": email, "password": PW})
    assert r.status_code == 200, r.get_json()
    return {"Authorization": "Bearer " + r.get_json()["data"]["access_token"]}


@pytest.fixture()
def auth(client):
    cache = {}
    def get(role="admin"):
        if role not in cache:
            cache[role] = _login(client, f"{role}@t.io")
        return cache[role]
    return get


def api(client, method, url, headers, json=None, **kw):
    r = getattr(client, method)(url, json=json, headers=headers, **kw)
    return r
