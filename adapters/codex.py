"""Codex adapter -- normalize Codex memories + sessions into L5 manifests."""

from __future__ import annotations

import json
import logging
import re
import socket
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from adapters.base import (
    SPEC_VERSION,
    AdapterDiscoveryError,
    AgentInfo,
    AgentStore,
    ContinuoAdapter,
    Entity,
    HealthStatus,
    L5Manifest,
    Session,
    Visibility,
    VisibilityPolicy,
    filter_for_federation,
)

logger = logging.getLogger(__name__)

AGENT_ID = "codex"
AGENT_TYPE = "code-assistant"

DEFAULT_POLICY = VisibilityPolicy(
    default=Visibility.TEAM,
    private_tags=[
        "personal",
        "financial",
        "credential",
        "health",
        "family",
        "legal",
    ],
    team_tags=["codex-memory", "workspace"],
)

_GENERIC_PROJECT_NAMES = {
    "access",
    "add",
    "after",
    "align",
    "and",
    "android",
    "app",
    "apps",
    "api",
    "archive",
    "architecture",
    "assess",
    "assistant",
    "back",
    "backend",
    "backup",
    "backups",
    "billing",
    "bin",
    "build",
    "building",
    "bootstrap",
    "camerax",
    "chat",
    "check",
    "clean",
    "claude",
    "code",
    "codex",
    "commit",
    "compose",
    "config",
    "console",
    "contracts",
    "create",
    "current",
    "data",
    "decide",
    "desktop",
    "determine",
    "dev",
    "diagnose",
    "dns",
    "doc",
    "docs",
    "documents",
    "drive",
    "editor",
    "env",
    "exact",
    "fastify",
    "file",
    "files",
    "find",
    "finish",
    "fixtures",
    "folder",
    "folders",
    "for",
    "foundation",
    "fresh",
    "from",
    "full",
    "get",
    "git",
    "github",
    "google",
    "gradle",
    "handoff",
    "home",
    "improve",
    "implement",
    "install",
    "into",
    "ios",
    "inventory",
    "java",
    "jetpack",
    "kit",
    "kotlin",
    "layout",
    "letters",
    "local",
    "locate",
    "mac",
    "memory",
    "machine",
    "map",
    "model",
    "move",
    "migration",
    "monorepo",
    "native",
    "new",
    "node",
    "notes",
    "npm",
    "off",
    "old",
    "onedrive",
    "parity",
    "play",
    "plan",
    "prepare",
    "preserve",
    "project",
    "projects",
    "push",
    "read",
    "react",
    "readiness",
    "recover",
    "recovery",
    "rebuild",
    "reinstall",
    "repo",
    "repos",
    "reset",
    "restore",
    "robocopy",
    "review",
    "root",
    "scaffold",
    "session",
    "sdk",
    "src",
    "state",
    "storage",
    "strategy",
    "studio",
    "swiftui",
    "the",
    "tooling",
    "triage",
    "update",
    "user",
    "users",
    "web",
    "with",
    "windows",
    "workspace",
    "save",
    "small",
    "merge",
    "inspect",
}

_MEMORY_SECTION_KEYS = (
    "task_groups",
    "task_titles",
    "preferences",
    "keywords",
    "descriptions",
)


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip())


def _split_csv(value: str) -> list[str]:
    return [
        part.strip().strip("`")
        for part in value.split(",")
        if part.strip().strip("`")
    ]


def _dedupe_preserve(
    items: list[str], key: callable | None = None
) -> list[str]:
    key = key or (lambda item: item)
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        marker = key(item)
        if marker in seen:
            continue
        seen.add(marker)
        result.append(item)
    return result


def _friendly_label(identifier: str) -> str:
    label = identifier.replace("_", " ").replace("-", " ").strip()
    if label.islower():
        return label.title()
    return label


def _empty_memory_sections() -> dict[str, list[str]]:
    return {key: [] for key in _MEMORY_SECTION_KEYS}


def _merge_visibility(
    current: Visibility | None, other: Visibility | None
) -> Visibility | None:
    order = {Visibility.PRIVATE: 0, Visibility.TEAM: 1, Visibility.PUBLIC: 2, None: 3}
    return other if order[other] < order[current] else current


def _merge_entity(into: Entity, other: Entity) -> None:
    if other.summary and not into.summary:
        into.summary = other.summary
    if other.last_touched and (
        into.last_touched is None or other.last_touched > into.last_touched
    ):
        into.last_touched = other.last_touched
    into.visibility = _merge_visibility(into.visibility, other.visibility)
    for alias in other.aliases:
        if alias not in into.aliases:
            into.aliases.append(alias)
    for tag in other.tags:
        if tag not in into.tags:
            into.tags.append(tag)


# -- Path resolution -----------------------------------------------------------


def _resolve_codex_home(base_home: Path | None = None) -> Path | None:
    """Locate `~/.codex/` (the primary Codex store)."""
    home = Path(base_home) if base_home else Path.home()
    candidate = home / ".codex"
    return candidate if candidate.is_dir() else None


def _resolve_codex_brain(base_home: Path | None = None) -> Path | None:
    """Locate the optional `~/codex-brain/` overlay."""
    home = Path(base_home) if base_home else Path.home()
    candidate = home / "codex-brain"
    return candidate if candidate.is_dir() else None


# -- Parsing helpers -----------------------------------------------------------


def _parse_session_index(path: Path, limit: int | None = None) -> list[dict]:
    """Read `session_index.jsonl` newest-first by `updated_at`."""
    if not path.is_file():
        return []
    entries: list[dict] = []
    try:
        with open(path, encoding="utf-8") as f:
            for line_num, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as exc:
                    logger.warning(
                        "Skipping malformed JSONL in %s:%d -- %s",
                        path,
                        line_num,
                        exc,
                    )
                    continue
                if isinstance(record, dict) and isinstance(record.get("id"), str):
                    entries.append(record)
    except OSError as exc:
        logger.warning("Failed to read %s: %s", path, exc)
        return []
    entries.sort(key=lambda record: record.get("updated_at", ""), reverse=True)
    return entries[:limit] if limit is not None else entries


def _find_rollout_file(codex_home: Path, session_id: str) -> Path | None:
    """Locate the rollout JSONL for a session id."""
    sessions_dir = codex_home / "sessions"
    if not sessions_dir.is_dir():
        return None
    matches = list(sessions_dir.rglob(f"rollout-*-{session_id}.jsonl"))
    return matches[0] if matches else None


def _iter_rollout_records(rollout_path: Path) -> list[dict[str, Any]]:
    if not rollout_path.is_file():
        return []
    records: list[dict[str, Any]] = []
    try:
        with open(rollout_path, encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    record = json.loads(stripped)
                except json.JSONDecodeError:
                    continue
                if isinstance(record, dict):
                    records.append(record)
    except OSError as exc:
        logger.warning("Failed to read rollout %s: %s", rollout_path, exc)
    return records


def _read_session_meta(rollout_path: Path) -> dict | None:
    """Return the first `session_meta.payload` dict from a rollout JSONL."""
    for record in _iter_rollout_records(rollout_path)[:5]:
        if record.get("type") == "session_meta":
            payload = record.get("payload")
            return payload if isinstance(payload, dict) else None
    return None


def _extract_files_from_patch(patch_text: str) -> list[str]:
    if not patch_text:
        return []
    files: list[str] = []
    patterns = (
        r"^\*\*\* (?:Update|Add|Delete) File: (.+)$",
        r"^\*\*\* Move to: (.+)$",
    )
    for line in patch_text.splitlines():
        for pattern in patterns:
            match = re.match(pattern, line.strip())
            if match:
                files.append(match.group(1).strip())
    return _dedupe_preserve(files, key=lambda item: item.lower())


def _extract_structured_files_touched(rollout_path: Path) -> list[str]:
    """Collect edited files from structured tool calls only."""
    files: list[str] = []
    for record in _iter_rollout_records(rollout_path):
        if record.get("type") != "response_item":
            continue
        payload = record.get("payload")
        if not isinstance(payload, dict):
            continue
        if payload.get("type") != "function_call":
            continue
        if payload.get("name") != "apply_patch":
            continue
        arguments = payload.get("arguments")
        if isinstance(arguments, str):
            files.extend(_extract_files_from_patch(arguments))
    return _dedupe_preserve(files, key=lambda item: item.lower())


def _timestamp_to_iso_date(ts: str) -> str | None:
    """Extract `YYYY-MM-DD` from an ISO-ish timestamp string."""
    if not ts:
        return None
    try:
        normalized = ts.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized).date().isoformat()
    except ValueError:
        if len(ts) >= 10 and ts[4] == "-" and ts[7] == "-":
            return ts[:10]
        return None


def _path_basename(path_value: str | None) -> str | None:
    if not isinstance(path_value, str) or not path_value.strip():
        return None
    parts = [part for part in re.split(r"[\\/]+", path_value.strip()) if part]
    return parts[-1] if parts else None


def _project_key_from_cwd(cwd: str | None) -> str | None:
    basename = _path_basename(cwd)
    if not basename:
        return None
    key = basename.strip().lower()
    if (
        key in _GENERIC_PROJECT_NAMES
        or key == Path.home().name.lower()
        or _looks_like_generated_workspace_name(key)
    ):
        return None
    return key


def _looks_like_generated_workspace_name(value: str) -> bool:
    return bool(
        re.match(r"^\d{4}[-_ ]\d{2}[-_ ]\d{2}", value)
        or value.startswith("202")
        or ("codex" in value and any(char.isdigit() for char in value))
    )


def _best_display_name(identifier: str, phrases: list[str]) -> str:
    pattern = re.compile(rf"\b{re.escape(identifier)}\b", re.IGNORECASE)
    candidates: list[str] = []
    for phrase in phrases:
        if not isinstance(phrase, str):
            continue
        for match in pattern.finditer(phrase):
            candidates.append(match.group(0))
    if candidates:
        counts = Counter(candidates)
        return sorted(
            counts.items(),
            key=lambda item: (-item[1], item[0].islower(), -len(item[0])),
        )[0][0]
    return _friendly_label(identifier)


def _extract_project_candidates(memory_data: dict[str, Any]) -> list[str]:
    counts: Counter[str] = Counter()
    stopwords = set(_GENERIC_PROJECT_NAMES)
    stopwords.add(Path.home().name.lower())

    for keyword in memory_data["keywords"]:
        tokens = re.findall(r"[A-Za-z][A-Za-z0-9-]{2,}", keyword)
        if not tokens:
            continue
        if len(tokens) == 1:
            candidate = tokens[0].strip("-").lower()
            if candidate in stopwords:
                continue
            counts[candidate] += 1
            continue

        for token in tokens:
            candidate = token.strip("-").lower()
            if candidate in stopwords:
                continue
            if token[0].isupper() or any(char.isupper() for char in token[1:]):
                counts[candidate] += 1

    for task_group in memory_data["task_groups"]:
        tokens = re.findall(r"[A-Za-z][A-Za-z0-9-]{2,}", task_group)
        if not tokens:
            continue
        lead_token = tokens[0].strip("-")
        candidate = lead_token.lower()
        if candidate in stopwords:
            continue
        if not (
            len(tokens) == 1
            or task_group == task_group.lower()
            or lead_token[0].isupper()
            or any(char.isupper() for char in lead_token[1:])
        ):
            continue
        counts[candidate] += 1

    return [
        candidate
        for candidate, count in counts.most_common()
        if count >= 2 and not _looks_like_generated_workspace_name(candidate)
    ]


def _pick_project_label(
    record: dict[str, Any],
    project_labels: dict[str, str],
    preferred_projects: list[str],
    thread_context: dict[str, list[str]] | None = None,
) -> str | None:
    def match_project(phrases: list[str]) -> str | None:
        for phrase in phrases:
            for project_key, project_label in project_labels.items():
                if re.search(
                    rf"\b{re.escape(project_key)}\b",
                    phrase,
                    re.IGNORECASE,
                ) or re.search(
                    rf"\b{re.escape(project_label)}\b",
                    phrase,
                    re.IGNORECASE,
                ):
                    return project_label
        return None

    project_key = _project_key_from_cwd(record.get("cwd"))
    if project_key and project_key in project_labels:
        return project_labels[project_key]

    if thread_context:
        thread_phrases = (
            thread_context["task_groups"]
            + thread_context["task_titles"]
            + thread_context["keywords"]
            + thread_context["descriptions"]
        )
        matched = match_project(thread_phrases)
        if matched:
            return matched

    thread_name = str(record.get("thread_name") or "")
    matched = match_project([thread_name])
    if matched:
        return matched

    if len(preferred_projects) == 1:
        return preferred_projects[0]
    return None


def _parse_memory_text(text: str) -> dict[str, list[str]]:
    """Extract task groups, task titles, preferences, keywords, and descriptions."""
    result = _empty_memory_sections()
    current_section: str | None = None

    for raw_line in text.splitlines():
        line = _normalize_text(raw_line)
        if not line:
            continue
        lower = line.lower()

        if line.startswith("# Task Group:"):
            result["task_groups"].append(
                _normalize_text(line.split(":", 1)[1])
            )
            current_section = None
            continue

        if re.match(r"^#{1,3}\s*Task\b", line):
            title = line.split(":", 1)[1] if ":" in line else re.sub(
                r"^#{1,3}\s*", "", line
            )
            result["task_titles"].append(_normalize_text(title))
            current_section = None
            continue

        if line.startswith("# ") and not lower.startswith("# raw memories"):
            result["task_groups"].append(_normalize_text(line[2:]))
            current_section = None
            continue

        if lower.startswith("task_group:"):
            result["task_groups"].append(
                _normalize_text(line.split(":", 1)[1]).replace("-", " ")
            )
            current_section = None
            continue

        if lower.startswith("task:"):
            result["task_titles"].append(
                _normalize_text(line.split(":", 1)[1]).replace("-", " ")
            )
            current_section = None
            continue

        if lower.startswith("description:"):
            result["descriptions"].append(_normalize_text(line.split(":", 1)[1]))
            continue

        if lower.startswith("keywords:"):
            result["keywords"].extend(_split_csv(line.split(":", 1)[1]))
            current_section = None
            continue

        if lower in {
            "## user preferences",
            "### user preferences",
            "## preference signals",
            "### preference signals",
        } or lower == "preference signals:":
            current_section = "preferences"
            continue

        if lower in {"## keywords", "### keywords"}:
            current_section = "keywords"
            continue

        if lower in {
            "## reusable knowledge",
            "### reusable knowledge",
        } or lower == "reusable knowledge:":
            current_section = "descriptions"
            continue

        if (
            lower in {
                "key steps:",
                "failures and how to do differently:",
                "references:",
                "rollout context:",
            }
            or re.match(r"^[a-z][a-z0-9 /()'`-]*:$", lower)
        ):
            current_section = None
            continue

        if line.startswith("- "):
            bullet = _normalize_text(line[2:])
            if current_section == "preferences":
                result["preferences"].append(bullet)
            elif current_section == "keywords":
                result["keywords"].extend(_split_csv(bullet))
            elif current_section == "descriptions":
                result["descriptions"].append(bullet)

    for key, values in result.items():
        result[key] = _dedupe_preserve(
            [value for value in values if value],
            key=lambda item: item.lower(),
        )
    return result


def _parse_raw_memories_threads(text: str) -> dict[str, dict[str, list[str]]]:
    thread_contexts: dict[str, dict[str, list[str]]] = {}
    current_thread_id: str | None = None
    current_lines: list[str] = []

    def flush_current() -> None:
        if not current_thread_id:
            return
        parsed = _parse_memory_text("\n".join(current_lines))
        if not any(parsed.values()):
            return
        existing = thread_contexts.setdefault(
            current_thread_id,
            _empty_memory_sections(),
        )
        _extend_memory_data(existing, parsed)

    for raw_line in text.splitlines():
        thread_match = re.match(r"^##\s+Thread\s+`([^`]+)`", raw_line.strip())
        if thread_match:
            flush_current()
            current_thread_id = _normalize_text(thread_match.group(1))
            current_lines = []
            continue
        if current_thread_id:
            current_lines.append(raw_line)

    flush_current()
    return thread_contexts


def _extend_memory_data(
    into: dict[str, Any], parsed: dict[str, list[str]]
) -> None:
    for key in _MEMORY_SECTION_KEYS:
        into[key].extend(parsed.get(key, []))
        into[key] = _dedupe_preserve(
            into[key],
            key=lambda item: item.lower(),
        )


def _collect_memory_data(
    codex_home: Path | None, codex_brain: Path | None
) -> dict[str, Any]:
    data: dict[str, Any] = {
        **_empty_memory_sections(),
        "thread_contexts": {},
        "source_counts": {
            "memory_md": 0,
            "raw_memories": 0,
            "rollout_summaries": 0,
            "codex_brain_files": 0,
        },
    }

    memories_dir = codex_home / "memories" if codex_home else None
    if memories_dir and memories_dir.is_dir():
        memory_md = memories_dir / "MEMORY.md"
        raw_memories = memories_dir / "raw_memories.md"
        rollout_summaries = memories_dir / "rollout_summaries"

        if memory_md.is_file():
            data["source_counts"]["memory_md"] += 1
            _extend_memory_data(
                data, _parse_memory_text(memory_md.read_text(encoding="utf-8"))
            )
        if raw_memories.is_file():
            data["source_counts"]["raw_memories"] += 1
            raw_text = raw_memories.read_text(encoding="utf-8")
            _extend_memory_data(data, _parse_memory_text(raw_text))
            for thread_id, parsed in _parse_raw_memories_threads(raw_text).items():
                existing = data["thread_contexts"].setdefault(
                    thread_id,
                    _empty_memory_sections(),
                )
                _extend_memory_data(existing, parsed)
        if rollout_summaries.is_dir():
            for summary_file in sorted(rollout_summaries.glob("*.md")):
                data["source_counts"]["rollout_summaries"] += 1
                _extend_memory_data(
                    data,
                    _parse_memory_text(summary_file.read_text(encoding="utf-8")),
                )

    if codex_brain and codex_brain.is_dir():
        for path in sorted(codex_brain.rglob("*")):
            if not path.is_file() or path.stat().st_size == 0:
                continue
            if not any(
                str(path).lower().endswith(suffix)
                for suffix in (".md", ".txt", ".md.txt")
            ):
                continue
            data["source_counts"]["codex_brain_files"] += 1
            _extend_memory_data(
                data,
                _parse_memory_text(path.read_text(encoding="utf-8")),
            )

    return data


def _collect_session_records(
    codex_home: Path | None, limit: int | None = None
) -> list[dict[str, Any]]:
    if codex_home is None:
        return []
    entries = _parse_session_index(codex_home / "session_index.jsonl", limit=limit)
    records: list[dict[str, Any]] = []
    for entry in entries:
        session_id = entry.get("id")
        if not isinstance(session_id, str):
            continue
        rollout = _find_rollout_file(codex_home, session_id)
        meta = _read_session_meta(rollout) if rollout else {}
        updated_at = entry.get("updated_at") or meta.get("timestamp") or ""
        session_date = _timestamp_to_iso_date(str(updated_at))
        if not session_date:
            continue
        records.append(
            {
                "id": session_id,
                "thread_name": _normalize_text(
                    str(entry.get("thread_name") or "(untitled)")
                ),
                "updated_at": str(updated_at),
                "date": session_date,
                "cwd": meta.get("cwd") if isinstance(meta.get("cwd"), str) else None,
                "model_provider": meta.get("model_provider")
                if isinstance(meta.get("model_provider"), str)
                else None,
                "cli_version": meta.get("cli_version")
                if isinstance(meta.get("cli_version"), str)
                else None,
                "originator": meta.get("originator")
                if isinstance(meta.get("originator"), str)
                else None,
                "source": meta.get("source")
                if isinstance(meta.get("source"), str)
                else None,
                "files_touched": (
                    _extract_structured_files_touched(rollout) if rollout else []
                ),
            }
        )
    return records


def _record_to_session(record: dict[str, Any], project_label: str | None = None) -> Session:
    project_focus = [project_label] if project_label else []
    return Session(
        date=record["date"],
        cwd=record.get("cwd"),
        project_focus=project_focus,
        key_actions=[record["thread_name"]],
        files_touched=list(record.get("files_touched") or []),
        visibility=Visibility.TEAM,
    )


# -- Adapter class -------------------------------------------------------------


class CodexAdapter:
    """External adapter for local Codex memories, sessions, and overlays."""

    agent_id = AGENT_ID
    agent_type = AGENT_TYPE

    def __init__(
        self,
        codex_home: Path | None = None,
        codex_brain: Path | None = None,
    ) -> None:
        if codex_home is not None:
            self._codex_home = Path(codex_home)
        else:
            self._codex_home = _resolve_codex_home()
        if codex_brain is not None:
            self._codex_brain = Path(codex_brain)
        else:
            self._codex_brain = _resolve_codex_brain()
        self.native_path = str(self._codex_home or (Path.home() / ".codex"))

    def discover(self) -> AgentStore:
        memories_dir = self._codex_home / "memories" if self._codex_home else None
        rollout_summaries = memories_dir / "rollout_summaries" if memories_dir else None
        sources = {
            "codex_home": str(self._codex_home) if self._codex_home else None,
            "session_index": None,
            "sessions_dir": None,
            "memories_dir": str(memories_dir) if memories_dir and memories_dir.is_dir() else None,
            "memory_md": None,
            "raw_memories": None,
            "rollout_summaries_dir": (
                str(rollout_summaries) if rollout_summaries and rollout_summaries.is_dir() else None
            ),
            "codex_brain": str(self._codex_brain) if self._codex_brain else None,
        }
        if self._codex_home is not None:
            session_index = self._codex_home / "session_index.jsonl"
            sessions_dir = self._codex_home / "sessions"
            if session_index.is_file():
                sources["session_index"] = str(session_index)
            if sessions_dir.is_dir():
                sources["sessions_dir"] = str(sessions_dir)
            if memories_dir and (memories_dir / "MEMORY.md").is_file():
                sources["memory_md"] = str(memories_dir / "MEMORY.md")
            if memories_dir and (memories_dir / "raw_memories.md").is_file():
                sources["raw_memories"] = str(memories_dir / "raw_memories.md")
        if not any(sources.values()):
            raise AdapterDiscoveryError(
                "No Codex memory sources found. Expected ~/.codex/ and/or ~/codex-brain/."
            )
        return AgentStore(
            path=self.native_path,
            version="codex-memory-v2",
            metadata={"sources": sources},
        )

    def export_sessions(self, since: datetime, limit: int = 100) -> list[Session]:
        cutoff = since.date() if since else None
        sessions: list[Session] = []
        for record in _collect_session_records(self._codex_home, limit=limit):
            try:
                parsed = date.fromisoformat(record["date"])
            except ValueError:
                continue
            if cutoff and parsed < cutoff:
                continue
            project_key = _project_key_from_cwd(record.get("cwd"))
            project_label = _friendly_label(project_key) if project_key else None
            sessions.append(_record_to_session(record, project_label=project_label))
        return sessions

    def export_l5(self, since: datetime | None = None) -> L5Manifest:
        store = self.discover()
        capabilities = sorted(
            key for key, value in store.metadata["sources"].items() if value
        )
        records = _collect_session_records(self._codex_home)
        memory_data = _collect_memory_data(self._codex_home, self._codex_brain)
        phrases = (
            memory_data["keywords"]
            + memory_data["task_groups"]
            + memory_data["task_titles"]
            + [record["thread_name"] for record in records]
        )

        project_labels: dict[str, str] = {}
        entity_map: dict[tuple[str, str], Entity] = {}
        preferred_project_keys = _extract_project_candidates(memory_data)

        project_counts = Counter(
            project_key
            for project_key in (
                _project_key_from_cwd(record.get("cwd")) for record in records
            )
            if project_key
        )
        for project_key, count in project_counts.items():
            label = _best_display_name(project_key, phrases)
            project_labels[project_key] = label
            descriptions = [
                text
                for text in memory_data["descriptions"] + memory_data["task_groups"]
                if project_key in text.lower()
            ]
            summary = (
                descriptions[0]
                if descriptions
                else f"Observed across {count} Codex session(s)."
            )
            entity = Entity(
                name=label,
                type="project",
                summary=summary,
                last_touched=max(
                    (
                        record["date"]
                        for record in records
                        if _project_key_from_cwd(record.get("cwd")) == project_key
                    ),
                    default=None,
                ),
                tags=["codex-project"],
                visibility=Visibility.TEAM,
            )
            entity_map[(entity.type or "topic", entity.name.lower())] = entity

        for project_key in preferred_project_keys:
            label = _best_display_name(project_key, phrases)
            project_labels[project_key] = label
            descriptions = [
                text
                for text in memory_data["descriptions"] + memory_data["task_groups"]
                if re.search(rf"\b{re.escape(project_key)}\b", text, re.IGNORECASE)
            ]
            entity = Entity(
                name=label,
                type="project",
                summary=(
                    descriptions[0]
                    if descriptions
                    else f"Named repeatedly across Codex memory as {label}."
                ),
                tags=["codex-project", "codex-memory"],
                visibility=Visibility.TEAM,
            )
            key = (entity.type or "topic", entity.name.lower())
            if key in entity_map:
                _merge_entity(entity_map[key], entity)
            else:
                entity_map[key] = entity

        preferred_projects = [
            entity.name
            for entity in entity_map.values()
            if entity.type == "project"
        ]

        cutoff = since.date() if since else None
        sessions: list[Session] = []
        for record in records:
            try:
                parsed = date.fromisoformat(record["date"])
            except ValueError:
                continue
            if cutoff and parsed < cutoff:
                continue
            project_label = _pick_project_label(
                record,
                project_labels,
                preferred_projects,
                thread_context=memory_data["thread_contexts"].get(record["id"]),
            )
            sessions.append(_record_to_session(record, project_label=project_label))

            topic = Entity(
                name=record["thread_name"],
                type="topic",
                summary=f"Codex thread: {record['thread_name']}",
                last_touched=record["date"],
                tags=["codex-thread"],
                visibility=Visibility.TEAM,
            )
            key = (topic.type or "topic", topic.name.lower())
            if key in entity_map:
                _merge_entity(entity_map[key], topic)
            else:
                entity_map[key] = topic

        for topic_name in memory_data["task_groups"] + memory_data["task_titles"]:
            topic = Entity(
                name=topic_name,
                type="topic",
                summary=f"Codex memory topic: {topic_name}",
                tags=["codex-memory"],
                visibility=Visibility.TEAM,
            )
            key = (topic.type or "topic", topic.name.lower())
            if key in entity_map:
                _merge_entity(entity_map[key], topic)
            else:
                entity_map[key] = topic

        for preference_text in memory_data["preferences"]:
            preference = Entity(
                name=preference_text,
                type="preference",
                summary=preference_text,
                tags=["codex-preference"],
                visibility=Visibility.TEAM,
            )
            key = (preference.type or "topic", preference.name.lower())
            if key in entity_map:
                _merge_entity(entity_map[key], preference)
            else:
                entity_map[key] = preference

        entities = sorted(
            entity_map.values(),
            key=lambda entity: ((entity.type or "topic"), entity.name.lower()),
        )
        visible_entities = filter_for_federation(entities, DEFAULT_POLICY)

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
        details: dict[str, Any] = {
            "codex_home": str(self._codex_home) if self._codex_home else "missing",
            "session_index": "missing",
            "sessions_dir": "missing",
            "memories_dir": "missing",
            "memory_md": "missing",
            "raw_memories": "missing",
            "rollout_summaries_dir": "missing",
            "codex_brain": str(self._codex_brain) if self._codex_brain else "missing",
        }
        if self._codex_home is None:
            return HealthStatus(
                status="blocked",
                reason="~/.codex/ not found -- Codex CLI never used on this machine",
                details=details,
            )

        session_index = self._codex_home / "session_index.jsonl"
        sessions_dir = self._codex_home / "sessions"
        memories_dir = self._codex_home / "memories"
        if session_index.is_file():
            details["session_index"] = str(session_index)
        if sessions_dir.is_dir():
            details["sessions_dir"] = str(sessions_dir)
        if memories_dir.is_dir():
            details["memories_dir"] = str(memories_dir)
            if (memories_dir / "MEMORY.md").is_file():
                details["memory_md"] = str(memories_dir / "MEMORY.md")
            if (memories_dir / "raw_memories.md").is_file():
                details["raw_memories"] = str(memories_dir / "raw_memories.md")
            if (memories_dir / "rollout_summaries").is_dir():
                details["rollout_summaries_dir"] = str(memories_dir / "rollout_summaries")

        if session_index.is_file() and sessions_dir.is_dir():
            return HealthStatus(status="ok", details=details)

        missing = [
            name
            for name, ok in (
                ("session_index", session_index.is_file()),
                ("sessions_dir", sessions_dir.is_dir()),
            )
            if not ok
        ]
        return HealthStatus(
            status="degraded",
            reason=f"Missing Codex sub-sources: {', '.join(missing)}",
            details=details,
        )


_: ContinuoAdapter = CodexAdapter()
