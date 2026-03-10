"""
tests/test_full_pipeline_workflow.py

Tests for app/workflows/full_pipeline_workflow.py

Covers:
  - Return structure: all expected keys
  - All four stages run by default
  - Analytics stage always runs (required)
  - Optional stages can be disabled
  - Invalid deal aborts pipeline early
  - Pipeline summary is a non-empty [demo]-tagged string
  - Audit events emitted at start and end
  - pipeline_id has correct prefix
  - Stages dict populated correctly per flags
"""

import json
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.workflows.full_pipeline_workflow import full_pipeline_workflow


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
def pipeline_result(valid_deal):
    """Full pipeline, optimizer uses coarse step for speed."""
    return full_pipeline_workflow(
        valid_deal,
        run_sensitivity=False,
        run_optimizer=True,
        run_benchmark=True,
        run_draft=True,
        optimizer_kwargs={"aaa_min": 0.60, "aaa_max": 0.65, "aaa_step": 0.025},
    )


# ---------------------------------------------------------------------------
# Return structure
# ---------------------------------------------------------------------------

class TestReturnStructure:

    EXPECTED_KEYS = {
        "pipeline_id", "deal_id", "run_at", "is_mock",
        "stages", "pipeline_summary", "audit_events",
    }

    def test_returns_dict(self, pipeline_result):
        assert isinstance(pipeline_result, dict)

    def test_all_expected_keys_present(self, pipeline_result):
        assert self.EXPECTED_KEYS <= set(pipeline_result.keys())

    def test_pipeline_id_starts_with_prefix(self, pipeline_result):
        assert pipeline_result["pipeline_id"].startswith("pipeline-")

    def test_deal_id_matches(self, valid_deal, pipeline_result):
        assert pipeline_result["deal_id"] == valid_deal["deal_id"]

    def test_is_mock_true(self, pipeline_result):
        assert pipeline_result["is_mock"] is True

    def test_no_error_on_valid_deal(self, pipeline_result):
        assert pipeline_result.get("error") is None

    def test_stages_dict_has_four_keys(self, pipeline_result):
        assert set(pipeline_result["stages"].keys()) == {"analytics", "optimizer", "benchmark", "draft"}


# ---------------------------------------------------------------------------
# Stage outputs
# ---------------------------------------------------------------------------

class TestStageOutputs:

    def test_analytics_stage_populated(self, pipeline_result):
        assert pipeline_result["stages"]["analytics"] is not None

    def test_analytics_has_key_metrics(self, pipeline_result):
        assert "key_metrics" in pipeline_result["stages"]["analytics"]

    def test_analytics_base_irr_positive(self, pipeline_result):
        irr = pipeline_result["stages"]["analytics"]["key_metrics"].get("base_equity_irr")
        assert irr is not None
        assert irr > 0

    def test_optimizer_stage_populated(self, pipeline_result):
        assert pipeline_result["stages"]["optimizer"] is not None

    def test_optimizer_has_optimal_point(self, pipeline_result):
        opt = pipeline_result["stages"]["optimizer"].get("optimal")
        assert opt is not None

    def test_benchmark_stage_populated(self, pipeline_result):
        assert pipeline_result["stages"]["benchmark"] is not None

    def test_benchmark_has_overall_position(self, pipeline_result):
        bench = pipeline_result["stages"]["benchmark"]
        assert "overall_position" in bench

    def test_draft_stage_populated(self, pipeline_result):
        assert pipeline_result["stages"]["draft"] is not None

    def test_draft_has_draft_markdown(self, pipeline_result):
        draft_stage = pipeline_result["stages"]["draft"]
        assert "draft_markdown" in draft_stage


# ---------------------------------------------------------------------------
# Optional stages
# ---------------------------------------------------------------------------

class TestOptionalStages:

    def test_optimizer_skipped_when_disabled(self, valid_deal):
        result = full_pipeline_workflow(
            valid_deal, run_optimizer=False, run_benchmark=False,
            run_draft=False,
        )
        assert result["stages"]["optimizer"] is None

    def test_benchmark_skipped_when_disabled(self, valid_deal):
        result = full_pipeline_workflow(
            valid_deal, run_optimizer=False, run_benchmark=False, run_draft=False,
        )
        assert result["stages"]["benchmark"] is None

    def test_draft_skipped_when_disabled(self, valid_deal):
        result = full_pipeline_workflow(
            valid_deal, run_optimizer=False, run_benchmark=False, run_draft=False,
        )
        assert result["stages"]["draft"] is None

    def test_analytics_only_run(self, valid_deal):
        result = full_pipeline_workflow(
            valid_deal, run_optimizer=False, run_benchmark=False, run_draft=False,
        )
        assert result["stages"]["analytics"] is not None
        assert result["stages"]["optimizer"] is None
        assert result["stages"]["benchmark"] is None
        assert result["stages"]["draft"] is None

    def test_optimizer_kwargs_forwarded(self, valid_deal):
        result = full_pipeline_workflow(
            valid_deal,
            run_optimizer=True, run_benchmark=False, run_draft=False,
            optimizer_kwargs={"aaa_min": 0.62, "aaa_max": 0.65, "aaa_step": 0.015},
        )
        opt = result["stages"]["optimizer"]
        assert opt is not None
        # With aaa_min=0.62, aaa_max=0.65, step=0.015 → 3 candidates
        assert len(opt.get("feasibility_table", [])) == 3


# ---------------------------------------------------------------------------
# Guard conditions
# ---------------------------------------------------------------------------

class TestGuardConditions:

    def test_invalid_deal_returns_error(self):
        bad_deal = {"deal_id": "", "name": "x", "issuer": "y",
                    "collateral": {"portfolio_size": 100_000_000, "diversity_score": 45, "ccc_bucket": 0.05},
                    "liabilities": [{"tranche_id": "t1", "name": "AAA", "seniority": 1, "size_pct": 0.61}]}
        result = full_pipeline_workflow(bad_deal)
        assert result["error"] is not None

    def test_invalid_deal_analytics_has_error(self):
        bad_deal = {"deal_id": "", "name": "x", "issuer": "y",
                    "collateral": {"portfolio_size": 100_000_000, "diversity_score": 45, "ccc_bucket": 0.05},
                    "liabilities": [{"tranche_id": "t1", "name": "AAA", "seniority": 1, "size_pct": 0.61}]}
        result = full_pipeline_workflow(bad_deal)
        # Analytics stage should contain the error
        assert result["stages"]["analytics"].get("error") is not None

    def test_invalid_deal_downstream_stages_skipped(self):
        bad_deal = {"deal_id": "", "name": "x", "issuer": "y",
                    "collateral": {"portfolio_size": 100_000_000, "diversity_score": 45, "ccc_bucket": 0.05},
                    "liabilities": [{"tranche_id": "t1", "name": "AAA", "seniority": 1, "size_pct": 0.61}]}
        result = full_pipeline_workflow(bad_deal)
        assert result["stages"]["optimizer"] is None
        assert result["stages"]["benchmark"] is None
        assert result["stages"]["draft"] is None


# ---------------------------------------------------------------------------
# Pipeline summary
# ---------------------------------------------------------------------------

class TestPipelineSummary:

    def test_summary_is_non_empty_string(self, pipeline_result):
        assert isinstance(pipeline_result["pipeline_summary"], str)
        assert len(pipeline_result["pipeline_summary"]) > 100

    def test_summary_tagged_demo(self, pipeline_result):
        assert "[demo]" in pipeline_result["pipeline_summary"].lower() or \
               "DEMO" in pipeline_result["pipeline_summary"]

    def test_summary_contains_analytics_section(self, pipeline_result):
        assert "ANALYTICS" in pipeline_result["pipeline_summary"]

    def test_summary_contains_optimizer_section(self, pipeline_result):
        assert "OPTIMIZER" in pipeline_result["pipeline_summary"]

    def test_summary_contains_benchmark_section(self, pipeline_result):
        assert "BENCHMARK" in pipeline_result["pipeline_summary"]

    def test_summary_contains_deal_id(self, valid_deal, pipeline_result):
        assert valid_deal["deal_id"] in pipeline_result["pipeline_summary"]

    def test_summary_contains_pipeline_id(self, pipeline_result):
        assert pipeline_result["pipeline_id"] in pipeline_result["pipeline_summary"]


# ---------------------------------------------------------------------------
# Audit events
# ---------------------------------------------------------------------------

class TestAuditEvents:

    def test_audit_events_emitted(self, pipeline_result):
        # At minimum: pipeline.started + analytics events + pipeline.completed
        assert len(pipeline_result["audit_events"]) >= 3

    def test_audit_events_are_strings(self, pipeline_result):
        for ev in pipeline_result["audit_events"]:
            assert isinstance(ev, str)

    def test_more_events_with_all_stages(self, valid_deal):
        full = full_pipeline_workflow(
            valid_deal,
            optimizer_kwargs={"aaa_min": 0.62, "aaa_max": 0.64, "aaa_step": 0.02},
        )
        minimal = full_pipeline_workflow(
            valid_deal,
            run_optimizer=False, run_benchmark=False, run_draft=False,
        )
        assert len(full["audit_events"]) > len(minimal["audit_events"])
