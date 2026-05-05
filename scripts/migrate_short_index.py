#!/usr/bin/env python3
"""
Migrate short-index payloads to the canonical `entries` schema.

Supports legacy payloads that use:
- top-level `topics` arrays
- `aliases` instead of `triggers`
- `access` instead of `access_level`
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any


def _topic_name_from_key(topic_key: str) -> str:
    words = topic_key.replace("-", "_").split("_")
    filtered = [word for word in words if word]
    if not filtered:
        return topic_key
    return " ".join(word.capitalize() for word in filtered)


def _normalize_entry(raw: dict[str, Any], default_scope: str) -> dict[str, Any] | None:
    topic_key = str(raw.get("topic_key", "")).strip()
    if not topic_key:
        return None

    topic_name = str(raw.get("topic_name", "")).strip() or _topic_name_from_key(topic_key)
    triggers_source = raw.get("triggers", raw.get("aliases", []))
    if isinstance(triggers_source, str):
        triggers = [triggers_source.strip()] if triggers_source.strip() else []
    else:
        triggers = [str(item).strip() for item in triggers_source if str(item).strip()]

    tags_source = raw.get("tags", [])
    if isinstance(tags_source, str):
        tags = [tags_source.strip()] if tags_source.strip() else []
    else:
        tags = [str(item).strip() for item in tags_source if str(item).strip()]

    scope = str(raw.get("scope", default_scope)).strip().lower() or default_scope
    access_level = str(raw.get("access_level", raw.get("access", "team"))).strip().lower() or "team"
    last_updated = str(raw.get("last_updated", date.today().isoformat())).strip() or date.today().isoformat()

    return {
        "topic_key": topic_key,
        "topic_name": topic_name,
        "summary": str(raw.get("summary", "")).strip(),
        "triggers": sorted(set(triggers)),
        "scope": scope,
        "access_level": access_level,
        "last_updated": last_updated,
        "tags": sorted(set(tags)),
    }


def _load_payload(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _uses_legacy_schema(payload: Any) -> bool:
    if isinstance(payload, list):
        return True
    if not isinstance(payload, dict):
        return False
    if "topics" in payload:
        return True

    entries = payload.get("entries")
    if not isinstance(entries, list):
        return False

    for entry in entries:
        if isinstance(entry, dict) and ("aliases" in entry or "access" in entry):
            return True

    return False


def _to_canonical_payload(payload: Any, default_scope: str) -> dict[str, Any]:
    if isinstance(payload, dict) and isinstance(payload.get("entries"), list) and not _uses_legacy_schema(payload):
        return payload

    if isinstance(payload, dict):
        raw_entries = payload.get("entries")
        if not isinstance(raw_entries, list):
            raw_entries = payload.get("topics", [])
    elif isinstance(payload, list):
        raw_entries = payload
    else:
        raw_entries = []

    entries: list[dict[str, Any]] = []
    for raw in raw_entries:
        if not isinstance(raw, dict):
            continue
        normalized = _normalize_entry(raw, default_scope)
        if normalized is not None:
            entries.append(normalized)

    deduped: dict[str, dict[str, Any]] = {}
    for entry in entries:
        deduped[entry["topic_key"].lower()] = entry

    return {
        "version": 1,
        "entries": [deduped[key] for key in sorted(deduped.keys())],
    }


def _default_paths(workspace_root: Path) -> list[Path]:
    return [
        workspace_root / ".cursor" / "memory" / "short-index.json",
        Path.home() / ".cursor" / "memory" / "short-index.json",
    ]


def _scope_for_path(path: Path, workspace_root: Path) -> str:
    workspace_path = workspace_root / ".cursor" / "memory" / "short-index.json"
    return "workspace" if path.resolve() == workspace_path.resolve() else "global"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Migrate short-index JSON to canonical entries schema.")
    parser.add_argument("--workspace-root", type=Path, required=True)
    parser.add_argument(
        "--path",
        dest="paths",
        type=Path,
        action="append",
        default=[],
        help="Specific short-index path to migrate. Repeatable.",
    )
    parser.add_argument("--check", action="store_true", help="Exit non-zero if any file needs migration.")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    workspace_root = args.workspace_root.resolve()
    paths = args.paths or _default_paths(workspace_root)

    checked = 0
    changed = 0
    for path in paths:
        if not path.exists():
            continue
        checked += 1
        payload = _load_payload(path)
        scope = _scope_for_path(path, workspace_root)
        canonical = _to_canonical_payload(payload, scope)
        existing_text = json.dumps(payload, indent=2, ensure_ascii=False).strip()
        canonical_text = json.dumps(canonical, indent=2, ensure_ascii=False).strip()
        if existing_text == canonical_text:
            continue
        changed += 1
        if args.check:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"{canonical_text}\n", encoding="utf-8")
        print(f"Migrated: {path}")

    if args.check and changed:
        print(f"Migration required for {changed} short-index file(s).")
        return 1

    print(f"Checked {checked} short-index file(s); changed {changed}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
