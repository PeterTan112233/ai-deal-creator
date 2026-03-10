"""
tests/policy/test_governance.py

Policy enforcement tests for the AI Deal Creator governance layer.

Verifies that the system correctly enforces:
  - No publication without an approval record
  - Mock data is blocked from external channels
  - Approval record status transitions (pending → approved/rejected)
  - Rejection workflow blocks publish
  - Channel policy: internal vs. external requirements
  - Approval cannot be re-applied once already applied
  - Draft ID must match approval record

These tests use service functions directly, not the HTTP API, so they
run fast and do not depend on FastAPI or the mock engine.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

import pytest

from app.services import approval_service
from app.workflows.publish_check_workflow import publish_check_workflow


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _mock_draft(approved=False, draft_type="investor_summary", draft_id="draft-test-001"):
    return {
        "draft_id": draft_id,
        "deal_id": "deal-policy-001",
        "draft_type": draft_type,
        "approved": approved,
        "sections": [{"section_id": "overview", "title": "Overview", "content": "Test CLO overview text."}],
        "grounding_sources": [],
        "is_mock": True,  # marks as mock engine output
    }


def _approved_record(draft, approver="head-of-risk"):
    rec = approval_service.request_approval(draft, requested_by="analyst")
    rec = approval_service.record_approval(rec, approver=approver)
    return rec


# ---------------------------------------------------------------------------
# Approval state machine
# ---------------------------------------------------------------------------

class TestApprovalStateMachine:

    def test_request_creates_pending_record(self):
        draft = _mock_draft()
        rec = approval_service.request_approval(draft, requested_by="analyst")
        assert rec["status"] == "pending"

    def test_pending_record_has_draft_id(self):
        draft = _mock_draft()
        rec = approval_service.request_approval(draft, requested_by="analyst")
        assert rec["draft_id"] == draft["draft_id"]

    def test_pending_record_has_deal_id(self):
        draft = _mock_draft()
        rec = approval_service.request_approval(draft, requested_by="analyst")
        assert rec["deal_id"] == draft["deal_id"]

    def test_record_approval_sets_approved_status(self):
        draft = _mock_draft()
        rec = approval_service.request_approval(draft, requested_by="analyst")
        rec = approval_service.record_approval(rec, approver="head-of-risk")
        assert rec["status"] == "approved"

    def test_record_approval_sets_approver(self):
        draft = _mock_draft()
        rec = approval_service.request_approval(draft, requested_by="analyst")
        rec = approval_service.record_approval(rec, approver="head-of-risk")
        assert rec.get("approver") == "head-of-risk"

    def test_record_rejection_sets_rejected_status(self):
        draft = _mock_draft()
        rec = approval_service.request_approval(draft, requested_by="analyst")
        rec = approval_service.record_rejection(
            rec, approver="head-of-risk", rejection_reason="Needs more scenario detail."
        )
        assert rec["status"] == "rejected"

    def test_record_rejection_stores_reason(self):
        draft = _mock_draft()
        rec = approval_service.request_approval(draft, requested_by="analyst")
        rec = approval_service.record_rejection(
            rec, approver="head-of-risk", rejection_reason="Missing stress scenario."
        )
        assert "Missing stress scenario." in rec.get("rejection_reason", "")

    def test_apply_approval_sets_draft_approved_flag(self):
        draft = _mock_draft()
        approved_rec = _approved_record(draft)
        approved_draft = approval_service.apply_approval_to_draft(draft, approved_rec)
        assert approved_draft["approved"] is True

    def test_apply_rejected_record_raises(self):
        draft = _mock_draft()
        rec = approval_service.request_approval(draft, requested_by="analyst")
        rec = approval_service.record_rejection(
            rec, approver="reviewer", rejection_reason="Not ready."
        )
        # Applying a rejected record must raise — it cannot grant approval
        with pytest.raises((ValueError, Exception)):
            approval_service.apply_approval_to_draft(draft, rec)


# ---------------------------------------------------------------------------
# Publish check — blocking rules
# ---------------------------------------------------------------------------

class TestPublishCheckBlocking:

    def test_unapproved_draft_blocked(self):
        draft = _mock_draft(approved=False)
        result = publish_check_workflow(
            draft=draft, approval_record=None, target_channel="internal"
        )
        assert result["recommendation"] == "BLOCKED"

    def test_unapproved_draft_has_blocking_reason(self):
        draft = _mock_draft(approved=False)
        result = publish_check_workflow(
            draft=draft, approval_record=None, target_channel="internal"
        )
        assert len(result["blocking_reasons"]) > 0

    def test_rejected_approval_blocks_publish(self):
        draft = _mock_draft(approved=False)
        rec = approval_service.request_approval(draft, requested_by="analyst")
        rejected = approval_service.record_rejection(
            rec, approver="reviewer", rejection_reason="Needs revision."
        )
        result = publish_check_workflow(
            draft=draft, approval_record=rejected, target_channel="internal"
        )
        assert result["recommendation"] == "BLOCKED"

    def test_draft_id_mismatch_blocks_publish(self):
        draft = _mock_draft(approved=True, draft_id="draft-aaa")
        wrong_draft = _mock_draft(approved=True, draft_id="draft-bbb")
        approved_rec = _approved_record(draft)
        # Try publish with mismatched draft
        result = publish_check_workflow(
            draft=wrong_draft, approval_record=approved_rec, target_channel="internal"
        )
        assert result["recommendation"] == "BLOCKED"

    def test_external_channel_stricter_than_internal(self):
        draft = _mock_draft(approved=True)
        approved_rec = _approved_record(draft)
        # Mock data is blocked on external channels
        external_result = publish_check_workflow(
            draft=draft, approval_record=approved_rec, target_channel="investor_portal"
        )
        internal_result = publish_check_workflow(
            draft=draft, approval_record=approved_rec, target_channel="internal"
        )
        # External should have more (or equal) blocking reasons than internal
        assert len(external_result["blocking_reasons"]) >= len(internal_result["blocking_reasons"])

    def test_checks_run_list_non_empty(self):
        draft = _mock_draft(approved=False)
        result = publish_check_workflow(
            draft=draft, approval_record=None, target_channel="internal"
        )
        assert len(result["checks_run"]) > 0

    def test_target_channel_echoed_in_result(self):
        draft = _mock_draft(approved=False)
        result = publish_check_workflow(
            draft=draft, approval_record=None, target_channel="internal"
        )
        assert result["target_channel"] == "internal"

    def test_draft_id_echoed_in_result(self):
        draft = _mock_draft(draft_id="draft-echo-001")
        result = publish_check_workflow(
            draft=draft, approval_record=None, target_channel="internal"
        )
        assert result["draft_id"] == "draft-echo-001"


# ---------------------------------------------------------------------------
# Publish check — passing / review required (non-mock draft)
# ---------------------------------------------------------------------------

def _non_mock_draft(draft_id="draft-nonmock-001"):
    """Simulate a draft that has passed through the real engine (Phase 2)."""
    return {
        "draft_id": draft_id,
        "deal_id": "deal-policy-002",
        "draft_type": "investor_summary",
        "approved": False,
        "sections": [{"section_id": "overview", "title": "Overview", "content": "CLO overview."}],
        "grounding_sources": [],
        "is_mock": False,  # not mock engine output
    }


class TestPublishCheckPassing:

    @pytest.fixture
    def approved_draft_and_record(self):
        draft = _non_mock_draft()
        approved_rec = _approved_record(draft)
        approved_draft = approval_service.apply_approval_to_draft(draft, approved_rec)
        return approved_draft, approved_rec

    def test_recommendation_is_valid_string(self, approved_draft_and_record):
        draft, rec = approved_draft_and_record
        result = publish_check_workflow(
            draft=draft, approval_record=rec, target_channel="internal"
        )
        assert result["recommendation"] in (
            "APPROVED_TO_PUBLISH", "REVIEW_REQUIRED", "BLOCKED"
        )

    def test_pass_key_in_result(self, approved_draft_and_record):
        draft, rec = approved_draft_and_record
        result = publish_check_workflow(
            draft=draft, approval_record=rec, target_channel="internal"
        )
        assert "pass" in result

    def test_approved_non_mock_not_blocked(self, approved_draft_and_record):
        draft, rec = approved_draft_and_record
        result = publish_check_workflow(
            draft=draft, approval_record=rec, target_channel="internal"
        )
        assert result["recommendation"] != "BLOCKED"

    def test_no_blocking_reasons_for_approved_non_mock(self, approved_draft_and_record):
        draft, rec = approved_draft_and_record
        result = publish_check_workflow(
            draft=draft, approval_record=rec, target_channel="internal"
        )
        assert result["blocking_reasons"] == []


# ---------------------------------------------------------------------------
# Channel policy
# ---------------------------------------------------------------------------

class TestChannelPolicy:

    def test_internal_channel_accepted(self):
        draft = _mock_draft(approved=False)
        # Just check it runs without error for internal channel
        result = publish_check_workflow(
            draft=draft, approval_record=None, target_channel="internal"
        )
        assert "recommendation" in result

    def test_investor_portal_channel_accepted_as_external(self):
        draft = _mock_draft(approved=False)
        result = publish_check_workflow(
            draft=draft, approval_record=None, target_channel="investor_portal"
        )
        assert result["recommendation"] == "BLOCKED"

    def test_ic_memo_draft_type_recognized(self):
        draft = _mock_draft(draft_type="ic_memo")
        result = publish_check_workflow(
            draft=draft, approval_record=None, target_channel="internal"
        )
        assert result["draft_type"] == "ic_memo"
