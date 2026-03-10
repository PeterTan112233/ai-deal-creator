"""
tests/test_deal_registry_service.py

Tests for app/services/deal_registry_service.py

Covers:
  - register / get / list_all / unregister / clear / count
  - update_pipeline_result
  - Thread-safety is not tested here (requires concurrent load)
  - Record structure: required keys, types
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from app.services import deal_registry_service as reg


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _deal(deal_id="reg-deal-001", name="Registry Test CLO"):
    return {
        "deal_id": deal_id,
        "name": name,
        "issuer": "Registry Issuer LLC",
        "region": "US",
        "currency": "USD",
        "manager": "Registry Manager",
        "collateral": {
            "pool_id": f"pool-{deal_id}",
            "asset_class": "broadly_syndicated_loans",
            "portfolio_size": 400_000_000,
            "diversity_score": 58,
            "ccc_bucket": 0.06,
        },
        "liabilities": [
            {"tranche_id": "t-aaa", "name": "AAA", "seniority": 1, "size_pct": 0.62},
            {"tranche_id": "t-eq",  "name": "Equity", "seniority": 2, "size_pct": 0.10},
        ],
    }


@pytest.fixture(autouse=True)
def clean_registry():
    """Clear the registry before every test."""
    reg.clear()
    yield
    reg.clear()


# ---------------------------------------------------------------------------
# register / get
# ---------------------------------------------------------------------------

class TestRegisterAndGet:

    def test_register_returns_record(self):
        rec = reg.register(_deal())
        assert isinstance(rec, dict)

    def test_register_stores_deal_id(self):
        reg.register(_deal("d-001"))
        assert reg.get("d-001") is not None

    def test_register_record_has_required_keys(self):
        rec = reg.register(_deal())
        for key in ("deal_id", "name", "issuer", "registered_at", "status",
                    "portfolio_size", "tranche_count", "pipeline_count"):
            assert key in rec, f"Missing key: {key}"

    def test_register_tranche_count_correct(self):
        rec = reg.register(_deal())
        assert rec["tranche_count"] == 2

    def test_register_portfolio_size_correct(self):
        rec = reg.register(_deal())
        assert rec["portfolio_size"] == 400_000_000

    def test_register_status_active(self):
        rec = reg.register(_deal())
        assert rec["status"] == "active"

    def test_register_pipeline_count_zero(self):
        rec = reg.register(_deal())
        assert rec["pipeline_count"] == 0

    def test_register_stores_deal_input(self):
        d = _deal()
        reg.register(d)
        stored = reg.get(d["deal_id"])
        assert stored["deal_input"]["deal_id"] == d["deal_id"]

    def test_get_returns_none_for_unknown(self):
        assert reg.get("nonexistent-id") is None

    def test_register_overwrites_existing(self):
        reg.register(_deal("d-dup", "Version 1"))
        reg.register(_deal("d-dup", "Version 2"))
        assert reg.get("d-dup")["name"] == "Version 2"
        assert reg.count() == 1


# ---------------------------------------------------------------------------
# list_all / count
# ---------------------------------------------------------------------------

class TestListAndCount:

    def test_empty_registry_returns_empty_list(self):
        assert reg.list_all() == []

    def test_count_zero_initially(self):
        assert reg.count() == 0

    def test_list_all_after_register(self):
        reg.register(_deal("d-a"))
        reg.register(_deal("d-b"))
        records = reg.list_all()
        assert len(records) == 2

    def test_count_matches_list_length(self):
        reg.register(_deal("d-1"))
        reg.register(_deal("d-2"))
        reg.register(_deal("d-3"))
        assert reg.count() == 3
        assert len(reg.list_all()) == 3

    def test_list_all_sorted_most_recent_first(self):
        import time
        reg.register(_deal("older"))
        time.sleep(0.01)
        reg.register(_deal("newer"))
        records = reg.list_all()
        assert records[0]["deal_id"] == "newer"

    def test_list_all_contains_all_deal_ids(self):
        ids = {"d-x", "d-y", "d-z"}
        for i in ids:
            reg.register(_deal(i))
        returned_ids = {r["deal_id"] for r in reg.list_all()}
        assert returned_ids == ids


# ---------------------------------------------------------------------------
# unregister / clear
# ---------------------------------------------------------------------------

class TestUnregisterAndClear:

    def test_unregister_returns_true_for_existing(self):
        reg.register(_deal("d-del"))
        assert reg.unregister("d-del") is True

    def test_unregister_removes_from_registry(self):
        reg.register(_deal("d-gone"))
        reg.unregister("d-gone")
        assert reg.get("d-gone") is None

    def test_unregister_returns_false_for_missing(self):
        assert reg.unregister("never-registered") is False

    def test_clear_removes_all(self):
        reg.register(_deal("d-1"))
        reg.register(_deal("d-2"))
        n = reg.clear()
        assert n == 2
        assert reg.count() == 0

    def test_clear_returns_count(self):
        reg.register(_deal("d-a"))
        reg.register(_deal("d-b"))
        reg.register(_deal("d-c"))
        assert reg.clear() == 3


# ---------------------------------------------------------------------------
# update_pipeline_result
# ---------------------------------------------------------------------------

class TestUpdatePipelineResult:

    def test_update_returns_true_for_registered_deal(self):
        reg.register(_deal("d-pipe"))
        result = reg.update_pipeline_result("d-pipe", {"pipeline_id": "pip-001"})
        assert result is True

    def test_update_returns_false_for_unknown_deal(self):
        assert reg.update_pipeline_result("not-registered", {}) is False

    def test_update_stores_result(self):
        reg.register(_deal("d-pipe2"))
        reg.update_pipeline_result("d-pipe2", {"pipeline_id": "pip-abc"})
        stored = reg.get("d-pipe2")
        assert stored["last_pipeline_result"]["pipeline_id"] == "pip-abc"

    def test_update_increments_pipeline_count(self):
        reg.register(_deal("d-pipe3"))
        reg.update_pipeline_result("d-pipe3", {})
        reg.update_pipeline_result("d-pipe3", {})
        assert reg.get("d-pipe3")["pipeline_count"] == 2

    def test_update_sets_last_pipeline_at(self):
        reg.register(_deal("d-pipe4"))
        reg.update_pipeline_result("d-pipe4", {})
        stored = reg.get("d-pipe4")
        assert stored["last_pipeline_at"] is not None

    def test_update_overwrites_previous_result(self):
        reg.register(_deal("d-pipe5"))
        reg.update_pipeline_result("d-pipe5", {"pipeline_id": "pip-1"})
        reg.update_pipeline_result("d-pipe5", {"pipeline_id": "pip-2"})
        stored = reg.get("d-pipe5")
        assert stored["last_pipeline_result"]["pipeline_id"] == "pip-2"
