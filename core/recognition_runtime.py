"""
Continuo recognition-first runtime.

Emits an immediate recognition response from the L0 / known-entities surface
and concurrently kicks off L1 hydration. The recognition string is computed
synchronously with no I/O and no model call -- it's a template populated from
matched-entity metadata, by deliberate design (see the project's POSITIONING.md
for the thesis grounding). This keeps L0 honest to its architectural role: the
recognition layer is *recognition*, not abbreviated retrieval.

Caller pattern (for an LLM-streaming context):

    result = recognition_first(user_msg, manifest, l1_dir=l1_dir)

    # 1. Emit the recognition immediately (no retrieval has happened yet)
    await stream.send(result.recognition)

    # 2. Start generating the model's main response in parallel with
    #    awaiting hydration:
    detail_future = asyncio.create_task(result.hydration) if result.hydration else None
    async for token in model.stream(user_msg, system_prompt=...):
        await stream.send(token)

    # 3. Inject hydrated detail when available (next turn or appended):
    if detail_future is not None:
        try:
            detail = await detail_future
        except asyncio.TimeoutError:
            detail = ""
        if detail:
            await stream.send_system_context(detail)

The recognition layer NEVER blocks on retrieval. Hydration NEVER blocks the
first response. Hydration NEVER raises -- timeouts and errors yield empty
string so the worst case degrades to "L0-only response" cleanly.

Future replacement for the template-based recognition string is straight-
forward: swap `build_recognition_string` for an LLM-based generator without
changing the public API. The Protocol-shaped boundary makes the swap safe.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Optional

from core.codex_context import filter_manifest_for_access

logger = logging.getLogger(__name__)

DEFAULT_HYDRATION_TIMEOUT = 3.0
"""Seconds. Past this budget, hydration is dropped for the current turn.
Tuned for the thesis: the AI's first response sentence should be ready
in ~0-200ms, so hydration has 2-3 seconds of LLM-generation overlap to
land before the next turn cares."""


# -- Result type ---------------------------------------------------------------


@dataclass
class RecognitionResult:
    """Output of a recognition-first dispatch."""

    recognition: str
    """The immediate, no-retrieval acknowledgment string. Ready to emit as the
    first sentence of the response. Empty string when nothing in the user
    message matched the manifest's known_entities."""

    matched_entities: list[dict[str, Any]] = field(default_factory=list)
    """The entity dicts that triggered recognition. Lets the caller decide
    whether to follow up with hydrated detail."""

    hydration: Optional[Awaitable[str]] = None
    """An awaitable that resolves to the L1-hydrated detail string. The caller
    awaits this in parallel with their own streaming work. None when there are
    no matches (no point hydrating nothing)."""


# -- Entity detection (mirrors core.orchestrator but reads a manifest) --------


def detect_entities(user_msg: str, manifest: dict) -> list[dict]:
    """
    Find entities from the manifest's known_entities mentioned in user_msg.

    Case-insensitive substring match on entity name + aliases. Same shape as
    core/orchestrator.py's detect_entities, but operates on a manifest dict
    instead of a flat keyword list (so it can read aliases and surface the
    full entity for downstream use).
    """
    if not isinstance(manifest, dict):
        return []
    msg_lower = user_msg.lower()
    matches: list[dict] = []
    for entity in manifest.get("known_entities") or []:
        if not isinstance(entity, dict):
            continue
        name = entity.get("name") or ""
        if not isinstance(name, str):
            continue
        aliases = entity.get("aliases") or []
        candidates: list[str] = [name]
        for alias in aliases:
            if isinstance(alias, str):
                candidates.append(alias)
        if any(c and c.lower() in msg_lower for c in candidates):
            matches.append(entity)
    return matches


# -- Recognition string templates (deliberately deterministic) -----------------


def build_recognition_string(matches: list[dict]) -> str:
    """
    Build the immediate recognition string from matched entities.

    Format rules:
      - 0 matches               -> ""
      - 1 match, with type      -> "Oh -- {name}, the {type}{suffix}."
      - 1 match, no type        -> "Oh -- {name}{suffix}."
      - 2 matches               -> "You're asking about {a} and {b} -- I have both."
      - 3+ matches              -> "You're asking about {a}, {b}, and {c} -- I have all of those."

    The {suffix} appends temporal context when the entity is end-of-life:
      - valid_to set            -> " (archived {valid_to})"
      - archived/canceled tag   -> " (archived)"
      - otherwise               -> ""

    The format is honest about scope: the recognition string acknowledges
    *that* the entity is known, not *what* is known about it. The hydration
    layer carries the actual content. This is the architectural separation
    POSITIONING.md stakes: recognition first, hydration second, archive
    descent third.
    """
    if not matches:
        return ""

    if len(matches) == 1:
        return _single_match_recognition(matches[0])

    names = [str(e.get("name") or "?") for e in matches]
    if len(names) == 2:
        joined = " and ".join(names)
        return f"You're asking about {joined} -- I have both."
    joined = ", ".join(names[:-1]) + f", and {names[-1]}"
    return f"You're asking about {joined} -- I have all of those."


def _single_match_recognition(entity: dict) -> str:
    name = str(entity.get("name") or "this")
    type_str = entity.get("type") or ""
    suffix = _temporal_suffix(entity)
    if type_str:
        return f"Oh -- {name}, the {type_str}{suffix}."
    return f"Oh -- {name}{suffix}."


_END_OF_LIFE_TAGS = frozenset({"archived", "canceled"})


def _temporal_suffix(entity: dict) -> str:
    """Generate the end-of-life suffix for the recognition string."""
    valid_to = entity.get("valid_to")
    if isinstance(valid_to, str) and valid_to:
        return f" (archived {valid_to})"
    tags = entity.get("tags") or []
    if isinstance(tags, list) and any(t in _END_OF_LIFE_TAGS for t in tags):
        return " (archived)"
    return ""


# -- Hydration -----------------------------------------------------------------


async def hydrate_l1(
    matches: list[dict],
    l1_dir: Optional[Path] = None,
) -> str:
    """
    Load L1 synopsis documents for matched entities, in parallel.

    Returns a formatted multi-section string. Empty when no l1_dir is set, the
    directory is missing, or no matching files are present. Never raises --
    the recognition runtime contract is that hydration failures degrade to
    L0-only behavior, never crash the response path.
    """
    if not matches or l1_dir is None:
        return ""
    if not l1_dir.is_dir():
        return ""

    loop = asyncio.get_event_loop()

    def _read_one(entity: dict) -> str:
        name = entity.get("name")
        if not isinstance(name, str) or not name:
            return ""
        # Try exact filename, then case-insensitive scan
        path = l1_dir / f"{name}.md"
        if not path.is_file():
            target = name.lower()
            for alt in l1_dir.glob("*.md"):
                if alt.stem.lower() == target:
                    path = alt
                    break
            else:
                return ""
        try:
            return path.read_text(encoding="utf-8")
        except OSError as exc:
            logger.debug("L1 hydration: failed to read %s: %s", path, exc)
            return ""

    try:
        docs = await asyncio.gather(
            *[loop.run_in_executor(None, _read_one, e) for e in matches]
        )
    except Exception as exc:  # noqa: BLE001 -- never crash hydration
        logger.warning("L1 hydration crashed: %s", exc)
        return ""

    blocks = [d.strip() for d in docs if d.strip()]
    if not blocks:
        return ""
    return "\n\n---\n\n".join(blocks)


# -- Public entry --------------------------------------------------------------


def recognition_first(
    user_msg: str,
    manifest: Any,
    *,
    l1_dir: Optional[Path] = None,
    access_level: str = "team",
    hydration_timeout: float = DEFAULT_HYDRATION_TIMEOUT,
) -> RecognitionResult:
    """
    Compose an immediate recognition response and an awaitable hydration call.

    The recognition string is computed synchronously (no I/O, no model call,
    no retrieval). The hydration coroutine, when present, runs in parallel
    with whatever the caller does next (model generation, response streaming,
    UI updates) up to ``hydration_timeout`` seconds.

    Visibility-filtered: entities marked private at the manifest's
    ``access_level`` are not considered for matching. So a recognition
    response can never accidentally surface a private entity name.

    Returns
    -------
    RecognitionResult
        With:
        - .recognition  -- ready-to-emit recognition string (may be "")
        - .matched_entities  -- the entities that triggered recognition
        - .hydration  -- awaitable that resolves to L1 detail (or None
          when there were no matches)
    """
    filtered = filter_manifest_for_access(manifest, access_level=access_level)
    matches = detect_entities(user_msg, filtered)
    recognition = build_recognition_string(matches)

    if not matches:
        return RecognitionResult(
            recognition=recognition,
            matched_entities=[],
            hydration=None,
        )

    async def _hydration_with_timeout() -> str:
        try:
            return await asyncio.wait_for(
                hydrate_l1(matches, l1_dir=l1_dir),
                timeout=hydration_timeout,
            )
        except asyncio.TimeoutError:
            logger.info(
                "L1 hydration timed out after %.1fs (matches=%d)",
                hydration_timeout,
                len(matches),
            )
            return ""

    return RecognitionResult(
        recognition=recognition,
        matched_entities=matches,
        hydration=_hydration_with_timeout(),
    )
