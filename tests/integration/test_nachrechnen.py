"""Unabhängige Nachrechnung (``tests/live/nachrechnen.py``) gegen DEMO-Stände – SYNTHETISCHE Daten.

Die Nachrechnung soll mit echten Daten belegen, dass die App richtig rechnet. Dafür muss sie selbst stimmen: Auf
fehlerfreien Ständen (Stand mit Schlusskursen und Zwischenstand) meldet sie keine Abweichung, und jede absichtlich
eingebaute Abweichung – eine Rendite, ein Kurs, eine Rangfolge, ein R², eine Häufigkeit, eine Umsatzgruppe – findet
sie. Der Vergleich mit ChatGPT zählt Übereinstimmungen über Prüfwerte, ohne Namen oder ISINs zu kennen.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from unittest import mock

from traktien.util import crypto

from tests.live import nachrechnen

REPO = Path(__file__).resolve().parents[2]
PASSPHRASE = "nachrechnen-test-passphrase"


def _failed(report: dict) -> Counter:
    out: Counter = Counter()
    for stand in report["staende"]:
        for name, value in stand["pruefungen"].items():
            out[name] += value["abweichend"]
    z = report.get("zwischenstand_gegen_schlusskurse") or {}
    for name, value in (z.get("pruefungen") or {}).items():
        out[name] += value["abweichend"]
    return +out


class NachrechnungTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = Path(tempfile.mkdtemp(prefix="nachrechnen-test-"))
        site = cls.tmp / "site"
        command = [
            sys.executable, "-m", "traktien", "demo", "--fresh", "--zwischenstand",
            "--state-dir", str(cls.tmp / "state"), "--site", str(site), "--app-dist", str(REPO / "app" / "dist"), "--passphrase", PASSPHRASE,
        ]  # fmt: skip
        env = dict(os.environ, PYTHONPATH=str(REPO / "backend"), LOG_LEVEL="WARNING")
        subprocess.run(command, check=True, cwd=REPO, env=env, capture_output=True, text=True, timeout=600)
        cls.site = site
        status = json.loads((site / "data" / "status.json").read_text(encoding="utf-8"))
        cls.official = status["latest_official_snapshot_id"]
        cls.intraday = status["latest_snapshot_id"]
        descriptor = json.loads((site / "data" / "crypto.json").read_text(encoding="utf-8"))
        cls.key = crypto.verify_descriptor(descriptor, PASSPHRASE)

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def check(self, site: Path, vergleich: Path | None = None) -> dict:
        with mock.patch.dict(os.environ, {"DATA_PASSPHRASE": PASSPHRASE}):
            meta, stands = nachrechnen.load_site_stands(site)
            return nachrechnen.run(meta, stands, vergleich)

    def read(self, site: Path, sid: str, relative: str):
        blob = (site / "data" / "snapshots" / sid / relative).read_bytes()
        return json.loads(crypto.unpack(blob, self.key, f"snapshots/{sid}/{relative}"))

    def mutated(self, relative: str, change, sid: str | None = None) -> Path:
        """Kopie der Website, in der eine Datei des Stands mit Schlusskursen verändert und neu verschlüsselt ist."""
        sid = sid or self.official
        target = Path(tempfile.mkdtemp(prefix="nachrechnen-fehler-", dir=self.tmp)) / "site"
        shutil.copytree(self.site, target)
        data = self.read(target, sid, relative)
        change(data)
        blob = crypto.pack(json.dumps(data).encode("utf-8"), self.key, f"snapshots/{sid}/{relative}")
        (target / "data" / "snapshots" / sid / relative).write_bytes(blob)
        return target

    # ---------------------------------------------------------- fehlerfreie Stände

    def test_clean_stands_have_no_deviations(self):
        report = self.check(self.site)
        self.assertEqual(report["ergebnis"], "bestanden", _failed(report))
        kinds = {s["art"]: s for s in report["staende"]}
        self.assertEqual(set(kinds), {"stand_mit_schlusskursen", "zwischenstand"})
        for stand in kinds.values():
            checks = stand["pruefungen"]
            self.assertGreater(sum(v["geprueft"] for v in checks.values()), 100_000)
            for name in ("rendite", "startkurs_endkurs", "r2", "trend_status", "zulassung_V", "rangliste_A_gewichtet", "rangliste_B_gewichtet", "umsatz_usd", "haeufigkeit_A_je_aktie", "dateien_pruefsumme"):
                self.assertGreater(checks[name]["geprueft"], 0, name)
        # Zwischenstand (ab 1.13): Aktien ohne Kurs von heute zählen mit dem Schlusskurs davor – gleiche Werte
        self.assertGreater(kinds["zwischenstand"]["mit_schlusskurs_davor"], 0)
        same = report["zwischenstand_gegen_schlusskurse"]["pruefungen"]["gleiche_werte_wie_mit_schlusskursen"]
        self.assertGreater(same["geprueft"], 100)
        self.assertEqual(same["abweichend"], 0)
        # Ausgabe ohne Namen, ISINs oder Kurse
        text = "\n".join(nachrechnen.annotations(report))
        instruments = self.read(self.site, self.official, "instruments.bin")
        for isin in instruments["isin"][:50]:
            self.assertNotIn(isin, text)
        self.assertNotIn(PASSPHRASE, text)

    # ---------------------------------------------------------- eingebaute Fehler werden gefunden

    def test_finds_a_changed_return(self):
        def change(data):
            data["m"]["r"][0] += 1e-12

        report = self.check(self.mutated("windows/30.full.bin", change))
        failed = _failed(report)
        self.assertGreater(failed["rendite"], 0)
        self.assertGreater(failed["dateien_pruefsumme"], 0, "Prüfsumme im Manifest passt nicht mehr")
        self.assertEqual(report["ergebnis"], "abweichungen")

    def test_finds_a_changed_price_in_a_series(self):
        win = self.read(self.site, self.official, "windows/30.full.bin")
        isin = self.read(self.site, self.official, "instruments.bin")["isin"][win["m"]["idx"][0]]

        def change(data):
            data["c"][-1] *= 1.001

        failed = _failed(self.check(self.mutated(f"series/{isin}.bin", change)))
        self.assertGreater(failed["startkurs_endkurs"], 0)
        self.assertGreater(failed["rendite"], 0)

    def test_finds_a_swapped_ranking(self):
        win = self.read(self.site, self.official, "windows/60.full.bin")
        self.assertGreaterEqual(len(win["orders"]["u"]["50"]), 2)

        def change(data):
            order = data["orders"]["u"]["50"]
            order[0], order[1] = order[1], order[0]

        self.assertGreater(_failed(self.check(self.mutated("windows/60.full.bin", change)))["rangliste_A_gewichtet"], 0)

    def test_finds_a_changed_r2(self):
        win = self.read(self.site, self.official, "windows/60.full.bin")
        status = __import__("base64").b64decode(win["status_b64"])
        row = next(k for k, i in enumerate(win["m"]["idx"]) if status[i] == 18)

        def change(data):
            data["m"]["r2"][row] = min(1.0, data["m"]["r2"][row] + 1e-6) if data["m"]["r2"][row] < 0.99 else data["m"]["r2"][row] - 1e-6

        self.assertGreater(_failed(self.check(self.mutated("windows/60.full.bin", change)))["r2"], 0)

    def test_finds_a_wrong_frequency_count(self):
        def change(data):
            data["server_reference"]["entries"][0]["n1"] += 1

        self.assertGreater(_failed(self.check(self.mutated("frequency.bin", change)))["haeufigkeit_A_je_aktie"], 0)

    def test_finds_a_wrong_turnover_group(self):
        instruments = self.read(self.site, self.official, "instruments.bin")
        turnover = instruments["turnover"]
        k = next(i for i, (st, usd) in enumerate(zip(turnover["status"], turnover["usd"])) if st == "ok" and usd is not None and usd < 10e6)

        def change(data):
            data["turnover"]["liquid"][k] = True

        self.assertGreater(_failed(self.check(self.mutated("instruments.bin", change)))["umsatz_gruppe_B"], 0)

    def test_finds_a_wrong_average_turnover_and_names_the_cause(self):
        """Ø Tagesumsatz ohne letzte Sitzung gerechnet: Abweichung gefunden, Ursachensuche nennt die passende Variante."""
        instruments = self.read(self.site, self.official, "instruments.bin")
        turnover = instruments["turnover"]
        k = next(i for i, st in enumerate(turnover["status"]) if st == "ok")
        isin = instruments["isin"][k]
        series = self.read(self.site, self.official, f"series/{isin}.bin")
        first, last = turnover["first"][k], turnover["last"][k]
        factor = series["listing"].get("unit_factor") or 1.0
        values = [c * v * factor for d, c, v in zip(series["d"], series["c"], series["v"]) if first <= d <= last and c and v is not None and v >= 0]
        self.assertEqual(turnover["currency"][k], "USD", "DEMO-Aktien notieren in USD")

        def change(data):
            data["turnover"]["usd"][k] = float(f"{sum(values[:-1]) / len(values[:-1]):.8g}")

        report = self.check(self.mutated("instruments.bin", change))
        self.assertGreater(_failed(report)["umsatz_usd"], 0)
        diagnosis = next(s for s in report["staende"] if s["art"] == "stand_mit_schlusskursen")["diagnose"]["umsatz"]
        self.assertEqual(diagnosis.get("passt_ohne_letzte_sitzung"), 1)
        self.assertEqual(diagnosis.get("klasse_USD"), 1)
        self.assertEqual(len(diagnosis["verhaeltnis_quantile"]), 5)

    def test_finds_a_changed_value_in_the_intraday_stand(self):
        """Zwischenstand: eine Aktie mit dem Schlusskurs davor, deren Startkurs nicht mehr zum Stand mit Schlusskursen passt."""
        z = self.read(self.site, self.intraday, "windows/30.full.bin")
        instruments = self.read(self.site, self.intraday, "instruments.bin")
        cutoff = z["cutoff_day"]
        row = next(k for k, i in enumerate(z["m"]["idx"]) if instruments["last_close_day"][i] is not None and instruments["last_close_day"][i] < cutoff)

        def change(data):
            data["m"]["p0"][row] *= 1.0001

        report = self.check(self.mutated("windows/30.full.bin", change, sid=self.intraday))
        failed = _failed(report)
        self.assertGreater(failed["startkurs_endkurs"], 0)
        self.assertGreater(failed["gleiche_werte_wie_mit_schlusskursen"], 0)

    # ---------------------------------------------------------- Vergleich über Prüfwerte

    def test_comparison_counts_matching_rankings_without_names(self):
        """Vergleichsdatei wie die aus ChatGPTs Bericht – hier aus dem Stand selbst gebildet: alles gleich; eine
        geänderte Rangliste zählt einmal weniger."""
        check = nachrechnen.Nachrechnung(nachrechnen.Stand(self.site / "data" / "snapshots" / self.official, self.official, self.key))
        check.run()
        salt = "0123456789abcdef"
        rows = []
        for group in ("A", "B"):
            for h in range(1, 31):
                for w in (0, 40, 50, 60):
                    isins = [check.isins[int(i)] for i in check._order(group, h, w)]
                    rows.append(nachrechnen.cell_digests(salt, group, h, w, isins))
        computed = [r for r in rows if r["anzahl"]]
        self.assertGreater(len(computed), 60)
        cells = [check._order(g, h, w) for g in ("A", "B") for h in range(1, 31) for w in (0, 40, 50, 60)]
        depots = {"bericht_1_30_ab": nachrechnen.depot_digests(salt, nachrechnen.depot_lists(check.isins, [c for c in cells if c]))}
        path = self.tmp / "vergleich.json"
        path.write_text(json.dumps({"stichtag": nachrechnen._iso(check.cutoff), "salz": salt, "ranglisten": rows, "depots": depots}), encoding="utf-8")
        result = nachrechnen.compare_chatgpt(check, path)
        flags = {k: v for k, v in result["musterdepots_bericht_1_30"].items() if not k.endswith("_gleiche_spitze")}
        self.assertEqual(set(flags.values()), {True}, "Musterdepots: gleiche Aktien und Reihenfolge")
        self.assertEqual(result["ranglisten_chatgpt"], len(computed))
        self.assertEqual(result["anzahl_aktien_gleich"], len(computed))
        self.assertEqual(result["platz_1_10_gleich"], sum(1 for r in computed if "top10" in r))
        self.assertEqual(result["gleiche_10_aktien"], sum(1 for r in computed if "menge10" in r))
        self.assertEqual(result["platz_1_5_gleich"], sum(1 for r in computed if "top5" in r))
        # Eine Rangliste mit anderem Platz 7: Plätze 1–5 noch gleich, 1–10 nicht mehr; gleiche Spitze 6 Plätze
        changed = next(r for r in rows if "top10" in r)
        changed["top10"] = "0" * 64
        for k in ("7", "8", "9", "10"):
            changed["anfang"][k] = "0" * 64
        depots["bericht_1_30_ab"]["sieger_reihenfolge"] = "0" * 64
        path.write_text(json.dumps({"stichtag": nachrechnen._iso(check.cutoff), "salz": salt, "ranglisten": rows, "depots": depots}), encoding="utf-8")
        again = nachrechnen.compare_chatgpt(check, path)
        self.assertFalse(again["musterdepots_bericht_1_30"]["sieger_reihenfolge"])
        self.assertTrue(again["musterdepots_bericht_1_30"]["sieger_menge"])
        self.assertEqual(again["platz_1_10_gleich"], result["platz_1_10_gleich"] - 1)
        self.assertEqual(again["platz_1_5_gleich"], result["platz_1_5_gleich"])
        self.assertEqual(again["gleiche_spitze_laenge"].get("6"), 1)
        # Muster des häufigsten Siegers je Gewichtung: Buchstaben statt Namen
        pattern = again["haeufigster_sieger_je_gewichtung"]
        self.assertEqual(len(pattern), 11)
        self.assertTrue(all(p["sieger"] is None or p["sieger"] in "ABCDEFGHIJK" for p in pattern))


if __name__ == "__main__":
    unittest.main()
