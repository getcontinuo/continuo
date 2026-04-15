"""
Codex adapter -- reads ~/.codex/sessions/ JSONL rollouts + session_index.jsonl.

v0.0.6 scope:
- discover() -- locates session_index.jsonl + sessions/ hierarchy
- export_sessions() -- parses session_index.jsonl newest-first, resolves each
  entry to its rollout file to pull out cwd + timestamp from session_meta
- export_l5() -- combines sessions with a light entity list derived from
  deduped session thread_names (each unique thread_name becomes an Entity
  typed "topic")
- health_check() -- grades source coverage (session_index + sessions dir +
  optional codex-brain)

Deferred to a later version:
- Parsing codex-brain markdown (CURRENT.md.txt / INDEX.md.txt / LOG/*.md).
  That path is less structured than claude-brain's PROJECTS/ and its
  entities are harder to extract without heuristics.
- Extracting files_touched from tool-call events in the rollout stream.
  Doable but noisy; punt to v0.1.0.

Privacy handling
----------------
- rollout `session_meta.cwd` is NOT scrubbed. It's a path, not credential
  content, and it's the primary federation signal. Users who consider
  their cwd private should set ``CONTINUO_CODEX_CWD_PRIVATE=true`` (not
  yet implemented; v0.1.x).
- thread_name is treated as user-generated content (it's the task title
  the user typed into Codex). Emitted public by default.
- base_instructions blob is intentionally ignored (too long, not memory).
"""

from __future__ import annotations

import json
import logging
import os
import socket
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Optional

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
    filter_for_federation,
)

logger = logging.getLogger(__name__)

AGENT_ID = "codex"
AGENT_TYPE = "code-assistant"

# Same conservative default policy as Claude Code adapter.
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


# -- Path resolution -----------------------------------------------------------


def _resolve_codex_home() -> Optional[Path]:
    """Locate ~/.codex/ (the primary Codex session store)."""
    candidate = Path.home() / ".codex"
    return candidate if candidate.is_dir() else None


def _resolve_codex_brain() -> Optional[Path]:
    """Optional user-managed ~/codex-brain/ repo (same pattern as claude-brain)."""
    candidate = Path.home() / "codex-brain"
    return candidate if candidate.is_dir() else None


# -- Parsing helpers -----------------------------------------------------------


def _parse_session_index(path: Path, limit: Optional[int] = None) -> list[dict]:
    """
    Read session_index.jsonl newest-first (by ``updated_at``).

    Returns a list of dicts with at minimum id + thread_name + updated_at.
    Malformed lines are skipped with a warning.
    """
    if not path.is_file():
        return []
    entries: list[dict] = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as e:
                    logger.warning(
                        "Skipping malformed JSONL in %s:%d -- %s", path, line_num, e
                    )
                    continue
                if not isinstance(record, dict):
                    continue
                if "id" not in record:
                    continue
                entries.append(record)
    except OSError as e:
        logger.warning("Failed to read %s: %s", path, e)
        return []
    # Sort newest-first by updated_at (ISO 8601 sorts lexicographically)
    entries.sort(key=lambda r: r.get("updated_at", ""), reverse=True)
    return entries[:limit] if limit is not None else entries


def _find_rollout_file(codex_home: Path, session_id: str) -> Optional[Path]:
    """
    Locate the rollout JSONL file for a given session id.

    Codex stores rollouts under sessions/YYYY/MM/DD/rollout-<ts>-<id>.jsonl.
    We glob for files whose name contains the id rather than reconstructing
    the timestamp path from updated_at (more robust to format drift).
    """
    sessions_dir = codex_home / "sessions"
    if not sessions_dir.is_dir():
        return None
    matches = list(sessions_dir.rglob(f"rollout-*-{session_id}.jsonl"))
    if not matches:
        return None
    return matches[0]


def _read_session_meta(rollout_path: Path) -> Optional[dict]:
    """
    Read the first ``session_meta`` record from a rollout JSONL.

    Returns the ``payload`` dict (with cwd, timestamp, originator, etc.) or
    None if the file is missing / malformed / has no session_meta event.
    Does NOT read the full rollout (those files can be 100KB+).
    """
    if not rollout_path.is_file():
        return None
    try:
        with open(rollout_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(record, dict) and record.get("type") == "session_meta":
                    payload = record.get("payload")
                    return payload if isinstance(payload, dict) else None
                # session_meta is always the first real event; bail after
                # checking one non-empty line to avoid reading the whole file.
                return None
    except OSError as e:
        logger.warning("Failed to read rollout %s: %s", rollout_path, e)
    return None


def _timestamp_to_iso_date(ts: str) -> Optional[str]:
    """Extract YYYY-MM-DD from an ISO 8601 timestamp string."""
    if not ts:
        return None
    # Accept both "2026-04-15T12:00:00Z" and "2026-04-15T12:00:00.123456+00:00"
    try:
        # Strip trailing Z for fromisoformat compat pre-3.11
        normalized = ts.replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)
        return dt.date().isoformat()
    except ValueError:
        # Last resort: first 10 chars if they look date-like
        if len(ts) >= 10 and ts[4] == "-" and ts[7] == "-":
            return ts[:10]
        return None


def _index_entry_to_session(
    codex_home: Path, entry: dict, include_rollout_meta: bool = True
) -> Optional[Session]:
    """
    Build a Session from one session_index entry, optionally enriching with
    rollout session_meta for cwd.
    """
    session_id = entry.get("id")
    if not isinstance(session_id, str):
        return None
    updated_at = entry.get("updated_at") or ""
    thread_name = entry.get("thread_name") or "(untitled)"
    session_date = _timestamp_to_iso_date(updated_at)
    if not session_date:
        return None

    cwd: Optional[str] = None
    if include_rollout_meta:
        rollout = _find_rollout_file(codex_home, session_id)
        if rollout is not None:
            meta = _read_session_meta(rollout)
            if meta:
                cwd = meta.get("cwd") if isinstance(meta.get("cwd"), str) else None

    return Session(
        date=session_date,
        cwd=cwd,
        project_focus=[],
        key_actions=[str(thread_name)],
        files_touched=[],
    )


# -- Adapter class -------------------------------------------------------------


class CodexAdapter:
    """
    External adapter for OpenAI Codex CLI.

    Reads session metadata from ``~/.codex/session_index.jsonl`` and enriches
    each entry with ``cwd`` from the corresponding rollout file's
    ``session_meta`` record. Optional ``~/codex-brain/`` presence is
    reported in health_check but not yet parsed (deferred).
    """

    agent_id = AGENT_ID
    agent_type = AGENT_TYPE

    def __init__(self) -> None:
        self._codex_home = _resolve_codex_home()
        self._codex_brain = _resolve_codex_brain()
        self.native_path = str(self._codex_home or (Path.home() / ".codex"))

    # -- Protocol methods ------------------------------------------------------

    def discover(self) -> AgentStore:
        sources = {
            "codex_home": str(self._codex_home) if self._codex_home else None,
            "session_index": None,
            "sessions_dir": None,
            "codex_brain": str(self._codex_brain) if self._codex_brain else None,
        }
        if self._codex_home is not None:
            idx = self._codex_home / "session_index.jsonl"
            if idx.is_file():
                sources["session_index"] = str(idx)
            sessions = self._codex_home / "sessions"
            if sessions.is_dir():
                sources["sessions_dir"] = str(sessions)
        if not any(sources.values()):
            raise AdapterDiscoveryError(
                "No Codex memory sources found. Expected ~/.codex/ and/or "
                "~/codex-brain/."
            )
        return AgentStore(
            path=self.native_path,
            version="codex-cli-rollout-v1",
            metadata={"sources": sources},
        )

    def export_sessions(
        self, since: datetime, limit: int = 100
    ) -> list[Session]:
        if self._codex_home is None:
            return []
        idx_path = self._codex_home / "session_index.jsonl"
        entries = _parse_session_index(idx_path, limit=limit)
        cutoff: Optional[date] = since.date() if since else None
        sessions: list[Session] = []
        for entry in entries:
            session = _index_entry_to_session(self._codex_home, entry)
            if session is None:
                continue
            if cutoff is not None:
                try:
                    parsed = date.fromisoformat(session.date)
                except ValueError:
                    continue
                if parsed < cutoff:
                    continue
            sessions.append(session)
        return sessions

    def export_l5(self, since: Optional[datetime] = None) -> L5Manifest:
        """Build L5 manifest combining sessions + topic entities from thread_names."""
        store = self.discover()  # re-raises on missing
        capabilities = sorted(k for k, v in store.metadata["sources"].items() if v)

        # Sessions (empty if ~/.codex/ not present)
        if self._codex_home is None:
            sessions: list[Session] = []
            thread_entries: list[dict] = []
        else:
            idx_path = self._codex_home / "session_index.jsonl"
            thread_entries = _parse_session_index(idx_path)
            # For export_l5 we pass since=None by convention (caller wants the full
            # manifest), but respect it if provided.
            cutoff = since.date() if since else None
            sessions = []
            for entry in thread_entries:
                s = _index_entry_to_session(self._codex_home, entry)
                if s is None:
                    continue
                if cutoff is not None:
                    try:
                        parsed = date.fromisoformat(s.date)
                    except ValueError:
                        continue
                    if parsed < cutoff:
                        continue
                sessions.append(s)

        # Entities: dedupe thread_names (case-insensitive).
        # Each unique thread_name becomes a topic-type entity with the
        # most-recent updated_at as last_touched.
        entities: dict[str, Entity] = {}
        for entry in thread_entries:
            name = entry.get("thread_name")
            if not isinstance(name, str) or not name.strip():
                continue
            key = name.strip().lower()
            updated_iso = _timestamp_to_iso_date(entry.get("updated_at") or "")
            if key in entities:
                # Keep most-recent last_touched
                if updated_iso and (
                    entities[key].last_touched is None
                    or updated_iso > (entities[key].last_touched or "")
                ):
                    entities[key].last_touched = updated_iso
                continue
            entities[key] = Entity(
                name=name.strip(),
                type="topic",
                summary=None,
                last_touched=updated_iso,
                tags=["codex-thread"],
            )

        visible_entities = filter_for_federation(
            sorted(entities.values(), key=lambda e: e.name.lower()),
            DEFAULT_POLICY,
        )

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
            recent_sessions=sessions,
            known_entities=visible_entities,
            visibility_policy=DEFAULT_POLICY,
        )

    def health_check(self) -> HealthStatus:
        """
        Classification:
            - ok        -- ~/.codex/ + session_index.jsonl + sessions/ all present
            - degraded  -- ~/.codex/ present but one sub-source missing
            - blocked   -- ~/.codex/ missing entirely
        """
        details: dict[str, Any] = {
            "codex_home": str(self._codex_home) if self._codex_home else "missing",
            "session_index": "missing",
            "sessions_dir": "missing",
            "codex_brain": str(self._codex_brain) if self._codex_brain else "missing",
        }
        if self._codex_home is None:
            return HealthStatus(
                status="blocked",
                reason="~/.codex/ not found -- Codex CLI never used on this machine",
                details=details,
            )
        idx = self._codex_home / "session_index.jsonl"
        sessions = self._codex_home / "sessions"
        idx_ok = idx.is_file()
        sessions_ok = sessions.is_dir()
        if idx_ok:
            details["session_index"] = str(idx)
        if sessions_ok:
            details["sessions_dir"] = str(sessions)
        if idx_ok and sessions_ok:
            return HealthStatus(status="ok", details=details)
        missing = [
            name
            for name, ok in (("session_index", idx_ok), ("sessions_dir", sessions_ok))
            if not ok
        ]
        return HealthStatus(
            status="degraded",
            reason=f"Missing Codex sub-sources: {', '.join(missing)}",
            details=details,
        )


# Protocol conformance check at import time
_: ContinuoAdapter = CodexAdapter()
