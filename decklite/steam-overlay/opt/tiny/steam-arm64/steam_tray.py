#!/usr/bin/env python3
"""Reliable XEmbed tray icon for the experimental native ARM64 Steam client."""

from __future__ import annotations

import fcntl
import os
from pathlib import Path
import subprocess

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk  # noqa: E402


HELPER = "/opt/tiny/steam-arm64/steam-window-helper.sh"
CONTROLS = "/opt/tiny/steam-arm64/steam_window_controls.py"


class SteamTray:
    def __init__(self) -> None:
        self.icon = Gtk.StatusIcon.new_from_icon_name("steam")
        self.icon.set_title("Steam ARM64")
        self.icon.set_tooltip_text("Steam ARM64")
        self.icon.set_visible(True)
        self.icon.connect("activate", self.show_steam)
        self.icon.connect("popup-menu", self.open_menu)

        self.menu = Gtk.Menu()
        for label, callback in (
            ("Show Steam", self.show_steam),
            ("Steam Window Controls", self.show_controls),
            ("Quit Steam", self.quit_steam),
        ):
            item = Gtk.MenuItem(label=label)
            item.connect("activate", callback)
            self.menu.append(item)
        self.menu.show_all()

    def steam_window(self) -> str | None:
        result = subprocess.run(
            [HELPER, "--find"],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        return result.stdout.strip() if result.returncode == 0 else None

    def show_steam(self, *_args) -> None:
        window_id = self.steam_window()
        if window_id:
            subprocess.run(
                [
                    "xdotool",
                    "windowmap",
                    window_id,
                    "windowraise",
                    window_id,
                    "windowactivate",
                    "--sync",
                    window_id,
                ],
                check=False,
            )

    def show_controls(self, *_args) -> None:
        subprocess.Popen([CONTROLS], start_new_session=True)

    def quit_steam(self, *_args) -> None:
        for proc in Path("/proc").iterdir():
            if not proc.name.isdigit():
                continue
            try:
                executable = os.readlink(proc / "exe")
                command = (proc / "cmdline").read_bytes().split(b"\0")
            except (OSError, PermissionError):
                continue
            if executable.endswith("/steam") and any(
                b"/steamrtarm64/steam" in part for part in command
            ):
                subprocess.Popen([executable, "-shutdown"], start_new_session=True)
                return

    def open_menu(self, icon: Gtk.StatusIcon, button: int, time: int) -> None:
        self.menu.popup(None, None, icon.position_menu, icon, button, time)


def main() -> None:
    state_dir = Path.home() / ".local/share/decklite-steam"
    state_dir.mkdir(parents=True, exist_ok=True)
    lock = (state_dir / "steam-tray.lock").open("w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return
    SteamTray()
    Gtk.main()


if __name__ == "__main__":
    main()
