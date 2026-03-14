import { client } from "./client";

export interface GateResult {
  gate: string;
  passed: boolean;
  message: string;
  severity?: "error" | "warning" | "info";
}

export interface PublishCheckResult {
  overall: "pass" | "pass_with_notes" | "fail";
  gates: GateResult[];
  blocking_issues: string[];
  warnings: string[];
  checked_at: string;
  _mock?: string;
}

export async function runPublishCheck(
  draft: Record<string, unknown>,
  approval_record?: Record<string, unknown> | null,
  target_channel = "internal"
): Promise<PublishCheckResult> {
  const { data } = await client.post("/publish-check", {
    draft,
    approval_record: approval_record ?? null,
    target_channel,
  });
  return data;
}
