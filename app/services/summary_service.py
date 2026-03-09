"""
app/services/summary_service.py

Generates a plain-English, grounded scenario summary from deal inputs
and engine outputs.

Every statement in the summary is tagged with its source type:
    [retrieved]   — from the deal input (user-provided data)
    [mock]        — from the mock engine (synthetic, NOT official)
    [calculated]  — will apply when real engine integration is active (Phase 2+)
    [generated]   — Claude/service interpretation based on grounded inputs

Principles:
    - Never present mock outputs as official CLO results
    - Never make investment claims or performance predictions
    - Flag interpretation clearly; separate from facts
    - Keep language plain and structurer-appropriate

Phase 2+: the [mock] tag is replaced by [calculated] when real engine outputs are used.
Phase 3+: approved language sections will be fetched from approved-language-mcp.
"""

from typing import Any, Dict


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def generate_summary(
    deal_input: Dict[str, Any],
    scenario_request: Dict[str, Any],
    scenario_result: Dict[str, Any],
) -> str:
    """
    Generate a grounded scenario summary.

    Returns a plain-text string with clearly labelled sections.
    """
    is_mock = "_mock" in scenario_result

    lines = []

    lines += _mock_banner(is_mock)
    lines += _section_deal_context(deal_input)
    lines += _section_scenario_parameters(scenario_request)
    lines += _section_engine_outputs(scenario_result, is_mock)
    lines += _section_interpretation(scenario_result, is_mock)
    lines += _section_footer(scenario_result)

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------

def _mock_banner(is_mock: bool) -> list:
    if not is_mock:
        return []
    return [
        "=" * 70,
        "WARNING: MOCK ENGINE OUTPUT — NOT OFFICIAL CLO RESULTS",
        "All metrics below are synthetic placeholders for development only.",
        "Replace model_engine_service with real cashflow-engine-mcp in Phase 2.",
        "=" * 70,
        "",
    ]


def _section_deal_context(deal_input: Dict[str, Any]) -> list:
    collateral = deal_input.get("collateral", {})
    liabilities = deal_input.get("liabilities", [])
    senior = next((t for t in liabilities if t.get("seniority") == 1), None)

    lines = [
        "DEAL CONTEXT  [retrieved]",
        "-" * 40,
        f"  Deal:        {deal_input.get('name', 'N/A')}",
        f"  Issuer:      {deal_input.get('issuer', 'N/A')}",
        f"  Region:      {deal_input.get('region', 'N/A')}",
        f"  Currency:    {deal_input.get('currency', 'N/A')}",
        f"  Manager:     {deal_input.get('manager', 'N/A')}",
        "",
        f"  Portfolio:   {_fmt_currency(collateral.get('portfolio_size'), deal_input.get('currency', 'USD'))}",
        f"  Asset class: {collateral.get('asset_class', 'N/A')}",
        f"  WAS:         {_fmt_pct(collateral.get('was'))}",
        f"  WARF:        {collateral.get('warf', 'N/A')}",
        f"  WAL:         {_fmt_years(collateral.get('wal'))}",
        f"  Diversity:   {collateral.get('diversity_score', 'N/A')}",
        f"  CCC bucket:  {_fmt_pct(collateral.get('ccc_bucket'))}",
    ]

    if senior:
        lines += [
            "",
            f"  Senior tranche ({senior.get('name', 'N/A')}): "
            f"{_fmt_pct(senior.get('size_pct'))} of deal, "
            f"coupon {senior.get('coupon', 'N/A')}",
        ]

    lines += ["", f"  Tranches:    {len(liabilities)} classes"]
    lines.append("")
    return lines


def _section_scenario_parameters(scenario_request: Dict[str, Any]) -> list:
    params = scenario_request.get("parameters", {})
    assumptions = scenario_request.get("assumptions_made", [])
    ambiguities = scenario_request.get("flagged_ambiguities", [])

    lines = [
        "SCENARIO PARAMETERS  [retrieved]",
        "-" * 40,
        f"  Scenario:       {scenario_request.get('name', 'N/A')}",
        f"  Type:           {scenario_request.get('scenario_type', 'N/A')}",
        f"  Default rate:   {_fmt_pct(params.get('default_rate'))}",
        f"  Recovery rate:  {_fmt_pct(params.get('recovery_rate'))}",
        f"  Spread shock:   {params.get('spread_shock_bps', 0)} bps",
    ]

    if assumptions:
        lines += ["", "  Assumptions applied:"]
        for a in assumptions:
            lines.append(f"    • {a}")

    if ambiguities:
        lines += ["", "  Ambiguities flagged:"]
        for a in ambiguities:
            lines.append(f"    ⚠ {a}")

    lines.append("")
    return lines


def _section_engine_outputs(scenario_result: Dict[str, Any], is_mock: bool) -> list:
    outputs = scenario_result.get("outputs", {})
    source_tag = "[mock — NOT official]" if is_mock else "[calculated]"
    run_id = scenario_result.get("run_id", "N/A")

    lines = [
        f"ENGINE OUTPUTS  {source_tag}",
        f"Run ID: {run_id}",
        "-" * 40,
    ]

    metric_labels = {
        "equity_irr":     ("Equity IRR",          _fmt_pct),
        "aaa_size_pct":   ("AAA size",             _fmt_pct),
        "wac":            ("WAC (liabilities)",    _fmt_pct),
        "oc_cushion_aaa": ("OC cushion (AAA)",     _fmt_pct),
        "ic_cushion_aaa": ("IC cushion (AAA)",     _fmt_pct),
        "equity_wal":     ("Equity WAL",           _fmt_years),
        "scenario_npv":   ("Scenario NPV",         _fmt_npv),
    }

    for key, (label, formatter) in metric_labels.items():
        value = outputs.get(key)
        if value is not None:
            lines.append(f"  {label:<22} {formatter(value)}")

    warnings = scenario_result.get("engine_warnings", [])
    if warnings:
        lines += [""]
        for w in warnings:
            lines.append(f"  ⚠ {w}")

    lines.append("")
    return lines


def _section_interpretation(scenario_result: Dict[str, Any], is_mock: bool) -> list:
    """
    Plain-English interpretation of the scenario result.
    All statements are [generated] and clearly hedged when outputs are mock.
    No investment conclusions are drawn.
    """
    outputs = scenario_result.get("outputs", {})
    hedge = " (based on mock outputs — for illustrative purposes only)" if is_mock else ""

    lines = [
        f"INTERPRETATION  [generated{hedge}]",
        "-" * 40,
    ]

    equity_irr = outputs.get("equity_irr")
    if equity_irr is not None:
        lines.append(
            f"  Equity return: The scenario produces an equity IRR of "
            f"{_fmt_pct(equity_irr)}{hedge}."
        )

    oc_cushion = outputs.get("oc_cushion_aaa")
    if oc_cushion is not None:
        cushion_desc = "healthy" if oc_cushion >= 0.04 else "tight"
        lines.append(
            f"  OC cushion: The AAA OC cushion of {_fmt_pct(oc_cushion)} "
            f"appears {cushion_desc} relative to a typical 4% threshold{hedge}."
        )

    aaa_pct = outputs.get("aaa_size_pct")
    if aaa_pct is not None:
        lines.append(
            f"  Senior sizing: AAA tranche at {_fmt_pct(aaa_pct)} of deal size{hedge}."
        )

    lines += [
        "",
        "  Note: Interpretation is [generated] from output values only.",
        "  No investment recommendation is made or implied.",
        "  For official analysis, run against the real cashflow engine (Phase 2).",
        "",
    ]
    return lines


def _section_footer(scenario_result: Dict[str, Any]) -> list:
    return [
        "SOURCE CITATIONS",
        "-" * 40,
        f"  Run ID:    {scenario_result.get('run_id', 'N/A')}",
        f"  Scenario:  {scenario_result.get('scenario_id', 'N/A')}",
        f"  Deal:      {scenario_result.get('deal_id', 'N/A')}",
        f"  Source:    {scenario_result.get('source', 'N/A')}",
        f"  Executed:  {scenario_result.get('executed_at', 'N/A')}",
        "",
    ]


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------

def _fmt_pct(value) -> str:
    if value is None:
        return "N/A"
    return f"{value:.2%}"


def _fmt_years(value) -> str:
    if value is None:
        return "N/A"
    return f"{value:.1f} yrs"


def _fmt_currency(value, currency: str = "USD") -> str:
    if value is None:
        return "N/A"
    if value >= 1_000_000_000:
        return f"{currency} {value / 1_000_000_000:.2f}bn"
    if value >= 1_000_000:
        return f"{currency} {value / 1_000_000:.0f}m"
    return f"{currency} {value:,.0f}"


def _fmt_npv(value) -> str:
    if value is None:
        return "N/A"
    return f"{value:,.0f}"
