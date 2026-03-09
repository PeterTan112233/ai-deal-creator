# /run-mvp-check

Run a quick health check on the Phase 1 MVP scaffold.

## What this command does

Verifies that the core Phase 1 components are in place and functional.
Does not run real engine integrations — only checks structure and tests.

## Steps

### 1. Check required files exist

Verify the following files are present:

```
CLAUDE.md
README.md
requirements.txt
app/domain/deal.py
app/domain/collateral.py
app/domain/tranche.py
app/domain/structure.py
app/domain/scenario.py
app/domain/market_assumptions.py
app/domain/structural_tests.py
app/schemas/deal_schema.py
app/schemas/collateral_schema.py
app/schemas/tranche_schema.py
app/schemas/structure_schema.py
app/schemas/scenario_schema.py
app/workflows/create_deal_workflow.py
app/workflows/run_scenario_workflow.py
app/workflows/compare_scenarios_workflow.py
app/services/audit_logger.py
mcp/cashflow_engine/mock_engine.py
mcp/portfolio_data/mock_portfolio.py
data/samples/sample_deal.json
infra/hooks/pre_tool_use.py
infra/hooks/post_tool_use.py
infra/hooks/session_start.py
```

### 2. Run unit tests

```bash
python3 -m pytest app/tests/ -v
```

Report: number of tests passed / failed.

### 3. Verify agent definitions

Confirm all 7 agents are present in `.claude/agents/`:
- deal-orchestrator
- deal-schema-agent
- scenario-design-agent
- model-execution-agent
- analytics-explainer-agent
- narrative-drafting-agent
- compliance-review-agent

### 4. Verify skills

Confirm all 4 skills are present in `.claude/skills/`:
- deal-intake
- scenario-comparison
- investor-summary-drafting
- approval-checks

### 5. Output summary

```
MVP CHECK RESULTS
=================
Required files:   PASS | MISSING: [list]
Unit tests:       N passed, M failed
Agents:           N/7 present | MISSING: [list]
Skills:           N/4 present | MISSING: [list]

Overall: READY | NOT READY
```
