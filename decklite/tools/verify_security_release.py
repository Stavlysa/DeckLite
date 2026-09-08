#!/usr/bin/env python3
"""Targeted distributable checks; not an exhaustive malware/CVE audit."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import tarfile


def verify(archive: Path, overlay: Path) -> None:
    source_paths = [
        'opt/tiny/debug/control.py', 'opt/tiny/debug/README.md', 'opt/tiny/debug/release.json',
        'opt/tiny/start-desktop.sh', 'opt/tiny/wine-manager/wine_manager.py',
        'opt/tiny/wine-manager/wine-region-env.sh', 'opt/tiny/wine-manager/wine_timezone.py',
        'opt/tiny/wine-manager/auto-display-x11.py', 'opt/tiny/wine-manager/stop-wine.py',
        'opt/tiny/steam-arm64/run-exe.sh', 'opt/tiny/steam-arm64/run-steam.sh',
        'opt/tiny/steam-arm64/patch-steam-webhelper.py',
        'opt/tiny/wine-manager/wine-prefix-run', 'opt/tiny/wine-manager/wine-midi-env.sh',
        'opt/tiny/extra/libdecklite-soft-midi.so',
        'usr/share/doc/decklite-steam-arm64/WINE-MIDI.md',
    ]
    expected = {path: hashlib.sha256((overlay / path).read_bytes()).hexdigest() for path in source_paths}
    binaries = {'usr/sbin/sshd', 'usr/bin/ssh-keygen', 'usr/lib/openssh/sshd-session', 'usr/lib/openssh/sshd-auth'}
    found = set()
    private = []
    total = 0
    with tarfile.open(archive, 'r|zst') as tar:
        for member in tar:
            total += 1
            name = member.name.removeprefix('./').rstrip('/')
            path = PurePosixPath(name)
            if path.is_absolute() or '..' in path.parts:
                raise RuntimeError(f'Unsafe archive member: {name}')
            if not member.isfile():
                continue
            if (re.fullmatch(r'etc/ssh/ssh_host_.*_key', name)
                    or name.startswith(('home/tiny/.ssh/', 'root/.ssh/', 'home/tiny/.local/state/decklite-debug/'))
                    or name in {'run/decklite-debug-control/enabled', 'run/decklite-debug-control/authorized_keys'}
                    or re.search(r'/(?:ssfn\d+|loginusers\.vdf)$', name)):
                private.append(name)
            if name in expected:
                if name in found:
                    raise RuntimeError(f'Duplicate release payload: {name}')
                digest = hashlib.sha256(tar.extractfile(member).read()).hexdigest()
                if digest != expected[name]:
                    raise RuntimeError(f'Payload differs from reviewed source: {name}')
                found.add(name)
            elif name in binaries:
                header = tar.extractfile(member).read(20)
                if header[:4] != b'\x7fELF' or int.from_bytes(header[18:20], 'little') != 183:
                    raise RuntimeError(f'Not ARM64 ELF: {name}')
                found.add(name)
            elif name == '.tiny.yaml':
                metadata = tar.extractfile(member).read().decode('utf-8')
                version = json.loads((overlay / 'opt/tiny/debug/release.json').read_text())['release']
                if f'DeckLite Steam ARM64 {version}' not in metadata:
                    raise RuntimeError('Wrong release metadata')
            elif name == 'opt/tiny/wine-manager/hangover-layer.json':
                packages = json.load(tar.extractfile(member))['packages']
                for package in ('openssh-server', 'openssh-client', 'openssh-sftp-server'):
                    if packages.get(package) != '1:10.0p1-7+deb13u4':
                        raise RuntimeError(f'Unexpected package version: {package}')
                found.add(name)
    missing = (set(expected) | binaries | {'opt/tiny/wine-manager/hangover-layer.json'}) - found
    if missing or private:
        raise RuntimeError(f'Missing required files: {sorted(missing)}; private/debug-state files: {private}')
    print(f'PASS: read {total:,} archive entries; {len(expected)} exact source hashes and ARM64 SSH binaries verified.')
    print('PASS: no shipped SSH host/private keys, paired keys, enabled marker or Steam login-user files in checked locations.')
    print('Existing Wine/Steam launch, timezone, UI and fullscreen payload hashes match the retained overlay.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--archive', required=True, type=Path)
    parser.add_argument('--overlay', type=Path, default=Path(__file__).resolve().parents[1] / 'steam-overlay')
    args = parser.parse_args()
    verify(args.archive, args.overlay)
