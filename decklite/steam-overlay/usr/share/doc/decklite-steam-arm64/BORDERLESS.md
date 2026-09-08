# Legacy forced-borderless fallback

Normal EXE launches now default to Automatic, which follows the game's own
Fullscreen/Windowed mode. See AUTO-DISPLAY.md. This page describes only the older
explicit fallback; no special shortcut is needed for Automatic.

In Wine Manager, choose **Game display → Borderless fullscreen**, then run an EXE.
Set the game's own display mode to **Windowed** first. The alternative command is:

```sh
run-exe-fullscreen /path/to/game.exe
```

This command does not change the global Wine Manager display preference. Safe
virtual desktop remains a rollback option. Native mode is unchanged.

The game is enlarged to fit the X11 display, with its aspect ratio preserved.
Black side bars on a widescreen display are normal for a 4:3 game. The virtual
desktop stays behind the scenes, protecting Android/X11 from old exclusive
display-mode switches. No video capture/upscaling loop or overlay input window
is used. The application still controls its internal render resolution.

A one-shot X11 startup check clears stale pixels in the black letterboxing
after the game has reached its fitted size. It targets only this launch's
uniquely named Wine desktop, does not touch game input or resize windows, and
exits after painting once (or after a bounded startup timeout).

The helper handles a limited startup stale-window retry and never continuously
resizes or steals focus. An exclusive-mode game that shrinks the virtual monitor
is left in safe mode: switch that game to Windowed before using borderless mode.
Compatibility is application-dependent; TH08 v1.00d was tested on SM-X810.

Wine's desktop background defaults to black once per prefix (including existing
prefixes). Later user colour changes are preserved. No EXE, save or game asset is
included or modified by this feature. Existing DXVK, GPU and CPU preferences
remain in effect.

Startup diagnostics: `%TEMP%\decklite-borderless-<Wine PID>.log` in the prefix.
These contain sizing status, not game arguments or account details. Test backups
and device logs are not part of the distributable.
