# Third-party provenance

Tiny Container baseline: `Cateners/tiny_container`, commit
`5f15dd1986b2a0569791f42e3838a823049206d1`, GPL-3.0 (see root COPYING).

## Termux:X11 library snapshot

Source: https://github.com/tiny-computer/termux-x11

Baseline: `21159a1405570aa55e1541ab3bb93578fa7af34b`.
Its GPL license is retained in `termux-x11/LICENSE`. This snapshot includes the
reviewed DeckLite Java viewport/input changes and the unchanged upstream ARM64
libXlorie.so. The original sample test signing key is excluded and its unused
configuration removed. No private signing identity is included.

The native submodule sources are not flattened here. Their original URLs are
retained in the nested `.gitmodules`; clone the upstream repository at the pinned
commit and initialize its submodules to inspect/rebuild the upstream native
renderer. The Android library build here uses the existing prebuilt renderer,
as did the device-tested app.

## Android JNI inputs

The contents of `app/src/main/jniLibs/arm64-v8a` are the upstream Tiny Container
JNI bundle used by the tested app, from the cached v4.2.2 `jniLibs.zip` asset.
Archive SHA-256: `b171034338365b4530698bae48f7ac3a7478b3c11b9e803d81a5bd2d3aec0fd8`.
These are Android-native loaders, PRoot, archive tools and renderer dependencies,
not Windows game files. Upstream documents its build sources at
https://github.com/tiny-computer/termux-packages and
https://github.com/tiny-computer/proot-termux.

## Container overlay

DeckLite scripts have their separate license at `decklite/LICENSE`; included
third-party components retain their own licenses, not the DeckLite MIT license.
tgcompat and steamclienttermux source/license provenance are included below
`decklite/steam-overlay/usr/share/doc/decklite-steam-arm64/`.
Custom MIDI/affinity/game-launch sources are in `decklite/tools/native/`.
The automatic display entry point is `wine-display-launch.c`, which includes the
legacy `wine-game-launch.c`. The provided LLVM build script reproduced the overlay
PE helper byte-for-byte: SHA-256
`215c3fa2cf38915ea9c471abee8b54c6ac4b3ee5abc36f58d493ab1d83f1c988`.
The locale archive is generated Debian locale data, not personal configuration.

The full Steam/Proton/Wine rootfs, SDK, downloaded package cache, live Steam data
and game/runtime installers are not stored in this source repository. Binary
distribution is a separate process; retain applicable third-party notices and
do not assume this project's license grants rights to every downloaded component.
