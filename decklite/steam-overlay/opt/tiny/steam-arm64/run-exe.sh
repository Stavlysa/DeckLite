#!/usr/bin/env bash
set -Eeuo pipefail

[[ -r /etc/profile.d/decklite-game-performance.sh ]] && \
    source /etc/profile.d/decklite-game-performance.sh

if ! command -v wine >/dev/null 2>&1; then
    echo "Hangover is not installed. In Tiny Container Quick Commands:" >&2
    echo "1. Enable Options > Miscellaneous > Hangover configuration and restart." >&2
    echo "2. Run 'Install Hangover'." >&2
    exit 1
fi

if [[ $# -eq 0 ]]; then
    echo "Usage: run-exe /path/to/program.exe [arguments...]" >&2
    exit 2
fi

case "${1,,}" in
    *.exe) ;;
    *) echo "Warning: '$1' does not end in .exe; trying it anyway." >&2 ;;
esac

# Many older Windows games (including Touhou) load music archives relative to
# the process working directory instead of the executable path. Always launch
# from the EXE's own directory so files such as thbgm.dat remain discoverable.
program="$1"
shift
if [[ "$program" != /* ]]; then
    program="$(realpath -m -- "$program")"
fi
program_directory="$(dirname -- "$program")"
program_name="$(basename -- "$program")"
cd "$program_directory"

export WINEDEBUG="${WINEDEBUG:--all}"
export HODLL64="${HODLL64:-libarm64ecfex.dll}"
# Wine's older OpenGL clients can fall onto a half-refresh cadence when Mesa's
# threaded GL queue and swap throttling interact through PRoot + Termux-X11.
# DXVK/Vulkan does not use these GL switches.  Compatibility-first Wine
# defaults therefore keep GL submission synchronous and let the game control
# its own frame limiter.  Both remain explicitly overridable for diagnostics.
export mesa_glthread="${DECKLITE_WINE_GLTHREAD:-false}"
export vblank_mode="${DECKLITE_WINE_VBLANK_MODE:-0}"
export MESA_VK_WSI_PRESENT_MODE="${DECKLITE_WINE_PRESENT_MODE:-immediate}"
export __GL_SYNC_TO_VBLANK="${DECKLITE_WINE_VSYNC:-0}"
# Keep one low-latency, unsynchronized DXVK profile for every D3D9 game.
# The Turnip checkerboard workaround is in the shared performance profile.
export DXVK_CONFIG_FILE="${DXVK_CONFIG_FILE:-/opt/tiny/steam-arm64/dxvk-game.conf}"
case "${DECKLITE_WINE_BACKEND:-auto}" in
    # Hangover does not consistently select a 32-bit translator when invoked
    # through PRoot.  FEX is the compatibility-first default; Box64 remains a
    # user-selectable alternative in Wine Manager.
    auto) export HODLL="${HODLL:-libwow64fex.dll}" ;;
    box64) export HODLL=wowbox64.dll ;;
    fex) export HODLL=libwow64fex.dll ;;
    *) echo "Unknown DECKLITE_WINE_BACKEND: $DECKLITE_WINE_BACKEND" >&2; exit 2 ;;
esac

# Android shared storage (Downloads, Documents and SD cards) rejects
# file-backed PROT_EXEC mappings.  Hangover needs to map PE sections as
# executable, so keep Tiny's copy-on-write mprotect shim active even when the
# launcher was entered through SSH or another sanitized environment.
mmap_shim=/opt/tiny/extra/libmmap_shim.so
if [[ -f "$mmap_shim" && ":${LD_PRELOAD:-}:" != *":$mmap_shim:"* ]]; then
    export LD_PRELOAD="$mmap_shim${LD_PRELOAD:+:$LD_PRELOAD}"
fi

# Several older Windows engines pin their render thread to logical CPU 0.
# Android ARM devices commonly place CPU 0 in the slow efficiency cluster,
# turning a GPU-accelerated game into a CPU-bound 30 FPS workload.  This small
# native shim uses all permitted big/prime cores by default, including the
# persistent wineserver and new game threads. It does not force CPU 7 or
# change Android's cpuset/thermal controls. Set DECKLITE_WINE_CPU_POLICY=all
# for all allowed cores, or DECKLITE_REMAP_CPU0=0 to disable the policy.
affinity_shim=/opt/tiny/extra/libdecklite-affinity.so
export DECKLITE_REMAP_CPU0="${DECKLITE_REMAP_CPU0:-1}"
source /opt/tiny/wine-manager/wine-affinity-env.sh
if [[ -f "$affinity_shim" && ":${LD_PRELOAD:-}:" != *":$affinity_shim:"* ]]; then
    export LD_PRELOAD="$affinity_shim${LD_PRELOAD:+:$LD_PRELOAD}"
fi
prefix="${WINEPREFIX:-$HOME/.wine}"

# Share Windows language + fixed UTC offset with MSI/tools/initialization.
source /opt/tiny/wine-manager/wine-region-env.sh

# Old DirectDraw/D3D games commonly change the physical X11 mode when their
# fullscreen option is enabled.  Under Android + Termux-X11 that mode switch
# can leave a permanently black surface.  Keep it inside a Wine virtual
# desktop: the game still sees a fullscreen-capable display, while the real
# X11 output never changes mode. Automatic mode presents actual fullscreen
# windows with the matching APK GPU viewport; windowed games keep their frame.
# Safe and native modes remain explicit rollback choices in Wine Manager.
# Wine Manager stores one global choice for every EXE launcher.  Keep the file
# deliberately data-only (one allow-listed word) instead of sourcing shell
# code from the user's home directory.
display_mode="${DECKLITE_WINE_DISPLAY_MODE:-}"
if [[ -z "$display_mode" ]]; then
    display_mode_file="${XDG_CONFIG_HOME:-$HOME/.config}/decklite/wine-display-mode"
    if [[ -r "$display_mode_file" ]]; then
        IFS= read -r display_mode <"$display_mode_file" || true
    fi
fi
display_mode="${display_mode:-auto}"
case "$display_mode" in
    safe|borderless|auto)
        # Only the legacy forced-borderless mode inherits a resize request.
        unset DECKLITE_WINE_FIT_SIZE
        desktop_size="${DECKLITE_WINE_DESKTOP_SIZE:-}"
        if [[ -z "$desktop_size" ]] && command -v xdotool >/dev/null 2>&1; then
            read -r display_width display_height < <(xdotool getdisplaygeometry 2>/dev/null || true)
            if [[ "${display_width:-}" =~ ^[0-9]+$ && "${display_height:-}" =~ ^[0-9]+$ ]]; then
                # Leave room for XFCE's top panel and the virtual desktop's
                # title bar so its move/close controls remain reachable.
                if [[ "$display_mode" == safe ]] && (( display_height > 120 )); then
                    display_height=$((display_height - 36))
                fi
                desktop_size="${display_width}x${display_height}"
            fi
        fi
        desktop_size="${desktop_size:-1280x720}"
        if [[ ! "$desktop_size" =~ ^[0-9]{3,5}x[0-9]{3,5}$ ]]; then
            echo "Invalid DECKLITE_WINE_DESKTOP_SIZE: $desktop_size" >&2
            exit 2
        fi
        echo "DeckLite safe fullscreen: Wine virtual desktop $desktop_size" >&2
        if [[ "$display_mode" == auto ]]; then
            python3 /opt/tiny/wine-manager/auto-display-x11.py >/tmp/decklite-auto-display.log 2>&1 &
        fi
        if [[ "$display_mode" == borderless ]]; then
            export DECKLITE_WINE_FIT_SIZE="$desktop_size"
            echo "DeckLite borderless scaling: choose Windowed in the game's own settings." >&2
            python3 /opt/tiny/wine-manager/borderless-x11.py \
                --desktop "DeckLite-$$" --size "$desktop_size" --launcher "$$" &
        fi
        # Some older DirectInput games create their window on another thread
        # and leave Wine's desktop foreground NULL. A windowless native ARM64
        # helper repairs only that missing initial foreground, then waits for
        # the game. It never continuously steals focus or changes game files.
        game_command=("$program_name" "$@")
        if [[ ( "${DECKLITE_WINE_STARTUP_FOCUS:-1}" != 0 || "$display_mode" == borderless || "$display_mode" == auto ) && \
              -f /opt/tiny/wine-manager/wine-game-launch.exe ]]; then
            if [[ "$display_mode" == auto ]]; then
                game_command=('Z:\opt\tiny\wine-manager\wine-game-launch.exe' "--decklite-observe=$$" -- "${game_command[@]}")
            elif [[ "$display_mode" == borderless ]]; then
                game_command=('Z:\opt\tiny\wine-manager\wine-game-launch.exe' "--decklite-fit=$desktop_size" -- "${game_command[@]}")
            else
                game_command=('Z:\opt\tiny\wine-manager\wine-game-launch.exe' "${game_command[@]}")
            fi
        fi
        exec /opt/tiny/wine-manager/wine-prefix-run \
            "$prefix" wine explorer "/desktop=DeckLite-$$,$desktop_size" "${game_command[@]}"
        ;;
    native)
        unset DECKLITE_WINE_FIT_SIZE
        exec /opt/tiny/wine-manager/wine-prefix-run "$prefix" wine "$program_name" "$@"
        ;;
    *)
        echo "Unknown DECKLITE_WINE_DISPLAY_MODE: $display_mode" >&2
        exit 2
        ;;
esac
