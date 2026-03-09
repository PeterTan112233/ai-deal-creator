from pydantic import BaseModel, Field, field_validator
from typing import Dict, Any, Optional


class CollateralSchema(BaseModel):
    collateral_id: str
    deal_id: str
    pool_id: str
    asset_class: str
    portfolio_size: float = Field(gt=0, description="Par amount in deal currency")
    currency: str = "USD"
    was: float = Field(ge=0, description="Weighted average spread (decimal)")
    warf: float = Field(ge=0, description="Weighted average rating factor")
    wal: float = Field(ge=0, description="Weighted average life in years")
    diversity_score: float = Field(ge=0)
    ccc_bucket: float = Field(ge=0, le=1, description="CCC as fraction of portfolio")
    concentrations: Dict[str, Any] = {}
    reinvestment_assumptions: Dict[str, Any] = {}
    notes: Optional[str] = None

    @field_validator("asset_class")
    @classmethod
    def asset_class_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("asset_class cannot be empty")
        return v
