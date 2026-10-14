"""Zusätzliche Quellen für das Potenzial-Ranking (ab 1.6), nur für US-Notierungen:

* **Nasdaq** – zweiter Kursziel-Konsens (tief/Ø/hoch) und Empfehlungsübersicht. Inoffizielle
  Schnittstelle der Website nasdaq.com, ohne Vertrag; nur private Auswertung.
* **Stocktwits** – Stimmung der Community: die letzten 30 Beiträge zu einem Kürzel, davon die von den
  Verfassern als „Bullish“ oder „Bearish“ markierten. Öffentliche Schnittstelle ohne Schlüssel,
  begrenzt auf etwa 200 Abrufe je Stunde – deshalb nur für die vorderen Kandidaten.

Beide liefern keine Kurse; veröffentlicht wird nur verschlüsselt (wie alle Daten der App).
"""

from __future__ import annotations

import datetime as dt
import math
from typing import Any

from .base import NoDataError, ProviderError
from .http import HttpClient

NASDAQ = "https://api.nasdaq.com/api/analyst"
STOCKTWITS = "https://api.stocktwits.com/api/2/streams/symbol"


def _money(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        number = float(value)
    else:
        text = str(value).replace("$", "").replace(",", "").strip()
        if not text or text.upper() in ("N/A", "NA", "--"):
            return None
        try:
            number = float(text)
        except ValueError:
            return None
    return number if math.isfinite(number) and number > 0 else None


def parse_nasdaq_targets(payload: dict) -> dict | None:
    """Kursziel-Konsens aus ``/analyst/<Kürzel>/targetprice`` (tief, Ø, hoch; Zahl der Empfehlungen, wenn gemeldet)."""
    data = (payload or {}).get("data") or {}
    overview = data.get("consensusOverview") or {}
    target = _money(overview.get("priceTarget"))
    if target is None:
        return None
    counts = {}
    for key, name in (("buy", "kaufen"), ("hold", "halten"), ("sell", "verkaufen")):
        value = overview.get(key)
        try:
            counts[name] = int(value) if value is not None else None
        except (TypeError, ValueError):
            counts[name] = None
    total = sum(v for v in counts.values() if v)
    return {
        "ziel": target,
        "tief": _money(overview.get("lowPriceTarget")),
        "hoch": _money(overview.get("highPriceTarget")),
        "anzahl": total or None,
        **counts,
    }


def parse_stocktwits(payload: dict) -> dict | None:
    """Stimmung der letzten Beiträge: Anzahl, davon bullish/bearish, Beiträge je Tag, Beobachter."""
    messages = (payload or {}).get("messages") or []
    if not messages:
        return None
    bull = bear = 0
    times = []
    for message in messages:
        basic = (((message.get("entities") or {}).get("sentiment")) or {}).get("basic")
        if basic == "Bullish":
            bull += 1
        elif basic == "Bearish":
            bear += 1
        created = message.get("created_at")
        if created:
            try:
                times.append(dt.datetime.fromisoformat(str(created).replace("Z", "+00:00")))
            except ValueError:
                pass
    per_day = None
    if len(times) >= 2:
        span = (max(times) - min(times)).total_seconds() / 86400.0
        per_day = round(len(times) / max(span, 1.0 / 24.0), 2)
    symbol = (payload or {}).get("symbol") or {}
    return {
        "beitraege": len(messages),
        "bullish": bull,
        "bearish": bear,
        "je_tag": per_day,
        "erster": min(times).strftime("%Y-%m-%dT%H:%MZ") if times else None,
        "letzter": max(times).strftime("%Y-%m-%dT%H:%MZ") if times else None,
        "beobachter": symbol.get("watchlist_count"),
    }


class ExtraSources:
    def __init__(self, http: HttpClient | None = None) -> None:
        self.http = http or HttpClient(
            impersonate="chrome", max_retries=2, timeout=20, min_interval={"api.nasdaq.com": 0.5, "api.stocktwits.com": 18.0}
        )

    def nasdaq_targets(self, symbol: str) -> dict | None:
        response = self.http.get(
            f"{NASDAQ}/{symbol}/targetprice",
            headers={"Accept": "application/json, text/plain, */*", "Origin": "https://www.nasdaq.com", "Referer": "https://www.nasdaq.com/"},
        )
        if response.status_code == 404:
            raise NoDataError(f"Nasdaq {symbol}: unbekannt")
        if response.status_code != 200:
            raise ProviderError(f"Nasdaq {symbol}: HTTP {response.status_code}")
        try:
            return parse_nasdaq_targets(response.json())
        except ValueError as exc:
            raise ProviderError(f"Nasdaq {symbol}: Antwort ist kein JSON") from exc

    def community(self, symbol: str) -> dict | None:
        response = self.http.get(f"{STOCKTWITS}/{symbol}.json")
        if response.status_code == 404:
            raise NoDataError(f"Stocktwits {symbol}: unbekannt")
        if response.status_code != 200:
            raise ProviderError(f"Stocktwits {symbol}: HTTP {response.status_code}")
        try:
            return parse_stocktwits(response.json())
        except ValueError as exc:
            raise ProviderError(f"Stocktwits {symbol}: Antwort ist kein JSON") from exc
