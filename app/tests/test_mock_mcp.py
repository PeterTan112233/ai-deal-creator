"""
Tests for mock MCP stubs.
Verifies mock data shape and _mock tag presence.
"""

import pytest
from mcp.cashflow_engine import mock_engine
from mcp.portfolio_data import mock_portfolio


# --- cashflow engine mock ---

def test_run_scenario_returns_run_id():
    result = mock_engine.run_scenario(
        deal_payload={"deal_id": "d1"},
        scenario_payload={"default_rate": 0.03},
    )
    assert "run_id" in result
    assert result["run_id"].startswith("mock-run-")
    assert result["_mock"] == "MOCK_ENGINE_OUTPUT"


def test_get_run_status_complete():
    status = mock_engine.get_run_status("mock-run-abc123")
    assert status["status"] == "complete"


def test_get_run_outputs_has_required_fields():
    outputs = mock_engine.get_run_outputs("mock-run-abc123")
    assert "equity_irr" in outputs
    assert "aaa_size_pct" in outputs
    assert outputs["_mock"] == "MOCK_ENGINE_OUTPUT"


# --- portfolio data mock ---

def test_get_pool_known_id():
    pool = mock_portfolio.get_pool("pool-001")
    assert pool["pool_id"] == "pool-001"
    assert pool["portfolio_size"] == 500_000_000
    assert pool["_mock"] == "MOCK_PORTFOLIO_DATA"


def test_get_pool_unknown_id():
    with pytest.raises(KeyError):
        mock_portfolio.get_pool("pool-999")


def test_validate_pool_passes():
    result = mock_portfolio.validate_pool({
        "portfolio_size": 500_000_000,
        "diversity_score": 62,
        "ccc_bucket": 0.055,
    })
    assert result["valid"] is True
    assert result["issues"] == []


def test_validate_pool_fails_high_ccc():
    result = mock_portfolio.validate_pool({
        "portfolio_size": 500_000_000,
        "diversity_score": 62,
        "ccc_bucket": 0.10,
    })
    assert result["valid"] is False
    assert any("ccc" in issue.lower() for issue in result["issues"])


def test_validate_pool_fails_low_diversity():
    result = mock_portfolio.validate_pool({
        "portfolio_size": 500_000_000,
        "diversity_score": 20,
        "ccc_bucket": 0.05,
    })
    assert result["valid"] is False
