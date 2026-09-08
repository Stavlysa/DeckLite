#!/usr/bin/env bash
set -u

[[ -r /etc/profile.d/00-decklite-glibc-loader.sh ]] && \
    source /etc/profile.d/00-decklite-glibc-loader.sh

mode="${1:-x11}"
state_dir="${HOME:-/home/tiny}/.local/state/decklite"
log_file="$state_dir/desktop.log"
export DISPLAY="${DISPLAY:-:6}"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/tmp/runtime-tiny}"

mkdir -p "$state_dir" "$XDG_RUNTIME_DIR" /tmp/.ICE-unix
chmod 0700 "$XDG_RUNTIME_DIR" 2>/dev/null || true
touch "$log_file"
# Keep essential startup evidence bounded, independently of optional diagnostics.
if [[ $(stat -c %s "$log_file" 2>/dev/null || echo 0) -gt 262144 ]]; then
    tail -c 131072 "$log_file" >"$log_file.rotate"
    mv -f "$log_file.rotate" "$log_file"
fi
# No server, key generation or persistent helper when the APK switch is off.
if [[ -x /opt/tiny/debug/control.py ]]; then
    sudo -n /usr/bin/python3 /opt/tiny/debug/control.py start >>"$log_file" 2>&1 || true
fi

# Android keeps a PRoot process alive independently of an APK reinstall in a
# few edge cases.  A plain pgrep can therefore see daemons owned by an older
# application UID and incorrectly decide that the new container is ready.
host_uid="$(awk '/^Uid:/{print $2; exit}' /proc/self/status 2>/dev/null || true)"

log() {
    printf '%s %s\n' "$(date '+%F %T')" "$*" >>"$log_file"
}

start_dbus() {
    sudo service dbus start >>"$log_file" 2>&1 || true
    if [[ -z "${DBUS_SESSION_BUS_ADDRESS:-}" ]] && command -v dbus-launch >/dev/null 2>&1; then
        local dbus_environment
        dbus_environment="$(dbus-launch --sh-syntax 2>>"$log_file" || true)"
        [[ -n "$dbus_environment" ]] && eval "$dbus_environment"
        export DBUS_SESSION_BUS_ADDRESS DBUS_SESSION_BUS_PID
    fi
}

start_audio() {
    command -v pipewire >/dev/null 2>&1 || return 0
    if ! current_process_ready pipewire; then
        nohup pipewire >>"$log_file" 2>&1 </dev/null &
    fi

    local attempt
    for attempt in {1..50}; do
        [[ -S "$XDG_RUNTIME_DIR/pipewire-0" ]] && break
        sleep 0.1
    done
    if [[ ! -S "$XDG_RUNTIME_DIR/pipewire-0" ]]; then
        log "PipeWire socket was not ready after 5 seconds; continuing without blocking XFCE."
        return 0
    fi

    if command -v wireplumber >/dev/null 2>&1; then
        if ! current_process_ready wireplumber; then
            nohup wireplumber >>"$log_file" 2>&1 </dev/null &
        fi
    fi
    if command -v pipewire-pulse >/dev/null 2>&1; then
        if ! current_process_ready pipewire-pulse; then
            nohup pipewire-pulse >>"$log_file" 2>&1 </dev/null &
        fi
    fi
}

start_vnc() {
    command -v Xtigervnc >/dev/null 2>&1 || {
        log "Xtigervnc is not installed."
        return 1
    }
    rm -f /tmp/.tiny.vnc /tmp/.X6-lock /tmp/.X11-unix/X6
    nohup Xtigervnc \
        -geometry 1440x720 -ZlibLevel=0 -pn -rfbport -1 \
        -SendPrimary=off -SetPrimary=off -FrameRate=120 \
        -rfbunixpath /tmp/.tiny.vnc -alwaysshared -a 5 -once -depth 24 \
        -SecurityTypes=None -desktop "DeckLite Steam ARM64" \
        :6 +extension MIT-SHM >>"$log_file" 2>&1 </dev/null &

    local attempt
    for attempt in {1..100}; do
        [[ -S /tmp/.tiny.vnc ]] && return 0
        sleep 0.1
    done
    log "VNC socket was not ready after 10 seconds."
    return 1
}

current_process_ready() {
    local name="$1" pid state pid_uid
    while IFS= read -r pid; do
        [[ -n "$pid" && -r "/proc/$pid/stat" ]] || continue
        pid_uid="$(awk '/^Uid:/{print $2; exit}' "/proc/$pid/status" 2>/dev/null || true)"
        [[ -z "$host_uid" || "$pid_uid" == "$host_uid" ]] || continue
        state="$(awk '{print $3}' "/proc/$pid/stat" 2>/dev/null || true)"
        [[ -n "$state" && "$state" != Z && "$state" != X ]] && return 0
    done < <(pgrep -x "$name" 2>/dev/null || true)
    return 1
}

wait_for_x_server() {
    local display_number="${DISPLAY##*:}"
    display_number="${display_number%%.*}"
    local socket="/tmp/.X11-unix/X${display_number}"
    # Xlorie creates the pathname socket before its renderer finishes
    # attaching to the Android surface. Active X11 probes can block in the
    # long-lived interactive PRoot even though the same server is healthy for
    # desktop clients. Use the socket only as a passive prerequisite and give
    # the renderer a quiet cold-start window before XFCE connects.
    for _ in {1..50}; do
        [[ -S "$socket" ]] && break
        sleep 0.1
    done
    if [[ ! -S "$socket" ]]; then
        log "X11 socket $socket was not created after 5 seconds."
        return 1
    fi
    sleep 5
    log "X11 socket $socket is present; renderer grace period completed."
    return 0
}

desktop_process_ready() {
    current_process_ready xfce4-session || return 1
    current_process_ready xfwm4 || return 1
    current_process_ready xfdesktop || return 1
}

ensure_dynamic_loader() {
    local attempt
    for attempt in {1..10}; do
        # Refresh unconditionally. Hangover can alter the library set on any
        # boot, so a generic /usr/bin/env probe or a persistent marker can be
        # healthy while XFCE's deeper GTK dependency chain still resolves the
        # libc.so linker script as an ELF shared object.
        log "Refreshing the dynamic loader cache (attempt $attempt)."
        if /sbin/ldconfig >>"$log_file" 2>&1 && \
                LD_TRACE_LOADED_OBJECTS=1 /usr/bin/xfconf-query \
                    >/dev/null 2>&1; then
            return 0
        fi
        sleep 0.5
    done
    # The trace probe can be stricter than actual GTK startup during early
    # post-start initialization. Let startxfce4 run so its real exit status is
    # observed and handled by the outer three-attempt retry loop.
    log "Loader probe is still inconclusive; trying the real XFCE startup."
    return 0
}

start_xfce() {
    command -v startxfce4 >/dev/null 2>&1 || {
        log "startxfce4 is not installed."
        return 1
    }
    desktop_process_ready && return 0

    local launch attempt
    for launch in 1 2 3; do
        ensure_dynamic_loader || {
            sleep 0.5
            continue
        }
        log "Starting XFCE (attempt $launch)."
        nohup startxfce4 >>"$log_file" 2>&1 </dev/null &
        for attempt in {1..50}; do
            desktop_process_ready && {
                # Avoid accepting short-lived processes from a failed startup.
                sleep 1
                if desktop_process_ready; then
                    log "XFCE is ready."
                    return 0
                fi
            }
            sleep 0.1
        done
        log "XFCE attempt $launch exited before the session became ready."
        sleep 0.5
    done
    return 1
}

apply_appearance_defaults() {
    local marker="$state_dir/appearance-defaults-v1"
    local wallpaper=/usr/share/backgrounds/decklite-black.svg
    local attempt property ready=0
    [[ -e "$marker" ]] && return 0

    # Wait briefly for xfconfd.  These are initial defaults only: once the
    # marker exists, later user theme and wallpaper choices are preserved.
    for attempt in {1..50}; do
        if xfconf-query -c xsettings -p /Net/ThemeName \
                -s Fluent-Dark >>"$log_file" 2>&1; then
            ready=1
            break
        fi
        sleep 0.1
    done
    if (( ! ready )); then
        log "XFCE settings were not ready; dark defaults will retry next boot."
        return 0
    fi

    xfconf-query -c xfwm4 -p /general/theme -s Fluent-Dark \
        >>"$log_file" 2>&1 || true
    while IFS= read -r property; do
        [[ "$property" == */last-image || "$property" == */last-single-image ]] || continue
        xfconf-query -c xfce4-desktop -p "$property" -s "$wallpaper" \
            >>"$log_file" 2>&1 || true
    done < <(xfconf-query -c xfce4-desktop -l 2>>"$log_file" || true)

    # New profiles normally contain these monitors; creating both also covers
    # X11 and AVNC before either frontend has generated its own property.
    for property in \
        /backdrop/screen0/monitorbuiltin/workspace0/last-image \
        /backdrop/screen0/monitorVNC-0/workspace0/last-image; do
        xfconf-query -c xfce4-desktop -p "$property" --create -t string \
            -s "$wallpaper" >>"$log_file" 2>&1 || \
        xfconf-query -c xfce4-desktop -p "$property" -s "$wallpaper" \
            >>"$log_file" 2>&1 || true
    done

    if command -v gsettings >/dev/null 2>&1 && \
            gsettings list-schemas 2>/dev/null | \
                grep -Fxq org.gnome.desktop.interface; then
        gsettings set org.gnome.desktop.interface color-scheme prefer-dark \
            >>"$log_file" 2>&1 || true
    fi
    touch "$marker"
    log "Applied the initial Fluent-Dark theme and DeckLite black wallpaper."
}

apply_desktop_icon_defaults() {
    local marker="$state_dir/desktop-icons-defaults-v1"
    local property=/desktop-icons/file-icons/show-removable
    [[ -e "$marker" ]] && return 0

    # Android's shared folders are mounted volumes, not Desktop files.
    # Hide their automatic icons without unmounting or deleting anything.
    # Apply once so later choices in Desktop Settings remain the user's.
    if xfconf-query -c xfce4-desktop -p "$property" -s false \
            >>"$log_file" 2>&1 || \
            xfconf-query -c xfce4-desktop -p "$property" --create -t bool \
                -s false >>"$log_file" 2>&1; then
        touch "$marker"
        log "Hidden automatic mounted-volume desktop icons; folders remain accessible."
    else
        log "Desktop icon defaults could not be applied; will retry next boot."
    fi
}

case "$mode" in
    x11)
        wait_for_x_server || exit 1
        ;;
    avnc)
        start_vnc || exit 1
        wait_for_x_server || exit 1
        ;;
    *)
        printf 'Usage: %s {x11|avnc}\n' "$0" >&2
        exit 2
        ;;
esac

ensure_dynamic_loader || exit 1
start_dbus
start_audio
start_xfce || {
    log "XFCE failed to start after three attempts."
    exit 1
}
apply_appearance_defaults
apply_desktop_icon_defaults
