"""Spitzenreiter ohne auffällige Aktien (ab 1.14, Simons Wahl „aussagekräftiger“) – SYNTHETISCHE Daten.

Kaum Umsatz (Ø Tagesumsatz unter 1 Mio. USD) oder ein Einzelsprung im Zeitraum (ein Handelstag erklärt mehr als die
Hälfte der Kursbewegung) → die Aktie bleibt in der vollständigen Rangliste, ist aber nicht „Spitzenreiter ohne
Auffällige“. Der Platz in der vollständigen Rangliste steht dabei."""

from __future__ import annotations

import datetime as dt
import unittest

import numpy as np

from tests.helpers import day, make_instrument, test_isin, weekday_sessions
from traktien.analytics.codes import WindowWarning
from traktien.analytics.engine import compute_snapshot
from traktien.config import MethodConfig
from traktien.publish import snapshot_writer as sw

SESSIONS = weekday_sessions(dt.date(2026, 5, 1), dt.date(2026, 10, 12))
CUTOFF = day(2026, 10, 12)


class CleanWinnerTests(unittest.TestCase):
    def setUp(self):
        n = len(SESSIONS)
        steady = lambda rate: (lambda k: 50.0 * (1 + rate) ** k)  # noqa: E731

        def jump(k: int) -> float:  # ruhig, dann ein Sprung um 80 % fünf Sitzungen vor dem Stichtag
            return 50.0 * (1.0005**k) * (1.8 if k >= n - 5 else 1.0)

        self.instruments = [
            make_instrument(test_isin(1), SESSIONS, steady(0.004), volume=5.0),  # stärkste Rendite, kaum Umsatz
            make_instrument(test_isin(2), SESSIONS, jump, volume=2_000_000.0),  # Einzelsprung
            make_instrument(test_isin(3), SESSIONS, steady(0.002), volume=2_000_000.0),  # unauffällig
            make_instrument(test_isin(4), SESSIONS, steady(0.001), volume=2_000_000.0),
        ]
        for inst in self.instruments:
            inst.currency = "USD"
        self.comp = compute_snapshot(self.instruments, CUTOFF, MethodConfig(), workers=1)
        metas = [sw.InstrumentMeta(isin=x.isin, name=x.isin, tr_name=x.isin, sessions=SESSIONS, calendar="XNYS") for x in self.instruments]
        self.writer = sw.SnapshotWriter(self.comp, metas, MethodConfig(), snapshot_id="s", key=None)

    def test_flags_are_set_as_expected(self):
        col = 29
        self.assertTrue(self.comp.wflags[1, col] & (1 << WindowWarning.IMPULSTAG), "Einzelsprung erkannt")
        quiet = self.writer.quiet_mask()
        self.assertEqual(quiet.tolist(), [False, True, True, True], "Ø Umsatz 5 Stück × 50 USD: kaum Umsatz")

    def test_clean_winners_skip_flagged_stocks_and_name_their_rank(self):
        overview = self.writer.overview_payload()
        row = overview["winners_klar"][29]  # 30 Tage
        full = overview["winners"][29]
        self.assertEqual(full["entries"][0]["idx"], 1, "vollständige Rangliste: Einzelsprung vorne (+80 %)")
        self.assertEqual(row["entries"][0]["idx"], 2, "ohne Auffällige: die unauffällige Aktie")
        self.assertEqual(row["rank"], 3, "Platz 3 der vollständigen Rangliste (hinter Einzelsprung und Kaum Umsatz)")
        self.assertEqual(row["M"], 2)
        self.assertEqual(row["entries"][0]["end"], CUTOFF)
        self.assertIn("text", overview["klar_regel"])
        self.assertEqual(len(overview["winners_klar"]), 90)
        self.assertEqual(len(overview["winners_l_klar"]), 90)


if __name__ == "__main__":
    unittest.main()
