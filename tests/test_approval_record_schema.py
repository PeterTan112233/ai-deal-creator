"""
tests/test_approval_record_schema.py

Tests that approval records produced by approval_service conform to
app/schemas/approval_record.schema.json.

These tests verify the service/schema contract that was misaligned before
Phase 12 (Issues 1 & 2 in evaluation-plan.md). If any test here fails,
it means the service and schema have drifted again.

Validation approach:
  We validate field presence, types, and enum values directly, matching
  the JSON schema contract without requiring the jsonschema library.
  The JSON schema is also loaded and inspected to keep the two in sync.
"""

import json
import os
import pytest
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services import approval_service

# ---------------------------------------------------------------------------
# Load the JSON schema for inspection
# ---------------------------------------------------------------------------

_SCHEMA_PATH = os.path.join(
    os.path.dirname(__file__), "..", "app", "schemas", "approval_record.schema.json"
)

with open(_SCHEMA_PATH) as f:
    _SCHEMA = json.load(f)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_draft(draft_type="investor_summary"):
    return {
        "draft_id": "draft-abc123",
        "deal_id":  "deal-001",
        "draft_type": draft_type,
        "approved": False,
    }


def _required_fields():
    return set(_SCHEMA["required"])


def _enum_values(field: str):
    return _SCHEMA["properties"][field].get("enum", [])


# ---------------------------------------------------------------------------
# Schema structure tests (schema is self-consistent)
# ---------------------------------------------------------------------------

class TestSchemaStructure:

    def test_required_fields_defined(self):
        required = _required_fields()
        assert "approval_id" in required
        assert "deal_id" in required
        assert "draft_id" in required
        assert "draft_type" in required
        assert "channel" in required
        assert "status" in required

    def test_no_legacy_target_fields(self):
        """target_type and target_id must not appear in the schema."""
        assert "target_type" not in _SCHEMA["properties"]
        assert "target_id" not in _SCHEMA["properties"]

    def test_channel_enum_values(self):
        allowed = set(_enum_values("channel"))
        assert "internal" in allowed
        assert "external" in allowed
        assert "investor_portal" not in allowed, \
            "investor_portal was removed from channel enum — service rejects it"

    def test_status_enum_values(self):
        allowed = set(_enum_values("status"))
        assert {"pending", "approved", "rejected"} == allowed

    def test_draft_type_enum_values(self):
        allowed = set(_enum_values("draft_type"))
        assert "investor_summary" in allowed
        assert "ic_memo" in allowed

    def test_rejected_at_field_present(self):
        assert "rejected_at" in _SCHEMA["properties"], \
            "rejected_at must be in schema — approval_service.record_rejection() writes it"

    def test_additional_properties_false(self):
        assert _SCHEMA.get("additionalProperties") is False


# ---------------------------------------------------------------------------
# request_approval — pending record
# ---------------------------------------------------------------------------

class TestRequestApproval:

    def test_has_all_required_fields(self):
        draft = _make_draft()
        record = approval_service.request_approval(draft, requested_by="analyst-1")
        for field in _required_fields():
            assert field in record, f"Missing required field: {field}"

    def test_status_is_pending(self):
        draft = _make_draft()
        record = approval_service.request_approval(draft, requested_by="analyst-1")
        assert record["status"] == "pending"
        assert record["status"] in _enum_values("status")

    def test_channel_is_valid_enum(self):
        draft = _make_draft()
        record = approval_service.request_approval(draft, requested_by="analyst-1", channel="internal")
        assert record["channel"] in _enum_values("channel")

    def test_external_channel_valid(self):
        draft = _make_draft()
        record = approval_service.request_approval(draft, requested_by="analyst-1", channel="external")
        assert record["channel"] == "external"
        assert record["channel"] in _enum_values("channel")

    def test_investor_portal_channel_rejected(self):
        draft = _make_draft()
        with pytest.raises(ValueError, match="Invalid channel"):
            approval_service.request_approval(draft, requested_by="analyst-1", channel="investor_portal")

    def test_draft_id_propagated(self):
        draft = _make_draft()
        record = approval_service.request_approval(draft, requested_by="analyst-1")
        assert record["draft_id"] == "draft-abc123"

    def test_draft_type_propagated(self):
        draft = _make_draft(draft_type="ic_memo")
        record = approval_service.request_approval(draft, requested_by="analyst-1")
        assert record["draft_type"] == "ic_memo"
        assert record["draft_type"] in _enum_values("draft_type")

    def test_deal_id_propagated(self):
        draft = _make_draft()
        record = approval_service.request_approval(draft, requested_by="analyst-1")
        assert record["deal_id"] == "deal-001"

    def test_no_extra_fields(self):
        """Service must not add fields not in the schema properties."""
        draft = _make_draft()
        record = approval_service.request_approval(draft, requested_by="analyst-1")
        allowed = set(_SCHEMA["properties"].keys())
        extra = set(record.keys()) - allowed
        assert not extra, f"Service produced fields not in schema: {extra}"


# ---------------------------------------------------------------------------
# record_approval — approved record
# ---------------------------------------------------------------------------

class TestRecordApproval:

    def test_status_becomes_approved(self):
        draft = _make_draft()
        pending = approval_service.request_approval(draft, requested_by="analyst-1")
        approved = approval_service.record_approval(pending, approver="approver-1")
        assert approved["status"] == "approved"
        assert approved["status"] in _enum_values("status")

    def test_approver_set(self):
        draft = _make_draft()
        pending = approval_service.request_approval(draft, requested_by="analyst-1")
        approved = approval_service.record_approval(pending, approver="approver-1")
        assert approved["approver"] == "approver-1"

    def test_approved_at_set(self):
        draft = _make_draft()
        pending = approval_service.request_approval(draft, requested_by="analyst-1")
        approved = approval_service.record_approval(pending, approver="approver-1")
        assert approved["approved_at"] is not None

    def test_no_extra_fields(self):
        draft = _make_draft()
        pending = approval_service.request_approval(draft, requested_by="analyst-1")
        approved = approval_service.record_approval(pending, approver="approver-1")
        allowed = set(_SCHEMA["properties"].keys())
        extra = set(approved.keys()) - allowed
        assert not extra, f"Approved record has fields not in schema: {extra}"

    def test_all_required_fields_present(self):
        draft = _make_draft()
        pending = approval_service.request_approval(draft, requested_by="analyst-1")
        approved = approval_service.record_approval(pending, approver="approver-1")
        for field in _required_fields():
            assert field in approved


# ---------------------------------------------------------------------------
# record_rejection — rejected record
# ---------------------------------------------------------------------------

class TestRecordRejection:

    def test_status_becomes_rejected(self):
        draft = _make_draft()
        pending = approval_service.request_approval(draft, requested_by="analyst-1")
        rejected = approval_service.record_rejection(pending, approver="approver-1", rejection_reason="Needs revision")
        assert rejected["status"] == "rejected"
        assert rejected["status"] in _enum_values("status")

    def test_rejected_at_set(self):
        draft = _make_draft()
        pending = approval_service.request_approval(draft, requested_by="analyst-1")
        rejected = approval_service.record_rejection(pending, approver="approver-1", rejection_reason="Needs revision")
        assert rejected["rejected_at"] is not None

    def test_rejection_reason_set(self):
        draft = _make_draft()
        pending = approval_service.request_approval(draft, requested_by="analyst-1")
        rejected = approval_service.record_rejection(pending, approver="approver-1", rejection_reason="Missing disclosures")
        assert rejected["rejection_reason"] == "Missing disclosures"

    def test_no_extra_fields(self):
        draft = _make_draft()
        pending = approval_service.request_approval(draft, requested_by="analyst-1")
        rejected = approval_service.record_rejection(pending, approver="approver-1", rejection_reason="Needs revision")
        allowed = set(_SCHEMA["properties"].keys())
        extra = set(rejected.keys()) - allowed
        assert not extra, f"Rejected record has fields not in schema: {extra}"

    def test_schema_if_then_rejection_reason_required(self):
        """The JSON schema if/then rule: rejected status requires rejection_reason."""
        draft = _make_draft()
        pending = approval_service.request_approval(draft, requested_by="analyst-1")
        with pytest.raises(ValueError, match="rejection_reason is required"):
            approval_service.record_rejection(pending, approver="approver-1", rejection_reason="")

    def test_approved_at_null_on_rejection(self):
        draft = _make_draft()
        pending = approval_service.request_approval(draft, requested_by="analyst-1")
        rejected = approval_service.record_rejection(pending, approver="approver-1", rejection_reason="Needs revision")
        assert rejected["approved_at"] is None


# ---------------------------------------------------------------------------
# State machine invariants
# ---------------------------------------------------------------------------

class TestStateMachineInvariants:

    def test_cannot_approve_already_approved(self):
        draft = _make_draft()
        pending = approval_service.request_approval(draft, requested_by="analyst-1")
        approved = approval_service.record_approval(pending, approver="approver-1")
        with pytest.raises(ValueError, match="already approved"):
            approval_service.record_approval(approved, approver="approver-2")

    def test_cannot_approve_rejected_record(self):
        draft = _make_draft()
        pending = approval_service.request_approval(draft, requested_by="analyst-1")
        rejected = approval_service.record_rejection(pending, approver="approver-1", rejection_reason="Too risky")
        with pytest.raises(ValueError, match="rejected"):
            approval_service.record_approval(rejected, approver="approver-2")

    def test_cannot_reject_approved_record(self):
        draft = _make_draft()
        pending = approval_service.request_approval(draft, requested_by="analyst-1")
        approved = approval_service.record_approval(pending, approver="approver-1")
        with pytest.raises(ValueError, match="approved"):
            approval_service.record_rejection(approved, approver="approver-2", rejection_reason="Changed mind")

    def test_immutability_request_approval(self):
        """request_approval must not mutate the draft."""
        draft = _make_draft()
        original_keys = set(draft.keys())
        approval_service.request_approval(draft, requested_by="analyst-1")
        assert set(draft.keys()) == original_keys

    def test_immutability_record_approval(self):
        """record_approval must not mutate the input record."""
        draft = _make_draft()
        pending = approval_service.request_approval(draft, requested_by="analyst-1")
        original_status = pending["status"]
        approval_service.record_approval(pending, approver="approver-1")
        assert pending["status"] == original_status
