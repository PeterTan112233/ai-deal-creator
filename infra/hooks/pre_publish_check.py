"""
infra/hooks/pre_publish_check.py

Claude Code PreToolUse hook — specifically targets publish and distribution actions.

PURPOSE
  Gate any tool call that distributes, exports, or publishes deal materials.
  Runs inline policy checks and blocks if the minimum conditions are not met.

INTERCEPTED TOOLS
  publish_artifact, send_to_portal, distribute_document, export_document,
  email_document, upload_to_dataroom   (extend as Phase 2+ tools are added)

PHASE 1 BEHAVIOR
  Checks are enforced. Any publish-type tool call without an approved, non-mock
  draft will be blocked. The check logic mirrors publish_check_workflow.py
  but runs inline to avoid import dependencies.

PHASE 3+ BEHAVIOR
  Replace inline policy with publish_check_workflow.run() after loading deal
  and approval context from session state or MCP.

HOOK INTERFACE
  Input  (stdin):  JSON event with keys: tool, inputs
  Output (stdout): JSON with keys: action ("allow" | "block"), reason (if block)
  Exit code: 0 always — blocking is communicated via the action field.

TESTING
  Use handle(event) directly — no stdin required.
"""

import json
import os
import sys


# Tools that are treated as publish/distribution actions
_PUBLISH_TOOLS = frozenset({
    "publish_artifact",
    "send_to_portal",
    "distribute_document",
    "export_document",
    "email_document",
    "upload_to_dataroom",
})


def handle(event: dict) -> dict:
    """
    Evaluate whether the tool call should be allowed or blocked.

    Parameters
    ----------
    event : {
        "tool":   str   — name of the tool being called
        "inputs": dict  — tool input arguments
    }

    Returns
    -------
    {
        "action": "allow" | "block",
        "reason": str    — present only when action="block"
        "checks": list   — check results for auditability
    }
    """
    tool_name = event.get("tool", "")
    inputs    = event.get("inputs", {})

    # Pass through non-publish tools immediately
    if tool_name not in _PUBLISH_TOOLS:
        return {"action": "allow"}

    checks = []
    blocks = []

    # ------------------------------------------------------------------ #
    # Check 1: Mock data gate
    # ------------------------------------------------------------------ #
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

    # ------------------------------------------------------------------ #
    # Check 2: Approval status gate
    # ------------------------------------------------------------------ #
    approval_status = (
        inputs.get("approval_status")
        or inputs.get("draft_approval_status")
    )
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

    # ------------------------------------------------------------------ #
    # Check 3: External channel requires explicit approval record ID
    # ------------------------------------------------------------------ #
    target_channel   = inputs.get("target_channel", "internal")
    approval_id      = inputs.get("approval_id") or inputs.get("approval_record_id")

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

    # ------------------------------------------------------------------ #
    # Decision
    # ------------------------------------------------------------------ #
    if blocks:
        return {
            "action":  "block",
            "reason":  " | ".join(blocks),
            "checks":  checks,
        }

    return {"action": "allow", "checks": checks}


def _log_stderr(message: str) -> None:
    print(f"[pre_publish_check] {message}", file=sys.stderr)


if __name__ == "__main__":
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        event = {}

    result = handle(event)

    if result.get("action") == "block":
        _log_stderr(f"BLOCKED: {result.get('reason', 'no reason given')}")

    print(json.dumps(result))
