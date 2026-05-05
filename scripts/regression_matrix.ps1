# DEPRECATED — kept for backward compatibility.
#
# The canonical implementation is now scripts/regression_matrix.py
# (cross-platform; runs on macOS, Linux, and Windows without PowerShell).
# This wrapper delegates to it and forwards exit codes. It will be
# removed in a future release; please call the .py script directly.
Param(
    [string]$WorkspaceRoot = (Get-Location).Path,
    [string]$FixturesRoot = "tests/fixtures/short-index",
    [string]$ReportPath = ".cursor/memory/reports/regression-matrix-report.json"
)

$ErrorActionPreference = "Stop"

function Resolve-Python {
    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) { return $python.Path }
    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) { return $py.Path }
    throw "Python launcher not found. Install Python and ensure 'python' or 'py' is available in PATH."
}

Write-Warning "scripts/regression_matrix.ps1 is deprecated; delegating to scripts/regression_matrix.py."

$pythonCmd = Resolve-Python
$workspaceRootResolved = (Resolve-Path $WorkspaceRoot).Path
$pyScript = Join-Path $workspaceRootResolved "scripts\regression_matrix.py"

& $pythonCmd $pyScript `
    --workspace-root $workspaceRootResolved `
    --fixtures-root $FixturesRoot `
    --report-path $ReportPath
exit $LASTEXITCODE
