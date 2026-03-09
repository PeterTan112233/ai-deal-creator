"""
app/workflows/generate_investor_summary_workflow.py

Thin orchestrator: validates inputs, generates an investor summary draft,
and emits audit events.

Produces a DraftDocument with approved=False.
Does NOT emit draft.approved or draft.published events — those belong to the
approval workflow (Phase 3+).

Audit events emitted:
  draft.started   — when drafting begins, before any content is generated
  draft.generated — on successful draft creation, with draft_id and section count
  draft.failed    — if drafting fails (e.g. missing required inputs)
"""

from typing import Dict, Optional

from app.services import drafting_service
from app.services.audit_logger import record_event


def generate_investor_summary_workflow(
    deal_input: Dict,
    scenario_result: Dict,
    scenario_request: Optional[Dict] = None,
    actor: str = "system",
) -> Dict:
    """
    Generate an investor summary draft from a completed scenario run.

    Parameters
    ----------
    deal_input      : Required. Deal input dict (validated deal).
    scenario_result : Required. Scenario result from model_engine_service.get_result().
    scenario_request: Optional. Scenario request dict for parameter context.
    actor           : Identifies the caller in audit events.

    Returns
    -------
    {
        draft:            dict  — DraftDocument serialised via to_dict()
        draft_markdown:   str   — rendered Markdown document
        approved:         False — always False at creation
        requires_approval:True  — always True for external-facing documents
        audit_events:     list
        error:            str | None
    }
    """
    deal_id = deal_input.get("deal_id", "unknown")
    audit_events = []

    # Guard: scenario_result must be present and complete
    if not scenario_result:
        return {
            "error": "scenario_result is required to generate an investor summary.",
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
            "draft_type": "investor_summary",
            "run_id": scenario_result.get("run_id"),
            "scenario_id": scenario_result.get("scenario_id"),
            "is_mock": "_mock" in scenario_result,
        },
        actor=actor,
    ))

    try:
        draft = drafting_service.generate_investor_summary(
            deal_input=deal_input,
            scenario_result=scenario_result,
            scenario_request=scenario_request,
        )
    except Exception as exc:
        audit_events.append(record_event(
            event_type="draft.failed",
            deal_id=deal_id,
            payload={"draft_type": "investor_summary", "error": str(exc)},
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
            "draft_type": "investor_summary",
            "sections_count": len(draft.sections),
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
