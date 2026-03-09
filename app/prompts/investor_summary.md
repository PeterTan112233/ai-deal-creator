# Investor Summary — Drafting Specification

## Purpose

Produce a concise, external-facing overview of a CLO transaction and a single scenario run.
The output is always a **DRAFT** requiring compliance and legal review before distribution.
This document presents facts from deal inputs and engine outputs; it does not make investment recommendations.

---

## Audience

Prospective investors, investor relations. External distribution.
Approval required before any use outside the deal team.

---

## Required Sections

### SECTION: draft-notice
Source tag: [placeholder]
Content: Prominent DRAFT watermark, approval status (pending), mock-engine notice if applicable.
Must appear first. Must not be omitted.

### SECTION: transaction-overview
Source tag: [retrieved]
Content: Deal name, issuer, manager, region, currency, portfolio size, close date.
Pull exclusively from: deal_input.name, deal_input.issuer, deal_input.manager,
  deal_input.region, deal_input.currency, deal_input.collateral.portfolio_size,
  deal_input.close_date.
Do not include assumptions or engine outputs in this section.

### SECTION: portfolio-overview
Source tag: [retrieved]
Content: Collateral pool summary — asset class, size, WAS, WARF, WAL, diversity score, CCC bucket.
Pull exclusively from: deal_input.collateral.*
Omit any field not present in the input (render as "Not provided").

### SECTION: tranche-summary
Source tag: [retrieved]
Content: Simplified tranche table — name, size as % of deal, target rating.
Do NOT include coupon spreads, tranche IDs, or seniority integers in investor-facing output.
Pull from: deal_input.liabilities[].{name, size_pct, target_rating}

### SECTION: scenario-metrics
Source tag: [calculated] or [mock — NOT official] depending on engine mode.
Content: Engine output metrics — equity IRR, AAA size, WAC, OC/IC cushions, equity WAL.
Include scenario name and parameters used. Label every number with its run_id.
If is_mock=True: add bold warning that values are illustrative only.
Pull from: scenario_result.outputs.*, scenario_result.run_id, scenario_request.parameters.*

### SECTION: risk-considerations
Source tag: [generated + placeholder]
Content: Standard CLO risk category headings, anchored where possible to deal data.
Each category must end with a [PLACEHOLDER: ...] line for compliance-drafted disclosure text.
Risk categories required: Credit Risk, Interest Rate Risk, Prepayment / Extension Risk,
  Liquidity Risk, Concentration Risk, Structural / Subordination Risk.
Do NOT make performance claims or predictions. Do NOT assert loss levels.

### SECTION: disclosures
Source tag: [placeholder]
Content: Mandatory disclosure block. All text is a placeholder — no generated language.
Required placeholders:
  [PLACEHOLDER: Regulatory disclosure — insert applicable jurisdiction notice]
  [PLACEHOLDER: Offering memorandum reference — confirm document version]
  [PLACEHOLDER: Legal entity and domicile confirmation]
  [PLACEHOLDER: Forward-looking statements disclaimer]
  [PLACEHOLDER: Past performance disclaimer]

---

## Language Guidelines

**Use:**
- Hedged language: "the scenario assumes", "based on the inputs provided", "as modelled"
- Factual framing: "the portfolio size is", "the scenario applies a default rate of"
- Passive construction for engine outputs: "equity IRR is modelled at X%"

**Avoid:**
- Investment recommendations: "investors should", "this deal offers", "attractive return"
- Performance predictions: "will generate", "expected to return", "guaranteed"
- Unsupported market comparisons: "better than typical", "outperforms peers"
- Finality language: "the deal provides", "the transaction ensures"

---

## Required Disclaimer Markers

The following placeholder lines must appear in every generated draft:
- `[DRAFT — NOT FOR DISTRIBUTION]` in the title header
- `[APPROVAL REQUIRED BEFORE USE]` in the footer
- At least one `[PLACEHOLDER: ...]` per risk category
- `[MOCK ENGINE — NOT OFFICIAL]` if is_mock=True

---

## Approval Requirements

- approved: False at generation
- requires_approval: True (always — this is an external-facing document)
- No content in this draft may be sent to investors, posted, or shared without
  explicit approval via the deal approval workflow

---

## Phase 2: LLM Prompt Interface

When this spec is used as an LLM prompt, inject the following structured context
before the section instructions above:

```
DEAL INPUT:
{{deal_input_json}}

SCENARIO RESULT:
{{scenario_result_json}}

SCENARIO REQUEST:
{{scenario_request_json}}
```

The LLM must:
1. Use only values from the injected structured context
2. Tag every factual statement with its source type
3. Render [PLACEHOLDER: ...] for all compliance gaps
4. Never set approved = True
5. Return structured sections matching the section IDs above
