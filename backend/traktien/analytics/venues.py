"""Abgleich mit einem zweiten Börsenplatz (``boersenplatz-v2``).

Für die vorderen Plätze beider Rendite-Ranglisten misst der Lauf die Kursrendite zusätzlich an
einem zweiten Handelsplatz derselben ISIN – bevorzugt Xetra, dann Frankfurt, wo auch Trade
Republic handelt – über dieselben Kalendertage und mit den Schlusskursen dieses Handelsplatzes.
Verglichen wird in der Währung der Referenznotierung (EZB-Referenzkurse, wenn die Währungen
verschieden sind).

Welcher Schlusskurs des Vergleichsplatzes zu Start- und Enddatum der Referenz gehört, bestimmt ab
``boersenplatz-v2`` dessen Börsenkalender: Hatte der Vergleichsplatz an dem Tag eine Sitzung, zählt
nur der Schlusskurs genau dieses Tages; an Tagen ohne Sitzung dort die letzte Sitzung davor
(höchstens ``max_gap_days`` Kalendertage früher). Fehlt der Schlusskurs dieser Sitzung beim
Kursanbieter, fehlt der Vergleich („Vergleichskurse fehlen“). Bis ``boersenplatz-v1`` galt der
letzte gelieferte Schlusskurs bis 4 Tage vorher – bei einer Lieferlücke des Anbieters (Yahoo,
12.10.2026, Europa) wurde so der Freitagskurs mit dem Montagskurs der Referenz verglichen und fast
jede Aktie mit großer Montagsbewegung als auffällig gemeldet. Ohne Kalender des Vergleichsplatzes
gilt weiter die Regel von v1.

Auffällig ist ein Fenster, wenn

* die Wertentwicklung (Endkurs / Startkurs) am Vergleichsplatz um mehr als die Schwelle von der
  Referenz abweicht:  |ln((1 + r_Vergleich) / (1 + r_Referenz))| > ln(1 + Schwelle), oder
* der Endkurs am Vergleichsplatz um mehr als die Schwelle vom Endkurs der Referenz abweicht
  (betrifft dann alle Fenster der Aktie, weil alle denselben Endkurs haben).

Der Abgleich ist ein Hinweis. Er ändert weder Rendite noch Rangfolge; die Referenzbörse bleibt
maßgeblich (Methodik, Abschnitt Referenznotierung). Fehlende Vergleichskurse werden nicht ersetzt.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from .fx import FxRates

VERSION = "boersenplatz-v2"

# Ergebnis je Aktie (Suche nach dem zweiten Börsenplatz und Kursabruf)
INSTRUMENT_STATUS = {
    "geprueft": {"kurz": "geprüft", "text": "Zweiter Börsenplatz gefunden und Schlusskurse geladen."},
    "kein_vergleichsplatz": {
        "kurz": "kein zweiter Börsenplatz",
        "text": "Zur ISIN gibt es bei der Identitätsquelle keine weitere unterstützte Notierung (OTC-Märkte zählen nicht).",
    },
    "abruf_fehlgeschlagen": {"kurz": "Vergleichskurse nicht abrufbar", "text": "Der Kursanbieter lieferte für den zweiten Börsenplatz keine Tageskurse."},
    "nicht_geprueft": {"kurz": "nicht geprüft", "text": "Zeitbudget oder Anbieterlimit des Laufs erreicht; der nächste Lauf prüft weiter."},
}

# Ergebnis je Aktie und Zeitraum
PAIR_STATUS = {
    "ok": {"kurz": "unauffällig", "text": "Wertentwicklung und Endkurs stimmen am zweiten Börsenplatz innerhalb der Schwelle überein."},
    "abweichung": {
        "kurz": "Kursabweichung zwischen Börsenplätzen",
        "text": "Wertentwicklung oder Endkurs weichen am zweiten Börsenplatz um mehr als die Schwelle ab – Kurse prüfen (Datenfehler, Kapitalmaßnahme, Handelsaussetzung).",
    },
    "keine_kurse": {
        "kurz": "Vergleichskurse fehlen",
        "text": (
            "Am zweiten Börsenplatz fehlt der Schlusskurs zum Start- oder Enddatum (an Tagen ohne Handel dort: "
            "der Schlusskurs der letzten Sitzung davor, höchstens wenige Tage früher). Es wird nicht auf ältere Kurse ausgewichen."
        ),
    },
    "wechselkurs_fehlt": {"kurz": "Wechselkurs fehlt", "text": "Für die Umrechnung in die Referenzwährung fehlt ein EZB-Referenzkurs."},
}


@dataclass(frozen=True)
class VenueSettings:
    top_n: int = 10
    preferred: tuple[str, ...] = ("XETR", "XFRA")
    max_return_dev: float = 0.10
    max_level_dev: float = 0.10
    max_gap_days: int = 4
    max_instruments: int = 600


@dataclass
class AltSeries:
    """Schlusskurse am zweiten Börsenplatz (splitbereinigt, wie geliefert)."""

    symbol: str
    exchange_key: str
    exchange_name: str
    currency: str | None  # Hauptwährung, z. B. GBP
    price_unit: str | None  # wie geliefert, z. B. GBp
    unit_factor: float  # Kurseinheit → Hauptwährung
    days: np.ndarray
    close: np.ndarray


@dataclass
class PairResult:
    status: str
    r_alt: float | None = None  # Rendite am Vergleichsplatz, in Referenzwährung umgerechnet
    dev: float | None = None  # (1 + r_alt) / (1 + r_ref) − 1
    d0: int | None = None  # Kurstage am Vergleichsplatz
    d1: int | None = None
    p0: float | None = None  # Schlusskurse am Vergleichsplatz in gelieferter Einheit
    p1: float | None = None


@dataclass
class InstrumentVenue:
    status: str
    symbol: str | None = None
    exchange_key: str | None = None
    exchange_name: str | None = None
    currency: str | None = None
    price_unit: str | None = None
    level: float | None = None  # Endkurs Vergleichsplatz (umgerechnet) / Endkurs Referenz − 1
    end_day: int | None = None
    end_price: float | None = None
    level_flagged: bool = False
    pairs: dict[int, PairResult] = field(default_factory=dict)  # Spalte (h − 1) → Ergebnis

    @property
    def flagged(self) -> bool:
        return any(p.status == "abweichung" for p in self.pairs.values())


@dataclass
class VenueCheck:
    """Ergebnis des Abgleichs für einen Datenstand."""

    version: str
    settings: VenueSettings
    candidates: int = 0  # Aktien unter den ersten ``top_n`` Plätzen mindestens einer Rendite-Rangliste
    results: dict[int, InstrumentVenue] = field(default_factory=dict)  # Instrumentindex → Ergebnis
    note: str | None = None
    aborted: bool = False  # wegen eines Fehlers übersprungen: keine Ergebnisse, keine Kennzeichen

    def counts(self) -> dict:
        by_status: dict[str, int] = {}
        pairs: dict[str, int] = {}
        for result in self.results.values():
            by_status[result.status] = by_status.get(result.status, 0) + 1
            for pair in result.pairs.values():
                pairs[pair.status] = pairs.get(pair.status, 0) + 1
        return {
            "kandidaten": self.candidates,
            "aktien": dict(sorted(by_status.items())),
            "auffaellige_aktien": sum(1 for r in self.results.values() if r.flagged),
            "aktie_zeitraum": dict(sorted(pairs.items())),
        }


def candidate_indices(rankings: dict, windows, top_n: int, max_instruments: int) -> tuple[list[int], int]:
    """Aktien unter den ersten ``top_n`` Plätzen von Ranking 1 oder 2 in mindestens einem Zeitraum.

    Reihenfolge: bester Platz zuerst (Sieger vor Platz 2 …), dann Instrumentindex. Gibt die auf
    ``max_instruments`` begrenzte Liste und die Gesamtzahl zurück.
    """
    best: dict[int, int] = {}
    for h in windows:
        window = rankings[h]
        for ranking in (window.native0, getattr(window, "native0_liquid", None)):
            if ranking is None or not ranking.size:
                continue
            for position, idx in enumerate(ranking.order[:top_n].tolist()):
                idx = int(idx)
                if position < best.get(idx, top_n):
                    best[idx] = position
    ordered = sorted(best, key=lambda i: (best[i], i))
    return ordered[:max_instruments], len(ordered)


def choose_venue(candidates, *, reference_symbol: str | None, reference_exchange: str | None, table, preferred) -> object | None:
    """Wählt den zweiten Börsenplatz aus den Notierungen der Identitätsquelle.

    Ausgeschlossen: die Referenzbörse selbst, Notierungen mit demselben Anbietersymbol (z. B. NYSE
    und Nasdaq liefern bei Yahoo dieselbe zusammengefasste US-Kursreihe), OTC-Märkte (oft ohne
    Handel) und unbekannte Börsen. Reihenfolge: ``preferred`` (Xetra, Frankfurt), dann die
    Standardreihenfolge der Börsentabelle.
    """
    order = {key: k for k, key in enumerate(list(preferred) + [k for k in table.default_preference if k not in preferred])}
    usable = []
    for candidate in candidates or []:
        key = candidate.exchange_key
        symbol = candidate.provider_symbol
        if not key or not symbol or key not in table.exchanges:
            continue
        if key == reference_exchange or symbol == reference_symbol:
            continue
        if table.exchanges[key].otc:
            continue
        usable.append(candidate)
    if not usable:
        return None
    usable.sort(key=lambda c: (order.get(c.exchange_key, len(order)), c.exchange_key, c.provider_symbol))
    return usable[0]


def compare_instrument(
    *,
    cols: list[int],
    start_days: np.ndarray,
    r_ref: np.ndarray,
    p1_ref: float,
    cutoff_day: int,
    ref_currency: str | None,
    ref_unit_factor: float,
    alt: AltSeries,
    fx: FxRates | None,
    settings: VenueSettings,
    alt_sessions: np.ndarray | None = None,
) -> InstrumentVenue:
    """Vergleicht alle Zeiträume ``cols`` einer Aktie mit dem zweiten Börsenplatz.

    ``start_days``/``r_ref`` sind je Spalte die Startsitzung und die ungerundete Kursrendite der
    Referenznotierung; ``p1_ref`` ist ihr Endkurs am Stichtag (gleich für alle Zeiträume).
    ``alt_sessions`` sind die Sitzungen des Vergleichsplatzes laut Börsenkalender (aufsteigend, bis
    zum Stichtag); ohne Kalender ``None``.
    """
    result = InstrumentVenue(
        status="geprueft",
        symbol=alt.symbol,
        exchange_key=alt.exchange_key,
        exchange_name=alt.exchange_name,
        currency=alt.currency,
        price_unit=alt.price_unit,
    )
    days = np.asarray(alt.days, dtype=np.int64)
    close = np.asarray(alt.close, dtype=np.float64)
    keep = (days <= cutoff_day) & np.isfinite(close) & (close > 0)
    days, close = days[keep], close[keep]
    sessions = None if alt_sessions is None else np.asarray(alt_sessions, dtype=np.int64)

    def asof(day: int) -> int | None:
        """Index des Vergleichskurses zum Referenztag ``day``; ``None``: Vergleichskurs fehlt."""
        if sessions is not None:
            # Maßgeblich ist die letzte Sitzung des Vergleichsplatzes am oder vor ``day`` – genau diese.
            p = int(np.searchsorted(sessions, day, side="right")) - 1
            if p < 0 or day - int(sessions[p]) > settings.max_gap_days:
                return None
            wanted = int(sessions[p])
            k = int(np.searchsorted(days, wanted))
            return k if k < len(days) and int(days[k]) == wanted else None
        k = int(np.searchsorted(days, day, side="right")) - 1
        if k < 0 or day - int(days[k]) > settings.max_gap_days:
            return None
        return k

    def factor(day: int) -> float | None:
        """Umrechnung einer Einheit Vergleichswährung in Referenzwährung am Kurstag ``day``."""
        if alt.currency is None or ref_currency is None:
            return None
        if alt.currency == ref_currency:
            return 1.0
        if fx is None:
            return None
        usd_alt = fx.usd_per_unit(alt.currency, day)
        usd_ref = fx.usd_per_unit(ref_currency, day)
        if usd_alt is None or usd_ref is None:
            return None
        return usd_alt[0] / usd_ref[0]

    end = asof(cutoff_day)
    if end is None:
        for col in cols:
            result.pairs[col] = PairResult("keine_kurse")
        return result
    d1 = int(days[end])
    p1_alt = float(close[end])
    result.end_day, result.end_price = d1, p1_alt
    f1 = factor(d1)
    if f1 is None:
        for col in cols:
            result.pairs[col] = PairResult("wechselkurs_fehlt", d1=d1, p1=p1_alt)
        return result
    v1 = p1_alt * alt.unit_factor * f1
    ref_end = p1_ref * ref_unit_factor
    if ref_end > 0 and math.isfinite(ref_end):
        result.level = v1 / ref_end - 1.0
        result.level_flagged = abs(math.log1p(result.level)) > math.log1p(settings.max_level_dev)

    for col in cols:
        start = int(start_days[col])
        r = float(r_ref[col])
        begin = asof(start) if start >= 0 else None
        if begin is None or begin >= end or not math.isfinite(r):
            result.pairs[col] = PairResult("keine_kurse", d1=d1, p1=p1_alt)
            continue
        d0 = int(days[begin])
        p0_alt = float(close[begin])
        f0 = factor(d0)
        if f0 is None:
            result.pairs[col] = PairResult("wechselkurs_fehlt", d0=d0, d1=d1, p0=p0_alt, p1=p1_alt)
            continue
        v0 = p0_alt * alt.unit_factor * f0
        growth_alt = v1 / v0
        growth_ref = 1.0 + r  # > 0, weil Start- und Endkurs der Referenz positiv sind
        ratio = growth_alt / growth_ref
        deviating = abs(math.log(ratio)) > math.log1p(settings.max_return_dev)
        status = "abweichung" if deviating or result.level_flagged else "ok"
        result.pairs[col] = PairResult(status, r_alt=growth_alt - 1.0, dev=ratio - 1.0, d0=d0, d1=d1, p0=p0_alt, p1=p1_alt)
    return result
