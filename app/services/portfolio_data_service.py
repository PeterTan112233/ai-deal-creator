"""
app/services/portfolio_data_service.py

Service wrapper for the portfolio data MCP.

PHASE 1 — MOCK ONLY.
All pool data returned by this service is synthetic. It must never be used as
official pool tape data, collateral analysis, or investment analysis.

The interface of this module is designed so that Phase 2 can replace the mock
calls with real portfolio-data-mcp calls without changing any caller.

Replacement plan (Phase 2):
    validate_pool()      →  portfolio-data-mcp.validate_pool()
    get_pool()           →  portfolio-data-mcp.get_pool()
    list_pool_versions() →  portfolio-data-mcp.list_pool_versions()
"""

from typing import Any, Dict

from mcp.portfolio_data import mock_portfolio

_MOCK_MODE = True  # set to False when real MCP integration is active


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def validate_pool(pool_payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate a pool payload against basic constraints.

    Parameters
    ----------
    pool_payload : dict with portfolio_size, diversity_score, ccc_bucket

    Returns
    -------
    {
        "valid":   bool,
        "issues":  list[str],
        "_mock":   str  — present in Phase 1 only
    }

    Phase 2: replace body with portfolio-data-mcp.validate_pool() call.
    """
    return mock_portfolio.validate_pool(pool_payload)


def get_pool(pool_id: str) -> Dict[str, Any]:
    """
    Retrieve a collateral pool by ID.

    Phase 2: replace body with portfolio-data-mcp.get_pool() call.
    """
    return mock_portfolio.get_pool(pool_id)


def list_pool_versions(deal_id: str) -> Dict[str, Any]:
    """
    List available pool tape versions for a deal.

    Phase 2: replace body with portfolio-data-mcp.list_pool_versions() call.
    """
    return mock_portfolio.list_pool_versions(deal_id)


def is_mock_mode() -> bool:
    """Return True while using the mock portfolio data source."""
    return _MOCK_MODE
