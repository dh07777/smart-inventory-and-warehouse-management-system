"""SQLAlchemy models for StockPilot (normalized SQLite schema)."""
import json
from datetime import datetime, date
from werkzeug.security import generate_password_hash, check_password_hash
from .extensions import db
from .utils import now


class Serializable:
    hidden = ()

    def to_dict(self):
        d = {}
        for c in self.__table__.columns:
            if c.name in self.hidden:
                continue
            v = getattr(self, c.name)
            d[c.name] = v.isoformat() if isinstance(v, (datetime, date)) else v
        d.update(self.extra())
        return d

    def extra(self):
        return {}


class Stamps:
    created_at = db.Column(db.DateTime, default=now, nullable=False)
    updated_at = db.Column(db.DateTime, default=now, onupdate=now, nullable=False)


role_permissions = db.Table(
    "role_permissions",
    db.Column("role_id", db.Integer, db.ForeignKey("roles.id"), primary_key=True),
    db.Column("permission_id", db.Integer, db.ForeignKey("permissions.id"), primary_key=True),
)


class Permission(Serializable, db.Model):
    __tablename__ = "permissions"
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(64), unique=True, nullable=False)
    description = db.Column(db.String(200))


class Role(Serializable, db.Model):
    __tablename__ = "roles"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True, nullable=False)
    description = db.Column(db.String(200))
    permissions = db.relationship("Permission", secondary=role_permissions, lazy="joined")

    def codes(self):
        return {p.code for p in self.permissions}

    def extra(self):
        return {"permissions": sorted(self.codes())}


class User(Serializable, Stamps, db.Model):
    __tablename__ = "users"
    hidden = ("password_hash", "reset_token_hash", "reset_expires")
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(160), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    phone = db.Column(db.String(40))
    role_id = db.Column(db.Integer, db.ForeignKey("roles.id"), nullable=False, index=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    last_login = db.Column(db.DateTime)
    reset_token_hash = db.Column(db.String(128))
    reset_expires = db.Column(db.DateTime)
    notification_prefs = db.Column(db.Text)
    role = db.relationship("Role", lazy="joined")

    def set_password(self, pw):
        self.password_hash = generate_password_hash(pw)

    def check_password(self, pw):
        return check_password_hash(self.password_hash, pw)

    def has_permission(self, code):
        return code in self.role.codes()

    def prefs(self):
        try:
            return json.loads(self.notification_prefs) if self.notification_prefs else {}
        except ValueError:
            return {}

    def extra(self):
        return {"role_name": self.role.name if self.role else None}


class LoginHistory(Serializable, db.Model):
    __tablename__ = "login_history"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), index=True)
    email = db.Column(db.String(160), index=True)
    success = db.Column(db.Boolean, default=False)
    ip_address = db.Column(db.String(64))
    user_agent = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=now, index=True)


class TokenBlocklist(db.Model):
    __tablename__ = "token_blocklist"
    id = db.Column(db.Integer, primary_key=True)
    jti = db.Column(db.String(64), unique=True, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=now)


class Category(Serializable, Stamps, db.Model):
    __tablename__ = "categories"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey("categories.id"), index=True)
    description = db.Column(db.String(300))
    __table_args__ = (db.UniqueConstraint("name", "parent_id", name="uq_category_name_parent"),)
    parent = db.relationship("Category", remote_side=[id], lazy="joined")

    def extra(self):
        return {"parent_name": self.parent.name if self.parent else None}


class Supplier(Serializable, Stamps, db.Model):
    __tablename__ = "suppliers"
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(32), unique=True, nullable=False)
    name = db.Column(db.String(160), nullable=False, index=True)
    contact_person = db.Column(db.String(120))
    email = db.Column(db.String(160))
    phone = db.Column(db.String(40))
    address = db.Column(db.String(300))
    city = db.Column(db.String(80))
    country = db.Column(db.String(80))
    tax_no = db.Column(db.String(60))
    payment_terms = db.Column(db.String(80))
    rating = db.Column(db.Float, default=0)
    notes = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True, nullable=False)


class SupplierProduct(Serializable, db.Model):
    __tablename__ = "supplier_products"
    id = db.Column(db.Integer, primary_key=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey("suppliers.id"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False, index=True)
    supplier_sku = db.Column(db.String(80))
    price = db.Column(db.Float, default=0)
    lead_time_days = db.Column(db.Integer, default=7)
    __table_args__ = (db.UniqueConstraint("supplier_id", "product_id", name="uq_supplier_product"),)
    product = db.relationship("Product", lazy="joined")

    def extra(self):
        return {"product_name": self.product.name, "sku": self.product.sku}


class SupplierPayment(Serializable, db.Model):
    __tablename__ = "supplier_payments"
    id = db.Column(db.Integer, primary_key=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey("suppliers.id"), nullable=False, index=True)
    purchase_order_id = db.Column(db.Integer, db.ForeignKey("purchase_orders.id"), index=True)
    amount = db.Column(db.Float, nullable=False)
    method = db.Column(db.String(40), default="bank_transfer")
    reference = db.Column(db.String(80))
    note = db.Column(db.String(300))
    paid_at = db.Column(db.DateTime, default=now)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"))


class Product(Serializable, Stamps, db.Model):
    __tablename__ = "products"
    id = db.Column(db.Integer, primary_key=True)
    sku = db.Column(db.String(64), unique=True, nullable=False, index=True)
    barcode = db.Column(db.String(64), unique=True, index=True)
    name = db.Column(db.String(200), nullable=False, index=True)
    description = db.Column(db.Text)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), index=True)
    brand = db.Column(db.String(100))
    supplier_id = db.Column(db.Integer, db.ForeignKey("suppliers.id"), index=True)
    unit = db.Column(db.String(20), default="pcs")
    purchase_price = db.Column(db.Float, default=0, nullable=False)
    selling_price = db.Column(db.Float, default=0, nullable=False)
    tax_rate = db.Column(db.Float, default=0, nullable=False)
    discount = db.Column(db.Float, default=0, nullable=False)
    min_stock = db.Column(db.Integer, default=0, nullable=False)
    max_stock = db.Column(db.Integer, default=0, nullable=False)
    reorder_qty = db.Column(db.Integer, default=0, nullable=False)
    image_url = db.Column(db.String(500))
    status = db.Column(db.String(20), default="active", nullable=False, index=True)
    is_demo = db.Column(db.Boolean, default=False)
    category = db.relationship("Category", lazy="joined")
    supplier = db.relationship("Supplier", lazy="joined")
    variants = db.relationship("ProductVariant", cascade="all, delete-orphan", lazy="select")

    def extra(self):
        return {"category_name": self.category.name if self.category else None,
                "supplier_name": self.supplier.name if self.supplier else None}


class ProductVariant(Serializable, db.Model):
    __tablename__ = "product_variants"
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    sku = db.Column(db.String(64), unique=True, nullable=False)
    attributes = db.Column(db.String(300))
    price_diff = db.Column(db.Float, default=0)


class Warehouse(Serializable, Stamps, db.Model):
    __tablename__ = "warehouses"
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(32), unique=True, nullable=False)
    name = db.Column(db.String(160), nullable=False)
    address = db.Column(db.String(300))
    city = db.Column(db.String(80))
    phone = db.Column(db.String(40))
    email = db.Column(db.String(160))
    manager_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    capacity = db.Column(db.Integer, default=0, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    manager = db.relationship("User", lazy="joined")

    def extra(self):
        return {"manager_name": self.manager.name if self.manager else None}


class WarehouseLocation(Serializable, db.Model):
    __tablename__ = "warehouse_locations"
    id = db.Column(db.Integer, primary_key=True)
    warehouse_id = db.Column(db.Integer, db.ForeignKey("warehouses.id"), nullable=False, index=True)
    zone = db.Column(db.String(40), nullable=False)
    rack = db.Column(db.String(40))
    shelf = db.Column(db.String(40))
    bin = db.Column(db.String(40))
    __table_args__ = (db.UniqueConstraint("warehouse_id", "zone", "rack", "shelf", "bin", name="uq_location"),)

    def extra(self):
        return {"label": "-".join(x for x in [self.zone, self.rack, self.shelf, self.bin] if x)}


class Batch(Serializable, db.Model):
    __tablename__ = "batches"
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False, index=True)
    batch_no = db.Column(db.String(64), nullable=False)
    mfg_date = db.Column(db.Date)
    expiry_date = db.Column(db.Date, index=True)
    unit_cost = db.Column(db.Float, default=0, nullable=False)
    received_at = db.Column(db.DateTime, default=now, nullable=False, index=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey("suppliers.id"))
    __table_args__ = (db.UniqueConstraint("product_id", "batch_no", name="uq_batch"),)


class Inventory(Serializable, db.Model):
    """One row per (product, warehouse, batch) = one FIFO cost layer."""
    __tablename__ = "inventory"
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False, index=True)
    warehouse_id = db.Column(db.Integer, db.ForeignKey("warehouses.id"), nullable=False, index=True)
    batch_id = db.Column(db.Integer, db.ForeignKey("batches.id"), nullable=False, index=True)
    location_id = db.Column(db.Integer, db.ForeignKey("warehouse_locations.id"))
    quantity = db.Column(db.Integer, default=0, nullable=False)
    updated_at = db.Column(db.DateTime, default=now, onupdate=now)
    __table_args__ = (db.UniqueConstraint("product_id", "warehouse_id", "batch_id", name="uq_inventory_layer"),)
    batch = db.relationship("Batch", lazy="joined")
    product = db.relationship("Product", lazy="joined")
    warehouse = db.relationship("Warehouse", lazy="joined")

    def extra(self):
        return {"batch_no": self.batch.batch_no, "expiry_date": self.batch.expiry_date.isoformat() if self.batch.expiry_date else None,
                "unit_cost": self.batch.unit_cost, "value": round(self.quantity * self.batch.unit_cost, 2),
                "product_name": self.product.name, "sku": self.product.sku, "warehouse_name": self.warehouse.name}


class Reservation(Serializable, db.Model):
    __tablename__ = "reservations"
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False, index=True)
    warehouse_id = db.Column(db.Integer, db.ForeignKey("warehouses.id"), nullable=False, index=True)
    quantity = db.Column(db.Integer, nullable=False)
    reference_type = db.Column(db.String(40), index=True)
    reference_id = db.Column(db.Integer, index=True)
    note = db.Column(db.String(300))
    status = db.Column(db.String(20), default="active", index=True)  # active|released|consumed
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=now)
    product = db.relationship("Product", lazy="joined")
    warehouse = db.relationship("Warehouse", lazy="joined")

    def extra(self):
        return {"product_name": self.product.name, "sku": self.product.sku, "warehouse_name": self.warehouse.name}


class StockMovement(Serializable, db.Model):
    __tablename__ = "stock_movements"
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False, index=True)
    warehouse_id = db.Column(db.Integer, db.ForeignKey("warehouses.id"), nullable=False, index=True)
    batch_id = db.Column(db.Integer, db.ForeignKey("batches.id"))
    movement_type = db.Column(db.String(24), nullable=False, index=True)
    quantity = db.Column(db.Integer, nullable=False)  # signed
    unit_cost = db.Column(db.Float, default=0)
    reference_type = db.Column(db.String(40))
    reference_id = db.Column(db.Integer)
    note = db.Column(db.String(300))
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=now, nullable=False, index=True)
    product = db.relationship("Product", lazy="joined")
    warehouse = db.relationship("Warehouse", lazy="joined")
    batch = db.relationship("Batch", lazy="joined")
    user = db.relationship("User", lazy="joined")

    def extra(self):
        return {"product_name": self.product.name, "sku": self.product.sku, "warehouse_name": self.warehouse.name,
                "batch_no": self.batch.batch_no if self.batch else None, "user_name": self.user.name if self.user else None}


class PurchaseOrder(Serializable, Stamps, db.Model):
    __tablename__ = "purchase_orders"
    id = db.Column(db.Integer, primary_key=True)
    po_number = db.Column(db.String(32), unique=True, nullable=False)
    supplier_id = db.Column(db.Integer, db.ForeignKey("suppliers.id"), nullable=False, index=True)
    warehouse_id = db.Column(db.Integer, db.ForeignKey("warehouses.id"), nullable=False)
    status = db.Column(db.String(24), default="pending_approval", nullable=False, index=True)
    order_date = db.Column(db.DateTime, default=now, index=True)
    expected_date = db.Column(db.Date)
    received_at = db.Column(db.DateTime)
    notes = db.Column(db.Text)
    subtotal = db.Column(db.Float, default=0)
    tax_total = db.Column(db.Float, default=0)
    total = db.Column(db.Float, default=0)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    approved_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    approved_at = db.Column(db.DateTime)
    rejection_reason = db.Column(db.String(300))
    invoice_no = db.Column(db.String(40), unique=True)
    invoice_date = db.Column(db.DateTime)
    is_demo = db.Column(db.Boolean, default=False)
    supplier = db.relationship("Supplier", lazy="joined")
    warehouse = db.relationship("Warehouse", lazy="joined")
    items = db.relationship("PurchaseOrderItem", cascade="all, delete-orphan", lazy="selectin")

    def recalc(self):
        self.subtotal = round(sum(i.quantity * i.unit_price for i in self.items), 2)
        self.tax_total = round(sum(i.quantity * i.unit_price * i.tax_rate / 100 for i in self.items), 2)
        self.total = round(self.subtotal + self.tax_total, 2)

    def paid(self):
        return round(db.session.query(db.func.coalesce(db.func.sum(SupplierPayment.amount), 0))
                     .filter(SupplierPayment.purchase_order_id == self.id).scalar(), 2)

    def extra(self):
        q = sum(i.quantity for i in self.items)
        r = sum(i.received_qty for i in self.items)
        return {"supplier_name": self.supplier.name, "warehouse_name": self.warehouse.name, "item_count": len(self.items),
                "received_pct": round(r * 100 / q, 1) if q else 0, "paid": self.paid()}

    def detail(self):
        d = self.to_dict()
        d["items"] = [i.to_dict() for i in self.items]
        return d


class PurchaseOrderItem(Serializable, db.Model):
    __tablename__ = "purchase_order_items"
    id = db.Column(db.Integer, primary_key=True)
    purchase_order_id = db.Column(db.Integer, db.ForeignKey("purchase_orders.id"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False, index=True)
    quantity = db.Column(db.Integer, nullable=False)
    received_qty = db.Column(db.Integer, default=0, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)
    tax_rate = db.Column(db.Float, default=0)
    product = db.relationship("Product", lazy="joined")

    def extra(self):
        return {"product_name": self.product.name, "sku": self.product.sku, "unit": self.product.unit,
                "line_total": round(self.quantity * self.unit_price * (1 + self.tax_rate / 100), 2)}


class PurchaseRequest(Serializable, Stamps, db.Model):
    """Internal request to buy stock. Flow: pending -> approved -> converted (to a purchase order) | rejected | cancelled."""
    __tablename__ = "purchase_requests"
    id = db.Column(db.Integer, primary_key=True)
    request_number = db.Column(db.String(32), unique=True, nullable=False)
    warehouse_id = db.Column(db.Integer, db.ForeignKey("warehouses.id"), nullable=False)
    status = db.Column(db.String(20), default="pending", nullable=False, index=True)
    priority = db.Column(db.String(10), default="normal")
    reason = db.Column(db.String(300))
    needed_by = db.Column(db.Date)
    requested_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    reviewed_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    reviewed_at = db.Column(db.DateTime)
    rejection_reason = db.Column(db.String(300))
    purchase_order_id = db.Column(db.Integer, db.ForeignKey("purchase_orders.id"))
    is_demo = db.Column(db.Boolean, default=False)
    warehouse = db.relationship("Warehouse", lazy="joined")
    requester = db.relationship("User", foreign_keys=[requested_by], lazy="joined")
    purchase_order = db.relationship("PurchaseOrder", lazy="joined")
    items = db.relationship("PurchaseRequestItem", cascade="all, delete-orphan", lazy="selectin")

    def extra(self):
        return {"warehouse_name": self.warehouse.name, "requester_name": self.requester.name if self.requester else None,
                "item_count": len(self.items), "po_number": self.purchase_order.po_number if self.purchase_order else None}

    def detail(self):
        d = self.to_dict()
        d["items"] = [i.to_dict() for i in self.items]
        return d


class PurchaseRequestItem(Serializable, db.Model):
    __tablename__ = "purchase_request_items"
    id = db.Column(db.Integer, primary_key=True)
    purchase_request_id = db.Column(db.Integer, db.ForeignKey("purchase_requests.id"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    note = db.Column(db.String(200))
    product = db.relationship("Product", lazy="joined")

    def extra(self):
        return {"product_name": self.product.name, "sku": self.product.sku, "unit": self.product.unit}


class Customer(Serializable, Stamps, db.Model):
    __tablename__ = "customers"
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(32), unique=True, nullable=False)
    name = db.Column(db.String(160), nullable=False, index=True)
    company = db.Column(db.String(160))
    email = db.Column(db.String(160))
    phone = db.Column(db.String(40))
    address = db.Column(db.String(300))
    city = db.Column(db.String(80))
    notes = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True, nullable=False)


class SalesOrder(Serializable, Stamps, db.Model):
    __tablename__ = "sales_orders"
    id = db.Column(db.Integer, primary_key=True)
    so_number = db.Column(db.String(32), unique=True, nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=False, index=True)
    warehouse_id = db.Column(db.Integer, db.ForeignKey("warehouses.id"), nullable=False)
    status = db.Column(db.String(24), default="pending", nullable=False, index=True)
    order_date = db.Column(db.DateTime, default=now, index=True)
    subtotal = db.Column(db.Float, default=0)
    discount_total = db.Column(db.Float, default=0)
    tax_total = db.Column(db.Float, default=0)
    total = db.Column(db.Float, default=0)
    paid_amount = db.Column(db.Float, default=0)
    refunded_amount = db.Column(db.Float, default=0)
    cogs_total = db.Column(db.Float, default=0)
    carrier = db.Column(db.String(80))
    tracking_no = db.Column(db.String(80))
    dispatched_at = db.Column(db.DateTime)
    delivered_at = db.Column(db.DateTime)
    notes = db.Column(db.Text)
    invoice_no = db.Column(db.String(40), unique=True)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    is_demo = db.Column(db.Boolean, default=False)
    customer = db.relationship("Customer", lazy="joined")
    warehouse = db.relationship("Warehouse", lazy="joined")
    items = db.relationship("SalesOrderItem", cascade="all, delete-orphan", lazy="selectin")

    def recalc(self):
        sub = disc = tax = 0
        for i in self.items:
            line = i.quantity * i.unit_price
            d = line * i.discount / 100
            sub += line
            disc += d
            tax += (line - d) * i.tax_rate / 100
        self.subtotal, self.discount_total, self.tax_total = round(sub, 2), round(disc, 2), round(tax, 2)
        self.total = round(sub - disc + tax, 2)

    def payment_status(self):
        if self.paid_amount <= 0:
            return "unpaid"
        return "paid" if self.paid_amount + 0.005 >= self.total - self.refunded_amount else "partial"

    def extra(self):
        return {"customer_name": self.customer.name, "warehouse_name": self.warehouse.name, "item_count": len(self.items),
                "payment_status": self.payment_status()}

    def detail(self):
        d = self.to_dict()
        d["items"] = [i.to_dict() for i in self.items]
        return d


class SalesOrderItem(Serializable, db.Model):
    __tablename__ = "sales_order_items"
    id = db.Column(db.Integer, primary_key=True)
    sales_order_id = db.Column(db.Integer, db.ForeignKey("sales_orders.id"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False, index=True)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)
    discount = db.Column(db.Float, default=0)
    tax_rate = db.Column(db.Float, default=0)
    cogs = db.Column(db.Float, default=0)
    product = db.relationship("Product", lazy="joined")

    def extra(self):
        line = self.quantity * self.unit_price * (1 - self.discount / 100)
        return {"product_name": self.product.name, "sku": self.product.sku,
                "line_total": round(line * (1 + self.tax_rate / 100), 2)}


class SalesReturn(Serializable, Stamps, db.Model):
    __tablename__ = "sales_returns"
    id = db.Column(db.Integer, primary_key=True)
    return_number = db.Column(db.String(32), unique=True, nullable=False)
    sales_order_id = db.Column(db.Integer, db.ForeignKey("sales_orders.id"), nullable=False, index=True)
    status = db.Column(db.String(24), default="requested", index=True)  # requested|refunded|rejected
    reason = db.Column(db.String(300))
    restock = db.Column(db.Boolean, default=True)
    refund_amount = db.Column(db.Float, default=0)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    processed_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    order = db.relationship("SalesOrder", lazy="joined")
    items = db.relationship("SalesReturnItem", cascade="all, delete-orphan", lazy="selectin")

    def extra(self):
        return {"so_number": self.order.so_number, "customer_name": self.order.customer.name,
                "items": [i.to_dict() for i in self.items]}


class SalesReturnItem(Serializable, db.Model):
    __tablename__ = "sales_return_items"
    id = db.Column(db.Integer, primary_key=True)
    sales_return_id = db.Column(db.Integer, db.ForeignKey("sales_returns.id"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    condition = db.Column(db.String(20), default="good")  # good|damaged
    product = db.relationship("Product", lazy="joined")

    def extra(self):
        return {"product_name": self.product.name, "sku": self.product.sku}


class Transfer(Serializable, Stamps, db.Model):
    __tablename__ = "transfers"
    id = db.Column(db.Integer, primary_key=True)
    transfer_number = db.Column(db.String(32), unique=True, nullable=False)
    from_warehouse_id = db.Column(db.Integer, db.ForeignKey("warehouses.id"), nullable=False, index=True)
    to_warehouse_id = db.Column(db.Integer, db.ForeignKey("warehouses.id"), nullable=False, index=True)
    status = db.Column(db.String(24), default="requested", nullable=False, index=True)
    notes = db.Column(db.String(300))
    rejection_reason = db.Column(db.String(300))
    requested_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    approved_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    dispatched_at = db.Column(db.DateTime)
    received_at = db.Column(db.DateTime)
    discrepancy_status = db.Column(db.String(20))  # open|resolved
    resolution_note = db.Column(db.String(300))
    is_demo = db.Column(db.Boolean, default=False)
    from_warehouse = db.relationship("Warehouse", foreign_keys=[from_warehouse_id], lazy="joined")
    to_warehouse = db.relationship("Warehouse", foreign_keys=[to_warehouse_id], lazy="joined")
    items = db.relationship("TransferItem", cascade="all, delete-orphan", lazy="selectin")

    def extra(self):
        return {"from_name": self.from_warehouse.name, "to_name": self.to_warehouse.name, "item_count": len(self.items)}

    def detail(self):
        d = self.to_dict()
        d["items"] = [i.to_dict() for i in self.items]
        return d


class TransferItem(Serializable, db.Model):
    __tablename__ = "transfer_items"
    id = db.Column(db.Integer, primary_key=True)
    transfer_id = db.Column(db.Integer, db.ForeignKey("transfers.id"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    dispatched_qty = db.Column(db.Integer, default=0)
    received_qty = db.Column(db.Integer, default=0)
    layers = db.Column(db.Text)  # JSON [{batch_id, quantity}] captured at dispatch (FIFO layers in transit)
    product = db.relationship("Product", lazy="joined")

    def extra(self):
        return {"product_name": self.product.name, "sku": self.product.sku,
                "discrepancy": (self.dispatched_qty or 0) - (self.received_qty or 0) if self.dispatched_qty else 0}


class Notification(Serializable, db.Model):
    __tablename__ = "notifications"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    type = db.Column(db.String(24), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.String(500))
    link = db.Column(db.String(200))
    is_read = db.Column(db.Boolean, default=False, index=True)
    created_at = db.Column(db.DateTime, default=now, index=True)


class AuditLog(Serializable, db.Model):
    __tablename__ = "audit_logs"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), index=True)
    action = db.Column(db.String(60), nullable=False, index=True)
    entity = db.Column(db.String(60), index=True)
    entity_id = db.Column(db.String(40))
    details = db.Column(db.Text)
    ip_address = db.Column(db.String(64))
    created_at = db.Column(db.DateTime, default=now, index=True)
    user = db.relationship("User", lazy="joined")

    def extra(self):
        return {"user_name": self.user.name if self.user else "system"}


class Setting(db.Model):
    __tablename__ = "settings"
    key = db.Column(db.String(80), primary_key=True)
    value = db.Column(db.Text)
    updated_at = db.Column(db.DateTime, default=now, onupdate=now)


class ProcessedOperation(db.Model):
    """Idempotency keys so a double-click / retry can never process a receipt, dispatch or transfer twice."""
    __tablename__ = "processed_operations"
    key = db.Column(db.String(120), primary_key=True)
    created_at = db.Column(db.DateTime, default=now)
