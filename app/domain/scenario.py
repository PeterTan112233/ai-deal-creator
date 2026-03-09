from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from datetime import datetime


@dataclass
class Scenario:
    # ------------------------------------------------------------------ #
    # USER INPUT — provided by structurer or scenario-design-agent        #
    # ------------------------------------------------------------------ #
    scenario_id: str
    deal_id: str
    name: str                           # human label, e.g. "Baseline", "Stressed recoveries"
    scenario_type: str = "base"         # base | stress | custom
    parameters: Dict[str, Any] = field(default_factory=dict)
    # parameters must be non-empty before engine submission
    # keys: default_rate, recovery_rate, spread_shock_bps (required)
    #       plus any engine-supported extensions

    # ------------------------------------------------------------------ #
    # SYSTEM METADATA — set by the platform during workflow execution     #
    # ------------------------------------------------------------------ #
    status: str = "draft"               # draft | submitted | official | rejected
    version: int = 1
    created_at: Optional[datetime] = None
    submitted_at: Optional[datetime] = None  # when sent to engine
    completed_at: Optional[datetime] = None  # when engine returned outputs
    created_by: Optional[str] = None

    # ------------------------------------------------------------------ #
    # ENGINE OUTPUT — populated only by model-execution-agent             #
    # source must always be "model_runner" for official runs              #
    # ------------------------------------------------------------------ #
    source: str = "model_runner"        # always "model_runner" — never overridden
    run_id: Optional[str] = None        # engine run reference; set after submission
    outputs: Dict[str, Any] = field(default_factory=dict)
    # outputs are populated from cashflow-engine-mcp only
    # keys are engine-defined: equity_irr, aaa_size_pct, wac, oc_cushion_*, etc.
    # NEVER populate outputs manually — they must come from the engine

    # ------------------------------------------------------------------ #
    # GENERATED NARRATIVE — set by narrative-drafting-agent               #
    # ------------------------------------------------------------------ #
    summary: Optional[str] = None       # plain-English output summary [generated]
    # summary is always labelled [generated] and never replaces official outputs

    notes: Optional[str] = None

    # ------------------------------------------------------------------ #
    # FUTURE EXPANSION (deferred)                                         #
    # parent_scenario_id (for branching), tags, batch_id                  #
    # ------------------------------------------------------------------ #
