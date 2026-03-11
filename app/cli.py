"""
app/cli.py

AI Deal Creator — command-line interface.

Usage
-----
  python3 -m app.cli <command> <deal_file> [options]
  python3 app/cli.py <command> <deal_file> [options]

Commands
--------
  pipeline   Run the full analytics → optimizer → benchmark → draft pipeline.
  analyze    Run the 4-scenario analytics suite (+ optional sensitivity).
  optimize   Sweep AAA size to find the optimal tranche structure.
  benchmark  Compare the deal against historical CLO cohort benchmarks.
  draft      Generate an investor summary draft from the base-case scenario.
  compare    Compare two deal versions (structural diff + scenario diff).

Global options
--------------
  --actor NAME        Caller identity written to the audit trail. Default: "cli".
  --format text|json  Output format. "text" prints a human-readable summary;
                      "json" prints the raw result dict. Default: "text".
  --out FILE          Write output to FILE instead of stdout.

IMPORTANT: All outputs are tagged [demo] and require Phase 2 production
engine for official use. Not for investment decisions.
"""

import argparse
import json
import sys
import os

# Allow running from any directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_deal(path: str) -> dict:
    """Load a deal dict from a JSON file.  Accepts both raw deal dicts and
    the sample_deal_inputs.json envelope (picks the first deal)."""
    with open(path) as f:
        data = json.load(f)
    # Handle sample_deal_inputs.json envelope
    if "deals" in data and isinstance(data["deals"], list):
        return data["deals"][0]
    return data


def _emit(result: dict, fmt: str, out_file: str | None) -> None:
    """Write the result to stdout or a file."""
    if fmt == "json":
        text = json.dumps(result, indent=2, default=str)
    else:
        text = _text_summary(result)

    if out_file:
        with open(out_file, "w") as f:
            f.write(text)
            f.write("\n")
        print(f"Output written to {out_file}", file=sys.stderr)
    else:
        print(text)


def _text_summary(result: dict) -> str:
    """Produce a human-readable text summary from a workflow result dict."""
    lines = []

    # Pipeline result
    if "pipeline_summary" in result and result["pipeline_summary"]:
        lines.append(result["pipeline_summary"])
        return "\n".join(lines)

    # Analytics result
    if "analytics_report" in result and result["analytics_report"]:
        lines.append(result["analytics_report"])
        return "\n".join(lines)

    # Optimizer result
    if "feasibility_table" in result:
        opt = result.get("optimal")
        lines.append("=" * 64)
        lines.append("  OPTIMIZER RESULT  [demo]")
        lines.append("=" * 64)
        if opt:
            lines.append(f"  Optimal AAA size : {opt['aaa_size_pct']:.1%}")
            lines.append(f"  Equity size      : {opt['equity_size_pct']:.1%}")
            lines.append(f"  Equity IRR [demo]: {opt['equity_irr']:.2%}")
            lines.append(f"  OC cushion [demo]: {opt['oc_cushion_aaa']:+.1%}")
            n = len(result.get("feasibility_table", []))
            nf = len(result.get("frontier", []))
            lines.append(f"  ({nf} feasible of {n} candidates)")
        else:
            reason = result.get("infeasible_reason", "No feasible structure found.")
            lines.append(f"  INFEASIBLE: {reason}")
        lines.append("=" * 64)
        return "\n".join(lines)

    # Benchmark result
    if "comparison_report" in result and result["comparison_report"]:
        lines.append(result["comparison_report"])
        return "\n".join(lines)

    # Draft result
    if "draft_markdown" in result and result["draft_markdown"]:
        lines.append(result["draft_markdown"])
        return "\n".join(lines)

    # Compare result
    if "deal_comparison" in result:
        lines.append("=" * 64)
        lines.append("  COMPARE RESULT  [demo]")
        lines.append("=" * 64)
        if result.get("summary"):
            lines.append(result["summary"])
        return "\n".join(lines)

    # Template suite result
    if "templates_run" in result and "comparison_table" in result:
        lines += [
            "=" * 72,
            f"  TEMPLATE SUITE  [demo]  —  {result['templates_run']} templates run",
            "=" * 72,
            "",
            f"  {'Template':<28} {'Type':<12} {'IRR':>8}  {'OC Cush':>9}",
            "  " + "-" * 60,
        ]
        for r in result.get("results", []):
            if r["status"] != "complete":
                lines.append(f"  {r['template_name']:<28} FAILED")
                continue
            irr = r["outputs"].get("equity_irr")
            oc  = r["outputs"].get("oc_cushion_aaa")
            irr_s = f"{irr:.1%}" if irr is not None else "n/a"
            oc_s  = f"{oc:+.1%}" if oc  is not None else "n/a"
            lines.append(f"  {r['template_name']:<28} {r['scenario_type']:<12} {irr_s:>8}  {oc_s:>9}")
        if result.get("comparison_table"):
            lines += ["", "  Best / Worst per metric:"]
            for row in result["comparison_table"]:
                lines.append(f"    {row['metric']}: best={row['best_template']}  worst={row['worst_template']}")
        lines += ["", "=" * 72]
        return "\n".join(lines)

    # Portfolio stress result
    if "stress_id" in result and "risk_ranking" in result:
        if result.get("portfolio_report"):
            lines.append(result["portfolio_report"])
            return "\n".join(lines)

    # Portfolio analytics result
    if "portfolio_id" in result and "concentration" in result:
        if result.get("portfolio_report"):
            lines.append(result["portfolio_report"])
            return "\n".join(lines)

    # Template list result
    if "templates" in result and "total" in result:
        lines += [
            "=" * 64,
            f"  SCENARIO TEMPLATES  ({result['total']} available)  [demo]",
            "=" * 64,
            f"  {'ID':<34} {'Type':<12} {'Tags'}",
            "  " + "-" * 60,
        ]
        for t in result.get("templates", []):
            tags = ", ".join(t.get("tags", []))
            lines.append(f"  {t['template_id']:<34} {t['scenario_type']:<12} {tags}")
        lines.append("=" * 64)
        return "\n".join(lines)

    # Fallback
    return json.dumps(result, indent=2, default=str)


def _exit_error(msg: str, code: int = 1) -> None:
    print(f"Error: {msg}", file=sys.stderr)
    sys.exit(code)


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

def cmd_pipeline(args: argparse.Namespace) -> dict:
    from app.workflows.full_pipeline_workflow import full_pipeline_workflow

    optimizer_kwargs = {}
    if args.aaa_min is not None:
        optimizer_kwargs["aaa_min"] = args.aaa_min
    if args.aaa_max is not None:
        optimizer_kwargs["aaa_max"] = args.aaa_max
    if args.aaa_step is not None:
        optimizer_kwargs["aaa_step"] = args.aaa_step

    deal = _load_deal(args.deal_file)
    return full_pipeline_workflow(
        deal,
        run_sensitivity=args.sensitivity,
        run_optimizer=not args.no_optimizer,
        run_benchmark=not args.no_benchmark,
        run_draft=not args.no_draft,
        vintage=args.vintage,
        region=args.region,
        optimizer_kwargs=optimizer_kwargs or None,
        actor=args.actor,
    )


def cmd_analyze(args: argparse.Namespace) -> dict:
    from app.workflows.deal_analytics_workflow import deal_analytics_workflow

    deal = _load_deal(args.deal_file)
    return deal_analytics_workflow(
        deal,
        run_sensitivity=args.sensitivity,
        actor=args.actor,
    )


def cmd_optimize(args: argparse.Namespace) -> dict:
    from app.workflows.tranche_optimizer_workflow import tranche_optimizer_workflow

    deal = _load_deal(args.deal_file)
    kwargs = {}
    if args.aaa_min is not None:
        kwargs["aaa_min"] = args.aaa_min
    if args.aaa_max is not None:
        kwargs["aaa_max"] = args.aaa_max
    if args.aaa_step is not None:
        kwargs["aaa_step"] = args.aaa_step
    if args.oc_floor is not None:
        kwargs["oc_floor"] = args.oc_floor
    return tranche_optimizer_workflow(deal, actor=args.actor, **kwargs)


def cmd_benchmark(args: argparse.Namespace) -> dict:
    from app.workflows.deal_analytics_workflow import deal_analytics_workflow
    from app.workflows.benchmark_comparison_workflow import benchmark_comparison_workflow

    deal = _load_deal(args.deal_file)
    # Need a scenario output — run analytics to get base outputs
    analytics = deal_analytics_workflow(deal, run_sensitivity=False, actor=args.actor)
    if analytics.get("error"):
        _exit_error(f"Analytics failed: {analytics['error']}")

    results = analytics.get("scenario_suite", {}).get("results", [])
    base = next((r for r in results if r["scenario_name"] == "Base"), results[0] if results else None)
    if not base:
        _exit_error("No base scenario outputs available for benchmark.")

    return benchmark_comparison_workflow(
        deal_input=deal,
        scenario_outputs=base["outputs"],
        vintage=args.vintage,
        region=args.region,
        actor=args.actor,
    )


def cmd_draft(args: argparse.Namespace) -> dict:
    from app.workflows.run_scenario_workflow import run_scenario_workflow
    from app.workflows.generate_investor_summary_workflow import generate_investor_summary_workflow

    deal = _load_deal(args.deal_file)
    base = run_scenario_workflow(
        deal, scenario_name="Baseline", scenario_type="base", actor=args.actor
    )
    if base.get("error"):
        _exit_error(f"Scenario run failed: {base['error']}")

    return generate_investor_summary_workflow(
        deal_input=deal,
        scenario_result=base.get("scenario_result", {}),
        scenario_request=base.get("scenario_request"),
        actor=args.actor,
    )


def cmd_compare(args: argparse.Namespace) -> dict:
    from app.workflows.compare_versions_workflow import compare_versions_workflow

    v1 = _load_deal(args.v1_file)
    v2 = _load_deal(args.v2_file)
    return compare_versions_workflow(v1_deal=v1, v2_deal=v2, actor=args.actor)


def cmd_template(args: argparse.Namespace) -> dict:
    """Run a single named template against a deal."""
    from app.workflows.run_scenario_workflow import run_scenario_workflow
    from app.services import scenario_template_service

    try:
        params = scenario_template_service.apply_template(args.template_id)
    except KeyError:
        _exit_error(f"Unknown template '{args.template_id}'. "
                    f"Run 'templates' to list available templates.")

    tmpl = scenario_template_service.get_template(args.template_id)
    deal = _load_deal(args.deal_file)
    return run_scenario_workflow(
        deal_input=deal,
        scenario_name=tmpl["name"],
        scenario_type=tmpl["scenario_type"],
        parameter_overrides=params,
        actor=args.actor,
    )


def cmd_template_suite(args: argparse.Namespace) -> dict:
    """Run all (or filtered) templates against a deal."""
    from app.workflows.template_suite_workflow import template_suite_workflow

    deal = _load_deal(args.deal_file)
    template_ids = args.templates.split(",") if args.templates else None
    return template_suite_workflow(
        deal,
        template_ids=template_ids,
        scenario_type=args.scenario_type,
        tag=args.tag,
        actor=args.actor,
    )


def cmd_portfolio_stress(args: argparse.Namespace) -> dict:
    """Run stress template battery across multiple deals, rank by vulnerability."""
    from app.workflows.portfolio_stress_workflow import portfolio_stress_workflow

    deal_inputs = [_load_deal(f) for f in args.deal_files]
    template_ids = args.templates.split(",") if getattr(args, "templates", None) else None
    return portfolio_stress_workflow(
        deal_inputs,
        template_ids=template_ids,
        scenario_type=getattr(args, "scenario_type", None),
        tag=getattr(args, "tag", None),
        actor=args.actor,
    )


def cmd_portfolio(args: argparse.Namespace) -> dict:
    """Run base-case analytics across multiple deals and return a portfolio summary."""
    from app.workflows.portfolio_analytics_workflow import portfolio_analytics_workflow

    deal_inputs = [_load_deal(f) for f in args.deal_files]
    metrics = args.metrics.split(",") if getattr(args, "metrics", None) else None
    return portfolio_analytics_workflow(deal_inputs, metrics=metrics, actor=args.actor)


def cmd_templates(_args: argparse.Namespace) -> dict:
    """List all available scenario templates."""
    from app.services import scenario_template_service

    templates = scenario_template_service.list_templates(
        scenario_type=getattr(_args, "scenario_type", None),
        tag=getattr(_args, "tag", None),
    )
    return {"total": len(templates), "templates": templates}


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    # Shared global options inherited by every subcommand
    _globals = argparse.ArgumentParser(add_help=False)
    _globals.add_argument("--actor", default="cli", help="Caller identity for audit trail.")
    _globals.add_argument(
        "--format", choices=["text", "json"], default="text",
        help="Output format (default: text).",
    )
    _globals.add_argument("--out", metavar="FILE", help="Write output to FILE.")

    parser = argparse.ArgumentParser(
        prog="ai-deal-creator",
        description="AI Deal Creator CLI — CLO deal analytics workspace [demo]",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=[_globals],
        epilog=(
            "All outputs are tagged [demo]. Not for investment decisions.\n\n"
            "Examples:\n"
            "  python3 -m app.cli pipeline deal.json\n"
            "  python3 -m app.cli analyze deal.json --sensitivity\n"
            "  python3 -m app.cli optimize deal.json --aaa-min 0.55 --aaa-max 0.72\n"
            "  python3 -m app.cli benchmark deal.json --vintage 2024 --region US\n"
            "  python3 -m app.cli draft deal.json --format json\n"
            "  python3 -m app.cli compare v1.json v2.json\n"
        ),
    )

    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")
    subparsers.required = True

    # ---- pipeline ----
    p = subparsers.add_parser("pipeline", parents=[_globals], help="Run full analytics pipeline.")
    p.add_argument("deal_file", help="Path to deal JSON file.")
    p.add_argument("--sensitivity", action="store_true", help="Include CDR/RR sensitivity sweeps.")
    p.add_argument("--no-optimizer", action="store_true", help="Skip optimizer stage.")
    p.add_argument("--no-benchmark", action="store_true", help="Skip benchmark stage.")
    p.add_argument("--no-draft", action="store_true", help="Skip draft stage.")
    p.add_argument("--vintage", type=int, help="Benchmark vintage year override.")
    p.add_argument("--region", help="Benchmark region override (US or EU).")
    _add_aaa_args(p)

    # ---- analyze ----
    p = subparsers.add_parser("analyze", parents=[_globals], help="Run 4-scenario analytics suite.")
    p.add_argument("deal_file", help="Path to deal JSON file.")
    p.add_argument("--sensitivity", action="store_true", help="Include CDR/RR sensitivity sweeps.")

    # ---- optimize ----
    p = subparsers.add_parser("optimize", parents=[_globals],
                              help="Sweep AAA size to find optimal structure.")
    p.add_argument("deal_file", help="Path to deal JSON file.")
    _add_aaa_args(p)
    p.add_argument("--oc-floor", type=float, metavar="FLOAT",
                   help="Minimum OC cushion constraint (default 0.18).")

    # ---- benchmark ----
    p = subparsers.add_parser("benchmark", parents=[_globals],
                              help="Compare deal to historical benchmarks.")
    p.add_argument("deal_file", help="Path to deal JSON file.")
    p.add_argument("--vintage", type=int, help="Vintage year (default: inferred from deal).")
    p.add_argument("--region", help="Region (US or EU; default: inferred from deal).")

    # ---- draft ----
    p = subparsers.add_parser("draft", parents=[_globals],
                              help="Generate investor summary draft.")
    p.add_argument("deal_file", help="Path to deal JSON file.")

    # ---- compare ----
    p = subparsers.add_parser("compare", parents=[_globals],
                              help="Structural diff between two deal versions.")
    p.add_argument("v1_file", help="Path to version-1 deal JSON file.")
    p.add_argument("v2_file", help="Path to version-2 deal JSON file.")

    # ---- portfolio-stress ----
    p = subparsers.add_parser("portfolio-stress", parents=[_globals],
                              help="Run stress template battery across multiple deals.")
    p.add_argument("deal_files", nargs="+", help="Paths to deal JSON files.")
    p.add_argument("--templates", metavar="ID1,ID2,...",
                   help="Comma-separated template IDs (default: all stress templates).")
    p.add_argument("--scenario-type", help="Filter templates by type.")
    p.add_argument("--tag", help="Filter templates by tag.")

    # ---- portfolio ----
    p = subparsers.add_parser("portfolio", parents=[_globals],
                              help="Cross-deal portfolio analytics (base-case per deal).")
    p.add_argument("deal_files", nargs="+", help="Paths to deal JSON files.")
    p.add_argument("--metrics", metavar="M1,M2,...",
                   help="Comma-separated metrics to include in rankings.")

    # ---- templates ----
    p = subparsers.add_parser("templates", parents=[_globals],
                              help="List available scenario templates.")
    p.add_argument("--scenario-type", help="Filter by type (base, stress, regulatory).")
    p.add_argument("--tag", help="Filter by tag (e.g. historical, standard).")

    # ---- template ----
    p = subparsers.add_parser("template", parents=[_globals],
                              help="Run a single named scenario template.")
    p.add_argument("deal_file", help="Path to deal JSON file.")
    p.add_argument("template_id", help="Template ID (e.g. gfc-2008, covid-2020, base).")

    # ---- template-suite ----
    p = subparsers.add_parser("template-suite", parents=[_globals],
                              help="Run all (or filtered) templates against a deal.")
    p.add_argument("deal_file", help="Path to deal JSON file.")
    p.add_argument("--templates", metavar="ID1,ID2,...",
                   help="Comma-separated template IDs (default: all).")
    p.add_argument("--scenario-type", help="Filter by scenario_type.")
    p.add_argument("--tag", help="Filter by tag.")

    return parser


def _add_aaa_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--aaa-min", type=float, metavar="FLOAT",
                   help="Minimum AAA size to test (e.g. 0.55).")
    p.add_argument("--aaa-max", type=float, metavar="FLOAT",
                   help="Maximum AAA size to test (e.g. 0.72).")
    p.add_argument("--aaa-step", type=float, metavar="FLOAT",
                   help="AAA size step (e.g. 0.005).")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

_COMMAND_MAP = {
    "pipeline":          cmd_pipeline,
    "analyze":           cmd_analyze,
    "optimize":          cmd_optimize,
    "benchmark":         cmd_benchmark,
    "draft":             cmd_draft,
    "compare":           cmd_compare,
    "portfolio":         cmd_portfolio,
    "portfolio-stress":  cmd_portfolio_stress,
    "templates":         cmd_templates,
    "template":          cmd_template,
    "template-suite":    cmd_template_suite,
}


def main(argv=None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    # Validate file existence
    if hasattr(args, "deal_file") and not os.path.exists(args.deal_file):
        _exit_error(f"Deal file not found: {args.deal_file}")
    if hasattr(args, "deal_files"):
        for f in args.deal_files:
            if not os.path.exists(f):
                _exit_error(f"Deal file not found: {f}")
    if hasattr(args, "v1_file") and not os.path.exists(args.v1_file):
        _exit_error(f"File not found: {args.v1_file}")
    if hasattr(args, "v2_file") and not os.path.exists(args.v2_file):
        _exit_error(f"File not found: {args.v2_file}")

    handler = _COMMAND_MAP[args.command]
    try:
        result = handler(args)
    except Exception as exc:
        _exit_error(str(exc))
        return 1

    _emit(result, fmt=args.format, out_file=args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
