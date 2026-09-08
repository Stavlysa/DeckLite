# Wine Manager interface language

Open Wine Manager and use **Interface language** to select English, 繁體中文,
简体中文, 日本語 or Русский. A fresh import always starts in English, regardless
of the Android, desktop or Windows language. Changes apply immediately and
survive closing/reopening the manager and restarting the container.

This choice controls Wine Manager's own buttons, labels, dialogs and new status
messages. Existing activity-log entries, technical identifiers, paths and output
from external programs remain unchanged. GTK's shared file-picker sidebar and
other desktop applications follow their own desktop settings.

**Windows language** is a separate setting for Wine programs. Changing the manager
interface does not change Windows language, Wine prefixes, graphics/display mode,
CPU policy or the environment of launched games. It does not restart running Wine
processes. A fresh import defaults to **English (en_US.UTF-8)** for Windows as
well. Existing valid saved Windows-language choices are preserved.

The UI preference is stored in
`$XDG_CONFIG_HOME/decklite/wine-manager-language`, or by default
`~/.config/decklite/wine-manager-language`. Missing or invalid values fall back to
English. The independent Windows preference remains
`$XDG_CONFIG_HOME/decklite/wine-locale` (normally
`~/.config/decklite/wine-locale`).

## Wine time zone

**Time zone (UTC)** is independently selectable and defaults to **UTC+00:00
(GMT / Greenwich)**. It offers fixed offsets from UTC-12:00 through UTC+14:00,
including common half/quarter-hour offsets. These are not city-based time zones:
they do **not** automatically switch to daylight saving time. In particular,
UTC+00:00 stays at Greenwich standard time even during British Summer Time.

The offset is saved as minutes east of Greenwich in
`$XDG_CONFIG_HOME/decklite/wine-timezone` (normally
`~/.config/decklite/wine-timezone`); `0` is the default. Missing/invalid values
fall back to zero. Windows language, manager language and time zone are three
separate preferences. No UTF encoding switch has been added.

After changing Windows language or time zone, close all Wine applications and
reopen them (or restart the container). Saving does not terminate games or alter
already-running applications. The shared environment helper is used by the
ordinary EXE association/launcher, MSI prefix runner, manager tools, runtime
installers and first-prefix initialization. No special game shortcut is needed.
Raw `/usr/bin/wine` commands bypass these launchers; advanced users can source
`/opt/tiny/wine-manager/wine-region-env.sh` in that command's subshell first.

Only Wine child environments receive the locale and `TZ` value. This does not
set the system clock or change Android, the X11 desktop, native Steam or Proton's
independent environment. An explicit `DECKLITE_WINE_UTC_OFFSET` (minutes) or
`DECKLITE_WINE_LOCALE` overrides the saved value for a launched process.

DeckLite's added Tiny Container quick-command labels are English, including
**Stop all Wine**. This does not force the rest of the Android app into English.
