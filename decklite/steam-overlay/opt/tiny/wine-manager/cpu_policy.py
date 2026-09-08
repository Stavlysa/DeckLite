"""Portable, data-only CPU preference handling; no GTK dependency."""
from __future__ import annotations

import os
from pathlib import Path
import re

CPU_ROOT = Path("/sys/devices/system/cpu")
CONFIG_FILE = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))) / "decklite/wine-cpu-policy"


def parse_cpu_list(value: str) -> set[int]:
    result: set[int] = set()
    for item in value.strip().split(","):
        if not re.fullmatch(r"[0-9]+(?:-[0-9]+)?", item):
            raise ValueError("Invalid CPU list")
        ends = [int(n) for n in item.split("-")]
        first, last = ends[0], ends[-1]
        if not 0 <= first <= last < 1024:
            raise ValueError("CPU ID outside supported affinity mask")
        result.update(range(first, last + 1))
    return result


def load_preference(path: Path = CONFIG_FILE) -> tuple[str, set[int]]:
    try:
        value = path.read_text(encoding="ascii").strip()
        if value in {"big", "all"}:
            return value, set()
        if value.startswith("custom:"):
            return "custom", parse_cpu_list(value[7:])
    except (OSError, ValueError, UnicodeError):
        pass
    return "big", set()


def save_preference(mode: str, selected: set[int], path: Path = CONFIG_FILE) -> None:
    if mode not in {"big", "all", "custom"}:
        raise ValueError("Unknown CPU mode")
    value = mode
    if mode == "custom":
        value += ":" + ",".join(str(n) for n in sorted(selected))
        parse_cpu_list(value[7:])  # Reject empty/out-of-range sets.
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(value + "\n", encoding="ascii")
    temporary.replace(path)


def inventory(root: Path = CPU_ROOT, status_path: Path | None = None) -> tuple[list[dict], set[int], bool]:
    try:
        allowed = set(os.sched_getaffinity(0))
    except (AttributeError, OSError):
        allowed = set(range(os.cpu_count() or 1))
    # sched_getaffinity can omit temporarily inactive cores on Android while
    # procfs still reports them in the permitted mask. Do not disable their
    # checkboxes or mislabel the prime core as a permanently unavailable CPU.
    if status_path is None and root == CPU_ROOT:
        status_path = Path('/proc/self/status')
    if status_path is not None:
        try:
            for line in status_path.read_text().splitlines():
                if line.startswith('Cpus_allowed_list:'):
                    allowed |= parse_cpu_list(line.split(':', 1)[1].strip())
                    break
        except (OSError, ValueError):
            pass
    try:
        present = parse_cpu_list((root / "present").read_text())
    except (OSError, ValueError):
        present = allowed.copy()
    try:
        online = parse_cpu_list((root / "online").read_text())
    except (OSError, ValueError):
        online = allowed.copy()
    usable = present & online & allowed
    rows = []
    for cpu in sorted(present):
        row = {"id": cpu, "available": cpu in usable, "capacity": None, "frequency": None}
        for key, relative in (("capacity", "cpu_capacity"), ("frequency", "cpufreq/cpuinfo_max_freq")):
            try:
                value = int((root / f"cpu{cpu}" / relative).read_text().strip())
                row[key] = value if value > 0 else None
            except (OSError, ValueError):
                pass
        rows.append(row)
    big = usable.copy()
    detected = False
    for key in ("capacity", "frequency"):
        scores = [row[key] for row in rows]
        if scores and all(value is not None for value in scores) and min(scores) != max(scores):
            selected = {row["id"] for row in rows if row[key] > min(scores) and row["available"]}
            if selected:
                big, detected = selected, True
                break
    return rows, big, detected
