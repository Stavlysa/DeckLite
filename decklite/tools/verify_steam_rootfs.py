#!/usr/bin/env python3
"""Verify the Steam-ready Tiny Container image."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import struct
import tarfile
from pathlib import Path


REQUIRED = {
    ".tiny.yaml",
    "home/tiny/.local/share/Steam/.decklite-steam-version",
    "home/tiny/.local/share/Steam/steam.sh",
    "home/tiny/.local/share/Steam/steamrt64/pv-runtime/steam-runtime-steamrt/_v2-entry-point",
    "home/tiny/.local/share/Steam/steamrtarm64/steam",
    "home/tiny/.local/share/Steam/package/decklite-pinned-build",
    "home/tiny/.local/share/Steam/package/decklite-package-sha256.json",
    "home/tiny/.local/share/Steam/package/steam_client_linuxarm64.installed",
    "home/tiny/.local/share/Steam/package/steam_client_linuxarm64.manifest",
    "home/tiny/.local/share/Steam/compatibilitytools.d/GE-Proton11-6-aarch64/compatibilitytool.vdf",
    "home/tiny/.local/share/Steam/compatibilitytools.d/GE-Proton11-6-aarch64/files/bin-arm64/wine",
    "home/tiny/.local/share/Steam/compatibilitytools.d/GE-Proton11-6-aarch64/proton",
    "home/tiny/.local/share/Steam/compatibilitytools.d/GE-Proton11-6-aarch64/toolmanifest.vdf",
    "home/tiny/.local/share/Steam/compatibilitytools.d/GE-Proton11-6-aarch64/version",
    "home/tiny/.local/share/Steam/compatibilitytools.d/decklite-arm64-runtime/compatibilitytool.vdf",
    "home/tiny/.local/share/Steam/steamapps/appmanifest_4185400.acf",
    "home/tiny/.local/share/Steam/steamapps/common/SteamLinuxRuntime_4-arm64/_v2-entry-point",
    "home/tiny/.local/share/Steam/steamapps/common/SteamLinuxRuntime_4-arm64/pressure-vessel/libexec/steam-runtime-tools-0/srt-bwrap",
    "home/tiny/.local/share/Steam/steamapps/common/SteamLinuxRuntime_4-arm64/toolmanifest.vdf",
    "home/tiny/.local/share/applications/steam-arm64.desktop",
    "home/tiny/.local/share/applications/mimeinfo.cache",
    "home/tiny/Desktop/Steam.desktop",
    "home/tiny/Desktop/Steam Window Controls.desktop",
    "home/tiny/Desktop/Wine Manager.desktop",
    "home/tiny/Desktop/Resource Monitor.desktop",
    "etc/profile.d/00-decklite-glibc-loader.sh",
    "etc/profile.d/decklite-game-performance.sh",
    "usr/lib/locale/locale-archive",
    "usr/share/backgrounds/decklite-black.svg",
    "opt/tiny/extra/install-hangover.sh",
    "opt/tiny/extra/libdecklite-affinity.so",
    "opt/tiny/extra/libdecklite-soft-midi.so",
    "usr/share/sounds/sf2/TimGM6mb.sf2",
    "usr/lib/aarch64-linux-gnu/libfluidsynth.so.3",
    "opt/tiny/start-desktop.sh",
    "opt/tiny/steam-arm64/run-steam.sh",
    "opt/tiny/steam-arm64/patch-steam-webhelper.py",
    "opt/tiny/steam-arm64/steam-window-helper.sh",
    "opt/tiny/steam-arm64/steam_window_controls.py",
    "opt/tiny/steam-arm64/steam_tray.py",
    "opt/tiny/steam-arm64/configure-proton.py",
    "opt/tiny/steam-arm64/patch-ge-proton.py",
    "opt/tiny/steam-arm64/test-keyboard.sh",
    "opt/tiny/steam-arm64/run-exe.sh",
    "opt/tiny/steam-arm64/dxvk-game.conf",
    "opt/tiny/steam-arm64/update_steam.py",
    "opt/tiny/steam-arm64/stage-update.py",
    "opt/tiny/steam-arm64/test-update.sh",
    "opt/tiny/steam-arm64/activate-update.sh",
    "opt/tiny/steam-arm64/rollback-update.sh",
    "opt/tiny/steam-arm64/libtgcompat-robust.so",
    "opt/tiny/steam-arm64/lsof.real",
    "opt/tiny/steam-arm64/patch-steam-ui.py",
    "opt/tiny/wine-manager/container-start.sh",
    "opt/tiny/wine-manager/borderless-x11.py",
    "opt/tiny/wine-manager/auto-display-x11.py",
    "usr/local/bin/wine-manager",
    "usr/share/doc/decklite-steam-arm64/AUTO-DISPLAY.md",
    "usr/share/doc/decklite-steam-arm64/WINE-UI-LANGUAGE.md",
    "opt/tiny/wine-manager/dxvk/arm64ec/d3d11.dll",
    "opt/tiny/wine-manager/dxvk/x32/d3d11.dll",
    "opt/tiny/wine-manager/hangover-layer.json",
    "opt/tiny/wine-manager/prefix-templates/game-complete/system.reg",
    "opt/tiny/wine-manager/prefix-templates/game-complete/.decklite-runtimes-common",
    "opt/tiny/wine-manager/prefix-templates/game-complete/.decklite-runtimes-legacy-media",
    "opt/tiny/wine-manager/prefix-templates/dotnet-xna-complete/system.reg",
    "opt/tiny/wine-manager/prefix-templates/dotnet-xna-complete/.decklite-runtimes-dotnet-xna",
    "opt/tiny/wine-manager/prefix-templates/dotnet-xna-complete/.decklite-dotnet-mscoree-repaired",
    "opt/tiny/wine-manager/install-dxvk.sh",
    "opt/tiny/wine-manager/install-game-runtimes.sh",
    "opt/tiny/wine-manager/prepare-prefix.sh",
    "opt/tiny/wine-manager/wine-prefix-run",
    "opt/tiny/wine-manager/wine-region-env.sh",
    "opt/tiny/wine-manager/wine-midi-env.sh",
    "usr/share/doc/decklite-steam-arm64/WINE-MIDI.md",
    "opt/tiny/wine-manager/wine_timezone.py",
    "opt/tiny/wine-manager/wine-game-launch.exe",
    "opt/tiny/wine-manager/wine_manager.py",
    "opt/tiny/wine-manager/ui_i18n.py",
    "opt/tiny/wine-manager/stop-wine.py",
    "proc/.cgroups",
    "proc/.diskstats",
    "proc/.net_dev",
    "usr/bin/wine",
    "usr/bin/wineboot",
    "usr/bin/winecfg",
    "usr/bin/winefile",
    "usr/bin/wineserver",
    "usr/bin/regedit",
    "usr/bin/lsof",
    "usr/bin/xdg-open",
    "usr/bin/xdotool",
    "usr/bin/xprop",
    "usr/lib/wine/aarch64-unix/wine",
    "usr/lib/wine/aarch64-windows/libarm64ecfex.dll",
    "usr/lib/wine/aarch64-windows/libwow64fex.dll",
    "usr/lib/wine/aarch64-windows/wowbox64.dll",
    "usr/lib/aarch64-linux-gnu/libgtk-3.so.0",
    "usr/lib/aarch64-linux-gnu/libopenal.so.1",
    "usr/lib/python3/dist-packages/gi/__init__.py",
    "usr/local/bin/run-exe",
    "usr/local/bin/run-exe-fullscreen",
    "opt/tiny/wine-manager/black-desktop.reg",
    "usr/local/bin/decklite-resource-monitor",
    "usr/local/bin/resource-monitor",
    "usr/local/bin/steam-arm64",
    "usr/local/bin/winetricks",
    "usr/local/bin/wine-manager",
    "usr/share/doc/decklite-steam-arm64/tgcompat/LICENSE",
    "usr/share/doc/decklite-steam-arm64/tgcompat/PROVENANCE.md",
    "usr/share/doc/decklite-steam-arm64/tgcompat/flock_shim.c",
    "usr/share/doc/decklite-steam-arm64/tgcompat/robust_shim.c",
    "usr/share/doc/decklite-steam-arm64/tgcompat/robust_shim_aarch64.S",
    "usr/share/doc/decklite-steam-arm64/steamclienttermux/LICENSE",
    "usr/share/doc/decklite-steam-arm64/steamclienttermux/PROVENANCE.md",
    "var/lib/dpkg/status",
}

REQUIRED_STEAM_SYMLINK = (
    "home/tiny/.local/share/Steam/steamrt64/video/libavcodec.so.62"
)

CLIENT_CODE_DENYLIST = (
    r"app.*",
    r"cache",
    r"code_cache",
    r"com.*",
    r"databases",
    r"files",
    r"lib",
    r"no_backup",
)


def normalize(value: str) -> str:
    while value.startswith("./"):
        value = value[2:]
    return value.rstrip("/")


def elf_machine(archive: tarfile.TarFile, member: tarfile.TarInfo) -> int:
    handle = archive.extractfile(member)
    if handle is None:
        raise RuntimeError(f"Cannot read {member.name}")
    header = handle.read(20)
    if header[:4] != b"\x7fELF":
        raise RuntimeError(f"Not an ELF file: {member.name}")
    endian = "<" if header[5] == 1 else ">"
    return struct.unpack(endian + "H", header[18:20])[0]


def parse_status(text: str) -> dict[str, dict[str, str]]:
    records: dict[str, dict[str, str]] = {}
    current: dict[str, str] = {}
    key: str | None = None
    for line in text.splitlines() + [""]:
        if not line:
            if current.get("Package"):
                records[current["Package"]] = current
            current = {}
            key = None
        elif line[0].isspace() and key:
            current[key] += " " + line.strip()
        elif ":" in line:
            key, value = line.split(":", 1)
            current[key] = value.lstrip()
    return records


def dependency_groups(value: str) -> list[list[str]]:
    groups: list[list[str]] = []
    for group in value.split(","):
        choices: list[str] = []
        for raw in group.split("|"):
            match = re.match(r"\s*([a-z0-9][a-z0-9+.-]*)(?::[a-z0-9-]+)?", raw)
            if match:
                choices.append(match.group(1))
        if choices:
            groups.append(choices)
    return groups


def verify(path: Path) -> None:
    with tarfile.open(path, "r:*") as archive:
        members = list(archive)
        by_name = {normalize(member.name): member for member in members}
        if "etc/ld.so.cache" in by_name:
            raise RuntimeError("Rootfs must not ship a stale dynamic loader cache")
        if not members or normalize(members[0].name) != ".tiny.yaml":
            raise RuntimeError(".tiny.yaml is not the first archive entry")
        unsafe_members = [
            member.name
            for member in members
            if member.name.startswith("/") or ".." in Path(member.name).parts
        ]
        if unsafe_members:
            raise RuntimeError(
                "Archive contains paths unsafe for the Tiny Container importer: "
                + ", ".join(unsafe_members[:5])
            )
        unsafe_links = [
            f"{member.name} -> {member.linkname}"
            for member in members
            if (member.issym() or member.islnk())
            and normalize(member.name).startswith(
                (
                    "home/tiny/.local/share/Steam/compatibilitytools.d/GE-Proton11-6-aarch64/",
                    "home/tiny/.local/share/Steam/steamapps/common/SteamLinuxRuntime_4-arm64/",
                )
            )
            and (
                member.linkname.startswith("/")
                or (member.islnk() and ".." in Path(member.linkname).parts)
            )
        ]
        if unsafe_links:
            raise RuntimeError(
                "Archive contains unsafe link targets: " + ", ".join(unsafe_links[:5])
            )
        missing = sorted(REQUIRED - set(by_name))
        if missing:
            raise RuntimeError(f"Missing required entries: {', '.join(missing)}")

        metadata = archive.extractfile(by_name[".tiny.yaml"])
        if metadata is None:
            raise RuntimeError("Cannot read Tiny metadata")
        metadata_text = metadata.read().decode("utf-8")
        code_match = re.search(r"(?m)^code:\s*([^\s]+)\s*$", metadata_text)
        if code_match is None or re.fullmatch(r"[A-Za-z0-9]{1,32}", code_match.group(1)) is None:
            raise RuntimeError(
                "Container code does not satisfy the Tiny Container client rule: "
                "1-32 ASCII letters or digits"
            )
        if any(
            re.fullmatch(pattern, code_match.group(1), flags=re.IGNORECASE)
            for pattern in CLIENT_CODE_DENYLIST
        ):
            raise RuntimeError("Container code matches Tiny Container's reserved-name denylist")
        for required_text in (
            "code: decklitesteamarm64",
            "Launch Steam ARM64",
            "Stage Steam update candidate",
            "Rollback to tested Steam",
            "Test hardware keyboard",
            "name: Stop all Wine\n",
            "python3 /opt/tiny/wine-manager/stop-wine.py --yes",
            "Hangover 11.16 is preinstalled",
            "Hangover configuration",
            "--wine=/usr/bin/wine",
            "Termux:X11 is the default desktop frontend",
            "command: /opt/tiny/start-desktop.sh avnc",
            "command: /opt/tiny/start-desktop.sh x11",
            "--bind=$CONTAINER_DIR/proc/.cgroups:/proc/cgroups",
            "--bind=$CONTAINER_DIR/proc/.diskstats:/proc/diskstats",
            "--bind=$CONTAINER_DIR/proc/.net_dev:/proc/net/dev",
            "LD_LIBRARY_PATH=/lib/aarch64-linux-gnu:/usr/lib/aarch64-linux-gnu:/lib:/usr/lib",
        ):
            if required_text not in metadata_text:
                raise RuntimeError(f"Metadata is missing: {required_text}")
        if "LD_LIBRARY_PATH=$EXTRA_LD_LIBRARY_PATH" in metadata_text:
            raise RuntimeError("Metadata leaks Android/Bionic libraries into the guest")
        lstat_feature = re.search(
            r"(?ms)^- type: lstat-cache\n.*?(?=^- type:|\Z)", metadata_text
        )
        if lstat_feature is None:
            raise RuntimeError("Metadata is missing the lstat-cache feature")
        if any(
            volatile_path in lstat_feature.group(0)
            for volatile_path in ("$CACHE_DIR/tmp", "$CACHE_DIR/run")
        ):
            raise RuntimeError("lstat-cache includes a dynamic runtime socket directory")
        if not re.search(
            r"at least 20 GiB of free\s+internal app storage", metadata_text
        ):
            raise RuntimeError("Metadata is missing the 20 GiB app-storage warning")
        if not re.search(
            r"name: Hangover configuration.*?enabled: true",
            metadata_text,
            flags=re.DOTALL,
        ):
            raise RuntimeError("Hangover container configuration is not enabled by default")
        for feature_type, expected in (("avnc", "false"), ("x11", "true")):
            if not re.search(
                rf"(?ms)^- type: {feature_type}\n.*?^  enabled: {expected}$",
                metadata_text,
            ):
                raise RuntimeError(
                    f"Tiny desktop default is incorrect: {feature_type} must be {expected}"
                )
        if not re.search(
            r"(?ms)name: Turnip \+ Zink Acceleration with DRI3\n.*?"
            r"^      enabled: true$",
            metadata_text,
        ):
            raise RuntimeError("Turnip + Zink DRI3 is not enabled by default")
        if not re.search(r"(?m)^  \$BIN_DIR/proot-latest ", metadata_text):
            raise RuntimeError("Steam container does not select Tiny's current PRoot")
        for command_name in ("boot_command", "export_command"):
            command_block = re.search(
                rf"(?ms)^{command_name}: \|\n(.*?)(?=^[A-Za-z_]+:|\Z)",
                metadata_text,
            )
            if command_block is None:
                raise RuntimeError(f"Metadata is missing {command_name}")
            command_lines = [
                line for line in command_block.group(1).splitlines() if line.strip()
            ]
            if len(command_lines) != 1:
                raise RuntimeError(
                    f"{command_name} contains a shell-breaking uncontinued newline"
                )

        steam_binary = by_name["home/tiny/.local/share/Steam/steamrtarm64/steam"]
        if elf_machine(archive, steam_binary) != 183:
            raise RuntimeError("Steam client is not native AArch64")
        if steam_binary.mode & 0o111 == 0:
            raise RuntimeError("Steam ARM64 binary is not executable")
        steam_binary_handle = archive.extractfile(steam_binary)
        if steam_binary_handle is None or hashlib.sha256(
            steam_binary_handle.read()
        ).hexdigest() != "72f48fb9c3f2c19cf64f8f7bbf4c7b7af65a73571ae0eeaab05bffd1633f4126":
            raise RuntimeError("Steam client is not the tested complete build 1785799196")
        for version_path in (
            "home/tiny/.local/share/Steam/.decklite-steam-version",
            "home/tiny/.local/share/Steam/package/decklite-pinned-build",
        ):
            version_handle = archive.extractfile(by_name[version_path])
            if version_handle is None or version_handle.read().strip() != b"1785799196":
                raise RuntimeError(f"Unexpected pinned Steam version marker: {version_path}")

        ge_wine = by_name[
            "home/tiny/.local/share/Steam/compatibilitytools.d/GE-Proton11-6-aarch64/files/bin-arm64/wine"
        ]
        if elf_machine(archive, ge_wine) != 183 or ge_wine.mode & 0o111 == 0:
            raise RuntimeError("GE-Proton Wine is not an executable AArch64 binary")
        ge_proton = by_name[
            "home/tiny/.local/share/Steam/compatibilitytools.d/GE-Proton11-6-aarch64/proton"
        ]
        if ge_proton.mode & 0o111 == 0:
            raise RuntimeError("GE-Proton entry point is not executable")
        runtime_entry = by_name[
            "home/tiny/.local/share/Steam/steamapps/common/SteamLinuxRuntime_4-arm64/_v2-entry-point"
        ]
        if runtime_entry.mode & 0o111 == 0:
            raise RuntimeError("Steam Linux Runtime 4 entry point is not executable")
        runtime_bwrap = by_name[
            "home/tiny/.local/share/Steam/steamapps/common/SteamLinuxRuntime_4-arm64/pressure-vessel/libexec/steam-runtime-tools-0/srt-bwrap"
        ]
        if elf_machine(archive, runtime_bwrap) != 183:
            raise RuntimeError("Steam Linux Runtime 4 srt-bwrap is not AArch64")

        if "home/tiny/.local/share/Steam/package/beta" in by_name:
            raise RuntimeError("Steam client is unexpectedly opted into a beta channel")

        robust_shim = by_name["opt/tiny/steam-arm64/libtgcompat-robust.so"]
        if elf_machine(archive, robust_shim) != 183:
            raise RuntimeError("Steam robust-list shim is not AArch64")
        if robust_shim.mode & 0o111 == 0:
            raise RuntimeError("Steam robust-list shim is not executable")
        robust_handle = archive.extractfile(robust_shim)
        if robust_handle is None:
            raise RuntimeError("Cannot read the Steam robust-list shim")
        if hashlib.sha256(robust_handle.read()).hexdigest() != (
            "48d1eccfcb3e5546cea0c38b3fdabadd9845de6fa2aecb3335da9f40a0a79a83"
        ):
            raise RuntimeError("Steam robust-list shim checksum is unexpected")

        affinity_shim = by_name["opt/tiny/extra/libdecklite-affinity.so"]
        if elf_machine(archive, affinity_shim) != 183:
            raise RuntimeError("Wine affinity shim is not AArch64")
        if affinity_shim.mode & 0o111 == 0:
            raise RuntimeError("Wine affinity shim is not executable")

        run_steam_handle = archive.extractfile(
            by_name["opt/tiny/steam-arm64/run-steam.sh"]
        )
        if run_steam_handle is None:
            raise RuntimeError("Cannot read the Steam launcher")
        run_steam_source = run_steam_handle.read().decode("utf-8")
        for required_text in (
            'ln -sfn "$steam_root/linuxarm64" "$HOME/.steam/sdkarm64"',
            'ln -sfn steamrtarm64 "$runtime"',
            '"$arm_client/steam"',
            "inherit_xfce_session",
            "DBUS_SESSION_BUS_ADDRESS",
            "XDG_RUNTIME_DIR",
            "TGCOMPAT_ROBUST_LIST=1",
            'LD_PRELOAD="$compat_shim:$mmap_shim:$affinity_shim"',
            "DECKLITE_REMAP_CPU0",
            'source /opt/tiny/wine-manager/wine-affinity-env.sh',
            'mesa_glthread="${DECKLITE_STEAM_GLTHREAD:-false}"',
            'LANG="${LANG:-C.UTF-8}"',
            "SUPPRESS_STEAM_OVERLAY=1",
            "PROTON_USE_XALIA=0",
            "configure-proton.py",
            "patch-ge-proton.py",
            "steam-window-helper.sh --watch",
            "steam_tray.py",
            'patch-steam-webhelper.py --wrapper "$webhelper_wrapper"',
            "-cef-disable-gpu",
            "-cef-force-gpu",
            "STEAM_CEF_SOFTWARE",
            "-chromeosnopreallocate",
            "MESA_SHADER_CACHE_DIR",
            "MESA_SHADER_CACHE_MAX_SIZE",
            "active-root",
            "patch-steam-ui.py --steam-root",
            "-inhibitbootstrap",
            "-nobootstrapperupdate",
            "notify-send --urgency=critical",
        ):
            if required_text not in run_steam_source:
                raise RuntimeError(f"Steam launcher is missing: {required_text}")
        cef_patch_handle = archive.extractfile(by_name['opt/tiny/steam-arm64/patch-steam-webhelper.py'])
        if cef_patch_handle is None:
            raise RuntimeError('Cannot read the Steam webhelper patcher')
        cef_patch_source = cef_patch_handle.read().decode('utf-8')
        ast.parse(cef_patch_source, filename='patch-steam-webhelper.py')
        for required_text in (
            '--disable-dev-shm-usage', '--enable-angle-features=disableSyncControlSupport',
            'LIBGL_KOPPER_DISABLE="${STEAM_CEF_KOPPER_DISABLE:-false}"',
            '--disable-gpu-compositing', 'len(matches) != 1',
        ):
            if required_text not in cef_patch_source:
                raise RuntimeError(f'Steam webhelper patcher is missing: {required_text}')
        if re.search(
            r'(?m)^\s*(?:exec\s+)?"\$steam_root/steam\.sh"(?:\s|$)',
            run_steam_source,
        ):
            raise RuntimeError("Steam launcher still uses the legacy x86 steam.sh path")
        for forbidden in (
            "steam-core-1785799196.zip",
            "compat_core_binary_sha256",
            "status == 42",
        ):
            if forbidden in run_steam_source:
                raise RuntimeError(f"Steam launcher still mixes client builds: {forbidden}")

        lsof_handle = archive.extractfile(by_name["usr/bin/lsof"])
        if lsof_handle is None:
            raise RuntimeError("Cannot read the Android-compatible lsof wrapper")
        lsof_source = lsof_handle.read().decode("utf-8")
        for required_text in (
            "TCP@127.0.0.1:",
            "steamrtarm64[/]steamwebhelper",
            "/opt/tiny/steam-arm64/lsof.real",
        ):
            if required_text not in lsof_source:
                raise RuntimeError(f"Steam lsof wrapper is missing: {required_text}")
        if by_name["opt/tiny/steam-arm64/lsof.real"].mode & 0o111 == 0:
            raise RuntimeError("Preserved Debian lsof is not executable")
        if by_name["usr/bin/lsof"].mode & 0o111 == 0:
            raise RuntimeError("Steam lsof wrapper is not executable")

        steam_ui_patch_handle = archive.extractfile(
            by_name["opt/tiny/steam-arm64/patch-steam-ui.py"]
        )
        if steam_ui_patch_handle is None:
            raise RuntimeError("Cannot read the Steam UI network guard")
        steam_ui_patch_source = steam_ui_patch_handle.read().decode("utf-8")
        ast.parse(steam_ui_patch_source, filename="patch-steam-ui.py")
        for method in (
            "RegisterForDeviceChanges",
            "GetProxyInfo",
            "RegisterForConnectivityTestChanges",
            "GetStartupUserChooserState",
        ):
            if method not in steam_ui_patch_source:
                raise RuntimeError(f"Steam UI network guard is missing: {method}")
        if "allow_absent" not in steam_ui_patch_source:
            raise RuntimeError("Steam UI guard cannot handle version-specific optional methods")

        client_manifest_handle = archive.extractfile(
            by_name["home/tiny/.local/share/Steam/package/steam_client_linuxarm64.manifest"]
        )
        client_installed_handle = archive.extractfile(
            by_name["home/tiny/.local/share/Steam/package/steam_client_linuxarm64.installed"]
        )
        if client_manifest_handle is None:
            raise RuntimeError("Pinned Steam bootstrap manifest is unreadable")
        client_manifest = client_manifest_handle.read().decode("ascii")
        if '"version"\t\t"1785799196"' not in client_manifest:
            raise RuntimeError("Pinned Steam bootstrap manifest has the wrong version")
        if (
            client_manifest.count('\t\t"file"') != 35
            or client_manifest.count('\t\t"sha2"') != 35
            or '"IsBootstrapperPackage"\t\t"1"' not in client_manifest
        ):
            raise RuntimeError("Pinned Steam bootstrap manifest is incomplete")
        if client_installed_handle is None:
            raise RuntimeError("Pinned Steam installed-file inventory marker is unreadable")

        runtime_tool_handle = archive.extractfile(
            by_name[
                "home/tiny/.local/share/Steam/steamapps/common/SteamLinuxRuntime_4-arm64/toolmanifest.vdf"
            ]
        )
        if runtime_tool_handle is None or '"compatmanager_layer_name" "container-runtime"' not in runtime_tool_handle.read().decode("utf-8"):
            raise RuntimeError("Steam Linux Runtime 4 tool manifest is invalid")

        configure_proton_handle = archive.extractfile(
            by_name["opt/tiny/steam-arm64/configure-proton.py"]
        )
        patch_proton_handle = archive.extractfile(
            by_name["opt/tiny/steam-arm64/patch-ge-proton.py"]
        )
        if configure_proton_handle is None or patch_proton_handle is None:
            raise RuntimeError("Cannot read DeckLite Proton configuration tools")
        configure_proton_source = configure_proton_handle.read().decode("utf-8")
        patch_proton_source = patch_proton_handle.read().decode("utf-8")
        ast.parse(configure_proton_source, filename="configure-proton.py")
        ast.parse(patch_proton_source, filename="patch-ge-proton.py")
        for feature in ("CompatToolMapping", "GE-Proton11-6-aarch64", "appid"):
            if feature not in configure_proton_source:
                raise RuntimeError(f"Proton default configuration is missing: {feature}")
        for feature in ("require_tool_appid", "4185400", "/proc/sys/fs/file-max"):
            if feature not in patch_proton_source:
                raise RuntimeError(f"Android PRoot Proton patch is missing: {feature}")

        wine_binary = by_name["usr/lib/wine/aarch64-unix/wine"]
        if elf_machine(archive, wine_binary) != 183:
            raise RuntimeError("Hangover Wine loader is not native AArch64")
        if wine_binary.mode & 0o111 == 0:
            raise RuntimeError("Hangover Wine loader is not executable")
        for tool in ("wineboot", "winecfg", "winefile", "regedit"):
            member = by_name[f"usr/bin/{tool}"]
            if not member.issym() or member.linkname != "wine":
                raise RuntimeError(f"Unexpected Hangover tool link: /usr/bin/{tool}")

        status_handle = archive.extractfile(by_name["var/lib/dpkg/status"])
        if status_handle is None:
            raise RuntimeError("Cannot read dpkg status")
        status = status_handle.read().decode("utf-8")
        for package in (
            "hangover-wine",
            "hangover-libarm64ecfex",
            "hangover-libwow64fex",
            "hangover-wowbox64",
            "libibus-1.0-5",
            "libnm0",
            "libavformat61",
            "libxkbregistry0",
            "cabextract",
            "gstreamer1.0-libav",
            "gstreamer1.0-plugins-bad",
            "gstreamer1.0-plugins-good",
            "gstreamer1.0-plugins-ugly",
            "gnome-system-monitor",
            "libasound2-plugins",
            "libfaudio0",
            "mesa-utils",
            "pciutils",
            "vulkan-tools",
        ):
            if not re.search(
                rf"(?m)^Package: {re.escape(package)}\nStatus: install ok installed$",
                status,
            ):
                raise RuntimeError(f"Package is not registered as installed: {package}")

        marker_handle = archive.extractfile(
            by_name["opt/tiny/wine-manager/hangover-layer.json"]
        )
        if marker_handle is None:
            raise RuntimeError("Cannot read Hangover layer marker")
        marker = json.loads(marker_handle.read())
        if marker.get("packages", {}).get("hangover-wine") != "11.16~trixie":
            raise RuntimeError("Unexpected preinstalled Hangover version")

        status_records = parse_status(status)
        available = {
            name
            for name, record in status_records.items()
            if record.get("Status") == "install ok installed"
        }
        for record in status_records.values():
            if record.get("Status") != "install ok installed":
                continue
            for provided in record.get("Provides", "").split(","):
                match = re.match(r"\s*([a-z0-9][a-z0-9+.-]*)", provided)
                if match:
                    available.add(match.group(1))
        for package in marker.get("packages", {}):
            record = status_records.get(package)
            if record is None:
                raise RuntimeError(f"Layer package has no dpkg record: {package}")
            for field in ("Pre-Depends", "Depends"):
                for choices in dependency_groups(record.get(field, "")):
                    if not any(choice in available for choice in choices):
                        raise RuntimeError(
                            f"Unsatisfied {package} dependency: {' | '.join(choices)}"
                        )

        stop_wine_handle = archive.extractfile(by_name["opt/tiny/wine-manager/stop-wine.py"])
        if stop_wine_handle is None:
            raise RuntimeError("Cannot read Stop Wine helper")
        stop_wine_source = stop_wine_handle.read().decode("utf-8")
        ast.parse(stop_wine_source, filename="stop-wine.py")
        for guard in (
            "os.readlink(entry / 'root') != os.readlink(PROC / 'self/root')",
            "entry.stat().st_uid != (PROC / 'self').stat().st_uid",
            "os.path.samestat",
            "identity(pid) != expected",
            "identity(self.pid) == self.expected",
            "os.pidfd_open(pid, 0)",
            "signal.pidfd_send_signal(self.fd, sig)",
            "select.select([self.fd], [], [], 0)",
            "group_alive(self.pid, self.expected[0])",
            "if args.list or not args.yes:",
        ):
            if guard not in stop_wine_source:
                raise RuntimeError(f"Stop Wine safety guard missing: {guard}")

        gui_handle = archive.extractfile(
            by_name["opt/tiny/wine-manager/wine_manager.py"]
        )
        if gui_handle is None:
            raise RuntimeError("Cannot read Wine Manager")
        gui_source = gui_handle.read().decode("utf-8")
        ast.parse(gui_source, filename="wine_manager.py")
        for feature in (
            "Gtk.Window",
            "wowbox64.dll",
            "libwow64fex.dll",
            "cwd=path.parent",
            "LD_PRELOAD",
            "libmmap_shim.so",
            "Install common game runtimes",
            "Install legacy audio / video",
            "Install .NET 4.8 + XNA 4",
            "RUNTIMES",
            "RUN_EXE",
            "DECKLITE_WINE_DISPLAY_MODE",
            "DISPLAY_MODE_FILE",
            "Global game display mode saved",
            "DECKLITE_WINE_LOCALE",
            "DECKLITE_WINE_UTC_OFFSET",
            "TIMEZONE_FILE",
            "Time zone (UTC)",
            "on_timezone_changed",
            'environment["TZ"] = timezone_env(offset)',
            "LOCALE_FILE",
            "Global Windows language saved",
            "Traditional Chinese",
            "Russian",
            "Automatic: fullscreen or windowed as selected in the game",
            "Interface language",
            "on_ui_language_changed",
            "combo.handler_block(handler)",
            "combo.handler_unblock(handler)",
            "load_language()",
            "save_language(chosen)",
            "Safe virtual desktop (compatibility fallback)",
            "Game Complete (VC++/DirectX/audio; recommended)",
            ".NET/XNA Complete (separate compatibility template)",
            ".decklite-template-request",
        ):
            if feature not in gui_source:
                raise RuntimeError(f"Wine Manager is missing feature: {feature}")

        ui_handle = archive.extractfile(by_name["opt/tiny/wine-manager/ui_i18n.py"])
        if ui_handle is None:
            raise RuntimeError("Cannot read Wine Manager translations")
        ui_source = ui_handle.read().decode("utf-8")
        ui_tree = ast.parse(ui_source, filename="ui_i18n.py")
        ui_data = {node.targets[0].id: ast.literal_eval(node.value)
                   for node in ui_tree.body if isinstance(node, ast.Assign)
                   and isinstance(node.targets[0], ast.Name)
                   and node.targets[0].id in {"LANGUAGES", "CATALOG"}}
        if set(ui_data.get("LANGUAGES", {})) != {"en", "zh_TW", "zh_CN", "ja", "ru"}:
            raise RuntimeError("Wine Manager must include all five interface languages")
        if not ui_data.get("CATALOG") or any(len(values) != 4 for values in ui_data["CATALOG"].values()):
            raise RuntimeError("Incomplete Wine Manager translation catalog")
        if 'wine-manager-language' not in ui_source or 'else "en"' not in ui_source:
            raise RuntimeError("Separate English-default interface preference is missing")

        run_exe_handle = archive.extractfile(by_name["opt/tiny/steam-arm64/run-exe.sh"])
        runtime_installer_handle = archive.extractfile(
            by_name["opt/tiny/wine-manager/install-game-runtimes.sh"]
        )
        prepare_prefix_handle = archive.extractfile(
            by_name["opt/tiny/wine-manager/prepare-prefix.sh"]
        )
        prefix_runner_handle = archive.extractfile(
            by_name["opt/tiny/wine-manager/wine-prefix-run"]
        )
        if (
            run_exe_handle is None
            or prepare_prefix_handle is None
            or prefix_runner_handle is None
            or runtime_installer_handle is None
        ):
            raise RuntimeError("Cannot read Hangover launchers")
        run_exe_source = run_exe_handle.read().decode("utf-8")
        prepare_prefix_source = prepare_prefix_handle.read().decode("utf-8")
        prefix_runner_source = prefix_runner_handle.read().decode("utf-8")
        runtime_installer_source = runtime_installer_handle.read().decode("utf-8")
        if "source /opt/tiny/wine-manager/wine-midi-env.sh" not in prefix_runner_source:
            raise RuntimeError("Wine launcher is missing the software MIDI fallback")
        for required_text in (
            "DECKLITE_WINE_DISPLAY_MODE",
            "wine-display-mode",
            "/desktop=DeckLite-$$,$desktop_size",
            "DECKLITE_WINE_DESKTOP_SIZE",
            "xdotool getdisplaygeometry",
            "source /opt/tiny/wine-manager/wine-region-env.sh",
            "DXVK_CONFIG_FILE",
            "dxvk-game.conf",
            "DECKLITE_WINE_PRESENT_MODE",
            "DECKLITE_WINE_VSYNC",
            "libdecklite-affinity.so",
            "DECKLITE_REMAP_CPU0",
            "DECKLITE_WINE_STARTUP_FOCUS",
            "wine-game-launch.exe",
            "safe|borderless|auto)",
            'display_mode="${display_mode:-auto}"',
            "--decklite-observe=$$",
            "auto-display-x11.py",
            "--decklite-fit=$desktop_size",
        ):
            if required_text not in run_exe_source:
                raise RuntimeError(f"Wine safe-fullscreen launcher is missing: {required_text}")
        for source_text in (prepare_prefix_source, prefix_runner_source, runtime_installer_source):
            if "source /opt/tiny/wine-manager/wine-region-env.sh" not in source_text:
                raise RuntimeError("Wine tools must share Windows locale and UTC preference")
        region_source = archive.extractfile(by_name["opt/tiny/wine-manager/wine-region-env.sh"]).read().decode("utf-8")
        for token in ('DECKLITE_WINE_LOCALE', 'wine-locale', 'locale="en_US.UTF-8"',
                      'zh_TW.UTF-8', 'ru_RU.UTF-8', 'DECKLITE_WINE_UTC_OFFSET',
                      'wine-timezone', 'tz=UTC0', 'TZ="$tz"'):
            if token not in region_source:
                raise RuntimeError(f"Incomplete Wine region preference: {token}")
        timezone_source = archive.extractfile(by_name["opt/tiny/wine-manager/wine_timezone.py"]).read().decode("utf-8")
        ast.parse(timezone_source, filename="wine_timezone.py")
        if 'DEFAULT_TIMEZONE = "0"' not in timezone_source or 'UTC+00:00 (GMT / Greenwich)' not in timezone_source:
            raise RuntimeError("Wine time zone must default to Greenwich UTC+00:00")
        if 'else "en_US.UTF-8"' not in gui_source or 'return "en_US.UTF-8"' not in gui_source:
            raise RuntimeError("Windows language must default to English")
        focus_helper = archive.extractfile(by_name["opt/tiny/wine-manager/wine-game-launch.exe"])
        if focus_helper is None:
            raise RuntimeError("Cannot read Wine startup focus helper")
        helper_bytes = focus_helper.read()
        if len(helper_bytes) < 128 or helper_bytes[:2] != b"MZ":
            raise RuntimeError("Wine focus helper is not a PE executable")
        pe_offset = struct.unpack_from("<I", helper_bytes, 0x3C)[0]
        if (pe_offset + 6 > len(helper_bytes)
                or helper_bytes[pe_offset:pe_offset + 4] != b"PE\0\0"
                or struct.unpack_from("<H", helper_bytes, pe_offset + 4)[0] != 0xAA64):
            raise RuntimeError("Wine focus helper is not native ARM64")
        for imported_api in (b"CreateProcessW", b"GetForegroundWindow", b"SetForegroundWindow",
                             b"GetClientRect", b"SetWindowPos", b"SetWindowLongPtrW", b"RedrawWindow",
                             b"MoveFileExW", b"DeleteFileW", b"IsIconic"):
            if imported_api not in helper_bytes:
                raise RuntimeError(f"Wine focus helper is missing {imported_api!r}")
        if b"CreateWindowExW" in helper_bytes:
            raise RuntimeError("Wine borderless helper must not create input-stealing overlays")
        # Optimized ARM64 clang emits the short observer flag/path as immediate
        # instructions, not a contiguous UTF-16 string. Check the launch protocol
        # here; the payload verifier compares the complete PE with the build.
        if "--decklite-observe=$$" not in run_exe_source:
            raise RuntimeError("Wine automatic-display observer launch is missing")
        for borderless_path, tokens in (
            ("usr/local/bin/run-exe-fullscreen", (b"DECKLITE_WINE_DISPLAY_MODE=borderless", b'"$@"')),
            ("opt/tiny/wine-manager/black-desktop.reg", (b'"Background"="0 0 0"',)),
            ("opt/tiny/wine-manager/wine_manager.py", (b'"borderless"', b"set game to Windowed")),
            ("opt/tiny/wine-manager/borderless-x11.py", (b'XClearArea', b'time.monotonic() + 150', b'state == previous')),
            ("opt/tiny/wine-manager/auto-display-x11.py", (b'XShapeCombineRectangles', b'decklite-viewport.support', b'_NET_ACTIVE_WINDOW', b'parse_mode', b'valid_view')),
            ("usr/local/bin/wine-manager", (b'*.exe)', b'exec /opt/tiny/steam-arm64/run-exe.sh "$@"')),
            ("home/tiny/.local/share/applications/mimeinfo.cache", (
                b'[MIME Cache]',
                b'application/x-msdownload=wine-manager.desktop;',
                b'application/x-ms-dos-executable=wine-manager.desktop;',
                b'application/vnd.microsoft.portable-executable=wine-manager.desktop;',
                b'application/x-msi=wine-manager.desktop;',
            )),
            ("opt/tiny/wine-manager/container-start.sh", (
                b'update-desktop-database "$HOME/.local/share/applications"',
            )),
        ):
            handle = archive.extractfile(by_name[borderless_path])
            if handle is None:
                raise RuntimeError(f"Missing borderless implementation in {borderless_path}")
            data = handle.read()
            if not all(token in data for token in tokens):
                raise RuntimeError(f"Incomplete borderless implementation in {borderless_path}")
        if ".decklite-black-desktop" not in prepare_prefix_source:
            raise RuntimeError("Black desktop default is not applied once per prefix")
        for line in prepare_prefix_source.splitlines():
            if any(token in line for token in ("wineboot --update", "wine regedit /S", "regedit 'Z:", "wine reg delete", '"$prefix" stage')) and "9>&-" not in line:
                raise RuntimeError("A persistent Wine child can inherit the prefix initialization lock")
        for source_name, source_text in (
            ("run-exe", run_exe_source),
            ("prepare-prefix", prepare_prefix_source),
            ("wine-prefix-run", prefix_runner_source),
        ):
            for required_text in ("libwow64fex.dll", "libmmap_shim.so", "LD_PRELOAD"):
                if required_text not in source_text:
                    raise RuntimeError(
                        f"{source_name} does not handle shared-storage Win32 execution: {required_text}"
                    )

        for source_name, source_text in (
            ("prepare-prefix", prepare_prefix_source),
            ("wine-prefix-run", prefix_runner_source),
        ):
            if "source /opt/tiny/wine-manager/wine-affinity-env.sh" not in source_text:
                raise RuntimeError(f"{source_name} omits the default Wine CPU policy")
        for policy_path in (
            "opt/tiny/wine-manager/wine-affinity-env.sh",
            "opt/tiny/wine-manager/container-start.sh",
        ):
            policy_handle = archive.extractfile(by_name[policy_path])
            if policy_handle is None:
                raise RuntimeError(f"Cannot read Wine CPU policy: {policy_path}")
            policy_source = policy_handle.read().decode("utf-8")
            required = (
                'DECKLITE_REMAP_CPU0="${DECKLITE_REMAP_CPU0:-1}"'
                if policy_path.endswith("wine-affinity-env.sh")
                else "source /opt/tiny/wine-manager/wine-affinity-env.sh"
            )
            if required not in policy_source:
                raise RuntimeError(f"Default wineserver CPU policy missing: {policy_path}")
            if policy_path.endswith("wine-affinity-env.sh"):
                for token in ("cpu_preference=big", "wine-cpu-policy", "DECKLITE_WINE_CPUS", "custom:*"):
                    if token not in policy_source:
                        raise RuntimeError(f"Wine CPU preference handling missing: {token}")
        for cpu_path, tokens in (
            ("opt/tiny/wine-manager/cpu_policy.py", ("sched_getaffinity", "cpu_capacity", "cpuinfo_max_freq", "save_preference")),
            ("opt/tiny/wine-manager/wine_manager.py", ("on_cpu_cores", "Gtk.CheckButton", "save_preference")),
        ):
            handle = archive.extractfile(by_name[cpu_path])
            if handle is None:
                raise RuntimeError(f"Cannot read CPU selector: {cpu_path}")
            source = handle.read().decode("utf-8")
            if not all(token in source for token in tokens):
                raise RuntimeError(f"Incomplete CPU selector: {cpu_path}")

        for required_text in (
            "prefix-templates",
            "game-complete",
            "dotnet-xna-complete",
            "cp -a --reflink=auto",
            "wineboot --update",
        ):
            if required_text not in prepare_prefix_source:
                raise RuntimeError(f"Offline Wine template support is missing: {required_text}")

        game_environment_handle = archive.extractfile(
            by_name["etc/profile.d/decklite-game-performance.sh"]
        )
        if game_environment_handle is None:
            raise RuntimeError("Cannot read global game performance defaults")
        game_environment_source = game_environment_handle.read().decode("utf-8")
        for required_text in (
            "MESA_SHADER_CACHE_MAX_SIZE",
            "DXVK_STATE_CACHE",
            "PULSE_LATENCY_MSEC",
            "mesa_glthread",
            "vblank_mode",
            "MESA_VK_WSI_PRESENT_MODE",
            "__GL_SYNC_TO_VBLANK",
            "DECKLITE_TURNIP_SAFE_RENDER",
            "noubwc",
            "SDL_AUDIODRIVER",
            "ALSOFT_DRIVERS",
        ):
            if required_text not in game_environment_source:
                raise RuntimeError(
                    f"Global game performance defaults are missing: {required_text}"
                )

        loader_profile_handle = archive.extractfile(
            by_name["etc/profile.d/00-decklite-glibc-loader.sh"]
        )
        if loader_profile_handle is None:
            raise RuntimeError("Cannot read the glibc loader isolation profile")
        loader_profile_source = loader_profile_handle.read().decode("utf-8")
        for required_text in (
            "/files/bootstrap/lib",
            "/lib/aarch64-linux-gnu:/usr/lib/aarch64-linux-gnu:/lib:/usr/lib",
            "LD_LIBRARY_PATH",
        ):
            if required_text not in loader_profile_source:
                raise RuntimeError(f"glibc loader isolation is missing: {required_text}")

        for verb in (
            "vcrun2005",
            "vcrun2022",
            "d3dx9",
            "xact",
            "directmusic",
            "quartz",
            "dotnet48",
            "xna40",
            "decklite-dotnet-mscoree-repaired",
            "x86_netfx-mscoree_dll",
            "amd64_netfx-mscoree_dll",
        ):
            if verb not in runtime_installer_source:
                raise RuntimeError(f"Game runtime profile is missing: {verb}")
        if "/usr/local/bin/winetricks" not in runtime_installer_source:
            raise RuntimeError("Game runtime profiles do not use pinned Winetricks")

        resource_monitor_handle = archive.extractfile(
            by_name["usr/local/bin/resource-monitor"]
        )
        if resource_monitor_handle is None:
            raise RuntimeError("Cannot read Resource Monitor launcher")
        resource_monitor_source = resource_monitor_handle.read().decode("utf-8")
        for feature in (
            "decklite-resource-monitor",
            "KGSL",
            "per-process",
        ):
            if feature not in resource_monitor_source:
                raise RuntimeError(f"Resource Monitor launcher is missing: {feature}")

        live_monitor_handle = archive.extractfile(
            by_name["usr/local/bin/decklite-resource-monitor"]
        )
        if live_monitor_handle is None:
            raise RuntimeError("Cannot read DeckLite Resource Monitor")
        live_monitor_source = live_monitor_handle.read().decode("utf-8")
        for feature in (
            "/sys/devices/system/cpu/online",
            "/cpuidle/state*/time",
            "/sys/class/kgsl/kgsl-3d0/gpu_busy_percentage",
            "/proc/meminfo",
            "/proc/[0-9]*",
            "Container CPU",
            "Device CPU",
            "--self-test",
            "READABLE_PROCESSES",
        ):
            if feature not in live_monitor_source:
                raise RuntimeError(f"Live Resource Monitor is missing: {feature}")

        desktop_launcher_handle = archive.extractfile(
            by_name["opt/tiny/start-desktop.sh"]
        )
        if desktop_launcher_handle is None:
            raise RuntimeError("Cannot read the desktop launcher")
        desktop_launcher_source = desktop_launcher_handle.read().decode("utf-8")
        for feature in (
            "appearance-defaults-v1",
            "desktop-icons-defaults-v1",
            "apply_desktop_icon_defaults",
            "/desktop-icons/file-icons/show-removable",
            "Fluent-Dark",
            "/usr/share/backgrounds/decklite-black.svg",
            "prefer-dark",
            "ensure_dynamic_loader",
            "desktop_process_ready",
            "Refreshing the dynamic loader cache",
            "LD_TRACE_LOADED_OBJECTS=1 /usr/bin/xfconf-query",
            "trying the real XFCE startup",
            "/sbin/ldconfig",
            '"$state" != Z',
        ):
            if feature not in desktop_launcher_source:
                raise RuntimeError(f"Dark desktop default is missing: {feature}")

        container_start_handle = archive.extractfile(
            by_name["opt/tiny/wine-manager/container-start.sh"]
        )
        if container_start_handle is None:
            raise RuntimeError("Cannot read the first-boot launcher")
        container_start_source = container_start_handle.read().decode("utf-8")
        for feature in (
            "if /sbin/ldconfig; then",
            "Never trust a first-boot marker",
            "sudo touch /var/lib/decklite-hangover-ldconfig",
            "prepare-prefix.sh",
        ):
            if feature not in container_start_source:
                raise RuntimeError(f"First-boot loader repair is missing: {feature}")

        window_helper_handle = archive.extractfile(
            by_name["opt/tiny/steam-arm64/steam-window-helper.sh"]
        )
        window_controls_handle = archive.extractfile(
            by_name["opt/tiny/steam-arm64/steam_window_controls.py"]
        )
        steam_tray_handle = archive.extractfile(
            by_name["opt/tiny/steam-arm64/steam_tray.py"]
        )
        if (
            window_helper_handle is None
            or window_controls_handle is None
            or steam_tray_handle is None
        ):
            raise RuntimeError("Cannot read Steam window controls")
        window_helper_source = window_helper_handle.read().decode("utf-8")
        window_controls_source = window_controls_handle.read().decode("utf-8")
        steam_tray_source = steam_tray_handle.read().decode("utf-8")
        ast.parse(window_controls_source, filename="steam_window_controls.py")
        ast.parse(steam_tray_source, filename="steam_tray.py")
        for feature in (
            "--watch",
            "--reset",
            "xdotool windowsize",
            "window-mode-v1",
            "_MOTIF_WM_HINTS",
            "xfwm4 --replace",
            "_NET_FRAME_EXTENTS",
        ):
            if feature not in window_helper_source:
                raise RuntimeError(f"Steam window helper is missing: {feature}")
        for feature in ("alt+F10", "alt+F", "Restore medium size", "HELPER"):
            if feature not in window_controls_source:
                raise RuntimeError(f"Steam window controls are missing: {feature}")
        for feature in ("Gtk.StatusIcon", "Show Steam", "Quit Steam", "steam-tray.lock"):
            if feature not in steam_tray_source:
                raise RuntimeError(f"Steam tray helper is missing: {feature}")

        stage_update_handle = archive.extractfile(
            by_name["opt/tiny/steam-arm64/stage-update.py"]
        )
        if stage_update_handle is None:
            raise RuntimeError("Cannot read the staged Steam updater")
        stage_update_source = stage_update_handle.read().decode("utf-8")
        ast.parse(stage_update_source, filename="stage-update.py")
        for feature in (
            "candidate.previous",
            ".decklite-update-candidate.json",
            "link_user_data",
            "ldd",
            "elf_machine",
            "patch-steam-ui.py",
        ):
            if feature not in stage_update_source:
                raise RuntimeError(f"Staged Steam updater is missing: {feature}")

        steam_symlinks = [
            member
            for member in members
            if member.issym()
            and normalize(member.name).startswith("home/tiny/.local/share/Steam/")
        ]
        if len(steam_symlinks) < 100:
            raise RuntimeError(
                f"Steam runtime symlinks were not preserved ({len(steam_symlinks)} found)"
            )
        codec_link = by_name.get(REQUIRED_STEAM_SYMLINK)
        if codec_link is None or not codec_link.issym():
            raise RuntimeError(f"Steam codec link is not a symlink: {REQUIRED_STEAM_SYMLINK}")

        for script in REQUIRED:
            if (script.endswith(".py") and script.startswith("opt/tiny/")) or script.endswith(
                (
                    ".sh",
                    "/steam-arm64",
                    "/run-exe",
                    "/wine-manager",
                    "/wine-prefix-run",
                )
            ):
                if by_name[script].mode & 0o111 == 0:
                    raise RuntimeError(f"Script is not executable: {script}")

    print(
        "Verified Steam ARM64, runtime symlinks, preinstalled Hangover 11.16, "
        "Wine Manager, X11 desktop defaults, Win32/Win64 backends, permissions, path safety, client code "
        f"validation, and Tiny metadata: {path}"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", required=True, type=Path)
    args = parser.parse_args()
    verify(args.archive.resolve())


if __name__ == "__main__":
    main()
