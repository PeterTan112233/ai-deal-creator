---
name: deal-intake
description: Intake a new deal from raw user inputs or an uploaded pool tape. Validates and normalizes inputs into the canonical deal schema. Use at the start of every new deal creation flow.
---

## When to use

Invoke when:
- A user wants to create a new deal
- A pool tape or parameter set is being imported
- Existing deal data appears inconsistent or incomplete

## Inputs expected

Provide as much of the following as available. Missing required fields will be flagged.

```
deal:
  name, issuer, region, currency

collateral:
  pool_id (or raw pool metrics: portfolio_size, was, warf, wal, diversity_score, ccc_bucket)

liabilities:
  list of tranches: name, seniority, size_pct or size_abs, coupon, target_rating

structural tests:
  oc_tests, ic_tests, ccc_limit

market assumptions:
  default_rate, recovery_rate, spread_shock_bps
```

## Steps when invoked

1. Delegate to **deal-schema-agent**
   - Validate all required fields
   - Normalize to canonical schema
   - Flag missing or out-of-range values
   - Output: `{valid, issues, normalized_deal}`

2. If `valid = false`:
   - Report issues to user
   - Request corrections before proceeding

3. If `valid = true`:
   - Confirm normalized deal object with user
   - Proceed to scenario design or baseline run

## Outputs

```
validation_report:
  valid: true | false
  issues: [list of field problems]
  assumptions_made: [any defaulted fields]

normalized_deal:
  canonical deal object per app/domain/ and app/schemas/
```

## Hard constraints

- Do not proceed to engine submission if `valid = false`
- Do not fill missing financial parameters with guesses
- `coupon` must always be a string (e.g. `"SOFR+145"`), never a float
- Seniority must be unique across tranches
