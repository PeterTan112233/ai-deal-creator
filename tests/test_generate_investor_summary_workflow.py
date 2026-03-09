"""
tests/test_generate_investor_summary_workflow.py

Tests for app/workflows/generate_investor_summary_workflow.py

Covers:
  - Happy path: draft returned, always unapproved, audit events emitted
  - Guard conditions: missing scenario_result, non-complete status
  - Mock flag propagation
  - Actor recorded in audit events
  - Markdown output present
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.workflows.generate_investor_summary_workflow import generate_investor_summary_workflow


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
        "status": None,  # complete (None treated as complete)
        "outputs": {
            "equity_irr": "[calculated]",
            "aaa_oc_cushion": "[calculated]",
        },
        "_mock": "MOCK_ENGINE_OUTPUT",
    }


@pytest.fixture
def scenario_request():
    return {
        "scenario_id": "scen-001",
        "name": "Baseline",
        "market_assumptions": {"default_rate": 0.03, "recovery_rate": 0.65},
    }


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

class TestHappyPath:

    def test_returns_draft(self, deal_input, scenario_result):
        result = generate_investor_summary_workflow(deal_input, scenario_result)
        assert result["draft"] is not None

    def test_draft_is_dict(self, deal_input, scenario_result):
        result = generate_investor_summary_workflow(deal_input, scenario_result)
        assert isinstance(result["draft"], dict)

    def test_approved_always_false(self, deal_input, scenario_result):
        result = generate_investor_summary_workflow(deal_input, scenario_result)
        assert result["approved"] is False
        assert result["draft"]["approved"] is False

    def test_requires_approval_always_true(self, deal_input, scenario_result):
        result = generate_investor_summary_workflow(deal_input, scenario_result)
        assert result["requires_approval"] is True

    def test_no_error(self, deal_input, scenario_result):
        result = generate_investor_summary_workflow(deal_input, scenario_result)
        assert result["error"] is None

    def test_draft_markdown_is_string(self, deal_input, scenario_result):
        result = generate_investor_summary_workflow(deal_input, scenario_result)
        assert isinstance(result["draft_markdown"], str)
        assert len(result["draft_markdown"]) > 0

    def test_draft_type_is_investor_summary(self, deal_input, scenario_result):
        result = generate_investor_summary_workflow(deal_input, scenario_result)
        assert result["draft"]["draft_type"] == "investor_summary"

    def test_draft_has_sections(self, deal_input, scenario_result):
        result = generate_investor_summary_workflow(deal_input, scenario_result)
        assert "sections" in result["draft"]
        assert len(result["draft"]["sections"]) > 0


# ---------------------------------------------------------------------------
# Audit events
# ---------------------------------------------------------------------------

class TestAuditEvents:

    def test_audit_events_list_returned(self, deal_input, scenario_result):
        result = generate_investor_summary_workflow(deal_input, scenario_result)
        assert "audit_events" in result
        assert isinstance(result["audit_events"], list)

    def test_draft_started_event_emitted(self, deal_input, scenario_result):
        result = generate_investor_summary_workflow(deal_input, scenario_result)
        types = [e["event_type"] for e in result["audit_events"]]
        assert "draft.started" in types

    def test_draft_generated_event_emitted(self, deal_input, scenario_result):
        result = generate_investor_summary_workflow(deal_input, scenario_result)
        types = [e["event_type"] for e in result["audit_events"]]
        assert "draft.generated" in types

    def test_actor_recorded_in_audit_events(self, deal_input, scenario_result):
        result = generate_investor_summary_workflow(
            deal_input, scenario_result, actor="test-runner"
        )
        for event in result["audit_events"]:
            assert event["actor"] == "test-runner"

    def test_deal_id_in_audit_events(self, deal_input, scenario_result):
        result = generate_investor_summary_workflow(deal_input, scenario_result)
        for event in result["audit_events"]:
            assert event["deal_id"] == "deal-001"


# ---------------------------------------------------------------------------
# Mock flag propagation
# ---------------------------------------------------------------------------

class TestMockFlagPropagation:

    def test_mock_scenario_produces_mock_draft(self, deal_input, scenario_result):
        result = generate_investor_summary_workflow(deal_input, scenario_result)
        assert result["draft"]["is_mock"] is True

    def test_non_mock_scenario_produces_non_mock_draft(self, deal_input):
        clean_result = {
            "deal_id": "deal-001",
            "scenario_id": "scen-001",
            "run_id": "run-001",
            "status": None,
            "outputs": {"equity_irr": 0.14},
        }
        result = generate_investor_summary_workflow(deal_input, clean_result)
        assert result["draft"]["is_mock"] is False

    def test_draft_started_event_records_mock_flag(self, deal_input, scenario_result):
        result = generate_investor_summary_workflow(deal_input, scenario_result)
        started = next(e for e in result["audit_events"] if e["event_type"] == "draft.started")
        assert started["payload"]["is_mock"] is True


# ---------------------------------------------------------------------------
# Guard conditions
# ---------------------------------------------------------------------------

class TestGuardConditions:

    def test_missing_scenario_result_returns_error(self, deal_input):
        result = generate_investor_summary_workflow(deal_input, None)
        assert result["error"] is not None
        assert result["draft"] is None
        assert result["approved"] is False

    def test_empty_scenario_result_returns_error(self, deal_input):
        result = generate_investor_summary_workflow(deal_input, {})
        assert result["error"] is not None
        assert result["draft"] is None

    def test_incomplete_status_returns_error(self, deal_input):
        incomplete = {"deal_id": "deal-001", "status": "running"}
        result = generate_investor_summary_workflow(deal_input, incomplete)
        assert result["error"] is not None
        assert "running" in result["error"]

    def test_failed_status_returns_error(self, deal_input):
        failed = {"deal_id": "deal-001", "status": "failed"}
        result = generate_investor_summary_workflow(deal_input, failed)
        assert result["error"] is not None

    def test_complete_status_string_is_accepted(self, deal_input):
        complete = {
            "deal_id": "deal-001",
            "status": "complete",
            "outputs": {"equity_irr": 0.14},
        }
        result = generate_investor_summary_workflow(deal_input, complete)
        assert result["error"] is None
        assert result["draft"] is not None


# ---------------------------------------------------------------------------
# Optional scenario_request
# ---------------------------------------------------------------------------

class TestOptionalScenarioRequest:

    def test_works_without_scenario_request(self, deal_input, scenario_result):
        result = generate_investor_summary_workflow(deal_input, scenario_result)
        assert result["error"] is None
        assert result["draft"] is not None

    def test_works_with_scenario_request(self, deal_input, scenario_result, scenario_request):
        result = generate_investor_summary_workflow(
            deal_input, scenario_result, scenario_request=scenario_request
        )
        assert result["error"] is None
        assert result["draft"] is not None
