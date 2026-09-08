#!/usr/bin/env python3
"""Stop Wine/Proton only in this container; native Steam/X11 stay running."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import select
import signal
import time

PROC = Path('/proc')


def is_wine_executable(executable: str) -> bool:
    path = Path(executable.removesuffix(' (deleted)'))
    if path.name in {'wineserver', 'wineserver64'}:
        return path.parent.name in {'bin', 'bin-arm64', 'wine', 'aarch64-unix', 'x86_64-unix'}
    return (path.name in {'wine', 'wine64', 'wine-preloader', 'wine64-preloader'}
            and any(part in {'wine', 'aarch64-unix', 'x86_64-unix'} for part in path.parts[:-1]))


def identity(pid: int) -> tuple[int, str] | None:
    try:
        entry = PROC / str(pid)
        if entry.stat().st_uid != (PROC / 'self').stat().st_uid:
            return None
        # PRoot translates a followed /proc/PID/root back into the guest root,
        # even for a host process whose raw link is '/'. Compare raw roots first
        # so shared Android UIDs cannot make other containers look identical.
        if os.readlink(entry / 'root') != os.readlink(PROC / 'self/root'):
            return None
        if not os.path.samestat((entry / 'root').stat(), (PROC / 'self/root').stat()):
            return None
        executable = os.readlink(entry / 'exe')
        if not is_wine_executable(executable):
            return None
        fields = (entry / 'stat').read_text().rsplit(')', 1)[1].split()
        return int(fields[19]), executable  # kernel start time, protects PID reuse
    except (OSError, ValueError, IndexError):
        return None


def targets() -> dict[int, tuple[int, str]]:
    result = {}
    for entry in PROC.iterdir():
        if entry.name.isdigit() and int(entry.name) != os.getpid():
            found = identity(int(entry.name))
            if found:
                result[int(entry.name)] = found
    return result


def group_alive(pid: int, start_time: int) -> bool:
    """Fallback liveness only; never grants permission to signal a process.

    A Wine leader can exit while Mesa/audio workers survive. In that state
    /proc/PID/exe and root may disappear, but the task group still consumes RAM.
    Do not mistake loss of those identity links for successful termination.
    """
    entry = PROC / str(pid)
    try:
        fields = (entry / 'stat').read_text().rsplit(')', 1)[1].split()
        if int(fields[19]) != start_time:
            return False
        for task in (entry / 'task').iterdir():
            try:
                state = (task / 'stat').read_text().rsplit(')', 1)[1].split()[0]
                if state not in {'Z', 'X'}:
                    return True
            except FileNotFoundError:
                continue
        return False
    except FileNotFoundError:
        return False
    except (OSError, ValueError, IndexError):
        return True  # Unknown is not proof that all workers have exited.


class TrackedProcess:
    def __init__(self, pid: int, expected: tuple[int, str]):
        self.pid, self.expected, self.fd = pid, expected, None
        self.stale = identity(pid) != expected
        if self.stale:
            return
        if hasattr(os, 'pidfd_open') and hasattr(signal, 'pidfd_send_signal'):
            try:
                fd = os.pidfd_open(pid, 0)
            except OSError:
                return  # Older/filtered kernels retain strict identity checks.
            # Pin every authorized process before signalling any server. A
            # pidfd cannot retarget a recycled PID, even after its leader exits.
            if identity(pid) != expected:
                os.close(fd)
                self.stale = True
                return
            self.fd = fd

    def alive(self) -> bool:
        if self.stale:
            return group_alive(self.pid, self.expected[0])
        if self.fd is not None:
            # A process pidfd (flags=0, not PIDFD_THREAD) becomes readable only
            # after the LAST thread exits, including a zombie leader's workers.
            return not bool(select.select([self.fd], [], [], 0)[0])
        return group_alive(self.pid, self.expected[0])

    def send(self, sig: int) -> None:
        if self.stale:
            return
        if self.fd is not None:
            signal.pidfd_send_signal(self.fd, sig)
        elif identity(self.pid) == self.expected:
            os.kill(self.pid, sig)

    def close(self) -> None:
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--yes', action='store_true', help='Stop now; unsaved work is lost')
    parser.add_argument('--list', action='store_true', help='List only (the default)')
    args = parser.parse_args()
    found = targets()
    for pid, (_, executable) in sorted(found.items()):
        print(f'{pid}: {executable}')
    if not found:
        print('No identifiable Wine processes in this container. / 沒有可確認屬於此容器的 Wine 程序。')
        return 0
    if args.list or not args.yes:
        print('Use --yes to stop these Wine/Proton processes. Unsaved work will be lost.')
        return 0
    print('Stopping Wine/Proton. Unsaved work may be lost. Native Steam and X11 are preserved.', flush=True)
    # Terminating the servers normally ends their Windows clients too. Include
    # loaders so a client hung before registering with wineserver can be stopped.
    tracked = [TrackedProcess(pid, expected) for pid, expected in found.items()]
    try:
        for sig, wait_seconds in ((signal.SIGTERM, 5), (signal.SIGKILL, 2)):
            for process in tracked:
                try:
                    process.send(sig)
                except ProcessLookupError:
                    pass
                except OSError as exc:
                    print(f'Cannot stop PID {process.pid}: {exc}')
            deadline = time.monotonic() + wait_seconds
            while time.monotonic() < deadline:
                if not any(process.alive() for process in tracked):
                    print('Selected Wine processes and all their threads stopped. / 已確認選定 Wine 程序及所有執行緒停止。')
                    return 0
                time.sleep(0.2)
        remaining = [process.pid for process in tracked if process.alive()]
        print(f'Could not stop these processes / 仍有程序或執行緒未退出: {remaining}')
        return 1
    finally:
        for process in tracked:
            process.close()


if __name__ == '__main__':
    raise SystemExit(main())
