"""Stream-compare a UI-only release with its hash-pinned clean base.

Checks all non-directory payloads and links without extracting a multi-GB rootfs.
This supplements source/security checks; it is not a device runtime test.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import tarfile

from build_steam_rootfs import normalize


CHANGED = {".tiny.yaml", "opt/tiny/debug/release.json",
           "opt/tiny/wine-manager/wine_manager.py"}


def inventory(path):
    entries = {}
    metadata = None
    with tarfile.open(path, "r|zst") as archive:
        for member in archive:
            name = normalize(member.name)
            if member.isdir():
                continue
            if name in entries:
                raise ValueError(f"Duplicate non-directory member: {name}")
            digest = None
            if member.isfile():
                stream = archive.extractfile(member)
                if name == ".tiny.yaml":
                    metadata = stream.read()
                    digest = hashlib.sha256(metadata).hexdigest()
                else:
                    digest = hashlib.file_digest(stream, "sha256").hexdigest()
            target = normalize(member.linkname) if member.islnk() else member.linkname
            entries[name] = (member.type, member.mode, member.uid, member.gid,
                             member.size, target, digest)
    if metadata is None:
        raise ValueError("Missing Tiny Container metadata")
    print(f"Indexed {len(entries):,} payloads/links: {path.name}", flush=True)
    return entries, metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True, type=Path)
    parser.add_argument("--base-sha256", required=True)
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--overlay", required=True, type=Path)
    args = parser.parse_args()
    with args.base.open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != args.base_sha256:
            raise ValueError("Base SHA-256 mismatch")
    before, old_metadata = inventory(args.base)
    after, new_metadata = inventory(args.archive)
    if before.keys() != after.keys():
        raise ValueError(f"Added: {after.keys() - before.keys()}; "
                         f"removed: {before.keys() - after.keys()}")
    changed = {name for name in before if before[name] != after[name]}
    if changed != CHANGED:
        raise ValueError(f"Unexpected change set: {sorted(changed)}")
    for name in CHANGED - {".tiny.yaml"}:
        source = args.overlay / name
        expected = hashlib.sha256(source.read_bytes()).hexdigest()
        if after[name][-1] != expected:
            raise ValueError(f"Changed payload differs from source: {name}")
        if before[name][:4] != after[name][:4]:
            raise ValueError(f"Changed payload permissions/ownership differ: {name}")
    release = json.loads((args.overlay / "opt/tiny/debug/release.json").read_text())
    version = release["release"]
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError("Invalid release version")
    expected, count = re.subn(rb"(?m)^name: DeckLite Steam ARM64 \d+\.\d+\.\d+$",
                             f"name: DeckLite Steam ARM64 {version}".encode(),
                             old_metadata, count=1)
    if count != 1 or new_metadata != expected:
        raise ValueError("Unexpected Tiny metadata change beyond release name")
    print(f"PASS: all {len(before) - len(CHANGED):,} other payloads/links are unchanged "
          "(bytes, mode, ownership, type and link target).", flush=True)
    print("PASS: only Wine Manager, release.json and the container name changed.", flush=True)


if __name__ == "__main__":
    main()
