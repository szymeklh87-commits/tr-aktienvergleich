"""Daytrading vorbereiten (ab 1.22, Auftrag vom 07.11.2026, Priorität 4; Befund F22) – reiner Rechenkern ohne Ein-/Ausgabe.

Aus Minutenkerzen eines Handelstags (Zeit, Eröffnung, Hoch, Tief, Schluss, Umsatz) rechnet dieses Modul die üblichen
Tageswerte und prüft vorher festgelegte Kriterien (``config/daytrading.yaml``). **Es erscheint keine Kandidatenliste**, solange
die Kriterien nicht rückwirkend mit Kosten geprüft und freigegeben sind (Maßnahme zu F22: „Kriterien vorher festlegen und im
Strategielabor rückwirkend mit Kosten prüfen, bevor eine Liste erscheint“). Keine Orders, kein Echtgeld.

Werte je Tag und Aktie:

* **VWAP** – umsatzgewichteter Durchschnittskurs seit Handelsbeginn (typischer Kurs = (Hoch + Tief + Schluss) / 3).
* **Eröffnungsspanne** – Hoch und Tief der ersten ``spanne_minuten`` Minuten.
* **Relativer Umsatz** – Umsatz seit Handelsbeginn geteilt durch den Durchschnitt derselben Tageszeit an früheren Tagen.
* **Bewegung seit Eröffnung** in Prozent.

Kriterium „Ausbruch aus der Eröffnungsspanne“ (Version ``orb-1``, Vorschlag, nicht freigegeben): Schluss einer Kerze nach der
Spanne über dem Spannenhoch, Kurs über dem VWAP, relativer Umsatz mindestens ``min_relativer_umsatz``, Spanne höchstens
``max_spanne_prozent`` breit. Einstieg = Schluss dieser Kerze, Stop = Spannentief (höchstens ``max_stop_prozent`` entfernt),
Ziel = Einstieg + ``chance_risiko`` × Risiko, Ausstieg spätestens ``ausstieg_minuten_vor_schluss`` vor Handelsende.

:func:`backtest` prüft das Kriterium rückwirkend Tag für Tag mit Kosten (Gebühr je Order und halbe Geld-Brief-Spanne je Seite)
und ohne Blick in die Zukunft: Entscheidungen nur mit Kerzen bis zum jeweiligen Zeitpunkt.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

VERSION = "orb-1"


@dataclass(frozen=True)
class Bar:
    """Eine Minutenkerze; ``t`` in Sekunden seit 1970 (UTC)."""

    t: int
    o: float
    h: float
    l: float  # noqa: E741 - üblicher Name für das Tief
    c: float
    v: float


@dataclass(frozen=True)
class Criteria:
    spanne_minuten: int = 15
    min_relativer_umsatz: float = 2.0
    max_spanne_prozent: float = 6.0
    max_stop_prozent: float = 4.0
    chance_risiko: float = 2.0
    ausstieg_minuten_vor_schluss: int = 15
    gebuehr_eur: float = 1.0
    spanne_halb_prozent: float = 0.10  # halbe Geld-Brief-Spanne je Seite in Prozent des Kurses
    einsatz_eur: float = 1000.0

    @classmethod
    def from_mapping(cls, raw: dict | None) -> "Criteria":
        raw = raw or {}
        values = {}
        for name, default in cls().__dict__.items():
            value = raw.get(name, default)
            try:
                value = type(default)(value)
            except (TypeError, ValueError):
                value = default
            values[name] = value
        criteria = cls(**values)
        problems = criteria.problems()
        if problems:
            raise ValueError("; ".join(problems))
        return criteria

    def problems(self) -> list[str]:
        out = []
        if not 1 <= self.spanne_minuten <= 120:
            out.append("spanne_minuten: 1 bis 120")
        if self.min_relativer_umsatz < 0:
            out.append("min_relativer_umsatz: nicht negativ")
        if not 0 < self.max_spanne_prozent <= 50 or not 0 < self.max_stop_prozent <= 50:
            out.append("Spanne und Stop: über 0 bis 50 %")
        if not 0.5 <= self.chance_risiko <= 10:
            out.append("chance_risiko: 0,5 bis 10")
        if self.gebuehr_eur < 0 or self.spanne_halb_prozent < 0 or self.einsatz_eur <= 0:
            out.append("Kosten und Einsatz: Gebühr und Spanne nicht negativ, Einsatz größer 0")
        return out


@dataclass
class DayValues:
    vwap: list[float]
    range_high: float | None
    range_low: float | None
    cum_volume: list[float]
    move_pct: list[float]


def day_values(bars: list[Bar], criteria: Criteria) -> DayValues:
    """VWAP, Eröffnungsspanne, kumulierter Umsatz und Bewegung seit Eröffnung je Kerze – nur aus Kerzen bis dahin."""
    vwap: list[float] = []
    cum: list[float] = []
    move: list[float] = []
    pv = vol = 0.0
    if not bars:
        return DayValues([], None, None, [], [])
    start = bars[0].t
    open_price = bars[0].o
    range_bars = [b for b in bars if b.t < start + criteria.spanne_minuten * 60]
    for bar in bars:
        typical = (bar.h + bar.l + bar.c) / 3
        pv += typical * max(bar.v, 0.0)
        vol += max(bar.v, 0.0)
        vwap.append(pv / vol if vol > 0 else typical)
        cum.append(vol)
        move.append((bar.c / open_price - 1) * 100 if open_price > 0 else 0.0)
    return DayValues(vwap, max(b.h for b in range_bars), min(b.l for b in range_bars), cum, move)


def relative_volume(cum_volume_now: float, minute: int, history: list[list[float]]) -> float | None:
    """Umsatz bis Minute ``minute`` geteilt durch den Durchschnitt derselben Minute an früheren Tagen (None ohne Vergleich)."""
    same_time = [day[min(minute, len(day) - 1)] for day in history if day]
    same_time = [v for v in same_time if v > 0]
    if not same_time:
        return None
    return cum_volume_now / (sum(same_time) / len(same_time))


@dataclass
class Signal:
    minute: int
    entry: float
    stop: float
    target: float
    relative_volume: float
    reasons: list[str] = field(default_factory=list)


def first_signal(bars: list[Bar], criteria: Criteria, history: list[list[float]]) -> Signal | None:
    """Erstes Signal des Tages nach Kriterium ``orb-1`` – geprüft Kerze für Kerze ohne Blick in die Zukunft."""
    values = day_values(bars, criteria)
    if values.range_high is None or values.range_low is None or values.range_low <= 0:
        return None
    width = (values.range_high / values.range_low - 1) * 100
    if width > criteria.max_spanne_prozent:
        return None
    start = bars[0].t
    for i, bar in enumerate(bars):
        minute = (bar.t - start) // 60
        if minute < criteria.spanne_minuten:
            continue
        if bar.c <= values.range_high or bar.c <= values.vwap[i]:
            continue
        rv = relative_volume(values.cum_volume[i], i, history)
        if rv is None or rv < criteria.min_relativer_umsatz:
            continue
        stop = max(values.range_low, bar.c * (1 - criteria.max_stop_prozent / 100))
        if stop >= bar.c:
            continue
        risk = bar.c - stop
        return Signal(
            minute=int(minute),
            entry=bar.c,
            stop=stop,
            target=bar.c + criteria.chance_risiko * risk,
            relative_volume=rv,
            reasons=[f"Ausbruch über die Spanne der ersten {criteria.spanne_minuten} Minuten", "Kurs über VWAP", f"relativer Umsatz {rv:.1f}"],
        )
    return None


@dataclass
class Trade:
    day: int
    minute_in: int
    minute_out: int
    entry: float
    exit: float
    outcome: str  # ziel | stop | schluss
    net_eur: float


def simulate(bars: list[Bar], signal: Signal, criteria: Criteria, day_index: int = 0) -> Trade:
    """Ein Trade ab dem Signal: Stop vor Ziel in derselben Kerze (vorsichtig), sonst Ausstieg vor Handelsende. Kosten: Gebühr je
    Order und halbe Spanne je Seite."""
    start = bars[0].t
    end_minute = (bars[-1].t - start) // 60 - criteria.ausstieg_minuten_vor_schluss
    exit_price, outcome, minute_out = bars[-1].c, "schluss", (bars[-1].t - start) // 60
    for bar in bars:
        minute = (bar.t - start) // 60
        if minute <= signal.minute:
            continue
        if bar.l <= signal.stop:
            exit_price, outcome, minute_out = signal.stop, "stop", minute
            break
        if bar.h >= signal.target:
            exit_price, outcome, minute_out = signal.target, "ziel", minute
            break
        if minute >= end_minute:
            exit_price, outcome, minute_out = bar.c, "schluss", minute
            break
    shares = math.floor(criteria.einsatz_eur / signal.entry) if signal.entry > 0 else 0
    spread = criteria.spanne_halb_prozent / 100
    buy = signal.entry * (1 + spread)
    sell = exit_price * (1 - spread)
    net = shares * (sell - buy) - 2 * criteria.gebuehr_eur
    return Trade(day_index, signal.minute, int(minute_out), signal.entry, exit_price, outcome, round(net, 2))


@dataclass
class BacktestResult:
    days: int
    signals: int
    trades: list[Trade]

    @property
    def net_eur(self) -> float:
        return round(sum(t.net_eur for t in self.trades), 2)

    @property
    def hit_rate(self) -> float | None:
        return sum(1 for t in self.trades if t.net_eur > 0) / len(self.trades) if self.trades else None

    def summary(self) -> dict:
        return {
            "version": VERSION,
            "tage": self.days,
            "signale": self.signals,
            "trades": len(self.trades),
            "ergebnis_eur_nach_kosten": self.net_eur,
            "trefferquote": None if self.hit_rate is None else round(self.hit_rate, 3),
            "ausgaenge": {k: sum(1 for t in self.trades if t.outcome == k) for k in ("ziel", "stop", "schluss")},
            "freigegeben": False,
        }


def backtest(days: list[list[Bar]], criteria: Criteria, history_days: int = 10) -> BacktestResult:
    """Rückwirkende Prüfung Tag für Tag: Der relative Umsatz eines Tages nutzt nur die ``history_days`` Tage davor."""
    trades: list[Trade] = []
    signals = 0
    curves: list[list[float]] = []
    for index, bars in enumerate(days):
        if bars:
            history = curves[-history_days:]
            signal = first_signal(bars, criteria, history)
            if signal is not None:
                signals += 1
                trades.append(simulate(bars, signal, criteria, index))
            curves.append(day_values(bars, criteria).cum_volume)
    return BacktestResult(len(days), signals, trades)
