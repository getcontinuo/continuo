# Cursor Alignment Spike

This spike tracks the hardening pass for:

1. CI-only migration enforcement
2. Canonical short-index schema validation
3. Fixture-driven regression matrix
4. One-command doctor preflight

## Changes

- Added canonical schema migration script: `scripts/migrate_short_index.py`
- Added canonical schema validation script: `scripts/validate_short_index.py`
- Updated cycle runner to run migrate+validate before export/smoke:
  - `scripts/run_memory_cycle.ps1`
- Updated bootstrap to use launcher resolution and run migrate+validate:
  - `scripts/bootstrap-bourdon-mcp.ps1`
- Updated MCP smoke script to accept explicit server Python executable:
  - `scripts/mcp_smoke_test.py` (`--server-python`)
- Added fixture-driven matrix:
  - `scripts/regression_matrix.ps1`
  - `tests/fixtures/short-index/*`
- Added one-command preflight:
  - `scripts/doctor.ps1`
- Wired CI guardrails:
  - `.github/workflows/memory-cycle.yml`

## CI behavior

`memory-cycle` workflow now:

1. Bootstraps memory dirs
2. Enforces canonical schema in check mode (`--check`)
3. Runs regression matrix
4. Runs full memory cycle
5. Uploads reports

## Notes

- CI intentionally fails if short-index files need migration.
- Local developers can run `migrate_short_index.py` without `--check` and commit normalized output.
