"""Signale je Aktie: kurzfristig (Trading), langfristig (etwa 12 Monate) und Gesamtwertung – ab 1.6
(`signale-v1`), Gesamtwertung ab 1.7 (`signale-v2`).

Grundsatz: Jede Zahl ist nachvollziehbar. Jedes Signal ist eine Punktzahl von 0 bis 100 (50 = neutral)
mit einem kurzen Satz, woraus sie entsteht. Fehlen die Daten für ein Signal, entfällt es – es wird nie
geschätzt. Die Ampel fasst die Punkte nach festen Regeln zusammen. Das ist keine Anlageempfehlung,
sondern eine geordnete Zusammenfassung öffentlich verfügbarer Signale.

**Kurzfristig** (Tage bis wenige Wochen; worauf Day- und Swingtrader achten) – alles aus den eigenen
Tageskursen, deshalb auch rückwirkend berechenbar und an der Vergangenheit überprüfbar:

* Relatives Volumen: Umsatz der letzten Sitzung gegenüber dem Durchschnitt der 20 Sitzungen davor.
* Schwung: Kursänderung der letzten 20 Sitzungen im Verhältnis zur üblichen Schwankung der Aktie.
* Steigetage: Anteil der Steigetage der letzten 10 Sitzungen und aktuelle Serie.
* Trendlage: Schlusskurs über der 20- und 50-Tage-Linie, 20- über 50-Tage-Linie.
* Ausbruch: Abstand zum höchsten Schlusskurs der letzten 20 Sitzungen.
* RSI (14): Stärke ohne Überhitzung (am besten zwischen 55 und 70).
* Nachrichten und Community (nur aktuell, nicht rückwirkend): Tendenz der Schlagzeilen, Stimmung.

**Langfristig** – Kursziele der Analysten (erwartete Steigerung, Anteil „Kaufen“, Zahl der
Analysten), Bewertung (Trading Central bei US-Aktien, erwartetes KGV im Branchenvergleich, PEG),
Wachstum und Finanzen (Gewinn- und Umsatzwachstum, Rendite, Marge, Verschuldung), langfristiger
Trend (1 Jahr, 200-Tage-Linie) und die Richtung der Analystenurteile.

**Gesamtwertung** (ab `signale-v2`, eine Zahl von 0 bis 100 für die Kandidatenliste):
35 % Steig-Konstanz (an wie vielen Handelstagen der letzten 30, 60 und 90 Kalendertage die Aktie
gestiegen ist), 35 % Kursziel-Potenzial (erwartete Steigerung bis zum Ø Kursziel, mit wenigen
Analysten anteilig), 15 % Aufmerksamkeit & Schwung (das kurzfristige Urteil) und 15 % Qualität
(Bewertung, Wachstum, Richtung der Analysten).

**Wahrscheinlichkeit** (``calibrate``): Für jede Aktie und jeden vergangenen Tag wird der technische
Teil des kurzfristigen Signals genauso berechnet wie heute; gezählt wird, wie oft der Kurs danach
5 bzw. 20 Sitzungen später höher stand. So entsteht eine echte Trefferquote je Punktebereich. Für
die Steig-Konstanz gilt dasselbe mit 20 und 60 Sitzungen. Kursziele lassen sich so nicht prüfen
(keine Historie) – die Quote gilt nur für den Kursverlauf-Teil.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

VERSION = "signale-v2"

# Gewichte innerhalb der Horizonte (fehlende Signale fallen heraus, die übrigen werden neu gewichtet)
SHORT_WEIGHTS = {"volumen": 0.20, "schwung": 0.25, "steigetage": 0.15, "trendlage": 0.20, "ausbruch": 0.10, "rsi": 0.10}
SHORT_NEWS_WEIGHT = 0.15  # Nachrichten und Community zusammen im kurzfristigen Urteil
LONG_WEIGHTS = {"kursziel": 0.35, "bewertung": 0.20, "wachstum": 0.20, "langfristtrend": 0.15, "analystenrichtung": 0.10}

# Gesamtwertung (ab signale-v2): Steig-Konstanz und Kursziel zählen am meisten
TOTAL_WEIGHTS = {"konstanz": 0.35, "kursziel": 0.35, "kurzfristig": 0.15, "qualitaet": 0.15}
QUALITY_WEIGHTS = {"bewertung": 0.4, "wachstum": 0.4, "analystenrichtung": 0.2}
QUALITY_NEUTRAL = 50.0  # ohne Angaben zur Qualität
CONSISTENCY_PERIODS = (30, 60, 90)  # Kalendertage, wie die Zeiträume der Ranglisten
CONSISTENCY_FLOOR = 0.40  # Anteil Anstiegstage für 0 Punkte
CONSISTENCY_TOP = 0.65  # Anteil Anstiegstage für 100 Punkte
CONSISTENCY_FALLING_CAP = 25.0  # höchstens so viele Punkte für einen Zeitraum, in dem der Kurs gefallen ist
CONSISTENCY_MAX_GAP = 7  # Startsitzung höchstens so viele Tage vor dem Zielstart (wie bei den Ranglisten)
CONSISTENCY_MIN_COMPARISONS = 5
TARGET_CURVE = 0.35  # Kursziel-Punkte = 100 × (1 − e^(−Steigerung / 0,35))
TARGET_FULL_ANALYSTS = 5  # ab so vielen Analysten zählt das Kursziel voll
TOTAL_STRONG = 65.0
TOTAL_MEDIUM = 50.0

TOTAL_LABELS = {
    "konstanz": "Steig-Konstanz (30/60/90 Tage)",
    "kursziel": "Kursziel-Potenzial",
    "kurzfristig": "Aufmerksamkeit & Schwung",
    "qualitaet": "Qualität",
}

TOTAL_EXPLAIN = {
    "konstanz": "An wie vielen Handelstagen die Aktie in den letzten 30, 60 und 90 Kalendertagen gestiegen ist (Schlusskurs über dem des Vortags). 40 % Anstiegstage = 0 Punkte, 52,5 % = 50, 65 % und mehr = 100; jeder Zeitraum zählt ein Drittel. Liegt der Kurs am Ende eines Zeitraums unter dem Anfangskurs, zählt dieser Zeitraum höchstens 25 Punkte. So liegt eine Aktie, die über drei Monate immer wieder steigt, vor einer mit nur einem kurzen Schub.",
    "kursziel": "Erwartete Steigerung bis zum Ø Kursziel aller Quellen: +10 % = 25 Punkte, +25 % = 51, +50 % = 76, +100 % = 94. Mit weniger als 5 Analysten zählt sie anteilig (1 Analyst = 20 %, 3 Analysten = 60 %), weil einzelne Ziele unsicher sind. Ohne Kursziel oder mit Kursziel unter dem Kurs: 0 Punkte.",
    "kurzfristig": "Das kurzfristige Urteil (0–100): Umsatz im Vergleich zum Üblichen, Schwung, Steigetage der letzten 10 Sitzungen, Trendlage, Ausbruch, RSI, Nachrichten und Community – zeigt, ob die Aktie gerade gefragt ist.",
    "qualitaet": "Aus dem langfristigen Urteil: Bewertung (40 %), Wachstum und Finanzen (40 %) und Richtung der Analystenurteile (20 %). Ohne Angaben neutral mit 50 Punkten.",
}

TOTAL_RULE = (
    "Gesamtwertung = 35 % Steig-Konstanz + 35 % Kursziel-Potenzial + 15 % Aufmerksamkeit & Schwung + 15 % Qualität. "
    "Ab 65 Punkten stark (grün), ab 50 mittel (gelb), darunter schwach. Ohne mindestens 60 Tage Kurshistorie keine Gesamtwertung."
)

LABELS = {
    "volumen": "Relatives Volumen",
    "schwung": "Schwung (20 Tage)",
    "steigetage": "Steigetage",
    "trendlage": "Trendlage",
    "ausbruch": "Ausbruch",
    "rsi": "RSI (14)",
    "nachrichten": "Nachrichten",
    "community": "Community",
    "kursziel": "Kursziel",
    "bewertung": "Bewertung",
    "wachstum": "Wachstum & Finanzen",
    "langfristtrend": "Langfristiger Trend",
    "analystenrichtung": "Richtung der Analysten",
}

EXPLAIN = {
    "volumen": "Umsatz (Stück) der letzten Sitzung im Verhältnis zum Durchschnitt der 20 Sitzungen davor. Ab etwa dem 1,5-Fachen ist ungewöhnlich viel los – oft der Grund für starke Bewegungen. 1× = 50 Punkte, 2× = 75, 4× = 100.",
    "schwung": "Kursänderung der letzten 20 Sitzungen, geteilt durch die übliche Schwankung der Aktie über diese Zeit. So zählt ein Anstieg bei einer ruhigen Aktie mehr als derselbe Anstieg bei einer sehr schwankenden. 0 = 50 Punkte, je Schwankungseinheit ±20 Punkte.",
    "steigetage": "Anteil der Tage mit steigendem Schlusskurs unter den letzten 10 Sitzungen (60 %) und die aktuelle Serie in Folge (40 %, je Tag ±12,5 Punkte). Je öfter und länger eine Aktie steigt, desto gefragter ist sie gerade.",
    "trendlage": "Liegt der Schlusskurs über der 20- und der 50-Tage-Linie (gleitende Durchschnitte) und die 20- über der 50-Tage-Linie? Je erfüllter Bedingung ein Drittel der Punkte.",
    "ausbruch": "Abstand zum höchsten Schlusskurs der letzten 20 Sitzungen. Ein neues 20-Tage-Hoch (Ausbruch) gibt 100 Punkte, 3 % darunter 75, 15 % darunter 0.",
    "rsi": "Relative-Stärke-Index über 14 Sitzungen (0–100). 55–70: kräftig, aber nicht überhitzt (beste Punkte). Über 75: überkauft, Rücksetzer häufiger. Unter 40: schwach.",
    "nachrichten": "Tendenz der Schlagzeilen der letzten Tage (einfache Wortliste: z. B. „hochgestuft“, „Rekord“ positiv, „Gewinnwarnung“, „Klage“ negativ) und – bei US-Aktien – Hoch- und Herabstufungen der Analysten. Erkennt keine Zusammenhänge; die Schlagzeilen selbst stehen in der Einzelansicht.",
    "community": "Stimmung der Beiträge auf Stocktwits: Anteil der als „bullish“ (steigend) markierten unter allen markierten Beiträgen. Wenige Beiträge zählen schwächer. Die Zahl der Beiträge je Tag zeigt den „Hype“.",
    "kursziel": "Erwartete Steigerung bis zum durchschnittlichen Kursziel der Analysten (etwa 12 Monate), dazu der Anteil „Kaufen“-Empfehlungen. Mit wenigen Analysten zählt das Signal schwächer (1 Analyst: ein Viertel, 3: die Hälfte, 10: drei Viertel).",
    "bewertung": "Ist die Aktie im Vergleich günstig? Bei US-Aktien die Einschätzung von Trading Central (unterbewertet/fair/überbewertet), für alle das erwartete Kurs-Gewinn-Verhältnis im Vergleich zur eigenen Branche und das PEG (KGV geteilt durch Gewinnwachstum; unter 1 gilt als günstig).",
    "wachstum": "Erwartetes Gewinn- und Umsatzwachstum im nächsten Geschäftsjahr, Eigenkapitalrendite, Nettomarge, Verschuldung und freier Cashflow – jeweils im Vergleich zu allen Aktien mit Angaben.",
    "langfristtrend": "Kursentwicklung über etwa ein Jahr im Vergleich zu allen Aktien und die Lage zur 200-Tage-Linie bzw. zum Jahreshoch.",
    "analystenrichtung": "Werden die Analysten optimistischer? Anteil „Kaufen“ heute gegenüber vor drei Monaten und – bei US-Aktien – angehobene gegenüber gesenkten Kurszielen der letzten 90 Tage.",
}


# --------------------------------------------------------------------------- Hilfen


def clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return float(min(hi, max(lo, x)))


def _finite(x) -> bool:
    return x is not None and isinstance(x, (int, float, np.floating, np.integer)) and math.isfinite(float(x))


def pct_de(x: float | None, digits: int = 1, sign: bool = True) -> str:
    """„+12,4 %“ (deutsches Format)."""
    if not _finite(x):
        return "–"
    value = float(x) * 100.0
    text = f"{value:+.{digits}f}" if sign else f"{value:.{digits}f}"
    return text.replace(".", ",").replace("-", "−") + " %"


def num_de(x: float | None, digits: int = 1) -> str:
    if not _finite(x):
        return "–"
    return f"{float(x):.{digits}f}".replace(".", ",").replace("-", "−")


def weighted(scores: dict[str, float | None], weights: dict[str, float]) -> tuple[float | None, int]:
    """Gewichteter Mittelwert der vorhandenen Punkte und Zahl der vorhandenen Signale."""
    total = weight = 0.0
    n = 0
    for key, w in weights.items():
        value = scores.get(key)
        if value is None or not math.isfinite(value):
            continue
        total += w * value
        weight += w
        n += 1
    if weight <= 0:
        return None, 0
    return total / weight, n


def tone_of(points: float | None, *, good: float = 60.0, bad: float = 40.0) -> int:
    if points is None:
        return 0
    return 1 if points >= good else -1 if points <= bad else 0


# ------------------------------------------------------- technische Reihen (vektorisiert)


def _shift_ratio(close: np.ndarray, k: int) -> np.ndarray:
    out = np.full(len(close), np.nan)
    if len(close) > k:
        out[k:] = close[k:] / close[:-k] - 1.0
    return out


def _rolling_mean(x: np.ndarray, window: int) -> np.ndarray:
    """Gleitender Mittelwert ohne NaN-Werte im Fenster; NaN, wenn das Fenster nicht vollständig ist."""
    out = np.full(len(x), np.nan)
    if len(x) < window:
        return out
    valid = np.isfinite(x)
    values = np.where(valid, x, 0.0)
    csum = np.concatenate([[0.0], np.cumsum(values)])
    ccount = np.concatenate([[0], np.cumsum(valid.astype(np.int64))])
    sums = csum[window:] - csum[:-window]
    counts = ccount[window:] - ccount[:-window]
    with np.errstate(invalid="ignore", divide="ignore"):
        out[window - 1 :] = np.where(counts == window, sums / np.maximum(counts, 1), np.nan)
    return out


def _rolling_std(x: np.ndarray, window: int) -> np.ndarray:
    mean = _rolling_mean(x, window)
    mean_sq = _rolling_mean(x * x, window)
    with np.errstate(invalid="ignore"):
        var = np.maximum(mean_sq - mean * mean, 0.0) * window / max(window - 1, 1)
    return np.sqrt(var)


def _rolling_max(x: np.ndarray, window: int) -> np.ndarray:
    out = np.full(len(x), np.nan)
    if len(x) < window:
        return out
    view = np.lib.stride_tricks.sliding_window_view(x, window)
    out[window - 1 :] = np.max(view, axis=1)
    return out


def _rsi(close: np.ndarray, period: int = 14) -> np.ndarray:
    """RSI nach Wilder."""
    n = len(close)
    out = np.full(n, np.nan)
    if n <= period:
        return out
    delta = np.diff(close)
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)
    avg_gain = gain[:period].mean()
    avg_loss = loss[:period].mean()
    for t in range(period, n):
        if t > period:
            avg_gain = (avg_gain * (period - 1) + gain[t - 1]) / period
            avg_loss = (avg_loss * (period - 1) + loss[t - 1]) / period
        if avg_loss == 0:
            out[t] = 100.0 if avg_gain > 0 else 50.0
        else:
            rs = avg_gain / avg_loss
            out[t] = 100.0 - 100.0 / (1.0 + rs)
    return out


def _streak(close: np.ndarray) -> np.ndarray:
    """Serie: +k = k Steigetage in Folge, −k = k Falltage in Folge (bis einschließlich t)."""
    n = len(close)
    out = np.zeros(n, dtype=np.int64)
    for t in range(1, n):
        if close[t] > close[t - 1]:
            out[t] = out[t - 1] + 1 if out[t - 1] > 0 else 1
        elif close[t] < close[t - 1]:
            out[t] = out[t - 1] - 1 if out[t - 1] < 0 else -1
        else:
            out[t] = 0
    return out


@dataclass
class TechSeries:
    """Technische Kennzahlen je Sitzung (Index wie die Eingabe)."""

    close: np.ndarray
    r1: np.ndarray
    r5: np.ndarray
    r20: np.ndarray
    r60: np.ndarray
    r120: np.ndarray
    r250: np.ndarray
    sigma: np.ndarray  # Standardabweichung der täglichen Log-Renditen (60 Sitzungen)
    z20: np.ndarray
    up10: np.ndarray
    streak: np.ndarray
    rvol: np.ndarray
    gap: np.ndarray
    sma20: np.ndarray
    sma50: np.ndarray
    sma200: np.ndarray
    high20: np.ndarray
    high250: np.ndarray
    rsi: np.ndarray
    atr_pct: np.ndarray
    turnover: np.ndarray  # Ø Umsatz × Kurs der letzten 20 Sitzungen in Notierungseinheit


def tech_series(open_: np.ndarray | None, high: np.ndarray | None, low: np.ndarray | None, close: np.ndarray, volume: np.ndarray | None) -> TechSeries:
    close = np.asarray(close, dtype=np.float64)
    n = len(close)
    vol = np.asarray(volume, dtype=np.float64) if volume is not None else np.full(n, np.nan)
    vol = np.where(vol > 0, vol, np.nan)  # 0 oder unbekannt zählt nicht als Umsatz
    lr = np.full(n, np.nan)
    if n > 1:
        lr[1:] = np.log(close[1:] / close[:-1])
    sigma = _rolling_std(lr, 60)
    sigma = np.where(np.isfinite(sigma), sigma, _rolling_std(lr, 20))
    with np.errstate(invalid="ignore", divide="ignore"):
        log20 = np.full(n, np.nan)
        if n > 20:
            log20[20:] = np.log(close[20:] / close[:-20])
        z20 = log20 / (sigma * math.sqrt(20.0))
        z20 = np.where(sigma > 1e-6, z20, np.nan)
        up = np.where(np.isfinite(lr), (lr > 0).astype(np.float64), np.nan)
        up10 = _rolling_mean(up, 10)
        prev_vol = np.full(n, np.nan)
        if n > 1:
            prev_vol[1:] = _rolling_mean(vol, 20)[:-1]
        rvol = vol / prev_vol
        gap = np.full(n, np.nan)
        if open_ is not None and n > 1:
            o = np.asarray(open_, dtype=np.float64)
            gap[1:] = o[1:] / close[:-1] - 1.0
        h = np.asarray(high, dtype=np.float64) if high is not None else np.full(n, np.nan)
        lo = np.asarray(low, dtype=np.float64) if low is not None else np.full(n, np.nan)
        prev_close = np.concatenate([[np.nan], close[:-1]])
        tr_hl = np.where(np.isfinite(h) & np.isfinite(lo), np.fmax(np.fmax(h - lo, np.abs(h - prev_close)), np.abs(lo - prev_close)), np.nan)
        tr = np.where(np.isfinite(tr_hl), tr_hl, np.abs(close - prev_close))
        atr_pct = _rolling_mean(tr, 14) / close
        turnover = _rolling_mean(close * vol, 20)
    return TechSeries(
        close=close,
        r1=_shift_ratio(close, 1),
        r5=_shift_ratio(close, 5),
        r20=_shift_ratio(close, 20),
        r60=_shift_ratio(close, 60),
        r120=_shift_ratio(close, 120),
        r250=_shift_ratio(close, 250),
        sigma=sigma,
        z20=z20,
        up10=up10,
        streak=_streak(close),
        rvol=rvol,
        gap=gap,
        sma20=_rolling_mean(close, 20),
        sma50=_rolling_mean(close, 50),
        sma200=_rolling_mean(close, 200),
        high20=_rolling_max(close, 20),
        high250=_rolling_max(close, min(250, n)) if n >= 60 else np.full(n, np.nan),
        rsi=_rsi(close),
        atr_pct=atr_pct,
        turnover=turnover,
    )


def short_component_series(ts: TechSeries) -> dict[str, np.ndarray]:
    """Punkte der technischen Kurzfrist-Signale je Sitzung (NaN = nicht berechenbar)."""
    with np.errstate(invalid="ignore", divide="ignore"):
        volumen = np.clip(50.0 + 25.0 * np.log2(ts.rvol), 0, 100)
        schwung = np.clip(50.0 + 20.0 * ts.z20, 0, 100)
        streak_pts = np.clip(50.0 + 12.5 * ts.streak, 0, 100)
        steigetage = np.where(np.isfinite(ts.up10), 0.6 * ts.up10 * 100.0 + 0.4 * streak_pts, np.nan)
        cond = np.vstack([ts.close > ts.sma20, ts.close > ts.sma50, ts.sma20 > ts.sma50]).astype(np.float64)
        known = np.isfinite(ts.sma20) & np.isfinite(ts.sma50)
        trendlage = np.where(known, cond.sum(axis=0) / 3.0 * 100.0, np.nan)
        ratio = ts.close / ts.high20
        ausbruch = np.where(ratio >= 0.9999, 100.0, np.clip(75.0 * (ratio - 0.85) / 0.12, 0, 75))
        ausbruch = np.where(np.isfinite(ratio), ausbruch, np.nan)
        rsi = ts.rsi
        rsi_pts = np.where(
            rsi < 40, np.clip(rsi / 40.0 * 30.0, 0, 30),
            np.where(rsi < 55, 30.0 + (rsi - 40.0) / 15.0 * 60.0,
                     np.where(rsi <= 70, 90.0 + (rsi - 55.0) / 15.0 * 10.0,
                              np.where(rsi <= 80, 100.0 - (rsi - 70.0) * 5.0, np.clip(50.0 - (rsi - 80.0) * 3.0, 10, 50)))),
        )
        rsi_pts = np.where(np.isfinite(rsi), rsi_pts, np.nan)
    return {"volumen": volumen, "schwung": schwung, "steigetage": steigetage, "trendlage": trendlage, "ausbruch": ausbruch, "rsi": rsi_pts}


def technical_score_series(components: dict[str, np.ndarray]) -> np.ndarray:
    """Gewichteter technischer Kurzfrist-Wert je Sitzung (mind. 4 der 6 Signale nötig)."""
    keys = list(SHORT_WEIGHTS)
    stack = np.vstack([components[k] for k in keys])
    weights = np.array([SHORT_WEIGHTS[k] for k in keys])[:, None]
    valid = np.isfinite(stack)
    total = np.where(valid, stack * weights, 0.0).sum(axis=0)
    wsum = np.where(valid, weights, 0.0).sum(axis=0)
    with np.errstate(invalid="ignore", divide="ignore"):
        score = total / wsum
    return np.where(valid.sum(axis=0) >= 4, score, np.nan)


@dataclass
class ConsistencySeries:
    """Steig-Konstanz je Sitzung (Index wie die Eingabe). Je Zeitraum (30/60/90 Kalendertage): Zahl der
    Anstiegstage, Zahl der Vergleiche (Handelstage), Kursveränderung und Punkte; −1 bzw. NaN = nicht berechenbar."""

    points: np.ndarray
    ups: dict[int, np.ndarray]
    comparisons: dict[int, np.ndarray]
    returns: dict[int, np.ndarray]
    period_points: dict[int, np.ndarray]

    def at(self, t: int) -> list[dict]:
        """Werte der Sitzung ``t`` je Zeitraum (für Anzeige und Texte)."""
        out = []
        for period in CONSISTENCY_PERIODS:
            comps = int(self.comparisons[period][t])
            if comps < 0:
                out.append({"tage": period, "steigtage": None, "vergleiche": None, "rendite": None, "punkte": None})
                continue
            out.append({
                "tage": period,
                "steigtage": int(self.ups[period][t]),
                "vergleiche": comps,
                "rendite": float(self.returns[period][t]),
                "punkte": float(self.period_points[period][t]),
            })
        return out


def consistency_points(share: np.ndarray, ret: np.ndarray) -> np.ndarray:
    """Punkte eines Zeitraums aus dem Anteil der Anstiegstage; gefallener Kurs höchstens 25 Punkte."""
    with np.errstate(invalid="ignore"):
        points = np.clip((share - CONSISTENCY_FLOOR) / (CONSISTENCY_TOP - CONSISTENCY_FLOOR) * 100.0, 0.0, 100.0)
        return np.where(ret > 0, points, np.minimum(points, CONSISTENCY_FALLING_CAP))


def consistency_series(days: np.ndarray, close: np.ndarray) -> ConsistencySeries:
    """Steig-Konstanz für jede Sitzung: Anteil der Tage mit höherem Schlusskurs als am Vortag in den letzten
    30, 60 und 90 Kalendertagen. Start eines Zeitraums ist – wie bei den Ranglisten – die letzte Sitzung am
    oder vor „heute − Zeitraum“ (höchstens 7 Tage davor); gezählt werden alle Vergleiche bis heute.
    Die Punkte sind das Mittel der vorhandenen Zeiträume; 30 und 60 Tage müssen vorhanden sein."""
    days = np.asarray(days, dtype=np.int64)
    close = np.asarray(close, dtype=np.float64)
    n = len(close)
    up = np.zeros(n, dtype=np.int64)
    if n > 1:
        with np.errstate(invalid="ignore"):
            up[1:] = (close[1:] > close[:-1]).astype(np.int64)
    cum = np.cumsum(up)
    idx = np.arange(n)
    ups: dict[int, np.ndarray] = {}
    comps: dict[int, np.ndarray] = {}
    rets: dict[int, np.ndarray] = {}
    pts: dict[int, np.ndarray] = {}
    for period in CONSISTENCY_PERIODS:
        if n == 0:
            ups[period] = comps[period] = np.zeros(0, dtype=np.int64)
            rets[period] = pts[period] = np.zeros(0)
            continue
        target = days - period
        start = np.searchsorted(days, target, side="right") - 1
        safe = np.clip(start, 0, n - 1)
        count = idx - safe
        valid = (start >= 0) & ((target - days[safe]) <= CONSISTENCY_MAX_GAP) & (count >= CONSISTENCY_MIN_COMPARISONS)
        rises = cum - cum[safe]
        with np.errstate(invalid="ignore", divide="ignore"):
            share = rises / np.maximum(count, 1)
            ret = close / close[safe] - 1.0
        ups[period] = np.where(valid, rises, -1)
        comps[period] = np.where(valid, count, -1)
        rets[period] = np.where(valid, ret, np.nan)
        pts[period] = np.where(valid, consistency_points(share, ret), np.nan)
    if n == 0:
        return ConsistencySeries(np.zeros(0), ups, comps, rets, pts)
    stack = np.vstack([pts[p] for p in CONSISTENCY_PERIODS])
    finite = np.isfinite(stack)
    total = np.where(finite, stack, 0.0).sum(axis=0)
    count = finite.sum(axis=0)
    with np.errstate(invalid="ignore", divide="ignore"):
        mean = total / np.maximum(count, 1)
    points = np.where(finite[0] & finite[1], mean, np.nan)
    return ConsistencySeries(points, ups, comps, rets, pts)


def target_points(upside: float | None, analysts: int) -> float:
    """Kursziel-Teil der Gesamtwertung: 100 × (1 − e^(−Steigerung/0,35)), mit weniger als 5 Analysten anteilig."""
    if upside is None or not math.isfinite(upside) or upside <= 0 or analysts <= 0:
        return 0.0
    base = 100.0 * (1.0 - math.exp(-upside / TARGET_CURVE))
    return base * min(1.0, analysts / TARGET_FULL_ANALYSTS)


def total_grade(total: float | None) -> str:
    """Stufe der Gesamtwertung: stark (grün), mittel (gelb), schwach; „ohne“ ohne Wertung."""
    if total is None:
        return "ohne"
    return "stark" if total >= TOTAL_STRONG else "mittel" if total >= TOTAL_MEDIUM else "schwach"


# ---------------------------------------------------------------- Kalibrierung


@dataclass
class Calibration:
    """Trefferquote je Punktebereich eines Werts (aus der eigenen Kurshistorie): wie oft der Kurs ``h``
    Sitzungen später höher stand und um wie viel im Mittel – je Punktebereich und für alle Fälle."""

    edges: list[float]
    horizons: tuple[int, ...]
    n: list[int]
    up: dict[int, list[float | None]]
    mean: dict[int, list[float | None]]
    base_up: dict[int, float | None]
    base_mean: dict[int, float | None]
    samples: int
    first_day: int | None
    last_day: int | None
    stocks: int

    def bucket(self, score: float | None) -> int | None:
        if score is None or not math.isfinite(score):
            return None
        for k in range(len(self.edges) - 1):
            if score < self.edges[k + 1] or k == len(self.edges) - 2:
                return k
        return None

    def probability(self, score: float | None) -> dict | None:
        """Trefferquote des Punktebereichs von ``score`` (``None``, wenn zu wenige Fälle)."""
        k = self.bucket(score)
        if k is None or self.up[self.horizons[0]][k] is None:
            return None
        out = {"bereich": [self.edges[k], min(100.0, self.edges[k + 1])], "faelle": self.n[k]}
        for h in self.horizons:
            out[f"steigt_{h}"] = self.up[h][k]
            out[f"mittel_{h}"] = self.mean[h][k]
        return out

    def as_dict(self) -> dict:
        out: dict = {"bereiche": self.edges, "horizonte": list(self.horizons), "faelle": self.n}
        for h in self.horizons:
            out[f"steigt_{h}"] = self.up[h]
            out[f"mittel_{h}"] = self.mean[h]
        for h in self.horizons:
            out[f"alle_steigt_{h}"] = self.base_up[h]
            out[f"alle_mittel_{h}"] = self.base_mean[h]
        out.update({"faelle_gesamt": self.samples, "erster_tag": self.first_day, "letzter_tag": self.last_day, "aktien": self.stocks})
        return out


CALIBRATION_EDGES = [0.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 100.0001]
CONSISTENCY_EDGES = [0.0, 20.0, 40.0, 60.0, 80.0, 100.0001]
MIN_BUCKET_CASES = 50


def calibrate(
    series: list[tuple[np.ndarray, np.ndarray, np.ndarray, bool]],
    *,
    horizons: tuple[int, ...] = (5, 20),
    edges: list[float] | None = None,
) -> Calibration:
    """``series``: je Aktie (Tage, Schlusskurse, Wert je Sitzung, handelbar?).

    Gezählt werden alle Tage mit Wert, für die ``horizons[0]`` Sitzungen später ein Kurs vorliegt (nur
    handelbare Aktien – sonst verzerren fortgeschriebene Kurse ohne Umsatz die Quote). Je Punktebereich
    und Horizont: Anteil der Fälle mit höherem Kurs und mittlere Veränderung (ab 50 Fällen)."""
    edges = list(edges or CALIBRATION_EDGES)
    scores: list[np.ndarray] = []
    forward: dict[int, list[np.ndarray]] = {h: [] for h in horizons}
    days: list[np.ndarray] = []
    stocks = 0
    first = horizons[0]
    for day_arr, close, values, tradable in series:
        if not tradable or len(close) < 30:
            continue
        n = len(close)
        fwd = {}
        for h in horizons:
            arr = np.full(n, np.nan)
            if n > h:
                arr[: n - h] = close[h:] / close[: n - h] - 1.0
            fwd[h] = arr
        mask = np.isfinite(values) & np.isfinite(fwd[first])
        if not mask.any():
            continue
        stocks += 1
        scores.append(np.asarray(values)[mask])
        for h in horizons:
            forward[h].append(fwd[h][mask])
        days.append(np.asarray(day_arr)[mask])
    buckets = len(edges) - 1
    if not scores:
        return Calibration(edges, tuple(horizons), [0] * buckets, {h: [None] * buckets for h in horizons}, {h: [None] * buckets for h in horizons},
                           {h: None for h in horizons}, {h: None for h in horizons}, 0, None, None, 0)
    s = np.concatenate(scores)
    d = np.concatenate(days)
    raw = {h: np.concatenate(forward[h]) for h in horizons}
    # Ausreißer (Datenfehler, Splits ohne Bereinigung) begrenzen, damit Mittelwerte nicht kippen
    clipped = {h: np.clip(raw[h], -0.9, 3.0) for h in horizons}
    n_list: list[int] = []
    up: dict[int, list[float | None]] = {h: [] for h in horizons}
    mean: dict[int, list[float | None]] = {h: [] for h in horizons}
    for k in range(buckets):
        sel = (s >= edges[k]) & (s < edges[k + 1])
        n_list.append(int(sel.sum()))
        for h in horizons:
            sel_h = sel & np.isfinite(raw[h])
            if sel_h.sum() >= MIN_BUCKET_CASES:
                up[h].append(round(float(np.mean(raw[h][sel_h] > 0)), 4))
                mean[h].append(round(float(np.mean(clipped[h][sel_h])), 5))
            else:
                up[h].append(None)
                mean[h].append(None)
    base_up: dict[int, float | None] = {}
    base_mean: dict[int, float | None] = {}
    for h in horizons:
        fin = np.isfinite(raw[h])
        base_up[h] = round(float(np.mean(raw[h][fin] > 0)), 4) if fin.any() else None
        base_mean[h] = round(float(np.mean(clipped[h][fin])), 5) if fin.any() else None
    return Calibration(
        edges=[round(e, 4) for e in edges],
        horizons=tuple(horizons),
        n=n_list,
        up=up,
        mean=mean,
        base_up=base_up,
        base_mean=base_mean,
        samples=int(len(s)),
        first_day=int(d.min()),
        last_day=int(d.max()),
        stocks=stocks,
    )


# ---------------------------------------------------------------- Einzelaktie


@dataclass
class StockInput:
    isin: str
    days: np.ndarray
    open: np.ndarray | None
    high: np.ndarray | None
    low: np.ndarray | None
    close: np.ndarray
    volume: np.ndarray | None
    unit_to_eur: float | None  # EUR je Kurseinheit (für Umsatz in EUR)
    unit_factor: float = 1.0  # Kurseinheit je Hauptwährung (z. B. 100 bei GBp)
    facts: dict | None = None
    valuation: dict | None = None  # Trading Central über Yahoo (nur US)
    nasdaq: dict | None = None  # zweite Kurszielquelle (nur US)
    news: list | None = None
    community: dict | None = None
    now_ts: float | None = None  # für „Meldungen der letzten Tage“
    weeks: tuple[np.ndarray, np.ndarray] | None = None  # Wochenschlusskurse (Vorauswahl der Umschichtungs-Regel)


@dataclass
class Component:
    key: str
    points: float | None
    text: str
    horizon: str  # „kurz“ oder „lang“

    @property
    def tone(self) -> int:
        return tone_of(self.points)

    def as_dict(self) -> dict:
        return {"key": self.key, "punkte": None if self.points is None else round(self.points, 1), "text": self.text, "ton": self.tone, "horizont": self.horizon}


@dataclass
class StockSignals:
    isin: str
    day: int | None
    close: float | None
    short: float | None
    short_tech: float | None
    short_light: str
    short_reason: str | None
    long: float | None
    long_light: str
    long_reason: str | None
    upside: float | None
    target: float | None
    target_low: float | None
    target_high: float | None
    target_sources: list[dict] = field(default_factory=list)
    analysts: int = 0
    buy_share: float | None = None
    tradable: bool = False
    turnover_eur: float | None = None
    components: list[Component] = field(default_factory=list)
    features: dict = field(default_factory=dict)
    probability: dict | None = None
    # Gesamtwertung (ab signale-v2)
    total: float | None = None
    total_parts: dict = field(default_factory=dict)
    total_grade: str = "ohne"
    consistency: list[dict] = field(default_factory=list)
    total_probability: dict | None = None

    @property
    def both_green(self) -> bool:
        return self.short_light == "gruen" and self.long_light == "gruen"


def _last(arr: np.ndarray) -> float | None:
    if arr is None or not len(arr):
        return None
    value = float(arr[-1])
    return value if math.isfinite(value) else None


def _news_points(news: list | None, now_ts: float | None, facts: dict | None) -> tuple[float | None, str, dict]:
    """Tendenz der Schlagzeilen der letzten 3 Tage und Hoch-/Herabstufungen der letzten 30 Tage."""
    info = {"meldungen_3_tage": 0, "positiv": 0, "negativ": 0, "hochstufungen_30": 0, "herabstufungen_30": 0}
    parts = []
    values = []
    if news and now_ts:
        recent = [n for n in news if (now_ts - float(n.get("zeit") or 0)) <= 3 * 86400]
        info["meldungen_3_tage"] = len(recent)
        pos = sum(1 for n in recent if n.get("tendenz") == 1)
        neg = sum(1 for n in recent if n.get("tendenz") == -1)
        info["positiv"], info["negativ"] = pos, neg
        if pos + neg >= 1:
            values.append((pos - neg) / (pos + neg) * min(1.0, (pos + neg) / 3.0))
        if recent:
            parts.append(f"{len(recent)} Meldungen in 3 Tagen ({pos} positiv, {neg} negativ)")
    actions = (facts or {}).get("urteile") or []
    if actions and now_ts:
        today = int(now_ts // 86400)
        recent_actions = [a for a in actions if a.get("tag") is not None and today - int(a["tag"]) <= 30]
        up = sum(1 for a in recent_actions if a.get("aktion") == "hochgestuft" or a.get("ziel_aktion") == "angehoben")
        down = sum(1 for a in recent_actions if a.get("aktion") == "herabgestuft" or a.get("ziel_aktion") == "gesenkt")
        info["hochstufungen_30"], info["herabstufungen_30"] = up, down
        if up + down >= 1:
            values.append((up - down) / (up + down) * min(1.0, (up + down) / 3.0))
            parts.append(f"{up} Anhebungen, {down} Senkungen in 30 Tagen")
    if not values:
        return None, "keine aktuellen Meldungen", info
    return clamp(50.0 + 50.0 * float(np.mean(values))), "; ".join(parts), info


def _community_points(community: dict | None) -> tuple[float | None, str, dict]:
    if not community:
        return None, "keine Community-Daten", {}
    bull = int(community.get("bullish") or 0)
    bear = int(community.get("bearish") or 0)
    tagged = bull + bear
    info = {"bullish": bull, "bearish": bear, "beitraege": community.get("beitraege"), "je_tag": community.get("je_tag")}
    if tagged < 3:
        return None, f"{community.get('beitraege') or 0} Beiträge, zu wenige mit Stimmung", info
    share = bull / tagged
    weight = tagged / (tagged + 5.0)
    points = 50.0 + (share * 100.0 - 50.0) * weight
    per_day = community.get("je_tag")
    hype = f", {num_de(per_day, 1)} Beiträge/Tag" if _finite(per_day) else ""
    return clamp(points), f"{round(share * 100)} % bullish ({tagged} markierte Beiträge{hype})", info


def unit_scale(facts_price: float | None, close: float | None) -> float | None:
    """Faktor, mit dem Kursziele in die Kurseinheit der eigenen Kurse umgerechnet werden (1, 100, 0,01),
    oder ``None``, wenn die Einheiten nicht zusammenpassen."""
    if not _finite(facts_price) or not _finite(close) or facts_price <= 0 or close <= 0:
        return 1.0 if _finite(close) and not _finite(facts_price) else None
    ratio = close / facts_price
    for factor in (1.0, 100.0, 0.01):
        if factor / 1.6 <= ratio <= factor * 1.6:
            return factor
    return None


def target_sources(facts: dict | None, nasdaq: dict | None, scale: float, now_ts: float | None) -> list[dict]:
    """Kursziel-Quellen: Yahoo-Konsens, Nasdaq-Konsens (US) und Ø der Einzelziele der letzten 90 Tage (US)."""
    out = []
    analysts = (facts or {}).get("analysten") or {}
    if _finite(analysts.get("ziel_mittel")) and (analysts.get("anzahl") or 0) > 0:
        out.append({
            "quelle": "Yahoo Finance (Konsens)",
            "ziel": analysts["ziel_mittel"] * scale,
            "tief": analysts["ziel_tief"] * scale if _finite(analysts.get("ziel_tief")) else None,
            "hoch": analysts["ziel_hoch"] * scale if _finite(analysts.get("ziel_hoch")) else None,
            "anzahl": int(analysts.get("anzahl") or 0),
        })
    if nasdaq and _finite(nasdaq.get("ziel")):
        out.append({"quelle": "Nasdaq (Konsens)", "ziel": nasdaq["ziel"] * scale, "tief": (nasdaq.get("tief") or 0) * scale or None,
                    "hoch": (nasdaq.get("hoch") or 0) * scale or None, "anzahl": nasdaq.get("anzahl")})
    actions = (facts or {}).get("urteile") or []
    if actions and now_ts:
        today = int(now_ts // 86400)
        latest: dict[str, float] = {}
        for action in sorted(actions, key=lambda a: a.get("tag") or 0, reverse=True):
            firm = action.get("haus")
            if not firm or firm in latest or action.get("tag") is None or today - int(action["tag"]) > 90:
                continue
            if _finite(action.get("ziel")):
                latest[firm] = float(action["ziel"])
        if len(latest) >= 2:
            values = list(latest.values())
            out.append({"quelle": f"Einzelziele der Häuser (90 Tage, {len(values)} Häuser)", "ziel": float(np.mean(values)) * scale,
                        "tief": min(values) * scale, "hoch": max(values) * scale, "anzahl": len(values)})
    return out


@dataclass
class UniverseStats:
    """Vergleichswerte über alle Aktien (für Perzentile der langfristigen Signale)."""

    r250: np.ndarray
    pe_by_sector: dict[str, np.ndarray]
    growth: dict[str, np.ndarray]  # Kennzahl → sortierte Werte

    @staticmethod
    def percentile(sorted_values: np.ndarray, x: float | None) -> float | None:
        if x is None or not math.isfinite(x) or sorted_values is None or len(sorted_values) < 20:
            return None
        left = np.searchsorted(sorted_values, x, side="left")
        right = np.searchsorted(sorted_values, x, side="right")
        return float((left + right) / 2.0 / len(sorted_values) * 100.0)


GROWTH_KEYS = (
    ("gewinn_naechstes_jahr", "wachstum", True),
    ("umsatz_naechstes_jahr", "wachstum", True),
    ("eigenkapitalrendite", "finanzen", True),
    ("nettomarge", "finanzen", True),
    ("verschuldung", "finanzen", False),
)


def build_universe_stats(inputs: list[StockInput], series: dict[str, TechSeries]) -> UniverseStats:
    r250 = []
    pe: dict[str, list[float]] = {}
    growth: dict[str, list[float]] = {key: [] for key, _, _ in GROWTH_KEYS}
    for item in inputs:
        ts = series.get(item.isin)
        if ts is not None:
            value = _last(ts.r250)
            if value is None and item.facts:
                value = ((item.facts.get("risiko") or {}).get("veraenderung_52w"))
            if _finite(value):
                r250.append(float(value))
        facts = item.facts or {}
        sector = (facts.get("branche") or {}).get("sektor")
        fpe = (facts.get("bewertung") or {}).get("kgv_erwartet")
        if sector and _finite(fpe) and 0 < fpe < 500:
            pe.setdefault(sector, []).append(float(fpe))
        for key, group, _ in GROWTH_KEYS:
            value = (facts.get(group) or {}).get(key)
            if _finite(value):
                growth[key].append(float(value))
    return UniverseStats(
        r250=np.sort(np.array(r250)),
        pe_by_sector={k: np.sort(np.array(v)) for k, v in pe.items()},
        growth={k: np.sort(np.array(v)) for k, v in growth.items()},
    )


MIN_TURNOVER_EUR = 250_000.0  # Ø Tagesumsatz, ab dem kurzfristiges Handeln realistisch ist


def evaluate(item: StockInput, ts: TechSeries | None, comps: dict[str, np.ndarray] | None, tech: np.ndarray | None,
             stats: UniverseStats, calibration: Calibration | None, consistency: ConsistencySeries | None = None,
             consistency_calibration: Calibration | None = None) -> StockSignals:
    """Alle Signale einer Aktie zum letzten Kurstag."""
    now_ts = item.now_ts
    day = int(item.days[-1]) if len(item.days) else None
    close = float(item.close[-1]) if len(item.close) else None
    components: list[Component] = []
    features: dict = {}

    # ---------------- kurzfristig
    short_scores: dict[str, float | None] = {}
    if ts is not None and comps is not None:
        f = {
            "r1": _last(ts.r1), "r5": _last(ts.r5), "r20": _last(ts.r20), "r60": _last(ts.r60), "r120": _last(ts.r120), "r250": _last(ts.r250),
            "z20": _last(ts.z20), "up10": _last(ts.up10), "serie": int(ts.streak[-1]) if len(ts.streak) else 0, "rvol": _last(ts.rvol),
            "gap": _last(ts.gap), "sma20": _last(ts.sma20), "sma50": _last(ts.sma50), "sma200": _last(ts.sma200), "hoch20": _last(ts.high20),
            "hoch250": _last(ts.high250), "rsi": _last(ts.rsi), "atr": _last(ts.atr_pct), "schwankung": _last(ts.sigma),
        }
        turnover_local = _last(ts.turnover)
        f["umsatz_eur"] = turnover_local * item.unit_to_eur if turnover_local is not None and _finite(item.unit_to_eur) else None
        features.update(f)
        for key in SHORT_WEIGHTS:
            short_scores[key] = _last(comps[key])
        texts = {
            "volumen": f"Umsatz {num_de(f['rvol'], 1)}× des 20-Tage-Durchschnitts" if f["rvol"] is not None else "Umsatz unbekannt",
            "schwung": f"{pct_de(f['r20'])} in 20 Sitzungen ({num_de(f['z20'], 1)} Schwankungseinheiten)" if f["r20"] is not None else "zu kurze Kurshistorie",
            "steigetage": (
                f"an {round((f['up10'] or 0) * 10)} von 10 Tagen gestiegen"
                + (f", {f['serie']} Tage in Folge" if f["serie"] >= 2 else f", {-f['serie']} Falltage in Folge" if f["serie"] <= -2 else "")
            ) if f["up10"] is not None else "zu kurze Kurshistorie",
            "trendlage": _trend_text(f, close),
            "ausbruch": _breakout_text(f, close),
            "rsi": f"RSI {num_de(f['rsi'], 0)}" + (" – überkauft" if (f["rsi"] or 0) > 75 else " – kräftig" if 55 <= (f["rsi"] or 0) <= 70 else " – schwach" if (f["rsi"] or 100) < 40 else "") if f["rsi"] is not None else "zu kurze Kurshistorie",
        }
        for key in SHORT_WEIGHTS:
            components.append(Component(key, short_scores[key], texts[key], "kurz"))
    news_pts, news_text, news_info = _news_points(item.news, now_ts, item.facts)
    comm_pts, comm_text, comm_info = _community_points(item.community)
    features["nachrichten"] = news_info
    features["community"] = comm_info
    components.append(Component("nachrichten", news_pts, news_text, "kurz"))
    components.append(Component("community", comm_pts, comm_text, "kurz"))
    short_tech = _last(tech) if tech is not None else None
    soft = [p for p in (news_pts, comm_pts) if p is not None]
    if short_tech is not None:
        short = short_tech if not soft else (1 - SHORT_NEWS_WEIGHT) * short_tech + SHORT_NEWS_WEIGHT * float(np.mean(soft))
    else:
        short = None
    turnover_eur = features.get("umsatz_eur")
    tradable = bool(_finite(turnover_eur) and turnover_eur >= MIN_TURNOVER_EUR)

    # ---------------- langfristig
    facts = item.facts or {}
    analysts = facts.get("analysten") or {}
    scale = unit_scale(analysts.get("kurs"), close)
    sources = target_sources(facts, item.nasdaq, scale, now_ts) if scale is not None else []
    target = float(np.mean([s["ziel"] for s in sources])) if sources else None
    lows = [s["tief"] for s in sources if _finite(s.get("tief"))]
    highs = [s["hoch"] for s in sources if _finite(s.get("hoch"))]
    upside = target / close - 1.0 if target is not None and close else None
    n_analysts = int(analysts.get("anzahl") or 0)
    buy = analysts.get("kaufen_anteil")
    rec = analysts.get("empfehlung_mittel")
    if upside is not None:
        s_up = clamp(50.0 + 100.0 * upside)
        s_rec = clamp((5.0 - rec) / 4.0 * 100.0) if _finite(rec) else (buy * 100.0 if _finite(buy) else 50.0)
        raw = 0.6 * s_up + 0.4 * s_rec
        n_eff = max(n_analysts, max((s.get("anzahl") or 0) for s in sources) if sources else 0)
        weight = n_eff / (n_eff + 3.0)
        target_pts = 50.0 + (raw - 50.0) * weight
        buy_text = f", {round(buy * 100)} % Kaufen" if _finite(buy) else ""
        target_text = f"erwartete Steigerung {pct_de(upside, 0)} bis zum Ø Kursziel, {n_eff} Analysten{buy_text}"
    else:
        target_pts = None
        target_text = "keine Kursziele" if scale is not None else "Kursziel in anderer Einheit – nicht vergleichbar"
    components.append(Component("kursziel", target_pts, target_text, "lang"))

    val_parts, val_points = [], []
    tc = item.valuation or {}
    if tc.get("bewertung"):
        tc_pts = {"unterbewertet": 75.0, "fair": 50.0, "ueberbewertet": 25.0}[tc["bewertung"]]
        if _finite(tc.get("abschlag")):
            tc_pts = clamp(50.0 + 150.0 * float(tc["abschlag"]))
        val_points += [tc_pts, tc_pts]  # doppelt gewichtet
        label = {"unterbewertet": "unterbewertet", "fair": "fair bewertet", "ueberbewertet": "überbewertet"}[tc["bewertung"]]
        val_parts.append(f"Trading Central: {label}" + (f" ({pct_de(tc.get('abschlag'), 0)} zum fairen Wert)" if _finite(tc.get("abschlag")) else ""))
    valuation = facts.get("bewertung") or {}
    sector = (facts.get("branche") or {}).get("sektor")
    fpe = valuation.get("kgv_erwartet")
    if sector and _finite(fpe) and fpe > 0:
        pct = UniverseStats.percentile(stats.pe_by_sector.get(sector), float(fpe))
        if pct is not None:
            val_points.append(100.0 - pct)
            val_parts.append(f"erwartetes KGV {num_de(fpe, 1)} – günstiger als {round(100 - pct)} % der Branche")
    elif _finite(fpe) and fpe <= 0:
        val_parts.append("Verlust erwartet (KGV negativ)")
    peg = valuation.get("peg")
    if _finite(peg) and peg > 0:
        val_points.append(75.0 if peg < 1 else 50.0 if peg <= 2 else 25.0)
        val_parts.append(f"PEG {num_de(peg, 2)}")
    components.append(Component("bewertung", float(np.mean(val_points)) if val_points else None, "; ".join(val_parts) or "keine Bewertungsdaten", "lang"))

    growth_points, growth_parts = [], []
    for key, group, higher_is_better in GROWTH_KEYS:
        value = (facts.get(group) or {}).get(key)
        pct = UniverseStats.percentile(stats.growth.get(key), value if _finite(value) else None)
        if pct is None:
            continue
        growth_points.append(pct if higher_is_better else 100.0 - pct)
        label = {"gewinn_naechstes_jahr": "Gewinn nächstes Jahr", "umsatz_naechstes_jahr": "Umsatz nächstes Jahr", "eigenkapitalrendite": "Eigenkapitalrendite",
                 "nettomarge": "Nettomarge", "verschuldung": "Verschuldung"}[key]
        growth_parts.append(f"{label} {num_de(value, 1)}×" if key == "verschuldung" else f"{label} {pct_de(value, 0)}")
    fcf = (facts.get("finanzen") or {}).get("free_cashflow_positiv")
    if fcf is not None and growth_points:
        growth_points.append(70.0 if fcf else 30.0)
        growth_parts.append("freier Cashflow positiv" if fcf else "freier Cashflow negativ")
    components.append(Component("wachstum", float(np.mean(growth_points)) if len(growth_points) >= 2 else None,
                                "; ".join(growth_parts[:4]) or "keine Angaben", "lang"))

    trend_points, trend_parts = [], []
    r_year = features.get("r250")
    if r_year is None:
        r_year = (facts.get("risiko") or {}).get("veraenderung_52w")
    pct = UniverseStats.percentile(stats.r250, r_year if _finite(r_year) else None)
    if pct is not None:
        trend_points.append(pct)
        trend_parts.append(f"{pct_de(r_year, 0)} in einem Jahr (besser als {round(pct)} % der Aktien)")
    if _finite(features.get("sma200")) and close:
        above = close > features["sma200"]
        trend_points.append(75.0 if above else 25.0)
        trend_parts.append("über der 200-Tage-Linie" if above else "unter der 200-Tage-Linie")
    high_year = (facts.get("risiko") or {}).get("hoch_52w")
    if _finite(high_year) and scale is not None and close:
        dist = close / (high_year * scale) - 1.0
        if -0.95 < dist < 0.2:
            trend_points.append(clamp(100.0 + 200.0 * min(dist, 0.0)))
            trend_parts.append("am Jahreshoch" if dist > -0.02 else f"{pct_de(dist, 0)} unter dem Jahreshoch")
    components.append(Component("langfristtrend", float(np.mean(trend_points)) if trend_points else None, "; ".join(trend_parts) or "zu kurze Kurshistorie", "lang"))

    direction_values, direction_parts = [], []
    trend_rows = facts.get("empfehlungen") or []
    now_row = next((r for r in trend_rows if r.get("monat") == "0m"), None)
    old_row = next((r for r in trend_rows if r.get("monat") == "-3m"), None) or next((r for r in trend_rows if r.get("monat") == "-2m"), None)
    from ..providers.yahoo import buy_share as _buy_share

    b_now, b_old = _buy_share(now_row), _buy_share(old_row)
    if b_now is not None and b_old is not None:
        direction_values.append(clamp((b_now - b_old) * 2.0, -1.0, 1.0))
        direction_parts.append(f"Anteil Kaufen {round(b_now * 100)} % (vor 3 Monaten {round(b_old * 100)} %)")
    actions = facts.get("urteile") or []
    if actions and now_ts:
        today = int(now_ts // 86400)
        recent = [a for a in actions if a.get("tag") is not None and today - int(a["tag"]) <= 90]
        up = sum(1 for a in recent if a.get("ziel_aktion") == "angehoben" or a.get("aktion") == "hochgestuft")
        down = sum(1 for a in recent if a.get("ziel_aktion") == "gesenkt" or a.get("aktion") == "herabgestuft")
        if up + down >= 2:
            direction_values.append((up - down) / (up + down))
            direction_parts.append(f"{up} Kursziele angehoben, {down} gesenkt (90 Tage)")
    components.append(Component("analystenrichtung", clamp(50.0 + 50.0 * float(np.mean(direction_values))) if direction_values else None,
                                "; ".join(direction_parts) or "keine Veränderung erkennbar", "lang"))

    long_scores = {c.key: c.points for c in components if c.horizon == "lang"}
    long, long_n = weighted(long_scores, LONG_WEIGHTS)

    # ---------------- Ampeln
    short_light, short_reason = _short_light(short, short_scores, features, tradable)
    long_light, long_reason = _long_light(long, long_n, upside, n_analysts, buy, target_pts)

    probability = None
    if calibration is not None and short_tech is not None and tradable:
        probability = calibration.probability(short_tech)

    # ---------------- Gesamtwertung (ab signale-v2)
    total = None
    parts: dict[str, float | None] = {}
    periods: list[dict] = []
    total_probability = None
    if consistency is not None and len(consistency.points):
        periods = consistency.at(len(consistency.points) - 1)
        cons_pts = _last(consistency.points)
        n_eff = max([n_analysts] + [int(s.get("anzahl") or 0) for s in sources]) if sources else n_analysts
        quality, _ = weighted({key: long_scores.get(key) for key in QUALITY_WEIGHTS}, QUALITY_WEIGHTS)
        parts = {
            "konstanz": cons_pts,
            "kursziel": target_points(upside, n_eff) if upside is not None else 0.0,
            "kurzfristig": short,
            "qualitaet": quality if quality is not None else QUALITY_NEUTRAL,
        }
        if cons_pts is not None and short is not None:
            total = sum(TOTAL_WEIGHTS[key] * float(parts[key]) for key in TOTAL_WEIGHTS)
        if consistency_calibration is not None and cons_pts is not None and tradable:
            total_probability = consistency_calibration.probability(cons_pts)
        for entry in periods:
            if entry["vergleiche"] is not None:
                features[f"steig_{entry['tage']}"] = entry["steigtage"]
                features[f"tage_{entry['tage']}"] = entry["vergleiche"]
                features[f"r_{entry['tage']}k"] = entry["rendite"]

    return StockSignals(
        isin=item.isin,
        day=day,
        close=close,
        short=None if short is None else round(short, 1),
        short_tech=None if short_tech is None else round(short_tech, 1),
        short_light=short_light,
        short_reason=short_reason,
        long=None if long is None else round(long, 1),
        long_light=long_light,
        long_reason=long_reason,
        upside=None if upside is None else round(upside, 4),
        target=target,
        target_low=min(lows) if lows else None,
        target_high=max(highs) if highs else None,
        target_sources=sources,
        analysts=n_analysts,
        buy_share=buy if _finite(buy) else None,
        tradable=tradable,
        turnover_eur=turnover_eur,
        components=components,
        features=features,
        probability=probability,
        total=None if total is None else round(total, 1),
        total_parts={key: (None if value is None else round(float(value), 1)) for key, value in parts.items()},
        total_grade=total_grade(total),
        consistency=periods,
        total_probability=total_probability,
    )


def consistency_text(periods: list[dict]) -> str:
    """„an 15 von 21 Handelstagen gestiegen (30 Tage), 31 von 42 (60 Tage), …“ – für Listen und Texte."""
    parts = []
    for entry in periods:
        if entry.get("vergleiche") is None:
            continue
        parts.append(f"{entry['steigtage']} von {entry['vergleiche']} ({entry['tage']} Tage)")
    return ("gestiegen an " + ", ".join(parts) + " Handelstagen") if parts else "zu kurze Kurshistorie"


def _trend_text(f: dict, close: float | None) -> str:
    s20, s50 = f.get("sma20"), f.get("sma50")
    if s20 is None or s50 is None or close is None:
        return "zu kurze Kurshistorie"
    if close > s20 and close > s50:
        base = "über der 20- und der 50-Tage-Linie"
    elif close > s20:
        base = "über der 20-, unter der 50-Tage-Linie"
    elif close > s50:
        base = "unter der 20-, über der 50-Tage-Linie"
    else:
        base = "unter der 20- und der 50-Tage-Linie"
    return base + ("; 20 über 50 – Aufwärtstrend" if s20 > s50 else "; 20 unter 50")


def _breakout_text(f: dict, close: float | None) -> str:
    high = f.get("hoch20")
    if high is None or close is None or high <= 0:
        return "zu kurze Kurshistorie"
    ratio = close / high
    if ratio >= 0.9999:
        return "neues 20-Tage-Hoch (Ausbruch)"
    return f"{pct_de(ratio - 1.0, 1)} unter dem 20-Tage-Hoch"


def _short_light(short: float | None, scores: dict, features: dict, tradable: bool) -> tuple[str, str | None]:
    if short is None:
        return "grau", "zu kurze Kurshistorie"
    if not tradable:
        return "grau", "zu wenig Umsatz für kurzfristiges Handeln"
    trend = scores.get("trendlage")
    r20 = features.get("r20")
    if short >= 65 and (trend or 0) >= 66 and (r20 or 0) > 0:
        return "gruen", None
    if short < 40 or ((trend is not None and trend <= 34) and (r20 is not None and r20 < 0)):
        return "rot", "fallender Kurs unter den Durchschnittslinien" if (trend or 100) <= 34 else "schwache Signale"
    return "gelb", None


def _long_light(long: float | None, n: int, upside: float | None, analysts: int, buy: float | None, target_pts: float | None) -> tuple[str, str | None]:
    if long is None or n < 2:
        return "grau", "zu wenige Angaben"
    if upside is not None and upside < 0:
        return "rot", "Kursziel unter dem aktuellen Kurs"
    if long < 40:
        return "rot", "schwache langfristige Signale"
    if upside is None:
        return "gelb", "ohne Kursziel der Analysten – höchstens Gelb"
    if long >= 62 and upside >= 0.10 and analysts >= 3 and (buy is None or buy >= 0.5):
        return "gruen", None
    if analysts < 3:
        return "gelb", "weniger als 3 Analysten – höchstens Gelb"
    return "gelb", None


@dataclass
class SignalBatch:
    results: list[StockSignals]
    calibration: Calibration
    stats: UniverseStats
    consistency_calibration: Calibration | None = None


def compute_all(inputs: list[StockInput]) -> SignalBatch:
    """Signale für alle Aktien: technische Reihen, Kalibrierung aus der Historie, Vergleichswerte, Urteile,
    Steig-Konstanz und Gesamtwertung."""
    series: dict[str, TechSeries] = {}
    comps: dict[str, dict[str, np.ndarray]] = {}
    techs: dict[str, np.ndarray] = {}
    consistency: dict[str, ConsistencySeries] = {}
    history = []
    history_consistency = []
    for item in inputs:
        if len(item.close) < 25:
            continue
        ts = tech_series(item.open, item.high, item.low, item.close, item.volume)
        c = short_component_series(ts)
        tech = technical_score_series(c)
        cons = consistency_series(item.days, item.close)
        series[item.isin], comps[item.isin], techs[item.isin], consistency[item.isin] = ts, c, tech, cons
        turnover = _last(ts.turnover)
        tradable = bool(turnover is not None and _finite(item.unit_to_eur) and turnover * item.unit_to_eur >= MIN_TURNOVER_EUR)
        history.append((item.days, ts.close, tech, tradable))
        history_consistency.append((item.days, ts.close, cons.points, tradable))
    calibration = calibrate(history)
    consistency_calibration = calibrate(history_consistency, horizons=(20, 60), edges=CONSISTENCY_EDGES)
    stats = build_universe_stats(inputs, series)
    results = [
        evaluate(item, series.get(item.isin), comps.get(item.isin), techs.get(item.isin), stats, calibration,
                 consistency.get(item.isin), consistency_calibration)
        for item in inputs
    ]
    return SignalBatch(results=results, calibration=calibration, stats=stats, consistency_calibration=consistency_calibration)
