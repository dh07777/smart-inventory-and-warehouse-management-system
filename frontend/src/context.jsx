import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import api, { get, post, tokens } from "./api";

const Ctx = createContext(null);
export const useApp = () => useContext(Ctx);

export function AppProvider({ children }) {
  const [user, setUser] = useState(null);
  const [booting, setBooting] = useState(!!tokens.access);
  const [settings, setSettings] = useState({ currency_symbol: "$", company_name: "StockPilot", demo_data: "false" });
  const [toasts, setToasts] = useState([]);
  const [dark, setDark] = useState(() => localStorage.getItem("sp_dark") === "1");

  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    localStorage.setItem("sp_dark", dark ? "1" : "0");
  }, [dark]);

  const notify = useCallback((message, type = "success") => {
    const id = Math.random();
    setToasts((t) => [...t, { id, message, type }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 4500);
  }, []);

  const loadMe = useCallback(async () => {
    try {
      const r = await get("/auth/me");
      setUser(r.data);
      get("/settings/public").then((s) => setSettings(s.data)).catch(() => {});
    } catch { setUser(null); }
    finally { setBooting(false); }
  }, []);

  useEffect(() => { if (tokens.access) loadMe(); else setBooting(false); }, [loadMe]);
  useEffect(() => {
    const out = () => { setUser(null); };
    window.addEventListener("sp:logout", out);
    return () => window.removeEventListener("sp:logout", out);
  }, []);

  const login = async (email, password) => {
    const r = await post("/auth/login", { email, password });
    tokens.set(r.data.access_token, r.data.refresh_token);
    setUser(r.data.user);
    get("/settings/public").then((s) => setSettings(s.data)).catch(() => {});
  };
  const logout = async () => {
    try { await post("/auth/logout", { refresh_token: tokens.refresh }); } catch { /* ignore */ }
    tokens.clear();
    setUser(null);
  };
  const can = useCallback((...codes) => !!user && (codes.length === 0 || codes.some((c) => user.permissions.includes(c))), [user]);
  const money = useCallback((n) => `${settings.currency_symbol || "$"}${Number(n || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`, [settings]);

  const value = useMemo(() => ({ user, setUser, booting, login, logout, can, money, settings, setSettings, notify, dark, setDark, loadMe }),
    [user, booting, can, money, settings, notify, dark, loadMe]);
  return (
    <Ctx.Provider value={value}>
      {children}
      <div className="fixed bottom-4 right-4 z-[100] space-y-2" role="status" aria-live="polite">
        {toasts.map((t) => (
          <div key={t.id} className={`max-w-sm rounded-lg px-4 py-3 text-sm text-white shadow-lg ${t.type === "error" ? "bg-red-600" : "bg-emerald-600"}`}>{t.message}</div>
        ))}
      </div>
    </Ctx.Provider>
  );
}
