"""
app/workflows/deal_analytics_workflow.py

One-call deal analytics package.

Runs a standard 4-scenario suite plus two parameter sensitivity sweeps
(default_rate and recovery_rate) and assembles a complete analytics report
covering scenario comparison, breakeven thresholds, structural metrics,
and a formatted text summary.

Intended as the primary analytical entry point for a deal — replaces the
need to make separate calls to batch_scenario_workflow and
sensitivity_analysis_workflow for a routine analysis.

IMPORTANT: All numeric outputs are tagged [demo] — produced by the
DEMO_ANALYTICAL_ENGINE. They are not [calculated] outputs and must not
be used for investment decisions or official CLO analysis.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.services import audit_logger, model_engine_service, validation_service
from app.workflows.batch_scenario_workflow import batch_scenario_workflow
from app.workflows.sensitivity_analysis_workflow import sensitivity_analysis_workflow


# ---------------------------------------------------------------------------
# Standard scenario suite
# ---------------------------------------------------------------------------

_STANDARD_SCENARIOS = [
    {
        "name": "Base",
        "type": "base",
        "parameters": {"default_rate": 0.030, "recovery_rate": 0.650, "spread_shock_bps":   0},
    },
    {
        "name": "Mild Stress",
        "type": "stress",
        "parameters": {"default_rate": 0.050, "recovery_rate": 0.550, "spread_shock_bps":  50},
    },
    {
        "name": "Stress",
        "type": "stress",
        "parameters": {"default_rate": 0.075, "recovery_rate": 0.450, "spread_shock_bps": 100},
    },
    {
        "name": "Deep Stress",
        "type": "stress",
        "parameters": {"default_rate": 0.120, "recovery_rate": 0.350, "spread_shock_bps": 150},
    },
]

_CDR_SWEEP   = [round(i * 0.01, 2) for i in range(1, 16)]   # 1%..15% CDR
_RR_SWEEP    = [round(i * 0.05, 2) for i in range(2, 17)]    # 10%..80% RR


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def deal_analytics_workflow(
    deal_input: Dict[str, Any],
    custom_scenarios: Optional[List[Dict[str, Any]]] = None,
    run_sensitivity: bool = True,
    actor: str = "system",
) -> Dict[str, Any]:
    """
    Run a complete analytics package for a deal.

    Args:
        deal_input:        Deal input dict matching deal_input.schema.json.
        custom_scenarios:  Override the standard 4-scenario suite. If None,
                           runs Base / Mild Stress / Stress / Deep Stress.
        run_sensitivity:   Whether to run CDR and RR sensitivity sweeps.
                           Set False to speed up testing.
        actor:             Caller identity for audit trail.

    Returns:
        {
            "deal_id":          str,
            "analysis_id":      str,           # unique ID for this run
            "analysed_at":      str,           # ISO timestamp
            "is_mock":          bool,
            "scenario_suite":   Dict,          # batch_scenario_workflow output
            "cdr_sensitivity":  Dict | None,   # sensitivity over default_rate
            "rr_sensitivity":   Dict | None,   # sensitivity over recovery_rate
            "summary_table":    List[Dict],    # metric rows with all scenario values
            "key_metrics":      Dict,          # base-case headline metrics
            "breakeven":        Dict,          # CDR and RR breakeven thresholds
            "analytics_report": str,           # formatted [demo]-tagged text report
            "audit_events":     List[str],
            "error":            str,           # only on validation failure
        }
    """
    import uuid
    analysis_id = f"analytics-{uuid.uuid4().hex[:8]}"
    audit_events: List[str] = []
    deal_id = deal_input.get("deal_id", "unknown")

    # ------------------------------------------------------------------
    # Step 1: Validate
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
            "analysis_id": analysis_id,
            "analysed_at": datetime.now(timezone.utc).isoformat(),
            "is_mock": model_engine_service.is_mock_mode(),
            "scenario_suite": {},
            "cdr_sensitivity": None,
            "rr_sensitivity": None,
            "summary_table": [],
            "key_metrics": {},
            "breakeven": {},
            "analytics_report": "",
            "audit_events": audit_events,
            "error": "Deal validation failed. Fix issues before running analytics.",
        }

    # ------------------------------------------------------------------
    # Step 2: Scenario suite
    # ------------------------------------------------------------------
    scenarios = custom_scenarios or _STANDARD_SCENARIOS
    scenario_suite = batch_scenario_workflow(deal_input, scenarios, actor=actor)
    audit_events.extend(scenario_suite.get("audit_events", []))

    # ------------------------------------------------------------------
    # Step 3: Sensitivity sweeps (optional)
    # ------------------------------------------------------------------
    cdr_sensitivity = rr_sensitivity = None

    if run_sensitivity:
        base_params = {"recovery_rate": 0.65, "spread_shock_bps": 0}
        cdr_sensitivity = sensitivity_analysis_workflow(
            deal_input, "default_rate", _CDR_SWEEP,
            base_parameters=base_params, actor=actor,
        )
        audit_events.extend(cdr_sensitivity.get("audit_events", []))

        base_params_rr = {"default_rate": 0.05, "spread_shock_bps": 0}
        rr_sensitivity = sensitivity_analysis_workflow(
            deal_input, "recovery_rate", _RR_SWEEP,
            base_parameters=base_params_rr, actor=actor,
        )
        audit_events.extend(rr_sensitivity.get("audit_events", []))

    # ------------------------------------------------------------------
    # Step 4: Derive summary artefacts
    # ------------------------------------------------------------------
    summary_table = scenario_suite.get("comparison_table", [])
    key_metrics   = _extract_key_metrics(scenario_suite)
    breakeven     = _extract_breakeven(cdr_sensitivity, rr_sensitivity)

    # ------------------------------------------------------------------
    # Step 5: Formatted analytics report
    # ------------------------------------------------------------------
    analytics_report = _format_report(
        deal_input, scenario_suite, cdr_sensitivity, rr_sensitivity,
        key_metrics, breakeven, analysis_id,
    )

    # ------------------------------------------------------------------
    # Step 6: Audit
    # ------------------------------------------------------------------
    audit_events.append(audit_logger.record_event(
        event_type="deal_analytics.completed",
        deal_id=deal_id,
        actor=actor,
        payload={
            "analysis_id":     analysis_id,
            "scenarios_run":   scenario_suite.get("scenarios_run", 0),
            "cdr_points":      len(cdr_sensitivity["series"]) if cdr_sensitivity else 0,
            "rr_points":       len(rr_sensitivity["series"])  if rr_sensitivity  else 0,
            "cdr_breakeven":   breakeven.get("cdr_irr_zero"),
            "rr_breakeven":    breakeven.get("rr_irr_zero"),
        },
    )["event_id"])

    return {
        "deal_id":          deal_id,
        "analysis_id":      analysis_id,
        "analysed_at":      datetime.now(timezone.utc).isoformat(),
        "is_mock":          model_engine_service.is_mock_mode(),
        "scenario_suite":   scenario_suite,
        "cdr_sensitivity":  cdr_sensitivity,
        "rr_sensitivity":   rr_sensitivity,
        "summary_table":    summary_table,
        "key_metrics":      key_metrics,
        "breakeven":        breakeven,
        "analytics_report": analytics_report,
        "audit_events":     audit_events,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_key_metrics(scenario_suite: Dict[str, Any]) -> Dict[str, Any]:
    """Pull base-case headline metrics from the scenario suite."""
    results = scenario_suite.get("results", [])
    base = next((r for r in results if r["scenario_name"] == "Base"), None)
    if base is None and results:
        base = results[0]
    if base is None:
        return {}

    outputs = base.get("outputs", {})
    return {
        "base_equity_irr":   outputs.get("equity_irr"),
        "base_wac":          outputs.get("wac"),
        "base_oc_cushion":   outputs.get("oc_cushion_aaa"),
        "base_ic_cushion":   outputs.get("ic_cushion_aaa"),
        "base_equity_wal":   outputs.get("equity_wal"),
        "base_scenario_npv": outputs.get("scenario_npv"),
        "aaa_size_pct":      outputs.get("aaa_size_pct"),
    }


def _extract_breakeven(
    cdr_sens: Optional[Dict],
    rr_sens:  Optional[Dict],
) -> Dict[str, Any]:
    """Consolidate breakeven thresholds from sensitivity sweeps."""
    result: Dict[str, Any] = {}

    if cdr_sens:
        be = cdr_sens.get("breakeven", {})
        result["cdr_irr_zero"] = be.get("equity_irr_zero")
        result["cdr_npv_zero"] = be.get("scenario_npv_zero")

    if rr_sens:
        be = rr_sens.get("breakeven", {})
        result["rr_irr_zero"] = be.get("equity_irr_zero")
        result["rr_npv_zero"] = be.get("scenario_npv_zero")

    return result


def _format_report(
    deal_input: Dict,
    scenario_suite: Dict,
    cdr_sensitivity: Optional[Dict],
    rr_sensitivity: Optional[Dict],
    key_metrics: Dict,
    breakeven: Dict,
    analysis_id: str,
) -> str:
    """
    Produce a plain-text analytics report. All outputs labelled [demo].
    """
    deal_name = deal_input.get("name", deal_input.get("deal_id", "Unknown Deal"))
    deal_id   = deal_input.get("deal_id", "unknown")
    ps        = deal_input.get("collateral", {}).get("portfolio_size", 0)

    lines: List[str] = []

    # Header
    lines += [
        "=" * 72,
        f"  DEAL ANALYTICS REPORT  [demo]",
        f"  {deal_name}  (ID: {deal_id})",
        f"  Analysis ID: {analysis_id}",
        f"  Pool size: ${ps:,.0f}",
        "",
        "  ALL OUTPUTS FROM DEMO_ANALYTICAL_ENGINE — NOT OFFICIAL CLO OUTPUTS",
        "  Do not use for investment decisions, pricing, or ratings analysis.",
        "=" * 72,
        "",
    ]

    # Scenario summary table
    lines += ["SCENARIO SUITE  [demo]", "-" * 72]
    results = scenario_suite.get("results", [])
    if results:
        header_cols = ["Scenario", "CDR", "RR", "IRR", "WAC", "OC Cushion", "NPV ($M)"]
        lines.append(f"{'Scenario':<18} {'CDR':>6} {'RR':>6} {'IRR':>8} {'WAC':>7} {'OC Cush':>10} {'NPV $M':>10}")
        lines.append("-" * 72)
        for r in results:
            p   = r.get("parameters", {})
            o   = r.get("outputs", {})
            cdr = p.get("default_rate", 0)
            rr  = p.get("recovery_rate", 0)
            irr = o.get("equity_irr")
            wac = o.get("wac")
            oc  = o.get("oc_cushion_aaa")
            npv = o.get("scenario_npv")
            irr_s = f"{irr:.1%}" if irr is not None else "n/a"
            wac_s = f"{wac:.1%}" if wac is not None else "n/a"
            oc_s  = f"{oc:.1%}"  if oc  is not None else "n/a"
            npv_s = f"{npv/1e6:+.1f}" if npv is not None else "n/a"
            lines.append(
                f"{r['scenario_name']:<18} {cdr:>5.1%} {rr:>5.1%} {irr_s:>8} {wac_s:>7} {oc_s:>10} {npv_s:>10}"
            )
    lines.append("")

    # Key metrics (base case)
    lines += ["KEY METRICS — BASE CASE  [demo]", "-" * 72]
    km = key_metrics
    if km:
        irr = km.get("base_equity_irr")
        wac = km.get("base_wac")
        oc  = km.get("base_oc_cushion")
        ic  = km.get("base_ic_cushion")
        wal = km.get("base_equity_wal")
        npv = km.get("base_scenario_npv")
        aaa = km.get("aaa_size_pct")
        lines += [
            f"  Equity IRR   [demo] : {irr:.2%}"  if irr is not None else "  Equity IRR: n/a",
            f"  Pool WAC     [demo] : {wac:.2%}"   if wac is not None else "  Pool WAC: n/a",
            f"  AAA size     [demo] : {aaa:.1%}"   if aaa is not None else "  AAA size: n/a",
            f"  OC cushion   [demo] : {oc:+.1%}"   if oc  is not None else "  OC cushion: n/a",
            f"  IC cushion   [demo] : {ic:+.1%}"   if ic  is not None else "  IC cushion: n/a",
            f"  Equity WAL   [demo] : {wal:.1f}y"  if wal is not None else "  Equity WAL: n/a",
            f"  Scenario NPV [demo] : ${npv/1e6:+.1f}M" if npv is not None else "  Scenario NPV: n/a",
        ]
    lines.append("")

    # Breakeven thresholds
    lines += ["BREAKEVEN THRESHOLDS  [demo]", "-" * 72]
    cdr_be = breakeven.get("cdr_irr_zero")
    rr_be  = breakeven.get("rr_irr_zero")
    if cdr_be is not None:
        lines.append(f"  Equity IRR = 0 at CDR [demo] : {cdr_be:.2%}  (base: 3.00%)")
    else:
        lines.append("  Equity IRR = 0 at CDR [demo] : not found in tested range (1%–15%)")
    if rr_be is not None:
        lines.append(f"  Equity IRR = 0 at RR  [demo] : {rr_be:.0%}  (base: 65%)")
    else:
        lines.append("  Equity IRR = 0 at RR  [demo] : not found in tested range (10%–80%)")
    lines.append("")

    # CDR sensitivity table (condensed)
    if cdr_sensitivity:
        lines += ["CDR SENSITIVITY — EQUITY IRR  [demo]", "-" * 72]
        series = [s for s in cdr_sensitivity.get("series", []) if s["status"] == "complete"]
        # Show every other data point to keep report compact
        for s in series[::2]:
            val = s.get("parameter_value", 0)
            irr = s["outputs"].get("equity_irr")
            bar = _irr_bar(irr)
            irr_s = f"{irr:+.1%}" if irr is not None else "  n/a"
            lines.append(f"  CDR={val:5.1%}  IRR={irr_s:>7}  {bar}")
        lines.append("")

    # Footer
    lines += [
        "=" * 72,
        "  [demo] All outputs from DEMO_ANALYTICAL_ENGINE.",
        "  Replace with real cashflow-engine-mcp outputs in Phase 2.",
        "=" * 72,
    ]

    return "\n".join(lines)


def _irr_bar(irr: Optional[float], width: int = 20) -> str:
    """ASCII bar chart for IRR value."""
    if irr is None:
        return ""
    pct = max(-1.0, min(1.0, irr))
    filled = int(abs(pct) * width)
    char = "█" if pct >= 0 else "░"
    prefix = "+" if pct >= 0 else "-"
    return f"{prefix}{'█' * filled}"
