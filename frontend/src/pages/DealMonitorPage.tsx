import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { listDeals, getDeal, type DealSummary } from "../api/deals";
import { runHealthCheck, type HealthCheckResult } from "../api/health";
import { GradeCircle } from "../components/GradeCircle";
import { KRIBadge } from "../components/KRIBadge";
import { Badge } from "../components/ui/Badge";
import { Activity, Pause, Play, RefreshCw, AlertTriangle, CheckCircle2 } from "lucide-react";

// ─── Types ────────────────────────────────────────────────────────────────────

const INTERVALS = [
  { label: "15s", value: 15_000 },
  { label: "30s", value: 30_000 },
  { label: "60s", value: 60_000 },
] as const;

// ─── Per-deal card ────────────────────────────────────────────────────────────

function MonitorCard({
  deal,
  refetchInterval,
}: {
  deal: DealSummary;
  refetchInterval: number | false;
}) {
  // 1. Fetch full deal detail (cached, rarely changes)
  const detailQuery = useQuery({
    queryKey: ["deal-detail", deal.deal_id],
    queryFn: () => getDeal(deal.deal_id),
    staleTime: 5 * 60_000,
  });

  // 2. Run health check as a query (auto-refreshes via refetchInterval)
  const healthQuery = useQuery({
    queryKey: ["monitor-health", deal.deal_id],
    queryFn: () => runHealthCheck(detailQuery.data!.deal_input),
    enabled: !!detailQuery.data,
    refetchInterval,
    staleTime: 0,
  });

  const result: HealthCheckResult | undefined = healthQuery.data;
  const loading = detailQuery.isLoading || healthQuery.isFetching;
  const errored = detailQuery.isError || healthQuery.isError;

  // Derive overall alert level from KRIs
  const kris = result?.key_risk_indicators ?? [];
  const hasCritical = kris.some((k) => k.status === "critical");
  const hasWarn = kris.some((k) => k.status === "warning");
  const alertLevel = hasCritical ? "critical" : hasWarn ? "warning" : "ok";

  const borderColor =
    alertLevel === "critical"
      ? "border-red-200 shadow-red-50"
      : alertLevel === "warning"
      ? "border-amber-200 shadow-amber-50"
      : "border-gray-100";

  const updatedAt = healthQuery.dataUpdatedAt
    ? new Date(healthQuery.dataUpdatedAt).toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      })
    : null;

  // Pick 3 key KRIs to show
  const keyKris = kris.filter((k) =>
    ["equity_irr", "oc_cushion_aaa", "ccc_bucket"].includes(k.name)
  );

  return (
    <div
      className={`relative bg-white border rounded-xl p-4 shadow-sm transition-all ${borderColor}`}
    >
      {/* Status dot */}
      <div className="absolute top-3 right-3 flex items-center gap-1.5">
        {loading ? (
          <RefreshCw size={12} className="animate-spin text-gray-400" />
        ) : errored ? (
          <span className="h-2 w-2 rounded-full bg-red-400" />
        ) : alertLevel === "critical" ? (
          <span className="h-2 w-2 rounded-full bg-red-500 animate-pulse" />
        ) : alertLevel === "warning" ? (
          <span className="h-2 w-2 rounded-full bg-amber-400 animate-pulse" />
        ) : (
          <span className="h-2 w-2 rounded-full bg-emerald-400" />
        )}
      </div>

      {/* Deal header */}
      <div className="flex items-start gap-3 mb-3">
        <GradeCircle grade={result?.overall_grade ?? "?"} size="md" />
        <div className="flex-1 min-w-0">
          <p className="font-semibold text-gray-900 truncate text-sm">{deal.name}</p>
          <p className="text-xs text-gray-400 truncate">{deal.issuer}</p>
          <div className="flex gap-1 mt-1 flex-wrap">
            {deal.asset_class && <Badge variant="info">{deal.asset_class}</Badge>}
            {deal.region && <Badge variant="outline">{deal.region}</Badge>}
          </div>
        </div>
      </div>

      {/* Score bar */}
      {result && (
        <div className="mb-3">
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs text-gray-500">Score</span>
            <span className="text-xs font-mono font-bold text-gray-900">
              {result.overall_score?.toFixed(1) ?? "—"}/100
            </span>
          </div>
          <div className="h-1.5 bg-gray-100 rounded-full">
            <div
              className={`h-1.5 rounded-full transition-all ${
                (result.overall_score ?? 0) >= 70
                  ? "bg-emerald-500"
                  : (result.overall_score ?? 0) >= 50
                  ? "bg-amber-400"
                  : "bg-red-500"
              }`}
              style={{ width: `${result.overall_score ?? 0}%` }}
            />
          </div>
        </div>
      )}

      {/* KRI badges */}
      {keyKris.length > 0 && (
        <div className="flex flex-wrap gap-1.5 mb-3">
          {keyKris.map((kri) => (
            <div key={kri.name} className="flex items-center gap-1">
              <KRIBadge status={kri.status} />
              <span className="text-xs text-gray-500">
                {kri.label ?? kri.name}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Action items count */}
      {result && result.action_items.length > 0 && (
        <div className="flex items-center gap-1.5 text-xs text-amber-700 bg-amber-50 rounded px-2 py-1 mb-2">
          <AlertTriangle size={11} />
          {result.action_items.length} action item
          {result.action_items.length !== 1 ? "s" : ""}
        </div>
      )}

      {/* Error state */}
      {errored && (
        <p className="text-xs text-red-500 mt-1">
          {detailQuery.isError ? "Failed to load deal" : "Health check failed"}
        </p>
      )}

      {/* Loading skeleton */}
      {!result && !errored && (
        <div className="space-y-2 mt-2">
          <div className="h-2 bg-gray-100 rounded animate-pulse w-3/4" />
          <div className="h-2 bg-gray-100 rounded animate-pulse w-1/2" />
        </div>
      )}

      {/* Last checked */}
      {updatedAt && (
        <p className="text-xs text-gray-300 mt-2 text-right">
          checked {updatedAt}
        </p>
      )}
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export function DealMonitorPage() {
  const [intervalMs, setIntervalMs] = useState<number>(30_000);
  const [paused, setPaused] = useState(false);

  const dealsQuery = useQuery({
    queryKey: ["deals"],
    queryFn: listDeals,
    refetchInterval: paused ? false : intervalMs,
  });

  const deals: DealSummary[] = dealsQuery.data ?? [];
  const refetchInterval = paused ? false : intervalMs;

  // Aggregate status counts (from deal list only — cards handle real statuses)
  const totalDeals = deals.length;

  return (
    <div className="space-y-6 max-w-7xl">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-gray-900">Deal Monitor</h1>
          <p className="text-sm text-gray-500 mt-1">
            Live health dashboard — auto-refreshes every registered deal
          </p>
        </div>

        {/* Controls */}
        <div className="flex items-center gap-3">
          {/* Live indicator */}
          <div className="flex items-center gap-1.5">
            {!paused ? (
              <>
                <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
                <span className="text-xs text-gray-500">Live</span>
              </>
            ) : (
              <>
                <span className="h-2 w-2 rounded-full bg-gray-300" />
                <span className="text-xs text-gray-400">Paused</span>
              </>
            )}
          </div>

          {/* Interval selector */}
          <div className="flex items-center gap-1 bg-gray-100 rounded-md p-0.5">
            {INTERVALS.map(({ label, value }) => (
              <button
                key={label}
                onClick={() => { setIntervalMs(value); setPaused(false); }}
                className={`px-2.5 py-1 rounded text-xs font-medium transition-colors ${
                  intervalMs === value && !paused
                    ? "bg-white shadow text-gray-900"
                    : "text-gray-500 hover:text-gray-700"
                }`}
              >
                {label}
              </button>
            ))}
          </div>

          {/* Pause/Resume */}
          <button
            onClick={() => setPaused((v) => !v)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-gray-200 text-xs text-gray-600 hover:bg-gray-50 transition-colors"
          >
            {paused ? (
              <>
                <Play size={12} /> Resume
              </>
            ) : (
              <>
                <Pause size={12} /> Pause
              </>
            )}
          </button>

          {/* Manual refresh */}
          <button
            onClick={() => dealsQuery.refetch()}
            className="p-1.5 rounded-md border border-gray-200 text-gray-500 hover:bg-gray-50 transition-colors"
            title="Refresh now"
          >
            <RefreshCw size={14} className={dealsQuery.isFetching ? "animate-spin" : ""} />
          </button>
        </div>
      </div>

      {/* Backend error */}
      {dealsQuery.isError && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700 text-sm">
          Failed to reach backend — is the server running at localhost:8000?
        </div>
      )}

      {/* Empty state */}
      {!dealsQuery.isLoading && deals.length === 0 && (
        <div className="text-center py-20 text-gray-400">
          <Activity size={48} className="mx-auto mb-4 opacity-20" />
          <p className="text-sm font-medium">No deals registered</p>
          <p className="text-xs mt-1">
            Go to <span className="font-semibold text-gray-600">Deal Registry</span> to add deals first
          </p>
        </div>
      )}

      {/* Deal grid */}
      {deals.length > 0 && (
        <>
          {/* Summary bar */}
          <div className="flex items-center gap-6 text-sm">
            <span className="flex items-center gap-1.5 text-gray-600">
              <Activity size={14} />
              <span className="font-semibold">{totalDeals}</span> deals monitored
            </span>
            <span className="text-gray-300">·</span>
            <span className="flex items-center gap-1 text-gray-500 text-xs">
              Refresh every {INTERVALS.find((i) => i.value === intervalMs)?.label ?? "—"}
              {paused && " (paused)"}
            </span>
          </div>

          <div className="grid grid-cols-3 gap-4">
            {deals.map((deal) => (
              <MonitorCard
                key={deal.deal_id}
                deal={deal}
                refetchInterval={refetchInterval as number | false}
              />
            ))}
          </div>

          {/* Legend */}
          <div className="flex items-center gap-4 text-xs text-gray-400">
            <span className="flex items-center gap-1.5">
              <CheckCircle2 size={12} className="text-emerald-500" /> All KRIs OK
            </span>
            <span className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-amber-400" /> One or more warnings
            </span>
            <span className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-red-500" /> Critical KRI breach
            </span>
          </div>
        </>
      )}
    </div>
  );
}
