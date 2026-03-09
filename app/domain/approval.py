from dataclasses import dataclass
from typing import Optional
from datetime import datetime


@dataclass
class Approval:
    # ------------------------------------------------------------------ #
    # USER INPUT — provided when requesting approval                      #
    # ------------------------------------------------------------------ #
    approval_id: str
    deal_id: str
    target_type: str                    # deal | investor_material | publish
    target_id: str                      # ID of the object requiring approval
    channel: str = "internal"          # internal | investor_portal | external
    # channel determines which approval rules apply and which disclosures are required

    # ------------------------------------------------------------------ #
    # SYSTEM METADATA — set by the workflow when approval is requested    #
    # ------------------------------------------------------------------ #
    status: str = "pending"             # pending | approved | rejected
    requested_at: Optional[datetime] = None
    requested_by: Optional[str] = None  # user or agent that requested approval

    # ------------------------------------------------------------------ #
    # APPROVAL ACTION — set by the human approver                         #
    # these fields must NEVER be set by Claude agents                     #
    # ------------------------------------------------------------------ #
    approver: Optional[str] = None      # identity of human approver
    approved_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None  # required if status = "rejected"

    notes: Optional[str] = None

    # ------------------------------------------------------------------ #
    # FUTURE EXPANSION                                                     #
    # Phase 9+: expires_at used by publish_check_workflow to reject stale  #
    #           approval records                                           #
    # Phase 3+: required_approver_roles, escalation_path (entitlement-mcp) #
    # ------------------------------------------------------------------ #
    expires_at: Optional[datetime] = None  # None = no expiry (Phase 1 default)
