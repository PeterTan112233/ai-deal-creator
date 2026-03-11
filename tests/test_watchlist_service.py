"""
tests/test_watchlist_service.py

Tests for app/services/watchlist_service.py

Covers:
  - add_item, get_item, list_items, remove_item, deactivate_item, clear, count
  - check_outputs: triggered vs not triggered for all operators
  - deal_id filtering (global vs per-deal items)
  - Invalid operator raises ValueError
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from app.services import watchlist_service


@pytest.fixture(autouse=True)
def clean_watchlist():
    watchlist_service.clear()
    yield
    watchlist_service.clear()


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

class TestCrud:

    def test_add_item_returns_dict(self):
        item = watchlist_service.add_item("equity_irr", "lt", 0.08)
        assert isinstance(item, dict)

    def test_add_item_has_item_id(self):
        item = watchlist_service.add_item("equity_irr", "lt", 0.08)
        assert "item_id" in item
        assert item["item_id"].startswith("wl-")

    def test_add_item_stores_metric(self):
        item = watchlist_service.add_item("equity_irr", "lt", 0.08)
        assert item["metric"] == "equity_irr"
        assert item["operator"] == "lt"
        assert item["threshold"] == 0.08

    def test_add_item_default_severity_warning(self):
        item = watchlist_service.add_item("equity_irr", "lt", 0.08)
        assert item["severity"] == "warning"

    def test_add_item_custom_severity(self):
        item = watchlist_service.add_item("equity_irr", "lt", 0.05, severity="critical")
        assert item["severity"] == "critical"

    def test_add_item_custom_label(self):
        item = watchlist_service.add_item("equity_irr", "lt", 0.08, label="IRR red flag")
        assert item["label"] == "IRR red flag"

    def test_add_item_deal_id_none_by_default(self):
        item = watchlist_service.add_item("equity_irr", "lt", 0.08)
        assert item["deal_id"] is None

    def test_add_item_with_deal_id(self):
        item = watchlist_service.add_item("equity_irr", "lt", 0.08, deal_id="deal-123")
        assert item["deal_id"] == "deal-123"

    def test_add_item_invalid_operator_raises(self):
        with pytest.raises(ValueError):
            watchlist_service.add_item("equity_irr", "bad_op", 0.08)

    def test_get_item_returns_item(self):
        item = watchlist_service.add_item("equity_irr", "lt", 0.08)
        fetched = watchlist_service.get_item(item["item_id"])
        assert fetched["item_id"] == item["item_id"]

    def test_get_item_missing_returns_none(self):
        assert watchlist_service.get_item("nonexistent") is None

    def test_list_items_empty(self):
        assert watchlist_service.list_items() == []

    def test_list_items_returns_all(self):
        watchlist_service.add_item("equity_irr", "lt", 0.08)
        watchlist_service.add_item("oc_cushion_aaa", "lt", 0.0)
        items = watchlist_service.list_items()
        assert len(items) == 2

    def test_remove_item_returns_true(self):
        item = watchlist_service.add_item("equity_irr", "lt", 0.08)
        assert watchlist_service.remove_item(item["item_id"]) is True

    def test_remove_item_missing_returns_false(self):
        assert watchlist_service.remove_item("nonexistent") is False

    def test_remove_item_no_longer_listed(self):
        item = watchlist_service.add_item("equity_irr", "lt", 0.08)
        watchlist_service.remove_item(item["item_id"])
        assert watchlist_service.list_items() == []

    def test_deactivate_item(self):
        item = watchlist_service.add_item("equity_irr", "lt", 0.08)
        assert watchlist_service.deactivate_item(item["item_id"]) is True
        assert watchlist_service.list_items() == []  # inactive items excluded

    def test_deactivate_missing_returns_false(self):
        assert watchlist_service.deactivate_item("nonexistent") is False

    def test_count(self):
        watchlist_service.add_item("equity_irr", "lt", 0.08)
        watchlist_service.add_item("wac", "gt", 0.15)
        assert watchlist_service.count() == 2

    def test_clear(self):
        watchlist_service.add_item("equity_irr", "lt", 0.08)
        n = watchlist_service.clear()
        assert n == 1
        assert watchlist_service.count() == 0


# ---------------------------------------------------------------------------
# check_outputs — operators
# ---------------------------------------------------------------------------

class TestCheckOutputsOperators:

    def test_lt_triggered(self):
        watchlist_service.add_item("equity_irr", "lt", 0.10)
        alerts = watchlist_service.check_outputs({"equity_irr": 0.05})
        assert alerts[0]["triggered"] is True

    def test_lt_not_triggered(self):
        watchlist_service.add_item("equity_irr", "lt", 0.10)
        alerts = watchlist_service.check_outputs({"equity_irr": 0.12})
        assert alerts[0]["triggered"] is False

    def test_lte_triggered_equal(self):
        watchlist_service.add_item("equity_irr", "lte", 0.10)
        alerts = watchlist_service.check_outputs({"equity_irr": 0.10})
        assert alerts[0]["triggered"] is True

    def test_gt_triggered(self):
        watchlist_service.add_item("wac", "gt", 0.12)
        alerts = watchlist_service.check_outputs({"wac": 0.15})
        assert alerts[0]["triggered"] is True

    def test_gt_not_triggered(self):
        watchlist_service.add_item("wac", "gt", 0.12)
        alerts = watchlist_service.check_outputs({"wac": 0.10})
        assert alerts[0]["triggered"] is False

    def test_gte_triggered_equal(self):
        watchlist_service.add_item("wac", "gte", 0.12)
        alerts = watchlist_service.check_outputs({"wac": 0.12})
        assert alerts[0]["triggered"] is True

    def test_eq_triggered(self):
        watchlist_service.add_item("equity_irr", "eq", 0.10)
        alerts = watchlist_service.check_outputs({"equity_irr": 0.10})
        assert alerts[0]["triggered"] is True

    def test_missing_metric_skipped(self):
        watchlist_service.add_item("nonexistent_metric", "lt", 0.10)
        alerts = watchlist_service.check_outputs({"equity_irr": 0.08})
        assert alerts == []


# ---------------------------------------------------------------------------
# check_outputs — deal_id filtering
# ---------------------------------------------------------------------------

class TestCheckOutputsDealFilter:

    def test_global_item_applies_to_all_deals(self):
        watchlist_service.add_item("equity_irr", "lt", 0.10)  # deal_id=None
        alerts = watchlist_service.check_outputs({"equity_irr": 0.05}, deal_id="any-deal")
        assert len(alerts) == 1

    def test_deal_specific_item_matches(self):
        watchlist_service.add_item("equity_irr", "lt", 0.10, deal_id="deal-abc")
        alerts = watchlist_service.check_outputs({"equity_irr": 0.05}, deal_id="deal-abc")
        assert len(alerts) == 1

    def test_deal_specific_item_excluded_for_other_deal(self):
        watchlist_service.add_item("equity_irr", "lt", 0.10, deal_id="deal-abc")
        alerts = watchlist_service.check_outputs({"equity_irr": 0.05}, deal_id="deal-xyz")
        assert len(alerts) == 0

    def test_mixed_global_and_specific(self):
        watchlist_service.add_item("equity_irr", "lt", 0.10)               # global
        watchlist_service.add_item("wac", "gt", 0.12, deal_id="deal-abc")  # specific
        # deal-abc: sees both
        alerts_abc = watchlist_service.check_outputs(
            {"equity_irr": 0.05, "wac": 0.15}, deal_id="deal-abc"
        )
        assert len(alerts_abc) == 2
        # deal-xyz: sees only global
        alerts_xyz = watchlist_service.check_outputs(
            {"equity_irr": 0.05, "wac": 0.15}, deal_id="deal-xyz"
        )
        assert len(alerts_xyz) == 1

    def test_check_without_deal_id_sees_all_global_items(self):
        watchlist_service.add_item("equity_irr", "lt", 0.10)
        watchlist_service.add_item("wac", "gt", 0.12)
        alerts = watchlist_service.check_outputs({"equity_irr": 0.05, "wac": 0.15})
        assert len(alerts) == 2
