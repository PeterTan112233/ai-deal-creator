"""
app/workflows/portfolio_analytics_workflow.py

Cross-deal portfolio analytics.

Accepts a list of deal inputs, runs a base-case scenario for each, then
aggregates, ranks, and summarises the portfolio's risk/return profile.

Use cases:
  - CLO manager reviewing their pipeline across 5-10 deals
  - Relative value comparison: which deal has the best risk-adjusted IRR?
  - Concentration analysis: how much Europe vs US? BSL vs MM?

IMPORTANT: All outputs tagged [demo]. Not for investment decisions.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.services import audit_logger, model_engine_service, validation_service
from app.workflows.run_scenario_workflow import run_scenario_workflow


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_BASE_PARAMS = {
    "default_rate": 0.030,
    "recovery_rate": 0.650,
    "spread_shock_bps": 0.0,
}

_RANK_METRICS = ["equity_irr", "oc_cushion_aaa", "ic_cushion_aaa", "scenario_npv", "wac"]

_HIGHER_IS_BETTER = {"equity_irr", "oc_cushion_aaa", "ic_cushion_aaa", "scenario_npv"}


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def portfolio_analytics_workflow(
    deal_inputs: List[Dict[str, Any]],
    metrics: Optional[List[str]] = None,
    actor: str = "system",
) -> Dict[str, Any]:
    """
    Run base-case analysis across a list of deals and return a portfolio summary.

    Parameters
    ----------
    deal_inputs  : List of deal input dicts (each validated internally).
    metrics      : Subset of output metrics to include in rankings.
                   Default: equity_irr, oc_cushion_aaa, ic_cushion_aaa, scenario_npv, wac.
    actor        : Caller identity for audit trail.

    Returns
    -------
    {
        "portfolio_id":     str,
        "analysed_at":      str,        # ISO timestamp
        "deal_count":       int,
        "deals":            List[deal summary dicts],
        "aggregate":        Dict,       # portfolio-level aggregates
        "rankings":         Dict,       # per-metric ranked lists
        "concentration":    Dict,       # breakdowns by region / asset class / size
        "portfolio_report": str,        # formatted [demo]-tagged text
        "audit_events":     List[str],
        "is_mock":          bool,
        "error":            str | None,
    }
    """
    portfolio_id = f"portfolio-{uuid.uuid4().hex[:8]}"
    audit_events: List[str] = []
    rank_metrics = metrics or _RANK_METRICS

    if not deal_inputs:
        return _result(
            portfolio_id, [], {}, {}, {}, "",
            audit_events, error="No deal inputs provided.",
        )

    # ------------------------------------------------------------------
    # Run base-case scenario for each deal
    # ------------------------------------------------------------------
    deal_summaries: List[Dict[str, Any]] = []
    for deal_input in deal_inputs:
        deal_id = deal_input.get("deal_id", "unknown")

        validation = validation_service.validate_deal_input(deal_input)
        if not validation.get("valid"):
            deal_summaries.append({
                "deal_id":        deal_id,
                "name":           deal_input.get("name", ""),
                "region":         deal_input.get("region"),
                "asset_class":    deal_input.get("collateral", {}).get("asset_class"),
                "portfolio_size": deal_input.get("collateral", {}).get("portfolio_size"),
                "key_metrics":    {},
                "status":         "error",
                "error":          f"Validation failed: {validation.get('errors', [])}",
            })
            continue

        scen = run_scenario_workflow(
            deal_input=deal_input,
            scenario_name="Portfolio Base",
            scenario_type="base",
            parameter_overrides=_BASE_PARAMS,
            actor=actor,
        )
        audit_events.extend(scen.get("audit_events", []))
        scen_result = scen.get("scenario_result") or {}
        outputs = scen_result.get("outputs", {})

        deal_summaries.append({
            "deal_id":        deal_id,
            "name":           deal_input.get("name", ""),
            "region":         deal_input.get("region"),
            "asset_class":    deal_input.get("collateral", {}).get("asset_class"),
            "portfolio_size": deal_input.get("collateral", {}).get("portfolio_size"),
            "key_metrics":    outputs,
            "status":         "ok" if not scen.get("error") else "error",
            "error":          scen.get("error"),
        })

    # ------------------------------------------------------------------
    # Aggregate, rank, concentrate
    # ------------------------------------------------------------------
    ok_deals = [d for d in deal_summaries if d["status"] == "ok"]
    aggregate    = _build_aggregate(ok_deals)
    rankings     = _build_rankings(ok_deals, rank_metrics)
    concentration = _build_concentration(deal_summaries)

    # ------------------------------------------------------------------
    # Formatted report
    # ------------------------------------------------------------------
    portfolio_report = _format_report(
        deal_summaries, aggregate, rankings, concentration, portfolio_id,
    )

    # ------------------------------------------------------------------
    # Audit
    # ------------------------------------------------------------------
    audit_events.append(audit_logger.record_event(
        event_type="portfolio_analytics.completed",
        deal_id="portfolio",
        actor=actor,
        payload={
            "portfolio_id": portfolio_id,
            "deal_count":   len(deal_inputs),
            "ok_count":     len(ok_deals),
            "error_count":  len(deal_summaries) - len(ok_deals),
        },
    )["event_id"])

    return _result(
        portfolio_id, deal_summaries, aggregate, rankings, concentration,
        portfolio_report, audit_events,
    )


# ---------------------------------------------------------------------------
# Aggregation helpers
# ---------------------------------------------------------------------------

def _build_aggregate(ok_deals: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute portfolio-level aggregates across all valid deals."""
    if not ok_deals:
        return {}

    total_size = sum(d.get("portfolio_size") or 0 for d in ok_deals)
    agg: Dict[str, Any] = {
        "deal_count":          len(ok_deals),
        "total_portfolio_size": total_size,
    }

    for metric in _RANK_METRICS:
        values = [
            d["key_metrics"][metric]
            for d in ok_deals
            if d["key_metrics"].get(metric) is not None
        ]
        if values:
            agg[f"avg_{metric}"] = sum(values) / len(values)
            agg[f"min_{metric}"] = min(values)
            agg[f"max_{metric}"] = max(values)

    return agg


def _build_rankings(
    ok_deals: List[Dict[str, Any]],
    metrics: List[str],
) -> Dict[str, Any]:
    """Rank deals by each metric."""
    rankings: Dict[str, Any] = {}
    for metric in metrics:
        entries = [
            {"deal_id": d["deal_id"], "name": d["name"], "value": d["key_metrics"][metric]}
            for d in ok_deals
            if d["key_metrics"].get(metric) is not None
        ]
        if not entries:
            continue
        entries.sort(key=lambda e: e["value"], reverse=(metric in _HIGHER_IS_BETTER))
        for i, e in enumerate(entries):
            e["rank"] = i + 1
        rankings[metric] = entries
    return rankings


def _build_concentration(deal_summaries: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Group deals by region, asset class, and size bucket."""
    by_region: Dict[str, int]       = {}
    by_asset_class: Dict[str, int]  = {}
    by_size_bucket: Dict[str, int]  = {}

    for d in deal_summaries:
        region = d.get("region") or "Unknown"
        by_region[region] = by_region.get(region, 0) + 1

        ac = d.get("asset_class") or "Unknown"
        by_asset_class[ac] = by_asset_class.get(ac, 0) + 1

        size = d.get("portfolio_size") or 0
        bucket = _size_bucket(size)
        by_size_bucket[bucket] = by_size_bucket.get(bucket, 0) + 1

    return {
        "by_region":      by_region,
        "by_asset_class": by_asset_class,
        "by_size_bucket": by_size_bucket,
    }


def _size_bucket(size: float) -> str:
    if size < 200_000_000:
        return "<$200M"
    elif size < 400_000_000:
        return "$200M–$400M"
    elif size < 600_000_000:
        return "$400M–$600M"
    else:
        return ">$600M"


# ---------------------------------------------------------------------------
# Report formatter
# ---------------------------------------------------------------------------

def _format_report(
    deal_summaries: List[Dict[str, Any]],
    aggregate: Dict[str, Any],
    rankings: Dict[str, Any],
    concentration: Dict[str, Any],
    portfolio_id: str,
) -> str:
    ok  = [d for d in deal_summaries if d["status"] == "ok"]
    err = [d for d in deal_summaries if d["status"] != "ok"]
    lines: List[str] = []

    # Header
    lines += [
        "=" * 72,
        "  PORTFOLIO ANALYTICS REPORT  [demo]",
        f"  Portfolio ID: {portfolio_id}",
        f"  Deals analysed: {len(ok)} ok  /  {len(err)} errors  /  {len(deal_summaries)} total",
        "",
        "  ALL OUTPUTS FROM DEMO_ANALYTICAL_ENGINE — NOT OFFICIAL CLO OUTPUTS",
        "  Do not use for investment decisions, pricing, or ratings analysis.",
        "=" * 72,
        "",
    ]

    # Per-deal table
    if ok:
        lines += [
            "DEAL SUMMARY  [demo]",
            "-" * 72,
            f"  {'Deal':<22} {'Region':<8} {'Size ($M)':>10} {'IRR':>8} {'OC Cush':>9} {'WAC':>7}",
            "  " + "-" * 68,
        ]
        for d in deal_summaries:
            km   = d.get("key_metrics", {})
            size = d.get("portfolio_size") or 0
            irr  = km.get("equity_irr")
            oc   = km.get("oc_cushion_aaa")
            wac  = km.get("wac")
            name = (d["deal_id"] if not d["name"] else d["name"])[:22]
            region = (d.get("region") or "")[:8]
            size_s = f"{size/1e6:,.0f}" if size else "n/a"
            irr_s  = f"{irr:.1%}"  if irr  is not None else "n/a"
            oc_s   = f"{oc:+.1%}" if oc   is not None else "n/a"
            wac_s  = f"{wac:.1%}" if wac  is not None else "n/a"
            tag    = " [error]" if d["status"] == "error" else ""
            lines.append(
                f"  {name:<22} {region:<8} {size_s:>10} {irr_s:>8} {oc_s:>9} {wac_s:>7}{tag}"
            )
        lines.append("")

    # Aggregate stats
    if aggregate:
        total = aggregate.get("total_portfolio_size", 0)
        avg_irr = aggregate.get("avg_equity_irr")
        avg_oc  = aggregate.get("avg_oc_cushion_aaa")
        lines += [
            "PORTFOLIO AGGREGATES  [demo]",
            "-" * 72,
            f"  Deal count            : {aggregate.get('deal_count', 0)}",
            f"  Total portfolio size  : ${total/1e9:.2f}B" if total else "  Total portfolio size: n/a",
        ]
        if avg_irr is not None:
            mn = aggregate.get("min_equity_irr", 0)
            mx = aggregate.get("max_equity_irr", 0)
            lines.append(f"  Avg equity IRR [demo] : {avg_irr:.2%}  (range {mn:.1%}–{mx:.1%})")
        if avg_oc is not None:
            mn = aggregate.get("min_oc_cushion_aaa", 0)
            mx = aggregate.get("max_oc_cushion_aaa", 0)
            lines.append(f"  Avg OC cushion [demo] : {avg_oc:+.2%} (range {mn:+.1%}–{mx:+.1%})")
        lines.append("")

    # IRR rankings
    irr_rank = rankings.get("equity_irr", [])
    if irr_rank:
        lines += ["EQUITY IRR RANKING  [demo]", "-" * 72]
        for e in irr_rank:
            bar = "█" * max(0, int(e["value"] * 200))
            lines.append(f"  #{e['rank']:>2}  {e['name'] or e['deal_id']:<30}  {e['value']:.2%}  {bar}")
        lines.append("")

    # Concentration
    for label, breakdown in [
        ("REGION CONCENTRATION", concentration.get("by_region", {})),
        ("ASSET CLASS CONCENTRATION", concentration.get("by_asset_class", {})),
        ("SIZE BUCKET CONCENTRATION", concentration.get("by_size_bucket", {})),
    ]:
        if breakdown:
            lines += [label, "-" * 72]
            total_n = sum(breakdown.values())
            for k, v in sorted(breakdown.items(), key=lambda x: -x[1]):
                pct = v / total_n if total_n else 0
                bar = "█" * int(pct * 30)
                lines.append(f"  {k:<30}  {v:>2} deal{'s' if v != 1 else ''}  ({pct:.0%})  {bar}")
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
    portfolio_id: str,
    deals: List[Dict],
    aggregate: Dict,
    rankings: Dict,
    concentration: Dict,
    portfolio_report: str,
    audit_events: List[str],
    error: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "portfolio_id":     portfolio_id,
        "analysed_at":      datetime.now(timezone.utc).isoformat(),
        "deal_count":       len(deals),
        "deals":            deals,
        "aggregate":        aggregate,
        "rankings":         rankings,
        "concentration":    concentration,
        "portfolio_report": portfolio_report,
        "audit_events":     audit_events,
        "is_mock":          model_engine_service.is_mock_mode(),
        "error":            error,
    }
