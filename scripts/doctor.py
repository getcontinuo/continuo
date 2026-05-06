#!/usr/bin/env python3
"""Cross-platform preflight for the Bourdon memory-cycle pipeline.

Verifies required files exist, required Python modules are importable,
the workspace's short-index files satisfy the canonical schema, and
(optionally) the fixture-driven regression matrix passes.

Replaces the legacy PowerShell version (``scripts/doctor.ps1``) with a
stdlib-only Python implementation so contributors on macOS, Linux, and
Windows can run the preflight locally without PowerShell.

CLI:
    python scripts/doctor.py [--workspace-root PATH]
                             [--install-missing-deps]
                             [--run-regression-matrix]
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

REQUIRED_MODULES = ("yaml", "jsonschema", "mcp")


def _required_files(workspace_root: Path) -> list[tuple[Path, str]]:
    return [
        (workspace_root / "scripts" / "migrate_short_index.py", "Migration script"),
        (workspace_root / "scripts" / "validate_short_index.py", "Validation script"),
        (workspace_root / "scripts" / "build_bourdon_l5.py", "Exporter script"),
        (workspace_root / "scripts" / "mcp_smoke_test.py", "MCP smoke script"),
        (workspace_root / "scripts" / "run_memory_cycle.ps1", "Memory cycle runner"),
        (workspace_root / "scripts" / "regression_matrix.py", "Regression matrix runner"),
        (workspace_root / ".github" / "workflows" / "memory-cycle.yml", "CI workflow"),
        (workspace_root / "spec" / "L5_schema.json", "L5 schema"),
        (workspace_root / "tests" / "fixtures" / "short-index", "Regression fixtures root"),
    ]


def _module_importable(python_cmd: str, name: str) -> bool:
    completed = subprocess.run(
        [python_cmd, "-c", f"import {name}"],
        check=False,
        capture_output=True,
    )
    return completed.returncode == 0


def _install_deps(python_cmd: str) -> None:
    print("Installing missing Python deps...")
    subprocess.run([python_cmd, "-m", "pip", "install", "--upgrade", "pip"], check=True)
    subprocess.run(
        [python_cmd, "-m", "pip", "install", ".[server]", "pyyaml", "jsonschema"],
        check=True,
    )


def _run_check(python_cmd: str, args: list[str]) -> int:
    completed = subprocess.run([python_cmd, *args], check=False)
    return completed.returncode


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bourdon memory-cycle doctor preflight.")
    parser.add_argument("--workspace-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--install-missing-deps",
        action="store_true",
        help="Install missing Python deps via pip before failing.",
    )
    parser.add_argument(
        "--run-regression-matrix",
        action="store_true",
        help="Also run the fixture-driven regression matrix as part of the preflight.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    workspace_root = args.workspace_root.resolve()
    python_cmd = sys.executable
    report_dir = workspace_root / ".cursor" / "memory" / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    doctor_report = report_dir / "doctor-report.json"

    print("Running Bourdon doctor preflight...")
    print(f"Workspace: {workspace_root}")
    print(f"Python: {python_cmd}")

    for path, label in _required_files(workspace_root):
        if not path.exists():
            print(f"{label} not found: {path}", file=sys.stderr)
            return 1

    missing = [m for m in REQUIRED_MODULES if not _module_importable(python_cmd, m)]
    if missing and args.install_missing_deps:
        _install_deps(python_cmd)
        missing = [m for m in REQUIRED_MODULES if not _module_importable(python_cmd, m)]
    if missing:
        print(
            f"Missing Python modules: {', '.join(missing)}. "
            f"Re-run with --install-missing-deps.",
            file=sys.stderr,
        )
        return 1

    migrate_script = str(workspace_root / "scripts" / "migrate_short_index.py")
    validate_script = str(workspace_root / "scripts" / "validate_short_index.py")
    matrix_script = str(workspace_root / "scripts" / "regression_matrix.py")

    rc = _run_check(
        python_cmd,
        [migrate_script, "--workspace-root", str(workspace_root), "--check"],
    )
    if rc != 0:
        print(
            f"migrate_short_index.py --check failed with exit code {rc}",
            file=sys.stderr,
        )
        return rc

    rc = _run_check(python_cmd, [validate_script, "--workspace-root", str(workspace_root)])
    if rc != 0:
        print(f"validate_short_index.py failed with exit code {rc}", file=sys.stderr)
        return rc

    regression_status = "skipped"
    if args.run_regression_matrix:
        rc = _run_check(
            python_cmd, [matrix_script, "--workspace-root", str(workspace_root)]
        )
        if rc != 0:
            print(f"regression_matrix.py failed with exit code {rc}", file=sys.stderr)
            return rc
        regression_status = "passed"

    report = {
        "status": "pass",
        "ranAtUtc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "workspaceRoot": str(workspace_root),
        "python": python_cmd,
        "checkedModules": list(REQUIRED_MODULES),
        "regressionMatrix": regression_status,
    }
    doctor_report.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print()
    print("Doctor preflight passed.")
    print(f"Report: {doctor_report}")
    print("Suggested next step:")
    print(f'  python scripts/regression_matrix.py --workspace-root "{workspace_root}"')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
