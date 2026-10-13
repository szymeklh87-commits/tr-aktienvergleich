"""Euro-Referenzkurse der Europäischen Zentralbank (für die indikative USD-Umrechnung).

Quelle: ``eurofxref-hist-90d.xml`` – die täglichen Referenzkurse der letzten 90 Tage, öffentlich
und kostenlos, veröffentlicht an TARGET-Arbeitstagen gegen 16:00 Uhr MEZ. Jeder Eintrag lautet
„1 EUR = x Einheiten“. Kurse dienen nur der Information; die EZB weist darauf hin, dass sie keine
Transaktionskurse sind. Genau so werden sie hier verwendet: für den Umsatzfilter, nie für Renditen.
"""

from __future__ import annotations

import datetime as dt
import xml.etree.ElementTree as ET
from dataclasses import dataclass

from ..util.timeutil import date_to_day, iso_utc, utc_now
from .base import ProviderError
from .http import HttpClient

URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist-90d.xml"
SOURCE = "EZB-Referenzkurse (Euro foreign exchange reference rates)"


@dataclass(frozen=True)
class FxFetch:
    rows: list[tuple[int, str, float]]  # (Tag, Währung, Einheiten je EUR)
    source: str
    url: str | None
    fetched_at: str


def parse_ecb_xml(data: bytes) -> list[tuple[int, str, float]]:
    """Zeilen (Epochentag, Währung, Einheiten je EUR) aus der EZB-XML-Datei.

    Dokumenttyp- und Entitätsdeklarationen werden abgelehnt (die echte Datei enthält keine);
    so kann auch eine manipulierte Antwort keine Entitätsexpansion auslösen.
    """
    head = data[:4096].lower()
    if b"<!doctype" in head or b"<!entity" in data.lower():
        raise ProviderError("EZB-Kurse: unerwartete Dokumenttyp- oder Entitätsdeklaration")
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise ProviderError(f"EZB-Kurse: XML nicht lesbar ({exc})") from exc
    rows: list[tuple[int, str, float]] = []
    for node in root.iter():
        when = node.attrib.get("time")
        if not when:
            continue
        try:
            day = date_to_day(dt.date.fromisoformat(when))
        except ValueError as exc:
            raise ProviderError(f"EZB-Kurse: ungültiges Datum {when!r}") from exc
        for child in node:
            currency = child.attrib.get("currency")
            rate = child.attrib.get("rate")
            if not currency or rate is None:
                continue
            try:
                value = float(rate)
            except ValueError:
                continue
            if value > 0 and len(currency) == 3 and currency.isalpha() and currency.isupper():
                rows.append((day, currency, value))
    if not rows:
        raise ProviderError("EZB-Kurse: keine Kurse in der Antwort")
    if not any(currency == "USD" for _, currency, _ in rows):
        raise ProviderError("EZB-Kurse: kein USD-Kurs enthalten")
    return rows


class EcbFxSource:
    name = SOURCE

    def __init__(self, url: str = URL, http: HttpClient | None = None) -> None:
        self.url = url
        self.http = http or HttpClient(timeout=60, max_retries=3)

    def fetch(self) -> FxFetch:
        response = self.http.get(self.url, headers={"Accept": "application/xml"})
        if response.status_code != 200:
            raise ProviderError(f"EZB-Kurse: HTTP {response.status_code}")
        return FxFetch(rows=parse_ecb_xml(response.content), source=SOURCE, url=self.url, fetched_at=iso_utc(utc_now()))
