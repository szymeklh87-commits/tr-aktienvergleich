"""Zentraler Risiko-Manager und Verlustgrenzen (Abschnitte 15 und 16).

Jede Order und jedes handelbare Signal – in Backtest, PAPER und SIGNAL – läuft durch dieselben zwei Funktionen:

* ``size_buy`` bestimmt die Stückzahl eines Kaufs als **zulässiges Minimum** aus Stop-Risiko, Positionsgrenze, Branchengrenzen,
  Strategiebudget, aktiver Kapitalbindung, freiem Guthaben einschließlich Kosten, Liquidität und Höchstorderwert – oder lehnt mit
  Grund ab (Pause, Verlustgrenze, Zahl der Einzelaktien, Aufstocken einer verlustreichen Position, Datenalter, Kursabweichung,
  nicht freigegebene Strategie bei Echtgeld, unvollständiger Bestand bei Echtgeld, synthetische Daten bei Echtgeld).
* ``check_sell`` erlaubt Verkäufe verwalteter Positionen immer (Schutzverkäufe werden nie durch Kaufsperren blockiert), verkauft nie
  fremde (``extern``) Positionen und den ETF-Kern nur nach seiner Rebalancing-Regel.

Bezugsgrößen (Abschnitt 15): Grenzen „vom Gesamtdepot“ beziehen sich auf ``reference_eur``. Im Pilotdepot ist das der Gesamtwert
des Depots. Ein Vergleichsdepot, das nur eine Strategie führt, steht für den aktiven Teil eines Gesamtdepots mit dem konfigurierten
aktiven Anteil: Bezugsgröße = Depotwert / aktiver Anteil (bei 30 % entsprechen 1 % des Gesamtdepots 3,33 % des aktiven Teils).

Verlustgrenzen (Abschnitt 16) misst ``LossLimits`` am aktiven Teil, zeitgewichtet (bereinigt um Zu- und Abflüsse des Topfs
``aktiv``), bewertet zum Schluss jeder Sitzung: Tagesverlust ab 5 % → keine neuen aktiven Käufe bis zur nächsten Sitzung;
Rückgang vom fortgeschriebenen Höchststand ab 15 % → nur risikosenkende Transaktionen; ab 20 % → geordnete Schließung aktiver
Positionen und Pause bis zur ausdrücklichen Freigabe; danach beginnt die Höchststand-Messung protokolliert neu.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .config import AktienPilotConfig

LIQUIDITY_SHARE = 0.01  # höchstens 1 % des Ø Tagesumsatzes (20 Sitzungen) je Order
ALLOWED_TYPES = ("aktie", "etf")
STAGES = ("normal", "tagesstopp", "nur_risikosenkend", "schliessen")


@dataclass
class Exposure:
    """Depotweiter Stand für die Prüfung (Positionen und offene Kauforders, alles in EUR)."""

    reference_eur: float  # Bezugsgröße „Gesamtdepot“
    complete: bool  # Bewertung und Bestand vollständig
    active_cap_eur: float  # erlaubte aktive Kapitalbindung
    active_eur: float  # aktive Positionen + reservierte aktive Kauforders
    free_cash_eur: float  # Guthaben des Topfs abzüglich Reservierungen
    by_isin_eur: dict[str, float] = field(default_factory=dict)  # alle Zuordnungen (auch extern) + Reservierungen
    by_strategy_eur: dict[str, float] = field(default_factory=dict)  # aktive Positionen + Reservierungen je Strategie
    strategy_budget_eur: dict[str, float] = field(default_factory=dict)
    sector_total_eur: dict[str, float] = field(default_factory=dict)
    sector_active_eur: dict[str, float] = field(default_factory=dict)
    single_stocks: set[str] = field(default_factory=set)  # Einzelaktien im Depot oder reserviert (verwaltet und extern)


@dataclass(frozen=True)
class BuyRequest:
    isin: str
    strategy: str
    instrument_type: str  # aktie | etf
    sector: str | None
    entry_eur: float  # erwarteter Ausführungskurs je Stück in EUR inkl. Spread/Slippage/Aufschlägen
    fee_eur: float
    stop_eur: float | None  # Initialstop je Stück in EUR (Pflicht bei aktiven Käufen)
    turnover_eur: float | None  # Ø Tagesumsatz über 20 Sitzungen
    price_now_eur: float  # aktueller Kurs (Bewertung) für die Aufstock-Regel
    managed_average_cost_eur: float | None  # Ø Einstand aktiver Bestände dieser ISIN (alle Strategien)
    data_age_sessions: int
    deviation: float | None  # Abweichung zum ausreichend aktuellen Referenzkurs (Anteil), None = nicht geprüft
    core: bool = False  # Kauf für den ETF-Kern (S4): keine Stop- und Einzelaktiengrenzen
    real_money: bool = False
    released: bool = False  # Strategie nach Abschnitt 22 freigegeben
    synthetic: bool = False


@dataclass(frozen=True)
class RiskDecision:
    allowed: bool
    qty: int
    reason: str | None
    limits: dict  # Stückzahl je Grenze (für das Protokoll und die App)
    binding: str | None  # welche Grenze die Stückzahl bestimmt

    def as_dict(self) -> dict:
        return {"erlaubt": self.allowed, "stueck": self.qty, "grund": self.reason, "grenzen": self.limits, "bestimmend": self.binding}


def _floor(value: float) -> int:
    if not math.isfinite(value) or value <= 0:
        return 0
    return int(math.floor(value + 1e-9))


def size_buy(cfg: AktienPilotConfig, exposure: Exposure, request: BuyRequest, loss: "LossLimits", *, paused: bool) -> RiskDecision:
    """Stückzahl eines Kaufs nach allen zentralen Grenzen – oder Ablehnung mit Grund."""
    risk = cfg.risiko

    def reject(reason: str) -> RiskDecision:
        return RiskDecision(False, 0, reason, {}, None)

    if request.instrument_type not in ALLOWED_TYPES:
        return reject("Instrumenttyp nicht erlaubt (nur Aktien und ETFs; kein Hebel, keine Derivate)")
    if request.real_money:
        # Abschnitt 29.1: In dieser Lieferung gibt es keinen Echtgeldweg – auch eine nach Abschnitt 22 „freigegebene“ Strategie
        # bekommt hier keine Stückzahl. Die Freigabeprüfung bleibt reine Zukunftsspezifikation.
        return reject("Echtgeld ist ausgeschlossen – nur Spielgeld (PAPER/DEMO)")
    if paused:
        return reject("Automatik pausiert")
    if not request.core:
        block = loss.blocks_new_buys()
        if block:
            return reject(block)
    if request.entry_eur <= 0 or not math.isfinite(request.entry_eur):
        return reject("kein gültiger Kurs")
    if request.data_age_sessions > risk.max_datenalter_sitzungen:
        return reject(f"Daten {request.data_age_sessions} Sitzungen alt (höchstens {risk.max_datenalter_sitzungen})")
    if request.deviation is not None and abs(request.deviation) > risk.max_kursabweichung:
        return reject(f"Kurs weicht {abs(request.deviation) * 100:.1f} % vom Referenzkurs ab (höchstens {risk.max_kursabweichung * 100:.0f} %)")
    if not request.core:
        if request.stop_eur is None or not (0 < request.stop_eur < request.entry_eur):
            return reject("kein gültiger Initialstop unter dem Einstieg")
        if request.managed_average_cost_eur is not None and request.price_now_eur < request.managed_average_cost_eur:
            return reject("kein Aufstocken einer verlustreichen Position (Kurs unter dem Ø Einstand)")
        if request.isin not in exposure.single_stocks and request.instrument_type == "aktie" and len(exposure.single_stocks) >= risk.max_einzelaktien:
            return reject(f"schon {len(exposure.single_stocks)} Einzelaktien im Depot (höchstens {risk.max_einzelaktien})")

    ref = exposure.reference_eur
    price = request.entry_eur
    limits: dict[str, int] = {}
    if not request.core:
        limits["risiko_je_trade"] = _floor(risk.risiko_je_trade * ref / (request.entry_eur - request.stop_eur))  # type: ignore[operator]
        limits["je_aktie"] = _floor((risk.max_je_aktie * ref - exposure.by_isin_eur.get(request.isin, 0.0)) / price)
        sector = request.sector or risk.unbekannte_branche
        limits["branche_gesamt"] = _floor((risk.max_je_branche_gesamt * ref - exposure.sector_total_eur.get(sector, 0.0)) / price)
        limits["branche_aktiv"] = _floor((risk.max_je_branche_aktiv * exposure.active_cap_eur - exposure.sector_active_eur.get(sector, 0.0)) / price)
        limits["aktive_bindung"] = _floor((exposure.active_cap_eur - exposure.active_eur) / price)
        budget = exposure.strategy_budget_eur.get(request.strategy)
        if budget is not None:
            limits["strategiebudget"] = _floor((budget - exposure.by_strategy_eur.get(request.strategy, 0.0)) / price)
    limits["guthaben"] = _floor((exposure.free_cash_eur - request.fee_eur) / price)
    if request.turnover_eur is not None and math.isfinite(request.turnover_eur):
        limits["liquiditaet"] = _floor(LIQUIDITY_SHARE * request.turnover_eur / price)
    else:
        limits["liquiditaet"] = 0 if not request.core else limits["guthaben"]
    if not request.core:
        # Höchstorderwert gilt für aktive Orders; der Kern (Welt-/Geldmarkt-ETF) wird nach Zielaufteilung in einem Schritt angelegt –
        # sonst wäre der Vergleich „Welt-ETF mit identischem Startkapital“ über mehrere Tage verteilt (Abschnitt 29.6)
        limits["orderwert"] = _floor(risk.max_orderwert_eur / price)
    binding = min(limits, key=lambda k: limits[k])
    qty = limits[binding]
    if qty < 1:
        names = {
            "risiko_je_trade": "Risiko je Trade", "je_aktie": "Grenze je Aktie", "branche_gesamt": "Branchengrenze (Gesamtdepot)",
            "branche_aktiv": "Branchengrenze (aktiver Teil)", "aktive_bindung": "aktive Kapitalbindung", "strategiebudget": "Strategiebudget",
            "guthaben": "freies Guthaben", "liquiditaet": "Liquidität (Ø Tagesumsatz)", "orderwert": "Höchstorderwert",
        }
        return RiskDecision(False, 0, f"keine ganze Aktie zulässig: {names.get(binding, binding)}", limits, binding)
    return RiskDecision(True, qty, None, limits, binding)


def check_sell(owner: str, qty_held: float, qty: float, *, reason: str) -> tuple[bool, str | None]:
    """Verkauf prüfen: fremde Positionen nie; ETF-Kern nur nach Rebalancing; sonst immer erlaubt (Schutz vor Kaufsperren)."""
    if owner == "extern":
        return False, "nicht von AktienPilot verwaltet – wird nie automatisch verkauft"
    if owner == "kern" and reason != "rebalancing":
        return False, "ETF-Kern wird nur nach seiner bestätigten Zielaufteilung umgeschichtet, nie durch aktive Regeln"
    if qty <= 0 or qty > qty_held + 1e-9:
        return False, "Stückzahl größer als der verwaltete Bestand"
    return True, None


# ------------------------------------------------------------------------------------------------ Verlustgrenzen


@dataclass
class LossLimits:
    """Zustand der Verlustgrenzen des aktiven Teils (zeitgewichteter Index, fortgeschriebener Höchststand)."""

    day_limit: float = 0.05
    dd_reduce: float = 0.15
    dd_close: float = 0.20
    index: float = 1.0
    peak: float = 1.0
    last_value: float | None = None
    last_day: int | None = None
    stage: str = "normal"
    stop_until_day: int | None = None  # Tagesstopp gilt bis einschließlich dieses Tages
    paused_until_release: bool = False
    day_return: float | None = None
    history: list[dict] = field(default_factory=list)

    @staticmethod
    def from_config(cfg: AktienPilotConfig) -> "LossLimits":
        r = cfg.risiko
        return LossLimits(day_limit=r.tagesverlust_kaufstopp, dd_reduce=r.drawdown_nur_risikosenkend, dd_close=r.drawdown_schliessen)

    @property
    def drawdown(self) -> float:
        return 0.0 if self.peak <= 0 else max(0.0, 1.0 - self.index / self.peak)

    def blocks_new_buys(self) -> str | None:
        if self.paused_until_release or self.stage == "schliessen":
            return f"Rückgang ≥ {self.dd_close * 100:.0f} % – aktive Positionen werden geschlossen, Pause bis zur Freigabe"
        if self.stage == "nur_risikosenkend":
            return f"Rückgang ≥ {self.dd_reduce * 100:.0f} % vom Höchststand – nur risikosenkende Transaktionen"
        if self.stage == "tagesstopp":
            return f"Tagesverlust ≥ {self.day_limit * 100:.0f} % – keine neuen aktiven Käufe bis zur nächsten Sitzung"
        return None

    def update(self, day: int, active_value: float, net_flow: float) -> list[dict]:
        """Bewertung zum Sitzungsschluss ``day``: ``active_value`` inklusive offener Positionen, ``net_flow`` = Zuflüsse in den
        aktiven Teil an diesem Tag (Einzahlungen, Umbuchungen; Abflüsse negativ). Rückgabe: neue Übergänge."""
        events: list[dict] = []
        if self.stage == "tagesstopp" and self.stop_until_day is not None and day > self.stop_until_day:
            self.stage = "normal"
            self.stop_until_day = None
        if self.last_value is None or self.last_value <= 0:
            self.last_value = active_value
            self.last_day = day
            self.day_return = None
            return events
        ret = (active_value - net_flow) / self.last_value - 1.0
        self.day_return = ret
        self.index *= 1.0 + ret
        self.peak = max(self.peak, self.index)
        self.last_value = active_value
        self.last_day = day
        dd = self.drawdown
        new_stage = self.stage
        if self.paused_until_release:
            new_stage = "schliessen"
        elif dd >= self.dd_close:
            new_stage = "schliessen"
            self.paused_until_release = True
        elif dd >= self.dd_reduce:
            new_stage = "nur_risikosenkend"
        elif ret <= -self.day_limit:
            new_stage = "tagesstopp"
            self.stop_until_day = day
        elif self.stage in ("nur_risikosenkend",):
            new_stage = "normal"
        if new_stage != self.stage:
            events.append({"tag": day, "von": self.stage, "nach": new_stage, "rueckgang": round(dd, 6), "tagesrendite": round(ret, 6)})
            self.stage = new_stage
            self.history.extend(events)
        return events

    def release(self, day: int, reason: str) -> dict:
        """Ausdrückliche Freigabe nach der Pause: Höchststand-Messung beginnt neu, die Historie bleibt."""
        event = {"tag": day, "von": self.stage, "nach": "normal", "freigabe": reason, "rueckgang_vorher": round(self.drawdown, 6)}
        self.paused_until_release = False
        self.stage = "normal"
        self.stop_until_day = None
        self.peak = self.index
        self.history.append(event)
        return event

    def as_dict(self) -> dict:
        return {
            "stufe": self.stage, "index": self.index, "hoechststand": self.peak, "rueckgang": self.drawdown, "tagesrendite": self.day_return,
            "letzter_wert_eur": self.last_value, "letzter_tag": self.last_day, "tagesstopp_bis": self.stop_until_day,
            "pause_bis_freigabe": self.paused_until_release, "grenzen": {"tag": self.day_limit, "nur_risikosenkend": self.dd_reduce, "schliessen": self.dd_close},
            "verlauf": self.history[-50:],
        }

    @staticmethod
    def from_dict(data: dict) -> "LossLimits":
        limits = data.get("grenzen") or {}
        state = LossLimits(day_limit=float(limits.get("tag", 0.05)), dd_reduce=float(limits.get("nur_risikosenkend", 0.15)), dd_close=float(limits.get("schliessen", 0.20)))
        state.index = float(data.get("index", 1.0))
        state.peak = float(data.get("hoechststand", 1.0))
        state.last_value = data.get("letzter_wert_eur")
        state.last_day = data.get("letzter_tag")
        state.stage = data.get("stufe", "normal") if data.get("stufe") in STAGES else "normal"
        state.stop_until_day = data.get("tagesstopp_bis")
        state.paused_until_release = bool(data.get("pause_bis_freigabe", False))
        state.day_return = data.get("tagesrendite")
        state.history = list(data.get("verlauf") or [])
        return state
