"""Quiet-hours guard (D-16, Pitfall 8): scan commands refuse 00:15-06:00 UTC unless --force."""

from datetime import UTC, datetime, time


class QuietHours(Exception):
    pass


def utcnow() -> datetime:
    return datetime.now(UTC)


def _parse(hhmm: str) -> time:
    h, m = hhmm.split(":")
    return time(int(h), int(m))


def in_quiet_hours(now: datetime | None = None, start: str = "00:15", end: str = "06:00") -> bool:
    now = (now or utcnow()).astimezone(UTC)
    t, s, e = now.time(), _parse(start), _parse(end)
    if s <= e:
        return s <= t < e
    return t >= s or t < e  # window wrapping midnight


def check(cfg: dict, force: bool) -> str | None:
    """Raise QuietHours inside the window without force; return an override note with force."""
    qh = (cfg or {}).get("quiet_hours") or {}
    start, end = qh.get("start", "00:15"), qh.get("end", "06:00")
    now = utcnow()
    if not in_quiet_hours(now, start, end):
        return None
    if not force:
        raise QuietHours(
            f"refused: {now:%H:%M} UTC is inside quiet hours {start}-{end} UTC (use --force)"
        )
    return f"quiet_hours_override at {now:%Y-%m-%dT%H:%M:%SZ}"
