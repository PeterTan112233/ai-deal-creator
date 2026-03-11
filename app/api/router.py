"""
app/api/router.py

FastAPI router — all AI Deal Creator endpoints.

Endpoints:
  GET    /health
  POST   /deals
  GET    /deals
  GET    /deals/{deal_id}
  DELETE /deals/{deal_id}
  POST   /scenarios
  POST   /scenarios/batch
  POST   /scenarios/sensitivity
  POST   /analyze
  POST   /optimize
  POST   /benchmarks/compare
  POST   /pipeline
  POST   /compare
  POST   /drafts/investor-summary
  POST   /drafts/ic-memo
  POST   /approvals/request
  POST   /approvals/approve
  POST   /approvals/reject
  POST   /approvals/apply
  POST   /publish-check

Phase 1: all engine calls go through mock services.
Phase 2+: set _MOCK_MODE = False in model_engine_service and
          portfolio_data_service — no router changes required.
"""

from typing import Optional
from fastapi import APIRouter, HTTPException

from app.api.models import (
    AnalyzeRequest,
    AnalyzeResponse,
    DealAnalyzeRequest,
    DealRerunRequest,
    DealScoringRequest,
    PortfolioAnalyzeRequest,
    PortfolioAnalyzeResponse,
    PortfolioScoringRequest,
    PortfolioScoringResponse,
    StressMatrixRequest,
    StressMatrixResponse,
    PortfolioStressRequest,
    PortfolioStressResponse,
    ScoringRequest,
    ScoringResponse,
    WatchlistCheckRequest,
    WatchlistCheckResponse,
    WatchlistItemRequest,
    WatchlistItemResponse,
    WatchlistListResponse,
    ApplyApprovalRequest,
    BatchScenarioRequest,
    BatchScenarioResponse,
    BenchmarkCompareRequest,
    BenchmarkCompareResponse,
    CompareRequest,
    CompareResponse,
    CreateDealRequest,
    CreateDealResponse,
    DealDetailResponse,
    DealListResponse,
    DealSummaryResponse,
    DeleteDealResponse,
    DraftResponse,
    GenerateDraftRequest,
    GenerateIcMemoRequest,
    OptimizeRequest,
    OptimizeResponse,
    PipelineRequest,
    PipelineResponse,
    PublishCheckRequest,
    PublishCheckResponse,
    RecordApprovalRequest,
    RecordRejectionRequest,
    RequestApprovalRequest,
    RunFromTemplateRequest,
    RunFromTemplateResponse,
    RunScenarioRequest,
    RunScenarioResponse,
    SensitivityRequest,
    SensitivityResponse,
    ScenarioTemplateResponse,
    TemplateListResponse,
    TemplateSuiteRequest,
    TemplateSuiteResponse,
)
from app.services import deal_registry_service, scenario_template_service
from app.workflows.template_suite_workflow import template_suite_workflow
from app.workflows.portfolio_analytics_workflow import portfolio_analytics_workflow
from app.workflows.portfolio_stress_workflow import portfolio_stress_workflow
from app.workflows.stress_matrix_workflow import stress_matrix_workflow
from app.workflows.portfolio_scoring_workflow import portfolio_scoring_workflow as _portfolio_scoring_workflow
from app.workflows.deal_scoring_workflow import deal_scoring_workflow
from app.services import watchlist_service
from app.workflows.watchlist_workflow import watchlist_check_workflow
from app.domain.collateral import Collateral
from app.domain.deal import Deal
from app.domain.structure import Structure
from app.domain.tranche import Tranche
from app.services import approval_service
from app.workflows.create_deal_workflow import create_deal_workflow, deal_input_from_domain
from app.workflows.batch_scenario_workflow import batch_scenario_workflow
from app.workflows.benchmark_comparison_workflow import benchmark_comparison_workflow
from app.workflows.compare_versions_workflow import compare_versions_workflow
from app.workflows.deal_analytics_workflow import deal_analytics_workflow
from app.workflows.full_pipeline_workflow import full_pipeline_workflow
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

    # Auto-register in the deal registry for GET /deals retrieval
    deal_registry_service.register(deal_input)

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
# POST /pipeline
# ---------------------------------------------------------------------------

@router.post("/pipeline", response_model=PipelineResponse, tags=["analytics"])
def run_pipeline(request: PipelineRequest):
    """
    Run the full end-to-end deal analytics pipeline in a single call.

    Chains: analytics (4-scenario suite) → tranche optimizer →
    benchmark comparison → investor summary draft.

    Each stage is optional and can be toggled via run_* flags.
    If the analytics stage fails (e.g. invalid deal), subsequent stages
    are skipped.

    All outputs are tagged [demo].
    """
    result = full_pipeline_workflow(
        deal_input=request.deal_input,
        run_sensitivity=request.run_sensitivity,
        run_optimizer=request.run_optimizer,
        run_benchmark=request.run_benchmark,
        run_draft=request.run_draft,
        vintage=request.vintage,
        region=request.region,
        optimizer_kwargs=request.optimizer_kwargs,
        actor=request.actor,
    )

    if result.get("error") and not result["stages"]["analytics"]:
        raise HTTPException(status_code=422, detail=result["error"])

    # Persist pipeline result in the registry (best-effort; ignores unknown deal_ids)
    deal_registry_service.update_pipeline_result(result["deal_id"], result)

    return PipelineResponse(
        pipeline_id=result["pipeline_id"],
        deal_id=result["deal_id"],
        run_at=result["run_at"],
        is_mock=result["is_mock"],
        stages=result["stages"],
        pipeline_summary=result["pipeline_summary"],
        audit_events_count=len(result.get("audit_events", [])),
        error=result.get("error"),
    )


# ---------------------------------------------------------------------------
# POST /compare
# ---------------------------------------------------------------------------

@router.post("/compare", response_model=CompareResponse, tags=["analytics"])
def compare_versions(request: CompareRequest):
    """
    Compare two deal versions and/or two scenario results.

    Modes:
      - Deal comparison:    provide v1_deal + v2_deal
      - Scenario comparison: provide v1_deal + v1_result + v2_result
      - Both:               provide all four

    Returns changed inputs, changed outputs, and a grounded text summary.
    """
    if request.v2_deal is None and request.v2_result is None:
        raise HTTPException(
            status_code=422,
            detail="Provide at least v2_deal (deal comparison) or v2_result (scenario comparison).",
        )

    result = compare_versions_workflow(
        v1_deal=request.v1_deal,
        v2_deal=request.v2_deal,
        v1_result=request.v1_result,
        v2_result=request.v2_result,
        actor=request.actor,
    )

    if result.get("error"):
        raise HTTPException(status_code=422, detail=result["error"])

    return CompareResponse(
        deal_comparison=result.get("deal_comparison"),
        scenario_comparison=result.get("scenario_comparison"),
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


# ---------------------------------------------------------------------------
# GET /deals
# ---------------------------------------------------------------------------

@router.get("/deals", response_model=DealListResponse, tags=["deals"])
def list_deals():
    """
    List all deals registered in the in-memory deal registry.

    Deals are registered automatically when POST /deals is called.
    Sorted by registration time, most recent first.
    """
    records = deal_registry_service.list_all()
    return DealListResponse(
        total=len(records),
        deals=[DealSummaryResponse(**{k: v for k, v in r.items()
                                      if k not in ("deal_input", "last_pipeline_result")})
               for r in records],
    )


# ---------------------------------------------------------------------------
# GET /deals/{deal_id}
# ---------------------------------------------------------------------------

@router.get("/deals/{deal_id}", response_model=DealDetailResponse, tags=["deals"])
def get_deal(deal_id: str):
    """
    Retrieve a single deal from the registry, including its last pipeline result.

    Returns 404 if the deal_id is not found in the registry.
    """
    record = deal_registry_service.get(deal_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Deal '{deal_id}' not found in registry.")
    return DealDetailResponse(**record)


# ---------------------------------------------------------------------------
# DELETE /deals/{deal_id}
# ---------------------------------------------------------------------------

@router.delete("/deals/{deal_id}", response_model=DeleteDealResponse, tags=["deals"])
def delete_deal(deal_id: str):
    """
    Remove a deal from the in-memory registry.

    Returns deleted=True if the deal was found and removed,
    deleted=False if it was not in the registry.
    """
    deleted = deal_registry_service.unregister(deal_id)
    return DeleteDealResponse(deal_id=deal_id, deleted=deleted)


# ---------------------------------------------------------------------------
# GET /scenarios/templates
# ---------------------------------------------------------------------------

@router.get("/scenarios/templates", response_model=TemplateListResponse, tags=["scenarios"])
def list_scenario_templates(scenario_type: str = None, tag: str = None):
    """
    List all named scenario templates.

    Optional query parameters:
      - scenario_type: filter by "base", "stress", or "regulatory"
      - tag:           filter by tag string (e.g. "historical", "gfc")

    Templates are tagged [demo] — parameters are illustrative, not official
    rating-agency or regulatory calibrations.
    """
    templates = scenario_template_service.list_templates(
        scenario_type=scenario_type, tag=tag
    )
    return TemplateListResponse(
        total=len(templates),
        templates=[ScenarioTemplateResponse(**t) for t in templates],
    )


# ---------------------------------------------------------------------------
# POST /scenarios/from-template
# ---------------------------------------------------------------------------

@router.post("/scenarios/from-template", response_model=RunFromTemplateResponse,
             tags=["scenarios"])
def run_from_template(request: RunFromTemplateRequest):
    """
    Run a named scenario template against a deal.

    Looks up the named template (e.g. "gfc-2008", "covid-2020", "base"),
    applies any parameter_overrides, then submits to the scenario engine.

    Returns the scenario result plus the parameters that were used.
    """
    try:
        params = scenario_template_service.apply_template(
            request.template_id, overrides=request.parameter_overrides
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    tmpl = scenario_template_service.get_template(request.template_id)

    result = run_scenario_workflow(
        deal_input=request.deal_input,
        scenario_name=tmpl["name"],
        scenario_type=tmpl["scenario_type"],
        parameter_overrides=params,
        actor=request.actor,
    )

    return RunFromTemplateResponse(
        template_id=request.template_id,
        template_name=tmpl["name"],
        scenario_type=tmpl["scenario_type"],
        parameters_used=params,
        is_mock=result.get("is_mock", True),
        scenario_request=result.get("scenario_request"),
        scenario_result=result.get("scenario_result"),
        summary=result.get("summary"),
        audit_events_count=len(result.get("audit_events", [])),
        error=result.get("error"),
    )


# ---------------------------------------------------------------------------
# POST /scenarios/template-suite
# ---------------------------------------------------------------------------

@router.post("/scenarios/template-suite", response_model=TemplateSuiteResponse,
             tags=["scenarios"])
def run_template_suite(request: TemplateSuiteRequest):
    """
    Run all (or a filtered subset of) named scenario templates against a deal.

    Returns a per-template result list and a metric comparison table showing
    which template produces the best/worst equity IRR, OC cushion, etc.

    Filter options:
      - template_ids:   explicit list of template IDs to run
      - scenario_type:  "base", "stress", or "regulatory"
      - tag:            e.g. "historical", "standard", "regulatory"

    All outputs are tagged [demo].
    """
    result = template_suite_workflow(
        deal_input=request.deal_input,
        template_ids=request.template_ids,
        scenario_type=request.scenario_type,
        tag=request.tag,
        actor=request.actor,
    )

    if result.get("error") and result["templates_run"] == 0:
        raise HTTPException(status_code=422, detail=result["error"])

    return TemplateSuiteResponse(
        deal_id=result["deal_id"],
        templates_run=result["templates_run"],
        results=result["results"],
        comparison_table=result["comparison_table"],
        audit_events_count=len(result.get("audit_events", [])),
        is_mock=result["is_mock"],
        error=result.get("error"),
    )


# ---------------------------------------------------------------------------
# POST /portfolio/analyze
# ---------------------------------------------------------------------------

@router.post("/portfolio/analyze", response_model=PortfolioAnalyzeResponse,
             tags=["portfolio"])
def analyze_portfolio(request: PortfolioAnalyzeRequest):
    """
    Run base-case analytics across a list of deals and return an aggregated
    portfolio summary: per-deal metrics, IRR/OC rankings, region/asset-class
    concentration, and a formatted portfolio report.

    All outputs are tagged [demo].
    """
    result = portfolio_analytics_workflow(
        deal_inputs=request.deal_inputs,
        metrics=request.metrics,
        actor=request.actor,
    )

    return PortfolioAnalyzeResponse(
        portfolio_id=result["portfolio_id"],
        analysed_at=result["analysed_at"],
        deal_count=result["deal_count"],
        deals=result["deals"],
        aggregate=result["aggregate"],
        rankings=result["rankings"],
        concentration=result["concentration"],
        portfolio_report=result["portfolio_report"],
        audit_events_count=len(result.get("audit_events", [])),
        is_mock=result["is_mock"],
        error=result.get("error"),
    )


# ---------------------------------------------------------------------------
# GET  /watchlist
# POST /watchlist
# DELETE /watchlist/{item_id}
# POST /watchlist/check
# ---------------------------------------------------------------------------

@router.get("/watchlist", response_model=WatchlistListResponse, tags=["watchlist"])
def list_watchlist(deal_id: Optional[str] = None):
    """List all active watchlist items, optionally filtered to a specific deal."""
    items = watchlist_service.list_items(deal_id=deal_id)
    return WatchlistListResponse(
        total=len(items),
        items=[WatchlistItemResponse(**i) for i in items],
    )


@router.post("/watchlist", response_model=WatchlistItemResponse,
             status_code=201, tags=["watchlist"])
def create_watchlist_item(request: WatchlistItemRequest):
    """
    Add a metric threshold alert to the watchlist.

    Operators: lt, lte, gt, gte, eq.
    Severity:  warning (default) or critical.
    deal_id:   if set, item only applies to that specific deal.
    """
    try:
        item = watchlist_service.add_item(
            metric=request.metric,
            operator=request.operator,
            threshold=request.threshold,
            label=request.label,
            deal_id=request.deal_id,
            severity=request.severity,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return WatchlistItemResponse(**item)


@router.delete("/watchlist/{item_id}", tags=["watchlist"])
def delete_watchlist_item(item_id: str):
    """Remove a watchlist item by ID."""
    removed = watchlist_service.remove_item(item_id)
    if not removed:
        raise HTTPException(status_code=404, detail=f"Watchlist item '{item_id}' not found.")
    return {"item_id": item_id, "deleted": True}


@router.post("/watchlist/check", response_model=WatchlistCheckResponse, tags=["watchlist"])
def check_watchlist(request: WatchlistCheckRequest):
    """
    Run the base-case scenario for a deal and evaluate all active watchlist items.

    Returns an alert for every applicable item, with triggered=True/False
    and the actual metric value that was compared.
    """
    result = watchlist_check_workflow(
        deal_input=request.deal_input,
        actor=request.actor,
    )
    return WatchlistCheckResponse(
        deal_id=result["deal_id"],
        items_checked=result["items_checked"],
        triggered_count=result["triggered_count"],
        alerts=result["alerts"],
        audit_events_count=len(result.get("audit_events", [])),
        is_mock=result["is_mock"],
        error=result.get("error"),
    )


# ---------------------------------------------------------------------------
# POST /deals/{deal_id}/pipeline
# POST /deals/{deal_id}/analyze
# ---------------------------------------------------------------------------

@router.post("/deals/{deal_id}/pipeline", response_model=PipelineResponse,
             tags=["deals"])
def rerun_deal_pipeline(deal_id: str, request: DealRerunRequest):
    """
    Re-run the full analytics pipeline on a deal that's already in the registry.

    Equivalent to POST /pipeline but looks the deal up from the registry
    instead of requiring the full deal_input in the request body.
    """
    record = deal_registry_service.get(deal_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Deal '{deal_id}' not found in registry.")

    deal_input = record.get("deal_input")
    if not deal_input:
        raise HTTPException(status_code=422, detail="Registered deal has no deal_input.")

    result = full_pipeline_workflow(
        deal_input,
        run_sensitivity=False,
        run_optimizer=request.run_optimizer,
        run_benchmark=request.run_benchmark,
        run_draft=request.run_draft,
        actor=request.actor,
    )
    deal_registry_service.update_pipeline_result(deal_id, result)
    return PipelineResponse(
        pipeline_id=result["pipeline_id"],
        deal_id=result["deal_id"],
        run_at=result["run_at"],
        is_mock=result["is_mock"],
        stages=result["stages"],
        pipeline_summary=result["pipeline_summary"],
        audit_events_count=len(result.get("audit_events", [])),
        error=result.get("error"),
    )


@router.post("/deals/{deal_id}/analyze", response_model=AnalyzeResponse,
             tags=["deals"])
def rerun_deal_analyze(deal_id: str, request: DealAnalyzeRequest):
    """
    Re-run deal analytics on a deal that's already in the registry.

    Equivalent to POST /analyze but looks the deal up from the registry.
    """
    record = deal_registry_service.get(deal_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Deal '{deal_id}' not found in registry.")

    deal_input = record.get("deal_input")
    if not deal_input:
        raise HTTPException(status_code=422, detail="Registered deal has no deal_input.")

    result = deal_analytics_workflow(
        deal_input,
        run_sensitivity=request.run_sensitivity,
        actor=request.actor,
    )
    return AnalyzeResponse(
        deal_id=result["deal_id"],
        analysis_id=result["analysis_id"],
        analysed_at=result["analysed_at"],
        is_mock=result["is_mock"],
        key_metrics=result["key_metrics"],
        breakeven=result["breakeven"],
        summary_table=result["summary_table"],
        analytics_report=result["analytics_report"],
        scenarios_run=result["scenario_suite"].get("scenarios_run", 0),
        audit_events_count=len(result.get("audit_events", [])),
        error=result.get("error"),
    )


# ---------------------------------------------------------------------------
# POST /portfolio/stress-test
# ---------------------------------------------------------------------------

@router.post("/portfolio/stress-test", response_model=PortfolioStressResponse,
             tags=["portfolio"])
def stress_test_portfolio(request: PortfolioStressRequest):
    """
    Run a named stress scenario template battery across a list of deals.

    For each deal, computes:
      - base-case IRR (reference)
      - worst-case IRR across all applied templates
      - IRR drawdown (base minus worst-case)

    Returns a risk ranking (most vulnerable deal first) and identifies
    the template that causes the greatest average IRR damage across the
    portfolio.

    All outputs are tagged [demo].
    """
    result = portfolio_stress_workflow(
        deal_inputs=request.deal_inputs,
        template_ids=request.template_ids,
        scenario_type=request.scenario_type,
        tag=request.tag,
        actor=request.actor,
    )

    if result.get("error") and result["deal_count"] == 0:
        raise HTTPException(status_code=422, detail=result["error"])

    return PortfolioStressResponse(
        stress_id=result["stress_id"],
        run_at=result["run_at"],
        deal_count=result["deal_count"],
        template_count=result["template_count"],
        deals=result["deals"],
        risk_ranking=result["risk_ranking"],
        most_sensitive_template=result["most_sensitive_template"],
        portfolio_report=result["portfolio_report"],
        audit_events_count=len(result.get("audit_events", [])),
        is_mock=result["is_mock"],
        error=result.get("error"),
    )


# ---------------------------------------------------------------------------
# POST /portfolio/stress-matrix
# ---------------------------------------------------------------------------

@router.post("/portfolio/stress-matrix", response_model=StressMatrixResponse,
             tags=["portfolio"])
def stress_matrix_portfolio(request: StressMatrixRequest):
    """
    Run a full stress template matrix across a list of deals.

    Returns a 2-D grid of (equity_irr, oc_cushion) for every (deal, template)
    pair, with per-deal and per-template aggregations showing which deals are
    most vulnerable and which templates cause the most damage.

    All outputs are tagged [demo].
    """
    result = stress_matrix_workflow(
        deal_inputs=request.deal_inputs,
        template_ids=request.template_ids,
        scenario_type=request.scenario_type,
        tag=request.tag,
        actor=request.actor,
    )

    if result.get("error") and result["deal_count"] == 0:
        raise HTTPException(status_code=422, detail=result["error"])

    return StressMatrixResponse(
        matrix_id=result["matrix_id"],
        run_at=result["run_at"],
        deal_count=result["deal_count"],
        template_count=result["template_count"],
        cells=result["cells"],
        deal_summaries=result["deal_summaries"],
        template_summaries=result["template_summaries"],
        matrix_report=result["matrix_report"],
        audit_events_count=len(result.get("audit_events", [])),
        is_mock=result["is_mock"],
        error=result.get("error"),
    )


# ---------------------------------------------------------------------------
# POST /scoring/score
# POST /deals/{deal_id}/score
# ---------------------------------------------------------------------------

def _scoring_response(result: dict) -> "ScoringResponse":
    return ScoringResponse(
        deal_id=result["deal_id"],
        scoring_id=result["scoring_id"],
        scored_at=result["scored_at"],
        composite_score=result.get("composite_score"),
        grade=result.get("grade"),
        grade_label=result.get("grade_label"),
        dimension_scores=result.get("dimension_scores", {}),
        top_drivers=result.get("top_drivers", []),
        risk_flags=result.get("risk_flags", []),
        score_report=result.get("score_report", ""),
        audit_events_count=len(result.get("audit_events", [])),
        is_mock=result["is_mock"],
        error=result.get("error"),
    )


@router.post("/scoring/score", response_model=ScoringResponse, tags=["scoring"])
def score_deal(request: ScoringRequest):
    """
    Compute a composite 0-100 risk/return score for a deal.

    Runs a base-case scenario + GFC/deep-stress templates to populate
    all four scoring dimensions:
      - IRR quality       (35%)
      - OC adequacy       (30%)
      - Stress resilience (25%)
      - Collateral quality (10%)

    Returns a letter grade (A–D) and top score drivers.
    All outputs are tagged [demo].
    """
    result = deal_scoring_workflow(
        deal_input=request.deal_input,
        actor=request.actor,
    )
    return _scoring_response(result)


@router.post("/deals/{deal_id}/score", response_model=ScoringResponse, tags=["deals"])
def score_registered_deal(deal_id: str, request: DealScoringRequest):
    """
    Score a deal that's already in the registry.

    Equivalent to POST /scoring/score but looks the deal up from the
    registry by deal_id.
    """
    record = deal_registry_service.get(deal_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Deal '{deal_id}' not found in registry.")
    deal_input = record.get("deal_input")
    if not deal_input:
        raise HTTPException(status_code=422, detail="Registered deal has no deal_input.")
    result = deal_scoring_workflow(deal_input=deal_input, actor=request.actor)
    return _scoring_response(result)


# ---------------------------------------------------------------------------
# POST /portfolio/score
# ---------------------------------------------------------------------------

@router.post("/portfolio/score", response_model=PortfolioScoringResponse,
             tags=["portfolio"])
def score_portfolio(request: PortfolioScoringRequest):
    """
    Score every deal in a portfolio and produce a unified scorecard.

    Runs deal_scoring_workflow for each deal, then aggregates:
      - Grade distribution (how many A/B/C/D)
      - Portfolio average composite score
      - Score ranking (best → worst)
      - Deals needing attention (grade C or D, or risk flags)

    Returns a formatted [demo] scorecard report.
    """
    result = _portfolio_scoring_workflow(
        deal_inputs=request.deal_inputs,
        actor=request.actor,
    )

    if result.get("error") and result["deal_count"] == 0:
        raise HTTPException(status_code=422, detail=result["error"])

    return PortfolioScoringResponse(
        scorecard_id=result["scorecard_id"],
        run_at=result["run_at"],
        deal_count=result["deal_count"],
        scored_count=result["scored_count"],
        deals=result["deals"],
        score_ranking=result["score_ranking"],
        grade_distribution=result["grade_distribution"],
        portfolio_avg_score=result["portfolio_avg_score"],
        needs_attention=result["needs_attention"],
        scorecard_report=result["scorecard_report"],
        audit_events_count=len(result.get("audit_events", [])),
        is_mock=result["is_mock"],
        error=result.get("error"),
    )
