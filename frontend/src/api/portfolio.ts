import { client } from "./client";

export interface PortfolioScoringResult {
  scorecard_id: string;
  run_at: string;
  deal_count: number;
  scored_count: number;
  deals: Record<string, unknown>[];
  score_ranking: {
    rank: number;
    deal_id: string;
    name: string;
    composite_score: number | null;
    grade: string | null;
  }[];
  grade_distribution: Record<string, number>;
  portfolio_avg_score: number | null;
  needs_attention: {
    deal_id: string;
    name: string;
    grade: string | null;
    score: number | null;
    reasons: string[];
  }[];
  scorecard_report: string;
  audit_events_count: number;
  is_mock: boolean;
  error?: string;
}

export async function scorePortfolio(
  dealInputs: Record<string, unknown>[]
): Promise<PortfolioScoringResult> {
  const { data } = await client.post<PortfolioScoringResult>("/portfolio/score", {
    deal_inputs: dealInputs,
    actor: "frontend",
  });
  return data;
}
