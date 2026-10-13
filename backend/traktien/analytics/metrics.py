"""Kennzahlen eines geprüften Fensters (Abschnitt 9 des Auftrags).

Eingabe sind echte, positive, endliche, splitbereinigte Schlusskurse p_0 … p_(N−1).
Gerechnet wird in float64 ohne Rundung.

* Kursrendite r = p_(N−1) / p_0 − 1
* OLS auf dem Preis mit t_i = i: Steigung m, Achsenabschnitt b, SSE, SST, R² = 1 − SSE/SST
* relative Steigung s = 100 · m / Mittel(p)  (Prozent je Handelsbeobachtung)
* Residualrauschen q = 100 · sqrt(SSE / N) / Mittel(p)
* größter Rückgang ab Fensterbeginn MDD = max_i (1 − p_i / max(p_0 … p_i))
* positive Schlusskursvergleiche: Zahl der Beobachtungen mit p_i > p_(i−1) (ab kennzahlen-v2)
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np


class NumericInconsistency(ArithmeticError):
    """R² liegt weit außerhalb von [0, 1] – ein echter Rechenfehler, kein Datenzustand."""


@dataclass(frozen=True)
class PriceMetrics:
    n: int
    r: float
    m: float | None
    b: float | None
    r2: float | None
    slope_pct: float | None
    noise_pct: float | None
    mdd: float
    sse: float | None
    sst: float | None
    r2_defined: bool
    ups: int = 0  # Zahl der Schlusskursvergleiche p_i > p_(i−1) im Fenster (von N − 1 möglichen)


def price_return(p_start: float, p_end: float) -> float:
    if not (math.isfinite(p_start) and math.isfinite(p_end)) or p_start <= 0 or p_end <= 0:
        raise ValueError("Rendite nur aus positiven, endlichen Kursen")
    return p_end / p_start - 1.0


def max_drawdown(prices: np.ndarray) -> float:
    """Größter Rückgang ab Fensterbeginn als positiver Bruch (0.25 = −25 %)."""
    running_peak = np.maximum.accumulate(prices)
    drawdowns = 1.0 - prices / running_peak
    return float(drawdowns.max()) if len(drawdowns) else 0.0


def ols_on_price(prices: np.ndarray) -> tuple[float, float, float, float]:
    """OLS mit t_i = i. Gibt (m, b, SSE, SST) zurück."""
    n = len(prices)
    t_mean = (n - 1) / 2.0
    p_mean = float(prices.mean())
    dt = np.arange(n, dtype=np.float64) - t_mean
    dp = prices - p_mean
    s_tt = float(np.dot(dt, dt))
    m = float(np.dot(dt, dp)) / s_tt
    b = p_mean - m * t_mean
    # Zentrierte Residuen (identisch zu p − (m·t + b), aber ohne Auslöschung gegen b)
    residuals = dp - m * dt
    sse = float(np.dot(residuals, residuals))
    sst = float(np.dot(dp, dp))
    return m, b, sse, sst


def calculate_price_metrics(
    prices: np.ndarray,
    *,
    min_obs_trend: int = 15,
    sst_rel_tolerance: float = 1e-18,
    r2_bound_tolerance: float = 1e-9,
    strict: bool = True,
) -> PriceMetrics:
    """``strict=False``: ein numerisch unplausibles R² macht nur dieses Fenster „Trend nicht
    definiert“, statt den ganzen Lauf abzubrechen (Ausfall eines Titels darf nicht das System
    zurücksetzen)."""
    p = np.asarray(prices, dtype=np.float64)
    n = len(p)
    if n < 2:
        raise ValueError("Mindestens zwei Beobachtungen erforderlich")
    if not np.all(np.isfinite(p)) or np.any(p <= 0):
        raise ValueError("Nur positive, endliche Kurse sind zulässig")

    r = price_return(float(p[0]), float(p[-1]))
    mdd = max_drawdown(p)
    ups = int(np.count_nonzero(p[1:] > p[:-1]))

    if n < min_obs_trend:
        return PriceMetrics(n, r, None, None, None, None, None, mdd, None, None, False, ups)

    m, b, sse, sst = ols_on_price(p)
    p_mean = float(p.mean())
    slope_pct = 100.0 * m / p_mean
    noise_pct = 100.0 * math.sqrt(sse / n) / p_mean

    if sst <= sst_rel_tolerance * n * p_mean * p_mean:
        # Konstante (oder numerisch konstante) Reihe: R² nicht definiert.
        return PriceMetrics(n, r, m, b, None, slope_pct, noise_pct, mdd, sse, sst, False, ups)

    r2 = 1.0 - sse / sst
    if r2 < -r2_bound_tolerance or r2 > 1.0 + r2_bound_tolerance:
        if not strict:
            return PriceMetrics(n, r, m, b, None, slope_pct, noise_pct, mdd, sse, sst, False, ups)
        raise NumericInconsistency(f"R² außerhalb des zulässigen Bereichs: {r2!r}")
    r2 = min(1.0, max(0.0, r2))
    return PriceMetrics(n, r, m, b, r2, slope_pct, noise_pct, mdd, sse, sst, True, ups)


def impulse_share(prices: np.ndarray) -> float | None:
    """Anteil der größten einzelnen Tagesbewegung an der Gesamtbewegung (log-basiert)."""
    p = np.asarray(prices, dtype=np.float64)
    if len(p) < 3:
        return None
    total = abs(math.log(p[-1] / p[0]))
    if total == 0.0:
        return None
    steps = np.abs(np.diff(np.log(p)))
    return float(steps.max() / total)


def takeover_pattern(prices: np.ndarray, *, jump_min: float, calm_max: float, calm_sessions: int) -> bool:
    """Übernahmemuster: größter Tagesanstieg ≥ ``jump_min``, danach an mindestens ``calm_sessions``
    Sitzungen bis zum Fensterende jede Tagesbewegung höchstens ±``calm_max``.

    Typisch für ein Übernahmeangebot (Kurs springt auf den Angebotspreis und bleibt dort). Nur ein
    Hinweis – die Rendite bleibt echt, stammt aber fast vollständig aus diesem einen Sprung.
    """
    p = np.asarray(prices, dtype=np.float64)
    if len(p) < calm_sessions + 2:
        return False
    moves = p[1:] / p[:-1] - 1.0
    k = int(np.argmax(moves))
    if not (moves[k] >= jump_min):
        return False
    after = moves[k + 1 :]
    return len(after) >= calm_sessions and bool(np.all(np.abs(after) <= calm_max))
