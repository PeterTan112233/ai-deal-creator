"""
app/services/model_engine_service.py

Service wrapper for the cashflow engine.

PHASE 1 — MOCK ONLY.
All outputs from this service are synthetic. They must never be used as
official CLO outputs, pricing guidance, or investment analysis.

The interface of this module is designed so that Phase 2 can replace the
mock calls with real cashflow-engine-mcp calls without changing any caller.

Replacement plan (Phase 2):
    submit_scenario()  →  cashflow-engine-mcp.run_scenario()
    poll_until_done()  →  cashflow-engine-mcp.get_run_status()  (with retry)
    get_result()       →  cashflow-engine-mcp.get_run_outputs()
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict

from mcp.cashflow_engine import analytical_engine as _engine

_MOCK_MODE = True  # set to False when real MCP integration is active


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def submit_scenario(deal_id: str, scenario_request: Dict[str, Any]) -> str:
    """
    Submit a scenario to the cashflow engine. Returns a run_id.

    Phase 2: replace body with cashflow-engine-mcp.run_scenario() call.
    """
    submission = _engine.run_scenario(
        deal_payload=scenario_request.get("deal_payload", {"deal_id": deal_id}),
        scenario_payload=scenario_request.get("parameters", {}),
    )
    return submission["run_id"]


def poll_until_done(run_id: str) -> bool:
    """
    Poll the engine until the run completes. Returns True if complete.

    Phase 2: replace with real polling loop against cashflow-engine-mcp.get_run_status().
    Mock returns complete immediately.
    """
    status = _engine.get_run_status(run_id)
    return status.get("status") == "complete"


def get_result(run_id: str, scenario_id: str, deal_id: str) -> Dict[str, Any]:
    """
    Retrieve and normalize engine outputs into a ScenarioResult dict.
    Structure matches scenario_result.schema.json.

    Phase 2: replace mock_engine.get_run_outputs() with cashflow-engine-mcp.get_run_outputs().
    """
    raw = _engine.get_run_outputs(run_id)

    is_mock = "_mock" in raw

    result: Dict[str, Any] = {
        "run_id": run_id,
        "scenario_id": scenario_id,
        "deal_id": deal_id,
        "source": raw.get("source", "model_runner"),
        "status": "complete",
        "executed_at": datetime.now(timezone.utc).isoformat(),
        "outputs": _extract_outputs(raw),
        "engine_warnings": [],
        "engine_errors": [],
    }

    if is_mock:
        result["_mock"] = raw["_mock"]
        result["engine_warnings"].append(
            "DEMO ANALYTICAL ENGINE: outputs are computed by simplified formulas "
            "for development use only. Tag as [demo] — not [calculated]. "
            "Replace with real cashflow-engine-mcp in Phase 2."
        )

    return result


def is_mock_mode() -> bool:
    """Return True while using the mock engine."""
    return _MOCK_MODE


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _extract_outputs(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract only the recognised output metric keys from a raw engine response.
    Unknown keys (including _mock, _warning, run_id) are excluded.
    """
    recognised_keys = {
        "equity_irr",
        "aaa_size_pct",
        "wac",
        "oc_cushion_aaa",
        "ic_cushion_aaa",
        "equity_wal",
        "scenario_npv",
    }
    return {k: v for k, v in raw.items() if k in recognised_keys}
