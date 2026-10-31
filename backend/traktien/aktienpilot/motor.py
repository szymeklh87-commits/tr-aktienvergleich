"""Spielgeld-Motor: ein gemeinsamer Tagesschritt für Vorwärts-PAPER, historische Simulation und DEMO (Abschnitte 29.3, 18).

Ablauf je Depot und neuem Datenstichtag ``D`` (``tagesschritt``) – derselbe Code für Backtest und PAPER:

1. Idempotenz: ein Stichtag wird je Depot genau einmal verarbeitet (``letzter_tag``).
2. Für jede Sitzung seit dem letzten Lauf in zeitlicher Folge: Splits buchen → Orders zur Eröffnung (erst Verkäufe, dann
   Käufe) → hinterlegte Stops (Tagestief, Kurslücke) → Orders zum Schluss (erst Verkäufe, dann Käufe). Bewertung zum
   Sitzungsschluss und Verlustgrenzen des aktiven Teils.
3. Verluststufe „schließen“ → Risikoverkäufe aller aktiven Positionen (Kern und fremde Bestände ausgenommen).
4. Tägliche Prüfung zum Schluss: fällige Gewinnmitnahmen, Nachziehen der Trailing-Stops (nie nach unten).
5. Entscheidungen der Regeln nach ihrem Zeitplan: Auswahl, freiwillige Ausstiege, Käufe – jede Stückzahl durch den zentralen
   Risiko-Manager; Guthaben und offene Käufe werden depotweit reserviert (derselbe Euro nie doppelt).
6. Robo-Kern: Zielaufteilung, zuerst freies Guthaben, Umschichtung erst ab der Schwelle.
7. Journal mit Begründung für jedes Handeln und Nicht-Handeln.

Orders werden zum Zeitpunkt ihrer Veröffentlichung geplant (``zeitregel.plan``) und erst ausgeführt, wenn die Kerze ihrer
Ausführungssitzung vorliegt – nie zu einem Kurs vor der Veröffentlichung. Echtgeld gibt es in diesem Motor nicht: jede Order ist
virtuell (``modus`` PAPER bzw. DEMO), es existiert kein Brokeradapter und kein Weg zu einer echten Order (Abschnitt 29.1).
"""

from __future__ import annotations

import datetime as dt
import hashlib
import math
from dataclasses import dataclass, field
from typing import Any, Callable

import numpy as np

from ..util.timeutil import UTC, day_to_date
from . import auswertung, gewinnziel, zeitregel
from .ausfuehrung import Fill, NichtAusgefuehrt, SimOrder, ausfuehren, buy_price_factor, sell_price_factor, stop_pruefen
from .buchhaltung import Book, Event, is_active_owner, value
from .config import AktienPilotConfig
from .katalog import Kontext, _atr_last
from .risiko import BuyRequest, Exposure, LossLimits, check_sell, size_buy

MOTOR_VERSION = "motor-1"
RESERVE_PUFFER = 0.02  # Reservierung eines Kaufs: geschätzter Kurswert + 2 % + Gebühr
KERN_MINDESTORDER_EUR = 50.0


# ------------------------------------------------------------------------------------------------ Definitionen


@dataclass(frozen=True)
class StrategieDef:
    zuordnung: str  # Zuordnung der Bestände (z. B. „r-s1“) – zugleich Strategiename im Journal
    regel: dict  # geprüfte, normalisierte Regel (mit ID und Version)
    anteil: float  # Anteil am aktiven Budget (Summe ≤ 1)


@dataclass(frozen=True)
class KernDef:
    ziele: dict[str, float]  # ISIN → Zielgewicht im Kern (Summe 1)
    schwelle_pp: float = 5.0
    rebalancing: bool = True  # False: nur Zuflüsse anlegen (Kaufen und Halten, z. B. Vergleich Welt-ETF)


@dataclass(frozen=True)
class DepotDef:
    id: str
    name: str
    art: str  # pilot | forschung | vergleich
    startkapital_eur: float
    start_tag: int
    aktiver_anteil: float  # Anteil des aktiven Teils am Depot (Pilot 0,30; Forschung 1,0; nur Kern 0,0)
    strategien: tuple[StrategieDef, ...] = ()
    kern: KernDef | None = None
    synthetisch: bool = False
    beschreibung: str = ""

    @property
    def bezug_faktor(self) -> float:
        """Bezugsgröße „Gesamtdepot“ der Risikogrenzen (Abschnitt 15): ein reines Strategiedepot steht für den aktiven Teil."""
        return 1.0


@dataclass
class Position:
    zuordnung: str
    isin: str
    eroeffnet: int
    urspruenglich: float
    gm: dict = field(default_factory=dict)
    stop: float | None = None
    hoechster: float | None = None
    regel: str | None = None
    atr_bei_kauf: float | None = None

    @property
    def key(self) -> str:
        return f"{self.zuordnung}|{self.isin}"

    def as_dict(self) -> dict:
        return {"zuordnung": self.zuordnung, "isin": self.isin, "eroeffnet": self.eroeffnet, "urspruenglich": self.urspruenglich,
                "gm": self.gm, "stop": self.stop, "hoechster": self.hoechster, "regel": self.regel, "atr_bei_kauf": self.atr_bei_kauf}

    @staticmethod
    def from_dict(d: dict) -> "Position":
        return Position(d["zuordnung"], d["isin"], int(d["eroeffnet"]), float(d["urspruenglich"]), d.get("gm") or {}, d.get("stop"),
                        d.get("hoechster"), d.get("regel"), d.get("atr_bei_kauf"))


@dataclass
class DepotZustand:
    depot_id: str
    events: list[Event] = field(default_factory=list)
    orders: list[SimOrder] = field(default_factory=list)
    positionen: dict[str, Position] = field(default_factory=dict)
    sperren: dict[str, dict] = field(default_factory=dict)
    verlust: LossLimits = field(default_factory=LossLimits)
    letzter_tag: int | None = None
    werte: list[dict] = field(default_factory=list)
    journal: list[dict] = field(default_factory=list)
    letzte_auswahl: dict[str, list[str]] = field(default_factory=dict)
    entschieden: dict[str, int] = field(default_factory=dict)
    kaeufe_pausiert: bool = False
    seq: int = 0
    order_seq: int = 0
    gestartet: bool = False
    book: Book | None = None

    def buch(self) -> Book:
        if self.book is None:
            self.book = Book(self.depot_id)
            for e in sorted(self.events, key=lambda e: e.seq):
                self.book.apply(e)
        return self.book

    def offene_orders(self) -> list[SimOrder]:
        return [o for o in self.orders if o.status == "offen"]


@dataclass
class Umwelt:
    """Was ein Tagesschritt von außen bekommt (täglicher Lauf, Backtest oder DEMO)."""

    cfg: AktienPilotConfig
    method: Any
    eintraege: dict
    markt: Any  # aktienpilot.markt.Market (Aktien, Kern-ETFs, Leitindizes)
    tag: int  # Datenstichtag D (letzte abgeschlossene Sitzung)
    kontext: Callable[[], Kontext]  # Kontext des Stichtags (gemeinsame Kennzahlen; Depotwerte setzt der Motor je Strategie)
    calendars: Any = None
    archiv: Any = None
    umsatz_eur: Callable[[str], float | None] = lambda isin: None
    stamm: Callable[[str], dict] = lambda isin: {}
    jetzt: dt.datetime | None = None
    veroeffentlicht: dt.datetime | None = None
    modus: str = "paper"  # paper | backtest | demo
    synthetisch: bool = False
    lauf_id: str = ""

    def zeiten(self) -> tuple[dt.datetime, dt.datetime]:
        if self.jetzt is not None and self.veroeffentlicht is not None:
            return self.jetzt, self.veroeffentlicht
        published = zeitregel.backtest_publication(self.tag, _hhmm(self.cfg.ausfuehrung.veroeffentlichung_backtest), self.cfg.ausfuehrung.zeitzone)
        return published, published


def _hhmm(text: str) -> int:
    h, m = text.split(":")
    return int(h) * 60 + int(m)


def _iso(value: dt.datetime | None) -> str | None:
    return None if value is None else value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _datum(day: int | None) -> str | None:
    return None if day is None else day_to_date(int(day)).isoformat()


# ------------------------------------------------------------------------------------------------ Hilfen


class _Lauf:
    """Arbeitskontext eines Tagesschritts für ein Depot."""

    def __init__(self, d: DepotDef, z: DepotZustand, u: Umwelt):
        self.d, self.z, self.u = d, z, u
        self.cfg = u.cfg
        self.jetzt, self.published = u.zeiten()
        self.neu: dict[str, list] = {"ereignisse": [], "orders": [], "journal": []}

    # --- Journal und Ereignisse
    def log(self, tag: int, art: str, text: str, zuordnung: str | None = None, **daten) -> None:
        entry = {"tag": int(tag), "datum": _datum(tag), "art": art, "text": text}
        if zuordnung:
            entry["zuordnung"] = zuordnung
        if daten:
            entry["daten"] = daten
        self.z.journal.append(entry)
        self.neu["journal"].append(entry)

    def book_event(self, typ: str, tag: int, *, isin: str | None = None, stueck: float | None = None, kurs: float | None = None,
                   waehrung: str | None = None, fx: float | None = None, betrag: float = 0.0, gebuehr: float = 0.0,
                   order: SimOrder | None = None, zuordnung: str | None = None, topf: str | None = None, quelle: str = "simulator",
                   **nutzlast) -> Event:
        self.z.seq += 1
        payload = dict(nutzlast)
        if zuordnung:
            payload["zuordnung"] = zuordnung
        if topf:
            payload["topf"] = topf
        payload.setdefault("modus", "DEMO" if self.u.modus == "demo" else ("HISTORISCH" if self.u.modus == "backtest" else "PAPER"))
        raw = f"{self.d.id}|{self.z.seq}|{typ}|{tag}|{isin}|{stueck}|{order.id if order else ''}"
        event = Event(
            id="e-" + hashlib.sha256(raw.encode()).hexdigest()[:20], depot_id=self.d.id, seq=self.z.seq, zeit=_iso(self.jetzt) or "",
            tag=int(tag), typ=typ, isin=isin, stueck=stueck, kurs=kurs, waehrung=waehrung, fx_eur=fx, fx_quelle="EZB" if fx and waehrung != "EUR" else None,
            betrag_eur=float(betrag), gebuehren_eur=float(gebuehr), quelle=quelle, order_id=order.id if order else None,
            signal_id=order.signal_id if order else None, verwaltet=True, nutzlast=payload,
        )
        self.z.buch().apply(event)
        self.z.events.append(event)
        self.neu["ereignisse"].append(event)
        return event

    def new_order(self, **kw) -> SimOrder:
        self.z.order_seq += 1
        raw = f"{self.d.id}|{self.z.order_seq}|{kw['isin']}|{kw['richtung']}|{kw['datentag']}"
        order = SimOrder(id="o-" + hashlib.sha256(raw.encode()).hexdigest()[:16], depot_id=self.d.id, erstellt_am=_iso(self.jetzt) or "", **kw)
        order.signal_id = "s-" + order.id[2:]
        self.z.orders.append(order)
        self.neu["orders"].append(order)
        return order

    # --- Markt
    def series(self, isin: str):
        return self.u.markt.series.get(isin)

    def close_eur(self, isin: str, day: int) -> float | None:
        last = self.u.markt.last_close(isin, day)
        if last is None:
            return None
        return self.u.markt.price_eur(isin, last[0], day)

    def plan(self, isin: str, profil: str) -> zeitregel.Timing | None:
        s = self.series(isin)
        if s is None:
            return None
        return zeitregel.plan(s, profil, self.u.tag, self.jetzt, self.published, self.u.calendars,
                              valid_sessions=self.cfg.ausfuehrung.gueltigkeit_sitzungen, delay_minutes=self.cfg.ausfuehrung.verzoegerung_minuten)

    # --- Exposure für den Risiko-Manager
    def exposure(self, day: int) -> tuple[Exposure, Any]:
        book = self.z.buch()
        val = value(book, self.u.markt, day)
        total = val.total_eur
        reserved_active = sum(o.reserviert_eur for o in self.z.offene_orders() if o.richtung == "kauf" and is_active_owner(o.zuordnung))
        reserved_by = {}
        for o in self.z.offene_orders():
            if o.richtung == "kauf":
                reserved_by.setdefault(o.isin, 0.0)
                reserved_by[o.isin] += o.reserviert_eur
        by_isin = dict(val.positions_eur)
        for isin, r in reserved_by.items():
            by_isin[isin] = by_isin.get(isin, 0.0) + r
        by_strategy: dict[str, float] = {}
        for isin, owners in book.holdings.items():
            price = val.prices_eur.get(isin)
            for owner, qty in owners.items():
                if qty > 0 and price is not None and is_active_owner(owner):
                    by_strategy[owner] = by_strategy.get(owner, 0.0) + qty * price
        for o in self.z.offene_orders():
            if o.richtung == "kauf" and is_active_owner(o.zuordnung):
                by_strategy[o.zuordnung] = by_strategy.get(o.zuordnung, 0.0) + o.reserviert_eur
        # Gebundenes aktives Kapital: aktive Positionen (ohne freies Guthaben des Topfs) plus reservierte aktive Käufe
        active_value = val.active_eur - val.pots.get("aktiv", 0.0)
        if self.d.art == "pilot":
            reference = total
            active_cap = self.d.aktiver_anteil * total
        else:
            # Reines Strategiedepot: steht für den aktiven Teil eines Gesamtdepots mit dem konfigurierten aktiven Anteil
            share = max(1e-9, self.cfg.depot.aktiver_anteil_max)
            reference = total / share if self.d.aktiver_anteil > 0 else total
            active_cap = total * self.d.aktiver_anteil
        budgets = {s.zuordnung: s.anteil * active_cap for s in self.d.strategien}
        sector_total: dict[str, float] = {}
        sector_active: dict[str, float] = {}
        unknown = self.cfg.risiko.unbekannte_branche
        singles: set[str] = set()
        for isin, owners in book.holdings.items():
            qty = sum(q for q in owners.values() if q > 0)
            if qty <= 0:
                continue
            st = self.u.stamm(isin) or {}
            if st.get("typ", "aktie") == "aktie":
                singles.add(isin)
            sec = st.get("branche") or unknown
            v = val.positions_eur.get(isin, 0.0)
            sector_total[sec] = sector_total.get(sec, 0.0) + v
            act = sum(q for o, q in owners.items() if is_active_owner(o) and q > 0)
            if act > 0 and qty > 0:
                sector_active[sec] = sector_active.get(sec, 0.0) + v * act / qty
        for o in self.z.offene_orders():
            if o.richtung == "kauf":
                st = self.u.stamm(o.isin) or {}
                if st.get("typ", "aktie") == "aktie":
                    singles.add(o.isin)
                sec = st.get("branche") or unknown
                sector_total[sec] = sector_total.get(sec, 0.0) + o.reserviert_eur
                if is_active_owner(o.zuordnung):
                    sector_active[sec] = sector_active.get(sec, 0.0) + o.reserviert_eur
        free_active = book.pots.get("aktiv", 0.0) - reserved_active
        exp = Exposure(
            reference_eur=reference, complete=val.complete, active_cap_eur=active_cap, active_eur=active_value + reserved_active,
            free_cash_eur=free_active, by_isin_eur=by_isin, by_strategy_eur=by_strategy, strategy_budget_eur=budgets,
            sector_total_eur=sector_total, sector_active_eur=sector_active, single_stocks=singles,
        )
        return exp, val


# ------------------------------------------------------------------------------------------------ Tagesschritt


@dataclass
class Tagesergebnis:
    depot_id: str
    tag: int
    verarbeitet: bool
    grund: str
    ereignisse: list[Event] = field(default_factory=list)
    orders: list[SimOrder] = field(default_factory=list)
    journal: list[dict] = field(default_factory=list)
    bewertung: dict | None = None


def tagesschritt(d: DepotDef, z: DepotZustand, u: Umwelt) -> Tagesergebnis:
    """Ein Datenstichtag für ein Depot (idempotent)."""
    if u.tag < d.start_tag:
        return Tagesergebnis(d.id, u.tag, False, f"Depot startet erst am {_datum(d.start_tag)}")
    if z.letzter_tag is not None and u.tag <= z.letzter_tag:
        return Tagesergebnis(d.id, u.tag, False, f"Stichtag {_datum(u.tag)} bereits verarbeitet")
    if u.synthetisch != d.synthetisch:
        return Tagesergebnis(d.id, u.tag, False, "DEMO-Daten und echte Daten werden nie im selben Depot gemischt")
    lauf = _Lauf(d, z, u)
    if not z.gestartet:
        _eroeffnen(lauf)
    days = _sitzungstage(lauf)
    for day in days:
        _sitzung(lauf, day)
        _bewerten(lauf, day)
    if not days or days[-1] != u.tag:
        _bewerten(lauf, u.tag)
    _risikostufe(lauf)
    _taeglich(lauf)
    for s in d.strategien:
        _entscheiden(lauf, s)
    if d.kern is not None:
        _kern(lauf)
    z.letzter_tag = u.tag
    werte = z.werte[-1] if z.werte else None
    return Tagesergebnis(d.id, u.tag, True, "verarbeitet", lauf.neu["ereignisse"], lauf.neu["orders"], lauf.neu["journal"], werte)


def _eroeffnen(l: _Lauf) -> None:
    d, z = l.d, l.z
    tag = l.u.tag
    l.book_event("einzahlung", tag, betrag=d.startkapital_eur, topf="frei", quelle="spielgeld", text="Startkapital (Spielgeld)")
    active = round(d.startkapital_eur * d.aktiver_anteil, 2) if d.strategien else 0.0
    core = round(d.startkapital_eur - active, 2) if d.kern is not None else 0.0
    if not d.strategien and d.kern is None:
        active = 0.0
    if active > 0:
        l.book_event("umbuchung", tag, betrag=active, quelle="spielgeld", von="frei", nach="aktiv", text="Aktiver Teil")
    if core > 0:
        l.book_event("umbuchung", tag, betrag=core, quelle="spielgeld", von="frei", nach="kern", text="Robo-Kern")
    z.verlust = LossLimits.from_config(l.cfg)
    z.gestartet = True
    mode = {"demo": "DEMO mit synthetischen Kursen", "backtest": "historische Simulation", "paper": "PAPER mit echten Kursen"}[l.u.modus]
    l.log(tag, "start", f"Depot eröffnet: {d.startkapital_eur:,.2f} EUR Spielgeld ({mode}); aktiver Teil {active:,.2f} EUR, Kern {core:,.2f} EUR"
          .replace(",", "X").replace(".", ",").replace("X", "."), modus=l.u.modus)


def _sitzungstage(l: _Lauf) -> list[int]:
    """Sitzungstage seit dem letzten Lauf, an denen gehaltene oder beauftragte Aktien eine Kerze haben."""
    lo = l.z.letzter_tag if l.z.letzter_tag is not None else l.u.tag - 1
    isins = set(l.z.buch().positions()) | {o.isin for o in l.z.offene_orders()}
    days: set[int] = set()
    for isin in isins:
        s = l.series(isin)
        if s is None:
            continue
        mask = (s.days > lo) & (s.days <= l.u.tag)
        days.update(int(x) for x in s.days[mask])
    return sorted(days)


def _sitzung(l: _Lauf, day: int) -> None:
    _splits(l, day)
    _orders(l, day, "open")
    _stops(l, day)
    _orders(l, day, "close")
    _verfallen(l, day)


def _splits(l: _Lauf, day: int) -> None:
    """Splits bis einschließlich ``day`` für gehaltene Positionen buchen (Stückzahl × Faktor, Stop und Höchstkurs ÷ Faktor).

    Faktor wie in ``daily_bar``: Kurs vor dem Split = bereinigter Kurs × Faktor (2:1 → Faktor 2 → doppelte Stückzahl).
    Ein Split, den die Datenquelle erst nachträglich meldet, wird beim nächsten Lauf nachgebucht (genau einmal je Split)."""
    book = l.z.buch()
    booked = {(e.isin, int(e.nutzlast.get("split_tag", e.tag))) for e in l.z.events if e.typ == "split"}
    for isin, total in list(book.positions().items()):
        s = l.series(isin)
        if s is None or total <= 0:
            continue
        opened = min((p.eroeffnet for p in l.z.positionen.values() if p.isin == isin), default=None)
        for s_day, factor in s.splits:
            s_day = int(s_day)
            if s_day > day or (isin, s_day) in booked or factor is None or float(factor) <= 0:
                continue
            if opened is not None and s_day <= opened:
                continue  # Split vor dem Kauf: schon im Kaufkurs enthalten
            factor = float(factor)
            late = s_day < day
            l.book_event("split", day, isin=isin, faktor=factor, split_tag=s_day, quelle="kapitalmassnahme",
                         text=f"Split {factor:g}:1" + (" (nachträglich gemeldet)" if late else ""))
            booked.add((isin, s_day))
            for pos in l.z.positionen.values():
                if pos.isin == isin:
                    pos.urspruenglich *= factor
                    if pos.stop:
                        pos.stop /= factor
                    if pos.hoechster:
                        pos.hoechster /= factor
            l.log(day, "kapitalmassnahme", f"Split {factor:g}:1 gebucht – Stückzahl ×{factor:g}, Stop und Höchstkurs ÷{factor:g}, kein Gewinn"
                  + (f" (Ex-Tag {_datum(s_day)}, nachträglich gemeldet)" if late else ""), isin=isin)


def _orders(l: _Lauf, day: int, point: str) -> None:
    due = [o for o in l.z.offene_orders() if o.sitzung == day and o.preispunkt == point]
    due.sort(key=lambda o: (0 if o.richtung == "verkauf" else 1, o.id))
    for o in due:
        s = l.series(o.isin)
        if s is None:
            _abschluss(l, o, "abgelehnt", f"keine Kursreihe für {o.isin}", day)
            continue
        book = l.z.buch()
        pot = "kern" if o.zuordnung == "kern" else "aktiv"
        held = book.qty(o.isin, o.zuordnung)
        if o.richtung == "kauf":
            available = book.pots.get(pot, 0.0) - sum(x.reserviert_eur for x in l.z.offene_orders()
                                                        if x.richtung == "kauf" and x.id != o.id and (x.zuordnung == "kern") == (o.zuordnung == "kern"))
        else:
            available = 0.0
        result = ausfuehren(o, s, l.u.markt, l.cfg, turnover_eur=l.u.umsatz_eur(o.isin), verfuegbar_eur=available, gehalten=held)
        if isinstance(result, NichtAusgefuehrt):
            if result.neu_einplanen:
                _neu_einplanen(l, o, day, result.grund)
            else:
                _abschluss(l, o, "verfallen" if o.richtung == "kauf" else "abgelehnt", result.grund, day)
            continue
        _buchen(l, o, result, pot)


def _buchen(l: _Lauf, o: SimOrder, f: Fill, pot: str) -> None:
    s = l.series(o.isin)
    l.book_event("kauf" if o.richtung == "kauf" else "verkauf", f.tag, isin=o.isin, stueck=float(f.stueck), kurs=f.kurs, waehrung=s.currency,
                 fx=f.fx_eur, betrag=f.betrag_eur, gebuehr=f.gebuehr_eur, order=o, zuordnung=o.zuordnung, topf=pot,
                 referenzkurs=f.referenzkurs, kosten=f.kosten, grund=o.grund, regel=o.regel, hinweis=f.hinweis)
    o.ausgefuehrt_stueck += f.stueck
    o.status = "ausgefuehrt" if o.ausgefuehrt_stueck >= o.stueck else "teilweise"
    o.reserviert_eur = 0.0
    key = f"{o.zuordnung}|{o.isin}"
    if o.richtung == "kauf":
        pos = l.z.positionen.get(key)
        if pos is None:
            pos = Position(o.zuordnung, o.isin, f.tag, float(f.stueck), {}, None, f.referenzkurs, o.regel)
            l.z.positionen[key] = pos
        else:
            pos.urspruenglich += f.stueck
        if o.stop_plan:
            if o.stop_plan["art"] == "atr":
                stop = f.referenzkurs - float(o.stop_plan["abstand"])
            else:
                stop = f.referenzkurs * (1.0 - float(o.stop_plan["wert"]) / 100.0)
            if stop > 0:
                pos.stop = stop if pos.stop is None else max(pos.stop, stop)
            pos.atr_bei_kauf = o.stop_plan.get("atr")
        text = f"Kauf {f.stueck} Stück zu {f.kurs:.4f} {s.currency} (Kurs {f.referenzkurs:.4f}, Kosten eingerechnet)"
    else:
        remaining = l.z.buch().qty(o.isin, o.zuordnung)
        pos = l.z.positionen.get(key)
        if pos is not None:
            if o.stufen:
                st = gewinnziel.Stufenzustand.from_dict(pos.gm, pos.urspruenglich)
                for stage in o.stufen:
                    st.offen.pop(stage, None)
                    if stage == "ganz":
                        st.erledigt.append(0)
                    else:
                        st.erledigt.append(int(stage))
                pos.gm = st.as_dict()
            if remaining <= 1e-9:
                del l.z.positionen[key]
                _sperre_setzen(l, o.zuordnung, o.isin, f.tag)
                for other in l.z.offene_orders():
                    if other.id != o.id and other.isin == o.isin and other.zuordnung == o.zuordnung and other.richtung == "verkauf":
                        other.status = "storniert"
                        other.begruendung = dict(other.begruendung, abschluss="Position bereits vollständig verkauft")
                        l.log(f.tag, "order", f"Verkaufsorder storniert: Position bereits durch „{o.grund}“ verkauft", o.zuordnung, isin=o.isin, order=other.id)
        text = f"Verkauf {f.stueck} Stück zu {f.kurs:.4f} {s.currency} (Kurs {f.referenzkurs:.4f}, Kosten eingerechnet)"
    if f.hinweis:
        text += f"; {f.hinweis}"
    l.log(f.tag, "ausfuehrung", text, o.zuordnung, isin=o.isin, order=o.id, grund=o.grund, grund_text=o.grund_text, stueck=f.stueck,
          kurs=f.kurs, referenzkurs=f.referenzkurs, betrag_eur=round(f.betrag_eur, 2), gebuehr_eur=f.gebuehr_eur, regel=o.regel)
    if o.status == "teilweise" and o.richtung == "kauf":
        o.status = "teilweise"  # Rest verfällt – kein Nachkauf zu späterem Kurs


def _abschluss(l: _Lauf, o: SimOrder, status: str, grund: str, day: int) -> None:
    o.status = status
    o.reserviert_eur = 0.0
    o.begruendung = dict(o.begruendung, abschluss=grund)
    if o.stufen:
        key = f"{o.zuordnung}|{o.isin}"
        pos = l.z.positionen.get(key)
        if pos is not None:
            st = gewinnziel.Stufenzustand.from_dict(pos.gm, pos.urspruenglich)
            for stage in o.stufen:
                st.offen.pop(stage, None)
            pos.gm = st.as_dict()
    l.log(day, "order", f"Order {status}: {grund}", o.zuordnung, isin=o.isin, order=o.id, richtung=o.richtung)


def _neu_einplanen(l: _Lauf, o: SimOrder, day: int, grund: str) -> None:
    s = l.series(o.isin)
    nxt = None
    if s is not None:
        later = s.days[s.days > day]
        nxt = int(later[0]) if len(later) else None
    o.sitzung = nxt if nxt is not None else day + 1
    if nxt is None:
        # nächste Kerze noch unbekannt: Sitzung auf den Folgetag setzen; der nächste Lauf prüft erneut
        o.sitzung = None
        o.preispunkt = o.preispunkt
    o.begruendung = dict(o.begruendung, neu_eingeplant=grund)
    l.log(day, "order", f"Verkauf neu eingeplant: {grund}", o.zuordnung, isin=o.isin, order=o.id)


def _verfallen(l: _Lauf, day: int) -> None:
    """Käufe, deren Sitzung vorbei ist, ohne dass eine Kerze kam, verfallen; Verkäufe ohne Sitzung werden neu eingeplant."""
    for o in l.z.offene_orders():
        if o.sitzung is None and o.richtung == "verkauf":
            s = l.series(o.isin)
            if s is not None and s.index_of(day) is not None and day > o.datentag:
                o.sitzung = day
                o.preispunkt = "close"
                _orders(l, day, "close")
        elif o.sitzung is not None and o.sitzung < day and o.status == "offen":
            if o.richtung == "kauf":
                _abschluss(l, o, "verfallen", "Ausführungssitzung ohne Kurs vergangen", day)
            else:
                _neu_einplanen(l, o, day, "Ausführungssitzung ohne Kurs vergangen")


def _stops(l: _Lauf, day: int) -> None:
    book = l.z.buch()
    for key, pos in sorted(list(l.z.positionen.items())):
        if pos.stop is None or not is_active_owner(pos.zuordnung):
            continue
        s = l.series(pos.isin)
        if s is None:
            continue
        k = s.index_of(day)
        if k is None or day <= pos.eroeffnet and _gekauft_zum_schluss(l, pos, day):
            continue  # ein am Schluss gekaufter Bestand hat am Kauftag noch keinen wirksamen Stop
        qty = book.qty(pos.isin, pos.zuordnung)
        if qty < 1:
            continue
        if any(o.isin == pos.isin and o.zuordnung == pos.zuordnung and o.richtung == "verkauf" and o.status == "offen" and o.grund == "stop" for o in l.z.orders):
            continue
        hit = stop_pruefen(pos.stop, s, k, l.u.markt, l.cfg, qty=qty, turnover_eur=l.u.umsatz_eur(pos.isin))
        if hit is None:
            continue
        ok, why = check_sell(pos.zuordnung, qty, hit.stueck, reason="stop")
        if not ok:
            l.log(day, "stop", f"Stop nicht ausgeführt: {why}", pos.zuordnung, isin=pos.isin)
            continue
        order = l.new_order(zuordnung=pos.zuordnung, isin=pos.isin, richtung="verkauf", stueck=hit.stueck, grund="stop",
                            profil="STOP", datentag=day, sitzung=day, preispunkt="stop", frueheste=None, ablauf=None, schutz=True,
                            regel=pos.regel, grund_text=f"Stop {pos.stop:.4f} {s.currency}")
        fill = Fill(hit.stueck, hit.referenzkurs, hit.kurs, hit.fx_eur, hit.betrag_eur, hit.gebuehr_eur, hit.kosten, day,
                    "Kurslücke: Eröffnung unter dem Stop" if hit.luecke else ("nur Schlusskurs bekannt" if hit.nur_schluss else None))
        _buchen(l, order, fill, "aktiv")


def _gekauft_zum_schluss(l: _Lauf, pos: Position, day: int) -> bool:
    return any(o.isin == pos.isin and o.zuordnung == pos.zuordnung and o.richtung == "kauf" and o.sitzung == day and o.preispunkt == "close"
               for o in l.z.orders)


def _bewerten(l: _Lauf, day: int) -> None:
    book = l.z.buch()
    val = value(book, l.u.markt, day)
    flows = sum(a for (t, pot, a) in book.flows if t == day and pot == "aktiv")
    transitions = l.z.verlust.update(day, val.active_eur, flows) if (l.d.strategien) else []
    for t in transitions:
        l.log(day, "verlustgrenze", f"Verluststufe {t['von']} → {t['nach']} (Rückgang {t['rueckgang'] * 100:.1f} %, Tag {t['tagesrendite'] * 100:.1f} %)", uebergang=t)
    rec = {
        "tag": day, "datum": _datum(day), "gesamt_eur": round(val.total_eur, 2), "kern_eur": round(val.core_eur, 2),
        "aktiv_eur": round(val.active_eur, 2), "guthaben_eur": round(val.cash_eur, 2), "einzahlungen_eur": round(book.deposits_eur, 2),
        "gebuehren_eur": round(book.fees_eur, 2), "vollstaendig": val.complete, "fehlend": list(val.missing), "stufe": l.z.verlust.stage,
    }
    if l.z.werte and l.z.werte[-1]["tag"] == day:
        l.z.werte[-1] = rec
    else:
        l.z.werte.append(rec)


def _risikostufe(l: _Lauf) -> None:
    if l.z.verlust.stage != "schliessen":
        return
    book = l.z.buch()
    for key, pos in sorted(l.z.positionen.items()):
        if not is_active_owner(pos.zuordnung):
            continue
        qty = book.qty(pos.isin, pos.zuordnung)
        if qty < 1 or _offener_verkauf(l, pos):
            continue
        _verkaufsorder(l, pos, int(qty), "risiko:schliessen", "Verlustgrenze: geordnete Schließung aktiver Positionen", schutz=True)


def _offener_verkauf(l: _Lauf, pos: Position) -> bool:
    return any(o.isin == pos.isin and o.zuordnung == pos.zuordnung and o.richtung == "verkauf" and o.status == "offen" for o in l.z.orders)


def _verkaufsorder(l: _Lauf, pos: Position, qty: int, grund: str, text: str, *, schutz: bool = False, stufen: tuple = (), details: dict | None = None) -> SimOrder | None:
    strategy = next((s for s in l.d.strategien if s.zuordnung == pos.zuordnung), None)
    profil = strategy.regel["profil"] if strategy else l.cfg.depot.ausfuehrungsprofil
    timing = l.plan(pos.isin, profil)
    if timing is None or not timing.simulatable:
        l.log(l.u.tag, "order", f"Verkauf nicht planbar: {timing.reason if timing else 'keine Kursreihe'}", pos.zuordnung, isin=pos.isin)
        return None
    return l.new_order(zuordnung=pos.zuordnung, isin=pos.isin, richtung="verkauf", stueck=int(qty), grund=grund, profil=profil,
                       datentag=l.u.tag, sitzung=timing.session_day, preispunkt=timing.price_point, frueheste=_iso(timing.earliest),
                       ablauf=_iso(timing.expires), schutz=schutz, regel=pos.regel, stufen=tuple(stufen), grund_text=text,
                       begruendung={"zeit": timing.as_dict(), **(details or {})})


def _taeglich(l: _Lauf) -> None:
    """Gewinnmitnahmen (Tagesschluss) und Trailing-Stops für alle aktiven Positionen."""
    book = l.z.buch()
    D = l.u.tag
    for key, pos in sorted(list(l.z.positionen.items())):
        if not is_active_owner(pos.zuordnung):
            continue
        strategy = next((s for s in l.d.strategien if s.zuordnung == pos.zuordnung), None)
        s = l.series(pos.isin)
        if s is None or strategy is None:
            continue
        k = s.upto(D)
        if k < 0:
            continue
        traded = s.unit_factor * s.split_factor_after(int(s.days[k]))  # wie damals gehandelt
        close = float(s.close[k]) * traded
        stop_cfg = strategy.regel.get("stop") or {}
        trailing = stop_cfg.get("trailing")
        pos.hoechster = max(pos.hoechster or close, close)
        if trailing:
            if trailing["art"] == "atr":
                atr = _atr_last(s, k, int(trailing.get("sitzungen", 14))) * traded
                level = pos.hoechster - float(trailing["faktor"]) * atr if math.isfinite(atr) else None
            else:
                level = pos.hoechster * (1.0 - float(trailing["wert"]) / 100.0)
            if level is not None and level > 0 and (pos.stop is None or level > pos.stop):
                old = pos.stop
                pos.stop = level  # nie nach unten (Abschnitt 9)
                l.log(D, "stop", f"Trailing-Stop nachgezogen auf {level:.4f} {s.currency}", pos.zuordnung, isin=pos.isin, alt=old, neu=level)
        gm = (strategy.regel.get("verkauf") or {}).get("gewinnmitnahme")
        if not gm or _offener_verkauf(l, pos):
            continue
        held = book.qty(pos.isin, pos.zuordnung)
        mins = int(strategy.regel["optionen"].get("mindesthaltedauer_sitzungen", 0))
        if _haltedauer(pos, D) < mins:
            continue
        cost = book.owner_cost.get(pos.isin, {}).get(pos.zuordnung)
        price_eur = l.close_eur(pos.isin, D)
        turnover = l.u.umsatz_eur(pos.isin)
        factor = sell_price_factor(l.cfg, s.currency, turnover, strategy.regel["profil"] == "FOLGETAG-SCHLUSS")
        avg_local = _avg_entry_local(l, pos)
        gewinn = gewinnziel.gewinn_fuer_regel(gm, qty=held, cost_eur=cost, price_eur=price_eur, avg_entry_local=avg_local, close_local=close,
                                             sell_price_factor=factor, fee_eur=l.cfg.handelskosten.ordergebuehr_eur)
        st = gewinnziel.Stufenzustand.from_dict(pos.gm, pos.urspruenglich)
        due = gewinnziel.faellig(gm, st, held, gewinn)
        if due is None:
            continue
        if due.stueck < 1:
            for i in due.uebersprungen:
                if i not in st.erledigt:
                    st.erledigt.append(i)
                    st.uebersprungen.append(i)
            pos.gm = st.as_dict()
            l.log(D, "gewinnmitnahme", due.grund, pos.zuordnung, isin=pos.isin)
            continue
        ok, why = check_sell(pos.zuordnung, held, due.stueck, reason="gewinnmitnahme")
        if not ok:
            l.log(D, "gewinnmitnahme", f"Gewinnmitnahme nicht möglich: {why}", pos.zuordnung, isin=pos.isin)
            continue
        order = _verkaufsorder(l, pos, due.stueck, "gewinnmitnahme", due.grund, stufen=due.stufen,
                               details={"gewinn_pct": round(gewinn, 4) if gewinn is not None else None, "basis": gm.get("basis", "nach_kosten")})
        if order is not None:
            for i in due.uebersprungen:
                if i not in st.erledigt:
                    st.erledigt.append(i)
                    st.uebersprungen.append(i)
            for stage in due.stufen:
                st.offen[stage] = order.id
            pos.gm = st.as_dict()
            l.log(D, "gewinnmitnahme", due.grund + f" – Verkauf von {due.stueck} Stück beauftragt", pos.zuordnung, isin=pos.isin, order=order.id)


def _avg_entry_local(l: _Lauf, pos: Position) -> float | None:
    """Ø Einstandskurs der Position in Notierungswährung (Kurse der Käufe, splitbereinigt über die Split-Ereignisse)."""
    qty = 0.0
    total = 0.0
    for e in l.z.events:
        if e.isin != pos.isin or e.nutzlast.get("zuordnung") != pos.zuordnung or e.tag < pos.eroeffnet:
            continue
        if e.typ == "kauf" and e.stueck:
            ref = e.nutzlast.get("referenzkurs") or e.kurs
            qty += e.stueck
            total += e.stueck * float(ref)
        elif e.typ == "split":
            f = float(e.nutzlast.get("faktor", 1.0))
            qty *= f
        elif e.typ == "verkauf" and e.stueck and qty > 0:
            share = min(1.0, e.stueck / qty)
            total *= 1.0 - share
            qty -= e.stueck
    return total / qty if qty > 1e-9 else None


def _haltedauer(pos: Position, day: int) -> int:
    return int(np.busday_count(np.datetime64(day_to_date(pos.eroeffnet)), np.datetime64(day_to_date(day))))


def _sperre_setzen(l: _Lauf, zuordnung: str, isin: str, day: int) -> None:
    strategy = next((s for s in l.d.strategien if s.zuordnung == zuordnung), None)
    if strategy is None:
        return
    we = strategy.regel["verkauf"].get("wiedereinstieg") or {"art": "neues_signal"}
    l.z.sperren[f"{zuordnung}|{isin}"] = {"art": we["art"], "seit": int(day), "pause": int(we.get("pause_sitzungen", 0)), "neues_signal_gesehen": False}


def _gesperrt(l: _Lauf, zuordnung: str, isin: str, selected_before: set[str]) -> str | None:
    key = f"{zuordnung}|{isin}"
    lock = l.z.sperren.get(key)
    if lock is None:
        return None
    D = l.u.tag
    if lock["art"] == "pause":
        passed = int(np.busday_count(np.datetime64(day_to_date(lock["seit"])), np.datetime64(day_to_date(D))))
        if passed < lock["pause"]:
            return f"Wiedereinstiegspause ({passed} von {lock['pause']} Sitzungen)"
        del l.z.sperren[key]
        return None
    if lock["art"] == "naechste_umschichtung":
        last = l.z.entschieden.get(zuordnung)
        if last is not None and last <= lock["seit"]:
            return "Wiedereinstieg erst zur nächsten regulären Umschichtung"
        del l.z.sperren[key]
        return None
    # neues Signal: erst nachdem die Aktie bei einer Entscheidung nach dem Verkauf nicht ausgewählt war
    if not lock.get("neues_signal_gesehen"):
        if isin not in selected_before or l.z.entschieden.get(zuordnung, -1) <= lock["seit"]:
            return "Wiedereinstieg erst bei einem neuen Signal (gleiches unverändertes Signal kauft nicht erneut)"
    del l.z.sperren[key]
    return None


def _faellig(l: _Lauf, s: StrategieDef) -> bool:
    plan = s.regel.get("zeitplan") or {"intervall": "woechentlich", "wochentag": 4}
    if s.zuordnung not in l.z.entschieden:
        return True  # erste Entscheidung nach dem Start
    if plan["intervall"] == "taeglich":
        return True
    D = l.u.tag
    last = l.z.entschieden[s.zuordnung]
    if zeitregel.weekday_of(D) == plan.get("wochentag", 4):
        return True
    # Wochentag ohne Daten (Feiertag): nachholen, wenn seit der letzten Entscheidung ein solcher Wochentag vergangen ist
    for day in range(last + 1, D):
        if zeitregel.weekday_of(day) == plan.get("wochentag", 4):
            return True
    return False


def _depotwerte(l: _Lauf, s: StrategieDef, ctx: Kontext) -> dict[str, dict]:
    book = l.z.buch()
    D = l.u.tag
    val = value(book, l.u.markt, D)
    total = max(1e-9, val.total_eur)
    out: dict[str, dict] = {}
    for key, pos in l.z.positionen.items():
        if pos.zuordnung != s.zuordnung:
            continue
        held = book.qty(pos.isin, pos.zuordnung)
        if held <= 0:
            continue
        ser = l.series(pos.isin)
        price_eur = val.prices_eur.get(pos.isin)
        cost = book.owner_cost.get(pos.isin, {}).get(pos.zuordnung)
        close_local = None
        if ser is not None:
            k = ser.upto(D)
            close_local = float(ser.close[k]) * ser.unit_factor * ser.split_factor_after(int(ser.days[k])) if k >= 0 else None
        factor = sell_price_factor(l.cfg, ser.currency if ser else "EUR", l.u.umsatz_eur(pos.isin), s.regel["profil"] == "FOLGETAG-SCHLUSS")
        net = gewinnziel.gewinn_nach_kosten_pct(held, cost, price_eur, sell_price_factor=factor, fee_eur=l.cfg.handelskosten.ordergebuehr_eur)
        gross = gewinnziel.kursgewinn_pct(_avg_entry_local(l, pos), close_local)
        out[pos.isin] = {
            "stueck": held, "gewinn_netto_pct": net, "kursgewinn_pct": gross, "haltedauer": _haltedauer(pos, D),
            "gewicht_pct": 100.0 * (price_eur or 0.0) * held / total if price_eur else None,
            "stopabstand_pct": 100.0 * (close_local / pos.stop - 1.0) if pos.stop and close_local else None,
        }
    return out


def _entscheiden(l: _Lauf, s: StrategieDef) -> None:
    D = l.u.tag
    regel = s.regel
    rid = f"{regel['id']}@{regel['version']}"
    if not _faellig(l, s):
        return
    base = l.u.kontext()
    ctx = Kontext(tag=base.tag, isins=base.isins, method=base.method, comp=base.comp, markt=base.markt, cfg=base.cfg, stamm=base.stamm,
                  fakten=base.fakten, depot=_depotwerte(l, s, base), vorher=base.vorher, modus=base.modus, _cache=base._cache, _index=base._index)
    # Depotwerte gehören nur zu dieser Strategie: eigener Zwischenspeicher; alles andere teilen die Depots eines Tages
    ctx._cache = {k: v for k, v in base._cache.items() if not _depotabhaengig(k)}
    try:
        auswahl = auswertung.auswaehlen(ctx, l.u.eintraege, regel, l.u.archiv, sektor_von=lambda isin: (l.u.stamm(isin) or {}).get("branche"))
    except Exception as exc:  # eine fehlerhafte Regel stoppt nur diese Regel, nie den Lauf oder Schutzverkäufe
        l.log(D, "entscheidung", f"Regel {rid} nicht auswertbar: {type(exc).__name__}: {exc}", s.zuordnung, regel=rid)
        l.z.entschieden[s.zuordnung] = D
        return
    before = set(l.z.letzte_auswahl.get(s.zuordnung, []))
    for key, lock in l.z.sperren.items():
        z_, isin = key.split("|", 1)
        if z_ == s.zuordnung and isin not in auswahl.ausgewaehlt and D > lock["seit"]:
            lock["neues_signal_gesehen"] = True
    book = l.z.buch()
    held = {pos.isin: ctx.depot.get(pos.isin, {}) for pos in l.z.positionen.values() if pos.zuordnung == s.zuordnung and book.qty(pos.isin, pos.zuordnung) >= 1}
    exits = auswertung.ausstiege(ctx, l.u.eintraege, regel, auswahl, held)
    for k, v in ctx._cache.items():
        if not _depotabhaengig(k):
            base._cache.setdefault(k, v)
    sells = []
    stage = l.z.verlust.stage
    for isin, ex in exits.items():
        if not ex.verkaufen:
            continue
        pos = l.z.positionen.get(f"{s.zuordnung}|{isin}")
        if pos is None or _offener_verkauf(l, pos):
            continue
        qty = int(book.qty(isin, s.zuordnung))
        ok, why = check_sell(s.zuordnung, qty, qty, reason=ex.art)
        if not ok:
            continue
        order = _verkaufsorder(l, pos, qty, f"regel:{ex.art}", ex.grund, details={"bedingungen": ex.details})
        if order is not None:
            sells.append({"isin": isin, "stueck": qty, "grund": ex.grund, "order": order.id})
    # Käufe
    buys, rejected = [], []
    kauf = regel["kauf"]["ausloeser"]
    targets = [i for i in auswahl.ausgewaehlt if i not in held]
    if kauf in ("neues_signal", "eintritt_top_n"):
        new_only = [i for i in targets if i not in before]
        for i in targets:
            if i not in new_only:
                rejected.append({"isin": i, "grund": "kein neues Signal (war schon bei der letzten Entscheidung ausgewählt)"})
        targets = new_only
    exp, val = l.exposure(D)
    n = regel["auswahl"]["anzahl"]
    budget = exp.strategy_budget_eur.get(s.zuordnung, 0.0)
    weights = _kapitalgewichte(l, regel, auswahl.ausgewaehlt, ctx)
    for isin in targets:
        reason = _gesperrt(l, s.zuordnung, isin, before)
        if reason:
            rejected.append({"isin": isin, "grund": reason})
            continue
        if stage in ("nur_risikosenkend", "schliessen"):
            rejected.append({"isin": isin, "grund": l.z.verlust.blocks_new_buys()})
            continue
        if any(o.isin == isin and o.zuordnung == s.zuordnung and o.status == "offen" for o in l.z.orders):
            rejected.append({"isin": isin, "grund": "Order bereits offen"})
            continue
        ser = l.series(isin)
        st = l.u.stamm(isin) or {}
        if ser is None:
            rejected.append({"isin": isin, "grund": "keine Kursreihe"})
            continue
        k = ser.upto(D)
        close_eur = l.close_eur(isin, D)
        if k < 0 or close_eur is None:
            rejected.append({"isin": isin, "grund": "kein Kurs oder Wechselkurs"})
            continue
        timing = l.plan(isin, regel["profil"])
        if timing is None or not timing.simulatable:
            rejected.append({"isin": isin, "grund": f"nicht ausführbar: {timing.reason if timing else 'keine Sitzung'}"})
            continue
        turnover = l.u.umsatz_eur(isin)
        entry_eur = close_eur * buy_price_factor(l.cfg, ser.currency, turnover, regel["profil"] == "FOLGETAG-SCHLUSS")
        stop_cfg = regel["stop"]["initial"]
        traded = ser.unit_factor * ser.split_factor_after(int(ser.days[k]))  # wie damals gehandelt
        atr_local = _atr_last(ser, k, int(stop_cfg.get("sitzungen", 14))) * traded
        close_local = float(ser.close[k]) * traded
        if stop_cfg["art"] == "atr":
            if not math.isfinite(atr_local) or atr_local <= 0:
                rejected.append({"isin": isin, "grund": "ATR nicht bestimmbar – kein Initialstop, kein Kauf"})
                continue
            distance_local = float(stop_cfg["faktor"]) * atr_local
            stop_plan = {"art": "atr", "abstand": distance_local, "atr": atr_local}
        else:
            distance_local = close_local * float(stop_cfg["wert"]) / 100.0
            stop_plan = {"art": "prozent", "wert": float(stop_cfg["wert"])}
        stop_eur = entry_eur - distance_local * (close_eur / close_local)
        target_eur = budget * weights.get(isin, 1.0 / max(1, n))
        age = int(np.busday_count(np.datetime64(day_to_date(int(ser.days[k]))), np.datetime64(day_to_date(D))))
        req = BuyRequest(isin=isin, strategy=s.zuordnung, instrument_type=st.get("typ", "aktie"), sector=st.get("branche"), entry_eur=entry_eur,
                         fee_eur=l.cfg.handelskosten.ordergebuehr_eur, stop_eur=stop_eur, turnover_eur=turnover, price_now_eur=close_eur,
                         managed_average_cost_eur=None, data_age_sessions=age, deviation=None, synthetic=l.u.synthetisch)
        decision = size_buy(l.cfg, exp, req, l.z.verlust, paused=l.z.kaeufe_pausiert)
        if not decision.allowed:
            rejected.append({"isin": isin, "grund": decision.reason, "grenzen": decision.limits})
            continue
        # Zielbetrag inklusive Reservierungspuffer und Gebühr: Summe der Reservierungen bleibt im Budget (kein Überbuchen)
        fee = l.cfg.handelskosten.ordergebuehr_eur
        qty = min(decision.qty, int(math.floor((target_eur - fee) / (entry_eur * (1.0 + RESERVE_PUFFER)) + 1e-9)))
        if qty < 1:
            rejected.append({"isin": isin, "grund": f"Zielbetrag {target_eur:.0f} EUR reicht nicht für ein Stück", "grenzen": decision.limits})
            continue
        minimum = float(regel["optionen"].get("mindestorderwert_eur", 0))
        if qty * entry_eur < minimum:
            rejected.append({"isin": isin, "grund": f"unter dem Mindestorderwert {minimum:.0f} EUR"})
            continue
        reserve = qty * entry_eur * (1.0 + RESERVE_PUFFER) + l.cfg.handelskosten.ordergebuehr_eur
        order = l.new_order(zuordnung=s.zuordnung, isin=isin, richtung="kauf", stueck=int(qty), grund="regel:auswahl", profil=regel["profil"],
                            datentag=D, sitzung=timing.session_day, preispunkt=timing.price_point, frueheste=_iso(timing.earliest),
                            ablauf=_iso(timing.expires), reserviert_eur=reserve, regel=rid, stop_plan=stop_plan,
                            grund_text=f"Platz {auswahl.platz_von(isin)} der Regel „{regel['name']}“",
                            begruendung={"zeit": timing.as_dict(), "risiko": decision.as_dict(), "zielbetrag_eur": round(target_eur, 2),
                                         "geschaetzter_kurs_eur": round(entry_eur, 6), "stop_eur": round(stop_eur, 6)})
        # Reservierung sofort wirksam für die folgenden Käufe dieser Entscheidung
        exp.free_cash_eur -= reserve
        exp.active_eur += reserve
        exp.by_isin_eur[isin] = exp.by_isin_eur.get(isin, 0.0) + reserve
        exp.by_strategy_eur[s.zuordnung] = exp.by_strategy_eur.get(s.zuordnung, 0.0) + reserve
        if st.get("typ", "aktie") == "aktie":
            exp.single_stocks.add(isin)
        sec = st.get("branche") or l.cfg.risiko.unbekannte_branche
        exp.sector_total_eur[sec] = exp.sector_total_eur.get(sec, 0.0) + reserve
        exp.sector_active_eur[sec] = exp.sector_active_eur.get(sec, 0.0) + reserve
        buys.append({"isin": isin, "stueck": int(qty), "order": order.id, "bestimmend": decision.binding})
    l.z.letzte_auswahl[s.zuordnung] = list(auswahl.ausgewaehlt)
    l.z.entschieden[s.zuordnung] = D
    summary = auswahl.as_dict()
    if not buys and not sells:
        why = "keine qualifizierten Kandidaten" if not auswahl.ausgewaehlt else ("Positionen unverändert gehalten" if not rejected else "Käufe durch Regeln/Risiko abgelehnt")
        text = f"Nicht gehandelt: {why}"
    else:
        text = f"{len(buys)} Kauf- und {len(sells)} Verkaufsorders beauftragt"
    l.log(D, "entscheidung", text, s.zuordnung, regel=rid, auswahl=summary, kaeufe=buys, verkaeufe=sells, abgelehnt=rejected,
          ausstiege={i: {"verkaufen": e.verkaufen, "grund": e.grund, "art": e.art} for i, e in exits.items()},
          verluststufe=stage, budget_eur=round(budget, 2))


DEPOT_KENNZAHLEN = ("gehalten", "position_gewinn_netto", "position_kursgewinn", "haltedauer", "positionsgewicht", "stopabstand")


def _depotabhaengig(key) -> bool:
    return isinstance(key, tuple) and len(key) > 1 and key[0] == "wert" and key[1] in DEPOT_KENNZAHLEN


def _kapitalgewichte(l: _Lauf, regel: dict, selected: list[str], ctx: Kontext) -> dict[str, float]:
    n = max(1, regel["auswahl"]["anzahl"])
    art = regel["kapital"]["art"]
    if art == "ziel":
        return {isin: regel["kapital"]["ziele_pct"][i] / 100.0 for i, isin in enumerate(selected) if i < len(regel["kapital"]["ziele_pct"])}
    if art == "risiko":
        inv = {}
        for isin in selected:
            ser = l.series(isin)
            if ser is None:
                continue
            k = ser.upto(l.u.tag)
            a = _atr_last(ser, k, 14)
            c = float(ser.close[k]) if k >= 0 else math.nan
            if math.isfinite(a) and a > 0 and c > 0:
                inv[isin] = c / a
        total = sum(inv.values())
        if total <= 0:
            return {isin: 1.0 / n for isin in selected}
        share = len(inv) / n  # zu wenige Titel: freier Rest bleibt Guthaben (kein Auffüllen mit ungeeigneten Titeln)
        return {isin: share * v / total for isin, v in inv.items()}
    return {isin: 1.0 / n for isin in selected}


def _kern(l: _Lauf) -> None:
    """Robo-Kern (S4): Zielaufteilung Welt-/Geldmarkt-ETF; zuerst Guthaben anlegen, Umschichtung ab der Schwelle."""
    kern = l.d.kern
    D = l.u.tag
    book = l.z.buch()
    open_core = [o for o in l.z.offene_orders() if o.zuordnung == "kern"]
    if open_core:
        return
    prices = {isin: l.close_eur(isin, D) for isin in kern.ziele}
    if any(p is None for p in prices.values()):
        missing = [i for i, p in prices.items() if p is None]
        l.log(D, "kern", f"Kern nicht bewertbar – Kurs fehlt für {', '.join(missing)}; keine Umschichtung", "kern")
        return
    held = {isin: book.qty(isin, "kern") for isin in kern.ziele}
    values = {isin: held[isin] * prices[isin] for isin in kern.ziele}
    cash = book.pots.get("kern", 0.0)
    core_total = cash + sum(values.values())
    if core_total <= KERN_MINDESTORDER_EUR:
        return
    weights = {isin: values[isin] / core_total for isin in kern.ziele}
    deviation = max(abs(weights[i] - kern.ziele[i]) * 100.0 for i in kern.ziele)
    orders = []
    if kern.rebalancing and deviation > kern.schwelle_pp:
        for isin, target in kern.ziele.items():
            diff = target * core_total - values[isin]
            if diff < -KERN_MINDESTORDER_EUR:
                qty = int(math.floor(-diff / prices[isin]))
                if qty >= 1:
                    orders.append(("verkauf", isin, qty, f"Rebalancing: Abweichung {deviation:.1f} pp > {kern.schwelle_pp:g} pp"))
        cash_after = cash + sum(q * prices[i] for (r, i, q, _) in orders if r == "verkauf")
    else:
        cash_after = cash
    # Kaufen: Untergewichte zuerst aus Guthaben (inkl. erwarteter Verkaufserlöse)
    budget = cash_after - len(kern.ziele) * l.cfg.handelskosten.ordergebuehr_eur
    for isin, target in sorted(kern.ziele.items(), key=lambda kv: (weights[kv[0]] - kv[1])):
        want = target * core_total - values[isin]
        if not kern.rebalancing:
            want = budget * target  # Kaufen und Halten: neue Mittel nach Zielgewicht anlegen
        ser = l.series(isin)
        if ser is None or want < KERN_MINDESTORDER_EUR or budget < KERN_MINDESTORDER_EUR:
            continue
        entry = prices[isin] * buy_price_factor(l.cfg, ser.currency, l.u.umsatz_eur(isin), l.cfg.depot.ausfuehrungsprofil == "FOLGETAG-SCHLUSS")
        qty = int(math.floor(min(want, budget) / entry))
        if qty >= 1:
            invested = sum(values.values()) > 0
            label = "Rebalancing" if (invested and deviation > kern.schwelle_pp and kern.rebalancing) else "Guthaben nach Zielaufteilung anlegen"
            orders.append(("kauf", isin, qty, label))
            budget -= qty * entry
    exp = None
    for richtung, isin, qty, why in orders:
        timing = l.plan(isin, l.cfg.depot.ausfuehrungsprofil)
        if timing is None or not timing.simulatable:
            l.log(D, "kern", f"Kern-Order nicht planbar ({isin})", "kern")
            continue
        entry = prices[isin]
        if richtung == "kauf":
            # Auch Kern-Käufe laufen durch den zentralen Risiko-Manager (ohne Stop- und Einzelaktiengrenzen, Abschnitt 15)
            if exp is None:
                exp, _ = l.exposure(D)
                exp.free_cash_eur = book.pots.get("kern", 0.0) - sum(o.reserviert_eur for o in l.z.offene_orders() if o.zuordnung == "kern" and o.richtung == "kauf")
            ser = l.series(isin)
            st = l.u.stamm(isin) or {}
            entry_eur = entry * buy_price_factor(l.cfg, ser.currency if ser else "EUR", l.u.umsatz_eur(isin), l.cfg.depot.ausfuehrungsprofil == "FOLGETAG-SCHLUSS")
            req = BuyRequest(isin=isin, strategy="kern", instrument_type=st.get("typ", "etf"), sector=st.get("branche"), entry_eur=entry_eur,
                             fee_eur=l.cfg.handelskosten.ordergebuehr_eur, stop_eur=None, turnover_eur=l.u.umsatz_eur(isin), price_now_eur=entry,
                             managed_average_cost_eur=None, data_age_sessions=0, deviation=None, core=True, synthetic=l.u.synthetisch)
            decision = size_buy(l.cfg, exp, req, l.z.verlust, paused=l.z.kaeufe_pausiert)
            if not decision.allowed:
                l.log(D, "kern", f"Kern-Kauf abgelehnt: {decision.reason}", "kern", isin=isin, grenzen=decision.limits)
                continue
            qty = min(qty, decision.qty)
            exp.free_cash_eur -= qty * entry_eur * (1.0 + RESERVE_PUFFER) + l.cfg.handelskosten.ordergebuehr_eur
        reserve = qty * entry * (1.0 + RESERVE_PUFFER) + l.cfg.handelskosten.ordergebuehr_eur if richtung == "kauf" else 0.0
        o = l.new_order(zuordnung="kern", isin=isin, richtung=richtung, stueck=qty, grund="kern:rebalancing" if "Rebalancing" in why else "kern:anlegen",
                        profil=l.cfg.depot.ausfuehrungsprofil, datentag=D, sitzung=timing.session_day, preispunkt=timing.price_point,
                        frueheste=_iso(timing.earliest), ablauf=_iso(timing.expires), reserviert_eur=reserve, grund_text=why,
                        begruendung={"zeit": timing.as_dict(), "ziel": kern.ziele, "ist": {k: round(v, 6) for k, v in weights.items()}})
        l.log(D, "kern", f"{'Kauf' if richtung == 'kauf' else 'Verkauf'} {qty} Stück beauftragt: {why}", "kern", isin=isin, order=o.id)
