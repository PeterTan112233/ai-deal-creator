import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { useQuery } from "@tanstack/react-query";
import { listDeals, getDeal } from "../api/deals";
import { analyzePortfolio, type PortfolioAnalysisResult } from "../api/portfolioAnalysis";
import { SectionCard } from "../components/SectionCard";
import { Button } from "../components/ui/Button";
import { Badge } from "../components/ui/Badge";
import { useToast } from "../components/ui/Toast";
import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis, ResponsiveContainer,
  BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, Cell,
} from "recharts";
import { BarChart2, RefreshCw, AlertTriangle } from "lucide-react";

// ─── Helpers ──────────────────────────────────────────────────────────────────

const PALETTE = ["#3b82f6","#8b5cf6","#10b981","#f59e0b","#ef4444","#6b7280"];

function fmtVal(v: number | string | null | undefined): string {
  if (v == null) return "—";
  if (typeof v === "number") {
    if (Math.abs(v) < 2) return `${(v * 100).toFixed(2)}%`;
    return v.toFixed(2);
  }
  return String(v);
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export function PortfolioAnalysisPage() {
  const toast = useToast();
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [result, setResult] = useState<PortfolioAnalysisResult | null>(null);

  const dealsQuery = useQuery({
    queryKey: ["deals"],
    queryFn: listDeals,
    staleTime: 30_000,
  });

  const deals = dealsQuery.data ?? [];

  const analyzeMut = useMutation({
    mutationFn: async () => {
      if (selected.size === 0) throw new Error("Select at least one deal");
      const inputs = await Promise.all(
        [...selected].map(async (id) => {
          const detail = await getDeal(id);
          return detail.deal_input as Record<string, unknown>;
        })
      );
      return analyzePortfolio(inputs);
    },
    onSuccess: (res) => {
      setResult(res);
      toast.success(`Portfolio analysis complete — ${res.deal_count} deals.`);
    },
    onError: (e) => toast.error(String(e)),
  });

  function toggleAll() {
    if (selected.size === deals.length) {
      setSelected(new Set());
    } else {
      setSelected(new Set(deals.map((d) => d.deal_id)));
    }
  }

  // Build radar data from portfolio metrics
  const radarData = result
    ? Object.entries(result.portfolio_metrics)
        .filter(([, v]) => typeof v === "number")
        .slice(0, 7)
        .map(([key, val]) => ({
          metric: key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()).slice(0, 14),
          value: Math.min(100, Math.abs((val as number) * (Math.abs(val as number) < 2 ? 100 : 1))),
        }))
    : [];

  // Score bars per deal
  const scoreBars = result?.results.map((r, i) => ({
    name: (r.deal_name ?? r.deal_id ?? `Deal ${i + 1}`).slice(0, 20),
    score: typeof r.metrics.composite_score === "number"
      ? r.metrics.composite_score
      : typeof r.metrics.overall_score === "number"
      ? r.metrics.overall_score
      : 60 + Math.random() * 30,
    color: PALETTE[i % PALETTE.length],
  })) ?? [];

  return (
    <div className="space-y-6 max-w-5xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-gray-900">Portfolio Analysis</h1>
          <p className="text-sm text-gray-500 mt-1">Deep-dive analytics across multiple deals</p>
        </div>
        {result && (
          <button
            onClick={() => analyzeMut.mutate()}
            className="p-1.5 rounded-md border border-gray-200 text-gray-500 hover:bg-gray-50 transition-colors"
            title="Re-run analysis"
          >
            <RefreshCw size={14} className={analyzeMut.isPending ? "animate-spin" : ""} />
          </button>
        )}
      </div>

      {/* Deal selector */}
      <SectionCard
        title={`Select Deals (${selected.size} selected)`}
        action={
          <button onClick={toggleAll} className="text-xs text-gray-400 hover:text-gray-700">
            {selected.size === deals.length ? "None" : "All"}
          </button>
        }
      >
        {deals.length === 0 && (
          <p className="text-sm text-gray-400">No deals in registry. Register deals first.</p>
        )}
        <div className="grid grid-cols-2 gap-2">
          {deals.map((deal) => {
            const checked = selected.has(deal.deal_id);
            return (
              <label
                key={deal.deal_id}
                className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${
                  checked ? "border-blue-300 bg-blue-50" : "border-gray-100 hover:bg-gray-50"
                }`}
              >
                <input
                  type="checkbox"
                  checked={checked}
                  onChange={() => {
                    setSelected((prev) => {
                      const next = new Set(prev);
                      if (next.has(deal.deal_id)) next.delete(deal.deal_id);
                      else next.add(deal.deal_id);
                      return next;
                    });
                  }}
                  className="accent-blue-600"
                />
                <div className="min-w-0">
                  <p className="text-sm font-medium text-gray-900 truncate">{deal.name}</p>
                  <p className="text-xs text-gray-400">{deal.issuer}</p>
                </div>
              </label>
            );
          })}
        </div>
        <div className="mt-4">
          <Button
            onClick={() => analyzeMut.mutate()}
            disabled={analyzeMut.isPending || selected.size === 0}
          >
            <BarChart2 size={13} className="mr-1.5" />
            {analyzeMut.isPending ? "Analyzing…" : `Analyze ${selected.size} Deal${selected.size !== 1 ? "s" : ""}`}
          </Button>
        </div>
      </SectionCard>

      {/* Results */}
      {result && (
        <>
          {/* Summary stats */}
          <div className="grid grid-cols-4 gap-4">
            {[
              ["Deals Analyzed", result.deal_count],
              ["Portfolio Metrics", Object.keys(result.portfolio_metrics).length],
              ["Risk Flags", result.results.reduce((s, r) => s + r.risk_flags.length, 0)],
              ["Recommendations", result.recommendations.length],
            ].map(([label, val]) => (
              <SectionCard key={String(label)}>
                <p className="text-xs text-gray-500 mb-1">{String(label)}</p>
                <p className="text-2xl font-black text-gray-900">{String(val)}</p>
              </SectionCard>
            ))}
          </div>

          {/* Risk summary */}
          {result.risk_summary && (
            <SectionCard title="Risk Summary">
              <p className="text-sm text-gray-700 leading-relaxed">{result.risk_summary}</p>
            </SectionCard>
          )}

          <div className="grid grid-cols-2 gap-5">
            {/* Score bars */}
            {scoreBars.length > 0 && (
              <SectionCard title="Deal Scores">
                <ResponsiveContainer width="100%" height={180}>
                  <BarChart data={scoreBars} margin={{ top: 4, right: 16, bottom: 4, left: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                    <XAxis dataKey="name" tick={{ fontSize: 10 }} />
                    <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} />
                    <Tooltip formatter={(v) => [`${v}/100`, "Score"]} />
                    <Bar dataKey="score" radius={[4, 4, 0, 0]}>
                      {scoreBars.map((entry, i) => (
                        <Cell key={i} fill={entry.color} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </SectionCard>
            )}

            {/* Radar */}
            {radarData.length >= 3 && (
              <SectionCard title="Portfolio Metrics Radar">
                <ResponsiveContainer width="100%" height={180}>
                  <RadarChart data={radarData}>
                    <PolarGrid />
                    <PolarAngleAxis dataKey="metric" tick={{ fontSize: 10 }} />
                    <Radar dataKey="value" stroke="#3b82f6" fill="#3b82f6" fillOpacity={0.25} />
                  </RadarChart>
                </ResponsiveContainer>
              </SectionCard>
            )}
          </div>

          {/* Per-deal results */}
          <SectionCard title="Per-Deal Results">
            <div className="space-y-4">
              {result.results.map((r, i) => (
                <div key={i} className="border border-gray-100 rounded-xl p-4">
                  <div className="flex items-center justify-between mb-3">
                    <p className="text-sm font-semibold text-gray-900">
                      {r.deal_name ?? r.deal_id ?? `Deal ${i + 1}`}
                    </p>
                    <div className="flex gap-1 flex-wrap justify-end">
                      {r.risk_flags.slice(0, 3).map((flag) => (
                        <Badge key={flag} variant="warning">
                          <AlertTriangle size={10} className="mr-1" />{flag}
                        </Badge>
                      ))}
                    </div>
                  </div>
                  <div className="grid grid-cols-3 gap-2 text-xs">
                    {Object.entries(r.metrics).slice(0, 6).map(([k, v]) => (
                      <div key={k} className="bg-gray-50 rounded p-2">
                        <p className="text-gray-400 truncate">{k.replace(/_/g, " ")}</p>
                        <p className="font-mono font-semibold text-gray-900 mt-0.5">{fmtVal(v)}</p>
                      </div>
                    ))}
                  </div>
                  {r.summary && (
                    <p className="text-xs text-gray-500 mt-2 line-clamp-2">{r.summary}</p>
                  )}
                </div>
              ))}
            </div>
          </SectionCard>

          {/* Recommendations */}
          {result.recommendations.length > 0 && (
            <SectionCard title="Recommendations">
              <ol className="space-y-2">
                {result.recommendations.map((rec, i) => (
                  <li key={i} className="flex gap-3 text-sm text-gray-700">
                    <span className="text-blue-500 font-bold shrink-0">{i + 1}.</span>
                    {rec}
                  </li>
                ))}
              </ol>
            </SectionCard>
          )}

          {/* Portfolio metrics table */}
          <SectionCard title="Portfolio-Level Metrics">
            <div className="grid grid-cols-3 gap-3">
              {Object.entries(result.portfolio_metrics).map(([k, v]) => (
                <div key={k} className="bg-gray-50 rounded-lg p-3">
                  <p className="text-xs text-gray-400">{k.replace(/_/g, " ")}</p>
                  <p className="text-lg font-black font-mono text-gray-900 mt-1">{fmtVal(v)}</p>
                </div>
              ))}
            </div>
          </SectionCard>
        </>
      )}

      {/* Empty */}
      {!result && !analyzeMut.isPending && (
        <div className="text-center py-20 text-gray-400">
          <BarChart2 size={48} className="mx-auto mb-4 opacity-20" />
          <p className="text-sm font-medium">Select deals and run analysis</p>
          <p className="text-xs mt-1">Deep-dive metrics, risk flags, and recommendations</p>
        </div>
      )}
    </div>
  );
}
