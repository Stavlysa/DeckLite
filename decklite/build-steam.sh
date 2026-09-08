#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
source_archive="${1:-$project_dir/cache/xfce-en-20260808-202640.tar.zst}"
output="${2:-$project_dir/build/decklite-steam-arm64-rootfs.tar.zst}"
steam_payload="${STEAM_ARM64_PAYLOAD:-$project_dir/cache/steam-arm64-1785799196/root}"
package_cache="${STEAM_ARM64_PACKAGE_CACHE:-$project_dir/cache/steam-arm64-1785799196/packages}"
hangover_bundle="${HANGOVER_BUNDLE:-$project_dir/cache/hangover/hangover_11.16_debian13_trixie_arm64.tar}"
debian_package_index="${DEBIAN_PACKAGE_INDEX:-$project_dir/cache/debian/trixie-main-arm64-Packages.xz}"
debian_package_cache="${DEBIAN_PACKAGE_CACHE:-$project_dir/cache/debian/packages}"
hangover_layer="${HANGOVER_LAYER:-$project_dir/cache/hangover/hangover-preinstalled-layer.tar.zst}"
ge_proton_archive="${GE_PROTON_ARCHIVE:-$project_dir/cache/ge-proton/GE-Proton11-6-aarch64.tar.gz}"
steamrt4_archive="${STEAMRT4_ARCHIVE:-$project_dir/cache/steamrt4/SteamLinuxRuntime_4-arm64.tar.xz}"
wine_prefix_templates_archive="${WINE_PREFIX_TEMPLATES_ARCHIVE:-$project_dir/cache/wine-prefix-templates.tar.zst}"
winetricks="${WINETRICKS:-$project_dir/cache/winetricks-20260125}"
jobs="${STEAM_DOWNLOAD_JOBS:-6}"
base_url="https://github.com/tiny-computer/images/releases/download/260808/xfce-en-20260808-202640.tar.zst"
base_sha256="571c3f56f64f068a278303b1abc0e1729de5c6a2272abb3deebb31cae3866b9f"
hangover_url="https://github.com/AndreRH/hangover/releases/download/hangover-11.16/hangover_11.16_debian13_trixie_arm64.tar"
hangover_sha256="b5493f5903ab3c05f78bf4c03b06ac0005eb26f732437748c1592fefa45e861a"
package_index_url="https://deb.debian.org/debian/dists/trixie/main/binary-arm64/Packages.xz"
ge_proton_url="https://github.com/GloriousEggroll/proton-ge-custom/releases/download/GE-Proton11-6/GE-Proton11-6-aarch64.tar.gz"
ge_proton_sha512="c539b1c3b4fe6132fa3a2bce274926e41f0ea77a9bbc9aadb78878b840f6ab32d690a3e2b89f00ac864678c528cee3abf99e7ac222277f33403cf27834626f3b"
steamrt4_url="https://repo.steampowered.com/steamrt4/images/4.0.20260805.254769/SteamLinuxRuntime_4-arm64.tar.xz"
steamrt4_sha256="caa4b3bc3aad1cac43d94dbd802a963c13ed63ea1c414f04669ae402af505adf"
winetricks_url="https://raw.githubusercontent.com/Winetricks/winetricks/20260125/src/winetricks"
winetricks_sha256="431f82fc74000e6c864409f1d8fb495d696c03928808e3e8acffc45179312a7b"
wine_prefix_templates_sha256="d69b2703bf9b6fcc4bb1e5a8b3809c4e750b915686d5ecc820b365371c9364a4"

mkdir -p "$(dirname -- "$source_archive")" "$steam_payload" "$package_cache" \
    "$(dirname -- "$hangover_bundle")" "$(dirname -- "$debian_package_index")" \
    "$debian_package_cache" "$(dirname -- "$ge_proton_archive")" \
    "$(dirname -- "$steamrt4_archive")" \
    "$(dirname -- "$winetricks")" \
    "$(dirname -- "$output")"

if [[ ! -f "$source_archive" ]]; then
    echo "Downloading the official Tiny Container XFCE base..."
    curl --fail --location --retry 3 "$base_url" --output "$source_archive"
fi

if command -v sha256sum >/dev/null 2>&1; then
    actual_sha256="$(sha256sum "$source_archive" | awk '{print tolower($1)}')"
else
    actual_sha256="$(shasum -a 256 "$source_archive" | awk '{print tolower($1)}')"
fi
if [[ "$actual_sha256" != "$base_sha256" ]]; then
    echo "Base image checksum mismatch: expected $base_sha256, got $actual_sha256" >&2
    exit 1
fi
echo "Verified official Tiny Container base SHA256: $actual_sha256"

if [[ ! -f "$hangover_bundle" ]]; then
    echo "Downloading Hangover 11.16 for Debian 13 ARM64..."
    curl --fail --location --retry 3 "$hangover_url" --output "$hangover_bundle"
fi
if command -v sha256sum >/dev/null 2>&1; then
    actual_hangover_sha256="$(sha256sum "$hangover_bundle" | awk '{print tolower($1)}')"
else
    actual_hangover_sha256="$(shasum -a 256 "$hangover_bundle" | awk '{print tolower($1)}')"
fi
if [[ "$actual_hangover_sha256" != "$hangover_sha256" ]]; then
    echo "Hangover checksum mismatch: expected $hangover_sha256, got $actual_hangover_sha256" >&2
    exit 1
fi
echo "Verified Hangover SHA256: $actual_hangover_sha256"

if [[ ! -f "$debian_package_index" ]]; then
    echo "Downloading the Debian 13 ARM64 package index..."
    curl --fail --location --retry 3 "$package_index_url" --output "$debian_package_index"
fi

if [[ ! -f "$ge_proton_archive" ]]; then
    echo "Downloading GE-Proton11-6 AArch64..."
    curl --fail --location --retry 3 "$ge_proton_url" --output "$ge_proton_archive"
fi
if command -v sha512sum >/dev/null 2>&1; then
    actual_ge_proton_sha512="$(sha512sum "$ge_proton_archive" | awk '{print tolower($1)}')"
else
    actual_ge_proton_sha512="$(shasum -a 512 "$ge_proton_archive" | awk '{print tolower($1)}')"
fi
if [[ "$actual_ge_proton_sha512" != "$ge_proton_sha512" ]]; then
    echo "GE-Proton checksum mismatch: expected $ge_proton_sha512, got $actual_ge_proton_sha512" >&2
    exit 1
fi
echo "Verified GE-Proton SHA512: $actual_ge_proton_sha512"

if [[ ! -f "$steamrt4_archive" ]]; then
    echo "Downloading Valve Steam Linux Runtime 4 ARM64..."
    curl --fail --location --retry 3 "$steamrt4_url" --output "$steamrt4_archive"
fi
if command -v sha256sum >/dev/null 2>&1; then
    actual_steamrt4_sha256="$(sha256sum "$steamrt4_archive" | awk '{print tolower($1)}')"
else
    actual_steamrt4_sha256="$(shasum -a 256 "$steamrt4_archive" | awk '{print tolower($1)}')"
fi
if [[ "$actual_steamrt4_sha256" != "$steamrt4_sha256" ]]; then
    echo "Steam Runtime 4 checksum mismatch: expected $steamrt4_sha256, got $actual_steamrt4_sha256" >&2
    exit 1
fi
echo "Verified Steam Runtime 4 SHA256: $actual_steamrt4_sha256"

if [[ ! -f "$winetricks" ]]; then
    echo "Downloading Winetricks 20260125..."
    curl --fail --location --retry 3 "$winetricks_url" --output "$winetricks"
fi
if command -v sha256sum >/dev/null 2>&1; then
    actual_winetricks_sha256="$(sha256sum "$winetricks" | awk '{print tolower($1)}')"
else
    actual_winetricks_sha256="$(shasum -a 256 "$winetricks" | awk '{print tolower($1)}')"
fi
if [[ "$actual_winetricks_sha256" != "$winetricks_sha256" ]]; then
    echo "Winetricks checksum mismatch: expected $winetricks_sha256, got $actual_winetricks_sha256" >&2
    exit 1
fi
echo "Verified Winetricks SHA256: $actual_winetricks_sha256"

if [[ ! -f "$wine_prefix_templates_archive" ]]; then
    echo "Offline Wine prefix templates are missing: $wine_prefix_templates_archive" >&2
    exit 1
fi
if command -v sha256sum >/dev/null 2>&1; then
    actual_wine_prefix_templates_sha256="$(sha256sum "$wine_prefix_templates_archive" | awk '{print tolower($1)}')"
else
    actual_wine_prefix_templates_sha256="$(shasum -a 256 "$wine_prefix_templates_archive" | awk '{print tolower($1)}')"
fi
if [[ "$actual_wine_prefix_templates_sha256" != "$wine_prefix_templates_sha256" ]]; then
    echo "Wine prefix template checksum mismatch: expected $wine_prefix_templates_sha256, got $actual_wine_prefix_templates_sha256" >&2
    exit 1
fi
echo "Verified offline Wine prefix templates SHA256: $actual_wine_prefix_templates_sha256"

python3 "$project_dir/tools/prepare_hangover_layer.py" \
    --base "$source_archive" \
    --bundle "$hangover_bundle" \
    --bundle-sha256 "$hangover_sha256" \
    --package-index "$debian_package_index" \
    --package-cache "$debian_package_cache" \
    --output "$hangover_layer"

python3 "$project_dir/tools/prepare_pinned_steam_arm64.py" \
    --lock "$project_dir/steam-arm64-1785799196-packages.json" \
    --output "$steam_payload" \
    --package-cache "$package_cache" \
    --jobs "$jobs"

python3 "$project_dir/tools/build_steam_rootfs.py" \
    --source "$source_archive" \
    --overlay "$project_dir/steam-overlay" \
    --winetricks "$winetricks" \
    --steam-payload "$steam_payload" \
    --hangover-layer "$hangover_layer" \
    --ge-proton-archive "$ge_proton_archive" \
    --steamrt4-archive "$steamrt4_archive" \
    --wine-prefix-templates-archive "$wine_prefix_templates_archive" \
    --output "$output"

python3 "$project_dir/tools/verify_steam_rootfs.py" --archive "$output"
ls -lh "$output" "$output.sha256"
