import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getWatchlist,
  addWatchlistItem,
  deleteWatchlistItem,
  checkDealAgainstWatchlist,
  type WatchlistItem,
  type WatchlistCheckAlert,
} from "../api/watchlist";
import { SectionCard } from "../components/SectionCard";
import { Button } from "../components/ui/Button";
import { Badge } from "../components/ui/Badge";
import { Input } from "../components/ui/Input";
import { Select } from "../components/ui/Select";
import { KRIBadge } from "../components/KRIBadge";
import { sampleDeals } from "../lib/sampleDeals";
import { Trash2, Bell, BellOff } from "lucide-react";

const SEVERITY_MAP: Record<string, "warning" | "danger" | "info"> = {
  warning: "warning",
  critical: "danger",
  info: "info",
};

function SeverityChip({ severity }: { severity: string }) {
  return <Badge variant={SEVERITY_MAP[severity] ?? "default"}>{severity}</Badge>;
}

const COMMON_METRICS = [
  "equity_irr",
  "oc_cushion_aaa",
  "diversity_score",
  "ccc_bucket_pct",
  "warf",
  "composite_score",
];

export function WatchlistPage() {
  const qc = useQueryClient();

  // Form state
  const [metric, setMetric] = useState("equity_irr");
  const [operator, setOperator] = useState("lt");
  const [threshold, setThreshold] = useState("0.10");
  const [label, setLabel] = useState("");
  const [severity, setSeverity] = useState("warning");
  const [formError, setFormError] = useState<string | null>(null);

  // Check panel
  const [checkJson, setCheckJson] = useState(() =>
    JSON.stringify(sampleDeals.usBSL, null, 2)
  );
  const [checkParseError, setCheckParseError] = useState<string | null>(null);

  const watchlistQuery = useQuery({
    queryKey: ["watchlist"],
    queryFn: getWatchlist,
  });

  const addMutation = useMutation({
    mutationFn: addWatchlistItem,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["watchlist"] });
      setLabel("");
    },
  });

  const deleteMutation = useMutation({
    mutationFn: deleteWatchlistItem,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["watchlist"] }),
  });

  const checkMutation = useMutation({
    mutationFn: (deal: Record<string, unknown>) => checkDealAgainstWatchlist(deal),
  });

  function handleAdd() {
    setFormError(null);
    const t = parseFloat(threshold);
    if (isNaN(t)) {
      setFormError("Threshold must be a number.");
      return;
    }
    addMutation.mutate({ metric, operator, threshold: t, label: label || undefined, severity });
  }

  function handleCheck() {
    setCheckParseError(null);
    try {
      const deal = JSON.parse(checkJson);
      checkMutation.mutate(deal);
    } catch {
      setCheckParseError("Invalid JSON.");
    }
  }

  const items: WatchlistItem[] = watchlistQuery.data ?? [];
  const alerts: WatchlistCheckAlert[] = (checkMutation.data?.alerts ?? []).filter(
    (a) => a.triggered
  );

  return (
    <div className="space-y-6 max-w-5xl">
      <div>
        <h1 className="text-xl font-bold text-gray-900">Watchlist</h1>
        <p className="text-sm text-gray-500 mt-1">
          Set metric alerts and check any deal against them instantly
        </p>
      </div>

      <div className="grid grid-cols-2 gap-6">
        {/* Add Alert Form */}
        <SectionCard title="Add Alert">
          <div className="space-y-3">
            <div>
              <label className="text-xs font-medium text-gray-600 mb-1 block">Metric</label>
              <Select value={metric} onChange={(e) => setMetric(e.target.value)}>
                {COMMON_METRICS.map((m) => (
                  <option key={m} value={m}>
                    {m}
                  </option>
                ))}
              </Select>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-medium text-gray-600 mb-1 block">Operator</label>
                <Select value={operator} onChange={(e) => setOperator(e.target.value)}>
                  <option value="lt">&lt; less than</option>
                  <option value="lte">&le; less than or equal</option>
                  <option value="gt">&gt; greater than</option>
                  <option value="gte">&ge; greater than or equal</option>
                  <option value="eq">= equal</option>
                </Select>
              </div>
              <div>
                <label className="text-xs font-medium text-gray-600 mb-1 block">Threshold</label>
                <Input
                  type="number"
                  step="0.01"
                  value={threshold}
                  onChange={(e) => setThreshold(e.target.value)}
                  placeholder="e.g. 0.10"
                />
              </div>
            </div>
            <div>
              <label className="text-xs font-medium text-gray-600 mb-1 block">
                Label <span className="text-gray-400">(optional)</span>
              </label>
              <Input
                value={label}
                onChange={(e) => setLabel(e.target.value)}
                placeholder="e.g. Low Equity IRR Alert"
              />
            </div>
            <div>
              <label className="text-xs font-medium text-gray-600 mb-1 block">Severity</label>
              <Select value={severity} onChange={(e) => setSeverity(e.target.value)}>
                <option value="info">info</option>
                <option value="warning">warning</option>
                <option value="critical">critical</option>
              </Select>
            </div>
            {formError && <p className="text-red-600 text-sm">{formError}</p>}
            {addMutation.isError && (
              <p className="text-red-600 text-sm">Error: {String(addMutation.error)}</p>
            )}
            <Button onClick={handleAdd} disabled={addMutation.isPending} className="w-full">
              {addMutation.isPending ? "Adding…" : "Add Alert"}
            </Button>
          </div>
        </SectionCard>

        {/* Active Alerts Table */}
        <SectionCard
          title={`Active Alerts (${items.length})`}
          action={
            watchlistQuery.isLoading ? (
              <span className="text-xs text-gray-400">Loading…</span>
            ) : undefined
          }
        >
          {items.length === 0 ? (
            <div className="text-center py-8 text-gray-400">
              <BellOff size={32} className="mx-auto mb-2 opacity-40" />
              <p className="text-sm">No alerts yet</p>
            </div>
          ) : (
            <div className="space-y-2 max-h-80 overflow-y-auto pr-1">
              {items.map((item) => (
                <div
                  key={item.item_id}
                  className="flex items-center gap-3 p-2.5 rounded-md border border-gray-100 hover:bg-gray-50"
                >
                  <Bell size={14} className="text-gray-400 shrink-0" />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-800 truncate">{item.label}</p>
                    <p className="text-xs text-gray-500 font-mono">
                      {item.metric} {item.operator} {item.threshold}
                    </p>
                  </div>
                  <SeverityChip severity={item.severity} />
                  <button
                    onClick={() => deleteMutation.mutate(item.item_id)}
                    className="text-gray-300 hover:text-red-500 transition-colors"
                    title="Delete alert"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              ))}
            </div>
          )}
        </SectionCard>
      </div>

      {/* Check Deal Panel */}
      <SectionCard title="Check Deal Against Watchlist">
        <div className="grid grid-cols-2 gap-6">
          <div>
            <label className="text-xs font-medium text-gray-600 mb-1 block">Deal JSON</label>
            <textarea
              className="w-full h-56 font-mono text-xs border border-gray-200 rounded p-3 resize-y focus:outline-none focus:ring-2 focus:ring-gray-900"
              value={checkJson}
              onChange={(e) => setCheckJson(e.target.value)}
              spellCheck={false}
            />
            {checkParseError && (
              <p className="text-red-600 text-sm mt-1">{checkParseError}</p>
            )}
            <div className="flex gap-2 mt-3 flex-wrap">
              {["usBSL", "euCLO", "mmCLO"].map((k) => (
                <Button
                  key={k}
                  variant="outline"
                  size="sm"
                  onClick={() =>
                    setCheckJson(
                      JSON.stringify(sampleDeals[k as keyof typeof sampleDeals], null, 2)
                    )
                  }
                >
                  {k === "usBSL" ? "US BSL" : k === "euCLO" ? "EU CLO" : "MM CLO"}
                </Button>
              ))}
            </div>
            <Button
              className="mt-3"
              onClick={handleCheck}
              disabled={checkMutation.isPending}
            >
              {checkMutation.isPending ? "Checking…" : "Check Deal"}
            </Button>
          </div>

          <div>
            {checkMutation.isError && (
              <p className="text-red-600 text-sm">Error: {String(checkMutation.error)}</p>
            )}
            {checkMutation.data && (
              <div className="space-y-3">
                <div className="flex gap-3">
                  <div className="bg-gray-50 rounded-lg p-3 flex-1 text-center">
                    <p className="text-xs text-gray-500">Checked</p>
                    <p className="text-xl font-bold text-gray-900">
                      {checkMutation.data.items_checked}
                    </p>
                  </div>
                  <div
                    className={`rounded-lg p-3 flex-1 text-center ${
                      checkMutation.data.triggered_count > 0
                        ? "bg-red-50"
                        : "bg-green-50"
                    }`}
                  >
                    <p className="text-xs text-gray-500">Triggered</p>
                    <p
                      className={`text-xl font-bold ${
                        checkMutation.data.triggered_count > 0
                          ? "text-red-600"
                          : "text-green-600"
                      }`}
                    >
                      {checkMutation.data.triggered_count}
                    </p>
                  </div>
                </div>

                {alerts.length === 0 ? (
                  <div className="text-center py-6 text-green-600">
                    <p className="text-sm font-medium">All clear — no alerts triggered</p>
                  </div>
                ) : (
                  <div className="space-y-2">
                    <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
                      Triggered Alerts
                    </p>
                    {alerts.map((a, i) => (
                      <div
                        key={i}
                        className="p-3 rounded-lg border border-red-200 bg-red-50 space-y-1"
                      >
                        <div className="flex items-center justify-between">
                          <p className="text-sm font-medium text-gray-900">{a.label}</p>
                          <KRIBadge status={a.severity === "critical" ? "critical" : "warn"} />
                        </div>
                        <p className="text-xs text-gray-600 font-mono">
                          {a.metric} {a.operator} {a.threshold} — actual:{" "}
                          <span className="font-bold text-red-700">
                            {a.actual_value != null ? String(a.actual_value) : "N/A"}
                          </span>
                        </p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {!checkMutation.data && !checkMutation.isPending && (
              <div className="flex items-center justify-center h-full text-gray-300">
                <p className="text-sm">Run a check to see results</p>
              </div>
            )}
          </div>
        </div>
      </SectionCard>
    </div>
  );
}
