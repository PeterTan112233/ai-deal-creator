# MCP Interface Spec — cashflow-engine

**Server ID:** `cashflow-engine`
**Phase:** 2 (first real MCP server to implement)
**Mock stub:** `mcp/cashflow_engine/mock_engine.py`
**Priority:** Critical — all official CLO numbers must flow through this server.

---

## Purpose

This server is the boundary between Claude's language generation and the
deterministic cashflow modeling engine. It is the single authorised source
of equity IRR, tranche sizing, OC/IC cushions, WARF, WAL, and scenario NPV.

Claude must never compute these numbers directly. Every official metric in
an analyst output must carry a `run_id` that traces to a run on this server.

---

## Tool contracts

### `run_scenario`

Submit a parameterised scenario to the engine for async execution.

**Request:**
```json
{
  "deal_payload": {
    "deal_id": "deal-us-bsl-001",
    "version": "1.0",
    "pool": {
      "pool_id": "pool-001",
      "was": 350.0,
      "warf": 2850,
      "wal": 4.2,
      "wac": 0.042,
      "diversity_score": 62,
      "ccc_bucket": 0.055
    },
    "tranches": [
      {
        "name": "Class A",
        "rating_target": "AAA",
        "size_pct": 0.61,
        "coupon": "SOFR+110",
        "seniority": 1
      }
    ]
  },
  "scenario_payload": {
    "scenario_id": "scen-baseline-001",
    "label": "US BSL Baseline",
    "default_rate": 0.03,
    "recovery_rate": 0.65,
    "spread_shock_bps": 0,
    "reinvestment_period_yrs": 4,
    "call_date_yrs": 4
  }
}
```

**Response:**
```json
{
  "run_id": "run-abc12345",
  "scenario_id": "scen-baseline-001",
  "deal_id": "deal-us-bsl-001",
  "status": "submitted",
  "submitted_at": "2024-01-15T10:30:00Z",
  "estimated_completion_secs": 30,
  "source": "model_runner"
}
```

**Errors:**
- `400 INVALID_DEAL_PAYLOAD` — missing required fields or schema mismatch
- `400 INVALID_SCENARIO_PAYLOAD` — unknown parameter or out-of-range value
- `409 DUPLICATE_RUN` — identical payload already queued; returns existing `run_id`
- `503 ENGINE_UNAVAILABLE` — engine cluster not reachable

---

### `get_run_status`

Poll the execution status of a submitted run.

**Request:**
```json
{ "run_id": "run-abc12345" }
```

**Response:**
```json
{
  "run_id": "run-abc12345",
  "status": "complete",
  "submitted_at": "2024-01-15T10:30:00Z",
  "completed_at": "2024-01-15T10:30:28Z",
  "source": "model_runner"
}
```

**Status values:** `submitted` | `running` | `complete` | `failed` | `cancelled`

**Errors:**
- `404 RUN_NOT_FOUND` — `run_id` does not exist

---

### `get_run_outputs`

Retrieve the official output metrics for a completed run.

**Request:**
```json
{ "run_id": "run-abc12345" }
```

**Response:**
```json
{
  "run_id": "run-abc12345",
  "scenario_id": "scen-baseline-001",
  "deal_id": "deal-us-bsl-001",
  "status": "complete",
  "completed_at": "2024-01-15T10:30:28Z",
  "source": "model_runner",
  "outputs": {
    "equity_irr": 0.142,
    "equity_wal": 12.4,
    "scenario_npv": 1820000,
    "aaa_size_pct": 0.61,
    "wac": 0.038,
    "oc_cushion_aaa": 0.052,
    "ic_cushion_aaa": 0.031,
    "warf_output": 2876,
    "diversity_score_output": 62
  }
}
```

**Errors:**
- `404 RUN_NOT_FOUND`
- `409 RUN_NOT_COMPLETE` — run status is not `complete`
- `422 RUN_FAILED` — run completed with an engine error; includes `error_detail`

---

### `compare_runs`

Produce a structured diff between two completed runs.

**Request:**
```json
{
  "run_id_a": "run-abc12345",
  "run_id_b": "run-xyz67890",
  "label_a": "Baseline",
  "label_b": "Stressed"
}
```

**Response:**
```json
{
  "run_id_a": "run-abc12345",
  "run_id_b": "run-xyz67890",
  "source": "model_runner",
  "diffs": {
    "equity_irr": { "a": 0.142, "b": 0.108, "delta": -0.034, "delta_pct": -23.9 },
    "oc_cushion_aaa": { "a": 0.052, "b": 0.038, "delta": -0.014, "delta_pct": -26.9 }
  }
}
```

**Errors:**
- `404 RUN_NOT_FOUND` — one or both run IDs not found
- `409 RUN_NOT_COMPLETE` — one or both runs are not in `complete` status

---

## Security and provenance rules

- All responses carry `"source": "model_runner"`. Any response missing this
  field must be treated as unofficial and not surfaced to analysts.
- Outputs must be tagged `[calculated]` in any document or summary that
  references them. The `run_id` and `scenario_id` must be cited.
- The engine server must run in an isolated network segment. Claude should
  never have direct socket access to the engine — only through this MCP tool.
- Do not cache engine outputs in Claude's context beyond the current workflow.
  Always re-fetch via `get_run_outputs` to ensure the authoritative value is used.

---

## Phase timeline

| Phase | Action |
|---|---|
| 1 (current) | Mock stub in `mcp/cashflow_engine/mock_engine.py` |
| 2 | Implement `infra/mcp/cashflow_engine/server.py`; register in `.claude/settings.json` |
| 2 | Replace mock imports in `app/workflows/` with MCP tool calls |
| 2 | Add integration tests in `tests/integration/test_cashflow_engine_mcp.py` |
| 3 | Add async polling via the Async hook when run takes >5 seconds |

---

## Migration path from mock stub

1. Implement `infra/mcp/cashflow_engine/server.py` using the tool contracts above
2. Add to `.claude/settings.json`:
   ```json
   "mcpServers": {
     "cashflow-engine": {
       "command": "python",
       "args": ["infra/mcp/cashflow_engine/server.py"]
     }
   }
   ```
3. Update `app/workflows/run_scenario_workflow.py` to call MCP instead of the mock module
4. Remove `mcp/cashflow_engine/mock_engine.py` import from all production workflows
5. Keep mock stub for unit tests via dependency injection

---

## Open questions

1. What is the engine's actual API? REST, gRPC, or native MCP over stdio?
2. What is the max run queue depth before `ENGINE_UNAVAILABLE` fires?
3. Should `run_scenario` be synchronous (wait for result) or always async?
4. How long are `run_id` records retained on the engine side?
