"""
MOCK: cashflow-engine-mcp

This is a clearly-marked mock of the official cashflow engine MCP server.
All outputs are synthetic and must NEVER be used as official CLO outputs.
Replace this with the real cashflow-engine-mcp integration in production.
"""

import uuid
from datetime import datetime
from typing import Any, Dict


_MOCK_TAG = "MOCK_ENGINE_OUTPUT"


def run_scenario(deal_payload: Dict[str, Any], scenario_payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    MOCK: Submit a scenario to the cashflow engine.
    Returns a run_id and mock status. Does not compute real CLO metrics.
    """
    run_id = f"mock-run-{uuid.uuid4().hex[:8]}"
    return {
        "run_id": run_id,
        "status": "queued",
        "submitted_at": datetime.utcnow().isoformat(),
        "_mock": _MOCK_TAG,
    }


def get_run_status(run_id: str) -> Dict[str, Any]:
    """
    MOCK: Poll engine job status.
    Always returns 'complete' immediately in mock mode.
    """
    return {
        "run_id": run_id,
        "status": "complete",
        "_mock": _MOCK_TAG,
    }


def get_run_outputs(run_id: str) -> Dict[str, Any]:
    """
    MOCK: Retrieve scenario outputs.
    Returns synthetic metrics — NOT official CLO outputs.
    """
    return {
        "run_id": run_id,
        "source": "model_runner",
        "equity_irr": 0.142,            # MOCK: 14.2% equity IRR
        "aaa_size_pct": 0.610,          # MOCK: 61% AAA tranche
        "wac": 0.038,                   # MOCK: weighted average cost of liabilities
        "oc_cushion_aaa": 0.052,        # MOCK: OC cushion on AAA test
        "ic_cushion_aaa": 0.031,
        "equity_wal": 12.4,             # MOCK: equity WAL
        "scenario_npv": 1_820_000.0,    # MOCK: scenario NPV
        "_mock": _MOCK_TAG,
        "_warning": "All values are synthetic mocks. Replace with real engine integration.",
    }


def compare_runs(run_id_a: str, run_id_b: str) -> Dict[str, Any]:
    """
    MOCK: Compare two engine runs.
    """
    outputs_a = get_run_outputs(run_id_a)
    outputs_b = get_run_outputs(run_id_b)

    changed = {
        k: {"a": outputs_a[k], "b": outputs_b[k]}
        for k in outputs_a
        if k not in ("run_id", "_mock", "_warning") and outputs_a[k] != outputs_b.get(k)
    }

    return {
        "run_id_a": run_id_a,
        "run_id_b": run_id_b,
        "changed_outputs": changed,
        "_mock": _MOCK_TAG,
    }
