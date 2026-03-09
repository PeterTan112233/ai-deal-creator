# MCP Interface Spec — portfolio-data

**Server ID:** `portfolio-data`
**Phase:** 2 (alongside cashflow-engine)
**Mock stub:** `mcp/portfolio_data/mock_portfolio.py`
**Priority:** High — collateral validation gates every scenario submission.

---

## Purpose

Retrieve and validate pool tape data. This server owns all collateral-level
information: aggregate pool metrics (WAS, WARF, WAL, CCC bucket, diversity
score) and obligor-level attributes when needed for granular analysis.

Claude uses this server to:
- Load a pool by ID before structuring a scenario
- Validate a submitted pool payload before sending it to the cashflow engine
- List available pool tape versions for a deal

All pool data returned here must be tagged `[retrieved]`.

---

## Tool contracts

### `get_pool`

Retrieve aggregate pool metrics by pool ID.

**Request:**
```json
{ "pool_id": "pool-001" }
```

**Response:**
```json
{
  "pool_id": "pool-001",
  "deal_id": "deal-us-bsl-001",
  "version": "2024-01-15",
  "currency": "USD",
  "target_par": 500000000,
  "asset_class": "US_BSL",
  "source": "portfolio_system",
  "retrieved_at": "2024-01-15T10:00:00Z",
  "metrics": {
    "was": 375.5,
    "warf": 2850,
    "wal": 4.2,
    "wac": 0.042,
    "diversity_score": 62,
    "ccc_bucket": 0.055,
    "fixed_rate_pct": 0.08,
    "top_10_obligor_pct": 0.18
  }
}
```

**Errors:**
- `404 POOL_NOT_FOUND` — `pool_id` does not exist in the portfolio system
- `410 POOL_STALE` — pool tape is older than the configured staleness threshold
- `503 PORTFOLIO_SYSTEM_UNAVAILABLE`

---

### `validate_pool`

Validate a pool payload against schema rules and eligibility criteria before
submitting it to the cashflow engine.

**Request:**
```json
{
  "pool_payload": {
    "pool_id": "pool-001",
    "was": 375.5,
    "warf": 2850,
    "wal": 4.2,
    "wac": 0.042,
    "diversity_score": 62,
    "ccc_bucket": 0.055
  },
  "deal_type": "US_CLO"
}
```

**Response (valid):**
```json
{
  "valid": true,
  "issues": [],
  "warnings": [],
  "source": "portfolio_system"
}
```

**Response (invalid):**
```json
{
  "valid": false,
  "issues": [
    {
      "field": "ccc_bucket",
      "severity": "error",
      "code": "EXCEEDS_CCC_LIMIT",
      "message": "CCC bucket 7.5% exceeds deal eligibility limit of 7.0%."
    }
  ],
  "warnings": [
    {
      "field": "diversity_score",
      "severity": "warning",
      "code": "LOW_DIVERSITY",
      "message": "Diversity score 48 is below the typical minimum of 50 for US CLO."
    }
  ],
  "source": "portfolio_system"
}
```

**Errors:**
- `400 INVALID_REQUEST` — payload missing required fields
- `503 PORTFOLIO_SYSTEM_UNAVAILABLE`

---

### `list_pool_versions`

List all available pool tape versions for a given deal.

**Request:**
```json
{ "deal_id": "deal-us-bsl-001" }
```

**Response:**
```json
{
  "deal_id": "deal-us-bsl-001",
  "source": "portfolio_system",
  "versions": [
    {
      "pool_id": "pool-001",
      "version": "2024-01-15",
      "tape_date": "2024-01-15",
      "asset_count": 247,
      "par_amount": 498500000,
      "is_current": true
    },
    {
      "pool_id": "pool-001-v0",
      "version": "2024-01-01",
      "tape_date": "2024-01-01",
      "asset_count": 241,
      "par_amount": 495000000,
      "is_current": false
    }
  ]
}
```

**Errors:**
- `404 DEAL_NOT_FOUND`
- `503 PORTFOLIO_SYSTEM_UNAVAILABLE`

---

### `get_obligor`

Retrieve obligor-level attributes for granular pool analysis.
*(Phase 2 — not in mock stub yet)*

**Request:**
```json
{
  "obligor_id": "ob-001",
  "pool_id": "pool-001"
}
```

**Response:**
```json
{
  "obligor_id": "ob-001",
  "pool_id": "pool-001",
  "source": "portfolio_system",
  "attributes": {
    "industry": "Technology",
    "country": "US",
    "par_amount": 2500000,
    "coupon_rate": 0.045,
    "maturity_date": "2028-07-15",
    "moody_rating": "B2",
    "sp_rating": "B",
    "fixed_rate": false,
    "secured": true
  }
}
```

**Errors:**
- `404 OBLIGOR_NOT_FOUND`
- `403 NOT_ENTITLED` — caller does not have access to obligor-level data for this pool

---

## Security and provenance rules

- All responses carry `"source": "portfolio_system"`. Pool data in any
  analyst output must be tagged `[retrieved]` with the `pool_id` and
  `version` cited.
- `get_obligor` is subject to entitlement check. The pre_tool_use hook
  must intercept calls to this tool and verify the user role has `pool_read`
  permission before allowing (Phase 3).
- Pool tapes must not be written back through this server — it is read-only.
  Pool updates go through the deal-schema-agent and a separate ingest pipeline.

---

## Phase timeline

| Phase | Action |
|---|---|
| 1 (current) | Mock stub in `mcp/portfolio_data/mock_portfolio.py` |
| 2 | Implement `infra/mcp/portfolio_data/server.py`; register in `.claude/settings.json` |
| 2 | Replace mock imports in deal setup workflows |
| 2 | `get_obligor` tool implemented and tested |
| 3 | Entitlement gate on `get_obligor` via entitlement-policy MCP |

---

## Migration path from mock stub

1. Implement `infra/mcp/portfolio_data/server.py` connecting to the live
   portfolio management system
2. Ensure response shapes match the contracts above exactly (no extra fields
   that could confuse the model)
3. Add to `.claude/settings.json`:
   ```json
   "mcpServers": {
     "portfolio-data": {
       "command": "python",
       "args": ["infra/mcp/portfolio_data/server.py"]
     }
   }
   ```
4. Update `app/domain/pool.py` and the deal-schema-agent to call this tool
   instead of the mock module
5. Keep mock stub for unit tests

---

## Open questions

1. What is the source portfolio management system? (Intex, Bloomberg PORT, proprietary?)
2. What is the staleness threshold for `POOL_STALE`? Deal lifecycle may be days to weeks.
3. Should `validate_pool` enforce CLO eligibility rules (static) or call a rules engine?
4. Is obligor-level data available at deal structuring time, or only at close?
