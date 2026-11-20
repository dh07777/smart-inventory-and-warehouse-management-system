# Progress checklist

| Area | Status |
|---|---|
| Phase 1 - architecture, schema, structure, plan (docs/ARCHITECTURE.md) | done |
| Phase 2 - backend: models, services, repositories, routes, validation, RBAC, audit, rate limit, headers | done |
| Phase 3 - frontend: all module pages wired to real APIs, role-based menu, dark mode, toasts, skeletons | done |
| Auth: register, login, logout, refresh, forgot/reset password, profile, lockout, login history, activate/deactivate | done |
| Products: CRUD, variants, SKU/barcode, barcode lookup + EAN-13 generation, images, CSV/Excel import/export, search/sort/filter/pagination | done |
| Warehouses: CRUD, zones/racks/shelves/bins, utilization, warehouse-wise stock, capacity warnings | done |
| Inventory: FIFO, batches/expiry, reservations, adjustments, damaged/expired, reconciliation, reorder suggestions, negative-stock block + override, overstock warnings | done |
| Suppliers: profile, catalog, payments, ratings, performance (on-time, delay, fill rate) | done |
| Purchasing: purchase requests -> approval -> PO, PO approval, partial receiving, invoice PDF, analytics | done |
| Sales: orders, reservation, dispatch/delivery tracking, invoice PDF, payments, returns/refunds, analytics | done |
| Transfers: request, approval, dispatch (partial), receipt, discrepancy resolution | done |
| Reports: 9 reports, date filters, PDF/Excel/print | done |
| Notifications + preferences, audit log, roles/permissions editor, settings (company, currency/tax, defaults), backup/restore | done |
| Seed script with labelled demo data | done |
| Backend tests (pytest) and frontend tests (Vitest + RTL) written | done |
| **Tests executed on the author's machine** | **not run in the build sandbox (no internet) - run `pytest` and `npm test` first** |
| Static verification (`python scripts/verify_static.py`) | passes |
