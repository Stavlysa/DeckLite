#!/usr/bin/env bash
set -Eeuo pipefail
source /opt/tiny/wine-manager/wine-region-env.sh

[[ -r /etc/profile.d/decklite-game-performance.sh ]] && \
    source /etc/profile.d/decklite-game-performance.sh

prefix="${1:-${WINEPREFIX:-$HOME/.wine}}"
action="${2:-enable}"
export WINEPREFIX="$prefix"
export HODLL64="${HODLL64:-libarm64ecfex.dll}"
export HODLL="${HODLL:-libwow64fex.dll}"
mmap_shim=/opt/tiny/extra/libmmap_shim.so
if [[ -f "$mmap_shim" && ":${LD_PRELOAD:-}:" != *":$mmap_shim:"* ]]; then
    export LD_PRELOAD="$mmap_shim${LD_PRELOAD:+:$LD_PRELOAD}"
fi
dxvk_root=/opt/tiny/wine-manager/dxvk

if [[ ! -d "$prefix/drive_c/windows/system32" ]]; then
    echo "Wine prefix is not initialized: $prefix" >&2
    exit 1
fi

mkdir -p "$prefix/drive_c/windows/system32" "$prefix/drive_c/windows/syswow64"
cp -f "$dxvk_root"/arm64ec/*.dll "$prefix/drive_c/windows/system32/"
cp -f "$dxvk_root"/x32/*.dll "$prefix/drive_c/windows/syswow64/"
touch "$prefix/.decklite-dxvk-staged"

case "$action" in
    stage)
        echo "DXVK files staged; builtin WineD3D remains active."
        ;;
    enable)
        for dll in d3d8 d3d9 d3d10core d3d11 dxgi; do
            WINEDLLOVERRIDES="$dll=n,b" wine reg add \
                'HKEY_CURRENT_USER\Software\Wine\DllOverrides' \
                /v "$dll" /d native /f >/dev/null
        done
        touch "$prefix/.decklite-dxvk-enabled"
        echo "DXVK enabled for $prefix"
        ;;
    disable)
        for dll in d3d8 d3d9 d3d10core d3d11 dxgi; do
            wine reg add 'HKEY_CURRENT_USER\Software\Wine\DllOverrides' \
                /v "$dll" /d builtin /f >/dev/null
        done
        rm -f "$prefix/.decklite-dxvk-enabled"
        echo "DXVK disabled; WineD3D enabled for $prefix"
        ;;
    *)
        echo "Unknown action: $action (use stage, enable, or disable)" >&2
        exit 2
        ;;
esac
