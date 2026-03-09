# MCP Server Map — AI Deal Creator

MCP (Model Context Protocol) is the integration backbone of this system.
Claude agents call MCP tools to retrieve data, submit engine runs, route approvals,
and publish artifacts. This keeps all enterprise system access controlled,
observable, and replaceable.

**Phase 1:** All MCP calls use mock stubs in `mcp/` (Python modules).
**Phase 2+:** Real MCP servers are implemented in `infra/mcp/` as separate server processes.

---

## Server index

| # | Server | Purpose | Phase | Spec |
|---|---|---|---|---|
| 1 | `cashflow-engine` | Submit and retrieve official scenario runs | 2 | [spec](../infra/mcp/cashflow_engine_mcp.md) |
| 2 | `portfolio-data` | Pool tape retrieval and validation | 2 | [spec](../infra/mcp/portfolio_data_mcp.md) |
| 3 | `historical-deals` | Comparable deal search and retrieval | 3 | [spec](../infra/mcp/historical_deals_mcp.md) |
| 4 | `approved-language` | Approved phrase library and disclosures | 3 | [spec](../infra/mcp/approved_language_mcp.md) |
| 5 | `workflow` | Approval task creation and status | 3 | [spec](../infra/mcp/workflow_mcp.md) |
| 6 | `audit-log` | Central audit trail for regulated workflow | 3 | — |
| 7 | `entitlement-policy` | Access control and publish gates | 3 | — |
| 8 | `deal-template` | Structuring templates and deal cloning | 4 | — |
| 9 | `market-data` | Current spread context and recent prints | 4 | — |
| 10 | `document-search` | Internal term sheets and legal clause search | 4 | — |
| 11 | `content-repository` | Draft and approved artifact persistence | 4 | — |

---

## Server details

### 1. cashflow-engine

**Purpose:** Submit official CLO scenario runs to the deterministic modeling engine.
This is the most critical integration — all official numbers must come from here.

**Mock stub:** `mcp/cashflow_engine/mock_engine.py`

**Tools:**

| Tool | Signature | Returns |
|---|---|---|
| `run_scenario` | `(deal_payload, scenario_payload)` | `{run_id, status, submitted_at}` |
| `get_run_status` | `(run_id)` | `{run_id, status}` |
| `get_run_outputs` | `(run_id)` | Official output metrics object |
| `compare_runs` | `(run_id_a, run_id_b)` | Diff of two run output objects |

**Key rule:** All outputs must be tagged `source = "model_runner"`. Any output
without this tag must not be presented as official.

---

### 2. portfolio-data

**Purpose:** Retrieve and validate collateral pool tapes. Expose obligor-level
attributes needed for deal setup.

**Mock stub:** `mcp/portfolio_data/mock_portfolio.py`

**Tools:**

| Tool | Signature | Returns |
|---|---|---|
| `get_pool` | `(pool_id)` | Pool object with metrics (was, warf, wal, etc.) |
| `validate_pool` | `(pool_payload)` | `{valid, issues}` |
| `list_pool_versions` | `(deal_id)` | List of pool tape versions |
| `get_obligor` | `(obligor_id)` | Obligor-level attributes (Phase 2) |

---

### 3. historical-deals *(Phase 3)*

**Purpose:** Search and retrieve precedent CLO transactions for comparables analysis.

**Tools:**

| Tool | Signature | Returns |
|---|---|---|
| `search_comps` | `(filters)` | Ranked list of comparable deals |
| `get_deal_summary` | `(deal_id)` | Summary metrics of a historical deal |
| `compare_deals` | `(deal_ids)` | Side-by-side comparison of multiple deals |

---

### 4. approved-language *(Phase 3)*

**Purpose:** Serve approved phrase libraries and mandatory disclosure templates.
All investor-facing language must pass through this server.

**Tools:**

| Tool | Signature | Returns |
|---|---|---|
| `get_language_pack` | `(audience, asset_class, region)` | Approved text blocks by section |
| `get_required_disclosures` | `(channel)` | Mandatory disclaimers for the channel |

**Key rule:** Document-drafter must use only language retrieved from this server
for external-facing sections.

---

### 5. workflow *(Phase 3)*

**Purpose:** Create and track approval tasks. Route materials to the right approvers.

**Tools:**

| Tool | Signature | Returns |
|---|---|---|
| `create_review_task` | `(payload)` | Task ID and assignees |
| `list_pending_reviews` | `(user)` | Open tasks for a user |
| `record_approval` | `(task_id, decision)` | Updated task with approval record |

---

### 6. audit-log *(Phase 3)*

**Purpose:** Central audit trail for all regulated workflow events.
Supplements the local `data/audit_log.jsonl` with a persistent, queryable store.

**Tools:**

| Tool | Signature | Returns |
|---|---|---|
| `record_event` | `(event_payload)` | Event ID |
| `get_event_history` | `(entity_id)` | List of events for a deal or material |

---

### 7. entitlement-policy *(Phase 3)*

**Purpose:** Enforce access control. Verify publish rights. Retrieve required approvers.

**Tools:**

| Tool | Signature | Returns |
|---|---|---|
| `can_view` | `(user, artifact)` | `{allowed: bool, reason}` |
| `can_publish` | `(user, channel)` | `{allowed: bool, reason}` |
| `get_required_approvers` | `(deal_type, channel)` | List of required approver roles |

---

### 8. deal-template *(Phase 4)*

**Purpose:** Retrieve standard structuring templates. Clone prior deal structures.

**Tools:**

| Tool | Signature | Returns |
|---|---|---|
| `get_template` | `(template_id)` | Template with default parameters |
| `suggest_template` | `(region, currency, manager_type)` | Recommended templates |
| `clone_prior_deal` | `(deal_id)` | Cloned deal object with new deal_id |

---

### 9. market-data *(Phase 4)*

**Purpose:** Provide current market context for scenario calibration.

**Tools:**

| Tool | Signature | Returns |
|---|---|---|
| `get_spread_snapshot` | `(date, market)` | Current spread levels by asset class |
| `get_recent_prints` | `(filters)` | Recent CLO pricings |
| `get_market_regime` | `(date_range)` | Market regime characterization |

---

### 10. document-search *(Phase 4)*

**Purpose:** Search internal documents: term sheets, risk notes, and legal clauses.

**Tools:**

| Tool | Signature | Returns |
|---|---|---|
| `search_docs` | `(query, filters)` | Ranked document results |
| `get_doc` | `(doc_id)` | Full document |
| `extract_clause` | `(doc_id, clause_type)` | Specific clause text |

---

### 11. content-repository *(Phase 4)*

**Purpose:** Persist generated drafts and approved artifacts.

**Tools:**

| Tool | Signature | Returns |
|---|---|---|
| `save_draft` | `(payload)` | Draft ID |
| `publish_artifact` | `(payload)` | Publication receipt and artifact URL |
| `get_artifact` | `(artifact_id)` | Artifact with metadata |

---

## Interface spec files (Phase 11)

Full tool contracts, request/response shapes, error codes, security rules,
and mock→real migration steps are documented in `infra/mcp/`:

| Spec file | Server | Status |
|---|---|---|
| [`cashflow_engine_mcp.md`](../infra/mcp/cashflow_engine_mcp.md) | `cashflow-engine` | Complete |
| [`portfolio_data_mcp.md`](../infra/mcp/portfolio_data_mcp.md) | `portfolio-data` | Complete |
| [`historical_deals_mcp.md`](../infra/mcp/historical_deals_mcp.md) | `historical-deals` | Complete |
| [`approved_language_mcp.md`](../infra/mcp/approved_language_mcp.md) | `approved-language` | Complete |
| [`workflow_mcp.md`](../infra/mcp/workflow_mcp.md) | `workflow` | Complete |

Servers 6–11 (audit-log, entitlement-policy, deal-template, market-data,
document-search, content-repository) are Phase 3–4 and will receive spec
files when their implementation phase begins.

---

## Mock → real migration path

When a real MCP server is ready to replace a mock stub:

1. Implement the server in `infra/mcp/<server-name>/server.py`
2. Register it in `.claude/settings.json` under `mcpServers`
3. Remove the mock import from any workflow that uses it
4. Update tests in `tests/integration/` to target the real server
5. Do not mix mock stubs and real MCP in the same workflow

---

## Open questions

1. Which cashflow engine is the system of record? (model version, API contract)
2. Is the approved-language bank a separate system or embedded in the document-search server?
3. How are deal-level entitlements defined — by desk, by role, or by named user?
4. Should audit-log MCP write synchronously (blocking) or asynchronously?
