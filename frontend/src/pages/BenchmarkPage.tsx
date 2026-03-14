import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { runHealthCheck } from "../api/health";
import { compareToBenchmarks, type MetricScore, type BenchmarkResult } from "../api/benchmarks";
import { SectionCard } from "../components/SectionCard";
import { Button } from "../components/ui/Button";
import { Badge } from "../components/ui/Badge";
import { RegistryMultiSelect, resolveSelectedDeals } from "../components/RegistryMultiSelect";
import { useToast } from "../components/ui/Toast";
import { sampleDeals } from "../lib/sampleDeals";
import { Database, Code, BarChart3 } from "lucide-react";

// ─── Helpers ──────────────────────────────────────────────────────────────────

const POSITION_STYLES: Record<string, { border: string; bg: string; text: string; label: string }> = {
  strong: { border: "border-emerald-200", bg: "bg-emerald-50", text: "text-emerald-800", label: "Strong" },
  median: { border: "border-blue-200",    bg: "bg-blue-50",    text: "text-blue-800",    label: "Median"  },
  weak:   { border: "border-red-200",     bg: "bg-red-50",     text: "text-red-800",     label: "Weak"    },
  mixed:  { border: "border-amber-200",   bg: "bg-amber-50",   text: "text-amber-800",   label: "Mixed"   },
};

const VS_BADGE: Record<string, "success" | "default" | "danger"> = {
  above: "success",
  at:    "default",
  below: "danger",
};

function fmtVal(v: number | null, fmt: string): string {
  if (v == null) return "—";
  if (fmt === "pct") return `${(v * 100).toFixed(2)}%`;
  if (fmt === "score") return v.toFixed(1);
  if (fmt === "int") return String(Math.round(v));
  return v.toFixed(3);
}

// ─── Percentile bar ───────────────────────────────────────────────────────────
// Renders p25─p75 band as a bar with a dot for the deal's actual value.

function PercentileBar({ row }: { row: MetricScore }) {
  if (row.p25 == null || row.p50 == null || row.p75 == null || row.deal_value == null) {
    return <span className="text-xs text-gray-300">no data</span>;
  }

  const lo = row.p25;
  const hi = row.p75;
  const range = hi - lo || 0.0001;

  // Clamp deal_value within [lo - range, hi + range] for display purposes
  const displayMin = lo - range * 0.5;
  const displayMax = hi + range * 0.5;
  const displayRange = displayMax - displayMin;

  const bandLeft  = ((lo - displayMin) / displayRange) * 100;
  const bandWidth = ((hi - lo) / displayRange) * 100;
  const dotLeft   = Math.max(2, Math.min(98, ((row.deal_value - displayMin) / displayRange) * 100));

  const dotColor =
    row.vs_median === "above"
      ? "bg-emerald-500"
      : row.vs_median === "below"
      ? "bg-red-500"
      : "bg-blue-500";

  return (
    <div className="flex items-center gap-2 w-full">
      {/* Labels */}
      <span className="text-xs font-mono text-gray-400 w-14 text-right shrink-0">
        {fmtVal(lo, row.fmt)}
      </span>
      {/* Track */}
      <div className="relative flex-1 h-3 bg-gray-100 rounded-full">
        {/* P25–P75 band */}
        <div
          className="absolute inset-y-0 bg-blue-100 rounded-full"
          style={{ left: `${bandLeft}%`, width: `${bandWidth}%` }}
        />
        {/* P50 tick */}
        <div
          className="absolute top-0 bottom-0 w-0.5 bg-blue-300"
          style={{ left: `${((row.p50 - displayMin) / displayRange) * 100}%` }}
        />
        {/* Deal dot */}
        <div
          className={`absolute top-1/2 -translate-y-1/2 h-3 w-3 rounded-full shadow ${dotColor} border-2 border-white`}
          style={{ left: `${dotLeft}%`, transform: "translate(-50%, -50%)" }}
          title={`Deal: ${fmtVal(row.deal_value, row.fmt)}`}
        />
      </div>
      <span className="text-xs font-mono text-gray-400 w-14 shrink-0">
        {fmtVal(hi, row.fmt)}
      </span>
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

const CURRENT_YEAR = new Date().getFullYear();

export function BenchmarkPage() {
  const toast = useToast();

  const [mode, setMode] = useState<"registry" | "json">("registry");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [json, setJson] = useState(() => JSON.stringify(sampleDeals.usBSL, null, 2));
  const [parseError, setParseError] = useState<string | null>(null);

  // Benchmark options
  const [vintage, setVintage] = useState(String(CURRENT_YEAR - 1));
  const [region, setRegion] = useState("US");
  const [assetClass, setAssetClass] = useState("broadly_syndicated_loans");

  const mutation = useMutation({
    mutationFn: async (dealInput: Record<string, unknown>) => {
      // Step 1: run health check to get scenario outputs
      const health = await runHealthCheck(dealInput);
      const healthAny = health as unknown as Record<string, unknown>;
      const scenarioOutputs = (healthAny.outputs as Record<string, unknown>) ?? {};
      // Merge KRIs as flat outputs for the benchmark
      const kris = (healthAny.key_risk_indicators as Array<{name: string; value: number}>) ?? [];
      const flat: Record<string, unknown> = { ...scenarioOutputs };
      kris.forEach((k) => { flat[k.name] = k.value; });

      // Step 2: benchmark compare
      return compareToBenchmarks(dealInput, flat, {
        vintage: parseInt(vintage) || undefined,
        region: region || undefined,
        asset_class: assetClass || undefined,
      });
    },
    onSuccess: (data) => {
      const style = POSITION_STYLES[data.overall_position] ?? POSITION_STYLES.mixed;
      toast.success(`Benchmark complete — ${style.label} vs ${data.vintage} ${data.region} cohort`);
    },
    onError: (err) => toast.error(`Benchmark failed: ${String(err)}`),
  });

  async function handleRun() {
    setParseError(null);
    try {
      let dealInput: Record<string, unknown>;
      if (mode === "registry") {
        if (selected.size === 0) { setParseError("Select a deal from the registry."); return; }
        const inputs = await resolveSelectedDeals(Array.from(selected));
        dealInput = inputs[0];
      } else {
        const parsed = JSON.parse(json);
        dealInput = Array.isArray(parsed) ? parsed[0] : parsed;
      }
      mutation.mutate(dealInput);
    } catch (e) {
      setParseError(String(e));
    }
  }

  const result: BenchmarkResult | undefined = mutation.data;
  const pos = result ? (POSITION_STYLES[result.overall_position] ?? POSITION_STYLES.mixed) : null;

  return (
    <div className="space-y-6 max-w-5xl">
      <div>
        <h1 className="text-xl font-bold text-gray-900">Benchmark Comparison</h1>
        <p className="text-sm text-gray-500 mt-1">
          Score a deal's metrics against historical CLO percentile bands (p25 / p50 / p75)
        </p>
      </div>

      {/* Input + options grid */}
      <div className="grid grid-cols-2 gap-5">
        {/* Deal input */}
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
            <RegistryMultiSelect selected={selected} onChange={setSelected} maxSelect={1} />
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

        {/* Benchmark options */}
        <SectionCard title="Cohort Options">
          <div className="space-y-4">
            <div>
              <label className="text-xs text-gray-500 block mb-1">Vintage Year</label>
              <input
                type="number"
                className="w-full text-sm border border-gray-200 rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-gray-900"
                value={vintage}
                onChange={(e) => setVintage(e.target.value)}
                min={2015}
                max={CURRENT_YEAR}
              />
            </div>
            <div>
              <label className="text-xs text-gray-500 block mb-1">Region</label>
              <select
                className="w-full text-sm border border-gray-200 rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-gray-900"
                value={region}
                onChange={(e) => setRegion(e.target.value)}
              >
                <option value="US">US</option>
                <option value="EU">EU</option>
                <option value="APAC">APAC</option>
              </select>
            </div>
            <div>
              <label className="text-xs text-gray-500 block mb-1">Asset Class</label>
              <select
                className="w-full text-sm border border-gray-200 rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-gray-900"
                value={assetClass}
                onChange={(e) => setAssetClass(e.target.value)}
              >
                <option value="broadly_syndicated_loans">Broadly Syndicated Loans</option>
                <option value="middle_market">Middle Market</option>
              </select>
            </div>
            <p className="text-xs text-gray-400">
              Step 1: runs a health check to get scenario outputs, then compares against the selected cohort's percentile bands.
            </p>
          </div>
        </SectionCard>
      </div>

      <Button onClick={handleRun} disabled={mutation.isPending} size="lg">
        <BarChart3 size={15} className="mr-2" />
        {mutation.isPending ? "Comparing…" : "Run Benchmark"}
      </Button>

      {/* ── Results ── */}
      {result && pos && (
        <>
          {/* Overall position hero */}
          <div className={`rounded-xl border p-5 ${pos.border} ${pos.bg}`}>
            <div className="flex items-start justify-between">
              <div>
                <p className={`text-xs font-semibold uppercase tracking-wide ${pos.text} mb-1`}>
                  Overall Position
                </p>
                <p className={`text-3xl font-black ${pos.text}`}>{pos.label}</p>
                <p className={`text-sm mt-1 ${pos.text} opacity-80`}>{result.overall_label}</p>
              </div>
              <div className="text-right space-y-1">
                <p className={`text-sm font-semibold ${pos.text}`}>
                  {result.above_median_count} above median
                </p>
                <p className={`text-sm ${pos.text} opacity-70`}>
                  {result.below_median_count} below median
                </p>
                <p className={`text-xs ${pos.text} opacity-50 mt-2`}>
                  {result.vintage} {result.region} cohort
                  {result.is_mock && " · mock data"}
                </p>
              </div>
            </div>
          </div>

          {/* Metric scores table */}
          <SectionCard title="Metric Scores vs Percentile Bands">
            <p className="text-xs text-gray-400 mb-4">
              Bar shows p25–p75 interquartile range · vertical tick = median · dot = this deal
            </p>
            <div className="space-y-4">
              {result.metric_scores.map((row) => (
                <div key={row.metric}>
                  <div className="flex items-center justify-between mb-1">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-gray-700">{row.label}</span>
                      {row.vs_median !== "n/a" && (
                        <Badge variant={VS_BADGE[row.vs_median] ?? "default"}>
                          {row.vs_median} median
                        </Badge>
                      )}
                    </div>
                    <span className="text-sm font-mono font-bold text-gray-900">
                      {fmtVal(row.deal_value, row.fmt)}
                    </span>
                  </div>
                  <PercentileBar row={row} />
                  {row.assessment && row.assessment !== "no data" && (
                    <p className="text-xs text-gray-400 mt-0.5 ml-16">{row.assessment}</p>
                  )}
                </div>
              ))}
            </div>
          </SectionCard>

          {/* Full text report */}
          {result.comparison_report && (
            <SectionCard title="Comparison Report">
              <pre className="text-xs text-gray-700 whitespace-pre-wrap font-mono leading-relaxed bg-gray-50 rounded p-4 max-h-72 overflow-y-auto">
                {result.comparison_report}
              </pre>
            </SectionCard>
          )}
        </>
      )}
    </div>
  );
}
