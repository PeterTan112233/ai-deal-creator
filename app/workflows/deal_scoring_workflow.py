"""
app/workflows/deal_scoring_workflow.py

Compute a composite risk/return score for a deal.

Steps:
  1. Validate deal input
  2. Run base-case scenario to get key metrics
  3. Run a quick stress test (gfc-2008 + deep-stress) for IRR drawdown
  4. Compute scoring via scoring_service
  5. Emit audit event and return structured score result

IMPORTANT: All outputs tagged [demo]. Not for investment decisions.
"""

from typing import Any, Dict, Optional

from app.services import audit_logger, model_engine_service, validation_service, scoring_service
from app.services import scenario_template_service
from app.workflows.run_scenario_workflow import run_scenario_workflow


_BASE_PARAMS = {
    "default_rate": 0.030,
    "recovery_rate": 0.650,
    "spread_shock_bps": 0.0,
}

# Stress templates used for resilience scoring
_STRESS_TEMPLATE_IDS = ["gfc-2008", "deep-stress"]


def deal_scoring_workflow(
    deal_input: Dict[str, Any],
    actor: str = "system",
) -> Dict[str, Any]:
    """
    Score a deal on a 0-100 composite scale.

    Parameters
    ----------
    deal_input : Deal input dict (validated internally).
    actor      : Caller identity for audit trail.

    Returns
    -------
    {
        "deal_id":          str,
        "scoring_id":       str,
        "scored_at":        str,
        "composite_score":  float,       # 0-100
        "grade":            str,         # A / B / C / D
        "grade_label":      str,         # Strong / Adequate / Marginal / Weak
        "dimension_scores": Dict,
        "top_drivers":      List[str],
        "risk_flags":       List[str],
        "score_report":     str,
        "audit_events":     List[str],
        "is_mock":          bool,
        "error":            str | None,
    }
    """
    import uuid
    from datetime import datetime, timezone

    scoring_id = f"score-{uuid.uuid4().hex[:8]}"
    audit_events = []
    deal_id = deal_input.get("deal_id", "unknown")

    # ------------------------------------------------------------------
    # Validate
    # ------------------------------------------------------------------
    validation = validation_service.validate_deal_input(deal_input)
    if not validation.get("valid"):
        return _result(scoring_id, deal_id, None, audit_events,
                       error=f"Deal validation failed: {validation.get('errors', [])}")

    # ------------------------------------------------------------------
    # Base-case scenario
    # ------------------------------------------------------------------
    base_scen = run_scenario_workflow(
        deal_input=deal_input,
        scenario_name="Scoring Base",
        scenario_type="base",
        parameter_overrides=_BASE_PARAMS,
        actor=actor,
    )
    audit_events.extend(base_scen.get("audit_events", []))
    if base_scen.get("error"):
        return _result(scoring_id, deal_id, None, audit_events,
                       error=f"Base scenario failed: {base_scen['error']}")

    base_outputs = (base_scen.get("scenario_result") or {}).get("outputs", {})
    base_irr = base_outputs.get("equity_irr")

    # ------------------------------------------------------------------
    # Stress scenarios (for resilience dimension)
    # ------------------------------------------------------------------
    stress_irrs = []
    for tid in _STRESS_TEMPLATE_IDS:
        tmpl = scenario_template_service.get_template(tid)
        if tmpl is None:
            continue
        scen = run_scenario_workflow(
            deal_input=deal_input,
            scenario_name=tmpl["name"],
            scenario_type=tmpl["scenario_type"],
            parameter_overrides=dict(tmpl["parameters"]),
            actor=actor,
        )
        audit_events.extend(scen.get("audit_events", []))
        irr = (scen.get("scenario_result") or {}).get("outputs", {}).get("equity_irr")
        if irr is not None:
            stress_irrs.append(irr)

    worst_stress_irr = min(stress_irrs) if stress_irrs else None
    stress_drawdown = (
        round(base_irr - worst_stress_irr, 6)
        if base_irr is not None and worst_stress_irr is not None
        else None
    )

    # ------------------------------------------------------------------
    # Compute score
    # ------------------------------------------------------------------
    collateral = deal_input.get("collateral", {})
    score_result = scoring_service.score_deal(
        key_metrics=base_outputs,
        collateral=collateral,
        stress_drawdown=stress_drawdown,
    )

    # ------------------------------------------------------------------
    # Formatted report
    # ------------------------------------------------------------------
    score_report = _format_report(deal_input, score_result, scoring_id, stress_drawdown)

    # ------------------------------------------------------------------
    # Audit
    # ------------------------------------------------------------------
    audit_events.append(audit_logger.record_event(
        event_type="deal.scored",
        deal_id=deal_id,
        actor=actor,
        payload={
            "scoring_id":      scoring_id,
            "composite_score": score_result["composite_score"],
            "grade":           score_result["grade"],
        },
    )["event_id"])

    return _result(scoring_id, deal_id, score_result, audit_events,
                   score_report=score_report)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _format_report(
    deal_input: Dict[str, Any],
    score_result: Dict[str, Any],
    scoring_id: str,
    stress_drawdown: Optional[float],
) -> str:
    from typing import List
    deal_name = deal_input.get("name", deal_input.get("deal_id", "Unknown"))
    deal_id   = deal_input.get("deal_id", "unknown")
    grade     = score_result["grade"]
    label     = score_result["grade_label"]
    composite = score_result["composite_score"]
    dims      = score_result["dimension_scores"]

    lines: List[str] = [
        "=" * 64,
        "  DEAL SCORE REPORT  [demo]",
        f"  {deal_name}  (ID: {deal_id})",
        f"  Scoring ID: {scoring_id}",
        "",
        "  ALL OUTPUTS FROM DEMO_ANALYTICAL_ENGINE — NOT FOR INVESTMENT USE",
        "=" * 64,
        "",
        f"  COMPOSITE SCORE  [demo]:  {composite:.1f} / 100   |   Grade: {grade}  ({label})",
        "",
    ]

    # Grade bar
    filled = int(composite / 5)
    bar    = "█" * filled + "░" * (20 - filled)
    lines.append(f"  [{bar}]  {composite:.0f}%")
    lines.append("")

    # Dimension breakdown
    lines += ["DIMENSION BREAKDOWN  [demo]", "-" * 64]
    for dim_name, dim in dims.items():
        s = dim["score"]
        w = dim["weight"]
        contrib = s * w
        bar2 = "█" * int(s / 5) + "░" * (20 - int(s / 5))
        lines.append(
            f"  {dim_name:<22} {s:>5.1f}/100  (wt {w:.0%}) → {contrib:>4.1f}pts  [{bar2}]"
        )
        lines.append(f"    {dim['label']}")
    lines.append("")

    # Top drivers
    drivers = score_result.get("top_drivers", [])
    if drivers:
        lines += ["TOP SCORE DRIVERS  [demo]", "-" * 64]
        for d in drivers:
            lines.append(f"  + {d}")
        lines.append("")

    # Risk flags
    flags = score_result.get("risk_flags", [])
    if flags:
        lines += ["RISK FLAGS  [demo]", "-" * 64]
        for f in flags:
            lines.append(f"  ⚑  {f}")
        lines.append("")

    lines += [
        "=" * 64,
        "  [demo] All outputs from DEMO_ANALYTICAL_ENGINE.",
        "=" * 64,
    ]
    return "\n".join(lines)


def _result(
    scoring_id: str,
    deal_id: str,
    score_result: Optional[Dict[str, Any]],
    audit_events,
    score_report: str = "",
    error: Optional[str] = None,
) -> Dict[str, Any]:
    from datetime import datetime, timezone
    base = {
        "deal_id":          deal_id,
        "scoring_id":       scoring_id,
        "scored_at":        datetime.now(timezone.utc).isoformat(),
        "audit_events":     audit_events,
        "score_report":     score_report,
        "is_mock":          model_engine_service.is_mock_mode(),
        "error":            error,
    }
    if score_result:
        base.update({
            "composite_score":  score_result["composite_score"],
            "grade":            score_result["grade"],
            "grade_label":      score_result["grade_label"],
            "dimension_scores": score_result["dimension_scores"],
            "top_drivers":      score_result["top_drivers"],
            "risk_flags":       score_result["risk_flags"],
        })
    else:
        base.update({
            "composite_score":  None,
            "grade":            None,
            "grade_label":      None,
            "dimension_scores": {},
            "top_drivers":      [],
            "risk_flags":       [],
        })
    return base
