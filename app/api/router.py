"""
app/api/router.py

FastAPI router — all AI Deal Creator endpoints.

Endpoints:
  GET  /health
  POST /deals
  POST /scenarios
  POST /drafts/investor-summary
  POST /drafts/ic-memo
  POST /approvals/request
  POST /approvals/approve
  POST /approvals/reject
  POST /approvals/apply
  POST /publish-check

Phase 1: all engine calls go through mock services.
Phase 2+: set _MOCK_MODE = False in model_engine_service and
          portfolio_data_service — no router changes required.
"""

from fastapi import APIRouter, HTTPException

from app.api.models import (
    ApplyApprovalRequest,
    CreateDealRequest,
    CreateDealResponse,
    DraftResponse,
    GenerateDraftRequest,
    GenerateIcMemoRequest,
    PublishCheckRequest,
    PublishCheckResponse,
    RecordApprovalRequest,
    RecordRejectionRequest,
    RequestApprovalRequest,
    RunScenarioRequest,
    RunScenarioResponse,
)
from app.domain.collateral import Collateral
from app.domain.deal import Deal
from app.domain.structure import Structure
from app.domain.tranche import Tranche
from app.services import approval_service
from app.workflows.create_deal_workflow import create_deal_workflow, deal_input_from_domain
from app.workflows.generate_ic_memo_workflow import generate_ic_memo_workflow
from app.workflows.generate_investor_summary_workflow import generate_investor_summary_workflow
from app.workflows.publish_check_workflow import publish_check_workflow
from app.workflows.run_scenario_workflow import run_scenario_workflow

router = APIRouter()


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@router.get("/health", tags=["meta"])
def health():
    """Service liveness check."""
    return {"status": "ok", "mode": "mock", "phase": 1}


# ---------------------------------------------------------------------------
# POST /deals
# ---------------------------------------------------------------------------

@router.post("/deals", response_model=CreateDealResponse, tags=["deals"])
def create_deal(request: CreateDealRequest):
    """
    Validate and register a new deal with its collateral and structure.

    Returns a deal summary and a deal_input dict ready for POST /scenarios.
    """
    deal = Deal(
        deal_id=request.deal.deal_id,
        name=request.deal.name,
        issuer=request.deal.issuer,
        region=request.deal.region,
        currency=request.deal.currency,
        manager=request.deal.manager,
    )
    collateral = Collateral(
        collateral_id=request.collateral.collateral_id,
        deal_id=request.deal.deal_id,
        pool_id=request.collateral.pool_id,
        asset_class=request.collateral.asset_class,
        portfolio_size=request.collateral.portfolio_size,
        was=request.collateral.was,
        warf=request.collateral.warf,
        wal=request.collateral.wal,
        diversity_score=request.collateral.diversity_score,
        ccc_bucket=request.collateral.ccc_bucket,
    )
    tranches = [
        Tranche(
            tranche_id=t.tranche_id,
            name=t.name,
            seniority=t.seniority,
            size_pct=t.size_pct,
            size_abs=t.size_abs,
            coupon=t.coupon,
            target_rating=t.target_rating,
        )
        for t in request.tranches
    ]
    structure = Structure(
        structure_id=f"struct-{deal.deal_id}",
        deal_id=deal.deal_id,
        tranches=tranches,
    )

    try:
        summary = create_deal_workflow(deal, collateral, structure, actor=request.actor)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    market_assumptions = (
        request.market_assumptions.model_dump() if request.market_assumptions else None
    )
    deal_input = deal_input_from_domain(deal, collateral, structure, market_assumptions)

    return CreateDealResponse(
        deal_id=summary["deal_id"],
        name=summary["name"],
        issuer=summary["issuer"],
        pool_id=summary["pool_id"],
        portfolio_size=summary["portfolio_size"],
        tranche_count=summary["tranche_count"],
        status=summary["status"],
        deal_input=deal_input,
    )


# ---------------------------------------------------------------------------
# POST /scenarios
# ---------------------------------------------------------------------------

@router.post("/scenarios", response_model=RunScenarioResponse, tags=["scenarios"])
def run_scenario(request: RunScenarioRequest):
    """
    Submit a deal to the cashflow engine and return structured results.

    Pass the deal_input from POST /deals response directly.
    """
    result = run_scenario_workflow(
        deal_input=request.deal_input,
        scenario_name=request.scenario_name,
        scenario_type=request.scenario_type,
        parameter_overrides=request.parameter_overrides,
        actor=request.actor,
    )

    if result.get("error") and result.get("scenario_result") is None:
        raise HTTPException(status_code=422, detail=result["error"])

    return RunScenarioResponse(
        is_mock=result["is_mock"],
        validation=result["validation"],
        scenario_request=result.get("scenario_request"),
        scenario_result=result.get("scenario_result"),
        summary=result.get("summary"),
        audit_events_count=len(result.get("audit_events", [])),
        error=result.get("error"),
    )


# ---------------------------------------------------------------------------
# POST /drafts/investor-summary
# ---------------------------------------------------------------------------

@router.post("/drafts/investor-summary", response_model=DraftResponse, tags=["drafts"])
def generate_investor_summary(request: GenerateDraftRequest):
    """Generate an investor summary draft from a completed scenario result."""
    result = generate_investor_summary_workflow(
        deal_input=request.deal_input,
        scenario_result=request.scenario_result,
        scenario_request=request.scenario_request,
        actor=request.actor,
    )

    if result.get("error"):
        raise HTTPException(status_code=422, detail=result["error"])

    return DraftResponse(
        draft=result["draft"],
        draft_markdown=result["draft_markdown"],
        approved=result["approved"],
        requires_approval=result["requires_approval"],
        audit_events_count=len(result.get("audit_events", [])),
        error=result.get("error"),
    )


# ---------------------------------------------------------------------------
# POST /drafts/ic-memo
# ---------------------------------------------------------------------------

@router.post("/drafts/ic-memo", response_model=DraftResponse, tags=["drafts"])
def generate_ic_memo(request: GenerateIcMemoRequest):
    """Generate an IC memo draft from a completed scenario result."""
    result = generate_ic_memo_workflow(
        deal_input=request.deal_input,
        scenario_result=request.scenario_result,
        scenario_request=request.scenario_request,
        comparison_result=request.comparison_result,
        actor=request.actor,
    )

    if result.get("error"):
        raise HTTPException(status_code=422, detail=result["error"])

    return DraftResponse(
        draft=result["draft"],
        draft_markdown=result["draft_markdown"],
        approved=result["approved"],
        requires_approval=result["requires_approval"],
        audit_events_count=len(result.get("audit_events", [])),
        error=result.get("error"),
    )


# ---------------------------------------------------------------------------
# POST /approvals/*
# ---------------------------------------------------------------------------

@router.post("/approvals/request", tags=["approvals"])
def request_approval_endpoint(request: RequestApprovalRequest):
    """Create a pending approval record for a draft."""
    try:
        record = approval_service.request_approval(
            draft=request.draft,
            requested_by=request.requested_by,
            channel=request.channel,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return record


@router.post("/approvals/approve", tags=["approvals"])
def approve_endpoint(request: RecordApprovalRequest):
    """Record an approval decision — transitions the record to status='approved'."""
    try:
        record = approval_service.record_approval(
            approval_record=request.approval_record,
            approver=request.approver,
            notes=request.notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return record


@router.post("/approvals/reject", tags=["approvals"])
def reject_endpoint(request: RecordRejectionRequest):
    """Record a rejection — transitions the record to status='rejected'."""
    try:
        record = approval_service.record_rejection(
            approval_record=request.approval_record,
            approver=request.approver,
            rejection_reason=request.rejection_reason,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return record


@router.post("/approvals/apply", tags=["approvals"])
def apply_approval_endpoint(request: ApplyApprovalRequest):
    """
    Stamp a draft as approved=True using a valid approval record.
    This is the only path by which draft.approved can become True.
    """
    try:
        approved_draft = approval_service.apply_approval_to_draft(
            draft=request.draft,
            approval_record=request.approval_record,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return approved_draft


# ---------------------------------------------------------------------------
# POST /publish-check
# ---------------------------------------------------------------------------

@router.post("/publish-check", response_model=PublishCheckResponse, tags=["publish"])
def publish_check(request: PublishCheckRequest):
    """
    Run the publish-readiness gate on a draft.

    Returns APPROVED_TO_PUBLISH, REVIEW_REQUIRED, or BLOCKED.
    APPROVED_TO_PUBLISH means the governance gate is satisfied — it does NOT
    trigger actual publication (Phase 2+).
    """
    result = publish_check_workflow(
        draft=request.draft,
        approval_record=request.approval_record,
        target_channel=request.target_channel,
        actor=request.actor,
    )

    return PublishCheckResponse(
        passed=result["pass"],
        recommendation=result["recommendation"],
        blocking_reasons=result["blocking_reasons"],
        warnings=result["warnings"],
        checks_run=result["checks_run"],
        draft_id=result["draft_id"],
        draft_type=result["draft_type"],
        target_channel=result["target_channel"],
    )
