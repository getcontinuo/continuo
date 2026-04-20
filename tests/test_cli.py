"""Tests for the top-level `continuo` CLI."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from cli.main import main


def _build_fake_codex_home(fake_home: Path) -> None:
    codex_home = fake_home / ".codex"
    memories = codex_home / "memories"
    sessions_dir = codex_home / "sessions" / "2026" / "04" / "19"
    memories.mkdir(parents=True)
    (memories / "rollout_summaries").mkdir(parents=True, exist_ok=True)
    sessions_dir.mkdir(parents=True, exist_ok=True)

    (codex_home / "session_index.jsonl").write_text(
        json.dumps(
            {
                "id": "sess1",
                "thread_name": "Ship Coolculator context",
                "updated_at": "2026-04-19T12:00:00Z",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    rollout_path = sessions_dir / "rollout-2026-04-19T12-00-00Z-sess1.jsonl"
    rollout_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "timestamp": "2026-04-19T12:00:00Z",
                        "type": "session_meta",
                        "payload": {
                            "id": "sess1",
                            "timestamp": "2026-04-19T12:00:00Z",
                            "cwd": "/workspace/coolculator",
                            "model_provider": "openai",
                            "cli_version": "0.200.0",
                        },
                    }
                ),
                json.dumps(
                    {
                        "timestamp": "2026-04-19T12:01:00Z",
                        "type": "response_item",
                        "payload": {
                            "type": "function_call",
                            "name": "apply_patch",
                            "arguments": (
                                "*** Begin Patch\n"
                                "*** Update File: apps/api/src/app.ts\n"
                                "@@\n"
                                "-old\n"
                                "+new\n"
                                "*** End Patch\n"
                            ),
                        },
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    (memories / "MEMORY.md").write_text(
        """# Task Group: Coolculator monorepo bootstrap
scope: generic

## Task 1: Build the API

### keywords

- Coolculator
- Fastify

## User preferences

- prefer backend-first delivery
""",
        encoding="utf-8",
    )
    (memories / "raw_memories.md").write_text(
        """# Raw Memories

## Thread `sess1`
updated_at: 2026-04-19T12:00:00+00:00
cwd: /workspace/coolculator
rollout_path: /tmp/sess1.jsonl

---
description: Coolculator session.
task: build-api
task_group: coolculator-monorepo
keywords: Coolculator, Fastify, Mac handoff
---

Preference signals:
- keep backend-first delivery
""",
        encoding="utf-8",
    )
    (memories / "rollout_summaries" / "2026-04-19-coolculator.md").write_text(
        """thread_id: sess1
updated_at: 2026-04-19T12:00:00+00:00

# Coolculator rollout

## Task 1: Mac handoff
Outcome: success
""",
        encoding="utf-8",
    )

    codex_brain = fake_home / "codex-brain" / "LOG"
    codex_brain.mkdir(parents=True, exist_ok=True)
    (codex_brain / "2026-04-19.md").write_text(
        "# Coolculator handoff\n\nKeep the handoff crisp.\n",
        encoding="utf-8",
    )


def test_cli_codex_export_writes_manifest(tmp_path, monkeypatch):
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: fake_home)
    _build_fake_codex_home(fake_home)

    out_path = tmp_path / "codex.l5.yaml"
    exit_code = main(["codex", "export", "--out", str(out_path)])

    assert exit_code == 0
    manifest = yaml.safe_load(out_path.read_text(encoding="utf-8"))
    assert manifest["agent"]["id"] == "codex"
    assert manifest["recent_sessions"][0]["visibility"] == "team"


def test_cli_codex_build_context_writes_l0_and_l1(tmp_path, monkeypatch):
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: fake_home)
    _build_fake_codex_home(fake_home)

    out_dir = tmp_path / "context"
    exit_code = main(["codex", "build-context", "--out-dir", str(out_dir)])

    assert exit_code == 0
    l0 = yaml.safe_load((out_dir / "l0" / "hot_cache.yaml").read_text(encoding="utf-8"))
    l1_files = list((out_dir / "l1").glob("*.md"))

    assert l0["current_focus"]["last_session"] == "2026-04-19"
    assert any(entity["keyword"] == "Coolculator" for entity in l0["entities"])
    assert l1_files
    assert any(
        "Coolculator" in l1_file.read_text(encoding="utf-8")
        for l1_file in l1_files
    )


def test_cli_codex_eval_fixtures_writes_report(tmp_path, capsys):
    report_path = tmp_path / "report.yaml"

    exit_code = main(
        ["codex", "eval", "--fixtures", "--report-out", str(report_path)]
    )

    assert exit_code == 0
    report = yaml.safe_load(report_path.read_text(encoding="utf-8"))
    stdout = capsys.readouterr().out

    assert report["mode"] == "fixtures"
    assert report["entity_counts"]["total"] >= 1
    assert report["context_generation"]["l0_generated"] is True
    assert "mode: fixtures" in stdout
