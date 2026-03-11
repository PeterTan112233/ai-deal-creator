import { client } from "./client";

export interface DealSummary {
  deal_id: string;
  name: string;
  issuer: string;
  region: string | null;
  currency: string;
  manager: string | null;
  registered_at: string;
  status: string;
  portfolio_size: number | null;
  asset_class: string | null;
  tranche_count: number;
  pipeline_count: number;
  last_pipeline_at: string | null;
}

export interface DealDetail extends DealSummary {
  deal_input: Record<string, unknown>;
  last_pipeline_result: Record<string, unknown> | null;
}

// Convert the unified deal_input dict (used by workflows) into CreateDealRequest shape
function dealInputToCreateRequest(input: Record<string, unknown>) {
  const c = input.collateral as Record<string, unknown>;
  const liabs = (input.liabilities as Record<string, unknown>[]) ?? [];
  return {
    deal: {
      deal_id: input.deal_id,
      name: input.name,
      issuer: input.issuer,
      region: input.region ?? null,
      currency: (input.currency as string) ?? "USD",
      manager: input.manager ?? null,
    },
    collateral: {
      collateral_id: `coll-${input.deal_id}`,
      pool_id: c.pool_id,
      asset_class: c.asset_class,
      portfolio_size: c.portfolio_size,
      was: c.was ?? null,
      warf: c.warf ?? null,
      wal: c.wal ?? null,
      diversity_score: c.diversity_score,
      ccc_bucket: c.ccc_bucket,
    },
    tranches: liabs.map((t) => ({
      tranche_id: t.tranche_id,
      name: t.name,
      seniority: t.seniority,
      size_pct: t.size_pct ?? null,
      size_abs: t.size_abs ?? null,
      coupon: t.coupon != null ? String(t.coupon) : null,
      target_rating: t.rating ?? null,
    })),
    actor: "frontend",
  };
}

export async function listDeals(): Promise<DealSummary[]> {
  const { data } = await client.get<{ total: number; deals: DealSummary[] }>("/deals");
  return data.deals;
}

export async function getDeal(dealId: string): Promise<DealDetail> {
  const { data } = await client.get<DealDetail>(`/deals/${dealId}`);
  return data;
}

export async function registerDeal(
  dealInput: Record<string, unknown>
): Promise<{ deal_id: string; name: string; deal_input: Record<string, unknown> }> {
  const body = dealInputToCreateRequest(dealInput);
  const { data } = await client.post("/deals", body);
  return data;
}

export async function deleteDeal(dealId: string): Promise<void> {
  await client.delete(`/deals/${dealId}`);
}
