"""
tests/test_drafting_service.py

Tests for app/services/drafting_service.py

Coverage:
- generate_investor_summary: structure, mock marking, placeholder presence
- generate_ic_memo: structure, mock marking, comparison section
- DraftDocument: to_dict, to_markdown, default state
- Helper formatters: _fmt_pct, _fmt_years, _fmt_currency

These tests assert governance invariants as well as structural ones.
A failing test here means either a mock leaks as official, or an approval
gate is missing from a document that goes external.
"""

import pytest
from app.services.drafting_service import (
    generate_investor_summary,
    generate_ic_memo,
    _fmt_pct,
    _fmt_years,
    _fmt_currency,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def deal_input():
    return {
        "deal_id": "deal-test-001",
        "name": "Test CLO I",
        "issuer": "Test Issuer LLC",
        "manager": "Test Manager",
        "region": "US",
        "currency": "USD",
        "close_date": "2025-09-15",
        "collateral": {
            "pool_id": "pool-001",
            "asset_class": "broadly_syndicated_loans",
            "portfolio_size": 500_000_000,
            "was": 0.042,
            "warf": 2800,
            "wal": 5.2,
            "diversity_score": 62,
            "ccc_bucket": 0.055,
        },
        "liabilities": [
            {"tranche_id": "t-aaa", "name": "AAA", "seniority": 1, "size_pct": 0.61, "coupon": "SOFR+145", "target_rating": "Aaa"},
            {"tranche_id": "t-equity", "name": "Equity", "seniority": 2, "size_pct": 0.09, "coupon": None, "target_rating": None},
        ],
        "structural_tests": {
            "oc_tests": {"AAA": 1.42},
            "ic_tests": {"AAA": 1.25},
            "ccc_limit": 0.075,
        },
        "market_assumptions": {
            "default_rate": 0.03,
            "recovery_rate": 0.65,
            "spread_shock_bps": 0,
        },
    }


@pytest.fixture
def mock_scenario_result():
    """Scenario result from the mock engine — carries _mock key."""
    return {
        "run_id": "run-mock-001",
        "scenario_id": "sc-test-001",
        "deal_id": "deal-test-001",
        "source": "model_runner",
        "status": "complete",
        "executed_at": "2025-01-01T00:00:00Z",
        "_mock": "MOCK_ENGINE_OUTPUT",
        "outputs": {
            "equity_irr": 0.142,
            "aaa_size_pct": 0.61,
            "wac": 0.038,
            "oc_cushion_aaa": 0.052,
            "ic_cushion_aaa": 0.031,
            "equity_wal": 12.4,
            "scenario_npv": 1_820_000,
        },
    }


@pytest.fixture
def real_scenario_result():
    """Scenario result without _mock — simulates real engine output."""
    return {
        "run_id": "run-real-001",
        "scenario_id": "sc-test-001",
        "deal_id": "deal-test-001",
        "source": "model_runner",
        "status": "complete",
        "executed_at": "2025-01-01T00:00:00Z",
        "outputs": {
            "equity_irr": 0.142,
            "aaa_size_pct": 0.61,
            "wac": 0.038,
            "oc_cushion_aaa": 0.052,
            "ic_cushion_aaa": 0.031,
            "equity_wal": 12.4,
            "scenario_npv": 1_820_000,
        },
    }


@pytest.fixture
def scenario_request():
    return {
        "scenario_id": "sc-test-001",
        "deal_id": "deal-test-001",
        "name": "Baseline",
        "scenario_type": "base",
        "parameters": {
            "default_rate": 0.03,
            "recovery_rate": 0.65,
            "spread_shock_bps": 0,
        },
        "assumptions_made": [],
        "flagged_ambiguities": [],
    }


# ---------------------------------------------------------------------------
# generate_investor_summary — structure
# ---------------------------------------------------------------------------

class TestGenerateInvestorSummary:

    def test_returns_draft_document(self, deal_input, mock_scenario_result):
        from app.services.drafting_service import DraftDocument
        doc = generate_investor_summary(deal_input, mock_scenario_result)
        assert isinstance(doc, DraftDocument)

    def test_draft_type_is_investor_summary(self, deal_input, mock_scenario_result):
        doc = generate_investor_summary(deal_input, mock_scenario_result)
        assert doc.draft_type == "investor_summary"

    def test_approved_is_false_always(self, deal_input, mock_scenario_result):
        doc = generate_investor_summary(deal_input, mock_scenario_result)
        assert doc.approved is False

    def test_approved_is_false_for_real_engine_output(self, deal_input, real_scenario_result):
        """approved=False even when outputs are not mock."""
        doc = generate_investor_summary(deal_input, real_scenario_result)
        assert doc.approved is False

    def test_requires_approval_is_true(self, deal_input, mock_scenario_result):
        doc = generate_investor_summary(deal_input, mock_scenario_result)
        assert doc.requires_approval is True

    def test_is_mock_true_when_mock_tag_present(self, deal_input, mock_scenario_result):
        doc = generate_investor_summary(deal_input, mock_scenario_result)
        assert doc.is_mock is True

    def test_is_mock_false_when_no_mock_tag(self, deal_input, real_scenario_result):
        doc = generate_investor_summary(deal_input, real_scenario_result)
        assert doc.is_mock is False

    def test_has_seven_sections(self, deal_input, mock_scenario_result):
        doc = generate_investor_summary(deal_input, mock_scenario_result)
        assert len(doc.sections) == 7

    def test_expected_section_ids(self, deal_input, mock_scenario_result):
        doc = generate_investor_summary(deal_input, mock_scenario_result)
        ids = [s.section_id for s in doc.sections]
        assert "draft-notice" in ids
        assert "transaction-overview" in ids
        assert "portfolio-overview" in ids
        assert "tranche-summary" in ids
        assert "scenario-metrics" in ids
        assert "risk-considerations" in ids
        assert "disclosures" in ids

    def test_draft_id_starts_with_draft_inv(self, deal_input, mock_scenario_result):
        doc = generate_investor_summary(deal_input, mock_scenario_result)
        assert doc.draft_id.startswith("draft-inv-")

    def test_deal_id_propagated(self, deal_input, mock_scenario_result):
        doc = generate_investor_summary(deal_input, mock_scenario_result)
        assert doc.deal_id == "deal-test-001"

    def test_grounding_sources_non_empty(self, deal_input, mock_scenario_result):
        doc = generate_investor_summary(deal_input, mock_scenario_result)
        assert len(doc.grounding_sources) >= 2

    def test_draft_warnings_non_empty(self, deal_input, mock_scenario_result):
        doc = generate_investor_summary(deal_input, mock_scenario_result)
        assert len(doc.draft_warnings) >= 2

    def test_mock_warning_present_when_mock(self, deal_input, mock_scenario_result):
        doc = generate_investor_summary(deal_input, mock_scenario_result)
        mock_warning = any("MOCK ENGINE" in w.upper() or "mock" in w.lower() for w in doc.draft_warnings)
        assert mock_warning, "Expected mock engine warning in draft_warnings"

    def test_no_mock_warning_when_not_mock(self, deal_input, real_scenario_result):
        doc = generate_investor_summary(deal_input, real_scenario_result)
        mock_warning = any("MOCK ENGINE" in w.upper() for w in doc.draft_warnings)
        assert not mock_warning

    def test_scenario_metrics_section_tags_mock(self, deal_input, mock_scenario_result):
        doc = generate_investor_summary(deal_input, mock_scenario_result)
        metrics_section = next(s for s in doc.sections if s.section_id == "scenario-metrics")
        assert "[mock" in metrics_section.source_tag.lower() or "NOT official" in metrics_section.source_tag

    def test_scenario_metrics_section_tags_calculated_when_real(self, deal_input, real_scenario_result):
        doc = generate_investor_summary(deal_input, real_scenario_result)
        metrics_section = next(s for s in doc.sections if s.section_id == "scenario-metrics")
        assert "[calculated]" in metrics_section.source_tag

    def test_disclosures_section_has_placeholders(self, deal_input, mock_scenario_result):
        doc = generate_investor_summary(deal_input, mock_scenario_result)
        disclosures = next(s for s in doc.sections if s.section_id == "disclosures")
        assert "[PLACEHOLDER:" in disclosures.content

    def test_risk_section_contains_generated_language(self, deal_input, mock_scenario_result):
        doc = generate_investor_summary(deal_input, mock_scenario_result)
        risk = next(s for s in doc.sections if s.section_id == "risk-considerations")
        assert risk.contains_generated_language is True


# ---------------------------------------------------------------------------
# generate_investor_summary — to_dict and to_markdown
# ---------------------------------------------------------------------------

class TestDraftDocumentSerialisation:

    def test_to_dict_has_required_keys(self, deal_input, mock_scenario_result):
        doc = generate_investor_summary(deal_input, mock_scenario_result)
        d = doc.to_dict()
        for key in ("draft_id", "draft_type", "deal_id", "approved", "requires_approval",
                    "is_mock", "sections", "grounding_sources", "draft_warnings"):
            assert key in d, f"Missing key in to_dict(): {key}"

    def test_to_dict_approved_is_false(self, deal_input, mock_scenario_result):
        doc = generate_investor_summary(deal_input, mock_scenario_result)
        assert doc.to_dict()["approved"] is False

    def test_to_dict_sections_have_source_tag(self, deal_input, mock_scenario_result):
        doc = generate_investor_summary(deal_input, mock_scenario_result)
        for section in doc.to_dict()["sections"]:
            assert "source_tag" in section
            assert section["source_tag"]  # non-empty

    def test_to_markdown_contains_draft_banner(self, deal_input, mock_scenario_result):
        doc = generate_investor_summary(deal_input, mock_scenario_result)
        md = doc.to_markdown()
        assert "[DRAFT — NOT FOR DISTRIBUTION]" in md

    def test_to_markdown_contains_mock_banner_when_mock(self, deal_input, mock_scenario_result):
        doc = generate_investor_summary(deal_input, mock_scenario_result)
        md = doc.to_markdown()
        assert "MOCK ENGINE" in md

    def test_to_markdown_no_mock_banner_when_real(self, deal_input, real_scenario_result):
        doc = generate_investor_summary(deal_input, real_scenario_result)
        md = doc.to_markdown()
        assert "MOCK ENGINE" not in md

    def test_to_markdown_contains_approval_status(self, deal_input, mock_scenario_result):
        doc = generate_investor_summary(deal_input, mock_scenario_result)
        md = doc.to_markdown()
        assert "approved = False" in md

    def test_to_markdown_contains_approval_required(self, deal_input, mock_scenario_result):
        doc = generate_investor_summary(deal_input, mock_scenario_result)
        md = doc.to_markdown()
        assert "APPROVAL REQUIRED" in md


# ---------------------------------------------------------------------------
# generate_ic_memo
# ---------------------------------------------------------------------------

class TestGenerateIcMemo:

    def test_draft_type_is_ic_memo(self, deal_input, mock_scenario_result):
        doc = generate_ic_memo(deal_input, mock_scenario_result)
        assert doc.draft_type == "ic_memo"

    def test_approved_is_false(self, deal_input, mock_scenario_result):
        doc = generate_ic_memo(deal_input, mock_scenario_result)
        assert doc.approved is False

    def test_has_ten_sections(self, deal_input, mock_scenario_result):
        doc = generate_ic_memo(deal_input, mock_scenario_result)
        assert len(doc.sections) == 10

    def test_expected_section_ids(self, deal_input, mock_scenario_result):
        doc = generate_ic_memo(deal_input, mock_scenario_result)
        ids = [s.section_id for s in doc.sections]
        for expected in (
            "internal-notice", "deal-overview", "collateral-analysis",
            "liability-structure", "scenario-parameters", "scenario-outputs",
            "structural-test-analysis", "scenario-comparison",
            "open-items", "approval-gate",
        ):
            assert expected in ids, f"Missing section: {expected}"

    def test_comparison_placeholder_when_no_comparison(self, deal_input, mock_scenario_result):
        doc = generate_ic_memo(deal_input, mock_scenario_result)
        comp = next(s for s in doc.sections if s.section_id == "scenario-comparison")
        assert "DATA NOT PROVIDED" in comp.content or "placeholder" in comp.source_tag.lower()

    def test_comparison_section_populated_when_provided(self, deal_input, mock_scenario_result):
        comparison = {
            "param_changes": [{"field": "default_rate", "label": "Default rate", "v1": 0.03, "v2": 0.05, "direction": "up"}],
            "output_changes": [{"field": "equity_irr", "label": "Equity IRR", "v1": 0.142, "v2": 0.108, "direction": "down"}],
            "likely_drivers": [{"statement": "Higher default rate reduced equity IRR.", "confidence": "medium"}],
        }
        doc = generate_ic_memo(deal_input, mock_scenario_result, comparison_result=comparison)
        comp = next(s for s in doc.sections if s.section_id == "scenario-comparison")
        assert "default_rate" in comp.content or "Default rate" in comp.content

    def test_approval_gate_section_has_placeholder(self, deal_input, mock_scenario_result):
        doc = generate_ic_memo(deal_input, mock_scenario_result)
        gate = next(s for s in doc.sections if s.section_id == "approval-gate")
        assert "[PLACEHOLDER:" in gate.content

    def test_draft_id_starts_with_draft_ic(self, deal_input, mock_scenario_result):
        doc = generate_ic_memo(deal_input, mock_scenario_result)
        assert doc.draft_id.startswith("draft-ic-")

    def test_scenario_outputs_tagged_mock(self, deal_input, mock_scenario_result):
        doc = generate_ic_memo(deal_input, mock_scenario_result)
        outputs = next(s for s in doc.sections if s.section_id == "scenario-outputs")
        assert "mock" in outputs.source_tag.lower()

    def test_structural_test_has_mock_hedge_when_mock(self, deal_input, mock_scenario_result):
        doc = generate_ic_memo(deal_input, mock_scenario_result)
        tests = next(s for s in doc.sections if s.section_id == "structural-test-analysis")
        assert "mock" in tests.content.lower() or "MOCK ENGINE" in tests.content


# ---------------------------------------------------------------------------
# Missing data handling — must render gracefully, not raise
# ---------------------------------------------------------------------------

class TestMissingDataHandling:

    def test_investor_summary_with_empty_deal_input(self, mock_scenario_result):
        doc = generate_investor_summary({}, mock_scenario_result)
        assert doc.approved is False
        assert doc.deal_id == "unknown"

    def test_ic_memo_with_no_tranches(self, mock_scenario_result):
        deal_no_tranches = {"deal_id": "d1", "name": "Test", "issuer": "X", "liabilities": []}
        doc = generate_ic_memo(deal_no_tranches, mock_scenario_result)
        liability = next(s for s in doc.sections if s.section_id == "liability-structure")
        assert "DATA NOT PROVIDED" in liability.content

    def test_investor_summary_with_no_scenario_request(self, deal_input, mock_scenario_result):
        doc = generate_investor_summary(deal_input, mock_scenario_result, scenario_request=None)
        assert len(doc.sections) == 7

    def test_ic_memo_scenario_outputs_renders_missing_metrics(self, deal_input):
        result_no_outputs = {
            "run_id": "run-001", "scenario_id": "sc-001", "deal_id": "deal-001",
            "source": "model_runner", "status": "complete",
            "_mock": "MOCK_ENGINE_OUTPUT",
            "outputs": {},
        }
        doc = generate_ic_memo(deal_input, result_no_outputs)
        outputs_section = next(s for s in doc.sections if s.section_id == "scenario-outputs")
        assert "[DATA NOT PROVIDED]" in outputs_section.content


# ---------------------------------------------------------------------------
# Governance invariants
# ---------------------------------------------------------------------------

class TestGovernanceInvariants:

    def test_approved_cannot_be_set_by_drafting_service(self, deal_input, real_scenario_result):
        """Drafting service must never produce approved=True regardless of inputs."""
        doc = generate_investor_summary(deal_input, real_scenario_result)
        assert doc.approved is False
        doc2 = generate_ic_memo(deal_input, real_scenario_result)
        assert doc2.approved is False

    def test_every_section_has_source_tag(self, deal_input, mock_scenario_result):
        for generator in (generate_investor_summary, generate_ic_memo):
            doc = generator(deal_input, mock_scenario_result)
            for section in doc.sections:
                assert section.source_tag, f"Section {section.section_id} has no source_tag"

    def test_placeholder_count_in_mock_investor_summary(self, deal_input, mock_scenario_result):
        """Investor summary must have placeholders (compliance gaps need human fill)."""
        doc = generate_investor_summary(deal_input, mock_scenario_result)
        total_placeholders = sum(
            s.content.count("[PLACEHOLDER:") for s in doc.sections
        )
        assert total_placeholders > 0, "Expected at least one PLACEHOLDER marker"

    def test_deal_id_not_unknown_when_provided(self, deal_input, mock_scenario_result):
        doc = generate_investor_summary(deal_input, mock_scenario_result)
        assert doc.deal_id != "unknown"

    def test_run_id_propagated_from_scenario_result(self, deal_input, mock_scenario_result):
        doc = generate_investor_summary(deal_input, mock_scenario_result)
        assert doc.run_id == "run-mock-001"


# ---------------------------------------------------------------------------
# Formatter helpers
# ---------------------------------------------------------------------------

class TestFormatters:

    def test_fmt_pct_formats_float(self):
        assert _fmt_pct(0.142) == "14.20%"

    def test_fmt_pct_handles_none(self):
        assert _fmt_pct(None) == "[DATA NOT PROVIDED]"

    def test_fmt_years_formats_float(self):
        assert _fmt_years(5.2) == "5.2 yrs"

    def test_fmt_years_handles_none(self):
        assert _fmt_years(None) == "[DATA NOT PROVIDED]"

    def test_fmt_currency_millions(self):
        result = _fmt_currency(500_000_000, "USD")
        assert "500" in result and "m" in result.lower()

    def test_fmt_currency_billions(self):
        result = _fmt_currency(1_500_000_000, "USD")
        assert "bn" in result.lower()

    def test_fmt_currency_handles_none(self):
        assert _fmt_currency(None, "USD") == "[DATA NOT PROVIDED]"
