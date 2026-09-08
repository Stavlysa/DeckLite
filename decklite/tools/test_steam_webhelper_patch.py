"""Host parser tests; shell environment tests also run inside the container."""
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'steam-overlay/opt/tiny/steam-arm64/patch-steam-webhelper.py'
if not SCRIPT.exists():
    SCRIPT = Path('/opt/tiny/steam-arm64/patch-steam-webhelper.py')
spec = importlib.util.spec_from_file_location('cefpatch', SCRIPT)
patcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(patcher)


class WebhelperPatchTests(unittest.TestCase):
    def test_known_versions_idempotent(self):
        for command in patcher.KNOWN:
            for prefix in ('exec ', 'exec taskset 0x7c '):
                with self.subTest(command=command, prefix=prefix):
                    source = '#!/bin/bash\nexport LIBGL_KOPPER_DISABLE=true\n' + prefix + command + ' &> ~/.steam/steam/logs/steamwebhelper.log\n'
                    result = patcher.patch_text(source)
                    self.assertIn(prefix + patcher.PATCHED, result)
                    self.assertEqual(result, patcher.patch_text(result))
                    self.assertTrue(result.endswith(' &> ~/.steam/steam/logs/steamwebhelper.log\n'))

    def test_reject_unknown_or_ambiguous(self):
        for source in ('# exec ' + patcher.CURRENT + '\n',
                       'exec ' + patcher.CURRENT + ' --future-flag\n',
                       ('exec ' + patcher.CURRENT + '\n') * 2,
                       'exec future-launcher "$@"\n'):
            with self.subTest(source=source), self.assertRaises(ValueError):
                patcher.patch_text(source)

    @unittest.skipUnless(os.name == 'posix' and shutil.which('bash'), 'guest shell test')
    def test_cef_only_environment_and_overrides(self):
        # Replace only the executable for a harmless environment print.
        command = patcher.PATCHED.replace('$(pwd)/steamwebhelper', '/usr/bin/env')
        command = command.split(' --disable-dev-shm-usage')[0]
        base = {k: v for k, v in os.environ.items()
                if k not in ('ZINK_DEBUG', 'GALLIUM_THREAD', 'STEAM_CEF_KOPPER_DISABLE')}
        for additions, expected in (({}, None), ({'ZINK_DEBUG': 'quiet'}, 'quiet')):
            with self.subTest(additions=additions):
                script = command + '\nprintf "PARENT_ZINK=%s\\n" "${ZINK_DEBUG-unset}"\n'
                result = subprocess.run(['bash', '-c', script], env=base | additions,
                                        check=True, capture_output=True, text=True)
                values = dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line)
                self.assertEqual(values.get('ZINK_DEBUG'), expected)
                self.assertNotIn('GALLIUM_THREAD', values)
                self.assertEqual(values['PARENT_ZINK'], additions.get('ZINK_DEBUG', 'unset'))
                self.assertEqual(values['LIBGL_KOPPER_DISABLE'], 'false')

    def test_flags_are_cef_only(self):
        self.assertEqual(patcher.PATCHED.count('--disable-gpu-compositing'), 1)
        self.assertNotIn('ZINK_DEBUG', patcher.PATCHED)
        self.assertNotIn('GALLIUM_THREAD', patcher.PATCHED)
        launcher = SCRIPT.with_name('run-steam.sh').read_text()
        self.assertNotIn('--disable-gpu-compositing', launcher)
        self.assertNotIn('export ZINK_DEBUG', launcher)


if __name__ == '__main__':
    unittest.main(verbosity=2)
