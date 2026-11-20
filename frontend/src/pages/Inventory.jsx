import { useState } from "react";
import { PackagePlus, PackageMinus, SlidersHorizontal, Flame, ClipboardCheck, Bell } from "lucide-react";
import { get, post, errMsg } from "../api";
import { useApp } from "../context";
import { useFetch, useList } from "../hooks";
import { Button, Modal, Input, Badge, DataTable, Pagination, Tabs, PageHeader, SearchBox } from "../ui";

const opt = (rows, label) => (rows || []).map((r) => ({ value: r.id, label: label(r) }));

function ActionModal({ kind, onClose, onDone }) {
  const { notify, can, settings } = useApp();
  const prods = useFetch("/products", { per_page: 200 });
  const whs = useFetch("/warehouses", { per_page: 100 });
  const [f, setF] = useState({ product_id: "", warehouse_id: settings.default_warehouse_id || "", quantity: "", unit_cost: "", batch_no: "", mfg_date: "", expiry_date: "", reason: "", new_quantity: "", batch_id: "", override: false, wreason: "damaged" });
  const [lines, setLines] = useState([{ product_id: "", counted: "" }]);
  const [batches, setBatches] = useState([]);
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const loadBatches = async (pid, wid) => { if (pid && wid) setBatches((await get("/inventory/batches", { product_id: pid, warehouse_id: wid, per_page: 100 })).data); };
  const titles = { in: "Stock in", out: "Stock out", adjust: "Stock adjustment", writeoff: "Damaged / expired stock", reconcile: "Stock reconciliation" };
  const num = (v) => (v === "" ? undefined : Number(v));
  const submit = async () => {
    setBusy(true);
    try {
      const base = { product_id: Number(f.product_id), warehouse_id: Number(f.warehouse_id) };
      let res;
      if (kind === "in") res = await post("/inventory/stock-in", { ...base, quantity: num(f.quantity), unit_cost: num(f.unit_cost), batch_no: f.batch_no, mfg_date: f.mfg_date || undefined, expiry_date: f.expiry_date || undefined, reason: f.reason });
      if (kind === "out") await post("/inventory/stock-out", { ...base, quantity: num(f.quantity), reason: f.reason, override: f.override });
      if (kind === "adjust") await post("/inventory/adjust", { ...base, new_quantity: num(f.new_quantity), reason: f.reason, override: f.override });
      if (kind === "writeoff") await post("/inventory/write-off", { ...base, batch_id: Number(f.batch_id), quantity: num(f.quantity), reason: f.wreason, note: f.reason });
      if (kind === "reconcile") await post("/inventory/reconcile", { warehouse_id: Number(f.warehouse_id), note: f.reason, counts: lines.filter((l) => l.product_id && l.counted !== "").map((l) => ({ product_id: Number(l.product_id), counted: Number(l.counted) })) });
      notify(`${titles[kind]} completed`); (res?.data?.warnings || []).forEach((w) => notify(w, "error")); onDone(); onClose();
    } catch (e) { notify(errMsg(e), "error"); } finally { setBusy(false); }
  };
  const P = <Input label="Product" type="select" value={f.product_id} onChange={(e) => { setF({ ...f, product_id: e.target.value, batch_id: "" }); loadBatches(e.target.value, f.warehouse_id); }} options={opt(prods.data, (p) => `${p.sku} - ${p.name}`)} />;
  const W = <Input label="Warehouse" type="select" value={f.warehouse_id} onChange={(e) => { setF({ ...f, warehouse_id: e.target.value, batch_id: "" }); loadBatches(f.product_id, e.target.value); }} options={opt(whs.data, (w) => w.name)} />;
  return (
    <Modal title={titles[kind]} onClose={onClose} footer={<><Button variant="ghost" onClick={onClose}>Cancel</Button><Button disabled={busy} onClick={submit}>{busy ? "Saving..." : "Submit"}</Button></>}>
      <div className="space-y-3">
        {W}
        {kind !== "reconcile" && P}
        {(kind === "in" || kind === "out" || kind === "writeoff") && <Input label="Quantity" type="number" min="1" value={f.quantity} onChange={set("quantity")} />}
        {kind === "in" && <>
          <Input label="Unit cost (blank = product purchase price)" type="number" step="0.01" value={f.unit_cost} onChange={set("unit_cost")} />
          <Input label="Batch / lot number" value={f.batch_no} onChange={set("batch_no")} />
          <div className="grid grid-cols-2 gap-2"><Input label="Manufacture date" type="date" value={f.mfg_date} onChange={set("mfg_date")} /><Input label="Expiry date" type="date" value={f.expiry_date} onChange={set("expiry_date")} /></div></>}
        {kind === "adjust" && <Input label="New counted quantity" type="number" min="0" value={f.new_quantity} onChange={set("new_quantity")} />}
        {kind === "writeoff" && <>
          <Input label="Batch" type="select" value={f.batch_id} onChange={set("batch_id")} options={batches.map((b) => ({ value: b.batch_id, label: `${b.batch_no} (qty ${b.quantity}${b.expiry_date ? ", exp " + b.expiry_date : ""})` }))} />
          <Input label="Reason" type="select" value={f.wreason} onChange={set("wreason")} options={[{ value: "damaged", label: "Damaged" }, { value: "expired", label: "Expired" }]} /></>}
        {kind === "reconcile" && <div className="space-y-2"><p className="text-xs text-slate-500">Enter the physically counted quantity; the system posts the difference as reconciliation movements.</p>
          {lines.map((l, i) => <div key={i} className="grid grid-cols-3 gap-2"><select aria-label="Product" className="input col-span-2" value={l.product_id} onChange={(e) => setLines(lines.map((x, j) => (j === i ? { ...x, product_id: e.target.value } : x)))}>
            <option value="">Product...</option>{(prods.data || []).map((p) => <option key={p.id} value={p.id}>{p.sku} - {p.name}</option>)}</select>
            <input aria-label="Counted" className="input" type="number" min="0" placeholder="Counted" value={l.counted} onChange={(e) => setLines(lines.map((x, j) => (j === i ? { ...x, counted: e.target.value } : x)))} /></div>)}
          <Button variant="ghost" onClick={() => setLines([...lines, { product_id: "", counted: "" }])}>Add product</Button></div>}
        <Input label={kind === "reconcile" ? "Note" : "Reason / note"} value={f.reason} onChange={set("reason")} />
        {(kind === "out" || kind === "adjust") && can("inventory.override") && <Input type="checkbox" label="Authorized negative-stock override (must be enabled in Settings)" value={f.override} onChange={set("override")} />}
      </div>
    </Modal>
  );
}

export default function Inventory() {
  const { can, notify, money } = useApp();
  const [tab, setTab] = useState("stock");
  const [act, setAct] = useState(null);
  const [tick, setTick] = useState(0);
  const whs = useFetch("/warehouses", { per_page: 100 });
  const stock = useList("/inventory/stock");
  const moves = useList("/inventory/movements");
  const batches = useList("/inventory/batches");
  const res = useList("/inventory/reservations", { status: "active" });
  const reorder = useFetch("/inventory/reorder", {}, [tick]);
  const alerts = useFetch("/inventory/alerts", {}, [tick]);
  const refresh = () => { setTick((t) => t + 1); stock.reload(); moves.reload(); batches.reload(); res.reload(); };
  const wsel = (l) => <select aria-label="Warehouse filter" className="input w-auto" value={l.params.warehouse_id ?? ""} onChange={(e) => l.set({ warehouse_id: e.target.value })}><option value="">All warehouses</option>{(whs.data || []).map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}</select>;
  return (
    <div>
      <PageHeader title="Inventory control" subtitle="FIFO valuation, batches, reservations, alerts and full movement history">
        {can("inventory.manage") && <>
          <Button onClick={() => setAct("in")}><PackagePlus size={15} /> Stock in</Button><Button variant="ghost" onClick={() => setAct("out")}><PackageMinus size={15} /> Stock out</Button>
          <Button variant="ghost" onClick={() => setAct("adjust")}><SlidersHorizontal size={15} /> Adjust</Button><Button variant="ghost" onClick={() => setAct("writeoff")}><Flame size={15} /> Damaged/expired</Button>
          <Button variant="ghost" onClick={() => setAct("reconcile")}><ClipboardCheck size={15} /> Reconcile</Button></>}
        <Button variant="ghost" onClick={async () => { try { const r = await post("/notifications/scan"); notify(`Scan done: ${r.data.low_stock} low, ${r.data.out_of_stock} out, ${r.data.expiring_batches} expiring`); } catch (e) { notify(errMsg(e), "error"); } }}><Bell size={15} /> Scan alerts</Button>
      </PageHeader>
      <Tabs value={tab} onChange={setTab} tabs={[{ key: "stock", label: "Stock levels" }, { key: "moves", label: "Movement history" }, { key: "batches", label: "Batches & expiry" }, { key: "res", label: "Reservations" }, { key: "reorder", label: "Reorder recommendations" }, { key: "alerts", label: "Alerts" }]} />
      <div className="card">
        {tab === "stock" && <><div className="mb-3 flex flex-wrap gap-2"><SearchBox onSearch={(q) => stock.set({ q })} placeholder="Search product or SKU" />{wsel(stock)}
          <select aria-label="Status" className="input w-auto" onChange={(e) => stock.set({ status: e.target.value })}><option value="">All</option><option value="low">Low stock only</option></select></div>
          <DataTable loading={stock.loading} rows={stock.rows} columns={[{ key: "sku", label: "SKU" }, { key: "name", label: "Product" }, { key: "warehouse_name", label: "Warehouse" }, { key: "on_hand", label: "On hand" }, { key: "reserved", label: "Reserved" }, { key: "available", label: "Available" }, { key: "min_stock", label: "Min" }, { key: "value", label: "Value (FIFO)", render: (r) => money(r.value) }]} /><Pagination meta={stock.meta} onPage={stock.setPage} /></>}
        {tab === "moves" && <><div className="mb-3 flex flex-wrap gap-2">{wsel(moves)}
          <select aria-label="Movement type" className="input w-auto" onChange={(e) => moves.set({ type: e.target.value })}><option value="">All types</option>{["IN", "OUT", "ADJUST", "RECONCILE", "TRANSFER_OUT", "TRANSFER_IN", "RETURN_IN", "DAMAGED", "EXPIRED"].map((t) => <option key={t}>{t}</option>)}</select>
          <input aria-label="From date" type="date" className="input w-auto" onChange={(e) => moves.set({ date_from: e.target.value })} /><input aria-label="To date" type="date" className="input w-auto" onChange={(e) => moves.set({ date_to: e.target.value })} /></div>
          <DataTable loading={moves.loading} rows={moves.rows} columns={[{ key: "created_at", label: "Date", render: (r) => r.created_at.slice(0, 16).replace("T", " ") }, { key: "movement_type", label: "Type", render: (r) => <Badge value={r.movement_type.toLowerCase()} /> }, { key: "product_name", label: "Product" }, { key: "warehouse_name", label: "Warehouse" }, { key: "batch_no", label: "Batch" },
            { key: "quantity", label: "Qty", render: (r) => <b className={r.quantity < 0 ? "text-red-600" : "text-emerald-600"}>{r.quantity > 0 ? "+" : ""}{r.quantity}</b> }, { key: "note", label: "Note" }, { key: "user_name", label: "By" }]} /><Pagination meta={moves.meta} onPage={moves.setPage} /></>}
        {tab === "batches" && <><div className="mb-3 flex flex-wrap gap-2">{wsel(batches)}<select aria-label="Expiry window" className="input w-auto" onChange={(e) => batches.set({ expiring_in_days: e.target.value })}><option value="">All batches</option><option value="30">Expiring in 30 days</option><option value="90">Expiring in 90 days</option><option value="0">Expired / today</option></select></div>
          <DataTable loading={batches.loading} rows={batches.rows} columns={[{ key: "sku", label: "SKU" }, { key: "product_name", label: "Product" }, { key: "warehouse_name", label: "Warehouse" }, { key: "batch_no", label: "Batch" }, { key: "quantity", label: "Qty" }, { key: "unit_cost", label: "Unit cost", render: (r) => money(r.unit_cost) },
            { key: "expiry_date", label: "Expiry", render: (r) => r.expiry_date ? <span className={new Date(r.expiry_date) < new Date() ? "font-semibold text-red-600" : ""}>{r.expiry_date}</span> : "-" }]} /><Pagination meta={batches.meta} onPage={batches.setPage} /></>}
        {tab === "res" && <><DataTable loading={res.loading} rows={res.rows} columns={[{ key: "product_name", label: "Product" }, { key: "warehouse_name", label: "Warehouse" }, { key: "quantity", label: "Qty" }, { key: "reference_type", label: "For", render: (r) => `${r.reference_type}${r.reference_id ? " #" + r.reference_id : ""}` }, { key: "created_at", label: "Created", render: (r) => r.created_at.slice(0, 10) },
          { key: "x", label: "", render: (r) => can("inventory.manage") && r.reference_type === "manual" && <Button variant="ghost" onClick={async () => { try { await post(`/inventory/reservations/${r.id}/release`); notify("Reservation released"); refresh(); } catch (e) { notify(errMsg(e), "error"); } }}>Release</Button> }]} /><Pagination meta={res.meta} onPage={res.setPage} />
          {can("inventory.manage") && <ReserveForm onDone={refresh} />}</>}
        {tab === "reorder" && <DataTable loading={reorder.loading} rows={reorder.data || []} rowKey="product_id" empty="Nothing needs reordering" columns={[{ key: "sku", label: "SKU" }, { key: "name", label: "Product" }, { key: "available", label: "Available" }, { key: "min_stock", label: "Min" }, { key: "suggested_qty", label: "Suggested qty" }, { key: "supplier_name", label: "Supplier" }, { key: "estimated_cost", label: "Est. cost", render: (r) => money(r.estimated_cost) }]} />}
        {tab === "alerts" && alerts.data && <div className="grid gap-4 md:grid-cols-3">
          <div><h3 className="mb-2 font-semibold text-red-600">Out of stock ({alerts.data.out_of_stock.length})</h3>{alerts.data.out_of_stock.map((a) => <div key={a.product_id} className="border-b py-1 text-sm dark:border-slate-700">{a.sku} - {a.name}</div>)}</div>
          <div><h3 className="mb-2 font-semibold text-amber-600">Low stock ({alerts.data.low_stock.length})</h3>{alerts.data.low_stock.map((a) => <div key={a.product_id} className="border-b py-1 text-sm dark:border-slate-700">{a.name}: {a.on_hand} / min {a.min_stock}</div>)}</div>
          <div><h3 className="mb-2 font-semibold text-orange-600">Expiring / expired ({alerts.data.expiring.length})</h3>{alerts.data.expiring.map((a) => <div key={a.batch_id} className="border-b py-1 text-sm dark:border-slate-700">{a.batch_no}: {a.quantity} units - {a.expired ? "EXPIRED " : ""}{a.expiry_date}</div>)}</div></div>}
      </div>
      {act && <ActionModal kind={act} onClose={() => setAct(null)} onDone={refresh} />}
    </div>
  );
}

function ReserveForm({ onDone }) {
  const { notify } = useApp();
  const prods = useFetch("/products", { per_page: 200 });
  const whs = useFetch("/warehouses", { per_page: 100 });
  const [f, setF] = useState({ product_id: "", warehouse_id: "", quantity: "" });
  return (
    <div className="mt-4 grid gap-2 border-t pt-3 sm:grid-cols-4 dark:border-slate-700">
      <select aria-label="Reserve product" className="input" value={f.product_id} onChange={(e) => setF({ ...f, product_id: e.target.value })}><option value="">Product...</option>{(prods.data || []).map((p) => <option key={p.id} value={p.id}>{p.sku} - {p.name}</option>)}</select>
      <select aria-label="Reserve warehouse" className="input" value={f.warehouse_id} onChange={(e) => setF({ ...f, warehouse_id: e.target.value })}><option value="">Warehouse...</option>{(whs.data || []).map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}</select>
      <input aria-label="Reserve quantity" className="input" type="number" min="1" placeholder="Quantity" value={f.quantity} onChange={(e) => setF({ ...f, quantity: e.target.value })} />
      <Button onClick={async () => { try { await post("/inventory/reservations", { product_id: Number(f.product_id), warehouse_id: Number(f.warehouse_id), quantity: Number(f.quantity) }); notify("Stock reserved"); setF({ product_id: "", warehouse_id: "", quantity: "" }); onDone(); } catch (e) { notify(errMsg(e), "error"); } }}>Reserve stock</Button>
    </div>
  );
}
