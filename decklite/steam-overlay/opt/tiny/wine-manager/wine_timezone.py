"""Fixed UTC offsets for Wine children; independent of UI/Windows language."""
from pathlib import Path

# Minutes east of Greenwich. Include half/quarter-hour civil offsets as well
# as every full hour; these are fixed offsets, not city/DST rules.
OFFSETS = tuple(sorted(set(range(-720, 841, 60)) | {
    -570, -210, 210, 270, 330, 345, 390, 525, 570, 630, 765,
}))
TIMEZONES = tuple(str(minutes) for minutes in OFFSETS)
DEFAULT_TIMEZONE = "0"


def timezone_label(value: str) -> str:
    if value not in TIMEZONES:
        raise ValueError("Unsupported UTC offset")
    if value == "0":
        return "UTC+00:00 (GMT / Greenwich)"
    minutes = int(value)
    return f"UTC{'+' if minutes >= 0 else '-'}{abs(minutes) // 60:02}:{abs(minutes) % 60:02}"


def timezone_env(value: str) -> str:
    if value not in TIMEZONES:
        raise ValueError("Unsupported UTC offset")
    minutes = int(value)
    if not minutes:
        return "UTC0"
    # POSIX TZ signs are the opposite of user-facing UTC offsets.
    return f"UTC{'-' if minutes > 0 else '+'}{abs(minutes) // 60}:{abs(minutes) % 60:02}"


def load_timezone(path: Path) -> str:
    try:
        value = path.read_text(encoding="ascii").strip()
        return value if value in TIMEZONES else DEFAULT_TIMEZONE
    except (OSError, UnicodeError):
        return DEFAULT_TIMEZONE


def save_timezone(value: str, path: Path) -> None:
    if value not in TIMEZONES:
        raise ValueError("Unsupported UTC offset")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(value + "\n", encoding="ascii", newline="\n")
    temporary.replace(path)
