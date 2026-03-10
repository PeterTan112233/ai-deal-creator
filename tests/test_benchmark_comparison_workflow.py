"""
tests/test_benchmark_comparison_workflow.py

Tests for:
  - mcp/historical_deals/benchmark_data.py
  - app/services/benchmarks_service.py
  - app/workflows/benchmark_comparison_workflow.py
"""

import json
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp.historical_deals.benchmark_data import (
    get_benchmark, list_vintages, list_regions, get_all_benchmarks, percentile_rank,
)
from app.services import benchmarks_service
from app.workflows.benchmark_comparison_workflow import (
    benchmark_comparison_workflow, _infer_vintage,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _load_sample_deal(label_substring: str) -> dict:
    with open("data/samples/sample_deal_inputs.json") as f:
        data = json.load(f)
    for deal in data["deals"]:
        if label_substring in deal.get("_label", ""):
            return deal
    raise KeyError(f"No sample deal matching '{label_substring}'")


@pytest.fixture
def valid_deal():
    return _load_sample_deal("US BSL")


@pytest.fixture
def base_outputs():
    """Realistic base-case outputs for a healthy US BSL CLO."""
    return {
        "equity_irr":     0.115,
        "aaa_size_pct":   0.630,
        "oc_cushion_aaa": 0.195,
        "ic_cushion_aaa": 0.700,
        "was":            0.042,
        "wac":            0.095,
        "equity_wal":     5.0,
        "scenario_npv":   -2_000_000,
    }


@pytest.fixture
def comparison_result(valid_deal, base_outputs):
    return benchmark_comparison_workflow(
        deal_input=valid_deal,
        scenario_outputs=base_outputs,
        vintage=2024,
        region="US",
    )


# ---------------------------------------------------------------------------
# benchmark_data module
# ---------------------------------------------------------------------------

class TestBenchmarkData:

    def test_get_benchmark_us_2024(self):
        b = get_benchmark(2024, "US")
        assert b is not None
        assert b["vintage"] == 2024
        assert b["region"] == "US"

    def test_get_benchmark_eu_2024(self):
        b = get_benchmark(2024, "EU")
        assert b is not None
        assert b["region"] == "EU"

    def test_get_benchmark_missing_returns_none(self):
        assert get_benchmark(1999, "US") is None

    def test_list_vintages_us(self):
        vintages = list_vintages("US")
        assert isinstance(vintages, list)
        assert len(vintages) >= 5
        assert 2024 in vintages

    def test_list_vintages_sorted(self):
        vintages = list_vintages("US")
        assert vintages == sorted(vintages)

    def test_list_regions(self):
        regions = list_regions()
        assert "US" in regions
        assert "EU" in regions

    def test_get_all_benchmarks_all(self):
        all_b = get_all_benchmarks()
        assert len(all_b) >= 8

    def test_get_all_benchmarks_filtered_us(self):
        us = get_all_benchmarks("US")
        assert all(b["region"] == "US" for b in us)

    def test_benchmark_has_required_metric_keys(self):
        b = get_benchmark(2024, "US")
        for metric in ("equity_irr", "aaa_size_pct", "oc_cushion_aaa", "wac"):
            assert metric in b["metrics"]
            assert "p25" in b["metrics"][metric]
            assert "p50" in b["metrics"][metric]
            assert "p75" in b["metrics"][metric]

    def test_percentile_rank_above_p75(self):
        bands = {"p25": 0.08, "p50": 0.12, "p75": 0.16}
        assert percentile_rank(0.20, bands) == "above p75"

    def test_percentile_rank_between_p25_p50(self):
        bands = {"p25": 0.08, "p50": 0.12, "p75": 0.16}
        assert percentile_rank(0.10, bands) == "p25–p50"

    def test_percentile_rank_below_p25(self):
        bands = {"p25": 0.08, "p50": 0.12, "p75": 0.16}
        assert percentile_rank(0.05, bands) == "below p25"

    def test_source_tag_present(self):
        b = get_benchmark(2024, "US")
        assert b["_source"] == "DEMO_BENCHMARK_DATA"


# ---------------------------------------------------------------------------
# benchmarks_service
# ---------------------------------------------------------------------------

class TestBenchmarksService:

    def test_get_benchmark_delegates(self):
        result = benchmarks_service.get_benchmark(2024, "US")
        assert result is not None

    def test_list_vintages_delegates(self):
        assert 2024 in benchmarks_service.list_vintages("US")

    def test_is_mock_mode_true(self):
        assert benchmarks_service.is_mock_mode() is True


# ---------------------------------------------------------------------------
# benchmark_comparison_workflow — return structure
# ---------------------------------------------------------------------------

class TestReturnStructure:

    EXPECTED_KEYS = {
        "deal_id", "comparison_id", "compared_at", "vintage", "region",
        "benchmark_cohort", "metric_scores", "above_median_count",
        "below_median_count", "overall_position", "overall_label",
        "comparison_report", "is_mock", "audit_events",
    }

    def test_returns_dict(self, comparison_result):
        assert isinstance(comparison_result, dict)

    def test_all_expected_keys_present(self, comparison_result):
        assert self.EXPECTED_KEYS <= set(comparison_result.keys())

    def test_comparison_id_starts_with_prefix(self, comparison_result):
        assert comparison_result["comparison_id"].startswith("bench-")

    def test_vintage_echoed(self, comparison_result):
        assert comparison_result["vintage"] == 2024

    def test_region_echoed(self, comparison_result):
        assert comparison_result["region"] == "US"

    def test_is_mock_true(self, comparison_result):
        assert comparison_result["is_mock"] is True

    def test_no_error_on_valid_cohort(self, comparison_result):
        assert "error" not in comparison_result


# ---------------------------------------------------------------------------
# Metric scores
# ---------------------------------------------------------------------------

class TestMetricScores:

    def test_metric_scores_is_list(self, comparison_result):
        assert isinstance(comparison_result["metric_scores"], list)

    def test_metric_scores_non_empty(self, comparison_result):
        assert len(comparison_result["metric_scores"]) > 0

    def test_each_score_has_required_keys(self, comparison_result):
        for s in comparison_result["metric_scores"]:
            assert "metric" in s
            assert "label" in s
            assert "deal_value" in s
            assert "vs_median" in s
            assert "percentile_rank" in s

    def test_equity_irr_scored(self, comparison_result):
        scored_keys = {s["metric"] for s in comparison_result["metric_scores"]}
        assert "equity_irr" in scored_keys

    def test_above_at_below_median_are_valid_values(self, comparison_result):
        valid = {"above", "below", "at", "n/a"}
        for s in comparison_result["metric_scores"]:
            assert s["vs_median"] in valid, f"Unexpected vs_median: {s['vs_median']}"


# ---------------------------------------------------------------------------
# Overall position
# ---------------------------------------------------------------------------

class TestOverallPosition:

    def test_overall_position_is_valid(self, comparison_result):
        assert comparison_result["overall_position"] in ("strong", "median", "weak", "mixed")

    def test_overall_label_is_non_empty_string(self, comparison_result):
        assert isinstance(comparison_result["overall_label"], str)
        assert len(comparison_result["overall_label"]) > 0

    def test_strong_deal_above_median(self, valid_deal):
        """Deal well above market median → should be 'strong'."""
        strong_outputs = {
            "equity_irr":     0.20,   # well above p75
            "aaa_size_pct":   0.60,
            "oc_cushion_aaa": 0.30,   # well above p75
            "ic_cushion_aaa": 1.50,   # well above p75
            "was":            0.050,
            "wac":            0.110,
            "equity_wal":     5.0,
        }
        result = benchmark_comparison_workflow(valid_deal, strong_outputs, vintage=2024, region="US")
        assert result["overall_position"] == "strong"

    def test_weak_deal_below_median(self, valid_deal):
        """Deal well below market median → should be 'weak'."""
        weak_outputs = {
            "equity_irr":     0.02,   # below p25
            "aaa_size_pct":   0.70,
            "oc_cushion_aaa": 0.10,   # below p25
            "ic_cushion_aaa": 0.20,   # well below p25
            "was":            0.025,
            "wac":            0.060,
            "equity_wal":     3.0,
        }
        result = benchmark_comparison_workflow(valid_deal, weak_outputs, vintage=2024, region="US")
        assert result["overall_position"] == "weak"


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

class TestErrorHandling:

    def test_unknown_vintage_returns_error(self, valid_deal, base_outputs):
        result = benchmark_comparison_workflow(
            valid_deal, base_outputs, vintage=1990, region="US"
        )
        assert "error" in result
        assert result["metric_scores"] == []

    def test_unknown_region_returns_error(self, valid_deal, base_outputs):
        result = benchmark_comparison_workflow(
            valid_deal, base_outputs, vintage=2024, region="JP"
        )
        assert "error" in result

    def test_vintage_inferred_from_close_date(self, base_outputs):
        deal = {
            "deal_id": "d1", "name": "Test", "issuer": "X",
            "close_date": "2023-06-15",
            "region": "US",
        }
        year = _infer_vintage(deal)
        assert year == 2023

    def test_vintage_defaults_when_no_close_date(self):
        deal = {"deal_id": "d1"}
        year = _infer_vintage(deal)
        assert isinstance(year, int)
        assert year >= 2024


# ---------------------------------------------------------------------------
# Comparison report
# ---------------------------------------------------------------------------

class TestComparisonReport:

    def test_report_is_non_empty_string(self, comparison_result):
        assert isinstance(comparison_result["comparison_report"], str)
        assert len(comparison_result["comparison_report"]) > 100

    def test_report_tagged_demo(self, comparison_result):
        assert "[demo]" in comparison_result["comparison_report"].lower() or \
               "DEMO" in comparison_result["comparison_report"]

    def test_report_contains_benchmark_section(self, comparison_result):
        assert "BENCHMARK" in comparison_result["comparison_report"]

    def test_report_contains_metric_table(self, comparison_result):
        assert "Equity IRR" in comparison_result["comparison_report"]

    def test_report_contains_deal_id(self, valid_deal, comparison_result):
        assert valid_deal["deal_id"] in comparison_result["comparison_report"]

    def test_report_shows_overall_position(self, comparison_result):
        pos = comparison_result["overall_position"].upper()
        assert pos in comparison_result["comparison_report"]

    def test_report_has_disclaimer(self, comparison_result):
        assert "DEMO_BENCHMARK_DATA" in comparison_result["comparison_report"]


# ---------------------------------------------------------------------------
# Audit events
# ---------------------------------------------------------------------------

class TestAuditEvents:

    def test_audit_events_emitted(self, comparison_result):
        assert len(comparison_result["audit_events"]) >= 1

    def test_audit_events_are_strings(self, comparison_result):
        for ev in comparison_result["audit_events"]:
            assert isinstance(ev, str)
