# IC Memo — Drafting Specification

## Purpose

Produce an internal credit committee memo summarising deal structure, collateral quality,
scenario results, and open items for committee discussion.
The output is always an **INTERNAL DRAFT** requiring review and approval before distribution.
This document is for internal deal team and committee use only.

---

## Audience

Internal credit committee, deal team, risk reviewers. Not for external distribution.
Approval required before distribution even to internal stakeholders outside the deal team.

---

## Required Sections

### SECTION: internal-notice
Source tag: [placeholder]
Content: INTERNAL DRAFT watermark, deal name, date, approval status (pending),
  mock-engine notice if applicable. Must appear first.

### SECTION: deal-overview
Source tag: [retrieved]
Content: Full deal metadata — deal_id, name, issuer, manager, region, currency,
  close date, notes. Present all available fields; mark absent fields as "Not provided".
Pull from: deal_input.*  (top-level fields only)

### SECTION: collateral-analysis
Source tag: [retrieved]
Content: Full collateral pool metrics — asset class, portfolio size, WAS, WARF, WAL,
  diversity score, CCC bucket, top obligor concentration, top industry concentration.
For each metric present, note the structural test limit where one exists
  (e.g., CCC bucket vs ccc_limit from structural_tests).
Pull from: deal_input.collateral.*, deal_input.structural_tests.ccc_limit

### SECTION: liability-structure
Source tag: [retrieved]
Content: Full tranche table — tranche_id, name, seniority, size_pct, coupon,
  target_rating for each tranche. Include equity tranche.
Compute aggregate: sum of size_pct across all tranches (flag if != 1.0).
Pull from: deal_input.liabilities[].*

### SECTION: scenario-parameters
Source tag: [retrieved]
Content: Full scenario specification — name, type, default_rate, recovery_rate,
  spread_shock_bps, any assumptions_made, any flagged_ambiguities.
Distinguish user-provided parameters from service-applied defaults.
Pull from: scenario_request.* (or deal_input.market_assumptions.* if no request)

### SECTION: scenario-outputs
Source tag: [calculated] or [mock — NOT official] depending on engine mode.
Content: Full engine output table — all output keys with values and units.
Include run_id, scenario_id, executed_at, engine source.
If is_mock=True: bold warning that all values are synthetic placeholders.
If engine_warnings present: list all warnings verbatim.
Pull from: scenario_result.*

### SECTION: structural-test-analysis
Source tag: [retrieved] + [calculated/mock]
Content: Compare scenario outputs to structural test thresholds.
For each OC test: list threshold from structural_tests.oc_tests, cushion from scenario_result.
For each IC test: same pattern.
CCC bucket vs ccc_limit.
State directionally whether cushions appear adequate, tight, or not available for analysis.
Hedge with is_mock caveat if applicable.
Do NOT assert pass/fail on mock outputs — only report the data.
Pull from: deal_input.structural_tests.*, scenario_result.outputs.{oc_cushion_aaa, ic_cushion_aaa}

### SECTION: scenario-comparison
Source tag: [calculated/mock] + [generated]
Content: If comparison_result is provided, summarise key input and output changes.
Present the factual diff first ([retrieved]/[calculated]), then likely drivers ([generated]).
If no comparison_result: render as "[DATA NOT PROVIDED — no comparison scenario available]".
Pull from: comparison_result.* (optional)

### SECTION: open-items
Source tag: [placeholder]
Content: Placeholder list for committee discussion items.
Minimum placeholders:
  [PLACEHOLDER: List open diligence items]
  [PLACEHOLDER: Confirm rating agency methodology applied]
  [PLACEHOLDER: Legal documentation status]
  [PLACEHOLDER: Any waivers or exceptions to structural tests]

### SECTION: approval-gate
Source tag: [placeholder]
Content: Approval status block — always shows approved=False at draft creation.
Must include:
  - Current status: PENDING APPROVAL
  - Required approvers: [PLACEHOLDER: list required approvers]
  - Next step: [PLACEHOLDER: describe review and approval process]
  - Distribution restriction: INTERNAL USE ONLY until approved

---

## Language Guidelines

**Use:**
- Technical precision: exact field names, units, and values from structured inputs
- Conditional framing: "if the scenario is representative of...", "the model assumes..."
- Hedged interpretation: "may suggest", "appears adequate based on modelled cushion"
- Active gap identification: "data not available", "requires confirmation"

**Avoid:**
- Investment recommendations or buy/sell language
- Assertions about real-world performance based on mock engine outputs
- Definitive statements about rating outcomes: "will achieve Aaa" — only "targets Aaa"
- Language implying the memo is final or approved

---

## Required Disclaimer Markers

- `[INTERNAL DRAFT — NOT FOR EXTERNAL DISTRIBUTION]` in header
- `[APPROVAL REQUIRED BEFORE DISTRIBUTION]` in footer
- `[MOCK ENGINE — NOT OFFICIAL]` on every output metric if is_mock=True
- `approved = False` explicitly stated in approval-gate section

---

## Approval Requirements

- approved: False at generation
- requires_approval: True (always — even for internal distribution)
- The approval-gate section must be present and must show pending status

---

## Phase 2: LLM Prompt Interface

When this spec is used as an LLM prompt, inject the following structured context:

```
DEAL INPUT:
{{deal_input_json}}

SCENARIO RESULT:
{{scenario_result_json}}

SCENARIO REQUEST:
{{scenario_request_json}}

COMPARISON RESULT (optional):
{{comparison_result_json}}
```

The LLM must:
1. Use only values from the injected structured context
2. Tag every factual statement with its source type
3. Never set approved = True or imply distribution readiness
4. Render [PLACEHOLDER: ...] for all gaps requiring human input
5. Return structured sections matching the section IDs above
6. If a section's data is not available, render "[DATA NOT PROVIDED]" rather than inferring
