"""
app/workflows/deal_health_workflow.py

Deal Health Check — a unified analytical snapshot for a single deal.

Synthesises outputs from three existing workflows into one report:
  1. deal_scoring_workflow      → composite grade, top drivers, risk flags
  2. run_scenario_workflow ×3   → base IRR + two stress IRRs (drawdown)
  3. watchlist_check_workflow   → triggered threshold alerts

Then derives Key Risk Indicators (KRIs) from all results and produces
concrete Action Items and a formatted [demo] health report.

Designed to be run at-a-glance by a portfolio manager who wants a single
call that answers: "How is this deal doing right now?"

IMPORTANT: All outputs tagged [demo]. Not for investment decisions.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.services import audit_logger, model_engine_service, validation_service
from app.workflows.deal_scoring_workflow import deal_scoring_workflow
from app.workflows.run_scenario_workflow import run_scenario_workflow
from app.workflows.watchlist_workflow import watchlist_check_workflow


# Stress scenarios used for the health check drawdown (lightweight — 2 only)
_HEALTH_STRESS_TEMPLATES = ["stress", "deep-stress"]

_BASE_PARAMS = {
    "default_rate": 0.030,
    "recovery_rate": 0.650,
    "spread_shock_bps": 0.0,
}

# KRI thresholds
_KRI_THRESHOLDS: Dict[str, Dict] = {
    "equity_irr":         {"ok": 0.10,  "warn": 0.05,  "direction": "higher_better"},
    "oc_cushion_aaa":     {"ok": 0.05,  "warn": 0.00,  "direction": "higher_better"},
    "irr_drawdown":       {"ok": 0.03,  "warn": 0.07,  "direction": "lower_better"},
    "composite_score":    {"ok": 75.0,  "warn": 55.0,  "direction": "higher_better"},
    "ccc_bucket":         {"ok": 0.05,  "warn": 0.07,  "direction": "lower_better"},
    "diversity_score":    {"ok": 40.0,  "warn": 25.0,  "direction": "higher_better"},
}


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def deal_health_workflow(
    deal_input: Dict[str, Any],
    actor: str = "system",
) -> Dict[str, Any]:
    """
    Run a unified health check on a deal.

    Parameters
    ----------
    deal_input : Deal input dict (validated internally).
    actor      : Caller identity for audit trail.

    Returns
    -------
    {
        "health_id":            str,
        "deal_id":              str,
        "checked_at":           str,
        "overall_grade":        str,          # A / B / C / D
        "overall_score":        float | None, # composite 0–100
        "score_summary":        Dict,         # grade, top_drivers, risk_flags
        "stress_summary":       Dict,         # base_irr, min_stress_irr, drawdown
        "watchlist_summary":    Dict,         # triggered_count, critical_count, alerts
        "key_risk_indicators":  List[Dict],   # name, value, status, threshold
        "action_items":         List[str],    # concrete follow-up items
        "health_report":        str,          # formatted [demo] report
        "audit_events":         List[str],
        "is_mock":              bool,
        "error":                str | None,
    }
    """
    health_id = f"health-{uuid.uuid4().hex[:8]}"
    audit_events: List[str] = []
    deal_id = deal_input.get("deal_id", "unknown")

    # ------------------------------------------------------------------
    # Validate
    # ------------------------------------------------------------------
    validation = validation_service.validate_deal_input(deal_input)
    if not validation.get("valid"):
        return _result(health_id, deal_id, None, {}, {}, {}, [], [],
                       audit_events,
                       error=f"Validation failed: {validation.get('errors', [])}")

    # ------------------------------------------------------------------
    # 1. Scoring (grade + top drivers + risk flags)
    # ------------------------------------------------------------------
    scored = deal_scoring_workflow(deal_input=deal_input, actor=actor)
    audit_events.extend(scored.get("audit_events", []))

    score_summary = {
        "composite_score": scored.get("composite_score"),
        "grade":           scored.get("grade"),
        "grade_label":     scored.get("grade_label"),
        "top_drivers":     scored.get("top_drivers", []),
        "risk_flags":      scored.get("risk_flags", []),
        "dimension_scores": scored.get("dimension_scores", {}),
    }

    # ------------------------------------------------------------------
    # 2. Quick stress: base-case + 2 stress templates
    # ------------------------------------------------------------------
    base_scen = run_scenario_workflow(
        deal_input=deal_input,
        scenario_name="Health Base",
        scenario_type="base",
        parameter_overrides=_BASE_PARAMS,
        actor=actor,
    )
    audit_events.extend(base_scen.get("audit_events", []))
    base_outputs = (base_scen.get("scenario_result") or {}).get("outputs", {})
    base_irr = base_outputs.get("equity_irr")
    base_oc  = base_outputs.get("oc_cushion_aaa")

    stress_irrs: List[float] = []
    stress_runs: List[Dict] = []
    for tid in _HEALTH_STRESS_TEMPLATES:
        from app.services import scenario_template_service
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
        outputs = (scen.get("scenario_result") or {}).get("outputs", {})
        irr = outputs.get("equity_irr")
        if irr is not None:
            stress_irrs.append(irr)
        stress_runs.append({
            "template_id":   tid,
            "template_name": tmpl["name"],
            "equity_irr":    irr,
            "oc_cushion":    outputs.get("oc_cushion_aaa"),
        })

    min_stress_irr = min(stress_irrs) if stress_irrs else None
    irr_drawdown = (
        round(base_irr - min_stress_irr, 6)
        if base_irr is not None and min_stress_irr is not None
        else None
    )

    stress_summary = {
        "base_irr":      base_irr,
        "base_oc":       base_oc,
        "min_stress_irr": min_stress_irr,
        "irr_drawdown":  irr_drawdown,
        "stress_runs":   stress_runs,
    }

    # ------------------------------------------------------------------
    # 3. Watchlist check
    # ------------------------------------------------------------------
    wl = watchlist_check_workflow(deal_input=deal_input, actor=actor)
    audit_events.extend(wl.get("audit_events", []))
    triggered_alerts = [a for a in wl.get("alerts", []) if a.get("triggered")]
    critical_count   = sum(1 for a in triggered_alerts if a.get("severity") == "critical")
    watchlist_summary = {
        "items_checked":   wl.get("items_checked", 0),
        "triggered_count": wl.get("triggered_count", 0),
        "critical_count":  critical_count,
        "triggered_alerts": triggered_alerts,
    }

    # ------------------------------------------------------------------
    # 4. Key Risk Indicators
    # ------------------------------------------------------------------
    collateral = deal_input.get("collateral", {})
    kri_inputs = {
        "equity_irr":      base_irr,
        "oc_cushion_aaa":  base_oc,
        "irr_drawdown":    irr_drawdown,
        "composite_score": scored.get("composite_score"),
        "ccc_bucket":      collateral.get("ccc_bucket"),
        "diversity_score": collateral.get("diversity_score"),
    }
    key_risk_indicators = _build_kris(kri_inputs)

    # ------------------------------------------------------------------
    # 5. Action items
    # ------------------------------------------------------------------
    action_items = _build_action_items(key_risk_indicators, watchlist_summary, score_summary)

    # ------------------------------------------------------------------
    # 6. Overall grade (from scoring)
    # ------------------------------------------------------------------
    overall_grade = scored.get("grade") or "D"
    overall_score = scored.get("composite_score")

    # ------------------------------------------------------------------
    # 7. Report
    # ------------------------------------------------------------------
    health_report = _format_health_report(
        deal_input, health_id, overall_grade, overall_score,
        score_summary, stress_summary, watchlist_summary,
        key_risk_indicators, action_items,
    )

    # ------------------------------------------------------------------
    # 8. Audit
    # ------------------------------------------------------------------
    critical_kris = sum(1 for k in key_risk_indicators if k["status"] == "critical")
    audit_events.append(audit_logger.record_event(
        event_type="deal_health.checked",
        deal_id=deal_id,
        actor=actor,
        payload={
            "health_id":     health_id,
            "overall_grade": overall_grade,
            "overall_score": overall_score,
            "critical_kris": critical_kris,
            "action_items":  len(action_items),
        },
    )["event_id"])

    return _result(
        health_id, deal_id, overall_grade, score_summary,
        stress_summary, watchlist_summary,
        key_risk_indicators, action_items,
        audit_events,
        overall_score=overall_score,
        health_report=health_report,
    )


# ---------------------------------------------------------------------------
# KRI builder
# ---------------------------------------------------------------------------

def _kri_status(value: Optional[float], thresholds: Dict) -> str:
    """Return 'ok', 'warn', or 'critical' based on thresholds."""
    if value is None:
        return "unknown"
    direction = thresholds["direction"]
    ok_thresh  = thresholds["ok"]
    warn_thresh = thresholds["warn"]
    if direction == "higher_better":
        if value >= ok_thresh:
            return "ok"
        if value >= warn_thresh:
            return "warn"
        return "critical"
    else:  # lower_better
        if value <= ok_thresh:
            return "ok"
        if value <= warn_thresh:
            return "warn"
        return "critical"


def _build_kris(inputs: Dict[str, Optional[float]]) -> List[Dict[str, Any]]:
    kris = []
    labels = {
        "equity_irr":      "Equity IRR",
        "oc_cushion_aaa":  "OC Cushion (AAA)",
        "irr_drawdown":    "IRR Drawdown (stress)",
        "composite_score": "Composite Score",
        "ccc_bucket":      "CCC Bucket",
        "diversity_score": "Diversity Score",
    }
    formats = {
        "equity_irr":      "pct",
        "oc_cushion_aaa":  "pct+",
        "irr_drawdown":    "pct",
        "composite_score": "score",
        "ccc_bucket":      "pct",
        "diversity_score": "int",
    }
    for key, thresholds in _KRI_THRESHOLDS.items():
        value  = inputs.get(key)
        status = _kri_status(value, thresholds)
        kris.append({
            "name":      key,
            "label":     labels[key],
            "value":     value,
            "format":    formats[key],
            "status":    status,
            "direction": thresholds["direction"],
            "ok_threshold":   thresholds["ok"],
            "warn_threshold": thresholds["warn"],
        })
    return kris


# ---------------------------------------------------------------------------
# Action items
# ---------------------------------------------------------------------------

def _build_action_items(
    kris: List[Dict],
    watchlist_summary: Dict,
    score_summary: Dict,
) -> List[str]:
    items: List[str] = []
    kri_map = {k["name"]: k for k in kris}

    if kri_map.get("equity_irr", {}).get("status") == "critical":
        items.append("Review equity IRR drivers — currently below minimum acceptable level.")
    elif kri_map.get("equity_irr", {}).get("status") == "warn":
        items.append("Monitor equity IRR — approaching warning threshold.")

    if kri_map.get("oc_cushion_aaa", {}).get("status") == "critical":
        items.append("OC cushion is below zero — consider reducing AAA tranche size.")
    elif kri_map.get("oc_cushion_aaa", {}).get("status") == "warn":
        items.append("OC cushion is thin — run optimizer to find a more resilient structure.")

    if kri_map.get("irr_drawdown", {}).get("status") == "critical":
        items.append("High stress IRR drawdown — deal is highly vulnerable to adverse scenarios.")
    elif kri_map.get("irr_drawdown", {}).get("status") == "warn":
        items.append("Moderate stress drawdown — review collateral quality and default assumptions.")

    if kri_map.get("composite_score", {}).get("status") in ("critical", "warn"):
        top_d = score_summary.get("top_drivers", [])
        driver_str = f" ({', '.join(top_d)})" if top_d else ""
        items.append(f"Composite score is below threshold{driver_str} — review scoring dimensions.")

    if kri_map.get("ccc_bucket", {}).get("status") == "critical":
        items.append("CCC bucket exceeds 7% — diversify collateral or reduce CCC exposure.")
    elif kri_map.get("ccc_bucket", {}).get("status") == "warn":
        items.append("CCC bucket approaching limit — monitor collateral quality closely.")

    if kri_map.get("diversity_score", {}).get("status") == "critical":
        items.append("Diversity score is critically low — concentration risk is elevated.")

    risk_flags = score_summary.get("risk_flags", [])
    for flag in risk_flags[:3]:
        candidate = f"Risk flag: {flag}"
        if candidate not in items:
            items.append(candidate)

    if watchlist_summary.get("critical_count", 0) > 0:
        items.append(
            f"Resolve {watchlist_summary['critical_count']} critical watchlist alert(s) "
            "before proceeding to committee."
        )
    elif watchlist_summary.get("triggered_count", 0) > 0:
        items.append(
            f"Review {watchlist_summary['triggered_count']} triggered watchlist alert(s)."
        )

    if not items:
        items.append("No immediate action required — all KRIs within acceptable range.")

    return items


# ---------------------------------------------------------------------------
# Report formatter
# ---------------------------------------------------------------------------

_STATUS_ICON = {"ok": "✓", "warn": "⚠", "critical": "✗", "unknown": "?"}


def _fmt_kri_value(kri: Dict) -> str:
    v = kri["value"]
    if v is None:
        return "n/a"
    fmt = kri["format"]
    if fmt == "pct":
        return f"{v:.1%}"
    if fmt == "pct+":
        return f"{v:+.1%}"
    if fmt == "score":
        return f"{v:.1f}/100"
    return f"{v:.0f}"


def _format_health_report(
    deal_input: Dict[str, Any],
    health_id: str,
    overall_grade: str,
    overall_score: Optional[float],
    score_summary: Dict,
    stress_summary: Dict,
    watchlist_summary: Dict,
    kris: List[Dict],
    action_items: List[str],
) -> str:
    deal_name = deal_input.get("name", deal_input.get("deal_id", "Unknown"))
    score_str = f"{overall_score:.1f}/100" if overall_score is not None else "n/a"
    lines: List[str] = []

    # Header
    lines += [
        "=" * 72,
        f"  DEAL HEALTH CHECK  [demo]",
        f"  {deal_name}",
        f"  Health ID: {health_id}",
        f"  Overall Grade: {overall_grade}  ({score_str})",
        "",
        "  ALL OUTPUTS FROM DEMO_ANALYTICAL_ENGINE — NOT FOR INVESTMENT USE",
        "=" * 72,
        "",
    ]

    # KRI dashboard
    lines += ["KEY RISK INDICATORS  [demo]", "-" * 72]
    for kri in kris:
        icon   = _STATUS_ICON.get(kri["status"], "?")
        label  = kri["label"]
        val    = _fmt_kri_value(kri)
        status = kri["status"].upper()
        lines.append(f"  {icon}  {label:<26}  {val:>10}   [{status}]")
    lines.append("")

    # Scoring summary
    lines += ["SCORING SUMMARY  [demo]", "-" * 72]
    grade = score_summary.get("grade", "?")
    glabel = score_summary.get("grade_label", "")
    lines.append(f"  Grade: {grade}  ({glabel})")
    if score_summary.get("top_drivers"):
        lines.append(f"  Top drivers: {', '.join(score_summary['top_drivers'])}")
    if score_summary.get("risk_flags"):
        for flag in score_summary["risk_flags"][:4]:
            lines.append(f"  ⚑ {flag}")
    lines.append("")

    # Stress summary
    lines += ["STRESS SUMMARY  [demo]", "-" * 72]
    base_irr = stress_summary.get("base_irr")
    min_irr  = stress_summary.get("min_stress_irr")
    drawdown = stress_summary.get("irr_drawdown")
    lines.append(f"  Base IRR:       {f'{base_irr:.1%}' if base_irr is not None else 'n/a'}")
    lines.append(f"  Worst stress:   {f'{min_irr:.1%}' if min_irr is not None else 'n/a'}")
    lines.append(f"  IRR drawdown:   {f'{drawdown:.1%}' if drawdown is not None else 'n/a'}")
    for run in stress_summary.get("stress_runs", []):
        irr = run.get("equity_irr")
        irr_s = f"{irr:.1%}" if irr is not None else "n/a"
        lines.append(f"    {run['template_name']:<28} {irr_s:>8}")
    lines.append("")

    # Watchlist summary
    lines += ["WATCHLIST  [demo]", "-" * 72]
    lines.append(
        f"  Items checked: {watchlist_summary.get('items_checked', 0)}  "
        f"  Triggered: {watchlist_summary.get('triggered_count', 0)}  "
        f"  Critical: {watchlist_summary.get('critical_count', 0)}"
    )
    for alert in watchlist_summary.get("triggered_alerts", [])[:4]:
        sev = alert.get("severity", "warning").upper()
        lines.append(f"  [{sev}]  {alert.get('label', alert.get('metric', ''))}")
    lines.append("")

    # Action items
    lines += [f"ACTION ITEMS  ({len(action_items)})  [demo]", "-" * 72]
    for i, item in enumerate(action_items, 1):
        lines.append(f"  {i}. {item}")
    lines.append("")

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
    health_id: str,
    deal_id: str,
    overall_grade: Optional[str],
    score_summary: Dict,
    stress_summary: Dict,
    watchlist_summary: Dict,
    key_risk_indicators: List[Dict],
    action_items: List[str],
    audit_events: List[str],
    overall_score: Optional[float] = None,
    health_report: str = "",
    error: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "health_id":            health_id,
        "deal_id":              deal_id,
        "checked_at":           datetime.now(timezone.utc).isoformat(),
        "overall_grade":        overall_grade,
        "overall_score":        overall_score,
        "score_summary":        score_summary,
        "stress_summary":       stress_summary,
        "watchlist_summary":    watchlist_summary,
        "key_risk_indicators":  key_risk_indicators,
        "action_items":         action_items,
        "health_report":        health_report,
        "audit_events":         audit_events,
        "is_mock":              model_engine_service.is_mock_mode(),
        "error":                error,
    }
