"""
tests/test_deal_health_workflow.py

Tests for app/workflows/deal_health_workflow.py

Covers:
  - Return structure (all required keys)
  - Overall grade is A-D
  - Score summary populated
  - Stress summary populated (base_irr, drawdown)
  - Watchlist summary populated
  - KRI list has all 6 indicators
  - KRI status is ok/warn/critical/unknown
  - Action items list is non-empty
  - Health report has [demo] tag and required sections
  - Invalid deal returns error
  - Audit events emitted
"""

import json
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from app.workflows.deal_health_workflow import deal_health_workflow


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _load_deal(label: str) -> dict:
    with open("data/samples/sample_deal_inputs.json") as f:
        data = json.load(f)
    for d in data["deals"]:
        if label in d.get("_label", ""):
            return d
    raise KeyError(f"No deal matching '{label}'")


@pytest.fixture(scope="module")
def us_bsl():
    return _load_deal("US BSL CLO")


@pytest.fixture(scope="module")
def health(us_bsl):
    return deal_health_workflow(us_bsl, actor="test")


# ---------------------------------------------------------------------------
# Return structure
# ---------------------------------------------------------------------------

class TestReturnStructure:

    def test_returns_dict(self, health):
        assert isinstance(health, dict)

    def test_has_required_keys(self, health):
        for key in (
            "health_id", "deal_id", "checked_at", "overall_grade", "overall_score",
            "score_summary", "stress_summary", "watchlist_summary",
            "key_risk_indicators", "action_items",
            "health_report", "audit_events", "is_mock", "error",
        ):
            assert key in health, f"Missing key: {key}"

    def test_no_error(self, health):
        assert health["error"] is None

    def test_is_mock_true(self, health):
        assert health["is_mock"] is True

    def test_health_id_prefixed(self, health):
        assert health["health_id"].startswith("health-")

    def test_checked_at_is_iso(self, health):
        assert "T" in health["checked_at"]

    def test_deal_id_correct(self, us_bsl, health):
        assert health["deal_id"] == us_bsl["deal_id"]


# ---------------------------------------------------------------------------
# Overall grade / score
# ---------------------------------------------------------------------------

class TestOverallGrade:

    def test_overall_grade_is_valid(self, health):
        assert health["overall_grade"] in ("A", "B", "C", "D")

    def test_overall_score_in_range(self, health):
        assert 0 <= health["overall_score"] <= 100

    def test_us_bsl_gets_good_grade(self, health):
        assert health["overall_grade"] in ("A", "B")


# ---------------------------------------------------------------------------
# Score summary
# ---------------------------------------------------------------------------

class TestScoreSummary:

    def test_score_summary_is_dict(self, health):
        assert isinstance(health["score_summary"], dict)

    def test_score_summary_has_required_keys(self, health):
        for key in ("composite_score", "grade", "grade_label",
                    "top_drivers", "risk_flags", "dimension_scores"):
            assert key in health["score_summary"]

    def test_score_summary_grade_matches_overall(self, health):
        assert health["score_summary"]["grade"] == health["overall_grade"]

    def test_top_drivers_are_strings(self, health):
        for d in health["score_summary"]["top_drivers"]:
            assert isinstance(d, str)


# ---------------------------------------------------------------------------
# Stress summary
# ---------------------------------------------------------------------------

class TestStressSummary:

    def test_stress_summary_is_dict(self, health):
        assert isinstance(health["stress_summary"], dict)

    def test_stress_summary_has_required_keys(self, health):
        for key in ("base_irr", "base_oc", "min_stress_irr",
                    "irr_drawdown", "stress_runs"):
            assert key in health["stress_summary"]

    def test_base_irr_is_positive(self, health):
        assert health["stress_summary"]["base_irr"] > 0

    def test_min_stress_irr_le_base(self, health):
        base = health["stress_summary"]["base_irr"]
        stress = health["stress_summary"]["min_stress_irr"]
        if stress is not None:
            assert stress <= base

    def test_irr_drawdown_non_negative(self, health):
        dd = health["stress_summary"]["irr_drawdown"]
        if dd is not None:
            assert dd >= 0

    def test_stress_runs_list(self, health):
        runs = health["stress_summary"]["stress_runs"]
        assert isinstance(runs, list)
        assert len(runs) >= 1

    def test_stress_runs_have_template_id(self, health):
        for run in health["stress_summary"]["stress_runs"]:
            assert "template_id" in run
            assert "equity_irr" in run


# ---------------------------------------------------------------------------
# Watchlist summary
# ---------------------------------------------------------------------------

class TestWatchlistSummary:

    def test_watchlist_summary_is_dict(self, health):
        assert isinstance(health["watchlist_summary"], dict)

    def test_watchlist_summary_has_required_keys(self, health):
        for key in ("items_checked", "triggered_count",
                    "critical_count", "triggered_alerts"):
            assert key in health["watchlist_summary"]

    def test_counts_are_non_negative(self, health):
        ws = health["watchlist_summary"]
        assert ws["items_checked"] >= 0
        assert ws["triggered_count"] >= 0
        assert ws["critical_count"] >= 0

    def test_triggered_count_le_items_checked(self, health):
        ws = health["watchlist_summary"]
        if ws["items_checked"] > 0:
            assert ws["triggered_count"] <= ws["items_checked"]


# ---------------------------------------------------------------------------
# Key Risk Indicators
# ---------------------------------------------------------------------------

class TestKeyRiskIndicators:

    _EXPECTED_KRI_NAMES = {
        "equity_irr", "oc_cushion_aaa", "irr_drawdown",
        "composite_score", "ccc_bucket", "diversity_score",
    }

    def test_kris_is_list(self, health):
        assert isinstance(health["key_risk_indicators"], list)

    def test_has_all_six_kris(self, health):
        names = {k["name"] for k in health["key_risk_indicators"]}
        assert names == self._EXPECTED_KRI_NAMES

    def test_each_kri_has_required_fields(self, health):
        for kri in health["key_risk_indicators"]:
            for field in ("name", "label", "value", "format", "status",
                          "direction", "ok_threshold", "warn_threshold"):
                assert field in kri, f"KRI '{kri.get('name')}' missing field: {field}"

    def test_kri_status_is_valid(self, health):
        valid = {"ok", "warn", "critical", "unknown"}
        for kri in health["key_risk_indicators"]:
            assert kri["status"] in valid, (
                f"KRI '{kri['name']}' has invalid status: {kri['status']}"
            )

    def test_equity_irr_kri_present(self, health):
        kri = next(k for k in health["key_risk_indicators"] if k["name"] == "equity_irr")
        assert kri["value"] is not None

    def test_composite_score_kri_matches_overall(self, health):
        kri = next(k for k in health["key_risk_indicators"]
                   if k["name"] == "composite_score")
        assert abs(kri["value"] - health["overall_score"]) < 0.01


# ---------------------------------------------------------------------------
# Action items
# ---------------------------------------------------------------------------

class TestActionItems:

    def test_action_items_is_list(self, health):
        assert isinstance(health["action_items"], list)

    def test_action_items_non_empty(self, health):
        assert len(health["action_items"]) >= 1

    def test_action_items_are_strings(self, health):
        for item in health["action_items"]:
            assert isinstance(item, str)
            assert len(item) > 5


# ---------------------------------------------------------------------------
# Health report
# ---------------------------------------------------------------------------

class TestHealthReport:

    def test_report_is_string(self, health):
        assert isinstance(health["health_report"], str)

    def test_report_non_empty(self, health):
        assert len(health["health_report"]) > 200

    def test_report_contains_demo_tag(self, health):
        assert "[demo]" in health["health_report"]

    def test_report_contains_health_id(self, health):
        assert health["health_id"] in health["health_report"]

    def test_report_contains_kri_section(self, health):
        assert "KEY RISK INDICATORS" in health["health_report"]

    def test_report_contains_scoring_section(self, health):
        assert "SCORING SUMMARY" in health["health_report"]

    def test_report_contains_stress_section(self, health):
        assert "STRESS SUMMARY" in health["health_report"]

    def test_report_contains_action_items(self, health):
        assert "ACTION ITEMS" in health["health_report"]

    def test_report_contains_grade(self, health):
        assert health["overall_grade"] in health["health_report"]


# ---------------------------------------------------------------------------
# Guard conditions
# ---------------------------------------------------------------------------

class TestGuardConditions:

    def test_invalid_deal_returns_error(self):
        bad = {
            "deal_id": "bad-health", "name": "x", "issuer": "y",
            "collateral": {"portfolio_size": 0, "diversity_score": 10, "ccc_bucket": 0.05},
            "liabilities": [{"tranche_id": "t1", "name": "AAA", "seniority": 1}],
        }
        result = deal_health_workflow(bad, actor="test")
        assert result["error"] is not None

    def test_invalid_deal_has_health_id(self):
        bad = {
            "deal_id": "bad-health2", "name": "x", "issuer": "y",
            "collateral": {"portfolio_size": 0, "diversity_score": 10, "ccc_bucket": 0.05},
            "liabilities": [{"tranche_id": "t1", "name": "AAA", "seniority": 1}],
        }
        result = deal_health_workflow(bad, actor="test")
        assert result["health_id"].startswith("health-")

    def test_different_runs_different_health_ids(self, us_bsl):
        r1 = deal_health_workflow(us_bsl, actor="test")
        r2 = deal_health_workflow(us_bsl, actor="test")
        assert r1["health_id"] != r2["health_id"]


# ---------------------------------------------------------------------------
# Audit events
# ---------------------------------------------------------------------------

class TestAuditEvents:

    def test_audit_events_emitted(self, health):
        # Scoring events + stress runs + watchlist + health.checked
        assert len(health["audit_events"]) >= 5

    def test_audit_events_are_strings(self, health):
        for ev in health["audit_events"]:
            assert isinstance(ev, str)
