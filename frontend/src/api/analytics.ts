import { client } from "./client";

// ─── Compare ─────────────────────────────────────────────────────────────────

export interface FieldChange {
  field: string;
  label: string;
  unit?: string;
  v1: unknown;
  v2: unknown;
  delta?: number;
  delta_pct?: number;
  direction?: "up" | "down" | "changed";
}

export interface DealComparison {
  v1_id: string;
  v2_id: string;
  collateral_changes: FieldChange[];
  assumption_changes: FieldChange[];
  metadata_changes: FieldChange[];
  change_count: number;
  caveat?: string;
}

export interface ScenarioComparison {
  v1_run_id: string;
  v2_run_id: string;
  v1_scenario_id: string;
  v2_scenario_id: string;
  param_changes: FieldChange[];
  output_changes: FieldChange[];
}

export interface CompareResponse {
  deal_comparison: DealComparison | null;
  scenario_comparison: ScenarioComparison | null;
  summary: string | null;
  audit_events_count: number;
  error?: string | null;
}

export async function compareDeals(
  v1Deal: Record<string, unknown>,
  v2Deal: Record<string, unknown>,
  v1Result?: Record<string, unknown>,
  v2Result?: Record<string, unknown>,
  actor = "frontend"
): Promise<CompareResponse> {
  const res = await client.post("/compare", {
    v1_deal: v1Deal,
    v2_deal: v2Deal,
    v1_result: v1Result ?? null,
    v2_result: v2Result ?? null,
    actor,
  });
  return res.data;
}

export async function runScenarioSimple(
  dealInput: Record<string, unknown>,
  name = "Baseline",
  type = "base"
): Promise<Record<string, unknown>> {
  const res = await client.post("/scenarios", {
    deal_input: dealInput,
    scenario_name: name,
    scenario_type: type,
    actor: "frontend",
  });
  return res.data;
}

// ─── Sensitivity ──────────────────────────────────────────────────────────────

export interface SensitivityPoint {
  parameter_value: number;
  outputs: {
    equity_irr?: number;
    oc_cushion_aaa?: number;
    scenario_npv?: number;
    wac?: number;
    [key: string]: number | undefined;
  };
  run_id: string;
  status: string;
  error?: string | null;
}

export interface SensitivityResponse {
  deal_id: string;
  parameter: string;
  values_tested: number[];
  series: SensitivityPoint[];
  breakeven: {
    equity_irr_zero: number | null;
    scenario_npv_zero: number | null;
  };
  is_mock: boolean;
  error?: string | null;
}

export async function runSensitivity(
  dealInput: Record<string, unknown>,
  parameter: string,
  values: number[],
  baseParameters?: Record<string, unknown>,
  actor = "frontend"
): Promise<SensitivityResponse> {
  const res = await client.post("/scenarios/sensitivity", {
    deal_input: dealInput,
    parameter,
    values,
    base_parameters: baseParameters ?? null,
    actor,
  });
  return res.data;
}
