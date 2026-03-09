# AI Deal Creator PRD

**Version:** 1.0  
**Document type:** Product Requirements Document  
**Product concept:** Claude AI Agent + Subagent architecture for a CLO Deal Creator platform  
**Primary mode:** Claude Code / Claude Agent SDK style orchestration with MCP-connected enterprise systems  
**Target users:** CLO structurers, portfolio managers, syndicate / primary desk, product control, investor marketing, risk, compliance, operations  
**Status:** Draft for discovery + architecture alignment

---

## 1. Executive Summary

AI Deal Creator is an enterprise application that sits on top of an existing CLO structuring and analytics stack and turns a traditional parameter-driven deal workflow into an AI-assisted, reviewable, auditable workspace.

The product is designed for a CLO / structured finance environment where users need to:

- build a new deal from portfolio and structural parameters
- compare deal scenarios rapidly
- generate internal and external deal narratives
- answer investor and internal committee questions with grounded outputs
- preserve strict controls around calculations, approvals, auditability, and disclosures

The core idea is **not** to let an LLM calculate structured finance outputs directly. Instead:

- deterministic engines compute all official numbers
- MCP tools expose data, documents, and modeling functions to Claude
- Claude agents and subagents perform orchestration, summarization, drafting, comparison, and workflow assistance
- hooks enforce hard controls before reads, writes, approvals, publishing, and sensitive tool calls

This architecture is especially well suited to Claude Code because Claude Code supports custom subagents, MCP tool integrations, and lifecycle hooks for deterministic control over behavior. Official Anthropic docs describe custom subagents for isolated delegated tasks, MCP for connecting Claude Code to external tools and data sources, and hooks for policy enforcement and automation at defined lifecycle points. citeturn0search2turn0search1turn0search0

---

## 2. Problem Statement

Current CLO deal structuring and packaging workflows are fragmented across spreadsheets, cashflow engines, data warehouses, emails, PDF term sheets, PowerPoint decks, and ad hoc review cycles.

### Current pain points

1. **Scenario generation is slow**  
   Business users must translate business intent into model inputs manually.

2. **Knowledge is fragmented**  
   Pool tapes, portfolio stats, tranche assumptions, historical comps, rating constraints, and legal language live in different systems.

3. **Narrative work is repetitive**  
   Teams repeatedly explain the same structure to internal stakeholders, investors, risk committees, and management.

4. **Version control is weak**  
   Users struggle to explain exactly what changed between v12 and v17 of a deal.

5. **Workflow governance is hard**  
   Sensitive data, draft language, model results, and final published materials require role controls and approval checkpoints.

6. **Time-to-market suffers**  
   Too much analyst and structurer time is spent on packaging and coordination rather than economic judgment.

---

## 3. Product Vision

Create a controlled AI workspace where a structurer can say:

> “Build a first-pass CLO from this pool, target 15% equity IRR, keep AAA placement realistic, show me the biggest sensitivities, compare it to our last two deals, and draft an investor summary.”

The system should then:

- retrieve the correct source data
- propose a parameter set
- invoke the official modeling engine
- explain outputs in plain language
- compare to historical deals
- draft internal / external materials
- route the draft through review and approval

---

## 4. Scope

### In scope for MVP

- deal creation from parameter inputs
- parameter validation
- scenario orchestration
- model run submission to official engine
- scenario result summarization
- deal version comparison
- historical comp retrieval
- investor summary draft generation
- internal IC / committee memo draft generation
- approval workflow integration
- full audit trail
- role-based publish controls

### Out of scope for MVP

- autonomous trading decisions
- autonomous investor communication without approval
- replacing official cashflow / analytics engines
- replacing legal document generation systems of record
- direct rating determination
- direct order book management

---

## 5. Users and Personas

### 5.1 Structurer

Needs to build, test, compare, and refine deal structures quickly.  
Success metric: fewer manual iterations and faster scenario turnaround.

### 5.2 Portfolio Manager / Desk

Needs to evaluate whether the structure is economically sensible and marketable.  
Success metric: faster understanding of tradeoffs and sensitivities.

### 5.3 Investor Marketing / Distribution

Needs accurate, approved, concise deal narratives and FAQs.  
Success metric: less manual deck rewriting and faster response to investor questions.

### 5.4 Risk / Product Control / Compliance

Needs traceability, reviewability, controlled language, and evidence of source grounding.  
Success metric: all published outputs auditable and policy compliant.

### 5.5 Technology / Platform Operations

Needs maintainable integrations, observability, and permission controls.  
Success metric: low operational overhead and safe model/tool usage.

---

## 6. Core Use Cases

### 6.1 Create a new deal

User uploads or selects a collateral pool and enters target constraints.  
AI proposes a first-pass structure.  
Official engine runs scenarios.  
AI summarizes outputs and flags issues.

### 6.2 Ask the deal

User asks natural language questions such as:

- What is driving the lower equity return in scenario B?
- Which tranche is most sensitive to spread compression?
- How does this compare with our last 3 European CLO prints?

### 6.3 Compare versions

User compares v3 vs v7.  
AI explains parameter changes, output changes, and likely causal drivers.

### 6.4 Generate materials

AI drafts:

- internal IC memo
- structuring summary
- investor one-pager
- Q&A sheet
- sensitivity commentary

### 6.5 Govern and publish

All external-facing materials pass required checks before publishing.

---

## 7. Product Principles

1. **Deterministic numbers, generative language**  
   Calculations come from official engines, not the LLM.

2. **Ground every answer**  
   Each answer must cite source objects: model output, deal schema, historical deal record, approved language bank, or source document excerpt.

3. **Review before release**  
   External narratives are never auto-published without human approval.

4. **Natural language in, structured actions out**  
   User requests are translated into typed scenario actions.

5. **Every important action is auditable**  
   Input, tool calls, model versions, outputs, approvals, and publication events are logged.

---

## 8. Functional Requirements

## 8.1 Deal Setup

The platform must allow users to create a deal from:

- imported pool tape
- selected template
- cloned prior deal
- manual parameter entry

### Required input parameter groups

#### A. Collateral parameters

- portfolio size
- weighted average spread
- weighted average life
- WARF / quality metrics
- diversity score
- sector concentrations
- top obligor concentration
- CCC bucket limits
- recovery assumptions by asset class
- reinvestment assumptions

#### B. Liability parameters

- tranche stack
- tranche sizes
- coupon / spread assumptions
- target ratings
- call / non-call assumptions
- payment frequency
- reinvestment period
- maturity profile

#### C. Structural parameters

- OC tests
n- IC tests
- concentration limits
- eligibility criteria
- waterfall settings
- trigger thresholds
- coverage definitions

#### D. Market assumptions

- base default rate
- stress default vectors
- recovery scenarios
- spread shock assumptions
- prepayment assumptions
- funding costs
- hedging assumptions if applicable

#### E. Commercial targets

- target equity IRR
- target AAA size / feasibility range
- target WAL / weighted average cost
- target cushion thresholds
- investor targeting notes

## 8.2 Scenario Management

The platform must let users:

- create baseline and alternate scenarios
- duplicate scenarios
- compare scenarios side by side
- run batch scenarios
- save named scenario sets
- mark official / draft / rejected scenarios

## 8.3 Natural Language Scenario Copilot

The platform must accept user instructions such as:

- Reduce AAA by 20m and shift proceeds to mezz.
- Optimize for stronger equity return while preserving AAA attractiveness.
- Stress recoveries by 10 points.
- Show me a conservative print scenario for today’s market.

The AI must convert these into a structured request object before engine submission.

## 8.4 Results Interpretation

The platform must provide plain-language interpretation for:

- tranche economics
- sensitivity drivers
- threshold breaches
- material changes from prior versions
- differences versus historical comparables

## 8.5 Narrative Generation

The platform must draft controlled narratives for:

- internal structuring note
- IC memo
- investor summary
- risk note
- FAQ responses
- change log / version note

## 8.6 Search and Retrieval

The platform must retrieve and rank:

- historical deals
- portfolio metrics
- approved marketing language
- risk disclosures
- document clauses
- investor-specific preferences where permitted

## 8.7 Approvals and Publishing

The platform must support:

- internal review states
- approval routing
- required sign-offs by role
- publish to internal portal
- publish to investor portal
- withdrawal / supersede of published drafts

---

## 9. Non-Functional Requirements

### 9.1 Security

- SSO / enterprise identity integration
- role-based access control
- deal-level entitlements
- audit logging for all critical actions
- data encryption in transit and at rest
- environment separation for dev / test / prod

### 9.2 Reliability

- modeling job retries
- graceful handling of MCP timeouts
- full fallback for AI summary failure when model output exists
- recovery workflow for partially failed publish flow

### 9.3 Explainability

- each answer tagged as calculated / retrieved / generated
- source links shown for all significant outputs
- versioned prompts for externally used narrative generation

### 9.4 Performance

- initial deal load under 10 seconds for cached records
- scenario submission under 3 seconds to queue
- standard scenario result narrative under 15 seconds after official engine output becomes available

### 9.5 Compliance

- all external-facing outputs require approved template families
- prohibited language detection
- mandatory disclaimer insertion where required

---

## 10. User Experience Overview

### Primary screens

1. **Deal Home**  
   Snapshot, current status, versions, owners, open tasks, latest outputs.

2. **Scenario Lab**  
   Parameters, natural-language requests, side-by-side scenario comparison.

3. **Ask the Deal**  
   Grounded Q&A over data, outputs, documents, and historical comps.

4. **Narrative Studio**  
   Draft memo / pitch / FAQ generation with source trace and review tools.

5. **Review & Publish**  
   Approval routing, redlines, compliance flags, publish destinations.

---

## 11. Claude Agent Architecture

This product uses a **supervisor + subagent** architecture.

Anthropic’s documentation states Claude Code supports custom subagents and that Claude uses each subagent’s description to decide when to delegate tasks. Built-in subagents include planning and code exploration patterns, and custom subagents can be configured for specialized tasks. citeturn0search2

### 11.1 Top-level Orchestrator Agent

**Name:** deal-creator-supervisor  
**Role:** Main user-facing agent that interprets intent, delegates to specialists, composes final response, and coordinates workflow state.

Responsibilities:

- interpret user request
- classify action type
- invoke subagents
- assemble grounded response
- route to approval when needed
- ensure only approved data is published

### 11.2 Proposed Subagents

#### A. deal-schema-agent

Purpose:

- map raw inputs into canonical deal schema
- validate required fields
- normalize pool and tranche data

Tools:

- schema registry MCP
- portfolio data MCP
- deal template MCP

Outputs:

- canonical deal object
- validation report

#### B. scenario-design-agent

Purpose:

- translate natural language into structured scenario instructions
- recommend scenario families
- detect ambiguous user requests

Tools:

- scenario DSL generator
- market assumptions MCP
- template library MCP

Outputs:

- scenario request JSON
- rationale

#### C. model-execution-agent

Purpose:

- submit official runs to structuring / cashflow engine
- poll for status
- collect output packages

Tools:

- cashflow engine MCP
- job status MCP
- result store MCP

Outputs:

- run IDs
- output object references
- execution status

#### D. analytics-explainer-agent

Purpose:

- interpret engine outputs
- identify key drivers
- compare scenarios and versions

Tools:

- result store MCP
- deal history MCP
- metrics dictionary MCP

Outputs:

- explanation summary
- driver analysis
- exception flags

#### E. comps-research-agent

Purpose:

- fetch similar historical deals
- compare structure, pricing assumptions, and outcomes

Tools:

- historical deals MCP
- market data MCP
- document search MCP

Outputs:

- ranked comps list
- comparison table
- comparable narrative

#### F. narrative-drafting-agent

Purpose:

- draft internal and external materials from approved sources
- tailor for audience and format

Tools:

- approved language bank MCP
- disclosure template MCP
- document output MCP

Outputs:

- memo draft
- investor summary draft
- FAQ draft

#### G. compliance-review-agent

Purpose:

- screen outputs for policy, entitlement, disclaimer, and prohibited language issues

Tools:

- policy rules MCP
- disclosure library MCP
- entitlement MCP

Outputs:

- pass/fail + issues
- required changes

#### H. publish-agent

Purpose:

- publish approved artifacts to allowed destinations
- stamp version, metadata, and audit event

Tools:

- content repository MCP
- investor portal MCP
- audit log MCP

Outputs:

- publication receipt
- artifact URL / ID

---

## 12. Subagent Delegation Rules

### Delegate to deal-schema-agent when

- new deal creation starts
- a pool tape is uploaded
- imported data appears inconsistent

### Delegate to scenario-design-agent when

- user asks for structural changes in plain English
- user requests optimization or stress scenarios
- multiple scenario variants are needed

### Delegate to model-execution-agent when

- a deterministic run is required
- official metrics are requested

### Delegate to analytics-explainer-agent when

- user asks “why” or “what changed”
- side-by-side comparison is requested

### Delegate to comps-research-agent when

- user asks for historical context, relative positioning, or market precedent

### Delegate to narrative-drafting-agent when

- a memo, deck summary, FAQ, or committee note is requested

### Delegate to compliance-review-agent when

- any output is destined for external audiences
- sensitive or policy-controlled language is present

### Delegate to publish-agent when

- approvals are complete and publication is explicitly requested

---

## 13. MCP Architecture

Anthropic’s docs describe MCP as the mechanism Claude Code uses to connect to external tools, databases, and APIs. MCP servers can expose enterprise systems and custom workflows to Claude Code. citeturn0search1turn0search7

For AI Deal Creator, MCP is the backbone of enterprise integration.

### 13.1 Required MCP Servers

#### 1. portfolio-data-mcp

Purpose:

- retrieve collateral pool tapes
- fetch obligor-level fields
- resolve sector / rating / spread attributes

Core tools:

- `get_pool(pool_id)`
- `get_obligor(obligor_id)`
- `validate_pool(pool_payload)`
- `list_pool_versions(deal_id)`

#### 2. deal-template-mcp

Purpose:

- retrieve structuring templates
- clone prior structures
- fetch regional / product conventions

Core tools:

- `get_template(template_id)`
- `suggest_template(region, currency, manager_type)`
- `clone_prior_deal(deal_id)`

#### 3. cashflow-engine-mcp

Purpose:

- submit official modeling jobs
- retrieve official outputs

Core tools:

- `run_scenario(deal_payload, scenario_payload)`
- `get_run_status(run_id)`
- `get_run_outputs(run_id)`
- `compare_runs(run_id_a, run_id_b)`

#### 4. historical-deals-mcp

Purpose:

- search historical deals and precedent transactions

Core tools:

- `search_comps(filters)`
- `get_deal_summary(deal_id)`
- `compare_deals(deal_ids)`

#### 5. market-data-mcp

Purpose:

- retrieve current market assumptions and spread context

Core tools:

- `get_spread_snapshot(date, market)`
- `get_recent_prints(filters)`
- `get_market_regime(date_range)`

#### 6. document-search-mcp

Purpose:

- search internal documents, term sheets, risk notes, legal language

Core tools:

- `search_docs(query, filters)`
- `get_doc(doc_id)`
- `extract_clause(doc_id, clause_type)`

#### 7. approved-language-mcp

Purpose:

- serve approved phrase libraries and disclosure templates

Core tools:

- `get_language_pack(audience, asset_class, region)`
- `get_required_disclosures(channel)`

#### 8. entitlement-policy-mcp

Purpose:

- verify access rights and release controls

Core tools:

- `can_view(user, artifact)`
- `can_publish(user, channel)`
- `get_required_approvers(deal_type, channel)`

#### 9. workflow-mcp

Purpose:

- create approval tasks and update statuses

Core tools:

- `create_review_task(payload)`
- `list_pending_reviews(user)`
- `record_approval(task_id, decision)`

#### 10. audit-log-mcp

Purpose:

- central audit trail for regulated workflow

Core tools:

- `record_event(event_payload)`
- `get_event_history(entity_id)`

#### 11. content-repository-mcp

Purpose:

- persist generated drafts and approved artifacts

Core tools:

- `save_draft(payload)`
- `publish_artifact(payload)`
- `get_artifact(artifact_id)`

---

## 14. Hook Architecture

Anthropic’s Claude Code hooks are deterministic controls that run at specific lifecycle points and can enforce project rules, automate workflows, and integrate with external systems. The official docs also describe advanced options including async hooks, HTTP hooks, prompt hooks, and MCP tool hooks. citeturn0search0turn0search3

For this application, hooks are mandatory because structured finance workflow cannot rely only on “the model remembering policy.”

### 14.1 Required Hook Events and Proposed Usage

#### A. PreToolUse Hook

Trigger: before a tool or MCP call executes.

Use cases:

- block unauthorized publication calls
- prevent access to restricted investor data
- require official engine for calculation requests
- validate that only approved tools are called in external narrative workflows

Example policies:

- deny `publish_artifact` unless approval state = approved
- deny `get_pool` for out-of-entitlement books
- deny any attempt to compute official output with a non-approved calculation tool

#### B. PostToolUse Hook

Trigger: after tool execution.

Use cases:

- log model runs
- attach provenance metadata
- detect suspicious result anomalies
- annotate outputs with calculated / retrieved / generated tags

#### C. UserPromptSubmit Hook

Trigger: when the user submits a prompt.

Use cases:

- classify request intent
- prepend regulatory instructions based on channel
- route to correct workflow mode: analysis, drafting, compare, publish

#### D. SessionStart Hook

Trigger: at start of session.

Use cases:

- load deal context
- load user role / entitlements
- load disclosure profile
- set active deal and current version

#### E. Stop / Completion Hook

Trigger: when agent finishes a major run.

Use cases:

- persist summary of completed actions
- create follow-up tasks
- emit audit event

#### F. MCP Tool Hook

Trigger: around specific MCP tool interactions.

Use cases:

- enforce schema checking on scenario requests
- redact sensitive fields on retrieval
- capture tool-level evidence for audits

#### G. Async Hook

Use cases:

- poll long-running engine jobs
- update status dashboard without blocking user conversation
- run background compliance scan after draft save

#### H. Prompt Hook / Agent Hook

Use cases:

- secondary LLM-based review of risky draft language
- detect overclaiming, non-grounded statements, or disallowed forward-looking phrasing before review submission

---

## 15. Recommended Hook Policy Matrix

| Event | Control | Purpose |
|---|---|---|
| UserPromptSubmit | intent classifier | Route to the right workflow |
| PreToolUse | entitlement check | Stop unauthorized data/tool access |
| PreToolUse | schema validation | Prevent malformed scenario runs |
| PreToolUse | publication gate | Block external publish before approval |
| PostToolUse | provenance tagging | Mark outputs by source type |
| PostToolUse | anomaly detector | Flag unusual run results |
| SessionStart | context bootstrap | Load deal, role, and policy state |
| Completion | audit persistence | Save trace of actions |
| MCP Tool Hook | redaction / normalization | Keep data exposure controlled |
| Async Hook | run polling | Handle long engine jobs safely |

---

## 16. Canonical Data Model

The system should use a canonical deal object to avoid raw-document chaos.

```json
{
  "deal_id": "string",
  "deal_name": "string",
  "currency": "EUR",
  "region": "EU",
  "manager": "string",
  "collateral": {
    "pool_id": "string",
    "portfolio_size": 500000000,
    "was": 0.042,
    "warf": 2800,
    "wal": 5.2,
    "diversity_score": 62,
    "concentrations": {}
  },
  "liabilities": [
    {
      "tranche": "AAA",
      "size": 0.60,
      "coupon": "SOFR+150",
      "target_rating": "Aaa"
    }
  ],
  "structural_tests": {
    "oc_tests": {},
    "ic_tests": {},
    "ccc_limit": 0.075
  },
  "market_assumptions": {
    "default_rate": 0.03,
    "recovery_rate": 0.65,
    "spread_shock_bps": 50
  },
  "workflow": {
    "status": "draft",
    "version": 3,
    "approvals": []
  }
}
```

---

## 17. End-to-End Workflow

### 17.1 New Deal Creation Flow

1. User opens Deal Home and selects **Create from pool**.
2. deal-schema-agent pulls pool data via `portfolio-data-mcp`.
3. Hook validates entitlement and required fields.
4. scenario-design-agent suggests initial structure based on template and targets.
5. User accepts or edits parameters.
6. model-execution-agent submits baseline run to `cashflow-engine-mcp`.
7. analytics-explainer-agent summarizes results.
8. narrative-drafting-agent drafts internal structuring note.
9. Draft saved to repository.
10. Audit event recorded.

### 17.2 Investor Summary Flow

1. User requests external investor summary.
2. narrative-drafting-agent drafts summary using approved language bank.
3. compliance-review-agent checks disclosures, unsupported claims, and channel fit.
4. workflow-mcp creates required approval tasks.
5. Once approved, publish-agent sends artifact to investor portal.
6. publication event recorded in audit log.

### 17.3 Compare Versions Flow

1. User selects v5 and v9.
2. analytics-explainer-agent retrieves both canonical objects and run outputs.
3. compare engine identifies changed parameters and changed metrics.
4. AI generates “what changed and why” summary.
5. Optional narrative exported to review packet.

---

## 18. Example Claude Project Layout

```text
ai-deal-creator/
├── CLAUDE.md
├── README.md
├── docs/
│   ├── prd.md
│   ├── architecture.md
│   ├── data-model.md
│   ├── hook-policies.md
│   └── evaluation-plan.md
├── .claude/
│   ├── settings.json
│   ├── agents/
│   │   ├── deal-schema-agent.md
│   │   ├── scenario-design-agent.md
│   │   ├── model-execution-agent.md
│   │   ├── analytics-explainer-agent.md
│   │   ├── comps-research-agent.md
│   │   ├── narrative-drafting-agent.md
│   │   ├── compliance-review-agent.md
│   │   └── publish-agent.md
│   └── hooks/
│       ├── pre_tool_use.py
│       ├── post_tool_use.py
│       ├── session_start.py
│       ├── completion.py
│       └── prompt_classifier.py
├── mcp/
│   ├── portfolio-data/
│   ├── cashflow-engine/
│   ├── historical-deals/
│   ├── approved-language/
│   └── workflow/
├── app/
│   ├── frontend/
│   ├── api/
│   ├── orchestration/
│   └── persistence/
└── tests/
    ├── evals/
    ├── integration/
    └── policy/
```

Anthropic’s settings docs state Claude Code supports hierarchical settings, project-level `.claude/settings.json`, project or user subagents, MCP server configuration, and `CLAUDE.md` instructions at user/project scope. citeturn0search8

---

## 19. Example `CLAUDE.md`

```md
# AI Deal Creator Project Instructions

You are working on a structured finance deal creation system.

Core rules:
1. Never invent official structured finance numbers.
2. All official metrics must come from approved engine MCP tools.
3. Distinguish clearly between:
   - calculated outputs
   - retrieved facts
   - generated language
4. External-facing language must pass compliance-review-agent before publish.
5. When a user asks for scenario changes, convert them into structured scenario JSON before execution.
6. Always cite source object IDs in analyst-facing outputs.
7. If a requested data source is missing or stale, state that explicitly.
```

---

## 20. Example Subagent Specs

### 20.1 `scenario-design-agent.md`

```md
---
name: scenario-design-agent
description: Converts natural-language structuring requests into typed scenario payloads for the official cashflow engine. Use when the user asks to change tranche sizes, assumptions, test thresholds, or wants optimization/stress scenarios.
tools:
  - market-data-mcp
  - deal-template-mcp
  - scenario-dsl-generator
---

You are a CLO scenario design specialist.

Rules:
- Produce typed JSON scenario payloads.
- Do not claim official outputs.
- Ask for missing hard constraints only when absolutely necessary; otherwise generate conservative defaults and flag assumptions.
- Prefer explainable scenario families: base, tight spreads, stressed defaults, lower recoveries, conservative print.
```

### 20.2 `analytics-explainer-agent.md`

```md
---
name: analytics-explainer-agent
description: Explains official model outputs, compares scenario runs, and identifies drivers of differences. Use when users ask why metrics moved or which risks matter most.
tools:
  - result-store-mcp
  - historical-deals-mcp
  - metrics-dictionary-mcp
---

You are a structured finance analytics explainer.

Rules:
- Use only official run outputs and retrieved reference data.
- Separate facts from inference.
- Rank drivers by likely materiality.
- If causality is uncertain, state that explicitly.
```

---

## 21. Example MCP Config Concepts

Anthropic docs note MCP server configuration can be project-scoped and user-scoped. Claude Code can connect to local or remote MCP servers that expose tools and data sources. citeturn0search1turn0search8

Illustrative configuration concept:

```json
{
  "mcpServers": {
    "portfolio-data": {
      "command": "python",
      "args": ["mcp/portfolio-data/server.py"]
    },
    "cashflow-engine": {
      "command": "python",
      "args": ["mcp/cashflow-engine/server.py"]
    },
    "historical-deals": {
      "command": "python",
      "args": ["mcp/historical-deals/server.py"]
    }
  }
}
```

---

## 22. Evaluation Framework

The product should be evaluated on both AI quality and workflow quality.

### 22.1 AI / Agent Metrics

- scenario translation accuracy
- explanation faithfulness
- comp retrieval relevance
- unsupported statement rate
- compliance pass rate pre-review
- source citation completeness

### 22.2 Workflow Metrics

- time to first baseline scenario
- time to investor summary draft
- time to compare versions
- number of manual analyst edits per draft
- approval cycle time
- publication error rate

### 22.3 Business Metrics

- reduction in structuring prep time
- reduction in marketing draft prep time
- increase in scenarios explored per deal
- user adoption by desk / structurer team
- percentage of outputs fully grounded in source objects

---

## 23. Risks and Mitigations

### Risk 1: Hallucinated financial claims

Mitigation:

- official numbers only from engine MCP
- compliance hook blocks unsupported claims
- source tagging in every output

### Risk 2: Unauthorized data exposure

Mitigation:

- pre-tool entitlement checks
- artifact-level RBAC
- redaction hooks on sensitive MCP calls

### Risk 3: Scenario misinterpretation

Mitigation:

- scenario JSON preview before run
- human confirmation for material structure changes
- versioned scenario templates

### Risk 4: Over-trust in AI narrative

Mitigation:

- “generated draft” watermark
- required approver workflow
- reviewer diff against source facts

### Risk 5: Operational fragility across integrations

Mitigation:

- MCP timeout handling
- cached read-only fallbacks
- resilient audit and retry architecture

---

## 24. Phased Delivery Plan

### Phase 1: Controlled Narrative Layer

Deliver:

- baseline deal creation UI
- official engine integration
- deal summary drafting
- version comparison
- audit logs

### Phase 2: Scenario Copilot

Deliver:

- natural-language scenario translation
- batch scenario runs
- comparison workspace
- comp retrieval

### Phase 3: Review and Publish Workflow

Deliver:

- compliance subagent
- approvals routing
- investor summary publish flow
- approved language packs

### Phase 4: Market-Aware Intelligence

Deliver:

- current market context retrieval
- historical comps ranking
- scenario recommendations based on market regime

### Phase 5: Optimization Assistance

Deliver:

- explainable optimization suggestions
- user-steered optimization loop
- advanced portfolio / structure tradeoff explorer

---

## 25. Open Questions

1. Which official engine is system-of-record for deterministic outputs?
2. What level of investor-specific tailoring is allowed?
3. Which disclosures are mandatory by region / channel?
4. Which deal data can be surfaced to which internal roles?
5. Should publish be one-step after approval, or require explicit final human release?
6. How much optimization autonomy is acceptable before a structurer must confirm?
7. What is the source of truth for historical comps?

---

## 26. Recommendation

Build AI Deal Creator as a **controlled orchestration layer** rather than a replacement for the current analytics engine.

Use:

- **Claude subagents** for specialist decomposition
- **MCP servers** for data, modeling, workflow, and publishing integrations
- **Hooks** for deterministic enforcement of policy, permissions, provenance, and approval gates

That design best matches the strengths of Claude Code as documented by Anthropic: specialized subagents, tool/data integration through MCP, and lifecycle hooks for reliable control. citeturn0search2turn0search1turn0search0

---

## 27. Appendix: Minimal Build Checklist

### Product

- [ ] confirm target desk and product scope
- [ ] lock canonical deal schema
- [ ] define approval matrix
- [ ] define external vs internal channels

### AI

- [ ] write subagent specs
- [ ] define prompt contracts
- [ ] define source citation format
- [ ] create eval dataset for scenario translation and narrative faithfulness

### MCP

- [ ] implement portfolio-data-mcp
- [ ] implement cashflow-engine-mcp
- [ ] implement historical-deals-mcp
- [ ] implement workflow-mcp
- [ ] implement content-repository-mcp

### Hooks

- [ ] pre-tool entitlement gate
- [ ] pre-publish approval gate
- [ ] post-tool provenance tagging
- [ ] session bootstrap
- [ ] async run polling

### Governance

- [ ] audit schema
- [ ] disclaimer library
- [ ] prohibited language rules
- [ ] publication watermarking

