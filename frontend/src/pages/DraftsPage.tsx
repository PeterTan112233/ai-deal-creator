import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { useLocation } from "react-router-dom";
import { client } from "../api/client";
import {
  generateInvestorSummary,
  generateIcMemo,
  requestApproval,
  approveRecord,
  rejectRecord,
  applyApproval,
  type DraftDoc,
  type ApprovalRecord,
  type DraftResponse,
} from "../api/drafts";
import { SectionCard } from "../components/SectionCard";
import { Button } from "../components/ui/Button";
import { Badge } from "../components/ui/Badge";
import { sampleDeals } from "../lib/sampleDeals";
import { Check, X, FileText, Send, ShieldCheck, ChevronRight, Database } from "lucide-react";
import { DealPickerModal } from "../components/DealPickerModal";

// Step names
const STEPS = [
  { id: 1, label: "Run Scenario" },
  { id: 2, label: "Generate Draft" },
  { id: 3, label: "Request Approval" },
  { id: 4, label: "Approve / Reject" },
  { id: 5, label: "Apply & Finalize" },
] as const;

type Step = (typeof STEPS)[number]["id"];

function StepIndicator({ current }: { current: Step }) {
  return (
    <ol className="flex items-center gap-0">
      {STEPS.map((s, i) => {
        const done = s.id < current;
        const active = s.id === current;
        return (
          <li key={s.id} className="flex items-center">
            <div className="flex items-center gap-2">
              <div
                className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold shrink-0 ${
                  done
                    ? "bg-green-500 text-white"
                    : active
                    ? "bg-gray-900 text-white"
                    : "bg-gray-100 text-gray-400"
                }`}
              >
                {done ? <Check size={12} /> : s.id}
              </div>
              <span
                className={`text-xs font-medium ${
                  active ? "text-gray-900" : done ? "text-green-600" : "text-gray-400"
                }`}
              >
                {s.label}
              </span>
            </div>
            {i < STEPS.length - 1 && (
              <ChevronRight size={14} className="mx-3 text-gray-300 shrink-0" />
            )}
          </li>
        );
      })}
    </ol>
  );
}

function StatusChip({ status }: { status?: string }) {
  if (!status) return null;
  const s = status.toLowerCase();
  if (s === "pending")
    return <Badge variant="warning">pending review</Badge>;
  if (s === "approved")
    return <Badge variant="success">approved</Badge>;
  if (s === "rejected")
    return <Badge variant="danger">rejected</Badge>;
  return <Badge variant="default">{status}</Badge>;
}

export function DraftsPage() {
  const location = useLocation();
  const preloaded = (location.state as { dealInput?: Record<string, unknown> } | null)
    ?.dealInput;

  // Step 1 state
  const [step, setStep] = useState<Step>(1);
  const [showPicker, setShowPicker] = useState(false);
  const [dealJson, setDealJson] = useState(() =>
    preloaded ? JSON.stringify(preloaded, null, 2) : JSON.stringify(sampleDeals.usBSL, null, 2)
  );
  const [docType, setDocType] = useState<"investor-summary" | "ic-memo">("investor-summary");
  const [scenarioResult, setScenarioResult] = useState<Record<string, unknown> | null>(null);
  const [scenarioRequest, setScenarioRequest] = useState<Record<string, unknown> | null>(null);
  const [step1Error, setStep1Error] = useState<string | null>(null);

  // Step 2 state
  const [draftResponse, setDraftResponse] = useState<DraftResponse | null>(null);

  // Step 3 state
  const [requestedBy, setRequestedBy] = useState("analyst@example.com");
  const [channel, setChannel] = useState("internal");
  const [approvalRecord, setApprovalRecord] = useState<ApprovalRecord | null>(null);

  // Step 4 state
  const [approver, setApprover] = useState("manager@example.com");
  const [approvalNotes, setApprovalNotes] = useState("");
  const [rejectionReason, setRejectionReason] = useState("");
  const [showRejectForm, setShowRejectForm] = useState(false);
  const [decidedRecord, setDecidedRecord] = useState<ApprovalRecord | null>(null);

  // Step 5 state
  const [finalDraft, setFinalDraft] = useState<DraftDoc | null>(null);

  // ─── Mutations ────────────────────────────────────────────────────────────

  const runScenarioMut = useMutation({
    mutationFn: async (dealInput: Record<string, unknown>) => {
      const res = await client.post("/scenarios", {
        deal_input: dealInput,
        scenario_name: "Baseline",
        scenario_type: "base",
        actor: "frontend",
      });
      return res.data;
    },
    onSuccess: (data) => {
      setScenarioResult(data.scenario_result ?? {});
      setScenarioRequest(data.scenario_request ?? null);
      setStep(2);
    },
    onError: (err) => setStep1Error(String(err)),
  });

  const generateDraftMut = useMutation({
    mutationFn: async () => {
      const dealInput = JSON.parse(dealJson);
      if (docType === "investor-summary") {
        return generateInvestorSummary(
          dealInput,
          scenarioResult!,
          scenarioRequest ?? undefined
        );
      } else {
        return generateIcMemo(
          dealInput,
          scenarioResult!,
          scenarioRequest ?? undefined
        );
      }
    },
    onSuccess: (data) => {
      setDraftResponse(data);
      setStep(3);
    },
  });

  const requestApprovalMut = useMutation({
    mutationFn: async () => {
      return requestApproval(draftResponse!.draft!, requestedBy, channel);
    },
    onSuccess: (record) => {
      setApprovalRecord(record);
      setStep(4);
    },
  });

  const approveMut = useMutation({
    mutationFn: async () => {
      return approveRecord(approvalRecord!, approver, approvalNotes || undefined);
    },
    onSuccess: (record) => {
      setDecidedRecord(record);
    },
  });

  const rejectMut = useMutation({
    mutationFn: async () => {
      return rejectRecord(approvalRecord!, approver, rejectionReason || "Rejected by reviewer");
    },
    onSuccess: (record) => {
      setDecidedRecord(record);
    },
  });

  const applyMut = useMutation({
    mutationFn: async () => {
      return applyApproval(draftResponse!.draft!, decidedRecord!);
    },
    onSuccess: (draft) => {
      setFinalDraft(draft);
      setStep(5);
    },
  });

  // ─── Step 1: Run Scenario ─────────────────────────────────────────────────

  function handleRunScenario() {
    setStep1Error(null);
    try {
      const dealInput = JSON.parse(dealJson);
      runScenarioMut.mutate(dealInput);
    } catch {
      setStep1Error("Invalid deal JSON.");
    }
  }

  // ─── Render ───────────────────────────────────────────────────────────────

  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <h1 className="text-xl font-bold text-gray-900">Draft & Approval</h1>
        <p className="text-sm text-gray-500 mt-1">
          Generate investor summaries and IC memos, request approval, and finalize documents
        </p>
      </div>

      {/* Step indicator */}
      <SectionCard>
        <StepIndicator current={step} />
      </SectionCard>

      {showPicker && (
        <DealPickerModal
          onSelect={(input) => setDealJson(JSON.stringify(input, null, 2))}
          onClose={() => setShowPicker(false)}
        />
      )}

      {/* ── Step 1: Run Scenario ─────────────────────────────────────── */}
      <SectionCard
        title="Step 1 — Run Baseline Scenario"
        action={
          scenarioResult && (
            <Badge variant="success">Scenario complete</Badge>
          )
        }
      >
        <div className="space-y-3">
          <div>
            <label className="text-xs text-gray-600 mb-1 block">Document type</label>
            <div className="flex gap-2">
              <button
                onClick={() => setDocType("investor-summary")}
                className={`px-3 py-1.5 rounded-md text-xs font-medium border transition-colors ${
                  docType === "investor-summary"
                    ? "bg-gray-900 text-white border-gray-900"
                    : "border-gray-200 text-gray-600 hover:border-gray-400"
                }`}
              >
                Investor Summary
              </button>
              <button
                onClick={() => setDocType("ic-memo")}
                className={`px-3 py-1.5 rounded-md text-xs font-medium border transition-colors ${
                  docType === "ic-memo"
                    ? "bg-gray-900 text-white border-gray-900"
                    : "border-gray-200 text-gray-600 hover:border-gray-400"
                }`}
              >
                IC Memo
              </button>
            </div>
          </div>

          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="text-xs text-gray-600">Deal JSON</label>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setShowPicker(true)}
                  className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-900 border border-gray-200 rounded px-2 py-1 hover:border-gray-400 transition-colors"
                >
                  <Database size={12} /> Pick from Registry
                </button>
                <div className="flex gap-1.5">
                {(["usBSL", "euCLO", "mmCLO"] as const).map((k) => (
                  <button
                    key={k}
                    onClick={() => setDealJson(JSON.stringify(sampleDeals[k], null, 2))}
                    className="text-xs text-gray-400 hover:text-gray-700 px-1.5 py-0.5 border border-gray-200 rounded"
                  >
                    {k === "usBSL" ? "US BSL" : k === "euCLO" ? "EU CLO" : "MM CLO"}
                  </button>
                ))}
                </div>
              </div>
            </div>
            <textarea
              className="w-full h-40 font-mono text-xs border border-gray-200 rounded p-3 resize-y focus:outline-none focus:ring-2 focus:ring-gray-900"
              value={dealJson}
              onChange={(e) => setDealJson(e.target.value)}
              spellCheck={false}
            />
          </div>

          {step1Error && <p className="text-red-600 text-sm">{step1Error}</p>}
          {runScenarioMut.isError && (
            <p className="text-red-600 text-sm">Error: {String(runScenarioMut.error)}</p>
          )}

          <Button onClick={handleRunScenario} disabled={runScenarioMut.isPending}>
            {runScenarioMut.isPending ? "Running…" : "Run Baseline Scenario"}
          </Button>

          {scenarioResult && (
            <div className="mt-2 bg-green-50 border border-green-100 rounded p-3 text-xs text-green-700">
              Scenario complete — equity IRR:{" "}
              <strong>
                {(() => {
                  const outputs = scenarioResult.outputs as Record<string, unknown> | undefined;
                  const irr = outputs?.equity_irr ?? scenarioResult.equity_irr;
                  return irr != null ? `${((irr as number) * 100).toFixed(2)}%` : "—";
                })()}
              </strong>
            </div>
          )}
        </div>
      </SectionCard>

      {/* ── Step 2: Generate Draft ────────────────────────────────────── */}
      {step >= 2 && (
        <SectionCard
          title={`Step 2 — Generate ${docType === "investor-summary" ? "Investor Summary" : "IC Memo"}`}
          action={draftResponse && <Badge variant="success">Draft ready</Badge>}
        >
          <div className="space-y-3">
            <p className="text-sm text-gray-600">
              Claude will draft the{" "}
              <strong>
                {docType === "investor-summary" ? "investor summary" : "IC memo"}
              </strong>{" "}
              from the scenario result. The output is tagged{" "}
              <code className="text-xs bg-gray-100 px-1 rounded">[generated]</code> and requires
              approval before any distribution.
            </p>

            {generateDraftMut.isError && (
              <p className="text-red-600 text-sm">Error: {String(generateDraftMut.error)}</p>
            )}

            {!draftResponse && (
              <Button
                onClick={() => generateDraftMut.mutate()}
                disabled={generateDraftMut.isPending}
              >
                <FileText size={14} className="mr-1.5" />
                {generateDraftMut.isPending ? "Generating…" : "Generate Draft"}
              </Button>
            )}

            {draftResponse && (
              <div className="space-y-3">
                <div className="flex items-center gap-3">
                  <Badge variant={draftResponse.approved ? "success" : "warning"}>
                    {draftResponse.approved ? "approved" : "not approved"}
                  </Badge>
                  {draftResponse.requires_approval && (
                    <span className="text-xs text-gray-500">Requires approval before distribution</span>
                  )}
                </div>

                {draftResponse.draft_markdown && (
                  <div className="bg-gray-50 border border-gray-100 rounded p-4 max-h-72 overflow-y-auto">
                    <pre className="text-xs text-gray-700 whitespace-pre-wrap font-mono leading-relaxed">
                      {draftResponse.draft_markdown}
                    </pre>
                  </div>
                )}
              </div>
            )}
          </div>
        </SectionCard>
      )}

      {/* ── Step 3: Request Approval ──────────────────────────────────── */}
      {step >= 3 && (
        <SectionCard
          title="Step 3 — Request Approval"
          action={approvalRecord && <StatusChip status={approvalRecord.status} />}
        >
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-gray-600 mb-1 block">Requested by</label>
                <input
                  type="text"
                  className="w-full h-9 text-sm border border-gray-200 rounded px-3 focus:outline-none focus:ring-2 focus:ring-gray-900"
                  value={requestedBy}
                  onChange={(e) => setRequestedBy(e.target.value)}
                />
              </div>
              <div>
                <label className="text-xs text-gray-600 mb-1 block">Channel</label>
                <select
                  className="w-full h-9 text-sm border border-gray-200 rounded px-3 focus:outline-none focus:ring-2 focus:ring-gray-900 bg-white"
                  value={channel}
                  onChange={(e) => setChannel(e.target.value)}
                >
                  <option value="internal">Internal</option>
                  <option value="investor">Investor</option>
                  <option value="regulatory">Regulatory</option>
                </select>
              </div>
            </div>

            {requestApprovalMut.isError && (
              <p className="text-red-600 text-sm">Error: {String(requestApprovalMut.error)}</p>
            )}

            {!approvalRecord && (
              <Button
                onClick={() => requestApprovalMut.mutate()}
                disabled={requestApprovalMut.isPending}
              >
                <Send size={14} className="mr-1.5" />
                {requestApprovalMut.isPending ? "Requesting…" : "Request Approval"}
              </Button>
            )}

            {approvalRecord && (
              <div className="bg-amber-50 border border-amber-100 rounded p-3 text-xs text-amber-700 space-y-1">
                <p>
                  <span className="font-medium">Approval ID:</span>{" "}
                  <code>{approvalRecord.approval_id ?? "—"}</code>
                </p>
                <p>
                  <span className="font-medium">Status:</span>{" "}
                  <StatusChip status={approvalRecord.status} />
                </p>
                <p>
                  <span className="font-medium">Requested by:</span>{" "}
                  {approvalRecord.requested_by}
                </p>
              </div>
            )}
          </div>
        </SectionCard>
      )}

      {/* ── Step 4: Approve / Reject ──────────────────────────────────── */}
      {step >= 4 && (
        <SectionCard
          title="Step 4 — Approve or Reject"
          action={decidedRecord && <StatusChip status={decidedRecord.status} />}
        >
          <div className="space-y-3">
            <div>
              <label className="text-xs text-gray-600 mb-1 block">Approver identity</label>
              <input
                type="text"
                className="w-full h-9 text-sm border border-gray-200 rounded px-3 focus:outline-none focus:ring-2 focus:ring-gray-900"
                value={approver}
                onChange={(e) => setApprover(e.target.value)}
              />
            </div>

            {!decidedRecord && !showRejectForm && (
              <div className="flex gap-3">
                <Button
                  onClick={() => approveMut.mutate()}
                  disabled={approveMut.isPending}
                >
                  <Check size={14} className="mr-1.5" />
                  {approveMut.isPending ? "Approving…" : "Approve"}
                </Button>
                <Button
                  variant="outline"
                  onClick={() => setShowRejectForm(true)}
                >
                  <X size={14} className="mr-1.5" />
                  Reject
                </Button>
              </div>
            )}

            {showRejectForm && !decidedRecord && (
              <div className="space-y-2">
                <label className="text-xs text-gray-600 block">Rejection reason</label>
                <textarea
                  className="w-full h-20 text-sm border border-gray-200 rounded p-3 resize-none focus:outline-none focus:ring-2 focus:ring-gray-900"
                  value={rejectionReason}
                  onChange={(e) => setRejectionReason(e.target.value)}
                  placeholder="Explain why this draft is being rejected…"
                />
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    onClick={() => rejectMut.mutate()}
                    disabled={rejectMut.isPending}
                  >
                    <X size={14} className="mr-1.5" />
                    {rejectMut.isPending ? "Rejecting…" : "Confirm Reject"}
                  </Button>
                  <Button variant="ghost" onClick={() => setShowRejectForm(false)}>
                    Cancel
                  </Button>
                </div>
              </div>
            )}

            {(approveMut.isError || rejectMut.isError) && (
              <p className="text-red-600 text-sm">
                Error: {String(approveMut.error ?? rejectMut.error)}
              </p>
            )}

            {decidedRecord && decidedRecord.status === "approved" && (
              <div className="space-y-3">
                <div className="bg-green-50 border border-green-100 rounded p-3 text-xs text-green-700 space-y-1">
                  <p>
                    <span className="font-medium">Approved by:</span> {decidedRecord.approver}
                  </p>
                  {decidedRecord.notes && (
                    <p>
                      <span className="font-medium">Notes:</span> {decidedRecord.notes}
                    </p>
                  )}
                </div>
                <Button onClick={() => applyMut.mutate()} disabled={applyMut.isPending}>
                  <ShieldCheck size={14} className="mr-1.5" />
                  {applyMut.isPending ? "Applying…" : "Apply Approval to Draft"}
                </Button>
                {applyMut.isError && (
                  <p className="text-red-600 text-sm">Error: {String(applyMut.error)}</p>
                )}
              </div>
            )}

            {decidedRecord && decidedRecord.status === "rejected" && (
              <div className="bg-red-50 border border-red-100 rounded p-3 text-xs text-red-700 space-y-1">
                <p>
                  <span className="font-medium">Rejected by:</span> {decidedRecord.approver}
                </p>
                {decidedRecord.rejection_reason && (
                  <p>
                    <span className="font-medium">Reason:</span>{" "}
                    {decidedRecord.rejection_reason}
                  </p>
                )}
                <p className="mt-2 text-gray-600">
                  Go back to Step 1 to revise the scenario and regenerate the draft.
                </p>
                <button
                  onClick={() => {
                    setStep(1);
                    setScenarioResult(null);
                    setDraftResponse(null);
                    setApprovalRecord(null);
                    setDecidedRecord(null);
                    setFinalDraft(null);
                    setShowRejectForm(false);
                  }}
                  className="mt-2 text-xs font-medium text-blue-600 hover:underline"
                >
                  Restart flow
                </button>
              </div>
            )}
          </div>
        </SectionCard>
      )}

      {/* ── Step 5: Final Approved Draft ─────────────────────────────── */}
      {step >= 5 && finalDraft && (
        <SectionCard title="Step 5 — Approved Draft">
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <ShieldCheck size={16} className="text-green-500" />
              <span className="text-sm font-medium text-green-700">
                Draft is approved and finalized
              </span>
              <Badge variant="success">approved = true</Badge>
            </div>

            <div className="bg-gray-50 border border-gray-100 rounded p-4 text-xs font-mono text-gray-500">
              <p>
                <span className="font-semibold text-gray-700">draft_id:</span>{" "}
                {String(finalDraft.draft_id ?? "—")}
              </p>
              <p>
                <span className="font-semibold text-gray-700">doc_type:</span>{" "}
                {String(finalDraft.doc_type ?? "—")}
              </p>
              <p>
                <span className="font-semibold text-gray-700">approved:</span>{" "}
                {String(finalDraft.approved ?? "—")}
              </p>
            </div>

            <div className="bg-amber-50 border border-amber-200 rounded px-4 py-3 text-sm text-amber-800">
              This document is ready for internal review. External distribution requires a
              separate publish action (not yet implemented in Phase 1).
            </div>
          </div>
        </SectionCard>
      )}
    </div>
  );
}
