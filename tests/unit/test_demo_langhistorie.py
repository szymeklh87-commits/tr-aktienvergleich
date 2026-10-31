"""Synthetische Vorgeschichte im DEMO für den Forschungslauf des Depot-Optimierers (``DemoLanghistorie``): lückenloser
Anschluss an die DEMO-Reihe, Drift des Musters, deterministisch unabhängig vom angefragten Zeitraum, Sonderfälle ohne
Vorgeschichte, exakte Gleichstände bleiben, Wechselkurse ohne Sprung am Anschluss. Die DEMO-Reihen selbst bleiben unverändert.
SYNTHETISCHE Daten."""

from __future__ import annotations

import datetime as dt
import unittest

import numpy as np

from traktien.providers import demo
from traktien.providers.base import NoDataError
from traktien.util.timeutil import date_to_day


class DemoLanghistorieTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.basis = demo.DemoProvider()
        cls.lang = demo.DemoLanghistorie(cls.basis)
        cls.start = date_to_day(demo.DEMO_LANG_START)

    def inst(self, pattern: str):
        return next(i for i in sorted(self.basis.instruments.values(), key=lambda i: i.seed) if i.pattern == pattern)

    def test_continuous_junction_and_pattern_drift(self):
        for pattern in ("steady_strong", "falling", "noisy_flat"):
            inst = self.inst(pattern)
            ref = self.basis._history(inst)
            h = self.lang.fetch_history(inst.symbol, self.start, int(ref.days[0]) - 1)
            self.assertLess(int(h.days[-1]), int(ref.days[0]))
            self.assertGreater(int(ref.days[0]) - int(h.days[-1]), 0)
            sprung = abs(np.log(float(ref.close[0]) / float(h.close[-1])))
            drift, vol = demo._muster_drift(inst)
            self.assertLess(sprung, abs(drift) + 5 * vol, f"{pattern}: kein Sprung am Anschluss")
            jahre = (int(h.days[-1]) - int(h.days[0])) / 365.25
            self.assertGreater(jahre, 4.5)
            mittel = float(np.mean(np.diff(np.log(h.close))))
            self.assertAlmostEqual(mittel, drift, delta=4 * vol / np.sqrt(len(h.close)) + 1e-4, msg=pattern)
            self.assertEqual(h.currency, ref.currency)
            self.assertEqual(h.unit_factor, ref.unit_factor)

    def test_deterministic_and_independent_of_requested_range(self):
        inst = self.inst("steady_mild")
        first = int(self.basis._history(inst).days[0])
        a = self.lang.fetch_history(inst.symbol, self.start, first - 1)
        b = demo.DemoLanghistorie(demo.DemoProvider()).fetch_history(inst.symbol, first - 400, first - 100)
        keep = (a.days >= first - 400) & (a.days <= first - 100)
        np.testing.assert_array_equal(a.days[keep], b.days)
        np.testing.assert_allclose(a.close[keep], b.close)

    def test_special_cases_and_ties(self):
        with self.assertRaises(NoDataError):
            self.lang.fetch_history(self.inst("recent_ipo").symbol, self.start, date_to_day(dt.date(2026, 1, 1)))
        with self.assertRaises(NoDataError):
            self.lang.fetch_history(self.inst("split_unadjusted").symbol, self.start, date_to_day(dt.date(2026, 1, 1)))
        a, b = self.inst("twin_a"), self.inst("twin_b")
        ha = self.lang.fetch_history(a.symbol, self.start, date_to_day(dt.date(2026, 1, 1)))
        hb = self.lang.fetch_history(b.symbol, self.start, date_to_day(dt.date(2026, 1, 1)))
        np.testing.assert_array_equal(ha.close, hb.close)

    def test_index_and_fund_series_and_fx(self):
        for symbol in ("EUNL.DE", "^GSPC"):
            ref = self.basis._fetch_reihe(symbol, date_to_day(demo.DEMO_START), date_to_day(dt.date(2026, 10, 12)))
            h = self.lang.fetch_history(symbol, self.start, int(ref.days[0]) - 1)
            self.assertLess(abs(np.log(float(ref.close[0]) / float(h.close[-1]))), 0.05, symbol)
        fx = self.lang.fx.fetch_history(self.start)
        alt = demo.DemoFxSource().fetch().rows
        erster_alt = min(d for d, _c, _r in alt)
        self.assertTrue(all(d < erster_alt for d, _c, _r in fx.rows))
        letzte = {c: r for d, c, r in sorted(fx.rows)}
        anschluss = {c: r for d, c, r in sorted(alt, reverse=True)}
        for c in letzte:
            self.assertLess(abs(letzte[c] / anschluss[c] - 1.0), 0.005, f"{c}: kein Sprung")

    def test_demo_series_and_default_calendar_unchanged(self):
        erster = int(demo.demo_calendars().sessions("XETR", 0, 10**6)[0]) - date_to_day(demo.DEMO_START - dt.timedelta(days=60))
        self.assertTrue(0 <= erster <= 4, "Standardkalender beginnt wie bisher 60 Tage vor dem ersten DEMO-Kurs")
        self.assertLessEqual(int(self.lang.calendars.sessions("XETR", 0, 10**6)[0]), date_to_day(demo.DEMO_LANG_START))
        inst = self.inst("steady_strong")
        np.testing.assert_array_equal(demo.DemoProvider()._history(inst).close, self.basis._history(inst).close)


if __name__ == "__main__":
    unittest.main()
