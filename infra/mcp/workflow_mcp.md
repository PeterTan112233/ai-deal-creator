# MCP Interface Spec — workflow

**Server ID:** `workflow`
**Phase:** 3
**Mock stub:** None yet — add `mcp/workflow/mock_workflow.py` in Phase 3 prep
**Priority:** Medium — enables structured approval routing to replace ad-hoc approval_service.

---

## Purpose

Create, route, and track approval tasks through the regulated review workflow.
This server is the integration point between Claude's approval logic
(`app/services/approval_service.py`) and the enterprise workflow system
(e.g. Jira, ServiceNow, or a proprietary deal management platform).

The Stop hook and completion events use this server to route pending items
to the correct approvers. The approval_service calls this server when
`request_approval` transitions to external workflow.

---

## Tool contracts

### `create_review_task`

Create a new approval task for a draft or artifact requiring human sign-off.

**Request:**
```json
{
  "task_type": "document_approval",
  "deal_id": "deal-us-bsl-001",
  "draft_id": "draft-inv-summary-001",
  "draft_type": "investor_summary",
  "channel": "external_investor",
  "requested_by": "analyst@firm.com",
  "required_approver_roles": ["compliance", "portfolio_manager"],
  "priority": "normal",
  "due_by": "2024-01-20T17:00:00Z",
  "context": {
    "deal_name": "US BSL CLO 2024-1",
    "summary": "Investor summary for initial investor outreach, external channel."
  }
}
```

**Response:**
```json
{
  "task_id": "task-wf-abc123",
  "deal_id": "deal-us-bsl-001",
  "draft_id": "draft-inv-summary-001",
  "status": "open",
  "created_at": "2024-01-15T10:30:00Z",
  "due_by": "2024-01-20T17:00:00Z",
  "assignees": [
    {
      "user_id": "user-compliance-001",
      "name": "J. Smith",
      "role": "compliance"
    },
    {
      "user_id": "user-pm-002",
      "name": "A. Patel",
      "role": "portfolio_manager"
    }
  ],
  "source": "workflow_system"
}
```

**Task types:** `document_approval` | `scenario_review` | `publish_release` | `exception_review`
**Priority values:** `low` | `normal` | `high` | `urgent`

**Errors:**
- `400 INVALID_TASK_TYPE`
- `400 MISSING_REQUIRED_APPROVERS` — `required_approver_roles` is empty
- `404 DEAL_NOT_FOUND`
- `409 DUPLICATE_TASK` — open task already exists for this `draft_id`; returns existing `task_id`
- `503 WORKFLOW_SYSTEM_UNAVAILABLE`

---

### `list_pending_reviews`

List open approval tasks assigned to a user or role.

**Request:**
```json
{
  "user_id": "user-compliance-001",
  "filters": {
    "deal_id": "deal-us-bsl-001",
    "task_type": "document_approval",
    "status": "open"
  }
}
```

`filters` is optional — if omitted, returns all open tasks for the user.

**Response:**
```json
{
  "user_id": "user-compliance-001",
  "source": "workflow_system",
  "retrieved_at": "2024-01-15T10:00:00Z",
  "tasks": [
    {
      "task_id": "task-wf-abc123",
      "deal_id": "deal-us-bsl-001",
      "draft_id": "draft-inv-summary-001",
      "draft_type": "investor_summary",
      "task_type": "document_approval",
      "status": "open",
      "created_at": "2024-01-15T10:30:00Z",
      "due_by": "2024-01-20T17:00:00Z",
      "overdue": false
    }
  ]
}
```

**Status filter values:** `open` | `pending_info` | `approved` | `rejected` | `cancelled`

**Errors:**
- `404 USER_NOT_FOUND`
- `503 WORKFLOW_SYSTEM_UNAVAILABLE`

---

### `record_approval`

Record a human approval or rejection decision on a task.

**Request:**
```json
{
  "task_id": "task-wf-abc123",
  "decision": "approved",
  "approver_id": "user-compliance-001",
  "notes": "Reviewed and approved. Minor formatting note: standardise heading caps.",
  "approval_id": "appr-xyz789"
}
```

**Response:**
```json
{
  "task_id": "task-wf-abc123",
  "draft_id": "draft-inv-summary-001",
  "decision": "approved",
  "approval_id": "appr-xyz789",
  "approver_id": "user-compliance-001",
  "decided_at": "2024-01-16T09:15:00Z",
  "status": "approved",
  "all_approvals_complete": true,
  "source": "workflow_system"
}
```

**Decision values:** `approved` | `rejected` | `request_changes`

**Errors:**
- `404 TASK_NOT_FOUND`
- `403 NOT_ASSIGNED` — approver is not assigned to this task
- `409 ALREADY_DECIDED` — task already has a final decision
- `400 MISSING_REJECTION_REASON` — decision is `rejected` but `notes` is empty
- `503 WORKFLOW_SYSTEM_UNAVAILABLE`

---

### `get_task_status`

Retrieve current status and decision history for a task.
*(Used by the Stop hook and pending approval scan in `infra/hooks/completion.py`)*

**Request:**
```json
{ "task_id": "task-wf-abc123" }
```

**Response:**
```json
{
  "task_id": "task-wf-abc123",
  "deal_id": "deal-us-bsl-001",
  "draft_id": "draft-inv-summary-001",
  "status": "approved",
  "source": "workflow_system",
  "created_at": "2024-01-15T10:30:00Z",
  "decided_at": "2024-01-16T09:15:00Z",
  "approvals": [
    {
      "approver_id": "user-compliance-001",
      "role": "compliance",
      "decision": "approved",
      "decided_at": "2024-01-16T09:15:00Z"
    }
  ],
  "all_approvals_complete": true
}
```

**Errors:**
- `404 TASK_NOT_FOUND`
- `503 WORKFLOW_SYSTEM_UNAVAILABLE`

---

### `route_open_items`

Batch route a list of pending items to the appropriate approvers.
*(Used by Stop hook in Phase 3 — replaces the local scan in `completion.py`)*

**Request:**
```json
{
  "session_id": "session-abc123",
  "pending_items": [
    {
      "item_type": "draft.generated",
      "draft_id": "draft-inv-summary-001",
      "deal_id": "deal-us-bsl-001",
      "channel": "external_investor"
    }
  ]
}
```

**Response:**
```json
{
  "session_id": "session-abc123",
  "source": "workflow_system",
  "routed": 1,
  "tasks_created": [
    {
      "task_id": "task-wf-abc456",
      "draft_id": "draft-inv-summary-001",
      "status": "open"
    }
  ],
  "skipped": []
}
```

**Errors:**
- `400 EMPTY_ITEMS_LIST`
- `503 WORKFLOW_SYSTEM_UNAVAILABLE`

---

## Security and provenance rules

- All responses carry `"source": "workflow_system"`.
- Only the approval_service and completion hook should call `record_approval`.
  The document-drafter must not call this tool directly.
- `record_approval` must only be called with an `approver_id` that matches
  an assigned user on the task. The server enforces this — but the
  pre_tool_use hook should also check before allowing the call.
- Workflow task IDs must be stored alongside approval records in the
  audit log to enable full audit trail reconstruction.

---

## Integration with approval_service

In Phase 3, `app/services/approval_service.py` will be updated to:

1. Call `create_review_task` when `request_approval()` is invoked
2. Store the returned `task_id` in the approval record dict
3. Call `record_approval` (MCP) when the human decision arrives (via webhook or poll)
4. The local approval record is the source of truth for publish gating —
   the workflow MCP is the routing and notification layer

---

## Phase timeline

| Phase | Action |
|---|---|
| 1–2 (current) | Approval state is managed locally in `approval_service.py` with no external routing |
| 3 prep | Add `mcp/workflow/mock_workflow.py` with in-memory task store |
| 3 | Implement `infra/mcp/workflow/server.py` connecting to enterprise workflow system |
| 3 | Update `approval_service.py` to call `create_review_task` and `record_approval` |
| 3 | Update Stop hook to call `route_open_items` instead of local scan |
| 3 | Update pending approval scan in `completion.py` to use `list_pending_reviews` |

---

## Open questions

1. What is the enterprise workflow system? (Jira, ServiceNow, proprietary deal management platform?)
2. Is approval routing synchronous (Claude waits for decision) or async (hook polls for result)?
3. Should multi-approver tasks require all approvals or any single approval?
4. What happens if a task expires (`due_by` passes) with no decision — auto-reject or escalate?
5. Should the workflow server send email/Slack notifications, or is that the workflow system's responsibility?
