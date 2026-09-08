#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


SCRIPT = Path(__file__).parents[1] / "tools" / "compact_steam_rootfs.py"
SPEC = importlib.util.spec_from_file_location("compact_steam_rootfs", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class CompactSteamRootfsTest(unittest.TestCase):
    def test_keeps_every_game_runtime(self) -> None:
        for path in (
            "home/tiny/.local/share/Steam/steamrtarm64/steam",
            "home/tiny/.local/share/Steam/compatibilitytools.d/GE-Proton11-6-aarch64/proton",
            "opt/tiny/wine-manager/prefix-templates/game-complete/system.reg",
            "opt/tiny/wine-manager/prefix-templates/dotnet-xna-complete/system.reg",
            "usr/lib/wine/aarch64-windows/wined3d.dll",
            "usr/lib/wine/i386-windows/wined3d.dll",
        ):
            self.assertIsNone(MODULE.exclusion_reason(path), path)

    def test_removes_only_declared_non_runtime_classes(self) -> None:
        expected = {
            "usr/include/wine/windows/windows.h": "development toolchain",
            "usr/lib/gcc/aarch64-linux-gnu/14/libgcc.a": "development toolchain",
            "usr/lib/aarch64-linux-gnu/libc.a": "development toolchain",
            "usr/bin/aarch64-linux-gnu-gcc-14": "development toolchain",
            "usr/share/man/man1/gcc.1.gz": "non-runtime documentation",
            "usr/share/doc/wine/changelog.gz": "non-license package documentation",
            "var/cache/swcatalog/cache-C-foo": "generated package cache",
            "usr/lib/firefox-esr/libxul.so": "optional Firefox browser",
            "usr/share/applications/firefox-esr.desktop": "optional Firefox browser",
            "opt/tiny/edraw/edraw": "optional non-gaming desktop stack",
            "usr/lib/aarch64-linux-gnu/libQt5Core.so.5": "optional non-gaming desktop stack",
            "usr/lib/aarch64-linux-gnu/libgdal.so.36": "optional non-gaming desktop stack",
            "usr/lib/aarch64-linux-gnu/libonnxruntime.so.1": "optional non-gaming desktop stack",
            "usr/lib/aarch64-linux-gnu/sane/libsane.so": "optional non-gaming desktop stack",
            "usr/share/proj/proj.db": "optional non-gaming desktop stack",
            "usr/lib/udev/hwdb.bin": "unused PRoot desktop data",
            "usr/lib/aarch64-linux-gnu/libgtk-4.so.1": "unused PRoot desktop data",
            "usr/share/plymouth/themes/spinner/watermark.png": "unused PRoot desktop data",
            "usr/share/desktop-base/emerald-theme/wallpaper.svg": "unused PRoot desktop data",
            "usr/share/i18n/locales/fr_FR": "unused PRoot desktop data",
            "usr/lib/python3.13/__pycache__/types.cpython-313.pyc": "regenerable Python bytecode",
            "usr/lib/aarch64-linux-gnu/libopencv_core.so.410": "optional non-gaming desktop stack",
            "usr/lib/aarch64-linux-gnu/libflite_cmu_us_slt.so.2": "optional non-gaming desktop stack",
            "usr/share/gdcm-3.0/XML/Part3.xml": "optional non-gaming desktop stack",
        }
        for path, reason in expected.items():
            self.assertEqual(MODULE.exclusion_reason(path), reason, path)

    def test_keeps_license_notices_and_supported_languages(self) -> None:
        for path in (
            "usr/share/doc/wine/copyright",
            "usr/share/doc/decklite-steam-arm64/tgcompat/PROVENANCE.md",
            "usr/share/doc/decklite-steam-arm64/tgcompat/robust_shim.c",
            "usr/share/locale/en/LC_MESSAGES/app.mo",
            "usr/share/locale/zh_TW/LC_MESSAGES/app.mo",
            "usr/share/locale/zh_CN/LC_MESSAGES/app.mo",
            "usr/share/locale/ja/LC_MESSAGES/app.mo",
            "usr/share/locale/ru/LC_MESSAGES/app.mo",
            "usr/share/locale/locale.alias",
        ):
            self.assertIsNone(MODULE.exclusion_reason(path), path)

    def test_removes_unsupported_translations(self) -> None:
        self.assertEqual(
            MODULE.exclusion_reason("usr/share/locale/fr/LC_MESSAGES/app.mo"),
            "unsupported translation",
        )


if __name__ == "__main__":
    unittest.main()
