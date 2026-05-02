# Getting Started: Memory Cycle

This guide runs Continuo's hybrid memory loop end-to-end:

1. Build/merge hybrid memory chain indices.
2. Export Continuo-compatible L5 manifests.
3. Run MCP smoke assertions against the L6 server.
4. Emit machine-readable JSON reports for CI.

## Prerequisites

- Python 3.10+
- PowerShell (for the provided automation scripts)

## One-time setup

```powershell
powershell -ExecutionPolicy Bypass -File scripts/bootstrap-continuo-mcp.ps1 -WorkspaceRoot "."
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
      "topic_key": "continuo_mcp",
      "topic_name": "Continuo MCP",
      "summary": "Workspace-specific Continuo MCP wiring and retrieval checks.",
      "triggers": ["continuo", "continuo mcp", "l6 server"],
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

- Workspace L5: `.cursor/memory/continuo.l5.yaml`
- Global L5: `~/agent-library/agents/cursor.l5.yaml`
- MCP report: `.cursor/memory/reports/mcp-smoke-report.json`
- Cycle report: `.cursor/memory/reports/memory-cycle-report.json`

## CI

GitHub Actions workflow:

- `.github/workflows/memory-cycle.yml`

The workflow uploads `memory-cycle-reports` as artifacts after each run.
