import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { listDeals, getDeal } from "../api/deals";
import { runHealthCheck, type HealthCheckResult } from "../api/health";
import { SectionCard } from "../components/SectionCard";
import { Button } from "../components/ui/Button";
import { GradeCircle } from "../components/GradeCircle";
import { KRIBadge } from "../components/KRIBadge";
import { useToast } from "../components/ui/Toast";
import { ArrowUp, ArrowDown, Minus, GitCompare } from "lucide-react";

// ─── Types ────────────────────────────────────────────────────────────────────

interface KRIRow {
  key: string;
  label: string;
  format: "pct" | "score" | "raw";
}

const KRI_ROWS: KRIRow[] = [
  { key: "equity_irr",        label: "Equity IRR",        format: "pct"   },
  { key: "oc_cushion_aaa",    label: "OC Cushion AAA",    format: "pct"   },
  { key: "composite_score",   label: "Composite Score",   format: "score" },
  { key: "irr_drawdown",      label: "IRR Drawdown",      format: "pct"   },
  { key: "ccc_bucket",        label: "CCC Bucket",        format: "pct"   },
  { key: "diversity_score",   label: "Diversity Score",   format: "score" },
  { key: "wac",               label: "WAC",               format: "pct"   },
  { key: "wal",               label: "WAL",               format: "raw"   },
];

// ─── Helpers ──────────────────────────────────────────────────────────────────

function fmtKRI(v: unknown, format: KRIRow["format"]): string {
  if (v == null) return "—";
  const n = Number(v);
  if (isNaN(n)) return String(v);
  if (format === "pct") return `${(n * 100).toFixed(2)}%`;
  if (format === "score") return n.toFixed(1);
  return n.toFixed(2);
}

function getDelta(a: unknown, b: unknown): { diff: number; pct: number } | null {
  const na = Number(a), nb = Number(b);
  if (isNaN(na) || isNaN(nb)) return null;
  const diff = nb - na;
  const pct = na !== 0 ? (diff / Math.abs(na)) * 100 : 0;
  return { diff, pct };
}

function DeltaCell({ a, b, format }: { a: unknown; b: unknown; format: KRIRow["format"] }) {
  const delta = getDelta(a, b);
  if (!delta) return <span className="text-gray-300 text-xs">—</span>;
  const { diff, pct } = delta;
  if (Math.abs(diff) < 0.0001) {
    return <span className="flex items-center gap-0.5 text-xs text-gray-400"><Minus size={11} />same</span>;
  }
  const up = diff > 0;
  const Icon = up ? ArrowUp : ArrowDown;
  const color = up ? "text-green-600" : "text-red-500";
  const fmtDiff = format === "pct"
    ? `${Math.abs(diff * 100).toFixed(2)}pp`
    : Math.abs(diff).toFixed(2);
  return (
    <span className={`flex items-center gap-0.5 text-xs font-semibold ${color}`}>
      <Icon size={11} />
      {fmtDiff}
      <span className="text-gray-400 font-normal ml-1">({pct >= 0 ? "+" : ""}{pct.toFixed(1)}%)</span>
    </span>
  );
}

function getKRIValue(result: HealthCheckResult, key: string): unknown {
  const match = result.key_risk_indicators.find((k) => k.name === key);
  return match?.value ?? null;
}

function getKRIStatus(result: HealthCheckResult, key: string): "ok" | "warn" | "critical" {
  const match = result.key_risk_indicators.find((k) => k.name === key);
  return (match?.status as "ok" | "warn" | "critical") ?? "ok";
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export function KRIComparisonPage() {
  const toast = useToast();
  const [dealA, setDealA] = useState("");
  const [dealB, setDealB] = useState("");
  const [resultA, setResultA] = useState<HealthCheckResult | null>(null);
  const [resultB, setResultB] = useState<HealthCheckResult | null>(null);

  const dealsQuery = useQuery({ queryKey: ["deals"], queryFn: listDeals, staleTime: 30_000 });
  const deals = dealsQuery.data ?? [];

  const compareMut = useMutation({
    mutationFn: async () => {
      if (!dealA || !dealB) throw new Error("Select both deals");
      if (dealA === dealB) throw new Error("Select two different deals");
      const [detailA, detailB] = await Promise.all([getDeal(dealA), getDeal(dealB)]);
      const [hA, hB] = await Promise.all([
        runHealthCheck(detailA.deal_input as Record<string, unknown>),
        runHealthCheck(detailB.deal_input as Record<string, unknown>),
      ]);
      return { a: hA, b: hB };
    },
    onSuccess: ({ a, b }) => {
      setResultA(a);
      setResultB(b);
      toast.success("Health checks complete — KRI comparison ready.");
    },
    onError: (e) => toast.error(String(e)),
  });

  const nameA = deals.find((d) => d.deal_id === dealA)?.name ?? "Deal A";
  const nameB = deals.find((d) => d.deal_id === dealB)?.name ?? "Deal B";

  return (
    <div className="space-y-6 max-w-5xl">
      <div>
        <h1 className="text-xl font-bold text-gray-900">KRI Comparison</h1>
        <p className="text-sm text-gray-500 mt-1">
          Side-by-side health check comparison across two registered deals
        </p>
      </div>

      {/* Deal picker */}
      <SectionCard title="Select Deals to Compare">
        <div className="grid grid-cols-2 gap-4">
          {(["A", "B"] as const).map((side) => {
            const val = side === "A" ? dealA : dealB;
            const other = side === "A" ? dealB : dealA;
            return (
              <div key={side}>
                <label className="text-xs text-gray-500 font-medium mb-1 block">Deal {side}</label>
                <select
                  className="w-full border border-gray-200 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-gray-900"
                  value={val}
                  onChange={(e) => side === "A" ? setDealA(e.target.value) : setDealB(e.target.value)}
                >
                  <option value="">— Select deal —</option>
                  {deals.map((d) => (
                    <option key={d.deal_id} value={d.deal_id} disabled={d.deal_id === other}>
                      {d.name}
                    </option>
                  ))}
                </select>
              </div>
            );
          })}
        </div>
        {deals.length === 0 && (
          <p className="text-sm text-amber-600 mt-2">No deals registered. Add deals in the Deal Registry first.</p>
        )}
        <div className="mt-4">
          <Button
            onClick={() => compareMut.mutate()}
            disabled={compareMut.isPending || !dealA || !dealB}
          >
            <GitCompare size={13} className="mr-1.5" />
            {compareMut.isPending ? "Running health checks…" : "Compare KRIs"}
          </Button>
        </div>
      </SectionCard>

      {/* Comparison results */}
      {resultA && resultB && (
        <>
          {/* Grade header */}
          <div className="grid grid-cols-3 gap-4">
            <SectionCard>
              <p className="text-xs text-gray-400 mb-2">{nameA}</p>
              <div className="flex items-center gap-3">
                <GradeCircle grade={resultA.overall_grade as string} size="md" />
                <div>
                  <p className="text-2xl font-black text-gray-900">{(resultA.overall_score as number).toFixed(0)}</p>
                  <p className="text-xs text-gray-400">/ 100</p>
                </div>
              </div>
            </SectionCard>

            <SectionCard>
              <p className="text-xs text-gray-500 text-center mb-2">Score Delta</p>
              <div className="text-center">
                <DeltaCell
                  a={resultA.overall_score}
                  b={resultB.overall_score}
                  format="score"
                />
                <p className="text-xs text-gray-400 mt-1">
                  {nameB} vs {nameA}
                </p>
              </div>
            </SectionCard>

            <SectionCard>
              <p className="text-xs text-gray-400 mb-2">{nameB}</p>
              <div className="flex items-center gap-3">
                <GradeCircle grade={resultB.overall_grade as string} size="md" />
                <div>
                  <p className="text-2xl font-black text-gray-900">{(resultB.overall_score as number).toFixed(0)}</p>
                  <p className="text-xs text-gray-400">/ 100</p>
                </div>
              </div>
            </SectionCard>
          </div>

          {/* KRI table */}
          <SectionCard title="KRI Side-by-Side">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs uppercase text-gray-500 border-b border-gray-100">
                    <th className="pb-2 pr-4">Metric</th>
                    <th className="pb-2 pr-4">{nameA}</th>
                    <th className="pb-2 pr-4">Delta (B−A)</th>
                    <th className="pb-2">{nameB}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  {KRI_ROWS.map((row) => {
                    const vA = getKRIValue(resultA, row.key);
                    const vB = getKRIValue(resultB, row.key);
                    const stA = getKRIStatus(resultA, row.key);
                    const stB = getKRIStatus(resultB, row.key);
                    return (
                      <tr key={row.key} className="hover:bg-gray-50">
                        <td className="py-2.5 pr-4 font-medium text-gray-700">{row.label}</td>
                        <td className="py-2.5 pr-4">
                          <div className="flex items-center gap-2">
                            <KRIBadge status={stA} />
                            <span className="font-mono text-gray-900">{fmtKRI(vA, row.format)}</span>
                          </div>
                        </td>
                        <td className="py-2.5 pr-4">
                          <DeltaCell a={vA} b={vB} format={row.format} />
                        </td>
                        <td className="py-2.5">
                          <div className="flex items-center gap-2">
                            <KRIBadge status={stB} />
                            <span className="font-mono text-gray-900">{fmtKRI(vB, row.format)}</span>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </SectionCard>

          {/* Action items */}
          <div className="grid grid-cols-2 gap-5">
            {[
              { name: nameA, result: resultA },
              { name: nameB, result: resultB },
            ].map(({ name, result }) => {
              const items = (result.action_items ?? []) as string[];
              if (items.length === 0) return null;
              return (
                <SectionCard key={name} title={`${name} — Action Items`}>
                  <ol className="space-y-1.5">
                    {items.map((item, i) => (
                      <li key={i} className="flex gap-2 text-xs text-gray-700">
                        <span className="text-blue-500 font-bold shrink-0">{i + 1}.</span>
                        {item}
                      </li>
                    ))}
                  </ol>
                </SectionCard>
              );
            })}
          </div>

          {/* Grades breakdown */}
          <div className="grid grid-cols-2 gap-5">
            {[
              { name: nameA, result: resultA },
              { name: nameB, result: resultB },
            ].map(({ name, result }) => {
              const dims = result.score_summary?.dimension_scores as Record<string, number> | undefined;
              if (!dims) return null;
              return (
                <SectionCard key={name} title={`${name} — Dimensions`}>
                  <div className="space-y-2">
                    {Object.entries(dims).map(([dim, score]) => (
                      <div key={dim}>
                        <div className="flex justify-between text-xs mb-0.5">
                          <span className="text-gray-600">{dim.replace(/_/g, " ")}</span>
                          <span className="font-semibold text-gray-700">{score.toFixed(0)}</span>
                        </div>
                        <div className="h-1.5 bg-gray-100 rounded-full">
                          <div
                            className={`h-1.5 rounded-full ${
                              score >= 70 ? "bg-green-400" : score >= 50 ? "bg-amber-400" : "bg-red-400"
                            }`}
                            style={{ width: `${score}%` }}
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                </SectionCard>
              );
            })}
          </div>
        </>
      )}

      {/* Empty */}
      {!resultA && !compareMut.isPending && (
        <div className="text-center py-20 text-gray-400">
          <GitCompare size={48} className="mx-auto mb-4 opacity-20" />
          <p className="text-sm font-medium">Select two deals and compare</p>
          <p className="text-xs mt-1">Runs live health checks and shows KRI deltas side-by-side</p>
        </div>
      )}
    </div>
  );
}
