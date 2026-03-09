# /publish-check

Run a full pre-publication compliance check on a draft material.

## What this command does

Invokes the `approval-checks` skill on a specified draft. Returns a structured
PASS / PASS WITH NOTES / FAIL result. This must be run and pass before any
publish action is attempted.

## Usage

```
/publish-check material_id=<id> channel=<internal|investor_portal|external>
```

## Steps

### 1. Identify the material

Ask the user for:
- `material_id` — the draft to be reviewed
- `channel` — publication destination (`internal`, `investor_portal`, `external`)

### 2. Load the material

Read the draft content and its source citations.

### 3. Run approval-checks skill

Invoke the `/approval-checks` skill with:
- material content
- source list (scenario_id, run_id, language source IDs)
- target channel

### 4. Delegate to compliance-review-agent

compliance-review-agent runs the full checklist:
- Source grounding
- Language controls
- Approval status
- Disclaimer completeness
- Entitlement

### 5. Return result

```
PUBLISH CHECK: <material_id>
Channel: <channel>
============================

SOURCE GROUNDING:    PASS | FAIL | WARNING
LANGUAGE CONTROLS:   PASS | FAIL | WARNING
APPROVAL STATUS:     PASS | FAIL | WARNING
DISCLAIMER:          PASS | FAIL | WARNING
ENTITLEMENT:         PASS | FAIL | WARNING

OVERALL: PASS | PASS WITH NOTES | FAIL

REQUIRED CHANGES (if applicable):
  1. ...
  2. ...

CLEARED FOR: <channel> | NOT CLEARED
```

### 6. If PASS

Inform the user the document has passed compliance review.
State clearly: **A human approver must still provide explicit approval before publication.**
Do not publish automatically.

### 7. If FAIL or PASS WITH NOTES

List required changes. Do not proceed to publish.
Offer to re-run the check after corrections are made.

## Hard constraints

- Never publish automatically — a PASS result only clears the document for human approval
- Do not skip any checklist item
- PASS WITH NOTES is not equivalent to PASS for external publication
- The command does not grant approval — it assesses readiness only
