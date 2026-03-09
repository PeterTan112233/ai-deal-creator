from dataclasses import dataclass, field
from typing import Dict, Any


@dataclass
class StructuralTests:
    oc_tests: Dict[str, float] = field(default_factory=dict)   # tranche -> OC threshold
    ic_tests: Dict[str, float] = field(default_factory=dict)   # tranche -> IC threshold
    ccc_limit: float = 0.075                                    # CCC bucket max as fraction
    concentration_limits: Dict[str, float] = field(default_factory=dict)
    trigger_thresholds: Dict[str, float] = field(default_factory=dict)
