# Continuo Adapter Contract v0.1

An **adapter** is the bridge between an agent's native memory store and Continuo's standardized L5 manifest. Adapters are how Continuo federates across agents it does not control.

## Two Kinds of Adapters

**Native publisher** — the agent itself writes its L5 directly. Used when we control the agent (Clyde, Clair, any agent built on OpenAI Agents SDK with Continuo as a dependency). L5 is written at session close from the agent's internal state.

**External adapter** — code that reads an agent's native memory store (files, SQLite, JSONL, proprietary APIs) and normalizes it into L5. Used when we do not control the agent. Examples in Continuo v1: Claude Code, Codex. Community adapters fill the rest (Cursor, Copilot, Obsidian, etc.).

Both kinds implement the same interface.

## The Protocol

```python
from typing import Protocol
from datetime import datetime

class ContinuoAdapter(Protocol):
    """Every adapter (native or external) implements this."""

    agent_id: str          # unique slug, matches L5 schema agent.id
    agent_type: str        # one of the L5 agent.type enum values
    native_path: str       # filesystem path or URI of native store

    def discover(self) -> AgentStore:
        """
        Check the native store exists + return metadata.
        Raises AdapterDiscoveryError if not found.
        """
        ...

    def export_l5(self, since: datetime | None = None) -> L5Manifest:
        """
        Build L5 manifest from native memory.
        Applies visibility_policy filter before returning.
        """
        ...

    def export_sessions(self, since: datetime, limit: int = 100) -> list[Session]:
        """
        Export recent sessions in normalized schema.
        Called by export_l5; exposed separately for incremental updates.
        """
        ...

    def health_check(self) -> HealthStatus:
        """
        Return ok | degraded | blocked with reason.
        Used by `continuo doctor` CLI.
        """
        ...
```

## Registration

Adapters register via Python entry points in `pyproject.toml`:

```toml
[project.entry-points."continuo.adapters"]
my-agent = "my_package.adapter:MyAgentAdapter"
```

Continuo's CLI and L6 server discover adapters by iterating the `continuo.adapters` entry point group. No central registry needed.

## Data Contract

See `L5_schema.json` for the normative schema. Adapters MUST produce manifests that validate against it. The CI pipeline validates every emitted manifest before L6 accepts it.

## Error Semantics

- **`AdapterDiscoveryError`** — the native store does not exist or cannot be read. Raised from `discover()`. Non-fatal; L6 skips this adapter and logs.
- **`AdapterExportError`** — the native store exists but something went wrong during export. Raised from `export_l5()` or `export_sessions()`. Non-fatal but surfaced in `continuo doctor`.
- **`AdapterVersionMismatchError`** — the native store is a newer/older format than this adapter supports. Specific case of discovery error. Surfaces upgrade guidance.
- **Everything else** must be caught inside the adapter and converted to a `HealthStatus.degraded` with a reason — adapters never propagate unknown exceptions to the L6 server.

## Visibility Enforcement Is the Adapter's Job

The adapter MUST apply `visibility_policy` filtering before emitting the L5 manifest. L6 trusts the manifest it receives; there is no second filter layer. If an adapter emits a `private`-tagged entity, it leaks. Test this.

Recommended pattern:

```python
def export_l5(self, since=None) -> L5Manifest:
    raw_entities = self._read_native_entities()
    policy = self._load_visibility_policy()

    visible_entities = [
        e for e in raw_entities
        if self._apply_visibility(e, policy) != "private"
    ]

    return L5Manifest(
        spec_version="0.1",
        agent=self._agent_info(),
        last_updated=datetime.utcnow(),
        known_entities=visible_entities,
        ...
    )
```

## Idempotency

`export_l5()` MUST be deterministic for a given native store state. Same store state = same manifest. This lets L6 detect "has anything changed" via a simple hash comparison.

## Incremental Export (Optional)

The `since` parameter on `export_l5()` and `export_sessions()` allows efficient updates. Adapters that support it emit only entities/sessions updated after `since`. Adapters that do not support it emit everything (and the caller deduplicates). Declare support via an `IncrementalAdapter` protocol extension (forthcoming in v0.2).

## Example: A Minimal Adapter

```python
from datetime import datetime
from pathlib import Path
from adapters.base import ContinuoAdapter, L5Manifest, AgentInfo, Entity

class MyToolAdapter:
    agent_id = "my-tool"
    agent_type = "code-assistant"
    native_path = str(Path.home() / ".my-tool")

    def discover(self):
        if not Path(self.native_path).exists():
            raise AdapterDiscoveryError(f"My Tool not installed at {self.native_path}")
        return AgentStore(path=self.native_path, version="unknown")

    def export_l5(self, since=None):
        return L5Manifest(
            spec_version="0.1",
            agent=AgentInfo(id=self.agent_id, type=self.agent_type),
            last_updated=datetime.utcnow().isoformat() + "Z",
            known_entities=[],  # TODO: actual parsing in v0.1.0
        )

    def export_sessions(self, since, limit=100):
        return []

    def health_check(self):
        try:
            self.discover()
            return HealthStatus(status="ok")
        except AdapterDiscoveryError as e:
            return HealthStatus(status="blocked", reason=str(e))
```

## Testing an Adapter

Every adapter MUST ship:
- **Discovery test** — verifies `discover()` raises on missing store, returns on present store
- **Schema conformance test** — runs `export_l5()` against a fixture store, validates output against `L5_schema.json` using `jsonschema` library
- **Visibility test** — constructs a fixture with `private`-tagged entities, verifies they are absent from emitted L5
- **Round-trip test (if applicable)** — for adapters where the native format supports it: parse → emit → re-parse → assert equivalence

Fixtures live under `tests/fixtures/<agent_id>/` with sample native-store content.

## Versioning

- Adapter contract has its own semver, tied to Continuo spec version but independently bumped on breaking changes
- Adapters declare `CONTRACT_VERSION = "0.1"` at module level
- L6 warns on version mismatch but does not reject — adapters are free to be ahead or behind

## Open Questions (To Resolve in v0.2)

- Async adapter interface (required for MCP/network-backed adapters like Linear, Attio, Notion)
- Batch export for very large native stores (1M+ entities)
- Adapter metadata for L6 UI (icon, name, description)
- Adapter sandboxing — do we trust all adapters to read their native paths, or enforce FS isolation?

## Reference Implementation

See `adapters/claude_code.py` for the first external adapter. See `adapters/base.py` for the Protocol + dataclass definitions.
