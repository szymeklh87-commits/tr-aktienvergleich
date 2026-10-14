"""Börsenkalender.

Produktiv: ``exchange_calendars`` (gepflegte Bibliothek mit Feiertagen, verkürzten
Handelstagen und Sitzungszeiten vieler Börsen). Eine allgemeine Montag-bis-Freitag-
Liste genügt international nicht und wird im Produktivbetrieb nicht verwendet.

Für Tests und den gekennzeichneten Demomodus gibt es ``StaticCalendarProvider`` mit
expliziten Sitzungslisten.
"""

from __future__ import annotations

import datetime as dt
from functools import lru_cache
from zoneinfo import ZoneInfo

import numpy as np

from ..util.timeutil import UTC, date_to_day, day_to_date


class ExchangeCalendarsProvider:
    """Adapter für die Bibliothek exchange_calendars (Version wird im Manifest vermerkt)."""

    def __init__(self) -> None:
        import exchange_calendars as xcals  # noqa: WPS433 - optionale Abhängigkeit

        self._xcals = xcals
        self._names = set(xcals.get_calendar_names(include_aliases=True))
        self._cache: dict[str, object] = {}

    def version(self) -> str:
        return f"exchange_calendars {getattr(self._xcals, '__version__', '?')}"

    def available(self, code: str) -> bool:
        return code in self._names

    def _calendar(self, code: str):
        if code not in self._cache:
            self._cache[code] = self._xcals.get_calendar(code)
        return self._cache[code]

    def sessions(self, code: str, start_day: int, end_day: int) -> np.ndarray:
        import pandas as pd

        cal = self._calendar(code)
        first = max(day_to_date(start_day), cal.first_session.date())
        last = min(day_to_date(end_day), cal.last_session.date())
        if first > last:
            return np.empty(0, dtype=np.int64)
        index = cal.sessions_in_range(pd.Timestamp(first), pd.Timestamp(last))
        return np.array([date_to_day(ts.date()) for ts in index], dtype=np.int64)

    def session_close_utc(self, code: str, day: int) -> dt.datetime | None:
        import pandas as pd

        cal = self._calendar(code)
        label = pd.Timestamp(day_to_date(day))
        if not cal.is_session(label):
            return None
        close = cal.session_close(label)
        if close.tzinfo is None:
            close = close.tz_localize("UTC")
        return close.to_pydatetime().astimezone(UTC)

    def session_open_utc(self, code: str, day: int) -> dt.datetime | None:
        """Beginn der regulären Sitzung (für den Zwischenstand: Hat die Börse heute schon gehandelt?)."""
        import pandas as pd

        cal = self._calendar(code)
        label = pd.Timestamp(day_to_date(day))
        if not cal.is_session(label):
            return None
        opening = cal.session_open(label)
        if opening.tzinfo is None:
            opening = opening.tz_localize("UTC")
        return opening.to_pydatetime().astimezone(UTC)


class StaticCalendarProvider:
    """Explizite Sitzungslisten (Tests, Demo). Schlusszeit als lokale Uhrzeit je Kalender."""

    def __init__(
        self,
        sessions: dict[str, np.ndarray],
        closes: dict[str, tuple[str, dt.time]],
        label: str = "statisch",
        opens: dict[str, dt.time] | None = None,
    ) -> None:
        self._sessions = {code: np.asarray(values, dtype=np.int64) for code, values in sessions.items()}
        self._closes = closes
        self._opens = opens or {}
        self._label = label

    def version(self) -> str:
        return f"static-calendar ({self._label})"

    def available(self, code: str) -> bool:
        return code in self._sessions

    def sessions(self, code: str, start_day: int, end_day: int) -> np.ndarray:
        values = self._sessions[code]
        return values[(values >= start_day) & (values <= end_day)]

    def session_close_utc(self, code: str, day: int) -> dt.datetime | None:
        values = self._sessions[code]
        pos = int(np.searchsorted(values, day))
        if pos >= len(values) or int(values[pos]) != day:
            return None
        tz_name, close_time = self._closes[code]
        local = dt.datetime.combine(day_to_date(day), close_time, tzinfo=ZoneInfo(tz_name))
        return local.astimezone(UTC)

    def session_open_utc(self, code: str, day: int) -> dt.datetime | None:
        """Sitzungsbeginn als lokale Uhrzeit je Kalender (Standard 09:00 Uhr)."""
        if self.session_close_utc(code, day) is None:
            return None
        tz_name, _ = self._closes[code]
        local = dt.datetime.combine(day_to_date(day), self._opens.get(code, dt.time(9, 0)), tzinfo=ZoneInfo(tz_name))
        return local.astimezone(UTC)


def weekday_holiday_sessions(start: dt.date, end: dt.date, holidays: set[dt.date]) -> np.ndarray:
    """Hilfsfunktion für den Demokalender (synthetisch, ausdrücklich nicht produktiv)."""
    days = []
    current = start
    while current <= end:
        if current.weekday() < 5 and current not in holidays:
            days.append(date_to_day(current))
        current += dt.timedelta(days=1)
    return np.array(days, dtype=np.int64)


@lru_cache(maxsize=1)
def production_calendars() -> ExchangeCalendarsProvider:
    return ExchangeCalendarsProvider()
