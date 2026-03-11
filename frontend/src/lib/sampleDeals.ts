// Sample deals shaped to match the backend validation schema.
//
// Rate conventions (matching the mock engine):
//   was, wac  → decimal fractions  (375bps = 0.0375)
//   coupon    → all-in annual rate  (SOFR 5.33% + spread)
//                e.g. SOFR+155bps = 0.0533 + 0.0155 = 0.069
//
// Top-level required: deal_id, name, issuer
// Pool:    collateral.{ pool_id, asset_class, portfolio_size, wal, was, wac, ... }
// Tranches: liabilities.[{ tranche_id, name, seniority, size_pct, coupon, rating }]

export const sampleDeals = {
  usBSL: {
    deal_id: "deal-us-bsl-001",
    name: "Apex CLO 2024-1",
    issuer: "Apex Capital Management",
    region: "US",
    collateral: {
      pool_id: "pool-apex-001",
      asset_class: "BSL",
      portfolio_size: 500000000,
      wal: 5.1,
      warf: 2850,
      was: 0.045,       // 450 bps (decimal)
      wac: 0.099,       // ~9.9% all-in (decimal)
      diversity_score: 78,
      ccc_bucket: 0.042,
      largest_industry_pct: 0.12,
      top_10_obligor_pct: 0.18,
      loan_count: 180,
    },
    liabilities: [
      // coupons = SOFR (5.33%) + spread, expressed as all-in decimal
      { tranche_id: "tr-aaa", name: "Class A", rating: "AAA", seniority: 1, size_pct: 0.62, coupon: 0.069 },
      { tranche_id: "tr-aa",  name: "Class B", rating: "AA",  seniority: 2, size_pct: 0.11, coupon: 0.074 },
      { tranche_id: "tr-a",   name: "Class C", rating: "A",   seniority: 3, size_pct: 0.07, coupon: 0.082 },
      { tranche_id: "tr-bbb", name: "Class D", rating: "BBB", seniority: 4, size_pct: 0.05, coupon: 0.094 },
      { tranche_id: "tr-bb",  name: "Class E", rating: "BB",  seniority: 5, size_pct: 0.04, coupon: 0.126 },
      { tranche_id: "tr-eq",  name: "Equity",  rating: "NR",  seniority: 6, size_pct: 0.11, coupon: 0.0 },
    ],
  },

  euCLO: {
    deal_id: "deal-eu-clo-002",
    name: "Meridian Euro CLO 2024-3",
    issuer: "Meridian Asset Management",
    region: "EU",
    collateral: {
      pool_id: "pool-meridian-002",
      asset_class: "BSL",
      portfolio_size: 400000000,
      wal: 5.4,
      warf: 2920,
      was: 0.042,       // 420 bps (decimal)
      wac: 0.095,       // ~9.5% all-in (decimal)
      diversity_score: 71,
      ccc_bucket: 0.051,
      largest_industry_pct: 0.14,
      top_10_obligor_pct: 0.21,
      loan_count: 145,
    },
    liabilities: [
      { tranche_id: "tr-aaa", name: "Class A", rating: "AAA", seniority: 1, size_pct: 0.62, coupon: 0.068 },
      { tranche_id: "tr-aa",  name: "Class B", rating: "AA",  seniority: 2, size_pct: 0.11, coupon: 0.073 },
      { tranche_id: "tr-a",   name: "Class C", rating: "A",   seniority: 3, size_pct: 0.07, coupon: 0.080 },
      { tranche_id: "tr-bbb", name: "Class D", rating: "BBB", seniority: 4, size_pct: 0.05, coupon: 0.093 },
      { tranche_id: "tr-bb",  name: "Class E", rating: "BB",  seniority: 5, size_pct: 0.04, coupon: 0.123 },
      { tranche_id: "tr-eq",  name: "Equity",  rating: "NR",  seniority: 6, size_pct: 0.11, coupon: 0.0 },
    ],
  },

  mmCLO: {
    deal_id: "deal-mm-clo-003",
    name: "Cornerstone Middle Market CLO I",
    issuer: "Cornerstone Credit Partners",
    region: "US",
    collateral: {
      pool_id: "pool-cornerstone-003",
      asset_class: "MM",
      portfolio_size: 300000000,
      wal: 4.8,
      warf: 3150,
      was: 0.055,       // 550 bps (decimal)
      wac: 0.109,       // ~10.9% all-in (decimal)
      diversity_score: 55,
      ccc_bucket: 0.068,
      largest_industry_pct: 0.18,
      top_10_obligor_pct: 0.28,
      loan_count: 85,
    },
    liabilities: [
      { tranche_id: "tr-aaa", name: "Class A", rating: "AAA", seniority: 1, size_pct: 0.60, coupon: 0.074 },
      { tranche_id: "tr-aa",  name: "Class B", rating: "AA",  seniority: 2, size_pct: 0.11, coupon: 0.081 },
      { tranche_id: "tr-a",   name: "Class C", rating: "A",   seniority: 3, size_pct: 0.07, coupon: 0.089 },
      { tranche_id: "tr-bbb", name: "Class D", rating: "BBB", seniority: 4, size_pct: 0.05, coupon: 0.105 },
      { tranche_id: "tr-bb",  name: "Class E", rating: "BB",  seniority: 5, size_pct: 0.04, coupon: 0.138 },
      { tranche_id: "tr-eq",  name: "Equity",  rating: "NR",  seniority: 6, size_pct: 0.13, coupon: 0.0 },
    ],
  },
};

export const sampleDealsArray = Object.values(sampleDeals);
