# /compare-versions

Compare two scenarios or deal versions and explain what changed.

## What this command does

Runs the scenario-comparison skill on two specified scenarios. Returns a
structured diff and a plain-English explanation of likely drivers.

## Usage

```
/compare-versions scenario_a=<id> scenario_b=<id>
```

Or if scenario IDs are already in context, the command will use them.

## Steps

### 1. Identify the two scenarios

Ask the user for:
- `scenario_a`: scenario_id (and optionally run_id)
- `scenario_b`: scenario_id (and optionally run_id)

If only version numbers are given (e.g. "v3 vs v7"), resolve to scenario_ids.

### 2. Verify engine outputs exist

Check that both scenarios have:
- `source = "model_runner"` on their outputs
- Non-empty outputs dict
- A `run_id` present

If either is missing: report which scenario needs to be run first. Stop.

### 3. Run scenario-comparison skill

Invoke the `/scenario-comparison` skill with both scenario objects.

### 4. Delegate driver analysis to analytics-explainer-agent

Pass `changed_inputs` and `changed_outputs` to analytics-explainer-agent.

### 5. Return structured result

```
COMPARISON: <scenario_a> vs <scenario_b>
Deal: <deal_id>

CHANGED INPUTS (N)
  recovery_rate:     0.65 → 0.55
  spread_shock_bps:  0 → 50

CHANGED OUTPUTS (N)
  equity_irr:        14.2% → 11.8%   [calculated — run_id_a vs run_id_b]
  oc_cushion_aaa:    5.2% → 3.8%     [calculated]

TOP DRIVERS [generated]
  1. Recovery rate reduction (-10pts) — primary driver of equity IRR compression
  2. Spread shock (50bps) — secondary contributor to OC cushion tightening
  3. Combined effect on scenario NPV — tertiary

BUSINESS INTERPRETATION [generated]
  <plain English paragraph>

CAVEATS
  <uncertainty flags, if any>
```

## Hard constraints

- Do not invent driver explanations without a diff to reference
- Do not produce a publishable document — output is internal analysis only
- Both scenarios must have official engine outputs before proceeding
- Label all interpretive content as `[generated]`
