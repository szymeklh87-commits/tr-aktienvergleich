"""Risiko je Aktie: niedrig, mittel oder hoch – mit den zwei bis drei wichtigsten Gründen (ab 1.24.0, ``risiko-1``).

Auftrag vom 07.11.2026 (17:36 und 17:39 Uhr): verständliche Risikobewertung aus zulässigen, kostenlosen Daten; keine
undurchsichtige Punktewertung, keine erfundenen Daten Dritter. Jede Regel steht hier und in der App mit dem Wert der Aktie.

Bausteine (Punkte, je mehr, desto riskanter):
* Kursschwankung (Standardabweichung der Tagesrenditen über 60 Sitzungen, aufs Jahr gerechnet): ab 60 % 2 Punkte, ab 35 % 1.
* Abstand zum 52-Wochen-Hoch: ab −50 % 2 Punkte, ab −30 % 1.
* Verschuldung (Schulden zum Eigenkapital, ohne Banken und Versicherungen): über 2,0 2 Punkte, über 1,0 1.
* Liquidität (kurzfristige Mittel zu kurzfristigen Schulden): unter 0,5 2 Punkte, unter 1,0 1.
* Verlust (Nettomarge unter null) 1 Punkt; negativer freier Cashflow 1 Punkt.
* Umsatz im letzten Quartal mehr als 10 % unter dem Vorjahr 1 Punkt; Gewinn mehr als 30 % darunter 1 Punkt.
* Börsenwert unter 50 Mio. € 2 Punkte, unter 300 Mio. € 1.
* Leerverkaufsanteil über 15 % des Streubesitzes 1 Punkt.
* Schlagzeilen der letzten drei Tage überwiegend negativ (mindestens zwei) 1 Punkt.

Stufe: 0–1 Punkte niedrig, 2–3 mittel, ab 4 hoch. Fehlen die Bilanzkennzahlen, ist das Ergebnis höchstens „mittel“ und als
unvollständig gekennzeichnet – fehlende Daten machen eine Aktie nie risikoarm. Ohne Kursreihe: „nicht beurteilbar“.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

VERSION = "risiko-1"
FINANCIAL_SECTORS = {"Financial Services", "Financials", "Banks", "Insurance"}
LEVELS = ("niedrig", "mittel", "hoch", "unbekannt")


@dataclass
class Risk:
    level: str  # niedrig · mittel · hoch · unbekannt
    points: int
    reasons: list[str] = field(default_factory=list)  # die wichtigsten zwei bis drei (riskanteste zuerst)
    complete: bool = True


def _num(x) -> float | None:
    try:
        value = float(x)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def _pct(x: float, digits: int = 0) -> str:
    text = f"{100.0 * x:.{digits}f}".replace(".", ",")
    return f"{text} %"


def _mio(x: float) -> str:
    return f"{x / 1e6:,.0f}".replace(",", ".") + " Mio. €"


def assess(features: dict, facts: dict | None, market_cap_eur: float | None, news_positive: int = 0, news_negative: int = 0,
           data_issue: str | None = None) -> Risk:
    """Risiko aus Kursmerkmalen (``schwankung`` = Tagesstandardabweichung, ``hoch250`` und Schlusskurs) und Kennzahlen."""
    sigma = _num(features.get("schwankung"))
    close = _num(features.get("kurs"))
    high250 = _num(features.get("hoch250"))
    if data_issue:
        return Risk("unbekannt", 0, [f"Kursdaten zurückgehalten: {data_issue}"], complete=False)
    if sigma is None:
        return Risk("unbekannt", 0, ["zu kurze Kurshistorie für die Kursschwankung"], complete=False)
    items: list[tuple[int, str]] = []  # (Punkte, Grund)
    calm: list[str] = []
    yearly = sigma * math.sqrt(252.0)
    if yearly >= 0.60:
        items.append((2, f"sehr hohe Kursschwankung ({_pct(yearly)} pro Jahr)"))
    elif yearly >= 0.35:
        items.append((1, f"hohe Kursschwankung ({_pct(yearly)} pro Jahr)"))
    elif yearly < 0.25:
        calm.append(f"geringe Kursschwankung ({_pct(yearly)} pro Jahr)")
    if close is not None and high250 is not None and high250 > 0:
        dd = close / high250 - 1.0
        if dd <= -0.50:
            items.append((2, f"{_pct(-dd)} unter dem 52-Wochen-Hoch"))
        elif dd <= -0.30:
            items.append((1, f"{_pct(-dd)} unter dem 52-Wochen-Hoch"))
    f = facts or {}
    fin = f.get("finanzen") or {}
    growth = f.get("wachstum") or {}
    risk_facts = f.get("risiko") or {}
    sector = (f.get("branche") or {}).get("sektor")
    leverage = _num(fin.get("verschuldung"))
    current = _num(fin.get("liquiditaet"))
    margin = _num(fin.get("nettomarge"))
    fcf = fin.get("free_cashflow_positiv")
    have_balance = leverage is not None or current is not None or margin is not None or isinstance(fcf, bool)
    if leverage is not None and sector not in FINANCIAL_SECTORS:
        if leverage > 2.0:
            items.append((2, f"Schulden {str(round(leverage, 1)).replace('.', ',')}-fach des Eigenkapitals"))
        elif leverage > 1.0:
            items.append((1, f"Schulden {str(round(leverage, 1)).replace('.', ',')}-fach des Eigenkapitals"))
        elif leverage < 0.5:
            calm.append("geringe Verschuldung")
    if current is not None:
        if current < 0.5:
            items.append((2, f"kurzfristige Schulden deutlich höher als kurzfristige Mittel ({str(round(current, 2)).replace('.', ',')})"))
        elif current < 1.0:
            items.append((1, f"kurzfristige Schulden höher als kurzfristige Mittel ({str(round(current, 2)).replace('.', ',')})"))
    if margin is not None and margin < 0:
        items.append((1, f"Verlust (Nettomarge {_pct(margin, 1)})"))
    if fcf is False:
        items.append((1, "negativer freier Cashflow"))
    revenue_q = _num(growth.get("umsatz_quartal"))
    earnings_q = _num(growth.get("gewinn_quartal"))
    if revenue_q is not None and revenue_q < -0.10:
        items.append((1, f"Umsatz {_pct(revenue_q)} zum Vorjahresquartal"))
    if earnings_q is not None and earnings_q < -0.30:
        items.append((1, f"Gewinn {_pct(earnings_q)} zum Vorjahresquartal"))
    if market_cap_eur is not None:
        if market_cap_eur < 50e6:
            items.append((2, f"sehr kleiner Börsenwert ({_mio(market_cap_eur)})"))
        elif market_cap_eur < 300e6:
            items.append((1, f"kleiner Börsenwert ({_mio(market_cap_eur)})"))
    short = _num(risk_facts.get("leerverkauf"))
    if short is not None and short > 0.15:
        items.append((1, f"hoher Leerverkaufsanteil ({_pct(short)} des Streubesitzes)"))
    if news_negative >= 2 and news_negative > news_positive:
        items.append((1, f"überwiegend negative Schlagzeilen ({news_negative} negativ, {news_positive} positiv)"))
    points = sum(p for p, _ in items)
    level = "niedrig" if points <= 1 else "mittel" if points <= 3 else "hoch"
    complete = have_balance
    if not complete and level == "niedrig":
        level = "mittel"  # ohne Bilanzkennzahlen nie „niedrig“
    ranked = [text for _, text in sorted(items, key=lambda x: -x[0])]
    reasons = ranked[:3]
    if level == "niedrig":
        reasons = (reasons + calm)[:3] or ["keine erhöhten Risikomerkmale gefunden"]
    if not complete:
        reasons = (reasons[:2] + ["Bilanzkennzahlen fehlen – Bewertung unvollständig"])[:3]
    return Risk(level, points, reasons, complete)
