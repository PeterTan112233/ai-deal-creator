// Sample deals shaped to match the backend validation schema:
//   deal_id, name, issuer  (top-level required)
//   collateral: { pool_id, asset_class, portfolio_size, wal, was, ... }
//   liabilities: [{ tranche_id, name, seniority, size_pct, coupon, rating }]

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
      was: 3.75,
      wac: 7.2,
      diversity_score: 78,
      ccc_bucket: 0.042,
      largest_industry_pct: 0.12,
      top_10_obligor_pct: 0.18,
      loan_count: 180,
    },
    liabilities: [
      { tranche_id: "tr-aaa", name: "Class A", rating: "AAA", seniority: 1, size_pct: 0.62, coupon: 0.0155 },
      { tranche_id: "tr-aa",  name: "Class B", rating: "AA",  seniority: 2, size_pct: 0.11, coupon: 0.0210 },
      { tranche_id: "tr-a",   name: "Class C", rating: "A",   seniority: 3, size_pct: 0.07, coupon: 0.0285 },
      { tranche_id: "tr-bbb", name: "Class D", rating: "BBB", seniority: 4, size_pct: 0.05, coupon: 0.0410 },
      { tranche_id: "tr-bb",  name: "Class E", rating: "BB",  seniority: 5, size_pct: 0.04, coupon: 0.0725 },
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
      was: 3.9,
      wac: 6.8,
      diversity_score: 71,
      ccc_bucket: 0.051,
      largest_industry_pct: 0.14,
      top_10_obligor_pct: 0.21,
      loan_count: 145,
    },
    liabilities: [
      { tranche_id: "tr-aaa", name: "Class A", rating: "AAA", seniority: 1, size_pct: 0.62, coupon: 0.0145 },
      { tranche_id: "tr-aa",  name: "Class B", rating: "AA",  seniority: 2, size_pct: 0.11, coupon: 0.0200 },
      { tranche_id: "tr-a",   name: "Class C", rating: "A",   seniority: 3, size_pct: 0.07, coupon: 0.0270 },
      { tranche_id: "tr-bbb", name: "Class D", rating: "BBB", seniority: 4, size_pct: 0.05, coupon: 0.0400 },
      { tranche_id: "tr-bb",  name: "Class E", rating: "BB",  seniority: 5, size_pct: 0.04, coupon: 0.0700 },
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
      was: 4.5,
      wac: 8.1,
      diversity_score: 55,
      ccc_bucket: 0.068,
      largest_industry_pct: 0.18,
      top_10_obligor_pct: 0.28,
      loan_count: 85,
    },
    liabilities: [
      { tranche_id: "tr-aaa", name: "Class A", rating: "AAA", seniority: 1, size_pct: 0.60, coupon: 0.0210 },
      { tranche_id: "tr-aa",  name: "Class B", rating: "AA",  seniority: 2, size_pct: 0.11, coupon: 0.0280 },
      { tranche_id: "tr-a",   name: "Class C", rating: "A",   seniority: 3, size_pct: 0.07, coupon: 0.0360 },
      { tranche_id: "tr-bbb", name: "Class D", rating: "BBB", seniority: 4, size_pct: 0.05, coupon: 0.0520 },
      { tranche_id: "tr-bb",  name: "Class E", rating: "BB",  seniority: 5, size_pct: 0.04, coupon: 0.0850 },
      { tranche_id: "tr-eq",  name: "Equity",  rating: "NR",  seniority: 6, size_pct: 0.13, coupon: 0.0 },
    ],
  },
};

export const sampleDealsArray = Object.values(sampleDeals);
