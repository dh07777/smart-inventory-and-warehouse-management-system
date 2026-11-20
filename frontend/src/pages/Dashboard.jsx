import { Link } from "react-router-dom";
import { Package, Warehouse, Boxes, DollarSign, AlertTriangle, XCircle, ShoppingCart, Receipt, Clock } from "lucide-react";
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, Legend, CartesianGrid, LineChart, Line } from "recharts";
import { useFetch } from "../hooks";
import { useApp } from "../context";
import { PageHeader, Stat, Badge, Bar as Meter } from "../ui";

export default function Dashboard() {
  const { money } = useApp();
  const { data: d, loading, error } = useFetch("/dashboard");
  if (loading) return <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">{Array.from({ length: 8 }).map((_, i) => <div key={i} className="card h-20 animate-pulse" />)}</div>;
  if (error) return <div className="card text-red-600">{error}</div>;
  const t = d.totals;
  return (
    <div className="space-y-5">
      <PageHeader title="Dashboard" subtitle="Live figures calculated from the database" />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat icon={Package} label="Total products" value={t.products} />
        <Stat icon={Warehouse} label="Warehouses" value={t.warehouses} tone="green" />
        <Stat icon={Boxes} label="Inventory quantity" value={t.inventory_quantity.toLocaleString()} tone="amber" />
        <Stat icon={DollarSign} label="Inventory valuation (FIFO)" value={money(t.inventory_value)} tone="green" />
        <Stat icon={AlertTriangle} label="Low-stock products" value={t.low_stock} tone="amber" />
        <Stat icon={XCircle} label="Out of stock" value={t.out_of_stock} tone="red" />
        <Stat icon={ShoppingCart} label="Pending purchase orders" value={t.pending_purchase_orders} />
        <Stat icon={Receipt} label="Pending sales orders" value={t.pending_sales_orders} tone="amber" sub={`${t.expiring_batches} batches expiring soon`} />
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <div className="card"><h2 className="mb-2 font-semibold">Monthly purchases vs sales</h2>
          <ResponsiveContainer width="100%" height={260}><BarChart data={d.monthly}><CartesianGrid strokeDasharray="3 3" opacity={0.3} /><XAxis dataKey="month" fontSize={11} /><YAxis fontSize={11} /><Tooltip formatter={(v) => money(v)} /><Legend />
            <Bar dataKey="purchases" fill="#6366f1" radius={[4, 4, 0, 0]} /><Bar dataKey="sales" fill="#10b981" radius={[4, 4, 0, 0]} /></BarChart></ResponsiveContainer></div>
        <div className="card"><h2 className="mb-2 font-semibold">Inventory trend (units on hand)</h2>
          <ResponsiveContainer width="100%" height={260}><LineChart data={d.inventory_trend}><CartesianGrid strokeDasharray="3 3" opacity={0.3} /><XAxis dataKey="month" fontSize={11} /><YAxis fontSize={11} /><Tooltip />
            <Line type="monotone" dataKey="quantity" stroke="#2563eb" strokeWidth={2} dot /></LineChart></ResponsiveContainer></div>
      </div>
      <div className="grid gap-4 lg:grid-cols-3">
        <div className="card"><h2 className="mb-3 font-semibold">Warehouse performance</h2>
          {d.warehouse_performance.map((w) => (<div key={w.warehouse} className="mb-3"><div className="flex justify-between text-sm"><span>{w.warehouse}</span><span>{w.utilization}% used - {w.movements_30d} moves/30d</span></div><Meter pct={w.utilization} /></div>))}</div>
        <div className="card"><h2 className="mb-3 font-semibold">Top-selling products</h2>
          {d.top_products.length === 0 && <p className="text-sm text-slate-500">No sales yet.</p>}
          {d.top_products.map((p, i) => <div key={p.name} className="flex justify-between border-b py-1.5 text-sm dark:border-slate-700"><span>{i + 1}. {p.name}</span><b>{p.units} units</b></div>)}</div>
        <div className="card"><h2 className="mb-3 font-semibold">Stock alerts</h2>
          {d.alerts.out.map((a) => <div key={a.id} className="flex justify-between py-1 text-sm"><span>{a.name}</span><Badge value="out" /></div>)}
          {d.alerts.low.map((a) => <div key={a.id} className="flex justify-between py-1 text-sm"><span>{a.name}</span><span className="text-amber-600">{a.on_hand}/{a.min_stock}</span></div>)}
          {!d.alerts.out.length && !d.alerts.low.length && <p className="text-sm text-slate-500">No stock alerts.</p>}
          <Link to="/inventory" className="mt-2 inline-block text-sm text-blue-600">Open inventory alerts</Link></div>
      </div>
      <div className="card"><h2 className="mb-3 flex items-center gap-2 font-semibold"><Clock size={16} /> Recent stock movements</h2>
        <div className="overflow-x-auto"><table className="min-w-full text-sm"><tbody>{d.recent_movements.map((m) => (
          <tr key={m.id} className="border-b dark:border-slate-700"><td className="td">{m.created_at.slice(0, 16).replace("T", " ")}</td><td className="td"><Badge value={m.movement_type.toLowerCase()} /></td>
            <td className="td">{m.product_name}</td><td className="td">{m.warehouse_name}</td><td className={`td font-semibold ${m.quantity < 0 ? "text-red-600" : "text-emerald-600"}`}>{m.quantity > 0 ? "+" : ""}{m.quantity}</td></tr>))}</tbody></table></div></div>
    </div>
  );
}
