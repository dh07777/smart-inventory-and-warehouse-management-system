"""Permission catalogue and default role -> permission mapping (seeded into the DB, editable by Super Admin)."""
PERMISSIONS = {
    "dashboard.view": "View dashboard", "products.view": "View products", "products.manage": "Create/edit/delete products",
    "warehouses.view": "View warehouses", "warehouses.manage": "Manage warehouses", "inventory.view": "View inventory",
    "inventory.manage": "Stock in/out, adjustments, reconciliation", "inventory.override": "Authorize negative-stock override",
    "suppliers.view": "View suppliers", "suppliers.manage": "Manage suppliers and payments",
    "purchases.view": "View purchase orders", "purchases.create": "Create purchase requests", "purchases.approve": "Approve/reject purchase orders",
    "purchases.receive": "Receive goods", "sales.view": "View sales orders", "sales.create": "Create sales orders",
    "sales.process": "Confirm, dispatch, deliver, returns", "transfers.view": "View transfers", "transfers.create": "Request transfers",
    "transfers.approve": "Approve transfers", "transfers.process": "Dispatch/receive transfers", "customers.view": "View customers",
    "customers.manage": "Manage customers", "reports.view": "View and export reports", "audit.view": "View audit logs",
    "users.manage": "Manage users and roles", "settings.manage": "Manage settings and backups",
}
ALL = list(PERMISSIONS)
ROLE_PERMS = {
    "Super Admin": ALL,
    "Warehouse Manager": ["dashboard.view", "products.view", "warehouses.view", "warehouses.manage", "inventory.view", "inventory.manage",
                          "purchases.view", "purchases.receive", "sales.view", "sales.process", "transfers.view", "transfers.create",
                          "transfers.approve", "transfers.process", "customers.view", "reports.view", "suppliers.view"],
    "Inventory Manager": ["dashboard.view", "products.view", "products.manage", "warehouses.view", "inventory.view", "inventory.manage",
                          "suppliers.view", "purchases.view", "transfers.view", "transfers.create", "reports.view"],
    "Purchase Manager": ["dashboard.view", "products.view", "inventory.view", "suppliers.view", "suppliers.manage", "purchases.view",
                         "purchases.create", "purchases.approve", "purchases.receive", "warehouses.view", "reports.view"],
    "Sales Manager": ["dashboard.view", "products.view", "inventory.view", "customers.view", "customers.manage", "sales.view",
                      "sales.create", "sales.process", "warehouses.view", "reports.view"],
    "Staff": ["dashboard.view", "products.view", "inventory.view", "warehouses.view", "transfers.view", "sales.view", "purchases.view",
              "customers.view"],
}
ROLE_DESCRIPTIONS = {
    "Super Admin": "Full system access", "Warehouse Manager": "Warehouses, transfers, dispatch and receiving",
    "Inventory Manager": "Products and stock control", "Purchase Manager": "Suppliers and purchasing",
    "Sales Manager": "Customers and sales orders", "Staff": "Read-only operational access",
}
