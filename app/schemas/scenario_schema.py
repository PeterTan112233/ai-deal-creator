from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
from datetime import datetime


class ScenarioSchema(BaseModel):
    scenario_id: str
    deal_id: str
    name: str = Field(min_length=1)
    parameters: Dict[str, Any] = Field(min_length=1, description="Must be non-empty")
    outputs: Dict[str, Any] = {}
    source: str = "model_runner"
    status: str = "draft"
    version: int = Field(default=1, ge=1)
    run_id: Optional[str] = None
    created_at: Optional[datetime] = None
    notes: Optional[str] = None
