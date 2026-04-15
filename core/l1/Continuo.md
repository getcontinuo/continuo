# Continuo
**Type:** Concept / Architecture / Future Product  
**Status:** Speccing — v1 spec complete  
**Last updated:** 2026-04-14

## What
A tiered, human-inspired memory orchestration layer for local AI systems. Designed by Ryan Davis (RADMAN) on 2026-04-14. The missing layer in every RAG stack.

## The Core Insight
Existing RAG systems (including UltraRAG, ClawXMemory, all OpenClaw plugins) are retrieve-then-respond. They are archives with fast lookup. Continuo introduces *timing-aware, parallelized retrieval* so AI feels like it recognizes context rather than looking it up.

## The Five Layers
- **L0 — Hot Cache:** 2–3K tokens, always in system prompt, zero retrieval
- **L1 — Entity Synopses:** ~500 tokens/entity, fires on L0 keyword hit, parallel with response start
- **L2 — Episodic Memory:** UltraRAG retrieval, fires during human response time
- **L3 — Indexed History:** On-demand, searchable session logs
- **L4 — Raw Archive:** Verbatim history, rarely accessed

## Key Innovation
Parallelizing retrieval with conversation rhythm. Each layer buys time for the next. L2 completes while the human is reading L1-informed response and typing their reply.

## Build Plan
- Phase 1 (2–3 weeks): L0 + L1, manual files, Ollama only — prove the *feel*
- Phase 2 (4–6 weeks): L2 UltraRAG async integration, L3 logging, auto L1 refresh
- Phase 3 (TBD): Provider abstraction, open source packaging as standalone SDK

## Technical Finding
UltraRAG 3.0 pipeline engine is sequential but underlying `fastmcp.Client` is async-native. L2 bypasses the YAML pipeline and calls the retriever MCP tool directly via `asyncio.create_task()`.

## Competitive Landscape
ClawXMemory (OpenBMB), openclaw-memory-hierarchical, memory-lancedb-pro all shipped April 2026 — none have the timing/parallelization layer. Gap confirmed open.

## Spec Location
`claude-brain/PROJECTS/Clyde/MEMORY_ARCHITECTURE_v1.md`
