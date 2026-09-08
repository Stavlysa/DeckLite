#!/usr/bin/env python3
"""Host-side protocol/policy tests, not an Android/OpenSSH runtime certification."""
import base64
import importlib.util
import os
from pathlib import Path
import struct
import sys
import tempfile
import types
import unittest
from unittest.mock import patch, MagicMock

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'steam-overlay/opt/tiny/debug/control.py'
if os.name == 'nt':
    sys.modules.setdefault('fcntl', types.SimpleNamespace(flock=MagicMock(), LOCK_EX=2, LOCK_NB=4))
    sys.modules.setdefault('pwd', types.SimpleNamespace(getpwnam=MagicMock()))
spec = importlib.util.spec_from_file_location('debug_control', SCRIPT)
control = importlib.util.module_from_spec(spec)
spec.loader.exec_module(control)


class DebugProtocolTests(unittest.TestCase):
    def setUp(self):
        # The guest uses Linux signals; Windows lacks SIGKILL. Calls to kill()
        # are mocked in these policy tests, so supply only the missing constant.
        if not hasattr(control.signal, 'SIGKILL'):
            signal_patch = patch.object(control.signal, 'SIGKILL', 9, create=True)
            signal_patch.start()
            self.addCleanup(signal_patch.stop)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.binding = patch.object(control, 'CONTROL', self.directory)
        self.binding.start()
        self.addCleanup(self.binding.stop)
        self.key = 'ssh-ed25519 ' + base64.b64encode(
            struct.pack('>I', 11) + b'ssh-ed25519' + struct.pack('>I', 32) + bytes(range(32))
        ).decode('ascii')

    def test_fresh_import_is_off(self):
        self.assertIsNone(control.consent())
        with patch.object(control.subprocess, 'Popen') as spawn, patch.object(sys, 'argv', ['control.py', 'start']):
            self.assertEqual(control.main(), 0)
            spawn.assert_not_called()
        self.assertEqual(list(self.directory.iterdir()), [])

    def test_flag_without_key_cannot_start_ssh(self):
        (self.directory / 'enabled').write_text('1\n')
        self.assertIsNone(control.consent())

    def test_key_without_consent_cannot_start_ssh(self):
        (self.directory / 'authorized_keys').write_text(self.key)
        self.assertIsNone(control.consent())

    def test_pairing_and_switch_off(self):
        (self.directory / 'enabled').write_text('1\n')
        (self.directory / 'authorized_keys').write_text(self.key)
        self.assertEqual(control.consent(), self.key)
        (self.directory / 'enabled').unlink()
        self.assertIsNone(control.consent())

    def test_invalid_keys_and_key_options_fail_closed(self):
        self.assertEqual(control.public_key(self.key + ' computer\n'), self.key)
        for bad in ('', 'ssh-rsa AAAA', 'ssh-ed25519 AAAA', self.key + '\n' + self.key,
                    'command="id" ' + self.key, self.key + 'AAAA', 'x' * 2048):
            self.assertIsNone(control.public_key(bad), bad[:30])

    def test_loopback_public_key_only_policy(self):
        parsed = dict(line.split(maxsplit=1) for line in control.config().splitlines())
        expected = {'Port': '8027', 'ListenAddress': '127.0.0.1', 'AddressFamily': 'inet',
                    'AuthenticationMethods': 'publickey', 'PasswordAuthentication': 'no',
                    'KbdInteractiveAuthentication': 'no', 'PermitRootLogin': 'no',
                    'PermitEmptyPasswords': 'no', 'AllowUsers': 'tiny', 'DisableForwarding': 'yes',
                    'X11Forwarding': 'no', 'PermitUserEnvironment': 'no'}
        for key, value in expected.items():
            self.assertEqual(parsed[key], value)

    def test_stop_does_not_signal_reused_pid(self):
        child = MagicMock(pid=400)
        with patch.object(control, 'descendants', return_value={400: 'old'}), \
             patch.object(control, 'proc_identity', return_value=(1, 'new')), \
             patch.object(control.os, 'kill') as kill, patch.object(control.time, 'sleep'):
            control.stop_tree(child)
            kill.assert_not_called()

    def test_stop_signals_only_owned_processes(self):
        child = MagicMock(pid=400)
        with patch.object(control, 'descendants', return_value={400: 'birth'}), \
             patch.object(control, 'proc_identity', return_value=(1, 'birth')), \
             patch.object(control.os, 'kill') as kill, patch.object(control.time, 'sleep'):
            control.stop_tree(child)
            self.assertEqual(kill.call_count, 2)
            self.assertTrue(all(call.args[0] == 400 for call in kill.call_args_list))


if __name__ == '__main__':
    unittest.main(verbosity=2)
