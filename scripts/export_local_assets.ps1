param(
    [Parameter(Mandatory = $true)]
    [string]$Destination
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$resolvedDestination = [System.IO.Path]::GetFullPath($Destination)

if ($resolvedDestination.StartsWith($projectRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Choose a destination outside the project directory, such as an external drive or private cloud folder."
}

New-Item -ItemType Directory -Force -Path $resolvedDestination | Out-Null

$assets = @(
    "backend\.env",
    "data_sources\manuals",
    "backend\uploads",
    "backend\vector_store"
)

foreach ($relativePath in $assets) {
    $source = Join-Path $projectRoot $relativePath
    if (-not (Test-Path -LiteralPath $source)) {
        Write-Warning "Skipped missing path: $relativePath"
        continue
    }

    $target = Join-Path $resolvedDestination $relativePath
    $targetParent = Split-Path -Parent $target
    New-Item -ItemType Directory -Force -Path $targetParent | Out-Null
    Copy-Item -LiteralPath $source -Destination $target -Recurse -Force
    Write-Host "Copied $relativePath"
}

$note = @"
This folder contains private runtime data that is intentionally excluded from Git.
Keep it private. Restore each path into the same relative location after cloning.
The MySQL database is not included; export it separately with mysqldump.
"@
Set-Content -LiteralPath (Join-Path $resolvedDestination "RESTORE_NOTE.txt") -Value $note -Encoding UTF8

Write-Host "Local assets exported to: $resolvedDestination"
