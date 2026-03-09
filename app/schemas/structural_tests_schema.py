from pydantic import BaseModel, Field
from typing import Dict


class StructuralTestsSchema(BaseModel):
    oc_tests: Dict[str, float] = {}
    ic_tests: Dict[str, float] = {}
    ccc_limit: float = Field(default=0.075, ge=0, le=1)
    concentration_limits: Dict[str, float] = {}
    trigger_thresholds: Dict[str, float] = {}
