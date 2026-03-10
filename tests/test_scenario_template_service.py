"""
tests/test_scenario_template_service.py

Tests for app/services/scenario_template_service.py

Covers:
  - list_templates: all, filtered by type, filtered by tag
  - get_template: known and unknown IDs
  - template_ids: sorted list
  - apply_template: happy path, overrides, unknown ID raises
  - Template registry completeness: all required keys present
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from app.services import scenario_template_service as svc

KNOWN_IDS = {
    "base", "mild-stress", "stress", "deep-stress",
    "gfc-2008", "covid-2020", "stagflation",
    "regulatory-adverse", "regulatory-severely-adverse",
}


# ---------------------------------------------------------------------------
# list_templates
# ---------------------------------------------------------------------------

class TestListTemplates:

    def test_returns_list(self):
        assert isinstance(svc.list_templates(), list)

    def test_all_known_templates_present(self):
        ids = {t["template_id"] for t in svc.list_templates()}
        assert KNOWN_IDS <= ids

    def test_filter_by_scenario_type_base(self):
        results = svc.list_templates(scenario_type="base")
        assert all(t["scenario_type"] == "base" for t in results)
        assert len(results) >= 1

    def test_filter_by_scenario_type_stress(self):
        results = svc.list_templates(scenario_type="stress")
        assert all(t["scenario_type"] == "stress" for t in results)
        assert len(results) >= 4

    def test_filter_by_scenario_type_regulatory(self):
        results = svc.list_templates(scenario_type="regulatory")
        assert all(t["scenario_type"] == "regulatory" for t in results)
        assert len(results) >= 2

    def test_filter_by_tag_historical(self):
        results = svc.list_templates(tag="historical")
        assert all("historical" in t["tags"] for t in results)
        ids = {t["template_id"] for t in results}
        assert "gfc-2008" in ids
        assert "covid-2020" in ids

    def test_filter_by_tag_standard(self):
        results = svc.list_templates(tag="standard")
        ids = {t["template_id"] for t in results}
        assert "base" in ids
        assert "stress" in ids

    def test_sorted_alphabetically(self):
        ids = [t["template_id"] for t in svc.list_templates()]
        assert ids == sorted(ids)

    def test_unknown_type_returns_empty(self):
        assert svc.list_templates(scenario_type="nonexistent") == []


# ---------------------------------------------------------------------------
# get_template
# ---------------------------------------------------------------------------

class TestGetTemplate:

    def test_get_known_template(self):
        t = svc.get_template("gfc-2008")
        assert t is not None
        assert t["template_id"] == "gfc-2008"

    def test_get_unknown_returns_none(self):
        assert svc.get_template("does-not-exist") is None

    def test_all_templates_have_required_keys(self):
        required = {"template_id", "name", "description", "scenario_type", "tags", "parameters", "_source"}
        for t in svc.list_templates():
            missing = required - set(t.keys())
            assert not missing, f"{t['template_id']} missing: {missing}"

    def test_parameters_have_required_fields(self):
        for t in svc.list_templates():
            params = t["parameters"]
            assert "default_rate" in params
            assert "recovery_rate" in params
            assert "spread_shock_bps" in params

    def test_source_is_demo(self):
        for t in svc.list_templates():
            assert t["_source"] == "DEMO_SCENARIO_TEMPLATES"


# ---------------------------------------------------------------------------
# template_ids
# ---------------------------------------------------------------------------

class TestTemplateIds:

    def test_returns_sorted_list(self):
        ids = svc.template_ids()
        assert ids == sorted(ids)

    def test_contains_all_known_ids(self):
        assert KNOWN_IDS <= set(svc.template_ids())


# ---------------------------------------------------------------------------
# apply_template
# ---------------------------------------------------------------------------

class TestApplyTemplate:

    def test_base_template_params(self):
        params = svc.apply_template("base")
        assert params["default_rate"] == pytest.approx(0.030)
        assert params["recovery_rate"] == pytest.approx(0.650)

    def test_gfc_template_higher_cdr_than_base(self):
        base = svc.apply_template("base")
        gfc = svc.apply_template("gfc-2008")
        assert gfc["default_rate"] > base["default_rate"]

    def test_gfc_template_lower_rr_than_base(self):
        base = svc.apply_template("base")
        gfc = svc.apply_template("gfc-2008")
        assert gfc["recovery_rate"] < base["recovery_rate"]

    def test_severity_ordering_cdr(self):
        """CDR should increase with stress severity."""
        cdr = {tid: svc.apply_template(tid)["default_rate"]
               for tid in ("base", "mild-stress", "stress", "deep-stress")}
        assert cdr["base"] < cdr["mild-stress"] < cdr["stress"] < cdr["deep-stress"]

    def test_overrides_applied(self):
        params = svc.apply_template("base", overrides={"spread_shock_bps": 999.0})
        assert params["spread_shock_bps"] == 999.0
        # Non-overridden values unchanged
        assert params["default_rate"] == pytest.approx(0.030)

    def test_overrides_do_not_mutate_template(self):
        svc.apply_template("base", overrides={"default_rate": 0.999})
        # Original template unaffected
        assert svc.apply_template("base")["default_rate"] == pytest.approx(0.030)

    def test_unknown_template_raises(self):
        with pytest.raises(KeyError):
            svc.apply_template("totally-unknown-template")

    def test_regulatory_cdr_above_standard_stress(self):
        reg_adv = svc.apply_template("regulatory-adverse")
        stress = svc.apply_template("stress")
        assert reg_adv["default_rate"] > stress["default_rate"]

    def test_regulatory_severely_adverse_strictest(self):
        severe = svc.apply_template("regulatory-severely-adverse")
        gfc = svc.apply_template("gfc-2008")
        # Severely adverse should be at least as severe as GFC
        assert severe["default_rate"] >= gfc["default_rate"]
