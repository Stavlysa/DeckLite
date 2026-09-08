#!/usr/bin/env bash
set -Eeuo pipefail

candidate="$HOME/.local/share/decklite-steam/candidate"
if [[ ! -f "$candidate/.decklite-update-candidate.json" ]]; then
    echo "No verified Steam update candidate is staged." >&2
    exit 1
fi
if pgrep -f '/steamrtarm64/steam([[:space:]]|$)' >/dev/null 2>&1; then
    echo "Close the currently running Steam client before testing the candidate." >&2
    exit 1
fi
export STEAM_ROOT="$candidate"
exec /opt/tiny/steam-arm64/run-steam.sh "$@"
