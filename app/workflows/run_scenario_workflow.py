"""
app/workflows/run_scenario_workflow.py

MVP runnable flow: load deal input → validate → build scenario request →
simulate engine run → collect result → generate summary → audit.

This workflow is intentionally thin — it delegates all logic to services.
Each service has a clear replacement point for Phase 2 MCP integration.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.services import audit_logger, validation_service, model_engine_service, summary_service


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def run_scenario_workflow(
    deal_input: Dict[str, Any],
    scenario_name: str = "Baseline",
    scenario_type: str = "base",
    parameter_overrides: Optional[Dict[str, Any]] = None,
    actor: str = "system",
) -> Dict[str, Any]:
    """
    Run the MVP scenario flow end-to-end.

    Args:
        deal_input:          Deal input dict matching deal_input.schema.json
        scenario_name:       Human label for the scenario
        scenario_type:       "base" | "stress" | "custom"
        parameter_overrides: Optional dict to override market_assumptions from deal_input
        actor:               Identity of the caller (for audit trail)

    Returns:
        {
            "deal_input":        original deal input,
            "validation":        validation report,
            "scenario_request":  scenario payload sent to engine,
            "scenario_result":   structured engine result,
            "summary":           plain-English grounded summary (text),
            "is_mock":           True while using mock engine,
            "audit_events":      list of audit event IDs emitted,
        }
    """
    audit_events = []
    deal_id = deal_input.get("deal_id", "unknown")

    # ------------------------------------------------------------------
    # Step 1: Validate deal input
    # ------------------------------------------------------------------
    validation = validation_service.validate_deal_input(deal_input)

    audit_events.append(audit_logger.record_event(
        event_type="deal.validated",
        deal_id=deal_id,
        actor=actor,
        payload={
            "valid": validation["valid"],
            "issues": validation["issues"],
            "warnings": validation["warnings"],
        },
    )["event_id"])

    if not validation["valid"]:
        return {
            "deal_input": deal_input,
            "validation": validation,
            "scenario_request": None,
            "scenario_result": None,
            "summary": None,
            "is_mock": model_engine_service.is_mock_mode(),
            "audit_events": audit_events,
            "error": "Deal validation failed. Fix issues before submitting to engine.",
        }

    # ------------------------------------------------------------------
    # Step 2: Build scenario request from deal market assumptions
    # ------------------------------------------------------------------
    scenario_request = _build_scenario_request(
        deal_id=deal_id,
        deal_input=deal_input,
        scenario_name=scenario_name,
        scenario_type=scenario_type,
        parameter_overrides=parameter_overrides or {},
    )

    scenario_validation = validation_service.validate_scenario_request(scenario_request)
    if not scenario_validation["valid"]:
        return {
            "deal_input": deal_input,
            "validation": validation,
            "scenario_request": scenario_request,
            "scenario_result": None,
            "summary": None,
            "is_mock": model_engine_service.is_mock_mode(),
            "audit_events": audit_events,
            "error": f"Scenario request invalid: {scenario_validation['issues']}",
        }

    # ------------------------------------------------------------------
    # Step 3: Submit to engine
    # Phase 2: model_engine_service.submit_scenario() → cashflow-engine-mcp.run_scenario()
    # ------------------------------------------------------------------
    # Attach deal_payload so the analytical engine has pool metrics + tranches
    scenario_request["deal_payload"] = {
        "deal_id":        deal_id,
        "portfolio_size": deal_input.get("collateral", {}).get("portfolio_size"),
        "was":            deal_input.get("collateral", {}).get("was"),
        "wal":            deal_input.get("collateral", {}).get("wal"),
        "diversity_score":deal_input.get("collateral", {}).get("diversity_score"),
        "ccc_bucket":     deal_input.get("collateral", {}).get("ccc_bucket"),
        "tranches":       deal_input.get("liabilities", []),
    }

    run_id = model_engine_service.submit_scenario(
        deal_id=deal_id,
        scenario_request=scenario_request,
    )

    audit_events.append(audit_logger.record_event(
        event_type="scenario.submitted",
        deal_id=deal_id,
        scenario_id=scenario_request["scenario_id"],
        actor=actor,
        payload={"run_id": run_id, "parameters": scenario_request["parameters"]},
    )["event_id"])

    # ------------------------------------------------------------------
    # Step 4: Poll for completion
    # Phase 2: replace with retry loop against cashflow-engine-mcp.get_run_status()
    # ------------------------------------------------------------------
    complete = model_engine_service.poll_until_done(run_id)
    if not complete:
        return {
            "deal_input": deal_input,
            "validation": validation,
            "scenario_request": scenario_request,
            "scenario_result": None,
            "summary": None,
            "is_mock": model_engine_service.is_mock_mode(),
            "audit_events": audit_events,
            "error": f"Engine run {run_id} did not complete.",
        }

    # ------------------------------------------------------------------
    # Step 5: Retrieve structured result
    # Phase 2: model_engine_service.get_result() → cashflow-engine-mcp.get_run_outputs()
    # ------------------------------------------------------------------
    scenario_result = model_engine_service.get_result(
        run_id=run_id,
        scenario_id=scenario_request["scenario_id"],
        deal_id=deal_id,
    )

    audit_events.append(audit_logger.record_event(
        event_type="scenario.completed",
        deal_id=deal_id,
        scenario_id=scenario_request["scenario_id"],
        actor=actor,
        payload={
            "run_id": run_id,
            "is_mock": "_mock" in scenario_result,
            "output_keys": list(scenario_result.get("outputs", {}).keys()),
        },
    )["event_id"])

    # ------------------------------------------------------------------
    # Step 6: Generate grounded summary
    # Phase 3: summary_service will fetch approved language from approved-language-mcp
    # ------------------------------------------------------------------
    summary = summary_service.generate_summary(
        deal_input=deal_input,
        scenario_request=scenario_request,
        scenario_result=scenario_result,
    )

    audit_events.append(audit_logger.record_event(
        event_type="summary.generated",
        deal_id=deal_id,
        scenario_id=scenario_request["scenario_id"],
        actor=actor,
        payload={"is_mock": "_mock" in scenario_result},
    )["event_id"])

    return {
        "deal_input": deal_input,
        "validation": validation,
        "scenario_request": scenario_request,
        "scenario_result": scenario_result,
        "summary": summary,
        "is_mock": model_engine_service.is_mock_mode(),
        "audit_events": audit_events,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_scenario_request(
    deal_id: str,
    deal_input: Dict[str, Any],
    scenario_name: str,
    scenario_type: str,
    parameter_overrides: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Build a scenario_request dict from deal market_assumptions plus any overrides.
    Structure matches scenario_request.schema.json.
    """
    base_assumptions = deal_input.get("market_assumptions", {})

    # Start from deal assumptions; allow caller to override specific parameters
    parameters = {
        "default_rate": base_assumptions.get("default_rate", 0.03),
        "recovery_rate": base_assumptions.get("recovery_rate", 0.65),
        "spread_shock_bps": base_assumptions.get("spread_shock_bps", 0),
    }
    parameters.update(parameter_overrides)

    assumptions_made = []
    if not deal_input.get("market_assumptions"):
        assumptions_made.append(
            "No market_assumptions in deal input — using defaults: "
            "default_rate=3%, recovery_rate=65%, spread_shock=0bps"
        )
    if parameter_overrides:
        assumptions_made.append(
            f"Caller overrode: {list(parameter_overrides.keys())}"
        )

    return {
        "scenario_id": f"sc-{deal_id}-{uuid.uuid4().hex[:6]}",
        "deal_id": deal_id,
        "name": scenario_name,
        "scenario_type": scenario_type,
        "parameters": parameters,
        "assumptions_made": assumptions_made,
        "flagged_ambiguities": [],
    }
