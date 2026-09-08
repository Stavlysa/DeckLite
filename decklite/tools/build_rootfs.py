#!/usr/bin/env python3
"""Build a Tiny Container rootfs without losing Unix tar metadata."""

from __future__ import annotations

import argparse
import copy
import hashlib
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import tarfile
import tempfile


PRUNED_PREFIXES = (
    "boot",
    "usr/lib/firmware",
    "usr/lib/modules",
    "var/cache/pacman/pkg",
    "var/log/journal",
)

PRUNED_EXACT = {
    "etc/machine-id",
    "var/lib/systemd/random-seed",
}

REPLACED_EXACT = {
    "etc/hostname",
    "etc/locale.conf",
    "etc/resolv.conf",
}

SYNTHETIC_DIRECTORIES = (
    "home/alarm/Desktop",
    "home/alarm/Documents",
    "home/alarm/Downloads",
    "home/alarm/Music",
    "home/alarm/Pictures",
    "home/alarm/Public",
    "home/alarm/Videos",
    "proc",
    "proc/bus",
    "proc/bus/pci",
    "proc/sys",
    "proc/sys/fs",
    "proc/sys/fs/inotify",
    "proc/sys/kernel",
    "sys",
    "sys/.empty",
)

SYNTHETIC_FILES = (
    "etc/machine-id",
    "proc/.devices",
    "proc/.loadavg",
    "proc/.overflowgid",
    "proc/.overflowuid",
    "proc/.stat",
    "proc/.sysctl_entry_cap_last_cap",
    "proc/.sysctl_inotify_max_user_watches",
    "proc/.uptime",
    "proc/.version",
    "proc/.vmstat",
)


def normalize_archive_path(value: str) -> str:
    while value.startswith("./"):
        value = value[2:]
    value = value.rstrip("/")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"Unsafe archive path: {value!r}")
    return path.as_posix() if value else "."


def is_under(path: str, prefix: str) -> bool:
    return path == prefix or path.startswith(prefix + "/")


def is_pruned(path: str) -> bool:
    if path in PRUNED_EXACT or path in REPLACED_EXACT:
        return True
    if any(is_under(path, prefix) for prefix in PRUNED_PREFIXES):
        return True
    if path.startswith("etc/ssh/ssh_host_"):
        return True
    if path.startswith("var/lib/pacman/local/linux-aarch64-"):
        return True
    if path.startswith("var/lib/pacman/local/linux-firmware-"):
        return True
    return False


def mode_for_overlay(path: str) -> int:
    filename = PurePosixPath(path).name
    if path.startswith("etc/sudoers.d/"):
        return 0o440
    if path.startswith("opt/tiny/") and filename.endswith(".sh"):
        return 0o755
    if path.startswith("usr/local/bin/"):
        return 0o755
    if path.startswith("etc/profile.d/") and filename.endswith(".sh"):
        return 0o755
    if filename == "autostart":
        return 0o755
    return 0o644


def ownership_for_overlay(path: str) -> tuple[int, int, str, str]:
    if path == "home/alarm" or path.startswith("home/alarm/"):
        return 1000, 1000, "alarm", "alarm"
    return 0, 0, "root", "root"


def make_info(path: str, *, directory: bool, size: int = 0) -> tarfile.TarInfo:
    info = tarfile.TarInfo(path)
    info.mtime = int(os.environ.get("SOURCE_DATE_EPOCH", "0"))
    info.type = tarfile.DIRTYPE if directory else tarfile.REGTYPE
    info.size = 0 if directory else size
    info.mode = 0o755 if directory else mode_for_overlay(path)
    info.uid, info.gid, info.uname, info.gname = ownership_for_overlay(path)
    return info


def add_overlay_file(target: tarfile.TarFile, path: str, source: Path) -> None:
    info = make_info(path, directory=False, size=source.stat().st_size)
    with source.open("rb") as handle:
        target.addfile(info, handle)


def output_tar_context(output: Path):
    """Return (TarFile, finalizer) with a zstd CLI fallback for Python < 3.14."""
    try:
        archive = tarfile.open(output, "w:zst", level=10)
        return archive, lambda: None
    except (tarfile.CompressionError, ValueError):
        zstd = shutil.which("zstd")
        if not zstd:
            raise RuntimeError(
                "This Python cannot write zstd tar files. Install the zstd command "
                "or run the builder with Python 3.14+."
            )
        temporary = Path(tempfile.mkstemp(suffix=".tar", dir=output.parent)[1])
        archive = tarfile.open(temporary, "w")

        def finalize() -> None:
            subprocess.run(
                [zstd, "-T0", "-10", "-f", str(temporary), "-o", str(output)],
                check=True,
            )
            temporary.unlink()

        return archive, finalize


def build(source: Path, overlay: Path, output: Path) -> None:
    if not source.is_file():
        raise FileNotFoundError(source)
    metadata = overlay / ".tiny.yaml"
    if not metadata.is_file():
        raise FileNotFoundError(metadata)

    overlay_files: dict[str, Path] = {}
    overlay_directories: set[str] = set()
    for item in sorted(overlay.rglob("*")):
        relative = item.relative_to(overlay).as_posix()
        normalized = normalize_archive_path(relative)
        if item.is_dir():
            overlay_directories.add(normalized)
        elif normalized != ".tiny.yaml":
            overlay_files[normalized] = item

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary_output = output.with_suffix(output.suffix + ".partial")
    temporary_output.unlink(missing_ok=True)

    target, finalize = output_tar_context(temporary_output)
    copied = 0
    dropped = 0
    try:
        # Tiny Container expects this exact file at the very beginning.
        add_overlay_file(target, ".tiny.yaml", metadata)

        with tarfile.open(source, "r:*") as original:
            for member in original:
                path = normalize_archive_path(member.name)
                if path == "." or is_pruned(path):
                    dropped += 1
                    continue
                if path in overlay_files or path in overlay_directories:
                    dropped += 1
                    continue

                cloned = copy.copy(member)
                cloned.name = path
                cloned.pax_headers = {
                    key: value
                    for key, value in member.pax_headers.items()
                    if key not in {"path", "linkpath"}
                }
                if cloned.islnk() and cloned.linkname.startswith("./"):
                    cloned.linkname = normalize_archive_path(cloned.linkname)
                fileobj = original.extractfile(member) if member.isreg() else None
                target.addfile(cloned, fileobj)
                copied += 1

        existing_directories = set(overlay_directories) | set(SYNTHETIC_DIRECTORIES)
        for path in list(overlay_files) + list(SYNTHETIC_DIRECTORIES) + list(SYNTHETIC_FILES):
            parent = PurePosixPath(path).parent
            while parent.as_posix() not in {".", ""}:
                existing_directories.add(parent.as_posix())
                parent = parent.parent

        for path in sorted(existing_directories, key=lambda value: (value.count("/"), value)):
            target.addfile(make_info(path, directory=True))

        for path, source_file in sorted(overlay_files.items()):
            add_overlay_file(target, path, source_file)

        for path in SYNTHETIC_FILES:
            target.addfile(make_info(path, directory=False, size=0))
    finally:
        target.close()

    finalize()
    temporary_output.replace(output)
    hasher = hashlib.sha256()
    with output.open("rb") as built_archive:
        for chunk in iter(lambda: built_archive.read(1024 * 1024), b""):
            hasher.update(chunk)
    digest = hasher.hexdigest()
    checksum_path = output.with_name(output.name + ".sha256")
    checksum_path.write_text(f"{digest}  {output.name}\n", encoding="ascii")
    print(f"Copied {copied:,} source entries; pruned/replaced {dropped:,} entries.")
    print(f"Created {output} ({output.stat().st_size / 1024 / 1024:.1f} MiB)")
    print(f"SHA256 {digest}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--overlay", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    build(args.source.resolve(), args.overlay.resolve(), args.output.resolve())


if __name__ == "__main__":
    main()
