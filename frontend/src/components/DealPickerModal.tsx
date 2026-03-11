import { useState, useEffect, useRef } from "react";
import { useQuery } from "@tanstack/react-query";
import { listDeals, getDeal, type DealSummary } from "../api/deals";
import { Badge } from "./ui/Badge";
import { Database, Search, X, Loader2 } from "lucide-react";

function fmt(n: number | null): string {
  if (n == null) return "—";
  if (n >= 1_000_000_000) return `$${(n / 1_000_000_000).toFixed(1)}B`;
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(0)}M`;
  return `$${n.toLocaleString()}`;
}

interface Props {
  onSelect: (dealInput: Record<string, unknown>) => void;
  onClose: () => void;
  title?: string;
}

export function DealPickerModal({ onSelect, onClose, title = "Pick a Deal" }: Props) {
  const [query, setQuery] = useState("");
  const [loadingId, setLoadingId] = useState<string | null>(null);
  const searchRef = useRef<HTMLInputElement>(null);

  const dealsQuery = useQuery({
    queryKey: ["deals"],
    queryFn: listDeals,
  });

  // Focus search on mount; close on Escape
  useEffect(() => {
    searchRef.current?.focus();
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const deals: DealSummary[] = (dealsQuery.data ?? []).filter((d) => {
    if (!query) return true;
    const q = query.toLowerCase();
    return (
      d.name.toLowerCase().includes(q) ||
      (d.issuer ?? "").toLowerCase().includes(q) ||
      (d.asset_class ?? "").toLowerCase().includes(q) ||
      (d.region ?? "").toLowerCase().includes(q)
    );
  });

  async function handleSelect(deal: DealSummary) {
    setLoadingId(deal.deal_id);
    try {
      const detail = await getDeal(deal.deal_id);
      onSelect(detail.deal_input);
      onClose();
    } catch {
      setLoadingId(null);
    }
  }

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/40 z-40"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
        <div className="bg-white rounded-xl shadow-2xl w-full max-w-2xl flex flex-col max-h-[80vh]">

          {/* Header */}
          <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
            <div className="flex items-center gap-2">
              <Database size={16} className="text-gray-500" />
              <h2 className="text-sm font-semibold text-gray-900">{title}</h2>
              {dealsQuery.data && (
                <span className="text-xs text-gray-400">
                  {dealsQuery.data.length} registered
                </span>
              )}
            </div>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-gray-700 transition-colors"
            >
              <X size={16} />
            </button>
          </div>

          {/* Search */}
          <div className="px-5 py-3 border-b border-gray-100">
            <div className="relative">
              <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
              <input
                ref={searchRef}
                type="text"
                placeholder="Search by name, issuer, asset class…"
                className="w-full pl-8 pr-3 py-2 text-sm border border-gray-200 rounded-md focus:outline-none focus:ring-2 focus:ring-gray-900"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
            </div>
          </div>

          {/* List */}
          <div className="overflow-y-auto flex-1">
            {dealsQuery.isLoading && (
              <div className="flex items-center justify-center py-12 text-gray-400">
                <Loader2 size={20} className="animate-spin mr-2" />
                Loading deals…
              </div>
            )}

            {dealsQuery.isError && (
              <p className="text-sm text-red-600 px-5 py-4">
                Failed to load deals — is the backend running?
              </p>
            )}

            {!dealsQuery.isLoading && deals.length === 0 && (
              <div className="text-center py-12 text-gray-400">
                <Database size={32} className="mx-auto mb-2 opacity-30" />
                {dealsQuery.data?.length === 0 ? (
                  <>
                    <p className="text-sm font-medium">No deals registered yet</p>
                    <p className="text-xs mt-1">Go to Deal Registry to register a deal first</p>
                  </>
                ) : (
                  <p className="text-sm">No deals match your search</p>
                )}
              </div>
            )}

            {deals.length > 0 && (
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-gray-50 border-b border-gray-100">
                  <tr className="text-left text-xs uppercase text-gray-400">
                    <th className="px-5 py-2.5 font-medium">Deal</th>
                    <th className="px-3 py-2.5 font-medium">Class</th>
                    <th className="px-3 py-2.5 font-medium">Size</th>
                    <th className="px-3 py-2.5 font-medium">Tranches</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  {deals.map((deal) => (
                    <tr
                      key={deal.deal_id}
                      onClick={() => handleSelect(deal)}
                      className="hover:bg-blue-50 cursor-pointer transition-colors group"
                    >
                      <td className="px-5 py-3">
                        <p className="font-medium text-gray-900 group-hover:text-blue-700">
                          {deal.name}
                        </p>
                        <p className="text-xs text-gray-400 mt-0.5">{deal.issuer}</p>
                      </td>
                      <td className="px-3 py-3">
                        <div className="flex flex-col gap-1">
                          {deal.asset_class && (
                            <Badge variant="info">{deal.asset_class}</Badge>
                          )}
                          {deal.region && (
                            <Badge variant="outline">{deal.region}</Badge>
                          )}
                        </div>
                      </td>
                      <td className="px-3 py-3 font-mono text-gray-700">
                        {fmt(deal.portfolio_size)}
                      </td>
                      <td className="px-3 py-3 text-gray-500">
                        {deal.tranche_count}
                        {loadingId === deal.deal_id && (
                          <Loader2 size={13} className="inline ml-2 animate-spin text-blue-500" />
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          {/* Footer */}
          <div className="px-5 py-3 border-t border-gray-100 text-xs text-gray-400">
            Click a row to load its deal JSON · Esc to close
          </div>
        </div>
      </div>
    </>
  );
}
