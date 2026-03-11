"""
tests/test_api.py

Tests for the AI Deal Creator REST API (app/api/router.py).

Uses FastAPI's TestClient — no server process required.
All tests run against Phase 1 mock services.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient
from app.api.main import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _deal_payload(**overrides):
    payload = {
        "deal": {
            "deal_id": "api-deal-001",
            "name": "API Test CLO",
            "issuer": "API Issuer LLC",
            "region": "US",
            "currency": "USD",
            "manager": "API Manager",
        },
        "collateral": {
            "collateral_id": "api-coll-001",
            "pool_id": "pool-001",
            "asset_class": "broadly_syndicated_loans",
            "portfolio_size": 500_000_000,
            "was": 0.042,
            "warf": 2800,
            "wal": 5.2,
            "diversity_score": 62,
            "ccc_bucket": 0.055,
        },
        "tranches": [
            {"tranche_id": "t-aaa", "name": "AAA", "seniority": 1, "size_pct": 0.61, "coupon": "SOFR+145"},
            {"tranche_id": "t-eq",  "name": "Equity", "seniority": 2, "size_pct": 0.09},
        ],
        "market_assumptions": {
            "default_rate": 0.03,
            "recovery_rate": 0.65,
            "spread_shock_bps": 0.0,
        },
        "actor": "test",
    }
    payload.update(overrides)
    return payload


def _create_deal_and_run_scenario():
    """Helper: create deal then run scenario, return (deal_response, scenario_response)."""
    deal_resp = client.post("/deals", json=_deal_payload())
    deal_data = deal_resp.json()
    scenario_resp = client.post("/scenarios", json={
        "deal_input": deal_data["deal_input"],
        "scenario_name": "Baseline",
        "actor": "test",
    })
    return deal_data, scenario_resp.json()


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------

class TestHealth:

    def test_health_returns_200(self):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_health_status_ok(self):
        resp = client.get("/health")
        assert resp.json()["status"] == "ok"

    def test_health_mode_mock(self):
        resp = client.get("/health")
        assert resp.json()["mode"] == "mock"


# ---------------------------------------------------------------------------
# POST /deals
# ---------------------------------------------------------------------------

class TestCreateDeal:

    def test_returns_200(self):
        resp = client.post("/deals", json=_deal_payload())
        assert resp.status_code == 200

    def test_deal_id_in_response(self):
        resp = client.post("/deals", json=_deal_payload())
        assert resp.json()["deal_id"] == "api-deal-001"

    def test_tranche_count_in_response(self):
        resp = client.post("/deals", json=_deal_payload())
        assert resp.json()["tranche_count"] == 2

    def test_pool_id_in_response(self):
        resp = client.post("/deals", json=_deal_payload())
        assert resp.json()["pool_id"] == "pool-001"

    def test_deal_input_returned(self):
        resp = client.post("/deals", json=_deal_payload())
        data = resp.json()
        assert "deal_input" in data
        assert data["deal_input"]["deal_id"] == "api-deal-001"

    def test_deal_input_has_liabilities(self):
        resp = client.post("/deals", json=_deal_payload())
        deal_input = resp.json()["deal_input"]
        assert "liabilities" in deal_input
        assert len(deal_input["liabilities"]) == 2

    def test_pool_validation_failure_returns_422(self):
        payload = _deal_payload()
        payload["collateral"]["ccc_bucket"] = 0.10  # exceeds 7.5% limit
        resp = client.post("/deals", json=payload)
        assert resp.status_code == 422

    def test_missing_required_field_returns_422(self):
        payload = _deal_payload()
        del payload["deal"]["deal_id"]
        resp = client.post("/deals", json=payload)
        assert resp.status_code == 422

    def test_no_tranches_returns_422(self):
        payload = _deal_payload()
        payload["tranches"] = []
        resp = client.post("/deals", json=payload)
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /scenarios
# ---------------------------------------------------------------------------

class TestRunScenario:

    def test_returns_200(self):
        deal_data = client.post("/deals", json=_deal_payload()).json()
        resp = client.post("/scenarios", json={"deal_input": deal_data["deal_input"]})
        assert resp.status_code == 200

    def test_validation_passes(self):
        deal_data = client.post("/deals", json=_deal_payload()).json()
        resp = client.post("/scenarios", json={"deal_input": deal_data["deal_input"]})
        assert resp.json()["validation"]["valid"] is True

    def test_scenario_result_present(self):
        deal_data = client.post("/deals", json=_deal_payload()).json()
        resp = client.post("/scenarios", json={"deal_input": deal_data["deal_input"]})
        assert resp.json()["scenario_result"] is not None

    def test_is_mock_true(self):
        deal_data = client.post("/deals", json=_deal_payload()).json()
        resp = client.post("/scenarios", json={"deal_input": deal_data["deal_input"]})
        assert resp.json()["is_mock"] is True

    def test_scenario_name_propagated(self):
        deal_data = client.post("/deals", json=_deal_payload()).json()
        resp = client.post("/scenarios", json={
            "deal_input": deal_data["deal_input"],
            "scenario_name": "Stress Test",
        })
        assert resp.json()["scenario_request"]["name"] == "Stress Test"

    def test_audit_events_counted(self):
        deal_data = client.post("/deals", json=_deal_payload()).json()
        resp = client.post("/scenarios", json={"deal_input": deal_data["deal_input"]})
        assert resp.json()["audit_events_count"] >= 3

    def test_invalid_deal_input_returns_422(self):
        resp = client.post("/scenarios", json={
            "deal_input": {"deal_id": "bad", "liabilities": []}
        })
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /drafts/investor-summary
# ---------------------------------------------------------------------------

class TestInvestorSummary:

    @pytest.fixture
    def scenario_result(self):
        deal_data, scenario_data = _create_deal_and_run_scenario()
        return deal_data["deal_input"], scenario_data["scenario_result"]

    def test_returns_200(self, scenario_result):
        deal_input, sr = scenario_result
        resp = client.post("/drafts/investor-summary", json={
            "deal_input": deal_input,
            "scenario_result": sr,
        })
        assert resp.status_code == 200

    def test_draft_present(self, scenario_result):
        deal_input, sr = scenario_result
        resp = client.post("/drafts/investor-summary", json={
            "deal_input": deal_input,
            "scenario_result": sr,
        })
        assert resp.json()["draft"] is not None

    def test_approved_always_false(self, scenario_result):
        deal_input, sr = scenario_result
        resp = client.post("/drafts/investor-summary", json={
            "deal_input": deal_input,
            "scenario_result": sr,
        })
        assert resp.json()["approved"] is False

    def test_requires_approval_true(self, scenario_result):
        deal_input, sr = scenario_result
        resp = client.post("/drafts/investor-summary", json={
            "deal_input": deal_input,
            "scenario_result": sr,
        })
        assert resp.json()["requires_approval"] is True

    def test_draft_markdown_present(self, scenario_result):
        deal_input, sr = scenario_result
        resp = client.post("/drafts/investor-summary", json={
            "deal_input": deal_input,
            "scenario_result": sr,
        })
        assert isinstance(resp.json()["draft_markdown"], str)

    def test_missing_scenario_result_returns_422(self):
        deal_data = client.post("/deals", json=_deal_payload()).json()
        resp = client.post("/drafts/investor-summary", json={
            "deal_input": deal_data["deal_input"],
            "scenario_result": {},
        })
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /drafts/ic-memo
# ---------------------------------------------------------------------------

class TestIcMemo:

    @pytest.fixture
    def scenario_result(self):
        deal_data, scenario_data = _create_deal_and_run_scenario()
        return deal_data["deal_input"], scenario_data["scenario_result"]

    def test_returns_200(self, scenario_result):
        deal_input, sr = scenario_result
        resp = client.post("/drafts/ic-memo", json={
            "deal_input": deal_input,
            "scenario_result": sr,
        })
        assert resp.status_code == 200

    def test_draft_type_ic_memo(self, scenario_result):
        deal_input, sr = scenario_result
        resp = client.post("/drafts/ic-memo", json={
            "deal_input": deal_input,
            "scenario_result": sr,
        })
        assert resp.json()["draft"]["draft_type"] == "ic_memo"

    def test_approved_always_false(self, scenario_result):
        deal_input, sr = scenario_result
        resp = client.post("/drafts/ic-memo", json={
            "deal_input": deal_input,
            "scenario_result": sr,
        })
        assert resp.json()["approved"] is False


# ---------------------------------------------------------------------------
# POST /approvals/*
# ---------------------------------------------------------------------------

class TestApprovals:

    @pytest.fixture
    def draft(self):
        deal_data, scenario_data = _create_deal_and_run_scenario()
        resp = client.post("/drafts/investor-summary", json={
            "deal_input": deal_data["deal_input"],
            "scenario_result": scenario_data["scenario_result"],
        })
        return resp.json()["draft"]

    def test_request_approval_returns_pending(self, draft):
        resp = client.post("/approvals/request", json={
            "draft": draft,
            "requested_by": "analyst-1",
            "channel": "internal",
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "pending"

    def test_request_approval_has_draft_id(self, draft):
        resp = client.post("/approvals/request", json={
            "draft": draft,
            "requested_by": "analyst-1",
        })
        assert resp.json()["draft_id"] == draft["draft_id"]

    def test_approve_transitions_to_approved(self, draft):
        pending = client.post("/approvals/request", json={
            "draft": draft, "requested_by": "analyst-1",
        }).json()
        approved = client.post("/approvals/approve", json={
            "approval_record": pending,
            "approver": "clo-head",
        })
        assert approved.status_code == 200
        assert approved.json()["status"] == "approved"

    def test_reject_transitions_to_rejected(self, draft):
        pending = client.post("/approvals/request", json={
            "draft": draft, "requested_by": "analyst-1",
        }).json()
        rejected = client.post("/approvals/reject", json={
            "approval_record": pending,
            "approver": "clo-head",
            "rejection_reason": "Needs revision",
        })
        assert rejected.status_code == 200
        assert rejected.json()["status"] == "rejected"

    def test_apply_approval_sets_approved_true(self, draft):
        pending = client.post("/approvals/request", json={
            "draft": draft, "requested_by": "analyst-1",
        }).json()
        approved_record = client.post("/approvals/approve", json={
            "approval_record": pending, "approver": "clo-head",
        }).json()
        approved_draft = client.post("/approvals/apply", json={
            "draft": draft, "approval_record": approved_record,
        })
        assert approved_draft.status_code == 200
        assert approved_draft.json()["approved"] is True

    def test_invalid_channel_returns_422(self, draft):
        resp = client.post("/approvals/request", json={
            "draft": draft,
            "requested_by": "analyst-1",
            "channel": "investor_portal",
        })
        assert resp.status_code == 422

    def test_approve_already_approved_returns_422(self, draft):
        pending = client.post("/approvals/request", json={
            "draft": draft, "requested_by": "analyst-1",
        }).json()
        approved = client.post("/approvals/approve", json={
            "approval_record": pending, "approver": "clo-head",
        }).json()
        resp = client.post("/approvals/approve", json={
            "approval_record": approved, "approver": "someone-else",
        })
        assert resp.status_code == 422

    def test_apply_wrong_draft_id_returns_422(self, draft):
        other_draft = {**draft, "draft_id": "draft-other-999"}
        pending = client.post("/approvals/request", json={
            "draft": draft, "requested_by": "analyst-1",
        }).json()
        approved_record = client.post("/approvals/approve", json={
            "approval_record": pending, "approver": "clo-head",
        }).json()
        resp = client.post("/approvals/apply", json={
            "draft": other_draft, "approval_record": approved_record,
        })
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /publish-check
# ---------------------------------------------------------------------------

class TestPublishCheck:

    def test_mock_draft_is_blocked(self):
        deal_data, scenario_data = _create_deal_and_run_scenario()
        draft_resp = client.post("/drafts/investor-summary", json={
            "deal_input": deal_data["deal_input"],
            "scenario_result": scenario_data["scenario_result"],
        }).json()
        draft = draft_resp["draft"]

        pending = client.post("/approvals/request", json={
            "draft": draft, "requested_by": "analyst-1",
        }).json()
        approved_record = client.post("/approvals/approve", json={
            "approval_record": pending, "approver": "clo-head",
        }).json()
        approved_draft = client.post("/approvals/apply", json={
            "draft": draft, "approval_record": approved_record,
        }).json()

        resp = client.post("/publish-check", json={
            "draft": approved_draft,
            "approval_record": approved_record,
            "target_channel": "internal",
        })
        assert resp.status_code == 200
        assert resp.json()["recommendation"] == "BLOCKED"

    def test_non_mock_approved_passes(self):
        clean_draft = {
            "draft_id": "draft-api-clean",
            "deal_id": "api-deal-001",
            "draft_type": "investor_summary",
            "approved": False,
            "is_mock": False,
            "sections": [],
        }
        pending = client.post("/approvals/request", json={
            "draft": clean_draft, "requested_by": "analyst-1",
        }).json()
        approved_record = client.post("/approvals/approve", json={
            "approval_record": pending, "approver": "clo-head",
        }).json()
        approved_draft = client.post("/approvals/apply", json={
            "draft": clean_draft, "approval_record": approved_record,
        }).json()

        resp = client.post("/publish-check", json={
            "draft": approved_draft,
            "approval_record": approved_record,
            "target_channel": "internal",
        })
        assert resp.status_code == 200
        assert resp.json()["recommendation"] == "APPROVED_TO_PUBLISH"

    def test_unapproved_draft_is_blocked(self):
        resp = client.post("/publish-check", json={
            "draft": {
                "draft_id": "d1", "deal_id": "x",
                "draft_type": "investor_summary",
                "approved": False, "is_mock": False, "sections": [],
            },
            "target_channel": "internal",
        })
        assert resp.json()["recommendation"] == "BLOCKED"

    def test_response_has_checks_run(self):
        resp = client.post("/publish-check", json={
            "draft": {
                "draft_id": "d1", "deal_id": "x",
                "draft_type": "investor_summary",
                "approved": False, "is_mock": False, "sections": [],
            },
        })
        assert "checks_run" in resp.json()
        assert len(resp.json()["checks_run"]) == 7


# ---------------------------------------------------------------------------
# POST /scenarios/batch
# ---------------------------------------------------------------------------

def _batch_deal_input():
    """Minimal valid deal_input dict for batch/sensitivity tests."""
    return {
        "deal_id": "batch-deal-001",
        "name": "Batch Test CLO",
        "issuer": "Batch Issuer LLC",
        "collateral": {
            "pool_id": "pool-batch-001",
            "asset_class": "broadly_syndicated_loans",
            "portfolio_size": 500_000_000,
            "was": 0.042,
            "wal": 5.2,
            "diversity_score": 62,
            "ccc_bucket": 0.055,
        },
        "liabilities": [
            {"tranche_id": "t-aaa", "name": "AAA",    "seniority": 1, "size_pct": 0.61, "coupon": "SOFR+145"},
            {"tranche_id": "t-aa",  "name": "AA",     "seniority": 2, "size_pct": 0.08, "coupon": "SOFR+200"},
            {"tranche_id": "t-eq",  "name": "Equity", "seniority": 3, "size_pct": 0.09},
        ],
        "market_assumptions": {"default_rate": 0.03, "recovery_rate": 0.65, "spread_shock_bps": 0},
    }


class TestBatchScenarios:

    def test_returns_200(self):
        resp = client.post("/scenarios/batch", json={
            "deal_input": _batch_deal_input(),
            "scenarios": [
                {"name": "Base",   "type": "base",   "parameters": {"default_rate": 0.03, "recovery_rate": 0.65, "spread_shock_bps": 0}},
                {"name": "Stress", "type": "stress",  "parameters": {"default_rate": 0.07, "recovery_rate": 0.40, "spread_shock_bps": 100}},
            ],
        })
        assert resp.status_code == 200

    def test_scenarios_run_count(self):
        resp = client.post("/scenarios/batch", json={
            "deal_input": _batch_deal_input(),
            "scenarios": [
                {"name": "A", "parameters": {"default_rate": 0.03, "recovery_rate": 0.65, "spread_shock_bps": 0}},
                {"name": "B", "parameters": {"default_rate": 0.06, "recovery_rate": 0.45, "spread_shock_bps": 50}},
            ],
        })
        assert resp.json()["scenarios_run"] == 2

    def test_comparison_table_present(self):
        resp = client.post("/scenarios/batch", json={
            "deal_input": _batch_deal_input(),
            "scenarios": [
                {"name": "Base",   "parameters": {"default_rate": 0.03, "recovery_rate": 0.65, "spread_shock_bps": 0}},
                {"name": "Stress", "parameters": {"default_rate": 0.07, "recovery_rate": 0.40, "spread_shock_bps": 75}},
            ],
        })
        data = resp.json()
        assert "comparison_table" in data
        assert len(data["comparison_table"]) > 0

    def test_equity_irr_best_worst_annotated(self):
        resp = client.post("/scenarios/batch", json={
            "deal_input": _batch_deal_input(),
            "scenarios": [
                {"name": "Base",   "parameters": {"default_rate": 0.03, "recovery_rate": 0.65, "spread_shock_bps": 0}},
                {"name": "Stress", "parameters": {"default_rate": 0.07, "recovery_rate": 0.40, "spread_shock_bps": 75}},
            ],
        })
        table = resp.json()["comparison_table"]
        irr_row = next(r for r in table if r["metric"] == "equity_irr")
        assert irr_row["best"] == "Base"
        assert irr_row["worst"] == "Stress"

    def test_is_mock_in_response(self):
        resp = client.post("/scenarios/batch", json={
            "deal_input": _batch_deal_input(),
            "scenarios": [{"name": "Base", "parameters": {"default_rate": 0.03, "recovery_rate": 0.65, "spread_shock_bps": 0}}],
        })
        assert resp.json()["is_mock"] is True

    def test_invalid_deal_returns_422(self):
        bad_deal = dict(_batch_deal_input())
        bad_deal["deal_id"] = ""
        resp = client.post("/scenarios/batch", json={
            "deal_input": bad_deal,
            "scenarios": [{"name": "Base", "parameters": {"default_rate": 0.03, "recovery_rate": 0.65, "spread_shock_bps": 0}}],
        })
        assert resp.status_code == 422

    def test_missing_scenarios_returns_422(self):
        resp = client.post("/scenarios/batch", json={
            "deal_input": _batch_deal_input(),
            "scenarios": [],
        })
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /scenarios/sensitivity
# ---------------------------------------------------------------------------

class TestSensitivityAnalysis:

    def test_returns_200(self):
        resp = client.post("/scenarios/sensitivity", json={
            "deal_input": _batch_deal_input(),
            "parameter": "default_rate",
            "values": [0.02, 0.04, 0.06, 0.08],
        })
        assert resp.status_code == 200

    def test_series_length_matches_values(self):
        values = [0.02, 0.04, 0.06, 0.08]
        resp = client.post("/scenarios/sensitivity", json={
            "deal_input": _batch_deal_input(),
            "parameter": "default_rate",
            "values": values,
        })
        assert len(resp.json()["series"]) == len(values)

    def test_parameter_name_echoed(self):
        resp = client.post("/scenarios/sensitivity", json={
            "deal_input": _batch_deal_input(),
            "parameter": "recovery_rate",
            "values": [0.30, 0.50, 0.70],
        })
        assert resp.json()["parameter"] == "recovery_rate"

    def test_breakeven_keys_present(self):
        resp = client.post("/scenarios/sensitivity", json={
            "deal_input": _batch_deal_input(),
            "parameter": "default_rate",
            "values": [0.01, 0.05, 0.10, 0.15],
        })
        be = resp.json()["breakeven"]
        assert "equity_irr_zero" in be
        assert "scenario_npv_zero" in be

    def test_irr_breakeven_found_in_wide_sweep(self):
        """Wide sweep should detect IRR=0 crossover."""
        values = [round(i * 0.01, 2) for i in range(1, 16)]
        resp = client.post("/scenarios/sensitivity", json={
            "deal_input": _batch_deal_input(),
            "parameter": "default_rate",
            "values": values,
        })
        be = resp.json()["breakeven"]["equity_irr_zero"]
        assert be is not None
        assert 0.01 <= be <= 0.15

    def test_is_mock_in_response(self):
        resp = client.post("/scenarios/sensitivity", json={
            "deal_input": _batch_deal_input(),
            "parameter": "default_rate",
            "values": [0.03, 0.06],
        })
        assert resp.json()["is_mock"] is True

    def test_invalid_deal_returns_422(self):
        bad_deal = dict(_batch_deal_input())
        bad_deal["deal_id"] = ""
        resp = client.post("/scenarios/sensitivity", json={
            "deal_input": bad_deal,
            "parameter": "default_rate",
            "values": [0.03],
        })
        assert resp.status_code == 422

    def test_empty_values_returns_422(self):
        resp = client.post("/scenarios/sensitivity", json={
            "deal_input": _batch_deal_input(),
            "parameter": "default_rate",
            "values": [],
        })
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /analyze
# ---------------------------------------------------------------------------

class TestAnalyze:

    def test_returns_200(self):
        resp = client.post("/analyze", json={
            "deal_input": _batch_deal_input(),
            "run_sensitivity": False,
        })
        assert resp.status_code == 200

    def test_analysis_id_present(self):
        resp = client.post("/analyze", json={
            "deal_input": _batch_deal_input(),
            "run_sensitivity": False,
        })
        assert resp.json()["analysis_id"].startswith("analytics-")

    def test_four_scenarios_run(self):
        resp = client.post("/analyze", json={
            "deal_input": _batch_deal_input(),
            "run_sensitivity": False,
        })
        assert resp.json()["scenarios_run"] == 4

    def test_key_metrics_present(self):
        resp = client.post("/analyze", json={
            "deal_input": _batch_deal_input(),
            "run_sensitivity": False,
        })
        km = resp.json()["key_metrics"]
        assert "base_equity_irr" in km
        assert isinstance(km["base_equity_irr"], float)

    def test_analytics_report_is_string(self):
        resp = client.post("/analyze", json={
            "deal_input": _batch_deal_input(),
            "run_sensitivity": False,
        })
        report = resp.json()["analytics_report"]
        assert isinstance(report, str)
        assert "DEMO" in report

    def test_summary_table_has_rows(self):
        resp = client.post("/analyze", json={
            "deal_input": _batch_deal_input(),
            "run_sensitivity": False,
        })
        assert len(resp.json()["summary_table"]) > 0

    def test_is_mock_true(self):
        resp = client.post("/analyze", json={
            "deal_input": _batch_deal_input(),
            "run_sensitivity": False,
        })
        assert resp.json()["is_mock"] is True

    def test_invalid_deal_returns_422(self):
        bad = dict(_batch_deal_input())
        bad["deal_id"] = ""
        resp = client.post("/analyze", json={
            "deal_input": bad,
            "run_sensitivity": False,
        })
        assert resp.status_code == 422

    def test_custom_scenarios_used(self):
        resp = client.post("/analyze", json={
            "deal_input": _batch_deal_input(),
            "custom_scenarios": [
                {"name": "Custom Base", "type": "base",
                 "parameters": {"default_rate": 0.02, "recovery_rate": 0.70, "spread_shock_bps": 0}},
            ],
            "run_sensitivity": False,
        })
        assert resp.json()["scenarios_run"] == 1


# ---------------------------------------------------------------------------
# POST /optimize
# ---------------------------------------------------------------------------

class TestOptimize:

    def _opt_payload(self, **overrides):
        payload = {
            "deal_input": _batch_deal_input(),
            "aaa_min": 0.58,
            "aaa_max": 0.68,
            "aaa_step": 0.02,
        }
        payload.update(overrides)
        return payload

    def test_returns_200(self):
        resp = client.post("/optimize", json=self._opt_payload())
        assert resp.status_code == 200

    def test_optimization_id_present(self):
        resp = client.post("/optimize", json=self._opt_payload())
        assert resp.json()["optimization_id"].startswith("opt-")

    def test_candidates_tested_count(self):
        resp = client.post("/optimize", json=self._opt_payload())
        # aaa_min=0.58, aaa_max=0.68, step=0.02 → 6 candidates
        assert resp.json()["candidates_tested"] == 6

    def test_optimal_is_present(self):
        resp = client.post("/optimize", json=self._opt_payload())
        assert resp.json()["optimal"] is not None

    def test_optimal_has_equity_irr(self):
        resp = client.post("/optimize", json=self._opt_payload())
        assert "equity_irr" in resp.json()["optimal"]
        assert isinstance(resp.json()["optimal"]["equity_irr"], float)

    def test_feasibility_table_returned(self):
        resp = client.post("/optimize", json=self._opt_payload())
        assert len(resp.json()["feasibility_table"]) == 6

    def test_frontier_is_list(self):
        resp = client.post("/optimize", json=self._opt_payload())
        assert isinstance(resp.json()["frontier"], list)

    def test_is_mock_true(self):
        resp = client.post("/optimize", json=self._opt_payload())
        assert resp.json()["is_mock"] is True

    def test_impossible_oc_floor_returns_none_optimal(self):
        resp = client.post("/optimize", json=self._opt_payload(oc_floor=5.0))
        data = resp.json()
        assert data["optimal"] is None
        assert data["infeasible_reason"] is not None

    def test_invalid_deal_returns_422(self):
        bad = dict(_batch_deal_input())
        bad["deal_id"] = ""
        resp = client.post("/optimize", json={"deal_input": bad, "aaa_min": 0.60, "aaa_max": 0.65, "aaa_step": 0.025})
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /benchmarks/compare
# ---------------------------------------------------------------------------

_BASE_OUTPUTS = {
    "equity_irr":     0.115,
    "aaa_size_pct":   0.630,
    "oc_cushion_aaa": 0.195,
    "ic_cushion_aaa": 0.700,
    "was":            0.042,
    "wac":            0.095,
    "equity_wal":     5.0,
    "scenario_npv":   -2_000_000,
}


class TestBenchmarkCompare:

    def test_returns_200(self):
        resp = client.post("/benchmarks/compare", json={
            "deal_input": _batch_deal_input(),
            "scenario_outputs": _BASE_OUTPUTS,
            "vintage": 2024,
            "region": "US",
        })
        assert resp.status_code == 200

    def test_comparison_id_present(self):
        resp = client.post("/benchmarks/compare", json={
            "deal_input": _batch_deal_input(),
            "scenario_outputs": _BASE_OUTPUTS,
            "vintage": 2024,
            "region": "US",
        })
        assert resp.json()["comparison_id"].startswith("bench-")

    def test_overall_position_valid(self):
        resp = client.post("/benchmarks/compare", json={
            "deal_input": _batch_deal_input(),
            "scenario_outputs": _BASE_OUTPUTS,
            "vintage": 2024,
            "region": "US",
        })
        assert resp.json()["overall_position"] in ("strong", "median", "weak", "mixed")

    def test_metric_scores_returned(self):
        resp = client.post("/benchmarks/compare", json={
            "deal_input": _batch_deal_input(),
            "scenario_outputs": _BASE_OUTPUTS,
            "vintage": 2024,
        })
        assert len(resp.json()["metric_scores"]) > 0

    def test_report_contains_demo_tag(self):
        resp = client.post("/benchmarks/compare", json={
            "deal_input": _batch_deal_input(),
            "scenario_outputs": _BASE_OUTPUTS,
            "vintage": 2024,
        })
        assert "DEMO" in resp.json()["comparison_report"]

    def test_is_mock_true(self):
        resp = client.post("/benchmarks/compare", json={
            "deal_input": _batch_deal_input(),
            "scenario_outputs": _BASE_OUTPUTS,
            "vintage": 2024,
        })
        assert resp.json()["is_mock"] is True

    def test_unknown_vintage_returns_422(self):
        resp = client.post("/benchmarks/compare", json={
            "deal_input": _batch_deal_input(),
            "scenario_outputs": _BASE_OUTPUTS,
            "vintage": 1990,
            "region": "US",
        })
        assert resp.status_code == 422

    def test_above_median_and_below_median_counts(self):
        resp = client.post("/benchmarks/compare", json={
            "deal_input": _batch_deal_input(),
            "scenario_outputs": _BASE_OUTPUTS,
            "vintage": 2024,
        })
        data = resp.json()
        assert "above_median_count" in data
        assert "below_median_count" in data
        assert data["above_median_count"] + data["below_median_count"] <= len(data["metric_scores"])


# ---------------------------------------------------------------------------
# POST /pipeline
# ---------------------------------------------------------------------------

class TestPipeline:

    def test_returns_200(self):
        resp = client.post("/pipeline", json={
            "deal_input": _batch_deal_input(),
            "run_optimizer": True,
            "run_benchmark": True,
            "run_draft": True,
            "optimizer_kwargs": {"aaa_min": 0.60, "aaa_max": 0.63, "aaa_step": 0.015},
        })
        assert resp.status_code == 200

    def test_pipeline_id_returned(self):
        resp = client.post("/pipeline", json={
            "deal_input": _batch_deal_input(),
            "run_optimizer": False, "run_benchmark": False, "run_draft": False,
        })
        assert resp.json()["pipeline_id"].startswith("pipeline-")

    def test_analytics_stage_present(self):
        resp = client.post("/pipeline", json={
            "deal_input": _batch_deal_input(),
            "run_optimizer": False, "run_benchmark": False, "run_draft": False,
        })
        assert resp.json()["stages"]["analytics"] is not None

    def test_optimizer_stage_present_when_enabled(self):
        resp = client.post("/pipeline", json={
            "deal_input": _batch_deal_input(),
            "run_optimizer": True, "run_benchmark": False, "run_draft": False,
            "optimizer_kwargs": {"aaa_min": 0.60, "aaa_max": 0.62, "aaa_step": 0.01},
        })
        assert resp.json()["stages"]["optimizer"] is not None

    def test_optimizer_stage_null_when_disabled(self):
        resp = client.post("/pipeline", json={
            "deal_input": _batch_deal_input(),
            "run_optimizer": False, "run_benchmark": False, "run_draft": False,
        })
        assert resp.json()["stages"]["optimizer"] is None

    def test_benchmark_stage_present_when_enabled(self):
        resp = client.post("/pipeline", json={
            "deal_input": _batch_deal_input(),
            "run_optimizer": False, "run_benchmark": True, "run_draft": False,
        })
        assert resp.json()["stages"]["benchmark"] is not None

    def test_pipeline_summary_non_empty(self):
        resp = client.post("/pipeline", json={
            "deal_input": _batch_deal_input(),
            "run_optimizer": False, "run_benchmark": False, "run_draft": False,
        })
        assert len(resp.json()["pipeline_summary"]) > 50

    def test_is_mock_true(self):
        resp = client.post("/pipeline", json={
            "deal_input": _batch_deal_input(),
            "run_optimizer": False, "run_benchmark": False, "run_draft": False,
        })
        assert resp.json()["is_mock"] is True

    def test_audit_events_count_positive(self):
        resp = client.post("/pipeline", json={
            "deal_input": _batch_deal_input(),
            "run_optimizer": False, "run_benchmark": False, "run_draft": False,
        })
        assert resp.json()["audit_events_count"] >= 3

    def test_invalid_deal_returns_error_in_body(self):
        resp = client.post("/pipeline", json={
            "deal_input": {"deal_id": "", "name": "x", "issuer": "y",
                           "collateral": {"portfolio_size": 100_000_000, "diversity_score": 45, "ccc_bucket": 0.05},
                           "liabilities": [{"tranche_id": "t1", "name": "AAA", "seniority": 1, "size_pct": 0.61}]},
        })
        # Pipeline handles invalid deals gracefully: 200 with error field populated
        assert resp.status_code == 200
        assert resp.json().get("error") is not None


# ---------------------------------------------------------------------------
# POST /compare
# ---------------------------------------------------------------------------

class TestCompare:

    def _v1_deal(self):
        return _batch_deal_input()

    def _v2_deal(self):
        d = _batch_deal_input()
        d["deal_id"] = "batch-deal-002"
        d["collateral"]["portfolio_size"] = 600_000_000
        return d

    def test_returns_200_with_two_deals(self):
        resp = client.post("/compare", json={
            "v1_deal": self._v1_deal(),
            "v2_deal": self._v2_deal(),
        })
        assert resp.status_code == 200

    def test_deal_comparison_present(self):
        resp = client.post("/compare", json={
            "v1_deal": self._v1_deal(),
            "v2_deal": self._v2_deal(),
        })
        assert resp.json()["deal_comparison"] is not None

    def test_summary_non_empty(self):
        resp = client.post("/compare", json={
            "v1_deal": self._v1_deal(),
            "v2_deal": self._v2_deal(),
        })
        assert resp.json().get("summary") is not None
        assert len(resp.json()["summary"]) > 10

    def test_audit_events_count_positive(self):
        resp = client.post("/compare", json={
            "v1_deal": self._v1_deal(),
            "v2_deal": self._v2_deal(),
        })
        assert resp.json()["audit_events_count"] >= 1

    def test_missing_v2_returns_422(self):
        resp = client.post("/compare", json={
            "v1_deal": self._v1_deal(),
        })
        assert resp.status_code == 422

    def test_compare_with_results(self):
        # Run a scenario on v1 first, use result for comparison
        scen_resp = client.post("/scenarios", json={
            "deal_input": self._v1_deal(),
            "scenario_name": "Base",
            "scenario_type": "base",
        })
        v1_result = scen_resp.json().get("scenario_result") or {}

        resp = client.post("/compare", json={
            "v1_deal": self._v1_deal(),
            "v2_deal": self._v2_deal(),
            "v1_result": v1_result,
        })
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# GET /deals  /  GET /deals/{deal_id}  /  DELETE /deals/{deal_id}
# ---------------------------------------------------------------------------

class TestDealRegistry:
    """Tests for deal registry endpoints.

    NOTE: the registry is in-memory and shared across the TestClient session.
    Each test that needs a clean slate calls POST /deals first to ensure
    the target deal_id exists, then cleans up via DELETE.
    """

    def _create_deal(self, deal_id="reg-api-001", name="Registry API CLO"):
        return client.post("/deals", json={
            "deal": {
                "deal_id": deal_id,
                "name": name,
                "issuer": "Registry Issuer LLC",
                "region": "US",
                "currency": "USD",
            },
            "collateral": {
                "collateral_id": f"coll-{deal_id}",
                "pool_id": f"pool-{deal_id}",
                "asset_class": "broadly_syndicated_loans",
                "portfolio_size": 500_000_000,
                "was": 0.042,
                "warf": 2800.0,
                "wal": 5.2,
                "diversity_score": 60,
                "ccc_bucket": 0.05,
            },
            "tranches": [
                {"tranche_id": "t-aaa", "name": "AAA", "seniority": 1, "size_pct": 0.62},
                {"tranche_id": "t-eq",  "name": "Equity", "seniority": 2, "size_pct": 0.10},
            ],
        })

    def test_list_deals_returns_200(self):
        resp = client.get("/deals")
        assert resp.status_code == 200

    def test_list_deals_has_total_and_deals(self):
        resp = client.get("/deals")
        data = resp.json()
        assert "total" in data
        assert "deals" in data
        assert isinstance(data["deals"], list)

    def test_create_deal_auto_registers(self):
        self._create_deal("reg-auto-001")
        resp = client.get("/deals")
        ids = [d["deal_id"] for d in resp.json()["deals"]]
        assert "reg-auto-001" in ids
        client.delete("/deals/reg-auto-001")

    def test_get_deal_returns_200(self):
        self._create_deal("reg-get-001")
        resp = client.get("/deals/reg-get-001")
        assert resp.status_code == 200
        client.delete("/deals/reg-get-001")

    def test_get_deal_has_deal_id(self):
        self._create_deal("reg-get-002")
        data = client.get("/deals/reg-get-002").json()
        assert data["deal_id"] == "reg-get-002"
        client.delete("/deals/reg-get-002")

    def test_get_deal_has_deal_input(self):
        self._create_deal("reg-get-003")
        data = client.get("/deals/reg-get-003").json()
        assert "deal_input" in data
        client.delete("/deals/reg-get-003")

    def test_get_deal_pipeline_count_zero_initially(self):
        self._create_deal("reg-get-004")
        data = client.get("/deals/reg-get-004").json()
        assert data["pipeline_count"] == 0
        client.delete("/deals/reg-get-004")

    def test_get_unknown_deal_returns_404(self):
        resp = client.get("/deals/deal-does-not-exist-xyz")
        assert resp.status_code == 404

    def test_delete_deal_returns_200(self):
        self._create_deal("reg-del-001")
        resp = client.delete("/deals/reg-del-001")
        assert resp.status_code == 200

    def test_delete_deal_deleted_true(self):
        self._create_deal("reg-del-002")
        data = client.delete("/deals/reg-del-002").json()
        assert data["deleted"] is True

    def test_delete_unknown_deal_deleted_false(self):
        data = client.delete("/deals/deal-never-existed-xyz").json()
        assert data["deleted"] is False

    def test_delete_removes_from_list(self):
        self._create_deal("reg-del-003")
        client.delete("/deals/reg-del-003")
        resp = client.get("/deals/reg-del-003")
        assert resp.status_code == 404

    def test_list_total_increments_on_create(self):
        before = client.get("/deals").json()["total"]
        self._create_deal(f"reg-count-{before}")
        after = client.get("/deals").json()["total"]
        assert after == before + 1
        client.delete(f"/deals/reg-count-{before}")

    def test_deal_summary_has_portfolio_size(self):
        self._create_deal("reg-size-001")
        data = client.get("/deals/reg-size-001").json()
        assert data["portfolio_size"] == 500_000_000
        client.delete("/deals/reg-size-001")

    def test_deal_summary_has_tranche_count(self):
        self._create_deal("reg-tc-001")
        data = client.get("/deals/reg-tc-001").json()
        assert data["tranche_count"] == 2
        client.delete("/deals/reg-tc-001")


# ---------------------------------------------------------------------------
# GET /scenarios/templates  /  POST /scenarios/from-template
# ---------------------------------------------------------------------------

class TestScenarioTemplates:

    def test_list_templates_returns_200(self):
        assert client.get("/scenarios/templates").status_code == 200

    def test_list_templates_has_total(self):
        data = client.get("/scenarios/templates").json()
        assert "total" in data
        assert data["total"] >= 9

    def test_list_templates_has_templates_list(self):
        data = client.get("/scenarios/templates").json()
        assert isinstance(data["templates"], list)

    def test_filter_by_stress_type(self):
        data = client.get("/scenarios/templates?scenario_type=stress").json()
        assert all(t["scenario_type"] == "stress" for t in data["templates"])

    def test_filter_by_regulatory_type(self):
        data = client.get("/scenarios/templates?scenario_type=regulatory").json()
        assert all(t["scenario_type"] == "regulatory" for t in data["templates"])

    def test_filter_by_historical_tag(self):
        data = client.get("/scenarios/templates?tag=historical").json()
        ids = {t["template_id"] for t in data["templates"]}
        assert "gfc-2008" in ids

    def test_template_has_parameters(self):
        data = client.get("/scenarios/templates").json()
        for t in data["templates"]:
            assert "parameters" in t
            assert "default_rate" in t["parameters"]

    def test_run_from_template_base_returns_200(self):
        resp = client.post("/scenarios/from-template", json={
            "deal_input": _batch_deal_input(),
            "template_id": "base",
        })
        assert resp.status_code == 200

    def test_run_from_template_gfc_returns_200(self):
        resp = client.post("/scenarios/from-template", json={
            "deal_input": _batch_deal_input(),
            "template_id": "gfc-2008",
        })
        assert resp.status_code == 200

    def test_run_from_template_has_scenario_result(self):
        resp = client.post("/scenarios/from-template", json={
            "deal_input": _batch_deal_input(),
            "template_id": "stress",
        })
        data = resp.json()
        assert data["scenario_result"] is not None

    def test_run_from_template_has_parameters_used(self):
        resp = client.post("/scenarios/from-template", json={
            "deal_input": _batch_deal_input(),
            "template_id": "base",
        })
        data = resp.json()
        assert "parameters_used" in data
        assert "default_rate" in data["parameters_used"]

    def test_run_from_template_with_overrides(self):
        resp = client.post("/scenarios/from-template", json={
            "deal_input": _batch_deal_input(),
            "template_id": "base",
            "parameter_overrides": {"spread_shock_bps": 100.0},
        })
        data = resp.json()
        assert data["parameters_used"]["spread_shock_bps"] == 100.0

    def test_run_from_unknown_template_returns_404(self):
        resp = client.post("/scenarios/from-template", json={
            "deal_input": _batch_deal_input(),
            "template_id": "does-not-exist",
        })
        assert resp.status_code == 404

    def test_run_from_template_template_name_in_response(self):
        resp = client.post("/scenarios/from-template", json={
            "deal_input": _batch_deal_input(),
            "template_id": "gfc-2008",
        })
        data = resp.json()
        assert data["template_name"] == "GFC 2008"

    def test_run_from_template_is_mock_true(self):
        resp = client.post("/scenarios/from-template", json={
            "deal_input": _batch_deal_input(),
            "template_id": "base",
        })
        assert resp.json()["is_mock"] is True


# ---------------------------------------------------------------------------
# POST /scenarios/template-suite
# ---------------------------------------------------------------------------

class TestTemplateSuite:

    def test_returns_200_stress_only(self):
        resp = client.post("/scenarios/template-suite", json={
            "deal_input": _batch_deal_input(),
            "scenario_type": "stress",
        })
        assert resp.status_code == 200

    def test_templates_run_positive(self):
        resp = client.post("/scenarios/template-suite", json={
            "deal_input": _batch_deal_input(),
            "scenario_type": "stress",
        })
        assert resp.json()["templates_run"] >= 4

    def test_results_list_non_empty(self):
        resp = client.post("/scenarios/template-suite", json={
            "deal_input": _batch_deal_input(),
            "scenario_type": "stress",
        })
        assert len(resp.json()["results"]) >= 4

    def test_comparison_table_non_empty(self):
        resp = client.post("/scenarios/template-suite", json={
            "deal_input": _batch_deal_input(),
            "scenario_type": "stress",
        })
        assert len(resp.json()["comparison_table"]) > 0

    def test_explicit_template_ids(self):
        resp = client.post("/scenarios/template-suite", json={
            "deal_input": _batch_deal_input(),
            "template_ids": ["base", "gfc-2008"],
        })
        data = resp.json()
        assert data["templates_run"] == 2
        ids = {r["template_id"] for r in data["results"]}
        assert ids == {"base", "gfc-2008"}

    def test_tag_filter_historical(self):
        resp = client.post("/scenarios/template-suite", json={
            "deal_input": _batch_deal_input(),
            "tag": "historical",
        })
        data = resp.json()
        ids = {r["template_id"] for r in data["results"]}
        assert "gfc-2008" in ids

    def test_invalid_filter_returns_422(self):
        resp = client.post("/scenarios/template-suite", json={
            "deal_input": _batch_deal_input(),
            "scenario_type": "nonexistent-type",
        })
        assert resp.status_code == 422

    def test_is_mock_true(self):
        resp = client.post("/scenarios/template-suite", json={
            "deal_input": _batch_deal_input(),
            "template_ids": ["base"],
        })
        assert resp.json()["is_mock"] is True

    def test_audit_events_count_positive(self):
        resp = client.post("/scenarios/template-suite", json={
            "deal_input": _batch_deal_input(),
            "template_ids": ["base", "stress"],
        })
        assert resp.json()["audit_events_count"] >= 3


# ---------------------------------------------------------------------------
# POST /portfolio/analyze
# ---------------------------------------------------------------------------

class TestPortfolioAnalyze:

    def test_200_with_two_deals(self):
        resp = client.post("/portfolio/analyze", json={
            "deal_inputs": [_batch_deal_input(), _batch_deal_input()],
        })
        assert resp.status_code == 200

    def test_response_has_required_fields(self):
        resp = client.post("/portfolio/analyze", json={
            "deal_inputs": [_batch_deal_input()],
        })
        data = resp.json()
        for key in ("portfolio_id", "analysed_at", "deal_count", "deals",
                    "aggregate", "rankings", "concentration",
                    "portfolio_report", "audit_events_count", "is_mock", "error"):
            assert key in data

    def test_deal_count_matches_input(self):
        resp = client.post("/portfolio/analyze", json={
            "deal_inputs": [_batch_deal_input(), _batch_deal_input()],
        })
        assert resp.json()["deal_count"] == 2

    def test_is_mock_true(self):
        resp = client.post("/portfolio/analyze", json={
            "deal_inputs": [_batch_deal_input()],
        })
        assert resp.json()["is_mock"] is True

    def test_aggregate_has_avg_irr(self):
        resp = client.post("/portfolio/analyze", json={
            "deal_inputs": [_batch_deal_input(), _batch_deal_input()],
        })
        assert "avg_equity_irr" in resp.json()["aggregate"]

    def test_rankings_has_equity_irr(self):
        resp = client.post("/portfolio/analyze", json={
            "deal_inputs": [_batch_deal_input(), _batch_deal_input()],
        })
        assert "equity_irr" in resp.json()["rankings"]

    def test_concentration_has_by_region(self):
        resp = client.post("/portfolio/analyze", json={
            "deal_inputs": [_batch_deal_input()],
        })
        assert "by_region" in resp.json()["concentration"]

    def test_portfolio_report_contains_demo_tag(self):
        resp = client.post("/portfolio/analyze", json={
            "deal_inputs": [_batch_deal_input()],
        })
        assert "[demo]" in resp.json()["portfolio_report"]

    def test_custom_metrics_filter(self):
        resp = client.post("/portfolio/analyze", json={
            "deal_inputs": [_batch_deal_input(), _batch_deal_input()],
            "metrics": ["equity_irr"],
        })
        rankings = resp.json()["rankings"]
        assert "equity_irr" in rankings
        assert "oc_cushion_aaa" not in rankings

    def test_422_on_empty_deal_inputs(self):
        resp = client.post("/portfolio/analyze", json={"deal_inputs": []})
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Watchlist endpoints
# ---------------------------------------------------------------------------

class TestWatchlist:

    def setup_method(self):
        """Clear watchlist before each test."""
        from app.services import watchlist_service
        watchlist_service.clear()

    def test_get_watchlist_empty(self):
        resp = client.get("/watchlist")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    def test_post_watchlist_creates_item(self):
        resp = client.post("/watchlist", json={
            "metric": "equity_irr",
            "operator": "lt",
            "threshold": 0.08,
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["metric"] == "equity_irr"
        assert data["item_id"].startswith("wl-")

    def test_get_watchlist_returns_created_items(self):
        client.post("/watchlist", json={"metric": "equity_irr", "operator": "lt", "threshold": 0.08})
        client.post("/watchlist", json={"metric": "wac", "operator": "gt", "threshold": 0.12})
        resp = client.get("/watchlist")
        assert resp.json()["total"] == 2

    def test_delete_watchlist_item(self):
        created = client.post("/watchlist", json={
            "metric": "equity_irr", "operator": "lt", "threshold": 0.08,
        }).json()
        item_id = created["item_id"]
        del_resp = client.delete(f"/watchlist/{item_id}")
        assert del_resp.status_code == 200
        assert del_resp.json()["deleted"] is True

    def test_delete_nonexistent_returns_404(self):
        resp = client.delete("/watchlist/nonexistent-id")
        assert resp.status_code == 404

    def test_post_watchlist_invalid_operator_returns_422(self):
        resp = client.post("/watchlist", json={
            "metric": "equity_irr", "operator": "INVALID", "threshold": 0.08,
        })
        assert resp.status_code == 422

    def test_check_with_no_items(self):
        resp = client.post("/watchlist/check", json={"deal_input": _batch_deal_input()})
        assert resp.status_code == 200
        data = resp.json()
        assert data["items_checked"] == 0
        assert data["triggered_count"] == 0

    def test_check_returns_triggered_alert(self):
        # Add item that will always trigger (threshold > max possible IRR)
        client.post("/watchlist", json={
            "metric": "equity_irr", "operator": "lt", "threshold": 0.99,
        })
        resp = client.post("/watchlist/check", json={"deal_input": _batch_deal_input()})
        data = resp.json()
        assert data["triggered_count"] >= 1

    def test_check_response_structure(self):
        resp = client.post("/watchlist/check", json={"deal_input": _batch_deal_input()})
        data = resp.json()
        for key in ("deal_id", "items_checked", "triggered_count",
                    "alerts", "audit_events_count", "is_mock", "error"):
            assert key in data

    def test_watchlist_filter_by_deal_id(self):
        client.post("/watchlist", json={
            "metric": "equity_irr", "operator": "lt", "threshold": 0.08,
            "deal_id": "specific-deal",
        })
        # Global GET with no filter shows the item
        resp = client.get("/watchlist")
        assert resp.json()["total"] == 1
        # Filtered GET for this deal also shows it
        resp = client.get("/watchlist?deal_id=specific-deal")
        assert resp.json()["total"] == 1
        # Filtered GET for a different deal excludes it
        resp = client.get("/watchlist?deal_id=other-deal")
        assert resp.json()["total"] == 0


# ---------------------------------------------------------------------------
# Registry re-run endpoints
# ---------------------------------------------------------------------------

class TestDealRerun:

    def _register_deal(self, deal_id="rerun-test-001"):
        """Create a deal via POST /deals and return the deal_id."""
        resp = client.post("/deals", json={
            "deal": {
                "deal_id": deal_id,
                "name": "Rerun Test CLO",
                "issuer": "Rerun Issuer LLC",
                "region": "US",
                "currency": "USD",
            },
            "collateral": {
                "collateral_id": f"coll-{deal_id}",
                "pool_id": f"pool-{deal_id}",
                "asset_class": "broadly_syndicated_loans",
                "portfolio_size": 500_000_000,
                "was": 0.042,
                "warf": 2800.0,
                "wal": 5.2,
                "diversity_score": 60,
                "ccc_bucket": 0.05,
            },
            "tranches": [
                {"tranche_id": "t-aaa", "name": "AAA", "seniority": 1, "size_pct": 0.62},
                {"tranche_id": "t-eq",  "name": "Equity", "seniority": 2, "size_pct": 0.10},
            ],
        })
        return resp.json()["deal_id"]

    def test_pipeline_rerun_200(self):
        deal_id = self._register_deal()
        resp = client.post(f"/deals/{deal_id}/pipeline", json={})
        assert resp.status_code == 200

    def test_pipeline_rerun_response_structure(self):
        deal_id = self._register_deal()
        resp = client.post(f"/deals/{deal_id}/pipeline", json={})
        data = resp.json()
        for key in ("pipeline_id", "deal_id", "run_at", "is_mock", "stages",
                    "pipeline_summary", "audit_events_count"):
            assert key in data

    def test_pipeline_rerun_deal_id_correct(self):
        deal_id = self._register_deal()
        resp = client.post(f"/deals/{deal_id}/pipeline", json={})
        assert resp.json()["deal_id"] == deal_id

    def test_pipeline_rerun_404_unknown_deal(self):
        resp = client.post("/deals/nonexistent-id/pipeline", json={})
        assert resp.status_code == 404

    def test_analyze_rerun_200(self):
        deal_id = self._register_deal()
        resp = client.post(f"/deals/{deal_id}/analyze", json={})
        assert resp.status_code == 200

    def test_analyze_rerun_response_structure(self):
        deal_id = self._register_deal()
        resp = client.post(f"/deals/{deal_id}/analyze", json={})
        data = resp.json()
        for key in ("deal_id", "analysis_id", "analysed_at", "is_mock",
                    "key_metrics", "breakeven", "analytics_report"):
            assert key in data

    def test_analyze_rerun_404_unknown_deal(self):
        resp = client.post("/deals/nonexistent-id/analyze", json={})
        assert resp.status_code == 404

    def test_pipeline_rerun_updates_registry(self):
        deal_id = self._register_deal()
        client.post(f"/deals/{deal_id}/pipeline", json={})
        detail = client.get(f"/deals/{deal_id}").json()
        assert detail["last_pipeline_at"] is not None


# ---------------------------------------------------------------------------
# POST /portfolio/stress-test
# ---------------------------------------------------------------------------

class TestPortfolioStress:

    def test_200_two_deals(self):
        resp = client.post("/portfolio/stress-test", json={
            "deal_inputs": [_batch_deal_input(), _batch_deal_input()],
            "template_ids": ["base", "stress"],
        })
        assert resp.status_code == 200

    def test_response_has_required_fields(self):
        resp = client.post("/portfolio/stress-test", json={
            "deal_inputs": [_batch_deal_input()],
            "template_ids": ["stress"],
        })
        data = resp.json()
        for key in ("stress_id", "run_at", "deal_count", "template_count",
                    "deals", "risk_ranking", "most_sensitive_template",
                    "portfolio_report", "audit_events_count", "is_mock", "error"):
            assert key in data

    def test_deal_count_matches(self):
        resp = client.post("/portfolio/stress-test", json={
            "deal_inputs": [_batch_deal_input(), _batch_deal_input()],
            "template_ids": ["stress"],
        })
        assert resp.json()["deal_count"] == 2

    def test_risk_ranking_populated(self):
        resp = client.post("/portfolio/stress-test", json={
            "deal_inputs": [_batch_deal_input(), _batch_deal_input()],
            "template_ids": ["stress", "deep-stress"],
        })
        assert len(resp.json()["risk_ranking"]) == 2

    def test_most_sensitive_template_present(self):
        resp = client.post("/portfolio/stress-test", json={
            "deal_inputs": [_batch_deal_input()],
            "template_ids": ["stress"],
        })
        assert resp.json()["most_sensitive_template"] is not None

    def test_portfolio_report_has_demo_tag(self):
        resp = client.post("/portfolio/stress-test", json={
            "deal_inputs": [_batch_deal_input()],
            "template_ids": ["stress"],
        })
        assert "[demo]" in resp.json()["portfolio_report"]

    def test_is_mock_true(self):
        resp = client.post("/portfolio/stress-test", json={
            "deal_inputs": [_batch_deal_input()],
            "template_ids": ["stress"],
        })
        assert resp.json()["is_mock"] is True

    def test_scenario_type_filter(self):
        resp = client.post("/portfolio/stress-test", json={
            "deal_inputs": [_batch_deal_input()],
            "scenario_type": "stress",
        })
        assert resp.status_code == 200

    def test_422_on_empty_deal_inputs(self):
        resp = client.post("/portfolio/stress-test", json={"deal_inputs": []})
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /scoring/score  /  POST /deals/{deal_id}/score
# ---------------------------------------------------------------------------

class TestScoring:

    def test_score_200(self):
        resp = client.post("/scoring/score", json={"deal_input": _batch_deal_input()})
        assert resp.status_code == 200

    def test_score_response_structure(self):
        resp = client.post("/scoring/score", json={"deal_input": _batch_deal_input()})
        data = resp.json()
        for key in ("deal_id", "scoring_id", "scored_at", "composite_score",
                    "grade", "grade_label", "dimension_scores", "top_drivers",
                    "risk_flags", "score_report", "audit_events_count", "is_mock", "error"):
            assert key in data

    def test_composite_score_in_range(self):
        resp = client.post("/scoring/score", json={"deal_input": _batch_deal_input()})
        score = resp.json()["composite_score"]
        assert 0 <= score <= 100

    def test_grade_is_valid(self):
        resp = client.post("/scoring/score", json={"deal_input": _batch_deal_input()})
        assert resp.json()["grade"] in ("A", "B", "C", "D")

    def test_all_dimensions_present(self):
        resp = client.post("/scoring/score", json={"deal_input": _batch_deal_input()})
        dims = resp.json()["dimension_scores"]
        for d in ("irr_quality", "oc_adequacy", "stress_resilience", "collateral_quality"):
            assert d in dims

    def test_score_report_has_demo_tag(self):
        resp = client.post("/scoring/score", json={"deal_input": _batch_deal_input()})
        assert "[demo]" in resp.json()["score_report"]

    def test_is_mock_true(self):
        resp = client.post("/scoring/score", json={"deal_input": _batch_deal_input()})
        assert resp.json()["is_mock"] is True

    def test_score_from_registry_200(self):
        # Register a deal first
        create_resp = client.post("/deals", json={
            "deal": {
                "deal_id": "scoring-reg-001",
                "name": "Scoring Registry CLO",
                "issuer": "Score Issuer LLC",
                "region": "US",
                "currency": "USD",
            },
            "collateral": {
                "collateral_id": "coll-scoring-001",
                "pool_id": "pool-scoring-001",
                "asset_class": "broadly_syndicated_loans",
                "portfolio_size": 500_000_000,
                "was": 0.042,
                "warf": 2800.0,
                "wal": 5.2,
                "diversity_score": 60,
                "ccc_bucket": 0.05,
            },
            "tranches": [
                {"tranche_id": "t-aaa", "name": "AAA", "seniority": 1, "size_pct": 0.62},
                {"tranche_id": "t-eq",  "name": "Equity", "seniority": 2, "size_pct": 0.10},
            ],
        })
        deal_id = create_resp.json()["deal_id"]
        resp = client.post(f"/deals/{deal_id}/score", json={})
        assert resp.status_code == 200
        assert resp.json()["deal_id"] == deal_id

    def test_score_from_registry_404_unknown(self):
        resp = client.post("/deals/nonexistent-id/score", json={})
        assert resp.status_code == 404
