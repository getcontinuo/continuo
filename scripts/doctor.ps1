# DEPRECATED — kept for backward compatibility.
#
# The canonical implementation is now scripts/doctor.py
# (cross-platform; runs on macOS, Linux, and Windows without PowerShell).
# This wrapper delegates to it and forwards exit codes. It will be
# removed in a future release; please call the .py script directly.
Param(
    [string]$WorkspaceRoot = (Get-Location).Path,
    [switch]$InstallMissingDeps,
    [switch]$RunRegressionMatrix
)

$ErrorActionPreference = "Stop"

function Resolve-Python {
    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) { return $python.Path }
    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) { return $py.Path }
    throw "Python launcher not found. Install Python and ensure 'python' or 'py' is available in PATH."
}

Write-Warning "scripts/doctor.ps1 is deprecated; delegating to scripts/doctor.py."

$pythonCmd = Resolve-Python
$workspaceRootResolved = (Resolve-Path $WorkspaceRoot).Path
$pyScript = Join-Path $workspaceRootResolved "scripts\doctor.py"

$pyArgs = @($pyScript, "--workspace-root", $workspaceRootResolved)
if ($InstallMissingDeps.IsPresent) {
    $pyArgs += "--install-missing-deps"
}
if ($RunRegressionMatrix.IsPresent) {
    $pyArgs += "--run-regression-matrix"
}

& $pythonCmd @pyArgs
exit $LASTEXITCODE
