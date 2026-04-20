"""Generate Codex-oriented L0/L1 timing artifacts from an L5 manifest."""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Any

import yaml


def _normalize_visibility(value: str | None) -> str:
    normalized = (value or "public").strip().lower()
    return normalized if normalized in {"public", "team", "private"} else "public"


def _visibility_rank(value: str) -> int:
    return {"public": 0, "team": 1, "private": 2}[_normalize_visibility(value)]


def _is_visible(item: dict[str, Any], access_level: str) -> bool:
    return _visibility_rank(item.get("visibility")) <= _visibility_rank(access_level)


def _slugify(value: str, max_len: int = 80) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    slug = slug or "entity"
    return slug[:max_len].rstrip("-")


def _manifest_dict(manifest: Any) -> dict[str, Any]:
    if hasattr(manifest, "to_dict"):
        return manifest.to_dict()
    return dict(manifest)


def filter_manifest_for_access(
    manifest: Any, access_level: str = "team"
) -> dict[str, Any]:
    """Filter sessions/entities to the requested visibility level."""
    data = _manifest_dict(manifest)
    filtered = dict(data)
    filtered["known_entities"] = [
        entity
        for entity in data.get("known_entities") or []
        if isinstance(entity, dict) and _is_visible(entity, access_level)
    ]
    filtered["recent_sessions"] = [
        session
        for session in data.get("recent_sessions") or []
        if isinstance(session, dict) and _is_visible(session, access_level)
    ]
    return filtered


def build_l0_payload(manifest: Any, access_level: str = "team") -> dict[str, Any]:
    """Build an orchestrator-compatible L0 hot cache payload."""
    data = filter_manifest_for_access(manifest, access_level=access_level)
    entities = data.get("known_entities") or []
    sessions = data.get("recent_sessions") or []
    projects = [entity for entity in entities if entity.get("type") == "project"]
    latest_session = sessions[0] if sessions else {}

    provider_counts = Counter(
        session.get("model_provider")
        for session in sessions
        if isinstance(session.get("model_provider"), str)
        and session.get("model_provider")
    )
    dominant_provider = (
        provider_counts.most_common(1)[0][0] if provider_counts else "openai"
    )
    primary_focus = (
        (latest_session.get("key_actions") or [None])[0]
        or (latest_session.get("project_focus") or [None])[0]
        or "Recent Codex work"
    )
    last_topic = (latest_session.get("key_actions") or [None])[0] or primary_focus

    return {
        "identity": {
            "user": "Codex user",
            "alias": "Codex",
            "company": "OpenAI",
            "role": "Collaborator",
        },
        "projects": [
            {"name": project["name"], "priority": index + 1}
            for index, project in enumerate(projects[:10])
        ],
        "hardware": {
            "local_model": "Codex CLI",
            "inference": str(dominant_provider).title(),
        },
        "current_focus": {
            "primary": primary_focus,
            "last_session": latest_session.get("date") or "",
            "last_topic": last_topic,
        },
        "entities": [
            {
                "keyword": entity["name"],
                "type": entity.get("type") or "topic",
            }
            for entity in entities
        ],
    }


def build_l1_documents(
    manifest: Any, access_level: str = "team"
) -> dict[str, str]:
    """Build markdown synopses keyed by slugified entity name."""
    data = filter_manifest_for_access(manifest, access_level=access_level)
    docs: dict[str, str] = {}
    for entity in data.get("known_entities") or []:
        slug = _slugify(entity.get("name") or "entity")
        tags = ", ".join(entity.get("tags") or [])
        aliases = ", ".join(entity.get("aliases") or [])
        summary = entity.get("summary") or "No summary available."
        body_lines = [
            f"# {entity.get('name')}",
            "",
            f"- Type: {entity.get('type') or 'topic'}",
            f"- Visibility: {_normalize_visibility(entity.get('visibility'))}",
            f"- Last touched: {entity.get('last_touched') or 'unknown'}",
        ]
        if tags:
            body_lines.append(f"- Tags: {tags}")
        if aliases:
            body_lines.append(f"- Aliases: {aliases}")
        body_lines.extend(["", summary.strip()])
        docs[slug] = "\n".join(body_lines).strip() + "\n"
    return docs


def write_codex_context_artifacts(
    manifest: Any, out_dir: Path, access_level: str = "team"
) -> dict[str, Any]:
    """Write `l0/hot_cache.yaml` plus `l1/*.md` files to `out_dir`."""
    out_dir = Path(out_dir)
    l0_dir = out_dir / "l0"
    l1_dir = out_dir / "l1"
    l0_dir.mkdir(parents=True, exist_ok=True)
    l1_dir.mkdir(parents=True, exist_ok=True)

    l0_payload = build_l0_payload(manifest, access_level=access_level)
    l1_docs = build_l1_documents(manifest, access_level=access_level)

    l0_path = l0_dir / "hot_cache.yaml"
    l0_path.write_text(
        yaml.safe_dump(l0_payload, sort_keys=False),
        encoding="utf-8",
    )
    for slug, body in l1_docs.items():
        (l1_dir / f"{slug}.md").write_text(body, encoding="utf-8")

    return {
        "l0_path": str(l0_path),
        "l1_dir": str(l1_dir),
        "l1_count": len(l1_docs),
        "l0_generated": l0_path.is_file(),
        "l1_generated": bool(l1_docs),
    }
