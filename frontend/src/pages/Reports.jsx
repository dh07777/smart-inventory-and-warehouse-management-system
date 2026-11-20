import { useEffect, useState } from "react";
import { Download, FileSpreadsheet, Printer } from "lucide-react";
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid } from "recharts";
import { get, download, errMsg } from "../api";
import { useApp } from "../context";
import { useFetch } from "../hooks";
import { Button, PageHeader, DataTable } from "../ui";

export default function Reports() {
  const { notify, settings } = useApp();
  const cat = useFetch("/reports");
  const whs = useFetch("/warehouses", { per_page: 100 });
  const [key, setKey] = useState("inventory-valuation");
  const [p, setP] = useState({ date_from: "", date_to: "", warehouse_id: "" });
  const [rep, setRep] = useState(null);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const params = () => Object.fromEntries(Object.entries(p).filter(([, v]) => v));
  const run = async () => {
    setLoading(true); setPage(1);
    try { setRep((await get(`/reports/${key}`, params())).data); } catch (e) { notify(errMsg(e), "error"); setRep(null); } finally { setLoading(false); }
  };
  useEffect(() => { run(); }, [key]); // eslint-disable-line
  const chartData = rep?.chart ? (rep.chart.use_chart_rows ? rep.chart_rows : rep.rows.slice(0, 15)).map((r) => ({ name: String(r[rep.chart.label]).slice(0, 16), value: Number(r[rep.chart.value]) || 0 })) : [];
  const per = 25;
  const rows = rep ? rep.rows.slice((page - 1) * per, page * per) : [];
  return (
    <div>
      <PageHeader title="Reports & analytics" subtitle="Every figure is derived from database records">
        <Button variant="ghost" onClick={() => download(`/reports/${key}`, { ...params(), format: "pdf" }, `${key}.pdf`)}><Download size={14} /> PDF</Button>
        <Button variant="ghost" onClick={() => download(`/reports/${key}`, { ...params(), format: "xlsx" }, `${key}.xlsx`)}><FileSpreadsheet size={14} /> Excel</Button>
        <Button variant="ghost" onClick={() => window.print()}><Printer size={14} /> Print</Button>
      </PageHeader>
      <div className="card mb-4 no-print"><div className="flex flex-wrap items-end gap-3">
        <label className="text-sm">Report<select aria-label="Report" className="input mt-1" value={key} onChange={(e) => setKey(e.target.value)}>{(cat.data || []).map((r) => <option key={r.key} value={r.key}>{r.title}</option>)}</select></label>
        <label className="text-sm">From<input aria-label="From date" type="date" className="input mt-1" value={p.date_from} onChange={(e) => setP({ ...p, date_from: e.target.value })} /></label>
        <label className="text-sm">To<input aria-label="To date" type="date" className="input mt-1" value={p.date_to} onChange={(e) => setP({ ...p, date_to: e.target.value })} /></label>
        <label className="text-sm">Warehouse<select aria-label="Warehouse" className="input mt-1" value={p.warehouse_id} onChange={(e) => setP({ ...p, warehouse_id: e.target.value })}><option value="">All</option>{(whs.data || []).map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}</select></label>
        <Button onClick={run}>Run report</Button></div></div>
      <div className="card print-area">
        {rep && <><div className="mb-3"><h2 className="text-lg font-bold">{settings.company_name} - {rep.title}</h2><p className="text-xs text-slate-500">Generated {rep.generated_at} | Range: {rep.date_from || "start"} to {rep.date_to || "today"}</p></div>
          <div className="mb-3 flex flex-wrap gap-4">{Object.entries(rep.summary).map(([k, v]) => <div key={k} className="rounded-lg bg-slate-100 px-3 py-2 text-sm dark:bg-slate-700"><span className="text-slate-500">{k}: </span><b>{typeof v === "number" ? v.toLocaleString() : v}</b></div>)}</div>
          {chartData.length > 0 && <div className="no-print mb-4"><ResponsiveContainer width="100%" height={240}><BarChart data={chartData}><CartesianGrid strokeDasharray="3 3" opacity={0.3} /><XAxis dataKey="name" fontSize={10} interval={0} angle={-25} textAnchor="end" height={60} /><YAxis fontSize={11} /><Tooltip /><Bar dataKey="value" fill="#2563eb" radius={[4, 4, 0, 0]} /></BarChart></ResponsiveContainer></div>}</>}
        <DataTable loading={loading} rows={rows} rowKey="_i" columns={(rep?.columns || []).map((c) => ({ key: c.key, label: c.label }))} empty="No data for the selected filters" />
        {rep && rep.rows.length > per && <div className="no-print mt-3 flex items-center justify-between text-sm"><span>{rep.rows.length} rows - page {page} of {Math.ceil(rep.rows.length / per)}</span>
          <div className="flex gap-1"><Button variant="ghost" disabled={page <= 1} onClick={() => setPage(page - 1)}>Prev</Button><Button variant="ghost" disabled={page * per >= rep.rows.length} onClick={() => setPage(page + 1)}>Next</Button></div></div>}
      </div>
    </div>
  );
}
