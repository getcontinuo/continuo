"""Top-level `continuo` CLI."""

from __future__ import annotations

import argparse
import sys
import tempfile
from collections import Counter
from datetime import date, datetime, time
from pathlib import Path
from typing import Any

import yaml

from adapters.base import AdapterDiscoveryError
from adapters.claude_code import ClaudeCodeAdapter
from adapters.codex import CodexAdapter
from core.codex_context import filter_manifest_for_access, write_codex_context_artifacts
from core.codex_fixtures import create_sample_codex_sources
from core.l5_io import write_l5_dict


def _default_claude_code_l5_path() -> Path:
    """Resolve ~/agent-library/agents/claude-code.l5.yaml at call time.

    Computed at call time (not import time) so tests can monkeypatch
    ``Path.home`` and have the resolution honor the override.
    """
    return Path.home() / "agent-library" / "agents" / "claude-code.l5.yaml"


def _parse_since(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        parsed = date.fromisoformat(value)
        return datetime.combine(parsed, time.min)


def _write_yaml_if_requested(data: dict[str, Any], path: str | None) -> None:
    if not path:
        return
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def _print_yaml(data: dict[str, Any]) -> None:
    print(yaml.safe_dump(data, sort_keys=False), end="")


def _build_adapter(args: argparse.Namespace) -> CodexAdapter:
    codex_home = Path(args.codex_home) if getattr(args, "codex_home", None) else None
    codex_brain = (
        Path(args.codex_brain) if getattr(args, "codex_brain", None) else None
    )
    return CodexAdapter(codex_home=codex_home, codex_brain=codex_brain)


def _manifest_for_access(
    adapter: CodexAdapter, since: datetime | None, access_level: str
) -> dict[str, Any]:
    manifest = adapter.export_l5(since=since)
    return filter_manifest_for_access(manifest, access_level=access_level)


def _handle_codex_export(args: argparse.Namespace) -> int:
    adapter = _build_adapter(args)
    data = _manifest_for_access(
        adapter,
        since=_parse_since(args.since),
        access_level=args.access_level,
    )
    _write_yaml_if_requested(data, args.out)
    _print_yaml(data)
    return 0


def _handle_codex_build_context(args: argparse.Namespace) -> int:
    adapter = _build_adapter(args)
    manifest = _manifest_for_access(adapter, since=_parse_since(args.since), access_level="team")
    report = write_codex_context_artifacts(manifest, Path(args.out_dir), access_level="team")
    _print_yaml(report)
    return 0


def _fixture_adapter() -> CodexAdapter:
    tmpdir = tempfile.TemporaryDirectory()
    sources = create_sample_codex_sources(Path(tmpdir.name) / "home")
    adapter = CodexAdapter(
        codex_home=sources["codex_home"],
        codex_brain=sources["codex_brain"],
    )
    adapter._fixture_tmpdir = tmpdir  # type: ignore[attr-defined]
    return adapter


def _source_coverage(adapter: CodexAdapter) -> dict[str, Any]:
    health = adapter.health_check()
    details = health.details or {}
    return {
        "status": health.status,
        "session_index": details.get("session_index") != "missing",
        "sessions_dir": details.get("sessions_dir") != "missing",
        "memory_md": details.get("memory_md") != "missing",
        "raw_memories": details.get("raw_memories") != "missing",
        "rollout_summaries_dir": details.get("rollout_summaries_dir") != "missing",
        "codex_brain": details.get("codex_brain") != "missing",
    }


def _handle_codex_eval(args: argparse.Namespace) -> int:
    adapter = _fixture_adapter() if args.fixtures else _build_adapter(args)
    manifest = _manifest_for_access(
        adapter,
        since=_parse_since(args.since),
        access_level=args.access_level,
    )
    with tempfile.TemporaryDirectory() as tmpdir:
        context_report = write_codex_context_artifacts(
            manifest,
            Path(tmpdir) / "context",
            access_level=args.access_level,
        )

    entities = manifest.get("known_entities") or []
    sessions = manifest.get("recent_sessions") or []
    entity_counts = Counter(entity.get("type") or "topic" for entity in entities)
    visibility_counts = Counter(entity.get("visibility") or "public" for entity in entities)
    project_hits = [
        entity["name"]
        for entity in entities
        if entity.get("type") == "project"
    ][:5]
    preference_hits = [
        entity["name"]
        for entity in entities
        if entity.get("type") == "preference"
    ][:5]

    report = {
        "mode": "fixtures" if args.fixtures else "live",
        "access_level": args.access_level,
        "source_coverage": _source_coverage(adapter),
        "session_count": len(sessions),
        "entity_counts": {
            "total": len(entities),
            "by_type": dict(entity_counts),
        },
        "visibility_counts": dict(visibility_counts),
        "context_generation": context_report,
        "recognition_spot_checks": {
            "projects": project_hits,
            "preferences": preference_hits,
        },
    }
    _write_yaml_if_requested(report, args.report_out)
    _print_yaml(report)
    return 0


def _handle_claude_code_export(args: argparse.Namespace) -> int:
    """
    Build a Claude Code L5 manifest and write it to ``~/agent-library/agents/
    claude-code.l5.yaml`` (or ``--out`` if specified). Designed for use as a
    SessionEnd hook in Claude Code:

      Add to ~/.claude/settings.json:
        "hooks": {
          "SessionEnd": [
            { "command": "continuo claude-code export" }
          ]
        }

    Operates silently on success and **never raises** -- a session-end hook
    that crashes is worse than a session-end hook that does nothing. Returns
    0 in all observable failure modes; use --verbose to surface diagnostics
    to stderr.
    """
    try:
        adapter = ClaudeCodeAdapter()
    except Exception as exc:  # noqa: BLE001 -- hook contract: never raises
        if args.verbose:
            print(
                f"continuo claude-code export: adapter init failed: {exc}",
                file=sys.stderr,
            )
        return 0

    try:
        manifest = adapter.export_l5(since=_parse_since(args.since))
    except AdapterDiscoveryError as exc:
        if args.verbose:
            print(
                f"continuo claude-code export: no Claude Code memory sources found ({exc}), skipping",
                file=sys.stderr,
            )
        return 0
    except Exception as exc:  # noqa: BLE001 -- hook contract
        if args.verbose:
            print(
                f"continuo claude-code export: export failed: {exc}",
                file=sys.stderr,
            )
        return 0

    data = filter_manifest_for_access(manifest, access_level=args.access_level)

    out_path = Path(args.out) if args.out else _default_claude_code_l5_path()
    try:
        write_l5_dict(data, out_path)
    except Exception as exc:  # noqa: BLE001 -- hook contract
        if args.verbose:
            print(
                f"continuo claude-code export: write to {out_path} failed: {exc}",
                file=sys.stderr,
            )
        return 0

    if getattr(args, "print_manifest", False):
        _print_yaml(data)
    elif args.verbose:
        print(
            f"continuo claude-code export: wrote {out_path}",
            file=sys.stderr,
        )
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="continuo",
        description="Continuo CLI",
    )
    subparsers = parser.add_subparsers(dest="command")

    codex = subparsers.add_parser("codex", help="Codex-specific commands")
    codex_subparsers = codex.add_subparsers(dest="codex_command")

    export_cmd = codex_subparsers.add_parser(
        "export", help="Build a Codex L5 manifest"
    )
    export_cmd.add_argument("--since")
    export_cmd.add_argument("--out")
    export_cmd.add_argument(
        "--access-level",
        choices=("public", "team", "private"),
        default="team",
    )
    export_cmd.add_argument("--codex-home", help=argparse.SUPPRESS)
    export_cmd.add_argument("--codex-brain", help=argparse.SUPPRESS)
    export_cmd.set_defaults(func=_handle_codex_export)

    build_context_cmd = codex_subparsers.add_parser(
        "build-context", help="Generate Codex L0/L1 artifacts"
    )
    build_context_cmd.add_argument("--out-dir", required=True)
    build_context_cmd.add_argument("--since")
    build_context_cmd.add_argument("--codex-home", help=argparse.SUPPRESS)
    build_context_cmd.add_argument("--codex-brain", help=argparse.SUPPRESS)
    build_context_cmd.set_defaults(func=_handle_codex_build_context)

    eval_cmd = codex_subparsers.add_parser("eval", help="Evaluate Codex sources")
    eval_mode = eval_cmd.add_mutually_exclusive_group()
    eval_mode.add_argument("--fixtures", action="store_true")
    eval_mode.add_argument("--live", action="store_true")
    eval_cmd.add_argument("--since")
    eval_cmd.add_argument(
        "--access-level",
        choices=("public", "team", "private"),
        default="team",
    )
    eval_cmd.add_argument("--report-out")
    eval_cmd.add_argument("--codex-home", help=argparse.SUPPRESS)
    eval_cmd.add_argument("--codex-brain", help=argparse.SUPPRESS)
    eval_cmd.set_defaults(func=_handle_codex_eval)

    # ---- claude-code subcommands --------------------------------------------
    cc = subparsers.add_parser(
        "claude-code", help="Claude Code-specific commands"
    )
    cc_subparsers = cc.add_subparsers(dest="cc_command")

    cc_export_cmd = cc_subparsers.add_parser(
        "export",
        help=(
            "Build a Claude Code L5 manifest and write it to ~/agent-library/. "
            "Silent + never raises; designed for SessionEnd hook use."
        ),
    )
    cc_export_cmd.add_argument(
        "--since",
        help="Filter sessions newer than this ISO 8601 date / datetime.",
    )
    cc_export_cmd.add_argument(
        "--out",
        help=(
            "Output YAML path. Default: ~/agent-library/agents/claude-code.l5.yaml"
        ),
    )
    cc_export_cmd.add_argument(
        "--access-level",
        choices=("public", "team", "private"),
        default="team",
    )
    cc_export_cmd.add_argument(
        "--print",
        dest="print_manifest",
        action="store_true",
        help="Also print the filtered manifest to stdout (default: silent).",
    )
    cc_export_cmd.add_argument(
        "--verbose",
        action="store_true",
        help="Log progress + errors to stderr (default: silent).",
    )
    cc_export_cmd.set_defaults(func=_handle_claude_code_export)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 1
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
