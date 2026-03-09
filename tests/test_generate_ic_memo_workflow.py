"""
tests/test_generate_ic_memo_workflow.py

Tests for app/workflows/generate_ic_memo_workflow.py

Covers:
  - Happy path: draft returned, always unapproved, audit events emitted
  - Guard conditions: missing scenario_result, non-complete status
  - Mock flag propagation
  - Optional comparison_result: absent and present
  - Actor recorded in audit events
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.workflows.generate_ic_memo_workflow import generate_ic_memo_workflow


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def deal_input():
    return {
        "deal_id": "deal-001",
        "name": "Test CLO I",
        "issuer": "Test Issuer LLC",
        "collateral": {
            "pool_id": "pool-001",
            "asset_class": "broadly_syndicated_loans",
            "portfolio_size": 500_000_000,
            "diversity_score": 62,
            "ccc_bucket": 0.055,
        },
        "liabilities": [
            {"tranche_id": "t-aaa", "name": "AAA", "seniority": 1, "size_pct": 0.61},
            {"tranche_id": "t-eq",  "name": "Equity", "seniority": 2, "size_pct": 0.09},
        ],
    }


@pytest.fixture
def scenario_result():
    return {
        "deal_id": "deal-001",
        "scenario_id": "scen-001",
        "run_id": "run-001",
        "status": None,
        "outputs": {
            "equity_irr": "[calculated]",
            "aaa_oc_cushion": "[calculated]",
        },
        "_mock": "MOCK_ENGINE_OUTPUT",
    }


@pytest.fixture
def comparison_result():
    return {
        "scenario_a": "scen-001",
        "scenario_b": "scen-002",
        "changed_inputs": [{"key": "default_rate", "a": 0.02, "b": 0.03}],
        "changed_outputs": [{"key": "equity_irr", "a": 0.15, "b": 0.12}],
        "input_changes_count": 1,
        "output_changes_count": 1,
    }


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

class TestHappyPath:

    def test_returns_draft(self, deal_input, scenario_result):
        result = generate_ic_memo_workflow(deal_input, scenario_result)
        assert result["draft"] is not None

    def test_draft_is_dict(self, deal_input, scenario_result):
        result = generate_ic_memo_workflow(deal_input, scenario_result)
        assert isinstance(result["draft"], dict)

    def test_approved_always_false(self, deal_input, scenario_result):
        result = generate_ic_memo_workflow(deal_input, scenario_result)
        assert result["approved"] is False
        assert result["draft"]["approved"] is False

    def test_requires_approval_always_true(self, deal_input, scenario_result):
        result = generate_ic_memo_workflow(deal_input, scenario_result)
        assert result["requires_approval"] is True

    def test_no_error(self, deal_input, scenario_result):
        result = generate_ic_memo_workflow(deal_input, scenario_result)
        assert result["error"] is None

    def test_draft_markdown_is_string(self, deal_input, scenario_result):
        result = generate_ic_memo_workflow(deal_input, scenario_result)
        assert isinstance(result["draft_markdown"], str)
        assert len(result["draft_markdown"]) > 0

    def test_draft_type_is_ic_memo(self, deal_input, scenario_result):
        result = generate_ic_memo_workflow(deal_input, scenario_result)
        assert result["draft"]["draft_type"] == "ic_memo"

    def test_draft_has_sections(self, deal_input, scenario_result):
        result = generate_ic_memo_workflow(deal_input, scenario_result)
        assert "sections" in result["draft"]
        assert len(result["draft"]["sections"]) > 0


# ---------------------------------------------------------------------------
# Audit events
# ---------------------------------------------------------------------------

class TestAuditEvents:

    def test_audit_events_list_returned(self, deal_input, scenario_result):
        result = generate_ic_memo_workflow(deal_input, scenario_result)
        assert "audit_events" in result
        assert isinstance(result["audit_events"], list)

    def test_draft_started_event_emitted(self, deal_input, scenario_result):
        result = generate_ic_memo_workflow(deal_input, scenario_result)
        types = [e["event_type"] for e in result["audit_events"]]
        assert "draft.started" in types

    def test_draft_generated_event_emitted(self, deal_input, scenario_result):
        result = generate_ic_memo_workflow(deal_input, scenario_result)
        types = [e["event_type"] for e in result["audit_events"]]
        assert "draft.generated" in types

    def test_actor_recorded_in_audit_events(self, deal_input, scenario_result):
        result = generate_ic_memo_workflow(
            deal_input, scenario_result, actor="test-runner"
        )
        for event in result["audit_events"]:
            assert event["actor"] == "test-runner"

    def test_deal_id_in_audit_events(self, deal_input, scenario_result):
        result = generate_ic_memo_workflow(deal_input, scenario_result)
        for event in result["audit_events"]:
            assert event["deal_id"] == "deal-001"

    def test_started_event_records_has_comparison_false(self, deal_input, scenario_result):
        result = generate_ic_memo_workflow(deal_input, scenario_result)
        started = next(e for e in result["audit_events"] if e["event_type"] == "draft.started")
        assert started["payload"]["has_comparison"] is False

    def test_started_event_records_has_comparison_true(
        self, deal_input, scenario_result, comparison_result
    ):
        result = generate_ic_memo_workflow(
            deal_input, scenario_result, comparison_result=comparison_result
        )
        started = next(e for e in result["audit_events"] if e["event_type"] == "draft.started")
        assert started["payload"]["has_comparison"] is True


# ---------------------------------------------------------------------------
# Mock flag propagation
# ---------------------------------------------------------------------------

class TestMockFlagPropagation:

    def test_mock_scenario_produces_mock_draft(self, deal_input, scenario_result):
        result = generate_ic_memo_workflow(deal_input, scenario_result)
        assert result["draft"]["is_mock"] is True

    def test_non_mock_scenario_produces_non_mock_draft(self, deal_input):
        clean_result = {
            "deal_id": "deal-001",
            "status": None,
            "outputs": {"equity_irr": 0.14},
        }
        result = generate_ic_memo_workflow(deal_input, clean_result)
        assert result["draft"]["is_mock"] is False

    def test_draft_started_event_records_mock_flag(self, deal_input, scenario_result):
        result = generate_ic_memo_workflow(deal_input, scenario_result)
        started = next(e for e in result["audit_events"] if e["event_type"] == "draft.started")
        assert started["payload"]["is_mock"] is True


# ---------------------------------------------------------------------------
# Comparison result
# ---------------------------------------------------------------------------

class TestComparisonResult:

    def test_works_without_comparison_result(self, deal_input, scenario_result):
        result = generate_ic_memo_workflow(deal_input, scenario_result)
        assert result["error"] is None
        assert result["draft"] is not None

    def test_works_with_comparison_result(
        self, deal_input, scenario_result, comparison_result
    ):
        result = generate_ic_memo_workflow(
            deal_input, scenario_result, comparison_result=comparison_result
        )
        assert result["error"] is None
        assert result["draft"] is not None

    def test_generated_event_records_comparison_section_present(
        self, deal_input, scenario_result, comparison_result
    ):
        result = generate_ic_memo_workflow(
            deal_input, scenario_result, comparison_result=comparison_result
        )
        generated = next(
            e for e in result["audit_events"] if e["event_type"] == "draft.generated"
        )
        assert generated["payload"]["has_comparison_section"] is True

    def test_generated_event_records_comparison_section_absent(
        self, deal_input, scenario_result
    ):
        result = generate_ic_memo_workflow(deal_input, scenario_result)
        generated = next(
            e for e in result["audit_events"] if e["event_type"] == "draft.generated"
        )
        assert generated["payload"]["has_comparison_section"] is False


# ---------------------------------------------------------------------------
# Guard conditions
# ---------------------------------------------------------------------------

class TestGuardConditions:

    def test_missing_scenario_result_returns_error(self, deal_input):
        result = generate_ic_memo_workflow(deal_input, None)
        assert result["error"] is not None
        assert result["draft"] is None
        assert result["approved"] is False

    def test_empty_scenario_result_returns_error(self, deal_input):
        result = generate_ic_memo_workflow(deal_input, {})
        assert result["error"] is not None

    def test_incomplete_status_returns_error(self, deal_input):
        incomplete = {"deal_id": "deal-001", "status": "running"}
        result = generate_ic_memo_workflow(deal_input, incomplete)
        assert result["error"] is not None
        assert "running" in result["error"]

    def test_complete_status_string_is_accepted(self, deal_input):
        complete = {
            "deal_id": "deal-001",
            "status": "complete",
            "outputs": {"equity_irr": 0.14},
        }
        result = generate_ic_memo_workflow(deal_input, complete)
        assert result["error"] is None
        assert result["draft"] is not None
