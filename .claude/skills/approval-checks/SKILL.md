---
name: approval-checks
description: Run a compliance and approval readiness check on any draft material before it moves to internal review or external publication. Returns a structured PASS / PASS WITH NOTES / FAIL result. Always invoke before any publish action.
---

## When to use

Invoke when:
- A draft investor summary, IC memo, or FAQ is ready for review
- A publish action is being considered
- Compliance wants to verify source grounding and language controls
- A prior FAIL result has been addressed and re-check is needed

## Inputs required

```
material:
  material_id, deal_id, material_type
  content: <draft text>
  sources: [list of source object IDs]
  approved: false (expected for drafts)

context:
  target_channel: internal | investor_portal | external
  scenario_id and run_id of engine outputs referenced
```

## Steps when invoked

1. Delegate to **compliance-review-agent**

2. Run full checklist:
   - Source grounding: all numbers traceable to run_id with source = "model_runner"
   - Language controls: no unsupported claims, no prohibited phrases
   - Approval status: approval record exists or is pending
   - Disclosure: disclaimer present and correct for channel
   - Entitlement: no cross-boundary data exposure

3. Return structured review result

## Outputs

```
review_result:
  overall: PASS | PASS WITH NOTES | FAIL
  checklist:
    source_grounding: PASS | FAIL | WARNING — detail
    language_controls: PASS | FAIL | WARNING — detail
    approval_status:   PASS | FAIL | WARNING — detail
    disclosure:        PASS | FAIL | WARNING — detail
    entitlement:       PASS | FAIL | WARNING — detail
  required_changes: [list — present if FAIL or PASS WITH NOTES]
  cleared_for: internal review | external publication | not cleared
```

## Hard constraints

- Do not approve a document — only assess readiness
- FAIL if disclaimer is missing for external-facing documents
- FAIL if any number lacks a `run_id` citation
- PASS WITH NOTES is not equivalent to PASS for publish purposes
- A human approver must act on the result — this skill does not substitute for human approval
- Never auto-publish — a publish action requires an explicit human instruction after PASS
