#!/usr/bin/env python3
"""Present private Wine desktops; never resize a game or change an X11 mode.

The Win32 observer reports actual popup/monitor geometry. Windowed applications
retain their Wine frames; X Shape removes only the unused virtual background.
One same-UID watcher publishes only the active desktop's fullscreen viewport.
"""
from __future__ import annotations
import ctypes as c
import os
from pathlib import Path
import re
import signal
import time

class Rect(c.Structure):
    _fields_ = [('x', c.c_short), ('y', c.c_short), ('width', c.c_ushort), ('height', c.c_ushort)]

class Attributes(c.Structure):
    _fields_ = [(k, t) for k, t in (
        ('x', c.c_int), ('y', c.c_int), ('width', c.c_int), ('height', c.c_int),
        ('border_width', c.c_int), ('depth', c.c_int), ('visual', c.c_void_p),
        ('root', c.c_ulong), ('class_', c.c_int), ('bit_gravity', c.c_int),
        ('win_gravity', c.c_int), ('backing_store', c.c_int), ('backing_planes', c.c_ulong),
        ('backing_pixel', c.c_ulong), ('save_under', c.c_int), ('colormap', c.c_ulong),
        ('map_installed', c.c_int), ('map_state', c.c_int), ('all_event_masks', c.c_long),
        ('your_event_mask', c.c_long), ('do_not_propagate_mask', c.c_long),
        ('override_redirect', c.c_int), ('screen', c.c_void_p))]

class X11:
    def __init__(self):
        self.x = c.CDLL('libX11.so.6')
        self.ext = c.CDLL('libXext.so.6')
        signatures = {
            'XOpenDisplay': (c.c_void_p, [c.c_char_p]),
            'XDefaultRootWindow': (c.c_ulong, [c.c_void_p]),
            'XInternAtom': (c.c_ulong, [c.c_void_p, c.c_char_p, c.c_int]),
            'XGetWindowAttributes': (c.c_int, [c.c_void_p, c.c_ulong, c.POINTER(Attributes)]),
            'XGetWindowProperty': (c.c_int, [c.c_void_p, c.c_ulong, c.c_ulong, c.c_long, c.c_long, c.c_int, c.c_ulong, c.POINTER(c.c_ulong), c.POINTER(c.c_int), c.POINTER(c.c_ulong), c.POINTER(c.c_ulong), c.POINTER(c.c_void_p)]),
            'XChangeProperty': (c.c_int, [c.c_void_p, c.c_ulong, c.c_ulong, c.c_ulong, c.c_int, c.c_int, c.c_void_p, c.c_int]),
            'XDeleteProperty': (c.c_int, [c.c_void_p, c.c_ulong, c.c_ulong]),
            'XQueryTree': (c.c_int, [c.c_void_p, c.c_ulong, c.POINTER(c.c_ulong), c.POINTER(c.c_ulong), c.POINTER(c.POINTER(c.c_ulong)), c.POINTER(c.c_uint)]),
            'XTranslateCoordinates': (c.c_int, [c.c_void_p, c.c_ulong, c.c_ulong, c.c_int, c.c_int, c.POINTER(c.c_int), c.POINTER(c.c_int), c.POINTER(c.c_ulong)]),
            'XSync': (c.c_int, [c.c_void_p, c.c_int]),
            'XFree': (c.c_int, [c.c_void_p]),
            'XCloseDisplay': (c.c_int, [c.c_void_p]),
        }
        for name, (result, args) in signatures.items():
            fn = getattr(self.x, name); fn.restype = result; fn.argtypes = args
        self.ext.XShapeCombineRectangles.argtypes = [c.c_void_p, c.c_ulong, c.c_int, c.c_int, c.c_int, c.POINTER(Rect), c.c_int, c.c_int, c.c_int]
        self.ext.XShapeCombineMask.argtypes = [c.c_void_p, c.c_ulong, c.c_int, c.c_int, c.c_int, c.c_ulong, c.c_int]
        self.error_type = c.CFUNCTYPE(c.c_int, c.c_void_p, c.c_void_p)
        self.ignore_stale = self.error_type(lambda *_: 0)
        self.x.XSetErrorHandler.argtypes = [self.error_type]
        self.x.XSetErrorHandler(self.ignore_stale)
        self.d = self.x.XOpenDisplay(None)
        if not self.d: raise RuntimeError('Cannot connect to X11')
        self.root = self.x.XDefaultRootWindow(self.d)
        self.atoms = {}

    def atom(self, name):
        if name not in self.atoms:
            self.atoms[name] = self.x.XInternAtom(self.d, name.encode(), 0)
        return self.atoms[name]

    def prop(self, w, name):
        typ, fmt, count, after, data = c.c_ulong(), c.c_int(), c.c_ulong(), c.c_ulong(), c.c_void_p()
        self.x.XGetWindowProperty(self.d, w, self.atom(name), 0, 512, 0, 0,
                                 c.byref(typ), c.byref(fmt), c.byref(count), c.byref(after), c.byref(data))
        try:
            if not data or after.value: return None
            if fmt.value == 8: return c.string_at(data, count.value)
            if fmt.value == 32: return list(c.cast(data, c.POINTER(c.c_ulong))[:count.value])
        finally:
            if data: self.x.XFree(data)

    def attrs(self, w):
        a = Attributes()
        return a if self.x.XGetWindowAttributes(self.d, w, c.byref(a)) else None

    def children(self, w):
        root, parent, count, children = c.c_ulong(), c.c_ulong(), c.c_uint(), c.POINTER(c.c_ulong)()
        ok = self.x.XQueryTree(self.d, w, c.byref(root), c.byref(parent), c.byref(children), c.byref(count))
        try: return list(children[:count.value]) if ok and count.value < 4096 else []
        finally:
            if children: self.x.XFree(children)

    def origin(self, w):
        x, y, child = c.c_int(), c.c_int(), c.c_ulong()
        if self.x.XTranslateCoordinates(self.d, w, self.root, 0, 0, c.byref(x), c.byref(y), c.byref(child)):
            return x.value, y.value

    def decoration(self, w, values):
        if values is None:
            self.x.XDeleteProperty(self.d, w, self.atom('_MOTIF_WM_HINTS'))
        else:
            data = (c.c_ulong * len(values))(*values)
            atom = self.atom('_MOTIF_WM_HINTS')
            self.x.XChangeProperty(self.d, w, atom, atom, 32, 0, data, len(values))

    def shape(self, w, regions):
        # Bounding shape also clips input; no overlay X windows can steal focus.
        if regions is None:
            self.ext.XShapeCombineMask(self.d, w, 0, 0, 0, 0, 0)
        else:
            rectangles = (Rect * len(regions))(*(Rect(*r) for r in regions))
            self.ext.XShapeCombineRectangles(self.d, w, 0, 0, 0, rectangles, len(regions), 0, 0)

def parse_mode(text):
    if not re.fullmatch(r'[01](?: [0-9]{1,5}){6}\n?', text): return None
    mode, dw, dh, x, y, w, h = map(int, text.split())
    if not 100 <= dw <= 32767 or not 100 <= dh <= 32767: return None
    if mode and (x != 0 or y != 0 or w != dw or h != dh): return None
    return mode, dw, dh, x, y, w, h

def valid_view(root, origin, mode):
    if not origin or not mode or not mode[0]: return None
    _, dw, dh, x, y, w, h = mode
    x += origin[0]; y += origin[1]
    if x < 0 or y < 0 or x+w > root.width or y+h > root.height: return None
    return root.width, root.height, x, y, w, h

def main():
    import fcntl
    lock = open('/tmp/decklite-display.lock', 'a')
    try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError: return
    x = X11()
    state = Path('/tmp/decklite-viewport.state')
    tracked, shapes = {}, {}
    idle_since = time.monotonic()
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    try:
        while True:
            view = None
            root = x.attrs(x.root)
            active = x.prop(x.root, '_NET_ACTIVE_WINDOW') or []
            clients = x.prop(x.root, '_NET_CLIENT_LIST') or []
            try:
                support = Path('/tmp/decklite-viewport.support')
                support_stat = support.stat()
                compatible = False
                if support_stat.st_size == 1 and 0 <= time.time()-support_stat.st_mtime < 3:
                    with support.open('rb') as stream:
                        compatible = stream.read(2) == b'1'
            except OSError:
                compatible = False
            if not compatible:
                clients = []  # Older APK / disconnected bridge retains Safe mode.
            present = set()
            for w in clients:
                title = x.prop(w, '_NET_WM_NAME') or x.prop(w, 'WM_NAME')
                if not isinstance(title, bytes): continue
                match = re.fullmatch(rb'DeckLite-([0-9]{1,10}) - Wine Desktop', title)
                if not match: continue
                mode_file = Path('/tmp/decklite-launch-' + match[1].decode() + '.mode')
                try:
                    if time.time()-mode_file.stat().st_mtime > 2.5 or mode_file.stat().st_size > 128: continue
                    mode = parse_mode(mode_file.read_text())
                except (OSError, ValueError): continue
                if not mode: continue
                present.add(w)
                a = x.attrs(w)
                if not a: continue
                if w not in tracked:
                    tracked[w] = x.prop(w, '_MOTIF_WM_HINTS')
                if x.prop(w, '_MOTIF_WM_HINTS') != [2, 0, 0, 0, 0]:
                    x.decoration(w, [2, 0, 0, 0, 0])
                regions = None
                if not mode[0]:
                    regions = []
                    for child in x.children(w):
                        ca = x.attrs(child)
                        if ca and ca.map_state == 2 and ca.width > 1 and ca.height > 1:
                            left, top = max(0, ca.x), max(0, ca.y)
                            right, bottom = min(a.width, ca.x+ca.width), min(a.height, ca.y+ca.height)
                            if right > left and bottom > top: regions.append((left, top, right-left, bottom-top))
                    regions = tuple(regions)
                if w not in shapes or shapes[w] != regions:
                    x.shape(w, regions); shapes[w] = regions
                if active and active[0] == w and a.map_state == 2 and root:
                    view = valid_view(root, x.origin(w), mode)
            for w in set(tracked)-present:
                x.shape(w, None); x.decoration(w, tracked.pop(w)); shapes.pop(w, None)
            x.x.XSync(x.d, 0)
            if view:
                pending = state.with_suffix('.new')
                pending.write_text('1 ' + ' '.join(map(str, view)) + '\n')
                pending.replace(state)
            else: state.unlink(missing_ok=True)
            if present: idle_since = time.monotonic()
            elif time.monotonic()-idle_since > 160: break
            time.sleep(0.5)
    except KeyboardInterrupt: pass
    finally:
        state.unlink(missing_ok=True)
        for w, hints in tracked.items():
            x.shape(w, None); x.decoration(w, hints)
        x.x.XSync(x.d, 0)
        x.x.XCloseDisplay(x.d)

if __name__ == '__main__': main()
