# Evaluation Plan — AI Deal Creator MVP

**Phase:** 12 — Consistency and readiness review
**Date:** 2026-03-10
**Scope:** Full repository audit against the PRD, CLAUDE.md rules, and Phase 1–11 deliverables

---

## Summary verdict

The scaffold is **structurally sound and consistent at the service level**, but has three categories of technical debt that must be resolved before Phase 2 integration: a schema/service contract mismatch on approval records, two active governance gaps in the hook layer, and a large stretch of the workflow surface that has no test coverage.

Nothing in the current codebase will cause harm at Phase 1 (mock-only, no live data, no real publish tools). The risks become material when real MCP servers and real approval workflows are wired in Phase 2–3.

---

## Status by layer

### Domain models (`app/domain/`)
**Status: ✓ Implemented**

All core entities exist as Python dataclasses with correct field types. `Approval` domain model is correctly defined with `target_type`/`target_id` fields. One `expires_at: Optional[datetime]` field was added in Phase 9 for future expiry enforcement.

No issues at the domain model level.

---

### Pydantic schemas (`app/schemas/`)
**Status: ✓ Implemented — with one inconsistency**

All structural schemas (DealSchema, CollateralSchema, TrancheSchema, StructureSchema, ScenarioSchema) are implemented and tested.

JSON schemas (`deal_input.schema.json`, `scenario_request.schema.json`, `scenario_result.schema.json`) are present and well-formed.

**Issue 1 (High): `approval_record.schema.json` vs `approval_service.py` field contract mismatch**

The JSON schema requires `target_type` and `target_id`. The service creates records with `draft_type` and `draft_id` instead. Additionally:

- The JSON schema has `"additionalProperties": false` — a record created by the service would FAIL validation against its own schema
- The JSON schema allows `channel = "investor_portal"` — the service rejects this value
- `record_rejection()` adds `rejected_at` to the returned dict — this field is not in the schema, so a rejection record would also fail `additionalProperties: false`

The service contract and the schema were designed independently and have drifted. This must be resolved before any external system validates approval records against the JSON schema.

**Affected files:**
- `app/schemas/approval_record.schema.json`
- `app/services/approval_service.py`

---

### Services (`app/services/`)
**Status: ✓ Implemented — mock-only for engine**

| Service | Implementation | Mock-only? | Audit events |
|---|---|---|---|
| `validation_service` | Full | No | No (validation only) |
| `model_engine_service` | Full | **Yes** | No (caller emits) |
| `summary_service` | Full | No | No (caller emits) |
| `comparison_service` | Full | No | No (caller emits) |
| `drafting_service` | Full | No (template-based) | No (caller emits) |
| `approval_service` | Full | No | No (caller emits) |
| `audit_logger` | Full | No | — |

`model_engine_service` has `_MOCK_MODE = True` hardcoded at module level. There is no runtime switch. Phase 2 requires replacing the import and removing the flag.

**Issue 2 (Low): `DraftDocument.is_mock` field default is `True`**

The dataclass default `is_mock: bool = True` is always overridden by the explicit call-site value, so it never produces incorrect output. But the default sends the wrong signal if someone constructs a `DraftDocument` directly without the service. Consider removing the default and making it required.

---

### Workflows (`app/workflows/`)
**Status: ✓ Implemented — with one structural gap**

| Workflow | Inputs | Audit events | Integration tested |
|---|---|---|---|
| `create_deal_workflow` | Domain dataclasses | `deal.created` | No |
| `run_scenario_workflow` | Dict (`deal_input.schema.json`) | `deal.validated`, `scenario.submitted`, `scenario.completed`, `summary.generated` | Partial |
| `compare_scenarios_workflow` | Scenario domain objects | `comparison.run` | Yes |
| `compare_versions_workflow` | Dicts | `comparison.started`, `comparison.completed` | Yes |
| `generate_investor_summary_workflow` | Dicts | `draft.started`, `draft.generated`, `draft.failed` | No |
| `generate_ic_memo_workflow` | Dicts | `draft.started`, `draft.generated`, `draft.failed` | No |
| `publish_check_workflow` | Dict | `publish_check.run` | Yes |

**Issue 3 (High): No bridge between `create_deal_workflow` and `run_scenario_workflow`**

`create_deal_workflow` accepts domain dataclasses (Deal, Collateral, Structure) and returns a summary dict.
`run_scenario_workflow` accepts a flat `deal_input` dict matching `deal_input.schema.json`.
No converter function exists. An operator who creates a deal through `create_deal_workflow` cannot directly pipe its output into `run_scenario_workflow` without constructing a new dict manually.

The MVP flow is: `create_deal → run_scenario → draft → approve → publish`. Step 1→2 has a structural gap.

**Issue 4 (Medium): Two active comparison workflows with overlapping scope**

- `compare_scenarios_workflow.py` — Phase 1, operates on `Scenario` domain objects, checks `source == "model_runner"`, no driver inference
- `compare_versions_workflow.py` — Phase 8, operates on dicts, includes driver inference, handles deal-only and scenario-only modes

Both are active. The Phase 1 version has no deprecation notice or documentation indicating it should not be used for new work. The test for Phase 1 (`test_compare_scenarios.py`) is in `app/tests/` and tests the old interface.

---

### Mock MCP stubs (`mcp/`)
**Status: ✓ Implemented — correctly isolated**

All mock stubs carry `_mock: "MOCK_ENGINE_OUTPUT"` in every response. Mock data never represents itself as official. The model_engine_service correctly propagates the mock flag to the scenario result, which propagates to the DraftDocument.

No mock leakage issues found.

---

### Hooks (`infra/hooks/`)
**Status: ✓ Active — two guardrail bugs found by testing**

All four hooks are wired in `.claude/settings.json` and implement the Phase 10 policy matrix. Exception handling invariant is correct: all hooks fall back to allow/continue on any exception.

**Hook Bug #1 (Medium): Audit log protection regex is too broad**

Regex `>\s*(data[/\\])?audit_log` in `_check_audit_log_protection()` matches `>>` (append) as well as `>` (overwrite). Appending to the audit log is safe and should be allowed. The hook currently blocks both operations.

Confirmed by test: `test_audit_log_append_is_currently_blocked` documents this as expected-wrong behaviour.

Fix: change the regex to `(?<!>)>\s*(data[/\\])?audit_log` or `(?:^|[^>])>\s*(data[/\\])?audit_log` to exclude the `>>` case.

**Hook Bug #2 (Medium): Bash safety regex misses `rm -rfv`**

Regex `\brm\s+-[a-z]*r[a-z]*f\b` requires `f` to be the last character before a word boundary. `rm -rfv` has `v` after `f`, so it does not match. This is a genuine guardrail gap: `rm -rfv` is as destructive as `rm -rf`.

Confirmed by test: `test_rm_rfv_not_blocked_currently` documents this as expected-wrong behaviour.

Fix: change to `\brm\s+-[a-z]*r[a-z]*` (remove the terminal `f\b` requirement) or use `\brm\s+-[a-z]*f[a-z]*\b`.

**Issue 5 (Low): `infra/hooks/pre_publish_check.py` is not wired as a hook**

This file exists in `infra/hooks/` alongside the active hooks but is NOT registered in `.claude/settings.json`. It is only a Python module. Its publish checks duplicate (with minor differences) the logic in `publish_check_workflow.py`. This creates a maintainability risk: if `publish_check_workflow.py` is updated, `pre_publish_check.py` may fall out of sync.

Either wire it as a `PreToolUse` hook (replacing the inline publication gate in `pre_tool_use.py`) or document it as a helper module only.

---

### Publication gate correctness

The three-layer publish gate works correctly:

1. `infra/hooks/pre_tool_use.py` — tool-call level (enforced)
2. `app/workflows/publish_check_workflow.py` — workflow level (enforced)
3. `app/services/approval_service.py` — state machine (enforced)

The mock data check blocks at all three layers. The `apply_approval_to_draft()` function is the only code path that sets `approved=True`. Verified by 50 tests.

---

### Test coverage

**Current test count: 240 (all passing)**

| File / area | Tests | Notes |
|---|---|---|
| `app/tests/test_schemas.py` | 17 | Pydantic schema validation |
| `app/tests/test_phase5.py` | 28 | validation, engine, summary, workflow |
| `app/tests/test_mock_mcp.py` | 8 | mock MCP stubs |
| `app/tests/test_compare_scenarios.py` | 5 | OLD comparison workflow (Phase 1) |
| `tests/test_comparison.py` | 38 | NEW comparison service + workflow |
| `tests/test_publish_controls.py` | 50 | approval service + publish gate |
| `tests/test_drafting_service.py` | 55 | drafting service (added Phase 12) |
| `tests/test_hooks.py` | 39 | hook scripts (added Phase 12) |

**Coverage gaps remaining:**

| Area | Gap | Severity |
|---|---|---|
| `create_deal_workflow` | 0 tests | High |
| `generate_investor_summary_workflow` | 0 tests | Medium |
| `generate_ic_memo_workflow` | 0 tests | Medium |
| `infra/hooks/session_start.py` | 0 tests | Medium |
| `infra/hooks/completion.py` | 0 tests | Low |
| `app/services/summary_service.py` | Only banner test | Low |
| `compare_scenarios_workflow.py` (Phase 1) | Only 5 smoke tests | Low (deprecated) |
| Approval record JSON schema validation | 0 tests | High (given schema/service mismatch) |

**Two-directory test structure**: Tests in `app/tests/` cover Phase 1–5 code; tests in `tests/` cover Phase 8+. Both are found by pytest. This split is not documented anywhere. Should be noted in the project README or a `tests/README.md`.

---

## Mock clarity assessment

**Overall: ✓ Well controlled**

All mock output paths are consistently tagged:

| Location | Mock signal |
|---|---|
| `mcp/cashflow_engine/mock_engine.py` | `"_mock": "MOCK_ENGINE_OUTPUT"` in every response |
| `mcp/portfolio_data/mock_portfolio.py` | `"_mock": "MOCK_ENGINE_OUTPUT"` in every response |
| `model_engine_service.get_result()` | Propagates `_mock` key; adds engine warning |
| `drafting_service.generate_*()` | Sets `is_mock=True`; adds mock banners and warnings |
| `drafting_service` markdown output | Prominent `[MOCK ENGINE — NOT OFFICIAL]` banner |
| `publish_check_workflow._check_mock_data()` | Blocks publication when `is_mock=True` |
| `infra/hooks/pre_tool_use._check_publication_gate()` | Blocks publish tools when `is_mock=True` |

No code path was found where mock data could be presented to an analyst as official without multiple explicit warnings. The mock blocking is belt-and-suspenders across two independent layers.

---

## Guardrail completeness

| Rule (CLAUDE.md) | Enforcement mechanism | Status |
|---|---|---|
| Never compute official numbers | All compute paths go through `model_engine_service` → mock only | **Enforced in Phase 1** |
| Tag every output by source | `source_tag` on every `DraftSection`; `_mock` on every engine output | **Enforced** |
| External content requires approval | `publish_check_workflow` + `pre_tool_use` publication gate | **Enforced** |
| No auto-publish | No publish destination in Phase 1; `APPROVED_TO_PUBLISH` is advisory only | **Enforced (by omission)** |
| Source grounding mandatory | `run_id`/`scenario_id` required for engine outputs; `[PLACEHOLDER]` for gaps | **Enforced (structural)** |
| Scenario actions are structured | `_build_scenario_request()` always used; parameters shown before submission | **Enforced** |

**Not yet enforced (Phase 3 scaffolds):**
- Calculation gate: non-MCP compute tools are not yet blocked
- Entitlement checks: no user identity or role enforcement
- Approval expiry: `expires_at` field exists on domain model but `publish_check_workflow` never checks it
- Schema validation pre-engine-submission: hook scaffold exists but not activated

---

## Open questions from hooks-policy.md

1. Should PreToolUse intercept reads of sensitive pool data? — Not yet implemented.
2. Provenance tagging granularity — currently per-tool-call in `post_tool_use.py`, not per-document-section.
3. Stop hook audit SIEM emit — scaffold only.
4. Entitlement failure behaviour — scaffold only.

---

## Change log

| Phase | Changes |
|---|---|
| 10 | Added Phase 10 hooks: publication gate, audit log protection, bash safety, file write safety |
| 11 | Added MCP interface specs |
| 12 | Added `tests/test_drafting_service.py` (55 tests), `tests/test_hooks.py` (39 tests); identified 5 issues, 2 hook bugs |
