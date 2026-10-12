"""Qualitätsregeln: Kurssprünge, unbereinigte Splits, Fensterzulassung (Abschnitte 10 und 12).

Ein Verhältnis p_t/p_(t−1) > 3 oder < 1/3 beweist keinen Fehler, löst aber eine Prüfung
aus. Fenster, die einen ungeklärten Sprung überspannen, werden zurückgehalten. Ein
dokumentiert geprüfter Sprung kann freigegeben werden. Es wird nichts geglättet,
winsorisiert oder durch 100 geteilt.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from ..config import MethodConfig
from .codes import Status
from .metrics import PriceMetrics
from .windows import ResolvedWindow


@dataclass(frozen=True)
class SplitEvent:
    day: int
    factor: float  # Zähler/Nenner, z. B. 2.0 für einen 2:1-Split, 0.1 für 1:10-Zusammenlegung


@dataclass
class JumpReview:
    """Ergebnis der Sprungprüfung einer Reihe."""

    held_days: list[int] = field(default_factory=list)
    released_days: list[int] = field(default_factory=list)
    unadjusted_split_days: list[int] = field(default_factory=list)

    def held_array(self) -> np.ndarray:
        return np.array(sorted(set(self.held_days) | set(self.unadjusted_split_days)), dtype=np.int64)

    def released_array(self) -> np.ndarray:
        return np.array(sorted(set(self.released_days)), dtype=np.int64)


def detect_jumps(days: np.ndarray, close: np.ndarray, factor: float = 3.0) -> list[int]:
    """Tage, an denen der Schlusskurs gegenüber der vorherigen gültigen Beobachtung
    um mehr als ``factor`` gestiegen oder unter 1/``factor`` gefallen ist."""
    if len(close) < 2:
        return []
    ratios = close[1:] / close[:-1]
    mask = (ratios > factor) | (ratios < 1.0 / factor)
    return [int(d) for d in days[1:][mask]]


def detect_unadjusted_splits(
    days: np.ndarray, close: np.ndarray, splits: list[SplitEvent], min_factor: float = 1.25
) -> list[int]:
    """Prüft, ob eine gemeldete Kapitalmaßnahme in der Reihe noch unbereinigt aussieht.

    Bei korrekt splitbereinigter Reihe liegt das Verhältnis über das Ex-Datum nahe 1.
    Liegt es (logarithmisch) näher an 1/Faktor, wird das Ex-Datum zurückgehalten.
    """
    flagged: list[int] = []
    if len(days) < 2:
        return flagged
    for event in splits:
        if event.factor <= 0 or not math.isfinite(event.factor):
            flagged.append(int(event.day))
            continue
        if abs(math.log(event.factor)) < math.log(min_factor):
            continue
        i = int(np.searchsorted(days, event.day))
        if i <= 0 or i >= len(days):
            continue
        ratio = float(close[i] / close[i - 1])
        if ratio <= 0 or not math.isfinite(ratio):
            flagged.append(int(days[i]))
            continue
        distance_unadjusted = abs(math.log(ratio) - math.log(1.0 / event.factor))
        distance_adjusted = abs(math.log(ratio))
        if distance_unadjusted < distance_adjusted:
            flagged.append(int(days[i]))
    return flagged


def review_jumps(
    days: np.ndarray,
    close: np.ndarray,
    splits: list[SplitEvent],
    reviewed: dict[int, str],
    cfg: MethodConfig,
) -> JumpReview:
    """Kombiniert automatische Erkennung mit dokumentierten Prüfentscheidungen.

    ``reviewed`` bildet Epochentag → Entscheidung ("freigegeben" oder "zurueckhalten") ab.
    """
    review = JumpReview()
    for day in detect_jumps(days, close, cfg.jump_factor):
        if reviewed.get(day) == "freigegeben":
            review.released_days.append(day)
        else:
            review.held_days.append(day)
    for day in detect_unadjusted_splits(days, close, splits, cfg.split_mismatch_min_factor):
        if reviewed.get(day) == "freigegeben":
            review.released_days.append(day)
        else:
            review.unadjusted_split_days.append(day)
    return review


def zero_volume_outliers(
    days: np.ndarray,
    close: np.ndarray,
    volume: np.ndarray,
    move: float,
    reviewed: dict[int, str] | None = None,
) -> np.ndarray:
    """Tage mit starker Kursbewegung (|p_t/p_(t−1) − 1| > move) ohne belegten positiven Umsatz.

    Ein solcher Kurs ist kein belegter Handel (oft Taxe oder Altwert). Liegt er am Beginn oder
    Ende eines Fensters, bestimmt er die Rendite – das Fenster wird bis zur Prüfung
    zurückgehalten (Abschnitt 12: „Ein ungeprüfter Zero-Volume-Ausreißer darf nicht zum
    Spitzengewinner werden“). Freigaben aus ``config/pruefungen.yaml`` gelten wie bei Sprüngen.
    """
    if len(days) < 2:
        return np.empty(0, dtype=np.int64)
    reviewed = reviewed or {}
    change = np.abs(close[1:] / close[:-1] - 1.0)
    no_volume = ~(np.isfinite(volume[1:]) & (volume[1:] > 0))
    hits = days[1:][(change > move) & no_volume]
    return np.array([int(d) for d in hits if reviewed.get(int(d)) != "freigegeben"], dtype=np.int64)


def spans_any(sorted_days: np.ndarray, start_day: int, end_day: int) -> bool:
    """True, wenn ein Übergangstag d mit start < d <= end existiert."""
    if len(sorted_days) == 0:
        return False
    i = int(np.searchsorted(sorted_days, start_day, side="right"))
    return i < len(sorted_days) and int(sorted_days[i]) <= end_day


def classify_window(
    rw: ResolvedWindow,
    *,
    vol_positive: int,
    held_in_window: bool,
    metrics: PriceMetrics | None,
    cfg: MethodConfig,
) -> Status:
    """Vergibt genau einen Hauptstatus für ein aufgelöstes Fenster (Prioritätsreihenfolge)."""
    if rw.status is not None:
        return rw.status
    if rw.n_obs < cfg.min_obs_return:
        return Status.HISTORIE_ZU_KURZ
    if not cfg.min_session_coverage.satisfied(rw.n_obs, rw.n_expected):
        return Status.SITZUNGSABDECKUNG_ZU_GERING
    if held_in_window:
        return Status.KURSSPRUNG_PRUEFEN
    if not cfg.min_volume_coverage.satisfied(vol_positive, rw.n_obs):
        return Status.VOLUMEN_UNZUREICHEND
    # Ab hier: Kursrendite ist veröffentlichbar (Menge V).
    if metrics is None or rw.n_obs < cfg.min_obs_trend:
        return Status.ZU_WENIG_TAGESDATEN_TREND
    if not (metrics.r > 0.0) or metrics.m is None or not (metrics.m > 0.0):
        return Status.NICHT_STEIGEND
    if not metrics.r2_defined or metrics.r2 is None:
        return Status.TREND_NICHT_DEFINIERT
    return Status.TREND_BEWERTBAR
