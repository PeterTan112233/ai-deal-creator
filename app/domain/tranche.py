from dataclasses import dataclass
from typing import Optional


@dataclass
class Tranche:
    tranche_id: str
    name: str                           # e.g. "AAA", "AA", "A", "BBB", "BB", "Equity"
    seniority: int = 1                  # 1 = most senior
    size_pct: Optional[float] = None    # fraction of total deal size (e.g. 0.60)
    size_abs: Optional[float] = None    # absolute size in deal currency
    coupon: Optional[str] = None        # e.g. "SOFR+150" or "6.25%"
    target_rating: Optional[str] = None # e.g. "Aaa", "Aa2", "A2"
    currency: str = "USD"
    payment_frequency: str = "quarterly"
    call_period_years: Optional[float] = None
    notes: Optional[str] = None
