#!/usr/bin/env python3
"""Guard Steam ARM64's UI against optional methods absent from its backend."""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil


REPLACEMENTS = (
    (
        'const t=(0,B.Dp)("System.Network.RegisterForDeviceChanges");'
        "t&&SteamClient.System.Network.RegisterForDeviceChanges",
        'const t="function"==typeof '
        "SteamClient.System.Network.RegisterForDeviceChanges;"
        "t&&SteamClient.System.Network.RegisterForDeviceChanges",
        1,
        False,
    ),
    (
        '(0,B.Dp)("System.Network.GetProxyInfo")&&'
        "SteamClient.System.Network.GetProxyInfo()",
        '"function"==typeof SteamClient.System.Network.GetProxyInfo&&'
        "SteamClient.System.Network.GetProxyInfo()",
        1,
        False,
    ),
    (
        '(0,B.Dp)("System.Network.RegisterForConnectivityTestChanges")&&'
        "SteamClient.System.Network.RegisterForConnectivityTestChanges",
        '"function"==typeof '
        "SteamClient.System.Network.RegisterForConnectivityTestChanges&&"
        "SteamClient.System.Network.RegisterForConnectivityTestChanges",
        1,
        False,
    ),
    (
        "()=>SteamClient.User.GetStartupUserChooserState(),[]",
        '()=>"function"==typeof SteamClient.User.GetStartupUserChooserState?'
        "SteamClient.User.GetStartupUserChooserState():Promise.resolve(0),[]",
        2,
        True,
    ),
)


def patch(steam_root: Path) -> None:
    target = steam_root / "steamui/chunk~2dcc5aaf7.js"
    if not target.is_file():
        raise RuntimeError(f"Steam UI compatibility target is missing: {target}")
    source = target.read_text(encoding="utf-8")
    patched = source
    changed = False
    for original, replacement, expected_count, allow_absent in REPLACEMENTS:
        if replacement in patched:
            continue
        count = patched.count(original)
        if count == 0 and allow_absent:
            continue
        if count != expected_count:
            raise RuntimeError(
                "Steam UI has an unexpected optional bridge expression "
                f"(found {count}, expected {expected_count})"
            )
        patched = patched.replace(original, replacement)
        changed = True
    if not changed:
        return

    backup = steam_root / "decklite-backups/chunk~2dcc5aaf7.js.pre-network-guard"
    backup.parent.mkdir(parents=True, exist_ok=True)
    if not backup.exists():
        shutil.copy2(target, backup)
    temporary = target.with_name(target.name + ".decklite-new")
    temporary.write_text(patched, encoding="utf-8")
    temporary.replace(target)
    print(f"Patched Steam ARM64 optional bridge guards: {target}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--steam-root", required=True, type=Path)
    args = parser.parse_args()
    patch(args.steam_root.expanduser().resolve())


if __name__ == "__main__":
    main()
