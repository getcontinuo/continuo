Param(
    [string]$WorkspaceRoot = (Get-Location).Path,
    [string]$SchemaPath = "",
    [string]$ReportDir = ".cursor/memory/reports"
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

$pythonCmd = Resolve-Python

Write-Host "Running memory cycle: migrate -> validate -> export -> MCP smoke assertions"

$reportPath = Join-Path $WorkspaceRoot $ReportDir
New-Item -ItemType Directory -Path $reportPath -Force | Out-Null
$mcpReport = Join-Path $reportPath "mcp-smoke-report.json"
$cycleReport = Join-Path $reportPath "memory-cycle-report.json"

$builderArgs = @(
    "scripts/build_bourdon_l5.py",
    "--workspace-root", $WorkspaceRoot,
    "--strict-aliases",
    "--strict-precedence"
)

if ($SchemaPath -and (Test-Path $SchemaPath)) {
    $builderArgs += @("--schema-path", $SchemaPath)
}

& $pythonCmd "scripts/migrate_short_index.py" --workspace-root $WorkspaceRoot
if ($LASTEXITCODE -ne 0) {
    throw "migrate_short_index.py failed with exit code $LASTEXITCODE"
}
& $pythonCmd "scripts/validate_short_index.py" --workspace-root $WorkspaceRoot
if ($LASTEXITCODE -ne 0) {
    throw "validate_short_index.py failed with exit code $LASTEXITCODE"
}
& $pythonCmd @builderArgs
if ($LASTEXITCODE -ne 0) {
    throw "build_bourdon_l5.py failed with exit code $LASTEXITCODE"
}
& $pythonCmd "scripts/mcp_smoke_test.py" --assertions --json-report $mcpReport --server-python $pythonCmd
if ($LASTEXITCODE -ne 0) {
    throw "mcp_smoke_test.py failed with exit code $LASTEXITCODE"
}

$cyclePayload = @{
    status = "pass"
    ranAtUtc = (Get-Date).ToUniversalTime().ToString("o")
    workspaceRoot = $WorkspaceRoot
    schemaPath = $SchemaPath
    reports = @{
        mcpSmoke = $mcpReport
    }
}
$cyclePayload | ConvertTo-Json -Depth 8 | Set-Content -Path $cycleReport -Encoding UTF8

Write-Host "Memory cycle passed."
Write-Host "Report: $cycleReport"
