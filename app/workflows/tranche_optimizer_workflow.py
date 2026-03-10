"""
app/workflows/tranche_optimizer_workflow.py

Tranche structure optimizer.

Sweeps AAA tranche size over a configurable range and finds the structure
that maximises equity IRR while satisfying OC cushion and IC cushion floor
constraints. Returns the optimal structure, a full feasibility table, and
an efficiency frontier of IRR vs. AAA size.

IMPORTANT: All outputs are tagged [demo] — produced by DEMO_ANALYTICAL_ENGINE.
These are analytical approximations and must not be used as official CLO
structuring outputs.

METHODOLOGY
  For each candidate AAA size (swept in 0.5% steps from aaa_min to aaa_max):
    1. Assign fixed mez tranche at mez_size_pct (default 8%) below the AAA.
    2. Equity absorbs the remainder (1 - aaa_size - mez_size).
    3. Run analytical engine with base-case scenario parameters.
    4. Record IRR, OC cushion, IC cushion.
  Feasible = OC cushion >= oc_floor AND IC cushion >= ic_floor.
  Optimal  = feasible point with the highest equity IRR.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from app.services import audit_logger, model_engine_service, validation_service


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

DEFAULT_AAA_MIN       = 0.55
DEFAULT_AAA_MAX       = 0.72
DEFAULT_AAA_STEP      = 0.005    # 0.5% increments
DEFAULT_MEZ_SIZE      = 0.08     # fixed mezzanine at 8%
DEFAULT_MEZ_COUPON    = "SOFR+200"
DEFAULT_AAA_COUPON    = "SOFR+145"
DEFAULT_OC_FLOOR      = 0.18     # minimum OC cushion (18%)
DEFAULT_IC_FLOOR      = 0.10     # minimum IC cushion (10%)

DEFAULT_SCENARIO = {
    "default_rate":     0.03,
    "recovery_rate":    0.65,
    "spread_shock_bps": 0,
}


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def tranche_optimizer_workflow(
    deal_input: Dict[str, Any],
    aaa_min: float = DEFAULT_AAA_MIN,
    aaa_max: float = DEFAULT_AAA_MAX,
    aaa_step: float = DEFAULT_AAA_STEP,
    mez_size_pct: float = DEFAULT_MEZ_SIZE,
    mez_coupon: str = DEFAULT_MEZ_COUPON,
    aaa_coupon: str = DEFAULT_AAA_COUPON,
    oc_floor: float = DEFAULT_OC_FLOOR,
    ic_floor: float = DEFAULT_IC_FLOOR,
    scenario_parameters: Optional[Dict[str, Any]] = None,
    actor: str = "system",
) -> Dict[str, Any]:
    """
    Find the optimal AAA tranche size for a given pool.

    Args:
        deal_input:          Deal input dict (pool metrics + existing liabilities ignored).
        aaa_min:             Minimum AAA size to test (default 55%).
        aaa_max:             Maximum AAA size to test (default 72%).
        aaa_step:            Step size between candidates (default 0.5%).
        mez_size_pct:        Fixed mezzanine tranche size (default 8%).
        mez_coupon:          Mezzanine coupon descriptor (default SOFR+200).
        aaa_coupon:          AAA coupon descriptor (default SOFR+145).
        oc_floor:            Minimum acceptable AAA OC cushion (default 18%).
        ic_floor:            Minimum acceptable AAA IC cushion (default 10%).
        scenario_parameters: Override base-case engine parameters.
        actor:               Caller identity for audit trail.

    Returns:
        {
            "deal_id":           str,
            "optimization_id":   str,
            "optimised_at":      str,
            "is_mock":           bool,
            "optimal":           Dict | None,   # best feasible structure
            "feasibility_table": List[Dict],    # one row per candidate AAA size
            "frontier":          List[Dict],    # IRR vs AAA size (feasible only)
            "constraints":       Dict,          # oc_floor, ic_floor applied
            "infeasible_reason": str | None,    # set if no feasible point found
            "audit_events":      List[str],
            "error":             str | None,
        }
    """
    optimization_id = f"opt-{uuid.uuid4().hex[:8]}"
    audit_events: List[str] = []
    deal_id = deal_input.get("deal_id", "unknown")

    # ------------------------------------------------------------------
    # Validate
    # ------------------------------------------------------------------
    validation = validation_service.validate_deal_input(deal_input)
    audit_events.append(audit_logger.record_event(
        event_type="deal.validated",
        deal_id=deal_id,
        actor=actor,
        payload={"valid": validation["valid"], "issues": validation["issues"]},
    )["event_id"])

    if not validation["valid"]:
        return _error_result(optimization_id, deal_id, audit_events,
                             "Deal validation failed.")

    # ------------------------------------------------------------------
    # Build candidate AAA sizes
    # ------------------------------------------------------------------
    candidates = _aaa_candidates(aaa_min, aaa_max, aaa_step)
    if not candidates:
        return _error_result(optimization_id, deal_id, audit_events,
                             f"No candidate AAA sizes between {aaa_min:.0%} and {aaa_max:.0%}.")

    params = {**DEFAULT_SCENARIO, **(scenario_parameters or {})}

    pool = deal_input.get("collateral", {})
    portfolio_size = pool.get("portfolio_size", 500_000_000)
    was  = pool.get("was",  0.042)
    wal  = pool.get("wal",  5.2)
    diversity_score = pool.get("diversity_score", 62)
    ccc_bucket      = pool.get("ccc_bucket",      0.055)

    # ------------------------------------------------------------------
    # Run engine for each candidate
    # ------------------------------------------------------------------
    feasibility_table: List[Dict[str, Any]] = []

    for aaa_pct in candidates:
        equity_pct = max(0.01, round(1.0 - aaa_pct - mez_size_pct, 6))

        # Build synthetic tranche stack for this candidate
        tranches = [
            {"tranche_id": "t-aaa", "name": "AAA",    "seniority": 1,
             "size_pct": aaa_pct,    "coupon": aaa_coupon},
            {"tranche_id": "t-mez", "name": "Mez",    "seniority": 2,
             "size_pct": mez_size_pct, "coupon": mez_coupon},
            {"tranche_id": "t-eq",  "name": "Equity", "seniority": 3,
             "size_pct": equity_pct},
        ]

        deal_payload = {
            "deal_id":         deal_id,
            "portfolio_size":  portfolio_size,
            "was":             was,
            "wal":             wal,
            "diversity_score": diversity_score,
            "ccc_bucket":      ccc_bucket,
            "tranches":        tranches,
        }

        scenario_request = {
            "scenario_id":   f"sc-opt-{uuid.uuid4().hex[:6]}",
            "deal_id":       deal_id,
            "name":          f"AAA={aaa_pct:.1%}",
            "scenario_type": "optimization",
            "parameters":    params,
            "deal_payload":  deal_payload,
        }

        try:
            run_id = model_engine_service.submit_scenario(deal_id, scenario_request)
            model_engine_service.poll_until_done(run_id)
            result = model_engine_service.get_result(run_id, scenario_request["scenario_id"], deal_id)
            outputs = result.get("outputs", {})

            oc_cushion = outputs.get("oc_cushion_aaa", 0.0)
            ic_cushion = outputs.get("ic_cushion_aaa", 0.0)
            equity_irr = outputs.get("equity_irr", -0.99)
            feasible   = oc_cushion >= oc_floor and ic_cushion >= ic_floor

            feasibility_table.append({
                "aaa_size_pct":  round(aaa_pct, 4),
                "mez_size_pct":  round(mez_size_pct, 4),
                "equity_size_pct": round(equity_pct, 4),
                "equity_irr":    equity_irr,
                "oc_cushion_aaa": oc_cushion,
                "ic_cushion_aaa": ic_cushion,
                "wac":           outputs.get("wac"),
                "equity_wal":    outputs.get("equity_wal"),
                "scenario_npv":  outputs.get("scenario_npv"),
                "feasible":      feasible,
                "oc_pass":       oc_cushion >= oc_floor,
                "ic_pass":       ic_cushion >= ic_floor,
                "run_id":        run_id,
                "status":        "complete",
            })
        except Exception as exc:  # noqa: BLE001
            feasibility_table.append({
                "aaa_size_pct":  round(aaa_pct, 4),
                "mez_size_pct":  round(mez_size_pct, 4),
                "equity_size_pct": round(equity_pct, 4),
                "equity_irr":    None,
                "oc_cushion_aaa": None,
                "ic_cushion_aaa": None,
                "wac":           None,
                "equity_wal":    None,
                "scenario_npv":  None,
                "feasible":      False,
                "oc_pass":       False,
                "ic_pass":       False,
                "run_id":        None,
                "status":        "failed",
                "error":         str(exc),
            })

    # ------------------------------------------------------------------
    # Find optimal point
    # ------------------------------------------------------------------
    feasible_rows = [r for r in feasibility_table if r["feasible"] and r["equity_irr"] is not None]
    optimal = None
    infeasible_reason = None

    if feasible_rows:
        optimal = max(feasible_rows, key=lambda r: r["equity_irr"])
    else:
        infeasible_reason = _diagnose_infeasibility(feasibility_table, oc_floor, ic_floor)

    # Efficiency frontier: feasible rows sorted by AAA size
    frontier = [
        {"aaa_size_pct": r["aaa_size_pct"], "equity_irr": r["equity_irr"]}
        for r in feasible_rows
    ]

    # ------------------------------------------------------------------
    # Audit
    # ------------------------------------------------------------------
    audit_events.append(audit_logger.record_event(
        event_type="tranche_optimization.completed",
        deal_id=deal_id,
        actor=actor,
        payload={
            "optimization_id":  optimization_id,
            "candidates_tested": len(feasibility_table),
            "feasible_count":   len(feasible_rows),
            "optimal_aaa":      optimal["aaa_size_pct"] if optimal else None,
            "optimal_irr":      optimal["equity_irr"]   if optimal else None,
        },
    )["event_id"])

    return {
        "deal_id":           deal_id,
        "optimization_id":   optimization_id,
        "optimised_at":      datetime.now(timezone.utc).isoformat(),
        "is_mock":           model_engine_service.is_mock_mode(),
        "optimal":           optimal,
        "feasibility_table": feasibility_table,
        "frontier":          frontier,
        "constraints": {
            "oc_floor":      oc_floor,
            "ic_floor":      ic_floor,
            "aaa_min":       aaa_min,
            "aaa_max":       aaa_max,
            "mez_size_pct":  mez_size_pct,
        },
        "infeasible_reason": infeasible_reason,
        "audit_events":      audit_events,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _aaa_candidates(aaa_min: float, aaa_max: float, step: float) -> List[float]:
    """Generate candidate AAA sizes from min to max inclusive."""
    candidates = []
    val = aaa_min
    while val <= aaa_max + 1e-9:
        candidates.append(round(val, 6))
        val = round(val + step, 6)
    return candidates


def _diagnose_infeasibility(
    table: List[Dict],
    oc_floor: float,
    ic_floor: float,
) -> str:
    """Explain why no feasible structure was found."""
    completed = [r for r in table if r["status"] == "complete"]
    if not completed:
        return "All engine runs failed — no feasibility data available."

    oc_fails = sum(1 for r in completed if not r.get("oc_pass", False))
    ic_fails = sum(1 for r in completed if not r.get("ic_pass", False))

    if oc_fails == len(completed):
        max_oc = max((r["oc_cushion_aaa"] or 0) for r in completed)
        return (
            f"OC cushion below floor ({oc_floor:.0%}) for all candidates. "
            f"Best OC seen: {max_oc:.1%}. "
            "Consider reducing pool leverage or adjusting the OC floor."
        )
    if ic_fails == len(completed):
        max_ic = max((r["ic_cushion_aaa"] or 0) for r in completed)
        return (
            f"IC cushion below floor ({ic_floor:.0%}) for all candidates. "
            f"Best IC seen: {max_ic:.1%}. "
            "Consider increasing WAS or reducing debt cost."
        )
    return (
        f"No structure satisfies both OC >= {oc_floor:.0%} and IC >= {ic_floor:.0%} "
        f"simultaneously. Try relaxing constraints."
    )


def _error_result(
    optimization_id: str,
    deal_id: str,
    audit_events: List[str],
    error: str,
) -> Dict[str, Any]:
    return {
        "deal_id":           deal_id,
        "optimization_id":   optimization_id,
        "optimised_at":      datetime.now(timezone.utc).isoformat(),
        "is_mock":           model_engine_service.is_mock_mode(),
        "optimal":           None,
        "feasibility_table": [],
        "frontier":          [],
        "constraints":       {},
        "infeasible_reason": None,
        "audit_events":      audit_events,
        "error":             error,
    }
