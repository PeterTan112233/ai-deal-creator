"""
app/workflows/publish_check_workflow.py

Runs a structured publish-readiness gate on a draft document.

CHECKS (in order)
  1. mock_data         — BLOCK if draft is based on mock engine outputs
  2. draft_approved    — BLOCK if draft.approved is not True
  3. approval_record   — BLOCK (external) / WARN (internal) if no approval record,
                         or if record status is not "approved"
  4. channel_policy    — BLOCK if external channel requires external-scoped record
  5. draft_id_match    — BLOCK if approval record draft_id does not match draft
  6. placeholder_scan  — WARN if unresolved [PLACEHOLDER: ...] markers exist in sections

RECOMMENDATIONS
  BLOCKED           — one or more blocking checks failed; publish must not proceed
  REVIEW_REQUIRED   — all blocking checks passed but warnings require human sign-off
  APPROVED_TO_PUBLISH — all checks passed; publish may proceed if destination is available

IMPORTANT
  APPROVED_TO_PUBLISH means the governance gate is satisfied.
  It does NOT trigger any actual publication — there is no publish destination in Phase 1.
  Phase 2+: wire to distribution-mcp.publish() after a APPROVED_TO_PUBLISH result.

Audit events emitted:
  publish_check.run — always emitted, includes full check results
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional

from app.services import approval_service
from app.services.audit_logger import record_event


# ---------------------------------------------------------------------------
# Check severity constants
# ---------------------------------------------------------------------------

BLOCK = "block"
WARN  = "warn"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def publish_check_workflow(
    draft: Dict,
    approval_record: Optional[Dict] = None,
    target_channel: str = "internal",
    actor: str = "system",
) -> Dict:
    """
    Run all publish-readiness checks on a draft.

    Parameters
    ----------
    draft           : DraftDocument dict (from drafting_service or post-approval).
    approval_record : Optional approval record dict (from approval_service).
                      Required for external channel; recommended for internal.
    target_channel  : "internal" or "external".
    actor           : Identifies the caller in audit events.

    Returns
    -------
    {
        pass:               bool
        recommendation:     "APPROVED_TO_PUBLISH" | "BLOCKED" | "REVIEW_REQUIRED"
        checks_run:         list of check result dicts
        blocking_reasons:   list of str — reasons for any blocking failures
        warnings:           list of str — non-blocking concerns
        draft_id:           str
        draft_type:         str
        target_channel:     str
        audit_events:       list
    }
    """
    deal_id    = draft.get("deal_id", "unknown")
    draft_id   = draft.get("draft_id", "unknown")
    draft_type = draft.get("draft_type", "unknown")

    checks_run: List[Dict] = []

    # Run all checks in order
    checks_run.append(_check_mock_data(draft))
    checks_run.append(_check_draft_approved(draft))
    checks_run.append(_check_approval_record(draft, approval_record, target_channel))
    checks_run.append(_check_channel_policy(approval_record, target_channel))
    checks_run.append(_check_draft_id_match(draft, approval_record))
    checks_run.append(_check_approval_expiry(approval_record))
    checks_run.append(_check_placeholders(draft))

    # Aggregate results
    blocking = [c for c in checks_run if c["severity"] == BLOCK and not c["pass"]]
    warnings = [c for c in checks_run if c["severity"] == WARN  and not c["pass"]]

    overall_pass   = len(blocking) == 0 and len(warnings) == 0
    blocking_reasons = [c["reason"] for c in blocking]
    warning_messages = [c["reason"] for c in warnings]

    if blocking:
        recommendation = "BLOCKED"
    elif warnings:
        recommendation = "REVIEW_REQUIRED"
    else:
        recommendation = "APPROVED_TO_PUBLISH"

    audit_events = [
        record_event(
            event_type="publish_check.run",
            deal_id=deal_id,
            payload={
                "draft_id":       draft_id,
                "draft_type":     draft_type,
                "target_channel": target_channel,
                "recommendation": recommendation,
                "pass":           overall_pass,
                "blocking_count": len(blocking),
                "warning_count":  len(warnings),
                "blocking_reasons": blocking_reasons,
            },
            actor=actor,
        )
    ]

    return {
        "pass":             overall_pass,
        "recommendation":   recommendation,
        "checks_run":       checks_run,
        "blocking_reasons": blocking_reasons,
        "warnings":         warning_messages,
        "draft_id":         draft_id,
        "draft_type":       draft_type,
        "target_channel":   target_channel,
        "audit_events":     audit_events,
    }


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------

def _check_mock_data(draft: Dict) -> Dict:
    """
    BLOCK if the draft is based on mock engine outputs.
    Mock data must never be published under any channel.
    """
    is_mock = draft.get("is_mock", False)
    if is_mock:
        return _make_check(
            "mock_data", BLOCK, False,
            "Draft is based on mock engine outputs. "
            "Mock data cannot be published under any channel. "
            "Replace model_engine_service with the real cashflow engine (Phase 2+)."
        )
    return _make_check("mock_data", BLOCK, True, "Draft uses official engine outputs.")


def _check_draft_approved(draft: Dict) -> Dict:
    """
    BLOCK if draft.approved is not True.
    approved=True can only be set via approval_service.apply_approval_to_draft().
    """
    approved = draft.get("approved", False)
    if not approved:
        return _make_check(
            "draft_approved", BLOCK, False,
            "Draft approval flag is False. "
            "The draft must be approved via approval_service.apply_approval_to_draft() "
            "before a publish check can pass."
        )
    return _make_check("draft_approved", BLOCK, True, "Draft approval flag is True.")


def _check_approval_record(
    draft: Dict, approval_record: Optional[Dict], target_channel: str
) -> Dict:
    """
    BLOCK (external) or WARN (internal) if no approval record is provided.
    BLOCK if the approval record status is not "approved".
    """
    if approval_record is None:
        if target_channel == "external":
            return _make_check(
                "approval_record", BLOCK, False,
                f"External channel requires a formal approval record. No record provided."
            )
        else:
            return _make_check(
                "approval_record", WARN, False,
                "Internal distribution without an approval record. "
                "Recommend requesting and obtaining approval via approval_service."
            )

    status = approval_record.get("status", "unknown")
    if status != "approved":
        return _make_check(
            "approval_record", BLOCK, False,
            f"Approval record status is '{status}', not 'approved'. "
            f"Record: {approval_record.get('approval_id', 'unknown')}."
        )
    return _make_check(
        "approval_record", BLOCK, True,
        f"Approval record {approval_record.get('approval_id')} has status 'approved'."
    )


def _check_channel_policy(
    approval_record: Optional[Dict], target_channel: str
) -> Dict:
    """
    BLOCK if distributing externally with an approval record scoped only to internal.
    An internal-channel approval record does not cover external distribution.
    """
    if target_channel != "external":
        return _make_check(
            "channel_policy", BLOCK, True,
            "Internal channel — no external channel-scope requirement."
        )
    if approval_record is None:
        # Already caught by approval_record check; skip here to avoid duplicate block
        return _make_check(
            "channel_policy", BLOCK, True,
            "No record provided — channel policy not evaluated (covered by approval_record check)."
        )
    record_channel = approval_record.get("channel", "")
    if record_channel != "external":
        return _make_check(
            "channel_policy", BLOCK, False,
            f"External distribution requires an approval record with channel='external'. "
            f"This record has channel='{record_channel}'."
        )
    return _make_check(
        "channel_policy", BLOCK, True,
        f"Approval record channel is 'external' — matches target channel."
    )


def _check_draft_id_match(draft: Dict, approval_record: Optional[Dict]) -> Dict:
    """
    BLOCK if the approval record's draft_id does not match the draft being checked.
    Ensures the approval record was issued for this specific draft.
    """
    if approval_record is None:
        return _make_check(
            "draft_id_match", BLOCK, True,
            "No approval record provided — draft ID match not evaluated."
        )
    record_draft_id = approval_record.get("draft_id")
    this_draft_id   = draft.get("draft_id")
    if record_draft_id != this_draft_id:
        return _make_check(
            "draft_id_match", BLOCK, False,
            f"Approval record draft_id '{record_draft_id}' does not match "
            f"draft draft_id '{this_draft_id}'. "
            "The approval record was not issued for this draft."
        )
    return _make_check(
        "draft_id_match", BLOCK, True,
        f"Approval record draft_id matches draft draft_id '{this_draft_id}'."
    )


def _check_approval_expiry(approval_record: Optional[Dict]) -> Dict:
    """
    BLOCK if the approval record has an expires_at timestamp that is in the past.
    An expired approval is no longer valid — a fresh approval must be requested.
    Records with expires_at=None never expire.
    """
    if approval_record is None:
        return _make_check(
            "approval_expiry", BLOCK, True,
            "No approval record — expiry check not applicable."
        )
    expires_at_raw = approval_record.get("expires_at")
    if expires_at_raw is None:
        return _make_check(
            "approval_expiry", BLOCK, True,
            "Approval record has no expiry — valid indefinitely."
        )
    try:
        if isinstance(expires_at_raw, str):
            expires_at = datetime.fromisoformat(expires_at_raw)
        else:
            expires_at = expires_at_raw
        # Ensure timezone-aware comparison
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) > expires_at:
            return _make_check(
                "approval_expiry", BLOCK, False,
                f"Approval record {approval_record.get('approval_id', 'unknown')} "
                f"expired at {expires_at_raw}. Request a fresh approval."
            )
    except (ValueError, TypeError) as exc:
        return _make_check(
            "approval_expiry", BLOCK, False,
            f"Could not parse approval expires_at value '{expires_at_raw}': {exc}. "
            "Treat as expired — request a fresh approval."
        )
    return _make_check(
        "approval_expiry", BLOCK, True,
        f"Approval record is within its validity period (expires: {expires_at_raw})."
    )


def _check_placeholders(draft: Dict) -> Dict:
    """
    WARN if the draft contains unresolved [PLACEHOLDER: ...] markers.
    Placeholder markers indicate content gaps that require human input before distribution.
    This is a warning, not a block — placeholders may be acceptable for review copies.
    """
    sections = draft.get("sections", [])
    count = sum(
        section.get("content", "").count("[PLACEHOLDER:")
        for section in sections
    )
    if count > 0:
        return _make_check(
            "placeholder_scan", WARN, False,
            f"Draft contains {count} unresolved [PLACEHOLDER: ...] marker(s). "
            "Each placeholder requires human-drafted content before external distribution."
        )
    return _make_check(
        "placeholder_scan", WARN, True,
        "No unresolved placeholder markers detected."
    )


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _make_check(check_id: str, severity: str, passed: bool, reason: str) -> Dict:
    return {
        "check_id":  check_id,
        "severity":  severity,
        "pass":      passed,
        "reason":    reason,
    }
