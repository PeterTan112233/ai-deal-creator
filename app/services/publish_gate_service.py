"""
app/services/publish_gate_service.py

Service-layer publication gate — lightweight inline policy checks for
publish and distribution tool calls.

PURPOSE
  Evaluate whether a publish/distribution action should be allowed based on
  the inputs provided. Callable from workflow code, tests, and hook scripts.

  This is NOT a registered Claude Code hook. The hook layer enforcement is in
  infra/hooks/pre_tool_use.py (_check_publication_gate). This module provides
  the same logic as a reusable Python service for use in workflows.

INTERCEPTED TOOLS (for documentation purposes)
  publish_artifact, send_to_portal, distribute_document, export_document,
  email_document, upload_to_dataroom

CHECKS (in order)
  1. mock_data          — BLOCK if is_mock is True
  2. approval_status    — BLOCK if draft not approved
  3. external_approval  — BLOCK if external channel without approval_id

PHASE 3+
  Replace inline checks with publish_check_workflow.run() after loading deal
  and approval context from session state or MCP.
"""

from typing import Dict


# Tools treated as publish/distribution actions
_PUBLISH_TOOLS = frozenset({
    "publish_artifact",
    "send_to_portal",
    "distribute_document",
    "export_document",
    "email_document",
    "upload_to_dataroom",
})


def check_publish_allowed(tool_name: str, inputs: Dict) -> Dict:
    """
    Evaluate whether a publish/distribution tool call should be allowed.

    Parameters
    ----------
    tool_name : Name of the tool being called.
    inputs    : Tool input arguments dict.

    Returns
    -------
    {
        "action": "allow" | "block",
        "reason": str    — present only when action="block",
        "checks": list   — check results for auditability
    }
    """
    if tool_name not in _PUBLISH_TOOLS:
        return {"action": "allow", "checks": []}

    checks = []
    blocks = []

    # Check 1: Mock data gate
    is_mock = inputs.get("is_mock") or inputs.get("draft_is_mock")
    if is_mock:
        reason = (
            "Publish blocked: draft is based on mock engine outputs. "
            "Mock data must not be published or distributed under any channel."
        )
        checks.append({"check": "mock_data", "pass": False, "reason": reason})
        blocks.append(reason)
    else:
        checks.append({"check": "mock_data", "pass": True, "reason": "Not flagged as mock."})

    # Check 2: Approval status gate
    approval_status = inputs.get("approval_status") or inputs.get("draft_approval_status")
    draft_approved = inputs.get("draft_approved")

    if approval_status != "approved" and draft_approved is not True:
        reason = (
            "Publish blocked: draft approval status is not 'approved'. "
            "Obtain approval via the deal approval workflow before distributing."
        )
        checks.append({"check": "approval_status", "pass": False, "reason": reason})
        blocks.append(reason)
    else:
        checks.append({
            "check": "approval_status", "pass": True,
            "reason": "Approval status confirmed as approved."
        })

    # Check 3: External channel requires explicit approval record ID
    target_channel = inputs.get("target_channel", "internal")
    approval_id = inputs.get("approval_id") or inputs.get("approval_record_id")

    if target_channel == "external" and not approval_id:
        reason = (
            "Publish blocked: external distribution requires a formal approval_id. "
            "Request and obtain approval via approval_service before distributing externally."
        )
        checks.append({"check": "external_approval_id", "pass": False, "reason": reason})
        blocks.append(reason)
    else:
        checks.append({
            "check": "external_approval_id", "pass": True,
            "reason": (
                "External approval ID provided." if target_channel == "external"
                else "Internal channel — no approval ID required."
            ),
        })

    if blocks:
        return {
            "action": "block",
            "reason": " | ".join(blocks),
            "checks": checks,
        }

    return {"action": "allow", "checks": checks}


def handle(event: Dict) -> Dict:
    """
    Hook-compatible adapter: accepts a {tool, inputs} event dict and delegates
    to check_publish_allowed. Provided for callers that use the hook event format.
    """
    tool_name = event.get("tool", "")
    inputs = event.get("inputs") or {}
    return check_publish_allowed(tool_name, inputs)
