"""Datenlücken des veröffentlichten Stands einzeln geklärt (ab 1.19.0, Prüfskript; App unverändert).

Simons Auftrag vom 25.10.2026, 14:23 Uhr, Punkt 1: „Kläre unzugeordnete Instrumente, fehlende Yahoo-Zuordnungen und fehlende
Stichtagskurse. Nichtaktien weiterhin ausschließen. … Fehlende Werte niemals erfinden oder stillschweigend ersetzen.“

Der Stand kommt aus dem Release und wird – nur in GitHub Actions, mit dem Secret DATA_PASSPHRASE – entschlüsselt wie in der
unabhängigen Nachrechnung. Für jede Aktie ohne Platz in den Ranglisten nennt der Stand den Hauptstatus (Abdeckungsbilanz der
App) und bei unklarer Identität den Grund. Dieses Skript ordnet die Gründe ein und fragt bei Yahoo nach, ob sich eine Lücke
mit belegter Grundlage schließen ließe:

* **Identität unklar**: Grund laut Stand (eingeordnet ohne Namen und Kürzel); Yahoo-Suche nach der ISIN – kennt Yahoo die ISIN
  an einer Börse der App oder nur an anderen Börsen (welche, als Börsencode von Yahoo)? Nur Beobachtung: die Zuordnung der App
  kommt weiter von OpenFIGI.
* **Keine Kursdaten**: heutiger Abruf unter dem gespeicherten Kürzel (bis zum Stichtag? gleiche Währung?); bei London-Kürzeln
  mit führender Ziffer die Schreibweise mit „.IL“ (International Order Book bei Yahoo); Yahoo-Suche nach der ISIN.
* **Kurs am Stichtag fehlt / Markt am Stichtag geschlossen**: liefert Yahoo den Stichtag heute (mit Umsatz)?
* **Kein Aktieninstrument**: nur gezählt nach Typ – bleibt ausgeschlossen.

Öffentlich ausgegeben werden nur Zählwerte, Börsencodes, Länderkennungen der ISIN und eingeordnete Gründe – keine Kurse,
Namen, Kürzel oder ISINs. Geändert wird nichts.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import tempfile
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "backend"))

import kurse_ursachen as ursachen  # noqa: E402
import nachrechnen  # noqa: E402
from traktien.analytics.codes import STATUS_INFO, Status  # noqa: E402
from traktien.providers.exchanges import load_exchange_table  # noqa: E402

SEARCH = "https://query2.finance.yahoo.com/v1/finance/search?q={q}&quotesCount=10&newsCount=0&listsCount=0&enableFuzzyQuery=false"
CHART = "https://query2.finance.yahoo.com/v8/finance/chart/{symbol}?range=1mo&interval=1d"
HEADERS = {"Accept": "application/json"}
STATUS_TEXT = {int(k): v["kurz"] for k, v in STATUS_INFO.items()}

# Gründe einer unklaren Identität (Texte aus providers/identity.py: Auswahl der Notierung und Prüfung gegen die Kursdaten)
# → Code ohne Namen
REASONS = (
    (re.compile(r"kennt die ISIN nicht"), "isin_bei_der_identitaetsquelle_unbekannt"),
    (re.compile(r"keine unterstützte Börsennotierung"), "keine_notierung_an_einer_boerse_der_app"),
    (re.compile(r"Instrumenttyp (\S+)"), "kursanbieter_meldet_typ_{0}"),
    (re.compile(r"[Zz]eitzone"), "zeitzone_der_kursdaten_passt_nicht"),
    (re.compile(r"Börsencode"), "boersencode_der_kursdaten_passt_nicht"),
    (re.compile(r"Börse unbekannt"), "boerse_unbekannt"),
    (re.compile(r"keine Referenznotierung"), "keine_referenznotierung"),
    (re.compile(r"Name beim Kursanbieter"), "name_beim_kursanbieter_passt_nicht"),
    (re.compile(r"Währung"), "waehrung_passt_nicht"),
)


def reason_code(text: str | None) -> str:
    """Grund als Code ohne Namen; beim Typ laut Kursanbieter mit dem Typ (z. B. „…_etf“)."""
    for pattern, code in REASONS:
        match = pattern.search(text or "")
        if match:
            return code.format(*(g.lower().strip("().,;") for g in match.groups()))
    return "ohne_grund" if not text else "sonstiger_grund"


def symbol_class(symbol: str, exchange_key: str | None) -> str:
    """Schreibweise eines Kürzels als Klasse (ohne das Kürzel selbst)."""
    if not symbol:
        return "ohne_kuerzel"
    base = symbol.rsplit(".", 1)[0] if "." in symbol else symbol
    if exchange_key == "XLON" and base[:1].isdigit():
        return "london_ziffer_vorn"
    if base[:1].isdigit():
        return "ziffer_vorn"
    if "-" in base:
        return "mit_bindestrich"
    if exchange_key in ("US", "OTC") and len(base) == 5 and base[-1] in "FY":
        return "us_fuenf_buchstaben_f_y"
    return "sonstige"


def get_json(http, url: str):
    try:
        r = http.get(url, headers=HEADERS)
    except Exception as exc:  # noqa: BLE001 - nur zählen
        return f"fehler_{type(exc).__name__}", None
    if r.status_code != 200:
        return f"http_{r.status_code}", None
    try:
        return "ok", r.json()
    except ValueError:
        return "unlesbar", None


def chart(http, symbol: str) -> tuple[str, dict]:
    """Heutiger Abruf: Status und Tage (Tag → Umsatz) samt Börse und Währung laut Yahoo."""
    status, payload = get_json(http, CHART.format(symbol=symbol))
    if status != "ok":
        return status, {}
    result = (((payload or {}).get("chart") or {}).get("result") or [None])[0]
    if not result:
        return "ohne_kurse", {}
    meta = result.get("meta") or {}
    offset = int(meta.get("gmtoffset") or 0)
    quote = ((result.get("indicators") or {}).get("quote") or [{}])[0] or {}
    days = {}
    volumes = quote.get("volume") or []
    for n, (ts, close) in enumerate(zip(result.get("timestamp") or [], quote.get("close") or [])):
        if ts is not None and close is not None:
            days[(int(ts) + offset) // 86400] = volumes[n] if n < len(volumes) else None
    return ("ok" if days else "ohne_kurse"), {"days": days, "boerse": meta.get("exchangeName"), "waehrung": meta.get("currency")}


def fit(data: dict, currency: str | None, cutoff: int) -> str:
    """Passt eine heutige Lieferung zum Stand? (Stichtag enthalten, gleiche Währung – nur als Klasse)."""
    days = data.get("days") or {}
    has_cutoff = "mit_stichtag" if cutoff in days else ("endet_vor_stichtag" if days and max(days) < cutoff else "ohne_stichtag")
    same = "gleiche_waehrung" if (data.get("waehrung") or "") == (currency or "") else "andere_waehrung"
    return f"{has_cutoff}_{same}"


def search(http, table, isin: str) -> tuple[str, list[tuple[str | None, str, str | None, str | None]]]:
    """Yahoo-Suche nach der ISIN: (Börse der App oder None, Kürzel, Art, Börsencode von Yahoo) je Treffer."""
    status, payload = get_json(http, SEARCH.format(q=isin))
    if status != "ok":
        return status, []
    out = []
    for q in (payload or {}).get("quotes") or []:
        symbol = q.get("symbol")
        if not symbol:
            continue
        exchange = table.exchange_for_yahoo_symbol(symbol, q.get("exchange"))
        out.append((exchange.key if exchange else None, symbol, (q.get("quoteType") or "").upper() or None, q.get("exchange")))
    return "ok", out


def run(stand, sid: str, http, limit: int | None = None) -> dict:
    instruments = stand.get("instruments.bin")
    manifest = stand.get("manifest.bin")
    cutoff = int(manifest["cutoff_day"])
    table = load_exchange_table()
    n = len(instruments["isin"])
    level = instruments.get("level_status") or [0] * n
    keys = instruments.get("exchange_key") or [None] * n
    symbols = instruments.get("symbol") or [None] * n
    currencies = instruments.get("currency") or [None] * n
    reasons = instruments.get("identity_reason") or [None] * n
    types = instruments.get("type") or [None] * n
    status_counts = Counter(int(x) for x in level)
    unclear: Counter = Counter()
    unclear_country: Counter = Counter()
    unclear_yahoo: Counter = Counter()
    unclear_elsewhere: Counter = Counter()
    non_equity: Counter = Counter()
    no_data: Counter = Counter()
    no_data_probe: Counter = Counter()
    missing_day: Counter = Counter()
    missing_probe: Counter = Counter()
    calendar: Counter = Counter()
    turnover = instruments.get("turnover") or {}
    t_status = turnover.get("status") or [None] * n
    t_currency = turnover.get("currency") or [None] * n
    turnover_status: Counter = Counter()  # Ø-Umsatz-Status der Aktien mit Schlusskurs am Stichtag (Ranking 2 / Gruppe B)
    fx_missing: Counter = Counter()  # davon ohne Wechselkurs: je Währung
    budget = limit if limit is not None else 10**9
    for i in range(n):
        code = int(level[i])
        isin = str(instruments["isin"][i])
        key = keys[i] or "ohne_boerse"
        if code == 0:
            turnover_status[t_status[i] or "ohne_status"] += 1
            if t_status[i] and "wechselkurs" in str(t_status[i]):
                fx_missing[t_currency[i] or currencies[i] or "ohne_waehrung"] += 1
        if code == Status.IDENTITAET_UNKLAR:
            unclear[reason_code(reasons[i])] += 1
            unclear_country[isin[:2]] += 1
            if budget > 0:
                budget -= 1
                status, hits = search(http, table, isin)
                if status != "ok":
                    unclear_yahoo[f"suche_{status}"] += 1
                elif any(k and t == "EQUITY" for k, _, t, _ in hits):
                    unclear_yahoo["yahoo_kennt_die_isin_als_aktie_an_einer_boerse_der_app"] += 1
                elif any(k for k, _, _, _ in hits):
                    unclear_yahoo["yahoo_kennt_die_isin_an_einer_boerse_der_app_aber_nicht_als_aktie"] += 1
                elif hits:
                    unclear_yahoo["yahoo_kennt_die_isin_nur_an_anderen_boersen"] += 1
                    for code_y in sorted({y or "ohne_code" for _, _, _, y in hits}):
                        unclear_elsewhere[code_y] += 1
                else:
                    unclear_yahoo["yahoo_kennt_die_isin_nicht"] += 1
        elif code == Status.KEIN_AKTIENINSTRUMENT:
            non_equity[types[i] or "unklar"] += 1
        elif code == Status.KALENDER_FEHLT:
            calendar[key] += 1
        elif code == Status.KEINE_KURSDATEN:
            symbol = str(symbols[i] or "")
            cls = symbol_class(symbol, keys[i])
            no_data[f"{key}:{cls}"] += 1
            if budget <= 0:
                continue
            budget -= 1
            status = "ohne_kuerzel"
            if symbol:
                status, data = chart(http, symbol)
                no_data_probe[f"heute_{status}" + (f"_{fit(data, currencies[i], cutoff)}" if status == "ok" else "")] += 1
            if status != "ok" and cls == "london_ziffer_vorn":
                status_il, data_il = chart(http, symbol.rsplit(".", 1)[0] + ".IL")
                no_data_probe[f"endung_il_{status_il}" + (f"_{fit(data_il, currencies[i], cutoff)}" if status_il == "ok" else "")] += 1
            if status != "ok":
                s_status, hits = search(http, table, isin)
                same = [s for k, s, t, _ in hits if k == keys[i] and t == "EQUITY" and s != symbol]
                other = [s for k, s, t, _ in hits if k and k != keys[i] and t == "EQUITY"]
                found = "kandidat_an_derselben_boerse" if same else ("kandidat_an_anderer_boerse_der_app" if other else ("treffer_ohne_aktie_der_app" if hits else "kein_treffer"))
                no_data_probe[f"suche_{s_status}_{found}" if s_status == "ok" else f"suche_{s_status}"] += 1
        elif code in (Status.KURS_AM_STICHTAG_FEHLT, Status.MARKT_AM_STICHTAG_GESCHLOSSEN):
            name = "kurs_fehlt" if code == Status.KURS_AM_STICHTAG_FEHLT else "markt_geschlossen"
            missing_day[f"{name}:{key}"] += 1
            symbol = str(symbols[i] or "")
            if budget > 0 and symbol:
                budget -= 1
                status, data = chart(http, symbol)
                if status != "ok":
                    missing_probe[f"{name}_heute_{status}"] += 1
                elif cutoff in data["days"]:
                    volume = data["days"][cutoff]
                    missing_probe[f"{name}_stichtag_heute_vorhanden_" + ("mit_umsatz" if volume else "ohne_umsatz")] += 1
                else:
                    missing_probe[f"{name}_stichtag_auch_heute_ohne_kurs"] += 1
    return {
        "stand": sid, "stichtag": nachrechnen._iso(cutoff), "aktien": n, "status": dict(status_counts),
        "unklar": dict(unclear), "unklar_land": dict(unclear_country), "unklar_yahoo": dict(unclear_yahoo),
        "unklar_andere_boersen": dict(unclear_elsewhere), "kein_aktieninstrument": dict(non_equity),
        "kalender_fehlt": dict(calendar), "keine_kursdaten": dict(no_data), "keine_kursdaten_probe": dict(no_data_probe),
        "stichtag_luecken": dict(missing_day), "stichtag_probe": dict(missing_probe),
        "umsatz": dict(turnover_status), "wechselkurs_fehlt": dict(fx_missing),
        "gruppe_b": sum(1 for x in (turnover.get("liquid") or []) if x),
    }


def counts(c: dict) -> str:
    return ", ".join(f"{k} {v}" for k, v in sorted(c.items(), key=lambda kv: (-kv[1], kv[0]))) or "–"


def status_name(code: int) -> str:
    return "Schlusskurs am Stichtag vorhanden" if code == 0 else STATUS_TEXT.get(code, f"Status {code}")


def lines(report: dict) -> list[tuple[str, list[str]]]:
    st = report["status"]
    head = [
        f"Stand {report['stand']} (Kursstand {report['stichtag']}): {report['aktien']} Instrumente der TR-Liste; Hauptstatus der "
        "Abdeckungsbilanz: " + ", ".join(f"{status_name(int(k))} {v}" for k, v in sorted(st.items(), key=lambda kv: int(kv[0]))),
        "Geändert wird nichts: Nichtaktien bleiben ausgeschlossen, fehlende Kurse werden nicht ersetzt; die Zuordnung der App kommt weiter von OpenFIGI.",
    ]
    return [
        ("Datenlücken – Überblick", head),
        ("Datenlücken – Identität unklar", [
            f"Gründe laut Stand: {counts(report['unklar'])}",
            f"Länderkennung der ISIN: {counts(report['unklar_land'])}",
            f"Yahoo-Suche nach der ISIN (nur Beobachtung): {counts(report['unklar_yahoo'])}",
            f"Nur an anderen Börsen – Börsencodes von Yahoo (je Aktie jeder Code einmal): {counts(report['unklar_andere_boersen'])}",
        ]),
        ("Datenlücken – keine Kursdaten", [
            f"Je Börse und Schreibweise des Kürzels: {counts(report['keine_kursdaten'])}",
            f"Heutige Abfrage bei Yahoo: {counts(report['keine_kursdaten_probe'])}",
        ]),
        ("Datenlücken – Stichtag, Kalender, Nichtaktien", [
            f"Kurs am Stichtag fehlt bzw. Markt geschlossen, je Börse: {counts(report['stichtag_luecken'])}",
            f"Heutige Abfrage des Stichtags bei Yahoo: {counts(report['stichtag_probe'])}",
            f"Börsenkalender fehlt, je Börse: {counts(report['kalender_fehlt'])}",
            f"Ø Tagesumsatz der Aktien mit Schlusskurs am Stichtag (für Gruppe B), je Status: {counts(report['umsatz'])}; ohne Wechselkurs je Währung: {counts(report['wechselkurs_fehlt'])}; in Gruppe B aufgenommen: {report.get('gruppe_b', 0)}",
            f"Kein Aktieninstrument (bleibt ausgeschlossen), je Typ: {counts(report['kein_aktieninstrument'])}",
        ]),
    ]


CLOSABLE = (
    ("keine_kursdaten_probe", "heute_ok_mit_stichtag", "Yahoo liefert heute unter dem gespeicherten Kürzel Kurse bis zum Stichtag"),
    ("keine_kursdaten_probe", "endung_il_ok_mit_stichtag", "Yahoo liefert unter der Endung „.IL“ Kurse bis zum Stichtag"),
    ("keine_kursdaten_probe", "suche_ok_kandidat_an_derselben_boerse", "Yahoo nennt zur ISIN ein anderes Kürzel an derselben Börse"),
    ("stichtag_probe", "stichtag_heute_vorhanden_mit_umsatz", "Yahoo liefert den Stichtag heute mit Umsatz"),
    ("unklar_yahoo", "yahoo_kennt_die_isin_als_aktie_an_einer_boerse_der_app", "Yahoo kennt die ISIN als Aktie an einer Börse der App"),
)


def closable(report: dict) -> list[str]:
    """Hinweise auf Lücken, die sich vielleicht schließen ließen – erst nach Prüfung von Börse, Währung und Kursart zu ändern."""
    out = []
    for section, prefix, text in CLOSABLE:
        count = sum(v for k, v in (report.get(section) or {}).items() if k.startswith(prefix))
        if count:
            out.append(f"{text}: {count}")
    return out


def split_long(line: str, limit: int = 2400) -> list[str]:
    """Lange Zählzeilen an „, “ teilen (GitHub schneidet Hinweise nach etwa 4.000 Zeichen ab)."""
    if len(line.encode("utf-8")) <= limit:
        return [line]
    head, _, rest = line.partition(": ")
    parts: list[list[str]] = [[]]
    for item in rest.split(", "):
        if parts[-1] and len(f"{head} (Fortsetzung): {', '.join(parts[-1] + [item])}".encode("utf-8")) > limit:
            parts.append([])
        parts[-1].append(item)
    return [f"{head}: {', '.join(parts[0])}"] + [f"{head} (Fortsetzung): {', '.join(p)}" for p in parts[1:]]


def emit(level: str, title: str, rows: list[str]) -> None:
    flat = [part for row in rows for part in split_long(row)]
    for part in ursachen.gegen.chunked(flat):
        text = "%0A".join(x.replace("%", "%25").replace("\r", " ").replace("\n", " ") for x in part)
        print(f"::{level} title={ursachen.gegen._title(title)}::{text}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", "szymeklh87-commits/tr-aktienvergleich"))
    parser.add_argument("--stand", default=os.environ.get("STAND") or None)
    args = parser.parse_args(argv)
    from traktien.providers.http import HttpClient

    with tempfile.TemporaryDirectory() as temp:
        sid, folder, key = ursachen.load_stand(args.repo, os.environ.get("GITHUB_TOKEN"), Path(temp), args.stand)
        stand = nachrechnen.Stand(folder, sid, key)
        http = HttpClient(impersonate="chrome", max_retries=1, timeout=12, min_interval={"query2.finance.yahoo.com": 0.3})
        report = run(stand, sid, http)
    for title, body in lines(report):
        emit("notice", title, body)
    hints = closable(report)
    if hints:
        # Untersuchung, keine Abnahme: kein Bestanden/Nicht bestanden – mögliche Korrekturen sichtbar als Warnung
        emit("warning", "Datenlücken – vielleicht schließbar (erst nach Prüfung von Börse, Währung und Kursart)", hints)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
