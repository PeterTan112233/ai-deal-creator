"""
app/services/approval_service.py

Models the approval lifecycle for deal drafts.

DESIGN PRINCIPLES
  - Approval records are immutable after creation: record_approval() and
    record_rejection() return NEW dicts, never mutate the input.
  - apply_approval_to_draft() is the ONLY path by which a draft's approved
    flag can become True. Both a valid approval record AND a draft are required.
  - This service never performs entitlement checks — it assumes the caller
    is authorised to request or record approval. Phase 3+: add entitlement
    check via entitlement-mcp.verify_approver_role().

APPROVAL STATE MACHINE
  [created] → pending ──────→ approved
                        ↘── rejected
  Transitions are one-way. A rejected record cannot be approved.
  An approved record cannot be rejected.
  To re-open: create a new request via request_approval().

WHAT THIS SERVICE DOES NOT DO
  - Notify approvers (Phase 3+: notification-mcp)
  - Persist approval records (Phase 3+: approval-store-mcp)
  - Verify approver identity or entitlement (Phase 3+: entitlement-mcp)
  - Set draft.approved=True directly (use apply_approval_to_draft())
"""

from datetime import datetime, timezone
from typing import Dict, Optional
import uuid


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def request_approval(
    draft: Dict,
    requested_by: str,
    channel: str = "internal",
) -> Dict:
    """
    Create a pending approval record for a draft.

    Parameters
    ----------
    draft        : DraftDocument dict (from drafting_service / workflow).
    requested_by : Identifier of the person or agent requesting approval.
    channel      : Target distribution channel — "internal" or "external".

    Returns a new approval record dict with status="pending".
    Phase 3+: persist via approval-store-mcp.create_request()
    """
    _validate_channel(channel)
    now = datetime.now(timezone.utc)
    return {
        "approval_id":    f"appr-{uuid.uuid4().hex[:8]}",
        "draft_id":       draft.get("draft_id", "unknown"),
        "deal_id":        draft.get("deal_id", "unknown"),
        "draft_type":     draft.get("draft_type", "unknown"),
        "channel":        channel,
        "status":         "pending",
        "requested_by":   requested_by,
        "requested_at":   now.isoformat(),
        "approver":       None,
        "approved_at":    None,
        "rejection_reason": None,
        "notes":          None,
    }


def record_approval(
    approval_record: Dict,
    approver: str,
    notes: Optional[str] = None,
) -> Dict:
    """
    Return a new approval record with status="approved".

    Does NOT mutate the input (append-only design).
    A rejected record cannot be approved — create a new request instead.

    Phase 3+: replace with entitlement-mcp.verify_and_record_approval()
    """
    status = approval_record.get("status")
    if status == "approved":
        raise ValueError(
            f"Record {approval_record.get('approval_id')} is already approved."
        )
    if status == "rejected":
        raise ValueError(
            f"Cannot approve a rejected record ({approval_record.get('approval_id')}). "
            "Create a new approval request via request_approval()."
        )
    now = datetime.now(timezone.utc)
    return {
        **approval_record,
        "status":      "approved",
        "approver":    approver,
        "approved_at": now.isoformat(),
        "notes":       notes or approval_record.get("notes"),
    }


def record_rejection(
    approval_record: Dict,
    approver: str,
    rejection_reason: str,
) -> Dict:
    """
    Return a new approval record with status="rejected".

    rejection_reason is required.
    Does NOT mutate the input (append-only design).
    An already-approved record cannot be rejected.

    Phase 3+: replace with entitlement-mcp.record_rejection()
    """
    if not rejection_reason or not rejection_reason.strip():
        raise ValueError("rejection_reason is required when rejecting an approval request.")
    status = approval_record.get("status")
    if status == "approved":
        raise ValueError(
            f"Cannot reject an already-approved record ({approval_record.get('approval_id')})."
        )
    now = datetime.now(timezone.utc)
    return {
        **approval_record,
        "status":           "rejected",
        "approver":         approver,
        "approved_at":      None,
        "rejection_reason": rejection_reason,
        "rejected_at":      now.isoformat(),
    }


def apply_approval_to_draft(draft: Dict, approval_record: Dict) -> Dict:
    """
    Return a new draft dict with approved=True.

    This is the ONLY authorised path by which draft.approved can become True.
    Requires:
      - An approval record with status="approved"
      - The approval record's draft_id matches the draft's draft_id

    Does NOT mutate the input draft.
    Phase 3+: replace with approval-store-mcp.stamp_draft(draft_id, approval_id)
    """
    if not is_approved(approval_record):
        raise ValueError(
            f"Cannot apply approval: record status is "
            f"'{approval_record.get('status')}', not 'approved'."
        )
    record_draft_id = approval_record.get("draft_id")
    this_draft_id   = draft.get("draft_id")
    if record_draft_id != this_draft_id:
        raise ValueError(
            f"Approval record draft_id '{record_draft_id}' "
            f"does not match draft draft_id '{this_draft_id}'."
        )
    return {**draft, "approved": True}


def is_approved(approval_record: Optional[Dict]) -> bool:
    """True only if the approval record has status='approved'."""
    if not approval_record:
        return False
    return approval_record.get("status") == "approved"


def get_approval_status(approval_record: Optional[Dict]) -> str:
    """Returns: 'pending' | 'approved' | 'rejected' | 'none'."""
    if not approval_record:
        return "none"
    return approval_record.get("status", "unknown")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _validate_channel(channel: str) -> None:
    allowed = {"internal", "external"}
    if channel not in allowed:
        raise ValueError(
            f"Invalid channel '{channel}'. Allowed values: {sorted(allowed)}"
        )
