import { client } from "./client";

export interface KRI {
  name: string;       // backend field
  metric?: string;    // alias (unused by backend)
  label: string;
  value: number | null;
  format?: string;    // "pct" | "pct+" | "score" | "int"
  status: string;
  formatted_value?: string;
}

export interface HealthCheckResult {
  health_id: string;
  deal_id: string;
  checked_at: string;
  overall_grade: string | null;
  overall_score: number | null;
  score_summary: Record<string, unknown>;
  stress_summary: Record<string, unknown>;
  watchlist_summary: Record<string, unknown>;
  key_risk_indicators: KRI[];
  action_items: string[];
  health_report: string;
  audit_events_count: number;
  is_mock: boolean;
  error?: string;
}

export async function runHealthCheck(dealInput: Record<string, unknown>): Promise<HealthCheckResult> {
  const { data } = await client.post<HealthCheckResult>("/health-check", {
    deal_input: dealInput,
    actor: "frontend",
  });
  return data;
}
