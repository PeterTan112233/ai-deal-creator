# Hooks Policy — AI Deal Creator

Claude Code hooks are deterministic controls that run at specific lifecycle points.
They enforce project rules regardless of what the model decides. In a regulated
structured finance context, hooks are mandatory — the system cannot rely on the
model remembering policy.

Hook scripts live in `infra/hooks/`. They are wired in `.claude/settings.json`
(active as of Phase 10).

---

## Hook types in use

| Hook | Trigger | Implementation file | Status |
|---|---|---|---|
| `PreToolUse` | Before any tool or MCP call | `infra/hooks/pre_tool_use.py` | Active — Phase 10 |
| `PostToolUse` | After tool execution | `infra/hooks/post_tool_use.py` | Active — Phase 10 |
| `SessionStart` | At start of each Claude session | `infra/hooks/session_start.py` | Active — Phase 10 |
| `Stop` | When agent completes a turn | `infra/hooks/completion.py` | Active — Phase 10 |
| `UserPromptSubmit` | When user submits a prompt | Planned — Phase 3 | |
| `Async` | Background polling | Planned — Phase 3 | |

---

## Policy matrix

### PreToolUse (`infra/hooks/pre_tool_use.py`)

Runs before every tool call. Can block the call and return a reason.

| Check | Tool(s) affected | Severity | Phase | Status |
|---|---|---|---|---|
| Publication gate | publish_artifact, send_to_portal, distribute_document, export_document, email_document, upload_to_dataroom | Block | 10 | **Enforced** |
| Audit log protection | Bash | Block | 10 | **Enforced** |
| Bash safety gate | Bash | Block | 10 | **Enforced** |
| File write safety | Write, Edit | Block | 10 | **Enforced** |
| Calculation gate | non-MCP compute tools | Block | 3 | Scaffold — not enforced |
| Entitlement check | all tools | Block | 3 | Scaffold — not enforced |
| Schema validation | run_scenario* | Block | 3 | Scaffold — not enforced |
| Sensitive data redaction | get_investor_preferences, get_obligor | Redact | 3 | Scaffold — not enforced |

**Publication gate policy:**
- `is_mock=True` → always blocked, no channel override
- `draft_approved ≠ True` AND `approval_status ≠ "approved"` → blocked
- External channel without `approval_id` → blocked

**Bash safety gate blocks:**
- `rm -rf` variants
- `git push --force`
- `git reset --hard`
- `chmod 777`
- `sudo`

---

### PostToolUse (`infra/hooks/post_tool_use.py`)

Runs after tool execution. Cannot undo the call. Observation and logging only.

| Check | Purpose | Phase | Status |
|---|---|---|---|
| Mock output detection | Warn if `_mock` tag in outputs | 10 | **Active** |
| Provenance tag mapping | Map tool → [calculated]/[retrieved]/[generated] | 10 | **Logged to stderr** |
| Structured event log | JSON event with tool, provenance, mock_detected | 10 | **Active** |
| Anomaly detection | Flag empty/unexpected engine outputs | 10 | **Active (basic)** |
| Audit log write | Persist tool provenance to audit_log.jsonl | 2 | Scaffold — Phase 2 |
| Output annotation | Attach provenance tag to output before model | 2 | Scaffold — Phase 2 |

**Tool → provenance tag mapping:**

| Tool pattern | Source tag |
|---|---|
| `cashflow_engine_*`, `run_scenario*` | `[calculated]` |
| `get_pool_data`, `get_portfolio*`, `get_deal*`, `Read` | `[retrieved]` |
| `draft_*`, `generate_*`, `compose_*` | `[generated]` |
| `Bash`, `Write`, `Edit`, `Glob`, `Grep` | `[internal]` |
| Unknown | `[unknown]` |

---

### SessionStart (`infra/hooks/session_start.py`)

Runs once at the beginning of each Claude Code session.

| Action | Purpose | Phase | Status |
|---|---|---|---|
| Session ID generation | Unique ID for correlation | 10 | **Active** |
| Environment validation | Check APP_ENV, URL vars | 10 | **Active** |
| Mock mode detection | Set mock_mode flag | 10 | **Active** |
| Data directory check | Verify data/ structure exists | 10 | **Active** |
| Session start log | JSON event to stderr | 10 | **Active** |
| Load active deal context | Set deal_id and version | 3 | Scaffold — Phase 3 |
| Load user role | Entitlement profile | 3 | Scaffold — Phase 3 |
| Load disclosure profile | Required disclosures by channel | 3 | Scaffold — Phase 3 |

**Context returned:**
```json
{
  "session_id": "session-abc123",
  "app_env": "local",
  "mock_mode": true,
  "env_valid": true,
  "data_dirs_ok": true,
  "active_deal_id": null,
  "user_role": null,
  "disclosure_profile": null
}
```

---

### Stop / Completion (`infra/hooks/completion.py`)

Runs when the agent completes a turn. May run multiple times per session.

| Action | Purpose | Phase | Status |
|---|---|---|---|
| Session summary log | Tool counts, pending items | 10 | **Active** |
| Audit log flush guidance | Reference to audit_log.jsonl | 10 | **Active** |
| Pending approval scan | Scan recent audit events for pending items | 10 | **Active** |
| Mock mode reminder | Warn if session is mock | 10 | **Active** |
| SIEM emit | Push summary to external audit system | 3 | Scaffold — Phase 3 |
| Workflow routing | Route open items to workflow-mcp | 3 | Scaffold — Phase 3 |
| Completion signal | Notify external systems | 3 | Scaffold — Phase 3 |

**Pending items detected:**
- `draft.generated` events with no subsequent approval
- `publish_check.run` events with BLOCKED or REVIEW_REQUIRED recommendation

---

### UserPromptSubmit (planned — Phase 3)

| Action | Purpose |
|---|---|
| Intent classification | Route to correct workflow mode: analysis, drafting, compare, publish |
| Channel detection | Prepend regulatory instructions if external-facing session |
| Prohibited phrase check | Block prompts containing disallowed external claims |

---

### Async hook (planned — Phase 3)

| Action | Purpose |
|---|---|
| Engine job polling | Check cashflow-engine-mcp run status without blocking the conversation |
| Background compliance scan | Run compliance-review-agent on saved draft after document-drafter finishes |
| Status dashboard update | Push run status to deal home without user prompt |

---

## Hook wiring (active as of Phase 10)

`.claude/settings.json` contains:

```json
{
  "hooks": {
    "PreToolUse":  [{ "hooks": [{ "type": "command", "command": "python3 infra/hooks/pre_tool_use.py"  }] }],
    "PostToolUse": [{ "hooks": [{ "type": "command", "command": "python3 infra/hooks/post_tool_use.py" }] }],
    "SessionStart":[{ "hooks": [{ "type": "command", "command": "python3 infra/hooks/session_start.py" }] }],
    "Stop":        [{ "hooks": [{ "type": "command", "command": "python3 infra/hooks/completion.py"    }] }]
  }
}
```

Hook scripts receive the event payload via stdin and return a JSON result to stdout.
A result with `"action": "block"` (PreToolUse only) prevents the tool call from executing.
All hooks log diagnostic events to stderr only.

---

## Error handling invariant

All hooks catch exceptions and fall back gracefully:
- `PreToolUse`: on exception → `{"action": "allow"}` (never block on hook error)
- `PostToolUse`, `SessionStart`, `Stop`: on exception → `{"action": "continue"}`

This ensures a broken hook never prevents Claude Code from functioning.
Hook errors are logged to stderr for investigation but do not surface to the user.

---

## Open questions

1. Should `PreToolUse` also intercept reads of sensitive pool data, or only writes/publishes?
2. At what granularity should provenance tagging happen — per tool call, or per workflow output?
3. Should the Stop hook emit to an external audit system (SIEM, workflow tracker) or just the local JSONL log?
4. When Phase 3 adds entitlement checks, should failed entitlement block silently or return an explanation?
