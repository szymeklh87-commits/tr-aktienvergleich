"""Kaufsignal nach fester Regel – „Signalregel 2“ (ab 1.23.0; „Signalregel 1“ ab 1.21.0 mit 1 Mio. € Mindestumsatz).

Aus den Tagesschlusskursen einer Aktie entsteht ein nachvollziehbarer Handelsplan: Signalstatus, Einstiegslimit,
Stop-Loss, Kursziel und Chance-Risiko-Verhältnis (CRV). Jede Bedingung ist eine einfache, veröffentlichte Regel mit
dem Wert der Aktie; fehlen Daten, gibt es kein Signal („kein Kauf“) – es wird nie geschätzt.

Grundlage sind nur Daten bis zum Schlusskurs des Kursstichtags (keine Zukunftsdaten). Das ist keine Anlageberatung
und keine Kaufempfehlung, sondern eine Regel, deren Bedingungen und Rechenweg in der App stehen. Die Rechnung von Stop,
Ziel und CRV folgt dem Ausstiegsplaner des quelloffenen Pakets „daytrader-skill“ (MIT-Lizenz; Stop als Vielfaches der
ATR unter dem Einstieg, Ziel als Vielfaches des Risikos „R“, Mindestabstand des Stops), hier eigenständig umgesetzt für
Tageskerzen statt Minutenkerzen.

Status
* ``kaufsignal`` – Ausgangslage, Zeitpunkt und Ereignisse in Ordnung, CRV mindestens 2.
* ``beobachten`` – die Ausgangslage stimmt, aber der Einstieg ist zu spät (überdehnt, überkauft, Kurslücke), Zahlen
  stehen an, die Nachrichten sind überwiegend negativ oder das CRV ist zu klein.
* ``kein_kauf`` – Daten fehlen oder die Ausgangslage (Handelbarkeit, Umsatz, Trend, Stärke, Nähe zum Hoch, Umsatz der
  letzten Sitzung) stimmt nicht.

Ob die Daten aktuell und geprüft sind (offizieller Stand, kein DEMO, keine ungeprüften Kurse), entscheidet zusätzlich
die App – ohne aktuelle, geprüfte Daten zeigt sie „KEIN KAUF“, gleich was hier steht.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

RULE_VERSION = "signalregel-2"

# ab 1.23.0 (Simons Vorgabe vom 07.11.2026, dauerhaft): reguläre Kaufkandidaten nur ab 10 Mio. USD Ø Tagesumsatz
MIN_TURNOVER_USD = 10_000_000.0  # Ø Tagesumsatz der letzten 20 Sitzungen in USD
MIN_STRENGTH_PCTILE = 70.0       # Kursänderung 20 Sitzungen besser als 70 % aller Aktien
NEAR_HIGH = 0.97                 # Schlusskurs höchstens 3 % unter dem höchsten Schlusskurs der letzten 20 Sitzungen
MIN_RVOL = 1.0                   # Umsatz der letzten Sitzung mindestens so hoch wie im Durchschnitt der 20 davor
MAX_EXTENSION_ATR = 3.0          # höchstens 3 Tagesspannen (ATR) über der 20-Tage-Linie, sonst zu spät
MAX_RSI = 75.0                   # darüber überkauft
MAX_GAP_ATR = 1.0                # Kurslücke zur Eröffnung höchstens eine Tagesspanne
ENTRY_ATR = 0.25                 # Einstiegslimit = Schlusskurs + 0,25 ATR (nicht hinterherlaufen)
STOP_ATR = 2.0                   # Stop = Einstieg − 2 ATR
TARGET_R = 2.0                   # Kursziel = Einstieg + 2 × Risiko
MIN_CRV = 2.0
MIN_TARGET_ANALYSTS = 3          # Ø Kursziel der Analysten zählt ab 3 Analysten
EARNINGS_DAYS = 3                # Geschäftszahlen in den nächsten 3 Kalendertagen: beobachten
MIN_RISK_SHARE = 0.0005          # Stop mindestens 0,05 % unter dem Einstieg (sonst im Spread)

RULES = {
    "version": RULE_VERSION,
    "mindestumsatz_usd": MIN_TURNOVER_USD,
    "staerke_perzentil": MIN_STRENGTH_PCTILE,
    "naehe_hoch": NEAR_HIGH,
    "umsatz_faktor": MIN_RVOL,
    "max_ueberdehnung_atr": MAX_EXTENSION_ATR,
    "max_rsi": MAX_RSI,
    "max_kursluecke_atr": MAX_GAP_ATR,
    "einstieg_atr": ENTRY_ATR,
    "stop_atr": STOP_ATR,
    "ziel_r": TARGET_R,
    "min_crv": MIN_CRV,
    "ziel_analysten_ab": MIN_TARGET_ANALYSTS,
    "zahlen_tage": EARNINGS_DAYS,
    "beschreibung": (
        "Kaufsignal nur, wenn alle Bedingungen erfüllt sind: handelbar, Ø Tagesumsatz ≥ 10 Mio. USD, Kurs über der 20- und "
        "50-Tage-Linie (20 über 50), in 20 Sitzungen stärker als 70 % aller Aktien, höchstens 3 % unter dem 20-Tage-Hoch, "
        "Umsatz der letzten Sitzung mindestens durchschnittlich; nicht zu spät (höchstens 3 ATR über der 20-Tage-Linie, "
        "RSI höchstens 75, Kurslücke höchstens 1 ATR); keine Geschäftszahlen in den nächsten 3 Tagen, Schlagzeilen nicht "
        "überwiegend negativ. Einstiegslimit = Schlusskurs + 0,25 ATR, Stop = Einstieg − 2 ATR, Kursziel = Einstieg + 2 × "
        "Risiko (liegt das Ø Kursziel von mindestens 3 Analysten darunter, gilt es), Chance-Risiko-Verhältnis mindestens 2. "
        "ATR = Ø Tagesspanne der letzten 14 Sitzungen. Keine Anlageberatung."
    ),
}

STATUS_ORDER = {"kaufsignal": 0, "beobachten": 1, "kein_kauf": 2}


@dataclass
class PlanInput:
    """Werte einer Aktie zum Schlusskurs des Kursstichtags (Kurseinheit der Notierung)."""

    close: float | None
    day: int | None
    atr_share: float | None          # Ø Tagesspanne (14) als Anteil am Kurs
    sma20: float | None
    sma50: float | None
    high20: float | None
    rsi: float | None
    gap: float | None                # Eröffnung gegenüber dem Vortagesschluss (Anteil)
    rvol: float | None               # Umsatz der letzten Sitzung / Ø der 20 davor
    strength_pctile: float | None    # Perzentil der Kursänderung über 20 Sitzungen im Universum (0–100)
    turnover_usd: float | None       # Ø Tagesumsatz in USD (20 Sitzungen)
    tradable: bool = True            # laut TR-Liste handelbar
    analyst_target: float | None = None   # Ø Kursziel (Kurseinheit der Notierung)
    analysts: int = 0
    news_positive: int = 0           # Schlagzeilen der letzten 3 Tage
    news_negative: int = 0
    earnings_day: int | None = None  # nächster Termin für Geschäftszahlen (Epochentag)
    data_issue: str | None = None    # z. B. „Kurse zurückgehalten“ – dann kein Signal


@dataclass
class Check:
    key: str
    label: str
    ok: bool | None   # None = nicht bewertbar (fehlende Daten)
    value: str
    rule: str
    group: str        # basis · ausgangslage · zeitpunkt · ereignis · risiko

    def as_dict(self) -> dict:
        return {"key": self.key, "label": self.label, "ok": self.ok, "wert": self.value, "regel": self.rule, "gruppe": self.group}


@dataclass
class TradePlan:
    status: str
    reason: str
    entry: float | None = None
    stop: float | None = None
    target: float | None = None
    target_basis: str | None = None   # „2R“ oder „analysten“
    crv: float | None = None
    risk_share: float | None = None   # (Einstieg − Stop) / Einstieg
    late: bool = False
    checks: list[Check] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "regel": RULE_VERSION,
            "status": self.status,
            "grund": self.reason,
            "einstieg": self.entry,
            "stop": self.stop,
            "ziel": self.target,
            "ziel_basis": self.target_basis,
            "crv": self.crv,
            "risiko_anteil": None if self.risk_share is None else round(self.risk_share, 5),
            "zu_spaet": self.late,
            "pruefungen": [c.as_dict() for c in self.checks],
        }


def _finite(x) -> bool:
    return x is not None and isinstance(x, (int, float)) and math.isfinite(x)


def tick_of(price: float) -> float:
    """Kursschritt zum Runden: 0,01 ab einem Kurs von 1, darunter 0,0001."""
    return 0.01 if price >= 1.0 else 0.0001


def round_up(x: float, tick: float) -> float:
    return round(math.ceil(round(x / tick, 6)) * tick, 6)


def round_down(x: float, tick: float) -> float:
    return round(math.floor(round(x / tick, 6)) * tick, 6)


def num_de(x: float, digits: int = 2) -> str:
    return f"{x:,.{digits}f}".replace(",", "§").replace(".", ",").replace("§", ".")


def pct_de(x: float, digits: int = 1) -> str:
    return f"{'+' if x > 0 else ''}{num_de(100.0 * x, digits)} %"


def plan_trade(p: PlanInput) -> TradePlan:
    """Handelsplan nach Signalregel 1. Reihenfolge der Gründe: Basis, Ausgangslage, Risiko, Zeitpunkt, Ereignisse."""
    checks: list[Check] = []
    close = p.close if _finite(p.close) and p.close > 0 else None
    atr_abs = p.atr_share * close if close is not None and _finite(p.atr_share) and p.atr_share > 0 else None

    # ---------------- Basis
    checks.append(Check("daten", "Kursdaten geprüft", p.data_issue is None, p.data_issue or "ohne Auffälligkeit",
                        "keine zurückgehaltenen oder unbestätigten Kurse", "basis"))
    if not p.tradable:
        checks.append(Check("handelbar", "Bei Trade Republic gelistet", False, "nein", "in der Instrumentenliste von Trade Republic", "basis"))
    turnover_ok = None if not _finite(p.turnover_usd) else p.turnover_usd >= MIN_TURNOVER_USD
    checks.append(Check("umsatz", "Ø Tagesumsatz", turnover_ok,
                        "unbekannt" if not _finite(p.turnover_usd) else f"{num_de(p.turnover_usd / 1e6, 1)} Mio. USD",
                        "mindestens 10 Mio. USD pro Handelstag (Ø 20 Sitzungen)", "basis"))

    # ---------------- Ausgangslage
    trend_ok = None
    trend_value = "zu kurze Kurshistorie"
    if close is not None and _finite(p.sma20) and _finite(p.sma50):
        trend_ok = close > p.sma20 > p.sma50
        trend_value = ("über der 20- und 50-Tage-Linie, 20 über 50" if trend_ok
                       else "über der 20-, unter der 50-Tage-Linie" if close > p.sma20 and close <= p.sma50
                       else "unter der 20-Tage-Linie" if close <= p.sma20 else "20- unter der 50-Tage-Linie")
    checks.append(Check("trend", "Trend", trend_ok, trend_value, "Kurs > 20-Tage-Linie > 50-Tage-Linie", "ausgangslage"))
    strength_ok = None if not _finite(p.strength_pctile) else p.strength_pctile >= MIN_STRENGTH_PCTILE
    checks.append(Check("staerke", "Relative Stärke (20 Sitzungen)", strength_ok,
                        "unbekannt" if not _finite(p.strength_pctile) else f"besser als {round(p.strength_pctile)} % der Aktien",
                        "besser als 70 % aller Aktien", "ausgangslage"))
    near_ok = None
    near_value = "zu kurze Kurshistorie"
    if close is not None and _finite(p.high20) and p.high20 > 0:
        ratio = close / p.high20
        near_ok = ratio >= NEAR_HIGH
        near_value = "neues 20-Tage-Hoch" if ratio >= 0.9999 else f"{pct_de(ratio - 1.0)} unter dem 20-Tage-Hoch"
    checks.append(Check("hoch", "Nähe zum 20-Tage-Hoch", near_ok, near_value, "höchstens 3 % darunter", "ausgangslage"))
    rvol_ok = None if not _finite(p.rvol) else p.rvol >= MIN_RVOL
    checks.append(Check("volumen", "Umsatz der letzten Sitzung", rvol_ok,
                        "unbekannt" if not _finite(p.rvol) else f"{num_de(p.rvol, 1)}× des Durchschnitts",
                        "mindestens durchschnittlich (1,0×)", "ausgangslage"))

    # ---------------- Zeitpunkt (zu spät?)
    ext_ok = None
    ext_value = "unbekannt"
    if close is not None and atr_abs and _finite(p.sma20):
        ext = (close - p.sma20) / atr_abs
        ext_ok = ext <= MAX_EXTENSION_ATR
        ext_value = f"{num_de(ext, 1)} ATR über der 20-Tage-Linie" if ext >= 0 else f"{num_de(-ext, 1)} ATR unter der 20-Tage-Linie"
    checks.append(Check("ueberdehnung", "Abstand zur 20-Tage-Linie", ext_ok, ext_value, "höchstens 3 ATR darüber", "zeitpunkt"))
    rsi_ok = None if not _finite(p.rsi) else p.rsi <= MAX_RSI
    checks.append(Check("rsi", "RSI (14)", rsi_ok, "unbekannt" if not _finite(p.rsi) else f"{round(p.rsi)}" + (" – überkauft" if p.rsi > MAX_RSI else ""),
                        "höchstens 75", "zeitpunkt"))
    gap_ok = None
    gap_value = "unbekannt"
    if _finite(p.gap) and _finite(p.atr_share) and p.atr_share > 0:
        gap_ok = p.gap <= MAX_GAP_ATR * p.atr_share
        gap_value = f"{pct_de(p.gap)} zur Eröffnung"
    checks.append(Check("kursluecke", "Kurslücke zur Eröffnung", gap_ok, gap_value, "höchstens 1 ATR nach oben", "zeitpunkt"))

    # ---------------- Ereignisse
    days_to_earnings = p.earnings_day - p.day if p.earnings_day is not None and p.day is not None else None
    earnings_ok = True if days_to_earnings is None or days_to_earnings < 0 else days_to_earnings > EARNINGS_DAYS
    earnings_value = ("kein Termin bekannt" if days_to_earnings is None or days_to_earnings < 0
                      else "heute" if days_to_earnings == 0
                      else f"in {days_to_earnings} {'Tag' if days_to_earnings == 1 else 'Tagen'}")
    checks.append(Check("zahlen", "Geschäftszahlen", earnings_ok, earnings_value, "nicht in den nächsten 3 Tagen", "ereignis"))
    news_ok = p.news_negative <= p.news_positive
    checks.append(Check("nachrichten", "Schlagzeilen (3 Tage)", news_ok,
                        f"{p.news_positive} positiv, {p.news_negative} negativ" if p.news_positive or p.news_negative else "keine Einordnung",
                        "nicht überwiegend negativ", "ereignis"))

    # ---------------- Entscheidung: Basis und Ausgangslage
    def first_fail(group: str) -> Check | None:
        for c in checks:
            if c.group == group and c.ok is not True:
                return c
        return None

    for group in ("basis", "ausgangslage"):
        bad = first_fail(group)
        if bad is not None:
            why = f"{bad.label}: {bad.value}" + ("" if bad.ok is None else f" (Regel: {bad.rule})")
            return TradePlan("kein_kauf", why, checks=checks)
    if close is None or atr_abs is None:
        return TradePlan("kein_kauf", "Tagesspanne (ATR) unbekannt", checks=checks)

    # ---------------- Einstieg, Stop, Ziel, CRV
    tick = tick_of(close)
    entry = round_up(close + ENTRY_ATR * atr_abs, tick)
    stop = round_down(entry - STOP_ATR * atr_abs, tick)
    if stop <= 0:
        return TradePlan("kein_kauf", "Stop läge bei oder unter null – Tagesspanne zu groß", checks=checks)
    risk = entry - stop
    if risk < MIN_RISK_SHARE * entry:
        return TradePlan("kein_kauf", "Stop zu eng (unter 0,05 % vom Kurs)", checks=checks)
    target = round_down(entry + TARGET_R * risk, tick)
    basis = "2R"
    if _finite(p.analyst_target) and p.analysts >= MIN_TARGET_ANALYSTS and p.analyst_target < target:
        target, basis = round_down(p.analyst_target, tick), "analysten"
    crv = round((target - entry) / risk, 2)
    crv_ok = crv >= MIN_CRV
    checks.append(Check("crv", "Chance-Risiko-Verhältnis", crv_ok, f"{num_de(crv, 1)} : 1" if crv > 0 else "Kursziel unter dem Einstieg",
                        "mindestens 2 : 1", "risiko"))
    plan = TradePlan("kaufsignal", "alle Bedingungen erfüllt", entry=entry, stop=stop, target=target, target_basis=basis,
                     crv=crv, risk_share=risk / entry, checks=checks)
    late = first_fail("zeitpunkt")
    if late is not None:
        plan.late = late.ok is False
        plan.status = "beobachten"
        plan.reason = (f"Einstieg zu spät – {late.label}: {late.value}; Rücksetzer Richtung 20-Tage-Linie abwarten" if plan.late
                       else f"{late.label} unbekannt")
        return plan
    event = first_fail("ereignis")
    if event is not None:
        plan.status = "beobachten"
        plan.reason = f"{event.label}: {event.value}"
        return plan
    if not crv_ok:
        plan.status = "beobachten"
        plan.reason = ("Kursziel der Analysten liegt unter dem Einstieg" if crv <= 0
                       else f"Chance-Risiko-Verhältnis {num_de(crv, 1)} : 1 unter 2 : 1 (Ø Kursziel der Analysten)")
        return plan
    return plan
