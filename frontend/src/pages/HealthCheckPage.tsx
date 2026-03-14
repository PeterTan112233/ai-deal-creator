import { useState, useEffect } from "react";
import { useMutation } from "@tanstack/react-query";
import { useLocation } from "react-router-dom";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import { runHealthCheck, type HealthCheckResult, type KRI } from "../api/health";
import { GradeCircle } from "../components/GradeCircle";
import { KRIBadge } from "../components/KRIBadge";
import { SectionCard } from "../components/SectionCard";
import { Button } from "../components/ui/Button";
import { Badge } from "../components/ui/Badge";
import { useToast } from "../components/ui/Toast";
import { PrintButton } from "../components/ui/PrintButton";
import { DealPickerModal } from "../components/DealPickerModal";
import { sampleDeals } from "../lib/sampleDeals";
import { Database } from "lucide-react";

// Format a KRI value using the backend's `format` hint
function fmtKRI(kri: KRI): string {
  const v = kri.value;
  if (v == null) return "—";
  const fmt = kri.format ?? "num";
  if (fmt === "pct" || fmt === "pct+") return `${(v * 100).toFixed(2)}%`;
  if (fmt === "score") return `${v.toFixed(1)}/100`;
  if (fmt === "int") return `${Math.round(v)}`;
  return String(v);
}

const DIM_COLORS = ["#3b82f6", "#10b981", "#8b5cf6", "#f59e0b", "#ef4444"];

export function HealthCheckPage() {
  const location = useLocation();
  const toast = useToast();
  const preloaded = (location.state as { dealInput?: Record<string, unknown> } | null)
    ?.dealInput;

  const [json, setJson] = useState(() =>
    preloaded
      ? JSON.stringify(preloaded, null, 2)
      : JSON.stringify(sampleDeals.usBSL, null, 2)
  );
  const [parseError, setParseError] = useState<string | null>(null);
  const [showPicker, setShowPicker] = useState(false);

  const mutation = useMutation({
    mutationFn: (input: Record<string, unknown>) => runHealthCheck(input),
    onSuccess: () => toast.success("Health check complete."),
    onError: (err) => toast.error(`Health check failed: ${String(err)}`),
  });

  // If navigated here from Deal Registry with a deal, auto-run
  useEffect(() => {
    if (preloaded) {
      mutation.mutate(preloaded);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function handleRun() {
    setParseError(null);
    try {
      const parsed = JSON.parse(json);
      mutation.mutate(parsed);
    } catch {
      setParseError("Invalid JSON — please fix before running.");
    }
  }

  const result: HealthCheckResult | undefined = mutation.data;

  // --- Dimension scores chart ---
  // score_summary.dimension_scores = { dim_name: { score, weight, label, inputs } }
  const dimScores = result?.score_summary as
    | Record<string, { score: number; weight: number; label: string }>
    | undefined;
  const scoreChartData =
    dimScores?.dimension_scores && typeof dimScores.dimension_scores === "object"
      ? Object.entries(
          dimScores.dimension_scores as unknown as Record<string, { score: number; label: string }>
        ).map(([k, v]) => ({
          name: k.replace(/_/g, " "),
          value: typeof v.score === "number" ? Math.round(v.score) : 0,
        }))
      : [];

  // --- Stress summary ---
  const stressSummary = result?.stress_summary as
    | Record<string, unknown>
    | undefined;

  // --- KRIs ---
  const kris: KRI[] = result?.key_risk_indicators ?? [];

  return (
    <div className="space-y-6 max-w-5xl">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-bold text-gray-900">Deal Health Check</h1>
          <p className="text-sm text-gray-500 mt-1">
            Unified KRI dashboard — scoring, stress, and watchlist in one view
          </p>
        </div>
        {result && <PrintButton />}
      </div>

      {showPicker && (
        <DealPickerModal
          onSelect={(input) => setJson(JSON.stringify(input, null, 2))}
          onClose={() => setShowPicker(false)}
        />
      )}

      {/* Input */}
      <SectionCard
        title="Deal Input (JSON)"
        action={
          <button
            onClick={() => setShowPicker(true)}
            className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-900 border border-gray-200 rounded px-2 py-1 hover:border-gray-400 transition-colors"
          >
            <Database size={12} /> Pick from Registry
          </button>
        }
      >
        <textarea
          className="w-full h-56 font-mono text-xs border border-gray-200 rounded p-3 resize-y focus:outline-none focus:ring-2 focus:ring-gray-900"
          value={json}
          onChange={(e) => setJson(e.target.value)}
          spellCheck={false}
        />
        {parseError && <p className="text-red-600 text-sm mt-1">{parseError}</p>}
        <div className="flex gap-3 mt-3 flex-wrap">
          <Button onClick={handleRun} disabled={mutation.isPending}>
            {mutation.isPending ? "Running…" : "Run Health Check"}
          </Button>
          {(["usBSL", "euCLO", "mmCLO"] as const).map((k) => (
            <Button
              key={k}
              variant="outline"
              size="sm"
              onClick={() => setJson(JSON.stringify(sampleDeals[k], null, 2))}
            >
              {k === "usBSL" ? "US BSL" : k === "euCLO" ? "EU CLO" : "MM CLO"}
            </Button>
          ))}
        </div>
      </SectionCard>

      {result && (
        <>
          {/* Header */}
          <SectionCard>
            <div className="flex items-center gap-5">
              <GradeCircle grade={result.overall_grade ?? "?"} size="lg" />
              <div>
                <p className="text-lg font-bold text-gray-900">{result.deal_id}</p>
                <p className="text-3xl font-black text-gray-700 mt-1">
                  {result.overall_score?.toFixed(1) ?? "—"}
                  <span className="text-base font-normal text-gray-400">/100</span>
                </p>
                {result.is_mock && (
                  <Badge variant="warning" className="mt-1">MOCK ENGINE</Badge>
                )}
              </div>
            </div>
          </SectionCard>

          {/* KRI Table */}
          {kris.length > 0 && (
            <SectionCard title="Key Risk Indicators">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-gray-500 text-xs uppercase border-b border-gray-100">
                    <th className="pb-2 pr-4">Metric</th>
                    <th className="pb-2 pr-4">Status</th>
                    <th className="pb-2">Value</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  {kris.map((kri, i) => (
                    <tr key={i}>
                      <td className="py-2 pr-4 font-medium text-gray-700">
                        {kri.label ?? kri.name}
                      </td>
                      <td className="py-2 pr-4">
                        <KRIBadge status={kri.status} />
                      </td>
                      <td className="py-2 font-mono text-gray-900">
                        {fmtKRI(kri)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </SectionCard>
          )}

          {/* Dimension Scores chart */}
          {scoreChartData.length > 0 && (
            <SectionCard title="Dimension Scores">
              <ResponsiveContainer width="100%" height={180}>
                <BarChart
                  data={scoreChartData}
                  layout="vertical"
                  margin={{ top: 0, right: 24, bottom: 0, left: 130 }}
                >
                  <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 11 }} />
                  <YAxis
                    type="category"
                    dataKey="name"
                    tick={{ fontSize: 11 }}
                    width={125}
                  />
                  <Tooltip formatter={(v) => [`${v}/100`, "Score"]} />
                  <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                    {scoreChartData.map((_e, i) => (
                      <Cell key={i} fill={DIM_COLORS[i % DIM_COLORS.length]} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>

              {/* Top drivers */}
              {Array.isArray(
                (result.score_summary as Record<string, unknown>)?.top_drivers
              ) && (
                <div className="flex flex-wrap gap-2 mt-3">
                  {(
                    (result.score_summary as Record<string, unknown[]>).top_drivers ?? []
                  ).map((d, i) => (
                    <Badge key={i} variant="info">
                      {String(d)}
                    </Badge>
                  ))}
                </div>
              )}
            </SectionCard>
          )}

          {/* Stress Summary */}
          {stressSummary && (
            <SectionCard title="Stress Test Summary">
              <div className="grid grid-cols-3 gap-4">
                {(
                  [
                    ["Base IRR", stressSummary.base_irr],
                    ["Worst Stress IRR", stressSummary.min_stress_irr],
                    ["IRR Drawdown", stressSummary.irr_drawdown],
                  ] as [string, unknown][]
                ).map(([label, val]) => (
                  <div key={label} className="bg-gray-50 rounded-lg p-3 text-center">
                    <p className="text-xs text-gray-500 mb-1">{label}</p>
                    <p className="text-lg font-bold text-gray-900">
                      {val != null && typeof val === "number"
                        ? `${(val * 100).toFixed(2)}%`
                        : "—"}
                    </p>
                  </div>
                ))}
              </div>
            </SectionCard>
          )}

          {/* Action Items */}
          {result.action_items.length > 0 && (
            <SectionCard title="Action Items">
              <ol className="space-y-2 list-none">
                {result.action_items.map((item, i) => (
                  <li key={i} className="flex gap-3 text-sm text-gray-700">
                    <span className="flex-shrink-0 h-6 w-6 rounded-full bg-gray-900 text-white text-xs flex items-center justify-center font-bold">
                      {i + 1}
                    </span>
                    {item}
                  </li>
                ))}
              </ol>
            </SectionCard>
          )}
        </>
      )}
    </div>
  );
}
