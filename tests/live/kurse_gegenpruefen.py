"""Kurse unabhängig gegenprüfen (ab 1.18): Schlusskurse und Renditen des veröffentlichten Stands gegen einen zweiten
Anbieter – Nasdaq (Kurshistorie der Website nasdaq.com) für US-Aktien.

Simons Auftrag vom 24.10.2026, 19:29 Uhr: „Prüfe die aktuelle Berechnung unabhängig anhand verfügbarer Kursdaten und
nachvollziehbarer Referenzfälle. Kennzeichne nachträglich beschaffte Daten ausdrücklich; sie beweisen nicht, welche Daten
dem ursprünglichen Modell damals vorlagen.“

Die App bezieht ihre Kurse von Yahoo. Die unabhängige Nachrechnung (``nachrechnen.py``) prüft die Rechnung mit den
veröffentlichten Kursreihen – ob diese Kurse selbst stimmen, prüft sie nicht. Dieses Skript lädt dafür **nachträglich**
die Tageskurse einer Auswahl von US-Aktien bei **Nasdaq** (anderer Anbieter, eigener Abruf und eigene Auswertung, ohne
den Kursabruf der App) und vergleicht mit dem Stand:

1. **Schlusskurs je Börsentag** – gleich (innerhalb der Rundung von Nasdaq auf Cent bzw. 1/100 Cent unter 1 $), Faktor
   (Split/Zusammenlegung seit dem Abruf), Kurs eines Nachbartags, kleine (≤ 0,5 %) oder große Abweichung;
2. **Kursrendite jedes Zeitraums 1–90 Tage** aus Nasdaq-Kursen an denselben Start- und Endtagen wie im Stand;
3. **fehlende Börsentage**: Tage, an denen der Stand keinen Kurs hat (in der App ein fehlender Kurstag), Nasdaq aber
   einen – und umgekehrt.
4. **Gegenprobe bei Yahoo** (ab dem 24.10.2026 abends): Dieselben Tage werden nachträglich auch bei Yahoo, der Quelle der
   App, abgerufen – mit eigener, schlichter Auswertung (Zeitstempel + Zeitzone der Börse, nur Tageskerzen mit
   Schlusskurs), nicht mit dem Kursabruf der App. Jede Abweichung von Nasdaq bekommt eine Ursache:
   *wie Yahoo* – der Kurs des Stands ist der heutige Yahoo-Kurs, die Anbieter unterscheiden sich (kein Fehler der App);
   *vorläufig aus der Kursmeldung* – der Tag steht in ``quote_days`` der Kursreihe (Schlusskurs aus der Kursmeldung, weil
   die Tageskerze noch keinen hatte) und Yahoo hat inzwischen einen anderen; *ohne Yahoo-Kurs* bzw. *unerklärt* – sonst.

Urteil: **bestanden**, wenn alle Kurse und Renditen mit Nasdaq übereinstimmen; **bestanden mit Unterschieden zwischen den
Anbietern**, wenn jede Abweichung durch den heutigen Yahoo-Kurs oder einen markierten vorläufigen Kurs belegt ist (die
Abweichungen stehen trotzdem vollständig im Ergebnis); **nicht bestanden**, sobald eine Abweichung unerklärt ist, Yahoo
für einen abweichenden Tag keinen Kurs hat oder eine der Quellen nur für einen Teil der Aktien erreichbar war.

Auswahl: alle US-Aktien unter den ersten 10 irgendeiner Rangliste (Gruppe A und B, alle Gewichtungen, 1–90 Tage) und
bis zu 150 weitere, zufällig gewählte (fester Startwert aus der Stand-ID – wiederholbar). Ausgegeben werden nur
Zählwerte und Abweichungsklassen, keine Kurse, Namen, Ticker oder ISINs (das Protokoll ist öffentlich).

Was das **nicht** zeigt: welche Kurse ein anderes Modell (z. B. das Ausgangsmodell) damals hatte; ob Yahoo seine Kurse
zwischen dem Abruf der App und der Gegenprobe geändert hat (dann gilt die Abweichung als unerklärt); Aktien außerhalb
der USA (Nasdaq führt sie nicht).
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import random
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "backend"))

import nachrechnen  # noqa: E402 - Datenstand laden und entschlüsseln (ohne Rechenkern)

NASDAQ = "https://api.nasdaq.com/api/quote/{symbol}/historical?assetclass=stocks&fromdate={start}&limit=9999&todate={end}"
HEADERS = {"Accept": "application/json, text/plain, */*", "Origin": "https://www.nasdaq.com", "Referer": "https://www.nasdaq.com/"}
YAHOO = "https://query2.finance.yahoo.com/v8/finance/chart/{symbol}?period1={start}&period2={end}&interval=1d&events=split"
YAHOO_HEADERS = {"Accept": "application/json"}
CAUSES = ("wie_yahoo", "kursmeldung", "ohne_yahoo_kurs", "unerklaert")
CAUSE_TEXT = {"wie_yahoo": "wie Yahoo", "kursmeldung": "vorläufig aus der Kursmeldung", "ohne_yahoo_kurs": "ohne Yahoo-Kurs", "unerklaert": "unerklärt"}
MAX_ANNOTATION_BYTES = 3000  # GitHub kürzt lange Hinweise (am 24.10.2026 nach etwa 4.000 Zeichen abgeschnitten)
EPOCH = dt.date(1970, 1, 1)
LOOKBACK_DAYS = 140  # 90 Kalendertage plus Vorlauf bis zur Startsitzung
RANDOM_EXTRA = 150
MAX_STOCKS = 450
FACTORS = (2, 3, 4, 5, 6, 8, 10, 12, 15, 20, 25, 30, 40, 50, 100)
SMALL = 0.005  # bis 0,5 % gilt eine Abweichung als klein


def day_of(text: str) -> int:
    """„10/23/2026“ (Nasdaq) → Tagesnummer seit 1970 wie im Datenstand."""
    month, day, year = (int(x) for x in text.split("/"))
    return (dt.date(year, month, day) - EPOCH).days


def price(text) -> float | None:
    """„$1,234.56“ → 1234.56; leer/„N/A“ → None."""
    if text is None:
        return None
    cleaned = str(text).replace("$", "").replace(",", "").strip()
    try:
        value = float(cleaned)
    except ValueError:
        return None
    return value if value > 0 else None


def parse_nasdaq(payload: dict) -> dict[int, float]:
    """Schlusskurse je Tag aus der Antwort von Nasdaq (``data.tradesTable.rows``)."""
    rows = (((payload or {}).get("data") or {}).get("tradesTable") or {}).get("rows") or []
    out: dict[int, float] = {}
    for row in rows:
        close = price(row.get("close"))
        if close is not None and row.get("date"):
            out[day_of(row["date"])] = close
    return out


def parse_yahoo(payload: dict) -> dict[int, float]:
    """Schlusskurse je Börsentag aus einer v8-Chart-Antwort von Yahoo – eigene, schlichte Auswertung, nicht der Kursabruf
    der App: Tag = Zeitstempel der Tageskerze + ``gmtoffset`` der Börse; nur Kerzen mit Schlusskurs (kein Ersatz aus der
    Kursmeldung, keine Rundung)."""
    results = (((payload or {}).get("chart") or {}).get("result")) or []
    result = results[0] if results else {}
    result = result or {}
    try:
        offset = int((result.get("meta") or {}).get("gmtoffset") or 0)
    except (TypeError, ValueError):
        offset = 0
    stamps = result.get("timestamp") or []
    quotes = (result.get("indicators") or {}).get("quote") or [{}]
    closes = (quotes[0] or {}).get("close") or []
    out: dict[int, float] = {}
    for ts, close in zip(stamps, closes):
        if ts is None or close is None:
            continue
        try:
            value = float(close)
        except (TypeError, ValueError):
            continue
        if value > 0 and math.isfinite(value):
            out[(int(ts) + offset) // 86400] = value
    return out


def same_as_yahoo(own: float, value: float) -> bool:
    """Kurs des Stands gleich dem heutigen Yahoo-Kurs. Yahoo liefert Gleitkommazahlen mit etwa 7 gültigen Stellen
    (z. B. 262.2399902), die App speichert sie unverändert."""
    return abs(own - value) <= max(1e-6 * abs(value), 1e-7)


def day_cause(day: int, own: float, yahoo: dict[int, float] | None, quote_days: set[int]) -> str:
    """Ursache einer Abweichung von Nasdaq an einem Tag (siehe Modulbeschreibung, Punkt 4)."""
    if yahoo is None or day not in yahoo:
        return "ohne_yahoo_kurs"
    if same_as_yahoo(own, yahoo[day]):
        return "wie_yahoo"
    if day in quote_days:
        return "kursmeldung"
    return "unerklaert"


def return_cause(causes: set[str]) -> str:
    """Ursache einer abweichenden Rendite aus den Ursachen an Start- und Endtag: nur wenn beide Kurse des Stands die
    heutigen Yahoo-Kurse sind, ist die Rendite die von Yahoo."""
    if causes == {"wie_yahoo"}:
        return "wie_yahoo"
    for cause in ("unerklaert", "ohne_yahoo_kurs"):
        if cause in causes:
            return cause
    return "kursmeldung"


def tolerance(value: float) -> float:
    """Halbe letzte Stelle, mit der Nasdaq den Kurs angibt: Cent ab 1 $, 1/100 Cent darunter."""
    return (0.005 if value >= 1 else 0.00005) + 1e-9


def classify(own: float, fresh: float, neighbours: list[float]) -> str:
    """Schlusskurs des Stands gegen Nasdaq am selben Tag."""
    if abs(own - fresh) <= tolerance(fresh):
        return "gleich"
    ratio = own / fresh
    if any(abs(ratio - f) <= 0.01 * f or abs(ratio - 1 / f) <= 0.01 / f for f in FACTORS):
        return "faktor"
    if any(abs(own - n) <= tolerance(n) for n in neighbours):
        return "nachbartag"
    return "klein" if abs(ratio - 1) <= SMALL else "gross"


def return_matches(r_own: float, p0: float, p1: float) -> bool:
    """Rendite des Stands gegen Nasdaq-Kurse an denselben Tagen, innerhalb der Rundung beider Kurse."""
    fresh = p1 / p0 - 1
    allowed = (1 + fresh) * (tolerance(p0) / p0 + tolerance(p1) / p1) + 1e-9
    return abs(r_own - fresh) <= allowed


def compare_stock(
    series: dict,
    fresh: dict[int, float],
    returns: dict[int, float],
    cutoff: int,
    diag: dict | None = None,
    yahoo: dict[int, float] | None = None,
) -> dict:
    """Zählwerte für eine Aktie: Kurstage, fehlende Tage, Renditen und – mit ``yahoo`` (heutige Yahoo-Kurse) – die
    Ursache jeder Abweichung. ``diag`` (optional) bekommt die Muster der Abweichungen ohne Kurse: Verhältnis
    Stand/Nasdaq, Lage vor dem Stichtag, Cent-Abweichungen, Ursachen, größte Renditeabweichung."""
    counts: Counter = Counter()
    off: list[tuple[int, float, float, str, str]] = []
    first = cutoff - LOOKBACK_DAYS
    days = [int(d) for d in series.get("d") or []]
    closes = [None if c is None else float(c) for c in series.get("c") or []]
    quote_days = {int(d) for d in series.get("quote_days") or []}
    own = {d: c for d, c in zip(days, closes) if c is not None and c > 0 and first <= d <= cutoff}
    fresh_days = sorted(d for d in fresh if first <= d <= cutoff)

    def cause_of(day: int) -> str:
        return day_cause(day, own[day], yahoo, quote_days) if day in own else "unerklaert"

    for d, c in own.items():
        if yahoo is not None:
            if d in yahoo:
                counts["yahoo_tage_verglichen"] += 1
                same = same_as_yahoo(c, yahoo[d])
                counts["yahoo_gleich" if same else "yahoo_abweichend"] += 1
                if not same and d in quote_days:
                    counts["yahoo_abweichend_kursmeldung"] += 1
            else:
                counts["nicht_bei_yahoo"] += 1
        if d not in fresh:
            counts["nur_im_stand"] += 1
            continue
        k = fresh_days.index(d)
        neighbours = [fresh[fresh_days[j]] for j in (k - 1, k + 1) if 0 <= j < len(fresh_days)]
        counts["tage_verglichen"] += 1
        kind = classify(c, fresh[d], neighbours)
        counts[f"tag_{kind}"] += 1
        if kind != "gleich":
            cause = cause_of(d)
            counts[f"abweichung_{cause}"] += 1
            off.append((d, c, fresh[d], kind, cause))
    gaps = {int(g) for g in series.get("gaps") or []}
    blank = {d for d, c in zip(days, closes) if c is None}
    series_start = min(days) if days else cutoff
    last_own = max(own, default=None)
    for d in fresh_days:
        if d in own or d < series_start:
            continue
        counts["nur_bei_nasdaq"] += 1
        if yahoo is not None and d in yahoo:
            counts["nur_bei_nasdaq_yahoo_heute_mit_kurs"] += 1
        if last_own is not None and d > last_own:
            counts["nur_bei_nasdaq_nach_letztem_kurs_des_stands"] += 1  # z. B. Stichtagskurs fehlte beim Abruf
        elif d in gaps or d in blank:
            counts["nur_bei_nasdaq_als_fehlender_tag_gezaehlt"] += 1
        else:
            counts["nur_bei_nasdaq_ohne_sitzung_im_stand"] += 1
    end = max(own) if own else None
    starts = series.get("window_start") or []
    return_causes: Counter = Counter()
    for h, r in returns.items():
        start = starts[h - 1] if h - 1 < len(starts) else None
        if start is None or end is None:
            continue
        if start not in fresh or end not in fresh:
            counts["rendite_ohne_nasdaq_kurs"] += 1
            continue
        counts["renditen_verglichen"] += 1
        ok = return_matches(r, fresh[start], fresh[end])
        counts["rendite_gleich" if ok else "rendite_abweichend"] += 1
        if not ok:
            cause = return_cause({cause_of(start), cause_of(end)})
            counts[f"rendite_abweichend_{cause}"] += 1
            return_causes[cause] += 1
            if diag is not None:
                diag["groesste_renditeabweichung_pp"] = max(diag.get("groesste_renditeabweichung_pp", 0.0), round(100 * abs(r - (fresh[end] / fresh[start] - 1)), 2))
    if diag is not None and (off or return_causes):
        compared = sorted(d for d in own if d in fresh)
        diag.update({"tage": len(compared), "abweichend": len(off), "renditen_ursachen": dict(return_causes)})
        if off:
            ratios = sorted(o / f for _, o, f, _, _ in off)
            last_off = max(d for d, *_ in off)
            diag.update(
                {
                    "verhaeltnis": [round(ratios[0], 4), round(ratios[len(ratios) // 2], 4), round(ratios[-1], 4)],
                    "konstant": (ratios[-1] - ratios[0]) <= 0.002 * ratios[len(ratios) // 2],
                    "erste_abweichung_tage_vor_stichtag": cutoff - min(d for d, *_ in off),
                    "letzte_abweichung_tage_vor_stichtag": cutoff - last_off,
                    "danach_gleich": len([d for d in compared if d > last_off]),
                    "cent": sum(1 for _, o, f, _, _ in off if abs(o - f) <= 0.0101),
                    "ursachen": dict(Counter(cause for *_, cause in off)),
                }
            )
        if fresh:
            diag["kursbereich"] = next(label for limit, label in ((1, "unter 1 $"), (10, "1–10 $"), (100, "10–100 $"), (float("inf"), "über 100 $")) if sorted(fresh.values())[len(fresh) // 2] < limit)
    return dict(counts)


def select(stand: nachrechnen.Stand, instruments: dict, sid: str) -> tuple[list[int], int]:
    """US-Aktien unter den ersten 10 einer Rangliste und zufällig gewählte weitere (wiederholbar)."""
    n = len(instruments["isin"])
    calendar = instruments.get("calendar") or [None] * n
    key = instruments.get("exchange_key") or [None] * n
    symbol = instruments.get("symbol") or [None] * n
    has_series = instruments.get("has_series") or [True] * n
    us = [i for i in range(n) if calendar[i] == "XNYS" and key[i] != "OTC" and symbol[i] and "." not in str(symbol[i]) and has_series[i]]
    us_set = set(us)
    top: set[int] = set()
    for h in range(1, 91):
        win = stand.get(f"windows/{h}.full.bin")
        orders = win["orders"]
        lists = [orders.get("v0") or [], orders.get("v0l") or []]
        for group in ("u", "ul"):
            lists += [values for values in (orders.get(group) or {}).values()]
        for values in lists:
            top.update(int(i) for i in values[:10] if int(i) in us_set)
        stand.drop(f"windows/{h}.full.bin")
    rest = sorted(us_set - top)
    extra = random.Random(sid).sample(rest, min(RANDOM_EXTRA, len(rest)))
    chosen = sorted(top)[: MAX_STOCKS - len(extra)] + sorted(extra)
    return chosen, len(top)


def window_returns(stand: nachrechnen.Stand, chosen: set[int]) -> dict[int, dict[int, float]]:
    """Veröffentlichte Rendite je Aktie und Zeitraum (nur für die Auswahl)."""
    out: dict[int, dict[int, float]] = {i: {} for i in chosen}
    for h in range(1, 91):
        m = stand.get(f"windows/{h}.full.bin")["m"]
        for k, i in enumerate(m["idx"]):
            if int(i) in out and m["r"][k] is not None:
                out[int(i)][h] = float(m["r"][k])
        stand.drop(f"windows/{h}.full.bin")
    return out


def fetch(http, symbol: str, cutoff: int) -> tuple[str, dict[int, float]]:
    start = (EPOCH + dt.timedelta(days=cutoff - LOOKBACK_DAYS - 5)).isoformat()
    end = (EPOCH + dt.timedelta(days=cutoff + 1)).isoformat()
    url = NASDAQ.format(symbol=symbol.replace("-", "."), start=start, end=end)
    try:
        response = http.get(url, headers=HEADERS)
    except Exception as exc:  # noqa: BLE001 - Netz: nur zählen
        return f"fehler_{type(exc).__name__}", {}
    if response.status_code != 200:
        return f"http_{response.status_code}", {}
    try:
        data = parse_nasdaq(response.json())
    except ValueError:
        return "kein_json", {}
    return ("ok" if data else "keine_kurse"), data


def fetch_yahoo(http, symbol: str, cutoff: int) -> tuple[str, dict[int, float]]:
    """Heutige Tageskurse bei Yahoo für denselben Zeitraum (Gegenprobe; eigene Auswertung, siehe ``parse_yahoo``)."""
    start = (cutoff - LOOKBACK_DAYS - 5) * 86400
    end = (cutoff + 2) * 86400
    try:
        response = http.get(YAHOO.format(symbol=symbol, start=start, end=end), headers=YAHOO_HEADERS)
    except Exception as exc:  # noqa: BLE001 - Netz: nur zählen
        return f"fehler_{type(exc).__name__}", {}
    if response.status_code != 200:
        return f"http_{response.status_code}", {}
    try:
        data = parse_yahoo(response.json())
    except ValueError:
        return "kein_json", {}
    return ("ok" if data else "keine_kurse"), data


def run(stand: nachrechnen.Stand, sid: str, http) -> dict:
    manifest = stand.get("manifest.bin")
    instruments = stand.get("instruments.bin")
    cutoff = int(manifest["cutoff_day"])
    chosen, from_top = select(stand, instruments, sid)
    returns = window_returns(stand, set(chosen))
    totals: Counter = Counter()
    sources: Counter = Counter()
    yahoo_sources: Counter = Counter()
    stocks_with_issue: Counter = Counter()
    missing_shapes: Counter = Counter()
    patterns: list[dict] = []
    top = set(chosen[:from_top])
    for i in chosen:
        symbol = str(instruments["symbol"][i])
        status, fresh = fetch(http, symbol, cutoff)
        sources[status] += 1
        if status != "ok":
            # nur die Form des Kürzels (keine Kürzel selbst): mit Bindestrich (Aktiengattung) oder ohne, Länge
            missing_shapes[f"{'mit Bindestrich' if '-' in symbol else 'ohne Bindestrich'}, {len(symbol)} Zeichen"] += 1
            continue
        yahoo_status, yahoo = fetch_yahoo(http, symbol, cutoff)
        yahoo_sources[yahoo_status] += 1
        series = stand.get(f"series/{instruments['isin'][i]}.bin")
        stand.drop(f"series/{instruments['isin'][i]}.bin")
        diag: dict = {}
        counts = compare_stock(series, fresh, returns.get(i, {}), cutoff, diag, yahoo if yahoo_status == "ok" else None)
        totals.update(counts)
        for name in ("tag_gross", "tag_klein", "tag_faktor", "tag_nachbartag", "rendite_abweichend", "yahoo_abweichend", "abweichung_unerklaert", "abweichung_kursmeldung"):
            if counts.get(name):
                stocks_with_issue[name] += 1
        if any(counts.get(name) for name in ("tag_gross", "tag_klein", "tag_faktor", "tag_nachbartag", "rendite_abweichend")):
            patterns.append({"unter_den_ersten_10": i in top, "gross": counts.get("tag_gross", 0), "klein": counts.get("tag_klein", 0),
                             "renditen_abweichend": counts.get("rendite_abweichend", 0), **diag})
    return {
        "stand": sid,
        "stichtag": nachrechnen._iso(cutoff),
        "abgerufen_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "ausgewaehlt": len(chosen),
        "davon_aus_den_ersten_10": from_top,
        "abruf": dict(sources),
        "yahoo_abruf": dict(yahoo_sources),
        "ohne_kurse_bei_nasdaq": dict(missing_shapes),
        "zaehler": dict(totals),
        "aktien_mit": dict(stocks_with_issue),
        # ohne Namen, Kürzel oder Kurse: nur Muster der Aktien mit abweichenden Kursen oder Renditen
        "aktien_mit_abweichung": len(patterns),
        "muster": sorted(patterns, key=lambda p: (-p.get("ursachen", {}).get("unerklaert", 0), -p["gross"], -p["renditen_abweichend"]))[:20],
    }


def verdict(report: dict) -> tuple[str, list[str]]:
    """Urteil der Gegenprüfung (siehe Modulbeschreibung): „bestanden“, „bestanden_mit_anbieterunterschieden“ oder
    „nicht_bestanden“ – mit den Gründen."""
    z = report["zaehler"]
    found = report["abruf"].get("ok", 0)
    reasons = []
    if found < report["ausgewaehlt"] * 0.5:
        reasons.append(f"Nasdaq nur für {found} von {report['ausgewaehlt']} Aktien mit Kursen")
    yahoo_ok = (report.get("yahoo_abruf") or {}).get("ok", 0)
    if yahoo_ok < found * 0.9:
        reasons.append(f"Gegenprobe bei Yahoo nur für {yahoo_ok} von {found} Aktien")
    for cause in ("unerklaert", "ohne_yahoo_kurs"):
        days, rets = z.get(f"abweichung_{cause}", 0), z.get(f"rendite_abweichend_{cause}", 0)
        if days or rets:
            reasons.append(f"Abweichungen {CAUSE_TEXT[cause]}: {days} Kurstage, {rets} Renditen")
    if reasons:
        return "nicht_bestanden", reasons
    deviations = sum(z.get(f"tag_{kind}", 0) for kind in ("faktor", "nachbartag", "klein", "gross")) + z.get("rendite_abweichend", 0)
    if deviations:
        return "bestanden_mit_anbieterunterschieden", [
            f"jede Abweichung belegt: wie Yahoo {z.get('abweichung_wie_yahoo', 0)} Kurstage und {z.get('rendite_abweichend_wie_yahoo', 0)} Renditen, "
            f"vorläufig aus der Kursmeldung {z.get('abweichung_kursmeldung', 0)} Kurstage und {z.get('rendite_abweichend_kursmeldung', 0)} Renditen"
        ]
    return "bestanden", []


def chunked(lines: list[str], limit: int = MAX_ANNOTATION_BYTES) -> list[list[str]]:
    """Zeilen auf mehrere Hinweise verteilen, damit GitHub keinen abschneidet (jede Zeile bleibt ganz)."""
    out: list[list[str]] = []
    current: list[str] = []
    size = 0
    for line in lines:
        add = len(line.encode("utf-8")) + 3
        if current and size + add > limit:
            out.append(current)
            current, size = [], 0
        current.append(line)
        size += add
    if current:
        out.append(current)
    return out


def _title(text: str) -> str:
    """Titel eines Hinweises: GitHub trennt die Angaben vor „::“ an Kommas – ein Komma im Titel schnitt ihn bis 1.18.0 ab
    („bestanden, Anbieter unterscheiden sich“ erschien als „bestanden“). Kodiert wie im Werkzeugkasten von GitHub."""
    return text.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A").replace(",", "%2C")


def _causes(counts: dict) -> str:
    return ", ".join(f"{CAUSE_TEXT[c]} {counts[c]}" for c in CAUSES if counts.get(c)) or "–"


def annotations(report: dict) -> list[str]:
    z, a = report["zaehler"], report["aktien_mit"]
    found = report["abruf"].get("ok", 0)
    result, reasons = verdict(report)
    head = (
        f"Nachträglich bei Nasdaq abgerufen am {report['abgerufen_utc']} (anderer Anbieter als Yahoo) und zur Gegenprobe bei Yahoo (Quelle der App) – "
        f"beweist nicht, welche Kurse ein anderes Modell damals hatte. Stand {report['stand']} (Kursstand {report['stichtag']})"
    )
    verdict_text = {
        "bestanden": "BESTANDEN – alle Kurse und Renditen wie bei Nasdaq",
        "bestanden_mit_anbieterunterschieden": "BESTANDEN MIT UNTERSCHIEDEN ZWISCHEN DEN ANBIETERN – " + "; ".join(reasons),
        "nicht_bestanden": "NICHT BESTANDEN – " + "; ".join(reasons),
    }[result]
    lines = [
        head,
        f"Urteil: {verdict_text}",
        f"Auswahl: {report['ausgewaehlt']} US-Aktien, davon {report['davon_aus_den_ersten_10']} aus den ersten 10 einer Rangliste; bei Nasdaq gefunden {found} "
        f"(Abruf: {', '.join(f'{k} {v}' for k, v in sorted(report['abruf'].items()))}); Gegenprobe Yahoo: {', '.join(f'{k} {v}' for k, v in sorted((report.get('yahoo_abruf') or {}).items())) or '–'}",
        f"Schlusskurse je Börsentag: {z.get('tage_verglichen', 0)} verglichen – gleich {z.get('tag_gleich', 0)} (innerhalb der Rundung), "
        f"Faktor (Split) {z.get('tag_faktor', 0)}, Kurs eines Nachbartags {z.get('tag_nachbartag', 0)}, klein (≤ 0,5 %) {z.get('tag_klein', 0)}, "
        f"groß {z.get('tag_gross', 0)}; Aktien mit großer Abweichung {a.get('tag_gross', 0)}, mit kleiner {a.get('tag_klein', 0)}",
        f"Ursache der abweichenden Kurstage: {_causes({c: z.get(f'abweichung_{c}', 0) for c in CAUSES})}",
        f"Fehlende Börsentage: nur im Stand {z.get('nur_im_stand', 0)}, nur bei Nasdaq {z.get('nur_bei_nasdaq', 0)} – davon in der App als "
        f"fehlender Kurstag gezählt {z.get('nur_bei_nasdaq_als_fehlender_tag_gezaehlt', 0)}, nach dem letzten Kurs des Stands "
        f"{z.get('nur_bei_nasdaq_nach_letztem_kurs_des_stands', 0)}, ohne Sitzung im Stand {z.get('nur_bei_nasdaq_ohne_sitzung_im_stand', 0)}; "
        f"Yahoo hat heute einen Kurs an {z.get('nur_bei_nasdaq_yahoo_heute_mit_kurs', 0)} dieser Tage",
        f"Renditen 1–90 Tage aus Nasdaq-Kursen an denselben Tagen: {z.get('renditen_verglichen', 0)} verglichen – gleich {z.get('rendite_gleich', 0)}, "
        f"abweichend {z.get('rendite_abweichend', 0)} (Aktien {a.get('rendite_abweichend', 0)}; Ursache: {_causes({c: z.get(f'rendite_abweichend_{c}', 0) for c in CAUSES})}); "
        f"ohne Nasdaq-Kurs an Start oder Ende {z.get('rendite_ohne_nasdaq_kurs', 0)}",
        f"Stand gegen Yahoo heute (alle Tage der Auswahl): {z.get('yahoo_tage_verglichen', 0)} verglichen – gleich {z.get('yahoo_gleich', 0)}, "
        f"abweichend {z.get('yahoo_abweichend', 0)} (davon vorläufig aus der Kursmeldung {z.get('yahoo_abweichend_kursmeldung', 0)}; Aktien {a.get('yahoo_abweichend', 0)}); "
        f"Tage des Stands ohne Yahoo-Kurs heute {z.get('nicht_bei_yahoo', 0)}",
    ]
    if report.get("ohne_kurse_bei_nasdaq"):
        lines.append("Ohne Kurse bei Nasdaq (Form des Kürzels): " + ", ".join(f"{k} {v}" for k, v in sorted(report["ohne_kurse_bei_nasdaq"].items())))
    patterns = []
    for k, p in enumerate(report.get("muster") or [], start=1):
        ratio = p.get("verhaeltnis") or ["–", "–", "–"]
        patterns.append(
            f"Muster {k} (unter den ersten 10: {'ja' if p['unter_den_ersten_10'] else 'nein'}, {p.get('kursbereich', '–')}): {p.get('abweichend', 0)} von {p.get('tage', 0)} Tagen abweichend "
            f"(groß {p['gross']}, klein {p['klein']}, Cent {p.get('cent', 0)}; Ursache: {_causes(p.get('ursachen') or {})}); "
            f"Stand/Nasdaq {ratio[0]}–{ratio[2]} (Median {ratio[1]}, {'konstant' if p.get('konstant') else 'nicht konstant'}); "
            f"Abweichungen {p.get('erste_abweichung_tage_vor_stichtag', '–')} bis {p.get('letzte_abweichung_tage_vor_stichtag', '–')} Tage vor dem Stichtag, danach {p.get('danach_gleich', 0)} Tage gleich; "
            f"Renditen abweichend {p['renditen_abweichend']} (größte {p.get('groesste_renditeabweichung_pp', 0)} Prozentpunkte; Ursache: {_causes(p.get('renditen_ursachen') or {})})"
        )
    level = {"bestanden": "notice", "bestanden_mit_anbieterunterschieden": "warning", "nicht_bestanden": "error"}[result]
    title = {
        "bestanden": "Kurse unabhängig gegengeprüft (Nasdaq): bestanden",
        "bestanden_mit_anbieterunterschieden": "Kurse unabhängig gegengeprüft (Nasdaq): bestanden, Anbieter unterscheiden sich",
        "nicht_bestanden": "Kurse unabhängig gegengeprüft (Nasdaq): NICHT bestanden",
    }[result]

    def encode(rows: list[str]) -> str:
        return "%0A".join(row.replace("%", "%25") for row in rows)

    out = [f"::{level} title={_title(title)}::{encode(part)}" for part in chunked(lines)]
    if patterns:
        parts = chunked(patterns)
        shown = len(report.get("muster") or [])
        total = report.get("aktien_mit_abweichung", shown)
        for n, part in enumerate(parts, start=1):
            pattern_title = f"Kurse gegengeprüft – Muster der Abweichungen ({n}/{len(parts)}; {shown} von {total} Aktien, ohne Kurse und Namen)"
            out.append(f"::{'error' if result == 'nicht_bestanden' else 'notice'} title={_title(pattern_title)}::{encode(part)}")
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", "szymeklh87-commits/tr-aktienvergleich"))
    parser.add_argument("--bericht", type=Path, help="Ergebnis als JSON (nur Zählwerte)")
    args = parser.parse_args(argv)
    from traktien.providers.http import HttpClient

    http = HttpClient(impersonate="chrome", max_retries=2, timeout=25, min_interval={"api.nasdaq.com": 0.4, "query2.finance.yahoo.com": 0.3})
    with tempfile.TemporaryDirectory() as temp:
        meta, stands = nachrechnen.load_release_stands(args.repo, os.environ.get("GITHUB_TOKEN"), Path(temp), None)
        key = nachrechnen.key_for(meta["descriptor"])
        official = meta["status"].get("latest_official_snapshot_id")
        folder = dict(stands).get(official)
        if folder is None:
            print("::error title=Kurse gegenprüfen::Stand mit Schlusskursen nicht im Release gefunden")
            return 1
        report = run(nachrechnen.Stand(folder, official, key), official, http)
    for line in annotations(report):
        print(line)
    if args.bericht:
        args.bericht.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return 1 if verdict(report)[0] == "nicht_bestanden" else 0


if __name__ == "__main__":
    started = time.monotonic()
    try:
        code = main()
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 - Abbruchgrund als Hinweis, ohne Inhalte
        print(f"::error title=Kurse gegenprüfen abgebrochen::{type(exc).__name__}: {str(exc).splitlines()[0][:200] if str(exc) else ''}")
        code = 1
    print(f"::notice title=Kurse gegenprüfen::Dauer {round(time.monotonic() - started)} s")
    sys.exit(code)
