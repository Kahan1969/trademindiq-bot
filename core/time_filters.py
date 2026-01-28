from __future__ import annotations

from datetime import datetime, time

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None  # type: ignore


def is_between(start_hhmm: str, end_hhmm: str, tz: str = "UTC", now: datetime | None = None) -> bool:
    """Return True if local time in tz is within [start,end) on the same day."""
    if ZoneInfo is None:
        now_local = now or datetime.now()
    else:
        now_local = now or datetime.now(tz=ZoneInfo(tz))

    sh, sm = [int(x) for x in start_hhmm.split(":", 1)]
    eh, em = [int(x) for x in end_hhmm.split(":", 1)]
    start_t = time(sh, sm)
    end_t = time(eh, em)
    cur_t = now_local.time()

    return start_t <= cur_t < end_t


def is_us_open_2h(now: datetime | None = None) -> bool:
    """US equities first 2 hours of RTH: 09:30–11:30 US/Eastern."""
    return is_between("09:30", "11:30", tz="US/Eastern", now=now)
