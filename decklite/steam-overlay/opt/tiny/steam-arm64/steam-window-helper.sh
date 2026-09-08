#!/usr/bin/env bash
set -Eeuo pipefail

state_dir="$HOME/.local/share/decklite-steam"
initial_marker="$state_dir/window-mode-v1"

find_main_window() {
    local deadline=$((SECONDS + ${1:-1}))
    local id geometry width height title area best_id="" best_area=0

    while (( SECONDS <= deadline )); do
        while read -r id; do
            [[ "$id" =~ ^[0-9]+$ ]] || continue
            geometry="$(xdotool getwindowgeometry --shell "$id" 2>/dev/null || true)"
            width="$(sed -n 's/^WIDTH=//p' <<<"$geometry")"
            height="$(sed -n 's/^HEIGHT=//p' <<<"$geometry")"
            [[ "$width" =~ ^[0-9]+$ && "$height" =~ ^[0-9]+$ ]] || continue
            (( width >= 800 && height >= 500 )) || continue
            title="$(xdotool getwindowname "$id" 2>/dev/null || true)"
            [[ "$title" == Steam* ]] || continue
            area=$((width * height))
            if (( area > best_area )); then
                best_id="$id"
                best_area="$area"
            fi
        done < <(xdotool search --class '^steam$' 2>/dev/null || true)
        if [[ -n "$best_id" ]]; then
            printf '%s\n' "$best_id"
            return 0
        fi
        sleep 1
    done
    return 1
}

medium_geometry() {
    local display_width=1280 display_height=720 width height x y
    read -r display_width display_height < <(
        xdotool getdisplaygeometry 2>/dev/null || printf '1280 720\n'
    )
    [[ "$display_width" =~ ^[0-9]+$ ]] || display_width=1280
    [[ "$display_height" =~ ^[0-9]+$ ]] || display_height=720
    width=$((display_width - 120))
    height=$((display_height - 100))
    (( width > 1100 )) && width=1100
    (( height > 650 )) && height=650
    (( width < 800 )) && width=800
    (( height < 500 )) && height=500
    x=$(((display_width - width) / 2))
    y=$(((display_height - height) / 2))
    printf '%s %s %s %s\n' "$width" "$height" "$x" "$y"
}

reset_window() {
    local window_id="$1" width height x y
    read -r width height x y < <(medium_geometry)
    xdotool windowmap "$window_id" windowraise "$window_id"
    xdotool windowsize --sync "$window_id" "$width" "$height"
    xdotool windowmove --sync "$window_id" "$x" "$y"
}

enable_native_decorations() {
    local window_id="$1" extents top=0 attempt
    command -v xprop >/dev/null 2>&1 || return 0
    command -v xfwm4 >/dev/null 2>&1 || return 0

    # Steam CEF publishes Motif decorations=0. XFWM only evaluates this hint
    # while initially managing a window, so changing the property alone is not
    # enough. Replacing XFWM remanages all existing windows without closing
    # them and gives Steam a normal title bar plus draggable resize borders.
    xprop -id "$window_id" -f _MOTIF_WM_HINTS 32c \
        -set _MOTIF_WM_HINTS "2, 0, 1, 0, 0"
    extents="$(xprop -id "$window_id" _NET_FRAME_EXTENTS 2>/dev/null || true)"
    top="$(sed -n 's/.*= *[0-9][0-9]*, *[0-9][0-9]*, *\([0-9][0-9]*\),.*/\1/p' <<<"$extents")"
    [[ "$top" =~ ^[0-9]+$ ]] || top=0
    if (( top < 10 )); then
        mkdir -p "$state_dir"
        nohup xfwm4 --replace --display="${DISPLAY:-:0}" \
            >>"$state_dir/xfwm4-steam-window.log" 2>&1 </dev/null &
        for attempt in {1..10}; do
            sleep 1
            extents="$(xprop -id "$window_id" _NET_FRAME_EXTENTS 2>/dev/null || true)"
            top="$(sed -n 's/.*= *[0-9][0-9]*, *[0-9][0-9]*, *\([0-9][0-9]*\),.*/\1/p' <<<"$extents")"
            [[ "$top" =~ ^[0-9]+$ ]] && (( top >= 10 )) && return 0
        done
        echo "Warning: Steam native window borders could not be enabled." >&2
    fi
}

mode="${1:---watch}"
case "$mode" in
    --watch)
        window_id="$(find_main_window 75)" || exit 0
        enable_native_decorations "$window_id"
        if [[ ! -e "$initial_marker" ]]; then
            reset_window "$window_id"
            mkdir -p "$state_dir"
            touch "$initial_marker"
        fi
        ;;
    --reset)
        window_id="$(find_main_window 10)" || {
            echo "Steam's main window was not found." >&2
            exit 1
        }
        enable_native_decorations "$window_id"
        reset_window "$window_id"
        ;;
    --find)
        find_main_window 10
        ;;
    *)
        echo "Usage: $0 [--watch|--reset|--find]" >&2
        exit 2
        ;;
esac
