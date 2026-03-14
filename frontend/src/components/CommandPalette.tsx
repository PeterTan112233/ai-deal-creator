import { useState, useEffect, useRef, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { listDeals } from "../api/deals";
import {
  Database, MonitorCheck, Activity, Layers, BarChart2, Grid3x3,
  Zap, BarChart3, Play, GitCompare, TrendingUp, Bell, FileCheck,
  ScrollText, Search, ChevronRight, ShieldCheck, Settings,
} from "lucide-react";

// ─── All navigable items ──────────────────────────────────────────────────────

const PAGES = [
  { label: "Deal Registry",       path: "/deals",        icon: Database,     group: "Registry" },
  { label: "Live Monitor",        path: "/monitor",      icon: MonitorCheck, group: "Registry" },
  { label: "Deal Health Check",   path: "/health",       icon: Activity,     group: "Analysis" },
  { label: "Bulk Health Check",   path: "/bulk-health",  icon: Layers,       group: "Analysis" },
  { label: "Portfolio Scoring",   path: "/portfolio",    icon: BarChart2,    group: "Analysis" },
  { label: "Portfolio Trend",     path: "/trend",        icon: TrendingUp,   group: "Analysis" },
  { label: "Stress Matrix",       path: "/stress-matrix",icon: Grid3x3,      group: "Analysis" },
  { label: "Full Pipeline",       path: "/pipeline",     icon: Zap,          group: "Analysis" },
  { label: "Optimizer",           path: "/optimize",     icon: Zap,          group: "Tools" },
  { label: "Benchmark",           path: "/benchmark",    icon: BarChart3,    group: "Tools" },
  { label: "Scenario Runner",     path: "/scenarios",    icon: Play,         group: "Tools" },
  { label: "Comparison",          path: "/compare",      icon: GitCompare,   group: "Tools" },
  { label: "Sensitivity",         path: "/sensitivity",  icon: TrendingUp,   group: "Tools" },
  { label: "Portfolio Analysis",  path: "/portfolio-analyze", icon: BarChart2,    group: "Analysis" },
  { label: "Template Suite",      path: "/template-suite",    icon: Play,         group: "Tools" },
  { label: "KRI Comparison",      path: "/kri-compare",       icon: GitCompare,   group: "Tools" },
  { label: "Watchlist",           path: "/watchlist",    icon: Bell,         group: "Governance" },
  { label: "Drafts & Approvals",  path: "/drafts",       icon: FileCheck,    group: "Governance" },
  { label: "Approvals",           path: "/approvals",    icon: ShieldCheck,  group: "Governance" },
  { label: "Publish Gate",        path: "/publish-gate", icon: ShieldCheck,  group: "Governance" },
  { label: "Audit Log",           path: "/audit",        icon: ScrollText,   group: "Governance" },
  { label: "Settings",            path: "/settings",     icon: Settings,     group: "Governance" },
];

// ─── CommandPalette ───────────────────────────────────────────────────────────

interface Props {
  open: boolean;
  onClose: () => void;
}

export function CommandPalette({ open, onClose }: Props) {
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [cursor, setCursor] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  const dealsQuery = useQuery({
    queryKey: ["deals"],
    queryFn: listDeals,
    enabled: open,
    staleTime: 30_000,
  });

  // Build combined results
  const dealItems = (dealsQuery.data ?? []).map((d) => ({
    label: d.name,
    sub: d.issuer,
    path: `/deals/${d.deal_id}`,
    icon: Database,
    group: "Deals",
  }));

  const q = query.toLowerCase().trim();
  const filtered = [
    ...PAGES.filter((p) => !q || p.label.toLowerCase().includes(q) || p.group.toLowerCase().includes(q)),
    ...dealItems.filter((d) => !q || d.label.toLowerCase().includes(q) || (d.sub ?? "").toLowerCase().includes(q)),
  ];

  // Group for display
  const grouped = filtered.reduce<Record<string, typeof filtered>>((acc, item) => {
    const g = item.group ?? "Other";
    if (!acc[g]) acc[g] = [];
    acc[g].push(item);
    return acc;
  }, {});

  // Flat list for keyboard nav
  const flat = filtered;
  const safeCursor = Math.min(cursor, flat.length - 1);

  useEffect(() => {
    if (open) {
      setQuery("");
      setCursor(0);
      setTimeout(() => inputRef.current?.focus(), 30);
    }
  }, [open]);

  useEffect(() => { setCursor(0); }, [query]);

  const select = useCallback((path: string) => {
    navigate(path);
    onClose();
  }, [navigate, onClose]);

  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "ArrowDown") { e.preventDefault(); setCursor((c) => Math.min(c + 1, flat.length - 1)); }
      if (e.key === "ArrowUp")   { e.preventDefault(); setCursor((c) => Math.max(c - 1, 0)); }
      if (e.key === "Enter" && flat[safeCursor]) { select(flat[safeCursor].path); }
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, flat, safeCursor, select, onClose]);

  if (!open) return null;

  let flatIdx = 0;

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-24 px-4">
      {/* Backdrop */}
      <div className="fixed inset-0 bg-black/40" onClick={onClose} />

      {/* Panel */}
      <div className="relative w-full max-w-xl bg-white rounded-2xl shadow-2xl border border-gray-100 overflow-hidden">
        {/* Search input */}
        <div className="flex items-center gap-3 px-4 py-3 border-b border-gray-100">
          <Search size={16} className="text-gray-400 shrink-0" />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search pages or deals…"
            className="flex-1 text-sm bg-transparent outline-none text-gray-900 placeholder-gray-400"
          />
          <kbd className="text-xs text-gray-300 border border-gray-200 rounded px-1.5 py-0.5">esc</kbd>
        </div>

        {/* Results */}
        <div className="max-h-96 overflow-y-auto pb-2">
          {flat.length === 0 && (
            <p className="text-sm text-gray-400 text-center py-8">No results</p>
          )}
          {Object.entries(grouped).map(([group, items]) => (
            <div key={group}>
              <p className="text-xs text-gray-400 uppercase font-semibold tracking-wide px-4 pt-3 pb-1">
                {group}
              </p>
              {items.map((item) => {
                const idx = flatIdx++;
                const active = idx === safeCursor;
                const Icon = item.icon;
                return (
                  <button
                    key={item.path}
                    onClick={() => select(item.path)}
                    onMouseEnter={() => setCursor(idx)}
                    className={`w-full flex items-center gap-3 px-4 py-2.5 text-left transition-colors ${
                      active ? "bg-blue-50 text-blue-700" : "text-gray-700 hover:bg-gray-50"
                    }`}
                  >
                    <Icon size={15} className={active ? "text-blue-500" : "text-gray-400"} />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate">{item.label}</p>
                      {"sub" in item && !!item.sub && (
                        <p className="text-xs text-gray-400 truncate">{String(item.sub)}</p>
                      )}
                    </div>
                    {active && <ChevronRight size={13} className="text-blue-400 shrink-0" />}
                  </button>
                );
              })}
            </div>
          ))}
        </div>

        {/* Footer hint */}
        <div className="border-t border-gray-100 px-4 py-2 flex gap-4 text-xs text-gray-300">
          <span><kbd className="border border-gray-200 rounded px-1">↑↓</kbd> navigate</span>
          <span><kbd className="border border-gray-200 rounded px-1">↵</kbd> open</span>
          <span><kbd className="border border-gray-200 rounded px-1">esc</kbd> close</span>
        </div>
      </div>
    </div>
  );
}
