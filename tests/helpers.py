"""Hilfen für synthetische Testdaten (SYNTHETISCH – keine echten Kurse)."""

from __future__ import annotations

import datetime as dt
from typing import Callable, Iterable

import numpy as np

from traktien.analytics.engine import InstrumentData
from traktien.util.isin import make_isin
from traktien.util.timeutil import date_to_day


def weekday_sessions(start: dt.date, end: dt.date, holidays: Iterable[dt.date] = ()) -> np.ndarray:
    """Synthetischer Testkalender: Montag–Freitag ohne angegebene Feiertage."""
    skip = {date_to_day(d) for d in holidays}
    days = []
    current = start
    while current <= end:
        if current.weekday() < 5:
            day = date_to_day(current)
            if day not in skip:
                days.append(day)
        current += dt.timedelta(days=1)
    return np.array(days, dtype=np.int64)


def test_isin(number: int, prefix: str = "ZZ") -> str:
    """Formal gültige Test-ISIN mit nicht vergebenem Länderpräfix ZZ."""
    return make_isin(f"{prefix}{number:09d}")


def make_instrument(
    isin: str,
    sessions: np.ndarray,
    price_fn: Callable[[int], float],
    *,
    volume: float | None = 1000.0,
    drop: Iterable[int] = (),
    start_index: int = 0,
    **kwargs,
) -> InstrumentData:
    """Baut eine Reihe über ``sessions[start_index:]``; ``drop`` entfernt Sitzungstage."""
    drop_set = set(int(d) for d in drop)
    days, close, vol = [], [], []
    for k, day in enumerate(sessions[start_index:]):
        if int(day) in drop_set:
            continue
        days.append(int(day))
        close.append(float(price_fn(k)))
        vol.append(np.nan if volume is None else float(volume))
    return InstrumentData(
        isin=isin,
        sessions=sessions,
        days=np.array(days, dtype=np.int64),
        close=np.array(close, dtype=np.float64),
        volume=np.array(vol, dtype=np.float64),
        **kwargs,
    )


def day(year: int, month: int, dayno: int) -> int:
    return date_to_day(dt.date(year, month, dayno))
