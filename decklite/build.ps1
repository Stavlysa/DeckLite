[CmdletBinding()]
param(
    [string]$SourceArchive,
    [string]$Output = (Join-Path $PSScriptRoot "build/decklite-arch-arm-rootfs.tar.zst"),
    [string]$Mirror = "https://de3.mirror.archlinuxarm.org/os",
    [switch]$KeepDownload
)

$ErrorActionPreference = "Stop"
$cacheDirectory = Join-Path $PSScriptRoot "cache"
$downloadedHere = $false

if (-not $SourceArchive) {
    New-Item -ItemType Directory -Force -Path $cacheDirectory | Out-Null
    $SourceArchive = Join-Path $cacheDirectory "ArchLinuxARM-aarch64-latest.tar.gz"
    $checksumFile = "$SourceArchive.md5"

    if (-not (Test-Path -LiteralPath $SourceArchive)) {
        & curl.exe --fail --location --retry 3 "$Mirror/ArchLinuxARM-aarch64-latest.tar.gz" --output $SourceArchive
        if ($LASTEXITCODE -ne 0) { throw "Arch Linux ARM rootfs download failed." }
        $downloadedHere = $true
    }

    & curl.exe --fail --location --retry 3 "$Mirror/ArchLinuxARM-aarch64-latest.tar.gz.md5" --output $checksumFile
    if ($LASTEXITCODE -ne 0) { throw "Checksum download failed." }

    $expected = ((Get-Content -LiteralPath $checksumFile -Raw) -split '\s+')[0].ToLowerInvariant()
    $actual = (Get-FileHash -LiteralPath $SourceArchive -Algorithm MD5).Hash.ToLowerInvariant()
    if ($actual -ne $expected) {
        throw "Rootfs checksum mismatch. Expected $expected, got $actual."
    }
    Write-Host "Verified official rootfs MD5: $actual"
}

$outputDirectory = Split-Path -Parent $Output
New-Item -ItemType Directory -Force -Path $outputDirectory | Out-Null

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) { $python = Get-Command python3 -ErrorAction SilentlyContinue }
if (-not $python) { throw "Python 3 is required." }

& $python.Source (Join-Path $PSScriptRoot "tools/build_rootfs.py") `
    --source (Resolve-Path -LiteralPath $SourceArchive) `
    --overlay (Join-Path $PSScriptRoot "overlay") `
    --output $Output
if ($LASTEXITCODE -ne 0) { throw "Rootfs build failed." }

& $python.Source (Join-Path $PSScriptRoot "tools/verify_rootfs.py") --archive $Output
if ($LASTEXITCODE -ne 0) { throw "Rootfs verification failed." }

if ($downloadedHere -and -not $KeepDownload) {
    Remove-Item -LiteralPath $SourceArchive
    Remove-Item -LiteralPath "$SourceArchive.md5" -ErrorAction SilentlyContinue
}

Get-Item -LiteralPath $Output | Select-Object FullName, Length, LastWriteTime

