"""Addierbare Abdeckungsbilanz (Abschnitt 15).

Jedes Instrument erhält je Fenster genau einen priorisierten Hauptstatus; die Summe
der Hauptstatus ergibt exakt das Universum. Hinweise (Bitmasken) werden getrennt
gezählt und erhöhen keine Aktienzahl.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .codes import RETURN_PUBLISHABLE, TREND_ELIGIBLE, InstrumentWarning, Status

INSTRUMENT_READY = 0  # Instrumentebene: Schlusskurs am Stichtag vorhanden


class LedgerError(AssertionError):
    pass


@dataclass
class CoverageLedger:
    universe_total: int
    instrument_counts: dict[int, int]
    per_window: list[dict]
    warning_counts: dict[int, int]
    identified: int
    histories_loaded: int
    with_any_return_window: int

    def as_dict(self) -> dict:
        return {
            "universe_total": self.universe_total,
            "identified": self.identified,
            "histories_loaded": self.histories_loaded,
            "with_any_return_window": self.with_any_return_window,
            "instrument_level": {str(k): v for k, v in sorted(self.instrument_counts.items())},
            "per_window": self.per_window,
            "warnings": {str(k): v for k, v in sorted(self.warning_counts.items())},
            "sum_check": True,
        }


def instrument_level_status(pre_status: np.ndarray, window_status: np.ndarray) -> np.ndarray:
    """Fensterunabhängiger Hauptstatus: Vorabstatus, sonst Stichtagsstatus, sonst bereit."""
    n = len(pre_status)
    result = np.zeros(n, dtype=np.uint8)
    for i in range(n):
        if pre_status[i]:
            result[i] = pre_status[i]
            continue
        first = int(window_status[i, 0]) if window_status.shape[1] else 0
        if first in (Status.MARKT_AM_STICHTAG_GESCHLOSSEN, Status.KURS_AM_STICHTAG_FEHLT):
            result[i] = first
        else:
            result[i] = INSTRUMENT_READY
    return result


def build_coverage_ledger(
    *,
    window_status: np.ndarray,
    pre_status: np.ndarray,
    warnings: np.ndarray,
    has_history: np.ndarray,
    windows: range,
) -> CoverageLedger:
    n = int(window_status.shape[0])
    if len(pre_status) != n or len(warnings) != n or len(has_history) != n:
        raise LedgerError("Inkonsistente Längen in der Abdeckungsbilanz")

    per_window: list[dict] = []
    for col, h in enumerate(windows):
        column = window_status[:, col]
        if np.any(column == 0):
            raise LedgerError(f"Fenster {h}: Instrument ohne Hauptstatus")
        values, counts = np.unique(column, return_counts=True)
        by_status = {str(int(v)): int(c) for v, c in zip(values, counts)}
        total = int(counts.sum())
        if total != n:
            raise LedgerError(f"Fenster {h}: Summe {total} ≠ Universum {n}")
        v_count = int(np.isin(column, [int(s) for s in RETURN_PUBLISHABLE]).sum())
        u_count = int(np.isin(column, [int(s) for s in TREND_ELIGIBLE]).sum())
        per_window.append({"h": h, "return_eligible": v_count, "trend_eligible": u_count, "by_status": by_status})

    level = instrument_level_status(pre_status, window_status)
    values, counts = np.unique(level, return_counts=True)
    instrument_counts = {int(v): int(c) for v, c in zip(values, counts)}
    if sum(instrument_counts.values()) != n:
        raise LedgerError("Instrumentebene: Summe ungleich Universum")

    warning_counts: dict[int, int] = {}
    for bit in InstrumentWarning:
        count = int(((warnings.astype(np.uint64) >> np.uint64(int(bit))) & np.uint64(1)).sum())
        if count:
            warning_counts[int(bit)] = count

    publishable = np.isin(window_status, [int(s) for s in RETURN_PUBLISHABLE]).any(axis=1)
    # Eindeutig zugeordnet = Identität geklärt (auch wenn der Typ kein Aktieninstrument ist).
    unresolved = [int(Status.ISIN_UNGUELTIG), int(Status.IDENTITAET_OFFEN), int(Status.IDENTITAET_UNKLAR)]
    identified = int(np.sum(~np.isin(pre_status, unresolved)))
    return CoverageLedger(
        universe_total=n,
        instrument_counts=instrument_counts,
        per_window=per_window,
        warning_counts=warning_counts,
        identified=identified,
        histories_loaded=int(np.sum(has_history)),
        with_any_return_window=int(publishable.sum()),
    )
