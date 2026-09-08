#!/usr/bin/env bash
set -Eeuo pipefail

state="$HOME/.local/share/decklite-steam"
if pgrep -f '/steamrtarm64/steam([[:space:]]|$)' >/dev/null 2>&1; then
    echo "Close Steam before rolling back." >&2
    exit 1
fi
rm -f -- "$state/active-root" "$state/active-root.new"
echo "Restored the tested Steam ARM64 build 1785799196. User data and games were not removed."
