"""
Claude Code adapter -- reads claude-brain + auto-memory + MCP knowledge graph.

Status: v0.0.2 stub.
- discover() -- WORKS. Locates claude-brain + auto-memory + knowledge graph paths.
- export_l5() -- STUB. Returns a minimal manifest with agent info + discovered paths.
  Full parsing of PROJECTS/, LOG/, MEMORY.md, and memory.jsonl comes in v0.1.0
  (tracked at github.com/getcontinuo/continuo/issues/<TBD>).

Paths scanned (in order of preference):

1. CLAUDE_BRAIN env var                -- explicit override
2. ~/claude-brain/                     -- RADLAB default (Ry's layout)
3. ./claude-brain/                     -- cwd-relative for project-scoped use

Auto-memory and knowledge graph paths are auto-detected from the user's home.
"""

from __future__ import annotations

import os
import socket
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from adapters.base import (
    AdapterDiscoveryError,
    AgentInfo,
    AgentStore,
    ContinuoAdapter,
    Entity,
    HealthStatus,
    L5Manifest,
    Session,
    SPEC_VERSION,
    Visibility,
    VisibilityPolicy,
)

AGENT_ID = "claude-code"
AGENT_TYPE = "code-assistant"

# Default visibility policy -- conservative, tuned for personal/work blend
DEFAULT_POLICY = VisibilityPolicy(
    default=Visibility.PUBLIC,
    private_tags=[
        "personal",
        "financial",
        "credential",
        "health",
        "family",
        "legal",
    ],
    team_tags=["internal-roadmap"],
)


def _resolve_claude_brain_path() -> Optional[Path]:
    """Locate claude-brain repo using the documented precedence order."""
    env_override = os.environ.get("CLAUDE_BRAIN")
    if env_override:
        p = Path(env_override).expanduser()
        if p.is_dir():
            return p

    home_candidate = Path.home() / "claude-brain"
    if home_candidate.is_dir():
        return home_candidate

    cwd_candidate = Path.cwd() / "claude-brain"
    if cwd_candidate.is_dir():
        return cwd_candidate

    return None


def _resolve_auto_memory_path() -> Optional[Path]:
    """Claude Code auto-memory usually lives at ~/.claude/projects/<workspace>/memory/."""
    base = Path.home() / ".claude" / "projects"
    if not base.is_dir():
        return None
    # Find any child dir that contains a memory/ subdirectory
    for child in base.iterdir():
        if (child / "memory" / "MEMORY.md").is_file():
            return child / "memory"
    return None


def _resolve_knowledge_graph_path() -> Optional[Path]:
    """MCP knowledge graph lives at ~/claude-memory/memory.jsonl by convention."""
    candidate = Path.home() / "claude-memory" / "memory.jsonl"
    if candidate.is_file():
        return candidate
    return None


class ClaudeCodeAdapter:
    """
    External adapter for Anthropic's Claude Code CLI.

    Reads three memory sources (all optional; adapter degrades gracefully):
        1. claude-brain/  -- git-synced markdown project + session records
        2. ~/.claude/projects/*/memory/  -- per-machine auto-memory
        3. ~/claude-memory/memory.jsonl  -- MCP knowledge graph JSONL
    """

    agent_id = AGENT_ID
    agent_type = AGENT_TYPE

    def __init__(self) -> None:
        self.native_path = str(Path.home() / "claude-brain")  # primary anchor
        self._brain_path = _resolve_claude_brain_path()
        self._auto_memory_path = _resolve_auto_memory_path()
        self._knowledge_graph_path = _resolve_knowledge_graph_path()

    # -- Protocol methods ------------------------------------------------------

    def discover(self) -> AgentStore:
        """
        Locate Claude Code memory stores. Raises if none of the three are present
        (meaning Claude Code has probably never been used on this machine).
        """
        sources = {
            "claude_brain": str(self._brain_path) if self._brain_path else None,
            "auto_memory": str(self._auto_memory_path) if self._auto_memory_path else None,
            "knowledge_graph": str(self._knowledge_graph_path) if self._knowledge_graph_path else None,
        }
        if not any(sources.values()):
            raise AdapterDiscoveryError(
                "No Claude Code memory sources found. "
                "Expected one of: ~/claude-brain/, ~/.claude/projects/*/memory/, "
                "~/claude-memory/memory.jsonl."
            )

        return AgentStore(
            path=self.native_path,
            version="claude-code-memory-v1",
            metadata={"sources": sources},
        )

    def export_l5(self, since: Optional[datetime] = None) -> L5Manifest:
        """
        Build a minimal L5 manifest.

        v0.0.2 behavior (stub): returns agent info + empty entity/session lists,
        plus discovered-source metadata in capabilities. This is enough to prove
        the L6 plumbing; full parsing of PROJECTS/, LOG/, MEMORY.md frontmatter,
        and memory.jsonl entities comes in v0.1.0.
        """
        store = self.discover()  # re-raises on missing
        capabilities = sorted(k for k, v in store.metadata["sources"].items() if v)

        return L5Manifest(
            spec_version=SPEC_VERSION,
            agent=AgentInfo(
                id=self.agent_id,
                type=self.agent_type,
                instance=socket.gethostname() or "unknown",
                spec_version_compat=f">={SPEC_VERSION}",
            ),
            last_updated=datetime.now(timezone.utc).isoformat(),
            capabilities=capabilities,
            recent_sessions=[],
            known_entities=[],
            visibility_policy=DEFAULT_POLICY,
        )

    def export_sessions(
        self, since: datetime, limit: int = 100
    ) -> list[Session]:
        """
        v0.0.2 stub: returns empty list.

        v0.1.0 will parse claude-brain/LOG/YYYY-MM-DD-*.md for recent sessions,
        extract machine tag from filename (-pc / -mac), and map project_focus
        from headline sections.
        """
        return []

    def health_check(self) -> HealthStatus:
        """
        Classification:
            - ok        -- all 3 sources reachable
            - degraded  -- 1 or 2 sources missing (partial coverage)
            - blocked   -- 0 sources reachable (Claude Code never used here)
        """
        found = sum(
            1
            for p in (
                self._brain_path,
                self._auto_memory_path,
                self._knowledge_graph_path,
            )
            if p is not None
        )
        details = {
            "claude_brain": str(self._brain_path) if self._brain_path else "missing",
            "auto_memory": str(self._auto_memory_path) if self._auto_memory_path else "missing",
            "knowledge_graph": str(self._knowledge_graph_path) if self._knowledge_graph_path else "missing",
        }
        if found == 3:
            return HealthStatus(status="ok", details=details)
        if found == 0:
            return HealthStatus(
                status="blocked",
                reason="No Claude Code memory sources found on this machine",
                details=details,
            )
        return HealthStatus(
            status="degraded",
            reason=f"{found}/3 Claude Code memory sources found",
            details=details,
        )


# Protocol conformance check at import time -- catches missing methods before CI
_: ContinuoAdapter = ClaudeCodeAdapter()
