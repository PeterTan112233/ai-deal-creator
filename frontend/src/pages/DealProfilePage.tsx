import { useParams, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { getDeal } from "../api/deals";
import { client } from "../api/client";
import { SectionCard } from "../components/SectionCard";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import {
  Activity, Play, Zap, BarChart3, ArrowLeft,
  Building2, Globe, Layers, Calendar, ChevronRight
} from "lucide-react";

// ─── Helpers ──────────────────────────────────────────────────────────────────

function fmt(n: number | null | undefined): string {
  if (n == null) return "—";
  if (n >= 1e9) return `$${(n / 1e9).toFixed(1)}B`;
  if (n >= 1e6) return `$${(n / 1e6).toFixed(0)}M`;
  return `$${n.toLocaleString()}`;
}

function pct(v: number | null | undefined, dec = 2): string {
  if (v == null) return "—";
  return `${(v * 100).toFixed(dec)}%`;
}

function fmtTs(iso: string) {
  const d = new Date(iso);
  return d.toLocaleDateString([], { month: "short", day: "numeric", year: "numeric" }) +
    " " + d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1) return "just now";
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

// ─── Audit events ─────────────────────────────────────────────────────────────

function eventBadge(eventType: string): "success" | "info" | "warning" | "danger" | "default" {
  if (eventType.includes("approved") || eventType.includes("completed") || eventType.includes("created")) return "success";
  if (eventType.includes("rejected") || eventType.includes("failed")) return "danger";
  if (eventType.includes("requested") || eventType.includes("submitted")) return "warning";
  if (eventType.includes("generated") || eventType.includes("validated")) return "info";
  return "default";
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export function DealProfilePage() {
  const { dealId } = useParams<{ dealId: string }>();
  const navigate = useNavigate();

  const detailQuery = useQuery({
    queryKey: ["deal-detail", dealId],
    queryFn: () => getDeal(dealId!),
    enabled: !!dealId,
  });

  const auditQuery = useQuery({
    queryKey: ["deal-audit", dealId],
    queryFn: async () => {
      const { data } = await client.get(`/audit/events`, { params: { deal_id: dealId, limit: 50 } });
      return data as { total: number; events: Record<string, unknown>[] };
    },
    enabled: !!dealId,
  });

  const detail = detailQuery.data;
  const deal_input = detail?.deal_input as Record<string, unknown> | undefined;
  const collateral = deal_input?.collateral as Record<string, unknown> | undefined;
  const liabilities = (deal_input?.liabilities as Record<string, unknown>[]) ?? [];

  // Last pipeline result
  const lastPipeline = detail?.last_pipeline_result as Record<string, unknown> | null;
  const pipelineStages = lastPipeline?.stages as Record<string, unknown> | undefined;
  const analyticsBase = pipelineStages
    ? ((pipelineStages.analytics as Record<string, unknown>)?.scenarios as Record<string, unknown>[])?.[0]
    : null;
  const baseOutputs = analyticsBase?.outputs as Record<string, unknown> ?? {};

  function goTo(path: string) {
    navigate(path, { state: { dealInput: deal_input } });
  }

  if (detailQuery.isLoading) {
    return (
      <div className="flex items-center justify-center h-64 text-gray-400 text-sm">
        Loading deal…
      </div>
    );
  }

  if (detailQuery.isError || !detail) {
    return (
      <div className="max-w-3xl space-y-4">
        <Button variant="outline" size="sm" onClick={() => navigate("/deals")}>
          <ArrowLeft size={14} className="mr-1" /> Back to Registry
        </Button>
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700 text-sm">
          Deal not found or failed to load.
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-5xl">
      {/* Back + header */}
      <div>
        <button
          onClick={() => navigate("/deals")}
          className="flex items-center gap-1 text-xs text-gray-400 hover:text-gray-700 mb-3 transition-colors"
        >
          <ArrowLeft size={12} /> Deal Registry
        </button>
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-xl font-bold text-gray-900">{detail.name}</h1>
            <div className="flex items-center gap-2 mt-1.5 flex-wrap">
              {detail.asset_class && <Badge variant="info">{detail.asset_class}</Badge>}
              {detail.region && <Badge variant="outline">{detail.region}</Badge>}
              <Badge variant={detail.status === "active" ? "success" : "default"}>{detail.status}</Badge>
              <span className="text-xs text-gray-400">registered {timeAgo(detail.registered_at)}</span>
            </div>
          </div>
          {/* Quick-launch actions */}
          <div className="flex items-center gap-2 flex-wrap">
            <Button size="sm" variant="outline" onClick={() => goTo("/health")}>
              <Activity size={13} className="mr-1" /> Health
            </Button>
            <Button size="sm" variant="outline" onClick={() => goTo("/scenarios")}>
              <Play size={13} className="mr-1" /> Scenarios
            </Button>
            <Button size="sm" variant="outline" onClick={() => goTo("/optimize")}>
              <Zap size={13} className="mr-1" /> Optimize
            </Button>
            <Button size="sm" variant="outline" onClick={() => goTo("/benchmark")}>
              <BarChart3 size={13} className="mr-1" /> Benchmark
            </Button>
            <Button size="sm" onClick={() => navigate(`/pipeline`, { state: { dealInput: deal_input } })}>
              <Zap size={13} className="mr-1" /> Full Pipeline
            </Button>
          </div>
        </div>
      </div>

      {/* Deal info grid */}
      <div className="grid grid-cols-3 gap-4">
        {[
          { icon: Building2, label: "Issuer",     value: detail.issuer },
          { icon: Globe,     label: "Region",     value: detail.region ?? "—" },
          { icon: Layers,    label: "Tranches",   value: String(detail.tranche_count) },
          { icon: Building2, label: "Portfolio",  value: fmt(detail.portfolio_size) },
          { icon: Calendar,  label: "Registered", value: detail.registered_at ? fmtTs(detail.registered_at) : "—" },
          { icon: Activity,  label: "Deal ID",    value: detail.deal_id },
        ].map(({ icon: Icon, label, value }) => (
          <div key={label} className="bg-white border border-gray-100 rounded-xl p-4">
            <div className="flex items-center gap-2 mb-1">
              <Icon size={13} className="text-gray-400" />
              <p className="text-xs text-gray-500">{label}</p>
            </div>
            <p className="text-sm font-semibold text-gray-900 font-mono truncate">{value}</p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-2 gap-5">
        {/* Collateral */}
        <SectionCard title="Collateral">
          {collateral ? (
            <div className="space-y-1.5">
              {[
                ["Portfolio Size", fmt(collateral.portfolio_size as number)],
                ["WAS", pct(collateral.was as number)],
                ["WAL", collateral.wal != null ? `${(collateral.wal as number).toFixed(1)}yr` : "—"],
                ["Diversity Score", collateral.diversity_score != null ? String(collateral.diversity_score) : "—"],
                ["CCC Bucket", pct(collateral.ccc_bucket as number)],
                ["WARF", collateral.warf != null ? String(collateral.warf) : "—"],
              ].map(([label, val]) => (
                <div key={label} className="flex justify-between text-sm">
                  <span className="text-gray-500">{label}</span>
                  <span className="font-mono font-semibold text-gray-900">{val}</span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-gray-400">No collateral data.</p>
          )}
        </SectionCard>

        {/* Tranche stack */}
        <SectionCard title="Tranche Stack">
          {liabilities.length > 0 ? (
            <div className="space-y-2">
              {liabilities.map((t, i) => (
                <div key={i} className="flex items-center gap-3">
                  <div
                    className="h-5 rounded text-xs font-mono font-bold text-white flex items-center justify-center shrink-0"
                    style={{
                      width: `${Math.max(8, ((t.size_pct as number ?? 0) * 100))}%`,
                      background: ["#3b82f6","#8b5cf6","#10b981","#f59e0b","#ef4444","#6b7280"][i % 6],
                      minWidth: "2rem",
                    }}
                  >
                    {pct(t.size_pct as number, 0)}
                  </div>
                  <span className="text-xs font-medium text-gray-700">{String(t.name)}</span>
                  {t.coupon != null && <span className="text-xs text-gray-400 font-mono">{String(t.coupon)}</span>}
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-gray-400">No tranche data.</p>
          )}
        </SectionCard>
      </div>

      {/* Last pipeline result */}
      {lastPipeline && (
        <SectionCard title="Last Pipeline Result">
          <div className="flex items-center justify-between mb-3">
            <p className="text-xs font-mono text-gray-400">{String(lastPipeline.pipeline_id ?? "")}</p>
            <button
              onClick={() => navigate("/pipeline", { state: { dealInput: deal_input } })}
              className="text-xs text-blue-600 hover:underline flex items-center gap-1"
            >
              Re-run pipeline <ChevronRight size={11} />
            </button>
          </div>
          <div className="grid grid-cols-3 gap-3">
            {[
              ["Base IRR", pct(baseOutputs.equity_irr as number)],
              ["OC Cushion", pct(baseOutputs.oc_cushion_aaa as number)],
              ["WAC", pct(baseOutputs.wac as number)],
            ].map(([label, val]) => (
              <div key={label} className="bg-gray-50 rounded-lg p-3 text-center">
                <p className="text-xs text-gray-500 mb-1">{label}</p>
                <p className="text-lg font-black font-mono text-gray-900">{val}</p>
              </div>
            ))}
          </div>
          {lastPipeline.pipeline_summary != null && (
            <p className="text-xs text-gray-500 mt-3 font-mono leading-relaxed line-clamp-3">
              {String(lastPipeline.pipeline_summary)}
            </p>
          )}
        </SectionCard>
      )}

      {/* Audit timeline */}
      <SectionCard
        title={`Audit Events (${auditQuery.data?.total ?? 0} total)`}
        action={
          <button
            onClick={() => navigate(`/audit?deal_id=${dealId}`)}
            className="text-xs text-gray-400 hover:text-gray-700 flex items-center gap-1"
          >
            View all <ChevronRight size={11} />
          </button>
        }
      >
        {auditQuery.isLoading && <p className="text-sm text-gray-400">Loading events…</p>}
        {(auditQuery.data?.events ?? []).length === 0 && !auditQuery.isLoading && (
          <p className="text-sm text-gray-400">No audit events for this deal yet.</p>
        )}
        <div className="space-y-0">
          {(auditQuery.data?.events ?? []).slice(0, 15).map((evt) => {
            const ts = fmtTs(String(evt.timestamp));
            return (
              <div key={String(evt.event_id)} className="flex items-center gap-3 py-2 border-b border-gray-50 last:border-0">
                <span className="text-xs text-gray-300 w-32 shrink-0 font-mono">{ts.split(" ")[1]}</span>
                <Badge variant={eventBadge(String(evt.event_type))}>{String(evt.event_type)}</Badge>
                <span className="text-xs text-gray-500">{String(evt.actor)}</span>
              </div>
            );
          })}
        </div>
      </SectionCard>
    </div>
  );
}
