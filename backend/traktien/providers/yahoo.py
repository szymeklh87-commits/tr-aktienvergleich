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
from ..util.log import get_logger

LOG = get_logger(__name__)

BASE = "https://query2.finance.yahoo.com"
NAME = "yahoo"
SPARK_BATCH = 20  # mehr Werte je Abruf lehnt die Schnittstelle ab
# Ab 1.10 zuerst die Kursabfrage „quote“ (mit Crumb): viele Werte je Abruf – statt rund 300 Spark-Abrufen
# für einen Zwischenstand nur etwa 40. Was sie nicht liefert, holt danach weiter „spark“.
QUOTE_BATCH = 150
QUOTE_ENDPOINTS = (
    "https://query2.finance.yahoo.com/v7/finance/quote",
    "https://query1.finance.yahoo.com/v7/finance/quote",
)
QUOTE_FIELDS = "symbol,regularMarketPrice,regularMarketTime,regularMarketVolume,regularMarketPreviousClose,currency,exchangeTimezoneName,marketState"
# Ab 1.12 laufen die Sammelabfragen eines Zwischenstands parallel: wenige gleichzeitige Abrufe mit gemeinsamem
# Mindestabstand je Host (statt 2,5 Abrufe je Sekunde nacheinander). Rund 60 Abrufe dauern so etwa 8 statt 22 s.
QUOTE_WORKERS = 3
BURST_INTERVAL_S = 0.12
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


def _raw(value):
    """Zahl aus ``{"raw": …, "fmt": …}`` (formatierte Antwort) oder die Zahl selbst."""
    return value.get("raw") if isinstance(value, dict) else value


def parse_quote_response(payload: dict) -> tuple[dict[str, LiveQuote], dict[str, str]]:
    """Wandelt eine Antwort der Kursabfrage „quote“ (v7) in aktuelle Kurse um (reine Funktion, testbar).

    Form: ``{"quoteResponse": {"result": [{"symbol", "regularMarketPrice", "regularMarketTime", …}], "error": null}}``.
    Werte, die Yahoo nicht kennt, fehlen in ``result`` einfach. Rückgabe wie ``parse_spark``."""
    response = (payload or {}).get("quoteResponse")
    if not isinstance(response, dict):
        raise ProviderError("Quote: unerwartete Antwort")
    if response.get("error"):
        error = response["error"]
        raise ProviderError(f"Quote: {error.get('description') or error.get('code') or error}" if isinstance(error, dict) else f"Quote: {error}")
    quotes: dict[str, LiveQuote] = {}
    missing: dict[str, str] = {}
    for item in response.get("result") or []:
        symbol = item.get("symbol") if isinstance(item, dict) else None
        if not symbol:
            continue
        meta = {
            "regularMarketPrice": _raw(item.get("regularMarketPrice")),
            "regularMarketTime": _raw(item.get("regularMarketTime")),
            "regularMarketVolume": _raw(item.get("regularMarketVolume")),
            "previousClose": _raw(item.get("regularMarketPreviousClose")),
            "exchangeTimezoneName": item.get("exchangeTimezoneName"),
            "currency": item.get("currency"),
        }
        quote_value = _quote_from_chart_like(symbol, meta, None, None)
        if quote_value is None:
            missing[symbol] = "kein gültiger Kurs"
        else:
            quotes[symbol] = quote_value
    return quotes, missing


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


# Ein Abruf je Aktie mit allen Modulen für das Potenzial-Ranking (ab 1.6)
FACT_MODULES = (
    "financialData,recommendationTrend,upgradeDowngradeHistory,defaultKeyStatistics,summaryDetail,"
    "earningsTrend,calendarEvents,assetProfile"
)
MAX_ACTIONS = 25  # Analystenurteile je Aktie (die jüngsten)
ACTION_DAYS = 180


def _opt(value: Any) -> float | None:
    number = _raw(value)
    return round(number, 6) if math.isfinite(number) else None


def _ratio(value: Any, *, percent_if_above: float | None = None) -> float | None:
    """Anteil als Bruch; ``percent_if_above``: größere Werte sind als Prozent geliefert (÷ 100)."""
    number = _raw(value)
    if not math.isfinite(number):
        return None
    if percent_if_above is not None and abs(number) > percent_if_above:
        number /= 100.0
    return round(number, 6)


def _day_of(epoch: Any) -> int | None:
    try:
        value = int(_raw(epoch))
        return date_to_day(dt.datetime.fromtimestamp(value, tz=UTC).date())
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def _count_row(row: dict) -> dict:
    keys = (("stark_kaufen", "strongBuy"), ("kaufen", "buy"), ("halten", "hold"), ("verkaufen", "sell"), ("stark_verkaufen", "strongSell"))
    out = {"monat": row.get("period")}
    out.update({name: _count(row.get(key)) for name, key in keys})
    return out


def buy_share(row: dict | None) -> float | None:
    """Anteil „Kaufen“ (stark kaufen + kaufen) an allen Empfehlungen eines Monats."""
    if not row:
        return None
    total = sum(int(row.get(k) or 0) for k in ("stark_kaufen", "kaufen", "halten", "verkaufen", "stark_verkaufen"))
    if total <= 0:
        return None
    return round((int(row.get("stark_kaufen") or 0) + int(row.get("kaufen") or 0)) / total, 4)


ACTION_NAMES = {"up": "hochgestuft", "down": "herabgestuft", "main": "bestätigt", "reit": "bestätigt", "init": "neu aufgenommen"}
TARGET_ACTIONS = {"Raises": "angehoben", "Lowers": "gesenkt", "Maintains": "beibehalten", "Announces": "neu", "Sets": "neu", "Initiates": "neu"}


def parse_facts(payload: dict, symbol: str, *, now: dt.datetime | None = None) -> dict:
    """Kennzahlen einer Aktie aus einer quoteSummary-Antwort mit ``FACT_MODULES`` (reine Funktion, testbar).

    Rückgabe ist ein kompaktes, JSON-fähiges dict; fehlende Angaben sind ``None``. Beträge stehen in der
    Kurseinheit der Notierung (Kursziele) bzw. in der Bilanzwährung (``waehrung_bilanz``); Anteile als Bruch."""
    view = parse_quote_summary(payload, symbol)  # wirft bei unbekanntem Symbol oder Fehler
    result = ((payload.get("quoteSummary") or {}).get("result") or [{}])[0] or {}
    fin = result.get("financialData") or {}
    stats = result.get("defaultKeyStatistics") or {}
    detail = result.get("summaryDetail") or {}
    profile = result.get("assetProfile") or {}
    calendar = result.get("calendarEvents") or {}
    now = now or dt.datetime.now(tz=UTC)

    trend_rows = [row for row in (result.get("recommendationTrend") or {}).get("trend") or [] if isinstance(row, dict)]
    order = {"0m": 0, "-1m": 1, "-2m": 2, "-3m": 3}
    trend = [_count_row(row) for row in sorted(trend_rows, key=lambda r: order.get(r.get("period"), 9)) if row.get("period") in order]

    actions = []
    cutoff = now.timestamp() - ACTION_DAYS * 86400
    for item in (result.get("upgradeDowngradeHistory") or {}).get("history") or []:
        when = _raw(item.get("epochGradeDate"))
        if not math.isfinite(when) or when < cutoff:
            continue
        actions.append(
            {
                "tag": _day_of(when),
                "haus": (item.get("firm") or "").strip() or None,
                "aktion": ACTION_NAMES.get(item.get("action"), item.get("action")),
                "von": item.get("fromGrade") or None,
                "zu": item.get("toGrade") or None,
                "ziel": _opt(item.get("currentPriceTarget")) if (_opt(item.get("currentPriceTarget")) or 0) > 0 else None,
                "ziel_vorher": _opt(item.get("priorPriceTarget")) if (_opt(item.get("priorPriceTarget")) or 0) > 0 else None,
                "ziel_aktion": TARGET_ACTIONS.get(item.get("priceTargetAction"), item.get("priceTargetAction")),
            }
        )
    actions.sort(key=lambda a: a["tag"] or 0, reverse=True)

    estimates = {row.get("period"): row for row in (result.get("earningsTrend") or {}).get("trend") or [] if isinstance(row, dict)}
    next_year = estimates.get("+1y") or {}
    this_year = estimates.get("0y") or {}
    earnings_days = []
    for value in ((calendar.get("earnings") or {}).get("earningsDate") or []):
        day = _day_of(value)
        if day is not None:
            earnings_days.append(day)
    today = date_to_day(now.date())
    upcoming = [d for d in earnings_days if d >= today]
    fcf = _opt(fin.get("freeCashflow"))
    forward_pe = _opt(stats.get("forwardPE"))
    if forward_pe is None:
        forward_pe = _opt(detail.get("forwardPE"))
    current = trend[0] if trend and trend[0]["monat"] == "0m" else None
    return {
        "symbol": symbol,
        "analysten": {
            "anzahl": view.analysts,
            "ziel_mittel": _opt(view.target_mean),
            "ziel_median": _opt(view.target_median),
            "ziel_hoch": _opt(view.target_high),
            "ziel_tief": _opt(view.target_low),
            "kurs": _opt(view.current_price),
            "empfehlung_mittel": _opt(view.rec_mean),
            "empfehlung": view.rec_key,
            "kaufen_anteil": buy_share(current),
            "empfehlungen_anzahl": sum(int(current.get(k) or 0) for k in ("stark_kaufen", "kaufen", "halten", "verkaufen", "stark_verkaufen")) if current else 0,
        },
        "empfehlungen": trend,
        "urteile": actions[:MAX_ACTIONS],
        "urteile_anzahl": len(actions),
        "bewertung": {
            "kgv": _opt(detail.get("trailingPE")),
            "kgv_erwartet": forward_pe,
            "peg": _opt(stats.get("pegRatio")),
            "kbv": _opt(stats.get("priceToBook")),
            "ev_ebitda": _opt(stats.get("enterpriseToEbitda")),
            "dividende": _ratio(detail.get("dividendYield"), percent_if_above=1.0),
            "boersenwert": _opt(detail.get("marketCap")),
        },
        "wachstum": {
            "gewinn_naechstes_jahr": _ratio(next_year.get("growth")),
            "gewinn_dieses_jahr": _ratio(this_year.get("growth")),
            "umsatz_naechstes_jahr": _ratio((next_year.get("revenueEstimate") or {}).get("growth")),
            "umsatz_quartal": _ratio(fin.get("revenueGrowth")),
            "gewinn_quartal": _ratio(fin.get("earningsGrowth")),
            "schaetzungen": _count((next_year.get("earningsEstimate") or {}).get("numberOfAnalysts")),
        },
        "finanzen": {
            "bruttomarge": _ratio(fin.get("grossMargins")),
            "operative_marge": _ratio(fin.get("operatingMargins")),
            "nettomarge": _ratio(fin.get("profitMargins")),
            "eigenkapitalrendite": _ratio(fin.get("returnOnEquity")),
            # Yahoo liefert das Verhältnis Schulden/Eigenkapital in Prozent (150 = 1,5-fach)
            "verschuldung": round(_raw(fin.get("debtToEquity")) / 100.0, 4) if math.isfinite(_raw(fin.get("debtToEquity"))) else None,
            "liquiditaet": _opt(fin.get("currentRatio")),
            "free_cashflow_positiv": None if fcf is None else fcf > 0,
        },
        "risiko": {
            "beta": _opt(stats.get("beta")) if _opt(stats.get("beta")) is not None else _opt(detail.get("beta")),
            "leerverkauf": _ratio(stats.get("shortPercentOfFloat")),
            "institutionen": _ratio(stats.get("heldPercentInstitutions")),
            "insider": _ratio(stats.get("heldPercentInsiders")),
            "veraenderung_52w": _ratio(stats.get("52WeekChange")),
            "hoch_52w": _opt(detail.get("fiftyTwoWeekHigh")),
            "tief_52w": _opt(detail.get("fiftyTwoWeekLow")),
        },
        "termine": {"zahlen": min(upcoming) if upcoming else None},
        "branche": {"sektor": profile.get("sector") or None, "industrie": profile.get("industry") or None},
        "waehrung_bilanz": fin.get("financialCurrency") or None,
    }


VALUATION_LABELS = {"undervalued": "unterbewertet", "overvalued": "ueberbewertet", "near fair value": "fair"}


def _percent_text(text: Any) -> float | None:
    if text is None:
        return None
    try:
        return round(float(str(text).replace("%", "").replace(",", ".").strip()) / 100.0, 4)
    except ValueError:
        return None


def parse_insights(payload: dict) -> dict | None:
    """Bewertung (unter-/überbewertet, Trading Central), technischer Ausblick und Research-Einstufung
    aus der Yahoo-„insights“-Antwort. ``None``, wenn nichts davon geliefert wird (außerhalb der USA üblich)."""
    result = ((payload or {}).get("finance") or {}).get("result") or {}
    info = result.get("instrumentInfo") or {}
    valuation = info.get("valuation") or {}
    tech = info.get("technicalEvents") or {}
    research = result.get("recommendation") or {}
    label = VALUATION_LABELS.get(str(valuation.get("description") or "").strip().lower())
    outlook = {}
    for key, name in (("shortTermOutlook", "kurz"), ("intermediateTermOutlook", "mittel"), ("longTermOutlook", "lang")):
        direction = str((tech.get(key) or {}).get("direction") or "").strip().lower()
        if direction in ("bullish", "bearish", "neutral"):
            outlook[name] = {"bullish": "steigend", "bearish": "fallend", "neutral": "seitwärts"}[direction]
    rating = str(research.get("rating") or "").strip().upper() or None
    target = _opt(research.get("targetPrice"))
    if label is None and not outlook and rating is None:
        return None
    return {
        "bewertung": label,
        "abschlag": _percent_text(valuation.get("discount")),  # > 0: Kurs unter dem fairen Wert
        "bewertung_quelle": valuation.get("provider") if label else None,
        "ausblick": outlook,
        "ausblick_quelle": "Trading Central" if outlook else None,
        "research": {"quelle": research.get("provider"), "einstufung": rating, "ziel": target if (target or 0) > 0 else None} if rating else None,
    }


# Einfache Wortlisten für die Tendenz von Schlagzeilen (Englisch und Deutsch). Bewusst schlicht und
# offengelegt: Sie erkennt Hochstufungen, Rekorde, Gewinnwarnungen usw., aber keinen Zusammenhang.
POSITIVE_WORDS = frozenset(
    """beat beats beating surge surges surged soar soars soared jump jumps jumped rally rallies rallied upgrade upgrades upgraded
    raise raises raised record strong stronger growth grows wins win won approval approved approves outperform outperforms buy bullish
    gain gains rises rise rising higher tops exceeds exceeded boost boosts boosted expands expansion partnership breakthrough profit profits
    upbeat optimistic climbs climb climbed rebound rebounds best positive accelerates dividend hike hikes
    steigt steigen gestiegen anstieg rekord hochgestuft kaufempfehlung angehoben übertrifft gewinn gewinne wachstum erfolgreich zulassung
    durchbruch stark starke stärker auftrag aufträge plus erholung höher""".split()
)
NEGATIVE_WORDS = frozenset(
    """miss misses missed plunge plunges plunged drop drops dropped fall falls fell slump slumps downgrade downgrades downgraded cut cuts
    lowers lowered lawsuit lawsuits probe investigation recall recalls weak weaker loss losses warning warns warned decline declines declined
    bearish sell underperform layoffs layoff bankruptcy fraud delay delays delayed halt halts fine fined lower slides slid tumble tumbles
    tumbled sinks sank crash crashes negative concern concerns risk risks disappoint disappoints disappointing short sued suit
    fällt fallen gefallen verlust verluste herabgestuft gesenkt warnung gewinnwarnung schwach schwäche klage einbruch minus rückgang
    insolvenz kürzt streicht tiefer""".split()
)


def headline_tone(title: str) -> int:
    """+1 positiv, −1 negativ, 0 neutral oder gemischt (Wortlisten, siehe oben)."""
    import re as _re

    words = _re.findall(r"[a-zäöüß]+", (title or "").lower())
    pos = sum(1 for w in words if w in POSITIVE_WORDS)
    neg = sum(1 for w in words if w in NEGATIVE_WORDS)
    return 1 if pos > neg else -1 if neg > pos else 0


def parse_news(payload: dict, symbol: str, *, limit: int = 8) -> list[dict]:
    """Meldungen zu einer Aktie aus der Yahoo-Suche: Titel, Quelle, Zeit, Link, Bezug und Tendenz."""
    items = []
    for item in (payload or {}).get("news") or []:
        title = (item.get("title") or "").strip()
        when = item.get("providerPublishTime")
        link = item.get("link") or ""
        if not title or when is None or not str(link).startswith("https://"):
            continue
        items.append(
            {
                "titel": title[:200],
                "quelle": (item.get("publisher") or "").strip()[:60] or None,
                "zeit": int(when),
                "link": str(link)[:500],
                "bezug": symbol in (item.get("relatedTickers") or []),
                "tendenz": headline_tone(title),
            }
        )
    items.sort(key=lambda n: n["zeit"], reverse=True)
    return items[:limit]


def _plausible_crumb(text: str) -> bool:
    return 5 <= len(text) <= 64 and not any(ch.isspace() for ch in text) and not any(ch in text for ch in "<>{}\"'")


class YahooProvider:
    name = NAME

    def __init__(
        self, http: HttpClient | None = None, *, requests_per_second: float = 2.5, quote_batches: bool = True, quote_workers: int | None = None
    ) -> None:
        own = http is None
        self.http = http or HttpClient(
            min_interval={"query2.finance.yahoo.com": 1.0 / requests_per_second, "query1.finance.yahoo.com": 1.0 / requests_per_second},
            impersonate="chrome",
        )
        self._crumb: str | None = None  # nur im Speicher; nie speichern oder protokollieren
        # Zwischenstand: zuerst die Kursabfrage „quote“ mit vielen Werten je Abruf (ab 1.10), dann „spark“
        self.quote_batches = quote_batches
        # Parallele Sammelabfragen (ab 1.12): im Betrieb QUOTE_WORKERS, mit übergebenem Client (Tests) einzeln
        self.quote_workers = max(1, quote_workers if quote_workers is not None else (QUOTE_WORKERS if own else 1))

    def _helper(self) -> "YahooProvider":
        """Zweiter Abrufer für parallele Sammelabfragen: eigene Sitzung (Cookies kopiert), gemeinsamer Mindestabstand."""
        burst = {host: min(interval, BURST_INTERVAL_S) for host, interval in self.http.min_interval.items()}
        helper = YahooProvider(http=self.http.clone(min_interval=burst), quote_batches=self.quote_batches, quote_workers=1)
        helper._crumb = self._crumb
        return helper

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

    def _summary(self, symbol: str, modules: str) -> dict:
        """Rohe quoteSummary-Antwort (bei abgelaufenem Crumb einmal erneuert)."""
        url = f"{BASE}/v10/finance/quoteSummary/{quote(symbol, safe='')}"
        response = None
        for attempt in range(2):
            crumb = self.ensure_crumb(refresh=attempt > 0)
            params = {"modules": modules, "crumb": crumb, "formatted": "false", "lang": "en-US", "region": "US"}
            response = self.http.get(url, params=params)
            if response.status_code != 401:
                break
        assert response is not None
        if response.status_code == 404:
            raise NoDataError(f"{symbol}: kein Eintrag (404)")
        if response.status_code != 200:
            raise ProviderError(f"{symbol}: HTTP {response.status_code}")
        try:
            return response.json()
        except ValueError as exc:
            raise ProviderError(f"{symbol}: Antwort ist kein JSON") from exc

    def fetch_facts(self, symbol: str) -> dict:
        """Alle Kennzahlen einer Aktie in einem Abruf (siehe ``parse_facts``)."""
        return parse_facts(self._summary(symbol, FACT_MODULES), symbol)

    def fetch_insights(self, symbol: str) -> dict | None:
        """Bewertung und Ausblick (Trading Central über Yahoo; meist nur US-Aktien)."""
        crumb = self.ensure_crumb()
        response = self.http.get(f"{BASE}/ws/insights/v2/finance/insights", params={"symbol": symbol, "crumb": crumb})
        if response.status_code == 404:
            return None
        if response.status_code != 200:
            raise ProviderError(f"{symbol}: HTTP {response.status_code}")
        try:
            return parse_insights(response.json())
        except ValueError as exc:
            raise ProviderError(f"{symbol}: Antwort ist kein JSON") from exc

    def fetch_news(self, symbol: str, *, count: int = 12) -> list[dict]:
        """Aktuelle Meldungen zu einer Aktie (Yahoo-Suche)."""
        response = self.http.get(f"{BASE}/v1/finance/search", params={"q": symbol, "quotesCount": "0", "newsCount": str(count), "enableFuzzyQuery": "false"})
        if response.status_code != 200:
            raise ProviderError(f"Nachrichten {symbol}: HTTP {response.status_code}")
        try:
            return parse_news(response.json(), symbol)
        except ValueError as exc:
            raise ProviderError(f"Nachrichten {symbol}: Antwort ist kein JSON") from exc

    def analyst_view(self, symbol: str) -> AnalystView:
        """Nur Kursziele und Empfehlungen einer Notierung (ein Abruf)."""
        return parse_quote_summary(self._summary(symbol, ANALYST_MODULES), symbol)

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

    def _quote_one(self, batch: list[str], endpoints: list[str]) -> tuple[dict[str, LiveQuote] | None, int, bool, str | None]:
        """Ein Abruf „quote“ für bis zu ``QUOTE_BATCH`` Werte: (Kurse oder None, Abrufe, gedrosselt, Endpunkt).
        Bei abgelaufenem Crumb (401) wird er einmal erneuert; die Endpunkte werden der Reihe nach versucht."""
        requests = 0
        for endpoint in endpoints:
            response = None
            for attempt in range(2):
                try:
                    crumb = self.ensure_crumb(refresh=attempt > 0)
                except (ProviderError, ConnectionError):
                    return None, requests, False, None
                params = {"symbols": ",".join(batch), "crumb": crumb, "formatted": "false", "lang": "en-US", "region": "US", "fields": QUOTE_FIELDS}
                try:
                    response = self.http.get(endpoint, params=params)
                except ProviderThrottled:
                    return None, requests + 1, True, None
                except (ProviderError, ConnectionError):
                    requests += 1
                    response = None
                    break
                requests += 1
                if response.status_code == 401 and attempt == 0:  # Crumb abgelaufen: einmal erneuern
                    continue
                break
            if response is None or response.status_code != 200:
                continue
            try:
                got, _ = parse_quote_response(response.json())
            except (ValueError, ProviderError):
                continue
            return got, requests, False, endpoint
        return None, requests, False, None

    def _spark_one(self, batch: list[str], endpoints: list[str]) -> tuple[dict | None, int, bool, str | None, Exception | None]:
        """Ein Spark-Abruf für bis zu ``SPARK_BATCH`` Werte: (Antwort oder None, Abrufe, gedrosselt, Endpunkt, letzter Fehler)."""
        requests = 0
        last_error: Exception | None = None
        for endpoint in endpoints:
            try:
                payload = self.spark(batch, endpoint)
                return payload, requests + 1, False, endpoint, None
            except ProviderThrottled:
                return None, requests + 1, True, None, None
            except (ProviderError, ConnectionError, ValueError) as exc:
                requests += 1
                last_error = exc
        return None, requests, False, None, last_error

    def _run_parallel(self, jobs: list, work, started: float, budget_s: float):
        """Führt ``work(provider, job)`` für alle Aufträge aus – mit ``quote_workers`` Abrufern gleichzeitig (eigene
        Sitzungen, gemeinsamer Mindestabstand) und in der Reihenfolge der Aufträge als Ergebnis.

        Ergebnis je Auftrag: Rückgabe von ``work`` oder ``None``, wenn das Zeitbudget erreicht war oder ein anderer
        Auftrag eine Drosselung gemeldet hat (``work`` liefert dafür ein Tupel mit ``True`` an dritter Stelle)."""
        import threading
        import time
        from concurrent.futures import ThreadPoolExecutor

        if not jobs:
            return []
        stop = threading.Event()
        workers = min(self.quote_workers, len(jobs))
        # Mehrere Abrufer: lauter Klone mit dem kurzen Abstand (gemeinsamer Zeitplan); einzeln: dieser Abrufer
        helpers = [self._helper() for _ in range(workers)] if workers > 1 else [self]
        free = list(helpers)
        lock = threading.Lock()

        def run(job):
            if stop.is_set() or time.monotonic() - started > budget_s:
                return None
            with lock:
                provider = free.pop()
            try:
                out = work(provider, job)
            finally:
                with lock:
                    free.append(provider)
            if out is not None and len(out) > 2 and out[2]:  # gedrosselt
                stop.set()
            return out

        if workers == 1:
            return [run(job) for job in jobs]
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="kurse") as pool:
            return list(pool.map(run, jobs))

    def _quote_pass(self, symbols: list[str], result: QuoteBatchResult, started: float, budget_s: float, progress=None) -> list[str] | None:
        """Erster Weg (ab 1.10): Kursabfrage „quote“ mit Crumb, bis zu ``QUOTE_BATCH`` Werte je Abruf; ab 1.12 parallel.

        Rückgabe: Werte, die danach noch über „spark“ geholt werden (fehlende oder ungültige; alle, wenn der
        Weg gar nicht funktioniert) – oder ``None``, wenn Yahoo drosselt (dann ist der Abruf beendet)."""
        try:
            self.ensure_crumb()
        except (ProviderError, ConnectionError) as exc:
            LOG.info("Kursabfrage „quote“ nicht möglich (%s) – weiter mit „spark“", type(exc).__name__)
            return list(symbols)
        batches = [symbols[k : k + QUOTE_BATCH] for k in range(0, len(symbols), QUOTE_BATCH)]
        endpoints = list(QUOTE_ENDPOINTS)
        # Der erste Abruf allein: findet den funktionierenden Endpunkt (und ob der Weg überhaupt geht)
        got, used, throttled, endpoint = self._quote_one(batches[0], endpoints)
        result.requests += used
        result.quote_requests += used
        if throttled:
            result.throttled = True
            for symbol in symbols:
                result.missing.setdefault(symbol, "Kursanbieter drosselt")
            return None
        if got is None:
            LOG.info("Kursabfrage „quote“ liefert nichts – weiter mit „spark“")
            return list(symbols)
        result.endpoint = endpoint
        endpoints = [endpoint] + [e for e in endpoints if e != endpoint]
        result.quotes.update(got)
        result.quote_found += len(got)
        leftover = [symbol for symbol in batches[0] if symbol not in got]
        done = len(batches[0])
        if progress is not None:
            progress(done, len(symbols))
        outcomes = self._run_parallel(batches[1:], lambda provider, batch: provider._quote_one(batch, endpoints), started, budget_s)
        stopped = False
        for batch, outcome in zip(batches[1:], outcomes):
            if outcome is None:
                if result.throttled:
                    for symbol in batch:
                        result.missing.setdefault(symbol, "Kursanbieter drosselt")
                else:
                    leftover.extend(batch)  # Zeitbudget: später über „spark“ (dort ebenfalls begrenzt)
                continue
            found, used, throttled, _ = outcome
            result.requests += used
            result.quote_requests += used
            if throttled:
                result.throttled = True
                stopped = True
                for symbol in batch:
                    result.missing.setdefault(symbol, "Kursanbieter drosselt")
                continue
            if found is None:
                leftover.extend(batch)
                continue
            result.quotes.update(found)
            result.quote_found += len(found)
            leftover.extend(symbol for symbol in batch if symbol not in found)
            done += len(batch)
            if progress is not None:
                progress(done, len(symbols))
        if stopped:
            for symbol in leftover:
                result.missing.setdefault(symbol, "Kursanbieter drosselt")
            return None
        return leftover

    def fetch_quotes(self, symbols: list[str], *, budget_s: float = 900.0, progress=None) -> QuoteBatchResult:
        """Aktuelle Kurse vieler Notierungen.

        Ab 1.10 zuerst über die Kursabfrage „quote“ (bis zu ``QUOTE_BATCH`` Werte je Abruf); was sie nicht
        liefert, über „spark“ in Abrufen zu je 20 Werten. Die erste funktionierende Variante aus
        ``SPARK_ENDPOINTS`` wird beibehalten. Ab 1.12 laufen die Abrufe parallel (``quote_workers``). Drosselt
        Yahoo dauerhaft, endet der Abruf mit ``throttled``; bereits geladene Kurse bleiben erhalten."""
        import time

        result = QuoteBatchResult()
        unique = list(dict.fromkeys(s for s in symbols if s))
        started = time.monotonic()
        if self.quote_batches and unique:
            rest = self._quote_pass(unique, result, started, budget_s, progress)
            if rest is None:
                return result
            unique = rest
        if not unique:
            return result
        batches = [unique[k : k + SPARK_BATCH] for k in range(0, len(unique), SPARK_BATCH)]
        endpoints = list(SPARK_ENDPOINTS)
        # Erster Abruf allein: funktionierende Variante finden; danach parallel
        first = self._spark_one(batches[0], endpoints)
        outcomes = [first]
        if first[2]:  # gedrosselt
            outcomes += [None] * (len(batches) - 1)
        else:
            if first[3] is not None:
                endpoints = [first[3]] + [e for e in endpoints if e != first[3]]
                if len(batches) > 1:
                    outcomes += self._run_parallel(batches[1:], lambda provider, batch: provider._spark_one(batch, endpoints), started, budget_s)
            else:
                # Erste Variante ging nicht: wie bisher nacheinander, nach drei Fehlschlägen ohne Kurs abbrechen
                failed_in_row = 1
                for batch in batches[1:]:
                    if failed_in_row >= 3 and not result.quotes:
                        outcomes.append(("abbruch",))
                        continue
                    if time.monotonic() - started > budget_s:
                        outcomes.append(None)
                        continue
                    outcome = self._spark_one(batch, endpoints)
                    outcomes.append(outcome)
                    if outcome[2]:
                        outcomes += [None] * (len(batches) - len(outcomes))
                        break
                    if outcome[0] is None:
                        failed_in_row += 1
                    else:
                        failed_in_row = 0
                        if outcome[3] is not None and outcome[3] != endpoints[0]:
                            endpoints = [outcome[3]] + [e for e in endpoints if e != outcome[3]]
        done = 0
        for batch, outcome in zip(batches, outcomes):
            if outcome is None:
                reason = "Kursanbieter drosselt" if result.throttled else "Zeitbudget erreicht"
                for symbol in batch:
                    result.missing.setdefault(symbol, reason)
                continue
            if outcome[0] == "abbruch":
                for symbol in batch:
                    result.missing.setdefault(symbol, "Sammelabfrage nicht verfügbar")
                continue
            payload, used, throttled, endpoint, last_error = outcome
            result.requests += used
            result.spark_requests += used
            if throttled:
                result.throttled = True
                for symbol in batch:
                    result.missing.setdefault(symbol, "Kursanbieter drosselt")
                continue
            if endpoint is not None:
                result.endpoint = endpoint  # zuletzt verwendete Variante (wie bis 1.11)
            if payload is None:
                for symbol in batch:
                    result.missing[symbol] = f"Abruf fehlgeschlagen ({last_error})"[:120]
                continue
            try:
                quotes, missing = parse_spark(payload)
            except ProviderError as exc:
                for symbol in batch:
                    result.missing[symbol] = str(exc)[:120]
                continue
            result.quotes.update(quotes)
            result.spark_found += len(quotes)
            for symbol in batch:
                if symbol not in quotes:
                    result.missing[symbol] = missing.get(symbol, "nicht in der Antwort")
            done += len(batch)
            if progress is not None:
                progress(done, len(unique))
        if result.throttled:
            # nach einer Drosselung: alles noch Offene als gedrosselt melden
            for symbol in unique:
                if symbol not in result.quotes:
                    result.missing.setdefault(symbol, "Kursanbieter drosselt")
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
