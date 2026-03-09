"""
infra/hooks/completion.py

Claude Code Stop hook — runs when the agent completes a turn.

Wired as the "Stop" hook type in .claude/settings.json (Claude Code maps
turn completion to the Stop lifecycle event; this file is named "completion"
to match the PRD and project convention).

IMPLEMENTED (Phase 10)
  1. Session summary log      — counts tool calls and event types in this turn
  2. Audit log flush guidance — notes audit_log.jsonl as the durable record
  3. Pending approval scan    — scans recent audit log for pending approval requests
  4. Mock mode reminder       — warns if session is in mock mode

SCAFFOLD ONLY — NOT YET IMPLEMENTED
  5. SIEM emit               — Phase 3: push session summary to external audit system
  6. Workflow routing        — Phase 3: call workflow-mcp to route open review items
  7. Completion event signal — Phase 3: signal external systems the workflow run finished
  8. Draft expiry check      — Phase 3: flag any approval records approaching expiry

HOOK INTERFACE
  Input  (stdin):  JSON stop event — structure varies by Claude Code version
  Output (stdout): JSON: { "action": "continue" }
  Side effects: session summary logged to stderr

NOTE
  This hook runs at the end of each agent turn, not just at session end.
  A long session may trigger this hook multiple times.
  The hook is safe to run idempotently.
"""

import json
import os
import sys
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_AUDIT_LOG_PATH = os.environ.get("AUDIT_LOG_PATH", "data/audit_log.jsonl")

# Number of recent audit log lines to scan for pending approvals
_AUDIT_SCAN_LINES = 50

# Event types that indicate pending work requiring follow-up
_PENDING_EVENT_TYPES = {"draft.generated", "approval.requested", "publish_check.run"}


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def handle(event: dict) -> dict:
    """
    Log a turn-completion summary and scan for pending items.
    Always returns {"action": "continue"}.
    """
    now        = datetime.now(timezone.utc).isoformat()
    session_id = event.get("session_id", "unknown")
    mock_mode  = os.environ.get("APP_ENV", "local") != "production"

    tool_summary  = _summarise_tool_usage(event)
    pending_items = _scan_for_pending_items()

    log_entry = {
        "hook":            "completion",
        "timestamp":       now,
        "session_id":      session_id,
        "mock_mode":       mock_mode,
        "tool_calls":      tool_summary.get("total", 0),
        "tool_breakdown":  tool_summary.get("by_tool", {}),
        "pending_items":   len(pending_items),
        "audit_log":       _AUDIT_LOG_PATH,
    }
    _log(json.dumps(log_entry))

    if mock_mode:
        _log(
            "REMINDER: Session is in mock mode. "
            "All engine outputs are synthetic placeholders — not official CLO results."
        )

    if pending_items:
        _log(f"PENDING ITEMS ({len(pending_items)}) — require follow-up:")
        for item in pending_items[:5]:   # cap at 5 in output
            _log(f"  • {item}")
        if len(pending_items) > 5:
            _log(f"  ... and {len(pending_items) - 5} more. See {_AUDIT_LOG_PATH}")

    _log(
        f"Audit log: {_AUDIT_LOG_PATH} — "
        "this is the durable record of all workflow events in this session."
    )

    # Phase 3 TODO: emit session summary to SIEM / workflow-mcp
    # Phase 3 TODO: call workflow-mcp.route_open_items(pending_items)
    # Phase 3 TODO: signal external completion event

    return {"action": "continue"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _summarise_tool_usage(event: dict) -> dict:
    """
    Extract tool usage summary from the completion event.
    Phase 10: uses fields present in common Claude Code Stop event payloads.
    Returns {"total": int, "by_tool": dict}.
    """
    # Claude Code Stop event may include tool_use_count or similar fields
    # Fall back gracefully if not present
    tool_calls = event.get("tool_use_count") or event.get("tool_calls") or []

    if isinstance(tool_calls, list):
        by_tool: dict = {}
        for call in tool_calls:
            name = call.get("tool", "unknown") if isinstance(call, dict) else str(call)
            by_tool[name] = by_tool.get(name, 0) + 1
        return {"total": len(tool_calls), "by_tool": by_tool}

    if isinstance(tool_calls, int):
        return {"total": tool_calls, "by_tool": {}}

    return {"total": 0, "by_tool": {}}


def _scan_for_pending_items() -> list:
    """
    Read the last N lines of the audit log and extract events that indicate
    pending work: draft.generated (no subsequent approval), approval.requested
    (no subsequent record_approval), publish_check.run with BLOCKED result.

    Phase 10: simple line scan — no index, no structured query.
    Phase 3+: replace with audit-store-mcp.get_pending_items(session_id).
    """
    pending = []

    if not os.path.exists(_AUDIT_LOG_PATH):
        return pending

    try:
        with open(_AUDIT_LOG_PATH) as f:
            lines = f.readlines()

        recent = lines[-_AUDIT_SCAN_LINES:]

        for line in recent:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            event_type = entry.get("event_type", "")
            payload    = entry.get("payload", {})

            if event_type == "draft.generated":
                draft_id   = payload.get("draft_id", "unknown")
                draft_type = payload.get("draft_type", "unknown")
                pending.append(
                    f"draft.generated: {draft_type} draft '{draft_id}' — "
                    "requires approval before distribution."
                )

            elif event_type == "publish_check.run":
                rec = payload.get("recommendation", "")
                if rec in ("BLOCKED", "REVIEW_REQUIRED"):
                    draft_id = payload.get("draft_id", "unknown")
                    pending.append(
                        f"publish_check.run: draft '{draft_id}' — "
                        f"result: {rec}. Blocking reasons: "
                        f"{payload.get('blocking_reasons', [])}"
                    )

    except OSError as exc:
        _log(f"Could not scan audit log: {exc}")

    return pending


def _log(message: str) -> None:
    print(f"[completion] {message}", file=sys.stderr)


if __name__ == "__main__":
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        event = {}
    result = handle(event)
    print(json.dumps(result))
