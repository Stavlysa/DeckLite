#!/usr/bin/env bash
set -Eeuo pipefail

if (( EUID != 0 )); then
    echo "Run as root: su -c '/opt/tiny/install-box64.sh'" >&2
    exit 1
fi

if [[ "$(uname -m)" != "aarch64" ]]; then
    echo "This installer supports only an AArch64 container." >&2
    exit 1
fi

box64_version="${BOX64_VERSION:-v0.4.2}"
build_root="$(mktemp -d /tmp/decklite-box64-XXXXXX)"
trap 'rm -rf "$build_root"' EXIT

echo "Installing Box64 build dependencies..."
pacman -S --needed --noconfirm base-devel cmake git python

echo "Cloning Box64 $box64_version..."
git clone --depth 1 --branch "$box64_version" https://github.com/ptitSeb/box64.git "$build_root/box64"

jobs="$(nproc 2>/dev/null || echo 2)"
(( jobs > 4 )) && jobs=4

cmake \
    -S "$build_root/box64" \
    -B "$build_root/box64/build" \
    -DARM64=1 \
    -DBAD_SIGNAL=ON \
    -DBOX32=ON \
    -DBOX32_BINFMT=OFF \
    -DCMAKE_BUILD_TYPE=Release
cmake --build "$build_root/box64/build" --parallel "$jobs"
cmake --install "$build_root/box64/build"
ldconfig

if [[ -f "$build_root/box64/tests/bash" ]]; then
    install -Dm755 "$build_root/box64/tests/bash" /usr/local/lib/box64/bash
fi

cat <<'EOF'

Box64/Box32 installation complete.
Tiny Container uses PRoot, so kernel binfmt integration is intentionally off.
Nested x86 launchers can still fail; Steam support remains experimental.
EOF
/usr/local/bin/box64 -v || true

