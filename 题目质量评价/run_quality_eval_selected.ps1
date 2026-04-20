$ErrorActionPreference = "Stop"

function Find-ChildDirectory {
    param(
        [string]$ParentDir,
        [scriptblock]$Predicate
    )

    $match = Get-ChildItem -Path $ParentDir -Directory | Where-Object $Predicate | Select-Object -First 1
    if (-not $match) {
        throw "Cannot locate required sibling directory under $ParentDir"
    }
    return $match.FullName
}

$projectDir = $PSScriptRoot
$rootDir = Split-Path -Parent $projectDir
$schemaProjectDir = Find-ChildDirectory $rootDir { Test-Path (Join-Path $_.FullName "output\batch\normalized") }
$generationProjectDir = Find-ChildDirectory $rootDir {
    (Test-Path (Join-Path $_.FullName "artifacts")) -and
    (Test-Path (Join-Path $_.FullName "output")) -and
    ($_.FullName -ne $projectDir)
}

$schemaDir = Join-Path $schemaProjectDir "output\batch\normalized"
$artifactDir = Join-Path $generationProjectDir "artifacts"
$markdownDir = Join-Path $generationProjectDir "output"

$jobs = @(
    @{
        Name = "CF1324C_v1_campus_ops_20260409_213731"
        SourceProblemId = "CF1324C"
    },
    @{
        Name = "CF1338B_v1_campus_ops_20260409_214952"
        SourceProblemId = "CF1338B"
    },
    @{
        Name = "CF1338D_v1_campus_ops_20260409_215949"
        SourceProblemId = "CF1338D"
    },
    @{
        Name = "CF1399E1_v1_campus_ops_20260409_221847"
        SourceProblemId = "CF1399E1"
    },
    @{
        Name = "CF1399E2_v1_campus_ops_20260409_222826"
        SourceProblemId = "CF1399E2"
    },
    @{
        Name = "CF1468F_v1_campus_ops_20260409_223826"
        SourceProblemId = "CF1468F"
    },
    @{
        Name = "CF1513D_v1_campus_ops_20260409_225026"
        SourceProblemId = "CF1513D"
    },
    @{
        Name = "CF253C_v1_campus_ops_20260409_230308"
        SourceProblemId = "CF253C"
    },
    @{
        Name = "CF722D_v1_campus_ops_20260409_231408"
        SourceProblemId = "CF722D"
    }
)

Set-Location $projectDir

foreach ($job in $jobs) {
    $name = $job.Name
    $sourceProblemId = $job.SourceProblemId
    $schemaPath = Join-Path $schemaDir ($sourceProblemId + ".json")
    $artifactPath = Join-Path $artifactDir ($name + ".json")
    $markdownPath = Join-Path $markdownDir ($name + ".md")

    if (-not (Test-Path $schemaPath)) {
        Write-Host "[SKIP] schema not found: $schemaPath"
        continue
    }
    if (-not (Test-Path $artifactPath)) {
        Write-Host "[SKIP] artifact not found: $artifactPath"
        continue
    }
    if (-not (Test-Path $markdownPath)) {
        Write-Host "[SKIP] markdown not found: $markdownPath"
        continue
    }

    Write-Host "[RUN] $name"
    python main.py --schema $schemaPath --artifact $artifactPath --markdown $markdownPath
}
