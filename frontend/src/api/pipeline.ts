import { client } from "./client";

export interface PipelineStages {
  analytics?: Record<string, unknown>;
  optimizer?: Record<string, unknown>;
  benchmark?: Record<string, unknown>;
  draft?: Record<string, unknown>;
}

export interface PipelineResult {
  pipeline_id: string;
  deal_id: string;
  run_at: string;
  is_mock: boolean;
  stages: PipelineStages;
  pipeline_summary: string;
  audit_events_count: number;
  error?: string;
}

export interface PipelineOptions {
  run_optimizer?: boolean;
  run_benchmark?: boolean;
  run_draft?: boolean;
  vintage?: number;
  region?: string;
  optimizer_kwargs?: Record<string, unknown>;
}

export async function runPipeline(
  dealInput: Record<string, unknown>,
  options: PipelineOptions = {}
): Promise<PipelineResult> {
  const { data } = await client.post<PipelineResult>("/pipeline", {
    deal_input: dealInput,
    actor: "frontend",
    run_sensitivity: false,
    ...options,
  });
  return data;
}

export async function rerunDealPipeline(
  dealId: string,
  options: PipelineOptions = {}
): Promise<PipelineResult> {
  const { data } = await client.post<PipelineResult>(`/deals/${dealId}/pipeline`, {
    actor: "frontend",
    ...options,
  });
  return data;
}
