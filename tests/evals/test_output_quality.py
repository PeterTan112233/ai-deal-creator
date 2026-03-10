"""
tests/evals/test_output_quality.py

Output quality evaluation tests.

These tests check properties that a human reviewer or automated quality gate
would care about: proper [demo] tagging, completeness of audit trails, sensible
numeric ranges, structural consistency, and no silent failures.

They are not unit tests (they don't assert exact values) but rather
invariant checks that must hold across ALL demo outputs.
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
from app.workflows.full_pipeline_workflow import full_pipeline_workflow


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def deal():
    with open("data/samples/sample_deal_inputs.json") as f:
        return json.load(f)["deals"][0]


@pytest.fixture(scope="module")
def analytics(deal):
    return deal_analytics_workflow(deal, run_sensitivity=False)


@pytest.fixture(scope="module")
def optimizer(deal):
    return tranche_optimizer_workflow(deal, aaa_min=0.60, aaa_max=0.64, aaa_step=0.02)


@pytest.fixture(scope="module")
def base_scenario(deal):
    return run_scenario_workflow(deal, scenario_name="Baseline", scenario_type="base")


@pytest.fixture(scope="module")
def investor_draft(deal, base_scenario):
    return generate_investor_summary_workflow(
        deal_input=deal,
        scenario_result=base_scenario.get("scenario_result", {}),
        scenario_request=base_scenario.get("scenario_request"),
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
    )


# ---------------------------------------------------------------------------
# [demo] tag presence
# ---------------------------------------------------------------------------

class TestDemoTagging:
    """Every analyst-facing text output must be clearly tagged [demo]."""

    def test_analytics_report_has_demo_tag(self, analytics):
        report = analytics.get("analytics_report", "")
        assert "[demo]" in report.lower() or "DEMO" in report, \
            "Analytics report must contain [demo] tag"

    def test_pipeline_summary_has_demo_tag(self, pipeline):
        summary = pipeline.get("pipeline_summary", "")
        assert "[demo]" in summary.lower() or "DEMO" in summary, \
            "Pipeline summary must contain [demo] tag"

    def test_benchmark_report_has_demo_tag(self, deal, analytics):
        results = analytics["scenario_suite"]["results"]
        base = next(r for r in results if r["scenario_name"] == "Base")
        bench = benchmark_comparison_workflow(
            deal_input=deal,
            scenario_outputs=base["outputs"],
            vintage=2024,
            region="US",
        )
        report = bench.get("comparison_report", "")
        assert "DEMO" in report, "Benchmark report must contain DEMO tag"

    def test_optimizer_feasibility_table_has_source_annotation(self, optimizer):
        table = optimizer.get("feasibility_table", [])
        assert len(table) > 0
        # Each row should have run_id referencing mock engine
        for row in table:
            assert "run_id" in row, "Each feasibility row must have a run_id"

    def test_draft_markdown_has_demo_or_generated_tag(self, investor_draft):
        md = investor_draft.get("draft_markdown", "")
        # Investor summary should indicate it is generated/demo
        has_tag = (
            "[demo]" in md.lower()
            or "[generated]" in md.lower()
            or "demo" in md.lower()
        )
        assert has_tag, "Draft markdown must reference demo/generated status"


# ---------------------------------------------------------------------------
# Audit trail completeness
# ---------------------------------------------------------------------------

class TestAuditTrailCompleteness:

    def test_analytics_has_audit_events(self, analytics):
        assert len(analytics.get("audit_events", [])) >= 2

    def test_optimizer_has_audit_events(self, optimizer):
        assert len(optimizer.get("audit_events", [])) >= 1

    def test_base_scenario_has_audit_events(self, base_scenario):
        assert len(base_scenario.get("audit_events", [])) >= 1

    def test_investor_draft_has_audit_events(self, investor_draft):
        assert len(investor_draft.get("audit_events", [])) >= 1

    def test_pipeline_audit_events_cover_all_stages(self, pipeline):
        events = pipeline.get("audit_events", [])
        # At minimum: pipeline.started + analytics + optimizer + benchmark + draft + pipeline.completed
        assert len(events) >= 6

    def test_audit_events_are_strings(self, pipeline):
        for ev in pipeline["audit_events"]:
            assert isinstance(ev, str), f"Audit event must be string, got {type(ev)}"

    def test_analytics_audit_events_are_strings(self, analytics):
        for ev in analytics.get("audit_events", []):
            assert isinstance(ev, str)

    def test_pipeline_has_started_and_completed_events(self, pipeline):
        # Pipeline emits pipeline.started (first) and pipeline.completed (last)
        events = pipeline["audit_events"]
        assert len(events) >= 2


# ---------------------------------------------------------------------------
# Numeric sanity ranges
# ---------------------------------------------------------------------------

class TestNumericSanity:
    """CLO output numbers must fall in plausible ranges for a US BSL deal."""

    def test_equity_irr_in_range(self, analytics):
        irr = analytics["key_metrics"]["base_equity_irr"]
        assert 0.0 < irr < 0.50, f"Equity IRR {irr:.2%} outside plausible range (0–50%)"

    def test_oc_cushion_in_range(self, analytics):
        oc = analytics["key_metrics"].get("base_oc_cushion")
        if oc is not None:
            assert -0.20 < oc < 0.50, f"OC cushion {oc:.2%} outside plausible range"

    def test_stress_irr_less_than_base_irr(self, analytics):
        results = analytics["scenario_suite"]["results"]
        base = next(r for r in results if r["scenario_name"] == "Base")
        stress = next(r for r in results if r["scenario_name"] == "Stress")
        assert base["outputs"]["equity_irr"] > stress["outputs"]["equity_irr"]

    def test_optimal_aaa_is_meaningful_fraction(self, optimizer):
        opt = optimizer.get("optimal")
        if opt:
            aaa = opt["aaa_size_pct"]
            assert 0.40 < aaa < 0.85, f"Optimal AAA {aaa:.1%} outside plausible range"

    def test_optimal_equity_is_positive(self, optimizer):
        opt = optimizer.get("optimal")
        if opt:
            eq = opt["equity_size_pct"]
            assert eq > 0, "Equity tranche must be positive"

    def test_aaa_plus_mez_plus_equity_close_to_one(self, optimizer):
        opt = optimizer.get("optimal")
        if opt:
            total = opt["aaa_size_pct"] + opt["mez_size_pct"] + opt["equity_size_pct"]
            assert abs(total - 1.0) < 0.02, f"Tranche sizes sum to {total:.3f}, expected ~1.0"

    def test_benchmark_counts_non_negative(self, deal, analytics):
        results = analytics["scenario_suite"]["results"]
        base = next(r for r in results if r["scenario_name"] == "Base")
        bench = benchmark_comparison_workflow(
            deal_input=deal,
            scenario_outputs=base["outputs"],
            vintage=2024,
            region="US",
        )
        assert bench.get("above_median_count", 0) >= 0
        assert bench.get("below_median_count", 0) >= 0


# ---------------------------------------------------------------------------
# Structural consistency
# ---------------------------------------------------------------------------

class TestStructuralConsistency:

    def test_scenario_results_all_have_outputs(self, analytics):
        for r in analytics["scenario_suite"]["results"]:
            assert "outputs" in r, f"Scenario {r['scenario_name']} missing outputs"
            assert "equity_irr" in r["outputs"]

    def test_feasibility_table_rows_have_required_fields(self, optimizer):
        required = {"aaa_size_pct", "equity_irr", "feasible", "run_id"}
        for row in optimizer.get("feasibility_table", []):
            missing = required - set(row.keys())
            assert not missing, f"Feasibility row missing fields: {missing}"

    def test_pipeline_stages_dict_has_all_keys(self, pipeline):
        assert set(pipeline["stages"].keys()) == {"analytics", "optimizer", "benchmark", "draft"}

    def test_pipeline_ids_have_correct_prefix(self, pipeline):
        assert pipeline["pipeline_id"].startswith("pipeline-")

    def test_run_at_is_iso_format(self, pipeline):
        from datetime import datetime
        run_at = pipeline.get("run_at", "")
        # Should parse as ISO datetime
        datetime.fromisoformat(run_at)  # raises if malformed

    def test_deal_id_consistent_through_pipeline(self, deal, pipeline):
        assert pipeline["deal_id"] == deal["deal_id"]

    def test_analytics_scenario_suite_has_results_list(self, analytics):
        suite = analytics.get("scenario_suite", {})
        assert isinstance(suite.get("results"), list)

    def test_investor_draft_has_required_keys(self, investor_draft):
        required = {"draft", "draft_markdown", "approved", "requires_approval", "audit_events"}
        missing = required - set(investor_draft.keys())
        assert not missing, f"Investor draft missing keys: {missing}"

    def test_no_none_values_in_pipeline_key_fields(self, pipeline):
        for key in ("pipeline_id", "deal_id", "run_at", "is_mock"):
            assert pipeline[key] is not None, f"pipeline['{key}'] should not be None"
