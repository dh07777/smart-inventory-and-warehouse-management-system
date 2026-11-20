import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("../api", async () => {
  const actual = await vi.importActual("../api");
  return { ...actual, get: vi.fn(), post: vi.fn(), put: vi.fn(), del: vi.fn(), download: vi.fn(),
    tokens: { access: "tok", refresh: "ref", set: vi.fn(), clear: vi.fn() } };
});
import * as api from "../api";
import { AppProvider } from "../context";
import CrudPage from "../crud";
import Dashboard from "../pages/Dashboard";

const ME = (perms) => ({ data: { name: "Tester", role_name: "Admin", permissions: perms, notification_prefs: {} } });
const rows = [{ id: 1, name: "Acme Corp", city: "Austin" }, { id: 2, name: "Globex", city: "Boston" }];
function setup(perms) {
  api.get.mockImplementation(async (url) => {
    if (url === "/auth/me") return ME(perms);
    if (url === "/settings/public") return { data: { currency_symbol: "$", company_name: "T", demo_data: "false" } };
    if (url === "/dashboard") return { data: DASH };
    return { data: rows, meta: { page: 1, pages: 1, total: 2 } };
  });
  return render(<MemoryRouter><AppProvider>
    <CrudPage title="Customers" entity="customer" endpoint="/customers" manage="customers.manage" columns={[{ key: "name", label: "Name" }, { key: "city", label: "City" }]}
      fields={[{ name: "name", label: "Name", required: true }, { name: "city", label: "City" }]} />
  </AppProvider></MemoryRouter>);
}
const DASH = { totals: { products: 30, warehouses: 3, inventory_quantity: 1234, inventory_value: 5000, low_stock: 2, out_of_stock: 1, expiring_batches: 4, pending_purchase_orders: 3, pending_sales_orders: 2 },
  monthly: [], inventory_trend: [], warehouse_performance: [{ warehouse: "Main", units: 10, capacity: 100, utilization: 10, movements_30d: 5 }], top_products: [{ name: "Widget", units: 9 }],
  recent_movements: [], alerts: { low: [], out: [{ id: 1, name: "Gadget" }] } };

beforeEach(() => { vi.clearAllMocks(); localStorage.clear(); });

describe("CrudPage", () => {
  it("lists records returned by the API and shows pagination info", async () => {
    setup(["customers.manage"]);
    expect(await screen.findByText("Acme Corp")).toBeInTheDocument();
    expect(screen.getByText("Globex")).toBeInTheDocument();
    expect(screen.getByText(/2 records/)).toBeInTheDocument();
  });
  it("hides create/edit/delete controls without the manage permission", async () => {
    setup(["customers.view"]);
    await screen.findByText("Acme Corp");
    expect(screen.queryByText(/Add customer/)).toBeNull();
    expect(screen.queryByLabelText("Edit Acme Corp")).toBeNull();
  });
  it("creates a record through the API", async () => {
    api.post.mockResolvedValue({ data: {} });
    setup(["customers.manage"]);
    fireEvent.click(await screen.findByText(/Add customer/));
    fireEvent.change(screen.getByLabelText(/^Name/), { target: { value: "New Co" } });
    fireEvent.click(screen.getByText("Save"));
    await waitFor(() => expect(api.post).toHaveBeenCalledWith("/customers", { name: "New Co", city: "" }));
  });
  it("sends the search term to the API", async () => {
    setup(["customers.manage"]);
    await screen.findByText("Acme Corp");
    fireEvent.change(screen.getByLabelText("Search"), { target: { value: "glob" } });
    await waitFor(() => expect(api.get).toHaveBeenCalledWith("/customers", expect.objectContaining({ q: "glob" })), { timeout: 2000 });
  });
  it("asks for confirmation before deleting", async () => {
    api.del.mockResolvedValue({});
    setup(["customers.manage"]);
    fireEvent.click(await screen.findByLabelText("Delete Acme Corp"));
    expect(screen.getByText(/Delete "Acme Corp"/)).toBeInTheDocument();
    fireEvent.click(screen.getByText("Confirm"));
    await waitFor(() => expect(api.del).toHaveBeenCalledWith("/customers/1"));
  });
});

describe("Dashboard", () => {
  it("renders live totals from the API instead of hard-coded numbers", async () => {
    api.get.mockImplementation(async (url) => (url === "/auth/me" ? ME(["dashboard.view"]) : url === "/settings/public" ? { data: { currency_symbol: "$" } } : { data: DASH }));
    render(<MemoryRouter><AppProvider><Dashboard /></AppProvider></MemoryRouter>);
    expect(await screen.findByText("1,234")).toBeInTheDocument();
    expect(screen.getByText("$5,000.00")).toBeInTheDocument();
    expect(screen.getByText("Gadget")).toBeInTheDocument();
    expect(screen.getByText("4 batches expiring soon")).toBeInTheDocument();
  });
});
