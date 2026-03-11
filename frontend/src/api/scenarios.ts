import { client } from "./client";

export interface ScenarioTemplate {
  template_id: string;
  name: string;
  description: string;
  scenario_type: string;
  tags: string[];
  parameters: Record<string, unknown>;
}

export interface BatchScenarioResult {
  deal_id: string;
  scenarios_run: number;
  results: Record<string, unknown>[];
  comparison_table: {
    scenario_name: string;
    scenario_type: string;
    equity_irr?: number;
    oc_cushion_aaa?: number;
    wac?: number;
    status?: string;
    [key: string]: unknown;
  }[];
  audit_events_count: number;
  is_mock: boolean;
  error?: string;
}

export async function getScenarioTemplates(): Promise<ScenarioTemplate[]> {
  const { data } = await client.get<{ total: number; templates: ScenarioTemplate[] }>(
    "/scenarios/templates"
  );
  return data.templates;
}

export async function runBatchScenarios(
  dealInput: Record<string, unknown>,
  scenarios: { name: string; type: string; parameters: Record<string, unknown> }[]
): Promise<BatchScenarioResult> {
  const { data } = await client.post<BatchScenarioResult>("/scenarios/batch", {
    deal_input: dealInput,
    scenarios,
    actor: "frontend",
  });
  return data;
}
