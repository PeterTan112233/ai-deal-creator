# Next Steps — AI Deal Creator

**Phase:** Post-Phase 12
**Date:** 2026-03-10

This document records the recommended next implementation milestone and the backlog of issues found during Phase 12 evaluation.

---

## MVP status

### What works (Phase 1 — verified)

- **Domain models and schemas**: all entities (Deal, Collateral, Structure, Tranche, Scenario, Approval) are defined with correct types and Pydantic validation
- **Validation service**: deal input and scenario request validation with blocking issues and advisory warnings
- **Mock engine**: run_scenario → poll → get_result produces structured mock results, consistently tagged `_mock: "MOCK_ENGINE_OUTPUT"`
- **Comparison service**: compares two deal inputs or two scenario results; driver inference with multi-change caveat
- **Drafting service**: generates investor summary and IC memo from structured inputs; every section has a `source_tag`; `approved=False` hardcoded
- **Approval service**: pending → approved / rejected state machine; `apply_approval_to_draft()` is the only path to `approved=True`
- **Publish check workflow**: six-check publish gate (mock_data, draft_approved, approval_record, channel_policy, draft_id_match, placeholder_scan)
- **Hook layer**: PreToolUse (publication gate, audit log protection, bash safety, file write safety), PostToolUse (provenance tagging, mock detection), SessionStart, Stop — all wired in `settings.json`
- **Audit logger**: append-only JSONL audit trail for all workflow events
- **240 tests passing**

### What is mock-only (not production-ready)

| Component | Mock implementation | Real implementation target |
|---|---|---|
| Cashflow engine | `mcp/cashflow_engine/mock_engine.py` | `infra/mcp/cashflow_engine/` (Phase 2) |
| Portfolio data | `mcp/portfolio_data/mock_portfolio.py` | `infra/mcp/portfolio_data/` (Phase 2) |
| Approval routing | In-memory dict in `approval_service.py` | `workflow` MCP (Phase 3) |
| Audit persistence | File write to `data/audit_log.jsonl` | `audit-log` MCP (Phase 3) |
| Language library | `[PLACEHOLDER]` markers in drafts | `approved-language` MCP (Phase 3) |
| Historical comps | Not implemented | `historical-deals` MCP (Phase 3) |
| Entitlement | Not implemented | `entitlement-policy` MCP (Phase 3) |
| Publish destination | Not implemented | `content-repository` MCP (Phase 4) |

### Biggest risks

1. **Schema/service contract drift** (High, can cause silent failures at Phase 2 integration boundary)
2. **No approval expiry enforcement** (High, stale approvals can be used to publish)
3. **Hook regex bugs** (Medium, `rm -rfv` not caught; `>>` incorrectly blocked)
4. **No create_deal → run_scenario bridge** (Medium, the primary MVP workflow has a gap)
5. **No entitlement enforcement** (Medium, any actor can approve any document in Phase 1)

---

## Issues backlog

Issues are ordered by severity. Fix before Phase 2 integration begins.

---

### Issue 1 — Approval schema/service contract mismatch
**Severity:** High
**Source:** Phase 12 evaluation
**Files:** `app/schemas/approval_record.schema.json`, `app/services/approval_service.py`

**Problem:**
The JSON schema requires `target_type` and `target_id`. The service creates records with `draft_type` and `draft_id`. The schema has `additionalProperties: false`, so service-generated records would fail schema validation. Additional gaps:
- Schema allows `channel = "investor_portal"`; service rejects it
- `record_rejection()` adds `rejected_at` which is not in the schema

**Fix options:**
1. Update the JSON schema to match the service contract (add `draft_id`, `draft_type`, `rejected_at`; remove `target_type`, `target_id`; add `investor_portal` to channel enum)
2. Update the service to use `target_type`/`target_id` and align the channel enum
3. Add `rejected_at` to the schema and relax `additionalProperties` on the rejection sub-schema

Recommendation: option 1 — the service-level field names (`draft_id`, `draft_type`) are more specific and clearer for the current use case than the generic schema names.

**Tests to add:** JSON schema validation of approval records created by the service.

---

### Issue 2 — Hook Bug: audit log append incorrectly blocked
**Severity:** Medium
**Source:** Phase 12 hook tests (`test_audit_log_append_is_currently_blocked`)
**File:** `infra/hooks/pre_tool_use.py` in `_check_audit_log_protection()`

**Problem:**
Regex `>\s*(data[/\\])?audit_log` matches `>>` (safe append) as well as `>` (dangerous overwrite). The audit log is append-only by design; appending to it should be allowed.

**Fix:**
```python
# Replace:
re.compile(r">\s*(data[/\\])?audit_log"),
# With:
re.compile(r"(?<![>])>\s*(data[/\\])?audit_log"),
```
After fixing, update `test_audit_log_append_is_currently_blocked` to assert `action == "allow"` and rename it to `test_audit_log_append_is_allowed`.

---

### Issue 3 — Hook Bug: `rm -rfv` not blocked
**Severity:** Medium
**Source:** Phase 12 hook tests (`test_rm_rfv_not_blocked_currently`)
**File:** `infra/hooks/pre_tool_use.py` in `_check_bash_safety()`

**Problem:**
Regex `\brm\s+-[a-z]*r[a-z]*f\b` requires `f` to be the last character before a word boundary. `rm -rfv` has `v` after `f` so it does not match.

**Fix:**
```python
# Replace:
re.compile(r"\brm\s+-[a-z]*r[a-z]*f\b"),
# With:
re.compile(r"\brm\s+-[a-z]*f[a-z]*\b"),
```
This matches any flag set containing `f` (like `-rf`, `-rfv`, `-Rf`) in any position relative to other flags.

After fixing, update `test_rm_rfv_not_blocked_currently` to assert `action == "block"` and rename it.

---

### Issue 4 — No bridge between `create_deal_workflow` and `run_scenario_workflow`
**Severity:** Medium
**Source:** Phase 12 architecture review
**Files:** `app/workflows/create_deal_workflow.py`, `app/workflows/run_scenario_workflow.py`

**Problem:**
`create_deal_workflow` takes domain dataclasses and produces a summary dict. `run_scenario_workflow` takes a `deal_input` dict matching `deal_input.schema.json`. No adapter exists between the two. The primary MVP workflow (`create deal → run scenario → draft → approve → publish`) has a gap at step 1→2.

**Fix:**
Add a `deal_input_from_domain(deal, collateral, structure) → dict` helper in `app/workflows/create_deal_workflow.py` or a shared `app/utils/deal_input_builder.py`. Alternatively, have `create_deal_workflow` also return the `deal_input` dict directly.

**Tests to add:** End-to-end test from `create_deal_workflow` output through `run_scenario_workflow`.

---

### Issue 5 — Two active comparison workflows, no deprecation notice
**Severity:** Low
**Source:** Phase 12 evaluation
**Files:** `app/workflows/compare_scenarios_workflow.py`, `app/workflows/compare_versions_workflow.py`

**Problem:**
Both comparison workflows are active and tested. The Phase 1 version (`compare_scenarios_workflow.py`) operates on domain objects; the Phase 8 version (`compare_versions_workflow.py`) operates on dicts and has driver inference. No notice indicates which should be used for new development.

**Fix:**
Add a deprecation comment to `compare_scenarios_workflow.py` directing new code to `compare_versions_workflow.py`. Clarify in `docs/architecture.md` which comparison workflow is authoritative.

---

### Issue 6 — `infra/hooks/pre_publish_check.py` not wired
**Severity:** Low
**Source:** Phase 12 evaluation
**File:** `infra/hooks/pre_publish_check.py`

**Problem:**
This file is in `infra/hooks/` but is not registered in `.claude/settings.json`. Its publication checks partially duplicate those in `pre_tool_use.py` with minor differences. It is only callable as a Python module, not as a hook.

**Fix options:**
1. Wire it in `settings.json` as an additional `PreToolUse` hook alongside `pre_tool_use.py`
2. Document it explicitly as a workflow-level helper module and move it to `app/workflows/` or `app/services/`
3. Remove it and consolidate all publication gate logic into `pre_tool_use.py` and `publish_check_workflow.py`

Recommendation: option 2 — keep it as a service-layer check callable from workflow code, and rename it to make its role clear.

---

### Issue 7 — Approval expiry not enforced
**Severity:** Medium (increases after Phase 3 when real approvals are time-bounded)
**Source:** Phase 12 evaluation
**Files:** `app/domain/approval.py`, `app/workflows/publish_check_workflow.py`

**Problem:**
`Approval.expires_at` exists in the domain model and `app/schemas/approval_record.schema.json` accepts it, but `publish_check_workflow.py` never checks it. A stale approval record (past `expires_at`) would pass the current publish gate.

**Fix:**
Add a 7th check to `publish_check_workflow`:
```python
checks_run.append(_check_approval_expiry(approval_record))
```
Where `_check_approval_expiry` returns BLOCK if `expires_at` is not None and is in the past.

**Tests to add:** Expired approval record should produce a BLOCKED recommendation.

---

### Issue 8 — No tests for `create_deal_workflow` or drafting workflows
**Severity:** Medium
**Source:** Phase 12 test coverage review

**Missing test files:**
- `tests/test_create_deal_workflow.py` — should test happy path, pool validation failure, audit event emission
- `tests/test_generate_investor_summary_workflow.py` — should test draft generated/failed events, audit trail
- `tests/test_generate_ic_memo_workflow.py` — same

---

## Recommended next milestone: Phase 2a

**Goal:** Fix all Phase 12 issues and wire the first real MCP server (cashflow-engine).

**Scope:**

1. Fix Issues 1–3 (schema alignment, hook regex bugs) — these are correctness bugs with known fixes
2. Implement `deal_input_from_domain()` adapter to close Issue 4
3. Add expiry check to `publish_check_workflow` (Issue 7)
4. Wire `cashflow-engine-mcp` following the contract in `infra/mcp/cashflow_engine_mcp.md`
5. Replace mock imports in `run_scenario_workflow.py` with MCP calls
6. Update `_MOCK_MODE = False` in `model_engine_service.py`
7. Add integration tests against the real engine

**Why this milestone before others:**
- Issues 1–3 are pre-conditions for correctness — they should not ship to production
- Cashflow engine is the highest-priority MCP (all official numbers flow through it)
- The mock/real replacement is designed to be a drop-in swap with no workflow changes required

**Not in scope for Phase 2a:**
- Portfolio data MCP (Phase 2b — can follow immediately after)
- Approval routing, approved language, historical deals (Phase 3)
- Entitlement checks (Phase 3)

---

## Test count target for Phase 2

| File | Current | Phase 2 target |
|---|---|---|
| All existing | 240 | 240 (all passing) |
| `tests/test_create_deal_workflow.py` | 0 | ~15 |
| `tests/test_generate_drafting_workflows.py` | 0 | ~20 |
| `tests/test_cashflow_engine_mcp.py` (integration) | 0 | ~10 |
| `tests/test_approval_record_schema.py` | 0 | ~10 |
| **Total target** | **240** | **~295** |
