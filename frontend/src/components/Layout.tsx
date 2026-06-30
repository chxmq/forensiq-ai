import { useState, type FormEvent } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import {
  LayoutGrid,
  Files,
  PlusCircle,
  ShieldAlert,
  Search,
  Settings2,
  LogOut,
  User,
} from "lucide-react";
import { clearAuth, getUsername } from "../lib/auth";

const nav = [
  { to: "/", label: "Dashboard", icon: LayoutGrid, end: true },
  { to: "/applications", label: "Applications", icon: Files },
  { to: "/new", label: "Create New", icon: PlusCircle },
  { to: "/cases", label: "Investigations", icon: ShieldAlert },
  { to: "/settings", label: "Policy", icon: Settings2 },
];

export default function Layout() {
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const username = getUsername() || "underwriter";

  const onLogout = () => {
    clearAuth();
    navigate("/login", { replace: true });
  };

  const onSearch = (e: FormEvent) => {
    e.preventDefault();
    const q = query.trim();
    navigate(q ? `/applications?q=${encodeURIComponent(q)}` : "/applications");
  };

  return (
    <div className="flex min-h-screen">
      <aside className="sticky top-0 hidden h-screen w-[248px] flex-col border-r border-line bg-surface px-4 py-5 lg:flex">
        <button onClick={() => navigate("/")} className="px-2 text-left">
          <p className="text-lg font-extrabold tracking-tight text-ink">Forensiq AI</p>
          <p className="text-[11px] uppercase tracking-[0.12em] text-faint">Underwriting Integrity</p>
        </button>

        <nav className="mt-8 space-y-1">
          {nav.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.end}
              className={({ isActive }) =>
                `relative flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-semibold transition ${
                  isActive
                    ? "bg-canvas text-ink"
                    : "text-muted hover:bg-canvas hover:text-ink"
                }`
              }
            >
              {({ isActive }) => (
                <>
                  {isActive && <span className="absolute left-0 top-1.5 h-7 w-1 rounded-full bg-navy-900" />}
                  <n.icon className="h-[18px] w-[18px]" />
                  {n.label}
                </>
              )}
            </NavLink>
          ))}
        </nav>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-20 flex h-16 items-center gap-4 border-b border-line bg-surface/90 px-5 backdrop-blur lg:px-8">
          <form onSubmit={onSearch} className="relative max-w-md flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-faint" />
            <input
              className="input pl-9"
              placeholder="Search applications, references, applicants…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </form>
          <div className="flex items-center gap-3 text-sm text-muted">
            <span className="hidden items-center gap-1.5 sm:flex">
              <User className="h-4 w-4 text-faint" /> {username}
            </span>
            <button type="button" className="btn-secondary py-1.5 text-xs" onClick={onLogout}>
              <LogOut className="h-3.5 w-3.5" /> Sign out
            </button>
          </div>
        </header>

        <main className="flex-1">
          <div className="mx-auto max-w-[1440px] px-5 py-7 lg:px-8">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
