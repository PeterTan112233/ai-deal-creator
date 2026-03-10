"""
app/workflows/batch_scenario_workflow.py

Run multiple named scenarios against the same deal in a single call and
return a side-by-side comparison table.

Typical usage:
    scenarios = [
        {"name": "Base",        "type": "base",   "parameters": {"default_rate": 0.03, "recovery_rate": 0.65, "spread_shock_bps": 0}},
        {"name": "Stress",      "type": "stress", "parameters": {"default_rate": 0.06, "recovery_rate": 0.45, "spread_shock_bps": 75}},
        {"name": "Super-Stress","type": "stress", "parameters": {"default_rate": 0.10, "recovery_rate": 0.35, "spread_shock_bps": 150}},
    ]
    result = batch_scenario_workflow(deal_input, scenarios)
"""

import uuid
from typing import Any, Dict, List, Optional

from app.services import audit_logger, model_engine_service, validation_service

# Metrics where a higher value is better (for best/worst annotation)
_HIGHER_IS_BETTER = {"equity_irr", "oc_cushion_aaa", "ic_cushion_aaa", "equity_wal", "scenario_npv"}
# Metrics where a lower value is better
_LOWER_IS_BETTER: set = set()
# All other metrics are annotated without best/worst

_OUTPUT_METRICS = [
    "equity_irr",
    "wac",
    "oc_cushion_aaa",
    "ic_cushion_aaa",
    "equity_wal",
    "scenario_npv",
    "aaa_size_pct",
]


def batch_scenario_workflow(
    deal_input: Dict[str, Any],
    scenarios: List[Dict[str, Any]],
    actor: str = "system",
) -> Dict[str, Any]:
    """
    Run multiple scenarios against the same deal and return a comparison table.

    Args:
        deal_input:  Deal input dict matching deal_input.schema.json.
        scenarios:   List of scenario definitions. Each entry:
                       {
                         "name": str,               # human label (required)
                         "type": str,               # "base"|"stress"|"custom" (default: "base")
                         "parameters": {            # engine parameters
                           "default_rate": float,
                           "recovery_rate": float,
                           "spread_shock_bps": float,
                         }
                       }
        actor:       Identity of the caller (audit trail).

    Returns:
        {
            "deal_id": str,
            "scenarios_run": int,
            "results": [...],           # one entry per scenario
            "comparison_table": [...],  # one row per output metric
            "audit_events": [...],
            "is_mock": bool,
            "error": str,               # only present if deal validation failed
        }
    """
    audit_events: List[str] = []
    deal_id = deal_input.get("deal_id", "unknown")

    # ------------------------------------------------------------------
    # Step 1: Validate deal input once (shared across all scenarios)
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
            "scenarios_run": 0,
            "results": [],
            "comparison_table": [],
            "audit_events": audit_events,
            "is_mock": model_engine_service.is_mock_mode(),
            "error": "Deal validation failed. Fix issues before running scenarios.",
        }

    if not scenarios:
        return {
            "deal_id": deal_id,
            "scenarios_run": 0,
            "results": [],
            "comparison_table": [],
            "audit_events": audit_events,
            "is_mock": model_engine_service.is_mock_mode(),
            "error": "No scenarios provided.",
        }

    # ------------------------------------------------------------------
    # Step 2: Build deal_payload (pool metrics + tranches for the engine)
    # ------------------------------------------------------------------
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
    # Step 3: Run each scenario
    # ------------------------------------------------------------------
    results: List[Dict[str, Any]] = []

    for scenario_def in scenarios:
        scenario_name = scenario_def.get("name", f"Scenario-{len(results) + 1}")
        scenario_type = scenario_def.get("type", "base")
        parameters = dict(scenario_def.get("parameters", {}))

        # Apply defaults for missing parameters
        base_assumptions = deal_input.get("market_assumptions", {})
        parameters.setdefault("default_rate",     base_assumptions.get("default_rate",     0.03))
        parameters.setdefault("recovery_rate",    base_assumptions.get("recovery_rate",    0.65))
        parameters.setdefault("spread_shock_bps", base_assumptions.get("spread_shock_bps", 0))

        scenario_request = {
            "scenario_id":  f"sc-{deal_id}-{uuid.uuid4().hex[:6]}",
            "deal_id":      deal_id,
            "name":         scenario_name,
            "scenario_type": scenario_type,
            "parameters":   parameters,
            "deal_payload": deal_payload,
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
            results.append({
                "scenario_name": scenario_name,
                "scenario_type": scenario_type,
                "run_id":        run_id,
                "parameters":    parameters,
                "outputs":       engine_result.get("outputs", {}),
                "status":        "complete",
                "error":         None,
            })
        except Exception as exc:  # noqa: BLE001
            results.append({
                "scenario_name": scenario_name,
                "scenario_type": scenario_type,
                "run_id":        None,
                "parameters":    parameters,
                "outputs":       {},
                "status":        "failed",
                "error":         str(exc),
            })

    # ------------------------------------------------------------------
    # Step 4: Build comparison table
    # ------------------------------------------------------------------
    comparison_table = _build_comparison_table(results)

    # ------------------------------------------------------------------
    # Step 5: Audit
    # ------------------------------------------------------------------
    completed = sum(1 for r in results if r["status"] == "complete")
    failed    = sum(1 for r in results if r["status"] == "failed")

    audit_events.append(audit_logger.record_event(
        event_type="batch_scenario.completed",
        deal_id=deal_id,
        actor=actor,
        payload={
            "scenarios_run": len(results),
            "completed":     completed,
            "failed":        failed,
            "scenario_names": [r["scenario_name"] for r in results],
        },
    )["event_id"])

    return {
        "deal_id":         deal_id,
        "scenarios_run":   len(results),
        "results":         results,
        "comparison_table": comparison_table,
        "audit_events":    audit_events,
        "is_mock":         model_engine_service.is_mock_mode(),
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_comparison_table(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Build a metric-by-metric comparison across all scenarios.
    Each row: {metric, values: {scenario_name: value}, best, worst}
    Only includes metrics present in at least one result.
    """
    completed = [r for r in results if r["status"] == "complete"]
    if not completed:
        return []

    table = []
    for metric in _OUTPUT_METRICS:
        row_values: Dict[str, Any] = {}
        for r in completed:
            val = r["outputs"].get(metric)
            if val is not None:
                row_values[r["scenario_name"]] = val

        if not row_values:
            continue

        best = worst = None
        numeric_vals = {k: v for k, v in row_values.items() if isinstance(v, (int, float))}

        if len(numeric_vals) > 1:
            if metric in _HIGHER_IS_BETTER:
                best  = max(numeric_vals, key=lambda k: numeric_vals[k])
                worst = min(numeric_vals, key=lambda k: numeric_vals[k])
            elif metric in _LOWER_IS_BETTER:
                best  = min(numeric_vals, key=lambda k: numeric_vals[k])
                worst = max(numeric_vals, key=lambda k: numeric_vals[k])

        table.append({
            "metric": metric,
            "values": row_values,
            "best":   best,
            "worst":  worst,
        })

    return table
