"""
tests/test_create_deal_workflow.py

Tests for app/workflows/create_deal_workflow.py

Covers:
  - create_deal_workflow: happy path, pool validation failure, audit event
  - deal_input_from_domain: bridge to run_scenario_workflow
  - End-to-end: create_deal → deal_input_from_domain → run_scenario_workflow
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.domain.deal import Deal
from app.domain.collateral import Collateral
from app.domain.structure import Structure
from app.domain.tranche import Tranche
from app.workflows.create_deal_workflow import create_deal_workflow, deal_input_from_domain
from app.workflows.run_scenario_workflow import run_scenario_workflow


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def deal():
    return Deal(
        deal_id="deal-test-001",
        name="Test CLO I",
        issuer="Test Issuer LLC",
        region="US",
        currency="USD",
        manager="Test Manager",
    )


@pytest.fixture
def collateral():
    return Collateral(
        collateral_id="coll-001",
        deal_id="deal-test-001",
        pool_id="pool-001",
        asset_class="broadly_syndicated_loans",
        portfolio_size=500_000_000,
        was=0.042,
        warf=2800,
        wal=5.2,
        diversity_score=62,
        ccc_bucket=0.055,
    )


@pytest.fixture
def structure(deal):
    return Structure(
        structure_id="struct-001",
        deal_id=deal.deal_id,
        tranches=[
            Tranche(tranche_id="t-aaa", name="AAA", seniority=1, size_pct=0.61,
                    coupon="SOFR+145", target_rating="Aaa"),
            Tranche(tranche_id="t-equity", name="Equity", seniority=2, size_pct=0.09),
        ],
    )


@pytest.fixture
def bad_collateral():
    """Collateral that fails pool validation (CCC too high)."""
    return Collateral(
        collateral_id="coll-bad",
        deal_id="deal-test-001",
        pool_id="pool-bad",
        asset_class="broadly_syndicated_loans",
        portfolio_size=300_000_000,
        diversity_score=62,
        ccc_bucket=0.10,  # exceeds 7.5% limit
    )


# ---------------------------------------------------------------------------
# create_deal_workflow
# ---------------------------------------------------------------------------

class TestCreateDealWorkflow:

    def test_happy_path_returns_summary(self, deal, collateral, structure):
        result = create_deal_workflow(deal, collateral, structure)
        assert result["deal_id"] == "deal-test-001"
        assert result["name"] == "Test CLO I"
        assert result["tranche_count"] == 2

    def test_returns_pool_id(self, deal, collateral, structure):
        result = create_deal_workflow(deal, collateral, structure)
        assert result["pool_id"] == "pool-001"

    def test_returns_portfolio_size(self, deal, collateral, structure):
        result = create_deal_workflow(deal, collateral, structure)
        assert result["portfolio_size"] == 500_000_000

    def test_pool_validation_failure_raises(self, deal, bad_collateral, structure):
        with pytest.raises(ValueError, match="Pool validation failed"):
            create_deal_workflow(deal, bad_collateral, structure)

    def test_audit_event_emitted(self, deal, collateral, structure, tmp_path, monkeypatch):
        """Audit logger writes to data/audit_log.jsonl — verify event is recorded."""
        import app.services.audit_logger as al
        events = []
        original = al.record_event
        def capture(*args, **kwargs):
            ev = original(*args, **kwargs)
            events.append(ev)
            return ev
        monkeypatch.setattr(al, "record_event", capture)
        create_deal_workflow(deal, collateral, structure)
        assert any(e["event_type"] == "deal.created" for e in events)

    def test_actor_is_recorded(self, deal, collateral, structure, monkeypatch):
        import app.services.audit_logger as al
        events = []
        original = al.record_event
        def capture(*args, **kwargs):
            ev = original(*args, **kwargs)
            events.append(ev)
            return ev
        monkeypatch.setattr(al, "record_event", capture)
        create_deal_workflow(deal, collateral, structure, actor="test-runner")
        created = next(e for e in events if e["event_type"] == "deal.created")
        assert created["actor"] == "test-runner"


# ---------------------------------------------------------------------------
# deal_input_from_domain
# ---------------------------------------------------------------------------

class TestDealInputFromDomain:

    def test_returns_dict(self, deal, collateral, structure):
        result = deal_input_from_domain(deal, collateral, structure)
        assert isinstance(result, dict)

    def test_deal_id_propagated(self, deal, collateral, structure):
        result = deal_input_from_domain(deal, collateral, structure)
        assert result["deal_id"] == "deal-test-001"

    def test_name_propagated(self, deal, collateral, structure):
        result = deal_input_from_domain(deal, collateral, structure)
        assert result["name"] == "Test CLO I"

    def test_issuer_propagated(self, deal, collateral, structure):
        result = deal_input_from_domain(deal, collateral, structure)
        assert result["issuer"] == "Test Issuer LLC"

    def test_collateral_block_present(self, deal, collateral, structure):
        result = deal_input_from_domain(deal, collateral, structure)
        assert "collateral" in result
        assert result["collateral"]["pool_id"] == "pool-001"
        assert result["collateral"]["portfolio_size"] == 500_000_000
        assert result["collateral"]["asset_class"] == "broadly_syndicated_loans"

    def test_collateral_metrics_propagated(self, deal, collateral, structure):
        result = deal_input_from_domain(deal, collateral, structure)
        c = result["collateral"]
        assert c["was"] == 0.042
        assert c["warf"] == 2800
        assert c["wal"] == 5.2
        assert c["diversity_score"] == 62
        assert c["ccc_bucket"] == 0.055

    def test_tranches_present(self, deal, collateral, structure):
        result = deal_input_from_domain(deal, collateral, structure)
        assert "liabilities" in result
        assert len(result["liabilities"]) == 2

    def test_tranche_seniority_preserved(self, deal, collateral, structure):
        result = deal_input_from_domain(deal, collateral, structure)
        tranches = sorted(result["liabilities"], key=lambda t: t["seniority"])
        assert tranches[0]["name"] == "AAA"
        assert tranches[0]["seniority"] == 1
        assert tranches[1]["name"] == "Equity"

    def test_tranche_coupon_propagated(self, deal, collateral, structure):
        result = deal_input_from_domain(deal, collateral, structure)
        aaa = next(t for t in result["liabilities"] if t["name"] == "AAA")
        assert aaa.get("coupon") == "SOFR+145"

    def test_market_assumptions_absent_when_not_provided(self, deal, collateral, structure):
        result = deal_input_from_domain(deal, collateral, structure)
        assert "market_assumptions" not in result

    def test_market_assumptions_included_when_provided(self, deal, collateral, structure):
        assumptions = {"default_rate": 0.03, "recovery_rate": 0.65, "spread_shock_bps": 0}
        result = deal_input_from_domain(deal, collateral, structure, market_assumptions=assumptions)
        assert result["market_assumptions"]["default_rate"] == 0.03

    def test_no_none_values_in_collateral(self, deal, collateral, structure):
        """None values are stripped from collateral to keep the dict clean."""
        result = deal_input_from_domain(deal, collateral, structure)
        for k, v in result["collateral"].items():
            assert v is not None, f"collateral.{k} should not be None"


# ---------------------------------------------------------------------------
# End-to-end: create_deal → deal_input_from_domain → run_scenario_workflow
# ---------------------------------------------------------------------------

class TestCreateDealToRunScenarioBridge:

    def test_bridge_output_is_valid_for_run_scenario(self, deal, collateral, structure):
        """deal_input_from_domain output must pass run_scenario_workflow validation."""
        deal_input = deal_input_from_domain(
            deal, collateral, structure,
            market_assumptions={"default_rate": 0.03, "recovery_rate": 0.65, "spread_shock_bps": 0},
        )
        result = run_scenario_workflow(deal_input, scenario_name="Baseline", actor="test")
        assert result["validation"]["valid"] is True
        assert result["scenario_result"] is not None

    def test_bridge_preserves_deal_id_through_full_flow(self, deal, collateral, structure):
        deal_input = deal_input_from_domain(
            deal, collateral, structure,
            market_assumptions={"default_rate": 0.03, "recovery_rate": 0.65, "spread_shock_bps": 0},
        )
        result = run_scenario_workflow(deal_input, actor="test")
        assert result["scenario_result"]["deal_id"] == "deal-test-001"

    def test_bridge_without_market_assumptions_still_runs(self, deal, collateral, structure):
        """run_scenario_workflow uses defaults when market_assumptions is absent."""
        deal_input = deal_input_from_domain(deal, collateral, structure)
        result = run_scenario_workflow(deal_input, actor="test")
        assert result["validation"]["valid"] is True
        # Should warn about missing market_assumptions
        assert any("market_assumptions" in w for w in result["validation"]["warnings"])
