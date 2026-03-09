"""
app/services/validation_service.py

Validates deal input dicts against structural rules before any workflow runs.

This is deterministic structural validation only. It does not perform
financial analysis or predict deal feasibility.

Phase 2+: the pool_validation section will delegate to portfolio-data-mcp.validate_pool().
"""

from typing import Any, Dict, List


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def validate_deal_input(deal_input: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate a deal input dict against MVP structural rules.

    Returns:
        {
            "valid": bool,
            "issues": list[str],   # blocking problems — must fix before submission
            "warnings": list[str], # non-blocking concerns — flag to user
        }
    """
    issues: List[str] = []
    warnings: List[str] = []

    _check_top_level(deal_input, issues)
    _check_collateral(deal_input.get("collateral", {}), issues, warnings)
    _check_liabilities(deal_input.get("liabilities", []), issues, warnings)
    _check_market_assumptions(deal_input.get("market_assumptions", {}), warnings)

    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "warnings": warnings,
    }


def validate_scenario_request(scenario_request: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate a scenario request dict before engine submission.

    Returns:
        { "valid": bool, "issues": list[str], "warnings": list[str] }
    """
    issues: List[str] = []
    warnings: List[str] = []

    required = ["scenario_id", "deal_id", "name", "parameters"]
    for field in required:
        if not scenario_request.get(field):
            issues.append(f"scenario_request.{field} is required and must be non-empty")

    params = scenario_request.get("parameters", {})
    required_params = ["default_rate", "recovery_rate", "spread_shock_bps"]
    for p in required_params:
        if p not in params:
            issues.append(f"scenario_request.parameters.{p} is required")

    if "default_rate" in params and not (0 <= params["default_rate"] <= 1):
        issues.append("parameters.default_rate must be between 0 and 1")

    if "recovery_rate" in params and not (0 <= params["recovery_rate"] <= 1):
        issues.append("parameters.recovery_rate must be between 0 and 1")

    if "spread_shock_bps" in params and params["spread_shock_bps"] < 0:
        issues.append("parameters.spread_shock_bps must be >= 0")

    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# Internal checkers
# ---------------------------------------------------------------------------

def _check_top_level(deal: Dict[str, Any], issues: List[str]) -> None:
    for field in ["deal_id", "name", "issuer"]:
        value = deal.get(field)
        if not value or not str(value).strip():
            issues.append(f"deal.{field} is required and must be non-empty")

    if deal.get("region") and deal["region"] not in ("US", "EU", "APAC"):
        issues.append(f"deal.region must be one of: US, EU, APAC")


def _check_collateral(collateral: Dict[str, Any], issues: List[str], warnings: List[str]) -> None:
    if not collateral:
        issues.append("deal.collateral is required")
        return

    # Required presence
    for field in ["pool_id", "asset_class", "portfolio_size"]:
        if not collateral.get(field):
            issues.append(f"collateral.{field} is required")

    # portfolio_size
    size = collateral.get("portfolio_size", 0)
    if isinstance(size, (int, float)) and size <= 0:
        issues.append("collateral.portfolio_size must be greater than 0")

    # Pool health checks
    # Phase 2+: replace with portfolio-data-mcp.validate_pool()
    ccc = collateral.get("ccc_bucket")
    if ccc is not None and ccc > 0.075:
        issues.append(
            f"collateral.ccc_bucket {ccc:.1%} exceeds limit of 7.5%"
        )

    diversity = collateral.get("diversity_score")
    if diversity is not None and diversity < 30:
        issues.append(
            f"collateral.diversity_score {diversity} is below minimum of 30"
        )

    wal = collateral.get("wal")
    if wal is not None and wal <= 0:
        issues.append("collateral.wal must be greater than 0")

    was = collateral.get("was")
    if was is not None and was < 0:
        issues.append("collateral.was must be >= 0")

    warf = collateral.get("warf")
    if warf is not None and warf < 0:
        issues.append("collateral.warf must be >= 0")

    # Soft warnings
    if ccc is not None and ccc > 0.06:
        warnings.append(
            f"collateral.ccc_bucket {ccc:.1%} is above 6% — approaching limit"
        )

    if diversity is not None and diversity < 40:
        warnings.append(
            f"collateral.diversity_score {diversity} is low — consider pool diversification"
        )


def _check_liabilities(liabilities: List[Any], issues: List[str], warnings: List[str]) -> None:
    if not liabilities:
        issues.append("deal.liabilities must contain at least one tranche")
        return

    seen_seniorities = set()
    total_size_pct = 0.0

    for i, tranche in enumerate(liabilities):
        label = tranche.get("name", f"tranche[{i}]")

        # Required fields
        if not tranche.get("tranche_id"):
            issues.append(f"liabilities[{i}] ({label}): tranche_id is required")
        if not tranche.get("name"):
            issues.append(f"liabilities[{i}]: name is required")

        # Seniority uniqueness
        seniority = tranche.get("seniority")
        if seniority is None:
            issues.append(f"liabilities[{i}] ({label}): seniority is required")
        elif seniority in seen_seniorities:
            issues.append(
                f"liabilities[{i}] ({label}): seniority {seniority} is not unique"
            )
        else:
            seen_seniorities.add(seniority)

        # Size: must have size_pct or size_abs
        has_size_pct = tranche.get("size_pct") is not None
        has_size_abs = tranche.get("size_abs") is not None
        if not has_size_pct and not has_size_abs:
            issues.append(
                f"liabilities[{i}] ({label}): must specify size_pct or size_abs"
            )

        if has_size_pct:
            total_size_pct += tranche["size_pct"]

    # Warn if size_pct tranches don't sum near 1.0
    if 0 < total_size_pct < 0.99 or total_size_pct > 1.01:
        warnings.append(
            f"liabilities: size_pct values sum to {total_size_pct:.2%} — "
            "expected to sum to ~100%"
        )


def _check_market_assumptions(assumptions: Dict[str, Any], warnings: List[str]) -> None:
    if not assumptions:
        warnings.append(
            "market_assumptions not provided — engine will use default parameters"
        )
        return

    dr = assumptions.get("default_rate")
    if dr is not None and dr > 0.15:
        warnings.append(
            f"market_assumptions.default_rate {dr:.1%} is high — "
            "confirm this is intentional"
        )

    rr = assumptions.get("recovery_rate")
    if rr is not None and rr < 0.30:
        warnings.append(
            f"market_assumptions.recovery_rate {rr:.1%} is very low — "
            "confirm this is intentional"
        )
