"""Synthetisches Testszenario für AktienPilot (SYNTHETISCH – keine echten Kurse).

Ein Börsenkalender (Montag–Freitag, Xetra-Schlusszeit), Aktien mit festen Kursverläufen (gleichmäßig steigend, stark
steigend, fallend, seitwärts, mit Kurslücke, in USD) und Füllaktien mit Zufallspfad (fester Startwert). Daraus entstehen
dieselben Eingaben wie im täglichen Lauf: ``InstrumentData`` für den Rechenkern (Ranglisten) und ``Series`` mit OHLCV für
Indikatoren und Simulator.
"""

from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass, field

import numpy as np

from traktien.aktienpilot import katalog as kat
from traktien.aktienpilot.config import load_aktienpilot_config as load_config
from traktien.aktienpilot.markt import Market, Series
from traktien.analytics.engine import InstrumentData, compute_snapshot
from traktien.analytics.fx import FxRates
from traktien.config import MethodConfig
from traktien.providers.calendars import StaticCalendarProvider
from traktien.util.isin import make_isin
from traktien.util.timeutil import date_to_day

from tests.helpers import weekday_sessions

START = dt.date(2025, 6, 2)
END = dt.date(2026, 10, 30)


def isin(n: int) -> str:
    return make_isin(f"ZZ{n:09d}")


@dataclass
class Aktie:
    isin: str
    name: str
    preis: callable
    waehrung: str = "EUR"
    volumen: float = 200_000.0
    branche: str = "Technologie"
    luecke_tag: int | None = None  # Index der Sitzung mit Eröffnungslücke
    luecke: float = 0.0


@dataclass
class Szenario:
    sessions: np.ndarray
    aktien: list[Aktie]
    cfg: object
    method: MethodConfig
    markt: Market
    calendars: StaticCalendarProvider
    stamm: dict[str, dict] = field(default_factory=dict)
    _comp: dict = field(default_factory=dict)

    @property
    def isins(self) -> list[str]:
        return sorted(a.isin for a in self.aktien)

    def instruments(self, day: int) -> list[InstrumentData]:
        out = []
        for a in sorted(self.aktien, key=lambda a: a.isin):
            s = self.markt.series[a.isin]  # nur Aktien des Universums – Kern-ETFs und Indizes rechnet der Rechenkern nicht
            mask = s.days <= day
            out.append(InstrumentData(isin=a.isin, sessions=self.sessions, days=s.days[mask], close=s.close[mask], volume=s.volume[mask],
                                      currency=a.waehrung))
        return out

    def comp(self, day: int):
        if day not in self._comp:
            self._comp[day] = compute_snapshot(self.instruments(day), day, self.method, self.markt.fx, workers=1)
        return self._comp[day]

    def kontext(self, day: int) -> kat.Kontext:
        comp = self.comp(day)
        return kat.Kontext(tag=day, isins=list(comp.isins), method=self.method, comp=comp, markt=self.markt, cfg=self.cfg, stamm=self.stamm)


def _ohlc(close: np.ndarray, rng: np.random.Generator, luecke_idx: int | None, luecke: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    prev = np.concatenate([[close[0]], close[:-1]])
    opn = prev * (1.0 + rng.normal(0, 0.002, len(close)))
    if luecke_idx is not None:
        opn[luecke_idx] = prev[luecke_idx] * (1.0 + luecke)
    high = np.maximum(opn, close) * (1.0 + np.abs(rng.normal(0, 0.004, len(close))))
    low = np.minimum(opn, close) * (1.0 - np.abs(rng.normal(0, 0.004, len(close))))
    return opn, high, low


def bauen(*, fuell: int = 24, seed: int = 7) -> Szenario:
    sessions = weekday_sessions(START, END)
    n = len(sessions)
    rng = np.random.default_rng(seed)
    aktien = [
        Aktie(isin(1), "Gleichmäßig AG", lambda k: 50.0 * math.exp(0.002 * k)),
        Aktie(isin(2), "Stark AG", lambda k: 20.0 * math.exp(0.004 * k) * (1.0 + 0.01 * math.sin(k / 3.0)), branche="Industrie"),
        Aktie(isin(3), "Fallend AG", lambda k: 80.0 * math.exp(-0.002 * k), branche="Energie"),
        Aktie(isin(4), "Seitwärts AG", lambda k: 30.0 * (1.0 + 0.02 * math.sin(k / 5.0)), branche="Handel"),
        Aktie(isin(5), "Lücke AG", lambda k: 40.0 * math.exp(0.003 * k) * (0.7 if k >= n - 30 else 1.0), branche="Industrie", luecke_tag=n - 30, luecke=-0.3),
        Aktie(isin(6), "Dollar Inc", lambda k: 100.0 * math.exp(0.0025 * k), waehrung="USD", branche="Technologie"),
    ]
    for j in range(fuell):
        steps = rng.normal(0.0003, 0.015, n)
        path = 25.0 * np.exp(np.cumsum(steps))
        aktien.append(Aktie(isin(100 + j), f"Füll {j:02d} AG", (lambda p: (lambda k: float(p[k])))(path), branche=["Technologie", "Industrie", "Handel", "Energie"][j % 4]))
    series = {}
    for a in aktien:
        close = np.array([a.preis(k) for k in range(n)], dtype=np.float64)
        opn, high, low = _ohlc(close, rng, a.luecke_tag, a.luecke)
        vol = np.full(n, a.volumen) * (1.0 + 0.2 * np.sin(np.arange(n) / 7.0))
        series[a.isin] = Series(a.isin, sessions.copy(), opn, high, low, close, vol, currency=a.waehrung, exchange="XETR", calendar="XETR",
                                name=a.name, sector=a.branche, synthetic=True)
    # Kern-ETFs (Welt, Geldmarkt) und Leitindex des Marktfilters – synthetisch, nur für Tests
    welt = 100.0 * np.exp(0.0004 * np.arange(n)) * (1.0 + 0.03 * np.sin(np.arange(n) / 20.0))
    geld = 140.0 * np.exp(0.0001 * np.arange(n))
    index = 15000.0 * np.exp(0.0005 * np.arange(n)) * (1.0 + 0.04 * np.sin(np.arange(n) / 25.0))
    for code, close in (("IE00B4L5Y983", welt), ("LU0290358497", geld)):
        opn, high, low = _ohlc(close, rng, None, 0.0)
        series[code] = Series(code, sessions.copy(), opn, high, low, close, np.full(n, 1e6), currency="EUR", exchange="XETR", calendar="XETR",
                              name="Welt-ETF (synthetisch)" if code.startswith("IE") else "Geldmarkt-ETF (synthetisch)", synthetic=True)
    opn, high, low = _ohlc(index, rng, None, 0.0)
    indices = {"^GDAXI": Series("^GDAXI", sessions.copy(), opn, high, low, index, np.full(n, np.nan), currency="EUR", exchange="XETR", calendar="XETR", synthetic=True)}
    rows = [(int(d), "USD", 1.10) for d in sessions]
    fx = FxRates.from_rows(rows, source="TEST – synthetische Wechselkurse", url=None, fetched_at=None, max_age_days=5)
    markt = Market(series=series, fx=fx, indices=indices, synthetic=True, data_stand="test", source="synthetisch")
    calendars = StaticCalendarProvider({"XETR": sessions}, {"XETR": ("Europe/Berlin", dt.time(17, 30))}, label="test", opens={"XETR": dt.time(9, 0)})
    cfg = load_config()
    method = MethodConfig()
    stamm = {a.isin: {"name": a.name, "branche": a.branche, "mic": "XETR", "boerse": "XETR", "waehrung": a.waehrung, "typ": "aktie"} for a in aktien}
    stamm["IE00B4L5Y983"] = {"name": "Welt-ETF (synthetisch)", "branche": "Fonds", "mic": "XETR", "waehrung": "EUR", "typ": "etf"}
    stamm["LU0290358497"] = {"name": "Geldmarkt-ETF (synthetisch)", "branche": "Fonds", "mic": "XETR", "waehrung": "EUR", "typ": "etf"}
    return Szenario(sessions, aktien, cfg, method, markt, calendars, stamm)


def tag(d: dt.date) -> int:
    return date_to_day(d)
