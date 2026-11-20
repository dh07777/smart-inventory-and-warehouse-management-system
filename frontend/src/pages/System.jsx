import { useState } from "react";
import { Trash2, DatabaseBackup, Download, RotateCcw } from "lucide-react";
import { get, post, put, del, download, errMsg } from "../api";
import { useApp } from "../context";
import { useFetch, useList } from "../hooks";
import { Button, Input, Badge, DataTable, Pagination, Tabs, PageHeader, SearchBox, Confirm } from "../ui";

export function Notifications() {
  const { notify } = useApp();
  const [unread, setUnread] = useState(false);
  const list = useList("/notifications", { per_page: 15 });
  const act = async (fn) => { try { await fn(); list.reload(); } catch (e) { notify(errMsg(e), "error"); } };
  return (
    <div>
      <PageHeader title="Notification center" subtitle="Stock, purchase, sales, expiry and transfer alerts">
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={unread} onChange={(e) => { setUnread(e.target.checked); list.set({ unread: e.target.checked ? "true" : "" }); }} /> Unread only</label>
        <Button variant="ghost" onClick={() => act(() => post("/notifications/read-all"))}>Mark all read</Button></PageHeader>
      <div className="card"><DataTable loading={list.loading} rows={list.rows} empty="No notifications" columns={[
        { key: "title", label: "Notification", render: (r) => <div className={r.is_read ? "" : "font-semibold"}>{r.title}<div className="text-xs font-normal text-slate-500">{r.message}</div></div> }, { key: "type", label: "Type", render: (r) => <Badge value={r.type} /> },
        { key: "created_at", label: "When", render: (r) => r.created_at.slice(0, 16).replace("T", " ") }, { key: "is_read", label: "Status", render: (r) => (r.is_read ? "Read" : <b className="text-blue-600">Unread</b>) },
        { key: "x", label: "", render: (r) => <div className="flex gap-1">{!r.is_read && <Button variant="ghost" onClick={() => act(() => post(`/notifications/${r.id}/read`))}>Mark read</Button>}<Button variant="ghost" aria-label="Delete notification" onClick={() => act(() => del(`/notifications/${r.id}`))}><Trash2 size={14} /></Button></div> }]} /><Pagination meta={list.meta} onPage={list.setPage} /></div>
    </div>
  );
}

export function Audit() {
  const [tab, setTab] = useState("audit");
  const logs = useList("/admin/audit-logs", { per_page: 15 });
  const logins = useList("/admin/login-history", { per_page: 15 });
  return (
    <div>
      <PageHeader title="Audit & system activity" subtitle="Critical operations and sign-in history" />
      <Tabs value={tab} onChange={setTab} tabs={[{ key: "audit", label: "Audit log" }, { key: "login", label: "Login history" }]} />
      <div className="card">
        {tab === "audit" ? <><div className="mb-3 flex flex-wrap gap-2"><SearchBox onSearch={(q) => logs.set({ q })} placeholder="Search action or details" />
          <input aria-label="From date" type="date" className="input w-auto" onChange={(e) => logs.set({ date_from: e.target.value })} /><input aria-label="To date" type="date" className="input w-auto" onChange={(e) => logs.set({ date_to: e.target.value })} /></div>
          <DataTable loading={logs.loading} rows={logs.rows} columns={[{ key: "created_at", label: "Time", render: (r) => r.created_at.slice(0, 19).replace("T", " ") }, { key: "user_name", label: "User" }, { key: "action", label: "Action" }, { key: "entity", label: "Entity" }, { key: "entity_id", label: "ID" },
            { key: "details", label: "Details", render: (r) => <span className="block max-w-xs truncate text-xs text-slate-500" title={r.details}>{r.details}</span> }, { key: "ip_address", label: "IP" }]} /><Pagination meta={logs.meta} onPage={logs.setPage} /></>
          : <><DataTable loading={logins.loading} rows={logins.rows} columns={[{ key: "created_at", label: "Time", render: (r) => r.created_at.slice(0, 19).replace("T", " ") }, { key: "email", label: "Email" }, { key: "success", label: "Result", render: (r) => <Badge value={r.success ? "ok" : "rejected"} /> }, { key: "ip_address", label: "IP" }, { key: "user_agent", label: "Device", render: (r) => <span className="block max-w-xs truncate text-xs">{r.user_agent}</span> }]} /><Pagination meta={logins.meta} onPage={logins.setPage} /></>}
      </div>
    </div>
  );
}

function Backups() {
  const { notify } = useApp();
  const { data, reload } = useFetch("/admin/backups");
  const [restore, setRestore] = useState(null);
  const act = async (fn, msg) => { try { await fn(); notify(msg); reload(); } catch (e) { notify(errMsg(e), "error"); } };
  return (
    <div className="card"><div className="mb-3 flex items-center justify-between"><h3 className="font-semibold">Database backup & restore</h3><Button onClick={() => act(() => post("/admin/backups"), "Backup created")}><DatabaseBackup size={14} /> Create backup now</Button></div>
      <DataTable rows={data || []} rowKey="name" empty="No backups yet" columns={[{ key: "name", label: "File" }, { key: "size_kb", label: "Size (KB)" }, { key: "created_at", label: "Created", render: (r) => r.created_at.slice(0, 16).replace("T", " ") },
        { key: "x", label: "", render: (r) => <div className="flex gap-1"><Button variant="ghost" aria-label="Download backup" onClick={() => download(`/admin/backups/${r.name}/download`, {}, r.name)}><Download size={14} /></Button>
          <Button variant="ghost" onClick={() => setRestore(r)}><RotateCcw size={14} /> Restore</Button><Button variant="ghost" aria-label="Delete backup" onClick={() => act(() => del(`/admin/backups/${r.name}`), "Backup deleted")}><Trash2 size={14} /></Button></div> }]} />
      <p className="mt-2 text-xs text-slate-500">Restoring replaces ALL current data with the backup. A safety copy of the current database ("prerestore") is made automatically first.</p>
      {restore && <Confirm message={`Restore ${restore.name}? All data created after this backup will be lost.`} onNo={() => setRestore(null)} onYes={() => { const n = restore.name; setRestore(null); act(() => post(`/admin/backups/${n}/restore`), "Database restored"); }} />}
    </div>
  );
}

export function SettingsPage() {
  const { notify, setSettings } = useApp();
  const [tab, setTab] = useState("company");
  const { data, reload } = useFetch("/admin/settings");
  const whs = useFetch("/warehouses", { per_page: 100 });
  const [f, setF] = useState(null);
  const v = f || data;
  const save = async (keys) => {
    try { const r = await put("/admin/settings", Object.fromEntries(keys.map((k) => [k, v[k]]))); notify("Settings saved"); setF(null); reload(); setSettings((s) => ({ ...s, ...r.data })); } catch (e) { notify(errMsg(e), "error"); }
  };
  const set = (k) => (e) => setF({ ...v, [k]: e.target.value });
  return (
    <div>
      <PageHeader title="Settings" subtitle="Company, currency & tax, inventory rules, notifications and backups" />
      <Tabs value={tab} onChange={setTab} tabs={[{ key: "company", label: "Company" }, { key: "money", label: "Currency & tax" }, { key: "inventory", label: "Inventory & warehouse" }, { key: "notif", label: "Notification preferences" }, { key: "backup", label: "Backup & restore" }]} />
      {v && tab === "company" && <div className="card grid max-w-2xl gap-3">{[["company_name", "Company name"], ["company_address", "Address"], ["company_email", "Email"], ["company_phone", "Phone"]].map(([k, l]) => <Input key={k} label={l} value={v[k] || ""} onChange={set(k)} />)}<div><Button onClick={() => save(["company_name", "company_address", "company_email", "company_phone"])}>Save</Button></div></div>}
      {v && tab === "money" && <div className="card grid max-w-2xl gap-3"><Input label="Currency code" value={v.currency_code} onChange={set("currency_code")} /><Input label="Currency symbol" value={v.currency_symbol} onChange={set("currency_symbol")} /><Input label="Default tax rate (%)" type="number" value={v.default_tax_rate} onChange={set("default_tax_rate")} /><div><Button onClick={() => save(["currency_code", "currency_symbol", "default_tax_rate"])}>Save</Button></div></div>}
      {v && tab === "inventory" && <div className="card grid max-w-2xl gap-3"><Input label="Expiry alert window (days)" type="number" value={v.expiry_alert_days} onChange={set("expiry_alert_days")} />
        <Input label="Default warehouse (pre-selected in forms)" type="select" value={v.default_warehouse_id || ""} onChange={set("default_warehouse_id")} options={(whs.data || []).map((w) => ({ value: w.id, label: w.name }))} />
        <Input label="Default minimum stock for new products" type="number" min="0" value={v.default_min_stock} onChange={set("default_min_stock")} />
        <Input type="checkbox" label="Allow authorized negative-stock override (Super Admin only)" value={v.allow_negative_override === "true"} onChange={(e) => setF({ ...v, allow_negative_override: String(e.target.value) })} />
        <Input type="checkbox" label="Allow public self-registration" value={v.allow_registration === "true"} onChange={(e) => setF({ ...v, allow_registration: String(e.target.value) })} />
        <div><Button onClick={() => save(["expiry_alert_days", "allow_negative_override", "allow_registration", "default_warehouse_id", "default_min_stock"])}>Save</Button></div></div>}
      {tab === "notif" && <PrefsCard />}
      {tab === "backup" && <Backups />}
    </div>
  );
}

export function PrefsCard() {
  const { user, setUser, notify } = useApp();
  const prefs = user.notification_prefs || {};
  const labels = { low_stock: "Low-stock & out-of-stock", purchase: "Purchase orders", sales: "Sales orders", expiry: "Expiry alerts", transfer: "Stock transfers" };
  const toggle = async (k) => { try { const r = await put("/auth/me/preferences", { [k]: !(prefs[k] ?? true) }); setUser(r.data); } catch (e) { notify(errMsg(e), "error"); } };
  return <div className="card max-w-xl space-y-2"><h3 className="font-semibold">My notification preferences</h3>{Object.entries(labels).map(([k, l]) => <label key={k} className="flex items-center gap-2 text-sm"><input type="checkbox" checked={prefs[k] ?? true} onChange={() => toggle(k)} />{l}</label>)}</div>;
}

export function Profile() {
  const { user, setUser, notify } = useApp();
  const [f, setF] = useState({ name: user.name, phone: user.phone || "" });
  const [pw, setPw] = useState({ current_password: "", new_password: "" });
  const hist = useList("/auth/me/login-history", { per_page: 5 });
  return (
    <div className="space-y-4">
      <PageHeader title="My account" subtitle={`${user.email} - ${user.role_name}`} />
      <div className="grid gap-4 lg:grid-cols-2">
        <div className="card space-y-3"><h3 className="font-semibold">Profile</h3><Input label="Name" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /><Input label="Phone" value={f.phone} onChange={(e) => setF({ ...f, phone: e.target.value })} />
          <Button onClick={async () => { try { const r = await put("/auth/me", f); setUser(r.data); notify("Profile updated"); } catch (e) { notify(errMsg(e), "error"); } }}>Save profile</Button></div>
        <div className="card space-y-3"><h3 className="font-semibold">Change password</h3><Input label="Current password" type="password" value={pw.current_password} onChange={(e) => setPw({ ...pw, current_password: e.target.value })} />
          <Input label="New password" type="password" hint="Minimum 8 characters with a letter and a digit" value={pw.new_password} onChange={(e) => setPw({ ...pw, new_password: e.target.value })} />
          <Button onClick={async () => { try { await post("/auth/change-password", pw); notify("Password changed"); setPw({ current_password: "", new_password: "" }); } catch (e) { notify(errMsg(e), "error"); } }}>Update password</Button></div>
      </div>
      <PrefsCard />
      <div className="card"><h3 className="mb-2 font-semibold">Recent sign-ins</h3><DataTable loading={hist.loading} rows={hist.rows} columns={[{ key: "created_at", label: "Time", render: (r) => r.created_at.slice(0, 19).replace("T", " ") }, { key: "ip_address", label: "IP" }, { key: "success", label: "Result", render: (r) => <Badge value={r.success ? "ok" : "rejected"} /> }]} /></div>
    </div>
  );
}
