#!/usr/bin/env python3
"""Rebuild one complete, content-addressed Valve Linux ARM64 Steam client.

Valve's VZip framing is decoded as documented by SteamKit2's MIT-licensed
VZipUtil implementation: https://github.com/SteamRE/SteamKit
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import io
import json
import lzma
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import struct
import tempfile
import urllib.request
import zipfile
import zlib


USER_AGENT = "DeckLite-Steam-ARM64/1.0"
SYMLINK_MANIFEST = ".decklite-steam-symlinks.json"
PACKAGE_PATTERN = re.compile(r"\.([0-9a-f]{40})(?:_(\d+))?$")


def write_bootstrap_metadata(
    lock: dict[str, object],
    output: Path,
    package_metadata: list[tuple[str, dict[str, str]]],
) -> None:
    """Write a complete updater manifest for the reconstructed pinned build."""
    platform = str(lock.get("platform", ""))
    version = str(lock.get("version", ""))
    if not re.fullmatch(r"[a-z0-9]+", platform) or not version.isdecimal():
        raise ValueError("Lock file has an invalid platform or version")
    if not package_metadata:
        raise ValueError("Cannot write a Steam manifest without package metadata")
    package_dir = output / "package"
    package_dir.mkdir(parents=True, exist_ok=True)
    lines = [f'"{platform}"', "{", f'\t"version"\t\t"{version}"']
    for package_name, fields in package_metadata:
        lines.extend((f'\t"{package_name}"', "\t{"))
        for key in ("file", "size", "sha2", "zipvz", "sha2vz"):
            value = fields.get(key)
            if value is not None:
                lines.append(f'\t\t"{key}"\t\t"{value}"')
        if package_name == f"steam_{platform}":
            lines.append('\t\t"IsBootstrapperPackage"\t\t"1"')
        lines.append("\t}")
    lines.extend(("}", ""))
    (package_dir / f"steam_client_{platform}.manifest").write_text(
        "\n".join(lines), encoding="ascii"
    )
    (package_dir / f"steam_client_{platform}.installed").write_text("", encoding="ascii")


def package_manifest_fields(
    package_name: str, compressed: Path, archive: Path
) -> tuple[str, dict[str, str]]:
    logical_name = package_name.split(".zip", 1)[0]
    fields = {
        "file": f"{logical_name}.zip.{hash_file(archive, 'sha1')}",
        "size": str(archive.stat().st_size),
        "sha2": hash_file(archive, "sha256"),
    }
    if archive != compressed:
        fields["zipvz"] = package_name
        fields["sha2vz"] = hash_file(compressed, "sha256")
    return logical_name, fields


def reconstruct_package_metadata(
    packages: list[str], cache: Path
) -> list[tuple[str, dict[str, str]]]:
    """Recover full manifest fields from the verified content-addressed cache."""
    metadata: list[tuple[str, dict[str, str]]] = []
    with tempfile.TemporaryDirectory(prefix="decklite-vzip-manifest-") as temporary:
        temporary_root = Path(temporary)
        for index, name in enumerate(packages, start=1):
            package = cache / name
            expected_sha1, expected_size = package_identity(name)
            if not valid_package(package, expected_sha1, expected_size):
                raise RuntimeError(f"Pinned Steam package is missing or invalid: {package}")
            archive = package
            if ".zip.vz." in name:
                archive = temporary_root / f"{index:02d}.zip"
                print(
                    f"Decoding VZip metadata {index}/{len(packages)}: {name}",
                    flush=True,
                )
                decompress_vzip(package, archive)
            metadata.append(package_manifest_fields(name, package, archive))
            if archive != package:
                archive.unlink(missing_ok=True)
    return metadata


def hash_file(path: Path, algorithm: str) -> str:
    digest = hashlib.new(algorithm)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def package_identity(name: str) -> tuple[str, int | None]:
    match = PACKAGE_PATTERN.search(name)
    if not match:
        raise ValueError(f"Package name is not content-addressed: {name}")
    size = int(match.group(2)) if match.group(2) else None
    return match.group(1), size


def valid_package(path: Path, expected_sha1: str, expected_size: int | None) -> bool:
    return (
        path.is_file()
        and (expected_size is None or path.stat().st_size == expected_size)
        and hash_file(path, "sha1") == expected_sha1
    )


def download_package(name: str, cdn_base: str, cache: Path) -> Path:
    expected_sha1, expected_size = package_identity(name)
    destination = cache / name
    if valid_package(destination, expected_sha1, expected_size):
        print(f"Cached: {name}", flush=True)
        return destination

    partial = destination.with_name(destination.name + ".partial")
    partial.unlink(missing_ok=True)
    request = urllib.request.Request(cdn_base + name, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=240) as response, partial.open("wb") as output:
        shutil.copyfileobj(response, output, length=1024 * 1024)
    if not valid_package(partial, expected_sha1, expected_size):
        actual = hash_file(partial, "sha1")
        size = partial.stat().st_size
        partial.unlink(missing_ok=True)
        raise RuntimeError(
            f"Valve package verification failed for {name}: sha1={actual}, size={size}"
        )
    partial.replace(destination)
    print(f"Downloaded: {name}", flush=True)
    return destination


def safe_member_path(name: str) -> PurePosixPath:
    path = PurePosixPath(name.replace("\\", "/"))
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"Unsafe path in Steam archive: {name!r}")
    return path


def safe_symlink_target(member: PurePosixPath, target: str) -> str:
    normalized = target.replace("\\", "/")
    path = PurePosixPath(normalized)
    if not normalized or path.is_absolute():
        raise ValueError(f"Unsafe symlink target: {member} -> {target!r}")
    resolved = list(member.parent.parts)
    for part in path.parts:
        if part in {"", "."}:
            continue
        if part == "..":
            if not resolved:
                raise ValueError(f"Symlink escapes Steam root: {member} -> {target}")
            resolved.pop()
        else:
            resolved.append(part)
    return normalized


def remove_existing(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)


def should_be_executable(path: Path, external_mode: int) -> bool:
    if external_mode & 0o111 or path.suffix in {".sh", ".py"}:
        return True
    try:
        with path.open("rb") as handle:
            header = handle.read(4)
        return header.startswith(b"#!") or header == b"\x7fELF"
    except OSError:
        return False


def extract_zip(archive_path: Path, output: Path, symlinks: dict[str, str]) -> None:
    with zipfile.ZipFile(archive_path) as archive:
        for member in archive.infolist():
            relative = safe_member_path(member.filename)
            if not relative.parts:
                continue
            destination = output.joinpath(*relative.parts)
            mode = (member.external_attr >> 16) & 0o7777
            file_type = (member.external_attr >> 16) & 0o170000
            if member.is_dir():
                if destination.is_symlink():
                    destination.unlink()
                destination.mkdir(parents=True, exist_ok=True)
                symlinks.pop(relative.as_posix(), None)
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            if file_type == stat.S_IFLNK:
                target = safe_symlink_target(relative, archive.read(member).decode("utf-8"))
                remove_existing(destination)
                symlinks[relative.as_posix()] = target
                if os.name == "nt":
                    destination.write_text(target, encoding="utf-8")
                else:
                    destination.symlink_to(target)
                continue
            if destination.is_symlink():
                destination.unlink()
            symlinks.pop(relative.as_posix(), None)
            with archive.open(member) as source, destination.open("wb") as target:
                shutil.copyfileobj(source, target, length=1024 * 1024)
            os.chmod(destination, 0o755 if should_be_executable(destination, mode) else 0o644)


def decompress_vzip(source: Path, destination: Path) -> None:
    total = source.stat().st_size
    if total < 22:
        raise ValueError(f"Truncated VZip: {source}")
    with source.open("rb") as handle:
        header = handle.read(12)
        if header[:3] != b"VZa":
            raise ValueError(f"Unsupported VZip header in {source.name}")
        property_bits = header[7]
        dictionary_size = max(4096, struct.unpack_from("<I", header, 8)[0])
        handle.seek(-10, io.SEEK_END)
        expected_crc, expected_size, footer = struct.unpack("<II2s", handle.read(10))
        if footer != b"zv":
            raise ValueError(f"Invalid VZip footer in {source.name}")

        lc = property_bits % 9
        remainder = property_bits // 9
        lp = remainder % 5
        pb = remainder // 5
        decoder = lzma.LZMADecompressor(
            format=lzma.FORMAT_RAW,
            filters=[
                {
                    "id": lzma.FILTER_LZMA1,
                    "dict_size": dictionary_size,
                    "lc": lc,
                    "lp": lp,
                    "pb": pb,
                }
            ],
        )
        handle.seek(12)
        remaining = total - 22
        actual_crc = 0
        actual_size = 0
        with destination.open("wb") as output:
            while remaining:
                chunk = handle.read(min(1024 * 1024, remaining))
                if not chunk:
                    raise ValueError(f"Truncated VZip data in {source.name}")
                remaining -= len(chunk)
                decoded = decoder.decompress(chunk)
                if decoded:
                    output.write(decoded)
                    actual_crc = zlib.crc32(decoded, actual_crc)
                    actual_size += len(decoded)
        if not decoder.eof or actual_size != expected_size:
            raise ValueError(
                f"VZip size mismatch for {source.name}: {actual_size} != {expected_size}"
            )
        if actual_crc & 0xFFFFFFFF != expected_crc:
            raise ValueError(f"VZip CRC mismatch for {source.name}")


def install(lock_path: Path, output: Path, cache: Path, jobs: int) -> None:
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    packages = lock.get("packages")
    if not isinstance(packages, list) or not all(isinstance(item, str) for item in packages):
        raise ValueError("Lock file has no package list")
    expected_client_sha256 = str(lock.get("client_binary_sha256", ""))
    existing_client = output / "steamrtarm64/steam"
    existing_version = output / ".decklite-steam-version"
    if output.exists() and any(output.iterdir()):
        if (
            existing_client.is_file()
            and existing_version.is_file()
            and existing_version.read_text(encoding="ascii").strip() == str(lock["version"])
            and hash_file(existing_client, "sha256") == expected_client_sha256
        ):
            package_metadata = reconstruct_package_metadata(packages, cache)
            write_bootstrap_metadata(lock, output, package_metadata)
            print(f"Pinned Steam ARM64 {lock['version']} is already ready: {output}")
            return
        raise RuntimeError(f"Refusing to merge a pinned client into non-empty output: {output}")
    cdn_base = str(lock.get("cdn_base", ""))
    if not cdn_base.startswith("https://") or not cdn_base.endswith("/"):
        raise ValueError("Lock file has an invalid HTTPS CDN base")

    cache.mkdir(parents=True, exist_ok=True)
    downloaded: dict[str, Path] = {}
    print(f"Downloading {len(packages)} content-addressed Valve packages...", flush=True)
    with ThreadPoolExecutor(max_workers=max(1, min(jobs, 8))) as executor:
        futures = {
            executor.submit(download_package, name, cdn_base, cache): name for name in packages
        }
        for future in as_completed(futures):
            name = futures[future]
            downloaded[name] = future.result()

    output.mkdir(parents=True, exist_ok=True)
    symlinks: dict[str, str] = {}
    sha256_inventory: dict[str, str] = {}
    package_metadata: list[tuple[str, dict[str, str]]] = []
    with tempfile.TemporaryDirectory(prefix="decklite-vzip-") as temporary:
        temporary_root = Path(temporary)
        for index, name in enumerate(packages, start=1):
            package = downloaded[name]
            sha256_inventory[name] = hash_file(package, "sha256")
            archive = package
            if ".zip.vz." in name:
                archive = temporary_root / f"{index:02d}.zip"
                print(f"Decoding VZip {index}/{len(packages)}: {name}", flush=True)
                decompress_vzip(package, archive)
            else:
                print(f"Extracting ZIP {index}/{len(packages)}: {name}", flush=True)
            package_metadata.append(package_manifest_fields(name, package, archive))
            extract_zip(archive, output, symlinks)
            if archive != package:
                archive.unlink(missing_ok=True)

    (output / SYMLINK_MANIFEST).write_text(
        json.dumps(symlinks, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output / ".decklite-steam-version").write_text(
        str(lock["version"]) + "\n", encoding="ascii"
    )
    (output / ".steam-enable-steamrt64-client").touch()
    package_dir = output / "package"
    package_dir.mkdir(parents=True, exist_ok=True)
    write_bootstrap_metadata(lock, output, package_metadata)
    (package_dir / "decklite-pinned-build").write_text(
        str(lock["version"]) + "\n", encoding="ascii"
    )
    (package_dir / "decklite-package-sha256.json").write_text(
        json.dumps(sha256_inventory, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    client_sha256 = hash_file(output / "steamrtarm64/steam", "sha256")
    if client_sha256 != expected_client_sha256:
        raise RuntimeError(
            f"Pinned Steam client binary mismatch: {client_sha256} != {expected_client_sha256}"
        )
    print(
        f"Pinned Steam ARM64 {lock['version']} ready: {output} ({len(symlinks)} symlinks)",
        flush=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    project_root = Path(__file__).resolve().parent.parent
    parser.add_argument(
        "--lock",
        type=Path,
        default=project_root / "steam-arm64-1785799196-packages.json",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--package-cache", type=Path, required=True)
    parser.add_argument("--jobs", type=int, default=4)
    args = parser.parse_args()
    install(args.lock.resolve(), args.output.resolve(), args.package_cache.resolve(), args.jobs)


if __name__ == "__main__":
    main()
