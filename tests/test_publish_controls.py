"""
tests/test_publish_controls.py

Tests for the Phase 9 approval and publish-control layer.

Covers:
  - approval_service: state machine correctness, immutability, error paths
  - publish_check_workflow: all 6 checks, recommendation logic, audit events
  - pre_publish_check hook: inline policy enforcement
  - Integration: full path from draft creation to approved publish check
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from app.services import approval_service
from app.workflows.publish_check_workflow import publish_check_workflow
from infra.hooks.pre_publish_check import handle as hook_handle


# ---------------------------------------------------------------------------
# Helpers — minimal fake drafts
# ---------------------------------------------------------------------------

def _make_draft(
    draft_id="draft-test-001",
    draft_type="investor_summary",
    deal_id="deal-001",
    approved=False,
    is_mock=False,
    sections=None,
):
    """Construct a minimal DraftDocument dict for testing."""
    return {
        "draft_id":   draft_id,
        "draft_type": draft_type,
        "deal_id":    deal_id,
        "approved":   approved,
        "is_mock":    is_mock,
        "requires_approval": True,
        "sections": sections or [
            {"section_id": "test", "title": "Test", "content": "No placeholders here."}
        ],
    }


def _make_draft_with_placeholders(n=3):
    content = "Text. " + " ".join(f"[PLACEHOLDER: item {i}]" for i in range(n))
    return _make_draft(sections=[{"section_id": "s1", "title": "S1", "content": content}])


def _approved_draft_and_record(channel="internal"):
    """Full happy-path setup: draft + request + approve + apply."""
    draft = _make_draft(is_mock=False)
    record = approval_service.request_approval(draft, requested_by="tester", channel=channel)
    record = approval_service.record_approval(record, approver="senior-reviewer")
    draft  = approval_service.apply_approval_to_draft(draft, record)
    return draft, record


# ---------------------------------------------------------------------------
# TestApprovalService
# ---------------------------------------------------------------------------

class TestApprovalService:

    def test_request_creates_pending_record(self):
        draft = _make_draft()
        record = approval_service.request_approval(draft, "alice")
        assert record["status"] == "pending"

    def test_request_sets_expected_fields(self):
        draft = _make_draft(draft_id="d-42", draft_type="ic_memo", deal_id="deal-99")
        record = approval_service.request_approval(draft, "bob", channel="external")
        assert record["draft_id"]   == "d-42"
        assert record["draft_type"] == "ic_memo"
        assert record["deal_id"]    == "deal-99"
        assert record["channel"]    == "external"
        assert record["requested_by"] == "bob"
        assert record["approver"]   is None
        assert record["approved_at"] is None
        assert record["rejection_reason"] is None

    def test_request_generates_unique_ids(self):
        draft = _make_draft()
        ids = {approval_service.request_approval(draft, "x")["approval_id"] for _ in range(10)}
        assert len(ids) == 10

    def test_invalid_channel_raises(self):
        draft = _make_draft()
        with pytest.raises(ValueError, match="Invalid channel"):
            approval_service.request_approval(draft, "x", channel="investor_portal_xyz")

    def test_record_approval_updates_status(self):
        draft = _make_draft()
        pending = approval_service.request_approval(draft, "alice")
        approved = approval_service.record_approval(pending, "senior-reviewer")
        assert approved["status"]   == "approved"
        assert approved["approver"] == "senior-reviewer"
        assert approved["approved_at"] is not None

    def test_record_approval_does_not_mutate_original(self):
        draft = _make_draft()
        pending = approval_service.request_approval(draft, "alice")
        _ = approval_service.record_approval(pending, "bob")
        assert pending["status"] == "pending"   # original unchanged

    def test_cannot_approve_already_approved(self):
        draft = _make_draft()
        record = approval_service.request_approval(draft, "alice")
        record = approval_service.record_approval(record, "bob")
        with pytest.raises(ValueError, match="already approved"):
            approval_service.record_approval(record, "carol")

    def test_cannot_approve_rejected_record(self):
        draft = _make_draft()
        record = approval_service.request_approval(draft, "alice")
        record = approval_service.record_rejection(record, "bob", "Not ready")
        with pytest.raises(ValueError, match="rejected"):
            approval_service.record_approval(record, "carol")

    def test_record_rejection_requires_reason(self):
        draft = _make_draft()
        record = approval_service.request_approval(draft, "alice")
        with pytest.raises(ValueError, match="rejection_reason is required"):
            approval_service.record_rejection(record, "bob", "")

    def test_record_rejection_updates_status(self):
        draft = _make_draft()
        record = approval_service.request_approval(draft, "alice")
        rejected = approval_service.record_rejection(record, "bob", "Incomplete disclosures")
        assert rejected["status"] == "rejected"
        assert rejected["rejection_reason"] == "Incomplete disclosures"
        assert rejected["approved_at"] is None

    def test_record_rejection_does_not_mutate_original(self):
        draft = _make_draft()
        pending = approval_service.request_approval(draft, "alice")
        _ = approval_service.record_rejection(pending, "bob", "reason")
        assert pending["status"] == "pending"

    def test_cannot_reject_approved_record(self):
        draft = _make_draft()
        record = approval_service.request_approval(draft, "alice")
        record = approval_service.record_approval(record, "bob")
        with pytest.raises(ValueError, match="already-approved"):
            approval_service.record_rejection(record, "carol", "too late")

    def test_apply_approval_sets_draft_approved_true(self):
        draft, record = _approved_draft_and_record()
        assert draft["approved"] is True

    def test_apply_approval_does_not_mutate_original_draft(self):
        original = _make_draft()
        record   = approval_service.request_approval(original, "alice")
        record   = approval_service.record_approval(record, "bob")
        _        = approval_service.apply_approval_to_draft(original, record)
        assert original["approved"] is False   # original unchanged

    def test_apply_approval_rejects_non_approved_record(self):
        draft  = _make_draft()
        record = approval_service.request_approval(draft, "alice")
        with pytest.raises(ValueError, match="not 'approved'"):
            approval_service.apply_approval_to_draft(draft, record)

    def test_apply_approval_rejects_mismatched_draft_id(self):
        draft_a = _make_draft(draft_id="draft-a")
        draft_b = _make_draft(draft_id="draft-b")
        record  = approval_service.request_approval(draft_a, "alice")
        record  = approval_service.record_approval(record, "bob")
        with pytest.raises(ValueError, match="does not match"):
            approval_service.apply_approval_to_draft(draft_b, record)

    def test_is_approved_true_when_approved(self):
        draft, record = _approved_draft_and_record()
        assert approval_service.is_approved(record) is True

    def test_is_approved_false_when_pending(self):
        draft  = _make_draft()
        record = approval_service.request_approval(draft, "alice")
        assert approval_service.is_approved(record) is False

    def test_is_approved_false_when_none(self):
        assert approval_service.is_approved(None) is False

    def test_get_approval_status_returns_none_for_missing_record(self):
        assert approval_service.get_approval_status(None) == "none"

    def test_get_approval_status_returns_correct_value(self):
        draft  = _make_draft()
        record = approval_service.request_approval(draft, "alice")
        assert approval_service.get_approval_status(record) == "pending"
        record = approval_service.record_approval(record, "bob")
        assert approval_service.get_approval_status(record) == "approved"


# ---------------------------------------------------------------------------
# TestPublishCheckWorkflow
# ---------------------------------------------------------------------------

class TestPublishCheckWorkflow:

    def test_mock_data_blocks_always(self):
        draft = _make_draft(is_mock=True, approved=True)
        result = publish_check_workflow(draft)
        assert result["pass"] is False
        assert result["recommendation"] == "BLOCKED"
        check = next(c for c in result["checks_run"] if c["check_id"] == "mock_data")
        assert check["pass"] is False
        assert check["severity"] == "block"

    def test_mock_data_blocks_even_with_approval_record(self):
        draft, record = _approved_draft_and_record()
        draft["is_mock"] = True   # force mock flag on an otherwise-approved draft
        result = publish_check_workflow(draft, approval_record=record)
        assert result["recommendation"] == "BLOCKED"
        assert any("mock" in r.lower() for r in result["blocking_reasons"])

    def test_unapproved_draft_blocks(self):
        draft = _make_draft(is_mock=False, approved=False)
        result = publish_check_workflow(draft)
        assert result["recommendation"] == "BLOCKED"
        check = next(c for c in result["checks_run"] if c["check_id"] == "draft_approved")
        assert check["pass"] is False

    def test_no_record_external_blocks(self):
        draft, _ = _approved_draft_and_record(channel="external")
        # approved draft but no record passed in
        result = publish_check_workflow(draft, approval_record=None, target_channel="external")
        assert result["recommendation"] == "BLOCKED"

    def test_no_record_internal_warns_not_blocks(self):
        draft, _ = _approved_draft_and_record(channel="internal")
        result = publish_check_workflow(draft, approval_record=None, target_channel="internal")
        check = next(c for c in result["checks_run"] if c["check_id"] == "approval_record")
        assert check["severity"] == "warn"
        assert check["pass"] is False
        # Not a blocking failure
        assert result["recommendation"] != "BLOCKED"

    def test_pending_record_blocks(self):
        draft  = _make_draft(is_mock=False, approved=False)
        record = approval_service.request_approval(draft, "alice")
        # record is pending, draft is not approved
        result = publish_check_workflow(draft, approval_record=record)
        assert result["recommendation"] == "BLOCKED"

    def test_rejected_record_blocks(self):
        draft = _make_draft(is_mock=False)
        record = approval_service.request_approval(draft, "alice")
        record = approval_service.record_rejection(record, "bob", "Incomplete")
        result = publish_check_workflow(draft, approval_record=record)
        assert result["recommendation"] == "BLOCKED"
        assert any("rejected" in r for r in result["blocking_reasons"])

    def test_external_channel_requires_external_scoped_record(self):
        draft, internal_record = _approved_draft_and_record(channel="internal")
        # Try to publish externally with an internal-channel approval record
        result = publish_check_workflow(
            draft, approval_record=internal_record, target_channel="external"
        )
        assert result["recommendation"] == "BLOCKED"
        check = next(c for c in result["checks_run"] if c["check_id"] == "channel_policy")
        assert check["pass"] is False

    def test_draft_id_mismatch_blocks(self):
        draft_a = _make_draft(draft_id="draft-a", is_mock=False)
        draft_b = _make_draft(draft_id="draft-b", is_mock=False)
        record  = approval_service.request_approval(draft_a, "alice")
        record  = approval_service.record_approval(record, "bob")
        draft_a = approval_service.apply_approval_to_draft(draft_a, record)
        # Check draft_b against draft_a's record — should block
        result = publish_check_workflow(draft_b, approval_record=record)
        check = next(c for c in result["checks_run"] if c["check_id"] == "draft_id_match")
        assert check["pass"] is False

    def test_placeholders_produce_warnings_not_blocks(self):
        draft, record = _approved_draft_and_record()
        draft["sections"] = [
            {"section_id": "s1", "content": "[PLACEHOLDER: insert disclosure]"}
        ]
        result = publish_check_workflow(draft, approval_record=record, target_channel="internal")
        check = next(c for c in result["checks_run"] if c["check_id"] == "placeholder_scan")
        assert check["severity"] == "warn"
        assert check["pass"] is False
        assert "1" in check["reason"]   # count reported

    def test_no_placeholders_passes_scan(self):
        draft, record = _approved_draft_and_record()
        result = publish_check_workflow(draft, approval_record=record)
        check = next(c for c in result["checks_run"] if c["check_id"] == "placeholder_scan")
        assert check["pass"] is True

    def test_review_required_when_only_warnings(self):
        draft, _ = _approved_draft_and_record(channel="internal")
        # Internal channel, no record → warning only
        result = publish_check_workflow(draft, approval_record=None, target_channel="internal")
        assert result["recommendation"] == "REVIEW_REQUIRED"
        assert result["pass"] is False

    def test_approved_to_publish_when_all_pass(self):
        draft, record = _approved_draft_and_record(channel="internal")
        result = publish_check_workflow(
            draft, approval_record=record, target_channel="internal"
        )
        assert result["recommendation"] == "APPROVED_TO_PUBLISH"
        assert result["pass"] is True

    def test_approved_to_publish_external_channel(self):
        draft, record = _approved_draft_and_record(channel="external")
        result = publish_check_workflow(
            draft, approval_record=record, target_channel="external"
        )
        assert result["recommendation"] == "APPROVED_TO_PUBLISH"
        assert result["pass"] is True

    def test_emits_one_audit_event(self):
        draft = _make_draft()
        result = publish_check_workflow(draft)
        assert len(result["audit_events"]) == 1
        assert result["audit_events"][0]["event_type"] == "publish_check.run"

    def test_audit_event_contains_recommendation(self):
        draft = _make_draft(is_mock=True)
        result = publish_check_workflow(draft)
        payload = result["audit_events"][0]["payload"]
        assert payload["recommendation"] == "BLOCKED"

    def test_result_includes_all_check_ids(self):
        draft = _make_draft()
        result = publish_check_workflow(draft)
        check_ids = {c["check_id"] for c in result["checks_run"]}
        expected = {"mock_data", "draft_approved", "approval_record",
                    "channel_policy", "draft_id_match", "approval_expiry", "placeholder_scan"}
        assert expected == check_ids

    def test_blocking_reasons_populated_on_failure(self):
        draft = _make_draft(is_mock=True, approved=False)
        result = publish_check_workflow(draft)
        assert len(result["blocking_reasons"]) >= 2   # mock + unapproved

    # --- Expiry checks ---

    def test_no_expiry_on_record_passes(self):
        draft, record = _approved_draft_and_record()
        # record has no expires_at by default
        result = publish_check_workflow(draft, approval_record=record)
        expiry = next(c for c in result["checks_run"] if c["check_id"] == "approval_expiry")
        assert expiry["pass"] is True

    def test_future_expiry_passes(self):
        draft, record = _approved_draft_and_record()
        record = {**record, "expires_at": "2099-12-31T23:59:59+00:00"}
        result = publish_check_workflow(draft, approval_record=record)
        expiry = next(c for c in result["checks_run"] if c["check_id"] == "approval_expiry")
        assert expiry["pass"] is True

    def test_past_expiry_blocks(self):
        draft, record = _approved_draft_and_record()
        record = {**record, "expires_at": "2000-01-01T00:00:00+00:00"}
        result = publish_check_workflow(draft, approval_record=record)
        expiry = next(c for c in result["checks_run"] if c["check_id"] == "approval_expiry")
        assert expiry["pass"] is False
        assert result["recommendation"] == "BLOCKED"

    def test_expired_approval_blocks_otherwise_clean_draft(self):
        """Expired record must block even if all other checks pass."""
        draft, record = _approved_draft_and_record(channel="internal")
        record = {**record, "expires_at": "2000-01-01T00:00:00+00:00"}
        result = publish_check_workflow(draft, approval_record=record, target_channel="internal")
        assert result["recommendation"] == "BLOCKED"
        assert any("expired" in r.lower() for r in result["blocking_reasons"])

    def test_unparseable_expiry_blocks(self):
        draft, record = _approved_draft_and_record()
        record = {**record, "expires_at": "not-a-date"}
        result = publish_check_workflow(draft, approval_record=record)
        expiry = next(c for c in result["checks_run"] if c["check_id"] == "approval_expiry")
        assert expiry["pass"] is False

    def test_no_record_expiry_check_passes(self):
        """When there is no approval record the expiry check is not applicable."""
        draft = _make_draft()
        result = publish_check_workflow(draft, approval_record=None)
        expiry = next(c for c in result["checks_run"] if c["check_id"] == "approval_expiry")
        assert expiry["pass"] is True


# ---------------------------------------------------------------------------
# TestPrePublishHook
# ---------------------------------------------------------------------------

class TestPrePublishHook:

    def test_non_publish_tool_allowed(self):
        event = {"tool": "read_file", "inputs": {}}
        result = hook_handle(event)
        assert result["action"] == "allow"

    def test_publish_with_mock_data_blocked(self):
        event = {
            "tool": "publish_artifact",
            "inputs": {
                "is_mock": True,
                "approval_status": "approved",
                "draft_approved": True,
            },
        }
        result = hook_handle(event)
        assert result["action"] == "block"
        assert "mock" in result["reason"].lower()

    def test_publish_without_approval_blocked(self):
        event = {
            "tool": "publish_artifact",
            "inputs": {
                "is_mock": False,
                "approval_status": "pending",
                "draft_approved": False,
            },
        }
        result = hook_handle(event)
        assert result["action"] == "block"

    def test_external_without_approval_id_blocked(self):
        event = {
            "tool": "send_to_portal",
            "inputs": {
                "is_mock": False,
                "draft_approved": True,
                "approval_status": "approved",
                "target_channel": "external",
                # no approval_id
            },
        }
        result = hook_handle(event)
        assert result["action"] == "block"
        assert "external" in result["reason"].lower()

    def test_fully_valid_internal_publish_allowed(self):
        event = {
            "tool": "publish_artifact",
            "inputs": {
                "is_mock": False,
                "draft_approved": True,
                "approval_status": "approved",
                "target_channel": "internal",
            },
        }
        result = hook_handle(event)
        assert result["action"] == "allow"

    def test_fully_valid_external_publish_allowed(self):
        event = {
            "tool": "distribute_document",
            "inputs": {
                "is_mock": False,
                "draft_approved": True,
                "approval_status": "approved",
                "target_channel": "external",
                "approval_id": "appr-abc123",
            },
        }
        result = hook_handle(event)
        assert result["action"] == "allow"

    def test_hook_returns_checks_list(self):
        event = {
            "tool": "publish_artifact",
            "inputs": {"is_mock": True},
        }
        result = hook_handle(event)
        assert "checks" in result
        assert isinstance(result["checks"], list)
        assert len(result["checks"]) > 0


# ---------------------------------------------------------------------------
# Integration: full path from draft creation to approved publish check
# ---------------------------------------------------------------------------

class TestIntegrationPublishFlow:

    def test_full_internal_approval_path(self):
        """
        Happy path: create draft → request approval → approve → apply → publish check.
        """
        # 1. Simulated draft from drafting_service (always approved=False at creation)
        draft = _make_draft(is_mock=False)
        assert draft["approved"] is False

        # 2. Request approval
        record = approval_service.request_approval(draft, requested_by="alice", channel="internal")
        assert record["status"] == "pending"

        # 3. Human approves (in Phase 3+: via entitlement-mcp)
        record = approval_service.record_approval(record, approver="senior-reviewer", notes="LGTM")
        assert record["status"] == "approved"

        # 4. Apply approval to draft
        approved_draft = approval_service.apply_approval_to_draft(draft, record)
        assert approved_draft["approved"] is True
        assert draft["approved"] is False   # original unchanged

        # 5. Publish check
        result = publish_check_workflow(approved_draft, approval_record=record, target_channel="internal")
        assert result["recommendation"] == "APPROVED_TO_PUBLISH"
        assert result["pass"] is True

    def test_full_external_approval_path(self):
        """
        External distribution requires external-channel approval record.
        """
        draft = _make_draft(is_mock=False, draft_type="investor_summary")
        record = approval_service.request_approval(draft, "alice", channel="external")
        record = approval_service.record_approval(record, "compliance-officer")
        approved_draft = approval_service.apply_approval_to_draft(draft, record)
        result = publish_check_workflow(approved_draft, approval_record=record, target_channel="external")
        assert result["recommendation"] == "APPROVED_TO_PUBLISH"

    def test_rejection_then_re_request_path(self):
        """
        After rejection, a new approval request can be created and approved.
        """
        draft  = _make_draft(is_mock=False)
        record = approval_service.request_approval(draft, "alice")
        record = approval_service.record_rejection(record, "bob", "Placeholders not resolved")
        assert record["status"] == "rejected"

        # Cannot approve the rejected record
        with pytest.raises(ValueError):
            approval_service.record_approval(record, "carol")

        # Create a new request
        record2 = approval_service.request_approval(draft, "alice")
        record2 = approval_service.record_approval(record2, "carol")
        approved_draft = approval_service.apply_approval_to_draft(draft, record2)
        result = publish_check_workflow(approved_draft, approval_record=record2)
        assert result["recommendation"] == "APPROVED_TO_PUBLISH"

    def test_mock_draft_never_passes_even_after_approval(self):
        """
        A draft built on mock engine outputs must always be blocked,
        even if it somehow has approved=True and a valid approval record.
        """
        draft = _make_draft(is_mock=True)
        record = approval_service.request_approval(draft, "alice")
        record = approval_service.record_approval(record, "bob")
        # Force approved=True to simulate a hypothetical bypass
        forced_draft = {**draft, "approved": True}
        result = publish_check_workflow(forced_draft, approval_record=record)
        assert result["recommendation"] == "BLOCKED"
        assert any("mock" in r.lower() for r in result["blocking_reasons"])
