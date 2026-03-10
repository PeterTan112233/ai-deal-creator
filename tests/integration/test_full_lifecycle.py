"""
tests/integration/test_full_lifecycle.py

End-to-end lifecycle integration tests.

Each test exercises a realistic CLO workflow chain using the workflow
functions directly (no HTTP layer). Tests validate that the full pipeline
hangs together — correct data flows from one stage to the next, audit
trails are complete, and governance gates enforce approval before publish.

Stages tested:
  analytics → optimizer → benchmark → draft → approval → publish-check
"""

import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

import pytest

from app.workflows.deal_analytics_workflow import deal_analytics_workflow
from app.workflows.tranche_optimizer_workflow import tranche_optimizer_workflow
from app.workflows.benchmark_comparison_workflow import benchmark_comparison_workflow
from app.workflows.run_scenario_workflow import run_scenario_workflow
from app.workflows.generate_investor_summary_workflow import generate_investor_summary_workflow
from app.workflows.generate_ic_memo_workflow import generate_ic_memo_workflow
from app.workflows.publish_check_workflow import publish_check_workflow
from app.workflows.full_pipeline_workflow import full_pipeline_workflow
from app.services import approval_service


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def deal():
    with open("data/samples/sample_deal_inputs.json") as f:
        return json.load(f)["deals"][0]


@pytest.fixture(scope="module")
def analytics(deal):
    return deal_analytics_workflow(
        deal,
        run_sensitivity=False,
        actor="integration-test",
    )


@pytest.fixture(scope="module")
def base_scenario(deal):
    return run_scenario_workflow(
        deal,
        scenario_name="Baseline",
        scenario_type="base",
        actor="integration-test",
    )


@pytest.fixture(scope="module")
def investor_draft(deal, base_scenario):
    return generate_investor_summary_workflow(
        deal_input=deal,
        scenario_result=base_scenario.get("scenario_result", {}),
        scenario_request=base_scenario.get("scenario_request"),
        actor="integration-test",
    )


@pytest.fixture(scope="module")
def ic_memo(deal, base_scenario):
    return generate_ic_memo_workflow(
        deal_input=deal,
        scenario_result=base_scenario.get("scenario_result", {}),
        scenario_request=base_scenario.get("scenario_request"),
        actor="integration-test",
    )


@pytest.fixture(scope="module")
def pipeline(deal):
    return full_pipeline_workflow(
        deal,
        run_sensitivity=False,
        run_optimizer=True,
        run_benchmark=True,
        run_draft=True,
        optimizer_kwargs={"aaa_min": 0.60, "aaa_max": 0.64, "aaa_step": 0.02},
        actor="integration-test",
    )


# ---------------------------------------------------------------------------
# Stage 1: Analytics
# ---------------------------------------------------------------------------

class TestAnalyticsStage:

    def test_analytics_has_no_error(self, analytics):
        assert analytics.get("error") is None

    def test_analytics_runs_four_scenarios(self, analytics):
        results = analytics.get("scenario_suite", {}).get("results", [])
        assert len(results) == 4

    def test_scenario_names_correct(self, analytics):
        names = {r["scenario_name"] for r in analytics["scenario_suite"]["results"]}
        assert names == {"Base", "Mild Stress", "Stress", "Deep Stress"}

    def test_key_metrics_present(self, analytics):
        km = analytics.get("key_metrics", {})
        assert "base_equity_irr" in km
        assert "base_oc_cushion" in km

    def test_base_irr_positive(self, analytics):
        assert analytics["key_metrics"]["base_equity_irr"] > 0

    def test_analytics_audit_events_emitted(self, analytics):
        assert len(analytics.get("audit_events", [])) >= 2

    def test_analytics_report_contains_demo(self, analytics):
        report = analytics.get("analytics_report", "")
        assert "[demo]" in report.lower() or "DEMO" in report

    def test_stress_irr_lower_than_base(self, analytics):
        results = analytics["scenario_suite"]["results"]
        base = next(r for r in results if r["scenario_name"] == "Base")
        stress = next(r for r in results if r["scenario_name"] == "Stress")
        base_irr = base["outputs"].get("equity_irr", 0)
        stress_irr = stress["outputs"].get("equity_irr", 0)
        assert base_irr > stress_irr


# ---------------------------------------------------------------------------
# Stage 2: Optimizer
# ---------------------------------------------------------------------------

class TestOptimizerStage:

    @pytest.fixture(scope="class")
    def optimizer(self, deal):
        return tranche_optimizer_workflow(
            deal,
            aaa_min=0.58,
            aaa_max=0.68,
            aaa_step=0.02,
            actor="integration-test",
        )

    def test_optimizer_has_optimal(self, optimizer):
        assert optimizer.get("optimal") is not None

    def test_optimal_aaa_in_range(self, optimizer):
        aaa = optimizer["optimal"]["aaa_size_pct"]
        assert 0.58 <= aaa <= 0.68

    def test_feasibility_table_populated(self, optimizer):
        assert len(optimizer.get("feasibility_table", [])) >= 1

    def test_feasible_candidates_exist(self, optimizer):
        feasible = optimizer.get("frontier", [])
        assert len(feasible) >= 1

    def test_optimal_passes_oc_constraint(self, optimizer):
        opt = optimizer["optimal"]
        assert opt.get("oc_pass") is True

    def test_optimizer_audit_events_emitted(self, optimizer):
        assert len(optimizer.get("audit_events", [])) >= 1


# ---------------------------------------------------------------------------
# Stage 3: Benchmark
# ---------------------------------------------------------------------------

class TestBenchmarkStage:

    @pytest.fixture(scope="class")
    def base_outputs(self, analytics):
        results = analytics["scenario_suite"]["results"]
        base = next(r for r in results if r["scenario_name"] == "Base")
        return base["outputs"]

    @pytest.fixture(scope="class")
    def benchmark(self, deal, base_outputs):
        return benchmark_comparison_workflow(
            deal_input=deal,
            scenario_outputs=base_outputs,
            vintage=2024,
            region="US",
            actor="integration-test",
        )

    def test_benchmark_has_no_error(self, benchmark):
        assert benchmark.get("error") is None

    def test_overall_position_valid(self, benchmark):
        assert benchmark["overall_position"] in ("strong", "median", "weak", "mixed")

    def test_metric_scores_populated(self, benchmark):
        assert len(benchmark.get("metric_scores", [])) > 0

    def test_comparison_report_contains_demo(self, benchmark):
        assert "DEMO" in benchmark.get("comparison_report", "")

    def test_vintage_matches_request(self, benchmark):
        assert benchmark["vintage"] == 2024

    def test_region_matches_request(self, benchmark):
        assert benchmark["region"] == "US"


# ---------------------------------------------------------------------------
# Stage 4: Investor Summary Draft
# ---------------------------------------------------------------------------

class TestInvestorDraftStage:

    def test_draft_returned(self, investor_draft):
        assert investor_draft.get("draft") is not None

    def test_draft_not_approved_at_creation(self, investor_draft):
        assert investor_draft["draft"].get("approved") is False

    def test_draft_requires_approval(self, investor_draft):
        assert investor_draft.get("requires_approval") is True

    def test_draft_markdown_present(self, investor_draft):
        assert len(investor_draft.get("draft_markdown", "")) > 100

    def test_draft_id_present(self, investor_draft):
        assert investor_draft["draft"].get("draft_id") is not None

    def test_draft_audit_events_emitted(self, investor_draft):
        assert len(investor_draft.get("audit_events", [])) >= 1


# ---------------------------------------------------------------------------
# Stage 5: IC Memo
# ---------------------------------------------------------------------------

class TestIcMemoStage:

    def test_ic_memo_returned(self, ic_memo):
        assert ic_memo.get("draft") is not None

    def test_ic_memo_not_approved_at_creation(self, ic_memo):
        assert ic_memo["draft"].get("approved") is False

    def test_ic_memo_requires_approval(self, ic_memo):
        assert ic_memo.get("requires_approval") is True

    def test_ic_memo_markdown_present(self, ic_memo):
        assert len(ic_memo.get("draft_markdown", "")) > 100

    def test_ic_memo_draft_id_differs_from_investor_summary(self, ic_memo, investor_draft):
        assert ic_memo["draft"]["draft_id"] != investor_draft["draft"]["draft_id"]


# ---------------------------------------------------------------------------
# Stage 6: Approval → Publish check flow
# ---------------------------------------------------------------------------

class TestApprovalAndPublishFlow:

    @pytest.fixture(scope="class")
    def approval_record(self, investor_draft):
        draft = investor_draft["draft"]
        return approval_service.request_approval(draft, requested_by="lead-analyst")

    @pytest.fixture(scope="class")
    def approved_record(self, approval_record):
        return approval_service.record_approval(
            approval_record, approver="head-of-risk", notes="Reviewed and approved"
        )

    @pytest.fixture(scope="class")
    def approved_draft(self, investor_draft, approved_record):
        return approval_service.apply_approval_to_draft(
            investor_draft["draft"], approved_record
        )

    def test_approval_request_pending(self, approval_record):
        assert approval_record["status"] == "pending"

    def test_approved_record_status(self, approved_record):
        assert approved_record["status"] == "approved"

    def test_approved_draft_has_flag(self, approved_draft):
        assert approved_draft.get("approved") is True

    def test_publish_check_blocked_for_mock_engine_draft(self, approved_draft, approved_record):
        result = publish_check_workflow(
            draft=approved_draft,
            approval_record=approved_record,
            target_channel="internal",
            actor="integration-test",
        )
        # Demo engine drafts are always BLOCKED — mock data cannot be published
        assert result["recommendation"] == "BLOCKED"
        assert any("mock" in r.lower() for r in result["blocking_reasons"])

    def test_publish_check_blocked_without_approval(self, investor_draft):
        result = publish_check_workflow(
            draft=investor_draft["draft"],
            approval_record=None,
            target_channel="internal",
            actor="integration-test",
        )
        assert result["recommendation"] == "BLOCKED"

    def test_publish_check_blocking_reasons_non_empty_without_approval(self, investor_draft):
        result = publish_check_workflow(
            draft=investor_draft["draft"],
            approval_record=None,
            target_channel="internal",
        )
        assert len(result["blocking_reasons"]) > 0


# ---------------------------------------------------------------------------
# Full pipeline integration
# ---------------------------------------------------------------------------

class TestFullPipelineIntegration:

    def test_pipeline_no_error(self, pipeline):
        assert pipeline.get("error") is None

    def test_all_stages_populated(self, pipeline):
        stages = pipeline["stages"]
        assert stages["analytics"] is not None
        assert stages["optimizer"] is not None
        assert stages["benchmark"] is not None
        assert stages["draft"] is not None

    def test_pipeline_audit_trail_complete(self, pipeline):
        # Should have: pipeline.started + analytics events + optimizer events +
        # benchmark events + draft events + pipeline.completed
        assert len(pipeline["audit_events"]) >= 6

    def test_pipeline_summary_mentions_all_sections(self, pipeline):
        summary = pipeline["pipeline_summary"]
        assert "ANALYTICS" in summary
        assert "OPTIMIZER" in summary
        assert "BENCHMARK" in summary

    def test_pipeline_deal_id_consistent(self, deal, pipeline):
        assert pipeline["deal_id"] == deal["deal_id"]

    def test_pipeline_is_mock(self, pipeline):
        assert pipeline["is_mock"] is True

    def test_analytics_and_pipeline_irr_consistent(self, analytics, pipeline):
        """Analytics stage IRR should match the pipeline's analytics stage IRR."""
        standalone_irr = analytics["key_metrics"]["base_equity_irr"]
        pipeline_irr = pipeline["stages"]["analytics"]["key_metrics"]["base_equity_irr"]
        # Both use the same mock engine → same deal → same outputs
        assert abs(standalone_irr - pipeline_irr) < 1e-6
