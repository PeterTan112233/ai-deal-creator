import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { client } from "../api/client";
import { getScenarioTemplates, type ScenarioTemplate } from "../api/scenarios";
import { SectionCard } from "../components/SectionCard";
import { Button } from "../components/ui/Button";
import { Badge } from "../components/ui/Badge";
import { RegistryMultiSelect, resolveSelectedDeals } from "../components/RegistryMultiSelect";
import { Grid3x3 } from "lucide-react";

// ─── Types ────────────────────────────────────────────────────────────────────

interface MatrixCell {
  deal_id: string;
  deal_name: string;
  template_id: string;
  template_name: string;
  equity_irr: number | null;
  oc_cushion: number | null;
  status: string;
  error?: string | null;
}

interface DealSummary {
  deal_id: string;
  deal_name: string;
  min_irr: number | null;
  max_irr: number | null;
  irr_range: number | null;
  worst_template: string | null;
  best_template: string | null;
}

interface TemplateSummary {
  template_id: string;
  template_name: string;
  avg_irr: number | null;
  min_irr: number | null;
  max_irr: number | null;
  most_impacted_deal: string | null;
}

interface MatrixResult {
  matrix_id: string;
  deal_count: number;
  template_count: number;
  cells: MatrixCell[];
  deal_summaries: DealSummary[];
  template_summaries: TemplateSummary[];
  is_mock: boolean;
  error?: string | null;
}

// ─── Cell color ───────────────────────────────────────────────────────────────

function irrColor(irr: number | null): { bg: string; text: string; label: string } {
  if (irr == null) return { bg: "bg-gray-50", text: "text-gray-400", label: "—" };
  if (irr >= 0.12) return { bg: "bg-emerald-100", text: "text-emerald-800", label: `${(irr * 100).toFixed(1)}%` };
  if (irr >= 0.08) return { bg: "bg-green-50", text: "text-green-700", label: `${(irr * 100).toFixed(1)}%` };
  if (irr >= 0.04) return { bg: "bg-amber-50", text: "text-amber-700", label: `${(irr * 100).toFixed(1)}%` };
  if (irr >= 0) return { bg: "bg-orange-100", text: "text-orange-700", label: `${(irr * 100).toFixed(1)}%` };
  return { bg: "bg-red-100", text: "text-red-700", label: `${(irr * 100).toFixed(1)}%` };
}

const TYPE_BADGE: Record<string, "info" | "warning" | "danger" | "default"> = {
  base: "info",
  stress: "warning",
  regulatory: "danger",
};

// ─── Page ─────────────────────────────────────────────────────────────────────

export function StressMatrixPage() {
  const [selectedDeals, setSelectedDeals] = useState<Set<string>>(new Set());
  const [selectedTemplates, setSelectedTemplates] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);

  const templatesQuery = useQuery({
    queryKey: ["scenario-templates"],
    queryFn: getScenarioTemplates,
  });
  const templates: ScenarioTemplate[] = templatesQuery.data ?? [];

  const mutation = useMutation({
    mutationFn: async ({
      dealInputs,
      templateIds,
    }: {
      dealInputs: Record<string, unknown>[];
      templateIds: string[];
    }) => {
      const res = await client.post("/portfolio/stress-matrix", {
        deal_inputs: dealInputs,
        template_ids: templateIds,
        actor: "frontend",
      });
      return res.data as MatrixResult;
    },
  });

  async function handleRun() {
    setError(null);
    if (selectedDeals.size === 0) { setError("Select at least one deal."); return; }
    if (selectedTemplates.size === 0) { setError("Select at least one scenario template."); return; }
    try {
      const dealInputs = await resolveSelectedDeals(Array.from(selectedDeals));
      mutation.mutate({ dealInputs, templateIds: Array.from(selectedTemplates) });
    } catch (e) {
      setError(String(e));
    }
  }

  const result = mutation.data;

  // Build deal_id → ordered index and template_id → ordered index for matrix lookup
  const dealOrder = result ? result.deal_summaries.map((d) => d.deal_id) : [];
  const templateOrder = result ? result.template_summaries.map((t) => t.template_id) : [];

  // Cell lookup map
  const cellMap = new Map<string, MatrixCell>();
  result?.cells.forEach((c) => cellMap.set(`${c.deal_id}::${c.template_id}`, c));

  return (
    <div className="space-y-6 max-w-7xl">
      <div>
        <h1 className="text-xl font-bold text-gray-900">Stress Matrix</h1>
        <p className="text-sm text-gray-500 mt-1">
          Cross-tabulate deals × scenarios — color-coded equity IRR heatmap
        </p>
      </div>

      <div className="grid grid-cols-2 gap-5">
        {/* Deal selector */}
        <SectionCard title="Select Deals">
          <RegistryMultiSelect selected={selectedDeals} onChange={setSelectedDeals} />
        </SectionCard>

        {/* Template selector */}
        <SectionCard title="Select Scenario Templates">
          {templatesQuery.isLoading && (
            <p className="text-sm text-gray-400">Loading templates…</p>
          )}
          {templates.length > 0 && (
            <>
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs text-gray-500">
                  {selectedTemplates.size} of {templates.length} selected
                </span>
                <div className="flex gap-2">
                  <button
                    onClick={() => setSelectedTemplates(new Set(templates.map((t) => t.template_id)))}
                    className="text-xs text-gray-500 hover:text-gray-900"
                  >
                    All
                  </button>
                  <span className="text-gray-300">·</span>
                  <button
                    onClick={() => setSelectedTemplates(new Set())}
                    className="text-xs text-gray-500 hover:text-gray-900"
                  >
                    None
                  </button>
                </div>
              </div>
              <div className="space-y-1.5 max-h-72 overflow-y-auto pr-1">
                {templates.map((t) => {
                  const checked = selectedTemplates.has(t.template_id);
                  return (
                    <label
                      key={t.template_id}
                      className={`flex items-start gap-3 p-2.5 rounded-md border cursor-pointer transition-colors ${
                        checked
                          ? "border-blue-200 bg-blue-50"
                          : "border-gray-100 hover:bg-gray-50"
                      }`}
                    >
                      <input
                        type="checkbox"
                        className="mt-0.5"
                        checked={checked}
                        onChange={() => {
                          const next = new Set(selectedTemplates);
                          if (next.has(t.template_id)) next.delete(t.template_id);
                          else next.add(t.template_id);
                          setSelectedTemplates(next);
                        }}
                      />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-medium text-gray-800 truncate">
                            {t.name}
                          </span>
                          <Badge variant={TYPE_BADGE[t.scenario_type] ?? "default"}>
                            {t.scenario_type}
                          </Badge>
                        </div>
                        <p className="text-xs text-gray-500 mt-0.5 line-clamp-1">
                          {t.description}
                        </p>
                      </div>
                    </label>
                  );
                })}
              </div>
            </>
          )}
        </SectionCard>
      </div>

      {/* Run button */}
      <div className="flex items-center gap-4">
        <Button onClick={handleRun} disabled={mutation.isPending} size="lg">
          <Grid3x3 size={15} className="mr-2" />
          {mutation.isPending
            ? "Running matrix…"
            : `Run ${selectedDeals.size}×${selectedTemplates.size} Matrix`}
        </Button>
        {error && <p className="text-red-600 text-sm">{error}</p>}
        {mutation.isError && (
          <p className="text-red-600 text-sm">Error: {String(mutation.error)}</p>
        )}
      </div>

      {/* Legend */}
      {result && (
        <div className="flex items-center gap-3 text-xs">
          <span className="text-gray-400 font-medium">IRR:</span>
          {[
            { bg: "bg-emerald-100 text-emerald-800", label: "≥ 12%" },
            { bg: "bg-green-50 text-green-700", label: "8–12%" },
            { bg: "bg-amber-50 text-amber-700", label: "4–8%" },
            { bg: "bg-orange-100 text-orange-700", label: "0–4%" },
            { bg: "bg-red-100 text-red-700", label: "< 0%" },
          ].map(({ bg, label }) => (
            <span key={label} className={`px-2 py-0.5 rounded font-mono ${bg}`}>
              {label}
            </span>
          ))}
          {result.is_mock && <Badge variant="warning">mock engine</Badge>}
        </div>
      )}

      {/* Heatmap grid */}
      {result && dealOrder.length > 0 && templateOrder.length > 0 && (
        <SectionCard
          title={`${result.deal_count} Deal${result.deal_count !== 1 ? "s" : ""} × ${result.template_count} Scenario${result.template_count !== 1 ? "s" : ""}`}
        >
          <div className="overflow-x-auto">
            <table className="text-sm border-collapse">
              <thead>
                <tr>
                  {/* Top-left corner */}
                  <th className="w-44 pb-2 pr-3" />
                  {templateOrder.map((tid) => {
                    const ts = result.template_summaries.find((t) => t.template_id === tid);
                    return (
                      <th key={tid} className="pb-2 px-2 text-center min-w-28">
                        <p className="text-xs font-semibold text-gray-700 leading-tight">
                          {ts?.template_name ?? tid}
                        </p>
                        {ts?.avg_irr != null && (
                          <p className="text-xs text-gray-400 font-mono mt-0.5">
                            avg {(ts.avg_irr * 100).toFixed(1)}%
                          </p>
                        )}
                      </th>
                    );
                  })}
                  <th className="pb-2 pl-3 text-left text-xs font-semibold text-gray-500 min-w-28">
                    Range
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {dealOrder.map((did) => {
                  const ds = result.deal_summaries.find((d) => d.deal_id === did);
                  return (
                    <tr key={did} className="hover:bg-gray-50/50">
                      {/* Deal label */}
                      <td className="py-2 pr-3">
                        <p className="text-xs font-semibold text-gray-800 leading-tight">
                          {ds?.deal_name ?? did}
                        </p>
                        {ds?.worst_template && (
                          <p className="text-xs text-red-500 mt-0.5">
                            worst: {ds.worst_template}
                          </p>
                        )}
                      </td>

                      {/* Cells */}
                      {templateOrder.map((tid) => {
                        const cell = cellMap.get(`${did}::${tid}`);
                        const { bg, text, label } = irrColor(cell?.equity_irr ?? null);
                        return (
                          <td key={tid} className="px-2 py-1.5 text-center">
                            <div
                              className={`rounded-md px-2 py-1.5 ${bg}`}
                              title={
                                cell?.oc_cushion != null
                                  ? `OC cushion: ${(cell.oc_cushion * 100).toFixed(1)}%`
                                  : undefined
                              }
                            >
                              <p className={`text-xs font-mono font-semibold ${text}`}>
                                {cell?.status === "error" ? (
                                  <span className="text-red-500">err</span>
                                ) : (
                                  label
                                )}
                              </p>
                              {cell?.oc_cushion != null && (
                                <p className="text-xs text-gray-400 font-mono mt-0.5 leading-none">
                                  OC {(cell.oc_cushion * 100).toFixed(0)}%
                                </p>
                              )}
                            </div>
                          </td>
                        );
                      })}

                      {/* IRR range summary */}
                      <td className="pl-3 py-2">
                        {ds && ds.min_irr != null && ds.max_irr != null ? (
                          <div className="text-xs font-mono">
                            <span className="text-green-600">
                              {(ds.max_irr * 100).toFixed(1)}%
                            </span>
                            <span className="text-gray-300 mx-1">→</span>
                            <span className={ds.min_irr < 0 ? "text-red-600" : "text-amber-600"}>
                              {(ds.min_irr * 100).toFixed(1)}%
                            </span>
                            {ds.irr_range != null && (
                              <p className="text-gray-400 mt-0.5">
                                Δ {(ds.irr_range * 100).toFixed(1)}pp
                              </p>
                            )}
                          </div>
                        ) : (
                          <span className="text-gray-400 text-xs">—</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </SectionCard>
      )}

      {/* Template summary bar */}
      {result && result.template_summaries.length > 0 && (
        <SectionCard title="Scenario Impact Summary">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
            {result.template_summaries.map((ts) => {
              const { bg, text } = irrColor(ts.avg_irr);
              return (
                <div
                  key={ts.template_id}
                  className="border border-gray-100 rounded-lg p-3 space-y-1"
                >
                  <p className="text-xs font-semibold text-gray-800 leading-tight">
                    {ts.template_name}
                  </p>
                  <p className={`text-lg font-black font-mono ${text}`}>
                    {ts.avg_irr != null ? `${(ts.avg_irr * 100).toFixed(1)}%` : "—"}
                  </p>
                  <div className={`text-xs rounded px-1.5 py-0.5 inline-block ${bg}`}>
                    avg IRR
                  </div>
                  {ts.most_impacted_deal && (
                    <p className="text-xs text-gray-400 truncate">
                      worst: {ts.most_impacted_deal}
                    </p>
                  )}
                </div>
              );
            })}
          </div>
        </SectionCard>
      )}
    </div>
  );
}
