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
