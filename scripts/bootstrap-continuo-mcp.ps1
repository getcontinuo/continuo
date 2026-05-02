Param(
    [string]$WorkspaceRoot = (Get-Location).Path
)

$ErrorActionPreference = "Stop"

Write-Host "Bootstrapping Continuo MCP integration..."

python -m pip install --upgrade pip
python -m pip install "continuo-memory[server]" pyyaml jsonschema

$workspaceMemory = Join-Path $WorkspaceRoot ".cursor\memory"
$workspaceTopics = Join-Path $workspaceMemory "topics"
$globalMemory = Join-Path $HOME ".cursor\memory"
$globalTopics = Join-Path $globalMemory "topics"
$agentLibrary = Join-Path $HOME "agent-library\agents"

New-Item -ItemType Directory -Path $workspaceTopics -Force | Out-Null
New-Item -ItemType Directory -Path $globalTopics -Force | Out-Null
New-Item -ItemType Directory -Path $agentLibrary -Force | Out-Null

$workspaceShortIndex = Join-Path $workspaceMemory "short-index.json"
$globalShortIndex = Join-Path $globalMemory "short-index.json"

if (-not (Test-Path $workspaceShortIndex)) {
@"
{
  "version": 1,
  "entries": []
}
"@ | Set-Content -Path $workspaceShortIndex -Encoding UTF8
}

if (-not (Test-Path $globalShortIndex)) {
@"
{
  "version": 1,
  "entries": []
}
"@ | Set-Content -Path $globalShortIndex -Encoding UTF8
}

Write-Host "Bootstrap complete."
