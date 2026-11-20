"""Idempotent core data: permissions, roles, default settings. Used by seed.py, the tests and first start-up."""
from .extensions import db
from .models import Permission, Role, Setting
from .permissions import PERMISSIONS, ROLE_PERMS, ROLE_DESCRIPTIONS
from .routes.admin import DEFAULT_SETTINGS


def seed_core():
    perms = {}
    for code, desc in PERMISSIONS.items():
        p = Permission.query.filter_by(code=code).first() or Permission(code=code)
        p.description = desc
        db.session.add(p)
        perms[code] = p
    db.session.flush()
    roles = {}
    for name, codes in ROLE_PERMS.items():
        r = Role.query.filter_by(name=name).first() or Role(name=name)
        r.description = ROLE_DESCRIPTIONS[name]
        if r.id is None or name == "Super Admin":  # never overwrite edits made later by an admin, except Super Admin
            r.permissions = [perms[c] for c in codes]
        db.session.add(r)
        roles[name] = r
    for k, v in DEFAULT_SETTINGS.items():
        if db.session.get(Setting, k) is None:
            db.session.add(Setting(key=k, value=v))
    db.session.commit()
    return roles
