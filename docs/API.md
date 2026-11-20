# StockPilot API reference

**141 endpoints.**
Generated from the route decorators (`python scripts/gen_api_docs.py`). Interactive Swagger UI: `/api/docs`; OpenAPI JSON: `/api/openapi.json`.

All endpoints are under `/api`, return `{success, data, meta}` or `{success:false, error:{code,message,details}}`, and (except those marked public) need `Authorization: Bearer <access token>`.
List endpoints accept `page`, `per_page` (max 200), `q`, `sort`, `order` plus module-specific filters.

## admin

| Method | Path | Permission | Handler |
|---|---|---|---|
| GET | `/api/admin/audit-logs` | audit.view | audit_logs |
| GET | `/api/admin/backups` | settings.manage | list_backups |
| POST | `/api/admin/backups` | settings.manage | create_backup |
| DELETE | `/api/admin/backups/<name>` | settings.manage | delete_backup |
| GET | `/api/admin/backups/<name>/download` | settings.manage | download_backup |
| POST | `/api/admin/backups/<name>/restore` | settings.manage | restore_backup |
| GET | `/api/admin/login-history` | audit.view | login_history |
| GET | `/api/admin/permissions` | users.manage | permissions |
| GET | `/api/admin/roles` | users.manage or warehouses.manage | roles |
| PUT | `/api/admin/roles/<int:rid>/permissions` | users.manage | set_role_permissions |
| GET | `/api/admin/settings` | settings.manage | get_settings |
| PUT | `/api/admin/settings` | settings.manage | put_settings |
| GET | `/api/admin/users` | users.manage | list_users |
| POST | `/api/admin/users` | users.manage | create_user |
| PUT | `/api/admin/users/<int:uid>` | users.manage | update_user |
| GET | `/api/admin/users/options` | warehouses.manage or users.manage | user_options |
| GET | `/api/settings/public` | any signed-in user | public_settings |

## auth

| Method | Path | Permission | Handler |
|---|---|---|---|
| POST | `/api/auth/change-password` | public / token | change_password |
| GET | `/api/auth/demo-accounts` | public / token | demo_accounts |
| POST | `/api/auth/forgot-password` | public / token | forgot |
| POST | `/api/auth/login` | public / token | login |
| POST | `/api/auth/logout` | public / token | logout |
| GET | `/api/auth/me` | public / token | me |
| PUT | `/api/auth/me` | public / token | update_me |
| GET | `/api/auth/me/login-history` | public / token | my_history |
| PUT | `/api/auth/me/preferences` | public / token | prefs |
| POST | `/api/auth/refresh` | public / token | refresh |
| POST | `/api/auth/register` | public / token | register |
| POST | `/api/auth/reset-password` | public / token | reset |

## customers

| Method | Path | Permission | Handler |
|---|---|---|---|
| GET | `/api/customers` | customers.view | list (search, filters, sort, pagination) |
| POST | `/api/customers` | customers.manage | create |
| GET | `/api/customers/<int:cid>/orders` | customers.view | orders |
| GET | `/api/customers/<int:cid>/profile` | customers.view | profile |
| DELETE | `/api/customers/<int:oid>` | customers.manage | delete |
| GET | `/api/customers/<int:oid>` | customers.view | get |
| PUT | `/api/customers/<int:oid>` | customers.manage | update |

## dashboard

| Method | Path | Permission | Handler |
|---|---|---|---|
| GET | `/api/dashboard` | dashboard.view | dashboard |

## inventory

| Method | Path | Permission | Handler |
|---|---|---|---|
| POST | `/api/inventory/adjust` | inventory.manage | adjust |
| GET | `/api/inventory/alerts` | inventory.view | alerts |
| GET | `/api/inventory/batches` | inventory.view | batches |
| GET | `/api/inventory/movements` | inventory.view | movements |
| POST | `/api/inventory/reconcile` | inventory.manage | reconcile |
| GET | `/api/inventory/reorder` | inventory.view | reorder |
| GET | `/api/inventory/reservations` | inventory.view | reservations |
| POST | `/api/inventory/reservations` | inventory.manage | reserve |
| POST | `/api/inventory/reservations/<int:rid>/release` | inventory.manage | release |
| GET | `/api/inventory/stock` | inventory.view | stock |
| POST | `/api/inventory/stock-in` | inventory.manage | stock_in |
| POST | `/api/inventory/stock-out` | inventory.manage | stock_out |
| GET | `/api/inventory/valuation` | inventory.view | valuation |
| POST | `/api/inventory/write-off` | inventory.manage | write_off |

## notifications

| Method | Path | Permission | Handler |
|---|---|---|---|
| GET | `/api/notifications` | any signed-in user | list_n |
| DELETE | `/api/notifications/<int:nid>` | any signed-in user | delete |
| POST | `/api/notifications/<int:nid>/read` | any signed-in user | read |
| POST | `/api/notifications/read-all` | any signed-in user | read_all |
| POST | `/api/notifications/scan` | inventory.view | scan |
| GET | `/api/notifications/unread-count` | any signed-in user | unread |

## products

| Method | Path | Permission | Handler |
|---|---|---|---|
| GET | `/api/categories` | products.view | list (search, filters, sort, pagination) |
| POST | `/api/categories` | products.manage | create |
| DELETE | `/api/categories/<int:oid>` | products.manage | delete |
| GET | `/api/categories/<int:oid>` | products.view | get |
| PUT | `/api/categories/<int:oid>` | products.manage | update |
| GET | `/api/products` | products.view | list_products |
| POST | `/api/products` | products.manage | create_product |
| DELETE | `/api/products/<int:pid>` | products.manage | delete_product |
| GET | `/api/products/<int:pid>` | products.view | get_product |
| PUT | `/api/products/<int:pid>` | products.manage | update_product |
| POST | `/api/products/<int:pid>/image` | products.manage | upload_image |
| POST | `/api/products/<int:pid>/variants` | products.manage | add_variant |
| GET | `/api/products/export` | products.view | export_products |
| POST | `/api/products/generate-barcodes` | products.manage | generate_barcodes |
| POST | `/api/products/import` | products.manage | import_products |
| GET | `/api/products/import-template` | products.manage | import_template |
| GET | `/api/products/lookup` | products.view | lookup |
| DELETE | `/api/products/variants/<int:vid>` | products.manage | delete_variant |

## purchases

| Method | Path | Permission | Handler |
|---|---|---|---|
| GET | `/api/purchases` | purchases.view | list_pos |
| POST | `/api/purchases` | purchases.create | create_po |
| GET | `/api/purchases/<int:oid>` | purchases.view | get_po |
| PUT | `/api/purchases/<int:oid>` | purchases.create | update_po |
| POST | `/api/purchases/<int:oid>/approve` | purchases.approve | approve |
| POST | `/api/purchases/<int:oid>/cancel` | purchases.create or purchases.approve | cancel |
| POST | `/api/purchases/<int:oid>/invoice` | purchases.view | make_invoice |
| GET | `/api/purchases/<int:oid>/invoice.pdf` | purchases.view | invoice |
| POST | `/api/purchases/<int:oid>/receive` | purchases.receive | receive |
| POST | `/api/purchases/<int:oid>/reject` | purchases.approve | reject |
| GET | `/api/purchases/analytics` | purchases.view | analytics |
| GET | `/api/purchases/requests` | purchases.view | list_requests |
| POST | `/api/purchases/requests` | purchases.create | create_request |
| GET | `/api/purchases/requests/<int:rid>` | purchases.view | get_request |
| POST | `/api/purchases/requests/<int:rid>/approve` | purchases.approve | approve_request |
| POST | `/api/purchases/requests/<int:rid>/cancel` | purchases.create or purchases.approve | cancel_request |
| POST | `/api/purchases/requests/<int:rid>/convert` | purchases.create | convert_request |
| POST | `/api/purchases/requests/<int:rid>/reject` | purchases.approve | reject_request |

## reports

| Method | Path | Permission | Handler |
|---|---|---|---|
| GET | `/api/reports` | reports.view | catalogue |
| GET | `/api/reports/<key>` | reports.view | report |

## sales

| Method | Path | Permission | Handler |
|---|---|---|---|
| GET | `/api/sales` | sales.view | list_sos |
| POST | `/api/sales` | sales.create | create_so |
| GET | `/api/sales/<int:oid>` | sales.view | get_so |
| POST | `/api/sales/<int:oid>/cancel` | sales.create or sales.process | cancel |
| POST | `/api/sales/<int:oid>/confirm` | sales.process | confirm |
| POST | `/api/sales/<int:oid>/deliver` | sales.process | deliver |
| POST | `/api/sales/<int:oid>/dispatch` | sales.process | dispatch |
| GET | `/api/sales/<int:oid>/invoice.pdf` | sales.view | invoice |
| POST | `/api/sales/<int:oid>/payment` | sales.process | payment |
| POST | `/api/sales/<int:oid>/returns` | sales.process | create_return |
| GET | `/api/sales/analytics` | sales.view | analytics |
| GET | `/api/sales/returns` | sales.view | list_returns |
| POST | `/api/sales/returns/<int:rid>/approve` | sales.process | approve_return |
| POST | `/api/sales/returns/<int:rid>/reject` | sales.process | reject_return |

## suppliers

| Method | Path | Permission | Handler |
|---|---|---|---|
| GET | `/api/suppliers` | suppliers.view | list (search, filters, sort, pagination) |
| POST | `/api/suppliers` | suppliers.manage | create |
| DELETE | `/api/suppliers/<int:oid>` | suppliers.manage | delete |
| GET | `/api/suppliers/<int:oid>` | suppliers.view | get |
| PUT | `/api/suppliers/<int:oid>` | suppliers.manage | update |
| GET | `/api/suppliers/<int:sid>/catalog` | suppliers.view | catalog |
| POST | `/api/suppliers/<int:sid>/catalog` | suppliers.manage | add_catalog |
| GET | `/api/suppliers/<int:sid>/payments` | suppliers.view | payments |
| POST | `/api/suppliers/<int:sid>/payments` | suppliers.manage | add_payment |
| GET | `/api/suppliers/<int:sid>/profile` | suppliers.view | profile |
| GET | `/api/suppliers/<int:sid>/purchases` | suppliers.view | purchases |
| DELETE | `/api/suppliers/catalog/<int:cid>` | suppliers.manage | del_catalog |

## transfers

| Method | Path | Permission | Handler |
|---|---|---|---|
| GET | `/api/transfers` | transfers.view | list_transfers |
| POST | `/api/transfers` | transfers.create | create |
| GET | `/api/transfers/<int:tid>` | transfers.view | get_transfer |
| POST | `/api/transfers/<int:tid>/approve` | transfers.approve | approve |
| POST | `/api/transfers/<int:tid>/cancel` | transfers.create or transfers.approve | cancel |
| POST | `/api/transfers/<int:tid>/dispatch` | transfers.process | dispatch |
| POST | `/api/transfers/<int:tid>/receive` | transfers.process | receive |
| POST | `/api/transfers/<int:tid>/reject` | transfers.approve | reject |
| POST | `/api/transfers/<int:tid>/resolve` | transfers.approve | resolve |

## warehouses

| Method | Path | Permission | Handler |
|---|---|---|---|
| GET | `/api/warehouses` | warehouses.view | list (search, filters, sort, pagination) |
| POST | `/api/warehouses` | warehouses.manage | create |
| DELETE | `/api/warehouses/<int:oid>` | warehouses.manage | delete |
| GET | `/api/warehouses/<int:oid>` | warehouses.view | get |
| PUT | `/api/warehouses/<int:oid>` | warehouses.manage | update |
| GET | `/api/warehouses/<int:wid>/locations` | warehouses.view | locations |
| POST | `/api/warehouses/<int:wid>/locations` | warehouses.manage | add_location |
| GET | `/api/warehouses/<int:wid>/stock` | warehouses.view | stock |
| GET | `/api/warehouses/<int:wid>/summary` | warehouses.view | summary |
| DELETE | `/api/warehouses/locations/<int:lid>` | warehouses.manage | delete_location |
| GET | `/api/warehouses/utilization` | warehouses.view | utilization |
