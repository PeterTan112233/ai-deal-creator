import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  ReferenceLine,
  Legend,
} from "recharts";
import { runSensitivity, type SensitivityPoint } from "../api/analytics";
import { SectionCard } from "../components/SectionCard";
import { Button } from "../components/ui/Button";
import { Badge } from "../components/ui/Badge";
import { DealPickerModal } from "../components/DealPickerModal";
import { sampleDeals } from "../lib/sampleDeals";
import { TrendingUp, Database } from "lucide-react";

// ─── Parameter presets ────────────────────────────────────────────────────────

const PARAMETERS: {
  key: string;
  label: string;
  unit: string;
  presets: number[];
  formatTick: (v: number) => string;
}[] = [
  {
    key: "default_rate",
    label: "Default Rate",
    unit: "pct",
    presets: [0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.08, 0.10],
    formatTick: (v) => `${(v * 100).toFixed(0)}%`,
  },
  {
    key: "was",
    label: "WAS (Spread)",
    unit: "pct",
    presets: [0.030, 0.035, 0.040, 0.045, 0.050, 0.055, 0.060, 0.065],
    formatTick: (v) => `${(v * 100).toFixed(1)}%`,
  },
  {
    key: "warf",
    label: "WARF",
    unit: "raw",
    presets: [2200, 2400, 2600, 2800, 3000, 3200, 3400, 3600],
    formatTick: (v) => String(v),
  },
  {
    key: "ccc_bucket",
    label: "CCC Bucket",
    unit: "pct",
    presets: [0.01, 0.02, 0.03, 0.04, 0.05, 0.07, 0.10, 0.12],
    formatTick: (v) => `${(v * 100).toFixed(0)}%`,
  },
  {
    key: "diversity_score",
    label: "Diversity Score",
    unit: "raw",
    presets: [40, 50, 60, 70, 75, 80, 85, 90],
    formatTick: (v) => String(v),
  },
];

// ─── Chart tooltip ────────────────────────────────────────────────────────────

function CustomTooltip({
  active,
  payload,
  label,
  paramLabel,
  paramUnit,
}: {
  active?: boolean;
  payload?: { name: string; value: number; color: string }[];
  label?: number;
  paramLabel: string;
  paramUnit: string;
}) {
  if (!active || !payload?.length) return null;
  const fmtParam = paramUnit === "pct" ? `${((label ?? 0) * 100).toFixed(2)}%` : String(label);
  return (
    <div className="bg-white border border-gray-200 rounded shadow-sm px-3 py-2 text-xs">
      <p className="font-semibold text-gray-700 mb-1">
        {paramLabel}: {fmtParam}
      </p>
      {payload.map((p) => (
        <p key={p.name} style={{ color: p.color }}>
          {p.name}: {(p.value * 100).toFixed(2)}%
        </p>
      ))}
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export function SensitivityPage() {
  const [json, setJson] = useState(() => JSON.stringify(sampleDeals.usBSL, null, 2));
  const [paramKey, setParamKey] = useState("default_rate");
  const [valuesStr, setValuesStr] = useState("0.01,0.02,0.03,0.04,0.05,0.06,0.08,0.10");
  const [parseError, setParseError] = useState<string | null>(null);
  const [showPicker, setShowPicker] = useState(false);

  const param = PARAMETERS.find((p) => p.key === paramKey) ?? PARAMETERS[0];

  const mutation = useMutation({
    mutationFn: async () => {
      const dealInput = JSON.parse(json);
      const values = valuesStr
        .split(",")
        .map((s) => parseFloat(s.trim()))
        .filter((n) => !isNaN(n));
      if (values.length === 0) throw new Error("Enter at least one value.");
      return runSensitivity(dealInput, paramKey, values);
    },
  });

  function handleRun() {
    setParseError(null);
    try {
      JSON.parse(json);
    } catch {
      setParseError("Invalid deal JSON.");
      return;
    }
    mutation.mutate();
  }

  function applyPreset() {
    setValuesStr(param.presets.join(","));
  }

  const result = mutation.data;

  // Build chart data from series
  const chartData = (result?.series ?? []).map((pt: SensitivityPoint) => ({
    param: pt.parameter_value,
    equity_irr: pt.outputs.equity_irr ?? null,
    oc_cushion_aaa: pt.outputs.oc_cushion_aaa ?? null,
  }));

  // Summary stats
  const irrs = chartData
    .map((d) => d.equity_irr)
    .filter((v): v is number => v != null);
  const maxIRR = irrs.length ? Math.max(...irrs) : null;
  const minIRR = irrs.length ? Math.min(...irrs) : null;
  const breakeven = result?.breakeven;

  return (
    <div className="space-y-6 max-w-5xl">
      <div>
        <h1 className="text-xl font-bold text-gray-900">Sensitivity Analysis</h1>
        <p className="text-sm text-gray-500 mt-1">
          Sweep a single parameter and see how equity IRR and OC cushion respond
        </p>
      </div>

      <div className="grid grid-cols-2 gap-5">
        {/* Config panel */}
        <SectionCard title="Configuration">
          <div className="space-y-4">
            {/* Parameter selector */}
            <div>
              <label className="text-xs text-gray-600 mb-1 block">Parameter to sweep</label>
              <div className="flex flex-wrap gap-1.5">
                {PARAMETERS.map((p) => (
                  <button
                    key={p.key}
                    onClick={() => {
                      setParamKey(p.key);
                      setValuesStr(p.presets.join(","));
                    }}
                    className={`px-2.5 py-1 rounded-md text-xs font-medium border transition-colors ${
                      paramKey === p.key
                        ? "bg-gray-900 text-white border-gray-900"
                        : "border-gray-200 text-gray-600 hover:border-gray-400"
                    }`}
                  >
                    {p.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Values */}
            <div>
              <div className="flex items-center justify-between mb-1">
                <label className="text-xs text-gray-600">
                  Values (comma-separated, decimal)
                </label>
                <button
                  onClick={applyPreset}
                  className="text-xs text-blue-600 hover:underline"
                >
                  Use preset
                </button>
              </div>
              <input
                type="text"
                className="w-full h-9 font-mono text-sm border border-gray-200 rounded px-3 focus:outline-none focus:ring-2 focus:ring-gray-900"
                value={valuesStr}
                onChange={(e) => setValuesStr(e.target.value)}
                placeholder="0.01,0.02,0.03..."
              />
              <p className="text-xs text-gray-400 mt-1">
                e.g. for {param.label}: {param.presets.join(", ")}
              </p>
            </div>

            <Button onClick={handleRun} disabled={mutation.isPending}>
              <TrendingUp size={14} className="mr-1.5" />
              {mutation.isPending ? "Running…" : "Run Sensitivity"}
            </Button>

            {parseError && <p className="text-red-600 text-sm">{parseError}</p>}
            {mutation.isError && (
              <p className="text-red-600 text-sm">Error: {String(mutation.error)}</p>
            )}
          </div>
        </SectionCard>

        {showPicker && (
          <DealPickerModal
            onSelect={(input) => setJson(JSON.stringify(input, null, 2))}
            onClose={() => setShowPicker(false)}
          />
        )}

        {/* Deal input */}
        <SectionCard
          title="Deal Input (JSON)"
          action={
            <div className="flex items-center gap-2">
              <button
                onClick={() => setShowPicker(true)}
                className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-900 border border-gray-200 rounded px-2 py-1 hover:border-gray-400 transition-colors"
              >
                <Database size={12} /> Registry
              </button>
              <div className="flex gap-1">
                {(["usBSL", "euCLO", "mmCLO"] as const).map((k) => (
                  <button
                    key={k}
                    onClick={() => setJson(JSON.stringify(sampleDeals[k], null, 2))}
                    className="text-xs text-gray-400 hover:text-gray-700 px-1.5 py-0.5 border border-gray-200 rounded"
                  >
                    {k === "usBSL" ? "US BSL" : k === "euCLO" ? "EU CLO" : "MM CLO"}
                  </button>
                ))}
              </div>
            </div>
          }
        >
          <textarea
            className="w-full h-52 font-mono text-xs border border-gray-200 rounded p-3 resize-y focus:outline-none focus:ring-2 focus:ring-gray-900"
            value={json}
            onChange={(e) => setJson(e.target.value)}
            spellCheck={false}
          />
        </SectionCard>
      </div>

      {/* Results */}
      {result && (
        <>
          {/* Summary stats */}
          <div className="grid grid-cols-4 gap-4">
            {[
              ["Best Equity IRR", maxIRR != null ? `${(maxIRR * 100).toFixed(2)}%` : "—", "text-green-600"],
              ["Worst Equity IRR", minIRR != null ? `${(minIRR * 100).toFixed(2)}%` : "—", "text-red-600"],
              ["IRR Range", maxIRR != null && minIRR != null ? `${((maxIRR - minIRR) * 100).toFixed(2)}pp` : "—", "text-gray-900"],
              ["Points Tested", String(result.values_tested.length), "text-gray-900"],
            ].map(([label, value, color]) => (
              <div key={label} className="bg-white rounded-lg border border-gray-200 shadow-sm p-4 text-center">
                <p className="text-xs text-gray-500 mb-1">{label}</p>
                <p className={`text-xl font-black ${color}`}>{value}</p>
              </div>
            ))}
          </div>

          {/* Breakeven */}
          {breakeven && (
            <div className="flex gap-3">
              {breakeven.equity_irr_zero != null && (
                <div className="bg-amber-50 border border-amber-200 rounded px-4 py-2 text-sm text-amber-800">
                  Equity IRR = 0 at{" "}
                  <strong>
                    {param.unit === "pct"
                      ? `${(breakeven.equity_irr_zero * 100).toFixed(2)}%`
                      : String(breakeven.equity_irr_zero)}
                  </strong>{" "}
                  {param.label}
                </div>
              )}
              {breakeven.scenario_npv_zero != null && (
                <div className="bg-blue-50 border border-blue-200 rounded px-4 py-2 text-sm text-blue-800">
                  NPV = 0 at{" "}
                  <strong>
                    {param.unit === "pct"
                      ? `${(breakeven.scenario_npv_zero * 100).toFixed(2)}%`
                      : String(breakeven.scenario_npv_zero)}
                  </strong>{" "}
                  {param.label}
                </div>
              )}
            </div>
          )}

          {/* Chart */}
          <SectionCard
            title={`Equity IRR &amp; OC Cushion (AAA) vs ${param.label}`}
            action={result.is_mock && <Badge variant="warning">mock engine</Badge>}
          >
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={chartData} margin={{ top: 8, right: 24, bottom: 8, left: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis
                  dataKey="param"
                  tickFormatter={param.formatTick}
                  tick={{ fontSize: 11 }}
                  label={{
                    value: param.label,
                    position: "insideBottom",
                    offset: -4,
                    fontSize: 11,
                    fill: "#9ca3af",
                  }}
                  height={40}
                />
                <YAxis
                  tickFormatter={(v) => `${(v * 100).toFixed(0)}%`}
                  tick={{ fontSize: 11 }}
                  width={45}
                />
                <Tooltip
                  content={
                    <CustomTooltip
                      paramLabel={param.label}
                      paramUnit={param.unit}
                    />
                  }
                />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <ReferenceLine y={0} stroke="#ef4444" strokeDasharray="4 4" />
                <Line
                  type="monotone"
                  dataKey="equity_irr"
                  name="Equity IRR"
                  stroke="#3b82f6"
                  strokeWidth={2}
                  dot={{ r: 4, fill: "#3b82f6" }}
                  connectNulls
                />
                <Line
                  type="monotone"
                  dataKey="oc_cushion_aaa"
                  name="OC Cushion AAA"
                  stroke="#10b981"
                  strokeWidth={2}
                  dot={{ r: 4, fill: "#10b981" }}
                  connectNulls
                />
              </LineChart>
            </ResponsiveContainer>
          </SectionCard>

          {/* Data table */}
          <SectionCard title="Raw Data">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs uppercase text-gray-400 border-b border-gray-100">
                    <th className="pb-2 pr-4">{param.label}</th>
                    <th className="pb-2 pr-4">Equity IRR</th>
                    <th className="pb-2 pr-4">OC Cushion AAA</th>
                    <th className="pb-2 pr-4">WAC</th>
                    <th className="pb-2">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  {result.series.map((pt: SensitivityPoint) => (
                    <tr key={pt.parameter_value}>
                      <td className="py-2 pr-4 font-mono font-medium text-gray-700">
                        {param.formatTick(pt.parameter_value)}
                      </td>
                      <td className="py-2 pr-4 font-mono text-blue-600">
                        {pt.outputs.equity_irr != null
                          ? `${(pt.outputs.equity_irr * 100).toFixed(2)}%`
                          : "—"}
                      </td>
                      <td className="py-2 pr-4 font-mono text-emerald-600">
                        {pt.outputs.oc_cushion_aaa != null
                          ? `${(pt.outputs.oc_cushion_aaa * 100).toFixed(2)}%`
                          : "—"}
                      </td>
                      <td className="py-2 pr-4 font-mono text-gray-500">
                        {pt.outputs.wac != null
                          ? `${(pt.outputs.wac * 100).toFixed(2)}%`
                          : "—"}
                      </td>
                      <td className="py-2">
                        <Badge variant={pt.status === "complete" ? "success" : "danger"}>
                          {pt.status}
                        </Badge>
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
