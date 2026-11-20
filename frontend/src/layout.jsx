import { useEffect, useState } from "react";
import { NavLink, Navigate, Outlet, useLocation, useNavigate } from "react-router-dom";
import { LayoutDashboard, Package, Warehouse, Boxes, Truck, ShoppingCart, Receipt, ArrowLeftRight, Users, BarChart3, Bell, ScrollText, Settings, UserCog,
  Menu, Moon, Sun, LogOut, Search, UserCircle, FolderTree } from "lucide-react";
import { useApp } from "./context";
import { get } from "./api";
import { cx } from "./ui";

export const MENU = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, perm: "dashboard.view" },
  { to: "/products", label: "Products", icon: Package, perm: "products.view" },
  { to: "/categories", label: "Categories", icon: FolderTree, perm: "products.view" },
  { to: "/warehouses", label: "Warehouses", icon: Warehouse, perm: "warehouses.view" },
  { to: "/inventory", label: "Inventory", icon: Boxes, perm: "inventory.view" },
  { to: "/transfers", label: "Transfers", icon: ArrowLeftRight, perm: "transfers.view" },
  { to: "/suppliers", label: "Suppliers", icon: Truck, perm: "suppliers.view" },
  { to: "/purchases", label: "Purchases", icon: ShoppingCart, perm: "purchases.view" },
  { to: "/customers", label: "Customers", icon: Users, perm: "customers.view" },
  { to: "/sales", label: "Sales", icon: Receipt, perm: "sales.view" },
  { to: "/reports", label: "Reports", icon: BarChart3, perm: "reports.view" },
  { to: "/notifications", label: "Notifications", icon: Bell, perm: null },
  { to: "/users", label: "Users & Roles", icon: UserCog, perm: "users.manage" },
  { to: "/audit", label: "Audit & Activity", icon: ScrollText, perm: "audit.view" },
  { to: "/settings", label: "Settings", icon: Settings, perm: "settings.manage" },
];

export function ProtectedRoute({ perm, children }) {
  const { user, booting, can } = useApp();
  const loc = useLocation();
  if (booting) return <div className="p-10 text-center text-slate-500">Loading...</div>;
  if (!user) return <Navigate to="/login" replace state={{ from: loc.pathname }} />;
  if (perm && !can(perm)) return <div className="card m-6 text-center"><h2 className="text-lg font-semibold">Access denied</h2><p className="text-sm text-slate-500">Your role does not include permission to view this page.</p></div>;
  return children;
}

function Bell_() {
  const [n, setN] = useState(0);
  const [items, setItems] = useState([]);
  const [open, setOpen] = useState(false);
  const nav = useNavigate();
  const refresh = () => get("/notifications/unread-count").then((r) => setN(r.data.count)).catch(() => {});
  useEffect(() => { refresh(); const t = setInterval(refresh, 60000); return () => clearInterval(t); }, []);
  const toggle = async () => {
    setOpen(!open);
    if (!open) setItems((await get("/notifications", { per_page: 6 })).data);
  };
  return (
    <div className="relative">
      <button onClick={toggle} aria-label="Notifications" className="relative rounded-lg p-2 hover:bg-slate-100 dark:hover:bg-slate-700">
        <Bell size={20} />{n > 0 && <span className="absolute -right-0.5 -top-0.5 min-w-[18px] rounded-full bg-red-600 px-1 text-center text-[10px] text-white">{n > 99 ? "99+" : n}</span>}
      </button>
      {open && (
        <div className="absolute right-0 z-40 mt-2 w-80 rounded-xl border border-slate-200 bg-white shadow-xl dark:border-slate-700 dark:bg-slate-800">
          <div className="border-b px-4 py-2 text-sm font-semibold dark:border-slate-700">Notifications</div>
          {items.length === 0 && <div className="p-4 text-sm text-slate-500">You're all caught up.</div>}
          {items.map((i) => <div key={i.id} className={cx("border-b px-4 py-2 text-sm dark:border-slate-700", !i.is_read && "bg-blue-50 dark:bg-slate-700/50")}><div className="font-medium">{i.title}</div><div className="text-xs text-slate-500">{i.message}</div></div>)}
          <button className="w-full px-4 py-2 text-sm text-blue-600" onClick={() => { setOpen(false); nav("/notifications"); }}>View all</button>
        </div>)}
    </div>
  );
}

export function Layout() {
  const { user, can, logout, dark, setDark, settings } = useApp();
  const [open, setOpen] = useState(false);
  const [menu, setMenu] = useState(false);
  const [q, setQ] = useState("");
  const nav = useNavigate();
  const loc = useLocation();
  useEffect(() => setOpen(false), [loc.pathname]);
  return (
    <div className="min-h-screen text-slate-900 dark:text-slate-100">
      {open && <div className="fixed inset-0 z-30 bg-black/40 lg:hidden" onClick={() => setOpen(false)} />}
      <aside className={cx("fixed inset-y-0 left-0 z-40 w-64 overflow-y-auto border-r border-slate-200 bg-white transition-transform dark:border-slate-700 dark:bg-slate-800 no-print", open ? "translate-x-0" : "-translate-x-full lg:translate-x-0")}>
        <div className="flex items-center gap-2 px-5 py-4 text-lg font-bold text-blue-600"><Package /> StockPilot</div>
        <nav className="space-y-0.5 px-3 pb-6" aria-label="Main">
          {MENU.filter((m) => !m.perm || can(m.perm)).map((m) => (
            <NavLink key={m.to} to={m.to} end={m.to === "/"} className={({ isActive }) => cx("flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium",
              isActive ? "bg-blue-50 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300" : "text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-700")}>
              <m.icon size={18} />{m.label}</NavLink>))}
        </nav>
      </aside>
      <div className="lg:pl-64">
        <header className="sticky top-0 z-20 flex items-center gap-3 border-b border-slate-200 bg-white/90 px-4 py-2.5 backdrop-blur dark:border-slate-700 dark:bg-slate-800/90 no-print">
          <button className="rounded-lg p-2 hover:bg-slate-100 dark:hover:bg-slate-700 lg:hidden" aria-label="Open menu" onClick={() => setOpen(true)}><Menu size={20} /></button>
          <form className="relative hidden max-w-md flex-1 sm:block" onSubmit={(e) => { e.preventDefault(); nav(`/products?q=${encodeURIComponent(q)}`); }}>
            <Search size={16} className="absolute left-3 top-2.5 text-slate-400" />
            <input aria-label="Global product search" className="input pl-9" placeholder="Search products by name, SKU or barcode..." value={q} onChange={(e) => setQ(e.target.value)} />
          </form>
          <div className="ml-auto flex items-center gap-1">
            <button onClick={() => setDark(!dark)} aria-label="Toggle dark mode" className="rounded-lg p-2 hover:bg-slate-100 dark:hover:bg-slate-700">{dark ? <Sun size={20} /> : <Moon size={20} />}</button>
            <Bell_ />
            <div className="relative">
              <button onClick={() => setMenu(!menu)} className="flex items-center gap-2 rounded-lg p-1.5 hover:bg-slate-100 dark:hover:bg-slate-700" aria-label="Profile menu">
                <UserCircle size={24} /><span className="hidden text-left text-xs leading-tight sm:block"><b className="block text-sm">{user.name}</b>{user.role_name}</span></button>
              {menu && (
                <div className="absolute right-0 z-40 mt-2 w-48 rounded-xl border border-slate-200 bg-white py-1 shadow-xl dark:border-slate-700 dark:bg-slate-800" onClick={() => setMenu(false)}>
                  <button className="block w-full px-4 py-2 text-left text-sm hover:bg-slate-100 dark:hover:bg-slate-700" onClick={() => nav("/profile")}>My profile</button>
                  <button className="flex w-full items-center gap-2 px-4 py-2 text-left text-sm text-red-600 hover:bg-slate-100 dark:hover:bg-slate-700" onClick={async () => { await logout(); nav("/login"); }}><LogOut size={15} />Sign out</button>
                </div>)}
            </div>
          </div>
        </header>
        {settings.demo_data === "true" && <div className="bg-amber-100 px-4 py-1.5 text-center text-xs text-amber-900 no-print">Demo mode: all records are generated sample data, not real business transactions.</div>}
        <main className="p-4 sm:p-6"><Outlet /></main>
      </div>
    </div>
  );
}
