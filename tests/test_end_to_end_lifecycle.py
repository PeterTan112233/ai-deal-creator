"""
tests/test_end_to_end_lifecycle.py

End-to-end integration tests for the full deal lifecycle.

Lifecycle under test:
  1. create_deal_workflow          — validate and register deal
  2. deal_input_from_domain        — bridge to run_scenario_workflow
  3. run_scenario_workflow         — submit to engine, collect result
  4. generate_investor_summary_workflow — draft investor summary
  5. generate_ic_memo_workflow     — draft IC memo
  6. request_approval              — create pending approval record
  7. record_approval               — approve the record
  8. apply_approval_to_draft       — stamp draft as approved
  9. publish_check_workflow        — run publish-readiness gate
 10. APPROVED_TO_PUBLISH           — final gate result

All steps use Phase 1 mock services. No real MCP servers required.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.domain.deal import Deal
from app.domain.collateral import Collateral
from app.domain.structure import Structure
from app.domain.tranche import Tranche

from app.workflows.create_deal_workflow import create_deal_workflow, deal_input_from_domain
from app.workflows.run_scenario_workflow import run_scenario_workflow
from app.workflows.generate_investor_summary_workflow import generate_investor_summary_workflow
from app.workflows.generate_ic_memo_workflow import generate_ic_memo_workflow
from app.workflows.publish_check_workflow import publish_check_workflow
from app.services import approval_service


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def deal():
    return Deal(
        deal_id="e2e-deal-001",
        name="E2E Test CLO",
        issuer="E2E Issuer LLC",
        region="US",
        currency="USD",
        manager="E2E Manager",
    )


@pytest.fixture
def collateral():
    return Collateral(
        collateral_id="e2e-coll-001",
        deal_id="e2e-deal-001",
        pool_id="pool-001",
        asset_class="broadly_syndicated_loans",
        portfolio_size=500_000_000,
        was=0.042,
        warf=2800,
        wal=5.2,
        diversity_score=62,
        ccc_bucket=0.055,
    )


@pytest.fixture
def structure(deal):
    return Structure(
        structure_id="e2e-struct-001",
        deal_id=deal.deal_id,
        tranches=[
            Tranche(tranche_id="t-aaa", name="AAA", seniority=1,
                    size_pct=0.61, coupon="SOFR+145", target_rating="Aaa"),
            Tranche(tranche_id="t-aa",  name="AA",  seniority=2,
                    size_pct=0.06, coupon="SOFR+200", target_rating="Aa2"),
            Tranche(tranche_id="t-eq",  name="Equity", seniority=3,
                    size_pct=0.09),
        ],
    )


@pytest.fixture
def market_assumptions():
    return {"default_rate": 0.03, "recovery_rate": 0.65, "spread_shock_bps": 0}


# ---------------------------------------------------------------------------
# Stage 1: create_deal_workflow
# ---------------------------------------------------------------------------

class TestStage1CreateDeal:

    def test_create_deal_succeeds(self, deal, collateral, structure):
        result = create_deal_workflow(deal, collateral, structure, actor="e2e-test")
        assert result["deal_id"] == "e2e-deal-001"
        assert result["tranche_count"] == 3

    def test_create_deal_emits_audit_event(self, deal, collateral, structure, monkeypatch):
        import app.services.audit_logger as al
        events = []
        original = al.record_event
        def capture(*a, **kw):
            ev = original(*a, **kw)
            events.append(ev)
            return ev
        monkeypatch.setattr(al, "record_event", capture)
        create_deal_workflow(deal, collateral, structure)
        assert any(e["event_type"] == "deal.created" for e in events)


# ---------------------------------------------------------------------------
# Stage 2: deal_input_from_domain bridge
# ---------------------------------------------------------------------------

class TestStage2Bridge:

    def test_bridge_produces_valid_deal_input(self, deal, collateral, structure, market_assumptions):
        deal_input = deal_input_from_domain(deal, collateral, structure, market_assumptions)
        assert deal_input["deal_id"] == "e2e-deal-001"
        assert len(deal_input["liabilities"]) == 3
        assert deal_input["market_assumptions"]["default_rate"] == 0.03

    def test_bridge_collateral_clean(self, deal, collateral, structure):
        deal_input = deal_input_from_domain(deal, collateral, structure)
        for k, v in deal_input["collateral"].items():
            assert v is not None, f"collateral.{k} should not be None"


# ---------------------------------------------------------------------------
# Stage 3: run_scenario_workflow
# ---------------------------------------------------------------------------

class TestStage3RunScenario:

    def test_scenario_runs_successfully(self, deal, collateral, structure, market_assumptions):
        deal_input = deal_input_from_domain(deal, collateral, structure, market_assumptions)
        result = run_scenario_workflow(deal_input, scenario_name="Baseline", actor="e2e-test")
        assert result["validation"]["valid"] is True
        assert result["scenario_result"] is not None
        assert result["scenario_result"]["deal_id"] == "e2e-deal-001"

    def test_scenario_result_is_mock(self, deal, collateral, structure, market_assumptions):
        deal_input = deal_input_from_domain(deal, collateral, structure, market_assumptions)
        result = run_scenario_workflow(deal_input)
        assert result["is_mock"] is True
        assert "_mock" in result["scenario_result"]

    def test_scenario_emits_audit_events(self, deal, collateral, structure, market_assumptions):
        deal_input = deal_input_from_domain(deal, collateral, structure, market_assumptions)
        result = run_scenario_workflow(deal_input, actor="e2e-test")
        assert len(result["audit_events"]) >= 3  # validated, submitted, completed


# ---------------------------------------------------------------------------
# Stage 4 & 5: generate drafts
# ---------------------------------------------------------------------------

class TestStage4GenerateDrafts:

    @pytest.fixture
    def scenario_result(self, deal, collateral, structure, market_assumptions):
        deal_input = deal_input_from_domain(deal, collateral, structure, market_assumptions)
        return run_scenario_workflow(deal_input)["scenario_result"]

    @pytest.fixture
    def deal_input(self, deal, collateral, structure, market_assumptions):
        return deal_input_from_domain(deal, collateral, structure, market_assumptions)

    def test_investor_summary_generated(self, deal_input, scenario_result):
        result = generate_investor_summary_workflow(deal_input, scenario_result, actor="e2e-test")
        assert result["error"] is None
        assert result["draft"] is not None
        assert result["approved"] is False
        assert result["requires_approval"] is True

    def test_ic_memo_generated(self, deal_input, scenario_result):
        result = generate_ic_memo_workflow(deal_input, scenario_result, actor="e2e-test")
        assert result["error"] is None
        assert result["draft"] is not None
        assert result["approved"] is False

    def test_both_drafts_are_mock(self, deal_input, scenario_result):
        inv = generate_investor_summary_workflow(deal_input, scenario_result)
        ic  = generate_ic_memo_workflow(deal_input, scenario_result)
        assert inv["draft"]["is_mock"] is True
        assert ic["draft"]["is_mock"] is True

    def test_draft_sections_have_source_tags(self, deal_input, scenario_result):
        result = generate_investor_summary_workflow(deal_input, scenario_result)
        for section in result["draft"]["sections"]:
            assert "source_tag" in section, f"Section {section.get('section_id')} missing source_tag"


# ---------------------------------------------------------------------------
# Stage 6, 7, 8: approval flow
# ---------------------------------------------------------------------------

class TestStage5ApprovalFlow:

    @pytest.fixture
    def approved_draft(self, deal, collateral, structure, market_assumptions):
        deal_input = deal_input_from_domain(deal, collateral, structure, market_assumptions)
        scenario_result = run_scenario_workflow(deal_input)["scenario_result"]
        draft_result = generate_investor_summary_workflow(deal_input, scenario_result)
        draft = draft_result["draft"]

        pending = approval_service.request_approval(draft, requested_by="analyst-1")
        approved_record = approval_service.record_approval(pending, approver="clo-head")
        approved_draft = approval_service.apply_approval_to_draft(draft, approved_record)
        return approved_draft, approved_record

    def test_pending_record_status(self, deal, collateral, structure, market_assumptions):
        deal_input = deal_input_from_domain(deal, collateral, structure, market_assumptions)
        scenario_result = run_scenario_workflow(deal_input)["scenario_result"]
        draft = generate_investor_summary_workflow(deal_input, scenario_result)["draft"]
        pending = approval_service.request_approval(draft, requested_by="analyst-1")
        assert pending["status"] == "pending"

    def test_approved_record_status(self, deal, collateral, structure, market_assumptions):
        deal_input = deal_input_from_domain(deal, collateral, structure, market_assumptions)
        scenario_result = run_scenario_workflow(deal_input)["scenario_result"]
        draft = generate_investor_summary_workflow(deal_input, scenario_result)["draft"]
        pending = approval_service.request_approval(draft, requested_by="analyst-1")
        approved = approval_service.record_approval(pending, approver="clo-head")
        assert approved["status"] == "approved"

    def test_apply_approval_sets_draft_approved_true(self, approved_draft):
        draft, _ = approved_draft
        assert draft["approved"] is True

    def test_draft_id_matches_approval_record(self, approved_draft):
        draft, record = approved_draft
        assert record["draft_id"] == draft["draft_id"]


# ---------------------------------------------------------------------------
# Stage 9: publish_check_workflow
# ---------------------------------------------------------------------------

class TestStage6PublishCheck:

    @pytest.fixture
    def approved_package(self, deal, collateral, structure, market_assumptions):
        """Full approval package: approved draft + approved record."""
        deal_input = deal_input_from_domain(deal, collateral, structure, market_assumptions)
        scenario_result = run_scenario_workflow(deal_input)["scenario_result"]
        draft_result = generate_investor_summary_workflow(deal_input, scenario_result)
        draft = draft_result["draft"]

        pending = approval_service.request_approval(draft, requested_by="analyst-1")
        approved_record = approval_service.record_approval(pending, approver="clo-head")
        approved_draft = approval_service.apply_approval_to_draft(draft, approved_record)
        return approved_draft, approved_record

    def test_mock_draft_is_blocked(self, approved_package):
        """Even with a valid approval, mock data must never pass the publish gate."""
        approved_draft, approved_record = approved_package
        result = publish_check_workflow(
            draft=approved_draft,
            approval_record=approved_record,
            target_channel="internal",
        )
        assert result["recommendation"] == "BLOCKED"
        assert any("mock" in r.lower() for r in result["blocking_reasons"])

    def test_non_mock_approved_internal_passes(self):
        """A non-mock approved draft for internal channel reaches APPROVED_TO_PUBLISH."""
        draft = {
            "draft_id":   "draft-e2e-nm",
            "deal_id":    "e2e-deal-001",
            "draft_type": "investor_summary",
            "approved":   False,
            "is_mock":    False,
            "sections":   [{"section_id": "s1", "content": "Clean content.", "source_tag": "[generated]"}],
        }
        pending = approval_service.request_approval(draft, requested_by="analyst-1")
        approved_record = approval_service.record_approval(pending, approver="clo-head")
        approved_draft = approval_service.apply_approval_to_draft(draft, approved_record)

        result = publish_check_workflow(
            draft=approved_draft,
            approval_record=approved_record,
            target_channel="internal",
        )
        assert result["recommendation"] == "APPROVED_TO_PUBLISH"
        assert result["pass"] is True

    def test_non_mock_approved_external_passes(self):
        """A non-mock approved draft with external-scoped record reaches APPROVED_TO_PUBLISH."""
        draft = {
            "draft_id":   "draft-e2e-ext",
            "deal_id":    "e2e-deal-001",
            "draft_type": "investor_summary",
            "approved":   False,
            "is_mock":    False,
            "sections":   [],
        }
        pending = approval_service.request_approval(draft, requested_by="analyst-1", channel="external")
        approved_record = approval_service.record_approval(pending, approver="clo-head")
        approved_draft = approval_service.apply_approval_to_draft(draft, approved_record)

        result = publish_check_workflow(
            draft=approved_draft,
            approval_record=approved_record,
            target_channel="external",
        )
        assert result["recommendation"] == "APPROVED_TO_PUBLISH"

    def test_unapproved_draft_is_blocked(self):
        """An unapproved draft must never pass the publish gate."""
        draft = {
            "draft_id":   "draft-e2e-unap",
            "deal_id":    "e2e-deal-001",
            "draft_type": "investor_summary",
            "approved":   False,
            "is_mock":    False,
            "sections":   [],
        }
        result = publish_check_workflow(draft=draft, target_channel="internal")
        assert result["recommendation"] == "BLOCKED"

    def test_all_checks_run(self):
        """publish_check_workflow always runs all 7 checks."""
        draft = {
            "draft_id": "draft-e2e-chk",
            "deal_id":  "e2e-deal-001",
            "draft_type": "investor_summary",
            "approved": False,
            "is_mock":  False,
            "sections": [],
        }
        result = publish_check_workflow(draft=draft)
        check_ids = {c["check_id"] for c in result["checks_run"]}
        expected = {
            "mock_data", "draft_approved", "approval_record",
            "channel_policy", "draft_id_match", "approval_expiry", "placeholder_scan",
        }
        assert check_ids == expected


# ---------------------------------------------------------------------------
# Full lifecycle: create → publish APPROVED_TO_PUBLISH
# ---------------------------------------------------------------------------

class TestFullLifecycle:

    def test_full_lifecycle_mock_ends_at_blocked(
        self, deal, collateral, structure, market_assumptions
    ):
        """
        Full lifecycle with mock engine always ends at BLOCKED because
        mock data must never be published. This is the expected Phase 1 result.
        """
        # Stage 1: create deal
        create_deal_workflow(deal, collateral, structure, actor="e2e")

        # Stage 2: bridge
        deal_input = deal_input_from_domain(deal, collateral, structure, market_assumptions)

        # Stage 3: run scenario
        run_result = run_scenario_workflow(deal_input, scenario_name="Baseline", actor="e2e")
        assert run_result["validation"]["valid"] is True
        scenario_result = run_result["scenario_result"]

        # Stage 4: generate investor summary
        draft_result = generate_investor_summary_workflow(deal_input, scenario_result, actor="e2e")
        assert draft_result["error"] is None
        draft = draft_result["draft"]

        # Stage 5: request and record approval
        pending = approval_service.request_approval(draft, requested_by="analyst-1")
        approved_record = approval_service.record_approval(pending, approver="clo-head")
        approved_draft = approval_service.apply_approval_to_draft(draft, approved_record)
        assert approved_draft["approved"] is True

        # Stage 6: publish check — must be BLOCKED because draft is mock
        publish_result = publish_check_workflow(
            draft=approved_draft,
            approval_record=approved_record,
            target_channel="internal",
            actor="e2e",
        )
        assert publish_result["recommendation"] == "BLOCKED"
        assert any("mock" in r.lower() for r in publish_result["blocking_reasons"])

    def test_full_lifecycle_audit_trail_complete(
        self, deal, collateral, structure, market_assumptions, monkeypatch
    ):
        """All lifecycle stages emit audit events — verify the trail is non-empty."""
        import app.services.audit_logger as al
        import app.workflows.generate_investor_summary_workflow as gisw
        events = []
        original = al.record_event
        def capture(*a, **kw):
            ev = original(*a, **kw)
            events.append(ev)
            return ev
        # Patch both the module and the direct binding in the workflow
        monkeypatch.setattr(al, "record_event", capture)
        monkeypatch.setattr(gisw, "record_event", capture)

        create_deal_workflow(deal, collateral, structure, actor="e2e")
        deal_input = deal_input_from_domain(deal, collateral, structure, market_assumptions)
        run_result = run_scenario_workflow(deal_input, actor="e2e")
        generate_investor_summary_workflow(deal_input, run_result["scenario_result"], actor="e2e")

        event_types = {e["event_type"] for e in events}
        assert "deal.created" in event_types
        assert "deal.validated" in event_types
        assert "scenario.submitted" in event_types
        assert "scenario.completed" in event_types
        assert "draft.started" in event_types
        assert "draft.generated" in event_types
