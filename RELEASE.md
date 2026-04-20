# Release Notes — Continuo

**Cross-agent memory federation for human-AI collaboration.**

---

## v0.0.6 (2026-04-15) — Codex Adapter + Atomic L5 Write

The latest pre-alpha release adds the second external adapter (OpenAI Codex CLI) and introduces atomic file writes for L5 manifests so the federation layer never reads half-written data.

### Highlights

- **Codex adapter** (`adapters/codex.py`) — reads `~/.codex/session_index.jsonl` newest-first, resolves each entry's rollout file to extract `session_meta.cwd` and timestamps, deduplicates `thread_name`s into topic-type entities with `last_touched` preserved. Registered as the `codex` entry point.
- **Atomic L5 write** (`core/l5_io.py`) — `write_l5()` / `write_l5_dict()` use tmp + rename semantics so L6 file watchers never see incomplete manifests. Safe on POSIX and NTFS within a single filesystem. `read_l5_dict()` provided for symmetric round-trip.
- **188 tests passing** (+39 from v0.0.5) — Codex session parsing, rollout resolution, timestamp normalization, dedupe, schema round-trip, and a full Codex L5 → `L6Store` end-to-end integration test.

### Install

```bash
pip install -e .            # core (L0 + L1 + adapters)
pip install -e '.[dev]'     # + pytest, ruff, mypy, jsonschema
pip install -e '.[ultrarag]'  # + L2 UltraRAG backend
pip install -e '.[server]'    # + L6 MCP federation server
```

---

## Previous Releases

### v0.0.5 (2026-04-15) — L6 Federation MCP Server

The federation layer that makes cross-agent queries serve-able.

- **`core/l6_store.py`** — loads `~/agent-library/agents/*.l5.yaml`, builds an inverted cross-agent entity index, and exposes query primitives (`list_agents`, `find_entity`, `list_recent_work`, `get_cross_agent_summary`) with visibility filtering re-applied at query time.
- **`core/l6_server.py`** — wraps the store in a `fastmcp` server exposing `agent-library://` resources and four MCP tools. Launch via `python -m core.l6_server`.
- **149 tests passing** (+33 from v0.0.4).

### v0.0.4 (2026-04-15) — L2 UltraRAG Async Integration

Turns the L2 stub into a real async retrieval layer that never blocks the first response.

- **`core/l2.py`** — `L2Config` (YAML + env-var overrides), `L2Client` Protocol, `FastMCPL2Client` production backend, and `query_l2()` entry point that never blocks and never raises.
- **Disabled by default** — opt in via `core/l2_config.yaml` or `CONTINUO_L2_ENABLED=true`.
- **Optional extra**: `pip install 'continuo-memory[ultrarag]'`.
- **116 tests passing** (+36 from v0.0.3).

### v0.0.3 (2026-04-15) — Claude Code Adapter Full Parsing

Full parsing of all three Claude Code memory sources with privacy filtering and entity deduplication.

- **Parsers** for `PROJECTS/*/OVERVIEW.md` → project entities, `LOG/*.md` → sessions, auto-memory frontmatter → entities, `memory.jsonl` knowledge graph → entities.
- **Privacy layers** — person-type entities and credential-pattern observations default to `PRIVATE`; summary emission capped at 2 observations / 500 chars.
- **Entity dedupe** across sources with priority order (auto-memory > knowledge-graph > projects), merge rules for summaries, tags, and visibility.
- **80 tests passing** (+31 from v0.0.2).

### v0.0.2 (2026-04-15) — L5 Schema + Adapter Contract + Test Suite

Foundation for the adapter plugin system and CI infrastructure.

- **`spec/L5_schema.json`** — normative JSON Schema for L5 manifests.
- **`spec/ADAPTER_CONTRACT.md`** — prose adapter contract (protocol shape, entry-point registration, error semantics, visibility enforcement).
- **`adapters/base.py`** — Protocol + dataclasses (`L5Manifest`, `Entity`, `Session`, `AgentInfo`, etc.), `Visibility` enum, `apply_visibility` / `filter_for_federation` helpers.
- **`adapters/claude_code.py`** — first external adapter stub (discovers memory sources, health check grading).
- **CI workflow** — GitHub Actions matrix: Ubuntu + Windows + macOS × Python 3.10–3.12.
- **49 tests passing**.

### v0.0.1 (2026-04-15) — Initial Scaffold

The first commit — reference implementation scaffold.

- **Phase 1 orchestrator** (`core/orchestrator.py`) — L0 hot cache + L1 entity synopses, parallel-loaded with 1.5 s timeout, token-budget enforced.
- **Spec documents** — `ARCHITECTURE_v0.1.md`, `THESIS.md`, `USE_CASES.md`.
- **Project metadata** — `README.md`, `LICENSE` (MIT), `CONTRIBUTING.md`, `pyproject.toml`.

---

## Roadmap

| Milestone | Target | Description |
|-----------|--------|-------------|
| **v0.1.0** | — | L2 UltraRAG async integration + session-close L5 export |
| **v0.2.0** | — | L6 MCP server + Claude Code + Codex adapters |
| **v0.3.0** | — | `pip install continuo-memory` + `continuo init/up/query` CLI |
| **v0.4.0** | — | Clyde + Clair native L5 publishers |
| **v1.0.0** | — | Docs site, community adapter contributions, public launch |
| **v1.x**  | — | Cursor adapter, Copilot adapter, framework adapters (LangChain, CrewAI, AutoGen) |

---

## Requirements

- Python ≥ 3.10
- `pyyaml >= 6.0` (only hard dependency)
- Optional: `fastmcp >= 2.0` for L2 UltraRAG or L6 server

## Links

- **Homepage**: [continuo.cloud](https://continuo.cloud)
- **Repository**: [github.com/getcontinuo/continuo](https://github.com/getcontinuo/continuo)
- **Issues**: [github.com/getcontinuo/continuo/issues](https://github.com/getcontinuo/continuo/issues)
- **License**: MIT

---

> **Status: Pre-Alpha.** Not ready for production use. Built in the open as a spec-and-reference-implementation for a convention we hope the ecosystem adopts.
