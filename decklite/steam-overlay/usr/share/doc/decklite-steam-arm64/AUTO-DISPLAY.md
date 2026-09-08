# Automatic Wine display

Use the matching DeckLite Tiny Container 4.2.9 APK with this image. Double-click
an EXE normally, or use Wine Manager's Run EXE button. No per-game shortcut is
required. Default Game display is Automatic; saved explicit choices are kept.

- Fullscreen in the game: the safe Wine virtual monitor changes resolution;
  X11's physical display does not. The APK presents that foreground game region
  at full display height/width with aspect-preserving black bars. The game keeps
  its own render resolution. This is GPU presentation scaling, not CPU capture.
- Windowed in the game: a normal framed Wine window. Its unused virtual desktop
  background is hidden using X Shape. Move it by the title bar. Resizing remains
  subject to the application's own support. The virtual desktop still exists
  internally to isolate exclusive mode changes.
- The observer handles windows on its private launch desktop, including children
  of bootstrapper EXEs. It does not recognize game names or patch game files.
- A one-time settled frame repaint repairs missing non-client controls after a
  display transition. There is no continuous forced resizing or focus stealing.

The same existing X11 GPU viewport produces the display and input coordinate
matrix. Android-side black bars are in the same Activity, not extra Wine/X11
windows. A private, bounded, expiring bridge returns to normal view if updates
stop. With an old/disconnected APK bridge the ordinary safe desktop is retained.

Fallback: Wine Manager > Game display > Safe virtual desktop. Native and the
older opt-in forced-borderless mode remain for explicit compatibility testing.
The old forced-borderless choice requires the game set to Windowed; Automatic
does not. Do not use run-exe-fullscreen as the normal launch method.

Scope: the shared Hangover run-exe path and normal Wine file associations. This
does not automatically hook native Linux games or Steam's separate Proton
launcher. No game assets or user sign-in data are included in this feature.
