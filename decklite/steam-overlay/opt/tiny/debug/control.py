#!/usr/bin/env python3
"""Opt-in localhost SSH. Consent/keys are bound from APK-private no-backup data."""
from __future__ import annotations

import base64
import fcntl
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import pwd
import signal
import struct
import subprocess
import sys
import threading
import time

CONTROL = Path('/run/decklite-debug-control')
STATE = Path('/home/tiny/.local/state/decklite-debug')
SSHD = '/usr/sbin/sshd'


def public_key(text: str) -> str | None:
    try:
        text = text.strip()
        if len(text) > 1024 or '\n' in text or '\r' in text:
            return None
        parts = text.split()
        if len(parts) < 2 or parts[0] != 'ssh-ed25519':
            return None
        raw = base64.b64decode(parts[1], validate=True)
        if len(raw) != 51 or raw[:15] != struct.pack('>I', 11) + b'ssh-ed25519':
            return None
        if raw[15:19] != struct.pack('>I', 32):
            return None
        return 'ssh-ed25519 ' + base64.b64encode(raw).decode('ascii')
    except (ValueError, UnicodeError):
        return None


def consent() -> str | None:
    try:
        if (CONTROL / 'enabled').read_text().strip() != '1':
            return None
        if (CONTROL / 'authorized_keys').stat().st_size > 1024:
            return None
        return public_key((CONTROL / 'authorized_keys').read_text())
    except (OSError, ValueError):
        return None


def config() -> str:
    return f'''Port 8027
ListenAddress 127.0.0.1
AddressFamily inet
HostKey {STATE}/host_ed25519
PidFile {STATE}/sshd.pid
AuthorizedKeysFile {CONTROL}/authorized_keys
AuthenticationMethods publickey
PubkeyAuthentication yes
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitEmptyPasswords no
PermitRootLogin no
AllowUsers tiny
UsePAM no
StrictModes no
DisableForwarding yes
AllowTcpForwarding no
AllowStreamLocalForwarding no
AllowAgentForwarding no
X11Forwarding no
PermitTunnel no
GatewayPorts no
PermitUserEnvironment no
PermitUserRC no
UseDNS no
LoginGraceTime 30
MaxAuthTries 3
MaxStartups 2:30:4
LogLevel ERROR
Subsystem sftp internal-sftp
'''


def proc_identity(pid: int) -> tuple[int, str] | None:
    try:
        fields = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
        return int(fields[1]), fields[19]  # PPID, starttime
    except (OSError, ValueError, IndexError):
        return None


def descendants(parent: int) -> dict[int, str]:
    table = {}
    for path in Path('/proc').iterdir():
        if path.name.isdigit():
            identity = proc_identity(int(path.name))
            if identity:
                table[int(path.name)] = identity
    found: dict[int, str] = {}
    if parent in table:
        found[parent] = table[parent][1]
    changed = True
    while changed:
        changed = False
        for pid, (ppid, start) in table.items():
            if ppid in found and pid not in found:
                found[pid] = start
                changed = True
    return found


def stop_tree(child: subprocess.Popen) -> None:
    # Snapshot only this server's descendants; guard against PID reuse.
    owned = descendants(child.pid)
    for sig in (signal.SIGTERM, signal.SIGKILL):
        for pid, start in reversed(list(owned.items())):
            current = proc_identity(pid)
            if current and current[1] == start:
                try:
                    os.kill(pid, sig)
                except ProcessLookupError:
                    pass
        if sig == signal.SIGTERM:
            time.sleep(0.25)
    try:
        child.wait(timeout=2)
    except subprocess.TimeoutExpired:
        child.kill()


def supervise() -> int:
    key = consent()
    if key is None:
        return 0
    os.umask(0o077)
    STATE.mkdir(parents=True, exist_ok=True)
    with (STATE / 'supervisor.lock').open('w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return 0
        logger = logging.getLogger('decklite-debug')
        logger.setLevel(logging.INFO)
        logger.addHandler(RotatingFileHandler(STATE / 'ssh.log', maxBytes=512*1024, backupCount=1))
        try:
            pwd.getpwnam('sshd')
        except KeyError:
            subprocess.run(['/usr/sbin/useradd', '--system', '--no-create-home',
                            '--home-dir', '/run/sshd', '--shell', '/usr/sbin/nologin', 'sshd'], check=True)
        Path('/run/sshd').mkdir(mode=0o755, parents=True, exist_ok=True)
        host = STATE / 'host_ed25519'
        if not host.exists():
            subprocess.run(['/usr/bin/ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-f', str(host)], check=True)
        host.chmod(0o600)
        configuration = STATE / 'sshd_config'
        configuration.write_text(config())
        subprocess.run([SSHD, '-t', '-f', str(configuration)], check=True)
        if consent() != key:
            return 0
        child = subprocess.Popen([SSHD, '-D', '-e', '-f', str(configuration)],
                                 stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                 stderr=subprocess.PIPE, start_new_session=True)
        # Drain bounded error messages, never command or terminal transcripts.
        def drain():
            while line := child.stderr.readline(4096):
                logger.error(line.decode('utf-8', errors='replace').strip())
        threading.Thread(target=drain, daemon=True).start()
        stopping = threading.Event()
        for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
            signal.signal(sig, lambda *_: stopping.set())
        logger.info('Debug SSH requested on 127.0.0.1:8027; public-key authentication only.')
        try:
            while child.poll() is None and not stopping.wait(1):
                if consent() != key:
                    break
        finally:
            stop_tree(child)
            logger.info('Debug SSH stopped.')
        return 0


def main() -> int:
    if sys.argv[1:] == ['start']:
        if consent() is not None:
            subprocess.Popen([sys.executable, str(Path(__file__).resolve()), 'supervise'],
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, start_new_session=True)
        return 0
    if sys.argv[1:] == ['supervise']:
        return supervise()
    print('Debug SSH ready to start' if consent() else 'Debug SSH off or not paired')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
