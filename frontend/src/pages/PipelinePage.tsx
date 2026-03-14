import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { runPipeline, type PipelineResult, type PipelineStages } from "../api/pipeline";
import { SectionCard } from "../components/SectionCard";
import { Button } from "../components/ui/Button";
import { Badge } from "../components/ui/Badge";
import { RegistryMultiSelect, resolveSelectedDeals } from "../components/RegistryMultiSelect";
import { useToast } from "../components/ui/Toast";
import { sampleDeals } from "../lib/sampleDeals";
import {
  Database, Code, Zap, ChevronDown, ChevronRight,
  Activity, BarChart3, FileText, CheckCircle2, XCircle, Clock
} from "lucide-react";

// ─── Helpers ──────────────────────────────────────────────────────────────────

function pct(v: number | null | undefined, dec = 1) {
  if (v == null) return "—";
  return `${(v * 100).toFixed(dec)}%`;
}

function StageStatus({ ok, skipped }: { ok: boolean | null; skipped?: boolean }) {
  if (skipped) return <span className="text-xs text-gray-400 flex items-center gap-1"><Clock size={11} /> skipped</span>;
  if (ok) return <span className="text-xs text-emerald-600 flex items-center gap-1"><CheckCircle2 size={11} /> done</span>;
  return <span className="text-xs text-red-500 flex items-center gap-1"><XCircle size={11} /> failed</span>;
}

// ─── Stage panels ─────────────────────────────────────────────────────────────

function AnalyticsPanel({ data }: { data: Record<string, unknown> }) {
  const scenarios = (data.scenarios as Record<string, unknown>[]) ?? [];
  return (
    <div className="space-y-3">
      {scenarios.map((s: Record<string, unknown>, i) => {
        const out = s.outputs as Record<string, unknown> ?? {};
        return (
          <div key={i} className="flex items-center gap-6 text-sm bg-gray-50 rounded-lg px-4 py-3">
            <div className="w-32 font-medium text-gray-700 shrink-0">{String(s.name ?? s.scenario_type ?? `Scenario ${i+1}`)}</div>
            <div className="flex gap-6 text-xs font-mono">
              <span>IRR: <strong>{pct(out.equity_irr as number)}</strong></span>
              <span>OC: <strong>{pct(out.oc_cushion_aaa as number)}</strong></span>
              <span>WAC: <strong>{pct(out.wac as number)}</strong></span>
            </div>
          </div>
        );
      })}
      {scenarios.length === 0 && (
        <p className="text-sm text-gray-400">No scenario data available.</p>
      )}
    </div>
  );
}

function OptimizerPanel({ data }: { data: Record<string, unknown> }) {
  const optimal = data.optimal as Record<string, unknown> | null;
  const feasible = (data.feasible_count as number) ?? 0;
  const tested = (data.candidates_tested as number) ?? 0;
  if (!optimal) {
    return <p className="text-sm text-amber-600">{String(data.infeasible_reason ?? "No feasible structure found.")}</p>;
  }
  return (
    <div className="grid grid-cols-2 gap-4">
      <div className="space-y-2">
        {[
          ["AAA Size", pct(optimal.aaa_size_pct as number)],
          ["MEZ Size", pct(optimal.mez_size_pct as number)],
          ["Equity", pct(optimal.equity_size_pct as number)],
        ].map(([label, val]) => (
          <div key={label} className="flex justify-between text-sm">
            <span className="text-gray-500">{label}</span>
            <span className="font-mono font-semibold">{val}</span>
          </div>
        ))}
      </div>
      <div className="space-y-2">
        {[
          ["Equity IRR", pct(optimal.equity_irr as number)],
          ["OC Cushion", pct(optimal.oc_cushion_aaa as number)],
          [`Feasible / Tested`, `${feasible} / ${tested}`],
        ].map(([label, val]) => (
          <div key={label} className="flex justify-between text-sm">
            <span className="text-gray-500">{label}</span>
            <span className="font-mono font-semibold">{val}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function BenchmarkPanel({ data }: { data: Record<string, unknown> }) {
  const pos = String(data.overall_position ?? "mixed");
  const COLOR: Record<string, string> = {
    strong: "text-emerald-700 bg-emerald-50",
    median: "text-blue-700 bg-blue-50",
    weak: "text-red-700 bg-red-50",
    mixed: "text-amber-700 bg-amber-50",
  };
  const metrics = (data.metric_scores as Record<string, unknown>[]) ?? [];
  return (
    <div className="space-y-3">
      <div className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-semibold ${COLOR[pos] ?? COLOR.mixed}`}>
        {pos.toUpperCase()} — {String(data.overall_label ?? "")}
      </div>
      <div className="grid grid-cols-2 gap-x-8 gap-y-1.5">
        {metrics.filter((m) => m.vs_median !== "n/a").map((m) => (
          <div key={String(m.metric)} className="flex items-center justify-between text-xs">
            <span className="text-gray-600">{String(m.label)}</span>
            <Badge variant={m.vs_median === "above" ? "success" : m.vs_median === "below" ? "danger" : "default"}>
              {String(m.vs_median)}
            </Badge>
          </div>
        ))}
      </div>
    </div>
  );
}

function DraftPanel({ data }: { data: Record<string, unknown> }) {
  const content = String(data.content ?? data.summary ?? data.draft_content ?? "");
  return (
    <pre className="text-xs font-mono text-gray-700 whitespace-pre-wrap bg-gray-50 rounded p-4 max-h-64 overflow-y-auto border border-gray-100 leading-relaxed">
      {content || "No draft content available."}
    </pre>
  );
}

// ─── Collapsible stage card ───────────────────────────────────────────────────

const STAGE_META = {
  analytics:  { label: "Analytics",          icon: Activity,  desc: "4-scenario suite (base, stress, CDR shock, spread shock)" },
  optimizer:  { label: "Tranche Optimizer",  icon: Zap,       desc: "AAA size sweep — max equity IRR within OC/IC floors" },
  benchmark:  { label: "Benchmark",          icon: BarChart3, desc: "Percentile comparison vs historical CLO cohort" },
  draft:      { label: "Investor Summary",   icon: FileText,  desc: "AI-drafted investor summary [demo]" },
} as const;

function StageCard({
  stageKey,
  stageData,
  defaultOpen,
}: {
  stageKey: keyof typeof STAGE_META;
  stageData: Record<string, unknown> | undefined;
  defaultOpen: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const meta = STAGE_META[stageKey];
  const Icon = meta.icon;
  const exists = !!stageData;
  const hasError = stageData?.error;

  return (
    <div className="border border-gray-100 rounded-xl overflow-hidden">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center gap-4 px-5 py-3.5 hover:bg-gray-50 transition-colors text-left"
      >
        <Icon size={16} className={exists && !hasError ? "text-blue-500" : "text-gray-300"} />
        <div className="flex-1">
          <p className="text-sm font-semibold text-gray-900">{meta.label}</p>
          <p className="text-xs text-gray-400">{meta.desc}</p>
        </div>
        <StageStatus ok={exists && !hasError} skipped={!exists} />
        {open ? <ChevronDown size={14} className="text-gray-400" /> : <ChevronRight size={14} className="text-gray-400" />}
      </button>

      {open && exists && (
        <div className="px-5 pb-4 pt-1 border-t border-gray-50">
          {hasError != null && <p className="text-sm text-red-500">{String(hasError)}</p>}
          {!hasError && stageKey === "analytics"  && <AnalyticsPanel  data={stageData} />}
          {!hasError && stageKey === "optimizer"  && <OptimizerPanel  data={stageData} />}
          {!hasError && stageKey === "benchmark"  && <BenchmarkPanel  data={stageData} />}
          {!hasError && stageKey === "draft"      && <DraftPanel      data={stageData} />}
        </div>
      )}
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export function PipelinePage() {
  const toast = useToast();
  const [mode, setMode] = useState<"registry" | "json">("registry");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [json, setJson] = useState(() => JSON.stringify(sampleDeals.usBSL, null, 2));
  const [parseError, setParseError] = useState<string | null>(null);
  const [runOptimizer, setRunOptimizer] = useState(true);
  const [runBenchmark, setRunBenchmark] = useState(true);
  const [runDraft, setRunDraft] = useState(true);

  const mutation = useMutation({
    mutationFn: (dealInput: Record<string, unknown>) =>
      runPipeline(dealInput, { run_optimizer: runOptimizer, run_benchmark: runBenchmark, run_draft: runDraft }),
    onSuccess: (data) => {
      const stagesDone = Object.values(data.stages).filter(Boolean).length;
      toast.success(`Pipeline complete — ${stagesDone} stage${stagesDone !== 1 ? "s" : ""} finished`);
    },
    onError: (err) => toast.error(`Pipeline failed: ${String(err)}`),
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

  const result: PipelineResult | undefined = mutation.data;
  const stages: PipelineStages = result?.stages ?? {};

  // Extract overall grade from analytics base scenario
  const baseScenario = (stages.analytics?.scenarios as Record<string, unknown>[])?.[0];
  const baseOutputs = baseScenario?.outputs as Record<string, unknown> ?? {};

  return (
    <div className="space-y-6 max-w-5xl">
      <div>
        <h1 className="text-xl font-bold text-gray-900">Full Pipeline</h1>
        <p className="text-sm text-gray-500 mt-1">
          One-click end-to-end analysis — analytics → optimizer → benchmark → draft
        </p>
      </div>

      {/* Input + options */}
      <div className="grid grid-cols-2 gap-5">
        <SectionCard
          title="Deal Input"
          action={
            <div className="flex items-center gap-1 bg-gray-100 rounded-md p-0.5">
              <button onClick={() => setMode("registry")} className={`px-2.5 py-1 rounded text-xs font-medium transition-colors flex items-center gap-1 ${mode === "registry" ? "bg-white shadow text-gray-900" : "text-gray-500 hover:text-gray-700"}`}>
                <Database size={11} /> Registry
              </button>
              <button onClick={() => setMode("json")} className={`px-2.5 py-1 rounded text-xs font-medium transition-colors flex items-center gap-1 ${mode === "json" ? "bg-white shadow text-gray-900" : "text-gray-500 hover:text-gray-700"}`}>
                <Code size={11} /> JSON
              </button>
            </div>
          }
        >
          {mode === "registry" ? (
            <RegistryMultiSelect selected={selected} onChange={setSelected} maxSelect={1} />
          ) : (
            <textarea className="w-full h-52 font-mono text-xs border border-gray-200 rounded p-3 resize-y focus:outline-none focus:ring-2 focus:ring-gray-900" value={json} onChange={(e) => setJson(e.target.value)} spellCheck={false} />
          )}
          {parseError && <p className="text-red-600 text-sm mt-2">{parseError}</p>}
        </SectionCard>

        <SectionCard title="Pipeline Stages">
          <div className="space-y-3">
            {([
              ["run_analytics", "Analytics (always on)", true, null],
              ["run_optimizer", "Tranche Optimizer", runOptimizer, setRunOptimizer],
              ["run_benchmark", "Benchmark Comparison", runBenchmark, setRunBenchmark],
              ["run_draft",    "Investor Summary Draft", runDraft, setRunDraft],
            ] as [string, string, boolean, ((v: boolean) => void) | null][]).map(([key, label, checked, setter]) => (
              <label key={key} className={`flex items-center gap-3 p-2.5 rounded-lg border cursor-pointer ${checked ? "border-blue-200 bg-blue-50" : "border-gray-100"} ${!setter ? "opacity-60 cursor-default" : ""}`}>
                <input
                  type="checkbox"
                  checked={checked}
                  disabled={!setter}
                  onChange={(e) => setter?.(e.target.checked)}
                  className="rounded"
                />
                <span className="text-sm text-gray-700">{label}</span>
              </label>
            ))}
          </div>
          <p className="text-xs text-gray-400 mt-3">
            Each stage feeds the next. Analytics runs first and is always required.
          </p>
        </SectionCard>
      </div>

      {/* Run button */}
      <Button onClick={handleRun} disabled={mutation.isPending} size="lg">
        <Zap size={15} className="mr-2" />
        {mutation.isPending ? "Running pipeline…" : "Run Full Pipeline"}
      </Button>

      {/* Loading stage tracker */}
      {mutation.isPending && (
        <div className="flex items-center gap-2 text-sm text-gray-500">
          <span className="h-2 w-2 rounded-full bg-blue-500 animate-pulse" />
          Running — this may take 10–15 seconds (mock engine)…
        </div>
      )}

      {/* Results */}
      {result && (
        <>
          {/* Hero summary */}
          <div className="bg-gray-900 text-white rounded-xl p-5">
            <div className="flex items-start justify-between mb-3">
              <div>
                <p className="text-xs text-gray-400 uppercase tracking-wide font-semibold mb-1">Pipeline Complete</p>
                <p className="text-lg font-bold">{result.deal_id}</p>
                <p className="text-xs text-gray-400 mt-0.5 font-mono">{result.pipeline_id}</p>
              </div>
              <div className="text-right">
                {baseOutputs.equity_irr != null && (
                  <p className="text-2xl font-black text-emerald-400">
                    {pct(baseOutputs.equity_irr as number)} IRR
                  </p>
                )}
                {result.is_mock && <Badge variant="warning" className="mt-1">mock engine</Badge>}
              </div>
            </div>
            {result.pipeline_summary && (
              <p className="text-sm text-gray-300 leading-relaxed border-t border-gray-700 pt-3 mt-3 font-mono text-xs whitespace-pre-wrap max-h-32 overflow-y-auto">
                {result.pipeline_summary}
              </p>
            )}
          </div>

          {/* Stage panels */}
          <div className="space-y-3">
            {(["analytics", "optimizer", "benchmark", "draft"] as const).map((key, i) => (
              <StageCard
                key={key}
                stageKey={key}
                stageData={stages[key] as Record<string, unknown> | undefined}
                defaultOpen={i === 0}
              />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
