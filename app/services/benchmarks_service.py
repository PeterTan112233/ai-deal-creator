"""
app/services/benchmarks_service.py

Service wrapper for CLO market benchmark data.

Phase 1: backed by demo benchmark dataset (mcp/historical_deals/benchmark_data.py).
Phase 2: replace with historical-deals-mcp calls.

All data returned is tagged _source: "DEMO_BENCHMARK_DATA" and must not
be presented as official market data.
"""

from typing import Any, Dict, List, Optional

from mcp.historical_deals import benchmark_data as _bd

_MOCK_MODE = True


def get_benchmark(
    vintage: int,
    region: str = "US",
    asset_class: str = "broadly_syndicated_loans",
) -> Optional[Dict[str, Any]]:
    """
    Return benchmark percentile bands for a given vintage / region / asset class.
    Returns None if no data is available for that cohort.

    Phase 2: replace with historical-deals-mcp.get_benchmark().
    """
    return _bd.get_benchmark(vintage, region, asset_class)


def list_vintages(region: str = "US") -> List[int]:
    """List available vintages for a region."""
    return _bd.list_vintages(region)


def list_regions() -> List[str]:
    """List all regions in the dataset."""
    return _bd.list_regions()


def get_all_benchmarks(region: Optional[str] = None) -> List[Dict[str, Any]]:
    """Return all benchmark records, optionally filtered by region."""
    return _bd.get_all_benchmarks(region)


def percentile_rank(value: float, metric_bands: Dict[str, float]) -> str:
    """Classify a metric value against p25/p50/p75 bands."""
    return _bd.percentile_rank(value, metric_bands)


def is_mock_mode() -> bool:
    return _MOCK_MODE
