"""Ursachen der Kursunterschiede zwischen Yahoo und Nasdaq und ihre Wirkung auf die Ranglisten (ab 1.18.1).

Simons Auftrag vom 24.10.2026, 21:23 Uhr: „‚Entspricht Yahoo‘ reicht nicht als unabhängiger Nachweis korrekter
Börsenkurse. Untersuche besonders die betroffenen Aktien in den Top 10. Prüfe anhand verfügbarer Quellen unter anderem
Kursdefinition, Handelsdatum, Bereinigung und Kapitalmaßnahmen. Weise Ursachen nur dann als geklärt aus, wenn sie belegt
sind. Ermittle, ob und wie die Unterschiede die Ranglisten verändern. Keine kostenpflichtigen Dienste buchen.“

Die Gegenprüfung (``kurse_gegenpruefen.py``) zeigt, *dass* Stand und Nasdaq an manchen Tagen verschiedene Schlusskurse
haben und dass der Stand dort den Yahoo-Kurs trägt – das allein ist kein Nachweis. Dieses Skript sucht für jeden
abweichenden Tag einen **Beleg** aus frei zugänglichen Quellen (nachträglich abgerufen, keine kostenpflichtigen Dienste)
und prüft bei Aktien mit Heimatbörse Nasdaq **jeden** Tag gegen den offiziellen Schlusskurs:

1. **Kursdefinition – offizieller Schlusskurs:** „Nasdaq Official Closing Price“ (NOCP, Historie auf nasdaq.com; nach
   Nasdaq Rule 4754 der Preis der Schlussauktion, ersatzweise der letzte Abschluss). Für alle Nasdaq-notierten Aktien der
   Auswahl wird an allen Tagen der Stand mit dem NOCP verglichen. An einem abweichenden Tag gilt: Nasdaq-Historie = NOCP
   und Stand nicht → Yahoo führt an diesem Tag nicht den offiziellen Schlusskurs; Stand = NOCP und Nasdaq-Historie nicht →
   der Stand hat den offiziellen Schlusskurs, die Nasdaq-Historie nicht.
2. **Kursdefinition – letzter Abschluss vor 16:00 Uhr New York** (Minutenkurse von Yahoo: Kerzen zu 1 Minute für die
   letzten 5 Sitzungen, zu 2 Minuten für die letzten 58 Kalendertage): Stand = letzter Abschluss und Nasdaq nicht – oder
   umgekehrt. Belegt ist damit die Definition einer Quelle, nicht, dass die andere den offiziellen Kurs führt.
3. **Anzeigegenauigkeit:** Der Kurs des Stands liegt zwischen zwei Kursstufen, die Nasdaq anzeigt (Cent ab 1 $, 1/100
   Cent darunter), und Nasdaq zeigt eine der beiden Nachbarstufen – weniger als eine Stufe Abstand.
4. **Handelsdatum und Handel:** Umsatz beider Quellen; ein Tag ohne Umsatz mit dem Kurs des Vortags ist belegt als „kein
   Handel, Kurs fortgeschrieben“ (so auch die Regel für den offiziellen Schlusskurs, z. B. NYSE Arca Rule 1.1(gg)); Tage,
   die nur eine Quelle führt.
5. **Bereinigung:** Nasdaq-Kurs gleich dem dividendenbereinigten Yahoo-Kurs (``adjclose``) statt dem splitbereinigten.
6. **Kapitalmaßnahmen:** Splits und Dividenden laut Yahoo und Dividenden laut Nasdaq im Zeitraum; ein konstanter Faktor.

Was keiner dieser Belege trifft, bleibt **ungeklärt** – auch wenn es dem Yahoo-Kurs entspricht. Gezählt wird, warum
(Heimatbörse der NYSE-Gruppe ohne frei abrufbaren offiziellen Schlusskurs, NOCP fehlt am Tag, NOCP ein dritter Wert) und
in welchem Muster (Abstand in Kursstufen, Richtung, Umsatz beider Quellen, Minutenkurs vorhanden).

**Wirkung auf die Ranglisten:** Alle Ranglisten (Gruppe A und B, 11 Gewichtungen, 1–90 Tage) werden mit der unabhängigen
Rechnung aus ``nachrechnen.py`` mit den Kursen des Stands und in zwei Varianten gerechnet: (a) an allen abweichenden
Tagen der Nasdaq-Kurs, (b) an allen Tagen mit offiziellem Schlusskurs (NOCP) ungleich dem Stand der NOCP – sonst dieselben
Kurse und dieselbe Zulassung zu Gruppe B. Gezählt werden geänderter Platz 1, andere Aktien unter den ersten 10 und andere
Reihenfolge. Geprüft sind die US-Aktien unter den ersten 20 irgendeiner Rangliste und 150 zufällig gewählte; Aktien
anderer Börsen führt Nasdaq nicht (ihr Anteil an den ersten 10 steht im Ergebnis).

**Abruf:** zuerst die Aktien unter den ersten 10 (die häufigsten zuerst), dann die übrigen unter den ersten 20, zuletzt die
zufällig gewählten. Antwortet eine Quelle mit einem Netz- oder Serverfehler, wird die Aktie nach einer Pause erneut
abgefragt (bis zu zwei weitere Runden). Bleiben bei Nasdaq mehrere Aktien hintereinander ohne Antwort, gilt das als Sperre:
Pause, danach doppelter Abstand zwischen den Anfragen. Bleibt am Ende eine Aktie ohne Antwort, ist das Ergebnis
**unvollständig** – gezählt je Gruppe (erste 10, erste 20, zufällig). Urteil und Job: grün nur, wenn der Abruf vollständig
ist und jede Abweichung belegt ist; sonst rot mit dem Grund im Titel – ein fehlerfrei gelaufenes Skript ist kein Beleg.

**Welche Ranglisten sich ändern:** je Variante einzeln die Ranglisten mit anderem Platz 1 bzw. anderen Aktien unter den
ersten 10 (Zeitraum, Gruppe, Gewichtung, Buchstaben der Aktien) und je Aktie unter den ersten 10 die Wirkung in beiden
Varianten – auch für Aktien, bei denen nur der offizielle Schlusskurs vom Stand abweicht.

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
RETRY_PAUSES = (60.0, 180.0)  # Pause vor der zweiten und der dritten Abrufrunde (24.10.2026, 23:09 Uhr: nach 30 und 90 s keine Antwort)
NASDAQ_HOST = "api.nasdaq.com"
NASDAQ_INTERVAL_S = 1.0  # Abstand der Anfragen an Nasdaq (bis dahin 0,6 s: 121 Aktien blieben ohne Antwort)
BLOCK_AFTER = 4  # so viele Aktien hintereinander ohne Antwort von Nasdaq gelten als Sperre …
BLOCK_PAUSE_S = 180.0  # … dann Pause und doppelter Abstand zwischen den Anfragen (höchstens MAX_INTERVAL_S)
MAX_BLOCK_PAUSES = 2
MAX_INTERVAL_S = 3.0
MAX_EVENTS = 12  # Ranglisten mit anderem Platz 1 bzw. anderen Aktien unter den ersten 10 in der Kurzfassung je Variante
MAX_TRIGGER_SEARCH = 40  # so viele weitere ersetzte Aktien prüft die Suche nach den Auslösern eines neuen Platzes 1 höchstens
MAX_TRIGGER_DAYS = 10  # ersetzte Tage je Aktie in der Zeile eines neuen Platzes 1 (die übrigen gezählt)
MAX_ATTRIBUTIONS = 60  # neue Plätze 1 je Variante mit Suche nach den Auslösern (danach „nicht untersucht“, gezählt)
MAX_PER_STEP = 9  # GitHub zeigt je Schritt höchstens 10 Hinweise je Art (notice/warning/error) – einer bleibt frei
MAX_STEPS = 5  # Prüfschritt und vier Schritte „Einzelheiten“ im Workflow (gleich der Zahl dort, Test)
MAX_JOB_ANNOTATIONS = 45  # GitHub: höchstens 50 je Job – Platz für Dauer, Fehlermeldung des Runners und Abschluss
GROUPS = ("erste_10", "erste_20", "zufall")
GROUP_TEXT = {"erste_10": "erste 10", "erste_20": "Plätze 11–20", "zufall": "Zufallsstichprobe"}
# Nasdaq beantwortet je Rechner nur etwa 430 Anfragen (24.10.2026: zweimal nach 430 Anfragen keine Antwort mehr, auch nach
# Pausen von 3 Minuten und mit 3 s Abstand) – deshalb zwei Jobs auf zwei Rechnern: die ersten 20 und die Zufallsstichprobe
SHARDS = {"alle": GROUPS, "erste20": ("erste_10", "erste_20"), "zufall": ("zufall",)}
SHARD_TEXT = {"alle": "", "erste20": " (erste 20)", "zufall": " (Zufallsstichprobe)"}
FETCH_BUDGET_S = 35 * 60  # Zeitbudget der Grundabfrage; der Job darf 60 min laufen (Ranglisten danach etwa 5 min)
DETAIL_EXTRA_S = 8 * 60  # danach noch Minutenkurse und Dividenden der Aktien mit Abweichung
MINUTES_2M_DAYS = 58  # Yahoo liefert Kerzen zu 2 Minuten nur für die letzten 60 Tage
NASDAQ_LISTED = {"NMS", "NGM", "NCM", "NAS", "NASDAQ", "NasdaqGS", "NasdaqGM", "NasdaqCM"}
NYSE_GROUP = {"NYQ": "NYSE", "NYS": "NYSE", "ASE": "NYSE American", "PCX": "NYSE Arca", "BTS": "Cboe BZX"}
NOCP_URLS = (
    "https://api.nasdaq.com/api/company/{symbol}/historical-nocp?timeframe=y1",
    "https://api.nasdaq.com/api/company/{symbol}/historical-nocp?timeframe=m3",
)
NASDAQ_DIVIDENDS = "https://api.nasdaq.com/api/quote/{symbol}/dividends?assetclass=stocks"
YAHOO_DAILY = "https://query2.finance.yahoo.com/v8/finance/chart/{symbol}?period1={start}&period2={end}&interval=1d&events=div%7Csplit&includeAdjustedClose=true"
YAHOO_MINUTES = "https://query2.finance.yahoo.com/v8/finance/chart/{symbol}?range=5d&interval=1m&includePrePost=false"
YAHOO_MINUTES_2M = "https://query2.finance.yahoo.com/v8/finance/chart/{symbol}?period1={start}&period2={end}&interval=2m&includePrePost=false"
CAUSES = (
    "offizieller_schlusskurs",
    "stand_ist_nocp",
    "letzter_abschluss",
    "nasdaq_letzter_abschluss",
    "rundung",
    "kein_handel",
    "dividendenbereinigung",
    "split",
    "ungeklaert",
)
CAUSE_TEXT = {
    "offizieller_schlusskurs": "Yahoo nicht der offizielle Schlusskurs der Heimatbörse (Nasdaq-Kurs = NOCP)",
    "stand_ist_nocp": "Stand = offizieller Schlusskurs (NOCP), Nasdaq-Historie nicht",
    "letzter_abschluss": "Stand = letzter Abschluss vor 16:00 Uhr, Nasdaq ein anderer Schlusskurs",
    "nasdaq_letzter_abschluss": "Nasdaq = letzter Abschluss vor 16:00 Uhr, Stand ein anderer Schlusskurs",
    "rundung": "unter einer Kursstufe (Stand zwischen zwei Stufen, Nasdaq zeigt die Nachbarstufe)",
    "kein_handel": "kein Umsatz, Kurs des Vortags fortgeschrieben",
    "dividendenbereinigung": "Nasdaq-Kurs = dividendenbereinigter Yahoo-Kurs",
    "split": "Faktor eines Splits",
    "ungeklaert": "ungeklärt",
}
SHORT_CAUSE = {  # Kurzform in den Zeilen je Aktie (Langform in der Legende des Ergebnisses)
    "offizieller_schlusskurs": "Nasdaq = NOCP",
    "stand_ist_nocp": "Stand = NOCP",
    "letzter_abschluss": "Stand = letzter Abschluss",
    "nasdaq_letzter_abschluss": "Nasdaq = letzter Abschluss",
    "rundung": "Kursstufe",
    "kein_handel": "ohne Umsatz",
    "dividendenbereinigung": "Dividendenbereinigung",
    "split": "Split",
    "ungeklaert": "ungeklärt",
}
# Warum für einen abweichenden Tag kein Beleg möglich war – das ist die Grenze der Prüfung, keine Ursache der Abweichung
UNEXPLAINED_TEXT = {
    "nyse_gruppe_ohne_offiziellen_kurs": "Prüfgrenze: Heimatbörse der NYSE-Gruppe oder Cboe – offizieller Schlusskurs nicht frei abrufbar",
    "nocp_fehlt_am_tag": "Prüfgrenze: Nasdaq-notiert – NOCP für den Tag fehlt",
    "nocp_dritter_wert": "Befund ohne Ursache: Nasdaq-notiert – Stand, Nasdaq-Historie und NOCP drei verschiedene Kurse",
    "boerse_unbekannt": "Prüfgrenze: Heimatbörse unbekannt (Yahoo ohne Angabe)",
}
NOCP_NOTE = {"nasdaq_gleich_nocp": "Nasdaq = NOCP", "nasdaq_anders": "Nasdaq ein dritter Kurs", "nasdaq_ohne_tag": "Nasdaq ohne den Tag"}


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
    """Letzter Abschluss der regulären Sitzung je Tag aus den Minutenkursen von Yahoo (letzte Kerze vor 16:00 Uhr New York;
    bei Kerzen zu 1 oder 2 Minuten ist das der letzte Abschluss vor 16:00 Uhr)."""
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


def step(value: float) -> float:
    """Kursstufe, mit der Nasdaq den Kurs angibt: Cent ab 1 $, 1/100 Cent darunter."""
    return 0.01 if value >= 1 else 0.0001


def on_grid(value: float, unit: float) -> bool:
    """Liegt der Kurs auf einer Kursstufe? Toleranz 2 % einer Stufe für die Gleitkomma-Darstellung der Quellen."""
    q = value / unit
    return abs(q - round(q)) <= 0.02


def within_display(own: float, nasdaq_close: float) -> bool:
    """Abstand unter einer Kursstufe: Der Stand liegt zwischen zwei Stufen, Nasdaq zeigt eine der beiden Nachbarstufen."""
    unit = step(nasdaq_close)
    return on_grid(nasdaq_close, unit) and not on_grid(own, unit) and abs(own - nasdaq_close) < unit * 0.98


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
    if nocp is not None and day in nocp:
        if same(n_close, nocp[day]) and not same(own, nocp[day]):
            return "offizieller_schlusskurs", "Nasdaq = NOCP, Stand ≠ NOCP"
        if same(own, nocp[day]) and not same(n_close, nocp[day]):
            return "stand_ist_nocp", "Stand = NOCP, Nasdaq-Historie ≠ NOCP"
    if n_close is not None and within_display(own, n_close):
        return "rundung", "Stand zwischen zwei Kursstufen, Nasdaq zeigt die Nachbarstufe"
    if day in minutes:
        if same(own, minutes[day]) and not same(n_close, minutes[day]):
            return "letzter_abschluss", "Stand = letzter Minutenkurs vor 16:00, Nasdaq anders"
        if same(n_close, minutes[day]) and not same(own, minutes[day]):
            return "nasdaq_letzter_abschluss", "Nasdaq = letzter Minutenkurs vor 16:00, Stand anders"
    volume_y, volume_n = y.get("volume"), n.get("volume")
    if previous_own is not None and own == previous_own and volume_y == 0:
        return "kein_handel", "Yahoo: Umsatz 0, Kurs des Vortags"
    if previous_nasdaq is not None and n_close == previous_nasdaq and volume_n == 0:
        return "kein_handel", "Nasdaq: Umsatz 0, Kurs des Vortags"
    if y.get("adjclose") is not None and same(n_close, y["adjclose"]) and not same(n_close, y.get("close")):
        return "dividendenbereinigung", "Nasdaq = adjclose"
    return "ungeklaert", ""


def unexplained_reason(exchange: str | None, nocp: dict[int, float] | None, day: int) -> str:
    """Warum ein Tag ungeklärt bleibt – welche Quelle fehlt."""
    if exchange in NASDAQ_LISTED:
        return "nocp_dritter_wert" if nocp is not None and day in nocp else "nocp_fehlt_am_tag"
    if exchange in NYSE_GROUP:
        return "nyse_gruppe_ohne_offiziellen_kurs"
    return "boerse_unbekannt"


def volume_bucket(nasdaq_volume: float | None, yahoo_volume: float | None) -> str:
    """Umsatz der Nasdaq-Historie gegen Yahoo am selben Tag (±2 % gilt als gleich)."""
    if nasdaq_volume is None or yahoo_volume is None:
        return "fehlt"
    if yahoo_volume <= 0:
        return "gleich" if nasdaq_volume <= 0 else "nasdaq_groesser"
    ratio = nasdaq_volume / yahoo_volume
    if abs(ratio - 1) <= 0.02:
        return "gleich"
    return "nasdaq_kleiner" if ratio < 1 else "nasdaq_groesser"


def tick_bucket(own: float, nasdaq_close: float) -> str:
    """Abstand in Kursstufen von Nasdaq (anonymes Muster ohne Kurse)."""
    ticks = abs(own - nasdaq_close) / step(nasdaq_close)
    if ticks < 1.5:
        return "1"
    if ticks < 2.5:
        return "2"
    return "3–10" if ticks < 10.5 else "über 10"


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


def select(stand: nachrechnen.Stand, instruments: dict, sid: str) -> tuple[list[int], dict[int, int], dict[int, int], int, dict]:
    """US-Aktien unter den ersten 20 einer Rangliste und zufällig gewählte; je Aktie die Zahl der Ranglisten mit ihr unter
    den ersten 10 bzw. auf Platz 1; dazu, wie viele der Plätze unter den ersten 10 (und auf Platz 1) aller Ranglisten
    US-Aktien belegen – nur diese kann Nasdaq gegenprüfen."""
    n = len(instruments["isin"])
    calendar = instruments.get("calendar") or [None] * n
    key = instruments.get("exchange_key") or [None] * n
    symbol = instruments.get("symbol") or [None] * n
    has_series = instruments.get("has_series") or [True] * n
    us = {i for i in range(n) if calendar[i] == "XNYS" and key[i] != "OTC" and symbol[i] and "." not in str(symbol[i]) and has_series[i]}
    top: set[int] = set()
    top10: Counter = Counter()
    first: Counter = Counter()
    places: Counter = Counter()
    for h in range(1, 91):
        win = stand.get(f"windows/{h}.full.bin")
        orders = win["orders"]
        lists = [orders.get("v0") or [], orders.get("v0l") or []]
        for group in ("u", "ul"):
            lists += [values for w, values in (orders.get(group) or {}).items() if str(w) != "0"]
        for values in lists:
            head = [int(i) for i in values[:TOP_SELECT]]
            if head:
                places["ranglisten"] += 1
                places["platz_1"] += 1
                places["platz_1_us"] += head[0] in us
            top.update(i for i in head if i in us)
            for k, i in enumerate(head[:10]):
                places["erste_10"] += 1
                if i in us:
                    places["erste_10_us"] += 1
                    top10[i] += 1
                    if k == 0:
                        first[i] += 1
        stand.drop(f"windows/{h}.full.bin")
    rest = sorted(us - top)
    extra = random.Random(sid).sample(rest, min(RANDOM_EXTRA, len(rest)))
    # Reihenfolge des Abrufs: die Aktien unter den ersten 10 (die häufigsten zuerst), dann die übrigen unter den ersten 20,
    # zuletzt die zufällig gewählten – fällt eine Quelle unterwegs aus, fehlen zuerst die am wenigsten wichtigen
    head = sorted(top, key=lambda i: (-top10.get(i, 0), i))[: MAX_STOCKS - len(extra)]
    return head + sorted(extra), dict(top10), dict(first), len(head), dict(places)


def get_json(http, url: str, headers: dict | None = None) -> tuple[str, dict | None]:
    try:
        response = http.get(url, headers=headers or {})
    except Exception as exc:  # noqa: BLE001 - Netz: nur zählen
        return f"fehler_{error_name(exc)}", None
    if response.status_code != 200:
        return f"http_{response.status_code}", None
    try:
        return "ok", response.json()
    except ValueError:
        return "kein_json", None


def error_name(exc: Exception) -> str:
    """Art des Fehlers ohne Adresse: ``HttpClient`` meldet „Anfrage an <Host> endgültig fehlgeschlagen: <Art>“ – die Art
    dahinter (z. B. ``Timeout``) unterscheidet eine Zeitüberschreitung von einer abgewiesenen Verbindung."""
    outer = type(exc).__name__
    inner = str(exc).rsplit(": ", 1)[-1].strip() if ": " in str(exc) else ""
    return f"{outer}_{inner}" if inner.isidentifier() and inner != outer else outer


def letter_label(k: int) -> str:
    return chr(ord("A") + k) if k < 26 else f"Z{k}"


def price_range(nasdaq: dict[int, dict]) -> str:
    """Kursbereich nach dem mittleren Nasdaq-Schlusskurs (ohne Kurse und Namen im Protokoll)."""
    values = sorted(row["close"] for row in nasdaq.values())
    median = values[len(values) // 2]
    return next(label for limit, label in ((1, "unter 1 $"), (10, "1–10 $"), (100, "10–100 $"), (float("inf"), "über 100 $")) if median < limit)


def nasdaq_requests(http) -> int | None:
    """Zahl der bisherigen Anfragen an Nasdaq (``HttpClient.stats``; ohne Zählung ``None``)."""
    by_host = getattr(getattr(http, "stats", None), "by_host", None)
    return int(by_host.get(NASDAQ_HOST, 0)) if isinstance(by_host, dict) else None


def slow_down(http) -> float | None:
    """Doppelter Abstand zwischen den Anfragen an Nasdaq (höchstens MAX_INTERVAL_S); ohne Drossel ``None``."""
    intervals = getattr(http, "min_interval", None)
    if not isinstance(intervals, dict):
        return None
    intervals[NASDAQ_HOST] = min(MAX_INTERVAL_S, max(float(intervals.get(NASDAQ_HOST, 0.0)), NASDAQ_INTERVAL_S) * 2)
    return intervals[NASDAQ_HOST]


def transient(status: str) -> bool:
    """Netz- oder Serverfehler, der eine neue Abrufrunde rechtfertigt (keine fehlenden Daten)."""
    return status.startswith("fehler_") or status == "http_429" or status.startswith("http_5") or status == "kein_json"


def fetch_base(http, symbol: str, start_day: int, cutoff: int) -> dict:
    """Nasdaq-Historie, Yahoo-Tageskurse und – bei Heimatbörse Nasdaq – die NOCP-Historie einer Aktie."""
    nasdaq_symbol = symbol.replace("-", ".")
    out: dict = {"nasdaq_symbol": nasdaq_symbol}
    url = gegen.NASDAQ.format(symbol=nasdaq_symbol, start=(EPOCH + dt.timedelta(days=start_day)).isoformat(), end=(EPOCH + dt.timedelta(days=cutoff + 1)).isoformat())
    status, payload = get_json(http, url, gegen.HEADERS)
    out["nasdaq_status"] = status
    out["nasdaq"] = parse_nasdaq_rows(payload) if status == "ok" else {}
    if not out["nasdaq"]:
        return out
    status, payload = get_json(http, YAHOO_DAILY.format(symbol=symbol, start=start_day * 86400, end=(cutoff + 2) * 86400), gegen.YAHOO_HEADERS)
    out["yahoo_status"] = status
    out["yahoo"] = parse_yahoo_daily(payload) if status == "ok" else {"days": {}, "splits": [], "dividends": []}
    out["nocp"], out["nocp_status"], out["nocp_fields"] = None, [], []
    if out["yahoo"].get("exchange") in NASDAQ_LISTED:
        for nocp_url in NOCP_URLS:
            status, payload = get_json(http, nocp_url.format(symbol=nasdaq_symbol), gegen.HEADERS)
            out["nocp_status"].append(status)
            rows, fields = parse_nocp(payload) if status == "ok" else ({}, [])
            if rows:
                out["nocp"], out["nocp_fields"] = rows, fields
                break
    return out


def base_failed(base: dict) -> str | None:
    """Fehlerstatus, wenn eine Quelle der Grundabfrage mit einem Netz- oder Serverfehler antwortete."""
    for name in ("nasdaq_status", "yahoo_status"):
        status = base.get(name)
        if status and transient(status):
            return f"{name.split('_')[0]}_{status}"
    statuses = base.get("nocp_status") or []
    if base.get("nocp") is None and statuses and any(transient(s) for s in statuses):
        return f"nocp_{next(s for s in statuses if transient(s))}"
    return None


def fetch_details(http, symbol: str, nasdaq_symbol: str, now: float) -> dict:
    """Minutenkurse (1 Minute: 5 Sitzungen; 2 Minuten: 58 Tage) und Dividenden bei Nasdaq – nur für Aktien mit Abweichung."""
    out: dict = {"status": {}}
    status, payload = get_json(http, YAHOO_MINUTES_2M.format(symbol=symbol, start=int(now) - MINUTES_2M_DAYS * 86400, end=int(now)), gegen.YAHOO_HEADERS)
    out["status"]["minuten_2m"] = status
    minutes = parse_yahoo_minutes(payload) if status == "ok" else {}
    status, payload = get_json(http, YAHOO_MINUTES.format(symbol=symbol), gegen.YAHOO_HEADERS)
    out["status"]["minuten"] = status
    minutes.update(parse_yahoo_minutes(payload) if status == "ok" else {})  # 1 Minute hat Vorrang
    out["minutes"] = minutes
    status, payload = get_json(http, NASDAQ_DIVIDENDS.format(symbol=nasdaq_symbol), gegen.HEADERS)
    out["status"]["dividenden"] = status
    out["dividends"] = parse_nasdaq_dividends(payload) if status == "ok" else []
    return out


def run(stand: nachrechnen.Stand, sid: str, http, pause=time.sleep, now: float | None = None, budget_s: float = FETCH_BUDGET_S, clock=time.monotonic, auswahl: str = "alle") -> dict:
    manifest = stand.get("manifest.bin")
    instruments = stand.get("instruments.bin")
    cutoff = int(manifest["cutoff_day"])
    min_trend = int((manifest.get("method") or {}).get("min_obs_trend", 15))
    liquid = (instruments.get("turnover") or {}).get("liquid") or [False] * len(instruments["isin"])
    chosen, top10, first, from_top, places = select(stand, instruments, sid)
    start_day = cutoff - gegen.LOOKBACK_DAYS - 5
    now = time.time() if now is None else now
    started = clock()

    # Gruppe je Aktie (Reihenfolge des Abrufs aus ``select``): unter den ersten 10, übrige unter den ersten 20, zufällig
    group_of = {i: ("erste_10" if top10.get(i) else "erste_20") for i in chosen[:from_top]}
    group_of.update({i: "zufall" for i in chosen[from_top:]})
    selected = len(chosen)
    other_job = [i for i in chosen if group_of[i] not in SHARDS[auswahl]]  # im anderen Job geprüft
    chosen = [i for i in chosen if group_of[i] in SHARDS[auswahl]]

    # 1. Grundabfrage mit bis zu zwei Nachholrunden – innerhalb eines Zeitbudgets, damit der Job nie ohne Ergebnis abbricht.
    # Bleiben bei Nasdaq BLOCK_AFTER Aktien hintereinander ohne Antwort, gilt das als Sperre: Pause und doppelter Abstand.
    bases: dict[int, dict] = {}
    failures: dict[int, str] = {}
    pending, rounds, recovered = list(chosen), 0, 0
    streak, block_pauses, first_block = 0, 0, None
    while pending:
        rounds += 1
        retry = []
        for k, i in enumerate(pending, start=1):
            if clock() - started > budget_s:
                failures[i] = "zeitbudget_erschoepft"
                continue
            if k % 50 == 0:
                print(f"Kursursachen: Runde {rounds}, {k} von {len(pending)} Aktien abgefragt, ohne Antwort bisher {len(failures)}", flush=True)
            base = fetch_base(http, str(instruments["symbol"][i]), start_day, cutoff)
            reason = base_failed(base)
            if reason is None:
                bases[i] = base
                if rounds > 1:
                    recovered += 1
                failures.pop(i, None)
                streak = 0
                continue
            failures[i] = reason
            retry.append(i)
            if not reason.startswith(("nasdaq_", "nocp_")):
                streak = 0  # Nasdaq hat geantwortet, nur Yahoo nicht
                continue
            streak += 1
            if streak >= BLOCK_AFTER and block_pauses < MAX_BLOCK_PAUSES and clock() - started + BLOCK_PAUSE_S < budget_s:
                block_pauses += 1
                streak = 0
                if first_block is None:
                    first_block = nasdaq_requests(http)
                interval = slow_down(http)
                after = f"danach Abstand {interval} s" if interval is not None else "Abstand unverändert"
                print(f"Kursursachen: {BLOCK_AFTER} Aktien hintereinander ohne Antwort von Nasdaq – Pause {BLOCK_PAUSE_S:.0f} s, {after}", flush=True)
                pause(BLOCK_PAUSE_S)
        if not retry or rounds > len(RETRY_PAUSES) or clock() - started > budget_s:
            break
        pause(RETRY_PAUSES[rounds - 1])
        pending = retry
    by_group: Counter = Counter()
    for i in chosen:
        if i in failures:
            by_group[f"{group_of[i]}_ohne_antwort"] += 1
        else:
            by_group[f"{group_of[i]}_{'mit_kursen' if bases[i]['nasdaq'] else 'keine_kurse'}"] += 1

    sources: Counter = Counter()
    for i in chosen:
        if i in failures:
            sources[f"fehlgeschlagen_{failures[i]}"] += 1
            continue
        base = bases[i]
        sources["nasdaq_ok" if base["nasdaq"] else ("nasdaq_keine_kurse" if base["nasdaq_status"] == "ok" else f"nasdaq_{base['nasdaq_status']}")] += 1
        if base["nasdaq"]:
            sources[f"yahoo_{base['yahoo_status']}"] += 1

    days_total: Counter = Counter()
    kinds: Counter = Counter()
    causes: Counter = Counter()
    unexplained: Counter = Counter()
    patterns: Counter = Counter()
    volumes: Counter = Counter()
    nocp_probe: Counter = Counter()
    nocp_compare: Counter = Counter()
    events: Counter = Counter()
    only: Counter = Counter()
    detail_status: Counter = Counter()
    nocp_fields: set[str] = set()
    stocks: list[dict] = []
    substituted: dict[int, tuple[np.ndarray, np.ndarray, set[int]]] = {}
    substituted_nocp: dict[int, tuple[np.ndarray, np.ndarray, set[int]]] = {}
    compared: set[int] = set()
    info: dict[int, dict] = {}  # Börse, Kursbereich, abweichende Tage – für die Legende der Buchstaben
    nocp_only: list[dict] = []  # Aktien unter den ersten 10, bei denen nur der offizielle Schlusskurs vom Stand abweicht
    no_prices: dict[int, str] = {}  # beantwortet, aber ohne Vergleichskurse – zählt nicht als geprüft
    nocp_state: dict[int, str] = {}  # verglichene Aktien: mit NOCP, Nasdaq-notiert ohne NOCP, nicht Nasdaq-notiert (Prüfgrenze)
    days_a: dict[int, dict[int, tuple[float, str]]] = {}  # (a) ersetzte Tage: Abweichung des Stands in %, Ursache
    days_b: dict[int, dict[int, tuple[float, str]]] = {}  # (b) Tage mit NOCP ≠ Stand: Abweichung in %, Lage der Nasdaq-Historie
    for i in chosen:
        base = bases.get(i)
        if base is None:
            continue
        if not base["nasdaq"]:
            no_prices[i] = "nasdaq_ohne_kurse"
            continue
        symbol = str(instruments["symbol"][i])
        nasdaq, yahoo, nocp = base["nasdaq"], base["yahoo"], base["nocp"]
        exchange = yahoo.get("exchange") or "–"
        group = "nasdaq" if exchange in NASDAQ_LISTED else ("nyse_gruppe" if exchange in NYSE_GROUP else "unbekannt")
        for status in base.get("nocp_status") or []:
            nocp_probe[status] += 1
        if nocp is not None:
            nocp_probe["mit_kursen"] += 1
            nocp_fields.update(base["nocp_fields"])
        series = stand.get(f"series/{instruments['isin'][i]}.bin")
        stand.drop(f"series/{instruments['isin'][i]}.bin")
        d = [int(x) for x in series.get("d") or []]
        c = [None if x is None else float(x) for x in series.get("c") or []]
        own = {day: close for day, close in zip(d, c) if close is not None and close > 0 and day >= start_day and day <= cutoff}
        if not own:
            no_prices[i] = "stand_ohne_kurse_im_zeitraum"
            continue
        compared.add(i)
        nocp_state[i] = "mit_nocp" if nocp is not None else ("nasdaq_ohne_nocp" if exchange in NASDAQ_LISTED else "nicht_nasdaq_notiert")
        info[i] = {"boerse": "Nasdaq" if exchange in NASDAQ_LISTED else NYSE_GROUP.get(exchange, "andere"), "kursbereich": price_range(nasdaq)}
        fresh_days = sorted(k for k in nasdaq if start_day <= k <= cutoff)
        for day in fresh_days:
            if day not in own and min(own) <= day <= max(own):
                only["nur_bei_nasdaq"] += 1
                if (yahoo["days"].get(day) or {}).get("close") is not None:
                    only["nur_bei_nasdaq_yahoo_mit_kurs"] += 1
        # offizieller Schlusskurs an allen Tagen (Nasdaq-notiert)
        nocp_wrong: dict[int, float] = {}
        if nocp is not None:
            nocp_compare["aktien"] += 1
            for day, close in own.items():
                if day not in nocp:
                    continue
                nocp_compare["tage"] += 1
                kind_nocp = gegen.classify(close, nocp[day], [])
                if kind_nocp == "gleich":
                    nocp_compare["stand_gleich"] += 1
                elif kind_nocp == "faktor":
                    # Faktor eines Splits: NOCP unbereinigt, Stand splitbereinigt – kein anderer Kurs, nicht ersetzt
                    nocp_compare["faktor_split"] += 1
                else:
                    nocp_compare["stand_ungleich"] += 1
                    nocp_wrong[day] = nocp[day]
                    note = "nasdaq_ohne_tag" if day not in nasdaq else ("nasdaq_gleich_nocp" if same(nasdaq[day]["close"], nocp[day]) else "nasdaq_anders")
                    days_b.setdefault(i, {})[day] = (round(100 * (close / nocp[day] - 1), 3), note)
                if day in nasdaq:
                    nocp_compare["nasdaq_historie_gleich" if same(nasdaq[day]["close"], nocp[day]) else "nasdaq_historie_ungleich"] += 1
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
            volumes[f"{group}_{volume_bucket(nasdaq[day].get('volume'), (yahoo['days'].get(day) or {}).get('volume'))}"] += 1
            if kind != "gleich":
                deviating.append((day, kind))
        if nocp_wrong:
            changed_nocp = dict(own)
            changed_nocp.update(nocp_wrong)
            days_arr = np.array(sorted(changed_nocp), dtype=np.int64)
            substituted_nocp[i] = (days_arr, np.array([changed_nocp[x] for x in days_arr.tolist()], dtype=np.float64), set(nocp_wrong))
        info[i].update(abweichend=len(deviating), nocp_ungleich=len(nocp_wrong))
        if not deviating:
            if nocp_wrong and top10.get(i):
                nocp_only.append(
                    {
                        "idx": i,
                        "top10": int(top10.get(i, 0)),
                        "platz1": int(first.get(i, 0)),
                        "kursbereich": info[i]["kursbereich"],
                        "boerse": info[i]["boerse"],
                        "nocp_tage_ungleich": len(nocp_wrong),
                        "groesste_abweichung_nocp_pct": round(100 * max(abs(own[day] / nocp_wrong[day] - 1) for day in nocp_wrong), 2),
                    }
                )
            continue
        if clock() - started > budget_s + DETAIL_EXTRA_S:
            # Zeitbudget auch für Minutenkurse und Dividenden erschöpft: Ursachen dieser Aktie nur mit NOCP und Tageskursen
            details = {"status": {"minuten": "zeitbudget", "minuten_2m": "zeitbudget", "dividenden": "zeitbudget"}, "minutes": {}, "dividends": []}
        else:
            details = fetch_details(http, symbol, base["nasdaq_symbol"], now)
        for name, status in details["status"].items():
            detail_status[f"{name}_{status}"] += 1
        minutes, nasdaq_dividends = details["minutes"], details["dividends"]
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
            days_a.setdefault(i, {})[day] = (round(100 * (own[day] / nasdaq[day]["close"] - 1), 3), cause)
            per_stock[cause] += 1
            causes[cause] += 1
            kinds[kind] += 1
            days_total["abweichend"] += 1
            if day in minutes:
                days_total["abweichend_mit_minutenkursen"] += 1
            if nocp is not None and day in nocp:
                days_total["abweichend_mit_nocp"] += 1
            if cause == "ungeklaert":
                n_close = nasdaq[day]["close"]
                unexplained[unexplained_reason(yahoo.get("exchange"), nocp, day)] += 1
                patterns[f"stufen_{tick_bucket(own[day], n_close)}"] += 1
                patterns["stand_hoeher" if own[day] > n_close else "stand_niedriger"] += 1
                patterns["stand_auf_kursstufe" if on_grid(own[day], step(n_close)) else "stand_zwischen_kursstufen"] += 1
                patterns[f"umsatz_{volume_bucket(nasdaq[day].get('volume'), (yahoo['days'].get(day) or {}).get('volume'))}"] += 1
                patterns["mit_minutenkurs_keiner_gleich" if day in minutes else "ohne_minutenkurs"] += 1
                patterns[f"art_{kind}"] += 1
        stocks.append(
            {
                "idx": i,
                "top10": int(top10.get(i, 0)),
                "platz1": int(first.get(i, 0)),
                "kursbereich": info[i]["kursbereich"],
                "boerse": info[i]["boerse"],
                "abweichend": len(deviating),
                "groesste_abweichung_pct": round(100 * max(abs(own[day] / nasdaq[day]["close"] - 1) for day, _ in deviating), 2),
                "ursachen": dict(per_stock),
                "nocp_abrufbar": nocp is not None,
                "nocp_tage_ungleich": len(nocp_wrong),
                "minutenkurse_tage": len(minutes),
                "ereignisse": window_events,
            }
        )
        # Variante (a): an den abweichenden Tagen der Nasdaq-Kurs, sonst der Kurs des Stands
        changed = dict(own)
        for day, _ in deviating:
            changed[day] = nasdaq[day]["close"]
        days_arr = np.array(sorted(changed), dtype=np.int64)
        substituted[i] = (days_arr, np.array([changed[x] for x in days_arr.tolist()], dtype=np.float64), {day for day, _ in deviating})
    track = set(top10)  # Wirkung je Aktie: alle US-Aktien unter den ersten 10, in beiden Varianten
    effect, moves_a, changes_a = ranking_effect(stand, substituted, liquid, min_trend, track)
    effect_nocp, moves_b, changes_b = ranking_effect(stand, substituted_nocp, liquid, min_trend, track)
    ordered = sorted(stocks, key=lambda s: (-s["top10"], -s["abweichend"])) + sorted(nocp_only, key=lambda s: (-s["top10"], -s["nocp_tage_ungleich"]))
    letters = {s["idx"]: letter_label(k) for k, s in enumerate(ordered)}
    legend: list[dict] = []
    other_set = set(other_job)

    def letter(i: int | None) -> str:
        """Buchstabe einer Aktie aus den geänderten Ranglisten; Aktien ohne eigene Zeile kommen in die Legende."""
        if i is None:
            return "–"
        if i not in letters:
            letters[i] = letter_label(len(letters))
            if i in info:
                state = "verglichen"
            elif i in failures:
                state = "ohne_antwort"
            elif i in no_prices:
                state = "ohne_vergleichskurse"
            elif i in other_set:
                state = "anderer_job"
            else:
                state = "nicht_ausgewaehlt"
            entry = {"aktie": letters[i], "abgefragt": i in info, "zustand": state, "top10": int(top10.get(i, 0))}
            entry.update(info.get(i, {}))
            legend.append(entry)
        return letters[i]

    def trigger_days(variant_days: dict[int, dict[int, tuple[float, str]]], j: int, start: int) -> dict:
        days = sorted(d for d in (variant_days.get(j) or {}) if d >= start)
        shown = [{"tag": nachrechnen._iso(d), "abweichung_pct": variant_days[j][d][0], "ursache": variant_days[j][d][1]} for d in days[:MAX_TRIGGER_DAYS]]
        return {"aktie": letter(j), "tage": shown, "weitere_tage": max(0, len(days) - MAX_TRIGGER_DAYS)}

    def lettered(changes: list[dict], variant_days: dict) -> list[dict]:
        out = []
        for c in changes:
            row = {"h": c["h"], "gruppe": c["gruppe"], "w": c["w"], "platz1": [letter(x) for x in c["platz1"]] if c.get("platz1") else None,
                   "raus": [letter(x) for x in c["raus"]], "rein": [letter(x) for x in c["rein"]]}
            if c.get("platz1"):
                row.update(
                    {
                        "platz_des_neuen_vorher": c.get("platz_des_neuen_vorher"),
                        "rendite_pct": {letter(j): [None if v is None else round(100 * v, 3) for v in pair] for j, pair in c["rendite"].items()},
                        "r2": {letter(j): [None if v is None else round(float(v), 5) for v in pair] for j, pair in c["r2"].items()},
                        "ausloeser": None if c["ausloeser"] is None else [trigger_days(variant_days, j, c["start"][j]) for j in c["ausloeser"]],
                        "allein_ausreichend": [letter(j) for j in c["allein"]],
                        "ersetzte_aktien_im_zeitraum": c["ersetzte_im_zeitraum"],
                        "nicht_untersucht": bool(c.get("nicht_untersucht")),
                    }
                )
            out.append(row)
        return out

    changes_a, changes_b = lettered(changes_a, days_a), lettered(changes_b, days_b)
    by_idx = {s["idx"]: s for s in stocks}
    nocp_only_idx = {s["idx"] for s in nocp_only}
    coverage = Counter()
    for i in top10:
        coverage["us_aktien_unter_ersten_10"] += 1
        if i in failures:
            coverage["abruf_fehlgeschlagen"] += 1
        elif i not in compared:
            coverage["ohne_nasdaq_kurse"] += 1
        else:
            coverage["verglichen"] += 1
            s = by_idx.get(i)
            if s is None:
                coverage["ohne_abweichung"] += 1
                coverage["davon_nur_nocp_abweichend"] += i in nocp_only_idx
            elif s["ursachen"].get("ungeklaert"):
                coverage["mit_ungeklaerten_tagen"] += 1
            else:
                coverage["alle_abweichungen_belegt"] += 1
    for s in stocks + nocp_only:
        s["aktie"] = letters[s["idx"]]
        s["rangwirkung"] = moves_a.get(s["idx"], {})
        s["rangwirkung_nocp"] = moves_b.get(s["idx"], {})
        del s["idx"]
    # Zuordnung jedes Buchstabens zu genau einer Aktie: ihr bester Platz in einer Rangliste dieses Stands (in der App mit
    # der Passphrase nachzusehen) – eindeutig, ohne Namen im öffentlichen Protokoll
    places_of = best_places(stand, set(letters))
    mapping = []
    for i, name in sorted(letters.items(), key=lambda kv: (len(kv[1]), kv[1])):
        found = places_of.get(i)
        mapping.append({"aktie": name, "fundstelle": None if found is None else {"h": found[1], "gruppe": "AB"[found[2]], "w": found[3], "platz": found[0]}})
    by_group_coverage = {g: Counter() for g in SHARDS[auswahl]}
    for i in chosen:
        g = group_of[i]
        if i in failures:
            by_group_coverage[g]["abruf_fehlgeschlagen"] += 1
        elif i in compared:
            by_group_coverage[g]["verglichen"] += 1
            by_group_coverage[g][f"nocp_{nocp_state[i]}"] += 1
        else:
            by_group_coverage[g]["keine_vergleichskurse"] += 1
            by_group_coverage[g][f"keine_vergleichskurse_{no_prices.get(i, 'unbekannt')}"] += 1
    intervals = getattr(http, "min_interval", None)
    report = {
        "stand": sid,
        "stichtag": nachrechnen._iso(cutoff),
        "abgerufen_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "auswahl": auswahl,
        "ausgewaehlt": len(chosen),
        "ausgewaehlt_insgesamt": selected,
        "im_anderen_job": len(other_job),
        "davon_aus_den_ersten_20": from_top,
        "plaetze": places,
        "abruf": dict(sources),
        "abrufrunden": rounds,
        "abruf_nachgeholt": recovered,
        "abruf_fehlgeschlagen": len(failures),
        "abruf_je_gruppe": dict(by_group),
        "abdeckung_je_gruppe": {g: dict(v) for g, v in by_group_coverage.items()},
        "ohne_vergleichskurse": len(no_prices),
        "sperrpausen": block_pauses,
        "nasdaq_anfragen": nasdaq_requests(http),
        "nasdaq_anfragen_bis_zur_ersten_sperre": first_block,
        "nasdaq_abstand_s": intervals.get(NASDAQ_HOST) if isinstance(intervals, dict) else None,
        "nocp_abruf": dict(nocp_probe),
        "nocp_felder": sorted(nocp_fields),
        "nocp_vergleich": dict(nocp_compare),
        "detailabruf": dict(detail_status),
        "tage": dict(days_total),
        "arten": dict(kinds),
        "nur_eine_quelle": dict(only),
        "umsatz_vergleich": dict(volumes),
        "ursachen": dict(causes),
        "ungeklaert_gruende": dict(unexplained),
        "ungeklaert_muster": dict(patterns),
        "aktien_mit_abweichung": len(stocks),
        "aktien_mit_ereignis_im_zeitraum": dict(events),
        "top10_abdeckung": dict(coverage),
        "aktien": sorted(stocks, key=lambda s: (len(s["aktie"]), s["aktie"])),
        "aktien_nur_nocp": sorted(nocp_only, key=lambda s: (len(s["aktie"]), s["aktie"])),
        "ranglisten": effect,
        "ranglisten_offizieller_schlusskurs": effect_nocp,
        "aenderungen_nasdaq": changes_a,
        "aenderungen_offizieller_schlusskurs": changes_b,
        "weitere_buchstaben": legend,
        "zuordnung": mapping,
    }
    report["urteil"] = verdict(report)
    return report


def verdict(report: dict) -> str:
    """„unvollstaendig“ (eine Aktie blieb ohne Antwort oder ohne Vergleichskurse – fehlende Daten zählen nicht als geprüft),
    „ungeklaert“ (mindestens ein abweichender Tag ohne Beleg), „belegt“ (jede Abweichung belegt) oder „keine_abweichungen“."""
    if report.get("abruf_fehlgeschlagen") or report.get("ohne_vergleichskurse"):
        return "unvollstaendig"
    if (report.get("ursachen") or {}).get("ungeklaert"):
        return "ungeklaert"
    return "belegt" if (report.get("tage") or {}).get("abweichend") else "keine_abweichungen"


def leader_change(members: np.ndarray, w: str, order: list[int], new_leader: int, candidates: list[int], base: tuple, new: tuple, start_of: dict[int, int]) -> dict:
    """Einzelheiten eines neuen Platzes 1: Rendite und R² des bisherigen und des neuen Spitzenreiters vorher/nachher, sein
    bisheriger Platz, und welche ersetzten Kurse den Wechsel auslösen – geprüft, indem die Rangliste nur mit den Kursen
    einzelner Aktien neu gerechnet wird: erst der bisherige und der neue Spitzenreiter je allein, dann beide, dann
    nacheinander weitere ersetzte Aktien (größte Änderung der Rendite zuerst), bis Platz 1 wechselt wie mit allen."""
    status, r_of, r2_of = base
    status_new, r_new, r2_new = new
    old_leader = order[0]

    def leader_with(subset: list[int]) -> int | None:
        st, r, r2 = status.copy(), dict(r_of), dict(r2_of)
        for j in subset:
            st[j], r[j], r2[j] = status_new[j], r_new[j], r2_new[j]
        ranked = lists_of(nachrechnen.rank_group(members, st, r, r2))[w]
        return int(ranked[0]) if len(ranked) else None

    own = [j for j in (old_leader, new_leader) if j in candidates]
    alone = [j for j in own if leader_with([j]) == new_leader]
    needed: list[int] | None = None
    if alone:
        needed = [alone[0]]
    elif own and leader_with(own) == new_leader:
        needed = list(own)
    else:
        def size(j: int) -> float:
            change_r2 = abs(float(r2_new[j]) - float(r2_of[j])) if r2_new.get(j) is not None and r2_of.get(j) is not None else 0.0
            return abs(r_new[j] - r_of[j]) + change_r2

        subset = list(own)
        for j in sorted((j for j in candidates if j not in (old_leader, new_leader)), key=lambda j: (-size(j), j))[:MAX_TRIGGER_SEARCH]:
            subset.append(j)
            if leader_with(subset) == new_leader:
                needed = subset
                break
    if needed and len(needed) <= 5:
        # auch eine weitere Aktie kann allein ausreichen (die Suche fügt sie der Reihe nach hinzu)
        alone += [j for j in needed if j not in alone and (len(needed) == 1 or leader_with([j]) == new_leader)]
    involved = {old_leader, new_leader, *(needed or [])}
    return {
        "platz_des_neuen_vorher": order.index(new_leader) + 1 if new_leader in order else None,
        "rendite": {j: (r_of.get(j), r_new.get(j)) for j in (old_leader, new_leader)},
        "r2": {j: (r2_of.get(j), r2_new.get(j)) for j in (old_leader, new_leader)},
        "ausloeser": needed,
        "allein": alone,
        "ersetzte_im_zeitraum": len(candidates),
        "start": {j: start_of[j] for j in involved if j in start_of},
    }


def best_places(stand: nachrechnen.Stand, wanted: set[int]) -> dict[int, tuple[int, int, int, int]]:
    """Bester Platz jeder gesuchten Aktie in den Ranglisten dieses Stands: (Platz, Zeitraum, Gruppe 0 = A / 1 = B,
    Gewichtung) – der kleinste Platz, dann der kürzeste Zeitraum, Gruppe A vor B, kleinere Gewichtung zuerst."""
    best: dict[int, tuple[int, int, int, int]] = {}
    if not wanted:
        return best
    for h in range(1, 91):
        win = stand.get(f"windows/{h}.full.bin")
        stand.drop(f"windows/{h}.full.bin")
        orders = win["orders"]
        lists = [(0, 0, orders.get("v0") or []), (1, 0, orders.get("v0l") or [])]
        for group, key in ((0, "u"), (1, "ul")):
            lists += [(group, int(w), values) for w, values in (orders.get(key) or {}).items() if str(w) != "0"]
        for group, w, values in lists:
            for place, i in enumerate(values, start=1):
                i = int(i)
                if i in wanted:
                    candidate = (place, h, group, w)
                    if i not in best or candidate < best[i]:
                        best[i] = candidate
    return best


def ranking_effect(stand: nachrechnen.Stand, substituted: dict[int, tuple[np.ndarray, np.ndarray, set[int]]], liquid, min_trend: int, top_stocks: set[int]) -> tuple[dict, dict, list[dict]]:
    """Alle Ranglisten mit den Kursen des Stands und mit den ersetzten Kursen (unabhängige Rechnung): Zählwerte, Wirkung je
    Aktie aus ``top_stocks`` und – einzeln – jede Rangliste mit anderem Platz 1 oder anderen Aktien unter den ersten 10."""
    totals: Counter = Counter()
    moves: dict[int, Counter] = {i: Counter() for i in top_stocks}
    changes: list[dict] = []
    attributed = 0
    for h in range(1, 91):
        if not substituted:
            break
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
        touched: list[int] = []  # Aktien mit ersetzten Kursen in diesem Zeitraum
        for i in idx:
            if i not in substituted:
                continue
            days, closes, deviating = substituted[i]
            if not any(start_of[i] <= day <= int(days[-1]) for day in deviating):
                continue  # kein ersetzter Tag im Zeitraum: Werte des Stands bleiben (auch R² nach der Formel des Rechenkerns)
            r, r2, st = window_values(days, closes, start_of[i], min_trend)
            if r != r_of[i] or (r2 is None) != (r2_of[i] is None) or (r2 is not None and r2_of[i] is not None and abs(r2 - r2_of[i]) > 1e-12) or st != int(status[i]):
                changed += 1
            r_new[i], r2_new[i], status_new[i] = r, r2, st
            touched.append(i)
        if not changed:
            continue
        totals["zeitraeume_mit_geaenderten_werten"] += 1
        groups = (("A", idx), ("B", [i for i in idx if liquid[i]]))
        for name, members in groups:
            members_arr = np.array(members, dtype=np.int64)
            before = lists_of(nachrechnen.rank_group(members_arr, status, r_of, r2_of))
            after = lists_of(nachrechnen.rank_group(members_arr, status_new, r_new, r2_new))
            in_group = set(members)
            candidates = [i for i in touched if i in in_group]
            for w, order in before.items():
                if not order and not after[w]:
                    continue
                totals["ranglisten_verglichen"] += 1
                flags = compare_orders(order, after[w])
                for flag, value in flags.items():
                    if value:
                        totals[f"{flag}_geaendert"] += 1
                if flags["spitze"] or flags["top10_aktien"]:
                    change = {
                        "h": h,
                        "gruppe": name,
                        "w": int(w),
                        "platz1": [order[0] if order else None, after[w][0] if after[w] else None] if flags["spitze"] else None,
                        "raus": sorted(set(order[:10]) - set(after[w][:10])),
                        "rein": sorted(set(after[w][:10]) - set(order[:10])),
                    }
                    if flags["spitze"] and order and after[w]:
                        if attributed < MAX_ATTRIBUTIONS:
                            attributed += 1
                            change.update(leader_change(members_arr, w, order, after[w][0], candidates, (status, r_of, r2_of), (status_new, r_new, r2_new), start_of))
                        else:
                            change.update({"nicht_untersucht": True, "platz_des_neuen_vorher": order.index(after[w][0]) + 1 if after[w][0] in order else None,
                                           "rendite": {}, "r2": {}, "ausloeser": None, "allein": [], "ersetzte_im_zeitraum": len(candidates), "start": {}})
                    changes.append(change)
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
    return dict(totals), {i: dict(v) for i, v in moves.items()}, changes


def _counts(counts: dict, texts: dict | None = None) -> str:
    return ", ".join(f"{(texts or {}).get(k, k)} {v}" for k, v in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])) if v) or "keine"


def _effect(e: dict) -> str:
    return (
        f"{e.get('ranglisten_verglichen', 0)} betroffene von {e.get('ranglisten_insgesamt', 0)} Ranglisten neu gerechnet – Platz 1 anders "
        f"{e.get('spitze_geaendert', 0)}, andere Aktien unter den ersten 10 {e.get('top10_aktien_geaendert', 0)}, andere Reihenfolge der ersten 10 "
        f"{e.get('top10_reihenfolge_geaendert', 0)}, irgendeine Änderung {e.get('reihenfolge_geaendert', 0)}"
    )


VERDICT_TITLE = {
    "unvollstaendig": "Kursursachen: UNVOLLSTÄNDIG – {n} Aktien ohne Antwort einer Quelle, {k} ohne Vergleichskurse; {u} von {a} abweichenden Tagen ungeklärt",
    "ungeklaert": "Kursursachen: NICHT VOLLSTÄNDIG BELEGT – {u} von {a} abweichenden Tagen ungeklärt",
    "belegt": "Kursursachen: jede Abweichung belegt ({a} Tage)",
    "keine_abweichungen": "Kursursachen: keine Abweichungen zu Nasdaq",
}
SUMMARY_NOTE = "vollständig in der Zusammenfassung dieses Jobs (Seite des Laufs, Abschnitt „Summary“)"


def _moves(m: dict) -> str:
    return (
        f"unter den ersten 10 {m.get('unter_ersten_10_vorher', 0)} → {m.get('unter_ersten_10_nachher', 0)}, Platz 1 {m.get('platz1_vorher', 0)} → "
        f"{m.get('platz1_nachher', 0)}, anderer Platz {m.get('platz_geaendert', 0)}"
    )


def _where(c: dict) -> str:
    return f"{c['h']} Tage Gruppe {c['gruppe']} {c['w']}/{100 - c['w']}"


def _method(c: dict) -> str:
    """Zeitraum und Berechnungsmethode einer Rangliste (Gruppe, Gewichtung Gleichmäßigkeit/Rendite)."""
    w = c["w"]
    weight = "nur Kursrendite" if w == 0 else ("nur Gleichmäßigkeit R²" if w == 100 else f"Gleichmäßigkeit {w} % und Rendite {100 - w} %")
    return f"{c['h']} Tage, Gruppe {c['gruppe']}, Gewichtung {w}/{100 - w} ({weight})"


def _pct(value: float | None) -> str:
    return "–" if value is None else f"{value:+.2f} %"


def _cause_label(code: str) -> str:
    return SHORT_CAUSE.get(code) or NOCP_NOTE.get(code) or code


def _changes(changes: list[dict], kind: str) -> str:
    """Kurzfassung der geänderten Ranglisten einer Variante: ``platz1`` (anderer Platz 1) oder ``top10``."""
    if kind == "platz1":
        items = [f"{_where(c)}: {c['platz1'][0]} → {c['platz1'][1]}" for c in changes if c.get("platz1")]
    else:
        items = [f"{_where(c)}: raus {' '.join(c['raus']) or '–'} rein {' '.join(c['rein']) or '–'}" for c in changes if c.get("raus") or c.get("rein")]
    if not items:
        return "keine"
    more = f"; und {len(items) - MAX_EVENTS} weitere (einzeln unten)" if len(items) > MAX_EVENTS else ""
    return f"{len(items)} – " + "; ".join(items[:MAX_EVENTS]) + more


def _leader_line(c: dict, variant: str, n: int, total: int) -> str:
    """Eine Rangliste mit neuem Platz 1: Zeitraum, Methode, bisheriger und neuer Spitzenreiter, auslösende Kursabweichungen."""
    before, after = c["platz1"]
    place = c.get("platz_des_neuen_vorher")
    parts = [f"{variant} {n}/{total} – {_method(c)}: bisher {before}, neu {after} " + (f"(vorher Platz {place})" if place else "(vorher nicht in dieser Rangliste)")]
    for name in (before, after):
        r = (c.get("rendite_pct") or {}).get(name)
        g = (c.get("r2") or {}).get(name)
        if r:
            text = f"{name}: Rendite {_pct(r[0])} → {_pct(r[1])}"
            if c["w"] and g:
                text += f", R² {'–' if g[0] is None else g[0]} → {'–' if g[1] is None else g[1]}"
            parts.append(text)
    triggers = c.get("ausloeser")
    if c.get("nicht_untersucht"):
        parts.append(f"Auslöser nicht untersucht (mehr als {MAX_ATTRIBUTIONS} neue Plätze 1 in dieser Variante) – {c.get('ersetzte_aktien_im_zeitraum', 0)} ersetzte Aktien im Zeitraum")
    elif triggers is None:
        parts.append(f"Auslöser nicht auf einzelne Aktien eingrenzbar – Platz 1 wechselt erst mit allen {c.get('ersetzte_aktien_im_zeitraum', 0)} ersetzten Aktien des Zeitraums")
    else:
        for tr in triggers:
            days = ", ".join(f"{d['tag']} {d['abweichung_pct']:+.3f} % ({_cause_label(d['ursache'])})" for d in tr["tage"]) or "keine ersetzten Tage im Zeitraum"
            more = f" und {tr['weitere_tage']} weitere Tage" if tr.get("weitere_tage") else ""
            parts.append(f"auslösend {tr['aktie']}: {days}{more}")
        alone = c.get("allein_ausreichend") or []
        parts.append("allein ausreichend: " + (" ".join(alone) if alone else "keine einzelne Aktie – nur zusammen"))
    return "; ".join(parts)


def _member_line(c: dict, variant: str) -> str:
    return f"{variant} – {_method(c)}: raus {' '.join(c['raus']) or '–'}, rein {' '.join(c['rein']) or '–'}"


LEGEND_STATE = {
    "ohne_antwort": "ausgewählt, aber ohne Antwort von Nasdaq – Kurse in beiden Varianten unverändert",
    "ohne_vergleichskurse": "ausgewählt, aber ohne Vergleichskurse bei Nasdaq – Kurse in beiden Varianten unverändert",
    "anderer_job": "im anderen Job geprüft – in diesem Job Kurse unverändert",
    "nicht_ausgewaehlt": "nicht ausgewählt (keine US-Aktie unter den ersten 20 einer Rangliste und nicht in der Zufallsstichprobe) – Kurse unverändert",
}


def _legend(entry: dict) -> str:
    if entry.get("zustand") in LEGEND_STATE:
        return LEGEND_STATE[entry["zustand"]]
    if not entry.get("abgefragt", True) or "boerse" not in entry:
        return "nicht abgefragt oder ohne Nasdaq-Kurse – Kurse in beiden Varianten unverändert"
    nocp = f", ungleich NOCP an {entry.get('nocp_ungleich', 0)} Tagen" if entry.get("nocp_ungleich") else ""
    return (
        f"{entry['boerse']}, {entry['kursbereich']}; unter den ersten 10 in {entry.get('top10', 0)} Ranglisten; "
        f"abweichend von der Nasdaq-Historie an {entry.get('abweichend', 0)} Tagen{nocp}"
    )


def _place_link(found: dict) -> str:
    """Wo die Aktie in der App steht (Rangliste mit allen Aktien, „Auffällige ausblenden“ aus)."""
    place = found["platz"]
    n = "10" if place <= 10 else ("50" if place <= 50 else "alle")
    page = f"&seite={(place - 1) // 50 + 1}" if n == "alle" else ""
    group = "&g=b" if found["gruppe"] == "B" else ""
    return f"#/ranking?h={found['h']}&w={found['w']}&p=native&n={n}{group}{page}"


def _coverage_line(name: str, c: dict) -> str:
    total = c.get("verglichen", 0) + c.get("keine_vergleichskurse", 0) + c.get("abruf_fehlgeschlagen", 0)
    no_prices = ", ".join(f"{text} {c[key]}" for key, text in (("keine_vergleichskurse_nasdaq_ohne_kurse", "Nasdaq ohne Kurse"), ("keine_vergleichskurse_stand_ohne_kurse_im_zeitraum", "Stand ohne Kurse im Zeitraum")) if c.get(key))
    nocp = ", ".join(f"{text} {c[key]}" for key, text in (("nocp_mit_nocp", "mit NOCP"), ("nocp_nasdaq_ohne_nocp", "Nasdaq-notiert ohne NOCP"), ("nocp_nicht_nasdaq_notiert", "ohne NOCP: nicht Nasdaq-notiert")) if c.get(key))
    return (
        f"{name}: {total} Aktien – erfolgreich verglichen {c.get('verglichen', 0)}" + (f" ({nocp})" if nocp else "")
        + f"; keine Vergleichskurse {c.get('keine_vergleichskurse', 0)}" + (f" ({no_prices})" if no_prices else "")
        + f"; Abruf fehlgeschlagen {c.get('abruf_fehlgeschlagen', 0)}"
    )


def build_lines(report: dict) -> tuple[str, str, list[str], list[tuple[str, list[str]]]]:
    """Titel, Art und Zeilen des Ergebnisses – Kopf (Urteil und Zählwerte) und Abschnitte mit Einzelheiten."""
    t, c, e = report["tage"], report["ursachen"], report["ranglisten"]
    explained = sum(v for k, v in c.items() if k != "ungeklaert")
    p = report.get("plaetze") or {}
    nc = report.get("nocp_vergleich") or {}
    cov = report.get("top10_abdeckung") or {}
    result = report.get("urteil") or verdict(report)
    shard = report.get("auswahl", "alle")
    title = VERDICT_TITLE[result].format(n=report.get("abruf_fehlgeschlagen", 0), k=report.get("ohne_vergleichskurse", 0), u=c.get("ungeklaert", 0), a=t.get("abweichend", 0))
    title = title.replace("Kursursachen:", f"Kursursachen{SHARD_TEXT[shard]}:", 1)
    level = {"unvollstaendig": "error", "ungeklaert": "error", "belegt": "notice", "keine_abweichungen": "notice"}[result]
    block = (
        f"; Sperrpausen {report.get('sperrpausen', 0)}"
        + (f" (erste nach {report['nasdaq_anfragen_bis_zur_ersten_sperre']} Anfragen an Nasdaq)" if report.get("nasdaq_anfragen_bis_zur_ersten_sperre") else "")
        + (f", Anfragen an Nasdaq {report['nasdaq_anfragen']}" if report.get("nasdaq_anfragen") is not None else "")
        + (f", Abstand zuletzt {report['nasdaq_abstand_s']} s" if report.get("nasdaq_abstand_s") is not None else "")
    )
    groups = report.get("abdeckung_je_gruppe") or {}
    head = [
        f"Nachträglich abgerufen am {report['abgerufen_utc']} (Nasdaq-Historie, offizieller Schlusskurs NOCP, Yahoo-Tages- und Minutenkurse, Dividenden) – keine Originaldaten. "
        f"Stand {report['stand']} (Kursstand {report['stichtag']}); {report['ausgewaehlt']} US-Aktien"
        + (f" in diesem Job, {report.get('im_anderen_job', 0)} im anderen Job (zusammen {report.get('ausgewaehlt_insgesamt', 0)}; davon {report['davon_aus_den_ersten_20']} aus den ersten 20 einer Rangliste). "
           if shard != "alle" else f" (davon {report['davon_aus_den_ersten_20']} aus den ersten 20 einer Rangliste). ")
        + f"Plätze unter den ersten 10 aller Ranglisten: {p.get('erste_10', 0)}, davon US-Aktien {p.get('erste_10_us', 0)} (nur diese führt Nasdaq); Platz 1: {p.get('platz_1', 0)}, davon US-Aktien {p.get('platz_1_us', 0)}",
    ]
    if groups:
        head.append("Abdeckung je Gruppe (fehlende Daten zählen nicht als geprüft):")
        head += [_coverage_line(GROUP_TEXT[g], groups.get(g) or {}) for g in GROUPS if g in groups]
        if "erste_10" in groups and "erste_20" in groups:
            both = Counter(groups.get("erste_10") or {}) + Counter(groups.get("erste_20") or {})
            head.append(_coverage_line("erste 20 gesamt (erste 10 und Plätze 11–20)", dict(both)))
        missing = [GROUP_TEXT[g] for g in GROUPS if g not in groups]
        if missing:
            head.append(f"Nicht in diesem Job (im anderen Job desselben Laufs geprüft): {', '.join(missing)}")
    head += [
        f"Abruf in {report.get('abrufrunden', 1)} Runden (nachgeholt {report.get('abruf_nachgeholt', 0)}, ohne Antwort {report.get('abruf_fehlgeschlagen', 0)}): {_counts(report['abruf'])}{block}; "
        f"NOCP: {_counts(report['nocp_abruf'])}" + (f" (Felder {', '.join(report['nocp_felder'])})" if report.get("nocp_felder") else "")
        + f"; Minutenkurse und Dividenden: {_counts(report.get('detailabruf') or {})}",
        f"Offizieller Schlusskurs (NOCP) aller Nasdaq-notierten Aktien der Auswahl: {nc.get('aktien', 0)} Aktien, {nc.get('tage', 0)} Tage – Stand gleich {nc.get('stand_gleich', 0)}, "
        f"Stand ungleich {nc.get('stand_ungleich', 0)}, Faktor eines Splits {nc.get('faktor_split', 0)} (NOCP unbereinigt, nicht ersetzt); "
        f"Nasdaq-Historie gleich {nc.get('nasdaq_historie_gleich', 0)}, ungleich {nc.get('nasdaq_historie_ungleich', 0)}",
        f"Börsentage gegen die Nasdaq-Historie verglichen {t.get('verglichen', 0)}, abweichend {t.get('abweichend', 0)} ({_counts(report.get('arten') or {})}; mit NOCP {t.get('abweichend_mit_nocp', 0)}, "
        f"mit Minutenkurs {t.get('abweichend_mit_minutenkursen', 0)}); Ursache belegt für {explained}: "
        + ("; ".join(f"{CAUSE_TEXT[k]} {c[k]}" for k in CAUSES if c.get(k) and k != "ungeklaert") or "–")
        + f"; ungeklärt (Ursache offen) {c.get('ungeklaert', 0)}",
        f"Ungeklärte Tage – Prüfgrenze bzw. Befund (erklärt, warum kein Beleg möglich war, nicht die Abweichung): {_counts(report.get('ungeklaert_gruende') or {}, UNEXPLAINED_TEXT)}; "
        f"Muster der ungeklärten Tage: {_counts(report.get('ungeklaert_muster') or {})}",
        f"Umsatz Nasdaq-Historie gegen Yahoo an allen verglichenen Tagen: {_counts(report.get('umsatz_vergleich') or {})}; "
        f"Tage nur im Stand {report['nur_eine_quelle'].get('nur_im_stand', 0)} (davon ohne Umsatz bei Yahoo {report['nur_eine_quelle'].get('nur_im_stand_ohne_umsatz_bei_yahoo', 0)}), "
        f"nur bei Nasdaq {report['nur_eine_quelle'].get('nur_bei_nasdaq', 0)} (davon mit Yahoo-Kurs {report['nur_eine_quelle'].get('nur_bei_nasdaq_yahoo_mit_kurs', 0)}); "
        f"Aktien mit Ereignis im Zeitraum: {_counts(report['aktien_mit_ereignis_im_zeitraum'])}",
        f"US-Aktien unter den ersten 10 irgendeiner Rangliste: {cov.get('us_aktien_unter_ersten_10', 0)} – verglichen {cov.get('verglichen', 0)} (ohne Abweichung {cov.get('ohne_abweichung', 0)}, "
        f"davon nur der offizielle Schlusskurs anders {cov.get('davon_nur_nocp_abweichend', 0)}; jede Abweichung belegt {cov.get('alle_abweichungen_belegt', 0)}, "
        f"mit ungeklärten Tagen {cov.get('mit_ungeklaerten_tagen', 0)}), ohne Nasdaq-Kurse {cov.get('ohne_nasdaq_kurse', 0)}, ohne Antwort {cov.get('abruf_fehlgeschlagen', 0)}",
        f"Ranglisten (unabhängige Rechnung, gleiche Zulassung zu Gruppe B) – (a) Nasdaq-Kurs an allen abweichenden Tagen: {_effect(e)}",
        f"(b) offizieller Schlusskurs (NOCP) an allen Tagen, an denen er vom Stand abweicht: {_effect(report.get('ranglisten_offizieller_schlusskurs') or {})}",
        f"Platz 1 anders – (a): {_changes(report.get('aenderungen_nasdaq') or [], 'platz1')} | (b): {_changes(report.get('aenderungen_offizieller_schlusskurs') or [], 'platz1')}",
        f"Andere Aktien unter den ersten 10 – (a): {_changes(report.get('aenderungen_nasdaq') or [], 'top10')} | (b): {_changes(report.get('aenderungen_offizieller_schlusskurs') or [], 'top10')}",
        "Lesart: Buchstaben statt Namen, Zuordnung zu genau einer Aktie im Abschnitt „Zuordnung der Buchstaben“; Abweichung = Stand gegenüber dem Ersatzkurs in %; "
        "Kurzformen je Aktie: " + "; ".join(f"„{SHORT_CAUSE[k]}“ = {CAUSE_TEXT[k]}" for k in CAUSES if k != "ungeklaert")
        + "; (a) mit Nasdaq-Kursen an den abweichenden Tagen, (b) mit dem offiziellen Schlusskurs",
    ]

    # Ranglisten mit neuem Platz 1 – jede einzeln, mit den auslösenden Kursabweichungen
    leaders: list[str] = []
    for key, variant in (("aenderungen_nasdaq", "(a) Nasdaq-Kurs"), ("aenderungen_offizieller_schlusskurs", "(b) offizieller Schlusskurs")):
        rows = [x for x in report.get(key) or [] if x.get("platz1")]
        leaders += [_leader_line(x, variant, n, len(rows)) for n, x in enumerate(rows, start=1)]
        if not rows:
            leaders.append(f"{variant}: in keiner Rangliste ein anderer Platz 1")
    members: list[str] = []
    for key, variant in (("aenderungen_nasdaq", "(a)"), ("aenderungen_offizieller_schlusskurs", "(b)")):
        members += [_member_line(x, variant) for x in report.get(key) or [] if x.get("raus") or x.get("rein")]

    # je Aktie: Aktien unter den ersten 10 (mit eigener Abweichung, dann nur mit anderem NOCP), danach die übrigen
    focus = [s for s in report["aktien"] if s["top10"] or s["ursachen"].get("ungeklaert") or s["groesste_abweichung_pct"] > 0.5]
    top_rows, other_rows, nocp_rows = [], [], []
    for s in focus:
        moves_a, moves_b = s.get("rangwirkung") or {}, s.get("rangwirkung_nocp") or {}
        (top_rows if s["top10"] else other_rows).append(
            f"Aktie {s['aktie']} ({s['boerse']}, {s['kursbereich']}; unter den ersten 10 in {s['top10']} Ranglisten, Platz 1 in {s['platz1']}): {s['abweichend']} Tage abweichend, "
            f"größte {s['groesste_abweichung_pct']} %; Ursachen: " + (", ".join(f"{SHORT_CAUSE[k]} {s['ursachen'][k]}" for k in CAUSES if s["ursachen"].get(k)) or "–")
            + f"; NOCP {'ja' if s['nocp_abrufbar'] else 'nein'}" + (f" (Stand ungleich NOCP an {s.get('nocp_tage_ungleich', 0)} Tagen)" if s["nocp_abrufbar"] else "")
            + f", Minutenkurse {s['minutenkurse_tage']} Tage; Ereignisse {', '.join(f'{k} {v}' for k, v in s['ereignisse'].items() if v) or 'keine'}"
            + (f"; (a) {_moves(moves_a)}" if moves_a else "")
            + (f"; (b) {_moves(moves_b)}" if moves_b else "")
        )
    for s in report.get("aktien_nur_nocp") or []:
        moves_a, moves_b = s.get("rangwirkung") or {}, s.get("rangwirkung_nocp") or {}
        nocp_rows.append(
            f"Aktie {s['aktie']} ({s['boerse']}, {s['kursbereich']}; unter den ersten 10 in {s['top10']} Ranglisten, Platz 1 in {s['platz1']}): Stand wie Nasdaq-Historie, "
            f"aber ungleich NOCP an {s['nocp_tage_ungleich']} Tagen (größte {s['groesste_abweichung_nocp_pct']} %)"
            + (f"; (a) {_moves(moves_a)}" if moves_a else "")
            + (f"; (b) {_moves(moves_b)}" if moves_b else "")
        )
    stock_rows = top_rows + nocp_rows + other_rows
    small = len(report["aktien"]) - len(focus)
    if small:
        stock_rows.append(f"Weitere {small} Aktien mit kleinen Abweichungen (höchstens 0,5 %), nicht unter den ersten 10 und mit belegter Ursache – Zählwerte oben, Einzelheiten im Bericht")

    # Zuordnung: jeder Buchstabe genau eine Aktie – ihr bester Platz in einer Rangliste des Stands
    legend = {x["aktie"]: x for x in report.get("weitere_buchstaben") or []}
    mapping = []
    for entry in report.get("zuordnung") or []:
        found = entry.get("fundstelle")
        where = (
            f"Rangliste {found['h']} Tage, Gruppe {found['gruppe']}, {found['w']}/{100 - found['w']}, Platz {found['platz']} (in der App: {_place_link(found)})"
            if found else "in keiner Rangliste dieses Stands"
        )
        extra = f" – {_legend(legend[entry['aktie']])}" if entry["aktie"] in legend else ""
        mapping.append(f"{entry['aktie']} = {where}{extra}")
    if mapping:
        mapping.insert(0, f"Stand {report['stand']}; in der App mit der Passphrase unter „Rangliste“, Einstellung „Auffällige ausblenden“ aus (ältere Stände über „Datenstand & Betrieb → Frühere Stände“)")
    sections = [
        ("Platz 1 anders – jede Rangliste einzeln", leaders),
        ("Andere Aktien unter den ersten 10 – einzeln", members),
        ("Ursachen je Aktie", stock_rows),
        ("Zuordnung der Buchstaben", mapping),
    ]
    return title, level, head, [(name, lines) for name, lines in sections if lines]


def _cut(text: str, limit: int) -> int:
    """Länge des längsten Anfangs von ``text`` mit höchstens ``limit`` Bytes – an einem Leerzeichen, wenn eines in der
    zweiten Hälfte liegt; mindestens ein Zeichen (kein Stillstand)."""
    size, end = 0, 0
    for k, ch in enumerate(text):
        size += len(ch.encode("utf-8"))
        if size > limit:
            break
        end = k + 1
    space = text.rfind(" ", 0, end)
    return space if space > end // 2 else max(end, 1)


def split_lines(lines: list[str], limit: int = gegen.MAX_ANNOTATION_BYTES - 300) -> list[str]:
    """Zu lange Zeilen an „; “ (notfalls an Leerzeichen) in Fortsetzungszeilen („… “) teilen – GitHub kürzt einen langen
    Hinweis sonst still. Kein Text geht verloren: ohne die Vorsilbe ergeben die Teile wieder die Zeile."""
    room = limit - len("… ".encode("utf-8"))
    out: list[str] = []
    for line in lines:
        if len(line.encode("utf-8")) <= limit:
            out.append(line)
            continue
        pieces: list[str] = []
        current = ""
        for token in line.split("; "):
            candidate = f"{current}; {token}" if current else token
            if len(candidate.encode("utf-8")) <= room:
                current = candidate
                continue
            if current:
                pieces.append(current + ";")
                current = ""
            while len(token.encode("utf-8")) > room:  # ein einzelnes Stück zu lang: an einem Leerzeichen trennen
                cut = _cut(token, room)
                pieces.append(token[:cut])
                token = token[cut:].lstrip()
            current = token
        if current:
            pieces.append(current)
        out += [pieces[0]] + [f"… {x}" for x in pieces[1:]]
    return out


def command(level: str, title: str, lines: list[str]) -> str:
    return f"::{level} title={gegen._title(title)}::" + "%0A".join(line.replace("%", "%25").replace("\r", "").replace("\n", " ") for line in lines)


def distribute(items: list[tuple[str, str, list[str]]], shard: str = "") -> dict:
    """Hinweise in fester Reihenfolge auf den Prüfschritt und die Schritte „Einzelheiten“ verteilen: je Schritt und Art
    höchstens MAX_PER_STEP, je Job höchstens MAX_JOB_ANNOTATIONS. Was nicht passt, wird im letzten Hinweis gezählt und
    genannt – nichts geht unbemerkt verloren; vollständig steht alles in der Zusammenfassung des Jobs."""
    steps: list[list[str]] = [[] for _ in range(MAX_STEPS)]
    used = [Counter() for _ in range(MAX_STEPS)]
    k, placed = 0, 0
    for level, title, lines in items:
        while k < MAX_STEPS and used[k][level] >= MAX_PER_STEP:
            k += 1
        if k >= MAX_STEPS or placed >= MAX_JOB_ANNOTATIONS - 1:
            break
        steps[k].append(command(level, title, lines))
        used[k][level] += 1
        placed += 1
    rest = items[placed:]
    if rest:
        names = Counter(title.split(" (")[0] for _, title, _ in rest)
        text = f"Nicht als Hinweis: {len(rest)} von {len(items)} Teilen ({', '.join(f'{n} {v}' for n, v in names.items())}) – {SUMMARY_NOTE}"
    else:
        text = f"Alle {len(items)} Teile als Hinweis ausgegeben – {SUMMARY_NOTE}"
    # Abschluss in den letzten belegten Schritt (der Prüfschritt hat zusätzlich den Hinweis „Dauer“ – dort höchstens 9)
    last = max((n for n, s in enumerate(steps) if s), default=0)
    if last == 0 and used[0]["notice"] >= MAX_PER_STEP and MAX_STEPS > 1:
        last = 1
    steps[last].append(command("notice", f"Kursursachen{shard}: Vollständigkeit der Hinweise", [text]))
    return {"schritte": steps, "teile": len(items), "ausgegeben": placed, "nicht_ausgegeben": len(rest)}


def annotation_plan(report: dict) -> dict:
    title, level, head, sections = build_lines(report)
    items = [(level, title, part) for part in gegen.chunked(split_lines(head))]
    for name, lines in sections:
        parts = gegen.chunked(split_lines(lines))
        items += [("notice", f"{name}{SHARD_TEXT[report.get('auswahl', 'alle')]} ({n}/{len(parts)}; Buchstaben statt Namen)", part) for n, part in enumerate(parts, start=1)]
    return distribute(items, SHARD_TEXT[report.get("auswahl", "alle")])


def annotations(report: dict) -> list[str]:
    """Alle Hinweise in der Reihenfolge der Schritte (Prüfschritt zuerst)."""
    return [line for step in annotation_plan(report)["schritte"] for line in step]


def summary_markdown(report: dict) -> str:
    """Vollständiges Ergebnis für die Zusammenfassung des Jobs – ohne Grenze der Hinweise, ohne Namen."""
    title, _, head, sections = build_lines(report)
    out = [f"## {title}", ""] + [f"- {line}" for line in head]
    for name, lines in sections:
        out += ["", f"### {name}", ""] + [f"- {line}" for line in lines]
    return "\n".join(out) + "\n"


def print_part(path: Path | None, part: int) -> int:
    """Schritt „Einzelheiten“: die Hinweise dieses Schritts aus der Datei des Prüfschritts ausgeben."""
    if path is None or not path.exists():
        print(f"Kursursachen: keine Hinweise für Schritt {part} (Prüfschritt ohne Ergebnis)")
        return 0
    plan = json.loads(path.read_text(encoding="utf-8"))
    steps = plan.get("schritte") or []
    for line in steps[part - 1] if 0 < part <= len(steps) else []:
        print(line)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", "szymeklh87-commits/tr-aktienvergleich"))
    parser.add_argument("--bericht", type=Path, help="vollständiger Bericht ohne Namen (JSON; nur für Läufe von Hand – der Workflow lädt nichts hoch)")
    parser.add_argument("--hinweise", type=Path, help="alle Hinweise, verteilt auf die Schritte (JSON)")
    parser.add_argument("--teil", type=int, help=f"nur die Hinweise dieses Schritts aus --hinweise ausgeben (2 bis {MAX_STEPS})")
    parser.add_argument("--auswahl", choices=sorted(SHARDS), default=os.environ.get("AUSWAHL") or "alle", help="welcher Teil der Auswahl in diesem Job (Nasdaq: etwa 430 Anfragen je Rechner)")
    args = parser.parse_args(argv)
    if args.teil:
        return print_part(args.hinweise, args.teil)
    started = time.monotonic()
    from traktien.providers.http import HttpClient

    # kurze Zeitgrenze, wenige Wiederholungen je Anfrage: Fehler holen die Nachholrunden nach (mit Pause), nicht 4 × 25 s
    http = HttpClient(impersonate="chrome", max_retries=1, timeout=12, min_interval={NASDAQ_HOST: NASDAQ_INTERVAL_S, "query2.finance.yahoo.com": 0.3})
    try:
        with tempfile.TemporaryDirectory() as temp:
            meta, stands = nachrechnen.load_release_stands(args.repo, os.environ.get("GITHUB_TOKEN"), Path(temp), None)
            key = nachrechnen.key_for(meta["descriptor"])
            official = meta["status"].get("latest_official_snapshot_id")
            folder = dict(stands).get(official)
            if folder is None:
                print("::error title=Kursursachen::Stand mit Schlusskursen nicht im Release gefunden")
                return 1
            report = run(nachrechnen.Stand(folder, official, key), official, http, auswahl=args.auswahl)
        plan = annotation_plan(report)
        for line in plan["schritte"][0]:
            print(line)
        if args.hinweise:
            args.hinweise.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
        if args.bericht:
            args.bericht.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        summary = os.environ.get("GITHUB_STEP_SUMMARY")
        if summary:
            with open(summary, "a", encoding="utf-8") as handle:
                handle.write(summary_markdown(report))
        return 0 if report["urteil"] in ("belegt", "keine_abweichungen") else 1
    finally:
        print(f"::notice title=Kursursachen{SHARD_TEXT[args.auswahl]}::Dauer {round(time.monotonic() - started)} s")


if __name__ == "__main__":
    try:
        code = main()
    except Exception as exc:  # noqa: BLE001 - Abbruchgrund ohne Inhalte
        print(f"::error title=Kursursachen abgebrochen::{type(exc).__name__}: {str(exc).splitlines()[0][:200] if str(exc) else ''}")
        code = 1
    sys.exit(code)
