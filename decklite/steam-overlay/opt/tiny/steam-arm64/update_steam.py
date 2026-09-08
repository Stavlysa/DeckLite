#!/usr/bin/env python3
"""Download and install Valve's native Linux ARM64 Steam payload."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import tempfile
import urllib.request
import zipfile


CDN_BASE = "https://steamcdn-a.akamaihd.net/client/"
MANIFEST_NAME = "steam_client_linuxarm64"
USER_AGENT = "DeckLite-Steam-ARM64/1.0"
SYMLINK_MANIFEST = ".decklite-steam-symlinks.json"


def parse_vdf(text: str) -> dict[str, object]:
    root: dict[str, object] = {}
    stack = [root]
    pending_key: str | None = None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("//"):
            continue
        if line == "{":
            if pending_key is None:
                raise ValueError("Unexpected opening brace in Steam manifest")
            child: dict[str, object] = {}
            stack[-1][pending_key] = child
            stack.append(child)
            pending_key = None
            continue
        if line == "}":
            if len(stack) == 1:
                raise ValueError("Unexpected closing brace in Steam manifest")
            stack.pop()
            pending_key = None
            continue
        values = re.findall(r'"((?:\\.|[^"\\])*)"', line)
        values = [bytes(value, "utf-8").decode("unicode_escape") for value in values]
        if len(values) == 1:
            pending_key = values[0]
        elif len(values) >= 2:
            stack[-1][values[0]] = values[1]
            pending_key = None
    if len(stack) != 1:
        raise ValueError("Unclosed section in Steam manifest")
    return root


def request_bytes(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=90) as response:
        return response.read()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_depot(file_name: str, expected_sha256: str, package_dir: Path) -> Path:
    destination = package_dir / file_name
    if destination.is_file() and sha256_file(destination) == expected_sha256:
        print(f"Cached: {file_name}")
        return destination

    partial = destination.with_name(destination.name + ".partial")
    partial.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(CDN_BASE + file_name, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=180) as response, partial.open("wb") as output:
        shutil.copyfileobj(response, output, length=1024 * 1024)
    actual = sha256_file(partial)
    if actual != expected_sha256:
        partial.unlink(missing_ok=True)
        raise RuntimeError(f"SHA256 mismatch for {file_name}: {actual}")
    partial.replace(destination)
    print(f"Downloaded: {file_name}")
    return destination


def safe_member_path(name: str) -> PurePosixPath:
    normalized = name.replace("\\", "/")
    path = PurePosixPath(normalized)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"Unsafe path in Steam archive: {name!r}")
    return path


def safe_symlink_target(member: PurePosixPath, target: str) -> str:
    normalized = target.replace("\\", "/")
    path = PurePosixPath(normalized)
    if not normalized or path.is_absolute():
        raise ValueError(f"Unsafe symlink target in Steam archive: {target!r}")
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


def restore_x86_runtime_before_update(output_dir: Path) -> None:
    """Restore Valve's original runtime tree before writing updated depots."""
    runtime = output_dir / "steamrt64"
    backup = output_dir / "steamrt64-x86-backup"
    if runtime.is_symlink():
        runtime.unlink()
    elif runtime.is_file():
        runtime.unlink()
    if backup.is_dir():
        if runtime.is_dir():
            shutil.rmtree(runtime)
        backup.rename(runtime)


def should_be_executable(path: Path, external_mode: int) -> bool:
    if external_mode & 0o111:
        return True
    if path.suffix in {".sh", ".py"}:
        return True
    try:
        with path.open("rb") as handle:
            header = handle.read(4)
        return header.startswith(b"#!") or header == b"\x7fELF"
    except OSError:
        return False


def extract_depot(
    archive_path: Path, output_dir: Path, symlinks: dict[str, str]
) -> None:
    with zipfile.ZipFile(archive_path) as archive:
        for member in archive.infolist():
            relative = safe_member_path(member.filename)
            if not relative.parts:
                continue
            destination = output_dir.joinpath(*relative.parts)
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
                target = safe_symlink_target(
                    relative, archive.read(member).decode("utf-8")
                )
                remove_existing(destination)
                symlinks[relative.as_posix()] = target
                if os.name == "nt":
                    # NTFS symlink creation normally needs elevation/developer mode.
                    # Keep a placeholder and let the tar builder restore the link.
                    destination.write_text(target, encoding="utf-8")
                else:
                    destination.symlink_to(target)
                continue
            if destination.is_symlink():
                destination.unlink()
            symlinks.pop(relative.as_posix(), None)
            with archive.open(member) as source, destination.open("wb") as output:
                shutil.copyfileobj(source, output, length=1024 * 1024)
            os.chmod(destination, 0o755 if should_be_executable(destination, mode) else 0o644)


def install(output_dir: Path, package_dir: Path, jobs: int) -> None:
    manifest_bytes = request_bytes(CDN_BASE + MANIFEST_NAME)
    manifest_text = manifest_bytes.decode("utf-8")
    parsed = parse_vdf(manifest_text)
    platform = parsed.get("linuxarm64")
    if not isinstance(platform, dict):
        raise RuntimeError("Valve manifest has no linuxarm64 section")

    depots: list[tuple[str, str, str]] = []
    for depot_name, raw_info in platform.items():
        if not isinstance(raw_info, dict):
            continue
        file_name = raw_info.get("file")
        checksum = raw_info.get("sha2")
        if isinstance(file_name, str) and isinstance(checksum, str):
            safe_member_path(file_name)
            depots.append((depot_name, file_name, checksum.lower()))
    if not depots:
        raise RuntimeError("Valve manifest contains no downloadable depots")

    package_dir.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {len(depots)} verified Valve Steam depots...")
    downloaded: dict[str, Path] = {}
    with ThreadPoolExecutor(max_workers=max(1, min(jobs, 8))) as executor:
        futures = {
            executor.submit(download_depot, file_name, checksum, package_dir): depot_name
            for depot_name, file_name, checksum in depots
        }
        for future in as_completed(futures):
            downloaded[futures[future]] = future.result()

    output_dir.mkdir(parents=True, exist_ok=True)
    restore_x86_runtime_before_update(output_dir)
    symlinks: dict[str, str] = {}
    for depot_name, _, _ in sorted(depots):
        print(f"Extracting: {depot_name}")
        extract_depot(downloaded[depot_name], output_dir, symlinks)

    (output_dir / SYMLINK_MANIFEST).write_text(
        json.dumps(symlinks, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"Recorded {len(symlinks)} Steam symlinks for portable rootfs creation.")

    steam_package_dir = output_dir / "package"
    steam_package_dir.mkdir(parents=True, exist_ok=True)
    (steam_package_dir / MANIFEST_NAME).write_bytes(manifest_bytes)
    # The ARM64 client is now published on Valve's stable channel.  Do not
    # silently opt every imported container into publicbeta: a beta regression
    # can otherwise leave the client indefinitely at "Loading user data".
    # Users can still create package/beta themselves when they explicitly want
    # to test Valve's beta builds.
    (steam_package_dir / "beta").unlink(missing_ok=True)
    (output_dir / ".steam-enable-steamrt64-client").touch()
    (output_dir / ".decklite-steam-version").write_text(
        str(platform.get("version", "unknown")) + "\n", encoding="ascii"
    )
    print(f"Steam ARM64 payload ready: {output_dir}")


def main() -> None:
    parser = argparse.ArgumentParser()
    default_home = Path.home()
    parser.add_argument(
        "--output",
        type=Path,
        default=default_home / ".local/share/Steam",
    )
    parser.add_argument(
        "--package-cache",
        type=Path,
        default=default_home / ".cache/decklite-steam-arm64/packages",
    )
    parser.add_argument("--jobs", type=int, default=4)
    args = parser.parse_args()
    install(args.output.resolve(), args.package_cache.resolve(), args.jobs)


if __name__ == "__main__":
    main()
