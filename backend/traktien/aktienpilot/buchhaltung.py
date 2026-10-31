"""Depotstand aus dem unveränderlichen Ereignisjournal (Abschnitte 16, 17, 19, 21).

Ein Depot ist die Folge seiner Ereignisse (``ap_ereignis``) – nichts wird überschrieben, Korrekturen sind eigene Ereignisse.
Daraus ergeben sich:

* **Guthaben in Töpfen** (EUR): ``frei`` (nicht zugeteilt, z. B. neue Einzahlungen), ``kern`` (Robo-Kern) und ``aktiv`` (S1–S3
  bzw. die Strategie eines Vergleichsdepots). Die Summe ist das Guthaben des Depots. Umbuchungen zwischen Töpfen sind eigene
  Ereignisse – so lassen sich Verlustgrenzen des aktiven Teils bereinigt um Ein-/Auszahlungen und Umbuchungen messen.
* **Bestände** je ISIN und Zuordnung (Strategie wie ``s1``, ``kern`` für den ETF-Kern, ``extern`` für nicht von AktienPilot
  verwaltete Bestände) mit Einstand je Zuordnung (Durchschnitt, für Strategie-Ergebnis und „kein Aufstocken von Verlierern“).
* **Anschaffungslose** je ISIN nach FIFO (Steuermodell und Export, wie bei der depotweisen FIFO-Regel).

Unbekannte Anschaffungskosten bleiben unbekannt (``None``) – sie werden nie mit 0 ersetzt.

==============  ===========================================================================================
einzahlung      Topf (Standard ``frei``) + Betrag
auszahlung      Topf − Betrag (Betrag negativ gespeichert)
kauf            Bestand + Stück für die Zuordnung, neues Los; Topf − (Kurswert + Gebühren) in EUR
verkauf         Bestand − Stück der Zuordnung, Lose nach FIFO; Topf + (Kurswert − Gebühren); realisiertes Ergebnis
gebuehr         Topf − Betrag (Betrag negativ)
dividende/zins  Topf + Betrag (Ertrag)
steuer          Topf ± Betrag (Abzug negativ, Erstattung positiv)
split           Stückzahl aller Lose und Bestände × Faktor (Kosten unverändert)
anfangsbestand  Bestand + Stück ohne Geldfluss (Kosten wie angegeben oder unbekannt) bzw. Anfangsguthaben eines Topfs
umbuchung       Guthaben zwischen Töpfen (ohne ISIN) oder Bestand zwischen Zuordnungen (mit ISIN), ohne Geldfluss
korrektur       Ausgleichsbuchung zu einem früheren Ereignis (Guthaben- und Stückdifferenz, Verweis im Inhalt)
==============  ===========================================================================================
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

EPS = 1e-9
EVENT_TYPES = ("einzahlung", "auszahlung", "kauf", "verkauf", "gebuehr", "dividende", "zins", "steuer", "split",
               "anfangsbestand", "umbuchung", "korrektur")
POTS = ("frei", "kern", "aktiv")
CORE_OWNERS = ("kern",)
EXTERNAL_OWNERS = ("extern",)


class BookingError(ValueError):
    """Ereignis passt nicht zum Depotstand (z. B. Verkauf ohne ausreichenden verwalteten Bestand)."""


def pot_for_owner(owner: str) -> str:
    if owner in CORE_OWNERS:
        return "kern"
    if owner in EXTERNAL_OWNERS:
        return "frei"
    return "aktiv"


def is_active_owner(owner: str) -> bool:
    return owner not in CORE_OWNERS and owner not in EXTERNAL_OWNERS


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

    @property
    def pot(self) -> str:
        pot = self.nutzlast.get("topf")
        if pot:
            if pot not in POTS:
                raise BookingError(f"Unbekannter Topf {pot!r}")
            return str(pot)
        if self.typ in ("einzahlung", "auszahlung") or self.isin is None:
            return "frei"
        return pot_for_owner(self.owner)

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
    cost_eur: float | None  # FIFO-Kosten der verbrauchten Lose; None, wenn eines unbekannte Kosten hatte
    owner: str
    owner_cost_eur: float | None  # Einstand der Zuordnung (Durchschnitt) – Ergebnis der Strategie
    fund_type: str | None = None
    # verbrauchte Anschaffungslose nach FIFO: (Ereignis des Kaufs, Anschaffungstag oder None, Stück, Kosten in EUR oder None)
    lots: tuple[tuple[str, int | None, float, float | None], ...] = ()

    @property
    def gain_eur(self) -> float | None:
        return None if self.cost_eur is None else self.proceeds_eur - self.cost_eur

    @property
    def owner_gain_eur(self) -> float | None:
        return None if self.owner_cost_eur is None else self.proceeds_eur - self.owner_cost_eur


@dataclass
class Book:
    """Stand eines Depots nach allen bisher angewendeten Ereignissen."""

    depot_id: str
    pots: dict[str, float] = field(default_factory=lambda: {p: 0.0 for p in POTS})
    lots: dict[str, list[Lot]] = field(default_factory=dict)
    holdings: dict[str, dict[str, float]] = field(default_factory=dict)  # ISIN → Zuordnung → Stück
    owner_cost: dict[str, dict[str, float | None]] = field(default_factory=dict)  # ISIN → Zuordnung → Einstand (EUR)
    realized: list[Realized] = field(default_factory=list)
    fees_eur: float = 0.0
    income_eur: float = 0.0
    taxes_eur: float = 0.0
    deposits_eur: float = 0.0  # Summe Einzahlungen − Auszahlungen
    flows: list[tuple[int, str, float]] = field(default_factory=list)  # (Tag, Topf, Betrag) – Zu- und Abflüsse je Topf
    last_seq: int = 0
    applied: set[str] = field(default_factory=set)
    first_buy_day: dict[tuple[str, str], int] = field(default_factory=dict)  # (ISIN, Zuordnung) → Tag des ersten Kaufs

    # ------------------------------------------------------------------ Abfragen

    @property
    def cash_eur(self) -> float:
        return float(sum(self.pots.values()))

    def qty(self, isin: str, owner: str | None = None) -> float:
        per = self.holdings.get(isin, {})
        if owner is None:
            return sum(per.values())
        return per.get(owner, 0.0)

    def owners(self, isin: str) -> dict[str, float]:
        return {k: v for k, v in self.holdings.get(isin, {}).items() if abs(v) > EPS}

    def positions(self) -> dict[str, float]:
        return {isin: total for isin in self.holdings if (total := self.qty(isin)) > EPS}

    def owned_by(self, owner: str) -> dict[str, float]:
        return {isin: q for isin, per in self.holdings.items() if (q := per.get(owner, 0.0)) > EPS}

    def cost_basis(self, isin: str) -> float | None:
        lots = self.lots.get(isin, [])
        if not lots:
            return 0.0
        if any(lot.cost_eur is None for lot in lots):
            return None
        return float(sum(lot.cost_eur for lot in lots))

    def managed_average_cost(self, isin: str) -> float | None:
        """Ø Einstand je Stück über alle verwalteten aktiven Zuordnungen (Regel „kein Aufstocken verlustreicher Positionen“, auch
        über eine andere Strategie); None, wenn Kosten unbekannt sind oder keine aktive Position besteht."""
        qty = 0.0
        cost = 0.0
        for owner, held in self.owners(isin).items():
            if not is_active_owner(owner):
                continue
            value = self.owner_cost.get(isin, {}).get(owner)
            if value is None:
                return None
            qty += held
            cost += value
        return cost / qty if qty > EPS else None

    def unknown_costs(self) -> list[str]:
        return sorted(isin for isin, lots in self.lots.items() if any(l.cost_eur is None and l.qty > EPS for l in lots))

    # ------------------------------------------------------------------ Buchen

    def apply(self, event: Event) -> None:
        if event.id in self.applied:
            return  # Wiederholung: genau einmal gebucht
        if event.typ not in EVENT_TYPES:
            raise BookingError(f"Unbekannter Ereignistyp {event.typ!r}")
        getattr(self, f"_apply_{event.typ}")(event)
        self.applied.add(event.id)
        self.last_seq = max(self.last_seq, int(event.seq))

    def _cash(self, pot: str, amount: float) -> None:
        self.pots[pot] = self.pots.get(pot, 0.0) + amount
        if abs(self.pots[pot]) < 1e-7:
            self.pots[pot] = 0.0

    def _add_holding(self, isin: str, owner: str, qty: float, cost: float | None) -> None:
        per = self.holdings.setdefault(isin, {})
        costs = self.owner_cost.setdefault(isin, {})
        held = per.get(owner, 0.0)
        if qty >= 0:
            old = costs.get(owner, 0.0) if held > EPS else 0.0
            costs[owner] = None if old is None or cost is None else old + cost
        else:
            share = min(1.0, -qty / held) if held > EPS else 1.0
            old = costs.get(owner, 0.0)
            costs[owner] = None if old is None else old * (1.0 - share)
        per[owner] = held + qty
        if abs(per[owner]) < EPS:
            per[owner] = 0.0
            costs[owner] = 0.0

    def _apply_einzahlung(self, e: Event) -> None:
        if e.betrag_eur < 0:
            raise BookingError("Einzahlung mit negativem Betrag")
        self._cash(e.pot, e.betrag_eur)
        self.deposits_eur += e.betrag_eur
        self.flows.append((e.tag, e.pot, e.betrag_eur))

    def _apply_auszahlung(self, e: Event) -> None:
        if e.betrag_eur > 0:
            raise BookingError("Auszahlung mit positivem Betrag")
        self._cash(e.pot, e.betrag_eur)
        self.deposits_eur += e.betrag_eur
        self.flows.append((e.tag, e.pot, e.betrag_eur))

    def _apply_gebuehr(self, e: Event) -> None:
        self._cash(e.pot, e.betrag_eur)
        self.fees_eur += -e.betrag_eur

    def _apply_dividende(self, e: Event) -> None:
        self._cash(e.pot, e.betrag_eur)
        self.income_eur += e.betrag_eur

    _apply_zins = _apply_dividende

    def _apply_steuer(self, e: Event) -> None:
        self._cash(e.pot, e.betrag_eur)
        self.taxes_eur += -e.betrag_eur

    def _apply_kauf(self, e: Event) -> None:
        if not e.isin or not e.stueck or e.stueck <= 0:
            raise BookingError("Kauf ohne ISIN oder positive Stückzahl")
        if e.betrag_eur > 0:
            raise BookingError("Kauf mit positivem Betrag (Abfluss erwartet)")
        self._cash(e.pot, e.betrag_eur)
        self.fees_eur += e.gebuehren_eur
        cost = -e.betrag_eur  # Kurswert + Gebühren in EUR
        self.lots.setdefault(e.isin, []).append(Lot(e.isin, float(e.stueck), cost, e.tag, e.id, e.nutzlast.get("fondsart")))
        self.first_buy_day.setdefault((e.isin, e.owner), e.tag)
        self._add_holding(e.isin, e.owner, float(e.stueck), cost)

    def _consume_fifo(self, isin: str, qty: float, used: list | None = None) -> tuple[float | None, str | None]:
        """Lose nach FIFO verbrauchen; ``used`` sammelt (Kauf-Ereignis, Anschaffungstag, Stück, Kosten) je verbrauchtem Los."""
        remaining = qty
        cost_total: float | None = 0.0
        fund_type = None
        lots = self.lots.get(isin, [])
        while remaining > EPS and lots:
            lot = lots[0]
            fund_type = fund_type or lot.fund_type
            take = min(lot.qty, remaining)
            share = take / lot.qty
            if lot.cost_eur is None:
                cost_total = None
                part = None
            else:
                part = lot.cost_eur * share
                if cost_total is not None:
                    cost_total += part
                lot.cost_eur -= part
            if used is not None:
                used.append((lot.event_id, lot.day, take, part))
            lot.qty -= take
            remaining -= take
            if lot.qty <= EPS:
                lots.pop(0)
        if remaining > EPS:
            raise BookingError(f"{isin}: Verkauf über den gesamten Bestand hinaus ({remaining:g} Stück fehlen)")
        return cost_total, fund_type

    def _apply_verkauf(self, e: Event) -> None:
        if not e.isin or not e.stueck or e.stueck <= 0:
            raise BookingError("Verkauf ohne ISIN oder positive Stückzahl")
        owner = e.owner
        held = self.qty(e.isin, owner)
        if held + EPS < e.stueck:
            raise BookingError(f"{e.isin}: Verkauf von {e.stueck:g} Stück für „{owner}“, verwaltet sind nur {held:g}")
        owner_cost = self.owner_cost.get(e.isin, {}).get(owner, 0.0)
        owner_share = None if owner_cost is None else owner_cost * min(1.0, float(e.stueck) / held)
        used: list = []
        cost, fund_type = self._consume_fifo(e.isin, float(e.stueck), used)
        self._cash(e.pot, e.betrag_eur)
        self.fees_eur += e.gebuehren_eur
        self._add_holding(e.isin, owner, -float(e.stueck), None)
        if self.qty(e.isin, owner) <= EPS:
            self.first_buy_day.pop((e.isin, owner), None)
        self.realized.append(Realized(e.id, e.isin, e.tag, float(e.stueck), e.betrag_eur, cost, owner, owner_share, fund_type, tuple(used)))

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
            # Anfangsguthaben eines Topfs – ein Bestand, keine Einzahlung
            self._cash(e.pot, e.betrag_eur)
            return
        if not e.stueck or e.stueck <= 0:
            raise BookingError("Anfangsbestand ohne positive Stückzahl")
        cost = e.nutzlast.get("anschaffungskosten_eur")
        day = e.nutzlast.get("kauftag")
        cost_value = None if cost is None else float(cost)
        self.lots.setdefault(e.isin, []).append(Lot(e.isin, float(e.stueck), cost_value, None if day is None else int(day), e.id, e.nutzlast.get("fondsart")))
        self._add_holding(e.isin, e.owner, float(e.stueck), cost_value)

    def _apply_umbuchung(self, e: Event) -> None:
        source = str(e.nutzlast.get("von"))
        target = str(e.nutzlast.get("nach"))
        if e.isin is None:
            if source not in POTS or target not in POTS or e.betrag_eur <= 0:
                raise BookingError("Umbuchung von Guthaben braucht Töpfe und positiven Betrag")
            if self.pots.get(source, 0.0) + 1e-6 < e.betrag_eur:
                raise BookingError(f"Umbuchung: Topf „{source}“ hat nur {self.pots.get(source, 0.0):.2f} EUR")
            self._cash(source, -e.betrag_eur)
            self._cash(target, e.betrag_eur)
            self.flows.append((e.tag, source, -e.betrag_eur))
            self.flows.append((e.tag, target, e.betrag_eur))
            return
        if not e.stueck or e.stueck <= 0:
            raise BookingError("Umbuchung ohne positive Stückzahl")
        held = self.qty(e.isin, source)
        if held + EPS < e.stueck:
            raise BookingError(f"{e.isin}: Umbuchung von „{source}“ über den Bestand hinaus")
        cost = self.owner_cost.get(e.isin, {}).get(source, 0.0)
        moved = None if cost is None else cost * min(1.0, float(e.stueck) / held)
        self._add_holding(e.isin, source, -float(e.stueck), None)
        self._add_holding(e.isin, target, float(e.stueck), moved)

    def _apply_korrektur(self, e: Event) -> None:
        delta_qty = float(e.nutzlast.get("stueck_differenz", 0.0))
        self._cash(e.pot, e.betrag_eur)
        if e.isin and abs(delta_qty) > EPS:
            owner = e.owner
            if delta_qty > 0:
                cost = e.nutzlast.get("kosten_differenz_eur")
                self.lots.setdefault(e.isin, []).append(Lot(e.isin, delta_qty, None if cost is None else float(cost), e.tag, e.id))
                self._add_holding(e.isin, owner, delta_qty, None if cost is None else float(cost))
            else:
                self._consume_fifo(e.isin, -delta_qty)
                self._add_holding(e.isin, owner, delta_qty, None)


def replay(depot_id: str, events: list[Event]) -> Book:
    """Depotstand aus allen Ereignissen in der Reihenfolge ihrer Nummer."""
    book = Book(depot_id)
    for event in sorted(events, key=lambda e: e.seq):
        book.apply(event)
    return book


@dataclass(frozen=True)
class Valuation:
    day: int
    pots: dict[str, float]
    positions_eur: dict[str, float]  # ISIN → Wert (nur bekannte Kurse)
    missing: tuple[str, ...]  # ISINs ohne Kurs oder Wechselkurs – Gesamtwert ist dann ein Teilwert
    by_owner_eur: dict[str, float]
    prices_eur: dict[str, float]  # ISIN → Kurs in EUR

    @property
    def cash_eur(self) -> float:
        return float(sum(self.pots.values()))

    @property
    def total_eur(self) -> float:
        return self.cash_eur + sum(self.positions_eur.values())

    @property
    def complete(self) -> bool:
        return not self.missing

    def owner_value(self, owners) -> float:
        return sum(v for k, v in self.by_owner_eur.items() if k in owners)

    @property
    def active_eur(self) -> float:
        """Aktiver Teil: Topf ``aktiv`` plus alle aktiven Positionen (ohne Kern und extern)."""
        return self.pots.get("aktiv", 0.0) + sum(v for k, v in self.by_owner_eur.items() if is_active_owner(k))

    @property
    def core_eur(self) -> float:
        return self.pots.get("kern", 0.0) + sum(v for k, v in self.by_owner_eur.items() if k in CORE_OWNERS)


def value(book: Book, market, day: int) -> Valuation:
    """Bewertung zum letzten Schlusskurs bis ``day`` in EUR (EZB-Referenzkurs des Tages oder davor)."""
    positions: dict[str, float] = {}
    by_owner: dict[str, float] = {}
    prices: dict[str, float] = {}
    missing: list[str] = []
    for isin, total in book.positions().items():
        last = market.last_close(isin, day)
        eur = None if last is None else market.price_eur(isin, last[0], day)
        if eur is None:
            missing.append(isin)
            continue
        prices[isin] = eur
        positions[isin] = eur * total
        for owner, qty in book.owners(isin).items():
            by_owner[owner] = by_owner.get(owner, 0.0) + eur * qty
    return Valuation(day, dict(book.pots), positions, tuple(sorted(missing)), by_owner, prices)
