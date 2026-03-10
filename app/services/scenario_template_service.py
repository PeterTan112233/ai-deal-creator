"""
app/services/scenario_template_service.py

Named stress scenario template library.

Templates encode market-consensus stress assumptions for well-known historical
events and regulatory test suites.  Analysts can apply a template to any deal
without specifying raw parameters — the template supplies the CDR, RR, and
spread shock values calibrated to that stress event.

All templates are tagged [demo] — they use illustrative parameters, not
official rating-agency or regulatory calibrations.

Template structure
------------------
{
    "template_id":   str,   # unique machine-readable name
    "name":          str,   # human-readable display name
    "description":   str,   # short explanation
    "scenario_type": str,   # "base" | "stress" | "regulatory"
    "tags":          list[str],
    "parameters": {
        "default_rate":      float,   # CDR (constant default rate)
        "recovery_rate":     float,   # recovery rate on defaulted assets
        "spread_shock_bps":  float,   # parallel spread shift in bps
    },
    "_source": "DEMO_SCENARIO_TEMPLATES",
}

Phase 2+: replace with a template-store-mcp connector that serves
officially validated stress parameters from the risk function.
"""

from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Template registry
# ---------------------------------------------------------------------------

_TEMPLATES: Dict[str, Dict[str, Any]] = {t["template_id"]: t for t in [
    # ---- Base-case --------------------------------------------------------
    {
        "template_id":   "base",
        "name":          "Base Case",
        "description":   "Consensus base-case assumption set: moderate default environment.",
        "scenario_type": "base",
        "tags":          ["base", "standard"],
        "parameters": {
            "default_rate":     0.030,
            "recovery_rate":    0.650,
            "spread_shock_bps": 0.0,
        },
        "_source": "DEMO_SCENARIO_TEMPLATES",
    },
    # ---- Mild stress ------------------------------------------------------
    {
        "template_id":   "mild-stress",
        "name":          "Mild Stress",
        "description":   "Mild credit deterioration; soft-landing recession scenario.",
        "scenario_type": "stress",
        "tags":          ["stress", "standard"],
        "parameters": {
            "default_rate":     0.050,
            "recovery_rate":    0.550,
            "spread_shock_bps": 50.0,
        },
        "_source": "DEMO_SCENARIO_TEMPLATES",
    },
    # ---- Standard stress -------------------------------------------------
    {
        "template_id":   "stress",
        "name":          "Stress",
        "description":   "Moderate recession; above-average defaults and spread widening.",
        "scenario_type": "stress",
        "tags":          ["stress", "standard"],
        "parameters": {
            "default_rate":     0.075,
            "recovery_rate":    0.450,
            "spread_shock_bps": 150.0,
        },
        "_source": "DEMO_SCENARIO_TEMPLATES",
    },
    # ---- Deep stress -----------------------------------------------------
    {
        "template_id":   "deep-stress",
        "name":          "Deep Stress",
        "description":   "Severe recession; tail-risk loss assumptions.",
        "scenario_type": "stress",
        "tags":          ["stress", "standard", "tail"],
        "parameters": {
            "default_rate":     0.120,
            "recovery_rate":    0.350,
            "spread_shock_bps": 300.0,
        },
        "_source": "DEMO_SCENARIO_TEMPLATES",
    },
    # ---- GFC 2008 --------------------------------------------------------
    {
        "template_id":   "gfc-2008",
        "name":          "GFC 2008",
        "description":   "Global Financial Crisis (2008–2009): peak CDR and spread levels "
                         "observed in US BSL CLOs during the credit crisis.",
        "scenario_type": "stress",
        "tags":          ["stress", "historical", "gfc"],
        "parameters": {
            "default_rate":     0.130,
            "recovery_rate":    0.380,
            "spread_shock_bps": 400.0,
        },
        "_source": "DEMO_SCENARIO_TEMPLATES",
    },
    # ---- COVID-19 2020 ---------------------------------------------------
    {
        "template_id":   "covid-2020",
        "name":          "COVID-19 2020",
        "description":   "COVID-19 shock (Q1–Q2 2020): sharp but short-lived spread "
                         "widening; moderate actual default realisation.",
        "scenario_type": "stress",
        "tags":          ["stress", "historical", "covid"],
        "parameters": {
            "default_rate":     0.065,
            "recovery_rate":    0.480,
            "spread_shock_bps": 350.0,
        },
        "_source": "DEMO_SCENARIO_TEMPLATES",
    },
    # ---- Stagflation -----------------------------------------------------
    {
        "template_id":   "stagflation",
        "name":          "Stagflation",
        "description":   "Elevated inflation + slow growth: spread widening driven by "
                         "rate risk, moderate credit stress.",
        "scenario_type": "stress",
        "tags":          ["stress", "macro"],
        "parameters": {
            "default_rate":     0.055,
            "recovery_rate":    0.500,
            "spread_shock_bps": 200.0,
        },
        "_source": "DEMO_SCENARIO_TEMPLATES",
    },
    # ---- Regulatory (EBA/Fed-DFAST proxy) --------------------------------
    {
        "template_id":   "regulatory-adverse",
        "name":          "Regulatory Adverse",
        "description":   "Proxy for regulator-specified adverse scenario "
                         "(illustrative; not an official regulatory test).",
        "scenario_type": "regulatory",
        "tags":          ["regulatory", "adverse"],
        "parameters": {
            "default_rate":     0.090,
            "recovery_rate":    0.400,
            "spread_shock_bps": 250.0,
        },
        "_source": "DEMO_SCENARIO_TEMPLATES",
    },
    # ---- Regulatory severely adverse ------------------------------------
    {
        "template_id":   "regulatory-severely-adverse",
        "name":          "Regulatory Severely Adverse",
        "description":   "Proxy for regulator-specified severely adverse scenario "
                         "(illustrative; not an official regulatory test).",
        "scenario_type": "regulatory",
        "tags":          ["regulatory", "severely-adverse"],
        "parameters": {
            "default_rate":     0.150,
            "recovery_rate":    0.300,
            "spread_shock_bps": 450.0,
        },
        "_source": "DEMO_SCENARIO_TEMPLATES",
    },
]}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def list_templates(
    scenario_type: Optional[str] = None,
    tag: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Return all templates, optionally filtered by scenario_type or tag.

    Parameters
    ----------
    scenario_type : If given, only return templates with this scenario_type.
    tag           : If given, only return templates whose tags list contains this value.

    Returns
    -------
    List of template dicts, sorted by template_id alphabetically.
    """
    results = list(_TEMPLATES.values())
    if scenario_type:
        results = [t for t in results if t["scenario_type"] == scenario_type]
    if tag:
        results = [t for t in results if tag in t.get("tags", [])]
    results.sort(key=lambda t: t["template_id"])
    return results


def get_template(template_id: str) -> Optional[Dict[str, Any]]:
    """Return the template dict for template_id, or None if not found."""
    return _TEMPLATES.get(template_id)


def template_ids() -> List[str]:
    """Return a sorted list of all template IDs."""
    return sorted(_TEMPLATES.keys())


def apply_template(
    template_id: str,
    overrides: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Return the parameter dict for the named template, with optional overrides.

    Parameters
    ----------
    template_id : ID of the template to apply.
    overrides   : Dict of parameter overrides (e.g. {"spread_shock_bps": 200}).
                  Merged on top of the template parameters.

    Returns
    -------
    {"default_rate": float, "recovery_rate": float, "spread_shock_bps": float}

    Raises
    ------
    KeyError if template_id is not found.
    """
    tmpl = _TEMPLATES.get(template_id)
    if tmpl is None:
        raise KeyError(f"Unknown scenario template: '{template_id}'")
    params = dict(tmpl["parameters"])
    if overrides:
        params.update(overrides)
    return params
