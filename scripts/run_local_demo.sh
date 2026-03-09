#!/usr/bin/env bash
# scripts/run_local_demo.sh
#
# Local demo runner for AI Deal Creator (Phase 1 — mock engine).
# Runs a sequence of representative scenarios and prints results to stdout.
#
# Usage:
#   bash scripts/run_local_demo.sh
#   bash scripts/run_local_demo.sh --json   # also print JSON output for each scenario

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

JSON_FLAG=""
if [[ "${1:-}" == "--json" ]]; then
  JSON_FLAG="--json"
fi

echo "============================================================"
echo " AI Deal Creator — Local MVP Demo  [MOCK ENGINE — Phase 1] "
echo "============================================================"
echo ""

# ---------------------------------------------------------------------------
# Scenario 1: US BSL baseline
# ---------------------------------------------------------------------------
echo "--- Scenario 1: US BSL — Baseline ---"
python3 app/main.py --deal us --scenario "Baseline" --type base $JSON_FLAG
echo ""

# ---------------------------------------------------------------------------
# Scenario 2: US BSL stress — low recoveries
# ---------------------------------------------------------------------------
echo "--- Scenario 2: US BSL — Stress (recovery 45%, default 6%) ---"
python3 app/main.py --deal us --scenario "Stress" --type stress \
  --recovery 0.45 --default-rate 0.06 $JSON_FLAG
echo ""

# ---------------------------------------------------------------------------
# Scenario 3: EU CLO baseline
# ---------------------------------------------------------------------------
echo "--- Scenario 3: EU CLO — Baseline ---"
python3 app/main.py --deal eu --scenario "Baseline" --type base $JSON_FLAG
echo ""

# ---------------------------------------------------------------------------
# Scenario 4: EU CLO stress — spread shock
# ---------------------------------------------------------------------------
echo "--- Scenario 4: EU CLO — Stress (spread shock +75 bps) ---"
python3 app/main.py --deal eu --scenario "Stress" --type stress \
  --spread-shock 75 $JSON_FLAG
echo ""

# ---------------------------------------------------------------------------
# Scenario 5: Minimal deal
# ---------------------------------------------------------------------------
echo "--- Scenario 5: Minimal deal — required fields only ---"
python3 app/main.py --deal minimal --scenario "Baseline" --type base $JSON_FLAG
echo ""

echo "============================================================"
echo " All scenarios complete."
echo " Audit log: data/audit_log.jsonl"
echo "============================================================"
