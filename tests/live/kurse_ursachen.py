"""Ursachen der Kursunterschiede zwischen Yahoo und Nasdaq und ihre Wirkung auf die Ranglisten (ab 1.18.1).

Simons Auftrag vom 24.10.2026, 21:23 Uhr: „‚Entspricht Yahoo‘ reicht nicht als unabhängiger Nachweis korrekter
Börsenkurse. Untersuche besonders die betroffenen Aktien in den Top 10. Prüfe anhand verfügbarer Quellen unter anderem
Kursdefinition, Handelsdatum, Bereinigung und Kapitalmaßnahmen. Weise Ursachen nur dann als geklärt aus, wenn sie belegt
sind. Ermittle, ob und wie die Unterschiede die Ranglisten verändern. Keine kostenpflichtigen Dienste buchen.“

Die Gegenprüfung (``kurse_gegenpruefen.py``) zeigt, *dass* Stand und Nasdaq an manchen Tagen verschiedene Schlusskurse
haben und dass der Stand dort den Yahoo-Kurs trägt. Dieses Skript sucht für jeden abweichenden Tag einen **Beleg** aus
frei zugänglichen Quellen (nachträglich abgerufen, keine kostenpflichtigen Dienste):

1. **Kursdefinition – offizieller Schlusskurs:** Bei Aktien mit Heimatbörse Nasdaq der „Nasdaq Official Closing Price“
   (NOCP, Historie auf nasdaq.com). Ist der Nasdaq-Kurs der NOCP und der Yahoo-Kurs nicht, ist belegt, dass Yahoo an
   diesem Tag nicht den offiziellen Schlusskurs der Heimatbörse führt.
2. **Kursdefinition – letzter Abschluss:** Minutenkurse von Yahoo (nur die letzten fünf Sitzungen abrufbar): Ist der
   Yahoo-Tagesschluss der letzte Abschluss vor 16:00 Uhr New York und der Nasdaq-Kurs ein anderer, ist belegt, dass Yahoo
   den letzten Abschluss führt und Nasdaq einen anderen Schlusskurs (Schlussauktion bzw. offizieller Kurs).
3. **Handelsdatum und Handel:** Umsatz beider Quellen am Tag; ein Tag ohne Umsatz mit dem Kurs des Vortags ist belegt als
   „kein Handel, Kurs fortgeschrieben“; Tage, die nur eine Quelle führt.
4. **Bereinigung:** Nasdaq-Kurs gleich dem dividendenbereinigten Yahoo-Kurs (``adjclose``) statt dem splitbereinigten.
5. **Kapitalmaßnahmen:** Splits und Dividenden laut Yahoo und Dividenden laut Nasdaq im Zeitraum; ein konstanter Faktor
   vor einem solchen Tag.

Was keiner dieser Belege trifft, bleibt **ungeklärt** – auch wenn es dem Yahoo-Kurs entspricht.

**Wirkung auf die Ranglisten:** Alle Ranglisten (Gruppe A und B, 11 Gewichtungen, 1–90 Tage) werden mit der unabhängigen
Rechnung aus ``nachrechnen.py`` zweimal gerechnet – mit den Kursen des Stands und mit den Nasdaq-Kursen an den abweichenden
Tagen (sonst dieselben Kurse, dieselbe Zulassung zu Gruppe B); gezählt werden geänderter Platz 1, andere Aktien unter den
ersten 10 und andere Reihenfolge. Geprüft sind die US-Aktien unter den ersten 20 irgendeiner Rangliste und 150 zufällig
gewählte; was mit Aktien dahinter wäre, zeigt das nicht.

Ausgegeben werden nur Zählwerte, Kursbereiche und Buchstaben statt Namen (das Protokoll ist öffentlich). Nachträglich
abgerufene Kurse sind keine Originaldaten und belegen nicht, welche Kurse ein anderes Modell damals hatte.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import random
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "backend"))

import kurse_gegenpruefen as gegen  # noqa: E402 - Nasdaq-/Yahoo-Abruf und Einordnung je Tag
import nachrechnen  # noqa: E402 - Datenstand lesen, unabhängige Ranglisten

EPOCH = dt.date(1970, 1, 1)
TOP_SELECT = 20
RANDOM_EXTRA = 150
MAX_STOCKS = 900
MAX_ROWS = 40  # Zeilen je Aktie in den Hinweisen (GitHub zeigt je Schritt höchstens 10 Hinweise einer Art)
NASDAQ_LISTED = {"NMS", "NGM", "NCM", "NAS", "NASDAQ", "NasdaqGS", "NasdaqGM", "NasdaqCM"}
NOCP_URLS = (
    "https://api.nasdaq.com/api/company/{symbol}/historical-nocp?timeframe=y1",
    "https://api.nasdaq.com/api/company/{symbol}/historical-nocp?timeframe=m3",
)
NASDAQ_DIVIDENDS = "https://api.nasdaq.com/api/quote/{symbol}/dividends?assetclass=stocks"
YAHOO_DAILY = "https://query2.finance.yahoo.com/v8/finance/chart/{symbol}?period1={start}&period2={end}&interval=1d&events=div%7Csplit&includeAdjustedClose=true"
YAHOO_MINUTES = "https://query2.finance.yahoo.com/v8/finance/chart/{symbol}?range=5d&interval=1m&includePrePost=false"
CAUSES = (
    "offizieller_schlusskurs",
    "letzter_abschluss",
    "kein_handel",
    "dividendenbereinigung",
    "split",
    "ungeklaert",
)
CAUSE_TEXT = {
    "offizieller_schlusskurs": "Yahoo nicht der offizielle Schlusskurs der Heimatbörse (Nasdaq-Kurs = NOCP)",
    "letzter_abschluss": "Yahoo = letzter Abschluss vor 16:00 Uhr, Nasdaq ein anderer Schlusskurs",
    "kein_handel": "kein Umsatz, Kurs des Vortags fortgeschrieben",
    "dividendenbereinigung": "Nasdaq-Kurs = dividendenbereinigter Yahoo-Kurs",
    "split": "Faktor eines Splits",
    "ungeklaert": "ungeklärt",
}


def day_of_iso(text: str) -> int:
    return (dt.date.fromisoformat(text) - EPOCH).days


def price(text) -> float | None:
    return gegen.price(text)


def number(text) -> float | None:
    """„1,234,567“ → 1234567.0; leer/„N/A“ → None (Umsatz bei Nasdaq)."""
    if text is None:
        return None
    try:
        return float(str(text).replace(",", "").replace("$", "").strip())
    except ValueError:
        return None


def parse_nasdaq_rows(payload: dict) -> dict[int, dict]:
    """Nasdaq-Historie je Tag: Schlusskurs und Umsatz."""
    rows = (((payload or {}).get("data") or {}).get("tradesTable") or {}).get("rows") or []
    out: dict[int, dict] = {}
    for row in rows:
        close = price(row.get("close"))
        if close is None or not row.get("date"):
            continue
        out[gegen.day_of(row["date"])] = {"close": close, "volume": number(row.get("volume"))}
    return out


def parse_nocp(payload) -> tuple[dict[int, float], list[str]]:
    """NOCP-Historie ohne feste Feldnamen: jede Liste von Einträgen mit einem Datum (MM/TT/JJJJ) und einem Kurs. Rückgabe:
    Kurs je Tag und die Feldnamen des ersten Eintrags (zur Kontrolle im Protokoll, ohne Werte)."""
    found: dict[int, float] = {}
    fields: list[str] = []

    def walk(node) -> None:
        if isinstance(node, dict):
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                if isinstance(item, dict):
                    day = value = None
                    for name, v in item.items():
                        if isinstance(v, str) and day is None and len(v) == 10 and v[2] == "/" and v[5] == "/":
                            try:
                                day = gegen.day_of(v)
                            except ValueError:
                                day = None
                        elif value is None and str(name).lower() in ("price", "nocp", "close", "value") and isinstance(v, (str, int, float)):
                            value = price(v)
                    if day is not None and value is not None:
                        found[day] = value
                        if not fields:
                            fields.extend(str(k) for k in item)
                walk(item)

    walk(payload)
    return found, fields


def parse_yahoo_daily(payload: dict) -> dict:
    """Yahoo-Tageskerzen mit Umsatz, dividendenbereinigtem Kurs, Ereignissen und Börse (eigene Auswertung)."""
    results = (((payload or {}).get("chart") or {}).get("result")) or []
    result = (results[0] if results else {}) or {}
    meta = result.get("meta") or {}
    offset = int(meta.get("gmtoffset") or 0)
    stamps = result.get("timestamp") or []
    quote = ((result.get("indicators") or {}).get("quote") or [{}])[0] or {}
    adj = ((result.get("indicators") or {}).get("adjclose") or [{}])[0] or {}
    closes, volumes, adjcloses = quote.get("close") or [], quote.get("volume") or [], adj.get("adjclose") or []
    days: dict[int, dict] = {}
    for k, ts in enumerate(stamps):
        if ts is None:
            continue
        close = closes[k] if k < len(closes) else None
        if close is None:
            continue
        day = (int(ts) + offset) // 86400
        days[day] = {
            "close": float(close),
            "volume": None if k >= len(volumes) or volumes[k] is None else float(volumes[k]),
            "adjclose": None if k >= len(adjcloses) or adjcloses[k] is None else float(adjcloses[k]),
        }
    events = result.get("events") or {}
    splits = sorted(((int(e["date"]) + offset) // 86400, float(e.get("numerator") or 0) / float(e.get("denominator") or 1)) for e in (events.get("splits") or {}).values() if e.get("date"))
    dividends = sorted((int(e["date"]) + offset) // 86400 for e in (events.get("dividends") or {}).values() if e.get("date"))
    return {"days": days, "splits": splits, "dividends": dividends, "exchange": meta.get("exchangeName"), "offset": offset}


def parse_yahoo_minutes(payload: dict) -> dict[int, float]:
    """Letzter Abschluss der regulären Sitzung je Tag aus den Minutenkursen von Yahoo (Kerze vor 16:00 Uhr New York)."""
    results = (((payload or {}).get("chart") or {}).get("result")) or []
    result = (results[0] if results else {}) or {}
    offset = int((result.get("meta") or {}).get("gmtoffset") or 0)
    stamps = result.get("timestamp") or []
    closes = (((result.get("indicators") or {}).get("quote") or [{}])[0] or {}).get("close") or []
    last: dict[int, tuple[int, float]] = {}
    for ts, close in zip(stamps, closes):
        if ts is None or close is None:
            continue
        local = int(ts) + offset
        day, second = local // 86400, local % 86400
        if second >= 16 * 3600:  # Kerzen ab 16:00 Uhr gehören nicht zur regulären Sitzung
            continue
        if day not in last or second >= last[day][0]:
            last[day] = (second, float(close))
    return {day: value for day, (_, value) in last.items()}


def parse_nasdaq_dividends(payload: dict) -> list[int]:
    rows = ((((payload or {}).get("data") or {}).get("dividends") or {}).get("rows")) or []
    out = []
    for row in rows:
        text = row.get("exOrEffDate") or row.get("exDate")
        if text and len(str(text)) == 10:
            try:
                out.append(gegen.day_of(str(text)))
            except ValueError:
                continue
    return sorted(out)


def same(a: float | None, b: float | None) -> bool:
    """Gleich innerhalb der Rundung der Quellen (Cent ab 1 $, 1/100 Cent darunter)."""
    if a is None or b is None:
        return False
    return abs(a - b) <= gegen.tolerance(b)


def day_cause(
    day: int,
    own: float,
    nasdaq: dict,
    yahoo: dict,
    nocp: dict[int, float] | None,
    minutes: dict[int, float],
    previous_own: float | None,
    previous_nasdaq: float | None,
    kind: str,
) -> tuple[str, str]:
    """Ursache eines abweichenden Tags mit Beleg (Name, kurze Begründung ohne Kurse). Reihenfolge: die stärkste Quelle zuerst;
    ohne passenden Beleg „ungeklärt“ – auch wenn der Kurs des Stands der Yahoo-Kurs ist."""
    n = nasdaq.get(day) or {}
    y = (yahoo.get("days") or {}).get(day) or {}
    n_close = n.get("close")
    if kind == "faktor":
        return "split", "konstanter Faktor"
    if nocp is not None and day in nocp and same(n_close, nocp[day]) and not same(own, nocp[day]):
        return "offizieller_schlusskurs", "Nasdaq = NOCP, Stand ≠ NOCP"
    if day in minutes and same(own, minutes[day]) and not same(n_close, minutes[day]):
        return "letzter_abschluss", "Stand = letzter Minutenkurs vor 16:00, Nasdaq anders"
    volume_y, volume_n = y.get("volume"), n.get("volume")
    if previous_own is not None and own == previous_own and volume_y == 0:
        return "kein_handel", "Yahoo: Umsatz 0, Kurs des Vortags"
    if previous_nasdaq is not None and n_close == previous_nasdaq and volume_n == 0:
        return "kein_handel", "Nasdaq: Umsatz 0, Kurs des Vortags"
    if y.get("adjclose") is not None and same(n_close, y["adjclose"]) and not same(n_close, y.get("close")):
        return "dividendenbereinigung", "Nasdaq = adjclose"
    return "ungeklaert", ""


def window_values(days: np.ndarray, closes: np.ndarray, start: int, min_trend: int) -> tuple[float, float | None, int]:
    """Rendite, R² und Trend-Status (15–18) eines Zeitraums ab ``start`` bis zum letzten Kurs – Regeln wie nachrechnen.py."""
    j = int(np.searchsorted(days, start))
    p = closes[j:]
    r = float(p[-1] / p[0] - 1.0)
    n = len(p)
    r2 = nachrechnen.Nachrechnung._r2(p) if n >= min_trend else None
    if n < min_trend:
        status = 15
    elif not (r > 0.0) or not nachrechnen.Nachrechnung._slope_positive(p):
        status = 16
    elif r2 is None:
        status = 17
    else:
        status = 18
    return r, r2, status


def compare_orders(before: list[int], after: list[int]) -> dict[str, bool]:
    return {
        "spitze": (before[0] if before else None) != (after[0] if after else None),
        "top10_aktien": set(before[:10]) != set(after[:10]),
        "top10_reihenfolge": before[:10] != after[:10],
        "reihenfolge": before != after,
    }


def lists_of(group: dict) -> dict:
    """Alle Ranglisten einer Gruppe aus ``nachrechnen.rank_group``: 0/100 (reine Rendite) und die gewichteten."""
    out = {"0": group["v0"].tolist()}
    for w in nachrechnen.WEIGHTS:
        if w:
            out[str(w)] = group["u"][w].tolist()
    return out


def select(stand: nachrechnen.Stand, instruments: dict, sid: str) -> tuple[list[int], dict[int, int], dict[int, int], int]:
    """US-Aktien unter den ersten 20 einer Rangliste und zufällig gewählte; je Aktie die Zahl der Ranglisten mit ihr unter
    den ersten 10 bzw. auf Platz 1."""
    n = len(instruments["isin"])
    calendar = instruments.get("calendar") or [None] * n
    key = instruments.get("exchange_key") or [None] * n
    symbol = instruments.get("symbol") or [None] * n
    has_series = instruments.get("has_series") or [True] * n
    us = {i for i in range(n) if calendar[i] == "XNYS" and key[i] != "OTC" and symbol[i] and "." not in str(symbol[i]) and has_series[i]}
    top: set[int] = set()
    top10: Counter = Counter()
    first: Counter = Counter()
    for h in range(1, 91):
        win = stand.get(f"windows/{h}.full.bin")
        orders = win["orders"]
        lists = [orders.get("v0") or [], orders.get("v0l") or []]
        for group in ("u", "ul"):
            lists += [values for w, values in (orders.get(group) or {}).items() if str(w) != "0"]
        for values in lists:
            head = [int(i) for i in values[:TOP_SELECT]]
            top.update(i for i in head if i in us)
            for k, i in enumerate(head[:10]):
                if i in us:
                    top10[i] += 1
                    if k == 0:
                        first[i] += 1
        stand.drop(f"windows/{h}.full.bin")
    rest = sorted(us - top)
    extra = random.Random(sid).sample(rest, min(RANDOM_EXTRA, len(rest)))
    chosen = sorted(top)[: MAX_STOCKS - len(extra)] + sorted(extra)
    return chosen, dict(top10), dict(first), len(top)


def get_json(http, url: str, headers: dict | None = None) -> tuple[str, dict | None]:
    try:
        response = http.get(url, headers=headers or {})
    except Exception as exc:  # noqa: BLE001 - Netz: nur zählen
        return f"fehler_{type(exc).__name__}", None
    if response.status_code != 200:
        return f"http_{response.status_code}", None
    try:
        return "ok", response.json()
    except ValueError:
        return "kein_json", None


def run(stand: nachrechnen.Stand, sid: str, http) -> dict:
    manifest = stand.get("manifest.bin")
    instruments = stand.get("instruments.bin")
    cutoff = int(manifest["cutoff_day"])
    min_trend = int((manifest.get("method") or {}).get("min_obs_trend", 15))
    liquid = (instruments.get("turnover") or {}).get("liquid") or [False] * len(instruments["isin"])
    chosen, top10, first, from_top = select(stand, instruments, sid)
    start_day = cutoff - gegen.LOOKBACK_DAYS - 5
    sources: Counter = Counter()
    days_total: Counter = Counter()
    causes: Counter = Counter()
    nocp_probe: Counter = Counter()
    events: Counter = Counter()
    only: Counter = Counter()
    nocp_fields: set[str] = set()
    stocks: list[dict] = []
    substituted: dict[int, tuple[np.ndarray, np.ndarray, set[int]]] = {}
    for i in chosen:
        symbol = str(instruments["symbol"][i])
        nasdaq_symbol = symbol.replace("-", ".")
        status, payload = get_json(http, gegen.NASDAQ.format(symbol=nasdaq_symbol, start=(EPOCH + dt.timedelta(days=start_day)).isoformat(), end=(EPOCH + dt.timedelta(days=cutoff + 1)).isoformat()), gegen.HEADERS)
        nasdaq = parse_nasdaq_rows(payload) if status == "ok" else {}
        sources[f"nasdaq_{status if nasdaq or status != 'ok' else 'keine_kurse'}"] += 1
        if not nasdaq:
            continue
        status, payload = get_json(http, YAHOO_DAILY.format(symbol=symbol, start=start_day * 86400, end=(cutoff + 2) * 86400), gegen.YAHOO_HEADERS)
        yahoo = parse_yahoo_daily(payload) if status == "ok" else {"days": {}, "splits": [], "dividends": []}
        sources[f"yahoo_{status}"] += 1
        series = stand.get(f"series/{instruments['isin'][i]}.bin")
        stand.drop(f"series/{instruments['isin'][i]}.bin")
        d = [int(x) for x in series.get("d") or []]
        c = [None if x is None else float(x) for x in series.get("c") or []]
        own = {day: close for day, close in zip(d, c) if close is not None and close > 0 and day >= start_day and day <= cutoff}
        if not own:
            continue
        fresh_days = sorted(k for k in nasdaq if start_day <= k <= cutoff)
        deviating: list[tuple[int, str]] = []
        for day, close in own.items():
            if day not in nasdaq:
                only["nur_im_stand"] += 1
                if ((yahoo["days"].get(day) or {}).get("volume")) == 0:
                    only["nur_im_stand_ohne_umsatz_bei_yahoo"] += 1
                continue
            k = fresh_days.index(day)
            neighbours = [nasdaq[fresh_days[j]]["close"] for j in (k - 1, k + 1) if 0 <= j < len(fresh_days)]
            kind = gegen.classify(close, nasdaq[day]["close"], neighbours)
            days_total["verglichen"] += 1
            if kind != "gleich":
                deviating.append((day, kind))
        if not deviating:
            continue
        exchange = yahoo.get("exchange") or "–"
        nocp = None
        if exchange in NASDAQ_LISTED:
            for url in NOCP_URLS:
                status, payload = get_json(http, url.format(symbol=nasdaq_symbol), gegen.HEADERS)
                nocp_probe[status] += 1
                rows, fields = parse_nocp(payload) if status == "ok" else ({}, [])
                if rows:
                    nocp = rows
                    nocp_probe["mit_kursen"] += 1
                    nocp_fields.update(fields)
                    break
        status, payload = get_json(http, YAHOO_MINUTES.format(symbol=symbol), gegen.YAHOO_HEADERS)
        minutes = parse_yahoo_minutes(payload) if status == "ok" else {}
        sources[f"minuten_{status}"] += 1
        status, payload = get_json(http, NASDAQ_DIVIDENDS.format(symbol=nasdaq_symbol), gegen.HEADERS)
        nasdaq_dividends = parse_nasdaq_dividends(payload) if status == "ok" else []
        window_events = {
            "yahoo_dividende": sum(1 for x in yahoo.get("dividends") or [] if start_day <= x <= cutoff),
            "yahoo_split": sum(1 for x, _ in yahoo.get("splits") or [] if start_day <= x <= cutoff),
            "nasdaq_dividende": sum(1 for x in nasdaq_dividends if start_day <= x <= cutoff),
        }
        for name, count in window_events.items():
            if count:
                events[name] += 1
        per_stock: Counter = Counter()
        ordered = sorted(own)
        for day, kind in deviating:
            k = ordered.index(day)
            previous = own[ordered[k - 1]] if k > 0 else None
            m = fresh_days.index(day)
            previous_n = nasdaq[fresh_days[m - 1]]["close"] if m > 0 else None
            cause, _ = day_cause(day, own[day], nasdaq, yahoo, nocp, minutes, previous, previous_n, kind)
            per_stock[cause] += 1
            causes[cause] += 1
            days_total["abweichend"] += 1
            if day in minutes:
                days_total["abweichend_mit_minutenkursen"] += 1
            if nocp is not None and day in nocp:
                days_total["abweichend_mit_nocp"] += 1
        values = sorted(nasdaq[day]["close"] for day in nasdaq)
        stocks.append(
            {
                "idx": i,
                "top10": int(top10.get(i, 0)),
                "platz1": int(first.get(i, 0)),
                "kursbereich": next(label for limit, label in ((1, "unter 1 $"), (10, "1–10 $"), (100, "10–100 $"), (float("inf"), "über 100 $")) if values[len(values) // 2] < limit),
                "boerse": "Nasdaq" if exchange in NASDAQ_LISTED else {"NYQ": "NYSE", "NYS": "NYSE", "ASE": "NYSE American", "PCX": "NYSE Arca", "BTS": "Cboe BZX"}.get(exchange, "andere"),
                "abweichend": len(deviating),
                "groesste_abweichung_pct": round(100 * max(abs(own[day] / nasdaq[day]["close"] - 1) for day, _ in deviating), 2),
                "ursachen": dict(per_stock),
                "nocp_abrufbar": nocp is not None,
                "minutenkurse_tage": len(minutes),
                "ereignisse": window_events,
            }
        )
        # Szenario „Nasdaq“: an den abweichenden Tagen der Nasdaq-Kurs, sonst der Kurs des Stands
        changed = dict(own)
        for day, _ in deviating:
            changed[day] = nasdaq[day]["close"]
        days_arr = np.array(sorted(changed), dtype=np.int64)
        substituted[i] = (days_arr, np.array([changed[x] for x in days_arr.tolist()], dtype=np.float64), {day for day, _ in deviating})
    effect, top_moves = ranking_effect(stand, substituted, liquid, min_trend, {s["idx"] for s in stocks if s["top10"]})
    letters = {s["idx"]: chr(ord("A") + k) if k < 26 else f"Z{k}" for k, s in enumerate(sorted(stocks, key=lambda s: (-s["top10"], -s["abweichend"])))}
    for s in stocks:
        s["aktie"] = letters[s["idx"]]
        s["rangwirkung"] = top_moves.get(s["idx"], {})
        del s["idx"]
    return {
        "stand": sid,
        "stichtag": nachrechnen._iso(cutoff),
        "abgerufen_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "ausgewaehlt": len(chosen),
        "davon_aus_den_ersten_20": from_top,
        "abruf": dict(sources),
        "nocp_abruf": dict(nocp_probe),
        "nocp_felder": sorted(nocp_fields),
        "tage": dict(days_total),
        "nur_eine_quelle": dict(only),
        "ursachen": dict(causes),
        "aktien_mit_abweichung": len(stocks),
        "aktien_mit_ereignis_im_zeitraum": dict(events),
        "aktien": sorted(stocks, key=lambda s: s["aktie"]),
        "ranglisten": effect,
    }


def ranking_effect(stand: nachrechnen.Stand, substituted: dict[int, tuple[np.ndarray, np.ndarray, set[int]]], liquid, min_trend: int, top_stocks: set[int]) -> tuple[dict, dict]:
    """Alle Ranglisten mit den Kursen des Stands und mit den Nasdaq-Kursen an den abweichenden Tagen (unabhängige Rechnung)."""
    totals: Counter = Counter()
    moves: dict[int, Counter] = {i: Counter() for i in top_stocks}
    for h in range(1, 91):
        win = stand.get(f"windows/{h}.full.bin")
        stand.drop(f"windows/{h}.full.bin")
        mm = win["m"]
        status = np.frombuffer(__import__("base64").b64decode(win["status_b64"]), dtype=np.uint8).copy()
        idx = [int(x) for x in mm["idx"]]
        r_of = {i: float(mm["r"][k]) for k, i in enumerate(idx)}
        r2_of = {i: mm["r2"][k] for k, i in enumerate(idx)}
        start_of = {i: int(mm["start"][k]) for k, i in enumerate(idx)}
        r_new, r2_new, status_new = dict(r_of), dict(r2_of), status.copy()
        changed = 0
        for i in idx:
            if i not in substituted:
                continue
            days, closes, deviating = substituted[i]
            if not any(start_of[i] <= day <= int(days[-1]) for day in deviating):
                continue  # kein abweichender Tag im Zeitraum: Werte des Stands bleiben (auch R² nach der Formel des Rechenkerns)
            r, r2, st = window_values(days, closes, start_of[i], min_trend)
            if r != r_of[i] or (r2 is None) != (r2_of[i] is None) or (r2 is not None and r2_of[i] is not None and abs(r2 - r2_of[i]) > 1e-12) or st != int(status[i]):
                changed += 1
            r_new[i], r2_new[i], status_new[i] = r, r2, st
        if not changed:
            continue
        totals["zeitraeume_mit_geaenderten_werten"] += 1
        groups = (("A", idx), ("B", [i for i in idx if liquid[i]]))
        for name, members in groups:
            members_arr = np.array(members, dtype=np.int64)
            before = lists_of(nachrechnen.rank_group(members_arr, status, r_of, r2_of))
            after = lists_of(nachrechnen.rank_group(members_arr, status_new, r_new, r2_new))
            for w, order in before.items():
                if not order and not after[w]:
                    continue
                totals["ranglisten_verglichen"] += 1
                for flag, value in compare_orders(order, after[w]).items():
                    if value:
                        totals[f"{flag}_geaendert"] += 1
                position_before = {i: k for k, i in enumerate(order[:10])}
                position_after = {i: k for k, i in enumerate(after[w][:10])}
                for i in moves:
                    was, now = position_before.get(i), position_after.get(i)
                    if was is None and now is None:
                        continue
                    moves[i]["unter_ersten_10_vorher"] += was is not None
                    moves[i]["unter_ersten_10_nachher"] += now is not None
                    moves[i]["platz1_vorher"] += was == 0
                    moves[i]["platz1_nachher"] += now == 0
                    if was is not None and now is not None and was != now:
                        moves[i]["platz_geaendert"] += 1
    totals["ranglisten_insgesamt"] = 90 * 2 * len(nachrechnen.WEIGHTS)
    return dict(totals), {i: dict(v) for i, v in moves.items()}


def annotations(report: dict) -> list[str]:
    t, c, e = report["tage"], report["ursachen"], report["ranglisten"]
    explained = sum(v for k, v in c.items() if k != "ungeklaert")
    head = [
        f"Nachträglich abgerufen am {report['abgerufen_utc']} (Nasdaq, Nasdaq-NOCP, Yahoo-Tages- und Minutenkurse, Dividenden) – keine Originaldaten. "
        f"Stand {report['stand']} (Kursstand {report['stichtag']}); {report['ausgewaehlt']} US-Aktien (davon {report['davon_aus_den_ersten_20']} aus den ersten 20 einer Rangliste)",
        f"Abruf: {', '.join(f'{k} {v}' for k, v in sorted(report['abruf'].items()))}; NOCP: {', '.join(f'{k} {v}' for k, v in sorted(report['nocp_abruf'].items())) or 'keine Nasdaq-notierte Aktie mit Abweichung'}"
        + (f" (Felder {', '.join(report['nocp_felder'])})" if report.get("nocp_felder") else ""),
        f"Börsentage verglichen {t.get('verglichen', 0)}, abweichend {t.get('abweichend', 0)} (mit NOCP {t.get('abweichend_mit_nocp', 0)}, mit Minutenkursen {t.get('abweichend_mit_minutenkursen', 0)}); "
        f"Ursache belegt für {explained}, ungeklärt {c.get('ungeklaert', 0)}: " + "; ".join(f"{CAUSE_TEXT[k]} {c[k]}" for k in CAUSES if c.get(k)),
        f"Tage nur im Stand {report['nur_eine_quelle'].get('nur_im_stand', 0)} (davon ohne Umsatz bei Yahoo {report['nur_eine_quelle'].get('nur_im_stand_ohne_umsatz_bei_yahoo', 0)}); "
        f"Aktien mit Ereignis im Zeitraum: {', '.join(f'{k} {v}' for k, v in sorted(report['aktien_mit_ereignis_im_zeitraum'].items())) or 'keine'}",
        f"Ranglisten mit Nasdaq-Kursen an den abweichenden Tagen (unabhängige Rechnung, gleiche Zulassung zu Gruppe B): {e.get('ranglisten_verglichen', 0)} betroffene von "
        f"{e.get('ranglisten_insgesamt', 0)} Ranglisten neu gerechnet – Platz 1 anders {e.get('spitze_geaendert', 0)}, andere Aktien unter den ersten 10 "
        f"{e.get('top10_aktien_geaendert', 0)}, andere Reihenfolge der ersten 10 {e.get('top10_reihenfolge_geaendert', 0)}, irgendeine Änderung {e.get('reihenfolge_geaendert', 0)}",
    ]
    rows = []
    focus = [s for s in report["aktien"] if s["top10"] or s["ursachen"].get("ungeklaert") or s["groesste_abweichung_pct"] > 0.5]
    rest = len(report["aktien"]) - len(focus[:MAX_ROWS])
    for s in focus[:MAX_ROWS]:
        moves = s.get("rangwirkung") or {}
        rows.append(
            f"Aktie {s['aktie']} ({s['boerse']}, {s['kursbereich']}; unter den ersten 10 in {s['top10']} Ranglisten, Platz 1 in {s['platz1']}): {s['abweichend']} Tage abweichend, "
            f"größte {s['groesste_abweichung_pct']} %; Ursachen: " + (", ".join(f"{CAUSE_TEXT[k]} {s['ursachen'][k]}" for k in CAUSES if s["ursachen"].get(k)) or "–")
            + f"; NOCP {'ja' if s['nocp_abrufbar'] else 'nein'}, Minutenkurse {s['minutenkurse_tage']} Tage; Ereignisse {', '.join(f'{k} {v}' for k, v in s['ereignisse'].items() if v) or 'keine'}"
            + (
                f"; mit Nasdaq-Kursen unter den ersten 10 {moves.get('unter_ersten_10_vorher', 0)} → {moves.get('unter_ersten_10_nachher', 0)}, Platz 1 {moves.get('platz1_vorher', 0)} → "
                f"{moves.get('platz1_nachher', 0)}, anderer Platz {moves.get('platz_geaendert', 0)}"
                if moves
                else ""
            )
        )
    if rest:
        rows.append(f"Weitere {rest} Aktien mit kleinen Abweichungen (höchstens 0,5 %), nicht unter den ersten 10 und mit belegter Ursache – nur in den Zählwerten oben")
    level = "notice" if c.get("ungeklaert", 0) == 0 else "warning"

    def encode(lines: list[str]) -> str:
        return "%0A".join(line.replace("%", "%25") for line in lines)

    out = [f"::{level} title={gegen._title('Ursachen der Kursunterschiede und Wirkung auf die Ranglisten')}::{encode(part)}" for part in gegen.chunked(head)]
    parts = gegen.chunked(rows)
    for n, part in enumerate(parts, start=1):
        out.append(f"::notice title={gegen._title(f'Ursachen je Aktie ({n}/{len(parts)}; Buchstaben statt Namen)')}::{encode(part)}")
    return out[:10]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", "szymeklh87-commits/tr-aktienvergleich"))
    parser.add_argument("--bericht", type=Path)
    args = parser.parse_args(argv)
    from traktien.providers.http import HttpClient

    http = HttpClient(impersonate="chrome", max_retries=2, timeout=25, min_interval={"api.nasdaq.com": 0.4, "query2.finance.yahoo.com": 0.3})
    with tempfile.TemporaryDirectory() as temp:
        meta, stands = nachrechnen.load_release_stands(args.repo, os.environ.get("GITHUB_TOKEN"), Path(temp), None)
        key = nachrechnen.key_for(meta["descriptor"])
        official = meta["status"].get("latest_official_snapshot_id")
        folder = dict(stands).get(official)
        if folder is None:
            print("::error title=Kursursachen::Stand mit Schlusskursen nicht im Release gefunden")
            return 1
        report = run(nachrechnen.Stand(folder, official, key), official, http)
    for line in annotations(report):
        print(line)
    if args.bericht:
        args.bericht.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    started = time.monotonic()
    try:
        code = main()
    except Exception as exc:  # noqa: BLE001 - Abbruchgrund ohne Inhalte
        print(f"::error title=Kursursachen abgebrochen::{type(exc).__name__}: {str(exc).splitlines()[0][:200] if str(exc) else ''}")
        code = 1
    print(f"::notice title=Kursursachen::Dauer {round(time.monotonic() - started)} s")
    sys.exit(code)
