"""Gesamtberechnung eines Snapshots: alle Instrumente × alle 90 Fenster.

Ablauf je Instrument: Kurse bis zum Stichtag kürzen, nur Kalendersitzungen verwenden,
ungültige Kurse verwerfen (nicht auffüllen), Sprünge prüfen, dann alle 90 Fenster
auflösen und bewerten. Fenster mit identischer tatsächlicher Startsitzung teilen sich
dieselbe Kennzahlberechnung (Zwischenspeicher je Startindex). Anschließend werden pro
Fenster die Mengen V und U gebildet und alle elf Gewichtungen aus denselben
Kennzahlen gerankt – Kurse werden dafür nicht erneut geladen.

Zusätzlich je Instrument der Ø Tagesumsatz der letzten 20 Sitzungen (indikativ in USD). Er
bildet die Menge L (Ø Umsatz ≥ Schwelle); Ranking 2 ist die reine Renditerangliste auf V ∩ L –
gleiche Renditen, gleicher Stichtag, gleiche Reihenfolge, nur ohne die übrigen Aktien.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

import numpy as np

from ..config import MethodConfig
from .codes import RETURN_PUBLISHABLE, InstrumentWarning, Status, WindowWarning
from .coverage import CoverageLedger, build_coverage_ledger
from .frequency import WinnerRow, build_pure_return_winners, overall_max_return
from .fx import FxRates
from .metrics import calculate_price_metrics, impulse_share, takeover_pattern
from .quality import JumpReview, SplitEvent, WindowVolumeChecks, classify_window, review_jumps, spans_any, zero_volume_outliers
from .ranking import WindowRanking, group_b_ranking, pure_return_subset, rank_window
from .turnover import TurnoverResult, compute_turnover
from .windows import resolve_window

_EMPTY_I = np.empty(0, dtype=np.int64)
_EMPTY_F = np.empty(0, dtype=np.float64)


@dataclass
class InstrumentData:
    """Rechenkern-Eingabe für ein Instrument (eine Referenznotierung)."""

    isin: str
    pre_status: int = 0
    sessions: np.ndarray | None = None
    days: np.ndarray = field(default_factory=lambda: _EMPTY_I)
    close: np.ndarray = field(default_factory=lambda: _EMPTY_F)
    volume: np.ndarray = field(default_factory=lambda: _EMPTY_F)
    splits: list[SplitEvent] = field(default_factory=list)
    reviewed_jumps: dict[int, str] = field(default_factory=dict)
    hold_all: bool = False
    warnings: int = 0
    currency: str | None = None  # Hauptwährung (z. B. GBP), für den Umsatz in USD
    unit_factor: float = 1.0  # Kurseinheit → Hauptwährung (0,01 bei Pence)
    # Zwischenstand (ab 1.8): Tag des vorläufigen Kurses (laufende Sitzung). Sein Umsatz ist erst ein Teil
    # des Tages und zählt deshalb nicht zum Ø Tagesumsatz; Rendite und Prüfungen verwenden ihn wie einen Schlusskurs.
    provisional_day: int | None = None
    # Eigener Stichtag (Zwischenstand ab 1.13, Stand mit Schlusskursen ab tr-methode-1.9.0): Fehlt der Kurs am Stichtag –
    # Börse noch nicht geöffnet (z. B. New York vor 15:30 Uhr), Feiertag oder kein Schlusskurs geliefert –, zählt die
    # Aktie mit ihrem letzten Schlusskurs; alle Fenster enden dort.
    cutoff_day: int | None = None


@dataclass
class ObservedSeries:
    days: np.ndarray
    close: np.ndarray
    volume: np.ndarray


@dataclass
class SnapshotComputation:
    cutoff_day: int
    isins: list[str]
    windows: tuple[int, ...]
    target_start: np.ndarray
    status: np.ndarray
    start_day: np.ndarray
    n_obs: np.ndarray
    n_exp: np.ndarray
    r: np.ndarray
    p0: np.ndarray
    p1: np.ndarray
    m: np.ndarray
    r2: np.ndarray
    slope_pct: np.ndarray
    noise_pct: np.ndarray
    mdd: np.ndarray
    vol_cov: np.ndarray
    wflags: np.ndarray
    ups: np.ndarray  # Zahl positiver Schlusskursvergleiche je Fenster (kennzahlen-v2)
    previous_status: np.ndarray  # Hauptstatus nach den Regeln der Vorversion (nur Methodenvergleich)
    pre_status: np.ndarray
    warnings: np.ndarray
    has_history: np.ndarray
    rankings: dict[int, WindowRanking]
    ledger: CoverageLedger
    winners: list[WinnerRow]
    overall_max: dict
    input_hash: str
    observed: dict[int, ObservedSeries]
    jump_reviews: dict[int, JumpReview]
    turnover: list[TurnoverResult] = field(default_factory=list)
    liquid: np.ndarray = field(default_factory=lambda: np.zeros(0, dtype=bool))  # Menge L
    winners_liquid: list[WinnerRow] = field(default_factory=list)
    overall_max_liquid: dict = field(default_factory=dict)
    fx: FxRates | None = None
    venue: object | None = None  # analytics.venues.VenueCheck – Abgleich mit zweitem Börsenplatz (nach der Berechnung)
    rotation: object | None = None  # jobs.daily.RotationOutcome – Umschichtungs-Regel (nach der Berechnung)
    method_comparison: dict = field(default_factory=dict)  # Vergleich mit den Regeln der Vorversion
    # Letzter Tag der Fenster je Aktie (ab 1.13): sonst der Stichtag; im Zwischenstand bei noch geschlossener Börse
    # der letzte Handelstag davor
    end_day: np.ndarray = field(default_factory=lambda: np.zeros(0, dtype=np.int64))

    @property
    def n_instruments(self) -> int:
        return len(self.isins)

    def isin_of(self, idx: int) -> str:
        return self.isins[idx]


@dataclass
class _Rows:
    """Ergebnis der Kennzahlberechnung für einen Block von Instrumenten (ab 1.10 parallel berechenbar)."""

    status: np.ndarray
    previous_status: np.ndarray
    start_day: np.ndarray
    n_obs: np.ndarray
    n_exp: np.ndarray
    r: np.ndarray
    p0: np.ndarray
    p1: np.ndarray
    m: np.ndarray
    r2: np.ndarray
    slope: np.ndarray
    noise: np.ndarray
    mdd: np.ndarray
    vol_cov: np.ndarray
    wflags: np.ndarray
    ups: np.ndarray
    pre_status: np.ndarray
    warnings: np.ndarray
    has_history: np.ndarray
    observed: dict
    jump_reviews: dict
    turnover: list
    hash_parts: list


def _compute_rows(instruments: list[InstrumentData], cutoff_day: int, cfg: MethodConfig, fx: FxRates | None, windows: tuple) -> _Rows:
    """Alle 90 Fenster für einen Block von Instrumenten – die bisherige Schleife, unverändert in der Rechnung.

    Statt den Hash direkt fortzuschreiben, sammelt sie die Hash-Bausteine je Instrument; der Aufrufer fügt sie
    in der ursprünglichen Reihenfolge an (gleicher ``input_hash`` wie bei einer einzigen Schleife)."""
    n = len(instruments)
    w = len(windows)
    status = np.zeros((n, w), dtype=np.uint8)
    start_day = np.full((n, w), -1, dtype=np.int64)
    n_obs = np.zeros((n, w), dtype=np.int16)
    n_exp = np.zeros((n, w), dtype=np.int16)
    shape = (n, w)
    r = np.full(shape, np.nan)
    p0 = np.full(shape, np.nan)
    p1 = np.full(shape, np.nan)
    m_arr = np.full(shape, np.nan)
    r2 = np.full(shape, np.nan)
    slope = np.full(shape, np.nan)
    noise = np.full(shape, np.nan)
    mdd = np.full(shape, np.nan)
    vol_cov = np.full(shape, np.nan)
    wflags = np.zeros(shape, dtype=np.uint16)
    ups = np.zeros(shape, dtype=np.int16)
    previous_status = np.zeros((n, w), dtype=np.uint8)
    pre_status = np.zeros(n, dtype=np.uint8)
    warnings = np.zeros(n, dtype=np.uint32)
    has_history = np.zeros(n, dtype=bool)
    observed: dict[int, ObservedSeries] = {}
    jump_reviews: dict[int, JumpReview] = {}
    turnover: list[TurnoverResult] = [TurnoverResult("keine_kurse") for _ in range(n)]

    hash_parts: list[list[bytes]] = []

    for i, inst in enumerate(instruments):
        parts: list[bytes] = []
        hash_parts.append(parts)
        warn = int(inst.warnings)
        parts.append(
            f"|{inst.isin}:{inst.pre_status}:{int(inst.hold_all)}{':p' + str(inst.provisional_day) if inst.provisional_day is not None else ''}"
            f"{':c' + str(inst.cutoff_day) if inst.cutoff_day is not None else ''}".encode()
        )
        # Stichtag dieser Aktie: ohne Kurs am gemeinsamen Stichtag der Tag ihres letzten Schlusskurses (ab 1.13 / 1.9.0)
        own_cutoff = int(inst.cutoff_day) if inst.cutoff_day is not None else int(cutoff_day)
        if inst.pre_status:
            pre_status[i] = inst.pre_status
            status[i, :] = previous_status[i, :] = inst.pre_status
            warnings[i] = warn
            continue
        if inst.sessions is None or len(inst.sessions) == 0:
            pre_status[i] = Status.KALENDER_FEHLT
            status[i, :] = previous_status[i, :] = Status.KALENDER_FEHLT
            warnings[i] = warn
            turnover[i] = TurnoverResult("kalender_fehlt")
            continue

        days = np.asarray(inst.days, dtype=np.int64)
        close = np.asarray(inst.close, dtype=np.float64)
        volume = np.asarray(inst.volume, dtype=np.float64)
        if not (len(days) == len(close) == len(volume)):
            raise ValueError(f"{inst.isin}: ungleich lange Kursarrays")
        if len(days) > 1 and np.any(np.diff(days) <= 0):
            raise ValueError(f"{inst.isin}: Sitzungsdaten nicht streng aufsteigend")
        keep = days <= own_cutoff
        days, close, volume = days[keep], close[keep], volume[keep]
        if len(days) == 0:
            pre_status[i] = Status.KEINE_KURSDATEN
            status[i, :] = previous_status[i, :] = Status.KEINE_KURSDATEN
            warnings[i] = warn
            continue
        has_history[i] = True

        sessions = np.asarray(inst.sessions, dtype=np.int64)
        on_session = np.isin(days, sessions)
        if not np.all(on_session):
            warn |= 1 << InstrumentWarning.BARS_AN_NICHTHANDELSTAGEN
            days, close, volume = days[on_session], close[on_session], volume[on_session]
        valid = np.isfinite(close) & (close > 0)
        obs_days = days[valid]
        obs_close = close[valid]
        obs_vol = volume[valid]
        observed[i] = ObservedSeries(obs_days, obs_close, obs_vol)
        parts.append(obs_days.tobytes())
        parts.append(obs_close.tobytes())
        parts.append(np.where(np.isfinite(obs_vol), obs_vol, -1.0).tobytes())
        for event in inst.splits:
            parts.append(f"s{event.day}:{event.factor!r}".encode())
        for day, decision in sorted(inst.reviewed_jumps.items()):
            parts.append(f"j{day}:{decision}".encode())

        if len(obs_days) == 0:
            pre_status[i] = Status.KEINE_KURSDATEN
            status[i, :] = previous_status[i, :] = Status.KEINE_KURSDATEN
            warnings[i] = warn
            continue

        review = review_jumps(obs_days, obs_close, inst.splits, inst.reviewed_jumps, cfg)
        jump_reviews[i] = review
        held = review.held_array()
        released = review.released_array()
        if len(released):
            warn |= 1 << InstrumentWarning.GEPRUEFTER_KURSSPRUNG
        split_days = np.array(sorted(e.day for e in inst.splits), dtype=np.int64)
        if len(split_days) and np.any((split_days > obs_days[0]) & (split_days <= obs_days[-1])):
            warn |= 1 << InstrumentWarning.SPLIT_IN_HISTORIE

        provisional_end = inst.provisional_day is not None and int(obs_days[-1]) == int(inst.provisional_day)
        result = compute_turnover(
            obs_days,
            obs_close,
            obs_vol,
            sessions,
            own_cutoff - 1 if provisional_end else own_cutoff,
            split_days=split_days,
            currency=inst.currency,
            unit_factor=inst.unit_factor,
            fx=fx,
            n_sessions=cfg.turnover_sessions,
            min_positive=cfg.turnover_min_positive,
        )
        turnover[i] = result
        parts.append(f"|t{result.fingerprint()}".encode())
        if result.determined:
            if result.avg_usd < cfg.turnover_very_low_usd:
                warn |= 1 << InstrumentWarning.SEHR_NIEDRIGER_UMSATZ
        else:
            warn |= 1 << InstrumentWarning.UMSATZ_NICHT_BESTIMMBAR

        lookback = obs_vol[-cfg.thin_trading_lookback :]
        if len(lookback):
            known = np.isfinite(lookback)
            if known.any() and np.mean(lookback[known] == 0) > cfg.thin_trading_zero_share:
                warn |= 1 << InstrumentWarning.WENIGE_AKTIVE_HANDELSTAGE
            if np.mean(~known) > cfg.unknown_volume_warn_share:
                warn |= 1 << InstrumentWarning.VOLUMEN_OFT_UNBEKANNT
        warnings[i] = warn

        positive_volume = np.isfinite(obs_vol) & (obs_vol > 0)
        vol_cum = np.cumsum(positive_volume.astype(np.int64))
        # Regeln des Ausgangsmodells (ab tr-methode-1.7.0): gemeldetes Volumen (endlich, ≥ 0) an jeder Beobachtung
        reported_volume = np.isfinite(obs_vol) & (obs_vol >= 0)
        reported_cum = np.cumsum(reported_volume.astype(np.int64))
        # gemeldete Splits ohne dokumentierte Freigabe halten (ab 1.7.0) jedes Fenster zurück, das sie überspannt
        open_split_days = np.array(
            [d for d in split_days.tolist() if inst.reviewed_jumps.get(int(d)) != "freigegeben"], dtype=np.int64
        )
        zero_volume_days = set(zero_volume_outliers(obs_days, obs_close, obs_vol, cfg.zero_volume_move, inst.reviewed_jumps).tolist())
        if zero_volume_days:
            warnings[i] = warn = warn | (1 << InstrumentWarning.NULLUMSATZ_AUSREISSER)
        end_outlier = int(obs_days[-1]) in zero_volume_days
        cache: dict[int, tuple] = {}

        for col, h in enumerate(windows):
            rw = resolve_window(obs_days, sessions, own_cutoff, h, cfg.anchor_max_gap_days)
            if rw.start_session is not None:
                start_day[i, col] = rw.start_session
            if not rw.ok:
                status[i, col] = previous_status[i, col] = rw.status
                continue
            j = int(rw.start_index)
            record = cache.get(j)
            if record is None:
                window_prices = obs_close[j:]
                metrics = calculate_price_metrics(
                    window_prices,
                    min_obs_trend=cfg.min_obs_trend,
                    sst_rel_tolerance=cfg.sst_rel_tolerance,
                    r2_bound_tolerance=cfg.r2_bound_tolerance,
                    strict=False,
                )
                vol_positive = int(vol_cum[-1] - (vol_cum[j - 1] if j > 0 else 0))
                zero_volume_edge = end_outlier or int(obs_days[j]) in zero_volume_days
                held_in = inst.hold_all or zero_volume_edge or spans_any(held, int(obs_days[j]), own_cutoff)
                flags = 0
                if metrics.sst is not None and metrics.r2 is None and metrics.sst > cfg.sst_rel_tolerance * metrics.n * float(np.mean(window_prices)) ** 2:
                    flags |= 1 << WindowWarning.R2_NUMERISCH_INSTABIL
                share = impulse_share(window_prices)
                if share is not None and share > cfg.impulse_share and abs(metrics.r) >= cfg.impulse_min_abs_return:
                    flags |= 1 << WindowWarning.IMPULSTAG
                split_reported = spans_any(open_split_days, int(obs_days[j]), own_cutoff)
                split_open = cfg.hold_split_windows and split_reported
                if len(split_days) and spans_any(split_days, int(obs_days[j]), own_cutoff) and not split_open:
                    flags |= 1 << WindowWarning.SPLIT_IM_FENSTER  # nur freigegebene Splits (sonst zurückgehalten)
                if len(released) and spans_any(released, int(obs_days[j]), own_cutoff):
                    flags |= 1 << WindowWarning.GEPRUEFTER_SPRUNG_IM_FENSTER
                if takeover_pattern(window_prices, jump_min=cfg.takeover_jump_min, calm_max=cfg.takeover_calm_max, calm_sessions=cfg.takeover_calm_sessions):
                    flags |= 1 << WindowWarning.UEBERNAHMEMUSTER
                # Befunde des Fensters; ob sie ausschließen, entscheiden die Zulassungsregeln der Version
                extra = WindowVolumeChecks(
                    volume_missing=int(reported_cum[-1] - (reported_cum[j - 1] if j > 0 else 0)) < rw.n_obs,
                    edge_volume_missing=not (bool(positive_volume[j]) and bool(positive_volume[-1])),
                    split_in_window=split_reported,
                )
                window_status = classify_window(
                    rw, vol_positive=vol_positive, held_in_window=held_in, metrics=metrics, cfg=cfg, extra=extra
                )
                legacy_status = classify_window(
                    rw, vol_positive=vol_positive, held_in_window=held_in, metrics=metrics, cfg=cfg, extra=extra, rules=cfg.previous_rules
                )
                record = (metrics, vol_positive, flags, window_status, legacy_status)
                cache[j] = record
            metrics, vol_positive, flags, window_status, legacy_status = record
            status[i, col] = window_status
            previous_status[i, col] = legacy_status
            ups[i, col] = metrics.ups
            n_obs[i, col] = rw.n_obs
            n_exp[i, col] = rw.n_expected
            r[i, col] = metrics.r
            p0[i, col] = obs_close[j]
            p1[i, col] = obs_close[-1]
            mdd[i, col] = metrics.mdd
            vol_cov[i, col] = vol_positive / rw.n_obs
            wflags[i, col] = flags
            if metrics.m is not None:
                m_arr[i, col] = metrics.m
                slope[i, col] = metrics.slope_pct
                noise[i, col] = metrics.noise_pct
            if metrics.r2 is not None:
                r2[i, col] = metrics.r2
        if own_cutoff != int(cutoff_day) and not cfg.previous_last_close:
            # Methodenvergleich mit einer Vorversion bis 1.8.0: Nach deren Regeln fehlte diese Aktie am gemeinsamen
            # Stichtag – Börse geschlossen (Feiertag) oder kein Schlusskurs; seit 1.9.0 zählt ihr letzter Schlusskurs.
            market_closed = not bool(np.any(np.asarray(inst.sessions) == int(cutoff_day)))
            previous_status[i, :] = Status.MARKT_AM_STICHTAG_GESCHLOSSEN if market_closed else Status.KURS_AM_STICHTAG_FEHLT

    return _Rows(
        status=status,
        previous_status=previous_status,
        start_day=start_day,
        n_obs=n_obs,
        n_exp=n_exp,
        r=r,
        p0=p0,
        p1=p1,
        m=m_arr,
        r2=r2,
        slope=slope,
        noise=noise,
        mdd=mdd,
        vol_cov=vol_cov,
        wflags=wflags,
        ups=ups,
        pre_status=pre_status,
        warnings=warnings,
        has_history=has_history,
        observed=observed,
        jump_reviews=jump_reviews,
        turnover=turnover,
        hash_parts=[b"".join(parts) for parts in hash_parts],
    )


def _rows_task(args) -> _Rows:
    return _compute_rows(*args)


# Unterhalb dieser Größe lohnt sich kein zweiter Prozess (Start und Datenübergabe kosten etwa eine Sekunde)
PARALLEL_MIN_INSTRUMENTS = 1500


def default_workers() -> int:
    """Rechenprozesse: ``TRAKTIEN_RECHENPROZESSE`` oder die Zahl der Prozessorkerne (höchstens 4)."""
    import os

    configured = os.environ.get("TRAKTIEN_RECHENPROZESSE", "").strip()
    if configured.isdigit() and int(configured) > 0:
        return int(configured)
    return max(1, min(4, os.cpu_count() or 1))


def _rows_parallel(instruments: list[InstrumentData], cutoff_day: int, cfg: MethodConfig, fx: FxRates | None, windows: tuple, workers: int) -> list[tuple[int, _Rows]]:
    """Blöcke aufeinanderfolgender Instrumente in ``workers`` Prozessen; Rückgabe (Anfangsindex, Ergebnis)."""
    import multiprocessing
    from concurrent.futures import ProcessPoolExecutor

    n = len(instruments)
    pieces = max(workers * 3, 1)
    bounds = [round(k * n / pieces) for k in range(pieces + 1)]
    blocks = [(bounds[k], bounds[k + 1]) for k in range(pieces) if bounds[k + 1] > bounds[k]]
    context = multiprocessing.get_context("forkserver" if "forkserver" in multiprocessing.get_all_start_methods() else "spawn")
    with ProcessPoolExecutor(max_workers=workers, mp_context=context) as pool:
        results = list(pool.map(_rows_task, [(instruments[lo:hi], cutoff_day, cfg, fx, windows) for lo, hi in blocks]))
    return [(lo, rows) for (lo, _), rows in zip(blocks, results)]


def compute_snapshot(
    instruments: list[InstrumentData],
    cutoff_day: int,
    cfg: MethodConfig,
    fx: FxRates | None = None,
    *,
    workers: int | None = None,
) -> SnapshotComputation:
    cfg.validate()
    isins = [inst.isin for inst in instruments]
    if isins != sorted(isins) or len(set(isins)) != len(isins):
        raise ValueError("Instrumente müssen eindeutig und aufsteigend nach ISIN sortiert sein")

    windows = tuple(cfg.windows())
    n = len(instruments)
    w = len(windows)
    target_start = np.array([cutoff_day - h for h in windows], dtype=np.int64)

    hasher = hashlib.sha256()
    hasher.update(f"cutoff={cutoff_day};n={n};".encode())

    # Kennzahlen je Instrument: bei großen Universen auf mehrere Prozesse verteilt (ab 1.10, gleiche Ergebnisse)
    count = default_workers() if workers is None else max(1, int(workers))
    parts = None
    if count > 1 and n >= (PARALLEL_MIN_INSTRUMENTS if workers is None else 2):
        try:
            parts = _rows_parallel(instruments, cutoff_day, cfg, fx, windows, count)
        except (OSError, RuntimeError, ImportError, EOFError) as exc:  # z. B. keine Hilfsprozesse möglich
            import logging

            logging.getLogger(__name__).warning("Mehrere Rechenprozesse nicht möglich (%s) – rechne in einem Prozess", type(exc).__name__)
            parts = None
    if parts is None:
        parts = [(0, _compute_rows(instruments, cutoff_day, cfg, fx, windows))]
    status = np.concatenate([rows.status for _, rows in parts]) if parts else np.zeros((0, w), dtype=np.uint8)
    previous_status = np.concatenate([rows.previous_status for _, rows in parts])
    start_day = np.concatenate([rows.start_day for _, rows in parts])
    n_obs = np.concatenate([rows.n_obs for _, rows in parts])
    n_exp = np.concatenate([rows.n_exp for _, rows in parts])
    r = np.concatenate([rows.r for _, rows in parts])
    p0 = np.concatenate([rows.p0 for _, rows in parts])
    p1 = np.concatenate([rows.p1 for _, rows in parts])
    m_arr = np.concatenate([rows.m for _, rows in parts])
    r2 = np.concatenate([rows.r2 for _, rows in parts])
    slope = np.concatenate([rows.slope for _, rows in parts])
    noise = np.concatenate([rows.noise for _, rows in parts])
    mdd = np.concatenate([rows.mdd for _, rows in parts])
    vol_cov = np.concatenate([rows.vol_cov for _, rows in parts])
    wflags = np.concatenate([rows.wflags for _, rows in parts])
    ups = np.concatenate([rows.ups for _, rows in parts])
    pre_status = np.concatenate([rows.pre_status for _, rows in parts])
    warnings = np.concatenate([rows.warnings for _, rows in parts])
    has_history = np.concatenate([rows.has_history for _, rows in parts])
    observed: dict[int, ObservedSeries] = {}
    jump_reviews: dict[int, JumpReview] = {}
    turnover: list[TurnoverResult] = []
    for offset, rows in parts:
        observed.update({offset + k: v for k, v in rows.observed.items()})
        jump_reviews.update({offset + k: v for k, v in rows.jump_reviews.items()})
        turnover.extend(rows.turnover)
        for piece in rows.hash_parts:
            hasher.update(piece)

    # Menge L: Ø Tagesumsatz bestimmt und mindestens die Schwelle (indikativ in USD)
    liquid = np.array([t.determined and t.avg_usd >= cfg.turnover_threshold_usd for t in turnover], dtype=bool)
    rankings: dict[int, WindowRanking] = {}
    publishable_codes = [int(s) for s in RETURN_PUBLISHABLE]
    for col, h in enumerate(windows):
        column = status[:, col]
        v_idx = np.nonzero(np.isin(column, publishable_codes))[0].astype(np.int64)
        u_idx = np.nonzero(column == Status.TREND_BEWERTBAR)[0].astype(np.int64)
        rankings[h] = rank_window(h, v_idx, u_idx, r[:, col], r2[:, col], slope[:, col], noise[:, col], cfg.tie_rule)
        rankings[h].native0_liquid = pure_return_subset(rankings[h].native0, liquid, r[:, col])
        rankings[h].group_b = group_b_ranking(rankings[h], liquid, r[:, col], r2[:, col], slope[:, col], noise[:, col], cfg.tie_rule)

    from .comparison import compare_with_previous_rules

    method_comparison = compare_with_previous_rules(
        status=status,
        previous_status=previous_status,
        rankings=rankings,
        liquid=liquid,
        r=r,
        r2=r2,
        slope=slope,
        noise=noise,
        windows=windows,
        cfg=cfg,
    )

    ledger = build_coverage_ledger(
        window_status=status,
        pre_status=pre_status,
        warnings=warnings,
        has_history=has_history,
        windows=windows,
    )
    end_day = np.array([int(inst.cutoff_day) if inst.cutoff_day is not None else int(cutoff_day) for inst in instruments], dtype=np.int64)
    winners = build_pure_return_winners(
        rankings, r_matrix=r, start_matrix=start_day, cutoff_day=cutoff_day, window_days=windows, end_days=end_day
    )
    winners_liquid = build_pure_return_winners(
        rankings,
        r_matrix=r,
        start_matrix=start_day,
        cutoff_day=cutoff_day,
        window_days=windows,
        ranking_of=lambda window: window.native0_liquid,
        end_days=end_day,
    )
    return SnapshotComputation(
        cutoff_day=cutoff_day,
        isins=isins,
        windows=windows,
        target_start=target_start,
        status=status,
        start_day=start_day,
        n_obs=n_obs,
        n_exp=n_exp,
        r=r,
        p0=p0,
        p1=p1,
        m=m_arr,
        r2=r2,
        slope_pct=slope,
        noise_pct=noise,
        mdd=mdd,
        vol_cov=vol_cov,
        wflags=wflags,
        ups=ups,
        previous_status=previous_status,
        pre_status=pre_status,
        warnings=warnings,
        has_history=has_history,
        rankings=rankings,
        ledger=ledger,
        winners=winners,
        overall_max=overall_max_return(winners),
        input_hash=hasher.hexdigest(),
        observed=observed,
        jump_reviews=jump_reviews,
        turnover=turnover,
        liquid=liquid,
        winners_liquid=winners_liquid,
        overall_max_liquid=overall_max_return(winners_liquid),
        fx=fx,
        method_comparison=method_comparison,
        end_day=end_day,
    )
