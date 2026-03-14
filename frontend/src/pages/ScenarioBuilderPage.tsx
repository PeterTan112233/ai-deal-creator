import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import { getTemplates, type ScenarioTemplate } from "../api/templateSuite";
import { client } from "../api/client";
import { listDeals, getDeal } from "../api/deals";
import { SectionCard } from "../components/SectionCard";
import { Button } from "../components/ui/Button";
import { Badge } from "../components/ui/Badge";
import { useToast } from "../components/ui/Toast";
import { ExportMenu } from "../components/ui/ExportMenu";
import { sampleDeals } from "../lib/sampleDeals";
import { Database, Code, Sliders } from "lucide-react";

// ─── Types ────────────────────────────────────────────────────────────────────

interface ScenarioResult {
  run_id: string;
  template_id: string;
  scenario_name: string;
  outputs: Record<string, unknown>;
  parameters_used: Record<string, number>;
  summary?: string;
  _mock?: string;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function pct(v: unknown): string {
  if (v == null) return "—";
  const n = Number(v);
  return isNaN(n) ? String(v) : `${(n * 100).toFixed(2)}%`;
}

function typeVariant(t: string): "info" | "warning" | "default" {
  if (t === "base") return "info";
  if (t === "stress") return "warning";
  return "default";
}

// ─── Slider param ─────────────────────────────────────────────────────────────

interface ParamSliderProps {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  fmt: (v: number) => string;
  onChange: (v: number) => void;
  overridden: boolean;
}

function ParamSlider({ label, value, min, max, step, fmt, onChange, overridden }: ParamSliderProps) {
  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <label className="text-xs text-gray-600 font-medium">{label}</label>
        <div className="flex items-center gap-2">
          <span className={`text-xs font-mono font-semibold ${overridden ? "text-blue-600" : "text-gray-700"}`}>
            {fmt(value)}
          </span>
          {overridden && (
            <Badge variant="info">overridden</Badge>
          )}
        </div>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full accent-blue-600"
      />
      <div className="flex justify-between text-xs text-gray-300 mt-0.5">
        <span>{fmt(min)}</span>
        <span>{fmt(max)}</span>
      </div>
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export function ScenarioBuilderPage() {
  const toast = useToast();

  // Deal input
  const [dealMode, setDealMode] = useState<"registry" | "json">("registry");
  const [selectedDeal, setSelectedDeal] = useState("");
  const [json, setJson] = useState(JSON.stringify(sampleDeals.usBSL, null, 2));
  const [jsonErr, setJsonErr] = useState<string | null>(null);

  // Template selection
  const [selectedTemplate, setSelectedTemplate] = useState<ScenarioTemplate | null>(null);

  // Parameter overrides (start from template defaults)
  const [defaultRate, setDefaultRate] = useState(0.03);
  const [recoveryRate, setRecoveryRate] = useState(0.65);
  const [spreadShock, setSpreadShock] = useState(0);

  const [result, setResult] = useState<ScenarioResult | null>(null);

  const dealsQuery = useQuery({ queryKey: ["deals"], queryFn: listDeals, staleTime: 30_000 });
  const templatesQuery = useQuery({ queryKey: ["templates"], queryFn: getTemplates, staleTime: 300_000 });

  const deals = dealsQuery.data ?? [];
  const templates = templatesQuery.data?.templates ?? [];

  function applyTemplate(t: ScenarioTemplate) {
    setSelectedTemplate(t);
    setDefaultRate(t.parameters.default_rate);
    setRecoveryRate(t.parameters.recovery_rate);
    setSpreadShock(t.parameters.spread_shock_bps);
  }

  const overrides: Record<string, number> = {};
  if (selectedTemplate) {
    if (defaultRate !== selectedTemplate.parameters.default_rate) overrides.default_rate = defaultRate;
    if (recoveryRate !== selectedTemplate.parameters.recovery_rate) overrides.recovery_rate = recoveryRate;
    if (spreadShock !== selectedTemplate.parameters.spread_shock_bps) overrides.spread_shock_bps = spreadShock;
  }

  const runMut = useMutation({
    mutationFn: async () => {
      if (!selectedTemplate) throw new Error("Select a template first");
      let deal_input: Record<string, unknown>;
      if (dealMode === "registry") {
        if (!selectedDeal) throw new Error("Select a deal");
        const detail = await getDeal(selectedDeal);
        deal_input = detail.deal_input as Record<string, unknown>;
      } else {
        setJsonErr(null);
        try { deal_input = JSON.parse(json); }
        catch { throw new Error("Invalid JSON"); }
      }
      const { data } = await client.post("/scenarios/from-template", {
        deal_input,
        template_id: selectedTemplate.template_id,
        parameter_overrides: Object.keys(overrides).length > 0 ? overrides : null,
      });
      return data as ScenarioResult;
    },
    onSuccess: (res) => {
      setResult(res);
      toast.success(`Scenario run complete — ${res.scenario_name}.`);
    },
    onError: (e) => {
      setJsonErr(String(e));
      toast.error(String(e));
    },
  });

  const KEY_OUTPUTS = [
    ["Equity IRR", "equity_irr", "pct"],
    ["OC Cushion AAA", "oc_cushion_aaa", "pct"],
    ["WAC", "wac", "pct"],
    ["IRR Drawdown", "irr_drawdown", "pct"],
    ["Diversity Score", "diversity_score", "raw"],
    ["Composite Score", "composite_score", "raw"],
  ] as const;

  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <h1 className="text-xl font-bold text-gray-900">Scenario Builder</h1>
        <p className="text-sm text-gray-500 mt-1">
          Start from a template, tune parameters with sliders, and run a custom scenario
        </p>
      </div>

      {/* Deal input */}
      <SectionCard
        title="Deal"
        action={
          <div className="flex items-center gap-1 bg-gray-100 rounded-md p-0.5">
            <button onClick={() => setDealMode("registry")}
              className={`px-2.5 py-1 rounded text-xs font-medium transition-colors flex items-center gap-1 ${dealMode === "registry" ? "bg-white shadow text-gray-900" : "text-gray-500 hover:text-gray-700"}`}>
              <Database size={11} /> Registry
            </button>
            <button onClick={() => setDealMode("json")}
              className={`px-2.5 py-1 rounded text-xs font-medium transition-colors flex items-center gap-1 ${dealMode === "json" ? "bg-white shadow text-gray-900" : "text-gray-500 hover:text-gray-700"}`}>
              <Code size={11} /> JSON
            </button>
          </div>
        }
      >
        {dealMode === "registry" ? (
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
              className="w-full h-32 font-mono text-xs border border-gray-200 rounded p-3 resize-y focus:outline-none focus:ring-2 focus:ring-gray-900"
              value={json} onChange={(e) => setJson(e.target.value)} spellCheck={false}
            />
            {jsonErr && <p className="text-red-600 text-xs mt-1">{jsonErr}</p>}
          </>
        )}
      </SectionCard>

      {/* Template picker */}
      <SectionCard title="Base Template">
        {templatesQuery.isLoading && <p className="text-sm text-gray-400">Loading…</p>}
        <div className="grid grid-cols-3 gap-2">
          {templates.map((t) => (
            <button
              key={t.template_id}
              onClick={() => applyTemplate(t)}
              className={`text-left p-3 rounded-lg border transition-colors ${
                selectedTemplate?.template_id === t.template_id
                  ? "border-blue-400 bg-blue-50"
                  : "border-gray-100 hover:border-gray-300 hover:bg-gray-50"
              }`}
            >
              <div className="flex items-center gap-1.5 mb-1">
                <p className="text-xs font-semibold text-gray-900">{t.name}</p>
                <Badge variant={typeVariant(t.scenario_type)}>{t.scenario_type}</Badge>
              </div>
              <div className="text-xs text-gray-400 font-mono space-x-2">
                <span>CDR {(t.parameters.default_rate * 100).toFixed(1)}%</span>
                <span>RR {(t.parameters.recovery_rate * 100).toFixed(0)}%</span>
              </div>
            </button>
          ))}
        </div>
      </SectionCard>

      {/* Parameter overrides */}
      {selectedTemplate && (
        <SectionCard
          title="Parameter Overrides"
          action={<Sliders size={14} className="text-gray-400" />}
        >
          <p className="text-xs text-gray-400 mb-4">
            Drag sliders to override template defaults. Unchanged values use the template as-is.
          </p>
          <div className="space-y-5">
            <ParamSlider
              label="Default Rate (CDR)"
              value={defaultRate}
              min={0} max={0.20} step={0.005}
              fmt={(v) => `${(v * 100).toFixed(1)}%`}
              onChange={setDefaultRate}
              overridden={defaultRate !== selectedTemplate.parameters.default_rate}
            />
            <ParamSlider
              label="Recovery Rate"
              value={recoveryRate}
              min={0.20} max={0.90} step={0.01}
              fmt={(v) => `${(v * 100).toFixed(0)}%`}
              onChange={setRecoveryRate}
              overridden={recoveryRate !== selectedTemplate.parameters.recovery_rate}
            />
            <ParamSlider
              label="Spread Shock (bps)"
              value={spreadShock}
              min={0} max={500} step={25}
              fmt={(v) => `${v}bps`}
              onChange={setSpreadShock}
              overridden={spreadShock !== selectedTemplate.parameters.spread_shock_bps}
            />
          </div>
          {Object.keys(overrides).length > 0 && (
            <div className="mt-4 p-3 bg-blue-50 rounded-lg">
              <p className="text-xs text-blue-600 font-semibold mb-1">Active overrides:</p>
              <div className="flex gap-3 flex-wrap">
                {Object.entries(overrides).map(([k, v]) => (
                  <span key={k} className="text-xs font-mono text-blue-700">
                    {k}: {k === "spread_shock_bps" ? `${v}bps` : `${(v * 100).toFixed(1)}%`}
                  </span>
                ))}
              </div>
            </div>
          )}
          <div className="mt-4">
            <Button
              onClick={() => runMut.mutate()}
              disabled={runMut.isPending || (dealMode === "registry" && !selectedDeal)}
            >
              {runMut.isPending ? "Running…" : "Run Custom Scenario"}
            </Button>
            {Object.keys(overrides).length === 0 && (
              <span className="ml-3 text-xs text-gray-400">No overrides — using template defaults</span>
            )}
          </div>
        </SectionCard>
      )}

      {/* Result */}
      {result && (
        <>
          <SectionCard
            title={`Results — ${result.scenario_name}`}
            action={<ExportMenu label="scenario-builder" data={result} />}
          >
            <p className="text-xs font-mono text-gray-400 mb-4">{result.run_id}</p>
            <div className="grid grid-cols-3 gap-3 mb-4">
              {KEY_OUTPUTS.map(([label, key, fmt]) => (
                <div key={key} className="bg-gray-50 rounded-lg p-3">
                  <p className="text-xs text-gray-500 mb-1">{label}</p>
                  <p className="text-xl font-black font-mono text-gray-900">
                    {fmt === "pct" ? pct(result.outputs[key]) : String(result.outputs[key] ?? "—")}
                  </p>
                </div>
              ))}
            </div>
            {/* Parameters used */}
            <div className="border-t border-gray-100 pt-3">
              <p className="text-xs text-gray-400 font-semibold mb-2">Parameters Used</p>
              <div className="flex gap-4 flex-wrap">
                {Object.entries(result.parameters_used ?? {}).map(([k, v]) => (
                  <div key={k} className="text-xs">
                    <span className="text-gray-400">{k.replace(/_/g, " ")}: </span>
                    <span className="font-mono font-semibold text-gray-700">
                      {k === "spread_shock_bps" ? `${v}bps` : `${(v * 100).toFixed(1)}%`}
                    </span>
                    {overrides[k] != null && (
                      <Badge variant="info" className="ml-1">custom</Badge>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </SectionCard>
          {result.summary && (
            <SectionCard title="Summary">
              <p className="text-sm text-gray-700 leading-relaxed">{result.summary}</p>
            </SectionCard>
          )}
        </>
      )}

      {/* Empty */}
      {!result && !runMut.isPending && (
        <div className="text-center py-20 text-gray-400">
          <Sliders size={48} className="mx-auto mb-4 opacity-20" />
          <p className="text-sm font-medium">Choose a template and tune parameters</p>
          <p className="text-xs mt-1">Override CDR, recovery rate, or spread shock before running</p>
        </div>
      )}
    </div>
  );
}
