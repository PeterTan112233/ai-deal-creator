"""
mcp/cashflow_engine/analytical_engine.py

Demo analytical CLO cashflow engine.

IMPORTANT — READ BEFORE USING
  All outputs from this engine are produced by simplified analytical formulas
  for development and testing purposes only. They are tagged _engine:
  "DEMO_ANALYTICAL_ENGINE" and must never be presented as official CLO outputs,
  used for investment decisions, pricing, ratings analysis, or distribution.

  The [calculated] source tag is reserved for outputs from a real, validated,
  production cashflow engine (Phase 2a). Outputs from this engine should be
  labelled [demo] in any user-facing presentation.

METHODOLOGY
  Implements a simplified CLO waterfall covering:
    - Pool income (WAS + SOFR base rate)
    - Sequential debt service (pay-in-kind order, by seniority)
    - OC / IC ratio computation for the most senior rated tranche
    - Expected default loss under the scenario
    - Equity IRR via bisection on discounted cashflows
    - Scenario NPV at a configurable hurdle rate

  Unspecified mezzanine tranches (gap between rated tranches and equity) are
  treated as blended-rate debt to prevent equity cashflow inflation.

PHASE 2 REPLACEMENT
  Replace this module with real cashflow-engine-mcp calls in
  app/services/model_engine_service.py. Interface is identical.
"""

from typing import Any, Dict, List

# ---------------------------------------------------------------------------
# Market constants (Phase 1 assumptions — override in Phase 2 via MCP config)
# ---------------------------------------------------------------------------

SOFR_RATE          = 0.0533   # Assumed SOFR base rate
TOTAL_FEE_RATE     = 0.0065   # Senior management + admin + trustee (65bps)
MEZ_SPREAD         = 0.0300   # Assumed mezzanine spread for unspecified tranches
HURDLE_RATE        = 0.15     # Equity NPV discount rate
REQUIRED_OC_AAA    = 1.36     # 136% standard AAA OC trigger
REQUIRED_IC_AAA    = 1.15     # 115% standard AAA IC trigger

_ENGINE_TAG = "DEMO_ANALYTICAL_ENGINE"


# ---------------------------------------------------------------------------
# Public interface (matches mock_engine.py)
# ---------------------------------------------------------------------------

def run_scenario(
    deal_payload: Dict[str, Any],
    scenario_payload: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Submit a scenario computation. Returns a run_id immediately (synchronous).
    Stores result internally for retrieval via get_run_outputs().
    """
    import uuid
    run_id = f"run-analytical-{uuid.uuid4().hex[:8]}"
    _RESULTS[run_id] = _compute(deal_payload, scenario_payload)
    return {"run_id": run_id, "status": "complete", "_engine": _ENGINE_TAG}


def get_run_status(run_id: str) -> Dict[str, Any]:
    """Return run status. Analytical engine is always synchronous."""
    if run_id in _RESULTS:
        return {"run_id": run_id, "status": "complete"}
    return {"run_id": run_id, "status": "unknown"}


def get_run_outputs(run_id: str) -> Dict[str, Any]:
    """Retrieve computed outputs for a completed run."""
    if run_id not in _RESULTS:
        raise KeyError(f"Run '{run_id}' not found. Submit via run_scenario() first.")
    return _RESULTS[run_id]


# ---------------------------------------------------------------------------
# In-memory result store (Phase 1 — replace with MCP persistence in Phase 2)
# ---------------------------------------------------------------------------

_RESULTS: Dict[str, Dict[str, Any]] = {}


# ---------------------------------------------------------------------------
# Core computation
# ---------------------------------------------------------------------------

def _compute(
    deal_payload: Dict[str, Any],
    scenario_payload: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Main analytical entry point. Returns a result dict with computed metrics.
    """
    # ---- Pool inputs -------------------------------------------------------
    portfolio_size   = float(deal_payload.get("portfolio_size", 500_000_000))
    was              = float(deal_payload.get("was", 0.042))
    wal              = float(deal_payload.get("wal", 5.2))
    diversity_score  = float(deal_payload.get("diversity_score", 75))
    ccc_bucket       = float(deal_payload.get("ccc_bucket", 0.04))
    warf             = float(deal_payload.get("warf", 2850))
    tranches: List[Dict] = deal_payload.get("tranches", [])

    # ---- Scenario inputs ---------------------------------------------------
    default_rate      = float(scenario_payload.get("default_rate",   0.030))
    recovery_rate     = float(scenario_payload.get("recovery_rate",  0.650))
    spread_shock_bps  = float(scenario_payload.get("spread_shock_bps", 0.0))
    prepayment_rate   = float(scenario_payload.get("prepayment_rate", 0.20))

    # ---- Pool quality adjustments ------------------------------------------
    # WARF: higher rating factor → higher implied default stress.
    # Benchmark WARF 2850 ≈ B+/BB-; each 100 points adds ~0.7bps annual CDR.
    warf_default_adj = (warf - 2850) * 0.000007

    # CCC bucket: loans in excess of the 7.5% OC-test threshold get a 50%
    # haircut in coverage tests, reducing distributable excess spread.
    CCC_TRIGGER = 0.075
    ccc_excess_haircut = max(0.0, ccc_bucket - CCC_TRIGGER) * 0.50 * portfolio_size * was

    # Diversity: below 60 obligors, concentration adds correlated-default risk.
    # Each point below 60 adds ~0.5bps incremental CDR.
    div_default_adj = max(0.0, (60 - diversity_score)) * 0.000005

    # Effective default rate for this run (scenario can override any of these)
    effective_default_rate = default_rate + warf_default_adj + div_default_adj

    # Spread shock tightens pool coupon (adverse scenario = spread compression)
    was_adj = was - spread_shock_bps / 10_000

    # ---- Pool economics ----------------------------------------------------
    pool_coupon        = was_adj + SOFR_RATE
    pool_income        = portfolio_size * pool_coupon
    # Interest shortfall: defaulted loans stop paying interest
    # (principal loss is captured separately in terminal equity erosion)
    interest_shortfall = portfolio_size * effective_default_rate * pool_coupon
    fees               = portfolio_size * TOTAL_FEE_RATE

    # ---- Tranche stack -----------------------------------------------------
    sorted_tranches = sorted(tranches, key=lambda t: t.get("seniority", 99))

    # Total rated size (tranches with an explicit coupon)
    rated_size_pct  = sum(
        t.get("size_pct", 0.0) for t in sorted_tranches
        if t.get("coupon") is not None
    )
    total_pct = sum(t.get("size_pct", 0.0) for t in sorted_tranches)

    # Equity is the last tranche by seniority (no coupon expected)
    equity_t    = sorted_tranches[-1] if sorted_tranches else {}
    equity_pct  = float(equity_t.get("size_pct", max(0.01, 1.0 - total_pct + equity_t.get("size_pct", 0))))
    equity_abs  = equity_pct * portfolio_size

    # Mezzanine gap: any pool exposure not covered by named tranches
    mez_pct  = max(0.0, 1.0 - total_pct)
    mez_cost = mez_pct * portfolio_size * (SOFR_RATE + MEZ_SPREAD)

    # Named tranche debt service (all tranches that have a coupon)
    named_debt_cost = sum(
        t.get("size_pct", 0.0) * portfolio_size * _parse_coupon(t.get("coupon"))
        for t in sorted_tranches
        if t.get("coupon") is not None
    )
    total_debt_cost = named_debt_cost + mez_cost

    # ---- Excess spread -----------------------------------------------------
    # Distributable income = pool income minus interest shortfall from defaults,
    # debt service, fees, and CCC OC-test haircut on excess CCC concentration.
    excess_spread = (pool_income - interest_shortfall) - total_debt_cost - fees - ccc_excess_haircut

    # ---- Senior (AAA) tranche metrics -------------------------------------
    aaa = next((t for t in sorted_tranches if t.get("seniority") == 1), None)
    aaa_pct    = float(aaa.get("size_pct", 0.61)) if aaa else 0.61
    aaa_abs    = aaa_pct * portfolio_size
    aaa_coupon = _parse_coupon(aaa.get("coupon") if aaa else "SOFR+145")

    oc_ratio_aaa   = portfolio_size / aaa_abs if aaa_abs > 0 else 0.0
    oc_cushion_aaa = oc_ratio_aaa / REQUIRED_OC_AAA - 1.0

    aaa_interest    = aaa_abs * aaa_coupon
    ic_ratio_aaa    = pool_income / aaa_interest if aaa_interest > 0 else 0.0
    ic_cushion_aaa  = ic_ratio_aaa / REQUIRED_IC_AAA - 1.0

    # ---- Equity cashflows & IRR -------------------------------------------
    equity_cf_annual = max(0.0, excess_spread)

    # Cumulative principal loss to the pool over WAL (net of recovery)
    # Equity absorbs first losses; residual principal is returned at maturity.
    total_pool_principal_loss = effective_default_rate * wal * (1 - recovery_rate) * portfolio_size
    terminal_equity = max(0.0, equity_abs - total_pool_principal_loss)

    equity_irr = _solve_irr(equity_abs, equity_cf_annual, terminal_equity, wal)

    # Equity WAL: pool WAL adjusted for prepayments and defaults
    equity_wal = round(wal * (1 - prepayment_rate * 0.3) * (1 - default_rate * 0.1), 2)
    equity_wal = max(0.5, equity_wal)

    # Scenario NPV at hurdle rate
    scenario_npv = _npv(HURDLE_RATE, equity_abs, equity_cf_annual, terminal_equity, wal)

    return {
        "equity_irr":      round(equity_irr,      4),
        "aaa_size_pct":    round(aaa_pct,          4),
        "wac":             round(pool_coupon,       4),
        "oc_cushion_aaa":  round(oc_cushion_aaa,   4),
        "ic_cushion_aaa":  round(ic_cushion_aaa,   4),
        "equity_wal":      round(equity_wal,        2),
        "scenario_npv":    round(scenario_npv,      0),
        # Engine metadata — NOT a production output tag
        "_engine":         _ENGINE_TAG,
        # Retained for system-level mock detection (Phase 1 governance)
        "_mock":           _ENGINE_TAG,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_coupon(coupon: Any) -> float:
    """
    Parse a coupon descriptor to a float annual rate.
      "SOFR+145"  → SOFR + 1.45%
      "SOFR+200"  → SOFR + 2.00%
      0.0678      → 6.78% (already a float)
      None        → 0.0 (equity)
    """
    if coupon is None:
        return 0.0
    if isinstance(coupon, (int, float)):
        return float(coupon)
    s = str(coupon).strip().upper()
    if s.startswith("SOFR+"):
        try:
            bps = float(s[5:])
            return SOFR_RATE + bps / 10_000
        except ValueError:
            pass
    try:
        return float(s)
    except ValueError:
        return SOFR_RATE + 0.015   # fallback: SOFR+150


def _solve_irr(
    investment: float,
    annual_cf: float,
    terminal: float,
    wal: float,
    lo: float = -0.90,
    hi: float = 10.0,
) -> float:
    """
    Solve for IRR using bisection on the NPV equation:
      0 = -investment + Σ(annual_cf/(1+r)^t, t=1..wal) + terminal/(1+r)^wal

    Returns a clamped float. Returns -0.99 if the deal has no positive cashflows.
    """
    if investment <= 0:
        return 0.0
    if annual_cf <= 0 and terminal <= 0:
        return -0.99

    def npv_at(r: float) -> float:
        if r <= -1:
            return float("inf")
        cf_pv   = sum(annual_cf / (1 + r) ** t for t in range(1, int(wal) + 1))
        term_pv = terminal / (1 + r) ** wal
        return -investment + cf_pv + term_pv

    # If NPV at lo and hi have the same sign, fall back to simple return estimate
    if npv_at(lo) < 0 and npv_at(hi) < 0:
        return max(-0.99, (annual_cf * wal + terminal - investment) / (investment * wal))
    if npv_at(lo) > 0 and npv_at(hi) > 0:
        return hi

    for _ in range(80):
        mid = (lo + hi) / 2
        if npv_at(mid) > 0:
            lo = mid
        else:
            hi = mid
        if hi - lo < 1e-7:
            break

    return round((lo + hi) / 2, 6)


def _npv(
    discount_rate: float,
    investment: float,
    annual_cf: float,
    terminal: float,
    wal: float,
) -> float:
    """Net present value of equity cashflows at a given discount rate."""
    cf_pv   = sum(annual_cf / (1 + discount_rate) ** t for t in range(1, int(wal) + 1))
    term_pv = terminal / (1 + discount_rate) ** wal
    return cf_pv + term_pv - investment
