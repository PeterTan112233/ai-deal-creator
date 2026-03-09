"""
MOCK: portfolio-data-mcp

Synthetic pool data for development and testing.
Replace with real portfolio-data-mcp integration in production.
"""

from typing import Any, Dict, Optional

_MOCK_TAG = "MOCK_PORTFOLIO_DATA"

_MOCK_POOLS: Dict[str, Dict[str, Any]] = {
    "pool-001": {
        "pool_id": "pool-001",
        "asset_class": "broadly_syndicated_loans",
        "portfolio_size": 500_000_000,
        "currency": "USD",
        "was": 0.042,
        "warf": 2800,
        "wal": 5.2,
        "diversity_score": 62,
        "ccc_bucket": 0.055,
        "concentrations": {
            "top_obligor_pct": 0.018,
            "top_industry_pct": 0.12,
        },
        "_mock": _MOCK_TAG,
    },
    "pool-002": {
        "pool_id": "pool-002",
        "asset_class": "broadly_syndicated_loans",
        "portfolio_size": 400_000_000,
        "currency": "EUR",
        "was": 0.038,
        "warf": 2600,
        "wal": 4.8,
        "diversity_score": 58,
        "ccc_bucket": 0.040,
        "concentrations": {
            "top_obligor_pct": 0.020,
            "top_industry_pct": 0.14,
        },
        "_mock": _MOCK_TAG,
    },
}


def get_pool(pool_id: str) -> Dict[str, Any]:
    """
    MOCK: Retrieve a collateral pool by ID.
    """
    if pool_id not in _MOCK_POOLS:
        raise KeyError(f"Pool '{pool_id}' not found in mock portfolio data.")
    return _MOCK_POOLS[pool_id]


def validate_pool(pool_payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    MOCK: Validate a pool payload against basic constraints.
    Returns a validation report.
    """
    issues = []
    if pool_payload.get("portfolio_size", 0) <= 0:
        issues.append("portfolio_size must be positive")
    if pool_payload.get("diversity_score", 0) < 30:
        issues.append("diversity_score below minimum threshold of 30")
    if pool_payload.get("ccc_bucket", 0) > 0.075:
        issues.append("ccc_bucket exceeds 7.5% limit")

    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "_mock": _MOCK_TAG,
    }


def list_pool_versions(deal_id: str) -> Dict[str, Any]:
    """
    MOCK: List available pool tape versions for a deal.
    """
    return {
        "deal_id": deal_id,
        "versions": [
            {"version": 1, "pool_id": "pool-001", "date": "2025-01-10"},
            {"version": 2, "pool_id": "pool-001", "date": "2025-02-05"},
        ],
        "_mock": _MOCK_TAG,
    }
