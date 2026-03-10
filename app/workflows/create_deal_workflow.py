from typing import Any, Dict, Optional

from app.domain.deal import Deal
from app.domain.collateral import Collateral
from app.domain.structure import Structure
from app.schemas.deal_schema import DealSchema
from app.schemas.collateral_schema import CollateralSchema
from app.schemas.structure_schema import StructureSchema
from app.services import audit_logger, portfolio_data_service


def deal_input_from_domain(
    deal: Deal,
    collateral: Collateral,
    structure: Structure,
    market_assumptions: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Convert domain dataclasses into a deal_input dict compatible with
    run_scenario_workflow (matching deal_input.schema.json).

    This is the bridge between create_deal_workflow (dataclass-based) and
    run_scenario_workflow (dict-based). Call after create_deal_workflow succeeds.

    Parameters
    ----------
    deal                : Deal domain object
    collateral          : Collateral domain object
    structure           : Structure domain object
    market_assumptions  : Optional dict with default_rate, recovery_rate,
                          spread_shock_bps. If None, run_scenario_workflow
                          uses its own defaults.

    Returns a dict matching deal_input.schema.json.
    """
    tranches = []
    for t in structure.tranches:
        tranche_dict: Dict[str, Any] = {
            "tranche_id":     t.tranche_id,
            "name":           t.name,
            "seniority":      t.seniority,
        }
        if t.size_pct is not None:
            tranche_dict["size_pct"] = t.size_pct
        if t.size_abs is not None:
            tranche_dict["size_abs"] = t.size_abs
        if getattr(t, "coupon", None) is not None:
            tranche_dict["coupon"] = t.coupon
        if getattr(t, "target_rating", None) is not None:
            tranche_dict["target_rating"] = t.target_rating
        tranches.append(tranche_dict)

    deal_input: Dict[str, Any] = {
        "deal_id":   deal.deal_id,
        "name":      deal.name,
        "issuer":    deal.issuer,
        "region":    getattr(deal, "region", None),
        "currency":  getattr(deal, "currency", "USD"),
        "manager":   getattr(deal, "manager", None),
        "collateral": {
            "pool_id":          collateral.pool_id,
            "asset_class":      collateral.asset_class,
            "portfolio_size":   collateral.portfolio_size,
            "was":              getattr(collateral, "was", None),
            "warf":             getattr(collateral, "warf", None),
            "wal":              getattr(collateral, "wal", None),
            "diversity_score":  collateral.diversity_score,
            "ccc_bucket":       collateral.ccc_bucket,
        },
        "liabilities": tranches,
    }

    # Strip None values from collateral to keep the dict clean
    deal_input["collateral"] = {
        k: v for k, v in deal_input["collateral"].items() if v is not None
    }

    if market_assumptions:
        deal_input["market_assumptions"] = market_assumptions

    return deal_input


def create_deal_workflow(
    deal: Deal,
    collateral: Collateral,
    structure: Structure,
    actor: str = "system",
) -> dict:
    """
    Validate and register a new deal with its collateral and structure.

    Steps:
    1. Validate inputs via Pydantic schemas
    2. Validate pool via portfolio-data-mcp
    3. Persist deal record (stub)
    4. Emit audit event
    5. Return deal summary
    """
    # --- Validate ---
    DealSchema.model_validate(deal.__dict__)
    CollateralSchema.model_validate(collateral.__dict__)
    StructureSchema.model_validate(structure, from_attributes=True)

    # --- Pool validation via portfolio data service ---
    pool_validation = portfolio_data_service.validate_pool({
        "portfolio_size": collateral.portfolio_size,
        "diversity_score": collateral.diversity_score,
        "ccc_bucket": collateral.ccc_bucket,
    })
    if not pool_validation["valid"]:
        raise ValueError(f"Pool validation failed: {pool_validation['issues']}")

    summary = {
        "deal_id": deal.deal_id,
        "name": deal.name,
        "issuer": deal.issuer,
        "region": deal.region,
        "currency": deal.currency,
        "status": deal.status,
        "version": deal.version,
        "collateral_id": collateral.collateral_id,
        "pool_id": collateral.pool_id,
        "portfolio_size": collateral.portfolio_size,
        "structure_id": structure.structure_id,
        "tranche_count": len(structure.tranches),
    }

    # --- Audit ---
    audit_logger.record_event(
        event_type="deal.created",
        deal_id=deal.deal_id,
        actor=actor,
        payload=summary,
    )

    return summary
