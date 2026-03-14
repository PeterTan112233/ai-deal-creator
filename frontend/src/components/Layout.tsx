import { useState, useEffect } from "react";
import { NavLink, Outlet } from "react-router-dom";
import {
  Activity, BarChart2, Play, Bell, Database, FileCheck,
  GitCompare, TrendingUp, Grid3x3, Zap, MonitorCheck,
  BarChart3, ScrollText, Layers, Search,
} from "lucide-react";
import { cn } from "../lib/utils";
import { CommandPalette } from "./CommandPalette";

// ─── Nav sections ─────────────────────────────────────────────────────────────

const NAV_SECTIONS = [
  {
    label: "Registry",
    items: [
      { to: "/deals",       icon: Database,     label: "Deal Registry" },
      { to: "/monitor",     icon: MonitorCheck, label: "Live Monitor"  },
    ],
  },
  {
    label: "Analysis",
    items: [
      { to: "/health",       icon: Activity,  label: "Deal Health"    },
      { to: "/bulk-health",  icon: Layers,    label: "Bulk Health"    },
      { to: "/portfolio",    icon: BarChart2, label: "Portfolio"      },
      { to: "/trend",        icon: TrendingUp,label: "Trend"          },
      { to: "/stress-matrix",icon: Grid3x3,   label: "Stress Matrix"  },
      { to: "/pipeline",     icon: Zap,       label: "Full Pipeline"  },
    ],
  },
  {
    label: "Tools",
    items: [
      { to: "/optimize",    icon: Zap,       label: "Optimizer"   },
      { to: "/benchmark",   icon: BarChart3, label: "Benchmark"   },
      { to: "/scenarios",   icon: Play,      label: "Scenarios"   },
      { to: "/compare",     icon: GitCompare,label: "Comparison"  },
      { to: "/sensitivity", icon: TrendingUp,label: "Sensitivity" },
    ],
  },
  {
    label: "Governance",
    items: [
      { to: "/watchlist",   icon: Bell,       label: "Watchlist"  },
      { to: "/drafts",      icon: FileCheck,  label: "Drafts"     },
      { to: "/audit",       icon: ScrollText, label: "Audit Log"  },
    ],
  },
];

// ─── Layout ───────────────────────────────────────────────────────────────────

export function Layout() {
  const [paletteOpen, setPaletteOpen] = useState(false);

  // Global ⌘K / Ctrl+K shortcut
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setPaletteOpen((v) => !v);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <div className="flex h-screen bg-gray-50">
      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} />

      {/* Sidebar */}
      <aside className="w-52 bg-gray-900 text-white flex flex-col shrink-0 overflow-y-auto">
        {/* Brand */}
        <div className="px-4 py-4 border-b border-gray-700 shrink-0">
          <p className="text-xs font-semibold uppercase tracking-widest text-gray-400">AI Deal Creator</p>
          <p className="text-sm font-bold text-white mt-0.5">CLO Workspace</p>
        </div>

        {/* ⌘K search button */}
        <button
          onClick={() => setPaletteOpen(true)}
          className="mx-3 mt-3 flex items-center gap-2 px-3 py-2 rounded-md bg-gray-800 text-gray-400 hover:text-white hover:bg-gray-700 transition-colors text-xs"
        >
          <Search size={12} />
          <span className="flex-1 text-left">Search…</span>
          <span className="border border-gray-600 rounded px-1 text-gray-500 text-xs">⌘K</span>
        </button>

        {/* Nav sections */}
        <nav className="flex-1 px-3 py-3 space-y-4">
          {NAV_SECTIONS.map(({ label, items }) => (
            <div key={label}>
              <p className="text-xs font-semibold uppercase tracking-wider text-gray-500 px-2 mb-1">
                {label}
              </p>
              <div className="space-y-0.5">
                {items.map(({ to, icon: Icon, label: itemLabel }) => (
                  <NavLink
                    key={to}
                    to={to}
                    className={({ isActive }) =>
                      cn(
                        "flex items-center gap-2.5 px-2.5 py-1.5 rounded-md text-xs font-medium transition-colors",
                        isActive
                          ? "bg-gray-700 text-white"
                          : "text-gray-400 hover:bg-gray-800 hover:text-white"
                      )
                    }
                  >
                    <Icon size={13} />
                    {itemLabel}
                  </NavLink>
                ))}
              </div>
            </div>
          ))}
        </nav>

        {/* Footer */}
        <div className="px-4 py-3 border-t border-gray-700 shrink-0">
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
