import { useState } from "react";
import { Plus, Eye } from "lucide-react";
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid } from "recharts";
import { get, post, put, download, errMsg } from "../api";
import { useApp } from "../context";
import { useFetch, useList } from "../hooks";
import { Button, Modal, Input, Badge, DataTable, Pagination, Tabs, PageHeader, SearchBox, ItemsEditor, cleanItems } from "../ui";

const opt = (rows, label) => (rows || []).map((r) => ({ value: r.id, label: label(r) }));
export const uid = () => (crypto.randomUUID ? crypto.randomUUID() : String(Math.random()).slice(2) + Date.now());

function NewPO({ onClose, onDone, initial }) {
  const { notify, settings } = useApp();
  const sups = useFetch("/suppliers", { per_page: 200, is_active: true });
  const whs = useFetch("/warehouses", { per_page: 100, is_active: true });
  const prods = useFetch("/products", { per_page: 200, status: "active" });
  const [f, setF] = useState({ supplier_id: initial?.supplier_id || "", warehouse_id: settings.default_warehouse_id || "", expected_date: "", notes: "" });
  const [items, setItems] = useState(initial?.items || [{ product_id: "", quantity: 1, unit_price: "" }]);
  const [busy, setBusy] = useState(false);
  const submit = async () => {
    setBusy(true);
    try { await post("/purchases", { supplier_id: Number(f.supplier_id), warehouse_id: Number(f.warehouse_id), expected_date: f.expected_date || undefined, notes: f.notes, items: cleanItems(items, ["price"]) }); notify("Purchase request created and sent for approval"); onDone(); onClose(); }
    catch (e) { notify(errMsg(e), "error"); } finally { setBusy(false); }
  };
  return (
    <Modal title="New purchase request" wide onClose={onClose} footer={<><Button variant="ghost" onClick={onClose}>Cancel</Button><Button disabled={busy} onClick={submit}>Submit for approval</Button></>}>
      <div className="mb-3 grid gap-3 sm:grid-cols-3">
        <Input label="Supplier" type="select" value={f.supplier_id} onChange={(e) => setF({ ...f, supplier_id: e.target.value })} options={opt(sups.data, (s) => s.name)} />
        <Input label="Deliver to warehouse" type="select" value={f.warehouse_id} onChange={(e) => setF({ ...f, warehouse_id: e.target.value })} options={opt(whs.data, (w) => w.name)} />
        <Input label="Expected delivery" type="date" value={f.expected_date} onChange={(e) => setF({ ...f, expected_date: e.target.value })} /></div>
      <ItemsEditor items={items} onChange={setItems} products={prods.data || []} priceField="purchase_price" />
      <div className="mt-3"><Input label="Notes" type="textarea" value={f.notes} onChange={(e) => setF({ ...f, notes: e.target.value })} /></div>
    </Modal>
  );
}


function NewRequest({ onClose, onDone }) {
  const { notify, settings } = useApp();
  const whs = useFetch("/warehouses", { per_page: 100, is_active: true });
  const prods = useFetch("/products", { per_page: 200, status: "active" });
  const [f, setF] = useState({ warehouse_id: settings.default_warehouse_id || "", priority: "normal", needed_by: "", reason: "" });
  const [items, setItems] = useState([{ product_id: "", quantity: 1 }]);
  const submit = async () => {
    try { await post("/purchases/requests", { warehouse_id: Number(f.warehouse_id), priority: f.priority, needed_by: f.needed_by || undefined, reason: f.reason, items: cleanItems(items, []) }); notify("Request submitted for approval"); onDone(); onClose(); }
    catch (e) { notify(errMsg(e), "error"); }
  };
  return (
    <Modal title="New purchase request" wide onClose={onClose} footer={<><Button variant="ghost" onClick={onClose}>Cancel</Button><Button onClick={submit}>Submit request</Button></>}>
      <div className="mb-3 grid gap-3 sm:grid-cols-3">
        <Input label="Needed at warehouse" type="select" value={f.warehouse_id} onChange={(e) => setF({ ...f, warehouse_id: e.target.value })} options={opt(whs.data, (w) => w.name)} />
        <Input label="Priority" type="select" value={f.priority} onChange={(e) => setF({ ...f, priority: e.target.value })} options={["low", "normal", "high"].map((v) => ({ value: v, label: v }))} />
        <Input label="Needed by" type="date" value={f.needed_by} onChange={(e) => setF({ ...f, needed_by: e.target.value })} /></div>
      <ItemsEditor items={items} onChange={setItems} products={prods.data || []} showPrice={false} />
      <div className="mt-3"><Input label="Reason / justification" value={f.reason} onChange={(e) => setF({ ...f, reason: e.target.value })} /></div>
    </Modal>
  );
}

function RequestDetail({ id, onClose, onChanged }) {
  const { can, notify } = useApp();
  const { data: r, reload } = useFetch(`/purchases/requests/${id}`);
  const sups = useFetch("/suppliers", { per_page: 200, is_active: true });
  const [sup, setSup] = useState("");
  const run = async (fn, msg) => { try { await fn(); notify(msg); reload(); onChanged(); } catch (e) { notify(errMsg(e), "error"); } };
  if (!r) return <Modal title="Purchase request" onClose={onClose}>Loading...</Modal>;
  return (
    <Modal title={`${r.request_number} (${r.priority} priority)`} wide onClose={onClose}>
      <div className="mb-3 flex flex-wrap items-center gap-3 text-sm"><Badge value={r.status} /><span>By {r.requester_name}</span><span>For {r.warehouse_name}</span>{r.needed_by && <span>Needed by {r.needed_by}</span>}
        {r.po_number && <span>PO: <b>{r.po_number}</b></span>}{r.rejection_reason && <span className="text-red-600">Rejected: {r.rejection_reason}</span>}</div>
      {r.reason && <p className="mb-3 text-sm text-slate-500">{r.reason}</p>}
      <DataTable rows={r.items} columns={[{ key: "sku", label: "SKU" }, { key: "product_name", label: "Product" }, { key: "quantity", label: "Quantity" }, { key: "note", label: "Note" }]} />
      <div className="mt-4 flex flex-wrap items-end gap-2">
        {r.status === "pending" && can("purchases.approve") && <><Button variant="success" onClick={() => run(() => post(`/purchases/requests/${id}/approve`), "Request approved")}>Approve</Button>
          <Button variant="danger" onClick={() => { const reason = prompt("Reason for rejection?"); if (reason !== null) run(() => post(`/purchases/requests/${id}/reject`, { reason }), "Request rejected"); }}>Reject</Button></>}
        {r.status === "approved" && can("purchases.create") && <><select aria-label="Supplier for PO" className="input w-56" value={sup} onChange={(e) => setSup(e.target.value)}><option value="">Choose supplier...</option>{(sups.data || []).map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</select>
          <Button disabled={!sup} onClick={() => run(() => post(`/purchases/requests/${id}/convert`, { supplier_id: Number(sup) }), "Purchase order generated")}>Generate purchase order</Button></>}
        {["pending", "approved"].includes(r.status) && can("purchases.create", "purchases.approve") && <Button variant="ghost" onClick={() => run(() => post(`/purchases/requests/${id}/cancel`), "Request cancelled")}>Cancel request</Button>}
      </div>
    </Modal>
  );
}

function PODetail({ id, onClose, onChanged }) {
  const { can, notify, money } = useApp();
  const { data: po, reload } = useFetch(`/purchases/${id}`);
  const [recv, setRecv] = useState(null);
  const [rkey, setRkey] = useState("");
  const run = async (fn, msg) => { try { await fn(); notify(msg); reload(); onChanged(); } catch (e) { notify(errMsg(e), "error"); } };
  if (!po) return <Modal title="Purchase order" onClose={onClose}>Loading...</Modal>;
  const startReceive = () => { setRkey(uid()); setRecv(Object.fromEntries(po.items.map((i) => [i.id, { quantity: i.quantity - i.received_qty, batch_no: "", expiry_date: "" }]))); };
  return (
    <Modal title={`${po.po_number} - ${po.supplier_name}`} wide onClose={onClose}>
      <div className="mb-3 flex flex-wrap items-center gap-3 text-sm"><Badge value={po.status} /><span>Warehouse: <b>{po.warehouse_name}</b></span><span>Date: {po.order_date.slice(0, 10)}</span>{po.expected_date && <span>Expected: {po.expected_date}</span>}
        {po.rejection_reason && <span className="text-red-600">Rejected: {po.rejection_reason}</span>}</div>
      <DataTable rows={po.items} columns={[{ key: "sku", label: "SKU" }, { key: "product_name", label: "Product" }, { key: "quantity", label: "Ordered" }, { key: "received_qty", label: "Received" }, { key: "unit_price", label: "Unit price", render: (r) => money(r.unit_price) }, { key: "tax_rate", label: "Tax %" }, { key: "line_total", label: "Total", render: (r) => money(r.line_total) }]} />
      <div className="mt-3 text-right text-sm">Subtotal {money(po.subtotal)} | Tax {money(po.tax_total)} | <b>Total {money(po.total)}</b> | Paid {money(po.paid)}</div>
      {recv && <div className="mt-4 rounded-lg border p-3 dark:border-slate-600"><h4 className="mb-2 font-semibold">Receive goods (partial deliveries allowed)</h4>
        {po.items.filter((i) => i.quantity > i.received_qty).map((i) => <div key={i.id} className="mb-2 grid grid-cols-2 gap-2 sm:grid-cols-4"><div className="self-center text-sm">{i.product_name} <span className="text-slate-500">(max {i.quantity - i.received_qty})</span></div>
          <input aria-label={`Receive qty ${i.product_name}`} type="number" min="0" className="input" value={recv[i.id].quantity} onChange={(e) => setRecv({ ...recv, [i.id]: { ...recv[i.id], quantity: e.target.value } })} />
          <input aria-label="Batch no" className="input" placeholder="Batch / lot no" value={recv[i.id].batch_no} onChange={(e) => setRecv({ ...recv, [i.id]: { ...recv[i.id], batch_no: e.target.value } })} />
          <input aria-label="Expiry" type="date" className="input" value={recv[i.id].expiry_date} onChange={(e) => setRecv({ ...recv, [i.id]: { ...recv[i.id], expiry_date: e.target.value } })} /></div>)}
        <Button variant="success" onClick={() => run(async () => { await post(`/purchases/${id}/receive`, { idempotency_key: rkey, items: Object.entries(recv).map(([item_id, v]) => ({ item_id: Number(item_id), quantity: Number(v.quantity || 0), batch_no: v.batch_no || undefined, expiry_date: v.expiry_date || undefined })) }); setRecv(null); }, "Goods received into stock")}>Confirm receipt</Button></div>}
      <div className="mt-4 flex flex-wrap gap-2">
        {po.status === "pending_approval" && can("purchases.approve") && <><Button variant="success" onClick={() => run(() => post(`/purchases/${id}/approve`), "Approved")}>Approve</Button>
          <Button variant="danger" onClick={() => { const reason = prompt("Reason for rejection?"); if (reason !== null) run(() => post(`/purchases/${id}/reject`, { reason }), "Rejected"); }}>Reject</Button></>}
        {["approved", "partially_received"].includes(po.status) && can("purchases.receive") && !recv && <Button onClick={startReceive}>Receive goods</Button>}
        {["pending_approval", "approved"].includes(po.status) && can("purchases.create", "purchases.approve") && <Button variant="ghost" onClick={() => run(() => post(`/purchases/${id}/cancel`), "Cancelled")}>Cancel order</Button>}
        {["received", "partially_received"].includes(po.status) && !po.invoice_no && <Button variant="ghost" onClick={() => run(() => post(`/purchases/${id}/invoice`), "Invoice generated")}>Generate invoice</Button>}
        {po.invoice_no && <Button variant="ghost" onClick={() => download(`/purchases/${id}/invoice.pdf`, {}, `${po.invoice_no}.pdf`)}>Download invoice {po.invoice_no}</Button>}
      </div>
    </Modal>
  );
}

export default function Purchases() {
  const { can, money } = useApp();
  const [tab, setTab] = useState("orders");
  const [adding, setAdding] = useState(false);
  const [view, setView] = useState(null);
  const [addingReq, setAddingReq] = useState(false);
  const [viewReq, setViewReq] = useState(null);
  const reqs = useList("/purchases/requests");
  const list = useList("/purchases");
  const an = useFetch("/purchases/analytics");
  const reorder = useFetch("/inventory/reorder");
  return (
    <div>
      <PageHeader title="Purchase management" subtitle="Requests, approvals, receiving, invoices and analytics">{can("purchases.create") && <Button variant="ghost" onClick={() => setAddingReq(true)}><Plus size={16} /> New request</Button>}{can("purchases.create") && <Button onClick={() => setAdding(true)}><Plus size={16} /> New purchase order</Button>}</PageHeader>
      <Tabs value={tab} onChange={setTab} tabs={[{ key: "requests", label: "Purchase requests" }, { key: "orders", label: "Purchase orders" }, { key: "analytics", label: "Analytics" }, ...(can("inventory.view") ? [{ key: "reorder", label: "Reorder suggestions" }] : [])]} />
      {tab === "requests" && <div className="card"><div className="mb-3 flex flex-wrap gap-2"><SearchBox onSearch={(q) => reqs.set({ q })} placeholder="Search request number" />
        <select aria-label="Request status" className="input w-auto" onChange={(e) => reqs.set({ status: e.target.value })}><option value="">All statuses</option>{["pending", "approved", "converted", "rejected", "cancelled"].map((x) => <option key={x}>{x}</option>)}</select></div>
        <DataTable loading={reqs.loading} rows={reqs.rows} empty="No purchase requests" columns={[{ key: "request_number", label: "Request #" }, { key: "created_at", label: "Date", render: (r) => r.created_at.slice(0, 10) }, { key: "requester_name", label: "Requested by" }, { key: "warehouse_name", label: "Warehouse" },
          { key: "priority", label: "Priority", render: (r) => <Badge value={r.priority === "high" ? "open" : r.priority === "low" ? "inactive" : "pending"} /> }, { key: "status", label: "Status", render: (r) => <Badge value={r.status} /> }, { key: "po_number", label: "PO" },
          { key: "x", label: "", render: (r) => <Button variant="ghost" aria-label={`Open ${r.request_number}`} onClick={() => setViewReq(r.id)}><Eye size={14} /></Button> }]} /><Pagination meta={reqs.meta} onPage={reqs.setPage} /></div>}
      {tab === "orders" && <div className="card"><div className="mb-3 flex flex-wrap gap-2"><SearchBox onSearch={(q) => list.set({ q })} placeholder="Search PO number" />
        <select aria-label="Status" className="input w-auto" onChange={(e) => list.set({ status: e.target.value })}><option value="">All statuses</option>{["pending_approval", "approved", "partially_received", "received", "rejected", "cancelled"].map((s) => <option key={s} value={s}>{s.replace(/_/g, " ")}</option>)}</select>
        <input aria-label="From date" type="date" className="input w-auto" onChange={(e) => list.set({ date_from: e.target.value })} /><input aria-label="To date" type="date" className="input w-auto" onChange={(e) => list.set({ date_to: e.target.value })} /></div>
        <DataTable loading={list.loading} rows={list.rows} columns={[{ key: "po_number", label: "PO #" }, { key: "order_date", label: "Date", render: (r) => r.order_date.slice(0, 10) }, { key: "supplier_name", label: "Supplier" }, { key: "warehouse_name", label: "Warehouse" }, { key: "status", label: "Status", render: (r) => <Badge value={r.status} /> },
          { key: "received_pct", label: "Received", render: (r) => `${r.received_pct}%` }, { key: "total", label: "Total", render: (r) => money(r.total) }, { key: "x", label: "", render: (r) => <Button variant="ghost" aria-label={`Open ${r.po_number}`} onClick={() => setView(r.id)}><Eye size={14} /></Button> }]} />
        <Pagination meta={list.meta} onPage={list.setPage} /></div>}
      {tab === "analytics" && an.data && <div className="grid gap-4 lg:grid-cols-2"><div className="card"><h3 className="mb-2 font-semibold">Monthly purchase spend</h3><ResponsiveContainer width="100%" height={260}><BarChart data={an.data.monthly}><CartesianGrid strokeDasharray="3 3" opacity={0.3} /><XAxis dataKey="month" fontSize={11} /><YAxis fontSize={11} /><Tooltip formatter={(v) => money(v)} /><Bar dataKey="total" fill="#6366f1" radius={[4, 4, 0, 0]} /></BarChart></ResponsiveContainer></div>
        <div className="card"><h3 className="mb-2 font-semibold">Top suppliers</h3>{an.data.top_suppliers.map((s) => <div key={s.supplier} className="flex justify-between border-b py-1.5 text-sm dark:border-slate-700"><span>{s.supplier}</span><b>{money(s.total)}</b></div>)}
          <h3 className="mb-2 mt-4 font-semibold">By status</h3>{an.data.by_status.map((s) => <div key={s.status} className="flex justify-between py-1 text-sm"><Badge value={s.status} /><b>{s.count}</b></div>)}</div></div>}
      {tab === "reorder" && <div className="card"><DataTable loading={reorder.loading} rows={reorder.data || []} rowKey="product_id" empty="Nothing needs reordering" columns={[{ key: "sku", label: "SKU" }, { key: "name", label: "Product" }, { key: "available", label: "Available" }, { key: "suggested_qty", label: "Suggested qty" }, { key: "supplier_name", label: "Supplier" }, { key: "estimated_cost", label: "Est. cost", render: (r) => money(r.estimated_cost) }]} />
        <p className="mt-2 text-xs text-slate-500">Use "New purchase request" to order these items.</p></div>}
      {addingReq && <NewRequest onClose={() => setAddingReq(false)} onDone={reqs.reload} />}
      {viewReq && <RequestDetail id={viewReq} onClose={() => setViewReq(null)} onChanged={() => { reqs.reload(); list.reload(); }} />}
      {adding && <NewPO onClose={() => setAdding(false)} onDone={list.reload} />}
      {view && <PODetail id={view} onClose={() => setView(null)} onChanged={list.reload} />}
    </div>
  );
}
