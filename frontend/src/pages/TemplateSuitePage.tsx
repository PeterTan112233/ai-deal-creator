import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { getTemplates, runTemplateSuite, type TemplateSuiteResult, type ScenarioTemplate } from "../api/templateSuite";
import { listDeals, getDeal } from "../api/deals";
import { SectionCard } from "../components/SectionCard";
import { Button } from "../components/ui/Button";
import { Badge } from "../components/ui/Badge";
import { useToast } from "../components/ui/Toast";
import { sampleDeals } from "../lib/sampleDeals";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid,
  ResponsiveContainer, Cell, ReferenceLine,
} from "recharts";
import { Play, Database, Code, CheckCircle2, XCircle, TrendingUp, TrendingDown } from "lucide-react";
import { ExportMenu } from "../components/ui/ExportMenu";

// ─── Helpers ──────────────────────────────────────────────────────────────────

const TYPE_COLORS: Record<string, string> = {
  base: "#3b82f6",
  stress: "#f59e0b",
  regulatory: "#8b5cf6",
};

function pct(v: unknown): string {
  if (v == null) return "—";
  const n = Number(v);
  if (isNaN(n)) return String(v);
  return `${(n * 100).toFixed(2)}%`;
}

function fmt2(v: unknown): string {
  if (v == null) return "—";
  const n = Number(v);
  if (isNaN(n)) return String(v);
  if (Math.abs(n) < 2) return pct(v);
  return n.toFixed(2);
}

function typeVariant(t: string): "info" | "warning" | "default" {
  if (t === "base") return "info";
  if (t === "stress") return "warning";
  return "default";
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export function TemplateSuitePage() {
  const toast = useToast();

  // Input mode
  const [mode, setMode] = useState<"registry" | "json">("registry");
  const [selectedDeal, setSelectedDeal] = useState<string>("");
  const [json, setJson] = useState(JSON.stringify(sampleDeals.usBSL, null, 2));
  const [jsonErr, setJsonErr] = useState<string | null>(null);

  // Template selection
  const [selectedTemplates, setSelectedTemplates] = useState<Set<string>>(new Set());
  const [typeFilter, setTypeFilter] = useState<string>("all");

  const [result, setResult] = useState<TemplateSuiteResult | null>(null);

  // Data queries
  const dealsQuery = useQuery({ queryKey: ["deals"], queryFn: listDeals, staleTime: 30_000 });
  const templatesQuery = useQuery({ queryKey: ["templates"], queryFn: getTemplates, staleTime: 300_000 });

  const deals = dealsQuery.data ?? [];
  const allTemplates: ScenarioTemplate[] = templatesQuery.data?.templates ?? [];
  const visibleTemplates = typeFilter === "all"
    ? allTemplates
    : allTemplates.filter((t) => t.scenario_type === typeFilter);

  function toggleTemplate(id: string) {
    setSelectedTemplates((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }

  function toggleAll() {
    if (selectedTemplates.size === allTemplates.length) setSelectedTemplates(new Set());
    else setSelectedTemplates(new Set(allTemplates.map((t) => t.template_id)));
  }

  const runMut = useMutation({
    mutationFn: async () => {
      let deal_input: Record<string, unknown>;
      if (mode === "registry") {
        if (!selectedDeal) throw new Error("Select a deal");
        const detail = await getDeal(selectedDeal);
        deal_input = detail.deal_input as Record<string, unknown>;
      } else {
        setJsonErr(null);
        try { deal_input = JSON.parse(json); }
        catch { throw new Error("Invalid JSON"); }
      }
      const ids = selectedTemplates.size > 0 ? [...selectedTemplates] : undefined;
      return runTemplateSuite(deal_input, ids);
    },
    onSuccess: (res) => {
      setResult(res);
      toast.success(`Suite complete — ${res.scenario_count} scenarios.`);
    },
    onError: (e) => {
      setJsonErr(String(e));
      toast.error(String(e));
    },
  });

  // Chart data: equity_irr per scenario
  const chartData = result?.results.map((r) => ({
    name: r.name.length > 14 ? r.name.slice(0, 13) + "…" : r.name,
    irr: r.outputs.equity_irr != null ? parseFloat(((r.outputs.equity_irr as number) * 100).toFixed(2)) : null,
    type: r.scenario_type,
    status: r.status,
  })).filter((r) => r.irr != null) ?? [];

  // Best / worst by IRR
  const sorted = result?.results
    .filter((r) => r.status === "completed" && r.outputs.equity_irr != null)
    .sort((a, b) => (b.outputs.equity_irr as number) - (a.outputs.equity_irr as number)) ?? [];
  const best = sorted[0];
  const worst = sorted[sorted.length - 1];

  // Key output columns
  const KEY_OUTPUTS = ["equity_irr", "oc_cushion_aaa", "wac", "irr_drawdown"];

  return (
    <div className="space-y-6 max-w-6xl">
      <div>
        <h1 className="text-xl font-bold text-gray-900">Template Suite Runner</h1>
        <p className="text-sm text-gray-500 mt-1">
          Run all scenario templates in one shot — base, stress, and regulatory
        </p>
      </div>

      {/* Input */}
      <SectionCard
        title="Deal Input"
        action={
          <div className="flex items-center gap-1 bg-gray-100 rounded-md p-0.5">
            <button
              onClick={() => setMode("registry")}
              className={`px-2.5 py-1 rounded text-xs font-medium transition-colors flex items-center gap-1 ${
                mode === "registry" ? "bg-white shadow text-gray-900" : "text-gray-500 hover:text-gray-700"
              }`}
            >
              <Database size={11} /> Registry
            </button>
            <button
              onClick={() => setMode("json")}
              className={`px-2.5 py-1 rounded text-xs font-medium transition-colors flex items-center gap-1 ${
                mode === "json" ? "bg-white shadow text-gray-900" : "text-gray-500 hover:text-gray-700"
              }`}
            >
              <Code size={11} /> JSON
            </button>
          </div>
        }
      >
        {mode === "registry" ? (
          <select
            className="w-full border border-gray-200 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-gray-900"
            value={selectedDeal}
            onChange={(e) => setSelectedDeal(e.target.value)}
          >
            <option value="">— Select a registered deal —</option>
            {deals.map((d) => (
              <option key={d.deal_id} value={d.deal_id}>{d.name} ({d.issuer})</option>
            ))}
          </select>
        ) : (
          <>
            <div className="flex gap-2 mb-2">
              {(["usBSL", "euCLO", "mmCLO"] as const).map((k) => (
                <Button key={k} variant="outline" size="sm"
                  onClick={() => setJson(JSON.stringify(sampleDeals[k], null, 2))}>
                  {k === "usBSL" ? "US BSL" : k === "euCLO" ? "EU CLO" : "MM CLO"}
                </Button>
              ))}
            </div>
            <textarea
              className="w-full h-36 font-mono text-xs border border-gray-200 rounded p-3 resize-y focus:outline-none focus:ring-2 focus:ring-gray-900"
              value={json}
              onChange={(e) => setJson(e.target.value)}
              spellCheck={false}
            />
            {jsonErr && <p className="text-red-600 text-xs mt-1">{jsonErr}</p>}
          </>
        )}
      </SectionCard>

      {/* Template selector */}
      <SectionCard
        title={`Templates (${selectedTemplates.size === 0 ? "all" : selectedTemplates.size} selected)`}
        action={
          <div className="flex items-center gap-2">
            <div className="flex gap-1">
              {["all", "base", "stress", "regulatory"].map((t) => (
                <button
                  key={t}
                  onClick={() => setTypeFilter(t)}
                  className={`px-2 py-0.5 rounded text-xs font-medium transition-colors ${
                    typeFilter === t ? "bg-gray-900 text-white" : "text-gray-500 hover:bg-gray-100"
                  }`}
                >
                  {t}
                </button>
              ))}
            </div>
            <button onClick={toggleAll} className="text-xs text-gray-400 hover:text-gray-700">
              {selectedTemplates.size === allTemplates.length ? "None" : "All"}
            </button>
          </div>
        }
      >
        {templatesQuery.isLoading && <p className="text-sm text-gray-400">Loading templates…</p>}
        <div className="grid grid-cols-3 gap-2">
          {visibleTemplates.map((t) => {
            const checked = selectedTemplates.size === 0 || selectedTemplates.has(t.template_id);
            const explicit = selectedTemplates.has(t.template_id);
            return (
              <label
                key={t.template_id}
                className={`flex gap-2 p-3 rounded-lg border cursor-pointer transition-colors ${
                  explicit ? "border-blue-300 bg-blue-50" :
                  selectedTemplates.size === 0 ? "border-gray-100 bg-gray-50" : "border-gray-100 opacity-50"
                }`}
              >
                <input
                  type="checkbox"
                  checked={checked && (explicit || selectedTemplates.size === 0)}
                  onChange={() => {
                    if (selectedTemplates.size === 0) {
                      // All were implicitly selected — switch to explicit, excluding this one
                      const all = new Set(allTemplates.map((x) => x.template_id));
                      all.delete(t.template_id);
                      setSelectedTemplates(all);
                    } else {
                      toggleTemplate(t.template_id);
                    }
                  }}
                  className="accent-blue-600 mt-0.5 shrink-0"
                />
                <div className="min-w-0">
                  <div className="flex items-center gap-1 mb-0.5">
                    <p className="text-xs font-semibold text-gray-900 truncate">{t.name}</p>
                    <Badge variant={typeVariant(t.scenario_type)}>{t.scenario_type}</Badge>
                  </div>
                  <p className="text-xs text-gray-400 line-clamp-2">{t.description}</p>
                  <div className="flex gap-2 mt-1 text-xs text-gray-500 font-mono">
                    <span>CDR {(t.parameters.default_rate * 100).toFixed(1)}%</span>
                    <span>RR {(t.parameters.recovery_rate * 100).toFixed(0)}%</span>
                    {t.parameters.spread_shock_bps > 0 && (
                      <span>+{t.parameters.spread_shock_bps}bps</span>
                    )}
                  </div>
                </div>
              </label>
            );
          })}
        </div>
        <div className="mt-4">
          <Button
            onClick={() => runMut.mutate()}
            disabled={runMut.isPending || (mode === "registry" && !selectedDeal)}
          >
            <Play size={13} className="mr-1.5" />
            {runMut.isPending
              ? "Running suite…"
              : `Run ${selectedTemplates.size === 0 ? allTemplates.length : selectedTemplates.size} Templates`}
          </Button>
        </div>
      </SectionCard>

      {/* Results */}
      {result && (
        <>
          {/* Summary */}
          <div className="grid grid-cols-4 gap-4">
            {[
              ["Scenarios Run", result.scenario_count],
              ["Completed", result.results.filter((r) => r.status === "completed").length],
              ["Failed", result.results.filter((r) => r.status === "failed").length],
              ["Best IRR", best ? pct(best.outputs.equity_irr) : "—"],
            ].map(([label, val]) => (
              <SectionCard key={String(label)}>
                <p className="text-xs text-gray-500 mb-1">{String(label)}</p>
                <p className="text-2xl font-black text-gray-900">{String(val)}</p>
              </SectionCard>
            ))}
          </div>

          {/* Best / worst */}
          {(best || worst) && (
            <div className="grid grid-cols-2 gap-4">
              {best && (
                <div className="flex items-center gap-3 p-4 bg-green-50 border border-green-200 rounded-xl">
                  <TrendingUp size={24} className="text-green-500 shrink-0" />
                  <div>
                    <p className="text-xs text-green-600 font-medium">Best Outcome</p>
                    <p className="text-sm font-bold text-green-800">{best.name}</p>
                    <p className="text-xs text-green-600 font-mono">IRR {pct(best.outputs.equity_irr)}</p>
                  </div>
                </div>
              )}
              {worst && worst.template_id !== best?.template_id && (
                <div className="flex items-center gap-3 p-4 bg-red-50 border border-red-200 rounded-xl">
                  <TrendingDown size={24} className="text-red-500 shrink-0" />
                  <div>
                    <p className="text-xs text-red-600 font-medium">Worst Outcome</p>
                    <p className="text-sm font-bold text-red-800">{worst.name}</p>
                    <p className="text-xs text-red-600 font-mono">IRR {pct(worst.outputs.equity_irr)}</p>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* IRR waterfall chart */}
          {chartData.length > 0 && (
            <SectionCard title="Equity IRR by Scenario">
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={chartData} margin={{ top: 4, right: 16, bottom: 40, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis dataKey="name" tick={{ fontSize: 9 }} angle={-30} textAnchor="end" interval={0} />
                  <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => `${v}%`} />
                  <Tooltip formatter={(v) => [`${v}%`, "Equity IRR"]} />
                  <ReferenceLine y={0} stroke="#e5e7eb" />
                  <Bar dataKey="irr" radius={[3, 3, 0, 0]}>
                    {chartData.map((entry, i) => (
                      <Cell key={i} fill={TYPE_COLORS[entry.type] ?? "#6b7280"} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
              <div className="flex items-center gap-4 mt-2">
                {Object.entries(TYPE_COLORS).map(([type, color]) => (
                  <div key={type} className="flex items-center gap-1.5 text-xs text-gray-500">
                    <div className="w-2.5 h-2.5 rounded-sm" style={{ background: color }} />
                    {type}
                  </div>
                ))}
              </div>
            </SectionCard>
          )}

          {/* Results table */}
          <SectionCard title="Full Results" action={
            result && <ExportMenu
              label="template-suite"
              data={result}
              csvRows={result.results.map(r => ({
                template_id: r.template_id,
                name: r.name,
                type: r.scenario_type,
                status: r.status,
                equity_irr: r.outputs.equity_irr,
                oc_cushion_aaa: r.outputs.oc_cushion_aaa,
                wac: r.outputs.wac,
                irr_drawdown: r.outputs.irr_drawdown,
              }))}
            />
          }>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs uppercase text-gray-500 border-b border-gray-100">
                    <th className="pb-2 pr-3">Scenario</th>
                    <th className="pb-2 pr-3">Type</th>
                    {KEY_OUTPUTS.map((k) => (
                      <th key={k} className="pb-2 pr-3 font-mono">{k.replace(/_/g, " ")}</th>
                    ))}
                    <th className="pb-2">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  {result.results.map((r) => (
                    <tr key={r.template_id} className="hover:bg-gray-50">
                      <td className="py-2.5 pr-3">
                        <p className="font-medium text-gray-900">{r.name}</p>
                        <p className="text-xs text-gray-400 font-mono">{r.template_id}</p>
                      </td>
                      <td className="py-2.5 pr-3">
                        <Badge variant={typeVariant(r.scenario_type)}>{r.scenario_type}</Badge>
                      </td>
                      {KEY_OUTPUTS.map((k) => (
                        <td key={k} className="py-2.5 pr-3 font-mono text-gray-700">
                          {r.status === "failed" ? (
                            <span className="text-gray-300">—</span>
                          ) : (
                            fmt2(r.outputs[k])
                          )}
                        </td>
                      ))}
                      <td className="py-2.5">
                        {r.status === "completed"
                          ? <span className="flex items-center gap-1 text-xs text-green-600"><CheckCircle2 size={12} />ok</span>
                          : <span className="flex items-center gap-1 text-xs text-red-500"><XCircle size={12} />{r.error ?? "failed"}</span>
                        }
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </SectionCard>

          {/* Summary text */}
          {result.summary && (
            <SectionCard title="Suite Summary">
              <p className="text-sm text-gray-700 leading-relaxed">{result.summary}</p>
            </SectionCard>
          )}
        </>
      )}

      {/* Empty */}
      {!result && !runMut.isPending && (
        <div className="text-center py-20 text-gray-400">
          <Play size={48} className="mx-auto mb-4 opacity-20" />
          <p className="text-sm font-medium">Select a deal and run the template suite</p>
          <p className="text-xs mt-1">Runs base, stress, and regulatory scenarios in one shot</p>
        </div>
      )}
    </div>
  );
}
