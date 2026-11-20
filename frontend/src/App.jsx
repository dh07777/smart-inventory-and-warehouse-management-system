import { Navigate, Route, Routes } from "react-router-dom";
import { Layout, ProtectedRoute } from "./layout";
import { Login, Register, Forgot, Reset } from "./pages/auth";
import Dashboard from "./pages/Dashboard";
import { Products, Categories, Warehouses, Suppliers, Customers, UsersPage } from "./pages/masters";
import Inventory from "./pages/Inventory";
import Purchases from "./pages/Purchases";
import Sales from "./pages/Sales";
import Transfers from "./pages/Transfers";
import Reports from "./pages/Reports";
import { Notifications, Audit, SettingsPage, Profile } from "./pages/System";

const P = ({ perm, children }) => <ProtectedRoute perm={perm}>{children}</ProtectedRoute>;

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route path="/forgot-password" element={<Forgot />} />
      <Route path="/reset-password" element={<Reset />} />
      <Route element={<ProtectedRoute><Layout /></ProtectedRoute>}>
        <Route index element={<P perm="dashboard.view"><Dashboard /></P>} />
        <Route path="products" element={<P perm="products.view"><Products /></P>} />
        <Route path="categories" element={<P perm="products.view"><Categories /></P>} />
        <Route path="warehouses" element={<P perm="warehouses.view"><Warehouses /></P>} />
        <Route path="inventory" element={<P perm="inventory.view"><Inventory /></P>} />
        <Route path="transfers" element={<P perm="transfers.view"><Transfers /></P>} />
        <Route path="suppliers" element={<P perm="suppliers.view"><Suppliers /></P>} />
        <Route path="purchases" element={<P perm="purchases.view"><Purchases /></P>} />
        <Route path="customers" element={<P perm="customers.view"><Customers /></P>} />
        <Route path="sales" element={<P perm="sales.view"><Sales /></P>} />
        <Route path="reports" element={<P perm="reports.view"><Reports /></P>} />
        <Route path="notifications" element={<Notifications />} />
        <Route path="users" element={<P perm="users.manage"><UsersPage /></P>} />
        <Route path="audit" element={<P perm="audit.view"><Audit /></P>} />
        <Route path="settings" element={<P perm="settings.manage"><SettingsPage /></P>} />
        <Route path="profile" element={<Profile />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
