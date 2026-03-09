# Workflows — AI Deal Creator

Three primary workflows are in scope for the MVP. Each workflow maps to one or
more orchestration functions in `app/workflows/` and a sequence of agent delegations.

---

## 1. New deal creation

**User intent:** "Create a CLO from this pool with these targets."

**Entry point:** `app/workflows/create_deal_workflow.py`

### Steps

```
1. User provides deal parameters (pool, tranche stack, structural tests, targets)

2. deal-schema-agent
   - maps raw inputs to canonical Deal / Collateral / Structure objects
   - validates all required fields
   - produces: validation report + normalized deal object

3. create_deal_workflow
   - validates via DealSchema, CollateralSchema, StructureSchema (Pydantic)
   - calls portfolio-data-mcp → validate_pool()
   - rejects if pool validation fails (CCC limit, diversity score, size)
   - persists deal record (stub in Phase 1)
   - emits audit event: deal.created

4. scenario-runner
   - builds baseline scenario parameters from deal inputs
   - submits to cashflow-engine-mcp → run_scenario()
   - polls for completion → get_run_status()
   - collects outputs → get_run_outputs()
   - tags outputs: source = "model_runner", run_id
   - emits audit events: scenario.submitted, scenario.completed

5. analytics-explainer-agent
   - interprets engine outputs
   - explains key metrics in plain English [generated from calculated]
   - flags any threshold breaches or missing cushions

6. document-drafter
   - drafts internal structuring note
   - marks draft: approved = False

7. audit_logger records all events
```

### Inputs required

| Group | Key fields |
|---|---|
| Deal | deal_id, name, issuer, region, currency |
| Collateral | pool_id, portfolio_size, was, warf, wal, diversity_score, ccc_bucket |
| Tranche stack | name, seniority, size_pct or size_abs, coupon, target_rating |
| Structural tests | oc_tests, ic_tests, ccc_limit |
| Market assumptions | default_rate, recovery_rate, spread_shock_bps |

### Guardrails

- Pool validation blocks deals with ccc_bucket > 7.5% or diversity_score < 30
- Scenario submission requires non-empty parameters
- Engine outputs must carry `source = "model_runner"` before any interpretation

---

## 2. Compare scenario versions

**User intent:** "What changed between scenario v3 and v7? What is driving the difference?"

**Entry point:** `app/workflows/compare_scenarios_workflow.py`

### Steps

```
1. User provides two scenario IDs (or two version numbers for the same deal)

2. Verify both scenarios have official engine outputs
   - source must be "model_runner"
   - outputs dict must be non-empty

3. compare_scenarios_workflow
   - diffs scenario parameters → changed_inputs list
   - diffs scenario outputs (excluding _mock / internal keys) → changed_outputs list
   - emits audit event: comparison.run

4. analytics-explainer-agent
   - receives changed_inputs and changed_outputs
   - identifies top 3 likely causal drivers
   - explains each driver in plain English [generated]
   - ranks drivers by likely materiality
   - explicitly flags any uncertain causality

5. document-drafter (optional)
   - drafts version comparison note if requested
   - approved = False
```

### Output structure

```json
{
  "scenario_a": "sc-baseline-v3",
  "scenario_b": "sc-revised-v7",
  "changed_inputs": [
    { "key": "recovery_rate", "a": 0.65, "b": 0.55 }
  ],
  "changed_outputs": [
    { "key": "equity_irr", "a": 0.142, "b": 0.118 }
  ],
  "input_changes_count": 1,
  "output_changes_count": 1,
  "source": "model_runner"
}
```

### Guardrails

- Comparison is blocked if either scenario has no outputs
- Comparison is blocked if either scenario source ≠ "model_runner"
- Driver interpretation is labelled `[generated]` — not official analysis

---

## 3. Generate investor summary

**User intent:** "Draft an investor summary for this deal."

**Entry point:** `app/workflows/generate_investor_summary_workflow.py`

### Steps

```
1. User requests investor summary for a deal with at least one completed scenario

2. Verify scenario has official outputs
   - source = "model_runner" required
   - non-empty outputs required

3. document-drafter
   - fetches approved language from docs-repo MCP (stub in Phase 1)
   - composes summary sections using only:
     - [calculated] outputs from model_runner
     - [retrieved] language from approved docs_repo
   - produces draft InvestorMaterial object
   - approved = False, created_at set

4. compliance-reviewer (Phase 3)
   - screens for unsupported claims
   - checks disclaimer section is present
   - checks all numbers traceable to a run_id
   - checks no .env or internal paths leaked into content

5. workflow-mcp → create_review_task() (Phase 3)
   - routes draft to required approvers

6. On approval → publish-agent (Phase 3)
   - publishes to investor portal
   - stamps with version, approval record, timestamp
   - emits audit event: artifact.published
```

### Required sections

| Section | Source |
|---|---|
| Transaction overview | [retrieved] approved language |
| Collateral highlights | [retrieved] approved language |
| Liability structure summary | [retrieved] approved language |
| Key sensitivities | [generated] from engine outputs |
| Disclaimer | [retrieved] mandatory disclosure template |
| Source footer | scenario_id + run_id |

### Guardrails

- Draft is always created with `approved = False`
- No publish call is allowed without an Approval record with `status = "approved"`
- All content must carry source citations before compliance review
- Prohibited language detection runs before review submission (Phase 3)

---

## Audit events emitted

| Event | Workflow | Payload |
|---|---|---|
| `deal.created` | create_deal | deal_id, collateral_id, structure_id |
| `scenario.submitted` | run_scenario | run_id, parameters |
| `scenario.completed` | run_scenario | run_id, outputs |
| `comparison.run` | compare_scenarios | scenario_a, scenario_b, change counts |
| `draft.generated` | generate_investor_summary | material_id, sources |
| `approval.requested` | review routing (Phase 3) | material_id, approvers |
| `approval.granted` | approval workflow (Phase 3) | material_id, approver, timestamp |
| `artifact.published` | publish (Phase 3) | material_id, channel, destination |
