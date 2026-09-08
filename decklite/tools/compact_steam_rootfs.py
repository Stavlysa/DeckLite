#!/usr/bin/env python3
"""Create the compact offline gaming image without removing runtime content.

The release image intentionally keeps Steam, Wine, Hangover, Proton, both Wine
prefix templates, fonts, codecs and package metadata.  Only development-only
headers/toolchain data, generated package caches, non-license documentation and
translations outside DeckLite's five supported languages are omitted. Firefox
ESR and unrelated office/GIS/print/scan/ML developer stacks are also omitted
from this gaming image and can be restored with APT.

XZ is used for the single-APK build because its denser compression and bounded
dictionary are a better fit for GitHub's 2 GiB release-asset limit.  Tiny
Computer's bundled bsdtar already links liblzma and detects compression by magic,
so the container import path remains streaming and format-safe.
"""

from __future__ import annotations

import argparse
import copy
from collections import Counter
from pathlib import Path, PurePosixPath
import subprocess
import tarfile


SUPPORTED_LOCALES = ("en", "zh", "ja", "ru")


def normalize(name: str) -> str:
    path = PurePosixPath(name)
    while path.parts and path.parts[0] in (".", "/"):
        path = PurePosixPath(*path.parts[1:])
    return path.as_posix()


def exclusion_reason(name: str) -> str | None:
    path = normalize(name)
    if path == ".":
        return None

    development_prefixes = (
        "usr/include",
        "usr/lib/gcc",
        "usr/libexec/gcc",
    )
    if any(path == prefix or path.startswith(prefix + "/") for prefix in development_prefixes):
        return "development toolchain"
    if path == "usr/bin/aarch64-linux-gnu-lto-dump-14":
        return "development toolchain"

    development_data_prefixes = (
        "usr/lib/cmake",
        "usr/lib/pkgconfig",
        "usr/lib/aarch64-linux-gnu/cmake",
        "usr/lib/aarch64-linux-gnu/pkgconfig",
        "usr/share/aclocal",
        "usr/share/cmake",
        "usr/share/pkgconfig",
    )
    if any(path == prefix or path.startswith(prefix + "/") for prefix in development_data_prefixes):
        return "development toolchain"
    if path.startswith("usr/lib/") and path.endswith((".a", ".o", ".la", ".prl")):
        return "development toolchain"

    if path.startswith("usr/bin/"):
        executable = PurePosixPath(path).name
        unprefixed = executable.removeprefix("aarch64-linux-gnu-")
        build_tools = {
            "ar", "as", "c++", "cc", "cmake", "cpp", "g++", "gcc", "ld",
            "make", "nm", "objcopy", "objdump", "ranlib", "readelf", "strip",
        }
        if unprefixed in build_tools or unprefixed.startswith(
            ("cpp-", "g++-", "gcc-", "ld.")
        ):
            return "development toolchain"

    firefox_prefixes = (
        "etc/firefox-esr",
        "usr/lib/firefox-esr",
        "usr/share/firefox-esr",
    )
    if any(path == prefix or path.startswith(prefix + "/") for prefix in firefox_prefixes):
        return "optional Firefox browser"
    if path in {
        "usr/bin/firefox",
        "usr/bin/firefox-esr",
        "usr/share/applications/firefox-esr.desktop",
    }:
        return "optional Firefox browser"
    if path.startswith("usr/share/icons/") and "firefox" in PurePosixPath(path).name.lower():
        return "optional Firefox browser"

    optional_desktop_prefixes = (
        "etc/cups",
        "etc/sane.d",
        "opt/tiny/edraw",
        "opt/tiny/wps",
        "usr/lib/aarch64-linux-gnu/qt5",
        "usr/lib/aarch64-linux-gnu/sane",
        "usr/lib/cups",
        "usr/libexec/cups",
        "usr/share/cups",
        "usr/share/gdal",
        "usr/share/gdcm-3.0",
        "usr/share/hdf5",
        "usr/share/poppler",
        "usr/share/proj",
        "usr/share/qt5",
        "usr/share/sane",
        "usr/share/tesseract-ocr",
    )
    if any(path == prefix or path.startswith(prefix + "/") for prefix in optional_desktop_prefixes):
        return "optional non-gaming desktop stack"
    if path in {
        "usr/bin/sane-find-scanner",
        "usr/bin/scanimage",
        "usr/sbin/ipp-usb",
    }:
        return "optional non-gaming desktop stack"
    if path.startswith("usr/lib/aarch64-linux-gnu/"):
        library = PurePosixPath(path).name
        optional_library_prefixes = (
            "libQt5",
            "libasan",
            "libblas",
            "libcfitsio",
            "libcups",
            "libdnnl",
            "libffado",
            "libfftw",
            "libflite",
            "libfortran",
            "libgdal",
            "libgdcm",
            "libgeos",
            "libgfortran",
            "libgphoto",
            "libhdf5",
            "libhwasan",
            "liblapack",
            "liblept",
            "liblsan",
            "libnetcdf",
            "libnetsnmp",
            "libonnxruntime",
            "libonnx",
            "libopencv",
            "libopenblas",
            "libpoppler",
            "libproj",
            "libprotobuf",
            "libsnmp",
            "libspatialite",
            "libtesseract",
            "libtsan",
            "libubsan",
            "libXNNPACK",
        )
        if library.startswith(optional_library_prefixes):
            return "optional non-gaming desktop stack"

    proot_unused_prefixes = (
        "etc/udev",
        "usr/lib/aarch64-linux-gnu/gtk-4.0",
        "usr/lib/udev",
        "usr/share/gtk-4.0",
        "usr/share/desktop-base",
        "usr/share/i18n",
        "usr/share/plymouth",
        "usr/share/udev",
    )
    if any(path == prefix or path.startswith(prefix + "/") for prefix in proot_unused_prefixes):
        return "unused PRoot desktop data"
    if path.startswith("usr/bin/gtk4-"):
        return "unused PRoot desktop data"
    if path.startswith("usr/lib/aarch64-linux-gnu/"):
        library = PurePosixPath(path).name
        if library.startswith(("libgtk-4", "libgtkmm-4")):
            return "unused PRoot desktop data"
    if path.endswith(".pyc") or "/__pycache__/" in path:
        return "regenerable Python bytecode"

    cache_prefixes = (
        "var/cache/apt/archives",
        "var/cache/swcatalog",
    )
    if any(path == prefix or path.startswith(prefix + "/") for prefix in cache_prefixes):
        return "generated package cache"

    documentation_prefixes = (
        "usr/share/man",
        "usr/share/info",
        "usr/share/lintian",
        "usr/share/groff",
        "usr/share/gtk-doc",
    )
    if any(path == prefix or path.startswith(prefix + "/") for prefix in documentation_prefixes):
        return "non-runtime documentation"

    if path == "usr/share/doc/decklite-steam-arm64" or path.startswith(
        "usr/share/doc/decklite-steam-arm64/"
    ):
        return None
    if path == "usr/share/doc" or path.startswith("usr/share/doc/"):
        # Keep Debian copyright/license notices in the distributable image.
        if path.endswith("/copyright"):
            return None
        return "non-license package documentation"

    locale_root = "usr/share/locale"
    if path.startswith(locale_root + "/"):
        relative = path[len(locale_root) + 1 :]
        language = relative.split("/", 1)[0]
        if language != "locale.alias" and not language.startswith(SUPPORTED_LOCALES):
            return "unsupported translation"

    return None


def compact(source: Path, output: Path, seven_zip: Path) -> None:
    source = source.resolve(strict=True)
    seven_zip = seven_zip.resolve(strict=True)
    output = output.resolve()
    if output.exists():
        raise FileExistsError(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    partial = output.with_name(output.name + ".partial")
    partial.unlink(missing_ok=True)

    command = [
        str(seven_zip),
        "a",
        "-txz",
        "-mx=9",
        "-md=256m",
        "-mmt=4",
        str(partial),
        "-si",
    ]
    compressor = subprocess.Popen(command, stdin=subprocess.PIPE)
    if compressor.stdin is None:
        raise RuntimeError("Could not open compressor input")

    kept_entries = 0
    kept_bytes = 0
    removed_entries: Counter[str] = Counter()
    removed_bytes: Counter[str] = Counter()
    try:
        with tarfile.open(source, mode="r|zst") as archive, tarfile.open(
            fileobj=compressor.stdin, mode="w|"
        ) as target:
            for member in archive:
                path = normalize(member.name)
                reason = exclusion_reason(path)
                if reason is not None:
                    removed_entries[reason] += 1
                    removed_bytes[reason] += member.size
                    continue
                if member.islnk() and exclusion_reason(member.linkname) is not None:
                    raise RuntimeError(
                        f"Kept hard link {path!r} targets excluded {member.linkname!r}"
                    )
                cloned = copy.copy(member)
                cloned.name = path
                cloned.pax_headers = {
                    key: value
                    for key, value in cloned.pax_headers.items()
                    if key not in {"path", "linkpath"}
                }
                if cloned.islnk():
                    cloned.linkname = normalize(cloned.linkname)
                target.addfile(
                    cloned,
                    archive.extractfile(member) if member.isfile() else None,
                )
                kept_entries += 1
                kept_bytes += member.size
    except BaseException:
        compressor.kill()
        compressor.wait()
        partial.unlink(missing_ok=True)
        raise
    finally:
        compressor.stdin.close()

    status = compressor.wait()
    if status != 0:
        partial.unlink(missing_ok=True)
        raise RuntimeError(f"7-Zip XZ compressor failed with exit status {status}")
    partial.replace(output)

    print(f"Kept {kept_entries:,} entries ({kept_bytes:,} bytes)")
    for reason in sorted(removed_entries):
        print(
            f"Removed {removed_entries[reason]:,} {reason} entries "
            f"({removed_bytes[reason]:,} bytes)"
        )
    print(f"Created {output} ({output.stat().st_size:,} bytes)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--seven-zip", required=True, type=Path)
    arguments = parser.parse_args()
    compact(arguments.source, arguments.output, arguments.seven_zip)


if __name__ == "__main__":
    main()
