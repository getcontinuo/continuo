Param(
    [string]$WorkspaceRoot = (Get-Location).Path,
    [switch]$InstallMissingDeps,
    [switch]$RunRegressionMatrix
)

$ErrorActionPreference = "Stop"

function Resolve-Python {
    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) {
        return $python.Path
    }
    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) {
        return $py.Path
    }
    throw "Python launcher not found. Install Python and ensure 'python' or 'py' is available in PATH."
}

function Test-PathOrThrow {
    param(
        [string]$PathValue,
        [string]$Label
    )
    if (-not (Test-Path $PathValue)) {
        throw "$Label not found: $PathValue"
    }
}

function Test-PythonModule {
    param(
        [string]$PythonCmd,
        [string]$ModuleName
    )
    & $PythonCmd -c "import $ModuleName" 2>$null
    return $LASTEXITCODE -eq 0
}

$workspaceRootResolved = (Resolve-Path $WorkspaceRoot).Path
$pythonCmd = Resolve-Python
$reportDir = Join-Path $workspaceRootResolved ".cursor\memory\reports"
New-Item -ItemType Directory -Path $reportDir -Force | Out-Null
$doctorReport = Join-Path $reportDir "doctor-report.json"

Write-Host "Running Continual Learning doctor preflight..."
Write-Host "Workspace: $workspaceRootResolved"
Write-Host "Python: $pythonCmd"

$requiredFiles = @(
    @{ path = (Join-Path $workspaceRootResolved "scripts\migrate_short_index.py"); label = "Migration script" },
    @{ path = (Join-Path $workspaceRootResolved "scripts\validate_short_index.py"); label = "Validation script" },
    @{ path = (Join-Path $workspaceRootResolved "scripts\build_continuo_l5.py"); label = "Exporter script" },
    @{ path = (Join-Path $workspaceRootResolved "scripts\mcp_smoke_test.py"); label = "MCP smoke script" },
    @{ path = (Join-Path $workspaceRootResolved "scripts\run_memory_cycle.ps1"); label = "Memory cycle runner" },
    @{ path = (Join-Path $workspaceRootResolved "scripts\regression_matrix.ps1"); label = "Regression matrix runner" },
    @{ path = (Join-Path $workspaceRootResolved ".github\workflows\memory-cycle.yml"); label = "CI workflow" },
    @{ path = (Join-Path $workspaceRootResolved "spec\L5_schema.json"); label = "L5 schema" },
    @{ path = (Join-Path $workspaceRootResolved "tests\fixtures\short-index"); label = "Regression fixtures root" }
)

foreach ($requiredFile in $requiredFiles) {
    Test-PathOrThrow -PathValue $requiredFile.path -Label $requiredFile.label
}

$requiredModules = @("yaml", "jsonschema", "mcp")
$missingModules = @()
foreach ($moduleName in $requiredModules) {
    if (-not (Test-PythonModule -PythonCmd $pythonCmd -ModuleName $moduleName)) {
        $missingModules += $moduleName
    }
}

if ($missingModules.Count -gt 0 -and $InstallMissingDeps.IsPresent) {
    Write-Host "Installing missing Python deps: $($missingModules -join ', ')"
    & $pythonCmd -m pip install --upgrade pip
    & $pythonCmd -m pip install ".[server]" pyyaml jsonschema
    $missingModules = @()
    foreach ($moduleName in $requiredModules) {
        if (-not (Test-PythonModule -PythonCmd $pythonCmd -ModuleName $moduleName)) {
            $missingModules += $moduleName
        }
    }
}

if ($missingModules.Count -gt 0) {
    throw "Missing Python modules: $($missingModules -join ', '). Re-run with -InstallMissingDeps."
}

& $pythonCmd "scripts/migrate_short_index.py" --workspace-root $workspaceRootResolved --check
& $pythonCmd "scripts/validate_short_index.py" --workspace-root $workspaceRootResolved

$regressionStatus = "skipped"
if ($RunRegressionMatrix.IsPresent) {
    powershell -ExecutionPolicy Bypass -File "scripts/regression_matrix.ps1" -WorkspaceRoot $workspaceRootResolved
    $regressionStatus = "passed"
}

$report = @{
    status = "pass"
    ranAtUtc = (Get-Date).ToUniversalTime().ToString("o")
    workspaceRoot = $workspaceRootResolved
    python = $pythonCmd
    checkedModules = $requiredModules
    regressionMatrix = $regressionStatus
}
$report | ConvertTo-Json -Depth 8 | Set-Content -Path $doctorReport -Encoding UTF8

Write-Host ""
Write-Host "Doctor preflight passed."
Write-Host "Report: $doctorReport"
Write-Host "Suggested next step:"
Write-Host "powershell -ExecutionPolicy Bypass -File scripts/run_memory_cycle.ps1 -WorkspaceRoot `"$workspaceRootResolved`" -SchemaPath `".\spec\L5_schema.json`""
