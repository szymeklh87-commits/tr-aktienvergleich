"""Schreibt einen geprüften Snapshot als statische Dateien (Datenvertrag ``static-api-v1``).

Verzeichnis ``<snapshot_id>/`` mit:

* ``manifest.bin``      Metadaten, Versionen, Abdeckungsbilanz, Prüfungen, Dateihashes
* ``instruments.bin``   vollständiges Universum (auch nicht berechenbare Einträge)
* ``overview.bin``      90 Zeilen je Gewichtung (Spitzenreiter) + Renditesieger + Maximum
* ``frequency.bin``     veröffentlichte Top-10-Fundstellen aller Zellen + Feldgrößen
* ``windows/<h>.bin``   vollständige Kennzahlen und alle Ranglisten eines Fensters
* ``series/<ISIN>.bin`` Kursreihe (verwendete Tageskurse), Lücken, Startanker, Rangmatrix

Jede Datei ist ein TRA1-Container (gzip, optional AES-GCM mit Pfad als AAD).
Vergleichsmengen: ``v0`` = 0/100 auf V (native), ``u`` = alle elf Gewichte auf U.
native(w=0) → v0; native(w≥10) → u[w]; common_trend(w) → u[w].
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

SCHEMA = "static-api-v1"
HEAD_LIMIT = 50  # Kopfdatei je Fenster: erste 50 Plätze jeder der zwölf Ranglisten
RANK_COLUMNS = ["v0"] + [f"u{w}" for w in CANONICAL_WEIGHTS]  # 12 Spalten je Fenster


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


def _r(value) -> float | None:
    if value is None:
        return None
    number = float(value)
    return number if np.isfinite(number) else None


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
        atomic_write_bytes(root / relative, blob)
        self.hashes[relative] = sha256_hex(plain)
        self.sizes[relative] = len(blob)

    def _build_rank_matrix(self) -> np.ndarray:
        comp = self.comp
        n = comp.n_instruments
        matrix = np.zeros((n, 90, len(RANK_COLUMNS)), dtype=np.uint16)
        for col, h in enumerate(comp.windows):
            window = comp.rankings[h]
            rankings = [window.native0] + [window.trend[w] for w in CANONICAL_WEIGHTS]
            for k, ranking in enumerate(rankings):
                if ranking.size:
                    matrix[ranking.order, col, k] = np.arange(1, ranking.size + 1, dtype=np.uint16)
        return matrix

    def _empty_reason(self, h: int, cohort: str) -> str:
        comp = self.comp
        window = comp.rankings[h]
        if window.native0.size == 0:
            return "keine_vergleichbare_aktie"
        if cohort == "v0":
            return "keine_vergleichbare_aktie"
        col = h - 1
        n_obs = comp.n_obs[window.v_idx, col]
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
            "counts": {"V": int(len(window.v_idx)), "U": int(len(window.u_idx))},
            "m": {
                "idx": members.astype(int).tolist(),
                "start": comp.start_day[members, col].astype(int).tolist(),
                "n": comp.n_obs[members, col].astype(int).tolist(),
                "n_exp": comp.n_exp[members, col].astype(int).tolist(),
                "r": [_r(x) for x in comp.r[members, col]],
                "r2": [_r(x) for x in comp.r2[members, col]],
                "slope": [_sig(x) for x in comp.slope_pct[members, col]],
                "noise": [_sig(x) for x in comp.noise_pct[members, col]],
                "mdd": [_sig(x) for x in comp.mdd[members, col]],
                "vol": [_sig(x, 4) for x in comp.vol_cov[members, col]],
                "wf": comp.wflags[members, col].astype(int).tolist(),
                "a_rv": a_rv,
                "a_gu": a_gu,
                "a_ru": a_ru,
            },
            "orders": {"v0": cut(window.native0.order), "u": {str(w): cut(window.trend[w].order) for w in CANONICAL_WEIGHTS}},
            "ties": {"v0": ties(window.native0), "u": {str(w): ties(window.trend[w]) for w in CANONICAL_WEIGHTS}},
        }
        if limit is None:
            payload["status_b64"] = base64.b64encode(comp.status[:, col].astype(np.uint8).tobytes()).decode("ascii")
        return payload

    def overview_payload(self) -> dict:
        comp = self.comp
        rows_v0 = []
        rows_u: dict[str, list] = {str(w): [] for w in CANONICAL_WEIGHTS}
        counts_v, counts_u = [], []
        for h in comp.windows:
            col = h - 1
            window = comp.rankings[h]
            counts_v.append(window.native0.size)
            counts_u.append(int(len(window.u_idx)))
            rows_v0.append(self._row(h, col, window.native0, "v0"))
            for w in CANONICAL_WEIGHTS:
                rows_u[str(w)].append(self._row(h, col, window.trend[w], "u"))
        winners = []
        for row in comp.winners:
            winners.append(
                {
                    "h": row.h,
                    "M": row.cohort_size,
                    "tie": row.tie,
                    "all_negative": row.all_negative,
                    "empty": row.empty_reason,
                    "entries": [
                        {"idx": e["idx"], "r": _r(e["r"]), "start": e["start_day"], "end": e["end_day"]} for e in row.entries
                    ],
                }
            )
        overall = comp.overall_max
        return {
            "schema": "tr-overview/1",
            "snapshot_id": self.snapshot_id,
            "cutoff_day": comp.cutoff_day,
            "counts": {"V": counts_v, "U": counts_u},
            "v0": rows_v0,
            "u": rows_u,
            "winners": winners,
            "overall_max": {
                "tie": overall["tie"],
                "pairs_evaluated": overall["pairs_evaluated"],
                "entries": [
                    {"idx": e["idx"], "h": e["h"], "r": _r(e["r"]), "start": e["start_day"], "end": e["end_day"], "same_h": e.get("same_effective_h", [])}
                    for e in overall["entries"]
                ],
            },
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
            "tie": tied,
            "sole": ranking.size == 1,
        }

    def frequency_payload(self) -> dict:
        comp = self.comp

        def occurrences(rank_getter) -> dict:
            out = {"h": [], "rank": [], "idx": [], "score": [], "r": [], "start": []}
            for h in comp.windows:
                ranking = rank_getter(h)
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
        default = aggregate_frequency(
            comp.rankings,
            policy="native",
            weights=CANONICAL_WEIGHTS,
            window_days=comp.windows,
            top_k=10,
            r_matrix=comp.r,
            start_matrix=comp.start_day,
            cutoff_day=comp.cutoff_day,
            isin_of=comp.isin_of,
        )
        return {
            "schema": "tr-frequency/1",
            "snapshot_id": self.snapshot_id,
            "aggregation_version": self.cfg.frequency_version,
            "cutoff_day": comp.cutoff_day,
            "M": {
                "v0": [comp.rankings[h].native0.size for h in comp.windows],
                "u": [int(len(comp.rankings[h].u_idx)) for h in comp.windows],
            },
            "occ": {"v0": v0, "u": u},
            "rules": {
                "zelle": "(snapshot, cohort_policy, h, w); je Zelle zählt eine ISIN höchstens einmal",
                "nenner_E": "Zahl der gültigen Zellen der Auswahl (veröffentlichtes Ranking mit mindestens einer Aktie)",
                "A_i": "Zahl der ausgewählten Zellen, in denen die Aktie einen gültigen Rang besitzt",
                "sortierung_einzeln": {"10": "N10,N3,N1,ISIN", "3": "N3,N1,N10,ISIN", "1": "N1,N3,N10,ISIN"},
                "sortierung_alle": {"10": "N10,H10,N3,N1,ISIN", "3": "N3,H3,N1,N10,ISIN", "1": "N1,H1,N3,N10,ISIN"},
                "sortierung_zeitraeume": "H_K,N_K,N1,ISIN",
            },
            "server_reference": {
                "policy": "native",
                "weights": "all",
                "top_k": 10,
                "E": default.valid_cells,
                "cells": default.theoretical_cells,
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
                    for e in default.entries[:200]
                ],
            },
        }

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
            "c": [_r(x) for x in close],
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
        }

    # ------------------------------------------------------------ Ablauf

    def write(self, out_dir: Path, manifest_base: dict) -> dict:
        """Schreibt alle Dateien in ein temporäres Verzeichnis und benennt es danach atomar um."""
        final = out_dir / self.snapshot_id
        tmp = out_dir / f".tmp-{self.snapshot_id}"
        if tmp.exists():
            shutil.rmtree(tmp)
        tmp.mkdir(parents=True)
        self._write(tmp, "instruments.bin", self.instruments_payload())
        for h in self.comp.windows:
            self._write(tmp, f"windows/{h}.bin", self.window_payload(h, limit=HEAD_LIMIT))
            self._write(tmp, f"windows/{h}.full.bin", self.window_payload(h))
        self._write(tmp, "overview.bin", self.overview_payload())
        self._write(tmp, "frequency.bin", self.frequency_payload())
        series_count = 0
        for i in range(self.comp.n_instruments):
            payload = self.series_payload(i)
            if payload is not None:
                self._write(tmp, f"series/{self.comp.isins[i]}.bin", payload)
                series_count += 1
        manifest = dict(manifest_base)
        manifest["schema"] = "tr-manifest/1"
        manifest["api_schema"] = SCHEMA
        manifest["snapshot_id"] = self.snapshot_id
        manifest["codes"] = code_tables()
        manifest["coverage"] = self.comp.ledger.as_dict()
        manifest["series_files"] = series_count
        manifest["files"] = {"sha256_plaintext": dict(sorted(self.hashes.items())), "bytes": sum(self.sizes.values())}
        self._write(tmp, "manifest.bin", manifest)
        if final.exists():
            shutil.rmtree(final)
        tmp.rename(final)
        return manifest


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
