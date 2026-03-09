"""
infra/hooks/post_tool_use.py

Claude Code PostToolUse hook — runs after every tool call.

IMPLEMENTED (Phase 10)
  1. Mock output detection   — warns to stderr if tool output carries _mock tag
  2. Provenance tag mapping  — logs the source-tag category for each tool type
  3. Structured event log    — JSON event to stderr for session-level observability

SCAFFOLD ONLY — NOT YET ENFORCED
  4. Audit log write         — Phase 2: write tool + provenance to audit_log.jsonl
  5. Anomaly detection       — Phase 2: flag empty or unexpected engine outputs
  6. Provenance annotation   — Phase 2: attach [calculated]/[retrieved]/[generated]
                               tag to output before it reaches the model

IMPORTANT
  PostToolUse cannot undo or modify a tool call that has already executed.
  It is an observation and logging hook, not a control hook.

HOOK INTERFACE
  Input  (stdin):  JSON: { "tool": str, "inputs": dict, "outputs": any, ... }
  Output (stdout): JSON: { "action": "continue" }
  Side effects: structured JSON event logged to stderr
"""

import json
import sys
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# Tool → provenance tag mapping
# Determines what source tag applies to outputs from each tool category.
# Phase 2+: this mapping drives automatic tag attachment to outputs.
# ---------------------------------------------------------------------------

_PROVENANCE_MAP = {
    # Official engine outputs → [calculated]
    "cashflow_engine_run":      "[calculated]",
    "run_scenario":             "[calculated]",
    "get_scenario_result":      "[calculated]",

    # Data retrieval → [retrieved]
    "get_pool_data":            "[retrieved]",
    "get_portfolio":            "[retrieved]",
    "get_deal":                 "[retrieved]",
    "get_obligor":              "[retrieved]",
    "Read":                     "[retrieved]",

    # Language generation → [generated]
    "generate_summary":         "[generated]",
    "draft_investor_summary":   "[generated]",
    "compose_ic_memo":          "[generated]",
    "generate_ic_memo":         "[generated]",

    # Internal project tools → no tag (not model-facing outputs)
    "Bash":                     None,
    "Write":                    None,
    "Edit":                     None,
    "Glob":                     None,
    "Grep":                     None,
}

# Prefix matches for tool names not in the exact map
_PROVENANCE_PREFIXES = [
    ("cashflow_engine",  "[calculated]"),
    ("get_pool",         "[retrieved]"),
    ("get_portfolio",    "[retrieved]"),
    ("get_deal",         "[retrieved]"),
    ("draft_",           "[generated]"),
    ("generate_",        "[generated]"),
    ("compose_",         "[generated]"),
]


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def handle(event: dict) -> dict:
    """
    Log and inspect tool output after execution.
    Always returns {"action": "continue"} — PostToolUse cannot block.
    """
    tool_name = event.get("tool", "unknown")
    outputs   = event.get("outputs")
    inputs    = event.get("inputs", {})

    provenance_tag = _resolve_provenance(tool_name)
    mock_detected  = _detect_mock(outputs)
    anomaly        = _detect_anomaly(tool_name, outputs)

    log_entry = {
        "hook":           "post_tool_use",
        "timestamp":      datetime.now(timezone.utc).isoformat(),
        "tool":           tool_name,
        "provenance_tag": provenance_tag,
        "mock_detected":  mock_detected,
        "anomaly":        anomaly,
        "output_keys":    _extract_output_keys(outputs),
    }

    _log(json.dumps(log_entry))

    if mock_detected:
        _log(
            f"WARNING [{tool_name}]: output contains _mock tag — "
            "these values are synthetic placeholders, not official CLO results."
        )

    if anomaly:
        _log(f"WARNING [{tool_name}]: {anomaly}")

    # Phase 2 TODO: write to audit_log.jsonl via audit_logger.record_event()
    # Phase 2 TODO: attach provenance_tag to output before returning to model

    return {"action": "continue"}


# ---------------------------------------------------------------------------
# Inspection helpers
# ---------------------------------------------------------------------------

def _resolve_provenance(tool_name: str) -> str:
    """Return the source tag for a given tool name, or '[unknown]'."""
    if tool_name in _PROVENANCE_MAP:
        tag = _PROVENANCE_MAP[tool_name]
        return tag if tag else "[internal]"
    for prefix, tag in _PROVENANCE_PREFIXES:
        if tool_name.startswith(prefix):
            return tag
    return "[unknown]"


def _detect_mock(outputs) -> bool:
    """True if the output dict contains a _mock key at any level."""
    if isinstance(outputs, dict):
        if "_mock" in outputs:
            return True
        # Check one level deep (e.g. outputs.outputs._mock)
        for val in outputs.values():
            if isinstance(val, dict) and "_mock" in val:
                return True
    return False


def _detect_anomaly(tool_name: str, outputs) -> str:
    """
    Return a non-empty string describing an anomaly, or empty string if none.
    Phase 10: checks for empty engine outputs and null result from expected tools.
    Phase 2+: expand with statistical anomaly detection on output values.
    """
    # Engine tools should always return a non-empty outputs dict
    if tool_name in ("cashflow_engine_run", "run_scenario", "get_scenario_result"):
        if outputs is None:
            return f"Engine tool '{tool_name}' returned None output."
        if isinstance(outputs, dict) and not outputs.get("outputs"):
            return f"Engine tool '{tool_name}' returned empty or missing outputs dict."

    # Read tool should not return None for an existing file path
    if tool_name == "Read" and outputs is None:
        return "Read returned None — file may not exist or is unreadable."

    return ""


def _extract_output_keys(outputs) -> list:
    """Return top-level keys if outputs is a dict, else empty list."""
    if isinstance(outputs, dict):
        return [k for k in outputs.keys() if not k.startswith("_")]
    return []


def _log(message: str) -> None:
    print(f"[post_tool_use] {message}", file=sys.stderr)


if __name__ == "__main__":
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        event = {}
    result = handle(event)
    print(json.dumps(result))
