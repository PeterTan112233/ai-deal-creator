"""
app/api/models.py

Pydantic request and response models for the AI Deal Creator REST API.

These models define the HTTP contract. They are intentionally separate from
the domain dataclasses (app/domain/) and Pydantic validation schemas
(app/schemas/) — their job is to describe the API surface, not the
internal domain representation.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Shared building blocks
# ---------------------------------------------------------------------------

class TrancheRequest(BaseModel):
    tranche_id: str
    name: str
    seniority: int
    size_pct: Optional[float] = None
    size_abs: Optional[float] = None
    coupon: Optional[str] = None
    target_rating: Optional[str] = None


class CollateralRequest(BaseModel):
    collateral_id: str
    pool_id: str
    asset_class: str
    portfolio_size: float = Field(gt=0)
    was: Optional[float] = None
    warf: Optional[float] = None
    wal: Optional[float] = None
    diversity_score: float
    ccc_bucket: float


class DealRequest(BaseModel):
    deal_id: str
    name: str
    issuer: str
    region: Optional[str] = None
    currency: str = "USD"
    manager: Optional[str] = None


class MarketAssumptionsRequest(BaseModel):
    default_rate: float = 0.03
    recovery_rate: float = 0.65
    spread_shock_bps: float = 0.0


# ---------------------------------------------------------------------------
# POST /deals
# ---------------------------------------------------------------------------

class CreateDealRequest(BaseModel):
    deal: DealRequest
    collateral: CollateralRequest
    tranches: List[TrancheRequest] = Field(min_length=1)
    market_assumptions: Optional[MarketAssumptionsRequest] = None
    actor: str = "api"


class CreateDealResponse(BaseModel):
    deal_id: str
    name: str
    issuer: str
    pool_id: str
    portfolio_size: float
    tranche_count: int
    status: str
    deal_input: Dict[str, Any]  # ready to pass to POST /scenarios


# ---------------------------------------------------------------------------
# POST /scenarios
# ---------------------------------------------------------------------------

class RunScenarioRequest(BaseModel):
    deal_input: Dict[str, Any]
    scenario_name: str = "Baseline"
    scenario_type: str = "base"
    parameter_overrides: Optional[Dict[str, Any]] = None
    actor: str = "api"


class RunScenarioResponse(BaseModel):
    is_mock: bool
    validation: Dict[str, Any]
    scenario_request: Optional[Dict[str, Any]]
    scenario_result: Optional[Dict[str, Any]]
    summary: Optional[str]
    audit_events_count: int
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# POST /drafts/investor-summary
# ---------------------------------------------------------------------------

class GenerateDraftRequest(BaseModel):
    deal_input: Dict[str, Any]
    scenario_result: Dict[str, Any]
    scenario_request: Optional[Dict[str, Any]] = None
    actor: str = "api"


class GenerateIcMemoRequest(BaseModel):
    deal_input: Dict[str, Any]
    scenario_result: Dict[str, Any]
    scenario_request: Optional[Dict[str, Any]] = None
    comparison_result: Optional[Dict[str, Any]] = None
    actor: str = "api"


class DraftResponse(BaseModel):
    draft: Optional[Dict[str, Any]]
    draft_markdown: Optional[str]
    approved: bool
    requires_approval: bool
    audit_events_count: int
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# POST /approvals/*
# ---------------------------------------------------------------------------

class RequestApprovalRequest(BaseModel):
    draft: Dict[str, Any]
    requested_by: str
    channel: str = "internal"


class RecordApprovalRequest(BaseModel):
    approval_record: Dict[str, Any]
    approver: str
    notes: Optional[str] = None


class RecordRejectionRequest(BaseModel):
    approval_record: Dict[str, Any]
    approver: str
    rejection_reason: str


class ApplyApprovalRequest(BaseModel):
    draft: Dict[str, Any]
    approval_record: Dict[str, Any]


# ---------------------------------------------------------------------------
# POST /scenarios/batch
# ---------------------------------------------------------------------------

class ScenarioDefinition(BaseModel):
    name: str
    type: str = "base"
    parameters: Dict[str, Any] = {}


class BatchScenarioRequest(BaseModel):
    deal_input: Dict[str, Any]
    scenarios: List[ScenarioDefinition] = Field(min_length=1)
    actor: str = "api"


class BatchScenarioResponse(BaseModel):
    deal_id: str
    scenarios_run: int
    results: List[Dict[str, Any]]
    comparison_table: List[Dict[str, Any]]
    audit_events_count: int
    is_mock: bool
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# POST /scenarios/sensitivity
# ---------------------------------------------------------------------------

class SensitivityRequest(BaseModel):
    deal_input: Dict[str, Any]
    parameter: str
    values: List[float] = Field(min_length=1)
    base_parameters: Optional[Dict[str, Any]] = None
    actor: str = "api"


class SensitivityResponse(BaseModel):
    deal_id: str
    parameter: str
    values_tested: List[float]
    series: List[Dict[str, Any]]
    breakeven: Dict[str, Any]
    audit_events_count: int
    is_mock: bool
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# POST /analyze
# ---------------------------------------------------------------------------

class AnalyzeRequest(BaseModel):
    deal_input: Dict[str, Any]
    custom_scenarios: Optional[List[Dict[str, Any]]] = None
    run_sensitivity: bool = True
    actor: str = "api"


class AnalyzeResponse(BaseModel):
    deal_id: str
    analysis_id: str
    analysed_at: str
    is_mock: bool
    key_metrics: Dict[str, Any]
    breakeven: Dict[str, Any]
    summary_table: List[Dict[str, Any]]
    analytics_report: str
    scenarios_run: int
    audit_events_count: int
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# POST /optimize
# ---------------------------------------------------------------------------

class OptimizeRequest(BaseModel):
    deal_input: Dict[str, Any]
    aaa_min: float = 0.55
    aaa_max: float = 0.72
    aaa_step: float = 0.005
    mez_size_pct: float = 0.08
    mez_coupon: str = "SOFR+200"
    aaa_coupon: str = "SOFR+145"
    oc_floor: float = 0.18
    ic_floor: float = 0.10
    scenario_parameters: Optional[Dict[str, Any]] = None
    actor: str = "api"


class OptimizeResponse(BaseModel):
    deal_id: str
    optimization_id: str
    optimised_at: str
    is_mock: bool
    optimal: Optional[Dict[str, Any]]
    feasibility_table: List[Dict[str, Any]]
    frontier: List[Dict[str, Any]]
    constraints: Dict[str, Any]
    infeasible_reason: Optional[str]
    candidates_tested: int
    feasible_count: int
    audit_events_count: int
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# POST /benchmarks/compare
# ---------------------------------------------------------------------------

class BenchmarkCompareRequest(BaseModel):
    deal_input: Dict[str, Any]
    scenario_outputs: Dict[str, Any]
    vintage: Optional[int] = None
    region: Optional[str] = None
    asset_class: str = "broadly_syndicated_loans"
    actor: str = "api"


class BenchmarkCompareResponse(BaseModel):
    deal_id: str
    comparison_id: str
    compared_at: str
    vintage: int
    region: str
    overall_position: str
    overall_label: str
    above_median_count: int
    below_median_count: int
    metric_scores: List[Dict[str, Any]]
    comparison_report: str
    is_mock: bool
    audit_events_count: int
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# POST /pipeline
# ---------------------------------------------------------------------------

class PipelineRequest(BaseModel):
    deal_input: Dict[str, Any]
    run_sensitivity: bool = False
    run_optimizer: bool = True
    run_benchmark: bool = True
    run_draft: bool = True
    vintage: Optional[int] = None
    region: Optional[str] = None
    optimizer_kwargs: Optional[Dict[str, Any]] = None
    actor: str = "api"


class PipelineResponse(BaseModel):
    pipeline_id: str
    deal_id: str
    run_at: str
    is_mock: bool
    stages: Dict[str, Any]
    pipeline_summary: str
    audit_events_count: int
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# POST /compare
# ---------------------------------------------------------------------------

class CompareRequest(BaseModel):
    v1_deal: Dict[str, Any]
    v2_deal: Optional[Dict[str, Any]] = None
    v1_result: Optional[Dict[str, Any]] = None
    v2_result: Optional[Dict[str, Any]] = None
    actor: str = "api"


class CompareResponse(BaseModel):
    deal_comparison: Optional[Dict[str, Any]]
    scenario_comparison: Optional[Dict[str, Any]]
    summary: Optional[str]
    audit_events_count: int
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# POST /publish-check
# ---------------------------------------------------------------------------

class PublishCheckRequest(BaseModel):
    draft: Dict[str, Any]
    approval_record: Optional[Dict[str, Any]] = None
    target_channel: str = "internal"
    actor: str = "api"


class PublishCheckResponse(BaseModel):
    passed: bool
    recommendation: str
    blocking_reasons: List[str]
    warnings: List[str]
    checks_run: List[Dict[str, Any]]
    draft_id: str
    draft_type: str
    target_channel: str


# ---------------------------------------------------------------------------
# GET /deals  /  GET /deals/{deal_id}  /  DELETE /deals/{deal_id}
# ---------------------------------------------------------------------------

class DealSummaryResponse(BaseModel):
    deal_id: str
    name: str
    issuer: str
    region: Optional[str]
    currency: str
    manager: Optional[str]
    registered_at: str
    status: str
    portfolio_size: Optional[float]
    asset_class: Optional[str]
    tranche_count: int
    pipeline_count: int
    last_pipeline_at: Optional[str]


class DealDetailResponse(DealSummaryResponse):
    deal_input: Dict[str, Any]
    last_pipeline_result: Optional[Dict[str, Any]]


class DealListResponse(BaseModel):
    total: int
    deals: List[DealSummaryResponse]


class DeleteDealResponse(BaseModel):
    deal_id: str
    deleted: bool


# ---------------------------------------------------------------------------
# GET /scenarios/templates  /  POST /scenarios/from-template
# ---------------------------------------------------------------------------

class ScenarioTemplateResponse(BaseModel):
    template_id: str
    name: str
    description: str
    scenario_type: str
    tags: List[str]
    parameters: Dict[str, Any]


class TemplateListResponse(BaseModel):
    total: int
    templates: List[ScenarioTemplateResponse]


class RunFromTemplateRequest(BaseModel):
    deal_input: Dict[str, Any]
    template_id: str
    parameter_overrides: Optional[Dict[str, Any]] = None
    actor: str = "api"


class RunFromTemplateResponse(BaseModel):
    template_id: str
    template_name: str
    scenario_type: str
    parameters_used: Dict[str, Any]
    is_mock: bool
    scenario_request: Optional[Dict[str, Any]]
    scenario_result: Optional[Dict[str, Any]]
    summary: Optional[str]
    audit_events_count: int
    error: Optional[str] = None
