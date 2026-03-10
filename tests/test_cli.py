"""
tests/test_cli.py

Tests for app/cli.py — the AI Deal Creator command-line interface.

Uses subprocess to invoke the CLI as a child process, validating stdout,
stderr, and exit codes. Also tests direct function-level behaviour (main()
called with argv list) for speed.

All tests use data/samples/sample_deal_inputs.json as the deal source.
"""

import json
import os
import subprocess
import sys
import tempfile

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE = "data/samples/sample_deal_inputs.json"
PYTHON  = sys.executable
CLI     = [PYTHON, "-m", "app.cli"]


def _run(*args, cwd=None) -> subprocess.CompletedProcess:
    return subprocess.run(
        CLI + list(args),
        capture_output=True,
        text=True,
        cwd=cwd or os.getcwd(),
    )


def _run_json(*args) -> dict:
    """Run CLI with --format json and parse stdout."""
    result = _run(*args, "--format", "json")
    assert result.returncode == 0, f"CLI failed:\n{result.stderr}"
    return json.loads(result.stdout)


# ---------------------------------------------------------------------------
# Global / help
# ---------------------------------------------------------------------------

class TestHelp:

    def test_help_exits_zero(self):
        r = _run("--help")
        assert r.returncode == 0

    def test_help_lists_commands(self):
        r = _run("--help")
        for cmd in ("pipeline", "analyze", "optimize", "benchmark", "draft", "compare"):
            assert cmd in r.stdout

    def test_analyze_help_exits_zero(self):
        assert _run("analyze", "--help").returncode == 0

    def test_pipeline_help_exits_zero(self):
        assert _run("pipeline", "--help").returncode == 0

    def test_missing_command_exits_nonzero(self):
        assert _run().returncode != 0

    def test_unknown_command_exits_nonzero(self):
        assert _run("nonexistent-command").returncode != 0

    def test_missing_deal_file_exits_nonzero(self):
        r = _run("analyze", "does_not_exist.json")
        assert r.returncode != 0
        assert "not found" in r.stderr.lower() or "error" in r.stderr.lower()


# ---------------------------------------------------------------------------
# analyze command
# ---------------------------------------------------------------------------

class TestAnalyzeCommand:

    def test_returns_zero(self):
        assert _run("analyze", SAMPLE).returncode == 0

    def test_text_output_contains_demo_tag(self):
        r = _run("analyze", SAMPLE)
        assert "demo" in r.stdout.lower()

    def test_text_output_contains_irr(self):
        r = _run("analyze", SAMPLE)
        assert "IRR" in r.stdout

    def test_json_output_has_key_metrics(self):
        data = _run_json("analyze", SAMPLE)
        assert "key_metrics" in data

    def test_json_output_base_irr_positive(self):
        data = _run_json("analyze", SAMPLE)
        assert data["key_metrics"]["base_equity_irr"] > 0

    def test_json_output_scenario_suite_present(self):
        data = _run_json("analyze", SAMPLE)
        assert "scenario_suite" in data

    def test_actor_flag_accepted(self):
        r = _run("analyze", SAMPLE, "--actor", "test-user")
        assert r.returncode == 0

    def test_out_flag_writes_file(self):
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            out_path = f.name
        try:
            r = _run("analyze", SAMPLE, "--out", out_path)
            assert r.returncode == 0
            assert os.path.exists(out_path)
            with open(out_path) as f:
                content = f.read()
            assert "IRR" in content
        finally:
            os.unlink(out_path)


# ---------------------------------------------------------------------------
# optimize command
# ---------------------------------------------------------------------------

class TestOptimizeCommand:

    def test_returns_zero(self):
        r = _run("optimize", SAMPLE, "--aaa-min", "0.60", "--aaa-max", "0.63", "--aaa-step", "0.015")
        assert r.returncode == 0

    def test_text_output_contains_optimal(self):
        r = _run("optimize", SAMPLE, "--aaa-min", "0.60", "--aaa-max", "0.62", "--aaa-step", "0.01")
        assert "Optimal" in r.stdout or "OPTIMIZER" in r.stdout

    def test_json_output_has_optimal_key(self):
        data = _run_json("optimize", SAMPLE,
                         "--aaa-min", "0.60", "--aaa-max", "0.62", "--aaa-step", "0.01")
        assert "optimal" in data

    def test_json_output_feasibility_table(self):
        data = _run_json("optimize", SAMPLE,
                         "--aaa-min", "0.60", "--aaa-max", "0.62", "--aaa-step", "0.01")
        assert len(data.get("feasibility_table", [])) >= 1

    def test_aaa_step_controls_candidates(self):
        # step=0.01 over [0.60,0.62] → 3 candidates
        data = _run_json("optimize", SAMPLE,
                         "--aaa-min", "0.60", "--aaa-max", "0.62", "--aaa-step", "0.01")
        assert len(data["feasibility_table"]) == 3


# ---------------------------------------------------------------------------
# benchmark command
# ---------------------------------------------------------------------------

class TestBenchmarkCommand:

    def test_returns_zero(self):
        r = _run("benchmark", SAMPLE, "--vintage", "2024", "--region", "US")
        assert r.returncode == 0

    def test_text_output_contains_demo(self):
        r = _run("benchmark", SAMPLE, "--vintage", "2024", "--region", "US")
        assert "DEMO" in r.stdout or "demo" in r.stdout

    def test_json_output_has_overall_position(self):
        data = _run_json("benchmark", SAMPLE, "--vintage", "2024", "--region", "US")
        assert "overall_position" in data
        assert data["overall_position"] in ("strong", "median", "weak", "mixed")

    def test_json_output_vintage_matches(self):
        data = _run_json("benchmark", SAMPLE, "--vintage", "2023", "--region", "US")
        assert data["vintage"] == 2023


# ---------------------------------------------------------------------------
# draft command
# ---------------------------------------------------------------------------

class TestDraftCommand:

    def test_returns_zero(self):
        assert _run("draft", SAMPLE).returncode == 0

    def test_text_output_non_empty(self):
        r = _run("draft", SAMPLE)
        assert len(r.stdout.strip()) > 100

    def test_json_output_has_draft(self):
        data = _run_json("draft", SAMPLE)
        assert "draft" in data
        assert data["draft"] is not None

    def test_json_output_requires_approval(self):
        data = _run_json("draft", SAMPLE)
        assert data.get("requires_approval") is True

    def test_json_output_not_approved(self):
        data = _run_json("draft", SAMPLE)
        assert data["approved"] is False


# ---------------------------------------------------------------------------
# pipeline command
# ---------------------------------------------------------------------------

class TestPipelineCommand:

    def test_returns_zero(self):
        r = _run("pipeline", SAMPLE, "--no-draft",
                 "--aaa-min", "0.60", "--aaa-max", "0.62", "--aaa-step", "0.01")
        assert r.returncode == 0

    def test_text_output_contains_all_stages(self):
        r = _run("pipeline", SAMPLE, "--no-draft",
                 "--aaa-min", "0.60", "--aaa-max", "0.62", "--aaa-step", "0.01")
        assert "ANALYTICS" in r.stdout
        assert "OPTIMIZER" in r.stdout
        assert "BENCHMARK" in r.stdout

    def test_json_output_has_stages(self):
        data = _run_json("pipeline", SAMPLE, "--no-draft",
                         "--aaa-min", "0.60", "--aaa-max", "0.62", "--aaa-step", "0.01")
        assert "stages" in data
        assert data["stages"]["analytics"] is not None

    def test_no_optimizer_flag(self):
        data = _run_json("pipeline", SAMPLE, "--no-optimizer", "--no-benchmark", "--no-draft")
        assert data["stages"]["optimizer"] is None

    def test_pipeline_id_in_json(self):
        data = _run_json("pipeline", SAMPLE, "--no-optimizer", "--no-benchmark", "--no-draft")
        assert data["pipeline_id"].startswith("pipeline-")

    def test_is_mock_in_json(self):
        data = _run_json("pipeline", SAMPLE, "--no-optimizer", "--no-benchmark", "--no-draft")
        assert data["is_mock"] is True


# ---------------------------------------------------------------------------
# compare command
# ---------------------------------------------------------------------------

class TestCompareCommand:

    def test_returns_zero(self):
        r = _run("compare", SAMPLE, SAMPLE)
        assert r.returncode == 0

    def test_text_output_non_empty(self):
        r = _run("compare", SAMPLE, SAMPLE)
        assert len(r.stdout.strip()) > 0

    def test_json_output_has_deal_comparison(self):
        data = _run_json("compare", SAMPLE, SAMPLE)
        assert "deal_comparison" in data

    def test_missing_v2_file_exits_nonzero(self):
        r = _run("compare", SAMPLE)
        assert r.returncode != 0


# ---------------------------------------------------------------------------
# Output routing
# ---------------------------------------------------------------------------

class TestOutputRouting:

    def test_json_format_is_parseable(self):
        r = _run("analyze", SAMPLE, "--format", "json")
        assert r.returncode == 0
        data = json.loads(r.stdout)
        assert isinstance(data, dict)

    def test_text_format_is_not_json(self):
        r = _run("analyze", SAMPLE, "--format", "text")
        assert r.returncode == 0
        with pytest.raises((json.JSONDecodeError, ValueError)):
            json.loads(r.stdout)

    def test_out_file_json(self):
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            out_path = f.name
        try:
            r = _run("analyze", SAMPLE, "--format", "json", "--out", out_path)
            assert r.returncode == 0
            with open(out_path) as f:
                data = json.load(f)
            assert "key_metrics" in data
        finally:
            os.unlink(out_path)
