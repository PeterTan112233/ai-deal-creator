import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { listDeals, getDeal, type DealSummary } from "../api/deals";
import { runHealthCheck, type HealthCheckResult } from "../api/health";
import { RegistryMultiSelect } from "../components/RegistryMultiSelect";
import { GradeCircle } from "../components/GradeCircle";
import { KRIBadge } from "../components/KRIBadge";
import { SectionCard } from "../components/SectionCard";
import { Button } from "../components/ui/Button";
import { Badge } from "../components/ui/Badge";
import { useToast } from "../components/ui/Toast";
import { Layers, CheckCircle2, AlertTriangle, XCircle } from "lucide-react";

// ─── Types ────────────────────────────────────────────────────────────────────

interface CheckResult {
  deal_id: string;
  name: string;
  status: "pending" | "running" | "done" | "error";
  result?: HealthCheckResult;
  error?: string;
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export function BulkHealthPage() {
  const toast = useToast();
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [results, setResults] = useState<CheckResult[]>([]);
  const [running, setRunning] = useState(false);

  const dealsQuery = useQuery({ queryKey: ["deals"], queryFn: listDeals });
  const deals: DealSummary[] = dealsQuery.data ?? [];

  const dealMap = new Map(deals.map((d) => [d.deal_id, d]));

  async function handleRun() {
    if (selected.size === 0) { toast.warning("Select at least one deal."); return; }
    setRunning(true);

    // Initialise result rows in pending state
    const initial: CheckResult[] = Array.from(selected).map((id) => ({
      deal_id: id,
      name: dealMap.get(id)?.name ?? id,
      status: "pending",
    }));
    setResults(initial);

    // Run all checks in parallel
    const checks = Array.from(selected).map(async (id) => {
      // Mark as running
      setResults((prev) =>
        prev.map((r) => r.deal_id === id ? { ...r, status: "running" } : r)
      );
      try {
        const detail = await getDeal(id);
        const health = await runHealthCheck(detail.deal_input);
        setResults((prev) =>
          prev.map((r) =>
            r.deal_id === id ? { ...r, status: "done", result: health } : r
          )
        );
      } catch (e) {
        setResults((prev) =>
          prev.map((r) =>
            r.deal_id === id ? { ...r, status: "error", error: String(e) } : r
          )
        );
      }
    });

    await Promise.all(checks);
    setRunning(false);
    toast.success(`Bulk health check complete — ${selected.size} deal${selected.size !== 1 ? "s" : ""}`);
  }

  // Summary counts
  const done = results.filter((r) => r.status === "done");
  const errored = results.filter((r) => r.status === "error");
  const criticalCount = done.filter((r) =>
    r.result?.key_risk_indicators?.some((k) => k.status === "critical")
  ).length;

  // Derive 3 key KRIs per deal
  function keyKris(r: HealthCheckResult) {
    return (r.key_risk_indicators ?? []).filter((k) =>
      ["equity_irr", "oc_cushion_aaa", "ccc_bucket"].includes(k.name)
    );
  }

  return (
    <div className="space-y-6 max-w-5xl">
      <div>
        <h1 className="text-xl font-bold text-gray-900">Bulk Health Check</h1>
        <p className="text-sm text-gray-500 mt-1">
          Select multiple deals and run health checks in parallel
        </p>
      </div>

      <div className="grid grid-cols-2 gap-5">
        {/* Deal selector */}
        <SectionCard title="Select Deals">
          <RegistryMultiSelect selected={selected} onChange={setSelected} />
        </SectionCard>

        {/* Info panel */}
        <SectionCard title="About Bulk Check">
          <div className="space-y-3 text-sm text-gray-600">
            <p>
              Runs <strong>POST /health-check</strong> for each selected deal in parallel.
              Results appear as they complete.
            </p>
            <p className="text-xs text-gray-400">
              For continuous monitoring with auto-refresh, see the{" "}
              <strong>Live Monitor</strong> page.
            </p>
            {results.length > 0 && (
              <div className="grid grid-cols-3 gap-3 pt-2">
                {[
                  { label: "Done", value: done.length, icon: CheckCircle2, color: "text-emerald-600" },
                  { label: "Critical", value: criticalCount, icon: AlertTriangle, color: "text-red-600" },
                  { label: "Errors", value: errored.length, icon: XCircle, color: "text-gray-400" },
                ].map(({ label, value, icon: Icon, color }) => (
                  <div key={label} className="bg-gray-50 rounded-lg p-3 text-center">
                    <Icon size={16} className={`mx-auto mb-1 ${color}`} />
                    <p className="text-xl font-black text-gray-900">{value}</p>
                    <p className="text-xs text-gray-500">{label}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        </SectionCard>
      </div>

      <div className="flex items-center gap-4">
        <Button onClick={handleRun} disabled={running || selected.size === 0} size="lg">
          <Layers size={15} className="mr-2" />
          {running
            ? `Running ${results.filter(r => r.status === "running").length} checks…`
            : `Check ${selected.size} Deal${selected.size !== 1 ? "s" : ""}`}
        </Button>
      </div>

      {/* Results table */}
      {results.length > 0 && (
        <SectionCard title="Results">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs uppercase text-gray-500 border-b border-gray-100">
                <th className="pb-2 pr-4">Deal</th>
                <th className="pb-2 pr-4">Grade</th>
                <th className="pb-2 pr-4">Score</th>
                <th className="pb-2 pr-4">KRIs</th>
                <th className="pb-2 pr-4">Action Items</th>
                <th className="pb-2">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {results.map((row) => (
                <tr key={row.deal_id} className="hover:bg-gray-50/50">
                  <td className="py-3 pr-4">
                    <p className="font-medium text-gray-900">{row.name}</p>
                    <p className="text-xs font-mono text-gray-300">{row.deal_id}</p>
                  </td>
                  <td className="py-3 pr-4">
                    {row.result ? (
                      <GradeCircle grade={row.result.overall_grade ?? "?"} size="sm" />
                    ) : (
                      <span className="text-gray-300">—</span>
                    )}
                  </td>
                  <td className="py-3 pr-4">
                    {row.result ? (
                      <div>
                        <div className="flex items-center gap-2">
                          <div className="h-1.5 rounded-full bg-gray-100 w-20">
                            <div
                              className={`h-1.5 rounded-full ${
                                (row.result.overall_score ?? 0) >= 70 ? "bg-emerald-500" :
                                (row.result.overall_score ?? 0) >= 50 ? "bg-amber-400" : "bg-red-500"
                              }`}
                              style={{ width: `${row.result.overall_score ?? 0}%` }}
                            />
                          </div>
                          <span className="font-mono text-xs text-gray-700">
                            {row.result.overall_score?.toFixed(1) ?? "—"}
                          </span>
                        </div>
                      </div>
                    ) : (
                      <span className="text-gray-300">—</span>
                    )}
                  </td>
                  <td className="py-3 pr-4">
                    {row.result ? (
                      <div className="flex gap-1 flex-wrap">
                        {keyKris(row.result).map((k) => (
                          <KRIBadge key={k.name} status={k.status} />
                        ))}
                      </div>
                    ) : (
                      <span className="text-gray-300">—</span>
                    )}
                  </td>
                  <td className="py-3 pr-4">
                    {row.result && row.result.action_items.length > 0 ? (
                      <Badge variant="warning">
                        {row.result.action_items.length} item{row.result.action_items.length !== 1 ? "s" : ""}
                      </Badge>
                    ) : row.result ? (
                      <Badge variant="success">none</Badge>
                    ) : (
                      <span className="text-gray-300">—</span>
                    )}
                  </td>
                  <td className="py-3">
                    {row.status === "pending" && <span className="text-xs text-gray-400">Waiting…</span>}
                    {row.status === "running" && (
                      <span className="text-xs text-blue-500 flex items-center gap-1">
                        <span className="h-1.5 w-1.5 rounded-full bg-blue-500 animate-pulse" />
                        Running
                      </span>
                    )}
                    {row.status === "done" && <Badge variant="success">Done</Badge>}
                    {row.status === "error" && (
                      <span className="text-xs text-red-500" title={row.error}>Error</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {/* Action items accordion */}
          {done.some((r) => r.result && r.result.action_items.length > 0) && (
            <div className="mt-4 pt-4 border-t border-gray-100">
              <p className="text-xs font-semibold text-gray-500 uppercase mb-3">Top Action Items</p>
              <div className="space-y-2">
                {done
                  .filter((r) => r.result && r.result.action_items.length > 0)
                  .map((r) => (
                    <div key={r.deal_id} className="bg-amber-50 rounded-lg p-3 border border-amber-100">
                      <p className="text-xs font-semibold text-gray-700 mb-1">{r.name}</p>
                      <ol className="space-y-0.5">
                        {r.result!.action_items.slice(0, 3).map((item, i) => (
                          <li key={i} className="text-xs text-gray-600">
                            {i + 1}. {item}
                          </li>
                        ))}
                        {r.result!.action_items.length > 3 && (
                          <li className="text-xs text-gray-400">
                            +{r.result!.action_items.length - 3} more
                          </li>
                        )}
                      </ol>
                    </div>
                  ))}
              </div>
            </div>
          )}
        </SectionCard>
      )}
    </div>
  );
}
