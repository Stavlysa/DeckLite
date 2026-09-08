#!/usr/bin/env python3
"""Create the compact, deterministic Wine prefix-template build input."""

from __future__ import annotations

import argparse
import copy
import os
from pathlib import Path, PurePosixPath
import subprocess
import tarfile


def archive_templates(root: Path, output: Path) -> None:
    root = root.resolve(strict=True)
    base = root / "game-complete"
    derived = root / "dotnet-xna-complete"
    for required in (
        base / "system.reg",
        base / ".decklite-runtimes-common",
        base / ".decklite-runtimes-legacy-media",
        derived / "system.reg",
        derived / ".decklite-runtimes-dotnet-xna",
        derived / ".decklite-dotnet-mscoree-repaired",
    ):
        if not required.is_file():
            raise FileNotFoundError(required)

    output.parent.mkdir(parents=True, exist_ok=True)
    partial = output.with_name(output.name + ".partial")
    partial.unlink(missing_ok=True)
    process = subprocess.Popen(
        ["zstd", "-T0", "-10", "-q", "-f", "-o", str(partial)],
        stdin=subprocess.PIPE,
    )
    if process.stdin is None:
        raise RuntimeError("Could not open zstd input")

    hardlinks = 0
    hardlink_bytes = 0
    try:
        with tarfile.open(fileobj=process.stdin, mode="w|") as archive:
            root_info = tarfile.TarInfo("prefix-templates")
            root_info.type = tarfile.DIRTYPE
            root_info.mode = 0o755
            root_info.uid = root_info.gid = 0
            root_info.uname = root_info.gname = "root"
            root_info.mtime = 0
            archive.addfile(root_info)

            for template in (base, derived):
                items = [template, *sorted(template.rglob("*"))]
                for item in items:
                    relative = item.relative_to(root)
                    name = PurePosixPath("prefix-templates", relative.as_posix()).as_posix()
                    if item.is_file() and not item.is_symlink() and template == derived:
                        base_item = base / item.relative_to(derived)
                        if base_item.is_file() and not base_item.is_symlink() and os.path.samefile(
                            item, base_item
                        ):
                            info = tarfile.TarInfo(name)
                            info.type = tarfile.LNKTYPE
                            info.linkname = PurePosixPath(
                                "prefix-templates",
                                "game-complete",
                                item.relative_to(derived).as_posix(),
                            ).as_posix()
                            info.mode = item.stat().st_mode & 0o7777
                            info.size = 0
                            info.mtime = 0
                            info.uid = info.gid = 0
                            info.uname = info.gname = "root"
                            archive.addfile(info)
                            hardlinks += 1
                            hardlink_bytes += item.stat().st_size
                            continue

                    info = archive.gettarinfo(str(item), arcname=name)
                    info = copy.copy(info)
                    info.uid = info.gid = 0
                    info.uname = info.gname = "root"
                    info.mtime = 0
                    info.pax_headers = {}
                    if info.isreg():
                        with item.open("rb") as handle:
                            archive.addfile(info, handle)
                    elif info.isdir() or info.issym():
                        archive.addfile(info)
                    else:
                        raise RuntimeError(f"Unsupported template entry: {item}")
    finally:
        process.stdin.close()
    status = process.wait()
    if status != 0:
        partial.unlink(missing_ok=True)
        raise RuntimeError(f"zstd failed with exit status {status}")
    partial.replace(output)
    print(
        f"Created {output} with {hardlinks:,} cross-template hardlinks "
        f"({hardlink_bytes / 1024 / 1024:.1f} MiB deduplicated)"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    archive_templates(args.root, args.output)


if __name__ == "__main__":
    main()
