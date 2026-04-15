"""
Continuo adapters -- normalize native agent memory into L5 manifests.

An adapter implements the ContinuoAdapter Protocol defined in adapters.base.
Adapters are registered via Python entry points in pyproject.toml under the
`continuo.adapters` group.

First-party adapters shipped in v0.0.x:
    - claude_code  -- Claude Code (reads claude-brain + auto-memory + MCP graph)

Planned:
    - codex  -- OpenAI Codex CLI
    - clyde  -- RADLAB Clyde (native publisher, not external adapter)
    - clair  -- RADLAB Clair (native publisher)
"""

from adapters.base import (
    AdapterDiscoveryError,
    AdapterError,
    AdapterExportError,
    AdapterVersionMismatchError,
    AgentInfo,
    AgentStore,
    ContinuoAdapter,
    Entity,
    HealthStatus,
    L5Manifest,
    Session,
    Visibility,
    VisibilityPolicy,
)

__all__ = [
    "AdapterDiscoveryError",
    "AdapterError",
    "AdapterExportError",
    "AdapterVersionMismatchError",
    "AgentInfo",
    "AgentStore",
    "ContinuoAdapter",
    "Entity",
    "HealthStatus",
    "L5Manifest",
    "Session",
    "Visibility",
    "VisibilityPolicy",
]
