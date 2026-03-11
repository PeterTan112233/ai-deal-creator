import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { listDeals, registerDeal, deleteDeal, getDeal, type DealSummary } from "../api/deals";
import { SectionCard } from "../components/SectionCard";
import { Button } from "../components/ui/Button";
import { Badge } from "../components/ui/Badge";
import { sampleDeals } from "../lib/sampleDeals";
import { Activity, Play, Trash2, Plus, ChevronUp, Database } from "lucide-react";

function fmt(n: number | null): string {
  if (n == null) return "—";
  if (n >= 1_000_000_000) return `$${(n / 1_000_000_000).toFixed(1)}B`;
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(0)}M`;
  return `$${n.toLocaleString()}`;
}

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1) return "just now";
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

export function DealRegistryPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [json, setJson] = useState(() => JSON.stringify(sampleDeals.usBSL, null, 2));
  const [parseError, setParseError] = useState<string | null>(null);

  const dealsQuery = useQuery({
    queryKey: ["deals"],
    queryFn: listDeals,
    refetchInterval: 10000,
  });

  const registerMutation = useMutation({
    mutationFn: (input: Record<string, unknown>) => registerDeal(input),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["deals"] });
      setShowForm(false);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: deleteDeal,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["deals"] }),
  });

  async function handleUse(deal: DealSummary, dest: "/health" | "/scenarios") {
    try {
      const detail = await getDeal(deal.deal_id);
      navigate(dest, { state: { dealInput: detail.deal_input } });
    } catch {
      // If detail fetch fails, navigate without pre-loading
      navigate(dest);
    }
  }

  function handleRegister() {
    setParseError(null);
    try {
      const parsed = JSON.parse(json);
      registerMutation.mutate(parsed);
    } catch {
      setParseError("Invalid JSON.");
    }
  }

  const deals: DealSummary[] = dealsQuery.data ?? [];

  return (
    <div className="space-y-6 max-w-6xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-gray-900">Deal Registry</h1>
          <p className="text-sm text-gray-500 mt-1">
            Register deals once — run health checks and scenarios without pasting JSON every time
          </p>
        </div>
        <Button onClick={() => setShowForm((v) => !v)} variant={showForm ? "outline" : "default"}>
          {showForm ? (
            <>
              <ChevronUp size={14} className="mr-1.5" /> Cancel
            </>
          ) : (
            <>
              <Plus size={14} className="mr-1.5" /> Register Deal
            </>
          )}
        </Button>
      </div>

      {/* Register form */}
      {showForm && (
        <SectionCard title="Register New Deal">
          <p className="text-xs text-gray-500 mb-2">
            Paste a deal JSON (same format as Health Check). The deal will be saved in the registry
            for this server session.
          </p>
          <div className="flex gap-2 mb-2">
            {(["usBSL", "euCLO", "mmCLO"] as const).map((k) => (
              <Button
                key={k}
                variant="outline"
                size="sm"
                onClick={() => setJson(JSON.stringify(sampleDeals[k], null, 2))}
              >
                {k === "usBSL" ? "US BSL" : k === "euCLO" ? "EU CLO" : "MM CLO"}
              </Button>
            ))}
          </div>
          <textarea
            className="w-full h-48 font-mono text-xs border border-gray-200 rounded p-3 resize-y focus:outline-none focus:ring-2 focus:ring-gray-900"
            value={json}
            onChange={(e) => setJson(e.target.value)}
            spellCheck={false}
          />
          {parseError && <p className="text-red-600 text-sm mt-1">{parseError}</p>}
          {registerMutation.isError && (
            <p className="text-red-600 text-sm mt-1">
              Error: {String(registerMutation.error)}
            </p>
          )}
          <div className="mt-3">
            <Button onClick={handleRegister} disabled={registerMutation.isPending}>
              {registerMutation.isPending ? "Registering…" : "Register Deal"}
            </Button>
          </div>
        </SectionCard>
      )}

      {/* In-memory warning */}
      <div className="flex items-start gap-2 px-4 py-3 bg-amber-50 border border-amber-200 rounded-lg text-sm text-amber-800">
        <Database size={16} className="mt-0.5 shrink-0" />
        <span>
          Registry is <strong>in-memory</strong> — deals reset when the backend restarts (Phase 1).
        </span>
      </div>

      {/* Deal list */}
      <SectionCard
        title={`Registered Deals (${deals.length})`}
        action={
          dealsQuery.isLoading ? (
            <span className="text-xs text-gray-400">Loading…</span>
          ) : (
            <button
              onClick={() => qc.invalidateQueries({ queryKey: ["deals"] })}
              className="text-xs text-gray-400 hover:text-gray-700"
            >
              Refresh
            </button>
          )
        }
      >
        {dealsQuery.isError && (
          <p className="text-sm text-red-600">
            Failed to load deals — is the backend running?
          </p>
        )}

        {deals.length === 0 && !dealsQuery.isLoading && (
          <div className="text-center py-12 text-gray-400">
            <Database size={40} className="mx-auto mb-3 opacity-30" />
            <p className="text-sm font-medium">No deals registered yet</p>
            <p className="text-xs mt-1">Click "Register Deal" to add your first deal</p>
          </div>
        )}

        {deals.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs uppercase text-gray-500 border-b border-gray-100">
                  <th className="pb-2 pr-4">Deal</th>
                  <th className="pb-2 pr-4">Class</th>
                  <th className="pb-2 pr-4">Size</th>
                  <th className="pb-2 pr-4">Tranches</th>
                  <th className="pb-2 pr-4">Registered</th>
                  <th className="pb-2 pr-4">Status</th>
                  <th className="pb-2">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {deals.map((deal) => (
                  <tr key={deal.deal_id} className="hover:bg-gray-50 group">
                    <td className="py-3 pr-4">
                      <p className="font-medium text-gray-900">{deal.name}</p>
                      <p className="text-xs text-gray-400 mt-0.5">{deal.issuer}</p>
                      <p className="text-xs font-mono text-gray-300">{deal.deal_id}</p>
                    </td>
                    <td className="py-3 pr-4">
                      <div className="space-y-1">
                        {deal.asset_class && (
                          <Badge variant="info">{deal.asset_class}</Badge>
                        )}
                        {deal.region && (
                          <Badge variant="outline">{deal.region}</Badge>
                        )}
                      </div>
                    </td>
                    <td className="py-3 pr-4 font-mono text-gray-700">
                      {fmt(deal.portfolio_size)}
                    </td>
                    <td className="py-3 pr-4 text-gray-600">{deal.tranche_count}</td>
                    <td className="py-3 pr-4 text-gray-500 text-xs">
                      {timeAgo(deal.registered_at)}
                    </td>
                    <td className="py-3 pr-4">
                      <Badge
                        variant={deal.status === "active" ? "success" : "default"}
                      >
                        {deal.status}
                      </Badge>
                    </td>
                    <td className="py-3">
                      <div className="flex items-center gap-1.5">
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleUse(deal, "/health")}
                          title="Run health check"
                        >
                          <Activity size={13} className="mr-1" />
                          Health
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleUse(deal, "/scenarios")}
                          title="Run scenarios"
                        >
                          <Play size={13} className="mr-1" />
                          Scenarios
                        </Button>
                        <button
                          onClick={() => {
                            if (confirm(`Delete "${deal.name}"?`)) {
                              deleteMutation.mutate(deal.deal_id);
                            }
                          }}
                          className="p-1.5 rounded text-gray-300 hover:text-red-500 hover:bg-red-50 transition-colors"
                          title="Delete deal"
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </SectionCard>
    </div>
  );
}
