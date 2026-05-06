#!/usr/bin/env python3
"""
Build Bourdon-compatible L5 manifests from hybrid short-index memory.

Inputs:
- Workspace short index: .cursor/memory/short-index.json
- Global short index: ~/.cursor/memory/short-index.json

Outputs:
- Workspace manifest: .cursor/memory/bourdon.l5.yaml
- Global manifest: ~/agent-library/agents/cursor.l5.yaml
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any

import yaml

try:
    import jsonschema
except ImportError:  # pragma: no cover
    jsonschema = None


def _read_json_file(path: Path) -> Any:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _validate_short_index_payload(payload: Any, path: Path, default_scope: str) -> None:
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must be a JSON object.")
    entries = payload.get("entries", [])
    if not isinstance(entries, list):
        raise ValueError(f"{path} field 'entries' must be an array.")

    allowed_scopes = {"workspace", "global"}
    allowed_access = {"public", "team", "private"}
    required_fields = {"topic_key", "topic_name", "summary", "scope", "access_level", "last_updated"}

    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise ValueError(f"{path} entry {index} must be an object.")
        missing = sorted(field for field in required_fields if field not in entry)
        if missing:
            raise ValueError(f"{path} entry {index} missing fields: {missing}")
        if not str(entry.get("topic_key", "")).strip():
            raise ValueError(f"{path} entry {index} has empty topic_key.")
        scope = str(entry.get("scope", default_scope)).strip().lower()
        if scope not in allowed_scopes:
            raise ValueError(f"{path} entry {index} has invalid scope: {scope!r}")
        access_level = str(entry.get("access_level", "team")).strip().lower()
        if access_level not in allowed_access:
            raise ValueError(f"{path} entry {index} has invalid access_level: {access_level!r}")
        try:
            dt.date.fromisoformat(str(entry.get("last_updated", "")))
        except ValueError as exc:
            raise ValueError(f"{path} entry {index} has invalid last_updated date.") from exc


def _normalize_entries(payload: Any, default_scope: str) -> list[dict[str, Any]]:
    entries = payload.get("entries", []) if isinstance(payload, dict) else []
    normalized: list[dict[str, Any]] = []
    for raw in entries:
        if not isinstance(raw, dict):
            continue
        topic_key = str(raw.get("topic_key", "")).strip()
        if not topic_key:
            continue
        normalized.append(
            {
                "topic_key": topic_key,
                "topic_name": str(raw.get("topic_name", topic_key)).strip() or topic_key,
                "summary": str(raw.get("summary", "")).strip(),
                "aliases": [
                    str(alias).strip()
                    for alias in raw.get("triggers", raw.get("aliases", []))
                    if str(alias).strip()
                ],
                "scope": str(raw.get("scope", default_scope)).strip() or default_scope,
                "access_level": str(raw.get("access_level", "team")).strip() or "team",
                "last_updated": str(raw.get("last_updated", dt.date.today().isoformat())),
                "tags": [str(tag).strip() for tag in raw.get("tags", []) if str(tag).strip()],
            }
        )
    return normalized


def _merge_entries(global_entries: list[dict[str, Any]], workspace_entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {entry["topic_key"].lower(): entry for entry in global_entries}
    for entry in workspace_entries:
        merged[entry["topic_key"].lower()] = entry
    return list(merged.values())


def _assert_alias_collisions(entries: list[dict[str, Any]]) -> None:
    alias_map: dict[str, set[str]] = {}
    for entry in entries:
        key = entry["topic_key"].lower()
        for alias in [entry["topic_name"], *entry["aliases"]]:
            norm = alias.strip().lower()
            if not norm:
                continue
            alias_map.setdefault(norm, set()).add(key)
    collisions = {alias: keys for alias, keys in alias_map.items() if len(keys) > 1}
    if collisions:
        detail = ", ".join(f"{alias}: {sorted(keys)}" for alias, keys in sorted(collisions.items()))
        raise ValueError(f"Alias collisions detected: {detail}")


def _assert_overlay_precedence(
    merged: list[dict[str, Any]],
    global_entries: list[dict[str, Any]],
    workspace_entries: list[dict[str, Any]],
) -> None:
    global_map = {entry["topic_key"].lower(): entry for entry in global_entries}
    workspace_map = {entry["topic_key"].lower(): entry for entry in workspace_entries}
    merged_map = {entry["topic_key"].lower(): entry for entry in merged}
    for key in sorted(set(global_map.keys()) & set(workspace_map.keys())):
        if merged_map[key].get("summary") != workspace_map[key].get("summary"):
            raise ValueError(f"Workspace overlay did not win for topic {key!r}.")


def _to_known_entity(entry: dict[str, Any]) -> dict[str, Any]:
    visibility = entry["access_level"].lower()
    if visibility not in {"public", "team", "private"}:
        visibility = "team"
    return {
        "name": entry["topic_name"],
        "type": "topic",
        "aliases": sorted(set(entry["aliases"])),
        "summary": entry["summary"],
        "last_touched": entry["last_updated"],
        "tags": sorted(set(entry["tags"] + [f"scope:{entry['scope']}", "memory-chain"])),
        "visibility": visibility,
    }


def _build_manifest(entries: list[dict[str, Any]], agent_id: str, role_narrative: str) -> dict[str, Any]:
    return {
        "spec_version": "0.1",
        "agent": {
            "id": agent_id,
            "type": "code-assistant",
            "role_narrative": role_narrative,
        },
        "last_updated": dt.datetime.now(dt.timezone.utc).isoformat(),
        "capabilities": [
            "memory-update",
            "keyword-trigger-recall",
            "cross-agent-federation",
        ],
        "recent_sessions": [],
        "known_entities": [_to_known_entity(entry) for entry in sorted(entries, key=lambda item: item["topic_name"].lower())],
        "visibility_policy": {
            "default": "team",
            "private_tags": ["credential", "secret", "pii", "private"],
            "team_tags": ["workspace", "memory-chain", "preference"],
        },
    }


def _validate_manifest_schema(manifest: dict[str, Any], schema_path: Path | None) -> None:
    if jsonschema is None or schema_path is None or not schema_path.exists():
        return
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    jsonschema.validate(instance=manifest, schema=schema)


def _write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Bourdon L5 manifests from hybrid memory.")
    parser.add_argument("--workspace-root", type=Path, required=True)
    parser.add_argument("--global-root", type=Path, default=Path.home() / ".cursor" / "memory")
    parser.add_argument("--workspace-out", type=Path, default=None)
    parser.add_argument("--global-out", type=Path, default=Path.home() / "agent-library" / "agents" / "cursor.l5.yaml")
    parser.add_argument("--schema-path", type=Path, default=None)
    parser.add_argument("--strict-aliases", action="store_true")
    parser.add_argument("--strict-precedence", action="store_true")
    parser.add_argument("--agent-id", default="cursor")
    parser.add_argument(
        "--role-narrative",
        default="Cursor memory maintainer for hybrid short/long memory chains and Bourdon federation exports.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    workspace_index_path = args.workspace_root / ".cursor" / "memory" / "short-index.json"
    global_index_path = args.global_root / "short-index.json"
    workspace_out = args.workspace_out or (args.workspace_root / ".cursor" / "memory" / "bourdon.l5.yaml")

    workspace_payload = _read_json_file(workspace_index_path)
    global_payload = _read_json_file(global_index_path)
    _validate_short_index_payload(workspace_payload, workspace_index_path, "workspace")
    _validate_short_index_payload(global_payload, global_index_path, "global")
    workspace_entries = _normalize_entries(workspace_payload, "workspace")
    global_entries = _normalize_entries(global_payload, "global")
    merged = _merge_entries(global_entries, workspace_entries)

    if args.strict_aliases:
        _assert_alias_collisions(merged)
    if args.strict_precedence:
        _assert_overlay_precedence(merged, global_entries, workspace_entries)

    manifest = _build_manifest(merged, args.agent_id, args.role_narrative)
    _validate_manifest_schema(manifest, args.schema_path)
    _write_yaml(workspace_out, manifest)
    _write_yaml(args.global_out, manifest)

    print(f"Wrote workspace manifest: {workspace_out}")
    print(f"Wrote global manifest: {args.global_out}")
    print(f"Known entities exported: {len(manifest['known_entities'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
