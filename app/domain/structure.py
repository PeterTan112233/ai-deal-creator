from dataclasses import dataclass, field
from typing import List, Optional
from app.domain.tranche import Tranche
from app.domain.structural_tests import StructuralTests
from app.domain.market_assumptions import MarketAssumptions


@dataclass
class Structure:
    structure_id: str
    deal_id: str
    tranches: List[Tranche] = field(default_factory=list)
    total_size: Optional[float] = None
    currency: str = "USD"
    reinvestment_period_years: Optional[float] = None
    non_call_period_years: Optional[float] = None
    structural_tests: StructuralTests = field(default_factory=StructuralTests)
    market_assumptions: MarketAssumptions = field(default_factory=MarketAssumptions)
    notes: Optional[str] = None
