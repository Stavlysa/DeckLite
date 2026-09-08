#!/usr/bin/env python3
"""Add DeckLite's initial Steam compatibility-tool mappings safely.

Steam stores these mappings in config/config.vdf.  This patcher preserves the
rest of that file byte-for-byte, inserts only missing entries, and keeps a
one-time backup before replacing it atomically.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import shutil
import tempfile


TOKEN_RE = re.compile(r'"((?:\\.|[^"\\])*)"|([{}])')
STEAM_PATH = ("InstallConfigStore", "Software", "Valve", "Steam")


def decode_vdf_string(value: str) -> str:
    return value.replace(r'\"', '"').replace(r"\\", "\\")


def object_ranges(text: str) -> list[tuple[tuple[str, ...], int, int]]:
    stack: list[tuple[str, int]] = []
    ranges: list[tuple[tuple[str, ...], int, int]] = []
    previous_string: str | None = None

    for match in TOKEN_RE.finditer(text):
        quoted, brace = match.groups()
        if quoted is not None:
            previous_string = decode_vdf_string(quoted)
            continue
        if brace == "{":
            if previous_string is None:
                raise ValueError("VDF object has no name")
            stack.append((previous_string, match.start()))
            previous_string = None
        else:
            if not stack:
                raise ValueError("VDF has an unmatched closing brace")
            path = tuple(item[0] for item in stack)
            _, opening = stack.pop()
            ranges.append((path, opening, match.start()))
            previous_string = None
    if stack:
        raise ValueError("VDF has an unmatched opening brace")
    return ranges


def find_object(text: str, path: tuple[str, ...]) -> tuple[int, int] | None:
    for candidate, opening, closing in object_ranges(text):
        if candidate == path:
            return opening, closing
    return None


def mapping_entry(appid: str, tool: str, indent_depth: int) -> str:
    indent = "\t" * indent_depth
    inner = indent + "\t"
    return (
        f'{indent}"{appid}"\n'
        f"{indent}{{\n"
        f'{inner}"name"\t\t"{tool}"\n'
        f'{inner}"config"\t\t""\n'
        f'{inner}"priority"\t\t"250"\n'
        f"{indent}}}\n"
    )


def before_closing_line(text: str, closing: int) -> int:
    """Return the start of a whitespace-only line containing a closing brace."""
    line_start = text.rfind("\n", 0, closing) + 1
    if text[line_start:closing].strip():
        return closing
    return line_start


def patch_config(text: str, appids: list[str], tool: str) -> tuple[str, list[str]]:
    steam_range = find_object(text, STEAM_PATH)
    if steam_range is None:
        raise ValueError("config.vdf has no InstallConfigStore/Software/Valve/Steam object")

    mapping_path = STEAM_PATH + ("CompatToolMapping",)
    mapping_range = find_object(text, mapping_path)
    added: list[str] = []

    if mapping_range is None:
        entries = "".join(mapping_entry(appid, tool, len(mapping_path)) for appid in appids)
        block_indent = "\t" * len(STEAM_PATH)
        block = (
            f'{block_indent}"CompatToolMapping"\n'
            f"{block_indent}{{\n"
            f"{entries}"
            f"{block_indent}}}\n"
        )
        closing = before_closing_line(text, steam_range[1])
        text = text[:closing] + block + text[closing:]
        added.extend(appids)
    else:
        existing_paths = {path for path, _, _ in object_ranges(text)}
        missing = [appid for appid in appids if mapping_path + (appid,) not in existing_paths]
        if missing:
            entries = "".join(mapping_entry(appid, tool, len(mapping_path)) for appid in missing)
            closing = before_closing_line(text, mapping_range[1])
            text = text[:closing] + entries + text[closing:]
            added.extend(missing)

    # Refuse to write malformed output even if Valve changes the file layout.
    object_ranges(text)
    return text, added


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--steam-root", type=Path, default=Path.home() / ".local/share/Steam")
    parser.add_argument("--tool", default="GE-Proton11-6-aarch64")
    parser.add_argument("--appid", action="append", default=[])
    parser.add_argument("--global-default", action="store_true")
    args = parser.parse_args()

    if not re.fullmatch(r"[A-Za-z0-9._-]+", args.tool):
        raise SystemExit("Unsafe compatibility-tool name")
    appids = (["0"] if args.global_default else []) + args.appid
    if not appids:
        appids = ["0", "10", "70"]
    if any(not appid.isdigit() for appid in appids):
        raise SystemExit("Steam app IDs must be decimal numbers")
    appids = list(dict.fromkeys(appids))

    config = args.steam_root / "config/config.vdf"
    config.parent.mkdir(parents=True, exist_ok=True)
    if config.exists():
        original = config.read_text(encoding="utf-8")
    else:
        original = (
            '"InstallConfigStore"\n{\n\t"Software"\n\t{\n\t\t"Valve"\n'
            '\t\t{\n\t\t\t"Steam"\n\t\t\t{\n\t\t\t}\n\t\t}\n\t}\n}\n'
        )

    updated, added = patch_config(original, appids, args.tool)
    if not added:
        print("Steam Proton mappings already exist; no changes made")
        return

    backup = config.with_name("config.vdf.decklite-pre-proton")
    if config.exists() and not backup.exists():
        shutil.copy2(config, backup)
    fd, temporary_name = tempfile.mkstemp(prefix="config.vdf.", dir=config.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(updated)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, config)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)
    print(f"Mapped Steam app IDs {', '.join(added)} to {args.tool}")


if __name__ == "__main__":
    main()
