import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import { scorePortfolio, type PortfolioScoringResult } from "../api/portfolio";
import { GradeCircle } from "../components/GradeCircle";
import { SectionCard } from "../components/SectionCard";
import { Button } from "../components/ui/Button";
import { Badge } from "../components/ui/Badge";
import { RegistryMultiSelect, resolveSelectedDeals } from "../components/RegistryMultiSelect";
import { sampleDealsArray } from "../lib/sampleDeals";
import { Database, Code } from "lucide-react";

const GRADE_COLORS: Record<string, string> = {
  A: "#10b981",
  B: "#3b82f6",
  C: "#f59e0b",
  D: "#f97316",
  F: "#ef4444",
};

export function PortfolioScoringPage() {
  const [mode, setMode] = useState<"registry" | "json">("registry");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [json, setJson] = useState(() => JSON.stringify(sampleDealsArray, null, 2));
  const [parseError, setParseError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: (inputs: Record<string, unknown>[]) => scorePortfolio(inputs),
  });

  async function handleRun() {
    setParseError(null);
    try {
      let inputs: Record<string, unknown>[];
      if (mode === "registry") {
        if (selected.size === 0) {
          setParseError("Select at least one deal from the registry.");
          return;
        }
        inputs = await resolveSelectedDeals(Array.from(selected));
      } else {
        const parsed = JSON.parse(json);
        if (!Array.isArray(parsed)) throw new Error("Input must be a JSON array of deals");
        inputs = parsed;
      }
      mutation.mutate(inputs);
    } catch (e) {
      setParseError(String(e));
    }
  }

  const result: PortfolioScoringResult | undefined = mutation.data;

  const gradeDist = result?.grade_distribution
    ? Object.entries(result.grade_distribution).map(([grade, count]) => ({
        grade,
        count: Number(count),
      }))
    : [];

  return (
    <div className="space-y-6 max-w-5xl">
      <div>
        <h1 className="text-xl font-bold text-gray-900">Portfolio Scoring</h1>
        <p className="text-sm text-gray-500 mt-1">
          Score all deals in your portfolio and compare grades
        </p>
      </div>

      {/* Input */}
      <SectionCard
        title="Deal Selection"
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
          <RegistryMultiSelect selected={selected} onChange={setSelected} />
        ) : (
          <textarea
            className="w-full h-52 font-mono text-xs border border-gray-200 rounded p-3 resize-y focus:outline-none focus:ring-2 focus:ring-gray-900"
            value={json}
            onChange={(e) => setJson(e.target.value)}
            spellCheck={false}
          />
        )}

        {parseError && <p className="text-red-600 text-sm mt-2">{parseError}</p>}
        <div className="mt-3">
          <Button onClick={handleRun} disabled={mutation.isPending}>
            {mutation.isPending
              ? "Scoring…"
              : mode === "registry"
              ? `Score ${selected.size} Deal${selected.size !== 1 ? "s" : ""}`
              : "Score Portfolio"}
          </Button>
        </div>
      </SectionCard>

      {mutation.isError && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-700 text-sm">
          Error: {String(mutation.error)}
        </div>
      )}

      {result && (
        <>
          {/* Summary Stats */}
          <div className="grid grid-cols-3 gap-4">
            {[
              ["Deals", result.deal_count],
              ["Avg Score", result.portfolio_avg_score?.toFixed(1) ?? "—"],
              ["Scored", result.scored_count],
            ].map(([label, val]) => (
              <SectionCard key={String(label)}>
                <p className="text-xs text-gray-500 mb-1">{String(label)}</p>
                <p className="text-2xl font-black text-gray-900">{String(val)}</p>
              </SectionCard>
            ))}
          </div>

          {/* Grade Distribution */}
          {gradeDist.length > 0 && (
            <SectionCard title="Grade Distribution">
              <ResponsiveContainer width="100%" height={160}>
                <BarChart
                  data={gradeDist}
                  layout="vertical"
                  margin={{ top: 0, right: 20, bottom: 0, left: 30 }}
                >
                  <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11 }} />
                  <YAxis type="category" dataKey="grade" tick={{ fontSize: 12, fontWeight: 600 }} />
                  <Tooltip />
                  <Bar dataKey="count" radius={[0, 4, 4, 0]}>
                    {gradeDist.map((entry) => (
                      <Cell
                        key={entry.grade}
                        fill={GRADE_COLORS[entry.grade[0]] ?? "#6b7280"}
                      />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </SectionCard>
          )}

          {/* Score Ranking */}
          <SectionCard title="Score Ranking">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs uppercase text-gray-500 border-b border-gray-100">
                  <th className="pb-2 pr-3">Rank</th>
                  <th className="pb-2 pr-3">Deal</th>
                  <th className="pb-2 pr-3">Score</th>
                  <th className="pb-2">Grade</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {result.score_ranking.map((row) => (
                  <tr key={row.deal_id}>
                    <td className="py-2 pr-3 text-gray-500 font-mono">#{row.rank}</td>
                    <td className="py-2 pr-3 font-medium text-gray-800">{row.name}</td>
                    <td className="py-2 pr-3">
                      <div className="flex items-center gap-2">
                        <div className="h-2 rounded-full bg-gray-100 flex-1 max-w-24">
                          <div
                            className="h-2 rounded-full bg-blue-500"
                            style={{ width: `${row.composite_score ?? 0}%` }}
                          />
                        </div>
                        <span className="font-mono text-xs text-gray-700">
                          {row.composite_score?.toFixed(1) ?? "—"}
                        </span>
                      </div>
                    </td>
                    <td className="py-2">
                      <GradeCircle grade={row.grade ?? "?"} size="sm" />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </SectionCard>

          {/* Needs Attention */}
          {result.needs_attention.length > 0 && (
            <SectionCard title="Needs Attention">
              <div className="space-y-3">
                {result.needs_attention.map((item, i) => (
                  <div
                    key={i}
                    className="flex items-start gap-3 p-3 bg-red-50 rounded-lg border border-red-100"
                  >
                    <div className="flex-1">
                      <p className="font-medium text-gray-900 text-sm">{item.name}</p>
                      <p className="text-xs text-gray-600 mt-0.5">{item.reasons?.[0] ?? ""}</p>
                    </div>
                    <div className="flex flex-wrap gap-1">
                      {(item.reasons ?? []).slice(1).map((r: string, j: number) => (
                        <Badge key={j} variant="danger">
                          {r}
                        </Badge>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </SectionCard>
          )}
        </>
      )}
    </div>
  );
}
