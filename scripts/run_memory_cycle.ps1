Param(
    [string]$WorkspaceRoot = (Get-Location).Path,
    [string]$SchemaPath = "",
    [string]$ReportDir = ".cursor/memory/reports"
)

$ErrorActionPreference = "Stop"

Write-Host "Running memory cycle: merge -> export -> MCP smoke assertions"

$reportPath = Join-Path $WorkspaceRoot $ReportDir
New-Item -ItemType Directory -Path $reportPath -Force | Out-Null
$mcpReport = Join-Path $reportPath "mcp-smoke-report.json"
$cycleReport = Join-Path $reportPath "memory-cycle-report.json"

$builderArgs = @(
    "scripts/build_continuo_l5.py",
    "--workspace-root", $WorkspaceRoot,
    "--strict-aliases",
    "--strict-precedence"
)

if ($SchemaPath -and (Test-Path $SchemaPath)) {
    $builderArgs += @("--schema-path", $SchemaPath)
}

python @builderArgs
if ($LASTEXITCODE -ne 0) {
    throw "build_continuo_l5.py failed with exit code $LASTEXITCODE"
}
python "scripts/mcp_smoke_test.py" --assertions --json-report $mcpReport
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
