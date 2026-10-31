"""Indikatoren des AktienPilot (reine Funktionen über NumPy-Reihen, ohne Blick in die Zukunft).

Jede Funktion rechnet am Index ``k`` nur mit den Werten ``0 … k`` (abgeschlossene Sitzungen bis einschließlich ``k``).
Fehlende oder zu kurze Reihen ergeben ``nan`` – nie einen erfundenen Wert. Aufwärmphase: Ein Indikator mit Länge ``n`` ist
erst ab dem ``n``-ten Wert definiert (ATR und RSI nach Wilder ab ``n + 1`` Werten, weil sie Vortageswerte brauchen).

Formeln (Abschnitte 8–10 und 23):

* gleitender Durchschnitt ``MA(n)_k = mean(close[k-n+1 … k])``
* wahre Spanne ``TR_k = max(high_k − low_k, |high_k − close_{k−1}|, |low_k − close_{k−1}|)``;
  ``ATR(n)`` nach Wilder: Start mit dem Mittel der ersten ``n`` Spannen, danach ``ATR_k = (ATR_{k−1}·(n−1) + TR_k) / n``
* ``RSI(n)`` nach Wilder auf Schlusskursänderungen: mittlerer Gewinn und Verlust wie ATR geglättet,
  ``RSI = 100 − 100 / (1 + G/V)``; nur Gewinne → 100, keine Bewegung → 50
* Regression logarithmierter Kurse gegen den Sitzungsindex über ``n`` Sitzungen: Steigung je Sitzung, annualisiert mit
  252 Sitzungen (``exp(252·b) − 1``), Bestimmtheitsmaß ``R² = 1 − SSE/SST``
* Übernachtlücke ``|open_k / close_{k−1} − 1|``
"""

from __future__ import annotations

import numpy as np

TRADING_DAYS_PER_YEAR = 252


def sma(values: np.ndarray, n: int) -> np.ndarray:
    """Einfacher gleitender Durchschnitt; ``nan`` in der Aufwärmphase und wenn ein Wert im Fenster fehlt."""
    values = np.asarray(values, dtype=np.float64)
    out = np.full(len(values), np.nan)
    if n <= 0 or len(values) < n:
        return out
    finite = np.isfinite(values)
    filled = np.where(finite, values, 0.0)
    csum = np.concatenate(([0.0], np.cumsum(filled)))
    ccount = np.concatenate(([0], np.cumsum(finite.astype(np.int64))))
    window_sum = csum[n:] - csum[:-n]
    window_count = ccount[n:] - ccount[:-n]
    result = np.where(window_count == n, window_sum / n, np.nan)
    out[n - 1:] = result
    return out


def true_range(high: np.ndarray, low: np.ndarray, close: np.ndarray) -> np.ndarray:
    high = np.asarray(high, dtype=np.float64)
    low = np.asarray(low, dtype=np.float64)
    close = np.asarray(close, dtype=np.float64)
    tr = np.full(len(close), np.nan)
    if len(close) == 0:
        return tr
    tr[0] = high[0] - low[0]
    if len(close) > 1:
        prev = close[:-1]
        tr[1:] = np.fmax(high[1:] - low[1:], np.fmax(np.abs(high[1:] - prev), np.abs(low[1:] - prev)))
    return tr


def atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, n: int) -> np.ndarray:
    """ATR nach Wilder; erste definierte Stelle ist Index ``n`` (Spannen 1 … n mit Vortageskurs)."""
    tr = true_range(high, low, close)
    out = np.full(len(tr), np.nan)
    if n <= 0 or len(tr) <= n:
        return out
    first = tr[1:n + 1]
    if not np.all(np.isfinite(first)):
        # Lücke in der Aufwärmphase: Start an der ersten Stelle mit n vollständigen Spannen
        start = None
        run = 0
        for k in range(1, len(tr)):
            run = run + 1 if np.isfinite(tr[k]) else 0
            if run >= n:
                start = k
                break
        if start is None:
            return out
        value = float(np.mean(tr[start - n + 1:start + 1]))
        out[start] = value
        k0 = start + 1
    else:
        value = float(np.mean(first))
        out[n] = value
        k0 = n + 1
    for k in range(k0, len(tr)):
        if not np.isfinite(tr[k]):
            out[k] = np.nan
            continue
        value = (value * (n - 1) + tr[k]) / n
        out[k] = value
    return out


def rsi(close: np.ndarray, n: int) -> np.ndarray:
    """RSI nach Wilder; erste definierte Stelle ist Index ``n``."""
    close = np.asarray(close, dtype=np.float64)
    out = np.full(len(close), np.nan)
    if n <= 0 or len(close) <= n:
        return out
    change = np.diff(close)
    gains = np.clip(change, 0.0, None)
    losses = np.clip(-change, 0.0, None)
    if not np.all(np.isfinite(change[:n])):
        return out
    avg_gain = float(np.mean(gains[:n]))
    avg_loss = float(np.mean(losses[:n]))

    def value(g: float, v: float) -> float:
        if v == 0.0 and g == 0.0:
            return 50.0
        if v == 0.0:
            return 100.0
        return 100.0 - 100.0 / (1.0 + g / v)

    out[n] = value(avg_gain, avg_loss)
    for k in range(n, len(change)):
        if not np.isfinite(change[k]):
            out[k + 1] = np.nan
            continue
        avg_gain = (avg_gain * (n - 1) + gains[k]) / n
        avg_loss = (avg_loss * (n - 1) + losses[k]) / n
        out[k + 1] = value(avg_gain, avg_loss)
    return out


def log_regression(close: np.ndarray, end: int, n: int) -> tuple[float, float, float]:
    """Regression ``ln(close)`` gegen den Sitzungsindex über die ``n`` Sitzungen bis einschließlich ``end``.

    Rückgabe: (Steigung je Sitzung, annualisierte Steigung ``exp(252·b) − 1``, ``R²``); ``nan``, wenn eine Sitzung fehlt oder
    ein Kurs nicht positiv ist. Bei konstantem Kurs ist ``SST = 0``: ``R²`` gilt dann als 0 (keine erklärte Bewegung)."""
    close = np.asarray(close, dtype=np.float64)
    if n < 2 or end < n - 1 or end >= len(close):
        return np.nan, np.nan, np.nan
    window = close[end - n + 1:end + 1]
    if not np.all(np.isfinite(window)) or np.any(window <= 0):
        return np.nan, np.nan, np.nan
    y = np.log(window)
    x = np.arange(n, dtype=np.float64)
    xm = x.mean()
    ym = y.mean()
    sxx = float(np.sum((x - xm) ** 2))
    sxy = float(np.sum((x - xm) * (y - ym)))
    slope = sxy / sxx
    fitted = ym + slope * (x - xm)
    sse = float(np.sum((y - fitted) ** 2))
    sst = float(np.sum((y - ym) ** 2))
    r2 = 0.0 if sst <= 0.0 else 1.0 - sse / sst
    return slope, float(np.expm1(TRADING_DAYS_PER_YEAR * slope)), r2


def percentile_ranks(values: np.ndarray) -> np.ndarray:
    """Perzentile 0–100 innerhalb der gültigen Werte (Mittelrang bei Gleichstand); ``nan`` bleibt ``nan``.

    Formel wie in der App: ``100 · (Rang − 1) / (Anzahl − 1)`` mit Mittelrang; bei nur einem Wert 100."""
    values = np.asarray(values, dtype=np.float64)
    out = np.full(len(values), np.nan)
    mask = np.isfinite(values)
    m = int(mask.sum())
    if m == 0:
        return out
    if m == 1:
        out[mask] = 100.0
        return out
    valid = values[mask]
    order = np.argsort(valid, kind="mergesort")
    ranks = np.empty(m, dtype=np.float64)
    sorted_vals = valid[order]
    k = 0
    while k < m:
        j = k
        while j + 1 < m and sorted_vals[j + 1] == sorted_vals[k]:
            j += 1
        mean_rank = (k + j) / 2.0 + 1.0
        ranks[order[k:j + 1]] = mean_rank
        k = j + 1
    out[mask] = 100.0 * (ranks - 1.0) / (m - 1.0)
    return out


def overnight_gaps(open_: np.ndarray, close: np.ndarray) -> np.ndarray:
    """Absolute Übernachtlücke je Sitzung ``|open_k / close_{k−1} − 1|`` (Index 0: ``nan``)."""
    open_ = np.asarray(open_, dtype=np.float64)
    close = np.asarray(close, dtype=np.float64)
    out = np.full(len(close), np.nan)
    if len(close) > 1:
        prev = close[:-1]
        with np.errstate(divide="ignore", invalid="ignore"):
            out[1:] = np.where((prev > 0) & np.isfinite(open_[1:]), np.abs(open_[1:] / prev - 1.0), np.nan)
    return out


def rolling_max(values: np.ndarray, n: int) -> np.ndarray:
    """Höchstwert der ``n`` Werte bis einschließlich ``k``; ``nan`` in der Aufwärmphase oder bei Lücken."""
    values = np.asarray(values, dtype=np.float64)
    out = np.full(len(values), np.nan)
    for k in range(n - 1, len(values)):
        window = values[k - n + 1:k + 1]
        if np.all(np.isfinite(window)):
            out[k] = float(window.max())
    return out


def previous(values: np.ndarray) -> np.ndarray:
    """Wert der Vorsitzung (``out[k] = values[k−1]``) – für Vergleiche ohne den aktuellen Tag."""
    values = np.asarray(values, dtype=np.float64)
    out = np.full(len(values), np.nan)
    if len(values) > 1:
        out[1:] = values[:-1]
    return out
