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
from urllib.parse import parse_qs, urlparse

from tests.live import nachrechnen

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tests" / "live"))
import kurse_ursachen as ursachen  # noqa: E402

EPOCH = dt.date(1970, 1, 1)


def decoded(lines: list[str]) -> str:
    return "\n".join(lines).replace("%0A", "\n").replace("%2C", ",").replace("%25", "%")


def us_date(day: int) -> str:
    return (EPOCH + dt.timedelta(days=day)).strftime("%m/%d/%Y")


def money(value: float) -> str:
    return f"${value:,.2f}" if value >= 1 else f"${value:.4f}"


class Response:
    def __init__(self, status: int, payload, content: bytes | None = None) -> None:
        self.status_code = status
        self._payload = payload
        self.content = content if content is not None else (json.dumps(payload).encode("utf-8") if payload is not None else b"")

    def json(self):
        return self._payload


class FakeHttp:
    """Nasdaq-Historie, NOCP, Dividenden und Yahoo-Tages- und Minutenkurse aus den Kursreihen des Stands – mit Abweichungen.
    ``failures``: Kürzel → Zahl der Nasdaq-Abrufe, die mit einem Verbindungsfehler enden (danach Antwort)."""

    def __init__(self, series: dict[str, dict], nasdaq_changes: dict[str, dict[int, float]], nocp: dict[str, dict[int, float]], nasdaq_listed: set[str], failures: dict[str, int] | None = None,
                 minutes_2m: bool = False, minute_changes: dict[str, dict[int, float]] | None = None, alt: dict[str, dict] | None = None, otc: set[str] | None = None) -> None:
        self.series, self.changes, self.nocp, self.listed = series, nasdaq_changes, nocp, nasdaq_listed
        self.failures = dict(failures or {})
        self.minutes_2m = minutes_2m
        self.minute_changes = minute_changes or {}  # letzter Abschluss vor 16:00 Uhr anders als der Kurs des Stands
        self.alt = alt or {}  # Zusatzquellen je Kürzel: name, closes (Tag → Kurs), cnbc / barchart (an/aus), exchange
        self.otc = otc or set()  # Kürzel, für die Nasdaq keine Kurse führt (Yahoo-Börse PNK)
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
            if own is None or symbol in self.otc:
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
            meta = {"gmtoffset": -14400, "exchangeName": "PNK" if symbol in self.otc else ("NCM" if symbol in self.listed else "NYQ"), "currency": "USD"}
            if "interval=2m" in parsed.query:
                if not self.minutes_2m:
                    return Response(422, {"chart": {"result": None, "error": {"code": "Unprocessable Entity"}}})
                days = sorted(own)  # letzte Kerze 15:58 Uhr New York mit dem Kurs des Stands als letztem Abschluss
                stamps = [d * 86400 + 19 * 3600 + 58 * 60 for d in days]
                closes = [self.minute_changes.get(symbol, {}).get(d, own[d]) for d in days]
                return Response(200, {"chart": {"result": [{"meta": meta, "timestamp": stamps, "indicators": {"quote": [{"close": closes}]}}]}})
            if "interval=1m" in parsed.query:
                last = sorted(own)[-5:]
                stamps = [d * 86400 + 19 * 3600 + 59 * 60 for d in last]
                closes = [self.minute_changes.get(symbol, {}).get(d, own[d]) for d in last]
                return Response(200, {"chart": {"result": [{"meta": meta, "timestamp": stamps, "indicators": {"quote": [{"close": closes}]}}]}})
            days = sorted(own)
            stamps = [d * 86400 + 13 * 3600 + 30 * 60 for d in days]
            closes = [own[d] for d in days]
            return Response(200, {"chart": {"result": [{"meta": meta, "timestamp": stamps, "indicators": {"quote": [{"close": closes, "volume": [1000] * len(days)}], "adjclose": [{"adjclose": closes}]}}]}})
        symbol = (parse_qs(parsed.query).get("symbol") or parse_qs(parsed.query).get("symbols") or [None])[0] or (parts[4] if parsed.netloc == "ts-api.cnbc.com" else None)
        source = self.alt.get(symbol or "")
        if source and parsed.netloc == "quote.cnbc.com" and source.get("cnbc"):
            return Response(200, {"FormattedQuoteResult": {"FormattedQuote": [{"symbol": symbol, "name": source["name"], "exchange": source.get("exchange", "Pink Sheets"), "currencyCode": "USD"}]}})
        if source and parsed.netloc == "ts-api.cnbc.com" and source.get("cnbc"):
            bars = [{"tradeTime": (EPOCH + dt.timedelta(days=d)).strftime("%Y%m%d000000"), "close": f"{c:.4f}", "volume": "1000"} for d, c in sorted(source["closes"].items())]
            return Response(200, {"barData": {"priceBars": bars}})
        if source and parsed.netloc == "backend.otcmarkets.com":
            if "/company/profile/" in parsed.path and source.get("otc_name"):
                return Response(200, {"name": source["otc_name"]})
            if "/trade/inside/" in parsed.path and source.get("otc_last"):
                d, v = source["otc_last"]
                return Response(200, {"lastSale": v, "lastTradeTime": (d * 86400 + 20 * 3600) * 1000, "volume": 100})
        if source and parsed.netloc == "www.barchart.com" and source.get("barchart"):
            text = "\n".join(f"{symbol},{(EPOCH + dt.timedelta(days=d)).isoformat()},{c},{c},{c},{c:.4f},1000" for d, c in sorted(source.get("barchart_closes", source["closes"]).items()))
            return Response(200, None, text.encode("utf-8"))
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
        # letzter Abschluss vor 16:00 Uhr am Stichtag weder der Kurs des Stands noch der Nasdaq-Kurs: die Abweichung vom
        # offiziellen Schlusskurs ist dann ein Befund ohne belegte Ursache (seit dem 25.10.2026)
        self.minute = {leader_symbol: {last_day: series[leader_symbol][last_day] * 1.002}}
        return instruments, chosen, top10, first, places, series, changes, nocp, leader, leader_symbol, other_symbol

    def test_causes_need_evidence_and_rankings_are_recomputed(self):
        instruments, chosen, top10, first, places, series, changes, nocp, leader, leader_symbol, _ = self.setup_case()
        http = FakeHttp(series, changes, nocp, {leader_symbol}, minute_changes=self.minute)
        report = ursachen.run(self.stand(), self.sid, http, pause=self.fail_on_pause)
        self.assertEqual(report["tage"]["abweichend"], 2, report["tage"])
        # seit dem 25.10.2026: Nasdaq-Historie = NOCP und Stand nicht ist ein Befund, keine belegte Ursache
        self.assertEqual(report["ursachen"], {"abweichung_vom_nocp": 1, "ungeklaert": 1})
        self.assertEqual(report["ungeklaert_gruende"], {"nocp_anders": 1, "nyse_gruppe_ohne_offiziellen_kurs": 1})
        self.assertEqual(report["ungeklaert_muster"]["stand_niedriger"], 1)
        self.assertEqual(report["urteil"], "ungeklaert", "kein Tag mit Beleg: nicht vollständig belegt")
        self.assertEqual(report["aktien_mit_abweichung"], 2)
        self.assertEqual((report["abrufrunden"], report["abruf_fehlgeschlagen"]), (1, 0))
        letters = {s["aktie"]: s for s in report["aktien"]}
        self.assertEqual(letters["A"]["ursachen"], {"abweichung_vom_nocp": 1}, "die Aktie unter den ersten 10 bekommt den ersten Buchstaben")
        self.assertTrue(letters["A"]["nocp_abrufbar"])
        self.assertEqual(letters["A"]["nocp_tage_ungleich"], 1)
        self.assertEqual(letters["B"]["ursachen"], {"ungeklaert": 1})
        # offizieller Schlusskurs an allen Tagen der Nasdaq-notierten Aktie (hier nur der eine Tag in der NOCP-Historie)
        self.assertEqual(report["nocp_vergleich"], {"aktien": 1, "tage": 1, "stand_ungleich": 1, "nasdaq_historie_gleich": 1})
        self.assertEqual(report["nocp_ursachen"], {"befund_nasdaq_gleich_nocp": 1}, "Minutenkurs weder Stand noch NOCP: keine belegte Ursache")
        # fünf Ergebnisarten getrennt: Übereinstimmung, Abweichung, belegt, ungeklärt, fehlende Vergleichsmöglichkeit
        a = report["kategorien"]["nasdaq_historie"]
        self.assertEqual((a["abweichung"], a["belegt"], a["ungeklaert"], a["stand_ist_nocp"]), (2, 0, 2, 0))
        self.assertEqual(a["uebereinstimmung"], report["tage"]["verglichen"] - 2)
        self.assertEqual(a["ohne_vergleich_aktien"], 0)
        b = report["kategorien"]["offizieller_schlusskurs"]
        self.assertEqual((b["uebereinstimmung"], b["abweichung"], b["belegt"], b["ungeklaert"]), (0, 1, 0, 1))
        self.assertEqual(b["ohne_vergleich_aktien"], len(chosen) - 1, "nur eine Aktie mit NOCP")
        self.assertEqual(places["erste_10_us"], sum(top10.values()))
        self.assertEqual(report["top10_abdeckung"]["us_aktien_unter_ersten_10"], len(top10))
        self.assertEqual(report["top10_abdeckung"]["mit_ungeklaerten_tagen"], 1)
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
            mapped = {x["aktie"] for x in report["zuordnung"]}
            for change in report["aenderungen_nasdaq"] + report["aenderungen_offizieller_schlusskurs"]:
                for name in (change["platz1"] or []) + change["raus"] + change["rein"]:
                    self.assertTrue(name in letters or name in legend or name == "–", name)
                    self.assertTrue(name in mapped or name == "–", f"{name} ohne Zuordnung")
            # jeder neue Platz 1 mit Auslösern: nur die beiden Aktien mit ersetzten Kursen kommen in Frage. Verliert A selbst
            # Platz 1, löst A ihn aus (−10 % am letzten Tag, Nasdaq = NOCP); sonst über die Ränge der Gruppe (Score)
            leaders = [c for c in report["aenderungen_nasdaq"] if c["platz1"]]
            self.assertTrue(leaders)
            studied = [c for c in leaders if not c["nicht_untersucht"]]
            self.assertEqual(len(studied), min(len(leaders), ursachen.MAX_ATTRIBUTIONS))
            for change in studied:
                names = [x["aktie"] for x in change["ausloeser"]]
                self.assertTrue(names and set(names) <= {"A", "B"}, (change["h"], change["gruppe"], change["w"], names))
                if change["platz1"][0] == "A":
                    self.assertEqual(names, ["A"])
                    self.assertEqual(change["allein_ausreichend"], ["A"])
                    days = change["ausloeser"][0]["tage"]
                    self.assertEqual(len(days), 1)
                    self.assertAlmostEqual(days[0]["abweichung_pct"], 100 * (1 / 0.9 - 1), delta=0.05, msg="Stand gegenüber dem Nasdaq-Kurs (auf Cent gerundet)")
                    self.assertEqual(days[0]["ursache"], "abweichung_vom_nocp")
                    self.assertEqual(days[0]["tag"], nachrechnen._iso(max(series[leader_symbol])))
            self.assertIn("allein ausreichend: A", ursachen.summary_markdown(report))
        # Abruf je Gruppe: jede ausgewählte Aktie genau einmal; keine Sperre ohne Abruffehler
        self.assertEqual(sum(report["abruf_je_gruppe"].values()), len(chosen))
        self.assertEqual(report["abruf_je_gruppe"].get("erste_10_mit_kursen", 0) + report["abruf_je_gruppe"].get("erste_10_keine_kurse", 0), len(top10))
        self.assertEqual(report["sperrpausen"], 0)
        lines = ursachen.annotations(report)
        text = "\n".join(lines).replace("%0A", "\n").replace("%2C", ",").replace("%25", "%")
        self.assertTrue(lines[0].startswith("::error title=Kursursachen: NICHT VOLLSTÄNDIG BELEGT – 2 von 2 abweichenden Tagen ungeklärt::"))
        self.assertIn("festgestellte Abweichung 2 – davon Ursache belegt 0 (–), Stand = offizieller Schlusskurs 0 (abweichend nur die Nasdaq-Historie), Ursache ungeklärt 2 "
                      "(Befund Stand ≠ NOCP bei Nasdaq-Historie = NOCP 1, ohne Beleg 1)", text)
        self.assertIn("Befund ohne Ursache: Nasdaq-Historie = NOCP, Stand nicht – Kurs des Stands nicht als letzter Abschluss vor 16:00 Uhr gefunden 1", text)
        self.assertIn("Prüfgrenze: Heimatbörse der NYSE-Gruppe oder Cboe – offizieller Schlusskurs in den geprüften Quellen nicht frei verfügbar", text)
        summary = ursachen.summary_markdown(report)
        for isin in instruments["isin"]:
            self.assertNotIn(isin, text)
            self.assertNotIn(isin, summary)
        self.assertNotIn(leader_symbol, text)
        self.assertNotIn(leader_symbol, summary)
        # Abdeckung je Gruppe: jede ausgewählte Aktie genau einmal – verglichen, ohne Vergleichskurse oder ohne Antwort
        groups = report["abdeckung_je_gruppe"]
        counted = sum(g.get(k, 0) for g in groups.values() for k in ("verglichen", "keine_vergleichskurse", "abruf_fehlgeschlagen"))
        self.assertEqual(counted, len(chosen))
        self.assertEqual(groups["erste_10"].get("verglichen", 0), len(top10), "alle US-Aktien unter den ersten 10 verglichen")
        self.assertEqual(report["ohne_vergleichskurse"], 0)
        # Zuordnung: jeder Buchstabe genau eine Aktie mit Fundstelle (Platz in einer Rangliste des Stands), jeder Platz eindeutig
        names = [x["aktie"] for x in report["zuordnung"]]
        self.assertEqual(len(names), len(set(names)))
        found = [tuple(sorted(x["fundstelle"].items())) for x in report["zuordnung"] if x["fundstelle"]]
        self.assertEqual(len(found), len(set(found)), "zwei Buchstaben auf demselben Platz")
        self.assertEqual(len(found), len(names), "jeder Buchstabe hat eine Fundstelle")
        a_place = next(x["fundstelle"] for x in report["zuordnung"] if x["aktie"] == "A")
        win = self.stand().get(f"windows/{a_place['h']}.full.bin")
        key = ("v0" if a_place["gruppe"] == "A" else "v0l") if a_place["w"] == 0 else None
        order = win["orders"][key] if key else win["orders"]["u" if a_place["gruppe"] == "A" else "ul"][str(a_place["w"])]
        self.assertEqual(int(order[a_place["platz"] - 1]), leader, "die Fundstelle von A ist die Aktie A")
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
        report = ursachen.run(self.stand(), self.sid, FakeHttp(series, changes, nocp, {leader_symbol, third}, minute_changes=self.minute), pause=self.fail_on_pause)
        before_split = sum(1 for d in days if d < split_day)
        self.assertEqual(report["nocp_vergleich"]["faktor_split"], before_split)
        self.assertEqual(report["nocp_vergleich"]["stand_ungleich"], 1, "nur der eine Tag der besten Aktie")
        self.assertEqual(report["nocp_vergleich"]["aktien"], 2)
        self.assertEqual(report["ursachen"], {"abweichung_vom_nocp": 1, "ungeklaert": 1})
        self.assertIn(f"Faktor eines Splits {before_split} (NOCP unbereinigt", "\n".join(ursachen.annotations(report)))

    def test_last_trade_from_two_minute_candles_is_evidence(self):
        """Mit Kerzen zu 2 Minuten (58 Tage) ist auch der ältere Tag belegt: Stand = letzter Abschluss vor 16:00 Uhr. Ist der Kurs
        des Stands am Stichtag der letzte Abschluss vor 16:00 Uhr, ist auch die Abweichung vom offiziellen Schlusskurs belegt –
        die Schlussauktion fehlt im Kurs des Stands (seit dem 25.10.2026 vor dem Befund „Stand ≠ NOCP“ geprüft)."""
        _, _, _, _, _, series, changes, nocp, _, leader_symbol, _ = self.setup_case()
        report = ursachen.run(self.stand(), self.sid, FakeHttp(series, changes, nocp, {leader_symbol}, minutes_2m=True), pause=self.fail_on_pause)
        self.assertEqual(report["ursachen"], {"letzter_abschluss": 2})
        self.assertEqual(report["nocp_ursachen"], {"letzter_abschluss": 1}, "auch in Variante (b) belegt")
        self.assertEqual(report["urteil"], "belegt")
        self.assertTrue(ursachen.annotations(report)[0].startswith("::notice title=Kursursachen: jede Abweichung belegt (2 Tage)::"))

    def test_connection_errors_are_fetched_again_after_a_pause(self):
        """71 Verbindungsfehler bei Nasdaq im Lauf vom 24.10.2026, 21:43 Uhr: Seitdem fragt das Skript solche Aktien nach einer
        Pause erneut ab; erst wenn auch die dritte Runde scheitert, ist das Ergebnis unvollständig."""
        _, chosen, _, _, _, series, changes, nocp, _, leader_symbol, other_symbol = self.setup_case()
        pauses: list[float] = []
        http = FakeHttp(series, changes, nocp, {leader_symbol}, failures={leader_symbol: 1, other_symbol: 2}, minute_changes=self.minute)
        report = ursachen.run(self.stand(), self.sid, http, pause=pauses.append)
        self.assertEqual(pauses, list(ursachen.RETRY_PAUSES))
        self.assertEqual((report["abrufrunden"], report["abruf_nachgeholt"], report["abruf_fehlgeschlagen"]), (3, 2, 0))
        self.assertEqual(report["abruf"]["nasdaq_ok"] + report["abruf"].get("nasdaq_keine_kurse", 0), len(chosen))
        self.assertEqual(report["ursachen"], {"abweichung_vom_nocp": 1, "ungeklaert": 1}, "nachgeholt wie ohne Fehler")
        # dauerhaft ohne Antwort: unvollständig, Job rot – auch wenn die übrigen Aktien keine Abweichung zeigen
        http = FakeHttp(series, {}, {}, set(), failures={other_symbol: 99})
        report = ursachen.run(self.stand(), self.sid, http, pause=lambda seconds: None)
        self.assertEqual(report["abruf_fehlgeschlagen"], 1)
        self.assertEqual(report["abruf"]["fehlgeschlagen_nasdaq_fehler_ConnectionError"], 1)
        self.assertEqual(report["urteil"], "unvollstaendig")
        self.assertTrue(ursachen.annotations(report)[0].startswith("::error title=Kursursachen: UNVOLLSTÄNDIG – 1 Aktien ohne Antwort einer Quelle%2C 0 ohne Vergleichskurse;"))

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
        self.assertEqual(sum(g.get("abruf_fehlgeschlagen", 0) for g in report["abdeckung_je_gruppe"].values()), len(chosen))
        self.assertEqual(report["abdeckung_je_gruppe"]["erste_10"].get("verglichen", 0), 0, "ohne Antwort ist nichts verglichen")
        self.assertEqual(report["urteil"], "unvollstaendig")
        self.assertEqual(report["top10_abdeckung"]["abruf_fehlgeschlagen"], len(top10))

    def test_stocks_without_comparison_prices_make_the_check_incomplete(self):
        """Nasdaq antwortet für eine Aktie ohne Kurse (wie bei fünfstelligen Kürzeln): sie gilt als „keine Vergleichskurse“ –
        nicht als geprüft. Das Urteil ist dann „unvollständig“, auch wenn alle verglichenen Abweichungen belegt sind."""
        _, chosen, top10, _, _, series, changes, nocp, _, leader_symbol, other_symbol = self.setup_case()
        series = dict(series)
        del series[other_symbol]  # Nasdaq: {"data": null}
        report = ursachen.run(self.stand(), self.sid, FakeHttp(series, changes, nocp, {leader_symbol}, minutes_2m=True), pause=self.fail_on_pause)
        self.assertEqual(report["ohne_vergleichskurse"], 1)
        self.assertEqual(report["urteil"], "unvollstaendig")
        groups = report["abdeckung_je_gruppe"]
        self.assertEqual(sum(g.get("keine_vergleichskurse", 0) for g in groups.values()), 1)
        self.assertEqual(sum(g.get("keine_vergleichskurse_nasdaq_ohne_kurse", 0) for g in groups.values()), 1)
        self.assertEqual(report["ursachen"], {"letzter_abschluss": 1}, "die übrige Abweichung bleibt belegt")
        self.assertEqual(report["zusatzquellen"]["aktien_ohne_nasdaq"], 1)
        self.assertEqual(report["zusatzquellen"]["verglichen"], 0, "keine Zusatzquelle antwortet")
        self.assertTrue(all(v for k, v in report["zusatzquellen"]["pruefungen"].items() if k.endswith("_abruf_gescheitert")))
        self.assertIn("1 ohne Vergleichskurse", ursachen.annotations(report)[0].replace("%2C", ","))

    def test_three_jobs_split_the_selection_without_overlap(self):
        """Nasdaq beantwortet je Rechner nur etwa 430 Anfragen (24.10.2026, zweimal belegt); im Lauf 40139805053 brauchte der Job
        „erste 20“ genau 430 Anfragen, die letzten 4 Gegenproben der Dividenden blieben ohne Antwort. Seit dem 25.10.2026 drei Jobs: die
        US-Aktien unter den ersten 10, die Plätze 11–20 und die Zufallsstichprobe – zusammen genau die Auswahl, ohne
        Überschneidung; jeder Job nennt, was die anderen prüfen, und zählt es nicht als geprüft."""
        _, chosen, top10, _, _, series, changes, nocp, _, leader_symbol, _ = self.setup_case()
        reports = {}
        for shard in ursachen.LEGS:
            http = FakeHttp(series, changes, nocp, {leader_symbol}, minutes_2m=True, minute_changes=self.minute)
            reports[shard] = ursachen.run(self.stand(), self.sid, http, pause=self.fail_on_pause, auswahl=shard)
        self.assertEqual(sum(r["ausgewaehlt"] for r in reports.values()), len(chosen))
        groups = [set(r["uebergabe"]["gruppen"]) for r in reports.values()]
        self.assertEqual(len(set().union(*groups)), len(chosen), "zusammen genau die Auswahl")
        self.assertEqual(sum(len(g) for g in groups), len(chosen), "keine Überschneidung")
        self.assertEqual(set(reports["erste10"]["abdeckung_je_gruppe"]), {"erste_10"})
        self.assertEqual(set(reports["plaetze11_20"]["abdeckung_je_gruppe"]), {"erste_20"})
        self.assertEqual(set(reports["zufall"]["abdeckung_je_gruppe"]), {"zufall"})
        self.assertEqual(reports["erste10"]["abdeckung_je_gruppe"]["erste_10"]["verglichen"], len(top10))
        first = reports["erste10"]
        self.assertEqual(first["im_anderen_job"], len(chosen) - first["ausgewaehlt"])
        self.assertIn(" title=Kursursachen (erste 10): ", ursachen.annotations(first)[0])
        text = decoded(ursachen.annotations(first))
        self.assertIn(f"US-Aktien in diesem Job, {first['im_anderen_job']} in den anderen Jobs (zusammen {len(chosen)};", text)
        self.assertIn("Nicht in diesem Job (in den anderen Jobs desselben Laufs geprüft): Plätze 11–20, Zufallsstichprobe", text)
        self.assertIn(f"Prüfsumme der Vergleichskurse {first['uebergabe']['pruefsumme']}", text)
        # die abweichende Aktie unter den ersten 10 gehört in den ersten Job – in den anderen „in einem anderen Job geprüft“
        self.assertEqual(first["ursachen"].get("abweichung_vom_nocp"), 1)
        self.assertNotIn("abweichung_vom_nocp", reports["zufall"]["ursachen"])
        self.assertEqual(reports["zufall"]["top10_abdeckung"].get("im_anderen_job", 0), len(top10))
        self.assertEqual(reports["zufall"]["top10_abdeckung"].get("ohne_nasdaq_kurse", 0), 0)
        for entry in sum((r["weitere_buchstaben"] for r in reports.values()), []):
            self.assertIn(entry["zustand"], ("verglichen", "ohne_antwort", "ohne_vergleichskurse", "anderer_job", "keine_us_aktie", "nicht_ausgewaehlt"))
        # Aufteilung bis 1.18.2 (zwei Jobs) bleibt für den Vergleich wählbar
        old = ursachen.run(self.stand(), self.sid, FakeHttp(series, changes, nocp, {leader_symbol}, minutes_2m=True, minute_changes=self.minute), pause=self.fail_on_pause, auswahl="erste20")
        self.assertEqual(old["ausgewaehlt"], reports["erste10"]["ausgewaehlt"] + reports["plaetze11_20"]["ausgewaehlt"])

    def test_combined_recomputation_equals_one_job_with_every_stock(self):
        """Auftrag vom 25.10.2026, 03:47 Uhr, Punkt 1: die Vergleichskurse aller Jobs gemeinsam gegen denselben Stand. Die
        gemeinsame Rechnung aus den verschlüsselten Übergaben der drei Jobs ergibt genau die Wirkung eines einzigen Jobs mit
        allen Aktien – und je Job allein genau die Wirkung, die dieser Job selbst gerechnet hat."""
        _, chosen, top10, first, _, series, changes, nocp, leader, leader_symbol, other_symbol = self.setup_case()
        # dritte Abweichung in der Zufallsstichprobe, damit jede Gruppe eigene Ersatzkurse hat
        stand = self.stand()
        instruments = stand.get("instruments.bin")
        legs = {}
        for shard in ursachen.LEGS:
            legs[shard] = ursachen.run(self.stand(), self.sid, FakeHttp(series, changes, nocp, {leader_symbol}, minute_changes=self.minute), pause=self.fail_on_pause, auswahl=shard)
        whole = ursachen.run(self.stand(), self.sid, FakeHttp(series, changes, nocp, {leader_symbol}, minute_changes=self.minute), pause=self.fail_on_pause, auswahl="alle")
        # Übergabe verschlüsselt (wie im Workflow) und wieder geöffnet – an Stand und Job gebunden
        key = ursachen.crypto.derive_key("nur-fuer-den-test", b"0123456789abcdef", iterations=1000)
        sealed = {shard: ursachen.seal(r["uebergabe"], key, self.sid, shard) for shard, r in legs.items()}
        for shard, text in sealed.items():
            self.assertNotIn(leader_symbol, text)
            with self.assertRaises(ursachen.crypto.ContainerError):
                ursachen.unseal(text, key, self.sid, "zufall" if shard != "zufall" else "erste10")
        transfers = {shard: ursachen.unseal(text, key, self.sid, shard) for shard, text in sealed.items()}
        report = ursachen.combine(self.stand(), self.sid, transfers)
        self.assertEqual(report["probleme"], [])
        for v, key_whole in (("a", "ranglisten"), ("b", "ranglisten_offizieller_schlusskurs")):
            self.assertEqual(report["ranglisten"][v], whole[key_whole], f"gemeinsam ({v}) = ein Job mit allen Aktien")
            for shard, r in legs.items():
                self.assertEqual(report["ranglisten"][f"{v}@{shard}"], r[key_whole], f"je Job allein ({v}, {shard})")
        leaders_whole = {(c["h"], c["gruppe"], c["w"]) for c in whole["aenderungen_nasdaq"] if c["platz1"]}
        leaders_combined = {(c["h"], c["gruppe"], c["w"]) for c in report["aenderungen"]["a"] if c["platz1"]}
        self.assertEqual(leaders_combined, leaders_whole)
        if first.get(leader):
            self.assertTrue(leaders_combined, "−10 % am Stichtag kostet Platz 1")
            for c in report["aenderungen"]["a"]:
                if c["platz1"]:
                    self.assertIn("erste10", c["auch_einzeln"], "die Abweichung der besten Aktie liegt im Job „erste 10“")
        text = decoded(ursachen.annotations(report))
        summary = ursachen.summary_markdown(report)
        self.assertTrue(text.startswith("::error title=Kursursachen gemeinsam:") or text.startswith("::notice title=Kursursachen gemeinsam:"))
        self.assertIn("Die 404 ausgewählten US-Aktien", text)
        self.assertIn("keine Vollprüfung aller Aktien der App", text)
        for shard in ursachen.LEGS:
            self.assertIn(f"Prüfsumme {legs[shard]['uebergabe']['pruefsumme']}", text)
        self.assertIn("Gemeinsam (a) Nasdaq-Historie an allen abweichenden Tagen:", text)
        self.assertIn("Zum Vergleich je Job allein:", text)
        for isin in instruments["isin"]:
            self.assertNotIn(isin, text)
            self.assertNotIn(isin, summary)
        for symbol in (leader_symbol, other_symbol):
            self.assertNotIn(symbol, text)
        # Zuordnung: jeder Buchstabe genau eine Aktie mit Fundstelle, jeder Platz eindeutig, mit Datenstand
        names = [x["aktie"] for x in report["zuordnung"]]
        self.assertEqual(len(names), len(set(names)))
        found = [tuple(sorted(x["fundstelle"].items())) for x in report["zuordnung"] if x["fundstelle"]]
        self.assertEqual(len(found), len(set(found)))
        self.assertIn(f"gegen den Stand {self.sid}", text)
        if report["zuordnung"]:
            self.assertIn(f"Datenstand {self.sid}", summary, "Zuordnung vollständig in der Zusammenfassung")
        plan = ursachen.annotation_plan(report)
        self.assertEqual(plan["ausgegeben"] + plan["nicht_ausgegeben"], plan["teile"], "jedes Teil ausgegeben oder gezählt")
        self.assertLessEqual(sum(len(step) for step in plan["schritte"]), ursachen.MAX_JOB_ANNOTATIONS)
        # alle Aktien verglichen → „gerechnet“; fehlt die Übergabe eines Jobs → unvollständig, mit Grund
        self.assertEqual(report["urteil"], "gerechnet")
        partial = ursachen.combine(self.stand(), self.sid, {**transfers, "zufall": None})
        self.assertEqual(partial["urteil"], "unvollstaendig")
        self.assertIn("Zufallsstichprobe: keine Übergabe", partial["probleme"])
        self.assertTrue(ursachen.annotations(partial)[0].startswith("::error title=Kursursachen gemeinsam: UNVOLLSTÄNDIG"))
        wrong = ursachen.combine(self.stand(), self.sid, {**transfers, "zufall": dict(transfers["zufall"], stand="2026-10-12_9820e6d9")})
        self.assertIn("Zufallsstichprobe: Übergabe passt nicht (Format, Stand oder Job)", wrong["probleme"])

    def test_alternative_sources_for_stocks_without_nasdaq_prices(self):
        """Auftrag vom 25.10.2026, Punkt 2: für Aktien ohne Nasdaq-Kurse weitere freie Quellen – geprüft vor jedem Vergleich
        (Identität, Handelsplatz, Währung, Handelsdatum, Bereinigung, Kursniveau). Verglichen wird mit der ersten Quelle, die
        alle Prüfungen besteht; eine zweite bestandene Quelle steht an den abweichenden Tagen daneben."""
        _, chosen, top10, _, _, series, changes, nocp, _, leader_symbol, other_symbol = self.setup_case()
        stand = self.stand()
        instruments = stand.get("instruments.bin")
        otc_i = next(i for i in chosen if str(instruments["symbol"][i]) not in (leader_symbol, other_symbol))
        otc_symbol = str(instruments["symbol"][otc_i])
        own = series[otc_symbol]
        days = sorted(own)
        moved = days[-3]
        closes = {d: round(c, 4) for d, c in own.items()}
        closes[moved] = round(own[moved] * 1.03, 4)  # ein Tag weicht ab
        name = str(instruments["name"][otc_i])
        alt = {otc_symbol: {"name": name, "closes": closes, "cnbc": True, "barchart": True}}
        report = ursachen.run(self.stand(), self.sid, FakeHttp(series, changes, nocp, {leader_symbol}, minute_changes=self.minute, alt=alt, otc={otc_symbol}), pause=self.fail_on_pause)
        z = report["zusatzquellen"]
        self.assertEqual((z["aktien_ohne_nasdaq"], z["verglichen"], z["je_quelle"]), (1, 1, {"cnbc": 1}))
        self.assertEqual(report["ohne_vergleichskurse"], 0, "verglichen mit der Zusatzquelle – nicht „ohne Vergleichskurse“")
        self.assertEqual(report["ohne_nasdaq_boerse"], {"PNK": 1})
        checks = z["pruefungen"]
        self.assertEqual(checks.get("cnbc_identitaet_name_bestaetigt"), 1)
        self.assertEqual(checks.get("cnbc_handelsplatz_gleich"), 1, "Pink Sheets und Yahoo PNK: beide OTC")
        self.assertEqual(checks.get("cnbc_waehrung_gleich"), 1)
        self.assertEqual(checks.get("cnbc_kursniveau_passt"), 1)
        self.assertEqual(checks.get("barchart_identitaet_nur_kuerzel"), 1, "Barchart nennt keinen Namen")
        self.assertEqual(checks.get("otc_markets_abruf_gescheitert"), 1)
        c = report["kategorien"]["zusatzquellen"]
        self.assertEqual((c["abweichung"], c["ungeklaert"]), (1, 1))
        self.assertGreater(c["uebereinstimmung"], 10)
        self.assertEqual(z["tage"].get("zweite_quelle_gleich_erster_quelle"), 1, "Barchart zeigt denselben Kurs wie CNBC")
        group = next(g for g, v in report["abdeckung_je_gruppe"].items() if v.get("verglichen_cnbc"))
        self.assertEqual(report["abdeckung_je_gruppe"][group]["verglichen_cnbc"], 1)
        self.assertEqual(report["ranglisten_zusatzquellen"].get("ranglisten_insgesamt"), 1980)
        text = decoded(ursachen.annotations(report))
        self.assertIn("mit Zusatzquelle: CNBC 1", text)
        self.assertNotIn(otc_symbol, text)
        self.assertNotIn(name, text)
        # zweite Quelle am abweichenden Tag: der letzte Abschluss bei OTC Markets (Identität über den Namen im Profil)
        alt[otc_symbol].update(barchart=False, otc_name=name, otc_last=(moved, own[moved]))
        report = ursachen.run(self.stand(), self.sid, FakeHttp(series, changes, nocp, {leader_symbol}, minute_changes=self.minute, alt=alt, otc={otc_symbol}), pause=self.fail_on_pause)
        days_c = report["zusatzquellen"]["tage"]
        self.assertEqual(days_c.get("zweite_quelle_otc_letzter_gleich_stand"), 1, "OTC Markets zeigt am Tag den Kurs des Stands – CNBC weicht ab")
        self.assertEqual(days_c.get("otc_letzter_abschluss_gleich"), 1)
        self.assertIn("lastSale", " ".join(report["zusatzquellen"]["felder"]))
        alt[otc_symbol].update(barchart=True, otc_name="Völlig Andere Gesellschaft")
        report = ursachen.run(self.stand(), self.sid, FakeHttp(series, changes, nocp, {leader_symbol}, minute_changes=self.minute, alt=alt, otc={otc_symbol}), pause=self.fail_on_pause)
        self.assertEqual(report["zusatzquellen"]["tage"].get("otc_letzter_abschluss_identitaet_nicht_bestaetigt"), 1, "anderer Name im Profil: kein Vergleich")
        # anderer Name bei CNBC: Identität nicht bestätigt – dann Barchart (nur Kürzel und Kursniveau) als Vergleichsquelle
        alt[otc_symbol]["name"] = "Völlig Andere Gesellschaft"
        report = ursachen.run(self.stand(), self.sid, FakeHttp(series, changes, nocp, {leader_symbol}, minute_changes=self.minute, alt=alt, otc={otc_symbol}), pause=self.fail_on_pause)
        self.assertEqual(report["zusatzquellen"]["je_quelle"], {"barchart": 1})
        self.assertEqual(report["zusatzquellen"]["pruefungen"].get("cnbc_identitaet_name_passt_nicht"), 1)
        # Kursniveau um einen Faktor anders (anderes Verhältnis ADR/Aktie): keine Quelle vergleichbar → ohne Vergleichskurse
        alt[otc_symbol] = {"name": name, "closes": {d: round(c * 10, 4) for d, c in own.items()}, "cnbc": True, "barchart": True}
        report = ursachen.run(self.stand(), self.sid, FakeHttp(series, changes, nocp, {leader_symbol}, minute_changes=self.minute, alt=alt, otc={otc_symbol}), pause=self.fail_on_pause)
        self.assertEqual(report["zusatzquellen"]["verglichen"], 0)
        self.assertEqual(report["ohne_vergleichskurse"], 1)
        self.assertEqual(report["zusatzquellen"]["pruefungen"].get("cnbc_kursniveau_faktor"), 1)
        self.assertEqual(report["urteil"], "unvollstaendig")

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
