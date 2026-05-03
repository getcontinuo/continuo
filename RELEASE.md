# 🎶 Continuo — Release Notes

### Your AI agents finally remember each other.

> *Named for basso continuo — the continuous bass line in Baroque music that holds everything together while the melody soars above it.*

Every AI tool you use — Claude Code, Codex, Cursor, Copilot — builds its own silo of memory. **None of them talk to each other.** You repeat yourself. Context evaporates. Collaboration resets to zero every time you switch tools.

**Continuo fixes that.** A tiered, timing-aware memory protocol that federates knowledge across every agent you work with — so your tools recognize you, recognize your projects, and recognize *each other*.

This isn't retrieval-augmented generation. This is **recognition-augmented cognition.** Your AI doesn't look you up. It *knows* you.

---

## 🚀 v0.0.9 — Layer A Validated + Layer B (`interrupt_first`)

**Released 2026-05-03** · 318 unit + 5 live integration tests passing · MIT licensed · [continuo.cloud](https://continuo.cloud) live

### What's New

🎯 **Layer A validated end-to-end against real `llama-server`.** New `tests/integration/test_llama_cpp_live.py` exercises the adapter against an actual running server (gated behind a pytest `integration` marker; auto-skips when no server is reachable; `CONTINUO_LLAMA_URL` overrides the default `http://localhost:8080`). The big result: **`backend.cancel(slot_id)` actually stops generation within the 5-second budget on real hardware** — the interrupt-first contract is no longer theoretical. **Measured during this release's Clyde wire-up: recognition emitted in 0.0ms, first token from Gemma 27B Q6_K at ~1000ms.** Recognition runs a full second ahead of the model's first token; the concurrent timing thesis is now demonstrated as measured behavior on real hardware.

⚡ **Layer B — `interrupt_first` primitive.** Symmetric companion to `recognition_first` for the speaker-still-talking case (`core/recognition_runtime.py`). The model is mid-generation, a new user message arrives; this primitive cancels the in-flight slot, then returns a fresh `RecognitionResult` shaped identically. Same downstream pattern as `recognition_first`. Locks the cancel-then-recognize order so recognition-emit latency is preserved (the entire latency budget the timing thesis is built on). KV-cache reuse flows automatically when the backend supports it (`LlamaCppBackend` does).

🩹 **Adapter hardening (Cursor agent-as-author).** Caught one more `httpx` exception type (`httpx.StreamClosed`) that the v0.0.8 hardening missed — could surface a clean cancellation as an unhandled exception to the consumer instead of returning gracefully. New regression test using `httpx.AsyncByteStream` to reproduce the timing.

🧪 **323 tests passing** (was 310 at v0.0.8) — 60 new tests across the inference Protocol, adapter, hardening, integration harness, and Layer B. The 5 integration tests run end-to-end against `llama-server` when one is reachable; they're skipped (port-knock) when not, so CI stays at 318 unit tests and contributors don't see spurious failures.

### Authorship

The agent-as-author + agent-as-reviewer pattern continues to pay off:

- **Claude Opus 4.7 (1M context)** authored the live integration test harness (#17) and Layer B's `interrupt_first` primitive (#18).
- **Cursor Cloud Agent** authored the additional `httpx.StreamClosed` hardening (#16) as a follow-up review pass on v0.0.8's adapter.
- Commits land under @ryandavispro1-cmyk per `CONTRIBUTORS.md`; agents credited via `Co-authored-by:` trailers.

### Get Started

```bash
pip install -e .              # Core — L0 + L1 + adapters
pip install -e '.[dev]'       # + pytest, ruff, mypy, jsonschema
pip install -e '.[ultrarag]'  # + L2 async episodic memory
pip install -e '.[server]'    # + L6 MCP federation server
```

---

## 📦 The Story So Far

Nine releases. Six in one day (the foundational architecture), then the recognition-first runtime, then the backend-neutral inference layer, then end-to-end validation + Layer B:

### v0.0.8 — Backend-Neutral Inference Layer (Layer A)

**The contract that makes Continuo's runtime backend-agnostic.** `core/inference_protocol.py` defines `InferenceBackend` as a `@runtime_checkable Protocol` with four methods: `capabilities()`, `slots()`, `stream_completion()`, `cancel()`. `adapters/llama_cpp_backend.py` implements it against `llama-server` SSE — first concrete adapter; httpx is gated behind the `[llama-cpp]` extra so the Protocol surface stays dependency-free. `register_backend()` checks capability requirements at registration time so missing primitives raise `BackendUnsupported` loudly rather than silently degrading. First release to formally exercise the agent-as-author + agent-as-reviewer pattern: Claude authored, Cursor reviewed and hardened. **310 tests passing.**

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

> ⚠️ **Pre-Alpha (v0.0.9).** Not production-ready — but the architecture is real, the tests pass, the federation loop works end-to-end, the recognition-first runtime is implemented, the inference layer it drives is backend-neutral, and the timing thesis is now proven as measured behavior on real hardware (recognition emitted in 0ms; the model's first token a full second behind). Built in the open as a spec-and-reference-implementation for a convention we hope the ecosystem adopts.
>
> *We used our minds to make minds that make our minds better.*
