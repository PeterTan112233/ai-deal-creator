# infra/mcp/

MCP server configuration and stubs for AI Deal Creator.

## Purpose
This directory contains MCP server definitions that connect Claude agents
to enterprise data sources, the official cashflow engine, and workflow systems.

## Development approach
- Phase 1: Mock stubs live in `mcp/` at the project root (Python modules).
- Phase 2+: Real MCP servers are implemented here as separate server processes.

## Planned MCP servers (PRD §13)

| Server | Purpose | Phase |
|---|---|---|
| `portfolio-data` | Pool tape retrieval, obligor data | 2 |
| `cashflow-engine` | Official scenario execution | 2 |
| `historical-deals` | Comps search and retrieval | 3 |
| `approved-language` | Approved phrase library, disclosures | 3 |
| `workflow` | Approval task creation and status | 3 |
| `audit-log` | Central audit trail | 3 |
| `entitlement-policy` | Access control and publish gates | 3 |
| `deal-template` | Structuring templates | 4 |
| `market-data` | Spread snapshots, recent prints | 4 |
| `document-search` | Term sheets, legal clauses | 4 |
| `content-repository` | Draft and artifact persistence | 4 |

## MCP config (add to .claude/settings.json in Phase 2)
```json
{
  "mcpServers": {
    "cashflow-engine": {
      "command": "python",
      "args": ["infra/mcp/cashflow_engine/server.py"]
    }
  }
}
```
