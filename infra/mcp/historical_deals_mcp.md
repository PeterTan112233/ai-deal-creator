# MCP Interface Spec — historical-deals

**Server ID:** `historical-deals`
**Phase:** 3
**Mock stub:** None yet — add `mcp/historical_deals/mock_comps.py` in Phase 3 prep
**Priority:** Medium — enables comparables analysis for investor summaries and IC memos.

---

## Purpose

Search and retrieve precedent CLO transactions. Provides the analyst
and document-drafter with factual grounding for comparables language:
"This deal is similar to ABC CLO 2023-1 in pool composition and tranche structure."

All language citing historical deals must reference a `deal_id` from this server.
The analytics-explainer-agent uses this server for version comparison context.

All data returned here must be tagged `[retrieved]`.

---

## Tool contracts

### `search_comps`

Search the historical deal database for comparable transactions.

**Request:**
```json
{
  "filters": {
    "asset_class": "US_BSL",
    "currency": "USD",
    "close_date_range": {
      "from": "2022-01-01",
      "to": "2024-12-31"
    },
    "target_par_range": {
      "min": 400000000,
      "max": 700000000
    },
    "manager_type": "broadly_syndicated",
    "aaa_spread_range": {
      "min": 100,
      "max": 140
    }
  },
  "limit": 10,
  "sort_by": "close_date_desc"
}
```

**Response:**
```json
{
  "source": "historical_deals_db",
  "retrieved_at": "2024-01-15T10:00:00Z",
  "total_matches": 47,
  "results": [
    {
      "deal_id": "hist-us-bsl-2023-001",
      "deal_name": "Meridian CLO 2023-1",
      "issuer": "Meridian Capital",
      "asset_class": "US_BSL",
      "currency": "USD",
      "close_date": "2023-11-14",
      "target_par": 500000000,
      "aaa_spread_bps": 117,
      "equity_irr": 0.138,
      "similarity_score": 0.91
    }
  ]
}
```

**Filters (all optional):**

| Field | Type | Description |
|---|---|---|
| `asset_class` | string | `US_BSL`, `EUR_CLO`, `US_MM`, etc. |
| `currency` | string | `USD`, `EUR`, `GBP` |
| `close_date_range` | object | ISO date range |
| `target_par_range` | object | `{min, max}` in currency units |
| `manager_type` | string | `broadly_syndicated`, `middle_market`, `static` |
| `aaa_spread_range` | object | `{min, max}` in basis points |
| `min_similarity` | float | Minimum similarity score (0–1) |
| `issuer` | string | Filter by deal manager name |

**Errors:**
- `400 INVALID_FILTER` — unrecognised filter field or out-of-range value
- `503 HISTORICAL_DB_UNAVAILABLE`

---

### `get_deal_summary`

Retrieve structured summary metrics for a specific historical deal.

**Request:**
```json
{ "deal_id": "hist-us-bsl-2023-001" }
```

**Response:**
```json
{
  "deal_id": "hist-us-bsl-2023-001",
  "deal_name": "Meridian CLO 2023-1",
  "issuer": "Meridian Capital",
  "source": "historical_deals_db",
  "retrieved_at": "2024-01-15T10:00:00Z",
  "deal_summary": {
    "asset_class": "US_BSL",
    "currency": "USD",
    "close_date": "2023-11-14",
    "target_par": 500000000,
    "reinvestment_period_yrs": 4,
    "non_call_period_yrs": 2
  },
  "pool_summary": {
    "was": 370.0,
    "warf": 2820,
    "wal": 4.1,
    "wac": 0.041,
    "diversity_score": 68,
    "ccc_bucket": 0.048
  },
  "tranche_summary": [
    {
      "name": "Class A",
      "rating": "AAA",
      "size_pct": 0.62,
      "spread_bps": 117,
      "seniority": 1
    }
  ],
  "output_summary": {
    "equity_irr": 0.138,
    "aaa_spread_bps": 117,
    "oc_cushion_aaa": 0.055
  }
}
```

**Errors:**
- `404 DEAL_NOT_FOUND`
- `503 HISTORICAL_DB_UNAVAILABLE`

---

### `compare_deals`

Side-by-side structured comparison of two or more historical deals.

**Request:**
```json
{
  "deal_ids": ["hist-us-bsl-2023-001", "hist-us-bsl-2022-005"],
  "fields": ["equity_irr", "aaa_spread_bps", "diversity_score", "ccc_bucket"]
}
```

**Response:**
```json
{
  "source": "historical_deals_db",
  "retrieved_at": "2024-01-15T10:00:00Z",
  "deals": {
    "hist-us-bsl-2023-001": {
      "deal_name": "Meridian CLO 2023-1",
      "equity_irr": 0.138,
      "aaa_spread_bps": 117,
      "diversity_score": 68,
      "ccc_bucket": 0.048
    },
    "hist-us-bsl-2022-005": {
      "deal_name": "Parkway CLO 2022-5",
      "equity_irr": 0.152,
      "aaa_spread_bps": 132,
      "diversity_score": 65,
      "ccc_bucket": 0.051
    }
  },
  "diffs": {
    "equity_irr": { "delta": -0.014, "direction": "lower" },
    "aaa_spread_bps": { "delta": -15, "direction": "tighter" }
  }
}
```

**Errors:**
- `400 TOO_FEW_DEALS` — fewer than 2 deal IDs provided
- `400 TOO_MANY_DEALS` — more than 10 deal IDs provided
- `404 DEAL_NOT_FOUND` — one or more deal IDs not found
- `503 HISTORICAL_DB_UNAVAILABLE`

---

## Security and provenance rules

- All responses carry `"source": "historical_deals_db"`. Any comps language
  must cite `deal_id` and `deal_name`. Tag: `[retrieved]`.
- This server is read-only. No write tools are exposed.
- Comps data is informational context only — it must never be used as a
  substitute for official engine outputs on the current deal.

---

## Phase timeline

| Phase | Action |
|---|---|
| 1–2 (current) | No comps integration — document-drafter uses `[PLACEHOLDER: add comparables]` |
| 3 prep | Add `mcp/historical_deals/mock_comps.py` with 5 sample deals |
| 3 | Implement `infra/mcp/historical_deals/server.py`; register in `.claude/settings.json` |
| 3 | Update analytics-explainer-agent and document-drafter to call `search_comps` |
| 4 | Add `similarity_score` model for better comp ranking |

---

## Open questions

1. What is the source database for historical CLO data? (Intex, Bloomberg, proprietary warehouse?)
2. Is deal data available at the tranche level (individual spreads and sizes)?
3. What is the data coverage — only internally managed deals or market-wide?
4. Should `compare_deals` include a current in-progress deal, or historical only?
