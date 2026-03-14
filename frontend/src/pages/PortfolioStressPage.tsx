import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { listDeals, getDeal } from "../api/deals";
import { getTemplates } from "../api/templateSuite";
import { client } from "../api/client";
import { SectionCard } from "../components/SectionCard";
import { Button } from "../components/ui/Button";
import { Badge } from "../components/ui/Badge";
import { useToast } from "../components/ui/Toast";
import { ExportMenu } from "../components/ui/ExportMenu";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid,
  ResponsiveContainer, Cell,
} from "recharts";
import { ShieldAlert, TrendingDown, TrendingUp } from "lucide-react";

// ─── Types ────────────────────────────────────────────────────────────────────

interface DealStressResult {
  deal_id?: string;
  deal_name?: string;
  scenario_results: {
    template_id: string;
    scenario_name: string;
    scenario_type: string;
    outputs: Record<string, unknown>;
    status: string;
  }[];
  worst_case_irr?: number;
  best_case_irr?: number;
  vulnerability_score?: number;
}

interface PortfolioStressResult {
  stress_id: string;
  deal_count: number;
  scenario_count: number;
  results: DealStressResult[];
  portfolio_vulnerability: string;
  most_vulnerable: string[];
  least_vulnerable: string[];
  _mock?: string;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

const STRESS_COLORS = ["#ef4444", "#f97316", "#f59e0b", "#10b981", "#3b82f6"];

function pct(v: unknown, dec = 2): string {
  if (v == null) return "—";
  const n = Number(v);
  return isNaN(n) ? "—" : `${(n * 100).toFixed(dec)}%`;
}

function vulnColor(score: number | undefined): string {
  if (score == null) return "#6b7280";
  if (score >= 80) return "#ef4444";
  if (score >= 60) return "#f97316";
  if (score >= 40) return "#f59e0b";
  return "#10b981";
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export function PortfolioStressPage() {
  const toast = useToast();
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [selectedTemplates, setSelectedTemplates] = useState<Set<string>>(new Set());
  const [result, setResult] = useState<PortfolioStressResult | null>(null);

  const dealsQuery = useQuery({ queryKey: ["deals"], queryFn: listDeals, staleTime: 30_000 });
  const templatesQuery = useQuery({ queryKey: ["templates"], queryFn: getTemplates, staleTime: 300_000 });

  const deals = dealsQuery.data ?? [];
  const templates = (templatesQuery.data?.templates ?? []).filter((t) => t.scenario_type !== "base");

  function toggleDeal(id: string) {
    setSelected((p) => { const n = new Set(p); n.has(id) ? n.delete(id) : n.add(id); return n; });
  }
  function toggleTemplate(id: string) {
    setSelectedTemplates((p) => { const n = new Set(p); n.has(id) ? n.delete(id) : n.add(id); return n; });
  }

  const stressMut = useMutation({
    mutationFn: async () => {
      if (selected.size === 0) throw new Error("Select at least one deal");
      const inputs = await Promise.all([...selected].map(async (id) => {
        const d = await getDeal(id);
        return d.deal_input as Record<string, unknown>;
      }));
      const { data } = await client.post("/portfolio/stress-test", {
        deal_inputs: inputs,
        template_ids: selectedTemplates.size > 0 ? [...selectedTemplates] : null,
        scenario_type: "stress",
      });
      return data as PortfolioStressResult;
    },
    onSuccess: (res) => {
      setResult(res);
      toast.success(`Stress test complete — ${res.deal_count} deals × ${res.scenario_count} scenarios.`);
    },
    onError: (e) => toast.error(String(e)),
  });

  // Vulnerability bar chart data
  const vulnData = result?.results.map((r) => ({
    name: (r.deal_name ?? r.deal_id ?? "?").slice(0, 16),
    score: r.vulnerability_score ?? 0,
    worst_irr: r.worst_case_irr,
  })).sort((a, b) => b.score - a.score) ?? [];

  // CSV rows
  const csvRows = result?.results.map((r) => ({
    deal: r.deal_name ?? r.deal_id,
    vulnerability_score: r.vulnerability_score,
    worst_case_irr: r.worst_case_irr,
    best_case_irr: r.best_case_irr,
    scenarios_run: r.scenario_results.length,
  })) ?? [];

  return (
    <div className="space-y-6 max-w-5xl">
      <div>
        <h1 className="text-xl font-bold text-gray-900">Portfolio Stress Test</h1>
        <p className="text-sm text-gray-500 mt-1">
          Run stress scenarios across multiple deals and rank by vulnerability
        </p>
      </div>

      {/* Deal selector */}
      <SectionCard
        title={`Deals (${selected.size} selected)`}
        action={
          <button
            onClick={() => setSelected(selected.size === deals.length ? new Set() : new Set(deals.map(d => d.deal_id)))}
            className="text-xs text-gray-400 hover:text-gray-700"
          >
            {selected.size === deals.length ? "None" : "All"}
          </button>
        }
      >
        {deals.length === 0 && <p className="text-sm text-gray-400">No deals registered.</p>}
        <div className="grid grid-cols-2 gap-2">
          {deals.map((d) => (
            <label key={d.deal_id}
              className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${
                selected.has(d.deal_id) ? "border-blue-300 bg-blue-50" : "border-gray-100 hover:bg-gray-50"
              }`}
            >
              <input type="checkbox" checked={selected.has(d.deal_id)}
                onChange={() => toggleDeal(d.deal_id)} className="accent-blue-600" />
              <div className="min-w-0">
                <p className="text-sm font-medium text-gray-900 truncate">{d.name}</p>
                <p className="text-xs text-gray-400">{d.issuer}</p>
              </div>
            </label>
          ))}
        </div>
      </SectionCard>

      {/* Template selector */}
      <SectionCard
        title={`Stress Templates (${selectedTemplates.size === 0 ? "all stress" : selectedTemplates.size} selected)`}
      >
        <div className="flex flex-wrap gap-2">
          {templates.map((t) => {
            const active = selectedTemplates.size === 0 || selectedTemplates.has(t.template_id);
            return (
              <button
                key={t.template_id}
                onClick={() => {
                  if (selectedTemplates.size === 0) {
                    const all = new Set(templates.map(x => x.template_id));
                    all.delete(t.template_id);
                    setSelectedTemplates(all);
                  } else toggleTemplate(t.template_id);
                }}
                className={`px-3 py-1.5 rounded-lg border text-xs font-medium transition-colors ${
                  active
                    ? "border-amber-300 bg-amber-50 text-amber-800"
                    : "border-gray-200 text-gray-400 hover:border-gray-300"
                }`}
              >
                {t.name}
              </button>
            );
          })}
        </div>
        <div className="mt-4">
          <Button
            onClick={() => stressMut.mutate()}
            disabled={stressMut.isPending || selected.size === 0}
          >
            <ShieldAlert size={13} className="mr-1.5" />
            {stressMut.isPending
              ? "Running stress tests…"
              : `Run Stress Test (${selected.size} deal${selected.size !== 1 ? "s" : ""})`}
          </Button>
        </div>
      </SectionCard>

      {/* Results */}
      {result && (
        <>
          {/* Summary */}
          <div className="grid grid-cols-4 gap-4">
            {[
              ["Deals", result.deal_count],
              ["Scenarios/Deal", result.scenario_count],
              ["Most Vulnerable", result.most_vulnerable[0]?.slice(0, 18) ?? "—"],
              ["Least Vulnerable", result.least_vulnerable[0]?.slice(0, 18) ?? "—"],
            ].map(([label, val]) => (
              <SectionCard key={String(label)}>
                <p className="text-xs text-gray-500 mb-1">{String(label)}</p>
                <p className="text-lg font-black text-gray-900 truncate">{String(val)}</p>
              </SectionCard>
            ))}
          </div>

          {/* Portfolio vulnerability summary */}
          {result.portfolio_vulnerability && (
            <SectionCard title="Portfolio Assessment">
              <p className="text-sm text-gray-700 leading-relaxed">{result.portfolio_vulnerability}</p>
            </SectionCard>
          )}

          {/* Vulnerability bar chart */}
          {vulnData.length > 0 && (
            <SectionCard title="Vulnerability Ranking">
              <p className="text-xs text-gray-400 mb-3">Higher score = more vulnerable to stress</p>
              <ResponsiveContainer width="100%" height={180}>
                <BarChart data={vulnData} margin={{ top: 4, right: 16, bottom: 40, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis dataKey="name" tick={{ fontSize: 10 }} angle={-20} textAnchor="end" interval={0} />
                  <YAxis domain={[0, 100]} tick={{ fontSize: 11 }} tickFormatter={(v) => `${v}`} />
                  <Tooltip formatter={(v) => [`${v}`, "Vulnerability"]} />
                  <Bar dataKey="score" radius={[4, 4, 0, 0]}>
                    {vulnData.map((entry, i) => (
                      <Cell key={i} fill={vulnColor(entry.score)} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
              <div className="flex items-center gap-4 mt-2">
                {[["High (80+)", "#ef4444"], ["Med-High (60-79)", "#f97316"], ["Medium (40-59)", "#f59e0b"], ["Low (<40)", "#10b981"]].map(([label, color]) => (
                  <div key={label} className="flex items-center gap-1.5 text-xs text-gray-500">
                    <div className="w-2.5 h-2.5 rounded-sm" style={{ background: color }} />
                    {label}
                  </div>
                ))}
              </div>
            </SectionCard>
          )}

          {/* Per-deal breakdown */}
          <SectionCard
            title="Per-Deal Results"
            action={<ExportMenu label="portfolio-stress" data={result} csvRows={csvRows} />}
          >
            <div className="space-y-3">
              {result.results
                .sort((a, b) => (b.vulnerability_score ?? 0) - (a.vulnerability_score ?? 0))
                .map((r, i) => (
                  <div key={i} className="border border-gray-100 rounded-xl p-4">
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-gray-400 font-mono">#{i + 1}</span>
                        <p className="text-sm font-semibold text-gray-900">
                          {r.deal_name ?? r.deal_id ?? `Deal ${i + 1}`}
                        </p>
                      </div>
                      <div className="flex items-center gap-3">
                        {r.vulnerability_score != null && (
                          <div className="flex items-center gap-1.5">
                            <div className="w-2 h-2 rounded-full" style={{ background: vulnColor(r.vulnerability_score) }} />
                            <span className="text-xs font-semibold text-gray-600">
                              Vuln: {r.vulnerability_score.toFixed(0)}
                            </span>
                          </div>
                        )}
                        {r.worst_case_irr != null && (
                          <div className="flex items-center gap-1 text-xs text-red-600">
                            <TrendingDown size={12} /> Worst {pct(r.worst_case_irr)}
                          </div>
                        )}
                        {r.best_case_irr != null && (
                          <div className="flex items-center gap-1 text-xs text-green-600">
                            <TrendingUp size={12} /> Best {pct(r.best_case_irr)}
                          </div>
                        )}
                      </div>
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                      {r.scenario_results.slice(0, 6).map((s) => (
                        <div key={s.template_id}
                          className="text-xs px-2 py-1 rounded bg-gray-50 border border-gray-100 font-mono"
                        >
                          <span className="text-gray-400">{s.scenario_name.slice(0, 12)}: </span>
                          <span className="font-semibold text-gray-700">
                            {s.outputs.equity_irr != null ? pct(s.outputs.equity_irr) : s.status}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
            </div>
          </SectionCard>

          {/* Most/Least vulnerable */}
          <div className="grid grid-cols-2 gap-4">
            {result.most_vulnerable.length > 0 && (
              <SectionCard title="Most Vulnerable">
                <ul className="space-y-1">
                  {result.most_vulnerable.map((d, i) => (
                    <li key={i} className="flex items-center gap-2 text-sm text-red-700">
                      <TrendingDown size={13} className="text-red-400" /> {d}
                    </li>
                  ))}
                </ul>
              </SectionCard>
            )}
            {result.least_vulnerable.length > 0 && (
              <SectionCard title="Least Vulnerable">
                <ul className="space-y-1">
                  {result.least_vulnerable.map((d, i) => (
                    <li key={i} className="flex items-center gap-2 text-sm text-green-700">
                      <TrendingUp size={13} className="text-green-400" /> {d}
                    </li>
                  ))}
                </ul>
              </SectionCard>
            )}
          </div>
        </>
      )}

      {/* Empty */}
      {!result && !stressMut.isPending && (
        <div className="text-center py-20 text-gray-400">
          <ShieldAlert size={48} className="mx-auto mb-4 opacity-20" />
          <p className="text-sm font-medium">Select deals and run stress tests</p>
          <p className="text-xs mt-1">Ranks portfolio by vulnerability across all stress scenarios</p>
        </div>
      )}

      {/* Suppress unused import */}
      {void STRESS_COLORS}
      {void Badge}
    </div>
  );
}
