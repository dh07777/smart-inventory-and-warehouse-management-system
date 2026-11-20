import { useState } from "react";
import { Plus, Eye } from "lucide-react";
import { post, errMsg } from "../api";
import { useApp } from "../context";
import { useFetch, useList } from "../hooks";
import { Button, Modal, Input, Badge, DataTable, Pagination, PageHeader, SearchBox, ItemsEditor, cleanItems } from "../ui";
import { uid } from "./Purchases";

const opt = (rows, label) => (rows || []).map((r) => ({ value: r.id, label: label(r) }));

function NewTransfer({ onClose, onDone }) {
  const { notify } = useApp();
  const whs = useFetch("/warehouses", { per_page: 100, is_active: true });
  const prods = useFetch("/products", { per_page: 200, status: "active" });
  const [f, setF] = useState({ from_warehouse_id: "", to_warehouse_id: "", notes: "" });
  const [items, setItems] = useState([{ product_id: "", quantity: 1 }]);
  const submit = async () => {
    try { await post("/transfers", { from_warehouse_id: Number(f.from_warehouse_id), to_warehouse_id: Number(f.to_warehouse_id), notes: f.notes, items: cleanItems(items, []) }); notify("Transfer requested"); onDone(); onClose(); }
    catch (e) { notify(errMsg(e), "error"); }
  };
  return (
    <Modal title="New stock transfer request" wide onClose={onClose} footer={<><Button variant="ghost" onClick={onClose}>Cancel</Button><Button onClick={submit}>Request transfer</Button></>}>
      <div className="mb-3 grid gap-3 sm:grid-cols-2"><Input label="Source warehouse" type="select" value={f.from_warehouse_id} onChange={(e) => setF({ ...f, from_warehouse_id: e.target.value })} options={opt(whs.data, (w) => w.name)} />
        <Input label="Destination warehouse" type="select" value={f.to_warehouse_id} onChange={(e) => setF({ ...f, to_warehouse_id: e.target.value })} options={opt(whs.data, (w) => w.name)} /></div>
      <ItemsEditor items={items} onChange={setItems} products={prods.data || []} showPrice={false} />
      <div className="mt-3"><Input label="Notes" value={f.notes} onChange={(e) => setF({ ...f, notes: e.target.value })} /></div>
    </Modal>
  );
}

function TransferDetail({ id, onClose, onChanged }) {
  const { can, notify } = useApp();
  const { data: t, reload } = useFetch(`/transfers/${id}`);
  const [dq, setDq] = useState(null);
  const [rq, setRq] = useState(null);
  const [note, setNote] = useState("");
  const [key] = useState(uid());
  const run = async (fn, msg) => { try { await fn(); notify(msg); reload(); onChanged(); } catch (e) { notify(errMsg(e), "error"); } };
  if (!t) return <Modal title="Transfer" onClose={onClose}>Loading...</Modal>;
  return (
    <Modal title={`${t.transfer_number}: ${t.from_name} -> ${t.to_name}`} wide onClose={onClose}>
      <div className="mb-3 flex flex-wrap items-center gap-3 text-sm"><Badge value={t.status} />{t.discrepancy_status && <span>Discrepancy: <Badge value={t.discrepancy_status} /></span>}{t.notes && <span className="text-slate-500">{t.notes}</span>}{t.rejection_reason && <span className="text-red-600">Rejected: {t.rejection_reason}</span>}</div>
      <DataTable rows={t.items} columns={[{ key: "sku", label: "SKU" }, { key: "product_name", label: "Product" }, { key: "quantity", label: "Requested" }, { key: "dispatched_qty", label: "Dispatched" }, { key: "received_qty", label: "Received" }, { key: "discrepancy", label: "Discrepancy", render: (r) => (t.status === "received" && r.discrepancy ? <b className="text-red-600">{r.discrepancy}</b> : "-") }]} />
      {t.resolution_note && <p className="mt-2 text-sm">Resolution: {t.resolution_note}</p>}
      {dq && <div className="mt-4 rounded-lg border p-3 dark:border-slate-600"><h4 className="mb-2 font-semibold">Dispatch quantities (partial dispatch allowed)</h4>{t.items.map((i) => <div key={i.id} className="mb-2 flex items-center gap-2 text-sm"><span className="w-48">{i.product_name}</span><input aria-label={`Dispatch ${i.product_name}`} type="number" min="0" max={i.quantity} className="input w-28" value={dq[i.id]} onChange={(e) => setDq({ ...dq, [i.id]: e.target.value })} /></div>)}
        <Button variant="success" onClick={() => run(async () => { await post(`/transfers/${id}/dispatch`, { idempotency_key: key, items: t.items.map((i) => ({ item_id: i.id, quantity: Number(dq[i.id]) })) }); setDq(null); }, "Dispatched - stock is in transit")}>Confirm dispatch</Button></div>}
      {rq && <div className="mt-4 rounded-lg border p-3 dark:border-slate-600"><h4 className="mb-2 font-semibold">Receipt confirmation</h4>{t.items.filter((i) => i.dispatched_qty > 0).map((i) => <div key={i.id} className="mb-2 flex items-center gap-2 text-sm"><span className="w-48">{i.product_name} (sent {i.dispatched_qty})</span><input aria-label={`Received ${i.product_name}`} type="number" min="0" max={i.dispatched_qty} className="input w-28" value={rq[i.id]} onChange={(e) => setRq({ ...rq, [i.id]: e.target.value })} /></div>)}
        <Input label="Receipt note (explain any shortage)" value={note} onChange={(e) => setNote(e.target.value)} />
        <Button className="mt-2" variant="success" onClick={() => run(async () => { await post(`/transfers/${id}/receive`, { idempotency_key: key, note, items: t.items.filter((i) => i.dispatched_qty > 0).map((i) => ({ item_id: i.id, received_qty: Number(rq[i.id]) })) }); setRq(null); }, "Transfer received")}>Confirm receipt</Button></div>}
      <div className="mt-4 flex flex-wrap gap-2">
        {t.status === "requested" && can("transfers.approve") && <><Button variant="success" onClick={() => run(() => post(`/transfers/${id}/approve`), "Transfer approved")}>Approve</Button>
          <Button variant="danger" onClick={() => { const reason = prompt("Reason for rejection?"); if (reason !== null) run(() => post(`/transfers/${id}/reject`, { reason }), "Rejected"); }}>Reject</Button></>}
        {t.status === "approved" && can("transfers.process") && !dq && <Button onClick={() => setDq(Object.fromEntries(t.items.map((i) => [i.id, i.quantity])))}>Dispatch</Button>}
        {t.status === "in_transit" && can("transfers.process") && !rq && <Button onClick={() => setRq(Object.fromEntries(t.items.map((i) => [i.id, i.dispatched_qty])))}>Receive</Button>}
        {["requested", "approved"].includes(t.status) && can("transfers.create", "transfers.approve") && <Button variant="ghost" onClick={() => run(() => post(`/transfers/${id}/cancel`), "Cancelled")}>Cancel</Button>}
        {t.discrepancy_status === "open" && can("transfers.approve") && <Button variant="ghost" onClick={() => { const n = prompt("Resolution note (e.g. insurance claim, recount)?"); if (n) run(() => post(`/transfers/${id}/resolve`, { note: n }), "Discrepancy resolved"); }}>Resolve discrepancy</Button>}
      </div>
    </Modal>
  );
}

export default function Transfers() {
  const { can } = useApp();
  const [adding, setAdding] = useState(false);
  const [view, setView] = useState(null);
  const list = useList("/transfers");
  return (
    <div>
      <PageHeader title="Stock transfers" subtitle="Request, approve, dispatch, receive and reconcile discrepancies">{can("transfers.create") && <Button onClick={() => setAdding(true)}><Plus size={16} /> New transfer</Button>}</PageHeader>
      <div className="card"><div className="mb-3 flex flex-wrap gap-2"><SearchBox onSearch={(q) => list.set({ q })} placeholder="Search transfer number" />
        <select aria-label="Status" className="input w-auto" onChange={(e) => list.set({ status: e.target.value })}><option value="">All statuses</option>{["requested", "approved", "in_transit", "received", "rejected", "cancelled"].map((s) => <option key={s} value={s}>{s.replace("_", " ")}</option>)}</select>
        <select aria-label="Discrepancy" className="input w-auto" onChange={(e) => list.set({ discrepancy_status: e.target.value })}><option value="">Any discrepancy</option><option value="open">Open discrepancies</option><option value="resolved">Resolved</option></select></div>
        <DataTable loading={list.loading} rows={list.rows} columns={[{ key: "transfer_number", label: "Transfer #" }, { key: "created_at", label: "Date", render: (r) => r.created_at.slice(0, 10) }, { key: "from_name", label: "From" }, { key: "to_name", label: "To" }, { key: "item_count", label: "Items" }, { key: "status", label: "Status", render: (r) => <Badge value={r.status} /> },
          { key: "discrepancy_status", label: "Discrepancy", render: (r) => <Badge value={r.discrepancy_status} /> }, { key: "x", label: "", render: (r) => <Button variant="ghost" aria-label={`Open ${r.transfer_number}`} onClick={() => setView(r.id)}><Eye size={14} /></Button> }]} /><Pagination meta={list.meta} onPage={list.setPage} /></div>
      {adding && <NewTransfer onClose={() => setAdding(false)} onDone={list.reload} />}
      {view && <TransferDetail id={view} onClose={() => setView(null)} onChanged={list.reload} />}
    </div>
  );
}
