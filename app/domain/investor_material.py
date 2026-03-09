from dataclasses import dataclass, field
from typing import Optional, List
from datetime import datetime


@dataclass
class InvestorMaterial:
    material_id: str
    deal_id: str
    material_type: str  # investor_summary | faq | term_sheet
    content: str = ""
    sources: List[str] = field(default_factory=list)  # grounded source references
    approved: bool = False
    created_at: Optional[datetime] = None
    notes: Optional[str] = None
