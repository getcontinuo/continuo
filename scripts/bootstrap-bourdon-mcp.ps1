Param(
    [string]$WorkspaceRoot = (Get-Location).Path
)

$ErrorActionPreference = "Stop"

Write-Host "Bootstrapping Bourdon MCP integration..."

function Resolve-Python {
    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) {
        return $python.Path
    }
    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) {
        return $py.Path
    }
    throw "Python is required but was not found in PATH."
}

$pythonCmd = Resolve-Python

& $pythonCmd -m pip install --upgrade pip
& $pythonCmd -m pip install ".[server]" pyyaml jsonschema

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
$didSeedWorkspaceFixtures = $false

$workspaceFixtureIndex = @"
{
  "version": 1,
  "entries": [
    {
      "topic_key": "bourdon_mcp",
      "topic_name": "Bourdon MCP",
      "summary": "Workspace-specific Bourdon MCP wiring and retrieval checks.",
      "triggers": [
        "bourdon",
        "bourdon mcp",
        "l6 server"
      ],
      "scope": "workspace",
      "access_level": "team",
      "last_updated": "2026-05-01",
      "tags": [
        "workspace",
        "memory-chain",
        "federation"
      ]
    },
    {
      "topic_key": "keyword_retrieval",
      "topic_name": "Keyword Retrieval",
      "summary": "Alias-driven retrieval flow for short and long memory chains.",
      "triggers": [
        "keyword retrieval",
        "trigger aliases",
        "memory recall"
      ],
      "scope": "workspace",
      "access_level": "team",
      "last_updated": "2026-05-01",
      "tags": [
        "workspace",
        "retrieval"
      ]
    }
  ]
}
"@

$workspaceFixtureTopics = @{
    "bourdon_mcp.md" = @"
# Bourdon MCP

## Trigger Aliases
- bourdon
- bourdon mcp
- l6 server

## Short Chain
- Workspace overlay for Bourdon MCP should take precedence over global baseline.

## Long Chain
- This workspace uses the continual-learning plugin to produce short and long memory chains.
- Bourdon L5 manifests are generated from merged chain data.
- L6 store queries should resolve the workspace-specific summary for overlapping keys.

## Retrieval Hints
- Prefer `find_entity("Bourdon MCP")`.
- Validate visibility remains `team`.

## Source Notes
- Seeded for live smoke test on 2026-05-01.
"@
    "keyword_retrieval.md" = @"
# Keyword Retrieval

## Trigger Aliases
- keyword retrieval
- trigger aliases
- memory recall

## Short Chain
- Triggers should be concise, reusable, and deterministic.

## Long Chain
- Short index aliases connect user phrases to topic keys.
- Long topic chains provide the expanded context once a trigger hits.

## Retrieval Hints
- Query by alias and canonical key.

## Source Notes
- Seeded for smoke testing of retrieval paths.
"@
}

if (-not (Test-Path $workspaceShortIndex)) {
    $workspaceFixtureIndex | Set-Content -Path $workspaceShortIndex -Encoding UTF8
    $didSeedWorkspaceFixtures = $true
}
else {
    try {
        $workspacePayload = Get-Content -Path $workspaceShortIndex -Raw | ConvertFrom-Json
        $workspaceEntries = @($workspacePayload.entries)
        if ($workspaceEntries.Count -eq 0) {
            $workspaceFixtureIndex | Set-Content -Path $workspaceShortIndex -Encoding UTF8
            $didSeedWorkspaceFixtures = $true
        }
    }
    catch {
        throw "Workspace short-index is invalid JSON: $workspaceShortIndex"
    }
}

if (-not (Test-Path $globalShortIndex)) {
@"
{
  "version": 1,
  "entries": []
}
"@ | Set-Content -Path $globalShortIndex -Encoding UTF8
}

if ($didSeedWorkspaceFixtures) {
    foreach ($topicFile in $workspaceFixtureTopics.Keys) {
        $topicPath = Join-Path $workspaceTopics $topicFile
        if (-not (Test-Path $topicPath)) {
            $workspaceFixtureTopics[$topicFile] | Set-Content -Path $topicPath -Encoding UTF8
        }
    }
    Write-Host "Seeded workspace smoke-test fixtures for Bourdon MCP and Keyword Retrieval."
}

& $pythonCmd "scripts/migrate_short_index.py" --workspace-root $WorkspaceRoot
& $pythonCmd "scripts/validate_short_index.py" --workspace-root $WorkspaceRoot

Write-Host "Bootstrap complete."
