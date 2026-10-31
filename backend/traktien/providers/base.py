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
    # Eröffnung, Tageshoch und -tief dieses Handelstags (ab 1.17 für den Sammelabruf; ``nan`` = nicht gemeldet)
    day_open: float = float("nan")
    day_high: float = float("nan")
    day_low: float = float("nan")
    # Ab 1.21 (Kursaktualisierung einzelner Aktien): vom Anbieter gemeldete Verzögerung in Minuten
    # (Yahoo „exchangeDataDelayedBy“; ``None`` = nicht gemeldet) und Handelsstatus (Yahoo „marketState“:
    # REGULAR, PRE, POST, CLOSED …)
    delay_min: int | None = None
    market_state: str | None = None


@dataclass
class QuoteBatchResult:
    """Ergebnis eines Kursabrufs für den Zwischenstand: Kurse je Symbol und Symbole ohne Kurs."""

    quotes: dict[str, LiveQuote] = field(default_factory=dict)
    missing: dict[str, str] = field(default_factory=dict)  # Symbol → Grund
    requests: int = 0
    endpoint: str | None = None
    throttled: bool = False
    # Aufteilung nach Weg (ab 1.12, nur Zählungen für die Laufübersicht)
    quote_requests: int = 0
    quote_found: int = 0
    spark_requests: int = 0
    spark_found: int = 0


@dataclass
class RecentBars:
    """Letzte Tageskurse einer Notierung aus einer Sammelabfrage (ab 1.17, Kursabruf „Sammelabruf“).

    ``timestamps`` sind die Zeitpunkte der Tageskerzen (Sekunden seit 1970, UTC) wie im Chart-Abruf,
    ``close`` die dazugehörigen splitbereinigten Schlusskurse (``nan`` = keine Angabe). Die Handelstage
    rechnet erst die Planung mit der Zeitzone der Börse aus (``exchange_tz`` aus der Antwort, sonst die der
    Notierung). ``last_*`` ist die Kursmeldung der neuesten Sitzung (Zeitpunkt, Kurs, Umsatz, Tageshoch und
    -tief, Eröffnung), soweit der Anbieter sie mitliefert – sonst ``None`` bzw. ``nan``."""

    symbol: str
    timestamps: list[int]
    close: np.ndarray
    currency: str | None = None
    exchange_tz: str | None = None
    exchange_name: str | None = None
    instrument_type: str | None = None
    long_name: str | None = None
    short_name: str | None = None
    last_time: int | None = None
    last_price: float = float("nan")
    last_volume: float = float("nan")
    last_high: float = float("nan")
    last_low: float = float("nan")
    last_open: float = float("nan")
    previous_close: float = float("nan")
    source: str = "spark"


@dataclass
class RecentBatchResult:
    """Ergebnis eines Sammelabrufs der letzten Tageskurse (ab 1.17): Kurse je Symbol, Symbole ohne Daten mit Grund."""

    bars: dict[str, RecentBars] = field(default_factory=dict)
    missing: dict[str, str] = field(default_factory=dict)
    requests: int = 0
    endpoint: str | None = None
    throttled: bool = False
    seconds: float = 0.0
    # Vorhandene Felder der Kursmeldung (nur Namen und Zählungen, für den Vergleich vor der Umstellung)
    meta_fields: dict[str, int] = field(default_factory=dict)


@dataclass
class HistoryJob:
    """Ein Chart-Abruf des täglichen Laufs (ab 1.17): Tageskurse einer Notierung von ``start_day`` bis ``end_day``.

    ``session_final`` entscheidet beim Auswerten, ob die letzte Kerze schon ein endgültiger Schlusskurs ist; es
    wird immer im aufrufenden Thread benutzt (Börsenkalender und Datenbank bleiben einem Thread vorbehalten)."""

    symbol: str
    start_day: int
    end_day: int
    session_final: SessionFinal | None = None


@dataclass
class HistoryFetchStats:
    """Zählungen eines Kursabrufs über ``fetch_histories`` (ab 1.17, nur Zahlen – für Protokoll und Messung)."""

    workers: int = 1
    hosts: int = 1
    interval_s: float = 0.0
    requests: int = 0  # Chart-Abrufe (ohne Wiederholungen nach HTTP-Fehlern)
    parallel: int = 0  # davon gleichzeitig über mehrere Hosts
    careful: int = 0  # davon einzeln mit dem bisherigen Abstand, nachdem Yahoo gedrosselt hat
    throttled_after: int | None = None  # nach so vielen Abrufen kam die erste Drosselung (HTTP 429)
    http_429: int = 0
    seconds: float = 0.0

    @property
    def per_second(self) -> float:
        return self.requests / self.seconds if self.seconds > 0 else 0.0


# Fehler eines einzelnen Abrufs, die der tägliche Lauf je Notierung behandelt (alles andere bricht ab wie bisher)
HISTORY_ERRORS = (ProviderError, ConnectionError, ValueError)


def history_outcome(provider, job: HistoryJob) -> "PriceHistory | Exception":
    """Ein Abruf über ``fetch_history`` – Fehler einer Notierung als Ergebnis statt als Ausnahme."""
    try:
        return provider.fetch_history(job.symbol, job.start_day, job.end_day, session_final=job.session_final)
    except HISTORY_ERRORS as exc:
        return exc


def fetch_histories_sequential(provider, jobs: list[HistoryJob], stats: HistoryFetchStats | None = None):
    """Nacheinander, in Auftragsreihenfolge: ``(Index, Kursreihe oder Fehler)`` – für Anbieter ohne parallelen Abruf."""
    import time

    stats = stats if stats is not None else HistoryFetchStats()
    started = time.monotonic()
    try:
        for k, job in enumerate(jobs):
            outcome = history_outcome(provider, job)
            stats.requests += 1
            yield k, outcome
    finally:
        stats.seconds = time.monotonic() - started


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

    def session_open_utc(self, code: str, day: int) -> dt.datetime | None: ...

    def version(self) -> str: ...
