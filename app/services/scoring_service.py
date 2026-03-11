"""
app/services/scoring_service.py

Composite deal scoring.

Produces a 0-100 score across four weighted dimensions and assigns a
letter grade (A–D).  All inputs are [demo] engine outputs; the score
itself is therefore also [demo] and must not be used for investment
decisions.

Dimensions and weights
----------------------
  irr_quality       35%  — base equity IRR normalised (0% → 0, 15% → 100)
  oc_adequacy       30%  — OC cushion normalised (−5% → 0, +25% → 100)
  stress_resilience 25%  — fraction of base IRR retained under worst stress
  collateral_quality 10% — diversity score, WAS, CCC bucket

Grade thresholds
----------------
  A  ≥ 75   Strong
  B  ≥ 55   Adequate
  C  ≥ 35   Marginal
  D  < 35   Weak
"""

from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Weights (must sum to 1.0)
# ---------------------------------------------------------------------------

_WEIGHTS = {
    "irr_quality":        0.35,
    "oc_adequacy":        0.30,
    "stress_resilience":  0.25,
    "collateral_quality": 0.10,
}

# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def score_deal(
    key_metrics: Dict[str, Any],
    collateral: Dict[str, Any],
    stress_drawdown: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Compute a composite deal score from analytical outputs.

    Parameters
    ----------
    key_metrics      : Dict with equity_irr, oc_cushion_aaa, ic_cushion_aaa, wac, etc.
                       (from run_scenario_workflow or deal_analytics_workflow).
    collateral       : Deal collateral dict (diversity_score, was, ccc_bucket, …).
    stress_drawdown  : IRR drawdown under worst stress scenario (base_irr - worst_irr).
                       If None, stress_resilience is estimated from OC cushion as a proxy.

    Returns
    -------
    {
        "composite_score":   float,          # 0-100
        "grade":             str,            # A / B / C / D
        "grade_label":       str,            # Strong / Adequate / Marginal / Weak
        "dimension_scores":  Dict,
        "top_drivers":       List[str],      # top 2 positive contributors
        "risk_flags":        List[str],      # concerns worth noting
    }
    """
    dims = _compute_dimensions(key_metrics, collateral, stress_drawdown)

    composite = round(
        sum(_WEIGHTS[k] * v["score"] for k, v in dims.items()),
        2,
    )

    grade, grade_label = _assign_grade(composite)
    top_drivers = _top_drivers(dims)
    risk_flags   = _risk_flags(key_metrics, collateral, stress_drawdown)

    return {
        "composite_score":  composite,
        "grade":            grade,
        "grade_label":      grade_label,
        "dimension_scores": dims,
        "top_drivers":      top_drivers,
        "risk_flags":       risk_flags,
    }


# ---------------------------------------------------------------------------
# Dimension calculators
# ---------------------------------------------------------------------------

def _compute_dimensions(
    km: Dict[str, Any],
    coll: Dict[str, Any],
    stress_drawdown: Optional[float],
) -> Dict[str, Any]:
    irr  = km.get("equity_irr") or km.get("base_equity_irr")
    oc   = km.get("oc_cushion_aaa") or km.get("base_oc_cushion")
    base_irr = km.get("equity_irr") or km.get("base_equity_irr")

    # ------------------------------------------------------------------
    # IRR quality
    # ------------------------------------------------------------------
    irr_score = _score_irr(irr)
    irr_label = (
        f"Equity IRR {irr:.1%}" if irr is not None else "IRR not available"
    )

    # ------------------------------------------------------------------
    # OC adequacy
    # ------------------------------------------------------------------
    oc_score = _score_oc(oc)
    oc_label = (
        f"OC cushion {oc:+.1%}" if oc is not None else "OC cushion not available"
    )

    # ------------------------------------------------------------------
    # Stress resilience
    # ------------------------------------------------------------------
    if stress_drawdown is not None and base_irr is not None and base_irr > 0:
        retention = max(0.0, 1.0 - stress_drawdown / base_irr)
        res_score = round(min(100.0, retention * 100), 2)
        res_label = f"IRR retention under stress: {retention:.0%}"
    else:
        # Proxy: use OC cushion as a stand-in if stress data unavailable
        res_score = min(100.0, oc_score) if oc is not None else 50.0
        res_label = "Estimated from OC cushion (no stress run)"

    # ------------------------------------------------------------------
    # Collateral quality
    # ------------------------------------------------------------------
    coll_score, coll_label = _score_collateral(coll)

    return {
        "irr_quality": {
            "score":   irr_score,
            "weight":  _WEIGHTS["irr_quality"],
            "label":   irr_label,
            "inputs":  {"equity_irr": irr},
        },
        "oc_adequacy": {
            "score":   oc_score,
            "weight":  _WEIGHTS["oc_adequacy"],
            "label":   oc_label,
            "inputs":  {"oc_cushion_aaa": oc},
        },
        "stress_resilience": {
            "score":   res_score,
            "weight":  _WEIGHTS["stress_resilience"],
            "label":   res_label,
            "inputs":  {"stress_drawdown": stress_drawdown, "base_irr": base_irr},
        },
        "collateral_quality": {
            "score":   coll_score,
            "weight":  _WEIGHTS["collateral_quality"],
            "label":   coll_label,
            "inputs":  {
                "diversity_score": coll.get("diversity_score"),
                "was":             coll.get("was"),
                "ccc_bucket":      coll.get("ccc_bucket"),
            },
        },
    }


def _score_irr(irr: Optional[float]) -> float:
    """0% IRR → 0 pts; 15%+ IRR → 100 pts (linear)."""
    if irr is None:
        return 0.0
    return round(min(100.0, max(0.0, irr / 0.15 * 100)), 2)


def _score_oc(oc: Optional[float]) -> float:
    """−5% cushion → 0 pts; +25% cushion → 100 pts (linear)."""
    if oc is None:
        return 0.0
    return round(min(100.0, max(0.0, (oc + 0.05) / 0.30 * 100)), 2)


def _score_collateral(coll: Dict[str, Any]) -> Tuple[float, str]:
    """Average of diversity (80=100), WAS (6%=100), CCC (0%=100)."""
    div = coll.get("diversity_score")
    was = coll.get("was")
    ccc = coll.get("ccc_bucket")

    components = []
    labels     = []

    if div is not None:
        s = min(100.0, div / 80 * 100)
        components.append(s)
        labels.append(f"Div {div:.0f}")

    if was is not None:
        s = min(100.0, was / 0.06 * 100)
        components.append(s)
        labels.append(f"WAS {was:.1%}")

    if ccc is not None:
        s = max(0.0, (0.075 - ccc) / 0.075 * 100)
        components.append(s)
        labels.append(f"CCC {ccc:.1%}")

    if not components:
        return 50.0, "Collateral data unavailable"

    score = round(sum(components) / len(components), 2)
    return score, "  |  ".join(labels)


# ---------------------------------------------------------------------------
# Grade assignment
# ---------------------------------------------------------------------------

_GRADE_TABLE = [
    (75, "A", "Strong"),
    (55, "B", "Adequate"),
    (35, "C", "Marginal"),
    (0,  "D", "Weak"),
]


def _assign_grade(score: float) -> Tuple[str, str]:
    for threshold, grade, label in _GRADE_TABLE:
        if score >= threshold:
            return grade, label
    return "D", "Weak"


# ---------------------------------------------------------------------------
# Driver / flag extraction
# ---------------------------------------------------------------------------

def _top_drivers(dims: Dict[str, Any]) -> List[str]:
    """Return labels of the two highest-scoring dimensions."""
    ranked = sorted(dims.items(), key=lambda x: x[1]["score"], reverse=True)
    return [v["label"] for _, v in ranked[:2]]


def _risk_flags(
    km: Dict[str, Any],
    coll: Dict[str, Any],
    stress_drawdown: Optional[float],
) -> List[str]:
    flags: List[str] = []

    irr = km.get("equity_irr") or km.get("base_equity_irr")
    if irr is not None and irr < 0.06:
        flags.append(f"Low equity IRR [demo]: {irr:.1%} (threshold: 6%)")

    oc = km.get("oc_cushion_aaa") or km.get("base_oc_cushion")
    if oc is not None and oc < 0.05:
        flags.append(f"Thin OC cushion [demo]: {oc:+.1%} (threshold: +5%)")

    ccc = coll.get("ccc_bucket")
    if ccc is not None and ccc > 0.06:
        flags.append(f"CCC bucket elevated [demo]: {ccc:.1%} (threshold: 6%)")

    div = coll.get("diversity_score")
    if div is not None and div < 40:
        flags.append(f"Low diversity score [demo]: {div:.0f} (threshold: 40)")

    if stress_drawdown is not None:
        base_irr = km.get("equity_irr") or km.get("base_equity_irr")
        if base_irr and base_irr > 0:
            retention = 1.0 - stress_drawdown / base_irr
            if retention < 0.5:
                flags.append(
                    f"IRR retention under stress [demo]: {retention:.0%} (threshold: 50%)"
                )

    return flags
