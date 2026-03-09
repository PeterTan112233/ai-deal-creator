# Data Model — AI Deal Creator

The system uses a canonical deal object as the single source of truth for
all deal state. This model is defined in `app/domain/` (Python dataclasses)
and validated by `app/schemas/` (Pydantic schemas).

---

## Canonical deal object

Full JSON representation. See `data/samples/sample_deal.json` for a populated example.

```json
{
  "deal_id": "string",
  "deal_name": "string",
  "currency": "USD | EUR | GBP",
  "region": "US | EU | APAC",
  "manager": "string",
  "collateral": { ... },
  "liabilities": [ ... ],
  "structural_tests": { ... },
  "market_assumptions": { ... },
  "workflow": { ... }
}
```

---

## Field groups

### Deal (top level)

| Field | Type | Description |
|---|---|---|
| `deal_id` | string | Unique deal identifier |
| `deal_name` | string | Human-readable name |
| `currency` | string | ISO 4217 code |
| `region` | string | Regulatory / market region |
| `manager` | string | CLO manager name |
| `status` | string | `draft` \| `approved` \| `published` |
| `version` | int | Monotonically increasing version counter |

**Domain file:** `app/domain/deal.py`
**Schema file:** `app/schemas/deal_schema.py`

---

### Collateral

The underlying loan portfolio backing the CLO.

| Field | Type | Description |
|---|---|---|
| `pool_id` | string | Reference to pool tape in portfolio-data-mcp |
| `portfolio_size` | float | Total par amount in deal currency |
| `was` | float | Weighted average spread (decimal, e.g. 0.042 = 4.2%) |
| `warf` | float | Weighted average rating factor |
| `wal` | float | Weighted average life in years |
| `diversity_score` | float | Moody's diversity score |
| `ccc_bucket` | float | CCC/Caa assets as fraction of portfolio (max 0.075) |
| `concentrations` | object | Top obligor %, top industry % |
| `reinvestment_assumptions` | object | Reinvestment criteria and rate assumptions |

**Domain file:** `app/domain/collateral.py`
**Schema file:** `app/schemas/collateral_schema.py`
**Validation:** `portfolio_size > 0`, `ccc_bucket ≤ 1`, `diversity_score ≥ 0`

---

### Liabilities (tranches)

Ordered by seniority (1 = most senior). Each tranche has:

| Field | Type | Description |
|---|---|---|
| `tranche_id` | string | Unique identifier |
| `name` | string | e.g. `AAA`, `AA`, `Equity` |
| `seniority` | int | 1 = senior, increasing downward; must be unique per structure |
| `size_pct` | float | Fraction of total deal size (e.g. 0.61) |
| `size_abs` | float | Absolute size in deal currency (alternative to size_pct) |
| `coupon` | string | Coupon expression, e.g. `"SOFR+145"` or `"6.25%"` — NOT a computed number |
| `target_rating` | string | e.g. `"Aaa"`, `"Aa2"`, `"Ba3"` |
| `payment_frequency` | string | `quarterly` \| `semi-annual` |
| `call_period_years` | float | Non-call period length |

**Domain file:** `app/domain/tranche.py`
**Schema file:** `app/schemas/tranche_schema.py`
**Validation:** must have `size_pct` OR `size_abs` (not neither); seniority must be unique within structure

> **Note:** `coupon` is always a string expression — never a computed float. Actual coupon economics come from the cashflow engine.

---

### Structural tests

Coverage and concentration test thresholds.

| Field | Type | Description |
|---|---|---|
| `oc_tests` | object | OC threshold per tranche, e.g. `{"AAA": 1.42}` |
| `ic_tests` | object | IC threshold per tranche, e.g. `{"AAA": 1.25}` |
| `ccc_limit` | float | CCC bucket maximum (default 0.075) |
| `concentration_limits` | object | Sector and obligor limit thresholds |
| `trigger_thresholds` | object | Trigger levels for diversion of cashflows |

**Domain file:** `app/domain/structural_tests.py`
**Schema file:** `app/schemas/structural_tests_schema.py`

---

### Market assumptions

Stress and pricing assumptions for scenario runs.

| Field | Type | Description |
|---|---|---|
| `default_rate` | float | Annual default rate assumption (e.g. 0.03 = 3%) |
| `recovery_rate` | float | Blended recovery assumption (e.g. 0.65 = 65%) |
| `spread_shock_bps` | float | Spread shock in basis points |
| `prepayment_rate` | float | Annual CPR assumption |
| `funding_cost_bps` | float | Additional funding cost overlay |

**Domain file:** `app/domain/market_assumptions.py`
**Schema file:** `app/schemas/market_assumptions_schema.py`

> **Note:** These are inputs to the engine, not outputs. Official stress results come from the cashflow engine via MCP.

---

### Workflow

Deal-level state tracking.

| Field | Type | Description |
|---|---|---|
| `status` | string | `draft` \| `approved` \| `published` |
| `version` | int | Version counter — increments on material changes |
| `approvals` | array | List of Approval records |

---

### Scenario

A parameterized engine run.

| Field | Type | Description |
|---|---|---|
| `scenario_id` | string | Unique identifier |
| `deal_id` | string | Parent deal |
| `name` | string | Human label, e.g. `"Baseline"`, `"Stressed recoveries"` |
| `parameters` | object | Engine input parameters — must be non-empty |
| `outputs` | object | Official engine outputs — populated after run |
| `source` | string | Always `"model_runner"` for official runs |
| `status` | string | `draft` \| `official` \| `rejected` |
| `run_id` | string | Engine run reference ID |
| `created_at` | datetime | When the run was submitted |

**Domain file:** `app/domain/scenario.py`
**Schema file:** `app/schemas/scenario_schema.py`
**Validation:** `parameters` must be non-empty before submission; `outputs` must have `source = "model_runner"` before comparison

---

### Approval

A sign-off record that gates publication.

| Field | Type | Description |
|---|---|---|
| `approval_id` | string | Unique identifier |
| `deal_id` | string | Parent deal |
| `target_type` | string | `deal` \| `investor_material` \| `publish` |
| `target_id` | string | ID of the object being approved |
| `status` | string | `pending` \| `approved` \| `rejected` |
| `approver` | string | Identity of approver |
| `approved_at` | datetime | Timestamp of approval |

**Domain file:** `app/domain/approval.py`

---

### InvestorMaterial

A generated document pending approval.

| Field | Type | Description |
|---|---|---|
| `material_id` | string | Unique identifier |
| `deal_id` | string | Parent deal |
| `material_type` | string | `investor_summary` \| `faq` \| `committee_memo` |
| `content` | string | Draft text |
| `sources` | array | Source object IDs (scenario_id, doc_id, etc.) |
| `approved` | bool | Always `False` until compliance review clears it |
| `created_at` | datetime | Draft creation time |

**Domain file:** `app/domain/investor_material.py`

---

## Validation rules (summary)

| Rule | Enforced in |
|---|---|
| `portfolio_size > 0` | CollateralSchema |
| `ccc_bucket ≤ 7.5%` checked by pool validation | mock_portfolio.validate_pool |
| `diversity_score ≥ 30` checked by pool validation | mock_portfolio.validate_pool |
| Tranche must have size_pct or size_abs | TrancheSchema |
| Seniority must be unique within structure | StructureSchema |
| Scenario parameters must be non-empty | ScenarioSchema |
| Scenario source must be "model_runner" before comparison | compare_scenarios_workflow |
| InvestorMaterial.approved must be True before publish | pre_tool_use hook (Phase 3) |
