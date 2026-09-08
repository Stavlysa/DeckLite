#!/usr/bin/env python3
"""Make the pinned AArch64 GE-Proton safe to run inside Android PRoot."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import tempfile


OLD_CHECK = """    with open('/proc/sys/fs/file-max', encoding='ascii') as fsmax:
        max_files = fsmax.readline()
        if int(max_files) < 8192:
            log.warn(warning)
            return False
    return True
"""

NEW_CHECK = """    try:
        with open('/proc/sys/fs/file-max', encoding='ascii') as fsmax:
            max_files = fsmax.readline()
            if int(max_files) < 8192:
                log.warn(warning)
                return False
    except (OSError, ValueError) as exc:
        # Android PRoot deliberately exposes some procfs sysctls as unreadable.
        # This advisory check must not prevent the Windows game from starting.
        log.info(f'Skipping inaccessible file-limit check: {exc}')
    return True
"""


def replace_atomic(path: Path, original: str, updated: str) -> None:
    backup = path.with_name(path.name + ".decklite-original")
    if not backup.exists():
        shutil.copy2(path, backup)
    fd, temporary_name = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(updated)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary_name, path.stat().st_mode)
        os.replace(temporary_name, path)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)
    print(f"Patched {path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tool-root", required=True, type=Path)
    args = parser.parse_args()

    manifest = args.tool_root / "toolmanifest.vdf"
    checks = args.tool_root / "protonfixes/checks.py"
    for path in (manifest, checks):
        if not path.is_file():
            raise SystemExit(f"GE-Proton payload is incomplete: {path}")

    manifest_text = manifest.read_text(encoding="utf-8")
    dependency = '  "require_tool_appid" "4185400"\n'
    if dependency in manifest_text:
        replace_atomic(manifest, manifest_text, manifest_text.replace(dependency, "", 1))
    elif "require_tool_appid" in manifest_text:
        raise SystemExit("GE-Proton has an unexpected runtime dependency declaration")

    checks_text = checks.read_text(encoding="utf-8")
    bad_log_call = "log.info('Skipping inaccessible file-limit check: %s', exc)"
    if bad_log_call in checks_text:
        updated = checks_text.replace(
            bad_log_call,
            "log.info(f'Skipping inaccessible file-limit check: {exc}')",
            1,
        )
        replace_atomic(checks, checks_text, updated)
        checks_text = updated
    if OLD_CHECK in checks_text:
        replace_atomic(checks, checks_text, checks_text.replace(OLD_CHECK, NEW_CHECK, 1))
    elif "Skipping inaccessible file-limit check" not in checks_text:
        raise SystemExit("GE-Proton file-limit check has an unexpected layout")


if __name__ == "__main__":
    main()
