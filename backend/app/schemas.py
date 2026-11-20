"""Marshmallow request schemas (server-side validation)."""
import re
from marshmallow import fields, validate, validates, ValidationError, validates_schema
from .utils import BaseSchema


def S(n=255, **k):
    return fields.String(validate=validate.Length(max=n), allow_none=True, **k)


def RS(n=255, mn=1):
    return fields.String(required=True, validate=validate.Length(min=mn, max=n))


def Fl(mn=0, mx=None, **k):
    return fields.Float(validate=validate.Range(min=mn, max=mx), allow_none=True, **k)


def It(mn=0, **k):
    return fields.Integer(validate=validate.Range(min=mn), allow_none=True, **k)


def RI(mn=1):
    return fields.Integer(required=True, validate=validate.Range(min=mn))


def check_password(pw):
    if len(pw) < 8 or not re.search(r"[A-Za-z]", pw) or not re.search(r"\d", pw):
        raise ValidationError("Password must be at least 8 characters and contain a letter and a digit")


class RegisterSchema(BaseSchema):
    name = RS(120, 2)
    email = fields.Email(required=True)
    password = fields.String(required=True, validate=check_password)


class LoginSchema(BaseSchema):
    email = fields.Email(required=True)
    password = fields.String(required=True)


class ForgotSchema(BaseSchema):
    email = fields.Email(required=True)


class ResetSchema(BaseSchema):
    email = fields.Email(required=True)
    token = RS(200)
    password = fields.String(required=True, validate=check_password)


class ChangePasswordSchema(BaseSchema):
    current_password = fields.String(required=True)
    new_password = fields.String(required=True, validate=check_password)


class ProfileSchema(BaseSchema):
    name = fields.String(validate=validate.Length(min=2, max=120))
    phone = S(40)


class UserCreateSchema(BaseSchema):
    name = RS(120, 2)
    email = fields.Email(required=True)
    password = fields.String(required=True, validate=check_password)
    role_id = RI()
    phone = S(40)
    is_active = fields.Boolean()


class UserUpdateSchema(BaseSchema):
    name = fields.String(validate=validate.Length(min=2, max=120))
    role_id = fields.Integer()
    phone = S(40)
    is_active = fields.Boolean()
    password = fields.String(validate=check_password)


class CategorySchema(BaseSchema):
    name = RS(120)
    parent_id = fields.Integer(allow_none=True)
    description = S(300)


class SupplierSchema(BaseSchema):
    code = RS(32)
    name = RS(160)
    contact_person = S(120)
    email = fields.Email(allow_none=True)
    phone = S(40)
    address = S(300)
    city = S(80)
    country = S(80)
    tax_no = S(60)
    payment_terms = S(80)
    rating = Fl(0, 5)
    notes = S(2000)
    is_active = fields.Boolean()


class CustomerSchema(BaseSchema):
    code = RS(32)
    name = RS(160)
    company = S(160)
    email = fields.Email(allow_none=True)
    phone = S(40)
    address = S(300)
    city = S(80)
    notes = S(2000)
    is_active = fields.Boolean()


class WarehouseSchema(BaseSchema):
    code = RS(32)
    name = RS(160)
    address = S(300)
    city = S(80)
    phone = S(40)
    email = fields.Email(allow_none=True)
    manager_id = fields.Integer(allow_none=True)
    capacity = It(0)
    is_active = fields.Boolean()


class LocationSchema(BaseSchema):
    zone = RS(40)
    rack = S(40)
    shelf = S(40)
    bin = S(40)


class ProductSchema(BaseSchema):
    sku = RS(64)
    barcode = S(64)
    name = RS(200)
    description = S(5000)
    category_id = fields.Integer(allow_none=True)
    brand = S(100)
    supplier_id = fields.Integer(allow_none=True)
    unit = S(20)
    purchase_price = Fl(0)
    selling_price = Fl(0)
    tax_rate = Fl(0, 100)
    discount = Fl(0, 100)
    min_stock = It(0)
    max_stock = It(0)
    reorder_qty = It(0)
    image_url = S(500)
    status = fields.String(validate=validate.OneOf(["active", "inactive", "discontinued"]))

    @validates_schema
    def check_levels(self, data, **kw):
        if data.get("max_stock") and data.get("min_stock") and data["max_stock"] < data["min_stock"]:
            raise ValidationError("Maximum stock must be >= minimum stock", "max_stock")


class VariantSchema(BaseSchema):
    name = RS(120)
    sku = RS(64)
    attributes = S(300)
    price_diff = fields.Float(allow_none=True)


class SupplierProductSchema(BaseSchema):
    product_id = RI()
    supplier_sku = S(80)
    price = Fl(0)
    lead_time_days = It(0)


class PaymentSchema(BaseSchema):
    amount = fields.Float(required=True, validate=validate.Range(min=0.01))
    purchase_order_id = fields.Integer(allow_none=True)
    method = S(40)
    reference = S(80)
    note = S(300)


class StockOpSchema(BaseSchema):
    product_id = RI()
    warehouse_id = RI()
    quantity = RI()
    unit_cost = Fl(0)
    batch_no = S(64)
    expiry_date = fields.Date(allow_none=True)
    mfg_date = fields.Date(allow_none=True)
    reason = S(300)
    override = fields.Boolean()


class AdjustSchema(BaseSchema):
    product_id = RI()
    warehouse_id = RI()
    delta = fields.Integer(allow_none=True)
    new_quantity = It(0)
    reason = RS(300)
    override = fields.Boolean()


class WriteOffSchema(BaseSchema):
    product_id = RI()
    warehouse_id = RI()
    batch_id = RI()
    quantity = RI()
    reason = fields.String(required=True, validate=validate.OneOf(["damaged", "expired"]))
    note = S(300)


class ReserveSchema(BaseSchema):
    product_id = RI()
    warehouse_id = RI()
    quantity = RI()
    note = S(300)


class CountLine(BaseSchema):
    product_id = RI()
    counted = RI(0)


class ReconcileSchema(BaseSchema):
    warehouse_id = RI()
    counts = fields.List(fields.Nested(CountLine), required=True, validate=validate.Length(min=1))
    note = S(300)


class POItem(BaseSchema):
    product_id = RI()
    quantity = RI()
    unit_price = Fl(0)


class POSchema(BaseSchema):
    supplier_id = RI()
    warehouse_id = RI()
    expected_date = fields.Date(allow_none=True)
    notes = S(2000)
    items = fields.List(fields.Nested(POItem), required=True, validate=validate.Length(min=1))


class ReceiptLine(BaseSchema):
    item_id = RI()
    quantity = RI(0)
    batch_no = S(64)
    expiry_date = fields.Date(allow_none=True)
    mfg_date = fields.Date(allow_none=True)


class ReceiveSchema(BaseSchema):
    items = fields.List(fields.Nested(ReceiptLine), required=True, validate=validate.Length(min=1))
    idempotency_key = S(80)


class ReasonSchema(BaseSchema):
    reason = S(300)


class SOItem(BaseSchema):
    product_id = RI()
    quantity = RI()
    unit_price = Fl(0)
    discount = Fl(0, 100)


class SOSchema(BaseSchema):
    customer_id = RI()
    warehouse_id = RI()
    notes = S(2000)
    items = fields.List(fields.Nested(SOItem), required=True, validate=validate.Length(min=1))


class DispatchSchema(BaseSchema):
    carrier = S(80)
    tracking_no = S(80)
    idempotency_key = S(80)


class SOPaymentSchema(BaseSchema):
    amount = fields.Float(required=True, validate=validate.Range(min=0.01))


class ReturnItem(BaseSchema):
    product_id = RI()
    quantity = RI()
    condition = fields.String(validate=validate.OneOf(["good", "damaged"]), allow_none=True)


class ReturnSchema(BaseSchema):
    reason = RS(300)
    restock = fields.Boolean()
    items = fields.List(fields.Nested(ReturnItem), required=True, validate=validate.Length(min=1))


class TrfItem(BaseSchema):
    product_id = RI()
    quantity = RI()


class TransferSchema(BaseSchema):
    from_warehouse_id = RI()
    to_warehouse_id = RI()
    notes = S(300)
    items = fields.List(fields.Nested(TrfItem), required=True, validate=validate.Length(min=1))


class TrfDispatchLine(BaseSchema):
    item_id = RI()
    quantity = RI(0)


class TrfDispatchSchema(BaseSchema):
    items = fields.List(fields.Nested(TrfDispatchLine), allow_none=True)
    idempotency_key = S(80)


class TrfReceiveLine(BaseSchema):
    item_id = RI()
    received_qty = RI(0)


class TrfReceiveSchema(BaseSchema):
    items = fields.List(fields.Nested(TrfReceiveLine), allow_none=True)
    note = S(300)
    idempotency_key = S(80)


class NoteSchema(BaseSchema):
    note = RS(300)


class RolePermsSchema(BaseSchema):
    permissions = fields.List(fields.String(), required=True)


class PrefsSchema(BaseSchema):
    low_stock = fields.Boolean()
    purchase = fields.Boolean()
    sales = fields.Boolean()
    expiry = fields.Boolean()
    transfer = fields.Boolean()


class PRItem(BaseSchema):
    product_id = RI()
    quantity = RI()
    note = S(200)


class PurchaseRequestSchema(BaseSchema):
    warehouse_id = RI()
    reason = S(300)
    priority = fields.String(validate=validate.OneOf(["low", "normal", "high"]), allow_none=True)
    needed_by = fields.Date(allow_none=True)
    items = fields.List(fields.Nested(PRItem), required=True, validate=validate.Length(min=1))


class ConvertSchema(BaseSchema):
    supplier_id = RI()
    expected_date = fields.Date(allow_none=True)
    notes = S(2000)
