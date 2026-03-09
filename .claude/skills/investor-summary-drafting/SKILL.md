---
name: investor-summary-drafting
description: Draft an investor summary for a deal that has at least one completed engine run. Uses only grounded engine outputs and approved language sources. Produces a draft marked approved=False. Always run approval-checks before external distribution.
---

## When to use

Invoke when:
- A user requests an investor summary or one-pager
- A deal has at least one completed scenario with `source = "model_runner"`
- Approved language sources are available (or the stub is acceptable for Phase 1)

## Inputs required

```
deal:
  deal_id, name, region, currency, manager

scenario:
  scenario_id, run_id, outputs (source = "model_runner")

approved_language (if available):
  transaction_overview, collateral_highlights, liability_structure,
  key_sensitivities, disclaimer
```

## Steps when invoked

1. Verify scenario has `source = "model_runner"` and non-empty outputs
   - If not: stop and report which inputs are missing

2. Fetch approved language from `approved-language-mcp` (or Phase 1 stub)
   - If unavailable: mark missing sections as `[LANGUAGE PENDING]`

3. Delegate to **narrative-drafting-agent**
   - Compose each required section using only grounded inputs
   - Tag every statement: `[calculated]`, `[retrieved]`, or `[generated]`
   - Attach source footer: scenario_id + run_id

4. Return draft InvestorMaterial object with `approved = False`

## Required output sections

| Section | Source tag |
|---|---|
| Transaction overview | `[retrieved]` |
| Collateral highlights | `[retrieved]` |
| Liability structure summary | `[retrieved]` |
| Key sensitivities | `[generated from calculated]` |
| Disclaimer | `[retrieved — mandatory]` |
| Source footer | scenario_id + run_id |

## Outputs

```
investor_material:
  material_id: <id>
  deal_id: <id>
  material_type: "investor_summary"
  content: <draft text with section labels>
  sources: [scenario_id, run_id, language_source_ids]
  approved: false
  created_at: <timestamp>
```

## Hard constraints

- `approved` must be `false` on all output — never set to true
- Every number must cite a `run_id`
- Every boilerplate section must cite a language source
- Do not add forward-looking statements or unsupported market claims
- Missing disclaimer = do not produce the document; request it first
- Always run **approval-checks** before the draft is distributed
