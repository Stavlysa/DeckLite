# DeckLite Debian 13 gaming container

ARM64 Debian 13 XFCE container for Tiny Container, with native ARM64 Steam,
Hangover 11.16, GE-Proton11-6-aarch64, Wine Manager and general compatibility fixes.
Current source baseline: container 4.3.4 / Android APK 4.4.1.

The clean binary image is separate from this source tree. It is about 3.5 GB
compressed and includes offline Wine runtime templates. Never substitute a live
device export containing accounts, saves or SSH keys for that clean build input.

## Build inputs

`build-steam.ps1` / `build-steam.sh` specify hashes and upstream URLs for the
official XFCE base, native Steam packages, Hangover, GE-Proton, Steam Runtime 4
and Winetricks. Python 3.14 provides streaming zstd tar support.

The preinstalled Wine prefix templates are a separately prepared input:
`cache/wine-prefix-templates.tar.zst`. They are **not** present in Git and are not
automatically downloadable from this source export. The scripts fail when the
required, hash-pinned template archive is unavailable. Prepare clean templates
with the runtime installers/`tools/archive_wine_templates.py`, or obtain the
separately distributed, verified build input. Do not silently skip the runtimes.
Creating a fresh template may require updating its recorded hash and testing it.

On Windows run `build-steam.ps1` from this directory; on Linux use
`bash build-steam.sh`. Paths default to this project's ignored `cache/` and
`build/` directories. For an already verified clean image, `tools/repack_steam_release.py`
can apply a reviewed minimal overlay without exporting a user's container.

Validate with `tools/verify_security_release.py` and `tools/verify_steam_rootfs.py`.
The former is a targeted source/privacy check, not a complete malware/CVE audit.
GTK tests under `tests/` run inside the X11 container, with isolated preferences.
Native custom helper sources are under `tools/native/`; MIDI has its own build
script, and the existing tgcompat provenance includes its ARM64 build command.

See [the app guide](../docs/DECKLITE.md) for building a signed APK with this image
embedded. GitHub's web file upload is for source files, not the multi-GB rootfs.
