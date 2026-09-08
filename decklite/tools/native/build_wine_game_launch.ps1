param(
    [Parameter(Mandatory=$true)][string]$LlvmBin,
    [string]$OutputDirectory = (Join-Path $PSScriptRoot '../../build/native')
)
$ErrorActionPreference = 'Stop'
New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null
Push-Location $OutputDirectory
try {
    & "$LlvmBin/clang.exe" --target=aarch64-pc-windows-msvc -c -O2 -Wall -Wextra -Werror -fno-builtin -fno-stack-protector (Join-Path $PSScriptRoot 'wine-display-launch.c') -o wine-game-launch.obj
    if ($LASTEXITCODE) { throw 'Compile failed' }
    & "$LlvmBin/llvm-dlltool.exe" -m arm64 -d (Join-Path $PSScriptRoot 'game-launch-kernel32.def') -l game-launch-kernel32.lib
    if ($LASTEXITCODE) { throw 'Kernel imports failed' }
    & "$LlvmBin/llvm-dlltool.exe" -m arm64 -d (Join-Path $PSScriptRoot 'game-launch-user32.def') -l game-launch-user32.lib
    if ($LASTEXITCODE) { throw 'User imports failed' }
    & "$LlvmBin/ld.lld.exe" -flavor link /entry:mainCRTStartup /subsystem:windows /nodefaultlib /machine:arm64 /timestamp:0 /out:wine-game-launch.exe wine-game-launch.obj game-launch-kernel32.lib game-launch-user32.lib
    if ($LASTEXITCODE) { throw 'Link failed' }
} finally { Pop-Location }
