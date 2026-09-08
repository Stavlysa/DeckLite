import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest

SCRIPT = Path(__file__).with_name('repack_steam_release.py')


class RepackTests(unittest.TestCase):
    def test_pinned_clean_base_overlay_and_link(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            base, output, overlay = root/'base.tar.zst', root/'out.tar.zst', root/'overlay'
            payload = overlay/'opt/tiny/new.sh'
            payload.parent.mkdir(parents=True)
            payload.write_text('#!/bin/sh\nexit 0\n')
            release = overlay/'opt/tiny/debug/release.json'
            release.parent.mkdir()
            release.write_text(json.dumps({'release': '4.3.2'}))
            with tarfile.open(base, 'w:zst') as tar:
                for name, value in [('.tiny.yaml', b'name: DeckLite Steam ARM64 4.3.0\ndescription: |\n  Optional authenticated USB debugging toolbox\n'),
                                    ('usr/bin/preserved', b'clean security binary'),
                                    ('opt/tiny/new.sh', b'old')]:
                    info = tarfile.TarInfo(name)
                    info.size = len(value)
                    info.mode = 0o755
                    tar.addfile(info, io.BytesIO(value))
                link = tarfile.TarInfo('usr/bin/preserved-link')
                link.type = tarfile.LNKTYPE
                link.linkname = 'usr/bin/preserved'
                tar.addfile(link)
            sha = hashlib.sha256(base.read_bytes()).hexdigest()
            command = [sys.executable, str(SCRIPT), '--base', str(base), '--base-sha256', sha,
                       '--overlay', str(overlay), '--output', str(output)]
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            with tarfile.open(output, 'r:zst') as tar:
                names = tar.getnames()
                self.assertEqual(names[0], '.tiny.yaml')
                self.assertEqual(names.count('.tiny.yaml'), 1)
                self.assertEqual(names.count('opt/tiny/new.sh'), 1)
                self.assertIn(b'4.3.2', tar.extractfile('.tiny.yaml').read())
                self.assertEqual(tar.extractfile('usr/bin/preserved').read(), b'clean security binary')
                self.assertEqual(tar.extractfile('usr/bin/preserved-link').read(), b'clean security binary')
                self.assertEqual(tar.extractfile('opt/tiny/new.sh').read(), payload.read_bytes())
                self.assertEqual(tar.getmember('opt/tiny/new.sh').mode, 0o755)
            self.assertEqual(hashlib.sha256(base.read_bytes()).hexdigest(), sha)
            # Repacking an already-upgraded clean base must not duplicate its
            # description. This is the 4.3.2 -> 4.3.3 incremental release path.
            again = root / 'again.tar.zst'
            repeat_command = command.copy()
            repeat_command[repeat_command.index('--base')+1] = str(output)
            repeat_command[repeat_command.index('--base-sha256')+1] = hashlib.sha256(output.read_bytes()).hexdigest()
            repeat_command[repeat_command.index('--output')+1] = str(again)
            result = subprocess.run(repeat_command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            with tarfile.open(again, 'r:zst') as tar:
                metadata = tar.extractfile('.tiny.yaml').read()
                self.assertEqual(metadata.count(b'Software MIDI output'), 1)
            # Wrong base checksum must fail before replacing an existing result.
            before = output.read_bytes()
            command[command.index('--base-sha256')+1] = '0'*64
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(output.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
