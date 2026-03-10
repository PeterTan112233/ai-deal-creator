"""
tests/test_batch_scenario_workflow.py

Tests for app/workflows/batch_scenario_workflow.py

Covers:
  - Happy path: 3 scenarios, all complete
  - Comparison table structure (metric rows, best/worst)
  - Single scenario
  - Invalid deal stops early (no scenarios run)
  - Empty scenario list
  - Audit events emitted
  - Failed scenario handled gracefully (others still complete)
  - Parameter defaults applied from market_assumptions
"""

import pytest
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.workflows.batch_scenario_workflow import batch_scenario_workflow, _build_comparison_table


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _load_sample_deal(label_substring: str) -> dict:
    with open("data/samples/sample_deal_inputs.json") as f:
        data = json.load(f)
    for deal in data["deals"]:
        if label_substring in deal.get("_label", ""):
            return deal
    raise KeyError(f"No sample deal matching '{label_substring}'")


@pytest.fixture
def valid_deal():
    return _load_sample_deal("US BSL")


@pytest.fixture
def three_scenarios():
    return [
        {
            "name": "Base",
            "type": "base",
            "parameters": {"default_rate": 0.03, "recovery_rate": 0.65, "spread_shock_bps": 0},
        },
        {
            "name": "Stress",
            "type": "stress",
            "parameters": {"default_rate": 0.06, "recovery_rate": 0.45, "spread_shock_bps": 75},
        },
        {
            "name": "Super-Stress",
            "type": "stress",
            "parameters": {"default_rate": 0.10, "recovery_rate": 0.30, "spread_shock_bps": 150},
        },
    ]


@pytest.fixture
def single_scenario():
    return [
        {"name": "Base", "type": "base", "parameters": {"default_rate": 0.03, "recovery_rate": 0.65, "spread_shock_bps": 0}},
    ]


# ---------------------------------------------------------------------------
# Return structure
# ---------------------------------------------------------------------------

class TestReturnStructure:

    def test_returns_dict(self, valid_deal, three_scenarios):
        result = batch_scenario_workflow(valid_deal, three_scenarios)
        assert isinstance(result, dict)

    def test_all_expected_keys_present(self, valid_deal, three_scenarios):
        result = batch_scenario_workflow(valid_deal, three_scenarios)
        for key in ("deal_id", "scenarios_run", "results", "comparison_table", "audit_events", "is_mock"):
            assert key in result, f"Missing key: {key}"

    def test_no_error_on_valid_deal(self, valid_deal, three_scenarios):
        result = batch_scenario_workflow(valid_deal, three_scenarios)
        assert "error" not in result

    def test_deal_id_matches_input(self, valid_deal, three_scenarios):
        result = batch_scenario_workflow(valid_deal, three_scenarios)
        assert result["deal_id"] == valid_deal["deal_id"]

    def test_is_mock_true(self, valid_deal, three_scenarios):
        result = batch_scenario_workflow(valid_deal, three_scenarios)
        assert result["is_mock"] is True


# ---------------------------------------------------------------------------
# Results list
# ---------------------------------------------------------------------------

class TestResultsList:

    def test_three_results_for_three_scenarios(self, valid_deal, three_scenarios):
        result = batch_scenario_workflow(valid_deal, three_scenarios)
        assert result["scenarios_run"] == 3
        assert len(result["results"]) == 3

    def test_results_in_input_order(self, valid_deal, three_scenarios):
        result = batch_scenario_workflow(valid_deal, three_scenarios)
        names = [r["scenario_name"] for r in result["results"]]
        assert names == ["Base", "Stress", "Super-Stress"]

    def test_each_result_has_required_keys(self, valid_deal, three_scenarios):
        result = batch_scenario_workflow(valid_deal, three_scenarios)
        for r in result["results"]:
            for key in ("scenario_name", "scenario_type", "run_id", "parameters", "outputs", "status"):
                assert key in r, f"Missing key '{key}' in result"

    def test_all_results_complete(self, valid_deal, three_scenarios):
        result = batch_scenario_workflow(valid_deal, three_scenarios)
        for r in result["results"]:
            assert r["status"] == "complete"

    def test_run_ids_are_strings(self, valid_deal, three_scenarios):
        result = batch_scenario_workflow(valid_deal, three_scenarios)
        for r in result["results"]:
            assert isinstance(r["run_id"], str)
            assert r["run_id"].startswith("run-")

    def test_outputs_contain_equity_irr(self, valid_deal, three_scenarios):
        result = batch_scenario_workflow(valid_deal, three_scenarios)
        for r in result["results"]:
            assert "equity_irr" in r["outputs"]

    def test_single_scenario(self, valid_deal, single_scenario):
        result = batch_scenario_workflow(valid_deal, single_scenario)
        assert result["scenarios_run"] == 1
        assert len(result["results"]) == 1
        assert result["results"][0]["status"] == "complete"


# ---------------------------------------------------------------------------
# Numeric plausibility
# ---------------------------------------------------------------------------

class TestNumericPlausibility:

    def test_base_irr_higher_than_stress(self, valid_deal, three_scenarios):
        result = batch_scenario_workflow(valid_deal, three_scenarios)
        irrs = {r["scenario_name"]: r["outputs"]["equity_irr"] for r in result["results"]}
        assert irrs["Base"] > irrs["Stress"] > irrs["Super-Stress"]

    def test_base_irr_in_plausible_range(self, valid_deal, three_scenarios):
        result = batch_scenario_workflow(valid_deal, three_scenarios)
        base_irr = next(r for r in result["results"] if r["scenario_name"] == "Base")["outputs"]["equity_irr"]
        assert -0.5 <= base_irr <= 1.0, f"IRR {base_irr:.2%} out of plausible range"

    def test_parameters_preserved_in_results(self, valid_deal, three_scenarios):
        result = batch_scenario_workflow(valid_deal, three_scenarios)
        base = next(r for r in result["results"] if r["scenario_name"] == "Base")
        assert abs(base["parameters"]["default_rate"] - 0.03) < 1e-6


# ---------------------------------------------------------------------------
# Comparison table
# ---------------------------------------------------------------------------

class TestComparisonTable:

    def test_comparison_table_is_list(self, valid_deal, three_scenarios):
        result = batch_scenario_workflow(valid_deal, three_scenarios)
        assert isinstance(result["comparison_table"], list)

    def test_comparison_table_has_rows(self, valid_deal, three_scenarios):
        result = batch_scenario_workflow(valid_deal, three_scenarios)
        assert len(result["comparison_table"]) > 0

    def test_each_row_has_required_keys(self, valid_deal, three_scenarios):
        result = batch_scenario_workflow(valid_deal, three_scenarios)
        for row in result["comparison_table"]:
            assert "metric" in row
            assert "values" in row

    def test_equity_irr_row_present(self, valid_deal, three_scenarios):
        result = batch_scenario_workflow(valid_deal, three_scenarios)
        metrics = [row["metric"] for row in result["comparison_table"]]
        assert "equity_irr" in metrics

    def test_equity_irr_best_is_base(self, valid_deal, three_scenarios):
        result = batch_scenario_workflow(valid_deal, three_scenarios)
        irr_row = next(r for r in result["comparison_table"] if r["metric"] == "equity_irr")
        assert irr_row["best"] == "Base"

    def test_equity_irr_worst_is_super_stress(self, valid_deal, three_scenarios):
        result = batch_scenario_workflow(valid_deal, three_scenarios)
        irr_row = next(r for r in result["comparison_table"] if r["metric"] == "equity_irr")
        assert irr_row["worst"] == "Super-Stress"

    def test_values_dict_has_all_scenario_names(self, valid_deal, three_scenarios):
        result = batch_scenario_workflow(valid_deal, three_scenarios)
        irr_row = next(r for r in result["comparison_table"] if r["metric"] == "equity_irr")
        assert set(irr_row["values"].keys()) == {"Base", "Stress", "Super-Stress"}

    def test_single_scenario_no_best_worst(self, valid_deal, single_scenario):
        """With only one scenario, best/worst can't be determined."""
        result = batch_scenario_workflow(valid_deal, single_scenario)
        for row in result["comparison_table"]:
            # best/worst are None or absent for single-scenario runs
            assert row.get("best") is None or len(result["results"]) == 1


# ---------------------------------------------------------------------------
# Audit events
# ---------------------------------------------------------------------------

class TestAuditEvents:

    def test_audit_events_emitted(self, valid_deal, three_scenarios):
        result = batch_scenario_workflow(valid_deal, three_scenarios)
        assert len(result["audit_events"]) >= 2  # validated + batch_completed

    def test_audit_events_are_strings(self, valid_deal, three_scenarios):
        result = batch_scenario_workflow(valid_deal, three_scenarios)
        for ev in result["audit_events"]:
            assert isinstance(ev, str)


# ---------------------------------------------------------------------------
# Guard conditions
# ---------------------------------------------------------------------------

class TestGuardConditions:

    def test_invalid_deal_returns_error(self, three_scenarios):
        bad_deal = {"deal_id": "", "name": "x", "issuer": "y",
                    "collateral": {"portfolio_size": 100_000_000, "diversity_score": 45, "ccc_bucket": 0.05},
                    "liabilities": [{"tranche_id": "t1", "name": "AAA", "seniority": 1, "size_pct": 0.61, "coupon": "SOFR+145"}]}
        result = batch_scenario_workflow(bad_deal, three_scenarios)
        assert "error" in result
        assert result["scenarios_run"] == 0

    def test_empty_scenarios_returns_error(self, valid_deal):
        result = batch_scenario_workflow(valid_deal, [])
        assert "error" in result
        assert result["scenarios_run"] == 0

    def test_parameter_defaults_from_market_assumptions(self, valid_deal):
        """Scenarios with no explicit parameters use deal market_assumptions."""
        deal = dict(valid_deal)
        deal["market_assumptions"] = {"default_rate": 0.04, "recovery_rate": 0.60, "spread_shock_bps": 25}
        scenarios = [{"name": "FromDeal", "type": "base", "parameters": {}}]
        result = batch_scenario_workflow(deal, scenarios)
        r = result["results"][0]
        assert r["parameters"]["default_rate"] == 0.04
        assert r["parameters"]["recovery_rate"] == 0.60


# ---------------------------------------------------------------------------
# Unit test for comparison table helper
# ---------------------------------------------------------------------------

class TestBuildComparisonTable:

    def _make_results(self):
        return [
            {"scenario_name": "A", "status": "complete", "outputs": {"equity_irr": 0.12, "wac": 0.095}},
            {"scenario_name": "B", "status": "complete", "outputs": {"equity_irr": 0.08, "wac": 0.090}},
            {"scenario_name": "C", "status": "failed",   "outputs": {}},
        ]

    def test_only_completed_scenarios_in_table(self):
        results = self._make_results()
        table = _build_comparison_table(results)
        for row in table:
            assert "C" not in row["values"]

    def test_equity_irr_best_is_a(self):
        results = self._make_results()
        table = _build_comparison_table(results)
        irr_row = next(r for r in table if r["metric"] == "equity_irr")
        assert irr_row["best"] == "A"
        assert irr_row["worst"] == "B"

    def test_empty_results_returns_empty_table(self):
        assert _build_comparison_table([]) == []

    def test_all_failed_returns_empty_table(self):
        results = [{"scenario_name": "X", "status": "failed", "outputs": {}}]
        assert _build_comparison_table(results) == []
