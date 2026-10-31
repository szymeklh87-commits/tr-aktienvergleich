"""Depotstand aus dem unveränderlichen Ereignisjournal (Abschnitte 17, 19, 21).

Ein Depot ist die Folge seiner Ereignisse (``ap_ereignis``) – nichts wird überschrieben, Korrekturen sind eigene Ereignisse.
Daraus ergeben sich Guthaben (EUR), Bestände je ISIN mit Zuordnung (Strategie, ``kern`` für den ETF-Kern, ``extern`` für nicht
von AktienPilot verwaltete Bestände) und Anschaffungslose nach FIFO (für Steuermodell und Export). Unbekannte
Anschaffungskosten bleiben unbekannt (``None``) – sie werden nie mit 0 ersetzt.

Ereignistypen und ihre Wirkung:

==============  ===========================================================================================
einzahlung      Guthaben + Betrag
auszahlung      Guthaben − Betrag (Betrag als negative Zahl gespeichert)
kauf            Bestand + Stück für die Zuordnung, neues Los; Guthaben − (Kurswert + Gebühren) in EUR
verkauf         Bestand − Stück der Zuordnung, Lose nach FIFO; Guthaben + (Kurswert − Gebühren); realisiertes Ergebnis
gebuehr         Guthaben − Betrag
dividende/zins  Guthaben + Betrag (Ertrag)
steuer          Guthaben ± Betrag (Abzug negativ, Erstattung positiv)
split           Stückzahl aller Lose × Faktor (Kosten unverändert)
anfangsbestand  Bestand + Stück ohne Geldfluss; Kosten wie angegeben oder unbekannt
umbuchung       Zuordnung zwischen Kern, aktivem Teil und extern ändern (ohne Geldfluss)
korrektur       Ausgleichsbuchung zu einem früheren Ereignis (Guthaben- und Stückdifferenz, Verweis im Inhalt)
==============  ===========================================================================================
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

EPS = 1e-9
EVENT_TYPES = ("einzahlung", "auszahlung", "kauf", "verkauf", "gebuehr", "dividende", "zins", "steuer", "split",
               "anfangsbestand", "umbuchung", "korrektur")
OWNERS_FIXED = ("kern", "extern")


class BookingError(ValueError):
    """Ereignis passt nicht zum Depotstand (z. B. Verkauf ohne ausreichenden verwalteten Bestand)."""


@dataclass
class Event:
    id: str
    depot_id: str
    seq: int
    zeit: str
    tag: int
    typ: str
    isin: str | None = None
    stueck: float | None = None
    kurs: float | None = None
    waehrung: str | None = None
    fx_eur: float | None = None
    fx_quelle: str | None = None
    betrag_eur: float = 0.0
    gebuehren_eur: float = 0.0
    quelle: str = "system"
    order_id: str | None = None
    signal_id: str | None = None
    verwaltet: bool = True
    nutzlast: dict = field(default_factory=dict)

    @property
    def owner(self) -> str:
        """Zuordnung des Bestands: Strategie (z. B. „s1“), „kern“ oder „extern“."""
        owner = self.nutzlast.get("zuordnung")
        if owner:
            return str(owner)
        return "extern" if not self.verwaltet else "pilot"

    def as_row(self) -> dict:
        return {
            "id": self.id, "depot_id": self.depot_id, "seq": self.seq, "zeit": self.zeit, "tag": self.tag, "typ": self.typ,
            "isin": self.isin, "stueck": self.stueck, "kurs": self.kurs, "waehrung": self.waehrung, "fx_eur": self.fx_eur,
            "fx_quelle": self.fx_quelle, "betrag_eur": self.betrag_eur, "gebuehren_eur": self.gebuehren_eur, "quelle": self.quelle,
            "order_id": self.order_id, "signal_id": self.signal_id, "verwaltet": 1 if self.verwaltet else 0,
            "nutzlast_json": json.dumps(self.nutzlast, ensure_ascii=False, sort_keys=True),
        }

    @staticmethod
    def from_row(row) -> "Event":
        return Event(
            id=row["id"], depot_id=row["depot_id"], seq=int(row["seq"]), zeit=row["zeit"], tag=int(row["tag"]), typ=row["typ"],
            isin=row["isin"], stueck=row["stueck"], kurs=row["kurs"], waehrung=row["waehrung"], fx_eur=row["fx_eur"],
            fx_quelle=row["fx_quelle"], betrag_eur=float(row["betrag_eur"] or 0.0), gebuehren_eur=float(row["gebuehren_eur"] or 0.0),
            quelle=row["quelle"], order_id=row["order_id"], signal_id=row["signal_id"], verwaltet=bool(row["verwaltet"]),
            nutzlast=json.loads(row["nutzlast_json"] or "{}"),
        )


@dataclass
class Lot:
    isin: str
    qty: float
    cost_eur: float | None  # Anschaffungskosten des verbleibenden Loses (inkl. Kaufgebühren), None = unbekannt
    day: int | None  # Anschaffungstag, None = unbekannt
    event_id: str
    fund_type: str | None = None  # „Aktienfonds“ für Teilfreistellung, sonst None


@dataclass
class Realized:
    event_id: str
    isin: str
    day: int
    qty: float
    proceeds_eur: float
    cost_eur: float | None  # None, wenn ein verbrauchtes Los unbekannte Kosten hatte
    owner: str

    @property
    def gain_eur(self) -> float | None:
        return None if self.cost_eur is None else self.proceeds_eur - self.cost_eur


@dataclass
class Book:
    """Stand eines Depots nach allen bisher angewendeten Ereignissen."""

    depot_id: str
    cash_eur: float = 0.0
    lots: dict[str, list[Lot]] = field(default_factory=dict)
    holdings: dict[str, dict[str, float]] = field(default_factory=dict)  # ISIN → Zuordnung → Stück
    realized: list[Realized] = field(default_factory=list)
    fees_eur: float = 0.0
    income_eur: float = 0.0
    taxes_eur: float = 0.0
    deposits_eur: float = 0.0  # Summe Einzahlungen − Auszahlungen
    last_seq: int = 0
    applied: set[str] = field(default_factory=set)
    cash_known: bool = True  # False, solange kein Guthaben erfasst ist (Anfangsbestand ohne Guthaben)

    # ------------------------------------------------------------------ Abfragen

    def qty(self, isin: str, owner: str | None = None) -> float:
        per = self.holdings.get(isin, {})
        if owner is None:
            return sum(per.values())
        return per.get(owner, 0.0)

    def owners(self, isin: str) -> dict[str, float]:
        return {k: v for k, v in self.holdings.get(isin, {}).items() if abs(v) > EPS}

    def positions(self) -> dict[str, float]:
        return {isin: total for isin in self.holdings if (total := self.qty(isin)) > EPS}

    def cost_basis(self, isin: str) -> float | None:
        lots = self.lots.get(isin, [])
        if not lots:
            return 0.0
        if any(lot.cost_eur is None for lot in lots):
            return None
        return float(sum(lot.cost_eur for lot in lots))

    def average_cost_eur(self, isin: str) -> float | None:
        """Ø Einstand je Stück in EUR (für die Regel „kein Aufstocken verlustreicher Positionen“); None bei unbekannten Kosten."""
        basis = self.cost_basis(isin)
        total = sum(lot.qty for lot in self.lots.get(isin, []))
        if basis is None or total <= EPS:
            return None
        return basis / total

    # ------------------------------------------------------------------ Buchen

    def apply(self, event: Event) -> None:
        if event.id in self.applied:
            return  # Wiederholung: genau einmal gebucht
        if event.typ not in EVENT_TYPES:
            raise BookingError(f"Unbekannter Ereignistyp {event.typ!r}")
        handler = getattr(self, f"_apply_{event.typ}")
        handler(event)
        self.applied.add(event.id)
        self.last_seq = max(self.last_seq, int(event.seq))

    def _add_holding(self, isin: str, owner: str, qty: float) -> None:
        per = self.holdings.setdefault(isin, {})
        per[owner] = per.get(owner, 0.0) + qty
        if abs(per[owner]) < EPS:
            per[owner] = 0.0

    def _apply_einzahlung(self, e: Event) -> None:
        if e.betrag_eur < 0:
            raise BookingError("Einzahlung mit negativem Betrag")
        self.cash_eur += e.betrag_eur
        self.deposits_eur += e.betrag_eur

    def _apply_auszahlung(self, e: Event) -> None:
        if e.betrag_eur > 0:
            raise BookingError("Auszahlung mit positivem Betrag")
        self.cash_eur += e.betrag_eur
        self.deposits_eur += e.betrag_eur

    def _apply_gebuehr(self, e: Event) -> None:
        self.cash_eur += e.betrag_eur
        self.fees_eur += -e.betrag_eur

    def _apply_dividende(self, e: Event) -> None:
        self.cash_eur += e.betrag_eur
        self.income_eur += e.betrag_eur

    _apply_zins = _apply_dividende

    def _apply_steuer(self, e: Event) -> None:
        self.cash_eur += e.betrag_eur
        self.taxes_eur += -e.betrag_eur

    def _apply_kauf(self, e: Event) -> None:
        if not e.isin or not e.stueck or e.stueck <= 0:
            raise BookingError("Kauf ohne ISIN oder positive Stückzahl")
        self.cash_eur += e.betrag_eur
        self.fees_eur += e.gebuehren_eur
        cost = -e.betrag_eur  # Kurswert + Gebühren in EUR
        self.lots.setdefault(e.isin, []).append(Lot(e.isin, float(e.stueck), cost, e.tag, e.id, e.nutzlast.get("fondsart")))
        self._add_holding(e.isin, e.owner, float(e.stueck))

    def _consume_fifo(self, isin: str, qty: float) -> float | None:
        remaining = qty
        cost_total: float | None = 0.0
        lots = self.lots.get(isin, [])
        while remaining > EPS and lots:
            lot = lots[0]
            take = min(lot.qty, remaining)
            share = take / lot.qty
            if lot.cost_eur is None:
                cost_total = None
            elif cost_total is not None:
                cost_total += lot.cost_eur * share
            if lot.cost_eur is not None:
                lot.cost_eur -= lot.cost_eur * share
            lot.qty -= take
            remaining -= take
            if lot.qty <= EPS:
                lots.pop(0)
        if remaining > EPS:
            raise BookingError(f"{isin}: Verkauf über den gesamten Bestand hinaus ({remaining:g} Stück fehlen)")
        return cost_total

    def _apply_verkauf(self, e: Event) -> None:
        if not e.isin or not e.stueck or e.stueck <= 0:
            raise BookingError("Verkauf ohne ISIN oder positive Stückzahl")
        owner = e.owner
        held = self.qty(e.isin, owner)
        if held + EPS < e.stueck:
            raise BookingError(f"{e.isin}: Verkauf von {e.stueck:g} Stück für „{owner}“, verwaltet sind nur {held:g}")
        cost = self._consume_fifo(e.isin, float(e.stueck))
        self.cash_eur += e.betrag_eur
        self.fees_eur += e.gebuehren_eur
        self._add_holding(e.isin, owner, -float(e.stueck))
        self.realized.append(Realized(e.id, e.isin, e.tag, float(e.stueck), e.betrag_eur, cost, owner))

    def _apply_split(self, e: Event) -> None:
        factor = float(e.nutzlast.get("faktor", 0.0))
        if not e.isin or factor <= 0:
            raise BookingError("Split ohne ISIN oder positiven Faktor")
        for lot in self.lots.get(e.isin, []):
            lot.qty *= factor
        per = self.holdings.get(e.isin, {})
        for owner in list(per):
            per[owner] *= factor

    def _apply_anfangsbestand(self, e: Event) -> None:
        if e.isin is None:
            # Anfangsguthaben (ohne Wirkung auf Einzahlungen – es ist ein Bestand, keine Bewegung)
            self.cash_eur += e.betrag_eur
            return
        if not e.stueck or e.stueck <= 0:
            raise BookingError("Anfangsbestand ohne positive Stückzahl")
        cost = e.nutzlast.get("anschaffungskosten_eur")
        day = e.nutzlast.get("kauftag")
        self.lots.setdefault(e.isin, []).append(
            Lot(e.isin, float(e.stueck), None if cost is None else float(cost), None if day is None else int(day), e.id, e.nutzlast.get("fondsart"))
        )
        self._add_holding(e.isin, e.owner, float(e.stueck))

    def _apply_umbuchung(self, e: Event) -> None:
        if not e.isin or not e.stueck or e.stueck <= 0:
            raise BookingError("Umbuchung ohne ISIN oder positive Stückzahl")
        source = str(e.nutzlast.get("von"))
        target = str(e.nutzlast.get("nach"))
        if self.qty(e.isin, source) + EPS < e.stueck:
            raise BookingError(f"{e.isin}: Umbuchung von „{source}“ über den Bestand hinaus")
        self._add_holding(e.isin, source, -float(e.stueck))
        self._add_holding(e.isin, target, float(e.stueck))

    def _apply_korrektur(self, e: Event) -> None:
        delta_qty = float(e.nutzlast.get("stueck_differenz", 0.0))
        self.cash_eur += e.betrag_eur
        if e.isin and abs(delta_qty) > EPS:
            owner = e.owner
            if delta_qty > 0:
                self.lots.setdefault(e.isin, []).append(Lot(e.isin, delta_qty, e.nutzlast.get("kosten_differenz_eur"), e.tag, e.id))
            else:
                self._consume_fifo(e.isin, -delta_qty)
            self._add_holding(e.isin, owner, delta_qty)


def replay(depot_id: str, events: list[Event]) -> Book:
    """Depotstand aus allen Ereignissen in der Reihenfolge ihrer Nummer."""
    book = Book(depot_id)
    for event in sorted(events, key=lambda e: e.seq):
        book.apply(event)
    return book


@dataclass(frozen=True)
class Valuation:
    day: int
    cash_eur: float
    positions_eur: dict[str, float]  # ISIN → Wert (nur bekannte Kurse)
    missing: tuple[str, ...]  # ISINs ohne Kurs oder Wechselkurs – Gesamtwert ist dann ein Teilwert
    by_owner_eur: dict[str, float]

    @property
    def total_eur(self) -> float:
        return self.cash_eur + sum(self.positions_eur.values())

    @property
    def complete(self) -> bool:
        return not self.missing

    def owner_value(self, owners: tuple[str, ...]) -> float:
        return sum(v for k, v in self.by_owner_eur.items() if k in owners)


def value(book: Book, market, day: int) -> Valuation:
    """Bewertung zum letzten Schlusskurs bis ``day`` in EUR (EZB-Referenzkurs des Tages oder davor)."""
    positions: dict[str, float] = {}
    by_owner: dict[str, float] = {}
    missing: list[str] = []
    for isin, total in book.positions().items():
        last = market.last_close(isin, day)
        eur = None if last is None else market.price_eur(isin, last[0], day)
        if eur is None:
            missing.append(isin)
            continue
        positions[isin] = eur * total
        for owner, qty in book.owners(isin).items():
            by_owner[owner] = by_owner.get(owner, 0.0) + eur * qty
    return Valuation(day, book.cash_eur, positions, tuple(sorted(missing)), by_owner)
