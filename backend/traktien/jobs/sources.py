"""Zusammenstellung der Datenquellen für Produktiv- und Demomodus."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Protocol

from ..providers import demo as demo_mod
from ..providers.base import CalendarProvider, ListingCandidate, PriceProvider, ProviderError, ProviderThrottled
from ..providers.ecb import EcbFxSource
from ..providers.exchanges import ExchangeTable
from ..providers.http import HttpClient
from ..providers.openfigi import OpenFigiClient, candidates_from_figi
from ..providers.tr_universe import DEFAULT_URL, UniverseParseResult, extract_lines, parse_lines, pdf_metadata, universe_id
from ..util.log import get_logger
from ..util.timeutil import iso_utc, utc_now

LOG = get_logger(__name__)


class UniverseSource(Protocol):
    data_mode: str

    def fetch(self) -> tuple[dict, UniverseParseResult]: ...


class IdentitySource(Protocol):
    def lookup(self, isins: list[str], budget_s: float) -> dict[str, list[ListingCandidate]]: ...


class FxSource(Protocol):
    name: str

    def fetch(self): ...  # → providers.ecb.FxFetch


class TrPdfUniverseSource:
    data_mode = "produktiv"

    def __init__(self, url: str = DEFAULT_URL, http: HttpClient | None = None) -> None:
        self.url = url
        self.http = http or HttpClient(timeout=60, max_retries=3)

    def fetch(self) -> tuple[dict, UniverseParseResult]:
        response = self.http.get(self.url, headers={"Accept": "application/pdf"})
        if response.status_code != 200:
            raise ProviderError(f"TR-Liste: HTTP {response.status_code}")
        content = response.content
        if not content.startswith(b"%PDF"):
            raise ProviderError("TR-Liste: Antwort ist kein PDF")
        uid, digest = universe_id(content)
        meta_pdf = pdf_metadata(content)
        headers = {k.lower(): v for k, v in response.headers.items()}
        meta = {
            "id": uid,
            "sha256": digest,
            "source_url": self.url,
            "retrieved_at": iso_utc(utc_now()),
            "http_last_modified": headers.get("last-modified"),
            "http_etag": headers.get("etag"),
            "pdf_creation_date": meta_pdf.get("creation_date"),
            "pdf_mod_date": meta_pdf.get("mod_date"),
            "data_mode": self.data_mode,
        }
        result = parse_lines(extract_lines(content))
        meta["parser_version"] = result.parser_version
        return meta, result


class DemoUniverseSource:
    data_mode = "demo"

    def fetch(self) -> tuple[dict, UniverseParseResult]:
        result = demo_mod.demo_universe_parse()
        payload = "\n".join(f"{e.isin};{e.name}" for e in result.entries).encode("utf-8")
        uid, digest = universe_id(payload)
        meta = {
            "id": "D" + uid[1:],
            "sha256": digest,
            "source_url": "demo://synthetische-testaktien",
            "retrieved_at": iso_utc(demo_mod.DEMO_NOW),
            "http_last_modified": None,
            "http_etag": None,
            "pdf_creation_date": None,
            "pdf_mod_date": None,
            "parser_version": result.parser_version,
            "data_mode": self.data_mode,
        }
        return meta, result


class ProductionIdentitySource:
    """OpenFIGI zuerst; für ISINs ohne unterstützte Notierung zusätzlich die Yahoo-Suche."""

    def __init__(self, table: ExchangeTable, *, figi: OpenFigiClient | None = None, yahoo=None, max_yahoo_searches: int = 1500) -> None:
        self.table = table
        self.figi = figi or OpenFigiClient()
        self.yahoo = yahoo
        self.max_yahoo_searches = max_yahoo_searches

    def lookup(self, isins: list[str], budget_s: float) -> dict[str, list[ListingCandidate]]:
        started = utc_now()
        out: dict[str, list[ListingCandidate]] = {}
        try:
            mapped = self.figi.map_isins(isins)
        except ProviderThrottled:
            LOG.warning("OpenFIGI drosselt – Identitätsprüfung wird im nächsten Lauf fortgesetzt")
            return out
        for isin in isins:
            out[isin] = candidates_from_figi(isin, mapped.get(isin, {}), self.table)
        if self.yahoo is not None:
            searches = 0
            for isin in isins:
                if out.get(isin):
                    continue
                if searches >= self.max_yahoo_searches or (utc_now() - started).total_seconds() > budget_s:
                    break
                try:
                    out[isin] = [c for c in self.yahoo.search(isin, self.table) if c.exchange_key]
                except ProviderThrottled:
                    break
                except ProviderError as exc:
                    LOG.info("Yahoo-Suche %s: %s", isin, exc)
                searches += 1
        return out


class EodhdIdentitySource:
    """Identität über die EODHD-Suche (nur mit kostenpflichtigem Schlüssel aktiv)."""

    def __init__(self, provider, table: ExchangeTable) -> None:
        self.provider = provider
        self.table = table

    def lookup(self, isins: list[str], budget_s: float) -> dict[str, list[ListingCandidate]]:
        started = utc_now()
        out: dict[str, list[ListingCandidate]] = {}
        for isin in isins:
            if (utc_now() - started).total_seconds() > budget_s:
                break
            try:
                out[isin] = [c for c in self.provider.search_isin(isin, self.table) if c.exchange_key]
            except ProviderThrottled:
                break
            except ProviderError as exc:
                LOG.info("EODHD-Suche %s: %s", isin, exc)
        return out


class DemoIdentitySource:
    def __init__(self) -> None:
        self._by_isin = {i.isin: i.candidates for i in demo_mod.build_demo_universe()}

    def lookup(self, isins: list[str], budget_s: float) -> dict[str, list[ListingCandidate]]:
        return {isin: list(self._by_isin.get(isin, [])) for isin in isins}


@dataclass
class Sources:
    data_mode: str
    universe: UniverseSource
    identity: IdentitySource
    prices: PriceProvider
    calendars: CalendarProvider
    price_provider_name: str
    now: dt.datetime
    review_decisions: list[dict]
    fx: FxSource | None = None  # Referenzkurse für den Umsatzfilter (indikativ in USD)
    venues: IdentitySource | None = None  # alle Notierungen je ISIN für den Abgleich mit einem zweiten Börsenplatz


def demo_sources() -> Sources:
    provider = demo_mod.DemoProvider()
    reviews = [
        {"isin": isin, "datum": day, "entscheidung": decision, "quelle": "DEMO-Prüfnotiz", "notiz": "synthetische Übernahme (DEMO)"}
        for isin, days in demo_mod.demo_review_decisions().items()
        for day, decision in days.items()
    ]
    return Sources(
        data_mode="demo",
        universe=DemoUniverseSource(),
        identity=DemoIdentitySource(),
        prices=provider,
        calendars=provider.calendars,
        price_provider_name="demo",
        now=demo_mod.DEMO_NOW,
        review_decisions=reviews,
        fx=demo_mod.DemoFxSource(),
        venues=demo_mod.DemoVenueSource(),
    )


def production_sources(table: ExchangeTable, review_decisions: list[dict], *, price_provider: str = "yahoo", universe_url: str | None = None) -> Sources:
    from ..providers.calendars import production_calendars

    if price_provider == "eodhd":
        from ..providers.eodhd import EodhdProvider

        prices = EodhdProvider()
        identity = EodhdIdentitySource(prices, table)
    else:
        from ..providers.yahoo import YahooProvider

        prices = YahooProvider()
        identity = ProductionIdentitySource(table, yahoo=prices)
    return Sources(
        data_mode="produktiv",
        universe=TrPdfUniverseSource(universe_url or DEFAULT_URL),
        identity=identity,
        prices=prices,
        calendars=production_calendars(),
        price_provider_name=prices.name,
        now=utc_now(),
        review_decisions=review_decisions,
        fx=EcbFxSource(),
        venues=identity,
    )
