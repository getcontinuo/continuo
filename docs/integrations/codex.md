# Bourdon x Codex

Codex can participate in Bourdon two ways:

1. **Consume** the L6 federation through Bourdon's MCP server.
2. **Publish** Codex-derived memory through the existing fallback/native bridge.

This keeps Codex out of its unstable native SQLite internals while still giving
it recognition-first runtime context at the start of a turn.

## Prerequisites

Install Bourdon from the repo environment you want Codex to launch:

```bash
cd /Users/radman/bourdon
.venv/bin/python -m pip install -e ".[dev,server,llama-cpp]"
.venv/bin/python -m pip show bourdon
```

The package version should match the repo version. For v0.6.0 work, `pip show`
should report `Version: 0.6.0`.

## Consume: MCP in Codex

Check whether Codex already knows about Bourdon:

```bash
bourdon codex mcp-status
```

Preview the install command without changing Codex config:

```bash
bourdon codex install-mcp
```

Register Bourdon with Codex:

```bash
bourdon codex install-mcp --write
```

The command is intentionally routed through `codex mcp add`; Bourdon does not
edit `~/.codex/config.toml` directly. The default registration is equivalent to:

```bash
codex mcp add bourdon \
  --env BOURDON_DEFAULT_ACCESS_LEVEL=team \
  -- /Users/radman/bourdon/.venv/bin/bourdon serve --quiet
```

Codex may need a new session or app restart before newly registered MCP tools
appear in the tool list.

Verify the server shape:

```bash
bourdon codex verify-mcp \
  --prompt "Can Codex join Bourdon federated memory?"
```

The verification expects these tools: `prepare_recognition_context`,
`get_deeper_context`, `commit_to_federation`, `find_entity`,
`list_recent_work`, `query_agent_memory`, and `get_cross_agent_summary`.

## Runtime Contract

At the start of a Bourdon-relevant turn, Codex should call:

```text
prepare_recognition_context(prompt, access_level="team")
```

Use the returned `prompt_context` as timing-layer context, not as a final
answer. After recognition has landed, Codex may call `get_deeper_context` for
slower L2 retrieval. If the session produces a durable fact that another agent
should know, Codex can call `commit_to_federation`; under-write here and prefer
stable project facts, decisions, constraints, or integration status over raw
conversation notes.

## Publish: Codex Fallback Bridge

The existing publisher remains the safe write path:

```bash
bourdon codex prepare-turn \
  --write \
  --memory-md \
  "Can we keep working on Bourdon runtime recognition?"
```

That refreshes the bounded Bourdon section in `~/.codex/memories/MEMORY.md` and
writes `~/agent-library/agents/codex.l5.yaml`.

## Rollback

Remove the Codex MCP registration:

```bash
codex mcp remove bourdon
```

This does not touch `~/.codex/state_5.sqlite` or `~/.codex/auth.json`.

## Tradeoffs

- MCP makes Bourdon tools available to Codex, but automatic every-turn
  recognition still depends on Codex's agent behavior.
- Native Codex distilled memory remains diagnostic. Bourdon reads safe fallback
  surfaces and does not mutate Codex SQLite.
- `commit_to_federation` is powerful and should stay high-signal to avoid
  memory noise.
