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

**Seit 25.10.2026** (Prüfskript, App unverändert 1.18.2; Auftrag vom 25.10.2026, 03:47 Uhr):

* **Befund ≠ Ursache:** „Nasdaq-Historie = NOCP, Stand nicht“ ist ein Befund (``abweichung_vom_nocp``), keine belegte
  Ursache; belegt ist eine Ursache nur, wenn gezeigt ist, wodurch der Unterschied entsteht (Kursstufe, letzter Abschluss vor
  16:00 Uhr ohne Schlussauktion, kein Umsatz, Bereinigung, Split). Je Vergleich getrennt gezählt: bestätigte Übereinstimmung,
  festgestellte Abweichung, belegte Ursache, ungeklärte Ursache, fehlende Vergleichsmöglichkeit – auch für jeden Tag mit
  Stand ≠ NOCP (Variante b).
* **Drei Jobs** (erste 10, Plätze 11–20, Zufallsstichprobe), damit auch die Gegenproben der Dividenden in das Kontingent von
  etwa 430 Anfragen je Rechner passen.
* **Zusatzquellen** für US-Aktien ohne Nasdaq-Kurse (``kurse_zusatzquellen.py``), Variante (c).
* **Gemeinsame Wirkung:** Jeder Job übergibt seine Ersatzkurse verschlüsselt (Schlüssel des Stands) als Ausgabe des Jobs;
  der Job „gemeinsame Wirkung“ rechnet alle Ranglisten mit den Kursen aller Jobs zusammen gegen denselben Stand (Option
  ``--stand``), dazu jeden Job allein und die Aufteilung des Laufs 40139805053 zum Vergleich.
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import hashlib
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
import kurse_zusatzquellen as zusatz  # noqa: E402 - weitere Quellen für US-Aktien ohne Nasdaq-Kurse (seit dem 25.10.2026)
import nachrechnen  # noqa: E402 - Datenstand lesen, unabhängige Ranglisten
from traktien.util import crypto  # noqa: E402 - Übergabe zwischen den Jobs verschlüsselt (wie die Datenstände)

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
# Pausen von 3 Minuten und mit 3 s Abstand). Lauf 40139805053 (zwei Jobs): der Job „erste 20“ brauchte genau 430 Anfragen,
# die letzten 4 Gegenproben der Dividenden blieben ohne Antwort – seit dem 25.10.2026 drei Jobs auf drei Rechnern
SHARDS = {
    "alle": GROUPS,
    "erste10": ("erste_10",),
    "plaetze11_20": ("erste_20",),
    "zufall": ("zufall",),
    "erste20": ("erste_10", "erste_20"),  # Aufteilung bis 1.18.2 (Lauf 40139805053) – nur noch für den Vergleich
}
SHARD_TEXT = {"alle": "", "erste10": " (erste 10)", "plaetze11_20": " (Plätze 11–20)", "zufall": " (Zufallsstichprobe)", "erste20": " (erste 20)"}
LEGS = ("erste10", "plaetze11_20", "zufall")  # die Jobs des Workflows (Matrix „auswahl“, gleiche Reihenfolge)
TRANSFER_FORMAT = "kursursachen-uebergabe/1"
TRANSFER_MAX_BYTES = 900_000  # GitHub: höchstens 1 MB je Ausgabe eines Jobs
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
# Einordnung eines abweichenden Tags (seit dem 25.10.2026, Auftrag 25.10.2026, 03:47 Uhr: „‚Yahoo weicht vom offiziellen Schlusskurs
# ab‘ beschreibt zunächst einen Befund. Eine Ursache gilt erst als belegt, wenn nachgewiesen ist, wodurch der Unterschied
# entsteht.“). Bis 1.18.2 zählte „offizieller_schlusskurs“ (Nasdaq-Historie = NOCP, Stand nicht) als belegte Ursache – das
# ist der Befund „abweichung_vom_nocp“: Der Stand führt an dem Tag nicht den offiziellen Schlusskurs; wodurch, ist offen.
CAUSES = (
    "stand_ist_nocp",
    "letzter_abschluss",
    "nasdaq_letzter_abschluss",
    "rundung",
    "kein_handel",
    "dividendenbereinigung",
    "split",
    "abweichung_vom_nocp",
    "ungeklaert",
)
EVIDENCE = {"letzter_abschluss", "nasdaq_letzter_abschluss", "rundung", "kein_handel", "dividendenbereinigung", "split"}  # Ursache belegt
MATCH_OFFICIAL = {"stand_ist_nocp"}  # Stand = offizieller Schlusskurs: bestätigte Übereinstimmung, abweichend nur die Nasdaq-Historie
OPEN = {"abweichung_vom_nocp", "ungeklaert"}  # Abweichung festgestellt, Ursache ungeklärt
CAUSE_TEXT = {
    "stand_ist_nocp": "Stand = offizieller Schlusskurs (NOCP), abweichend nur die Nasdaq-Historie",
    "letzter_abschluss": "Stand = letzter Abschluss vor 16:00 Uhr (ohne Schlussauktion), Vergleichskurs ein anderer Schlusskurs",
    "nasdaq_letzter_abschluss": "Nasdaq-Historie = letzter Abschluss vor 16:00 Uhr (ohne Schlussauktion), Stand ein anderer Schlusskurs",
    "rundung": "unter einer Kursstufe (Stand zwischen zwei Stufen, Vergleichsquelle zeigt die Nachbarstufe)",
    "kein_handel": "kein Umsatz, Kurs des Vortags fortgeschrieben",
    "dividendenbereinigung": "Vergleichskurs = dividendenbereinigter Yahoo-Kurs",
    "split": "Faktor eines Splits",
    "abweichung_vom_nocp": "Befund: Stand ≠ offizieller Schlusskurs (NOCP), Nasdaq-Historie = NOCP – wodurch, ist nicht belegt",
    "ungeklaert": "ohne Beleg",
}
SHORT_CAUSE = {  # Kurzform in den Zeilen je Aktie (Langform in der Legende des Ergebnisses)
    "stand_ist_nocp": "Stand = NOCP",
    "letzter_abschluss": "Stand = letzter Abschluss",
    "nasdaq_letzter_abschluss": "Nasdaq = letzter Abschluss",
    "rundung": "Kursstufe",
    "kein_handel": "ohne Umsatz",
    "dividendenbereinigung": "Dividendenbereinigung",
    "split": "Split",
    "abweichung_vom_nocp": "Stand ≠ NOCP (Befund)",
    "ungeklaert": "ungeklärt",
    "offizieller_schlusskurs": "Nasdaq = NOCP",  # Läufe bis 1.18.2 (dort als Ursache gezählt)
}
# Warum für einen ungeklärten Tag kein Beleg möglich war – das ist die Grenze der Prüfung, keine Ursache der Abweichung
UNEXPLAINED_TEXT = {
    "nyse_gruppe_ohne_offiziellen_kurs": "Prüfgrenze: Heimatbörse der NYSE-Gruppe oder Cboe – offizieller Schlusskurs in den geprüften Quellen nicht frei verfügbar (NYSE: nur im kostenpflichtigen Produkt „TAQ NYSE Closing Prices“)",
    "nocp_fehlt_am_tag": "Prüfgrenze: Nasdaq-notiert – NOCP für den Tag fehlt",
    "nocp_dritter_wert": "Befund ohne Ursache: Nasdaq-notiert – Stand, Nasdaq-Historie und NOCP drei verschiedene Kurse",
    "nocp_anders": "Befund ohne Ursache: Nasdaq-Historie = NOCP, Stand nicht – Kurs des Stands nicht als letzter Abschluss vor 16:00 Uhr gefunden",
    "boerse_unbekannt": "Prüfgrenze: Heimatbörse unbekannt (Yahoo ohne Angabe)",
}
CATEGORY_TEXT = {  # die fünf Ergebnisarten (Auftrag 25.10.2026, Punkt 3) – Tage
    "uebereinstimmung": "bestätigte Übereinstimmung",
    "abweichung": "festgestellte Abweichung",
    "belegt": "davon Ursache belegt",
    "stand_ist_nocp": "davon Stand = offizieller Schlusskurs (Abweichung nur der Vergleichsquelle)",
    "ungeklaert": "davon Ursache ungeklärt",
    "ohne_vergleich": "fehlende Vergleichsmöglichkeit",
}
# Lage der Nasdaq-Historie an einem Tag mit NOCP ≠ Stand: gleich dem NOCP (Yahoo führt nicht den offiziellen Schlusskurs),
# gleich dem Stand (beide führen denselben anderen Schlusskurs als den offiziellen) oder ein dritter Kurs
NOCP_NOTE = {
    "nasdaq_gleich_nocp": "Nasdaq-Historie = NOCP",
    "nasdaq_gleich_stand": "Nasdaq-Historie = Stand, NOCP anders",
    "drei_kurse": "Stand, Nasdaq-Historie und NOCP verschieden",
    "nasdaq_ohne_tag": "Nasdaq-Historie ohne den Tag",
    "nasdaq_anders": "Nasdaq-Historie ein dritter Kurs",  # Läufe bis 25.10.2026, 00:30 Uhr (nicht weiter unterschieden)
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
    """Einordnung eines abweichenden Tags (Name, kurze Begründung ohne Kurse). Belegt ist eine Ursache nur, wenn gezeigt ist,
    wodurch der Unterschied entsteht: Faktor eines Splits, Kursstufe, letzter Abschluss vor 16:00 Uhr (Minutenkurse), kein
    Umsatz mit dem Kurs des Vortags, Dividendenbereinigung. Stand = offizieller Schlusskurs (NOCP) ist eine bestätigte
    Übereinstimmung (abweichend ist dann nur die Nasdaq-Historie). Nasdaq-Historie = NOCP und Stand nicht ist ein **Befund**
    („abweichung_vom_nocp“), keine Ursache; ohne jeden Beleg „ungeklaert“ – auch wenn der Kurs des Stands der Yahoo-Kurs ist."""
    n = nasdaq.get(day) or {}
    y = (yahoo.get("days") or {}).get(day) or {}
    n_close = n.get("close")
    if kind == "faktor":
        return "split", "konstanter Faktor"
    if nocp is not None and day in nocp and same(own, nocp[day]) and not same(n_close, nocp[day]):
        return "stand_ist_nocp", "Stand = NOCP, Nasdaq-Historie ≠ NOCP"
    if n_close is not None and within_display(own, n_close):
        return "rundung", "Stand zwischen zwei Kursstufen, Nasdaq zeigt die Nachbarstufe"
    # Ist die Nasdaq-Historie an dem Tag der offizielle Schlusskurs, erklärt „Nasdaq = letzter Abschluss“ nichts: dann ist der
    # letzte Abschluss zugleich der offizielle Schlusskurs, und offen ist, warum der Stand davon abweicht (Lauf 40158331688)
    nasdaq_is_official = nocp is not None and day in nocp and same(n_close, nocp[day])
    if day in minutes:
        if same(own, minutes[day]) and not same(n_close, minutes[day]):
            return "letzter_abschluss", "Stand = letzter Minutenkurs vor 16:00, Nasdaq anders"
        if same(n_close, minutes[day]) and not same(own, minutes[day]) and not nasdaq_is_official:
            return "nasdaq_letzter_abschluss", "Nasdaq = letzter Minutenkurs vor 16:00, Stand anders"
    volume_y, volume_n = y.get("volume"), n.get("volume")
    if previous_own is not None and own == previous_own and volume_y == 0:
        return "kein_handel", "Yahoo: Umsatz 0, Kurs des Vortags"
    if previous_nasdaq is not None and n_close == previous_nasdaq and volume_n == 0:
        return "kein_handel", "Nasdaq: Umsatz 0, Kurs des Vortags"
    if y.get("adjclose") is not None and same(n_close, y["adjclose"]) and not same(n_close, y.get("close")):
        return "dividendenbereinigung", "Nasdaq = adjclose"
    if nocp is not None and day in nocp and same(n_close, nocp[day]) and not same(own, nocp[day]):
        return "abweichung_vom_nocp", "Befund: Nasdaq = NOCP, Stand ≠ NOCP"
    return "ungeklaert", ""


def nocp_day_cause(day: int, own: float, nocp_close: float, minutes: dict[int, float]) -> str:
    """Belegte Ursache eines Tags mit Stand ≠ offizieller Schlusskurs (Variante b): Kursstufe oder Stand = letzter Abschluss
    vor 16:00 Uhr (die Schlussauktion fehlt im Kurs des Stands); sonst „ungeklaert“ (Befund ohne Ursache)."""
    if within_display(own, nocp_close):
        return "rundung"
    if day in minutes and same(own, minutes[day]) and not same(nocp_close, minutes[day]):
        return "letzter_abschluss"
    return "ungeklaert"


def unexplained_reason(exchange: str | None, nocp: dict[int, float] | None, day: int, cause: str = "ungeklaert") -> str:
    """Warum ein Tag ungeklärt bleibt – welche Quelle fehlt bzw. welcher Befund vorliegt."""
    if cause == "abweichung_vom_nocp":
        return "nocp_anders"
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
    us = us_stocks(instruments)
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


def nocp_note(own: float, nasdaq_close: float | None, nocp_close: float) -> str:
    """Lage der Nasdaq-Historie an einem Tag, an dem der Stand vom offiziellen Schlusskurs abweicht."""
    if nasdaq_close is None:
        return "nasdaq_ohne_tag"
    if same(nasdaq_close, nocp_close):
        return "nasdaq_gleich_nocp"
    if gegen.classify(own, nasdaq_close, []) == "gleich":
        return "nasdaq_gleich_stand"
    return "drei_kurse"


def us_stocks(instruments: dict) -> set[int]:
    """US-Aktien, die Nasdaq führen kann (NYSE-Kalender, nicht OTC, Kürzel ohne Punkt, mit Kursreihe)."""
    n = len(instruments["isin"])
    calendar = instruments.get("calendar") or [None] * n
    key = instruments.get("exchange_key") or [None] * n
    symbol = instruments.get("symbol") or [None] * n
    has_series = instruments.get("has_series") or [True] * n
    return {i for i in range(n) if calendar[i] == "XNYS" and key[i] != "OTC" and symbol[i] and "." not in str(symbol[i]) and has_series[i]}


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


NASDAQ_SYMBOL_VARIANTS = (".", "%2F", "%5E")  # Aktiengattung „BRK-B“ (Yahoo) bei Nasdaq als „BRK.B“, sonst „BRK/B“ oder „BRK^B“


def fetch_base(http, symbol: str, start_day: int, cutoff: int) -> dict:
    """Nasdaq-Historie, Yahoo-Tageskurse und – bei Heimatbörse Nasdaq – die NOCP-Historie einer Aktie. Antwortet Nasdaq für
    ein Kürzel mit Aktiengattung („-“) ohne Kurse, werden die übrigen Schreibweisen versucht (seit dem 25.10.2026)."""
    variants = [symbol.replace("-", sep) for sep in NASDAQ_SYMBOL_VARIANTS] if "-" in symbol else [symbol]
    out: dict = {"nasdaq_symbol": variants[0]}
    begin, finish = (EPOCH + dt.timedelta(days=start_day)).isoformat(), (EPOCH + dt.timedelta(days=cutoff + 1)).isoformat()
    for k, nasdaq_symbol in enumerate(variants):
        status, payload = get_json(http, gegen.NASDAQ.format(symbol=nasdaq_symbol, start=begin, end=finish), gegen.HEADERS)
        rows = parse_nasdaq_rows(payload) if status == "ok" else {}
        if k == 0:
            # erste Schreibweise: ihr Ergebnis gilt (Kurse, keine Kurse oder Netzfehler – dann Nachholrunde)
            out["nasdaq_status"], out["nasdaq"] = status, rows
            if rows or status != "ok":
                break
        elif rows:
            out.update(nasdaq_symbol=nasdaq_symbol, nasdaq=rows, nasdaq_variante=k)
            break
        else:
            # weitere Schreibweise ohne Kurse (auch HTTP 404): gezählt, ändert das Ergebnis „keine Kurse“ nicht
            out.setdefault("nasdaq_varianten_status", []).append(status)
    if not out["nasdaq"] and out["nasdaq_status"] != "ok":
        return out
    # Yahoo auch ohne Nasdaq-Kurse (seit dem 25.10.2026): Börse, Währung und Art der Yahoo-Kurse des Stands für die Zusatzquellen
    status, payload = get_json(http, YAHOO_DAILY.format(symbol=symbol, start=start_day * 86400, end=(cutoff + 2) * 86400), gegen.YAHOO_HEADERS)
    out["yahoo_status"] = status
    out["yahoo"] = parse_yahoo_daily(payload) if status == "ok" else {"days": {}, "splits": [], "dividends": []}
    out["nocp"], out["nocp_status"], out["nocp_fields"] = None, [], []
    if not out["nasdaq"]:
        return out
    if out["yahoo"].get("exchange") in NASDAQ_LISTED:
        for nocp_url in NOCP_URLS:
            status, payload = get_json(http, nocp_url.format(symbol=out["nasdaq_symbol"]), gegen.HEADERS)
            out["nocp_status"].append(status)
            rows, fields = parse_nocp(payload) if status == "ok" else ({}, [])
            if rows:
                out["nocp"], out["nocp_fields"] = rows, fields
                break
    return out


def base_failed(base: dict) -> str | None:
    """Fehlerstatus, wenn eine Quelle der Grundabfrage mit einem Netz- oder Serverfehler antwortete (Yahoo nur bei Aktien mit
    Nasdaq-Kursen – ohne sie ist Yahoo nur die Angabe der Börse für die Zusatzquellen)."""
    for name in ("nasdaq_status", "yahoo_status"):
        status = base.get(name)
        if name == "yahoo_status" and not base.get("nasdaq"):
            continue
        if status and transient(status):
            return f"{name.split('_')[0]}_{status}"
    statuses = base.get("nocp_status") or []
    if base.get("nocp") is None and statuses and any(transient(s) for s in statuses):
        return f"nocp_{next(s for s in statuses if transient(s))}"
    return None


def fetch_details(http, symbol: str, nasdaq_symbol: str, now: float, dividends: bool = True) -> dict:
    """Minutenkurse (1 Minute: 5 Sitzungen; 2 Minuten: 58 Tage) und Dividenden bei Nasdaq – nur für Aktien mit Abweichung
    (Dividenden nur bei Abweichung von der Nasdaq-Historie; seit dem 25.10.2026 Minutenkurse auch bei Stand ≠ NOCP allein)."""
    out: dict = {"status": {}}
    status, payload = get_json(http, YAHOO_MINUTES_2M.format(symbol=symbol, start=int(now) - MINUTES_2M_DAYS * 86400, end=int(now)), gegen.YAHOO_HEADERS)
    out["status"]["minuten_2m"] = status
    minutes = parse_yahoo_minutes(payload) if status == "ok" else {}
    status, payload = get_json(http, YAHOO_MINUTES.format(symbol=symbol), gegen.YAHOO_HEADERS)
    out["status"]["minuten"] = status
    minutes.update(parse_yahoo_minutes(payload) if status == "ok" else {})  # 1 Minute hat Vorrang
    out["minutes"] = minutes
    out["dividends"] = []
    if dividends:
        status, payload = get_json(http, NASDAQ_DIVIDENDS.format(symbol=nasdaq_symbol), gegen.HEADERS)
        out["status"]["dividenden"] = status
        out["dividends"] = parse_nasdaq_dividends(payload) if status == "ok" else []
    return out


def own_series(stand: nachrechnen.Stand, instruments: dict, i: int, start_day: int, cutoff: int) -> dict[int, float]:
    """Schlusskurse des Stands im Zeitraum der Prüfung (gültig, > 0) – dieselbe Auswahl im Prüfjob und in der gemeinsamen
    Rechnung."""
    name = f"series/{instruments['isin'][i]}.bin"
    if not stand.exists(name):
        return {}
    series = stand.get(name)
    stand.drop(name)
    d = [int(x) for x in series.get("d") or []]
    c = [None if x is None else float(x) for x in series.get("c") or []]
    return {day: close for day, close in zip(d, c) if close is not None and close > 0 and start_day <= day <= cutoff}


def substitution(own: dict[int, float], replaced: dict[int, float]) -> tuple[np.ndarray, np.ndarray, set[int]]:
    """Kursreihe mit ersetzten Tagen für die Neuberechnung: (Tage, Kurse, ersetzte Tage)."""
    changed = dict(own)
    changed.update(replaced)
    days = np.array(sorted(changed), dtype=np.int64)
    return days, np.array([changed[x] for x in days.tolist()], dtype=np.float64), set(replaced)


def field_names(checks: list[dict]) -> list[str]:
    """Feldnamen der Antworten je Quelle (Kurshistorie und Kursmeldung), vereinigt über alle Aktien – nur Namen, keine Werte."""
    history: dict[str, set[str]] = {}
    quote: dict[str, set[str]] = {}
    for c in checks:
        history.setdefault(c["quelle"], set()).update(c.get("felder") or [])
        quote.setdefault(c["quelle"], set()).update(c.get("felder_kurs") or [])
    out = [f"{q}: {', '.join(sorted(f))}" for q, f in sorted(history.items()) if f]
    return out + [f"{q} (Kursmeldung): {', '.join(sorted(f))}" for q, f in sorted(quote.items()) if f]


def stand_meta(instruments: dict, i: int) -> dict:
    """ISIN, Namen und Währung einer Aktie im Stand – nur für die Prüfung der Identität, nie im Protokoll."""
    def column(name: str):
        values = instruments.get(name) or []
        return values[i] if i < len(values) else None

    aliases = column("aliases") or []
    names = [column("name"), column("tr_name")] + (list(aliases) if isinstance(aliases, (list, tuple)) else [aliases])
    return {"isin": str(instruments["isin"][i]), "namen": [str(n) for n in names if n], "waehrung": column("currency") or ""}


def alternative_comparison(http, symbol: str, own: dict[int, float], meta: dict, yahoo: dict, start_day: int, cutoff: int) -> dict:
    """Weitere Quellen für eine Aktie ohne Nasdaq-Kurse: alle Quellen abfragen und prüfen (Identität, Handelsplatz, Währung,
    Handelsdatum, Bereinigung, Kursniveau); verglichen wird mit der ersten Quelle, die alle Prüfungen besteht. Weitere
    bestandene Quellen dienen als zweite Quelle an den abweichenden Tagen, ebenso der letzte Abschluss bei OTC Markets
    (Betreiber des OTC-Handels) für seinen Tag. Rückgabe ohne Kürzel und Namen."""
    checks, passed, fetched_by = [], [], {}
    for source in zusatz.SOURCES:
        fetched = zusatz.fetch_source(http, source, symbol, start_day, cutoff)
        fetched_by[source] = fetched
        result = zusatz.check(fetched, own, meta, yahoo)
        result["status"] = dict(fetched["status"])
        result["felder"] = list(fetched.get("felder") or [])
        result["felder_kurs"] = list(fetched.get("felder_kurs") or [])
        checks.append(result)
        if result["vergleichbar"]:
            passed.append((source, fetched, result))
    out = {"checks": checks, "quelle": None, "rows": {}, "tage": {}, "zweite": {}, "pruefung": {}, "otc_letzter": None}
    # letzter Abschluss bei OTC Markets (nur mit bestätigter Identität über den Namen im Profil): Vergleich am selben Tag
    otc = fetched_by.get("otc_markets") or {}
    otc_identity = zusatz.identity(otc.get("meta") or {}, meta.get("isin", ""), meta.get("namen") or []) if (otc.get("meta") or {}).get("name") else "nur_kuerzel"
    last = otc.get("letzter")
    if last and otc_identity not in ("isin_anders", "cusip_anders", "name_passt_nicht"):
        day, value = last
        # Lauf 40160248028: bei 25 von 38 Aktien lag der Tag nicht im Stand – seitdem mit seiner Lage (nur als Zählwert)
        out["otc_letzter"] = ("gleich" if same(own[day], value) else "abweichend") if day in own else "tag_nicht_im_stand_" + zusatz.day_position(day, start_day, cutoff)
    elif last:
        out["otc_letzter"] = "identitaet_nicht_bestaetigt"
    elif (otc.get("status") or {}).get("kurs") == "ok":
        out["otc_letzter"] = "kursmeldung_ohne_abschluss"  # kein lastSale > 0 oder kein lesbarer lastTradeTime
    elif otc:
        out["otc_letzter"] = "ohne_kursmeldung"
    if not passed:
        return out
    source, fetched, result = passed[0]
    days = zusatz.compare(own, fetched["rows"], result["datum_versatz"], yahoo, within_display)
    second: dict[int, str] = {}
    for d, (kind, alt_close, _) in days.items():
        if kind == "gleich":
            continue
        for _, other, other_result in passed[1:]:
            value = (other["rows"].get(d + other_result["datum_versatz"]) or {}).get("close")
            if value is None:
                continue
            second[d] = "gleich_stand" if same(own[d], value) else ("gleich_erster_quelle" if same(alt_close, value) else "dritter_kurs")
            break
        if d not in second and out["otc_letzter"] in ("gleich", "abweichend") and last and last[0] == d:
            value = last[1]
            second[d] = "otc_letzter_gleich_stand" if same(own[d], value) else ("otc_letzter_gleich_erster_quelle" if same(alt_close, value) else "otc_letzter_dritter_kurs")
    out.update(quelle=source, rows={d: fetched["rows"][d + result["datum_versatz"]] for d in own if (d + result["datum_versatz"]) in fetched["rows"]}, tage=days, zweite=second, pruefung=result)
    return out


def run(stand: nachrechnen.Stand, sid: str, http, pause=time.sleep, now: float | None = None, budget_s: float = FETCH_BUDGET_S, clock=time.monotonic, auswahl: str = "alle", zusatzquellen: bool = True) -> dict:
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
        if base.get("nasdaq_variante"):
            sources["nasdaq_ok_mit_anderer_schreibweise_der_gattung"] += 1
        for status in base.get("nasdaq_varianten_status") or []:
            sources[f"nasdaq_andere_schreibweise_{status}"] += 1
        if base["nasdaq"]:
            sources[f"yahoo_{base['yahoo_status']}"] += 1
        elif base.get("yahoo_status"):
            sources[f"yahoo_ohne_nasdaq_{base['yahoo_status']}"] += 1

    days_total: Counter = Counter()
    kinds: Counter = Counter()
    causes: Counter = Counter()
    unexplained: Counter = Counter()
    patterns: Counter = Counter()
    volumes: Counter = Counter()
    nocp_probe: Counter = Counter()
    nocp_compare: Counter = Counter()
    nocp_causes: Counter = Counter()  # (b) Tage mit Stand ≠ NOCP: belegte Ursache bzw. Befund
    events: Counter = Counter()
    only: Counter = Counter()
    detail_status: Counter = Counter()
    nocp_fields: set[str] = set()
    stocks: list[dict] = []
    alt_stocks: list[dict] = []  # mit einer Zusatzquelle verglichene Aktien mit Abweichung
    substituted: dict[int, tuple[np.ndarray, np.ndarray, set[int]]] = {}
    substituted_nocp: dict[int, tuple[np.ndarray, np.ndarray, set[int]]] = {}
    substituted_alt: dict[int, tuple[np.ndarray, np.ndarray, set[int]]] = {}
    compared: set[int] = set()  # mit Nasdaq verglichen
    alt_compared: dict[int, str] = {}  # mit einer Zusatzquelle verglichen (Aktie → Quelle)
    alt_checks: list[dict] = []  # Prüfungen je Quelle vor dem Vergleich (ohne Namen und Kurse)
    alt_days: Counter = Counter()  # Tage der Zusatzquellen: gleich, abweichend, Ursachen, zweite Quelle
    alt_patterns: Counter = Counter()  # Muster der ungeklärten Tage gegen Zusatzquellen (ohne Kurse)
    no_price_exchange: Counter = Counter()  # Börse der Yahoo-Kurse der Aktien, für die Nasdaq keine Kurse führt
    info: dict[int, dict] = {}  # Börse, Kursbereich, abweichende Tage – für die Legende der Buchstaben
    nocp_only: list[dict] = []  # Aktien unter den ersten 10, bei denen nur der offizielle Schlusskurs vom Stand abweicht
    no_prices: dict[int, str] = {}  # beantwortet, aber ohne Vergleichskurse – zählt nicht als geprüft
    no_price_symbols: Counter = Counter()  # Länge des Kürzels der Aktien, für die Nasdaq keine Kurse führt (ohne Namen)
    nocp_state: dict[int, str] = {}  # verglichene Aktien: mit NOCP, Nasdaq-notiert ohne NOCP, nicht Nasdaq-notiert (Prüfgrenze)
    days_a: dict[int, dict[int, tuple[float, str]]] = {}  # (a) ersetzte Tage: Abweichung des Stands in %, Ursache
    days_b: dict[int, dict[int, tuple[float, str]]] = {}  # (b) Tage mit NOCP ≠ Stand: Abweichung in %, Ursache bzw. Lage der Nasdaq-Historie
    days_c: dict[int, dict[int, tuple[float, str]]] = {}  # (c) Tage mit Zusatzquelle ≠ Stand: Abweichung in %, Ursache
    repl: dict[str, dict[int, dict[int, float]]] = {"a": {}, "b": {}, "c": {}}  # Ersatzkurse je Variante (für die gemeinsame Rechnung)
    days_without_nocp = 0  # verglichene Tage ohne offiziellen Schlusskurs (Prüfgrenze)
    for i in chosen:
        base = bases.get(i)
        if base is None:
            continue
        symbol = str(instruments["symbol"][i])
        if not base["nasdaq"]:
            no_price_symbols[f"{len(symbol)} Zeichen"] += 1
            yahoo = base.get("yahoo") or {"days": {}}
            no_price_exchange[yahoo.get("exchange") or "ohne_angabe"] += 1
            own = own_series(stand, instruments, i, start_day, cutoff)
            if not own:
                no_prices[i] = "stand_ohne_kurse_im_zeitraum"
                continue
            if not zusatzquellen:
                no_prices[i] = "nasdaq_ohne_kurse"
                continue
            alt = alternative_comparison(http, symbol, own, stand_meta(instruments, i), yahoo, start_day, cutoff)
            alt_checks += alt["checks"]
            alt_days[f"otc_letzter_abschluss_{alt['otc_letzter'] or 'ohne'}"] += 1
            if alt["quelle"] is None:
                no_prices[i] = "nasdaq_ohne_kurse"
                continue
            alt_compared[i] = alt["quelle"]
            rows = alt["rows"]
            info[i] = {"boerse": "OTC" if zusatz.stand_venue(yahoo.get("exchange")) == "otc" else "andere", "kursbereich": price_range(rows), "quelle": alt["quelle"]}
            deviating_c = {d: v for d, v in alt["tage"].items() if v[0] != "gleich"}
            alt_days["gleich"] += len(alt["tage"]) - len(deviating_c)
            alt_days["nur_im_stand"] += alt["pruefung"].get("nur_im_stand", 0)
            alt_days["nur_im_stand_ohne_umsatz"] += alt["pruefung"].get("nur_im_stand_ohne_umsatz", 0)
            per_stock = Counter()
            unit = zusatz.source_unit(r["close"] for r in rows.values())
            for d, (kind, alt_close, cause) in deviating_c.items():
                alt_days["abweichend"] += 1
                alt_days[f"ursache_{cause}"] += 1
                if cause not in EVIDENCE:
                    for name in zusatz.pattern(own[d], alt_close, (yahoo["days"].get(d) or {}).get("volume"), (rows.get(d) or {}).get("volume"), unit):
                        alt_patterns[name] += 1
                alt_days[f"zweite_quelle_{alt['zweite'].get(d, 'keine')}"] += 1
                per_stock[cause] += 1
                days_c.setdefault(i, {})[d] = (round(100 * (own[d] / alt_close - 1), 3), cause)
                repl["c"].setdefault(i, {})[d] = alt_close
            info[i].update(abweichend=len(deviating_c), nocp_ungleich=0)
            if deviating_c:
                substituted_alt[i] = substitution(own, repl["c"][i])
                alt_stocks.append({
                    "idx": i, "top10": int(top10.get(i, 0)), "platz1": int(first.get(i, 0)), "kursbereich": info[i]["kursbereich"], "boerse": info[i]["boerse"],
                    "quelle": alt["quelle"], "abweichend": len(deviating_c),
                    "groesste_abweichung_pct": round(100 * max(abs(own[d] / v[1] - 1) for d, v in deviating_c.items()), 2), "ursachen": dict(per_stock),
                })
            continue
        nasdaq, yahoo, nocp = base["nasdaq"], base["yahoo"], base["nocp"]
        exchange = yahoo.get("exchange") or "–"
        group = "nasdaq" if exchange in NASDAQ_LISTED else ("nyse_gruppe" if exchange in NYSE_GROUP else "unbekannt")
        for status in base.get("nocp_status") or []:
            nocp_probe[status] += 1
        if nocp is not None:
            nocp_probe["mit_kursen"] += 1
            nocp_fields.update(base["nocp_fields"])
        own = own_series(stand, instruments, i, start_day, cutoff)
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
        notes: dict[int, tuple[float, str]] = {}
        days_without_nocp += sum(1 for day in own if nocp is None or day not in nocp)
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
                    notes[day] = (round(100 * (close / nocp[day] - 1), 3), nocp_note(close, nasdaq[day]["close"] if day in nasdaq else None, nocp[day]))
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
            repl["b"][i] = dict(nocp_wrong)
            substituted_nocp[i] = substitution(own, nocp_wrong)
        info[i].update(abweichend=len(deviating), nocp_ungleich=len(nocp_wrong))
        if not deviating and not nocp_wrong:
            continue
        if clock() - started > budget_s + DETAIL_EXTRA_S:
            # Zeitbudget auch für Minutenkurse und Dividenden erschöpft: Ursachen dieser Aktie nur mit NOCP und Tageskursen
            details = {"status": {"minuten": "zeitbudget", "minuten_2m": "zeitbudget", **({"dividenden": "zeitbudget"} if deviating else {})}, "minutes": {}, "dividends": []}
        else:
            # Dividenden bei Nasdaq nur bei Abweichung von der Nasdaq-Historie (Kontingent der Anfragen je Rechner)
            details = fetch_details(http, symbol, base["nasdaq_symbol"], now, dividends=bool(deviating))
        for name, status in details["status"].items():
            detail_status[f"{name}_{status}"] += 1
        minutes, nasdaq_dividends = details["minutes"], details["dividends"]
        # (b) jeder Tag mit Stand ≠ NOCP: belegte Ursache (Kursstufe, letzter Abschluss) oder Befund (Lage der Nasdaq-Historie)
        for day, (pct, note) in notes.items():
            cause_b = nocp_day_cause(day, own[day], nocp_wrong[day], minutes)
            nocp_causes[cause_b if cause_b in EVIDENCE else f"befund_{note}"] += 1
            days_b.setdefault(i, {})[day] = (pct, cause_b if cause_b in EVIDENCE else note)
        if not deviating:
            if top10.get(i):
                nocp_only.append(
                    {
                        "idx": i,
                        "top10": int(top10.get(i, 0)),
                        "platz1": int(first.get(i, 0)),
                        "kursbereich": info[i]["kursbereich"],
                        "boerse": info[i]["boerse"],
                        "nocp_tage_ungleich": len(nocp_wrong),
                        "nocp_belegt": sum(1 for day in nocp_wrong if days_b[i][day][1] in EVIDENCE),
                        "groesste_abweichung_nocp_pct": round(100 * max(abs(own[day] / nocp_wrong[day] - 1) for day in nocp_wrong), 2),
                    }
                )
            continue
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
            if cause in OPEN:
                n_close = nasdaq[day]["close"]
                unexplained[unexplained_reason(yahoo.get("exchange"), nocp, day, cause)] += 1
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
                "dividenden_nasdaq": details["status"].get("dividenden", "–"),
            }
        )
        # Variante (a): an den abweichenden Tagen der Nasdaq-Kurs, sonst der Kurs des Stands
        repl["a"][i] = {day: nasdaq[day]["close"] for day, _ in deviating}
        substituted[i] = substitution(own, repl["a"][i])
    track = set(top10)  # Wirkung je Aktie: alle US-Aktien unter den ersten 10, in allen Varianten
    effects = ranking_effects(stand, {"a": substituted, "b": substituted_nocp, "c": substituted_alt}, liquid, min_trend, track)
    effect, moves_a, changes_a = effects["a"]
    effect_nocp, moves_b, changes_b = effects["b"]
    effect_alt, moves_c, changes_c = effects["c"]
    ordered = (
        sorted(stocks, key=lambda s: (-s["top10"], -s["abweichend"]))
        + sorted(nocp_only, key=lambda s: (-s["top10"], -s["nocp_tage_ungleich"]))
        + sorted(alt_stocks, key=lambda s: (-s["top10"], -s["abweichend"]))
    )
    other_set = set(other_job)
    us_set = us_stocks(instruments)

    def state_of(i: int) -> str:
        if i in info:
            return "verglichen"
        if i in failures:
            return "ohne_antwort"
        if i in no_prices:
            return "ohne_vergleichskurse"
        if i in other_set:
            return "anderer_job"
        return "keine_us_aktie" if i not in us_set else "nicht_ausgewaehlt"

    names = Lettering([s["idx"] for s in ordered], state_of, info, top10)
    changes_a, changes_b, changes_c = names.changes(changes_a, days_a), names.changes(changes_b, days_b), names.changes(changes_c, days_c)
    by_idx = {s["idx"]: s for s in stocks}
    nocp_only_idx = {s["idx"] for s in nocp_only}
    alt_idx = {s["idx"]: s for s in alt_stocks}
    coverage = Counter()
    for i in top10:
        coverage["us_aktien_unter_ersten_10"] += 1
        if i in other_set:
            coverage["im_anderen_job"] += 1
        elif i in failures:
            coverage["abruf_fehlgeschlagen"] += 1
        elif i in alt_compared:
            coverage["verglichen_zusatzquelle"] += 1
            s = alt_idx.get(i)
            coverage["zusatzquelle_ohne_abweichung" if s is None else ("zusatzquelle_mit_ungeklaerten_tagen" if s["ursachen"].get("ungeklaert") else "zusatzquelle_alle_belegt")] += 1
        elif i not in compared:
            coverage["ohne_nasdaq_kurse"] += 1
        else:
            coverage["verglichen"] += 1
            s = by_idx.get(i)
            if s is None:
                coverage["ohne_abweichung"] += 1
                coverage["davon_nur_nocp_abweichend"] += i in nocp_only_idx
            elif any(s["ursachen"].get(k) for k in OPEN):
                coverage["mit_ungeklaerten_tagen"] += 1
            else:
                coverage["alle_abweichungen_belegt"] += 1
    for s in stocks + nocp_only + alt_stocks:
        s["aktie"] = names(s["idx"])
        s["rangwirkung"] = moves_a.get(s["idx"], {})
        s["rangwirkung_nocp"] = moves_b.get(s["idx"], {})
        if s["idx"] in alt_compared:
            s["rangwirkung_zusatz"] = moves_c.get(s["idx"], {})
        del s["idx"]
    # Zuordnung jedes Buchstabens zu genau einer Aktie: ihr bester Platz in einer Rangliste dieses Stands (in der App mit
    # der Passphrase nachzusehen) – eindeutig, ohne Namen im öffentlichen Protokoll
    mapping = names.mapping(stand)
    by_group_coverage = {g: Counter() for g in SHARDS[auswahl]}
    for i in chosen:
        g = group_of[i]
        if i in failures:
            by_group_coverage[g]["abruf_fehlgeschlagen"] += 1
        elif i in compared:
            by_group_coverage[g]["verglichen"] += 1
            by_group_coverage[g]["verglichen_nasdaq"] += 1
            by_group_coverage[g][f"nocp_{nocp_state[i]}"] += 1
        elif i in alt_compared:
            by_group_coverage[g]["verglichen"] += 1
            by_group_coverage[g][f"verglichen_{alt_compared[i]}"] += 1
        else:
            by_group_coverage[g]["keine_vergleichskurse"] += 1
            by_group_coverage[g][f"keine_vergleichskurse_{no_prices.get(i, 'unbekannt')}"] += 1
    intervals = getattr(http, "min_interval", None)
    open_a = sum(causes.get(k, 0) for k in OPEN)
    categories = {
        "nasdaq_historie": {
            "uebereinstimmung": days_total.get("verglichen", 0) - days_total.get("abweichend", 0),
            "abweichung": days_total.get("abweichend", 0),
            "belegt": sum(causes.get(k, 0) for k in EVIDENCE),
            "stand_ist_nocp": sum(causes.get(k, 0) for k in MATCH_OFFICIAL),
            "ungeklaert": open_a,
            "ohne_vergleich_aktien": len(no_prices) + len(alt_compared),
            "ohne_vergleich_tage": only.get("nur_im_stand", 0),
        },
        "offizieller_schlusskurs": {
            "uebereinstimmung": nocp_compare.get("stand_gleich", 0),
            "abweichung": nocp_compare.get("stand_ungleich", 0),
            "belegt": sum(v for k, v in nocp_causes.items() if k in EVIDENCE),
            "ungeklaert": sum(v for k, v in nocp_causes.items() if k not in EVIDENCE),
            "faktor_split": nocp_compare.get("faktor_split", 0),
            "ohne_vergleich_aktien": sum(1 for i in compared if nocp_state.get(i) != "mit_nocp") + len(no_prices) + len(alt_compared),
            "ohne_vergleich_tage": days_without_nocp,
        },
        "zusatzquellen": {
            "uebereinstimmung": alt_days.get("gleich", 0),
            "abweichung": alt_days.get("abweichend", 0),
            "belegt": sum(v for k, v in alt_days.items() if k.startswith("ursache_") and k[len("ursache_"):] in EVIDENCE),
            "ungeklaert": alt_days.get("ursache_ungeklaert", 0),
            "ohne_vergleich_aktien": len(no_prices),
            "ohne_vergleich_tage": alt_days.get("nur_im_stand", 0),
        },
    }
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
        "ohne_vergleichskurse_kuerzel": dict(no_price_symbols),
        "ohne_nasdaq_boerse": dict(no_price_exchange),
        "sperrpausen": block_pauses,
        "nasdaq_anfragen": nasdaq_requests(http),
        "nasdaq_anfragen_bis_zur_ersten_sperre": first_block,
        "nasdaq_abstand_s": intervals.get(NASDAQ_HOST) if isinstance(intervals, dict) else None,
        "nocp_abruf": dict(nocp_probe),
        "nocp_felder": sorted(nocp_fields),
        "nocp_vergleich": dict(nocp_compare),
        "nocp_ursachen": dict(nocp_causes),
        "detailabruf": dict(detail_status),
        "tage": dict(days_total),
        "arten": dict(kinds),
        "nur_eine_quelle": dict(only),
        "umsatz_vergleich": dict(volumes),
        "ursachen": dict(causes),
        "ungeklaert_gruende": dict(unexplained),
        "ungeklaert_muster": dict(patterns),
        "kategorien": categories,
        "zusatzquellen": {
            "aktien_ohne_nasdaq": sum(no_price_symbols.values()),
            "verglichen": len(alt_compared),
            "je_quelle": dict(Counter(alt_compared.values())),
            "pruefungen": dict(zusatz.summary_counts(alt_checks)),
            "felder": field_names(alt_checks),
            "tage": dict(alt_days),
            "muster": dict(alt_patterns),
        },
        "aktien_mit_abweichung": len(stocks),
        "aktien_mit_ereignis_im_zeitraum": dict(events),
        "top10_abdeckung": dict(coverage),
        "aktien": sorted(stocks, key=lambda s: (len(s["aktie"]), s["aktie"])),
        "aktien_nur_nocp": sorted(nocp_only, key=lambda s: (len(s["aktie"]), s["aktie"])),
        "aktien_zusatzquelle": sorted(alt_stocks, key=lambda s: (len(s["aktie"]), s["aktie"])),
        "ranglisten": effect,
        "ranglisten_offizieller_schlusskurs": effect_nocp,
        "ranglisten_zusatzquellen": effect_alt,
        "aenderungen_nasdaq": changes_a,
        "aenderungen_offizieller_schlusskurs": changes_b,
        "aenderungen_zusatzquellen": changes_c,
        "weitere_buchstaben": names.legend,
        "zuordnung": mapping,
    }
    report["urteil"] = verdict(report)
    # Übergabe an den Job „gemeinsame Wirkung“ (verschlüsselt mit dem Schlüssel des Stands, nie im Protokoll): Gruppen,
    # Abdeckung, Ersatzkurse je Variante mit Abweichung und Ursache – die Kurse des Stands liest der Job selbst
    report["uebergabe"] = transfer_payload(sid, auswahl, report, {i: group_of[i] for i in chosen}, compared, alt_compared, no_prices, failures, repl, {"a": days_a, "b": days_b, "c": days_c}, info)
    return report


def verdict(report: dict) -> str:
    """„unvollstaendig“ (eine Aktie blieb ohne Antwort oder ohne Vergleichskurse – fehlende Daten zählen nicht als geprüft),
    „ungeklaert“ (mindestens ein abweichender Tag ohne Beleg), „belegt“ (jede Abweichung belegt) oder „keine_abweichungen“."""
    if report.get("abruf_fehlgeschlagen") or report.get("ohne_vergleichskurse"):
        return "unvollstaendig"
    c = report.get("ursachen") or {}
    if any(c.get(k) for k in OPEN) or ((report.get("kategorien") or {}).get("zusatzquellen") or {}).get("ungeklaert"):
        return "ungeklaert"
    return "belegt" if (report.get("tage") or {}).get("abweichend") else "keine_abweichungen"


def leader_change(members: np.ndarray, w: str, order: list[int], new_leader: int, candidates: list[int], base: tuple, new: tuple, start_of: dict[int, int]) -> dict:
    """Einzelheiten eines neuen Platzes 1: Rendite und R² des bisherigen und des neuen Spitzenreiters vorher/nachher, sein
    bisheriger Platz, und welche ersetzten Kurse den Wechsel auslösen – geprüft, indem die Rangliste nur mit den Kursen
    einzelner Aktien neu gerechnet wird. Gesucht wird die kleinste Menge: zuerst jede Aktie allein (bisheriger und neuer
    Spitzenreiter zuerst, dann die übrigen nach der Größe ihrer Änderung); reicht keine allein, werden Aktien der Reihe nach
    hinzugenommen, bis Platz 1 wechselt wie mit allen, und danach jede wieder weggelassen, die nicht nötig ist (seit dem
    25.10.2026 – vorher standen auch Aktien unter den Auslösern, die die Suche nur unterwegs hinzugenommen hatte). Dazu: ob
    Platz 1 mit allen übrigen ersetzten Kursen, aber ohne die Auslöser ebenfalls wechselt (gemeinsame Wirkung)."""
    status, r_of, r2_of = base
    status_new, r_new, r2_new = new
    old_leader = order[0]

    def leader_with(subset: list[int]) -> int | None:
        st, r, r2 = status.copy(), dict(r_of), dict(r2_of)
        for j in subset:
            st[j], r[j], r2[j] = status_new[j], r_new[j], r2_new[j]
        ranked = lists_of(nachrechnen.rank_group(members, st, r, r2))[w]
        return int(ranked[0]) if len(ranked) else None

    def size(j: int) -> float:
        change_r2 = abs(float(r2_new[j]) - float(r2_of[j])) if r2_new.get(j) is not None and r2_of.get(j) is not None else 0.0
        return abs(r_new[j] - r_of[j]) + change_r2

    own = [j for j in (old_leader, new_leader) if j in candidates]
    pool = own + sorted((j for j in candidates if j not in (old_leader, new_leader)), key=lambda j: (-size(j), j))[:MAX_TRIGGER_SEARCH]
    alone = [j for j in pool if leader_with([j]) == new_leader]
    needed: list[int] | None = None
    if alone:
        needed = list(alone)  # jede dieser Aktien reicht allein
    else:
        subset: list[int] = []
        for j in pool:
            subset.append(j)
            if leader_with(subset) == new_leader:
                needed = list(subset)
                break
        if needed:
            for j in list(reversed(needed)):  # nicht nötige Aktien wieder weglassen
                trial = [x for x in needed if x != j]
                if trial and leader_with(trial) == new_leader:
                    needed = trial
    # gemeinsame Wirkung: Platz 1 mit allen übrigen ersetzten Kursen, aber ohne die Auslöser – bleibt der bisherige
    # Spitzenreiter, sind die Auslöser nötig; wechselt Platz 1 trotzdem, genügen auch andere Aktien
    without = leader_with([j for j in candidates if j not in (needed or [])]) if needed else None
    involved = {old_leader, new_leader, *(needed or []), *([without] if without is not None else [])}
    # Wodurch der Wechsel entsteht (seit dem 25.10.2026, Auftrag Punkt 4): Score wie in der App aus den Perzentilen von
    # Rendite und R² in der Vergleichsmenge – ein Auslöser, der weder bisheriger noch neuer Spitzenreiter ist, ändert deren
    # Score nur über seine Lage zu ihren Werten (über beiden, zwischen ihnen, unter beiden) oder über die Vergleichsmenge
    full_before = nachrechnen.rank_group(members, status, r_of, r2_of)
    full_after = nachrechnen.rank_group(members, status_new, r_new, r2_new)
    leaders = (old_leader, new_leader)
    trigger_values = {}
    for j in needed or []:
        trigger_values[j] = {
            "rendite": (r_of.get(j), r_new.get(j)),
            "r2": (r2_of.get(j), r2_new.get(j)),
            "in_vergleichsmenge": (int(status[j]) == nachrechnen.U_STATUS, int(status_new[j]) == nachrechnen.U_STATUS),
            "lage_rendite": (side(r_of.get(j), [r_of.get(x) for x in leaders]), side(r_new.get(j), [r_new.get(x) for x in leaders])),
            "lage_r2": (side(r2_of.get(j), [r2_of.get(x) for x in leaders]), side(r2_new.get(j), [r2_new.get(x) for x in leaders])),
        }
    return {
        "platz_des_neuen_vorher": order.index(new_leader) + 1 if new_leader in order else None,
        "rendite": {j: (r_of.get(j), r_new.get(j)) for j in leaders},
        "r2": {j: (r2_of.get(j), r2_new.get(j)) for j in leaders},
        "score": {j: (app_score(full_before, int(w), j), app_score(full_after, int(w), j)) for j in leaders},
        "vergleichsmenge": (comparison_size(full_before, int(w)), comparison_size(full_after, int(w))),
        "ausloeser": needed,
        "ausloeser_werte": trigger_values,
        "allein": alone,
        "ohne_ausloeser": without,
        "ersetzte_im_zeitraum": len(candidates),
        "start": {j: start_of[j] for j in involved if j in start_of},
    }


def side(value: float | None, leaders: list[float | None]) -> str | None:
    """Lage eines Werts gegenüber den Werten des bisherigen und des neuen Spitzenreiters: „ueber_beiden“, „zwischen“,
    „unter_beiden“ oder „gleich“ (gleich einem der beiden); ohne Wert None."""
    known = [x for x in leaders if x is not None]
    if value is None or not known:
        return None
    if any(value == x for x in known):
        return "gleich"
    if all(value > x for x in known):
        return "ueber_beiden"
    if all(value < x for x in known):
        return "unter_beiden"
    return "zwischen"


def comparison_size(group: dict, weight: int) -> int:
    """Zahl der Aktien in der Vergleichsmenge einer Rangliste: V bei 0/100, sonst U (Perzentile darin)."""
    return int(len(group["V"] if weight == 0 else group["U"]))


def app_score(group: dict, weight: int, j: int) -> dict | None:
    """Score einer Aktie wie in der App (Methodenbeschreibung: Score = w/100 · G + (1 − w/100) · R) mit den Perzentilen
    ihrer Rendite (R) und ihres R² (G) in der Vergleichsmenge; bei 0/100 die Rendite in V (R² nicht gewichtet). Nicht
    in der Vergleichsmenge → None."""
    if weight == 0:
        m, d_r = len(group["V"]), group["a_rv"].get(j)
        if d_r is None:
            return None
        p_r = 100.0 if m == 1 else 100.0 * (d_r / 2.0 - 1.0) / (m - 1)
        return {"score": p_r, "p_rendite": p_r, "p_r2": None}
    m, d_g, d_r = len(group["U"]), group["a_gu"].get(j), group["a_ru"].get(j)
    if d_g is None or d_r is None:
        return None
    if m == 1:
        p_g = p_r = 100.0
    else:
        p_g, p_r = 100.0 * (d_g / 2.0 - 1.0) / (m - 1), 100.0 * (d_r / 2.0 - 1.0) / (m - 1)
    s = float(nachrechnen.score(weight, np.array([p_g]), np.array([p_r]))[0])
    return {"score": s, "p_rendite": p_r, "p_r2": p_g}


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


def ranking_effects(
    stand: nachrechnen.Stand,
    variants: dict[str, dict[int, tuple[np.ndarray, np.ndarray, set[int]]]],
    liquid,
    min_trend: int,
    top_stocks: set[int],
    attribute: set[str] | None = None,
    order_details: set[str] | None = None,
) -> dict[str, tuple[dict, dict, list[dict]]]:
    """Alle Ranglisten mit den Kursen des Stands und – je Variante – mit den ersetzten Kursen (unabhängige Rechnung, ein
    Durchgang über die Zeiträume für alle Varianten): Zählwerte, Wirkung je Aktie aus ``top_stocks`` und – einzeln – jede
    Rangliste mit anderem Platz 1 oder anderen Aktien unter den ersten 10. Für Varianten in ``attribute`` (Vorgabe: alle) mit
    Suche nach den Auslösern eines neuen Platzes 1, für Varianten in ``order_details`` auch jede Rangliste, deren erste 10
    bei gleichen Aktien eine andere Reihenfolge haben (mit den Plätzen vorher und nachher)."""
    attribute = set(variants) if attribute is None else set(attribute)
    order_details = set(order_details or ())
    totals = {v: Counter() for v in variants}
    moves = {v: {i: Counter() for i in top_stocks} for v in variants}
    changes: dict[str, list[dict]] = {v: [] for v in variants}
    attributed = Counter()
    active = {v: subs for v, subs in variants.items() if subs}
    for h in range(1, 91) if active else ():
        win = stand.get(f"windows/{h}.full.bin")
        stand.drop(f"windows/{h}.full.bin")
        mm = win["m"]
        status = np.frombuffer(__import__("base64").b64decode(win["status_b64"]), dtype=np.uint8).copy()
        idx = [int(x) for x in mm["idx"]]
        r_of = {i: float(mm["r"][k]) for k, i in enumerate(idx)}
        r2_of = {i: mm["r2"][k] for k, i in enumerate(idx)}
        start_of = {i: int(mm["start"][k]) for k, i in enumerate(idx)}
        groups = (("A", idx), ("B", [i for i in idx if liquid[i]]))
        before_of: dict[str, dict] = {}
        for v, substituted in active.items():
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
            totals[v]["zeitraeume_mit_geaenderten_werten"] += 1
            for name, members in groups:
                members_arr = np.array(members, dtype=np.int64)
                if name not in before_of:
                    before_of[name] = lists_of(nachrechnen.rank_group(members_arr, status, r_of, r2_of))
                before = before_of[name]
                after = lists_of(nachrechnen.rank_group(members_arr, status_new, r_new, r2_new))
                in_group = set(members)
                candidates = [i for i in touched if i in in_group]
                for w, order in before.items():
                    if not order and not after[w]:
                        continue
                    totals[v]["ranglisten_verglichen"] += 1
                    flags = compare_orders(order, after[w])
                    for flag, value in flags.items():
                        if value:
                            totals[v][f"{flag}_geaendert"] += 1
                    same_members = not flags["top10_aktien"]
                    if flags["spitze"] or flags["top10_aktien"] or (v in order_details and flags["top10_reihenfolge"]):
                        change = {
                            "h": h,
                            "gruppe": name,
                            "w": int(w),
                            "platz1": [order[0] if order else None, after[w][0] if after[w] else None] if flags["spitze"] else None,
                            "raus": sorted(set(order[:10]) - set(after[w][:10])),
                            "rein": sorted(set(after[w][:10]) - set(order[:10])),
                            "ersetzt": sorted(set(candidates) & (set(order[:10]) | set(after[w][:10]))),
                        }
                        if v in order_details and flags["top10_reihenfolge"] and same_members:
                            places = [k for k in range(min(10, len(order), len(after[w]))) if order[k] != after[w][k]]
                            change["reihenfolge"] = {"plaetze": [k + 1 for k in places], "vorher": [order[k] for k in places], "nachher": [after[w][k] for k in places]}
                        if flags["spitze"] and order and after[w]:
                            if v in attribute and attributed[v] < MAX_ATTRIBUTIONS:
                                attributed[v] += 1
                                change.update(leader_change(members_arr, w, order, after[w][0], candidates, (status, r_of, r2_of), (status_new, r_new, r2_new), start_of))
                            else:
                                change.update({"nicht_untersucht": True, "platz_des_neuen_vorher": order.index(after[w][0]) + 1 if after[w][0] in order else None,
                                               "rendite": {}, "r2": {}, "score": {}, "vergleichsmenge": None, "ausloeser": None, "ausloeser_werte": {},
                                               "allein": [], "ohne_ausloeser": None, "ersetzte_im_zeitraum": len(candidates), "start": {}})
                        changes[v].append(change)
                    position_before = {i: k for k, i in enumerate(order[:10])}
                    position_after = {i: k for k, i in enumerate(after[w][:10])}
                    for i in moves[v]:
                        was, now = position_before.get(i), position_after.get(i)
                        if was is None and now is None:
                            continue
                        moves[v][i]["unter_ersten_10_vorher"] += was is not None
                        moves[v][i]["unter_ersten_10_nachher"] += now is not None
                        moves[v][i]["platz1_vorher"] += was == 0
                        moves[v][i]["platz1_nachher"] += now == 0
                        if was is not None and now is not None and was != now:
                            moves[v][i]["platz_geaendert"] += 1
    out = {}
    for v in variants:
        totals[v]["ranglisten_insgesamt"] = 90 * 2 * len(nachrechnen.WEIGHTS)
        out[v] = (dict(totals[v]), {i: dict(c) for i, c in moves[v].items()}, changes[v])
    return out


def ranking_effect(stand: nachrechnen.Stand, substituted: dict[int, tuple[np.ndarray, np.ndarray, set[int]]], liquid, min_trend: int, top_stocks: set[int]) -> tuple[dict, dict, list[dict]]:
    """Eine Variante – siehe ``ranking_effects``."""
    return ranking_effects(stand, {"x": substituted}, liquid, min_trend, top_stocks)["x"]


class Lettering:
    """Buchstaben statt Namen: jede Aktie genau ein Buchstabe (A–Z, dann Z26 …), zuerst die Aktien der Zeilen je Aktie, dann
    die übrigen in der Reihenfolge ihres ersten Auftretens; Aktien ohne eigene Zeile kommen mit ihrem Zustand in die Legende."""

    def __init__(self, first: list[int], state_of, info: dict[int, dict], top10: dict[int, int]) -> None:
        self.letters = {i: letter_label(k) for k, i in enumerate(first)}
        self.state_of, self.info, self.top10 = state_of, info, top10
        self.legend: list[dict] = []

    def __call__(self, i: int | None) -> str:
        if i is None:
            return "–"
        if i not in self.letters:
            self.letters[i] = letter_label(len(self.letters))
            state = self.state_of(i)
            entry = {"aktie": self.letters[i], "abgefragt": i in self.info, "zustand": state, "top10": int(self.top10.get(i, 0))}
            entry.update(self.info.get(i, {}))
            self.legend.append(entry)
        return self.letters[i]

    def trigger_days(self, variant_days: dict[int, dict[int, tuple[float, str]]], j: int, start: int, values: dict | None = None) -> dict:
        days = sorted(d for d in (variant_days.get(j) or {}) if d >= start)
        shown = [{"tag": nachrechnen._iso(d), "abweichung_pct": variant_days[j][d][0], "ursache": variant_days[j][d][1]} for d in days[:MAX_TRIGGER_DAYS]]
        out = {"aktie": self(j), "tage": shown, "weitere_tage": max(0, len(days) - MAX_TRIGGER_DAYS)}
        if values:
            out.update(
                {
                    "rendite_pct": [None if v is None else round(100 * v, 3) for v in values["rendite"]],
                    "r2": [None if v is None else round(float(v), 5) for v in values["r2"]],
                    "in_vergleichsmenge": list(values["in_vergleichsmenge"]),
                    "lage_rendite": list(values["lage_rendite"]),
                    "lage_r2": list(values["lage_r2"]),
                }
            )
        return out

    @staticmethod
    def score_pair(pair) -> list[dict | None]:
        return [None if s is None else {"score": round(s["score"], 3), "p_rendite": round(s["p_rendite"], 3), "p_r2": None if s["p_r2"] is None else round(s["p_r2"], 3)} for s in pair]

    def changes(self, changes: list[dict], variant_days: dict) -> list[dict]:
        out = []
        for c in changes:
            row = {"h": c["h"], "gruppe": c["gruppe"], "w": c["w"], "platz1": [self(x) for x in c["platz1"]] if c.get("platz1") else None,
                   "raus": [self(x) for x in c["raus"]], "rein": [self(x) for x in c["rein"]], "ersetzt": [self(x) for x in c.get("ersetzt") or []]}
            if c.get("reihenfolge"):
                row["reihenfolge"] = {"plaetze": c["reihenfolge"]["plaetze"], "vorher": [self(x) for x in c["reihenfolge"]["vorher"]], "nachher": [self(x) for x in c["reihenfolge"]["nachher"]]}
            if c.get("platz1"):
                row.update(
                    {
                        "platz_des_neuen_vorher": c.get("platz_des_neuen_vorher"),
                        "rendite_pct": {self(j): [None if v is None else round(100 * v, 3) for v in pair] for j, pair in c["rendite"].items()},
                        "r2": {self(j): [None if v is None else round(float(v), 5) for v in pair] for j, pair in c["r2"].items()},
                        "score": {self(j): self.score_pair(pair) for j, pair in (c.get("score") or {}).items()},
                        "vergleichsmenge": None if c.get("vergleichsmenge") is None else list(c["vergleichsmenge"]),
                        "ausloeser": None if c["ausloeser"] is None else [self.trigger_days(variant_days, j, c["start"][j], (c.get("ausloeser_werte") or {}).get(j)) for j in c["ausloeser"]],
                        "allein_ausreichend": [self(j) for j in c["allein"]],
                        "ohne_ausloeser": None if c.get("ohne_ausloeser") is None else self(c["ohne_ausloeser"]),
                        "ersetzte_aktien_im_zeitraum": c["ersetzte_im_zeitraum"],
                        "nicht_untersucht": bool(c.get("nicht_untersucht")),
                    }
                )
            out.append(row)
        return out

    def mapping(self, stand: nachrechnen.Stand) -> list[dict]:
        """Zuordnung jedes Buchstabens zu genau einer Aktie: ihr bester Platz in einer Rangliste dieses Stands."""
        places_of = best_places(stand, set(self.letters))
        out = []
        for i, name in sorted(self.letters.items(), key=lambda kv: (len(kv[1]), kv[1])):
            found = places_of.get(i)
            out.append({"aktie": name, "fundstelle": None if found is None else {"h": found[1], "gruppe": "AB"[found[2]], "w": found[3], "platz": found[0]}})
        return out


def canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def transfer_payload(sid: str, auswahl: str, report: dict, groups: dict[int, str], compared: set[int], alt_compared: dict[int, str], no_prices: dict[int, str],
                     failures: dict[int, str], repl: dict[str, dict[int, dict[int, float]]], days: dict[str, dict[int, dict[int, tuple[float, str]]]], info: dict[int, dict]) -> dict:
    """Übergabe eines Prüfjobs an den Job „gemeinsame Wirkung“: je Variante (a Nasdaq-Historie, b offizieller Schlusskurs, c
    Zusatzquellen) die Ersatzkurse mit Abweichung in % und Ursache, dazu Gruppen, Abdeckung und Zählwerte. Die Prüfsumme über
    die Ersatzkurse steht im Protokoll beider Jobs – so ist belegt, dass die gemeinsame Rechnung genau diese Kurse nutzt."""
    variants = {
        v: {str(i): [[int(d), float(repl[v][i][d]), days[v][i][d][0], days[v][i][d][1]] for d in sorted(repl[v][i])] for i in sorted(repl[v])}
        for v in ("a", "b", "c")
    }
    counts = ("tage", "ursachen", "nocp_vergleich", "nocp_ursachen", "ungeklaert_gruende", "nur_eine_quelle", "ohne_vergleichskurse_kuerzel", "ohne_nasdaq_boerse",
              "zusatzquellen", "detailabruf", "nasdaq_anfragen", "abruf_fehlgeschlagen", "ohne_vergleichskurse", "ranglisten", "ranglisten_offizieller_schlusskurs", "ranglisten_zusatzquellen")
    data = {
        "format": TRANSFER_FORMAT,
        "stand": sid,
        "auswahl": auswahl,
        "abgerufen_utc": report["abgerufen_utc"],
        "gruppen": {str(i): g for i, g in sorted(groups.items())},
        "verglichen_nasdaq": sorted(int(i) for i in compared),
        "verglichen_zusatz": {str(i): source for i, source in sorted(alt_compared.items())},
        "ohne_vergleichskurse": {str(i): reason for i, reason in sorted(no_prices.items())},
        "fehlgeschlagen": {str(i): reason for i, reason in sorted(failures.items())},
        "info": {str(i): value for i, value in sorted(info.items())},
        "abdeckung_je_gruppe": report["abdeckung_je_gruppe"],
        "kategorien": report["kategorien"],
        "zaehler": {k: report.get(k) for k in counts},
        **variants,
    }
    data["pruefsumme"] = hashlib.sha256(canonical({v: variants[v] for v in ("a", "b", "c")})).hexdigest()[:16]
    return data


def transfer_aad(sid: str, auswahl: str) -> str:
    return f"kursursachen/{sid}/{auswahl}"


def seal(data: dict, key, sid: str, auswahl: str) -> str:
    """Übergabe verschlüsseln (AES-256-GCM mit dem Schlüssel des Stands, an Stand und Job gebunden) und als Base64 – so steht
    sie als Ausgabe des Jobs bei GitHub, ohne dass Kurse oder Zuordnungen lesbar sind."""
    return base64.b64encode(crypto.pack(canonical(data), key, transfer_aad(sid, auswahl))).decode("ascii")


def unseal(text: str, key, sid: str, auswahl: str) -> dict:
    return json.loads(crypto.unpack(base64.b64decode(text), key, transfer_aad(sid, auswahl)))


# Ergebnis des Laufs 40139805053 (24.10.2026, Stand 2026-10-23_3f7ce5f3, zwei Jobs) – zum Vergleich: dieselben Kurse ergeben
# dieselbe Wirkung, wenn die erneut abgerufenen Vergleichskurse denen von damals gleichen (die Kurse selbst hat der Lauf
# nicht gespeichert: keine Artefakte, nur Zählwerte im Protokoll)
REFERENCE_RUN = "40139805053"
REFERENCE_STAND = "2026-10-23_3f7ce5f3"
REFERENCE_EFFECTS = {
    "a@erste20": {"spitze_geaendert": 0, "top10_aktien_geaendert": 2, "top10_reihenfolge_geaendert": 14, "reihenfolge_geaendert": 1237},
    "b@erste20": {"spitze_geaendert": 4, "top10_aktien_geaendert": 6, "top10_reihenfolge_geaendert": 33, "reihenfolge_geaendert": 1034},
    "a@zufall": {"spitze_geaendert": 0, "top10_aktien_geaendert": 0, "top10_reihenfolge_geaendert": 0, "reihenfolge_geaendert": 842},
    "b@zufall": {"spitze_geaendert": 0, "top10_aktien_geaendert": 0, "top10_reihenfolge_geaendert": 0, "reihenfolge_geaendert": 781},
}
EFFECT_KEYS = ("spitze_geaendert", "top10_aktien_geaendert", "top10_reihenfolge_geaendert", "reihenfolge_geaendert")
COMBINED = ("a", "b", "c", "ac")
COMBINED_TEXT = {
    "a": "(a) Nasdaq-Historie an allen abweichenden Tagen",
    "b": "(b) offizieller Schlusskurs (NOCP) an allen Tagen, an denen er vom Stand abweicht",
    "c": "(c) Zusatzquelle an allen abweichenden Tagen (Aktien ohne Nasdaq-Kurse)",
    "ac": "(a)+(c) alle Vergleichskurse: Nasdaq-Historie und Zusatzquellen",
}


def combine(stand: nachrechnen.Stand, sid: str, transfers: dict[str, dict | None], problems: list[str] | None = None) -> dict:
    """Gemeinsame Neuberechnung (seit dem 25.10.2026, Auftrag 25.10.2026, Punkt 1): die Vergleichskurse aller Prüfjobs zusammen gegen
    denselben Stand – je Variante alle Ranglisten neu, dazu jede Variante je Job allein und in der Aufteilung des Laufs
    40139805053 (erste 20 / Zufallsstichprobe). Jeder neue Platz 1 mit Auslösern über alle Gruppen und dem Vergleich mit den
    Jobs einzeln („auch einzeln“ bzw. „nur gemeinsam“)."""
    manifest = stand.get("manifest.bin")
    instruments = stand.get("instruments.bin")
    cutoff = int(manifest["cutoff_day"])
    min_trend = int((manifest.get("method") or {}).get("min_obs_trend", 15))
    liquid = (instruments.get("turnover") or {}).get("liquid") or [False] * len(instruments["isin"])
    chosen, top10, first, from_top, places = select(stand, instruments, sid)
    start_day = cutoff - gegen.LOOKBACK_DAYS - 5
    problems = list(problems or [])
    legs: dict[str, dict] = {}
    for leg in LEGS:
        t = transfers.get(leg)
        if t is None:
            problems.append(f"{SHARD_TEXT[leg].strip(' ()')}: keine Übergabe")
        elif t.get("format") != TRANSFER_FORMAT or t.get("stand") != sid or t.get("auswahl") != leg:
            problems.append(f"{SHARD_TEXT[leg].strip(' ()')}: Übergabe passt nicht (Format, Stand oder Job)")
        else:
            legs[leg] = t
    present = [leg for leg in LEGS if leg in legs]
    group_of: dict[int, str] = {}
    overlap = 0
    for leg in present:
        for key, g in legs[leg]["gruppen"].items():
            overlap += int(key) in group_of
            group_of[int(key)] = g
    if overlap:
        problems.append(f"{overlap} Aktien in mehr als einem Job")
    missing = [i for i in chosen if i not in group_of]
    cache: dict[int, dict[int, float]] = {}

    def own(i: int) -> dict[int, float]:
        if i not in cache:
            cache[i] = own_series(stand, instruments, i, start_day, cutoff)
        return cache[i]

    def subs(names: list[str], variant: str) -> dict:
        out = {}
        for leg in names:
            for key, rows in (legs[leg].get(variant) or {}).items():
                out[int(key)] = substitution(own(int(key)), {int(r[0]): float(r[1]) for r in rows})
        return out

    def day_notes(variant: str) -> dict[int, dict[int, tuple[float, str]]]:
        out: dict[int, dict[int, tuple[float, str]]] = {}
        for leg in present:
            for key, rows in (legs[leg].get(variant) or {}).items():
                out[int(key)] = {int(r[0]): (r[2], r[3]) for r in rows}
        return out

    variants = {v: subs(present, v) for v in ("a", "b", "c")}
    variants["ac"] = {**variants["a"], **variants["c"]} if variants["c"] else {}  # ohne Zusatzquellen gleich (a)
    for leg in present:
        for v in ("a", "b", "c"):
            variants[f"{v}@{leg}"] = subs([leg], v)
    if "erste10" in legs and "plaetze11_20" in legs:
        for v in ("a", "b"):
            variants[f"{v}@erste20"] = subs(["erste10", "plaetze11_20"], v)
    effects = ranking_effects(stand, variants, liquid, min_trend, set(top10), attribute=set(COMBINED), order_details=set(COMBINED))

    def leaders(changes: list[dict]) -> dict[tuple, tuple]:
        return {(c["h"], c["gruppe"], c["w"]): tuple(c["platz1"]) for c in changes if c.get("platz1")}

    for v in COMBINED:
        bases = ("a", "c") if v == "ac" else (v,)
        single = {leg: {} for leg in present}
        for leg in present:
            for b in bases:
                single[leg].update(leaders(effects[f"{b}@{leg}"][2]))
        for c in effects[v][2]:
            if c.get("platz1"):
                key = (c["h"], c["gruppe"], c["w"])
                c["auch_einzeln"] = [leg for leg in present if single[leg].get(key) == tuple(c["platz1"])]
    only_separate: dict[str, list[dict]] = {}
    for v in ("a", "b", "c"):
        together = leaders(effects[v][2])
        rows = []
        for leg in present:
            for c in effects[f"{v}@{leg}"][2]:
                if c.get("platz1") and together.get((c["h"], c["gruppe"], c["w"])) != tuple(c["platz1"]):
                    rows.append({"job": leg, **c})
        only_separate[v] = rows

    info: dict[int, dict] = {}
    compared_any: set[int] = set()
    no_prices: set[int] = set()
    failed: set[int] = set()
    for leg in present:
        t = legs[leg]
        info.update({int(k): v for k, v in t["info"].items()})
        compared_any |= set(int(i) for i in t["verglichen_nasdaq"]) | {int(k) for k in t["verglichen_zusatz"]}
        no_prices |= {int(k) for k in t["ohne_vergleichskurse"]}
        failed |= {int(k) for k in t["fehlgeschlagen"]}
    us_set = us_stocks(instruments)

    def state_of(i: int) -> str:
        if i in compared_any:
            return "verglichen"
        if i in failed:
            return "ohne_antwort"
        if i in no_prices:
            return "ohne_vergleichskurse"
        if i in missing:
            return "job_fehlt"
        return "keine_us_aktie" if i not in us_set else "nicht_ausgewaehlt"

    names = Lettering([], state_of, info, top10)
    notes = {v: day_notes(v) for v in ("a", "b", "c")}
    notes["ac"] = {**notes["a"], **notes["c"]}
    changes = {}
    for v in COMBINED:
        rows = names.changes(effects[v][2], notes[v])
        for row, raw in zip(rows, effects[v][2]):
            if "auch_einzeln" in raw:
                row["auch_einzeln"] = raw["auch_einzeln"]
        changes[v] = rows
    separate_rows = {}
    for v, rows in only_separate.items():
        lettered = names.changes(rows, notes[v])
        for row, raw in zip(lettered, rows):
            row["job"] = raw["job"]
        separate_rows[v] = lettered
    coverage: dict[str, Counter] = {g: Counter() for g in GROUPS}
    categories: dict[str, Counter] = {}
    counts: dict[str, Counter] = {}
    for leg in present:
        for g, c in legs[leg]["abdeckung_je_gruppe"].items():
            coverage[g].update(c)
        for name, c in (legs[leg].get("kategorien") or {}).items():
            categories.setdefault(name, Counter()).update(c)
        for name in ("tage", "ursachen", "nocp_vergleich", "nocp_ursachen", "ungeklaert_gruende", "ohne_vergleichskurse_kuerzel", "ohne_nasdaq_boerse"):
            counts.setdefault(name, Counter()).update(legs[leg]["zaehler"].get(name) or {})
        counts.setdefault("zusatzquellen_pruefungen", Counter()).update(((legs[leg]["zaehler"].get("zusatzquellen") or {}).get("pruefungen")) or {})
        counts.setdefault("zusatzquellen_tage", Counter()).update(((legs[leg]["zaehler"].get("zusatzquellen") or {}).get("tage")) or {})
        counts.setdefault("zusatzquellen_muster", Counter()).update(((legs[leg]["zaehler"].get("zusatzquellen") or {}).get("muster")) or {})
        counts.setdefault("detailabruf", Counter()).update(legs[leg]["zaehler"].get("detailabruf") or {})
    totals = {v: effects[v][0] for v in effects}
    reference = None
    if sid == REFERENCE_STAND:
        reference = {}
        for v, expected in REFERENCE_EFFECTS.items():
            if v in totals:
                got = {k: totals[v].get(k, 0) for k in EFFECT_KEYS}
                reference[v] = {"erwartet": expected, "jetzt": got, "gleich": got == expected}
    report = {
        "stand": sid,
        "stichtag": nachrechnen._iso(cutoff),
        "jobs": {leg: {"pruefsumme": legs[leg].get("pruefsumme"), "abgerufen_utc": legs[leg].get("abgerufen_utc"), "aktien": len(legs[leg]["gruppen"]),
                       "nasdaq_anfragen": legs[leg]["zaehler"].get("nasdaq_anfragen")} for leg in present},
        "probleme": problems,
        "ausgewaehlt": len(chosen),
        "nicht_uebergeben": len(missing),
        "davon_aus_den_ersten_20": from_top,
        "plaetze": places,
        "abdeckung_je_gruppe": {g: dict(c) for g, c in coverage.items() if c},
        "kategorien": {name: dict(c) for name, c in categories.items()},
        "zaehler": {name: dict(c) for name, c in counts.items()},
        "ranglisten": totals,
        "aenderungen": changes,
        "nur_getrennt": separate_rows,
        "vergleich_mit_lauf": reference,
        "weitere_buchstaben": names.legend,
        "zuordnung": names.mapping(stand),
    }
    gaps = sum(c.get("keine_vergleichskurse", 0) + c.get("abruf_fehlgeschlagen", 0) for c in coverage.values())
    report["urteil"] = "unvollstaendig" if problems or missing or gaps else "gerechnet"
    return report


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


JOB_TEXT = {"erste10": "erste 10", "plaetze11_20": "Plätze 11–20", "zufall": "Zufallsstichprobe", "erste20": "erste 20"}


def _leader_line(c: dict, variant: str, n: int, total: int) -> str:
    """Eine Rangliste mit neuem Platz 1: Zeitraum, Methode, bisheriger und neuer Spitzenreiter mit Rendite und R² vorher/nachher,
    auslösende Kursabweichungen, ob eine Aktie allein reicht und ob Platz 1 auch ohne die Auslöser wechselt."""
    before, after = c["platz1"]
    place = c.get("platz_des_neuen_vorher")
    parts = [f"{variant} {n}/{total} – {_method(c)}: bisher {before}, neu {after} " + (f"(vorher Platz {place})" if place else "(vorher nicht in dieser Rangliste)")]
    for name in (before, after):
        r = (c.get("rendite_pct") or {}).get(name)
        g = (c.get("r2") or {}).get(name)
        if r:
            text = f"{name}: Rendite {_pct(r[0])} → {_pct(r[1])}"
            if g:
                text += f", R² {'–' if g[0] is None else g[0]} → {'–' if g[1] is None else g[1]}" + (" (bei 0/100 nicht gewichtet)" if not c["w"] else "")
            s = (c.get("score") or {}).get(name)
            if s:
                text += f", Score {_score_pair(s, c['w'])}"
            parts.append(text)
    size = c.get("vergleichsmenge")
    if size:
        parts.append(f"Score wie in der App aus den Perzentilen in der Vergleichsmenge ({size[0]} → {size[1]} Aktien)")
    triggers = c.get("ausloeser")
    if c.get("nicht_untersucht"):
        parts.append(f"Auslöser nicht untersucht (mehr als {MAX_ATTRIBUTIONS} neue Plätze 1 in dieser Variante) – {c.get('ersetzte_aktien_im_zeitraum', 0)} ersetzte Aktien im Zeitraum")
    elif triggers is None:
        parts.append(f"Auslöser nicht auf einzelne Aktien eingrenzbar – Platz 1 wechselt erst mit allen {c.get('ersetzte_aktien_im_zeitraum', 0)} ersetzten Aktien des Zeitraums")
    else:
        for tr in triggers:
            days = ", ".join(f"{d['tag']} {d['abweichung_pct']:+.3f} % ({_cause_label(d['ursache'])})" for d in tr["tage"]) or "keine ersetzten Tage im Zeitraum"
            more = f" und {tr['weitere_tage']} weitere Tage" if tr.get("weitere_tage") else ""
            parts.append(f"auslösend {tr['aktie']}{_trigger_values(tr, c['w'], before, after)}: {days}{more}")
        alone = c.get("allein_ausreichend") or []
        parts.append("allein ausreichend: " + (" ".join(alone) + (" (jede für sich)" if len(alone) > 1 else "") if alone else "keine einzelne Aktie – nur zusammen"))
        without = c.get("ohne_ausloeser")
        if without is not None:
            others = max(0, c.get("ersetzte_aktien_im_zeitraum", 0) - len(triggers))
            parts.append(
                f"mit den übrigen {others} ersetzten Aktien, aber ohne die Auslöser: "
                + (f"Platz 1 bleibt {before} (Auslöser nötig)" if without == before else (f"Platz 1 wechselt trotzdem zu {after}" if without == after else f"Platz 1 wäre {without}"))
            )
    if "auch_einzeln" in c:
        jobs = c["auch_einzeln"]
        parts.append("ebenso mit den Kursen eines Jobs allein: " + ", ".join(JOB_TEXT.get(j, j) for j in jobs) if jobs else "nur gemeinsam – mit den Kursen keines Jobs allein")
    return "; ".join(parts)


LAGE_TEXT = {"ueber_beiden": "über beiden", "zwischen": "zwischen beiden", "unter_beiden": "unter beiden", "gleich": "gleich einem der beiden"}


def _score_pair(pair: list, w: int) -> str:
    """Score vorher → nachher mit den Perzentilen (drei Stellen; die App zeigt den Score mit einer)."""
    def one(s: dict | None) -> str:
        return "–" if s is None else f"{s['score']:.3f}"

    def part(key: str) -> str:
        values = ["–" if s is None or s.get(key) is None else f"{s[key]:.3f}" for s in pair]
        return f"{values[0]} → {values[1]}"

    detail = f"Perzentil der Rendite {part('p_rendite')}" if not w else f"Perzentil der Rendite {part('p_rendite')}, des R² {part('p_r2')}"
    return f"{one(pair[0])} → {one(pair[1])} ({detail})"


def _trigger_values(tr: dict, w: int, before: str, after: str) -> str:
    """Werte eines Auslösers und ihre Lage gegenüber den Werten von bisherigem und neuem Spitzenreiter (vorher → nachher)."""
    if "rendite_pct" not in tr:
        return ""
    r, g = tr["rendite_pct"], tr["r2"]
    lr, lg = tr.get("lage_rendite") or [None, None], tr.get("lage_r2") or [None, None]
    lage = lambda pair: f"{LAGE_TEXT.get(pair[0], '–')} → {LAGE_TEXT.get(pair[1], '–')}"  # noqa: E731
    text = f" (Rendite {_pct(r[0])} → {_pct(r[1])}, gegenüber {before} und {after}: {lage(lr)}"
    if w:
        text += f"; R² {'–' if g[0] is None else g[0]} → {'–' if g[1] is None else g[1]}: {lage(lg)}"
        inside = tr.get("in_vergleichsmenge") or [True, True]
        if inside[0] != inside[1]:
            text += "; " + ("tritt in die Vergleichsmenge ein" if inside[1] else "fällt aus der Vergleichsmenge")
    return text + ")"


def _member_line(c: dict, variant: str) -> str:
    marked = set(c.get("ersetzt") or [])
    def show(names: list[str]) -> str:
        return " ".join(f"{x}*" if x in marked else x for x in names) or "–"
    return f"{variant} – {_method(c)}: raus {show(c['raus'])}, rein {show(c['rein'])}"


def _order_line(c: dict, variant: str) -> str:
    o = c["reihenfolge"]
    marked = set(c.get("ersetzt") or [])
    def show(names: list[str]) -> str:
        return " ".join(f"{x}*" if x in marked else x for x in names)
    return f"{variant} – {_method(c)}: Plätze {', '.join(str(k) for k in o['plaetze'])} – vorher {show(o['vorher'])}, nachher {show(o['nachher'])}"


LEGEND_STATE = {
    "ohne_antwort": "ausgewählt, aber ohne Antwort von Nasdaq – Kurse in allen Varianten unverändert",
    "ohne_vergleichskurse": "ausgewählt, aber ohne Vergleichskurse (Nasdaq und Zusatzquellen) – Kurse in allen Varianten unverändert",
    "anderer_job": "in einem anderen Job geprüft – in diesem Job Kurse unverändert",
    "job_fehlt": "ausgewählt, aber ihr Job hat keine Übergabe geliefert – Kurse unverändert",
    "keine_us_aktie": "keine US-Aktie (Nasdaq führt sie nicht) – Kurse unverändert",
    "nicht_ausgewaehlt": "US-Aktie, aber weder unter den ersten 20 einer Rangliste noch in der Zufallsstichprobe – Kurse unverändert",
}


def _legend(entry: dict) -> str:
    if entry.get("zustand") in LEGEND_STATE:
        return LEGEND_STATE[entry["zustand"]]
    if not entry.get("abgefragt", True) or "boerse" not in entry:
        return "nicht abgefragt oder ohne Vergleichskurse – Kurse in allen Varianten unverändert"
    if entry.get("quelle"):
        return (f"{entry['boerse']}, {entry['kursbereich']}; unter den ersten 10 in {entry.get('top10', 0)} Ranglisten; verglichen mit "
                f"{zusatz.SOURCE_TEXT.get(entry['quelle'], entry['quelle'])}, abweichend an {entry.get('abweichend', 0)} Tagen")
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
    no_prices = ", ".join(f"{text} {c[key]}" for key, text in (("keine_vergleichskurse_nasdaq_ohne_kurse", "weder Nasdaq noch eine Zusatzquelle"), ("keine_vergleichskurse_stand_ohne_kurse_im_zeitraum", "Stand ohne Kurse im Zeitraum")) if c.get(key))
    nocp = ", ".join(f"{text} {c[key]}" for key, text in (("nocp_mit_nocp", "mit NOCP"), ("nocp_nasdaq_ohne_nocp", "Nasdaq-notiert ohne NOCP"), ("nocp_nicht_nasdaq_notiert", "ohne NOCP: nicht Nasdaq-notiert")) if c.get(key))
    nasdaq = c.get("verglichen_nasdaq", c.get("verglichen", 0) - sum(c.get(f"verglichen_{q}", 0) for q in zusatz.SOURCES))
    alt = ", ".join(f"{zusatz.SOURCE_TEXT[q]} {c[f'verglichen_{q}']}" for q in zusatz.SOURCES if c.get(f"verglichen_{q}"))
    return (
        f"{name}: {total} Aktien – erfolgreich verglichen {c.get('verglichen', 0)} (mit Nasdaq {nasdaq}" + (f": {nocp}" if nocp else "") + (f"; mit Zusatzquelle: {alt}" if alt else "") + ")"
        + f"; keine Vergleichskurse {c.get('keine_vergleichskurse', 0)}" + (f" ({no_prices})" if no_prices else "")
        + f"; Abruf fehlgeschlagen {c.get('abruf_fehlgeschlagen', 0)}"
    )


def _category_lines(categories: dict, ursachen: dict, nocp_ursachen: dict, alt_days: dict) -> list[str]:
    """Die fünf Ergebnisarten je Vergleich (Tage): bestätigte Übereinstimmung, festgestellte Abweichung, belegte Ursache,
    ungeklärte Ursache, fehlende Vergleichsmöglichkeit."""
    a = categories.get("nasdaq_historie") or {}
    b = categories.get("offizieller_schlusskurs") or {}
    c = categories.get("zusatzquellen") or {}
    evidence = "; ".join(f"{CAUSE_TEXT[k]} {ursachen[k]}" for k in CAUSES if k in EVIDENCE and ursachen.get(k)) or "–"
    befund_b = ", ".join(f"{NOCP_NOTE.get(k[len('befund_'):], k)} {v}" for k, v in sorted(nocp_ursachen.items()) if k.startswith("befund_")) or "–"
    evidence_b = ", ".join(f"{CAUSE_TEXT[k]} {v}" for k, v in sorted(nocp_ursachen.items()) if k in EVIDENCE) or "–"
    evidence_c = ", ".join(f"{CAUSE_TEXT[k[len('ursache_'):]]} {v}" for k, v in sorted(alt_days.items()) if k.startswith("ursache_") and k[len("ursache_"):] in EVIDENCE) or "–"
    second = ", ".join(f"{k[len('zweite_quelle_'):]} {v}" for k, v in sorted(alt_days.items()) if k.startswith("zweite_quelle_")) or "–"
    otc_last = ", ".join(f"{k[len('otc_letzter_abschluss_'):]} {v}" for k, v in sorted(alt_days.items()) if k.startswith("otc_letzter_abschluss_")) or "–"
    return [
        f"Ergebnis gegen die Nasdaq-Historie (Tage): bestätigte Übereinstimmung {a.get('uebereinstimmung', 0)}; festgestellte Abweichung {a.get('abweichung', 0)} – "
        f"davon Ursache belegt {a.get('belegt', 0)} ({evidence}), Stand = offizieller Schlusskurs {a.get('stand_ist_nocp', 0)} (abweichend nur die Nasdaq-Historie), "
        f"Ursache ungeklärt {a.get('ungeklaert', 0)} (Befund Stand ≠ NOCP bei Nasdaq-Historie = NOCP {ursachen.get('abweichung_vom_nocp', 0)}, ohne Beleg {ursachen.get('ungeklaert', 0)}); "
        f"fehlende Vergleichsmöglichkeit: {a.get('ohne_vergleich_aktien', 0)} Aktien ohne Nasdaq-Kurse, {a.get('ohne_vergleich_tage', 0)} Tage nur im Stand",
        f"Ergebnis gegen den offiziellen Schlusskurs NOCP (Tage): bestätigte Übereinstimmung {b.get('uebereinstimmung', 0)}; festgestellte Abweichung {b.get('abweichung', 0)} – "
        f"davon Ursache belegt {b.get('belegt', 0)} ({evidence_b}), Ursache ungeklärt {b.get('ungeklaert', 0)} (Befund: {befund_b}); Faktor eines Splits {b.get('faktor_split', 0)} "
        f"(NOCP unbereinigt, keine Abweichung); fehlende Vergleichsmöglichkeit: {b.get('ohne_vergleich_aktien', 0)} Aktien und {b.get('ohne_vergleich_tage', 0)} Tage ohne NOCP "
        "(nicht Nasdaq-notiert: offizieller Schlusskurs der NYSE-Gruppe in den geprüften Quellen nur kostenpflichtig)",
        f"Ergebnis gegen die Zusatzquellen (Tage): bestätigte Übereinstimmung {c.get('uebereinstimmung', 0)}; festgestellte Abweichung {c.get('abweichung', 0)} – davon Ursache belegt "
        f"{c.get('belegt', 0)} ({evidence_c}), Ursache ungeklärt {c.get('ungeklaert', 0)} (zweite Quelle am Tag: {second}); fehlende Vergleichsmöglichkeit: "
        f"{c.get('ohne_vergleich_aktien', 0)} Aktien ohne Vergleichskurse in den geprüften Quellen, {c.get('ohne_vergleich_tage', 0)} Tage nur im Stand "
        f"(davon ohne Umsatz bei Yahoo {alt_days.get('nur_im_stand_ohne_umsatz', 0)}); letzter Abschluss bei OTC Markets gegen den Stand am selben Tag (je Aktie ohne Nasdaq-Kurse): {otc_last}",
    ]


def _zusatz_line(z: dict, exchanges: dict) -> list[str]:
    checks = z.get("pruefungen") or {}
    rows = [
        f"Zusatzquellen für {z.get('aktien_ohne_nasdaq', 0)} Aktien ohne Nasdaq-Kurse (Börse der Yahoo-Kurse des Stands: {_counts(exchanges)}): verglichen {z.get('verglichen', 0)} "
        f"({_counts({zusatz.SOURCE_TEXT.get(k, k): v for k, v in (z.get('je_quelle') or {}).items()})}); geprüft je Quelle: Identität, Handelsplatz, Währung, Handelsdatum, "
        "Kursniveau, Bereinigung – Ergebnis: " + _counts(checks),
    ]
    if z.get("muster"):
        rows.append(f"Muster der ungeklärten Tage gegen Zusatzquellen (ohne Kurse): {_counts(z['muster'])}")
    if z.get("felder"):
        rows.append("Felder der Antworten (nur Namen, ohne Werte): " + "; ".join(sorted(set(z["felder"]))))
    return rows


def _mapping_lines(report: dict) -> list[str]:
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
        mapping.insert(0, f"Datenstand {report['stand']} (Kursstand {report.get('stichtag', '–')}); in der App mit der Passphrase unter „Rangliste“, Einstellung „Auffällige ausblenden“ aus "
                          "– nach einem neueren Stand über „Datenstand & Betrieb → Frühere Stände → Anzeigen“ diesen Stand wählen")
    return mapping


def build_lines(report: dict) -> tuple[str, str, list[str], list[tuple[str, list[str]]]]:
    """Titel, Art und Zeilen des Ergebnisses eines Prüfjobs – Kopf (Urteil und Zählwerte) und Abschnitte mit Einzelheiten."""
    if "jobs" in report:
        return build_combined_lines(report)
    t, c, e = report["tage"], report["ursachen"], report["ranglisten"]
    p = report.get("plaetze") or {}
    nc = report.get("nocp_vergleich") or {}
    cov = report.get("top10_abdeckung") or {}
    result = report.get("urteil") or verdict(report)
    shard = report.get("auswahl", "alle")
    open_days = sum(c.get(k, 0) for k in OPEN) + ((report.get("kategorien") or {}).get("zusatzquellen") or {}).get("ungeklaert", 0)
    all_days = t.get("abweichend", 0) + ((report.get("kategorien") or {}).get("zusatzquellen") or {}).get("abweichung", 0)
    title = VERDICT_TITLE[result].format(n=report.get("abruf_fehlgeschlagen", 0), k=report.get("ohne_vergleichskurse", 0), u=open_days, a=all_days)
    title = title.replace("Kursursachen:", f"Kursursachen{SHARD_TEXT[shard]}:", 1)
    level = {"unvollstaendig": "error", "ungeklaert": "error", "belegt": "notice", "keine_abweichungen": "notice"}[result]
    block = (
        f"; Sperrpausen {report.get('sperrpausen', 0)}"
        + (f" (erste nach {report['nasdaq_anfragen_bis_zur_ersten_sperre']} Anfragen an Nasdaq)" if report.get("nasdaq_anfragen_bis_zur_ersten_sperre") else "")
        + (f", Anfragen an Nasdaq {report['nasdaq_anfragen']}" if report.get("nasdaq_anfragen") is not None else "")
        + (f", Abstand zuletzt {report['nasdaq_abstand_s']} s" if report.get("nasdaq_abstand_s") is not None else "")
    )
    groups = report.get("abdeckung_je_gruppe") or {}
    others = report.get("im_anderen_job", 0)
    head = [
        f"Nachträglich abgerufen am {report['abgerufen_utc']} (Nasdaq-Historie, offizieller Schlusskurs NOCP, Yahoo-Tages- und Minutenkurse, Dividenden, Zusatzquellen) – keine Originaldaten. "
        f"Stand {report['stand']} (Kursstand {report['stichtag']}); {report['ausgewaehlt']} US-Aktien"
        + (f" in diesem Job, {others} in den anderen Jobs (zusammen {report.get('ausgewaehlt_insgesamt', 0)}; davon {report['davon_aus_den_ersten_20']} aus den ersten 20 einer Rangliste). "
           if shard != "alle" else f" (davon {report['davon_aus_den_ersten_20']} aus den ersten 20 einer Rangliste). ")
        + f"Plätze unter den ersten 10 aller Ranglisten: {p.get('erste_10', 0)}, davon US-Aktien {p.get('erste_10_us', 0)}; Platz 1: {p.get('platz_1', 0)}, davon US-Aktien {p.get('platz_1_us', 0)}. "
        "Die ausgewählten US-Aktien sind keine Vollprüfung aller Aktien der App.",
    ]
    if report.get("uebergabe"):
        head.append(f"Übergabe an den Job „gemeinsame Wirkung“: Prüfsumme der Vergleichskurse {report['uebergabe'].get('pruefsumme')} (verschlüsselt, nur Prüfsumme im Protokoll)")
    if groups:
        head.append("Abdeckung je Gruppe (fehlende Daten zählen nicht als geprüft):")
        head += [_coverage_line(GROUP_TEXT[g], groups.get(g) or {}) for g in GROUPS if g in groups]
        if "erste_10" in groups and "erste_20" in groups:
            both = Counter(groups.get("erste_10") or {}) + Counter(groups.get("erste_20") or {})
            head.append(_coverage_line("erste 20 gesamt (erste 10 und Plätze 11–20)", dict(both)))
        if report.get("ohne_vergleichskurse_kuerzel"):
            head.append(f"Ohne Kurse bei Nasdaq nach Länge des Kürzels: {_counts(report['ohne_vergleichskurse_kuerzel'])}")
        missing = [GROUP_TEXT[g] for g in GROUPS if g not in groups]
        if missing:
            head.append(f"Nicht in diesem Job (in den anderen Jobs desselben Laufs geprüft): {', '.join(missing)}")
    head += [
        f"Abruf in {report.get('abrufrunden', 1)} Runden (nachgeholt {report.get('abruf_nachgeholt', 0)}, ohne Antwort {report.get('abruf_fehlgeschlagen', 0)}): {_counts(report['abruf'])}{block}; "
        f"NOCP: {_counts(report['nocp_abruf'])}" + (f" (Felder {', '.join(report['nocp_felder'])})" if report.get("nocp_felder") else "")
        + f"; Minutenkurse und Dividenden: {_counts(report.get('detailabruf') or {})}",
        f"Offizieller Schlusskurs (NOCP) aller Nasdaq-notierten Aktien der Auswahl: {nc.get('aktien', 0)} Aktien, {nc.get('tage', 0)} Tage – Stand gleich {nc.get('stand_gleich', 0)}, "
        f"Stand ungleich {nc.get('stand_ungleich', 0)}, Faktor eines Splits {nc.get('faktor_split', 0)} (NOCP unbereinigt, nicht ersetzt); "
        f"Nasdaq-Historie gleich {nc.get('nasdaq_historie_gleich', 0)}, ungleich {nc.get('nasdaq_historie_ungleich', 0)}",
        f"Börsentage gegen die Nasdaq-Historie verglichen {t.get('verglichen', 0)}, abweichend {t.get('abweichend', 0)} ({_counts(report.get('arten') or {})}; mit NOCP {t.get('abweichend_mit_nocp', 0)}, "
        f"mit Minutenkurs {t.get('abweichend_mit_minutenkursen', 0)})",
    ]
    head += _category_lines(report.get("kategorien") or {}, c, report.get("nocp_ursachen") or {}, (report.get("zusatzquellen") or {}).get("tage") or {})
    head += [
        f"Ungeklärte Tage – Prüfgrenze bzw. Befund (erklärt, warum kein Beleg möglich war, nicht die Abweichung): {_counts(report.get('ungeklaert_gruende') or {}, UNEXPLAINED_TEXT)}; "
        f"Muster der ungeklärten Tage: {_counts(report.get('ungeklaert_muster') or {})}",
        f"Umsatz Nasdaq-Historie gegen Yahoo an allen verglichenen Tagen: {_counts(report.get('umsatz_vergleich') or {})}; "
        f"Tage nur im Stand {report['nur_eine_quelle'].get('nur_im_stand', 0)} (davon ohne Umsatz bei Yahoo {report['nur_eine_quelle'].get('nur_im_stand_ohne_umsatz_bei_yahoo', 0)}), "
        f"nur bei Nasdaq {report['nur_eine_quelle'].get('nur_bei_nasdaq', 0)} (davon mit Yahoo-Kurs {report['nur_eine_quelle'].get('nur_bei_nasdaq_yahoo_mit_kurs', 0)}); "
        f"Aktien mit Ereignis im Zeitraum: {_counts(report['aktien_mit_ereignis_im_zeitraum'])}",
    ]
    if report.get("zusatzquellen", {}).get("aktien_ohne_nasdaq"):
        head += _zusatz_line(report["zusatzquellen"], report.get("ohne_nasdaq_boerse") or {})
    head += [
        f"US-Aktien unter den ersten 10 irgendeiner Rangliste: {cov.get('us_aktien_unter_ersten_10', 0)} – mit Nasdaq verglichen {cov.get('verglichen', 0)} (ohne Abweichung {cov.get('ohne_abweichung', 0)}, "
        f"davon nur der offizielle Schlusskurs anders {cov.get('davon_nur_nocp_abweichend', 0)}; jede Abweichung belegt {cov.get('alle_abweichungen_belegt', 0)}, "
        f"mit ungeklärten Tagen {cov.get('mit_ungeklaerten_tagen', 0)}), mit Zusatzquelle verglichen {cov.get('verglichen_zusatzquelle', 0)}, "
        f"ohne Vergleichskurse {cov.get('ohne_nasdaq_kurse', 0)}, ohne Antwort {cov.get('abruf_fehlgeschlagen', 0)}"
        + (f", in den anderen Jobs {cov['im_anderen_job']}" if cov.get("im_anderen_job") else ""),
        f"Ranglisten dieses Jobs allein (unabhängige Rechnung, gleiche Zulassung zu Gruppe B; gemeinsame Wirkung aller Jobs im Job „gemeinsame Wirkung“) – (a) Nasdaq-Kurs an allen abweichenden Tagen: {_effect(e)}",
        f"(b) offizieller Schlusskurs (NOCP) an allen Tagen, an denen er vom Stand abweicht: {_effect(report.get('ranglisten_offizieller_schlusskurs') or {})}",
        f"(c) Zusatzquelle an allen abweichenden Tagen: {_effect(report.get('ranglisten_zusatzquellen') or {})}",
        f"Platz 1 anders – (a): {_changes(report.get('aenderungen_nasdaq') or [], 'platz1')} | (b): {_changes(report.get('aenderungen_offizieller_schlusskurs') or [], 'platz1')} | (c): {_changes(report.get('aenderungen_zusatzquellen') or [], 'platz1')}",
        f"Andere Aktien unter den ersten 10 – (a): {_changes(report.get('aenderungen_nasdaq') or [], 'top10')} | (b): {_changes(report.get('aenderungen_offizieller_schlusskurs') or [], 'top10')} | (c): {_changes(report.get('aenderungen_zusatzquellen') or [], 'top10')}",
        "Lesart: Buchstaben statt Namen, Zuordnung zu genau einer Aktie im Abschnitt „Zuordnung der Buchstaben“; Abweichung = Stand gegenüber dem Ersatzkurs in %; "
        "Kurzformen je Aktie: " + "; ".join(f"„{SHORT_CAUSE[k]}“ = {CAUSE_TEXT[k]}" for k in CAUSES if k != "ungeklaert")
        + "; (a) mit Nasdaq-Kursen an den abweichenden Tagen, (b) mit dem offiziellen Schlusskurs, (c) mit der Zusatzquelle",
    ]

    # Ranglisten mit neuem Platz 1 – jede einzeln, mit den auslösenden Kursabweichungen
    leaders: list[str] = []
    for key, variant in (("aenderungen_nasdaq", "(a) Nasdaq-Kurs"), ("aenderungen_offizieller_schlusskurs", "(b) offizieller Schlusskurs"), ("aenderungen_zusatzquellen", "(c) Zusatzquelle")):
        rows = [x for x in report.get(key) or [] if x.get("platz1")]
        leaders += [_leader_line(x, variant, n, len(rows)) for n, x in enumerate(rows, start=1)]
        if not rows:
            leaders.append(f"{variant}: in keiner Rangliste ein anderer Platz 1")
    members: list[str] = []
    for key, variant in (("aenderungen_nasdaq", "(a)"), ("aenderungen_offizieller_schlusskurs", "(b)"), ("aenderungen_zusatzquellen", "(c)")):
        members += [_member_line(x, variant) for x in report.get(key) or [] if x.get("raus") or x.get("rein")]

    # je Aktie: Aktien unter den ersten 10 (mit eigener Abweichung, dann nur mit anderem NOCP), danach die übrigen
    focus = [s for s in report["aktien"] if s["top10"] or any(s["ursachen"].get(k) for k in OPEN) or s["groesste_abweichung_pct"] > 0.5]
    top_rows, other_rows, nocp_rows, alt_rows = [], [], [], []
    for s in focus:
        moves_a, moves_b = s.get("rangwirkung") or {}, s.get("rangwirkung_nocp") or {}
        (top_rows if s["top10"] else other_rows).append(
            f"Aktie {s['aktie']} ({s['boerse']}, {s['kursbereich']}; unter den ersten 10 in {s['top10']} Ranglisten, Platz 1 in {s['platz1']}): {s['abweichend']} Tage abweichend, "
            f"größte {s['groesste_abweichung_pct']} %; Einordnung: " + (", ".join(f"{SHORT_CAUSE[k]} {s['ursachen'][k]}" for k in CAUSES if s["ursachen"].get(k)) or "–")
            + f"; NOCP {'ja' if s['nocp_abrufbar'] else 'nein'}" + (f" (Stand ungleich NOCP an {s.get('nocp_tage_ungleich', 0)} Tagen)" if s["nocp_abrufbar"] else "")
            + f", Minutenkurse {s['minutenkurse_tage']} Tage; Ereignisse {', '.join(f'{k} {v}' for k, v in s['ereignisse'].items() if v) or 'keine'}"
            + (f" (Dividenden bei Nasdaq nicht geprüft: {s['dividenden_nasdaq']})" if s.get("dividenden_nasdaq", "ok") != "ok" else "")
            + (f"; (a) {_moves(moves_a)}" if moves_a else "")
            + (f"; (b) {_moves(moves_b)}" if moves_b else "")
        )
    for s in report.get("aktien_nur_nocp") or []:
        moves_a, moves_b = s.get("rangwirkung") or {}, s.get("rangwirkung_nocp") or {}
        nocp_rows.append(
            f"Aktie {s['aktie']} ({s['boerse']}, {s['kursbereich']}; unter den ersten 10 in {s['top10']} Ranglisten, Platz 1 in {s['platz1']}): Stand wie Nasdaq-Historie, "
            f"aber ungleich NOCP an {s['nocp_tage_ungleich']} Tagen (größte {s['groesste_abweichung_nocp_pct']} %; Ursache belegt an {s.get('nocp_belegt', 0)})"
            + (f"; (a) {_moves(moves_a)}" if moves_a else "")
            + (f"; (b) {_moves(moves_b)}" if moves_b else "")
        )
    for s in report.get("aktien_zusatzquelle") or []:
        moves_c = s.get("rangwirkung_zusatz") or {}
        alt_rows.append(
            f"Aktie {s['aktie']} ({s['boerse']}, {s['kursbereich']}; unter den ersten 10 in {s['top10']} Ranglisten, Platz 1 in {s['platz1']}): verglichen mit "
            f"{zusatz.SOURCE_TEXT.get(s['quelle'], s['quelle'])}, {s['abweichend']} Tage abweichend, größte {s['groesste_abweichung_pct']} %; Einordnung: "
            + (", ".join(f"{SHORT_CAUSE.get(k, k)} {v}" for k, v in sorted(s["ursachen"].items())) or "–")
            + (f"; (c) {_moves(moves_c)}" if moves_c else "")
        )
    stock_rows = top_rows + nocp_rows + alt_rows + other_rows
    small = len(report["aktien"]) - len(focus)
    if small:
        unchecked = sum(1 for s in report["aktien"] if s not in focus and s.get("dividenden_nasdaq", "ok") != "ok")
        stock_rows.append(
            f"Weitere {small} Aktien mit kleinen Abweichungen (höchstens 0,5 %), nicht unter den ersten 10 und mit belegter Ursache – Zählwerte oben"
            + (f"; davon Dividenden bei Nasdaq nicht geprüft {unchecked}" if unchecked else "")
        )
    sections = [
        ("Platz 1 anders – jede Rangliste einzeln", leaders),
        ("Andere Aktien unter den ersten 10 – einzeln", members),
        ("Ursachen je Aktie", stock_rows),
        ("Zuordnung der Buchstaben", _mapping_lines(report)),
    ]
    return title, level, head, [(name, lines) for name, lines in sections if lines]


COMBINED_TITLE = {
    "unvollstaendig": "Kursursachen gemeinsam: UNVOLLSTÄNDIG – {gaps} von {n} ausgewählten Aktien ohne Vergleichskurse oder ohne Antwort{problems}; gemeinsame Wirkung der übrigen gerechnet",
    "gerechnet": "Kursursachen gemeinsam: alle {n} ausgewählten Aktien verglichen – gemeinsame Wirkung gerechnet",
}


def build_combined_lines(report: dict) -> tuple[str, str, list[str], list[tuple[str, list[str]]]]:
    """Titel, Art und Zeilen der gemeinsamen Neuberechnung aller Prüfjobs."""
    coverage = report.get("abdeckung_je_gruppe") or {}
    gaps = sum(c.get("keine_vergleichskurse", 0) + c.get("abruf_fehlgeschlagen", 0) for c in coverage.values()) + report.get("nicht_uebergeben", 0)
    problems = report.get("probleme") or []
    title = COMBINED_TITLE[report["urteil"]].format(gaps=gaps, n=report.get("ausgewaehlt", 0), problems=(" – " + "; ".join(problems)) if problems else "")
    level = "error" if report["urteil"] == "unvollstaendig" else "notice"
    jobs = "; ".join(f"{JOB_TEXT.get(leg, leg)}: {j['aktien']} Aktien, abgerufen {j['abgerufen_utc']}, Anfragen an Nasdaq {j.get('nasdaq_anfragen')}, Prüfsumme {j['pruefsumme']}"
                     for leg, j in (report.get("jobs") or {}).items())
    p = report.get("plaetze") or {}
    head = [
        f"Gemeinsame Neuberechnung aller Ranglisten gegen den Stand {report['stand']} (Kursstand {report['stichtag']}) mit den Vergleichskursen aller Prüfjobs dieses Laufs – {jobs or 'keine Übergabe'}. "
        "Vergleichskurse nachträglich abgerufen – keine Originaldaten. Die 404 ausgewählten US-Aktien (US-Aktien unter den ersten 20 einer Rangliste und eine Zufallsstichprobe) sind keine Vollprüfung aller Aktien der App; "
        f"Plätze unter den ersten 10 aller Ranglisten: {p.get('erste_10', 0)}, davon US-Aktien {p.get('erste_10_us', 0)}.",
    ]
    if problems:
        head.append("Fehlende oder unpassende Übergaben: " + "; ".join(problems))
    head.append("Abdeckung je Gruppe (aus den Prüfjobs; fehlende Daten zählen nicht als geprüft):")
    head += [_coverage_line(GROUP_TEXT[g], coverage[g]) for g in GROUPS if g in coverage]
    if "erste_10" in coverage and "erste_20" in coverage:
        head.append(_coverage_line("erste 20 gesamt (erste 10 und Plätze 11–20)", dict(Counter(coverage["erste_10"]) + Counter(coverage["erste_20"]))))
    head.append(_coverage_line("alle Gruppen", dict(sum((Counter(c) for c in coverage.values()), Counter()))))
    counts = report.get("zaehler") or {}
    head += _category_lines(report.get("kategorien") or {}, counts.get("ursachen") or {}, counts.get("nocp_ursachen") or {}, counts.get("zusatzquellen_tage") or {})
    head.append(f"Ungeklärte Tage – Prüfgrenze bzw. Befund: {_counts(counts.get('ungeklaert_gruende') or {}, UNEXPLAINED_TEXT)}")
    head.append(f"Minutenkurse und Gegenproben der Dividenden bei Nasdaq (alle Jobs): {_counts(counts.get('detailabruf') or {})}")
    if counts.get("ohne_nasdaq_boerse"):
        head.append(f"Aktien ohne Nasdaq-Kurse – Börse der Yahoo-Kurse des Stands: {_counts(counts['ohne_nasdaq_boerse'])}; Länge des Kürzels: {_counts(counts.get('ohne_vergleichskurse_kuerzel') or {})}; "
                    f"Prüfungen der Zusatzquellen: {_counts(counts.get('zusatzquellen_pruefungen') or {})}; Muster der ungeklärten Tage gegen Zusatzquellen: {_counts(counts.get('zusatzquellen_muster') or {})}")
    effects = report.get("ranglisten") or {}
    head += [f"Gemeinsam {COMBINED_TEXT[v]}: {_effect(effects.get(v) or {})}" for v in COMBINED]
    separate = []
    for name in ("erste10", "plaetze11_20", "zufall", "erste20"):
        for v in ("a", "b", "c"):
            if f"{v}@{name}" in effects and (v != "c" or (effects[f"{v}@{name}"].get("ranglisten_verglichen"))):
                e = effects[f"{v}@{name}"]
                separate.append(f"{JOB_TEXT[name]} ({v}): Platz 1 {e.get('spitze_geaendert', 0)}, Aktien der ersten 10 {e.get('top10_aktien_geaendert', 0)}, "
                                f"Reihenfolge der ersten 10 {e.get('top10_reihenfolge_geaendert', 0)}, irgendeine Änderung {e.get('reihenfolge_geaendert', 0)}")
    head.append("Zum Vergleich je Job allein: " + "; ".join(separate))
    reference = report.get("vergleich_mit_lauf")
    if reference:
        same_all = all(x["gleich"] for x in reference.values())
        detail = "; ".join(f"{JOB_TEXT[v.split('@')[1]]} ({v.split('@')[0]}): " + ("gleich" if x["gleich"] else f"damals {x['erwartet']}, jetzt {x['jetzt']}") for v, x in reference.items())
        head.append(f"Vergleich mit Lauf {REFERENCE_RUN} (gleicher Stand, Aufteilung erste 20 / Zufallsstichprobe): " + ("dieselbe Wirkung – " if same_all else "ABWEICHEND – ") + detail)
    changes = report.get("aenderungen") or {}
    only = report.get("nur_getrennt") or {}
    head.append(
        "Platz 1 anders gemeinsam – " + " | ".join(f"({v}): {_changes(changes.get(v) or [], 'platz1')}" for v in COMBINED)
        + "; nur in einem Job allein anders (gemeinsam nicht): " + (", ".join(f"({v}) {len(rows)}" for v, rows in only.items() if rows) or "keine")
    )
    head.append("Lesart: Buchstaben dieses Jobs (eigene Zählung, Zuordnung unten); * = Kurse dieser Aktie im Zeitraum ersetzt; Abweichung = Stand gegenüber dem Ersatzkurs in %")
    leaders, members, orders, separate_rows = [], [], [], []
    for v in COMBINED:
        if v == "ac" and not (effects.get("ac") or {}).get("ranglisten_verglichen"):
            leaders.append("gemeinsam ac: keine Ersatzkurse aus Zusatzquellen – gleich (a)")
            continue
        rows = [x for x in changes.get(v) or [] if x.get("platz1")]
        leaders += [_leader_line(x, f"gemeinsam {v}", n, len(rows)) for n, x in enumerate(rows, start=1)]
        if not rows:
            leaders.append(f"gemeinsam {v}: in keiner Rangliste ein anderer Platz 1")
        members += [_member_line(x, f"gemeinsam {v}") for x in changes.get(v) or [] if x.get("raus") or x.get("rein")]
        orders += [_order_line(x, f"gemeinsam {v}") for x in changes.get(v) or [] if x.get("reihenfolge")]
    for v, rows in only.items():
        separate_rows += [f"({v}) nur mit den Kursen des Jobs {JOB_TEXT.get(x['job'], x['job'])}: {_method(x)}: bisher {x['platz1'][0]}, neu {x['platz1'][1]} – gemeinsam nicht" for x in rows]
    # Reihenfolge nach Bedeutung: passen nicht alle Teile in die Hinweise, fehlen zuerst die Reihenfolgen (vollständig in der
    # Zusammenfassung des Jobs); die Zuordnung der Buchstaben steht vor ihnen
    sections = [
        ("Gemeinsam: Platz 1 anders – jede Rangliste einzeln", leaders),
        ("Gemeinsam: andere Aktien unter den ersten 10 – einzeln", members),
        ("Nur in einem Job allein anders", separate_rows),
        ("Zuordnung der Buchstaben (gemeinsame Wirkung)", _mapping_lines(report)),
        ("Gemeinsam: andere Reihenfolge der ersten 10 bei gleichen Aktien – einzeln", orders),
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


def _shard_text(report: dict) -> str:
    return " gemeinsam" if "jobs" in report else SHARD_TEXT[report.get("auswahl", "alle")]


def annotation_plan(report: dict) -> dict:
    title, level, head, sections = build_lines(report)
    shard = _shard_text(report)
    items = [(level, title, part) for part in gegen.chunked(split_lines(head))]
    for name, lines in sections:
        parts = gegen.chunked(split_lines(lines))
        suffix = "" if "jobs" in report else shard
        items += [("notice", f"{name}{suffix} ({n}/{len(parts)}; Buchstaben statt Namen)", part) for n, part in enumerate(parts, start=1)]
    return distribute(items, shard)


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


def write_output(path: Path | None, output: str | None) -> int:
    """Schritt „Übergabe“ (ohne Secrets): die verschlüsselte Übergabe des Prüfschritts als Ausgabe des Jobs
    ``vergleich_<Job>`` – der Job „gemeinsame Wirkung“ liest sie aus ``needs``. Ohne Datei: keine Ausgabe (der gemeinsame
    Job meldet dann „keine Übergabe“)."""
    if path is None or not path.exists():
        print("::warning title=Kursursachen: Übergabe::Prüfschritt ohne Übergabe – der Job „gemeinsame Wirkung“ rechnet ohne diesen Job")
        return 0
    leg, _, sealed = path.read_text(encoding="ascii").strip().partition(":")
    if leg not in LEGS or not sealed:
        print("::error title=Kursursachen: Übergabe::Datei der Übergabe unlesbar")
        return 1
    if output:
        with open(output, "a", encoding="ascii") as handle:
            handle.write(f"vergleich_{leg}={sealed}\n")
    print(f"Kursursachen: Übergabe {leg} ({len(sealed)} Zeichen, verschlüsselt) als Ausgabe des Jobs")
    return 0


def load_stand(repo: str, token: str | None, temp: Path, wanted: str | None) -> tuple[str, Path, object]:
    """Stand aus dem Release: der angegebene (z. B. 2026-10-23_3f7ce5f3 – gleich für alle Jobs eines Laufs, auch wenn
    zwischendurch ein neuer Stand erscheint) oder der letzte Stand mit Schlusskursen."""
    if wanted:
        sid = nachrechnen.stand_id(wanted)
        meta, stands, _, _ = nachrechnen.load_explicit_stands(repo, token, temp, [sid], False)
    else:
        meta, stands = nachrechnen.load_release_stands(repo, token, temp, None)
        sid = meta["status"].get("latest_official_snapshot_id")
    folder = dict(stands).get(sid)
    if folder is None:
        raise SystemExit(f"Stand {sid} nicht im Release gefunden")
    return sid, folder, nachrechnen.key_for(meta["descriptor"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", "szymeklh87-commits/tr-aktienvergleich"))
    parser.add_argument("--bericht", type=Path, help="vollständiger Bericht ohne Namen (JSON; nur für Läufe von Hand – der Workflow lädt nichts hoch)")
    parser.add_argument("--hinweise", type=Path, help="alle Hinweise, verteilt auf die Schritte (JSON)")
    parser.add_argument("--teil", type=int, help=f"nur die Hinweise dieses Schritts aus --hinweise ausgeben (2 bis {MAX_STEPS})")
    parser.add_argument("--auswahl", choices=sorted(SHARDS), default=os.environ.get("AUSWAHL") or "alle", help="welcher Teil der Auswahl in diesem Job (Nasdaq: etwa 430 Anfragen je Rechner)")
    parser.add_argument("--stand", default=os.environ.get("STAND") or None, help="Stand-ID (Vorgabe: letzter Stand mit Schlusskursen)")
    parser.add_argument("--uebergabe", type=Path, help="verschlüsselte Übergabe an den Job „gemeinsame Wirkung“ in diese Datei schreiben")
    parser.add_argument("--ausgabe", type=Path, help="Übergabe aus dieser Datei als Ausgabe des Jobs schreiben (Schritt ohne Secrets)")
    parser.add_argument("--gemeinsam", action="store_true", help="gemeinsame Wirkung aus den Übergaben aller Jobs (Umgebung VERGLEICH_<JOB>)")
    args = parser.parse_args(argv)
    if args.teil:
        return print_part(args.hinweise, args.teil)
    if args.ausgabe:
        return write_output(args.ausgabe, os.environ.get("GITHUB_OUTPUT"))
    started = time.monotonic()
    label = " gemeinsam" if args.gemeinsam else SHARD_TEXT[args.auswahl]
    try:
        with tempfile.TemporaryDirectory() as temp:
            sid, folder, key = load_stand(args.repo, os.environ.get("GITHUB_TOKEN"), Path(temp), args.stand)
            if key is None and os.environ.get("GITHUB_ACTIONS") and (args.uebergabe or args.gemeinsam):
                print("::error title=Kursursachen::Stand ohne Verschlüsselung – keine Übergabe zwischen den Jobs (Kurse wären lesbar)")
                return 1
            stand = nachrechnen.Stand(folder, sid, key)
            if args.gemeinsam:
                transfers, problems = {}, []
                for leg in LEGS:
                    text = (os.environ.get(f"VERGLEICH_{leg.upper()}") or "").strip()
                    if not text:
                        transfers[leg] = None
                        continue
                    try:
                        transfers[leg] = unseal(text, key, sid, leg)
                    except (crypto.ContainerError, ValueError):
                        transfers[leg] = None
                        problems.append(f"{JOB_TEXT[leg]}: Übergabe nicht entschlüsselbar (anderer Stand oder Job)")
                report = combine(stand, sid, transfers, problems)
            else:
                from traktien.providers.http import HttpClient

                # kurze Zeitgrenze, wenige Wiederholungen je Anfrage: Fehler holen die Nachholrunden nach (mit Pause), nicht 4 × 25 s
                http = HttpClient(impersonate="chrome", max_retries=1, timeout=12, min_interval={NASDAQ_HOST: NASDAQ_INTERVAL_S, "query2.finance.yahoo.com": 0.3, **zusatz.HOSTS})
                report = run(stand, sid, http, auswahl=args.auswahl)
                transfer = report.pop("uebergabe", None)
                if args.uebergabe and transfer is not None and args.auswahl in LEGS:
                    sealed = seal(transfer, key, sid, args.auswahl)
                    report["uebergabe"] = {"pruefsumme": transfer["pruefsumme"]}
                    if len(sealed) > TRANSFER_MAX_BYTES:
                        print(f"::error title=Kursursachen{label}: Übergabe::zu groß für eine Ausgabe des Jobs ({len(sealed)} Zeichen)")
                    else:
                        args.uebergabe.write_text(f"{args.auswahl}:{sealed}", encoding="ascii")
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
        if args.gemeinsam:
            return 0 if report["urteil"] == "gerechnet" else 1
        return 0 if report["urteil"] in ("belegt", "keine_abweichungen") else 1
    finally:
        print(f"::notice title=Kursursachen{label}::Dauer {round(time.monotonic() - started)} s")


if __name__ == "__main__":
    try:
        code = main()
    except Exception as exc:  # noqa: BLE001 - Abbruchgrund ohne Inhalte
        print(f"::error title=Kursursachen abgebrochen::{type(exc).__name__}: {str(exc).splitlines()[0][:200] if str(exc) else ''}")
        code = 1
    sys.exit(code)
