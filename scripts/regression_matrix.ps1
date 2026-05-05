Param(
    [string]$WorkspaceRoot = (Get-Location).Path,
    [string]$FixturesRoot = "tests/fixtures/short-index",
    [string]$ReportPath = ".cursor/memory/reports/regression-matrix-report.json"
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

function Invoke-PythonStep {
    param(
        [string]$PythonCmd,
        [string[]]$Arguments
    )
    $output = & $PythonCmd @Arguments 2>&1
    $exitCode = $LASTEXITCODE
    if ($output) {
        $output | ForEach-Object {
            if ($_ -is [System.Management.Automation.ErrorRecord]) {
                Write-Host $_.ToString()
            }
            else {
                Write-Host $_
            }
        }
    }
    return $exitCode
}

function Ensure-ParentDirectory {
    param([string]$PathValue)
    $parent = Split-Path -Path $PathValue -Parent
    if ($parent -and -not (Test-Path $parent)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }
}

$pythonCmd = Resolve-Python
$workspaceRootResolved = (Resolve-Path $WorkspaceRoot).Path
$repoFixturesRoot = Join-Path $workspaceRootResolved $FixturesRoot
if (-not (Test-Path $repoFixturesRoot)) {
    throw "Fixtures root not found: $repoFixturesRoot"
}

$schemaPath = Join-Path $workspaceRootResolved "spec\L5_schema.json"
$buildScript = Join-Path $workspaceRootResolved "scripts\build_continuo_l5.py"
$migrateScript = Join-Path $workspaceRootResolved "scripts\migrate_short_index.py"
$validateScript = Join-Path $workspaceRootResolved "scripts\validate_short_index.py"

$caseDirs = Get-ChildItem -Path $repoFixturesRoot -Directory | Sort-Object Name
if ($caseDirs.Count -eq 0) {
    throw "No regression fixtures found in $repoFixturesRoot"
}

$results = @()
$overallPass = $true

foreach ($caseDir in $caseDirs) {
    $metaPath = Join-Path $caseDir.FullName "meta.json"
    if (-not (Test-Path $metaPath)) {
        throw "Missing fixture metadata: $metaPath"
    }

    $meta = Get-Content -Path $metaPath -Raw | ConvertFrom-Json
    $caseName = $caseDir.Name
    Write-Host ""
    Write-Host "=== Regression case: $caseName ==="

    $tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("continuo-regression-" + [guid]::NewGuid().ToString("N"))
    $tempWorkspaceRoot = Join-Path $tempRoot "workspace"
    $tempGlobalRoot = Join-Path $tempRoot "global-memory"
    $tempOutRoot = Join-Path $tempRoot "out"
    $tempWorkspaceMemory = Join-Path $tempWorkspaceRoot ".cursor\memory"
    $tempGlobalMemory = $tempGlobalRoot
    $workspaceIndex = Join-Path $tempWorkspaceMemory "short-index.json"
    $globalIndex = Join-Path $tempGlobalMemory "short-index.json"
    $workspaceOut = Join-Path $tempOutRoot "workspace.l5.yaml"
    $globalOut = Join-Path $tempOutRoot "global.l5.yaml"

    New-Item -ItemType Directory -Path $tempWorkspaceMemory -Force | Out-Null
    New-Item -ItemType Directory -Path $tempGlobalMemory -Force | Out-Null
    New-Item -ItemType Directory -Path $tempOutRoot -Force | Out-Null

    $workspaceFixture = Join-Path $caseDir.FullName "workspace-short-index.json"
    $globalFixture = Join-Path $caseDir.FullName "global-short-index.json"

    if (Test-Path $workspaceFixture) {
        Copy-Item -Path $workspaceFixture -Destination $workspaceIndex -Force
    }
    else {
        @"
{
  "version": 1,
  "entries": []
}
"@ | Set-Content -Path $workspaceIndex -Encoding UTF8
    }

    if (Test-Path $globalFixture) {
        Copy-Item -Path $globalFixture -Destination $globalIndex -Force
    }
    else {
        @"
{
  "version": 1,
  "entries": []
}
"@ | Set-Content -Path $globalIndex -Encoding UTF8
    }

    $expectedCheck = [int]$meta.expectCheckExit
    $expectedValidate = [int]$meta.expectValidateExit
    $expectedExport = [int]$meta.expectExportExit
    $runMigrateWrite = [bool]$meta.runMigrateWrite
    $expectedKnownEntities = $null
    if ($null -ne $meta.expectedKnownEntities) {
        $expectedKnownEntities = [int]$meta.expectedKnownEntities
    }

    $checkExit = Invoke-PythonStep -PythonCmd $pythonCmd -Arguments @(
        $migrateScript,
        "--workspace-root", $tempWorkspaceRoot,
        "--path", $workspaceIndex,
        "--path", $globalIndex,
        "--check"
    )

    $migrateWriteExit = $null
    if ($runMigrateWrite) {
        $migrateWriteExit = Invoke-PythonStep -PythonCmd $pythonCmd -Arguments @(
            $migrateScript,
            "--workspace-root", $tempWorkspaceRoot,
            "--path", $workspaceIndex,
            "--path", $globalIndex
        )
    }

    $validateExit = Invoke-PythonStep -PythonCmd $pythonCmd -Arguments @(
        $validateScript,
        "--workspace-root", $tempWorkspaceRoot,
        "--path", $workspaceIndex,
        "--path", $globalIndex
    )

    $exportExit = $null
    $knownEntities = $null
    if ($validateExit -eq 0) {
        $exportExit = Invoke-PythonStep -PythonCmd $pythonCmd -Arguments @(
            $buildScript,
            "--workspace-root", $tempWorkspaceRoot,
            "--global-root", $tempGlobalRoot,
            "--workspace-out", $workspaceOut,
            "--global-out", $globalOut,
            "--strict-aliases",
            "--strict-precedence",
            "--schema-path", $schemaPath
        )

        if ($exportExit -eq 0 -and $null -ne $expectedKnownEntities) {
            if (Test-Path $workspaceOut) {
                $knownEntitiesRaw = & $pythonCmd -c "import sys, yaml; data = yaml.safe_load(open(sys.argv[1], encoding='utf-8')); print(len(data.get('known_entities', [])))" $workspaceOut
                if ($LASTEXITCODE -eq 0) {
                    $knownEntities = [int]($knownEntitiesRaw | Select-Object -Last 1)
                }
                else {
                    Write-Host "Failed to parse known_entities count for case '$caseName'."
                }
            }
            else {
                Write-Host "Expected export artifact missing for case '$caseName': $workspaceOut"
            }
        }
    }

    $casePass = $true
    if ($checkExit -ne $expectedCheck) {
        $casePass = $false
    }
    if ($validateExit -ne $expectedValidate) {
        $casePass = $false
    }
    if ($validateExit -eq 0 -and $null -ne $exportExit -and $exportExit -ne $expectedExport) {
        $casePass = $false
    }
    if ($runMigrateWrite -and $migrateWriteExit -ne 0) {
        $casePass = $false
    }
    if ($null -ne $expectedKnownEntities -and $null -ne $knownEntities -and $knownEntities -ne $expectedKnownEntities) {
        $casePass = $false
    }

    $results += [PSCustomObject]@{
        case = $caseName
        description = [string]$meta.description
        pass = $casePass
        expectCheckExit = $expectedCheck
        checkExit = $checkExit
        expectValidateExit = $expectedValidate
        validateExit = $validateExit
        expectExportExit = $expectedExport
        exportExit = $exportExit
        runMigrateWrite = $runMigrateWrite
        migrateWriteExit = $migrateWriteExit
        expectedKnownEntities = $expectedKnownEntities
        knownEntities = $knownEntities
    }

    if (-not $casePass) {
        $overallPass = $false
    }

    Remove-Item -Path $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
}

$reportAbsolutePath = Join-Path $workspaceRootResolved $ReportPath
Ensure-ParentDirectory -PathValue $reportAbsolutePath
$reportPayload = [PSCustomObject]@{
    status = if ($overallPass) { "pass" } else { "fail" }
    ranAtUtc = (Get-Date).ToUniversalTime().ToString("o")
    caseCount = $results.Count
    cases = $results
}
$reportPayload | ConvertTo-Json -Depth 8 | Set-Content -Path $reportAbsolutePath -Encoding UTF8

Write-Host ""
Write-Host "Regression matrix results:"
$results | Format-Table case, pass, checkExit, validateExit, exportExit, knownEntities -AutoSize
Write-Host "Report: $reportAbsolutePath"

if (-not $overallPass) {
    throw "Regression matrix failed. See report at $reportAbsolutePath."
}
