#!/usr/bin/env python3
"""Small GTK3 frontend for Hangover Wine prefixes in DeckLite."""

from __future__ import annotations

import os
from pathlib import Path
import re
import subprocess
import sys

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, GLib, Gtk, Pango  # noqa: E402
from cpu_policy import inventory, load_preference, save_preference  # noqa: E402
from ui_i18n import LANGUAGES, load_language, save_language, translate  # noqa: E402
from wine_timezone import TIMEZONES, load_timezone, save_timezone, timezone_env, timezone_label  # noqa: E402


PREFIX_ROOT = Path.home() / ".local/share/decklite-wine/prefixes"
DEFAULT_PREFIX = Path.home() / ".wine"
RUNNER = "/opt/tiny/wine-manager/wine-prefix-run"
RUN_EXE = "/opt/tiny/steam-arm64/run-exe.sh"
DXVK = "/opt/tiny/wine-manager/install-dxvk.sh"
RUNTIMES = "/opt/tiny/wine-manager/install-game-runtimes.sh"
DISPLAY_MODE_FILE = Path.home() / ".config/decklite/wine-display-mode"
CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")) / "decklite"
LOCALE_FILE = CONFIG_DIR / "wine-locale"
TIMEZONE_FILE = CONFIG_DIR / "wine-timezone"
LOCALE_LANGUAGES = {
    "zh_TW.UTF-8": "zh_TW:zh:en",
    "zh_CN.UTF-8": "zh_CN:zh:en",
    "ja_JP.UTF-8": "ja_JP:ja:en",
    "ru_RU.UTF-8": "ru_RU:ru:en",
    "en_US.UTF-8": "en_US:en",
}


def fit_initial_window(window: Gtk.Window, width: int, height: int) -> None:
    """Use logical desktop workarea pixels, not the Android panel resolution."""
    display = window.get_display()
    parent = window.get_transient_for()
    native = parent.get_window() if parent else window.get_window()
    monitor = display.get_monitor_at_window(native) if native else display.get_primary_monitor()
    monitor = monitor or display.get_monitor(0)
    if monitor is not None:
        area = monitor.get_workarea()
        # Window.get_size/default_size exclude the CSD titlebar. Leave room for
        # it, outer borders and the desktop panel instead of hiding the bottom.
        width = min(width, max(1, area.width - 32))
        height = min(height, max(1, area.height - 80))
    window.set_default_size(width, height)
    if window.get_mapped():
        window.resize(width, height)


def compact_combo(combo: Gtk.ComboBoxText) -> Gtk.ComboBoxText:
    # Long translated values/prefix paths must not impose a desktop-sized
    # minimum width. The popup and tooltip still expose the complete value.
    for cell in combo.get_cells():
        if isinstance(cell, Gtk.CellRendererText):
            cell.set_property("ellipsize", Pango.EllipsizeMode.END)
            cell.set_property("width-chars", 18)
    combo.connect("changed", lambda widget: widget.set_tooltip_text(widget.get_active_text()))
    def scroll_form(widget, event):
        # Scrolling down the form must not silently change Windows language,
        # display mode, time zone, backend or the selected prefix under the pointer.
        if not widget.get_property("popup-shown"):
            parent = widget.get_ancestor(Gtk.ScrolledWindow)
            if parent is not None:
                directions = {
                    Gdk.ScrollDirection.UP: (0, -1), Gdk.ScrollDirection.DOWN: (0, 1),
                    Gdk.ScrollDirection.LEFT: (-1, 0), Gdk.ScrollDirection.RIGHT: (1, 0),
                }
                if event.direction == Gdk.ScrollDirection.SMOOTH:
                    valid, dx, dy = event.get_scroll_deltas()
                    if not valid:
                        return True
                else:
                    dx, dy = directions.get(event.direction, (0, 0))
                for adjustment, delta in ((parent.get_hadjustment(), dx),
                                          (parent.get_vadjustment(), dy)):
                    value = adjustment.get_value() + delta * max(1, adjustment.get_step_increment())
                    adjustment.set_value(max(adjustment.get_lower(), min(value,
                        adjustment.get_upper() - adjustment.get_page_size())))
                return True
        return False
    combo.connect("scroll-event", scroll_form)
    combo.set_tooltip_text(combo.get_active_text())
    return combo


class WineManager(Gtk.Window):
    def __init__(self) -> None:
        super().__init__(title="DeckLite Wine Manager")
        self.ui_language = load_language()
        self._translations = []
        self._translated_combos = []
        self._combo_handlers = {}
        self.bind_text(self, "DeckLite Wine Manager", "set_title")
        fit_initial_window(self, 1080, 540)
        self.set_border_width(8)
        self.processes: list[subprocess.Popen[bytes]] = []

        header = Gtk.HeaderBar(title="DeckLite Wine Manager")
        self.bind_text(header, "DeckLite Wine Manager", "set_title")
        self.bind_text(header, "Hangover 11.16 · Win32 + Win64 on ARM64", "set_subtitle")
        header.set_show_close_button(True)
        self.set_titlebar(header)

        # Scroll the WHOLE form, not just Activity. Without this, the fixed
        # rows impose a minimum window height larger than a phone's desktop,
        # so even the window manager cannot maximize it into the workarea.
        self.content_scroll = Gtk.ScrolledWindow()
        self.content_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.content_scroll.set_overlay_scrolling(False)
        self.content_scroll.set_propagate_natural_height(False)
        self.content_scroll.set_propagate_natural_width(False)
        self.add(self.content_scroll)
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.content_scroll.add(outer)
        outer.set_focus_vadjustment(self.content_scroll.get_vadjustment())
        outer.set_focus_hadjustment(self.content_scroll.get_hadjustment())

        selector = Gtk.Grid(column_spacing=8, row_spacing=6)
        outer.pack_start(selector, False, False, 0)
        selector.attach(self.label("Wine prefix"), 0, 0, 1, 1)
        self.prefix_combo = compact_combo(Gtk.ComboBoxText())
        self.prefix_combo.set_hexpand(True)
        selector.attach(self.prefix_combo, 1, 0, 4, 1)
        new_button = self.bind_text(Gtk.Button(), "New prefix")
        new_button.connect("clicked", self.on_new_prefix)
        selector.attach(new_button, 5, 0, 1, 1)

        selector.attach(self.label("32-bit backend"), 0, 1, 1, 1)
        self.backend_combo = self.translated_combo([
            ("auto", "Automatic (FEX compatibility)"), ("box64", "Box64"), ("fex", "FEX")
        ], "auto")
        selector.attach(self.backend_combo, 1, 1, 2, 1)

        selector.attach(self.label("Game display"), 0, 2, 1, 1)
        self.display_combo = self.translated_combo([
            ("auto", "Automatic: fullscreen or windowed as selected in the game"),
            ("safe", "Safe virtual desktop (compatibility fallback)"),
            ("borderless", "Borderless fullscreen (set game to Windowed)"),
            ("native", "Native fullscreen (can black-screen old games)"),
        ], self.load_display_mode())
        self._combo_handlers[self.display_combo] = self.display_combo.connect("changed", self.on_display_mode_changed)
        selector.attach(self.display_combo, 1, 2, 2, 1)

        selector.attach(self.label("Windows language"), 3, 1, 1, 1)
        self.locale_combo = self.translated_combo([
            ("en_US.UTF-8", "English"), ("zh_TW.UTF-8", "Traditional Chinese"),
            ("zh_CN.UTF-8", "Simplified Chinese"), ("ja_JP.UTF-8", "Japanese"),
            ("ru_RU.UTF-8", "Russian"),
        ], self.load_locale())
        self._combo_handlers[self.locale_combo] = self.locale_combo.connect("changed", self.on_locale_changed)
        selector.attach(self.locale_combo, 4, 1, 2, 1)

        selector.attach(self.label("CPU cores"), 3, 2, 1, 1)
        self.cpu_button = self.bind_text(Gtk.Button(), "Choose CPU cores…")
        self.cpu_button.connect("clicked", self.on_cpu_cores)
        selector.attach(self.cpu_button, 4, 2, 2, 1)

        selector.attach(self.label("Interface language"), 0, 3, 1, 1)
        self.ui_language_combo = compact_combo(Gtk.ComboBoxText())
        for code, name in LANGUAGES.items():
            self.ui_language_combo.append(code, name)
        self.ui_language_combo.set_active_id(self.ui_language)
        self.ui_language_combo.connect("changed", self.on_ui_language_changed)
        selector.attach(self.ui_language_combo, 1, 3, 2, 1)
        selector.attach(self.label("Time zone (UTC)"), 3, 3, 1, 1)
        self.timezone_combo = self.translated_combo([
            (value, timezone_label(value)) for value in TIMEZONES
        ], load_timezone(TIMEZONE_FILE))
        self._combo_handlers[self.timezone_combo] = self.timezone_combo.connect("changed", self.on_timezone_changed)
        selector.attach(self.timezone_combo, 4, 3, 2, 1)
        hint = self.label("Interface, Windows language and time zone are independent. Restart Wine apps after changing Windows language or time zone. UTC offsets are fixed (no daylight saving).")
        hint.set_line_wrap(True)
        hint.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        hint.set_max_width_chars(90)

        actions = Gtk.FlowBox()
        actions.set_selection_mode(Gtk.SelectionMode.NONE)
        actions.set_min_children_per_line(1)
        actions.set_max_children_per_line(4)
        actions.set_homogeneous(True)
        actions.set_column_spacing(4)
        actions.set_row_spacing(4)
        outer.pack_start(actions, False, False, 0)
        buttons = [
            ("Run EXE / MSI", self.on_run_file),
            ("Wine configuration", lambda *_: self.launch(["winecfg"], "winecfg")),
            ("Registry editor", lambda *_: self.launch(["regedit"], "regedit")),
            ("Uninstall programs", lambda *_: self.launch(["wine", "uninstaller"], "uninstaller")),
            ("Windows file manager", lambda *_: self.launch(["winefile"], "winefile")),
            ("Open drive C", self.on_open_drive),
            ("Enable / refresh DXVK", lambda *_: self.dxvk("enable")),
            ("Disable DXVK", lambda *_: self.dxvk("disable")),
            ("Install common game runtimes", lambda *_: self.runtimes("common")),
            ("Install legacy audio / video", lambda *_: self.runtimes("legacy-media")),
            ("Install .NET 4.8 + XNA 4", lambda *_: self.runtimes("dotnet-xna")),
            ("Stop Wine processes", self.on_stop_wine),
            ("Refresh status", lambda *_: self.refresh_status()),
        ]
        self.action_buttons = []
        for label, callback in buttons:
            button = self.bind_text(Gtk.Button(), label)
            if label == "Run EXE / MSI":
                button.get_style_context().add_class("suggested-action")
                emphasis = Pango.AttrList()
                emphasis.insert(Pango.attr_weight_new(Pango.Weight.BOLD))
                button.get_child().set_attributes(emphasis)
            button.get_child().set_line_wrap(True)
            button.get_child().set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
            button.get_child().set_max_width_chars(24)
            button.connect("clicked", callback)
            actions.insert(button, -1)
            self.action_buttons.append(button)

        self.status = Gtk.Label(xalign=0)
        self.status.set_line_wrap(True)
        self.status.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
        self.status.set_max_width_chars(90)
        self.activity_expander = self.bind_text(Gtk.Expander(), "Activity")
        self.activity_expander.set_expanded(False)
        outer.pack_start(self.activity_expander, False, False, 0)
        details = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.activity_expander.add(details)
        details.pack_start(hint, False, False, 0)
        details.pack_start(self.status, False, False, 0)
        scroll = Gtk.ScrolledWindow()
        scroll.set_min_content_height(96)
        details.pack_start(scroll, True, True, 0)
        self.log_buffer = Gtk.TextBuffer()
        log_view = Gtk.TextView(buffer=self.log_buffer)
        log_view.set_editable(False)
        log_view.set_cursor_visible(False)
        log_view.set_monospace(True)
        log_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        scroll.add(log_view)

        PREFIX_ROOT.mkdir(parents=True, exist_ok=True)
        self.refresh_prefixes()
        self.refresh_status()
        self.connect("destroy", Gtk.main_quit)

    def tr(self, message: str, **values: object) -> str:
        return translate(self.ui_language, message, **values)

    def bind_text(self, widget, message: str, method: str = "set_label"):
        update = lambda: getattr(widget, method)(self.tr(message))
        self._translations.append(update)
        update()
        return widget

    def label(self, message: str):
        return self.bind_text(Gtk.Label(xalign=0), message)

    def translated_combo(self, entries, active: str):
        combo = compact_combo(Gtk.ComboBoxText())
        for code, message in entries:
            combo.append(code, self.tr(message))
        combo.set_active_id(active)
        self._translated_combos.append((combo, entries))
        return combo

    def on_ui_language_changed(self, *_args) -> None:
        chosen = self.ui_language_combo.get_active_id() or "en"
        if chosen == self.ui_language:
            return
        try:
            save_language(chosen)
        except (OSError, ValueError) as error:
            self.ui_language_combo.set_active_id(self.ui_language)
            self.error(self.tr("Could not save interface language: {error}", error=error))
            return
        self.ui_language = chosen
        for update in self._translations:
            update()
        # Replacing translated labels must NOT fire Windows/display preference
        # callbacks or change stable backend/prefix IDs. Running apps stay alive.
        for combo, entries in self._translated_combos:
            active = combo.get_active_id()
            handler = self._combo_handlers.get(combo)
            if handler is not None:
                combo.handler_block(handler)
            try:
                combo.remove_all()
                for code, message in entries:
                    combo.append(code, self.tr(message))
                combo.set_active_id(active)
            finally:
                if handler is not None:
                    combo.handler_unblock(handler)
        self.refresh_prefixes()
        self.refresh_status()
        self.log(self.tr("Interface language saved."))

    def log(self, message: str) -> None:
        end = self.log_buffer.get_end_iter()
        self.log_buffer.insert(end, message.rstrip() + "\n")

    @staticmethod
    def load_display_mode() -> str:
        try:
            mode = DISPLAY_MODE_FILE.read_text(encoding="ascii").strip()
        except OSError:
            return "auto"
        return mode if mode in {"auto", "safe", "borderless", "native"} else "auto"

    def on_display_mode_changed(self, *_args) -> None:
        mode = self.display_combo.get_active_id() or "auto"
        DISPLAY_MODE_FILE.parent.mkdir(parents=True, exist_ok=True)
        temporary = DISPLAY_MODE_FILE.with_name(DISPLAY_MODE_FILE.name + ".tmp")
        temporary.write_text(mode + "\n", encoding="ascii")
        temporary.replace(DISPLAY_MODE_FILE)
        if hasattr(self, "log_buffer"):
            self.log(self.tr("Global game display mode saved: {mode}", mode=mode))

    @staticmethod
    def load_locale() -> str:
        try:
            locale = LOCALE_FILE.read_text(encoding="ascii").strip()
        except (OSError, UnicodeError):
            return "en_US.UTF-8"
        return locale if locale in LOCALE_LANGUAGES else "en_US.UTF-8"

    def on_locale_changed(self, *_args) -> None:
        locale = self.locale_combo.get_active_id() or "en_US.UTF-8"
        if locale not in LOCALE_LANGUAGES:
            locale = "en_US.UTF-8"
        LOCALE_FILE.parent.mkdir(parents=True, exist_ok=True)
        temporary = LOCALE_FILE.with_name(LOCALE_FILE.name + ".tmp")
        temporary.write_text(locale + "\n", encoding="ascii")
        temporary.replace(LOCALE_FILE)
        if hasattr(self, "log_buffer"):
            self.log(self.tr("Global Windows language saved: {locale}", locale=locale))

    def on_timezone_changed(self, *_args) -> None:
        value = self.timezone_combo.get_active_id() or "0"
        try:
            save_timezone(value, TIMEZONE_FILE)
        except (OSError, ValueError) as error:
            handler = self._combo_handlers[self.timezone_combo]
            self.timezone_combo.handler_block(handler)
            try:
                self.timezone_combo.set_active_id(load_timezone(TIMEZONE_FILE))
            finally:
                self.timezone_combo.handler_unblock(handler)
            self.error(self.tr("Could not save time zone: {error}", error=error))
            return
        if hasattr(self, "log_buffer"):
            self.log(self.tr("Wine time zone saved: {zone}. Close all Wine apps and reopen them to apply.", zone=self.tr(timezone_label(value))))

    def refresh_prefixes(self, select: Path | None = None) -> None:
        wanted = str(select or self.current_prefix(fallback=True))
        self.prefix_combo.remove_all()
        self.prefix_combo.append(str(DEFAULT_PREFIX), self.tr("Default (~/.wine)"))
        for path in sorted(PREFIX_ROOT.iterdir()):
            if path.is_dir():
                self.prefix_combo.append(str(path), path.name)
        if not self.prefix_combo.set_active_id(wanted):
            self.prefix_combo.set_active_id(str(DEFAULT_PREFIX))

    def on_cpu_cores(self, *_args) -> None:
        rows, big, detected = inventory()
        mode, saved = load_preference()
        available = {row["id"] for row in rows if row["available"]}
        dialog = Gtk.Dialog(title=self.tr("Wine CPU cores"), transient_for=self, modal=True)
        fit_initial_window(dialog, 620, 520)
        dialog.add_buttons(self.tr("Cancel"), Gtk.ResponseType.CANCEL, self.tr("Save"), Gtk.ResponseType.OK)
        box = dialog.get_content_area()
        box.set_border_width(12)
        box.set_spacing(10)
        combo = Gtk.ComboBoxText()
        combo.append("big", self.tr("Automatic: all big + prime cores"))
        combo.append("all", self.tr("All available cores"))
        combo.append("custom", self.tr("Custom: tick cores below"))
        combo.set_active_id(mode)
        box.pack_start(combo, False, False, 0)
        info = Gtk.Label(xalign=0)
        info.set_line_wrap(True)
        info.set_text(
            self.tr("Applies to every Wine prefix. Save, close all Wine apps, then restart the container.")
            + "\n" + self.tr("Big/prime cores detected automatically." if detected else
                            "Cannot distinguish core tiers; Automatic uses available cores.")
        )
        box.pack_start(info, False, False, 0)
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        box.pack_start(scroll, True, True, 0)
        checks_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        scroll.add(checks_box)
        checks = {}
        updating = False

        def ticked(_button) -> None:
            nonlocal updating
            if not updating:
                updating = True
                combo.set_active_id("custom")
                updating = False

        for row in rows:
            cpu = row["id"]
            tier = self.tr("big/prime") if detected and cpu in big else ""
            frequency = self.tr(" · max {frequency:.2f} GHz", frequency=row["frequency"] / 1000000) if row["frequency"] else ""
            unavailable = self.tr(" · unavailable") if not row["available"] else ""
            check = Gtk.CheckButton(label=f"CPU {cpu} {tier}{frequency}{unavailable}")
            check.set_sensitive(row["available"])
            checks[cpu] = check
            checks_box.pack_start(check, False, False, 0)
            check.connect("toggled", ticked)

        def select_mode(*_args) -> None:
            nonlocal updating
            if updating:
                return
            updating = True
            chosen = combo.get_active_id()
            selected = big if chosen == "big" else available if chosen == "all" else saved
            for cpu, check in checks.items():
                check.set_active(cpu in selected and cpu in available)
            updating = False

        combo.connect("changed", select_mode)
        select_mode()
        warning = Gtk.Label(xalign=0)
        warning.set_line_wrap(True)
        box.pack_start(warning, False, False, 0)
        dialog.show_all()
        while dialog.run() == Gtk.ResponseType.OK:
            chosen = combo.get_active_id() or "big"
            selected = {cpu for cpu, check in checks.items() if check.get_active()}
            if chosen == "custom" and not selected:
                warning.set_text(self.tr("Select at least one available CPU."))
                continue
            try:
                save_preference(chosen, selected)
            except (OSError, ValueError) as error:
                warning.set_text(self.tr("Could not save CPU settings: {error}", error=error))
                continue
            self.log(self.tr("Global CPU policy saved: {mode}; cores {cores}. Close all Wine apps and restart the container to apply.", mode=chosen, cores=sorted(selected)))
            self.refresh_status()
            break
        dialog.destroy()

    def current_prefix(self, fallback: bool = False) -> Path:
        active = self.prefix_combo.get_active_id() if hasattr(self, "prefix_combo") else None
        if active:
            return Path(active)
        if fallback:
            return DEFAULT_PREFIX
        raise RuntimeError(self.tr("No Wine prefix is selected"))

    def environment(self) -> dict[str, str]:
        environment = os.environ.copy()
        environment["WINEPREFIX"] = str(self.current_prefix())
        environment["HODLL64"] = "libarm64ecfex.dll"
        mmap_shim = "/opt/tiny/extra/libmmap_shim.so"
        preload = [item for item in environment.get("LD_PRELOAD", "").split(":") if item]
        if Path(mmap_shim).is_file() and mmap_shim not in preload:
            preload.insert(0, mmap_shim)
        if preload:
            environment["LD_PRELOAD"] = ":".join(preload)
        backend = self.backend_combo.get_active_id()
        if backend == "box64":
            environment["HODLL"] = "wowbox64.dll"
        elif backend == "fex":
            environment["HODLL"] = "libwow64fex.dll"
        else:
            environment["HODLL"] = "libwow64fex.dll"
        environment["DECKLITE_WINE_DISPLAY_MODE"] = (
            self.display_combo.get_active_id() or "auto"
        )
        locale = self.locale_combo.get_active_id() or "en_US.UTF-8"
        if locale not in LOCALE_LANGUAGES:
            locale = "en_US.UTF-8"
        environment["DECKLITE_WINE_LOCALE"] = locale
        environment["LANG"] = locale
        environment["LC_ALL"] = locale
        environment["LANGUAGE"] = LOCALE_LANGUAGES[locale]
        offset = self.timezone_combo.get_active_id() or "0"
        environment["DECKLITE_WINE_UTC_OFFSET"] = offset
        environment["TZ"] = timezone_env(offset)
        return environment

    def launch(
        self,
        command: list[str],
        label: str,
        cwd: Path | None = None,
        through_prefix_runner: bool = True,
    ) -> None:
        prefix = self.current_prefix()
        full_command = (
            [RUNNER, str(prefix), *command] if through_prefix_runner else command
        )
        log_path = Path.home() / "wine-manager.log"
        log_handle = log_path.open("ab")
        try:
            process = subprocess.Popen(
                full_command,
                cwd=cwd,
                env=self.environment(),
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        finally:
            log_handle.close()
        self.processes.append(process)
        self.log(self.tr("Started {label} in {prefix} (PID {pid})", label=label, prefix=prefix, pid=process.pid))
        self.status.set_text(self.tr("Running {label}. Detailed log: {path}", label=label, path=log_path))

    def dxvk(self, action: str) -> None:
        self.launch([DXVK, str(self.current_prefix()), action], f"DXVK {action}")

    def runtimes(self, profile: str) -> None:
        self.launch(
            [RUNTIMES, str(self.current_prefix()), profile],
            self.tr("Game runtimes ({profile})", profile=profile),
        )

    def on_run_file(self, *_args) -> None:
        dialog = Gtk.FileChooserDialog(
            title=self.tr("Choose a Windows program"),
            parent=self,
            action=Gtk.FileChooserAction.OPEN,
        )
        dialog.add_buttons(
            self.tr("Cancel"),
            Gtk.ResponseType.CANCEL,
            self.tr("Open"),
            Gtk.ResponseType.OK,
        )
        # GTK restores the file chooser's last size when mapping it, which may
        # come from a much larger desktop. Refit after that restoration too.
        fit_initial_window(dialog, 960, 540)
        dialog.connect("map", lambda window: fit_initial_window(window, 960, 540))
        windows_filter = Gtk.FileFilter()
        windows_filter.set_name(self.tr("Windows programs (*.exe, *.msi)"))
        windows_filter.add_pattern("*.exe")
        windows_filter.add_pattern("*.EXE")
        windows_filter.add_pattern("*.msi")
        windows_filter.add_pattern("*.MSI")
        dialog.add_filter(windows_filter)
        all_filter = Gtk.FileFilter()
        all_filter.set_name(self.tr("All files"))
        all_filter.add_pattern("*")
        dialog.add_filter(all_filter)
        response = dialog.run()
        filename = dialog.get_filename()
        dialog.destroy()
        if response == Gtk.ResponseType.OK and filename:
            self.open_windows_file(Path(filename))

    def open_windows_file(self, path: Path) -> None:
        if path.suffix.lower() == ".msi":
            self.launch(
                ["wine", "msiexec", "/i", str(path)], path.name, cwd=path.parent
            )
        else:
            self.launch(
                [RUN_EXE, str(path)],
                path.name,
                cwd=path.parent,
                through_prefix_runner=False,
            )

    def on_new_prefix(self, *_args) -> None:
        dialog = Gtk.Dialog(title=self.tr("Create Wine prefix"), transient_for=self, modal=True)
        dialog.add_buttons(self.tr("Cancel"), Gtk.ResponseType.CANCEL, self.tr("Create"), Gtk.ResponseType.OK)
        entry = Gtk.Entry()
        entry.set_placeholder_text(self.tr("Example: game-name"))
        template_combo = Gtk.ComboBoxText()
        template_combo.append(
            "game-complete", self.tr("Game Complete (VC++/DirectX/audio; recommended)")
        )
        template_combo.append(
            "dotnet-xna-complete", self.tr(".NET/XNA Complete (separate compatibility template)")
        )
        template_combo.append("clean", self.tr("Clean Hangover prefix"))
        template_combo.set_active_id("game-complete")
        box = dialog.get_content_area()
        box.set_spacing(8)
        box.pack_start(Gtk.Label(label=self.tr("Prefix name (letters, numbers, dot, dash or underscore)")), False, False, 0)
        box.pack_start(entry, False, False, 0)
        box.pack_start(Gtk.Label(label=self.tr("Offline template"), xalign=0), False, False, 0)
        box.pack_start(template_combo, False, False, 0)
        dialog.show_all()
        response = dialog.run()
        name = entry.get_text().strip()
        template = template_combo.get_active_id() or "game-complete"
        dialog.destroy()
        if response != Gtk.ResponseType.OK:
            return
        if not re.fullmatch(r"[A-Za-z0-9._-]+", name) or name in {".", ".."}:
            self.error(self.tr("Invalid prefix name"))
            return
        prefix = PREFIX_ROOT / name
        prefix.mkdir(parents=True, exist_ok=True)
        (prefix / ".decklite-template-request").write_text(
            template + "\n",
            encoding="ascii",
        )
        self.refresh_prefixes(prefix)
        self.launch(["winecfg"], self.tr("Initialize {name}", name=name))

    def on_open_drive(self, *_args) -> None:
        prefix = self.current_prefix()
        self.launch(["xdg-open", str(prefix / "drive_c")], "drive C")

    def on_stop_wine(self, *_args) -> None:
        environment = self.environment()
        subprocess.run(["wineserver", "-k"], env=environment, check=False)
        self.log(self.tr("Stopped Wine processes in {prefix}", prefix=self.current_prefix()))
        self.refresh_status()

    def refresh_status(self) -> None:
        prefix = self.current_prefix(fallback=True)
        installed = Path("/usr/bin/wine").is_file()
        initialized = (prefix / "system.reg").is_file()
        dxvk_enabled = (prefix / ".decklite-dxvk-enabled").is_file()
        runtime_profiles = [
            name
            for name in ("common", "legacy-media", "dotnet-xna")
            if (prefix / f".decklite-runtimes-{name}").is_file()
        ]
        template = self.tr("custom")
        template_marker = prefix / ".decklite-template"
        if template_marker.is_file():
            template = template_marker.read_text(encoding="ascii", errors="replace").strip()
        self.status.set_text(self.tr(
            "Hangover: {installed} · Prefix: {ready} · Template: {template} · DXVK: {dxvk} · Runtimes: {runtimes} · Global display: {display} · CPU policy: {cpu} · Windows language: {locale}",
            installed=self.tr("installed" if installed else "missing"),
            ready=self.tr("ready" if initialized else "not initialized"), template=template,
            dxvk=self.tr("enabled" if dxvk_enabled else "disabled"),
            runtimes=", ".join(runtime_profiles) if runtime_profiles else self.tr("not added"),
            display=self.display_combo.get_active_id() or "auto", cpu=load_preference()[0],
            locale=self.locale_combo.get_active_id() or "en_US.UTF-8",
        ))

    def error(self, message: str) -> None:
        dialog = Gtk.MessageDialog(
            transient_for=self,
            modal=True,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.NONE,
            text=message,
        )
        dialog.add_button(self.tr("OK"), Gtk.ResponseType.OK)
        dialog.run()
        dialog.destroy()


def main() -> None:
    window = WineManager()
    window.show_all()
    if len(sys.argv) > 1:
        GLib.idle_add(window.open_windows_file, Path(sys.argv[1]))
    Gtk.main()


if __name__ == "__main__":
    main()
