import { useRef, useState } from "react";
import { Eye, Download, Upload, FileSpreadsheet, Trash2, Plus, Shield } from "lucide-react";
import api, { get, post, put, del, download, errMsg } from "../api";
import { useApp } from "../context";
import { useFetch, useList } from "../hooks";
import CrudPage from "../crud";
import { Button, Modal, Input, Badge, ProductImage, Bar, DataTable, Pagination, Tabs, Stat } from "../ui";

const stockBadge = (r) => <span className="flex items-center gap-2">{r.stock}<Badge value={r.stock_status} /></span>;
const yesNo = (r) => <Badge value={r.is_active ? "active" : "inactive"} />;
const statusOpts = ["active", "inactive", "discontinued"].map((v) => ({ value: v, label: v }));

function ProductDetail({ id, onClose, onChanged }) {
  const { can, notify, money } = useApp();
  const { data: p, reload } = useFetch(`/products/${id}`);
  const [v, setV] = useState({ name: "", sku: "", attributes: "", price_diff: "" });
  const file = useRef();
  const run = async (fn, msg) => { try { await fn(); notify(msg); reload(); onChanged(); } catch (e) { notify(errMsg(e), "error"); } };
  if (!p) return <Modal title="Product" onClose={onClose}>Loading...</Modal>;
  return (
    <Modal title={`${p.name} (${p.sku})`} onClose={onClose} wide>
      <div className="grid gap-4 sm:grid-cols-3">
        <div><ProductImage src={p.image_url} alt={p.name} className="h-40 w-full" />
          {can("products.manage") && <><input ref={file} type="file" accept="image/*" hidden aria-label="Upload image" onChange={(e) => {
            const fd = new FormData(); fd.append("image", e.target.files[0]);
            run(() => api.post(`/products/${id}/image`, fd), "Image uploaded");
          }} /><Button variant="ghost" className="mt-2 w-full" onClick={() => file.current.click()}><Upload size={14} /> Upload image</Button></>}</div>
        <div className="space-y-1 text-sm sm:col-span-2">
          <p className="text-slate-500">{p.description || "No description"}</p>
          <p><b>Category:</b> {p.category_name || "-"} | <b>Brand:</b> {p.brand || "-"} | <b>Supplier:</b> {p.supplier_name || "-"}</p>
          <p><b>Barcode:</b> {p.barcode || "-"} | <b>Unit:</b> {p.unit}</p>
          <p><b>Cost:</b> {money(p.purchase_price)} | <b>Price:</b> {money(p.selling_price)} | <b>Tax:</b> {p.tax_rate}% | <b>Discount:</b> {p.discount}%</p>
          <p><b>Min/Max/Reorder:</b> {p.min_stock} / {p.max_stock} / {p.reorder_qty} | <b>Status:</b> <Badge value={p.status} /></p>
          <p><b>On hand:</b> {p.stock} | <b>Reserved:</b> {p.reserved}</p>
        </div>
      </div>
      <h4 className="mb-1 mt-4 font-semibold">Stock by warehouse</h4>
      {p.warehouse_stock.length === 0 ? <p className="text-sm text-slate-500">No stock in any warehouse.</p> : p.warehouse_stock.map((w) => <div key={w.warehouse_id} className="flex justify-between border-b py-1 text-sm dark:border-slate-700"><span>{w.warehouse_name}</span><b>{w.quantity}</b></div>)}
      <h4 className="mb-1 mt-4 font-semibold">Variants</h4>
      {p.variants.map((x) => <div key={x.id} className="flex items-center justify-between border-b py-1 text-sm dark:border-slate-700"><span>{x.name} - {x.sku} {x.attributes && `(${x.attributes})`} {x.price_diff ? `+${x.price_diff}` : ""}</span>
        {can("products.manage") && <Button variant="ghost" aria-label="Remove variant" onClick={() => run(() => del(`/products/variants/${x.id}`), "Variant removed")}><Trash2 size={14} /></Button>}</div>)}
      {can("products.manage") && (
        <div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-5">
          <input className="input" placeholder="Variant name" value={v.name} onChange={(e) => setV({ ...v, name: e.target.value })} />
          <input className="input" placeholder="Variant SKU" value={v.sku} onChange={(e) => setV({ ...v, sku: e.target.value })} />
          <input className="input" placeholder="Attributes (Red, XL)" value={v.attributes} onChange={(e) => setV({ ...v, attributes: e.target.value })} />
          <input className="input" type="number" placeholder="Price diff" value={v.price_diff} onChange={(e) => setV({ ...v, price_diff: e.target.value })} />
          <Button onClick={() => run(async () => { await post(`/products/${id}/variants`, { ...v, price_diff: v.price_diff === "" ? 0 : Number(v.price_diff) }); setV({ name: "", sku: "", attributes: "", price_diff: "" }); }, "Variant added")}><Plus size={14} /> Add</Button>
        </div>)}
    </Modal>
  );
}

export function Products() {
  const { can, notify } = useApp();
  const [view, setView] = useState(null);
  const [tick, setTick] = useState(0);
  const imp = useRef();
  const [code, setCode] = useState("");
  const lookup = async (e) => {
    e.preventDefault();
    try { const r = await get("/products/lookup", { code }); setView(r.data.id); setCode(""); } catch (err) { notify(errMsg(err), "error"); }
  };
  return (
    <>
      <CrudPage key={tick} title="Products" subtitle="Catalogue, pricing, stock levels and bulk import/export" entity="product" endpoint="/products" manage="products.manage"
        searchHint="Search name, SKU, barcode, brand..." initialSort={{ sort: "created_at", order: "desc" }} defaults={{ unit: "pcs", status: "active", tax_rate: 0, discount: 0, min_stock: 0, max_stock: 0, reorder_qty: 0 }}
        filters={[{ name: "category_id", label: "All categories", options: null, optionsFrom: true }, { name: "status", label: "Any status", options: statusOpts },
          { name: "stock", label: "Any stock", options: [{ value: "low", label: "Low stock" }, { value: "out", label: "Out of stock" }, { value: "ok", label: "In stock" }] }]}
        columns={[{ key: "image_url", label: "", render: (r) => <ProductImage src={r.image_url} alt={r.name} /> }, { key: "sku", label: "SKU", sortable: true }, { key: "name", label: "Name", sortable: true },
          { key: "category_name", label: "Category" }, { key: "selling_price", label: "Price", sortable: true }, { key: "stock", label: "Stock", sortable: true, render: stockBadge }, { key: "status", label: "Status", render: (r) => <Badge value={r.status} /> }]}
        fields={[{ name: "sku", label: "SKU", required: true }, { name: "barcode", label: "Barcode" }, { name: "name", label: "Name", required: true },
          { name: "category_id", label: "Category", type: "select", optionsUrl: "/categories" }, { name: "brand", label: "Brand" }, { name: "supplier_id", label: "Supplier", type: "select", optionsUrl: "/suppliers" },
          { name: "unit", label: "Unit of measure" }, { name: "status", label: "Status", type: "select", options: statusOpts },
          { name: "purchase_price", label: "Purchase price", type: "number", step: "0.01" }, { name: "selling_price", label: "Selling price", type: "number", step: "0.01" },
          { name: "tax_rate", label: "Tax %", type: "number", step: "0.01" }, { name: "discount", label: "Discount %", type: "number", step: "0.01" },
          { name: "min_stock", label: "Minimum stock", type: "number" }, { name: "max_stock", label: "Maximum stock", type: "number" }, { name: "reorder_qty", label: "Reorder quantity", type: "number" },
          { name: "image_url", label: "Image URL (or upload in View)" }, { name: "description", label: "Description", type: "textarea" }]}
        rowActions={(r) => <Button variant="ghost" onClick={() => setView(r.id)} aria-label={`View ${r.name}`}><Eye size={14} /></Button>}
        toolbar={(reload) => <>
          <form onSubmit={lookup} className="flex gap-1"><input aria-label="Scan barcode or SKU" className="input w-44" placeholder="Scan barcode / SKU" value={code} onChange={(e) => setCode(e.target.value)} /><Button type="submit" variant="ghost">Find</Button></form>
          {can("products.manage") && <Button variant="ghost" onClick={async () => { try { const r = await post("/products/generate-barcodes"); notify(r.message); reload(); } catch (err) { notify(errMsg(err), "error"); } }}>Generate barcodes</Button>}
          <Button variant="ghost" onClick={() => download("/products/export", { format: "csv" }, "products.csv")}><Download size={14} /> CSV</Button>
          <Button variant="ghost" onClick={() => download("/products/export", { format: "xlsx" }, "products.xlsx")}><FileSpreadsheet size={14} /> Excel</Button>
          {can("products.manage") && <>
            <Button variant="ghost" onClick={() => download("/products/import-template", {}, "product_import_template.csv")}>Template</Button>
            <input ref={imp} type="file" accept=".csv,.xlsx" hidden aria-label="Import file" onChange={async (e) => {
              const fd = new FormData(); fd.append("file", e.target.files[0]);
              try { const r = await api.post("/products/import", fd); const d = r.data.data; notify(r.data.message, d.errors.length ? "error" : "success"); if (d.errors.length) alert("Rows with errors:\n" + d.errors.map((x) => `Row ${x.row}: ${x.error}`).join("\n")); reload(); }
              catch (err) { notify(errMsg(err), "error"); } e.target.value = "";
            }} />
            <Button variant="ghost" onClick={() => imp.current.click()}><Upload size={14} /> Import</Button></>}
        </>} />
      {view && <ProductDetail id={view} onClose={() => setView(null)} onChanged={() => setTick((t) => t + 1)} />}
    </>
  );
}

export const Categories = () => (
  <CrudPage title="Categories" subtitle="Categories and subcategories" entity="category" endpoint="/categories" manage="products.manage" initialSort={{ sort: "name", order: "asc" }}
    columns={[{ key: "name", label: "Name", sortable: true }, { key: "parent_name", label: "Parent category" }, { key: "description", label: "Description" }]}
    fields={[{ name: "name", label: "Name", required: true }, { name: "parent_id", label: "Parent category (optional)", type: "select", optionsUrl: "/categories" }, { name: "description", label: "Description" }]} />
);

function WarehouseDetail({ w, onClose }) {
  const { can, notify } = useApp();
  const sum = useFetch(`/warehouses/${w.id}/summary`);
  const stock = useList(`/warehouses/${w.id}/stock`);
  const [tab, setTab] = useState("s");
  const [loc, setLoc] = useState({ zone: "", rack: "", shelf: "", bin: "" });
  const act = async (fn) => { try { await fn(); sum.reload(); } catch (e) { notify(errMsg(e), "error"); } };
  const s = sum.data;
  return (
    <Modal title={`${w.name} (${w.code})`} onClose={onClose} wide>
      {s && <div className="mb-4 grid gap-3 sm:grid-cols-3"><Stat label="Units stored" value={s.units} /><Stat label="Capacity" value={s.capacity} tone="amber" /><div className="card"><div className="mb-1 text-xs text-slate-500">Utilization {s.utilization}%</div><Bar pct={s.utilization} /></div></div>}
      <Tabs tabs={[{ key: "s", label: "Warehouse-wise inventory" }, { key: "l", label: "Zones, racks, shelves & bins" }]} value={tab} onChange={setTab} />
      {tab === "s" ? (
        <><DataTable loading={stock.loading} rows={stock.rows} rowKey="product_id" columns={[{ key: "sku", label: "SKU" }, { key: "name", label: "Product" }, { key: "quantity", label: "Qty" }, { key: "value", label: "Value (FIFO)" }]} /><Pagination meta={stock.meta} onPage={stock.setPage} /></>
      ) : (
        <div>
          <div className="mb-3 flex flex-wrap gap-2">{(s?.locations || []).map((l) => <span key={l.id} className="flex items-center gap-1 rounded-full bg-slate-100 px-3 py-1 text-xs dark:bg-slate-700">{l.label}
            {can("warehouses.manage") && <button aria-label="Remove location" onClick={() => act(() => del(`/warehouses/locations/${l.id}`))}>×</button>}</span>)}</div>
          {can("warehouses.manage") && <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">{["zone", "rack", "shelf", "bin"].map((k) => <input key={k} className="input" placeholder={k} value={loc[k]} onChange={(e) => setLoc({ ...loc, [k]: e.target.value })} />)}
            <Button onClick={() => act(async () => { await post(`/warehouses/${w.id}/locations`, loc); setLoc({ zone: "", rack: "", shelf: "", bin: "" }); })}><Plus size={14} /> Add</Button></div>}
        </div>)}
    </Modal>
  );
}

export function Warehouses() {
  const [sel, setSel] = useState(null);
  return (
    <>
      <CrudPage title="Warehouses" subtitle="Locations, capacity and managers" entity="warehouse" endpoint="/warehouses" manage="warehouses.manage" initialSort={{ sort: "name", order: "asc" }} defaults={{ capacity: 0, is_active: true }}
        columns={[{ key: "code", label: "Code", sortable: true }, { key: "name", label: "Name", sortable: true }, { key: "city", label: "City" }, { key: "manager_name", label: "Manager" }, { key: "capacity", label: "Capacity", sortable: true }, { key: "is_active", label: "Status", render: yesNo }]}
        fields={[{ name: "code", label: "Code", required: true }, { name: "name", label: "Name", required: true }, { name: "address", label: "Address" }, { name: "city", label: "City" }, { name: "phone", label: "Phone" }, { name: "email", label: "Email", type: "email" },
          { name: "manager_id", label: "Warehouse manager", type: "select", optionsUrl: "/admin/users/options", optionLabel: (u) => `${u.name} (${u.role})` }, { name: "capacity", label: "Capacity (units)", type: "number" }, { name: "is_active", label: "Active", type: "checkbox" }]}
        rowActions={(r) => <Button variant="ghost" onClick={() => setSel(r)} aria-label={`Details ${r.name}`}><Eye size={14} /></Button>} />
      {sel && <WarehouseDetail w={sel} onClose={() => setSel(null)} />}
    </>
  );
}

function SupplierProfile({ s, onClose }) {
  const { can, notify, money } = useApp();
  const prof = useFetch(`/suppliers/${s.id}/profile`);
  const cat = useFetch(`/suppliers/${s.id}/catalog`);
  const pays = useList(`/suppliers/${s.id}/payments`);
  const pos = useList(`/suppliers/${s.id}/purchases`);
  const prods = useFetch("/products", { per_page: 200 });
  const [tab, setTab] = useState("catalog");
  const [c, setC] = useState({ product_id: "", supplier_sku: "", price: "", lead_time_days: 7 });
  const [p, setP] = useState({ amount: "", method: "bank_transfer", reference: "" });
  const act = async (fn, after) => { try { await fn(); after(); prof.reload(); } catch (e) { notify(errMsg(e), "error"); } };
  const st = prof.data?.stats;
  return (
    <Modal title={`Supplier: ${s.name}`} onClose={onClose} wide>
      {st && <div className="mb-4 grid gap-3 sm:grid-cols-3 lg:grid-cols-6"><Stat label="Orders" value={st.orders} /><Stat label="Purchased" value={money(st.total_purchased)} tone="green" /><Stat label="Outstanding" value={money(st.outstanding)} tone="red" /><Stat label="On-time delivery" value={st.on_time_pct == null ? "n/a" : st.on_time_pct + "%"} tone="amber" />
        <Stat label="Avg delay (days)" value={st.avg_delay_days == null ? "n/a" : st.avg_delay_days} tone="amber" /><Stat label="Fill rate" value={st.fill_rate_pct == null ? "n/a" : st.fill_rate_pct + "%"} tone="green" /></div>}
      <p className="mb-3 text-sm">Rating: <b>{prof.data?.rating ?? 0}/5</b> {prof.data?.notes && <>- {prof.data.notes}</>}</p>
      <Tabs tabs={[{ key: "catalog", label: "Product catalog" }, { key: "pay", label: "Payments" }, { key: "po", label: "Purchase history" }]} value={tab} onChange={setTab} />
      {tab === "catalog" && <>
        <DataTable rows={cat.data || []} loading={cat.loading} columns={[{ key: "sku", label: "SKU" }, { key: "product_name", label: "Product" }, { key: "supplier_sku", label: "Supplier SKU" }, { key: "price", label: "Price" }, { key: "lead_time_days", label: "Lead (days)" },
          { key: "x", label: "", render: (r) => can("suppliers.manage") && <Button variant="ghost" aria-label="Remove" onClick={() => act(() => del(`/suppliers/catalog/${r.id}`), cat.reload)}><Trash2 size={14} /></Button> }]} />
        {can("suppliers.manage") && <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-5">
          <select className="input" aria-label="Catalog product" value={c.product_id} onChange={(e) => setC({ ...c, product_id: e.target.value })}><option value="">Product...</option>{(prods.data || []).map((x) => <option key={x.id} value={x.id}>{x.sku} - {x.name}</option>)}</select>
          <input className="input" placeholder="Supplier SKU" value={c.supplier_sku} onChange={(e) => setC({ ...c, supplier_sku: e.target.value })} />
          <input className="input" type="number" placeholder="Price" value={c.price} onChange={(e) => setC({ ...c, price: e.target.value })} />
          <input className="input" type="number" placeholder="Lead days" value={c.lead_time_days} onChange={(e) => setC({ ...c, lead_time_days: e.target.value })} />
          <Button onClick={() => act(() => post(`/suppliers/${s.id}/catalog`, { product_id: Number(c.product_id), supplier_sku: c.supplier_sku, price: Number(c.price || 0), lead_time_days: Number(c.lead_time_days || 0) }), cat.reload)}>Add</Button></div>}</>}
      {tab === "pay" && <>
        <DataTable rows={pays.rows} loading={pays.loading} columns={[{ key: "paid_at", label: "Date", render: (r) => r.paid_at.slice(0, 10) }, { key: "amount", label: "Amount", render: (r) => money(r.amount) }, { key: "method", label: "Method" }, { key: "reference", label: "Reference" }]} />
        {can("suppliers.manage") && <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
          <input className="input" type="number" step="0.01" placeholder="Amount" value={p.amount} onChange={(e) => setP({ ...p, amount: e.target.value })} />
          <input className="input" placeholder="Method" value={p.method} onChange={(e) => setP({ ...p, method: e.target.value })} />
          <input className="input" placeholder="Reference" value={p.reference} onChange={(e) => setP({ ...p, reference: e.target.value })} />
          <Button onClick={() => act(() => post(`/suppliers/${s.id}/payments`, { ...p, amount: Number(p.amount) }), () => { setP({ amount: "", method: "bank_transfer", reference: "" }); pays.reload(); })}>Record payment</Button></div>}</>}
      {tab === "po" && <><DataTable rows={pos.rows} loading={pos.loading} columns={[{ key: "po_number", label: "PO" }, { key: "order_date", label: "Date", render: (r) => r.order_date.slice(0, 10) }, { key: "status", label: "Status", render: (r) => <Badge value={r.status} /> }, { key: "total", label: "Total", render: (r) => money(r.total) }]} /><Pagination meta={pos.meta} onPage={pos.setPage} /></>}
    </Modal>
  );
}

export function Suppliers() {
  const [sel, setSel] = useState(null);
  return (
    <>
      <CrudPage title="Suppliers" subtitle="Supplier profiles, catalogs, ratings and payments" entity="supplier" endpoint="/suppliers" manage="suppliers.manage" initialSort={{ sort: "name", order: "asc" }} defaults={{ is_active: true, rating: 0 }}
        columns={[{ key: "code", label: "Code", sortable: true }, { key: "name", label: "Name", sortable: true }, { key: "contact_person", label: "Contact" }, { key: "phone", label: "Phone" }, { key: "rating", label: "Rating", sortable: true, render: (r) => `${r.rating ?? 0} / 5` }, { key: "is_active", label: "Status", render: yesNo }]}
        fields={[{ name: "code", label: "Code", required: true }, { name: "name", label: "Company name", required: true }, { name: "contact_person", label: "Contact person" }, { name: "email", label: "Email", type: "email" }, { name: "phone", label: "Phone" },
          { name: "address", label: "Address" }, { name: "city", label: "City" }, { name: "country", label: "Country" }, { name: "tax_no", label: "Tax number" }, { name: "payment_terms", label: "Payment terms" },
          { name: "rating", label: "Rating (0-5)", type: "number", step: "0.1" }, { name: "is_active", label: "Active", type: "checkbox" }, { name: "notes", label: "Notes", type: "textarea" }]}
        rowActions={(r) => <Button variant="ghost" onClick={() => setSel(r)} aria-label={`Profile ${r.name}`}><Eye size={14} /></Button>} />
      {sel && <SupplierProfile s={sel} onClose={() => setSel(null)} />}
    </>
  );
}

function CustomerProfile({ c, onClose }) {
  const { money } = useApp();
  const prof = useFetch(`/customers/${c.id}/profile`);
  const orders = useList(`/customers/${c.id}/orders`);
  const st = prof.data?.stats;
  return (
    <Modal title={`Customer: ${c.name}`} onClose={onClose} wide>
      {st && <div className="mb-4 grid gap-3 sm:grid-cols-4"><Stat label="Orders" value={st.orders} /><Stat label="Total spent" value={money(st.total_spent)} tone="green" /><Stat label="Avg order" value={money(st.average_order)} tone="amber" /><Stat label="Last order" value={st.last_order ? st.last_order.slice(0, 10) : "-"} /></div>}
      <DataTable rows={orders.rows} loading={orders.loading} columns={[{ key: "so_number", label: "Order" }, { key: "order_date", label: "Date", render: (r) => r.order_date.slice(0, 10) }, { key: "status", label: "Status", render: (r) => <Badge value={r.status} /> }, { key: "total", label: "Total", render: (r) => money(r.total) }]} />
      <Pagination meta={orders.meta} onPage={orders.setPage} />
    </Modal>
  );
}

export function Customers() {
  const [sel, setSel] = useState(null);
  return (
    <>
      <CrudPage title="Customers" subtitle="Profiles, order history and purchase statistics" entity="customer" endpoint="/customers" manage="customers.manage" initialSort={{ sort: "name", order: "asc" }} defaults={{ is_active: true }}
        columns={[{ key: "code", label: "Code", sortable: true }, { key: "name", label: "Name", sortable: true }, { key: "company", label: "Company" }, { key: "email", label: "Email" }, { key: "phone", label: "Phone" }, { key: "city", label: "City" }, { key: "is_active", label: "Status", render: yesNo }]}
        filters={[{ name: "is_active", label: "Any status", options: [{ value: "true", label: "Active" }, { value: "false", label: "Inactive" }] }]}
        fields={[{ name: "code", label: "Code", required: true }, { name: "name", label: "Name", required: true }, { name: "company", label: "Company" }, { name: "email", label: "Email", type: "email" }, { name: "phone", label: "Phone" }, { name: "address", label: "Address" }, { name: "city", label: "City" },
          { name: "is_active", label: "Active", type: "checkbox" }, { name: "notes", label: "Notes", type: "textarea" }]}
        rowActions={(r) => <Button variant="ghost" onClick={() => setSel(r)} aria-label={`Profile ${r.name}`}><Eye size={14} /></Button>} />
      {sel && <CustomerProfile c={sel} onClose={() => setSel(null)} />}
    </>
  );
}

function RolesModal({ onClose }) {
  const { notify } = useApp();
  const roles = useFetch("/admin/roles");
  const perms = useFetch("/admin/permissions");
  const [rid, setRid] = useState("");
  const [sel, setSel] = useState([]);
  const role = (roles.data || []).find((r) => String(r.id) === String(rid));
  const pick = (id) => { setRid(id); setSel((roles.data || []).find((r) => String(r.id) === String(id))?.permissions || []); };
  const toggle = (c) => setSel(sel.includes(c) ? sel.filter((x) => x !== c) : [...sel, c]);
  return (
    <Modal title="Roles & permissions" onClose={onClose} wide footer={<><Button variant="ghost" onClick={onClose}>Close</Button>
      <Button disabled={!role || role.name === "Super Admin"} onClick={async () => { try { await put(`/admin/roles/${rid}/permissions`, { permissions: sel }); notify("Permissions saved"); roles.reload(); } catch (e) { notify(errMsg(e), "error"); } }}>Save</Button></>}>
      <Input label="Role" type="select" value={rid} onChange={(e) => pick(e.target.value)} options={(roles.data || []).map((r) => ({ value: r.id, label: r.name }))} />
      {role?.name === "Super Admin" && <p className="mt-2 text-sm text-amber-600">Super Admin always has every permission.</p>}
      <div className="mt-3 grid gap-1 sm:grid-cols-2">{(perms.data || []).map((p) => (
        <label key={p.code} className="flex items-center gap-2 text-sm"><input type="checkbox" disabled={!role || role.name === "Super Admin"} checked={sel.includes(p.code)} onChange={() => toggle(p.code)} />{p.description} <code className="text-xs text-slate-400">{p.code}</code></label>))}</div>
    </Modal>
  );
}

export function UsersPage() {
  const [roles, setRoles] = useState(false);
  return (
    <>
      <CrudPage title="Users & Roles" subtitle="Accounts, roles and activation (deactivate instead of delete to keep the audit trail)" entity="user" endpoint="/admin/users" manage="users.manage" noDelete initialSort={{}} defaults={{ is_active: true }}
        beforeSubmit={(b, editing) => { if (editing && !b.password) delete b.password; return b; }}
        columns={[{ key: "name", label: "Name" }, { key: "email", label: "Email" }, { key: "role_name", label: "Role" }, { key: "last_login", label: "Last login", render: (r) => r.last_login ? r.last_login.slice(0, 16).replace("T", " ") : "never" }, { key: "is_active", label: "Status", render: yesNo }]}
        filters={[{ name: "role_id", label: "All roles", optionsFrom: true }, { name: "is_active", label: "Any status", options: [{ value: "true", label: "Active" }, { value: "false", label: "Deactivated" }] }]}
        fields={[{ name: "name", label: "Full name", required: true }, { name: "email", label: "Email", type: "email", required: true, createOnly: true }, { name: "password", label: "Password", type: "password", hint: "Leave blank when editing to keep the current password" },
          { name: "role_id", label: "Role", type: "select", optionsUrl: "/admin/roles", required: true }, { name: "phone", label: "Phone" }, { name: "is_active", label: "Active", type: "checkbox" }]}
        toolbar={() => <Button variant="ghost" onClick={() => setRoles(true)}><Shield size={14} /> Roles & permissions</Button>} />
      {roles && <RolesModal onClose={() => setRoles(false)} />}
    </>
  );
}
