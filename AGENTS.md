# AGENTS.md

## Cursor Cloud specific instructions

### Project overview

Bourdon is a Python 3.10+ cross-agent memory federation protocol (v0.3.0, pre-alpha). See `README.md` for the full L0–L6 memory stack architecture and `CONTRIBUTING.md` for contributor setup. Adapter authoring guide at `docs/AUTHORING_AN_ADAPTER.md`; formal contract at `spec/ADAPTER_CONTRACT.md`.

### Development environment

- **Virtual environment**: `.venv` at repo root. Activate with `source .venv/bin/activate`.
- **Install**: `pip install -e ".[dev,server,llama-cpp]"` installs all runtime + dev + optional extras.
- The `python3.12-venv` system package is required on Ubuntu (pre-installed in the Cloud Agent snapshot).
- No external services (databases, Docker, Redis, etc.) required. The entire test suite runs in-process.

### Key commands

| Task | Command |
|---|---|
| Lint | `ruff check .` (pre-existing warnings; non-fatal in CI per `test.yml`) |
| Type check | `mypy core/ adapters/ cli/` (pre-existing type issues) |
| Tests | `pytest tests/ -v` (384 tests, ~2s) |
| Orchestrator smoke | `cd core && python orchestrator.py` (used in CI) |
| CLI | `bourdon --help` / `bourdon prepare-turn "prompt" --access-level team` |
| L6 MCP server | `python -m core.l6_server --transport stdio` (requires `fastmcp>=2.0`) |
| Doctor preflight | `python scripts/doctor.py --workspace-root "."` |
| Regression matrix | `python scripts/regression_matrix.py --workspace-root "."` |
| Short-index check | `python scripts/migrate_short_index.py --workspace-root "." --check && python scripts/validate_short_index.py --workspace-root "."` |

### CI workflows

Two GitHub Actions workflows run on PRs and pushes to `main`:

1. **`test.yml`** — 3×3 matrix (ubuntu/windows/macos × Python 3.10/3.11/3.12). Installs `.[dev,llama-cpp]`, runs `pytest tests/ -v`, then `cd core && python orchestrator.py` as a smoke test. Ruff lint runs but is non-fatal (`|| echo "::warning::"` pattern).
2. **`memory-cycle.yml`** — Windows-only. Installs `.[server]`, runs PowerShell bootstrap + short-index schema enforcement + regression matrix + full memory cycle. Uploads reports as artifacts.

### Non-obvious caveats

- **CI vs local test parity**: CI's `test.yml` installs `.[dev,llama-cpp]` but NOT `.[server]`. This means L6 server tests (8 tests in `test_l6_server.py`) skip in CI when `fastmcp` is absent but pass locally with our full install. The local environment runs a superset of CI tests.
- **`tests/test_llama_cpp_backend.py`** requires the `httpx` package (installed via `.[llama-cpp]` extra). Without it, pytest collection fails with `ModuleNotFoundError`.
- **Entry points**: Adapters are registered via `[project.entry-points."bourdon.adapters"]` in `pyproject.toml`. After installing new adapter code, verify registration with: `python -c "from importlib.metadata import entry_points; print([ep.name for ep in entry_points(group='bourdon.adapters')])"`.
- The `web/` directory contains a static Cloudflare Workers marketing site — not part of the dev workflow.
- Commit style is conventional commits: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`.
