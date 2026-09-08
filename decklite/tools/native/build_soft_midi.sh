#!/usr/bin/env bash
set -euo pipefail
# Build natively on ARM64 Linux; Debian development packages:
# gcc libc6-dev libasound2-dev libfluidsynth-dev. Runtime needs libasound2,
# libfluidsynth3, a PulseAudio-compatible server, and timgm6mb-soundfont.
source_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
output="${1:?Usage: build_soft_midi.sh OUTPUT.so}"
[[ "$(uname -m)" == aarch64 ]] || {
    printf 'Build this preload library on ARM64 Linux.\n' >&2
    exit 1
}
gcc -shared -fPIC -O2 -Wall -Wextra -Werror \
    "$source_dir/soft_midi.c" -Wl,-z,relro,-z,now -Wl,-z,defs \
    -l:libasound.so.2 -ldl -pthread -o "$output"
