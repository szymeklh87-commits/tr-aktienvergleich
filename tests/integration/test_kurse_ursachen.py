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
    """Nasdaq-Historie, NOCP, Dividenden und Yahoo-Tages- und Minutenkurse aus den Kursreihen des Stands – mit Abweichungen.
    ``failures``: Kürzel → Zahl der Nasdaq-Abrufe, die mit einem Verbindungsfehler enden (danach Antwort)."""

    def __init__(self, series: dict[str, dict], nasdaq_changes: dict[str, dict[int, float]], nocp: dict[str, dict[int, float]], nasdaq_listed: set[str], failures: dict[str, int] | None = None, minutes_2m: bool = False) -> None:
        self.series, self.changes, self.nocp, self.listed = series, nasdaq_changes, nocp, nasdaq_listed
        self.failures = dict(failures or {})
        self.minutes_2m = minutes_2m
        self.calls: list[str] = []

    def get(self, url: str, headers=None) -> Response:
        self.calls.append(url)
        parsed = urlparse(url)
        parts = parsed.path.split("/")
        if parsed.netloc == "api.nasdaq.com":
            symbol, endpoint = parts[3], parts[4]  # /api/quote/<Kürzel>/historical, /api/company/<Kürzel>/historical-nocp
            if endpoint == "historical" and self.failures.get(symbol, 0) > 0:
                self.failures[symbol] -= 1
                raise ConnectionError("Anfrage an api.nasdaq.com endgültig fehlgeschlagen: ConnectionError")
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
            if "interval=2m" in parsed.query:
                if not self.minutes_2m:
                    return Response(422, {"chart": {"result": None, "error": {"code": "Unprocessable Entity"}}})
                days = sorted(own)  # letzte Kerze 15:58 Uhr New York mit dem Kurs des Stands als letztem Abschluss
                stamps = [d * 86400 + 19 * 3600 + 58 * 60 for d in days]
                return Response(200, {"chart": {"result": [{"meta": meta, "timestamp": stamps, "indicators": {"quote": [{"close": [own[d] for d in days]}]}}]}})
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

    def setup_case(self):
        """Auswahl, Kursreihen und zwei absichtlich abweichende Aktien: die beste unter den ersten 10 (−10 % am letzten Tag,
        Nasdaq = NOCP) und eine ohne Platz unter den ersten 10 (+5 % an einem älteren Tag, ohne Beleg)."""
        stand = self.stand()
        instruments = stand.get("instruments.bin")
        cutoff = int(stand.get("manifest.bin")["cutoff_day"])
        chosen, top10, first, _, places = ursachen.select(stand, instruments, self.sid)
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
        return instruments, chosen, top10, first, places, series, changes, nocp, leader, leader_symbol, other_symbol

    def test_causes_need_evidence_and_rankings_are_recomputed(self):
        instruments, chosen, top10, first, places, series, changes, nocp, leader, leader_symbol, _ = self.setup_case()
        http = FakeHttp(series, changes, nocp, {leader_symbol})
        report = ursachen.run(self.stand(), self.sid, http, pause=self.fail_on_pause)
        self.assertEqual(report["tage"]["abweichend"], 2, report["tage"])
        self.assertEqual(report["ursachen"], {"offizieller_schlusskurs": 1, "ungeklaert": 1})
        self.assertEqual(report["ungeklaert_gruende"], {"nyse_gruppe_ohne_offiziellen_kurs": 1})
        self.assertEqual(report["ungeklaert_muster"]["stand_niedriger"], 1)
        self.assertEqual(report["urteil"], "ungeklaert", "ein Tag ohne Beleg: nicht vollständig belegt")
        self.assertEqual(report["aktien_mit_abweichung"], 2)
        self.assertEqual((report["abrufrunden"], report["abruf_fehlgeschlagen"]), (1, 0))
        letters = {s["aktie"]: s for s in report["aktien"]}
        self.assertEqual(letters["A"]["ursachen"], {"offizieller_schlusskurs": 1}, "die Aktie unter den ersten 10 bekommt den ersten Buchstaben")
        self.assertTrue(letters["A"]["nocp_abrufbar"])
        self.assertEqual(letters["A"]["nocp_tage_ungleich"], 1)
        self.assertEqual(letters["B"]["ursachen"], {"ungeklaert": 1})
        # offizieller Schlusskurs an allen Tagen der Nasdaq-notierten Aktie (hier nur der eine Tag in der NOCP-Historie)
        self.assertEqual(report["nocp_vergleich"], {"aktien": 1, "tage": 1, "stand_ungleich": 1, "nasdaq_historie_gleich": 1})
        self.assertEqual(places["erste_10_us"], sum(top10.values()))
        self.assertEqual(report["top10_abdeckung"]["us_aktien_unter_ersten_10"], len(top10))
        self.assertEqual(report["top10_abdeckung"]["alle_abweichungen_belegt"], 1)
        for effect in (report["ranglisten"], report["ranglisten_offizieller_schlusskurs"]):
            self.assertGreater(effect["ranglisten_verglichen"], 0)
            self.assertGreater(effect["reihenfolge_geaendert"], 0)
        if first.get(leader):
            self.assertGreater(report["ranglisten"]["spitze_geaendert"], 0, "−10 % am Stichtag kostet Platz 1")
            self.assertGreater(report["ranglisten_offizieller_schlusskurs"]["spitze_geaendert"], 0, "mit dem NOCP ebenso")
            moves = letters["A"]["rangwirkung"]
            self.assertLess(moves["platz1_nachher"], moves["platz1_vorher"])
            self.assertLess(letters["A"]["rangwirkung_nocp"]["platz1_nachher"], letters["A"]["rangwirkung_nocp"]["platz1_vorher"])
            # ab 1.18.2 einzeln: jede Rangliste mit anderem Platz 1 – vorher die Aktie A, nachher eine andere (mit Buchstaben)
            for key, effect in (("aenderungen_nasdaq", report["ranglisten"]), ("aenderungen_offizieller_schlusskurs", report["ranglisten_offizieller_schlusskurs"])):
                leaders = [c["platz1"] for c in report[key] if c["platz1"]]
                self.assertEqual(len(leaders), effect["spitze_geaendert"])
                self.assertIn("A", {before for before, _ in leaders})
                self.assertTrue(all(after != before for before, after in leaders))
            legend = {x["aktie"] for x in report["weitere_buchstaben"]}
            for change in report["aenderungen_nasdaq"] + report["aenderungen_offizieller_schlusskurs"]:
                for name in (change["platz1"] or []) + change["raus"] + change["rein"]:
                    self.assertTrue(name in letters or name in legend or name == "–", name)
        # Abruf je Gruppe: jede ausgewählte Aktie genau einmal; keine Sperre ohne Abruffehler
        self.assertEqual(sum(report["abruf_je_gruppe"].values()), len(chosen))
        self.assertEqual(report["abruf_je_gruppe"].get("erste_10_mit_kursen", 0) + report["abruf_je_gruppe"].get("erste_10_keine_kurse", 0), len(top10))
        self.assertEqual(report["sperrpausen"], 0)
        lines = ursachen.annotations(report)
        text = "\n".join(lines)
        self.assertTrue(lines[0].startswith("::error title=Kursursachen: NICHT VOLLSTÄNDIG BELEGT – 1 von 2 abweichenden Tagen ungeklärt::"))
        self.assertIn("Ursache belegt für 1, ungeklärt 1", text)
        self.assertIn("Heimatbörse der NYSE-Gruppe oder Cboe – offizieller Schlusskurs nicht frei abrufbar 1", text)
        for isin in instruments["isin"]:
            self.assertNotIn(isin, text)
        self.assertNotIn(leader_symbol, text)
        # NOCP nur für die Nasdaq-notierte Aktie, Minutenkurse und Dividenden nur für Aktien mit Abweichung
        self.assertEqual(sum("historical-nocp" in url for url in http.calls), 1)
        self.assertEqual(sum("interval=1m" in url for url in http.calls), 2)
        self.assertEqual(sum("interval=2m" in url for url in http.calls), 2)
        self.assertEqual(report["detailabruf"]["minuten_2m_http_422"], 2)

    def test_unadjusted_official_close_before_a_split_is_no_deviation(self):
        """Die NOCP-Historie ist unbereinigt: vor einem Split weicht sie um dessen Faktor vom (splitbereinigten) Stand ab. Das
        zählt als „Faktor eines Splits“ – kein anderer Kurs, und die Ranglisten mit dem offiziellen Schlusskurs ersetzen ihn nicht."""
        _, chosen, _, _, _, series, changes, nocp, leader, leader_symbol, other_symbol = self.setup_case()
        stand = self.stand()
        instruments = stand.get("instruments.bin")
        third = next(str(instruments["symbol"][i]) for i in chosen if str(instruments["symbol"][i]) not in (leader_symbol, other_symbol))
        days = sorted(series[third])
        split_day = days[len(days) // 2]
        nocp = dict(nocp)
        nocp[third] = {d: c * 2 if d < split_day else c for d, c in series[third].items()}
        report = ursachen.run(self.stand(), self.sid, FakeHttp(series, changes, nocp, {leader_symbol, third}), pause=self.fail_on_pause)
        before_split = sum(1 for d in days if d < split_day)
        self.assertEqual(report["nocp_vergleich"]["faktor_split"], before_split)
        self.assertEqual(report["nocp_vergleich"]["stand_ungleich"], 1, "nur der eine Tag der besten Aktie")
        self.assertEqual(report["nocp_vergleich"]["aktien"], 2)
        self.assertEqual(report["ursachen"], {"offizieller_schlusskurs": 1, "ungeklaert": 1})
        self.assertIn(f"Faktor eines Splits {before_split} (NOCP unbereinigt", "\n".join(ursachen.annotations(report)))

    def test_last_trade_from_two_minute_candles_is_evidence(self):
        """Mit Kerzen zu 2 Minuten (58 Tage) ist auch der ältere Tag belegt: Stand = letzter Abschluss vor 16:00 Uhr."""
        _, _, _, _, _, series, changes, nocp, _, leader_symbol, _ = self.setup_case()
        report = ursachen.run(self.stand(), self.sid, FakeHttp(series, changes, nocp, {leader_symbol}, minutes_2m=True), pause=self.fail_on_pause)
        self.assertEqual(report["ursachen"], {"offizieller_schlusskurs": 1, "letzter_abschluss": 1})
        self.assertEqual(report["urteil"], "belegt")
        self.assertTrue(ursachen.annotations(report)[0].startswith("::notice title=Kursursachen: jede Abweichung belegt (2 Tage)::"))

    def test_connection_errors_are_fetched_again_after_a_pause(self):
        """71 Verbindungsfehler bei Nasdaq im Lauf vom 24.10.2026, 21:43 Uhr: Seitdem fragt das Skript solche Aktien nach einer
        Pause erneut ab; erst wenn auch die dritte Runde scheitert, ist das Ergebnis unvollständig."""
        _, chosen, _, _, _, series, changes, nocp, _, leader_symbol, other_symbol = self.setup_case()
        pauses: list[float] = []
        http = FakeHttp(series, changes, nocp, {leader_symbol}, failures={leader_symbol: 1, other_symbol: 2})
        report = ursachen.run(self.stand(), self.sid, http, pause=pauses.append)
        self.assertEqual(pauses, list(ursachen.RETRY_PAUSES))
        self.assertEqual((report["abrufrunden"], report["abruf_nachgeholt"], report["abruf_fehlgeschlagen"]), (3, 2, 0))
        self.assertEqual(report["abruf"]["nasdaq_ok"] + report["abruf"].get("nasdaq_keine_kurse", 0), len(chosen))
        self.assertEqual(report["ursachen"], {"offizieller_schlusskurs": 1, "ungeklaert": 1}, "nachgeholt wie ohne Fehler")
        # dauerhaft ohne Antwort: unvollständig, Job rot – auch wenn die übrigen Aktien keine Abweichung zeigen
        http = FakeHttp(series, {}, {}, set(), failures={other_symbol: 99})
        report = ursachen.run(self.stand(), self.sid, http, pause=lambda seconds: None)
        self.assertEqual(report["abruf_fehlgeschlagen"], 1)
        self.assertEqual(report["abruf"]["fehlgeschlagen_nasdaq_fehler_ConnectionError"], 1)
        self.assertEqual(report["urteil"], "unvollstaendig")
        self.assertTrue(ursachen.annotations(report)[0].startswith("::error title=Kursursachen: UNVOLLSTÄNDIG – 1 Aktien ohne Antwort einer Quelle::"))

    def test_a_block_at_nasdaq_pauses_and_slows_down_and_counts_by_group(self):
        """Lauf vom 24.10.2026, 23:09 Uhr: 121 Aktien ohne Antwort von Nasdaq, auch nach 30 und 90 s nicht. Seitdem gilt eine
        Reihe von Aktien ohne Antwort als Sperre: Pause, danach doppelter Abstand; gezählt wird je Gruppe (erste 10, erste 20,
        zufällig) – und abgefragt werden zuerst die Aktien unter den ersten 10."""
        _, chosen, top10, _, _, series, changes, nocp, _, leader_symbol, _ = self.setup_case()
        stand = self.stand()
        instruments = stand.get("instruments.bin")
        if len(chosen) <= ursachen.BLOCK_AFTER:
            self.skipTest("DEMO-Stand mit zu wenigen US-Aktien")
        # Reihenfolge des Abrufs: zuerst alle Aktien unter den ersten 10, die häufigsten zuerst
        in_top = [i for i in chosen if top10.get(i)]
        self.assertEqual(chosen[: len(in_top)], sorted(in_top, key=lambda i: (-top10[i], i)))
        blocked = [str(instruments["symbol"][i]) for i in chosen[: ursachen.BLOCK_AFTER]]
        pauses: list[float] = []
        http = FakeHttp(series, changes, nocp, {leader_symbol}, failures={s: 1 for s in blocked})
        http.min_interval = {"api.nasdaq.com": ursachen.NASDAQ_INTERVAL_S}
        report = ursachen.run(self.stand(), self.sid, http, pause=pauses.append)
        self.assertEqual(pauses, [ursachen.BLOCK_PAUSE_S, ursachen.RETRY_PAUSES[0]], "erst die Sperrpause, dann die Nachholrunde")
        self.assertEqual(report["sperrpausen"], 1)
        self.assertEqual(report["nasdaq_abstand_s"], 2 * ursachen.NASDAQ_INTERVAL_S)
        self.assertEqual((report["abruf_nachgeholt"], report["abruf_fehlgeschlagen"]), (ursachen.BLOCK_AFTER, 0))
        self.assertTrue(any("Sperrpausen 1" in line for line in ursachen.annotations(report)))
        # dauerhaft ohne Antwort: höchstens MAX_BLOCK_PAUSES Sperrpausen, dann unvollständig – je Gruppe gezählt
        pauses = []
        http = FakeHttp(series, {}, {}, set(), failures={str(instruments["symbol"][i]): 99 for i in chosen})
        report = ursachen.run(self.stand(), self.sid, http, pause=pauses.append)
        self.assertEqual(report["sperrpausen"], ursachen.MAX_BLOCK_PAUSES)
        self.assertEqual(pauses, [ursachen.BLOCK_PAUSE_S] * ursachen.MAX_BLOCK_PAUSES + list(ursachen.RETRY_PAUSES), "Sperrpausen in der ersten Runde, dann die Nachholrunden")
        self.assertEqual(report["abruf_fehlgeschlagen"], len(chosen))
        groups = report["abruf_je_gruppe"]
        self.assertEqual(groups.get("erste_10_ohne_antwort", 0), len(in_top))
        self.assertEqual(sum(groups.values()), len(chosen))
        self.assertEqual(report["urteil"], "unvollstaendig")
        self.assertEqual(report["top10_abdeckung"]["abruf_fehlgeschlagen"], len(top10))

    def test_time_budget_ends_with_an_incomplete_result_instead_of_none(self):
        """Lauf vom 24.10.2026, 22:08 Uhr: über 30 Minuten ohne Ergebnis. Seitdem ein Zeitbudget für den Abruf – danach endet
        das Skript mit „unvollständig“ und allen Zählwerten, statt vom Job-Limit ohne Ergebnis abgebrochen zu werden."""
        _, chosen, _, _, _, series, changes, nocp, _, leader_symbol, _ = self.setup_case()
        report = ursachen.run(self.stand(), self.sid, FakeHttp(series, changes, nocp, {leader_symbol}), pause=self.fail_on_pause, budget_s=-1)
        self.assertEqual(report["abruf_fehlgeschlagen"], len(chosen))
        self.assertEqual(report["abruf"], {"fehlgeschlagen_zeitbudget_erschoepft": len(chosen)})
        self.assertEqual(report["urteil"], "unvollstaendig")

    def test_without_differences_nothing_changes(self):
        stand = self.stand()
        instruments = stand.get("instruments.bin")
        cutoff = int(stand.get("manifest.bin")["cutoff_day"])
        chosen, _, _, _, _ = ursachen.select(stand, instruments, self.sid)
        series = {}
        for i in chosen:
            data = stand.get(f"series/{instruments['isin'][i]}.bin")
            series[str(instruments["symbol"][i])] = {int(d): float(c) for d, c in zip(data["d"], data["c"]) if c is not None and int(d) >= cutoff - 145}
        report = ursachen.run(self.stand(), self.sid, FakeHttp(series, {}, {}, set()), pause=self.fail_on_pause)
        self.assertGreater(report["tage"]["verglichen"], 1000, "alle Kurse verglichen")
        self.assertEqual(report["tage"].get("abweichend", 0), 0)
        self.assertEqual(report["ranglisten"].get("ranglisten_verglichen", 0), 0)
        self.assertEqual(report["aktien"], [])
        self.assertEqual(report["urteil"], "keine_abweichungen")

    @staticmethod
    def fail_on_pause(seconds: float) -> None:
        raise AssertionError(f"Pause von {seconds} s ohne Abruffehler")


if __name__ == "__main__":
    unittest.main()
