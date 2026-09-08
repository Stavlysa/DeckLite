#!/usr/bin/env bash
set -Eeuo pipefail

[[ -r /etc/profile.d/decklite-game-performance.sh ]] && \
    source /etc/profile.d/decklite-game-performance.sh

# The extra Mesa GL submission thread corrupts Steam CEF's layered Library
# view on the tested Zink/Turnip path. Off/on/off testing reproduces the
# disappearing controls with it enabled. This keeps GPU rendering enabled;
# it only removes the additional GL command queue (also inherited by Proton).
export mesa_glthread="${DECKLITE_STEAM_GLTHREAD:-false}"

stable_root="$HOME/.local/share/Steam"
update_state="$HOME/.local/share/decklite-steam"
proton_defaults_marker="$update_state/proton-defaults-v1"
if [[ -n "${STEAM_ROOT:-}" ]]; then
    steam_root="$STEAM_ROOT"
elif [[ -f "$update_state/active-root" ]]; then
    steam_root="$(head -n 1 "$update_state/active-root")"
    if [[ "$steam_root" != "$update_state/candidate" ]]; then
        echo "Ignoring an invalid Steam active-root selection: $steam_root" >&2
        steam_root="$stable_root"
    fi
else
    steam_root="$stable_root"
fi
log_file="$HOME/steam-arm64.log"
compat_shim="/opt/tiny/steam-arm64/libtgcompat-robust.so"
mmap_shim="/opt/tiny/extra/libmmap_shim.so"
affinity_shim="/opt/tiny/extra/libdecklite-affinity.so"

# A launcher invoked from an SSH shell does not inherit Xfce's session bus.
# Reuse the active desktop environment when possible so Steam sees the same
# D-Bus and runtime directory as a launcher started from the desktop icon.
inherit_xfce_session() {
    local session_pid session_env value variable

    if [[ -n "${DBUS_SESSION_BUS_ADDRESS:-}" && -n "${XDG_RUNTIME_DIR:-}" &&
          -n "${DISPLAY:-}" && -n "${LANG:-}" ]]; then
        return
    fi
    # PRoot virtualises uid/gid for userspace, while procfs still exposes the
    # Android app uid. Filtering pgrep by `id -u` therefore hides the session.
    session_pid="$(pgrep -n xfce4-session 2>/dev/null || true)"
    [[ -n "$session_pid" && -r "/proc/$session_pid/environ" ]] || return 0
    session_env="$(tr '\0' '\n' <"/proc/$session_pid/environ")"
    for variable in DISPLAY DBUS_SESSION_BUS_ADDRESS XDG_RUNTIME_DIR LANG; do
        if [[ -z "${!variable:-}" ]]; then
            value="$(sed -n "s/^${variable}=//p" <<<"$session_env" | head -n 1)"
            [[ -n "$value" ]] && export "$variable=$value"
        fi
    done
    return 0
}

inherit_xfce_session
# Minimal SSH environments otherwise reach XOpenIM with LANG=(null).
export LANG="${LANG:-C.UTF-8}"

mkdir -p "$(dirname "$log_file")"
exec > >(tee -a "$log_file") 2>&1

notify_failure() {
    local status="${1:-1}"
    local message="Steam ARM64 stopped with exit code $status. Open $log_file for details."
    echo "$message" >&2
    if command -v notify-send >/dev/null 2>&1 && [[ -n "${DISPLAY:-}" ]]; then
        notify-send --urgency=critical "Steam ARM64 failed to start" "$message" || true
    fi
}

on_error() {
    local status=$?
    trap - ERR
    notify_failure "$status"
    exit "$status"
}
trap on_error ERR

if [[ ! -f "$steam_root/steam.sh" ]]; then
    echo "Steam ARM64 payload is missing: $steam_root" >&2
    echo "Use 'Rollback to tested Steam' or stage a separate update candidate." >&2
    exit 1
fi

ge_proton_root="$stable_root/compatibilitytools.d/GE-Proton11-6-aarch64"
if [[ -f "$ge_proton_root/compatibilitytool.vdf" ]]; then
    # Steam Runtime's bubblewrap cannot create namespaces inside Android
    # PRoot. Run the AArch64 Proton payload directly and make its advisory
    # procfs limit check tolerate Android's intentionally unreadable sysctls.
    python3 /opt/tiny/steam-arm64/patch-ge-proton.py --tool-root "$ge_proton_root"
fi

# Windows titles use the bundled AArch64 GE-Proton by default.  Counter-Strike
# and Half-Life also need an explicit mapping because Steam otherwise prefers
# their unusable x86 Linux depots on an AArch64 host.  Apply this only once so
# later choices made in Steam's per-game Compatibility panel remain intact.
if [[ ! -e "$proton_defaults_marker" && \
      -f "$stable_root/compatibilitytools.d/GE-Proton11-6-aarch64/compatibilitytool.vdf" ]]; then
    mkdir -p "$update_state"
    if python3 /opt/tiny/steam-arm64/configure-proton.py \
            --steam-root "$stable_root" --global-default --appid 10 --appid 70; then
        touch "$proton_defaults_marker"
    else
        echo "Warning: could not install DeckLite's initial Proton mappings." >&2
    fi
fi

mkdir -p "$HOME/.steam" "$steam_root/package"
ln -sfn "$steam_root" "$HOME/.steam/steam"
ln -sfn "$steam_root" "$HOME/.steam/root"
ln -sfn "$steam_root/linuxarm64" "$HOME/.steam/sdkarm64"

runtime="$steam_root/steamrt64"
runtime_backup="$steam_root/steamrt64-x86-backup"
arm_client="$steam_root/steamrtarm64"
webhelper_wrapper="$arm_client/steamwebhelper.sh"

if [[ ! -x "$arm_client/steam" ]]; then
    echo "Native ARM64 Steam client is missing: $arm_client/steam" >&2
    exit 1
fi
if [[ ! -f "$compat_shim" ]]; then
    echo "Steam Android robust-list shim is missing: $compat_shim" >&2
    exit 1
fi
if [[ ! -f "$mmap_shim" ]]; then
    echo "Android executable-mapping shim is missing: $mmap_shim" >&2
    exit 1
fi
if [[ ! -f "$affinity_shim" ]]; then
    echo "Android heterogeneous-CPU affinity shim is missing: $affinity_shim" >&2
    exit 1
fi

# Valve's experimental ARM64 client expects steamrt64 to resolve to
# steamrtarm64 and looks up its native Steam API through ~/.steam/sdkarm64.
# Launching it through the legacy steam.sh wrapper incorrectly selects
# ubuntu12_32 and produces the misleading "missing a 32-bit dependency"
# error on ARM64-only systems.
if [[ -L "$runtime" ]]; then
    rm -f "$runtime"
fi
if [[ -d "$runtime" && ! -d "$runtime_backup" ]]; then
    mv "$runtime" "$runtime_backup"
fi
if [[ -d "$runtime" ]]; then
    # A previous DeckLite hybrid directory is fully reproducible. Preserve
    # Valve's original runtime in runtime_backup and replace only the hybrid.
    rm -rf -- "$runtime"
fi
ln -sfn steamrtarm64 "$runtime"

if [[ ! -x "$runtime/steam" || ! -e "$HOME/.steam/sdkarm64/steamclient.so" ]]; then
    echo "ARM64 Steam compatibility layout could not be created." >&2
    exit 1
fi
touch "$steam_root/.steam-enable-steamrt64-client"

for executable in \
    steam.sh \
    steamrtarm64/steam \
    steamrtarm64/steamwebhelper \
    steamrtarm64/steamwebhelper.sh \
    steamrtarm64/gldriverquery \
    steamrtarm64/vulkandriverquery \
    steamrtarm64/steamsysinfo; do
    [[ -e "$steam_root/$executable" ]] && chmod 0755 "$steam_root/$executable"
done

# Android applications do not get a conventional /dev/shm.  Chromium exits
# before drawing Steam's sign-in window unless the ARM64 webhelper is told to
# keep its shared files in TMPDIR.  Termux:X11 also does not expose
# GLX_OML_sync_control/XFree86-VidMode; letting ANGLE query it once per frame
# makes Steam's GPU-composited library view flicker.  Disable only that ANGLE
# feature. Layered Library content remains intermittently corrupted on the
# tested Turnip stack, even with GL threading off and synchronous Zink draws.
# Use CEF's software compositor; do not disable GPU rendering for games or
# add expensive Zink debug flags to Steam's inherited Wine/Proton environment.
# Known updated wrappers are patched on every launch; unknown formats fail
# without modification. No game-specific executable or shortcut is needed.
python3 /opt/tiny/steam-arm64/patch-steam-webhelper.py --wrapper "$webhelper_wrapper"

# Valve's current Linux ARM64 beta UI calls three network bridge methods which
# its ARM64 backend does not export. Guard those optional calls before CEF
# loads; without this, login succeeds but the main window spins forever.
python3 /opt/tiny/steam-arm64/patch-steam-ui.py --steam-root "$steam_root"

export STEAM_DISABLE_BROWSER_SANDBOX=1
export SDL_VIDEODRIVER=x11
export MESA_SHADER_CACHE_DIR="${MESA_SHADER_CACHE_DIR:-$HOME/.cache/mesa_shader_cache}"
export MESA_SHADER_CACHE_MAX_SIZE="${MESA_SHADER_CACHE_MAX_SIZE:-1G}"
export LD_LIBRARY_PATH="$steam_root/steamrtarm64${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export TGCOMPAT_ROBUST_LIST=1
export TGCOMPAT_FLOCK_FCNTL=1
# Xalia's accessibility helper creates a futex failure under Android PRoot and
# can deadlock Steam's Windows install-script evaluator.  It is not required
# for keyboard, mouse, gamepad, or the X11 desktop itself.
export PROTON_USE_XALIA=0
# The ARM64 beta client concatenates its x86 overlay path with an inherited
# LD_PRELOAD entry.  Besides being unusable for AArch64 Proton, that drops the
# executable-mapping shim and makes Wine report a misleading "noexec
# filesystem" error.  Disable the overlay for Windows games and pass both
# Android compatibility shims explicitly.
export SUPPRESS_STEAM_OVERLAY=1
export DECKLITE_REMAP_CPU0="${DECKLITE_REMAP_CPU0:-1}"
source /opt/tiny/wine-manager/wine-affinity-env.sh
export LD_PRELOAD="$compat_shim:$mmap_shim:$affinity_shim"

cd "$steam_root"
mkdir -p "$MESA_SHADER_CACHE_DIR"
echo "Steam ARM64 log: $log_file"
trap - ERR
set +e
steam_args=(
    -inhibitbootstrap
    -nobootstrapperupdate
    -noverifyfiles
    -no-cef-sandbox
    -cef-force-gpu
    -chromeosnopreallocate
)
if [[ "${STEAM_CEF_SOFTWARE:-0}" == "1" ]]; then
    steam_args+=( -cef-disable-gpu )
fi
# Steam CEF declares its main window borderless and, on this X11 stack, its
# custom title area is not draggable.  Put only the first launch into a sane,
# movable size; later starts preserve the user's chosen geometry.  The desktop
# Window Controls utility can reset it again at any time.
/opt/tiny/steam-arm64/steam-window-helper.sh --watch >/dev/null 2>&1 &
/opt/tiny/steam-arm64/steam_tray.py >/dev/null 2>&1 &
tray_pid=$!
"$arm_client/steam" "${steam_args[@]}" "$@"
status=$?
kill "$tray_pid" 2>/dev/null || true
set -e
if (( status != 0 )); then
    notify_failure "$status"
fi
exit "$status"
