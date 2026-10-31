"""Historische Simulation mit dem gemeinsamen Motor (Abschnitte 14, 29.8, 31.6 „Historisch testen“).

Derselbe Tagesschritt wie im Vorwärts-PAPER (``motor.tagesschritt``), nur mit simulierter Uhr: Veröffentlichung am Morgen nach
dem Datenstichtag (``ausfuehrung.veroeffentlichung_backtest``), Ausführung nach Profil an späteren Kerzen. Für Lineal-Kennzahlen
wird der Rechenkern je Entscheidungstag mit den Kursen bis zu diesem Tag neu gerechnet – **nachgerechnet** mit der heutigen
Datenrevision und dem heutigen Universum (mögliche Rückschau-Verzerrung, im Ergebnis gekennzeichnet). Kennzahlen ohne
historische Zeitreihe (``backtest = nur_vorwaerts``) lehnt der historische Test ab, statt heutige Werte einzusetzen.

Eine historische Simulation ist nie ein laufender Vorwärtstest und zählt nicht als tatsächlich vergangene Paper-Sitzung.
"""

from __future__ import annotations

import dataclasses
import math
import time
from dataclasses import dataclass, field
from typing import Callable

import numpy as np

from ..analytics.engine import InstrumentData, compute_snapshot
from ..config import MethodConfig
from ..util.timeutil import day_to_date
from . import katalog as kat
from . import motor, regeln
from .buchhaltung import replay

VORLAUF_TAGE = 180
TOP_BEHALTEN = 64  # nachgerechnete Spitzenlisten im Speicher (Regeln greifen höchstens 60 Stichtage zurück)

LINEAL_IDS = {"rendite", "r2", "steigung", "rauschen", "max_rueckgang", "beobachtungen", "datenabdeckung", "aufwaertstage", "lineal_bewertbar",
              "rang", "score", "haeufigkeit", "auswertbare_zellen", "gueltige_listen", "verschiedene_zeitraeume", "verschiedene_gewichtungen",
              "trefferanteil", "gruppe_b", "tagesumsatz_usd", "split_im_fenster", "impulstag", "uebernahmemuster", "boersenplatz_abweichung",
              "kurs_der_boerse", "split_in_historie", "otc"} | set(kat.ARCHIV_KENNZAHLEN)


class BacktestFehler(ValueError):
    pass


def lineal_fenster(eintraege: dict, regeln_liste: list[dict], method: MethodConfig) -> int:
    """Größtes Kalenderfenster, das die Regeln aus dem Rechenkern brauchen (0 = keine Lineal-Kennzahl)."""
    biggest = 0
    for r in regeln_liste:
        p = regeln.pruefen(r, eintraege, method)
        if not p.gueltig:
            raise BacktestFehler(f"Regel {r.get('id')} ungültig")
        uses = set(p.benoetigt["kennzahlen"]) & LINEAL_IDS or any(q["art"] in ("rangliste", "haeufigkeit") for q in p.regel["kandidaten"])
        if uses:
            biggest = max(biggest, int(p.benoetigt["fenster_kalendertage"] or 0), 1)
            for q in p.regel["kandidaten"]:
                if q["art"] in ("rangliste", "haeufigkeit"):
                    biggest = max(biggest, q["fenster"]["bis"])
    return min(biggest, int(method.max_window))


def pruefe_historisch(eintraege: dict, regeln_liste: list[dict], method: MethodConfig) -> list[str]:
    """Gründe, warum eine Regel nicht historisch testbar ist (leer = testbar)."""
    out = []
    for r in regeln_liste:
        p = regeln.pruefen(r, eintraege, method)
        if not p.gueltig:
            out.append(f"{r.get('id')}: ungültig")
            continue
        if p.benoetigt["nur_vorwaerts"]:
            names = ", ".join(eintraege[i].kennzahl.name for i in p.benoetigt["nur_vorwaerts"])
            out.append(f"{r['name']}: ohne historische Zeitreihe nur vorwärts prüfbar ({names})")
        if p.benoetigt["ranglistenarchiv"]:
            out.append(f"{r['name']}: Variante B braucht archivierte damalige Ranglisten – historisch nur nachgerechnet, nicht archiviert")
    return out


@dataclass
class Kontextquelle:
    """Kontext je Entscheidungstag. Der Rechenkern läuft je Tag mit den Kursen bis zu diesem Tag (alle Fenster 1–90 wie im
    täglichen Lauf – die Methode lässt keine verkürzte Rechnung zu); daraus kommen Lineal-Kennzahlen und der Ø Tagesumsatz.
    Zwischenspeicher: die letzten Rechnungen und je Tag die Spitzenplätze (für Variante B, nachgerechnet)."""

    method: MethodConfig
    cfg: object
    markt: object
    instrumente: list[InstrumentData]
    stamm: dict
    fenster: int
    fx: object = None
    fakten_fn: Callable[[int], dict] | None = None
    _comp: dict = field(default_factory=dict)
    _ctx: dict = field(default_factory=dict)
    _top: dict = field(default_factory=dict)
    rechnungen: int = 0
    rechenzeit_s: float = 0.0

    def comp(self, day: int):
        day = int(day)
        if day not in self._comp:
            from ..jobs.daily import own_cutoff_day

            started = time.monotonic()
            first = day - VORLAUF_TAGE  # wie im täglichen Lauf: Kurse und Sitzungen ab D − 180
            cut = []
            for inst in self.instrumente:
                if inst.days is None or not len(inst.days) or inst.pre_status:
                    cut.append(inst)
                    continue
                lo = int(np.searchsorted(inst.days, first))
                hi = int(np.searchsorted(inst.days, day, side="right"))
                sessions = inst.sessions
                own = None
                if sessions is not None and len(sessions):
                    sessions = sessions[int(np.searchsorted(sessions, first)):int(np.searchsorted(sessions, day, side="right"))]
                    own = own_cutoff_day(inst.days[lo:hi], inst.close[lo:hi], sessions, day, self.method.last_close_max_missed_sessions)
                cut.append(dataclasses.replace(inst, days=inst.days[lo:hi], close=inst.close[lo:hi], volume=inst.volume[lo:hi], sessions=sessions,
                                               splits=[s for s in inst.splits if int(s.day) <= day], cutoff_day=own))
            self._comp[day] = compute_snapshot(cut, day, self.method, self.fx)
            self.rechnungen += 1
            self.rechenzeit_s += time.monotonic() - started
            for old in sorted(self._comp)[:-3]:
                if old != day:  # ein nachträglich angefragter älterer Tag (Archiv) bleibt bis zur Rückgabe erhalten
                    del self._comp[old]
        return self._comp[day]

    def kontext(self, day: int) -> kat.Kontext:
        day = int(day)
        if day not in self._ctx:
            comp = self.comp(day)
            fakten = self.fakten_fn(day) if self.fakten_fn is not None else {}
            self._ctx = {day: kat.Kontext(tag=day, isins=list(comp.isins), method=self.method, comp=comp, markt=self.markt, cfg=self.cfg,
                                          stamm=self.stamm, fakten=fakten, modus="backtest")}
        return self._ctx[day]

    def umsatz_eur(self, isin: str, day: int) -> float | None:
        """Ø Tagesumsatz aus derselben Rechnung wie die Rangliste (USD → EUR mit dem Referenzkurs des Tages)."""
        ctx = self.kontext(day)
        k = ctx.index.get(isin)
        turnover = getattr(ctx.comp, "turnover", None)
        if k is None or not turnover or turnover[k] is None or not turnover[k].determined:
            return None
        rate = self.markt.eur_rate("USD", int(day))
        return None if rate is None else float(turnover[k].avg_usd) * rate

    def spitzen(self, day: int) -> dict[str, list[str]]:
        day = int(day)
        if day not in self._top:
            from .tageslauf import rang_archiv_inhalt

            self._top[day] = rang_archiv_inhalt(self.comp(day))
            # Regeln greifen höchstens 60 Stichtage zurück (Variante B, Rangverlauf): ältere Listen nicht im Speicher halten
            for old in sorted(self._top)[:-TOP_BEHALTEN]:
                del self._top[old]
        return self._top[day]


class NachgerechnetesArchiv:
    """Variante B im historischen Test: Spitzenplätze früherer Stichtage aus der Nachrechnung (gekennzeichnet), nicht aus dem
    Archiv tatsächlich veröffentlichter Stände."""

    def __init__(self, quelle: Kontextquelle, tage: list[int]):
        self.quelle = quelle
        self.tage = sorted(int(d) for d in tage)

    def letzte_tage(self, tag: int, n: int) -> list[int]:
        k = int(np.searchsorted(np.asarray(self.tage, dtype=np.int64), int(tag), side="right"))
        return self.tage[max(0, k - int(n)):k]

    def top(self, tag: int, gruppe: str, politik: str, h: int, w: int, n: int) -> list[str]:
        from .tageslauf import rang_archiv_schluessel

        return list(self.quelle.spitzen(tag).get(rang_archiv_schluessel(gruppe, politik, h, w), []))[:n]


@dataclass
class Ergebnis:
    depots: dict[str, motor.DepotZustand]
    tage: list[int]
    kennzahlen: dict[str, dict]
    hinweise: list[str]


def kennzahlen(z: motor.DepotZustand, start_kapital: float) -> dict:
    werte = z.werte
    if not werte:
        return {}
    end = float(werte[-1]["gesamt_eur"])
    peak = None
    worst = 0.0
    for w in werte:
        v = float(w["gesamt_eur"])
        peak = v if peak is None else max(peak, v)
        worst = max(worst, 1.0 - v / peak if peak > 0 else 0.0)
    book = replay(z.depot_id, z.events)
    gains = [r.gain_eur for r in book.realized if r.gain_eur is not None]
    plus = sum(g for g in gains if g > 0)
    minus = -sum(g for g in gains if g < 0)
    days = (int(werte[-1]["tag"]) - int(werte[0]["tag"])) or 1
    total = end / start_kapital - 1.0 if start_kapital > 0 else None
    return {
        "endwert_eur": round(end, 2), "rendite_pct": None if total is None else round(100.0 * total, 2),
        "rendite_pro_jahr_pct": None if total is None or days < 365 else round(100.0 * ((1 + total) ** (365.0 / days) - 1.0), 2),
        "max_rueckgang_pct": round(100.0 * worst, 2), "verkaeufe_mit_ergebnis": len(gains),
        "gewinnquote_pct": None if not gains else round(100.0 * sum(1 for g in gains if g > 0) / len(gains), 1),
        "profitfaktor": None if minus <= 0 else round(plus / minus, 3), "kosten_eur": round(book.fees_eur, 2),
        "kaeufe": sum(1 for e in z.events if e.typ == "kauf"), "verkaeufe": sum(1 for e in z.events if e.typ == "verkauf"),
        "kalendertage": days,
    }


def laufen(defs: list[motor.DepotDef], tage: list[int], quelle: Kontextquelle, *, cfg, method: MethodConfig, eintraege: dict, calendars,
           stamm_fn: Callable[[str], dict], synthetisch: bool, modus: str = "backtest", zustaende: dict[str, motor.DepotZustand] | None = None,
           archiv=None, nach_schritt: Callable[[motor.DepotDef, motor.DepotZustand, motor.Tagesergebnis], None] | None = None) -> Ergebnis:
    """Alle Depots über die Handelstage ``tage`` (aufsteigend) – derselbe Tagesschritt wie im täglichen Lauf. ``nach_schritt``
    bekommt jedes Tagesergebnis (z. B. zum Speichern)."""
    states = zustaende if zustaende is not None else {d.id: motor.DepotZustand(d.id) for d in defs}
    notes: list[str] = ["Ranglisten und Kennzahlen je Tag nachgerechnet (heutige Datenrevision und heutiges Universum – mögliche Rückschau-Verzerrung)"]
    for D in tage:
        for d in defs:
            u = motor.Umwelt(cfg=cfg, method=method, eintraege=eintraege, markt=quelle.markt, tag=int(D), kontext=lambda D=D: quelle.kontext(int(D)),
                             calendars=calendars, archiv=archiv, umsatz_eur=lambda isin, D=D: quelle.umsatz_eur(isin, int(D)), stamm=stamm_fn,
                             modus=modus, synthetisch=synthetisch)
            res = motor.tagesschritt(d, states[d.id], u)
            if nach_schritt is not None:
                nach_schritt(d, states[d.id], res)
    metrics = {d.id: kennzahlen(states[d.id], d.startkapital_eur) for d in defs}
    return Ergebnis(states, list(tage), metrics, notes)


def handelstage(markt, von: int, bis: int) -> list[int]:
    return [int(d) for d in markt.calendar_days(von, bis)]


def datum(day: int) -> str:
    return day_to_date(int(day)).isoformat()


def instrumente_aus_markt(markt, isins: list[str], sessions: dict[str, np.ndarray]) -> list[InstrumentData]:
    """Rechenkern-Eingaben aus den Tageskerzen (Schlusskurs, Volumen, Kalender der Börse) – für die Nachrechnung."""
    out = []
    for isin in sorted(isins):
        s = markt.series.get(isin)
        if s is None or not len(s.days):
            continue
        cal = sessions.get(s.calendar or "") if s.calendar else None
        out.append(InstrumentData(isin=isin, sessions=cal if cal is not None else s.days, days=s.days, close=s.close * 1.0, volume=s.volume * 1.0,
                                  currency=s.currency, unit_factor=1.0))
    return out


def wertvergleich(ergebnis: Ergebnis, benchmark_id: str) -> dict[str, dict]:
    """Abstand jedes Depots zum Vergleichsdepot über denselben Zeitraum (Prozentpunkte)."""
    base = ergebnis.kennzahlen.get(benchmark_id) or {}
    out = {}
    for did, k in ergebnis.kennzahlen.items():
        if not k or not base or k.get("rendite_pct") is None or base.get("rendite_pct") is None:
            continue
        out[did] = {"abstand_pp": round(k["rendite_pct"] - base["rendite_pct"], 2)}
    return out


def _finite(x) -> bool:
    return x is not None and math.isfinite(float(x))
