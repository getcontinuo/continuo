# 🎶 Continuo — Release Notes

### Your AI agents finally remember each other.

> *Named for basso continuo — the continuous bass line in Baroque music that holds everything together while the melody soars above it.*

Every AI tool you use — Claude Code, Codex, Cursor, Copilot — builds its own silo of memory. **None of them talk to each other.** You repeat yourself. Context evaporates. Collaboration resets to zero every time you switch tools.

**Continuo fixes that.** A tiered, timing-aware memory protocol that federates knowledge across every agent you work with — so your tools recognize you, recognize your projects, and recognize *each other*.

This isn't retrieval-augmented generation. This is **recognition-augmented cognition.** Your AI doesn't look you up. It *knows* you.

---

## 🚀 v0.0.7 — Recognition Runtime + Temporal Validity + Role Narratives

**Released 2026-04-22** · 250 tests passing · MIT licensed · [continuo.cloud](https://continuo.cloud) live

### What's New

🧠 **Recognition runtime — the headline behavior fix.** `core/recognition_runtime.py` ships the first concrete implementation of the recognition-first runtime: a synchronous template-based recognition string + a concurrent L1 hydration awaitable, with a ≤3-second timeout budget. **Never raises.** This is the behavior FINDINGS_JOURNAL flagged on 2026-04-19 — Continuo's "concurrent, not call-and-repeat" thesis is now actual code, not just a spec.

⏰ **Temporal validity windows on entities.** Zep-Graphiti-inspired `valid_from` / `valid_to` ISO 8601 dates on L5 Entities, so federation queries can answer "what was active in Q1 2026?" — not just "what's in memory?"

🎭 **Role narratives — `agent.role_narrative`.** A new optional L5 schema field that differentiates agents sharing the same `type` slug: Claude Code = manager, Codex = lead author, Cursor = debugger, Cline = throwaway, Clyde = general-purpose. Inspired by [Intrinsic Memory Agents](https://hf.co/papers/2508.08997). Both shipping adapters populate it; Clyde publisher does too.

📤 **Generic Codex memory pipeline + first-class CLI.** `continuo codex export | build-context | eval` turns Codex's distilled memory into L5 federation output plus L0/L1 timing artifacts. Plus `continuo claude-code export` — a SessionEnd hook target that silently writes the manifest, never raises, exits 0 in all failure modes.

📜 **`spec/POSITIONING.md`** stakes the recognition-first thesis publicly. **`spec/RELATED_WORK.md`** maps Continuo's vocabulary to Mem0, Zep, Letta, Cognee, Memora, SCS, Intrinsic Memory Agents, G-Memory, H-MEM, and the MCP roadmap.

🧪 **250 tests passing** — recognition runtime semantics, temporal validity round-trips, Codex eval pipeline, role narrative schema enforcement, end-to-end SessionEnd hook integration.

🌐 **Deployed at [continuo.cloud](https://continuo.cloud).**

### Get Started

```bash
pip install -e .              # Core — L0 + L1 + adapters
pip install -e '.[dev]'       # + pytest, ruff, mypy, jsonschema
pip install -e '.[ultrarag]'  # + L2 async episodic memory
pip install -e '.[server]'    # + L6 MCP federation server
```

---

## 📦 The Story So Far

Seven releases — six in one day, then the headline-behavior fix a week later. Here's how the full memory stack came together:

### v0.0.6 — Codex Adapter + Atomic L5 Write

**OpenAI Codex joins the federation, and L5 writes are never observed half-written.** `adapters/codex.py` parses `~/.codex/session_index.jsonl` newest-first, resolves rollout files to extract working directories and timestamps, and dedupes thread names into topic entities. Registered under the `continuo.adapters` entry point. `core/l5_io.py` introduces `write_l5()` / `write_l5_dict()` with tmp + rename atomic semantics — safe on POSIX and NTFS, no more race conditions between adapters writing and L6 reading. **188 tests passing.**

### v0.0.5 — L6 Federation MCP Server *(the big one)*

**The layer that makes it all real.** `core/l6_store.py` loads every agent's L5 manifest from `~/agent-library/agents/`, builds a cross-agent entity index, and exposes four query primitives — `list_agents`, `find_entity`, `list_recent_work`, `get_cross_agent_summary` — with visibility filtering re-applied at query time. `core/l6_server.py` wraps the store in a `fastmcp` MCP server. Launch with `python -m core.l6_server` and any MCP client can query the combined memory of every agent you've ever used. **149 tests passing.**

### v0.0.4 — L2 UltraRAG Async Integration

**Memory retrieval that doesn't make you wait.** L2 fires concurrently with the AI's first response and completes while you're still reading. It *never* blocks. It *never* raises. If the retrieval backend is down, you still get a response — you just don't get the deep context. Opt in via `CONTINUO_L2_ENABLED=true` or `core/l2_config.yaml`. **116 tests passing.**

### v0.0.3 — Claude Code Adapter Full Parsing

**Your Claude Code brain, federated.** Parses `PROJECTS/*/OVERVIEW.md` → project entities, `LOG/*.md` → sessions, auto-memory frontmatter → entities, and `memory.jsonl` knowledge graph → entities. Person-type entities and credential patterns are automatically marked `PRIVATE` — zero secrets leak into federation. Entity dedupe across all sources with priority ordering and merge rules. Tested against a real Claude Code brain: 55 entities, 46 sessions, 0 credential leaks. **80 tests passing.**

### v0.0.2 — L5 Schema + Adapter Contract + CI

**The spec that holds everything together.** `spec/L5_schema.json` defines the normative JSON Schema for L5 manifests. `spec/ADAPTER_CONTRACT.md` defines the rules every adapter must follow. `adapters/base.py` provides the Protocol, dataclasses, and visibility helpers. CI matrix: Ubuntu + Windows + macOS × Python 3.10–3.12. **49 tests passing.**

### v0.0.1 — Initial Scaffold

**Where it started.** Phase 1 orchestrator with L0 hot cache and L1 entity synopses. The spec documents that define *why* this architecture exists. The proof that timing-aware memory feels fundamentally different from retrieval-based memory.

---

## 🗺️ What's Next

| Milestone | What it unlocks |
|-----------|----------------|
| **v0.3.0** | `pip install continuo-memory` + `continuo init / up / query` CLI — one command to federate |
| **v0.4.0** | Clyde + Clair native L5 publishers — agents that *write* to the federation, not just get read |
| **v1.0.0** | Docs site, community adapters, **public launch** |
| **v1.x** | Cursor adapter (SQLite reverse-engineering), Copilot adapter, LangChain / CrewAI / AutoGen integrations |

---

## 🏗️ The Memory Stack

```
Per-agent personal memory:
  L0 — Hot Cache          always in prompt, instant recognition (~3K tokens)
  L1 — Entity Synopses    triggered on keyword hit, parallel loaded
  L2 — Episodic Memory    async retrieval during human response time
  L3 — Indexed History    on-demand searchable session logs
  L4 — Raw Archive        verbatim conversation history

Cross-agent federation:
  L5 — Agent Manifest     per-agent public glossary (projection of L0–L4)
  L6 — Federation Library  aggregates all L5s, exposed as MCP server
```

**L0–L2 are implemented. L5–L6 are implemented. The federation loop is closed.**

---

## 🔧 Requirements

- **Python ≥ 3.10** — that's it for core
- `pyyaml >= 6.0` — the only hard dependency
- `fastmcp >= 2.0` — optional, for L2 UltraRAG or L6 server

## 🔗 Links

| | |
|---|---|
| 🌐 **Homepage** | [continuo.cloud](https://continuo.cloud) |
| 💻 **Repository** | [github.com/getcontinuo/continuo](https://github.com/getcontinuo/continuo) |
| 🐛 **Issues** | [github.com/getcontinuo/continuo/issues](https://github.com/getcontinuo/continuo/issues) |
| 📄 **License** | MIT |
| 📐 **Architecture** | [`spec/ARCHITECTURE_v0.1.md`](spec/ARCHITECTURE_v0.1.md) |
| 📜 **Thesis** | [`spec/THESIS.md`](spec/THESIS.md) |

---

> ⚠️ **Pre-Alpha (v0.0.7).** Not production-ready — but the architecture is real, the tests pass, the federation loop works end-to-end, and the recognition-first runtime is now implemented. Built in the open as a spec-and-reference-implementation for a convention we hope the ecosystem adopts.
>
> *We used our minds to make minds that make our minds better.*
