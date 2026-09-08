#!/usr/bin/env python3
"""Run the same verified Steam downloader that is shipped in the container."""

from __future__ import annotations

from pathlib import Path
import runpy


script = (
    Path(__file__).resolve().parents[1]
    / "steam-overlay/opt/tiny/steam-arm64/update_steam.py"
)
runpy.run_path(str(script), run_name="__main__")

