"""Tests for the Bourdon MCP smoke-test helper script."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_mcp_smoke_test_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "mcp_smoke_test.py"
    spec = importlib.util.spec_from_file_location("mcp_smoke_test", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_mcp_smoke_test_accepts_configurable_query_agent(monkeypatch):
    module = _load_mcp_smoke_test_module()
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "mcp_smoke_test.py",
            "--query-agent",
            "codex",
            "--query-topic",
            "Bourdon",
        ],
    )

    args = module._parse_args()

    assert args.query_agent == "codex"
    assert args.query_topic == "Bourdon"
