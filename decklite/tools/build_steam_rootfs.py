#!/usr/bin/env python3
"""Augment Tiny Container's official XFCE image with native ARM64 Steam."""

from __future__ import annotations

import argparse
import copy
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import tarfile
import tempfile


STEAM_DESTINATION = "home/tiny/.local/share/Steam"
GE_PROTON_DESTINATION = (
    f"{STEAM_DESTINATION}/compatibilitytools.d/GE-Proton11-6-aarch64"
)
STEAMRT4_DESTINATION = (
    f"{STEAM_DESTINATION}/steamapps/common/SteamLinuxRuntime_4-arm64"
)
WINE_PREFIX_TEMPLATES_DESTINATION = "opt/tiny/wine-manager/prefix-templates"
SYMLINK_MANIFEST = ".decklite-steam-symlinks.json"
WINETRICKS_SHA256 = "431f82fc74000e6c864409f1d8fb495d696c03928808e3e8acffc45179312a7b"


def normalize(value: str) -> str:
    while value.startswith("./"):
        value = value[2:]
    value = value.rstrip("/")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"Unsafe archive path: {value!r}")
    return path.as_posix() if value else "."


def ownership(path: str) -> tuple[int, int, str, str]:
    if path == "home/tiny" or path.startswith("home/tiny/"):
        return 1000, 1000, "tiny", "tiny"
    return 0, 0, "root", "root"


def file_mode(path: str, source: Path) -> int:
    if path.startswith("home/tiny/Desktop/") and path.endswith(".desktop"):
        return 0o755
    if path.startswith(("opt/tiny/", "usr/local/bin/")) and (
        path.endswith((".sh", ".py")) or path.startswith("usr/local/bin/")
    ):
        return 0o755
    try:
        with source.open("rb") as handle:
            header = handle.read(4)
        if header.startswith(b"#!") or header == b"\x7fELF":
            return 0o755
    except OSError:
        pass
    return 0o644


def tar_info(path: str, *, directory: bool, source: Path | None = None) -> tarfile.TarInfo:
    info = tarfile.TarInfo(path)
    info.mtime = int(os.environ.get("SOURCE_DATE_EPOCH", "0"))
    info.uid, info.gid, info.uname, info.gname = ownership(path)
    if directory:
        info.type = tarfile.DIRTYPE
        info.mode = 0o755
        info.size = 0
    else:
        if source is None:
            raise ValueError("source is required for a regular file")
        info.type = tarfile.REGTYPE
        info.mode = file_mode(path, source)
        info.size = source.stat().st_size
    return info


def add_file(target: tarfile.TarFile, path: str, source: Path) -> None:
    with source.open("rb") as handle:
        target.addfile(tar_info(path, directory=False, source=source), handle)


def add_symlink(target: tarfile.TarFile, path: str, linkname: str) -> None:
    info = tarfile.TarInfo(path)
    info.type = tarfile.SYMTYPE
    info.linkname = linkname
    info.mode = 0o777
    info.size = 0
    info.mtime = int(os.environ.get("SOURCE_DATE_EPOCH", "0"))
    info.uid, info.gid, info.uname, info.gname = ownership(path)
    target.addfile(info)


def output_tar_context(output: Path):
    try:
        archive = tarfile.open(output, "w:zst", level=10)
        return archive, lambda: None
    except (tarfile.CompressionError, ValueError):
        zstd = shutil.which("zstd")
        if not zstd:
            raise RuntimeError("Python 3.14+ or the zstd command is required")
        temporary = Path(tempfile.mkstemp(suffix=".tar", dir=output.parent)[1])
        archive = tarfile.open(temporary, "w")

        def finalize() -> None:
            subprocess.run(
                [zstd, "-T0", "-10", "-f", str(temporary), "-o", str(output)],
                check=True,
            )
            temporary.unlink()

        return archive, finalize


def patched_metadata(source_text: str) -> bytes:
    # Tiny Container validates this value with ^[a-zA-Z0-9]+$ in its install
    # confirmation dialog. Keep it alphanumeric or the Install button is disabled.
    heading = """code: decklitesteamarm64
name: DeckLite Steam ARM64 4.3.4
description: >-
  Steam-first Tiny Container image with Valve's native ARM64 Steam client,
  Proton 11/FEX support for x86 and x86_64 Windows games, preinstalled
  Hangover WOW64, and a graphical Wine prefix manager for Win32/Win64 EXEs.
  Software MIDI output and clean desktop defaults included. Use APK 4.3.2 for
  language selection and corrected mouse/touchpad input. Optional authenticated
  USB debugging toolbox is off by default.
  Termux:X11 is the default desktop frontend. Allow at least 20 GiB of free
  internal app storage while importing.
preview:"""
    result, replacements = re.subn(
        r"\Acode:.*?^preview:", heading, source_text, count=1, flags=re.MULTILINE | re.DOTALL
    )
    if replacements != 1:
        raise RuntimeError("Could not patch Tiny Container metadata heading")

    # Never put dynamic runtime directories in PRoot's lstat cache. X11,
    # PipeWire and D-Bus sockets are created/replaced after PRoot starts; an
    # assured tmp/run path can therefore preserve a missing or stale socket
    # and leave the Android X11 activity on a permanent black surface.
    volatile_runtime_paths = "$CACHE_DIR/tmp, $CACHE_DIR/run, "
    if volatile_runtime_paths not in result:
        raise RuntimeError("Could not find volatile runtime paths in lstat-cache metadata")
    result = result.replace(volatile_runtime_paths, "", 1)

    steam_commands = """quick_commands:
- type: command
  name: Stop all Wine
  description: Stops Wine and Proton games in this container. Unsaved progress will be lost. Keeps native Steam and the X11 desktop running.
  command: python3 /opt/tiny/wine-manager/stop-wine.py --yes
- type: commands
  name: Steam ARM64 and Windows games
  description: Native ARM64 Steam client; Proton 11/FEX handles x86/x86_64 games.
  commands:
  - type: command
    name: Launch Steam ARM64
    command: steam-arm64
  - type: command
    name: Stage Steam update candidate
    description: Downloads a new client separately; the tested client is not replaced.
    command: python3 /opt/tiny/steam-arm64/stage-update.py
  - type: command
    name: Test Steam update candidate
    description: Close Steam first. Runs the candidate without making it the default.
    command: /opt/tiny/steam-arm64/test-update.sh
  - type: command
    name: Activate tested Steam candidate
    description: Close Steam first. Makes the staged candidate the default.
    command: /opt/tiny/steam-arm64/activate-update.sh
  - type: command
    name: Rollback to tested Steam
    description: Close Steam first. Restores build 1785799196 without deleting games or login data.
    command: /opt/tiny/steam-arm64/rollback-update.sh
  - type: command
    name: Open Steam log
    command: less /home/tiny/steam-arm64.log
  - type: command
    name: Test hardware keyboard
    description: Opens xev so physical key events can be checked in the X11 desktop.
    command: /opt/tiny/steam-arm64/test-keyboard.sh
  - type: command
    name: Open Wine Manager
    description: Manage prefixes, Win32/Win64 backends and DXVK, or choose an EXE/MSI.
    command: wine-manager
"""
    if "quick_commands:\n" not in result:
        raise RuntimeError("Could not find quick_commands in Tiny metadata")
    result = result.replace("quick_commands:\n", steam_commands, 1)

    wine_group = """- type: commands
  name: Run Windows Software
  description: |
    Hangover 11.16 is preinstalled for 32-bit and 64-bit Windows software.
    Use Wine Manager to create isolated prefixes, switch Box64/FEX, and control DXVK.
    Keep Windows software inside Tiny Container rather than Android shared storage.
  commands:
  - {type: command, name: Open Wine Manager, command: wine-manager}
  - {type: command, name: Initialize default prefix, command: /opt/tiny/wine-manager/prepare-prefix.sh /home/tiny/.wine}
  - {type: command, name: Open Wine Manager log, command: less /home/tiny/wine-manager.log}
  - type: commands
    name: Useful Wine Commands"""
    result, replacements = re.subn(
        r"(?ms)^- type: commands\n  name: Run Windows Software\n.*?"
        r"^  - type: commands\n    name: Useful Wine Commands",
        wine_group,
        result,
        count=1,
    )
    if replacements != 1:
        raise RuntimeError("Could not patch the official Hangover quick-command group")

    old_option = """    name: Hangover configuration
    description: Enable to ensure Hangover works properly.
    args: [--wine=/usr/bin/wine]
    ld_preload: [/opt/tiny/extra/libmmap_shim.so]
    post_start_container_command: wineserver -p
    enabled: false"""
    new_option = """    name: Hangover configuration
    description: Preinstalled Hangover support for Win32 and Win64 applications.
    args: [--wine=/usr/bin/wine]
    ld_preload: [/opt/tiny/extra/libmmap_shim.so]
    post_start_container_command: /opt/tiny/wine-manager/container-start.sh
    enabled: true"""
    if old_option not in result:
        raise RuntimeError("Could not enable the official Hangover container option")
    result = result.replace(old_option, new_option, 1)

    for feature_type, enabled in (("avnc", "false"), ("x11", "true")):
        pattern = rf"(?ms)(^- type: {feature_type}\n.*?^  enabled: )(?:true|false)(?=\n)"
        result, replacements = re.subn(pattern, rf"\g<1>{enabled}", result, count=1)
        if replacements != 1:
            raise RuntimeError(f"Could not set the {feature_type} desktop feature")

    # The upstream inline command backgrounds startxfce4 and discards all of
    # its output.  On a busy first boot (while the offline Wine prefix is being
    # materialised) that process can exit before XFCE is ready, leaving a live
    # X server with only a black root window.  Use our bounded, logged launcher
    # for both frontends so audio failure cannot block the desktop indefinitely
    # and XFCE is retried when the first start races another first-boot task.
    for feature_type in ("avnc", "x11"):
        pattern = rf"(?ms)(^- type: {feature_type}\n.*?^  command:) \|\n(?:^    [^\n]*\n)+"
        replacement = rf"\g<1> /opt/tiny/start-desktop.sh {feature_type}\n"
        result, replacements = re.subn(pattern, replacement, result, count=1)
        if replacements != 1:
            raise RuntimeError(
                f"Could not install the resilient {feature_type} desktop launcher"
            )

    # This image targets the user's Adreno 740 Galaxy Tab and X11 is already
    # the default display. Enable the fastest system-wide Mesa path once here;
    # it affects native Linux, Steam CEF, Proton and standalone Wine rather
    # than carrying per-game launch flags. The option remains reversible in
    # Tiny Container before boot for non-Adreno devices.
    pattern = (
        r"(?ms)(    name: Turnip \+ Zink Acceleration with DRI3\n"
        r".*?^      enabled: )(?:true|false)(?=\n)"
    )
    result, replacements = re.subn(pattern, r"\g<1>true", result, count=1)
    if replacements != 1:
        raise RuntimeError("Could not enable the Turnip + Zink DRI3 graphics option")

    # Steam's ARM64 client needs robust-list and SysV IPC emulation which is
    # implemented by Tiny Container's current PRoot, not its legacy default.
    result, replacements = re.subn(
        r"(?m)^(  \$BIN_DIR/)proot(?= )",
        r"\1proot-latest",
        result,
        count=1,
    )
    if replacements != 1:
        raise RuntimeError("Could not select proot-latest for the Steam container")

    # Tiny Container's host bootstrap contains Android/Bionic libraries used
    # by PRoot itself. Passing that directory into the Debian guest makes a
    # glibc program load Bionic libpcre2, whose `libc.so` dependency resolves
    # to Debian's linker script and aborts XFCE with "invalid ELF header".
    # The guest has complete Mesa and Wine libraries of its own.
    host_library_path = "LD_LIBRARY_PATH=$EXTRA_LD_LIBRARY_PATH"
    guest_library_path = (
        "LD_LIBRARY_PATH=/lib/aarch64-linux-gnu:"
        "/usr/lib/aarch64-linux-gnu:/lib:/usr/lib"
    )
    if result.count(host_library_path) != 1:
        raise RuntimeError("Could not isolate the Debian guest library path")
    result = result.replace(host_library_path, guest_library_path, 1)

    # Android denies application UIDs access to /proc/cgroups.  GNOME System
    # Monitor treats that denial as fatal, so bind a harmless synthetic view in
    # both the normal and export PRoot commands.  The real per-process CPU and
    # memory counters remain sourced from the readable /proc entries.
    proc_stat_bind = "--bind=$CONTAINER_DIR/proc/.stat:/proc/stat"
    proc_android_binds = (
        "--bind=$CONTAINER_DIR/proc/.cgroups:/proc/cgroups "
        "--bind=$CONTAINER_DIR/proc/.diskstats:/proc/diskstats "
        "--bind=$CONTAINER_DIR/proc/.net_dev:/proc/net/dev"
    )
    if result.count(proc_stat_bind) != 2:
        raise RuntimeError("Could not locate both Tiny PRoot /proc/stat bindings")
    result = result.replace(
        proc_stat_bind,
        f"{proc_stat_bind} {proc_android_binds}",
    )
    return result.encode("utf-8")


def gather_tree(
    root: Path, destination: str
) -> tuple[set[str], dict[str, Path], dict[str, str]]:
    directories: set[str] = {destination}
    files: dict[str, Path] = {}
    symlinks: dict[str, str] = {}
    for item in sorted(root.rglob("*")):
        relative = item.relative_to(root).as_posix()
        if not destination and ("__pycache__" in item.relative_to(root).parts or item.suffix == ".pyc"):
            continue  # Never package Windows development bytecode from the overlay.
        target = normalize(f"{destination}/{relative}" if destination else relative)
        if item.is_symlink():
            symlinks[target] = os.readlink(item)
        elif item.is_dir():
            directories.add(target)
        elif item.is_file():
            files[target] = item
    return directories, files, symlinks


def portable_steam_symlinks(steam_payload: Path) -> dict[str, str]:
    manifest = steam_payload / SYMLINK_MANIFEST
    if not manifest.is_file():
        return {}
    raw = json.loads(manifest.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise RuntimeError(f"Invalid Steam symlink manifest: {manifest}")
    result: dict[str, str] = {}
    for relative, linkname in raw.items():
        if not isinstance(relative, str) or not isinstance(linkname, str):
            raise RuntimeError(f"Invalid Steam symlink entry: {relative!r}")
        safe_relative = normalize(relative)
        if PurePosixPath(linkname).is_absolute():
            raise RuntimeError(f"Absolute Steam symlink target: {relative} -> {linkname}")
        result[normalize(f"{STEAM_DESTINATION}/{safe_relative}")] = linkname
    return result


def archive_paths(path: Path) -> set[str]:
    with tarfile.open(path, "r:*") as archive:
        return {
            name
            for member in archive
            if (name := normalize(member.name)) != "."
        }


def mapped_name(name: str, source_root: str, destination: str) -> str:
    source = normalize(name)
    if source == source_root:
        return destination
    prefix = source_root + "/"
    if not source.startswith(prefix):
        raise RuntimeError(
            f"Archive entry is outside its expected root {source_root!r}: {name!r}"
        )
    return normalize(f"{destination}/{source[len(prefix):]}")


def validate_symlink(path: str, linkname: str, destination: str) -> None:
    link = PurePosixPath(linkname)
    if link.is_absolute():
        raise RuntimeError(f"Absolute archive symlink: {path} -> {linkname}")
    destination_parts = PurePosixPath(destination).parts
    resolved = list(PurePosixPath(path).parent.parts)
    for part in link.parts:
        if part in {"", "."}:
            continue
        if part == "..":
            if len(resolved) <= len(destination_parts):
                raise RuntimeError(f"Archive symlink escapes its tool: {path} -> {linkname}")
            resolved.pop()
        else:
            resolved.append(part)
    if tuple(resolved[: len(destination_parts)]) != destination_parts:
        raise RuntimeError(f"Archive symlink escapes its tool: {path} -> {linkname}")


def mapped_archive_paths(path: Path, source_root: str, destination: str) -> set[str]:
    with tarfile.open(path, "r:*") as archive:
        return {
            mapped_name(member.name, source_root, destination)
            for member in archive
            if normalize(member.name) != "."
        }


def add_mapped_archive(
    target: tarfile.TarFile,
    archive_path: Path,
    source_root: str,
    destination: str,
    *,
    allow_external_symlinks: bool = False,
) -> int:
    copied = 0
    with tarfile.open(archive_path, "r:*") as archive:
        for member in archive:
            if normalize(member.name) == ".":
                continue
            cloned = copy.copy(member)
            cloned.name = mapped_name(member.name, source_root, destination)
            cloned.uid, cloned.gid, cloned.uname, cloned.gname = ownership(cloned.name)
            cloned.mtime = int(os.environ.get("SOURCE_DATE_EPOCH", "0"))
            cloned.pax_headers = {
                key: value
                for key, value in member.pax_headers.items()
                if key not in {"path", "linkpath", "mtime", "atime", "ctime"}
            }
            if member.issym():
                if not allow_external_symlinks:
                    validate_symlink(cloned.name, member.linkname, destination)
            elif member.islnk():
                cloned.linkname = mapped_name(
                    member.linkname, source_root, destination
                )
            elif not (member.isdir() or member.isreg()):
                raise RuntimeError(
                    f"Unsupported special entry in {archive_path}: {member.name}"
                )
            fileobj = archive.extractfile(member) if member.isreg() else None
            target.addfile(cloned, fileobj)
            copied += 1
    return copied


def build(
    source: Path,
    overlay: Path,
    winetricks: Path,
    steam_payload: Path,
    hangover_layer: Path,
    ge_proton_archive: Path,
    steamrt4_archive: Path,
    wine_prefix_templates_archive: Path,
    output: Path,
) -> None:
    if not source.is_file():
        raise FileNotFoundError(source)
    if not winetricks.is_file():
        raise FileNotFoundError(winetricks)
    if hashlib.sha256(winetricks.read_bytes()).hexdigest() != WINETRICKS_SHA256:
        raise RuntimeError("Pinned Winetricks 20260125 checksum mismatch")
    if not (steam_payload / "steam.sh").is_file():
        raise RuntimeError(f"Steam payload is incomplete: {steam_payload}")
    if not hangover_layer.is_file():
        raise FileNotFoundError(hangover_layer)
    for required_archive in (
        ge_proton_archive,
        steamrt4_archive,
        wine_prefix_templates_archive,
    ):
        if not required_archive.is_file():
            raise FileNotFoundError(required_archive)

    overlay_directories, overlay_files, overlay_symlinks = gather_tree(overlay, "")
    overlay_files["usr/local/bin/winetricks"] = winetricks
    overlay_directories.discard("")
    steam_directories, steam_files, steam_symlinks = gather_tree(
        steam_payload, STEAM_DESTINATION
    )
    steam_symlinks.update(portable_steam_symlinks(steam_payload))
    all_directories = overlay_directories | steam_directories
    all_files = overlay_files | steam_files
    all_symlinks = overlay_symlinks | steam_symlinks
    for path in all_symlinks:
        all_files.pop(path, None)
    hangover_paths = archive_paths(hangover_layer)
    ge_proton_paths = mapped_archive_paths(
        ge_proton_archive,
        "GE-Proton11-6-aarch64",
        GE_PROTON_DESTINATION,
    )
    steamrt4_paths = mapped_archive_paths(
        steamrt4_archive,
        "SteamLinuxRuntime_4-arm64",
        STEAMRT4_DESTINATION,
    )
    wine_prefix_template_paths = mapped_archive_paths(
        wine_prefix_templates_archive,
        "prefix-templates",
        WINE_PREFIX_TEMPLATES_DESTINATION,
    )
    external_paths = ge_proton_paths | steamrt4_paths | wine_prefix_template_paths

    with tarfile.open(source, "r:*") as original:
        metadata_member = original.getmember(".tiny.yaml")
        metadata_handle = original.extractfile(metadata_member)
        if metadata_handle is None:
            raise RuntimeError("Source image has no readable .tiny.yaml")
        metadata = patched_metadata(metadata_handle.read().decode("utf-8"))

    output.parent.mkdir(parents=True, exist_ok=True)
    partial = output.with_name(output.name + ".partial")
    partial.unlink(missing_ok=True)
    target, finalize = output_tar_context(partial)
    copied = 0
    replaced = 0
    try:
        metadata_info = tarfile.TarInfo(".tiny.yaml")
        metadata_info.size = len(metadata)
        metadata_info.mode = 0o644
        metadata_info.uid = metadata_info.gid = 0
        metadata_info.uname = metadata_info.gname = "root"
        metadata_info.mtime = int(os.environ.get("SOURCE_DATE_EPOCH", "0"))
        target.addfile(metadata_info, io.BytesIO(metadata))

        with tarfile.open(source, "r:*") as original:
            for member in original:
                path = normalize(member.name)
                # Package extraction happens after the base image's cache was
                # generated. Shipping that cache can map libc.so.6 to the
                # libc.so linker script and prevent XFCE from reaching the
                # first-boot repair. Absence is safe: Debian's loader searches
                # its built-in multiarch paths until post-start runs ldconfig.
                if path == "etc/ld.so.cache":
                    replaced += 1
                    continue
                if path == "usr/bin/lsof" and "usr/bin/lsof" in all_files:
                    if not member.isreg():
                        raise RuntimeError("The base image's /usr/bin/lsof is not a file")
                    cloned_lsof = copy.copy(member)
                    cloned_lsof.name = "opt/tiny/steam-arm64/lsof.real"
                    cloned_lsof.pax_headers = {}
                    lsof_handle = original.extractfile(member)
                    if lsof_handle is None:
                        raise RuntimeError("Cannot preserve the base image's /usr/bin/lsof")
                    target.addfile(cloned_lsof, lsof_handle)
                    copied += 1
                if (
                    path in {".", ".tiny.yaml"}
                    or path in hangover_paths
                    or path in all_files
                    or path in all_symlinks
                    or path in all_directories
                    or path in external_paths
                ):
                    replaced += 1
                    continue
                cloned = copy.copy(member)
                cloned.name = path
                cloned.pax_headers = {
                    key: value
                    for key, value in member.pax_headers.items()
                    if key not in {"path", "linkpath"}
                }
                if cloned.islnk() and cloned.linkname.startswith("./"):
                    cloned.linkname = normalize(cloned.linkname)
                fileobj = original.extractfile(member) if member.isreg() else None
                target.addfile(cloned, fileobj)
                copied += 1

        layer_copied = 0
        with tarfile.open(hangover_layer, "r:*") as layer:
            for member in layer:
                path = normalize(member.name)
                if (
                    path == "."
                    or path == "etc/ld.so.cache"
                    or path in all_files
                    or path in all_symlinks
                    or path in all_directories
                    or path in external_paths
                ):
                    continue
                cloned = copy.copy(member)
                cloned.name = path
                cloned.pax_headers = {
                    key: value
                    for key, value in member.pax_headers.items()
                    if key not in {"path", "linkpath"}
                }
                if cloned.islnk() and cloned.linkname.startswith("./"):
                    cloned.linkname = normalize(cloned.linkname)
                fileobj = layer.extractfile(member) if member.isreg() else None
                target.addfile(cloned, fileobj)
                layer_copied += 1

        needed_directories = set(all_directories)
        for path in set(all_files) | set(all_symlinks):
            parent = PurePosixPath(path).parent
            while parent.as_posix() not in {".", ""}:
                needed_directories.add(parent.as_posix())
                parent = parent.parent
        for path in sorted(needed_directories, key=lambda value: (value.count("/"), value)):
            target.addfile(tar_info(path, directory=True))
        for path, local_file in sorted(all_files.items()):
            add_file(target, path, local_file)
        for path, linkname in sorted(all_symlinks.items()):
            add_symlink(target, path, linkname)
        ge_proton_copied = add_mapped_archive(
            target,
            ge_proton_archive,
            "GE-Proton11-6-aarch64",
            GE_PROTON_DESTINATION,
        )
        steamrt4_copied = add_mapped_archive(
            target,
            steamrt4_archive,
            "SteamLinuxRuntime_4-arm64",
            STEAMRT4_DESTINATION,
        )
        wine_prefix_templates_copied = add_mapped_archive(
            target,
            wine_prefix_templates_archive,
            "prefix-templates",
            WINE_PREFIX_TEMPLATES_DESTINATION,
            allow_external_symlinks=True,
        )
    finally:
        target.close()
    finalize()
    partial.replace(output)

    hasher = hashlib.sha256()
    with output.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    digest = hasher.hexdigest()
    output.with_name(output.name + ".sha256").write_text(
        f"{digest}  {output.name}\n", encoding="ascii"
    )
    print(
        f"Copied {copied:,} base entries and {layer_copied:,} Hangover entries; "
        f"added {ge_proton_copied:,} GE-Proton and {steamrt4_copied:,} "
        f"Steam Runtime 4 and {wine_prefix_templates_copied:,} Wine template "
        f"entries; replaced {replaced:,} base entries."
    )
    print(f"Created {output} ({output.stat().st_size / 1024 / 1024:.1f} MiB)")
    print(f"SHA256 {digest}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--overlay", required=True, type=Path)
    parser.add_argument("--winetricks", required=True, type=Path)
    parser.add_argument("--steam-payload", required=True, type=Path)
    parser.add_argument("--hangover-layer", required=True, type=Path)
    parser.add_argument("--ge-proton-archive", required=True, type=Path)
    parser.add_argument("--steamrt4-archive", required=True, type=Path)
    parser.add_argument("--wine-prefix-templates-archive", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    build(
        args.source.resolve(),
        args.overlay.resolve(),
        args.winetricks.resolve(),
        args.steam_payload.resolve(),
        args.hangover_layer.resolve(),
        args.ge_proton_archive.resolve(),
        args.steamrt4_archive.resolve(),
        args.wine_prefix_templates_archive.resolve(),
        args.output.resolve(),
    )


if __name__ == "__main__":
    main()
