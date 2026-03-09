"""
app/services/comparison_service.py

Compares two deal input dicts or two scenario result dicts.

WHAT THIS SERVICE DOES
  - Identifies field-by-field numeric and categorical changes (deterministic facts)
  - Applies conservative heuristic rules to infer likely input→output drivers
  - Clearly separates [retrieved] / [calculated] facts from [generated] inference

WHAT THIS SERVICE DOES NOT DO
  - Attribute causality with precision — no cashflow model access
  - Perform tranche-level (liability) diffs — deferred to Phase 2+
  - Model interaction effects between simultaneous parameter changes

Phase 2+: replace driver inference with model-attributed cashflow decomposition
          via cashflow-engine-mcp.attribute_drivers()
"""

from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Field metadata — known fields with display labels, units, and scale
# Only fields in these maps are compared; others are silently ignored.
# ---------------------------------------------------------------------------

_COLLATERAL_FIELDS: Dict[str, tuple] = {
    "portfolio_size":   ("Portfolio size",    "currency", 1),
    "was":              ("WAS",               "pct",      1),
    "warf":             ("WARF",              "raw",      1),
    "wal":              ("WAL",               "yrs",      1),
    "diversity_score":  ("Diversity score",   "raw",      1),
    "ccc_bucket":       ("CCC bucket",        "pct",      1),
}

_MARKET_ASSUMPTION_FIELDS: Dict[str, tuple] = {
    "default_rate":     ("Default rate",      "pct",      1),
    "recovery_rate":    ("Recovery rate",     "pct",      1),
    "spread_shock_bps": ("Spread shock",      "bps",      1),
}

_OUTPUT_FIELDS: Dict[str, tuple] = {
    "equity_irr":       ("Equity IRR",        "pct",      1),
    "aaa_size_pct":     ("AAA size",          "pct",      1),
    "wac":              ("WAC",               "pct",      1),
    "oc_cushion_aaa":   ("OC cushion (AAA)",  "pct",      1),
    "ic_cushion_aaa":   ("IC cushion (AAA)",  "pct",      1),
    "equity_wal":       ("Equity WAL",        "yrs",      1),
    "scenario_npv":     ("Scenario NPV",      "currency", 1),
}

# ---------------------------------------------------------------------------
# Driver inference rules
#
# Format: (input_field, input_direction, output_field, output_direction, statement)
# A rule fires only when both the input AND the output moved in the stated direction.
# No rule fires on an input change alone — both sides must confirm.
#
# Language is deliberately hedged: "may", "likely", never "will" or "causes".
# ---------------------------------------------------------------------------

_DRIVER_RULES: List[tuple] = [
    (
        "recovery_rate", "down", "equity_irr", "down",
        "Lower recovery rate may reduce equity IRR as loss severity on defaulted assets increases.",
    ),
    (
        "recovery_rate", "down", "oc_cushion_aaa", "down",
        "Lower recovery rate may erode OC cushion as realised losses reduce collateral par.",
    ),
    (
        "recovery_rate", "up", "equity_irr", "up",
        "Higher recovery rate may improve equity IRR as loss severity on defaulted assets decreases.",
    ),
    (
        "recovery_rate", "up", "oc_cushion_aaa", "up",
        "Higher recovery rate may strengthen OC cushion as realised losses on defaults decrease.",
    ),
    (
        "default_rate", "up", "equity_irr", "down",
        "Higher default rate may reduce equity IRR as more collateral assets default and generate losses.",
    ),
    (
        "default_rate", "up", "oc_cushion_aaa", "down",
        "Higher default rate may compress OC cushion as defaulted assets are removed from par.",
    ),
    (
        "default_rate", "down", "equity_irr", "up",
        "Lower default rate may improve equity IRR as fewer defaults reduce collateral erosion.",
    ),
    (
        "default_rate", "down", "oc_cushion_aaa", "up",
        "Lower default rate may strengthen OC cushion as fewer assets default out of par.",
    ),
    (
        "spread_shock_bps", "up", "wac", "up",
        "Spread widening increases the weighted average cost of liabilities, compressing returns.",
    ),
    (
        "spread_shock_bps", "up", "equity_irr", "down",
        "Higher spread shock increases funding costs, which may reduce equity IRR.",
    ),
    (
        "spread_shock_bps", "down", "wac", "down",
        "Spread tightening reduces the weighted average cost of liabilities.",
    ),
    (
        "warf", "up", "equity_irr", "down",
        "Higher WARF (lower average pool quality) may increase expected defaults and reduce equity returns.",
    ),
    (
        "ccc_bucket", "up", "oc_cushion_aaa", "down",
        "A larger CCC bucket may trigger haircuts in OC tests, reducing effective OC cushion.",
    ),
]

_CAVEAT_GENERAL = (
    "Driver inference is heuristic only. No cashflow model is available to attribute "
    "output changes to specific inputs with precision. [generated]"
)

_CAVEAT_MULTI_CHANGE = (
    "Multiple inputs changed simultaneously. Interaction effects between changes are not "
    "modelled — actual output changes may differ from the sum of individual drivers. [generated]"
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _diff_numeric(v1: Any, v2: Any) -> Optional[Dict[str, Any]]:
    """Return delta dict for two numeric values, or None if unchanged."""
    if v1 is None and v2 is None:
        return None
    if v1 == v2:
        return None
    if v1 is None or v2 is None:
        return {"delta": None, "delta_pct": None, "direction": "changed"}
    try:
        delta = v2 - v1
        delta_pct = round(delta / v1 * 100, 2) if v1 != 0 else None
        return {
            "delta": round(delta, 6),
            "delta_pct": delta_pct,
            "direction": "up" if delta > 0 else "down",
        }
    except (TypeError, ValueError):
        return {"delta": None, "delta_pct": None, "direction": "changed"}


def _diff_section(
    v1_section: Dict, v2_section: Dict, field_meta: Dict
) -> List[Dict]:
    """
    Diff two flat dicts for fields listed in field_meta.
    Returns a list of FieldDiff records for changed fields only.
    Fields absent from field_meta are silently ignored.
    """
    diffs = []
    relevant_keys = set(field_meta.keys()) & (
        set(v1_section.keys()) | set(v2_section.keys())
    )
    for field in sorted(relevant_keys):
        v1_val = v1_section.get(field)
        v2_val = v2_section.get(field)
        if v1_val == v2_val:
            continue
        label, unit, _ = field_meta[field]
        entry: Dict[str, Any] = {
            "field": field,
            "label": label,
            "unit": unit,
            "v1": v1_val,
            "v2": v2_val,
        }
        numeric = _diff_numeric(v1_val, v2_val)
        if numeric:
            entry.update(numeric)
        diffs.append(entry)
    return diffs


def _infer_drivers(
    input_changes: List[Dict], output_changes: List[Dict]
) -> List[Dict]:
    """
    Apply heuristic driver rules.
    A rule fires only when both the input and the output moved in the rule's
    predicted direction. Returns an empty list if either list is empty.
    All results are tagged [generated] and carry hedged language.
    """
    if not input_changes or not output_changes:
        return []
    input_dir = {c["field"]: c.get("direction") for c in input_changes}
    output_dir = {c["field"]: c.get("direction") for c in output_changes}
    drivers = []
    for (in_field, in_dir, out_field, out_dir, statement) in _DRIVER_RULES:
        if input_dir.get(in_field) == in_dir and output_dir.get(out_field) == out_dir:
            drivers.append({
                "input_field": in_field,
                "output_field": out_field,
                "statement": statement,
                "confidence": "heuristic",
                "tag": "[generated — heuristic rule, not model-attributed]",
            })
    return drivers


def _format_change_line(change: Dict) -> str:
    """Format a single field change as an aligned display line."""
    label = change.get("label", change.get("field", ""))
    v1 = change.get("v1")
    v2 = change.get("v2")
    unit = change.get("unit", "raw")
    delta = change.get("delta")
    direction = change.get("direction", "changed")
    arrow = "↑" if direction == "up" else ("↓" if direction == "down" else "→")

    if unit == "pct":
        v1_s = f"{v1 * 100:.2f}%" if isinstance(v1, (int, float)) else str(v1)
        v2_s = f"{v2 * 100:.2f}%" if isinstance(v2, (int, float)) else str(v2)
        d_s = f"  (Δ {delta * 100:+.2f}pp)" if isinstance(delta, (int, float)) else ""
    elif unit == "bps":
        v1_s = f"{v1:.0f} bps" if isinstance(v1, (int, float)) else str(v1)
        v2_s = f"{v2:.0f} bps" if isinstance(v2, (int, float)) else str(v2)
        d_s = f"  (Δ {delta:+.0f} bps)" if isinstance(delta, (int, float)) else ""
    elif unit == "currency":
        v1_s = f"{v1:,.0f}" if isinstance(v1, (int, float)) else str(v1)
        v2_s = f"{v2:,.0f}" if isinstance(v2, (int, float)) else str(v2)
        d_s = f"  (Δ {delta:+,.0f})" if isinstance(delta, (int, float)) else ""
    elif unit == "yrs":
        v1_s = f"{v1:.1f} yrs" if isinstance(v1, (int, float)) else str(v1)
        v2_s = f"{v2:.1f} yrs" if isinstance(v2, (int, float)) else str(v2)
        d_s = f"  (Δ {delta:+.1f} yrs)" if isinstance(delta, (int, float)) else ""
    else:
        v1_s = str(v1)
        v2_s = str(v2)
        d_s = f"  (Δ {delta:+g})" if isinstance(delta, (int, float)) else ""

    return f"  {label:<28} {v1_s:>12}  {arrow}  {v2_s:<12}{d_s}"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compare_deal_inputs(v1: Dict, v2: Dict) -> Dict:
    """
    Compare two deal input dicts field by field.

    Diffs: collateral metrics, market assumptions, top-level deal metadata.
    Does NOT diff liabilities (tranche-level — Phase 2+).

    Returns a structured dict with change lists and a total change count.
    No inference is performed here — this is purely a factual diff.
    """
    collateral_changes = _diff_section(
        v1.get("collateral", {}), v2.get("collateral", {}), _COLLATERAL_FIELDS
    )
    assumption_changes = _diff_section(
        v1.get("market_assumptions", {}),
        v2.get("market_assumptions", {}),
        _MARKET_ASSUMPTION_FIELDS,
    )
    metadata_changes = []
    for field in ("name", "issuer", "region", "currency", "manager", "close_date"):
        a, b = v1.get(field), v2.get(field)
        if a != b:
            metadata_changes.append(
                {"field": field, "v1": a, "v2": b, "direction": "changed"}
            )

    total = len(collateral_changes) + len(assumption_changes) + len(metadata_changes)
    return {
        "v1_id": v1.get("deal_id", "unknown"),
        "v2_id": v2.get("deal_id", "unknown"),
        "collateral_changes": collateral_changes,
        "assumption_changes": assumption_changes,
        "metadata_changes": metadata_changes,
        "change_count": total,
        "caveat": (
            "Tranche-level (liability) comparison not included in Phase 1. "
            "Phase 2+: add tranche diff via compare_liabilities()."
        ),
    }


def compare_scenario_results(
    v1: Dict,
    v2: Dict,
    v1_params: Optional[Dict] = None,
    v2_params: Optional[Dict] = None,
) -> Dict:
    """
    Compare two scenario result dicts (as returned by model_engine_service.get_result).

    v1_params / v2_params: scenario parameter dicts (default_rate, recovery_rate,
    spread_shock_bps). If provided, driver inference is attempted. If absent, the
    service falls back to any 'parameters' key present inside v1 / v2.

    Separates:
      - param_changes: changed input parameters [retrieved]
      - output_changes: changed engine output values [calculated]
      - likely_drivers: heuristic inferences [generated]

    Does NOT assert causality. Multiple simultaneous changes trigger an explicit
    multi-change caveat.
    """
    # Resolve parameters: explicit arg → key in result dict → empty
    p1 = v1_params or v1.get("parameters", {})
    p2 = v2_params or v2.get("parameters", {})

    # Strip internal/meta keys before diffing outputs
    v1_out = {k: v for k, v in v1.get("outputs", {}).items() if not k.startswith("_")}
    v2_out = {k: v for k, v in v2.get("outputs", {}).items() if not k.startswith("_")}

    param_changes = _diff_section(p1, p2, _MARKET_ASSUMPTION_FIELDS)
    output_changes = _diff_section(v1_out, v2_out, _OUTPUT_FIELDS)
    drivers = _infer_drivers(param_changes, output_changes)

    caveats = [_CAVEAT_GENERAL]
    if len(param_changes) > 1:
        caveats.append(_CAVEAT_MULTI_CHANGE)

    is_mock = v1.get("_mock") is not None or v2.get("_mock") is not None

    return {
        "v1_run_id": v1.get("run_id", "unknown"),
        "v2_run_id": v2.get("run_id", "unknown"),
        "v1_scenario_id": v1.get("scenario_id", "unknown"),
        "v2_scenario_id": v2.get("scenario_id", "unknown"),
        "param_changes": param_changes,
        "output_changes": output_changes,
        "likely_drivers": drivers,
        "change_count": {
            "params": len(param_changes),
            "outputs": len(output_changes),
            "drivers_inferred": len(drivers),
        },
        "caveats": caveats,
        "is_mock": is_mock,
    }


def generate_comparison_summary(comparison: Dict, mode: str = "scenario") -> str:
    """
    Produce a grounded, conservative text summary of a comparison result.

    mode: "scenario" | "deal_inputs"

    Tagging:
      [retrieved]   — facts from deal inputs
      [calculated]  — engine output values
      [generated]   — heuristic driver inferences
    """
    lines = []

    if mode == "scenario":
        lines += [
            "SCENARIO COMPARISON SUMMARY",
            "=" * 60,
        ]
        if comparison.get("is_mock"):
            lines += [
                "NOTE: Outputs are MOCK ENGINE values — not official CLO results.",
                "",
            ]
        v1_run = comparison.get("v1_run_id", "v1")
        v2_run = comparison.get("v2_run_id", "v2")
        lines += [f"  Comparing: {v1_run}  →  {v2_run}", ""]

        param_changes = comparison.get("param_changes", [])
        lines.append("PARAMETER CHANGES  [retrieved]")
        lines.append("-" * 40)
        if param_changes:
            lines += [_format_change_line(c) for c in param_changes]
        else:
            lines.append("  No parameter changes detected.")
        lines.append("")

        output_changes = comparison.get("output_changes", [])
        lines.append("OUTPUT CHANGES  [calculated — engine outputs]")
        lines.append("-" * 40)
        if output_changes:
            lines += [_format_change_line(c) for c in output_changes]
        else:
            lines.append("  No output changes detected.")
        lines.append("")

        drivers = comparison.get("likely_drivers", [])
        lines.append("LIKELY DRIVERS  [generated — heuristic inference, not model-attributed]")
        lines.append("-" * 40)
        if drivers:
            lines += [f"  • {d['statement']}" for d in drivers]
        else:
            lines += [
                "  No clear directional driver pattern identified.",
                "  Changes may reflect multiple interacting effects.",
            ]
        lines.append("")

        caveats = comparison.get("caveats", [])
        if caveats:
            lines.append("LIMITATIONS")
            lines.append("-" * 40)
            lines += [f"  ⚠ {c}" for c in caveats]
            lines.append("")

        cc = comparison.get("change_count", {})
        lines.append(
            f"Summary: {cc.get('params', 0)} parameter change(s), "
            f"{cc.get('outputs', 0)} output change(s), "
            f"{cc.get('drivers_inferred', 0)} driver(s) inferred."
        )

    elif mode == "deal_inputs":
        lines += [
            "DEAL INPUT COMPARISON SUMMARY",
            "=" * 60,
            f"  Comparing: {comparison.get('v1_id', 'v1')}  →  {comparison.get('v2_id', 'v2')}",
            "",
        ]
        for section_key, header in [
            ("collateral_changes", "COLLATERAL CHANGES  [retrieved]"),
            ("assumption_changes", "MARKET ASSUMPTION CHANGES  [retrieved]"),
            ("metadata_changes",   "DEAL METADATA CHANGES  [retrieved]"),
        ]:
            changes = comparison.get(section_key, [])
            if changes:
                lines.append(header)
                lines.append("-" * 40)
                lines += [_format_change_line(c) for c in changes]
                lines.append("")

        caveat = comparison.get("caveat")
        if caveat:
            lines += ["LIMITATIONS", "-" * 40, f"  ⚠ {caveat}", ""]

        lines.append(f"Total changes: {comparison.get('change_count', 0)}")

    return "\n".join(lines)
