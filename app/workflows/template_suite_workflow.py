"""
app/workflows/template_suite_workflow.py

Run all (or a filtered subset of) named scenario templates against a deal
and return a comparison table across templates.

This is the "stress testing battery" entry point: one call to apply every
relevant stress template and immediately see how the deal's equity IRR,
OC cushion, and NPV respond.

Internally delegates to run_scenario_workflow for each template, then
builds a comparison table identical in structure to batch_scenario_workflow.

IMPORTANT: All outputs are tagged [demo]. Not for investment decisions.
"""

from typing import Any, Dict, List, Optional

from app.services import audit_logger, model_engine_service, scenario_template_service
from app.services.validation_service import validate_deal_input
from app.workflows.run_scenario_workflow import run_scenario_workflow


# ---------------------------------------------------------------------------
# Metrics for comparison table
# ---------------------------------------------------------------------------

_HIGHER_IS_BETTER = {
    "equity_irr", "oc_cushion_aaa", "ic_cushion_aaa", "equity_wal", "scenario_npv",
}

_COMPARE_METRICS = [
    "equity_irr", "oc_cushion_aaa", "ic_cushion_aaa", "wac", "scenario_npv",
]


# ---------------------------------------------------------------------------
# Main workflow
# ---------------------------------------------------------------------------

def template_suite_workflow(
    deal_input: Dict[str, Any],
    template_ids: Optional[List[str]] = None,
    scenario_type: Optional[str] = None,
    tag: Optional[str] = None,
    actor: str = "system",
) -> Dict[str, Any]:
    """
    Run a set of named scenario templates against a deal.

    Parameters
    ----------
    deal_input    : Deal input dict (validated).
    template_ids  : Explicit list of template IDs to run.  If None, all
                    templates matching scenario_type / tag filters are used.
    scenario_type : If template_ids is None, filter by scenario_type.
    tag           : If template_ids is None, filter by tag.
    actor         : Caller identity for audit trail.

    Returns
    -------
    {
        "deal_id":       str,
        "templates_run": int,
        "results":       List[{template_id, template_name, scenario_type,
                               parameters, outputs, status, error}],
        "comparison_table": List[{metric, values, best, worst}],
        "audit_events":  List[str],
        "is_mock":       bool,
        "error":         str | None,
    }
    """
    deal_id = deal_input.get("deal_id", "unknown")
    audit_events: List[str] = []
    errors: List[str] = []

    # Validate deal first
    validation = validate_deal_input(deal_input)
    if not validation.get("valid"):
        return _result(deal_id, [], [], audit_events,
                       error=f"Deal validation failed: {validation.get('errors', [])}")

    # Resolve template list
    if template_ids is not None:
        templates = [
            t for tid in template_ids
            if (t := scenario_template_service.get_template(tid)) is not None
        ]
        missing = set(template_ids) - {t["template_id"] for t in templates}
        if missing:
            errors.append(f"Unknown template IDs: {sorted(missing)}")
    else:
        templates = scenario_template_service.list_templates(
            scenario_type=scenario_type, tag=tag
        )

    if not templates:
        return _result(deal_id, [], [], audit_events,
                       error="No templates matched the specified filters.")

    # Audit: suite started
    audit_events.append(audit_logger.record_event(
        event_type="template_suite.started",
        deal_id=deal_id,
        actor=actor,
        payload={"templates": [t["template_id"] for t in templates]},
    )["event_id"])

    # Run each template
    results: List[Dict[str, Any]] = []
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
        scen_result = scen.get("scenario_result", {})
        outputs = scen_result.get("outputs", {}) if scen_result else {}
        status = "complete" if not scen.get("error") else "failed"
        results.append({
            "template_id":   tmpl["template_id"],
            "template_name": tmpl["name"],
            "scenario_type": tmpl["scenario_type"],
            "parameters":    params,
            "outputs":       outputs,
            "run_id":        scen_result.get("run_id") if scen_result else None,
            "status":        status,
            "error":         scen.get("error"),
        })

    # Build comparison table
    comparison_table = _build_comparison_table(results)

    # Audit: suite completed
    audit_events.append(audit_logger.record_event(
        event_type="template_suite.completed",
        deal_id=deal_id,
        actor=actor,
        payload={
            "templates_run": len(results),
            "complete":      sum(1 for r in results if r["status"] == "complete"),
            "failed":        sum(1 for r in results if r["status"] == "failed"),
        },
    )["event_id"])

    return _result(deal_id, results, comparison_table, audit_events,
                   error="; ".join(errors) if errors else None)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_comparison_table(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Build a metric-by-metric comparison table across all template results."""
    complete = [r for r in results if r["status"] == "complete"]
    if len(complete) < 2:
        return []

    table = []
    for metric in _COMPARE_METRICS:
        row_values: Dict[str, Any] = {}
        for r in complete:
            v = r["outputs"].get(metric)
            if v is not None:
                row_values[r["template_id"]] = v

        if not row_values:
            continue

        higher_better = metric in _HIGHER_IS_BETTER
        best_key  = max(row_values, key=row_values.__getitem__) if higher_better \
                    else min(row_values, key=row_values.__getitem__)
        worst_key = min(row_values, key=row_values.__getitem__) if higher_better \
                    else max(row_values, key=row_values.__getitem__)

        table.append({
            "metric":        metric,
            "values":        row_values,
            "best_template": best_key,
            "worst_template": worst_key,
        })
    return table


def _result(
    deal_id: str,
    results: List[Dict],
    comparison_table: List[Dict],
    audit_events: List[str],
    error: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "deal_id":          deal_id,
        "templates_run":    len(results),
        "results":          results,
        "comparison_table": comparison_table,
        "audit_events":     audit_events,
        "is_mock":          model_engine_service.is_mock_mode(),
        "error":            error,
    }
