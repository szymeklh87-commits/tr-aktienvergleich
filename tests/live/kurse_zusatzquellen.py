"""Weitere frei zugängliche Vergleichsquellen für US-Aktien ohne Kurse bei Nasdaq (seit dem 25.10.2026).

Simons Auftrag vom 25.10.2026, 03:47 Uhr: „Suche für die 38 ungeprüften Aktien weitere unabhängige, frei zugängliche
Quellen. Beginne mit den zehn Aktien aus den Top 10. Prüfe vor jedem Vergleich Wertpapieridentität, Handelsplatz,
Währung, Handelsdatum, Schlusskursdefinition und Split-/Dividendenbereinigung. […] Keine kostenpflichtigen Zugänge ohne
Freigabe.“

Nasdaq führt für 38 der 404 ausgewählten US-Aktien keine Kurse (Lauf 40139805053; 34 davon mit fünfstelligem Kürzel). Die
App ordnet einer Aktie den Schlüssel „US“ zu, wenn die Identitätsquelle die US-Gesamtnotierung meldet; Yahoo liefert die
Kurse dann auch aus dem OTC-Handel (Börsencode PNK, OQX, OQB …) – den Nasdaq nicht führt. Dieses Modul fragt für solche
Aktien weitere Quellen ab, **ohne Schlüssel und ohne Anmeldung** (keine kostenpflichtigen Zugänge):

* **OTC Markets** – Betreiber des OTC-Handels (Unternehmensprofil, letzter Abschluss, Kurshistorie der Website),
* **CNBC** – Kursmeldung (Name, Börse, Währung) und Tageskerzen der Website,
* **Barchart** – Tageskurse der Website (unbereinigt angefordert),
* **MarketWatch** – CSV-Download der Kurshistorie,
* **Stooq** – CSV-Download (seit März 2026 nur noch mit Schlüssel – geprüft, ob er ohne Schlüssel antwortet).

Diese Schnittstellen sind nicht offiziell dokumentiert; jede Antwort wird ohne feste Feldnamen ausgewertet (Liste von
Einträgen mit Datum und Schlusskurs) und vor jedem Vergleich geprüft:

1. **Wertpapieridentität:** ISIN oder CUSIP der Quelle gleich der ISIN des Stands; sonst Name der Quelle ähnlich einem
   Namen des Stands; Quellen ohne Namen nur über das US-Kürzel (in den USA börsenübergreifend eindeutig) und das Kursniveau.
2. **Handelsplatz:** Börse der Quelle (wo angegeben) und Börse, aus der Yahoo die Kurse des Stands liefert.
3. **Währung:** Währung der Quelle (wo angegeben), Währung des Stands und der Yahoo-Kurse.
4. **Handelsdatum:** Tag der Quelle (Zeitstempel als Kalendertag) – geprüft, ob die Kurse um einen Tag versetzt passen.
5. **Schlusskursdefinition:** OTC-Handel kennt keine Schlussauktion, Schlusskurs ist der letzte Abschluss; bei den übrigen
   Quellen ist die Definition nicht veröffentlicht. Tage ohne Umsatz werden gezählt.
6. **Split- und Dividendenbereinigung:** konstanter Faktor (Split) und Gleichheit mit dem dividendenbereinigten Yahoo-Kurs.

Verglichen wird nur mit einer Quelle, die alle Prüfungen besteht; was keine besteht, bleibt „keine Vergleichskurse“ – mit
dem Grund je Quelle (Abruf gescheitert, keine Kurse, Identität, Kursniveau, Währung, Handelsplatz). Ausgegeben werden nur
Zählwerte, nie Kürzel, Namen oder Kurse.
"""

from __future__ import annotations

import csv
import datetime as dt
import io
import statistics
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "backend"))

import kurse_gegenpruefen as gegen  # noqa: E402 - Toleranz, Einordnung eines Tags, Datum
from traktien.util.names import name_similarity  # noqa: E402 - dieselbe Namensähnlichkeit wie die Identitätsprüfung

EPOCH = dt.date(1970, 1, 1)
SOURCES = ("otc_markets", "cnbc", "barchart", "marketwatch", "stooq")  # Reihenfolge = Vorrang als Vergleichsquelle
SOURCE_TEXT = {
    "otc_markets": "OTC Markets (Betreiber des OTC-Handels)",
    "cnbc": "CNBC",
    "barchart": "Barchart",
    "marketwatch": "MarketWatch",
    "stooq": "Stooq",
}
DEFINITION = {
    "otc_markets": "letzter Abschluss des Tages (OTC-Handel ohne Schlussauktion)",
    "cnbc": "Schlusskurs der Tageskerze (Definition nicht veröffentlicht)",
    "barchart": "Schlusskurs, unbereinigt angefordert (Definition nicht veröffentlicht)",
    "marketwatch": "Schlusskurs der Kurshistorie (Definition nicht veröffentlicht)",
    "stooq": "Schlusskurs (Definition nicht veröffentlicht)",
}
HOSTS = {
    "backend.otcmarkets.com": 0.5,
    "quote.cnbc.com": 0.3,
    "ts-api.cnbc.com": 0.3,
    "www.barchart.com": 0.5,
    "www.marketwatch.com": 1.0,
    "stooq.com": 0.5,
}
HEADERS = {
    "otc_markets": {"Accept": "application/json, text/plain, */*", "Origin": "https://www.otcmarkets.com", "Referer": "https://www.otcmarkets.com/"},
    "cnbc": {"Accept": "application/json, text/plain, */*", "Origin": "https://www.cnbc.com", "Referer": "https://www.cnbc.com/"},
    "barchart": {"Accept": "text/plain, */*", "Referer": "https://www.barchart.com/"},
    "marketwatch": {"Accept": "text/csv, text/plain, */*", "Referer": "https://www.marketwatch.com/"},
    "stooq": {"Accept": "text/csv, text/plain, */*", "Referer": "https://stooq.com/"},
}
OTC_CODES = {"PNK", "OQB", "OQX", "OEM", "OGM", "OBB"}  # Yahoo-Börsencodes des OTC-Handels (config/boersen.yaml)
EXCHANGE_CODES = {"NYQ", "NYS", "NMS", "NGM", "NCM", "NAS", "ASE", "PCX", "BTS"}
MIN_DAYS = 10  # so viele gemeinsame Tage braucht ein Vergleich
LEVEL_TOLERANCE = 0.02  # mittlere Abweichung des Kursniveaus, ab der eine Quelle ein anderes Wertpapier oder eine andere Einheit führt
NAME_CONFIRMED = 0.5
NAME_SIMILAR = 0.3
CLOSE_KEYS = ("close", "closeprice", "closingprice", "closing", "lastsale", "lastsaleprice", "lastprice", "last", "price")
NAME_KEYS = ("name", "companyname", "issuername", "securityname", "longname")
VENUE_KEYS = ("exchange", "exchangename", "tierdisplayname", "tiername", "venue", "market", "exchangecode")
CURRENCY_KEYS = ("currency", "currencycode")


def _date(year: int, month: int, day: int) -> int | None:
    try:
        return (dt.date(year, month, day) - EPOCH).days
    except ValueError:
        return None


def day_of_value(value) -> int | None:
    """Kalendertag aus den üblichen Formaten: „MM/TT/JJJJ“, „JJJJ-MM-TT…“, „JJJJMMTT[hhmmss]“, Zeitstempel in s oder ms
    (als UTC-Kalendertag – ein Versatz um einen Tag fällt bei der Prüfung des Handelsdatums auf)."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        if 1e12 <= number < 4e12:
            number /= 1000.0
        if 1e9 <= number < 4e9:
            return int(number // 86400)
        return None
    text = str(value).strip()
    if len(text) >= 10 and text[2] == "/" and text[5] == "/" and text[:2].isdigit() and text[3:5].isdigit() and text[6:10].isdigit():
        return _date(int(text[6:10]), int(text[:2]), int(text[3:5]))
    if len(text) >= 10 and text[4] == "-" and text[7] == "-" and text[:4].isdigit() and text[5:7].isdigit() and text[8:10].isdigit():
        return _date(int(text[:4]), int(text[5:7]), int(text[8:10]))
    if text.isdigit() and len(text) in (8, 14):
        return _date(int(text[:4]), int(text[4:6]), int(text[6:8]))
    if text.isdigit() and len(text) in (10, 13):
        return day_of_value(int(text))
    return None


def number(value) -> float | None:
    """„$1,234.56“, „1.234“, 1234 → Zahl; leer, „N/A“, ≤ 0 → None."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value) if value > 0 else None
    return gegen.price(value)


def volume_value(value) -> float | None:
    """Umsatz: Zahl (auch 0) oder Text mit Tausenderkommas; leer oder unlesbar → None."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).replace(",", "").strip()
    try:
        return float(text)
    except ValueError:
        return None


def _key(name) -> str:
    return "".join(ch for ch in str(name).lower() if ch.isalnum())


def parse_json_rows(payload) -> tuple[dict[int, dict], list[str]]:
    """Tageskurse ohne feste Feldnamen: die längste Liste von Einträgen mit einem Datum und einem Schlusskurs (Feldnamen wie
    „close“, „closingPrice“, „lastSale“). Rückgabe: Kurs und Umsatz je Tag, Feldnamen des ersten Eintrags (ohne Werte)."""
    best: tuple[dict[int, dict], list[str]] = ({}, [])

    def row_of(item: dict) -> tuple[int, float, float | None] | None:
        day = None
        close = None
        volume = None
        rank = len(CLOSE_KEYS)
        for name, value in item.items():
            key = _key(name)
            if day is None and ("date" in key or "time" in key or key in ("d", "t", "day")):
                day = day_of_value(value)
            if key in CLOSE_KEYS and CLOSE_KEYS.index(key) < rank:
                candidate = number(value)
                if candidate is not None:
                    close, rank = candidate, CLOSE_KEYS.index(key)
            if "volume" in key or key in ("vol", "v"):
                volume = volume_value(value)
        if day is None:  # Datum ohne sprechenden Feldnamen
            for value in item.values():
                day = day_of_value(value) if isinstance(value, str) else None
                if day is not None:
                    break
        return (day, close, volume) if day is not None and close is not None else None

    def walk(node) -> None:
        nonlocal best
        if isinstance(node, dict):
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            rows: dict[int, dict] = {}
            fields: list[str] = []
            for item in node:
                if isinstance(item, dict):
                    parsed = row_of(item)
                    if parsed is not None:
                        day, close, volume = parsed
                        rows[day] = {"close": close, "volume": volume}
                        if not fields:
                            fields = [str(k) for k in item]
                walk(item)
            if len(rows) > len(best[0]):
                best = (rows, fields)

    walk(payload)
    return best


def parse_csv_rows(text: str) -> tuple[dict[int, dict], list[str]]:
    """CSV mit Kopfzeile („Date,Open,High,Low,Close,Volume“) oder ohne (Barchart: Kürzel, Datum, Eröffnung, Hoch, Tief,
    Schluss, Umsatz). Rückgabe wie ``parse_json_rows``."""
    lines = [line for line in (text or "").splitlines() if line.strip()]
    if not lines:
        return {}, []
    reader = list(csv.reader(io.StringIO("\n".join(lines))))
    header = [_key(x) for x in reader[0]]
    rows: dict[int, dict] = {}
    if "date" in header and any(k in header for k in ("close", "last")):
        d, c = header.index("date"), header.index("close") if "close" in header else header.index("last")
        v = header.index("volume") if "volume" in header else None
        for row in reader[1:]:
            if len(row) <= max(d, c):
                continue
            day, close = day_of_value(row[d]), number(row[c])
            if day is not None and close is not None:
                rows[day] = {"close": close, "volume": volume_value(row[v]) if v is not None and v < len(row) else None}
        return rows, [str(x) for x in reader[0]]
    for row in reader:  # ohne Kopfzeile: Datum in der zweiten Spalte, Schluss in der sechsten
        if len(row) >= 6 and day_of_value(row[1]) is not None:
            close = number(row[5])
            if close is not None:
                rows[day_of_value(row[1])] = {"close": close, "volume": volume_value(row[6]) if len(row) > 6 else None}
    return rows, (["kuerzel", "datum", "eroeffnung", "hoch", "tief", "schluss", "umsatz"] if rows else [])


def find_meta(payload) -> dict:
    """Name, Börse, Währung, ISIN und CUSIP aus einer Antwort ohne feste Struktur – Ebene für Ebene (die oberste zuerst),
    je Angabe der erste Treffer."""
    found: dict = {}
    level = [payload]
    while level:
        deeper = []
        for node in level:
            items = node.items() if isinstance(node, dict) else enumerate(node) if isinstance(node, list) else ()
            for name, value in items:
                if isinstance(value, (dict, list)):
                    deeper.append(value)
                    continue
                if not isinstance(node, dict) or not isinstance(value, str) or not value.strip():
                    continue
                key, text = _key(name), value.strip()
                if key in NAME_KEYS and len(text) >= 3:
                    found.setdefault("name", text)
                elif key in VENUE_KEYS:
                    found.setdefault("boerse", text)
                elif key in CURRENCY_KEYS and len(text) == 3:
                    found.setdefault("waehrung", text.upper())
                elif key == "isin" and len(text) == 12:
                    found.setdefault("isin", text.upper())
                elif key == "cusip" and len(text) == 9:
                    found.setdefault("cusip", text.upper())
        level = deeper
    return found


def requests_for(source: str, symbol: str, start_day: int, cutoff: int) -> list[tuple[str, str]]:
    """Abrufe je Quelle: (Art, Adresse). Art „profil“ (Name, Börse, Währung), „kurs“ (letzter Abschluss), „historie…“
    (Tageskurse; mehrere Adressen werden der Reihe nach versucht, die erste mit Kursen gilt). Das Kürzel kommt im Format von
    Yahoo („BRK-B“); CNBC, Barchart und MarketWatch schreiben die Aktiengattung mit Punkt („BRK.B“)."""
    s = symbol.upper()
    dotted = s.replace("-", ".")
    start = EPOCH + dt.timedelta(days=start_day)
    end = EPOCH + dt.timedelta(days=cutoff + 1)
    if source == "otc_markets":
        return [
            ("profil", f"https://backend.otcmarkets.com/otcapi/company/profile/full/{s}?symbol={s}"),
            ("kurs", f"https://backend.otcmarkets.com/otcapi/stock/trade/inside/{s}?symbol={s}"),
            ("historie", f"https://backend.otcmarkets.com/otcapi/stock/trade/historical/{s}?symbol={s}&page=1&pageSize=200&sortOn=tradeDate&sortDir=DESC"),
            ("historie_2", f"https://backend.otcmarkets.com/otcapi/stock/trade/history/{s}?symbol={s}&page=1&pageSize=200"),
            ("historie_3", f"https://backend.otcmarkets.com/otcapi/stock/trade/chart/{s}?symbol={s}&period=6M"),
        ]
    if source == "cnbc":
        return [
            ("profil", f"https://quote.cnbc.com/quote-html-webservice/restQuote/symbolType/symbol?symbols={dotted}&requestMethod=itv&noform=1&partnerId=2&fund=1&exthrs=1&output=json&events=1"),
            ("historie", f"https://ts-api.cnbc.com/harmony/app/bars/{dotted}/1D/{start:%Y%m%d}000000/{end:%Y%m%d}000000/adjusted/EST5EDT.json"),
        ]
    if source == "barchart":
        return [("historie", f"https://www.barchart.com/proxies/timeseries/queryeod.ashx?symbol={dotted}&data=daily&maxrecords=200&volume=total&order=asc&dividends=false&backadjust=false&daystoexpiration=1&contractroll=expiration")]
    if source == "marketwatch":
        return [("historie", f"https://www.marketwatch.com/investing/stock/{dotted.lower()}/downloaddatapartial?startdate={start:%m/%d/%Y}%2000:00:00&enddate={end:%m/%d/%Y}%2023:59:59&daterange=d30&frequency=p1d&csvdownload=true&downloadpartial=false&newdates=false&countrycode=us")]
    if source == "stooq":
        return [("historie", f"https://stooq.com/q/d/l/?s={s.lower()}.us&d1={start:%Y%m%d}&d2={end:%Y%m%d}&i=d")]
    raise ValueError(source)


def last_trade(payload) -> tuple[int, float] | None:
    """Letzter Abschluss aus der Kursmeldung von OTC Markets: ``lastSale`` mit dem Tag aus ``lastTradeTime`` (Lauf
    40159274087: die Meldung hat auch „insideTime“, „quoteTime“ und „quoteDateTime“ – das ist der Zeitpunkt der Abfrage,
    nicht des Abschlusses). Ohne beide Felder kein Wert."""
    if not isinstance(payload, dict):
        return None
    value, stamp = number(payload.get("lastSale")), payload.get("lastTradeTime")
    day = day_of_value(stamp) if stamp not in (None, "") else None
    return (day, value) if day is not None and value is not None else None


def get_raw(http, url: str, headers: dict) -> tuple[str, bytes | None]:
    """Status („ok“, „http_403“, „fehler_<Art>“) und Inhalt einer Antwort."""
    try:
        response = http.get(url, headers=headers)
    except Exception as exc:  # noqa: BLE001 - Netz: nur zählen
        return f"fehler_{type(exc).__name__}", None
    if response.status_code != 200:
        return f"http_{response.status_code}", None
    content = getattr(response, "content", None)
    if content is None:  # Testantworten ohne Rohinhalt
        try:
            import json

            content = json.dumps(response.json()).encode("utf-8")
        except Exception:  # noqa: BLE001
            content = b""
    return "ok", bytes(content)


def decode(content: bytes | None) -> tuple[object | None, str]:
    """JSON, falls die Antwort JSON ist, sonst Text."""
    text = (content or b"").decode("utf-8", errors="replace")
    stripped = text.lstrip()
    if stripped[:1] in ("{", "["):
        try:
            import json

            return json.loads(stripped), text
        except ValueError:
            return None, text
    return None, text


def fetch_source(http, source: str, symbol: str, start_day: int, cutoff: int) -> dict:
    """Alle Abrufe einer Quelle: Status je Art, Tageskurse, Feldnamen (ohne Werte), Angaben zu Name, Börse und Währung und –
    bei einer Kursmeldung – der letzte Abschluss (Tag, Kurs). Von mehreren Adressen der Kurshistorie gilt die erste mit
    Kursen; die übrigen werden dann nicht mehr abgefragt."""
    out: dict = {"quelle": source, "status": {}, "rows": {}, "felder": [], "felder_kurs": [], "meta": {}, "letzter": None}
    for kind, url in requests_for(source, symbol, start_day, cutoff):
        if kind.startswith("historie") and out["rows"]:
            continue
        status, content = get_raw(http, url, HEADERS[source])
        payload, text = decode(content) if status == "ok" else (None, "")
        if status == "ok" and payload is None and not kind.startswith("historie"):
            status = "kein_json"
        if status == "ok" and kind.startswith("historie"):
            rows, fields = parse_json_rows(payload) if payload is not None else parse_csv_rows(text)
            if not rows:
                status = "ok_ohne_kurse" if (payload is not None or text.strip()) else "leer"
                if payload is None and "<html" in text[:2000].lower():
                    status = "html_statt_daten"  # z. B. Hinweis auf einen Schlüssel oder eine Anmeldung
            else:
                out["rows"], out["felder"] = {d: r for d, r in rows.items() if start_day <= d <= cutoff}, fields
        if status == "ok" and payload is not None and kind in ("profil", "kurs"):
            for name, value in find_meta(payload).items():
                out["meta"].setdefault(name, value)
            if kind == "kurs":
                out["felder_kurs"] = sorted(str(k) for k in payload) if isinstance(payload, dict) else []
                out["letzter"] = last_trade(payload)
        out["status"][kind] = status
    return out


def venue_kind(text: str | None, source: str) -> str:
    """Handelsplatz einer Quelle: „otc“, „boerse“ oder „nicht_angegeben“."""
    if source == "otc_markets":
        return "otc"
    t = (text or "").upper()
    if not t:
        return "nicht_angegeben"
    if any(word in t for word in ("OTC", "PINK", "PNK", "GREY", "EXPERT")):
        return "otc"
    if any(word in t for word in ("NYSE", "NASDAQ", "AMEX", "ARCA", "BATS", "CBOE", "NYQ", "NMS", "NGM", "NCM")):
        return "boerse"
    return "nicht_angegeben"


def stand_venue(yahoo_exchange: str | None) -> str:
    if yahoo_exchange in OTC_CODES:
        return "otc"
    if yahoo_exchange in EXCHANGE_CODES:
        return "boerse"
    return "unbekannt"


def identity(meta: dict, stand_isin: str, stand_names: list[str]) -> str:
    """Identität nach der stärksten Angabe der Quelle: ISIN, CUSIP (bei US- und CA-ISIN die Stellen 3–11), Name, sonst Kürzel."""
    isin = (stand_isin or "").upper()
    if meta.get("isin"):
        return "isin_bestaetigt" if meta["isin"] == isin else "isin_anders"
    if meta.get("cusip") and isin[:2] in ("US", "CA"):
        return "cusip_bestaetigt" if isin[2:11] == meta["cusip"] else "cusip_anders"
    if meta.get("name"):
        best = max((name_similarity(meta["name"], n) for n in stand_names if n), default=0.0)
        if best >= NAME_CONFIRMED:
            return "name_bestaetigt"
        return "name_aehnlich" if best >= NAME_SIMILAR else "name_passt_nicht"
    return "nur_kuerzel"


def best_shift(own: dict[int, float], rows: dict[int, dict]) -> tuple[int, int]:
    """Versatz der Tage (−1, 0, +1), bei dem die meisten Kurse gleich sind, und die Zahl der gleichen Tage dabei. Ein Versatz
    gilt nur, wenn mit ihm die Mehrheit der gemeinsamen Tage gleich ist und deutlich mehr als ohne (doppelt so viele und
    mindestens 5 mehr) – zufällig gleiche Kurse an einzelnen Tagen ergeben keinen Versatz."""
    counts, common = {}, {}
    for shift in (0, -1, 1):
        days = [d for d in own if (d + shift) in rows]
        common[shift] = len(days)
        counts[shift] = sum(1 for d in days if abs(own[d] - rows[d + shift]["close"]) <= gegen.tolerance(rows[d + shift]["close"]))
    best = max((-1, 1), key=lambda s: counts[s])
    if common[best] and counts[best] >= 0.5 * common[best] and counts[best] >= 2 * counts[0] and counts[best] >= counts[0] + 5:
        return best, counts[best]
    return 0, counts[0]


def check(fetched: dict, own: dict[int, float], stand: dict, yahoo: dict) -> dict:
    """Prüfungen vor dem Vergleich mit einer Quelle. ``stand``: isin, namen, waehrung; ``yahoo``: Tageskurse und Börse der
    Yahoo-Kurse des Stands (parse_yahoo_daily). Ergebnis: jede Prüfung einzeln und ``vergleichbar``."""
    source = fetched["quelle"]
    rows = fetched["rows"]
    meta = fetched.get("meta") or {}
    result: dict = {"quelle": source, "definition": DEFINITION[source]}
    if not rows:
        result.update(vergleichbar=False, grund="keine_kurse" if all(s.startswith("ok") for s in fetched["status"].values()) else "abruf_gescheitert")
        return result
    result["identitaet"] = identity(meta, stand.get("isin", ""), stand.get("namen") or [])
    venue = venue_kind(meta.get("boerse"), source)
    mine = stand_venue(yahoo.get("exchange"))
    result["handelsplatz"] = "nicht_angegeben" if venue == "nicht_angegeben" else ("gleich" if venue == mine else "anders")
    result["handelsplatz_stand"] = mine
    own_currency = (stand.get("waehrung") or "").upper()
    yahoo_currency = (yahoo.get("currency") or "").upper()
    source_currency = (meta.get("waehrung") or "").upper()
    if source_currency:
        result["waehrung"] = "gleich" if source_currency == own_currency else "anders"
    else:
        result["waehrung"] = "nicht_angegeben"
    result["waehrung_yahoo"] = "gleich" if not yahoo_currency or yahoo_currency == own_currency else "anders"
    shift, equal = best_shift(own, rows)
    days_y = yahoo.get("days") or {}
    result["datum_versatz"] = shift
    common = [d for d in own if (d + shift) in rows]
    result["gemeinsame_tage"] = len(common)
    result["nur_im_stand"] = sum(1 for d in own if (d + shift) not in rows)
    result["nur_in_quelle"] = sum(1 for d in rows if (d - shift) not in own and min(own) <= d - shift <= max(own))
    ratios = sorted(own[d] / rows[d + shift]["close"] for d in common)
    level = statistics.median(ratios) if ratios else None
    if level is None:
        result["kursniveau"] = "ohne_gemeinsame_tage"
    elif abs(level - 1) <= LEVEL_TOLERANCE:
        result["kursniveau"] = "passt"
    elif gegen.classify(level, 1.0, []) == "faktor":
        result["kursniveau"] = "faktor"  # anderes Verhältnis (ADR/Aktie) oder anders bereinigt
    else:
        result["kursniveau"] = "passt_nicht"
    days_y = yahoo.get("days") or {}
    adjusted = sum(1 for d in common if (days_y.get(d) or {}).get("adjclose") is not None and gegen.classify(rows[d + shift]["close"], days_y[d]["adjclose"], []) == "gleich"
                   and gegen.classify(rows[d + shift]["close"], days_y[d]["close"], []) != "gleich")
    result["bereinigung"] = "dividendenbereinigt" if adjusted >= 3 else ("faktor" if any(gegen.classify(own[d], rows[d + shift]["close"], []) == "faktor" for d in common) else "wie_stand")
    result["ohne_umsatz_quelle"] = sum(1 for d in common if rows[d + shift].get("volume") == 0)
    # Tage nur im Stand: an wie vielen davon meldet Yahoo keinen Umsatz (kein Handel – die Quelle führt den Tag dann nicht)
    result["nur_im_stand_ohne_umsatz"] = sum(1 for d in own if (d + shift) not in rows and (days_y.get(d) or {}).get("volume") == 0)
    result["gleiche_tage"] = equal
    reasons = []
    if result["identitaet"] in ("isin_anders", "cusip_anders", "name_passt_nicht"):
        reasons.append("identitaet")
    if result["handelsplatz"] == "anders":
        reasons.append("handelsplatz")
    if result["waehrung"] == "anders" or result["waehrung_yahoo"] == "anders":
        reasons.append("waehrung")
    if result["kursniveau"] != "passt":
        reasons.append("kursniveau")
    if result["bereinigung"] == "dividendenbereinigt":
        reasons.append("bereinigung")
    if len(common) < MIN_DAYS:
        reasons.append("zu_wenige_tage")
    result["vergleichbar"] = not reasons
    result["grund"] = ",".join(reasons) if reasons else ""
    return result


def source_unit(values) -> float | None:
    """Gröbste Kursstufe, auf der alle Kurse einer Quelle liegen (0,01, 0,001 oder 0,0001 $) – ihre Anzeigegenauigkeit.
    Zeigt eine Quelle Kurse unter 1 $ nur mit drei Nachkommastellen, liegt der Kurs des Stands (vier Stellen) oft eine
    Viertelstelle daneben: das ist Rundung der Quelle, keine andere Kursangabe."""
    found = [float(v) for v in values if v]
    if not found:
        return None
    for unit in (0.01, 0.001, 0.0001):
        if all(abs(v / unit - round(v / unit)) <= 0.02 for v in found):
            return unit
    return None


def compare(own: dict[int, float], rows: dict[int, dict], shift: int, yahoo: dict, within_display) -> dict[int, tuple[str, float, str]]:
    """Jeder gemeinsame Tag: (Art, Kurs der Quelle, Ursache). Art wie bei Nasdaq (gleich, klein, gross, nachbartag, faktor);
    Ursache nur mit Beleg: Kursstufe (``within_display`` – dieselbe Regel wie bei Nasdaq), kein Umsatz mit dem Kurs des
    Vortags, Faktor eines Splits – sonst „ungeklaert“."""
    out: dict[int, tuple[str, float, str]] = {}
    ordered = sorted(d for d in own if (d + shift) in rows)
    days_y = yahoo.get("days") or {}
    unit = source_unit(r["close"] for r in rows.values())
    for k, d in enumerate(ordered):
        alt = rows[d + shift]["close"]
        neighbours = [rows[ordered[j] + shift]["close"] for j in (k - 1, k + 1) if 0 <= j < len(ordered)]
        kind = gegen.classify(own[d], alt, neighbours)
        if kind == "gleich":
            out[d] = (kind, alt, "")
            continue
        previous_own = own[ordered[k - 1]] if k > 0 else None
        previous_alt = rows[ordered[k - 1] + shift]["close"] if k > 0 else None
        if kind == "faktor":
            cause = "split"
        elif within_display(own[d], alt):
            cause = "rundung"
        elif unit is not None and unit > 0.0001 and abs(own[d] - alt) <= unit / 2 + 1e-9:
            cause = "rundung"  # Quelle zeigt weniger Nachkommastellen: der Kurs des Stands, so gerundet, ist ihr Kurs
        elif previous_own is not None and own[d] == previous_own and (days_y.get(d) or {}).get("volume") == 0:
            cause = "kein_handel"
        elif previous_alt is not None and alt == previous_alt and rows[d + shift].get("volume") == 0:
            cause = "kein_handel"
        else:
            cause = "ungeklaert"
        out[d] = (kind, alt, cause)
    return out


def pattern(own: float, alt: float, yahoo_volume, source_volume, unit: float | None) -> list[str]:
    """Anonymes Muster eines abweichenden Tags gegen eine Zusatzquelle: Umsatz beider Quellen, Abstand in Kursstufen der
    Quelle, Richtung – ohne Kurse."""
    step = unit or (0.01 if alt >= 1 else 0.0001)
    ticks = abs(own - alt) / step
    size = "1" if ticks < 1.5 else ("2" if ticks < 2.5 else ("3–10" if ticks < 10.5 else "über 10"))
    return [
        "yahoo_ohne_umsatz" if yahoo_volume == 0 else ("yahoo_mit_umsatz" if yahoo_volume else "yahoo_umsatz_fehlt"),
        "quelle_ohne_umsatz" if source_volume == 0 else ("quelle_mit_umsatz" if source_volume else "quelle_umsatz_fehlt"),
        f"stufen_{size}",
        "stand_hoeher" if own > alt else "stand_niedriger",
        f"stufe_der_quelle_{unit}" if unit else "stufe_der_quelle_gemischt",
    ]


def summary_counts(checks: list[dict]) -> Counter:
    """Zählwerte der Prüfungen aller Quellen (ohne Kurse und Namen) für das Protokoll."""
    counts: Counter = Counter()
    for c in checks:
        q = c["quelle"]
        for kind, status in (c.get("status") or {}).items():
            counts[f"{q}_{kind}_{status}"] += 1  # Ergebnis jedes Abrufs (z. B. otc_markets_historie_http_404)
        if not c.get("identitaet"):
            counts[f"{q}_{c['grund']}"] += 1
            continue
        counts[f"{q}_mit_kursen"] += 1
        for name in ("identitaet", "handelsplatz", "waehrung", "kursniveau", "bereinigung"):
            counts[f"{q}_{name}_{c[name]}"] += 1
        if c.get("datum_versatz"):
            counts[f"{q}_datum_versatz_{c['datum_versatz']:+d}"] += 1
        counts[f"{q}_{'vergleichbar' if c['vergleichbar'] else 'nicht_vergleichbar'}"] += 1
        for reason in filter(None, (c.get("grund") or "").split(",")):
            counts[f"{q}_grund_{reason}"] += 1
    return counts
