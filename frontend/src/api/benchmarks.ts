import { client } from "./client";

export interface MetricScore {
  metric: string;
  label: string;
  deal_value: number | null;
  p25: number | null;
  p50: number | null;
  p75: number | null;
  percentile_rank: string;
  vs_median: string;
  higher_is_better: boolean | null;
  fmt: string;
  assessment: string;
}

export interface BenchmarkResult {
  deal_id: string;
  comparison_id: string;
  compared_at: string;
  vintage: number;
  region: string;
  overall_position: "strong" | "median" | "weak" | "mixed";
  overall_label: string;
  above_median_count: number;
  below_median_count: number;
  metric_scores: MetricScore[];
  comparison_report: string;
  is_mock: boolean;
  error?: string;
}

export async function compareToBenchmarks(
  dealInput: Record<string, unknown>,
  scenarioOutputs: Record<string, unknown>,
  options: { vintage?: number; region?: string; asset_class?: string } = {}
): Promise<BenchmarkResult> {
  const { data } = await client.post<BenchmarkResult>("/benchmarks/compare", {
    deal_input: dealInput,
    scenario_outputs: scenarioOutputs,
    actor: "frontend",
    ...options,
  });
  return data;
}
