"""Hermetic fixture sources for `bourdon codex eval --fixtures`."""

from __future__ import annotations

import json
from pathlib import Path


def create_sample_codex_sources(home: Path) -> dict[str, Path]:
    """Write a small but realistic Codex source tree under `home`."""
    home = Path(home)
    codex_home = home / ".codex"
    memories = codex_home / "memories"
    sessions_dir = codex_home / "sessions" / "2026" / "04" / "19"
    brain_dir = home / "codex-brain" / "LOG"

    (memories / "rollout_summaries").mkdir(parents=True, exist_ok=True)
    sessions_dir.mkdir(parents=True, exist_ok=True)
    brain_dir.mkdir(parents=True, exist_ok=True)

    (codex_home / "session_index.jsonl").write_text(
        json.dumps(
            {
                "id": "fixture-session",
                "thread_name": "Ship Coolculator context",
                "updated_at": "2026-04-19T12:00:00Z",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    rollout_path = sessions_dir / "rollout-2026-04-19T12-00-00Z-fixture-session.jsonl"
    rollout_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "timestamp": "2026-04-19T12:00:00Z",
                        "type": "session_meta",
                        "payload": {
                            "id": "fixture-session",
                            "timestamp": "2026-04-19T12:00:00Z",
                            "cwd": "/workspace/coolculator",
                            "model_provider": "openai",
                            "cli_version": "0.200.0",
                            "source": "desktop",
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

## Thread `fixture-session`
updated_at: 2026-04-19T12:00:00+00:00
cwd: /workspace/coolculator
rollout_path: /tmp/fixture.jsonl

---
description: Fixture Coolculator session.
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
        """thread_id: fixture-session
updated_at: 2026-04-19T12:00:00+00:00

# Coolculator rollout

## Task 1: Mac handoff
Outcome: success
""",
        encoding="utf-8",
    )
    (brain_dir / "2026-04-19.md").write_text(
        "# Coolculator handoff\n\nKeep the handoff crisp.\n",
        encoding="utf-8",
    )

    return {
        "codex_home": codex_home,
        "codex_brain": home / "codex-brain",
        "rollout": rollout_path,
    }
