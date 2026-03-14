import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { client } from "../api/client";
import { SectionCard } from "../components/SectionCard";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { ScrollText, RefreshCw } from "lucide-react";

// ─── Types ────────────────────────────────────────────────────────────────────

interface AuditEvent {
  event_id: string;
  timestamp: string;
  event_type: string;
  deal_id: string;
  scenario_id: string | null;
  actor: string;
  payload: Record<string, unknown>;
}

interface AuditResponse {
  total: number;
  offset: number;
  limit: number;
  events: AuditEvent[];
}

// ─── Event type badge colours ─────────────────────────────────────────────────

function eventBadge(eventType: string): "success" | "info" | "warning" | "danger" | "default" | "outline" {
  if (eventType.includes("approved") || eventType.includes("completed") || eventType.includes("published"))
    return "success";
  if (eventType.includes("rejected") || eventType.includes("failed") || eventType.includes("error"))
    return "danger";
  if (eventType.includes("requested") || eventType.includes("submitted") || eventType.includes("validation"))
    return "warning";
  if (eventType.includes("created") || eventType.includes("drafted") || eventType.includes("generated"))
    return "info";
  return "default";
}

// ─── Format timestamp ─────────────────────────────────────────────────────────

function fmtTs(iso: string): { date: string; time: string } {
  const d = new Date(iso);
  return {
    date: d.toLocaleDateString([], { month: "short", day: "numeric" }),
    time: d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }),
  };
}

// ─── Event row ────────────────────────────────────────────────────────────────

function EventRow({
  event,
  expanded,
  onToggle,
}: {
  event: AuditEvent;
  expanded: boolean;
  onToggle: () => void;
}) {
  const { date, time } = fmtTs(event.timestamp);

  return (
    <div className="border-b border-gray-50 last:border-0">
      <button
        onClick={onToggle}
        className="w-full flex items-start gap-4 px-4 py-3 hover:bg-gray-50/80 text-left transition-colors"
      >
        {/* Timeline dot */}
        <div className="flex flex-col items-center pt-1 shrink-0">
          <div className="h-2 w-2 rounded-full bg-gray-300 mt-0.5" />
          <div className="w-px flex-1 bg-gray-100 mt-1" />
        </div>

        {/* Timestamp */}
        <div className="w-24 shrink-0 text-right">
          <p className="text-xs font-mono text-gray-500">{time}</p>
          <p className="text-xs text-gray-300">{date}</p>
        </div>

        {/* Event type */}
        <div className="w-52 shrink-0">
          <Badge variant={eventBadge(event.event_type)}>
            {event.event_type}
          </Badge>
        </div>

        {/* Deal + actor */}
        <div className="flex-1 min-w-0">
          <p className="text-xs font-mono text-gray-700 truncate">{event.deal_id}</p>
          <p className="text-xs text-gray-400">{event.actor}</p>
        </div>

        {/* Expand indicator */}
        <span className="text-xs text-gray-300">{expanded ? "▲" : "▼"}</span>
      </button>

      {/* Payload panel */}
      {expanded && (
        <div className="px-4 pb-3 ml-10">
          <pre className="text-xs font-mono bg-gray-50 rounded p-3 text-gray-600 overflow-x-auto max-h-48 border border-gray-100">
            {JSON.stringify(event.payload, null, 2)}
          </pre>
          {event.scenario_id && (
            <p className="text-xs text-gray-400 mt-1">
              scenario: <span className="font-mono">{event.scenario_id}</span>
            </p>
          )}
          <p className="text-xs text-gray-300 mt-0.5 font-mono">{event.event_id}</p>
        </div>
      )}
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

const EVENT_TYPES = [
  "deal.validated",
  "deal.created",
  "scenario.submitted",
  "scenario.completed",
  "health_check.completed",
  "portfolio_scoring.completed",
  "tranche_optimization.completed",
  "benchmark_comparison.completed",
  "draft.generated",
  "approval.requested",
  "approval.granted",
  "approval.rejected",
  "approval.applied",
];

export function AuditLogPage() {
  const [dealFilter, setDealFilter] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const query = useQuery<AuditResponse>({
    queryKey: ["audit-events", dealFilter, typeFilter],
    queryFn: async () => {
      const params: Record<string, string> = { limit: "300" };
      if (dealFilter.trim()) params.deal_id = dealFilter.trim();
      if (typeFilter) params.event_type = typeFilter;
      const { data } = await client.get<AuditResponse>("/audit/events", { params });
      return data;
    },
    refetchInterval: 15_000,
  });

  const events = query.data?.events ?? [];
  const total = query.data?.total ?? 0;

  return (
    <div className="space-y-6 max-w-5xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-gray-900">Audit Log</h1>
          <p className="text-sm text-gray-500 mt-1">
            Governance timeline — every workflow action, newest first
          </p>
        </div>
        <button
          onClick={() => query.refetch()}
          className="p-1.5 rounded-md border border-gray-200 text-gray-500 hover:bg-gray-50 transition-colors"
          title="Refresh"
        >
          <RefreshCw size={14} className={query.isFetching ? "animate-spin" : ""} />
        </button>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3">
        <input
          type="text"
          placeholder="Filter by deal ID…"
          value={dealFilter}
          onChange={(e) => setDealFilter(e.target.value)}
          className="flex-1 max-w-xs text-sm border border-gray-200 rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-gray-900"
        />
        <select
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value)}
          className="text-sm border border-gray-200 rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-gray-900"
        >
          <option value="">All event types</option>
          {EVENT_TYPES.map((t) => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>
        {(dealFilter || typeFilter) && (
          <Button variant="outline" size="sm" onClick={() => { setDealFilter(""); setTypeFilter(""); }}>
            Clear
          </Button>
        )}
        <span className="text-xs text-gray-400">{total} event{total !== 1 ? "s" : ""}</span>
      </div>

      {/* Timeline */}
      <SectionCard title={`Events${events.length < total ? ` (showing ${events.length} of ${total})` : ""}`}>
        {query.isError && (
          <p className="text-sm text-red-600 p-4">
            Failed to load audit log — is the backend running?
          </p>
        )}

        {query.isLoading && (
          <div className="py-8 text-center text-gray-400 text-sm">Loading…</div>
        )}

        {!query.isLoading && events.length === 0 && (
          <div className="text-center py-16 text-gray-400">
            <ScrollText size={40} className="mx-auto mb-3 opacity-20" />
            <p className="text-sm font-medium">No events yet</p>
            <p className="text-xs mt-1">
              Run a health check, scenario, or optimizer to generate audit events
            </p>
          </div>
        )}

        {events.map((evt) => (
          <EventRow
            key={evt.event_id}
            event={evt}
            expanded={expandedId === evt.event_id}
            onToggle={() =>
              setExpandedId((prev) => (prev === evt.event_id ? null : evt.event_id))
            }
          />
        ))}
      </SectionCard>
    </div>
  );
}
