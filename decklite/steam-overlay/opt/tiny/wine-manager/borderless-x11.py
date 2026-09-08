#!/usr/bin/env python3
"""Clear stale X11 letterboxing once after this launch's game has been fitted.

Some Wine X11 desktop surfaces retain the old window pixels even after Win32
RedrawWindow/PaintDesktop succeeds. This clears only the unused border regions
of the uniquely named launch desktop. It never captures, resizes, focuses or
creates a window and exits after one repaint or a bounded startup timeout.
"""
from __future__ import annotations

import argparse
import ctypes as c
import os
import re
import subprocess
import time

CHILD = re.compile(
    r'^\s+(0x[0-9a-f]+).*?: \("([^"\n]*)" "[^"\n]*"\)\s+'
    r'(\d+)x(\d+)([+-]\d+)([+-]\d+)\s', re.MULTILINE | re.IGNORECASE
)


def query(*args: str) -> str:
    try:
        return subprocess.run(args, check=True, stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL, timeout=3,
                              env={**os.environ, 'LC_ALL': 'C'}).stdout.decode('utf-8', 'replace')
    except (OSError, subprocess.SubprocessError):
        return ''


def borders(width: int, height: int, rect: tuple[int, int, int, int]):
    x, y, w, h = rect
    if min(width, height, w, h) <= 0 or x < 0 or y < 0:
        return None
    if x + w > width or y + h > height or (w != width and h != height):
        return None
    if abs(2 * x + w - width) > 1 or abs(2 * y + h - height) > 1:
        return None
    return [(a, b, cw, ch) for a, b, cw, ch in (
        (0, 0, x, height), (x + w, 0, width - x - w, height),
        (x, 0, w, y), (x, y + h, w, height - y - h),
    ) if cw > 0 and ch > 0]


def fitted_child(info: str, width: int, height: int):
    if not re.search(rf'Width:\s+{width}\s', info) or not re.search(rf'Height:\s+{height}\s', info):
        return None
    candidates = []
    for match in CHILD.finditer(info):
        ident, instance, sw, sh, sx, sy = match.groups()
        rect = (int(sx), int(sy), int(sw), int(sh))
        if instance.lower() == 'explorer.exe' or rect[2] < 320 or rect[3] < 200:
            continue
        if borders(width, height, rect) is not None:
            candidates.append((ident, rect))
    return candidates[0] if len(candidates) == 1 else None


def repaint(window: int, regions) -> None:
    lib = c.CDLL('libX11.so.6')
    lib.XOpenDisplay.argtypes = [c.c_char_p]
    lib.XOpenDisplay.restype = c.c_void_p
    lib.XSetWindowBackground.argtypes = [c.c_void_p, c.c_ulong, c.c_ulong]
    lib.XClearArea.argtypes = [c.c_void_p, c.c_ulong, c.c_int, c.c_int, c.c_uint, c.c_uint, c.c_int]
    lib.XSync.argtypes = [c.c_void_p, c.c_int]
    lib.XCloseDisplay.argtypes = [c.c_void_p]
    # Closing a game between query and repaint is harmless; do not terminate
    # the game or the launcher when the X server reports a stale window ID.
    error_callback = c.CFUNCTYPE(c.c_int, c.c_void_p, c.c_void_p)
    ignore_stale = error_callback(lambda _display, _event: 0)
    lib.XSetErrorHandler.argtypes = [error_callback]
    lib.XSetErrorHandler(ignore_stale)
    display = lib.XOpenDisplay(None)
    if not display:
        return
    try:
        lib.XSetWindowBackground(display, window, 0)
        for x, y, w, h in regions:
            lib.XClearArea(display, window, x, y, w, h, 0)
        lib.XSync(display, 0)
    finally:
        lib.XCloseDisplay(display)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--desktop', required=True)
    parser.add_argument('--size', required=True)
    parser.add_argument('--launcher', required=True, type=int)
    args = parser.parse_args()
    if args.launcher < 2 or args.desktop != f'DeckLite-{args.launcher}':
        parser.error('Expected a unique launch desktop')
    if not re.fullmatch(r'\d{3,5}x\d{3,5}', args.size):
        parser.error('Invalid display geometry')
    width, height = map(int, args.size.split('x'))
    if not 100 <= min(width, height) <= max(width, height) <= 32767:
        parser.error('Display geometry out of bounds')
    title = f'{args.desktop} - Wine Desktop'
    deadline = time.monotonic() + 150
    previous = None
    while time.monotonic() < deadline:
        try:
            os.kill(args.launcher, 0)
        except ProcessLookupError:
            return
        ids = query('xdotool', 'search', '--name', '^' + re.escape(title) + '$').split()
        state = None
        if len(ids) == 1 and ids[0].isdigit():
            info = query('xwininfo', '-id', ids[0], '-stats', '-children')
            child = fitted_child(info, width, height) if f'"{title}"' in info else None
            if child:
                state = (int(ids[0]), child)
        # Two consecutive matching observations avoid the initial transition.
        if state is not None and state == previous:
            repaint(state[0], borders(width, height, state[1][1]))
            print('DeckLite borderless: stale X11 letterboxing cleared once.', flush=True)
            return
        previous = state
        time.sleep(1)


if __name__ == '__main__':
    main()
