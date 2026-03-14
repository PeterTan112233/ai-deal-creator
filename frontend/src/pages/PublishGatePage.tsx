import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { runPublishCheck, type PublishCheckResult, type GateResult } from "../api/publishCheck";
import { SectionCard } from "../components/SectionCard";
import { Button } from "../components/ui/Button";
import { Badge } from "../components/ui/Badge";
import { useToast } from "../components/ui/Toast";
import { CheckCircle2, XCircle, AlertTriangle, ShieldCheck, ShieldOff, Shield } from "lucide-react";

// ─── Helpers ──────────────────────────────────────────────────────────────────

const SAMPLE_DRAFT = {
  draft_id: "draft-001",
  deal_name: "Sample CLO 2024-1",
  draft_type: "investor_summary",
  content: "Sample investor summary content.",
  approved: false,
};

const SAMPLE_APPROVAL = {
  approval_id: "appr-001",
  draft_id: "draft-001",
  status: "approved",
  requested_by: "analyst@clo.internal",
  approver: "senior.reviewer@clo.internal",
  requested_at: new Date(Date.now() - 3600_000).toISOString(),
  decided_at: new Date().toISOString(),
  expires_at: new Date(Date.now() + 86400_000 * 30).toISOString(),
};

function GateRow({ gate }: { gate: GateResult }) {
  const { passed, message, severity } = gate;
  const label = gate.gate.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
  return (
    <div className={`flex items-start gap-3 p-3 rounded-lg ${
      passed ? "bg-green-50" : severity === "warning" ? "bg-amber-50" : "bg-red-50"
    }`}>
      {passed
        ? <CheckCircle2 size={16} className="text-green-500 mt-0.5 shrink-0" />
        : severity === "warning"
        ? <AlertTriangle size={16} className="text-amber-500 mt-0.5 shrink-0" />
        : <XCircle size={16} className="text-red-500 mt-0.5 shrink-0" />}
      <div>
        <p className={`text-sm font-medium ${
          passed ? "text-green-800" : severity === "warning" ? "text-amber-800" : "text-red-800"
        }`}>{label}</p>
        <p className={`text-xs mt-0.5 ${
          passed ? "text-green-600" : severity === "warning" ? "text-amber-600" : "text-red-600"
        }`}>{message}</p>
      </div>
    </div>
  );
}

function OverallVerdict({ result }: { result: PublishCheckResult }) {
  const { overall } = result;
  if (overall === "pass") {
    return (
      <div className="flex items-center gap-3 p-4 bg-green-50 border border-green-200 rounded-xl">
        <ShieldCheck size={32} className="text-green-500 shrink-0" />
        <div>
          <p className="text-lg font-bold text-green-800">All Gates Pass</p>
          <p className="text-sm text-green-600">This draft is cleared for publication.</p>
        </div>
      </div>
    );
  }
  if (overall === "pass_with_notes") {
    return (
      <div className="flex items-center gap-3 p-4 bg-amber-50 border border-amber-200 rounded-xl">
        <Shield size={32} className="text-amber-500 shrink-0" />
        <div>
          <p className="text-lg font-bold text-amber-800">Pass with Notes</p>
          <p className="text-sm text-amber-600">Cleared with warnings — review notes before publishing.</p>
        </div>
      </div>
    );
  }
  return (
    <div className="flex items-center gap-3 p-4 bg-red-50 border border-red-200 rounded-xl">
      <ShieldOff size={32} className="text-red-500 shrink-0" />
      <div>
        <p className="text-lg font-bold text-red-800">Publication Blocked</p>
        <p className="text-sm text-red-600">Resolve blocking issues before this draft can be published.</p>
      </div>
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export function PublishGatePage() {
  const toast = useToast();
  const [draftJson, setDraftJson] = useState(JSON.stringify(SAMPLE_DRAFT, null, 2));
  const [approvalJson, setApprovalJson] = useState(JSON.stringify(SAMPLE_APPROVAL, null, 2));
  const [includeApproval, setIncludeApproval] = useState(false);
  const [channel, setChannel] = useState("internal");
  const [result, setResult] = useState<PublishCheckResult | null>(null);
  const [parseErr, setParseErr] = useState<string | null>(null);

  const checkMut = useMutation({
    mutationFn: async () => {
      setParseErr(null);
      let draft: Record<string, unknown>;
      let approval: Record<string, unknown> | null = null;
      try {
        draft = JSON.parse(draftJson);
      } catch {
        throw new Error("Invalid draft JSON");
      }
      if (includeApproval) {
        try {
          approval = JSON.parse(approvalJson);
        } catch {
          throw new Error("Invalid approval JSON");
        }
      }
      return runPublishCheck(draft, approval, channel);
    },
    onSuccess: (res) => {
      setResult(res);
      if (res.overall === "pass") toast.success("All gates passed.");
      else if (res.overall === "pass_with_notes") toast.info("Pass with notes.");
      else toast.error("Publication blocked.");
    },
    onError: (e) => {
      setParseErr(String(e));
      toast.error(String(e));
    },
  });

  const gatesPass = result?.gates.filter((g) => g.passed).length ?? 0;
  const gatesTotal = result?.gates.length ?? 0;

  return (
    <div className="space-y-6 max-w-3xl">
      <div>
        <h1 className="text-xl font-bold text-gray-900">Publish Gate</h1>
        <p className="text-sm text-gray-500 mt-1">
          7-gate compliance check before publishing any draft to internal or external channels
        </p>
      </div>

      {/* Input */}
      <SectionCard title="Draft & Approval">
        <div className="space-y-4">
          <div>
            <label className="text-xs text-gray-500 font-medium">Target Channel</label>
            <div className="flex gap-2 mt-1">
              {["internal", "external", "investor_portal"].map((ch) => (
                <button
                  key={ch}
                  onClick={() => setChannel(ch)}
                  className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                    channel === ch
                      ? "bg-gray-900 text-white"
                      : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                  }`}
                >
                  {ch.replace("_", " ")}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="text-xs text-gray-500 font-medium">Draft JSON</label>
            <textarea
              className="mt-1 w-full h-36 font-mono text-xs border border-gray-200 rounded p-3 resize-y focus:outline-none focus:ring-2 focus:ring-gray-900"
              value={draftJson}
              onChange={(e) => setDraftJson(e.target.value)}
              spellCheck={false}
            />
          </div>

          <label className="flex items-center gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={includeApproval}
              onChange={(e) => setIncludeApproval(e.target.checked)}
              className="accent-blue-600"
            />
            <span className="text-xs text-gray-600 font-medium">Include approval record</span>
          </label>

          {includeApproval && (
            <div>
              <label className="text-xs text-gray-500 font-medium">Approval Record JSON</label>
              <textarea
                className="mt-1 w-full h-36 font-mono text-xs border border-gray-200 rounded p-3 resize-y focus:outline-none focus:ring-2 focus:ring-gray-900"
                value={approvalJson}
                onChange={(e) => setApprovalJson(e.target.value)}
                spellCheck={false}
              />
            </div>
          )}

          {parseErr && <p className="text-red-600 text-sm">{parseErr}</p>}

          <Button onClick={() => checkMut.mutate()} disabled={checkMut.isPending}>
            <ShieldCheck size={13} className="mr-1.5" />
            {checkMut.isPending ? "Checking…" : "Run Publish Check"}
          </Button>
        </div>
      </SectionCard>

      {/* Results */}
      {result && (
        <>
          <OverallVerdict result={result} />

          <SectionCard
            title="Gate Results"
            action={
              <span className="text-xs text-gray-400">{gatesPass}/{gatesTotal} passed</span>
            }
          >
            {/* Progress bar */}
            <div className="h-2 bg-gray-100 rounded-full mb-4 overflow-hidden">
              <div
                className={`h-2 rounded-full transition-all ${
                  result.overall === "pass" ? "bg-green-500" :
                  result.overall === "pass_with_notes" ? "bg-amber-500" : "bg-red-500"
                }`}
                style={{ width: gatesTotal ? `${(gatesPass / gatesTotal) * 100}%` : "0%" }}
              />
            </div>
            <div className="space-y-2">
              {result.gates.map((gate) => (
                <GateRow key={gate.gate} gate={gate} />
              ))}
            </div>
          </SectionCard>

          {result.blocking_issues.length > 0 && (
            <SectionCard title="Blocking Issues">
              <ul className="space-y-2">
                {result.blocking_issues.map((issue, i) => (
                  <li key={i} className="flex gap-2 text-sm text-red-700">
                    <XCircle size={15} className="shrink-0 mt-0.5 text-red-500" />
                    {issue}
                  </li>
                ))}
              </ul>
            </SectionCard>
          )}

          {result.warnings.length > 0 && (
            <SectionCard title="Warnings">
              <ul className="space-y-2">
                {result.warnings.map((w, i) => (
                  <li key={i} className="flex gap-2 text-sm text-amber-700">
                    <AlertTriangle size={15} className="shrink-0 mt-0.5 text-amber-500" />
                    {w}
                  </li>
                ))}
              </ul>
            </SectionCard>
          )}

          <div className="flex items-center justify-between">
            <p className="text-xs text-gray-400">
              Checked at {new Date(result.checked_at).toLocaleString()}
            </p>
            <Badge variant="default">
              {result._mock ? "mock engine" : "live"}
            </Badge>
          </div>
        </>
      )}

      {/* Empty */}
      {!result && !checkMut.isPending && (
        <div className="text-center py-16 text-gray-400">
          <ShieldCheck size={44} className="mx-auto mb-4 opacity-20" />
          <p className="text-sm font-medium">Run a publish check to see gate results</p>
          <p className="text-xs mt-1">Verifies approval status, expiry, content sources, and channel permissions</p>
        </div>
      )}
    </div>
  );
}
