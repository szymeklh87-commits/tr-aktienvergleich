"""Einrichtung des Spielgelddepots (Abschnitte 11 und 29.2): fünf Fragen, daraus ein **Testprofil** für den Robo-Kern.

Das Testprofil ist keine Anlageberatung und keine bestätigte persönliche Zielaufteilung; es steuert nur die Aufteilung des
virtuellen Kerns (Welt-Aktien-ETF / Geldmarkt-ETF) im Spielgeld. Die Herleitung ist offen und für jede Antwort gleich:

1. Jede Antwort hat 0 bis 4 Punkte (vorsichtig → offensiv); Summe 0 bis 20.
2. Welt-Anteil nach Punkten: 30 % + 3,5 Prozentpunkte je Punkt (0 Punkte → 30 %, 20 Punkte → 100 %).
3. Begrenzung durch die Verlusttragfähigkeit: Ein Welt-Aktien-ETF kann vorübergehend etwa die Hälfte verlieren
   (z. B. 2008/09); der Welt-Anteil × 50 % soll den genannten verkraftbaren Rückgang nicht übersteigen.
4. Auf 5 Prozentpunkte abrunden, mindestens 10 %; der Rest ist Geldmarkt.

Die App bekommt die Fragen und die fertige Tabelle (Punkte × Verlusttragfähigkeit → Welt-Anteil) mit dem Stand – dieselbe
Rechnung, keine zweite Formel in der App.
"""

from __future__ import annotations

import math

FRAGEN: tuple[dict, ...] = (
    {"id": "horizont", "frage": "Wie lange soll das Geld angelegt bleiben?",
     "antworten": ("unter 1 Jahr", "1 bis 3 Jahre", "3 bis 5 Jahre", "5 bis 10 Jahre", "über 10 Jahre")},
    {"id": "liquiditaet", "frage": "Welchen Teil könntest du in den nächsten drei Jahren brauchen?",
     "antworten": ("den Großteil", "etwa die Hälfte", "etwa ein Viertel", "wenig", "nichts")},
    {"id": "verlust", "frage": "Welchen vorübergehenden Rückgang des Depotwerts würdest du aushalten, ohne zu verkaufen?",
     "antworten": ("höchstens 5 %", "höchstens 10 %", "höchstens 20 %", "höchstens 30 %", "40 % und mehr")},
    {"id": "risiko", "frage": "Was ist dir wichtiger?",
     "antworten": ("Sicherheit, auch bei wenig Ertrag", "eher Sicherheit", "ausgewogen", "eher Ertrag", "Ertrag, auch mit großen Schwankungen")},
    {"id": "erfahrung", "frage": "Welche Erfahrung hast du mit Wertpapieren?",
     "antworten": ("keine", "wenig", "einige Jahre mit Fonds/ETFs", "mehrere Jahre mit Aktien", "langjährig, auch in Krisen")},
)
VERLUST_PCT = (5, 10, 20, 30, 40)  # Antwort „verlust“ 0–4 → verkraftbarer Rückgang in %
WELT_RUECKGANG = 0.5  # angenommener vorübergehender Rückgang eines Welt-Aktien-ETF (Szenario, keine Prognose)
AKTIV_ANTEILE = (0.0, 0.1, 0.2, 0.3)
STARTKAPITAL_MIN, STARTKAPITAL_MAX = 1_000.0, 10_000_000.0


class ProfilFehler(ValueError):
    pass


def welt_anteil(punkte: int, verlust_antwort: int) -> float:
    """Welt-Anteil (0–1) aus Punktsumme und Antwort zur Verlusttragfähigkeit – die einzige Formel (siehe Modulbeschreibung)."""
    nach_punkten = 30.0 + 3.5 * punkte
    obergrenze = VERLUST_PCT[verlust_antwort] / WELT_RUECKGANG if verlust_antwort < len(VERLUST_PCT) - 1 else 100.0
    wert = min(nach_punkten, obergrenze, 100.0)
    return max(10.0, math.floor(wert / 5.0 + 1e-9) * 5.0) / 100.0


def ableiten(antworten: dict) -> dict:
    """Testprofil aus den fünf Antworten (je 0–4). Rückgabe mit Herleitung in Sätzen."""
    if not isinstance(antworten, dict) or set(antworten) != {f["id"] for f in FRAGEN}:
        raise ProfilFehler("genau fünf Antworten nötig: " + ", ".join(f["id"] for f in FRAGEN))
    werte = {}
    for f in FRAGEN:
        v = antworten[f["id"]]
        if isinstance(v, bool) or not isinstance(v, int) or not 0 <= v <= 4:
            raise ProfilFehler(f"Antwort „{f['id']}“: 0 bis 4")
        werte[f["id"]] = v
    punkte = sum(werte.values())
    welt = welt_anteil(punkte, werte["verlust"])
    nach_punkten = min(100.0, 30.0 + 3.5 * punkte)
    begrenzt = welt * 100 < math.floor(nach_punkten / 5.0 + 1e-9) * 5.0
    name = "vorsichtig" if welt <= 0.4 else "ausgewogen" if welt <= 0.7 else "wachstumsorientiert" if welt < 1.0 else "offensiv"
    herleitung = [
        f"{punkte} von 20 Punkten → nach Punkten {nach_punkten:.1f} % Welt-Aktien-ETF".replace(".", ","),
        (f"begrenzt durch den verkraftbaren Rückgang von {VERLUST_PCT[werte['verlust']]} %: bei einem vorübergehenden Rückgang des Welt-ETF um "
         f"{int(WELT_RUECKGANG * 100)} % höchstens {VERLUST_PCT[werte['verlust']] / WELT_RUECKGANG:.0f} % Welt-Anteil") if begrenzt else
        "keine Begrenzung durch den verkraftbaren Rückgang",
        f"Ergebnis (auf 5 Prozentpunkte abgerundet): {welt * 100:.0f} % Welt-Aktien-ETF, {100 - welt * 100:.0f} % Geldmarkt-ETF",
    ]
    return {"name": f"Testprofil {name}", "welt": welt, "geldmarkt": round(1.0 - welt, 4), "punkte": punkte, "antworten": werte,
            "herleitung": herleitung}


def tabelle() -> list[list[float]]:
    """Welt-Anteil für alle Punktsummen 0–20 (Zeilen) × Antworten zur Verlusttragfähigkeit 0–4 (Spalten) – für die App."""
    return [[welt_anteil(p, v) for v in range(5)] for p in range(21)]


def einrichtung_pruefen(inhalt: dict, aktiver_anteil_max: float) -> dict:
    """Eingang „pilot_einrichten“: Startkapital, Antworten, aktiver Anteil (höchstens der konfigurierte Wert)."""
    if not isinstance(inhalt, dict) or set(inhalt) != {"startkapital_eur", "antworten", "aktiver_anteil"}:
        raise ProfilFehler("Einrichtung braucht startkapital_eur, antworten und aktiver_anteil")
    kapital = inhalt["startkapital_eur"]
    if isinstance(kapital, bool) or not isinstance(kapital, (int, float)) or not STARTKAPITAL_MIN <= float(kapital) <= STARTKAPITAL_MAX:
        raise ProfilFehler(f"Startkapital zwischen {STARTKAPITAL_MIN:,.0f} und {STARTKAPITAL_MAX:,.0f} EUR Spielgeld".replace(",", "."))
    aktiv = inhalt["aktiver_anteil"]
    if isinstance(aktiv, bool) or not isinstance(aktiv, (int, float)) or not any(abs(float(aktiv) - a) < 1e-9 for a in AKTIV_ANTEILE):
        raise ProfilFehler("aktiver Anteil 0, 10, 20 oder 30 %")
    if float(aktiv) > aktiver_anteil_max + 1e-9:
        raise ProfilFehler(f"aktiver Anteil höchstens {aktiver_anteil_max:.0%}")
    profil = ableiten(inhalt["antworten"])
    return {"startkapital_eur": round(float(kapital), 2), "aktiver_anteil": float(aktiv), "profil": profil}
