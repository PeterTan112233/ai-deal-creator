import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { useLocation } from "react-router-dom";
import { getScenarioTemplates, runBatchScenarios, type ScenarioTemplate, type BatchScenarioResult } from "../api/scenarios";
import { SectionCard } from "../components/SectionCard";
import { Button } from "../components/ui/Button";
import { Badge } from "../components/ui/Badge";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "../components/ui/Tabs";
import { sampleDeals } from "../lib/sampleDeals";
import { TrendingUp, TrendingDown } from "lucide-react";

const TYPE_COLORS: Record<string, "default" | "info" | "warning" | "danger"> = {
  base: "info",
  stress: "warning",
  regulatory: "danger",
};

function StatusBadge({ status }: { status?: string }) {
  if (!status) return null;
  const s = String(status).toLowerCase();
  if (s === "completed" || s === "ok") return <Badge variant="success">completed</Badge>;
  if (s === "error" || s === "failed") return <Badge variant="danger">error</Badge>;
  return <Badge variant="default">{status}</Badge>;
}

function fmtPct(v: unknown): string {
  if (v == null) return "—";
  const n = Number(v);
  return isNaN(n) ? "—" : `${(n * 100).toFixed(2)}%`;
}

function fmtNum(v: unknown): string {
  if (v == null) return "—";
  const n = Number(v);
  return isNaN(n) ? "—" : n.toFixed(2);
}

export function ScenarioRunnerPage() {
  const location = useLocation();
  const preloaded = (location.state as { dealInput?: Record<string, unknown> } | null)
    ?.dealInput;

  const [json, setJson] = useState(() =>
    preloaded
      ? JSON.stringify(preloaded, null, 2)
      : JSON.stringify(sampleDeals.usBSL, null, 2)
  );
  const [parseError, setParseError] = useState<string | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const templatesQuery = useQuery({
    queryKey: ["scenario-templates"],
    queryFn: getScenarioTemplates,
  });

  const mutation = useMutation({
    mutationFn: ({
      deal,
      templates,
    }: {
      deal: Record<string, unknown>;
      templates: ScenarioTemplate[];
    }) =>
      runBatchScenarios(
        deal,
        templates.map((t) => ({
          name: t.name,
          type: t.scenario_type,
          parameters: t.parameters,
        }))
      ),
  });

  function toggleTemplate(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function handleRun() {
    setParseError(null);
    const templates = (templatesQuery.data ?? []).filter((t) => selected.has(t.template_id));
    if (templates.length === 0) {
      setParseError("Select at least one scenario template.");
      return;
    }
    try {
      const deal = JSON.parse(json);
      mutation.mutate({ deal, templates });
    } catch {
      setParseError("Invalid deal JSON.");
    }
  }

  const result: BatchScenarioResult | undefined = mutation.data;
  const table = result?.comparison_table ?? [];

  const irrs = table
    .map((r) => r.equity_irr)
    .filter((v): v is number => typeof v === "number" && !isNaN(v));
  const bestIRR = irrs.length ? Math.max(...irrs) : null;
  const worstIRR = irrs.length ? Math.min(...irrs) : null;

  const templates = templatesQuery.data ?? [];
  const types = ["all", ...Array.from(new Set(templates.map((t) => t.scenario_type)))];

  return (
    <div className="space-y-6 max-w-5xl">
      <div>
        <h1 className="text-xl font-bold text-gray-900">Scenario Runner</h1>
        <p className="text-sm text-gray-500 mt-1">
          Select templates and run batch scenarios against a deal
        </p>
      </div>

      <div className="grid grid-cols-2 gap-6">
        {/* Template Browser */}
        <SectionCard title="Scenario Templates">
          {templatesQuery.isLoading && (
            <p className="text-sm text-gray-500">Loading templates…</p>
          )}
          {templatesQuery.isError && (
            <p className="text-sm text-red-600">Failed to load templates — is the backend running?</p>
          )}
          {templates.length > 0 && (
            <Tabs defaultValue="all">
              <TabsList>
                {types.map((t) => (
                  <TabsTrigger key={t} value={t}>
                    {t.charAt(0).toUpperCase() + t.slice(1)}
                  </TabsTrigger>
                ))}
              </TabsList>
              {types.map((type) => (
                <TabsContent key={type} value={type}>
                  <div className="space-y-2 max-h-72 overflow-y-auto pr-1">
                    {templates
                      .filter((t) => type === "all" || t.scenario_type === type)
                      .map((t) => (
                        <label
                          key={t.template_id}
                          className="flex items-start gap-3 p-2.5 rounded-md border border-gray-100 hover:bg-gray-50 cursor-pointer"
                        >
                          <input
                            type="checkbox"
                            className="mt-0.5"
                            checked={selected.has(t.template_id)}
                            onChange={() => toggleTemplate(t.template_id)}
                          />
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2">
                              <span className="text-sm font-medium text-gray-800 truncate">
                                {t.name}
                              </span>
                              <Badge variant={TYPE_COLORS[t.scenario_type] ?? "default"}>
                                {t.scenario_type}
                              </Badge>
                            </div>
                            <p className="text-xs text-gray-500 mt-0.5 line-clamp-2">
                              {t.description}
                            </p>
                          </div>
                        </label>
                      ))}
                  </div>
                </TabsContent>
              ))}
            </Tabs>
          )}
          <div className="mt-3 flex items-center justify-between">
            <span className="text-xs text-gray-500">{selected.size} selected</span>
            <div className="flex gap-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setSelected(new Set(templates.map((t) => t.template_id)))}
              >
                All
              </Button>
              <Button variant="ghost" size="sm" onClick={() => setSelected(new Set())}>
                None
              </Button>
            </div>
          </div>
        </SectionCard>

        {/* Deal Input */}
        <SectionCard title="Deal Input (JSON)">
          <textarea
            className="w-full h-72 font-mono text-xs border border-gray-200 rounded p-3 resize-y focus:outline-none focus:ring-2 focus:ring-gray-900"
            value={json}
            onChange={(e) => setJson(e.target.value)}
            spellCheck={false}
          />
          {parseError && <p className="text-red-600 text-sm mt-1">{parseError}</p>}
          <div className="flex gap-2 mt-3 flex-wrap">
            {["usBSL", "euCLO", "mmCLO"].map((k) => (
              <Button
                key={k}
                variant="outline"
                size="sm"
                onClick={() =>
                  setJson(JSON.stringify(sampleDeals[k as keyof typeof sampleDeals], null, 2))
                }
              >
                {k === "usBSL" ? "US BSL" : k === "euCLO" ? "EU CLO" : "MM CLO"}
              </Button>
            ))}
          </div>
        </SectionCard>
      </div>

      <Button onClick={handleRun} disabled={mutation.isPending} size="lg">
        {mutation.isPending ? "Running scenarios…" : `Run ${selected.size} Scenario(s)`}
      </Button>

      {mutation.isError && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700 text-sm">
          Error: {String(mutation.error)}
        </div>
      )}

      {result && (
        <>
          {/* Best/Worst */}
          {irrs.length > 0 && (
            <div className="grid grid-cols-2 gap-4">
              <SectionCard>
                <div className="flex items-center gap-3">
                  <TrendingUp className="text-green-500" size={24} />
                  <div>
                    <p className="text-xs text-gray-500">Best Equity IRR</p>
                    <p className="text-2xl font-black text-green-600">
                      {fmtPct(bestIRR)}
                    </p>
                  </div>
                </div>
              </SectionCard>
              <SectionCard>
                <div className="flex items-center gap-3">
                  <TrendingDown className="text-red-500" size={24} />
                  <div>
                    <p className="text-xs text-gray-500">Worst Equity IRR</p>
                    <p className="text-2xl font-black text-red-600">
                      {fmtPct(worstIRR)}
                    </p>
                  </div>
                </div>
              </SectionCard>
            </div>
          )}

          {/* Results Table */}
          <SectionCard title={`Results — ${result.scenarios_run} scenario(s) run`}>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs uppercase text-gray-500 border-b border-gray-100">
                    <th className="pb-2 pr-4">Scenario</th>
                    <th className="pb-2 pr-4">Type</th>
                    <th className="pb-2 pr-4">Equity IRR</th>
                    <th className="pb-2 pr-4">OC Cushion AAA</th>
                    <th className="pb-2 pr-4">WAC</th>
                    <th className="pb-2">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  {table.map((row, i) => (
                    <tr key={i}>
                      <td className="py-2 pr-4 font-medium text-gray-800">
                        {String(row.scenario_name ?? row.name ?? `Scenario ${i + 1}`)}
                      </td>
                      <td className="py-2 pr-4">
                        <Badge variant={TYPE_COLORS[String(row.scenario_type)] ?? "default"}>
                          {String(row.scenario_type ?? "—")}
                        </Badge>
                      </td>
                      <td className="py-2 pr-4 font-mono">
                        {row.equity_irr != null ? fmtPct(row.equity_irr) : "—"}
                      </td>
                      <td className="py-2 pr-4 font-mono">
                        {row.oc_cushion_aaa != null ? fmtPct(row.oc_cushion_aaa) : "—"}
                      </td>
                      <td className="py-2 pr-4 font-mono">
                        {row.wac != null ? fmtNum(row.wac) : "—"}
                      </td>
                      <td className="py-2">
                        <StatusBadge status={String(row.status ?? "completed")} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </SectionCard>
        </>
      )}
    </div>
  );
}
