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
from .base import ListingCandidate, LiveQuote, NoDataError, PriceHistory, QuoteBatchResult, SessionFinal
from .calendars import StaticCalendarProvider, weekday_holiday_sessions
from .tr_universe import UniverseEntry, UniverseParseResult

DEMO_NOW = dt.datetime(2026, 10, 13, 4, 5, tzinfo=UTC)  # 06:05 Uhr Berlin
# Zwischenstand im DEMO (ab 1.8): 12:30 Uhr Berlin – Tokio, Hongkong und Sydney haben den 13.10. beendet,
# Xetra und London handeln, New York öffnet erst um 15:30 Uhr
DEMO_INTRADAY_NOW = dt.datetime(2026, 10, 13, 10, 30, tzinfo=UTC)
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
_HOLIDAYS["XFRA"] = list(_HOLIDAYS["XETR"])  # zweiter Börsenplatz im DEMO-Abgleich (gleiche Feiertage wie Xetra)
_CLOSES = {
    "XNYS": ("America/New_York", dt.time(16, 0)),
    "XETR": ("Europe/Berlin", dt.time(17, 30)),
    "XLON": ("Europe/London", dt.time(16, 30)),
    "XTKS": ("Asia/Tokyo", dt.time(15, 30)),
    "XHKG": ("Asia/Hong_Kong", dt.time(16, 0)),
    "XASX": ("Australia/Sydney", dt.time(16, 0)),
    "XFRA": ("Europe/Berlin", dt.time(20, 0)),
}
_OPENS = {
    "XNYS": dt.time(9, 30),
    "XETR": dt.time(9, 0),
    "XLON": dt.time(8, 0),
    "XTKS": dt.time(9, 0),
    "XHKG": dt.time(9, 30),
    "XASX": dt.time(10, 0),
    "XFRA": dt.time(8, 0),
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
    return StaticCalendarProvider(sessions, _CLOSES, label="DEMO, synthetisch", opens=_OPENS)


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


# Zweiter Börsenplatz im DEMO-Modus: jede Aktie (außer den Sonderfällen unten) hat eine
# synthetische Frankfurter Notierung „<Ticker>.F“ in EUR, die der Referenz folgt. Bewusste
# Abweichungen für die Tests: Die Impulstag-Aktie hat dort keinen Kurssprung (Endkurs und
# Wertentwicklung weichen ab); bei der ersten US-Aktie mit Muster „curved_up“ lagen die Kurse
# dort bis 25 Tage vor dem Stichtag 15 % tiefer (nur längere Zeiträume weichen ab); der Börsengang
# hat dort keine Kurse; die OTC-Aktie hat keinen zweiten Börsenplatz.
_NO_VENUE = ("otc_up", "no_data", "identity_unclear", "fund", "invalid_isin")


def demo_venue_symbol(inst: DemoInstrument) -> str | None:
    if inst.pattern in _NO_VENUE:
        return None
    return inst.symbol.split(".")[0] + ".F"


DEMO_VENUE_OFFSET_DAYS = 25  # bis zu diesem Abstand vor dem DEMO-Stichtag liegen die Vergleichskurse 15 % tiefer


def demo_venue_offset_isin() -> str | None:
    for inst in sorted(build_demo_universe(), key=lambda i: i.seed):
        if inst.pattern == "curved_up" and inst.exchange_key == "US":
            return inst.isin
    return None


class DemoVenueSource:
    """Notierungen je ISIN wie bei der Identitätsquelle, ergänzt um den DEMO-Börsenplatz Frankfurt."""

    def __init__(self) -> None:
        self._by_isin: dict[str, list[ListingCandidate]] = {}
        for inst in build_demo_universe():
            candidates = list(inst.candidates)
            symbol = demo_venue_symbol(inst)
            if symbol is not None and candidates:
                candidates.append(
                    ListingCandidate(
                        source="demo",
                        exchange_key="XFRA",
                        provider_symbol=symbol,
                        ticker=symbol.split(".")[0],
                        exch_code="XFRA",
                        name=inst.name,
                        security_type=candidates[0].security_type,
                    )
                )
            self._by_isin[inst.isin] = candidates

    def lookup(self, isins: list[str], budget_s: float) -> dict[str, list[ListingCandidate]]:
        return {isin: list(self._by_isin.get(isin, [])) for isin in isins}


class DemoProvider:
    """Liefert synthetische Kurse im selben Format wie echte Adapter (Kennzeichnung DEMO)."""

    name = "demo"

    def __init__(self) -> None:
        self.calendars = demo_calendars()
        universe = build_demo_universe()
        self.instruments = {i.symbol: i for i in universe}
        self.venue_instruments = {demo_venue_symbol(i): i for i in universe if demo_venue_symbol(i)}
        self._cache: dict[str, PriceHistory] = {}
        self.quote_now = DEMO_INTRADAY_NOW  # Zeitpunkt der „aktuellen“ DEMO-Kurse

    def fetch_quotes(self, symbols: list[str], *, budget_s: float = 900.0, progress=None) -> QuoteBatchResult:
        """Synthetische aktuelle Kurse wie die Sammelabfrage von Yahoo: für Börsen, deren Sitzung bis
        ``quote_now`` begonnen hat, ein Kurs dieses Tages (verzögert um 15 Minuten, nach Börsenschluss der
        Schlusskurs), sonst der letzte Schlusskurs mit seinem Handelstag."""
        result = QuoteBatchResult(endpoint="demo")
        unique = list(dict.fromkeys(s for s in symbols if s))
        result.requests = (len(unique) + 19) // 20
        now = self.quote_now
        for symbol in unique:
            inst = self.instruments.get(symbol)
            if inst is None or inst.pattern in ("no_data", "missing_cutoff"):
                result.missing[symbol] = "keine Daten"
                continue
            history = self._build(inst)
            last_day = int(history.days[-1])
            code = inst.calendar
            today = None
            for day in self.calendars.sessions(code, last_day + 1, last_day + 5).tolist():
                opening = self.calendars.session_open_utc(code, int(day))
                if opening is not None and opening <= now:
                    today = int(day)
            tz_name = _CLOSES[code][0]
            if today is None:
                close_at = self.calendars.session_close_utc(code, last_day)
                result.quotes[symbol] = LiveQuote(symbol, float(history.close[-1]), close_at, last_day, float(history.volume[-1]),
                                                  float(history.close[-2]) if len(history.close) > 1 else math.nan, inst.currency, tz_name)
                continue
            rng = np.random.default_rng(7000 + inst.seed)
            move = {"steady_strong": 0.012, "late_rally": 0.03, "falling": -0.015, "steady_down": -0.008}.get(inst.pattern, 0.0) + rng.normal(0.0, 0.008)
            opening = self.calendars.session_open_utc(code, today)
            close_at = self.calendars.session_close_utc(code, today)
            when = min(now - dt.timedelta(minutes=15), close_at) if close_at is not None else now - dt.timedelta(minutes=15)
            share = 1.0 if close_at is not None and now >= close_at else max(0.05, (now - opening).total_seconds() / max(1.0, (close_at - opening).total_seconds()))
            volume = float(history.volume[-1]) * share if np.isfinite(history.volume[-1]) else math.nan
            result.quotes[symbol] = LiveQuote(symbol, float(history.close[-1]) * (1.0 + move), when, today, volume, float(history.close[-1]), inst.currency, tz_name)
        if progress is not None:
            progress(len(unique), len(unique))
        return result

    def fetch_history(self, symbol: str, start_day: int, end_day: int, *, session_final: SessionFinal | None = None) -> PriceHistory:
        if symbol in self.venue_instruments:
            return self._fetch_venue(symbol, start_day, end_day, session_final)
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

    def _fetch_venue(self, symbol: str, start_day: int, end_day: int, session_final: SessionFinal | None) -> PriceHistory:
        inst = self.venue_instruments[symbol]
        if inst.pattern == "recent_ipo":
            raise NoDataError(f"{symbol}: DEMO – am zweiten Börsenplatz keine Kurse")
        ref = self._build(inst)
        sessions = self.calendars.sessions("XFRA", date_to_day(DEMO_START), date_to_day(dt.date(2026, 10, 12)))
        k = np.searchsorted(ref.days, sessions, side="right") - 1
        valid = k >= 0
        days = sessions[valid]
        ref_close = ref.close[k[valid]].astype(float)
        if inst.pattern == "impulse":
            jump_day = int(ref.days[len(ref.days) - 6])
            ref_close = np.where(ref.days[k[valid]] >= jump_day, ref_close / 1.6, ref_close)
        base_currency = "GBP" if inst.currency == "GBp" else inst.currency
        unit = 0.01 if inst.currency == "GBp" else 1.0
        eur = np.array([ref_close[i] * unit / _demo_per_eur_asof(base_currency, int(d)) for i, d in enumerate(days)])
        rng = np.random.default_rng(5000 + inst.seed)
        close = eur * (1.0 + rng.normal(0.0, 0.002, len(days)))
        if inst.isin == demo_venue_offset_isin():
            close = np.where(days <= date_to_day(dt.date(2026, 10, 12)) - DEMO_VENUE_OFFSET_DAYS, close * 0.85, close)
        mask = (days >= start_day) & (days <= end_day)
        if session_final is not None:
            mask &= np.array([session_final(int(d)) for d in days], dtype=bool)
        if not mask.any():
            raise NoDataError(f"{symbol}: keine Daten im Zeitraum")
        close = close[mask]
        return PriceHistory(
            provider=self.name,
            symbol=symbol,
            days=days[mask].astype(np.int64),
            open=close,
            high=close,
            low=close,
            close=close,
            volume=rng.integers(0, 20_000, len(close)).astype(float),
            close_raw=close.copy(),
            currency="EUR",
            price_unit="EUR",
            unit_factor=1.0,
            exchange_name="XFRA",
            exchange_tz="Europe/Berlin",
            instrument_type="EQUITY",
            long_name=inst.name,
            fetched_at=DEMO_NOW,
            notes=["DEMO – synthetischer zweiter Börsenplatz"],
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


def _demo_per_eur_asof(currency: str, day: int) -> float:
    """DEMO-Kurs (Einheiten je EUR) am Tag ``day`` oder am letzten Tag davor."""
    if currency == "EUR":
        return 1.0
    table = _demo_fx_table()
    days, rates = table[currency]
    k = int(np.searchsorted(days, day, side="right")) - 1
    return float(rates[max(k, 0)])


_FX_TABLE: dict[str, tuple[np.ndarray, np.ndarray]] = {}


def _demo_fx_table() -> dict[str, tuple[np.ndarray, np.ndarray]]:
    if not _FX_TABLE:
        rows = DemoFxSource().fetch().rows
        for currency in _DEMO_FX_PER_EUR:
            pairs = sorted((day, rate) for day, cur, rate in rows if cur == currency)
            _FX_TABLE[currency] = (np.array([d for d, _ in pairs], dtype=np.int64), np.array([r for _, r in pairs], dtype=float))
    return _FX_TABLE


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


class DemoFactsProvider:
    """Synthetische Kennzahlen, Kursziele, Bewertung und Nachrichten (DEMO, ab 1.6) – deterministisch je Symbol.

    Rund ein Viertel der Aktien hat keine Analysten (wie bei kleinen Werten üblich); einige haben
    Kursziele unter dem Kurs. Alle Texte tragen „DEMO“."""

    name = "demo"

    def __init__(self, prices: DemoProvider | None = None) -> None:
        self.prices = prices or DemoProvider()

    def _rng(self, symbol: str, salt: int = 0) -> np.random.Generator:
        seed = sum((k + 1) * ord(ch) for k, ch in enumerate(symbol)) + salt
        return np.random.default_rng(seed)

    def fetch_facts(self, symbol: str) -> dict:
        inst = self.prices.instruments.get(symbol)
        if inst is None or inst.pattern == "no_data":
            raise NoDataError(f"{symbol}: DEMO ohne Kennzahlen")
        history = self.prices._build(inst)
        close = float(history.close[-1])
        rng = self._rng(symbol)
        analysts = int(rng.choice([0, 0, 1, 3, 5, 8, 12, 20]))
        factor = float(np.clip(rng.normal(1.15, 0.25), 0.6, 2.4))
        buy, hold, sell = int(rng.integers(0, 10)), int(rng.integers(0, 6)), int(rng.integers(0, 3))
        old_buy = max(0, buy - int(rng.integers(-2, 3)))
        sector = ["Technology", "Healthcare", "Industrials", "Financial Services", "Consumer Cyclical"][int(rng.integers(0, 5))]
        today = date_to_day(DEMO_NOW.date())

        def row(month, b):
            return {"monat": month, "stark_kaufen": b // 2, "kaufen": b - b // 2, "halten": hold, "verkaufen": sell, "stark_verkaufen": 0}

        has = analysts > 0
        # Börsenwert (ab 1.11) aus eigenem Zufallsstrom, damit alle übrigen DEMO-Werte gleich bleiben;
        # in der Hauptwährung der Notierung wie bei Yahoo (GBP auch bei Kursen in Pence)
        cap = round(float(10 ** self._rng(symbol, 13).uniform(7.3, 11.6)), -4)
        return {
            "symbol": symbol,
            "analysten": {
                "anzahl": analysts,
                "ziel_mittel": round(close * factor, 4) if has else None,
                "ziel_median": round(close * factor, 4) if has else None,
                "ziel_hoch": round(close * factor * 1.35, 4) if has else None,
                "ziel_tief": round(close * factor * 0.7, 4) if has else None,
                "kurs": round(close, 4),
                "empfehlung_mittel": round(float(np.clip(3.0 - (buy - sell) / 4.0, 1.0, 5.0)), 2) if has else None,
                "empfehlung": "buy" if has and buy > hold else ("hold" if has else None),
                "kaufen_anteil": round(buy / (buy + hold + sell), 3) if has and (buy + hold + sell) else None,
                "empfehlungen_anzahl": buy + hold + sell if has else 0,
            },
            "empfehlungen": [row("0m", buy), row("-1m", buy), row("-2m", old_buy), row("-3m", old_buy)] if has else [],
            "urteile": [
                {"tag": today - int(rng.integers(1, 60)), "haus": f"DEMO-Bank {k + 1}", "aktion": "bestätigt", "von": "Buy", "zu": "Buy",
                 "ziel": round(close * factor * (1 + 0.05 * k), 4), "ziel_vorher": round(close * factor * 0.95, 4), "ziel_aktion": "angehoben"}
                for k in range(min(3, analysts))
            ] if inst.exchange_key == "US" else [],
            "urteile_anzahl": min(3, analysts) if inst.exchange_key == "US" else 0,
            "bewertung": {"kgv": round(float(rng.uniform(8, 40)), 2), "kgv_erwartet": round(float(rng.uniform(6, 35)), 2), "peg": round(float(rng.uniform(0.5, 3.0)), 2),
                          "kbv": round(float(rng.uniform(0.8, 8)), 2), "ev_ebitda": None, "dividende": round(float(rng.uniform(0, 0.05)), 4), "boersenwert": cap},
            "wachstum": {"gewinn_naechstes_jahr": round(float(rng.normal(0.1, 0.15)), 4), "gewinn_dieses_jahr": None,
                         "umsatz_naechstes_jahr": round(float(rng.normal(0.06, 0.08)), 4), "umsatz_quartal": None, "gewinn_quartal": None, "schaetzungen": analysts},
            "finanzen": {"bruttomarge": None, "operative_marge": None, "nettomarge": round(float(rng.normal(0.1, 0.08)), 4),
                         "eigenkapitalrendite": round(float(rng.normal(0.12, 0.1)), 4), "verschuldung": round(float(abs(rng.normal(0.8, 0.6))), 4),
                         "liquiditaet": None, "free_cashflow_positiv": bool(rng.random() > 0.25)},
            "risiko": {"beta": round(float(rng.uniform(0.5, 2.0)), 2), "leerverkauf": None, "institutionen": None, "insider": None,
                       "veraenderung_52w": None, "hoch_52w": round(float(history.close.max()), 4), "tief_52w": round(float(history.close.min()), 4)},
            "termine": {"zahlen": today + int(rng.integers(5, 80))},
            "branche": {"sektor": sector, "industrie": "DEMO"},
            "waehrung_bilanz": inst.currency if inst.currency != "GBp" else "GBP",
        }

    def fetch_insights(self, symbol: str) -> dict | None:
        rng = self._rng(symbol, 7)
        label = ["unterbewertet", "fair", "ueberbewertet"][int(rng.integers(0, 3))]
        return {"bewertung": label, "abschlag": {"unterbewertet": 0.12, "fair": 0.0, "ueberbewertet": -0.1}[label], "bewertung_quelle": "DEMO",
                "ausblick": {"kurz": "steigend", "mittel": "seitwärts", "lang": "steigend"}, "ausblick_quelle": "DEMO", "research": None}

    def fetch_news(self, query: str, *, count: int = 12) -> list[dict]:
        rng = self._rng(query, 11)
        base = DEMO_NOW.timestamp()
        titles = ["DEMO: Company beats estimates, raises outlook", "DEMO: Analyst upgrades shares", "DEMO: Shares fall after warning", "DEMO: Quarterly report due next week"]
        tones = [1, 1, -1, 0]
        out = []
        for k in range(int(rng.integers(0, 4))):
            j = int(rng.integers(0, len(titles)))
            out.append({"titel": titles[j], "quelle": "DEMO-Nachrichten", "zeit": int(base - (k + 1) * 9000), "link": "https://example.org/demo",
                        "bezug": True, "tendenz": tones[j]})
        return out


class DemoExtraSources:
    """Synthetischer zweiter Kursziel-Konsens und Community-Stimmung (DEMO)."""

    def __init__(self, facts: DemoFactsProvider) -> None:
        self.facts = facts

    def nasdaq_targets(self, symbol: str) -> dict | None:
        data = self.facts.fetch_facts(symbol)["analysten"]
        if not data.get("anzahl"):
            return None
        return {"ziel": round(data["ziel_mittel"] * 1.03, 4), "tief": data["ziel_tief"], "hoch": data["ziel_hoch"], "anzahl": data["anzahl"],
                "kaufen": None, "halten": None, "verkaufen": None}

    def community(self, symbol: str) -> dict | None:
        rng = self.facts._rng(symbol, 23)
        bull = int(rng.integers(0, 20))
        bear = int(rng.integers(0, 10))
        return {"beitraege": 30, "bullish": bull, "bearish": bear, "je_tag": round(float(rng.uniform(0.5, 40.0)), 2),
                "erster": None, "letzter": None, "beobachter": int(rng.integers(100, 50000))}
