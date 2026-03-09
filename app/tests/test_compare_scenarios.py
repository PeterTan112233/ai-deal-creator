"""
Tests for compare_scenarios_workflow.
"""

import pytest
from app.domain.scenario import Scenario
from app.workflows.compare_scenarios_workflow import compare_scenarios_workflow, _diff


def _make_scenario(sid, outputs=None, source="model_runner"):
    s = Scenario(
        scenario_id=sid, deal_id="d1", name=sid,
        parameters={"default_rate": 0.03},
        outputs={"equity_irr": 0.14, "aaa_size_pct": 0.61} if outputs is None else outputs,
        source=source,
    )
    return s


def test_compare_identical_scenarios():
    a = _make_scenario("sc-a")
    b = _make_scenario("sc-b")
    result = compare_scenarios_workflow(a, b)
    assert result["output_changes_count"] == 0
    assert result["input_changes_count"] == 0


def test_compare_different_outputs():
    a = _make_scenario("sc-a", outputs={"equity_irr": 0.14, "aaa_size_pct": 0.61})
    b = _make_scenario("sc-b", outputs={"equity_irr": 0.11, "aaa_size_pct": 0.61})
    result = compare_scenarios_workflow(a, b)
    assert result["output_changes_count"] == 1
    changed = result["changed_outputs"][0]
    assert changed["key"] == "equity_irr"
    assert changed["a"] == 0.14
    assert changed["b"] == 0.11


def test_compare_fails_without_outputs():
    a = _make_scenario("sc-a", outputs={})
    b = _make_scenario("sc-b")
    with pytest.raises(ValueError, match="no outputs"):
        compare_scenarios_workflow(a, b)


def test_compare_fails_if_not_model_runner():
    a = _make_scenario("sc-a", source="manual")
    b = _make_scenario("sc-b")
    with pytest.raises(ValueError, match="model_runner"):
        compare_scenarios_workflow(a, b)


def test_diff_utility():
    result = _diff({"a": 1, "b": 2}, {"a": 1, "b": 3, "c": 4})
    keys = {r["key"] for r in result}
    assert "b" in keys
    assert "c" in keys
    assert "a" not in keys
