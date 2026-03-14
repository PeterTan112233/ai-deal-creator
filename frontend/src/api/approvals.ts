import { client } from "./client";

export interface ApprovalRecord {
  approval_id: string;
  draft_id: string;
  status: "pending" | "approved" | "rejected";
  requested_by: string;
  approver?: string;
  notes?: string;
  rejection_reason?: string;
  requested_at: string;
  decided_at?: string;
  expires_at?: string;
}

export interface RequestApprovalResult {
  approval_record: ApprovalRecord;
  message: string;
}

export interface ApprovalActionResult {
  approval_record: ApprovalRecord;
  message: string;
}

export interface ApplyApprovalResult {
  draft: Record<string, unknown>;
  message: string;
}

export async function requestApproval(
  draft: Record<string, unknown>,
  requested_by: string,
  channel = "internal"
): Promise<RequestApprovalResult> {
  const { data } = await client.post("/approvals/request", { draft, requested_by, channel });
  return data;
}

export async function approveApproval(
  approval_record: ApprovalRecord,
  approver: string,
  notes?: string
): Promise<ApprovalActionResult> {
  const { data } = await client.post("/approvals/approve", { approval_record, approver, notes });
  return data;
}

export async function rejectApproval(
  approval_record: ApprovalRecord,
  approver: string,
  rejection_reason: string
): Promise<ApprovalActionResult> {
  const { data } = await client.post("/approvals/reject", { approval_record, approver, rejection_reason });
  return data;
}

export async function applyApproval(
  draft: Record<string, unknown>,
  approval_record: ApprovalRecord
): Promise<ApplyApprovalResult> {
  const { data } = await client.post("/approvals/apply", { draft, approval_record });
  return data;
}
