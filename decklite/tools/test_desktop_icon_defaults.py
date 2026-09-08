#!/usr/bin/env python3
"""Exercise the one-time desktop icon defaults without an X11 session."""

import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest


class DesktopIconDefaultsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bash = shutil.which("bash")
        if not cls.bash:
            raise unittest.SkipTest("bash is required")
        source = Path(os.environ.get(
            "DECKLITE_START_DESKTOP_TEST_SOURCE",
            Path(__file__).resolve().parents[1]
            / "steam-overlay/opt/tiny/start-desktop.sh",
        )).read_text(encoding="utf-8")
        match = re.search(
            r"^apply_desktop_icon_defaults\(\) \{\n.*?^\}", source, re.M | re.S
        )
        if not match:
            raise AssertionError("desktop icon defaults function missing")
        cls.function = match.group()
        if not source.rstrip().endswith("apply_desktop_icon_defaults"):
            raise AssertionError("desktop startup does not apply icon defaults")

    def run_defaults(self, state, behavior="success"):
        script = r'''
set -eu
state_dir="$1"
log_file="$state_dir/log"
log() { printf '%s\n' "$*" >>"$log_file"; }
xfconf-query() {
    printf '%s\n' "$*" >>"$state_dir/calls"
    case "$2" in xfce4-desktop) ;; *) return 9 ;; esac
    case "$4" in /desktop-icons/file-icons/show-removable) ;; *) return 9 ;; esac
    case "$TEST_XFCONF_BEHAVIOR" in
        fail) return 1 ;;
        missing) [[ "$5" == --create ]] ;;
        success) return 0 ;;
    esac
}
'''
        result = subprocess.run(
            [self.bash, "-c", script + self.function
             + "\napply_desktop_icon_defaults\n", "test", str(state)],
            env={**os.environ, "TEST_XFCONF_BEHAVIOR": behavior},
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_existing_property(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)
            self.run_defaults(state)
            self.assertTrue((state / "desktop-icons-defaults-v1").exists())
            self.assertEqual((state / "calls").read_text().splitlines(), [
                "-c xfce4-desktop -p /desktop-icons/file-icons/show-removable -s false"
            ])

    def test_create_missing_property(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)
            self.run_defaults(state, "missing")
            self.assertTrue((state / "desktop-icons-defaults-v1").exists())
            calls = (state / "calls").read_text().splitlines()
            self.assertEqual(len(calls), 2)
            self.assertTrue(calls[1].endswith("--create -t bool -s false"))

    def test_preserve_later_user_choice(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)
            (state / "desktop-icons-defaults-v1").touch()
            self.run_defaults(state)
            self.assertFalse((state / "calls").exists())

    def test_retry_after_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)
            self.run_defaults(state, "fail")
            self.assertFalse((state / "desktop-icons-defaults-v1").exists())
            self.run_defaults(state)
            self.assertTrue((state / "desktop-icons-defaults-v1").exists())


if __name__ == "__main__":
    unittest.main()
