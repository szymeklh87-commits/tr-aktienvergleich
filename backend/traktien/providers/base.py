"""Gemeinsame Datentypen und Schnittstellen der Anbieter-Adapter."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Callable, Protocol

import numpy as np

from ..analytics.quality import SplitEvent


class ProviderError(RuntimeError):
    """Allgemeiner Anbieterfehler (einzelnes Instrument)."""


class NoDataError(ProviderError):
    """Anbieter kennt das Symbol nicht oder liefert keine Daten."""


class ProviderThrottled(ProviderError):
    """Anbieter drosselt dauerhaft (HTTP 429). Lauf soll Checkpoint setzen und später fortsetzen."""


@dataclass
class ListingCandidate:
    """Mögliche Börsennotierung einer ISIN laut Identitätsquelle."""

    source: str
    exchange_key: str | None
    provider_symbol: str | None
    ticker: str | None
    exch_code: str | None
    name: str | None = None
    security_type: str | None = None
    security_type2: str | None = None
    figi: str | None = None
    composite_figi: str | None = None
    share_class_figi: str | None = None
    currency: str | None = None


@dataclass
class PriceHistory:
    """Normalisierte Tageskurse einer Notierung.

    ``close`` ist der splitbereinigte Schlusskurs (Rangbasis). ``close_total`` ist ein
    vom Anbieter dividendenbereinigter Wert und wird getrennt gespeichert; er wird nie
    stillschweigend als nur splitbereinigt verwendet. ``close_raw`` ist der unveränderte
    Schlusskurs, wenn vorhanden oder aus Splitfaktoren rekonstruiert.
    """

    provider: str
    symbol: str
    days: np.ndarray
    open: np.ndarray
    high: np.ndarray
    low: np.ndarray
    close: np.ndarray
    volume: np.ndarray
    close_raw: np.ndarray | None = None
    close_total: np.ndarray | None = None
    currency: str | None = None
    price_unit: str | None = None
    unit_factor: float = 1.0
    exchange_name: str | None = None
    exchange_tz: str | None = None
    instrument_type: str | None = None
    long_name: str | None = None
    short_name: str | None = None
    splits: list[SplitEvent] = field(default_factory=list)
    dividends: list[tuple[int, float]] = field(default_factory=list)
    bar_times_utc: list[str | None] = field(default_factory=list)
    fetched_at: dt.datetime | None = None
    raw_close_reconstructed: bool = False
    dropped_unfinished: int = 0
    dropped_invalid: int = 0
    notes: list[str] = field(default_factory=list)

    def __len__(self) -> int:
        return int(len(self.days))


SessionFinal = Callable[[int], bool]


class PriceProvider(Protocol):
    name: str

    def fetch_history(
        self, symbol: str, start_day: int, end_day: int, *, session_final: SessionFinal | None = None
    ) -> PriceHistory: ...


class CalendarProvider(Protocol):
    def available(self, code: str) -> bool: ...

    def sessions(self, code: str, start_day: int, end_day: int) -> np.ndarray: ...

    def session_close_utc(self, code: str, day: int) -> dt.datetime | None: ...

    def version(self) -> str: ...
