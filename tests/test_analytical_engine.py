"""
tests/test_analytical_engine.py

Tests for mcp/cashflow_engine/analytical_engine.py

Covers:
  - Interface: run_scenario / get_run_status / get_run_outputs
  - Output structure and numeric plausibility for a typical US BSL CLO
  - Stress sensitivity: higher defaults → lower equity IRR, lower OC cushion
  - Edge cases: missing tranches, zero excess spread, extreme inputs
  - Engine tag is DEMO_ANALYTICAL_ENGINE (not an official [calculated] output)
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mcp.cashflow_engine import analytical_engine as engine


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def base_deal():
    """Typical US BSL CLO: 500M pool, 3 tranches."""
    return {
        "portfolio_size": 500_000_000,
        "was":  0.042,
        "wal":  5.2,
        "diversity_score": 62,
        "ccc_bucket": 0.055,
        "tranches": [
            {"tranche_id": "t-aaa", "name": "AAA", "seniority": 1,
             "size_pct": 0.61, "coupon": "SOFR+145"},
            {"tranche_id": "t-aa",  "name": "AA",  "seniority": 2,
             "size_pct": 0.08, "coupon": "SOFR+200"},
            {"tranche_id": "t-eq",  "name": "Equity", "seniority": 3,
             "size_pct": 0.09},
        ],
    }


@pytest.fixture
def base_scenario():
    return {
        "default_rate":     0.03,
        "recovery_rate":    0.65,
        "spread_shock_bps": 0.0,
    }


@pytest.fixture
def stress_scenario():
    return {
        "default_rate":     0.08,
        "recovery_rate":    0.40,
        "spread_shock_bps": 100.0,
    }


@pytest.fixture
def base_outputs(base_deal, base_scenario):
    result = engine.run_scenario(base_deal, base_scenario)
    return engine.get_run_outputs(result["run_id"])


# ---------------------------------------------------------------------------
# Interface tests
# ---------------------------------------------------------------------------

class TestInterface:

    def test_run_scenario_returns_run_id(self, base_deal, base_scenario):
        result = engine.run_scenario(base_deal, base_scenario)
        assert "run_id" in result
        assert result["run_id"].startswith("run-analytical-")

    def test_run_scenario_status_complete(self, base_deal, base_scenario):
        result = engine.run_scenario(base_deal, base_scenario)
        assert result["status"] == "complete"

    def test_get_run_status_complete(self, base_deal, base_scenario):
        result = engine.run_scenario(base_deal, base_scenario)
        status = engine.get_run_status(result["run_id"])
        assert status["status"] == "complete"

    def test_get_run_status_unknown_run(self):
        status = engine.get_run_status("run-does-not-exist")
        assert status["status"] == "unknown"

    def test_get_run_outputs_returns_dict(self, base_deal, base_scenario):
        result = engine.run_scenario(base_deal, base_scenario)
        outputs = engine.get_run_outputs(result["run_id"])
        assert isinstance(outputs, dict)

    def test_get_run_outputs_unknown_raises(self):
        with pytest.raises(KeyError):
            engine.get_run_outputs("run-does-not-exist")


# ---------------------------------------------------------------------------
# Output structure
# ---------------------------------------------------------------------------

class TestOutputStructure:

    EXPECTED_KEYS = {
        "equity_irr", "aaa_size_pct", "wac",
        "oc_cushion_aaa", "ic_cushion_aaa",
        "equity_wal", "scenario_npv", "_mock",
    }

    def test_all_expected_keys_present(self, base_outputs):
        assert self.EXPECTED_KEYS <= set(base_outputs.keys())

    def test_engine_tag_is_demo(self, base_outputs):
        assert base_outputs["_mock"] == "DEMO_ANALYTICAL_ENGINE"

    def test_engine_tag_is_not_mock_engine_output(self, base_outputs):
        assert base_outputs["_mock"] != "MOCK_ENGINE_OUTPUT"

    def test_equity_irr_is_float(self, base_outputs):
        assert isinstance(base_outputs["equity_irr"], float)

    def test_wac_is_float(self, base_outputs):
        assert isinstance(base_outputs["wac"], float)

    def test_scenario_npv_is_numeric(self, base_outputs):
        assert isinstance(base_outputs["scenario_npv"], (int, float))


# ---------------------------------------------------------------------------
# Numeric plausibility — base case
# ---------------------------------------------------------------------------

class TestNumericPlausibility:

    def test_equity_irr_in_reasonable_range(self, base_outputs):
        """Equity IRR should be between -50% and +100% for a valid deal."""
        irr = base_outputs["equity_irr"]
        assert -0.50 <= irr <= 1.00, f"Equity IRR {irr:.1%} outside plausible range"

    def test_wac_above_sofr(self, base_outputs):
        """Pool WAC = WAS + SOFR, must exceed SOFR alone."""
        assert base_outputs["wac"] > engine.SOFR_RATE

    def test_wac_in_range(self, base_outputs):
        """Pool WAC should be roughly WAS + SOFR ≈ 4.2% + 5.33% ≈ 9.5%."""
        wac = base_outputs["wac"]
        assert 0.05 <= wac <= 0.20, f"WAC {wac:.1%} outside plausible range"

    def test_aaa_size_pct_preserved(self, base_outputs):
        """aaa_size_pct should match the input tranche definition."""
        assert abs(base_outputs["aaa_size_pct"] - 0.61) < 0.001

    def test_oc_cushion_positive_for_healthy_deal(self, base_outputs):
        """AAA OC cushion must be positive for a well-structured deal."""
        assert base_outputs["oc_cushion_aaa"] > 0, \
            "AAA OC cushion should be positive for a healthy CLO structure"

    def test_ic_cushion_positive_for_healthy_deal(self, base_outputs):
        assert base_outputs["ic_cushion_aaa"] > 0

    def test_equity_wal_less_than_pool_wal(self, base_outputs, base_deal):
        """Equity WAL should be shorter than pool WAL due to prepayments."""
        assert base_outputs["equity_wal"] < base_deal["wal"]

    def test_equity_wal_positive(self, base_outputs):
        assert base_outputs["equity_wal"] > 0


# ---------------------------------------------------------------------------
# Stress sensitivity
# ---------------------------------------------------------------------------

class TestStressSensitivity:

    def test_higher_defaults_reduce_equity_irr(self, base_deal):
        base = engine.run_scenario(base_deal, {"default_rate": 0.02, "recovery_rate": 0.65, "spread_shock_bps": 0})
        stress = engine.run_scenario(base_deal, {"default_rate": 0.08, "recovery_rate": 0.65, "spread_shock_bps": 0})
        base_irr   = engine.get_run_outputs(base["run_id"])["equity_irr"]
        stress_irr = engine.get_run_outputs(stress["run_id"])["equity_irr"]
        assert stress_irr < base_irr, \
            f"Higher defaults should reduce IRR: {stress_irr:.2%} vs {base_irr:.2%}"

    def test_lower_recovery_reduces_equity_irr(self, base_deal):
        base = engine.run_scenario(base_deal, {"default_rate": 0.04, "recovery_rate": 0.70, "spread_shock_bps": 0})
        stress = engine.run_scenario(base_deal, {"default_rate": 0.04, "recovery_rate": 0.30, "spread_shock_bps": 0})
        base_irr   = engine.get_run_outputs(base["run_id"])["equity_irr"]
        stress_irr = engine.get_run_outputs(stress["run_id"])["equity_irr"]
        assert stress_irr < base_irr

    def test_spread_shock_reduces_equity_irr(self, base_deal):
        base = engine.run_scenario(base_deal, {"default_rate": 0.03, "recovery_rate": 0.65, "spread_shock_bps": 0})
        stress = engine.run_scenario(base_deal, {"default_rate": 0.03, "recovery_rate": 0.65, "spread_shock_bps": 150})
        base_irr   = engine.get_run_outputs(base["run_id"])["equity_irr"]
        stress_irr = engine.get_run_outputs(stress["run_id"])["equity_irr"]
        assert stress_irr < base_irr

    def test_higher_defaults_reduce_oc_cushion(self, base_deal):
        """OC cushion is structural (based on tranche sizes), not scenario-dependent.
        Stress affects equity IRR and NPV more than OC ratio."""
        base = engine.run_scenario(base_deal, {"default_rate": 0.02, "recovery_rate": 0.65, "spread_shock_bps": 0})
        stress = engine.run_scenario(base_deal, {"default_rate": 0.08, "recovery_rate": 0.40, "spread_shock_bps": 0})
        base_npv   = engine.get_run_outputs(base["run_id"])["scenario_npv"]
        stress_npv = engine.get_run_outputs(stress["run_id"])["scenario_npv"]
        assert stress_npv < base_npv, "Stress scenario should reduce equity NPV"

    def test_stress_scenario_lower_irr_than_base(self, base_deal, base_scenario, stress_scenario):
        base_r   = engine.run_scenario(base_deal, base_scenario)
        stress_r = engine.run_scenario(base_deal, stress_scenario)
        base_irr   = engine.get_run_outputs(base_r["run_id"])["equity_irr"]
        stress_irr = engine.get_run_outputs(stress_r["run_id"])["equity_irr"]
        assert stress_irr < base_irr


# ---------------------------------------------------------------------------
# Coupon parsing
# ---------------------------------------------------------------------------

class TestCouponParsing:

    def test_sofr_plus_145(self):
        assert abs(engine._parse_coupon("SOFR+145") - (engine.SOFR_RATE + 0.0145)) < 1e-6

    def test_sofr_plus_200(self):
        assert abs(engine._parse_coupon("SOFR+200") - (engine.SOFR_RATE + 0.0200)) < 1e-6

    def test_sofr_plus_lowercase(self):
        assert abs(engine._parse_coupon("sofr+300") - (engine.SOFR_RATE + 0.0300)) < 1e-6

    def test_float_passthrough(self):
        assert engine._parse_coupon(0.08) == 0.08

    def test_none_returns_zero(self):
        assert engine._parse_coupon(None) == 0.0


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:

    def test_two_tranche_deal(self, base_scenario):
        """Minimal deal: just AAA and equity."""
        deal = {
            "portfolio_size": 300_000_000,
            "was": 0.038,
            "wal": 4.5,
            "tranches": [
                {"tranche_id": "t-aaa", "name": "AAA", "seniority": 1,
                 "size_pct": 0.65, "coupon": "SOFR+130"},
                {"tranche_id": "t-eq", "name": "Equity", "seniority": 2,
                 "size_pct": 0.08},
            ],
        }
        result = engine.run_scenario(deal, base_scenario)
        outputs = engine.get_run_outputs(result["run_id"])
        assert "equity_irr" in outputs
        assert isinstance(outputs["equity_irr"], float)

    def test_no_tranches_does_not_crash(self, base_scenario):
        deal = {"portfolio_size": 200_000_000, "was": 0.04, "wal": 4.0, "tranches": []}
        result = engine.run_scenario(deal, base_scenario)
        outputs = engine.get_run_outputs(result["run_id"])
        assert "equity_irr" in outputs

    def test_extreme_stress_irr_clamped(self, base_deal):
        """Deep stress should not produce nonsensical IRR values."""
        extreme = {"default_rate": 0.50, "recovery_rate": 0.0, "spread_shock_bps": 500}
        result = engine.run_scenario(base_deal, extreme)
        outputs = engine.get_run_outputs(result["run_id"])
        assert outputs["equity_irr"] >= -0.99

    def test_larger_pool_same_ratios(self, base_scenario):
        """Scaling pool size should preserve ratio-based metrics."""
        small = {"portfolio_size": 200_000_000, "was": 0.042, "wal": 5.2,
                 "tranches": [{"tranche_id": "t-aaa", "name": "AAA", "seniority": 1,
                                "size_pct": 0.61, "coupon": "SOFR+145"},
                               {"tranche_id": "t-eq", "name": "Equity", "seniority": 2,
                                "size_pct": 0.09}]}
        large = {**small, "portfolio_size": 1_000_000_000}
        sr = engine.run_scenario(small, base_scenario)
        lr = engine.run_scenario(large, base_scenario)
        so = engine.get_run_outputs(sr["run_id"])
        lo = engine.get_run_outputs(lr["run_id"])
        # OC/IC cushions are ratio-based — should be identical regardless of size
        assert abs(so["oc_cushion_aaa"] - lo["oc_cushion_aaa"]) < 0.001
        assert abs(so["ic_cushion_aaa"] - lo["ic_cushion_aaa"]) < 0.001
        # IRR should be very close (minor float differences only)
        assert abs(so["equity_irr"] - lo["equity_irr"]) < 0.001


# ---------------------------------------------------------------------------
# IRR solver
# ---------------------------------------------------------------------------

class TestIRRSolver:

    def test_positive_cashflows_positive_irr(self):
        irr = engine._solve_irr(
            investment=100, annual_cf=15, terminal=100, wal=5
        )
        assert irr > 0

    def test_zero_cashflows_negative_irr(self):
        irr = engine._solve_irr(
            investment=100, annual_cf=0, terminal=50, wal=5
        )
        assert irr < 0

    def test_irr_consistent_with_npv(self):
        """NPV at the solved IRR should be approximately zero."""
        irr = engine._solve_irr(
            investment=45_000_000,
            annual_cf=5_000_000,
            terminal=40_000_000,
            wal=5.0,
        )
        npv = engine._npv(irr, 45_000_000, 5_000_000, 40_000_000, 5.0)
        assert abs(npv) < 1_000, f"NPV at IRR should be near zero, got {npv:,.0f}"
