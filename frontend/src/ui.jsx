import { useEffect, useState } from "react";
import { X, Search, ChevronLeft, ChevronRight, Inbox, Plus, Trash2, Package } from "lucide-react";
import { useDebounced } from "./hooks";

export const cx = (...a) => a.filter(Boolean).join(" ");

export function Button({ variant = "primary", className, ...p }) {
  const v = { primary: "bg-blue-600 text-white hover:bg-blue-700", ghost: "border border-slate-300 hover:bg-slate-100 dark:border-slate-600 dark:text-slate-100 dark:hover:bg-slate-700",
    danger: "bg-red-600 text-white hover:bg-red-700", success: "bg-emerald-600 text-white hover:bg-emerald-700" }[variant];
  return <button type="button" {...p} className={cx("inline-flex items-center justify-center gap-1.5 rounded-lg px-3 py-2 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-50", v, className)} />;
}

const COLORS = { active: "green", approved: "blue", received: "green", delivered: "green", refunded: "green", resolved: "green", paid: "green", ok: "green", good: "green",
  pending: "amber", pending_approval: "amber", requested: "amber", partial: "amber", partially_received: "amber", low: "amber", in_transit: "blue", confirmed: "blue", dispatched: "blue", open: "red",
  rejected: "red", cancelled: "slate", inactive: "slate", discontinued: "slate", out: "red", unpaid: "red", returned: "slate", damaged: "red" };
const TONE = { green: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300", amber: "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300",
  blue: "bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300", red: "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300", slate: "bg-slate-200 text-slate-700 dark:bg-slate-700 dark:text-slate-300" };
export const Badge = ({ value }) => value ? <span className={cx("rounded-full px-2 py-0.5 text-xs font-medium capitalize", TONE[COLORS[value] || "slate"])}>{String(value).replace(/_/g, " ")}</span> : null;

export function Modal({ title, onClose, children, wide, footer }) {
  useEffect(() => { const f = (e) => e.key === "Escape" && onClose(); window.addEventListener("keydown", f); return () => window.removeEventListener("keydown", f); }, [onClose]);
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/50 p-4 no-print" role="dialog" aria-modal="true" aria-label={title}>
      <div className={cx("my-8 w-full rounded-xl bg-white shadow-xl dark:bg-slate-800 dark:text-slate-100", wide ? "max-w-4xl" : "max-w-lg")}>
        <div className="flex items-center justify-between border-b border-slate-200 px-5 py-3 dark:border-slate-700">
          <h3 className="text-base font-semibold">{title}</h3>
          <button onClick={onClose} aria-label="Close" className="rounded p-1 hover:bg-slate-100 dark:hover:bg-slate-700"><X size={18} /></button>
        </div>
        <div className="p-5">{children}</div>
        {footer && <div className="flex justify-end gap-2 border-t border-slate-200 px-5 py-3 dark:border-slate-700">{footer}</div>}
      </div>
    </div>
  );
}

export function Confirm({ message, onYes, onNo, busy }) {
  return (
    <Modal title="Please confirm" onClose={onNo} footer={<><Button variant="ghost" onClick={onNo}>Cancel</Button><Button variant="danger" disabled={busy} onClick={onYes}>Confirm</Button></>}>
      <p className="text-sm">{message}</p>
    </Modal>
  );
}

export function Field({ label, error, children, hint }) {
  return (
    <label className="block text-sm">
      <span className="mb-1 block font-medium text-slate-700 dark:text-slate-200">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-xs text-slate-500">{hint}</span>}
      {error && <span className="mt-1 block text-xs text-red-600">{error}</span>}
    </label>
  );
}

export function Input({ label, error, hint, type = "text", options, ...p }) {
  let el;
  if (type === "select") el = <select className="input" {...p}><option value="">{p.placeholder || "Select..."}</option>{(options || []).map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}</select>;
  else if (type === "textarea") el = <textarea className="input" rows={3} {...p} />;
  else if (type === "checkbox") return <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={!!p.value} onChange={(e) => p.onChange({ target: { value: e.target.checked } })} />{label}</label>;
  else el = <input type={type} className="input" {...p} />;
  return <Field label={label} error={error} hint={hint}>{el}</Field>;
}

export const SearchBox = ({ onSearch, placeholder = "Search..." }) => {
  const [v, setV] = useState("");
  const d = useDebounced(v);
  useEffect(() => { onSearch(d); }, [d]); // eslint-disable-line
  return (
    <div className="relative min-w-[200px] flex-1 sm:max-w-xs">
      <Search size={16} className="absolute left-3 top-2.5 text-slate-400" />
      <input aria-label="Search" className="input pl-9" placeholder={placeholder} value={v} onChange={(e) => setV(e.target.value)} />
    </div>
  );
};

export function Pagination({ meta, onPage }) {
  if (!meta || !meta.total) return null;
  return (
    <div className="flex items-center justify-between px-1 pt-3 text-sm text-slate-600 dark:text-slate-300">
      <span>{meta.total} record{meta.total === 1 ? "" : "s"} - page {meta.page} of {meta.pages}</span>
      <div className="flex gap-1">
        <Button variant="ghost" disabled={meta.page <= 1} onClick={() => onPage(meta.page - 1)} aria-label="Previous page"><ChevronLeft size={16} /></Button>
        <Button variant="ghost" disabled={meta.page >= meta.pages} onClick={() => onPage(meta.page + 1)} aria-label="Next page"><ChevronRight size={16} /></Button>
      </div>
    </div>
  );
}

export function DataTable({ columns, rows, loading, empty = "No records found", sort, onSort, rowKey = "id" }) {
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-slate-200 dark:divide-slate-700">
        <thead><tr>{columns.map((c) => (
          <th key={c.key} className={cx("th", c.sortable && "cursor-pointer select-none")} onClick={() => c.sortable && onSort?.(c.key)}>
            {c.label}{sort?.sort === c.key ? (sort.order === "asc" ? " ▲" : " ▼") : ""}
          </th>))}</tr></thead>
        <tbody className="divide-y divide-slate-100 dark:divide-slate-700/60">
          {loading && Array.from({ length: 5 }).map((_, i) => (
            <tr key={i} aria-hidden>{columns.map((c) => <td key={c.key} className="td"><div className="h-4 animate-pulse rounded bg-slate-200 dark:bg-slate-700" /></td>)}</tr>))}
          {!loading && rows.map((r, i) => (
            <tr key={r[rowKey] ?? i} className="hover:bg-slate-50 dark:hover:bg-slate-700/40">
              {columns.map((c) => <td key={c.key} className="td">{c.render ? c.render(r) : (r[c.key] ?? "-")}</td>)}</tr>))}
        </tbody>
      </table>
      {!loading && rows.length === 0 && (
        <div className="flex flex-col items-center gap-2 py-10 text-slate-500"><Inbox size={36} /><span className="text-sm">{empty}</span></div>)}
    </div>
  );
}

const PLACEHOLDER = "data:image/svg+xml;utf8," + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 80 60"><rect width="80" height="60" fill="#e2e8f0"/><path d="M26 24l14-7 14 7v14l-14 7-14-7z" fill="none" stroke="#94a3b8" stroke-width="2"/><path d="M26 24l14 7 14-7M40 31v14" stroke="#94a3b8" stroke-width="2" fill="none"/></svg>');
export function ProductImage({ src, alt = "", className = "h-10 w-10" }) {
  const [bad, setBad] = useState(false);
  return <img src={!src || bad ? PLACEHOLDER : src} alt={alt} loading="lazy" onError={() => setBad(true)} className={cx("rounded-lg object-cover", className)} />;
}

export const Tabs = ({ tabs, value, onChange }) => (
  <div className="mb-4 flex gap-1 overflow-x-auto border-b border-slate-200 dark:border-slate-700 no-print" role="tablist">
    {tabs.map((t) => (
      <button key={t.key} role="tab" aria-selected={value === t.key} onClick={() => onChange(t.key)}
        className={cx("whitespace-nowrap border-b-2 px-3 py-2 text-sm font-medium", value === t.key ? "border-blue-600 text-blue-600" : "border-transparent text-slate-500 hover:text-slate-800 dark:hover:text-slate-200")}>{t.label}</button>))}
  </div>
);

export const PageHeader = ({ title, subtitle, children }) => (
  <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
    <div><h1 className="text-xl font-bold text-slate-900 dark:text-white">{title}</h1>{subtitle && <p className="text-sm text-slate-500">{subtitle}</p>}</div>
    <div className="flex flex-wrap items-center gap-2">{children}</div>
  </div>
);

export const Stat = ({ icon: Icon = Package, label, value, tone = "blue", sub }) => (
  <div className="card flex items-center gap-3">
    <div className={cx("rounded-lg p-2.5", TONE[tone])}><Icon size={20} /></div>
    <div><div className="text-xs text-slate-500">{label}</div><div className="text-lg font-bold dark:text-white">{value}</div>{sub && <div className="text-xs text-slate-400">{sub}</div>}</div>
  </div>
);

export function Bar({ pct }) {
  const c = pct > 90 ? "bg-red-500" : pct > 70 ? "bg-amber-500" : "bg-emerald-500";
  return <div className="h-2 w-full rounded-full bg-slate-200 dark:bg-slate-700"><div className={cx("h-2 rounded-full", c)} style={{ width: `${Math.min(pct, 100)}%` }} /></div>;
}

/** Line-item editor shared by purchase orders, sales orders and transfers. */
export function ItemsEditor({ items, onChange, products, showPrice = true, showDiscount = false, priceField = "purchase_price" }) {
  const set = (i, patch) => onChange(items.map((it, idx) => (idx === i ? { ...it, ...patch } : it)));
  const pick = (i, id) => { const p = products.find((x) => String(x.id) === String(id)); set(i, { product_id: id, unit_price: p ? p[priceField] : "", discount: p ? p.discount : 0 }); };
  return (
    <div className="space-y-2">
      {items.map((it, i) => (
        <div key={i} className="grid grid-cols-12 gap-2">
          <select aria-label="Product" className="input col-span-12 sm:col-span-5" value={it.product_id} onChange={(e) => pick(i, e.target.value)}>
            <option value="">Product...</option>{products.map((p) => <option key={p.id} value={p.id}>{p.sku} - {p.name}</option>)}</select>
          <input aria-label="Quantity" type="number" min="1" className="input col-span-4 sm:col-span-2" placeholder="Qty" value={it.quantity} onChange={(e) => set(i, { quantity: e.target.value })} />
          {showPrice && <input aria-label="Unit price" type="number" step="0.01" min="0" className="input col-span-4 sm:col-span-2" placeholder="Price" value={it.unit_price ?? ""} onChange={(e) => set(i, { unit_price: e.target.value })} />}
          {showDiscount && <input aria-label="Discount %" type="number" min="0" max="100" className="input col-span-4 sm:col-span-2" placeholder="Disc %" value={it.discount ?? ""} onChange={(e) => set(i, { discount: e.target.value })} />}
          <Button variant="ghost" className="col-span-2 sm:col-span-1" onClick={() => onChange(items.filter((_, x) => x !== i))} aria-label="Remove line"><Trash2 size={15} /></Button>
        </div>))}
      <Button variant="ghost" onClick={() => onChange([...items, { product_id: "", quantity: 1, unit_price: "", discount: 0 }])}><Plus size={15} /> Add line</Button>
    </div>
  );
}

export const cleanItems = (items, keys) => items.filter((i) => i.product_id && Number(i.quantity) > 0).map((i) => {
  const o = { product_id: Number(i.product_id), quantity: Number(i.quantity) };
  if (keys.includes("price") && i.unit_price !== "" && i.unit_price != null) o.unit_price = Number(i.unit_price);
  if (keys.includes("discount") && i.discount !== "" && i.discount != null) o.discount = Number(i.discount);
  return o;
});
