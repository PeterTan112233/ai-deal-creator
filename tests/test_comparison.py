"""
tests/test_comparison.py

Tests for comparison_service and compare_versions_workflow.

Covers:
  - Factual diff detection (deterministic)
  - Driver inference (conservative heuristics)
  - Summary generation (tagging and structure)
  - Workflow orchestration and audit events
  - Edge cases: identical inputs, missing params, single vs multi-change
"""

import json
import sys
import os

# Ensure project root is on the path when running from tests/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from app.services import comparison_service
from app.workflows.compare_versions_workflow import compare_versions_workflow


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _load_deal(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


def _load_result(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


@pytest.fixture
def deal_v1():
    data = _load_deal("data/samples/sample_deal_inputs.json")
    return next(d for d in data["deals"] if "US BSL" in d.get("_label", ""))


@pytest.fixture
def deal_v2():
    return _load_deal("data/samples/sample_deal_inputs_v2.json")


@pytest.fixture
def result_v1():
    return _load_result("data/samples/sample_scenario_output.json")


@pytest.fixture
def result_v2():
    return _load_result("data/samples/sample_scenario_output_v2.json")


# ---------------------------------------------------------------------------
# comparison_service — compare_deal_inputs
# ---------------------------------------------------------------------------

class TestCompareDealInputs:

    def test_detects_market_assumption_changes(self, deal_v1, deal_v2):
        result = comparison_service.compare_deal_inputs(deal_v1, deal_v2)
        assumption_fields = {c["field"] for c in result["assumption_changes"]}
        assert "default_rate" in assumption_fields
        assert "recovery_rate" in assumption_fields
        assert "spread_shock_bps" in assumption_fields

    def test_detects_collateral_changes(self, deal_v1, deal_v2):
        result = comparison_service.compare_deal_inputs(deal_v1, deal_v2)
        collateral_fields = {c["field"] for c in result["collateral_changes"]}
        assert "ccc_bucket" in collateral_fields
        assert "diversity_score" in collateral_fields

    def test_correct_direction_on_recovery_rate(self, deal_v1, deal_v2):
        result = comparison_service.compare_deal_inputs(deal_v1, deal_v2)
        rr = next(c for c in result["assumption_changes"] if c["field"] == "recovery_rate")
        assert rr["direction"] == "down"
        assert rr["v1"] == 0.65
        assert rr["v2"] == 0.55
        assert abs(rr["delta"] - (-0.10)) < 1e-9

    def test_correct_direction_on_default_rate(self, deal_v1, deal_v2):
        result = comparison_service.compare_deal_inputs(deal_v1, deal_v2)
        dr = next(c for c in result["assumption_changes"] if c["field"] == "default_rate")
        assert dr["direction"] == "up"

    def test_correct_direction_on_spread_shock(self, deal_v1, deal_v2):
        result = comparison_service.compare_deal_inputs(deal_v1, deal_v2)
        ss = next(c for c in result["assumption_changes"] if c["field"] == "spread_shock_bps")
        assert ss["direction"] == "up"
        assert ss["delta"] == 50

    def test_identical_inputs_produce_no_changes(self, deal_v1):
        result = comparison_service.compare_deal_inputs(deal_v1, deal_v1)
        assert result["change_count"] == 0
        assert result["collateral_changes"] == []
        assert result["assumption_changes"] == []
        assert result["metadata_changes"] == []

    def test_total_change_count_is_correct(self, deal_v1, deal_v2):
        result = comparison_service.compare_deal_inputs(deal_v1, deal_v2)
        expected = (
            len(result["collateral_changes"])
            + len(result["assumption_changes"])
            + len(result["metadata_changes"])
        )
        assert result["change_count"] == expected

    def test_caveat_mentions_liabilities(self, deal_v1, deal_v2):
        result = comparison_service.compare_deal_inputs(deal_v1, deal_v2)
        assert "liabilit" in result["caveat"].lower() or "tranche" in result["caveat"].lower()

    def test_returns_v1_and_v2_ids(self, deal_v1, deal_v2):
        result = comparison_service.compare_deal_inputs(deal_v1, deal_v2)
        assert result["v1_id"] == "deal-us-bsl-001"
        assert result["v2_id"] == "deal-us-bsl-002"


# ---------------------------------------------------------------------------
# comparison_service — compare_scenario_results
# ---------------------------------------------------------------------------

class TestCompareScenarioResults:

    def test_detects_output_changes(self, result_v1, result_v2):
        result = comparison_service.compare_scenario_results(result_v1, result_v2)
        output_fields = {c["field"] for c in result["output_changes"]}
        assert "equity_irr" in output_fields
        assert "oc_cushion_aaa" in output_fields
        assert "wac" in output_fields

    def test_equity_irr_direction_is_down(self, result_v1, result_v2):
        result = comparison_service.compare_scenario_results(result_v1, result_v2)
        irr = next(c for c in result["output_changes"] if c["field"] == "equity_irr")
        assert irr["direction"] == "down"
        assert irr["v1"] == 0.142
        assert irr["v2"] == 0.108

    def test_wac_direction_is_up(self, result_v1, result_v2):
        result = comparison_service.compare_scenario_results(result_v1, result_v2)
        wac = next(c for c in result["output_changes"] if c["field"] == "wac")
        assert wac["direction"] == "up"

    def test_detects_param_changes_when_provided(self, result_v1, result_v2):
        p1 = {"default_rate": 0.03, "recovery_rate": 0.65, "spread_shock_bps": 0}
        p2 = {"default_rate": 0.05, "recovery_rate": 0.55, "spread_shock_bps": 50}
        result = comparison_service.compare_scenario_results(
            result_v1, result_v2, v1_params=p1, v2_params=p2
        )
        param_fields = {c["field"] for c in result["param_changes"]}
        assert "default_rate" in param_fields
        assert "recovery_rate" in param_fields

    def test_infers_drivers_from_params_and_outputs(self, result_v1, result_v2):
        p1 = {"default_rate": 0.03, "recovery_rate": 0.65, "spread_shock_bps": 0}
        p2 = {"default_rate": 0.05, "recovery_rate": 0.55, "spread_shock_bps": 50}
        result = comparison_service.compare_scenario_results(
            result_v1, result_v2, v1_params=p1, v2_params=p2
        )
        assert result["change_count"]["drivers_inferred"] > 0

    def test_driver_tags_are_generated(self, result_v1, result_v2):
        p1 = {"default_rate": 0.03, "recovery_rate": 0.65, "spread_shock_bps": 0}
        p2 = {"default_rate": 0.05, "recovery_rate": 0.55, "spread_shock_bps": 50}
        result = comparison_service.compare_scenario_results(
            result_v1, result_v2, v1_params=p1, v2_params=p2
        )
        for driver in result["likely_drivers"]:
            assert "[generated" in driver["tag"]

    def test_driver_statements_use_hedged_language(self, result_v1, result_v2):
        p1 = {"default_rate": 0.03, "recovery_rate": 0.65, "spread_shock_bps": 0}
        p2 = {"default_rate": 0.05, "recovery_rate": 0.55, "spread_shock_bps": 50}
        result = comparison_service.compare_scenario_results(
            result_v1, result_v2, v1_params=p1, v2_params=p2
        )
        for driver in result["likely_drivers"]:
            statement = driver["statement"].lower()
            assert any(word in statement for word in ("may", "likely", "potential", "compressing")), (
                f"Driver statement lacks hedged language: {driver['statement']}"
            )

    def test_no_drivers_without_params(self, result_v1, result_v2):
        """Without parameter context, driver inference must not fire."""
        result = comparison_service.compare_scenario_results(result_v1, result_v2)
        # result_v2 has 'parameters' key — but result_v1 does not.
        # If v1 params are missing, param_changes will be empty → no drivers.
        # (This tests the fallback path when v1 has no parameters key.)
        import copy
        r1 = copy.deepcopy(result_v1)
        r1.pop("parameters", None)
        r2 = copy.deepcopy(result_v2)
        r2.pop("parameters", None)
        result = comparison_service.compare_scenario_results(r1, r2)
        assert result["change_count"]["drivers_inferred"] == 0

    def test_driver_does_not_fire_on_wrong_output_direction(self, result_v1, result_v2):
        """
        If recovery_rate ↓ but equity_irr somehow ↑, the recovery→equity_irr driver
        must NOT fire (rule requires output to also move in the predicted direction).
        """
        import copy
        r2 = copy.deepcopy(result_v2)
        r2["outputs"]["equity_irr"] = 0.999  # unexpected ↑
        p1 = {"recovery_rate": 0.65}
        p2 = {"recovery_rate": 0.55}
        result = comparison_service.compare_scenario_results(
            result_v1, r2, v1_params=p1, v2_params=p2
        )
        driver_pairs = {
            (d["input_field"], d["output_field"]) for d in result["likely_drivers"]
        }
        assert ("recovery_rate", "equity_irr") not in driver_pairs

    def test_multi_change_caveat_fires_for_multiple_param_changes(self, result_v1, result_v2):
        p1 = {"default_rate": 0.03, "recovery_rate": 0.65, "spread_shock_bps": 0}
        p2 = {"default_rate": 0.05, "recovery_rate": 0.55, "spread_shock_bps": 50}
        result = comparison_service.compare_scenario_results(
            result_v1, result_v2, v1_params=p1, v2_params=p2
        )
        # Multiple param changes → multi-change caveat must be present
        combined = " ".join(result["caveats"])
        assert "interaction" in combined.lower() or "multiple" in combined.lower()

    def test_multi_change_caveat_absent_for_single_param_change(self, result_v1, result_v2):
        p1 = {"recovery_rate": 0.65}
        p2 = {"recovery_rate": 0.55}
        result = comparison_service.compare_scenario_results(
            result_v1, result_v2, v1_params=p1, v2_params=p2
        )
        # Only one param changed — multi-change caveat must NOT fire
        assert len(result["caveats"]) == 1  # only general caveat

    def test_identical_results_produce_no_changes(self, result_v1):
        result = comparison_service.compare_scenario_results(result_v1, result_v1)
        assert result["change_count"]["outputs"] == 0
        assert result["change_count"]["drivers_inferred"] == 0

    def test_internal_keys_stripped_from_outputs(self, result_v1, result_v2):
        result = comparison_service.compare_scenario_results(result_v1, result_v2)
        output_fields = {c["field"] for c in result["output_changes"]}
        assert "_mock" not in output_fields
        assert "_comment" not in output_fields
        assert "_warning" not in output_fields

    def test_is_mock_flag_set_when_mock_output(self, result_v1, result_v2):
        result = comparison_service.compare_scenario_results(result_v1, result_v2)
        assert result["is_mock"] is True


# ---------------------------------------------------------------------------
# comparison_service — generate_comparison_summary
# ---------------------------------------------------------------------------

class TestGenerateComparisonSummary:

    def _scenario_comparison(self, result_v1, result_v2):
        p1 = {"default_rate": 0.03, "recovery_rate": 0.65, "spread_shock_bps": 0}
        p2 = {"default_rate": 0.05, "recovery_rate": 0.55, "spread_shock_bps": 50}
        return comparison_service.compare_scenario_results(
            result_v1, result_v2, v1_params=p1, v2_params=p2
        )

    def test_scenario_summary_contains_section_headers(self, result_v1, result_v2):
        comp = self._scenario_comparison(result_v1, result_v2)
        summary = comparison_service.generate_comparison_summary(comp, mode="scenario")
        assert "PARAMETER CHANGES" in summary
        assert "OUTPUT CHANGES" in summary
        assert "LIKELY DRIVERS" in summary
        assert "LIMITATIONS" in summary

    def test_scenario_summary_has_retrieved_tag(self, result_v1, result_v2):
        comp = self._scenario_comparison(result_v1, result_v2)
        summary = comparison_service.generate_comparison_summary(comp, mode="scenario")
        assert "[retrieved]" in summary

    def test_scenario_summary_has_calculated_tag(self, result_v1, result_v2):
        comp = self._scenario_comparison(result_v1, result_v2)
        summary = comparison_service.generate_comparison_summary(comp, mode="scenario")
        assert "[calculated" in summary

    def test_scenario_summary_has_generated_tag(self, result_v1, result_v2):
        comp = self._scenario_comparison(result_v1, result_v2)
        summary = comparison_service.generate_comparison_summary(comp, mode="scenario")
        assert "[generated" in summary

    def test_scenario_summary_contains_mock_note(self, result_v1, result_v2):
        comp = self._scenario_comparison(result_v1, result_v2)
        summary = comparison_service.generate_comparison_summary(comp, mode="scenario")
        assert "MOCK" in summary

    def test_deal_input_summary_contains_section_headers(self, deal_v1, deal_v2):
        comp = comparison_service.compare_deal_inputs(deal_v1, deal_v2)
        summary = comparison_service.generate_comparison_summary(comp, mode="deal_inputs")
        assert "COLLATERAL CHANGES" in summary
        assert "MARKET ASSUMPTION CHANGES" in summary
        assert "LIMITATIONS" in summary

    def test_deal_input_summary_has_retrieved_tag(self, deal_v1, deal_v2):
        comp = comparison_service.compare_deal_inputs(deal_v1, deal_v2)
        summary = comparison_service.generate_comparison_summary(comp, mode="deal_inputs")
        assert "[retrieved]" in summary


# ---------------------------------------------------------------------------
# compare_versions_workflow
# ---------------------------------------------------------------------------

class TestCompareVersionsWorkflow:

    def test_deal_comparison_mode(self, deal_v1, deal_v2):
        result = compare_versions_workflow(deal_v1, v2_deal=deal_v2, actor="test")
        assert "error" not in result
        assert result["deal_comparison"] is not None
        assert result["scenario_comparison"] is None
        assert result["deal_comparison"]["change_count"] > 0

    def test_scenario_comparison_mode(self, deal_v1, result_v1, result_v2):
        result = compare_versions_workflow(
            deal_v1, v1_result=result_v1, v2_result=result_v2, actor="test"
        )
        assert "error" not in result
        assert result["scenario_comparison"] is not None
        assert result["deal_comparison"] is None

    def test_combined_mode(self, deal_v1, deal_v2, result_v1, result_v2):
        result = compare_versions_workflow(
            deal_v1, v2_deal=deal_v2,
            v1_result=result_v1, v2_result=result_v2,
            actor="test",
        )
        assert "error" not in result
        assert result["deal_comparison"] is not None
        assert result["scenario_comparison"] is not None

    def test_no_inputs_returns_error(self, deal_v1):
        result = compare_versions_workflow(deal_v1)
        assert "error" in result
        assert result["deal_comparison"] is None
        assert result["scenario_comparison"] is None
        assert result["audit_events"] == []

    def test_emits_two_audit_events(self, deal_v1, deal_v2):
        result = compare_versions_workflow(deal_v1, v2_deal=deal_v2)
        assert len(result["audit_events"]) == 2
        event_types = [e["event_type"] for e in result["audit_events"]]
        assert "comparison.started" in event_types
        assert "comparison.completed" in event_types

    def test_summary_is_string(self, deal_v1, deal_v2):
        result = compare_versions_workflow(deal_v1, v2_deal=deal_v2)
        assert isinstance(result["summary"], str)
        assert len(result["summary"]) > 0

    def test_workflow_sources_params_from_deal(self, deal_v1, deal_v2, result_v1, result_v2):
        """
        When result dicts have no 'parameters' key, the workflow should source them
        from the deal's market_assumptions. Driver inference should still fire.
        """
        import copy
        r1 = copy.deepcopy(result_v1)
        r2 = copy.deepcopy(result_v2)
        r1.pop("parameters", None)
        r2.pop("parameters", None)
        result = compare_versions_workflow(
            deal_v1, v2_deal=deal_v2,
            v1_result=r1, v2_result=r2,
            actor="test",
        )
        sc = result["scenario_comparison"]
        # With params sourced from deal market_assumptions, drivers should fire
        assert sc["change_count"]["params"] > 0
        assert sc["change_count"]["drivers_inferred"] > 0

    def test_combined_summary_contains_both_sections(self, deal_v1, deal_v2, result_v1, result_v2):
        result = compare_versions_workflow(
            deal_v1, v2_deal=deal_v2,
            v1_result=result_v1, v2_result=result_v2,
        )
        summary = result["summary"]
        assert "DEAL INPUT COMPARISON" in summary
        assert "SCENARIO COMPARISON" in summary
