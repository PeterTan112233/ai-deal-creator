"""
Tests for Phase 5 services and the updated run_scenario_workflow.
"""

import json
import pytest
from app.services import validation_service, model_engine_service, summary_service
from app.workflows.run_scenario_workflow import run_scenario_workflow


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


def _valid_deal():
    return _load_sample_deal("US BSL")


def _minimal_deal():
    return _load_sample_deal("Minimal")


# ---------------------------------------------------------------------------
# validation_service
# ---------------------------------------------------------------------------

class TestValidationService:

    def test_valid_deal_passes(self):
        result = validation_service.validate_deal_input(_valid_deal())
        assert result["valid"] is True
        assert result["issues"] == []

    def test_missing_deal_id_fails(self):
        deal = _valid_deal()
        del deal["deal_id"]
        result = validation_service.validate_deal_input(deal)
        assert result["valid"] is False
        assert any("deal_id" in i for i in result["issues"])

    def test_missing_issuer_fails(self):
        deal = _valid_deal()
        deal["issuer"] = ""
        result = validation_service.validate_deal_input(deal)
        assert result["valid"] is False
        assert any("issuer" in i for i in result["issues"])

    def test_zero_portfolio_size_fails(self):
        deal = _valid_deal()
        deal["collateral"]["portfolio_size"] = 0
        result = validation_service.validate_deal_input(deal)
        assert result["valid"] is False
        assert any("portfolio_size" in i for i in result["issues"])

    def test_ccc_over_limit_fails(self):
        deal = _valid_deal()
        deal["collateral"]["ccc_bucket"] = 0.10
        result = validation_service.validate_deal_input(deal)
        assert result["valid"] is False
        assert any("ccc_bucket" in i for i in result["issues"])

    def test_low_diversity_fails(self):
        deal = _valid_deal()
        deal["collateral"]["diversity_score"] = 20
        result = validation_service.validate_deal_input(deal)
        assert result["valid"] is False
        assert any("diversity_score" in i for i in result["issues"])

    def test_duplicate_seniority_fails(self):
        deal = _valid_deal()
        deal["liabilities"][1]["seniority"] = 1  # duplicate seniority
        result = validation_service.validate_deal_input(deal)
        assert result["valid"] is False
        assert any("seniority" in i for i in result["issues"])

    def test_no_size_on_tranche_fails(self):
        deal = _valid_deal()
        for t in deal["liabilities"]:
            t.pop("size_pct", None)
            t.pop("size_abs", None)
        result = validation_service.validate_deal_input(deal)
        assert result["valid"] is False
        assert any("size_pct" in i or "size_abs" in i for i in result["issues"])

    def test_missing_liabilities_fails(self):
        deal = _valid_deal()
        deal["liabilities"] = []
        result = validation_service.validate_deal_input(deal)
        assert result["valid"] is False

    def test_ccc_near_limit_warns(self):
        deal = _valid_deal()
        deal["collateral"]["ccc_bucket"] = 0.065
        result = validation_service.validate_deal_input(deal)
        assert result["valid"] is True  # not a blocking issue
        assert any("ccc" in w.lower() for w in result["warnings"])

    def test_minimal_deal_passes(self):
        result = validation_service.validate_deal_input(_minimal_deal())
        assert result["valid"] is True

    def test_validate_scenario_request_valid(self):
        req = {
            "scenario_id": "sc-001",
            "deal_id": "deal-001",
            "name": "Baseline",
            "parameters": {
                "default_rate": 0.03,
                "recovery_rate": 0.65,
                "spread_shock_bps": 0,
            },
        }
        result = validation_service.validate_scenario_request(req)
        assert result["valid"] is True

    def test_validate_scenario_request_missing_param(self):
        req = {
            "scenario_id": "sc-001",
            "deal_id": "deal-001",
            "name": "Baseline",
            "parameters": {"default_rate": 0.03},  # missing recovery_rate
        }
        result = validation_service.validate_scenario_request(req)
        assert result["valid"] is False
        assert any("recovery_rate" in i for i in result["issues"])


# ---------------------------------------------------------------------------
# model_engine_service
# ---------------------------------------------------------------------------

class TestModelEngineService:

    def test_submit_returns_run_id(self):
        run_id = model_engine_service.submit_scenario(
            deal_id="deal-001",
            scenario_request={
                "parameters": {"default_rate": 0.03, "recovery_rate": 0.65, "spread_shock_bps": 0}
            },
        )
        assert run_id.startswith("mock-run-")

    def test_poll_returns_true(self):
        run_id = model_engine_service.submit_scenario("deal-001", {"parameters": {}})
        assert model_engine_service.poll_until_done(run_id) is True

    def test_get_result_structure(self):
        run_id = model_engine_service.submit_scenario("deal-001", {"parameters": {}})
        result = model_engine_service.get_result(run_id, "sc-001", "deal-001")
        assert result["source"] == "model_runner"
        assert result["status"] == "complete"
        assert "outputs" in result
        assert "_mock" in result  # Phase 1 — mock output

    def test_get_result_outputs_known_keys_only(self):
        run_id = model_engine_service.submit_scenario("deal-001", {"parameters": {}})
        result = model_engine_service.get_result(run_id, "sc-001", "deal-001")
        outputs = result["outputs"]
        assert "_mock" not in outputs
        assert "_warning" not in outputs
        assert "equity_irr" in outputs

    def test_is_mock_mode(self):
        assert model_engine_service.is_mock_mode() is True


# ---------------------------------------------------------------------------
# summary_service
# ---------------------------------------------------------------------------

class TestSummaryService:

    def _make_result(self):
        run_id = model_engine_service.submit_scenario("deal-001", {"parameters": {}})
        return model_engine_service.get_result(run_id, "sc-001", "deal-001")

    def test_summary_contains_mock_banner(self):
        deal = _valid_deal()
        req = {"name": "Baseline", "scenario_type": "base", "parameters": {}, "assumptions_made": [], "flagged_ambiguities": []}
        result = self._make_result()
        summary = summary_service.generate_summary(deal, req, result)
        assert "MOCK ENGINE OUTPUT" in summary
        assert "NOT OFFICIAL" in summary

    def test_summary_contains_deal_name(self):
        deal = _valid_deal()
        req = {"name": "Baseline", "scenario_type": "base", "parameters": {}, "assumptions_made": [], "flagged_ambiguities": []}
        result = self._make_result()
        summary = summary_service.generate_summary(deal, req, result)
        assert deal["name"] in summary

    def test_summary_contains_source_citations(self):
        deal = _valid_deal()
        req = {"name": "Baseline", "scenario_type": "base", "parameters": {}, "assumptions_made": [], "flagged_ambiguities": []}
        result = self._make_result()
        summary = summary_service.generate_summary(deal, req, result)
        assert "SOURCE CITATIONS" in summary
        assert result["run_id"] in summary

    def test_summary_has_interpretation_label(self):
        deal = _valid_deal()
        req = {"name": "Baseline", "scenario_type": "base", "parameters": {}, "assumptions_made": [], "flagged_ambiguities": []}
        result = self._make_result()
        summary = summary_service.generate_summary(deal, req, result)
        assert "[generated" in summary


# ---------------------------------------------------------------------------
# run_scenario_workflow (integration)
# ---------------------------------------------------------------------------

class TestRunScenarioWorkflow:

    def test_full_flow_succeeds(self):
        deal = _valid_deal()
        result = run_scenario_workflow(deal, scenario_name="Baseline")
        assert "error" not in result
        assert result["validation"]["valid"] is True
        assert result["scenario_result"] is not None
        assert result["summary"] is not None
        assert result["is_mock"] is True
        assert len(result["audit_events"]) >= 3  # validated, submitted, completed, generated

    def test_invalid_deal_stops_early(self):
        deal = _valid_deal()
        deal["deal_id"] = ""
        result = run_scenario_workflow(deal)
        assert "error" in result
        assert result["scenario_result"] is None
        assert result["summary"] is None

    def test_parameter_overrides_applied(self):
        deal = _valid_deal()
        result = run_scenario_workflow(
            deal,
            scenario_name="Stressed recoveries",
            scenario_type="stress",
            parameter_overrides={"recovery_rate": 0.45},
        )
        assert result["scenario_request"]["parameters"]["recovery_rate"] == 0.45

    def test_audit_events_emitted(self):
        deal = _valid_deal()
        result = run_scenario_workflow(deal)
        assert len(result["audit_events"]) == 4  # validated, submitted, completed, generated

    def test_scenario_result_has_run_id(self):
        deal = _valid_deal()
        result = run_scenario_workflow(deal)
        assert result["scenario_result"]["run_id"].startswith("mock-run-")
