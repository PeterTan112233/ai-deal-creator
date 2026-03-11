"""
tests/test_portfolio_scoring_workflow.py

Tests for app/workflows/portfolio_scoring_workflow.py

Covers:
  - Return structure (all required keys)
  - Scored deals count matches input
  - Grade distribution adds up
  - Score ranking is sorted descending
  - Portfolio average is in 0–100
  - Needs attention contains only C/D or flagged deals
  - Scorecard report contains [demo] and header
  - Empty input returns error
  - Single deal works
  - Audit events emitted
"""

import json
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from app.workflows.portfolio_scoring_workflow import portfolio_scoring_workflow


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _load_all_deals() -> list:
    with open("data/samples/sample_deal_inputs.json") as f:
        data = json.load(f)
    return data["deals"]


def _us_bsl():
    for d in _load_all_deals():
        if "US BSL" in d.get("_label", ""):
            return d
    raise KeyError("US BSL deal not found")


def _eu_clo():
    for d in _load_all_deals():
        if "EU CLO" in d.get("_label", ""):
            return d
    raise KeyError("EU CLO deal not found")


def _mm_clo():
    for d in _load_all_deals():
        if "Middle Market" in d.get("_label", ""):
            return d
    raise KeyError("Middle Market deal not found")


@pytest.fixture(scope="module")
def three_deals():
    return [_us_bsl(), _eu_clo(), _mm_clo()]


@pytest.fixture(scope="module")
def scorecard(three_deals):
    return portfolio_scoring_workflow(three_deals, actor="test")


@pytest.fixture(scope="module")
def single_deal():
    return [_us_bsl()]


@pytest.fixture(scope="module")
def single_scorecard(single_deal):
    return portfolio_scoring_workflow(single_deal, actor="test")


# ---------------------------------------------------------------------------
# Return structure
# ---------------------------------------------------------------------------

class TestReturnStructure:

    def test_returns_dict(self, scorecard):
        assert isinstance(scorecard, dict)

    def test_has_required_keys(self, scorecard):
        for key in (
            "scorecard_id", "run_at", "deal_count", "scored_count",
            "deals", "score_ranking", "grade_distribution",
            "portfolio_avg_score", "needs_attention",
            "scorecard_report", "audit_events", "is_mock", "error",
        ):
            assert key in scorecard, f"Missing key: {key}"

    def test_no_error(self, scorecard):
        assert scorecard["error"] is None

    def test_is_mock_true(self, scorecard):
        assert scorecard["is_mock"] is True

    def test_scorecard_id_prefixed(self, scorecard):
        assert scorecard["scorecard_id"].startswith("scorecard-")

    def test_run_at_is_string(self, scorecard):
        assert isinstance(scorecard["run_at"], str)
        assert "T" in scorecard["run_at"]  # ISO-8601


# ---------------------------------------------------------------------------
# Deal counts
# ---------------------------------------------------------------------------

class TestDealCounts:

    def test_deal_count_matches_input(self, scorecard, three_deals):
        assert scorecard["deal_count"] == len(three_deals)

    def test_scored_count_positive(self, scorecard):
        assert scorecard["scored_count"] > 0

    def test_scored_count_le_deal_count(self, scorecard):
        assert scorecard["scored_count"] <= scorecard["deal_count"]

    def test_deals_list_length(self, scorecard, three_deals):
        assert len(scorecard["deals"]) == len(three_deals)

    def test_deals_have_required_fields(self, scorecard):
        for d in scorecard["deals"]:
            for key in ("deal_id", "name", "composite_score", "grade",
                        "grade_label", "top_drivers", "risk_flags",
                        "status", "error"):
                assert key in d, f"Deal missing key: {key}"

    def test_ok_deals_have_no_error(self, scorecard):
        for d in scorecard["deals"]:
            if d["status"] == "ok":
                assert d["error"] is None

    def test_ok_deals_have_score(self, scorecard):
        for d in scorecard["deals"]:
            if d["status"] == "ok":
                assert d["composite_score"] is not None


# ---------------------------------------------------------------------------
# Score ranking
# ---------------------------------------------------------------------------

class TestScoreRanking:

    def test_ranking_has_entries(self, scorecard):
        assert len(scorecard["score_ranking"]) > 0

    def test_ranking_sorted_descending(self, scorecard):
        scores = [e["composite_score"] for e in scorecard["score_ranking"]]
        assert scores == sorted(scores, reverse=True)

    def test_ranking_has_rank_field(self, scorecard):
        for i, e in enumerate(scorecard["score_ranking"]):
            assert e["rank"] == i + 1

    def test_ranking_has_deal_fields(self, scorecard):
        for e in scorecard["score_ranking"]:
            for key in ("rank", "deal_id", "name", "composite_score", "grade"):
                assert key in e

    def test_ranking_count_matches_scored_count(self, scorecard):
        assert len(scorecard["score_ranking"]) == scorecard["scored_count"]

    def test_scores_in_range(self, scorecard):
        for e in scorecard["score_ranking"]:
            assert 0 <= e["composite_score"] <= 100


# ---------------------------------------------------------------------------
# Grade distribution
# ---------------------------------------------------------------------------

class TestGradeDistribution:

    def test_grade_distribution_has_all_grades(self, scorecard):
        gd = scorecard["grade_distribution"]
        for g in ("A", "B", "C", "D"):
            assert g in gd

    def test_grade_distribution_sums_to_scored_count(self, scorecard):
        total = sum(scorecard["grade_distribution"].values())
        assert total == scorecard["scored_count"]

    def test_grade_distribution_no_negatives(self, scorecard):
        for v in scorecard["grade_distribution"].values():
            assert v >= 0


# ---------------------------------------------------------------------------
# Portfolio average
# ---------------------------------------------------------------------------

class TestPortfolioAverage:

    def test_avg_score_is_float(self, scorecard):
        avg = scorecard["portfolio_avg_score"]
        assert avg is not None
        assert isinstance(avg, float)

    def test_avg_score_in_range(self, scorecard):
        avg = scorecard["portfolio_avg_score"]
        assert 0 <= avg <= 100

    def test_avg_score_between_min_and_max(self, scorecard):
        scores = [e["composite_score"] for e in scorecard["score_ranking"]]
        avg = scorecard["portfolio_avg_score"]
        assert min(scores) <= avg <= max(scores)


# ---------------------------------------------------------------------------
# Needs attention
# ---------------------------------------------------------------------------

class TestNeedsAttention:

    def test_needs_attention_is_list(self, scorecard):
        assert isinstance(scorecard["needs_attention"], list)

    def test_needs_attention_items_have_required_fields(self, scorecard):
        for d in scorecard["needs_attention"]:
            for key in ("deal_id", "name", "grade", "score", "reasons"):
                assert key in d

    def test_needs_attention_only_cd_or_flagged(self, scorecard):
        """Every item must have grade C/D or at least one reason (risk flag)."""
        for item in scorecard["needs_attention"]:
            in_cd = item["grade"] in ("C", "D")
            has_reasons = len(item["reasons"]) > 0
            assert in_cd or has_reasons, (
                f"Deal {item['deal_id']} in needs_attention but grade={item['grade']} "
                f"and no reasons"
            )

    def test_good_deals_not_in_attention_if_no_flags(self, scorecard):
        """A-grade deals with no risk_flags should not be in needs_attention."""
        attention_ids = {d["deal_id"] for d in scorecard["needs_attention"]}
        for d in scorecard["deals"]:
            if d["status"] == "ok" and d["grade"] == "A" and not d["risk_flags"]:
                assert d["deal_id"] not in attention_ids


# ---------------------------------------------------------------------------
# Scorecard report
# ---------------------------------------------------------------------------

class TestScorecardReport:

    def test_report_is_string(self, scorecard):
        assert isinstance(scorecard["scorecard_report"], str)

    def test_report_non_empty(self, scorecard):
        assert len(scorecard["scorecard_report"]) > 100

    def test_report_contains_demo_tag(self, scorecard):
        assert "[demo]" in scorecard["scorecard_report"]

    def test_report_contains_portfolio_header(self, scorecard):
        assert "PORTFOLIO SCORECARD" in scorecard["scorecard_report"]

    def test_report_contains_scorecard_id(self, scorecard):
        assert scorecard["scorecard_id"] in scorecard["scorecard_report"]

    def test_report_contains_score_ranking(self, scorecard):
        assert "SCORE RANKING" in scorecard["scorecard_report"]

    def test_report_contains_grade_distribution(self, scorecard):
        assert "GRADE DISTRIBUTION" in scorecard["scorecard_report"]


# ---------------------------------------------------------------------------
# Single deal
# ---------------------------------------------------------------------------

class TestSingleDeal:

    def test_single_deal_no_error(self, single_scorecard):
        assert single_scorecard["error"] is None

    def test_single_deal_count(self, single_scorecard):
        assert single_scorecard["deal_count"] == 1
        assert single_scorecard["scored_count"] == 1

    def test_single_deal_avg_equals_score(self, single_scorecard):
        score = single_scorecard["score_ranking"][0]["composite_score"]
        avg = single_scorecard["portfolio_avg_score"]
        assert abs(avg - score) < 0.01


# ---------------------------------------------------------------------------
# Empty input
# ---------------------------------------------------------------------------

class TestEmptyInput:

    def test_empty_returns_error(self):
        result = portfolio_scoring_workflow([], actor="test")
        assert result["error"] is not None

    def test_empty_zero_deal_count(self):
        result = portfolio_scoring_workflow([], actor="test")
        assert result["deal_count"] == 0

    def test_empty_no_avg_score(self):
        result = portfolio_scoring_workflow([], actor="test")
        assert result["portfolio_avg_score"] is None

    def test_empty_scorecard_id_present(self):
        result = portfolio_scoring_workflow([], actor="test")
        assert result["scorecard_id"].startswith("scorecard-")


# ---------------------------------------------------------------------------
# Audit events
# ---------------------------------------------------------------------------

class TestAuditEvents:

    def test_audit_events_emitted(self, scorecard):
        # At minimum: one event per deal scored + portfolio.completed
        assert len(scorecard["audit_events"]) >= scorecard["scored_count"] + 1

    def test_audit_events_are_strings(self, scorecard):
        for ev in scorecard["audit_events"]:
            assert isinstance(ev, str)

    def test_different_runs_different_scorecard_ids(self, three_deals):
        r1 = portfolio_scoring_workflow(three_deals, actor="test")
        r2 = portfolio_scoring_workflow(three_deals, actor="test")
        assert r1["scorecard_id"] != r2["scorecard_id"]
