"""
app/workflows/compare_versions_workflow.py

Thin orchestrator for comparing two deal versions or two scenario results.

Wraps comparison_service calls with audit logging.
Does not perform any computation itself.

Usage modes:
  1. Deal input comparison only:   provide v1_deal + v2_deal, no results
  2. Scenario result comparison:   provide v1_deal + v1_result + v2_result
     (v2_deal optional — used only to source parameters when missing from v2_result)
  3. Both simultaneously:          provide v1_deal + v2_deal + v1_result + v2_result
"""

from typing import Dict, Optional

from app.services import comparison_service
from app.services.audit_logger import record_event


def compare_versions_workflow(
    v1_deal: Dict,
    v2_deal: Optional[Dict] = None,
    v1_result: Optional[Dict] = None,
    v2_result: Optional[Dict] = None,
    actor: str = "system",
) -> Dict:
    """
    Run a deal-input diff, scenario-result diff, or both.

    Parameters
    ----------
    v1_deal     : Required. Base deal input dict.
    v2_deal     : Optional. Revised deal input dict. Required for deal comparison mode.
    v1_result   : Optional. Scenario result dict for v1 (from model_engine_service.get_result).
    v2_result   : Optional. Scenario result dict for v2. Required for scenario comparison mode.
    actor       : Identifies the caller in audit events.

    Returns
    -------
    {
        deal_comparison:     None | dict from comparison_service.compare_deal_inputs
        scenario_comparison: None | dict from comparison_service.compare_scenario_results
        summary:             str  — combined grounded text summary
        audit_events:        list — comparison.started + comparison.completed
        error:               str  — present only on bad input
    }
    """
    deal_id = v1_deal.get("deal_id", "unknown")
    audit_events = []

    compare_deals = v2_deal is not None
    compare_results = v1_result is not None and v2_result is not None

    if not compare_deals and not compare_results:
        return {
            "error": (
                "Must provide v2_deal (deal comparison) or both v1_result and v2_result "
                "(scenario comparison), or all three for a combined comparison."
            ),
            "deal_comparison": None,
            "scenario_comparison": None,
            "summary": None,
            "audit_events": [],
        }

    audit_events.append(record_event(
        event_type="comparison.started",
        deal_id=deal_id,
        payload={
            "compare_deals": compare_deals,
            "compare_results": compare_results,
            "v1_deal_id": v1_deal.get("deal_id"),
            "v2_deal_id": v2_deal.get("deal_id") if v2_deal else None,
            "v1_run_id": v1_result.get("run_id") if v1_result else None,
            "v2_run_id": v2_result.get("run_id") if v2_result else None,
        },
        actor=actor,
    ))

    deal_comparison = None
    scenario_comparison = None
    summaries = []

    if compare_deals:
        deal_comparison = comparison_service.compare_deal_inputs(v1_deal, v2_deal)
        summaries.append(
            comparison_service.generate_comparison_summary(
                deal_comparison, mode="deal_inputs"
            )
        )

    if compare_results:
        # Source parameters from market_assumptions if not already in the result dicts
        p1 = v1_result.get("parameters") or v1_deal.get("market_assumptions", {})
        p2 = (
            v2_result.get("parameters")
            or (v2_deal or {}).get("market_assumptions", {})
            or v1_deal.get("market_assumptions", {})
        )
        scenario_comparison = comparison_service.compare_scenario_results(
            v1_result, v2_result, v1_params=p1, v2_params=p2
        )
        summaries.append(
            comparison_service.generate_comparison_summary(
                scenario_comparison, mode="scenario"
            )
        )

    summary = "\n\n".join(summaries)

    audit_events.append(record_event(
        event_type="comparison.completed",
        deal_id=deal_id,
        payload={
            "deal_change_count": deal_comparison.get("change_count") if deal_comparison else None,
            "scenario_change_count": (
                scenario_comparison.get("change_count") if scenario_comparison else None
            ),
        },
        actor=actor,
    ))

    return {
        "deal_comparison": deal_comparison,
        "scenario_comparison": scenario_comparison,
        "summary": summary,
        "audit_events": audit_events,
    }
