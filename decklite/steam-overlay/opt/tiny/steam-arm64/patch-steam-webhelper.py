#!/usr/bin/env python3
"""Reapply the CEF-only software compositor to known Valve/DeckLite wrappers."""
import argparse
from pathlib import Path
import re

ORIGINAL = '$(pwd)/steamwebhelper "$@"'
SHM = '$(pwd)/steamwebhelper --disable-dev-shm-usage "$@"'
KOPPER = 'env LIBGL_KOPPER_DISABLE="${STEAM_CEF_KOPPER_DISABLE:-false}" '
ANGLE = '--enable-angle-features=disableSyncControlSupport'
CURRENT = KOPPER + '$(pwd)/steamwebhelper --disable-dev-shm-usage ' + ANGLE + ' "$@"'
# Scope the flag to the actual Chromium webhelper, not Steam or a game. This
# avoids layered Library corruption without globally disabling GL/Vulkan.
PATCHED = CURRENT.replace(' "$@"', ' --disable-gpu-compositing "$@"')
KNOWN = (ORIGINAL, SHM, KOPPER + SHM, CURRENT, PATCHED)


def patch_text(source):
    # Match a complete known exec line, not a comment, substring, or a new
    # upstream wrapper with additional unknown options. Preserve taskset and
    # log redirection verbatim. Fail without writing if upstream changes shape.
    matches = []
    for command in KNOWN:
        pattern = (r'(?m)^(exec (?:taskset (?:0x[0-9a-fA-F]+|[0-9]+) )?)'
                   + re.escape(command)
                   + r'(?:(&> [^\r\n]+)|([ \t]+&> [^\r\n]+)|([ \t]*))$')
        for match in re.finditer(pattern, source):
            matches.append((match, command))
    if len(matches) != 1:
        raise ValueError('Steam webhelper wrapper has an unexpected launch command')
    match, command = matches[0]
    if command == PATCHED:
        return source
    return source[:match.start()] + match.group(0).replace(command, PATCHED, 1) + source[match.end():]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wrapper', type=Path, required=True)
    args = parser.parse_args()
    before = args.wrapper.read_text(encoding='utf-8')
    after = patch_text(before)
    if after != before:
        # Preserve executable mode and Valve's surrounding script.
        args.wrapper.write_text(after, encoding='utf-8', newline='\n')
        print('Applied Steam CEF-only software compositor workaround')


if __name__ == '__main__':
    main()
