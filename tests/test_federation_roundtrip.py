"""
Bourdon federation round-trip integration tests.

Scope
-----
These tests assert the contract that ties Bourdon together:

    each adapter's export_l5() output is queryable through L6Store with
    correct attribution, visibility filtering, and cross-agent aggregation.

Per-adapter unit suites verify only the adapter -> L5 leg. The L6Store
unit suite verifies only the store -> query leg with synthetic manifests.
Nothing else covers the seam where they meet. If an adapter silently
changes the shape of its L5 in a way the store does not expect, the unit
tests stay green and the federation product silently breaks.

This is Layer 1 of the cross-agent test plan recorded in
PROJECTS/NEUROLAYER/NOTES.md (2026-05-11 entry on claude-brain).
Layers 2 and 3 (`bourdon dogfood` CLI + public acceptance scenario)
live outside the test suite.

Coverage as of v0.4.1
---------------------
Wired end-to-end:
    copilot   (convention-file adapter, plants memory.md)
    cascade   (convention-file adapter, plants memory.md)
    cursor    (SQLite adapter, seeds state.vscdb directly)

Stubbed (TODO -- fixture plumbing only, the assertions below already cover them):
    claude-code  (needs Path.home() monkeypatch over a 3-source tree)
    codex        (needs Path.home() monkeypatch over sessions+memories+brain)
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Callable

import pytest

from adapters.base import L5Manifest
from adapters.cascade import CascadeAdapter
from adapters.copilot import CopilotAdapter
from adapters.cursor import CursorAdapter
from core.l5_io import write_l5_dict
from core.l6_store import L6Store

# ---------------------------------------------------------------------------
# Marker facts -- a distinct, easily-grepped entity per adapter.
#
# The round-trip test plants each adapter with a marker entity whose name is
# unique to that adapter (so we can prove the L5 reached L6 and is attributed
# to the right agent), plus a shared entity ("Bourdon") that every adapter
# knows about (so we can prove cross-agent aggregation works).
# ---------------------------------------------------------------------------

SHARED_ENTITY = "Bourdon"
SHARED_SUMMARY_PREFIX = "Cross-agent memory federation, as seen by"

UNIQUE_MARKERS: dict[str, str] = {
    "copilot": "CopilotOnlyFact",
    "cascade": "CascadeOnlyFact",
    "cursor": "CursorOnlyFact",
}


# ---------------------------------------------------------------------------
# Per-adapter fixture planters.
#
# Each helper accepts `tmp_path` and returns a configured adapter whose
# `export_l5()` will produce a manifest containing:
#   - one entity named UNIQUE_MARKERS[agent_id] (attribution proof)
#   - one entity named SHARED_ENTITY            (federation proof)
# Plus whatever incidental rows the adapter naturally produces from the
# fixture (sessions, project entities, etc.) -- those are not asserted on,
# only the marker shape is contract.
# ---------------------------------------------------------------------------


def _plant_copilot(tmp_path: Path) -> CopilotAdapter:
    d = tmp_path / ".copilot-bourdon"
    d.mkdir()
    (d / "memory.md").write_text(
        "---\n"
        "entities:\n"
        f"  - name: {UNIQUE_MARKERS['copilot']}\n"
        "    type: project\n"
        "    summary: A fact only Copilot knows.\n"
        "    tags: [marker, federation-test]\n"
        f"  - name: {SHARED_ENTITY}\n"
        # Match Cursor's inferred entity type so build_recognition_manifest()
        # (which dedupes on (name, type)) collapses all three adapters into
        # one row. See "Cross-type entity-dedupe question" in
        # PROJECTS/NEUROLAYER/NOTES.md for why this is contract-relevant.
        "    type: project\n"
        f"    summary: {SHARED_SUMMARY_PREFIX} Copilot\n"
        "    tags: [shared, federation-test]\n"
        "sessions: []\n"
        "---\n"
        "Freeform body intentionally left short.\n",
        encoding="utf-8",
    )
    return CopilotAdapter(copilot_dir=d)


def _plant_cascade(tmp_path: Path) -> CascadeAdapter:
    d = tmp_path / ".cascade-bourdon"
    d.mkdir()
    (d / "memory.md").write_text(
        "---\n"
        "entities:\n"
        f"  - name: {UNIQUE_MARKERS['cascade']}\n"
        "    type: project\n"
        "    summary: A fact only Cascade knows.\n"
        "    tags: [marker, federation-test]\n"
        f"  - name: {SHARED_ENTITY}\n"
        # Match Cursor's inferred entity type so build_recognition_manifest()
        # (which dedupes on (name, type)) collapses all three adapters into
        # one row. See "Cross-type entity-dedupe question" in
        # PROJECTS/NEUROLAYER/NOTES.md for why this is contract-relevant.
        "    type: project\n"
        f"    summary: {SHARED_SUMMARY_PREFIX} Cascade\n"
        "    tags: [shared, federation-test]\n"
        "sessions: []\n"
        "---\n"
        "Freeform body intentionally left short.\n",
        encoding="utf-8",
    )
    return CascadeAdapter(cascade_dir=d)


def _plant_cursor(tmp_path: Path) -> CursorAdapter:
    cursor_dir = tmp_path / "Cursor"
    (cursor_dir / "User" / "globalStorage").mkdir(parents=True)
    workspace = cursor_dir / "User" / "workspaceStorage" / "fedtest"
    workspace.mkdir(parents=True)
    db = workspace / "state.vscdb"

    # Cursor's adapter infers project entities from composer workspacePaths.
    # We use the marker names as the project names so they appear in
    # manifest.known_entities verbatim.
    records = [
        (
            "composer.composerData",
            {
                "workspacePath": f"/projects/{UNIQUE_MARKERS['cursor']}",
                "title": "Marker session for federation round-trip",
                "messages": [],
                "lastUpdatedAt": "2026-05-11T12:00:00Z",
            },
        ),
        (
            "composer.composerData.bourdon",
            {
                "workspacePath": f"/projects/{SHARED_ENTITY}",
                "title": "Shared-entity session for federation round-trip",
                "messages": [],
                "lastUpdatedAt": "2026-05-11T12:00:01Z",
            },
        ),
    ]
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db))
    try:
        conn.execute("CREATE TABLE ItemTable (key TEXT PRIMARY KEY, value TEXT)")
        for key, value in records:
            conn.execute(
                "INSERT INTO ItemTable (key, value) VALUES (?, ?)",
                (key, json.dumps(value)),
            )
        conn.commit()
    finally:
        conn.close()
    return CursorAdapter(cursor_dir=cursor_dir)


# Stubbed planters. Implementing these is purely fixture plumbing -- both
# adapters need Path.home() monkey-patching and a small tree of native
# files. See tests/test_claude_code_adapter.py::isolated_home and
# tests/test_codex_adapter.py for the patterns to lift.
def _plant_claude_code(tmp_path: Path) -> object:
    pytest.skip(
        "TODO: wire claude-code planter. Pattern: monkeypatch Path.home(), "
        "create claude-brain/{CURRENT.md, PROJECTS/<marker>/OVERVIEW.md, "
        "LOG/<dated>.md}. Lift from tests/test_claude_code_adapter.py::isolated_home."
    )


def _plant_codex(tmp_path: Path) -> object:
    pytest.skip(
        "TODO: wire codex planter. Pattern: monkeypatch Path.home(), create "
        ".codex/{session_index.jsonl, sessions/YYYY/MM/DD/rollout-*.jsonl, "
        "memories/rollout_summaries/}. Lift from tests/test_codex_adapter.py."
    )


PLANTERS: dict[str, Callable[[Path], object]] = {
    "copilot": _plant_copilot,
    "cascade": _plant_cascade,
    "cursor": _plant_cursor,
    "claude-code": _plant_claude_code,
    "codex": _plant_codex,
}


# ---------------------------------------------------------------------------
# Shared fixture: a populated library + L6Store.
#
# Plants every wired adapter, exports each to <tmp>/agent-library/agents/,
# loads the store. Stubbed adapters are silently skipped at planter level
# via pytest.skip -- their fixtures will reappear once the planter lands.
# ---------------------------------------------------------------------------


@pytest.fixture
def federation(tmp_path):
    """Return (L6Store, library_path, planted_agents) with all wired adapters loaded."""
    library = tmp_path / "agent-library"
    agents_dir = library / "agents"
    agents_dir.mkdir(parents=True)

    planted: list[str] = []
    for agent_id, planter in PLANTERS.items():
        agent_tmp = tmp_path / agent_id
        agent_tmp.mkdir()
        try:
            adapter = planter(agent_tmp)
        except pytest.skip.Exception:
            # Stubbed planter -- skip this adapter, don't fail the whole test.
            continue
        manifest: L5Manifest = adapter.export_l5()
        write_l5_dict(manifest.to_dict(), agents_dir / f"{agent_id}.l5.yaml")
        planted.append(agent_id)

    store = L6Store(library_path=library)
    store.reload_all()
    return store, library, planted


# ---------------------------------------------------------------------------
# Tests.
# ---------------------------------------------------------------------------


def test_all_planted_adapters_visible_in_store(federation):
    """Sanity: every adapter that exported an L5 shows up in list_agents()."""
    store, _library, planted = federation
    assert set(store.list_agents()) >= set(planted)
    # Federation test is only meaningful with >=2 agents.
    assert len(planted) >= 2, (
        f"Only {len(planted)} adapters wired -- need at least two to test "
        f"federation. Wire the stubbed planters in this file."
    )


@pytest.mark.parametrize("agent_id", list(UNIQUE_MARKERS.keys()))
def test_unique_marker_round_trips_with_correct_attribution(federation, agent_id):
    """
    The contract: a fact known only to agent A is retrievable via L6Store
    and attributed only to agent A.
    """
    store, _library, planted = federation
    if agent_id not in planted:
        pytest.skip(f"{agent_id} planter is stubbed -- see PLANTERS")

    marker = UNIQUE_MARKERS[agent_id]
    matches = store.find_entity(marker)

    assert matches, f"{agent_id} marker {marker!r} did not surface in L6"
    assert len(matches) == 1, (
        f"{marker!r} matched multiple entity rows; expected exactly one"
    )
    match = matches[0]
    assert match.agents == [agent_id], (
        f"{marker!r} should be attributed only to {agent_id}, "
        f"got {match.agents}"
    )


def test_shared_entity_aggregates_across_agents(federation):
    """
    The federation payoff: a fact known to multiple agents surfaces as
    ONE EntityMatch with multiple agents in match.agents and per-agent
    summaries in match.summaries.
    """
    store, _library, planted = federation
    matches = store.find_entity(SHARED_ENTITY)

    assert matches, f"shared entity {SHARED_ENTITY!r} did not surface in L6"
    assert len(matches) == 1, (
        f"shared entity {SHARED_ENTITY!r} did not deduplicate across agents; "
        f"got {len(matches)} matches: {[(m.name, m.agents) for m in matches]}"
    )
    match = matches[0]

    # All adapters that publish SHARED_ENTITY with a structured entity row
    # should appear. Cursor publishes it as a project entity via composer
    # workspacePath inference -- if that path ever changes, this assertion
    # will catch it.
    expected_publishers = {a for a in planted if a in {"copilot", "cascade", "cursor"}}
    assert set(match.agents) == expected_publishers, (
        f"shared-entity attribution drift: expected {expected_publishers}, "
        f"got {set(match.agents)}"
    )

    # Each convention-file adapter should contribute a distinct summary.
    for convention_agent in {"copilot", "cascade"} & expected_publishers:
        summary = match.summaries.get(convention_agent, "")
        assert SHARED_SUMMARY_PREFIX in summary, (
            f"{convention_agent} did not contribute its summary for "
            f"{SHARED_ENTITY!r}; got {summary!r}"
        )


def test_recognition_manifest_dedupes_shared_entity(federation):
    """
    build_recognition_manifest() is the surface recognition-runtime
    consumes. It must collapse multi-agent entities into a single row
    with merged source_agents -- otherwise an agent re-asking a known
    fact gets N copies instead of one canonical view.
    """
    store, _library, _planted = federation
    rec = store.build_recognition_manifest()

    shared_rows = [
        e
        for e in rec["known_entities"]
        if e.get("name", "").strip().lower() == SHARED_ENTITY.lower()
    ]
    assert len(shared_rows) == 1, (
        f"shared entity duplicated in recognition manifest: "
        f"{[r['name'] for r in shared_rows]}"
    )
    row = shared_rows[0]
    # >=2 source agents is the federation invariant we care about here.
    assert len(row.get("source_agents") or []) >= 2, (
        f"shared entity has only one source agent in recognition manifest: "
        f"{row.get('source_agents')}"
    )


def test_unknown_entity_returns_empty(federation):
    """Negative case: a fact no agent has published returns no matches."""
    store, _library, _planted = federation
    assert store.find_entity("NoAgentEverPublishedThis") == []
