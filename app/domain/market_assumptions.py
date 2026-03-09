from dataclasses import dataclass, field
from typing import Dict, Any


@dataclass
class MarketAssumptions:
    default_rate: float = 0.03          # annual default rate
    recovery_rate: float = 0.65         # blended recovery assumption
    spread_shock_bps: float = 0.0       # spread shock in basis points
    prepayment_rate: float = 0.20       # annual prepayment / CPR
    funding_cost_bps: float = 0.0       # additional funding cost overlay
    extra: Dict[str, Any] = field(default_factory=dict)  # extensible for future assumptions
