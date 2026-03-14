import { client } from "./client";

export interface DealAnalysisResult {
  deal_id?: string;
  deal_name?: string;
  metrics: Record<string, number | string | null>;
  risk_flags: string[];
  summary?: string;
}

export interface PortfolioAnalysisResult {
  analysis_id: string;
  deal_count: number;
  results: DealAnalysisResult[];
  portfolio_metrics: Record<string, number | string | null>;
  risk_summary: string;
  recommendations: string[];
  _mock?: string;
}

export async function analyzePortfolio(
  deal_inputs: Record<string, unknown>[],
  metrics?: string[]
): Promise<PortfolioAnalysisResult> {
  const { data } = await client.post("/portfolio/analyze", { deal_inputs, metrics });
  return data;
}

export interface SingleAnalysisResult {
  analysis_id: string;
  scenarios: Record<string, unknown>[];
  sensitivity?: Record<string, unknown>;
  summary: string;
  _mock?: string;
}

export async function analyzeDeal(
  deal_input: Record<string, unknown>,
  run_sensitivity = true
): Promise<SingleAnalysisResult> {
  const { data } = await client.post("/analyze", { deal_input, run_sensitivity });
  return data;
}
