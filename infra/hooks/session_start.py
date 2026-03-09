"""
infra/hooks/session_start.py

Claude Code SessionStart hook — runs once at the start of each session.

IMPLEMENTED (Phase 10)
  1. Session ID generation  — unique ID for correlation across tool-call logs
  2. Environment validation — checks APP_ENV and key URL vars are set
  3. Mock mode detection    — sets mock_mode=True if not in production env
  4. Data directory check   — verifies data/ structure is accessible
  5. Session start log      — JSON event to stderr for audit trail

SCAFFOLD ONLY — NOT YET IMPLEMENTED
  6. Active deal context    — Phase 3: load deal_id and version from deal-store-mcp
  7. User role              — Phase 3: load entitlement profile from entitlement-mcp
  8. Disclosure profile     — Phase 3: pre-load required disclosures by channel
  9. Rate limit check       — Phase 3: confirm engine quota is available

HOOK INTERFACE
  Input  (stdin):  JSON session event (may be empty in some Claude Code versions)
  Output (stdout): JSON: { "action": "continue", "context": dict }
  Side effects: session start event logged to stderr
"""

import json
import os
import sys
import uuid
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# Required environment variable names
# ---------------------------------------------------------------------------

_REQUIRED_VARS = ["APP_ENV"]
_OPTIONAL_VARS = ["MODEL_ENGINE_URL", "DOCS_SERVICE_URL", "AUDIT_LOG_PATH"]

# Expected data directory structure (spot check only)
_DATA_DIRS = [
    "data",
    "data/samples",
]
_AUDIT_LOG_PATH_DEFAULT = "data/audit_log.jsonl"


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def handle(event: dict) -> dict:
    """
    Bootstrap session context.
    Returns {"action": "continue", "context": dict}.
    Never blocks — session_start cannot prevent a session from starting.
    """
    session_id = f"session-{uuid.uuid4().hex[:12]}"
    now        = datetime.now(timezone.utc).isoformat()

    env_status   = _validate_environment()
    mock_mode    = _detect_mock_mode()
    data_status  = _check_data_directories()
    audit_path   = os.environ.get("AUDIT_LOG_PATH", _AUDIT_LOG_PATH_DEFAULT)

    context = {
        # Session metadata
        "session_id":       session_id,
        "session_started":  now,

        # Environment
        "app_env":          os.environ.get("APP_ENV", "local"),
        "model_engine_url": os.environ.get("MODEL_ENGINE_URL", "http://localhost:8080"),
        "docs_service_url": os.environ.get("DOCS_SERVICE_URL", "http://localhost:8090"),
        "audit_log_path":   audit_path,

        # Runtime mode
        "mock_mode":        mock_mode,
        "env_valid":        env_status["valid"],
        "env_warnings":     env_status["warnings"],

        # Data integrity
        "data_dirs_ok":     data_status["ok"],
        "data_warnings":    data_status["warnings"],

        # Phase 3 scaffolds — always None in Phase 1
        "active_deal_id":   None,   # Phase 3: load from deal-store-mcp
        "user_role":        None,   # Phase 3: load from entitlement-mcp
        "user_id":          None,   # Phase 3: read from session auth token
        "disclosure_profile": None, # Phase 3: load from disclosure-library-mcp
    }

    log_entry = {
        "hook":         "session_start",
        "session_id":   session_id,
        "timestamp":    now,
        "app_env":      context["app_env"],
        "mock_mode":    mock_mode,
        "env_valid":    env_status["valid"],
        "data_dirs_ok": data_status["ok"],
    }
    _log(json.dumps(log_entry))

    for warning in env_status["warnings"] + data_status["warnings"]:
        _log(f"WARNING: {warning}")

    return {"action": "continue", "context": context}


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def _validate_environment() -> dict:
    """
    Check that expected environment variables are present and valid.
    Returns {"valid": bool, "warnings": list}.
    """
    warnings = []

    for var in _REQUIRED_VARS:
        if not os.environ.get(var):
            warnings.append(
                f"Required env var '{var}' is not set. "
                "Add it to .claude/settings.local.json or your shell environment."
            )

    app_env = os.environ.get("APP_ENV", "local")
    if app_env not in ("local", "dev", "staging", "production"):
        warnings.append(
            f"APP_ENV='{app_env}' is not a recognised environment. "
            "Expected: local | dev | staging | production."
        )

    model_url = os.environ.get("MODEL_ENGINE_URL", "")
    if model_url and not (model_url.startswith("http://") or model_url.startswith("https://")):
        warnings.append(
            f"MODEL_ENGINE_URL does not look like a valid URL: {model_url!r}"
        )

    return {"valid": len(warnings) == 0, "warnings": warnings}


def _detect_mock_mode() -> bool:
    """
    True if the session is operating in mock mode.
    Phase 10: mock mode is inferred from APP_ENV or an explicit MOCK_MODE var.
    Production apps should set APP_ENV=production and MOCK_MODE=false.
    """
    explicit = os.environ.get("MOCK_MODE", "").lower()
    if explicit in ("false", "0", "no"):
        return False
    if explicit in ("true", "1", "yes"):
        return True
    # Default: mock unless in production
    return os.environ.get("APP_ENV", "local") != "production"


def _check_data_directories() -> dict:
    """
    Spot-check that expected data directories exist.
    Does not verify file contents — just presence.
    Returns {"ok": bool, "warnings": list}.
    """
    warnings = []
    for path in _DATA_DIRS:
        if not os.path.isdir(path):
            warnings.append(
                f"Expected data directory not found: '{path}'. "
                "Run the project setup steps to create required directories."
            )
    return {"ok": len(warnings) == 0, "warnings": warnings}


def _log(message: str) -> None:
    print(f"[session_start] {message}", file=sys.stderr)


if __name__ == "__main__":
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        event = {}
    result = handle(event)
    print(json.dumps(result))
