"""Tests for adapters.claude_code -- the Claude Code external adapter."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from adapters.base import (
    AdapterDiscoveryError,
    ContinuoAdapter,
    HealthStatus,
    L5Manifest,
    SPEC_VERSION,
)
from adapters import claude_code as cc_module


@pytest.fixture
def isolated_home(tmp_path, monkeypatch):
    """
    Redirect the adapter's source-resolution helpers at a tmp directory tree.
    Returns (fake_home, helpers) where helpers lets tests create fake sources.
    """
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("CLAUDE_BRAIN", "")  # clear env override
    monkeypatch.delenv("CLAUDE_BRAIN", raising=False)
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    def create_brain():
        brain = fake_home / "claude-brain"
        brain.mkdir()
        (brain / "CURRENT.md").write_text("# Current focus\n", encoding="utf-8")
        return brain

    def create_auto_memory():
        mem_base = fake_home / ".claude" / "projects" / "C--Users-test"
        mem_dir = mem_base / "memory"
        mem_dir.mkdir(parents=True)
        (mem_dir / "MEMORY.md").write_text("# Memory index\n", encoding="utf-8")
        return mem_dir

    def create_knowledge_graph():
        kg_dir = fake_home / "claude-memory"
        kg_dir.mkdir()
        kg_path = kg_dir / "memory.jsonl"
        kg_path.write_text(
            json.dumps(
                {"type": "entity", "name": "TestEntity", "observations": []}
            )
            + "\n",
            encoding="utf-8",
        )
        return kg_path

    return {
        "home": fake_home,
        "create_brain": create_brain,
        "create_auto_memory": create_auto_memory,
        "create_knowledge_graph": create_knowledge_graph,
    }


# -- Adapter shape -------------------------------------------------------------


def test_adapter_satisfies_protocol(isolated_home):
    adapter = cc_module.ClaudeCodeAdapter()
    assert isinstance(adapter, ContinuoAdapter)


def test_adapter_exposes_expected_constants():
    assert cc_module.AGENT_ID == "claude-code"
    assert cc_module.AGENT_TYPE == "code-assistant"
    # Policy guards the usual PII categories
    assert "credential" in cc_module.DEFAULT_POLICY.private_tags
    assert "financial" in cc_module.DEFAULT_POLICY.private_tags


# -- discover() ----------------------------------------------------------------


def test_discover_raises_when_no_sources(isolated_home):
    adapter = cc_module.ClaudeCodeAdapter()
    with pytest.raises(AdapterDiscoveryError):
        adapter.discover()


def test_discover_succeeds_with_just_claude_brain(isolated_home):
    isolated_home["create_brain"]()
    adapter = cc_module.ClaudeCodeAdapter()
    store = adapter.discover()
    assert store.metadata["sources"]["claude_brain"] is not None
    assert store.metadata["sources"]["auto_memory"] is None
    assert store.metadata["sources"]["knowledge_graph"] is None


def test_discover_succeeds_with_all_three_sources(isolated_home):
    isolated_home["create_brain"]()
    isolated_home["create_auto_memory"]()
    isolated_home["create_knowledge_graph"]()
    adapter = cc_module.ClaudeCodeAdapter()
    store = adapter.discover()
    sources = store.metadata["sources"]
    assert all(v is not None for v in sources.values())


def test_discover_env_override_takes_precedence(tmp_path, monkeypatch):
    """CLAUDE_BRAIN env var should win over the default ~/claude-brain."""
    override_dir = tmp_path / "explicit-brain"
    override_dir.mkdir()
    monkeypatch.setenv("CLAUDE_BRAIN", str(override_dir))
    # Also fake home so the default path would resolve somewhere else
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: fake_home)

    adapter = cc_module.ClaudeCodeAdapter()
    store = adapter.discover()
    assert store.metadata["sources"]["claude_brain"] == str(override_dir)


# -- health_check() ------------------------------------------------------------


def test_health_check_ok_with_all_sources(isolated_home):
    isolated_home["create_brain"]()
    isolated_home["create_auto_memory"]()
    isolated_home["create_knowledge_graph"]()
    adapter = cc_module.ClaudeCodeAdapter()
    health = adapter.health_check()
    assert health.status == "ok"


def test_health_check_degraded_with_partial_sources(isolated_home):
    isolated_home["create_brain"]()  # 1 of 3
    adapter = cc_module.ClaudeCodeAdapter()
    health = adapter.health_check()
    assert health.status == "degraded"
    assert "1/3" in health.reason


def test_health_check_blocked_with_no_sources(isolated_home):
    adapter = cc_module.ClaudeCodeAdapter()
    health = adapter.health_check()
    assert health.status == "blocked"


def test_health_check_never_raises(isolated_home):
    """Contract: health_check must not raise even if the world is on fire."""
    adapter = cc_module.ClaudeCodeAdapter()
    # No sources set up -- should still return a structured response, not raise
    result = adapter.health_check()
    assert isinstance(result, HealthStatus)


# -- export_l5() ---------------------------------------------------------------


def test_export_l5_returns_valid_manifest(isolated_home):
    isolated_home["create_brain"]()
    adapter = cc_module.ClaudeCodeAdapter()
    manifest = adapter.export_l5()
    assert isinstance(manifest, L5Manifest)
    assert manifest.spec_version == SPEC_VERSION
    assert manifest.agent.id == "claude-code"
    assert manifest.agent.type == "code-assistant"
    # v0.0.2 stub behavior: sessions + entities empty, capabilities populated
    assert manifest.recent_sessions == []
    assert manifest.known_entities == []
    assert "claude_brain" in manifest.capabilities


def test_export_l5_raises_when_nothing_discovered(isolated_home):
    adapter = cc_module.ClaudeCodeAdapter()
    with pytest.raises(AdapterDiscoveryError):
        adapter.export_l5()


def test_export_sessions_returns_empty_in_stub(isolated_home):
    """v0.0.2 stub behavior -- real parsing lands in v0.1.0."""
    isolated_home["create_brain"]()
    from datetime import datetime, timezone

    adapter = cc_module.ClaudeCodeAdapter()
    sessions = adapter.export_sessions(since=datetime.now(timezone.utc))
    assert sessions == []
