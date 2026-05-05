from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml


REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURES_ROOT = REPO_ROOT / "tests" / "fixtures" / "short-index"
MIGRATE_SCRIPT = REPO_ROOT / "scripts" / "migrate_short_index.py"
VALIDATE_SCRIPT = REPO_ROOT / "scripts" / "validate_short_index.py"
DOCTOR_SCRIPT = REPO_ROOT / "scripts" / "doctor.ps1"
WORKFLOW_FILE = REPO_ROOT / ".github" / "workflows" / "memory-cycle.yml"


def _default_short_index_text() -> str:
    return '{\n  "version": 1,\n  "entries": []\n}\n'


def _copy_fixture_case(case_dir: Path, tmp_path: Path) -> tuple[Path, Path, dict[str, object]]:
    workspace_root = tmp_path / "workspace"
    workspace_memory = workspace_root / ".cursor" / "memory"
    global_root = tmp_path / "global-memory"
    workspace_memory.mkdir(parents=True)
    global_root.mkdir(parents=True)

    workspace_index = workspace_memory / "short-index.json"
    global_index = global_root / "short-index.json"

    workspace_fixture = case_dir / "workspace-short-index.json"
    global_fixture = case_dir / "global-short-index.json"
    workspace_index.write_text(
        workspace_fixture.read_text(encoding="utf-8") if workspace_fixture.exists() else _default_short_index_text(),
        encoding="utf-8",
    )
    global_index.write_text(
        global_fixture.read_text(encoding="utf-8") if global_fixture.exists() else _default_short_index_text(),
        encoding="utf-8",
    )

    meta = json.loads((case_dir / "meta.json").read_text(encoding="utf-8"))
    return workspace_root, workspace_index, global_index, meta


def _run_python(*args: Path | str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *(str(arg) for arg in args)],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


@pytest.mark.parametrize(
    "case_name",
    sorted(path.name for path in FIXTURES_ROOT.iterdir() if path.is_dir()),
)
def test_short_index_regression_fixtures_match_expected_check_and_validate_exits(
    tmp_path: Path, case_name: str
) -> None:
    case_dir = FIXTURES_ROOT / case_name
    workspace_root, workspace_index, global_index, meta = _copy_fixture_case(case_dir, tmp_path)

    check_result = _run_python(
        MIGRATE_SCRIPT,
        "--workspace-root",
        workspace_root,
        "--path",
        workspace_index,
        "--path",
        global_index,
        "--check",
    )
    assert check_result.returncode == meta["expectCheckExit"], check_result.stdout + check_result.stderr

    if meta["runMigrateWrite"]:
        migrate_write_result = _run_python(
            MIGRATE_SCRIPT,
            "--workspace-root",
            workspace_root,
            "--path",
            workspace_index,
            "--path",
            global_index,
        )
        assert migrate_write_result.returncode == 0, (
            migrate_write_result.stdout + migrate_write_result.stderr
        )

    validate_result = _run_python(
        VALIDATE_SCRIPT,
        "--workspace-root",
        workspace_root,
        "--path",
        workspace_index,
        "--path",
        global_index,
    )
    assert validate_result.returncode == meta["expectValidateExit"], (
        validate_result.stdout + validate_result.stderr
    )


def test_doctor_checks_native_exit_codes_after_short_index_preflight_steps() -> None:
    doctor_text = DOCTOR_SCRIPT.read_text(encoding="utf-8")

    migrate_guard = re.compile(
        r'& \$pythonCmd "scripts/migrate_short_index\.py".*?\n'
        r'if \(\$LASTEXITCODE -ne 0\) \{\n'
        r'\s+throw "migrate_short_index\.py --check failed with exit code \$LASTEXITCODE"\n'
        r"\}",
        re.DOTALL,
    )
    validate_guard = re.compile(
        r'& \$pythonCmd "scripts/validate_short_index\.py".*?\n'
        r'if \(\$LASTEXITCODE -ne 0\) \{\n'
        r'\s+throw "validate_short_index\.py failed with exit code \$LASTEXITCODE"\n'
        r"\}",
        re.DOTALL,
    )

    assert migrate_guard.search(doctor_text)
    assert validate_guard.search(doctor_text)


def test_memory_cycle_workflow_stops_after_failed_migration_check() -> None:
    workflow = yaml.safe_load(WORKFLOW_FILE.read_text(encoding="utf-8"))
    steps = workflow["jobs"]["verify-memory-cycle"]["steps"]
    schema_step = next(
        step for step in steps if step.get("name") == "Enforce canonical short-index schema (CI check only)"
    )

    run_script = schema_step["run"]
    expected_guard = "if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }"

    assert "python scripts/migrate_short_index.py --workspace-root \".\" --check" in run_script
    assert expected_guard in run_script
    assert run_script.index(expected_guard) < run_script.index(
        "python scripts/validate_short_index.py --workspace-root \".\""
    )
