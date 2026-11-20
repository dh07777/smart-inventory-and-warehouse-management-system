import logging, re, sqlite3
from flask import Flask, jsonify, request, send_from_directory
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import HTTPException
from .config import Config
from .extensions import db, migrate, jwt, limiter, cors
from .utils import BusinessError, error_response
from . import models  # noqa: F401  (register models for migrations)


@event.listens_for(Engine, "connect")
def _sqlite_pragmas(conn, _record):
    if isinstance(conn, sqlite3.Connection):
        cur = conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.execute("PRAGMA busy_timeout=8000")
        cur.execute("PRAGMA journal_mode=WAL")
        cur.close()


def create_app(config_class=Config):
    import os
    app = Flask(__name__)
    app.config.from_object(config_class)
    app.url_map.strict_slashes = False
    if app.config["ENV_NAME"] == "production" and not (os.getenv("SECRET_KEY") and os.getenv("JWT_SECRET_KEY")):
        raise RuntimeError("SECRET_KEY and JWT_SECRET_KEY must be set in the environment for production")
    for folder in (app.config["UPLOAD_FOLDER"], app.config["BACKUP_FOLDER"]):
        os.makedirs(folder, exist_ok=True)
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    limiter.init_app(app)
    cors.init_app(app, resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}}, allow_headers=["Content-Type", "Authorization"],
                  expose_headers=["Content-Disposition"], supports_credentials=False)
    logging.basicConfig(level=logging.INFO)

    from .routes import auth, products, warehouses, inventory, suppliers, purchases, sales, transfers, customers, reports, notifications, dashboard, admin
    for m in (auth.bp, products.bp, products.cat_bp, warehouses.bp, inventory.bp, suppliers.bp, purchases.bp, sales.bp, transfers.bp,
              customers.bp, reports.bp, notifications.bp, dashboard.bp, admin.bp):
        app.register_blueprint(m)

    # ---- JWT behaviour ----
    @jwt.token_in_blocklist_loader
    def _revoked(_h, payload):
        return db.session.query(models.TokenBlocklist.id).filter_by(jti=payload["jti"]).first() is not None

    @jwt.expired_token_loader
    def _expired(_h, _p):
        return error_response("Session expired. Please sign in again.", 401, "token_expired")

    @jwt.invalid_token_loader
    def _invalid(msg):
        return error_response("Invalid authentication token", 401, "token_invalid")

    @jwt.unauthorized_loader
    def _missing(msg):
        return error_response("Authentication required", 401, "unauthorized")

    @jwt.revoked_token_loader
    def _revoked_cb(_h, _p):
        return error_response("Session was signed out", 401, "token_revoked")

    # ---- Centralised error handling ----
    @app.errorhandler(BusinessError)
    def _biz(e):
        db.session.rollback()
        return error_response(e.message, e.status, e.code, e.details)

    @app.errorhandler(IntegrityError)
    def _integrity(e):
        db.session.rollback()
        text = str(getattr(e, "orig", e))
        msg = ("A record with the same unique value already exists" if "UNIQUE" in text
               else "This record is referenced by other data and cannot be deleted or changed this way. Deactivate it instead."
               if "FOREIGN KEY" in text else "The data violates a database constraint")
        return error_response(msg, 409, "conflict")

    @app.errorhandler(HTTPException)
    def _http(e):
        db.session.rollback()
        msgs = {404: "Resource not found", 405: "Method not allowed", 413: "Upload is too large", 429: "Too many requests. Slow down and retry shortly."}
        return error_response(msgs.get(e.code, e.description), e.code, (e.name or "error").lower().replace(" ", "_"))

    @app.errorhandler(Exception)
    def _unhandled(e):
        db.session.rollback()
        app.logger.exception("Unhandled error")
        return error_response("Internal server error" if not app.debug else str(e), 500, "server_error")

    @app.after_request
    def _headers(resp):
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "no-referrer"
        resp.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"
        if request.path.startswith("/api/") and not request.path.startswith("/api/docs"):
            resp.headers["Cache-Control"] = "no-store"
            resp.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
        if app.config["ENV_NAME"] == "production":
            resp.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return resp

    @app.get("/uploads/<path:name>")
    def _uploads(name):
        resp = send_from_directory(app.config["UPLOAD_FOLDER"], name)
        resp.headers["Cross-Origin-Resource-Policy"] = "cross-origin"
        return resp

    @app.get("/api/health")
    def _health():
        return jsonify({"success": True, "data": {"status": "ok"}})

    # ---- OpenAPI / Swagger (generated from the registered routes) ----
    @app.get("/api/openapi.json")
    def _openapi():
        paths = {}
        for rule in app.url_map.iter_rules():
            if not rule.rule.startswith("/api/") or rule.rule.startswith("/api/docs") or rule.rule.endswith("openapi.json"):
                continue
            fn = app.view_functions[rule.endpoint]
            path = re.sub(r"<(?:\w+:)?(\w+)>", r"{\1}", rule.rule)
            params = [{"name": n, "in": "path", "required": True, "schema": {"type": "string"}} for n in re.findall(r"<(?:\w+:)?(\w+)>", rule.rule)]
            for method in rule.methods - {"HEAD", "OPTIONS"}:
                perms = getattr(fn, "required_permissions", ())
                op = {"tags": [rule.endpoint.split(".")[0]], "summary": fn.__name__.replace("_", " ").strip().title(),
                      "description": ("Requires one of: " + ", ".join(perms)) if perms else "", "parameters": params,
                      "responses": {"200": {"description": "Success: {success, data, meta}"}, "401": {"description": "Unauthenticated"},
                                    "403": {"description": "Forbidden"}, "422": {"description": "Validation error"}}}
                if not rule.endpoint.startswith(("auth.login", "auth.register", "auth.forgot", "auth.reset", "auth.demo")) and rule.endpoint != "_health":
                    op["security"] = [{"bearerAuth": []}]
                if method in ("POST", "PUT"):
                    op["requestBody"] = {"content": {"application/json": {"schema": {"type": "object"}}}}
                paths.setdefault(path, {})[method.lower()] = op
        return jsonify({"openapi": "3.0.3", "info": {"title": "StockPilot API", "version": "1.0.0",
                        "description": "Smart Inventory & Warehouse Management System. All responses use {success, data, meta} / {success:false, error}."},
                        "components": {"securitySchemes": {"bearerAuth": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}}},
                        "paths": dict(sorted(paths.items()))})

    @app.get("/api/docs")
    def _docs():
        html = ('<!doctype html><html><head><meta charset="utf-8"><title>StockPilot API</title>'
                '<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.17.14/swagger-ui.css"></head><body><div id="ui"></div>'
                '<script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.17.14/swagger-ui-bundle.js"></script>'
                '<script>SwaggerUIBundle({url:"/api/openapi.json",dom_id:"#ui"})</script></body></html>')
        return html, 200, {"Content-Type": "text/html; charset=utf-8"}

    @app.cli.command("scan-alerts")
    def _scan():
        from .services.notification_service import scan_alerts
        print(scan_alerts())
        db.session.commit()

    return app
