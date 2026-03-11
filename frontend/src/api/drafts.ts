import { client } from "./client";

export interface DraftDoc {
  draft_id?: string;
  deal_id?: string;
  doc_type?: string;
  content?: string;
  approved?: boolean;
  approval_record?: ApprovalRecord | null;
  [key: string]: unknown;
}

export interface ApprovalRecord {
  approval_id?: string;
  draft_id?: string;
  status?: string;
  requested_by?: string;
  approver?: string;
  channel?: string;
  notes?: string;
  rejection_reason?: string;
  created_at?: string;
  decided_at?: string;
  expires_at?: string;
  [key: string]: unknown;
}

export interface DraftResponse {
  draft: DraftDoc | null;
  draft_markdown: string | null;
  approved: boolean;
  requires_approval: boolean;
  audit_events_count: number;
  error?: string | null;
}

export async function generateInvestorSummary(
  dealInput: Record<string, unknown>,
  scenarioResult: Record<string, unknown>,
  scenarioRequest?: Record<string, unknown>,
  actor = "frontend"
): Promise<DraftResponse> {
  const res = await client.post("/drafts/investor-summary", {
    deal_input: dealInput,
    scenario_result: scenarioResult,
    scenario_request: scenarioRequest ?? null,
    actor,
  });
  return res.data;
}

export async function generateIcMemo(
  dealInput: Record<string, unknown>,
  scenarioResult: Record<string, unknown>,
  scenarioRequest?: Record<string, unknown>,
  actor = "frontend"
): Promise<DraftResponse> {
  const res = await client.post("/drafts/ic-memo", {
    deal_input: dealInput,
    scenario_result: scenarioResult,
    scenario_request: scenarioRequest ?? null,
    actor,
  });
  return res.data;
}

export async function requestApproval(
  draft: DraftDoc,
  requestedBy: string,
  channel = "internal"
): Promise<ApprovalRecord> {
  const res = await client.post("/approvals/request", {
    draft,
    requested_by: requestedBy,
    channel,
  });
  return res.data;
}

export async function approveRecord(
  approvalRecord: ApprovalRecord,
  approver: string,
  notes?: string
): Promise<ApprovalRecord> {
  const res = await client.post("/approvals/approve", {
    approval_record: approvalRecord,
    approver,
    notes: notes ?? null,
  });
  return res.data;
}

export async function rejectRecord(
  approvalRecord: ApprovalRecord,
  approver: string,
  rejectionReason: string
): Promise<ApprovalRecord> {
  const res = await client.post("/approvals/reject", {
    approval_record: approvalRecord,
    approver,
    rejection_reason: rejectionReason,
  });
  return res.data;
}

export async function applyApproval(
  draft: DraftDoc,
  approvalRecord: ApprovalRecord
): Promise<DraftDoc> {
  const res = await client.post("/approvals/apply", {
    draft,
    approval_record: approvalRecord,
  });
  return res.data;
}
