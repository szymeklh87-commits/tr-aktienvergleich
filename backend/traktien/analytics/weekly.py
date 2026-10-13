"""Wochenwerte je Aktie für die Umschichtungs-Regel (``rotation-v1``).

Die Regel prüft ihre Kandidaten an Wochenenden. Je Aktie und Woche wird verdichtet:

* ``close``     letzter splitbereinigter Schlusskurs der Woche (Kurseinheit der Notierung)
* ``first_close`` Schlusskurs der ersten Sitzung der Woche mit Kurs (``first_day`` = deren Tag);
                Ausführungskurs einer am Freitag zuvor beschlossenen Umschichtung
* ``turnover``  Summe Schlusskurs × Volumen über die Sitzungen mit Kurs und Volumen
                (Kurseinheit; unabhängig von Splitbereinigungen, weil Kurs und Volumen
                gegenläufig bereinigt werden)
* ``with_data`` Sitzungen mit Kurs und Volumen, ``positive`` davon mit Volumen > 0
* ``observed``  Sitzungen mit Kurs, ``sessions`` Sitzungen laut Börsenkalender
* ``jump``      größte Tagesbewegung |ln(Kurs_t / Kurs_vorher)| in dieser Woche
                (einschließlich des Übergangs von der Vorwoche)

Eine Woche reicht von ``Wochenende − 7`` (ausschließlich) bis ``Wochenende`` (einschließlich).
Für den Rückblick-Test sind die Wochenenden Freitage; für den Tagesvorschlag endet die jüngste
„Woche“ am Kursstichtag, damit dieselbe Regel auf dem neuesten Stand rechnet.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


def friday_of(day: int) -> int:
    """Freitag der Kalenderwoche (Montag–Sonntag), in der ``day`` liegt. Tag 0 = 1.1.1970 (Donnerstag)."""
    weekday = (int(day) + 3) % 7  # Montag = 0
    return int(day) - weekday + 4


def fridays(first_day: int, last_day: int) -> np.ndarray:
    """Alle Freitage mit ``first_day ≤ Freitag ≤ last_day``."""
    start = friday_of(first_day)
    if start < first_day:
        start += 7
    if start > last_day:
        return np.empty(0, dtype=np.int64)
    return np.arange(start, last_day + 1, 7, dtype=np.int64)


def rolling_week_ends(end_day: int, weeks: int) -> np.ndarray:
    """``weeks`` Wochenenden im Abstand von 7 Tagen, das jüngste am ``end_day`` (aufsteigend)."""
    return np.arange(end_day - 7 * (weeks - 1), end_day + 1, 7, dtype=np.int64)


FIELDS = ("week_ends", "close", "turnover", "with_data", "positive", "observed", "sessions", "jump", "first_close", "first_day")


@dataclass
class WeekAggregates:
    week_ends: np.ndarray
    close: np.ndarray
    turnover: np.ndarray
    with_data: np.ndarray
    positive: np.ndarray
    observed: np.ndarray
    sessions: np.ndarray
    jump: np.ndarray
    first_close: np.ndarray
    first_day: np.ndarray  # −1 = keine Sitzung mit Kurs

    def select(self, keep: slice | np.ndarray) -> "WeekAggregates":
        return WeekAggregates(*(getattr(self, name)[keep] for name in FIELDS))

    def __len__(self) -> int:
        return int(len(self.week_ends))


def aggregate_weeks(
    days: np.ndarray,
    close: np.ndarray,
    volume: np.ndarray,
    week_ends: np.ndarray,
    *,
    sessions: np.ndarray | None = None,
) -> WeekAggregates:
    """Verdichtet Tageskurse (aufsteigend, nur echte Sitzungen) zu Wochenwerten an ``week_ends``.

    Fehlende Kurse werden nicht ersetzt: Eine Woche ohne Kurs hat ``close = NaN``. Volumen ohne
    Angabe (NaN) zählt nicht als null, sondern fehlt in ``with_data``.
    """
    week_ends = np.asarray(week_ends, dtype=np.int64)
    w = len(week_ends)
    out = WeekAggregates(
        week_ends=week_ends,
        close=np.full(w, np.nan),
        turnover=np.zeros(w),
        with_data=np.zeros(w, dtype=np.int32),
        positive=np.zeros(w, dtype=np.int32),
        observed=np.zeros(w, dtype=np.int32),
        sessions=np.zeros(w, dtype=np.int32),
        jump=np.zeros(w),
        first_close=np.full(w, np.nan),
        first_day=np.full(w, -1, dtype=np.int64),
    )
    if w == 0:
        return out
    days = np.asarray(days, dtype=np.int64)
    close = np.asarray(close, dtype=np.float64)
    volume = np.asarray(volume, dtype=np.float64) if volume is not None else np.full(len(days), np.nan)
    valid = np.isfinite(close) & (close > 0)
    days, close, volume = days[valid], close[valid], volume[valid]

    def bucket(values: np.ndarray) -> np.ndarray:
        """Index der Woche je Tag; −1 außerhalb des Rasters."""
        idx = np.searchsorted(week_ends, values, side="left")
        inside = (idx < w) & (values > (week_ends[np.minimum(idx, w - 1)] - 7))
        return np.where(inside, idx, -1)

    if sessions is not None and len(sessions):
        s_idx = bucket(np.asarray(sessions, dtype=np.int64))
        np.add.at(out.sessions, s_idx[s_idx >= 0], 1)
    if len(days) == 0:
        return out
    b = bucket(days)
    inside = b >= 0
    np.add.at(out.observed, b[inside], 1)
    has_volume = inside & np.isfinite(volume)
    np.add.at(out.with_data, b[has_volume], 1)
    np.add.at(out.positive, b[has_volume & (volume > 0)], 1)
    np.add.at(out.turnover, b[has_volume], close[has_volume] * volume[has_volume])
    # letzter Kurs je Woche (Tage sind aufsteigend): erstes Vorkommen in umgekehrter Reihenfolge
    b_in, c_in, d_in = b[inside], close[inside], days[inside]
    weeks_seen, first_reversed = np.unique(b_in[::-1], return_index=True)
    out.close[weeks_seen] = c_in[::-1][first_reversed]
    # erster Kurs je Woche
    weeks_seen, first_index = np.unique(b_in, return_index=True)
    out.first_close[weeks_seen] = c_in[first_index]
    out.first_day[weeks_seen] = d_in[first_index]
    if len(close) > 1:
        moves = np.abs(np.diff(np.log(close)))
        later = b[1:]
        ok = later >= 0
        np.maximum.at(out.jump, later[ok], moves[ok])
    return out
