"""Euro-Referenzkurse der Europäischen Zentralbank (für die indikative USD-Umrechnung).

Quelle: ``eurofxref-hist-90d.xml`` – die täglichen Referenzkurse der letzten 90 Tage, öffentlich
und kostenlos, veröffentlicht an TARGET-Arbeitstagen gegen 16:00 Uhr MEZ. Jeder Eintrag lautet
„1 EUR = x Einheiten“. Kurse dienen nur der Information; die EZB weist darauf hin, dass sie keine
Transaktionskurse sind. Genau so werden sie hier verwendet: für den Umsatzfilter und für die
Euro-Bewertung des gedachten Regeldepots der Umschichtungs-Regel, nie für die Renditen der Ranglisten.
"""

from __future__ import annotations

import csv
import datetime as dt
import io
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass

from ..util.timeutil import date_to_day, iso_utc, utc_now
from .base import ProviderError
from .http import HttpClient

URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist-90d.xml"
# Gesamte Reihe seit 1999 (ZIP mit einer CSV-Datei, gut 0,5 MB) – nur für die Rückschau der
# Umschichtungs-Regel, einmalig bzw. wenn ältere Kurse fehlen
HISTORY_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.zip"
MAX_HISTORY_BYTES = 30_000_000
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


def parse_ecb_history_zip(data: bytes, *, first_day: int | None = None) -> list[tuple[int, str, float]]:
    """Zeilen (Epochentag, Währung, Einheiten je EUR) aus ``eurofxref-hist.zip`` (ab ``first_day``).

    Die ZIP-Datei muss genau eine CSV-Datei enthalten; entpackt höchstens 30 MB (Schutz vor
    übergroßen oder manipulierten Antworten). Felder „N/A“ und leere Felder werden übersprungen.
    """
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise ProviderError("EZB-Kurshistorie: keine ZIP-Datei") from exc
    names = [info for info in archive.infolist() if not info.is_dir()]
    if len(names) != 1 or not names[0].filename.lower().endswith(".csv"):
        raise ProviderError("EZB-Kurshistorie: unerwarteter Inhalt der ZIP-Datei")
    if names[0].file_size > MAX_HISTORY_BYTES:
        raise ProviderError("EZB-Kurshistorie: Datei zu groß")
    with archive.open(names[0]) as handle:
        text = handle.read(MAX_HISTORY_BYTES + 1).decode("utf-8", errors="replace")
    if len(text) > MAX_HISTORY_BYTES:
        raise ProviderError("EZB-Kurshistorie: Datei zu groß")
    reader = csv.reader(io.StringIO(text))
    header = next(reader, None)
    if not header or header[0].strip().lower() != "date":
        raise ProviderError("EZB-Kurshistorie: Kopfzeile fehlt")
    currencies = [h.strip() for h in header[1:]]
    rows: list[tuple[int, str, float]] = []
    for record in reader:
        if not record or not record[0].strip():
            continue
        try:
            day = date_to_day(dt.date.fromisoformat(record[0].strip()))
        except ValueError:
            continue
        if first_day is not None and day < first_day:
            continue
        for currency, raw in zip(currencies, record[1:]):
            raw = raw.strip()
            if not currency or len(currency) != 3 or not currency.isalpha() or raw in ("", "N/A"):
                continue
            try:
                value = float(raw)
            except ValueError:
                continue
            if value > 0:
                rows.append((day, currency.upper(), value))
    if not any(currency == "USD" for _, currency, _ in rows):
        raise ProviderError("EZB-Kurshistorie: kein USD-Kurs enthalten")
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

    def fetch_history(self, first_day: int) -> FxFetch:
        """Referenzkurse ab ``first_day`` aus der vollständigen EZB-Reihe."""
        response = self.http.get(HISTORY_URL, headers={"Accept": "application/zip"})
        if response.status_code != 200:
            raise ProviderError(f"EZB-Kurshistorie: HTTP {response.status_code}")
        content = response.content
        if len(content) > MAX_HISTORY_BYTES:
            raise ProviderError("EZB-Kurshistorie: Antwort zu groß")
        rows = parse_ecb_history_zip(content, first_day=first_day)
        return FxFetch(rows=rows, source=SOURCE, url=HISTORY_URL, fetched_at=iso_utc(utc_now()))
