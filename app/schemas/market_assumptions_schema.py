from pydantic import BaseModel, Field
from typing import Dict, Any


class MarketAssumptionsSchema(BaseModel):
    default_rate: float = Field(default=0.03, ge=0, le=1)
    recovery_rate: float = Field(default=0.65, ge=0, le=1)
    spread_shock_bps: float = Field(default=0.0, ge=0)
    prepayment_rate: float = Field(default=0.20, ge=0, le=1)
    funding_cost_bps: float = Field(default=0.0, ge=0)
    extra: Dict[str, Any] = {}
