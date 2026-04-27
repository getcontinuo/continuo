"""Tests for core.recognition_runtime."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from core.recognition_runtime import (
    DEFAULT_HYDRATION_TIMEOUT,
    RecognitionResult,
    build_recognition_string,
    detect_entities,
    hydrate_l1,
    recognition_first,
)


# ---- detect_entities --------------------------------------------------------


def test_detect_entities_case_insensitive_name():
    manifest = {
        "known_entities": [
            {"name": "OMNIvour", "type": "project"},
        ]
    }
    matches = detect_entities("tell me about omnivour", manifest)
    assert len(matches) == 1
    assert matches[0]["name"] == "OMNIvour"


def test_detect_entities_alias_match():
    manifest = {
        "known_entities": [
            {"name": "ILTT", "aliases": ["if_lift_then_that"], "type": "product"},
        ]
    }
    matches = detect_entities(
        "what is happening with if_lift_then_that today", manifest
    )
    assert len(matches) == 1
    assert matches[0]["name"] == "ILTT"


def test_detect_entities_multiple_matches():
    manifest = {
        "known_entities": [
            {"name": "Alpha"},
            {"name": "Beta"},
            {"name": "Gamma"},
        ]
    }
    matches = detect_entities("alpha and beta together", manifest)
    names = {m["name"] for m in matches}
    assert names == {"Alpha", "Beta"}


def test_detect_entities_no_match_returns_empty_list():
    manifest = {"known_entities": [{"name": "Alpha"}]}
    assert detect_entities("talking about the weather", manifest) == []


def test_detect_entities_handles_non_dict_manifest():
    """Defensive: if a caller passes a non-dict, return [] cleanly."""
    assert detect_entities("anything", "not a dict") == []  # type: ignore[arg-type]


def test_detect_entities_skips_entities_without_string_name():
    manifest = {
        "known_entities": [
            {"name": 12345},  # invalid
            {"name": "RealOne"},
        ]
    }
    matches = detect_entities("realone please", manifest)
    assert len(matches) == 1
    assert matches[0]["name"] == "RealOne"


# ---- build_recognition_string ----------------------------------------------


def test_recognition_string_empty_when_no_matches():
    assert build_recognition_string([]) == ""


def test_recognition_string_single_match_with_type():
    s = build_recognition_string([{"name": "OMNIvour", "type": "project"}])
    assert s == "Oh -- OMNIvour, the project."


def test_recognition_string_single_match_without_type():
    s = build_recognition_string([{"name": "OMNIvour"}])
    assert s == "Oh -- OMNIvour."


def test_recognition_string_archived_entity_with_valid_to():
    """valid_to date appears in the recognition suffix."""
    s = build_recognition_string(
        [{"name": "Cyndy", "type": "project", "valid_to": "2026-04-14"}]
    )
    assert "Cyndy" in s
    assert "2026-04-14" in s
    assert "archived" in s


def test_recognition_string_archived_entity_via_tag():
    """End-of-life tag without valid_to gets generic '(archived)' suffix."""
    s = build_recognition_string(
        [{"name": "Cyndy", "type": "project", "tags": ["archived"]}]
    )
    assert "(archived)" in s


def test_recognition_string_two_matches():
    s = build_recognition_string([{"name": "Alpha"}, {"name": "Beta"}])
    assert s == "You're asking about Alpha and Beta -- I have both."


def test_recognition_string_three_matches_uses_oxford_comma():
    s = build_recognition_string(
        [{"name": "Alpha"}, {"name": "Beta"}, {"name": "Gamma"}]
    )
    assert s == "You're asking about Alpha, Beta, and Gamma -- I have all of those."


# ---- hydrate_l1 -------------------------------------------------------------


@pytest.mark.asyncio
async def test_hydrate_l1_loads_matching_docs(tmp_path):
    l1_dir = tmp_path / "l1"
    l1_dir.mkdir()
    (l1_dir / "Alpha.md").write_text("# Alpha\nAlpha synopsis.", encoding="utf-8")
    (l1_dir / "Beta.md").write_text("# Beta\nBeta synopsis.", encoding="utf-8")
    matches = [{"name": "Alpha"}, {"name": "Beta"}]
    result = await hydrate_l1(matches, l1_dir=l1_dir)
    assert "Alpha synopsis" in result
    assert "Beta synopsis" in result
    assert "---" in result  # block separator


@pytest.mark.asyncio
async def test_hydrate_l1_empty_when_no_l1_dir():
    matches = [{"name": "Alpha"}]
    assert await hydrate_l1(matches, l1_dir=None) == ""


@pytest.mark.asyncio
async def test_hydrate_l1_empty_when_dir_missing(tmp_path):
    matches = [{"name": "Alpha"}]
    assert await hydrate_l1(matches, l1_dir=tmp_path / "nope") == ""


@pytest.mark.asyncio
async def test_hydrate_l1_case_insensitive_filename_match(tmp_path):
    l1_dir = tmp_path / "l1"
    l1_dir.mkdir()
    (l1_dir / "alpha.md").write_text("Alpha body", encoding="utf-8")
    matches = [{"name": "Alpha"}]  # uppercase request, lowercase file
    result = await hydrate_l1(matches, l1_dir=l1_dir)
    assert "Alpha body" in result


@pytest.mark.asyncio
async def test_hydrate_l1_skips_entity_without_name(tmp_path):
    l1_dir = tmp_path / "l1"
    l1_dir.mkdir()
    matches = [{"type": "project"}]  # no name field
    assert await hydrate_l1(matches, l1_dir=l1_dir) == ""


@pytest.mark.asyncio
async def test_hydrate_l1_returns_empty_when_no_matches():
    assert await hydrate_l1([], l1_dir=Path("/nonexistent")) == ""


# ---- recognition_first (full dispatch) --------------------------------------


def test_recognition_first_recognition_is_synchronous():
    """The recognition string must be available without awaiting anything."""
    manifest = {
        "known_entities": [{"name": "OMNIvour", "type": "project"}]
    }
    result = recognition_first("tell me about OMNIvour", manifest)
    # No event loop needed to read .recognition
    assert result.recognition == "Oh -- OMNIvour, the project."
    assert isinstance(result, RecognitionResult)
    # Close the unawaited hydration coroutine to silence the
    # "coroutine was never awaited" warning. In real use the caller
    # would either await it or close it after extracting recognition.
    if result.hydration is not None:
        result.hydration.close()


def test_recognition_first_no_matches_yields_no_hydration():
    """No-match path doesn't allocate a hydration coroutine."""
    manifest = {"known_entities": [{"name": "Alpha"}]}
    result = recognition_first("totally unrelated", manifest)
    assert result.recognition == ""
    assert result.matched_entities == []
    assert result.hydration is None


@pytest.mark.asyncio
async def test_recognition_first_hydrates_l1_docs_in_parallel(tmp_path):
    l1_dir = tmp_path / "l1"
    l1_dir.mkdir()
    (l1_dir / "OMNIvour.md").write_text("OMNIvour synopsis", encoding="utf-8")
    manifest = {
        "known_entities": [{"name": "OMNIvour", "type": "project"}]
    }
    result = recognition_first(
        "tell me about omnivour", manifest, l1_dir=l1_dir
    )
    assert result.recognition.startswith("Oh -- OMNIvour")
    assert result.hydration is not None
    detail = await result.hydration
    assert "OMNIvour synopsis" in detail


@pytest.mark.asyncio
async def test_recognition_first_hydration_timeout_yields_empty(tmp_path):
    """Slow hydration past the timeout returns "" instead of raising."""
    # Build a manifest that matches; we'll force a slow read by replacing
    # hydrate_l1 with one that sleeps longer than the timeout.
    manifest = {"known_entities": [{"name": "Alpha"}]}

    async def slow_hydrate(*args, **kwargs):
        await asyncio.sleep(2.0)
        return "should never be returned"

    import core.recognition_runtime as rr_module

    original = rr_module.hydrate_l1
    rr_module.hydrate_l1 = slow_hydrate  # type: ignore[assignment]
    try:
        result = recognition_first(
            "alpha please", manifest, hydration_timeout=0.05
        )
        assert result.recognition == "Oh -- Alpha."
        detail = await result.hydration
        assert detail == ""
    finally:
        rr_module.hydrate_l1 = original  # type: ignore[assignment]


def test_recognition_first_visibility_filter_excludes_private_entity():
    """Private-tagged entities are not surfaced even if their name appears in
    the user message at the default 'team' access level."""
    manifest = {
        "known_entities": [
            {"name": "PublicProject", "type": "project"},
            {"name": "SecretSauce", "type": "project", "visibility": "private"},
        ]
    }
    result = recognition_first(
        "tell me about SecretSauce and PublicProject",
        manifest,
        access_level="team",
    )
    matched_names = {e["name"] for e in result.matched_entities}
    # PublicProject must match; SecretSauce must NOT
    assert "PublicProject" in matched_names
    assert "SecretSauce" not in matched_names
    # Close unawaited coroutine for clean test output
    if result.hydration is not None:
        result.hydration.close()


def test_default_hydration_timeout_is_three_seconds():
    """Module-level constant should be 3.0s, the documented thesis budget."""
    assert DEFAULT_HYDRATION_TIMEOUT == 3.0
