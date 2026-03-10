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
