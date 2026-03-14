import { useQuery } from "@tanstack/react-query";
import { client } from "../api/client";
import { SectionCard } from "../components/SectionCard";
import { Badge } from "../components/ui/Badge";
import {
  LineChart, Line, XAxis, YAxis, Tooltip,
  ResponsiveContainer, CartesianGrid,
  BarChart, Bar, Cell,
} from "recharts";
import { TrendingUp, RefreshCw } from "lucide-react";

// ─── Types ────────────────────────────────────────────────────────────────────

interface AuditEvent {
  event_id: string;
  timestamp: string;
  event_type: string;
  deal_id: string;
  payload: Record<string, unknown>;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

const GRADE_COLORS: Record<string, string> = {
  A: "#10b981", B: "#3b82f6", C: "#f59e0b", D: "#f97316", F: "#ef4444",
};

function bucketHour(iso: string): string {
  const d = new Date(iso);
  d.setMinutes(0, 0, 0);
  return d.toISOString().slice(0, 13) + ":00";
}

function fmtHour(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) +
    " " + d.toLocaleDateString([], { month: "short", day: "numeric" });
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export function PortfolioTrendPage() {
  const query = useQuery({
    queryKey: ["audit-trend"],
    queryFn: async () => {
      const { data } = await client.get("/audit/events", { params: { limit: 500 } });
      return data as { total: number; events: AuditEvent[] };
    },
    refetchInterval: 30_000,
  });

  const events = query.data?.events ?? [];

  // ── 1. Score trend: events with payload.overall_score ─────────────────────
  const scoreEvents = events
    .filter((e) => e.payload?.overall_score != null)
    .map((e) => ({
      ts: e.timestamp,
      hour: bucketHour(e.timestamp),
      score: e.payload.overall_score as number,
      grade: e.payload.overall_grade as string ?? "?",
      deal_id: e.deal_id,
    }))
    .sort((a, b) => a.ts.localeCompare(b.ts));

  // Group by hour → avg score
  const hourMap = new Map<string, { total: number; count: number }>();
  scoreEvents.forEach(({ hour, score }) => {
    const existing = hourMap.get(hour) ?? { total: 0, count: 0 };
    hourMap.set(hour, { total: existing.total + score, count: existing.count + 1 });
  });
  const scoreTrend = Array.from(hourMap.entries())
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([hour, { total, count }]) => ({
      hour,
      label: fmtHour(hour),
      avg_score: parseFloat((total / count).toFixed(1)),
      count,
    }));

  // ── 2. Grade distribution: from score events ──────────────────────────────
  const gradeCounts: Record<string, number> = {};
  scoreEvents.forEach(({ grade }) => {
    const g = grade?.[0] ?? "?";
    gradeCounts[g] = (gradeCounts[g] ?? 0) + 1;
  });
  const gradeDist = Object.entries(gradeCounts)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([grade, count]) => ({ grade, count }));

  // ── 3. Event type distribution ─────────────────────────────────────────────
  const typeCounts: Record<string, number> = {};
  events.forEach((e) => {
    typeCounts[e.event_type] = (typeCounts[e.event_type] ?? 0) + 1;
  });
  const topTypes = Object.entries(typeCounts)
    .sort(([, a], [, b]) => b - a)
    .slice(0, 8)
    .map(([type, count]) => ({ type, count }));

  // ── 4. Activity by deal ───────────────────────────────────────────────────
  const dealCounts: Record<string, number> = {};
  events.forEach((e) => {
    dealCounts[e.deal_id] = (dealCounts[e.deal_id] ?? 0) + 1;
  });
  const topDeals = Object.entries(dealCounts)
    .sort(([, a], [, b]) => b - a)
    .slice(0, 6)
    .map(([deal_id, count]) => ({ deal_id, count }));

  const totalEvents = query.data?.total ?? 0;
  const uniqueDeals = Object.keys(dealCounts).length;

  return (
    <div className="space-y-6 max-w-5xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-gray-900">Portfolio Trend</h1>
          <p className="text-sm text-gray-500 mt-1">
            Scoring history and activity patterns derived from the audit log
          </p>
        </div>
        <button
          onClick={() => query.refetch()}
          className="p-1.5 rounded-md border border-gray-200 text-gray-500 hover:bg-gray-50 transition-colors"
        >
          <RefreshCw size={14} className={query.isFetching ? "animate-spin" : ""} />
        </button>
      </div>

      {/* Summary stats */}
      <div className="grid grid-cols-4 gap-4">
        {[
          ["Total Events", totalEvents],
          ["Unique Deals", uniqueDeals],
          ["Scored Runs", scoreEvents.length],
          ["Avg Score", scoreEvents.length > 0
            ? (scoreEvents.reduce((s, e) => s + e.score, 0) / scoreEvents.length).toFixed(1)
            : "—"],
        ].map(([label, val]) => (
          <SectionCard key={String(label)}>
            <p className="text-xs text-gray-500 mb-1">{String(label)}</p>
            <p className="text-2xl font-black text-gray-900">{String(val)}</p>
          </SectionCard>
        ))}
      </div>

      {/* Score trend chart */}
      {scoreTrend.length > 1 ? (
        <SectionCard title="Avg Portfolio Score Over Time">
          <p className="text-xs text-gray-400 mb-3">Hourly average of overall_score across all health check and scoring runs</p>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={scoreTrend} margin={{ top: 4, right: 20, bottom: 4, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="label" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
              <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v) => [`${v}/100`, "Avg Score"]} />
              <Line type="monotone" dataKey="avg_score" stroke="#3b82f6" strokeWidth={2} dot={{ r: 3 }} />
            </LineChart>
          </ResponsiveContainer>
        </SectionCard>
      ) : scoreEvents.length > 0 ? (
        <SectionCard title="Score History">
          <p className="text-xs text-gray-400 mb-3">Individual run scores (not enough data for trend — need runs across multiple hours)</p>
          <div className="flex flex-wrap gap-2">
            {scoreEvents.slice(-20).map((e, i) => (
              <div key={i} className="bg-gray-50 rounded px-3 py-2 text-center">
                <p className="text-xs text-gray-400 font-mono">{e.deal_id.slice(0, 12)}</p>
                <p className="text-lg font-black text-gray-900">{e.score.toFixed(0)}</p>
                <p className="text-xs text-gray-400">{e.grade}</p>
              </div>
            ))}
          </div>
        </SectionCard>
      ) : null}

      <div className="grid grid-cols-2 gap-5">
        {/* Grade distribution */}
        {gradeDist.length > 0 && (
          <SectionCard title="Grade Distribution">
            <ResponsiveContainer width="100%" height={160}>
              <BarChart data={gradeDist} layout="vertical" margin={{ top: 0, right: 16, bottom: 0, left: 20 }}>
                <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11 }} />
                <YAxis type="category" dataKey="grade" tick={{ fontSize: 13, fontWeight: 600 }} />
                <Tooltip />
                <Bar dataKey="count" radius={[0, 4, 4, 0]}>
                  {gradeDist.map((entry) => (
                    <Cell key={entry.grade} fill={GRADE_COLORS[entry.grade] ?? "#6b7280"} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </SectionCard>
        )}

        {/* Top event types */}
        {topTypes.length > 0 && (
          <SectionCard title="Top Event Types">
            <div className="space-y-2">
              {topTypes.map(({ type, count }) => {
                const maxCount = topTypes[0].count;
                return (
                  <div key={type}>
                    <div className="flex justify-between text-xs mb-0.5">
                      <span className="text-gray-600 font-mono truncate max-w-48">{type}</span>
                      <span className="text-gray-500 font-semibold shrink-0 ml-2">{count}</span>
                    </div>
                    <div className="h-1.5 bg-gray-100 rounded-full">
                      <div
                        className="h-1.5 bg-blue-400 rounded-full"
                        style={{ width: `${(count / maxCount) * 100}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </SectionCard>
        )}
      </div>

      {/* Activity by deal */}
      {topDeals.length > 0 && (
        <SectionCard title="Most Active Deals">
          <div className="grid grid-cols-3 gap-3">
            {topDeals.map(({ deal_id, count }, i) => (
              <div key={deal_id} className="bg-gray-50 rounded-lg p-3">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-xs text-gray-400 font-mono">#{i + 1}</span>
                  {i === 0 && <Badge variant="warning">most active</Badge>}
                </div>
                <p className="text-xs font-mono text-gray-700 truncate">{deal_id}</p>
                <p className="text-xl font-black text-gray-900 mt-1">{count}</p>
                <p className="text-xs text-gray-400">events</p>
              </div>
            ))}
          </div>
        </SectionCard>
      )}

      {/* Empty state */}
      {events.length === 0 && !query.isLoading && (
        <div className="text-center py-20 text-gray-400">
          <TrendingUp size={48} className="mx-auto mb-4 opacity-20" />
          <p className="text-sm font-medium">No audit data yet</p>
          <p className="text-xs mt-1">Run health checks, scenarios, or the optimizer to generate trend data</p>
        </div>
      )}
    </div>
  );
}
