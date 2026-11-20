import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { DataTable, Pagination, Badge, ItemsEditor, ProductImage } from "../ui";

describe("DataTable", () => {
  const cols = [{ key: "name", label: "Name" }, { key: "qty", label: "Qty", render: (r) => <b>{r.qty} pcs</b> }];
  it("renders rows with custom cell renderers", () => {
    render(<DataTable columns={cols} rows={[{ id: 1, name: "Widget", qty: 5 }]} />);
    expect(screen.getByText("Widget")).toBeInTheDocument();
    expect(screen.getByText("5 pcs")).toBeInTheDocument();
  });
  it("shows an empty state", () => {
    render(<DataTable columns={cols} rows={[]} empty="Nothing here" />);
    expect(screen.getByText("Nothing here")).toBeInTheDocument();
  });
  it("shows skeleton rows while loading and hides data", () => {
    const { container } = render(<DataTable columns={cols} rows={[{ id: 1, name: "Hidden", qty: 1 }]} loading />);
    expect(container.querySelectorAll(".animate-pulse").length).toBeGreaterThan(0);
    expect(screen.queryByText("Hidden")).toBeNull();
  });
  it("calls onSort for sortable headers", () => {
    const onSort = vi.fn();
    render(<DataTable columns={[{ key: "name", label: "Name", sortable: true }]} rows={[]} onSort={onSort} />);
    fireEvent.click(screen.getByText("Name"));
    expect(onSort).toHaveBeenCalledWith("name");
  });
});

describe("Pagination", () => {
  it("navigates pages and disables edges", () => {
    const onPage = vi.fn();
    render(<Pagination meta={{ page: 1, pages: 3, total: 25 }} onPage={onPage} />);
    expect(screen.getByLabelText("Previous page")).toBeDisabled();
    fireEvent.click(screen.getByLabelText("Next page"));
    expect(onPage).toHaveBeenCalledWith(2);
  });
});

describe("Badge / images / items editor", () => {
  it("formats status values", () => {
    render(<Badge value="partially_received" />);
    expect(screen.getByText("partially received")).toBeInTheDocument();
  });
  it("falls back to a local placeholder when an image fails to load", () => {
    render(<ProductImage src="https://broken.invalid/x.jpg" alt="p" />);
    const img = screen.getByAltText("p");
    fireEvent.error(img);
    expect(img.getAttribute("src")).toMatch(/^data:image\/svg/);
  });
  it("adds and removes order lines", () => {
    let items = [{ product_id: "", quantity: 1, unit_price: "" }];
    const onChange = vi.fn((n) => { items = n; });
    const { rerender } = render(<ItemsEditor items={items} onChange={onChange} products={[{ id: 1, sku: "P1", name: "Widget", purchase_price: 10, discount: 0 }]} />);
    fireEvent.click(screen.getByText("Add line"));
    expect(items).toHaveLength(2);
    rerender(<ItemsEditor items={items} onChange={onChange} products={[]} />);
    fireEvent.click(screen.getAllByLabelText("Remove line")[0]);
    expect(items).toHaveLength(1);
  });
  it("auto-fills the unit price when a product is chosen", () => {
    let items = [{ product_id: "", quantity: 1, unit_price: "" }];
    const onChange = vi.fn((n) => { items = n; });
    render(<ItemsEditor items={items} onChange={onChange} products={[{ id: 1, sku: "P1", name: "Widget", purchase_price: 10, discount: 0 }]} />);
    fireEvent.change(screen.getByLabelText("Product"), { target: { value: "1" } });
    expect(items[0].unit_price).toBe(10);
  });
});
