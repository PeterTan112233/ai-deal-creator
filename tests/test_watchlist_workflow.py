"""
tests/test_watchlist_workflow.py

Tests for app/workflows/watchlist_workflow.py

Covers:
  - Return structure
  - No watchlist items → empty alerts, no error
  - Triggered alerts returned correctly
  - Non-triggered items included (triggered=False)
  - Invalid deal returns error
  - Audit events emitted
"""

import json
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from app.services import watchlist_service
from app.workflows.watchlist_workflow import watchlist_check_workflow


@pytest.fixture(autouse=True)
def clean_watchlist():
    watchlist_service.clear()
    yield
    watchlist_service.clear()


def _load_deal(label: str) -> dict:
    with open("data/samples/sample_deal_inputs.json") as f:
        data = json.load(f)
    for d in data["deals"]:
        if label in d.get("_label", ""):
            return d
    raise KeyError(f"No deal matching '{label}'")


@pytest.fixture(scope="module")
def us_bsl():
    return _load_deal("US BSL CLO")


# ---------------------------------------------------------------------------
# Return structure
# ---------------------------------------------------------------------------

class TestReturnStructure:

    def test_returns_dict(self, us_bsl):
        result = watchlist_check_workflow(us_bsl, actor="test")
        assert isinstance(result, dict)

    def test_has_required_keys(self, us_bsl):
        result = watchlist_check_workflow(us_bsl, actor="test")
        for key in ("deal_id", "items_checked", "triggered_count",
                    "alerts", "outputs_used", "audit_events", "is_mock", "error"):
            assert key in result

    def test_no_error_for_valid_deal(self, us_bsl):
        result = watchlist_check_workflow(us_bsl, actor="test")
        assert result["error"] is None

    def test_deal_id_correct(self, us_bsl):
        result = watchlist_check_workflow(us_bsl, actor="test")
        assert result["deal_id"] == us_bsl["deal_id"]

    def test_is_mock_true(self, us_bsl):
        result = watchlist_check_workflow(us_bsl, actor="test")
        assert result["is_mock"] is True


# ---------------------------------------------------------------------------
# Empty watchlist
# ---------------------------------------------------------------------------

class TestEmptyWatchlist:

    def test_no_alerts_with_empty_watchlist(self, us_bsl):
        result = watchlist_check_workflow(us_bsl, actor="test")
        assert result["alerts"] == []
        assert result["items_checked"] == 0
        assert result["triggered_count"] == 0

    def test_outputs_used_populated(self, us_bsl):
        result = watchlist_check_workflow(us_bsl, actor="test")
        assert "equity_irr" in result["outputs_used"]


# ---------------------------------------------------------------------------
# Triggered alerts
# ---------------------------------------------------------------------------

class TestTriggeredAlerts:

    def test_triggered_alert_returned(self, us_bsl):
        # Set threshold way above expected mock IRR so it triggers
        watchlist_service.add_item("equity_irr", "lt", 0.99, label="IRR always triggers")
        result = watchlist_check_workflow(us_bsl, actor="test")
        triggered = [a for a in result["alerts"] if a["triggered"]]
        assert len(triggered) >= 1

    def test_not_triggered_alert_returned(self, us_bsl):
        # Set threshold way below mock IRR so it does NOT trigger
        watchlist_service.add_item("equity_irr", "lt", 0.001, label="IRR never triggers")
        result = watchlist_check_workflow(us_bsl, actor="test")
        not_triggered = [a for a in result["alerts"] if not a["triggered"]]
        assert len(not_triggered) == 1

    def test_triggered_count_correct(self, us_bsl):
        watchlist_service.add_item("equity_irr", "lt", 0.99)  # will trigger
        watchlist_service.add_item("equity_irr", "lt", 0.001)  # won't trigger
        result = watchlist_check_workflow(us_bsl, actor="test")
        assert result["items_checked"] == 2
        assert result["triggered_count"] == 1

    def test_alert_entry_structure(self, us_bsl):
        watchlist_service.add_item("equity_irr", "lt", 0.99, label="test alert")
        result = watchlist_check_workflow(us_bsl, actor="test")
        alert = result["alerts"][0]
        for field in ("item_id", "label", "metric", "operator", "threshold",
                      "value", "triggered", "severity"):
            assert field in alert

    def test_alert_value_matches_output(self, us_bsl):
        watchlist_service.add_item("equity_irr", "lt", 0.99)
        result = watchlist_check_workflow(us_bsl, actor="test")
        alert = next(a for a in result["alerts"] if a["metric"] == "equity_irr")
        expected = result["outputs_used"]["equity_irr"]
        assert alert["value"] == pytest.approx(expected)

    def test_multiple_metrics_checked(self, us_bsl):
        watchlist_service.add_item("equity_irr", "lt", 0.99)
        watchlist_service.add_item("oc_cushion_aaa", "lt", 0.99)
        result = watchlist_check_workflow(us_bsl, actor="test")
        assert result["items_checked"] == 2

    def test_deal_specific_item_fires(self, us_bsl):
        watchlist_service.add_item(
            "equity_irr", "lt", 0.99, deal_id=us_bsl["deal_id"]
        )
        result = watchlist_check_workflow(us_bsl, actor="test")
        assert result["items_checked"] == 1

    def test_other_deal_item_not_checked(self, us_bsl):
        watchlist_service.add_item("equity_irr", "lt", 0.99, deal_id="other-deal")
        result = watchlist_check_workflow(us_bsl, actor="test")
        assert result["items_checked"] == 0


# ---------------------------------------------------------------------------
# Guard conditions
# ---------------------------------------------------------------------------

class TestGuardConditions:

    def test_invalid_deal_returns_error(self):
        bad = {"deal_id": "bad", "name": "x", "issuer": "y",
               "collateral": {"portfolio_size": 0, "diversity_score": 10, "ccc_bucket": 0.05},
               "liabilities": [{"tranche_id": "t1", "name": "AAA", "seniority": 1}]}
        result = watchlist_check_workflow(bad, actor="test")
        assert result["error"] is not None

    def test_invalid_deal_returns_empty_alerts(self):
        bad = {"deal_id": "bad2", "name": "x", "issuer": "y",
               "collateral": {"portfolio_size": 0, "diversity_score": 10, "ccc_bucket": 0.05},
               "liabilities": [{"tranche_id": "t1", "name": "AAA", "seniority": 1}]}
        result = watchlist_check_workflow(bad, actor="test")
        assert result["alerts"] == []


# ---------------------------------------------------------------------------
# Audit events
# ---------------------------------------------------------------------------

class TestAuditEvents:

    def test_audit_events_emitted(self, us_bsl):
        result = watchlist_check_workflow(us_bsl, actor="test")
        # Scenario audit events + watchlist.checked
        assert len(result["audit_events"]) >= 2

    def test_audit_events_are_strings(self, us_bsl):
        result = watchlist_check_workflow(us_bsl, actor="test")
        for ev in result["audit_events"]:
            assert isinstance(ev, str)
