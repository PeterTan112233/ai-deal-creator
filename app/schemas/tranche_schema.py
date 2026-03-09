from pydantic import BaseModel, Field, model_validator
from typing import Optional


class TrancheSchema(BaseModel):
    tranche_id: str
    name: str
    seniority: int = Field(ge=1)
    size_pct: Optional[float] = Field(default=None, ge=0, le=1)
    size_abs: Optional[float] = Field(default=None, gt=0)
    coupon: Optional[str] = None        # e.g. "SOFR+150" — string, not computed
    target_rating: Optional[str] = None
    currency: str = "USD"
    payment_frequency: str = "quarterly"
    call_period_years: Optional[float] = None
    notes: Optional[str] = None

    @model_validator(mode="after")
    def must_have_size(self) -> "TrancheSchema":
        if self.size_pct is None and self.size_abs is None:
            raise ValueError("Tranche must specify size_pct or size_abs")
        return self
