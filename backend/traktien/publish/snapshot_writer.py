"""Schreibt einen geprüften Snapshot als statische Dateien (Datenvertrag ``static-api-v1``).

Verzeichnis ``<snapshot_id>/`` mit:

* ``manifest.bin``      Metadaten, Versionen, Abdeckungsbilanz, Prüfungen, Dateihashes
* ``instruments.bin``   vollständiges Universum (auch nicht berechenbare Einträge)
* ``overview.bin``      90 Zeilen je Gewichtung (Spitzenreiter) + Renditesieger + Maximum
* ``frequency.bin``     veröffentlichte Top-10-Fundstellen aller Zellen + Feldgrößen
* ``windows/<h>.bin``   vollständige Kennzahlen und alle Ranglisten eines Fensters
* ``series/<ISIN>.bin`` Kursreihe (verwendete Tageskurse), Lücken, Startanker, Rangmatrix
* ``rotation/index.bin`` Umschichtungs-Regel: Regel, Kosten, Kennzahlen aller Varianten
* ``rotation/<Variante>.bin`` Verlauf, Orders und Tagesvorschlag einer Variante
* ``fx.bin``            Euro-Referenzkurse der letzten 100 Tage (ab 1.9, für die Musterdepots in USD/EUR)

Jede Datei ist ein TRA1-Container (gzip, optional AES-GCM mit Pfad als AAD).
Vergleichsmengen: ``v0`` = 0/100 auf V (native), ``u`` = alle elf Gewichte auf U.
native(w=0) → v0; native(w≥10) → u[w]; common_trend(w) → u[w].
``v0l`` = Ranking 2: 0/100 auf V ∩ L (Ø Tagesumsatz ≥ Schwelle), gleiche Renditen wie ``v0``.
``ul`` = Gruppe B (ab 1.4): alle elf Gewichte auf U ∩ L mit eigenen Perzentilen (Vergleichsmenge
der Gruppe); natives 0/100 der Gruppe B ist ``v0l``.
"""

from __future__ import annotations

import base64
import io
import shutil
import tarfile
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from ..analytics.codes import RETURN_PUBLISHABLE, Status, code_tables
from ..analytics.engine import SnapshotComputation
from ..analytics.frequency import aggregate_frequency
from ..config import CANONICAL_WEIGHTS, MethodConfig
from ..util import crypto
from ..util.jsonio import atomic_write_bytes, canonical_bytes, dumps, sha256_hex
from ..util.timeutil import day_to_iso
from ..util.log import get_logger
from .rotation_payload import RotationPayloads

LOG = get_logger(__name__)

SCHEMA = "static-api-v1"
HEAD_LIMIT = 50  # Kopfdatei je Fenster: erste 50 Plätze jeder der zwölf Ranglisten
FX_DAYS = 100  # Wechselkurse für Musterdepots: bis 90 Kalendertage zurück plus Puffer für Feiertage
RANK_COLUMNS = ["v0"] + [f"u{w}" for w in CANONICAL_WEIGHTS] + ["v0l"] + [f"ul{w}" for w in CANONICAL_WEIGHTS]  # 24 Spalten je Fenster


@dataclass
class InstrumentMeta:
    isin: str
    name: str
    tr_name: str
    aliases: list[str] = field(default_factory=list)
    ticker: str | None = None
    symbol: str | None = None
    exchange_key: str | None = None
    exchange_name: str | None = None
    mic: str | None = None
    tz: str | None = None
    calendar: str | None = None
    currency: str | None = None
    price_unit: str | None = None
    unit_factor: float = 1.0
    instrument_type: str = "unklar"
    identity_status: str = "offen"
    identity_reason: str | None = None
    provider: str | None = None
    data_revision: int | None = None
    fetched_at: str | None = None
    events: list[dict] = field(default_factory=list)
    sessions: np.ndarray | None = None
    ohlc: dict[str, np.ndarray] | None = None  # days, open, high, low, close_raw je Tag (für Kerzen/Tooltip)
    quote_days: list[int] = field(default_factory=list)  # Schlusskurse aus der Kursmeldung (ab 1.5.4)
    provisional_day: int | None = None  # Zwischenstand (ab 1.8): Tag des vorläufigen Kurses
    provisional_time: str | None = None  # Zeitpunkt dieses Kurses (UTC, ISO)
    provisional_final: bool = False  # Sitzung dieses Tages laut Börsenkalender bereits beendet


def _r(value) -> float | None:
    if value is None:
        return None
    number = float(value)
    return number if np.isfinite(number) else None


_INF = float("inf")


def _r_list(values) -> list[float | None]:
    """Wie ``[_r(x) for x in values]``, nur schneller (ab 1.12): gleiche Zahlen, nicht endliche als ``None``."""
    return [x if (x == x and x != _INF and x != -_INF) else None for x in np.asarray(values, dtype=np.float64).tolist()]


def _sig(value, digits: int = 6) -> float | None:
    """Anzeigewert mit begrenzten signifikanten Stellen (nur für reine Anzeigekennzahlen)."""
    if value is None:
        return None
    number = float(value)
    if not np.isfinite(number):
        return None
    return float(f"{number:.{digits}g}")


def _bits(mask: np.ndarray) -> str:
    return base64.b64encode(np.packbits(mask.astype(np.uint8), bitorder="little").tobytes()).decode("ascii")


class SnapshotWriter:
    def __init__(
        self,
        comp: SnapshotComputation,
        metas: list[InstrumentMeta],
        cfg: MethodConfig,
        *,
        snapshot_id: str,
        key: crypto.KeyMaterial | None,
    ) -> None:
        if [m.isin for m in metas] != comp.isins:
            raise ValueError("Metadaten passen nicht zur Instrumentreihenfolge")
        self.comp = comp
        self.metas = metas
        self.cfg = cfg
        self.snapshot_id = snapshot_id
        self.key = key
        self.hashes: dict[str, str] = {}
        self.sizes: dict[str, int] = {}
        self._rank_matrix = self._build_rank_matrix()

    # ------------------------------------------------------------ Hilfen

    def _write(self, root: Path, relative: str, value) -> None:
        plain = dumps(value).encode("utf-8")
        aad = f"snapshots/{self.snapshot_id}/{relative}"
        blob = crypto.pack(plain, self.key, aad)
        atomic_write_bytes(root / relative, blob, durable=False)
        self.hashes[relative] = sha256_hex(plain)
        self.sizes[relative] = len(blob)

    def _build_rank_matrix(self) -> np.ndarray:
        comp = self.comp
        n = comp.n_instruments
        matrix = np.zeros((n, 90, len(RANK_COLUMNS)), dtype=np.uint16)
        for col, h in enumerate(comp.windows):
            window = comp.rankings[h]
            group_b = window.group_b
            rankings = [window.native0] + [window.trend[w] for w in CANONICAL_WEIGHTS] + [window.native0_liquid]
            rankings += [group_b.trend[w] if group_b is not None else None for w in CANONICAL_WEIGHTS]
            for k, ranking in enumerate(rankings):
                if ranking is not None and ranking.size:
                    matrix[ranking.order, col, k] = np.arange(1, ranking.size + 1, dtype=np.uint16)
        return matrix

    def _empty_reason(self, h: int, cohort: str) -> str:
        comp = self.comp
        window = comp.rankings[h]
        if window.native0.size == 0:
            return "keine_vergleichbare_aktie"
        if cohort == "v0":
            return "keine_vergleichbare_aktie"
        group = window
        if cohort in ("v0l", "ul"):
            group = window.group_b
            if group is None or group.native0.size == 0:
                return "keine_aktie_mit_umsatz"
            if cohort == "v0l":
                return "keine_aktie_mit_umsatz"
        col = h - 1
        n_obs = comp.n_obs[group.v_idx, col]
        if np.all(n_obs < self.cfg.min_obs_trend):
            return "zu_wenig_tagesdaten"
        return "kein_aufwaertskandidat"

    # ---------------------------------------------------------- Inhalte

    def instruments_payload(self) -> dict:
        comp = self.comp
        publishable = [int(s) for s in RETURN_PUBLISHABLE]
        v_mask = np.isin(comp.status, publishable)
        u_mask = comp.status == Status.TREND_BEWERTBAR
        r_v = np.where(v_mask, comp.r, -np.inf)
        best_h: list[int | None] = []
        best_r: list[float | None] = []
        for i in range(comp.n_instruments):
            if v_mask[i].any():
                col = int(np.argmax(r_v[i]))
                best_h.append(col + 1)
                best_r.append(_r(comp.r[i, col]))
            else:
                best_h.append(None)
                best_r.append(None)
        level = _instrument_level(comp)
        last_close, last_day = [], []
        for i in range(comp.n_instruments):
            obs = comp.observed.get(i)
            if obs is not None and len(obs.days):
                last_close.append(_r(obs.close[-1]))
                last_day.append(int(obs.days[-1]))
            else:
                last_close.append(None)
                last_day.append(None)
        m = self.metas
        return {
            "schema": "tr-instruments/1",
            "snapshot_id": self.snapshot_id,
            "count": comp.n_instruments,
            "isin": comp.isins,
            "name": [x.name for x in m],
            "tr_name": [x.tr_name for x in m],
            "aliases": [x.aliases for x in m],
            "ticker": [x.ticker for x in m],
            "symbol": [x.symbol for x in m],
            "exchange_key": [x.exchange_key for x in m],
            "exchange": [x.exchange_name for x in m],
            "mic": [x.mic for x in m],
            "tz": [x.tz for x in m],
            "calendar": [x.calendar for x in m],
            "currency": [x.currency for x in m],
            "price_unit": [x.price_unit for x in m],
            "type": [x.instrument_type for x in m],
            "identity": [x.identity_status for x in m],
            "identity_reason": [x.identity_reason for x in m],
            "pre_status": comp.pre_status.astype(int).tolist(),
            "level_status": level.tolist(),
            "warnings": comp.warnings.astype(int).tolist(),
            "last_close": last_close,
            "last_close_day": last_day,
            "has_series": [bool(comp.has_history[i] and i in comp.observed) for i in range(comp.n_instruments)],
            "v_bits": [_bits(v_mask[i]) for i in range(comp.n_instruments)],
            "u_bits": [_bits(u_mask[i]) for i in range(comp.n_instruments)],
            "best_h": best_h,
            "best_r": best_r,
            "turnover": self.turnover_columns(),
            "venue": self.venue_columns(),
        }

    def venue_columns(self) -> dict | None:
        """Zweiter Börsenplatz je geprüfter Aktie (dünn besetzt: nur geprüfte Indizes)."""
        check = self.comp.venue
        if check is None:
            return None
        keys = ("idx", "status", "symbol", "exchange_key", "exchange", "currency", "price_unit", "level", "level_flag", "end_day", "end_price", "noise", "limit_r", "limit_l")
        out: dict[str, list] = {k: [] for k in keys}
        for idx in sorted(check.results):
            res = check.results[idx]
            out["idx"].append(int(idx))
            out["status"].append(res.status)
            out["symbol"].append(res.symbol)
            out["exchange_key"].append(res.exchange_key)
            out["exchange"].append(res.exchange_name)
            out["currency"].append(res.currency)
            out["price_unit"].append(res.price_unit)
            out["level"].append(_r(res.level))
            out["level_flag"].append(bool(res.level_flagged))
            out["end_day"].append(res.end_day)
            out["end_price"].append(_r(res.end_price))
            out["noise"].append(_r(res.noise))  # ab boersenplatz-v3: übliche Tagesschwankung und angewandte Schwellen
            out["limit_r"].append(_r(res.limit_return))
            out["limit_l"].append(_r(res.limit_level))
        return out

    def venue_window(self, col: int, members: np.ndarray) -> dict | None:
        """Abgleich je Aktie für ein Fenster (nur geprüfte Aktien dieser Datei)."""
        check = self.comp.venue
        if check is None:
            return None
        wanted = set(int(i) for i in members.tolist())
        out: dict[str, list] = {k: [] for k in ("idx", "status", "r", "dev", "d0", "d1", "p0", "p1")}
        for idx in sorted(check.results):
            pair = check.results[idx].pairs.get(col)
            if pair is None or idx not in wanted:
                continue
            out["idx"].append(int(idx))
            out["status"].append(pair.status)
            out["r"].append(_r(pair.r_alt))
            out["dev"].append(_r(pair.dev))
            out["d0"].append(pair.d0)
            out["d1"].append(pair.d1)
            out["p0"].append(_r(pair.p0))
            out["p1"].append(_r(pair.p1))
        return out

    def _venue_pair(self, idx: int, col: int) -> dict | None:
        """Abgleich einer Aktie in einem Fenster (für die Siegerzeilen der Übersicht)."""
        check = self.comp.venue
        result = check.results.get(int(idx)) if check is not None else None
        pair = result.pairs.get(col) if result is not None else None
        if pair is None:
            return None
        return {"status": pair.status, "r": _r(pair.r_alt), "dev": _r(pair.dev), "d0": pair.d0, "d1": pair.d1, "p0": _r(pair.p0), "p1": _r(pair.p1)}

    def venue_summary(self) -> dict | None:
        """Manifest-Abschnitt: Regeln und Zählungen des Abgleichs mit einem zweiten Börsenplatz."""
        check = self.comp.venue
        if check is None:
            return None
        settings = check.settings
        return {
            "version": check.version,
            "plaetze": settings.top_n,
            "bevorzugt": list(settings.preferred),
            "schwelle_wertentwicklung": settings.max_return_dev,
            "schwelle_endkurs": settings.max_level_dev,
            "max_abstand_tage": settings.max_gap_days,
            "max_aktien": settings.max_instruments,
            "schwankung_faktor": settings.noise_factor,
            "schwankung_sitzungen": settings.noise_sessions,
            "schwelle_hoechstens": settings.max_dev_cap,
            "nur_mit_umsatz": settings.require_volume,
            "beschreibung": "Aktien unter den ersten Plätzen von Ranking 1 oder 2 werden in allen ihren Zeiträumen mit einem zweiten Börsenplatz derselben ISIN verglichen (Schlusskurse dieses Platzes, in Referenzwährung umgerechnet). Nur ein Hinweis: Rendite und Rang bleiben unverändert.",
            "hinweis": check.note,
            "abgebrochen": check.aborted,
            "anzahl": check.counts(),
            "auswertung": check.diagnostics(),
        }

    def turnover_columns(self) -> dict:
        """Ø Tagesumsatz je Instrument (spaltenweise, Index = Instrument)."""
        comp = self.comp
        rows = comp.turnover or []
        return {
            "status": [t.status for t in rows],
            "usd": [_sig(t.avg_usd, 8) for t in rows],
            "local": [_sig(t.avg_local, 8) for t in rows],
            "currency": [t.currency for t in rows],
            "sessions": [t.sessions for t in rows],
            "with_data": [t.with_data for t in rows],
            "positive": [t.positive for t in rows],
            "first": [t.first_day for t in rows],
            "last": [t.last_day for t in rows],
            "fx_first": [t.fx_first_day for t in rows],
            "fx_last": [t.fx_last_day for t in rows],
            "liquid": [bool(x) for x in comp.liquid.tolist()] if len(comp.liquid) else [False] * comp.n_instruments,
        }

    def turnover_summary(self) -> dict:
        """Manifest-Abschnitt: Definition, Wechselkursquelle mit Datenzeit und Zählungen."""
        comp, cfg = self.comp, self.cfg
        counts: dict[str, int] = {}
        for t in comp.turnover or []:
            counts[t.status] = counts.get(t.status, 0) + 1
        fx = comp.fx
        very_low = sum(1 for t in comp.turnover or [] if t.determined and t.avg_usd < cfg.turnover_very_low_usd)
        return {
            "version": cfg.turnover_version,
            "sitzungen": cfg.turnover_sessions,
            "min_sitzungen_mit_umsatz": cfg.turnover_min_positive,
            "schwelle_usd": cfg.turnover_threshold_usd,
            "sehr_niedrig_usd": cfg.turnover_very_low_usd,
            "berechnung": "je Sitzung Schlusskurs × gemeldetes Volumen (splitbereinigt, gleiche Notierung), arithmetischer Mittelwert über die Sitzungen mit Daten; fehlende Sitzungen zählen nicht als null",
            "wechselkurse": {
                "quelle": fx.source if fx else None,
                "url": fx.url if fx else None,
                "abgerufen_utc": fx.fetched_at if fx else None,
                "erster_kurstag": iso_or_none(fx.first_day) if fx else None,
                "letzter_kurstag": iso_or_none(fx.last_day) if fx else None,
                "waehrungen": fx.currencies if fx else [],
                "max_alter_tage": fx.max_age_days if fx else cfg.fx_max_age_days,
                "hinweis": "Indikative Umrechnung nur für den Umsatzfilter; Kursrenditen bleiben in Notierungswährung.",
            },
            "anzahl": {
                "status": dict(sorted(counts.items())),
                "aufgenommen": int(comp.liquid.sum()) if len(comp.liquid) else 0,
                "sehr_niedrig": very_low,
            },
        }

    def window_payload(self, h: int, limit: int | None = None) -> dict:
        """Fensterdaten. ``limit`` = Kopfdatei mit den ersten Plätzen jeder Rangliste;
        ``None`` = vollständige Datei mit allen Mitgliedern von V, allen Ranglisten und Status.

        Perzentile werden als exakte doppelte Durchschnittsränge veröffentlicht; die App
        berechnet daraus Perzentile und Scores mit identischer Operationsfolge.
        """
        comp = self.comp
        col = h - 1
        window = comp.rankings[h]
        rankings = {"v0": window.native0, **{f"u{w}": window.trend[w] for w in CANONICAL_WEIGHTS}}
        liquid = window.native0_liquid
        if liquid is not None:
            rankings["v0l"] = liquid
        group_b = window.group_b
        if group_b is not None:
            rankings.update({f"ul{w}": group_b.trend[w] for w in CANONICAL_WEIGHTS})
        if limit is None:
            members = window.v_idx
        else:
            chosen: set[int] = set()
            for ranking in rankings.values():
                chosen.update(ranking.order[:limit].tolist())
            members = np.array(sorted(chosen), dtype=np.int64)
        v_pos = {int(idx): k for k, idx in enumerate(window.v_idx.tolist())}
        u_pos = {int(idx): k for k, idx in enumerate(window.u_idx.tolist())}
        rows = [v_pos[int(i)] for i in members.tolist()]
        a_rv = [int(window.ar2_r_v[p]) for p in rows]
        a_gu = [int(window.ar2_g_u[u_pos[int(i)]]) if int(i) in u_pos else None for i in members.tolist()]
        a_ru = [int(window.ar2_r_u[u_pos[int(i)]]) if int(i) in u_pos else None for i in members.tolist()]
        # Gruppe B: doppelte Durchschnittsränge innerhalb V ∩ L bzw. U ∩ L (eigene Perzentile)
        bv_pos = {int(idx): k for k, idx in enumerate(group_b.v_idx.tolist())} if group_b is not None else {}
        bu_pos = {int(idx): k for k, idx in enumerate(group_b.u_idx.tolist())} if group_b is not None else {}
        a_rvl = [int(group_b.ar2_r_v[bv_pos[int(i)]]) if int(i) in bv_pos else None for i in members.tolist()]
        a_gul = [int(group_b.ar2_g_u[bu_pos[int(i)]]) if int(i) in bu_pos else None for i in members.tolist()]
        a_rul = [int(group_b.ar2_r_u[bu_pos[int(i)]]) if int(i) in bu_pos else None for i in members.tolist()]

        def cut(values: np.ndarray) -> list[int]:
            return (values if limit is None else values[:limit]).astype(int).tolist()

        def ties(ranking) -> list[int]:
            positions = ranking.tie_positions
            if limit is not None:
                positions = positions[positions < limit]
            return positions.astype(int).tolist()

        payload = {
            "schema": "tr-window/1",
            "snapshot_id": self.snapshot_id,
            "h": h,
            "part": "vollstaendig" if limit is None else f"kopf_{limit}",
            "cutoff_day": comp.cutoff_day,
            "target_start_day": int(comp.target_start[col]),
            "counts": {
                "V": int(len(window.v_idx)),
                "U": int(len(window.u_idx)),
                "L": liquid.size if liquid is not None else 0,
                "UL": int(len(group_b.u_idx)) if group_b is not None else 0,
            },
            "m": {
                "idx": members.astype(int).tolist(),
                "start": comp.start_day[members, col].astype(int).tolist(),
                "n": comp.n_obs[members, col].astype(int).tolist(),
                "n_exp": comp.n_exp[members, col].astype(int).tolist(),
                "r": _r_list(comp.r[members, col]),
                "p0": _r_list(comp.p0[members, col]),
                "p1": _r_list(comp.p1[members, col]),
                "r2": _r_list(comp.r2[members, col]),
                "slope": [_sig(x) for x in comp.slope_pct[members, col]],
                "noise": [_sig(x) for x in comp.noise_pct[members, col]],
                "mdd": [_sig(x) for x in comp.mdd[members, col]],
                "up": comp.ups[members, col].astype(int).tolist(),
                "vol": [_sig(x, 4) for x in comp.vol_cov[members, col]],
                "wf": comp.wflags[members, col].astype(int).tolist(),
                "a_rv": a_rv,
                "a_gu": a_gu,
                "a_ru": a_ru,
                "a_rvl": a_rvl,
                "a_gul": a_gul,
                "a_rul": a_rul,
            },
            "orders": {
                "v0": cut(window.native0.order),
                "u": {str(w): cut(window.trend[w].order) for w in CANONICAL_WEIGHTS},
                "v0l": cut(liquid.order) if liquid is not None else [],
                "ul": {str(w): cut(group_b.trend[w].order) for w in CANONICAL_WEIGHTS} if group_b is not None else {},
            },
            "ties": {
                "v0": ties(window.native0),
                "u": {str(w): ties(window.trend[w]) for w in CANONICAL_WEIGHTS},
                "v0l": ties(liquid) if liquid is not None else [],
                "ul": {str(w): ties(group_b.trend[w]) for w in CANONICAL_WEIGHTS} if group_b is not None else {},
            },
        }
        payload["xv"] = self.venue_window(col, members)
        if limit is None:
            payload["status_b64"] = base64.b64encode(comp.status[:, col].astype(np.uint8).tobytes()).decode("ascii")
        return payload

    def overview_payload(self) -> dict:
        comp = self.comp
        rows_v0 = []
        rows_u: dict[str, list] = {str(w): [] for w in CANONICAL_WEIGHTS}
        rows_v0l = []
        rows_ul: dict[str, list] = {str(w): [] for w in CANONICAL_WEIGHTS}
        counts_v, counts_u, counts_l, counts_ul = [], [], [], []
        for h in comp.windows:
            col = h - 1
            window = comp.rankings[h]
            group_b = window.group_b
            counts_v.append(window.native0.size)
            counts_u.append(int(len(window.u_idx)))
            counts_l.append(window.native0_liquid.size if window.native0_liquid is not None else 0)
            counts_ul.append(int(len(group_b.u_idx)) if group_b is not None else 0)
            rows_v0.append(self._row(h, col, window.native0, "v0"))
            for w in CANONICAL_WEIGHTS:
                rows_u[str(w)].append(self._row(h, col, window.trend[w], "u"))
            if group_b is not None:
                rows_v0l.append(self._row(h, col, group_b.native0, "v0l"))
                for w in CANONICAL_WEIGHTS:
                    rows_ul[str(w)].append(self._row(h, col, group_b.trend[w], "ul"))
        return {
            "schema": "tr-overview/1",
            "snapshot_id": self.snapshot_id,
            "cutoff_day": comp.cutoff_day,
            "counts": {"V": counts_v, "U": counts_u, "L": counts_l, "UL": counts_ul},
            "v0": rows_v0,
            "u": rows_u,
            # Gruppe B (ab 1.4): Spitzenreiter je Zeitraum und Gewichtung mit eigener Vergleichsmenge
            "v0l": rows_v0l,
            "ul": rows_ul,
            "winners": self._winner_rows(comp.winners),
            "overall_max": self._overall(comp.overall_max),
            "winners_l": self._winner_rows(comp.winners_liquid),
            "overall_max_l": self._overall(comp.overall_max_liquid),
            # Identische Kursfenster (ab 1.5): gleicher Wert = gleicher ISIN-/Startdatumsbestand = gleiche Rangliste
            "same_set": self.identical_sets(),
        }

    def _winner_rows(self, rows) -> list[dict]:
        comp = self.comp
        out = []
        for row in rows:
            col = row.h - 1
            out.append(
                {
                    "h": row.h,
                    "M": row.cohort_size,
                    "tie": row.tie,
                    "all_negative": row.all_negative,
                    "empty": row.empty_reason,
                    "entries": [
                        {
                            "idx": e["idx"],
                            "r": _r(e["r"]),
                            "start": e["start_day"],
                            "end": e["end_day"],
                            "p0": _r(comp.p0[e["idx"], col]),
                            "p1": _r(comp.p1[e["idx"], col]),
                            "n": int(comp.n_obs[e["idx"], col]),
                            "wf": int(comp.wflags[e["idx"], col]),
                            "xv": self._venue_pair(e["idx"], col),
                        }
                        for e in row.entries
                    ],
                }
            )
        return out

    def _overall(self, overall: dict) -> dict:
        if not overall:
            return {"tie": False, "pairs_evaluated": 0, "entries": []}
        return {
            "tie": overall["tie"],
            "pairs_evaluated": overall["pairs_evaluated"],
            "entries": [
                {"idx": e["idx"], "h": e["h"], "r": _r(e["r"]), "start": e["start_day"], "end": e["end_day"], "same_h": e.get("same_effective_h", [])}
                for e in overall["entries"]
            ],
        }

    def _row(self, h: int, col: int, ranking, cohort: str) -> dict:
        comp = self.comp
        if ranking.size == 0:
            return {"h": h, "M": 0, "empty": self._empty_reason(h, cohort)}
        idx = int(ranking.order[0])
        tied = bool(len(ranking.tie_positions) and int(ranking.tie_positions[0]) == 0)
        return {
            "h": h,
            "M": ranking.size,
            "idx": idx,
            "r": _r(comp.r[idx, col]),
            "score": _r(ranking.scores[0]),
            "r2": _r(comp.r2[idx, col]),
            "start": int(comp.start_day[idx, col]),
            "n": int(comp.n_obs[idx, col]),
            "tie": tied,
            "sole": ranking.size == 1,
        }

    def frequency_payload(self) -> dict:
        comp = self.comp

        def occurrences(rank_getter) -> dict:
            out = {"h": [], "rank": [], "idx": [], "score": [], "r": [], "start": []}
            for h in comp.windows:
                ranking = rank_getter(h)
                if ranking is None:
                    continue
                for position in range(min(10, ranking.size)):
                    idx = int(ranking.order[position])
                    out["h"].append(h)
                    out["rank"].append(position + 1)
                    out["idx"].append(idx)
                    out["score"].append(_r(ranking.scores[position]))
                    out["r"].append(_r(comp.r[idx, h - 1]))
                    out["start"].append(int(comp.start_day[idx, h - 1]))
            return out

        v0 = occurrences(lambda h: comp.rankings[h].native0)
        u = {str(w): occurrences(lambda h, w=w: comp.rankings[h].trend[w]) for w in CANONICAL_WEIGHTS}
        v0l = occurrences(lambda h: comp.rankings[h].native0_liquid)
        has_b = all(comp.rankings[h].group_b is not None for h in comp.windows)
        ul = {str(w): occurrences(lambda h, w=w: comp.rankings[h].group_b.trend[w]) for w in CANONICAL_WEIGHTS} if has_b else {}

        def reference(windows) -> object:
            return aggregate_frequency(
                windows,
                policy="native",
                weights=CANONICAL_WEIGHTS,
                window_days=comp.windows,
                top_k=10,
                r_matrix=comp.r,
                start_matrix=comp.start_day,
                cutoff_day=comp.cutoff_day,
                isin_of=comp.isin_of,
            )

        def reference_payload(result) -> dict:
            return {
                "policy": "native",
                "weights": "all",
                "top_k": 10,
                "E": result.valid_cells,
                "cells": result.theoretical_cells,
                "entries": [
                    {
                        "idx": e.idx,
                        "n1": e.n1,
                        "n3": e.n3,
                        "n10": e.n10,
                        "A": e.available_cells,
                        "H": e.distinct_windows_k,
                        "W": e.distinct_weights_k,
                        "dew": e.distinct_effective_windows_k,
                    }
                    for e in result.entries[:200]
                ],
            }

        default = reference(comp.rankings)
        default_b = reference({h: comp.rankings[h].group_b for h in comp.windows}) if has_b else None
        return {
            "schema": "tr-frequency/1",
            "snapshot_id": self.snapshot_id,
            "aggregation_version": self.cfg.frequency_version,
            "cutoff_day": comp.cutoff_day,
            "M": {
                "v0": [comp.rankings[h].native0.size for h in comp.windows],
                "u": [int(len(comp.rankings[h].u_idx)) for h in comp.windows],
                "v0l": [comp.rankings[h].native0_liquid.size for h in comp.windows],
                "ul": [int(len(comp.rankings[h].group_b.u_idx)) for h in comp.windows] if has_b else [],
            },
            "occ": {"v0": v0, "u": u, "v0l": v0l, "ul": ul},
            "universe": {
                "v0": "Alle Aktien mit veröffentlichter Kursrendite (Menge V), ohne Umsatzfilter",
                "u": "Gleichmäßig gestiegene Aktien (Menge U ⊆ V), ohne Umsatzfilter",
                "v0l": f"Aktien aus V mit Ø Tagesumsatz ≥ {self.cfg.turnover_threshold_usd / 1e6:g} Mio. USD (Ranking 2, Gruppe B)",
                "ul": f"Gleichmäßig gestiegene Aktien mit Ø Tagesumsatz ≥ {self.cfg.turnover_threshold_usd / 1e6:g} Mio. USD (Gruppe B, U ∩ L); Perzentile innerhalb der Gruppe",
            },
            # Tatsächliche Startsitzung je Börsenkalender und Zeitraum 1–90 (gleiche Regel wie der Rechenkern)
            "starts": self.calendar_starts(),
            # Identische Kursfenster (frequency-v2): je Vergleichsmenge der kleinste Zeitraum mit genau demselben
            # Bestand aus ISIN und tatsächlichem Startdatum (Ende = Stichtag). Gleicher Wert = gleiche Rangliste.
            "same_set": self.identical_sets(),
            "rules": {
                "zelle": "(snapshot, cohort_policy, h, w); je Zelle zählt eine ISIN höchstens einmal",
                "nenner_E": "Zahl der gültigen Zellen der Auswahl (veröffentlichtes Ranking mit mindestens einer Aktie)",
                "A_i": "Zahl der ausgewählten Zellen, in denen die Aktie einen gültigen Rang besitzt",
                "sortierung_einzeln": {"10": "N10,N3,N1,ISIN", "3": "N3,N1,N10,ISIN", "1": "N1,N3,N10,ISIN"},
                "sortierung_alle": {"10": "N10,H10,N3,N1,ISIN", "3": "N3,H3,N1,N10,ISIN", "1": "N1,H1,N3,N10,ISIN"},
                "sortierung_zeitraeume": "H_K,N_K,N1,ISIN",
            },
            "server_reference": reference_payload(default),
            "server_reference_b": reference_payload(default_b) if default_b is not None else None,
        }

    def identical_sets(self) -> dict[str, list[int]]:
        """Je Vergleichsmenge (v0 = V, u = U, v0l = V ∩ L, ul = U ∩ L) und Zeitraum h der kleinste Zeitraum
        mit identischem Bestand aus (ISIN, tatsächlichem Startdatum). Bei leerer Menge der Zeitraum selbst."""
        cached = getattr(self, "_identical_sets", None)
        if cached is not None:
            return cached
        self._identical_sets = self._compute_identical_sets()
        return self._identical_sets

    def _compute_identical_sets(self) -> dict[str, list[int]]:
        comp = self.comp

        def representative(members_of) -> list[int]:
            first: dict[bytes, int] = {}
            out: list[int] = []
            for h in comp.windows:
                members = np.asarray(members_of(h), dtype=np.int64)
                if len(members) == 0:
                    out.append(h)
                    continue
                key = members.tobytes() + b"|" + comp.start_day[members, h - 1].astype(np.int64).tobytes()
                out.append(first.setdefault(key, h))
            return out

        sets = {
            "v0": representative(lambda h: comp.rankings[h].v_idx),
            "u": representative(lambda h: comp.rankings[h].u_idx),
        }
        if all(comp.rankings[h].group_b is not None for h in comp.windows):
            sets["v0l"] = representative(lambda h: comp.rankings[h].group_b.v_idx)
            sets["ul"] = representative(lambda h: comp.rankings[h].group_b.u_idx)
        return sets

    def calendar_starts(self) -> dict[str, list[int | None]]:
        """Startsitzung je Börsenkalender für die Zeiträume 1–90 (None = keine Sitzung in Reichweite)."""
        from ..analytics.windows import expected_start_sessions

        out: dict[str, list[int | None]] = {}
        for meta in self.metas:
            code = meta.calendar
            if not code or code in out or meta.sessions is None or not len(meta.sessions):
                continue
            out[code] = expected_start_sessions(meta.sessions, self.comp.cutoff_day, range(1, 91), self.cfg.anchor_max_gap_days)
        return dict(sorted(out.items()))

    def series_payload(self, i: int) -> dict | None:
        comp = self.comp
        obs = comp.observed.get(i)
        if obs is None or len(obs.days) == 0:
            return None
        meta = self.metas[i]
        starts = comp.start_day[i]
        valid_starts = starts[starts >= 0]
        first = int(valid_starts.min()) if len(valid_starts) else comp.cutoff_day - 97
        first = min(first, comp.cutoff_day - 97)
        mask = obs.days >= first
        days = obs.days[mask]
        close = obs.close[mask]
        volume = obs.volume[mask]
        ohlc = meta.ohlc or {}
        o = h_ = l_ = c_raw = None
        complete = False
        if ohlc and len(ohlc.get("days", [])):
            lookup = {int(d): k for k, d in enumerate(ohlc["days"].tolist())}
            pos = [lookup.get(int(d)) for d in days.tolist()]

            def pick(name):
                arr = ohlc.get(name)
                if arr is None:
                    return [None] * len(pos)
                return [(_sig(arr[p], 8) if p is not None else None) for p in pos]

            o, h_, l_, c_raw = pick("open"), pick("high"), pick("low"), pick("close_raw")
            complete = all(x is not None for x in o + h_ + l_)
        gaps = []
        if meta.sessions is not None:
            expected = meta.sessions[(meta.sessions >= first) & (meta.sessions <= comp.cutoff_day)]
            present = set(days.tolist())
            gaps = [int(d) for d in expected.tolist() if d not in present]
        ranks = self._rank_matrix[i].astype("<u2").tobytes()
        return {
            "schema": "tr-series/1",
            "snapshot_id": self.snapshot_id,
            "isin": meta.isin,
            "listing": {
                "symbol": meta.symbol,
                "exchange": meta.exchange_name,
                "mic": meta.mic,
                "tz": meta.tz,
                "currency": meta.currency,
                "price_unit": meta.price_unit,
                "unit_factor": meta.unit_factor,
                "calendar": meta.calendar,
            },
            "price_basis": "split_adjusted_close",
            "resolution": "daily",
            "source": {"provider": meta.provider, "fetched_at": meta.fetched_at, "revision": meta.data_revision},
            "d": days.astype(int).tolist(),
            "c": _r_list(close),
            "v": [(int(x) if np.isfinite(x) and float(x).is_integer() else _sig(x, 8)) for x in volume],
            "o": o,
            "h": h_,
            "l": l_,
            "c_raw": c_raw,
            "ohlc_complete": complete,
            "gaps": gaps,
            "window_start": [int(s) if s >= 0 else None for s in starts.tolist()],
            "window_status": comp.status[i].astype(int).tolist(),
            "rank_columns": RANK_COLUMNS,
            "ranks_b64": base64.b64encode(ranks).decode("ascii"),
            "events": meta.events,
            "quote_days": [d for d in meta.quote_days if d >= first],
            # Zwischenstand (ab 1.8): letzter Punkt ist ein vorläufiger Kurs der laufenden oder gerade beendeten Sitzung
            "provisional": None
            if meta.provisional_day is None or int(days[-1]) != int(meta.provisional_day)
            else {"day": int(meta.provisional_day), "time_utc": meta.provisional_time, "session_closed": meta.provisional_final},
        }

    def fx_payload(self) -> dict | None:
        """Euro-Referenzkurse (Einheiten je EUR) der letzten ``FX_DAYS`` Tage bis zum Stichtag – Rechengrundlage
        der Musterdepots in USD oder EUR (ab 1.9). Fehlende Kurse bleiben ``null``; nichts wird aufgefüllt."""
        fx = self.comp.fx
        if fx is None or not len(fx.days):
            return None
        cutoff = self.comp.cutoff_day
        mask = (fx.days >= cutoff - FX_DAYS) & (fx.days <= cutoff)
        days = fx.days[mask]
        if not len(days):
            return None
        rates = {currency: _r_list(column[mask]) for currency, column in sorted(fx.per_eur.items())}
        return {
            "schema": "tr-fx/1",
            "snapshot_id": self.snapshot_id,
            "quelle": fx.source,
            "url": fx.url,
            "abgerufen_utc": fx.fetched_at,
            "max_alter_tage": fx.max_age_days,
            "basis": "Einheiten je EUR; USD je Einheit = (USD je EUR) / (Einheiten je EUR)",
            "tage": days.astype(int).tolist(),
            "je_eur": rates,
        }

    # ------------------------------------------------------------ Ablauf

    # ------------------------------------------------------------ Schreiben (ab 1.12 auf mehrere Prozesse verteilt)

    def _jobs(self) -> list[tuple]:
        """Arbeitspakete in der Reihenfolge abnehmender Dauer (vollständige Fenster zuerst) – für gleichmäßige Auslastung."""
        jobs: list[tuple] = [("window", h, None) for h in self.comp.windows]
        jobs += [("frequency",), ("overview",), ("instruments",)]
        n = self.comp.n_instruments
        jobs += [("series", start, min(n, start + SERIES_CHUNK)) for start in range(0, n, SERIES_CHUNK)]
        jobs += [("window", h, HEAD_LIMIT) for h in self.comp.windows]
        jobs += [("fx",)]
        if self.comp.rotation is not None:
            jobs += [("rotation", key) for key in sorted(self.comp.rotation.results)] + [("rotation_index",)]
        return jobs

    def _run_job(self, root: Path, job: tuple) -> None:
        kind = job[0]
        if kind == "window":
            h, limit = job[1], job[2]
            self._write(root, f"windows/{h}.bin" if limit is not None else f"windows/{h}.full.bin", self.window_payload(h, limit=limit))
        elif kind == "instruments":
            self._write(root, "instruments.bin", self.instruments_payload())
        elif kind == "overview":
            self._write(root, "overview.bin", self.overview_payload())
        elif kind == "frequency":
            self._write(root, "frequency.bin", self.frequency_payload())
        elif kind == "fx":
            data = self.fx_payload()
            if data is not None:
                self._write(root, "fx.bin", data)
        elif kind == "series":
            for i in range(job[1], job[2]):
                payload = self.series_payload(i)
                if payload is not None:
                    self._write(root, f"series/{self.comp.isins[i]}.bin", payload)
        elif kind == "rotation":
            self._write(root, f"rotation/{job[1]}.bin", RotationPayloads(self.comp.rotation, self.snapshot_id).variant(job[1]))
        elif kind == "rotation_index":
            self._write(root, "rotation/index.bin", RotationPayloads(self.comp.rotation, self.snapshot_id).index())
        else:  # pragma: no cover - Programmierfehler
            raise ValueError(f"unbekanntes Arbeitspaket {kind}")

    def _write_all(self, root: Path, workers: int | None) -> str:
        """Alle Dateien schreiben; mit mehreren Prozessen (fork: der Rechenstand wird nicht kopiert, nur geerbt),
        sonst – oder wenn das nicht geht – in diesem Prozess. Rückgabe: „parallel“ oder „ein Prozess“."""
        global _ACTIVE
        import multiprocessing

        from ..analytics.engine import default_workers

        jobs = self._jobs()
        count = workers if workers is not None else default_workers()
        if count > 1 and self.comp.n_instruments >= PARALLEL_WRITE_MIN_INSTRUMENTS and "fork" in multiprocessing.get_all_start_methods() and _only_thread():
            _ACTIVE = (self, root)
            try:
                ctx = multiprocessing.get_context("fork")
                with ctx.Pool(processes=count) as pool:
                    for hashes, sizes in pool.imap_unordered(_write_job, jobs):
                        self.hashes.update(hashes)
                        self.sizes.update(sizes)
                return "parallel"
            except (OSError, RuntimeError, EOFError) as exc:
                LOG.warning("Paralleles Schreiben nicht möglich (%s) – schreibe in einem Prozess", type(exc).__name__)
                self.hashes.clear()
                self.sizes.clear()
            finally:
                _ACTIVE = None
        for job in jobs:
            self._run_job(root, job)
        return "ein Prozess"

    def write(self, out_dir: Path, manifest_base: dict, *, workers: int | None = None) -> dict:
        """Schreibt alle Dateien in ein temporäres Verzeichnis und benennt es danach atomar um."""
        final = out_dir / self.snapshot_id
        tmp = out_dir / f".tmp-{self.snapshot_id}"
        if tmp.exists():
            shutil.rmtree(tmp)
        tmp.mkdir(parents=True)
        self.mode = self._write_all(tmp, workers)
        fx_data = self.fx_payload()
        series_count = sum(1 for relative in self.hashes if relative.startswith("series/"))
        rotation_summary = None
        if self.comp.rotation is not None:
            payloads = RotationPayloads(self.comp.rotation, self.snapshot_id)
            rotation_summary = payloads.manifest_summary(payloads.index())
        manifest = dict(manifest_base)
        manifest["schema"] = "tr-manifest/1"
        manifest["api_schema"] = SCHEMA
        manifest["snapshot_id"] = self.snapshot_id
        manifest["codes"] = code_tables(self.cfg)
        manifest["coverage"] = self.comp.ledger.as_dict()
        manifest["turnover"] = self.turnover_summary()
        manifest["venue_check"] = self.venue_summary()
        manifest["rotation"] = rotation_summary
        manifest["method_comparison"] = self.comp.method_comparison or None
        manifest["series_files"] = series_count
        manifest["fx"] = (
            None
            if fx_data is None
            else {
                "datei": "fx.bin",
                "quelle": fx_data["quelle"],
                "erster_tag": iso_or_none(fx_data["tage"][0]),
                "letzter_tag": iso_or_none(fx_data["tage"][-1]),
                "waehrungen": sorted({"EUR", *fx_data["je_eur"]}),
                "max_alter_tage": fx_data["max_alter_tage"],
            }
        )
        manifest["files"] = {"sha256_plaintext": dict(sorted(self.hashes.items())), "bytes": sum(self.sizes.values())}
        self._write(tmp, "manifest.bin", manifest)
        if final.exists():
            shutil.rmtree(final)
        tmp.rename(final)
        return manifest


# Ab 1.12: paralleles Schreiben erst ab dieser Größe (sonst überwiegt der Aufwand für die Prozesse – DEMO, Tests)
PARALLEL_WRITE_MIN_INSTRUMENTS = 1500
SERIES_CHUNK = 250
_ACTIVE: "tuple[SnapshotWriter, Path] | None" = None  # nur während write(): von den Kindprozessen geerbt (fork)


def _only_thread(timeout_s: float = 60.0) -> bool:
    """Vor fork: warten, bis keine anderen Threads mehr laufen (z. B. das Vorbereiten der Website im Hintergrund,
    ab 1.12). Ein Thread, der beim fork eine Sperre hält (etwa in OpenSSL beim Herunterladen), könnte den Kindprozess
    blockieren. Laufen nach ``timeout_s`` noch andere Threads, wird in einem Prozess geschrieben."""
    import threading
    import time

    deadline = time.monotonic() + timeout_s
    while True:
        others = [t for t in threading.enumerate() if t is not threading.current_thread() and t.is_alive()]
        if not others:
            return True
        if time.monotonic() > deadline:
            LOG.warning("Andere Threads laufen noch (%s) – schreibe in einem Prozess", ", ".join(t.name for t in others)[:120])
            return False
        others[0].join(timeout=0.2)


def _write_job(job: tuple) -> tuple[dict[str, str], dict[str, int]]:
    """Kindprozess: ein Arbeitspaket schreiben, Prüfsummen und Größen zurückgeben."""
    writer, root = _ACTIVE  # type: ignore[misc]
    writer.hashes, writer.sizes = {}, {}
    writer._run_job(root, job)
    return writer.hashes, writer.sizes


def _instrument_level(comp: SnapshotComputation) -> np.ndarray:
    from ..analytics.coverage import instrument_level_status

    return instrument_level_status(comp.pre_status, comp.status)


def snapshot_tar(snapshot_dir: Path) -> bytes:
    """Unkomprimiertes tar der (bereits komprimierten/verschlüsselten) Snapshot-Dateien."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w", format=tarfile.PAX_FORMAT) as tar:
        for path in sorted(snapshot_dir.rglob("*")):
            if path.is_file():
                info = tar.gettarinfo(str(path), arcname=f"{snapshot_dir.name}/{path.relative_to(snapshot_dir).as_posix()}")
                info.mtime = 0
                info.uid = info.gid = 0
                info.uname = info.gname = ""
                with open(path, "rb") as handle:
                    tar.addfile(info, handle)
    return buffer.getvalue()


def safe_extract_tar(data: bytes, target: Path, *, max_files: int = 200_000, max_bytes: int = 4 * 1024**3) -> list[str]:
    """Entpackt nur reguläre Dateien unterhalb von ``target`` (Schutz gegen Pfadüberschreibung)."""
    target = target.resolve()
    names: list[str] = []
    total = 0
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:*") as tar:
        members = tar.getmembers()
        if len(members) > max_files:
            raise ValueError("Archiv enthält zu viele Dateien")
        for member in members:
            if not member.isfile():
                continue
            destination = (target / member.name).resolve()
            if target not in destination.parents:
                raise ValueError(f"Unzulässiger Pfad im Archiv: {member.name}")
            if not member.name.endswith((".bin", ".json", ".npz")):
                raise ValueError(f"Unzulässiger Dateityp im Archiv: {member.name}")
            total += member.size
            if total > max_bytes:
                raise ValueError("Archiv entpackt zu groß")
            destination.parent.mkdir(parents=True, exist_ok=True)
            source = tar.extractfile(member)
            assert source is not None
            destination.write_bytes(source.read())
            names.append(member.name)
    return names


def evidence_archive(comp: SnapshotComputation, manifest: dict) -> bytes:
    """Prüfnachweis: alle berechneten Kennzahlen (auch nicht freigegebene) und Eingabereihen als NPZ."""
    arrays = {
        "isins": np.array(comp.isins),
        "status": comp.status,
        "start_day": comp.start_day,
        "n_obs": comp.n_obs,
        "n_exp": comp.n_exp,
        "r": comp.r,
        "p0": comp.p0,
        "p1": comp.p1,
        "m": comp.m,
        "r2": comp.r2,
        "slope_pct": comp.slope_pct,
        "noise_pct": comp.noise_pct,
        "mdd": comp.mdd,
        "vol_cov": comp.vol_cov,
        "wflags": comp.wflags,
        "pre_status": comp.pre_status,
        "warnings": comp.warnings,
        # Menge L (Ø Tagesumsatz ≥ Schwelle): reproduziert Ranking 2 und Gruppe B
        "liquid": comp.liquid if len(comp.liquid) == comp.n_instruments else np.zeros(comp.n_instruments, dtype=bool),
    }
    obs_index, obs_days, obs_close, obs_volume = [], [], [], []
    for i, series in sorted(comp.observed.items()):
        obs_index.extend([i] * len(series.days))
        obs_days.append(series.days)
        obs_close.append(series.close)
        obs_volume.append(series.volume)
    arrays["obs_instrument"] = np.array(obs_index, dtype=np.int32)
    arrays["obs_day"] = np.concatenate(obs_days) if obs_days else np.empty(0, dtype=np.int64)
    arrays["obs_close"] = np.concatenate(obs_close) if obs_close else np.empty(0)
    arrays["obs_volume"] = np.concatenate(obs_volume) if obs_volume else np.empty(0)
    npz = io.BytesIO()
    np.savez_compressed(npz, **arrays)
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        for name, data in (("kennzahlen_und_eingaben.npz", npz.getvalue()), ("manifest.json", dumps(manifest, pretty=True).encode("utf-8"))):
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mtime = 0
            tar.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


def load_evidence_npz(data: bytes) -> dict[str, np.ndarray]:
    """Liest den Prüfnachweis ohne Pickle (allow_pickle=False)."""
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
        member = tar.extractfile("kennzahlen_und_eingaben.npz")
        assert member is not None
        with np.load(io.BytesIO(member.read()), allow_pickle=False) as npz:
            return {k: npz[k] for k in npz.files}


def manifest_digest(manifest: dict) -> str:
    return sha256_hex(canonical_bytes(manifest))


def iso_or_none(day: int | None) -> str | None:
    return day_to_iso(day) if day is not None else None
