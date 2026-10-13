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


@dataclass(frozen=True)
class MethodConfig:
    method_version: str = "tr-methode-1.4.0"
    metrics_version: str = "kennzahlen-v1"
    ranking_version: str = "ranking-11w-v1"
    frequency_version: str = "frequency-v1"
    calendar_convention: str = "kalendertage"
    currency_basis: str = "notierungswaehrung_splitbereinigt_ohne_dividenden"
    min_window: int = 1
    max_window: int = 90
    anchor_max_gap_days: int = 7
    weights: tuple[int, ...] = CANONICAL_WEIGHTS
    min_obs_trend: int = 15
    min_obs_return: int = 2
    min_session_coverage: Ratio = Ratio(49, 50)
    min_volume_coverage: Ratio = Ratio(4, 5)
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
    venue_version: str = "boersenplatz-v1"
    venue_top_n: int = 10
    venue_preferred: tuple[str, ...] = ("XETR", "XFRA")
    venue_max_return_dev: float = 0.10
    venue_max_level_dev: float = 0.10
    venue_max_gap_days: int = 4
    venue_max_instruments: int = 600
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

    def validate(self) -> None:
        if tuple(self.weights) != CANONICAL_WEIGHTS:
            raise ValueError("Es sind genau elf Gewichtungen 0,10,…,100 vorgeschrieben")
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
        if self.venue_top_n < 0 or self.venue_max_instruments < 0 or self.venue_max_gap_days < 0:
            raise ValueError("boersenplatz: plaetze, max_aktien und max_abstand_tage dürfen nicht negativ sein")
        if not (0 < self.venue_max_return_dev < 1 and 0 < self.venue_max_level_dev < 1):
            raise ValueError("boersenplatz: Schwellen müssen zwischen 0 und 1 liegen")

    def venue_settings(self):
        from .analytics.venues import VenueSettings

        return VenueSettings(
            top_n=self.venue_top_n,
            preferred=tuple(self.venue_preferred),
            max_return_dev=self.venue_max_return_dev,
            max_level_dev=self.venue_max_level_dev,
            max_gap_days=self.venue_max_gap_days,
            max_instruments=self.venue_max_instruments,
        )

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["weights"] = list(self.weights)
        data["excluded_security_types"] = list(self.excluded_security_types)
        data["venue_preferred"] = list(self.venue_preferred)
        return data

    def fingerprint(self) -> str:
        return sha256_hex(canonical_bytes(self.as_dict()))[:16]


def _ratio(value: Any, default: Ratio) -> Ratio:
    if value is None:
        return default
    if isinstance(value, dict):
        return Ratio(int(value["zaehler"]), int(value["nenner"]))
    raise ValueError("Schwellen bitte als {zaehler, nenner} angeben")


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
    defaults = MethodConfig()
    cfg = MethodConfig(
        method_version=raw.get("methode_version", defaults.method_version),
        metrics_version=raw.get("kennzahlen_version", defaults.metrics_version),
        ranking_version=raw.get("ranking_version", defaults.ranking_version),
        frequency_version=raw.get("haeufigkeit_version", defaults.frequency_version),
        calendar_convention=raw.get("kalenderkonvention", defaults.calendar_convention),
        currency_basis=raw.get("waehrungsbasis", defaults.currency_basis),
        min_window=int(fenster.get("min_tage", defaults.min_window)),
        max_window=int(fenster.get("max_tage", defaults.max_window)),
        anchor_max_gap_days=int(raw.get("anker_max_luecke_tage", defaults.anchor_max_gap_days)),
        weights=tuple(int(w) for w in raw.get("gewichte_gleichmaessigkeit", defaults.weights)),
        min_obs_trend=int(q.get("min_beobachtungen_trend", defaults.min_obs_trend)),
        min_obs_return=int(q.get("min_beobachtungen_rendite", defaults.min_obs_return)),
        min_session_coverage=_ratio(q.get("min_sitzungsabdeckung"), defaults.min_session_coverage),
        min_volume_coverage=_ratio(q.get("min_volumenabdeckung"), defaults.min_volume_coverage),
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
        excluded_security_types=tuple(raw.get("ausgeschlossene_typen", defaults.excluded_security_types)),
    )
    cfg.validate()
    return cfg


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
