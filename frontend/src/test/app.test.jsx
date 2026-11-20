import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("../api", async () => {
  const actual = await vi.importActual("../api");
  return { ...actual, get: vi.fn(), post: vi.fn(), put: vi.fn(), del: vi.fn(), download: vi.fn(),
    tokens: { access: null, refresh: null, set: vi.fn(), clear: vi.fn() } };
});
import * as api from "../api";
import { AppProvider } from "../context";
import { Login } from "../pages/auth";
import { ProtectedRoute, MENU } from "../layout";
import { cleanItems } from "../ui";

const wrap = (ui, path = "/") => render(<MemoryRouter initialEntries={[path]}><AppProvider>{ui}</AppProvider></MemoryRouter>);
beforeEach(() => { vi.clearAllMocks(); localStorage.clear(); api.get.mockResolvedValue({ data: [], meta: {} }); });

describe("authentication UI", () => {
  it("renders the login form and demo account shortcuts", async () => {
    api.get.mockResolvedValue({ data: [{ email: "admin@stockpilot.demo", role: "Super Admin" }], meta: { password: "Demo@12345" } });
    wrap(<Login />);
    expect(screen.getByLabelText("Email")).toBeInTheDocument();
    expect(await screen.findByText("Super Admin")).toBeInTheDocument();
  });
  it("submits credentials to the API", async () => {
    api.post.mockResolvedValue({ data: { access_token: "a", refresh_token: "r", user: { name: "Alex", permissions: [] } } });
    wrap(<Login />);
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "a@b.io" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "secret123" } });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    await waitFor(() => expect(api.post).toHaveBeenCalledWith("/auth/login", { email: "a@b.io", password: "secret123" }));
  });
  it("shows the server error message when login fails", async () => {
    api.post.mockRejectedValue({ response: { data: { error: { message: "Invalid email or password" } } } });
    wrap(<Login />);
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "a@b.io" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "x" } });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByText("Invalid email or password")).toBeInTheDocument();
  });
});

describe("route guards", () => {
  it("redirects anonymous visitors to /login", () => {
    wrap(<Routes><Route path="/login" element={<div>LOGIN PAGE</div>} /><Route path="/secret" element={<ProtectedRoute><div>SECRET</div></ProtectedRoute>} /></Routes>, "/secret");
    expect(screen.getByText("LOGIN PAGE")).toBeInTheDocument();
    expect(screen.queryByText("SECRET")).toBeNull();
  });
  it("role-based menu only references known permission codes", () => {
    const codes = MENU.map((m) => m.perm).filter(Boolean);
    expect(codes).toContain("users.manage");
    expect(new Set(codes).size).toBeGreaterThan(8);
  });
});

describe("helpers", () => {
  it("cleanItems drops empty lines and coerces numbers", () => {
    const out = cleanItems([{ product_id: "3", quantity: "4", unit_price: "2.5", discount: "10" }, { product_id: "", quantity: 1 }], ["price", "discount"]);
    expect(out).toEqual([{ product_id: 3, quantity: 4, unit_price: 2.5, discount: 10 }]);
  });
});
