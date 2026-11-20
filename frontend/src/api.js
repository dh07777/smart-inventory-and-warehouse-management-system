import axios from "axios";

const api = axios.create({ baseURL: import.meta.env.VITE_API_URL || "/api" });
export const tokens = {
  get access() { return localStorage.getItem("sp_access"); },
  get refresh() { return localStorage.getItem("sp_refresh"); },
  set(a, r) { localStorage.setItem("sp_access", a); if (r) localStorage.setItem("sp_refresh", r); },
  clear() { localStorage.removeItem("sp_access"); localStorage.removeItem("sp_refresh"); },
};

api.interceptors.request.use((cfg) => {
  if (tokens.access) cfg.headers.Authorization = `Bearer ${tokens.access}`;
  return cfg;
});

let refreshing = null;
api.interceptors.response.use(
  (r) => r,
  async (err) => {
    const orig = err.config;
    const code = err.response?.data?.error?.code;
    if (err.response?.status === 401 && code === "token_expired" && tokens.refresh && !orig._retry) {
      orig._retry = true;
      refreshing = refreshing || axios.post((import.meta.env.VITE_API_URL || "/api") + "/auth/refresh", {}, { headers: { Authorization: `Bearer ${tokens.refresh}` } })
        .finally(() => { setTimeout(() => (refreshing = null), 0); });
      try {
        const r = await refreshing;
        tokens.set(r.data.data.access_token);
        orig.headers.Authorization = `Bearer ${tokens.access}`;
        return api(orig);
      } catch { /* fall through to logout */ }
    }
    if (err.response?.status === 401 && !orig.url.includes("/auth/login")) {
      tokens.clear();
      window.dispatchEvent(new Event("sp:logout"));
    }
    return Promise.reject(err);
  }
);

export const errMsg = (e) => {
  const er = e?.response?.data?.error;
  if (!er) return e?.message || "Something went wrong";
  let d = "";
  if (er.details && typeof er.details === "object") {
    d = " (" + Object.entries(er.details).map(([k, v]) => `${k}: ${typeof v === "object" ? JSON.stringify(v) : v}`).join("; ") + ")";
  }
  return er.message + d;
};
export const get = async (url, params) => (await api.get(url, { params })).data;
export const post = async (url, body) => (await api.post(url, body ?? {})).data;
export const put = async (url, body) => (await api.put(url, body ?? {})).data;
export const del = async (url) => (await api.delete(url)).data;

export async function download(url, params, fallbackName) {
  const r = await api.get(url, { params, responseType: "blob" });
  const cd = r.headers["content-disposition"] || "";
  const name = (cd.match(/filename\*?=(?:UTF-8'')?"?([^";]+)"?/i) || [])[1] || fallbackName;
  const a = document.createElement("a");
  a.href = URL.createObjectURL(r.data);
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
}
export default api;
