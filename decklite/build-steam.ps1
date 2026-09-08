[CmdletBinding()]
param(
    [string]$SourceArchive = (Join-Path $PSScriptRoot "cache/xfce-en-20260808-202640.tar.zst"),
    [string]$SteamPayload = (Join-Path $PSScriptRoot "cache/steam-arm64-1785799196/root"),
    [string]$PackageCache = (Join-Path $PSScriptRoot "cache/steam-arm64-1785799196/packages"),
    [string]$HangoverBundle = (Join-Path $PSScriptRoot "cache/hangover/hangover_11.16_debian13_trixie_arm64.tar"),
    [string]$DebianPackageIndex = (Join-Path $PSScriptRoot "cache/debian/trixie-main-arm64-Packages.xz"),
    [string]$DebianPackageCache = (Join-Path $PSScriptRoot "cache/debian/packages"),
    [string]$HangoverLayer = (Join-Path $PSScriptRoot "cache/hangover/hangover-preinstalled-layer.tar.zst"),
    [string]$GeProtonArchive = (Join-Path $PSScriptRoot "cache/ge-proton/GE-Proton11-6-aarch64.tar.gz"),
    [string]$SteamRt4Archive = (Join-Path $PSScriptRoot "cache/steamrt4/SteamLinuxRuntime_4-arm64.tar.xz"),
    [string]$WinePrefixTemplatesArchive = (Join-Path $PSScriptRoot "cache/wine-prefix-templates.tar.zst"),
    [string]$Winetricks = (Join-Path $PSScriptRoot "cache/winetricks-20260125"),
    [string]$Output = (Join-Path $PSScriptRoot "build/decklite-steam-arm64-rootfs.tar.zst"),
    [ValidateRange(1, 16)][int]$Jobs = 6
)

$ErrorActionPreference = "Stop"
$baseUrl = "https://github.com/tiny-computer/images/releases/download/260808/xfce-en-20260808-202640.tar.zst"
$baseSha256 = "571c3f56f64f068a278303b1abc0e1729de5c6a2272abb3deebb31cae3866b9f"
$hangoverUrl = "https://github.com/AndreRH/hangover/releases/download/hangover-11.16/hangover_11.16_debian13_trixie_arm64.tar"
$hangoverSha256 = "b5493f5903ab3c05f78bf4c03b06ac0005eb26f732437748c1592fefa45e861a"
$packageIndexUrl = "https://deb.debian.org/debian/dists/trixie/main/binary-arm64/Packages.xz"
$geProtonUrl = "https://github.com/GloriousEggroll/proton-ge-custom/releases/download/GE-Proton11-6/GE-Proton11-6-aarch64.tar.gz"
$geProtonSha512 = "c539b1c3b4fe6132fa3a2bce274926e41f0ea77a9bbc9aadb78878b840f6ab32d690a3e2b89f00ac864678c528cee3abf99e7ac222277f33403cf27834626f3b"
$steamRt4Url = "https://repo.steampowered.com/steamrt4/images/4.0.20260805.254769/SteamLinuxRuntime_4-arm64.tar.xz"
$steamRt4Sha256 = "caa4b3bc3aad1cac43d94dbd802a963c13ed63ea1c414f04669ae402af505adf"
$winetricksUrl = "https://raw.githubusercontent.com/Winetricks/winetricks/20260125/src/winetricks"
$winetricksSha256 = "431f82fc74000e6c864409f1d8fb495d696c03928808e3e8acffc45179312a7b"
$winePrefixTemplatesSha256 = "d69b2703bf9b6fcc4bb1e5a8b3809c4e750b915686d5ecc820b365371c9364a4"

$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) { $python = Get-Command python3 -ErrorAction SilentlyContinue }
if (-not $python) { throw "Python 3 is required." }

$sourceParent = Split-Path -Parent $SourceArchive
$payloadParent = Split-Path -Parent $SteamPayload
$outputParent = Split-Path -Parent $Output
New-Item -ItemType Directory -Force -Path $sourceParent, $payloadParent, $PackageCache, $outputParent, (Split-Path -Parent $HangoverBundle), (Split-Path -Parent $DebianPackageIndex), $DebianPackageCache, (Split-Path -Parent $GeProtonArchive), (Split-Path -Parent $SteamRt4Archive), (Split-Path -Parent $Winetricks) | Out-Null

if (-not (Test-Path -LiteralPath $SourceArchive)) {
    Write-Host "Downloading the official Tiny Container XFCE base..."
    & curl.exe --fail --location --retry 3 $baseUrl --output $SourceArchive
    if ($LASTEXITCODE -ne 0) { throw "Tiny Container base download failed." }
}

$actualSha256 = (Get-FileHash -LiteralPath $SourceArchive -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actualSha256 -ne $baseSha256) {
    throw "Base image checksum mismatch. Expected $baseSha256, got $actualSha256."
}
Write-Host "Verified official Tiny Container base SHA256: $actualSha256"

if (-not (Test-Path -LiteralPath $HangoverBundle)) {
    Write-Host "Downloading Hangover 11.16 for Debian 13 ARM64..."
    & curl.exe --fail --location --retry 3 $hangoverUrl --output $HangoverBundle
    if ($LASTEXITCODE -ne 0) { throw "Hangover download failed." }
}
$actualHangoverSha256 = (Get-FileHash -LiteralPath $HangoverBundle -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actualHangoverSha256 -ne $hangoverSha256) {
    throw "Hangover checksum mismatch. Expected $hangoverSha256, got $actualHangoverSha256."
}
Write-Host "Verified Hangover SHA256: $actualHangoverSha256"

if (-not (Test-Path -LiteralPath $DebianPackageIndex)) {
    Write-Host "Downloading the Debian 13 ARM64 package index..."
    & curl.exe --fail --location --retry 3 $packageIndexUrl --output $DebianPackageIndex
    if ($LASTEXITCODE -ne 0) { throw "Debian package index download failed." }
}

if (-not (Test-Path -LiteralPath $GeProtonArchive)) {
    Write-Host "Downloading GE-Proton11-6 AArch64..."
    & curl.exe --fail --location --retry 3 $geProtonUrl --output $GeProtonArchive
    if ($LASTEXITCODE -ne 0) { throw "GE-Proton download failed." }
}
$actualGeProtonSha512 = (Get-FileHash -LiteralPath $GeProtonArchive -Algorithm SHA512).Hash.ToLowerInvariant()
if ($actualGeProtonSha512 -ne $geProtonSha512) {
    throw "GE-Proton checksum mismatch. Expected $geProtonSha512, got $actualGeProtonSha512."
}
Write-Host "Verified GE-Proton SHA512: $actualGeProtonSha512"

if (-not (Test-Path -LiteralPath $SteamRt4Archive)) {
    Write-Host "Downloading Valve Steam Linux Runtime 4 ARM64..."
    & curl.exe --fail --location --retry 3 $steamRt4Url --output $SteamRt4Archive
    if ($LASTEXITCODE -ne 0) { throw "Steam Runtime 4 download failed." }
}
$actualSteamRt4Sha256 = (Get-FileHash -LiteralPath $SteamRt4Archive -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actualSteamRt4Sha256 -ne $steamRt4Sha256) {
    throw "Steam Runtime 4 checksum mismatch. Expected $steamRt4Sha256, got $actualSteamRt4Sha256."
}
Write-Host "Verified Steam Runtime 4 SHA256: $actualSteamRt4Sha256"

if (-not (Test-Path -LiteralPath $Winetricks)) {
    Write-Host "Downloading Winetricks 20260125..."
    & curl.exe --fail --location --retry 3 $winetricksUrl --output $Winetricks
    if ($LASTEXITCODE -ne 0) { throw "Winetricks download failed." }
}
$actualWinetricksSha256 = (Get-FileHash -LiteralPath $Winetricks -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actualWinetricksSha256 -ne $winetricksSha256) {
    throw "Winetricks checksum mismatch. Expected $winetricksSha256, got $actualWinetricksSha256."
}
Write-Host "Verified Winetricks SHA256: $actualWinetricksSha256"

if (-not (Test-Path -LiteralPath $WinePrefixTemplatesArchive)) {
    throw "Offline Wine prefix templates are missing: $WinePrefixTemplatesArchive"
}
$actualWinePrefixTemplatesSha256 = (Get-FileHash -LiteralPath $WinePrefixTemplatesArchive -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actualWinePrefixTemplatesSha256 -ne $winePrefixTemplatesSha256) {
    throw "Wine prefix template checksum mismatch. Expected $winePrefixTemplatesSha256, got $actualWinePrefixTemplatesSha256."
}
Write-Host "Verified offline Wine prefix templates SHA256: $actualWinePrefixTemplatesSha256"

& $python.Source (Join-Path $PSScriptRoot "tools/prepare_hangover_layer.py") `
    --base $SourceArchive `
    --bundle $HangoverBundle `
    --bundle-sha256 $hangoverSha256 `
    --package-index $DebianPackageIndex `
    --package-cache $DebianPackageCache `
    --output $HangoverLayer
if ($LASTEXITCODE -ne 0) { throw "Preinstalled Hangover layer preparation failed." }

& $python.Source (Join-Path $PSScriptRoot "tools/prepare_pinned_steam_arm64.py") `
    --lock (Join-Path $PSScriptRoot "steam-arm64-1785799196-packages.json") `
    --output $SteamPayload `
    --package-cache $PackageCache `
    --jobs $Jobs
if ($LASTEXITCODE -ne 0) { throw "Steam ARM64 preparation failed." }

& $python.Source (Join-Path $PSScriptRoot "tools/build_steam_rootfs.py") `
    --source $SourceArchive `
    --overlay (Join-Path $PSScriptRoot "steam-overlay") `
    --winetricks $Winetricks `
    --steam-payload $SteamPayload `
    --hangover-layer $HangoverLayer `
    --ge-proton-archive $GeProtonArchive `
    --steamrt4-archive $SteamRt4Archive `
    --wine-prefix-templates-archive $WinePrefixTemplatesArchive `
    --output $Output
if ($LASTEXITCODE -ne 0) { throw "Steam-ready rootfs build failed." }

& $python.Source (Join-Path $PSScriptRoot "tools/verify_steam_rootfs.py") --archive $Output
if ($LASTEXITCODE -ne 0) { throw "Steam-ready rootfs verification failed." }

Get-Item -LiteralPath $Output, "$Output.sha256" | Select-Object FullName, Length, LastWriteTime
