# Getting Started: Memory Cycle

This guide runs Bourdon's hybrid memory loop end-to-end:

1. Build/merge hybrid memory chain indices.
2. Export Bourdon-compatible L5 manifests.
3. Run MCP smoke assertions against the L6 server.
4. Emit machine-readable JSON reports for CI.

## Prerequisites

- Python 3.10+
- PowerShell (for the provided automation scripts)

## One-time setup

```powershell
powershell -ExecutionPolicy Bypass -File scripts/bootstrap-bourdon-mcp.ps1 -WorkspaceRoot "."
```

This creates:

- `.cursor/memory/short-index.json`
- `.cursor/memory/topics/`
- `~/.cursor/memory/short-index.json`
- `~/.cursor/memory/topics/`
- `~/agent-library/agents/`

## Seed memory data (example)

Add at least one entry to `.cursor/memory/short-index.json`:

```json
{
  "version": 1,
  "entries": [
    {
      "topic_key": "bourdon_mcp",
      "topic_name": "Bourdon MCP",
      "summary": "Workspace-specific Bourdon MCP wiring and retrieval checks.",
      "triggers": ["bourdon", "bourdon mcp", "l6 server"],
      "scope": "workspace",
      "access_level": "team",
      "last_updated": "2026-05-01",
      "tags": ["workspace", "memory-chain", "federation"]
    }
  ]
}
```

## Run full cycle

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_memory_cycle.ps1 -WorkspaceRoot "." -SchemaPath ".\spec\L5_schema.json"
```

## Outputs

- Workspace L5: `.cursor/memory/bourdon.l5.yaml`
- Global L5: `~/agent-library/agents/cursor.l5.yaml`
- MCP report: `.cursor/memory/reports/mcp-smoke-report.json`
- Cycle report: `.cursor/memory/reports/memory-cycle-report.json`

## CI

GitHub Actions workflow:

- `.github/workflows/memory-cycle.yml`

The workflow uploads `memory-cycle-reports` as artifacts after each run.
