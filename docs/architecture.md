# Architecture — AI Deal Creator

## Overview

AI Deal Creator is a **controlled orchestration layer** built on top of an existing CLO
structuring and analytics stack. It does not replace the cashflow engine, rating models,
or legal systems of record. It connects them through MCP, enforces controls through hooks,
and uses Claude subagents for interpretation, drafting, and workflow assistance.

```
User
  │
  ▼
deal-orchestrator (supervisor agent)
  │
  ├── deal-schema-agent          validate and normalize deal inputs
  ├── structure-analyst          tranche logic and parameter review
  ├── scenario-runner            engine submission and output collection
  ├── analytics-explainer-agent  output interpretation and driver analysis
  ├── document-drafter           investor summary, IC memo, FAQ
  └── compliance-reviewer        pre-publication screening
          │
          ▼
     [publish-agent]             (Phase 3 — not yet implemented)
```

All agents are defined in `.claude/agents/`. Claude Code uses the agent description
field to decide when to delegate.

---

## Component layers

### 1. Claude agent layer (`.claude/`)

| Path | Contents |
|---|---|
| `.claude/agents/` | Subagent definitions — name, description, tool permissions, instructions |
| `.claude/skills/` | Reusable task skills: `/compare-scenarios`, `/draft-investor-summary`, `/committee-memo` |
| `.claude/commands/` | Custom slash commands (Phase 2+) |
| `.claude/settings.json` | Project-level permissions and MCP server config |

Agents interact with the system through tools and MCP calls.
They do not directly read or write the database — they go through workflows or MCP.

### 2. Application layer (`app/`)

| Path | Purpose |
|---|---|
| `app/domain/` | Canonical Python dataclasses: Deal, Collateral, Tranche, Structure, Scenario, Approval |
| `app/schemas/` | Pydantic validation schemas — enforced at workflow entry points |
| `app/workflows/` | Orchestration functions: create_deal, run_scenario, compare_scenarios, generate_investor_summary |
| `app/services/` | Shared services: audit_logger |
| `app/prompts/` | Prompt templates — stored separately from business logic |
| `app/api/` | API surface (Phase 2+) |
| `app/tests/` | Unit and workflow tests |

**Key rule:** Business logic lives in `app/`. Prompts live in `app/prompts/`.
They must never be combined in the same file.

### 3. Infrastructure layer (`infra/`)

| Path | Purpose |
|---|---|
| `infra/hooks/` | Claude Code lifecycle hook scripts (Python) |
| `infra/mcp/` | Real MCP server definitions (Phase 2+) |

Hooks enforce policy deterministically. They run regardless of what the model decides.
See [hooks-policy.md](hooks-policy.md) for the full hook policy matrix.

### 4. MCP layer (`mcp/` and `infra/mcp/`)

| Path | Purpose |
|---|---|
| `mcp/` | Phase 1 mock stubs — Python modules that simulate MCP tool calls |
| `infra/mcp/` | Phase 2+ real MCP server implementations |

MCP servers are the integration backbone. They expose enterprise data and tools
to Claude agents in a controlled, auditable way.
See [mcp-map.md](mcp-map.md) for the full server map.

---

## Subagent responsibilities

### deal-orchestrator
Entry point for all user requests. Classifies intent, delegates to specialists,
assembles the final response. Has `Agent` tool access — can spawn other subagents.
Never computes outputs directly.

### deal-schema-agent
Maps raw inputs to the canonical deal schema. Validates required fields.
Produces a validation report before any workflow runs.

### structure-analyst
Reviews deal parameters and tranche stack. Identifies missing or inconsistent
parameters. Proposes first-pass configurations. Explains structural tradeoffs.
Does not invoke the engine — delegates run requests to scenario-runner.

### scenario-runner
Translates validated scenario parameters into engine payloads.
Submits to `cashflow-engine-mcp`. Collects and labels outputs with
`source = "model_runner"` and `run_id`. Never computes outputs independently.

### analytics-explainer-agent
Interprets official engine outputs. Identifies drivers of differences between
scenarios. Explains threshold breaches. Compares to historical comps.
All interpretation is clearly labelled `[generated]` vs `[calculated]`.

### document-drafter
Drafts investor summaries, IC memos, FAQs, and change notes from
grounded engine outputs and approved language sources.
All drafts are produced with `approved = False`.

### compliance-reviewer
Screens drafts before internal review or external publication.
Checks: source grounding, approved language, disclaimer completeness,
no unsupported market claims, required approvals present.
Returns: PASS | PASS WITH NOTES | FAIL.

---

## Data flow — new deal creation

```
User input
  → deal-schema-agent         (validate + normalize)
  → create_deal_workflow      (schema check + pool validation via portfolio-data-mcp)
  → scenario-runner           (submit to cashflow-engine-mcp)
  → analytics-explainer-agent (interpret outputs)
  → document-drafter          (draft structuring note)
  → audit_logger              (record all events)
```

---

## Design decisions

| Decision | Rationale |
|---|---|
| Dataclasses for domain, Pydantic for schemas | Domain objects are lightweight; validation is explicit and happens only at boundaries |
| Mock MCP stubs in `mcp/` | Enables full workflow testing without a real engine in Phase 1 |
| `_mock` tag on all stub outputs | Prevents mock data from being mistaken for official results |
| Audit logger writes append-only JSONL | Simple, debuggable, no database dependency in Phase 1 |
| Prompts in `app/prompts/` | Keeps LLM instructions versioned, reviewable, and separate from logic |
