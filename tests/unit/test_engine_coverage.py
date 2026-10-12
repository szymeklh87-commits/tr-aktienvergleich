"""T38 und T40: Abdeckungsbilanz und Reproduzierbarkeit (synthetische Daten)."""

from __future__ import annotations

import copy
import datetime as dt
import unittest

import numpy as np

from traktien.analytics.codes import InstrumentWarning, Status
from traktien.analytics.engine import InstrumentData, compute_snapshot
from traktien.config import MethodConfig
from tests.helpers import day, make_instrument, test_isin, weekday_sessions

CFG = MethodConfig()


def mixed_universe():
    sessions = weekday_sessions(dt.date(2026, 4, 1), dt.date(2026, 10, 12))
    cutoff = day(2026, 10, 12)
    instruments = [
        make_instrument(test_isin(1), sessions, lambda k: 10 + 0.05 * k, volume=1000, warnings=1 << InstrumentWarning.TYP_UNKLAR),
        make_instrument(test_isin(2), sessions, lambda k: 30 - 0.05 * k, volume=1000, warnings=(1 << InstrumentWarning.TYP_UNKLAR) | (1 << InstrumentWarning.OTC_NOTIERUNG)),
        make_instrument(test_isin(3), sessions[-10:], lambda k: 5 + k, volume=1000),
        InstrumentData(isin=test_isin(4), pre_status=int(Status.IDENTITAET_UNKLAR)),
        InstrumentData(isin=test_isin(5), pre_status=int(Status.KEIN_AKTIENINSTRUMENT)),
        InstrumentData(isin=test_isin(6), sessions=sessions),  # keine Kursdaten
        make_instrument(test_isin(7), sessions[:-1], lambda k: 7 + 0.01 * k, volume=1000),  # Stichtag fehlt
    ]
    for inst in instruments:
        if inst.sessions is not None and inst.isin != test_isin(6):
            inst.sessions = sessions
    instruments.sort(key=lambda x: x.isin)
    return instruments, cutoff


class CoverageTests(unittest.TestCase):
    def test_T38_main_status_sums_to_universe_and_warnings_do_not_double(self):
        instruments, cutoff = mixed_universe()
        result = compute_snapshot(instruments, cutoff, CFG)
        ledger = result.ledger.as_dict()
        self.assertEqual(ledger["universe_total"], 7)
        for window in ledger["per_window"]:
            self.assertEqual(sum(window["by_status"].values()), 7)
        self.assertEqual(sum(ledger["instrument_level"].values()), 7)
        self.assertEqual(ledger["warnings"][str(int(InstrumentWarning.TYP_UNKLAR))], 2)
        self.assertEqual(ledger["warnings"][str(int(InstrumentWarning.OTC_NOTIERUNG))], 1)
        self.assertEqual(ledger["histories_loaded"], 4)
        self.assertEqual(ledger["identified"], 6)

    def test_status_categories_are_distinct(self):
        instruments, cutoff = mixed_universe()
        result = compute_snapshot(instruments, cutoff, CFG)
        col = 29
        by_isin = {isin: int(result.status[i, col]) for i, isin in enumerate(result.isins)}
        self.assertEqual(by_isin[test_isin(2)], Status.NICHT_STEIGEND)
        self.assertEqual(by_isin[test_isin(3)], Status.HISTORIE_ZU_KURZ)
        self.assertEqual(by_isin[test_isin(6)], Status.KEINE_KURSDATEN)
        self.assertEqual(by_isin[test_isin(7)], Status.KURS_AM_STICHTAG_FEHLT)
        self.assertNotEqual(by_isin[test_isin(2)], by_isin[test_isin(6)])

    def test_T40_repeated_execution_is_reproducible(self):
        instruments, cutoff = mixed_universe()
        a = compute_snapshot(copy.deepcopy(instruments), cutoff, CFG)
        b = compute_snapshot(copy.deepcopy(instruments), cutoff, CFG)
        self.assertEqual(a.input_hash, b.input_hash)
        for name in ("status", "start_day", "n_obs", "n_exp", "r", "r2", "slope_pct", "noise_pct", "mdd", "vol_cov"):
            np.testing.assert_array_equal(getattr(a, name), getattr(b, name), err_msg=name)
        for h in a.rankings:
            self.assertEqual(a.rankings[h].native0.order.tolist(), b.rankings[h].native0.order.tolist())
            for w in a.rankings[h].trend:
                np.testing.assert_array_equal(a.rankings[h].trend[w].order, b.rankings[h].trend[w].order)
                np.testing.assert_array_equal(a.rankings[h].trend[w].scores, b.rankings[h].trend[w].scores)

    def test_input_hash_changes_when_data_changes(self):
        instruments, cutoff = mixed_universe()
        a = compute_snapshot(copy.deepcopy(instruments), cutoff, CFG)
        changed = copy.deepcopy(instruments)
        changed[0].close = changed[0].close.copy()
        changed[0].close[-1] *= 1.0001
        b = compute_snapshot(changed, cutoff, CFG)
        self.assertNotEqual(a.input_hash, b.input_hash)

    def test_unsorted_input_is_rejected(self):
        instruments, cutoff = mixed_universe()
        with self.assertRaises(ValueError):
            compute_snapshot(list(reversed(instruments)), cutoff, CFG)


if __name__ == "__main__":
    unittest.main()
