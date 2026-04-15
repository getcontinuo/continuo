"""Tests for adapters.codex -- Codex CLI external adapter."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from adapters.base import (
    AdapterDiscoveryError,
    ContinuoAdapter,
    HealthStatus,
    L5Manifest,
    SPEC_VERSION,
)
from adapters import codex as codex_module
from adapters.codex import (
    CodexAdapter,
    _find_rollout_file,
    _parse_session_index,
    _read_session_meta,
    _timestamp_to_iso_date,
)


# -- Fixture -------------------------------------------------------------------


@pytest.fixture
def isolated_home(tmp_path, monkeypatch):
    """Redirect Path.home() at a tmp dir so adapter resolvers don't see the
    host machine's real ~/.codex/."""
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    def create_codex_home():
        (fake_home / ".codex").mkdir()
        (fake_home / ".codex" / "sessions").mkdir()
        return fake_home / ".codex"

    def add_index_entry(codex_home, session_id: str, thread_name: str, updated_at: str):
        idx = codex_home / "session_index.jsonl"
        with open(idx, "a", encoding="utf-8") as f:
            f.write(
                json.dumps(
                    {
                        "id": session_id,
                        "thread_name": thread_name,
                        "updated_at": updated_at,
                    }
                )
                + "\n"
            )

    def add_rollout(codex_home, date_parts: tuple[int, int, int], session_id: str, cwd: str, timestamp: str):
        y, m, d = date_parts
        date_dir = codex_home / "sessions" / f"{y:04d}" / f"{m:02d}" / f"{d:02d}"
        date_dir.mkdir(parents=True, exist_ok=True)
        rollout = date_dir / f"rollout-{timestamp.replace(':', '-').replace('.', '-')}-{session_id}.jsonl"
        payload = {"id": session_id, "timestamp": timestamp, "cwd": cwd}
        with open(rollout, "w", encoding="utf-8") as f:
            f.write(
                json.dumps({"timestamp": timestamp, "type": "session_meta", "payload": payload})
                + "\n"
            )
            f.write(json.dumps({"timestamp": timestamp, "type": "user_input", "payload": {"text": "hi"}}) + "\n")
        return rollout

    def create_codex_brain():
        cb = fake_home / "codex-brain"
        cb.mkdir()
        (cb / "CURRENT.md.txt").write_text("# Current focus\n", encoding="utf-8")
        return cb

    return {
        "home": fake_home,
        "create_codex_home": create_codex_home,
        "add_index_entry": add_index_entry,
        "add_rollout": add_rollout,
        "create_codex_brain": create_codex_brain,
    }


# -- Protocol + constants ------------------------------------------------------


def test_adapter_satisfies_protocol(isolated_home):
    assert isinstance(CodexAdapter(), ContinuoAdapter)


def test_adapter_constants():
    assert codex_module.AGENT_ID == "codex"
    assert codex_module.AGENT_TYPE == "code-assistant"


# -- discover + health_check ---------------------------------------------------


def test_discover_raises_when_no_codex_home(isolated_home):
    adapter = CodexAdapter()
    with pytest.raises(AdapterDiscoveryError):
        adapter.discover()


def test_discover_ok_with_index_and_sessions(isolated_home):
    codex_home = isolated_home["create_codex_home"]()
    isolated_home["add_index_entry"](
        codex_home, "id1", "Thread 1", "2026-04-15T12:00:00Z"
    )
    adapter = CodexAdapter()
    store = adapter.discover()
    assert store.metadata["sources"]["codex_home"] is not None
    assert store.metadata["sources"]["session_index"] is not None
    assert store.metadata["sources"]["sessions_dir"] is not None


def test_health_ok_with_all_present(isolated_home):
    codex_home = isolated_home["create_codex_home"]()
    isolated_home["add_index_entry"](
        codex_home, "id1", "Thread", "2026-04-15T12:00:00Z"
    )
    assert CodexAdapter().health_check().status == "ok"


def test_health_degraded_missing_session_index(isolated_home):
    isolated_home["create_codex_home"]()
    # No session_index.jsonl written
    health = CodexAdapter().health_check()
    assert health.status == "degraded"
    assert "session_index" in health.reason


def test_health_blocked_missing_codex_home(isolated_home):
    health = CodexAdapter().health_check()
    assert health.status == "blocked"


def test_health_check_never_raises(isolated_home):
    assert isinstance(CodexAdapter().health_check(), HealthStatus)


# -- Parsing helpers -----------------------------------------------------------


def test_parse_session_index_newest_first(tmp_path):
    idx = tmp_path / "session_index.jsonl"
    with open(idx, "w", encoding="utf-8") as f:
        f.write(
            json.dumps({"id": "a", "thread_name": "Old", "updated_at": "2026-04-10T00:00:00Z"})
            + "\n"
        )
        f.write(
            json.dumps({"id": "b", "thread_name": "New", "updated_at": "2026-04-15T00:00:00Z"})
            + "\n"
        )
    entries = _parse_session_index(idx)
    assert [e["id"] for e in entries] == ["b", "a"]


def test_parse_session_index_skips_malformed_lines(tmp_path, caplog):
    idx = tmp_path / "session_index.jsonl"
    with open(idx, "w", encoding="utf-8") as f:
        f.write(json.dumps({"id": "a", "thread_name": "Good", "updated_at": "2026-04-15T00:00:00Z"}) + "\n")
        f.write("not json at all\n")
        f.write(json.dumps({"id": "b", "thread_name": "Also good", "updated_at": "2026-04-14T00:00:00Z"}) + "\n")
    with caplog.at_level("WARNING"):
        entries = _parse_session_index(idx)
    assert {e["id"] for e in entries} == {"a", "b"}


def test_parse_session_index_empty_on_missing_file(tmp_path):
    assert _parse_session_index(tmp_path / "nothing.jsonl") == []


def test_find_rollout_file_matches_by_id(isolated_home):
    codex_home = isolated_home["create_codex_home"]()
    isolated_home["add_rollout"](codex_home, (2026, 4, 15), "abc123", "/tmp", "2026-04-15T12:00:00Z")
    found = _find_rollout_file(codex_home, "abc123")
    assert found is not None
    assert "abc123" in found.name


def test_find_rollout_file_returns_none_when_missing(isolated_home):
    codex_home = isolated_home["create_codex_home"]()
    assert _find_rollout_file(codex_home, "nope") is None


def test_read_session_meta_returns_payload(isolated_home):
    codex_home = isolated_home["create_codex_home"]()
    rollout = isolated_home["add_rollout"](
        codex_home, (2026, 4, 15), "abc", "/home/user", "2026-04-15T12:00:00Z"
    )
    meta = _read_session_meta(rollout)
    assert meta is not None
    assert meta["cwd"] == "/home/user"


def test_read_session_meta_returns_none_for_non_meta_first_line(tmp_path):
    rollout = tmp_path / "weird.jsonl"
    rollout.write_text(
        json.dumps({"type": "user_input", "payload": {"text": "hi"}}) + "\n",
        encoding="utf-8",
    )
    assert _read_session_meta(rollout) is None


def test_timestamp_parsing_accepts_z_suffix():
    assert _timestamp_to_iso_date("2026-04-15T12:00:00Z") == "2026-04-15"


def test_timestamp_parsing_accepts_microseconds_and_tz():
    assert _timestamp_to_iso_date("2026-04-15T12:00:00.123456+00:00") == "2026-04-15"


def test_timestamp_parsing_falls_back_to_prefix_for_unusual_format():
    # Not valid ISO, but starts with a date-shaped prefix
    assert _timestamp_to_iso_date("2026-04-15 weird stuff") == "2026-04-15"


def test_timestamp_parsing_returns_none_for_garbage():
    assert _timestamp_to_iso_date("totally broken") is None
    assert _timestamp_to_iso_date("") is None


# -- export_sessions -----------------------------------------------------------


def test_export_sessions_resolves_cwd_from_rollout(isolated_home):
    codex_home = isolated_home["create_codex_home"]()
    isolated_home["add_index_entry"](
        codex_home, "sess1", "Work thread", "2026-04-15T12:00:00Z"
    )
    isolated_home["add_rollout"](
        codex_home, (2026, 4, 15), "sess1", "/workspace/project", "2026-04-15T12:00:00Z"
    )
    sessions = CodexAdapter().export_sessions(since=datetime(2026, 4, 1, tzinfo=timezone.utc))
    assert len(sessions) == 1
    assert sessions[0].date == "2026-04-15"
    assert sessions[0].cwd == "/workspace/project"
    assert "Work thread" in sessions[0].key_actions[0]


def test_export_sessions_since_filter(isolated_home):
    codex_home = isolated_home["create_codex_home"]()
    isolated_home["add_index_entry"](codex_home, "new", "New", "2026-04-15T00:00:00Z")
    isolated_home["add_index_entry"](codex_home, "old", "Old", "2026-04-01T00:00:00Z")
    cutoff = datetime(2026, 4, 10, tzinfo=timezone.utc)
    sessions = CodexAdapter().export_sessions(since=cutoff)
    assert [s.date for s in sessions] == ["2026-04-15"]


def test_export_sessions_with_missing_rollout_still_emits_session(isolated_home):
    """If the rollout file isn't locatable, cwd falls back to None but session
    still appears. Codex session index is authoritative."""
    codex_home = isolated_home["create_codex_home"]()
    isolated_home["add_index_entry"](codex_home, "orphan", "No rollout", "2026-04-15T00:00:00Z")
    # No add_rollout call
    sessions = CodexAdapter().export_sessions(since=datetime(2026, 4, 1, tzinfo=timezone.utc))
    assert len(sessions) == 1
    assert sessions[0].cwd is None


def test_export_sessions_empty_when_no_codex_home(isolated_home):
    """Missing ~/.codex/ should not crash -- just return empty."""
    # Don't call create_codex_home
    with pytest.raises(AdapterDiscoveryError):
        CodexAdapter().discover()
    # But export_sessions directly bypasses discover
    sessions = CodexAdapter().export_sessions(since=datetime(2026, 4, 1, tzinfo=timezone.utc))
    assert sessions == []


# -- export_l5 -----------------------------------------------------------------


def test_export_l5_produces_valid_manifest(isolated_home):
    codex_home = isolated_home["create_codex_home"]()
    isolated_home["add_index_entry"](
        codex_home, "s1", "Set up CI", "2026-04-15T00:00:00Z"
    )
    isolated_home["add_index_entry"](
        codex_home, "s2", "Debug auth", "2026-04-14T00:00:00Z"
    )
    manifest = CodexAdapter().export_l5()
    assert isinstance(manifest, L5Manifest)
    assert manifest.agent.id == "codex"
    assert manifest.spec_version == SPEC_VERSION
    assert len(manifest.recent_sessions) == 2
    # Two unique thread_names -> two entities
    names = {e.name for e in manifest.known_entities}
    assert names == {"Set up CI", "Debug auth"}


def test_export_l5_dedupes_thread_names_case_insensitive(isolated_home):
    codex_home = isolated_home["create_codex_home"]()
    isolated_home["add_index_entry"](codex_home, "a", "Set up CI", "2026-04-15T00:00:00Z")
    isolated_home["add_index_entry"](codex_home, "b", "set up ci", "2026-04-14T00:00:00Z")
    manifest = CodexAdapter().export_l5()
    assert len(manifest.known_entities) == 1
    # Keeps the most-recent last_touched
    assert manifest.known_entities[0].last_touched == "2026-04-15"


def test_export_l5_schema_round_trip(isolated_home):
    import jsonschema

    codex_home = isolated_home["create_codex_home"]()
    isolated_home["add_index_entry"](
        codex_home, "s1", "A thread", "2026-04-15T00:00:00Z"
    )
    manifest = CodexAdapter().export_l5()
    schema_path = Path(__file__).parent.parent / "spec" / "L5_schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    jsonschema.validate(instance=manifest.to_dict(), schema=schema)


def test_export_l5_raises_when_nothing_discovered(isolated_home):
    with pytest.raises(AdapterDiscoveryError):
        CodexAdapter().export_l5()


# -- Integration: round-trip through write_l5 + L6Store -----------------------


def test_codex_l5_can_round_trip_through_l6_store(isolated_home, tmp_path):
    """Adapter output writes cleanly to disk and the L6 store picks it up."""
    from core.l5_io import write_l5
    from core.l6_store import L6Store

    codex_home = isolated_home["create_codex_home"]()
    isolated_home["add_index_entry"](
        codex_home, "s1", "Federation test", "2026-04-15T00:00:00Z"
    )
    manifest = CodexAdapter().export_l5()

    library = tmp_path / "agent-library"
    target = library / "agents" / f"{manifest.agent.id}.l5.yaml"
    write_l5(manifest, target)

    store = L6Store(library)
    assert "codex" in store.list_agents()
    matches = store.find_entity("Federation test")
    assert len(matches) == 1
    assert "codex" in matches[0].agents
