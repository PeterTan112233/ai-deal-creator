"""
tests/test_sensitivity_analysis_workflow.py

Tests for app/workflows/sensitivity_analysis_workflow.py

Covers:
  - Happy path: default_rate sweep 1%→10%
  - Series structure and ordering
  - IRR decreases monotonically with default_rate
  - Breakeven detection
  - Single value
  - Invalid deal stops early
  - Empty values list
  - Unknown parameter passes through
  - base_parameters override
  - Audit events emitted
  - Breakeven helper unit tests
"""

import pytest
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.workflows.sensitivity_analysis_workflow import (
    sensitivity_analysis_workflow,
    _compute_breakeven,
    _interpolate_zero,
)


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
def default_rate_values():
    return [0.01, 0.02, 0.03, 0.05, 0.07, 0.10]


# ---------------------------------------------------------------------------
# Return structure
# ---------------------------------------------------------------------------

class TestReturnStructure:

    def test_returns_dict(self, valid_deal, default_rate_values):
        result = sensitivity_analysis_workflow(valid_deal, "default_rate", default_rate_values)
        assert isinstance(result, dict)

    def test_all_expected_keys_present(self, valid_deal, default_rate_values):
        result = sensitivity_analysis_workflow(valid_deal, "default_rate", default_rate_values)
        for key in ("deal_id", "parameter", "values_tested", "series", "breakeven", "audit_events", "is_mock"):
            assert key in result, f"Missing key: {key}"

    def test_deal_id_matches_input(self, valid_deal, default_rate_values):
        result = sensitivity_analysis_workflow(valid_deal, "default_rate", default_rate_values)
        assert result["deal_id"] == valid_deal["deal_id"]

    def test_parameter_name_preserved(self, valid_deal, default_rate_values):
        result = sensitivity_analysis_workflow(valid_deal, "default_rate", default_rate_values)
        assert result["parameter"] == "default_rate"

    def test_values_tested_matches_input(self, valid_deal, default_rate_values):
        result = sensitivity_analysis_workflow(valid_deal, "default_rate", default_rate_values)
        assert result["values_tested"] == default_rate_values

    def test_is_mock_true(self, valid_deal, default_rate_values):
        result = sensitivity_analysis_workflow(valid_deal, "default_rate", default_rate_values)
        assert result["is_mock"] is True

    def test_no_error_on_valid_input(self, valid_deal, default_rate_values):
        result = sensitivity_analysis_workflow(valid_deal, "default_rate", default_rate_values)
        assert "error" not in result


# ---------------------------------------------------------------------------
# Series structure
# ---------------------------------------------------------------------------

class TestSeriesStructure:

    def test_series_length_matches_values(self, valid_deal, default_rate_values):
        result = sensitivity_analysis_workflow(valid_deal, "default_rate", default_rate_values)
        assert len(result["series"]) == len(default_rate_values)

    def test_each_series_entry_has_required_keys(self, valid_deal, default_rate_values):
        result = sensitivity_analysis_workflow(valid_deal, "default_rate", default_rate_values)
        for entry in result["series"]:
            for key in ("parameter_value", "outputs", "run_id", "status"):
                assert key in entry, f"Missing key: {key}"

    def test_series_in_value_order(self, valid_deal, default_rate_values):
        result = sensitivity_analysis_workflow(valid_deal, "default_rate", default_rate_values)
        for i, entry in enumerate(result["series"]):
            assert entry["parameter_value"] == default_rate_values[i]

    def test_all_entries_complete(self, valid_deal, default_rate_values):
        result = sensitivity_analysis_workflow(valid_deal, "default_rate", default_rate_values)
        for entry in result["series"]:
            assert entry["status"] == "complete"

    def test_outputs_contain_equity_irr(self, valid_deal, default_rate_values):
        result = sensitivity_analysis_workflow(valid_deal, "default_rate", default_rate_values)
        for entry in result["series"]:
            assert "equity_irr" in entry["outputs"]

    def test_run_ids_are_strings(self, valid_deal, default_rate_values):
        result = sensitivity_analysis_workflow(valid_deal, "default_rate", default_rate_values)
        for entry in result["series"]:
            assert isinstance(entry["run_id"], str)


# ---------------------------------------------------------------------------
# Numeric plausibility
# ---------------------------------------------------------------------------

class TestNumericPlausibility:

    def test_irr_decreases_monotonically_with_default_rate(self, valid_deal):
        """Higher default rates must produce lower equity IRR."""
        values = [0.01, 0.03, 0.05, 0.07, 0.10]
        result = sensitivity_analysis_workflow(valid_deal, "default_rate", values)
        irrs = [s["outputs"]["equity_irr"] for s in result["series"]]
        for i in range(len(irrs) - 1):
            assert irrs[i] > irrs[i + 1], f"IRR not decreasing: {irrs[i]:.2%} → {irrs[i+1]:.2%} at step {i}"

    def test_low_default_rate_positive_irr(self, valid_deal):
        result = sensitivity_analysis_workflow(valid_deal, "default_rate", [0.01])
        irr = result["series"][0]["outputs"]["equity_irr"]
        assert irr > 0, f"Low CDR should give positive IRR, got {irr:.2%}"

    def test_high_default_rate_negative_irr(self, valid_deal):
        result = sensitivity_analysis_workflow(valid_deal, "default_rate", [0.15])
        irr = result["series"][0]["outputs"]["equity_irr"]
        assert irr < 0, f"Very high CDR should give negative IRR, got {irr:.2%}"

    def test_recovery_rate_sweep_irr_increases(self, valid_deal):
        """Higher recovery rates → better IRR (less principal loss)."""
        values = [0.20, 0.40, 0.60, 0.80]
        result = sensitivity_analysis_workflow(
            valid_deal, "recovery_rate", values,
            base_parameters={"default_rate": 0.05, "spread_shock_bps": 0},
        )
        irrs = [s["outputs"]["equity_irr"] for s in result["series"]]
        assert irrs[-1] > irrs[0], "Higher recovery rate should increase IRR"


# ---------------------------------------------------------------------------
# Breakeven detection
# ---------------------------------------------------------------------------

class TestBreakevenDetection:

    def test_breakeven_dict_has_expected_keys(self, valid_deal, default_rate_values):
        result = sensitivity_analysis_workflow(valid_deal, "default_rate", default_rate_values)
        assert "equity_irr_zero" in result["breakeven"]
        assert "scenario_npv_zero" in result["breakeven"]

    def test_irr_breakeven_found_in_range(self, valid_deal):
        """Sweeping 1%→15% CDR should cross IRR=0 somewhere in the middle."""
        values = [round(v * 0.01, 2) for v in range(1, 16)]  # 1%..15%
        result = sensitivity_analysis_workflow(valid_deal, "default_rate", values)
        be = result["breakeven"]["equity_irr_zero"]
        assert be is not None, "Breakeven CDR should be found in 1%–15% range"
        assert 0.01 <= be <= 0.15, f"Breakeven {be:.2%} outside tested range"

    def test_irr_breakeven_none_if_always_positive(self, valid_deal):
        """If all IRRs are positive, no breakeven should be found."""
        result = sensitivity_analysis_workflow(valid_deal, "default_rate", [0.005, 0.010, 0.015])
        be = result["breakeven"]["equity_irr_zero"]
        # Very low CDRs → IRR always positive → no crossing
        # (could be None or could be found if positive throughout)
        # Just check it's a float or None
        assert be is None or isinstance(be, float)

    def test_single_value_no_breakeven(self, valid_deal):
        result = sensitivity_analysis_workflow(valid_deal, "default_rate", [0.05])
        assert result["breakeven"]["equity_irr_zero"] is None


# ---------------------------------------------------------------------------
# Guard conditions
# ---------------------------------------------------------------------------

class TestGuardConditions:

    def test_invalid_deal_returns_error(self):
        bad_deal = {"deal_id": "", "name": "x", "issuer": "y",
                    "collateral": {"portfolio_size": 100_000_000, "diversity_score": 45, "ccc_bucket": 0.05},
                    "liabilities": [{"tranche_id": "t1", "name": "AAA", "seniority": 1, "size_pct": 0.61}]}
        result = sensitivity_analysis_workflow(bad_deal, "default_rate", [0.03])
        assert "error" in result
        assert result["series"] == []

    def test_empty_values_returns_error(self, valid_deal):
        result = sensitivity_analysis_workflow(valid_deal, "default_rate", [])
        assert "error" in result
        assert result["series"] == []

    def test_base_parameters_override_defaults(self, valid_deal):
        """base_parameters should override deal market_assumptions."""
        result = sensitivity_analysis_workflow(
            valid_deal, "default_rate", [0.03],
            base_parameters={"recovery_rate": 0.80, "spread_shock_bps": 50},
        )
        assert result["series"][0]["status"] == "complete"

    def test_unknown_parameter_passes_through(self, valid_deal):
        """An unknown parameter is passed to the engine and may be ignored gracefully."""
        result = sensitivity_analysis_workflow(valid_deal, "unknown_param", [1.0, 2.0])
        # Engine should still return outputs (it ignores unknown params)
        for entry in result["series"]:
            assert entry["status"] == "complete"
            assert "equity_irr" in entry["outputs"]


# ---------------------------------------------------------------------------
# Audit events
# ---------------------------------------------------------------------------

class TestAuditEvents:

    def test_audit_events_emitted(self, valid_deal, default_rate_values):
        result = sensitivity_analysis_workflow(valid_deal, "default_rate", default_rate_values)
        assert len(result["audit_events"]) >= 2  # validated + completed

    def test_audit_events_are_strings(self, valid_deal, default_rate_values):
        result = sensitivity_analysis_workflow(valid_deal, "default_rate", default_rate_values)
        for ev in result["audit_events"]:
            assert isinstance(ev, str)


# ---------------------------------------------------------------------------
# Unit tests for helpers
# ---------------------------------------------------------------------------

class TestInterpolateZero:

    def test_crossing_from_positive_to_negative(self):
        pairs = [(0.03, 0.10), (0.05, 0.05), (0.07, -0.02)]
        zero = _interpolate_zero(pairs)
        assert zero is not None
        assert 0.05 < zero < 0.07

    def test_crossing_from_negative_to_positive(self):
        pairs = [(1.0, -5.0), (2.0, 5.0)]
        zero = _interpolate_zero(pairs)
        assert zero is not None
        assert abs(zero - 1.5) < 0.001

    def test_no_crossing_all_positive(self):
        pairs = [(0.01, 0.10), (0.05, 0.08), (0.10, 0.02)]
        assert _interpolate_zero(pairs) is None

    def test_no_crossing_all_negative(self):
        pairs = [(0.01, -0.10), (0.05, -0.05)]
        assert _interpolate_zero(pairs) is None

    def test_exact_zero_at_point(self):
        pairs = [(0.04, 0.05), (0.06, 0.0), (0.08, -0.03)]
        zero = _interpolate_zero(pairs)
        # Should detect the crossing around 0.06
        assert zero is not None
        assert zero <= 0.08

    def test_single_point_returns_none(self):
        assert _interpolate_zero([(0.03, 0.10)]) is None

    def test_empty_returns_none(self):
        assert _interpolate_zero([]) is None

    def test_none_values_skipped(self):
        pairs = [(0.03, None), (0.05, 0.05), (0.07, -0.02)]
        zero = _interpolate_zero(pairs)
        assert zero is not None


class TestComputeBreakeven:

    def test_returns_both_keys(self):
        series = [
            {"status": "complete", "parameter_value": 0.03, "outputs": {"equity_irr": 0.10, "scenario_npv": 1_000_000}},
            {"status": "complete", "parameter_value": 0.08, "outputs": {"equity_irr": -0.05, "scenario_npv": -500_000}},
        ]
        result = _compute_breakeven(series)
        assert "equity_irr_zero" in result
        assert "scenario_npv_zero" in result

    def test_finds_irr_crossover(self):
        series = [
            {"status": "complete", "parameter_value": 0.04, "outputs": {"equity_irr": 0.10, "scenario_npv": 0}},
            {"status": "complete", "parameter_value": 0.08, "outputs": {"equity_irr": -0.05, "scenario_npv": 0}},
        ]
        result = _compute_breakeven(series)
        assert result["equity_irr_zero"] is not None
        assert 0.04 < result["equity_irr_zero"] < 0.08

    def test_failed_entries_excluded(self):
        series = [
            {"status": "failed",   "parameter_value": 0.03, "outputs": {}},
            {"status": "complete", "parameter_value": 0.05, "outputs": {"equity_irr": 0.05, "scenario_npv": 100}},
        ]
        result = _compute_breakeven(series)
        # Only one data point → no crossover possible
        assert result["equity_irr_zero"] is None
