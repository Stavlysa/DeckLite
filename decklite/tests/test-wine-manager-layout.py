"""Real GTK/X11 small-screen regression; no Wine or runtime installer launches.

Preferences/prefixes are isolated. Run on the container with its real GTK theme.
DECKLITE_TEST_MANAGER_DIR may point to a candidate before installing it.
"""
import os
from pathlib import Path
import sys
import subprocess
import re
import tempfile
import time

sys.path.insert(0, "/opt/tiny/wine-manager")
sys.path.insert(0, os.environ.get("DECKLITE_TEST_MANAGER_DIR", "/opt/tiny/wine-manager"))
import wine_manager as manager
import ui_i18n
from gi.repository import Gdk, GLib, Gtk


def pump(seconds=0.16):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)
        time.sleep(0.005)


def within_workarea(window):
    rect = window.get_window().get_frame_extents()
    area = window.get_display().get_monitor_at_window(window.get_window()).get_workarea()
    # GTK3 CSD shadows are part of the X window, but are not visible controls.
    # This theme reserves 85 transparent pixels on EACH side: don't mistake
    # those shadow/input extents for a form overflowing the workarea.
    extents = subprocess.check_output(["xprop", "-id", str(window.get_window().get_xid()),
                                      "_GTK_FRAME_EXTENTS"], text=True)
    match = re.search(r"= (\d+), (\d+), (\d+), (\d+)", extents)
    left, right, top, bottom = map(int, match.groups()) if match else (0, 0, 0, 0)
    visible_width, visible_height = rect.width - left - right, rect.height - top - bottom
    sizes = (visible_width, visible_height, area.width, area.height, tuple(window.get_size()))
    assert visible_width <= area.width and visible_height <= area.height, sizes
    return visible_width, visible_height, area.width, area.height


with tempfile.TemporaryDirectory(prefix="decklite-layout-test-") as tmp:
    root = Path(tmp)
    manager.PREFIX_ROOT = root / "prefixes"
    manager.DEFAULT_PREFIX = root / "default"
    manager.LOCALE_FILE = root / "locale"
    manager.TIMEZONE_FILE = root / "timezone"
    manager.DISPLAY_MODE_FILE = root / "display"
    manager.load_language = lambda: "en"
    manager.save_language = lambda code: ui_i18n.save_language(code, root / "ui")
    window = manager.WineManager()
    window.show_all()
    pump(0.4)
    print("PASS initial frame/workarea:", within_workarea(window), flush=True)
    initial_environment = window.environment()
    assert len(window.action_buttons) == 13
    assert window.action_buttons[0].get_style_context().has_class("suggested-action")
    for lang in ui_i18n.LANGUAGES:
        window.ui_language_combo.set_active_id(lang)
        assert window.action_buttons[0].get_style_context().has_class("suggested-action")
        window.unmaximize()
        window.resize(520, 280)
        pump(0.3)
        w, h = window.get_size()
        assert w <= 522 and h <= 282, (lang, w, h)
        within_workarea(window)
        scroll = window.content_scroll
        vertical = scroll.get_vadjustment()
        assert vertical.get_upper() > vertical.get_page_size(), lang
        vertical.set_value(0)
        event = Gdk.Event.new(Gdk.EventType.SCROLL)
        event.direction = Gdk.ScrollDirection.DOWN
        event.window = window.locale_combo.get_window()
        window.locale_combo.emit("scroll-event", event)
        pump(0.25)
        assert vertical.get_value() > 0, "Wheel over a selector must scroll the form"
        assert window.environment() == initial_environment, "Scrolling must not change Wine settings"
        # Every action must be reachable via native scrollbar adjustments,
        # regardless of how FlowBox wraps it in this translation.
        viewport = scroll.get_child()
        content = viewport.get_child()
        for button in window.action_buttons:
            bx, by = button.translate_coordinates(content, 0, 0)
            horizontal = scroll.get_hadjustment()
            horizontal.set_value(min(bx, horizontal.get_upper() - horizontal.get_page_size()))
            vertical.set_value(min(by, vertical.get_upper() - vertical.get_page_size()))
            pump(0.025)
            assert 0 <= by - vertical.get_value() < vertical.get_page_size(), (lang, button.get_label())
            assert by + button.get_allocated_height() - vertical.get_value() <= vertical.get_page_size() + 1
        vertical.set_value(0)
        window.prefix_combo.grab_focus()
        window.action_buttons[-1].grab_focus()
        pump()
        _, focused_y = window.action_buttons[-1].translate_coordinates(content, 0, 0)
        assert 0 <= focused_y - vertical.get_value() < vertical.get_page_size(), "Keyboard focus must scroll into view"
        # A real bottom-row button signal still reaches its ordinary callback.
        calls = []
        original = window.refresh_status
        window.refresh_status = lambda: calls.append(True)
        window.action_buttons[-1].clicked()
        window.refresh_status = original
        assert calls == [True]
        assert window.environment() == initial_environment
        window.maximize()
        pump(0.3)
        print("PASS small/maximized, 13 reachable actions, language:", lang,
              within_workarea(window), flush=True)
    assert not manager.LOCALE_FILE.exists()
    assert not manager.TIMEZONE_FILE.exists()
    assert not manager.DISPLAY_MODE_FILE.exists()

    errors = []
    def inspect_cpu():
        dialog = next(w for w in Gtk.Window.list_toplevels() if isinstance(w, Gtk.Dialog) and w.get_visible())
        try:
            print("PASS CPU dialog frame/workarea:", within_workarea(dialog), flush=True)
            save = dialog.get_widget_for_response(Gtk.ResponseType.OK)
            _, y = save.translate_coordinates(dialog, 0, 0)
            assert y + save.get_allocated_height() <= dialog.get_allocated_height()
        except Exception as error:
            errors.append(error)
        finally:
            dialog.response(Gtk.ResponseType.CANCEL)
        return False
    GLib.timeout_add(300, inspect_cpu)
    window.on_cpu_cores()
    assert not errors, errors

    def inspect_picker():
        dialog = next(w for w in Gtk.Window.list_toplevels()
                      if isinstance(w, Gtk.FileChooserDialog) and w.get_visible())
        try:
            print("PASS EXE picker frame/workarea:", within_workarea(dialog), flush=True)
            for response in (Gtk.ResponseType.OK, Gtk.ResponseType.CANCEL):
                button = dialog.get_widget_for_response(response)
                _, y = button.translate_coordinates(dialog, 0, 0)
                assert y + button.get_allocated_height() <= dialog.get_allocated_height()
        except Exception as error:
            errors.append(error)
        finally:
            dialog.response(Gtk.ResponseType.CANCEL)
        return False
    GLib.timeout_add(600, inspect_picker)
    window.action_buttons[0].clicked()
    assert not errors, errors
    window.hide()
    print("PASS: no Wine processes launched and all preferences isolated", flush=True)
