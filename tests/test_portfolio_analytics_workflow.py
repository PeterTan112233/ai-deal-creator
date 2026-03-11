"""
tests/test_portfolio_analytics_workflow.py

Tests for app/workflows/portfolio_analytics_workflow.py

Covers:
  - Return structure
  - Aggregate computation
  - Metric rankings (correct order, correct direction)
  - Concentration breakdowns
  - Single deal works
  - Empty deal list returns error
  - Invalid deal handled gracefully (others still run)
  - Audit events emitted
  - Portfolio report generated
  - Custom metrics subset
"""

import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from app.workflows.portfolio_analytics_workflow import portfolio_analytics_workflow


# ---------------------------------------------------------------------------
# Fixtures
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
def eu_bsl():
    return _load_deal("EU CLO")


@pytest.fixture(scope="module")
def us_mm():
    return _load_deal("US Middle Market")


@pytest.fixture(scope="module")
def portfolio_two(us_bsl, eu_bsl):
    """Two-deal portfolio: US BSL + EU BSL."""
    return portfolio_analytics_workflow(
        [us_bsl, eu_bsl],
        actor="test",
    )


@pytest.fixture(scope="module")
def portfolio_three(us_bsl, eu_bsl, us_mm):
    """Three-deal portfolio."""
    return portfolio_analytics_workflow(
        [us_bsl, eu_bsl, us_mm],
        actor="test",
    )


# ---------------------------------------------------------------------------
# Return structure
# ---------------------------------------------------------------------------

class TestReturnStructure:

    def test_returns_dict(self, portfolio_two):
        assert isinstance(portfolio_two, dict)

    def test_has_required_keys(self, portfolio_two):
        for key in ("portfolio_id", "analysed_at", "deal_count", "deals",
                    "aggregate", "rankings", "concentration",
                    "portfolio_report", "audit_events", "is_mock", "error"):
            assert key in portfolio_two

    def test_no_error(self, portfolio_two):
        assert portfolio_two["error"] is None

    def test_is_mock(self, portfolio_two):
        assert portfolio_two["is_mock"] is True

    def test_deal_count(self, portfolio_two):
        assert portfolio_two["deal_count"] == 2

    def test_portfolio_id_prefixed(self, portfolio_two):
        assert portfolio_two["portfolio_id"].startswith("portfolio-")

    def test_analysed_at_is_string(self, portfolio_two):
        assert isinstance(portfolio_two["analysed_at"], str)


# ---------------------------------------------------------------------------
# Deal summaries
# ---------------------------------------------------------------------------

class TestDealSummaries:

    def test_deals_list_length(self, portfolio_two):
        assert len(portfolio_two["deals"]) == 2

    def test_each_deal_has_required_fields(self, portfolio_two):
        for d in portfolio_two["deals"]:
            for field in ("deal_id", "name", "region", "asset_class",
                          "portfolio_size", "key_metrics", "status", "error"):
                assert field in d

    def test_all_deals_ok(self, portfolio_two):
        for d in portfolio_two["deals"]:
            assert d["status"] == "ok"

    def test_deal_has_equity_irr(self, portfolio_two):
        for d in portfolio_two["deals"]:
            assert "equity_irr" in d["key_metrics"]

    def test_three_deal_portfolio(self, portfolio_three):
        assert portfolio_three["deal_count"] == 3
        assert len(portfolio_three["deals"]) == 3

    def test_invalid_deal_handled_gracefully(self, us_bsl):
        bad = {"deal_id": "bad-deal", "name": "Bad", "issuer": "x",
               "collateral": {"portfolio_size": 0, "diversity_score": 10, "ccc_bucket": 0.05},
               "liabilities": [{"tranche_id": "t1", "name": "AAA", "seniority": 1}]}
        result = portfolio_analytics_workflow([us_bsl, bad], actor="test")
        # One ok, one error — no top-level error
        assert result["error"] is None
        statuses = {d["deal_id"]: d["status"] for d in result["deals"]}
        assert statuses[us_bsl["deal_id"]] == "ok"
        assert statuses["bad-deal"] == "error"

    def test_bad_deal_error_message(self, us_bsl):
        bad = {"deal_id": "bad-deal2", "name": "Bad", "issuer": "x",
               "collateral": {"portfolio_size": 0, "diversity_score": 10, "ccc_bucket": 0.05},
               "liabilities": [{"tranche_id": "t1", "name": "AAA", "seniority": 1}]}
        result = portfolio_analytics_workflow([bad], actor="test")
        assert result["deals"][0]["error"] is not None


# ---------------------------------------------------------------------------
# Aggregate
# ---------------------------------------------------------------------------

class TestAggregate:

    def test_aggregate_is_dict(self, portfolio_two):
        assert isinstance(portfolio_two["aggregate"], dict)

    def test_aggregate_deal_count(self, portfolio_two):
        assert portfolio_two["aggregate"]["deal_count"] == 2

    def test_aggregate_total_portfolio_size(self, portfolio_two, us_bsl, eu_bsl):
        expected = (
            us_bsl["collateral"]["portfolio_size"]
            + eu_bsl["collateral"]["portfolio_size"]
        )
        assert portfolio_two["aggregate"]["total_portfolio_size"] == pytest.approx(expected)

    def test_aggregate_has_avg_equity_irr(self, portfolio_two):
        assert "avg_equity_irr" in portfolio_two["aggregate"]

    def test_avg_irr_between_min_and_max(self, portfolio_two):
        agg = portfolio_two["aggregate"]
        assert agg["min_equity_irr"] <= agg["avg_equity_irr"] <= agg["max_equity_irr"]

    def test_aggregate_has_avg_oc_cushion(self, portfolio_two):
        assert "avg_oc_cushion_aaa" in portfolio_two["aggregate"]

    def test_empty_deal_list_returns_error(self):
        result = portfolio_analytics_workflow([], actor="test")
        assert result["error"] is not None
        assert result["deal_count"] == 0


# ---------------------------------------------------------------------------
# Rankings
# ---------------------------------------------------------------------------

class TestRankings:

    def test_rankings_is_dict(self, portfolio_two):
        assert isinstance(portfolio_two["rankings"], dict)

    def test_equity_irr_ranking_present(self, portfolio_two):
        assert "equity_irr" in portfolio_two["rankings"]

    def test_ranking_entries_have_rank_field(self, portfolio_two):
        for entry in portfolio_two["rankings"]["equity_irr"]:
            assert "rank" in entry

    def test_rank_1_is_highest_irr(self, portfolio_two):
        entries = portfolio_two["rankings"]["equity_irr"]
        rank1 = next(e for e in entries if e["rank"] == 1)
        others = [e for e in entries if e["rank"] != 1]
        for o in others:
            assert rank1["value"] >= o["value"]

    def test_oc_cushion_ranking_present(self, portfolio_two):
        assert "oc_cushion_aaa" in portfolio_two["rankings"]

    def test_wac_ranking_lower_is_better(self, portfolio_two):
        # WAC not in _HIGHER_IS_BETTER, so rank 1 has lowest WAC
        entries = portfolio_two["rankings"].get("wac", [])
        if len(entries) >= 2:
            rank1 = next(e for e in entries if e["rank"] == 1)
            rank2 = next(e for e in entries if e["rank"] == 2)
            assert rank1["value"] <= rank2["value"]

    def test_custom_metrics_respected(self, us_bsl, eu_bsl):
        result = portfolio_analytics_workflow(
            [us_bsl, eu_bsl],
            metrics=["equity_irr"],
            actor="test",
        )
        # Only equity_irr in rankings
        assert "equity_irr" in result["rankings"]
        assert "oc_cushion_aaa" not in result["rankings"]

    def test_single_deal_has_rank_1(self, us_bsl):
        result = portfolio_analytics_workflow([us_bsl], actor="test")
        irr_entries = result["rankings"].get("equity_irr", [])
        assert len(irr_entries) == 1
        assert irr_entries[0]["rank"] == 1


# ---------------------------------------------------------------------------
# Concentration
# ---------------------------------------------------------------------------

class TestConcentration:

    def test_concentration_is_dict(self, portfolio_two):
        assert isinstance(portfolio_two["concentration"], dict)

    def test_concentration_has_by_region(self, portfolio_two):
        assert "by_region" in portfolio_two["concentration"]

    def test_concentration_has_by_asset_class(self, portfolio_two):
        assert "by_asset_class" in portfolio_two["concentration"]

    def test_concentration_has_by_size_bucket(self, portfolio_two):
        assert "by_size_bucket" in portfolio_two["concentration"]

    def test_region_totals_match_deal_count(self, portfolio_two):
        total = sum(portfolio_two["concentration"]["by_region"].values())
        assert total == portfolio_two["deal_count"]

    def test_asset_class_totals_match(self, portfolio_two):
        total = sum(portfolio_two["concentration"]["by_asset_class"].values())
        assert total == portfolio_two["deal_count"]

    def test_us_bsl_region_us(self, us_bsl):
        result = portfolio_analytics_workflow([us_bsl], actor="test")
        assert result["concentration"]["by_region"].get("US", 0) == 1

    def test_three_deal_region_concentration(self, portfolio_three, us_bsl, eu_bsl):
        by_region = portfolio_three["concentration"]["by_region"]
        # US BSL + US MM = 2 US, EU BSL = 1 EU
        assert by_region.get("US", 0) >= 1
        assert by_region.get("EU", 0) >= 1


# ---------------------------------------------------------------------------
# Portfolio report
# ---------------------------------------------------------------------------

class TestPortfolioReport:

    def test_report_is_string(self, portfolio_two):
        assert isinstance(portfolio_two["portfolio_report"], str)

    def test_report_non_empty(self, portfolio_two):
        assert len(portfolio_two["portfolio_report"]) > 100

    def test_report_contains_demo_tag(self, portfolio_two):
        assert "[demo]" in portfolio_two["portfolio_report"]

    def test_report_contains_portfolio_id(self, portfolio_two):
        assert portfolio_two["portfolio_id"] in portfolio_two["portfolio_report"]

    def test_report_contains_deal_names(self, portfolio_two, us_bsl):
        assert us_bsl["name"] in portfolio_two["portfolio_report"]


# ---------------------------------------------------------------------------
# Audit events
# ---------------------------------------------------------------------------

class TestAuditEvents:

    def test_audit_events_emitted(self, portfolio_two):
        # At least: per-deal scenario events + portfolio_analytics.completed
        assert len(portfolio_two["audit_events"]) >= 3

    def test_audit_events_are_strings(self, portfolio_two):
        for ev in portfolio_two["audit_events"]:
            assert isinstance(ev, str)

    def test_more_events_with_more_deals(self, us_bsl, eu_bsl, us_mm):
        small = portfolio_analytics_workflow([us_bsl], actor="test")
        large = portfolio_analytics_workflow([us_bsl, eu_bsl, us_mm], actor="test")
        assert len(large["audit_events"]) > len(small["audit_events"])
