"""
tests/test_deal_analytics_workflow.py

Tests for app/workflows/deal_analytics_workflow.py

Covers:
  - Return structure and all expected keys
  - Standard 4-scenario suite runs
  - Sensitivity sweeps run when run_sensitivity=True
  - Sensitivity skipped when run_sensitivity=False
  - Key metrics come from base case
  - Breakeven thresholds populated
  - Analytics report is a non-empty string with required sections
  - Invalid deal returns error early
  - Custom scenarios override the standard suite
  - Audit events emitted
  - Analytics report tagged [demo]
"""

import json
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.workflows.deal_analytics_workflow import deal_analytics_workflow, _extract_key_metrics, _extract_breakeven


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
def analytics_result(valid_deal):
    """Run analytics once with sensitivity disabled for speed."""
    return deal_analytics_workflow(valid_deal, run_sensitivity=False)


@pytest.fixture
def full_analytics_result(valid_deal):
    """Full run including sensitivity sweeps."""
    return deal_analytics_workflow(valid_deal, run_sensitivity=True)


# ---------------------------------------------------------------------------
# Return structure
# ---------------------------------------------------------------------------

class TestReturnStructure:

    EXPECTED_KEYS = {
        "deal_id", "analysis_id", "analysed_at", "is_mock",
        "scenario_suite", "cdr_sensitivity", "rr_sensitivity",
        "summary_table", "key_metrics", "breakeven",
        "analytics_report", "audit_events",
    }

    def test_returns_dict(self, analytics_result):
        assert isinstance(analytics_result, dict)

    def test_all_expected_keys_present(self, analytics_result):
        assert self.EXPECTED_KEYS <= set(analytics_result.keys())

    def test_deal_id_matches(self, valid_deal, analytics_result):
        assert analytics_result["deal_id"] == valid_deal["deal_id"]

    def test_analysis_id_starts_with_prefix(self, analytics_result):
        assert analytics_result["analysis_id"].startswith("analytics-")

    def test_analysed_at_is_iso_string(self, analytics_result):
        from datetime import datetime
        ts = analytics_result["analysed_at"]
        assert isinstance(ts, str)
        datetime.fromisoformat(ts)  # must be valid ISO format

    def test_is_mock_true(self, analytics_result):
        assert analytics_result["is_mock"] is True

    def test_no_error_key_on_success(self, analytics_result):
        assert "error" not in analytics_result


# ---------------------------------------------------------------------------
# Scenario suite
# ---------------------------------------------------------------------------

class TestScenarioSuite:

    def test_four_scenarios_run_by_default(self, analytics_result):
        assert analytics_result["scenario_suite"]["scenarios_run"] == 4

    def test_standard_scenario_names(self, analytics_result):
        names = [r["scenario_name"] for r in analytics_result["scenario_suite"]["results"]]
        assert "Base" in names
        assert "Stress" in names

    def test_all_scenarios_complete(self, analytics_result):
        for r in analytics_result["scenario_suite"]["results"]:
            assert r["status"] == "complete"

    def test_irr_decreasing_across_standard_suite(self, analytics_result):
        results = analytics_result["scenario_suite"]["results"]
        irrs = [r["outputs"]["equity_irr"] for r in results]
        # Standard suite is ordered base→stress→deep stress → IRR should decrease
        for i in range(len(irrs) - 1):
            assert irrs[i] > irrs[i + 1], f"IRR not decreasing at position {i}"

    def test_summary_table_has_rows(self, analytics_result):
        assert len(analytics_result["summary_table"]) > 0

    def test_custom_scenarios_override_default(self, valid_deal):
        custom = [
            {"name": "My Base", "type": "base",
             "parameters": {"default_rate": 0.02, "recovery_rate": 0.70, "spread_shock_bps": 0}},
        ]
        result = deal_analytics_workflow(valid_deal, custom_scenarios=custom, run_sensitivity=False)
        assert result["scenario_suite"]["scenarios_run"] == 1
        assert result["scenario_suite"]["results"][0]["scenario_name"] == "My Base"


# ---------------------------------------------------------------------------
# Sensitivity sweeps
# ---------------------------------------------------------------------------

class TestSensitivitySweeps:

    def test_cdr_sensitivity_present_when_enabled(self, full_analytics_result):
        assert full_analytics_result["cdr_sensitivity"] is not None

    def test_rr_sensitivity_present_when_enabled(self, full_analytics_result):
        assert full_analytics_result["rr_sensitivity"] is not None

    def test_cdr_sensitivity_none_when_disabled(self, analytics_result):
        assert analytics_result["cdr_sensitivity"] is None

    def test_rr_sensitivity_none_when_disabled(self, analytics_result):
        assert analytics_result["rr_sensitivity"] is None

    def test_cdr_series_has_15_points(self, full_analytics_result):
        series = full_analytics_result["cdr_sensitivity"]["series"]
        assert len(series) == 15  # 1%..15%

    def test_rr_series_has_15_points(self, full_analytics_result):
        series = full_analytics_result["rr_sensitivity"]["series"]
        assert len(series) == 15  # 10%..80% in 5% steps


# ---------------------------------------------------------------------------
# Key metrics
# ---------------------------------------------------------------------------

class TestKeyMetrics:

    def test_key_metrics_has_equity_irr(self, analytics_result):
        assert "base_equity_irr" in analytics_result["key_metrics"]

    def test_key_metrics_base_irr_is_float(self, analytics_result):
        irr = analytics_result["key_metrics"]["base_equity_irr"]
        assert isinstance(irr, float)

    def test_key_metrics_base_irr_positive_for_healthy_deal(self, analytics_result):
        irr = analytics_result["key_metrics"]["base_equity_irr"]
        assert irr > 0, f"Base case IRR should be positive, got {irr:.2%}"

    def test_key_metrics_has_oc_and_ic_cushions(self, analytics_result):
        km = analytics_result["key_metrics"]
        assert "base_oc_cushion" in km
        assert "base_ic_cushion" in km

    def test_key_metrics_oc_positive(self, analytics_result):
        assert analytics_result["key_metrics"]["base_oc_cushion"] > 0

    def test_key_metrics_has_aaa_size(self, analytics_result):
        assert "aaa_size_pct" in analytics_result["key_metrics"]


# ---------------------------------------------------------------------------
# Breakeven
# ---------------------------------------------------------------------------

class TestBreakeven:

    def test_breakeven_dict_present(self, analytics_result):
        assert isinstance(analytics_result["breakeven"], dict)

    def test_breakeven_empty_when_no_sensitivity(self, analytics_result):
        # Without sensitivity sweeps, breakeven should be empty
        assert analytics_result["breakeven"] == {}

    def test_cdr_breakeven_found_in_full_run(self, full_analytics_result):
        be = full_analytics_result["breakeven"]
        assert "cdr_irr_zero" in be
        # For a healthy deal, breakeven CDR should be between 5% and 15%
        cdr_be = be["cdr_irr_zero"]
        if cdr_be is not None:
            assert 0.01 <= cdr_be <= 0.15, f"Breakeven CDR {cdr_be:.2%} outside expected range"

    def test_rr_breakeven_key_present_in_full_run(self, full_analytics_result):
        assert "rr_irr_zero" in full_analytics_result["breakeven"]


# ---------------------------------------------------------------------------
# Analytics report
# ---------------------------------------------------------------------------

class TestAnalyticsReport:

    def test_report_is_non_empty_string(self, analytics_result):
        report = analytics_result["analytics_report"]
        assert isinstance(report, str)
        assert len(report) > 100

    def test_report_tagged_demo(self, analytics_result):
        report = analytics_result["analytics_report"]
        assert "[demo]" in report.lower() or "DEMO" in report

    def test_report_contains_scenario_suite_section(self, analytics_result):
        report = analytics_result["analytics_report"]
        assert "SCENARIO SUITE" in report

    def test_report_contains_key_metrics_section(self, analytics_result):
        report = analytics_result["analytics_report"]
        assert "KEY METRICS" in report

    def test_report_contains_breakeven_section(self, analytics_result):
        report = analytics_result["analytics_report"]
        assert "BREAKEVEN" in report

    def test_report_contains_deal_id(self, valid_deal, analytics_result):
        assert valid_deal["deal_id"] in analytics_result["analytics_report"]

    def test_report_contains_analysis_id(self, analytics_result):
        assert analytics_result["analysis_id"] in analytics_result["analytics_report"]

    def test_full_report_contains_cdr_sensitivity_section(self, full_analytics_result):
        assert "CDR SENSITIVITY" in full_analytics_result["analytics_report"]

    def test_report_has_equity_irr_value(self, analytics_result):
        report = analytics_result["analytics_report"]
        assert "Equity IRR" in report

    def test_engine_disclaimer_present(self, analytics_result):
        report = analytics_result["analytics_report"]
        assert "DEMO_ANALYTICAL_ENGINE" in report


# ---------------------------------------------------------------------------
# Guard conditions
# ---------------------------------------------------------------------------

class TestGuardConditions:

    def test_invalid_deal_returns_error(self):
        bad_deal = {"deal_id": "", "name": "x", "issuer": "y",
                    "collateral": {"portfolio_size": 100_000_000, "diversity_score": 45, "ccc_bucket": 0.05},
                    "liabilities": [{"tranche_id": "t1", "name": "AAA", "seniority": 1, "size_pct": 0.61}]}
        result = deal_analytics_workflow(bad_deal)
        assert "error" in result
        assert result["analytics_report"] == ""

    def test_invalid_deal_scenario_suite_empty(self):
        bad_deal = {"deal_id": "", "name": "x", "issuer": "y",
                    "collateral": {"portfolio_size": 100_000_000, "diversity_score": 45, "ccc_bucket": 0.05},
                    "liabilities": [{"tranche_id": "t1", "name": "AAA", "seniority": 1, "size_pct": 0.61}]}
        result = deal_analytics_workflow(bad_deal)
        assert result["scenario_suite"] == {}


# ---------------------------------------------------------------------------
# Audit events
# ---------------------------------------------------------------------------

class TestAuditEvents:

    def test_audit_events_emitted(self, analytics_result):
        assert len(analytics_result["audit_events"]) >= 3  # validated + batch events + completed

    def test_full_run_more_audit_events(self, full_analytics_result):
        # Full run has more audit events due to sensitivity sweeps
        assert len(full_analytics_result["audit_events"]) > 4

    def test_audit_events_are_strings(self, analytics_result):
        for ev in analytics_result["audit_events"]:
            assert isinstance(ev, str)


# ---------------------------------------------------------------------------
# Unit tests for helpers
# ---------------------------------------------------------------------------

class TestExtractKeyMetrics:

    def test_returns_empty_on_empty_suite(self):
        assert _extract_key_metrics({}) == {}

    def test_returns_empty_on_no_results(self):
        assert _extract_key_metrics({"results": []}) == {}

    def test_picks_base_scenario_by_name(self):
        suite = {
            "results": [
                {"scenario_name": "Stress", "outputs": {"equity_irr": 0.05}},
                {"scenario_name": "Base",   "outputs": {"equity_irr": 0.15}},
            ]
        }
        km = _extract_key_metrics(suite)
        assert km["base_equity_irr"] == 0.15

    def test_falls_back_to_first_result_if_no_base(self):
        suite = {
            "results": [
                {"scenario_name": "Custom", "outputs": {"equity_irr": 0.12}},
            ]
        }
        km = _extract_key_metrics(suite)
        assert km["base_equity_irr"] == 0.12


class TestExtractBreakeven:

    def test_returns_empty_on_no_sweeps(self):
        assert _extract_breakeven(None, None) == {}

    def test_cdr_keys_present_when_cdr_provided(self):
        cdr = {"breakeven": {"equity_irr_zero": 0.07, "scenario_npv_zero": 0.08}}
        result = _extract_breakeven(cdr, None)
        assert "cdr_irr_zero" in result
        assert result["cdr_irr_zero"] == 0.07

    def test_rr_keys_present_when_rr_provided(self):
        rr = {"breakeven": {"equity_irr_zero": 0.25, "scenario_npv_zero": None}}
        result = _extract_breakeven(None, rr)
        assert "rr_irr_zero" in result
        assert result["rr_irr_zero"] == 0.25
