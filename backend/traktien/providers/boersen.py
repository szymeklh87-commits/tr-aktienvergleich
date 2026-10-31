"""Amtliche Kursquellen der Börsen und unabhängige Vergleichsquellen für den Kursabgleich (ab 1.20.0).

Die Hauptquelle der App (Yahoo) liefert Tageskerzen für alle rund 11 000 Notierungen. Ihr Schlusskurs ist nicht überall
der amtliche Schlusskurs der Heimatbörse: An Tagen ohne Umsatz nennt Yahoo bei der GPW einen anderen Wert als die Börse,
bei Nasdaq-Aktien teils den letzten Abschluss statt des offiziellen Schlusskurses (NOCP), bei TSX Venture teils einen anderen
Kurs als die Börse. Dieses Modul liest die frei zugänglichen Kursarchive der Börsenbetreiber selbst:

* **GPW** (Warschau, Hauptmarkt): Notierungsarchiv je Sitzung, alle Aktien mit ISIN, Eröffnungs-, Höchst-, Tiefst- und
  Schlusskurs, Volumen, Zahl der Abschlüsse – eine Anfrage je Tag für alle Aktien.
* **NewConnect** (Warschau, von der GPW betrieben): Tagesstatistik je Sitzung als Excel-Datei, ebenfalls mit ISIN.
* **TMX** (Toronto und TSX Venture; die TMX Group betreibt beide Börsen): Tageskerzen je Kürzel über die Schnittstelle von
  TMX Money.
* **Nasdaq** (Nasdaq-notierte Aktien): Historie des offiziellen Schlusskurses „Nasdaq Official Closing Price“ (NOCP).

Vergleichsquelle ohne amtlichen Rang: **CNBC** (Tageskerzen, Definition nicht veröffentlicht) – nur zur Gegenprobe, nie als
Ersatzkurs (siehe ``analytics/kursabgleich.py``).

Alle Werte bleiben unbereinigt, wie veröffentlicht; die Umrechnung auf die Split-Basis der App und die Auswahlregel stehen im
Rechenmodul. Netzfehler werden gezählt, nie geraten. Keine Schlüssel, keine Anmeldung.
"""

from __future__ import annotations

import datetime as dt
import io
import json
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Callable, Iterable

EPOCH = dt.date(1970, 1, 1)
ISIN_RE = re.compile(r"[A-Z]{2}[A-Z0-9]{9}\d")

GPW_URL = "https://www.gpw.pl/archiwum-notowan-full?type=10&instrument=&date={date}"
GPW_HEADERS = {"Accept": "text/html,application/xhtml+xml", "Accept-Language": "pl,en;q=0.8", "Referer": "https://www.gpw.pl/archiwum-notowan-full"}
NC_URL = "https://newconnect.pl/pub/NEWCONNECT/statystyki/statystyki_dzienne/NC_{ymd}.{ext}"
NC_HEADERS = {"Accept": "*/*", "Referer": "https://newconnect.pl/archiwum-notowan"}
CSE_URL = "https://market-reports-primary.thecse.com/CSEListed/Daily/Summary/CSEListed.Daily.Market.Summary.{date}.txt"
CSE_HEADERS = {"Accept": "text/plain, */*", "Referer": "https://thecse.com/"}
TMX_URL = "https://app-money.tmx.com/graphql"
TMX_HEADERS = {"Accept": "*/*", "Content-Type": "application/json", "locale": "en", "Origin": "https://money.tmx.com", "Referer": "https://money.tmx.com/"}
NOCP_URLS = (
    "https://api.nasdaq.com/api/company/{symbol}/historical-nocp?timeframe=y1",
    "https://api.nasdaq.com/api/company/{symbol}/historical-nocp?timeframe=m3",
)
NASDAQ_HEADERS = {"Accept": "application/json, text/plain, */*", "Origin": "https://www.nasdaq.com", "Referer": "https://www.nasdaq.com/"}
CNBC_QUOTE_URL = "https://quote.cnbc.com/quote-html-webservice/restQuote/symbolType/symbol?symbols={symbols}&requestMethod=itv&noform=1&partnerId=2&fund=1&exthrs=1&output=json&events=1"
CNBC_BARS_URL = "https://ts-api.cnbc.com/harmony/app/bars/{symbol}/1D/{start:%Y%m%d}000000/{end:%Y%m%d}000000/adjusted/EST5EDT.json"
CNBC_HEADERS = {"Accept": "application/json, text/plain, */*", "Origin": "https://www.cnbc.com", "Referer": "https://www.cnbc.com/"}

# Mindestabstand je Host (Sekunden) – höflich, deutlich unter den beobachteten Grenzen
MIN_INTERVAL = {
    "www.gpw.pl": 0.5,
    "newconnect.pl": 0.5,
    "market-reports-primary.thecse.com": 0.5,
    "app-money.tmx.com": 0.4,
    "api.nasdaq.com": 0.4,
    "quote.cnbc.com": 0.3,
    "ts-api.cnbc.com": 0.3,
}

TMX_QUOTE = (
    "query getQuoteBySymbol($symbol: String, $locale: String) {"
    " getQuoteBySymbol(symbol: $symbol, locale: $locale) { symbol name exchangeName exchangeCode } }"
)
TMX_SERIES_OHLC = (
    "query getTimeSeriesData($symbol: String!, $freq: String, $interval: Int, $start: String, $end: String, $startDateTime: Int,"
    " $endDateTime: Int) { getTimeSeriesData(symbol: $symbol, freq: $freq, interval: $interval, start: $start, end: $end,"
    " startDateTime: $startDateTime, endDateTime: $endDateTime) { dateTime open high low close volume } }"
)
TMX_SERIES = (
    "query getTimeSeriesData($symbol: String!, $freq: String, $interval: Int, $start: String, $end: String, $startDateTime: Int,"
    " $endDateTime: Int) { getTimeSeriesData(symbol: $symbol, freq: $freq, interval: $interval, start: $start, end: $end,"
    " startDateTime: $startDateTime, endDateTime: $endDateTime) { dateTime close volume } }"
)
TMX_HISTORY = (
    "query getCompanyPriceHistory($symbol: String!, $start: String, $end: String, $limit: Int, $adjusted: Boolean,"
    " $adjustmentType: String, $unadjusted: Boolean) { getCompanyPriceHistory(symbol: $symbol, start: $start, end: $end,"
    " limit: $limit, adjusted: $adjusted, adjustmentType: $adjustmentType, unadjusted: $unadjusted) {"
    " datetime openPrice highPrice lowPrice closePrice volume } }"
)
TMX_HISTORY_PAGES = 10


@dataclass(frozen=True)
class SourceInfo:
    """Beschreibung einer Quelle für Manifest, App und Dokumentation."""

    key: str
    name: str
    role: str  # „amtlich“ (Börse bzw. Börsenbetreiber selbst) oder „vergleich“ (Datenanbieter)
    operator: str
    definition: str  # Kursdefinition der Quelle, wie veröffentlicht
    url: str
    exchanges: tuple[str, ...]  # Börsenschlüssel der App, für die die Quelle gilt
    basis: str  # „unbereinigt“ (Kurse wie gehandelt) oder „bereinigt“ / „unbekannt“
    ohlc: bool  # Eröffnung, Hoch, Tief verfügbar
    volume: bool


SOURCES: dict[str, SourceInfo] = {
    "gpw": SourceInfo(
        "gpw", "GPW – Notierungsarchiv", "amtlich", "Giełda Papierów Wartościowych w Warszawie (GPW)",
        "„Kurs zamknięcia“ der Sitzung (Schlusskurs der Börse) in Notierungswährung, unbereinigt; je Aktie mit ISIN",
        "https://www.gpw.pl/archiwum-notowan-full", ("XWAR",), "unbereinigt", True, True,
    ),
    "newconnect": SourceInfo(
        "newconnect", "NewConnect – Tagesstatistik", "amtlich", "GPW (Betreiberin von NewConnect)",
        "„Kurs zamknięcia“ der Sitzung auf NewConnect in Notierungswährung, unbereinigt; je Aktie mit ISIN",
        "https://newconnect.pl/statystyki-dzienne", ("XWAR",), "unbereinigt", True, True,
    ),
    "cse": SourceInfo(
        "cse", "CSE – Daily Market Summary", "amtlich", "Canadian Securities Exchange (CSE)",
        "„Close“ der Sitzung (letzter Abschluss an der CSE) in Notierungswährung, unbereinigt; je Kürzel mit Namen, Umsatz in 100 Stück; "
        "Aktien ohne Abschluss stehen ohne Schlusskurs in der Liste der Geld-/Briefkurse",
        "https://thecse.com/market-activity/activity-summaries", ("XCNQ",), "unbereinigt", False, True,
    ),
    "tmx": SourceInfo(
        "tmx", "TMX Money – Tageskerzen", "amtlich", "TMX Group (Betreiberin der TSX und der TSX Venture Exchange)",
        "Schlusskurs der Sitzung an der Heimatbörse (TSX bzw. TSXV) in Notierungswährung; je Kürzel, Börse in der Kursmeldung",
        "https://money.tmx.com", ("XTSE", "XTSX"), "unbekannt", True, True,
    ),
    "nasdaq_nocp": SourceInfo(
        "nasdaq_nocp", "Nasdaq – Official Closing Price (NOCP)", "amtlich", "The Nasdaq Stock Market",
        "„Nasdaq Official Closing Price“ (Preis der Schlussauktion bzw. nach Regel 4754 bestimmter offizieller Schlusskurs), USD, unbereinigt",
        "https://www.nasdaq.com/market-activity/stocks", ("XNAS",), "unbereinigt", False, False,
    ),
    "cnbc": SourceInfo(
        "cnbc", "CNBC – Tageskerzen", "vergleich", "CNBC (Datenanbieter, nicht die Börse)",
        "Schlusskurs der Tageskerze (Definition nicht veröffentlicht); nur Gegenprobe, nie Ersatzkurs",
        "https://www.cnbc.com", (), "unbekannt", True, True,
    ),
}


@dataclass(frozen=True)
class OfficialBar:
    """Ein Kurstag einer Quelle, Werte wie veröffentlicht (unbereinigt, Notierungswährung)."""

    day: int
    close: float
    open: float | None = None
    high: float | None = None
    low: float | None = None
    volume: float | None = None  # Stück
    trades: float | None = None  # Zahl der Abschlüsse, falls angegeben
    decimals: int | None = None  # Nachkommastellen des Schlusskurses, wie veröffentlicht (für die Rundungsgrenze)


@dataclass
class OfficialSeries:
    """Kurse einer Aktie aus einer Quelle."""

    source: str
    status: str  # „ok“, „nicht_gefunden“, „keine_kurse“, „fehler_…“, „http_…“
    bars: dict[int, OfficialBar] = field(default_factory=dict)
    name: str | None = None
    exchange: str | None = None  # Börse laut Quelle
    currency: str | None = None
    symbol: str | None = None
    detail: str | None = None  # Abrufweg (z. B. „kursgrafik“), ohne Werte


def day_of(date: dt.date) -> int:
    return (date - EPOCH).days


def date_of(day: int) -> dt.date:
    return EPOCH + dt.timedelta(days=int(day))


def decimals_of_text(text: str) -> int | None:
    """Nachkommastellen einer Zahl in Textform („1 234,560“ → 3, „$0.4550“ → 4, „12“ → 0)."""
    s = (text or "").replace("\xa0", "").replace(" ", "").replace("$", "").strip()
    if not s:
        return None
    s = s.replace(",", ".")
    if s.count(".") > 1:  # Tausenderpunkte (z. B. „1.234.56“ kommt nicht vor; zur Sicherheit letzter Punkt)
        head, _, tail = s.rpartition(".")
        s = head.replace(".", "") + "." + tail
    if "." not in s:
        return 0 if re.fullmatch(r"-?\d+", s) else None
    tail = s.split(".", 1)[1]
    return len(tail) if re.fullmatch(r"\d+", tail) else None


def decimals_of_number(value: float, max_decimals: int = 6) -> int | None:
    """Kleinste Nachkommastellenzahl, mit der ``value`` (bis auf Darstellungsrauschen) genau dargestellt wird."""
    if value is None or not (value == value):  # NaN
        return None
    for d in range(max_decimals + 1):
        scaled = float(value) * (10**d)
        if abs(scaled - round(scaled)) <= 1e-6 * max(1.0, abs(scaled)):
            return d
    return None


def pl_number(text: str | None) -> float | None:
    """Zahl in polnischer Schreibweise („1 234,56“, auch mit geschütztem Leerzeichen); „-“ oder leer → None."""
    s = (text or "").replace("\xa0", "").replace(" ", "").replace(",", ".").strip()
    if not s or s in ("-", "–", "—"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def money_number(text) -> float | None:
    """„$1,234.5600“ → 1234.56; Zahlen bleiben Zahlen; leer, „N/A“ → None."""
    if isinstance(text, (int, float)):
        return float(text)
    s = str(text or "").replace("$", "").replace(",", "").replace("\xa0", "").strip()
    if not s or s.upper() in ("N/A", "NA", "-", "--"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


# --------------------------------------------------------------------------------------------- GPW und NewConnect

class _Tables(HTMLParser):
    """Alle Tabellen einer Seite als Zeilen von Zelltexten (Leerraum zusammengefasst)."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[list[list[str]]] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self.tables.append([])
        elif tag == "tr" and self.tables:
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []
        elif tag == "br" and self._cell is not None:
            self._cell.append(" ")

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._cell is not None and self._row is not None:
            self._row.append(" ".join("".join(self._cell).split()))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            if self._row and self.tables:
                self.tables[-1].append(self._row)
            self._row = None

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)


# Spaltenköpfe des Notierungsarchivs und der Tagesstatistik (polnisch und englisch), als reguläre Ausdrücke – „min“ allein
# träfe auch „Wartość nominalna“
_COLUMNS = {
    "isin": (r"\bisin\b", r"kod isin"),
    "name": (r"^nazwa", r"^name$", r"^instrument", r"^spółka", r"^emitent"),
    "currency": (r"walut", r"currency"),
    "open": (r"otwarc", r"\bopen"),
    "high": (r"kurs max", r"maksym", r"\bmax\b", r"\bhigh"),
    "low": (r"kurs min\b", r"kurs min$", r"minimal", r"^min\b", r"\blow"),
    "close": (r"zamkn", r"closing", r"\bclose"),
    "volume": (r"wolumen", r"volume"),
    "trades": (r"liczba transakcji", r"number of trades", r"transakcj"),
}


def _header_map(header: list[str]) -> dict[str, int]:
    cells = [" ".join(str(c or "").split()).lower() for c in header]
    found: dict[str, int] = {}
    for key, patterns in _COLUMNS.items():
        for k, cell in enumerate(cells):
            if k in found.values():
                continue
            if any(re.search(p, cell) for p in patterns):
                found[key] = k
                break
    return found


def parse_table(table: list[list], day: int) -> tuple[str, dict[str, OfficialBar], dict]:
    """Zeilen einer Tabelle (Notierungsarchiv der GPW oder Tagesstatistik der NewConnect): Kopfzeile mit „ISIN“ suchen, dann
    je ISIN ein ``OfficialBar`` (Status, Kurse je ISIN, Angaben je ISIN: Name, Währung)."""
    head_at = next((k for k, row in enumerate(table) if any("isin" in str(c or "").lower() for c in row)), None)
    if head_at is None:
        return "ohne_isin_spalte", {}, {}
    cols = _header_map(table[head_at])
    if "isin" not in cols or "close" not in cols:
        return "spalten_fehlen", {}, {}
    bars: dict[str, OfficialBar] = {}
    info: dict[str, dict] = {}

    def cell(row, key):
        k = cols.get(key)
        return row[k] if k is not None and k < len(row) else None

    def number(value):
        if isinstance(value, (int, float)):
            return float(value)
        return pl_number(None if value is None else str(value))

    for row in table[head_at + 1:]:
        isin = str(cell(row, "isin") or "").strip().upper()
        if not ISIN_RE.fullmatch(isin):
            continue
        raw_close = cell(row, "close")
        close = number(raw_close)
        if close is None or close <= 0:
            continue
        decimals = decimals_of_number(raw_close) if isinstance(raw_close, (int, float)) else decimals_of_text(str(raw_close))

        def positive(key):
            v = number(cell(row, key))
            return v if v is not None and v > 0 else None

        bars[isin] = OfficialBar(
            day=day,
            close=close,
            open=positive("open"),
            high=positive("high"),
            low=positive("low"),
            volume=number(cell(row, "volume")),
            trades=number(cell(row, "trades")),
            decimals=decimals,
        )
        info[isin] = {"name": (str(cell(row, "name") or "").strip() or None), "currency": (str(cell(row, "currency") or "").strip() or None)}
    return ("ok" if bars else "ohne_zeilen"), bars, info


def parse_gpw_html(html: str, day: int) -> tuple[str, dict[str, OfficialBar], dict]:
    parser = _Tables()
    parser.feed(html or "")
    for table in parser.tables:
        if any(any("isin" in c.lower() for c in row) for row in table[:3]):
            return parse_table(table, day)
    return ("ohne_tabelle" if not parser.tables else "ohne_isin_spalte"), {}, {}


def sheet_tables(content: bytes, ext: str) -> list[list[list]]:
    """Alle Blätter einer Excel-Datei als Zeilen (Werte) – .xlsx mit openpyxl, .xls mit xlrd."""
    if ext == "xlsx":
        import openpyxl

        book = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        return [[list(r) for r in ws.iter_rows(values_only=True)] for ws in book.worksheets]
    import xlrd

    book = xlrd.open_workbook(file_contents=content)
    return [[sh.row_values(k) for k in range(sh.nrows)] for sh in book.sheets()]


def _get(http, url: str, headers: dict) -> tuple[str, bytes | None]:
    try:
        response = http.get(url, headers=headers)
    except Exception as exc:  # noqa: BLE001 - Netzfehler werden gezählt, nicht geraten
        return f"fehler_{type(exc).__name__}", None
    if response.status_code != 200:
        return f"http_{response.status_code}", None
    return "ok", bytes(response.content or b"")


@dataclass
class DayFile:
    """Kurse aller Aktien einer Sitzung aus einer Tagesquelle (GPW oder NewConnect)."""

    source: str
    day: int
    status: str
    bars: dict[str, OfficialBar] = field(default_factory=dict)
    info: dict[str, dict] = field(default_factory=dict)


def fetch_gpw_day(http, day: int) -> DayFile:
    url = GPW_URL.format(date=date_of(day).strftime("%d-%m-%Y"))
    code, content = _get(http, url, GPW_HEADERS)
    if code != "ok":
        return DayFile("gpw", day, code)
    status, bars, info = parse_gpw_html((content or b"").decode("utf-8", errors="replace"), day)
    return DayFile("gpw", day, status, bars, info)


def fetch_newconnect_day(http, day: int) -> DayFile:
    ymd = date_of(day).strftime("%Y%m%d")
    status = "ohne_datei"
    for ext in ("xlsx", "xls"):
        code, content = _get(http, NC_URL.format(ymd=ymd, ext=ext), NC_HEADERS)
        if code != "ok":
            status = code
            continue
        try:
            tables = sheet_tables(content or b"", ext)
        except ImportError:
            status = f"modul_fehlt_{ext}"
            continue
        except Exception as exc:  # noqa: BLE001 - unlesbare Datei: nur zählen
            status = f"unlesbar_{ext}_{type(exc).__name__}"
            continue
        for table in tables:
            status, bars, info = parse_table(table, day)
            if status == "ok":
                return DayFile("newconnect", day, status, bars, info)
    return DayFile("newconnect", day, status)


# ----------------------------------------------------------------------------------------------------------- CSE

def cse_symbol(yahoo_symbol: str) -> str:
    """Yahoo-Kürzel → Kürzel der CSE („ABC.CN“ → „ABC“, „ABC-U.CN“ → „ABC.U“)."""
    s = (yahoo_symbol or "").strip().upper()
    for suffix in (".CN", ".NE"):
        if s.endswith(suffix):
            s = s[: -len(suffix)]
            break
    return s.replace("-", ".")


def _split_line(line: str) -> list[str]:
    parts = [p.strip() for p in line.split("\t")]
    if len([p for p in parts if p]) >= 4:
        return parts
    return [p.strip() for p in re.split(r"\s{2,}", line.strip())]


def parse_cse_summary(text: str, day: int) -> tuple[str, dict[str, OfficialBar], dict]:
    """„Daily Market Summary“ der CSE: Tabelle mit Abschlüssen (Stock, Symbol, Vol(00s), High, Low, Close, …) und Tabelle der
    Werte ohne Abschluss (Geld/Brief). Rückgabe: Kurse je Kürzel; Werte ohne Abschluss mit Umsatz 0 und ohne Schlusskurs werden
    nur gezählt (``info[...]['ohne_abschluss']``) – die CSE nennt für sie keinen Schlusskurs."""
    bars: dict[str, OfficialBar] = {}
    info: dict[str, dict] = {}
    header: dict[str, int] | None = None
    for raw in (text or "").splitlines():
        if not raw.strip():
            continue
        cells = _split_line(raw)
        lower = [c.lower() for c in cells]
        if "symbol" in lower and ("close" in lower or "bid" in lower or "ask" in lower):
            header = {name: k for k, name in enumerate(lower)}
            continue
        if header is None or "symbol" not in header:
            continue
        k_sym = header["symbol"]
        if k_sym >= len(cells):
            continue
        symbol = cells[k_sym].strip().upper()
        if not symbol or " " in symbol:
            continue
        name = cells[header["stock"]].strip() if "stock" in header and header["stock"] < len(cells) else None
        if "close" not in header:
            info.setdefault(symbol, {"name": name, "currency": None, "ohne_abschluss": True})
            continue
        k_close = header["close"]
        close_text = cells[k_close] if k_close < len(cells) else ""
        close = money_number(close_text)
        if close is None or close <= 0:
            continue
        vol_key = next((h for h in header if h.startswith("vol")), None)
        volume = money_number(cells[header[vol_key]]) if vol_key is not None and header[vol_key] < len(cells) else None
        if volume is not None and "00s" in (vol_key or ""):
            volume *= 100.0

        def opt(name):
            k = header.get(name)
            v = money_number(cells[k]) if k is not None and k < len(cells) else None
            return v if v is not None and v > 0 else None

        bars[symbol] = OfficialBar(day=day, close=close, high=opt("high"), low=opt("low"), volume=volume, decimals=decimals_of_text(close_text))
        info[symbol] = {"name": name, "currency": "USD" if symbol.endswith(".U") else "CAD"}
    return ("ok" if bars else "ohne_zeilen"), bars, info


def fetch_cse_day(http, day: int) -> "DayFile":
    code, content = _get(http, CSE_URL.format(date=date_of(day).isoformat()), CSE_HEADERS)
    if code != "ok":
        return DayFile("cse", day, code)
    status, bars, info = parse_cse_summary((content or b"").decode("utf-8", errors="replace"), day)
    return DayFile("cse", day, status, bars, info)


# ----------------------------------------------------------------------------------------------------------- TMX

def tmx_symbol(yahoo_symbol: str) -> str:
    """Yahoo-Kürzel → Kürzel bei TMX: Endung weg, Gattung mit Punkt („ABC-A.TO“ → „ABC.A“, „XYZ.V“ → „XYZ“, „ABC-UN.TO“ →
    „ABC.UN“)."""
    s = (yahoo_symbol or "").strip().upper()
    for suffix in (".TO", ".V", ".NE", ".CN"):
        if s.endswith(suffix):
            s = s[: -len(suffix)]
            break
    return s.replace("-", ".")


def _tmx_post(http, query: str, variables: dict, name: str) -> tuple[str, object | None]:
    try:
        r = http.post(TMX_URL, json_body={"operationName": name, "variables": variables, "query": query}, headers=TMX_HEADERS)
    except Exception as exc:  # noqa: BLE001
        return f"fehler_{type(exc).__name__}", None
    if r.status_code != 200:
        return f"http_{r.status_code}", None
    try:
        payload = r.json()
    except ValueError:
        return "unlesbar", None
    if not isinstance(payload, dict):
        return "unlesbar", None
    data = (payload.get("data") or {}).get(name)
    if payload.get("errors") and not data:
        return "graphql_fehler", None
    return "ok", data


def tmx_rows(items, date_key: str, keys: dict[str, str], start_day: int, end_day: int) -> dict[int, OfficialBar]:
    rows: dict[int, OfficialBar] = {}
    for item in items or []:
        if not isinstance(item, dict):
            continue
        text = str(item.get(date_key) or "")[:10]
        try:
            day = day_of(dt.date.fromisoformat(text))
        except ValueError:
            continue
        close = money_number(item.get(keys["close"]))
        if close is None or close <= 0 or not (start_day <= day <= end_day):
            continue

        def opt(k):
            name = keys.get(k)
            v = money_number(item.get(name)) if name else None
            return v if v is not None and v > 0 else None

        volume = money_number(item.get(keys.get("volume", "volume")))
        rows[day] = OfficialBar(day=day, close=close, open=opt("open"), high=opt("high"), low=opt("low"), volume=volume,
                                decimals=decimals_of_number(close))
    return rows


def fetch_tmx(http, yahoo_symbol: str, start_day: int, end_day: int) -> OfficialSeries:
    """Kursmeldung (Name, Börse) und Tageskerzen bei TMX Money: zuerst die Kerzen der Kursgrafik, sonst die Kurshistorie
    rückwärts in Abschnitten (liefert je Abfrage nur einen Teil der Tage)."""
    symbol = tmx_symbol(yahoo_symbol)
    code, quote = _tmx_post(http, TMX_QUOTE, {"symbol": symbol, "locale": "en"}, "getQuoteBySymbol")
    if code != "ok":
        return OfficialSeries("tmx", f"kursmeldung_{code}", symbol=symbol)
    if not isinstance(quote, dict) or not quote.get("name"):
        return OfficialSeries("tmx", "nicht_gefunden", symbol=symbol)
    series = OfficialSeries(
        "tmx", "ok", name=quote.get("name"), exchange=quote.get("exchangeName") or quote.get("exchangeCode"),
        currency="USD" if symbol.endswith(".U") else "CAD", symbol=symbol,
    )
    variables = {"symbol": symbol, "freq": "day", "interval": None, "start": date_of(start_day).isoformat(),
                 "end": date_of(end_day + 1).isoformat(), "startDateTime": None, "endDateTime": None}
    rows: dict[int, OfficialBar] = {}
    code, data = _tmx_post(http, TMX_SERIES_OHLC, variables, "getTimeSeriesData")
    if code == "ok":
        rows = tmx_rows(data, "dateTime", {"close": "close", "open": "open", "high": "high", "low": "low", "volume": "volume"}, start_day, end_day)
        series.detail = "kursgrafik"
    else:
        code, data = _tmx_post(http, TMX_SERIES, variables, "getTimeSeriesData")
        if code == "ok":
            rows = tmx_rows(data, "dateTime", {"close": "close", "volume": "volume"}, start_day, end_day)
            series.detail = "kursgrafik_ohne_ohlc"
    if len(rows) < 2:
        rows, end, pages = {}, end_day, 0
        while end >= start_day and pages < TMX_HISTORY_PAGES:
            variables = {"symbol": symbol, "start": date_of(start_day).isoformat(), "end": date_of(end).isoformat(), "limit": 400,
                         "adjusted": False, "unadjusted": True}
            code, data = _tmx_post(http, TMX_HISTORY, variables, "getCompanyPriceHistory")
            pages += 1
            if code != "ok":
                break
            part = tmx_rows(data, "datetime", {"close": "closePrice", "open": "openPrice", "high": "highPrice", "low": "lowPrice", "volume": "volume"}, start_day, end_day)
            new = {d: r for d, r in part.items() if d not in rows}
            if not new:
                break
            rows.update(new)
            end = min(new) - 1
        series.detail = f"kurshistorie_{pages}_abschnitte"
    series.bars = rows
    if not rows:
        series.status = "keine_kurse"
    return series


# ---------------------------------------------------------------------------------------------------------- NOCP

def nasdaq_date(text: str) -> int | None:
    try:
        return day_of(dt.datetime.strptime(text.strip(), "%m/%d/%Y").date())
    except (ValueError, AttributeError):
        return None


def parse_nocp(payload) -> dict[int, OfficialBar]:
    """NOCP-Historie ohne feste Feldnamen: jede Liste von Einträgen mit einem Datum (MM/TT/JJJJ) und einem Kurs."""
    found: dict[int, OfficialBar] = {}

    def walk(node) -> None:
        if isinstance(node, dict):
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                if isinstance(item, dict):
                    day = None
                    value = None
                    text = None
                    for name, v in item.items():
                        if isinstance(v, str) and day is None and len(v.strip()) == 10 and v.strip()[2:3] == "/" and v.strip()[5:6] == "/":
                            day = nasdaq_date(v)
                        elif value is None and str(name).lower() in ("price", "nocp", "close", "value") and isinstance(v, (str, int, float)):
                            value = money_number(v)
                            text = v if isinstance(v, str) else None
                    if day is not None and value is not None and value > 0:
                        decimals = decimals_of_text(text) if text is not None else decimals_of_number(value)
                        found[day] = OfficialBar(day=day, close=value, decimals=decimals)
                walk(item)

    walk(payload)
    return found


def fetch_nocp(http, symbol: str) -> OfficialSeries:
    """Offizieller Schlusskurs (NOCP) der letzten 12 Monate, sonst 3 Monate."""
    nasdaq = (symbol or "").strip().upper().replace("-", ".")
    status = "keine_kurse"
    for url in NOCP_URLS:
        code, content = _get(http, url.format(symbol=nasdaq), NASDAQ_HEADERS)
        if code != "ok":
            status = code
            continue
        try:
            payload = json.loads((content or b"").decode("utf-8"))
        except ValueError:
            status = "unlesbar"
            continue
        bars = parse_nocp(payload)
        if bars:
            return OfficialSeries("nasdaq_nocp", "ok", bars=bars, exchange="Nasdaq", currency="USD", symbol=nasdaq,
                                  detail="y1" if "y1" in url else "m3")
        status = "keine_kurse"
    return OfficialSeries("nasdaq_nocp", status, symbol=nasdaq)


# ----------------------------------------------------------------------------------------------------------- CNBC

def cnbc_bars(payload, start_day: int, end_day: int) -> dict[int, OfficialBar]:
    rows: dict[int, OfficialBar] = {}
    bars = (((payload or {}).get("barData") or {}).get("priceBars")) if isinstance(payload, dict) else None
    for item in bars or []:
        if not isinstance(item, dict):
            continue
        stamp = str(item.get("tradeTime") or "")[:8]
        try:
            day = day_of(dt.datetime.strptime(stamp, "%Y%m%d").date())
        except ValueError:
            continue
        close = money_number(item.get("close"))
        if close is None or close <= 0 or not (start_day <= day <= end_day):
            continue

        def opt(k):
            v = money_number(item.get(k))
            return v if v is not None and v > 0 else None

        rows[day] = OfficialBar(day=day, close=close, open=opt("open"), high=opt("high"), low=opt("low"),
                                volume=money_number(item.get("volume")), decimals=decimals_of_number(close))
    return rows


def fetch_cnbc_bars(http, cnbc_symbol: str, start_day: int, end_day: int) -> OfficialSeries:
    url = CNBC_BARS_URL.format(symbol=cnbc_symbol, start=date_of(start_day), end=date_of(end_day + 1))
    code, content = _get(http, url, CNBC_HEADERS)
    if code != "ok":
        return OfficialSeries("cnbc", code, symbol=cnbc_symbol)
    try:
        payload = json.loads((content or b"").decode("utf-8"))
    except ValueError:
        return OfficialSeries("cnbc", "unlesbar", symbol=cnbc_symbol)
    bars = cnbc_bars(payload, start_day, end_day)
    return OfficialSeries("cnbc", "ok" if bars else "keine_kurse", bars=bars, symbol=cnbc_symbol)


# ------------------------------------------------------------------------------------------------- Zusammenstellung

@dataclass
class ExchangeSources:
    """Zugriff auf die amtlichen Quellen im täglichen Lauf (Produktion) – über ``HttpClient``; in Tests ersetzbar."""

    http: object
    fetch_gpw: Callable[[object, int], DayFile] = fetch_gpw_day
    fetch_newconnect: Callable[[object, int], DayFile] = fetch_newconnect_day
    fetch_cse: Callable[[object, int], DayFile] = fetch_cse_day
    fetch_tmx: Callable[[object, str, int, int], OfficialSeries] = fetch_tmx
    fetch_nocp: Callable[[object, str], OfficialSeries] = fetch_nocp
    name: str = "boersen"

    def sources_for(self, exchange_key: str | None) -> tuple[str, ...]:
        return sources_for(exchange_key)

    def day_file(self, source: str, day: int) -> DayFile:
        if source == "gpw":
            return self.fetch_gpw(self.http, day)
        if source == "newconnect":
            return self.fetch_newconnect(self.http, day)
        if source == "cse":
            return self.fetch_cse(self.http, day)
        raise KeyError(source)

    def symbol_series(self, source: str, symbol: str, start_day: int, end_day: int) -> OfficialSeries:
        if source == "tmx":
            return self.fetch_tmx(self.http, symbol, start_day, end_day)
        if source == "nasdaq_nocp":
            series = self.fetch_nocp(self.http, symbol)
            series.bars = {d: b for d, b in series.bars.items() if start_day <= d <= end_day}
            return series
        raise KeyError(source)


def sources_for(exchange_key: str | None, provider_exchange: str | None = None) -> tuple[str, ...]:
    """Amtliche Quellen einer Notierung der App (in der Reihenfolge der Abfrage). Nasdaq: nur für Nasdaq-notierte Aktien
    (Börsenschlüssel XNAS)."""
    if exchange_key == "XWAR":
        return ("gpw", "newconnect")
    if exchange_key in ("XTSE", "XTSX"):
        return ("tmx",)
    if exchange_key == "XCNQ":
        return ("cse",)
    if exchange_key == "XNAS":
        return ("nasdaq_nocp",)
    return ()


def tmx_exchange_matches(exchange_key: str, source_exchange: str | None) -> bool:
    """Börse laut TMX passt zur Börse der App (TSX ≠ TSX Venture)."""
    text = (source_exchange or "").upper()
    if not text:
        return False
    venture = "VENTURE" in text or "TSXV" in text or text in ("CDX", "TSX-V")
    if exchange_key == "XTSX":
        return venture
    if exchange_key == "XTSE":
        return not venture and ("TORONTO" in text or "TSX" in text)
    return False


def iter_days(first: int, last: int) -> Iterable[int]:
    return range(int(first), int(last) + 1)
