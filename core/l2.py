"""
Bourdon L2 -- Episodic Memory async retrieval.

L2 is the third layer of the memory stack. It fires concurrent with the AI's
first response tokens and is expected to complete during the human's reading +
typing window (~3-8 seconds). By the time the human finishes composing their
reply, L2 context is ready for the AI's follow-up turn -- no retrieval pause.

This module provides:

- ``L2Config``: dataclass with YAML loader + env-var overrides
- ``L2Client``: Protocol for retriever clients (makes the module testable
  without a real UltraRAG instance)
- ``FastMCPL2Client``: production client backed by ``fastmcp.Client``
  (requires ``pip install 'bourdon[ultrarag]'``)
- ``query_l2()``: the single entry point; swallows all errors and returns
  empty string on failure so L2 can never crash a session

Design invariants:

- L2 NEVER blocks the first response. Any failure returns empty context.
- L2 NEVER raises out of query_l2(). Callers do not need try/except.
- L2 is OPT-IN. Default config has enabled=false so a fresh install needs
  no UltraRAG setup.
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Protocol, runtime_checkable

import yaml

logger = logging.getLogger(__name__)


DEFAULT_CONFIG_PATH = Path(__file__).parent / "l2_config.yaml"


# -- Config --------------------------------------------------------------------


_TRUE_VALUES = frozenset({"true", "1", "yes", "on", "t", "y"})
_FALSE_VALUES = frozenset({"false", "0", "no", "off", "f", "n"})


def _parse_bool(raw: Any) -> Optional[bool]:
    """Parse a bool-ish value. Returns None if unparseable."""
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, (int, float)):
        return bool(raw)
    if isinstance(raw, str):
        lower = raw.strip().lower()
        if lower in _TRUE_VALUES:
            return True
        if lower in _FALSE_VALUES:
            return False
    return None


@dataclass
class L2Config:
    """
    Configuration for the L2 episodic memory layer.

    Load order (later overrides earlier):
        1. Dataclass defaults (this class)
        2. YAML file (if provided via from_yaml())
        3. Environment variables (BOURDON_L2_*)
    """

    enabled: bool = False
    endpoint: str = "http://localhost:8765"
    tool_name: str = "retriever_search"
    top_k: int = 5
    timeout_seconds: float = 8.0

    @classmethod
    def from_yaml(cls, path: Optional[Path] = None) -> "L2Config":
        """Load config from YAML file (falls back to defaults if missing)."""
        cfg = cls()
        target = path or DEFAULT_CONFIG_PATH
        if target.is_file():
            try:
                with open(target, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                if isinstance(data, dict):
                    cfg = cls._merge_dict(cfg, data)
            except (yaml.YAMLError, OSError) as e:
                logger.warning("Failed to load L2 config from %s: %s", target, e)
        cfg = cls._apply_env_overrides(cfg)
        return cfg

    @staticmethod
    def _merge_dict(base: "L2Config", data: dict) -> "L2Config":
        """Merge dict values into a config, ignoring unknown keys."""
        enabled = data.get("enabled", base.enabled)
        parsed_enabled = _parse_bool(enabled)
        return L2Config(
            enabled=parsed_enabled if parsed_enabled is not None else base.enabled,
            endpoint=str(data.get("endpoint", base.endpoint)),
            tool_name=str(data.get("tool_name", base.tool_name)),
            top_k=int(data.get("top_k", base.top_k)),
            timeout_seconds=float(data.get("timeout_seconds", base.timeout_seconds)),
        )

    @staticmethod
    def _apply_env_overrides(cfg: "L2Config") -> "L2Config":
        """Apply any BOURDON_L2_* env vars on top of the given config."""
        updates: dict = {}
        if "BOURDON_L2_ENABLED" in os.environ:
            parsed = _parse_bool(os.environ["BOURDON_L2_ENABLED"])
            if parsed is not None:
                updates["enabled"] = parsed
        if "BOURDON_L2_ENDPOINT" in os.environ:
            updates["endpoint"] = os.environ["BOURDON_L2_ENDPOINT"]
        if "BOURDON_L2_TOOL" in os.environ:
            updates["tool_name"] = os.environ["BOURDON_L2_TOOL"]
        if "BOURDON_L2_TOP_K" in os.environ:
            try:
                updates["top_k"] = int(os.environ["BOURDON_L2_TOP_K"])
            except ValueError:
                logger.warning(
                    "Invalid BOURDON_L2_TOP_K=%s, ignoring", os.environ["BOURDON_L2_TOP_K"]
                )
        if "BOURDON_L2_TIMEOUT" in os.environ:
            try:
                updates["timeout_seconds"] = float(os.environ["BOURDON_L2_TIMEOUT"])
            except ValueError:
                logger.warning(
                    "Invalid BOURDON_L2_TIMEOUT=%s, ignoring",
                    os.environ["BOURDON_L2_TIMEOUT"],
                )
        if not updates:
            return cfg
        return L2Config(
            enabled=updates.get("enabled", cfg.enabled),
            endpoint=updates.get("endpoint", cfg.endpoint),
            tool_name=updates.get("tool_name", cfg.tool_name),
            top_k=updates.get("top_k", cfg.top_k),
            timeout_seconds=updates.get("timeout_seconds", cfg.timeout_seconds),
        )


# -- Client protocol + formatting ---------------------------------------------


@runtime_checkable
class L2Client(Protocol):
    """
    Protocol for an L2 retrieval client.

    Implementations must provide an async ``query`` method. Tests supply a
    mock client; production uses :class:`FastMCPL2Client`.
    """

    async def query(self, query: str, top_k: int) -> str:
        """Return formatted L2 context for the query, or raise on failure."""
        ...


def _format_l2_context(raw: Any) -> str:
    """
    Normalize a raw retriever response into a human-readable context block.

    Accepts several shapes:
      - A plain string (returned as-is, trimmed)
      - A list of dicts with ``content`` / ``text`` / ``summary`` fields
      - An MCP tool-call result with a ``content`` attribute (fastmcp style)
      - Anything else -> str(value)
    """
    if raw is None:
        return ""
    if isinstance(raw, str):
        return raw.strip()

    # fastmcp's CallToolResult exposes a list[TextContent] at .content
    content = getattr(raw, "content", None)
    if content is not None:
        raw = content

    if isinstance(raw, list):
        parts: list[str] = []
        for item in raw:
            if isinstance(item, str):
                parts.append(item.strip())
                continue
            # TextContent-like: .text attribute
            text_attr = getattr(item, "text", None)
            if text_attr:
                parts.append(str(text_attr).strip())
                continue
            if isinstance(item, dict):
                for key in ("content", "text", "summary", "body"):
                    value = item.get(key)
                    if value:
                        parts.append(str(value).strip())
                        break
                else:
                    parts.append(str(item))
            else:
                parts.append(str(item))
        return "\n\n---\n\n".join(p for p in parts if p)

    return str(raw).strip()


# -- Production client (lazy fastmcp import) ----------------------------------


class FastMCPL2Client:
    """
    Production L2 client backed by ``fastmcp.Client``.

    Creates a fresh MCP connection per query (stateless). This is simpler and
    safer than a long-lived connection for agents that are mostly idle, and
    the latency overhead is negligible for a layer that already has a
    multi-second budget.

    Requires ``fastmcp`` to be installed. The import is deferred so that
    importing :mod:`core.l2` does not require fastmcp -- only instantiating
    this client does.
    """

    def __init__(self, endpoint: str, tool_name: str) -> None:
        try:
            from fastmcp import Client  # type: ignore[import-not-found]
        except ImportError as exc:
            raise ImportError(
                "fastmcp is required for L2 UltraRAG integration. "
                "Install with: pip install 'bourdon[ultrarag]'"
            ) from exc
        self._Client = Client
        self.endpoint = endpoint
        self.tool_name = tool_name

    async def query(self, query: str, top_k: int) -> str:
        """Call the remote MCP tool with (query, top_k). Returns formatted text."""
        async with self._Client(self.endpoint) as client:
            result = await client.call_tool(
                self.tool_name,
                {"query": query, "top_k": top_k},
            )
        return _format_l2_context(result)


# -- Entry point ---------------------------------------------------------------


async def query_l2(
    query: str,
    config: Optional[L2Config] = None,
    client: Optional[L2Client] = None,
) -> str:
    """
    Fire an L2 retrieval. Never raises. Returns empty string on any failure.

    Parameters
    ----------
    query : str
        The user message (or derived query) to retrieve context for.
    config : L2Config, optional
        Config to use. Defaults to ``L2Config.from_yaml()`` (reads the
        bundled config file + env overrides).
    client : L2Client, optional
        Override the default client (used in tests). Defaults to a fresh
        :class:`FastMCPL2Client` constructed from the config.

    Behavior
    --------
    - If ``config.enabled`` is false, returns "" immediately without
      attempting any connection.
    - If instantiating the default client raises (typically because
      fastmcp is not installed), logs a warning and returns "".
    - If the client call exceeds ``config.timeout_seconds``, returns "".
    - Any other exception from the client is logged at WARNING level and
      the function returns "".
    """
    cfg = config if config is not None else L2Config.from_yaml()
    if not cfg.enabled:
        return ""

    if client is None:
        try:
            client = FastMCPL2Client(cfg.endpoint, cfg.tool_name)
        except ImportError as e:
            logger.warning("L2 client unavailable: %s", e)
            return ""
        except Exception as e:
            logger.warning("L2 client init failed: %s", e)
            return ""

    try:
        return await asyncio.wait_for(
            client.query(query, cfg.top_k),
            timeout=cfg.timeout_seconds,
        )
    except asyncio.TimeoutError:
        logger.warning("L2 query timed out after %ss", cfg.timeout_seconds)
        return ""
    except Exception as e:  # noqa: BLE001 -- L2 must never crash the session
        logger.warning("L2 query failed: %s", e)
        return ""
