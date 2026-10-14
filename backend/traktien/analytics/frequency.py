"""Häufigste Aktien und höchste Rendite 1–90 Tage (Abschnitt 34).

Eine Ergebniszelle ist (snapshot, cohort_policy, h, w). Gezählt werden ausschließlich
veröffentlichte Rangplätze des ausgewählten Snapshots; je Zelle zählt eine ISIN
höchstens einmal. Es wird nicht über mehrere Ausgabetage aufsummiert.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Mapping, Sequence

import numpy as np

from ..config import CANONICAL_WEIGHTS, POLICIES, TOP_K_VALUES
from .ranking import Ranking, WindowRanking


def cell_ranking(windows: Mapping[int, WindowRanking], policy: str, weight: int, h: int) -> Ranking:
    if policy not in POLICIES:
        raise ValueError(policy)
    return windows[h].ranking(policy, weight)


@dataclass
class Occurrence:
    h: int
    weight: int
    rank: int
    score: float
    r: float
    start_day: int
    end_day: int
    cohort_size: int
    small_field: bool


@dataclass
class InstrumentFrequency:
    idx: int
    n1: int = 0
    n3: int = 0
    n10: int = 0
    available_cells: int = 0
    distinct_windows_k: int = 0
    distinct_weights_k: int = 0
    hits_by_weight: dict[int, int] = field(default_factory=dict)
    distinct_effective_windows_k: int = 0
    occurrences: list[Occurrence] = field(default_factory=list)

    def n_k(self, k: int) -> int:
        return {1: self.n1, 3: self.n3, 10: self.n10}[k]


@dataclass
class FrequencyResult:
    policy: str
    weights: tuple[int, ...]
    windows: tuple[int, ...]
    top_k: int
    mode: str
    sort: str
    theoretical_cells: int
    valid_cells: int
    empty_cells: int
    entries: list[InstrumentFrequency]
    aggregation_version: str = "frequency-v1"

    @property
    def denominator_e(self) -> int:
        return self.valid_cells


def _sort_key(entry: InstrumentFrequency, k: int, mode: str, sort: str, isin_of: Callable[[int], str]):
    isin = isin_of(entry.idx)
    if sort == "distinct_windows":
        return (-entry.distinct_windows_k, -entry.n_k(k), -entry.n1, isin)
    if mode == "single":
        if k == 10:
            return (-entry.n10, -entry.n3, -entry.n1, isin)
        if k == 3:
            return (-entry.n3, -entry.n1, -entry.n10, isin)
        return (-entry.n1, -entry.n3, -entry.n10, isin)
    if k == 10:
        return (-entry.n10, -entry.distinct_windows_k, -entry.n3, -entry.n1, isin)
    if k == 3:
        return (-entry.n3, -entry.distinct_windows_k, -entry.n1, -entry.n10, isin)
    return (-entry.n1, -entry.distinct_windows_k, -entry.n3, -entry.n10, isin)


def aggregate_frequency(
    windows: Mapping[int, WindowRanking],
    *,
    policy: str,
    weights: Sequence[int],
    window_days: Sequence[int],
    top_k: int,
    r_matrix: np.ndarray,
    start_matrix: np.ndarray,
    cutoff_day: int,
    isin_of: Callable[[int], str],
    sort: str = "occurrences",
    end_days: np.ndarray | None = None,
) -> FrequencyResult:
    """Zählt Top-1/Top-3/Top-10-Treffer aus veröffentlichten Ranglisten.

    ``r_matrix`` und ``start_matrix`` haben die Form (Instrumente × 90) mit Spalte h−1. ``end_days`` (ab 1.13):
    letzter Fenstertag je Aktie, wenn er vom Stichtag abweicht (Zwischenstand vor Börsenbeginn).
    """
    if top_k not in TOP_K_VALUES:
        raise ValueError("top_k muss 1, 3 oder 10 sein")
    weights = tuple(sorted(set(int(w) for w in weights)))
    if not weights or any(w not in CANONICAL_WEIGHTS for w in weights):
        raise ValueError("Ungültige Gewichtungsauswahl")
    window_days = tuple(sorted(set(int(h) for h in window_days)))
    if not window_days or window_days[0] < 1 or window_days[-1] > 90:
        raise ValueError("Ungültige Fensterauswahl")
    if sort not in ("occurrences", "distinct_windows"):
        raise ValueError("sort muss occurrences oder distinct_windows sein")
    mode = "single" if len(weights) == 1 else "all"

    stats: dict[int, InstrumentFrequency] = {}
    hit_windows: dict[int, set[int]] = {}
    hit_weights: dict[int, set[int]] = {}
    hit_effective: dict[int, set[tuple[int, int]]] = {}
    valid_cells = 0

    for h in window_days:
        for w in weights:
            ranking = cell_ranking(windows, policy, w, h)
            size = ranking.size
            if size == 0:
                continue
            valid_cells += 1
            order = ranking.order
            # Verfügbarkeit A_i: jede ISIN der Vergleichsmenge besitzt in dieser Zelle einen Rang.
            for idx in order.tolist():
                entry = stats.get(idx)
                if entry is None:
                    entry = stats[idx] = InstrumentFrequency(idx=idx)
                entry.available_cells += 1
            top = min(10, size)
            for position in range(top):
                idx = int(order[position])
                rank = position + 1
                entry = stats[idx]
                if rank <= 1:
                    entry.n1 += 1
                if rank <= 3:
                    entry.n3 += 1
                entry.n10 += 1
                if rank <= top_k:
                    hit_windows.setdefault(idx, set()).add(h)
                    hit_weights.setdefault(idx, set()).add(w)
                    entry.hits_by_weight[w] = entry.hits_by_weight.get(w, 0) + 1
                    start_day = int(start_matrix[idx, h - 1])
                    end_day = int(end_days[idx]) if end_days is not None else int(cutoff_day)
                    hit_effective.setdefault(idx, set()).add((start_day, end_day))
                    entry.occurrences.append(
                        Occurrence(
                            h=h,
                            weight=w,
                            rank=rank,
                            score=float(ranking.scores[position]),
                            r=float(r_matrix[idx, h - 1]),
                            start_day=start_day,
                            end_day=end_day,
                            cohort_size=size,
                            small_field=size < top_k,
                        )
                    )

    listed: list[InstrumentFrequency] = []
    for idx, entry in stats.items():
        entry.distinct_windows_k = len(hit_windows.get(idx, ()))
        entry.distinct_weights_k = len(hit_weights.get(idx, ()))
        entry.distinct_effective_windows_k = len(hit_effective.get(idx, ()))
        if entry.n_k(top_k) > 0:
            listed.append(entry)
    listed.sort(key=lambda e: _sort_key(e, top_k, mode, sort, isin_of))

    theoretical = len(weights) * len(window_days)
    return FrequencyResult(
        policy=policy,
        weights=weights,
        windows=window_days,
        top_k=top_k,
        mode=mode,
        sort=sort,
        theoretical_cells=theoretical,
        valid_cells=valid_cells,
        empty_cells=theoretical - valid_cells,
        entries=listed,
    )


@dataclass
class WinnerRow:
    h: int
    cohort_size: int
    entries: list[dict]  # gleichplatzierte Spitzenwerte (idx, r, start_day, end_day)
    tie: bool
    empty_reason: str | None
    all_negative: bool


def build_pure_return_winners(
    windows: Mapping[int, WindowRanking],
    *,
    r_matrix: np.ndarray,
    start_matrix: np.ndarray,
    cutoff_day: int,
    window_days: Sequence[int] = tuple(range(1, 91)),
    ranking_of: Callable[[WindowRanking], Ranking | None] = lambda window: window.native0,
    end_days: np.ndarray | None = None,
) -> list[WinnerRow]:
    """Genau eine Zeile je Fenster aus einer reinen Renditerangliste (Standard: 0/100 auf V).

    Mit ``ranking_of`` auch für Ranking 2 (V mit Umsatzfilter): gleiche Renditen, gleiche
    Gleichstandsregel, nur eine kleinere Menge.
    """
    rows: list[WinnerRow] = []
    for h in window_days:
        ranking = ranking_of(windows[h])
        if ranking is None or ranking.size == 0:
            rows.append(WinnerRow(h, 0, [], False, "keine_vergleichbare_aktie", False))
            continue
        top_idx = int(ranking.order[0])
        top_r = float(r_matrix[top_idx, h - 1])
        tied: list[dict] = []
        for idx in ranking.order.tolist():
            value = float(r_matrix[idx, h - 1])
            if value != top_r:
                break
            end_day = int(end_days[idx]) if end_days is not None else int(cutoff_day)
            tied.append({"idx": int(idx), "r": value, "start_day": int(start_matrix[idx, h - 1]), "end_day": end_day})
        rows.append(
            WinnerRow(
                h=h,
                cohort_size=ranking.size,
                entries=tied,
                tie=len(tied) > 1,
                empty_reason=None,
                all_negative=top_r < 0,
            )
        )
    return rows


def overall_max_return(rows: Sequence[WinnerRow]) -> dict:
    """Rückblickendes Maximum über alle gültigen Instrument-Fenster-Paare (mit Gleichständen)."""
    candidates = [(entry["r"], row.h, entry) for row in rows for entry in row.entries]
    if not candidates:
        return {"entries": [], "tie": False, "pairs_evaluated": sum(r.cohort_size for r in rows)}
    best = max(value for value, _, _ in candidates)
    entries = [dict(entry, h=h) for value, h, entry in candidates if value == best]
    entries.sort(key=lambda e: (e["h"], e["idx"]))
    # Dieselbe Aktie mit demselben tatsächlichen Start/Ende (z. B. Freitag als Start für h, h+1, h+2)
    # ist kein Gleichstand: nur das kürzeste angefragte Fenster bleibt, die übrigen h werden genannt.
    unique: dict[tuple[int, int, int], dict] = {}
    for entry in entries:
        key = (entry["idx"], entry["start_day"], entry["end_day"])
        if key in unique:
            unique[key].setdefault("same_effective_h", []).append(entry["h"])
        else:
            unique[key] = entry
    kept = list(unique.values())
    return {"entries": kept, "tie": len(kept) > 1, "pairs_evaluated": int(sum(r.cohort_size for r in rows))}
