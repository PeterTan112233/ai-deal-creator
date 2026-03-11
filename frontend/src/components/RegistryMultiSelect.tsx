import { useQuery } from "@tanstack/react-query";
import { listDeals, getDeal, type DealSummary } from "../api/deals";
import { Badge } from "./ui/Badge";
import { Loader2, Database } from "lucide-react";

function fmt(n: number | null): string {
  if (n == null) return "—";
  if (n >= 1_000_000_000) return `$${(n / 1_000_000_000).toFixed(1)}B`;
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(0)}M`;
  return `$${n.toLocaleString()}`;
}

interface Props {
  selected: Set<string>;          // deal_ids
  onChange: (next: Set<string>) => void;
  loadingIds?: Set<string>;       // deal_ids being fetched
}

export function RegistryMultiSelect({ selected, onChange, loadingIds }: Props) {
  const dealsQuery = useQuery({ queryKey: ["deals"], queryFn: listDeals });
  const deals: DealSummary[] = dealsQuery.data ?? [];

  function toggle(id: string) {
    const next = new Set(selected);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    onChange(next);
  }

  function selectAll() {
    onChange(new Set(deals.map((d) => d.deal_id)));
  }

  function clearAll() {
    onChange(new Set());
  }

  if (dealsQuery.isLoading) {
    return (
      <div className="flex items-center gap-2 py-4 text-gray-400 text-sm">
        <Loader2 size={14} className="animate-spin" /> Loading registry…
      </div>
    );
  }

  if (dealsQuery.isError) {
    return (
      <p className="text-sm text-red-600 py-2">Failed to load registry — is the backend running?</p>
    );
  }

  if (deals.length === 0) {
    return (
      <div className="text-center py-8 text-gray-400">
        <Database size={28} className="mx-auto mb-2 opacity-30" />
        <p className="text-sm font-medium">No deals registered</p>
        <p className="text-xs mt-0.5">Go to Deal Registry to add deals first</p>
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs text-gray-500">
          {selected.size} of {deals.length} selected
        </span>
        <div className="flex gap-2">
          <button
            onClick={selectAll}
            className="text-xs text-gray-500 hover:text-gray-900"
          >
            All
          </button>
          <span className="text-gray-300">·</span>
          <button
            onClick={clearAll}
            className="text-xs text-gray-500 hover:text-gray-900"
          >
            None
          </button>
        </div>
      </div>

      <div className="border border-gray-100 rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50">
            <tr className="text-left text-xs uppercase text-gray-400">
              <th className="w-8 px-3 py-2" />
              <th className="px-3 py-2">Deal</th>
              <th className="px-3 py-2">Class</th>
              <th className="px-3 py-2">Size</th>
              <th className="px-3 py-2">Tranches</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50">
            {deals.map((deal) => {
              const checked = selected.has(deal.deal_id);
              const loading = loadingIds?.has(deal.deal_id);
              return (
                <tr
                  key={deal.deal_id}
                  onClick={() => toggle(deal.deal_id)}
                  className={`cursor-pointer transition-colors ${
                    checked ? "bg-blue-50" : "hover:bg-gray-50"
                  }`}
                >
                  <td className="px-3 py-2.5 text-center">
                    {loading ? (
                      <Loader2 size={13} className="animate-spin text-blue-500 mx-auto" />
                    ) : (
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() => toggle(deal.deal_id)}
                        onClick={(e) => e.stopPropagation()}
                        className="rounded"
                      />
                    )}
                  </td>
                  <td className="px-3 py-2.5">
                    <p className="font-medium text-gray-900">{deal.name}</p>
                    <p className="text-xs text-gray-400">{deal.issuer}</p>
                  </td>
                  <td className="px-3 py-2.5">
                    <div className="flex flex-col gap-1">
                      {deal.asset_class && <Badge variant="info">{deal.asset_class}</Badge>}
                      {deal.region && <Badge variant="outline">{deal.region}</Badge>}
                    </div>
                  </td>
                  <td className="px-3 py-2.5 font-mono text-gray-700">
                    {fmt(deal.portfolio_size)}
                  </td>
                  <td className="px-3 py-2.5 text-gray-500">
                    {deal.tranche_count}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// Helper: resolve selected deal_ids → full deal_input objects
export async function resolveSelectedDeals(
  dealIds: string[]
): Promise<Record<string, unknown>[]> {
  const results = await Promise.all(dealIds.map((id) => getDeal(id)));
  return results.map((r) => r.deal_input);
}
