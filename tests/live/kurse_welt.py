"""Vergleichskurse für Aktien außerhalb der US-Auswahl (seit dem 25.10.2026, Prüfskript; App unverändert).

Simons Auftrag vom 25.10.2026, 09:20 Uhr, Punkt 6: „Erfasse das gesamte Aktienuniversum der App und seine Prüfabdeckung.
Priorisiere sämtliche bislang ungeprüften Aktien mit Top-10-Platzierungen weltweit sowie die sieben Aktien ohne Vergleichskurse.
Nutze geeignete zugängliche Vergleichsquellen. … Eine Stichprobe darf nicht als Vollprüfung bezeichnet werden.“

Ausgewählt werden alle Aktien mit mindestens einem Platz unter den ersten 10 irgendeiner Rangliste, die nicht zur US-Auswahl
gehören (Heimatbörse außerhalb der USA, US-OTC-Notierungen, Kürzel mit Punkt). Vergleichsquelle ist **CNBC** (Kursmeldung mit
Name, Börse und Währung; Tageskerzen) – frei zugänglich, ohne Schlüssel. Das Kürzel bei CNBC wird nach festen Regeln aus dem
Yahoo-Kürzel und der Börse gebildet (Tabelle ``CNBC_SUFFIX``; mehrere Schreibweisen der Reihe nach). Vor jedem Vergleich gilt
dieselbe strenge Absicherung wie bei den US-Aktien (``kurse_absicherung``): Aktie über die ISIN (OpenFIGI), Name der Quelle,
Börse der Quelle = Börse des Stands (Schlüsselwörter je Börse, ``VENUE_WORDS``), Währung angegeben und gleich (Untereinheiten
wie GBp umgerechnet), Handelstag ohne Versatz, Bereinigung wie im Stand. Was nicht abgesichert ist, liefert keinen Ersatzkurs.
"""

from __future__ import annotations

import datetime as dt
import sys
import time
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "backend"))

import kurse_absicherung as absicherung  # noqa: E402
import kurse_zusatzquellen as zusatz  # noqa: E402
from traktien.providers.exchanges import unit_info  # noqa: E402

EPOCH = dt.date(1970, 1, 1)
QUOTE_URL = "https://quote.cnbc.com/quote-html-webservice/restQuote/symbolType/symbol?symbols={symbols}&requestMethod=itv&noform=1&partnerId=2&fund=1&exthrs=1&output=json&events=1"
BARS_URL = "https://ts-api.cnbc.com/harmony/app/bars/{symbol}/1D/{start:%Y%m%d}000000/{end:%Y%m%d}000000/adjusted/EST5EDT.json"
QUOTE_BATCH = 20  # Kürzel je Kursmeldung (CNBC trennt mehrere mit „|“)
BUDGET_S = 30 * 60
# Länderkennung des Kürzels bei CNBC je Börsenschlüssel der App (mehrere = der Reihe nach versucht). Belegt ist die Zuordnung
# erst durch die Kursmeldung selbst (Börse, Währung, Name) – eine falsche Kennung führt nie zu einem Vergleich.
CNBC_SUFFIX = {
    "XETR": ("DE",), "XFRA": ("FF",), "XLON": ("GB",), "XHKG": ("HK",), "XTKS": ("JP",), "XASX": ("AU",), "XTSE": ("CA",),
    "XTSX": ("V", "CA"), "XCNQ": ("CNX", "CA"), "XSWX": ("CH",), "XPAR": ("FR",), "XAMS": ("NL",), "XBRU": ("BE",), "XLIS": ("PT",),
    "XDUB": ("IE", "IR"), "XMIL": ("IT",), "XMAD": ("ES",), "XWBO": ("AT",), "XSTO": ("SE",), "XCSE": ("DK",), "XHEL": ("FI",),
    "XOSL": ("NO",), "XICE": ("IS",), "XWAR": ("PL",), "XPRA": ("CZ",), "XBUD": ("HU",), "ASEX": ("GR",), "XIST": ("TR",),
    "XTAE": ("IL",), "XJSE": ("ZA",), "XSES": ("SG",), "XKRX": ("KR",), "XKOS": ("KQ", "KR"), "XTAI": ("TW",), "XNSE": ("IN",),
    "XNZE": ("NZ",), "XMEX": ("MX",), "BVMF": ("BR",), "XSGO": ("CL",), "XTAL": ("EE",), "XSHG": ("CN",), "XSHE": ("CN", "SZ"),
    "XKLS": ("MY",), "XBKK": ("TH",), "XIDX": ("ID",),
}
# Schlüsselwörter, an denen die Börse in der Kursmeldung von CNBC („exchange“) erkannt wird – Großschreibung
VENUE_WORDS = {
    "XETR": ("XETRA",), "XFRA": ("FRANKFURT",), "XLON": ("LONDON", "LSE"), "XHKG": ("HONG KONG", "HKEX", "HKG"),
    "XTKS": ("TOKYO", "JAPAN"), "XASX": ("AUSTRALIA", "ASX"), "XTSE": ("TORONTO", "TSX"), "XTSX": ("VENTURE", "TSXV", "TSX-V"),
    "XCNQ": ("CANADIAN SECURITIES", "CSE", "CNSX"), "XSWX": ("SWISS", "SIX", "ZURICH"), "XPAR": ("PARIS",), "XAMS": ("AMSTERDAM",),
    "XBRU": ("BRUSSELS",), "XLIS": ("LISBON",), "XDUB": ("DUBLIN", "IRISH"), "XMIL": ("MILAN", "ITALIAN", "BORSA ITALIANA"),
    "XMAD": ("MADRID", "SPANISH", "BME"), "XWBO": ("VIENNA", "WIENER"), "XSTO": ("STOCKHOLM",), "XCSE": ("COPENHAGEN",),
    "XHEL": ("HELSINKI",), "XOSL": ("OSLO",), "XICE": ("ICELAND",), "XWAR": ("WARSAW",), "XPRA": ("PRAGUE",), "XBUD": ("BUDAPEST",),
    "ASEX": ("ATHENS",), "XIST": ("ISTANBUL",), "XTAE": ("TEL AVIV",), "XJSE": ("JOHANNESBURG",), "XSES": ("SINGAPORE",),
    "XKRX": ("KOREA",), "XKOS": ("KOSDAQ",), "XTAI": ("TAIWAN",), "XNSE": ("NATIONAL STOCK EXCHANGE OF INDIA", "NSE"),
    "XNZE": ("NEW ZEALAND", "NZX"), "XMEX": ("MEXICAN", "MEXICO"), "BVMF": ("SAO PAULO", "BOVESPA", "B3"), "XSGO": ("SANTIAGO",),
    "XTAL": ("TALLINN",), "XSHG": ("SHANGHAI",), "XSHE": ("SHENZHEN",), "XKLS": ("MALAYSIA", "KUALA LUMPUR", "BURSA"),
    "XBKK": ("THAILAND",), "XIDX": ("INDONESIA", "JAKARTA"), "OTC": ("OTC", "PINK", "GREY", "EXPERT"),
}
EXCLUDE_WORDS = {"XKRX": ("KOSDAQ",), "XTSE": ("VENTURE",)}  # „KOREA … KOSDAQ“ ist nicht KOSPI, „TSX Venture“ nicht TSX


def base_ticker(symbol: str) -> str:
    """Yahoo-Kürzel ohne Börsenendung: „SIE.DE“ → „SIE“, „VOLV-B.ST“ → „VOLV-B“, „BRK-B“ → „BRK-B“."""
    s = (symbol or "").strip().upper()
    head, dot, tail = s.rpartition(".")
    return head if dot and 1 <= len(tail) <= 3 and head else s


def cnbc_candidates(symbol: str, exchange_key: str | None) -> list[str]:
    """Kürzel bei CNBC in der Reihenfolge der Versuche (höchstens vier). US-OTC und US-Kürzel ohne Endung: Gattung mit Punkt."""
    key = exchange_key or ""
    base = base_ticker(symbol)
    if key in absicherung.US_FAMILY or key in absicherung.OTC_FAMILY or key not in CNBC_SUFFIX:
        return [base.replace("-", ".")] if key in absicherung.US_FAMILY | absicherung.OTC_FAMILY else []
    tickers: list[str] = []
    if "-" in base:  # Gattung: „VOLV-B“ → „VOLV.B“, „VOLVB“
        tickers += [base.replace("-", "."), base.replace("-", "")]
    elif key == "XHKG" and base.isdigit():
        tickers += [base.zfill(4), base.lstrip("0") or base]
    elif key == "XLON" and len(base) <= 2:
        tickers += [base + ".", base]
    elif key == "XMEX":
        tickers += [base, base + "*"]
    else:
        tickers.append(base)
    out: list[str] = []
    for suffix in CNBC_SUFFIX[key]:
        for ticker in tickers:
            candidate = f"{ticker}-{suffix}"
            if candidate not in out:
                out.append(candidate)
    return out[:4]


def venue_check(source_exchange: str | None, exchange_key: str | None) -> str:
    """Börse der Kursmeldung gegen die Börse des Stands: „gleich“, „anders“, „nicht_angegeben“ oder „nicht_zuordenbar“
    (Börse ohne Schlüsselwörter in der Tabelle)."""
    text = (source_exchange or "").upper()
    if not text:
        return "nicht_angegeben"
    words = VENUE_WORDS.get(exchange_key or "")
    if not words:
        return "nicht_zuordenbar"
    if any(word in text for word in EXCLUDE_WORDS.get(exchange_key or "", ())):
        return "anders"
    return "gleich" if any(word in text for word in words) else "anders"


def unit_factor(source_currency: str | None, stand_currency: str | None, stand_unit: str | None) -> tuple[str, float]:
    """Währung der Quelle gegen die des Stands. Rückgabe: Ergebnis und der Faktor, mit dem ein Kurs der Quelle in die Einheit
    des Stands umgerechnet wird (GBP-Kurs → GBp: × 100). Ohne Angabe der Quelle „nicht_angegeben“ (nie bestanden)."""
    if not source_currency:
        return "nicht_angegeben", 1.0
    src = source_currency.strip()
    unit = (stand_unit or stand_currency or "").strip()
    if src == unit:
        return "gleich", 1.0
    # Groß-/Kleinschreibung unterscheidet Pfund und Pence („GBP“ und „GBp“) – deshalb über die Untereinheiten der App, nie über
    # einen Vergleich ohne Groß-/Kleinschreibung (bis 25.10.2026, 11 Uhr galten GBP-Kurse fälschlich als Pence)
    src_base, src_factor = unit_info(src)
    own_base, own_factor = unit_info(unit)
    if src_base and own_base and src_base.upper() == own_base.upper():
        return "gleich", src_factor / own_factor  # z. B. GBP (1) → GBp (0,01): × 100; GBX → GBp: × 1
    return "anders", 1.0


def quote_entries(payload) -> list[dict]:
    """Einträge einer Kursmeldung von CNBC (ein oder mehrere Kürzel)."""
    if isinstance(payload, dict):
        result = payload.get("FormattedQuoteResult") or payload.get("QuickQuoteResult") or {}
        entries = result.get("FormattedQuote") or result.get("QuickQuote") or []
        if isinstance(entries, dict):
            entries = [entries]
        return [e for e in entries if isinstance(e, dict)]
    return []


def fetch_quotes(http, symbols: list[str]) -> tuple[dict[str, dict], Counter]:
    """Kursmeldungen für viele Kürzel (je Anfrage ``QUOTE_BATCH``): je Kürzel Name, Börse, Währung, ISIN – nur Kürzel mit
    Namen gelten als gefunden."""
    found: dict[str, dict] = {}
    status: Counter = Counter()
    for k in range(0, len(symbols), QUOTE_BATCH):
        batch = symbols[k : k + QUOTE_BATCH]
        url = QUOTE_URL.format(symbols="%7C".join(batch))
        code, content = zusatz.get_raw(http, url, zusatz.HEADERS["cnbc"])
        status[f"kursmeldung_{code}"] += 1
        if code != "ok":
            continue
        payload, _ = zusatz.decode(content)
        for entry in quote_entries(payload):
            meta = zusatz.find_meta(entry)
            symbol = str(entry.get("symbol") or "").upper()
            if symbol and meta.get("name") and entry.get("code") in (None, 0, "0"):
                found[symbol] = meta
    return found, status


def fetch_bars(http, symbol: str, start_day: int, cutoff: int) -> tuple[str, dict[int, dict]]:
    start = EPOCH + dt.timedelta(days=start_day)
    end = EPOCH + dt.timedelta(days=cutoff + 1)
    code, content = zusatz.get_raw(http, BARS_URL.format(symbol=symbol, start=start, end=end), zusatz.HEADERS["cnbc"])
    if code != "ok":
        return code, {}
    payload, text = zusatz.decode(content)
    rows, _ = zusatz.parse_json_rows(payload) if payload is not None else ({}, [])
    rows = {d: r for d, r in rows.items() if start_day <= d <= cutoff}
    return ("ok" if rows else "ok_ohne_kurse"), rows


def check_world(rows: dict[int, dict], meta_source: dict, own: dict[int, float], meta: dict, yahoo: dict, figi: dict | None, cnbc_symbol: str,
                stand_symbol: str, exchange_key: str, cutoff: int) -> tuple[dict, dict[int, dict]]:
    """Strenge Prüfungen eines Vergleichs mit CNBC für eine Aktie außerhalb der US-Auswahl (wie ``absicherung.verdict``).
    Rückgabe: Prüfungen und die Tageskurse in der Einheit des Stands."""
    checks: dict = {"quelle": "cnbc_welt"}
    checks["aktie"] = absicherung.figi_identity(figi, stand_symbol, exchange_key)
    identity = zusatz.identity(meta_source, meta.get("isin", ""), meta.get("namen") or [])
    if identity in ("isin_bestaetigt", "cusip_bestaetigt"):
        checks["aktie"] = "isin_kuerzel_bestaetigt"
    elif identity in ("isin_anders", "cusip_anders"):
        checks["aktie"] = "isin_anders"
    checks["name"] = "bestaetigt" if identity in ("name_bestaetigt", "isin_bestaetigt", "cusip_bestaetigt") else ("nicht_angegeben" if identity == "nur_kuerzel" else "passt_nicht")
    checks["art"] = "kein_aktieninstrument" if absicherung.not_equity(meta_source.get("name")) else "aktie"
    checks["handelsplatz"] = venue_check(meta_source.get("boerse"), exchange_key)
    currency, factor = unit_factor(meta_source.get("waehrung"), meta.get("waehrung"), meta.get("einheit"))
    checks["waehrung"] = currency
    converted = {d: {**r, "close": r["close"] * factor} for d, r in rows.items()} if factor != 1.0 else rows
    shift, _ = zusatz.best_shift(own, converted)
    checks["handelstag"] = "gleich" if shift == 0 else f"versatz_{shift:+d}"
    checks["bereinigung"] = absicherung.adjustment(own, converted, yahoo, (yahoo or {}).get("splits") or [], cutoff)
    checks["kursniveau"] = absicherung.level_check(own, converted)
    checks["tage"] = "genug" if sum(1 for d in own if d in converted) >= absicherung.MIN_DAYS else "zu_wenige"
    ok, reason = absicherung.verdict(checks)
    checks["abgesichert"], checks["grund"] = ok, reason
    checks["faktor_einheit"] = factor
    return checks, converted


def select_world(stand, instruments: dict, us: set[int]) -> tuple[list[int], dict[int, int], dict[int, int]]:
    """Alle Aktien außerhalb der US-Auswahl mit mindestens einem Platz unter den ersten 10 einer Rangliste – die häufigsten
    zuerst; dazu je Aktie die Zahl der Plätze unter den ersten 10 und auf Platz 1."""
    top10: Counter = Counter()
    first: Counter = Counter()
    for h in range(1, 91):
        win = stand.get(f"windows/{h}.full.bin")
        orders = win["orders"]
        lists = [orders.get("v0") or [], orders.get("v0l") or []]
        for group in ("u", "ul"):
            lists += [values for w, values in (orders.get(group) or {}).items() if str(w) != "0"]
        for values in lists:
            for k, i in enumerate(int(x) for x in values[:10]):
                if i in us:
                    continue
                top10[i] += 1
                first[i] += k == 0
        stand.drop(f"windows/{h}.full.bin")
    chosen = sorted(top10, key=lambda i: (-top10[i], i))
    return chosen, dict(top10), dict(first)


def classify_days(own: dict[int, float], rows: dict[int, dict], yahoo: dict, splits, cutoff: int, within_display) -> dict[int, tuple[str, float, str]]:
    """Jeder gemeinsame Tag wie bei den US-Zusatzquellen (``zusatz.compare``)."""
    return zusatz.compare(own, rows, 0, yahoo, within_display, splits=splits, cutoff=cutoff)


def run_world(stand, instruments: dict, http, us: set[int], own_series, stand_meta, figi: dict[str, dict], start_day: int, cutoff: int,
              yahoo_daily, within_display, clock=time.monotonic, budget_s: float = BUDGET_S, selection: tuple | None = None) -> dict:
    """Vergleich aller ausgewählten Aktien außerhalb der US-Auswahl mit CNBC. ``own_series(i)`` liefert die Kurse des Stands,
    ``stand_meta(i)`` die Angaben zur Identität, ``yahoo_daily(symbol)`` die Yahoo-Tageskurse (dividendenbereinigt, Splits);
    ``selection`` (Auswahl, Plätze unter den ersten 10, Plätze 1) aus ``select_world``, sonst hier bestimmt."""
    started = clock()
    chosen, top10, first = selection if selection is not None else select_world(stand, instruments, us)
    keys = instruments.get("exchange_key") or [None] * len(instruments["isin"])
    symbols = [str(s or "") for s in (instruments.get("symbol") or [None] * len(instruments["isin"]))]
    candidates = {i: cnbc_candidates(symbols[i], keys[i]) for i in chosen}
    counts: Counter = Counter()
    for i in chosen:
        counts[f"ausgewaehlt_{keys[i] or 'ohne_boerse'}"] += 1
        if not candidates[i]:
            counts[f"ohne_kuerzelregel_{keys[i] or 'ohne_boerse'}"] += 1
    wanted = list(dict.fromkeys(c for i in chosen for c in candidates[i]))
    quotes, quote_status = fetch_quotes(http, wanted)
    counts.update(quote_status)
    out: dict = {"aktien": {}, "zaehler": counts, "pruefungen": [], "top10": top10, "platz1": first, "ausgewaehlt": chosen}
    for i in chosen:
        key = keys[i] or "ohne_boerse"
        entry: dict = {"boerse": key, "top10": int(top10.get(i, 0)), "platz1": int(first.get(i, 0))}
        out["aktien"][i] = entry
        if clock() - started > budget_s:
            entry["ergebnis"] = "zeitbudget_erschoepft"
            counts[f"zeitbudget_{key}"] += 1
            continue
        found = next(((k, c) for k, c in enumerate(candidates[i]) if c.upper() in quotes), None)
        if found is None:
            entry["ergebnis"] = "nicht_gefunden" if candidates[i] else "ohne_kuerzelregel"
            counts[f"nicht_gefunden_{key}"] += 1
            continue
        pattern, cnbc_symbol = found
        counts[f"kuerzel_schreibweise_{pattern + 1}_{key}"] += 1
        own = own_series(i)
        if not own:
            entry["ergebnis"] = "stand_ohne_kurse"
            counts[f"stand_ohne_kurse_{key}"] += 1
            continue
        code, rows = fetch_bars(http, cnbc_symbol, start_day, cutoff)
        counts[f"kerzen_{code}"] += 1
        if not rows:
            entry["ergebnis"] = "keine_kurse"
            counts[f"keine_kurse_{key}"] += 1
            continue
        yahoo = yahoo_daily(symbols[i])
        checks, converted = check_world(rows, quotes[cnbc_symbol.upper()], own, stand_meta(i), yahoo, figi.get(str(instruments["isin"][i])), cnbc_symbol,
                                        symbols[i], keys[i], cutoff)
        checks["boerse"] = key
        out["pruefungen"].append(checks)
        entry.update(ergebnis="abgesichert" if checks["abgesichert"] else "nicht_abgesichert", grund=checks["grund"])
        counts[f"{entry['ergebnis']}_{key}"] += 1
        days = classify_days(own, converted, yahoo, (yahoo or {}).get("splits") or [], cutoff, within_display)
        entry["tage"] = days
        entry["nur_im_stand"] = sum(1 for d in own if d not in converted)
        entry["nur_im_stand_ohne_umsatz"] = sum(1 for d in own if d not in converted and (((yahoo or {}).get("days") or {}).get(d) or {}).get("volume") == 0)
        entry["kursbereich"] = zusatz_price_range(converted)
        entry["tage_stand"] = len(own)
        entry["tage_verglichen"] = len(days)
        entry["rows"] = converted
    return out


def zusatz_price_range(rows: dict[int, dict]) -> str:
    values = sorted(r["close"] for r in rows.values())
    median = values[len(values) // 2] if values else 0
    return next(label for limit, label in ((1, "unter 1"), (10, "1–10"), (100, "10–100"), (float("inf"), "über 100")) if median < limit) + " (Landeswährung)"
