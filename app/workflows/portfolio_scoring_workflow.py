"""
app/workflows/portfolio_scoring_workflow.py

Score every deal in a portfolio and produce a unified scorecard.

Runs deal_scoring_workflow for each deal, then aggregates:
  - Grade distribution (how many A/B/C/D)
  - Portfolio average composite score
  - Score ranking (best → worst)
  - Deals needing attention (grade C or D, or risk flags)

IMPORTANT: All outputs tagged [demo]. Not for investment decisions.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.services import audit_logger, model_engine_service, validation_service
from app.workflows.deal_scoring_workflow import deal_scoring_workflow


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def portfolio_scoring_workflow(
    deal_inputs: List[Dict[str, Any]],
    actor: str = "system",
) -> Dict[str, Any]:
    """
    Score all deals in a portfolio.

    Parameters
    ----------
    deal_inputs : List of deal input dicts.
    actor       : Caller identity for audit trail.

    Returns
    -------
    {
        "scorecard_id":        str,
        "run_at":              str,
        "deal_count":          int,
        "scored_count":        int,         # deals that scored successfully
        "deals":               List[Dict],  # per-deal score summaries
        "score_ranking":       List[Dict],  # ranked by composite_score desc
        "grade_distribution":  Dict,        # {"A": 2, "B": 3, "C": 1, "D": 0}
        "portfolio_avg_score": float | None,
        "needs_attention":     List[Dict],  # grade C/D or has risk_flags
        "scorecard_report":    str,
        "audit_events":        List[str],
        "is_mock":             bool,
        "error":               str | None,
    }
    """
    scorecard_id = f"scorecard-{uuid.uuid4().hex[:8]}"
    audit_events: List[str] = []

    if not deal_inputs:
        return _result(scorecard_id, [], audit_events,
                       error="No deal inputs provided.")

    # ------------------------------------------------------------------
    # Score each deal
    # ------------------------------------------------------------------
    deal_scores: List[Dict[str, Any]] = []
    for deal_input in deal_inputs:
        scored = deal_scoring_workflow(deal_input=deal_input, actor=actor)
        audit_events.extend(scored.get("audit_events", []))

        deal_scores.append({
            "deal_id":         scored["deal_id"],
            "name":            deal_input.get("name", ""),
            "composite_score": scored.get("composite_score"),
            "grade":           scored.get("grade"),
            "grade_label":     scored.get("grade_label"),
            "top_drivers":     scored.get("top_drivers", []),
            "risk_flags":      scored.get("risk_flags", []),
            "status":          "ok" if not scored.get("error") else "error",
            "error":           scored.get("error"),
        })

    # ------------------------------------------------------------------
    # Aggregations
    # ------------------------------------------------------------------
    ok_deals = [d for d in deal_scores if d["status"] == "ok"
                and d["composite_score"] is not None]

    score_ranking      = _build_ranking(ok_deals)
    grade_distribution = _grade_distribution(ok_deals)
    portfolio_avg      = _avg_score(ok_deals)
    needs_attention    = _needs_attention(ok_deals)

    # ------------------------------------------------------------------
    # Report
    # ------------------------------------------------------------------
    scorecard_report = _format_report(
        deal_scores, score_ranking, grade_distribution,
        portfolio_avg, needs_attention, scorecard_id,
    )

    # ------------------------------------------------------------------
    # Audit
    # ------------------------------------------------------------------
    audit_events.append(audit_logger.record_event(
        event_type="portfolio_scoring.completed",
        deal_id="portfolio",
        actor=actor,
        payload={
            "scorecard_id":  scorecard_id,
            "deal_count":    len(deal_inputs),
            "scored_count":  len(ok_deals),
            "avg_score":     portfolio_avg,
        },
    )["event_id"])

    return _result(scorecard_id, deal_scores, audit_events,
                   score_ranking=score_ranking,
                   grade_distribution=grade_distribution,
                   portfolio_avg_score=portfolio_avg,
                   needs_attention=needs_attention,
                   scorecard_report=scorecard_report)


# ---------------------------------------------------------------------------
# Aggregation helpers
# ---------------------------------------------------------------------------

def _build_ranking(ok_deals: List[Dict]) -> List[Dict]:
    ranked = sorted(ok_deals, key=lambda d: d["composite_score"] or 0, reverse=True)
    return [
        {
            "rank":            i + 1,
            "deal_id":         d["deal_id"],
            "name":            d["name"],
            "composite_score": d["composite_score"],
            "grade":           d["grade"],
        }
        for i, d in enumerate(ranked)
    ]


def _grade_distribution(ok_deals: List[Dict]) -> Dict[str, int]:
    dist = {"A": 0, "B": 0, "C": 0, "D": 0}
    for d in ok_deals:
        grade = d.get("grade")
        if grade in dist:
            dist[grade] += 1
    return dist


def _avg_score(ok_deals: List[Dict]) -> Optional[float]:
    scores = [d["composite_score"] for d in ok_deals if d["composite_score"] is not None]
    if not scores:
        return None
    return round(sum(scores) / len(scores), 2)


def _needs_attention(ok_deals: List[Dict]) -> List[Dict]:
    """Deals with grade C/D or any risk flags."""
    flagged = []
    for d in ok_deals:
        grade = d.get("grade", "")
        flags = d.get("risk_flags", [])
        if grade in ("C", "D") or flags:
            flagged.append({
                "deal_id":   d["deal_id"],
                "name":      d["name"],
                "grade":     grade,
                "score":     d["composite_score"],
                "reasons":   (
                    ([f"Grade {grade}"] if grade in ("C", "D") else []) + flags
                ),
            })
    return flagged


# ---------------------------------------------------------------------------
# Report formatter
# ---------------------------------------------------------------------------

def _format_report(
    deal_scores: List[Dict],
    score_ranking: List[Dict],
    grade_dist: Dict[str, int],
    avg_score: Optional[float],
    needs_attention: List[Dict],
    scorecard_id: str,
) -> str:
    ok  = [d for d in deal_scores if d["status"] == "ok"]
    err = [d for d in deal_scores if d["status"] != "ok"]
    lines: List[str] = []

    # Header
    lines += [
        "=" * 72,
        "  PORTFOLIO SCORECARD  [demo]",
        f"  Scorecard ID: {scorecard_id}",
        f"  Deals: {len(ok)} scored  /  {len(err)} errors  /  {len(deal_scores)} total",
        f"  Portfolio average: {avg_score:.1f} / 100" if avg_score is not None
        else "  Portfolio average: n/a",
        "",
        "  ALL OUTPUTS FROM DEMO_ANALYTICAL_ENGINE — NOT FOR INVESTMENT USE",
        "=" * 72,
        "",
    ]

    # Score ranking table
    if score_ranking:
        lines += [
            "SCORE RANKING  [demo]",
            "-" * 72,
            f"  {'#':>2}  {'Deal':<28}  {'Score':>6}  {'Grade'}",
            "  " + "-" * 50,
        ]
        for e in score_ranking:
            bar = "█" * int((e["composite_score"] or 0) / 5)
            lines.append(
                f"  {e['rank']:>2}  {(e['name'] or e['deal_id']):<28}"
                f"  {e['composite_score']:>5.1f}   {e['grade']}  {bar}"
            )
        lines.append("")

    # Grade distribution
    total_graded = sum(grade_dist.values())
    if total_graded:
        lines += ["GRADE DISTRIBUTION  [demo]", "-" * 72]
        for grade in ("A", "B", "C", "D"):
            n   = grade_dist[grade]
            pct = n / total_graded if total_graded else 0
            bar = "█" * int(pct * 30)
            lines.append(f"  Grade {grade}  {n:>2} deals  ({pct:.0%})  {bar}")
        lines.append("")

    # Needs attention
    if needs_attention:
        lines += [
            f"NEEDS ATTENTION  ({len(needs_attention)} deal{'s' if len(needs_attention) != 1 else ''})  [demo]",
            "-" * 72,
        ]
        for d in needs_attention:
            lines.append(f"  {(d['name'] or d['deal_id']):<30}  Grade {d['grade']}  "
                         f"({d['score']:.1f}/100)")
            for reason in d["reasons"][:3]:
                lines.append(f"    ⚑ {reason}")
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
    scorecard_id: str,
    deals: List[Dict],
    audit_events: List[str],
    score_ranking: Optional[List[Dict]] = None,
    grade_distribution: Optional[Dict] = None,
    portfolio_avg_score: Optional[float] = None,
    needs_attention: Optional[List[Dict]] = None,
    scorecard_report: str = "",
    error: Optional[str] = None,
) -> Dict[str, Any]:
    ok_count = sum(1 for d in deals if d.get("status") == "ok")
    return {
        "scorecard_id":        scorecard_id,
        "run_at":              datetime.now(timezone.utc).isoformat(),
        "deal_count":          len(deals),
        "scored_count":        ok_count,
        "deals":               deals,
        "score_ranking":       score_ranking or [],
        "grade_distribution":  grade_distribution or {"A": 0, "B": 0, "C": 0, "D": 0},
        "portfolio_avg_score": portfolio_avg_score,
        "needs_attention":     needs_attention or [],
        "scorecard_report":    scorecard_report,
        "audit_events":        audit_events,
        "is_mock":             model_engine_service.is_mock_mode(),
        "error":               error,
    }
