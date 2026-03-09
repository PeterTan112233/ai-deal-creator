# AI Deal Creator

An AI-assisted CLO deal structuring workspace built on Claude Code.

The system helps structurers build deals, run scenarios, compare versions, and draft materials — while keeping all official numbers in the hands of deterministic engines and all publications behind human approval.

---

## What it does

| Capability | Status |
|---|---|
| Create a deal from structured inputs | Phase 1 — scaffold |
| Validate deal parameters | Phase 1 — Pydantic schemas |
| Submit scenarios to official engine | Phase 1 — mock engine |
| Compare scenario outputs | Phase 1 — workflow implemented |
| Draft investor summary / IC memo | Phase 1 — workflow scaffold |
| Natural language → scenario translation | Phase 2 — planned |
| Compliance review and approval routing | Phase 3 — planned |
| Publish to investor portal | Phase 3 — planned |

---

## Core principles

1. **Deterministic numbers, generative language.** The LLM never calculates official CLO outputs. All numbers come from the cashflow engine via MCP.
2. **Every answer is grounded.** Each output cites a source object: model run ID, deal schema field, historical deal record, or approved language reference.
3. **Review before release.** External-facing materials require human approval before any publish action.
4. **Auditable by design.** Every workflow action emits a structured audit event.

---

## Project layout

```
ai-deal-creator/
├── CLAUDE.md                   # Hard rules and architecture guidance for Claude Code
├── README.md
├── requirements.txt
│
├── app/                        # Python application
│   ├── domain/                 # Canonical domain models (Deal, Scenario, Tranche, ...)
│   ├── schemas/                # Pydantic validation schemas
│   ├── workflows/              # Orchestration logic (create_deal, run_scenario, compare, ...)
│   ├── services/               # Shared services (audit_logger, ...)
│   ├── prompts/                # LLM prompt templates (separate from logic)
│   ├── api/                    # API routing layer
│   └── tests/                  # Unit and workflow tests
│
├── mcp/                        # Mock MCP stubs (Phase 1 — replaced by real servers in Phase 2+)
│   ├── cashflow_engine/        # Official scenario engine stub
│   └── portfolio_data/         # Pool data stub
│
├── infra/
│   ├── hooks/                  # Claude Code lifecycle hook implementations
│   └── mcp/                    # Real MCP server definitions (Phase 2+)
│
├── .claude/
│   ├── agents/                 # Custom Claude subagent definitions
│   ├── skills/                 # Reusable Claude skills
│   ├── commands/               # Claude Code custom commands
│   └── settings.json           # Project-level Claude Code settings
│
├── data/
│   └── samples/                # Sample deal objects for development and testing
│
├── docs/                       # Project documentation
│   ├── architecture.md
│   ├── workflow.md
│   ├── data-model.md
│   ├── hooks-policy.md
│   └── mcp-map.md
│
└── tests/                      # Integration, evaluation, and policy tests
    ├── evals/
    ├── integration/
    └── policy/
```

---

## Getting started

```bash
# Install dependencies (pydantic + pytest — no other deps required for the CLI)
pip install -r requirements.txt

# Run the test suite
python3 -m pytest app/tests/ -v
```

---

## Running locally (Phase 1 — mock engine)

### CLI demo

```bash
# US BSL deal — baseline scenario
python3 app/main.py

# EU CLO deal
python3 app/main.py --deal eu

# Stress scenario — custom recovery and default rate
python3 app/main.py --deal us --scenario "Stress" --type stress \
  --recovery 0.45 --default-rate 0.06

# EU stress — spread shock
python3 app/main.py --deal eu --type stress --spread-shock 75

# Full JSON output instead of summary
python3 app/main.py --deal us --json
```

### Run all demo scenarios at once

```bash
bash scripts/run_local_demo.sh

# Also print JSON output for each scenario
bash scripts/run_local_demo.sh --json
```

### Optional: FastAPI server (requires fastapi + uvicorn)

```bash
pip install fastapi uvicorn

uvicorn app.api.main:app --reload
# → http://localhost:8000/health
# → POST http://localhost:8000/run-scenario
```

All outputs are clearly labelled **MOCK ENGINE OUTPUT — NOT OFFICIAL**. Audit events are written to `data/audit_log.jsonl`.

---

## Documentation

| Doc | Purpose |
|---|---|
| [docs/architecture.md](docs/architecture.md) | Agent architecture, component responsibilities |
| [docs/workflow.md](docs/workflow.md) | Main end-to-end flows |
| [docs/data-model.md](docs/data-model.md) | Canonical deal object and field definitions |
| [docs/hooks-policy.md](docs/hooks-policy.md) | Hook events and enforcement policy |
| [docs/mcp-map.md](docs/mcp-map.md) | MCP server map and planned integrations |
| [docs/ai_deal_creator_prd.md](docs/ai_deal_creator_prd.md) | Full product requirements document |
