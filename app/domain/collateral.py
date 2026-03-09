from dataclasses import dataclass, field
from typing import Optional, Dict, Any


@dataclass
class Collateral:
    collateral_id: str
    deal_id: str
    pool_id: str
    asset_class: str
    portfolio_size: float               # par amount in deal currency
    currency: str = "USD"
    was: float = 0.0                    # weighted average spread (decimal, e.g. 0.042)
    warf: float = 0.0                   # weighted average rating factor
    wal: float = 0.0                    # weighted average life (years)
    diversity_score: float = 0.0
    ccc_bucket: float = 0.0             # CCC as fraction of portfolio
    concentrations: Dict[str, Any] = field(default_factory=dict)  # sector / obligor concentrations
    reinvestment_assumptions: Dict[str, Any] = field(default_factory=dict)
    notes: Optional[str] = None
