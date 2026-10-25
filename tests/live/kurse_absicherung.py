"""Absicherung der Zuordnung eines Vergleichskurses (seit dem 25.10.2026, Prüfskript; App unverändert).

Simons Auftrag vom 25.10.2026, 09:20 Uhr, Punkt 3: „Prüfe Aktie beziehungsweise Aktiengattung, Notierung, Handelsplatz, Währung,
Handelstag und Bereinigung. Ein passendes Kürzel oder ähnliches Kursniveau allein reicht nicht. Fehlende Angaben dürfen nicht
automatisch als bestandene Prüfung gelten. Beschaffe ergänzende Belege; andernfalls kennzeichne den Vergleich als nicht
ausreichend abgesichert und übernimm ihn nicht als bestätigten Ersatzkurs.“

Belege je Vergleich (jede Prüfung einzeln, ohne Namen und Kürzel im Protokoll):

* **Aktie und Gattung:** ISIN des Stands → Notierungen laut OpenFIGI (Identitätsanbieter, im Prüfjob live abgefragt): das
  Kürzel, mit dem die Quelle abgefragt wird, gehört zu dieser ISIN an einer Börse derselben Gruppe (USA, OTC, sonst dieselbe
  Börse). Jede Gattung hat eine eigene ISIN – damit ist auch die Gattung belegt. Namen sind nur ein Hinweis
  (``traktien.util.names``); geprüft wird zusätzlich, dass der Name der Quelle (Wertpapierliste von Nasdaq Trader,
  Kursmeldung von CNBC) zum Namen im Stand passt, und dass die Quelle kein Fonds, Optionsschein oder Testwert ist.
* **Notierung und Handelsplatz:** Börse laut Quelle (Nasdaq Trader „Listing Exchange“, CNBC „exchange“) = Börse der Kurse des
  Stands (Yahoo „exchangeName“). Die Börsencodes von OpenFIGI belegen die Heimatbörse nicht: OpenFIGI führt eine US-Aktie
  an jeder US-Börse, an der sie gehandelt wird – sie belegen nur, dass das Kürzel zur ISIN gehört.
* **Wertpapierliste:** „nasdaqtraded.txt“ von Nasdaq Trader (alle an US-Börsen gehandelten Wertpapiere mit Name, Börse der
  Notierung, Fonds, Testwert); ist sie nicht abrufbar, ersatzweise die Aktienliste von nasdaq.com (je Börse eine Anfrage,
  ohne Angabe von Fonds und Testwerten – gezählt).
* **Währung:** von der Quelle angegeben und gleich der des Stands (Untereinheiten wie GBp umgerechnet).
* **Handelstag:** Kursfolge ohne Versatz der Tage (−1, 0, +1 geprüft).
* **Bereinigung:** kein dividendenbereinigter Vergleichskurs; ein konstanter Faktor nur mit gemeldetem Split passenden
  Verhältnisses nach dem Tag (dann wird um den Split bereinigt verglichen).

Fehlt eine Angabe oder widerspricht sie, ist der Vergleich **nicht ausreichend abgesichert**: Er wird gezählt, liefert aber
weder Ersatzkurse noch bestätigte Übereinstimmungen.
"""

from __future__ import annotations

import os
import re
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "backend"))

import kurse_gegenpruefen as gegen  # noqa: E402 - Toleranz und Einordnung eines Kurses
import kurse_zusatzquellen as zusatz  # noqa: E402 - Versatz der Tage, Namensprüfung
from traktien.providers.exchanges import load_exchange_table, unit_info  # noqa: E402 - Börsentabelle der App (OpenFIGI-Codes)
from traktien.util.names import name_similarity  # noqa: E402

NASDAQ_TRADED = "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqtraded.txt"
LISTING_HOST = "www.nasdaqtrader.com"
# Ersatz, falls die Wertpapierliste nicht abrufbar ist: Aktienliste von nasdaq.com je Börse (drei Anfragen an api.nasdaq.com)
NASDAQ_SCREENER = "https://api.nasdaq.com/api/screener/stocks?tableonly=true&limit=10000&offset=0&exchange={exchange}&download=true"
SCREENER_EXCHANGES = {"nasdaq": "nasdaq", "nyse": "nyse", "amex": "nyse_american"}
LISTING_OK = {"ok", "ok_ersatz"}
# „Listing Exchange“ der Wertpapierliste von Nasdaq Trader (Symbol Directory, Feldbeschreibung auf nasdaqtrader.com)
US_LISTING = {"Q": "nasdaq", "N": "nyse", "A": "nyse_american", "P": "nyse_arca", "Z": "cboe_bzx", "V": "iex"}
YAHOO_LISTING = {"NMS": "nasdaq", "NGM": "nasdaq", "NCM": "nasdaq", "NAS": "nasdaq", "NYQ": "nyse", "NYS": "nyse", "ASE": "nyse_american", "PCX": "nyse_arca", "BTS": "cboe_bzx"}
US_FAMILY = {"US", "XNYS", "XNAS", "XASE", "ARCX", "BATS"}
OTC_FAMILY = {"OTC"}
CONFIRMED = {"isin_kuerzel_bestaetigt"}
NAME_CONFIRMED = 0.5
# Art eines Wertpapiers: Fonds, ETF, ETN irgendwo im Namen; Optionsschein, Bezugsrecht, Einheit (SPAC), Anleihe in der
# Beschreibung hinter dem Namen des Emittenten („- Warrants“, „Units“) – „Common Units“ einer Kommanditgesellschaft sind Anteile
NOT_EQUITY_NAME = re.compile(r"\b(etfs?|etns?|fund)\b", re.IGNORECASE)
NOT_EQUITY = re.compile(r"\b(warrants?|rights?|(?<!common )units?|notes due|debentures?|subscription receipts?)\b", re.IGNORECASE)
# Beschreibung des Wertpapiers hinter dem Namen des Emittenten („Apple Inc. - Common Stock“, „Coca-Cola Company (The) Common
# Stock“, „Alphabet Inc. Class A Common Stock“) – für die Namensprüfung abgeschnitten
DESCRIPTOR = re.compile(
    r"(?<=\S)[\s,\-–]+(?:class\s+[a-z0-9]\b|series\s+[a-z0-9]\b|common\s+stock|common\s+shares?|common\s+units?|capital\s+stock|ordinary\s+shares?|"
    r"american\s+depositary|american\s+depository|depositary\s+shares|depositary\s+receipts?|depository\s+receipts?|sponsored\s+adr|unsponsored\s+adr|"
    r"ads\b|adr\b|shares\s+of\s+beneficial|beneficial\s+interest|each\s+representing|subordinate\s+voting|limited\s+voting|voting\s+shares|"
    r"new\s+common|partnership\s+units?|limited\s+partnership|preferred\s+stock|warrants?\b|units?\b|rights?\b)\b.*$",
    re.IGNORECASE,
)
LEVEL_TOLERANCE = 0.02
MIN_DAYS = 10
FIGI_CHUNK = 100  # ISINs je Block bei OpenFIGI (ein gescheiterter Block betrifft nur seine ISINs)
CHECK_TEXT = {
    "aktie": "Aktie und Gattung (ISIN → Kürzel laut OpenFIGI)",
    "name": "Name der Quelle passt zum Stand (nur Hinweis)",
    "art": "kein Fonds, Optionsschein oder Testwert",
    "handelsplatz": "Börse der Quelle = Börse der Kurse des Stands",
    "waehrung": "Währung angegeben und gleich",
    "handelstag": "Handelstag ohne Versatz",
    "bereinigung": "Bereinigung wie im Stand",
    "kursniveau": "Kursniveau",
    "tage": f"mindestens {MIN_DAYS} gemeinsame Tage",
}


def normalize(symbol: str | None) -> str:
    """Kürzel ohne Unterschied der Schreibweise der Gattung: „BRK.B“, „BRK/B“, „BRK^B“, „BRK=B“ → „BRK-B“."""
    return re.sub(r"[./^= ]", "-", (symbol or "").strip().upper())


def issuer_name(security_name: str | None) -> str:
    """Name des Emittenten ohne die Beschreibung des Wertpapiers: „Apple Inc. - Common Stock“ → „Apple Inc.“."""
    text = (security_name or "").strip()
    if " - " in text:
        text = text.split(" - ", 1)[0]
    text = DESCRIPTOR.sub("", text).strip(" ,-–")
    return text or (security_name or "").strip()


def parse_listing(text: str) -> dict[str, dict]:
    """Wertpapierliste von Nasdaq Trader („nasdaqtraded.txt“, Trennzeichen „|“): je Kürzel (Symbol, CQS- und Nasdaq-Schreibweise)
    Name, Börse der Notierung, Fonds und Testwert. Die letzte Zeile („File Creation Time“) hat zu wenige Felder."""
    lines = [line for line in (text or "").splitlines() if line.strip()]
    if not lines or "|" not in lines[0]:
        return {}
    header = [h.strip() for h in lines[0].split("|")]
    idx = {name: k for k, name in enumerate(header)}
    needed = ("Symbol", "Security Name", "Listing Exchange")
    if any(name not in idx for name in needed):
        return {}
    out: dict[str, dict] = {}
    for line in lines[1:]:
        parts = line.split("|")
        if len(parts) < len(header):
            continue
        field = lambda name: parts[idx[name]].strip() if name in idx else ""  # noqa: E731
        row = {
            "name": field("Security Name"),
            "boerse": US_LISTING.get(field("Listing Exchange"), "unbekannt"),
            "fonds": field("ETF") == "Y",
            "test": field("Test Issue") == "Y",
        }
        for key in ("Symbol", "CQS Symbol", "NASDAQ Symbol"):
            if field(key):
                out.setdefault(normalize(field(key)), row)
    return out


def parse_screener(payload, venue: str) -> dict[str, dict]:
    """Aktienliste von nasdaq.com („download=true“): je Kürzel Name und Börse (die der Anfrage) – ohne Fonds- und Testkennzeichen."""
    rows = (((payload or {}).get("data") or {}).get("rows")) or [] if isinstance(payload, dict) else []
    out: dict[str, dict] = {}
    for row in rows:
        if not isinstance(row, dict) or not row.get("symbol"):
            continue
        out.setdefault(normalize(str(row["symbol"])), {"name": str(row.get("name") or ""), "boerse": venue, "fonds": False, "test": False})
    return out


def fetch_listing(http) -> tuple[str, dict[str, dict]]:
    """Wertpapierliste von Nasdaq Trader (ein Abruf je Job, anderer Rechner als api.nasdaq.com – nicht im Kontingent); ist sie
    nicht abrufbar, die Aktienliste von nasdaq.com je Börse (Status „ok_ersatz“). Ohne beide: Status des Fehlers, leere Liste –
    dann ist kein Vergleich mit Nasdaq abgesichert."""
    status = "nicht_abgefragt"
    for attempt in range(2):
        try:
            response = http.get(NASDAQ_TRADED, headers={"Accept": "text/plain, */*"})
        except Exception as exc:  # noqa: BLE001 - Netz: nur zählen
            status = f"fehler_{type(exc).__name__}"
            continue
        if response.status_code != 200:
            status = f"http_{response.status_code}"
            continue
        content = getattr(response, "content", None)
        text = content.decode("utf-8", "replace") if isinstance(content, (bytes, bytearray)) else str(getattr(response, "text", "") or "")
        listing = parse_listing(text)
        if listing:
            return "ok", listing
        status = "leer"
    merged: dict[str, dict] = {}
    for exchange, venue in SCREENER_EXCHANGES.items():
        try:
            response = http.get(NASDAQ_SCREENER.format(exchange=exchange), headers=gegen.HEADERS)
            payload = response.json() if response.status_code == 200 else None
        except Exception:  # noqa: BLE001 - Netz oder kein JSON: diese Börse fehlt
            payload = None
        for key, row in parse_screener(payload, venue).items():
            merged.setdefault(key, row)
    return ("ok_ersatz", merged) if merged else (status, {})


def figi_lookup(isins: list[str], client=None) -> dict[str, dict]:
    """ISIN → Notierungen laut OpenFIGI (Börsenschlüssel der App und Yahoo-Kürzel, wie die App sie bildet). Ohne Antwort
    „nicht_geprueft“ – das gilt nie als bestanden."""
    from traktien.providers.base import ProviderError
    from traktien.providers.openfigi import OpenFigiClient, candidates_from_figi

    table = load_exchange_table()
    out: dict[str, dict] = {}
    if not isins:
        return out
    answers: dict[str, dict] = {}
    try:
        client = client or OpenFigiClient(api_key=os.environ.get("OPENFIGI_API_KEY") or None)
    except (ProviderError, Exception) as exc:  # noqa: BLE001 - ohne Client: nichts gilt als bestanden
        return {isin: {"status": f"fehler_{type(exc).__name__}", "kandidaten": []} for isin in isins}
    # in Blöcken: scheitert ein Block (nach den Wiederholungen des HTTP-Clients), gelten nur seine ISINs als nicht geprüft
    for k in range(0, len(isins), FIGI_CHUNK):
        chunk = isins[k : k + FIGI_CHUNK]
        try:
            answers.update(client.map_isins(chunk))
        except (ProviderError, Exception) as exc:  # noqa: BLE001 - Netz oder Grenze: nur zählen, nichts gilt als bestanden
            for isin in chunk:
                out[isin] = {"status": f"fehler_{type(exc).__name__}", "kandidaten": []}
    for isin in isins:
        if isin in out:
            continue
        item = answers.get(isin) or {}
        if item.get("error"):
            out[isin] = {"status": "fehler_antwort", "kandidaten": []}
            continue
        candidates = [
            {"boerse": c.exchange_key, "symbol": c.provider_symbol, "code": c.exch_code, "typ": c.security_type, "typ2": c.security_type2}
            for c in candidates_from_figi(isin, item, table)
        ]
        out[isin] = {"status": "ok" if candidates else "keine_zuordnung", "kandidaten": candidates}
    return out


def family_of(exchange_key: str | None) -> set[str]:
    """Börsen, an denen dieselbe Notierung des Stands gehandelt wird: USA zusammengefasst, OTC (mit USA – Yahoo führt manche
    US-Notierung des Stands als OTC), sonst genau die Börse."""
    key = exchange_key or ""
    if key in US_FAMILY or key in OTC_FAMILY:
        return US_FAMILY | OTC_FAMILY
    return {key} if key else set()


def figi_identity(entry: dict | None, symbol: str, exchange_key: str | None) -> str:
    """Gehört das abgefragte Kürzel laut OpenFIGI zur ISIN des Stands (an einer Börse derselben Gruppe)?"""
    if not entry or entry.get("status") != "ok":
        return "nicht_geprueft" if not entry or str(entry.get("status", "")).startswith("fehler") else "isin_ohne_zuordnung"
    family = family_of(exchange_key)
    mine = [c for c in entry["kandidaten"] if c["boerse"] in family]
    if not mine:
        return "isin_ohne_notierung_der_boerse"
    target = normalize(symbol)
    if any(normalize(c["symbol"]) == target for c in mine):
        return "isin_kuerzel_bestaetigt"
    return "isin_anderes_kuerzel"


def name_check(source_name: str | None, names: list[str]) -> str:
    """Name der Quelle gegen die Namen des Stands (Ähnlichkeit wie bei der Identitätsprüfung der App, mindestens 0,5) – der Name
    der Quelle ohne die Beschreibung des Wertpapiers („Common Stock“, „Class A“ …)."""
    if not source_name:
        return "nicht_angegeben"
    candidates = {source_name, issuer_name(source_name)}
    best = max((name_similarity(c, n) for c in candidates for n in names if n), default=0.0)
    return "bestaetigt" if best >= NAME_CONFIRMED else "passt_nicht"


def not_equity(name: str | None) -> bool:
    """Name eines Fonds (ETF, ETN, „Fund“) oder Beschreibung eines Optionsscheins, Bezugsrechts, einer Einheit oder Anleihe hinter
    dem Namen des Emittenten (ganze Wörter – „United“ ist kein „Unit“, „Rights Holding Co.“ kein Bezugsrecht)."""
    text = (name or "").strip()
    issuer = issuer_name(text)
    descriptor = text[len(issuer):] if issuer and text.startswith(issuer) else text
    return bool(NOT_EQUITY_NAME.search(text) or NOT_EQUITY.search(descriptor))


def adjustment(own: dict[int, float], rows: dict[int, dict], yahoo: dict, splits: list[tuple[int, float]], cutoff: int, shift: int = 0) -> str:
    """Bereinigung der Quelle gegen den Stand: „dividendenbereinigt“ (gleich dem dividendenbereinigten Yahoo-Kurs an mindestens
    3 Tagen, an denen er vom unbereinigten abweicht), „faktor_ohne_split“ (konstanter Faktor ohne gemeldeten Split),
    „split_gemeldet“ (Faktor = gemeldeter Split) oder „wie_stand“."""
    days_y = (yahoo or {}).get("days") or {}
    common = [d for d in own if (d + shift) in rows]
    dividend = sum(
        1 for d in common
        if (days_y.get(d) or {}).get("adjclose") is not None and gegen.classify(rows[d + shift]["close"], days_y[d]["adjclose"], []) == "gleich"
        and gegen.classify(rows[d + shift]["close"], days_y[d]["close"], []) != "gleich"
    )
    if dividend >= 3:
        return "dividendenbereinigt"
    factor_days = [d for d in common if gegen.classify(own[d], rows[d + shift]["close"], []) == "faktor"]
    if not factor_days:
        return "wie_stand"
    if all(zusatz.adjusted_equal(own[d], rows[d + shift]["close"], zusatz.split_factor(d, splits, cutoff)) for d in factor_days):
        return "split_gemeldet"
    return "faktor_ohne_split"


def level_check(own: dict[int, float], rows: dict[int, dict], shift: int = 0, splits: list[tuple[int, float]] | None = None, cutoff: int | None = None) -> str:
    """Mittleres Kursniveau Stand/Quelle innerhalb von 2 %. An Tagen vor einem gemeldeten Split wird ein unbereinigter Kurs der
    Quelle um den Split bereinigt, wenn er damit dem Stand näher kommt (sonst zählte ein Split im Zeitraum als anderes Niveau)."""
    ratios = []
    for d in own:
        row = rows.get(d + shift)
        if not row or not row.get("close"):
            continue
        raw = row["close"]
        factor = zusatz.split_factor(d, splits, cutoff)
        value = raw
        if factor != 1.0 and abs(own[d] / (raw / factor) - 1) < abs(own[d] / raw - 1):
            value = raw / factor
        ratios.append(own[d] / value)
    if not ratios:
        return "ohne_gemeinsame_tage"
    return "passt" if abs(statistics.median(ratios) - 1) <= LEVEL_TOLERANCE else "passt_nicht"


def verdict(checks: dict) -> tuple[bool, str]:
    """Abgesichert nur, wenn jede Prüfung bestanden ist – fehlende Angaben sind nicht bestanden."""
    passed = {
        "aktie": checks.get("aktie") in CONFIRMED,
        "name": checks.get("name") == "bestaetigt",
        "art": checks.get("art") == "aktie",
        "handelsplatz": checks.get("handelsplatz") == "gleich",
        "waehrung": checks.get("waehrung") == "gleich",
        "handelstag": checks.get("handelstag") == "gleich",
        "bereinigung": checks.get("bereinigung") in ("wie_stand", "split_gemeldet"),
        "kursniveau": checks.get("kursniveau") == "passt",
        "tage": checks.get("tage") == "genug",
    }
    failed = [name for name in passed if not passed[name]]
    return not failed, ",".join(failed)


def secure_nasdaq(listing: dict[str, dict], listing_status: str, figi: dict | None, symbol: str, meta: dict, yahoo: dict, own: dict[int, float],
                  rows: dict[int, dict], dollar: bool, cutoff: int, official: bool = False, source_symbol: str | None = None) -> dict:
    """Prüfungen eines Vergleichs mit Nasdaq (Historie bzw. offizieller Schlusskurs, ``official``): Ergebnis je Prüfung,
    „abgesichert“ und der Grund. ``symbol``: Kürzel des Stands (Yahoo), ``source_symbol``: Schreibweise, mit der Nasdaq abgefragt
    wurde. ``meta``: Angaben des Stands (ISIN, Namen, Währung, Einheit, Börsenschlüssel)."""
    row = listing.get(normalize(source_symbol or symbol)) if listing else None
    checks: dict = {"quelle": "nocp" if official else "nasdaq"}
    checks["aktie"] = figi_identity(figi, symbol, meta.get("boerse"))
    if listing_status not in LISTING_OK:
        checks["name"] = checks["art"] = "wertpapierliste_nicht_abrufbar"
    elif row is None:
        checks["name"] = checks["art"] = "nicht_in_wertpapierliste"
    else:
        checks["name"] = name_check(row["name"], meta.get("namen") or [])
        # Art aus dem vollständigen Namen: die Beschreibung des Wertpapiers („- Warrants“, „- Units“) nennt die Art
        checks["art"] = "kein_aktieninstrument" if row["fonds"] or row["test"] or not_equity(row["name"]) else "aktie"
    source_venue = row["boerse"] if row else None
    yahoo_venue = YAHOO_LISTING.get((yahoo or {}).get("exchange") or "")
    if not source_venue or source_venue == "unbekannt" or not yahoo_venue:
        checks["handelsplatz"] = "nicht_angegeben"
    elif source_venue != yahoo_venue:
        checks["handelsplatz"] = "anders"
    elif official and source_venue != "nasdaq":
        checks["handelsplatz"] = "nocp_nur_fuer_nasdaq"
    else:
        checks["handelsplatz"] = "gleich"
    base, _ = unit_info(meta.get("einheit") or meta.get("waehrung"))
    yahoo_currency = ((yahoo or {}).get("currency") or "").upper()
    if not dollar:
        checks["waehrung"] = "nicht_angegeben"
    elif (base or "").upper() != "USD" or (meta.get("waehrung") or "").upper() != "USD" or (yahoo_currency and yahoo_currency != "USD"):
        checks["waehrung"] = "anders"
    else:
        checks["waehrung"] = "gleich"
    splits = (yahoo or {}).get("splits") or []
    shift, _ = zusatz.best_shift(own, rows)
    checks["handelstag"] = "gleich" if shift == 0 else f"versatz_{shift:+d}"
    checks["bereinigung"] = adjustment(own, rows, yahoo, splits, cutoff)
    checks["kursniveau"] = level_check(own, rows, 0, splits, cutoff)
    checks["tage"] = "genug" if sum(1 for d in own if d in rows) >= MIN_DAYS else "zu_wenige"
    ok, reason = verdict(checks)
    checks["abgesichert"], checks["grund"] = ok, reason
    return checks


def strict_source(result: dict, fetched: dict, own: dict[int, float], yahoo: dict, figi: dict | None, symbol: str, exchange_key: str | None, cutoff: int) -> dict:
    """Strenge Prüfung einer Zusatzquelle (CNBC u. a.) nach ``kurse_zusatzquellen.check``: Aktie über die ISIN (OpenFIGI) oder
    eine ISIN/CUSIP der Quelle, Name der Quelle, Art, Handelsplatz, Währung, Handelstag ohne Versatz, Bereinigung, Kursniveau und
    Tage müssen bestätigt sein – „nur Kürzel“, „nicht angegeben“, ein ähnlicher Name oder ein Versatz der Tage reichen nicht."""
    checks: dict = {"quelle": result.get("quelle")}
    rows = (fetched or {}).get("rows") or {}
    if not rows or "identitaet" not in result:
        checks.update(abgesichert=False, grund=result.get("grund") or "keine_kurse")
        return checks
    source_name = ((fetched or {}).get("meta") or {}).get("name")
    identity = result.get("identitaet")
    checks["aktie"] = figi_identity(figi, symbol, exchange_key)
    if identity in ("isin_bestaetigt", "cusip_bestaetigt"):
        checks["aktie"] = "isin_kuerzel_bestaetigt"  # die Quelle nennt selbst ISIN bzw. CUSIP des Stands
    elif identity in ("isin_anders", "cusip_anders"):
        checks["aktie"] = identity
    checks["name"] = {"name_bestaetigt": "bestaetigt", "isin_bestaetigt": "bestaetigt", "cusip_bestaetigt": "bestaetigt", "nur_kuerzel": "nicht_angegeben",
                      "name_aehnlich": "nur_aehnlich"}.get(identity, "passt_nicht")
    checks["art"] = "kein_aktieninstrument" if not_equity(source_name) else ("aktie" if source_name else "nicht_angegeben")
    checks["handelsplatz"] = result.get("handelsplatz") or "nicht_angegeben"
    checks["waehrung"] = "anders" if result.get("waehrung_yahoo") == "anders" else (result.get("waehrung") or "nicht_angegeben")
    shift = int(result.get("datum_versatz") or 0)
    checks["handelstag"] = "gleich" if shift == 0 else f"versatz_{shift:+d}"
    splits = (yahoo or {}).get("splits") or []
    checks["bereinigung"] = adjustment(own, rows, yahoo, splits, cutoff, shift)
    checks["kursniveau"] = level_check(own, rows, shift, splits, cutoff)
    checks["tage"] = "genug" if int(result.get("gemeinsame_tage") or 0) >= MIN_DAYS else "zu_wenige"
    ok, reason = verdict(checks)
    checks["abgesichert"], checks["grund"] = ok, reason
    return checks


def summary(checks: list[dict]) -> dict[str, int]:
    """Zählwerte je Quelle und Prüfung (ohne Namen und Kürzel): „<quelle>_<prüfung>_<ergebnis>“ und „<quelle>_abgesichert“."""
    from collections import Counter

    out: Counter = Counter()
    for c in checks:
        q = c.get("quelle") or "quelle"
        out[f"{q}_{'abgesichert' if c.get('abgesichert') else 'nicht_abgesichert'}"] += 1
        for name in CHECK_TEXT:
            if name in c:
                out[f"{q}_{name}_{c[name]}"] += 1
        for reason in (c.get("grund") or "").split(","):
            if reason and not c.get("abgesichert"):
                out[f"{q}_grund_{reason}"] += 1
    return dict(out)
