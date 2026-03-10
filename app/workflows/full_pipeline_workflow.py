"""
app/workflows/full_pipeline_workflow.py

Full end-to-end deal analytics pipeline.

One call that chains:
  1. deal_analytics_workflow   — 4-scenario suite + optional sensitivity sweeps
  2. tranche_optimizer_workflow — find optimal AAA size
  3. benchmark_comparison_workflow — score vs. historical cohort
  4. generate_investor_summary_workflow — produce a draft investor summary

Returns a single consolidated result dict with outputs from each stage
plus a pipeline-level summary and audit trail.

IMPORTANT: All outputs are tagged [demo]. Not for investment use.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.services import audit_logger, model_engine_service
from app.workflows.benchmark_comparison_workflow import benchmark_comparison_workflow
from app.workflows.deal_analytics_workflow import deal_analytics_workflow
from app.workflows.generate_investor_summary_workflow import generate_investor_summary_workflow
from app.workflows.run_scenario_workflow import run_scenario_workflow
from app.workflows.tranche_optimizer_workflow import tranche_optimizer_workflow


def full_pipeline_workflow(
    deal_input: Dict[str, Any],
    run_sensitivity: bool = False,
    run_optimizer: bool = True,
    run_benchmark: bool = True,
    run_draft: bool = True,
    vintage: Optional[int] = None,
    region: Optional[str] = None,
    optimizer_kwargs: Optional[Dict[str, Any]] = None,
    actor: str = "system",
) -> Dict[str, Any]:
    """
    Run the full deal analytics pipeline end-to-end.

    Args:
        deal_input:       Deal input dict matching deal_input.schema.json.
        run_sensitivity:  Whether to include CDR/RR sensitivity sweeps
                          in the analytics stage (slower). Default False.
        run_optimizer:    Whether to run the tranche structure optimizer.
        run_benchmark:    Whether to run benchmark comparison.
        run_draft:        Whether to generate an investor summary draft.
        vintage:          Override vintage for benchmark comparison.
        region:           Override region for benchmark comparison.
        optimizer_kwargs: Extra kwargs forwarded to tranche_optimizer_workflow
                          (aaa_min, aaa_max, aaa_step, oc_floor, ic_floor, ...).
        actor:            Caller identity for audit trail.

    Returns:
        {
            "pipeline_id":   str,
            "deal_id":       str,
            "run_at":        str,
            "is_mock":       bool,
            "stages":        {
                "analytics":   dict | None,
                "optimizer":   dict | None,
                "benchmark":   dict | None,
                "draft":       dict | None,
            },
            "pipeline_summary": str,    # plain-text executive summary
            "audit_events":  List[str],
            "error":         str | None,
        }
    """
    pipeline_id  = f"pipeline-{uuid.uuid4().hex[:8]}"
    audit_events: List[str] = []
    deal_id = deal_input.get("deal_id", "unknown")
    errors: List[str] = []

    stages: Dict[str, Any] = {
        "analytics": None,
        "optimizer": None,
        "benchmark": None,
        "draft":     None,
    }

    audit_events.append(audit_logger.record_event(
        event_type="pipeline.started",
        deal_id=deal_id,
        actor=actor,
        payload={
            "pipeline_id":    pipeline_id,
            "run_sensitivity": run_sensitivity,
            "run_optimizer":  run_optimizer,
            "run_benchmark":  run_benchmark,
            "run_draft":      run_draft,
        },
    )["event_id"])

    # ------------------------------------------------------------------
    # Stage 1: Analytics (scenario suite + optional sensitivity)
    # ------------------------------------------------------------------
    analytics = deal_analytics_workflow(
        deal_input,
        run_sensitivity=run_sensitivity,
        actor=actor,
    )
    stages["analytics"] = analytics
    audit_events.extend(analytics.get("audit_events", []))

    if analytics.get("error"):
        # If analytics fails (e.g. invalid deal), abort the pipeline
        errors.append(f"analytics: {analytics['error']}")
        return _result(pipeline_id, deal_id, stages, audit_events, errors, deal_input)

    # ------------------------------------------------------------------
    # Stage 2: Tranche optimizer (optional)
    # ------------------------------------------------------------------
    if run_optimizer:
        opt_kwargs = optimizer_kwargs or {}
        # Use coarser step for pipeline speed (can be overridden)
        opt_kwargs.setdefault("aaa_step", 0.01)
        optimizer = tranche_optimizer_workflow(deal_input, actor=actor, **opt_kwargs)
        stages["optimizer"] = optimizer
        audit_events.extend(optimizer.get("audit_events", []))

    # ------------------------------------------------------------------
    # Stage 3: Benchmark comparison (optional)
    # ------------------------------------------------------------------
    if run_benchmark:
        # Use base-case outputs for benchmark scoring
        base_outputs = _get_base_outputs(analytics)
        if base_outputs:
            bench = benchmark_comparison_workflow(
                deal_input=deal_input,
                scenario_outputs=base_outputs,
                vintage=vintage,
                region=region,
                actor=actor,
            )
            stages["benchmark"] = bench
            audit_events.extend(bench.get("audit_events", []))
        else:
            stages["benchmark"] = {"error": "No base-case outputs available for benchmark."}

    # ------------------------------------------------------------------
    # Stage 4: Draft investor summary (optional)
    # ------------------------------------------------------------------
    if run_draft:
        # Run a single base-case scenario to produce a proper scenario_result
        base_scenario_result = _run_base_scenario(deal_input, actor)
        if base_scenario_result and not base_scenario_result.get("error"):
            draft_result = generate_investor_summary_workflow(
                deal_input=deal_input,
                scenario_result=base_scenario_result.get("scenario_result", {}),
                scenario_request=base_scenario_result.get("scenario_request"),
                actor=actor,
            )
            stages["draft"] = draft_result
            audit_events.extend([e["event_id"] if isinstance(e, dict) else e
                                  for e in draft_result.get("audit_events", [])])

    # ------------------------------------------------------------------
    # Pipeline summary
    # ------------------------------------------------------------------
    pipeline_summary = _format_pipeline_summary(deal_input, stages, pipeline_id)

    audit_events.append(audit_logger.record_event(
        event_type="pipeline.completed",
        deal_id=deal_id,
        actor=actor,
        payload={
            "pipeline_id":   pipeline_id,
            "stages_run":    [k for k, v in stages.items() if v is not None],
            "errors":        errors,
        },
    )["event_id"])

    return _result(pipeline_id, deal_id, stages, audit_events, errors, deal_input,
                   pipeline_summary=pipeline_summary)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_base_outputs(analytics: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract outputs from the Base scenario in the analytics suite."""
    results = analytics.get("scenario_suite", {}).get("results", [])
    base = next((r for r in results if r["scenario_name"] == "Base"), None)
    if base is None and results:
        base = results[0]
    return base.get("outputs") if base else None


def _run_base_scenario(deal_input: Dict[str, Any], actor: str) -> Optional[Dict[str, Any]]:
    """Run a single base-case scenario for draft generation."""
    try:
        return run_scenario_workflow(
            deal_input=deal_input,
            scenario_name="Baseline",
            scenario_type="base",
            actor=actor,
        )
    except Exception:  # noqa: BLE001
        return None


def _format_pipeline_summary(
    deal_input: Dict,
    stages: Dict[str, Any],
    pipeline_id: str,
) -> str:
    deal_name = deal_input.get("name", deal_input.get("deal_id", "Unknown Deal"))
    deal_id   = deal_input.get("deal_id", "unknown")
    ps        = deal_input.get("collateral", {}).get("portfolio_size", 0)

    lines: List[str] = [
        "=" * 72,
        "  FULL PIPELINE SUMMARY  [demo]",
        f"  {deal_name}  (ID: {deal_id})",
        f"  Pipeline ID: {pipeline_id}",
        f"  Pool size: ${ps:,.0f}",
        "",
        "  ALL OUTPUTS FROM DEMO_ANALYTICAL_ENGINE / DEMO_BENCHMARK_DATA",
        "=" * 72,
        "",
    ]

    # Analytics stage
    analytics = stages.get("analytics")
    if analytics and not analytics.get("error"):
        km = analytics.get("key_metrics", {})
        be = analytics.get("breakeven", {})
        irr = km.get("base_equity_irr")
        oc  = km.get("base_oc_cushion")
        cdr_be = be.get("cdr_irr_zero")

        lines += [
            "ANALYTICS  [demo]",
            "-" * 72,
        ]
        if irr is not None:
            lines.append(f"  Base equity IRR : {irr:.2%}")
        if oc is not None:
            lines.append(f"  AAA OC cushion  : {oc:+.1%}")
        if cdr_be is not None:
            lines.append(f"  CDR breakeven   : {cdr_be:.2%}")
        elif analytics.get("cdr_sensitivity"):
            lines.append(f"  CDR breakeven   : not found in tested range")

        # Scenario IRR table
        results = analytics.get("scenario_suite", {}).get("results", [])
        if results:
            lines.append("")
            lines.append(f"  {'Scenario':<18} {'IRR':>8}  {'NPV ($M)':>10}")
            for r in results:
                irr_s = f"{r['outputs']['equity_irr']:.1%}" if r.get("outputs", {}).get("equity_irr") is not None else "n/a"
                npv   = r.get("outputs", {}).get("scenario_npv")
                npv_s = f"{npv/1e6:+.1f}" if npv is not None else "n/a"
                lines.append(f"  {r['scenario_name']:<18} {irr_s:>8}  {npv_s:>10}")
        lines.append("")

    # Optimizer stage
    optimizer = stages.get("optimizer")
    if optimizer and not optimizer.get("error"):
        opt = optimizer.get("optimal")
        n   = len(optimizer.get("feasibility_table", []))
        nf  = len(optimizer.get("frontier", []))
        lines += ["OPTIMIZER  [demo]", "-" * 72]
        if opt:
            lines += [
                f"  Optimal AAA size  : {opt['aaa_size_pct']:.1%}",
                f"  Optimal equity    : {opt['equity_size_pct']:.1%}",
                f"  Optimal IRR [demo]: {opt['equity_irr']:.2%}",
                f"  OC cushion [demo] : {opt['oc_cushion_aaa']:+.1%}",
                f"  ({nf} feasible of {n} candidates tested)",
            ]
        else:
            reason = optimizer.get("infeasible_reason", "No feasible structure found.")
            lines.append(f"  No feasible structure: {reason}")
        lines.append("")

    # Benchmark stage
    benchmark = stages.get("benchmark")
    if benchmark and not benchmark.get("error"):
        pos   = benchmark.get("overall_position", "").upper()
        label = benchmark.get("overall_label", "")
        above = benchmark.get("above_median_count", 0)
        below = benchmark.get("below_median_count", 0)
        lines += [
            "BENCHMARK  [demo]",
            "-" * 72,
            f"  Vintage: {benchmark.get('vintage')}  Region: {benchmark.get('region')}",
            f"  Overall: {pos}",
            f"  {label}",
            f"  Above median: {above}  |  Below median: {below}",
            "",
        ]

    # Draft stage
    draft_stage = stages.get("draft")
    if draft_stage and not draft_stage.get("error"):
        draft = draft_stage.get("draft", {})
        lines += [
            "DRAFT  [generated]",
            "-" * 72,
            f"  Draft ID       : {draft.get('draft_id', 'n/a')}",
            f"  Approved       : {draft.get('approved', False)}",
            f"  Requires approval: {draft.get('approved', False) is False}",
            "",
        ]

    lines += [
        "=" * 72,
        "  [demo] All outputs require Phase 2 production engine for official use.",
        "=" * 72,
    ]

    return "\n".join(lines)


def _result(
    pipeline_id: str,
    deal_id: str,
    stages: Dict,
    audit_events: List[str],
    errors: List[str],
    deal_input: Dict,
    pipeline_summary: str = "",
) -> Dict[str, Any]:
    return {
        "pipeline_id":      pipeline_id,
        "deal_id":          deal_id,
        "run_at":           datetime.now(timezone.utc).isoformat(),
        "is_mock":          model_engine_service.is_mock_mode(),
        "stages":           stages,
        "pipeline_summary": pipeline_summary,
        "audit_events":     audit_events,
        "error":            "; ".join(errors) if errors else None,
    }
