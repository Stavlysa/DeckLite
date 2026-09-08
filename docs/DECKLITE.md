# DeckLite

An ARM64 Android fork of Tiny Container with a Debian 13 (Trixie) XFCE desktop.
Native Linux ARM64 Steam handles its own interface; standalone Windows programs
use Hangover 11.16, and Steam Windows games use the included GE-Proton11-6-aarch64.

## Included changes

- English, Traditional Chinese, Simplified Chinese, Japanese and Russian app/UI
  language selection. Wine Windows language is independent and defaults to English;
  Wine timezone defaults to UTC+00:00.
- General Wine display/focus helpers, CPU selection including big/prime cores,
  software MIDI fallback, and offline runtime templates in the container image.
- Compact Wine Manager, prominent Run EXE / MSI action, and reachable small-screen
  controls and file-chooser buttons. Details/logs can be expanded as needed.
- Default dark desktop; a PRoot-aware resource monitor. Unavailable GPU counters
  remain unavailable, rather than being presented as a reliable 0% measurement.
- Native Steam launch/update helpers, tray/window controls and a CEF compositor
  workaround for the observed Library flicker. Game GL/Vulkan rendering is separate.
- General X11 touchpad/pointer, viewport/render scheduling and Android audio fixes.
- Optional Debugging defaults OFF, with key-paired localhost USB SSH. No private
  key, signing key, user account, device log, saved game or home backup is included.
- Built-in rootfs streaming supports seven <=512 MiB chunks, SHA-256 validation,
  first-launch language selection, and a 22 GiB free-space check before importing.
  An APK upgrade deliberately does not overwrite an existing imported container.

These are compatibility improvements, not a promise that every Windows game works.
The occasional Touhou menu/dialogue transition FPS dip remains deferred. No new
claim of stable CS 1.6 gameplay at 100 FPS or 45+ FPS with nine bots is made here.

## Build the Android app

Use JDK 21 and Android SDK platform/build tools 37 with the repository Gradle wrapper.
The Android native build also needs CMake and a compatible NDK. Configure your own
SDK path in an ignored `local.properties`, or set `ANDROID_HOME`.

The reviewed ARM64 JNI inputs are included, as is the modified Termux:X11 Java
library under `third_party/termux-x11`. No sibling checkout is required.

```sh
bash gradlew :app:assembleRelease :app:testDebugUnitTest :app:lintVitalRelease
```

On Windows use `gradlew.bat` instead. The release build is **not debuggable**, but
currently uses your local Android debug signing configuration for development.
No maintainer signing key is shipped. Independently built APKs will not necessarily
have the signing identity required to overwrite an existing installed APK.

## Include a clean container

See [container build instructions](../decklite/README.md). Do not export your live
home directory or Steam account into a public image. A built-in APK can be assembled
from a small release APK and a separately validated rootfs using Python 3.14:

```sh
python decklite/tools/bundle_container_apk.py embed \
  --base app/build/outputs/apk/release/app-release.apk \
  --rootfs /path/to/clean-rootfs.tar.zst --output /path/to/unsigned.apk \
  --sha256 ROOTFS_SHA256
```

Then run SDK `zipalign -P 16 4`, sign with **your own** key using `apksigner`, and
run `bundle_container_apk.py verify SIGNED.apk --sha256 ROOTFS_SHA256`.
Never distribute the unsigned intermediate. A built-in image adds about 3.5 GB to
installed-app storage in addition to the expanded container.

## Tested scope

The 4.4.1/4.3.4 packaging baseline passed 19 Android JVM tests, five packaging tests,
signature/CRC/rootfs-hash checks, and a full old/new payload comparison. The compact
GTK interface was tested at a 1168x507 X11 workarea in all five UI languages.
The standalone source export passed release APK assembly, all 19 Android JVM tests
and release vital lint on 2026-09-09. Container tooling passed 21 host tests; one
Linux-guest-only shell test was skipped on Windows. The desktop tests require a
working Bash (Git Bash on Windows, not an unconfigured WSL app alias).

The ARM64 display helper rebuilt byte-for-byte identically to the reviewed overlay
binary. All 21 Android JNI inputs match the pinned upstream bundle. This export
reorganizes the X11 project path and removes its unused public sample signing-key
configuration. No new phone installation, Steam login, gameplay or audio benchmark
is implied by these source-export checks.
