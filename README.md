# Continuo

**Cross-agent memory federation for human-AI collaboration.**

Current AI memory systems are **call-and-repeat** — discrete turns with nothing happening in between. Real human language is **concurrent** — listeners recognize, recall, and formulate *while* speakers are still speaking. Continuo is the engineering translation of that concurrent structure into AI systems.

> "We used our minds to make minds that make our minds better."

Named for *basso continuo* — the continuous bass accompaniment in Baroque music that provides constant grounding while the melody moves above it.

---

## Status: Pre-Alpha (v0.0.1)

This is the initial scaffold. The Phase 1 reference implementation (L0 + L1 personal memory orchestrator) is in `core/orchestrator.py` and works standalone. The federation layer (L5 + L6) and adapter system are being built next.

**Not ready for production use.** Built in the open as a spec-and-reference-implementation for a convention we hope the ecosystem adopts.

## What It Is

A tiered, timing-aware memory protocol for any human-AI collaboration where context matters over time:

- **Developer workflows** — memory across Claude Code, Codex, Cursor, Copilot
- **Customer support operations** — cross-tool customer intelligence
- **Scientific research** — lab notebook continuity across sessions and team members
- **Creative writing, architecture, project management, education** — and anywhere else context accrues

One architecture, many domains. Content is always domain-specific; cognition is universal.

## The Memory Stack

```
Per-agent personal memory:
  L0 — Hot Cache          always in system prompt, ~3K tokens
  L1 — Entity Synopses    triggered on L0 keyword hit, parallel loaded
  L2 — Episodic Memory    async retrieval during human response time
  L3 — Indexed History    on-demand searchable session logs
  L4 — Raw Archive        verbatim conversation history

Cross-agent federation:
  L5 — Agent Memory Manifest    per-agent public glossary (a projection of L0-L4)
  L6 — Federation Library       aggregates all L5s, exposed as MCP server
```

See [`spec/ARCHITECTURE_v0.1.md`](spec/ARCHITECTURE_v0.1.md) for the full architecture doc.

## Quick Start (Phase 1 Orchestrator)

```bash
# From a local clone:
cd core/
python -c "
import asyncio
from orchestrator import Continuo

async def main():
    memory = Continuo()
    base = 'You are a helpful AI assistant.'
    prompt = await memory.prepare('Let us work on Continuo today', base)
    print(prompt)

asyncio.run(main())
"
```

This loads the L0 hot cache and any matching L1 synopses, then prints the fully-assembled system prompt ready to pass to an Ollama / OpenAI / Claude API call.

## Roadmap

- **v0.0.1** (now) — Scaffold + Phase 1 orchestrator (L0 + L1, manual files, Ollama-compatible)
- **v0.1.0** — L2 UltraRAG async integration + session-close L5 export
- **v0.2.0** — L6 MCP server + Claude Code + Codex adapters
- **v0.3.0** — `pip install continuo-memory` + `continuo init/up/query` CLI
- **v0.4.0** — Clyde + Clair native L5 publishers
- **v1.0.0** — Docs site, community adapter contributions, public launch
- **v1.x** — Cursor adapter (SQLite reverse-engineering), Copilot adapter (partial coverage), framework adapters (LangChain, CrewAI, AutoGen)

## Adapter Compatibility (Planned v1)

| Agent          | Difficulty        | Status    |
|----------------|-------------------|-----------|
| Clyde          | Native            | Planned   |
| Clair          | Native            | Planned   |
| Claude Code    | Native + Adapter  | Planned   |
| Codex          | Moderate          | Planned   |
| Cursor         | Deferred v1.x     | SQLite reverse-engineering required |
| Copilot        | Deferred v1.x     | Encrypted reasoning, no session index |

## Philosophy

See [`spec/THESIS.md`](spec/THESIS.md) (canonical copy lives in the project's [claude-brain repo](https://github.com/ryandavispro1-cmyk/claude-brain)) for the founding argument.

See [`spec/USE_CASES.md`](spec/USE_CASES.md) for eight worked domain scenarios beyond developer workflows.

## Contributing

Continuo is free (MIT) and welcomes contributions — especially adapters for new agents and frameworks. See [`CONTRIBUTING.md`](CONTRIBUTING.md).

## About

Continuo is a project by [RADLAB LLC](https://continuo.cloud). Designed with Ryan Davis (RADMAN). Co-authored with Claude (Anthropic).

## Other RADLAB Projects

Because you found us here, you might like to check out:

- **ILTT** — AI fitness automation for personal trainers ([iltt.app](https://iltt.app))
- **PRUN** — Privacy-first encrypted password manager ([prunpassword.com](https://prunpassword.com))
- **Castmore** — Cross-platform streaming discovery
- **OMNIVour** — Universal file conversion with AI extras

## License

MIT. See [`LICENSE`](LICENSE).
