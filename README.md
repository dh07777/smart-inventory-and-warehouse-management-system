# StockPilot - Smart Inventory & Warehouse Management System

Full-stack inventory and warehouse platform: **React + Vite + Tailwind** frontend, **Flask + SQLAlchemy + SQLite** backend, JWT auth with role-based access control, FIFO inventory valuation, PDF/Excel reports, Swagger docs and automated tests.

> Screenshots: `docs/screenshots/dashboard.png`, `inventory.png`, `purchases.png`, `reports.png` *(add your own after running the app)*

Docs: [Architecture & schema](docs/ARCHITECTURE.md) - [API reference (141 endpoints)](docs/API.md) - [Progress checklist](docs/CHECKLIST.md)

## Features (12 modules)
* **Dashboard** - live KPIs, monthly purchase/sales chart, inventory trend, warehouse performance, top sellers, stock alerts, recent movements.
* **Products** - CRUD, categories/subcategories, variants, SKU + barcode (scan/lookup, EAN-13 generation), images (upload + local fallback), pricing/tax/discount, min/max/reorder levels, CSV/Excel import & export, search/sort/filter/pagination.
* **Warehouses** - multiple sites, managers, capacity + utilization, zones/racks/shelves/bins, warehouse-wise stock, capacity warnings.
* **Inventory control** - stock in/out, adjustments, reservations, damaged/expired write-off, batches & expiry, **FIFO valuation**, reconciliation, reorder recommendations, overstock warnings, negative-stock block with authorized override (setting + permission), full movement history.
* **Suppliers** - profiles, product catalog, payments & outstanding balance, rating/notes, performance (on-time %, average delay, fill rate).
* **Purchasing** - purchase **requests -> approval -> generate PO**, direct POs with approval, partial receiving with batch/expiry, purchase invoice PDF, analytics.
* **Sales** - orders, stock reservation, dispatch + tracking, delivery, payments, sales invoice PDF, returns/refunds (restock or damaged), analytics.
* **Stock transfers** - request, approval, partial dispatch, receipt confirmation, discrepancy resolution, history.
* **Customers** - profiles, order history, purchase statistics.
* **Reports** - 9 reports (valuation, movements, low stock, expiry, warehouse stock, purchases, sales, suppliers, product performance) with date filters, charts, PDF, Excel and print layouts.
* **Notifications** - low/out-of-stock, overstock/capacity, expiry, purchase, sales, transfer; read/unread; per-user preferences.
* **Admin** - users (activate/deactivate), roles & permission editor, audit log, login history, company/currency/tax/defaults settings, SQLite backup & restore.

Roles: Super Admin, Warehouse Manager, Inventory Manager, Purchase Manager, Sales Manager, Staff - enforced **server-side** (`@permission_required`) and mirrored in the UI.

## Run on Windows (VS Code + PowerShell)
Prerequisites: Python 3.11+, Node.js 18+, VS Code. Open the `stockpilot` folder in VS Code, then open a terminal (Terminal -> New Terminal).

### Fastest: two scripts
```powershell
Set-ExecutionPolicy -Scope Process Bypass      # only for this window
.\scripts\setup.ps1                            # venv, pip install, .env with random secrets, DB + demo data, npm install
.\scripts\dev.ps1                              # API in a new window (http://127.0.0.1:5000) + web app (http://localhost:5173)
```
(VS Code: *Terminal -> Run Task -> "Run StockPilot (API + web)"* does the same after setup.)

### Step by step
**Terminal 1 - backend**
```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1          # if blocked: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
pip install -r requirements.txt
python scripts/make_env.py            # creates .env with random secrets
python seed.py --create-tables        # SQLite DB + clearly-labelled DEMO data
python wsgi.py                        # API http://127.0.0.1:5000   (Swagger: /api/docs)
```
**Terminal 2 - frontend**
```powershell
cd frontend
npm install
npm run dev                           # http://localhost:5173
```
Sign in with a demo account (password **Demo@12345**; click a role on the login page): `admin@stockpilot.demo`, `warehouse@…`, `inventory@…`, `purchase@…`, `sales@…`, `staff@…`.

### Migrations instead of `--create-tables`
```powershell
$env:FLASK_APP = "wsgi.py"
flask db init ; flask db migrate -m "initial schema" ; flask db upgrade
python seed.py
```
Reset demo data any time: `python seed.py --reset`.

## Tests and verification
```powershell
cd backend ; pytest -v                       # 44 test cases: auth, RBAC, products, FIFO, purchases/requests, sales, transfers, reports, backup/restore ...
cd frontend ; npm test                       # 21 Vitest + React Testing Library tests
python scripts/verify_static.py              # dependency-free checks: syntax, undefined names, tables/FKs, permissions, every UI API call has a route, JSX structure
```
**Honest status:** `verify_static.py` passes. The pytest and Vitest suites were written but could not be executed where this project was generated (no internet to install packages), so run them first (`pytest -v`, `npm test`) and fix anything they report before relying on the app.

## Architecture (short)
```
backend/app/  models.py  schemas.py  permissions.py  utils.py
              routes/         thin Flask blueprints + generic CRUD factory
              services/       business rules (inventory_service = the only code that changes stock)
              repositories/   query building: stock, products, orders
frontend/src/ context (auth/theme/toasts) - api (axios + token refresh) - ui/crud (reusable components) - pages/
```
Inventory = one row per (product, warehouse, batch) = a FIFO cost layer. Every quantity change goes through `stock_in` / `stock_out`, writes `stock_movements`, and a route commits once, so each business operation is one atomic transaction. Duplicates are prevented by status guards plus idempotency keys.

## Deployment (production)
1. Backend: `APP_ENV=production`, strong `SECRET_KEY` / `JWT_SECRET_KEY`, `CORS_ORIGINS` = your site URL. Windows: `waitress-serve --listen=0.0.0.0:8000 wsgi:app`; Linux: `gunicorn -w 1 --threads 8 wsgi:app` behind Nginx + HTTPS.
2. Frontend: `VITE_API_URL=https://your-api/api`, `npm run build`, serve `frontend/dist` from any static host.
3. Persist `backend/instance`, `uploads`, `backups`; schedule backups and copy them off-server.

**SQLite limitations:** one writer at a time. Fine for a project, demo or small team (WAL + busy timeout enabled), not for high-volume concurrent multi-user production. Run one worker process; move to PostgreSQL via `DATABASE_URL` when traffic grows (the dashboard/analytics month grouping uses SQLite `strftime` and would need adapting).

## Security notes
Password hashing (Werkzeug), JWT access/refresh with revocation list, login lockout (5 failures / 15 min), rate limiting, strict CORS, security headers, validated input, parameterized queries, audit trail. Tokens live in `localStorage` for simplicity (XSS risk if untrusted HTML is ever rendered) - use HttpOnly cookies for hardened deployments. Reset links are e-mailed when `MAIL_*` is configured; otherwise logged (and shown in the UI only in development).

## Data notes
Seeded records are flagged `is_demo` and the UI shows a demo banner. Demo product photos use `picsum.photos` placeholders; the UI falls back to a built-in SVG whenever an image fails to load. Money is stored as rounded floats (use Numeric/integer cents for real accounting).
