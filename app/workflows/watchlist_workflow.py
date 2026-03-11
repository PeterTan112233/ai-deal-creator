"""
app/workflows/watchlist_workflow.py

Check a deal's base-case outputs against all active watchlist items and
return a structured alert report.

Typical usage:
    result = watchlist_check_workflow(deal_input, actor="analyst")
    triggered = [a for a in result["alerts"] if a["triggered"]]

IMPORTANT: All outputs tagged [demo]. Not for investment decisions.
"""

from typing import Any, Dict, List, Optional

from app.services import audit_logger, model_engine_service, validation_service, watchlist_service
from app.workflows.run_scenario_workflow import run_scenario_workflow


_BASE_PARAMS = {
    "default_rate": 0.030,
    "recovery_rate": 0.650,
    "spread_shock_bps": 0.0,
}


def watchlist_check_workflow(
    deal_input: Dict[str, Any],
    actor: str = "system",
) -> Dict[str, Any]:
    """
    Run the base-case scenario for a deal and check outputs against the watchlist.

    Parameters
    ----------
    deal_input : Deal input dict (validated internally).
    actor      : Caller identity for audit trail.

    Returns
    -------
    {
        "deal_id":           str,
        "items_checked":     int,          # watchlist items evaluated
        "triggered_count":   int,          # items that fired an alert
        "alerts":            List[Dict],   # one entry per applicable item
        "outputs_used":      Dict,         # base-case outputs used for checking
        "audit_events":      List[str],
        "is_mock":           bool,
        "error":             str | None,
    }
    """
    deal_id = deal_input.get("deal_id", "unknown")
    audit_events: List[str] = []

    # ------------------------------------------------------------------
    # Validate
    # ------------------------------------------------------------------
    validation = validation_service.validate_deal_input(deal_input)
    if not validation.get("valid"):
        return _result(deal_id, [], {}, audit_events,
                       error=f"Deal validation failed: {validation.get('errors', [])}")

    # ------------------------------------------------------------------
    # Run base-case scenario to get outputs
    # ------------------------------------------------------------------
    scen = run_scenario_workflow(
        deal_input=deal_input,
        scenario_name="Watchlist Base",
        scenario_type="base",
        parameter_overrides=_BASE_PARAMS,
        actor=actor,
    )
    audit_events.extend(scen.get("audit_events", []))

    if scen.get("error"):
        return _result(deal_id, [], {}, audit_events,
                       error=f"Scenario run failed: {scen['error']}")

    scen_result = scen.get("scenario_result") or {}
    outputs = scen_result.get("outputs", {})

    # ------------------------------------------------------------------
    # Evaluate watchlist items
    # ------------------------------------------------------------------
    alerts = watchlist_service.check_outputs(outputs, deal_id=deal_id)

    # ------------------------------------------------------------------
    # Audit
    # ------------------------------------------------------------------
    triggered = [a for a in alerts if a["triggered"]]
    audit_events.append(audit_logger.record_event(
        event_type="watchlist.checked",
        deal_id=deal_id,
        actor=actor,
        payload={
            "items_checked":   len(alerts),
            "triggered_count": len(triggered),
            "triggered_items": [a["item_id"] for a in triggered],
        },
    )["event_id"])

    return _result(deal_id, alerts, outputs, audit_events)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _result(
    deal_id: str,
    alerts: List[Dict],
    outputs: Dict,
    audit_events: List[str],
    error: Optional[str] = None,
) -> Dict[str, Any]:
    triggered = [a for a in alerts if a.get("triggered")]
    return {
        "deal_id":         deal_id,
        "items_checked":   len(alerts),
        "triggered_count": len(triggered),
        "alerts":          alerts,
        "outputs_used":    outputs,
        "audit_events":    audit_events,
        "is_mock":         model_engine_service.is_mock_mode(),
        "error":           error,
    }
