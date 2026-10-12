"""Zeit- und Datumshilfen.

Intern werden Zeitpunkte in UTC geführt. Börsensitzungen sind Kalenderdaten in der
Zeitzone der jeweiligen Börse und werden kompakt als "Epochentag" gespeichert
(Tage seit 1970-01-01). Ein Epochentag ist eindeutig und nicht ortsabhängig.
"""

from __future__ import annotations

import datetime as _dt
from zoneinfo import ZoneInfo

EPOCH = _dt.date(1970, 1, 1)
UTC = _dt.timezone.utc
BERLIN = ZoneInfo("Europe/Berlin")


def date_to_day(value: _dt.date) -> int:
    return (value - EPOCH).days


def day_to_date(day: int) -> _dt.date:
    return EPOCH + _dt.timedelta(days=int(day))


def day_to_iso(day: int | None) -> str | None:
    if day is None:
        return None
    return day_to_date(day).isoformat()


def iso_to_day(text: str) -> int:
    return date_to_day(_dt.date.fromisoformat(text))


def utc_now() -> _dt.datetime:
    return _dt.datetime.now(tz=UTC)


def iso_utc(value: _dt.datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        raise ValueError("Zeitpunkt ohne Zeitzone ist mehrdeutig")
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_iso_utc(text: str | None) -> _dt.datetime | None:
    if not text:
        return None
    value = _dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
    if value.tzinfo is None:
        raise ValueError("Zeitpunkt ohne Zeitzone ist mehrdeutig: " + text)
    return value.astimezone(UTC)


def session_date_from_timestamp(ts: int | float, tz_name: str) -> _dt.date:
    """Sitzungsdatum eines Unix-Zeitstempels in der Börsenzeitzone."""
    return _dt.datetime.fromtimestamp(float(ts), tz=ZoneInfo(tz_name)).date()
