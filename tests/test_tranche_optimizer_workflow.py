"""
tests/test_tranche_optimizer_workflow.py

Tests for app/workflows/tranche_optimizer_workflow.py

Covers:
  - Return structure and all expected keys
  - Optimal point is feasible (OC and IC >= floor)
  - Higher OC floor narrows feasible set
  - Feasibility table has one row per candidate
  - All rows have required keys
  - Frontier contains only feasible rows
  - Optimal has highest IRR among feasible rows
  - Tighter step produces more candidates
  - Invalid deal returns error
  - No feasible structure sets infeasible_reason
  - Audit events emitted
  - Unit tests for helpers
"""

import json
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.workflows.tranche_optimizer_workflow import (
    tranche_optimizer_workflow,
    _aaa_candidates,
    _diagnose_infeasibility,
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
def opt_result(valid_deal):
    """Run optimizer with coarse step for speed."""
    return tranche_optimizer_workflow(
        valid_deal, aaa_min=0.58, aaa_max=0.68, aaa_step=0.02
    )


# ---------------------------------------------------------------------------
# Return structure
# ---------------------------------------------------------------------------

class TestReturnStructure:

    EXPECTED_KEYS = {
        "deal_id", "optimization_id", "optimised_at", "is_mock",
        "optimal", "feasibility_table", "frontier", "constraints",
        "infeasible_reason", "audit_events",
    }

    def test_returns_dict(self, opt_result):
        assert isinstance(opt_result, dict)

    def test_all_expected_keys_present(self, opt_result):
        assert self.EXPECTED_KEYS <= set(opt_result.keys())

    def test_optimization_id_starts_with_prefix(self, opt_result):
        assert opt_result["optimization_id"].startswith("opt-")

    def test_is_mock_true(self, opt_result):
        assert opt_result["is_mock"] is True

    def test_no_error_on_valid_deal(self, opt_result):
        assert "error" not in opt_result

    def test_deal_id_matches(self, valid_deal, opt_result):
        assert opt_result["deal_id"] == valid_deal["deal_id"]


# ---------------------------------------------------------------------------
# Feasibility table
# ---------------------------------------------------------------------------

class TestFeasibilityTable:

    def test_table_is_list(self, opt_result):
        assert isinstance(opt_result["feasibility_table"], list)

    def test_table_has_correct_row_count(self, valid_deal):
        # aaa_min=0.58, aaa_max=0.68, step=0.02 → 0.58, 0.60, 0.62, 0.64, 0.66, 0.68 = 6 rows
        result = tranche_optimizer_workflow(
            valid_deal, aaa_min=0.58, aaa_max=0.68, aaa_step=0.02
        )
        assert len(result["feasibility_table"]) == 6

    def test_each_row_has_required_keys(self, opt_result):
        required = {"aaa_size_pct", "equity_size_pct", "equity_irr",
                    "oc_cushion_aaa", "ic_cushion_aaa", "feasible", "status"}
        for row in opt_result["feasibility_table"]:
            assert required <= set(row.keys()), f"Missing keys in row: {row}"

    def test_aaa_sizes_in_ascending_order(self, opt_result):
        sizes = [r["aaa_size_pct"] for r in opt_result["feasibility_table"]]
        assert sizes == sorted(sizes)

    def test_aaa_sizes_within_bounds(self, opt_result):
        constraints = opt_result["constraints"]
        for row in opt_result["feasibility_table"]:
            assert constraints["aaa_min"] - 0.001 <= row["aaa_size_pct"] <= constraints["aaa_max"] + 0.001

    def test_equity_plus_aaa_plus_mez_near_one(self, opt_result):
        for row in opt_result["feasibility_table"]:
            total = row["aaa_size_pct"] + row["mez_size_pct"] + row["equity_size_pct"]
            assert abs(total - 1.0) < 0.01, f"Tranche sizes don't sum to 1: {total}"

    def test_all_rows_complete(self, opt_result):
        for row in opt_result["feasibility_table"]:
            assert row["status"] == "complete"


# ---------------------------------------------------------------------------
# Optimal point
# ---------------------------------------------------------------------------

class TestOptimalPoint:

    def test_optimal_is_not_none(self, opt_result):
        assert opt_result["optimal"] is not None, \
            f"Expected a feasible optimal point. infeasible_reason: {opt_result.get('infeasible_reason')}"

    def test_optimal_is_feasible(self, opt_result):
        assert opt_result["optimal"]["feasible"] is True

    def test_optimal_satisfies_oc_floor(self, opt_result):
        oc_floor = opt_result["constraints"]["oc_floor"]
        assert opt_result["optimal"]["oc_cushion_aaa"] >= oc_floor

    def test_optimal_satisfies_ic_floor(self, opt_result):
        ic_floor = opt_result["constraints"]["ic_floor"]
        assert opt_result["optimal"]["ic_cushion_aaa"] >= ic_floor

    def test_optimal_has_highest_irr_among_feasible(self, opt_result):
        optimal_irr = opt_result["optimal"]["equity_irr"]
        for row in opt_result["feasibility_table"]:
            if row["feasible"]:
                assert row["equity_irr"] <= optimal_irr + 1e-6, \
                    f"Found feasible row with higher IRR than optimal: {row['equity_irr']:.2%} > {optimal_irr:.2%}"

    def test_optimal_has_run_id(self, opt_result):
        assert opt_result["optimal"]["run_id"] is not None
        assert opt_result["optimal"]["run_id"].startswith("run-")


# ---------------------------------------------------------------------------
# Frontier
# ---------------------------------------------------------------------------

class TestFrontier:

    def test_frontier_is_list(self, opt_result):
        assert isinstance(opt_result["frontier"], list)

    def test_frontier_only_contains_feasible_rows(self, opt_result):
        feasible_aaa = {r["aaa_size_pct"] for r in opt_result["feasibility_table"] if r["feasible"]}
        for f in opt_result["frontier"]:
            assert f["aaa_size_pct"] in feasible_aaa

    def test_frontier_has_irr_and_aaa_size(self, opt_result):
        for f in opt_result["frontier"]:
            assert "aaa_size_pct" in f
            assert "equity_irr" in f

    def test_frontier_length_matches_feasible_count(self, opt_result):
        feasible_count = sum(1 for r in opt_result["feasibility_table"] if r["feasible"])
        assert len(opt_result["frontier"]) == feasible_count


# ---------------------------------------------------------------------------
# Economic properties
# ---------------------------------------------------------------------------

class TestEconomicProperties:

    def test_irr_varies_across_aaa_range(self, valid_deal):
        """IRR should change across the sweep — not constant."""
        result = tranche_optimizer_workflow(
            valid_deal, aaa_min=0.58, aaa_max=0.70, aaa_step=0.03
        )
        irrs = [r["equity_irr"] for r in result["feasibility_table"]
                if r["status"] == "complete" and r["equity_irr"] is not None]
        # IRR should not be identical at all AAA sizes
        assert max(irrs) != min(irrs), "IRR should vary across the AAA size sweep"

    def test_tighter_oc_floor_reduces_feasible_set(self, valid_deal):
        loose  = tranche_optimizer_workflow(valid_deal, aaa_min=0.58, aaa_max=0.68,
                                            aaa_step=0.02, oc_floor=0.10)
        tight  = tranche_optimizer_workflow(valid_deal, aaa_min=0.58, aaa_max=0.68,
                                            aaa_step=0.02, oc_floor=0.35)
        loose_feasible = sum(1 for r in loose["feasibility_table"] if r["feasible"])
        tight_feasible = sum(1 for r in tight["feasibility_table"] if r["feasible"])
        assert tight_feasible <= loose_feasible

    def test_stress_scenario_lowers_optimal_irr(self, valid_deal):
        base   = tranche_optimizer_workflow(
            valid_deal, aaa_min=0.60, aaa_max=0.65, aaa_step=0.025,
            scenario_parameters={"default_rate": 0.03, "recovery_rate": 0.65, "spread_shock_bps": 0},
        )
        stress = tranche_optimizer_workflow(
            valid_deal, aaa_min=0.60, aaa_max=0.65, aaa_step=0.025,
            scenario_parameters={"default_rate": 0.07, "recovery_rate": 0.45, "spread_shock_bps": 75},
        )
        if base["optimal"] and stress["optimal"]:
            assert stress["optimal"]["equity_irr"] < base["optimal"]["equity_irr"]


# ---------------------------------------------------------------------------
# Guard conditions
# ---------------------------------------------------------------------------

class TestGuardConditions:

    def test_invalid_deal_returns_error(self):
        bad_deal = {"deal_id": "", "name": "x", "issuer": "y",
                    "collateral": {"portfolio_size": 100_000_000, "diversity_score": 45, "ccc_bucket": 0.05},
                    "liabilities": [{"tranche_id": "t1", "name": "AAA", "seniority": 1, "size_pct": 0.61}]}
        result = tranche_optimizer_workflow(bad_deal)
        assert "error" in result
        assert result["optimal"] is None

    def test_infeasible_reason_set_when_no_feasible_point(self, valid_deal):
        """Impossibly tight OC floor → no feasible structure."""
        result = tranche_optimizer_workflow(
            valid_deal, aaa_min=0.58, aaa_max=0.68, aaa_step=0.02,
            oc_floor=5.0,  # 500% OC cushion — impossible
        )
        assert result["optimal"] is None
        assert result["infeasible_reason"] is not None
        assert len(result["infeasible_reason"]) > 0

    def test_constraints_recorded_in_result(self, opt_result):
        c = opt_result["constraints"]
        assert "oc_floor" in c
        assert "ic_floor" in c
        assert "aaa_min" in c
        assert "aaa_max" in c


# ---------------------------------------------------------------------------
# Audit events
# ---------------------------------------------------------------------------

class TestAuditEvents:

    def test_audit_events_emitted(self, opt_result):
        assert len(opt_result["audit_events"]) >= 2  # validated + optimization.completed

    def test_audit_events_are_strings(self, opt_result):
        for ev in opt_result["audit_events"]:
            assert isinstance(ev, str)


# ---------------------------------------------------------------------------
# Unit tests for helpers
# ---------------------------------------------------------------------------

class TestAaaCandidates:

    def test_correct_count(self):
        c = _aaa_candidates(0.58, 0.68, 0.02)
        assert len(c) == 6

    def test_starts_at_min(self):
        c = _aaa_candidates(0.60, 0.70, 0.05)
        assert abs(c[0] - 0.60) < 1e-9

    def test_ends_at_max(self):
        c = _aaa_candidates(0.60, 0.70, 0.05)
        assert abs(c[-1] - 0.70) < 1e-9

    def test_empty_when_min_greater_than_max(self):
        assert _aaa_candidates(0.70, 0.60, 0.02) == []

    def test_single_value_when_min_equals_max(self):
        c = _aaa_candidates(0.65, 0.65, 0.02)
        assert len(c) == 1
        assert abs(c[0] - 0.65) < 1e-9


class TestDiagnoseInfeasibility:

    def test_oc_failure_identified(self):
        table = [
            {"status": "complete", "oc_pass": False, "ic_pass": True,
             "oc_cushion_aaa": 0.05, "ic_cushion_aaa": 0.20},
            {"status": "complete", "oc_pass": False, "ic_pass": True,
             "oc_cushion_aaa": 0.08, "ic_cushion_aaa": 0.20},
        ]
        msg = _diagnose_infeasibility(table, oc_floor=0.18, ic_floor=0.10)
        assert "OC" in msg

    def test_all_failed_message(self):
        table = [
            {"status": "failed", "oc_pass": False, "ic_pass": False,
             "oc_cushion_aaa": None, "ic_cushion_aaa": None},
        ]
        msg = _diagnose_infeasibility(table, oc_floor=0.18, ic_floor=0.10)
        assert "failed" in msg.lower() or "no feasibility" in msg.lower()
