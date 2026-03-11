"""
app/workflows/portfolio_stress_workflow.py

Cross-deal portfolio stress testing.

For each deal in the input list, runs a set of named stress scenario
templates and aggregates the results across the whole portfolio.

Key outputs:
  - Per-deal worst-case IRR and IRR drawdown (base minus worst-case)
  - Risk ranking: which deals are most vulnerable to stress?
  - Most impactful template: which template causes the most average IRR damage?
  - Full per-deal, per-template result matrix

This is the "stress battery across the pipeline" entry point: one call to
see how every deal in your pipeline holds up under GFC, COVID, and
deep-stress scenarios, side-by-side.

IMPORTANT: All outputs tagged [demo]. Not for investment decisions.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.services import audit_logger, model_engine_service, validation_service
from app.services import scenario_template_service
from app.workflows.run_scenario_workflow import run_scenario_workflow


# ---------------------------------------------------------------------------
# Base-case parameters (used to compute the IRR drawdown)
# ---------------------------------------------------------------------------

_BASE_PARAMS = {
    "default_rate": 0.030,
    "recovery_rate": 0.650,
    "spread_shock_bps": 0.0,
}


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def portfolio_stress_workflow(
    deal_inputs: List[Dict[str, Any]],
    template_ids: Optional[List[str]] = None,
    scenario_type: Optional[str] = None,
    tag: Optional[str] = None,
    actor: str = "system",
) -> Dict[str, Any]:
    """
    Run a stress template battery across a list of deals.

    Parameters
    ----------
    deal_inputs   : List of deal input dicts.
    template_ids  : Explicit template IDs to run. If None, uses all templates
                    matching scenario_type / tag filters.
    scenario_type : Filter templates by type (e.g. "stress").
    tag           : Filter templates by tag (e.g. "historical").
    actor         : Caller identity for audit trail.

    Returns
    -------
    {
        "stress_id":              str,
        "run_at":                 str,
        "deal_count":             int,
        "template_count":         int,
        "deals":                  List[per-deal stress result],
        "risk_ranking":           List[{deal_id, name, irr_drawdown, rank}],
        "most_sensitive_template": str | None,
        "portfolio_report":       str,
        "audit_events":           List[str],
        "is_mock":                bool,
        "error":                  str | None,
    }
    """
    stress_id = f"stress-{uuid.uuid4().hex[:8]}"
    audit_events: List[str] = []

    if not deal_inputs:
        return _result(stress_id, [], [], None, "", audit_events,
                       error="No deal inputs provided.")

    # ------------------------------------------------------------------
    # Resolve template list once (shared across all deals)
    # ------------------------------------------------------------------
    if template_ids is not None:
        templates = [
            t for tid in template_ids
            if (t := scenario_template_service.get_template(tid)) is not None
        ]
    else:
        templates = scenario_template_service.list_templates(
            scenario_type=scenario_type, tag=tag
        )

    if not templates:
        return _result(stress_id, [], [], None, "", audit_events,
                       error="No templates matched the specified filters.")

    # ------------------------------------------------------------------
    # Process each deal
    # ------------------------------------------------------------------
    deal_results: List[Dict[str, Any]] = []
    for deal_input in deal_inputs:
        deal_id = deal_input.get("deal_id", "unknown")

        validation = validation_service.validate_deal_input(deal_input)
        if not validation.get("valid"):
            deal_results.append({
                "deal_id":          deal_id,
                "name":             deal_input.get("name", ""),
                "base_irr":         None,
                "worst_case_irr":   None,
                "irr_drawdown":     None,
                "template_results": [],
                "status":           "error",
                "error":            f"Validation failed: {validation.get('errors', [])}",
            })
            continue

        # Run base-case to get reference IRR
        base_scen = run_scenario_workflow(
            deal_input=deal_input,
            scenario_name="Stress Base",
            scenario_type="base",
            parameter_overrides=_BASE_PARAMS,
            actor=actor,
        )
        audit_events.extend(base_scen.get("audit_events", []))
        base_outputs = (base_scen.get("scenario_result") or {}).get("outputs", {})
        base_irr = base_outputs.get("equity_irr")

        # Run each stress template
        tmpl_results: List[Dict[str, Any]] = []
        for tmpl in templates:
            params = dict(tmpl["parameters"])
            scen = run_scenario_workflow(
                deal_input=deal_input,
                scenario_name=tmpl["name"],
                scenario_type=tmpl["scenario_type"],
                parameter_overrides=params,
                actor=actor,
            )
            audit_events.extend(scen.get("audit_events", []))
            scen_result = scen.get("scenario_result") or {}
            outputs = scen_result.get("outputs", {})
            status = "complete" if not scen.get("error") else "failed"
            tmpl_results.append({
                "template_id":   tmpl["template_id"],
                "template_name": tmpl["name"],
                "scenario_type": tmpl["scenario_type"],
                "outputs":       outputs,
                "status":        status,
                "error":         scen.get("error"),
            })

        # Derive worst-case IRR and drawdown
        irr_values = [
            r["outputs"].get("equity_irr")
            for r in tmpl_results
            if r["status"] == "complete" and r["outputs"].get("equity_irr") is not None
        ]
        worst_case_irr = min(irr_values) if irr_values else None
        irr_drawdown = (
            round(base_irr - worst_case_irr, 6)
            if base_irr is not None and worst_case_irr is not None
            else None
        )

        deal_results.append({
            "deal_id":          deal_id,
            "name":             deal_input.get("name", ""),
            "base_irr":         base_irr,
            "worst_case_irr":   worst_case_irr,
            "irr_drawdown":     irr_drawdown,
            "template_results": tmpl_results,
            "status":           "ok",
            "error":            None,
        })

    # ------------------------------------------------------------------
    # Risk ranking (most drawdown first)
    # ------------------------------------------------------------------
    ok_deals = [d for d in deal_results if d["status"] == "ok" and d["irr_drawdown"] is not None]
    risk_ranking = _build_risk_ranking(ok_deals)

    # ------------------------------------------------------------------
    # Most sensitive template (causes most average IRR damage)
    # ------------------------------------------------------------------
    most_sensitive = _find_most_sensitive_template(ok_deals)

    # ------------------------------------------------------------------
    # Report
    # ------------------------------------------------------------------
    portfolio_report = _format_report(
        deal_results, risk_ranking, most_sensitive, templates, stress_id,
    )

    # ------------------------------------------------------------------
    # Audit
    # ------------------------------------------------------------------
    audit_events.append(audit_logger.record_event(
        event_type="portfolio_stress.completed",
        deal_id="portfolio",
        actor=actor,
        payload={
            "stress_id":     stress_id,
            "deal_count":    len(deal_inputs),
            "template_count": len(templates),
            "ok_count":      len(ok_deals),
        },
    )["event_id"])

    return _result(stress_id, deal_results, risk_ranking, most_sensitive,
                   portfolio_report, audit_events)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_risk_ranking(ok_deals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    ranked = sorted(ok_deals, key=lambda d: d["irr_drawdown"] or 0, reverse=True)
    return [
        {
            "deal_id":      d["deal_id"],
            "name":         d["name"],
            "base_irr":     d["base_irr"],
            "worst_case_irr": d["worst_case_irr"],
            "irr_drawdown": d["irr_drawdown"],
            "rank":         i + 1,
        }
        for i, d in enumerate(ranked)
    ]


def _find_most_sensitive_template(ok_deals: List[Dict[str, Any]]) -> Optional[str]:
    """Template whose average IRR gap vs base is largest across all deals."""
    template_damage: Dict[str, List[float]] = {}

    for deal in ok_deals:
        base_irr = deal.get("base_irr")
        if base_irr is None:
            continue
        for tr in deal.get("template_results", []):
            if tr["status"] != "complete":
                continue
            irr = tr["outputs"].get("equity_irr")
            if irr is None:
                continue
            tid = tr["template_id"]
            template_damage.setdefault(tid, []).append(base_irr - irr)

    if not template_damage:
        return None

    avg_damage = {tid: sum(vals) / len(vals) for tid, vals in template_damage.items()}
    return max(avg_damage, key=avg_damage.__getitem__)


def _format_report(
    deal_results: List[Dict[str, Any]],
    risk_ranking: List[Dict[str, Any]],
    most_sensitive: Optional[str],
    templates: List[Dict[str, Any]],
    stress_id: str,
) -> str:
    ok   = [d for d in deal_results if d["status"] == "ok"]
    err  = [d for d in deal_results if d["status"] != "ok"]
    lines: List[str] = []

    # Header
    lines += [
        "=" * 72,
        "  PORTFOLIO STRESS TEST REPORT  [demo]",
        f"  Stress ID: {stress_id}",
        f"  Deals: {len(ok)} ok  /  {len(err)} errors  /  {len(deal_results)} total",
        f"  Templates: {len(templates)} scenarios applied per deal",
        "",
        "  ALL OUTPUTS FROM DEMO_ANALYTICAL_ENGINE — NOT OFFICIAL CLO OUTPUTS",
        "=" * 72,
        "",
    ]

    # Per-deal summary table
    if ok:
        tmpl_names = [t["template_id"] for t in templates[:4]]  # cap at 4 for width
        header = f"  {'Deal':<22} {'Base IRR':>9} {'Worst IRR':>10} {'Drawdown':>9}"
        lines += ["DEAL STRESS SUMMARY  [demo]", "-" * 72, header, "  " + "-" * 54]
        for d in deal_results:
            name = (d["name"] or d["deal_id"])[:22]
            base  = f"{d['base_irr']:.1%}"  if d.get("base_irr")  is not None else "n/a"
            worst = f"{d['worst_case_irr']:.1%}" if d.get("worst_case_irr") is not None else "n/a"
            dd    = f"{d['irr_drawdown']:.1%}"  if d.get("irr_drawdown") is not None else "n/a"
            tag   = " [error]" if d["status"] == "error" else ""
            lines.append(f"  {name:<22} {base:>9} {worst:>10} {dd:>9}{tag}")
        lines.append("")

    # Risk ranking
    if risk_ranking:
        lines += ["RISK RANKING (most drawdown first)  [demo]", "-" * 72]
        for e in risk_ranking:
            bar = "█" * max(0, int((e["irr_drawdown"] or 0) * 100))
            lines.append(
                f"  #{e['rank']:>2}  {(e['name'] or e['deal_id']):<28}"
                f"  drawdown {e['irr_drawdown']:.1%}  {bar}"
            )
        lines.append("")

    # Most sensitive template
    if most_sensitive:
        lines += [
            "MOST IMPACTFUL TEMPLATE  [demo]",
            "-" * 72,
            f"  {most_sensitive}  (largest average IRR drawdown across all deals)",
            "",
        ]

    # Footer
    lines += [
        "=" * 72,
        "  [demo] All outputs from DEMO_ANALYTICAL_ENGINE.",
        "  Replace with real cashflow-engine-mcp outputs in Phase 2.",
        "=" * 72,
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Result builder
# ---------------------------------------------------------------------------

def _result(
    stress_id: str,
    deals: List[Dict],
    risk_ranking: List[Dict],
    most_sensitive: Optional[str],
    portfolio_report: str,
    audit_events: List[str],
    error: Optional[str] = None,
) -> Dict[str, Any]:
    templates_run = max(
        (len(d.get("template_results", [])) for d in deals if d.get("status") == "ok"),
        default=0,
    )
    return {
        "stress_id":               stress_id,
        "run_at":                  datetime.now(timezone.utc).isoformat(),
        "deal_count":              len(deals),
        "template_count":          templates_run,
        "deals":                   deals,
        "risk_ranking":            risk_ranking,
        "most_sensitive_template": most_sensitive,
        "portfolio_report":        portfolio_report,
        "audit_events":            audit_events,
        "is_mock":                 model_engine_service.is_mock_mode(),
        "error":                   error,
    }
