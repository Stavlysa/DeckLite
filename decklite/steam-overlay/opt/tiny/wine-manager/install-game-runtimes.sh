#!/usr/bin/env bash
set -Eeuo pipefail
source /opt/tiny/wine-manager/wine-region-env.sh

[[ -r /etc/profile.d/decklite-game-performance.sh ]] && \
    source /etc/profile.d/decklite-game-performance.sh

if [[ $# -ne 2 ]]; then
    echo "Usage: install-game-runtimes.sh PREFIX common|legacy-media|dotnet-xna" >&2
    exit 2
fi

prefix="$1"
profile="$2"
export WINEPREFIX="$prefix"
export HODLL64="${HODLL64:-libarm64ecfex.dll}"
export HODLL="${HODLL:-libwow64fex.dll}"
mmap_shim=/opt/tiny/extra/libmmap_shim.so
if [[ -f "$mmap_shim" && ":${LD_PRELOAD:-}:" != *":$mmap_shim:"* ]]; then
    export LD_PRELOAD="$mmap_shim${LD_PRELOAD:+:$LD_PRELOAD}"
fi
winetricks=/usr/local/bin/winetricks
winetricks_flags=(-q)
install_quartz=false
repair_dotnet_mscoree=false

if [[ ! -x "$winetricks" ]]; then
    echo "The pinned Winetricks installer is missing: $winetricks" >&2
    exit 1
fi

case "$profile" in
    common)
        # Visual C++ 2005-2022, legacy D3D helper DLLs, XInput/XAudio and fonts.
        verbs=(
            corefonts
            vcrun2005 vcrun2008 vcrun2010 vcrun2012 vcrun2013 vcrun2022
            d3dcompiler_43 d3dcompiler_47 d3dx9 xact xinput
        )
        ;;
    legacy-media)
        # Older Japanese/Windows games often use DirectMusic, DirectShow or quartz.
        # Winetricks marks its Win7 quartz and DirectX devenum verbs as
        # conflicting even though old titles can require both COM providers.
        # Install this deliberately tested pair together rather than leaving
        # the profile half-complete at the conflict guard.
        winetricks_flags+=(--force)
        verbs=(amstream devenum directmusic directplay dsound)
        install_quartz=true
        ;;
    dotnet-xna)
        # Kept separate because .NET/XNA can conflict with older game prefixes.
        verbs=(dotnet48 xna40)
        repair_dotnet_mscoree=true
        ;;
    *)
        echo "Unknown game runtime profile: $profile" >&2
        exit 2
        ;;
esac

mkdir -p "$prefix"
echo "Installing game runtime profile '$profile' into $prefix"
echo "The imported complete templates already contain these runtimes."
echo "Installing into a clean/custom prefix may download files from upstream sources."
WINEDEBUG="${WINEDEBUG:--all}" "$winetricks" "${winetricks_flags[@]}" "${verbs[@]}"
if [[ "$install_quartz" == true ]]; then
    if WINEDEBUG="${WINEDEBUG:--all}" "$winetricks" -q --force quartz; then
        :
    elif [[ -s "$prefix/drive_c/windows/syswow64/quartz.dll" ]]; then
        # Hangover 11.16 registers the 32-bit DirectShow provider successfully
        # but its ARM64EC regsvr32 can reject Microsoft's x64 quartz DLL. Keep
        # Wine's built-in 64-bit fallback and record the limitation; the x86
        # provider required by Touhou-class games is installed and registered.
        echo "Warning: native x86 quartz is ready; x64 uses Wine's built-in quartz fallback." >&2
        touch "$prefix/.decklite-runtime-warning-quartz64"
    else
        echo "The 32-bit quartz runtime was not installed." >&2
        exit 1
    fi
fi
if [[ "$repair_dotnet_mscoree" == true ]]; then
    # Windows normally supplies mscoree.dll as an OS component, so Microsoft's
    # redistributable does not restore the Wine copy removed by Winetricks.
    # Hangover then reports a successful .NET install but cannot start any IL
    # executable. Extract Microsoft's matching x86/x64 loaders from the cached
    # Windows 7 SP1 packages and keep the native override selected.
    win7_cache="${XDG_CACHE_HOME:-$HOME/.cache}/winetricks/win7sp1"
    win7_x86="$win7_cache/windows6.1-KB976932-X86.exe"
    win7_x64="$win7_cache/windows6.1-KB976932-X64.exe"
    if [[ ! -s "$win7_x86" || ! -s "$win7_x64" ]]; then
        echo "Winetricks did not provide the Windows 7 SP1 mscoree sources." >&2
        exit 1
    fi
    mscoree_temp="$(mktemp -d "${TMPDIR:-/tmp}/decklite-mscoree.XXXXXX")"
    trap 'rm -rf -- "$mscoree_temp"' EXIT
    mkdir -p "$mscoree_temp/x86" "$mscoree_temp/x64"
    cabextract -q -d "$mscoree_temp/x86" \
        -F 'x86_netfx-mscoree_dll_31bf3856ad364e35_6.2.7601.17514_none_7f96335553371a30/mscoree.dll' \
        "$win7_x86"
    cabextract -q -d "$mscoree_temp/x64" \
        -F 'amd64_netfx-mscoree_dll_31bf3856ad364e35_6.2.7601.17514_none_dbb4ced90b948b66/mscoree.dll' \
        "$win7_x64"
    cp -f "$mscoree_temp/x86"/*/mscoree.dll \
        "$prefix/drive_c/windows/syswow64/mscoree.dll"
    cp -f "$mscoree_temp/x64"/*/mscoree.dll \
        "$prefix/drive_c/windows/system32/mscoree.dll"
    wine reg add 'HKCU\Software\Wine\DllOverrides' \
        /v mscoree /d native /f >/dev/null
    touch "$prefix/.decklite-dotnet-mscoree-repaired"
    rm -rf -- "$mscoree_temp"
    trap - EXIT
fi
touch "$prefix/.decklite-runtimes-$profile"
echo "Installed game runtime profile '$profile'."
