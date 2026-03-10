"""
app/api/router.py

FastAPI router — all AI Deal Creator endpoints.

Endpoints:
  GET  /health
  POST /deals
  POST /scenarios
  POST /scenarios/batch
  POST /scenarios/sensitivity
  POST /analyze
  POST /optimize
  POST /benchmarks/compare
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
    AnalyzeRequest,
    AnalyzeResponse,
    ApplyApprovalRequest,
    BatchScenarioRequest,
    BatchScenarioResponse,
    BenchmarkCompareRequest,
    BenchmarkCompareResponse,
    CreateDealRequest,
    CreateDealResponse,
    DraftResponse,
    GenerateDraftRequest,
    GenerateIcMemoRequest,
    OptimizeRequest,
    OptimizeResponse,
    PublishCheckRequest,
    PublishCheckResponse,
    RecordApprovalRequest,
    RecordRejectionRequest,
    RequestApprovalRequest,
    RunScenarioRequest,
    RunScenarioResponse,
    SensitivityRequest,
    SensitivityResponse,
)
from app.domain.collateral import Collateral
from app.domain.deal import Deal
from app.domain.structure import Structure
from app.domain.tranche import Tranche
from app.services import approval_service
from app.workflows.create_deal_workflow import create_deal_workflow, deal_input_from_domain
from app.workflows.batch_scenario_workflow import batch_scenario_workflow
from app.workflows.benchmark_comparison_workflow import benchmark_comparison_workflow
from app.workflows.deal_analytics_workflow import deal_analytics_workflow
from app.workflows.tranche_optimizer_workflow import tranche_optimizer_workflow
from app.workflows.generate_ic_memo_workflow import generate_ic_memo_workflow
from app.workflows.generate_investor_summary_workflow import generate_investor_summary_workflow
from app.workflows.publish_check_workflow import publish_check_workflow
from app.workflows.run_scenario_workflow import run_scenario_workflow
from app.workflows.sensitivity_analysis_workflow import sensitivity_analysis_workflow

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
# POST /analyze
# ---------------------------------------------------------------------------

@router.post("/analyze", response_model=AnalyzeResponse, tags=["analytics"])
def analyze_deal(request: AnalyzeRequest):
    """
    Run a complete analytics package for a deal in one call.

    Executes the standard 4-scenario suite (Base / Mild Stress / Stress /
    Deep Stress) plus CDR and RR sensitivity sweeps, and returns:
    - Per-scenario outputs and comparison table
    - Base-case headline metrics
    - Breakeven CDR and RR thresholds
    - A formatted [demo]-tagged analytics report

    All outputs are tagged [demo] (DEMO_ANALYTICAL_ENGINE).
    """
    result = deal_analytics_workflow(
        deal_input=request.deal_input,
        custom_scenarios=request.custom_scenarios,
        run_sensitivity=request.run_sensitivity,
        actor=request.actor,
    )

    if result.get("error"):
        raise HTTPException(status_code=422, detail=result["error"])

    suite = result.get("scenario_suite", {})
    return AnalyzeResponse(
        deal_id=result["deal_id"],
        analysis_id=result["analysis_id"],
        analysed_at=result["analysed_at"],
        is_mock=result["is_mock"],
        key_metrics=result["key_metrics"],
        breakeven=result["breakeven"],
        summary_table=result["summary_table"],
        analytics_report=result["analytics_report"],
        scenarios_run=suite.get("scenarios_run", 0),
        audit_events_count=len(result.get("audit_events", [])),
        error=result.get("error"),
    )


# ---------------------------------------------------------------------------
# POST /optimize
# ---------------------------------------------------------------------------

@router.post("/optimize", response_model=OptimizeResponse, tags=["analytics"])
def optimize_structure(request: OptimizeRequest):
    """
    Find the optimal AAA tranche size for a given pool.

    Sweeps AAA size over the specified range (default 55%–72% in 0.5% steps),
    holding mezzanine fixed, and finds the structure that maximises equity IRR
    subject to OC cushion >= oc_floor and IC cushion >= ic_floor.

    Returns the optimal structure, the full feasibility table, and the
    efficiency frontier (IRR vs AAA size for all feasible points).

    All outputs are tagged [demo] (DEMO_ANALYTICAL_ENGINE).
    """
    result = tranche_optimizer_workflow(
        deal_input=request.deal_input,
        aaa_min=request.aaa_min,
        aaa_max=request.aaa_max,
        aaa_step=request.aaa_step,
        mez_size_pct=request.mez_size_pct,
        mez_coupon=request.mez_coupon,
        aaa_coupon=request.aaa_coupon,
        oc_floor=request.oc_floor,
        ic_floor=request.ic_floor,
        scenario_parameters=request.scenario_parameters,
        actor=request.actor,
    )

    if result.get("error"):
        raise HTTPException(status_code=422, detail=result["error"])

    feasible_count = sum(1 for r in result["feasibility_table"] if r.get("feasible"))
    return OptimizeResponse(
        deal_id=result["deal_id"],
        optimization_id=result["optimization_id"],
        optimised_at=result["optimised_at"],
        is_mock=result["is_mock"],
        optimal=result["optimal"],
        feasibility_table=result["feasibility_table"],
        frontier=result["frontier"],
        constraints=result["constraints"],
        infeasible_reason=result.get("infeasible_reason"),
        candidates_tested=len(result["feasibility_table"]),
        feasible_count=feasible_count,
        audit_events_count=len(result.get("audit_events", [])),
        error=result.get("error"),
    )


# ---------------------------------------------------------------------------
# POST /benchmarks/compare
# ---------------------------------------------------------------------------

@router.post("/benchmarks/compare", response_model=BenchmarkCompareResponse, tags=["analytics"])
def compare_to_benchmarks(request: BenchmarkCompareRequest):
    """
    Compare a deal's scenario outputs against historical CLO market benchmarks.

    Scores each metric (equity IRR, OC cushion, WAC, etc.) against p25/p50/p75
    percentile bands for the matching vintage + region cohort, and returns an
    overall positioning assessment (strong / median / weak / mixed).

    All benchmark data is tagged [demo] (DEMO_BENCHMARK_DATA).
    """
    result = benchmark_comparison_workflow(
        deal_input=request.deal_input,
        scenario_outputs=request.scenario_outputs,
        vintage=request.vintage,
        region=request.region,
        asset_class=request.asset_class,
        actor=request.actor,
    )

    if result.get("error"):
        raise HTTPException(status_code=422, detail=result["error"])

    return BenchmarkCompareResponse(
        deal_id=result["deal_id"],
        comparison_id=result["comparison_id"],
        compared_at=result["compared_at"],
        vintage=result["vintage"],
        region=result["region"],
        overall_position=result["overall_position"],
        overall_label=result["overall_label"],
        above_median_count=result["above_median_count"],
        below_median_count=result["below_median_count"],
        metric_scores=result["metric_scores"],
        comparison_report=result["comparison_report"],
        is_mock=result["is_mock"],
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
# POST /scenarios/batch
# ---------------------------------------------------------------------------

@router.post("/scenarios/batch", response_model=BatchScenarioResponse, tags=["scenarios"])
def run_batch_scenarios(request: BatchScenarioRequest):
    """
    Run multiple named scenarios against the same deal in a single call.

    Returns per-scenario results plus a metric-by-metric comparison table
    annotated with best/worst scenario for each metric.
    """
    scenarios = [s.model_dump() for s in request.scenarios]
    result = batch_scenario_workflow(
        deal_input=request.deal_input,
        scenarios=scenarios,
        actor=request.actor,
    )

    if result.get("error") and not result.get("results"):
        raise HTTPException(status_code=422, detail=result["error"])

    return BatchScenarioResponse(
        deal_id=result["deal_id"],
        scenarios_run=result["scenarios_run"],
        results=result["results"],
        comparison_table=result["comparison_table"],
        audit_events_count=len(result.get("audit_events", [])),
        is_mock=result["is_mock"],
        error=result.get("error"),
    )


# ---------------------------------------------------------------------------
# POST /scenarios/sensitivity
# ---------------------------------------------------------------------------

@router.post("/scenarios/sensitivity", response_model=SensitivityResponse, tags=["scenarios"])
def run_sensitivity_analysis(request: SensitivityRequest):
    """
    Sweep a single parameter over a list of values and return the output series.

    Also returns interpolated breakeven points (e.g. the default_rate at which
    equity IRR crosses zero).
    """
    result = sensitivity_analysis_workflow(
        deal_input=request.deal_input,
        parameter=request.parameter,
        values=request.values,
        base_parameters=request.base_parameters,
        actor=request.actor,
    )

    if result.get("error") and not result.get("series"):
        raise HTTPException(status_code=422, detail=result["error"])

    return SensitivityResponse(
        deal_id=result["deal_id"],
        parameter=result["parameter"],
        values_tested=result["values_tested"],
        series=result["series"],
        breakeven=result["breakeven"],
        audit_events_count=len(result.get("audit_events", [])),
        is_mock=result["is_mock"],
        error=result.get("error"),
    )


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
