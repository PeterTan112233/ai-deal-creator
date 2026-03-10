"""
app/api/main.py

FastAPI application for AI Deal Creator.

Phase 1: all engine calls use mock services.
Phase 2+: set _MOCK_MODE = False in model_engine_service and
          portfolio_data_service to wire real MCP servers.

To run:
    uvicorn app.api.main:app --reload

Interactive docs:
    http://localhost:8000/docs
"""

from fastapi import FastAPI

from app.api.router import router

app = FastAPI(
    title="AI Deal Creator API",
    description=(
        "AI-assisted CLO deal structuring workspace. "
        "Phase 1: mock cashflow engine. "
        "All engine outputs are synthetic — not for investment or pricing use."
    ),
    version="0.1.0-mock",
)

app.include_router(router)
