"""Yahoo-Finance-Adapter (Tageskurse, Splits, ISIN-Suche, aktuelle Kurse für den Zwischenstand).

Kennzeichnung: inoffizielle, nicht dokumentierte Schnittstelle ohne Lizenz für einen
dauerhaften Massendatenfeed. Geeignet nur für private, nicht kommerzielle Auswertung;
Nutzungsbedingungen von Yahoo beachten. Die veröffentlichten Daten werden deshalb
verschlüsselt und nicht öffentlich lesbar bereitgestellt.

Felder:
* ``close`` – von Yahoo splitbereinigter Schlusskurs → Rangbasis.
* ``adjclose`` – zusätzlich dividendenbereinigt → nur getrennt gespeichert.
* Unveränderter Schlusskurs wird aus den Splitereignissen rekonstruiert und so markiert.
* Tageskerzen einer noch nicht abgeschlossenen Sitzung werden verworfen.
* Aktuelle Kurse (Zwischenstand, ab 1.6) kommen aus der Sammelabfrage „spark“ – bis zu 20 Werte je
  Abruf, je Börse bis etwa 15–20 Minuten verzögert. Sie werden nie als Tagesschlusskurse gespeichert.
* Kursziele und Empfehlungen der Analysten (Potenzial, ab 1.6) kommen aus „quoteSummary“ – ein Abruf
  je Wert. Yahoo verlangt dafür ein Sitzungs-Cookie und einen dazu passenden „Crumb“; beides wird nur
  im Speicher gehalten, nie gespeichert oder protokolliert.
"""

from __future__ import annotations

import datetime as dt
import math
from typing import Any
from urllib.parse import quote

import numpy as np

from ..analytics.quality import SplitEvent
from ..util.timeutil import UTC, day_to_date, iso_utc, session_date_from_timestamp, date_to_day, utc_now
from .base import (
    AnalystView,
    ListingCandidate,
    LiveQuote,
    NoDataError,
    PriceHistory,
    ProviderError,
    ProviderThrottled,
    QuoteBatchResult,
    SessionFinal,
)
from .exchanges import ExchangeTable, unit_info
from .http import HttpClient

BASE = "https://query2.finance.yahoo.com"
NAME = "yahoo"
SPARK_BATCH = 20  # mehr Werte je Abruf lehnt die Schnittstelle ab
# Varianten der Sammelabfrage in der Reihenfolge, in der sie versucht werden (erste funktionierende bleibt)
SPARK_ENDPOINTS = (
    "https://query2.finance.yahoo.com/v7/finance/spark",
    "https://query1.finance.yahoo.com/v7/finance/spark",
    "https://query1.finance.yahoo.com/v8/finance/spark",
)
# Sitzungs-Cookie (Antwort ist meist 404 – entscheidend ist das gesetzte Cookie) und Crumb dazu
COOKIE_URL = "https://fc.yahoo.com"
CRUMB_URLS = (
    "https://query1.finance.yahoo.com/v1/test/getcrumb",
    "https://query2.finance.yahoo.com/v1/test/getcrumb",
)
ANALYST_MODULES = "financialData,recommendationTrend"


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

    close_from_quote: list[int] = []
    filled = _close_from_quote(meta, tz_name, timestamps, quote_block, by_day, session_final)
    if filled is not None:
        day, row, had_placeholder = filled
        by_day[day] = row
        close_from_quote.append(day)
        if had_placeholder:
            dropped_invalid = max(0, dropped_invalid - 1)

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
        close_from_quote=close_from_quote,
    )


def _close_from_quote(meta: dict, tz_name: str, timestamps: list, quote_block: dict, by_day: dict, session_final: SessionFinal | None):
    """Schlusskurs der letzten Sitzung aus der Kursmeldung, wenn die Tageskerze noch keinen hat.

    Yahoo legt die Tageskerze mancher Börsen sofort an, füllt den Schlusskurs aber teils erst Stunden
    (oder einen Tag) später. Die Kursmeldung derselben Antwort (``regularMarketPrice`` mit Zeitpunkt
    ``regularMarketTime``) enthält dann bereits den letzten Kurs der Sitzung. Übernommen wird er nur,
    wenn (1) die Sitzung laut Börsenkalender abgeschlossen ist (``session_final``), (2) die Meldung zu
    dieser Sitzung gehört, (3) es für diesen Tag keine Tageskerze mit Schlusskurs gibt und (4) keine
    spätere Sitzung mit Kurs vorliegt. Tageshoch, -tief und Umsatz kommen ebenfalls aus der Meldung.
    Rückgabe: (Tag, Zeile wie in ``parse_chart``, ob es eine leere Tageskerze gab) oder ``None``."""
    if session_final is None:
        return None
    price = _first_number(meta.get("regularMarketPrice"))
    when = meta.get("regularMarketTime")
    if not (price > 0) or when is None:
        return None
    try:
        when = int(when)
        day = date_to_day(session_date_from_timestamp(when, tz_name))
    except (TypeError, ValueError, OverflowError, OSError):
        return None
    if day in by_day or (by_day and max(by_day) > day) or not session_final(day):
        return None
    placeholder = None
    for i, ts in enumerate(timestamps):
        if ts is not None and date_to_day(session_date_from_timestamp(ts, tz_name)) == day:
            placeholder = i
    open_ = _num(quote_block.get("open"), placeholder) if placeholder is not None else math.nan
    high = _first_number(meta.get("regularMarketDayHigh"), _num(quote_block.get("high"), placeholder) if placeholder is not None else None)
    low = _first_number(meta.get("regularMarketDayLow"), _num(quote_block.get("low"), placeholder) if placeholder is not None else None)
    volume = _first_number(meta.get("regularMarketVolume"), _num(quote_block.get("volume"), placeholder) if placeholder is not None else None)
    # Tageshoch/-tief nur übernehmen, wenn sie zum Schlusskurs passen
    if not (high >= price and low <= price and low > 0):
        high = low = math.nan
    row = (open_, high, low, float(price), volume, math.nan, iso_utc(dt.datetime.fromtimestamp(when, tz=UTC)))
    return day, row, placeholder is not None


def _first_number(*values) -> float:
    for value in values:
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(number):
            return number
    return math.nan


def _last_valid(timestamps: list | None, closes: list | None) -> tuple[int | None, float]:
    """Letzter Zeitpunkt mit gültigem Kurs einer Kursreihe (Spark liefert Lücken als ``null``)."""
    for ts, close in zip(reversed(timestamps or []), reversed((closes or [])[: len(timestamps or [])])):
        number = _first_number(close)
        if ts is not None and number > 0:
            return int(ts), number
    return None, math.nan


def _quote_from_chart_like(symbol: str, meta: dict, timestamps: list | None, closes: list | None) -> LiveQuote | None:
    """Aktueller Kurs aus einem chart-ähnlichen Ergebnis (``meta`` plus Kursreihe)."""
    tz_name = meta.get("exchangeTimezoneName") or "UTC"
    last_ts, last_close = _last_valid(timestamps, closes)
    price = _first_number(meta.get("regularMarketPrice"))
    ts = meta.get("regularMarketTime")
    if not (price > 0) or ts is None:
        price, ts = last_close, last_ts
    if not (price > 0) or ts is None:
        return None
    try:
        when = dt.datetime.fromtimestamp(int(ts), tz=UTC)
    except (TypeError, ValueError, OverflowError, OSError):
        return None
    session_day = date_to_day(session_date_from_timestamp(int(ts), tz_name))
    return LiveQuote(
        symbol=symbol,
        price=float(price),
        time_utc=when,
        session_day=session_day,
        volume=_first_number(meta.get("regularMarketVolume")),
        previous_close=_first_number(meta.get("previousClose"), meta.get("chartPreviousClose")),
        currency=meta.get("currency"),
        exchange_tz=tz_name,
    )


def parse_spark(payload: dict) -> tuple[dict[str, LiveQuote], dict[str, str]]:
    """Wandelt eine Spark-Antwort in aktuelle Kurse um (reine Funktion, testbar).

    Zwei Formen: v7 ``{"spark": {"result": [{"symbol", "response": [{"meta", "timestamp",
    "indicators"}]}]}}`` und v8 ``{"AAPL": {"timestamp", "close", "chartPreviousClose", …}}``.
    Rückgabe: Kurse je Symbol und Symbole ohne verwertbaren Kurs mit Grund."""
    quotes: dict[str, LiveQuote] = {}
    missing: dict[str, str] = {}
    payload = payload or {}
    spark = payload.get("spark")
    if isinstance(spark, dict):
        if spark.get("error"):
            error = spark["error"]
            raise ProviderError(f"Spark: {error.get('description') or error.get('code') or error}" if isinstance(error, dict) else f"Spark: {error}")
        for item in spark.get("result") or []:
            symbol = item.get("symbol")
            if not symbol:
                continue
            responses = item.get("response") or []
            if not responses:
                missing[symbol] = "keine Daten"
                continue
            result = responses[0] or {}
            quote_block = ((result.get("indicators") or {}).get("quote") or [{}])[0] or {}
            quote = _quote_from_chart_like(symbol, result.get("meta") or {}, result.get("timestamp"), quote_block.get("close"))
            if quote is None:
                missing[symbol] = "kein gültiger Kurs"
            else:
                quotes[symbol] = quote
        return quotes, missing
    for symbol, item in payload.items():
        if not isinstance(item, dict):
            continue
        meta = {
            "regularMarketPrice": item.get("regularMarketPrice"),
            "regularMarketTime": item.get("regularMarketTime"),
            "previousClose": item.get("previousClose"),
            "chartPreviousClose": item.get("chartPreviousClose"),
            "exchangeTimezoneName": item.get("exchangeTimezoneName"),
            "currency": item.get("currency"),
        }
        quote = _quote_from_chart_like(item.get("symbol") or symbol, meta, item.get("timestamp"), item.get("close"))
        if quote is None:
            missing[symbol] = "kein gültiger Kurs"
        else:
            quotes[quote.symbol] = quote
    return quotes, missing


def _raw(value: Any) -> float:
    """quoteSummary liefert Zahlen als Zahl („formatted=false“) oder als ``{"raw": …, "fmt": …}``."""
    if isinstance(value, dict):
        value = value.get("raw")
    return _first_number(value)


def _positive(value: Any) -> float:
    number = _raw(value)
    return number if number > 0 else math.nan


def _count(value: Any) -> int:
    number = _raw(value)
    return int(round(number)) if number > 0 else 0


def parse_quote_summary(payload: dict, symbol: str) -> AnalystView:
    """Kursziele und Empfehlungen aus einer quoteSummary-Antwort (Module „financialData“ und
    „recommendationTrend“; reine Funktion, testbar). Ohne Analystenabdeckung: ``analysts == 0``."""
    summary = (payload or {}).get("quoteSummary")
    if summary is None:
        summary = (payload or {}).get("finance") or {}
    error = summary.get("error")
    if error:
        description = (error.get("description") or error.get("code")) if isinstance(error, dict) else str(error)
        if "not found" in str(description).lower():
            raise NoDataError(f"{symbol}: {description}")
        raise ProviderError(f"{symbol}: {description}")
    results = summary.get("result") or []
    if not results:
        raise NoDataError(f"{symbol}: keine Daten")
    result = results[0] or {}
    fin = result.get("financialData") or {}
    key = fin.get("recommendationKey")
    view = AnalystView(
        symbol=symbol,
        analysts=_count(fin.get("numberOfAnalystOpinions")),
        target_mean=_positive(fin.get("targetMeanPrice")),
        target_median=_positive(fin.get("targetMedianPrice")),
        target_high=_positive(fin.get("targetHighPrice")),
        target_low=_positive(fin.get("targetLowPrice")),
        current_price=_positive(fin.get("currentPrice")),
        rec_mean=_positive(fin.get("recommendationMean")),
        rec_key=key if isinstance(key, str) and key and key.lower() != "none" else None,
    )
    trend = (result.get("recommendationTrend") or {}).get("trend") or []
    current = next((row for row in trend if isinstance(row, dict) and row.get("period") == "0m"), None)
    if current is not None:
        view.trend_period = "0m"
        view.strong_buy = _count(current.get("strongBuy"))
        view.buy = _count(current.get("buy"))
        view.hold = _count(current.get("hold"))
        view.sell = _count(current.get("sell"))
        view.strong_sell = _count(current.get("strongSell"))
    return view


def _plausible_crumb(text: str) -> bool:
    return 5 <= len(text) <= 64 and not any(ch.isspace() for ch in text) and not any(ch in text for ch in "<>{}\"'")


class YahooProvider:
    name = NAME

    def __init__(self, http: HttpClient | None = None, *, requests_per_second: float = 2.5) -> None:
        self.http = http or HttpClient(
            min_interval={"query2.finance.yahoo.com": 1.0 / requests_per_second, "query1.finance.yahoo.com": 1.0 / requests_per_second},
            impersonate="chrome",
        )
        self._crumb: str | None = None  # nur im Speicher; nie speichern oder protokollieren

    def ensure_crumb(self, *, refresh: bool = False) -> str:
        """Sitzungs-Cookie holen und den dazugehörigen Crumb abfragen (für quoteSummary nötig)."""
        if self._crumb and not refresh:
            return self._crumb
        self._crumb = None
        try:
            self.http.get(COOKIE_URL, headers={"Accept": "text/html,application/xhtml+xml,*/*;q=0.8"})
        except ConnectionError:
            pass  # ohne Cookie scheitert der Crumb-Abruf unten mit einer klaren Meldung
        last = "keine Antwort"
        for url in CRUMB_URLS:
            try:
                response = self.http.get(url, headers={"Accept": "text/plain,*/*;q=0.8"})
            except ConnectionError as exc:
                last = type(exc).__name__
                continue
            text = response.content.decode("utf-8", "replace").strip()
            if response.status_code == 200 and _plausible_crumb(text):
                self._crumb = text
                return text
            last = f"HTTP {response.status_code}"
        raise ProviderError(f"Yahoo: kein Crumb erhalten ({last})")

    def analyst_view(self, symbol: str) -> AnalystView:
        """Kursziele und Empfehlungen einer Notierung (ein Abruf; bei abgelaufenem Crumb einmal erneuert)."""
        url = f"{BASE}/v10/finance/quoteSummary/{quote(symbol, safe='')}"
        response = None
        for attempt in range(2):
            crumb = self.ensure_crumb(refresh=attempt > 0)
            params = {"modules": ANALYST_MODULES, "crumb": crumb, "formatted": "false", "lang": "en-US", "region": "US"}
            response = self.http.get(url, params=params)
            if response.status_code != 401:
                break
        assert response is not None
        if response.status_code == 404:
            raise NoDataError(f"{symbol}: kein Eintrag (404)")
        if response.status_code != 200:
            raise ProviderError(f"{symbol}: HTTP {response.status_code}")
        try:
            payload = response.json()
        except ValueError as exc:
            raise ProviderError(f"{symbol}: Antwort ist kein JSON") from exc
        return parse_quote_summary(payload, symbol)

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

    def spark(self, symbols: list[str], endpoint: str) -> dict:
        """Rohe Spark-Antwort für bis zu ``SPARK_BATCH`` Symbole (letzter Kurs je Wert)."""
        if not symbols or len(symbols) > SPARK_BATCH:
            raise ValueError(f"Spark: 1 bis {SPARK_BATCH} Symbole je Abruf")
        response = self.http.get(endpoint, params={"symbols": ",".join(symbols), "range": "1d", "interval": "1d"})
        if response.status_code != 200:
            raise ProviderError(f"Spark: HTTP {response.status_code}")
        try:
            return response.json()
        except ValueError as exc:
            raise ProviderError("Spark: Antwort ist kein JSON") from exc

    def fetch_quotes(self, symbols: list[str], *, budget_s: float = 900.0, progress=None) -> QuoteBatchResult:
        """Aktuelle Kurse vieler Notierungen in Abrufen zu je 20 Werten.

        Die erste funktionierende Variante aus ``SPARK_ENDPOINTS`` wird beibehalten. Drosselt Yahoo
        dauerhaft, endet der Abruf mit ``throttled``; bereits geladene Kurse bleiben erhalten."""
        import time

        result = QuoteBatchResult()
        unique = list(dict.fromkeys(s for s in symbols if s))
        started = time.monotonic()
        endpoints = list(SPARK_ENDPOINTS)
        failed_in_row = 0
        for start in range(0, len(unique), SPARK_BATCH):
            batch = unique[start : start + SPARK_BATCH]
            if time.monotonic() - started > budget_s:
                for symbol in unique[start:]:
                    result.missing.setdefault(symbol, "Zeitbudget erreicht")
                break
            payload = None
            last_error: Exception | None = None
            for endpoint in list(endpoints):
                try:
                    payload = self.spark(batch, endpoint)
                    result.requests += 1
                    if result.endpoint != endpoint:
                        result.endpoint = endpoint
                        endpoints = [endpoint] + [e for e in endpoints if e != endpoint]
                    break
                except ProviderThrottled:
                    result.throttled = True
                    for symbol in unique[start:]:
                        result.missing.setdefault(symbol, "Kursanbieter drosselt")
                    return result
                except (ProviderError, ConnectionError, ValueError) as exc:
                    result.requests += 1
                    last_error = exc
                    continue
            if payload is None:
                for symbol in batch:
                    result.missing[symbol] = f"Abruf fehlgeschlagen ({last_error})"[:120]
                failed_in_row += 1
                if failed_in_row >= 3 and not result.quotes:
                    # Sammelabfrage offenbar nicht verfügbar: nicht für alle Werte weiter vergeblich abfragen
                    for symbol in unique[start + len(batch) :]:
                        result.missing.setdefault(symbol, f"Sammelabfrage nicht verfügbar ({last_error})"[:120])
                    return result
                continue
            failed_in_row = 0
            try:
                quotes, missing = parse_spark(payload)
            except ProviderError as exc:
                for symbol in batch:
                    result.missing[symbol] = str(exc)[:120]
                continue
            result.quotes.update(quotes)
            for symbol in batch:
                if symbol not in quotes:
                    result.missing[symbol] = missing.get(symbol, "nicht in der Antwort")
            if progress is not None:
                progress(start + len(batch), len(unique))
        return result

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
