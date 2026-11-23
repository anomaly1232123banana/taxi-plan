import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

SYD = ZoneInfo("Australia/Sydney")
# Shift minutes = minutes since 12:00 on the shift date (0..900); the last block includes 900.
BLOCKS = [(0, 120), (120, 240), (240, 360), (360, 480), (480, 600), (600, 720), (720, 840), (840, 900)]
SHIFT_END = 900


@dataclass
class Candidate:
    id: str
    kind: str  # "event" | "race" | "office"
    name: str
    venue: str
    address: str
    area: str | None
    lat: float | None
    lon: float | None
    source_url: str
    start: datetime | None = None
    exit: datetime | None = None
    info: str = ""
    size: int | None = None
    median_age: float | None = None
    age_lo: int | None = None
    age_hi: int | None = None
    pays: float | None = None
    spend: float | None = None
    wait: str = ""
    desc: str = ""
    score: int = 0


def shift_slot(t: datetime) -> tuple[date, int] | None:
    """Shift date and shift minute for an aware time, or None outside the shift / on a Sunday shift."""
    t = t.astimezone(SYD)
    if t.hour >= 12:
        d, minute = t.date(), (t.hour - 12) * 60 + t.minute
    elif t.hour < 3 or (t.hour == 3 and t.minute == 0):
        d, minute = t.date() - timedelta(days=1), 720 + t.hour * 60 + t.minute
    else:
        return None
    return None if d.weekday() == 6 else (d, minute)


def shift_date(t: datetime) -> date:
    """Shift date of a clock time: before 03:00 still belongs to the previous day's shift."""
    t = t.astimezone(SYD)
    return t.date() - timedelta(days=1) if t.hour < 3 else t.date()


def block_index(minute: int) -> int:
    return min(minute // 120, len(BLOCKS) - 1)


def working_days(start: date, n: int = 5) -> list[date]:
    days, d = [], start
    while len(days) < n:
        if d.weekday() != 6:
            days.append(d)
        d += timedelta(days=1)
    return days


def at_shift(d: date, hm: str) -> datetime:
    h, m = map(int, hm.split(":"))
    return datetime(d.year, d.month, d.day, h, m, tzinfo=SYD) + (timedelta(days=1) if h < 12 else timedelta())


def exit_after(start: datetime, hm: str) -> datetime:
    h, m = map(int, hm.split(":"))
    s = start.astimezone(SYD)
    out = datetime(s.year, s.month, s.day, h, m, tzinfo=SYD)
    return out + timedelta(days=1) if out < s else out


def shift_minute(hm: str) -> int:
    h, m = map(int, hm.split(":"))
    return (h * 60 + m - 720) % 1440


def hm_of(minute: int) -> str:
    return f"{(minute + 720) // 60 % 24:02d}:{minute % 60:02d}"


def fmt12(hm: str, S: dict) -> str:
    h, m = map(int, hm.split(":"))
    suffix = S["pm"] if h >= 12 else S["am"]
    return f"{h % 12 or 12}{'' if m == 0 else f':{m:02d}'}{suffix}"


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
