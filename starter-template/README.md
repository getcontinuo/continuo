# Continuo Hybrid Memory Starter

Portable starter kit for projects that want:

- Hybrid memory chains (`workspace` + `global`)
- Continuo L5 export bridge
- MCP smoke assertions
- CI wiring and JSON reports

## Copy into a new repo

Copy:

- `scripts/build_continuo_l5.py`
- `scripts/mcp_smoke_test.py`
- `scripts/bootstrap-continuo-mcp.ps1`
- `scripts/run_memory_cycle.ps1`
- `.github/workflows/memory-cycle.yml`
- `spec/L5_schema.json`

Then run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/bootstrap-continuo-mcp.ps1 -WorkspaceRoot "."
powershell -ExecutionPolicy Bypass -File scripts/run_memory_cycle.ps1 -WorkspaceRoot "." -SchemaPath ".\spec\L5_schema.json"
```
