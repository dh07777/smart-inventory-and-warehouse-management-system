from datetime import timedelta
from ..extensions import db
from ..models import Notification, User, Role, Batch, Inventory, Product, Setting
from ..utils import now

NOTIFY_ROLES = {
    "low_stock": ("Super Admin", "Warehouse Manager", "Inventory Manager", "Purchase Manager"),
    "purchase": ("Super Admin", "Purchase Manager", "Warehouse Manager"),
    "sales": ("Super Admin", "Sales Manager", "Warehouse Manager"),
    "expiry": ("Super Admin", "Warehouse Manager", "Inventory Manager"),
    "transfer": ("Super Admin", "Warehouse Manager", "Inventory Manager"),
}


def get_setting(key, default=None):
    s = db.session.get(Setting, key)
    return s.value if s and s.value is not None else default


def notify(kind, title, message="", link=None, dedupe=True):
    users = User.query.join(Role).filter(User.is_active.is_(True), Role.name.in_(NOTIFY_ROLES.get(kind, ("Super Admin",)))).all()
    for u in users:
        if not u.prefs().get(kind, True):
            continue
        if dedupe and Notification.query.filter_by(user_id=u.id, title=title, is_read=False).first():
            continue
        db.session.add(Notification(user_id=u.id, type=kind, title=title, message=message, link=link))


def scan_alerts():
    """Create low-stock, out-of-stock and expiry notifications. Safe to run repeatedly (de-duplicated)."""
    from .inventory_service import low_and_out_products
    low, out = low_and_out_products()
    for p, qty in low:
        notify("low_stock", f"Low stock: {p.name}", f"{qty} {p.unit} left (minimum {p.min_stock}).", "/inventory")
    for p, qty in out:
        notify("low_stock", f"Out of stock: {p.name}", f"{p.sku} has no stock on hand.", "/inventory")
    days = int(get_setting("expiry_alert_days", "30"))
    limit = now().date() + timedelta(days=days)
    rows = (db.session.query(Batch, db.func.sum(Inventory.quantity)).join(Inventory, Inventory.batch_id == Batch.id)
            .filter(Batch.expiry_date.isnot(None), Batch.expiry_date <= limit).group_by(Batch.id)
            .having(db.func.sum(Inventory.quantity) > 0).all())
    for b, qty in rows:
        p = db.session.get(Product, b.product_id)
        state = "expired" if b.expiry_date < now().date() else "expires"
        notify("expiry", f"Batch {b.batch_no} {state}: {p.name}", f"{qty} units, expiry {b.expiry_date}.", "/inventory")
    db.session.flush()
    return {"low_stock": len(low), "out_of_stock": len(out), "expiring_batches": len(rows)}
