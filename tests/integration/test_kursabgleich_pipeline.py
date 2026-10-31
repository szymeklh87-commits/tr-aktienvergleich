"""Kursabgleich im täglichen Lauf (ab 1.20.0) mit der DEMO-Börse: Abruf, Auswahlregel, Nachweis, Wirkung auf die Ranglisten.

Die DEMO-Börse (``providers.demo.DemoExchangeSources``) liefert für alle Aktien an XETR eine Tagesdatei je Sitzung mit den
Kursen des DEMO-Anbieters; zwei Aktien weichen an Tagen vor allen Zeiträumen ab (ohne Wirkung auf die Ranglisten). Ein
zweiter Lauf setzt den Kurs der Börse einer Aktie am Stichtag deutlich höher – die Ranglisten müssen sich ändern und der
Nachweis muss den Auslöser nennen.
"""

from __future__ import annotations

import dataclasses
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from traktien.analytics import kursabgleich as ka
from traktien.config import load_method_config, load_pipeline_config
from traktien.jobs.daily import EXIT_OK, DailyRun, RunOptions
from traktien.jobs.sources import demo_sources
from traktien.providers.boersen import DayFile, OfficialBar
from traktien.providers.demo import DEMO_EXCHANGE_SOURCE, DemoExchangeSources
from traktien.providers.exchanges import load_exchange_table
from traktien.store.db import connect
from traktien.util import crypto


class LiftOnCutoff(DemoExchangeSources):
    """DEMO-Börse, die den Schlusskurs einer Aktie am Stichtag um 30 % höher meldet als der DEMO-Anbieter."""

    def __init__(self, provider, isin: str, day: int) -> None:
        super().__init__(provider)
        self.lift = (isin, day)

    def day_file(self, source: str, day: int) -> DayFile:
        f = super().day_file(source, day)
        if day == self.lift[1] and self.lift[0] in f.bars:
            bar = f.bars[self.lift[0]]
            f.bars[self.lift[0]] = OfficialBar(day=bar.day, close=round(bar.close * 1.3, 4), volume=bar.volume)
        return f


class KursabgleichPipelineTests(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="kursabgleich-"))
        self.method = load_method_config()
        self.pipeline = load_pipeline_config()
        self.table = load_exchange_table()

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def run_demo(self, folder: Path, sources):
        conn = connect(folder / "state.sqlite")
        self.addCleanup(conn.close)
        outcome = DailyRun(conn, folder, sources, self.method, self.pipeline, self.table, None, RunOptions()).execute()
        self.assertEqual(outcome.exit_code, EXIT_OK, outcome.message)
        return outcome, conn

    @staticmethod
    def load(folder: Path, snapshot_id: str, name: str):
        blob = (folder / "snapshots" / snapshot_id / name).read_bytes()
        return json.loads(crypto.unpack(blob, None, f"snapshots/{snapshot_id}/{name}"))

    def test_demo_run_reconciles_xetra_and_records_each_correction(self):
        folder = self.dir / "a"
        outcome, conn = self.run_demo(folder, demo_sources(kursabgleich=True))
        manifest = self.load(folder, outcome.snapshot_id, "manifest.bin")
        summary = manifest["kursabgleich"]
        self.assertEqual(summary["regel"], ka.RULE_VERSION)
        self.assertEqual(manifest["versions"]["kursabgleich"], ka.RULE_VERSION)
        self.assertEqual(summary["aktien_mit_kurskorrektur"], 2)
        source = summary["quellen"][DEMO_EXCHANGE_SOURCE]
        self.assertEqual(source["korrektur:amtlicher_schlusskurs"], 1)
        self.assertEqual(source["korrektur:tag_ohne_umsatz"], 1)
        self.assertGreater(source["status:bestaetigt"], 20)
        # beide Abweichungen liegen vor allen Zeiträumen: keine Rangliste ändert sich
        self.assertEqual(summary["ranglisten"]["platz1_anders"], 0)
        self.assertEqual(summary["ranglisten"]["erste10_andere_aktien"], 0)
        payload = self.load(folder, outcome.snapshot_id, "kursabgleich.bin")
        self.assertEqual(payload["schema"], "tr-kursabgleich/1")
        reasons = sorted(c["grund"] for case in payload["faelle"] for c in case["korrekturen"])
        self.assertEqual(reasons, ["amtlicher_schlusskurs", "tag_ohne_umsatz"])
        for case in payload["faelle"]:
            for c in case["korrekturen"]:
                self.assertIsNotNone(c["alt"])
                self.assertNotEqual(c["alt"], c["neu"])
        self.assertGreater(payload["luecken_gesamt"], 0)  # Spitzenplätze an Börsen ohne Quelle werden genannt
        stored = conn.execute("SELECT reason, source, rule FROM kurskorrektur ORDER BY reason").fetchall()
        self.assertEqual([tuple(r) for r in stored], [("amtlicher_schlusskurs", DEMO_EXCHANGE_SOURCE, ka.RULE_VERSION), ("tag_ohne_umsatz", DEMO_EXCHANGE_SOURCE, ka.RULE_VERSION)])
        days = conn.execute("SELECT COUNT(*) FROM boersenquelle_tag WHERE source = ? AND status = 'ok'", (DEMO_EXCHANGE_SOURCE,)).fetchone()[0]
        self.assertGreater(days, 90)

    def test_without_exchange_source_nothing_changes(self):
        """Ohne angebundene Quelle der Börsen (Tests des Laufs, ältere Zustände): kein Kursabgleich, kein Nachweis im Stand."""
        folder = self.dir / "ohne"
        outcome, conn = self.run_demo(folder, demo_sources())
        manifest = self.load(folder, outcome.snapshot_id, "manifest.bin")
        self.assertIsNone(manifest.get("kursabgleich"))
        self.assertNotIn("kursabgleich", manifest["versions"])
        self.assertFalse((folder / "snapshots" / outcome.snapshot_id / "kursabgleich.bin").exists())
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM kurskorrektur").fetchone()[0], 0)

    def test_missing_trading_day_of_the_main_source_is_filled_from_the_exchange(self):
        """Fehlt der Hauptquelle ein Handelstag mit Umsatz, den die Börse meldet, ergänzt der Abgleich ihn (Grund
        „fehlender_kurstag“) – hier der Stichtag einer Aktie an XETR."""
        sources = demo_sources(kursabgleich=True)
        base_provider = sources.prices
        xetr = sorted((i for i in base_provider.instruments.values() if i.exchange_key == "XETR" and i.pattern in ("steady_mild", "steady_strong")), key=lambda i: i.isin)
        target = xetr[-1]

        class WithoutCutoff:
            name = base_provider.name

            def __init__(self, inner):
                self.inner = inner

            def __getattr__(self, item):
                return getattr(self.inner, item)

            def fetch_history(self, symbol, start, end, *, session_final=None):
                history = self.inner.fetch_history(symbol, start, end, session_final=session_final)
                if symbol != target.symbol:
                    return history
                keep = history.days < history.days[-1]
                return dataclasses.replace(history, days=history.days[keep], open=history.open[keep], high=history.high[keep], low=history.low[keep],
                                           close=history.close[keep], volume=history.volume[keep],
                                           close_raw=history.close_raw[keep] if history.close_raw is not None else None)

        folder = self.dir / "luecke"
        outcome, conn = self.run_demo(folder, dataclasses.replace(sources, prices=WithoutCutoff(base_provider)))
        manifest = self.load(folder, outcome.snapshot_id, "manifest.bin")
        cutoff = int(manifest["cutoff_day"])
        series = self.load(folder, outcome.snapshot_id, f"series/{target.isin}.bin")
        self.assertEqual(series["d"][-1], cutoff)
        added = [c for c in series["korrekturen"] if c["d"] == cutoff]
        self.assertEqual([c["grund"] for c in added], ["fehlender_kurstag"])
        self.assertIsNone(added[0]["alt"])
        row = conn.execute("SELECT reason, old_close FROM kurskorrektur WHERE day = ? AND reason = 'fehlender_kurstag'", (cutoff,)).fetchone()
        self.assertEqual((row[0], row[1]), ("fehlender_kurstag", None))

    def test_correction_on_cutoff_day_changes_rankings_and_names_the_trigger(self):
        base = self.dir / "b"
        outcome, _ = self.run_demo(base, demo_sources(kursabgleich=True))
        instruments = self.load(base, outcome.snapshot_id, "instruments.bin")
        manifest = self.load(base, outcome.snapshot_id, "manifest.bin")
        cutoff = int(manifest["cutoff_day"])
        keys = instruments["exchange_key"]
        win = self.load(base, outcome.snapshot_id, "windows/20.full.bin")
        order = [int(i) for i in win["orders"]["v0"]]
        target = next(i for i in order[1:15] if keys[i] == "XETR")
        isin = instruments["isin"][target]

        sources = demo_sources(kursabgleich=True)
        lifted = dataclasses.replace(sources, exchanges=LiftOnCutoff(sources.prices, isin, cutoff))
        folder = self.dir / "c"
        outcome2, conn2 = self.run_demo(folder, lifted)
        summary = self.load(folder, outcome2.snapshot_id, "manifest.bin")["kursabgleich"]
        self.assertGreater(summary["ranglisten"]["platz1_anders"], 0)
        payload = self.load(folder, outcome2.snapshot_id, "kursabgleich.bin")
        changed = [r for r in payload["ranglisten"] if r["platz1_anders"]]
        self.assertTrue(changed)
        # reine Renditeranglisten (Gewichtung 0): die korrigierte Aktie ist der neue Platz 1 und als Auslöser genannt
        pure = [r for r in changed if r["w"] == 0]
        self.assertTrue(pure)
        self.assertTrue(all(r["nachher"][0] == target and target in r["ausloeser"] for r in pure))
        # jede Rangliste, in der sie vorher oder nachher Platz 1 ist, nennt sie als Auslöser (sonst wirkt sie über die Perzentile)
        self.assertTrue(all(target in r["ausloeser"] for r in changed if target in (r["vorher"][:1] + r["nachher"][:1])))
        series = self.load(folder, outcome2.snapshot_id, f"series/{isin}.bin")
        on_cutoff = [c for c in series["korrekturen"] if c["d"] == cutoff]
        self.assertEqual(len(on_cutoff), 1)
        self.assertEqual(on_cutoff[0]["grund"], "amtlicher_schlusskurs")
        k = series["d"].index(cutoff)
        self.assertAlmostEqual(series["c"][k], on_cutoff[0]["neu"], places=6)
        self.assertAlmostEqual(on_cutoff[0]["neu"] / on_cutoff[0]["alt"], 1.3, places=3)
        self.assertEqual(series["kursabgleich"]["status"], "uebernommen")


if __name__ == "__main__":
    unittest.main()
