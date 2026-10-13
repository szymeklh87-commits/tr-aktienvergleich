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
from .quality import JumpReview, SplitEvent, classify_window, review_jumps, spans_any, zero_volume_outliers
from .ranking import WindowRanking, pure_return_subset, rank_window
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

    @property
    def n_instruments(self) -> int:
        return len(self.isins)

    def isin_of(self, idx: int) -> str:
        return self.isins[idx]


def compute_snapshot(
    instruments: list[InstrumentData],
    cutoff_day: int,
    cfg: MethodConfig,
    fx: FxRates | None = None,
) -> SnapshotComputation:
    cfg.validate()
    isins = [inst.isin for inst in instruments]
    if isins != sorted(isins) or len(set(isins)) != len(isins):
        raise ValueError("Instrumente müssen eindeutig und aufsteigend nach ISIN sortiert sein")

    windows = tuple(cfg.windows())
    n = len(instruments)
    w = len(windows)
    target_start = np.array([cutoff_day - h for h in windows], dtype=np.int64)

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
    pre_status = np.zeros(n, dtype=np.uint8)
    warnings = np.zeros(n, dtype=np.uint32)
    has_history = np.zeros(n, dtype=bool)
    observed: dict[int, ObservedSeries] = {}
    jump_reviews: dict[int, JumpReview] = {}
    turnover: list[TurnoverResult] = [TurnoverResult("keine_kurse") for _ in range(n)]

    hasher = hashlib.sha256()
    hasher.update(f"cutoff={cutoff_day};n={n};".encode())

    for i, inst in enumerate(instruments):
        warn = int(inst.warnings)
        hasher.update(f"|{inst.isin}:{inst.pre_status}:{int(inst.hold_all)}".encode())
        if inst.pre_status:
            pre_status[i] = inst.pre_status
            status[i, :] = inst.pre_status
            warnings[i] = warn
            continue
        if inst.sessions is None or len(inst.sessions) == 0:
            pre_status[i] = Status.KALENDER_FEHLT
            status[i, :] = Status.KALENDER_FEHLT
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
        keep = days <= cutoff_day
        days, close, volume = days[keep], close[keep], volume[keep]
        if len(days) == 0:
            pre_status[i] = Status.KEINE_KURSDATEN
            status[i, :] = Status.KEINE_KURSDATEN
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
        hasher.update(obs_days.tobytes())
        hasher.update(obs_close.tobytes())
        hasher.update(np.where(np.isfinite(obs_vol), obs_vol, -1.0).tobytes())
        for event in inst.splits:
            hasher.update(f"s{event.day}:{event.factor!r}".encode())
        for day, decision in sorted(inst.reviewed_jumps.items()):
            hasher.update(f"j{day}:{decision}".encode())

        if len(obs_days) == 0:
            pre_status[i] = Status.KEINE_KURSDATEN
            status[i, :] = Status.KEINE_KURSDATEN
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

        result = compute_turnover(
            obs_days,
            obs_close,
            obs_vol,
            sessions,
            cutoff_day,
            split_days=split_days,
            currency=inst.currency,
            unit_factor=inst.unit_factor,
            fx=fx,
            n_sessions=cfg.turnover_sessions,
            min_positive=cfg.turnover_min_positive,
        )
        turnover[i] = result
        hasher.update(f"|t{result.fingerprint()}".encode())
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
        zero_volume_days = set(zero_volume_outliers(obs_days, obs_close, obs_vol, cfg.zero_volume_move, inst.reviewed_jumps).tolist())
        if zero_volume_days:
            warnings[i] = warn = warn | (1 << InstrumentWarning.NULLUMSATZ_AUSREISSER)
        end_outlier = int(obs_days[-1]) in zero_volume_days
        cache: dict[int, tuple] = {}

        for col, h in enumerate(windows):
            rw = resolve_window(obs_days, sessions, cutoff_day, h, cfg.anchor_max_gap_days)
            if rw.start_session is not None:
                start_day[i, col] = rw.start_session
            if not rw.ok:
                status[i, col] = rw.status
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
                held_in = inst.hold_all or zero_volume_edge or spans_any(held, int(obs_days[j]), cutoff_day)
                flags = 0
                if metrics.sst is not None and metrics.r2 is None and metrics.sst > cfg.sst_rel_tolerance * metrics.n * float(np.mean(window_prices)) ** 2:
                    flags |= 1 << WindowWarning.R2_NUMERISCH_INSTABIL
                share = impulse_share(window_prices)
                if share is not None and share > cfg.impulse_share and abs(metrics.r) >= cfg.impulse_min_abs_return:
                    flags |= 1 << WindowWarning.IMPULSTAG
                if len(split_days) and spans_any(split_days, int(obs_days[j]), cutoff_day):
                    flags |= 1 << WindowWarning.SPLIT_IM_FENSTER
                if len(released) and spans_any(released, int(obs_days[j]), cutoff_day):
                    flags |= 1 << WindowWarning.GEPRUEFTER_SPRUNG_IM_FENSTER
                if takeover_pattern(window_prices, jump_min=cfg.takeover_jump_min, calm_max=cfg.takeover_calm_max, calm_sessions=cfg.takeover_calm_sessions):
                    flags |= 1 << WindowWarning.UEBERNAHMEMUSTER
                window_status = classify_window(
                    rw, vol_positive=vol_positive, held_in_window=held_in, metrics=metrics, cfg=cfg
                )
                record = (metrics, vol_positive, flags, window_status)
                cache[j] = record
            metrics, vol_positive, flags, window_status = record
            status[i, col] = window_status
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

    # Menge L: Ø Tagesumsatz bestimmt und mindestens die Schwelle (indikativ in USD)
    liquid = np.array([t.determined and t.avg_usd >= cfg.turnover_threshold_usd for t in turnover], dtype=bool)
    rankings: dict[int, WindowRanking] = {}
    publishable_codes = [int(s) for s in RETURN_PUBLISHABLE]
    for col, h in enumerate(windows):
        column = status[:, col]
        v_idx = np.nonzero(np.isin(column, publishable_codes))[0].astype(np.int64)
        u_idx = np.nonzero(column == Status.TREND_BEWERTBAR)[0].astype(np.int64)
        rankings[h] = rank_window(h, v_idx, u_idx, r[:, col], r2[:, col], slope[:, col], noise[:, col])
        rankings[h].native0_liquid = pure_return_subset(rankings[h].native0, liquid, r[:, col])

    ledger = build_coverage_ledger(
        window_status=status,
        pre_status=pre_status,
        warnings=warnings,
        has_history=has_history,
        windows=windows,
    )
    winners = build_pure_return_winners(
        rankings, r_matrix=r, start_matrix=start_day, cutoff_day=cutoff_day, window_days=windows
    )
    winners_liquid = build_pure_return_winners(
        rankings,
        r_matrix=r,
        start_matrix=start_day,
        cutoff_day=cutoff_day,
        window_days=windows,
        ranking_of=lambda window: window.native0_liquid,
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
    )
