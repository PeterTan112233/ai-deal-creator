"""
tests/test_portfolio_stress_workflow.py

Tests for app/workflows/portfolio_stress_workflow.py

Covers:
  - Return structure
  - Per-deal base IRR, worst-case IRR, drawdown computed correctly
  - Risk ranking (most drawdown = rank 1)
  - Most sensitive template identified
  - Template filtering: scenario_type, tag, explicit IDs
  - Single deal works
  - Empty deal list returns error
  - Invalid deal handled gracefully
  - Audit events emitted
  - Portfolio stress report generated
"""

import json
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from app.workflows.portfolio_stress_workflow import portfolio_stress_workflow


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
def eu_clo():
    return _load_deal("EU CLO")


@pytest.fixture(scope="module")
def us_mm():
    return _load_deal("US Middle Market")


@pytest.fixture(scope="module")
def stress_two(us_bsl, eu_clo):
    """Two-deal stress test using historical templates only."""
    return portfolio_stress_workflow(
        [us_bsl, eu_clo],
        tag="historical",
        actor="test",
    )


@pytest.fixture(scope="module")
def stress_explicit(us_bsl, eu_clo):
    """Two-deal stress test with explicit template IDs."""
    return portfolio_stress_workflow(
        [us_bsl, eu_clo],
        template_ids=["base", "stress", "deep-stress"],
        actor="test",
    )


# ---------------------------------------------------------------------------
# Return structure
# ---------------------------------------------------------------------------

class TestReturnStructure:

    def test_returns_dict(self, stress_two):
        assert isinstance(stress_two, dict)

    def test_has_required_keys(self, stress_two):
        for key in ("stress_id", "run_at", "deal_count", "template_count",
                    "deals", "risk_ranking", "most_sensitive_template",
                    "portfolio_report", "audit_events", "is_mock", "error"):
            assert key in stress_two

    def test_no_error(self, stress_two):
        assert stress_two["error"] is None

    def test_is_mock(self, stress_two):
        assert stress_two["is_mock"] is True

    def test_stress_id_prefixed(self, stress_two):
        assert stress_two["stress_id"].startswith("stress-")

    def test_deal_count(self, stress_two, us_bsl, eu_clo):
        assert stress_two["deal_count"] == 2

    def test_template_count_positive(self, stress_two):
        assert stress_two["template_count"] >= 2


# ---------------------------------------------------------------------------
# Per-deal results
# ---------------------------------------------------------------------------

class TestPerDealResults:

    def test_deals_list_length(self, stress_two):
        assert len(stress_two["deals"]) == 2

    def test_each_deal_has_required_fields(self, stress_two):
        for d in stress_two["deals"]:
            for field in ("deal_id", "name", "base_irr", "worst_case_irr",
                          "irr_drawdown", "template_results", "status", "error"):
                assert field in d

    def test_all_deals_ok(self, stress_two):
        for d in stress_two["deals"]:
            assert d["status"] == "ok"

    def test_base_irr_populated(self, stress_two):
        for d in stress_two["deals"]:
            assert d["base_irr"] is not None

    def test_worst_case_irr_populated(self, stress_two):
        for d in stress_two["deals"]:
            assert d["worst_case_irr"] is not None

    def test_irr_drawdown_positive(self, stress_two):
        # Stress scenarios should always lower IRR vs base
        for d in stress_two["deals"]:
            assert d["irr_drawdown"] >= 0

    def test_worst_case_irr_lte_base_irr(self, stress_two):
        for d in stress_two["deals"]:
            assert d["worst_case_irr"] <= d["base_irr"]

    def test_drawdown_equals_base_minus_worst(self, stress_two):
        for d in stress_two["deals"]:
            expected = d["base_irr"] - d["worst_case_irr"]
            assert d["irr_drawdown"] == pytest.approx(expected, abs=1e-5)

    def test_template_results_populated(self, stress_two):
        for d in stress_two["deals"]:
            assert len(d["template_results"]) >= 2

    def test_each_template_result_structure(self, stress_two):
        for d in stress_two["deals"]:
            for tr in d["template_results"]:
                for field in ("template_id", "template_name", "scenario_type",
                              "outputs", "status"):
                    assert field in tr

    def test_all_template_results_complete(self, stress_two):
        for d in stress_two["deals"]:
            for tr in d["template_results"]:
                assert tr["status"] == "complete"

    def test_explicit_templates_respected(self, stress_explicit):
        for d in stress_explicit["deals"]:
            ids = {tr["template_id"] for tr in d["template_results"]}
            assert ids == {"base", "stress", "deep-stress"}


# ---------------------------------------------------------------------------
# Risk ranking
# ---------------------------------------------------------------------------

class TestRiskRanking:

    def test_risk_ranking_is_list(self, stress_two):
        assert isinstance(stress_two["risk_ranking"], list)

    def test_risk_ranking_length_matches_ok_deals(self, stress_two):
        ok_count = sum(1 for d in stress_two["deals"] if d["status"] == "ok")
        assert len(stress_two["risk_ranking"]) == ok_count

    def test_rank_1_has_highest_drawdown(self, stress_two):
        ranking = stress_two["risk_ranking"]
        if len(ranking) >= 2:
            assert ranking[0]["irr_drawdown"] >= ranking[1]["irr_drawdown"]

    def test_ranking_entries_have_rank(self, stress_two):
        for entry in stress_two["risk_ranking"]:
            assert "rank" in entry
            assert entry["rank"] >= 1

    def test_ranking_entries_have_drawdown(self, stress_two):
        for entry in stress_two["risk_ranking"]:
            assert "irr_drawdown" in entry
            assert entry["irr_drawdown"] is not None

    def test_three_deals_ranked(self, us_bsl, eu_clo, us_mm):
        result = portfolio_stress_workflow(
            [us_bsl, eu_clo, us_mm],
            template_ids=["stress", "deep-stress"],
            actor="test",
        )
        assert len(result["risk_ranking"]) == 3
        ranks = [e["rank"] for e in result["risk_ranking"]]
        assert sorted(ranks) == [1, 2, 3]


# ---------------------------------------------------------------------------
# Most sensitive template
# ---------------------------------------------------------------------------

class TestMostSensitiveTemplate:

    def test_most_sensitive_is_string(self, stress_two):
        assert isinstance(stress_two["most_sensitive_template"], str)

    def test_most_sensitive_is_a_template_id(self, stress_two):
        template_ids = {
            tr["template_id"]
            for d in stress_two["deals"]
            for tr in d["template_results"]
        }
        assert stress_two["most_sensitive_template"] in template_ids

    def test_single_template_is_most_sensitive(self, us_bsl, eu_clo):
        result = portfolio_stress_workflow(
            [us_bsl, eu_clo],
            template_ids=["gfc-2008"],
            actor="test",
        )
        assert result["most_sensitive_template"] == "gfc-2008"


# ---------------------------------------------------------------------------
# Template filtering
# ---------------------------------------------------------------------------

class TestTemplateFiltering:

    def test_stress_type_filter(self, us_bsl):
        result = portfolio_stress_workflow([us_bsl], scenario_type="stress", actor="test")
        assert result["error"] is None
        for d in result["deals"]:
            for tr in d["template_results"]:
                assert tr["scenario_type"] == "stress"

    def test_historical_tag_filter(self, us_bsl):
        result = portfolio_stress_workflow([us_bsl], tag="historical", actor="test")
        ids = {tr["template_id"] for d in result["deals"] for tr in d["template_results"]}
        assert "gfc-2008" in ids
        assert "covid-2020" in ids

    def test_unknown_filter_returns_error(self, us_bsl):
        result = portfolio_stress_workflow([us_bsl], scenario_type="nonexistent", actor="test")
        assert result["error"] is not None

    def test_explicit_ids_respected(self, us_bsl):
        result = portfolio_stress_workflow(
            [us_bsl], template_ids=["base", "stress"], actor="test"
        )
        ids = {tr["template_id"] for d in result["deals"] for tr in d["template_results"]}
        assert ids == {"base", "stress"}


# ---------------------------------------------------------------------------
# Guard conditions
# ---------------------------------------------------------------------------

class TestGuardConditions:

    def test_empty_deal_list_returns_error(self):
        result = portfolio_stress_workflow([])
        assert result["error"] is not None
        assert result["deal_count"] == 0

    def test_invalid_deal_handled(self, us_bsl):
        bad = {"deal_id": "bad", "name": "x", "issuer": "y",
               "collateral": {"portfolio_size": 0, "diversity_score": 10, "ccc_bucket": 0.05},
               "liabilities": [{"tranche_id": "t1", "name": "AAA", "seniority": 1}]}
        result = portfolio_stress_workflow(
            [us_bsl, bad], template_ids=["stress"], actor="test"
        )
        assert result["error"] is None  # no top-level error
        statuses = {d["deal_id"]: d["status"] for d in result["deals"]}
        assert statuses[us_bsl["deal_id"]] == "ok"
        assert statuses["bad"] == "error"

    def test_single_deal_works(self, us_bsl):
        result = portfolio_stress_workflow(
            [us_bsl], template_ids=["stress"], actor="test"
        )
        assert result["deal_count"] == 1
        assert result["deals"][0]["status"] == "ok"


# ---------------------------------------------------------------------------
# Portfolio stress report
# ---------------------------------------------------------------------------

class TestPortfolioReport:

    def test_report_is_string(self, stress_two):
        assert isinstance(stress_two["portfolio_report"], str)

    def test_report_non_empty(self, stress_two):
        assert len(stress_two["portfolio_report"]) > 100

    def test_report_contains_demo_tag(self, stress_two):
        assert "[demo]" in stress_two["portfolio_report"]

    def test_report_contains_stress_id(self, stress_two):
        assert stress_two["stress_id"] in stress_two["portfolio_report"]


# ---------------------------------------------------------------------------
# Audit events
# ---------------------------------------------------------------------------

class TestAuditEvents:

    def test_audit_events_emitted(self, stress_two):
        assert len(stress_two["audit_events"]) >= 3

    def test_audit_events_are_strings(self, stress_two):
        for ev in stress_two["audit_events"]:
            assert isinstance(ev, str)

    def test_more_events_for_more_deals(self, us_bsl, eu_clo):
        small = portfolio_stress_workflow([us_bsl], template_ids=["stress"], actor="test")
        large = portfolio_stress_workflow(
            [us_bsl, eu_clo], template_ids=["stress"], actor="test"
        )
        assert len(large["audit_events"]) > len(small["audit_events"])
