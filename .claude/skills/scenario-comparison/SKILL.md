---
name: scenario-comparison
description: Compare two CLO scenarios that have been run through the official engine. Produces a structured diff of inputs and outputs, then explains likely drivers in plain English. Both scenarios must have model_runner outputs before invoking.
---

## When to use

Invoke when:
- A user asks "what changed between scenario A and B?"
- A user asks "why did equity IRR fall in version 7?"
- A user wants a side-by-side comparison of two runs
- A deal version comparison is requested

## Inputs required

```
scenario_a:
  scenario_id, deal_id, parameters, outputs (source = "model_runner"), run_id

scenario_b:
  scenario_id, deal_id, parameters, outputs (source = "model_runner"), run_id
```

Both scenarios must be for the same deal. Both must have completed engine runs.

## Steps when invoked

1. Verify both scenarios have `source = "model_runner"` and non-empty outputs
   - If not: report which scenario is missing outputs and stop

2. Call **compare_scenarios_workflow** (or delegate to model-execution-agent if runs are missing)
   - Produces: `changed_inputs`, `changed_outputs`

3. Delegate to **analytics-explainer-agent**
   - Inputs: changed_inputs, changed_outputs, both scenario objects
   - Produces: top 3 drivers, business interpretation, caveats

4. Return structured comparison result

## Outputs

```
comparison:
  scenario_a: <scenario_id>
  scenario_b: <scenario_id>
  changed_inputs: [{key, a, b}]
  changed_outputs: [{key, a, b}]
  input_changes_count: N
  output_changes_count: N
  source: "model_runner"

explanation:
  top_drivers: [ranked list with reasoning] [generated]
  business_interpretation: <plain English summary> [generated]
  caveats: <uncertainty flags>
  run_ids_cited: [run_id_a, run_id_b]
```

## Hard constraints

- Do not proceed if either scenario lacks `source = "model_runner"` outputs
- Do not invent driver explanations — all interpretation must reference the diff
- Label every interpretive statement as `[generated]`
- Cite both run_ids in the output
- Do not produce a publishable narrative — route to investor-summary-drafting for that
