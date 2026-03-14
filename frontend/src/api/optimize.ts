import { client } from "./client";

export interface FeasibilityRow {
  aaa_size_pct: number;
  mez_size_pct: number;
  equity_size_pct: number;
  equity_irr: number | null;
  oc_cushion_aaa: number | null;
  ic_cushion_aaa: number | null;
  wac: number | null;
  equity_wal: number | null;
  feasible: boolean;
  oc_pass: boolean;
  ic_pass: boolean;
  status: string;
}

export interface FrontierPoint {
  aaa_size_pct: number;
  equity_irr: number;
}

export interface OptimizeResponse {
  deal_id: string;
  optimization_id: string;
  optimised_at: string;
  is_mock: boolean;
  optimal: FeasibilityRow | null;
  feasibility_table: FeasibilityRow[];
  frontier: FrontierPoint[];
  constraints: {
    oc_floor: number;
    ic_floor: number;
    aaa_min: number;
    aaa_max: number;
    mez_size_pct: number;
  };
  infeasible_reason: string | null;
  candidates_tested: number;
  feasible_count: number;
  audit_events_count: number;
  error?: string;
}

export interface OptimizeParams {
  aaa_min?: number;   // decimal, e.g. 0.55
  aaa_max?: number;
  aaa_step?: number;
  mez_size_pct?: number;
  mez_coupon?: string;
  aaa_coupon?: string;
  oc_floor?: number;
  ic_floor?: number;
}

export async function optimizeStructure(
  dealInput: Record<string, unknown>,
  params: OptimizeParams = {}
): Promise<OptimizeResponse> {
  const { data } = await client.post<OptimizeResponse>("/optimize", {
    deal_input: dealInput,
    actor: "frontend",
    ...params,
  });
  return data;
}
