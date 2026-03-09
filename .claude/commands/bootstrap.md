# /bootstrap

Set up the workspace for a new deal creation session.

## What this command does

1. Reads `docs/architecture.md` and `CLAUDE.md` to load project rules into context
2. Reads `data/samples/sample_deal.json` to show the canonical deal structure
3. Lists available agents in `.claude/agents/`
4. Lists available skills in `.claude/skills/`
5. Confirms the mock engine is available at `mcp/cashflow_engine/mock_engine.py`
6. Asks the user: "What deal would you like to work on?"

## When to use

- Start of a new Claude Code session on this project
- When context has been cleared and you need to reload project state
- When onboarding a new team member to the workspace

## Steps

Read the following files and summarize their key points:
- `CLAUDE.md` — hard rules
- `docs/architecture.md` — agent structure
- `docs/workflow.md` — available workflows

Then output a session summary:
```
Project: AI Deal Creator
Mode: [Phase 1 — mock engine]

Available agents:
  deal-orchestrator, deal-schema-agent, scenario-design-agent,
  model-execution-agent, analytics-explainer-agent,
  narrative-drafting-agent, compliance-review-agent

Available skills:
  /deal-intake, /scenario-comparison,
  /investor-summary-drafting, /approval-checks

Available commands:
  /bootstrap, /run-mvp-check, /compare-versions, /publish-check

Ready. What deal would you like to work on?
```
