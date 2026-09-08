#!/usr/bin/env python3
"""Download a Steam ARM64 update without replacing the tested client."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile


STATE_DIR = Path.home() / ".local/share/decklite-steam"
STABLE_ROOT = Path.home() / ".local/share/Steam"
CANDIDATE = STATE_DIR / "candidate"
PREVIOUS = STATE_DIR / "candidate.previous"
ACTIVE_FILE = STATE_DIR / "active-root"
UPDATER = Path("/opt/tiny/steam-arm64/update_steam.py")
PATCHER = Path("/opt/tiny/steam-arm64/patch-steam-ui.py")


def elf_machine(path: Path) -> int:
    header = path.read_bytes()[:20]
    if len(header) != 20 or header[:4] != b"\x7fELF":
        raise RuntimeError(f"Not an ELF executable: {path}")
    endian = "<" if header[5] == 1 else ">"
    return struct.unpack(endian + "H", header[18:20])[0]


def validate(root: Path) -> str:
    required = (
        root / "steam.sh",
        root / "steamrtarm64/steam",
        root / "steamrtarm64/steamwebhelper",
        root / "package/steam_client_linuxarm64",
    )
    for path in required:
        if not path.is_file():
            raise RuntimeError(f"Update candidate is incomplete: {path}")
    for path in required[1:3]:
        if elf_machine(path) != 183:
            raise RuntimeError(f"Update candidate is not native AArch64: {path}")
    environment = os.environ.copy()
    environment["LD_LIBRARY_PATH"] = str(root / "steamrtarm64")
    for path in required[1:3]:
        result = subprocess.run(
            ["ldd", str(path)],
            env=environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        if result.returncode != 0 or "not found" in result.stdout:
            raise RuntimeError(f"Missing native dependency for {path.name}:\n{result.stdout}")
    version_file = root / ".decklite-steam-version"
    version = version_file.read_text(encoding="ascii").strip()
    if not version.isdigit():
        raise RuntimeError("Update candidate has no numeric Steam version")
    return version


def link_user_data(root: Path) -> None:
    # Keep large games, login data, saves and compatibility tools outside the
    # replaceable client candidate. html/app cache remains candidate-specific.
    for name in ("config", "userdata", "steamapps", "compatibilitytools.d"):
        source = STABLE_ROOT / name
        if not source.exists():
            continue
        destination = root / name
        if destination.is_symlink() or destination.is_file():
            destination.unlink()
        elif destination.is_dir():
            shutil.rmtree(destination)
        destination.symlink_to(source, target_is_directory=True)


def main() -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    if ACTIVE_FILE.is_file() and ACTIVE_FILE.read_text(encoding="utf-8").strip() == str(CANDIDATE):
        raise RuntimeError("Roll back to the tested Steam build before replacing the active candidate")
    temporary = Path(tempfile.mkdtemp(prefix="candidate-", dir=STATE_DIR))
    try:
        subprocess.run(
            [
                sys.executable,
                str(UPDATER),
                "--output",
                str(temporary),
                "--package-cache",
                str(STATE_DIR / "packages"),
            ],
            check=True,
        )
        subprocess.run(
            [sys.executable, str(PATCHER), "--steam-root", str(temporary)],
            check=True,
        )
        version = validate(temporary)
        link_user_data(temporary)
        (temporary / ".decklite-update-candidate.json").write_text(
            json.dumps(
                {"version": version, "tested_build": "1785799196"},
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        if PREVIOUS.exists() or PREVIOUS.is_symlink():
            if PREVIOUS.is_dir() and not PREVIOUS.is_symlink():
                shutil.rmtree(PREVIOUS)
            else:
                PREVIOUS.unlink()
        if CANDIDATE.exists() or CANDIDATE.is_symlink():
            CANDIDATE.rename(PREVIOUS)
        temporary.rename(CANDIDATE)
        print(f"Steam ARM64 update candidate {version} is staged at {CANDIDATE}")
        print("The tested build is unchanged. Use 'Test Steam update candidate' next.")
    except BaseException:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise


if __name__ == "__main__":
    main()
