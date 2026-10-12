"""EODHD-Adapter (kostenpflichtig, mit API-Schlüssel) – vorbereitet, nicht live verifiziert.

Verwendete dokumentierte Endpunkte:
* ``/api/eod/{SYMBOL}.{EXCHANGE}`` – Tageskurse (``close`` unverändert,
  ``adjusted_close`` split- und dividendenbereinigt, ``volume``)
* ``/api/splits/{SYMBOL}.{EXCHANGE}`` – Splits als "neu/alt"
* ``/api/search/{ISIN}`` – Notierungen zu einer ISIN

Der Schlüssel liegt ausschließlich serverseitig in ``EODHD_API_KEY``. Ohne Schlüssel
ist dieser Adapter deaktiviert. Ein Wechsel des Anbieters innerhalb einer Reihe
erfordert eine neue Datenrevision; Reihen werden nicht unbemerkt gemischt.
"""

from __future__ import annotations

import datetime as dt
import math
import os

import numpy as np

from ..analytics.quality import SplitEvent
from ..util.timeutil import day_to_date, iso_to_day, utc_now
from .base import ListingCandidate, NoDataError, PriceHistory, ProviderError, SessionFinal
from .exchanges import ExchangeTable, unit_info
from .http import HttpClient

BASE = "https://eodhd.com/api"
NAME = "eodhd"


def parse_split(text: str) -> float:
    """"2.000000/1.000000" → 2.0 (neue Aktien je alte Aktie)."""
    new, old = (float(part) for part in str(text).split("/"))
    if new <= 0 or old <= 0:
        raise ValueError(text)
    return new / old


def parse_eod(rows: list[dict], splits: list[SplitEvent], symbol: str, session_final: SessionFinal | None) -> PriceHistory:
    data = []
    dropped = 0
    for row in rows:
        day = iso_to_day(row["date"])
        if session_final is not None and not session_final(day):
            dropped += 1
            continue
        close = float(row.get("close") or math.nan)
        if not (close > 0):
            continue
        volume = row.get("volume")
        data.append(
            (
                day,
                float(row.get("open") or math.nan),
                float(row.get("high") or math.nan),
                float(row.get("low") or math.nan),
                close,
                math.nan if volume is None else float(volume),
                float(row.get("adjusted_close") or math.nan),
            )
        )
    data.sort()
    days = np.array([r[0] for r in data], dtype=np.int64)
    raw = np.array([r[4] for r in data], dtype=np.float64)
    # Splitbereinigung: Kurse vor dem Ex-Datum durch das kumulierte Verhältnis teilen.
    factor_after = np.ones(len(days))
    for event in splits:
        factor_after[days < event.day] *= event.factor
    split_adjusted = raw / factor_after
    adj = lambda k: np.array([r[k] for r in data], dtype=np.float64) / factor_after  # noqa: E731
    volume = np.array([r[5] for r in data], dtype=np.float64) * factor_after
    return PriceHistory(
        provider=NAME,
        symbol=symbol,
        days=days,
        open=adj(1),
        high=adj(2),
        low=adj(3),
        close=split_adjusted,
        volume=volume,
        close_raw=raw,
        close_total=np.array([r[6] for r in data], dtype=np.float64),
        splits=splits,
        fetched_at=utc_now(),
        dropped_unfinished=dropped,
    )


class EodhdProvider:
    name = NAME

    def __init__(self, api_key: str | None = None, http: HttpClient | None = None) -> None:
        self.api_key = api_key or os.environ.get("EODHD_API_KEY")
        if not self.api_key:
            raise ProviderError("EODHD_API_KEY fehlt – kostenpflichtiger Adapter nicht aktiv")
        self.http = http or HttpClient(min_interval={"eodhd.com": 0.06})

    def _get(self, path: str, params: dict) -> object:
        query = dict(params, api_token=self.api_key, fmt="json")
        response = self.http.get(f"{BASE}/{path}", params=query)
        if response.status_code == 404:
            raise NoDataError(path)
        if response.status_code != 200:
            raise ProviderError(f"EODHD HTTP {response.status_code}")
        return response.json()

    def fetch_history(self, symbol: str, start_day: int, end_day: int, *, session_final: SessionFinal | None = None) -> PriceHistory:
        start = day_to_date(start_day).isoformat()
        end = (day_to_date(end_day) + dt.timedelta(days=1)).isoformat()
        rows = self._get(f"eod/{symbol}", {"from": start, "to": end, "period": "d"})
        split_rows = self._get(f"splits/{symbol}", {"from": "2000-01-01"})
        splits = [SplitEvent(iso_to_day(r["date"]), parse_split(r["split"])) for r in split_rows or []]
        history = parse_eod(rows or [], splits, symbol, session_final)
        if not len(history):
            raise NoDataError(f"{symbol}: keine Tageskurse")
        return history

    def search_isin(self, isin: str, table: ExchangeTable) -> list[ListingCandidate]:
        rows = self._get(f"search/{isin}", {}) or []
        by_eodhd = {ex.eodhd: ex for ex in table.exchanges.values() if ex.eodhd}
        out = []
        for row in rows:
            if (row.get("ISIN") or "").upper() != isin:
                continue
            exchange = by_eodhd.get(row.get("Exchange"))
            out.append(
                ListingCandidate(
                    source="eodhd",
                    exchange_key=exchange.key if exchange else None,
                    provider_symbol=f"{row.get('Code')}.{row.get('Exchange')}",
                    ticker=row.get("Code"),
                    exch_code=row.get("Exchange"),
                    name=row.get("Name"),
                    security_type=row.get("Type"),
                    currency=row.get("Currency"),
                )
            )
        return out


def unit_of(currency: str | None) -> tuple[str | None, float]:
    return unit_info(currency)
