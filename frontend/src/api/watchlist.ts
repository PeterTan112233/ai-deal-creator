import { client } from "./client";

export interface WatchlistItem {
  item_id: string;
  metric: string;
  operator: string;
  threshold: number;
  label: string;
  deal_id: string | null;
  severity: string;
  created_at: string;
  active: boolean;
}

export interface WatchlistCheckAlert {
  item_id: string;
  label: string;
  metric: string;
  operator: string;
  threshold: number;
  actual_value: number | null;
  severity: string;
  triggered: boolean;
}

export interface WatchlistCheckResult {
  deal_id: string;
  items_checked: number;
  triggered_count: number;
  alerts: WatchlistCheckAlert[];
  audit_events_count: number;
  is_mock: boolean;
  error?: string;
}

export async function getWatchlist(): Promise<WatchlistItem[]> {
  const { data } = await client.get<{ total: number; items: WatchlistItem[] }>("/watchlist");
  return data.items;
}

export async function addWatchlistItem(item: {
  metric: string;
  operator: string;
  threshold: number;
  label?: string;
  severity?: string;
  deal_id?: string;
}): Promise<WatchlistItem> {
  const { data } = await client.post<WatchlistItem>("/watchlist", item);
  return data;
}

export async function deleteWatchlistItem(itemId: string): Promise<void> {
  await client.delete(`/watchlist/${itemId}`);
}

export async function checkDealAgainstWatchlist(
  dealInput: Record<string, unknown>
): Promise<WatchlistCheckResult> {
  const { data } = await client.post<WatchlistCheckResult>("/watchlist/check", {
    deal_input: dealInput,
    actor: "frontend",
  });
  return data;
}
