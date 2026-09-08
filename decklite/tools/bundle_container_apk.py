"""Embed an independently verified rootfs in a ZIP32 APK, without a giant asset.

Build a normal APK first, run `embed`, then zipalign and apksigner. Finally run
`verify` on the signed APK. Never sign/ship the intermediate unsigned output.
Only task-created output is removed after an unsuccessful build.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import struct
import zipfile

CHUNK = 512 * 1024 * 1024
BUFFER = 1024 * 1024
ZIP32_MAX = 0xFFFFFFFF
MANIFEST = "assets/builtin/rootfs.properties"


def part_name(index):
    return f"assets/builtin/rootfs.part{index:03d}"


def signature_entry(name):
    upper = name.upper()
    return upper.startswith("META-INF/") and (
        upper == "META-INF/MANIFEST.MF" or
        upper.endswith((".SF", ".RSA", ".DSA", ".EC")))


def properties(size, digest, chunk, minimum_free, code):
    return (f"format=1\nbytes={size}\npart_bytes={chunk}\nsha256={digest}\n"
            f"minimum_free_bytes={minimum_free}\ncode={code}\n").encode("ascii")


def embed(base, rootfs, output, expected_sha, *, chunk=CHUNK,
          minimum_free=22 * 1024**3, code="decklitesteamarm64"):
    base, rootfs, output = map(Path, (base, rootfs, output))
    size = rootfs.stat().st_size
    if not (0 < size <= ZIP32_MAX and 0 < chunk <= CHUNK and
            (size + chunk - 1) // chunk <= 64 and minimum_free >= size):
        raise ValueError("Invalid rootfs/chunk/free-space size")
    if not re.fullmatch(r"[0-9a-f]{64}", expected_sha):
        raise ValueError("An expected SHA-256 is required")
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", code):
        raise ValueError("Invalid container code")
    if size + base.stat().st_size + 8 * 1024 * 1024 >= ZIP32_MAX:
        raise ValueError("APK would exceed conservative ZIP32 size limit")
    if output.exists():
        raise FileExistsError(output)
    # Python defaults to ZIP64 above 2 GiB; Android APKs must remain ZIP32.
    # Every member is <= 512 MiB; the whole APK is checked below 4 GiB.
    old_limit = zipfile.ZIP64_LIMIT
    zipfile.ZIP64_LIMIT = ZIP32_MAX
    created = False
    try:
        with zipfile.ZipFile(base) as source, output.open("xb") as raw:
            created = True
            with zipfile.ZipFile(raw, "w", allowZip64=False) as dest:
                seen = set()
                for info in source.infolist():
                    if info.filename in seen:
                        raise ValueError("Duplicate base APK entry")
                    seen.add(info.filename)
                    if info.filename.startswith("assets/builtin/") or info.filename == "assets/rootfs.tar.zst":
                        raise ValueError("Base APK already contains a bundled rootfs")
                    if signature_entry(info.filename):
                        continue
                    entry = copy.copy(info)
                    entry.extra = b""  # discard old alignment / ZIP64 fields
                    with source.open(info) as src, dest.open(entry, "w", force_zip64=False) as dst:
                        while block := src.read(BUFFER):
                            dst.write(block)
                dest.writestr(MANIFEST, properties(size, expected_sha, chunk, minimum_free, code),
                              compress_type=zipfile.ZIP_STORED)
                digest = hashlib.sha256()
                with rootfs.open("rb") as src:
                    remaining = size
                    for index in range((size + chunk - 1) // chunk):
                        entry = zipfile.ZipInfo(part_name(index), (2026, 9, 8, 0, 0, 0))
                        entry.compress_type = zipfile.ZIP_STORED
                        entry.file_size = min(chunk, remaining)
                        count = entry.file_size
                        with dest.open(entry, "w", force_zip64=False) as dst:
                            while count:
                                block = src.read(min(BUFFER, count))
                                if not block:
                                    raise ValueError("Rootfs became truncated while packaging")
                                dst.write(block)
                                digest.update(block)
                                count -= len(block)
                                remaining -= len(block)
                        print(f"Embedded part {index + 1}: {size - remaining}/{size}", flush=True)
                    if src.read(1) or digest.hexdigest() != expected_sha:
                        raise ValueError("Rootfs changed or SHA-256 does not match approved release")
        return verify(output, expected_sha)
    except BaseException:
        if created:
            output.unlink(missing_ok=True)
        raise
    finally:
        zipfile.ZIP64_LIMIT = old_limit


def verify(apk, expected_sha):
    apk = Path(apk)
    if apk.stat().st_size >= ZIP32_MAX:
        raise ValueError("APK exceeds ZIP32 limit")
    with apk.open("rb") as raw:
        raw.seek(-22, 2)
        eocd = raw.read(22)
    if eocd[:4] != b"PK\x05\x06":
        raise ValueError("Expected standard ZIP32 end record without a comment")
    _, disk, central_disk, disk_entries, entries, central_size, central_offset, comment = struct.unpack("<4s4H2IH", eocd)
    if disk or central_disk or disk_entries != entries or comment or entries == 65535:
        raise ValueError("Unsupported multi-disk/ZIP64 APK")
    if central_offset + central_size != apk.stat().st_size - 22:
        raise ValueError("Invalid ZIP32 central directory")
    with zipfile.ZipFile(apk) as archive:
        infos = archive.infolist()
        if len(infos) != entries or len(set(i.filename for i in infos)) != entries:
            raise ValueError("Duplicate or inconsistent APK entries")
        p = dict(line.split("=", 1) for line in archive.read(MANIFEST).decode("ascii").splitlines() if line)
        size, chunk = int(p["bytes"]), int(p["part_bytes"])
        if p["format"] != "1" or p["sha256"] != expected_sha or not (0 < size <= ZIP32_MAX and 0 < chunk <= CHUNK):
            raise ValueError("Invalid embedded manifest")
        count = (size + chunk - 1) // chunk
        expected_names = {MANIFEST} | {part_name(i) for i in range(count)}
        actual_names = {i.filename for i in infos if i.filename.startswith("assets/builtin/")}
        if actual_names != expected_names:
            raise ValueError("Unexpected/missing bundled asset")
        digest = hashlib.sha256()
        total = 0
        for index in range(count):
            info = archive.getinfo(part_name(index))
            if info.file_size != min(chunk, size - total) or info.compress_type != zipfile.ZIP_STORED:
                raise ValueError("Unexpected asset size/compression")
            with archive.open(info) as stream:
                while block := stream.read(BUFFER):
                    digest.update(block)
                    total += len(block)
        if total != size or digest.hexdigest() != expected_sha:
            raise ValueError("Embedded rootfs SHA-256 mismatch")
        # Reading the smaller app entries also checks their ZIP CRCs.
        for info in infos:
            if not info.filename.startswith("assets/builtin/"):
                with archive.open(info) as stream:
                    while stream.read(BUFFER):
                        pass
    result = {"apk": str(apk.resolve()), "apk_bytes": apk.stat().st_size,
              "rootfs_bytes": total, "rootfs_sha256": digest.hexdigest(),
              "parts": count, "zip32": True, "central_directory_offset": central_offset}
    print(json.dumps(result), flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("embed")
    build.add_argument("--base", required=True)
    build.add_argument("--rootfs", required=True)
    build.add_argument("--output", required=True)
    build.add_argument("--sha256", required=True)
    check = sub.add_parser("verify")
    check.add_argument("apk")
    check.add_argument("--sha256", required=True)
    args = parser.parse_args()
    if args.command == "embed":
        embed(args.base, args.rootfs, args.output, args.sha256)
    else:
        verify(args.apk, args.sha256)


if __name__ == "__main__":
    main()
