"""Ereignisse aus Schlagzeilen (ab 1.25.0, ``ereignisse-1``): Art, Stand (bestätigt, Bericht, Gerücht), Ton und Kaufwarnung.

Auftrag vom 07.11.2026 (17:22 und 19:06 Uhr): Ereignisarten erkennen, bestätigte Meldungen von Berichten und Gerüchten
trennen, „Hohes Unternehmensrisiko – Kaufwarnung“ nur bei belegten kritischen Ereignissen (dann nie grün), Zeit, Quelle und
Link je Meldung. Grundlage sind die Schlagzeilen des Kursanbieters (Titel, Quelle, Zeit, Link) – der Text der Meldung liegt
nicht vor; die Einordnung folgt festen Wortlisten (deutsch und englisch) und ist eine Lesehilfe, keine Prüfung des Inhalts.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

VERSION = "ereignisse-1"
WARN_DAYS = 30  # Kaufwarnung nur aus Meldungen der letzten 30 Tage
KAUFWARNUNG = "Hohes Unternehmensrisiko – Kaufwarnung"

# Art → (Bezeichnung, Ton −1/0/+1, kritisch, Muster)
EVENT_TYPES: dict[str, tuple[str, int, bool, str]] = {
    "insolvenz": ("Insolvenz", -1, True,
                  r"insolven|bankrupt|chapter 1[15]\b|chapter 7\b|gläubigerschutz|zahlungsunfähig|files? for (court )?protection|receivership|"
                  r"schutzschirmverfahren|liquidation\b"),
    "bilanz": ("Bilanzprobleme", -1, True,
               r"restate|restatement|accounting (irregularit|fraud|scandal|issue)|bilanz(fälschung|manipulation|skandal)|testat verweiger|"
               r"auditor (resign|quits|withdraw)|wirtschaftsprüfer (verweigert|legt mandat|kündigt)|fehlende? milliarden|cannot be located"),
    "ermittlung": ("Ermittlungen", -1, True,
                   r"\bsec (probe|investigation|charges|sues)|\bdoj\b|department of justice|subpoena|fraud (charges|probe|investigation)|"
                   r"indicted|staatsanwalt|\bermittlung|razzia|durchsuchung|bafin[- ](prüft|ermittelt|sonderprüfung)|criminal (probe|investigation)"),
    "handelsaussetzung": ("Handelsaussetzung", -1, True,
                          r"trading halt|trading (was |is )?(halted|suspended)|halts trading|halted trading|(shares|stock) halted|suspended from trading|delist|"
                          r"handelsaussetzung|vom handel ausgesetzt|handel ausgesetzt|börsenrückzug"),
    "liquiditaet": ("Liquiditätsprobleme", -1, True,
                    r"going concern|liquidity (crisis|crunch|concerns)|liquiditätsengpass|zahlungsausfall|missed (a |an )?(interest |debt )?payment|"
                    r"covenant (breach|waiver)|default(s|ed)? on|kreditlinie gekündigt"),
    "gewinnwarnung": ("Gewinnwarnung", -1, True,
                      r"profit warning|gewinnwarnung|umsatzwarnung|(cuts|lowers|slashes|withdraws|pulls) (its |full[- ]year |annual )?(guidance|forecast|outlook)|"
                      r"senkt (die |seine |ihre )?(prognose|jahresprognose|ziele)|prognose gesenkt|kassiert (die )?prognose"),
    "verwaesserung": ("Verwässerung", -1, False,
                      r"kapitalerhöhung|share offering|stock offering|public offering|secondary offering|at-the-market|\bdilution\b|verwässer|"
                      r"convertible (notes|bonds) offering|direct offering|registered direct"),
    "kundenverlust": ("Auftrags- oder Kundenverlust", -1, False,
                      r"loses? (a |its )?(contract|customer|client)|contract (terminated|cancell?ed)|verliert (großkunden|auftrag|kunden)|"
                      r"auftrag (storniert|gekündigt)|kündigt (den )?vertrag"),
    "analyst_runter": ("Analyst senkt Einstufung oder Ziel", -1, False,
                       r"downgraded|downgrades? .{0,40}\bto\b|analyst downgrade|rating downgrade|herabgestuft|abgestuft|cut to (sell|underweight|neutral|hold)|"
                       r"price target (cut|lowered|reduced)|"
                       r"senkt (das )?kursziel|kursziel gesenkt"),
    "zahlen_schwach": ("schwache Geschäftszahlen", -1, False,
                       r"miss(es|ed)? (estimates|expectations|forecasts)|falls short of|verfehlt (die )?erwartungen|unter den erwartungen|"
                       r"quarterly loss widens|verlust ausgeweitet"),
    "zahlen_stark": ("starke Geschäftszahlen", 1, False,
                     r"beats? (estimates|expectations|forecasts)|tops (estimates|expectations)|übertrifft (die )?erwartungen|record (revenue|sales|profit)|"
                     r"rekord(umsatz|gewinn|quartal)|über den erwartungen"),
    "prognose_hoch": ("Prognose erhöht", 1, False,
                      r"(raises|lifts|boosts|ups) (its |full[- ]year |annual )?(guidance|forecast|outlook)|hebt (die |seine |ihre )?(prognose|jahresprognose|ziele) an|"
                      r"erhöht (die |seine |ihre )?(prognose|jahresprognose)|prognose (angehoben|erhöht)"),
    "auftrag": ("Auftrag", 1, False,
                r"wins? (a |an )?(\$?[\d.,]+ ?(million|billion|mio|mrd)\.? )?(contract|order|deal)|awarded (a )?contract|großauftrag|erhält auftrag|"
                r"auftrag (über|im wert)|milliardenauftrag|secures (a )?(contract|order)"),
    "analyst_hoch": ("Analyst erhöht Einstufung oder Ziel", 1, False,
                     r"upgraded|upgrades? .{0,40}\bto (buy|outperform|overweight|neutral)|analyst upgrade|hochgestuft|heraufgestuft|raised to (buy|outperform|overweight)|"
                     r"price target (raised|increased|hiked)|"
                     r"hebt (das )?kursziel|kursziel (angehoben|erhöht)"),
}

RUMOR = re.compile(
    r"reportedly|rumou?r|gerücht|insidern|according to insiders|people familiar|sources (said|say)|according to (people|sources)|laut kreisen|kreisen zufolge|"
    r"erwägt|considering|weighs|explores|in talks|could face|may face|prüft (einen|eine|den|die)|spekulation|speculat",
    re.IGNORECASE,
)
CONFIRMED_SOURCE = re.compile(r"business wire|businesswire|pr newswire|prnewswire|globenewswire|globe newswire|eqs|accesswire|newsfile|dgap", re.IGNORECASE)
CONFIRMED_WORDS = re.compile(r"\b(announces|announced|reports|reported results|files|filed|confirms|gibt bekannt|teilt mit|meldet|bestätigt)\b", re.IGNORECASE)
COMPILED = {key: re.compile(pattern, re.IGNORECASE) for key, (_, _, _, pattern) in EVENT_TYPES.items()}
# Reihenfolge der Prüfung: kritische zuerst, dann übrige negative, dann positive
ORDER = [k for k, v in EVENT_TYPES.items() if v[2]] + [k for k, v in EVENT_TYPES.items() if not v[2] and v[1] < 0] + [k for k, v in EVENT_TYPES.items() if v[1] > 0]
STATUS_LABEL = {"bestaetigt": "bestätigt (Mitteilung)", "bericht": "Bericht", "geruecht": "Gerücht / unbestätigt"}


@dataclass
class Event:
    art: str
    label: str
    ton: int
    kritisch: bool
    status: str  # bestaetigt · bericht · geruecht
    titel: str
    quelle: str | None
    zeit: int | None  # Sekunden seit 1970
    link: str | None

    def as_dict(self) -> dict:
        return {
            "art": self.art,
            "bezeichnung": self.label,
            "ton": self.ton,
            "kritisch": self.kritisch,
            "stand": self.status,
            "titel": self.titel,
            "quelle": self.quelle,
            "zeit": self.zeit,
            "link": self.link,
        }


def classify(title: str, source: str | None = None) -> tuple[str, str] | None:
    """(Art, Stand) einer Schlagzeile oder None."""
    text = title or ""
    for key in ORDER:
        if COMPILED[key].search(text):
            if RUMOR.search(text):
                status = "geruecht"
            elif (source and CONFIRMED_SOURCE.search(source)) or CONFIRMED_WORDS.search(text):
                status = "bestaetigt"
            else:
                status = "bericht"
            return key, status
    return None


def events_of(news: list[dict] | None) -> list[Event]:
    """Ereignisse aus den Schlagzeilen einer Aktie (nur Meldungen mit Bezug zur Aktie), neueste zuerst, Dubletten (gleiche Art
    am selben Tag) zusammengefasst."""
    out: list[Event] = []
    seen: set[tuple[str, int]] = set()
    def when(n) -> float:
        value = n.get("zeit") if isinstance(n, dict) else None
        return float(value) if isinstance(value, (int, float)) else 0.0

    for item in sorted((n for n in (news or []) if isinstance(n, dict)), key=lambda n: -when(n)):
        if item.get("bezug") is False:
            continue
        found = classify(str(item.get("titel") or ""), item.get("quelle"))
        if not found:
            continue
        key, status = found
        zeit = item.get("zeit")
        day = int(zeit // 86400) if isinstance(zeit, (int, float)) else -1
        if (key, day) in seen:
            continue
        seen.add((key, day))
        label, tone, critical, _ = EVENT_TYPES[key]
        out.append(Event(key, label, tone, critical, status, str(item.get("titel") or ""), item.get("quelle"), int(zeit) if isinstance(zeit, (int, float)) else None, item.get("link")))
    return out


def warning(events: list[Event], now_ts: float | None) -> Event | None:
    """Belegtes kritisches Ereignis der letzten 30 Tage (kein Gerücht) → Kaufwarnung."""
    for e in events:
        if not e.kritisch or e.status == "geruecht" or e.zeit is None:
            continue
        if now_ts is None or now_ts - e.zeit <= WARN_DAYS * 86400:
            return e
    return None


def light(events: list[Event], now_ts: float | None) -> str:
    """Nachrichtenlage: rot bei Kaufwarnung oder überwiegend negativen Ereignissen, grün bei überwiegend positiven, gelb
    bei gemischten, grau ohne Ereignisse (letzte 30 Tage, Gerüchte zählen nicht)."""
    if warning(events, now_ts):
        return "rot"
    recent = [e for e in events if e.status != "geruecht" and (now_ts is None or e.zeit is None or now_ts - e.zeit <= WARN_DAYS * 86400)]
    if not recent:
        return "grau"
    pos = sum(1 for e in recent if e.ton > 0)
    neg = sum(1 for e in recent if e.ton < 0)
    if neg > pos:
        return "rot"
    if pos > neg:
        return "gruen"
    return "gelb"
