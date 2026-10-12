"""Perzentile, elf Gewichtungen und deterministische Ranglisten (Abschnitt 11).

Vergleichsmengen je Stichtag D und Fenster h:

* V(D,h): alle für eine veröffentlichte reine Kursrendite qualifizierten Instrumente.
* U(D,h): alle für die Aufwärts-Gleichmäßigkeit qualifizierten Instrumente; U ⊆ V.

Politik ``native``: 0/100 nutzt V, 10/90 … 100/0 nutzen U.
Politik ``common_trend``: alle elf Varianten einschließlich 0/100 nutzen U.

Weil 10/90 … 100/0 in beiden Politiken dieselbe Menge U und dieselben Perzentile
verwenden, sind ihre Ranglisten identisch und werden einmal berechnet. Unterschiedlich
ist nur 0/100 (V gegenüber U).

Instrumente werden über ihren globalen Index adressiert. Die Instrumenttabelle eines
Snapshots ist aufsteigend nach ISIN sortiert; ein kleinerer Index bedeutet daher eine
lexikografisch kleinere ISIN und dient als stabiler technischer Gleichstandsentscheid.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..config import CANONICAL_WEIGHTS


def average_ranks_doubled(values: np.ndarray) -> np.ndarray:
    """Doppelter aufsteigender Durchschnittsrang als ganze Zahl (exakt, ohne Rundung).

    Bei einer Gleichstandsgruppe auf den Plätzen a…b (1-basiert) ist der Durchschnittsrang
    (a + b) / 2; gespeichert wird a + b. Ganzzahlen lassen sich verlustfrei veröffentlichen.
    """
    v = np.asarray(values, dtype=np.float64)
    m = len(v)
    if m == 0:
        return np.empty(0, dtype=np.int64)
    if not np.all(np.isfinite(v)):
        raise ValueError("Perzentile nur aus endlichen Werten")
    order = np.argsort(v, kind="mergesort")
    sorted_v = v[order]
    doubled = np.empty(m, dtype=np.int64)
    start = 0
    while start < m:
        end = start
        while end + 1 < m and sorted_v[end + 1] == sorted_v[start]:
            end += 1
        doubled[order[start : end + 1]] = (start + 1) + (end + 1)
        start = end + 1
    return doubled


def percentile_from_doubled(doubled: np.ndarray, m: int) -> np.ndarray:
    """P = 100 · (Rang − 1) / (M − 1) mit Rang = doppelter Rang / 2; M = 1 ergibt 100.

    Die App verwendet exakt diese Operationsfolge (IEEE-754, bitgleiches Ergebnis).
    """
    if m == 0:
        return np.empty(0, dtype=np.float64)
    if m == 1:
        return np.array([100.0])
    ranks = np.asarray(doubled, dtype=np.float64) / 2.0
    return 100.0 * (ranks - 1.0) / (m - 1)


def percentile_average_rank(values: np.ndarray) -> np.ndarray:
    """Perzentilrang 0–100 aus aufsteigenden Durchschnittsrängen.

    P_i = 100 · (Durchschnittsrang_i − 1) / (M − 1); M = 1 ergibt 100.
    Exakte Gleichstände erhalten denselben Durchschnittsrang.
    """
    v = np.asarray(values, dtype=np.float64)
    return percentile_from_doubled(average_ranks_doubled(v), len(v))


def weighted_score(weight: int, g: np.ndarray, r: np.ndarray) -> np.ndarray:
    """Score(w) = (w/100)·G + (1 − w/100)·R in genau dieser Operationsreihenfolge.

    Die App berechnet Anzeige-Scores mit identischer Formel; IEEE-754-Doubles liefern
    dann bitgleiche Ergebnisse.
    """
    if weight not in CANONICAL_WEIGHTS:
        raise ValueError(f"Unzulässige Gewichtung {weight}")
    if weight == 0:
        return np.array(r, dtype=np.float64, copy=True)
    if weight == 100:
        return np.array(g, dtype=np.float64, copy=True)
    a = weight / 100
    return a * np.asarray(g, dtype=np.float64) + (1 - weight / 100) * np.asarray(r, dtype=np.float64)


def _tie_positions(primary_sorted: np.ndarray) -> np.ndarray:
    """Positionen (0-basiert) in einer sortierten Liste, deren Primärwert mit einem Nachbarn exakt übereinstimmt."""
    n = len(primary_sorted)
    if n < 2:
        return np.empty(0, dtype=np.int64)
    eq = primary_sorted[1:] == primary_sorted[:-1]
    flags = np.zeros(n, dtype=bool)
    flags[1:] |= eq
    flags[:-1] |= eq
    return np.nonzero(flags)[0].astype(np.int64)


@dataclass
class Ranking:
    """Eine veröffentlichte Rangliste: ``order[k]`` ist der globale Instrumentindex auf Platz k+1."""

    weight: int
    cohort: str  # "V" oder "U"
    order: np.ndarray
    scores: np.ndarray  # in Rangfolge, ungerundet
    tie_positions: np.ndarray

    @property
    def size(self) -> int:
        return int(len(self.order))

    @property
    def sole_candidate(self) -> bool:
        """M = 1: Score 100 nur mit Pflichthinweis „Einziger qualifizierter Titel“."""
        return self.size == 1

    def rank_of(self, idx: int) -> int | None:
        hits = np.nonzero(self.order == idx)[0]
        return int(hits[0]) + 1 if len(hits) else None


@dataclass
class WindowRanking:
    h: int
    v_idx: np.ndarray  # globale Indizes der Menge V (aufsteigend)
    u_idx: np.ndarray  # globale Indizes der Menge U (aufsteigend)
    pct_r_v: np.ndarray  # Renditeperzentil innerhalb V, ausgerichtet an v_idx
    pct_g_u: np.ndarray  # R²-Perzentil innerhalb U, ausgerichtet an u_idx
    pct_r_u: np.ndarray  # Renditeperzentil innerhalb U, ausgerichtet an u_idx
    ar2_r_v: np.ndarray  # doppelter Durchschnittsrang Rendite in V (exakt, ganzzahlig)
    ar2_g_u: np.ndarray  # doppelter Durchschnittsrang R² in U
    ar2_r_u: np.ndarray  # doppelter Durchschnittsrang Rendite in U
    native0: Ranking  # 0/100 auf V
    trend: dict[int, Ranking] = field(default_factory=dict)  # alle elf Gewichte auf U
    label: str = "global"  # "global" oder "untergruppe:<Name>"

    def ranking(self, policy: str, weight: int) -> Ranking:
        if policy == "native" and weight == 0:
            return self.native0
        return self.trend[weight]


def rank_window(
    h: int,
    v_idx: np.ndarray,
    u_idx: np.ndarray,
    r_all: np.ndarray,
    r2_all: np.ndarray,
    slope_all: np.ndarray,
    noise_all: np.ndarray,
) -> WindowRanking:
    """Berechnet alle Ranglisten eines Fensters.

    ``*_all`` sind Spalten je globalem Instrumentindex (NaN, wo nicht berechnet).
    """
    v_idx = np.asarray(v_idx, dtype=np.int64)
    u_idx = np.asarray(u_idx, dtype=np.int64)
    if not np.all(np.isin(u_idx, v_idx)):
        raise ValueError("U muss Teilmenge von V sein")

    # --- native 0/100 auf V: Rendite absteigend, ISIN (Index) aufsteigend
    r_v = r_all[v_idx]
    if len(v_idx) and not np.all(np.isfinite(r_v)):
        raise ValueError("V enthält Instrumente ohne Rendite")
    ar2_r_v = average_ranks_doubled(r_v)
    pct_r_v = percentile_from_doubled(ar2_r_v, len(v_idx))
    order_v = np.lexsort((v_idx, -r_v)) if len(v_idx) else np.empty(0, dtype=np.int64)
    native0 = Ranking(
        weight=0,
        cohort="V",
        order=v_idx[order_v],
        scores=pct_r_v[order_v],
        tie_positions=_tie_positions(r_v[order_v]),
    )

    # --- U-basierte Ranglisten für alle elf Gewichte
    r_u = r_all[u_idx]
    g_raw = r2_all[u_idx]
    slope_u = slope_all[u_idx]
    noise_u = noise_all[u_idx]
    if len(u_idx) and not (np.all(np.isfinite(r_u)) and np.all(np.isfinite(g_raw))):
        raise ValueError("U enthält Instrumente ohne Rendite oder R²")
    ar2_g_u = average_ranks_doubled(g_raw)
    ar2_r_u = average_ranks_doubled(r_u)
    pct_g_u = percentile_from_doubled(ar2_g_u, len(u_idx))
    pct_r_u = percentile_from_doubled(ar2_r_u, len(u_idx))

    trend: dict[int, Ranking] = {}
    for weight in CANONICAL_WEIGHTS:
        if len(u_idx) == 0:
            trend[weight] = Ranking(weight, "U", np.empty(0, dtype=np.int64), np.empty(0), np.empty(0, dtype=np.int64))
            continue
        score = weighted_score(weight, pct_g_u, pct_r_u)
        if weight == 0:
            order = np.lexsort((u_idx, -r_u))
            primary = r_u[order]
        elif weight == 100:
            order = np.lexsort((u_idx, noise_u, -slope_u, -g_raw))
            primary = g_raw[order]
        else:
            order = np.lexsort((u_idx, -g_raw, -r_u, -score))
            primary = score[order]
        trend[weight] = Ranking(
            weight=weight,
            cohort="U",
            order=u_idx[order],
            scores=score[order],
            tie_positions=_tie_positions(primary),
        )

    return WindowRanking(
        h=h,
        v_idx=v_idx,
        u_idx=u_idx,
        pct_r_v=pct_r_v,
        pct_g_u=pct_g_u,
        pct_r_u=pct_r_u,
        ar2_r_v=ar2_r_v,
        ar2_g_u=ar2_g_u,
        ar2_r_u=ar2_r_u,
        native0=native0,
        trend=trend,
    )


def rank_subgroup(
    base: WindowRanking,
    subset_idx,
    r_all: np.ndarray,
    r2_all: np.ndarray,
    slope_all: np.ndarray,
    noise_all: np.ndarray,
    name: str,
) -> WindowRanking:
    """Echtes Untergruppenranking mit eigener, benannter Vergleichsmenge.

    Die globale Rangliste bleibt unverändert. V und U werden auf die Untergruppe
    eingeschränkt und alle Perzentile darin konsistent neu berechnet.
    """
    subset = np.asarray(sorted(set(int(i) for i in subset_idx)), dtype=np.int64)
    v = base.v_idx[np.isin(base.v_idx, subset)]
    u = base.u_idx[np.isin(base.u_idx, subset)]
    result = rank_window(base.h, v, u, r_all, r2_all, slope_all, noise_all)
    result.label = f"untergruppe:{name}"
    return result
