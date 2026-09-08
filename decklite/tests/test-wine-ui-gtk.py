"""Real GTK widget regression on the test container; no Wine process launches.

All preferences and prefixes are redirected to a temporary test directory.
"""
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0, os.environ.get("DECKLITE_TEST_MANAGER_DIR", "/opt/tiny/wine-manager"))
import ui_i18n
import wine_manager as manager
from gi.repository import Gtk

with tempfile.TemporaryDirectory(prefix="decklite-ui-test-") as directory:
    root = Path(directory)
    manager.LOCALE_FILE = root / "wine-locale"
    manager.TIMEZONE_FILE = root / "wine-timezone"
    manager.DISPLAY_MODE_FILE = root / "wine-display-mode"
    manager.DEFAULT_PREFIX = root / "default-prefix"
    manager.PREFIX_ROOT = root / "prefixes"
    language_file = root / "wine-manager-language"
    manager.load_language = lambda: ui_i18n.load_language(language_file)
    manager.save_language = lambda value: ui_i18n.save_language(value, language_file)
    fresh = manager.WineManager()
    assert fresh.locale_combo.get_active_id() == "en_US.UTF-8"
    assert fresh.timezone_combo.get_active_id() == "0"
    assert fresh.environment()["TZ"] == "UTC0"
    assert not manager.LOCALE_FILE.exists() and not manager.TIMEZONE_FILE.exists()
    fresh.hide()
    manager.LOCALE_FILE.write_text("ja_JP.UTF-8\n")
    manager.TIMEZONE_FILE.write_text("345\n")
    manager.DISPLAY_MODE_FILE.write_text("native\n")
    window = manager.WineManager()
    assert window.ui_language == "en"
    window.backend_combo.set_active_id("box64")
    before_environment = window.environment()
    before_host = dict(os.environ)
    writes = {path: (path.read_bytes(), path.stat().st_mtime_ns)
              for path in (manager.LOCALE_FILE, manager.DISPLAY_MODE_FILE, manager.TIMEZONE_FILE)}
    sentinel = object()
    window.processes.append(sentinel)
    for language in ui_i18n.LANGUAGES:
        with patch.object(manager.subprocess, "Popen", side_effect=AssertionError("Unexpected launch")), \
                patch.object(manager.subprocess, "run", side_effect=AssertionError("Unexpected command")):
            window.ui_language_combo.set_active_id(language)
        assert window.get_title() == ui_i18n.translate(language, "DeckLite Wine Manager")
        assert window.ui_language == language
        assert window.environment() == before_environment, language
        assert window.processes == [sentinel]
        assert window.backend_combo.get_active_id() == "box64"
        assert window.display_combo.get_active_id() == "native"
        assert window.locale_combo.get_active_id() == "ja_JP.UTF-8"
        assert window.timezone_combo.get_active_id() == "345"
        assert window.environment()["TZ"] == "UTC-5:45"
        for path, original in writes.items():
            assert (path.read_bytes(), path.stat().st_mtime_ns) == original, (language, path)
        if language != "en":
            assert ui_i18n.load_language(language_file) == language
        print("PASS: UI switch preserves environment, selections and running-process list:", language)
    assert dict(os.environ) == before_host
    # Reverse direction: changing Windows language cannot alter UI preference.
    for locale, language_chain in manager.LOCALE_LANGUAGES.items():
        window.locale_combo.set_active_id(locale)
        environment = window.environment()
        assert environment["LANG"] == environment["LC_ALL"] == locale
        assert environment["LANGUAGE"] == language_chain
        assert ui_i18n.load_language(language_file) == window.ui_language == "ru"
        assert environment["TZ"] == "UTC-5:45"
    print("PASS: all 5 Windows locales stay independent of the interface")
    for offset in manager.TIMEZONES:
        window.timezone_combo.set_active_id(offset)
        assert window.environment()["TZ"] == manager.timezone_env(offset)
        assert window.locale_combo.get_active_id() == "en_US.UTF-8"
        assert ui_i18n.load_language(language_file) == window.ui_language == "ru"
        assert manager.load_timezone(manager.TIMEZONE_FILE) == offset
    assert dict(os.environ) == before_host
    print("PASS: all UTC offsets stay independent of Windows/UI language and host environment")
    second = manager.WineManager()
    assert second.ui_language == "ru", "Interface preference must survive reopening"
    assert second.timezone_combo.get_active_id() == "840"
    second.connect("destroy", lambda *_: None)
    # Do not call Gtk.main_quit without a running loop through destroy signals.
    second.hide()
    window.hide()
    print("PASS: reopened GTK manager restores saved UI language")
