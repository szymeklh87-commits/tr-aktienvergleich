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
    # Tage, deren Schlusskurs aus der letzten Kursmeldung nach Börsenschluss stammt, weil die Tageskerze
    # beim Anbieter noch ohne Schlusskurs war (ab 1.5.4; wird ersetzt, sobald die Tageskerze kommt)
    close_from_quote: list[int] = field(default_factory=list)

    def __len__(self) -> int:
        return int(len(self.days))


SessionFinal = Callable[[int], bool]


@dataclass
class LiveQuote:
    """Aktueller Kurs einer Notierung für den Zwischenstand (ab 1.6).

    ``price`` ist der letzte gemeldete Kurs in der gelieferten Kurseinheit (wie die Tageskurse, z. B.
    GBp), ``time_utc`` sein Zeitpunkt und ``session_day`` der Handelstag dieses Kurses in der
    Zeitzone der Börse. ``volume`` ist der Umsatz (Stück) dieses Handelstags bis jetzt – nur wenn
    der Anbieter ihn meldet, sonst ``nan``. Anbieter liefern solche Kurse meist mit Verzögerung
    (bei Yahoo je nach Börse bis etwa 15–20 Minuten)."""

    symbol: str
    price: float
    time_utc: dt.datetime
    session_day: int
    volume: float
    previous_close: float
    currency: str | None
    exchange_tz: str | None


@dataclass
class QuoteBatchResult:
    """Ergebnis eines Kursabrufs für den Zwischenstand: Kurse je Symbol und Symbole ohne Kurs."""

    quotes: dict[str, LiveQuote] = field(default_factory=dict)
    missing: dict[str, str] = field(default_factory=dict)  # Symbol → Grund
    requests: int = 0
    endpoint: str | None = None
    throttled: bool = False


@dataclass
class AnalystView:
    """Kursziele und Empfehlungen der Analysten zu einer Notierung (ab 1.6, Grundlage für „Potenzial“).

    Kursziele stehen in der Kurseinheit, in der der Anbieter die Notierung führt (``current_price`` ist
    der Kurs derselben Antwort und dient nur zur Einheitenprüfung, z. B. GBp gegenüber GBP).
    ``analysts`` zählt die Kursziele, ``strong_buy`` … ``strong_sell`` die Empfehlungen des laufenden
    Monats (``trend_period`` „0m“) – beides kann voneinander abweichen. Fehlende Angaben sind ``nan``
    bzw. 0; ``analysts == 0`` heißt: keine Analystenabdeckung gemeldet."""

    symbol: str
    analysts: int
    target_mean: float
    target_median: float
    target_high: float
    target_low: float
    current_price: float
    rec_mean: float  # 1 = starker Kauf … 5 = starker Verkauf
    rec_key: str | None
    strong_buy: int = 0
    buy: int = 0
    hold: int = 0
    sell: int = 0
    strong_sell: int = 0
    trend_period: str | None = None

    @property
    def ratings(self) -> int:
        return self.strong_buy + self.buy + self.hold + self.sell + self.strong_sell

    @property
    def has_targets(self) -> bool:
        return self.analysts > 0 and self.target_mean == self.target_mean and self.target_mean > 0


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
