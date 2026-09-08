#!/usr/bin/env bash
set -Eeuo pipefail

if (( EUID == 0 )); then
    echo "Run this installer as the alarm desktop user, not root." >&2
    exit 1
fi

box64_bin="$(command -v box64 || true)"
if [[ -z "$box64_bin" ]]; then
    echo "Box64 is not installed. Run the Box64 quick command first." >&2
    exit 1
fi

for command_name in curl ar tar; do
    command -v "$command_name" >/dev/null 2>&1 || {
        echo "Missing command: $command_name. Re-run the Box64 installer." >&2
        exit 1
    }
done

steam_root="$HOME/steam"
work_dir="$(mktemp -d /tmp/decklite-steam-XXXXXX)"
trap 'rm -rf "$work_dir"' EXIT

echo "Downloading the official Linux Steam package..."
curl --fail --location --retry 3 \
    https://cdn.cloudflare.steamstatic.com/client/installer/steam.deb \
    --output "$work_dir/steam.deb"

mkdir -p "$work_dir/deb" "$work_dir/unpacked" "$steam_root"
cd "$work_dir/deb"
ar x "$work_dir/steam.deb"

data_archive=""
for candidate in data.tar.*; do
    [[ -f "$candidate" ]] && data_archive="$candidate" && break
done
if [[ -z "$data_archive" ]]; then
    echo "The Steam package does not contain data.tar.*" >&2
    exit 1
fi

tar -xf "$data_archive" -C "$work_dir/unpacked"
if [[ ! -d "$work_dir/unpacked/usr" ]]; then
    echo "Unexpected Steam package layout." >&2
    exit 1
fi
cp -a "$work_dir/unpacked/usr/." "$steam_root/"

mkdir -p "$HOME/.local/bin" "$HOME/.local/share/applications"
cat >"$HOME/.local/bin/steam-decklite" <<'EOF'
#!/usr/bin/env bash
set -e
export STEAMOS=1
export STEAM_RUNTIME=1
export PROTON_USE_WOW64=1
export DBUS_FATAL_WARNINGS=0
export BOX64_DYNAREC_STRONGMEM=2
export BOX64_DYNAREC_BIGBLOCK=3
export BOX64_DYNAREC_CALLRET=1
export BOX64_MAXCPU=8
if [[ -x /usr/local/lib/box64/bash ]]; then
    export BOX64_BASH=/usr/local/lib/box64/bash
fi
exec box64 "$HOME/steam/bin/steam" "$@"
EOF
chmod 0755 "$HOME/.local/bin/steam-decklite"

cat >"$HOME/.local/share/applications/steam-decklite.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=Steam (DeckLite experimental)
Comment=Run the x86 Steam client through Box64/Box32
Exec=/home/alarm/.local/bin/steam-decklite
Icon=applications-games
Terminal=false
Categories=Game;
EOF

cat <<'EOF'

Steam files installed. Launch with:
  ~/.local/bin/steam-decklite

This is experimental on Android AArch64 PRoot. Failure of Steam WebHelper,
Vulkan, anti-cheat, or individual games is expected on some devices.
EOF

