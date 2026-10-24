"""Versionierte Konfiguration für Methode und Betrieb.

Die Methodenparameter sind transparente Startregeln aus dem Auftrag (Abschnitte 8–12).
Sie werden nicht stillschweigend verändert; jede Änderung braucht eine neue
``methode_version`` und einen Eintrag im CHANGELOG. Ihr Hash steht in jedem Manifest.
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .util.jsonio import canonical_bytes, sha256_hex

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = Path(os.environ.get("TRAKTIEN_CONFIG_DIR", REPO_ROOT / "config"))

CANONICAL_WEIGHTS: tuple[int, ...] = tuple(range(0, 101, 10))
POLICIES: tuple[str, ...] = ("native", "common_trend")
TOP_K_VALUES: tuple[int, ...] = (1, 3, 10)


@dataclass(frozen=True)
class Ratio:
    """Exakter Schwellenwert als Bruch; vermeidet Rundungsfehler an der Grenze."""

    num: int
    den: int

    def satisfied(self, part: int, whole: int) -> bool:
        if whole <= 0:
            return False
        return part * self.den >= whole * self.num

    def as_float(self) -> float:
        return self.num / self.den


VOLUME_BASES: tuple[str, ...] = ("sitzungen", "beobachtungen")


@dataclass(frozen=True)
class AdmissionRules:
    """Zulassungsregeln der veröffentlichten Kursrendite (Menge V) einer Methodenversion.

    ``session_coverage`` mit ``tolerated_missing_sessions``: Anteil der erwarteten Börsensitzungen mit
    Kurs; so viele fehlende Sitzungen sind immer erlaubt (ab tr-methode-1.8.0: eine). ``volume_basis``:
    Bezug der Volumenschwelle – „beobachtungen“ (vorhandene Kurse, wie im Ausgangsmodell) oder
    „sitzungen“ (erwartete Börsensitzungen). Mit den Regeln der Vorversion rechnet jeder Lauf zusätzlich
    nach (Methodenvergleich).
    """

    session_coverage: Ratio
    volume_coverage: Ratio
    volume_basis: str = "beobachtungen"
    # so viele fehlende erwartete Sitzungen sind immer erlaubt, auch wenn der Anteil darunter liegt
    tolerated_missing_sessions: int = 0
    volume_every_obs: bool = True
    edge_volume_positive: bool = True
    hold_split_windows: bool = True

    def validate(self, label: str) -> None:
        if self.volume_basis not in VOLUME_BASES:
            raise ValueError(f"{label}: volumen_bezug muss „sitzungen“ oder „beobachtungen“ sein")
        if self.tolerated_missing_sessions < 0:
            raise ValueError(f"{label}: fehlende_sitzungen_immer_erlaubt darf nicht negativ sein")
        for ratio in (self.session_coverage, self.volume_coverage):
            if ratio.den <= 0 or not (0 <= ratio.num <= ratio.den):
                raise ValueError(f"{label}: Schwellen als Bruch zwischen 0 und 1 angeben")


# Regeln von tr-methode-1.7.0 (Vorversion von 1.8.0): 98 % der erwarteten Sitzungen mit Kurs,
# 80 % der vorhandenen Beobachtungen mit positivem Volumen, Regeln des Ausgangsmodells zu Volumen und Splits
RULES_1_7_0 = AdmissionRules(
    session_coverage=Ratio(49, 50),
    volume_coverage=Ratio(4, 5),
    volume_basis="beobachtungen",
    tolerated_missing_sessions=0,
    volume_every_obs=True,
    edge_volume_positive=True,
    hold_split_windows=True,
)

# Regeln von tr-methode-1.8.0 (Vorversion von 1.9.0): dieselben Zulassungsregeln wie 1.9.0 – der Unterschied liegt im
# Stichtag je Aktie (siehe CHANGE_NOTES_1_9_0); der Methodenvergleich setzt dafür die Aktien mit eigenem Stichtag auf
# ihren Status am gemeinsamen Stichtag („Markt am Stichtag geschlossen“ bzw. „Kurs am Stichtag fehlt“)
RULES_1_8_0 = AdmissionRules(
    session_coverage=Ratio(4, 5),
    volume_coverage=Ratio(4, 5),
    volume_basis="beobachtungen",
    tolerated_missing_sessions=1,
    volume_every_obs=True,
    edge_volume_positive=True,
    hold_split_windows=True,
)

# Regeln von tr-methode-1.9.0 (Vorversion von 1.10.0): dieselben Zulassungsregeln und derselbe Stichtag je Aktie wie 1.10.0 –
# der Unterschied liegt allein in der Gleichstandsregel (ranking-11w-v2 → v3, siehe CHANGE_NOTES_1_10_0)
RULES_1_9_0 = AdmissionRules(
    session_coverage=Ratio(4, 5),
    volume_coverage=Ratio(4, 5),
    volume_basis="beobachtungen",
    tolerated_missing_sessions=1,
    volume_every_obs=True,
    edge_volume_positive=True,
    hold_split_windows=True,
)

CHANGE_NOTES_1_10_0: tuple[str, ...] = (
    "Gleichstand exakt (ranking-11w-v3, deine Entscheidung vom 24.10.2026): Bei gemischter Gewichtung wird der Score ohne Rundung verglichen – haben zwei Aktien rechnerisch denselben Score, steht die mit der höheren Kursrendite vorn, bei gleicher Rendite die kleinere ISIN. Bis 1.9.0 entschied dann eine Rundung in der letzten Stelle des Gleitkomma-Scores. Verschiedene Scores werden nicht gleichgesetzt (kein Runden auf Stellen).",
    "Unverändert: Ein fehlender Börsentag zählt als fehlend – kein Ersatzkurs, kein Wert null, der Zeitraum fällt nicht allein deshalb weg. Start- und Endkurs sind Pflicht, höchstens 20 % fehlende Börsentage (einer immer erlaubt), positives Volumen an mindestens 80 % der Kurstage, Volumen an jeder Beobachtung gemeldet, positives Volumen an Start und Ende, gemeldeter Split im Fenster zurückgehalten, letzter Schlusskurs bei höchstens einer verpassten Sitzung.",
)

CHANGE_NOTES_1_9_0: tuple[str, ...] = (
    "Alle Aktien werden bewertet: Fehlt der Schlusskurs am Stichtag – die Börse hatte Feiertag oder der Kursanbieter lieferte ihn nicht –, zählt die Aktie mit ihrem letzten Schlusskurs; ihre Zeiträume enden an diesem Tag. Höchstens eine verpasste Börsensitzung, ältere Kurse gelten als veraltet. Bis 1.8.0 fehlte die Aktie dann in den Ranglisten („Markt am Stichtag geschlossen“ bzw. „Kurs am Stichtag fehlt“).",
    "Unverändert: Start- und Endkurs sind Pflicht, höchstens 20 % fehlende Börsentage (einer immer erlaubt), positives Volumen an mindestens 80 % der Kurstage, Volumen an jeder Beobachtung gemeldet, positives Volumen an Start und Ende, gemeldeter Split im Fenster zurückgehalten, Gleichstand Score → Rendite → ISIN.",
)

CHANGE_NOTES_1_8_0: tuple[str, ...] = (
    "Fehlende Börsentage beim Kursanbieter: Ein Zeitraum bleibt bewertbar, wenn höchstens 20 % der erwarteten Börsentage fehlen; ein einzelner fehlender Tag ist immer erlaubt (bis 1.7.0: höchstens 2 %). Fehlende Tage werden nicht aufgefüllt.",
    "Unverändert: Start- und Endkurs sind Pflicht, positives Volumen an mindestens 80 % der Kurstage, Volumen an jeder Beobachtung gemeldet, positives Volumen an Start und Ende, gemeldeter Split im Fenster zurückgehalten, Gleichstand Score → Rendite → ISIN.",
    "Hinweis „Börsenplatz-Abweichung“ (boersenplatz-v3, ändert weder Rendite noch Rang): Verglichen wird nur der Schlusskurs genau des Start- und Enddatums und nur mit Umsatz am zweiten Börsenplatz; die Schwelle wächst mit der üblichen Tagesschwankung der Aktie (mindestens 10 %, ab Faktor 2 immer auffällig). Bis 1.7.0: letzter gelieferter Kurs bis 4 Tage vorher, feste Schwelle 10 %.",
)


@dataclass(frozen=True)
class RotationConfig:
    """Umschichtungs-Regel (rotation-v1): Varianten, Kosten, Kandidatenauswahl, Langhistorie."""

    version: str = "rotation-v1"
    default_holdings: int = 5
    default_rhythm: str = "monatlich"
    default_lookback_weeks: int = 13
    default_capital: float = 10_000.0
    holdings: tuple[int, ...] = (5, 10)
    rhythms: tuple[str, ...] = ("monatlich", "woechentlich")
    lookback_weeks: tuple[int, ...] = (13, 4)
    capitals: tuple[float, ...] = (5_000.0, 10_000.0, 25_000.0)
    keep_rank_factor: int = 2
    band: float = 0.05
    fee_eur: float = 1.0
    spread: float = 0.001
    tax_rate: float = 0.26375
    allowance_eur: float = 1000.0
    min_turnover_usd: float = 10_000_000.0
    turnover_weeks: int = 4
    min_positive_share: float = 0.8
    min_coverage: float = 0.9
    max_jump_factor: float = 3.0
    history_years: int = 3
    pool_min_turnover_usd: float = 2_000_000.0

    def validate(self) -> None:
        if self.default_holdings not in self.holdings or self.default_rhythm not in self.rhythms:
            raise ValueError("umschichtung: Standard muss unter den Varianten sein")
        if self.default_lookback_weeks not in self.lookback_weeks or self.default_capital not in self.capitals:
            raise ValueError("umschichtung: Standard muss unter den Varianten sein")
        if any(r not in ("monatlich", "woechentlich") for r in self.rhythms):
            raise ValueError("umschichtung: Rhythmus nur monatlich oder woechentlich")
        if any(h < 1 for h in self.holdings) or any(w < 1 for w in self.lookback_weeks) or any(c <= 0 for c in self.capitals):
            raise ValueError("umschichtung: Anzahl, Trendwochen und Kapital müssen positiv sein")
        if not (0 <= self.spread < 0.05 and 0 <= self.tax_rate < 1 and self.fee_eur >= 0 and self.allowance_eur >= 0):
            raise ValueError("umschichtung: Kosten außerhalb des zulässigen Bereichs")
        if self.history_years < 1 or self.max_jump_factor <= 1 or not (0 < self.min_coverage <= 1):
            raise ValueError("umschichtung: Langhistorie, Sprungfaktor oder Abdeckung ungültig")


@dataclass(frozen=True)
class MethodConfig:
    method_version: str = "tr-methode-1.10.0"
    metrics_version: str = "kennzahlen-v2"
    # ab tr-methode-1.10.0: ranking-11w-v3 – Score exakt verglichen (bis 1.9.0: ranking-11w-v2, Gleitkomma-Score)
    ranking_version: str = "ranking-11w-v3"
    frequency_version: str = "frequency-v2"
    groups_version: str = "gruppen-v1"  # Gruppenvergleich A/B (ab 1.4)
    # Bezug: Ausgangsmodell, dessen dokumentierte Regeln ab tr-methode-1.7.0 übernommen sind
    reference_model: str = "TR-90D-11W-two-universes-v1.1"
    previous_method_version: str = "tr-methode-1.9.0"
    # Vorversion für den Methodenvergleich jedes Laufs: ihre Ranglistenversion (Gleichstandsregel) und ob sie ohne
    # Stichtagskurs schon den letzten Schlusskurs zählte (ab 1.9.0; bis 1.8.0 fehlte die Aktie dann)
    previous_ranking_version: str = "ranking-11w-v2"
    previous_last_close: bool = True
    calendar_convention: str = "kalendertage"
    currency_basis: str = "notierungswaehrung_splitbereinigt_ohne_dividenden"
    min_window: int = 1
    max_window: int = 90
    anchor_max_gap_days: int = 7
    # ab tr-methode-1.9.0: ohne Schlusskurs am Stichtag zählt der letzte Schlusskurs, wenn die Börse seitdem höchstens so
    # viele Sitzungen hatte (1 = der Stichtag selbst; Feiertage zählen nicht); sonst gilt der Kurs als veraltet
    last_close_max_missed_sessions: int = 1
    weights: tuple[int, ...] = CANONICAL_WEIGHTS
    min_obs_trend: int = 15
    min_obs_return: int = 2
    # ab tr-methode-1.8.0: höchstens 20 % der erwarteten Sitzungen ohne Kurs, eine fehlende Sitzung immer
    # erlaubt (bis 1.7.0: 98 % Pflicht); fehlende Tage werden nicht aufgefüllt. Positives Volumen an 80 %
    # der Kurstage (Beobachtungen), wie im Ausgangsmodell.
    min_session_coverage: Ratio = Ratio(4, 5)
    tolerated_missing_sessions: int = 1
    min_volume_coverage: Ratio = Ratio(4, 5)
    volume_basis: str = "beobachtungen"
    # ab tr-methode-1.7.0 (Regeln des Ausgangsmodells): Volumen an jeder Beobachtung gemeldet (≥ 0),
    # Start- und Endbeobachtung mit positivem Volumen, gemeldeter Split im Fenster → zurückhalten
    volume_every_obs: bool = True
    edge_volume_positive: bool = True
    hold_split_windows: bool = True
    jump_factor: float = 3.0
    zero_volume_move: float = 0.10
    split_mismatch_min_factor: float = 1.25
    sst_rel_tolerance: float = 1e-18
    r2_bound_tolerance: float = 1e-9
    impulse_share: float = 0.5
    impulse_min_abs_return: float = 0.10
    thin_trading_zero_share: float = 0.2
    thin_trading_lookback: int = 20
    unknown_volume_warn_share: float = 0.2
    takeover_jump_min: float = 0.15
    takeover_calm_max: float = 0.01
    takeover_calm_sessions: int = 3
    turnover_version: str = "umsatz-v1"
    turnover_sessions: int = 20
    turnover_min_positive: int = 16
    turnover_threshold_usd: float = 10_000_000.0
    turnover_very_low_usd: float = 1_000_000.0
    fx_max_age_days: int = 5
    venue_version: str = "boersenplatz-v3"
    venue_top_n: int = 10
    venue_preferred: tuple[str, ...] = ("XETR", "XFRA")
    venue_max_return_dev: float = 0.10
    venue_max_level_dev: float = 0.10
    venue_max_gap_days: int = 4
    venue_max_instruments: int = 600
    venue_noise_factor: float = 3.0  # ab v3: Schwelle wächst mit der üblichen Tagesschwankung (0 = feste Schwellen)
    venue_noise_sessions: int = 20
    venue_max_dev_cap: float = 1.0  # Schwelle höchstens Faktor 2
    venue_require_volume: bool = True  # ab v3: nur Vergleichskurse mit Umsatz
    rotation: RotationConfig = field(default_factory=RotationConfig)
    # Regeln der Vorversion (Methodenvergleich in jedem Lauf) und Kurzbeschreibung der Änderungen
    previous_rules: AdmissionRules = RULES_1_9_0
    change_notes: tuple[str, ...] = CHANGE_NOTES_1_10_0
    excluded_security_types: tuple[str, ...] = (
        "ETP",
        "ETF",
        "Mutual Fund",
        "Open-End Fund",
        "Closed-End Fund",
        "Fund",
        "Right",
        "Warrant",
        "Equity WRT",
        "Bond",
        "Certificate",
    )

    def windows(self) -> range:
        return range(self.min_window, self.max_window + 1)

    @property
    def tie_rule(self) -> str:
        """Gleichstandsregel dieser Version (``ranking-11w-v3`` → ``v3``)."""
        from .analytics.ranking import tie_rule_of

        return tie_rule_of(self.ranking_version)

    @property
    def previous_tie_rule(self) -> str:
        from .analytics.ranking import tie_rule_of

        return tie_rule_of(self.previous_ranking_version)

    def validate(self) -> None:
        if tuple(self.weights) != CANONICAL_WEIGHTS:
            raise ValueError("Es sind genau elf Gewichtungen 0,10,…,100 vorgeschrieben")
        # unbekannte Ranglistenversionen früh ablehnen (ValueError aus tie_rule_of)
        _ = (self.tie_rule, self.previous_tie_rule)
        if self.min_window != 1 or self.max_window != 90:
            raise ValueError("Der Auftrag verlangt die Fenster 1 bis 90 Kalendertage")
        if self.min_obs_trend < 3 or self.min_obs_return < 2:
            raise ValueError("Mindestbeobachtungen zu klein")
        if not (1 <= self.turnover_min_positive <= self.turnover_sessions):
            raise ValueError("umsatz: min_sitzungen_mit_umsatz muss zwischen 1 und sitzungen liegen")
        if self.turnover_threshold_usd <= 0 or self.turnover_very_low_usd < 0:
            raise ValueError("umsatz: Schwellen müssen positiv sein")
        if self.fx_max_age_days < 0:
            raise ValueError("umsatz: wechselkurs_max_alter_tage darf nicht negativ sein")
        if not (0 <= self.last_close_max_missed_sessions <= 5):
            raise ValueError("letzter_schlusskurs_max_verpasste_sitzungen muss zwischen 0 und 5 liegen")
        if self.venue_top_n < 0 or self.venue_max_instruments < 0 or self.venue_max_gap_days < 0:
            raise ValueError("boersenplatz: plaetze, max_aktien und max_abstand_tage dürfen nicht negativ sein")
        if not (0 < self.venue_max_return_dev < 1 and 0 < self.venue_max_level_dev < 1):
            raise ValueError("boersenplatz: Schwellen müssen zwischen 0 und 1 liegen")
        if self.venue_noise_factor < 0 or self.venue_noise_sessions < 5:
            raise ValueError("boersenplatz: schwankung_faktor darf nicht negativ sein, schwankung_sitzungen mindestens 5")
        if not (max(self.venue_max_return_dev, self.venue_max_level_dev) <= self.venue_max_dev_cap <= 10):
            raise ValueError("boersenplatz: schwelle_hoechstens muss zwischen den festen Schwellen und 10 liegen")
        self.rotation.validate()
        self.admission_rules().validate("qualitaet")
        self.previous_rules.validate("vorherige_regeln")

    def admission_rules(self) -> AdmissionRules:
        """Zulassungsregeln dieser Methodenversion."""
        return AdmissionRules(
            session_coverage=self.min_session_coverage,
            volume_coverage=self.min_volume_coverage,
            volume_basis=self.volume_basis,
            tolerated_missing_sessions=self.tolerated_missing_sessions,
            volume_every_obs=self.volume_every_obs,
            edge_volume_positive=self.edge_volume_positive,
            hold_split_windows=self.hold_split_windows,
        )

    def venue_settings(self):
        from .analytics.venues import VenueSettings

        return VenueSettings(
            top_n=self.venue_top_n,
            preferred=tuple(self.venue_preferred),
            max_return_dev=self.venue_max_return_dev,
            max_level_dev=self.venue_max_level_dev,
            max_gap_days=self.venue_max_gap_days,
            max_instruments=self.venue_max_instruments,
            noise_factor=self.venue_noise_factor,
            noise_sessions=self.venue_noise_sessions,
            max_dev_cap=self.venue_max_dev_cap,
            require_volume=self.venue_require_volume,
        )

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["weights"] = list(self.weights)
        data["excluded_security_types"] = list(self.excluded_security_types)
        data["venue_preferred"] = list(self.venue_preferred)
        data["rotation"] = {k: (list(v) if isinstance(v, tuple) else v) for k, v in asdict(self.rotation).items()}
        data["change_notes"] = list(self.change_notes)
        return data

    def fingerprint(self) -> str:
        return sha256_hex(canonical_bytes(self.as_dict()))[:16]


def _ratio(value: Any, default: Ratio) -> Ratio:
    if value is None:
        return default
    if isinstance(value, dict):
        return Ratio(int(value["zaehler"]), int(value["nenner"]))
    raise ValueError("Schwellen bitte als {zaehler, nenner} angeben")


def _rotation_config(raw: dict) -> RotationConfig:
    d = RotationConfig()
    standard = raw.get("standard", {}) or {}
    variants = raw.get("varianten", {}) or {}
    costs = raw.get("kosten", {}) or {}
    pick = raw.get("auswahl", {}) or {}
    history = raw.get("langhistorie", {}) or {}
    return RotationConfig(
        version=str(raw.get("version", d.version)),
        default_holdings=int(standard.get("aktien", d.default_holdings)),
        default_rhythm=str(standard.get("rhythmus", d.default_rhythm)),
        default_lookback_weeks=int(standard.get("trend_wochen", d.default_lookback_weeks)),
        default_capital=float(standard.get("kapital", d.default_capital)),
        holdings=tuple(int(x) for x in variants.get("aktien", d.holdings)),
        rhythms=tuple(str(x) for x in variants.get("rhythmus", d.rhythms)),
        lookback_weeks=tuple(int(x) for x in variants.get("trend_wochen", d.lookback_weeks)),
        capitals=tuple(float(x) for x in variants.get("kapital", d.capitals)),
        keep_rank_factor=int(raw.get("haltepuffer_faktor", d.keep_rank_factor)),
        band=float(raw.get("anteil_toleranz", d.band)),
        fee_eur=float(costs.get("order_eur", d.fee_eur)),
        spread=float(costs.get("spanne", d.spread)),
        tax_rate=float(costs.get("steuersatz", d.tax_rate)),
        allowance_eur=float(costs.get("freibetrag_eur", d.allowance_eur)),
        min_turnover_usd=float(pick.get("min_umsatz_usd", d.min_turnover_usd)),
        turnover_weeks=int(pick.get("umsatz_wochen", d.turnover_weeks)),
        min_positive_share=float(pick.get("min_anteil_umsatztage", d.min_positive_share)),
        min_coverage=float(pick.get("min_abdeckung", d.min_coverage)),
        max_jump_factor=float(pick.get("max_sprung_faktor", d.max_jump_factor)),
        history_years=int(history.get("jahre", d.history_years)),
        pool_min_turnover_usd=float(history.get("vorauswahl_min_umsatz_usd", d.pool_min_turnover_usd)),
    )


def load_method_config(path: Path | None = None) -> MethodConfig:
    path = path or CONFIG_DIR / "methode.yaml"
    if not path.exists():
        cfg = MethodConfig()
        cfg.validate()
        return cfg
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    q = raw.get("qualitaet", {})
    fenster = raw.get("fenster", {})
    umsatz = raw.get("umsatz", {}) or {}
    platz = raw.get("boersenplatz", {}) or {}
    rotation = _rotation_config(raw.get("umschichtung", {}) or {})
    defaults = MethodConfig()
    cfg = MethodConfig(
        method_version=raw.get("methode_version", defaults.method_version),
        metrics_version=raw.get("kennzahlen_version", defaults.metrics_version),
        ranking_version=raw.get("ranking_version", defaults.ranking_version),
        frequency_version=raw.get("haeufigkeit_version", defaults.frequency_version),
        groups_version=raw.get("gruppen_version", defaults.groups_version),
        reference_model=str(raw.get("ausgangsmodell", defaults.reference_model)),
        previous_method_version=str(raw.get("vorherige_methode_version", defaults.previous_method_version)),
        previous_ranking_version=str(raw.get("vorherige_ranking_version", defaults.previous_ranking_version)),
        previous_last_close=bool(raw.get("vorherige_letzter_schlusskurs", defaults.previous_last_close)),
        calendar_convention=raw.get("kalenderkonvention", defaults.calendar_convention),
        currency_basis=raw.get("waehrungsbasis", defaults.currency_basis),
        min_window=int(fenster.get("min_tage", defaults.min_window)),
        max_window=int(fenster.get("max_tage", defaults.max_window)),
        anchor_max_gap_days=int(raw.get("anker_max_luecke_tage", defaults.anchor_max_gap_days)),
        last_close_max_missed_sessions=int(raw.get("letzter_schlusskurs_max_verpasste_sitzungen", defaults.last_close_max_missed_sessions)),
        weights=tuple(int(w) for w in raw.get("gewichte_gleichmaessigkeit", defaults.weights)),
        min_obs_trend=int(q.get("min_beobachtungen_trend", defaults.min_obs_trend)),
        min_obs_return=int(q.get("min_beobachtungen_rendite", defaults.min_obs_return)),
        min_session_coverage=_ratio(q.get("min_sitzungsabdeckung"), defaults.min_session_coverage),
        min_volume_coverage=_ratio(q.get("min_volumenabdeckung"), defaults.min_volume_coverage),
        volume_basis=str(q.get("volumen_bezug", defaults.volume_basis)),
        tolerated_missing_sessions=int(q.get("fehlende_sitzungen_immer_erlaubt", defaults.tolerated_missing_sessions)),
        volume_every_obs=bool(q.get("volumen_jede_beobachtung", defaults.volume_every_obs)),
        edge_volume_positive=bool(q.get("randvolumen_positiv", defaults.edge_volume_positive)),
        hold_split_windows=bool(q.get("split_im_fenster_zurueckhalten", defaults.hold_split_windows)),
        jump_factor=float(q.get("sprung_faktor", defaults.jump_factor)),
        zero_volume_move=float(q.get("nullumsatz_bewegung", defaults.zero_volume_move)),
        split_mismatch_min_factor=float(q.get("split_pruefung_min_faktor", defaults.split_mismatch_min_factor)),
        sst_rel_tolerance=float(q.get("r2_sst_relativ_toleranz", defaults.sst_rel_tolerance)),
        r2_bound_tolerance=float(q.get("r2_rand_toleranz", defaults.r2_bound_tolerance)),
        impulse_share=float(q.get("impulstag_anteil", defaults.impulse_share)),
        impulse_min_abs_return=float(q.get("impulstag_min_rendite", defaults.impulse_min_abs_return)),
        thin_trading_zero_share=float(q.get("duenner_handel_nullanteil", defaults.thin_trading_zero_share)),
        thin_trading_lookback=int(q.get("duenner_handel_sitzungen", defaults.thin_trading_lookback)),
        unknown_volume_warn_share=float(q.get("volumen_unbekannt_hinweis_anteil", defaults.unknown_volume_warn_share)),
        takeover_jump_min=float(q.get("uebernahme_sprung_min", defaults.takeover_jump_min)),
        takeover_calm_max=float(q.get("uebernahme_ruhe_max", defaults.takeover_calm_max)),
        takeover_calm_sessions=int(q.get("uebernahme_ruhe_sitzungen", defaults.takeover_calm_sessions)),
        turnover_version=str(umsatz.get("version", defaults.turnover_version)),
        turnover_sessions=int(umsatz.get("sitzungen", defaults.turnover_sessions)),
        turnover_min_positive=int(umsatz.get("min_sitzungen_mit_umsatz", defaults.turnover_min_positive)),
        turnover_threshold_usd=float(umsatz.get("schwelle_usd", defaults.turnover_threshold_usd)),
        turnover_very_low_usd=float(umsatz.get("sehr_niedrig_usd", defaults.turnover_very_low_usd)),
        fx_max_age_days=int(umsatz.get("wechselkurs_max_alter_tage", defaults.fx_max_age_days)),
        venue_version=str(platz.get("version", defaults.venue_version)),
        venue_top_n=int(platz.get("plaetze", defaults.venue_top_n)),
        venue_preferred=tuple(str(k) for k in platz.get("bevorzugt", defaults.venue_preferred)),
        venue_max_return_dev=float(platz.get("schwelle_wertentwicklung", defaults.venue_max_return_dev)),
        venue_max_level_dev=float(platz.get("schwelle_endkurs", defaults.venue_max_level_dev)),
        venue_max_gap_days=int(platz.get("max_abstand_tage", defaults.venue_max_gap_days)),
        venue_max_instruments=int(platz.get("max_aktien", defaults.venue_max_instruments)),
        venue_noise_factor=float(platz.get("schwankung_faktor", defaults.venue_noise_factor)),
        venue_noise_sessions=int(platz.get("schwankung_sitzungen", defaults.venue_noise_sessions)),
        venue_max_dev_cap=float(platz.get("schwelle_hoechstens", defaults.venue_max_dev_cap)),
        venue_require_volume=bool(platz.get("nur_mit_umsatz", defaults.venue_require_volume)),
        rotation=rotation,
        previous_rules=_admission_rules(raw.get("vorherige_regeln"), defaults.previous_rules),
        change_notes=tuple(str(t) for t in raw.get("aenderungen_gegenueber_vorversion", defaults.change_notes)),
        excluded_security_types=tuple(raw.get("ausgeschlossene_typen", defaults.excluded_security_types)),
    )
    cfg.validate()
    return cfg


def _admission_rules(raw: Any, default: AdmissionRules) -> AdmissionRules:
    if not raw:
        return default
    if not isinstance(raw, dict):
        raise ValueError("vorherige_regeln bitte als Abschnitt mit Schwellen angeben")
    return AdmissionRules(
        session_coverage=_ratio(raw.get("min_sitzungsabdeckung"), default.session_coverage),
        volume_coverage=_ratio(raw.get("min_volumenabdeckung"), default.volume_coverage),
        volume_basis=str(raw.get("volumen_bezug", default.volume_basis)),
        tolerated_missing_sessions=int(raw.get("fehlende_sitzungen_immer_erlaubt", default.tolerated_missing_sessions)),
        volume_every_obs=bool(raw.get("volumen_jede_beobachtung", default.volume_every_obs)),
        edge_volume_positive=bool(raw.get("randvolumen_positiv", default.edge_volume_positive)),
        hold_split_windows=bool(raw.get("split_im_fenster_zurueckhalten", default.hold_split_windows)),
    )


@dataclass(frozen=True)
class PipelineConfig:
    raw: dict = field(default_factory=dict)

    def get(self, dotted: str, default: Any = None) -> Any:
        node: Any = self.raw
        for part in dotted.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node


def load_pipeline_config(path: Path | None = None) -> PipelineConfig:
    path = path or CONFIG_DIR / "pipeline.yaml"
    if not path.exists():
        return PipelineConfig({})
    return PipelineConfig(yaml.safe_load(path.read_text(encoding="utf-8")) or {})


def load_yaml(name: str) -> Any:
    path = CONFIG_DIR / name
    if not path.exists():
        return None
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def parse_window_days(value: Any, cfg: MethodConfig | None = None) -> int:
    """Validiert eine Fensterangabe; lehnt 0, 91, negative und gebrochene Werte ab."""
    cfg = cfg or MethodConfig()
    if isinstance(value, bool):
        raise ValueError("Zeitraum muss eine ganze Zahl sein")
    if isinstance(value, str):
        text = value.strip()
        if not text.isdigit():
            raise ValueError(f"Ungültiger Zeitraum: {value!r}")
        number = int(text)
    elif isinstance(value, int):
        number = value
    elif isinstance(value, float) and value.is_integer():
        number = int(value)
    else:
        raise ValueError(f"Ungültiger Zeitraum: {value!r}")
    if not (cfg.min_window <= number <= cfg.max_window):
        raise ValueError(f"Zeitraum {number} liegt außerhalb von {cfg.min_window}–{cfg.max_window}")
    return number


LEGACY_MODE_ALIASES = {"return": 0, "mix40": 40, "mix50": 50, "mix60": 60, "consistency": 100}


def parse_weight(value: Any) -> int:
    """Gewicht der Gleichmäßigkeit in Prozent (0,10,…,100); alte Modusnamen als Alias."""
    if isinstance(value, str):
        text = value.strip().lower()
        if text in LEGACY_MODE_ALIASES:
            return LEGACY_MODE_ALIASES[text]
        if not text.isdigit():
            raise ValueError(f"Ungültige Gewichtung: {value!r}")
        value = int(text)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"Ungültige Gewichtung: {value!r}")
    if value not in CANONICAL_WEIGHTS:
        raise ValueError(f"Gewichtung {value} ist nicht in {CANONICAL_WEIGHTS}")
    return value


def parse_policy(value: Any) -> str:
    if value not in POLICIES:
        raise ValueError(f"Vergleichspolitik muss native oder common_trend sein, nicht {value!r}")
    return value
