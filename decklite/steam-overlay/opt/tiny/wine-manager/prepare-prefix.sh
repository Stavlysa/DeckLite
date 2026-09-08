#!/usr/bin/env bash
set -Eeuo pipefail

[[ -r /etc/profile.d/decklite-game-performance.sh ]] && \
    source /etc/profile.d/decklite-game-performance.sh
source /opt/tiny/wine-manager/wine-affinity-env.sh
source /opt/tiny/wine-manager/wine-region-env.sh

prefix="${1:-${WINEPREFIX:-$HOME/.wine}}"
export WINEPREFIX="$prefix"
export HODLL64="${HODLL64:-libarm64ecfex.dll}"
export HODLL="${HODLL:-libwow64fex.dll}"
template_root=/opt/tiny/wine-manager/prefix-templates

mkdir -p "$(dirname -- "$prefix")"
exec 9>"${prefix}.decklite-init.lock"
flock 9

mmap_shim=/opt/tiny/extra/libmmap_shim.so
if [[ -f "$mmap_shim" && ":${LD_PRELOAD:-}:" != *":$mmap_shim:"* ]]; then
    export LD_PRELOAD="$mmap_shim${LD_PRELOAD:+:$LD_PRELOAD}"
fi

if [[ ! -f "$prefix/system.reg" ]]; then
    requested_template="${DECKLITE_WINE_TEMPLATE:-}"
    request_file="$prefix/.decklite-template-request"
    if [[ -z "$requested_template" && -f "$request_file" ]]; then
        requested_template="$(head -n 1 "$request_file")"
    fi
    requested_template="${requested_template:-game-complete}"
    case "$requested_template" in
        game-complete|dotnet-xna-complete)
            if [[ -f "$template_root/$requested_template/system.reg" ]]; then
                echo "Cloning offline Wine template '$requested_template' into $prefix"
                mkdir -p "$prefix"
                cp -a --reflink=auto "$template_root/$requested_template/." "$prefix/"
                printf '%s\n' "$requested_template" >"$prefix/.decklite-template"
            else
                echo "Offline template '$requested_template' is unavailable; creating a clean prefix." >&2
                mkdir -p "$prefix"
            fi
            ;;
        clean)
            echo "Initializing a clean Hangover Wine prefix: $prefix"
            mkdir -p "$prefix"
            ;;
        *)
            echo "Unknown Wine template: $requested_template" >&2
            exit 2
            ;;
    esac
    rm -f "$request_file"
    # wineboot refreshes relocated user paths and recreates device links. This
    # is entirely offline; redistributables are already present in the clone.
    WINEDEBUG="${WINEDEBUG:--all}" wineboot --update 9>&-
fi

if [[ ! -f "$prefix/.decklite-dxvk-staged" ]]; then
    /opt/tiny/wine-manager/install-dxvk.sh "$prefix" stage 9>&-
fi

# Black letterboxing uses Wine's existing desktop, not input-stealing overlay
# windows. Apply the default once; later user colour changes are respected.
if [[ ! -f "$prefix/.decklite-black-desktop" ]]; then
    if wine regedit /S 'Z:\opt\tiny\wine-manager\black-desktop.reg' 9>&- >/dev/null 2>&1; then
        touch "$prefix/.decklite-black-desktop"
    fi
fi

if [[ ! -f "$prefix/.decklite-fonts-fixed" && -f /opt/tiny/extra/chn_fonts.reg ]]; then
    regedit 'Z:\opt\tiny\extra\chn_fonts.reg' 9>&- >/dev/null 2>&1 || true
    wine reg delete 'HKEY_LOCAL_MACHINE\Software\Microsoft\Windows NT\CurrentVersion\FontSubstitutes' /va /f 9>&- >/dev/null 2>&1 || true
    touch "$prefix/.decklite-fonts-fixed"
fi
