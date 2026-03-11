"""
tests/test_scoring_service.py

Tests for app/services/scoring_service.py

Covers:
  - Composite score is 0-100
  - Grade assignment: A/B/C/D thresholds
  - IRR quality scoring (0% → 0, 15% → 100)
  - OC adequacy scoring
  - Stress resilience scoring
  - Collateral quality scoring
  - Top drivers are top 2 by score
  - Risk flags triggered correctly
  - Missing inputs handled gracefully
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from app.services.scoring_service import score_deal, _score_irr, _score_oc, _assign_grade


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

GOOD_METRICS = {
    "equity_irr":    0.12,
    "oc_cushion_aaa": 0.22,
}

GOOD_COLLATERAL = {
    "diversity_score": 65,
    "was":             0.045,
    "ccc_bucket":      0.04,
}

BAD_METRICS = {
    "equity_irr":    0.03,
    "oc_cushion_aaa": -0.01,
}

BAD_COLLATERAL = {
    "diversity_score": 25,
    "was":             0.02,
    "ccc_bucket":      0.07,
}


# ---------------------------------------------------------------------------
# score_deal: top-level structure
# ---------------------------------------------------------------------------

class TestScoreDealStructure:

    def test_returns_dict(self):
        result = score_deal(GOOD_METRICS, GOOD_COLLATERAL)
        assert isinstance(result, dict)

    def test_has_required_keys(self):
        result = score_deal(GOOD_METRICS, GOOD_COLLATERAL)
        for key in ("composite_score", "grade", "grade_label",
                    "dimension_scores", "top_drivers", "risk_flags"):
            assert key in result

    def test_composite_score_range(self):
        result = score_deal(GOOD_METRICS, GOOD_COLLATERAL)
        assert 0 <= result["composite_score"] <= 100

    def test_dimension_scores_present(self):
        result = score_deal(GOOD_METRICS, GOOD_COLLATERAL)
        dims = result["dimension_scores"]
        assert "irr_quality" in dims
        assert "oc_adequacy" in dims
        assert "stress_resilience" in dims
        assert "collateral_quality" in dims

    def test_each_dimension_has_score_and_weight(self):
        result = score_deal(GOOD_METRICS, GOOD_COLLATERAL)
        for dim in result["dimension_scores"].values():
            assert "score" in dim
            assert "weight" in dim
            assert 0 <= dim["score"] <= 100

    def test_weights_sum_to_one(self):
        result = score_deal(GOOD_METRICS, GOOD_COLLATERAL)
        total = sum(d["weight"] for d in result["dimension_scores"].values())
        assert total == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Grade assignment
# ---------------------------------------------------------------------------

class TestGradeAssignment:

    def test_grade_a_at_75(self):
        grade, label = _assign_grade(75)
        assert grade == "A"
        assert label == "Strong"

    def test_grade_a_above_75(self):
        grade, _ = _assign_grade(90)
        assert grade == "A"

    def test_grade_b_at_55(self):
        grade, label = _assign_grade(55)
        assert grade == "B"
        assert label == "Adequate"

    def test_grade_b_just_below_a(self):
        grade, _ = _assign_grade(74)
        assert grade == "B"

    def test_grade_c_at_35(self):
        grade, label = _assign_grade(35)
        assert grade == "C"
        assert label == "Marginal"

    def test_grade_d_below_35(self):
        grade, label = _assign_grade(20)
        assert grade == "D"
        assert label == "Weak"

    def test_grade_d_at_zero(self):
        grade, _ = _assign_grade(0)
        assert grade == "D"

    def test_good_deal_gets_high_grade(self):
        result = score_deal(GOOD_METRICS, GOOD_COLLATERAL)
        assert result["grade"] in ("A", "B")

    def test_bad_deal_gets_low_grade(self):
        result = score_deal(BAD_METRICS, BAD_COLLATERAL)
        assert result["grade"] in ("C", "D")


# ---------------------------------------------------------------------------
# IRR quality scoring
# ---------------------------------------------------------------------------

class TestIrrScoring:

    def test_zero_irr_gives_zero(self):
        assert _score_irr(0.0) == 0.0

    def test_15_pct_irr_gives_100(self):
        assert _score_irr(0.15) == pytest.approx(100.0)

    def test_above_15_pct_capped_at_100(self):
        assert _score_irr(0.20) == 100.0

    def test_negative_irr_gives_zero(self):
        assert _score_irr(-0.05) == 0.0

    def test_7_5_pct_irr_gives_50(self):
        assert _score_irr(0.075) == pytest.approx(50.0)

    def test_none_irr_gives_zero(self):
        assert _score_irr(None) == 0.0

    def test_higher_irr_gives_higher_score(self):
        assert _score_irr(0.12) > _score_irr(0.08)


# ---------------------------------------------------------------------------
# OC adequacy scoring
# ---------------------------------------------------------------------------

class TestOcScoring:

    def test_negative_5_pct_gives_zero(self):
        assert _score_oc(-0.05) == pytest.approx(0.0)

    def test_25_pct_gives_100(self):
        assert _score_oc(0.25) == pytest.approx(100.0)

    def test_above_25_pct_capped(self):
        assert _score_oc(0.40) == 100.0

    def test_zero_oc_gives_midpoint(self):
        # 0% → (0.05) / 0.30 * 100 ≈ 16.7
        assert _score_oc(0.0) == pytest.approx(16.67, abs=0.1)

    def test_10_pct_oc_scores_higher_than_5_pct(self):
        assert _score_oc(0.10) > _score_oc(0.05)


# ---------------------------------------------------------------------------
# Stress resilience
# ---------------------------------------------------------------------------

class TestStressResilience:

    def test_no_drawdown_gives_100(self):
        result = score_deal(GOOD_METRICS, GOOD_COLLATERAL, stress_drawdown=0.0)
        assert result["dimension_scores"]["stress_resilience"]["score"] == pytest.approx(100.0)

    def test_full_drawdown_gives_zero(self):
        # drawdown == base_irr → 0% retention
        result = score_deal(GOOD_METRICS, GOOD_COLLATERAL,
                            stress_drawdown=GOOD_METRICS["equity_irr"])
        assert result["dimension_scores"]["stress_resilience"]["score"] == pytest.approx(0.0)

    def test_half_drawdown_gives_50(self):
        base_irr = GOOD_METRICS["equity_irr"]
        result = score_deal(GOOD_METRICS, GOOD_COLLATERAL,
                            stress_drawdown=base_irr * 0.5)
        assert result["dimension_scores"]["stress_resilience"]["score"] == pytest.approx(50.0)

    def test_no_stress_data_uses_proxy(self):
        # Without stress_drawdown, still returns a score
        result = score_deal(GOOD_METRICS, GOOD_COLLATERAL, stress_drawdown=None)
        assert result["dimension_scores"]["stress_resilience"]["score"] >= 0


# ---------------------------------------------------------------------------
# Risk flags
# ---------------------------------------------------------------------------

class TestRiskFlags:

    def test_low_irr_triggers_flag(self):
        result = score_deal({"equity_irr": 0.04, "oc_cushion_aaa": 0.20}, {})
        assert any("IRR" in f for f in result["risk_flags"])

    def test_thin_oc_triggers_flag(self):
        result = score_deal({"equity_irr": 0.10, "oc_cushion_aaa": 0.02}, {})
        assert any("OC" in f for f in result["risk_flags"])

    def test_high_ccc_triggers_flag(self):
        result = score_deal(GOOD_METRICS, {"ccc_bucket": 0.07})
        assert any("CCC" in f for f in result["risk_flags"])

    def test_low_diversity_triggers_flag(self):
        result = score_deal(GOOD_METRICS, {"diversity_score": 30})
        assert any("diversity" in f.lower() for f in result["risk_flags"])

    def test_good_deal_no_risk_flags(self):
        result = score_deal(GOOD_METRICS, GOOD_COLLATERAL, stress_drawdown=0.02)
        assert result["risk_flags"] == []

    def test_stress_flag_when_low_retention(self):
        # drawdown = 80% of base IRR → 20% retention < 50% threshold
        base_irr = GOOD_METRICS["equity_irr"]
        result = score_deal(GOOD_METRICS, GOOD_COLLATERAL,
                            stress_drawdown=base_irr * 0.80)
        assert any("retention" in f.lower() for f in result["risk_flags"])


# ---------------------------------------------------------------------------
# Top drivers
# ---------------------------------------------------------------------------

class TestTopDrivers:

    def test_two_top_drivers_returned(self):
        result = score_deal(GOOD_METRICS, GOOD_COLLATERAL)
        assert len(result["top_drivers"]) == 2

    def test_top_drivers_are_strings(self):
        result = score_deal(GOOD_METRICS, GOOD_COLLATERAL)
        for d in result["top_drivers"]:
            assert isinstance(d, str)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:

    def test_empty_metrics_returns_score(self):
        result = score_deal({}, {})
        assert "composite_score" in result
        assert result["composite_score"] >= 0

    def test_none_values_handled(self):
        result = score_deal({"equity_irr": None, "oc_cushion_aaa": None}, {})
        assert result["composite_score"] >= 0
