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

**Seit 25.10.2026, 09:20 Uhr** (Auftrag vom 25.10.2026, 09:20 Uhr; Prüfskript, App unverändert 1.18.2):

* **Beleglage streng (Punkt 2):** belegt ist eine Ursache nur mit gemeldetem Ereignis – Split passenden Verhältnisses nach dem Tag
  (Stand splitbereinigt, Quelle nicht; bereinigt gleich) bzw. Dividende nach dem Tag bei einem Vergleichskurs gleich dem
  dividendenbereinigten Kurs. Gleicher Kurs wie die letzte Minutenkerze, Abstand unter einer Kursstufe, Umsatz 0 mit dem Kurs des
  Vortags und ein Faktor ohne gemeldeten Split sind **plausible Erklärungen** – die Abweichung bleibt ungeklärt. Getrennt gezählt:
  bestätigte Übereinstimmung, festgestellte Abweichung, belegte Ursache, plausible Erklärung, ohne Erklärung, fehlende
  Prüfmöglichkeit, nicht abgesichert – je Vergleich und **je Aktie und Tag genau einmal** (Nasdaq-Historie und NOCP überschneiden
  sich; maßgeblich ist der abgesicherte NOCP).
* **Zuordnung abgesichert (Punkt 3, ``kurse_absicherung.py``):** Aktie/Gattung über die ISIN (OpenFIGI), Name und Art laut Quelle
  (Wertpapierliste von Nasdaq Trader bzw. Kursmeldung), Handelsplatz, Währung, Handelstag ohne Versatz, Bereinigung, Kursniveau und
  mindestens 10 Tage. Fehlt eine Angabe oder widerspricht sie, ist der Vergleich nicht abgesichert: kein Ersatzkurs, keine
  Bestätigung, zählt nicht als geprüft.
* **OTC-Zeitstempel (Punkt 4):** „lastTradeTime“ ist nicht dokumentiert – der letzte Abschluss bei OTC Markets ist weder
  Vergleichskurs noch zweite Quelle; gezählt werden nur Beobachtungen (``kurse_zusatzquellen.otc_stamp_evidence``).
* **Auslösersuche (Punkt 5):** Teilmengen der ersetzten Aktien nach Größe, jede Größe vollständig, bis Platz 1 wechselt –
  nachweislich die kleinste Menge; reicht das Budget nicht, eine irreduzible Menge mit der Grenze „mindestens k Aktien“. Platz 1
  je Teilmenge schnell aus berichtigten Rängen, gegen die unabhängige Rechnung geprüft; Gegenprobe je Auslöser allein und ohne ihn.
* **Gemeinsame Varianten (Punkt 1):** (b)+(c), (c)+(d), (b)+(c)+(d), (a)+(c), (a)+(c)+(d) mit der Wechselwirkung der Teile
  (erst gemeinsam, aufgehoben, auch einzeln – für Platz 1, Aktien und Reihenfolge der ersten 10 und alle übrigen Ränge) und der
  Quelle je Aktie und Tag (Prüfsumme, Überschneidung).
* **Abdeckung (Punkt 6):** vierter Job „welt“ – alle Aktien außerhalb der US-Auswahl mit Platz unter den ersten 10 gegen CNBC
  (``kurse_welt.py``, Variante d); im Job „gemeinsame Wirkung“ die Abdeckung des ganzen Aktienuniversums nach Börse, Aktien, Tagen
  und Ranglisten.
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
import urllib.parse
from collections import Counter
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "backend"))

import kurse_gegenpruefen as gegen  # noqa: E402 - Nasdaq-/Yahoo-Abruf und Einordnung je Tag
import kurse_absicherung as absicherung  # noqa: E402 - Absicherung der Zuordnung jedes Vergleichs (seit dem 25.10.2026, 09:20 Uhr)
import kurse_zusatzquellen as zusatz  # noqa: E402 - weitere Quellen für US-Aktien ohne Nasdaq-Kurse (seit dem 25.10.2026)
import kurse_welt as welt  # noqa: E402 - CNBC für Aktien außerhalb der US-Auswahl (seit dem 25.10.2026, 09:20 Uhr)
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
GROUP_TEXT = {"erste_10": "erste 10", "erste_20": "Plätze 11–20", "zufall": "Zufallsstichprobe", "welt": "außerhalb der US-Auswahl (unter den ersten 10)"}
ALL_GROUPS = GROUPS + ("welt",)
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
SHARD_TEXT = {"alle": "", "erste10": " (erste 10)", "plaetze11_20": " (Plätze 11–20)", "zufall": " (Zufallsstichprobe)", "erste20": " (erste 20)", "welt": " (außerhalb der US-Auswahl)"}
US_LEGS = ("erste10", "plaetze11_20", "zufall")
WORLD_LEG = "welt"  # seit dem 25.10.2026, 09:20 Uhr (Punkt 6): alle Aktien außerhalb der US-Auswahl mit Platz unter den ersten 10, CNBC
LEGS = US_LEGS + (WORLD_LEG,)  # die Jobs des Workflows (Matrix „auswahl“, gleiche Reihenfolge)
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
    "split",
    "dividendenbereinigung",
    "letzter_abschluss",
    "nasdaq_letzter_abschluss",
    "rundung",
    "kein_handel",
    "split_ohne_ereignis",
    "dividende_ohne_ereignis",
    "abweichung_vom_nocp",
    "ungeklaert",
)
# Seit dem 25.10.2026, 09:20 Uhr (Auftrag Punkt 2: „Gleicher Kurs wie eine Minutenkerze beweist allein keine ausgelassene
# Schlussauktion. Ein Abstand unter einer Kursstufe beweist allein keine Rundungsursache. Auch gemeldeter Umsatz null beweist
# allein keinen ausgebliebenen Handel.“): belegt ist eine Ursache nur, wenn der Mechanismus durch ein gemeldetes Ereignis
# gezeigt ist – ein Split passenden Verhältnisses nach dem Tag (Stand splitbereinigt, Quelle nicht) bzw. eine Dividende nach
# dem Tag bei einem Vergleichskurs gleich dem dividendenbereinigten Kurs. Minutenkerze, Kursstufe und Umsatz null sind nur
# **plausible Erklärungen**; die Abweichung bleibt ungeklärt.
EVIDENCE = {"split", "dividendenbereinigung"}  # Ursache belegt
PLAUSIBLE = {"letzter_abschluss", "nasdaq_letzter_abschluss", "rundung", "kein_handel", "split_ohne_ereignis", "dividende_ohne_ereignis"}
UNEXPLAINED = {"abweichung_vom_nocp", "ungeklaert"}  # ohne Erklärung
MATCH_OFFICIAL = {"stand_ist_nocp"}  # Stand = offizieller Schlusskurs: bestätigte Übereinstimmung, abweichend nur die Nasdaq-Historie
OPEN = PLAUSIBLE | UNEXPLAINED  # Abweichung festgestellt, Ursache ungeklärt (mit oder ohne plausible Erklärung)
CAUSE_TEXT = {
    "stand_ist_nocp": "Stand = offizieller Schlusskurs (NOCP), abweichend nur die Nasdaq-Historie",
    "split": "belegt: Stand splitbereinigt, Vergleichskurs unbereinigt – Faktor = Verhältnis eines gemeldeten Splits nach dem Tag",
    "dividendenbereinigung": "belegt: Vergleichskurs = dividendenbereinigter Kurs, Dividende nach dem Tag gemeldet",
    "letzter_abschluss": "plausibel: Stand = letzte Minutenkerze vor 16:00 Uhr – fehlende Schlussauktion möglich, mit Minutenkerzen nicht belegt",
    "nasdaq_letzter_abschluss": "plausibel: Nasdaq-Historie = letzte Minutenkerze vor 16:00 Uhr – fehlende Schlussauktion möglich, nicht belegt",
    "rundung": "plausibel: Abstand unter einer Kursstufe – Rundung möglich, Rohwerte der Quellen unbekannt",
    "kein_handel": "plausibel: gemeldeter Umsatz 0 und Kurs des Vortags – ausgebliebener Handel möglich, nicht belegt",
    "split_ohne_ereignis": "plausibel: Faktor eines üblichen Split-Verhältnisses, aber kein passender Split nach dem Tag gemeldet",
    "dividende_ohne_ereignis": "plausibel: Vergleichskurs = dividendenbereinigter Kurs, aber keine Dividende nach dem Tag gemeldet",
    "abweichung_vom_nocp": "Befund: Stand ≠ offizieller Schlusskurs (NOCP), Nasdaq-Historie = NOCP – wodurch, ist nicht belegt",
    "ungeklaert": "ohne Erklärung",
}
SHORT_CAUSE = {  # Kurzform in den Zeilen je Aktie (Langform in der Legende des Ergebnisses)
    "stand_ist_nocp": "Stand = NOCP",
    "split": "Split (belegt)",
    "dividendenbereinigung": "Dividende (belegt)",
    "letzter_abschluss": "Stand = letzte Minutenkerze (plausibel)",
    "nasdaq_letzter_abschluss": "Nasdaq = letzte Minutenkerze (plausibel)",
    "rundung": "Kursstufe (plausibel)",
    "kein_handel": "Umsatz 0 (plausibel)",
    "split_ohne_ereignis": "Faktor ohne Split (plausibel)",
    "dividende_ohne_ereignis": "dividendenbereinigt ohne Dividende (plausibel)",
    "abweichung_vom_nocp": "Stand ≠ NOCP (Befund)",
    "ungeklaert": "ohne Erklärung",
    "offizieller_schlusskurs": "Nasdaq = NOCP",  # Läufe bis 1.18.2 (dort als Ursache gezählt)
}
# Warum für einen ungeklärten Tag kein Beleg möglich war – das ist die Grenze der Prüfung, keine Ursache der Abweichung
UNEXPLAINED_TEXT = {
    "nyse_gruppe_ohne_offiziellen_kurs": "Prüfgrenze: Heimatbörse der NYSE-Gruppe oder Cboe – offizieller Schlusskurs in den geprüften Quellen nicht frei verfügbar (NYSE: nur im kostenpflichtigen Produkt „TAQ NYSE Closing Prices“)",
    "nocp_fehlt_am_tag": "Prüfgrenze: Nasdaq-notiert – NOCP für den Tag fehlt",
    "nocp_dritter_wert": "Befund ohne Ursache: Nasdaq-notiert – Stand, Nasdaq-Historie und NOCP drei verschiedene Kurse",
    "nocp_anders": "Befund ohne belegte Ursache: Nasdaq-notiert – Nasdaq-Historie = NOCP, Stand nicht",
    "nocp_nicht_abgesichert": "Prüfgrenze: Nasdaq-notiert – NOCP vorhanden, Zuordnung nicht ausreichend abgesichert",
    "boerse_unbekannt": "Prüfgrenze: Heimatbörse unbekannt (Yahoo ohne Angabe)",
}
CATEGORY_TEXT = {  # die Ergebnisarten (Auftrag 25.10.2026, 09:20 Uhr, Punkt 2) – Tage
    "uebereinstimmung": "bestätigte Übereinstimmung",
    "gleich_nach_split": "davon nach Bereinigung um einen gemeldeten Split",
    "abweichung": "festgestellte Abweichung",
    "belegt": "davon Ursache belegt",
    "plausibel": "davon ungeklärt mit plausibler Erklärung",
    "ohne_erklaerung": "davon ungeklärt ohne Erklärung",
    "stand_ist_nocp": "davon Stand = offizieller Schlusskurs (Abweichung nur der Vergleichsquelle)",
    "ohne_vergleich": "fehlende Prüfmöglichkeit",
    "nicht_abgesichert": "davon Vergleich nicht ausreichend abgesichert",
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
    return {"days": days, "splits": splits, "dividends": dividends, "exchange": meta.get("exchangeName"), "offset": offset,
            "currency": meta.get("currency"), "type": meta.get("instrumentType"), "name": meta.get("longName") or meta.get("shortName")}


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


def has_dollar(payload) -> bool:
    """Nennt die Antwort die Währung? Nasdaq schreibt Kurse als „$12.34“ – nur dann gilt die Währung als angegeben."""
    stack = [payload]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            stack.extend(node.values())
        elif isinstance(node, list):
            stack.extend(node)
        elif isinstance(node, str) and node.strip().startswith("$") and node.strip()[1:2].isdigit():
            return True
    return False


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
    dividends: list[int] | None = None,
    cutoff: int | None = None,
) -> tuple[str, str]:
    """Einordnung eines abweichenden Tags (Name, kurze Begründung ohne Kurse). Seit dem 25.10.2026, 09:20 Uhr (Auftrag Punkt 2):
    **belegt** nur mit gemeldetem Ereignis – Faktor = Verhältnis eines Splits nach dem Tag (der Stand ist splitbereinigt, die
    Quelle nicht; bereinigt sind beide gleich) bzw. Vergleichskurs = dividendenbereinigter Kurs mit Dividende nach dem Tag.
    **Plausibel**, aber nicht belegt: Stand bzw. Nasdaq-Historie = letzte Minutenkerze vor 16:00 Uhr, Abstand unter einer
    Kursstufe, gemeldeter Umsatz 0 mit dem Kurs des Vortags, Faktor ohne gemeldeten Split. Stand = offizieller Schlusskurs
    (NOCP) ist eine bestätigte Übereinstimmung (abweichend ist dann nur die Nasdaq-Historie). Nasdaq-Historie = NOCP und Stand
    nicht ist ein **Befund** („abweichung_vom_nocp“); sonst „ungeklaert“ (ohne Erklärung)."""
    n = nasdaq.get(day) or {}
    y = (yahoo.get("days") or {}).get(day) or {}
    n_close = n.get("close")
    if kind == "faktor":
        factor = zusatz.split_factor(day, yahoo.get("splits") or [], cutoff)
        if n_close is not None and zusatz.adjusted_equal(own, n_close, factor):
            return "split", "Faktor = Verhältnis eines gemeldeten Splits nach dem Tag"
        return "split_ohne_ereignis", "Faktor ohne passenden gemeldeten Split"
    if nocp is not None and day in nocp and same(own, nocp[day]) and not same(n_close, nocp[day]):
        return "stand_ist_nocp", "Stand = NOCP, Nasdaq-Historie ≠ NOCP"
    if n_close is not None and within_display(own, n_close):
        return "rundung", "Stand zwischen zwei Kursstufen, Nasdaq zeigt die Nachbarstufe (plausibel)"
    # Ist die Nasdaq-Historie an dem Tag der offizielle Schlusskurs, erklärt „Nasdaq = letzter Abschluss“ nichts: dann ist der
    # letzte Abschluss zugleich der offizielle Schlusskurs, und offen ist, warum der Stand davon abweicht (Lauf 40158331688)
    nasdaq_is_official = nocp is not None and day in nocp and same(n_close, nocp[day])
    if day in minutes:
        if same(own, minutes[day]) and not same(n_close, minutes[day]):
            return "letzter_abschluss", "Stand = letzte Minutenkerze vor 16:00, Nasdaq anders (plausibel)"
        if same(n_close, minutes[day]) and not same(own, minutes[day]) and not nasdaq_is_official:
            return "nasdaq_letzter_abschluss", "Nasdaq = letzte Minutenkerze vor 16:00, Stand anders (plausibel)"
    volume_y, volume_n = y.get("volume"), n.get("volume")
    if previous_own is not None and own == previous_own and volume_y == 0:
        return "kein_handel", "Yahoo: Umsatz 0, Kurs des Vortags (plausibel)"
    if previous_nasdaq is not None and n_close == previous_nasdaq and volume_n == 0:
        return "kein_handel", "Nasdaq: Umsatz 0, Kurs des Vortags (plausibel)"
    if y.get("adjclose") is not None and same(n_close, y["adjclose"]) and not same(n_close, y.get("close")):
        events = list(yahoo.get("dividends") or []) + list(dividends or [])
        if any(day < x and (cutoff is None or x <= cutoff) for x in events):
            return "dividendenbereinigung", "Nasdaq = adjclose, Dividende nach dem Tag gemeldet"
        return "dividende_ohne_ereignis", "Nasdaq = adjclose, keine Dividende nach dem Tag gemeldet (plausibel)"
    if nocp is not None and day in nocp and same(n_close, nocp[day]) and not same(own, nocp[day]):
        return "abweichung_vom_nocp", "Befund: Nasdaq = NOCP, Stand ≠ NOCP"
    return "ungeklaert", ""


def evidence_class(cause: str) -> str:
    """Belegt, plausibel (ungeklärt mit Erklärung) oder ohne Erklärung (ungeklärt) – für Zählwerte je Aktie und Tag."""
    if cause in EVIDENCE:
        return "belegt"
    if cause in MATCH_OFFICIAL:
        return "stand_ist_nocp"
    return "plausibel" if cause in PLAUSIBLE else "ohne_erklaerung"


def nocp_day_cause(day: int, own: float, nocp_close: float, minutes: dict[int, float]) -> str:
    """Einordnung eines Tags mit Stand ≠ offizieller Schlusskurs (Variante b): plausible Erklärung Kursstufe oder Stand = letzte
    Minutenkerze vor 16:00 Uhr (eine fehlende Schlussauktion wäre möglich – seit dem 25.10.2026, 09:20 Uhr nicht mehr als
    belegt gezählt); sonst „ungeklaert“ (Befund ohne Erklärung)."""
    if within_display(own, nocp_close):
        return "rundung"
    if day in minutes and same(own, minutes[day]) and not same(nocp_close, minutes[day]):
        return "letzter_abschluss"
    return "ungeklaert"


def unexplained_reason(exchange: str | None, nocp: dict[int, float] | None, day: int, cause: str = "ungeklaert", nasdaq_close: float | None = None,
                       nocp_unsecured: bool = False) -> str:
    """Warum ein Tag ungeklärt bleibt – welche Quelle fehlt bzw. welcher Befund vorliegt (``nocp``: nur ein abgesicherter NOCP)."""
    if cause == "abweichung_vom_nocp" or (nocp is not None and day in nocp and nasdaq_close is not None and same(nasdaq_close, nocp[day])):
        return "nocp_anders"
    if exchange in NASDAQ_LISTED:
        if nocp_unsecured:
            return "nocp_nicht_abgesichert"
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


def venue_label(yahoo_exchange: str | None) -> str:
    """Börse der Kurse des Stands für die Legende der Buchstaben (ohne Kürzel): Nasdaq, NYSE-Gruppe, Cboe, OTC oder „andere“ – bis
    zum Lauf 40181869022 hieß jede US-Aktie ohne Nasdaq-Kurse, die nicht im OTC-Handel notiert, nur „andere“."""
    if zusatz.stand_venue(yahoo_exchange) == "otc":
        return "OTC"
    if yahoo_exchange in NASDAQ_LISTED:
        return "Nasdaq"
    return NYSE_GROUP.get(yahoo_exchange or "", "andere")


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
            out["nasdaq_status"], out["nasdaq"], out["nasdaq_dollar"] = status, rows, bool(rows) and has_dollar(payload)
            if rows or status != "ok":
                break
        elif rows:
            out.update(nasdaq_symbol=nasdaq_symbol, nasdaq=rows, nasdaq_variante=k, nasdaq_dollar=has_dollar(payload))
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
                out["nocp"], out["nocp_fields"], out["nocp_dollar"] = rows, fields, has_dollar(payload)
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
    return {
        "isin": str(instruments["isin"][i]),
        "namen": [str(n) for n in names if n],
        "waehrung": column("currency") or "",
        "einheit": column("price_unit") or column("currency") or "",
        "boerse": column("exchange_key") or "",
        "typ": column("type") or "",
        "identitaet": column("identity") or "",
    }


def alternative_comparison(http, symbol: str, own: dict[int, float], meta: dict, yahoo: dict, start_day: int, cutoff: int, figi_entry: dict | None = None) -> dict:
    """Weitere Quellen für eine Aktie ohne Nasdaq-Kurse: alle Quellen abfragen, je Quelle die Prüfungen von ``zusatz.check`` und
    die strenge Absicherung der Zuordnung (``absicherung.strict_source``, seit dem 25.10.2026, 09:20 Uhr: Aktie über die ISIN,
    Name der Quelle, Art, Handelsplatz, Währung, Handelstag ohne Versatz, Bereinigung, Kursniveau, Tage – fehlende Angaben gelten
    nicht als bestanden). Verglichen wird mit der ersten abgesicherten Quelle; weitere abgesicherte Quellen sind zweite Quelle an
    den abweichenden Tagen. Der letzte Abschluss bei OTC Markets ist **keine** zweite Quelle mehr: Die Bedeutung von
    „lastTradeTime“ ist nicht belegt, die Tageszuordnung bleibt offen – gezählt werden nur Beobachtungen
    (``zusatz.otc_stamp_evidence``). Rückgabe ohne Kürzel und Namen."""
    checks, secured, fetched_by, strict = [], [], {}, []
    for source in zusatz.SOURCES:
        fetched = zusatz.fetch_source(http, source, symbol, start_day, cutoff)
        fetched_by[source] = fetched
        result = zusatz.check(fetched, own, meta, yahoo)
        result["status"] = dict(fetched["status"])
        result["felder"] = list(fetched.get("felder") or [])
        result["felder_kurs"] = list(fetched.get("felder_kurs") or [])
        checks.append(result)
        if not fetched["rows"]:
            continue
        sec = absicherung.strict_source(result, fetched, own, yahoo, figi_entry, symbol, meta.get("boerse"), cutoff, names=meta.get("namen") or [])
        sec["technisch_vergleichbar"] = bool(result.get("vergleichbar"))
        strict.append(sec)
        if sec["abgesichert"]:
            secured.append((source, fetched, result))
    otc = fetched_by.get("otc_markets") or {}
    out = {
        "checks": checks,
        "absicherung": strict,
        "quelle": None,
        "rows": {},
        "tage": {},
        "zweite": {},
        "pruefung": {},
        "otc_beobachtung": zusatz.otc_stamp_evidence(otc, own, yahoo, start_day, cutoff),
        "otc_letzter": "mit_kursmeldung" if otc.get("letzter") else ("kursmeldung_ohne_abschluss" if (otc.get("status") or {}).get("kurs") == "ok" else "ohne_kursmeldung"),
        "mit_kursen": bool(strict),
        "mit_kursen_tage": max((int(c.get("gemeinsame_tage") or 0) for c in checks if "identitaet" in c), default=0),
    }
    if not secured:
        return out
    source, fetched, result = secured[0]
    days = zusatz.compare(own, fetched["rows"], result["datum_versatz"], yahoo, within_display, splits=yahoo.get("splits") or [], cutoff=cutoff)
    second: dict[int, str] = {}
    for d, (kind, alt_close, _) in days.items():
        if kind in ("gleich", "gleich_nach_split"):
            continue
        for _, other, other_result in secured[1:]:
            value = (other["rows"].get(d + other_result["datum_versatz"]) or {}).get("close")
            if value is None:
                continue
            second[d] = "gleich_stand" if same(own[d], value) else ("gleich_erster_quelle" if same(alt_close, value) else "dritter_kurs")
            break
    out.update(quelle=source, rows={d: fetched["rows"][d + result["datum_versatz"]] for d in own if (d + result["datum_versatz"]) in fetched["rows"]}, tage=days, zweite=second, pruefung=result)
    return out


def consolidate_days(own: dict[int, float], a_class: dict[int, str], b_class: dict[int, str]) -> Counter:
    """Je Aktie und Tag genau eine Einordnung (Auftrag vom 25.10.2026, 09:20 Uhr, Punkt 2: überlappende Fälle verschiedener
    Vergleiche nicht als unabhängige Fälle zählen). Maßgeblich ist der offizielle Schlusskurs (NOCP), wo er abgesichert
    vorliegt, sonst die Nasdaq-Historie: „uebereinstimmung“ (auch Stand = NOCP bei abweichender Nasdaq-Historie), „belegt“,
    „plausibel“, „ohne_erklaerung“ oder „ohne_vergleich“. Dazu die Überschneidung: Tage, an denen beide Vergleiche bzw. nur einer
    abweichen."""
    out: Counter = Counter()
    for day in own:
        a, b = a_class.get(day), b_class.get(day)
        primary = b if b is not None else a
        if primary is None:
            out["ohne_vergleich"] += 1
            continue
        out["uebereinstimmung" if primary in ("gleich", "stand_ist_nocp") else primary] += 1
        out["verglichen"] += 1
        deviates_a = a is not None and a != "gleich"
        deviates_b = b is not None and b != "gleich"
        if deviates_a and deviates_b:
            out["abweichend_in_beiden"] += 1
        elif deviates_a:
            out["abweichend_nur_nasdaq_historie"] += 1
        elif deviates_b:
            out["abweichend_nur_nocp"] += 1
    return out


def deviating_days(own: dict[int, float], nasdaq: dict[int, dict] | None, nocp: dict[int, float] | None) -> int:
    """Zahl der Tage, an denen der Stand von der Nasdaq-Historie bzw. vom NOCP abweicht (ohne Nachbartage) – nur, um zu
    entscheiden, ob Minutenkurse für die Abstimmung gebraucht werden."""
    count = 0
    for day, close in own.items():
        if nasdaq is not None and day in nasdaq and gegen.classify(close, nasdaq[day]["close"], []) != "gleich":
            count += 1
        elif nocp is not None and day in nocp and gegen.classify(close, nocp[day], []) != "gleich":
            count += 1
    return count


def diagnose_unsecured(own: dict[int, float], nasdaq: dict[int, dict] | None, nocp: dict[int, float] | None, yahoo: dict, minutes: dict[int, float],
                       start_day: int, cutoff: int, nasdaq_for_notes: dict[int, dict] | None = None) -> dict[str, Counter]:
    """Abstimmung mit den Zählungen vor der Absicherung (Auftrag vom 25.10.2026, 09:20 Uhr, Punkt 2: die früher als belegt
    gezählten Fälle überprüfen). Ein nicht ausreichend abgesicherter Vergleich liefert weder Bestätigung noch Ursache noch
    Ersatzkurs – er wird hier nur gezählt: verglichene und abweichende Tage und die Einordnung, die ein Tag in einem abgesicherten
    Vergleich bekäme (wie in den Läufen vor der Absicherung, in denen es keine Absicherung gab). ``nasdaq``/``nocp``: nur die
    nicht abgesicherten Vergleiche; ``nasdaq_for_notes``: die Nasdaq-Historie für die Lage am NOCP-Tag."""
    out: dict[str, Counter] = {}
    if nasdaq is not None:
        c: Counter = Counter()
        fresh = sorted(k for k in nasdaq if start_day <= k <= cutoff)
        ordered = sorted(own)
        for day, close in own.items():
            if day not in nasdaq or day not in fresh:
                continue
            k = fresh.index(day)
            neighbours = [nasdaq[fresh[j]]["close"] for j in (k - 1, k + 1) if 0 <= j < len(fresh)]
            kind = gegen.classify(close, nasdaq[day]["close"], neighbours)
            c["tage"] += 1
            if kind == "gleich":
                c["gleich"] += 1
                continue
            j = ordered.index(day)
            previous = own[ordered[j - 1]] if j > 0 else None
            previous_n = nasdaq[fresh[k - 1]]["close"] if k > 0 else None
            cause, _ = day_cause(day, close, nasdaq, yahoo, nocp, minutes, previous, previous_n, kind, [], cutoff)
            c["abweichend"] += 1
            c[f"ursache_{cause}"] += 1
        out["nasdaq"] = c
    if nocp is not None:
        c = Counter()
        notes_from = nasdaq_for_notes if nasdaq_for_notes is not None else (nasdaq or {})
        for day, close in own.items():
            if day not in nocp:
                continue
            c["tage"] += 1
            kind = gegen.classify(close, nocp[day], [])
            if kind == "gleich":
                c["gleich"] += 1
                continue
            c["abweichend"] += 1
            if kind == "faktor":
                split = zusatz.adjusted_equal(close, nocp[day], zusatz.split_factor(day, yahoo.get("splits") or [], cutoff))
                c["ursache_split" if split else "ursache_split_ohne_ereignis"] += 1
                continue
            cause_b = nocp_day_cause(day, close, nocp[day], minutes)
            if cause_b in PLAUSIBLE | EVIDENCE:
                c[f"ursache_{cause_b}"] += 1
            else:
                n_close = (notes_from.get(day) or {}).get("close")
                c[f"ursache_befund_{nocp_note(close, n_close, nocp[day])}"] += 1
        out["nocp"] = c
    return out


def run(stand: nachrechnen.Stand, sid: str, http, pause=time.sleep, now: float | None = None, budget_s: float = FETCH_BUDGET_S, clock=time.monotonic, auswahl: str = "alle",
        zusatzquellen: bool = True, figi_lookup=None, listing: tuple[str, dict] | None = None) -> dict:
    """Ein Prüfjob: Abruf, Absicherung, Einordnung je Tag und Wirkung auf die Ranglisten. ``figi_lookup`` (ISINs → Notierungen
    laut OpenFIGI) und ``listing`` (Status, Wertpapierliste) sind für Tests ersetzbar; sonst live abgefragt."""
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
    # Absicherung der Zuordnung (seit dem 25.10.2026, 09:20 Uhr, Punkt 3): je Job einmal die Wertpapierliste (Name, Börse der
    # Notierung, Art) und ISIN → Kürzel laut OpenFIGI; ein Vergleich, der nicht jede Prüfung besteht, liefert weder Ersatzkurse
    # noch bestätigte Übereinstimmungen
    listing_status, listing_rows = listing if listing is not None else absicherung.fetch_listing(http)
    isins = sorted({str(instruments["isin"][i]) for i in chosen if i in bases})
    figi = (figi_lookup or absicherung.figi_lookup)(isins) if isins else {}
    sec_checks: list[dict] = []  # Absicherung je Vergleich (ohne Namen und Kürzel)
    unsecured: dict[int, str] = {}  # Aktien mit Vergleichskursen, deren Zuordnung nicht abgesichert ist → nicht geprüft
    unsecured_days: Counter = Counter()  # Tage dieser Vergleiche (je Quelle)
    stock_days: Counter = Counter()  # je Aktie und Tag genau eine Einordnung (Nasdaq-Historie und NOCP zusammen)
    stock_days_c: Counter = Counter()  # ebenso gegen die Zusatzquellen (andere Aktien als Nasdaq)
    otc_seen: Counter = Counter()  # Beobachtungen zu „lastTradeTime“ bei OTC Markets (keine Zuordnung)
    # nicht abgesicherte Vergleiche: nur gezählt, mit der Einordnung, die ein Tag in einem abgesicherten Vergleich bekäme – für die
    # Abstimmung mit den Zählungen der Läufe vor der Absicherung (Auftrag Punkt 2); weder Bestätigung noch Ursache noch Ersatzkurs
    reconcile: dict[str, Counter] = {"nasdaq": Counter(), "nocp": Counter()}
    gaps: dict[int, dict] = {}  # Lücken je Aktie (ohne Vergleichskurse, nicht abgesichert): Börse, Kursbereich, Grund – für die Legende

    def gap(i: int, own_prices: dict[int, float], yahoo_exchange: str | None, reason: str, failed: str = "", detail: str = "") -> None:
        gaps[i] = {"boerse": venue_label(yahoo_exchange), "kursbereich": price_range({d: {"close": v} for d, v in own_prices.items()}) if own_prices else "–",
                   "grund": reason, "pruefungen": failed, "tage_stand": len(own_prices), "befund": detail}

    def reconcile_unsecured(own_prices: dict[int, float], nasdaq_rows, nocp_rows, yahoo: dict, minutes: dict[int, float] | None, symbol: str, nasdaq_symbol: str,
                            notes_rows: dict[int, dict]) -> None:
        if minutes is None:
            minutes = {}
            if deviating_days(own_prices, nasdaq_rows, nocp_rows) and clock() - started <= budget_s + DETAIL_EXTRA_S:
                extra = fetch_details(http, symbol, nasdaq_symbol, now, dividends=False)  # nur Minutenkerzen (Yahoo), kein Kontingent bei Nasdaq
                for name, status in extra["status"].items():
                    detail_status[f"abstimmung_{name}_{status}"] += 1
                minutes = extra["minutes"]
        for name, c in diagnose_unsecured(own_prices, nasdaq_rows, nocp_rows, yahoo, minutes, start_day, cutoff, nasdaq_for_notes=notes_rows).items():
            reconcile[name].update(c)
            reconcile[name]["aktien"] += 1

    for i in chosen:
        base = bases.get(i)
        if base is None:
            continue
        symbol = str(instruments["symbol"][i])
        meta = stand_meta(instruments, i)
        figi_entry = figi.get(meta["isin"])
        if not base["nasdaq"]:
            no_price_symbols[f"{len(symbol)} Zeichen"] += 1
            yahoo = base.get("yahoo") or {"days": {}}
            no_price_exchange[yahoo.get("exchange") or "ohne_angabe"] += 1
            own = own_series(stand, instruments, i, start_day, cutoff)
            if not own:
                no_prices[i] = "stand_ohne_kurse_im_zeitraum"
                gap(i, own, yahoo.get("exchange"), no_prices[i])
                continue
            if not zusatzquellen:
                no_prices[i] = "nasdaq_ohne_kurse"
                gap(i, own, yahoo.get("exchange"), no_prices[i])
                continue
            alt = alternative_comparison(http, symbol, own, meta, yahoo, start_day, cutoff, figi_entry)
            alt_checks += alt["checks"]
            sec_checks += alt["absicherung"]
            alt_days[f"otc_kursmeldung_{alt['otc_letzter']}"] += 1
            for name, value in (alt.get("otc_beobachtung") or {}).items():
                otc_seen[f"{name}_{value:02d}" if isinstance(value, int) else f"{name}_{value}"] += 1
            if alt["quelle"] is None:
                if alt["mit_kursen"]:
                    # Kurse vorhanden, aber keine Quelle abgesichert: zählt nicht als geprüft (keine Ersatzkurse, keine Bestätigung)
                    unsecured[i] = "zusatzquelle"
                    unsecured_days["zusatzquelle"] += alt["mit_kursen_tage"]
                    failed = sorted({r for s in alt["absicherung"] if not s.get("abgesichert") for r in (s.get("grund") or "").split(",") if r})
                    detail = " | ".join(f"{zusatz.SOURCE_TEXT.get(s.get('quelle'), s.get('quelle'))}: {absicherung.failure_details(s, figi_entry, meta['boerse'])}"
                                        for s in alt["absicherung"] if not s.get("abgesichert"))
                    gap(i, own, yahoo.get("exchange"), "zusatzquelle_nicht_abgesichert", ",".join(failed), detail)
                else:
                    no_prices[i] = "nasdaq_ohne_kurse"
                    gap(i, own, yahoo.get("exchange"), "weder_nasdaq_noch_zusatzquelle")
                continue
            alt_compared[i] = alt["quelle"]
            rows = alt["rows"]
            info[i] = {"boerse": venue_label(yahoo.get("exchange")), "kursbereich": price_range(rows), "quelle": alt["quelle"]}
            split_days_c = [d for d, v in alt["tage"].items() if v[0] == "gleich_nach_split"]
            deviating_c = {d: v for d, v in alt["tage"].items() if v[0] not in ("gleich", "gleich_nach_split")}
            equal_c = len(alt["tage"]) - len(deviating_c) - len(split_days_c)
            alt_days["gleich"] += equal_c
            alt_days["abweichend_split_belegt"] += len(split_days_c)
            alt_days["nur_im_stand"] += alt["pruefung"].get("nur_im_stand", 0)
            alt_days["nur_im_stand_ohne_umsatz"] += alt["pruefung"].get("nur_im_stand_ohne_umsatz", 0)
            stock_days_c["uebereinstimmung"] += equal_c
            stock_days_c["belegt"] += len(split_days_c)
            stock_days_c["verglichen"] += len(alt["tage"])
            stock_days_c["ohne_vergleich"] += sum(1 for d in own if d not in alt["tage"])
            per_stock = Counter()
            unit = zusatz.source_unit(r["close"] for r in rows.values())
            for d, (kind, alt_close, cause) in deviating_c.items():
                alt_days["abweichend"] += 1
                alt_days[f"ursache_{cause}"] += 1
                stock_days_c[evidence_class(cause)] += 1
                for name in zusatz.pattern(own[d], alt_close, (yahoo["days"].get(d) or {}).get("volume"), (rows.get(d) or {}).get("volume"), unit):
                    alt_patterns[name] += 1
                alt_days[f"zweite_quelle_{alt['zweite'].get(d, 'keine')}"] += 1
                per_stock[cause] += 1
                days_c.setdefault(i, {})[d] = (round(100 * (own[d] / alt_close - 1), 3), cause)
                repl["c"].setdefault(i, {})[d] = alt_close
            if split_days_c:
                per_stock["split"] += len(split_days_c)
            info[i].update(abweichend=len(deviating_c), nocp_ungleich=0, tage_stand=len(own), tage_verglichen=len(alt["tage"]))
            if deviating_c:
                substituted_alt[i] = substitution(own, repl["c"][i])
            if deviating_c or split_days_c:
                alt_stocks.append({
                    "idx": i, "top10": int(top10.get(i, 0)), "platz1": int(first.get(i, 0)), "kursbereich": info[i]["kursbereich"], "boerse": info[i]["boerse"],
                    "quelle": alt["quelle"], "abweichend": len(deviating_c) + len(split_days_c),
                    "groesste_abweichung_pct": round(100 * max([abs(own[d] / v[1] - 1) for d, v in deviating_c.items()] or [0.0]), 2), "ursachen": dict(per_stock),
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
        # Absicherung: Nasdaq-Historie und offizieller Schlusskurs getrennt (eigene Kursfolge, gleiche Wertpapierangaben)
        source_symbol = urllib.parse.unquote(base["nasdaq_symbol"])
        sec_a = absicherung.secure_nasdaq(listing_rows, listing_status, figi_entry, symbol, meta, yahoo, own, nasdaq, bool(base.get("nasdaq_dollar")), cutoff,
                                          source_symbol=source_symbol)
        sec_checks.append(sec_a)
        sec_b = None
        if nocp is not None:
            sec_b = absicherung.secure_nasdaq(listing_rows, listing_status, figi_entry, symbol, meta, yahoo, own, {d: {"close": v} for d, v in nocp.items()},
                                              bool(base.get("nocp_dollar") or base.get("nasdaq_dollar")), cutoff, official=True, source_symbol=source_symbol)
            sec_checks.append(sec_b)
        use_a = bool(sec_a["abgesichert"])
        use_b = bool(sec_b and sec_b["abgesichert"])
        if not use_a:
            unsecured_days["nasdaq"] += sum(1 for d in own if d in nasdaq)
        if nocp is not None and not use_b:
            unsecured_days["nocp"] += sum(1 for d in own if d in nocp)
        if not use_a and not use_b:
            unsecured[i] = "nasdaq"
            failed = sorted({r for s in (sec_a, sec_b) if s for r in (s.get("grund") or "").split(",") if r})
            details = list(dict.fromkeys(x for s in (sec_a, sec_b) if s for x in absicherung.failure_details(s, figi_entry, meta["boerse"]).split("; ") if x))
            gap(i, own, yahoo.get("exchange"), "nasdaq_nicht_abgesichert", ",".join(failed), "; ".join(details))
            reconcile_unsecured(own, nasdaq, nocp, yahoo, None, symbol, base["nasdaq_symbol"], nasdaq)
            continue
        compared.add(i)
        nocp_state[i] = "mit_nocp" if use_b else ("nocp_nicht_abgesichert" if nocp is not None else ("nasdaq_ohne_nocp" if exchange in NASDAQ_LISTED else "nicht_nasdaq_notiert"))
        info[i] = {"boerse": "Nasdaq" if exchange in NASDAQ_LISTED else NYSE_GROUP.get(exchange, "andere"), "kursbereich": price_range(nasdaq),
                   "nasdaq_abgesichert": use_a, "nocp_abgesichert": use_b}
        fresh_days = sorted(k for k in nasdaq if start_day <= k <= cutoff)
        if use_a:
            for day in fresh_days:
                if day not in own and min(own) <= day <= max(own):
                    only["nur_bei_nasdaq"] += 1
                    if (yahoo["days"].get(day) or {}).get("close") is not None:
                        only["nur_bei_nasdaq_yahoo_mit_kurs"] += 1
        # offizieller Schlusskurs an allen Tagen (Nasdaq-notiert, Zuordnung abgesichert)
        nocp_wrong: dict[int, float] = {}
        notes: dict[int, tuple[float, str]] = {}
        b_class: dict[int, str] = {}
        days_without_nocp += sum(1 for day in own if not use_b or day not in nocp)
        if use_b:
            nocp_compare["aktien"] += 1
            for day, close in own.items():
                if day not in nocp:
                    continue
                nocp_compare["tage"] += 1
                kind_nocp = gegen.classify(close, nocp[day], [])
                if kind_nocp == "gleich":
                    nocp_compare["stand_gleich"] += 1
                    b_class[day] = "gleich"
                elif kind_nocp == "faktor":
                    # NOCP unbereinigt, Stand splitbereinigt: belegt nur mit gemeldetem Split passenden Verhältnisses nach dem Tag
                    # (sonst wäre die Absicherung an der Bereinigung gescheitert) – nicht ersetzt
                    if zusatz.adjusted_equal(close, nocp[day], zusatz.split_factor(day, yahoo.get("splits") or [], cutoff)):
                        nocp_compare["faktor_split"] += 1
                        b_class[day] = "belegt"
                    else:
                        nocp_compare["faktor_ohne_split"] += 1
                        b_class[day] = "plausibel"
                else:
                    nocp_compare["stand_ungleich"] += 1
                    nocp_wrong[day] = nocp[day]
                    notes[day] = (round(100 * (close / nocp[day] - 1), 3), nocp_note(close, nasdaq[day]["close"] if day in nasdaq else None, nocp[day]))
                if day in nasdaq:
                    nocp_compare["nasdaq_historie_gleich" if same(nasdaq[day]["close"], nocp[day]) else "nasdaq_historie_ungleich"] += 1
        deviating: list[tuple[int, str]] = []
        a_class: dict[int, str] = {}
        if use_a:
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
                else:
                    a_class[day] = "gleich"
        if nocp_wrong:
            repl["b"][i] = dict(nocp_wrong)
            substituted_nocp[i] = substitution(own, nocp_wrong)
        info[i].update(abweichend=len(deviating), nocp_ungleich=len(nocp_wrong))
        minutes: dict[int, float] = {}
        nasdaq_dividends: list[int] = []
        details: dict = {"status": {}}
        if deviating or nocp_wrong:
            if clock() - started > budget_s + DETAIL_EXTRA_S:
                # Zeitbudget auch für Minutenkurse und Dividenden erschöpft: Ursachen dieser Aktie nur mit NOCP und Tageskursen
                details = {"status": {"minuten": "zeitbudget", "minuten_2m": "zeitbudget", **({"dividenden": "zeitbudget"} if deviating else {})}, "minutes": {}, "dividends": []}
            else:
                # Dividenden bei Nasdaq nur bei Abweichung von der Nasdaq-Historie (Kontingent der Anfragen je Rechner)
                details = fetch_details(http, symbol, base["nasdaq_symbol"], now, dividends=bool(deviating))
            for name, status in details["status"].items():
                detail_status[f"{name}_{status}"] += 1
            minutes, nasdaq_dividends = details["minutes"], details["dividends"]
        # der nicht abgesicherte Teil (nur Nasdaq-Historie oder nur NOCP abgesichert): nur gezählt – Abstimmung mit früheren Läufen
        if not use_a or (nocp is not None and not use_b):
            reconcile_unsecured(own, None if use_a else nasdaq, nocp if (nocp is not None and not use_b) else None, yahoo,
                                minutes if (deviating or nocp_wrong) else None, symbol, base["nasdaq_symbol"], nasdaq)
        # (b) jeder Tag mit Stand ≠ NOCP: plausible Erklärung (Kursstufe, letzte Minutenkerze) oder Befund (Lage der Nasdaq-Historie)
        for day, (pct, note) in notes.items():
            cause_b = nocp_day_cause(day, own[day], nocp_wrong[day], minutes)
            nocp_causes[cause_b if cause_b in PLAUSIBLE | EVIDENCE else f"befund_{note}"] += 1
            days_b.setdefault(i, {})[day] = (pct, cause_b if cause_b in PLAUSIBLE | EVIDENCE else note)
            b_class[day] = evidence_class(cause_b)
        window_events = {
            "yahoo_dividende": sum(1 for x in yahoo.get("dividends") or [] if start_day <= x <= cutoff),
            "yahoo_split": sum(1 for x, _ in yahoo.get("splits") or [] if start_day <= x <= cutoff),
            "nasdaq_dividende": sum(1 for x in nasdaq_dividends if start_day <= x <= cutoff),
        }
        per_stock: Counter = Counter()
        ordered = sorted(own)
        for day, kind in deviating:
            k = ordered.index(day)
            previous = own[ordered[k - 1]] if k > 0 else None
            m = fresh_days.index(day)
            previous_n = nasdaq[fresh_days[m - 1]]["close"] if m > 0 else None
            cause, _ = day_cause(day, own[day], nasdaq, yahoo, nocp if use_b else None, minutes, previous, previous_n, kind, nasdaq_dividends, cutoff)
            days_a.setdefault(i, {})[day] = (round(100 * (own[day] / nasdaq[day]["close"] - 1), 3), cause)
            a_class[day] = evidence_class(cause)
            per_stock[cause] += 1
            causes[cause] += 1
            kinds[kind] += 1
            days_total["abweichend"] += 1
            if day in minutes:
                days_total["abweichend_mit_minutenkursen"] += 1
            if use_b and day in nocp:
                days_total["abweichend_mit_nocp"] += 1
            if cause in OPEN:
                n_close = nasdaq[day]["close"]
                unexplained[unexplained_reason(yahoo.get("exchange"), nocp if use_b else None, day, cause, n_close, nocp is not None and not use_b)] += 1
                patterns[f"stufen_{tick_bucket(own[day], n_close)}"] += 1
                patterns["stand_hoeher" if own[day] > n_close else "stand_niedriger"] += 1
                patterns["stand_auf_kursstufe" if on_grid(own[day], step(n_close)) else "stand_zwischen_kursstufen"] += 1
                patterns[f"umsatz_{volume_bucket(nasdaq[day].get('volume'), (yahoo['days'].get(day) or {}).get('volume'))}"] += 1
                patterns["mit_minutenkurs_keiner_gleich" if day in minutes else "ohne_minutenkurs"] += 1
                patterns[f"art_{kind}"] += 1
        # je Aktie und Tag genau einmal (Nasdaq-Historie und NOCP überschneiden sich – nicht als unabhängige Fälle zählen)
        stock_days.update(consolidate_days(own, a_class, b_class))
        info[i].update(tage_stand=len(own), tage_verglichen=len(set(a_class) | set(b_class)))
        if not deviating and not nocp_wrong:
            continue
        for name, count in window_events.items():
            if count and deviating:
                events[name] += 1
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
                        "nocp_belegt": sum(1 for day in nocp_wrong if b_class.get(day) == "belegt"),
                        "nocp_plausibel": sum(1 for day in nocp_wrong if b_class.get(day) == "plausibel"),
                        "groesste_abweichung_nocp_pct": round(100 * max(abs(own[day] / nocp_wrong[day] - 1) for day in nocp_wrong), 2),
                    }
                )
            continue
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
                "nocp_abrufbar": use_b,
                "nocp_nicht_abgesichert": nocp is not None and not use_b,
                "nocp_tage_ungleich": len(nocp_wrong),
                "minutenkurse_tage": len(minutes),
                "ereignisse": window_events,
                "dividenden_nasdaq": details["status"].get("dividenden", "–"),
            }
        )
        # Variante (a): an den abweichenden Tagen der Nasdaq-Kurs – ohne die Tage, die um einen gemeldeten Split bereinigt gleich
        # sind (der unbereinigte Kurs wäre ein falscher Ersatz für den splitbereinigten Stand)
        replaced_a = {day: nasdaq[day]["close"] for day, _ in deviating if days_a[i][day][1] != "split"}
        if replaced_a:
            repl["a"][i] = replaced_a
            substituted[i] = substitution(own, replaced_a)
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
        if i in unsecured:
            return "nicht_abgesichert"
        if i in no_prices:
            return "ohne_vergleichskurse"
        if i in other_set:
            return "anderer_job"
        return "keine_us_aktie" if i not in us_set else "nicht_ausgewaehlt"

    names = Lettering([s["idx"] for s in ordered], state_of, info, top10, gaps=gaps, first_places=first)
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
        elif i in unsecured:
            coverage["nicht_abgesichert"] += 1
        elif i in alt_compared:
            coverage["verglichen_zusatzquelle"] += 1
            s = alt_idx.get(i)
            coverage["zusatzquelle_ohne_abweichung" if s is None else ("zusatzquelle_mit_ungeklaerten_tagen" if any(s["ursachen"].get(k) for k in OPEN) else "zusatzquelle_alle_belegt")] += 1
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
    # Lücken je Aktie (ohne Vergleichskurse, nicht abgesichert) mit Buchstaben – zuletzt vergeben, die übrigen Buchstaben bleiben gleich
    for i in sorted(gaps, key=lambda j: (-top10.get(j, 0), j)):
        names(i)
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
            if not info[i].get("nasdaq_abgesichert", True):
                by_group_coverage[g]["nasdaq_historie_nicht_abgesichert"] += 1
        elif i in alt_compared:
            by_group_coverage[g]["verglichen"] += 1
            by_group_coverage[g][f"verglichen_{alt_compared[i]}"] += 1
        elif i in unsecured:
            by_group_coverage[g]["nicht_abgesichert"] += 1
            by_group_coverage[g][f"nicht_abgesichert_{unsecured[i]}"] += 1
        else:
            by_group_coverage[g]["keine_vergleichskurse"] += 1
            by_group_coverage[g][f"keine_vergleichskurse_{no_prices.get(i, 'unbekannt')}"] += 1
    intervals = getattr(http, "min_interval", None)
    unsecured_nasdaq = sum(1 for i in unsecured.values() if i == "nasdaq")
    unsecured_alt = sum(1 for i in unsecured.values() if i == "zusatzquelle")
    nocp_plausible = sum(v for k, v in nocp_causes.items() if k in PLAUSIBLE)
    nocp_open = sum(v for k, v in nocp_causes.items() if k not in EVIDENCE and k not in PLAUSIBLE)
    without_nasdaq = len(no_prices) + len(alt_compared) + unsecured_alt  # ohne Nasdaq-Kurse (auch ohne Kurse im Stand)
    nocp_of = Counter(nocp_state.get(i) for i in compared)
    unsecured_nasdaq_nocp = sum(1 for i, why in unsecured.items() if why == "nasdaq" and bases[i].get("nocp") is not None)
    # Aufschlüsselung der fehlenden Prüfmöglichkeit (seit dem 25.10.2026, 11:45 Uhr): bis dahin hieß es bei allen Aktien ohne
    # abgesicherten NOCP „nicht Nasdaq-notiert“, auch bei Aktien ohne Nasdaq-Kurse oder mit nicht abgesicherter Zuordnung
    categories = {
        "nasdaq_historie": {
            "uebereinstimmung": days_total.get("verglichen", 0) - days_total.get("abweichend", 0),
            "abweichung": days_total.get("abweichend", 0),
            "belegt": sum(causes.get(k, 0) for k in EVIDENCE),
            "stand_ist_nocp": sum(causes.get(k, 0) for k in MATCH_OFFICIAL),
            "plausibel": sum(causes.get(k, 0) for k in PLAUSIBLE),
            "ohne_erklaerung": sum(causes.get(k, 0) for k in UNEXPLAINED),
            "ohne_vergleich_aktien": len(no_prices) + len(alt_compared) + len(unsecured) + sum(1 for i in compared if not info[i].get("nasdaq_abgesichert", True)),
            "ohne_vergleich_ohne_kurse": without_nasdaq,
            "ohne_vergleich_tage": only.get("nur_im_stand", 0),
            "nicht_abgesichert_aktien": unsecured_nasdaq + sum(1 for i in compared if not info[i].get("nasdaq_abgesichert", True)),
            "nicht_abgesichert_tage": unsecured_days.get("nasdaq", 0),
        },
        "offizieller_schlusskurs": {
            "uebereinstimmung": nocp_compare.get("stand_gleich", 0),
            "abweichung": nocp_compare.get("stand_ungleich", 0) + nocp_compare.get("faktor_split", 0) + nocp_compare.get("faktor_ohne_split", 0),
            "belegt": nocp_compare.get("faktor_split", 0),
            "plausibel": nocp_plausible + nocp_compare.get("faktor_ohne_split", 0),
            "ohne_erklaerung": nocp_open,
            "ohne_vergleich_aktien": sum(1 for i in compared if nocp_state.get(i) != "mit_nocp") + len(no_prices) + len(alt_compared) + len(unsecured),
            "ohne_vergleich_nicht_nasdaq_notiert": nocp_of.get("nicht_nasdaq_notiert", 0),
            "ohne_vergleich_nasdaq_ohne_nocp": nocp_of.get("nasdaq_ohne_nocp", 0),
            "ohne_vergleich_ohne_kurse": without_nasdaq,
            "ohne_vergleich_nasdaq_nicht_abgesichert_ohne_nocp": unsecured_nasdaq - unsecured_nasdaq_nocp,
            "ohne_vergleich_tage": days_without_nocp,
            "nicht_abgesichert_aktien": sum(1 for i in compared if nocp_state.get(i) == "nocp_nicht_abgesichert") + sum(1 for i, why in unsecured.items() if why == "nasdaq" and bases[i].get("nocp") is not None),
            "nicht_abgesichert_tage": unsecured_days.get("nocp", 0),
        },
        "zusatzquellen": {
            "uebereinstimmung": alt_days.get("gleich", 0),
            "abweichung": alt_days.get("abweichend", 0) + alt_days.get("abweichend_split_belegt", 0),
            "belegt": alt_days.get("abweichend_split_belegt", 0) + sum(v for k, v in alt_days.items() if k.startswith("ursache_") and k[len("ursache_"):] in EVIDENCE),
            "plausibel": sum(v for k, v in alt_days.items() if k.startswith("ursache_") and k[len("ursache_"):] in PLAUSIBLE),
            "ohne_erklaerung": sum(v for k, v in alt_days.items() if k.startswith("ursache_") and k[len("ursache_"):] in UNEXPLAINED),
            "ohne_vergleich_aktien": len(no_prices) + unsecured_alt,
            "ohne_vergleich_ohne_kurse": len(no_prices),
            "ohne_vergleich_tage": alt_days.get("nur_im_stand", 0),
            "nicht_abgesichert_aktien": unsecured_alt,
            "nicht_abgesichert_tage": unsecured_days.get("zusatzquelle", 0),
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
        "nicht_abgesichert": len(unsecured),
        "nicht_abgesichert_je_vergleich": dict(Counter(unsecured.values())),
        "abstimmung_nasdaq": dict(reconcile["nasdaq"]),
        "abstimmung_nocp": dict(reconcile["nocp"]),
        "ohne_vergleichskurse_kuerzel": dict(no_price_symbols),
        "ohne_nasdaq_boerse": dict(no_price_exchange),
        "sperrpausen": block_pauses,
        "nasdaq_anfragen": nasdaq_requests(http),
        "nasdaq_anfragen_bis_zur_ersten_sperre": first_block,
        "nasdaq_abstand_s": intervals.get(NASDAQ_HOST) if isinstance(intervals, dict) else None,
        "wertpapierliste": {"status": listing_status, "eintraege": len(listing_rows)},
        "openfigi": dict(Counter(str(entry.get("status", "fehlt")) for entry in figi.values())),
        "absicherung": absicherung.summary(sec_checks),
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
        "je_aktie_und_tag": dict(stock_days),
        "je_aktie_und_tag_zusatz": dict(stock_days_c),
        "zusatzquellen": {
            "aktien_ohne_nasdaq": sum(no_price_symbols.values()),
            "verglichen": len(alt_compared),
            "nicht_abgesichert": unsecured_alt,
            "je_quelle": dict(Counter(alt_compared.values())),
            "pruefungen": dict(zusatz.summary_counts(alt_checks)),
            "felder": field_names(alt_checks),
            "tage": dict(alt_days),
            "muster": dict(alt_patterns),
            "otc_lasttradetime": dict(otc_seen),
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
    report["uebergabe"] = transfer_payload(sid, auswahl, report, {i: group_of[i] for i in chosen}, compared, alt_compared, no_prices, failures, repl,
                                           {"a": days_a, "b": days_b, "c": days_c}, info, unsecured, gaps)
    return report


def yahoo_daily(http, symbol: str, start_day: int, cutoff: int) -> dict:
    """Yahoo-Tageskurse einer Aktie (unbereinigt, dividendenbereinigt, Splits, Dividenden, Börse, Währung) – für die Prüfung der
    Bereinigung einer Vergleichsquelle."""
    url = YAHOO_DAILY.format(symbol=urllib.parse.quote(symbol, safe="-.^="), start=start_day * 86400, end=(cutoff + 2) * 86400)
    status, payload = get_json(http, url, gegen.YAHOO_HEADERS)
    out = parse_yahoo_daily(payload) if status == "ok" else {"days": {}, "splits": [], "dividends": []}
    out["status"] = status
    return out


WORLD_RESULT_TEXT = {
    "abgesichert": "abgesichert verglichen",
    "nicht_abgesichert": "Kurse gefunden, Zuordnung nicht ausreichend abgesichert",
    "nicht_gefunden": "bei CNBC unter keiner Schreibweise des Kürzels gefunden",
    "ohne_kuerzelregel": "keine Regel für das Kürzel bei CNBC (Börse ohne Tabelle)",
    "keine_kurse": "Kursmeldung gefunden, aber keine Tageskerzen im Zeitraum",
    "stand_ohne_kurse": "Stand ohne Kurse im Zeitraum",
    "zeitbudget_erschoepft": "Zeitbudget erschöpft",
}


def run_world_leg(stand: nachrechnen.Stand, sid: str, http, figi_lookup=None, clock=time.monotonic, budget_s: float = welt.BUDGET_S) -> dict:
    """Prüfjob „welt“ (Auftrag vom 25.10.2026, 09:20 Uhr, Punkt 6): alle Aktien außerhalb der US-Auswahl mit mindestens einem Platz
    unter den ersten 10 irgendeiner Rangliste, die häufigsten zuerst, gegen CNBC – mit derselben strengen Absicherung und Einordnung
    wie die US-Aktien. Variante (d): an jedem abweichenden Tag einer abgesicherten Aktie der Kurs von CNBC (in der Einheit des Stands)."""
    manifest = stand.get("manifest.bin")
    instruments = stand.get("instruments.bin")
    cutoff = int(manifest["cutoff_day"])
    min_trend = int((manifest.get("method") or {}).get("min_obs_trend", 15))
    liquid = (instruments.get("turnover") or {}).get("liquid") or [False] * len(instruments["isin"])
    start_day = cutoff - gegen.LOOKBACK_DAYS - 5
    us = us_stocks(instruments)
    selection = welt.select_world(stand, instruments, us)
    chosen, top10, first = selection
    figi = (figi_lookup or absicherung.figi_lookup)([str(instruments["isin"][i]) for i in chosen]) if chosen else {}
    result = welt.run_world(stand, instruments, http, us, lambda i: own_series(stand, instruments, i, start_day, cutoff), lambda i: stand_meta(instruments, i), figi,
                            start_day, cutoff, lambda symbol: yahoo_daily(http, symbol, start_day, cutoff), within_display, clock=clock, budget_s=budget_s, selection=selection)
    repl: dict[str, dict[int, dict[int, float]]] = {"d": {}}
    days_d: dict[int, dict[int, tuple[float, str]]] = {}
    substituted: dict[int, tuple[np.ndarray, np.ndarray, set[int]]] = {}
    stock_days: Counter = Counter()
    causes: Counter = Counter()
    by_exchange: dict[str, Counter] = {}
    info: dict[int, dict] = {}
    secured: dict[int, str] = {}
    unsecured: dict[int, str] = {}
    no_prices: dict[int, str] = {}
    rows_out: list[dict] = []
    totals = Counter()
    gaps: dict[int, dict] = {}  # Lücken je Aktie (ohne Vergleichskurse, nicht abgesichert) – Börse, Kursbereich, Grund, nicht bestandene Prüfungen
    for i in chosen:
        entry = result["aktien"][i]
        key = entry["boerse"]
        c = by_exchange.setdefault(key, Counter())
        c["aktien"] += 1
        c["plaetze_erste_10"] += entry["top10"]
        c["plaetze_platz_1"] += entry["platz1"]
        c[f"ergebnis_{entry.get('ergebnis', 'unbekannt')}"] += 1
        if entry.get("ergebnis") != "abgesichert":
            own_gap = own_series(stand, instruments, i, start_day, cutoff)
            gaps[i] = {"boerse": key, "kursbereich": welt.zusatz_price_range({d: {"close": v} for d, v in own_gap.items()}) if own_gap else "–",
                       "grund": entry.get("ergebnis", "unbekannt"), "pruefungen": entry.get("grund") or "", "tage_stand": len(own_gap), "befund": entry.get("befund") or ""}
            c["tage_stand_ungeprueft"] += len(own_gap)
            if entry.get("ergebnis") == "nicht_abgesichert":
                unsecured[i] = "cnbc_welt"
                totals["nicht_abgesichert_tage"] += int(entry.get("tage_verglichen") or 0)
                for check in (entry.get("grund") or "").split(","):
                    if check:
                        c[f"nicht_bestanden_{check}"] += 1
            else:
                no_prices[i] = entry.get("ergebnis", "unbekannt")
            continue
        secured[i] = "cnbc_welt"
        c["plaetze_erste_10_abgesichert"] += entry["top10"]
        c["plaetze_platz_1_abgesichert"] += entry["platz1"]
        days = entry.get("tage") or {}
        own_count = int(entry.get("tage_stand") or 0)
        split_days = [d for d, v in days.items() if v[0] == "gleich_nach_split"]
        deviating = {d: v for d, v in days.items() if v[0] not in ("gleich", "gleich_nach_split")}
        equal = len(days) - len(split_days) - len(deviating)
        stock_days["verglichen"] += len(days)
        stock_days["uebereinstimmung"] += equal
        stock_days["belegt"] += len(split_days)
        stock_days["ohne_vergleich"] += max(0, own_count - len(days))
        c["tage_stand"] += own_count
        c["tage_verglichen"] += len(days)
        totals["nur_im_stand"] += int(entry.get("nur_im_stand") or 0)
        totals["nur_im_stand_ohne_umsatz"] += int(entry.get("nur_im_stand_ohne_umsatz") or 0)
        per_stock: Counter = Counter()
        if split_days:
            per_stock["split"] += len(split_days)
            causes["split"] += len(split_days)
        own = own_series(stand, instruments, i, start_day, cutoff) if deviating else {}
        for d, (kind, alt_close, cause) in deviating.items():
            stock_days[evidence_class(cause)] += 1
            causes[cause] += 1
            per_stock[cause] += 1
            days_d.setdefault(i, {})[d] = (round(100 * (own[d] / alt_close - 1), 3), cause)
            repl["d"].setdefault(i, {})[d] = alt_close
        if deviating:
            substituted[i] = substitution(own, repl["d"][i])
        info[i] = {"boerse": key, "kursbereich": entry.get("kursbereich", "–"), "quelle": "cnbc_welt", "abweichend": len(deviating) + len(split_days), "nocp_ungleich": 0,
                   "tage_stand": own_count, "tage_verglichen": len(days)}
        if deviating or split_days:
            rows_out.append({"idx": i, "top10": entry["top10"], "platz1": entry["platz1"], "boerse": key, "kursbereich": entry.get("kursbereich", "–"), "quelle": "cnbc_welt",
                             "abweichend": len(deviating) + len(split_days), "ursachen": dict(per_stock),
                             "groesste_abweichung_pct": round(max([abs(v[0]) for v in (days_d.get(i) or {}).values()] or [0.0]), 2)})
    effects = ranking_effects(stand, {"d": substituted}, liquid, min_trend, set(chosen))
    effect_d, moves_d, changes_d = effects["d"]
    ordered = sorted(rows_out, key=lambda r: (-r["top10"], -r["abweichend"]))

    def state_of(i: int) -> str:
        if i in info:
            return "verglichen"
        if i in unsecured:
            return "nicht_abgesichert"
        if i in no_prices:
            return "ohne_vergleichskurse"
        return "us_auswahl" if i in us else "nicht_ausgewaehlt"

    names = Lettering([r["idx"] for r in ordered], state_of, info, top10, gaps=gaps, first_places=first)
    changes_d = names.changes(changes_d, days_d)
    for r in rows_out:
        r["aktie"] = names(r["idx"])
        r["rangwirkung_zusatz"] = moves_d.get(r["idx"], {})
        del r["idx"]
    for i in sorted(gaps, key=lambda j: (-top10.get(j, 0), j)):  # Lücken je Aktie mit Buchstaben (zuletzt vergeben)
        names(i)
    category = {
        "uebereinstimmung": stock_days.get("uebereinstimmung", 0),
        "abweichung": stock_days.get("belegt", 0) + stock_days.get("plausibel", 0) + stock_days.get("ohne_erklaerung", 0),
        "belegt": stock_days.get("belegt", 0),
        "plausibel": stock_days.get("plausibel", 0),
        "ohne_erklaerung": stock_days.get("ohne_erklaerung", 0),
        "ohne_vergleich_aktien": len(no_prices) + len(unsecured),
        "ohne_vergleich_ohne_kurse": len(no_prices),
        "ohne_vergleich_tage": totals.get("nur_im_stand", 0),
        "nicht_abgesichert_aktien": len(unsecured),
        "nicht_abgesichert_tage": totals.get("nicht_abgesichert_tage", 0),
    }
    coverage = Counter()
    for i in chosen:
        coverage["verglichen" if i in secured else ("nicht_abgesichert" if i in unsecured else "keine_vergleichskurse")] += 1
        if i in secured:
            coverage["verglichen_cnbc_welt"] += 1
        elif i in no_prices:
            coverage[f"keine_vergleichskurse_{no_prices[i]}"] += 1
    report = {
        "stand": sid,
        "stichtag": nachrechnen._iso(cutoff),
        "abgerufen_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "auswahl": WORLD_LEG,
        "ausgewaehlt": len(chosen),
        "plaetze_welt": {"erste_10": int(sum(top10.values())), "platz_1": int(sum(first.values()))},
        "abruf_fehlgeschlagen": 0,
        "ohne_vergleichskurse": len(no_prices),
        "nicht_abgesichert": len(unsecured),
        "abdeckung_je_gruppe": {"welt": dict(coverage)},
        "openfigi": dict(Counter(str(entry.get("status", "fehlt")) for entry in figi.values())),
        "absicherung": absicherung.summary(result["pruefungen"]),
        "welt": {"zaehler": dict(result["zaehler"]), "je_boerse": {k: dict(v) for k, v in sorted(by_exchange.items())}, "ursachen": dict(causes),
                 "nur_im_stand": totals.get("nur_im_stand", 0), "nur_im_stand_ohne_umsatz": totals.get("nur_im_stand_ohne_umsatz", 0)},
        "kategorien": {"cnbc_welt": category},
        "je_aktie_und_tag_welt": dict(stock_days),
        "aktien_welt": sorted(rows_out, key=lambda r: (len(r["aktie"]), r["aktie"])),
        "ranglisten_welt": effect_d,
        "aenderungen_welt": changes_d,
        "weitere_buchstaben": names.legend,
        "zuordnung": names.mapping(stand),
    }
    report["urteil"] = verdict(report)
    report["uebergabe"] = transfer_payload(sid, WORLD_LEG, report, {i: "welt" for i in chosen}, set(), secured, no_prices, {}, repl, {"d": days_d}, info, unsecured, gaps)
    return report


def open_days(report: dict) -> tuple[int, int, int]:
    """Abweichende Tage aller Vergleiche eines Berichts: (alle, ungeklärt, davon mit plausibler Erklärung) – je Vergleich gezählt;
    dieselbe Aktie und derselbe Tag können in Nasdaq-Historie und NOCP zugleich vorkommen (eindeutig: ``je_aktie_und_tag``)."""
    cats = report.get("kategorien") or {}
    total = sum((c or {}).get("abweichung", 0) for c in cats.values())
    plausible = sum((c or {}).get("plausibel", 0) for c in cats.values())
    unexplained = sum((c or {}).get("ohne_erklaerung", 0) for c in cats.values())
    return total, plausible + unexplained, plausible


def verdict(report: dict) -> str:
    """„unvollstaendig“ (eine Aktie blieb ohne Antwort, ohne Vergleichskurse oder ohne abgesicherte Zuordnung – fehlende Daten
    und nicht abgesicherte Vergleiche zählen nicht als geprüft), „ungeklaert“ (mindestens ein abweichender Tag ohne belegte
    Ursache, auch mit plausibler Erklärung), „belegt“ (jede Abweichung belegt) oder „keine_abweichungen“."""
    if report.get("abruf_fehlgeschlagen") or report.get("ohne_vergleichskurse") or report.get("nicht_abgesichert"):
        return "unvollstaendig"
    total, unresolved, _ = open_days(report)
    if unresolved:
        return "ungeklaert"
    return "belegt" if total else "keine_abweichungen"


def doubled_ranks_fast(values: np.ndarray) -> np.ndarray:
    """Doppelter aufsteigender Durchschnittsrang wie ``nachrechnen.doubled_ranks`` (Gleichstand a…b → a + b, NaN je eigener
    Rang am Ende), vektorisiert – Gleichheit im Test für Zufallswerte mit Gleichständen geprüft."""
    values = np.asarray(values, dtype=np.float64)
    n = len(values)
    if n == 0:
        return np.empty(0, dtype=np.int64)
    order = np.argsort(values, kind="stable")
    ordered = values[order]
    starts_flag = np.empty(n, dtype=bool)
    starts_flag[0] = True
    starts_flag[1:] = ordered[1:] != ordered[:-1]
    starts = np.nonzero(starts_flag)[0]
    ends = np.append(starts[1:], n) - 1
    group = np.cumsum(starts_flag) - 1
    ranks = np.empty(n, dtype=np.int64)
    ranks[order] = (starts[group] + 1) + (ends[group] + 1)
    return ranks


class LeaderSearch:
    """Platz 1 einer Rangliste (Gruppe, Gewichtung), wenn nur die Kurse einer Teilmenge der ersetzten Aktien ersetzt werden –
    dieselben Regeln wie ``nachrechnen.rank_group`` (0/100: Rendite in V; 100/0: R², Rendite, Index in U; sonst exakter Score
    w·(dG − 2) + (100 − w)·(dR − 2), Rendite, Index in U). Schnell, weil sich je Teilmenge nur wenige Werte ändern: der doppelte
    Durchschnittsrang ist 2·(Zahl kleinerer Werte) + (Zahl gleicher Werte) + 1 und wird aus den Rängen ohne Ersatz um die
    entfernten und hinzugekommenen Werte berichtigt (bei NaN die vollständige Rechnung). ``leader_full`` rechnet jede Teilmenge
    vollständig neu (Gegenprobe im Test)."""

    def __init__(self, members: np.ndarray, w: str | int, base: tuple, new: tuple) -> None:
        status, r_of, r2_of = base
        status_new, r_new, r2_new = new
        self.w = int(w)
        self.v = np.array(sorted(int(i) for i in members), dtype=np.int64)
        self.pos = {int(i): k for k, i in enumerate(self.v.tolist())}
        ids = self.v.tolist()
        self.r0 = np.array([r_of[i] for i in ids], dtype=np.float64)
        self.r1 = np.array([r_new[i] for i in ids], dtype=np.float64)
        self.g0 = np.array([np.nan if r2_of.get(i) is None else float(r2_of[i]) for i in ids], dtype=np.float64)
        self.g1 = np.array([np.nan if r2_new.get(i) is None else float(r2_new[i]) for i in ids], dtype=np.float64)
        self.u0 = np.array([int(status[i]) == nachrechnen.U_STATUS for i in ids], dtype=bool)
        self.u1 = np.array([int(status_new[i]) == nachrechnen.U_STATUS for i in ids], dtype=bool)
        self.evaluations = 0
        self.incremental = 0 < self.w < 100 and not np.isnan(self.g0[self.u0]).any() and not np.isnan(self.g1[self.u1]).any()
        if self.incremental:
            self.base = {}
            for name, values in (("g", self.g0), ("r", self.r0)):
                pool = np.sort(values[self.u0])
                less = np.searchsorted(pool, values, side="left")
                equal = np.searchsorted(pool, values, side="right") - less
                self.base[name] = (pool, less.astype(np.int64), equal.astype(np.int64))

    def leader(self, subset) -> int | None:
        self.evaluations += 1
        k = sorted({self.pos[int(j)] for j in subset if int(j) in self.pos})
        if not len(self.v):
            return None
        if not self.incremental:
            return self._full(k)
        removed = [j for j in k if self.u0[j]]
        added = [j for j in k if self.u1[j]]
        keep = self.u0.copy()
        keep[k] = False
        doubled = {}
        for name, old, new in (("g", self.g0, self.g1), ("r", self.r0, self.r1)):
            pool, less0, equal0 = self.base[name]
            less, equal = less0.copy(), equal0.copy()
            for j in removed:
                less -= old[j] < old
                equal -= old[j] == old
            for j in added:
                less += new[j] < old
                equal += new[j] == old
            ranks = 2 * less + equal + 1
            for j in added:  # neuer Wert der Aktie gegen alle Werte der Vergleichsmenge mit dieser Teilmenge
                value = new[j]
                lj = int(np.searchsorted(pool, value, side="left"))
                ej = int(np.searchsorted(pool, value, side="right")) - lj
                lj -= sum(1 for x in removed if old[x] < value)
                ej -= sum(1 for x in removed if old[x] == value)
                lj += sum(1 for x in added if x != j and new[x] < value)
                ej += sum(1 for x in added if new[x] == value)
                ranks[j] = 2 * lj + ej + 1
            doubled[name] = ranks
        members = keep.copy()
        members[added] = True
        sel = np.nonzero(members)[0]
        if not len(sel):
            return None
        r = self.r0.copy()
        if k:
            r[k] = self.r1[k]
        key = self.w * (doubled["g"][sel] - 2) + (100 - self.w) * (doubled["r"][sel] - 2)
        best = sel[key == key.max()]
        if len(best) > 1:
            best = best[r[best] == r[best].max()]
        return int(self.v[best[0]])  # Index aufsteigend: bei Gleichstand die kleinere Nummer (wie die Reihenfolge in rank_group)

    def leader_full(self, subset) -> int | None:
        return self._full(sorted({self.pos[int(j)] for j in subset if int(j) in self.pos}))

    def _full(self, k: list[int]) -> int | None:
        r, g, u = self.r0.copy(), self.g0.copy(), self.u0.copy()
        if k:
            r[k], g[k], u[k] = self.r1[k], self.g1[k], self.u1[k]
        if not len(self.v):
            return None
        if self.w == 0:
            if np.isnan(r).any():
                return int(self.v[np.lexsort((self.v, -r))[0]])
            return int(self.v[np.flatnonzero(r == r.max())[0]])  # größte Rendite, bei Gleichstand die kleinere Nummer
        sel = np.nonzero(u)[0]
        if not len(sel):
            return None
        ru, gu, vu = r[sel], g[sel], self.v[sel]
        if self.w == 100:
            if np.isnan(gu).any() or np.isnan(ru).any():
                return int(vu[np.lexsort((vu, -ru, -gu))[0]])
            best = np.flatnonzero(gu == gu.max())
            best = best[ru[best] == ru[best].max()]
            return int(vu[best[0]])
        key = self.w * (doubled_ranks_fast(gu) - 2) + (100 - self.w) * (doubled_ranks_fast(ru) - 2)
        return int(vu[np.lexsort((vu, -ru, -key))[0]])


def minimal_triggers(leader_of, candidates: list[int], target: int, budget: int, order_key=None) -> dict:
    """Kleinste Auslösermenge: Teilmengen der ersetzten Aktien nach Größe, jede Größe vollständig, bis Platz 1 = ``target`` wird
    – dann ist die gefundene Größe nachweislich die kleinste (alle kleineren Mengen geprüft; die leere Menge ergibt den bisherigen
    Platz 1). Reicht das Budget (Zahl der Auswertungen) für eine Größe nicht, endet die exakte Suche: dann eine irreduzible Menge
    (schrittweise hinzugenommen, danach jede überflüssige weggelassen) mit der Grenze „kleinste Menge hat mindestens k Aktien“ –
    ausdrücklich nicht als kleinste bezeichnet."""
    from itertools import combinations
    from math import comb

    n = len(candidates)
    used = 0
    checked = 0
    for k in range(1, n + 1):
        count = comb(n, k)
        if used + count > budget and k > 1:
            break
        found = []
        for subset in combinations(candidates, k):
            used += 1
            if leader_of(list(subset)) == target:
                found.append(list(subset))
        checked = k
        if found:
            return {"verfahren": "exakt", "nachgewiesen": True, "groesse": k, "mengen": found, "geprueft_bis": k, "auswertungen": used, "kandidaten": n}
    pool = sorted(candidates, key=order_key) if order_key else list(candidates)
    subset: list[int] = []
    needed: list[int] | None = None
    for j in pool:
        subset.append(j)
        used += 1
        if leader_of(subset) == target:
            needed = list(subset)
            break
    if needed:
        for j in list(reversed(needed)):
            trial = [x for x in needed if x != j]
            used += 1
            if trial and leader_of(trial) == target:
                needed = trial
    return {"verfahren": "irreduzibel", "nachgewiesen": False, "groesse": len(needed) if needed else None, "mengen": [needed] if needed else [],
            "geprueft_bis": checked, "mindestens": checked + 1, "auswertungen": used, "kandidaten": n}


TRIGGER_BUDGET = 60_000  # Auswertungen je neuem Platz 1 für die exakte Suche (alle Paare bis etwa 345 ersetzte Aktien; je Auswertung unter 1 ms)
MAX_TRIGGER_SETS = 12  # gleich kleine Auslösermengen je neuem Platz 1 in der Ausgabe (die übrigen gezählt)
SINGLE_CHECK_LIMIT = 400  # bei Auslösermenge 1: so viele ersetzte Aktien je neuem Platz 1 zusätzlich einzeln mit der unabhängigen Rechnung


def leader_change(members: np.ndarray, w: str, order: list[int], new_leader: int, candidates: list[int], base: tuple, new: tuple, start_of: dict[int, int],
                  budget: int = TRIGGER_BUDGET) -> dict:
    """Einzelheiten eines neuen Platzes 1: Rendite, R² und Score (wie in der App) des bisherigen und des neuen Spitzenreiters
    vorher/nachher, sein bisheriger Platz und die kleinste Menge ersetzter Aktien, die den Wechsel auslöst (seit dem 25.10.2026,
    09:20 Uhr, Punkt 5: exakte Suche nach Größe mit benannter Grenze – schrittweises Hinzufügen und Weglassen findet die kleinste
    Menge im Allgemeinen nicht). Gegenprobe je Auslöser: Platz 1 mit diesem Auslöser allein und mit allen übrigen ersetzten
    Kursen ohne ihn; für die ganze Menge: Platz 1 ohne alle ihre Aktien."""
    status, r_of, r2_of = base
    status_new, r_new, r2_new = new
    old_leader = order[0]
    fast = LeaderSearch(members, w, base, new)

    def slow(subset: list[int]) -> int | None:
        st, r, r2 = status.copy(), dict(r_of), dict(r2_of)
        for j in subset:
            st[j], r[j], r2[j] = status_new[j], r_new[j], r2_new[j]
        ranked = lists_of(nachrechnen.rank_group(members, st, r, r2))[w]
        return int(ranked[0]) if len(ranked) else None

    # die schnelle Rechnung gilt nur, wenn sie für die leere und die volle Menge den Platz 1 der unabhängigen Rechnung ergibt
    valid = fast.leader([]) == old_leader and fast.leader(candidates) == new_leader
    leader_of = fast.leader if valid else slow

    def size(j: int) -> float:
        change_r2 = abs(float(r2_new[j]) - float(r2_of[j])) if r2_new.get(j) is not None and r2_of.get(j) is not None else 0.0
        return abs(r_new[j] - r_of[j]) + change_r2

    order_key = lambda j: (0 if j in (old_leader, new_leader) else 1, -size(j), j)  # noqa: E731
    search = minimal_triggers(leader_of, sorted(candidates, key=order_key), new_leader, budget if valid else min(budget, 400), order_key)
    sets = search["mengen"]
    needed = sets[0] if sets else None
    alone = [m[0] for m in sets] if search.get("groesse") == 1 else []
    # Gegenprobe mit der unabhängigen Rechnung (``nachrechnen.rank_group`` wie in der Nachrechnung des Stands), nicht mit der
    # schnellen Rechnung der Suche (seit dem 25.10.2026, 11:45 Uhr; Auftrag Punkt 5: „Z31 allein sowie alle übrigen Änderungen
    # ohne Z31“) – weicht die schnelle Rechnung ab, steht das am Wechsel
    checks = []
    for j in (alone if alone else (needed or [])):
        rest = [x for x in candidates if x != j]
        independent = (slow([j]), slow(rest) if rest else old_leader)
        by_search = (leader_of([j]), leader_of(rest) if rest else old_leader)
        checks.append({"aktie": j, "allein": independent[0], "ohne": independent[1], "wie_suche": by_search == independent})
    # bei Größe 1 jede einzelne ersetzte Aktie auch unabhängig: bestätigt „allein ausreichend“ und dass keine andere allein reicht
    singles = None
    if search.get("groesse") == 1 and len(candidates) <= SINGLE_CHECK_LIMIT:
        found_alone = [j for j in candidates if slow([j]) == new_leader]
        singles = {"geprueft": len(candidates), "allein": found_alone, "wie_suche": sorted(found_alone) == sorted(alone)}
    without = slow([j for j in candidates if j not in (needed or [])]) if needed else None
    involved = {old_leader, new_leader, *(needed or []), *alone, *([without] if without is not None else [])}
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
        "weitere_mengen": [m for m in sets[1:MAX_TRIGGER_SETS]] if search.get("groesse", 0) and search["groesse"] > 1 else [],
        "mengen_gleicher_groesse": len(sets),
        "suche": {k: search.get(k) for k in ("verfahren", "nachgewiesen", "groesse", "geprueft_bis", "mindestens", "auswertungen", "kandidaten")} | {"schnell": valid},
        "gegenprobe": checks,
        "einzeln_unabhaengig": singles,
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


INTERACTION_PROPS = ("spitze", "top10_aktien", "top10_reihenfolge", "reihenfolge")
MAX_INTERACTION_EXAMPLES = 40  # Ranglisten je Wechselwirkung mit „erst gemeinsam“ bzw. „aufgehoben“ (Platz 1, erste 10) in der Ausgabe
ATTRIBUTION_BUDGET_S = 15 * 60  # Zeit für die Suche nach Auslösern je Job (danach „nicht untersucht – Zeitbudget“, gezählt)


def _positions(order: list[int], size: int) -> np.ndarray:
    out = np.full(size, -1, dtype=np.int64)
    if order:
        out[np.asarray(order, dtype=np.int64)] = np.arange(len(order), dtype=np.int64)
    return out


def interaction_step(stats: dict, examples: list, before: list[int], p_after: list[int], q_after: list[int], pq_after: list[int], where: dict, size: int) -> None:
    """Wechselwirkung zweier Teile P und Q in einer Rangliste (Auftrag vom 25.10.2026, 09:20 Uhr, Punkt 1): je Eigenschaft (Platz 1,
    Aktien der ersten 10, Reihenfolge der ersten 10, irgendeine Änderung) „erst gemeinsam“ (gemeinsam geändert, mit keinem Teil
    allein), „aufgehoben“ (mit einem Teil allein geändert, gemeinsam nicht), „auch einzeln“ (gemeinsam und mit mindestens einem Teil
    allein geändert); bei Platz 1 zusätzlich „anderer Spitzenreiter als einzeln“. Dazu je Aktie die Rangänderungen über die ganze
    Liste: gemeinsam, mit P, mit Q, erst gemeinsam, aufgehoben."""
    stats["ranglisten"] += 1
    flags = {name: compare_orders(before, x) for name, x in (("p", p_after), ("q", q_after), ("pq", pq_after))}
    for prop in INTERACTION_PROPS:
        cp, cq, cpq = flags["p"][prop], flags["q"][prop], flags["pq"][prop]
        stats[f"{prop}_mit_p"] += cp
        stats[f"{prop}_mit_q"] += cq
        stats[f"{prop}_gemeinsam"] += cpq
        if cpq and not cp and not cq:
            stats[f"{prop}_erst_gemeinsam"] += 1
        elif (cp or cq) and not cpq:
            stats[f"{prop}_aufgehoben"] += 1
        elif cpq:
            stats[f"{prop}_auch_einzeln"] += 1
    lead = lambda order: order[0] if order else None  # noqa: E731
    if flags["pq"]["spitze"] and (flags["p"]["spitze"] or flags["q"]["spitze"]):
        singles = {lead(x) for name, x in (("p", p_after), ("q", q_after)) if flags[name]["spitze"]}
        if lead(pq_after) not in singles:
            stats["spitze_anderer_spitzenreiter_als_einzeln"] += 1
    kind = None
    if flags["pq"]["spitze"] != (flags["p"]["spitze"] or flags["q"]["spitze"]) or flags["pq"]["top10_aktien"] != (flags["p"]["top10_aktien"] or flags["q"]["top10_aktien"]):
        kind = "erst_gemeinsam" if (flags["pq"]["spitze"] or flags["pq"]["top10_aktien"]) else "aufgehoben"
    elif flags["pq"]["spitze"] and lead(pq_after) not in {lead(p_after), lead(q_after)}:
        kind = "anderer_spitzenreiter"
    if kind and len(examples) < MAX_INTERACTION_EXAMPLES:
        examples.append({**where, "art": kind, "platz1": [lead(before), lead(p_after), lead(q_after), lead(pq_after)],
                         "erste10": [sorted(before[:10]), sorted(p_after[:10]), sorted(q_after[:10]), sorted(pq_after[:10])]})
    elif kind:
        stats["beispiele_nicht_ausgegeben"] += 1
    pos0, pp, pq, ppq = (_positions(x, size) for x in (before, p_after, q_after, pq_after))
    present = (pos0 >= 0) | (pp >= 0) | (pq >= 0) | (ppq >= 0)
    ch_p, ch_q, ch_pq = (pp != pos0) & present, (pq != pos0) & present, (ppq != pos0) & present
    stats["aktien_rang_mit_p"] += int(ch_p.sum())
    stats["aktien_rang_mit_q"] += int(ch_q.sum())
    stats["aktien_rang_gemeinsam"] += int(ch_pq.sum())
    stats["aktien_rang_erst_gemeinsam"] += int((ch_pq & ~ch_p & ~ch_q).sum())
    stats["aktien_rang_aufgehoben"] += int(((ch_p | ch_q) & ~ch_pq).sum())


def ranking_effects(
    stand: nachrechnen.Stand,
    variants: dict[str, dict[int, tuple[np.ndarray, np.ndarray, set[int]]]],
    liquid,
    min_trend: int,
    top_stocks: set[int],
    attribute: set[str] | None = None,
    order_details: set[str] | None = None,
    interactions: list[tuple[str, str, str]] | None = None,
    interaction_out: dict | None = None,
    clock=time.monotonic,
    attribution_budget_s: float = ATTRIBUTION_BUDGET_S,
) -> dict[str, tuple[dict, dict, list[dict]]]:
    """Alle Ranglisten mit den Kursen des Stands und – je Variante – mit den ersetzten Kursen (unabhängige Rechnung, ein
    Durchgang über die Zeiträume für alle Varianten): Zählwerte, Wirkung je Aktie aus ``top_stocks`` und – einzeln – jede
    Rangliste mit anderem Platz 1 oder anderen Aktien unter den ersten 10. Für Varianten in ``attribute`` (Vorgabe: alle) mit
    Suche nach den Auslösern eines neuen Platzes 1 (exakt mit Grenze, ``leader_change``), für Varianten in ``order_details``
    auch jede Rangliste, deren erste 10 bei gleichen Aktien eine andere Reihenfolge haben. ``interactions``: Tripel (P, Q, PQ)
    von Varianten, deren Wechselwirkung je Rangliste gezählt wird (Ergebnis in ``interaction_out``)."""
    attribute = set(variants) if attribute is None else set(attribute)
    order_details = set(order_details or ())
    interactions = [t for t in (interactions or []) if all(v in variants for v in t)]
    in_interactions = {v for t in interactions for v in t}  # nur deren Ranglisten je Zeitraum aufheben (Speicher)
    totals = {v: Counter() for v in variants}
    moves = {v: {i: Counter() for i in top_stocks} for v in variants}
    changes: dict[str, list[dict]] = {v: [] for v in variants}
    attributed = Counter()
    started = clock()
    i_stats = {t: Counter() for t in interactions}
    i_examples: dict[tuple, list] = {t: [] for t in interactions}
    active = {v: subs for v, subs in variants.items() if subs}
    size = None
    for h in range(1, 91) if active else ():
        win = stand.get(f"windows/{h}.full.bin")
        stand.drop(f"windows/{h}.full.bin")
        mm = win["m"]
        status = np.frombuffer(__import__("base64").b64decode(win["status_b64"]), dtype=np.uint8).copy()
        size = size or len(status)
        idx = [int(x) for x in mm["idx"]]
        r_of = {i: float(mm["r"][k]) for k, i in enumerate(idx)}
        r2_of = {i: mm["r2"][k] for k, i in enumerate(idx)}
        start_of = {i: int(mm["start"][k]) for k, i in enumerate(idx)}
        groups = (("A", idx), ("B", [i for i in idx if liquid[i]]))
        before_of: dict[str, dict] = {}
        after_of: dict[tuple[str, str], dict] = {}
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
                if v in in_interactions:
                    after_of[(v, name)] = after
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
                            in_time = clock() - started <= attribution_budget_s
                            if v in attribute and attributed[v] < MAX_ATTRIBUTIONS and in_time:
                                attributed[v] += 1
                                change.update(leader_change(members_arr, w, order, after[w][0], candidates, (status, r_of, r2_of), (status_new, r_new, r2_new), start_of))
                            else:
                                # nicht in den Zählwerten: die sollen in jedem Job gleich gerechnet vergleichbar bleiben (Grund steht am Wechsel)
                                reason = "zeitbudget" if v in attribute and attributed[v] < MAX_ATTRIBUTIONS else ("grenze" if v in attribute else "nicht_vorgesehen")
                                change.update({"nicht_untersucht": reason, "platz_des_neuen_vorher": order.index(after[w][0]) + 1 if after[w][0] in order else None,
                                               "rendite": {}, "r2": {}, "score": {}, "vergleichsmenge": None, "ausloeser": None, "ausloeser_werte": {},
                                               "allein": [], "weitere_mengen": [], "mengen_gleicher_groesse": 0, "suche": {}, "gegenprobe": [],
                                               "ohne_ausloeser": None, "ersetzte_im_zeitraum": len(candidates), "start": {}})
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
        # Wechselwirkung je Rangliste: ohne Änderung in einem Teil gilt dessen Rangliste als unverändert
        for t in interactions:
            p_v, q_v, pq_v = t
            for name, members in groups:
                if not any((x, name) in after_of for x in t):
                    continue
                if name not in before_of:
                    before_of[name] = lists_of(nachrechnen.rank_group(np.array(members, dtype=np.int64), status, r_of, r2_of))
                before = before_of[name]
                for w, order in before.items():
                    pick = lambda v: (after_of.get((v, name)) or before)[w]  # noqa: E731
                    if not order and not any(pick(v) for v in t):
                        continue  # leere Rangliste (bis 25.10.2026, 11:45 Uhr mitgezählt: „1980 Ranglisten“ statt der 1640 mit Einträgen)
                    interaction_step(i_stats[t], i_examples[t], order, pick(p_v), pick(q_v), pick(pq_v), {"h": h, "gruppe": name, "w": int(w)}, size)
    out = {}
    for v in variants:
        totals[v]["ranglisten_insgesamt"] = 90 * 2 * len(nachrechnen.WEIGHTS)
        out[v] = (dict(totals[v]), {i: dict(c) for i, c in moves[v].items()}, changes[v])
    if interaction_out is not None:
        for t in interactions:
            interaction_out["+".join(t)] = {"teile": list(t[:2]), "gemeinsam": t[2], "zaehler": dict(i_stats[t]), "beispiele": i_examples[t]}
    return out


def ranking_effect(stand: nachrechnen.Stand, substituted: dict[int, tuple[np.ndarray, np.ndarray, set[int]]], liquid, min_trend: int, top_stocks: set[int]) -> tuple[dict, dict, list[dict]]:
    """Eine Variante – siehe ``ranking_effects``."""
    return ranking_effects(stand, {"x": substituted}, liquid, min_trend, top_stocks)["x"]


class Lettering:
    """Buchstaben statt Namen: jede Aktie genau ein Buchstabe (A–Z, dann Z26 …), zuerst die Aktien der Zeilen je Aktie, dann
    die übrigen in der Reihenfolge ihres ersten Auftretens; Aktien ohne eigene Zeile kommen mit ihrem Zustand in die Legende."""

    def __init__(self, first: list[int], state_of, info: dict[int, dict], top10: dict[int, int], gaps: dict[int, dict] | None = None,
                 first_places: dict[int, int] | None = None) -> None:
        self.letters = {i: letter_label(k) for k, i in enumerate(first)}
        self.state_of, self.info, self.top10 = state_of, info, top10
        # Lücken (ohne Vergleichskurse, nicht abgesichert): Börse, Kursbereich und Grund für die Legende – seit dem Lauf 40181869022,
        # in dem ein neuer Platz 1 ohne Vergleichskurse nur als „ausgewählt, aber ohne Vergleichskurse“ erschien
        self.gaps = gaps or {}
        self.first_places = first_places or {}
        self.legend: list[dict] = []

    def __call__(self, i: int | None) -> str:
        if i is None:
            return "–"
        if i not in self.letters:
            self.letters[i] = letter_label(len(self.letters))
            state = self.state_of(i)
            entry = {"aktie": self.letters[i], "abgefragt": i in self.info, "zustand": state, "top10": int(self.top10.get(i, 0))}
            if i in self.first_places:
                entry["platz1"] = int(self.first_places.get(i, 0))
            entry.update(self.info.get(i, {}))
            if i not in self.info and i in self.gaps:
                entry["luecke"] = dict(self.gaps[i])
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
                        "weitere_mengen": [[self(j) for j in m] for m in c.get("weitere_mengen") or []],
                        "mengen_gleicher_groesse": c.get("mengen_gleicher_groesse", 0),
                        "suche": dict(c.get("suche") or {}),
                        "gegenprobe": [{"aktie": self(g["aktie"]), "allein": self(g["allein"]), "ohne": self(g["ohne"]), "wie_suche": g.get("wie_suche", True)}
                                       for g in c.get("gegenprobe") or []],
                        "einzeln_unabhaengig": None if not c.get("einzeln_unabhaengig") else {
                            "geprueft": c["einzeln_unabhaengig"]["geprueft"], "allein": [self(j) for j in c["einzeln_unabhaengig"]["allein"]],
                            "wie_suche": c["einzeln_unabhaengig"]["wie_suche"]},
                        "ohne_ausloeser": None if c.get("ohne_ausloeser") is None else self(c["ohne_ausloeser"]),
                        "ersetzte_aktien_im_zeitraum": c["ersetzte_im_zeitraum"],
                        "nicht_untersucht": c.get("nicht_untersucht") or False,
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
                     failures: dict[int, str], repl: dict[str, dict[int, dict[int, float]]], days: dict[str, dict[int, dict[int, tuple[float, str]]]], info: dict[int, dict],
                     unsecured: dict[int, str] | None = None, gaps: dict[int, dict] | None = None) -> dict:
    """Übergabe eines Prüfjobs an den Job „gemeinsame Wirkung“: je Variante (a Nasdaq-Historie, b offizieller Schlusskurs, c
    Zusatzquellen, d CNBC außerhalb der US-Auswahl) die Ersatzkurse mit Abweichung in % und Ursache, dazu Gruppen, Abdeckung,
    nicht abgesicherte Vergleiche und Zählwerte. Die Prüfsumme über die Ersatzkurse steht im Protokoll beider Jobs – so ist
    belegt, dass die gemeinsame Rechnung genau diese Kurse nutzt."""
    names = sorted(repl)
    variants = {
        v: {str(i): [[int(d), float(repl[v][i][d]), days[v][i][d][0], days[v][i][d][1]] for d in sorted(repl[v][i])] for i in sorted(repl[v])}
        for v in names
    }
    counts = ("tage", "ursachen", "nocp_vergleich", "nocp_ursachen", "ungeklaert_gruende", "nur_eine_quelle", "ohne_vergleichskurse_kuerzel", "ohne_nasdaq_boerse",
              "zusatzquellen", "detailabruf", "nasdaq_anfragen", "abruf_fehlgeschlagen", "ohne_vergleichskurse", "ranglisten", "ranglisten_offizieller_schlusskurs",
              "ranglisten_zusatzquellen", "je_aktie_und_tag", "je_aktie_und_tag_zusatz", "je_aktie_und_tag_welt", "absicherung", "wertpapierliste", "openfigi",
              "nicht_abgesichert", "nicht_abgesichert_je_vergleich", "welt", "ranglisten_welt", "abstimmung_nasdaq", "abstimmung_nocp")
    data = {
        "format": TRANSFER_FORMAT,
        "stand": sid,
        "auswahl": auswahl,
        "abgerufen_utc": report["abgerufen_utc"],
        "gruppen": {str(i): g for i, g in sorted(groups.items())},
        "verglichen_nasdaq": sorted(int(i) for i in compared),
        "verglichen_zusatz": {str(i): source for i, source in sorted(alt_compared.items())},
        "ohne_vergleichskurse": {str(i): reason for i, reason in sorted(no_prices.items())},
        "nicht_abgesichert": {str(i): reason for i, reason in sorted((unsecured or {}).items())},
        "fehlgeschlagen": {str(i): reason for i, reason in sorted(failures.items())},
        "info": {str(i): value for i, value in sorted(info.items())},
        "luecken": {str(i): value for i, value in sorted((gaps or {}).items())},
        "abdeckung_je_gruppe": report["abdeckung_je_gruppe"],
        "kategorien": report["kategorien"],
        "zaehler": {k: report.get(k) for k in counts if k in report},
        "varianten": names,
        **variants,
    }
    data["pruefsumme"] = hashlib.sha256(canonical({v: variants[v] for v in names})).hexdigest()[:16]
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
COMBINED = ("a", "b", "c", "d", "bc", "cd", "bcd", "ac", "acd")
COMBINED_TEXT = {
    "a": "(a) Nasdaq-Historie an allen abweichenden Tagen",
    "b": "(b) offizieller Schlusskurs (NOCP) an allen Tagen, an denen er vom Stand abweicht",
    "c": "(c) Zusatzquelle (CNBC) an allen abweichenden Tagen – US-Aktien ohne Nasdaq-Kurse",
    "d": "(d) CNBC an allen abweichenden Tagen – Aktien außerhalb der US-Auswahl",
    "bc": "(b)+(c) offizieller Schlusskurs und CNBC gemeinsam (US-Auswahl)",
    "cd": "(c)+(d) alle CNBC-Kurse gemeinsam",
    "bcd": "(b)+(c)+(d) offizieller Schlusskurs und alle CNBC-Kurse gemeinsam",
    "ac": "(a)+(c) Nasdaq-Historie und CNBC (US-Auswahl)",
    "acd": "(a)+(c)+(d) Nasdaq-Historie und alle CNBC-Kurse",
}
UNIONS = {"bc": ("b", "c"), "cd": ("c", "d"), "bcd": ("b", "c", "d"), "ac": ("a", "c"), "acd": ("a", "c", "d")}
FOCUS_VARIANTS = ("b", "bc", "bcd")  # offizieller Schlusskurs und CNBC (Auftrag 25.10.2026, 09:20 Uhr, Punkt 1) – zuerst ausgegeben
# Wechselwirkung (P, Q, gemeinsam): ob Änderungen erst gemeinsam entstehen oder sich aufheben (Auftrag 25.10.2026, 09:20 Uhr, Punkt 1)
INTERACTIONS = (("b", "c", "bc"), ("b", "cd", "bcd"), ("c", "d", "cd"), ("a", "c", "ac"), ("a", "cd", "acd"))
SOURCE_OF_VARIANT = {"a": "Nasdaq-Historie", "b": "offizieller Schlusskurs (NOCP)", "c": "Zusatzquelle", "d": "CNBC (außerhalb der US-Auswahl)"}


def source_map(legs: dict[str, dict], present: list[str]) -> dict[int, dict[int, list[tuple[str, str, float, str]]]]:
    """Welche Quelle für welche Aktie an welchem Tag in den gemeinsamen Varianten (b), (c), (d) verwendet wird: je Aktie und Tag die
    Varianten mit Quelle, Abweichung in % und Einordnung – mehr als ein Eintrag wäre eine Überschneidung (in den Varianten
    ausgeschlossen: NOCP nur für Aktien mit Nasdaq-Kursen, Zusatzquellen nur ohne, CNBC außerhalb der US-Auswahl)."""
    out: dict[int, dict[int, list[tuple[str, str, float, str]]]] = {}
    for leg in present:
        t = legs[leg]
        for v in ("b", "c", "d"):
            for key, rows in (t.get(v) or {}).items():
                source = {"b": "nocp", "c": (t.get("verglichen_zusatz") or {}).get(key, "zusatzquelle"), "d": "cnbc_welt"}[v]
                for r in rows:
                    out.setdefault(int(key), {}).setdefault(int(r[0]), []).append((v, source, float(r[2]), str(r[3])))
    return out


def _bucket10(covered: int, total: int) -> str:
    if total and covered == total:
        return "alle"
    if covered == 0:
        return "keine"
    return "mehr_als_die_haelfte" if covered * 2 > total else "bis_zur_haelfte"


def universe(stand: nachrechnen.Stand, instruments: dict, legs: dict[str, dict], present: list[str], start_day: int, cutoff: int,
             per_stock: dict | None = None) -> dict:
    """Abdeckung des ganzen Aktienuniversums der App (Auftrag Punkt 6) – nach Börse, Aktien, Tagen im Prüfzeitraum und Ranglisten:
    abgesichert verglichen, nicht ausreichend abgesichert, ohne Vergleichskurse, ohne Antwort oder nicht ausgewählt. ``per_stock``
    (falls angegeben) erhält je Aktie die Plätze unter den ersten 10 und auf Platz 1 aller Ranglisten („top10“, „platz1“) und die
    Ranglisten, deren Platz 1 keinen abgesicherten Vergleich hat („platz1_ungeprueft“: Tage, Gruppe, Gewichtung, Aktie, Zustand)."""
    n = len(instruments["isin"])
    keys = instruments.get("exchange_key") or [None] * n
    has_series = instruments.get("has_series") or [True] * n
    state: dict[int, str] = {}
    compared_days: dict[int, int] = {}
    for leg in present:
        t = legs[leg]
        for i in t.get("verglichen_nasdaq") or []:
            state[int(i)] = "abgesichert"
        for key in t.get("verglichen_zusatz") or {}:
            state[int(key)] = "abgesichert"
        for name, label in (("nicht_abgesichert", "nicht_abgesichert"), ("ohne_vergleichskurse", "ohne_vergleichskurse"), ("fehlgeschlagen", "ohne_antwort")):
            for key in t.get(name) or {}:
                state.setdefault(int(key), label)
        for key, value in (t.get("info") or {}).items():
            if isinstance(value, dict) and value.get("tage_verglichen") is not None:
                compared_days[int(key)] = int(value["tage_verglichen"])
    top10: Counter = Counter()
    first: Counter = Counter()
    rankings: Counter = Counter()
    unchecked_leaders: list[tuple[int, str, int, int, str]] = []
    for h in range(1, 91):
        win = stand.get(f"windows/{h}.full.bin")
        stand.drop(f"windows/{h}.full.bin")
        orders = win["orders"]
        lists = [("A", 0, orders.get("v0") or []), ("B", 0, orders.get("v0l") or [])]
        for group, label in (("u", "A"), ("ul", "B")):
            lists += [(label, int(w), values) for w, values in (orders.get(group) or {}).items() if str(w) != "0"]
        for label, w, values in lists:
            head = [int(x) for x in values[:10]]
            if not head:
                continue
            covered = sum(1 for i in head if state.get(i) == "abgesichert")
            rankings["ranglisten"] += 1
            rankings[f"erste_10_abgesichert_{_bucket10(covered, len(head))}"] += 1
            rankings["plaetze_erste_10"] += len(head)
            rankings["plaetze_erste_10_abgesichert"] += covered
            rankings["platz_1"] += 1
            rankings["platz_1_abgesichert"] += state.get(head[0]) == "abgesichert"
            if state.get(head[0]) != "abgesichert":
                unchecked_leaders.append((h, label, w, head[0], state.get(head[0], "nicht_ausgewaehlt")))
            for k, i in enumerate(head):
                top10[i] += 1
                first[i] += k == 0
    if per_stock is not None:
        per_stock.update(top10=top10, platz1=first, platz1_ungeprueft=unchecked_leaders)
    by_exchange: dict[str, Counter] = {}
    for i in range(n):
        c = by_exchange.setdefault(keys[i] or "ohne_boerse", Counter())
        c["aktien"] += 1
        st = state.get(i, "nicht_ausgewaehlt")
        c[f"aktien_{st}"] += 1
        if top10.get(i):
            c["aktien_unter_ersten_10"] += 1
            c[f"aktien_unter_ersten_10_{st}"] += 1
            c["plaetze_erste_10"] += top10[i]
            c["plaetze_platz_1"] += first.get(i, 0)
            if st == "abgesichert":
                c["plaetze_erste_10_abgesichert"] += top10[i]
                c["plaetze_platz_1_abgesichert"] += first.get(i, 0)
        if not has_series[i]:
            c["ohne_kursreihe"] += 1
            continue
        c["tage_stand"] += len(own_series(stand, instruments, i, start_day, cutoff))
        if st == "abgesichert":
            c["tage_verglichen"] += compared_days.get(i, 0)
    total: Counter = Counter()
    for c in by_exchange.values():
        total.update(c)
    return {"je_boerse": {k: dict(v) for k, v in sorted(by_exchange.items(), key=lambda kv: (-kv[1]["aktien"], kv[0]))}, "gesamt": dict(total), "ranglisten": dict(rankings),
            "zeitraum": [nachrechnen._iso(start_day), nachrechnen._iso(cutoff)]}


def combine(stand: nachrechnen.Stand, sid: str, transfers: dict[str, dict | None], problems: list[str] | None = None, clock=time.monotonic) -> dict:
    """Gemeinsame Neuberechnung: die Vergleichskurse aller Prüfjobs zusammen gegen denselben unveränderten Stand – je Variante alle
    Ranglisten neu; dazu (b)+(c), (b)+(c)+(d) u. a. gemeinsam mit der Wechselwirkung der Teile (erst gemeinsam, aufgehoben, auch
    einzeln), jede Variante je Job allein, die Quelle je Aktie und Tag und die Abdeckung des ganzen Aktienuniversums. Jeder neue
    Platz 1 mit Score, Perzentilen und der kleinsten Auslösermenge (Suche mit benannter Grenze)."""
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
            problems.append(f"{JOB_TEXT[leg]}: keine Übergabe")
        elif t.get("format") != TRANSFER_FORMAT or t.get("stand") != sid or t.get("auswahl") != leg:
            problems.append(f"{JOB_TEXT[leg]}: Übergabe passt nicht (Format, Stand oder Job)")
        else:
            legs[leg] = t
    present = [leg for leg in LEGS if leg in legs]
    us_present = [leg for leg in US_LEGS if leg in legs]
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

    variants = {v: subs(present, v) for v in ("a", "b", "c", "d")}
    clash: Counter = Counter()  # dieselbe Aktie in zwei Teilen einer gemeinsamen Variante (ausgeschlossen – gezählt)
    for name, parts in UNIONS.items():
        merged: dict = {}
        for part in parts:
            for i, value in variants[part].items():
                if i in merged:
                    clash[name] += 1
                merged.setdefault(i, value)  # Vorrang in der Reihenfolge der Teile (b vor c vor d) – nur bei Überschneidung
        variants[name] = merged
    for leg in us_present:
        for v in ("a", "b", "c"):
            variants[f"{v}@{leg}"] = subs([leg], v)
    if "erste10" in legs and "plaetze11_20" in legs:
        for v in ("a", "b"):
            variants[f"{v}@erste20"] = subs(["erste10", "plaetze11_20"], v)
    interaction_raw: dict = {}
    effects = ranking_effects(stand, variants, liquid, min_trend, set(top10), attribute=set(COMBINED), order_details=set(COMBINED), interactions=list(INTERACTIONS),
                              interaction_out=interaction_raw, clock=clock)

    def leaders(changes: list[dict]) -> dict[tuple, tuple]:
        return {(c["h"], c["gruppe"], c["w"]): tuple(c["platz1"]) for c in changes if c.get("platz1")}

    for v in ("a", "b", "c"):
        single = {leg: leaders(effects[f"{v}@{leg}"][2]) for leg in us_present}
        for c in effects[v][2]:
            if c.get("platz1"):
                key = (c["h"], c["gruppe"], c["w"])
                c["auch_einzeln"] = [leg for leg in us_present if single[leg].get(key) == tuple(c["platz1"])]
    singles = {v: leaders(effects[v][2]) for v in ("a", "b", "c", "d")}
    for v, parts in UNIONS.items():
        for c in effects[v][2]:
            if c.get("platz1"):
                key = (c["h"], c["gruppe"], c["w"])
                c["gleich_mit_teil"] = [p for p in parts if singles[p].get(key) == tuple(c["platz1"])]
                c["anders_mit_teil"] = [p for p in parts if key in singles[p] and singles[p][key] != tuple(c["platz1"])]
    only_separate: dict[str, list[dict]] = {}
    for v in ("a", "b", "c"):
        together = leaders(effects[v][2])
        rows = []
        for leg in us_present:
            for c in effects[f"{v}@{leg}"][2]:
                if c.get("platz1") and together.get((c["h"], c["gruppe"], c["w"])) != tuple(c["platz1"]):
                    rows.append({"job": leg, **c})
        only_separate[v] = rows

    info: dict[int, dict] = {}
    gap_info: dict[int, dict] = {}
    compared_any: set[int] = set()
    no_prices: set[int] = set()
    unsecured: set[int] = set()
    failed: set[int] = set()
    for leg in present:
        t = legs[leg]
        info.update({int(k): v for k, v in t["info"].items()})
        gap_info.update({int(k): v for k, v in (t.get("luecken") or {}).items()})
        compared_any |= set(int(i) for i in t["verglichen_nasdaq"]) | {int(k) for k in t["verglichen_zusatz"]}
        no_prices |= {int(k) for k in t["ohne_vergleichskurse"]}
        unsecured |= {int(k) for k in t.get("nicht_abgesichert") or {}}
        failed |= {int(k) for k in t["fehlgeschlagen"]}
    us_set = us_stocks(instruments)
    # Plätze unter den ersten 10 und auf Platz 1 je Aktie über alle Aktien (bis zum Lauf 40181869022 nur die der US-Auswahl – Aktien
    # außerhalb standen in der Zuordnung der Buchstaben mit „unter den ersten 10 in 0 Ranglisten“, auch auf Platz 1)
    per_stock: dict = {}
    universe_report = universe(stand, instruments, legs, present, start_day, cutoff, per_stock=per_stock)

    def state_of(i: int) -> str:
        if i in compared_any:
            return "verglichen"
        if i in failed:
            return "ohne_antwort"
        if i in unsecured:
            return "nicht_abgesichert"
        if i in no_prices:
            return "ohne_vergleichskurse"
        if i in missing:
            return "job_fehlt"
        return "keine_us_aktie" if i not in us_set else "nicht_ausgewaehlt"

    names = Lettering([], state_of, info, per_stock.get("top10") or top10, gaps=gap_info, first_places=per_stock.get("platz1"))
    notes = {v: day_notes(v) for v in ("a", "b", "c", "d")}
    for name, parts in UNIONS.items():
        merged_notes: dict = {}
        for part in parts:
            for i, value in notes[part].items():
                merged_notes.setdefault(i, value)
        notes[name] = merged_notes
    changes = {}
    for v in COMBINED:
        rows = names.changes(effects[v][2], notes[v])
        for row, raw in zip(rows, effects[v][2]):
            for field in ("auch_einzeln", "gleich_mit_teil", "anders_mit_teil"):
                if field in raw:
                    row[field] = raw[field]
        changes[v] = rows
    separate_rows = {}
    for v, rows in only_separate.items():
        lettered = names.changes(rows, notes[v])
        for row, raw in zip(lettered, rows):
            row["job"] = raw["job"]
        separate_rows[v] = lettered
    interactions = {}
    for key, value in interaction_raw.items():
        examples = []
        for x in value["beispiele"]:
            examples.append({**{k: x[k] for k in ("h", "gruppe", "w", "art")}, "platz1": [names(j) for j in x["platz1"]],
                             "erste10": [[names(j) for j in members] for members in x["erste10"]]})
        interactions[key] = {**value, "beispiele": examples}
    # Quelle je Aktie und Tag in den gemeinsamen Varianten (b), (c), (d) – mit Prüfsumme über (Aktie, Tag, Variante)
    mapping = source_map(legs, present)
    doubled = sum(1 for days in mapping.values() for entries in days.values() if len(entries) > 1)
    flat = sorted((i, d, e[0]) for i, days in mapping.items() for d, entries in days.items() for e in entries)
    by_source: Counter = Counter()
    for i, days in mapping.items():
        kinds = {e[1] for entries in days.values() for e in entries}
        for kind in kinds:
            by_source[f"aktien_{kind}"] += 1
        for entries in days.values():
            for e in entries:
                by_source[f"tage_{e[1]}"] += 1
    source_rows = []
    for i in sorted(mapping, key=lambda j: (-top10.get(j, 0), j)):
        days = mapping[i]
        kinds = sorted({e[1] for entries in days.values() for e in entries})
        source_rows.append({"aktie": names(i), "quelle": kinds, "tage": [[nachrechnen._iso(d), e[0], e[1], e[2], e[3]] for d in sorted(days) for e in days[d]]})
    sources = {"aktien": len(mapping), "aktientage": len(flat), "ueberschneidung_aktientage": doubled, "ueberschneidung_aktien_in_varianten": dict(clash),
               "je_quelle": dict(by_source), "pruefsumme": hashlib.sha256(canonical(flat)).hexdigest()[:16], "je_aktie": source_rows}
    coverage: dict[str, Counter] = {g: Counter() for g in ALL_GROUPS}
    categories: dict[str, Counter] = {}
    counts: dict[str, Counter] = {}
    for leg in present:
        for g, c in legs[leg]["abdeckung_je_gruppe"].items():
            coverage.setdefault(g, Counter()).update(c)
        for name, c in (legs[leg].get("kategorien") or {}).items():
            categories.setdefault(name, Counter()).update(c)
        z = legs[leg]["zaehler"]
        for name in ("tage", "ursachen", "nocp_vergleich", "nocp_ursachen", "ungeklaert_gruende", "ohne_vergleichskurse_kuerzel", "ohne_nasdaq_boerse", "je_aktie_und_tag",
                     "je_aktie_und_tag_zusatz", "absicherung", "openfigi", "detailabruf", "nicht_abgesichert_je_vergleich", "abstimmung_nasdaq", "abstimmung_nocp"):
            counts.setdefault(name, Counter()).update(z.get(name) or {})
        zq = z.get("zusatzquellen") or {}
        counts.setdefault("zusatzquellen_pruefungen", Counter()).update(zq.get("pruefungen") or {})
        counts.setdefault("zusatzquellen_tage", Counter()).update(zq.get("tage") or {})
        counts.setdefault("zusatzquellen_muster", Counter()).update(zq.get("muster") or {})
        counts.setdefault("otc_lasttradetime", Counter()).update(zq.get("otc_lasttradetime") or {})
        if leg == WORLD_LEG:
            counts.setdefault("je_aktie_und_tag_welt", Counter()).update(z.get("je_aktie_und_tag_welt") or {})
            w = z.get("welt") or {}
            counts.setdefault("welt_zaehler", Counter()).update(w.get("zaehler") or {})
            counts.setdefault("welt_ursachen", Counter()).update(w.get("ursachen") or {})
            for exchange, c in (w.get("je_boerse") or {}).items():
                counts.setdefault(f"welt_boerse_{exchange}", Counter()).update(c)
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
        "ausgewaehlt_welt": sum(1 for g in group_of.values() if g == "welt"),
        "nicht_uebergeben": len(missing),
        "davon_aus_den_ersten_20": from_top,
        "plaetze": places,
        "abdeckung_je_gruppe": {g: dict(c) for g, c in coverage.items() if c},
        "kategorien": {name: dict(c) for name, c in categories.items()},
        "zaehler": {name: dict(c) for name, c in counts.items()},
        "je_aktie_und_tag": dict(counts.get("je_aktie_und_tag") or {}),
        "je_aktie_und_tag_zusatz": dict(counts.get("je_aktie_und_tag_zusatz") or {}),
        "je_aktie_und_tag_welt": dict(counts.get("je_aktie_und_tag_welt") or {}),
        "ranglisten": totals,
        "aenderungen": changes,
        "nur_getrennt": separate_rows,
        "wechselwirkung": interactions,
        "quellen_je_aktie_und_tag": sources,
        "universum": universe_report,
        "vergleich_mit_lauf": reference,
        "weitere_buchstaben": names.legend,
    }
    # Ranglisten, deren Platz 1 keinen abgesicherten Vergleich hat (Lücke der Abdeckung je Rangliste) – Buchstaben erst hier
    # vergeben, damit die Buchstaben der übrigen Aktien dieselben bleiben wie ohne diese Liste
    report["universum"]["platz1_ungeprueft"] = [{"h": h, "gruppe": label, "w": w, "aktie": names(i), "zustand": st}
                                               for h, label, w, i, st in per_stock.get("platz1_ungeprueft") or []]
    all_top10 = per_stock.get("top10") or {}
    for i in sorted(gap_info, key=lambda j: (-all_top10.get(j, 0), j)):  # Lücken je Aktie aller Jobs mit Buchstaben
        names(i)
    report["zuordnung"] = names.mapping(stand)
    gaps = sum(c.get("keine_vergleichskurse", 0) + c.get("abruf_fehlgeschlagen", 0) + c.get("nicht_abgesichert", 0) for c in coverage.values())
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
    "unvollstaendig": "Kursursachen: UNVOLLSTÄNDIG – {n} Aktien ohne Antwort einer Quelle, {k} ohne Vergleichskurse, {s} nicht abgesichert; {u} von {a} abweichenden Aktientagen ungeklärt ({p} davon mit plausibler Erklärung)",
    "ungeklaert": "Kursursachen: NICHT VOLLSTÄNDIG BELEGT – {u} von {a} abweichenden Aktientagen ungeklärt ({p} davon mit plausibler Erklärung)",
    "belegt": "Kursursachen: jede Abweichung belegt ({a} Aktientage)",
    "keine_abweichungen": "Kursursachen: keine Abweichungen in den abgesicherten Vergleichen",
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


JOB_TEXT = {"erste10": "erste 10", "plaetze11_20": "Plätze 11–20", "zufall": "Zufallsstichprobe", "erste20": "erste 20", "welt": "außerhalb der US-Auswahl"}


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
    search = c.get("suche") or {}
    if c.get("nicht_untersucht"):
        why = {"zeitbudget": f"Zeitbudget der Suche ({ATTRIBUTION_BUDGET_S // 60} min) erschöpft", "grenze": f"mehr als {MAX_ATTRIBUTIONS} neue Plätze 1 in dieser Variante"}.get(
            str(c["nicht_untersucht"]), "in dieser Variante nicht vorgesehen")
        parts.append(f"Auslöser nicht untersucht ({why}) – {c.get('ersetzte_aktien_im_zeitraum', 0)} ersetzte Aktien im Zeitraum")
    elif not triggers:
        parts.append(f"keine Auslösermenge gefunden ({search.get('auswertungen', 0)} Auswertungen über {c.get('ersetzte_aktien_im_zeitraum', 0)} ersetzte Aktien)")
    else:
        n_cand = search.get("kandidaten", c.get("ersetzte_aktien_im_zeitraum", 0))
        how = "" if search.get("schnell", True) else "; Platz 1 je Teilmenge mit der unabhängigen Rechnung (schnelle Rechnung wich ab)"
        if search.get("nachgewiesen"):
            parts.append(f"kleinste Auslösermenge {search.get('groesse')} {'Aktie' if search.get('groesse') == 1 else 'Aktien'} – nachweislich: jede kleinere Teilmenge der "
                         f"{n_cand} ersetzten Aktien geprüft, keine ergibt diesen Platz 1 ({search.get('auswertungen', 0)} Auswertungen{how})")
        else:
            parts.append(f"Auslösermenge mit {search.get('groesse')} Aktien – irreduzibel, aber NICHT nachweislich die kleinste: Teilmengen bis {search.get('geprueft_bis', 0)} "
                         f"Aktien vollständig geprüft, die kleinste hat mindestens {search.get('mindestens', 0)} ({search.get('auswertungen', 0)} Auswertungen über {n_cand} ersetzte Aktien{how})")
        for tr in triggers:
            days = ", ".join(f"{d['tag']} {d['abweichung_pct']:+.3f} % ({_cause_label(d['ursache'])})" for d in tr["tage"]) or "keine ersetzten Tage im Zeitraum"
            more = f" und {tr['weitere_tage']} weitere Tage" if tr.get("weitere_tage") else ""
            parts.append(f"auslösend {tr['aktie']}{_trigger_values(tr, c['w'], before, after)}: {days}{more}")
        alone = c.get("allein_ausreichend") or []
        parts.append("allein ausreichend: " + (" ".join(alone) + (" (jede für sich)" if len(alone) > 1 else "") if alone else "keine einzelne Aktie – nur zusammen"))
        others = c.get("weitere_mengen") or []
        if others or c.get("mengen_gleicher_groesse", 0) > 1 + len(others):
            parts.append(f"gleich kleine Auslösermengen insgesamt {c.get('mengen_gleicher_groesse', 0)}" + (": " + ", ".join("[" + " ".join(m) + "]" for m in others) if others else ""))
        for g in c.get("gegenprobe") or []:
            parts.append(
                f"Gegenprobe {g['aktie']} mit der unabhängigen Rechnung: allein → Platz 1 {g['allein']}" + (" (wie mit allen)" if g["allein"] == after else "")
                + f"; alle übrigen ersetzten Kurse ohne {g['aktie']} → Platz 1 {g['ohne']}" + (" (bisheriger Spitzenreiter: ohne diese Aktie kein Wechsel)" if g["ohne"] == before else "")
                + ("" if g.get("wie_suche", True) else " – ABWEICHEND von der schnellen Rechnung der Suche")
            )
        single = c.get("einzeln_unabhaengig")
        if single:
            parts.append(f"jede der {single['geprueft']} ersetzten Aktien einzeln auch mit der unabhängigen Rechnung: allein ausreichend "
                         + (" ".join(single["allein"]) or "keine") + (" – wie die Suche" if single["wie_suche"] else " – ABWEICHEND von der Suche"))
        without = c.get("ohne_ausloeser")
        if without is not None and len(triggers) > 1:
            rest = max(0, c.get("ersetzte_aktien_im_zeitraum", 0) - len(triggers))
            parts.append(
                f"mit den übrigen {rest} ersetzten Aktien, aber ohne die Auslösermenge: "
                + (f"Platz 1 bleibt {before} (Auslöser nötig)" if without == before else (f"Platz 1 wechselt trotzdem zu {after}" if without == after else f"Platz 1 wäre {without}"))
            )
    if "auch_einzeln" in c:
        jobs = c["auch_einzeln"]
        parts.append("ebenso mit den Kursen eines Jobs allein: " + ", ".join(JOB_TEXT.get(j, j) for j in jobs) if jobs else "nur gemeinsam – mit den Kursen keines Jobs allein")
    if "gleich_mit_teil" in c:
        same_parts, other_parts = c["gleich_mit_teil"], c.get("anders_mit_teil") or []
        parts.append(("ebenso mit " + ", ".join(f"({x}) allein" for x in same_parts)) if same_parts else "erst gemeinsam – mit keinem Teil allein dieser neue Platz 1")
        if other_parts:
            parts.append("mit " + ", ".join(f"({x}) allein" for x in other_parts) + " ein anderer neuer Platz 1")
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


# Kurzform für die Hinweise des Jobs „gemeinsame Wirkung“ (GitHub zeigt je Job höchstens 50 Hinweise; im Lauf 40181869022 fehlten
# 42 von 86 Teilen): Fundstelle „Tage/Gruppe/Gewichtung der Gleichmäßigkeit in %“, Legende im ersten Teil jedes Abschnitts.
# Die Zusammenfassung des Jobs behält die Langform.
SHORT_FORM_NOTE = "Kurzform: Rangliste als Tage/Gruppe/Gewichtung der Gleichmäßigkeit in % (z. B. 45/A/80 = 45 Tage, Gruppe A, 80/20); * = Kurse dieser Aktie ersetzt"


def _short_method(c: dict) -> str:
    return f"{c['h']}/{c['gruppe']}/{c['w']}"


def _places_text(places: list[int]) -> str:
    places = sorted(int(p) for p in places)
    if places and places == list(range(places[0], places[-1] + 1)) and len(places) > 2:
        return f"{places[0]}–{places[-1]}"
    return ", ".join(str(p) for p in places)


def _member_rows_short(changes: dict, variants: tuple[str, ...]) -> list[str]:
    """Andere Aktien unter den ersten 10 je Variante in einer Zeile (Kurzform)."""
    rows = [SHORT_FORM_NOTE] if any(x.get("raus") or x.get("rein") for v in variants for x in changes.get(v) or []) else []
    for v in variants:
        items = []
        for x in changes.get(v) or []:
            if not (x.get("raus") or x.get("rein")):
                continue
            marked = set(x.get("ersetzt") or [])
            show = lambda names: " ".join(f"{n}*" if n in marked else n for n in names) or "–"  # noqa: E731
            items.append(f"{_short_method(x)} raus {show(x['raus'])} rein {show(x['rein'])}")
        if items:
            rows.append(f"gemeinsam {v} ({len(items)}): " + "; ".join(items))
    return rows


def _order_rows_short(changes: dict, variants: tuple[str, ...]) -> list[str]:
    """Andere Reihenfolge der ersten 10 bei gleichen Aktien je Variante in einer Zeile (Kurzform: Plätze, vorher → nachher)."""
    rows = []
    for v in variants:
        items = []
        for x in changes.get(v) or []:
            o = x.get("reihenfolge")
            if not o:
                continue
            marked = set(x.get("ersetzt") or [])
            show = lambda names: " ".join(f"{n}*" if n in marked else n for n in names)  # noqa: E731
            items.append(f"{_short_method(x)} Pl. {_places_text(o['plaetze'])}: {show(o['vorher'])} → {show(o['nachher'])}")
        if items:
            rows.append(f"gemeinsam {v} ({len(items)}): " + "; ".join(items))
    return ([SHORT_FORM_NOTE] + rows) if rows else []


def _same_leader(x: dict, y: dict) -> bool:
    """Derselbe Wechsel mit denselben Werten (Spitzenreiter, Rendite, R², Score, Perzentile, Vergleichsmenge, Auslöser)."""
    keys = ("platz1", "platz_des_neuen_vorher", "rendite_pct", "r2", "score", "vergleichsmenge")
    triggers = lambda c: [t["aktie"] for t in c.get("ausloeser") or []]  # noqa: E731
    return all(x.get(k) == y.get(k) for k in keys) and triggers(x) == triggers(y)


def _leader_short(c: dict, variant: str, n: int, total: int, ref: str, ref_n: int, ref_total: int) -> str:
    """Kurzform eines neuen Platzes 1, der mit denselben Werten schon in ``ref`` steht (Langform dort und in der Zusammenfassung)."""
    before, after = c["platz1"]
    search = c.get("suche") or {}
    triggers = " ".join(t["aktie"] for t in c.get("ausloeser") or []) or "–"
    size = search.get("groesse")
    proof = (f"kleinste Auslösermenge {size} – nachweislich ({search.get('kandidaten', c.get('ersetzte_aktien_im_zeitraum', 0))} ersetzte Aktien, "
             f"{search.get('auswertungen', 0)} Auswertungen)") if search.get("nachgewiesen") else (
             f"Auslösermenge mit {size} Aktien – NICHT nachweislich die kleinste (mindestens {search.get('mindestens', 0)})")
    checks = "; ".join(f"Gegenprobe {g['aktie']} (unabhängige Rechnung): allein → {g['allein']}, ohne → {g['ohne']}"
                       + ("" if g.get("wie_suche", True) else " – ABWEICHEND von der Suche") for g in c.get("gegenprobe") or [])
    single = c.get("einzeln_unabhaengig")
    if single:
        checks += (f"; einzeln unabhängig {single['geprueft']} geprüft: allein ausreichend " + (" ".join(single["allein"]) or "keine")
                   + ("" if single["wie_suche"] else " – ABWEICHEND von der Suche"))
    same = c.get("gleich_mit_teil")
    tail = ("; ebenso mit " + ", ".join(f"({x}) allein" for x in same)) if same else ("; erst gemeinsam – mit keinem Teil allein" if same is not None else "")
    return (f"{variant} {n}/{total} – {_short_method(c)}: bisher {before}, neu {after} – Rendite, R², Score und Perzentile wie in ({ref}) {ref_n}/{ref_total}; "
            f"{proof}: {triggers}" + (f"; {checks}" if checks else "") + tail)


def _order_line(c: dict, variant: str) -> str:
    o = c["reihenfolge"]
    marked = set(c.get("ersetzt") or [])
    def show(names: list[str]) -> str:
        return " ".join(f"{x}*" if x in marked else x for x in names)
    return f"{variant} – {_method(c)}: Plätze {', '.join(str(k) for k in o['plaetze'])} – vorher {show(o['vorher'])}, nachher {show(o['nachher'])}"


LEGEND_STATE = {
    "ohne_antwort": "ausgewählt, aber ohne Antwort von Nasdaq – Kurse in allen Varianten unverändert",
    "ohne_vergleichskurse": "ausgewählt, aber ohne Vergleichskurse (Nasdaq und Zusatzquellen) – Kurse in allen Varianten unverändert",
    "nicht_abgesichert": "ausgewählt, Vergleichskurse vorhanden, aber Zuordnung nicht ausreichend abgesichert – Kurse in allen Varianten unverändert",
    "anderer_job": "in einem anderen Job geprüft – in diesem Job Kurse unverändert",
    "us_auswahl": "US-Aktie der US-Auswahl – in den US-Jobs geprüft, in diesem Job Kurse unverändert",
    "job_fehlt": "ausgewählt, aber ihr Job hat keine Übergabe geliefert – Kurse unverändert",
    "keine_us_aktie": "keine US-Aktie (Nasdaq führt sie nicht) – Kurse unverändert",
    "nicht_ausgewaehlt": "US-Aktie, aber weder unter den ersten 20 einer Rangliste noch in der Zufallsstichprobe – Kurse unverändert",
}


GAP_TEXT = {
    **WORLD_RESULT_TEXT,
    "stand_ohne_kurse_im_zeitraum": "Stand ohne Kurse im Zeitraum",
    "nasdaq_ohne_kurse": "Nasdaq ohne Kurse, Zusatzquellen nicht abgefragt",
    "weder_nasdaq_noch_zusatzquelle": "weder Nasdaq noch eine Zusatzquelle mit Kursen",
    "zusatzquelle_nicht_abgesichert": "Kurse einer Zusatzquelle, Zuordnung nicht ausreichend abgesichert",
    "nasdaq_nicht_abgesichert": "Nasdaq-Kurse, Zuordnung nicht ausreichend abgesichert",
}


def _places(entry: dict) -> str:
    first = f", Platz 1 in {entry['platz1']}" if entry.get("platz1") else ""
    return f"unter den ersten 10 in {entry.get('top10', 0)} Ranglisten{first}"


def _legend(entry: dict) -> str:
    if entry.get("zustand") in LEGEND_STATE:
        text = LEGEND_STATE[entry["zustand"]]
        gap = entry.get("luecke")
        if gap:
            failed = ", ".join(absicherung.CHECK_TEXT.get(x, x) for x in (gap.get("pruefungen") or "").split(",") if x)
            text += (f" – {gap.get('boerse', '–')}, {gap.get('kursbereich', '–')}; {_places(entry)}; {gap.get('tage_stand', 0)} Tage im Stand ungeprüft; Grund: "
                     f"{GAP_TEXT.get(gap.get('grund'), gap.get('grund'))}" + (f"; nicht bestanden: {failed}" if failed else "")
                     + (f"; Befund: {gap['befund']}" if gap.get("befund") else ""))
        return text
    if not entry.get("abgefragt", True) or "boerse" not in entry:
        return "nicht abgefragt oder ohne Vergleichskurse – Kurse in allen Varianten unverändert"
    if entry.get("quelle"):
        return (f"{entry['boerse']}, {entry['kursbereich']}; {_places(entry)}; verglichen mit "
                f"{zusatz.SOURCE_TEXT.get(entry['quelle'], WORLD_SOURCE_TEXT.get(entry['quelle'], entry['quelle']))}, abweichend an {entry.get('abweichend', 0)} Tagen")
    nocp = f", ungleich NOCP an {entry.get('nocp_ungleich', 0)} Tagen" if entry.get("nocp_ungleich") else ""
    return (
        f"{entry['boerse']}, {entry['kursbereich']}; {_places(entry)}; "
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
    total = c.get("verglichen", 0) + c.get("keine_vergleichskurse", 0) + c.get("abruf_fehlgeschlagen", 0) + c.get("nicht_abgesichert", 0)
    no_prices = ", ".join(f"{text} {c[key]}" for key, text in (("keine_vergleichskurse_nasdaq_ohne_kurse", "weder Nasdaq noch eine Zusatzquelle"), ("keine_vergleichskurse_stand_ohne_kurse_im_zeitraum", "Stand ohne Kurse im Zeitraum"))
                          + tuple((f"keine_vergleichskurse_{k}", v) for k, v in WORLD_RESULT_TEXT.items() if k not in ("abgesichert", "nicht_abgesichert")) if c.get(key))
    nocp = ", ".join(f"{text} {c[key]}" for key, text in (("nocp_mit_nocp", "mit NOCP"), ("nocp_nocp_nicht_abgesichert", "NOCP nicht abgesichert"), ("nocp_nasdaq_ohne_nocp", "Nasdaq-notiert ohne NOCP"),
                                                           ("nocp_nicht_nasdaq_notiert", "ohne NOCP: nicht Nasdaq-notiert"), ("nasdaq_historie_nicht_abgesichert", "nur NOCP abgesichert")) if c.get(key))
    alt_sources = zusatz.SOURCES + ("cnbc_welt",)
    nasdaq = c.get("verglichen_nasdaq", c.get("verglichen", 0) - sum(c.get(f"verglichen_{q}", 0) for q in alt_sources))
    alt = ", ".join(f"{zusatz.SOURCE_TEXT.get(q, WORLD_SOURCE_TEXT.get(q, q))} {c[f'verglichen_{q}']}" for q in alt_sources if c.get(f"verglichen_{q}"))
    return (
        f"{name}: {total} Aktien – abgesichert verglichen {c.get('verglichen', 0)} (mit Nasdaq {nasdaq}" + (f": {nocp}" if nocp else "") + (f"; mit Zusatzquelle: {alt}" if alt else "") + ")"
        + f"; nicht ausreichend abgesichert {c.get('nicht_abgesichert', 0)}"
        + (" (" + ", ".join(f"{text} {c[key]}" for key, text in (("nicht_abgesichert_nasdaq", "Nasdaq"), ("nicht_abgesichert_zusatzquelle", "Zusatzquelle")) if c.get(key)) + ")"
           if c.get("nicht_abgesichert_nasdaq") or c.get("nicht_abgesichert_zusatzquelle") else "")
        + f"; keine Vergleichskurse {c.get('keine_vergleichskurse', 0)}" + (f" ({no_prices})" if no_prices else "")
        + f"; Abruf fehlgeschlagen {c.get('abruf_fehlgeschlagen', 0)}"
    )


def unique_days(report: dict) -> dict[str, int]:
    """Abweichende Aktientage eines Berichts, je Aktie und Tag genau einmal (Nasdaq-Historie/NOCP zusammengefasst; Zusatzquellen
    und CNBC außerhalb der US-Auswahl betreffen andere Aktien und werden addiert)."""
    out: Counter = Counter()
    for key in ("je_aktie_und_tag", "je_aktie_und_tag_zusatz", "je_aktie_und_tag_welt"):
        out.update(report.get(key) or {})
    return {"abweichend": out.get("belegt", 0) + out.get("plausibel", 0) + out.get("ohne_erklaerung", 0), "ungeklaert": out.get("plausibel", 0) + out.get("ohne_erklaerung", 0),
            "plausibel": out.get("plausibel", 0), **dict(out)}


def _cause_counts(counts: dict, keys) -> str:
    return ", ".join(f"{SHORT_CAUSE.get(k, k)} {counts[k]}" for k in CAUSES if k in keys and counts.get(k)) or "–"


def _category_lines(categories: dict, ursachen: dict, nocp_ursachen: dict, alt_days: dict) -> list[str]:
    """Ergebnisarten je Vergleich (Tage, nur abgesicherte Vergleiche): bestätigte Übereinstimmung, festgestellte Abweichung,
    belegte Ursache, ungeklärt mit plausibler Erklärung, ungeklärt ohne Erklärung, fehlende Prüfmöglichkeit, nicht abgesichert."""
    a = categories.get("nasdaq_historie") or {}
    b = categories.get("offizieller_schlusskurs") or {}
    c = categories.get("zusatzquellen") or {}
    befund_b = ", ".join(f"{NOCP_NOTE.get(k[len('befund_'):], k)} {v}" for k, v in sorted(nocp_ursachen.items()) if k.startswith("befund_")) or "–"
    plausible_b = ", ".join(f"{SHORT_CAUSE.get(k, k)} {v}" for k, v in sorted(nocp_ursachen.items()) if k in PLAUSIBLE) or "–"
    alt_causes = {k[len("ursache_"):]: v for k, v in alt_days.items() if k.startswith("ursache_")}
    second = ", ".join(f"{k[len('zweite_quelle_'):]} {v}" for k, v in sorted(alt_days.items()) if k.startswith("zweite_quelle_")) or "–"
    # die nicht ausreichend abgesicherten Aktien sind Teil der fehlenden Prüfmöglichkeit (nicht zusätzlich) – ausdrücklich so genannt
    unsecured = lambda x, prices="Kurse": (f"{prices} vorhanden, aber Zuordnung nicht ausreichend abgesichert {x.get('nicht_abgesichert_aktien', 0)} "  # noqa: E731
                                           f"(deren {x.get('nicht_abgesichert_tage', 0)} Tage nur gezählt: weder Ersatzkurs noch Bestätigung)")
    return [
        f"Ergebnis gegen die Nasdaq-Historie (Tage, nur abgesicherte Vergleiche): bestätigte Übereinstimmung {a.get('uebereinstimmung', 0)}; festgestellte Abweichung {a.get('abweichung', 0)} – "
        f"davon Ursache belegt {a.get('belegt', 0)} ({_cause_counts(ursachen, EVIDENCE)}), Stand = offizieller Schlusskurs {a.get('stand_ist_nocp', 0)} (abweichend nur die Nasdaq-Historie), "
        f"ungeklärt mit plausibler Erklärung {a.get('plausibel', 0)} ({_cause_counts(ursachen, PLAUSIBLE)}), ungeklärt ohne Erklärung {a.get('ohne_erklaerung', 0)} "
        f"(Befund Stand ≠ NOCP bei Nasdaq-Historie = NOCP {ursachen.get('abweichung_vom_nocp', 0)}, ohne Befund {ursachen.get('ungeklaert', 0)}); fehlende Prüfmöglichkeit: "
        f"{a.get('ohne_vergleich_aktien', 0)} Aktien ohne abgesicherte Nasdaq-Historie – ohne Nasdaq-Kurse {a.get('ohne_vergleich_ohne_kurse', 0)}, {unsecured(a, 'Nasdaq-Kurse')}; "
        f"{a.get('ohne_vergleich_tage', 0)} Tage nur im Stand",
        f"Ergebnis gegen den offiziellen Schlusskurs NOCP (Tage, nur abgesicherte Vergleiche): bestätigte Übereinstimmung {b.get('uebereinstimmung', 0)}; festgestellte Abweichung "
        f"{b.get('abweichung', 0)} – davon Ursache belegt {b.get('belegt', 0)} (NOCP unbereinigt vor einem gemeldeten Split passenden Verhältnisses – nicht ersetzt), "
        f"ungeklärt mit plausibler Erklärung {b.get('plausibel', 0)} ({plausible_b}), ungeklärt ohne Erklärung {b.get('ohne_erklaerung', 0)} (Befund: {befund_b}); "
        f"fehlende Prüfmöglichkeit: {b.get('ohne_vergleich_aktien', 0)} Aktien ohne abgesicherten NOCP – nicht Nasdaq-notiert {b.get('ohne_vergleich_nicht_nasdaq_notiert', 0)} "
        f"(offizieller Schlusskurs der NYSE-Gruppe in den geprüften Quellen nur kostenpflichtig), Nasdaq-notiert ohne NOCP {b.get('ohne_vergleich_nasdaq_ohne_nocp', 0)}, "
        f"ohne Nasdaq-Kurse {b.get('ohne_vergleich_ohne_kurse', 0)}, Nasdaq-Kurse nicht abgesichert und ohne NOCP {b.get('ohne_vergleich_nasdaq_nicht_abgesichert_ohne_nocp', 0)}, "
        f"{unsecured(b, 'NOCP')}; {b.get('ohne_vergleich_tage', 0)} Tage ohne abgesicherten NOCP bei Aktien mit abgesichertem Nasdaq-Vergleich",
        f"Ergebnis gegen die Zusatzquellen (Tage, nur abgesicherte Vergleiche): bestätigte Übereinstimmung {c.get('uebereinstimmung', 0)}; festgestellte Abweichung {c.get('abweichung', 0)} – "
        f"davon Ursache belegt {c.get('belegt', 0)} (Quelle unbereinigt vor einem gemeldeten Split), ungeklärt mit plausibler Erklärung {c.get('plausibel', 0)} "
        f"({_cause_counts(alt_causes, PLAUSIBLE)}), ungeklärt ohne Erklärung {c.get('ohne_erklaerung', 0)}; zweite abgesicherte Quelle an den abweichenden Tagen: {second}; "
        f"fehlende Prüfmöglichkeit: {c.get('ohne_vergleich_aktien', 0)} Aktien ohne abgesicherte Vergleichskurse – ohne Kurse in den geprüften Quellen "
        f"{c.get('ohne_vergleich_ohne_kurse', 0)}, {unsecured(c)}; {c.get('ohne_vergleich_tage', 0)} Tage nur im Stand "
        f"(davon ohne Umsatz bei Yahoo {alt_days.get('nur_im_stand_ohne_umsatz', 0)})",
    ]


def _stock_day_lines(report: dict) -> list[str]:
    """Je Aktie und Tag genau einmal (Auftrag Punkt 2): überlappende Fälle der Vergleiche nicht als unabhängig gezählt."""
    a = report.get("je_aktie_und_tag") or {}
    c = report.get("je_aktie_und_tag_zusatz") or {}
    w = report.get("je_aktie_und_tag_welt") or {}
    u = unique_days(report)
    lines = []
    if a or c:
        lines.append(
            f"Je Aktie und Tag genau einmal gezählt (Nasdaq-Historie und NOCP überschneiden sich – maßgeblich der abgesicherte NOCP, sonst die Nasdaq-Historie): "
            f"verglichen {a.get('verglichen', 0)} Aktientage – bestätigte Übereinstimmung {a.get('uebereinstimmung', 0)}, Ursache belegt {a.get('belegt', 0)}, "
            f"ungeklärt mit plausibler Erklärung {a.get('plausibel', 0)}, ungeklärt ohne Erklärung {a.get('ohne_erklaerung', 0)}; Überschneidung: in beiden Vergleichen abweichend "
            f"{a.get('abweichend_in_beiden', 0)}, nur Nasdaq-Historie {a.get('abweichend_nur_nasdaq_historie', 0)}, nur NOCP {a.get('abweichend_nur_nocp', 0)}; ohne Vergleich "
            f"{a.get('ohne_vergleich', 0)}. Zusatzquellen (andere Aktien, keine Überschneidung): verglichen {c.get('verglichen', 0)} – Übereinstimmung {c.get('uebereinstimmung', 0)}, "
            f"belegt {c.get('belegt', 0)}, plausibel {c.get('plausibel', 0)}, ohne Erklärung {c.get('ohne_erklaerung', 0)}, ohne Vergleich {c.get('ohne_vergleich', 0)}"
        )
    if w:
        lines.append(
            f"CNBC außerhalb der US-Auswahl, je Aktie und Tag: verglichen {w.get('verglichen', 0)} – Übereinstimmung {w.get('uebereinstimmung', 0)}, belegt {w.get('belegt', 0)}, "
            f"plausibel {w.get('plausibel', 0)}, ohne Erklärung {w.get('ohne_erklaerung', 0)}, ohne Vergleich {w.get('ohne_vergleich', 0)}"
        )
    if lines:
        lines.append(f"Zusammen (eindeutige Aktientage): abweichend {u['abweichend']}, davon belegt {u.get('belegt', 0)}, ungeklärt {u['ungeklaert']} (plausibel {u['plausibel']}, "
                     f"ohne Erklärung {u.get('ohne_erklaerung', 0)})")
    return lines


SECURITY_SOURCES = {"nasdaq": "Nasdaq-Historie", "nocp": "offizieller Schlusskurs NOCP", "cnbc": "CNBC", "cnbc_welt": "CNBC (außerhalb der US-Auswahl)", "otc_markets": "OTC Markets",
                    "barchart": "Barchart", "marketwatch": "MarketWatch", "stooq": "Stooq"}
IDENTITY_TEXT = {
    "isin_kuerzel_bestaetigt_schreibweise": "Kürzel in einer dokumentierten anderen Schreibweise der App bestätigt (bestanden)",
    "isin_anderes_kuerzel": "ISIN laut OpenFIGI mit anderem Kürzel",
    "isin_ohne_notierung_der_boerse": "ISIN laut OpenFIGI ohne Notierung an der Börse des Stands",
    "isin_ohne_zuordnung": "ISIN bei OpenFIGI ohne Notierung an einer Börse der App",
    "isin_unbekannt": "ISIN bei OpenFIGI unbekannt",
    "isin_anders": "ISIN der Quelle anders",
    "cusip_anders": "CUSIP der Quelle anders",
    "nicht_geprueft": "OpenFIGI ohne Antwort",
}
ART_TEXT = {"fonds_laut_liste": "Fonds/ETF laut Wertpapierliste", "testwert_laut_liste": "Testwert laut Wertpapierliste",
            "beschreibung_im_namen": "Optionsschein, Bezugsrecht, Einheit oder Anleihe laut Name"}


def _security_lines(summary: dict, listing: dict | None = None, figi: dict | None = None) -> list[str]:
    """Absicherung der Zuordnung je Quelle: abgesichert/geprüft und die Gründe (eine fehlende Angabe gilt nicht als bestanden)."""
    by_source: dict[str, dict] = {}
    for key, value in (summary or {}).items():
        for q in sorted(SECURITY_SOURCES, key=len, reverse=True):
            if key.startswith(q + "_"):
                by_source.setdefault(q, {})[key[len(q) + 1:]] = value
                break
    parts = []
    for q in SECURITY_SOURCES:
        x = by_source.get(q)
        if not x:
            continue
        ok, bad = x.get("abgesichert", 0), x.get("nicht_abgesichert", 0)
        reasons = ", ".join(f"{absicherung.CHECK_TEXT.get(k[len('grund_'):], k[len('grund_'):])} {v}" for k, v in sorted(x.items(), key=lambda kv: -kv[1]) if k.startswith("grund_"))
        detail = []
        identity = {k[len("aktie_"):]: v for k, v in x.items() if k.startswith("aktie_") and k != "aktie_isin_kuerzel_bestaetigt"}
        if identity:
            detail.append("Aktie und Gattung: " + ", ".join(f"{IDENTITY_TEXT.get(k, k)} {v}" for k, v in sorted(identity.items(), key=lambda kv: (-kv[1], kv[0]))))
        art = {k[len("artgrund_"):]: v for k, v in x.items() if k.startswith("artgrund_")}
        if art:
            detail.append("Art: " + ", ".join(f"{ART_TEXT.get(k, k)} {v}" for k, v in sorted(art.items(), key=lambda kv: (-kv[1], kv[0]))))
        parts.append(f"{SECURITY_SOURCES[q]}: abgesichert {ok} von {ok + bad}" + (f" (nicht bestanden: {reasons})" if reasons else "")
                     + (f" [{'; '.join(detail)}]" if detail else ""))
    head = "Absicherung der Zuordnung (Aktie/Gattung über die ISIN laut OpenFIGI, Name und Art laut Quelle, Handelsplatz, Währung, Handelstag, Bereinigung, Kursniveau, Tage – " \
           "jede Prüfung muss bestanden sein, fehlende Angaben gelten nicht als bestanden)"
    extra = []
    if listing:
        extra.append(f"Wertpapierliste {listing.get('status')} ({listing.get('eintraege', 0)} Einträge)")
    if figi:
        extra.append(f"OpenFIGI je ISIN: {_counts(figi)}")
    return [head + (": " + "; ".join(extra) if extra else "") + (" – " + "; ".join(parts) if parts else " – keine Vergleiche")]


def _otc_lines(alt_days: dict, seen: dict) -> list[str]:
    """Beobachtungen zu „lastTradeTime“ (OTC Markets) – keine Zuordnung zu einem Handelstag (Auftrag Punkt 4)."""
    reports = ", ".join(f"{k[len('otc_kursmeldung_'):]} {v}" for k, v in sorted(alt_days.items()) if k.startswith("otc_kursmeldung_")) or "–"
    if not seen:
        return [f"Letzter Abschluss bei OTC Markets (Kursmeldung je Aktie ohne Nasdaq-Kurse): {reports}; keine Zeitstempel"]
    pick = lambda prefix: ", ".join(f"{k[len(prefix):]} {v}" for k, v in sorted(seen.items()) if k.startswith(prefix)) or "–"  # noqa: E731
    exact = sum(v for k, v in seen.items() if k == "zeitstempel_exakt_0_uhr_utc")
    stamped = sum(v for k, v in seen.items() if k in ("zeitstempel_exakt_0_uhr_utc", "zeitstempel_andere_uhrzeit"))
    if exact and exact == stamped:
        reading = (f"Alle {stamped} Zeitstempel liegen genau auf 00:00:00.000 Uhr UTC – als echter Abschlusszeitpunkt unwahrscheinlich, ein Hinweis auf ein kodiertes "
                   "Tagesdatum; welcher Tag kodiert ist, belegt das nicht.")
    elif stamped:
        reading = (f"Genau auf 00:00:00.000 Uhr UTC liegen {exact} von {stamped} Zeitstempeln; die übrigen tragen eine andere Uhrzeit (Minute, Sekunde und Bruchteil "
                   "oben) – ob es echte Zeitpunkte (z. B. eines Abschlusses nach 20 Uhr New York) oder kodierte Tagesdaten sind, belegen die Beobachtungen nicht.")
    else:
        reading = "Keine lesbaren Zeitstempel."
    return [
        f"Letzter Abschluss bei OTC Markets (Kursmeldung je Aktie ohne Nasdaq-Kurse): {reports}. Feld „lastTradeTime“ – Bedeutung nicht öffentlich dokumentiert. Zeitstempel: "
        f"{pick('zeitstempel_')}; Einheit {pick('einheit_')}; Uhrzeit UTC – Stunde {pick('stunde_utc_')}, Minute {pick('minute_utc_')}, Sekunde {pick('sekunde_utc_')}, "
        f"Bruchteil der Sekunde {pick('bruchteil_der_sekunde_')}; Tag als UTC-Datum: {pick('utc_lage_')} (Wochentag {pick('utc_wochentag_')}; Yahoo-Umsatz "
        f"{pick('utc_umsatz_yahoo_')}); Tag nach Ortszeit New York: {pick('ny_lage_')} (Wochentag {pick('ny_wochentag_')}; Yahoo-Umsatz {pick('ny_umsatz_yahoo_')}); "
        f"quoteTime der Antwort minus Zeitstempel: {pick('quotetime_minus_stempel_')}; Abruf (Uhr des Prüfrechners) minus Zeitstempel: {pick('abruf_minus_stempel_')}; "
        f"lastSale = letzter Kurs des Stands: {pick('lastsale_gleich_letztem_kurs_des_stands_')}; previousClose = vorletzter Kurs des Stands: "
        f"{pick('previousclose_gleich_vorletztem_kurs_des_stands_')}, = letzter Kurs: {pick('previousclose_gleich_letztem_kurs_des_stands_')}",
        f"Lesart: {reading} Als UTC-Datum fiele ein Stempel der Stunde 00 auf den Tag nach dem letzten Kurstag, nach Ortszeit New York auf den Abend (20 Uhr) des "
        "letzten Kurstags. Der Handelstag wird nicht daraus abgeleitet, welche Umrechnung zum Stand passt: Die Zuordnung bleibt offen, der letzte Abschluss bei OTC Markets "
        "ist weder Vergleichskurs noch zweite Quelle.",
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


def _mapping_lines(report: dict, compact: bool = False) -> list[str]:
    legend = {x["aktie"]: x for x in report.get("weitere_buchstaben") or []}
    mapping = []
    for entry in report.get("zuordnung") or []:
        found = entry.get("fundstelle")
        if compact:
            where = f"{found['h']}/{found['gruppe']}/{found['w']} Platz {found['platz']}" if found else "in keiner Rangliste dieses Stands"
        else:
            where = (
                f"Rangliste {found['h']} Tage, Gruppe {found['gruppe']}, {found['w']}/{100 - found['w']}, Platz {found['platz']} (in der App: {_place_link(found)})"
                if found else "in keiner Rangliste dieses Stands"
            )
        extra = f" – {_legend(legend[entry['aktie']])}" if entry["aktie"] in legend else ""
        mapping.append(f"{entry['aktie']} = {where}{extra}")
    if mapping:
        mapping.insert(0, f"Datenstand {report['stand']} (Kursstand {report.get('stichtag', '–')}); in der App mit der Passphrase unter „Rangliste“, Einstellung „Auffällige ausblenden“ aus "
                          "– nach einem neueren Stand über „Datenstand & Betrieb → Frühere Stände → Anzeigen“ diesen Stand wählen"
                          + ("; Kurzform der Fundstelle: Tage/Gruppe/Gewichtung der Gleichmäßigkeit in % und Platz – in der App #/ranking?h=<Tage>&w=<Gewichtung>&p=native "
                             "mit &n=10 bis Platz 10, &n=50 bis Platz 50, sonst &n=alle&seite=<(Platz − 1) ÷ 50, abgerundet, + 1>; Gruppe B zusätzlich &g=b" if compact else ""))
    return mapping


def build_lines(report: dict, compact: bool = False) -> tuple[str, str, list[str], list[tuple[str, list[str]]]]:
    """Titel, Art und Zeilen des Ergebnisses eines Prüfjobs – Kopf (Urteil und Zählwerte) und Abschnitte mit Einzelheiten.
    ``compact``: Kurzform für die Hinweise des Jobs „gemeinsame Wirkung“ (die Zusammenfassung bleibt in Langform)."""
    if "jobs" in report:
        return build_combined_lines(report, compact)
    if report.get("auswahl") == WORLD_LEG:
        return build_world_lines(report)
    t, c, e = report["tage"], report["ursachen"], report["ranglisten"]
    p = report.get("plaetze") or {}
    nc = report.get("nocp_vergleich") or {}
    cov = report.get("top10_abdeckung") or {}
    result = report.get("urteil") or verdict(report)
    shard = report.get("auswahl", "alle")
    u = unique_days(report)
    title = VERDICT_TITLE[result].format(n=report.get("abruf_fehlgeschlagen", 0), k=report.get("ohne_vergleichskurse", 0), s=report.get("nicht_abgesichert", 0), u=u["ungeklaert"],
                                         a=u["abweichend"], p=u["plausibel"])
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
        f"Offizieller Schlusskurs (NOCP) aller Nasdaq-notierten Aktien der Auswahl mit abgesicherter Zuordnung: {nc.get('aktien', 0)} Aktien, {nc.get('tage', 0)} Tage – Stand gleich "
        f"{nc.get('stand_gleich', 0)}, Stand ungleich {nc.get('stand_ungleich', 0)}, Faktor eines gemeldeten Splits {nc.get('faktor_split', 0)} (NOCP unbereinigt, nicht ersetzt), "
        f"Faktor ohne gemeldeten Split {nc.get('faktor_ohne_split', 0)}; Nasdaq-Historie gleich {nc.get('nasdaq_historie_gleich', 0)}, ungleich {nc.get('nasdaq_historie_ungleich', 0)}",
        f"Börsentage gegen die Nasdaq-Historie verglichen {t.get('verglichen', 0)}, abweichend {t.get('abweichend', 0)} ({_counts(report.get('arten') or {})}; mit NOCP {t.get('abweichend_mit_nocp', 0)}, "
        f"mit Minutenkurs {t.get('abweichend_mit_minutenkursen', 0)})",
    ]
    head += _category_lines(report.get("kategorien") or {}, c, report.get("nocp_ursachen") or {}, (report.get("zusatzquellen") or {}).get("tage") or {})
    head += _reconcile_lines(report.get("abstimmung_nasdaq"), report.get("abstimmung_nocp"))
    head += _stock_day_lines(report)
    head += _security_lines(report.get("absicherung") or {}, report.get("wertpapierliste"), report.get("openfigi"))
    head += _gap_summary(report.get("weitere_buchstaben") or [])
    if (report.get("zusatzquellen") or {}).get("aktien_ohne_nasdaq"):
        head += _otc_lines((report.get("zusatzquellen") or {}).get("tage") or {}, (report.get("zusatzquellen") or {}).get("otc_lasttradetime") or {})
    head += [
        f"Ungeklärte Tage gegen die Nasdaq-Historie – Prüfgrenze bzw. Befund (erklärt, warum kein Beleg möglich war, nicht die Abweichung): {_counts(report.get('ungeklaert_gruende') or {}, UNEXPLAINED_TEXT)}; "
        f"Muster der ungeklärten Tage: {_counts(report.get('ungeklaert_muster') or {})}",
        f"Umsatz Nasdaq-Historie gegen Yahoo an allen verglichenen Tagen: {_counts(report.get('umsatz_vergleich') or {})}; "
        f"Tage nur im Stand {report['nur_eine_quelle'].get('nur_im_stand', 0)} (davon ohne Umsatz bei Yahoo {report['nur_eine_quelle'].get('nur_im_stand_ohne_umsatz_bei_yahoo', 0)}), "
        f"nur bei Nasdaq {report['nur_eine_quelle'].get('nur_bei_nasdaq', 0)} (davon mit Yahoo-Kurs {report['nur_eine_quelle'].get('nur_bei_nasdaq_yahoo_mit_kurs', 0)}); "
        f"Aktien mit Ereignis im Zeitraum: {_counts(report['aktien_mit_ereignis_im_zeitraum'])}",
    ]
    if report.get("zusatzquellen", {}).get("aktien_ohne_nasdaq"):
        head += _zusatz_line(report["zusatzquellen"], report.get("ohne_nasdaq_boerse") or {})
    head += [
        f"US-Aktien unter den ersten 10 irgendeiner Rangliste: {cov.get('us_aktien_unter_ersten_10', 0)} – mit Nasdaq abgesichert verglichen {cov.get('verglichen', 0)} (ohne Abweichung "
        f"{cov.get('ohne_abweichung', 0)}, davon nur der offizielle Schlusskurs anders {cov.get('davon_nur_nocp_abweichend', 0)}; jede Abweichung belegt {cov.get('alle_abweichungen_belegt', 0)}, "
        f"mit ungeklärten Tagen {cov.get('mit_ungeklaerten_tagen', 0)}), mit Zusatzquelle abgesichert verglichen {cov.get('verglichen_zusatzquelle', 0)}, "
        f"nicht ausreichend abgesichert {cov.get('nicht_abgesichert', 0)}, ohne Vergleichskurse {cov.get('ohne_nasdaq_kurse', 0)}, ohne Antwort {cov.get('abruf_fehlgeschlagen', 0)}"
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
            + f"; NOCP {'ja' if s['nocp_abrufbar'] else ('vorhanden, nicht abgesichert' if s.get('nocp_nicht_abgesichert') else 'nein')}"
            + (f" (Stand ungleich NOCP an {s.get('nocp_tage_ungleich', 0)} Tagen)" if s["nocp_abrufbar"] else "")
            + f", Minutenkurse {s['minutenkurse_tage']} Tage; Ereignisse {', '.join(f'{k} {v}' for k, v in s['ereignisse'].items() if v) or 'keine'}"
            + (f" (Dividenden bei Nasdaq nicht geprüft: {s['dividenden_nasdaq']})" if s.get("dividenden_nasdaq", "ok") != "ok" else "")
            + (f"; (a) {_moves(moves_a)}" if moves_a else "")
            + (f"; (b) {_moves(moves_b)}" if moves_b else "")
        )
    for s in report.get("aktien_nur_nocp") or []:
        moves_a, moves_b = s.get("rangwirkung") or {}, s.get("rangwirkung_nocp") or {}
        nocp_rows.append(
            f"Aktie {s['aktie']} ({s['boerse']}, {s['kursbereich']}; unter den ersten 10 in {s['top10']} Ranglisten, Platz 1 in {s['platz1']}): Stand wie Nasdaq-Historie, "
            f"aber ungleich NOCP an {s['nocp_tage_ungleich']} Tagen (größte {s['groesste_abweichung_nocp_pct']} %; Ursache belegt an {s.get('nocp_belegt', 0)}, plausible Erklärung an "
            f"{s.get('nocp_plausibel', 0)})"
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
            f"Weitere {small} Aktien mit kleinen Abweichungen (höchstens 0,5 %), nicht unter den ersten 10 und ohne ungeklärten Tag – Zählwerte oben"
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
    "unvollstaendig": "Kursursachen gemeinsam: UNVOLLSTÄNDIG – {gaps} von {n} ausgewählten Aktien ohne abgesicherten Vergleich{problems}; gemeinsame Wirkung der übrigen gerechnet",
    "gerechnet": "Kursursachen gemeinsam: alle {n} ausgewählten Aktien abgesichert verglichen – gemeinsame Wirkung gerechnet",
}
INTERACTION_TEXT = {"spitze": "Platz 1", "top10_aktien": "Aktien der ersten 10", "top10_reihenfolge": "Reihenfolge der ersten 10", "reihenfolge": "irgendeine Änderung"}
PROP_ART = {"erst_gemeinsam": "erst gemeinsam", "aufgehoben": "aufgehoben (einzeln geändert, gemeinsam nicht)", "anderer_spitzenreiter": "gemeinsam ein anderer neuer Platz 1 als einzeln"}


def _pct_of(part: int, whole: int) -> str:
    return f"{100 * part / whole:.1f} %" if whole else "–"


def _interaction_line(name: str, x: dict) -> str:
    c = x.get("zaehler") or {}
    p_v, q_v = x["teile"]
    pv, qv, pqv = f"({p_v})", f"({q_v})", f"({x['gemeinsam']})"
    parts = [f"Wechselwirkung {pqv} gegen {pv} und {qv} allein ({c.get('ranglisten', 0)} Ranglisten mit Einträgen, in denen mindestens ein Teil Rendite, R² oder Zulassung einer Aktie ändert)"]
    for prop in INTERACTION_PROPS:
        text = (f"{INTERACTION_TEXT[prop]}: gemeinsam {c.get(prop + '_gemeinsam', 0)}, mit {pv} allein {c.get(prop + '_mit_p', 0)}, mit {qv} allein {c.get(prop + '_mit_q', 0)} – "
                f"erst gemeinsam {c.get(prop + '_erst_gemeinsam', 0)}, aufgehoben {c.get(prop + '_aufgehoben', 0)}, auch einzeln {c.get(prop + '_auch_einzeln', 0)}")
        if prop == "spitze":
            text += f", gemeinsam ein anderer neuer Platz 1 als einzeln {c.get('spitze_anderer_spitzenreiter_als_einzeln', 0)}"
        parts.append(text)
    parts.append(f"übrige Rangänderungen (Aktie × Rangliste, ganze Liste): gemeinsam {c.get('aktien_rang_gemeinsam', 0)}, mit {pv} allein {c.get('aktien_rang_mit_p', 0)}, "
                 f"mit {qv} allein {c.get('aktien_rang_mit_q', 0)}, erst gemeinsam {c.get('aktien_rang_erst_gemeinsam', 0)}, aufgehoben {c.get('aktien_rang_aufgehoben', 0)}")
    return "; ".join(parts)


def _example_line(name: str, x: dict) -> str:
    lead = x["platz1"]
    t = name.split("+")
    head = f"({t[2]}) – {_method(x)}: {PROP_ART.get(x['art'], x['art'])} – Platz 1 vorher {lead[0]}, mit ({t[0]}) allein {lead[1]}, mit ({t[1]}) allein {lead[2]}, gemeinsam {lead[3]}"
    tops = x.get("erste10") or []
    if tops and set(tops[3]) != set(tops[0]):
        head += f"; erste 10 gemeinsam raus {' '.join(sorted(set(tops[0]) - set(tops[3]))) or '–'}, rein {' '.join(sorted(set(tops[3]) - set(tops[0]))) or '–'}"
    return head


def _source_rows(sources: dict, compact: bool = False) -> list[str]:
    rows = []
    if compact and sources.get("je_aktie"):
        rows.append("Kurzform: Aktie (Variante) Quelle Zahl der Tage: TT.MM. Abweichung des Stands gegenüber dem Ersatzkurs in % und Einordnung – "
                    + ", ".join(f"{code} = {text}" for code, text in SOURCE_CODE_TEXT.items()) + "; alle Tage 2026")
    for x in sources.get("je_aktie") or []:
        variants = "/".join(sorted({t[1] for t in x["tage"]}))
        if compact:
            days = ", ".join(f"{d[8:10]}.{d[5:7]} {pct:+.2f} {SOURCE_CODE.get(cause, cause)}" for d, v, q, pct, cause in x["tage"])
            rows.append(f"{x['aktie']} ({variants}) {' und '.join(SOURCE_SHORT.get(q, q) for q in x['quelle'])} {len(x['tage'])}: {days}")
            continue
        days = ", ".join(f"{d[8:10]}.{d[5:7]}.{d[2:4]} {pct:+.2f} % {_cause_label(cause)}" for d, v, q, pct, cause in x["tage"])
        rows.append(f"Aktie {x['aktie']} – ({variants}) {' und '.join(zusatz.SOURCE_TEXT.get(q, WORLD_SOURCE_TEXT.get(q, q)) for q in x['quelle'])}, "
                    f"{len(x['tage'])} Tage: {days}")
    return rows


# Kurzzeichen der Einordnung je Tag (Kurzform der Hinweise; die Zusammenfassung nennt die Langform)
SOURCE_CODE = {
    "nasdaq_gleich_nocp": "n", "nasdaq_gleich_stand": "s", "drei_kurse": "v", "nasdaq_ohne_tag": "t", "letzter_abschluss": "m", "nasdaq_letzter_abschluss": "q",
    "rundung": "k", "kein_handel": "u", "split_ohne_ereignis": "f", "dividende_ohne_ereignis": "d", "ungeklaert": "o", "abweichung_vom_nocp": "b", "split": "S",
    "dividendenbereinigung": "D",
}
SOURCE_CODE_TEXT = {
    "n": "Nasdaq-Historie = NOCP", "s": "Nasdaq-Historie = Stand, NOCP anders", "v": "Stand, Nasdaq-Historie und NOCP verschieden", "t": "Nasdaq-Historie ohne den Tag",
    "m": "Stand = letzte Minutenkerze (plausibel)", "q": "Nasdaq = letzte Minutenkerze (plausibel)", "k": "Kursstufe (plausibel)", "u": "Umsatz 0 (plausibel)",
    "f": "Faktor ohne Split (plausibel)", "d": "dividendenbereinigt ohne Dividende (plausibel)", "o": "ohne Erklärung", "b": "Stand ≠ NOCP (Befund)",
    "S": "Split (belegt)", "D": "Dividende (belegt)",
}
SOURCE_SHORT = {"nocp": "NOCP", "cnbc": "CNBC", "cnbc_welt": "CNBC", "otc_markets": "OTC Markets", "barchart": "Barchart", "marketwatch": "MarketWatch", "stooq": "Stooq",
                "zusatzquelle": "Zusatzquelle"}


WORLD_SOURCE_TEXT = {"nocp": "offizieller Schlusskurs NOCP", "cnbc_welt": "CNBC (außerhalb der US-Auswahl)", "zusatzquelle": "Zusatzquelle"}


def _universe_lines(u: dict) -> list[str]:
    g = u.get("gesamt") or {}
    r = u.get("ranglisten") or {}
    span = " bis ".join(u.get("zeitraum") or [])
    head = [
        f"Aktienuniversum der App (alle Aktien des Stands): {g.get('aktien', 0)} Aktien – abgesichert verglichen {g.get('aktien_abgesichert', 0)}, nicht ausreichend abgesichert "
        f"{g.get('aktien_nicht_abgesichert', 0)}, ohne Vergleichskurse in den geprüften Quellen {g.get('aktien_ohne_vergleichskurse', 0)}, ohne Antwort {g.get('aktien_ohne_antwort', 0)}, "
        f"nicht ausgewählt {g.get('aktien_nicht_ausgewaehlt', 0)} (ohne Kursreihe {g.get('ohne_kursreihe', 0)}); Tage im Prüfzeitraum {span}: im Stand {g.get('tage_stand', 0)}, "
        f"abgesichert verglichen {g.get('tage_verglichen', 0)} ({_pct_of(g.get('tage_verglichen', 0), g.get('tage_stand', 0))})",
        f"Ranglisten: {r.get('ranglisten', 0)} mit Einträgen – Plätze unter den ersten 10 {r.get('plaetze_erste_10', 0)}, davon mit abgesichertem Vergleich der Aktie "
        f"{r.get('plaetze_erste_10_abgesichert', 0)} ({_pct_of(r.get('plaetze_erste_10_abgesichert', 0), r.get('plaetze_erste_10', 0))}); Platz 1 {r.get('platz_1', 0)}, davon "
        f"{r.get('platz_1_abgesichert', 0)} ({_pct_of(r.get('platz_1_abgesichert', 0), r.get('platz_1', 0))}); Ranglisten mit allen ersten 10 abgesichert "
        f"{r.get('erste_10_abgesichert_alle', 0)}, mehr als der Hälfte {r.get('erste_10_abgesichert_mehr_als_die_haelfte', 0)}, höchstens der Hälfte "
        f"{r.get('erste_10_abgesichert_bis_zur_haelfte', 0)}, keiner {r.get('erste_10_abgesichert_keine', 0)}. Eine Prüfung einzelner Tage gegen eine Quelle ist keine "
        "Vollprüfung: Tage ohne Vergleich und nicht abgesicherte Aktien bleiben ungeprüft",
    ]
    rows = []
    for key, c in (u.get("je_boerse") or {}).items():
        rows.append(
            f"{key}: {c.get('aktien', 0)} Aktien – abgesichert {c.get('aktien_abgesichert', 0)}, nicht abgesichert {c.get('aktien_nicht_abgesichert', 0)}, ohne Vergleichskurse "
            f"{c.get('aktien_ohne_vergleichskurse', 0)}, ohne Antwort {c.get('aktien_ohne_antwort', 0)}, nicht ausgewählt {c.get('aktien_nicht_ausgewaehlt', 0)}; unter den ersten 10 "
            f"{c.get('aktien_unter_ersten_10', 0)} Aktien (abgesichert {c.get('aktien_unter_ersten_10_abgesichert', 0)}) mit {c.get('plaetze_erste_10', 0)} Plätzen (abgesichert "
            f"{c.get('plaetze_erste_10_abgesichert', 0)}), Platz 1 {c.get('plaetze_platz_1', 0)} (abgesichert {c.get('plaetze_platz_1_abgesichert', 0)}); Tage im Stand "
            f"{c.get('tage_stand', 0)}, abgesichert verglichen {c.get('tage_verglichen', 0)} ({_pct_of(c.get('tage_verglichen', 0), c.get('tage_stand', 0))})"
        )
    return head, rows


STATE_SHORT = {"nicht_abgesichert": "nicht abgesichert", "ohne_vergleichskurse": "ohne Vergleichskurse", "ohne_antwort": "ohne Antwort",
               "nicht_ausgewaehlt": "nicht ausgewählt"}


def _reconcile_lines(nasdaq: dict | None, nocp: dict | None) -> list[str]:
    """Abstimmung mit den Zählungen der Läufe vor der Absicherung (bis 40162120622): die nicht abgesicherten Vergleiche, nur gezählt."""
    def one(name: str, c: dict) -> str:
        causes = {k[len("ursache_"):]: v for k, v in c.items() if k.startswith("ursache_")}
        label = lambda k: (f"Befund: {NOCP_NOTE.get(k[len('befund_'):], k)}" if k.startswith("befund_") else _cause_label(k))  # noqa: E731
        text = ", ".join(f"{label(k)} {v}" for k, v in sorted(causes.items(), key=lambda kv: (-kv[1], kv[0]))) or "–"
        return (f"{name} {c.get('aktien', 0)} Aktien, {c.get('tage', 0)} Tage verglichen, gleich {c.get('gleich', 0)}, abweichend {c.get('abweichend', 0)} "
                f"(Einordnung, die ein Tag in einem abgesicherten Vergleich bekäme: {text})")
    parts = [one(name, c) for name, c in (("Nasdaq-Historie", nasdaq), ("offizieller Schlusskurs NOCP", nocp)) if c]
    if not parts:
        return []
    return ["Abstimmung mit den Zählungen vor der Absicherung (bis Lauf 40162120622) – nicht ausreichend abgesicherte Vergleiche, nur gezählt (weder Bestätigung noch "
            "Ursache noch Ersatzkurs): " + "; ".join(parts)]


def _unchecked_leader_lines(u: dict) -> list[str]:
    """Ranglisten, deren Platz 1 keinen abgesicherten Vergleich hat – je Aktie (Börse und Grund in der Zuordnung der Buchstaben)."""
    rows = u.get("platz1_ungeprueft") or []
    if not rows:
        return []
    by_stock: dict[tuple[str, str], list[str]] = {}
    for r in rows:
        by_stock.setdefault((r["aktie"], r["zustand"]), []).append(f"{r['h']}/{r['gruppe']}/{r['w']}")
    out = [f"Platz 1 ohne abgesicherten Vergleich der Aktie: {len(rows)} Ranglisten, {len(by_stock)} Aktien – Rangliste als Tage/Gruppe/Gewichtung der Gleichmäßigkeit "
           "in %; Börse, Kursbereich und Grund in der Zuordnung der Buchstaben"]
    for (name, state), places in sorted(by_stock.items(), key=lambda kv: (-len(kv[1]), len(kv[0][0]), kv[0][0])):
        out.append(f"{name} ({STATE_SHORT.get(state, state)}): {len(places)} – " + ", ".join(places))
    return out


def _gap_summary(legend: list[dict]) -> list[str]:
    """Lücken je Aktie: jede ausgewählte Aktie ohne abgesicherten Vergleich mit ihrem Buchstaben, nach Grund (Börse, Kursbereich,
    Plätze und ungeprüfte Tage je Buchstabe in der Zuordnung) – Auftrag Punkt 6: Lücken nach Aktien dokumentieren."""
    by_reason: dict[str, list[str]] = {}
    for x in legend:
        gap = x.get("luecke")
        if gap:
            by_reason.setdefault(gap.get("grund") or "unbekannt", []).append(x["aktie"])
    if not by_reason:
        return []
    total = sum(len(v) for v in by_reason.values())
    return [f"Lücken je Aktie – {total} ausgewählte Aktien ohne abgesicherten Vergleich (Börse, Kursbereich, Plätze, ungeprüfte Tage und Grund je Buchstabe in der "
            "Zuordnung): " + "; ".join(f"{GAP_TEXT.get(k, k)} {len(v)}: {' '.join(v)}" for k, v in sorted(by_reason.items(), key=lambda kv: (-len(kv[1]), kv[0])))]


def _world_category_line(c: dict, causes: dict) -> str:
    return (
        f"Ergebnis gegen CNBC außerhalb der US-Auswahl (Tage, nur abgesicherte Vergleiche): bestätigte Übereinstimmung {c.get('uebereinstimmung', 0)}; festgestellte Abweichung "
        f"{c.get('abweichung', 0)} – davon Ursache belegt {c.get('belegt', 0)} (Quelle unbereinigt vor einem gemeldeten Split), ungeklärt mit plausibler Erklärung {c.get('plausibel', 0)} "
        f"({_cause_counts(causes, PLAUSIBLE)}), ungeklärt ohne Erklärung {c.get('ohne_erklaerung', 0)}; fehlende Prüfmöglichkeit: {c.get('ohne_vergleich_aktien', 0)} Aktien ohne "
        f"abgesicherte Vergleichskurse – ohne Vergleichskurse bei CNBC {c.get('ohne_vergleich_ohne_kurse', 0)}, Kurse gefunden, aber Zuordnung nicht ausreichend abgesichert "
        f"{c.get('nicht_abgesichert_aktien', 0)} (deren {c.get('nicht_abgesichert_tage', 0)} Tage nur gezählt: weder Ersatzkurs noch Bestätigung); "
        f"{c.get('ohne_vergleich_tage', 0)} Tage der abgesicherten Aktien nur im Stand"
    )


def _world_exchange_lines(by_exchange: dict) -> list[str]:
    rows = []
    for key, c in sorted(by_exchange.items(), key=lambda kv: (-kv[1].get("aktien", 0), kv[0])):
        results = ", ".join(f"{WORLD_RESULT_TEXT.get(k[len('ergebnis_'):], k[len('ergebnis_'):])} {v}" for k, v in sorted(c.items()) if k.startswith("ergebnis_"))
        failed = ", ".join(f"{absicherung.CHECK_TEXT.get(k[len('nicht_bestanden_'):], k[len('nicht_bestanden_'):])} {v}"
                           for k, v in sorted(c.items(), key=lambda kv: (-kv[1], kv[0])) if k.startswith("nicht_bestanden_"))
        rows.append(f"{key}: {c.get('aktien', 0)} Aktien mit {c.get('plaetze_erste_10', 0)} Plätzen unter den ersten 10 (abgesichert {c.get('plaetze_erste_10_abgesichert', 0)}) "
                    f"und {c.get('plaetze_platz_1', 0)} Plätzen 1 (abgesichert {c.get('plaetze_platz_1_abgesichert', 0)}); Tage verglichen {c.get('tage_verglichen', 0)} von "
                    f"{c.get('tage_stand', 0)} der abgesicherten Aktien, ungeprüft {c.get('tage_stand_ungeprueft', 0)} Tage der übrigen; {results}"
                    + (f"; nicht bestanden: {failed}" if failed else ""))
    return rows


def build_world_lines(report: dict) -> tuple[str, str, list[str], list[tuple[str, list[str]]]]:
    """Titel, Art und Zeilen des Prüfjobs „außerhalb der US-Auswahl“ (CNBC)."""
    result = report.get("urteil") or verdict(report)
    u = unique_days(report)
    title = VERDICT_TITLE[result].format(n=0, k=report.get("ohne_vergleichskurse", 0), s=report.get("nicht_abgesichert", 0), u=u["ungeklaert"], a=u["abweichend"], p=u["plausibel"])
    title = title.replace("Kursursachen:", f"Kursursachen{SHARD_TEXT[WORLD_LEG]}:", 1)
    level = {"unvollstaendig": "error", "ungeklaert": "error", "belegt": "notice", "keine_abweichungen": "notice"}[result]
    w = report.get("welt") or {}
    pw = report.get("plaetze_welt") or {}
    cov = (report.get("abdeckung_je_gruppe") or {}).get("welt") or {}
    z = w.get("zaehler") or {}
    head = [
        f"Nachträglich abgerufen am {report['abgerufen_utc']} (CNBC: Kursmeldung mit Name, Börse, Währung und Tageskerzen; Yahoo-Tageskurse für die Prüfung der Bereinigung; "
        f"OpenFIGI) – keine Originaldaten. Stand {report['stand']} (Kursstand {report['stichtag']}); ausgewählt alle {report['ausgewaehlt']} Aktien außerhalb der US-Auswahl mit "
        f"mindestens einem Platz unter den ersten 10 irgendeiner Rangliste ({pw.get('erste_10', 0)} Plätze unter den ersten 10, {pw.get('platz_1', 0)} Plätze 1) – keine Stichprobe, "
        "aber nur eine Vergleichsquelle (CNBC); Aktien ohne Platz unter den ersten 10 sind hier nicht geprüft.",
        _coverage_line("außerhalb der US-Auswahl", cov),
        "Kürzel bei CNBC und Abruf: " + _counts({k: v for k, v in z.items() if k.startswith(("kursmeldung_", "kerzen_", "kuerzel_schreibweise_", "ohne_kuerzelregel_"))}),
        _world_category_line((report.get("kategorien") or {}).get("cnbc_welt") or {}, w.get("ursachen") or {}),
    ]
    head += _stock_day_lines(report)
    head += _security_lines(report.get("absicherung") or {}, None, report.get("openfigi"))
    head += _gap_summary(report.get("weitere_buchstaben") or [])
    head += [
        f"(d) CNBC an allen abweichenden Tagen der abgesicherten Aktien – dieser Job allein (gemeinsam mit den US-Jobs im Job „gemeinsame Wirkung“): {_effect(report.get('ranglisten_welt') or {})}",
        f"Platz 1 anders – (d): {_changes(report.get('aenderungen_welt') or [], 'platz1')}",
        f"Andere Aktien unter den ersten 10 – (d): {_changes(report.get('aenderungen_welt') or [], 'top10')}",
        "Lesart: Buchstaben statt Namen (eigene Zählung dieses Jobs), Zuordnung im Abschnitt „Zuordnung der Buchstaben“; Abweichung = Stand gegenüber dem CNBC-Kurs in %, Kurse "
        "der Quelle in der Einheit des Stands (z. B. GBp)",
    ]
    leaders = [_leader_line(x, "(d) CNBC", n, len([y for y in report.get("aenderungen_welt") or [] if y.get("platz1")]))
               for n, x in enumerate([y for y in report.get("aenderungen_welt") or [] if y.get("platz1")], start=1)] or ["(d) CNBC: in keiner Rangliste ein anderer Platz 1"]
    members = [_member_line(x, "(d)") for x in report.get("aenderungen_welt") or [] if x.get("raus") or x.get("rein")]
    stock_rows = [
        f"Aktie {r['aktie']} ({r['boerse']}, {r['kursbereich']}; unter den ersten 10 in {r['top10']} Ranglisten, Platz 1 in {r['platz1']}): {r['abweichend']} Tage abweichend, größte "
        f"{r['groesste_abweichung_pct']} %; Einordnung: " + (", ".join(f"{SHORT_CAUSE.get(k, k)} {v}" for k, v in sorted(r["ursachen"].items())) or "–")
        + (f"; (d) {_moves(r['rangwirkung_zusatz'])}" if r.get("rangwirkung_zusatz") else "")
        for r in sorted(report.get("aktien_welt") or [], key=lambda r: (-r["top10"], r["aktie"]))
    ]
    sections = [
        ("Je Börse", _world_exchange_lines(w.get("je_boerse") or {})),
        ("Platz 1 anders – jede Rangliste einzeln", leaders),
        ("Zuordnung der Buchstaben", _mapping_lines(report)),
        ("Abweichungen je Aktie", stock_rows),
        ("Andere Aktien unter den ersten 10 – einzeln", members),
    ]
    return title, level, head, [(name, lines) for name, lines in sections if lines]


def build_combined_lines(report: dict, compact: bool = False) -> tuple[str, str, list[str], list[tuple[str, list[str]]]]:
    """Titel, Art und Zeilen der gemeinsamen Neuberechnung aller Prüfjobs."""
    coverage = report.get("abdeckung_je_gruppe") or {}
    gaps = sum(c.get("keine_vergleichskurse", 0) + c.get("abruf_fehlgeschlagen", 0) + c.get("nicht_abgesichert", 0) for c in coverage.values()) + report.get("nicht_uebergeben", 0)
    problems = report.get("probleme") or []
    selected = report.get("ausgewaehlt", 0) + report.get("ausgewaehlt_welt", 0)
    title = COMBINED_TITLE[report["urteil"]].format(gaps=gaps, n=selected, problems=(" – " + "; ".join(problems)) if problems else "")
    level = "error" if report["urteil"] == "unvollstaendig" else "notice"
    jobs = "; ".join(f"{JOB_TEXT.get(leg, leg)}: {j['aktien']} Aktien, abgerufen {j['abgerufen_utc']}, Anfragen an Nasdaq {j.get('nasdaq_anfragen')}, Prüfsumme {j['pruefsumme']}"
                     for leg, j in (report.get("jobs") or {}).items())
    p = report.get("plaetze") or {}
    head = [
        f"Gemeinsame Neuberechnung aller Ranglisten gegen den unveränderten Stand {report['stand']} (Kursstand {report['stichtag']}) mit den Vergleichskursen aller Prüfjobs dieses Laufs – "
        f"{jobs or 'keine Übergabe'}. Vergleichskurse nachträglich abgerufen – keine Originaldaten. Ausgewählt: {report.get('ausgewaehlt', 0)} US-Aktien (unter den ersten 20 einer "
        f"Rangliste und eine Zufallsstichprobe) und {report.get('ausgewaehlt_welt', 0)} Aktien außerhalb der US-Auswahl mit Platz unter den ersten 10 – keine Vollprüfung aller "
        f"Aktien der App (Abdeckung des Universums unten); Plätze unter den ersten 10 aller Ranglisten: {p.get('erste_10', 0)}, davon US-Aktien {p.get('erste_10_us', 0)}. "
        "Nur abgesicherte Vergleiche liefern Ersatzkurse.",
    ]
    if problems:
        head.append("Fehlende oder unpassende Übergaben: " + "; ".join(problems))
    head.append("Abdeckung je Gruppe (aus den Prüfjobs; fehlende Daten und nicht abgesicherte Vergleiche zählen nicht als geprüft):")
    head += [_coverage_line(GROUP_TEXT[g], coverage[g]) for g in ALL_GROUPS if g in coverage]
    if "erste_10" in coverage and "erste_20" in coverage:
        head.append(_coverage_line("erste 20 gesamt (erste 10 und Plätze 11–20)", dict(Counter(coverage["erste_10"]) + Counter(coverage["erste_20"]))))
    head.append(_coverage_line("alle Gruppen", dict(sum((Counter(c) for c in coverage.values()), Counter()))))
    counts = report.get("zaehler") or {}
    categories = report.get("kategorien") or {}
    head += _category_lines(categories, counts.get("ursachen") or {}, counts.get("nocp_ursachen") or {}, counts.get("zusatzquellen_tage") or {})
    head += _reconcile_lines(counts.get("abstimmung_nasdaq"), counts.get("abstimmung_nocp"))
    if categories.get("cnbc_welt"):
        head.append(_world_category_line(categories["cnbc_welt"], counts.get("welt_ursachen") or {}))
    head += _stock_day_lines(report)
    head += _security_lines(counts.get("absicherung") or {}, None, counts.get("openfigi"))
    head += _gap_summary(report.get("weitere_buchstaben") or [])
    head += _otc_lines(counts.get("zusatzquellen_tage") or {}, counts.get("otc_lasttradetime") or {})
    head.append(f"Ungeklärte Tage gegen die Nasdaq-Historie – Prüfgrenze bzw. Befund: {_counts(counts.get('ungeklaert_gruende') or {}, UNEXPLAINED_TEXT)}")
    head.append(f"Minutenkurse und Gegenproben der Dividenden bei Nasdaq (alle Jobs): {_counts(counts.get('detailabruf') or {})}")
    effects = report.get("ranglisten") or {}
    head += [f"Gemeinsam {COMBINED_TEXT[v]}: {_effect(effects.get(v) or {})}" for v in COMBINED]
    separate = []
    for name in ("erste10", "plaetze11_20", "zufall", "erste20"):
        for v in ("a", "b", "c"):
            if f"{v}@{name}" in effects and (v != "c" or (effects[f"{v}@{name}"].get("ranglisten_verglichen"))):
                e = effects[f"{v}@{name}"]
                separate.append(f"{JOB_TEXT[name]} ({v}): Platz 1 {e.get('spitze_geaendert', 0)}, Aktien der ersten 10 {e.get('top10_aktien_geaendert', 0)}, "
                                f"Reihenfolge der ersten 10 {e.get('top10_reihenfolge_geaendert', 0)}, irgendeine Änderung {e.get('reihenfolge_geaendert', 0)}")
    if separate:
        head.append("Zum Vergleich je Job allein: " + "; ".join(separate))
    reference = report.get("vergleich_mit_lauf")
    if reference:
        same_all = all(x["gleich"] for x in reference.values())
        detail = "; ".join(f"{JOB_TEXT[v.split('@')[1]]} ({v.split('@')[0]}): " + ("gleich" if x["gleich"] else f"damals {x['erwartet']}, jetzt {x['jetzt']}") for v, x in reference.items())
        head.append(f"Vergleich mit Lauf {REFERENCE_RUN} (gleicher Stand, Aufteilung erste 20 / Zufallsstichprobe; damals ohne Absicherung der Zuordnung, Unterschiede also auch aus "
                    "der Absicherung): " + ("dieselbe Wirkung – " if same_all else "ABWEICHEND – ") + detail)
    changes = report.get("aenderungen") or {}
    only = report.get("nur_getrennt") or {}
    head.append(
        "Platz 1 anders gemeinsam – " + " | ".join(f"({v}): {_changes(changes.get(v) or [], 'platz1')}" for v in COMBINED)
        + "; nur in einem Job allein anders (gemeinsam nicht): " + (", ".join(f"({v}) {len(rows)}" for v, rows in only.items() if rows) or "keine")
    )
    interactions = report.get("wechselwirkung") or {}
    head += [_interaction_line(name, x) for name, x in interactions.items()]
    sources = report.get("quellen_je_aktie_und_tag") or {}
    if sources:
        head.append(
            "Quelle je Aktie und Tag in (b), (c), (d) und ihren gemeinsamen Varianten – Regel: (b) offizieller Schlusskurs NOCP an jedem Tag mit Stand ≠ NOCP bei Nasdaq-notierten "
            "Aktien der US-Auswahl mit abgesicherter Zuordnung; (c) die erste abgesicherte Zusatzquelle (Reihenfolge OTC Markets, CNBC, Barchart, MarketWatch, Stooq) an jedem "
            "abweichenden Tag bei US-Aktien ohne Nasdaq-Kurse; (d) CNBC an jedem abweichenden Tag bei abgesicherten Aktien außerhalb der US-Auswahl; Tage, die um einen gemeldeten "
            f"Split bereinigt gleich sind, nie ersetzt. {sources.get('aktien', 0)} Aktien, {sources.get('aktientage', 0)} Aktientage ({_counts(sources.get('je_quelle') or {})}); "
            f"Überschneidung {sources.get('ueberschneidung_aktientage', 0)} Aktientage (je Aktie und Tag genau eine Quelle); Prüfsumme {sources.get('pruefsumme')}; jede Aktie mit "
            "jedem Tag im Abschnitt „Quelle je Aktie und Tag“"
        )
    universe_head, universe_rows = _universe_lines(report.get("universum") or {})
    head += universe_head
    head.append("Lesart: Buchstaben dieses Jobs (eigene Zählung, Zuordnung unten); * = Kurse dieser Aktie im Zeitraum ersetzt; Abweichung = Stand gegenüber dem Ersatzkurs in %")
    leaders: dict[str, list[str]] = {"vorrang": [], "uebrige": []}
    members, orders, separate_rows = [], [], []
    leader_rows = {v: [x for x in changes.get(v) or [] if x.get("platz1")] for v in COMBINED}
    for v in FOCUS_VARIANTS + tuple(x for x in COMBINED if x not in FOCUS_VARIANTS):
        part = leaders["vorrang" if v in FOCUS_VARIANTS else "uebrige"]
        rows = leader_rows[v]
        if not (effects.get(v) or {}).get("ranglisten_verglichen"):
            part.append(f"gemeinsam {v}: keine Ersatzkurse in dieser Variante")
            continue
        for n, x in enumerate(rows, start=1):
            # Kurzform (nur in den Hinweisen): derselbe Wechsel mit denselben Werten steht schon in (b) – Langform dort und in der Zusammenfassung
            ref = next(((k, y) for k, y in enumerate(leader_rows.get("b") or [], start=1) if (y["h"], y["gruppe"], y["w"]) == (x["h"], x["gruppe"], x["w"])), None) if v != "b" else None
            if compact and ref is not None and _same_leader(x, ref[1]):
                part.append(_leader_short(x, f"gemeinsam {v}", n, len(rows), "b", ref[0], len(leader_rows["b"])))
            else:
                part.append(_leader_line(x, f"gemeinsam {v}", n, len(rows)))
        if not rows:
            part.append(f"gemeinsam {v}: in keiner Rangliste ein anderer Platz 1")
        if not compact:
            members += [_member_line(x, f"gemeinsam {v}") for x in changes.get(v) or [] if x.get("raus") or x.get("rein")]
            orders += [_order_line(x, f"gemeinsam {v}") for x in changes.get(v) or [] if x.get("reihenfolge")]
    later_orders: list[str] = []
    if compact:
        members = _member_rows_short(changes, COMBINED)
        # Reihenfolgen einzeln zuerst für (b), (c) und (b)+(c) (Auftrag Punkt 1), dann die übrigen Varianten
        first_orders = ("b", "c", "bc")
        orders = _order_rows_short(changes, first_orders)
        later_orders = _order_rows_short(changes, tuple(v for v in COMBINED if v not in first_orders))
    for v, rows in only.items():
        separate_rows += [f"({v}) nur mit den Kursen des Jobs {JOB_TEXT.get(x['job'], x['job'])}: {_method(x)}: bisher {x['platz1'][0]}, neu {x['platz1'][1]} – gemeinsam nicht" for x in rows]
    examples = [_example_line(name, x) for name, value in interactions.items() for x in value.get("beispiele") or []]
    # Reihenfolge nach Bedeutung (GitHub zeigt je Job höchstens 50 Hinweise; vollständig steht alles in der Zusammenfassung):
    # zuerst die neuen Plätze 1 mit offiziellem Schlusskurs und CNBC (Auftrag Punkt 1), die Abdeckung je Börse, die
    # Wechselwirkung, die Zuordnung der Buchstaben und die Quelle je Aktie und Tag; zuletzt die Reihenfolgen
    sections = [
        ("Gemeinsam: Platz 1 anders – (b), (b)+(c), (b)+(c)+(d) – jede Rangliste einzeln", leaders["vorrang"]),
        ("Abdeckung je Börse", universe_rows),
        ("Platz 1 ohne abgesicherten Vergleich – je Aktie", _unchecked_leader_lines(report.get("universum") or {})),
        ("Wechselwirkung: erst gemeinsam entstanden oder aufgehoben – einzeln", examples),
        ("Zuordnung der Buchstaben (gemeinsame Wirkung)", _mapping_lines(report, compact)),
        ("Quelle je Aktie und Tag", _source_rows(sources, compact)),
        ("Gemeinsam: Platz 1 anders – übrige Varianten – jede Rangliste einzeln", leaders["uebrige"]),
        ("Gemeinsam: andere Aktien unter den ersten 10 – einzeln", members),
        ("Nur in einem Job allein anders", separate_rows),
        ("Gemeinsam: andere Reihenfolge der ersten 10 bei gleichen Aktien – einzeln" + (" – (b), (c), (b)+(c)" if compact else ""), orders),
        ("Gemeinsam: andere Reihenfolge der ersten 10 bei gleichen Aktien – übrige Varianten", later_orders),
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
    title, level, head, sections = build_lines(report, compact=True)
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
    parser.add_argument("--auswahl", choices=sorted(set(SHARDS) | {WORLD_LEG}), default=os.environ.get("AUSWAHL") or "alle",
                        help="welcher Teil der Auswahl in diesem Job (Nasdaq: etwa 430 Anfragen je Rechner; „welt“: Aktien außerhalb der US-Auswahl gegen CNBC)")
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
                report = run_world_leg(stand, sid, http) if args.auswahl == WORLD_LEG else run(stand, sid, http, auswahl=args.auswahl)
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
