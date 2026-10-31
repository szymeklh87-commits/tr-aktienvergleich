"""Interner PAPER-Simulator: virtuelle Ausführung von Orders und Stops mit Tageskerzen (Abschnitte 13, 29.4).

Regeln (konservativ, dokumentiert):

* Ausgeführt wird nur zum Kurs der Ausführungssitzung des Profils (Eröffnung bei TAGESDATEN, Schluss bei FOLGETAG-SCHLUSS) –
  nie zu einem Kurs vor der Veröffentlichung der Entscheidung. Fehlt die Kerze dieser Sitzung (kein Handel, Feiertag), verfällt
  ein Kauf; ein Verkauf wird für die nächste Sitzung neu eingeplant (Schutz- und Risikoverkäufe verfallen nie still).
* Kosten: halber Spread nach Liquiditätsklasse, Slippage, Währungsaufschlag, TR-Aufschlag beim Schlussprofil, Ordergebühr
  (``kosten``). Kauf zum Kurs plus Aufschlag, Verkauf minus Aufschlag; EUR mit dem EZB-Referenzkurs des Ausführungstags.
* Liquidität: höchstens ``ANTEIL_TAGESVOLUMEN`` des gemeldeten Tagesvolumens; Tage ohne Umsatz führen nicht aus. Ein Kauf wird
  auf das tatsächlich verfügbare Guthaben (einschließlich seiner Reservierung) gekürzt – Teilausführung statt Überziehung.
* Stops gelten wie beim Broker hinterlegt: Eröffnung unter dem Stop → Ausführung zur Eröffnung (Kurslücke, schlechter als das
  Stopniveau); sonst Tief unter dem Stop → Ausführung zum Stopniveau; jeweils minus Verkaufskosten. Fehlen Eröffnung/Tief, zählt
  nur der Schlusskurs (Prüfung zum Schluss, als „nur Schlusskurs bekannt“ markiert). Innerhalb einer Tageskerze gilt die
  ungünstige Reihenfolge: Stop vor Gewinnmitnahme.
* Splits: Kerzen sind splitbereinigt; gerechnet wird mit dem damals gehandelten Kurs (bereinigter Kurs × Faktor späterer
  Splits). Ein Split nach einer Ausführung wird als eigenes Ereignis gebucht (Stückzahl × Faktor, Stopniveau ÷ Faktor) – kein
  künstlicher Gewinn.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from . import kosten
from .config import AktienPilotConfig

ANTEIL_TAGESVOLUMEN = 0.05


@dataclass
class SimOrder:
    id: str
    depot_id: str
    zuordnung: str
    isin: str
    richtung: str  # kauf | verkauf
    stueck: int
    grund: str  # z. B. regel:auswahl, regel:herausfallen, gewinnmitnahme, risiko:schliessen, kern:rebalancing, stop
    profil: str
    datentag: int
    sitzung: int | None
    preispunkt: str | None  # open | close
    frueheste: str | None
    ablauf: str | None
    reserviert_eur: float = 0.0
    status: str = "offen"  # offen | ausgefuehrt | teilweise | verfallen | abgelehnt | storniert
    ausgefuehrt_stueck: int = 0
    signal_id: str | None = None
    schutz: bool = False  # Schutz-/Risikoverkauf: wird bis zur Ausführung neu eingeplant
    begruendung: dict = field(default_factory=dict)
    stop_plan: dict | None = None  # Initialstop nach Ausführung: {"art": "atr", "abstand": x} | {"art": "prozent", "wert": w}
    regel: str | None = None  # Regel-ID@Version
    stufen: tuple[str, ...] = ()
    erstellt_am: str = ""
    grund_text: str = ""

    def as_dict(self) -> dict:
        return {
            "id": self.id, "depot": self.depot_id, "zuordnung": self.zuordnung, "isin": self.isin, "richtung": self.richtung,
            "stueck": self.stueck, "grund": self.grund, "grund_text": self.grund_text, "profil": self.profil, "datentag": self.datentag,
            "sitzung": self.sitzung, "preispunkt": self.preispunkt, "frueheste": self.frueheste, "ablauf": self.ablauf,
            "reserviert_eur": round(self.reserviert_eur, 2), "status": self.status, "ausgefuehrt_stueck": self.ausgefuehrt_stueck,
            "signal": self.signal_id, "schutz": self.schutz, "begruendung": self.begruendung, "stop_plan": self.stop_plan,
            "regel": self.regel, "stufen": list(self.stufen), "erstellt_am": self.erstellt_am,
        }

    @staticmethod
    def from_dict(d: dict) -> "SimOrder":
        return SimOrder(
            id=d["id"], depot_id=d["depot"], zuordnung=d["zuordnung"], isin=d["isin"], richtung=d["richtung"], stueck=int(d["stueck"]),
            grund=d["grund"], profil=d["profil"], datentag=int(d["datentag"]), sitzung=d.get("sitzung"), preispunkt=d.get("preispunkt"),
            frueheste=d.get("frueheste"), ablauf=d.get("ablauf"), reserviert_eur=float(d.get("reserviert_eur") or 0.0),
            status=d.get("status", "offen"), ausgefuehrt_stueck=int(d.get("ausgefuehrt_stueck") or 0), signal_id=d.get("signal"),
            schutz=bool(d.get("schutz")), begruendung=d.get("begruendung") or {}, stop_plan=d.get("stop_plan"), regel=d.get("regel"),
            stufen=tuple(d.get("stufen") or ()), erstellt_am=d.get("erstellt_am", ""), grund_text=d.get("grund_text", ""),
        )


@dataclass(frozen=True)
class Fill:
    stueck: int
    referenzkurs: float  # Kurs der Kerze (Basiswährung, splitbereinigt wie die Kerzen)
    kurs: float  # Ausführungskurs nach Spread/Slippage/Aufschlägen (Basiswährung)
    fx_eur: float
    betrag_eur: float  # Kauf: −(Kurswert + Gebühr); Verkauf: +(Kurswert − Gebühr)
    gebuehr_eur: float
    kosten: dict
    tag: int
    hinweis: str | None = None


@dataclass(frozen=True)
class NichtAusgefuehrt:
    grund: str
    neu_einplanen: bool = False


def _price_at(series, k: int, point: str) -> float | None:
    """Kurs der Kerze ``k`` in der Basiswährung, wie damals gehandelt (splitbereinigt × Faktor späterer Splits)."""
    value = series.open[k] if point == "open" else series.close[k]
    if not math.isfinite(value) or value <= 0:
        return None
    return float(value) * series.unit_factor * series.split_factor_after(int(series.days[k]))


def ausfuehren(order: SimOrder, series, market, cfg: AktienPilotConfig, *, turnover_eur: float | None, verfuegbar_eur: float,
               gehalten: float) -> Fill | NichtAusgefuehrt:
    """Ausführung einer fälligen Order an ihrer Sitzung (Kerze muss vorhanden sein, sonst NichtAusgefuehrt)."""
    if order.sitzung is None or order.preispunkt is None:
        return NichtAusgefuehrt("keine erreichbare Sitzung – nicht simulierbar")
    k = series.index_of(order.sitzung)
    if k is None:
        return NichtAusgefuehrt("kein Kurs in der Ausführungssitzung (kein Handel oder Feiertag)", neu_einplanen=order.richtung == "verkauf")
    volume = float(series.volume[k]) if math.isfinite(series.volume[k]) else None
    if volume is not None and volume <= 0:
        return NichtAusgefuehrt("kein Umsatz in der Ausführungssitzung", neu_einplanen=order.richtung == "verkauf")
    ref = _price_at(series, k, order.preispunkt)
    if ref is None:
        if order.preispunkt == "open":
            return NichtAusgefuehrt("Eröffnungskurs fehlt – Ausführung zur Eröffnung nicht simulierbar", neu_einplanen=order.richtung == "verkauf")
        return NichtAusgefuehrt("Schlusskurs fehlt", neu_einplanen=order.richtung == "verkauf")
    fx = market.eur_rate(series.currency, order.sitzung)
    if fx is None or not (fx > 0):
        return NichtAusgefuehrt("kein EZB-Wechselkurs für die Ausführung", neu_einplanen=order.richtung == "verkauf")
    q = kosten.quote(cfg.handelskosten, order.richtung, ref, currency=series.currency, turnover_eur=turnover_eur,
                     next_close_profile=order.preispunkt == "close")
    qty = int(order.stueck - order.ausgefuehrt_stueck)
    hinweis = None
    if volume is not None:
        cap = int(math.floor(volume * ANTEIL_TAGESVOLUMEN))
        if cap < qty:
            qty = cap
            hinweis = f"auf {ANTEIL_TAGESVOLUMEN * 100:.0f} % des Tagesvolumens begrenzt"
    if order.richtung == "kauf":
        price_eur = q.price * fx
        affordable = int(math.floor((verfuegbar_eur - q.fee_eur) / price_eur + 1e-9)) if price_eur > 0 else 0
        if affordable < qty:
            qty = max(0, affordable)
            hinweis = "auf das verfügbare Guthaben gekürzt"
        if qty < 1:
            return NichtAusgefuehrt("Guthaben oder Liquidität reicht nicht für ein Stück")
        value = qty * price_eur
        return Fill(qty, ref, q.price, fx, -(value + q.fee_eur), q.fee_eur, q.as_dict(), order.sitzung, hinweis)
    qty = int(min(qty, math.floor(gehalten + 1e-9)))
    if qty < 1:
        return NichtAusgefuehrt("kein verwalteter Bestand mehr")
    value = qty * q.price * fx
    return Fill(qty, ref, q.price, fx, value - q.fee_eur, q.fee_eur, q.as_dict(), order.sitzung, hinweis)


@dataclass(frozen=True)
class StopFill:
    stueck: int
    stop: float
    referenzkurs: float
    kurs: float
    fx_eur: float
    betrag_eur: float
    gebuehr_eur: float
    kosten: dict
    tag: int
    luecke: bool
    nur_schluss: bool


def stop_pruefen(stop: float, series, k: int, market, cfg: AktienPilotConfig, *, qty: float, turnover_eur: float | None) -> StopFill | None:
    """Stop an Kerze ``k`` (Basiswährung, splitbereinigt). Ausgelöst → StopFill zum Ausführungskurs nach Kosten."""
    if qty < 1 or not (stop > 0):
        return None
    day = int(series.days[k])
    f = series.unit_factor * series.split_factor_after(day)  # wie damals gehandelt
    o = float(series.open[k]) * f if math.isfinite(series.open[k]) else math.nan
    lo = float(series.low[k]) * f if math.isfinite(series.low[k]) else math.nan
    c = float(series.close[k]) * f if math.isfinite(series.close[k]) else math.nan
    gap = False
    only_close = False
    if math.isfinite(o) and math.isfinite(lo):
        if o <= stop:
            ref, gap = o, True
        elif lo <= stop:
            ref = stop
        else:
            return None
    elif math.isfinite(c):
        if c > stop:
            return None
        ref, only_close = c, True
    else:
        return None
    fx = market.eur_rate(series.currency, day)
    if fx is None or not (fx > 0):
        return None  # ohne Wechselkurs keine Bewertung – Stop bleibt aktiv, nächste Kerze
    q = kosten.quote(cfg.handelskosten, "verkauf", ref, currency=series.currency, turnover_eur=turnover_eur, next_close_profile=False)
    n = int(math.floor(qty + 1e-9))
    value = n * q.price * fx
    return StopFill(n, stop, ref, q.price, fx, value - q.fee_eur, q.fee_eur, q.as_dict(), day, gap, only_close)


def sell_price_factor(cfg: AktienPilotConfig, currency: str, turnover_eur: float | None, next_close: bool = True) -> float:
    """Faktor Verkaufskurs/Referenzkurs für die Schätzung des liquidierbaren Werts (Gewinn nach Kosten)."""
    q = kosten.quote(cfg.handelskosten, "verkauf", 1.0, currency=currency, turnover_eur=turnover_eur, next_close_profile=next_close)
    return q.price


def buy_price_factor(cfg: AktienPilotConfig, currency: str, turnover_eur: float | None, next_close: bool = True) -> float:
    q = kosten.quote(cfg.handelskosten, "kauf", 1.0, currency=currency, turnover_eur=turnover_eur, next_close_profile=next_close)
    return q.price
