import { useState } from "react";
import { Plus, Eye } from "lucide-react";
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, Legend, CartesianGrid } from "recharts";
import { post, download, errMsg } from "../api";
import { useApp } from "../context";
import { useFetch, useList } from "../hooks";
import { Button, Modal, Input, Badge, DataTable, Pagination, Tabs, PageHeader, SearchBox, ItemsEditor, cleanItems } from "../ui";
import { uid } from "./Purchases";

const opt = (rows, label) => (rows || []).map((r) => ({ value: r.id, label: label(r) }));

function NewSO({ onClose, onDone }) {
  const { notify, settings } = useApp();
  const custs = useFetch("/customers", { per_page: 200, is_active: true });
  const whs = useFetch("/warehouses", { per_page: 100, is_active: true });
  const prods = useFetch("/products", { per_page: 200, status: "active" });
  const [f, setF] = useState({ customer_id: "", warehouse_id: settings.default_warehouse_id || "", notes: "" });
  const [items, setItems] = useState([{ product_id: "", quantity: 1, unit_price: "", discount: 0 }]);
  const submit = async () => {
    try { await post("/sales", { customer_id: Number(f.customer_id), warehouse_id: Number(f.warehouse_id), notes: f.notes, items: cleanItems(items, ["price", "discount"]) }); notify("Sales order created"); onDone(); onClose(); }
    catch (e) { notify(errMsg(e), "error"); }
  };
  return (
    <Modal title="New sales order" wide onClose={onClose} footer={<><Button variant="ghost" onClick={onClose}>Cancel</Button><Button onClick={submit}>Create order</Button></>}>
      <div className="mb-3 grid gap-3 sm:grid-cols-2"><Input label="Customer" type="select" value={f.customer_id} onChange={(e) => setF({ ...f, customer_id: e.target.value })} options={opt(custs.data, (c) => c.name)} />
        <Input label="Ship from warehouse" type="select" value={f.warehouse_id} onChange={(e) => setF({ ...f, warehouse_id: e.target.value })} options={opt(whs.data, (w) => w.name)} /></div>
      <ItemsEditor items={items} onChange={setItems} products={prods.data || []} priceField="selling_price" showDiscount />
      <div className="mt-3"><Input label="Notes" type="textarea" value={f.notes} onChange={(e) => setF({ ...f, notes: e.target.value })} /></div>
    </Modal>
  );
}

function SODetail({ id, onClose, onChanged }) {
  const { can, notify, money } = useApp();
  const { data: so, reload } = useFetch(`/sales/${id}`);
  const [ship, setShip] = useState({ carrier: "", tracking_no: "" });
  const [pay, setPay] = useState("");
  const [ret, setRet] = useState(null);
  const [key] = useState(uid());
  const run = async (fn, msg) => { try { await fn(); notify(msg); reload(); onChanged(); } catch (e) { notify(errMsg(e), "error"); } };
  if (!so) return <Modal title="Sales order" onClose={onClose}>Loading...</Modal>;
  const proc = can("sales.process");
  return (
    <Modal title={`${so.so_number} - ${so.customer_name}`} wide onClose={onClose}>
      <div className="mb-3 flex flex-wrap items-center gap-3 text-sm"><Badge value={so.status} /><Badge value={so.payment_status} /><span>Warehouse: <b>{so.warehouse_name}</b></span><span>{so.order_date.slice(0, 10)}</span>
        {so.tracking_no && <span>Tracking: <b>{so.carrier} {so.tracking_no}</b></span>}{so.delivered_at && <span>Delivered {so.delivered_at.slice(0, 10)}</span>}</div>
      <DataTable rows={so.items} columns={[{ key: "sku", label: "SKU" }, { key: "product_name", label: "Product" }, { key: "quantity", label: "Qty" }, { key: "unit_price", label: "Price", render: (r) => money(r.unit_price) }, { key: "discount", label: "Disc %" }, { key: "tax_rate", label: "Tax %" }, { key: "line_total", label: "Total", render: (r) => money(r.line_total) }]} />
      <div className="mt-3 text-right text-sm">Subtotal {money(so.subtotal)} | Discount -{money(so.discount_total)} | Tax {money(so.tax_total)} | <b>Total {money(so.total)}</b> | Paid {money(so.paid_amount)}{so.refunded_amount > 0 && ` | Refunded ${money(so.refunded_amount)}`}</div>
      {so.returns?.length > 0 && <div className="mt-3 text-sm"><b>Returns:</b> {so.returns.map((r) => <span key={r.id} className="mr-2">{r.return_number} <Badge value={r.status} /></span>)}</div>}
      {ret && <div className="mt-4 rounded-lg border p-3 dark:border-slate-600"><h4 className="mb-2 font-semibold">Request return</h4>
        {so.items.map((i) => <div key={i.id} className="mb-2 grid grid-cols-3 gap-2"><span className="self-center text-sm">{i.product_name}</span>
          <input aria-label={`Return qty ${i.product_name}`} type="number" min="0" max={i.quantity} className="input" value={ret.lines[i.product_id]?.quantity ?? ""} placeholder="Qty" onChange={(e) => setRet({ ...ret, lines: { ...ret.lines, [i.product_id]: { ...ret.lines[i.product_id], quantity: e.target.value } } })} />
          <select aria-label="Condition" className="input" value={ret.lines[i.product_id]?.condition || "good"} onChange={(e) => setRet({ ...ret, lines: { ...ret.lines, [i.product_id]: { ...ret.lines[i.product_id], condition: e.target.value } } })}><option value="good">Good (restock)</option><option value="damaged">Damaged</option></select></div>)}
        <Input label="Reason" value={ret.reason} onChange={(e) => setRet({ ...ret, reason: e.target.value })} />
        <Button className="mt-2" onClick={() => run(async () => { await post(`/sales/${id}/returns`, { reason: ret.reason, items: Object.entries(ret.lines).filter(([, v]) => Number(v.quantity) > 0).map(([pid, v]) => ({ product_id: Number(pid), quantity: Number(v.quantity), condition: v.condition || "good" })) }); setRet(null); }, "Return requested")}>Submit return request</Button></div>}
      <div className="mt-4 flex flex-wrap items-end gap-2">
        {so.status === "pending" && proc && <Button onClick={() => run(() => post(`/sales/${id}/confirm`), "Confirmed - stock reserved")}>Confirm & reserve stock</Button>}
        {so.status === "confirmed" && proc && <><input aria-label="Carrier" className="input w-32" placeholder="Carrier" value={ship.carrier} onChange={(e) => setShip({ ...ship, carrier: e.target.value })} />
          <input aria-label="Tracking number" className="input w-40" placeholder="Tracking no" value={ship.tracking_no} onChange={(e) => setShip({ ...ship, tracking_no: e.target.value })} />
          <Button variant="success" onClick={() => run(() => post(`/sales/${id}/dispatch`, { ...ship, idempotency_key: key }), "Dispatched - stock deducted")}>Dispatch</Button></>}
        {so.status === "dispatched" && proc && <Button variant="success" onClick={() => run(() => post(`/sales/${id}/deliver`), "Marked delivered")}>Mark delivered</Button>}
        {["pending", "confirmed"].includes(so.status) && can("sales.create", "sales.process") && <Button variant="ghost" onClick={() => run(() => post(`/sales/${id}/cancel`), "Order cancelled")}>Cancel order</Button>}
        {["dispatched", "delivered", "returned"].includes(so.status) && proc && !ret && <Button variant="ghost" onClick={() => setRet({ reason: "", lines: {} })}>Request return</Button>}
        {proc && ["dispatched", "delivered"].includes(so.status) && <><input aria-label="Payment amount" type="number" step="0.01" className="input w-32" placeholder="Payment" value={pay} onChange={(e) => setPay(e.target.value)} /><Button variant="ghost" onClick={() => run(async () => { await post(`/sales/${id}/payment`, { amount: Number(pay) }); setPay(""); }, "Payment recorded")}>Record payment</Button></>}
        {so.invoice_no && <Button variant="ghost" onClick={() => download(`/sales/${id}/invoice.pdf`, {}, `${so.invoice_no}.pdf`)}>Invoice {so.invoice_no}</Button>}
      </div>
    </Modal>
  );
}

export default function Sales() {
  const { can, notify, money } = useApp();
  const [tab, setTab] = useState("orders");
  const [adding, setAdding] = useState(false);
  const [view, setView] = useState(null);
  const list = useList("/sales");
  const rets = useList("/sales/returns");
  const an = useFetch("/sales/analytics");
  const act = async (url, msg) => { try { await post(url); notify(msg); rets.reload(); list.reload(); } catch (e) { notify(errMsg(e), "error"); } };
  return (
    <div>
      <PageHeader title="Sales & orders" subtitle="Orders, reservation, dispatch, delivery, invoices and returns">{can("sales.create") && <Button onClick={() => setAdding(true)}><Plus size={16} /> New sales order</Button>}</PageHeader>
      <Tabs value={tab} onChange={setTab} tabs={[{ key: "orders", label: "Orders" }, { key: "returns", label: "Returns & refunds" }, { key: "analytics", label: "Analytics" }]} />
      {tab === "orders" && <div className="card"><div className="mb-3 flex flex-wrap gap-2"><SearchBox onSearch={(q) => list.set({ q })} placeholder="Search order number" />
        <select aria-label="Status" className="input w-auto" onChange={(e) => list.set({ status: e.target.value })}><option value="">All statuses</option>{["pending", "confirmed", "dispatched", "delivered", "returned", "cancelled"].map((s) => <option key={s}>{s}</option>)}</select>
        <input aria-label="From date" type="date" className="input w-auto" onChange={(e) => list.set({ date_from: e.target.value })} /><input aria-label="To date" type="date" className="input w-auto" onChange={(e) => list.set({ date_to: e.target.value })} /></div>
        <DataTable loading={list.loading} rows={list.rows} columns={[{ key: "so_number", label: "Order #" }, { key: "order_date", label: "Date", render: (r) => r.order_date.slice(0, 10) }, { key: "customer_name", label: "Customer" }, { key: "status", label: "Status", render: (r) => <Badge value={r.status} /> }, { key: "payment_status", label: "Payment", render: (r) => <Badge value={r.payment_status} /> },
          { key: "total", label: "Total", render: (r) => money(r.total) }, { key: "x", label: "", render: (r) => <Button variant="ghost" aria-label={`Open ${r.so_number}`} onClick={() => setView(r.id)}><Eye size={14} /></Button> }]} /><Pagination meta={list.meta} onPage={list.setPage} /></div>}
      {tab === "returns" && <div className="card"><DataTable loading={rets.loading} rows={rets.rows} empty="No returns" columns={[{ key: "return_number", label: "Return #" }, { key: "so_number", label: "Order" }, { key: "customer_name", label: "Customer" }, { key: "reason", label: "Reason" }, { key: "refund_amount", label: "Refund", render: (r) => money(r.refund_amount) }, { key: "status", label: "Status", render: (r) => <Badge value={r.status} /> },
        { key: "x", label: "", render: (r) => r.status === "requested" && can("sales.process") && <div className="flex gap-1"><Button variant="success" onClick={() => act(`/sales/returns/${r.id}/approve`, "Return approved and refund recorded")}>Approve</Button><Button variant="ghost" onClick={() => act(`/sales/returns/${r.id}/reject`, "Return rejected")}>Reject</Button></div> }]} /><Pagination meta={rets.meta} onPage={rets.setPage} /></div>}
      {tab === "analytics" && an.data && <div className="grid gap-4 lg:grid-cols-2"><div className="card"><h3 className="mb-2 font-semibold">Revenue vs cost of goods</h3><ResponsiveContainer width="100%" height={260}><BarChart data={an.data.monthly}><CartesianGrid strokeDasharray="3 3" opacity={0.3} /><XAxis dataKey="month" fontSize={11} /><YAxis fontSize={11} /><Tooltip formatter={(v) => money(v)} /><Legend /><Bar dataKey="revenue" fill="#10b981" radius={[4, 4, 0, 0]} /><Bar dataKey="cogs" fill="#f59e0b" radius={[4, 4, 0, 0]} /></BarChart></ResponsiveContainer></div>
        <div className="card"><h3 className="mb-2 font-semibold">Top customers</h3>{an.data.top_customers.map((c) => <div key={c.customer} className="flex justify-between border-b py-1.5 text-sm dark:border-slate-700"><span>{c.customer}</span><b>{money(c.total)}</b></div>)}
          <h3 className="mb-2 mt-4 font-semibold">Orders by status</h3>{an.data.by_status.map((s) => <div key={s.status} className="flex justify-between py-1 text-sm"><Badge value={s.status} /><b>{s.count}</b></div>)}</div></div>}
      {adding && <NewSO onClose={() => setAdding(false)} onDone={list.reload} />}
      {view && <SODetail id={view} onClose={() => setView(null)} onChanged={() => { list.reload(); rets.reload(); }} />}
    </div>
  );
}
