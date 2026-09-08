#!/usr/bin/env python3
"""Touch-friendly controls for Steam's intentionally borderless CEF window."""

from __future__ import annotations

import subprocess

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk  # noqa: E402


HELPER = "/opt/tiny/steam-arm64/steam-window-helper.sh"


class SteamWindowControls(Gtk.Window):
    def __init__(self) -> None:
        super().__init__(title="Steam Window Controls")
        self.set_default_size(520, 240)
        self.set_border_width(14)
        self.set_keep_above(True)
        self.connect("destroy", Gtk.main_quit)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.add(outer)
        explanation = Gtk.Label(
            label=(
                "DeckLite normally restores Steam's native X11 title bar and borders. "
                "These controls remain as a touch-friendly move and resize fallback."
            ),
            xalign=0,
        )
        explanation.set_line_wrap(True)
        outer.pack_start(explanation, False, False, 0)

        grid = Gtk.Grid(column_spacing=8, row_spacing=8, column_homogeneous=True)
        outer.pack_start(grid, True, True, 0)
        actions = [
            ("Move, then tap to place", "move"),
            ("Resize, then tap to finish", "resize"),
            ("Restore medium size", "reset"),
            ("Maximize / restore", "maximize"),
        ]
        for index, (label, action) in enumerate(actions):
            button = Gtk.Button(label=label)
            button.connect("clicked", self.on_action, action)
            grid.attach(button, index % 2, index // 2, 1, 1)

        self.status = Gtk.Label(label="Open Steam first.", xalign=0)
        outer.pack_start(self.status, False, False, 0)

    def find_window(self) -> str | None:
        result = subprocess.run(
            [HELPER, "--find"],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        return result.stdout.strip() if result.returncode == 0 else None

    def on_action(self, _button: Gtk.Button, action: str) -> None:
        window_id = self.find_window()
        if not window_id:
            self.status.set_text("Steam's main window was not found. Open Steam first.")
            return
        if action == "reset":
            result = subprocess.run([HELPER, "--reset"], check=False)
            self.status.set_text(
                "Steam restored to a centered medium window."
                if result.returncode == 0
                else "Could not resize Steam."
            )
            return

        key = "alt+F10" if action == "maximize" else f"alt+F{7 if action == 'move' else 8}"
        self.status.set_text(
            "Move the pointer or drag, then tap once to finish."
            if action == "move"
            else (
                "Move the pointer or drag, then tap once to finish."
                if action == "resize"
                else "Steam maximized/restored."
            )
        )
        # Run after GTK finishes the button-release event, otherwise the same
        # touch release can immediately cancel XFWM's interactive operation.
        GLib.timeout_add(180, self.send_window_command, window_id, key)

    def send_window_command(self, window_id: str, key: str) -> bool:
        subprocess.run(
            ["xdotool", "windowmap", window_id, "windowactivate", "--sync", window_id],
            check=False,
        )
        subprocess.run(["xdotool", "key", "--clearmodifiers", key], check=False)
        return False


def main() -> None:
    window = SteamWindowControls()
    window.show_all()
    Gtk.main()


if __name__ == "__main__":
    main()
