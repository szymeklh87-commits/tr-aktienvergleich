"""Gemeinsamer Kursstichtag D (Abschnitt 8, „Globale Vergleichbarkeit“).

D ist der neueste Kalendertag, an dem alle unterstützten Börsen mit einer Sitzung an
diesem Tag ihre reguläre Sitzung beendet haben – zuzüglich einer Nachlieferungsfrist.
Schlusszeiten stammen aus den Börsenkalendern (Zeitzonen, verkürzte Handelstage);
es gibt keine feste Annahme wie „US-Schluss immer 22 Uhr“.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from ..providers.base import CalendarProvider
from ..util.timeutil import date_to_day, day_to_date


@dataclass
class CutoffResult:
    cutoff_day: int
    markets_with_session: list[str]
    markets_closed: list[str]
    checked_days: list[dict]


def determine_cutoff(
    codes: set[str],
    calendars: CalendarProvider,
    now_utc: dt.datetime,
    *,
    grace_minutes: int = 60,
    lookback_days: int = 14,
) -> CutoffResult:
    usable = sorted(c for c in codes if calendars.available(c))
    if not usable:
        raise RuntimeError("Kein verfügbarer Börsenkalender")
    grace = dt.timedelta(minutes=grace_minutes)
    start = (now_utc + dt.timedelta(days=1)).date()
    checked: list[dict] = []
    for offset in range(lookback_days + 1):
        candidate = start - dt.timedelta(days=offset)
        day = date_to_day(candidate)
        open_markets, pending = [], []
        for code in usable:
            close = calendars.session_close_utc(code, day)
            if close is None:
                continue
            open_markets.append(code)
            if close + grace > now_utc:
                pending.append(code)
        checked.append({"day": candidate.isoformat(), "open": open_markets, "pending": pending})
        if open_markets and not pending:
            closed = [c for c in usable if c not in open_markets]
            return CutoffResult(day, open_markets, closed, checked)
    raise RuntimeError("Kein abgeschlossener Börsentag im Rückblickzeitraum gefunden")


def session_final_checker(calendars: CalendarProvider, code: str, now_utc: dt.datetime, grace_minutes: int = 60):
    """Funktion day → True, wenn die Sitzung abgeschlossen ist (laufender Tag ersetzt keinen Schlusskurs)."""
    grace = dt.timedelta(minutes=grace_minutes)

    def final(day: int) -> bool:
        close = calendars.session_close_utc(code, day)
        if close is None:
            # Kein regulärer Sitzungstag laut Kalender: Kurs wird später als Nicht-Handelstag verworfen.
            return day_to_date(day) < now_utc.date()
        return close + grace <= now_utc

    return final
