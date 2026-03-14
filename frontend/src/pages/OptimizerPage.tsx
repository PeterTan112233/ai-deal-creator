import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  CartesianGrid,
} from "recharts";
import { optimizeStructure, type OptimizeResponse, type FeasibilityRow } from "../api/optimize";
import { SectionCard } from "../components/SectionCard";
import { Button } from "../components/ui/Button";
import { Badge } from "../components/ui/Badge";
import { RegistryMultiSelect, resolveSelectedDeals } from "../components/RegistryMultiSelect";
import { useToast } from "../components/ui/Toast";
import { sampleDeals } from "../lib/sampleDeals";
import { Database, Code, Zap } from "lucide-react";

// ─── Helpers ──────────────────────────────────────────────────────────────────

function pct(v: number | null | undefined, dec = 1): string {
  if (v == null) return "—";
  return `${(v * 100).toFixed(dec)}%`;
}

function passChip(pass: boolean) {
  return pass ? (
    <Badge variant="success">pass</Badge>
  ) : (
    <Badge variant="danger">fail</Badge>
  );
}

// ─── Param row helper ─────────────────────────────────────────────────────────

function ParamRow({
  label,
  value,
  onChange,
  min,
  max,
  step,
  suffix,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  min?: number;
  max?: number;
  step?: number;
  suffix?: string;
}) {
  return (
    <div className="flex items-center justify-between gap-4">
      <label className="text-xs text-gray-600 w-40 shrink-0">{label}</label>
      <div className="flex items-center gap-1">
        <input
          type="number"
          className="w-24 text-xs font-mono border border-gray-200 rounded px-2 py-1 focus:outline-none focus:ring-1 focus:ring-gray-900 text-right"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          min={min}
          max={max}
          step={step}
        />
        {suffix && <span className="text-xs text-gray-400">{suffix}</span>}
      </div>
    </div>
  );
}

function TextRow({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <div className="flex items-center justify-between gap-4">
      <label className="text-xs text-gray-600 w-40 shrink-0">{label}</label>
      <input
        type="text"
        className="w-32 text-xs font-mono border border-gray-200 rounded px-2 py-1 focus:outline-none focus:ring-1 focus:ring-gray-900"
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export function OptimizerPage() {
  const toast = useToast();

  // ─ Input mode ─
  const [mode, setMode] = useState<"registry" | "json">("registry");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [json, setJson] = useState(() => JSON.stringify(sampleDeals.usBSL, null, 2));
  const [parseError, setParseError] = useState<string | null>(null);

  // ─ Optimizer params (displayed as %) ─
  const [aaaMin, setAaaMin] = useState("55");
  const [aaaMax, setAaaMax] = useState("72");
  const [aaaStep, setAaaStep] = useState("0.5");
  const [mezSize, setMezSize] = useState("8");
  const [ocFloor, setOcFloor] = useState("18");
  const [icFloor, setIcFloor] = useState("10");
  const [aaaCoupon, setAaaCoupon] = useState("SOFR+145");
  const [mezCoupon, setMezCoupon] = useState("SOFR+200");

  const mutation = useMutation({
    mutationFn: ({
      dealInput,
      params,
    }: {
      dealInput: Record<string, unknown>;
      params: Record<string, unknown>;
    }) => optimizeStructure(dealInput, params),
    onSuccess: (data) => {
      if (data.optimal) {
        toast.success(
          `Optimal: AAA ${pct(data.optimal.aaa_size_pct)} → IRR ${pct(data.optimal.equity_irr)}`
        );
      } else {
        toast.warning("No feasible structure found within constraints.");
      }
    },
    onError: (err) => toast.error(`Optimizer failed: ${String(err)}`),
  });

  async function handleRun() {
    setParseError(null);
    try {
      let dealInput: Record<string, unknown>;
      if (mode === "registry") {
        if (selected.size === 0) {
          setParseError("Select a deal from the registry.");
          return;
        }
        const inputs = await resolveSelectedDeals(Array.from(selected));
        dealInput = inputs[0];
      } else {
        const parsed = JSON.parse(json);
        if (Array.isArray(parsed)) {
          dealInput = parsed[0];
        } else {
          dealInput = parsed;
        }
      }
      mutation.mutate({
        dealInput,
        params: {
          aaa_min: parseFloat(aaaMin) / 100,
          aaa_max: parseFloat(aaaMax) / 100,
          aaa_step: parseFloat(aaaStep) / 100,
          mez_size_pct: parseFloat(mezSize) / 100,
          oc_floor: parseFloat(ocFloor) / 100,
          ic_floor: parseFloat(icFloor) / 100,
          aaa_coupon: aaaCoupon,
          mez_coupon: mezCoupon,
        },
      });
    } catch (e) {
      setParseError(String(e));
    }
  }

  const result: OptimizeResponse | undefined = mutation.data;

  // Frontier chart: x = AAA size %, y = equity IRR %
  const chartData = (result?.frontier ?? []).map((pt) => ({
    aaa: parseFloat((pt.aaa_size_pct * 100).toFixed(1)),
    irr: parseFloat((pt.equity_irr * 100).toFixed(2)),
  }));

  return (
    <div className="space-y-6 max-w-5xl">
      <div>
        <h1 className="text-xl font-bold text-gray-900">Deal Optimizer</h1>
        <p className="text-sm text-gray-500 mt-1">
          Sweep AAA tranche sizes to find the structure that maximises equity IRR within OC and IC constraints
        </p>
      </div>

      {/* Input + params grid */}
      <div className="grid grid-cols-2 gap-5">
        {/* Deal input */}
        <SectionCard
          title="Deal Input"
          action={
            <div className="flex items-center gap-1 bg-gray-100 rounded-md p-0.5">
              <button
                onClick={() => setMode("registry")}
                className={`px-2.5 py-1 rounded text-xs font-medium transition-colors flex items-center gap-1 ${
                  mode === "registry"
                    ? "bg-white shadow text-gray-900"
                    : "text-gray-500 hover:text-gray-700"
                }`}
              >
                <Database size={11} /> Registry
              </button>
              <button
                onClick={() => setMode("json")}
                className={`px-2.5 py-1 rounded text-xs font-medium transition-colors flex items-center gap-1 ${
                  mode === "json"
                    ? "bg-white shadow text-gray-900"
                    : "text-gray-500 hover:text-gray-700"
                }`}
              >
                <Code size={11} /> JSON
              </button>
            </div>
          }
        >
          {mode === "registry" ? (
            <RegistryMultiSelect
              selected={selected}
              onChange={setSelected}
              maxSelect={1}
            />
          ) : (
            <textarea
              className="w-full h-52 font-mono text-xs border border-gray-200 rounded p-3 resize-y focus:outline-none focus:ring-2 focus:ring-gray-900"
              value={json}
              onChange={(e) => setJson(e.target.value)}
              spellCheck={false}
            />
          )}
          {parseError && <p className="text-red-600 text-sm mt-2">{parseError}</p>}
        </SectionCard>

        {/* Constraint params */}
        <SectionCard title="Constraints">
          <div className="space-y-3">
            <p className="text-xs text-gray-400 uppercase font-semibold tracking-wide">
              AAA Sweep Range
            </p>
            <ParamRow label="AAA Min" value={aaaMin} onChange={setAaaMin} min={40} max={80} step={0.5} suffix="%" />
            <ParamRow label="AAA Max" value={aaaMax} onChange={setAaaMax} min={40} max={85} step={0.5} suffix="%" />
            <ParamRow label="Step Size" value={aaaStep} onChange={setAaaStep} min={0.1} max={2} step={0.1} suffix="pp" />

            <p className="text-xs text-gray-400 uppercase font-semibold tracking-wide pt-1">
              Capital Structure
            </p>
            <ParamRow label="MEZ Size" value={mezSize} onChange={setMezSize} min={2} max={20} step={0.5} suffix="%" />
            <TextRow label="AAA Coupon" value={aaaCoupon} onChange={setAaaCoupon} />
            <TextRow label="MEZ Coupon" value={mezCoupon} onChange={setMezCoupon} />

            <p className="text-xs text-gray-400 uppercase font-semibold tracking-wide pt-1">
              Floors
            </p>
            <ParamRow label="OC Floor" value={ocFloor} onChange={setOcFloor} min={5} max={40} step={0.5} suffix="%" />
            <ParamRow label="IC Floor" value={icFloor} onChange={setIcFloor} min={0} max={25} step={0.5} suffix="%" />
          </div>
        </SectionCard>
      </div>

      {/* Run button */}
      <div className="flex items-center gap-4">
        <Button onClick={handleRun} disabled={mutation.isPending} size="lg">
          <Zap size={15} className="mr-2" />
          {mutation.isPending ? "Optimizing…" : "Run Optimizer"}
        </Button>
        {mutation.isPending && (
          <p className="text-xs text-gray-400">
            Testing ~{Math.round(
              (parseFloat(aaaMax) - parseFloat(aaaMin)) / parseFloat(aaaStep) + 1
            )} candidate structures…
          </p>
        )}
      </div>

      {/* ── Results ── */}
      {result && (
        <>
          {/* Stats bar */}
          <div className="grid grid-cols-3 gap-4">
            {[
              ["Candidates", result.candidates_tested],
              ["Feasible", result.feasible_count],
              [
                "Feasibility Rate",
                result.candidates_tested > 0
                  ? `${((result.feasible_count / result.candidates_tested) * 100).toFixed(0)}%`
                  : "—",
              ],
            ].map(([label, val]) => (
              <SectionCard key={String(label)}>
                <p className="text-xs text-gray-500 mb-1">{String(label)}</p>
                <p className="text-2xl font-black text-gray-900">{String(val)}</p>
              </SectionCard>
            ))}
          </div>

          {/* Infeasible banner */}
          {result.infeasible_reason && (
            <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 text-amber-800 text-sm">
              <p className="font-semibold mb-1">No Feasible Structure Found</p>
              <p>{result.infeasible_reason}</p>
            </div>
          )}

          {/* Optimal structure card */}
          {result.optimal && (
            <SectionCard title="Optimal Structure">
              <div className="grid grid-cols-3 gap-6">
                {/* Tranche breakdown */}
                <div className="space-y-3 col-span-1">
                  <p className="text-xs text-gray-500 uppercase font-semibold tracking-wide">
                    Capital Stack
                  </p>
                  {[
                    { label: "AAA", pctVal: result.optimal.aaa_size_pct, color: "bg-blue-500" },
                    { label: "MEZ", pctVal: result.optimal.mez_size_pct, color: "bg-purple-400" },
                    { label: "Equity", pctVal: result.optimal.equity_size_pct, color: "bg-amber-400" },
                  ].map(({ label, pctVal, color }) => (
                    <div key={label}>
                      <div className="flex justify-between text-xs mb-1">
                        <span className="text-gray-600 font-medium">{label}</span>
                        <span className="font-mono text-gray-900">{pct(pctVal)}</span>
                      </div>
                      <div className="h-2 bg-gray-100 rounded-full">
                        <div
                          className={`h-2 rounded-full ${color}`}
                          style={{ width: `${(pctVal ?? 0) * 100}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </div>

                {/* Key metrics */}
                <div className="col-span-2 grid grid-cols-2 gap-4">
                  {[
                    ["Equity IRR", pct(result.optimal.equity_irr)],
                    ["OC Cushion AAA", pct(result.optimal.oc_cushion_aaa)],
                    ["IC Cushion AAA", pct(result.optimal.ic_cushion_aaa)],
                    ["WAC", pct(result.optimal.wac)],
                    ["Equity WAL", result.optimal.equity_wal != null ? `${result.optimal.equity_wal.toFixed(1)}yr` : "—"],
                  ].map(([label, val]) => (
                    <div key={String(label)} className="bg-gray-50 rounded-lg p-3">
                      <p className="text-xs text-gray-500 mb-1">{String(label)}</p>
                      <p className="text-lg font-black text-gray-900 font-mono">{String(val)}</p>
                    </div>
                  ))}
                  {result.is_mock && (
                    <div className="flex items-center">
                      <Badge variant="warning">mock engine</Badge>
                    </div>
                  )}
                </div>
              </div>
            </SectionCard>
          )}

          {/* Frontier chart */}
          {chartData.length > 0 && (
            <SectionCard title="IRR Frontier (Feasible Structures)">
              <p className="text-xs text-gray-400 mb-3">
                Equity IRR vs AAA tranche size — feasible points only (OC ≥ {ocFloor}%, IC ≥ {icFloor}%)
              </p>
              <ResponsiveContainer width="100%" height={220}>
                <LineChart data={chartData} margin={{ top: 4, right: 20, bottom: 4, left: 10 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis
                    dataKey="aaa"
                    tickFormatter={(v) => `${v}%`}
                    tick={{ fontSize: 11 }}
                    label={{ value: "AAA Size (%)", position: "insideBottomRight", offset: -4, fontSize: 11, fill: "#9ca3af" }}
                  />
                  <YAxis
                    tickFormatter={(v) => `${v}%`}
                    tick={{ fontSize: 11 }}
                    label={{ value: "Equity IRR (%)", angle: -90, position: "insideLeft", offset: 10, fontSize: 11, fill: "#9ca3af" }}
                  />
                  <Tooltip formatter={(v) => [`${v}%`, "Equity IRR"]} labelFormatter={(v) => `AAA: ${v}%`} />
                  <ReferenceLine y={0} stroke="#ef4444" strokeDasharray="4 2" />
                  <Line
                    type="monotone"
                    dataKey="irr"
                    stroke="#3b82f6"
                    strokeWidth={2}
                    dot={{ r: 3, fill: "#3b82f6" }}
                    activeDot={{ r: 5 }}
                  />
                  {/* Mark the optimal point */}
                  {result.optimal && (
                    <ReferenceLine
                      x={parseFloat((result.optimal.aaa_size_pct * 100).toFixed(1))}
                      stroke="#10b981"
                      strokeDasharray="4 2"
                      label={{ value: "optimal", position: "top", fontSize: 10, fill: "#10b981" }}
                    />
                  )}
                </LineChart>
              </ResponsiveContainer>
            </SectionCard>
          )}

          {/* Feasibility table */}
          {result.feasibility_table.length > 0 && (
            <SectionCard title="Feasibility Table">
              <div className="overflow-x-auto">
                <table className="w-full text-xs font-mono">
                  <thead>
                    <tr className="text-left text-gray-500 uppercase border-b border-gray-100">
                      <th className="pb-2 pr-3">AAA</th>
                      <th className="pb-2 pr-3">MEZ</th>
                      <th className="pb-2 pr-3">Equity</th>
                      <th className="pb-2 pr-3">IRR</th>
                      <th className="pb-2 pr-3">OC</th>
                      <th className="pb-2 pr-3">IC</th>
                      <th className="pb-2 pr-3">OC Pass</th>
                      <th className="pb-2 pr-3">IC Pass</th>
                      <th className="pb-2">Feasible</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-50">
                    {result.feasibility_table.map((row: FeasibilityRow, i) => {
                      const isOptimal =
                        result.optimal &&
                        row.aaa_size_pct === result.optimal.aaa_size_pct;
                      return (
                        <tr
                          key={i}
                          className={isOptimal ? "bg-emerald-50" : "hover:bg-gray-50/50"}
                        >
                          <td className="py-1.5 pr-3">{pct(row.aaa_size_pct)}</td>
                          <td className="py-1.5 pr-3">{pct(row.mez_size_pct)}</td>
                          <td className="py-1.5 pr-3">{pct(row.equity_size_pct)}</td>
                          <td className={`py-1.5 pr-3 font-semibold ${row.equity_irr != null && row.equity_irr < 0 ? "text-red-600" : "text-gray-900"}`}>
                            {pct(row.equity_irr)}
                          </td>
                          <td className="py-1.5 pr-3">{pct(row.oc_cushion_aaa)}</td>
                          <td className="py-1.5 pr-3">{pct(row.ic_cushion_aaa)}</td>
                          <td className="py-1.5 pr-3">{passChip(row.oc_pass)}</td>
                          <td className="py-1.5 pr-3">{passChip(row.ic_pass)}</td>
                          <td className="py-1.5">
                            {row.feasible ? (
                              <Badge variant="success">
                                {isOptimal ? "optimal" : "yes"}
                              </Badge>
                            ) : (
                              <Badge variant="danger">no</Badge>
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
        </>
      )}
    </div>
  );
}
