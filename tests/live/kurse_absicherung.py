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
# Bestätigt: das abgefragte Kürzel ist eines der Kürzel, die OpenFIGI für die ISIN an einer Börse derselben Gruppe nennt –
# in der Schreibweise der App (``ExchangeTable.yahoo_symbol``) oder in einer ihrer dokumentierten anderen Schreibweisen
# (``ExchangeTable.symbol_variants``: nordische Gattungen „ADDTB“ → „ADDT-B.ST“). Bis zum Lauf 40181869022 galt nur die erste
# – vier Stockholmer Aktien mit Gattung im Kürzel waren dadurch zu Unrecht nicht abgesichert.
CONFIRMED = {"isin_kuerzel_bestaetigt", "isin_kuerzel_bestaetigt_schreibweise"}
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
    # eine Pflichtprüfung wie alle anderen (bis zum Lauf 40181869022 fälschlich „nur Hinweis“ beschriftet – gezählt wurde sie
    # schon damals als Pflicht, siehe ``verdict``)
    "name": "Name der Quelle passt zum Stand",
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


def isin_valid(isin: str | None) -> bool:
    """Form und Prüfziffer einer ISIN (ISO 6166): zwei Buchstaben, neun Zeichen, eine Ziffer; Buchstaben als Zahlen 10–35, dann
    das Luhn-Verfahren über alle Ziffern („US0378331005“ gültig). Für den Befund bei „ISIN bei OpenFIGI unbekannt“."""
    text = (isin or "").strip().upper()
    if not re.fullmatch(r"[A-Z]{2}[A-Z0-9]{9}[0-9]", text):
        return False
    digits = "".join(str(int(ch, 36)) for ch in text)
    total = 0
    for k, ch in enumerate(reversed(digits)):
        n = int(ch) * (2 if k % 2 else 1)
        total += n - 9 if n > 9 else n
    return total % 10 == 0


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
        candidates = []
        for c in candidates_from_figi(isin, item, table):
            exchange = table.exchanges.get(c.exchange_key)
            variants = table.symbol_variants(exchange, c.provider_symbol) if exchange is not None else []
            candidates.append({"boerse": c.exchange_key, "symbol": c.provider_symbol, "varianten": variants, "code": c.exch_code, "typ": c.security_type,
                               "typ2": c.security_type2})
        if candidates:
            status = "ok"
        elif item.get("warning") and not item.get("data"):
            status = "isin_unbekannt"  # OpenFIGI: „No identifier found“ – die ISIN ist dort nicht bekannt
        else:
            status = "keine_zuordnung"  # Datensätze, aber keiner an einer Börse der Tabelle der App
        records = [r for r in item.get("data") or [] if isinstance(r, dict)]
        # Befund ohne Namen und Kürzel (seit dem 25.10.2026, 11:45 Uhr): Form/Prüfziffer und Land der ISIN, Börsencodes und Sektoren
        # der Datensätze von OpenFIGI – damit ist eine nicht bestandene Prüfung „Aktie und Gattung“ im Protokoll begründet
        out[isin] = {"status": status, "kandidaten": candidates, "pruefziffer": "gueltig" if isin_valid(isin) else "ungueltig", "land": isin[:2].upper(),
                     "boersencodes": sorted({str(r.get("exchCode") or "–") for r in records})[:12],
                     "sektoren": sorted({str(r.get("marketSector") or "–") for r in records})[:6]}
    return out


def family_of(exchange_key: str | None) -> set[str]:
    """Börsen, an denen dieselbe Notierung des Stands gehandelt wird: USA zusammengefasst, OTC (mit USA – Yahoo führt manche
    US-Notierung des Stands als OTC), sonst genau die Börse."""
    key = exchange_key or ""
    if key in US_FAMILY or key in OTC_FAMILY:
        return US_FAMILY | OTC_FAMILY
    return {key} if key else set()


def figi_identity(entry: dict | None, symbol: str, exchange_key: str | None) -> str:
    """Gehört das abgefragte Kürzel laut OpenFIGI zur ISIN des Stands (an einer Börse derselben Gruppe)? Verglichen wird mit dem
    Kürzel in der Schreibweise der App und mit ihren dokumentierten anderen Schreibweisen (nordische Gattungen) – „…_schreibweise“."""
    if not entry or entry.get("status") != "ok":
        if not entry or str(entry.get("status", "")).startswith("fehler"):
            return "nicht_geprueft"
        return "isin_unbekannt" if entry.get("status") == "isin_unbekannt" else "isin_ohne_zuordnung"
    family = family_of(exchange_key)
    mine = [c for c in entry["kandidaten"] if c["boerse"] in family]
    if not mine:
        return "isin_ohne_notierung_der_boerse"
    target = normalize(symbol)
    if any(normalize(c["symbol"]) == target for c in mine):
        return "isin_kuerzel_bestaetigt"
    if any(normalize(v) == target for c in mine for v in c.get("varianten") or []):
        return "isin_kuerzel_bestaetigt_schreibweise"
    return "isin_anderes_kuerzel"


def name_score(source_name: str | None, names: list[str]) -> float | None:
    """Größte Ähnlichkeit des Namens der Quelle (auch ohne die Beschreibung des Wertpapiers) mit einem Namen des Stands; ohne
    Namen None."""
    if not source_name:
        return None
    candidates = {source_name, issuer_name(source_name)}
    return max((name_similarity(c, n) for c in candidates for n in names if n), default=0.0)


def name_check(source_name: str | None, names: list[str]) -> str:
    """Name der Quelle gegen die Namen des Stands (Ähnlichkeit wie bei der Identitätsprüfung der App, mindestens 0,5) – der Name
    der Quelle ohne die Beschreibung des Wertpapiers („Common Stock“, „Class A“ …)."""
    best = name_score(source_name, names)
    if best is None:
        return "nicht_angegeben"
    return "bestaetigt" if best >= NAME_CONFIRMED else "passt_nicht"


def figi_detail(entry: dict | None, exchange_key: str | None) -> str:
    """Befund zu einer nicht bestandenen Prüfung „Aktie und Gattung“ – nur Codes, keine Namen, Kürzel oder ISIN."""
    if not entry or str(entry.get("status", "")).startswith("fehler"):
        return "OpenFIGI ohne Antwort"
    form = f"Prüfziffer der ISIN {'gültig' if entry.get('pruefziffer') == 'gueltig' else 'ungültig'}, Land {entry.get('land') or '–'}"
    if entry.get("status") == "isin_unbekannt":
        return f"ISIN bei OpenFIGI unbekannt ({form})"
    codes = ", ".join(entry.get("boersencodes") or []) or "–"
    if entry.get("status") != "ok":
        return f"OpenFIGI nennt die ISIN nur mit Börsencodes {codes} (Sektor {', '.join(entry.get('sektoren') or []) or '–'}) – keiner an einer Börse der App ({form})"
    family = family_of(exchange_key)
    mine = sorted({c["boerse"] for c in entry.get("kandidaten") or [] if c["boerse"] in family})
    if not mine:
        others = ", ".join(sorted({c["boerse"] for c in entry.get("kandidaten") or []})) or "–"
        return f"OpenFIGI nennt die ISIN nur an {others}, nicht an {exchange_key or '–'} ({form})"
    return f"OpenFIGI nennt für die ISIN an {', '.join(mine)} ein anderes Kürzel ({form})"


def failure_details(checks: dict, figi: dict | None = None, exchange_key: str | None = None) -> str:
    """Befund je nicht bestandener Prüfung (seit dem 25.10.2026, 11:45 Uhr) – Codes und Zahlen, keine Namen oder Kürzel: warum die
    Zuordnung nicht ausreichend abgesichert ist (Auftrag Punkt 3: „Beschaffe ergänzende Belege“)."""
    if not checks or checks.get("abgesichert"):
        return ""
    failed = set((checks.get("grund") or "").split(","))
    parts = []
    if "aktie" in failed:
        parts.append({"isin_anders": "ISIN der Quelle anders als im Stand", "cusip_anders": "CUSIP der Quelle anders als im Stand"}.get(
            str(checks.get("aktie")), figi_detail(figi, exchange_key)))
    if "name" in failed:
        score = checks.get("name_aehnlichkeit")
        parts.append("Name von der Quelle nicht angegeben" if score is None else f"Ähnlichkeit des Namens {score:.2f} (verlangt mindestens {NAME_CONFIRMED})")
    if "art" in failed:
        parts.append(f"Art laut Quelle: {checks.get('art_grund') or checks.get('art')}")
    if "handelsplatz" in failed:
        parts.append(f"Börse laut Quelle {checks.get('boerse_quelle') or 'nicht angegeben'}, Kurse des Stands {checks.get('boerse_stand') or exchange_key or '–'}"
                     + (" (offizieller Schlusskurs nur für Nasdaq-notierte Aktien)" if checks.get("handelsplatz") == "nocp_nur_fuer_nasdaq" else ""))
    if "waehrung" in failed:
        parts.append(f"Währung laut Quelle {checks.get('waehrung_quelle') or 'nicht angegeben'}")
    if "handelstag" in failed:
        parts.append(f"Handelstag {checks.get('handelstag')}")
    if "bereinigung" in failed:
        parts.append(f"Bereinigung {checks.get('bereinigung')}")
    if "kursniveau" in failed:
        ratio = checks.get("kursniveau_median")
        parts.append("Kursniveau ohne gemeinsame Tage" if ratio is None else
                     f"Kursniveau Stand/Quelle im Median {ratio:.3f} (erlaubt {1 - LEVEL_TOLERANCE:.2f} bis {1 + LEVEL_TOLERANCE:.2f})")
    if "tage" in failed:
        parts.append(f"{checks.get('gemeinsame_tage', 0)} gemeinsame Tage (verlangt mindestens {MIN_DAYS})")
    return "; ".join(p for p in parts if p)


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


def level_ratio(own: dict[int, float], rows: dict[int, dict], shift: int = 0, splits: list[tuple[int, float]] | None = None, cutoff: int | None = None) -> float | None:
    """Kursniveau Stand/Quelle im Median der gemeinsamen Tage (ohne gemeinsamen Tag None). An Tagen vor einem gemeldeten Split
    wird ein unbereinigter Kurs der Quelle um den Split bereinigt, wenn er damit dem Stand näher kommt (sonst zählte ein Split im
    Zeitraum als anderes Niveau)."""
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
    return statistics.median(ratios) if ratios else None


def level_check(own: dict[int, float], rows: dict[int, dict], shift: int = 0, splits: list[tuple[int, float]] | None = None, cutoff: int | None = None) -> str:
    """Kursniveau Stand/Quelle (Median, ``level_ratio``) innerhalb von 2 %."""
    ratio = level_ratio(own, rows, shift, splits, cutoff)
    if ratio is None:
        return "ohne_gemeinsame_tage"
    return "passt" if abs(ratio - 1) <= LEVEL_TOLERANCE else "passt_nicht"


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
        score = name_score(row["name"], meta.get("namen") or [])
        checks["name_aehnlichkeit"] = None if score is None else round(score, 2)
        # Art aus dem vollständigen Namen: die Beschreibung des Wertpapiers („- Warrants“, „- Units“) nennt die Art; der Grund
        # wird gezählt (Fonds laut Liste, Testwert laut Liste oder Beschreibung im Namen), ohne Namen
        art_grund = "fonds_laut_liste" if row["fonds"] else ("testwert_laut_liste" if row["test"] else ("beschreibung_im_namen" if not_equity(row["name"]) else None))
        checks["art"] = "kein_aktieninstrument" if art_grund else "aktie"
        if art_grund:
            checks["art_grund"] = art_grund
    source_venue = row["boerse"] if row else None
    yahoo_venue = YAHOO_LISTING.get((yahoo or {}).get("exchange") or "")
    checks["boerse_quelle"], checks["boerse_stand"] = source_venue or "nicht_angegeben", yahoo_venue or "nicht_angegeben"
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
    ratio = level_ratio(own, rows, 0, splits, cutoff)
    checks["kursniveau_median"] = None if ratio is None else round(ratio, 4)
    checks["gemeinsame_tage"] = sum(1 for d in own if d in rows)
    checks["tage"] = "genug" if checks["gemeinsame_tage"] >= MIN_DAYS else "zu_wenige"
    ok, reason = verdict(checks)
    checks["abgesichert"], checks["grund"] = ok, reason
    return checks


def strict_source(result: dict, fetched: dict, own: dict[int, float], yahoo: dict, figi: dict | None, symbol: str, exchange_key: str | None, cutoff: int,
                  names: list[str] | None = None) -> dict:
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
    if names is not None:
        score = name_score(source_name, names)
        checks["name_aehnlichkeit"] = None if score is None else round(score, 2)
    checks["art"] = "kein_aktieninstrument" if not_equity(source_name) else ("aktie" if source_name else "nicht_angegeben")
    if checks["art"] == "kein_aktieninstrument":
        checks["art_grund"] = "beschreibung_im_namen"
    checks["handelsplatz"] = result.get("handelsplatz") or "nicht_angegeben"
    source_meta = (fetched or {}).get("meta") or {}
    checks["boerse_quelle"] = zusatz.venue_kind(source_meta.get("boerse"), str(result.get("quelle") or ""))  # otc, boerse, nicht_angegeben
    checks["boerse_stand"] = result.get("handelsplatz_stand") or "unbekannt"
    checks["waehrung"] = "anders" if result.get("waehrung_yahoo") == "anders" else (result.get("waehrung") or "nicht_angegeben")
    checks["waehrung_quelle"] = source_meta.get("waehrung") or "nicht_angegeben"
    shift = int(result.get("datum_versatz") or 0)
    checks["handelstag"] = "gleich" if shift == 0 else f"versatz_{shift:+d}"
    splits = (yahoo or {}).get("splits") or []
    checks["bereinigung"] = adjustment(own, rows, yahoo, splits, cutoff, shift)
    checks["kursniveau"] = level_check(own, rows, shift, splits, cutoff)
    ratio = level_ratio(own, rows, shift, splits, cutoff)
    checks["kursniveau_median"] = None if ratio is None else round(ratio, 4)
    checks["gemeinsame_tage"] = int(result.get("gemeinsame_tage") or 0)
    checks["tage"] = "genug" if checks["gemeinsame_tage"] >= MIN_DAYS else "zu_wenige"
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
        if c.get("art_grund"):
            out[f"{q}_artgrund_{c['art_grund']}"] += 1
        for reason in (c.get("grund") or "").split(","):
            if reason and not c.get("abgesichert"):
                out[f"{q}_grund_{reason}"] += 1
    return dict(out)
