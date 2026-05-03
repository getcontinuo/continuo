# 🎶 Continuo — Release Notes

### Your AI agents finally remember each other.

> *Named for basso continuo — the continuous bass line in Baroque music that holds everything together while the melody soars above it.*

Every AI tool you use — Claude Code, Codex, Cursor, Copilot — builds its own silo of memory. **None of them talk to each other.** You repeat yourself. Context evaporates. Collaboration resets to zero every time you switch tools.

**Continuo fixes that.** A tiered, timing-aware memory protocol that federates knowledge across every agent you work with — so your tools recognize you, recognize your projects, and recognize *each other*.

This isn't retrieval-augmented generation. This is **recognition-augmented cognition.** Your AI doesn't look you up. It *knows* you.

---

## 🚀 v0.0.8 — Backend-Neutral Inference Layer (Layer A)

**Released 2026-05-03** · 310 tests passing · MIT licensed · [continuo.cloud](https://continuo.cloud) live

### What's New

🔌 **Backend-neutral inference Protocol — `core/inference_protocol.py`.** The contract every local-inference adapter implements: `capabilities()`, `slots()`, `stream_completion(prompt, *, slot_id)`, `cancel(slot_id)`. Plus `Slot` and `BackendCapabilities` value types and `register_backend()` with capability-gated registration that raises `BackendUnsupported` on missing requirements. Built so Continuo's recognition-first runtime can drive token streaming + mid-stream cancel + concurrent-slot routing without ever baking a specific backend into the runtime — Ollama, vLLM, TGI, transformers all drop in once they support the same primitives.

⚡ **`adapters/llama_cpp_backend.py` — first adapter.** Drives `llama-server` via SSE-streaming completion, slot enumeration with graceful degradation, and two-pronged cancel (stop-event + connection close so cancellation lands cleanly even when the upstream is mid-byte-read). Reports `streaming=True`, `cancel=True`, `concurrent_slots=N` (caller-supplied to match the `-np` flag), `kv_cache_reuse=True`. Hardened against malformed slot IDs (string/None/inf/bool), partial-failure parsing, and HTTP-error stop-event leaks. **Optional install**: `pip install 'continuo-memory[llama-cpp]'` — httpx is gated behind the extra; the Protocol itself is dependency-free.

🛠️ **CI infrastructure fixes.** The `verify-memory-cycle` workflow had been failing on every PR since it was added — assumed `continuo-memory` was on PyPI (it's not yet) and asserted MCP-server fixtures that the bootstrap script didn't seed. Both bugs fixed: install from local checkout, seed agent-library fixtures in bootstrap. Test matrix CI now installs `[dev,llama-cpp]` so adapter tests collect.

🧹 **Protocol cleanup pass (Cursor agent-as-author).** Bare-string `required_capabilities="cancel"` would have silently iterated as `{'c','a','n','e','l'}` and reported a useless missing-capability error — now an explicit `TypeError`. Plus modernized typing: `Optional[X]` → `X | None`, `AsyncIterator` moved to `collections.abc`, unused `logger` import removed.

🧪 **310 tests passing** (was 250 at v0.0.7). 60 new tests for the inference Protocol + adapter + Cursor's hardening. Full matrix CI (Ubuntu/Windows/macOS × Python 3.10–3.12) green.

### Authorship

This release is the first to formally demonstrate the **agent-as-author + agent-as-reviewer** pattern from `CONTRIBUTORS.md`:

- **Claude Opus 4.7 (1M context)** authored the Protocol contract, adapter, and CI workflow fix.
- **Cursor Cloud Agent** reviewed both, caught real bugs in each (bare-string capability iteration; `_parse_slot()` raising and violating the never-raise contract; `stop_event` leak on HTTP error), and authored the cleanup + hardening commits.
- All commits land under @ryandavispro1-cmyk's GitHub identity per the agent-as-author convention; agents are credited via `Co-authored-by:` trailers and PR descriptions.

### Get Started

```bash
pip install -e .              # Core — L0 + L1 + adapters
pip install -e '.[dev]'       # + pytest, ruff, mypy, jsonschema
pip install -e '.[ultrarag]'  # + L2 async episodic memory
pip install -e '.[server]'    # + L6 MCP federation server
```

---

## 📦 The Story So Far

Eight releases. Six in one day (the foundational architecture), then the recognition-first runtime, then the backend-neutral inference layer:

### v0.0.7 — Recognition Runtime + Temporal Validity + Role Narratives

**The headline behavior fix.** `core/recognition_runtime.py` ships the first concrete implementation of the recognition-first runtime: synchronous template-based recognition string + concurrent L1 hydration awaitable, ≤3s timeout budget, never raises. Plus `agent.role_narrative` (differentiates agents sharing the same `type` slug — Inspired by [Intrinsic Memory Agents](https://hf.co/papers/2508.08997)). Plus temporal validity windows on entities (Zep-Graphiti-inspired `valid_from`/`valid_to`). Plus `continuo codex export | build-context | eval` and `continuo claude-code export` SessionEnd hook target. Plus `spec/POSITIONING.md` and `spec/RELATED_WORK.md`. **250 tests passing.** Deployed at [continuo.cloud](https://continuo.cloud).

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

> ⚠️ **Pre-Alpha (v0.0.8).** Not production-ready — but the architecture is real, the tests pass, the federation loop works end-to-end, the recognition-first runtime is implemented, and the inference layer it drives is now backend-neutral. Built in the open as a spec-and-reference-implementation for a convention we hope the ecosystem adopts.
>
> *We used our minds to make minds that make our minds better.*
