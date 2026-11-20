import { useEffect, useState } from "react";
import { Link, Navigate, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { Package } from "lucide-react";
import { get, post, errMsg } from "../api";
import { useApp } from "../context";
import { Button, Input } from "../ui";

const Shell = ({ title, children }) => (
  <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-blue-600 to-indigo-800 p-4">
    <div className="w-full max-w-md rounded-2xl bg-white p-7 shadow-2xl dark:bg-slate-800 dark:text-slate-100">
      <div className="mb-5 flex items-center gap-2 text-xl font-bold text-blue-600"><Package /> StockPilot</div>
      <h1 className="mb-4 text-lg font-semibold">{title}</h1>{children}
    </div>
  </div>
);

export function Login() {
  const { user, login, notify } = useApp();
  const nav = useNavigate();
  const loc = useLocation();
  const [f, setF] = useState({ email: "", password: "" });
  const [busy, setBusy] = useState(false);
  const [demo, setDemo] = useState({ list: [], pw: "" });
  useEffect(() => { get("/auth/demo-accounts").then((r) => setDemo({ list: r.data, pw: r.meta?.password || "" })).catch(() => {}); }, []);
  if (user) return <Navigate to={loc.state?.from || "/"} replace />;
  const submit = async (e) => {
    e.preventDefault(); setBusy(true);
    try { await login(f.email, f.password); nav(loc.state?.from || "/", { replace: true }); }
    catch (err) { notify(errMsg(err), "error"); } finally { setBusy(false); }
  };
  return (
    <Shell title="Sign in to your account">
      <form onSubmit={submit} className="space-y-3">
        <Input label="Email" type="email" required autoComplete="username" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} />
        <Input label="Password" type="password" required autoComplete="current-password" value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} />
        <Button type="submit" className="w-full" disabled={busy}>{busy ? "Signing in..." : "Sign in"}</Button>
      </form>
      <div className="mt-3 flex justify-between text-sm"><Link className="text-blue-600" to="/forgot-password">Forgot password?</Link><Link className="text-blue-600" to="/register">Create account</Link></div>
      {demo.list.length > 0 && (
        <div className="mt-5 rounded-lg bg-slate-100 p-3 text-xs dark:bg-slate-700">
          <b>Demo accounts</b> (password <code>{demo.pw}</code>) - click to fill:
          <div className="mt-2 flex flex-wrap gap-1">{demo.list.map((d) => (
            <button key={d.email} className="rounded bg-white px-2 py-1 shadow-sm dark:bg-slate-800" onClick={() => setF({ email: d.email, password: demo.pw })}>{d.role}</button>))}</div>
        </div>)}
    </Shell>
  );
}

export function Register() {
  const { notify } = useApp();
  const nav = useNavigate();
  const [f, setF] = useState({ name: "", email: "", password: "" });
  const submit = async (e) => {
    e.preventDefault();
    try { await post("/auth/register", f); notify("Account created. Please sign in."); nav("/login"); } catch (err) { notify(errMsg(err), "error"); }
  };
  return (
    <Shell title="Create an account">
      <form onSubmit={submit} className="space-y-3">
        <Input label="Full name" required value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} />
        <Input label="Email" type="email" required value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} />
        <Input label="Password" type="password" required hint="Minimum 8 characters with a letter and a digit" value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} />
        <Button type="submit" className="w-full">Register</Button>
      </form>
      <p className="mt-3 text-sm">Already registered? <Link className="text-blue-600" to="/login">Sign in</Link></p>
    </Shell>
  );
}

export function Forgot() {
  const { notify } = useApp();
  const [email, setEmail] = useState("");
  const [link, setLink] = useState("");
  const submit = async (e) => {
    e.preventDefault();
    try { const r = await post("/auth/forgot-password", { email }); notify(r.message); setLink(r.data.dev_reset_link || ""); } catch (err) { notify(errMsg(err), "error"); }
  };
  return (
    <Shell title="Reset your password">
      <form onSubmit={submit} className="space-y-3">
        <Input label="Email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        <Button type="submit" className="w-full">Send reset link</Button>
      </form>
      {link && <p className="mt-3 break-all rounded bg-amber-50 p-2 text-xs text-amber-900">Development mode (no SMTP configured): <a className="underline" href={link}>open reset link</a></p>}
      <p className="mt-3 text-sm"><Link className="text-blue-600" to="/login">Back to sign in</Link></p>
    </Shell>
  );
}

export function Reset() {
  const { notify } = useApp();
  const [sp] = useSearchParams();
  const nav = useNavigate();
  const [password, setPassword] = useState("");
  const submit = async (e) => {
    e.preventDefault();
    try { await post("/auth/reset-password", { email: sp.get("email"), token: sp.get("token"), password }); notify("Password updated"); nav("/login"); } catch (err) { notify(errMsg(err), "error"); }
  };
  return (
    <Shell title="Choose a new password">
      <form onSubmit={submit} className="space-y-3">
        <Input label="New password" type="password" required hint="Minimum 8 characters with a letter and a digit" value={password} onChange={(e) => setPassword(e.target.value)} />
        <Button type="submit" className="w-full">Update password</Button>
      </form>
    </Shell>
  );
}
