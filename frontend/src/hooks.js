import { useCallback, useEffect, useRef, useState } from "react";
import { get, errMsg } from "./api";
import { useApp } from "./context";

/** Paginated, searchable list bound to a Flask endpoint. */
export function useList(url, initial = {}) {
  const { notify } = useApp();
  const [params, setParams] = useState({ page: 1, per_page: 10, ...initial });
  const [rows, setRows] = useState([]);
  const [meta, setMeta] = useState({ page: 1, pages: 1, total: 0 });
  const [loading, setLoading] = useState(true);
  const seq = useRef(0);
  const load = useCallback(async () => {
    const my = ++seq.current;
    setLoading(true);
    try {
      const clean = Object.fromEntries(Object.entries(params).filter(([, v]) => v !== "" && v != null));
      const r = await get(url, clean);
      if (my === seq.current) { setRows(r.data); setMeta(r.meta || {}); }
    } catch (e) { notify(errMsg(e), "error"); }
    finally { if (my === seq.current) setLoading(false); }
  }, [url, JSON.stringify(params)]); // eslint-disable-line
  useEffect(() => { load(); }, [load]);
  const set = (patch) => setParams((p) => ({ ...p, page: 1, ...patch }));
  return { rows, meta, loading, params, set, setPage: (page) => setParams((p) => ({ ...p, page })), reload: load };
}

export function useFetch(url, params, deps = []) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const load = useCallback(async () => {
    setLoading(true);
    try { setData((await get(url, params)).data); setError(null); } catch (e) { setError(errMsg(e)); } finally { setLoading(false); }
  }, [url, JSON.stringify(params), ...deps]); // eslint-disable-line
  useEffect(() => { load(); }, [load]);
  return { data, loading, error, reload: load };
}

export const useDebounced = (value, ms = 350) => {
  const [v, setV] = useState(value);
  useEffect(() => { const t = setTimeout(() => setV(value), ms); return () => clearTimeout(t); }, [value, ms]);
  return v;
};
