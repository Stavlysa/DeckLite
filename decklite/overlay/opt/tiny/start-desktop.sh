#!/usr/bin/env bash
set -Eeuo pipefail

mode="${1:-x11}"
log_file="/tmp/decklite-desktop.log"
export DISPLAY="${DISPLAY:-:6}"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/tmp/runtime-alarm}"

if ! command -v openbox-session >/dev/null 2>&1; then
    echo "DeckLite desktop is not installed. Run the 'Install lightweight desktop' quick command first." >&2
    exit 1
fi

mkdir -p "$XDG_RUNTIME_DIR"
chmod 0700 "$XDG_RUNTIME_DIR"

start_audio_stack() {
    command -v pipewire >/dev/null 2>&1 || return 0
    pgrep -x pipewire >/dev/null 2>&1 || pipewire >>"$log_file" 2>&1 &
    for _ in {1..30}; do
        [[ -S "$XDG_RUNTIME_DIR/pipewire-0" ]] && break
        sleep 0.1
    done
    command -v wireplumber >/dev/null 2>&1 && \
        (pgrep -x wireplumber >/dev/null 2>&1 || wireplumber >>"$log_file" 2>&1 &) || true
    command -v pipewire-pulse >/dev/null 2>&1 && \
        (pgrep -x pipewire-pulse >/dev/null 2>&1 || pipewire-pulse >>"$log_file" 2>&1 &) || true
}

start_openbox() {
    nohup dbus-launch --exit-with-session openbox-session >>"$log_file" 2>&1 &
}

: >"$log_file"
start_audio_stack

case "$mode" in
    x11)
        start_openbox
        ;;
    avnc)
        if ! command -v Xtigervnc >/dev/null 2>&1; then
            echo "TigerVNC is missing. Re-run the desktop installer." >&2
            exit 1
        fi
        rm -f /tmp/.tiny.vnc /tmp/.X6-lock /tmp/.X11-unix/X6
        Xtigervnc \
            -geometry 1280x720 \
            -depth 24 \
            -ZlibLevel=0 \
            -pn \
            -rfbport -1 \
            -rfbunixpath /tmp/.tiny.vnc \
            -SecurityTypes=None \
            -alwaysshared \
            -once \
            :6 >>"$log_file" 2>&1 &
        for _ in {1..100}; do
            [[ -S /tmp/.tiny.vnc ]] && break
            sleep 0.1
        done
        [[ -S /tmp/.tiny.vnc ]] || {
            echo "VNC socket was not created. See $log_file" >&2
            exit 1
        }
        start_openbox
        ;;
    *)
        echo "Usage: $0 {x11|avnc}" >&2
        exit 2
        ;;
esac
