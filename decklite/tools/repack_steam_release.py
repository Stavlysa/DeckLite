#!/usr/bin/env python3
"""Apply a reviewed overlay to a hash-pinned clean distributable, not a device export."""
import argparse
import copy
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import tarfile

from build_steam_rootfs import add_file, add_symlink, gather_tree, normalize, tar_info


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', required=True, type=Path)
    parser.add_argument('--base-sha256', required=True)
    parser.add_argument('--overlay', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if args.base.resolve() == args.output.resolve():
        raise RuntimeError('Never overwrite the clean base')
    if digest(args.base) != args.base_sha256.lower():
        raise RuntimeError('Clean base checksum mismatch')
    directories, files, symlinks = gather_tree(args.overlay, '')
    version = json.loads((args.overlay / 'opt/tiny/debug/release.json').read_text())['release']
    if not re.fullmatch(r'\d+\.\d+\.\d+', version):
        raise RuntimeError('Invalid release version')
    partial = args.output.with_name(args.output.name + '.partial')
    copied = 0
    with tarfile.open(args.base, 'r|zst') as source, tarfile.open(partial, 'w:zst', level=10) as target:
        first = next(iter(source))
        if normalize(first.name) != '.tiny.yaml' or not first.isfile():
            raise RuntimeError('Clean base metadata must be first')
        metadata = source.extractfile(first).read().decode('utf-8')
        metadata, count = re.subn(r'(?m)^name: DeckLite Steam ARM64 \d+\.\d+\.\d+$',
                                  f'name: DeckLite Steam ARM64 {version}', metadata, count=1)
        if count != 1:
            raise RuntimeError('Missing release name')
        if 'Software MIDI output and clean desktop defaults included.' not in metadata:
            metadata = metadata.replace('  Optional authenticated USB debugging toolbox',
                '  Software MIDI output and clean desktop defaults included. Use APK 4.3.2\n'
                '  for language selection and corrected mouse/touchpad input.\n'
                '  Optional authenticated USB debugging toolbox', 1)
        metadata = metadata.replace('APK 4.3.0 required', 'APK 4.3.2 recommended')
        first = copy.copy(first)
        first.name = '.tiny.yaml'
        first.pax_headers = {}
        encoded = metadata.encode('utf-8')
        first.size = len(encoded)
        target.addfile(first, io.BytesIO(encoded))
        # iter(source) includes the first cached member again; skip metadata explicitly.
        for member in source:
            path = normalize(member.name)
            if path in {'.', '.tiny.yaml'} or path in files or path in symlinks or path in directories:
                continue
            cloned = copy.copy(member)
            cloned.name = path
            cloned.pax_headers = {k: v for k, v in cloned.pax_headers.items()
                                  if k not in {'path', 'linkpath'}}
            if cloned.islnk():
                cloned.linkname = normalize(cloned.linkname)
            target.addfile(cloned, source.extractfile(member) if member.isfile() else None)
            copied += 1
        needed = set(directories)
        for path in set(files) | set(symlinks):
            for parent in PurePosixPath(path).parents:
                if str(parent) != '.':
                    needed.add(str(parent))
        for path in sorted(needed - {''}, key=lambda p: (p.count('/'), p)):
            target.addfile(tar_info(path, directory=True))
        for path, local in sorted(files.items()):
            add_file(target, path, local)
        for path, link in sorted(symlinks.items()):
            add_symlink(target, path, link)
    partial.replace(args.output)
    checksum = digest(args.output)
    args.output.with_name(args.output.name + '.sha256').write_text(
        f'{checksum}  {args.output.name}\n', encoding='ascii')
    print(f'Copied {copied:,} clean-base entries; applied {len(files)} overlay files.')
    print(f'Created {args.output} ({args.output.stat().st_size:,} bytes)')
    print(f'SHA256 {checksum}')


if __name__ == '__main__':
    main()
