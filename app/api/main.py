"""
app/api/main.py

FastAPI application stub for AI Deal Creator.

PHASE 1: one working endpoint (/run-scenario) that calls the same
mock workflow used by the CLI. No auth, no database, no real engine.

Phase 2+: add real MCP integration, auth middleware, and full routing via router.py.

To run (Phase 2+):
    pip install fastapi uvicorn
    uvicorn app.api.main:app --reload
"""

# FastAPI is an optional dependency — only imported when the API is used.
# It is not required to run the CLI demo (app/main.py).
try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import JSONResponse
    from pydantic import BaseModel
    _FASTAPI_AVAILABLE = True
except ImportError:
    _FASTAPI_AVAILABLE = False

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.workflows.run_scenario_workflow import run_scenario_workflow


if not _FASTAPI_AVAILABLE:
    print("FastAPI not installed. Run: pip install fastapi uvicorn")
    print("For the CLI demo, use: python3 app/main.py")
else:
    app = FastAPI(
        title="AI Deal Creator API",
        description="MVP demo — Phase 1 mock engine. Not for production use.",
        version="0.1.0-mock",
    )

    # ------------------------------------------------------------------ #
    # Request / response models                                           #
    # ------------------------------------------------------------------ #

    class RunScenarioRequest(BaseModel):
        deal_id: str = "deal-us-bsl-001"
        scenario_name: str = "Baseline"
        scenario_type: str = "base"
        recovery_rate_override: float | None = None
        default_rate_override: float | None = None
        spread_shock_bps_override: float | None = None

    # ------------------------------------------------------------------ #
    # Routes                                                              #
    # ------------------------------------------------------------------ #

    @app.get("/health")
    def health():
        return {"status": "ok", "mode": "mock", "phase": 1}

    @app.post("/run-scenario")
    def run_scenario(request: RunScenarioRequest):
        """
        Run the MVP scenario flow against the mock engine.

        Loads the matching sample deal from data/samples/sample_deal_inputs.json,
        runs validation, mock engine submission, and returns the structured result
        plus a grounded summary.
        """
        deal_input = _load_sample_deal(request.deal_id)
        if deal_input is None:
            raise HTTPException(
                status_code=404,
                detail=f"No sample deal found for deal_id '{request.deal_id}'"
            )

        overrides = {}
        if request.recovery_rate_override is not None:
            overrides["recovery_rate"] = request.recovery_rate_override
        if request.default_rate_override is not None:
            overrides["default_rate"] = request.default_rate_override
        if request.spread_shock_bps_override is not None:
            overrides["spread_shock_bps"] = request.spread_shock_bps_override

        result = run_scenario_workflow(
            deal_input=deal_input,
            scenario_name=request.scenario_name,
            scenario_type=request.scenario_type,
            parameter_overrides=overrides,
            actor="api",
        )

        if "error" in result:
            raise HTTPException(status_code=422, detail=result["error"])

        return JSONResponse(content={
            "is_mock": result["is_mock"],
            "validation": result["validation"],
            "scenario_request": result["scenario_request"],
            "scenario_result": result["scenario_result"],
            "summary": result["summary"],
            "audit_events_count": len(result["audit_events"]),
        })


def _load_sample_deal(deal_id: str):
    sample_file = "data/samples/sample_deal_inputs.json"
    if not os.path.exists(sample_file):
        return None
    with open(sample_file) as f:
        data = json.load(f)
    for deal in data.get("deals", []):
        if deal.get("deal_id") == deal_id:
            return deal
    return None
