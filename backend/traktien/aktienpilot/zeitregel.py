"""Ausführungsprofile und Zeitregeln (Abschnitt 13).

Gespeichert werden Datenzeitpunkt, Berechnungszeit, Veröffentlichungszeit, früheste Ausführung und Ablauf. Ein Signal wird nie
zu einem Kurs ausgeführt, der vor seiner Veröffentlichung lag (verspäteter GitHub-Lauf, bereits geöffnete Börse).

* **TAGESDATEN** – abgeschlossene Tagesdaten; Ausführung zur Eröffnung der ersten Sitzung der Börse der Aktie, deren Beginn
  nach der Veröffentlichung liegt. Keine 15-Minuten-Sperre.
* **VERZOEGERTER-EINSTIEG** – neue Käufe frühestens 15 Minuten nach Eröffnung. Mit Tageskerzen lässt sich der Kurs 15 Minuten
  nach Eröffnung nicht bestimmen: In Backtest und PAPER gilt dieselbe Zeitregel, die Ausführung ist ohne Intraday-Daten aber
  „nicht simulierbar“ (keine erfundene Ausführung) und das Profil nicht für Echtgeld freigabefähig.
* **FOLGETAG-SCHLUSS** – Ausführung zum Schluss der ersten Sitzung, deren Ende nach der Veröffentlichung liegt; mit
  Tagesdaten testbar. Der Unterschied zum TR-Handelsplatz wird als konservativer Aufschlag gerechnet (``kosten``).

Ohne Börsenkalender gilt eine konservative Ersatzregel: die erste Sitzung mit Kurs an einem Kalendertag *nach* dem Tag der
Veröffentlichung.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from zoneinfo import ZoneInfo

import numpy as np

from ..util.timeutil import UTC, date_to_day, day_to_date
from .markt import Series

PROFILE_DAILY = "TAGESDATEN"
PROFILE_DELAYED = "VERZOEGERTER-EINSTIEG"
PROFILE_NEXT_CLOSE = "FOLGETAG-SCHLUSS"


@dataclass(frozen=True)
class Timing:
    profile: str
    data_day: int  # letzter Datenstichtag der Entscheidung
    computed_at: dt.datetime
    published_at: dt.datetime
    session_day: int | None  # Sitzung der frühesten Ausführung
    earliest: dt.datetime | None  # frühester Ausführungszeitpunkt
    expires: dt.datetime | None  # Ablauf (Ende der letzten gültigen Sitzung)
    price_point: str | None  # "open" | "close" | None
    simulatable: bool
    reason: str | None = None

    def as_dict(self) -> dict:
        def iso(value: dt.datetime | None) -> str | None:
            return None if value is None else value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

        return {
            "profil": self.profile,
            "datentag": int(self.data_day),
            "berechnet_am": iso(self.computed_at),
            "veroeffentlicht_am": iso(self.published_at),
            "sitzung": None if self.session_day is None else day_to_date(self.session_day).isoformat(),
            "frueheste_ausfuehrung": iso(self.earliest),
            "ablauf": iso(self.expires),
            "kurs": self.price_point,
            "simulierbar": self.simulatable,
            "grund": self.reason,
        }


def backtest_publication(data_day: int, hhmm_minutes: int, tz: str = "Europe/Berlin") -> dt.datetime:
    """Angenommene Veröffentlichung im Backtest: am Kalendertag nach dem Datenstichtag zur konfigurierten Uhrzeit."""
    local = dt.datetime.combine(day_to_date(data_day + 1), dt.time(hhmm_minutes // 60, hhmm_minutes % 60), tzinfo=ZoneInfo(tz))
    return local.astimezone(UTC)


def _sessions_after(series: Series, calendars, first_day: int, count: int = 12) -> list[int]:
    """Die nächsten Sitzungstage ab ``first_day`` laut Börsenkalender (Ersatz: Tage mit Kurs)."""
    if calendars is not None and series.calendar and calendars.available(series.calendar):
        sessions = calendars.sessions(series.calendar, first_day, first_day + 40)
        return [int(d) for d in sessions[:count]]
    later = series.days[series.days >= first_day]
    return [int(d) for d in later[:count]]


def plan(series: Series, profile: str, data_day: int, computed_at: dt.datetime, published_at: dt.datetime, calendars,
         *, valid_sessions: int = 1, delay_minutes: int = 15) -> Timing:
    """Früheste Ausführung und Ablauf eines Signals nach Profil (siehe Modulbeschreibung)."""
    published_at = published_at.astimezone(UTC)
    has_calendar = calendars is not None and bool(series.calendar) and calendars.available(series.calendar)
    start_day = min(data_day + 1, date_to_day(published_at.date()))
    candidates = _sessions_after(series, calendars, start_day)

    def session_bounds(day: int) -> tuple[dt.datetime | None, dt.datetime | None]:
        if has_calendar:
            return calendars.session_open_utc(series.calendar, day), calendars.session_close_utc(series.calendar, day)
        return None, None

    chosen = None
    earliest = None
    point = None
    for day in candidates:
        if day <= data_day:
            continue
        opening, closing = session_bounds(day)
        if not has_calendar:
            # Ersatzregel ohne Kalender: nur Sitzungen nach dem Kalendertag der Veröffentlichung
            if day <= date_to_day(published_at.date()):
                continue
            chosen = day
            earliest = dt.datetime.combine(day_to_date(day), dt.time(0, 0), tzinfo=UTC)
            point = "close" if profile == PROFILE_NEXT_CLOSE else "open"
            break
        if opening is None or closing is None:
            continue
        if profile == PROFILE_DAILY and opening >= published_at:
            chosen, earliest, point = day, opening, "open"
            break
        if profile == PROFILE_DELAYED and opening + dt.timedelta(minutes=delay_minutes) >= published_at:
            chosen, earliest, point = day, opening + dt.timedelta(minutes=delay_minutes), None
            break
        if profile == PROFILE_NEXT_CLOSE and closing > published_at:
            chosen, earliest, point = day, max(published_at, opening), "close"
            break
    if chosen is None:
        return Timing(profile, data_day, computed_at, published_at, None, None, None, None, False, "keine erreichbare Sitzung im Kalender")
    # Ablauf: Ende der letzten gültigen Sitzung (gueltigkeit_sitzungen ab der ersten erreichbaren)
    later = [d for d in candidates if d >= chosen][:max(1, valid_sessions)]
    last = later[-1]
    _, last_close = session_bounds(last)
    expires = last_close or dt.datetime.combine(day_to_date(last), dt.time(23, 59), tzinfo=UTC)
    if profile == PROFILE_DELAYED:
        return Timing(profile, data_day, computed_at, published_at, chosen, earliest, expires, None, False,
                      "Kurs 15 Minuten nach Eröffnung ist mit Tageskerzen nicht bestimmbar – ohne Intraday-Daten nicht simulierbar")
    return Timing(profile, data_day, computed_at, published_at, chosen, earliest, expires, point, True)


def bar_for(series: Series, timing: Timing) -> int | None:
    """Index der Kerze, deren Kurs (Eröffnung bzw. Schluss) die Ausführung bestimmt; None, wenn sie (noch) fehlt."""
    if timing.session_day is None:
        return None
    return series.index_of(timing.session_day)


def is_due(timing: Timing, now: dt.datetime) -> bool:
    """Ist die Ausführungssitzung abgeschlossen (Kerze vollständig)? Erst dann rechnet der Simulator die Ausführung."""
    return timing.expires is not None and now.astimezone(UTC) >= timing.expires


def weekday_of(day: int) -> int:
    return day_to_date(day).weekday()


def next_trading_day(days: np.ndarray, day: int) -> int | None:
    k = int(np.searchsorted(days, day, side="right"))
    return int(days[k]) if k < len(days) else None
