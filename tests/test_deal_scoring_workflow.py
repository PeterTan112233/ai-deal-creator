"""
tests/test_deal_scoring_workflow.py

Tests for app/workflows/deal_scoring_workflow.py

Covers:
  - Return structure
  - Grade is A-D
  - Composite score 0-100
  - Dimension scores populated
  - Stress resilience computed (stress templates ran)
  - Score report generated with [demo] tag
  - Invalid deal returns error
  - Audit events emitted
"""

import json
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from app.workflows.deal_scoring_workflow import deal_scoring_workflow


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
def scored(us_bsl):
    return deal_scoring_workflow(us_bsl, actor="test")


# ---------------------------------------------------------------------------
# Return structure
# ---------------------------------------------------------------------------

class TestReturnStructure:

    def test_returns_dict(self, scored):
        assert isinstance(scored, dict)

    def test_has_required_keys(self, scored):
        for key in ("deal_id", "scoring_id", "scored_at", "composite_score",
                    "grade", "grade_label", "dimension_scores", "top_drivers",
                    "risk_flags", "score_report", "audit_events", "is_mock", "error"):
            assert key in scored

    def test_no_error(self, scored):
        assert scored["error"] is None

    def test_is_mock_true(self, scored):
        assert scored["is_mock"] is True

    def test_scoring_id_prefixed(self, scored):
        assert scored["scoring_id"].startswith("score-")

    def test_deal_id_correct(self, us_bsl, scored):
        assert scored["deal_id"] == us_bsl["deal_id"]


# ---------------------------------------------------------------------------
# Score values
# ---------------------------------------------------------------------------

class TestScoreValues:

    def test_composite_score_in_range(self, scored):
        assert 0 <= scored["composite_score"] <= 100

    def test_grade_is_valid(self, scored):
        assert scored["grade"] in ("A", "B", "C", "D")

    def test_grade_label_is_string(self, scored):
        assert isinstance(scored["grade_label"], str)
        assert len(scored["grade_label"]) > 0

    def test_us_bsl_gets_good_grade(self, scored):
        # US BSL with good metrics should score B or better
        assert scored["grade"] in ("A", "B")

    def test_all_dimension_scores_in_range(self, scored):
        for dim in scored["dimension_scores"].values():
            assert 0 <= dim["score"] <= 100

    def test_stress_resilience_populated(self, scored):
        # Stress templates ran, so we have a real stress_drawdown
        stress = scored["dimension_scores"]["stress_resilience"]
        assert stress["score"] >= 0
        inputs = stress.get("inputs", {})
        # base_irr should be captured
        assert "base_irr" in inputs

    def test_irr_quality_dimension_has_irr(self, scored):
        irr_dim = scored["dimension_scores"]["irr_quality"]
        assert irr_dim["inputs"]["equity_irr"] is not None

    def test_top_drivers_are_strings(self, scored):
        for d in scored["top_drivers"]:
            assert isinstance(d, str)

    def test_two_top_drivers(self, scored):
        assert len(scored["top_drivers"]) == 2


# ---------------------------------------------------------------------------
# Score report
# ---------------------------------------------------------------------------

class TestScoreReport:

    def test_report_is_string(self, scored):
        assert isinstance(scored["score_report"], str)

    def test_report_non_empty(self, scored):
        assert len(scored["score_report"]) > 100

    def test_report_contains_demo_tag(self, scored):
        assert "[demo]" in scored["score_report"]

    def test_report_contains_grade(self, scored):
        assert scored["grade"] in scored["score_report"]

    def test_report_contains_deal_name(self, us_bsl, scored):
        assert us_bsl["name"] in scored["score_report"]

    def test_report_contains_composite_score(self, scored):
        score_str = f"{scored['composite_score']:.1f}"
        assert score_str in scored["score_report"]


# ---------------------------------------------------------------------------
# Guard conditions
# ---------------------------------------------------------------------------

class TestGuardConditions:

    def test_invalid_deal_returns_error(self):
        bad = {"deal_id": "bad", "name": "x", "issuer": "y",
               "collateral": {"portfolio_size": 0, "diversity_score": 10, "ccc_bucket": 0.05},
               "liabilities": [{"tranche_id": "t1", "name": "AAA", "seniority": 1}]}
        result = deal_scoring_workflow(bad, actor="test")
        assert result["error"] is not None
        assert result["composite_score"] is None

    def test_invalid_deal_empty_dimensions(self):
        bad = {"deal_id": "bad2", "name": "x", "issuer": "y",
               "collateral": {"portfolio_size": 0, "diversity_score": 10, "ccc_bucket": 0.05},
               "liabilities": [{"tranche_id": "t1", "name": "AAA", "seniority": 1}]}
        result = deal_scoring_workflow(bad, actor="test")
        assert result["dimension_scores"] == {}


# ---------------------------------------------------------------------------
# Audit events
# ---------------------------------------------------------------------------

class TestAuditEvents:

    def test_audit_events_emitted(self, scored):
        # Base-case + 2 stress scenarios + deal.scored = at least 4 events
        assert len(scored["audit_events"]) >= 4

    def test_audit_events_are_strings(self, scored):
        for ev in scored["audit_events"]:
            assert isinstance(ev, str)

    def test_different_deals_different_scoring_ids(self, us_bsl):
        r1 = deal_scoring_workflow(us_bsl, actor="test")
        r2 = deal_scoring_workflow(us_bsl, actor="test")
        assert r1["scoring_id"] != r2["scoring_id"]
