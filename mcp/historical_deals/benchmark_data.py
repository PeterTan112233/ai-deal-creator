"""
mcp/historical_deals/benchmark_data.py

Demo CLO market benchmark dataset.

IMPORTANT — READ BEFORE USING
  All data in this module is illustrative and representative of broad
  historical CLO market trends. It is NOT sourced from official deal
  databases, rating agency data, or Bloomberg. Do not use for investment
  decisions, pricing, ratings analysis, or distribution.

  Data tagged _source: "DEMO_BENCHMARK_DATA".

METHODOLOGY
  Benchmarks represent approximate market medians and percentiles for
  broadly syndicated loan (BSL) CLOs by vintage year and region.
  Percentile bands (p25, p50, p75) are derived from illustrative
  distributions. Phase 2 replacement: connect to historical-deals-mcp.

COVERAGE
  Vintages: 2020 – 2025
  Regions:  US (broadly syndicated loans), EU (broadly syndicated loans)
  Metrics:  equity_irr, aaa_size_pct, oc_cushion_aaa, ic_cushion_aaa,
            was, wac, equity_wal, aaa_spread_bps
"""

from typing import Any, Dict, List, Optional

_SOURCE_TAG = "DEMO_BENCHMARK_DATA"

# ---------------------------------------------------------------------------
# Benchmark dataset
# Each entry covers one (vintage, region) cohort.
# p25/p50/p75 = 25th / 50th / 75th percentile across deals in that cohort.
# ---------------------------------------------------------------------------

_BENCHMARKS: List[Dict[str, Any]] = [
    # ── US BSL CLO ──────────────────────────────────────────────────────────
    {
        "vintage": 2020, "region": "US", "asset_class": "broadly_syndicated_loans",
        "deal_count": 87,
        "metrics": {
            "equity_irr":      {"p25": 0.065, "p50": 0.095, "p75": 0.130},
            "aaa_size_pct":    {"p25": 0.610, "p50": 0.630, "p75": 0.645},
            "oc_cushion_aaa":  {"p25": 0.165, "p50": 0.195, "p75": 0.225},
            "ic_cushion_aaa":  {"p25": 0.750, "p50": 0.920, "p75": 1.100},
            "was":             {"p25": 0.035, "p50": 0.038, "p75": 0.042},
            "wac":             {"p25": 0.038, "p50": 0.042, "p75": 0.047},
            "equity_wal":      {"p25": 4.0,   "p50": 4.8,   "p75": 5.5},
            "aaa_spread_bps":  {"p25": 115,   "p50": 130,   "p75": 155},
        },
        "_source": _SOURCE_TAG,
    },
    {
        "vintage": 2021, "region": "US", "asset_class": "broadly_syndicated_loans",
        "deal_count": 142,
        "metrics": {
            "equity_irr":      {"p25": 0.090, "p50": 0.125, "p75": 0.165},
            "aaa_size_pct":    {"p25": 0.615, "p50": 0.635, "p75": 0.650},
            "oc_cushion_aaa":  {"p25": 0.170, "p50": 0.200, "p75": 0.230},
            "ic_cushion_aaa":  {"p25": 0.950, "p50": 1.100, "p75": 1.350},
            "was":             {"p25": 0.036, "p50": 0.040, "p75": 0.044},
            "wac":             {"p25": 0.040, "p50": 0.044, "p75": 0.049},
            "equity_wal":      {"p25": 4.2,   "p50": 5.0,   "p75": 5.8},
            "aaa_spread_bps":  {"p25": 105,   "p50": 118,   "p75": 135},
        },
        "_source": _SOURCE_TAG,
    },
    {
        "vintage": 2022, "region": "US", "asset_class": "broadly_syndicated_loans",
        "deal_count": 98,
        "metrics": {
            "equity_irr":      {"p25": 0.070, "p50": 0.100, "p75": 0.135},
            "aaa_size_pct":    {"p25": 0.605, "p50": 0.625, "p75": 0.640},
            "oc_cushion_aaa":  {"p25": 0.158, "p50": 0.188, "p75": 0.215},
            "ic_cushion_aaa":  {"p25": 0.480, "p50": 0.620, "p75": 0.790},
            "was":             {"p25": 0.038, "p50": 0.042, "p75": 0.047},
            "wac":             {"p25": 0.082, "p50": 0.090, "p75": 0.098},
            "equity_wal":      {"p25": 4.0,   "p50": 4.7,   "p75": 5.4},
            "aaa_spread_bps":  {"p25": 140,   "p50": 160,   "p75": 185},
        },
        "_source": _SOURCE_TAG,
    },
    {
        "vintage": 2023, "region": "US", "asset_class": "broadly_syndicated_loans",
        "deal_count": 115,
        "metrics": {
            "equity_irr":      {"p25": 0.080, "p50": 0.115, "p75": 0.155},
            "aaa_size_pct":    {"p25": 0.608, "p50": 0.628, "p75": 0.645},
            "oc_cushion_aaa":  {"p25": 0.162, "p50": 0.192, "p75": 0.220},
            "ic_cushion_aaa":  {"p25": 0.520, "p50": 0.680, "p75": 0.850},
            "was":             {"p25": 0.038, "p50": 0.042, "p75": 0.046},
            "wac":             {"p25": 0.090, "p50": 0.096, "p75": 0.103},
            "equity_wal":      {"p25": 4.1,   "p50": 4.9,   "p75": 5.5},
            "aaa_spread_bps":  {"p25": 130,   "p50": 148,   "p75": 168},
        },
        "_source": _SOURCE_TAG,
    },
    {
        "vintage": 2024, "region": "US", "asset_class": "broadly_syndicated_loans",
        "deal_count": 128,
        "metrics": {
            "equity_irr":      {"p25": 0.088, "p50": 0.120, "p75": 0.158},
            "aaa_size_pct":    {"p25": 0.610, "p50": 0.630, "p75": 0.648},
            "oc_cushion_aaa":  {"p25": 0.165, "p50": 0.195, "p75": 0.225},
            "ic_cushion_aaa":  {"p25": 0.540, "p50": 0.700, "p75": 0.880},
            "was":             {"p25": 0.038, "p50": 0.042, "p75": 0.046},
            "wac":             {"p25": 0.088, "p50": 0.094, "p75": 0.101},
            "equity_wal":      {"p25": 4.2,   "p50": 5.0,   "p75": 5.6},
            "aaa_spread_bps":  {"p25": 120,   "p50": 138,   "p75": 158},
        },
        "_source": _SOURCE_TAG,
    },
    {
        "vintage": 2025, "region": "US", "asset_class": "broadly_syndicated_loans",
        "deal_count": 54,   # partial year
        "metrics": {
            "equity_irr":      {"p25": 0.090, "p50": 0.122, "p75": 0.160},
            "aaa_size_pct":    {"p25": 0.612, "p50": 0.632, "p75": 0.650},
            "oc_cushion_aaa":  {"p25": 0.168, "p50": 0.198, "p75": 0.228},
            "ic_cushion_aaa":  {"p25": 0.560, "p50": 0.720, "p75": 0.900},
            "was":             {"p25": 0.038, "p50": 0.042, "p75": 0.046},
            "wac":             {"p25": 0.086, "p50": 0.092, "p75": 0.099},
            "equity_wal":      {"p25": 4.2,   "p50": 5.0,   "p75": 5.6},
            "aaa_spread_bps":  {"p25": 118,   "p50": 135,   "p75": 155},
        },
        "_source": _SOURCE_TAG,
    },
    # ── EU BSL CLO ──────────────────────────────────────────────────────────
    {
        "vintage": 2022, "region": "EU", "asset_class": "broadly_syndicated_loans",
        "deal_count": 42,
        "metrics": {
            "equity_irr":      {"p25": 0.065, "p50": 0.095, "p75": 0.128},
            "aaa_size_pct":    {"p25": 0.620, "p50": 0.640, "p75": 0.658},
            "oc_cushion_aaa":  {"p25": 0.155, "p50": 0.182, "p75": 0.210},
            "ic_cushion_aaa":  {"p25": 0.420, "p50": 0.560, "p75": 0.720},
            "was":             {"p25": 0.036, "p50": 0.040, "p75": 0.044},
            "wac":             {"p25": 0.078, "p50": 0.086, "p75": 0.094},
            "equity_wal":      {"p25": 4.0,   "p50": 4.6,   "p75": 5.2},
            "aaa_spread_bps":  {"p25": 145,   "p50": 165,   "p75": 190},
        },
        "_source": _SOURCE_TAG,
    },
    {
        "vintage": 2023, "region": "EU", "asset_class": "broadly_syndicated_loans",
        "deal_count": 58,
        "metrics": {
            "equity_irr":      {"p25": 0.075, "p50": 0.108, "p75": 0.145},
            "aaa_size_pct":    {"p25": 0.618, "p50": 0.638, "p75": 0.655},
            "oc_cushion_aaa":  {"p25": 0.158, "p50": 0.185, "p75": 0.215},
            "ic_cushion_aaa":  {"p25": 0.460, "p50": 0.600, "p75": 0.760},
            "was":             {"p25": 0.037, "p50": 0.041, "p75": 0.045},
            "wac":             {"p25": 0.082, "p50": 0.090, "p75": 0.098},
            "equity_wal":      {"p25": 4.0,   "p50": 4.7,   "p75": 5.3},
            "aaa_spread_bps":  {"p25": 132,   "p50": 150,   "p75": 172},
        },
        "_source": _SOURCE_TAG,
    },
    {
        "vintage": 2024, "region": "EU", "asset_class": "broadly_syndicated_loans",
        "deal_count": 62,
        "metrics": {
            "equity_irr":      {"p25": 0.080, "p50": 0.112, "p75": 0.150},
            "aaa_size_pct":    {"p25": 0.618, "p50": 0.638, "p75": 0.655},
            "oc_cushion_aaa":  {"p25": 0.160, "p50": 0.188, "p75": 0.218},
            "ic_cushion_aaa":  {"p25": 0.480, "p50": 0.620, "p75": 0.780},
            "was":             {"p25": 0.037, "p50": 0.041, "p75": 0.045},
            "wac":             {"p25": 0.080, "p50": 0.088, "p75": 0.096},
            "equity_wal":      {"p25": 4.1,   "p50": 4.8,   "p75": 5.4},
            "aaa_spread_bps":  {"p25": 122,   "p50": 140,   "p75": 162},
        },
        "_source": _SOURCE_TAG,
    },
]


# ---------------------------------------------------------------------------
# Public query interface
# ---------------------------------------------------------------------------

def get_benchmark(
    vintage: int,
    region: str = "US",
    asset_class: str = "broadly_syndicated_loans",
) -> Optional[Dict[str, Any]]:
    """
    Retrieve the benchmark entry for a given vintage + region + asset class.
    Returns None if no data is available for that cohort.
    """
    region = region.upper()
    for b in _BENCHMARKS:
        if (b["vintage"] == vintage
                and b["region"].upper() == region
                and b["asset_class"] == asset_class):
            return b
    return None


def list_vintages(region: str = "US") -> List[int]:
    """List vintages available for a given region, sorted ascending."""
    region = region.upper()
    return sorted({b["vintage"] for b in _BENCHMARKS if b["region"].upper() == region})


def list_regions() -> List[str]:
    """List all regions in the dataset."""
    return sorted({b["region"] for b in _BENCHMARKS})


def get_all_benchmarks(region: Optional[str] = None) -> List[Dict[str, Any]]:
    """Return all benchmark records, optionally filtered by region."""
    if region is None:
        return list(_BENCHMARKS)
    region = region.upper()
    return [b for b in _BENCHMARKS if b["region"].upper() == region]


def percentile_rank(value: float, metric_bands: Dict[str, float]) -> str:
    """
    Given a metric value and {p25, p50, p75} bands, return a percentile
    label: "below p25" | "p25–p50" | "p50–p75" | "above p75".
    """
    p25 = metric_bands.get("p25", 0)
    p50 = metric_bands.get("p50", 0)
    p75 = metric_bands.get("p75", 0)
    if value < p25:
        return "below p25"
    if value < p50:
        return "p25–p50"
    if value < p75:
        return "p50–p75"
    return "above p75"
