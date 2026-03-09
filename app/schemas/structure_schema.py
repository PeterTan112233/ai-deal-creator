from pydantic import BaseModel, Field, model_validator
from typing import List, Optional
from app.schemas.tranche_schema import TrancheSchema
from app.schemas.structural_tests_schema import StructuralTestsSchema
from app.schemas.market_assumptions_schema import MarketAssumptionsSchema


class StructureSchema(BaseModel):
    structure_id: str
    deal_id: str
    tranches: List[TrancheSchema] = Field(min_length=1)
    total_size: Optional[float] = Field(default=None, gt=0)
    currency: str = "USD"
    reinvestment_period_years: Optional[float] = None
    non_call_period_years: Optional[float] = None
    structural_tests: StructuralTestsSchema = StructuralTestsSchema()
    market_assumptions: MarketAssumptionsSchema = MarketAssumptionsSchema()
    notes: Optional[str] = None

    @model_validator(mode="after")
    def tranches_seniority_unique(self) -> "StructureSchema":
        ranks = [t.seniority for t in self.tranches]
        if len(ranks) != len(set(ranks)):
            raise ValueError("Each tranche must have a unique seniority rank")
        return self
