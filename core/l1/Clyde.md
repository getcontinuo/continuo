# Clyde
**Type:** Project — Local AI Swarm  
**Status:** Active development  
**Last updated:** 2026-04-14

## What
Clyde is RADLAB's local AI swarm. A multi-agent system running entirely on local hardware, built on OpenAI Agents SDK + Ollama + UltraRAG 3.0.

## Stack
- **Inference:** Ollama — Gemma 3 27B quantized (128K context)
- **Agents:** OpenAI Agents SDK
- **Memory/RAG:** UltraRAG 3.0 (recently upgraded from archive-style to MCP pipeline)
- **Hardware target:** NVIDIA A100 PCIe 80GB (evaluating)

## Current Work
Upgrading Clyde's memory system. Previous UltraRAG setup was essentially an archive — retrieve-then-respond, no conversational timing. Designing Bourdon (L0–L4 tiered memory) to make Clyde feel like it *recognizes* context rather than looking it up.

## Why It Matters
Clyde is the proving ground for Bourdon. If the memory architecture works here, it becomes a standalone open source package for any Ollama-compatible AI stack.

## Related
- Bourdon (memory architecture being built for Clyde)
- A100 PCIe 80GB (hardware evaluation driving Clyde's future compute)
- ILTT (Clyde's AI features are part of ILTT's backend)
