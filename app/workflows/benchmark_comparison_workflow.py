"""
app/workflows/benchmark_comparison_workflow.py

Compare a deal's analytical outputs against historical CLO market benchmarks.

Given a deal input and a scenario result (from run_scenario_workflow or
deal_analytics_workflow), this workflow:
  1. Retrieves the benchmark cohort matching the deal's vintage and region.
  2. Scores each output metric against p25/p50/p75 percentile bands.
  3. Produces an overall positioning summary (above/at/below median).
  4. Generates a formatted [demo]-tagged comparison report.

IMPORTANT: All benchmark data is tagged [demo] / _source: DEMO_BENCHMARK_DATA
and must not be used as official market data or investment guidance.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.services import audit_logger, benchmarks_service


# ---------------------------------------------------------------------------
# Metrics to compare (must be present in both deal outputs and benchmark data)
# ---------------------------------------------------------------------------

_COMPARE_METRICS = [
    ("equity_irr",     "Equity IRR",      True,  ".1%"),   # (key, label, higher_is_better, fmt)
    ("aaa_size_pct",   "AAA Size",        False, ".1%"),   # higher leverage = higher risk
    ("oc_cushion_aaa", "AAA OC Cushion",  True,  ".1%"),
    ("ic_cushion_aaa", "AAA IC Cushion",  True,  ".1%"),
    ("was",            "WAS",             True,  ".2%"),
    ("wac",            "WAC",             True,  ".2%"),
    ("equity_wal",     "Equity WAL",      None,  ".1f"),   # neutral — depends on strategy
]

_OVERALL_LABELS = {
    "strong":  "ABOVE MEDIAN on most metrics — deal appears above-market for this vintage",
    "median":  "AT MEDIAN — deal tracks the vintage cohort closely",
    "weak":    "BELOW MEDIAN on most metrics — deal may face structural headwinds vs. peers",
    "mixed":   "MIXED POSITIONING — some metrics above median, others below",
}


def benchmark_comparison_workflow(
    deal_input: Dict[str, Any],
    scenario_outputs: Dict[str, Any],
    vintage: Optional[int] = None,
    region: Optional[str] = None,
    asset_class: str = "broadly_syndicated_loans",
    actor: str = "system",
) -> Dict[str, Any]:
    """
    Compare deal scenario outputs against historical CLO benchmark percentiles.

    Args:
        deal_input:        Deal input dict (used for vintage/region fallback).
        scenario_outputs:  The `outputs` dict from a scenario result
                           (e.g. result["scenario_result"]["outputs"]).
        vintage:           Vintage year for benchmark cohort. Falls back to
                           deal_input.close_date year or current year - 1.
        region:            "US" | "EU". Falls back to deal_input.region or "US".
        asset_class:       Asset class filter (default: broadly_syndicated_loans).
        actor:             Caller identity for audit trail.

    Returns:
        {
            "deal_id":            str,
            "comparison_id":      str,
            "compared_at":        str,
            "vintage":            int,
            "region":             str,
            "benchmark_cohort":   Dict,        # full benchmark record
            "metric_scores":      List[Dict],  # per-metric percentile positions
            "above_median_count": int,
            "below_median_count": int,
            "overall_position":   str,         # "strong" | "median" | "weak" | "mixed"
            "overall_label":      str,
            "comparison_report":  str,         # formatted [demo] text report
            "is_mock":            bool,
            "audit_events":       List[str],
            "error":              str | None,
        }
    """
    comparison_id = f"bench-{uuid.uuid4().hex[:8]}"
    audit_events:  List[str] = []
    deal_id = deal_input.get("deal_id", "unknown")

    # ------------------------------------------------------------------
    # Resolve vintage and region
    # ------------------------------------------------------------------
    vintage = vintage or _infer_vintage(deal_input)
    region  = (region or deal_input.get("region") or "US").upper()

    # ------------------------------------------------------------------
    # Fetch benchmark cohort
    # ------------------------------------------------------------------
    cohort = benchmarks_service.get_benchmark(vintage, region, asset_class)

    if cohort is None:
        available = benchmarks_service.list_vintages(region)
        error_msg = (
            f"No benchmark data for vintage={vintage}, region={region}, "
            f"asset_class={asset_class}. "
            f"Available vintages for {region}: {available}."
        )
        audit_events.append(audit_logger.record_event(
            event_type="benchmark_comparison.failed",
            deal_id=deal_id,
            actor=actor,
            payload={"comparison_id": comparison_id, "reason": error_msg},
        )["event_id"])
        return _error_result(comparison_id, deal_id, vintage, region, audit_events, error_msg)

    # ------------------------------------------------------------------
    # Score each metric
    # ------------------------------------------------------------------
    metric_scores: List[Dict[str, Any]] = []
    above_median = 0
    below_median = 0

    benchmark_metrics = cohort.get("metrics", {})

    for key, label, higher_is_better, fmt in _COMPARE_METRICS:
        deal_val = scenario_outputs.get(key)
        bands    = benchmark_metrics.get(key)

        if deal_val is None or bands is None:
            metric_scores.append({
                "metric":  key,
                "label":   label,
                "deal_value":  None,
                "p25": None, "p50": None, "p75": None,
                "percentile_rank":   "n/a",
                "vs_median":         "n/a",
                "assessment":        "no data",
            })
            continue

        rank = benchmarks_service.percentile_rank(deal_val, bands)
        p50  = bands["p50"]

        if higher_is_better is True:
            vs = "above" if deal_val > p50 else ("at" if abs(deal_val - p50) / max(abs(p50), 1e-9) < 0.02 else "below")
        elif higher_is_better is False:
            vs = "below" if deal_val > p50 else ("at" if abs(deal_val - p50) / max(abs(p50), 1e-9) < 0.02 else "above")
        else:
            vs = "at" if abs(deal_val - p50) / max(abs(p50), 1e-9) < 0.05 else (
                "above" if deal_val > p50 else "below"
            )

        if vs == "above":
            above_median += 1
        elif vs == "below":
            below_median += 1

        metric_scores.append({
            "metric":         key,
            "label":          label,
            "deal_value":     deal_val,
            "p25":            bands["p25"],
            "p50":            bands["p50"],
            "p75":            bands["p75"],
            "percentile_rank": rank,
            "vs_median":      vs,
            "higher_is_better": higher_is_better,
            "fmt":            fmt,
        })

    # ------------------------------------------------------------------
    # Overall position
    # ------------------------------------------------------------------
    scored = [s for s in metric_scores if s["vs_median"] != "n/a"]
    total  = len(scored)

    if total == 0:
        overall = "mixed"
    elif above_median >= total * 0.6:
        overall = "strong"
    elif below_median >= total * 0.6:
        overall = "weak"
    elif above_median == below_median:
        overall = "median"
    else:
        overall = "mixed"

    # ------------------------------------------------------------------
    # Formatted report
    # ------------------------------------------------------------------
    report = _format_report(
        deal_input, cohort, metric_scores,
        above_median, below_median, overall,
        vintage, region, comparison_id,
    )

    # ------------------------------------------------------------------
    # Audit
    # ------------------------------------------------------------------
    audit_events.append(audit_logger.record_event(
        event_type="benchmark_comparison.completed",
        deal_id=deal_id,
        actor=actor,
        payload={
            "comparison_id":      comparison_id,
            "vintage":            vintage,
            "region":             region,
            "overall_position":   overall,
            "above_median_count": above_median,
            "below_median_count": below_median,
            "metrics_scored":     total,
        },
    )["event_id"])

    return {
        "deal_id":            deal_id,
        "comparison_id":      comparison_id,
        "compared_at":        datetime.now(timezone.utc).isoformat(),
        "vintage":            vintage,
        "region":             region,
        "benchmark_cohort":   cohort,
        "metric_scores":      metric_scores,
        "above_median_count": above_median,
        "below_median_count": below_median,
        "overall_position":   overall,
        "overall_label":      _OVERALL_LABELS[overall],
        "comparison_report":  report,
        "is_mock":            benchmarks_service.is_mock_mode(),
        "audit_events":       audit_events,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _infer_vintage(deal_input: Dict[str, Any]) -> int:
    """Infer vintage year from close_date or default to current year - 1."""
    close_date = deal_input.get("close_date", "")
    if close_date and len(close_date) >= 4:
        try:
            return int(close_date[:4])
        except ValueError:
            pass
    return datetime.now(timezone.utc).year - 1


def _format_report(
    deal_input: Dict,
    cohort: Dict,
    scores: List[Dict],
    above: int,
    below: int,
    overall: str,
    vintage: int,
    region: str,
    comparison_id: str,
) -> str:
    deal_name = deal_input.get("name", deal_input.get("deal_id", "Unknown Deal"))
    deal_id   = deal_input.get("deal_id", "unknown")
    n_deals   = cohort.get("deal_count", "?")

    lines: List[str] = [
        "=" * 72,
        "  BENCHMARK COMPARISON REPORT  [demo]",
        f"  {deal_name}  (ID: {deal_id})",
        f"  Comparison ID: {comparison_id}",
        f"  Cohort: {region} BSL CLO  |  Vintage: {vintage}  |  N={n_deals} deals",
        "",
        "  BENCHMARK DATA: DEMO_BENCHMARK_DATA — NOT OFFICIAL MARKET DATA",
        "  Do not use for investment decisions, pricing, or distribution.",
        "=" * 72,
        "",
        f"  OVERALL POSITIONING:  {overall.upper()}",
        f"  {_OVERALL_LABELS[overall]}",
        "",
        f"  Above median: {above} metrics  |  Below median: {below} metrics",
        "",
    ]

    # Metric comparison table
    lines += [
        "METRIC-BY-METRIC COMPARISON  [demo]",
        "-" * 72,
        f"{'Metric':<18} {'Deal':>9} {'p25':>9} {'p50':>9} {'p75':>9}  {'Rank':<12} {'vs Median'}",
        "-" * 72,
    ]

    for s in scores:
        if s["deal_value"] is None:
            lines.append(f"{s['label']:<18}  {'n/a':>9}")
            continue

        fmt = s.get("fmt", ".2%")
        dv  = s["deal_value"]
        p25 = s["p25"]
        p50 = s["p50"]
        p75 = s["p75"]

        if "%" in fmt:
            dv_s  = f"{dv:{fmt}}"
            p25_s = f"{p25:{fmt}}"
            p50_s = f"{p50:{fmt}}"
            p75_s = f"{p75:{fmt}}"
        else:
            dv_s  = f"{dv:{fmt}}y"
            p25_s = f"{p25:{fmt}}y"
            p50_s = f"{p50:{fmt}}y"
            p75_s = f"{p75:{fmt}}y"

        rank = s.get("percentile_rank", "n/a")
        vs   = s.get("vs_median", "n/a")
        hib  = s.get("higher_is_better")
        indicator = ""
        if vs == "above" and hib is True:
            indicator = "▲ strong"
        elif vs == "above" and hib is False:
            indicator = "▲ caution"
        elif vs == "below" and hib is True:
            indicator = "▼ weak"
        elif vs == "below" and hib is False:
            indicator = "▼ conservative"
        elif vs == "at":
            indicator = "= at median"

        lines.append(
            f"{s['label']:<18} {dv_s:>9} {p25_s:>9} {p50_s:>9} {p75_s:>9}  {rank:<12} {indicator}"
        )

    lines += [
        "",
        "=" * 72,
        "  [demo] Benchmark data from DEMO_BENCHMARK_DATA (illustrative).",
        "  Replace with real historical-deals-mcp data in Phase 2.",
        "=" * 72,
    ]

    return "\n".join(lines)


def _error_result(
    comparison_id: str,
    deal_id: str,
    vintage: int,
    region: str,
    audit_events: List[str],
    error: str,
) -> Dict[str, Any]:
    return {
        "deal_id":            deal_id,
        "comparison_id":      comparison_id,
        "compared_at":        datetime.now(timezone.utc).isoformat(),
        "vintage":            vintage,
        "region":             region,
        "benchmark_cohort":   None,
        "metric_scores":      [],
        "above_median_count": 0,
        "below_median_count": 0,
        "overall_position":   "mixed",
        "overall_label":      "",
        "comparison_report":  "",
        "is_mock":            benchmarks_service.is_mock_mode(),
        "audit_events":       audit_events,
        "error":              error,
    }
