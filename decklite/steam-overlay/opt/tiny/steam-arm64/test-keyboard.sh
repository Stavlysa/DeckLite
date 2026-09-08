#!/usr/bin/env bash
set -Eeuo pipefail

log_file="$HOME/Downloads/decklite-keyboard-test.log"
mkdir -p "$(dirname "$log_file")"
echo "DeckLite physical keyboard test: press A, Z, Left, Right, then close the window." | tee "$log_file"
xev -event keyboard -name "DeckLite physical keyboard test" 2>&1 | tee -a "$log_file"
