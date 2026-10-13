"""DEMO-Datenquelle: synthetische Testaktien mit gekennzeichneten Namen.

Alle Namen beginnen mit „DEMO“, alle ISINs mit dem nicht vergebenen Präfix „ZZ“.
Kurse sind deterministisch erzeugte Zufallsreihen – keine echten Kurse.
Die Demo deckt bewusst Sonderfälle ab: Feiertag am Stichtag, fehlender Stichtagskurs,
kurze Historie, Lücken, fehlendes/Null-Volumen, Splits (bereinigt und unbereinigt),
Einheitenfehler (Faktor 100), geprüfter Kurssprung, unklare Identität, Fonds,
ungültige ISIN, OTC-Notierung, konstante Reihe und exakte Gleichstände.
"""

from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass, field

import numpy as np

from ..analytics.quality import SplitEvent
from ..util.isin import make_isin
from ..util.timeutil import UTC, date_to_day
from .base import ListingCandidate, NoDataError, PriceHistory, SessionFinal
from .calendars import StaticCalendarProvider, weekday_holiday_sessions
from .tr_universe import UniverseEntry, UniverseParseResult

DEMO_NOW = dt.datetime(2026, 10, 13, 4, 5, tzinfo=UTC)  # 06:05 Uhr Berlin
DEMO_START = dt.date(2026, 3, 2)
DEMO_END = dt.date(2026, 10, 16)

_HOLIDAYS = {
    "XNYS": ["2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03", "2026-05-25", "2026-06-19", "2026-07-03", "2026-09-07", "2026-11-26", "2026-12-25"],
    "XETR": ["2026-01-01", "2026-04-03", "2026-04-06", "2026-05-01", "2026-12-24", "2026-12-25", "2026-12-31"],
    "XLON": ["2026-01-01", "2026-04-03", "2026-04-06", "2026-05-04", "2026-05-25", "2026-08-31", "2026-12-25", "2026-12-28"],
    "XTKS": ["2026-01-01", "2026-01-02", "2026-01-12", "2026-02-11", "2026-02-23", "2026-03-20", "2026-04-29", "2026-05-04", "2026-05-05", "2026-05-06", "2026-07-20", "2026-08-11", "2026-09-21", "2026-09-22", "2026-09-23", "2026-10-12", "2026-11-03", "2026-11-23", "2026-12-31"],
    "XHKG": ["2026-01-01", "2026-02-17", "2026-02-18", "2026-02-19", "2026-04-03", "2026-04-06", "2026-05-01", "2026-05-25", "2026-06-19", "2026-07-01", "2026-10-01", "2026-10-19", "2026-12-25"],
    "XASX": ["2026-01-01", "2026-01-26", "2026-04-03", "2026-04-06", "2026-06-08", "2026-12-25", "2026-12-28"],
}
_CLOSES = {
    "XNYS": ("America/New_York", dt.time(16, 0)),
    "XETR": ("Europe/Berlin", dt.time(17, 30)),
    "XLON": ("Europe/London", dt.time(16, 30)),
    "XTKS": ("Asia/Tokyo", dt.time(15, 30)),
    "XHKG": ("Asia/Hong_Kong", dt.time(16, 0)),
    "XASX": ("Australia/Sydney", dt.time(16, 0)),
}
_MARKETS = [
    ("XNYS", "US", "USD", ""),
    ("XETR", "XETR", "EUR", ".DE"),
    ("XLON", "XLON", "GBp", ".L"),
    ("XTKS", "XTKS", "JPY", ".T"),
    ("XHKG", "XHKG", "HKD", ".HK"),
    ("XASX", "XASX", "AUD", ".AX"),
]
_WORDS = [
    "Alpha", "Boreal", "Cobalt", "Delta", "Eisen", "Fjord", "Granit", "Helios", "Iris", "Jade", "Kobold", "Lumen",
    "Meridian", "Nordlicht", "Onyx", "Polaris", "Quarz", "Rubin", "Saphir", "Tundra", "Umbra", "Vektor", "Wolfram",
    "Xenon", "Yukon", "Zirkon", "Aurora", "Basalt", "Cirrus", "Dynamo",
]
_SUFFIX = {"US": "Inc.", "XETR": "AG", "XLON": "plc", "XTKS": "K.K.", "XHKG": "Holdings Ltd.", "XASX": "Ltd."}


def demo_calendars() -> StaticCalendarProvider:
    sessions = {}
    for code, days in _HOLIDAYS.items():
        holidays = {dt.date.fromisoformat(d) for d in days}
        sessions[code] = weekday_holiday_sessions(DEMO_START - dt.timedelta(days=60), DEMO_END, holidays)
    return StaticCalendarProvider(sessions, _CLOSES, label="DEMO, synthetisch")


@dataclass
class DemoInstrument:
    isin: str
    name: str
    exchange_key: str
    calendar: str
    currency: str
    symbol: str
    pattern: str
    seed: int
    candidates: list[ListingCandidate] = field(default_factory=list)


def _patterns() -> list[str]:
    base = ["steady_strong", "steady_mild", "volatile_up", "noisy_flat", "falling", "steady_down", "curved_up", "late_rally"]
    return base


def build_demo_universe() -> list[DemoInstrument]:
    instruments: list[DemoInstrument] = []
    number = 1
    patterns = _patterns()
    for market_index, (calendar, key, currency, suffix) in enumerate(_MARKETS):
        for j in range(30):
            word = _WORDS[(j + market_index * 7) % len(_WORDS)]
            word2 = _WORDS[(j * 3 + market_index) % len(_WORDS)]
            pattern = patterns[j % len(patterns)]
            name = f"DEMO {word} {word2} {_SUFFIX[key]}"
            isin = make_isin(f"ZZ{number:09d}")
            ticker = f"D{number:03d}" if key not in ("XTKS", "XHKG") else f"{9000 + number}"
            symbol = f"{ticker}{suffix}"
            instruments.append(DemoInstrument(isin, name, key, calendar, currency, symbol, pattern, seed=number))
            number += 1
    specials = [
        ("XNYS", "US", "USD", "", "recent_ipo", "DEMO Neuling Börsengang Inc."),
        ("XETR", "XETR", "EUR", ".DE", "gappy", "DEMO Lückenhaft Daten AG"),
        ("XETR", "XETR", "EUR", ".DE", "zero_volume", "DEMO Selten Gehandelt AG"),
        ("XNYS", "US", "USD", "", "unknown_volume", "DEMO Ohne Umsatzangabe Inc."),
        ("XNYS", "US", "USD", "", "split_adjusted", "DEMO Geteilt Bereinigt Inc."),
        ("XNYS", "US", "USD", "", "split_unadjusted", "DEMO Geteilt Unbereinigt Inc."),
        ("XLON", "XLON", "GBp", ".L", "unit_error", "DEMO Pence Pfund Fehler plc"),
        ("XASX", "XASX", "AUD", ".AX", "reviewed_jump", "DEMO Übernahmeangebot Ltd."),
        ("XNYS", "US", "USD", "", "missing_cutoff", "DEMO Stichtag Fehlt Inc."),
        ("XNYS", "OTC", "USD", "", "otc_up", "DEMO Freiverkehr ADR"),
        ("XETR", "XETR", "EUR", ".DE", "constant", "DEMO Konstant Kurs AG"),
        ("XETR", "XETR", "EUR", ".DE", "twin_a", "DEMO Zwilling A AG"),
        ("XETR", "XETR", "EUR", ".DE", "twin_b", "DEMO Zwilling B AG"),
        ("XHKG", "XHKG", "HKD", ".HK", "impulse", "DEMO Impulstag Holdings Ltd."),
        ("XNYS", "US", "USD", "", "identity_unclear", "DEMO Unbekannte Identität Corp."),
        ("XNYS", "US", "USD", "", "fund", "DEMO Indexfonds Trust"),
        ("XNYS", "US", "USD", "", "no_data", "DEMO Keine Kursdaten Corp."),
    ]
    for calendar, key, currency, suffix, pattern, name in specials:
        isin = make_isin(f"ZZ{number:09d}")
        instruments.append(DemoInstrument(isin, name, key, calendar, currency, f"S{number:03d}{suffix}", pattern, seed=number))
        number += 1
    # Formal ungültige ISIN (Prüfziffer absichtlich falsch).
    bad = make_isin(f"ZZ{number:09d}")
    bad = bad[:-1] + str((int(bad[-1]) + 1) % 10)
    instruments.append(DemoInstrument(bad, "DEMO Falsche Prüfziffer AG", "XETR", "XETR", "EUR", "BAD.DE", "invalid_isin", seed=number))

    for inst in instruments:
        if inst.pattern in ("identity_unclear", "invalid_isin"):
            continue
        security_type = "Mutual Fund" if inst.pattern == "fund" else ("ADR" if inst.pattern == "otc_up" else "Common Stock")
        inst.candidates = [
            ListingCandidate(
                source="demo",
                exchange_key=inst.exchange_key,
                provider_symbol=inst.symbol,
                ticker=inst.symbol.split(".")[0],
                exch_code=inst.exchange_key,
                name=inst.name,
                security_type=security_type,
            )
        ]
    instruments.sort(key=lambda x: x.isin)
    return instruments


def demo_universe_parse() -> UniverseParseResult:
    entries = [UniverseEntry(i.isin, i.name, i.pattern != "invalid_isin", page=1) for i in build_demo_universe()]
    return UniverseParseResult(entries, ["Stocks (DEMO)"], True, 0, 1, 0, [], parser_version="demo-generator-1")


def _series(pattern: str, n: int, rng: np.random.Generator) -> np.ndarray:
    t = np.arange(n, dtype=float)
    if pattern == "steady_strong":
        drift, vol = rng.uniform(0.002, 0.004), rng.uniform(0.002, 0.006)
    elif pattern == "steady_mild":
        drift, vol = rng.uniform(0.0006, 0.0015), rng.uniform(0.002, 0.005)
    elif pattern == "volatile_up":
        drift, vol = rng.uniform(0.003, 0.006), rng.uniform(0.03, 0.05)
    elif pattern == "noisy_flat":
        drift, vol = 0.0, rng.uniform(0.01, 0.025)
    elif pattern == "falling":
        drift, vol = -rng.uniform(0.001, 0.004), rng.uniform(0.01, 0.02)
    elif pattern == "steady_down":
        drift, vol = -rng.uniform(0.001, 0.002), 0.003
    elif pattern == "curved_up":
        base = 20 * np.exp(0.00004 * t ** 2)
        return base * np.exp(rng.normal(0, 0.004, n))
    elif pattern == "late_rally":
        steps = np.where(t > n - 25, 0.012, -0.0005) + rng.normal(0, 0.008, n)
        return 15 * np.exp(np.cumsum(steps))
    else:
        drift, vol = 0.001, 0.01
    level = float(10 ** rng.uniform(0.3, 2.7))
    return level * np.exp(np.cumsum(rng.normal(drift, vol, n)))


class DemoProvider:
    """Liefert synthetische Kurse im selben Format wie echte Adapter (Kennzeichnung DEMO)."""

    name = "demo"

    def __init__(self) -> None:
        self.calendars = demo_calendars()
        self.instruments = {i.symbol: i for i in build_demo_universe()}
        self._cache: dict[str, PriceHistory] = {}

    def fetch_history(self, symbol: str, start_day: int, end_day: int, *, session_final: SessionFinal | None = None) -> PriceHistory:
        inst = self.instruments.get(symbol)
        if inst is None or inst.pattern == "no_data":
            raise NoDataError(f"{symbol}: DEMO ohne Daten")
        history = self._build(inst)
        mask = (history.days >= start_day) & (history.days <= end_day)
        if session_final is not None:
            mask &= np.array([session_final(int(d)) for d in history.days], dtype=bool)
        if not mask.any():
            raise NoDataError(f"{symbol}: keine Daten im Zeitraum")
        return PriceHistory(
            provider=self.name,
            symbol=symbol,
            days=history.days[mask],
            open=history.open[mask],
            high=history.high[mask],
            low=history.low[mask],
            close=history.close[mask],
            volume=history.volume[mask],
            close_raw=history.close_raw[mask] if history.close_raw is not None else None,
            close_total=None,
            currency=history.currency,
            price_unit=history.price_unit,
            unit_factor=history.unit_factor,
            exchange_name=inst.exchange_key,
            exchange_tz=_CLOSES[inst.calendar][0],
            instrument_type="EQUITY",
            long_name=inst.name,
            splits=history.splits,
            fetched_at=DEMO_NOW,
            raw_close_reconstructed=bool(history.splits),
            notes=["DEMO – synthetische Testdaten"],
        )

    def _build(self, inst: DemoInstrument) -> PriceHistory:
        if inst.symbol in self._cache:
            return self._cache[inst.symbol]
        rng = np.random.default_rng(1000 + inst.seed)
        sessions = self.calendars.sessions(inst.calendar, date_to_day(DEMO_START), date_to_day(dt.date(2026, 10, 12)))
        n = len(sessions)
        close = _series(inst.pattern, n, rng)
        volume = rng.integers(2_000, 900_000, n).astype(float)
        days = sessions.copy()
        splits: list[SplitEvent] = []
        p = inst.pattern
        if p == "recent_ipo":
            keep = days >= days[-1] - 40
            days, close, volume = days[keep], close[keep], volume[keep]
        elif p == "gappy":
            drop = rng.choice(np.arange(5, n - 5), size=8, replace=False)
            keep = np.ones(n, dtype=bool)
            keep[drop] = False
            days, close, volume = days[keep], close[keep], volume[keep]
        elif p == "zero_volume":
            volume[rng.random(n) < 0.45] = 0.0
        elif p == "unknown_volume":
            volume[:] = math.nan
        elif p == "split_adjusted":
            close = 40 * np.exp(np.cumsum(rng.normal(0.002, 0.004, n)))
            splits = [SplitEvent(int(days[n - 30]), 2.0)]
        elif p == "split_unadjusted":
            close = 40 * np.exp(np.cumsum(rng.normal(0.002, 0.004, n)))
            split_day = int(days[n - 30])
            close = np.where(days >= split_day, close / 2.0, close)
            splits = [SplitEvent(split_day, 2.0)]
        elif p == "unit_error":
            close = 500 * np.exp(np.cumsum(rng.normal(0.001, 0.004, n)))
            close[n - 12] = close[n - 12] / 100.0
        elif p == "reviewed_jump":
            close = 2 * np.exp(np.cumsum(rng.normal(0.0005, 0.004, n)))
            close[n - 20 :] *= 3.5
        elif p == "missing_cutoff":
            close = 25 * np.exp(np.cumsum(rng.normal(0.003, 0.004, n)))
            days, close, volume = days[:-1], close[:-1], volume[:-1]
        elif p == "otc_up":
            close = 3 * np.exp(np.cumsum(rng.normal(0.002, 0.006, n)))
        elif p == "constant":
            close = np.full(n, 12.5)
        elif p in ("twin_a", "twin_b"):
            close = 10 * np.exp(np.cumsum(np.full(n, 0.0015)))
            close = np.round(close, 6)
        elif p == "impulse":
            close = 8 * np.exp(np.cumsum(rng.normal(0.0, 0.003, n)))
            close[n - 6 :] *= 1.6
        elif p in ("identity_unclear", "fund", "invalid_isin"):
            close = 20 * np.exp(np.cumsum(rng.normal(0.001, 0.01, n)))
        close_raw = close.copy()
        for event in splits:
            close_raw[days < event.day] *= event.factor
        spread = np.abs(rng.normal(0, 0.006, len(close)))
        history = PriceHistory(
            provider=self.name,
            symbol=inst.symbol,
            days=days.astype(np.int64),
            open=close * (1 - spread / 2),
            high=close * (1 + spread),
            low=close * (1 - spread),
            close=close,
            volume=volume,
            close_raw=close_raw,
            currency=inst.currency,
            price_unit=inst.currency,
            unit_factor=0.01 if inst.currency == "GBp" else 1.0,
            splits=splits,
        )
        self._cache[inst.symbol] = history
        return history


def demo_review_decisions() -> dict[str, dict[int, str]]:
    """Dokumentierte DEMO-Prüfentscheidung: Kurssprung der Übernahme-Testaktie freigegeben."""
    provider = DemoProvider()
    decisions: dict[str, dict[int, str]] = {}
    for inst in provider.instruments.values():
        if inst.pattern == "reviewed_jump":
            history = provider._build(inst)
            n = len(history.days)
            decisions[inst.isin] = {int(history.days[n - 20]): "freigegeben"}
    return decisions


# Synthetische Referenzkurse je EUR für den DEMO-Modus (keine echten Kurse, kein Abruf).
_DEMO_FX_PER_EUR = {"USD": 1.10, "GBP": 0.85, "JPY": 160.0, "HKD": 8.6, "AUD": 1.65}


class DemoFxSource:
    name = "DEMO – synthetische Wechselkurse (keine echten Kurse)"

    def fetch(self):
        from .ecb import FxFetch

        rows: list[tuple[int, str, float]] = []
        current = DEMO_START - dt.timedelta(days=60)
        k = 0
        while current <= dt.date(2026, 10, 12):
            if current.weekday() < 5:
                day = date_to_day(current)
                wiggle = 1.0 + 0.002 * math.sin(k / 7.0)
                rows += [(day, currency, round(rate * wiggle, 6)) for currency, rate in _DEMO_FX_PER_EUR.items()]
                k += 1
            current += dt.timedelta(days=1)
        return FxFetch(rows=rows, source=self.name, url=None, fetched_at=DEMO_NOW.strftime("%Y-%m-%dT%H:%M:%SZ"))
