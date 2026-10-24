"""Ursachen der Kursunterschiede und Wirkung auf die Ranglisten (``tests/live/kurse_ursachen.py``) auf einem DEMO-Stand –
SYNTHETISCHE Daten und nachgebildete Antworten von Nasdaq und Yahoo (kein Netz).

Zwei Aktien weichen absichtlich ab: eine unter den ersten 10 am Stichtag um −10 % mit einem passenden offiziellen
Schlusskurs (NOCP) – Ursache belegt, die Ranglisten ändern sich –, eine andere an einem älteren Tag ohne jeden Beleg –
Ursache ungeklärt. Alle übrigen Kurse gleichen dem Stand (auf Cent gerundet wie bei Nasdaq)."""

from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlparse

from tests.live import nachrechnen

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tests" / "live"))
import kurse_ursachen as ursachen  # noqa: E402

EPOCH = dt.date(1970, 1, 1)


def us_date(day: int) -> str:
    return (EPOCH + dt.timedelta(days=day)).strftime("%m/%d/%Y")


def money(value: float) -> str:
    return f"${value:,.2f}" if value >= 1 else f"${value:.4f}"


class Response:
    def __init__(self, status: int, payload) -> None:
        self.status_code = status
        self._payload = payload

    def json(self):
        return self._payload


class FakeHttp:
    """Nasdaq-Historie, NOCP, Dividenden und Yahoo-Tages- und Minutenkurse aus den Kursreihen des Stands – mit Abweichungen."""

    def __init__(self, series: dict[str, dict], nasdaq_changes: dict[str, dict[int, float]], nocp: dict[str, dict[int, float]], nasdaq_listed: set[str]) -> None:
        self.series, self.changes, self.nocp, self.listed = series, nasdaq_changes, nocp, nasdaq_listed
        self.calls: list[str] = []

    def get(self, url: str, headers=None) -> Response:
        self.calls.append(url)
        parsed = urlparse(url)
        parts = parsed.path.split("/")
        if parsed.netloc == "api.nasdaq.com":
            symbol, endpoint = parts[3], parts[4]  # /api/quote/<Kürzel>/historical, /api/company/<Kürzel>/historical-nocp
            own = self.series.get(symbol)
            if own is None:
                return Response(200, {"data": None})
            if endpoint == "historical":
                rows = [{"date": us_date(d), "close": money(self.changes.get(symbol, {}).get(d, c)), "volume": "1,000"} for d, c in sorted(own.items(), reverse=True)]
                return Response(200, {"data": {"tradesTable": {"rows": rows}}})
            if endpoint == "historical-nocp":
                rows = [{"date": us_date(d), "price": money(p)} for d, p in sorted(self.nocp.get(symbol, {}).items(), reverse=True)]
                return Response(200, {"data": {"nocp": {"nocpTable": rows}}})
            if endpoint == "dividends":
                return Response(200, {"data": {"dividends": {"rows": []}}})
        if parsed.netloc == "query2.finance.yahoo.com":
            symbol = parts[-1]
            own = self.series.get(symbol, {})
            meta = {"gmtoffset": -14400, "exchangeName": "NCM" if symbol in self.listed else "NYQ"}
            if "interval=1m" in parsed.query:
                last = sorted(own)[-5:]
                stamps = [d * 86400 + 19 * 3600 + 59 * 60 for d in last]
                return Response(200, {"chart": {"result": [{"meta": meta, "timestamp": stamps, "indicators": {"quote": [{"close": [own[d] for d in last]}]}}]}})
            days = sorted(own)
            stamps = [d * 86400 + 13 * 3600 + 30 * 60 for d in days]
            closes = [own[d] for d in days]
            return Response(200, {"chart": {"result": [{"meta": meta, "timestamp": stamps, "indicators": {"quote": [{"close": closes, "volume": [1000] * len(days)}], "adjclose": [{"adjclose": closes}]}}]}})
        return Response(404, None)


class KursUrsachenTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = Path(tempfile.mkdtemp(prefix="ursachen-test-"))
        site = cls.tmp / "site"
        command = [sys.executable, "-m", "traktien", "demo", "--fresh", "--state-dir", str(cls.tmp / "state"), "--site", str(site), "--app-dist", str(REPO / "app" / "dist")]
        env = dict(os.environ, PYTHONPATH=str(REPO / "backend"), LOG_LEVEL="WARNING")
        subprocess.run(command, check=True, cwd=REPO, env=env, capture_output=True, text=True, timeout=600)
        status = json.loads((site / "data" / "status.json").read_text(encoding="utf-8"))
        cls.sid = status["latest_official_snapshot_id"]
        cls.folder = site / "data" / "snapshots" / cls.sid

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def stand(self) -> nachrechnen.Stand:
        return nachrechnen.Stand(self.folder, self.sid, None)

    def test_causes_need_evidence_and_rankings_are_recomputed(self):
        stand = self.stand()
        instruments = stand.get("instruments.bin")
        cutoff = int(stand.get("manifest.bin")["cutoff_day"])
        chosen, top10, first, _ = ursachen.select(stand, instruments, self.sid)
        self.assertTrue(chosen, "DEMO-Stand ohne US-Aktien")
        leader = max((i for i in chosen if first.get(i)), key=lambda i: first[i], default=None) or max(chosen, key=lambda i: top10.get(i, 0))
        other = next(i for i in chosen if i != leader and not top10.get(i))
        series: dict[str, dict] = {}
        for i in chosen:
            data = stand.get(f"series/{instruments['isin'][i]}.bin")
            series[str(instruments["symbol"][i])] = {int(d): float(c) for d, c in zip(data["d"], data["c"]) if c is not None and int(d) >= cutoff - 145}
        leader_symbol, other_symbol = str(instruments["symbol"][leader]), str(instruments["symbol"][other])
        last_day = max(series[leader_symbol])
        old_day = sorted(series[other_symbol])[-30]
        changes = {
            leader_symbol: {last_day: series[leader_symbol][last_day] * 0.9},
            other_symbol: {old_day: series[other_symbol][old_day] * 1.05},
        }
        nocp = {leader_symbol: {last_day: series[leader_symbol][last_day] * 0.9}}
        http = FakeHttp(series, changes, nocp, {leader_symbol})
        report = ursachen.run(self.stand(), self.sid, http)
        self.assertEqual(report["tage"]["abweichend"], 2, report["tage"])
        self.assertEqual(report["ursachen"], {"offizieller_schlusskurs": 1, "ungeklaert": 1})
        self.assertEqual(report["aktien_mit_abweichung"], 2)
        letters = {s["aktie"]: s for s in report["aktien"]}
        self.assertEqual(letters["A"]["ursachen"], {"offizieller_schlusskurs": 1}, "die Aktie unter den ersten 10 bekommt den ersten Buchstaben")
        self.assertTrue(letters["A"]["nocp_abrufbar"])
        self.assertEqual(letters["B"]["ursachen"], {"ungeklaert": 1})
        effect = report["ranglisten"]
        self.assertGreater(effect["ranglisten_verglichen"], 0)
        self.assertGreater(effect["reihenfolge_geaendert"], 0)
        if first.get(leader):
            self.assertGreater(effect["spitze_geaendert"], 0, "−10 % am Stichtag kostet Platz 1")
            moves = letters["A"]["rangwirkung"]
            self.assertLess(moves["platz1_nachher"], moves["platz1_vorher"])
        text = "\n".join(ursachen.annotations(report))
        self.assertIn("Ursache belegt für 1, ungeklärt 1", text)
        for isin in instruments["isin"]:
            self.assertNotIn(isin, text)
        self.assertNotIn(leader_symbol, text)
        # NOCP nur für die Nasdaq-notierte Aktie mit Abweichung, Minutenkurse und Dividenden nur für Aktien mit Abweichung
        self.assertEqual(sum("historical-nocp" in url for url in http.calls), 1)
        self.assertEqual(sum("interval=1m" in url for url in http.calls), 2)

    def test_without_differences_nothing_changes(self):
        stand = self.stand()
        instruments = stand.get("instruments.bin")
        cutoff = int(stand.get("manifest.bin")["cutoff_day"])
        chosen, _, _, _ = ursachen.select(stand, instruments, self.sid)
        series = {}
        for i in chosen:
            data = stand.get(f"series/{instruments['isin'][i]}.bin")
            series[str(instruments["symbol"][i])] = {int(d): float(c) for d, c in zip(data["d"], data["c"]) if c is not None and int(d) >= cutoff - 145}
        report = ursachen.run(self.stand(), self.sid, FakeHttp(series, {}, {}, set()))
        self.assertGreater(report["tage"]["verglichen"], 1000, "alle Kurse verglichen")
        self.assertEqual(report["tage"].get("abweichend", 0), 0)
        self.assertEqual(report["ranglisten"].get("ranglisten_verglichen", 0), 0)
        self.assertEqual(report["aktien"], [])


if __name__ == "__main__":
    unittest.main()
