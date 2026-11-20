import { useEffect, useState } from "react";
import { Plus, Pencil, Trash2 } from "lucide-react";
import { get, post, put, del, errMsg } from "./api";
import { useApp } from "./context";
import { useList } from "./hooks";
import { Button, Modal, Input, SearchBox, DataTable, Pagination, PageHeader, Confirm } from "./ui";

/** Generic master-data page: search, filter, sort, paginate, create, edit, delete - all against a real API endpoint. */
export default function CrudPage({ title, subtitle, entity, endpoint, columns, fields, manage, defaults = {}, filters = [], searchHint, rowActions, toolbar, initialSort = {}, beforeSubmit, listUrl, noDelete }) {
  const { can, notify } = useApp();
  const list = useList(listUrl || endpoint, { sort: initialSort.sort, order: initialSort.order });
  const [form, setForm] = useState(null);
  const [editing, setEditing] = useState(null);
  const [errors, setErrors] = useState({});
  const [saving, setSaving] = useState(false);
  const [removing, setRemoving] = useState(null);
  const [opts, setOpts] = useState({});

  useEffect(() => {
    fields.filter((f) => f.optionsUrl).forEach(async (f) => {
      try {
        const r = await get(f.optionsUrl, { per_page: 200 });
        setOpts((o) => ({ ...o, [f.name]: r.data.map((x) => ({ value: x.id, label: f.optionLabel ? f.optionLabel(x) : x.name })) }));
      } catch { /* ignore */ }
    });
  }, []); // eslint-disable-line

  const open = (row) => {
    setEditing(row);
    setErrors({});
    const v = { ...defaults };
    fields.forEach((f) => { v[f.name] = row ? (row[f.name] ?? "") : (defaults[f.name] ?? (f.type === "checkbox" ? true : "")); });
    setForm(v);
  };
  const submit = async () => {
    setSaving(true); setErrors({});
    try {
      let body = {};
      fields.forEach((f) => {
        if (f.createOnly && editing) return;
        let v = form[f.name];
        if (f.type === "number" || f.numeric) v = v === "" ? undefined : Number(v);
        if (f.type === "select" && f.numeric !== false && f.optionsUrl) v = v === "" ? null : Number(v);
        body[f.name] = v;
      });
      if (beforeSubmit) body = beforeSubmit(body, editing);
      editing ? await put(`${endpoint}/${editing.id}`, body) : await post(endpoint, body);
      notify(`${entity} ${editing ? "updated" : "created"}`);
      setForm(null);
      list.reload();
    } catch (e) {
      const d = e.response?.data?.error?.details;
      if (d && typeof d === "object") setErrors(Object.fromEntries(Object.entries(d).map(([k, v]) => [k, Array.isArray(v) ? v.join(", ") : JSON.stringify(v)])));
      notify(errMsg(e), "error");
    } finally { setSaving(false); }
  };
  const remove = async () => {
    try { await del(`${endpoint}/${removing.id}`); notify(`${entity} deleted`); setRemoving(null); list.reload(); }
    catch (e) { notify(errMsg(e), "error"); setRemoving(null); }
  };

  const cols = [...columns, { key: "_a", label: "", render: (r) => (
    <div className="flex justify-end gap-1 whitespace-nowrap">
      {rowActions?.(r, list.reload)}
      {can(manage) && <Button variant="ghost" onClick={() => open(r)} aria-label={`Edit ${r.name || r.id}`}><Pencil size={14} /></Button>}
      {can(manage) && !noDelete && <Button variant="ghost" onClick={() => setRemoving(r)} aria-label={`Delete ${r.name || r.id}`}><Trash2 size={14} /></Button>}
    </div>) }];

  return (
    <div>
      <PageHeader title={title} subtitle={subtitle}>
        {toolbar?.(list.reload)}
        {can(manage) && <Button onClick={() => open(null)}><Plus size={16} /> Add {entity}</Button>}
      </PageHeader>
      <div className="card">
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <SearchBox onSearch={(q) => list.set({ q })} placeholder={searchHint || `Search ${title.toLowerCase()}...`} />
          {filters.map((f) => (
            <select key={f.name} aria-label={f.label} className="input w-auto" value={list.params[f.name] ?? ""} onChange={(e) => list.set({ [f.name]: e.target.value })}>
              <option value="">{f.label}</option>{(f.options || opts[f.name] || []).map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}</select>))}
        </div>
        <DataTable columns={cols} rows={list.rows} loading={list.loading} sort={list.params}
          onSort={(k) => list.set({ sort: k, order: list.params.sort === k && list.params.order === "asc" ? "desc" : "asc" })} />
        <Pagination meta={list.meta} onPage={list.setPage} />
      </div>
      {form && (
        <Modal title={`${editing ? "Edit" : "Add"} ${entity}`} onClose={() => setForm(null)} wide={fields.length > 8}
          footer={<><Button variant="ghost" onClick={() => setForm(null)}>Cancel</Button><Button disabled={saving} onClick={submit}>{saving ? "Saving..." : "Save"}</Button></>}>
          <div className={fields.length > 6 ? "grid gap-3 sm:grid-cols-2" : "space-y-3"}>
            {fields.filter((f) => !(f.createOnly && editing)).map((f) => (
              <div key={f.name} className={f.type === "textarea" ? "sm:col-span-2" : ""}>
                <Input label={f.label + (f.required ? " *" : "")} type={f.type === "number" ? "number" : f.type} step={f.step} hint={f.hint} error={errors[f.name]}
                  options={f.options || opts[f.name]} value={form[f.name] ?? ""} onChange={(e) => setForm({ ...form, [f.name]: e.target.value })} />
              </div>))}
          </div>
        </Modal>)}
      {removing && <Confirm message={`Delete "${removing.name || removing.id}"? Records already used elsewhere cannot be deleted - deactivate them instead.`} onYes={remove} onNo={() => setRemoving(null)} />}
    </div>
  );
}
