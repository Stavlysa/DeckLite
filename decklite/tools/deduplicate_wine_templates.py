#!/usr/bin/env python3
"""Hard-link byte-identical files at matching paths in two Wine templates."""

from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path


def digest(path: Path) -> bytes:
    result = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            result.update(chunk)
    return result.digest()


def deduplicate(base: Path, derived: Path) -> tuple[int, int]:
    base = base.resolve(strict=True)
    derived = derived.resolve(strict=True)
    if base == derived or base.parent != derived.parent:
        raise ValueError("Templates must be different siblings")

    linked_files = 0
    linked_bytes = 0
    for candidate in derived.rglob("*"):
        if candidate.is_symlink() or not candidate.is_file():
            continue
        relative = candidate.relative_to(derived)
        original = base / relative
        if original.is_symlink() or not original.is_file():
            continue
        candidate_stat = candidate.stat()
        original_stat = original.stat()
        if (
            candidate_stat.st_size != original_stat.st_size
            or (candidate_stat.st_mode & 0o7777) != (original_stat.st_mode & 0o7777)
            or digest(candidate) != digest(original)
        ):
            continue

        temporary = candidate.with_name(candidate.name + ".decklite-linking")
        if temporary.exists() or temporary.is_symlink():
            raise FileExistsError(temporary)
        candidate.rename(temporary)
        try:
            os.link(original, candidate)
        except Exception:
            temporary.rename(candidate)
            raise
        temporary.unlink()
        linked_files += 1
        linked_bytes += candidate_stat.st_size
    return linked_files, linked_bytes


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True, type=Path)
    parser.add_argument("--derived", required=True, type=Path)
    args = parser.parse_args()
    count, size = deduplicate(args.base, args.derived)
    print(f"Hard-linked {count:,} matching files ({size / 1024 / 1024:.1f} MiB)")


if __name__ == "__main__":
    main()
