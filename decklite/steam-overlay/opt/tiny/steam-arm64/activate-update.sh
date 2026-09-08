#!/usr/bin/env bash
set -Eeuo pipefail

state="$HOME/.local/share/decklite-steam"
candidate="$state/candidate"
if [[ ! -f "$candidate/.decklite-update-candidate.json" ]]; then
    echo "No verified Steam update candidate is staged." >&2
    exit 1
fi
if pgrep -f '/steamrtarm64/steam([[:space:]]|$)' >/dev/null 2>&1; then
    echo "Close Steam before activating an update candidate." >&2
    exit 1
fi
mkdir -p "$state"
printf '%s\n' "$candidate" >"$state/active-root.new"
mv -f "$state/active-root.new" "$state/active-root"
echo "The staged Steam candidate is now active. Rollback remains available."
