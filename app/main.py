"""
app/main.py

CLI entrypoint for the AI Deal Creator MVP demo.

Usage:
    python3 app/main.py
    python3 app/main.py --deal eu
    python3 app/main.py --deal us --scenario stress --recovery 0.50

Phase 1: runs the full mock flow and prints a grounded summary to stdout.
Phase 2+: replace model_engine_service with real cashflow-engine-mcp.
"""

import argparse
import json
import sys
import os

# Make sure project root is on the path when running directly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.workflows.run_scenario_workflow import run_scenario_workflow


# ---------------------------------------------------------------------------
# Sample deal loader
# ---------------------------------------------------------------------------

SAMPLE_FILE = "data/samples/sample_deal_inputs.json"

DEAL_LABELS = {
    "us":      "US BSL",
    "eu":      "EU CLO",
    "minimal": "Minimal",
}


def load_sample_deal(key: str) -> dict:
    label = DEAL_LABELS.get(key)
    if not label:
        print(f"ERROR: unknown deal key '{key}'. Choose from: {list(DEAL_LABELS.keys())}")
        sys.exit(1)

    with open(SAMPLE_FILE) as f:
        data = json.load(f)

    for deal in data["deals"]:
        if label in deal.get("_label", ""):
            return deal

    print(f"ERROR: no sample deal matching '{label}' in {SAMPLE_FILE}")
    sys.exit(1)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="AI Deal Creator — local MVP demo (mock engine)"
    )
    parser.add_argument(
        "--deal",
        default="us",
        choices=list(DEAL_LABELS.keys()),
        help="Which sample deal to load (default: us)",
    )
    parser.add_argument(
        "--scenario",
        default="Baseline",
        help="Scenario name label (default: Baseline)",
    )
    parser.add_argument(
        "--type",
        default="base",
        choices=["base", "stress", "custom"],
        dest="scenario_type",
        help="Scenario type (default: base)",
    )
    parser.add_argument(
        "--recovery",
        type=float,
        default=None,
        help="Override recovery_rate (e.g. 0.50 = 50%%)",
    )
    parser.add_argument(
        "--default-rate",
        type=float,
        default=None,
        dest="default_rate",
        help="Override default_rate (e.g. 0.05 = 5%%)",
    )
    parser.add_argument(
        "--spread-shock",
        type=float,
        default=None,
        dest="spread_shock_bps",
        help="Override spread_shock_bps (e.g. 75)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="output_json",
        help="Output full result as JSON instead of the summary",
    )
    return parser.parse_args()


def build_overrides(args: argparse.Namespace) -> dict:
    overrides = {}
    if args.recovery is not None:
        overrides["recovery_rate"] = args.recovery
    if args.default_rate is not None:
        overrides["default_rate"] = args.default_rate
    if args.spread_shock_bps is not None:
        overrides["spread_shock_bps"] = args.spread_shock_bps
    return overrides


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args()

    deal_input = load_sample_deal(args.deal)
    overrides = build_overrides(args)

    print(f"\nAI Deal Creator — local demo  [MOCK ENGINE — Phase 1]\n")
    print(f"  Deal:     {deal_input.get('name')}")
    print(f"  Scenario: {args.scenario} ({args.scenario_type})")
    if overrides:
        print(f"  Overrides: {overrides}")
    print()

    result = run_scenario_workflow(
        deal_input=deal_input,
        scenario_name=args.scenario,
        scenario_type=args.scenario_type,
        parameter_overrides=overrides,
        actor="local-demo",
    )

    # --- Error path ---
    if "error" in result:
        print("VALIDATION FAILED")
        print(f"  {result['error']}")
        if result.get("validation"):
            for issue in result["validation"].get("issues", []):
                print(f"  • {issue}")
        sys.exit(1)

    # --- JSON output ---
    if args.output_json:
        output = {
            "validation": result["validation"],
            "scenario_request": result["scenario_request"],
            "scenario_result": result["scenario_result"],
            "is_mock": result["is_mock"],
            "audit_events": result["audit_events"],
        }
        print(json.dumps(output, indent=2, default=str))
        return

    # --- Summary output ---
    print(result["summary"])

    # Validation warnings
    warnings = result.get("validation", {}).get("warnings", [])
    if warnings:
        print("VALIDATION WARNINGS")
        print("-" * 40)
        for w in warnings:
            print(f"  ⚠ {w}")
        print()

    print(f"Audit events logged: {len(result['audit_events'])}")
    print(f"Audit log:           data/audit_log.jsonl\n")


if __name__ == "__main__":
    main()
