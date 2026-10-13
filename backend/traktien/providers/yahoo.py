"""Yahoo-Finance-Adapter (Tageskurse, Splits, ISIN-Suche).

Kennzeichnung: inoffizielle, nicht dokumentierte Schnittstelle ohne Lizenz für einen
dauerhaften Massendatenfeed. Geeignet nur für private, nicht kommerzielle Auswertung;
Nutzungsbedingungen von Yahoo beachten. Die veröffentlichten Daten werden deshalb
verschlüsselt und nicht öffentlich lesbar bereitgestellt.

Felder:
* ``close`` – von Yahoo splitbereinigter Schlusskurs → Rangbasis.
* ``adjclose`` – zusätzlich dividendenbereinigt → nur getrennt gespeichert.
* Unveränderter Schlusskurs wird aus den Splitereignissen rekonstruiert und so markiert.
* Tageskerzen einer noch nicht abgeschlossenen Sitzung werden verworfen.
"""

from __future__ import annotations

import datetime as dt
import math
from typing import Any
from urllib.parse import quote

import numpy as np

from ..analytics.quality import SplitEvent
from ..util.timeutil import UTC, day_to_date, iso_utc, session_date_from_timestamp, date_to_day, utc_now
from .base import ListingCandidate, NoDataError, PriceHistory, ProviderError, SessionFinal
from .exchanges import ExchangeTable, unit_info
from .http import HttpClient

BASE = "https://query2.finance.yahoo.com"
NAME = "yahoo"


def _num(values: list[Any] | None, i: int) -> float:
    if values is None or i >= len(values):
        return math.nan
    value = values[i]
    if value is None:
        return math.nan
    try:
        number = float(value)
    except (TypeError, ValueError):
        return math.nan
    return number if math.isfinite(number) else math.nan


def parse_chart(payload: dict, symbol: str, *, session_final: SessionFinal | None = None, fetched_at: dt.datetime | None = None) -> PriceHistory:
    """Wandelt eine v8-Chart-Antwort in eine ``PriceHistory`` um (reine Funktion, testbar)."""
    chart = (payload or {}).get("chart") or {}
    if chart.get("error"):
        description = chart["error"].get("description") or chart["error"].get("code") or "Fehler"
        raise NoDataError(f"{symbol}: {description}")
    results = chart.get("result") or []
    if not results:
        raise NoDataError(f"{symbol}: keine Daten")
    result = results[0]
    meta = result.get("meta") or {}
    tz_name = meta.get("exchangeTimezoneName") or "UTC"
    timestamps = result.get("timestamp") or []
    indicators = result.get("indicators") or {}
    quote_block = (indicators.get("quote") or [{}])[0] or {}
    adj_block = (indicators.get("adjclose") or [{}])[0] or {}

    by_day: dict[int, tuple] = {}
    dropped_unfinished = 0
    dropped_invalid = 0
    for i, ts in enumerate(timestamps):
        if ts is None:
            continue
        session_day = date_to_day(session_date_from_timestamp(ts, tz_name))
        if session_final is not None and not session_final(session_day):
            dropped_unfinished += 1
            continue
        close = _num(quote_block.get("close"), i)
        if not (close > 0):
            dropped_invalid += 1
            continue
        row = (
            _num(quote_block.get("open"), i),
            _num(quote_block.get("high"), i),
            _num(quote_block.get("low"), i),
            close,
            _num(quote_block.get("volume"), i),
            _num(adj_block.get("adjclose"), i),
            iso_utc(dt.datetime.fromtimestamp(ts, tz=UTC)),
        )
        by_day[session_day] = row  # bei Doppelungen gewinnt der letzte Eintrag desselben Tages

    days = np.array(sorted(by_day), dtype=np.int64)
    rows = [by_day[d] for d in days.tolist()]

    def col(k: int) -> np.ndarray:
        return np.array([row[k] for row in rows], dtype=np.float64)

    splits: list[SplitEvent] = []
    for event in ((result.get("events") or {}).get("splits") or {}).values():
        try:
            numerator = float(event.get("numerator"))
            denominator = float(event.get("denominator"))
            ts = event.get("date")
        except (TypeError, ValueError):
            continue
        if not denominator or ts is None:
            continue
        splits.append(SplitEvent(day=date_to_day(session_date_from_timestamp(ts, tz_name)), factor=numerator / denominator))
    splits.sort(key=lambda e: e.day)

    dividends: list[tuple[int, float]] = []
    for event in ((result.get("events") or {}).get("dividends") or {}).values():
        ts = event.get("date")
        amount = event.get("amount")
        if ts is None or amount is None:
            continue
        dividends.append((date_to_day(session_date_from_timestamp(ts, tz_name)), float(amount)))
    dividends.sort()

    close = col(3)
    close_raw = close.copy()
    for event in splits:
        close_raw[days < event.day] *= event.factor
    currency = meta.get("currency")
    _, factor = unit_info(currency)
    return PriceHistory(
        provider=NAME,
        symbol=symbol,
        days=days,
        open=col(0),
        high=col(1),
        low=col(2),
        close=close,
        volume=col(4),
        close_raw=close_raw,
        close_total=col(5) if adj_block else None,
        currency=currency,
        price_unit=currency,
        unit_factor=factor,
        exchange_name=meta.get("exchangeName"),
        exchange_tz=tz_name,
        instrument_type=meta.get("instrumentType"),
        long_name=meta.get("longName"),
        short_name=meta.get("shortName"),
        splits=splits,
        dividends=dividends,
        bar_times_utc=[row[6] for row in rows],
        fetched_at=fetched_at or utc_now(),
        raw_close_reconstructed=bool(splits),
        dropped_unfinished=dropped_unfinished,
        dropped_invalid=dropped_invalid,
    )


class YahooProvider:
    name = NAME

    def __init__(self, http: HttpClient | None = None, *, requests_per_second: float = 2.5) -> None:
        self.http = http or HttpClient(
            min_interval={"query2.finance.yahoo.com": 1.0 / requests_per_second, "query1.finance.yahoo.com": 1.0 / requests_per_second},
            impersonate="chrome",
        )

    def chart(self, symbol: str, start_day: int | None, end_day: int | None, *, host: str = BASE, range_: str | None = None, interval: str = "1d") -> dict:
        """Rohe v8-Chart-Antwort: Zeitraum über Kalendertage oder ``range_`` (z. B. „1mo“); Tageskerzen,
        für Prüfzwecke auch andere Intervalle (z. B. „1h“)."""
        url = f"{host}/v8/finance/chart/{quote(symbol, safe='')}"
        params = {"interval": interval, "events": "div|split", "includeAdjustedClose": "true"}
        if range_:
            params["range"] = range_
        else:
            start = dt.datetime.combine(day_to_date(start_day) - dt.timedelta(days=1), dt.time(0, 0), tzinfo=UTC)
            end = dt.datetime.combine(day_to_date(end_day) + dt.timedelta(days=2), dt.time(0, 0), tzinfo=UTC)
            params = {"period1": str(int(start.timestamp())), "period2": str(int(end.timestamp())), **params}
        response = self.http.get(url, params=params)
        if response.status_code == 404:
            raise NoDataError(f"{symbol}: Symbol unbekannt (404)")
        if response.status_code != 200:
            raise ProviderError(f"{symbol}: HTTP {response.status_code}")
        try:
            return response.json()
        except ValueError as exc:
            raise ProviderError(f"{symbol}: Antwort ist kein JSON") from exc

    def fetch_history(self, symbol: str, start_day: int, end_day: int, *, session_final: SessionFinal | None = None) -> PriceHistory:
        history = parse_chart(self.chart(symbol, start_day, end_day), symbol, session_final=session_final)
        if len(history) == 0:
            raise NoDataError(f"{symbol}: keine gültigen Tageskurse im Zeitraum")
        return history

    def search(self, query: str, table: ExchangeTable) -> list[ListingCandidate]:
        url = f"{BASE}/v1/finance/search"
        params = {"q": query, "quotesCount": "10", "newsCount": "0", "listsCount": "0", "enableFuzzyQuery": "false"}
        response = self.http.get(url, params=params)
        if response.status_code != 200:
            raise ProviderError(f"Yahoo-Suche: HTTP {response.status_code}")
        return candidates_from_search(response.json(), table)


def candidates_from_search(payload: dict, table: ExchangeTable) -> list[ListingCandidate]:
    out: list[ListingCandidate] = []
    for quote_item in (payload or {}).get("quotes") or []:
        symbol = quote_item.get("symbol")
        if not symbol:
            continue
        quote_type = (quote_item.get("quoteType") or "").upper()
        exchange = table.exchange_for_yahoo_symbol(symbol, quote_item.get("exchange"))
        out.append(
            ListingCandidate(
                source="yahoo_search",
                exchange_key=exchange.key if exchange else None,
                provider_symbol=symbol,
                ticker=symbol.split(".")[0],
                exch_code=quote_item.get("exchange"),
                name=quote_item.get("longname") or quote_item.get("shortname"),
                security_type={"EQUITY": "Common Stock", "ETF": "ETP", "MUTUALFUND": "Mutual Fund"}.get(quote_type, quote_type or None),
            )
        )
    return out
