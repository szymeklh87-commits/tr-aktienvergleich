"""Rückblick der Signalregel (ab 1.24.0, ``rueckblick-1``): Was geschah historisch nach Signalen derselben Regel?

Auftrag vom 07.11.2026 (17:03, 17:06, 17:09, 17:42 Uhr): je Kaufsignal die durchschnittliche Rendite nach 1, 5, 10 und 20
Handelstagen und nach 1, 3, 6 und 12 Monaten, mit Trefferquote und Fallzahl – nur mit damals verfügbaren Daten, mit
realistischem Einstieg, Stop, Kursziel und Kosten. Historische Ergebnisse sind keine Vorhersage.

Rechnung
* Für jede Aktie und jede Sitzung der geladenen Historie wird die Signalregel aus :mod:`tradeplan` ausgewertet – nur mit Kursen
  bis zu diesem Tag (gleitende Linien, ATR, RSI, Kurslücke, Umsatz der letzten 20 Sitzungen, relative Stärke gegenüber allen
  Aktien desselben Tages). Nachrichten, Termine für Geschäftszahlen und Analystenziele liegen rückwirkend nicht vor und
  bleiben unberücksichtigt; das Kursziel ist deshalb immer das 2-R-Ziel der Regel.
* **Ausführung wie im Plan** (Kaufsignal): Limit-Kauf am nächsten Handelstag – zur Eröffnung, wenn sie höchstens beim Limit
  liegt, sonst zum Limit, wenn die Tagesspanne es erreicht; sonst kein Kauf („nicht ausgeführt“). Danach Stop und Kursziel mit
  den Tagestiefs und -hochs (öffnet der Kurs jenseits davon: zur Eröffnung; beides an einem Tag: Stop zuerst, vorsichtig),
  sonst Verkauf zum Schlusskurs nach h Handelstagen.
* **Halten ohne Stop und Ziel**: Kauf wie oben, Verkauf zum Schlusskurs nach h Handelstagen (auch für 1–12 Monate).
* Kosten je Kauf und Verkauf wie im Spielgeld-Robo (Spread nach Umsatzklasse, Slippage, Währungs- und Handelsplatzaufschlag,
  Ordergebühr bei einer Position von 1.000 €); Renditen netto, ohne Steuern und Dividenden.
* Gezählt wird nur der **erste Tag einer zusammenhängenden Signalfolge** derselben Aktie – aufeinanderfolgende Tage mit
  demselben Signal wären sonst fast derselbe Fall. Vergleichsgruppe: alle Aktien mit Mindestumsatz an jedem zehnten
  Handelstag (Kauf zur nächsten Eröffnung).
* Verzerrungen: heutiges Aktienverzeichnis (nicht mehr gelistete Aktien fehlen), Wechselkurs des Stichtags für den
  Mindestumsatz in USD.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from . import tradeplan as tp

VERSION = "rueckblick-1"
DAY_HORIZONS: tuple[int, ...] = (1, 5, 10, 20)
MONTH_HORIZONS: tuple[tuple[int, int], ...] = ((1, 21), (3, 63), (6, 126), (12, 252))  # (Monate, Handelstage)
HOLD_HORIZONS: tuple[int, ...] = DAY_HORIZONS + tuple(h for _, h in MONTH_HORIZONS)
MIN_CASES = 30  # ab so vielen unabhängigen Fällen gilt eine Kennzahl als belegt
MIN_CASES_STOCK = 10
POSITION_EUR = 1000.0
WARMUP = 55  # Sitzungen für 50-Tage-Linie, ATR, RSI und 20-Tage-Hoch
BASELINE_STEP = 10
STATUS = {0: None, 1: "kein_kauf", 2: "beobachten", 3: "kaufsignal"}

HINWEISE = [
    "Historische Ergebnisse sind keine Vorhersage und keine Gewinnwahrscheinlichkeit für die Zukunft.",
    "Nachrichten, Termine für Geschäftszahlen und Analystenziele liegen rückwirkend nicht vor – sie fehlen in diesem Rückblick.",
    "Nur der erste Tag einer Signalfolge zählt; Kosten wie im Spielgeld-Robo, ohne Steuern und Dividenden.",
    "Heutiges Aktienverzeichnis: nicht mehr gelistete Aktien fehlen (Überlebensverzerrung).",
]


@dataclass
class StockHistory:
    """Eingaben je Aktie (gleicher Index wie die Sitzungen)."""

    isin: str
    days: np.ndarray
    open: np.ndarray
    high: np.ndarray
    low: np.ndarray
    close: np.ndarray
    sma20: np.ndarray
    sma50: np.ndarray
    high20: np.ndarray
    rsi: np.ndarray
    atr_pct: np.ndarray
    gap: np.ndarray
    rvol: np.ndarray
    r20: np.ndarray
    turnover_local: np.ndarray
    unit_to_eur: float | None
    usd_per_eur: float | None
    currency: str | None = None


@dataclass
class Outcome:
    """Ergebnis eines Falls je Haltedauer (netto, Anteil); None, wenn die Haltedauer über das Datenende reicht."""

    filled: bool
    plan: dict[int, float | None] = field(default_factory=dict)
    plan_drawdown: dict[int, float | None] = field(default_factory=dict)
    hold: dict[int, float | None] = field(default_factory=dict)


@dataclass
class Result:
    payload: dict
    per_stock: dict[str, dict]  # ISIN → {"n", "mittel", "treffer"} (Kaufsignale, Plan, 10 Tage)
    statuses: dict[str, np.ndarray] = field(default_factory=dict)  # ISIN → Status je Sitzung (Prüfungen)


def _finite(x) -> bool:
    return x is not None and isinstance(x, (int, float, np.floating)) and math.isfinite(float(x))


def _squash(values: np.ndarray) -> np.ndarray:
    """Monotone Abbildung auf (0, 1) für den gemeinsamen Sortierschlüssel (Tag + Wert)."""
    return (np.arctan(values) / math.pi + 0.5) * 0.999


def strength_percentiles(histories: list[StockHistory]) -> list[np.ndarray]:
    """Perzentil der Kursänderung über 20 Sitzungen gegenüber allen Aktien desselben Tages – wie ``UniverseStats.percentile``
    (Mitte zwischen linker und rechter Einordnung), mindestens 20 Werte je Tag, sonst NaN. Nur Werte desselben Tages."""
    parts_days = []
    parts_vals = []
    for hist in histories:
        ok = np.isfinite(hist.r20)
        parts_days.append(hist.days[ok].astype(np.float64))
        parts_vals.append(hist.r20[ok])
    if not parts_days:
        return [np.full(len(h.days), np.nan) for h in histories]
    days = np.concatenate(parts_days)
    vals = np.concatenate(parts_vals)
    keys = np.sort(days + _squash(vals))
    out = []
    for hist in histories:
        d = hist.days.astype(np.float64)
        v = hist.r20
        base = np.searchsorted(keys, d, side="left")
        end = np.searchsorted(keys, d + 0.9995, side="left")
        q = d + _squash(np.where(np.isfinite(v), v, 0.0))
        left = np.searchsorted(keys, q, side="left")
        right = np.searchsorted(keys, q, side="right")
        size = end - base
        pct = np.where(size >= 20, ((left - base) + (right - base)) / 2.0 / np.maximum(size, 1) * 100.0, np.nan)
        out.append(np.where(np.isfinite(v), pct, np.nan))
    return out


def _tick(price: np.ndarray) -> np.ndarray:
    return np.where(price >= 1.0, 0.01, 0.0001)


def plan_levels(close: np.ndarray, atr_abs: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Einstiegslimit, Stop und 2-R-Kursziel wie :func:`tradeplan.plan_trade` (gerundet auf den Kursschritt)."""
    tick = _tick(close)
    with np.errstate(invalid="ignore"):
        entry = np.ceil(np.round((close + tp.ENTRY_ATR * atr_abs) / tick, 6)) * tick
        stop = np.floor(np.round((entry - tp.STOP_ATR * atr_abs) / tick, 6)) * tick
        target = np.floor(np.round((entry + tp.TARGET_R * (entry - stop)) / tick, 6)) * tick
    return np.round(entry, 6), np.round(stop, 6), np.round(target, 6)


def statuses(hist: StockHistory, pctile: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Status der Signalregel je Sitzung (0 = nicht bewertbar, 1 = kein Kauf, 2 = beobachten, 3 = Kaufsignal) und die
    Planwerte (Einstieg, Stop, Ziel) – nur mit Daten bis zum jeweiligen Tag."""
    c = hist.close
    n = len(c)
    atr_abs = hist.atr_pct * c
    usd = hist.turnover_local * (hist.unit_to_eur if _finite(hist.unit_to_eur) else np.nan) * (hist.usd_per_eur if _finite(hist.usd_per_eur) else np.nan)
    with np.errstate(invalid="ignore", divide="ignore"):
        known = (np.isfinite(c) & (c > 0) & np.isfinite(hist.sma20) & np.isfinite(hist.sma50) & np.isfinite(hist.high20) & (hist.high20 > 0)
                 & np.isfinite(hist.rvol) & np.isfinite(atr_abs) & (atr_abs > 0) & np.isfinite(pctile) & np.isfinite(usd))
        known &= np.arange(n) >= WARMUP
        basis = usd >= tp.MIN_TURNOVER_USD
        setup = (c > hist.sma20) & (hist.sma20 > hist.sma50) & (pctile >= tp.MIN_STRENGTH_PCTILE) & (c / hist.high20 >= tp.NEAR_HIGH) & (hist.rvol >= tp.MIN_RVOL)
        entry, stop, target = plan_levels(c, atr_abs)
        valid_plan = (stop > 0) & ((entry - stop) >= tp.MIN_RISK_SHARE * entry)
        ext = (c - hist.sma20) / atr_abs
        timing_known = np.isfinite(hist.rsi) & np.isfinite(hist.gap)
        timing_ok = (ext <= tp.MAX_EXTENSION_ATR) & (hist.rsi <= tp.MAX_RSI) & (hist.gap <= tp.MAX_GAP_ATR * hist.atr_pct)
    status = np.zeros(n, dtype=np.int8)
    status[known] = 1
    ok_setup = known & basis & setup & valid_plan
    status[ok_setup] = 2  # Ausgangslage stimmt: beobachten, solange der Zeitpunkt nicht passt
    status[ok_setup & timing_known & timing_ok] = 3
    return status, entry, stop, target


def episode_starts(status: np.ndarray, value: int) -> np.ndarray:
    """Erste Sitzung jeder zusammenhängenden Folge mit ``value``."""
    hit = status == value
    prev = np.concatenate([[False], hit[:-1]])
    return np.nonzero(hit & ~prev)[0]


def simulate(hist: StockHistory, t: int, entry: float | None, stop: float | None, target: float | None, cost: float) -> Outcome:
    """Ein Fall ab dem Signaltag ``t``: Kauf am nächsten Handelstag (Limit ``entry`` oder, ohne Limit, zur Eröffnung)."""
    n = len(hist.close)
    f = t + 1
    if f >= n:
        return Outcome(filled=False)
    o, lo, hi = hist.open[f], hist.low[f], hist.high[f]
    if not np.isfinite(o):
        return Outcome(filled=False)
    if entry is None:
        fill = float(o)
    elif o <= entry:
        fill = float(o)
    elif np.isfinite(lo) and lo <= entry:
        fill = float(entry)
    else:
        return Outcome(filled=False)
    out = Outcome(filled=True)
    # Halten ohne Stop und Ziel: Schlusskurs nach h Handelstagen (Tag 1 = Kauftag)
    for h in HOLD_HORIZONS:
        k = t + h
        out.hold[h] = (float(hist.close[k]) / fill - 1.0 - cost) if k < n and np.isfinite(hist.close[k]) else None
    if stop is None or target is None:
        return out
    exit_price = None
    exit_day = None
    lowest = fill
    for k in range(f, min(n, t + max(DAY_HORIZONS) + 1)):
        ok, kl, kh = hist.open[k], hist.low[k], hist.high[k]
        if k > f and np.isfinite(ok) and ok <= stop:
            exit_price, exit_day = float(ok), k
        elif np.isfinite(kl) and kl <= stop:
            exit_price, exit_day = float(stop), k
        elif k > f and np.isfinite(ok) and ok >= target:
            exit_price, exit_day = float(ok), k
        elif np.isfinite(kh) and kh >= target:
            exit_price, exit_day = float(target), k
        if np.isfinite(kl):
            lowest = min(lowest, float(kl))
        for h in DAY_HORIZONS:
            if h in out.plan:
                continue
            if exit_day is not None:
                out.plan[h] = exit_price / fill - 1.0 - cost
                out.plan_drawdown[h] = min(lowest, exit_price) / fill - 1.0
            elif k == t + h:
                close = hist.close[k]
                out.plan[h] = (float(close) / fill - 1.0 - cost) if np.isfinite(close) else None
                out.plan_drawdown[h] = lowest / fill - 1.0
        if exit_day is not None:
            break
    for h in DAY_HORIZONS:
        out.plan.setdefault(h, None)
        out.plan_drawdown.setdefault(h, None)
    return out


def stats(values: list[float], drawdowns: list[float] | None = None) -> dict:
    """Kennzahlen einer Liste von Nettorenditen (Anteile)."""
    arr = np.array([v for v in values if v is not None and math.isfinite(v)], dtype=np.float64)
    n = int(len(arr))
    if n == 0:
        return {"n": 0, "belegt": False}
    losses = arr[arr < 0]
    out = {
        "n": n,
        "belegt": n >= MIN_CASES,
        "mittel": round(float(arr.mean()), 5),
        "median": round(float(np.median(arr)), 5),
        "treffer": round(float((arr > 0).mean()), 4),
        "verlust_mittel": round(float(losses.mean()), 5) if len(losses) else None,
        "gewinn_mittel": round(float(arr[arr > 0].mean()), 5) if (arr > 0).any() else None,
        "schlechtester": round(float(arr.min()), 5),
        "bester": round(float(arr.max()), 5),
    }
    if drawdowns:
        dd = np.array([d for d in drawdowns if d is not None and math.isfinite(d)], dtype=np.float64)
        if len(dd):
            out["rueckgang_mittel"] = round(float(dd.mean()), 5)
            out["rueckgang_groesster"] = round(float(dd.min()), 5)
    return out


def _cost_fn(costs):
    """Kosten (Anteil) für Kauf und Verkauf einer Position von 1.000 € – Bausteine wie im Spielgeld-Robo."""
    if costs is None:
        return lambda turnover_eur, currency: 0.0
    from ..aktienpilot import kosten

    def fn(turnover_eur: float | None, currency: str | None) -> float:
        return kosten.rundreise_pct(costs, turnover_eur=turnover_eur, currency=currency or "EUR", position_eur=POSITION_EUR) / 100.0

    return fn


def compute(histories: list[StockHistory], *, costs=None, cutoff_day: int | None = None) -> Result:
    """Rückblick über alle Aktien. ``costs``: :class:`aktienpilot.config.CostConfig` (None = ohne Kosten, nur Prüfungen)."""
    cost_of = _cost_fn(costs)
    pct = strength_percentiles(histories)
    groups: dict[str, dict] = {name: {"faelle": 0, "ausgefuehrt": 0, "plan": {h: [] for h in DAY_HORIZONS}, "dd": {h: [] for h in DAY_HORIZONS},
                                      "hold": {h: [] for h in HOLD_HORIZONS}} for name in ("kaufsignal", "beobachten", "vergleich")}
    market = {"steigend": [], "fallend": []}
    per_stock: dict[str, dict] = {}
    all_statuses: dict[str, np.ndarray] = {}
    first_day = None
    last_day = None
    # Marktlage je Tag: Median der 20-Tage-Veränderung aller Aktien (steigend > 0)
    median_r20 = _median_by_day(histories)
    for hist, p in zip(histories, pct):
        n = len(hist.close)
        if n <= WARMUP + 1:
            continue
        status, entry, stop, target = statuses(hist, p)
        all_statuses[hist.isin] = status
        turnover_eur = hist.turnover_local * (hist.unit_to_eur if _finite(hist.unit_to_eur) else np.nan)
        own: list[float] = []
        for value, name in ((3, "kaufsignal"), (2, "beobachten")):
            for t in episode_starts(status, value).tolist():
                if t + 1 >= n:
                    continue
                g = groups[name]
                g["faelle"] += 1
                cost = cost_of(float(turnover_eur[t]) if np.isfinite(turnover_eur[t]) else None, hist.currency)
                if value == 3:
                    res = simulate(hist, t, float(entry[t]), float(stop[t]), float(target[t]), cost)
                else:
                    res = simulate(hist, t, None, None, None, cost)  # kein Limit: zur nächsten Eröffnung
                day = int(hist.days[t])
                first_day = day if first_day is None else min(first_day, day)
                last_day = day if last_day is None else max(last_day, day)
                if not res.filled:
                    continue
                g["ausgefuehrt"] += 1
                for h in HOLD_HORIZONS:
                    g["hold"][h].append(res.hold.get(h))
                if value == 3:
                    for h in DAY_HORIZONS:
                        g["plan"][h].append(res.plan.get(h))
                        g["dd"][h].append(res.plan_drawdown.get(h))
                    ten = res.plan.get(10)
                    if ten is not None:
                        own.append(ten)
                        m = median_r20.get(day)
                        if m is not None:
                            market["steigend" if m > 0 else "fallend"].append(ten)
        # Vergleichsgruppe: alle Aktien mit Mindestumsatz an jedem zehnten Handelstag (Kauf zur nächsten Eröffnung)
        eligible = np.nonzero(status >= 1)[0]
        usd = hist.turnover_local * (hist.unit_to_eur if _finite(hist.unit_to_eur) else np.nan) * (hist.usd_per_eur if _finite(hist.usd_per_eur) else np.nan)
        for t in eligible[::BASELINE_STEP].tolist():
            if t + 1 >= n or not (np.isfinite(usd[t]) and usd[t] >= tp.MIN_TURNOVER_USD):
                continue
            g = groups["vergleich"]
            g["faelle"] += 1
            res = simulate(hist, t, None, None, None, cost_of(float(turnover_eur[t]) if np.isfinite(turnover_eur[t]) else None, hist.currency))
            if not res.filled:
                continue
            g["ausgefuehrt"] += 1
            for h in HOLD_HORIZONS:
                g["hold"][h].append(res.hold.get(h))
        arr = np.array(own, dtype=np.float64)
        per_stock[hist.isin] = {
            "n": int(len(arr)),
            "mittel": round(float(arr.mean()), 5) if len(arr) else None,
            "treffer": round(float((arr > 0).mean()), 4) if len(arr) else None,
            "belegt": bool(len(arr) >= MIN_CASES_STOCK),
        }
    payload = {
        "version": VERSION,
        "regel": tp.RULE_VERSION,
        "zeitraum": {"von": first_day, "bis": last_day, "stichtag": cutoff_day},
        "mindestens_faelle": MIN_CASES,
        "mindestens_faelle_aktie": MIN_CASES_STOCK,
        "horizonte": {"tage": list(DAY_HORIZONS), "monate": [[m, h] for m, h in MONTH_HORIZONS]},
        "kosten": {"position_eur": POSITION_EUR, "mit_kosten": costs is not None},
        "status": {},
        "markt": {name: stats(values) for name, values in market.items()},
        "hinweise": HINWEISE,
    }
    for name, g in groups.items():
        entry = {"faelle": g["faelle"], "ausgefuehrt": g["ausgefuehrt"], "halten": {str(h): stats(g["hold"][h]) for h in HOLD_HORIZONS}}
        if name == "kaufsignal":
            entry["plan"] = {str(h): stats(g["plan"][h], g["dd"][h]) for h in DAY_HORIZONS}
        payload["status"][name] = entry
    return Result(payload=payload, per_stock=per_stock, statuses=all_statuses)


def _median_by_day(histories: list[StockHistory]) -> dict[int, float]:
    """Median der 20-Tage-Veränderung aller Aktien je Tag (mindestens 20 Werte) – Marktlage steigend/fallend."""
    days = [h.days[np.isfinite(h.r20)] for h in histories]
    vals = [h.r20[np.isfinite(h.r20)] for h in histories]
    if not days:
        return {}
    d = np.concatenate(days).astype(np.int64)
    v = np.concatenate(vals)
    if not len(d):
        return {}
    order = np.argsort(d, kind="stable")
    d, v = d[order], v[order]
    unique, start, counts = np.unique(d, return_index=True, return_counts=True)
    return {int(day): float(np.median(v[s:s + c])) for day, s, c in zip(unique, start, counts) if c >= 20}
