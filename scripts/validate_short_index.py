#!/usr/bin/env python3
"""Validate canonical short-index JSON files."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any


ALLOWED_SCOPES = {"workspace", "global"}
ALLOWED_ACCESS = {"public", "team", "private"}
REQUIRED_FIELDS = {
    "topic_key",
    "topic_name",
    "summary",
    "triggers",
    "scope",
    "access_level",
    "last_updated",
}


def _default_paths(workspace_root: Path) -> list[Path]:
    return [
        workspace_root / ".cursor" / "memory" / "short-index.json",
        Path.home() / ".cursor" / "memory" / "short-index.json",
    ]


def _validate_entry(entry: Any, path: Path, index: int) -> list[str]:
    errors: list[str] = []
    if not isinstance(entry, dict):
        return [f"{path} entry {index}: must be an object"]

    missing = sorted(field for field in REQUIRED_FIELDS if field not in entry)
    if missing:
        errors.append(f"{path} entry {index}: missing fields {missing}")
        return errors

    topic_key = str(entry.get("topic_key", "")).strip()
    if not topic_key:
        errors.append(f"{path} entry {index}: empty topic_key")

    topic_name = str(entry.get("topic_name", "")).strip()
    if not topic_name:
        errors.append(f"{path} entry {index}: empty topic_name")

    triggers = entry.get("triggers")
    if not isinstance(triggers, list) or not triggers:
        errors.append(f"{path} entry {index}: triggers must be a non-empty array")
    else:
        for trigger_idx, trigger in enumerate(triggers):
            if not str(trigger).strip():
                errors.append(f"{path} entry {index}: trigger {trigger_idx} is empty")

    scope = str(entry.get("scope", "")).strip().lower()
    if scope not in ALLOWED_SCOPES:
        errors.append(f"{path} entry {index}: invalid scope {scope!r}")

    access_level = str(entry.get("access_level", "")).strip().lower()
    if access_level not in ALLOWED_ACCESS:
        errors.append(f"{path} entry {index}: invalid access_level {access_level!r}")

    date_value = str(entry.get("last_updated", "")).strip()
    try:
        dt.date.fromisoformat(date_value)
    except ValueError:
        errors.append(f"{path} entry {index}: invalid last_updated date {date_value!r}")

    tags = entry.get("tags", [])
    if not isinstance(tags, list):
        errors.append(f"{path} entry {index}: tags must be an array")

    return errors


def _validate_file(path: Path) -> list[str]:
    errors: list[str] = []
    if not path.exists():
        return errors

    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        return [f"{path}: invalid JSON ({exc})"]

    if not isinstance(payload, dict):
        return [f"{path}: root must be a JSON object"]

    if payload.get("version") != 1:
        errors.append(f"{path}: expected version=1")

    entries = payload.get("entries")
    if not isinstance(entries, list):
        errors.append(f"{path}: entries must be an array")
        return errors

    alias_map: dict[str, set[str]] = {}
    key_map: set[str] = set()
    for index, entry in enumerate(entries):
        errors.extend(_validate_entry(entry, path, index))
        if not isinstance(entry, dict):
            continue
        topic_key = str(entry.get("topic_key", "")).strip().lower()
        if topic_key:
            if topic_key in key_map:
                errors.append(f"{path}: duplicate topic_key {topic_key!r}")
            key_map.add(topic_key)
        aliases = [str(alias).strip().lower() for alias in entry.get("triggers", []) if str(alias).strip()]
        aliases.append(str(entry.get("topic_name", "")).strip().lower())
        for alias in aliases:
            alias_map.setdefault(alias, set()).add(topic_key)

    collisions = {alias: keys for alias, keys in alias_map.items() if alias and len(keys) > 1}
    for alias, keys in sorted(collisions.items()):
        errors.append(f"{path}: alias collision for {alias!r} across {sorted(keys)}")

    return errors


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate short-index canonical schema.")
    parser.add_argument("--workspace-root", type=Path, required=True)
    parser.add_argument(
        "--path",
        dest="paths",
        type=Path,
        action="append",
        default=[],
        help="Specific short-index file to validate. Repeatable.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    workspace_root = args.workspace_root.resolve()
    paths = args.paths or _default_paths(workspace_root)

    errors: list[str] = []
    checked = 0
    for path in paths:
        if not path.exists():
            continue
        checked += 1
        errors.extend(_validate_file(path))

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    print(f"Validated {checked} short-index file(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
