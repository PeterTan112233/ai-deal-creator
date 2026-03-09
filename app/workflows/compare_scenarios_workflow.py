# DEPRECATED — Phase 1 only.
# This workflow operates on Scenario domain dataclasses and is no longer the
# recommended comparison path for new development.
# Use compare_versions_workflow (app/workflows/compare_versions_workflow.py)
# instead — it operates on plain dicts, supports driver inference, and is the
# authoritative comparison workflow from Phase 8 onwards.
# This file is retained for backward compatibility with app/tests/test_compare_scenarios.py.

from app.domain.scenario import Scenario
from app.services import audit_logger
from typing import List


def compare_scenarios_workflow(
    scenario_a: Scenario,
    scenario_b: Scenario,
    actor: str = "system",
) -> dict:
    """
    Compare two model-run scenarios and return a structured diff.

    Steps:
    1. Assert both scenarios have official engine outputs
    2. Diff input parameters
    3. Diff output values
    4. Emit audit event
    5. Return structured comparison result

    NOTE: Causal driver interpretation is done by analytics-explainer-agent,
    not computed here.
    """
    _assert_official(scenario_a)
    _assert_official(scenario_b)

    changed_inputs = _diff(scenario_a.parameters, scenario_b.parameters)
    changed_outputs = _diff(
        {k: v for k, v in scenario_a.outputs.items() if not k.startswith("_")},
        {k: v for k, v in scenario_b.outputs.items() if not k.startswith("_")},
    )

    result = {
        "scenario_a": scenario_a.scenario_id,
        "scenario_b": scenario_b.scenario_id,
        "changed_inputs": changed_inputs,
        "changed_outputs": changed_outputs,
        "input_changes_count": len(changed_inputs),
        "output_changes_count": len(changed_outputs),
        "source": "model_runner",
    }

    audit_logger.record_event(
        event_type="comparison.run",
        deal_id=scenario_a.deal_id,
        actor=actor,
        payload={
            "scenario_a": scenario_a.scenario_id,
            "scenario_b": scenario_b.scenario_id,
            "input_changes": len(changed_inputs),
            "output_changes": len(changed_outputs),
        },
    )

    return result


def _assert_official(scenario: Scenario) -> None:
    if not scenario.outputs:
        raise ValueError(
            f"Scenario '{scenario.scenario_id}' has no outputs. "
            "Run it through the engine before comparing."
        )
    if scenario.source != "model_runner":
        raise ValueError(
            f"Scenario '{scenario.scenario_id}' outputs are not from model_runner."
        )


def _diff(a: dict, b: dict) -> List[dict]:
    keys = set(a) | set(b)
    return [
        {"key": k, "a": a.get(k), "b": b.get(k)}
        for k in sorted(keys)
        if a.get(k) != b.get(k)
    ]
