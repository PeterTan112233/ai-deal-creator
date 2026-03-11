import { NavLink, Outlet } from "react-router-dom";
import { Activity, BarChart2, Play, Bell, Database, FileCheck } from "lucide-react";
import { cn } from "../lib/utils";

const navItems = [
  { to: "/deals", icon: Database, label: "Deal Registry" },
  { to: "/health", icon: Activity, label: "Deal Health" },
  { to: "/portfolio", icon: BarChart2, label: "Portfolio Scoring" },
  { to: "/scenarios", icon: Play, label: "Scenario Runner" },
  { to: "/watchlist", icon: Bell, label: "Watchlist" },
  { to: "/drafts", icon: FileCheck, label: "Drafts & Approvals" },
];

export function Layout() {
  return (
    <div className="flex h-screen bg-gray-50">
      {/* Sidebar */}
      <aside className="w-56 bg-gray-900 text-white flex flex-col shrink-0">
        <div className="px-5 py-5 border-b border-gray-700">
          <p className="text-xs font-semibold uppercase tracking-widest text-gray-400">AI Deal Creator</p>
          <p className="text-sm font-bold text-white mt-0.5">CLO Workspace</p>
        </div>
        <nav className="flex-1 px-3 py-4 space-y-1">
          {navItems.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors",
                  isActive
                    ? "bg-gray-700 text-white"
                    : "text-gray-400 hover:bg-gray-800 hover:text-white"
                )
              }
            >
              <Icon size={16} />
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="px-5 py-4 border-t border-gray-700">
          <p className="text-xs text-gray-500">Phase 1 — Mock Engine</p>
          <p className="text-xs text-gray-600">localhost:8000</p>
        </div>
      </aside>

      {/* Main */}
      <div className="flex-1 flex flex-col overflow-hidden">
        <header className="bg-white border-b border-gray-200 px-6 py-3 shrink-0">
          <p className="text-xs text-amber-600 font-medium">
            ⚠ All outputs are mock engine data — not for investment or pricing use
          </p>
        </header>
        <main className="flex-1 overflow-y-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
