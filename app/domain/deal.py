from dataclasses import dataclass, field
from typing import Optional, Literal
from datetime import date, datetime


@dataclass
class Deal:
    # ------------------------------------------------------------------ #
    # USER INPUT — provided by structurer at deal creation                #
    # ------------------------------------------------------------------ #
    deal_id: str
    name: str
    issuer: str
    region: str = "US"          # US | EU | APAC
    currency: str = "USD"       # ISO 4217
    manager: Optional[str] = None
    close_date: Optional[date] = None
    notes: Optional[str] = None

    # ------------------------------------------------------------------ #
    # SYSTEM METADATA — set and managed by the platform                   #
    # ------------------------------------------------------------------ #
    status: str = "draft"       # draft | approved | published
    version: int = 1            # monotonically increasing; increments on material change
    created_at: Optional[datetime] = None
    created_by: Optional[str] = None    # user or system actor that created the deal

    # ------------------------------------------------------------------ #
    # FUTURE EXPANSION (deferred)                                         #
    # desk, product_type, legal_entity, external_ids                      #
    # ------------------------------------------------------------------ #
