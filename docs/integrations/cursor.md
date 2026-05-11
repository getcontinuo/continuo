# Bourdon × Cursor (IDE)

Cursor is both a **publisher** into cross-agent memory and an **MCP consumer** of the same federation. This document wires both directions.

## Publish: SQLite → L5 (`cursor` adapter)

Cursor keeps composer/chat workspace state in SQLite `state.vscdb` files under its application data directory:

- **macOS:** `~/Library/Application Support/Cursor`
- **Linux:** `~/.config/Cursor`
- **Windows:** `%APPDATA%\Cursor`

The Bourdon adapter copies each DB read-only, reads `ItemTable`, and emits `~/agent-library/agents/cursor.l5.yaml`.

### One-shot export

From a shell where `bourdon` is installed (`pip install -e ".[dev]"` in this repo):

```bash
bourdon cursor export
```

Options:

- `--cursor-dir PATH` — non-standard Cursor data root
- `--out PATH` — output YAML (default: `~/agent-library/agents/cursor.l5.yaml`)
- `--since ISO-DATETIME` — drop sessions older than this
- `--access-level public|team|private` — default `team` (matches other IDE adapters)
- `--print` — dump the filtered manifest to stdout after writing

### Hook (optional)

To refresh federation after significant work, run `bourdon cursor export` from a **shell command** hook or your own automation (Cursor’s hook surface evolves; keep the command non-interactive and fast).

## Consume: L6 MCP inside Cursor

Install the optional server extra, then point Cursor at the stdio MCP server:

```bash
pip install -e ".[server]"
```

**PATH gotcha:** MCP hosts often spawn subprocesses with a minimal `PATH`. If `python` or your venv is not on that PATH, use **absolute** paths in the config below (same pattern as Claude Desktop — see Bourdon’s `docs/integrations/claude-desktop.md` in the successor repo).

### Cursor MCP configuration

Add a server entry (user-level MCP settings in Cursor; path may vary by Cursor version — use **Cursor Settings → MCP** or the documented `mcp.json` location). Example:

```json
{
  "mcpServers": {
    "bourdon": {
      "command": "/absolute/path/to/python3",
      "args": ["-m", "core.l6_server"],
      "cwd": "/absolute/path/to/bourdon-repo-root"
    }
  }
}
```

If your project is installed in a venv:

```json
{
  "mcpServers": {
    "bourdon": {
      "command": "/absolute/path/to/.venv/bin/python",
      "args": ["-m", "core.l6_server"],
      "cwd": "/absolute/path/to/bourdon-repo-root"
    }
  }
}
```

Restart Cursor (or reload MCP servers) after editing. You should see Bourdon’s L6 tools (`query_agent_memory`, `list_recent_work`, `find_entity`, etc.) alongside other MCP servers.

### Visibility / `access_level`

Entities from Codex and Cursor adapters are often tagged **team**. L6 tools historically defaulted to **public**, which can hide those entities. For a single-user machine, prefer `team` when calling tools, or set the environment variable supported by your Bourdon version for default access level (see core release notes).

## Implementation notes (2026-05)

- Session sorting uses ISO dates parsed from Cursor records; `lastUpdatedAt` is honored in addition to `createdAt` / `updatedAt` / `timestamp` so composer rows match real Cursor JSON.
- The adapter is registered as `bourdon.adapters` entry point `cursor` and is invoked by `bourdon cursor export`.

## See also

- [`docs/getting-started-memory-cycle.md`](../getting-started-memory-cycle.md) — short-index + L5 layout under `.cursor/memory/`
- [`spec/ADAPTER_CONTRACT.md`](../../spec/ADAPTER_CONTRACT.md) — normative adapter behavior
