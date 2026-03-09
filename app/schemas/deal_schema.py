from pydantic import BaseModel, Field
from typing import Optional
from datetime import date


class DealSchema(BaseModel):
    deal_id: str
    name: str = Field(min_length=1)
    issuer: str = Field(min_length=1)
    region: str = "US"
    currency: str = "USD"
    manager: Optional[str] = None
    close_date: Optional[date] = None
    status: str = "draft"
    version: int = Field(default=1, ge=1)
    notes: Optional[str] = None
