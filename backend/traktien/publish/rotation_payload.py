"""Dateien der Umschichtungs-Regel im Datenstand (``rotation/index.bin`` und ``rotation/<Variante>.bin``).

* ``rotation/index.bin``       Regel, Kosten, Vorauswahl und die Kennzahlen aller Varianten
                                (klein; die App lädt sie für den Variantenvergleich)
* ``rotation/<Variante>.bin``  Verlauf (wöchentlich), alle Orders und der Tagesvorschlag einer Variante

Instrumente stehen als Index ``idx`` in ``instruments.bin``. Beträge in Euro sind auf Cent gerundet,
Anteile und Renditen auf sechs signifikante Stellen.
"""

from __future__ import annotations

import math

import numpy as np

from ..analytics import rotation as rot

INDEX_SCHEMA = "tr-rotation/1"
VARIANT_SCHEMA = "tr-rotation-variante/1"
KEY_PATTERN = r"^n\d{1,2}-(monatlich|woechentlich)-w\d{1,2}-k\d{3,7}$"

STAT_MONEY = ("startkapital", "endwert", "endwert_ohne_kosten", "vergleich_endwert", "gebuehren", "spanne", "steuern", "verlusttopf")
STAT_RATIO = ("rendite", "rendite_ohne_kosten", "vergleich_rendite", "rendite_pro_jahr", "vergleich_pro_jahr", "max_rueckgang", "vergleich_max_rueckgang")
STAT_COUNT = ("start_day", "end_day", "tage", "umschichtungen", "orders", "verkaeufe", "kaeufe")


def _money(value) -> float | None:
    if value is None:
        return None
    number = float(value)
    return round(number, 2) + 0.0 if math.isfinite(number) else None  # + 0.0: keine „-0.0“


def _ratio(value, digits: int = 6) -> float | None:
    if value is None:
        return None
    number = float(value)
    if not math.isfinite(number):
        return None
    return float(f"{number:.{digits}g}") + 0.0


def _int(value) -> int | None:
    return None if value is None else int(value)


def variant_stats(result: rot.BacktestResult) -> dict:
    """Kennzahlen einer Variante (gerundet); leer, wenn der Rückblick nicht rechnen konnte."""
    stats = result.stats()
    if not stats:
        return {}
    bench = np.array(result.benchmark, dtype=float)
    if len(bench):
        peak = np.maximum.accumulate(bench)
        stats["vergleich_max_rueckgang"] = float(np.max(1.0 - bench / peak))
    stats["verkaeufe"] = sum(1 for t in result.trades if t.action in ("verkauf", "reduzieren"))
    stats["kaeufe"] = sum(1 for t in result.trades if t.action in ("kauf", "aufstocken"))
    out: dict = {}
    for name in STAT_COUNT:
        out[name] = _int(stats.get(name))
    for name in STAT_MONEY:
        out[name] = _money(stats.get(name))
    for name in STAT_RATIO:
        out[name] = _ratio(stats.get(name))
    return out


class RotationPayloads:
    """Baut die Dateien der Umschichtungs-Regel aus dem Ergebnis eines Laufs."""

    def __init__(self, outcome, snapshot_id: str) -> None:
        self.outcome = outcome
        self.snapshot_id = snapshot_id
        self.idx = outcome.panel_idx if outcome.panel_idx is not None else np.zeros(0, dtype=np.int64)

    def _i(self, row: int) -> int:
        return int(self.idx[int(row)])

    def index(self) -> dict:
        o = self.outcome
        cfg, rule, costs = o.config, o.rule, o.costs
        grid = o.grid if o.grid is not None else np.zeros(0, dtype=np.int64)
        variants = []
        for key in sorted(o.results):
            result = o.results[key]
            v = result.variant
            preview = o.previews.get(key)
            variants.append(
                {
                    "key": key,
                    "aktien": v.holdings,
                    "rhythmus": v.rhythm,
                    "trend_wochen": v.lookback_weeks,
                    "kapital": _money(v.capital),
                    "status": result.status,
                    "kennzahlen": variant_stats(result),
                    "aenderungen_heute": None if preview is None else len(preview.actions),
                    "beschlossen_am": None if preview is None else preview.decision_day,
                    "naechste_entscheidung": None if preview is None else preview.next_decision_day,
                }
            )
        return {
            "schema": INDEX_SCHEMA,
            "snapshot_id": self.snapshot_id,
            "version": rot.VERSION,
            "stichtag": int(o.day),
            "standard": o.default_key,
            "vorauswahl": int(o.pool),
            "raster": {
                "von": int(grid[0]) if len(grid) else None,
                "bis": int(grid[-1]) if len(grid) else None,
                "wochen": int(len(grid)),
                "erste_woche_mit_daten": o.first_week_with_data,
            },
            "hinweis": o.note,
            "langhistorie": {k: int(v) for k, v in (o.history or {}).items()},
            "regel": {
                "aktien": list(cfg.holdings),
                "rhythmus": list(cfg.rhythms),
                "trend_wochen": list(cfg.lookback_weeks),
                "kapital": [_money(c) for c in cfg.capitals],
                "haltepuffer_faktor": cfg.keep_rank_factor,
                "anteil_toleranz": cfg.band,
                "min_umsatz_usd": rule.min_turnover_usd,
                "umsatz_wochen": rule.turnover_weeks,
                "min_anteil_umsatztage": rule.min_positive_share,
                "min_abdeckung": rule.min_coverage,
                "max_sprung_faktor": cfg.max_jump_factor,
                "langhistorie_jahre": cfg.history_years,
                "vorauswahl_min_umsatz_usd": cfg.pool_min_turnover_usd,
            },
            "kosten": {
                "order_eur": costs.fee,
                "spanne": costs.spread,
                "steuersatz": costs.tax_rate,
                "freibetrag_eur": costs.allowance,
            },
            "varianten": variants,
        }

    def variant(self, key: str) -> dict:
        o = self.outcome
        result: rot.BacktestResult = o.results[key]
        preview = o.previews.get(key)
        trades = result.trades
        payload = {
            "schema": VARIANT_SCHEMA,
            "snapshot_id": self.snapshot_id,
            "key": key,
            "status": result.status,
            "kennzahlen": variant_stats(result),
            "verlauf": {
                "tage": [int(d) for d in result.days],
                "depot": [_money(x) for x in result.equity],
                "ohne_kosten": [_money(x) for x in result.equity_gross],
                "vergleich": [_money(x) for x in result.benchmark],
            },
            "umschichtungen": [int(d) for d in result.rebalance_days],
            "orders": {
                "tag": [int(t.day) for t in trades],
                "ausfuehrung": [int(t.exec_day) if t.exec_day is not None else int(t.day) for t in trades],
                "idx": [self._i(t.row) for t in trades],
                "aktion": [t.action for t in trades],
                "wert": [_money(t.value) for t in trades],
                "anteil_vorher": [_ratio(t.weight_before) for t in trades],
                "anteil_nachher": [_ratio(t.weight_after) for t in trades],
                "platz": [_int(t.rank) for t in trades],
                "trend": [_ratio(t.signal) for t in trades],
                "gebuehr": [_money(t.fee) for t in trades],
                "spanne": [_money(t.spread) for t in trades],
                "steuer": [_money(t.tax) for t in trades],
                "gewinn": [_money(t.gain) for t in trades],
            },
            "vorschlag": None if preview is None else self.preview(preview),
        }
        return payload

    def preview(self, p: rot.Preview) -> dict:
        return {
            "tag": int(p.day),
            "beschlossen_am": None if p.decision_day is None else int(p.decision_day),
            "naechste_entscheidung": int(p.next_decision_day),
            "depotwert": _money(p.value),
            "bargeld": _money(p.cash),
            "bestand": {
                "idx": [self._i(h["row"]) for h in p.holdings],
                "stueck": [_ratio(h["shares"], 8) for h in p.holdings],
                "wert": [_money(h["value"]) for h in p.holdings],
                "anteil": [_ratio(h["weight"]) for h in p.holdings],
                "seit": [int(h["entry_day"]) for h in p.holdings],
                "einstand": [_money(h["basis"]) for h in p.holdings],
                "rendite": [_ratio(h["rendite"]) for h in p.holdings],
                "platz": [_int(h["rank"]) for h in p.holdings],
                "trend": [_ratio(h["signal"]) for h in p.holdings],
            },
            "aenderungen": {
                "idx": [self._i(a["row"]) for a in p.actions],
                "aktion": [a["action"] for a in p.actions],
                "anteil_vorher": [_ratio(a["w0"]) for a in p.actions],
                "anteil_nachher": [_ratio(a["w1"]) for a in p.actions],
                "wert": [_money(a["value"]) for a in p.actions],
                "platz": [_int(a["rank"]) for a in p.actions],
                "trend": [_ratio(a["signal"]) for a in p.actions],
                "grund": [a["reason"] for a in p.actions],
            },
            "rangliste": {
                "idx": [self._i(r["row"]) for r in p.ranking],
                "platz": [int(r["rank"]) for r in p.ranking],
                "trend": [_ratio(r["signal"]) for r in p.ranking],
                "umsatz_usd": [_ratio(r["usd"], 8) for r in p.ranking],
                "gehalten": [bool(r["held"]) for r in p.ranking],
            },
        }

    def manifest_summary(self, index: dict) -> dict:
        """Kurzfassung für das Manifest (Kennzahlen der Standardvariante, Dateien)."""
        default = next((v for v in index["varianten"] if v["key"] == index["standard"]), None)
        return {
            "version": index["version"],
            "standard": index["standard"],
            "varianten": len(index["varianten"]),
            "vorauswahl": index["vorauswahl"],
            "raster": index["raster"],
            "langhistorie": index["langhistorie"],
            "standard_status": default["status"] if default else None,
            "standard_kennzahlen": default["kennzahlen"] if default else {},
            "hinweis": index["hinweis"],
            "beschreibung": (
                "Mechanische Regel zur Veranschaulichung (keine Anlageberatung, keine Prognose): monatlich die "
                "Aktien mit der höchsten Kursrendite der letzten Wochen unter den Aktien mit ausreichendem Umsatz "
                "gleich gewichtet halten. Entscheidung zum Freitagsschluss, Ausführung zum Schlusskurs des nächsten "
                "Handelstags. Rückblick mit heutigem TR-Angebot (Überlebende), ohne Dividenden; Kosten und Steuern vereinfacht."
            ),
        }
