"""OpenFIGI v3 – Zuordnung ISIN → Börsennotierungen (FIGI, Ticker, Börsencode, Typ).

Dokumentierte Grenzen (openfigi.com/api/documentation): ohne API-Schlüssel 25 Anfragen
pro Minute und höchstens 10 Jobs je Anfrage; mit kostenlosem Schlüssel 25 Anfragen je
6 Sekunden und 100 Jobs. Der Schlüssel liegt nur serverseitig (``OPENFIGI_API_KEY``).
Eine zu große Anfrage (HTTP 413) wird mit kleineren Blöcken wiederholt.
"""

from __future__ import annotations

import os
from typing import Iterable

from ..util.log import get_logger
from .base import ListingCandidate, ProviderError
from .exchanges import ExchangeTable
from .http import HttpClient

LOG = get_logger(__name__)
URL = "https://api.openfigi.com/v3/mapping"


class OpenFigiClient:
    def __init__(self, http: HttpClient | None = None, api_key: str | None = None) -> None:
        self.api_key = api_key if api_key is not None else os.environ.get("OPENFIGI_API_KEY") or None
        if self.api_key:
            self.batch_size = 100
            interval = 6.0 / 25.0
        else:
            self.batch_size = 10
            interval = 60.0 / 25.0
        self.http = http or HttpClient(min_interval={"api.openfigi.com": interval * 1.05})

    def _post(self, jobs: list[dict]) -> list[dict]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["X-OPENFIGI-APIKEY"] = self.api_key
        response = self.http.post(URL, json_body=jobs, headers=headers)
        if response.status_code == 413:
            raise _TooLarge()
        if response.status_code == 401:
            raise ProviderError("OpenFIGI: API-Schlüssel ungültig")
        if response.status_code != 200:
            raise ProviderError(f"OpenFIGI: HTTP {response.status_code}")
        data = response.json()
        if not isinstance(data, list) or len(data) != len(jobs):
            raise ProviderError("OpenFIGI: Antwort passt nicht zur Anzahl der Jobs")
        return data

    def map_isins(self, isins: Iterable[str]) -> dict[str, dict]:
        """Ergebnis je ISIN: {"data": [...]} oder {"warning"/"error": "..."}."""
        pending = list(dict.fromkeys(isins))
        results: dict[str, dict] = {}
        size = self.batch_size
        position = 0
        while position < len(pending):
            batch = pending[position : position + size]
            jobs = [{"idType": "ID_ISIN", "idValue": isin} for isin in batch]
            try:
                answer = self._post(jobs)
            except _TooLarge:
                if size == 1:
                    raise ProviderError("OpenFIGI: selbst Einzelanfrage zu groß")
                size = max(1, size // 2)
                LOG.info("OpenFIGI 413 – Blockgröße auf %d reduziert", size)
                continue
            for isin, item in zip(batch, answer):
                results[isin] = item if isinstance(item, dict) else {"error": "unerwartetes Format"}
            position += len(batch)
        return results


class _TooLarge(Exception):
    pass


def candidates_from_figi(isin: str, item: dict, table: ExchangeTable) -> list[ListingCandidate]:
    """Wandelt OpenFIGI-Datensätze in Notierungskandidaten mit Yahoo-Symbol um."""
    out: list[ListingCandidate] = []
    seen: set[str] = set()
    for record in item.get("data") or []:
        if (record.get("marketSector") or "Equity") != "Equity":
            continue
        exchange = table.exchange_for_figi(record.get("exchCode"))
        ticker = record.get("ticker")
        if exchange is None or not ticker:
            continue
        symbol = table.yahoo_symbol(exchange, ticker)
        key = f"{exchange.key}|{symbol}"
        if key in seen:
            continue
        seen.add(key)
        out.append(
            ListingCandidate(
                source="openfigi",
                exchange_key=exchange.key,
                provider_symbol=symbol,
                ticker=ticker,
                exch_code=record.get("exchCode"),
                name=record.get("name"),
                security_type=record.get("securityType"),
                security_type2=record.get("securityType2"),
                figi=record.get("figi"),
                composite_figi=record.get("compositeFIGI"),
                share_class_figi=record.get("shareClassFIGI"),
            )
        )
    return out
