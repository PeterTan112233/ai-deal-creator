"""
tests/test_stress_matrix_workflow.py

Tests for app/workflows/stress_matrix_workflow.py

Covers:
  - Return structure (all required keys)
  - Cell grid shape: deal_count × template_count
  - Each cell has required fields and valid status
  - Deal summaries: one per deal, min ≤ max, worst/best template valid
  - Template summaries: one per template, avg between min and max
  - Template filtering (scenario_type, tag, explicit IDs)
  - Guard conditions: empty input, all-invalid deals
  - Matrix report format ([demo] tag, matrix_id in header)
  - Audit events
"""

import json
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from app.workflows.stress_matrix_workflow import stress_matrix_workflow


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


@pytest.fixture(scope="module")
def two_deals():
    return [_us_bsl(), _eu_clo()]


# Fixture: 2 deals, 2 explicit templates (fast)
@pytest.fixture(scope="module")
def matrix_2x2(two_deals):
    return stress_matrix_workflow(
        two_deals,
        template_ids=["base", "stress"],
        actor="test",
    )


# Fixture: 1 deal, 1 template (minimal)
@pytest.fixture(scope="module")
def matrix_1x1():
    return stress_matrix_workflow(
        [_us_bsl()],
        template_ids=["stress"],
        actor="test",
    )


# ---------------------------------------------------------------------------
# Return structure
# ---------------------------------------------------------------------------

class TestReturnStructure:

    def test_returns_dict(self, matrix_2x2):
        assert isinstance(matrix_2x2, dict)

    def test_has_required_keys(self, matrix_2x2):
        for key in (
            "matrix_id", "run_at", "deal_count", "template_count",
            "cells", "deal_summaries", "template_summaries",
            "matrix_report", "audit_events", "is_mock", "error",
        ):
            assert key in matrix_2x2, f"Missing key: {key}"

    def test_matrix_id_prefixed(self, matrix_2x2):
        assert matrix_2x2["matrix_id"].startswith("matrix-")

    def test_no_error(self, matrix_2x2):
        assert matrix_2x2["error"] is None

    def test_is_mock_true(self, matrix_2x2):
        assert matrix_2x2["is_mock"] is True

    def test_deal_count(self, matrix_2x2, two_deals):
        assert matrix_2x2["deal_count"] == len(two_deals)

    def test_template_count(self, matrix_2x2):
        assert matrix_2x2["template_count"] == 2  # "base" + "stress"

    def test_run_at_is_iso(self, matrix_2x2):
        assert "T" in matrix_2x2["run_at"]


# ---------------------------------------------------------------------------
# Cells
# ---------------------------------------------------------------------------

class TestCells:

    def test_cells_is_list(self, matrix_2x2):
        assert isinstance(matrix_2x2["cells"], list)

    def test_cell_count_deals_times_templates(self, matrix_2x2):
        assert len(matrix_2x2["cells"]) == matrix_2x2["deal_count"] * matrix_2x2["template_count"]

    def test_each_cell_has_required_fields(self, matrix_2x2):
        for cell in matrix_2x2["cells"]:
            for key in ("deal_id", "deal_name", "template_id", "template_name",
                        "equity_irr", "oc_cushion", "status", "error"):
                assert key in cell, f"Cell missing key: {key}"

    def test_all_cells_complete_on_valid_deals(self, matrix_2x2):
        for cell in matrix_2x2["cells"]:
            assert cell["status"] == "complete", (
                f"Expected 'complete', got '{cell['status']}' for "
                f"deal={cell['deal_id']} template={cell['template_id']}"
            )

    def test_equity_irr_is_float(self, matrix_2x2):
        for cell in matrix_2x2["cells"]:
            if cell["status"] == "complete":
                assert isinstance(cell["equity_irr"], float)

    def test_oc_cushion_is_float(self, matrix_2x2):
        for cell in matrix_2x2["cells"]:
            if cell["status"] == "complete":
                assert isinstance(cell["oc_cushion"], float)

    def test_cells_cover_all_deals(self, matrix_2x2, two_deals):
        cell_deal_ids = {c["deal_id"] for c in matrix_2x2["cells"]}
        input_deal_ids = {d["deal_id"] for d in two_deals}
        assert input_deal_ids == cell_deal_ids

    def test_cells_cover_all_templates(self, matrix_2x2):
        cell_tids = {c["template_id"] for c in matrix_2x2["cells"]}
        assert "base" in cell_tids
        assert "stress" in cell_tids

    def test_1x1_cell_count(self, matrix_1x1):
        assert len(matrix_1x1["cells"]) == 1

    def test_explicit_templates_respected(self, two_deals):
        result = stress_matrix_workflow(
            two_deals,
            template_ids=["base"],
            actor="test",
        )
        assert result["template_count"] == 1
        assert len(result["cells"]) == 2  # 2 deals × 1 template


# ---------------------------------------------------------------------------
# Deal summaries
# ---------------------------------------------------------------------------

class TestDealSummaries:

    def test_deal_summaries_is_list(self, matrix_2x2):
        assert isinstance(matrix_2x2["deal_summaries"], list)

    def test_one_summary_per_deal(self, matrix_2x2, two_deals):
        assert len(matrix_2x2["deal_summaries"]) == len(two_deals)

    def test_each_summary_has_required_fields(self, matrix_2x2):
        for ds in matrix_2x2["deal_summaries"]:
            for key in ("deal_id", "deal_name", "min_irr", "max_irr", "irr_range",
                        "min_oc", "max_oc", "worst_template", "best_template",
                        "cell_count", "status", "error"):
                assert key in ds, f"Deal summary missing key: {key}"

    def test_min_irr_le_max_irr(self, matrix_2x2):
        for ds in matrix_2x2["deal_summaries"]:
            if ds["min_irr"] is not None and ds["max_irr"] is not None:
                assert ds["min_irr"] <= ds["max_irr"]

    def test_irr_range_equals_max_minus_min(self, matrix_2x2):
        for ds in matrix_2x2["deal_summaries"]:
            if ds["irr_range"] is not None:
                expected = round(ds["max_irr"] - ds["min_irr"], 6)
                assert abs(ds["irr_range"] - expected) < 1e-9

    def test_worst_template_is_valid(self, matrix_2x2):
        valid_tids = {c["template_id"] for c in matrix_2x2["cells"]}
        for ds in matrix_2x2["deal_summaries"]:
            if ds["worst_template"] is not None:
                assert ds["worst_template"] in valid_tids

    def test_best_template_is_valid(self, matrix_2x2):
        valid_tids = {c["template_id"] for c in matrix_2x2["cells"]}
        for ds in matrix_2x2["deal_summaries"]:
            if ds["best_template"] is not None:
                assert ds["best_template"] in valid_tids

    def test_cell_count_ge_1(self, matrix_2x2):
        for ds in matrix_2x2["deal_summaries"]:
            if ds["status"] == "ok":
                assert ds["cell_count"] >= 1

    def test_invalid_deal_summary_status_is_error(self):
        bad_deal = {
            "deal_id": "invalid-001",
            "name": "Bad Deal",
            "issuer": "None",
            "collateral": {"portfolio_size": 0, "diversity_score": 10, "ccc_bucket": 0.05},
            "liabilities": [{"tranche_id": "t1", "name": "AAA", "seniority": 1}],
        }
        result = stress_matrix_workflow(
            [bad_deal],
            template_ids=["stress"],
            actor="test",
        )
        assert result["deal_summaries"][0]["status"] == "error"
        assert result["deal_summaries"][0]["min_irr"] is None


# ---------------------------------------------------------------------------
# Template summaries
# ---------------------------------------------------------------------------

class TestTemplateSummaries:

    def test_template_summaries_is_list(self, matrix_2x2):
        assert isinstance(matrix_2x2["template_summaries"], list)

    def test_one_summary_per_template(self, matrix_2x2):
        assert len(matrix_2x2["template_summaries"]) == matrix_2x2["template_count"]

    def test_each_summary_has_required_fields(self, matrix_2x2):
        for ts in matrix_2x2["template_summaries"]:
            for key in ("template_id", "template_name", "avg_irr", "avg_oc",
                        "min_irr", "max_irr", "most_impacted_deal", "cell_count"):
                assert key in ts, f"Template summary missing key: {key}"

    def test_avg_irr_between_min_and_max(self, matrix_2x2):
        for ts in matrix_2x2["template_summaries"]:
            if ts["avg_irr"] is not None:
                assert ts["min_irr"] <= ts["avg_irr"] <= ts["max_irr"]

    def test_most_impacted_deal_is_valid_deal_id(self, matrix_2x2, two_deals):
        valid_ids = {d["deal_id"] for d in two_deals}
        for ts in matrix_2x2["template_summaries"]:
            if ts["most_impacted_deal"] is not None:
                assert ts["most_impacted_deal"] in valid_ids


# ---------------------------------------------------------------------------
# Template filtering
# ---------------------------------------------------------------------------

class TestTemplateFiltering:

    def test_scenario_type_filter(self):
        result = stress_matrix_workflow(
            [_us_bsl()],
            scenario_type="stress",
            actor="test",
        )
        assert result["error"] is None
        for c in result["cells"]:
            assert c["template_id"] != "base"  # base is type "base", not "stress"

    def test_tag_filter_historical(self):
        result = stress_matrix_workflow(
            [_us_bsl()],
            tag="historical",
            actor="test",
        )
        assert result["error"] is None
        assert result["template_count"] >= 1

    def test_no_matching_templates_returns_error(self):
        result = stress_matrix_workflow(
            [_us_bsl()],
            scenario_type="nonexistent-type",
            actor="test",
        )
        assert result["error"] is not None
        assert result["template_count"] == 0

    def test_unknown_template_id_silently_ignored(self):
        """Unresolvable template IDs are skipped without raising."""
        result = stress_matrix_workflow(
            [_us_bsl()],
            template_ids=["stress", "no-such-template-xyz"],
            actor="test",
        )
        # Only "stress" is found; "no-such-template-xyz" silently dropped
        assert result["template_count"] == 1
        assert result["error"] is None


# ---------------------------------------------------------------------------
# Guard conditions
# ---------------------------------------------------------------------------

class TestGuardConditions:

    def test_empty_deal_list_returns_error(self):
        result = stress_matrix_workflow([], actor="test")
        assert result["error"] is not None
        assert result["deal_count"] == 0

    def test_empty_deal_list_has_matrix_id(self):
        result = stress_matrix_workflow([], actor="test")
        assert result["matrix_id"].startswith("matrix-")

    def test_all_invalid_deals_no_top_level_error(self):
        """Invalid deals produce skipped cells; the workflow itself succeeds."""
        bad = {
            "deal_id": "bad-1", "name": "Bad", "issuer": "X",
            "collateral": {"portfolio_size": 0, "diversity_score": 10, "ccc_bucket": 0.05},
            "liabilities": [{"tranche_id": "t1", "name": "AAA", "seniority": 1}],
        }
        result = stress_matrix_workflow([bad], template_ids=["stress"], actor="test")
        assert result["error"] is None  # top-level ok
        assert all(c["status"] == "skipped" for c in result["cells"])


# ---------------------------------------------------------------------------
# Matrix report
# ---------------------------------------------------------------------------

class TestMatrixReport:

    def test_report_is_string(self, matrix_2x2):
        assert isinstance(matrix_2x2["matrix_report"], str)

    def test_report_non_empty(self, matrix_2x2):
        assert len(matrix_2x2["matrix_report"]) > 200

    def test_report_contains_demo_tag(self, matrix_2x2):
        assert "[demo]" in matrix_2x2["matrix_report"]

    def test_report_contains_matrix_id(self, matrix_2x2):
        assert matrix_2x2["matrix_id"] in matrix_2x2["matrix_report"]

    def test_report_contains_irr_matrix_header(self, matrix_2x2):
        assert "EQUITY IRR MATRIX" in matrix_2x2["matrix_report"]

    def test_report_contains_oc_matrix_header(self, matrix_2x2):
        assert "OC CUSHION MATRIX" in matrix_2x2["matrix_report"]

    def test_report_contains_deal_summary_section(self, matrix_2x2):
        assert "DEAL SUMMARY" in matrix_2x2["matrix_report"]

    def test_report_contains_template_summary_section(self, matrix_2x2):
        assert "TEMPLATE SUMMARY" in matrix_2x2["matrix_report"]


# ---------------------------------------------------------------------------
# Audit events
# ---------------------------------------------------------------------------

class TestAuditEvents:

    def test_audit_events_is_list(self, matrix_2x2):
        assert isinstance(matrix_2x2["audit_events"], list)

    def test_at_least_one_event(self, matrix_2x2):
        assert len(matrix_2x2["audit_events"]) >= 1

    def test_audit_events_are_strings(self, matrix_2x2):
        for ev in matrix_2x2["audit_events"]:
            assert isinstance(ev, str)

    def test_different_runs_different_matrix_ids(self):
        deal = [_us_bsl()]
        r1 = stress_matrix_workflow(deal, template_ids=["stress"], actor="test")
        r2 = stress_matrix_workflow(deal, template_ids=["stress"], actor="test")
        assert r1["matrix_id"] != r2["matrix_id"]
