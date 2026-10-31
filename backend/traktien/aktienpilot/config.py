"""Konfiguration des AktienPilot (``config/aktienpilot.yaml``) mit Prüfung beim Laden.

Erweitert das vorhandene Konfigurationsformat (YAML unter ``config/``, Dataclasses wie ``traktien.config``). Geprüft werden
Wertebereiche, Aufzählungen und das Nullbudget: Ein als kostenpflichtig gekennzeichneter Anbieter lässt sich nicht aktivieren
(Abschnitt 0). Der Fingerabdruck (SHA-256 der kanonischen Werte) bindet Backtests und Echtgeldfreigaben an genau diese Werte.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml

from ..config import CONFIG_DIR
from ..util.jsonio import canonical_bytes, sha256_hex

PROFILES = ("TAGESDATEN", "VERZOEGERTER-EINSTIEG", "FOLGETAG-SCHLUSS")
# Betriebsmodi der aktuellen Lieferung: nur virtuell (Abschnitt 29.1). LIVE ist reine Zukunftsspezifikation (Abschnitte 22, 27)
# und weder in der Konfiguration noch in der Datenbank (CHECK in Migration 0010) auswählbar.
MODES = ("PAPER", "SIGNAL")
CONFIRM_WAYS = ("aus", "lokal", "github")


class ConfigError(ValueError):
    """Ungültige AktienPilot-Konfiguration."""


def _num(raw: dict, key: str, default: float, lo: float, hi: float, *, integer: bool = False) -> Any:
    value = raw.get(key, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError(f"{key}: Zahl erwartet, nicht {value!r}")
    if integer and float(value) != int(value):
        raise ConfigError(f"{key}: ganze Zahl erwartet, nicht {value!r}")
    if not (lo <= value <= hi):
        raise ConfigError(f"{key}: {value} liegt außerhalb von {lo}–{hi}")
    return int(value) if integer else float(value)


def _text(raw: dict, key: str, default: str, choices: tuple[str, ...] | None = None) -> str:
    value = raw.get(key, default)
    if not isinstance(value, str):
        raise ConfigError(f"{key}: Text erwartet, nicht {value!r}")
    if choices is not None and value not in choices:
        raise ConfigError(f"{key}: {value!r} ist nicht in {choices}")
    return value


def _bool(raw: dict, key: str, default: bool) -> bool:
    value = raw.get(key, default)
    if not isinstance(value, bool):
        raise ConfigError(f"{key}: ja/nein (true/false) erwartet, nicht {value!r}")
    return value


@dataclass(frozen=True)
class DepotConfig:
    waehrung: str = "EUR"
    demo_startkapital_eur: float = 10_000.0
    aktiver_anteil_max: float = 0.30
    ausfuehrungsprofil: str = "FOLGETAG-SCHLUSS"
    universum: str = "tr_gesamt"
    mindestkurs_eur: float = 1.0
    mindestumsatz_eur: float = 2_000_000.0


@dataclass(frozen=True)
class RiskConfig:
    risiko_je_trade: float = 0.01
    max_je_aktie: float = 0.10
    max_je_branche_gesamt: float = 0.25
    max_je_branche_aktiv: float = 0.50
    max_einzelaktien: int = 8
    max_orderwert_eur: float = 5000.0
    max_datenalter_sitzungen: int = 3
    max_kursabweichung: float = 0.03
    tagesverlust_kaufstopp: float = 0.05
    drawdown_nur_risikosenkend: float = 0.15
    drawdown_schliessen: float = 0.20
    unbekannte_branche: str = "Unbekannt"


@dataclass(frozen=True)
class ExecutionConfig:
    veroeffentlichung_backtest: str = "07:30"
    zeitzone: str = "Europe/Berlin"
    verzoegerung_minuten: int = 15
    gueltigkeit_sitzungen: int = 1
    stop_beim_broker: bool = True

    def publication_minutes(self) -> int:
        hours, minutes = self.veroeffentlichung_backtest.split(":")
        return int(hours) * 60 + int(minutes)


@dataclass(frozen=True)
class CostConfig:
    ordergebuehr_eur: float = 1.0
    spread_bp_liquide: float = 10.0
    spread_bp_normal: float = 25.0
    spread_bp_illiquide: float = 60.0
    slippage_bp: float = 5.0
    waehrung_bp: float = 15.0
    tr_aufschlag_bp: float = 10.0


@dataclass(frozen=True)
class Instrument:
    isin: str
    name: str
    notierung: str
    symbol: str
    waehrung: str
    ausschuettung: str
    fondsart: str


@dataclass(frozen=True)
class LinealConfig:
    version: str = "lineal-vorwaerts-1"
    gruppe: str = "A"
    gewichtung: int = 50
    zeitraum_tage: int = 30
    anzahl: int = 8
    umschichtung_wochentag: int = 4


@dataclass(frozen=True)
class S1Config:
    version: str = "s1-momentum-1"
    regression_sitzungen: int = 60
    gewicht_gleichmaessigkeit: float = 0.6
    gewicht_steigung: float = 0.4
    ma_filter: int = 100
    max_luecke: float = 0.15
    luecke_sitzungen: int = 90
    anzahl: int = 5
    rangpuffer: int = 3
    umschichtung_wochentag: int = 4
    atr: int = 14
    initialstop_atr: float = 2.0


@dataclass(frozen=True)
class S2Config:
    version: str = "s2-breakout-1"
    hoch_sitzungen: int = 55
    volumen_faktor: float = 1.5
    volumen_sitzungen: int = 20
    atr: int = 14
    initialstop_atr: float = 2.0
    trailing_atr: float = 3.0
    anzahl: int = 5


@dataclass(frozen=True)
class S3Config:
    version: str = "s3-meanrev-1"
    rsi_periode: int = 2
    rsi_kauf_unter: float = 10.0
    ma_trend: int = 200
    ma_ausstieg: int = 5
    max_haltedauer: int = 10
    atr: int = 14
    initialstop_atr: float = 2.0
    anzahl: int = 5


@dataclass(frozen=True)
class MarketFilterConfig:
    aktiv: bool = True
    ma: int = 200
    leitindex: dict = field(default_factory=dict)


@dataclass(frozen=True)
class S4Config:
    version: str = "s4-robo-1"
    rebalancing_schwelle_pp: float = 5.0
    sparrate_eur: float = 0.0


@dataclass(frozen=True)
class ReleaseConfig:
    min_trades_oos: int = 50
    min_profitfaktor: float = 1.2
    max_drawdown: float = 0.25
    min_paper_sitzungen: int = 30
    min_paper_ausfuehrungen: int = 20
    code_gueltig_minuten: int = 30


@dataclass(frozen=True)
class TaxConfig:
    abgeltungsteuer: float = 0.25
    solidaritaetszuschlag: float = 0.055
    kirchensteuer: float = 0.0
    sparerpauschbetrag_eur: float = 1000.0
    teilfreistellung_aktienfonds: float = 0.30
    basiszins_vorabpauschale: dict = field(default_factory=dict)

    def rate(self) -> float:
        """Steuersatz auf Kapitalerträge: Abgeltungsteuer und Solidaritätszuschlag darauf; mit Kirchensteuer nach § 32d Abs. 1
        EStG ermäßigt (Abgeltungsteuer = 25 % / (1 + 0,25 × Kirchensteuersatz))."""
        if self.kirchensteuer > 0:
            base = self.abgeltungsteuer / (1 + self.abgeltungsteuer * self.kirchensteuer)
            return base * (1 + self.solidaritaetszuschlag + self.kirchensteuer)
        return self.abgeltungsteuer * (1 + self.solidaritaetszuschlag)


@dataclass(frozen=True)
class ConfirmConfig:
    weg: str = "lokal"
    lokal_ordner: str = "eingang"
    github_repository: str = ""
    github_pfad: str = "eingang"
    max_groesse_byte: int = 65536
    max_alter_tage: int = 14


@dataclass(frozen=True)
class NotifyConfig:
    ntfy_aktiv: bool = False
    ntfy_server: str = "https://ntfy.sh"
    ntfy_topic_umgebung: str = "NTFY_TOPIC"
    max_je_tag: int = 5


@dataclass(frozen=True)
class Provider:
    name: str
    zweck: str
    kostenpflichtig: bool
    aktiv: bool


@dataclass(frozen=True)
class AktienPilotConfig:
    version: str = "aktienpilot-konfig-1"
    aktiv: bool = True
    veroeffentlichen: bool = False
    budget_einmalig_eur: float = 0.0
    budget_laufend_eur: float = 0.0
    depot: DepotConfig = field(default_factory=DepotConfig)
    risiko: RiskConfig = field(default_factory=RiskConfig)
    ausfuehrung: ExecutionConfig = field(default_factory=ExecutionConfig)
    handelskosten: CostConfig = field(default_factory=CostConfig)
    msci_world: Instrument | None = None
    geldmarkt: Instrument | None = None
    lineal: LinealConfig = field(default_factory=LinealConfig)
    s1: S1Config = field(default_factory=S1Config)
    s2: S2Config = field(default_factory=S2Config)
    s3: S3Config = field(default_factory=S3Config)
    marktfilter: MarketFilterConfig = field(default_factory=MarketFilterConfig)
    budget_aktiv: dict = field(default_factory=lambda: {"s1": 0.4, "s2": 0.3, "s3": 0.3})
    s4: S4Config = field(default_factory=S4Config)
    freigabe: ReleaseConfig = field(default_factory=ReleaseConfig)
    steuern: TaxConfig = field(default_factory=TaxConfig)
    bestaetigung: ConfirmConfig = field(default_factory=ConfirmConfig)
    benachrichtigung: NotifyConfig = field(default_factory=NotifyConfig)
    anbieter: tuple[Provider, ...] = ()

    def as_dict(self) -> dict:
        return asdict(self)

    def fingerprint(self) -> str:
        return sha256_hex(canonical_bytes(self.as_dict()))

    def strategy(self, name: str):
        return {"lineal": self.lineal, "s1": self.s1, "s2": self.s2, "s3": self.s3, "s4": self.s4}[name]

    def strategy_fingerprint(self, name: str) -> str:
        """Bindung einer Strategie: Parameter, Risiko-, Kosten- und Ausführungswerte (Abschnitt 22)."""
        bound = {
            "strategie": asdict(self.strategy(name)),
            "risiko": asdict(self.risiko),
            "kosten": asdict(self.handelskosten),
            "ausfuehrung": asdict(self.ausfuehrung),
            "profil": self.depot.ausfuehrungsprofil,
            "marktfilter": asdict(self.marktfilter),
        }
        return sha256_hex(canonical_bytes(bound))


def _instrument(raw: Any, key: str) -> Instrument | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ConfigError(f"vergleich.{key}: Abschnitt erwartet")
    values = {name: _text(raw, name, "") for name in ("isin", "name", "notierung", "symbol", "waehrung", "ausschuettung", "fondsart")}
    isin = values["isin"]
    if len(isin) != 12 or not isin[:2].isalpha() or not isin.isalnum():
        raise ConfigError(f"vergleich.{key}.isin: keine gültige ISIN ({isin!r})")
    return Instrument(**values)


def parse_config(raw: dict | None) -> AktienPilotConfig:
    raw = raw or {}
    if not isinstance(raw, dict):
        raise ConfigError("Konfiguration muss ein Abschnitt (Zuordnung) sein")
    budget = raw.get("budget") or {}
    once = _num(budget, "einmalig_eur", 0.0, 0.0, 0.0)
    running = _num(budget, "laufend_eur", 0.0, 0.0, 0.0)

    d = raw.get("depot") or {}
    depot = DepotConfig(
        waehrung=_text(d, "waehrung", "EUR", ("EUR",)),
        demo_startkapital_eur=_num(d, "demo_startkapital_eur", 10_000.0, 100.0, 10_000_000.0),
        aktiver_anteil_max=_num(d, "aktiver_anteil_max", 0.30, 0.0, 1.0),
        ausfuehrungsprofil=_text(d, "ausfuehrungsprofil", "FOLGETAG-SCHLUSS", PROFILES),
        universum=_text(d, "universum", "tr_gesamt", ("tr_gesamt",)),
        mindestkurs_eur=_num(d, "mindestkurs_eur", 1.0, 0.0, 10_000.0),
        mindestumsatz_eur=_num(d, "mindestumsatz_eur", 2_000_000.0, 0.0, 1e12),
    )

    r = raw.get("risiko") or {}
    risk = RiskConfig(
        risiko_je_trade=_num(r, "risiko_je_trade", 0.01, 0.0001, 0.05),
        max_je_aktie=_num(r, "max_je_aktie", 0.10, 0.001, 1.0),
        max_je_branche_gesamt=_num(r, "max_je_branche_gesamt", 0.25, 0.001, 1.0),
        max_je_branche_aktiv=_num(r, "max_je_branche_aktiv", 0.50, 0.001, 1.0),
        max_einzelaktien=_num(r, "max_einzelaktien", 8, 1, 100, integer=True),
        max_orderwert_eur=_num(r, "max_orderwert_eur", 5000.0, 1.0, 1e9),
        max_datenalter_sitzungen=_num(r, "max_datenalter_sitzungen", 3, 0, 30, integer=True),
        max_kursabweichung=_num(r, "max_kursabweichung", 0.03, 0.001, 0.5),
        tagesverlust_kaufstopp=_num(r, "tagesverlust_kaufstopp", 0.05, 0.001, 1.0),
        drawdown_nur_risikosenkend=_num(r, "drawdown_nur_risikosenkend", 0.15, 0.001, 1.0),
        drawdown_schliessen=_num(r, "drawdown_schliessen", 0.20, 0.001, 1.0),
        unbekannte_branche=_text(r, "unbekannte_branche", "Unbekannt"),
    )
    if not risk.drawdown_nur_risikosenkend < risk.drawdown_schliessen:
        raise ConfigError("risiko: drawdown_nur_risikosenkend muss kleiner als drawdown_schliessen sein")

    a = raw.get("ausfuehrung") or {}
    publication = _text(a, "veroeffentlichung_backtest", "07:30")
    parts = publication.split(":")
    if len(parts) != 2 or not all(p.isdigit() for p in parts) or not (0 <= int(parts[0]) < 24 and 0 <= int(parts[1]) < 60):
        raise ConfigError(f"ausfuehrung.veroeffentlichung_backtest: Uhrzeit HH:MM erwartet, nicht {publication!r}")
    execution = ExecutionConfig(
        veroeffentlichung_backtest=publication,
        zeitzone=_text(a, "zeitzone", "Europe/Berlin"),
        verzoegerung_minuten=_num(a, "verzoegerung_minuten", 15, 0, 240, integer=True),
        gueltigkeit_sitzungen=_num(a, "gueltigkeit_sitzungen", 1, 1, 10, integer=True),
        stop_beim_broker=_bool(a, "stop_beim_broker", True),
    )

    k = raw.get("handelskosten") or {}
    costs = CostConfig(**{name: _num(k, name, default, 0.0, 10_000.0) for name, default in asdict(CostConfig()).items()})

    v = raw.get("vergleich") or {}
    st = raw.get("strategien") or {}

    li = st.get("lineal") or {}
    lineal = LinealConfig(
        version=_text(li, "version", "lineal-vorwaerts-1"),
        gruppe=_text(li, "gruppe", "A", ("A", "B")),
        gewichtung=_num(li, "gewichtung", 50, 0, 100, integer=True),
        zeitraum_tage=_num(li, "zeitraum_tage", 30, 1, 90, integer=True),
        anzahl=_num(li, "anzahl", 8, 1, 50, integer=True),
        umschichtung_wochentag=_num(li, "umschichtung_wochentag", 4, 0, 6, integer=True),
    )
    if lineal.gewichtung % 10:
        raise ConfigError("strategien.lineal.gewichtung: nur Zehnerschritte 0–100")

    s1r = st.get("s1") or {}
    s1 = S1Config(
        version=_text(s1r, "version", "s1-momentum-1"),
        regression_sitzungen=_num(s1r, "regression_sitzungen", 60, 20, 90, integer=True),
        gewicht_gleichmaessigkeit=_num(s1r, "gewicht_gleichmaessigkeit", 0.6, 0.0, 1.0),
        gewicht_steigung=_num(s1r, "gewicht_steigung", 0.4, 0.0, 1.0),
        ma_filter=_num(s1r, "ma_filter", 100, 2, 400, integer=True),
        max_luecke=_num(s1r, "max_luecke", 0.15, 0.01, 1.0),
        luecke_sitzungen=_num(s1r, "luecke_sitzungen", 90, 1, 400, integer=True),
        anzahl=_num(s1r, "anzahl", 5, 1, 50, integer=True),
        rangpuffer=_num(s1r, "rangpuffer", 3, 0, 100, integer=True),
        umschichtung_wochentag=_num(s1r, "umschichtung_wochentag", 4, 0, 6, integer=True),
        atr=_num(s1r, "atr", 14, 2, 100, integer=True),
        initialstop_atr=_num(s1r, "initialstop_atr", 2.0, 0.1, 20.0),
    )
    if abs(s1.gewicht_gleichmaessigkeit + s1.gewicht_steigung - 1.0) > 1e-9:
        raise ConfigError("strategien.s1: Gewichte Gleichmäßigkeit und Steigung müssen zusammen 1 ergeben")

    s2r = st.get("s2") or {}
    s2 = S2Config(
        version=_text(s2r, "version", "s2-breakout-1"),
        hoch_sitzungen=_num(s2r, "hoch_sitzungen", 55, 2, 400, integer=True),
        volumen_faktor=_num(s2r, "volumen_faktor", 1.5, 0.1, 100.0),
        volumen_sitzungen=_num(s2r, "volumen_sitzungen", 20, 2, 400, integer=True),
        atr=_num(s2r, "atr", 14, 2, 100, integer=True),
        initialstop_atr=_num(s2r, "initialstop_atr", 2.0, 0.1, 20.0),
        trailing_atr=_num(s2r, "trailing_atr", 3.0, 0.1, 20.0),
        anzahl=_num(s2r, "anzahl", 5, 1, 50, integer=True),
    )

    s3r = st.get("s3") or {}
    s3 = S3Config(
        version=_text(s3r, "version", "s3-meanrev-1"),
        rsi_periode=_num(s3r, "rsi_periode", 2, 2, 50, integer=True),
        rsi_kauf_unter=_num(s3r, "rsi_kauf_unter", 10.0, 0.0, 100.0),
        ma_trend=_num(s3r, "ma_trend", 200, 2, 400, integer=True),
        ma_ausstieg=_num(s3r, "ma_ausstieg", 5, 1, 100, integer=True),
        max_haltedauer=_num(s3r, "max_haltedauer", 10, 1, 100, integer=True),
        atr=_num(s3r, "atr", 14, 2, 100, integer=True),
        initialstop_atr=_num(s3r, "initialstop_atr", 2.0, 0.1, 20.0),
        anzahl=_num(s3r, "anzahl", 5, 1, 50, integer=True),
    )

    mf = st.get("marktfilter") or {}
    index_map = mf.get("leitindex") or {}
    if not isinstance(index_map, dict) or not all(isinstance(k, str) and isinstance(x, str) for k, x in index_map.items()):
        raise ConfigError("strategien.marktfilter.leitindex: Zuordnung Börse → Indexkürzel erwartet")
    market_filter = MarketFilterConfig(aktiv=_bool(mf, "aktiv", True), ma=_num(mf, "ma", 200, 2, 400, integer=True), leitindex=dict(index_map))

    budget_active = st.get("budget_aktiv") or {"s1": 0.4, "s2": 0.3, "s3": 0.3}
    if set(budget_active) - {"s1", "s2", "s3"}:
        raise ConfigError("strategien.budget_aktiv: nur s1, s2, s3")
    shares = {name: _num(budget_active, name, 0.0, 0.0, 1.0) for name in budget_active}
    if sum(shares.values()) > 1.0 + 1e-9:
        raise ConfigError("strategien.budget_aktiv: Anteile zusammen höchstens 1")

    s4r = st.get("s4") or {}
    s4 = S4Config(
        version=_text(s4r, "version", "s4-robo-1"),
        rebalancing_schwelle_pp=_num(s4r, "rebalancing_schwelle_pp", 5.0, 0.1, 100.0),
        sparrate_eur=_num(s4r, "sparrate_eur", 0.0, 0.0, 1e7),
    )

    f = raw.get("freigabe") or {}
    release = ReleaseConfig(
        min_trades_oos=_num(f, "min_trades_oos", 50, 1, 100_000, integer=True),
        min_profitfaktor=_num(f, "min_profitfaktor", 1.2, 0.0, 100.0),
        max_drawdown=_num(f, "max_drawdown", 0.25, 0.0, 1.0),
        min_paper_sitzungen=_num(f, "min_paper_sitzungen", 30, 1, 10_000, integer=True),
        min_paper_ausfuehrungen=_num(f, "min_paper_ausfuehrungen", 20, 1, 100_000, integer=True),
        code_gueltig_minuten=_num(f, "code_gueltig_minuten", 30, 1, 1440, integer=True),
    )

    t = raw.get("steuern") or {}
    rates = t.get("basiszins_vorabpauschale") or {}
    if not isinstance(rates, dict):
        raise ConfigError("steuern.basiszins_vorabpauschale: Zuordnung Jahr → Basiszins erwartet")
    clean_rates = {}
    for year, value in rates.items():
        if not str(year).isdigit() or isinstance(value, bool) or not isinstance(value, (int, float)) or not (-0.05 <= value <= 0.2):
            raise ConfigError(f"steuern.basiszins_vorabpauschale: ungültiger Eintrag {year!r}: {value!r}")
        clean_rates[str(year)] = float(value)
    tax = TaxConfig(
        abgeltungsteuer=_num(t, "abgeltungsteuer", 0.25, 0.0, 1.0),
        solidaritaetszuschlag=_num(t, "solidaritaetszuschlag", 0.055, 0.0, 1.0),
        kirchensteuer=_num(t, "kirchensteuer", 0.0, 0.0, 0.09),
        sparerpauschbetrag_eur=_num(t, "sparerpauschbetrag_eur", 1000.0, 0.0, 100_000.0),
        teilfreistellung_aktienfonds=_num(t, "teilfreistellung_aktienfonds", 0.30, 0.0, 1.0),
        basiszins_vorabpauschale=clean_rates,
    )

    b = raw.get("bestaetigung") or {}
    confirm = ConfirmConfig(
        weg=_text(b, "weg", "lokal", CONFIRM_WAYS),
        lokal_ordner=_text(b, "lokal_ordner", "eingang"),
        github_repository=_text(b, "github_repository", ""),
        github_pfad=_text(b, "github_pfad", "eingang"),
        max_groesse_byte=_num(b, "max_groesse_byte", 65536, 256, 1_048_576, integer=True),
        max_alter_tage=_num(b, "max_alter_tage", 14, 1, 365, integer=True),
    )
    if confirm.weg == "github":
        repo_name = confirm.github_repository
        if repo_name.count("/") != 1 or not all(repo_name.split("/")):
            raise ConfigError("bestaetigung.github_repository: <konto>/<repository> erwartet")
        if repo_name.split("/")[1] == "tr-aktienvergleich":
            raise ConfigError("bestaetigung.github_repository: nicht das Code-Repository – ein getrenntes privates Daten-Repository")

    n = raw.get("benachrichtigung") or {}
    notify = NotifyConfig(
        ntfy_aktiv=_bool(n, "ntfy_aktiv", False),
        ntfy_server=_text(n, "ntfy_server", "https://ntfy.sh"),
        ntfy_topic_umgebung=_text(n, "ntfy_topic_umgebung", "NTFY_TOPIC"),
        max_je_tag=_num(n, "max_je_tag", 5, 0, 100, integer=True),
    )
    if not notify.ntfy_server.startswith("https://"):
        raise ConfigError("benachrichtigung.ntfy_server: nur https")

    providers = []
    for entry in raw.get("anbieter") or []:
        if not isinstance(entry, dict):
            raise ConfigError("anbieter: Liste von Abschnitten erwartet")
        provider = Provider(
            name=_text(entry, "name", ""),
            zweck=_text(entry, "zweck", ""),
            kostenpflichtig=_bool(entry, "kostenpflichtig", True),
            aktiv=_bool(entry, "aktiv", False),
        )
        if provider.kostenpflichtig and provider.aktiv:
            raise ConfigError(f"anbieter {provider.name!r}: kostenpflichtig und aktiv – Nullbudget (Abschnitt 0) verbietet das")
        providers.append(provider)

    return AktienPilotConfig(
        version=_text(raw, "version", "aktienpilot-konfig-1"),
        aktiv=_bool(raw, "aktiv", True),
        veroeffentlichen=_bool(raw, "veroeffentlichen", False),
        budget_einmalig_eur=once,
        budget_laufend_eur=running,
        depot=depot,
        risiko=risk,
        ausfuehrung=execution,
        handelskosten=costs,
        msci_world=_instrument(v.get("msci_world"), "msci_world"),
        geldmarkt=_instrument(v.get("geldmarkt"), "geldmarkt"),
        lineal=lineal,
        s1=s1,
        s2=s2,
        s3=s3,
        marktfilter=market_filter,
        budget_aktiv=shares,
        s4=s4,
        freigabe=release,
        steuern=tax,
        bestaetigung=confirm,
        benachrichtigung=notify,
        anbieter=tuple(providers),
    )


def load_aktienpilot_config(path: Path | None = None) -> AktienPilotConfig:
    path = path or CONFIG_DIR / "aktienpilot.yaml"
    if not path.exists():
        return parse_config({})
    return parse_config(yaml.safe_load(path.read_text(encoding="utf-8")) or {})
