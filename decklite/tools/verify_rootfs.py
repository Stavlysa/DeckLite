#!/usr/bin/env python3
"""Structural verification for a DeckLite Tiny Container image."""

from __future__ import annotations

import argparse
import struct
import tarfile
from pathlib import Path


REQUIRED = {
    ".tiny.yaml",
    "bin",
    "etc/passwd",
    "home/alarm",
    "opt/tiny/export.sh",
    "opt/tiny/install-box64.sh",
    "opt/tiny/install-steam.sh",
    "opt/tiny/setup-desktop.sh",
    "opt/tiny/start-desktop.sh",
    "proc/.loadavg",
    "sys/.empty",
    "usr/bin/bash",
}

FORBIDDEN_PREFIXES = ("boot/", "usr/lib/firmware/", "usr/lib/modules/")


def normalize(value: str) -> str:
    while value.startswith("./"):
        value = value[2:]
    return value.rstrip("/")


def verify(archive_path: Path) -> None:
    with tarfile.open(archive_path, "r:*") as archive:
        first = archive.next()
        if first is None or normalize(first.name) != ".tiny.yaml":
            raise RuntimeError(".tiny.yaml is not the first archive entry")

        members = [first, *archive]
        by_name = {normalize(member.name): member for member in members}
        missing = sorted(REQUIRED - set(by_name))
        if missing:
            raise RuntimeError(f"Missing required entries: {', '.join(missing)}")

        forbidden = [
            name
            for name in by_name
            if any(name.startswith(prefix) for prefix in FORBIDDEN_PREFIXES)
        ]
        if forbidden:
            raise RuntimeError(f"Hardware-only entries remain, e.g. {forbidden[0]}")

        for script in (
            "opt/tiny/export.sh",
            "opt/tiny/install-box64.sh",
            "opt/tiny/install-steam.sh",
            "opt/tiny/setup-desktop.sh",
            "opt/tiny/start-desktop.sh",
        ):
            if by_name[script].mode & 0o111 == 0:
                raise RuntimeError(f"Script is not executable: {script}")

        bash = archive.extractfile(by_name["usr/bin/bash"])
        if bash is None:
            raise RuntimeError("Cannot read /usr/bin/bash")
        header = bash.read(20)
        if header[:4] != b"\x7fELF":
            raise RuntimeError("/usr/bin/bash is not ELF")
        endian = "<" if header[5] == 1 else ">"
        machine = struct.unpack(endian + "H", header[18:20])[0]
        if machine != 183:
            raise RuntimeError(f"Expected AArch64 ELF machine 183, got {machine}")

        metadata = archive.extractfile(by_name[".tiny.yaml"])
        if metadata is None:
            raise RuntimeError("Cannot read .tiny.yaml")
        yaml_text = metadata.read().decode("utf-8")
        for key in ("code:", "name:", "boot_command:", "export_command:"):
            if key not in yaml_text:
                raise RuntimeError(f"Metadata is missing {key}")

    print(f"Verified Tiny Container structure and AArch64 userspace: {archive_path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", required=True, type=Path)
    args = parser.parse_args()
    verify(args.archive.resolve())


if __name__ == "__main__":
    main()

