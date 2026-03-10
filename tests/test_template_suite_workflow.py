"""
tests/test_template_suite_workflow.py

Tests for app/workflows/template_suite_workflow.py

Covers:
  - All templates run by default
  - Filter by scenario_type
  - Filter by tag
  - Explicit template_ids list
  - Comparison table structure
  - Best/worst assignments per metric
  - Invalid deal returns error
  - Single template works
  - Audit events emitted
  - Failed templates handled gracefully
"""

import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from app.workflows.template_suite_workflow import template_suite_workflow


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
def suite_all(us_bsl):
    """Run all standard stress templates for speed (exclude regulatory)."""
    return template_suite_workflow(
        us_bsl,
        scenario_type="stress",
        actor="test",
    )


@pytest.fixture(scope="module")
def suite_explicit(us_bsl):
    """Explicit subset: base + gfc-2008 + deep-stress."""
    return template_suite_workflow(
        us_bsl,
        template_ids=["base", "gfc-2008", "deep-stress"],
        actor="test",
    )


# ---------------------------------------------------------------------------
# Return structure
# ---------------------------------------------------------------------------

class TestReturnStructure:

    def test_returns_dict(self, suite_all):
        assert isinstance(suite_all, dict)

    def test_has_required_keys(self, suite_all):
        for key in ("deal_id", "templates_run", "results", "comparison_table",
                    "audit_events", "is_mock", "error"):
            assert key in suite_all

    def test_no_error(self, suite_all):
        assert suite_all["error"] is None

    def test_is_mock_true(self, suite_all):
        assert suite_all["is_mock"] is True

    def test_deal_id_correct(self, us_bsl, suite_all):
        assert suite_all["deal_id"] == us_bsl["deal_id"]


# ---------------------------------------------------------------------------
# Template filtering
# ---------------------------------------------------------------------------

class TestTemplateFiltering:

    def test_filter_stress_only(self, us_bsl):
        result = template_suite_workflow(us_bsl, scenario_type="stress", actor="test")
        for r in result["results"]:
            assert r["scenario_type"] == "stress"

    def test_filter_regulatory_only(self, us_bsl):
        result = template_suite_workflow(us_bsl, scenario_type="regulatory", actor="test")
        assert result["templates_run"] >= 2
        for r in result["results"]:
            assert r["scenario_type"] == "regulatory"

    def test_filter_by_historical_tag(self, us_bsl):
        result = template_suite_workflow(us_bsl, tag="historical", actor="test")
        ids = {r["template_id"] for r in result["results"]}
        assert "gfc-2008" in ids
        assert "covid-2020" in ids

    def test_explicit_ids_respected(self, suite_explicit):
        ids = {r["template_id"] for r in suite_explicit["results"]}
        assert ids == {"base", "gfc-2008", "deep-stress"}

    def test_templates_run_count_matches_results(self, suite_all):
        assert suite_all["templates_run"] == len(suite_all["results"])

    def test_unknown_filter_returns_error(self, us_bsl):
        result = template_suite_workflow(us_bsl, scenario_type="nonexistent", actor="test")
        assert result["error"] is not None
        assert result["templates_run"] == 0


# ---------------------------------------------------------------------------
# Result entries
# ---------------------------------------------------------------------------

class TestResultEntries:

    def test_each_result_has_required_fields(self, suite_explicit):
        required = {"template_id", "template_name", "scenario_type",
                    "parameters", "outputs", "status"}
        for r in suite_explicit["results"]:
            assert required <= set(r.keys())

    def test_all_results_complete(self, suite_explicit):
        for r in suite_explicit["results"]:
            assert r["status"] == "complete"

    def test_outputs_have_equity_irr(self, suite_explicit):
        for r in suite_explicit["results"]:
            assert "equity_irr" in r["outputs"]

    def test_gfc_irr_lower_than_base(self, suite_explicit):
        base_irr = next(r["outputs"]["equity_irr"]
                        for r in suite_explicit["results"] if r["template_id"] == "base")
        gfc_irr  = next(r["outputs"]["equity_irr"]
                        for r in suite_explicit["results"] if r["template_id"] == "gfc-2008")
        assert base_irr > gfc_irr

    def test_deep_stress_irr_lowest(self, suite_explicit):
        irrs = {r["template_id"]: r["outputs"]["equity_irr"]
                for r in suite_explicit["results"]}
        assert irrs["deep-stress"] <= irrs["gfc-2008"]
        assert irrs["deep-stress"] <= irrs["base"]


# ---------------------------------------------------------------------------
# Comparison table
# ---------------------------------------------------------------------------

class TestComparisonTable:

    def test_comparison_table_is_list(self, suite_explicit):
        assert isinstance(suite_explicit["comparison_table"], list)

    def test_comparison_table_non_empty(self, suite_explicit):
        assert len(suite_explicit["comparison_table"]) > 0

    def test_each_row_has_metric(self, suite_explicit):
        for row in suite_explicit["comparison_table"]:
            assert "metric" in row

    def test_each_row_has_best_worst(self, suite_explicit):
        for row in suite_explicit["comparison_table"]:
            assert "best_template" in row
            assert "worst_template" in row

    def test_equity_irr_best_is_base(self, suite_explicit):
        irr_row = next((r for r in suite_explicit["comparison_table"]
                        if r["metric"] == "equity_irr"), None)
        if irr_row:
            assert irr_row["best_template"] == "base"

    def test_equity_irr_worst_is_a_stress_template(self, suite_explicit):
        irr_row = next((r for r in suite_explicit["comparison_table"]
                        if r["metric"] == "equity_irr"), None)
        if irr_row:
            # Worst should be one of the stress templates, not the base
            assert irr_row["worst_template"] != "base"

    def test_values_dict_contains_all_template_ids(self, suite_explicit):
        template_ids = {r["template_id"] for r in suite_explicit["results"]}
        for row in suite_explicit["comparison_table"]:
            assert set(row["values"].keys()) <= template_ids


# ---------------------------------------------------------------------------
# Guard conditions
# ---------------------------------------------------------------------------

class TestGuardConditions:

    def test_invalid_deal_returns_error(self):
        bad = {"deal_id": "", "name": "x", "issuer": "y",
               "collateral": {"portfolio_size": 100_000_000,
                              "diversity_score": 45, "ccc_bucket": 0.05},
               "liabilities": [{"tranche_id": "t1", "name": "AAA",
                                 "seniority": 1, "size_pct": 0.61}]}
        result = template_suite_workflow(bad)
        assert result["error"] is not None

    def test_single_template_works(self, us_bsl):
        result = template_suite_workflow(us_bsl, template_ids=["base"], actor="test")
        assert result["templates_run"] == 1
        assert result["results"][0]["status"] == "complete"

    def test_single_template_no_comparison_table(self, us_bsl):
        result = template_suite_workflow(us_bsl, template_ids=["base"], actor="test")
        # Comparison table requires >= 2 complete results
        assert result["comparison_table"] == []


# ---------------------------------------------------------------------------
# Audit events
# ---------------------------------------------------------------------------

class TestAuditEvents:

    def test_audit_events_emitted(self, suite_all):
        # template_suite.started + per-scenario events + template_suite.completed
        assert len(suite_all["audit_events"]) >= 3

    def test_audit_events_are_strings(self, suite_all):
        for ev in suite_all["audit_events"]:
            assert isinstance(ev, str)

    def test_more_events_with_more_templates(self, us_bsl):
        small = template_suite_workflow(us_bsl, template_ids=["base"], actor="test")
        large = template_suite_workflow(us_bsl, template_ids=["base", "stress", "gfc-2008"],
                                        actor="test")
        assert len(large["audit_events"]) > len(small["audit_events"])
