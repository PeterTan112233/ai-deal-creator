"""
app/workflows/stress_matrix_workflow.py

Stress Matrix: cross-tabulation of N deals × M stress templates.

For every (deal, template) pair the engine is called once and the result
stored in a flat cell list.  The matrix is then summarised along both axes:

  - deal_summaries  — per deal: min/max IRR, IRR range, worst/best template
  - template_summaries — per template: avg IRR damage, most-impacted deal

The ASCII matrix report shows IRR and OC cushion grids side-by-side.

Unlike portfolio_stress_workflow (which collapses the template axis into a
single worst-case number), the stress matrix keeps the full 2-D grid
visible — which is what analysts use to understand *which* template drives
each deal's vulnerability.

IMPORTANT: All outputs tagged [demo]. Not for investment decisions.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.services import audit_logger, model_engine_service, validation_service
from app.services import scenario_template_service
from app.workflows.run_scenario_workflow import run_scenario_workflow


# Max template columns to render in the ASCII grid (all templates still
# appear in the summary tables below the grid).
_MAX_COLS = 5


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def stress_matrix_workflow(
    deal_inputs: List[Dict[str, Any]],
    template_ids: Optional[List[str]] = None,
    scenario_type: Optional[str] = None,
    tag: Optional[str] = None,
    actor: str = "system",
) -> Dict[str, Any]:
    """
    Run a full stress template matrix across a list of deals.

    Parameters
    ----------
    deal_inputs   : List of deal input dicts.
    template_ids  : Explicit template IDs to run.  If None, uses all
                    templates matching scenario_type / tag filters.
    scenario_type : Filter templates by type (e.g. "stress").
    tag           : Filter templates by tag (e.g. "historical").
    actor         : Caller identity for audit trail.

    Returns
    -------
    {
        "matrix_id":          str,
        "run_at":             str,
        "deal_count":         int,
        "template_count":     int,
        "cells":              List[Dict],   # one per (deal, template) pair
        "deal_summaries":     List[Dict],   # one per deal
        "template_summaries": List[Dict],   # one per template
        "matrix_report":      str,
        "audit_events":       List[str],
        "is_mock":            bool,
        "error":              str | None,
    }
    """
    matrix_id = f"matrix-{uuid.uuid4().hex[:8]}"
    audit_events: List[str] = []

    if not deal_inputs:
        return _result(matrix_id, [], [], [], [], "", audit_events,
                       error="No deal inputs provided.")

    # ------------------------------------------------------------------
    # Resolve template list once (shared across all deals)
    # ------------------------------------------------------------------
    if template_ids is not None:
        templates = [
            t for tid in template_ids
            if (t := scenario_template_service.get_template(tid)) is not None
        ]
    else:
        templates = scenario_template_service.list_templates(
            scenario_type=scenario_type, tag=tag
        )

    if not templates:
        return _result(matrix_id, [], [], [], [], "", audit_events,
                       error="No templates matched the specified filters.")

    # ------------------------------------------------------------------
    # Build cell grid  (N deals × M templates)
    # ------------------------------------------------------------------
    cells: List[Dict[str, Any]] = []

    for deal_input in deal_inputs:
        deal_id   = deal_input.get("deal_id", "unknown")
        deal_name = deal_input.get("name", "")

        validation = validation_service.validate_deal_input(deal_input)
        if not validation.get("valid"):
            # Append one skipped cell per template so the grid stays N×M
            for tmpl in templates:
                cells.append(_skipped_cell(
                    deal_id, deal_name, tmpl,
                    error=f"Validation failed: {validation.get('errors', [])}",
                ))
            continue

        for tmpl in templates:
            params = dict(tmpl["parameters"])
            scen = run_scenario_workflow(
                deal_input=deal_input,
                scenario_name=tmpl["name"],
                scenario_type=tmpl["scenario_type"],
                parameter_overrides=params,
                actor=actor,
            )
            audit_events.extend(scen.get("audit_events", []))
            outputs = (scen.get("scenario_result") or {}).get("outputs", {})
            status  = "complete" if not scen.get("error") else "failed"
            cells.append({
                "deal_id":       deal_id,
                "deal_name":     deal_name,
                "template_id":   tmpl["template_id"],
                "template_name": tmpl["name"],
                "equity_irr":    outputs.get("equity_irr"),
                "oc_cushion":    outputs.get("oc_cushion_aaa"),
                "status":        status,
                "error":         scen.get("error"),
            })

    # ------------------------------------------------------------------
    # Aggregations
    # ------------------------------------------------------------------
    deal_summaries     = _build_deal_summaries(deal_inputs, cells, templates)
    template_summaries = _build_template_summaries(templates, cells)

    # ------------------------------------------------------------------
    # Report
    # ------------------------------------------------------------------
    matrix_report = _format_matrix_report(
        deal_inputs, templates, cells,
        deal_summaries, template_summaries, matrix_id,
    )

    # ------------------------------------------------------------------
    # Audit
    # ------------------------------------------------------------------
    ok_cells = sum(1 for c in cells if c["status"] == "complete")
    audit_events.append(audit_logger.record_event(
        event_type="stress_matrix.completed",
        deal_id="portfolio",
        actor=actor,
        payload={
            "matrix_id":      matrix_id,
            "deal_count":     len(deal_inputs),
            "template_count": len(templates),
            "cell_count":     len(cells),
            "ok_cells":       ok_cells,
        },
    )["event_id"])

    return _result(
        matrix_id, cells, deal_summaries, template_summaries,
        templates, matrix_report, audit_events,
    )


# ---------------------------------------------------------------------------
# Cell factory helpers
# ---------------------------------------------------------------------------

def _skipped_cell(
    deal_id: str,
    deal_name: str,
    tmpl: Dict[str, Any],
    error: str,
) -> Dict[str, Any]:
    return {
        "deal_id":       deal_id,
        "deal_name":     deal_name,
        "template_id":   tmpl["template_id"],
        "template_name": tmpl["name"],
        "equity_irr":    None,
        "oc_cushion":    None,
        "status":        "skipped",
        "error":         error,
    }


# ---------------------------------------------------------------------------
# Aggregation helpers
# ---------------------------------------------------------------------------

def _build_deal_summaries(
    deal_inputs: List[Dict[str, Any]],
    cells: List[Dict[str, Any]],
    templates: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    summaries = []
    for deal_input in deal_inputs:
        deal_id   = deal_input.get("deal_id", "unknown")
        deal_name = deal_input.get("name", "")

        deal_cells = [c for c in cells if c["deal_id"] == deal_id]
        ok_cells   = [c for c in deal_cells if c["status"] == "complete"]

        irr_vals = [c["equity_irr"] for c in ok_cells if c["equity_irr"] is not None]
        oc_vals  = [c["oc_cushion"] for c in ok_cells if c["oc_cushion"]  is not None]

        if not irr_vals:
            # All cells skipped or failed
            first_error = next(
                (c["error"] for c in deal_cells if c["error"]), None
            )
            summaries.append({
                "deal_id":        deal_id,
                "deal_name":      deal_name,
                "min_irr":        None,
                "max_irr":        None,
                "irr_range":      None,
                "min_oc":         None,
                "max_oc":         None,
                "worst_template": None,
                "best_template":  None,
                "cell_count":     0,
                "status":         "error",
                "error":          first_error,
            })
            continue

        worst_cell = min(ok_cells, key=lambda c: c["equity_irr"] or float("inf"))
        best_cell  = max(ok_cells, key=lambda c: c["equity_irr"] or float("-inf"))
        summaries.append({
            "deal_id":        deal_id,
            "deal_name":      deal_name,
            "min_irr":        min(irr_vals),
            "max_irr":        max(irr_vals),
            "irr_range":      round(max(irr_vals) - min(irr_vals), 6),
            "min_oc":         min(oc_vals) if oc_vals else None,
            "max_oc":         max(oc_vals) if oc_vals else None,
            "worst_template": worst_cell["template_id"],
            "best_template":  best_cell["template_id"],
            "cell_count":     len(ok_cells),
            "status":         "ok",
            "error":          None,
        })
    return summaries


def _build_template_summaries(
    templates: List[Dict[str, Any]],
    cells: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    summaries = []
    for tmpl in templates:
        tid = tmpl["template_id"]
        tmpl_cells = [c for c in cells
                      if c["template_id"] == tid and c["status"] == "complete"]
        irr_vals = [c["equity_irr"] for c in tmpl_cells if c["equity_irr"] is not None]
        oc_vals  = [c["oc_cushion"] for c in tmpl_cells if c["oc_cushion"]  is not None]

        most_impacted = None
        if irr_vals:
            worst = min(tmpl_cells, key=lambda c: c["equity_irr"] or float("inf"))
            most_impacted = worst["deal_id"]

        summaries.append({
            "template_id":        tid,
            "template_name":      tmpl["name"],
            "avg_irr":  round(sum(irr_vals) / len(irr_vals), 6) if irr_vals else None,
            "avg_oc":   round(sum(oc_vals)  / len(oc_vals),  6) if oc_vals  else None,
            "min_irr":  min(irr_vals) if irr_vals else None,
            "max_irr":  max(irr_vals) if irr_vals else None,
            "most_impacted_deal": most_impacted,
            "cell_count":         len(tmpl_cells),
        })
    return summaries


# ---------------------------------------------------------------------------
# Report formatter
# ---------------------------------------------------------------------------

def _format_matrix_report(
    deal_inputs: List[Dict[str, Any]],
    templates: List[Dict[str, Any]],
    cells: List[Dict[str, Any]],
    deal_summaries: List[Dict[str, Any]],
    template_summaries: List[Dict[str, Any]],
    matrix_id: str,
) -> str:
    ok_cells  = sum(1 for c in cells if c["status"] == "complete")
    err_cells = len(cells) - ok_cells
    lines: List[str] = []

    # -- Header --
    lines += [
        "=" * 90,
        "  STRESS MATRIX REPORT  [demo]",
        f"  Matrix ID: {matrix_id}",
        f"  Deals: {len(deal_inputs)}  /  Templates: {len(templates)}"
        f"  /  Cells: {len(cells)} total ({ok_cells} complete, {err_cells} failed/skipped)",
        "",
        "  ALL OUTPUTS FROM DEMO_ANALYTICAL_ENGINE — NOT OFFICIAL CLO OUTPUTS",
        "=" * 90,
        "",
    ]

    # Cap grid columns
    grid_templates = templates[:_MAX_COLS]
    col_w = 12   # fixed column width
    name_w = 28

    def _col_header(tmpl: Dict) -> str:
        return tmpl["template_id"][:col_w].rjust(col_w)

    def _deal_label(di: Dict) -> str:
        return (di.get("name") or di.get("deal_id", ""))[:name_w].ljust(name_w)

    col_headers = "".join(_col_header(t) for t in grid_templates)
    separator   = "  " + "-" * (name_w + 2) + "-" * (col_w * len(grid_templates))

    # -- Equity IRR grid --
    lines += [
        "EQUITY IRR MATRIX  [demo]",
        "-" * 90,
        f"  {'Deal':<{name_w}}  {col_headers}",
        separator,
    ]
    for di in deal_inputs:
        label = _deal_label(di)
        values = ""
        for tmpl in grid_templates:
            cell = next(
                (c for c in cells
                 if c["deal_id"] == di.get("deal_id") and c["template_id"] == tmpl["template_id"]),
                None,
            )
            if cell is None or cell["equity_irr"] is None:
                values += "         n/a"
            else:
                values += f"{cell['equity_irr']:>11.1%} "
        lines.append(f"  {label}  {values}")
    if len(templates) > _MAX_COLS:
        lines.append(f"  (+ {len(templates) - _MAX_COLS} more templates — see Template Summary below)")
    lines.append("")

    # -- OC Cushion grid --
    lines += [
        "OC CUSHION MATRIX  [demo]",
        "-" * 90,
        f"  {'Deal':<{name_w}}  {col_headers}",
        separator,
    ]
    for di in deal_inputs:
        label = _deal_label(di)
        values = ""
        for tmpl in grid_templates:
            cell = next(
                (c for c in cells
                 if c["deal_id"] == di.get("deal_id") and c["template_id"] == tmpl["template_id"]),
                None,
            )
            if cell is None or cell["oc_cushion"] is None:
                values += "         n/a"
            else:
                values += f"{cell['oc_cushion']:>+11.1%} "
        lines.append(f"  {label}  {values}")
    if len(templates) > _MAX_COLS:
        lines.append(f"  (+ {len(templates) - _MAX_COLS} more templates — see Template Summary below)")
    lines.append("")

    # -- Deal Summary --
    lines += [
        "DEAL SUMMARY  [demo]",
        "-" * 90,
        f"  {'Deal':<{name_w}}  {'Min IRR':>8}  {'Max IRR':>8}  {'IRR Range':>10}  Worst Template",
        "  " + "-" * 72,
    ]
    for ds in deal_summaries:
        name = (ds["deal_name"] or ds["deal_id"])[:name_w].ljust(name_w)
        if ds["status"] == "error":
            lines.append(f"  {name}  [ERROR]")
            continue
        min_irr   = f"{ds['min_irr']:.1%}" if ds["min_irr"] is not None else "n/a"
        max_irr   = f"{ds['max_irr']:.1%}" if ds["max_irr"] is not None else "n/a"
        irr_range = f"{ds['irr_range']:.1%}" if ds["irr_range"] is not None else "n/a"
        worst     = ds.get("worst_template") or "n/a"
        lines.append(
            f"  {name}  {min_irr:>8}  {max_irr:>8}  {irr_range:>10}  {worst}"
        )
    lines.append("")

    # -- Template Summary --
    lines += [
        "TEMPLATE SUMMARY  [demo]",
        "-" * 90,
        f"  {'Template':<20}  {'Avg IRR':>8}  {'Min IRR':>8}  Most Impacted Deal",
        "  " + "-" * 70,
    ]
    for ts in template_summaries:
        avg_irr = f"{ts['avg_irr']:.1%}"  if ts["avg_irr"] is not None else "n/a"
        min_irr = f"{ts['min_irr']:.1%}"  if ts["min_irr"] is not None else "n/a"
        impacted = ts.get("most_impacted_deal") or "n/a"
        lines.append(
            f"  {ts['template_id']:<20}  {avg_irr:>8}  {min_irr:>8}  {impacted}"
        )
    lines.append("")

    # -- Footer --
    lines += [
        "=" * 90,
        "  [demo] All outputs from DEMO_ANALYTICAL_ENGINE.",
        "  Replace with real cashflow-engine-mcp outputs in Phase 2.",
        "=" * 90,
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Result builder
# ---------------------------------------------------------------------------

def _result(
    matrix_id: str,
    cells: List[Dict],
    deal_summaries: List[Dict],
    template_summaries: List[Dict],
    templates: List[Dict],
    matrix_report: str,
    audit_events: List[str],
    error: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "matrix_id":           matrix_id,
        "run_at":              datetime.now(timezone.utc).isoformat(),
        "deal_count":          len(deal_summaries),
        "template_count":      len(templates),
        "cells":               cells,
        "deal_summaries":      deal_summaries,
        "template_summaries":  template_summaries,
        "matrix_report":       matrix_report,
        "audit_events":        audit_events,
        "is_mock":             model_engine_service.is_mock_mode(),
        "error":               error,
    }
