import { client } from "./client";

export interface ScenarioTemplate {
  template_id: string;
  name: string;
  description: string;
  scenario_type: "base" | "stress" | "regulatory";
  tags: string[];
  parameters: Record<string, number>;
}

export interface SuiteScenarioResult {
  template_id: string;
  name: string;
  scenario_type: string;
  outputs: Record<string, unknown>;
  status: "completed" | "failed";
  error?: string;
}

export interface TemplateSuiteResult {
  suite_id: string;
  deal_name?: string;
  scenario_count: number;
  results: SuiteScenarioResult[];
  summary: string;
  _mock?: string;
}

export async function getTemplates(): Promise<{ total: number; templates: ScenarioTemplate[] }> {
  const { data } = await client.get("/scenarios/templates");
  return data;
}

export async function runTemplateSuite(
  deal_input: Record<string, unknown>,
  template_ids?: string[],
  scenario_type?: string
): Promise<TemplateSuiteResult> {
  const { data } = await client.post("/scenarios/template-suite", {
    deal_input,
    template_ids: template_ids ?? null,
    scenario_type: scenario_type ?? null,
  });
  return data;
}
