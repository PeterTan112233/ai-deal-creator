"""
app/workflows/generate_ic_memo_workflow.py

Thin orchestrator: validates inputs, generates an IC memo draft,
and emits audit events.

The IC memo is internal-facing but still requires approval before distribution
even to internal stakeholders outside the deal team.

Produces a DraftDocument with approved=False.
Does NOT emit draft.approved or draft.published events.

Audit events emitted:
  draft.started   — when drafting begins
  draft.generated — on successful draft creation
  draft.failed    — if drafting fails
"""

from typing import Dict, Optional

from app.services import drafting_service
from app.services.audit_logger import record_event


def generate_ic_memo_workflow(
    deal_input: Dict,
    scenario_result: Dict,
    scenario_request: Optional[Dict] = None,
    comparison_result: Optional[Dict] = None,
    actor: str = "system",
) -> Dict:
    """
    Generate an IC memo draft from a completed scenario run.

    Parameters
    ----------
    deal_input       : Required. Deal input dict (validated deal).
    scenario_result  : Required. Scenario result from model_engine_service.get_result().
    scenario_request : Optional. Scenario request dict for parameter context.
    comparison_result: Optional. Comparison result from compare_versions_workflow.
                       If provided, a scenario comparison section is included.
    actor            : Identifies the caller in audit events.

    Returns
    -------
    {
        draft:            dict  — DraftDocument serialised via to_dict()
        draft_markdown:   str   — rendered Markdown document
        approved:         False — always False at creation
        requires_approval:True  — always True (even internal docs require approval)
        audit_events:     list
        error:            str | None
    }
    """
    deal_id = deal_input.get("deal_id", "unknown")
    audit_events = []

    if not scenario_result:
        return {
            "error": "scenario_result is required to generate an IC memo.",
            "draft": None,
            "draft_markdown": None,
            "approved": False,
            "requires_approval": True,
            "audit_events": [],
        }

    if scenario_result.get("status") not in ("complete", None):
        return {
            "error": (
                f"scenario_result has status '{scenario_result.get('status')}'. "
                "Only completed scenario results may be used to generate drafts."
            ),
            "draft": None,
            "draft_markdown": None,
            "approved": False,
            "requires_approval": True,
            "audit_events": [],
        }

    audit_events.append(record_event(
        event_type="draft.started",
        deal_id=deal_id,
        payload={
            "draft_type": "ic_memo",
            "run_id": scenario_result.get("run_id"),
            "scenario_id": scenario_result.get("scenario_id"),
            "has_comparison": comparison_result is not None,
            "is_mock": "_mock" in scenario_result,
        },
        actor=actor,
    ))

    try:
        draft = drafting_service.generate_ic_memo(
            deal_input=deal_input,
            scenario_result=scenario_result,
            scenario_request=scenario_request,
            comparison_result=comparison_result,
        )
    except Exception as exc:
        audit_events.append(record_event(
            event_type="draft.failed",
            deal_id=deal_id,
            payload={"draft_type": "ic_memo", "error": str(exc)},
            actor=actor,
        ))
        return {
            "error": f"Draft generation failed: {exc}",
            "draft": None,
            "draft_markdown": None,
            "approved": False,
            "requires_approval": True,
            "audit_events": audit_events,
        }

    audit_events.append(record_event(
        event_type="draft.generated",
        deal_id=deal_id,
        payload={
            "draft_id": draft.draft_id,
            "draft_type": "ic_memo",
            "sections_count": len(draft.sections),
            "has_comparison_section": comparison_result is not None,
            "approved": False,
            "requires_approval": True,
            "is_mock": draft.is_mock,
        },
        actor=actor,
    ))

    return {
        "draft": draft.to_dict(),
        "draft_markdown": draft.to_markdown(),
        "approved": False,
        "requires_approval": True,
        "audit_events": audit_events,
        "error": None,
    }
