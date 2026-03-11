import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { compareDeals, runScenarioSimple, type FieldChange } from "../api/analytics";
import { SectionCard } from "../components/SectionCard";
import { Button } from "../components/ui/Button";
import { Badge } from "../components/ui/Badge";
import { DealPickerModal } from "../components/DealPickerModal";
import { sampleDeals } from "../lib/sampleDeals";
import { ArrowUp, ArrowDown, GitCompare, Database } from "lucide-react";

// ─── Helpers ─────────────────────────────────────────────────────────────────

function fmtVal(v: unknown, unit?: string): string {
  if (v == null) return "—";
  const n = Number(v);
  if (isNaN(n)) return String(v);
  if (unit === "pct") return `${(n * 100).toFixed(2)}%`;
  if (unit === "currency") return n >= 1e6 ? `$${(n / 1e6).toFixed(1)}M` : `$${n.toLocaleString()}`;
  return n.toFixed(n % 1 === 0 ? 0 : 3);
}

function DeltaChip({ change }: { change: FieldChange }) {
  const { direction, delta, delta_pct, unit } = change;
  if (direction === "changed") return <Badge variant="info">changed</Badge>;
  if (delta == null) return null;

  const positive = direction === "up";
  const color = positive ? "text-green-600" : "text-red-600";
  const Icon = positive ? ArrowUp : ArrowDown;
  const label =
    unit === "pct"
      ? `${positive ? "+" : ""}${(delta * 100).toFixed(2)}pp`
      : delta_pct != null
      ? `${positive ? "+" : ""}${delta_pct.toFixed(1)}%`
      : `${positive ? "+" : ""}${delta.toFixed(3)}`;

  return (
    <span className={`inline-flex items-center gap-0.5 text-xs font-mono ${color}`}>
      <Icon size={11} />
      {label}
    </span>
  );
}

function ChangeTable({
  title,
  changes,
}: {
  title: string;
  changes: FieldChange[];
}) {
  if (changes.length === 0) return null;
  return (
    <div>
      <h4 className="text-xs font-semibold uppercase tracking-wide text-gray-500 mb-2">
        {title}
      </h4>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-xs uppercase text-gray-400 border-b border-gray-100">
            <th className="pb-1.5 pr-4">Field</th>
            <th className="pb-1.5 pr-4">V1</th>
            <th className="pb-1.5 pr-4">V2</th>
            <th className="pb-1.5">Change</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-50">
          {changes.map((c) => (
            <tr key={c.field}>
              <td className="py-2 pr-4 font-medium text-gray-700">{c.label ?? c.field}</td>
              <td className="py-2 pr-4 font-mono text-gray-500">{fmtVal(c.v1, c.unit)}</td>
              <td className="py-2 pr-4 font-mono text-gray-900 font-medium">
                {fmtVal(c.v2, c.unit)}
              </td>
              <td className="py-2">
                <DeltaChip change={c} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

const SAMPLES = ["usBSL", "euCLO", "mmCLO"] as const;

function sampleLabel(k: string) {
  return k === "usBSL" ? "US BSL" : k === "euCLO" ? "EU CLO" : "MM CLO";
}

export function ComparisonPage() {
  const [json1, setJson1] = useState(() => JSON.stringify(sampleDeals.usBSL, null, 2));
  const [json2, setJson2] = useState(() => JSON.stringify(sampleDeals.euCLO, null, 2));
  const [runScenarios, setRunScenarios] = useState(true);
  const [parseError, setParseError] = useState<string | null>(null);
  const [picker, setPicker] = useState<"v1" | "v2" | null>(null);

  const mutation = useMutation({
    mutationFn: async () => {
      const d1 = JSON.parse(json1);
      const d2 = JSON.parse(json2);
      let r1: Record<string, unknown> | undefined;
      let r2: Record<string, unknown> | undefined;
      if (runScenarios) {
        const [sc1, sc2] = await Promise.all([
          runScenarioSimple(d1, "Baseline", "base"),
          runScenarioSimple(d2, "Baseline", "base"),
        ]);
        r1 = (sc1.scenario_result as Record<string, unknown>) ?? undefined;
        r2 = (sc2.scenario_result as Record<string, unknown>) ?? undefined;
      }
      return compareDeals(d1, d2, r1, r2);
    },
    onError: () => {},
  });

  function handleCompare() {
    setParseError(null);
    try {
      JSON.parse(json1);
      JSON.parse(json2);
    } catch {
      setParseError("One or both deal JSONs are invalid.");
      return;
    }
    mutation.mutate();
  }

  const result = mutation.data;
  const dc = result?.deal_comparison;
  const sc = result?.scenario_comparison;

  return (
    <div className="space-y-6 max-w-6xl">
      <div>
        <h1 className="text-xl font-bold text-gray-900">Scenario Comparison</h1>
        <p className="text-sm text-gray-500 mt-1">
          Compare two deals side-by-side — collateral changes, scenario output deltas, and summary
        </p>
      </div>

      {picker && (
        <DealPickerModal
          title={`Pick ${picker === "v1" ? "Deal V1" : "Deal V2"}`}
          onSelect={(input) => {
            if (picker === "v1") setJson1(JSON.stringify(input, null, 2));
            else setJson2(JSON.stringify(input, null, 2));
          }}
          onClose={() => setPicker(null)}
        />
      )}

      {/* Two JSON panels */}
      <div className="grid grid-cols-2 gap-5">
        {([
          { label: "Deal V1", json: json1, setJson: setJson1, pickerId: "v1" as const },
          { label: "Deal V2", json: json2, setJson: setJson2, pickerId: "v2" as const },
        ] as const).map(({ label, json, setJson, pickerId }) => (
          <SectionCard
            key={label}
            title={label}
            action={
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setPicker(pickerId)}
                  className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-900 border border-gray-200 rounded px-2 py-1 hover:border-gray-400 transition-colors"
                >
                  <Database size={12} /> Registry
                </button>
                <div className="flex gap-1">
                  {SAMPLES.map((k) => (
                    <button
                      key={k}
                      onClick={() => setJson(JSON.stringify(sampleDeals[k], null, 2))}
                      className="text-xs text-gray-400 hover:text-gray-700 px-1.5 py-0.5 border border-gray-200 rounded"
                    >
                      {sampleLabel(k)}
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
        ))}
      </div>

      {/* Controls */}
      <div className="flex items-center gap-4">
        <Button onClick={handleCompare} disabled={mutation.isPending} size="lg">
          <GitCompare size={15} className="mr-2" />
          {mutation.isPending ? "Comparing…" : "Compare"}
        </Button>
        <label className="flex items-center gap-2 text-sm text-gray-600 cursor-pointer">
          <input
            type="checkbox"
            checked={runScenarios}
            onChange={(e) => setRunScenarios(e.target.checked)}
            className="rounded"
          />
          Also run &amp; compare baseline scenarios
        </label>
        {parseError && <p className="text-red-600 text-sm">{parseError}</p>}
        {mutation.isError && (
          <p className="text-red-600 text-sm">Error: {String(mutation.error)}</p>
        )}
      </div>

      {/* Results */}
      {result && (
        <>
          {/* Deal comparison */}
          {dc && (
            <SectionCard
              title={`Deal Changes — ${dc.change_count} field(s) changed`}
              action={
                <span className="text-xs text-gray-400 font-mono">
                  {dc.v1_id} → {dc.v2_id}
                </span>
              }
            >
              <div className="space-y-5">
                <ChangeTable title="Collateral" changes={dc.collateral_changes} />
                <ChangeTable title="Assumptions" changes={dc.assumption_changes} />
                <ChangeTable title="Metadata" changes={dc.metadata_changes} />
                {dc.change_count === 0 && (
                  <p className="text-sm text-gray-400">No differences detected.</p>
                )}
                {dc.caveat && (
                  <p className="text-xs text-amber-600 bg-amber-50 px-3 py-2 rounded">
                    {dc.caveat}
                  </p>
                )}
              </div>
            </SectionCard>
          )}

          {/* Scenario output comparison */}
          {sc && (
            <SectionCard
              title="Scenario Output Changes"
              action={
                <span className="text-xs text-gray-400 font-mono">
                  {sc.v1_run_id.slice(-8)} → {sc.v2_run_id.slice(-8)}
                </span>
              }
            >
              <div className="space-y-5">
                <ChangeTable title="Parameters" changes={sc.param_changes} />
                <ChangeTable title="Outputs" changes={sc.output_changes} />
                {sc.output_changes.length === 0 && sc.param_changes.length === 0 && (
                  <p className="text-sm text-gray-400">No output differences detected.</p>
                )}
              </div>
            </SectionCard>
          )}

          {/* Summary */}
          {result.summary && (
            <SectionCard title="Analysis Summary">
              <pre className="text-sm text-gray-700 whitespace-pre-wrap font-sans leading-relaxed">
                {result.summary}
              </pre>
            </SectionCard>
          )}
        </>
      )}
    </div>
  );
}
