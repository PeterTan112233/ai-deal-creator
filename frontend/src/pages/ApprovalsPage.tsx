import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import {
  requestApproval, approveApproval, rejectApproval, applyApproval,
  type ApprovalRecord,
} from "../api/approvals";
import { SectionCard } from "../components/SectionCard";
import { Button } from "../components/ui/Button";
import { Badge } from "../components/ui/Badge";
import { useToast } from "../components/ui/Toast";
import { CheckCircle2, XCircle, Clock, ShieldCheck, ChevronDown, ChevronUp } from "lucide-react";

// ─── Types ────────────────────────────────────────────────────────────────────

type Stage = "input" | "pending" | "decided" | "applied";

function statusBadge(status: string) {
  if (status === "approved") return <Badge variant="success">approved</Badge>;
  if (status === "rejected") return <Badge variant="danger">rejected</Badge>;
  return <Badge variant="warning">pending</Badge>;
}

function fmtTs(iso?: string) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export function ApprovalsPage() {
  const toast = useToast();

  // Draft JSON
  const [draftJson, setDraftJson] = useState(JSON.stringify({
    draft_id: "draft-001",
    deal_name: "Sample CLO 2024-1",
    draft_type: "investor_summary",
    content: "This is a sample investor summary draft for approval.",
    approved: false,
  }, null, 2));
  const [draftParseErr, setDraftParseErr] = useState<string | null>(null);
  const [showDraftJson, setShowDraftJson] = useState(false);

  // State machine
  const [stage, setStage] = useState<Stage>("input");
  const [approvalRecord, setApprovalRecord] = useState<ApprovalRecord | null>(null);
  const [appliedDraft, setAppliedDraft] = useState<Record<string, unknown> | null>(null);

  // Fields
  const [requestedBy, setRequestedBy] = useState("analyst@clo.internal");
  const [approver, setApprover] = useState("senior.reviewer@clo.internal");
  const [notes, setNotes] = useState("");
  const [rejectReason, setRejectReason] = useState("");
  const [showRejectForm, setShowRejectForm] = useState(false);

  function parseDraft(): Record<string, unknown> | null {
    setDraftParseErr(null);
    try {
      return JSON.parse(draftJson);
    } catch {
      setDraftParseErr("Invalid JSON");
      return null;
    }
  }

  // Mutations
  const requestMut = useMutation({
    mutationFn: async () => {
      const draft = parseDraft();
      if (!draft) throw new Error("Invalid JSON");
      return requestApproval(draft, requestedBy);
    },
    onSuccess: (res) => {
      setApprovalRecord(res.approval_record);
      setStage("pending");
      toast.success("Approval requested.");
    },
    onError: (e) => toast.error(String(e)),
  });

  const approveMut = useMutation({
    mutationFn: async () => {
      if (!approvalRecord) throw new Error("No approval record");
      return approveApproval(approvalRecord, approver, notes || undefined);
    },
    onSuccess: (res) => {
      setApprovalRecord(res.approval_record);
      setStage("decided");
      toast.success("Approved.");
    },
    onError: (e) => toast.error(String(e)),
  });

  const rejectMut = useMutation({
    mutationFn: async () => {
      if (!approvalRecord || !rejectReason.trim()) throw new Error("Rejection reason required");
      return rejectApproval(approvalRecord, approver, rejectReason);
    },
    onSuccess: (res) => {
      setApprovalRecord(res.approval_record);
      setStage("decided");
      toast.info("Rejected.");
    },
    onError: (e) => toast.error(String(e)),
  });

  const applyMut = useMutation({
    mutationFn: async () => {
      const draft = parseDraft();
      if (!draft || !approvalRecord) throw new Error("Missing draft or approval");
      return applyApproval(draft, approvalRecord);
    },
    onSuccess: (res) => {
      setAppliedDraft(res.draft);
      setStage("applied");
      toast.success("Approval applied to draft.");
    },
    onError: (e) => toast.error(String(e)),
  });

  function reset() {
    setStage("input");
    setApprovalRecord(null);
    setAppliedDraft(null);
    setNotes("");
    setRejectReason("");
    setShowRejectForm(false);
  }

  return (
    <div className="space-y-6 max-w-3xl">
      <div>
        <h1 className="text-xl font-bold text-gray-900">Approvals</h1>
        <p className="text-sm text-gray-500 mt-1">
          Request, review, and apply approvals for investor summaries and IC memos
        </p>
      </div>

      {/* Step indicator */}
      <div className="flex items-center gap-2">
        {(["input", "pending", "decided", "applied"] as Stage[]).map((s, i) => {
          const labels = ["1. Draft", "2. Requested", "3. Decided", "4. Applied"];
          const active = s === stage;
          const done = ["input","pending","decided","applied"].indexOf(stage) > i;
          return (
            <div key={s} className="flex items-center gap-2">
              <div className={`flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium ${
                active ? "bg-blue-100 text-blue-700" :
                done ? "bg-green-100 text-green-700" :
                "bg-gray-100 text-gray-400"
              }`}>
                {done && <CheckCircle2 size={11} />}
                {labels[i]}
              </div>
              {i < 3 && <div className="w-6 h-px bg-gray-200" />}
            </div>
          );
        })}
      </div>

      {/* Stage 1: Draft input */}
      {stage === "input" && (
        <SectionCard title="Draft Document">
          <div className="space-y-4">
            <div>
              <label className="text-xs text-gray-500 font-medium">Requested By</label>
              <input
                className="mt-1 w-full border border-gray-200 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-gray-900"
                value={requestedBy}
                onChange={(e) => setRequestedBy(e.target.value)}
              />
            </div>
            <div>
              <button
                onClick={() => setShowDraftJson((v) => !v)}
                className="flex items-center gap-1 text-xs text-gray-500 hover:text-gray-700 font-medium"
              >
                {showDraftJson ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                Draft JSON
              </button>
              {showDraftJson && (
                <textarea
                  className="mt-2 w-full h-40 font-mono text-xs border border-gray-200 rounded p-3 resize-y focus:outline-none focus:ring-2 focus:ring-gray-900"
                  value={draftJson}
                  onChange={(e) => setDraftJson(e.target.value)}
                  spellCheck={false}
                />
              )}
              {draftParseErr && <p className="text-red-600 text-xs mt-1">{draftParseErr}</p>}
            </div>
            <Button onClick={() => requestMut.mutate()} disabled={requestMut.isPending}>
              {requestMut.isPending ? "Requesting…" : "Request Approval"}
            </Button>
          </div>
        </SectionCard>
      )}

      {/* Stage 2: Pending approval */}
      {stage === "pending" && approvalRecord && (
        <SectionCard title="Approval Request">
          <ApprovalCard record={approvalRecord} />
          <div className="mt-4 space-y-3">
            <div>
              <label className="text-xs text-gray-500 font-medium">Approver</label>
              <input
                className="mt-1 w-full border border-gray-200 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-gray-900"
                value={approver}
                onChange={(e) => setApprover(e.target.value)}
              />
            </div>
            <div>
              <label className="text-xs text-gray-500 font-medium">Notes (optional)</label>
              <textarea
                className="mt-1 w-full border border-gray-200 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-gray-900 resize-none"
                rows={2}
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
              />
            </div>
            <div className="flex items-center gap-2">
              <Button onClick={() => approveMut.mutate()} disabled={approveMut.isPending}>
                <CheckCircle2 size={13} className="mr-1.5" />
                {approveMut.isPending ? "Approving…" : "Approve"}
              </Button>
              <Button
                variant="outline"
                onClick={() => setShowRejectForm((v) => !v)}
              >
                <XCircle size={13} className="mr-1.5 text-red-400" />
                Reject
              </Button>
            </div>
            {showRejectForm && (
              <div className="space-y-2">
                <textarea
                  placeholder="Rejection reason…"
                  className="w-full border border-gray-200 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-red-400 resize-none"
                  rows={2}
                  value={rejectReason}
                  onChange={(e) => setRejectReason(e.target.value)}
                />
                <Button
                  variant="outline"
                  onClick={() => rejectMut.mutate()}
                  disabled={!rejectReason.trim() || rejectMut.isPending}
                >
                  {rejectMut.isPending ? "Rejecting…" : "Confirm Reject"}
                </Button>
              </div>
            )}
          </div>
        </SectionCard>
      )}

      {/* Stage 3: Decided */}
      {stage === "decided" && approvalRecord && (
        <SectionCard title="Approval Decision">
          <ApprovalCard record={approvalRecord} />
          {approvalRecord.status === "approved" && (
            <div className="mt-4 space-y-3">
              <p className="text-sm text-gray-600">
                The approval record is now ready. Apply it to the draft to mark it as officially approved.
              </p>
              <div className="flex items-center gap-2">
                <Button onClick={() => applyMut.mutate()} disabled={applyMut.isPending}>
                  <ShieldCheck size={13} className="mr-1.5" />
                  {applyMut.isPending ? "Applying…" : "Apply Approval to Draft"}
                </Button>
                <Button variant="outline" onClick={reset}>Start Over</Button>
              </div>
            </div>
          )}
          {approvalRecord.status === "rejected" && (
            <div className="mt-4">
              <p className="text-sm text-gray-500 mb-3">
                Draft was rejected. Revise and request approval again.
              </p>
              <Button variant="outline" onClick={reset}>Start Over</Button>
            </div>
          )}
        </SectionCard>
      )}

      {/* Stage 4: Applied */}
      {stage === "applied" && appliedDraft && (
        <SectionCard title="Draft — Approval Applied">
          <div className="flex items-center gap-2 mb-4">
            <ShieldCheck size={20} className="text-green-500" />
            <p className="text-sm font-semibold text-green-700">
              Draft is now marked as approved and ready for publication.
            </p>
          </div>
          <div className="bg-gray-50 rounded-lg p-4 font-mono text-xs text-gray-700 overflow-auto max-h-64">
            {JSON.stringify(appliedDraft, null, 2)}
          </div>
          <div className="mt-4">
            <Button variant="outline" onClick={reset}>New Approval Request</Button>
          </div>
        </SectionCard>
      )}

      {/* Info card */}
      <SectionCard title="Approval Flow">
        <div className="space-y-2 text-xs text-gray-500">
          {[
            ["Request", "Submit draft + requestor → backend creates approval_record with status=pending"],
            ["Approve / Reject", "Reviewer decides → record updated with decision + timestamp"],
            ["Apply", "Approved record stamped onto draft → draft.approved = true"],
            ["Publish Check", "Run /publish-check with the applied draft to verify all gates pass"],
          ].map(([step, desc]) => (
            <div key={step} className="flex gap-3">
              <span className="font-semibold text-gray-700 w-20 shrink-0">{step}</span>
              <span>{desc}</span>
            </div>
          ))}
        </div>
      </SectionCard>
    </div>
  );
}

// ─── ApprovalCard ─────────────────────────────────────────────────────────────

function ApprovalCard({ record }: { record: ApprovalRecord }) {
  return (
    <div className="bg-gray-50 rounded-lg p-4 space-y-2">
      <div className="flex items-center justify-between">
        <p className="text-xs font-mono text-gray-400">{record.approval_id}</p>
        {statusBadge(record.status)}
      </div>
      <div className="grid grid-cols-2 gap-2 text-xs">
        {[
          ["Draft ID", record.draft_id],
          ["Requested By", record.requested_by],
          ["Approver", record.approver ?? "—"],
          ["Requested", fmtTs(record.requested_at)],
          ["Decided", fmtTs(record.decided_at)],
          ["Expires", fmtTs(record.expires_at)],
        ].map(([label, val]) => (
          <div key={label}>
            <p className="text-gray-400">{label}</p>
            <p className="font-medium text-gray-700">{val}</p>
          </div>
        ))}
      </div>
      {record.notes && (
        <p className="text-xs text-gray-500 border-t border-gray-200 pt-2">Notes: {record.notes}</p>
      )}
      {record.rejection_reason && (
        <p className="text-xs text-red-500 border-t border-gray-200 pt-2">Rejection: {record.rejection_reason}</p>
      )}
    </div>
  );
}

// Suppress unused icon warning
void Clock;
