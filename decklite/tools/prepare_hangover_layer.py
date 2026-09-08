#!/usr/bin/env python3
"""Create a preinstalled Hangover/DXVK layer without executing ARM64 dpkg."""

from __future__ import annotations

import argparse
import copy
from dataclasses import dataclass
import hashlib
import io
import json
import lzma
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import tarfile
import tempfile
import time
import urllib.request


DEBIAN_MIRROR = "https://deb.debian.org/debian/"
USER_AGENT = "DeckLite-Hangover-Layer/1.0"
COMPATIBILITY_PACKAGES = (
    "cabextract",
    "gstreamer1.0-libav",
    "gstreamer1.0-plugins-bad",
    "gstreamer1.0-plugins-good",
    "gstreamer1.0-plugins-ugly",
    "gnome-system-monitor",
    "libasound2-plugins",
    "libfaudio0",
    "libibus-1.0-5",
    "libnm0",
    "libopenal1",
    "libsdl2-2.0-0",
    "mesa-utils",
    "openssh-client",
    "openssh-server",
    "openssh-sftp-server",
    "pciutils",
    "vulkan-tools",
    "xdotool",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize(value: str) -> str:
    while value.startswith("./"):
        value = value[2:]
    value = value.rstrip("/")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"Unsafe archive path: {value!r}")
    return path.as_posix() if value else "."


def parse_deb822(text: str) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    current: dict[str, str] = {}
    key: str | None = None
    for line in text.splitlines():
        if not line:
            if current:
                records.append(current)
                current = {}
            key = None
        elif line[0].isspace() and key:
            current[key] += "\n" + line
        elif ":" in line:
            key, value = line.split(":", 1)
            current[key] = value.lstrip()
    if current:
        records.append(current)
    return records


def record_text(record: dict[str, str], *, installed: bool) -> str:
    lines: list[str] = []
    for key, value in record.items():
        lines.append(f"{key}: {value}")
        if key == "Package" and installed:
            lines.append("Status: install ok installed")
    if installed and "Status" in record:
        lines = [line for line in lines if not line.startswith("Status: ")]
        lines.insert(1, "Status: install ok installed")
    return "\n".join(lines)


def ar_members(path: Path) -> dict[str, tuple[int, int]]:
    members: dict[str, tuple[int, int]] = {}
    with path.open("rb") as handle:
        if handle.read(8) != b"!<arch>\n":
            raise RuntimeError(f"Not a Debian ar archive: {path}")
        while True:
            header = handle.read(60)
            if not header:
                break
            if len(header) != 60 or header[58:60] != b"`\n":
                raise RuntimeError(f"Invalid ar member in {path}")
            name = header[:16].decode("ascii").strip().rstrip("/")
            size = int(header[48:58].decode("ascii").strip())
            offset = handle.tell()
            members[name] = (offset, size)
            handle.seek(size + (size & 1), os.SEEK_CUR)
    return members


class FileSlice(io.RawIOBase):
    def __init__(self, path: Path, offset: int, size: int):
        self._handle = path.open("rb")
        self._offset = offset
        self._size = size
        self._position = 0
        self._handle.seek(offset)

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def tell(self) -> int:
        return self._position

    def seek(self, offset: int, whence: int = os.SEEK_SET) -> int:
        if whence == os.SEEK_SET:
            position = offset
        elif whence == os.SEEK_CUR:
            position = self._position + offset
        elif whence == os.SEEK_END:
            position = self._size + offset
        else:
            raise ValueError(f"Unsupported seek mode: {whence}")
        if position < 0:
            raise ValueError("Negative seek position")
        self._position = min(position, self._size)
        self._handle.seek(self._offset + self._position)
        return self._position

    def read(self, size: int = -1) -> bytes:
        remaining = self._size - self._position
        if size < 0 or size > remaining:
            size = remaining
        data = self._handle.read(size)
        self._position += len(data)
        return data

    def close(self) -> None:
        if not self.closed:
            self._handle.close()
        super().close()


@dataclass
class DebPackage:
    path: Path
    control: dict[str, str]
    control_assets: dict[str, tuple[bytes, int]]
    data_name: str

    @property
    def name(self) -> str:
        return self.control["Package"]

    @classmethod
    def load(cls, path: Path) -> "DebPackage":
        members = ar_members(path)
        control_name = next(
            (name for name in members if name.startswith("control.tar")), None
        )
        data_name = next((name for name in members if name.startswith("data.tar")), None)
        if not control_name or not data_name:
            raise RuntimeError(f"Incomplete Debian package: {path}")
        offset, size = members[control_name]
        assets: dict[str, tuple[bytes, int]] = {}
        control_record: dict[str, str] | None = None
        with FileSlice(path, offset, size) as source, tarfile.open(
            fileobj=source, mode="r:*"
        ) as archive:
            for member in archive:
                name = normalize(member.name)
                if name == "." or not member.isreg():
                    continue
                handle = archive.extractfile(member)
                if handle is None:
                    continue
                content = handle.read()
                if name == "control":
                    records = parse_deb822(content.decode("utf-8"))
                    if len(records) != 1:
                        raise RuntimeError(f"Invalid control file in {path}")
                    control_record = records[0]
                else:
                    assets[name] = (content, member.mode)
        if control_record is None:
            raise RuntimeError(f"Package has no control record: {path}")
        return cls(path, control_record, assets, data_name)

    def open_data(self) -> tuple[FileSlice, tarfile.TarFile]:
        offset, size = ar_members(self.path)[self.data_name]
        source = FileSlice(self.path, offset, size)
        return source, tarfile.open(fileobj=source, mode="r:*")


def package_names_and_provides(records: list[dict[str, str]]) -> set[str]:
    names = {record["Package"] for record in records if "Package" in record}
    for record in records:
        for provided in record.get("Provides", "").split(","):
            match = re.match(r"\s*([a-z0-9][a-z0-9+.-]*)", provided)
            if match:
                names.add(match.group(1))
    return names


def dependency_groups(value: str) -> list[list[str]]:
    groups: list[list[str]] = []
    for group in value.replace("\n", " ").split(","):
        choices: list[str] = []
        for raw in group.split("|"):
            match = re.match(r"\s*([a-z0-9][a-z0-9+.-]*)(?::[a-z0-9-]+)?", raw)
            if match:
                choices.append(match.group(1))
        if choices:
            groups.append(choices)
    return groups


def resolve_dependencies(
    base_records: list[dict[str, str]],
    hangover: list[DebPackage],
    index_records: list[dict[str, str]],
) -> list[dict[str, str]]:
    by_name = {
        record["Package"]: record
        for record in index_records
        if record.get("Architecture") in {"arm64", "all"}
        and "Filename" in record
        and "SHA256" in record
    }
    # Some ABI dependencies (for example libre2-11-absl20240722) are virtual
    # capabilities from a concrete Debian package. Index Provides as well as
    # Package names so the dependency closure remains real and auditable.
    by_capability = dict(by_name)
    for record in by_name.values():
        for provided in record.get("Provides", "").split(","):
            match = re.match(r"\s*([a-z0-9][a-z0-9+.-]*)", provided)
            if match:
                by_capability.setdefault(match.group(1), record)
    available = package_names_and_provides(base_records)
    available.update(package.name for package in hangover)
    selected: dict[str, dict[str, str]] = {}
    queue = [package.control for package in hangover]
    for name in COMPATIBILITY_PACKAGES:
        # Keep OpenSSH's exact-version client/server dependency synchronized.
        if name not in available or name in {"openssh-client", "openssh-server", "openssh-sftp-server"}:
            record = by_name.get(name)
            if record is None:
                raise RuntimeError(f"Debian index has no package: {name}")
            selected[name] = record
            available.update(package_names_and_provides([record]))
            queue.append(record)

    while queue:
        record = queue.pop(0)
        for field in ("Pre-Depends", "Depends"):
            for choices in dependency_groups(record.get(field, "")):
                if any(choice in available for choice in choices):
                    continue
                chosen = next(
                    (by_capability[name] for name in choices if name in by_capability),
                    None,
                )
                if chosen is None:
                    raise RuntimeError(
                        f"Cannot satisfy {record.get('Package')} dependency: "
                        + " | ".join(choices)
                    )
                name = chosen["Package"]
                if name not in selected:
                    selected[name] = chosen
                    available.update(package_names_and_provides([chosen]))
                    queue.append(chosen)
    return [selected[name] for name in sorted(selected)]


def download_package(record: dict[str, str], package_cache: Path) -> Path:
    filename = record["Filename"]
    expected = record["SHA256"].lower()
    destination = package_cache / PurePosixPath(filename).name
    if destination.is_file() and sha256_file(destination) == expected:
        print(f"Cached Debian dependency: {destination.name}")
        return destination
    partial = destination.with_name(destination.name + ".partial")
    partial.unlink(missing_ok=True)
    request = urllib.request.Request(DEBIAN_MIRROR + filename, headers={"User-Agent": USER_AGENT})
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=180) as response, partial.open(
                "wb"
            ) as output:
                shutil.copyfileobj(response, output, length=1024 * 1024)
            break
        except Exception as error:  # network errors differ across Python builds
            last_error = error
            partial.unlink(missing_ok=True)
            if attempt == 2:
                raise
            time.sleep(1 + attempt)
    if not partial.is_file():
        raise RuntimeError(f"Download failed: {filename}: {last_error}")
    actual = sha256_file(partial)
    if actual != expected:
        partial.unlink(missing_ok=True)
        raise RuntimeError(f"SHA256 mismatch for {filename}: {actual}")
    partial.replace(destination)
    print(f"Downloaded Debian dependency: {destination.name}")
    return destination


def output_tar_context(output: Path):
    try:
        archive = tarfile.open(output, "w:zst", level=10)
        return archive, lambda: None
    except (tarfile.CompressionError, ValueError):
        zstd = shutil.which("zstd")
        if not zstd:
            raise RuntimeError("Python 3.14+ or the zstd command is required")
        temporary = Path(tempfile.mkstemp(suffix=".tar", dir=output.parent)[1])
        archive = tarfile.open(temporary, "w")

        def finalize() -> None:
            subprocess.run(
                [zstd, "-T0", "-10", "-f", str(temporary), "-o", str(output)],
                check=True,
            )
            temporary.unlink()

        return archive, finalize


def add_bytes(
    archive: tarfile.TarFile, name: str, content: bytes, mode: int = 0o644
) -> None:
    info = tarfile.TarInfo(name)
    info.size = len(content)
    info.mode = mode
    info.uid = info.gid = 0
    info.uname = info.gname = "root"
    info.mtime = int(os.environ.get("SOURCE_DATE_EPOCH", "0"))
    archive.addfile(info, io.BytesIO(content))


def copy_package_data(
    target: tarfile.TarFile, package: DebPackage
) -> list[str]:
    installed_paths: list[str] = []
    source, data = package.open_data()
    try:
        for member in data:
            path = normalize(member.name)
            if path == ".":
                continue
            cloned = copy.copy(member)
            cloned.name = path
            cloned.pax_headers = {
                key: value
                for key, value in member.pax_headers.items()
                if key not in {"path", "linkpath"}
            }
            if cloned.islnk() and cloned.linkname.startswith("./"):
                cloned.linkname = normalize(cloned.linkname)
            fileobj = data.extractfile(member) if member.isreg() else None
            target.addfile(cloned, fileobj)
            installed_paths.append("/" + path)
    finally:
        data.close()
        source.close()
    return installed_paths


def add_dxvk(target: tarfile.TarFile, dxvk_path: Path) -> int:
    count = 0
    with tarfile.open(dxvk_path, "r:*") as archive:
        for member in archive:
            path = PurePosixPath(normalize(member.name))
            parts = path.parts
            if len(parts) < 2 or parts[1] not in {"x32", "arm64ec"}:
                continue
            destination = PurePosixPath("opt/tiny/wine-manager/dxvk", *parts[1:]).as_posix()
            cloned = copy.copy(member)
            cloned.name = destination
            cloned.uid = cloned.gid = 0
            cloned.uname = cloned.gname = "root"
            cloned.pax_headers = {}
            fileobj = archive.extractfile(member) if member.isreg() else None
            target.addfile(cloned, fileobj)
            count += 1
    return count


def create_layer(
    base: Path,
    bundle: Path,
    bundle_sha256: str,
    package_index: Path,
    package_cache: Path,
    output: Path,
) -> None:
    actual_bundle_sha256 = sha256_file(bundle)
    if actual_bundle_sha256 != bundle_sha256.lower():
        raise RuntimeError(
            f"Hangover bundle SHA256 mismatch: expected {bundle_sha256}, "
            f"got {actual_bundle_sha256}"
        )
    with tarfile.open(base, "r:*") as archive:
        status_handle = archive.extractfile("var/lib/dpkg/status")
        if status_handle is None:
            raise RuntimeError("Base image has no dpkg status database")
        status_text = status_handle.read().decode("utf-8")
    base_records = parse_deb822(status_text)
    index_text = lzma.open(package_index, "rt", encoding="utf-8").read()
    index_records = parse_deb822(index_text)

    package_cache.mkdir(parents=True, exist_ok=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="decklite-hangover-") as temporary_name:
        temporary = Path(temporary_name)
        hangover_paths: list[Path] = []
        dxvk_path: Path | None = None
        with tarfile.open(bundle, "r:") as outer:
            for member in outer:
                name = PurePosixPath(member.name).name
                if not member.isreg() or not (
                    name.endswith(".deb") or name.startswith("dxvk-v")
                ):
                    continue
                source = outer.extractfile(member)
                if source is None:
                    raise RuntimeError(f"Cannot read bundle member: {member.name}")
                destination = temporary / name
                with destination.open("wb") as handle:
                    shutil.copyfileobj(source, handle, length=1024 * 1024)
                if name.endswith(".deb"):
                    hangover_paths.append(destination)
                elif name.endswith(".tar.gz"):
                    dxvk_path = destination
        if not hangover_paths or dxvk_path is None:
            raise RuntimeError("Hangover bundle is missing packages or DXVK")

        hangover_packages = [DebPackage.load(path) for path in sorted(hangover_paths)]
        dependency_records = resolve_dependencies(
            base_records, hangover_packages, index_records
        )
        dependency_packages = [
            DebPackage.load(download_package(record, package_cache))
            for record in dependency_records
        ]
        packages = dependency_packages + hangover_packages

        partial = output.with_name(output.name + ".partial")
        partial.unlink(missing_ok=True)
        target, finalize = output_tar_context(partial)
        try:
            lists: dict[str, list[str]] = {}
            for package in packages:
                print(f"Adding package: {package.name} {package.control.get('Version', '')}")
                lists[package.name] = copy_package_data(target, package)
            dxvk_count = add_dxvk(target, dxvk_path)

            installed_names = {package.name for package in packages}
            retained = [
                record
                for record in base_records
                if record.get("Package") not in installed_names
            ]
            status_records = [record_text(record, installed=False) for record in retained]
            status_records.extend(record_text(package.control, installed=True) for package in packages)
            add_bytes(
                target,
                "var/lib/dpkg/status",
                ("\n\n".join(status_records).rstrip() + "\n").encode("utf-8"),
            )

            for package in packages:
                package_list = "\n".join(sorted(set(lists[package.name]))) + "\n"
                add_bytes(
                    target,
                    f"var/lib/dpkg/info/{package.name}.list",
                    package_list.encode("utf-8"),
                )
                for asset_name, (content, mode) in package.control_assets.items():
                    add_bytes(
                        target,
                        f"var/lib/dpkg/info/{package.name}.{PurePosixPath(asset_name).name}",
                        content,
                        mode,
                    )

            marker = {
                "bundle_sha256": actual_bundle_sha256,
                "dxvk_files": dxvk_count,
                "packages": {
                    package.name: package.control.get("Version", "unknown")
                    for package in packages
                },
            }
            add_bytes(
                target,
                "opt/tiny/wine-manager/hangover-layer.json",
                (json.dumps(marker, indent=2, sort_keys=True) + "\n").encode("utf-8"),
            )
        finally:
            target.close()
        finalize()
        partial.replace(output)

    digest = sha256_file(output)
    output.with_name(output.name + ".sha256").write_text(
        f"{digest}  {output.name}\n", encoding="ascii"
    )
    print(f"Created Hangover layer: {output} ({output.stat().st_size / 1024 / 1024:.1f} MiB)")
    print(f"SHA256 {digest}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True, type=Path)
    parser.add_argument("--bundle", required=True, type=Path)
    parser.add_argument("--bundle-sha256", required=True)
    parser.add_argument("--package-index", required=True, type=Path)
    parser.add_argument("--package-cache", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    create_layer(
        args.base.resolve(),
        args.bundle.resolve(),
        args.bundle_sha256,
        args.package_index.resolve(),
        args.package_cache.resolve(),
        args.output.resolve(),
    )


if __name__ == "__main__":
    main()
