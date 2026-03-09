"""
Tests for Pydantic schema validation.
"""

import pytest
from pydantic import ValidationError
from app.schemas.deal_schema import DealSchema
from app.schemas.collateral_schema import CollateralSchema
from app.schemas.tranche_schema import TrancheSchema
from app.schemas.structure_schema import StructureSchema
from app.schemas.scenario_schema import ScenarioSchema


# --- DealSchema ---

def test_deal_schema_valid():
    d = DealSchema(deal_id="d1", name="Test CLO", issuer="Issuer Co")
    assert d.deal_id == "d1"
    assert d.status == "draft"
    assert d.version == 1


def test_deal_schema_missing_name():
    with pytest.raises(ValidationError):
        DealSchema(deal_id="d1", name="", issuer="Issuer Co")


# --- CollateralSchema ---

def test_collateral_schema_valid():
    c = CollateralSchema(
        collateral_id="c1", deal_id="d1", pool_id="pool-001",
        asset_class="broadly_syndicated_loans", portfolio_size=500_000_000,
        was=0.042, warf=2800, wal=5.2, diversity_score=62, ccc_bucket=0.055,
    )
    assert c.portfolio_size == 500_000_000


def test_collateral_schema_zero_size():
    with pytest.raises(ValidationError):
        CollateralSchema(
            collateral_id="c1", deal_id="d1", pool_id="pool-001",
            asset_class="bsl", portfolio_size=0,
            was=0.04, warf=2500, wal=5.0, diversity_score=60, ccc_bucket=0.05,
        )


def test_collateral_schema_ccc_over_limit():
    with pytest.raises(ValidationError):
        CollateralSchema(
            collateral_id="c1", deal_id="d1", pool_id="pool-001",
            asset_class="bsl", portfolio_size=100_000_000,
            was=0.04, warf=2500, wal=5.0, diversity_score=60, ccc_bucket=1.5,
        )


# --- TrancheSchema ---

def test_tranche_schema_valid_with_size_pct():
    t = TrancheSchema(tranche_id="t1", name="AAA", seniority=1, size_pct=0.61)
    assert t.size_pct == 0.61


def test_tranche_schema_valid_with_size_abs():
    t = TrancheSchema(tranche_id="t1", name="AAA", seniority=1, size_abs=300_000_000)
    assert t.size_abs == 300_000_000


def test_tranche_schema_no_size():
    with pytest.raises(ValidationError):
        TrancheSchema(tranche_id="t1", name="AAA", seniority=1)


# --- StructureSchema ---

def test_structure_schema_valid():
    s = StructureSchema(
        structure_id="s1",
        deal_id="d1",
        tranches=[
            {"tranche_id": "t1", "name": "AAA", "seniority": 1, "size_pct": 0.61},
            {"tranche_id": "t2", "name": "Equity", "seniority": 2, "size_pct": 0.09},
        ],
    )
    assert len(s.tranches) == 2


def test_structure_schema_duplicate_seniority():
    with pytest.raises(ValidationError):
        StructureSchema(
            structure_id="s1",
            deal_id="d1",
            tranches=[
                {"tranche_id": "t1", "name": "AAA", "seniority": 1, "size_pct": 0.61},
                {"tranche_id": "t2", "name": "AA", "seniority": 1, "size_pct": 0.09},
            ],
        )


def test_structure_schema_empty_tranches():
    with pytest.raises(ValidationError):
        StructureSchema(structure_id="s1", deal_id="d1", tranches=[])


# --- ScenarioSchema ---

def test_scenario_schema_valid():
    s = ScenarioSchema(
        scenario_id="sc1", deal_id="d1", name="Baseline",
        parameters={"default_rate": 0.03, "recovery_rate": 0.65},
    )
    assert s.source == "model_runner"


def test_scenario_schema_empty_parameters():
    with pytest.raises(ValidationError):
        ScenarioSchema(
            scenario_id="sc1", deal_id="d1", name="Baseline",
            parameters={},
        )
