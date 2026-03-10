"""
app/workflows/sensitivity_analysis_workflow.py

Sweep a single scenario parameter across a range of values and return the
resulting output series plus interpolated breakeven points.

Typical usage:
    result = sensitivity_analysis_workflow(
        deal_input=deal,
        parameter="default_rate",
        values=[0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.09, 0.10],
    )
    # result["breakeven"]["equity_irr_zero"] → ~0.065 (CDR where IRR turns negative)
"""

from typing import Any, Dict, List, Optional
import uuid

from app.services import audit_logger, model_engine_service, validation_service


def sensitivity_analysis_workflow(
    deal_input: Dict[str, Any],
    parameter: str,
    values: List[float],
    base_parameters: Optional[Dict[str, Any]] = None,
    actor: str = "system",
) -> Dict[str, Any]:
    """
    Sweep one parameter over a list of values and collect engine outputs.

    Args:
        deal_input:       Deal input dict matching deal_input.schema.json.
        parameter:        Name of the parameter to sweep (e.g. "default_rate").
        values:           Ordered list of values to test (e.g. [0.01, ..., 0.10]).
        base_parameters:  Fixed values for all other parameters. Falls back to
                          deal_input.market_assumptions or standard defaults.
        actor:            Caller identity for audit trail.

    Returns:
        {
            "deal_id": str,
            "parameter": str,
            "values_tested": List[float],
            "series": [
                {
                    "parameter_value": float,
                    "outputs": Dict,     # equity_irr, wac, oc_cushion_aaa, ...
                    "run_id": str,
                    "status": "complete" | "failed",
                    "error": Optional[str],
                }, ...
            ],
            "breakeven": {
                "equity_irr_zero":    Optional[float],  # param value where IRR ~ 0
                "scenario_npv_zero":  Optional[float],  # param value where NPV ~ 0
            },
            "audit_events": List[str],
            "is_mock": bool,
            "error": str,   # only if deal validation failed
        }
    """
    audit_events: List[str] = []
    deal_id = deal_input.get("deal_id", "unknown")

    # ------------------------------------------------------------------
    # Step 1: Validate deal input
    # ------------------------------------------------------------------
    validation = validation_service.validate_deal_input(deal_input)

    audit_events.append(audit_logger.record_event(
        event_type="deal.validated",
        deal_id=deal_id,
        actor=actor,
        payload={"valid": validation["valid"], "issues": validation["issues"]},
    )["event_id"])

    if not validation["valid"]:
        return {
            "deal_id": deal_id,
            "parameter": parameter,
            "values_tested": [],
            "series": [],
            "breakeven": {"equity_irr_zero": None, "scenario_npv_zero": None},
            "audit_events": audit_events,
            "is_mock": model_engine_service.is_mock_mode(),
            "error": "Deal validation failed.",
        }

    if not values:
        return {
            "deal_id": deal_id,
            "parameter": parameter,
            "values_tested": [],
            "series": [],
            "breakeven": {"equity_irr_zero": None, "scenario_npv_zero": None},
            "audit_events": audit_events,
            "is_mock": model_engine_service.is_mock_mode(),
            "error": "No parameter values provided.",
        }

    # ------------------------------------------------------------------
    # Step 2: Resolve base parameters
    # ------------------------------------------------------------------
    base_assumptions = deal_input.get("market_assumptions", {})
    fixed_params: Dict[str, Any] = {
        "default_rate":     base_assumptions.get("default_rate",     0.03),
        "recovery_rate":    base_assumptions.get("recovery_rate",    0.65),
        "spread_shock_bps": base_assumptions.get("spread_shock_bps", 0),
    }
    if base_parameters:
        fixed_params.update(base_parameters)

    deal_payload = {
        "deal_id":         deal_id,
        "portfolio_size":  deal_input.get("collateral", {}).get("portfolio_size"),
        "was":             deal_input.get("collateral", {}).get("was"),
        "wal":             deal_input.get("collateral", {}).get("wal"),
        "diversity_score": deal_input.get("collateral", {}).get("diversity_score"),
        "ccc_bucket":      deal_input.get("collateral", {}).get("ccc_bucket"),
        "tranches":        deal_input.get("liabilities", []),
    }

    # ------------------------------------------------------------------
    # Step 3: Run engine for each value
    # ------------------------------------------------------------------
    series: List[Dict[str, Any]] = []

    for val in values:
        params = dict(fixed_params)
        params[parameter] = val

        scenario_request = {
            "scenario_id":   f"sc-{deal_id}-{uuid.uuid4().hex[:6]}",
            "deal_id":       deal_id,
            "name":          f"{parameter}={val}",
            "scenario_type": "sensitivity",
            "parameters":    params,
            "deal_payload":  deal_payload,
        }

        try:
            run_id = model_engine_service.submit_scenario(
                deal_id=deal_id,
                scenario_request=scenario_request,
            )
            model_engine_service.poll_until_done(run_id)
            engine_result = model_engine_service.get_result(
                run_id=run_id,
                scenario_id=scenario_request["scenario_id"],
                deal_id=deal_id,
            )
            series.append({
                "parameter_value": val,
                "outputs":         engine_result.get("outputs", {}),
                "run_id":          run_id,
                "status":          "complete",
                "error":           None,
            })
        except Exception as exc:  # noqa: BLE001
            series.append({
                "parameter_value": val,
                "outputs":         {},
                "run_id":          None,
                "status":          "failed",
                "error":           str(exc),
            })

    # ------------------------------------------------------------------
    # Step 4: Interpolate breakeven points
    # ------------------------------------------------------------------
    breakeven = _compute_breakeven(series)

    # ------------------------------------------------------------------
    # Step 5: Audit
    # ------------------------------------------------------------------
    completed = sum(1 for s in series if s["status"] == "complete")
    audit_events.append(audit_logger.record_event(
        event_type="sensitivity_analysis.completed",
        deal_id=deal_id,
        actor=actor,
        payload={
            "parameter":    parameter,
            "values_count": len(values),
            "completed":    completed,
            "breakeven":    breakeven,
        },
    )["event_id"])

    return {
        "deal_id":       deal_id,
        "parameter":     parameter,
        "values_tested": values,
        "series":        series,
        "breakeven":     breakeven,
        "audit_events":  audit_events,
        "is_mock":       model_engine_service.is_mock_mode(),
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _compute_breakeven(series: List[Dict[str, Any]]) -> Dict[str, Optional[float]]:
    """
    Linearly interpolate the parameter value where equity_irr and scenario_npv
    cross zero. Returns None if no crossover is found in the tested range.
    """
    completed = [s for s in series if s["status"] == "complete"]

    irr_zero = _interpolate_zero(
        [(s["parameter_value"], s["outputs"].get("equity_irr")) for s in completed]
    )
    npv_zero = _interpolate_zero(
        [(s["parameter_value"], s["outputs"].get("scenario_npv")) for s in completed]
    )

    return {"equity_irr_zero": irr_zero, "scenario_npv_zero": npv_zero}


def _interpolate_zero(pairs: List[tuple]) -> Optional[float]:
    """
    Given a list of (x, y) pairs, find x where y crosses zero via linear
    interpolation between consecutive points. Returns None if no crossing found.
    """
    valid = [(x, y) for x, y in pairs if y is not None and isinstance(y, (int, float))]
    if len(valid) < 2:
        return None

    for i in range(len(valid) - 1):
        x0, y0 = valid[i]
        x1, y1 = valid[i + 1]
        # Sign change → crossing
        if (y0 >= 0 and y1 < 0) or (y0 < 0 and y1 >= 0):
            if y1 == y0:
                continue
            # Linear interpolation: x_zero = x0 + (0 - y0) * (x1 - x0) / (y1 - y0)
            x_zero = x0 + (-y0) * (x1 - x0) / (y1 - y0)
            return round(x_zero, 6)

    return None
