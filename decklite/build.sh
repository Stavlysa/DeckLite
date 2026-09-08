#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
mirror="${ARCHLINUXARM_MIRROR:-https://de3.mirror.archlinuxarm.org/os}"
source_archive="${1:-$project_dir/cache/ArchLinuxARM-aarch64-latest.tar.gz}"
output="${2:-$project_dir/build/decklite-arch-arm-rootfs.tar.zst}"

mkdir -p "$(dirname -- "$source_archive")" "$(dirname -- "$output")"

if [[ ! -f "$source_archive" ]]; then
    curl --fail --location --retry 3 \
        "$mirror/ArchLinuxARM-aarch64-latest.tar.gz" \
        --output "$source_archive"
fi

checksum_file="$source_archive.md5"
curl --fail --location --retry 3 \
    "$mirror/ArchLinuxARM-aarch64-latest.tar.gz.md5" \
    --output "$checksum_file"

expected="$(awk '{print tolower($1); exit}' "$checksum_file")"
actual="$(md5sum "$source_archive" | awk '{print tolower($1)}')"
if [[ "$actual" != "$expected" ]]; then
    echo "Rootfs checksum mismatch: expected $expected, got $actual" >&2
    exit 1
fi
echo "Verified official rootfs MD5: $actual"

python3 "$project_dir/tools/build_rootfs.py" \
    --source "$source_archive" \
    --overlay "$project_dir/overlay" \
    --output "$output"

python3 "$project_dir/tools/verify_rootfs.py" --archive "$output"
ls -lh "$output"

