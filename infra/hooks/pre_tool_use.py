"""
infra/hooks/pre_tool_use.py

Claude Code PreToolUse hook — runs before any tool call executes.

IMPLEMENTED (Phase 10)
  1. Publication gate     — blocks publish/distribution tools without approval
  2. Audit log protection — blocks Bash commands that would delete or overwrite the audit log
  3. Bash safety gate     — blocks known-dangerous bash patterns (belt+suspenders)

SCAFFOLD ONLY — NOT YET ENFORCED
  4. Calculation gate     — Phase 3: block non-MCP financial compute tools
  5. Entitlement check    — Phase 3: call entitlement-mcp.can_use(user, tool, inputs)
  6. Schema validation    — Phase 3: validate scenario parameters before engine submission
  7. Sensitive data gate  — Phase 3: redact before returning pool/obligor data

HOOK INTERFACE
  Input  (stdin):  JSON: { "tool": str, "inputs": dict, ... }
  Output (stdout): JSON: { "action": "allow" | "block", "reason"?: str, "checks": list }
  Errors: logged to stderr; always fall back to allow on unexpected exceptions

RELATIONSHIP TO pre_publish_check.py
  pre_tool_use.py: lightweight gate at the tool-call boundary — first line of defence
  pre_publish_check.py: full structured check callable from workflow code
  Both enforce the same policy; pre_publish_check.py is the authoritative implementation
  for complex publish scenarios.
"""

import json
import sys
import re


# ---------------------------------------------------------------------------
# Tool categories
# ---------------------------------------------------------------------------

_PUBLISH_TOOLS = frozenset({
    "publish_artifact",
    "send_to_portal",
    "distribute_document",
    "export_document",
    "email_document",
    "upload_to_dataroom",
})

# Bash patterns that must never be allowed against project data
_AUDIT_LOG_PATHS = ("audit_log", "data/audit_log", "data\\audit_log")
_BASH_DESTROY_PATTERNS = [
    re.compile(r"\brm\b.*audit_log"),
    re.compile(r">\s*(data/)?audit_log"),
    re.compile(r"\btruncate\b.*audit_log"),
    re.compile(r"\brm\s+-[a-z]*r[a-z]*f\b"),     # rm -rf variants
    re.compile(r"\bgit\s+push\s+.*--force\b"),    # force push
    re.compile(r"\bgit\s+reset\s+--hard\b"),       # hard reset
    re.compile(r"\bchmod\s+777\b"),               # broad permission grant
    re.compile(r"\bsudo\b"),                       # no sudo in project hooks
]


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def handle(event: dict) -> dict:
    """
    Evaluate whether the tool call should be allowed or blocked.

    Returns {"action": "allow", "checks": [...]} or
            {"action": "block", "reason": str, "checks": [...]}
    """
    tool_name = event.get("tool", "")
    inputs    = event.get("inputs", {})
    checks    = []

    try:
        # ---------------------------------------------------------------- #
        # Check 1: Publication gate (Phase 10 — enforced)                  #
        # ---------------------------------------------------------------- #
        if tool_name in _PUBLISH_TOOLS:
            result = _check_publication_gate(inputs)
            checks.append(result)
            if not result["pass"]:
                _log(f"BLOCK [{tool_name}]: {result['reason']}")
                return {"action": "block", "reason": result["reason"], "checks": checks}

        # ---------------------------------------------------------------- #
        # Check 2: Audit log protection (Phase 10 — enforced)              #
        # ---------------------------------------------------------------- #
        if tool_name == "Bash":
            result = _check_audit_log_protection(inputs)
            checks.append(result)
            if not result["pass"]:
                _log(f"BLOCK [Bash]: {result['reason']}")
                return {"action": "block", "reason": result["reason"], "checks": checks}

            result = _check_bash_safety(inputs)
            checks.append(result)
            if not result["pass"]:
                _log(f"BLOCK [Bash]: {result['reason']}")
                return {"action": "block", "reason": result["reason"], "checks": checks}

        # ---------------------------------------------------------------- #
        # Check 3: Write/Edit protection on critical files                  #
        # Phase 10 — enforced for .env and audit log                       #
        # ---------------------------------------------------------------- #
        if tool_name in ("Write", "Edit"):
            result = _check_file_write_safety(inputs)
            checks.append(result)
            if not result["pass"]:
                _log(f"BLOCK [{tool_name}]: {result['reason']}")
                return {"action": "block", "reason": result["reason"], "checks": checks}

        # ---------------------------------------------------------------- #
        # Scaffold: Calculation gate (Phase 3 — not enforced)              #
        # TODO: block non-MCP calls that attempt to compute official CLO   #
        # metrics. Phase 3: call entitlement-mcp.can_compute(tool, inputs) #
        # ---------------------------------------------------------------- #

        # ---------------------------------------------------------------- #
        # Scaffold: Entitlement check (Phase 3 — not enforced)             #
        # TODO: call entitlement-mcp.can_use(user_id, tool_name, inputs)   #
        # Block if user lacks deal-level access.                            #
        # ---------------------------------------------------------------- #

        # ---------------------------------------------------------------- #
        # Scaffold: Schema validation (Phase 3 — not enforced)             #
        # TODO: for run_scenario* tools, validate parameters against        #
        # scenario_request.schema.json before allowing engine submission.   #
        # ---------------------------------------------------------------- #

    except Exception as exc:
        # Hook errors must never block tool execution — log and fall through
        _log(f"ERROR in pre_tool_use (falling through to allow): {exc}")

    return {"action": "allow", "checks": checks}


# ---------------------------------------------------------------------------
# Check implementations
# ---------------------------------------------------------------------------

def _check_publication_gate(inputs: dict) -> dict:
    """
    Block publish/distribution tools unless the draft is approved and not mock.
    Phase 10: inline check. For full structured check, use pre_publish_check.py.
    """
    is_mock = inputs.get("is_mock") or inputs.get("draft_is_mock")
    if is_mock:
        return _fail(
            "publication_gate",
            "Draft is based on mock engine outputs. Mock data cannot be published."
        )

    approved = inputs.get("draft_approved") or (inputs.get("approval_status") == "approved")
    if not approved:
        return _fail(
            "publication_gate",
            "Draft approval status is not 'approved'. "
            "Obtain approval via the deal approval workflow before distributing."
        )

    target_channel = inputs.get("target_channel", "internal")
    approval_id    = inputs.get("approval_id") or inputs.get("approval_record_id")
    if target_channel == "external" and not approval_id:
        return _fail(
            "publication_gate",
            "External distribution requires a formal approval_id. "
            "Request and obtain approval via approval_service before distributing externally."
        )

    return _pass("publication_gate", "Publication gate: approved, not mock.")


def _check_audit_log_protection(inputs: dict) -> dict:
    """
    Block Bash commands that would delete or overwrite the audit log.
    The audit log at data/audit_log.jsonl must be append-only.
    """
    command = inputs.get("command", "")
    for pattern in [
        re.compile(r"\brm\b.*audit_log"),
        re.compile(r"(?<![>])>\s*(data[/\\])?audit_log"),
        re.compile(r"\btruncate\b.*audit_log"),
    ]:
        if pattern.search(command):
            return _fail(
                "audit_log_protection",
                f"Bash command appears to target the audit log file. "
                "The audit log is append-only and must not be deleted or overwritten. "
                f"Command pattern matched: {pattern.pattern!r}"
            )
    return _pass("audit_log_protection", "No audit log modification detected.")


def _check_bash_safety(inputs: dict) -> dict:
    """
    Block known-dangerous Bash patterns as belt+suspenders alongside
    the permissions deny list in settings.json.
    Phase 10: rm -rf, force-push, hard-reset, sudo, chmod 777.
    """
    command = inputs.get("command", "")
    for pattern in [
        re.compile(r"\brm\s+-[a-zA-Z]*f[a-zA-Z]*\b"),
        re.compile(r"\bgit\s+push\s+.*--force\b"),
        re.compile(r"\bgit\s+reset\s+--hard\b"),
        re.compile(r"\bchmod\s+777\b"),
        re.compile(r"\bsudo\b"),
    ]:
        if pattern.search(command):
            return _fail(
                "bash_safety",
                f"Bash command matches a blocked pattern. "
                f"Pattern: {pattern.pattern!r}. Review the command before proceeding."
            )
    return _pass("bash_safety", "No dangerous Bash patterns detected.")


def _check_file_write_safety(inputs: dict) -> dict:
    """
    Block writes to .env files and the audit log.
    Phase 10: .env* and data/audit_log.jsonl are write-protected.
    """
    file_path = inputs.get("file_path", "") or inputs.get("path", "")
    blocked_patterns = [
        re.compile(r"(^|[/\\])\.env([^/\\]|$)"),
        re.compile(r"audit_log\.jsonl"),
    ]
    for pattern in blocked_patterns:
        if pattern.search(file_path):
            return _fail(
                "file_write_safety",
                f"Write to protected file is not allowed: {file_path!r}. "
                "Audit logs are append-only via audit_logger.py. "
                ".env files must not be written by hooks or agents."
            )
    return _pass("file_write_safety", "File write target is not a protected path.")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _pass(check_id: str, reason: str) -> dict:
    return {"check_id": check_id, "pass": True, "reason": reason}


def _fail(check_id: str, reason: str) -> dict:
    return {"check_id": check_id, "pass": False, "reason": reason}


def _log(message: str) -> None:
    print(f"[pre_tool_use] {message}", file=sys.stderr)


if __name__ == "__main__":
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        event = {}
    result = handle(event)
    if result.get("action") == "block":
        _log(f"BLOCKED: {result.get('reason', '')}")
    print(json.dumps(result))
