// App shell: a fixed sidebar with brand + nav, and a scrollable content area.
// Responsive — the sidebar collapses to a top bar of icons on small screens.
import type { ReactNode } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { AlertTriangle, BarChart3, Bell, ListTree } from "lucide-react";
import { cn } from "@/lib/utils";

const NAV = [
  { to: "/", label: "Errors", icon: AlertTriangle, end: true },
  { to: "/runs", label: "Runs", icon: ListTree, end: false },
  { to: "/stats", label: "Stats", icon: BarChart3, end: false },
  { to: "/alerts", label: "Alerts", icon: Bell, end: false },
];

export function Layout() {
  return (
    <div className="flex min-h-screen">
      <aside className="flex w-16 flex-col border-r border-border bg-surface/50 md:w-56">
        <div className="flex h-16 items-center gap-2 border-b border-border px-4">
          <span className="text-2xl">🐤</span>
          <div className="hidden md:block">
            <p className="text-sm font-semibold leading-none">Canary</p>
            <p className="mt-1 text-[10px] uppercase tracking-widest text-muted">agent errors</p>
          </div>
        </div>

        <nav className="flex flex-1 flex-col gap-1 p-2">
          {NAV.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                  isActive
                    ? "bg-surface-2 text-fg"
                    : "text-muted hover:bg-surface-2/60 hover:text-fg",
                )
              }
            >
              <Icon className="h-4 w-4 shrink-0" />
              <span className="hidden md:inline">{label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="hidden border-t border-border p-3 md:block">
          <p className="text-[10px] leading-relaxed text-muted">
            Sentry for AI agents.
            <br />
            Error tracking, not analytics.
          </p>
        </div>
      </aside>

      <main className="flex-1 overflow-x-hidden">
        <Outlet />
      </main>
    </div>
  );
}

/** Shared page header used by every route. */
export function PageHeader({
  title,
  subtitle,
  actions,
}: {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="sticky top-0 z-10 flex items-center justify-between border-b border-border bg-bg/80 px-6 py-4 backdrop-blur">
      <div>
        <h1 className="text-lg font-semibold tracking-tight">{title}</h1>
        {subtitle && <p className="text-xs text-muted">{subtitle}</p>}
      </div>
      {actions}
    </div>
  );
}
