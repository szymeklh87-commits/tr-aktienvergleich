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
# Wertpapierliste (nasdaqtraded.txt) und OpenFIGI aus den Angaben des DEMO-Stands (seit dem 25.10.2026, 09:20 Uhr: ohne abgesicherte
# Zuordnung kein Vergleich) – in setUpClass gefüllt
LISTING_NAMES: dict[str, str] = {}
FIGI_BY_ISIN: dict[str, dict] = {}


def fake_figi(isins: list[str]) -> dict[str, dict]:
    return {isin: FIGI_BY_ISIN.get(isin, {"status": "keine_zuordnung", "kandidaten": []}) for isin in isins}


def names_of(report: dict) -> set[str]:
    """Alle Buchstaben der Zuordnung eines Berichts."""
    return {x["aktie"] for x in report.get("zuordnung") or []}


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
                 minutes_2m: bool = False, minute_changes: dict[str, dict[int, float]] | None = None, alt: dict[str, dict] | None = None, otc: set[str] | None = None,
                 splits: dict[str, list[tuple[int, float]]] | None = None, world: dict[str, dict] | None = None, listing: bool = True,
                 yahoo_changes: dict[str, dict[int, float]] | None = None) -> None:
        self.series, self.changes, self.nocp, self.listed = series, nasdaq_changes, nocp, nasdaq_listed
        self.failures = dict(failures or {})
        self.minutes_2m = minutes_2m
        self.minute_changes = minute_changes or {}  # letzter Abschluss vor 16:00 Uhr anders als der Kurs des Stands
        self.alt = alt or {}  # Zusatzquellen je Kürzel: name, closes (Tag → Kurs), cnbc / barchart (an/aus), exchange
        self.otc = otc or set()  # Kürzel, für die Nasdaq keine Kurse führt (Yahoo-Börse PNK)
        self.splits = splits or {}  # von Yahoo gemeldete Splits je Kürzel: (Tag, Verhältnis)
        self.world = world or {}  # CNBC je Kürzel außerhalb der US-Auswahl: name, exchange, currency, closes
        self.listing = listing  # Wertpapierliste von Nasdaq Trader abrufbar?
        self.yahoo_changes = yahoo_changes or {}  # ab 1.19.0: heutige Yahoo-Tageskurse, die vom Stand abweichen (Stand veraltet)
        self.calls: list[str] = []

    def listing_text(self) -> str:
        lines = ["Nasdaq Traded|Symbol|Security Name|Listing Exchange|Market Category|ETF|Round Lot Size|Test Issue|Financial Status|CQS Symbol|NASDAQ Symbol|NextShares"]
        for symbol in sorted(self.series):
            if symbol in self.otc:
                continue
            exchange = "Q" if symbol in self.listed else "N"
            lines.append(f"Y|{symbol}|{LISTING_NAMES.get(symbol, symbol)} - Common Stock|{exchange}|Q|N|100|N|N|{'' if exchange == 'Q' else symbol}|{symbol}|N")
        lines.append("File Creation Time: 1025202606:00|||||||||||")
        return "\n".join(lines)

    def get(self, url: str, headers=None) -> Response:
        self.calls.append(url)
        parsed = urlparse(url)
        parts = parsed.path.split("/")
        if parsed.netloc == "www.nasdaqtrader.com":
            return Response(200, None, self.listing_text().encode("utf-8")) if self.listing else Response(403, None)
        if parsed.netloc == "api.nasdaq.com" and parts[2] == "screener":
            return Response(403, None)
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
            closes = [self.yahoo_changes.get(symbol, {}).get(d, own[d]) for d in days]
            events = {"splits": {str(k): {"date": d * 86400 + 13 * 3600 + 30 * 60, "numerator": ratio, "denominator": 1} for k, (d, ratio) in enumerate(self.splits.get(symbol, []))}}
            return Response(200, {"chart": {"result": [{"meta": meta, "timestamp": stamps, "events": events,
                                                        "indicators": {"quote": [{"close": closes, "volume": [1000] * len(days)}], "adjclose": [{"adjclose": closes}]}}]}})
        if self.world and parsed.netloc == "quote.cnbc.com":
            wanted = (parse_qs(parsed.query).get("symbols") or [""])[0].split("|")
            entries = [{"symbol": x, "code": 0, "name": self.world[x]["name"], "exchange": self.world[x]["exchange"], "currencyCode": self.world[x]["currency"]} for x in wanted if x in self.world]
            entries += [{"symbol": x, "code": 1} for x in wanted if x not in self.world]
            if any(x in self.world for x in wanted):
                return Response(200, {"FormattedQuoteResult": {"FormattedQuote": entries}})
        if self.world and parsed.netloc == "ts-api.cnbc.com" and parts[4] in self.world:
            bars = [{"tradeTime": (EPOCH + dt.timedelta(days=d)).strftime("%Y%m%d000000"), "close": f"{c:.4f}", "volume": "1000"} for d, c in sorted(self.world[parts[4]]["closes"].items())]
            return Response(200, {"barData": {"priceBars": bars}})
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
                stamp = d * 86400 if source.get("otc_midnight") else d * 86400 + 20 * 3600
                return Response(200, {"lastSale": v, "lastTradeTime": stamp * 1000, "volume": 100, "quoteTime": (d + 2) * 86400 * 1000})
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
        instruments = nachrechnen.Stand(cls.folder, cls.sid, None).get("instruments.bin")
        LISTING_NAMES.clear()
        FIGI_BY_ISIN.clear()
        for k, isin in enumerate(instruments["isin"]):
            symbol, key = str(instruments["symbol"][k] or ""), instruments["exchange_key"][k] or "US"
            LISTING_NAMES[symbol] = str(instruments["name"][k] or symbol)
            FIGI_BY_ISIN[isin] = {"status": "ok", "kandidaten": [{"boerse": key, "symbol": symbol, "code": "XX", "typ": "Common Stock", "typ2": "Common Stock"}]}
        cls._figi = ursachen.absicherung.figi_lookup
        ursachen.absicherung.figi_lookup = fake_figi  # OpenFIGI aus den Angaben des Stands (kein Netz)

    @classmethod
    def tearDownClass(cls) -> None:
        ursachen.absicherung.figi_lookup = cls._figi
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
        # NOCP-Historie aller Tage (wie bei Nasdaq): gleich dem Stand, nur am Stichtag der Nasdaq-Kurs (−10 %) – seit dem 25.10.2026 ist
        # ein Vergleich erst mit mindestens 10 gemeinsamen Tagen und passendem Kursniveau abgesichert
        nocp = {leader_symbol: {**series[leader_symbol], last_day: series[leader_symbol][last_day] * 0.9}}
        # letzter Abschluss vor 16:00 Uhr am Stichtag weder der Kurs des Stands noch der Nasdaq-Kurs: die Abweichung vom
        # offiziellen Schlusskurs ist dann ein Befund ohne belegte Ursache (seit dem 25.10.2026)
        self.minute = {leader_symbol: {last_day: series[leader_symbol][last_day] * 1.002}}
        return instruments, chosen, top10, first, places, series, changes, nocp, leader, leader_symbol, other_symbol

    def test_conspicuous_venue_stocks_are_examined_one_by_one_with_a_third_source(self):
        """Ab 1.19.0 (Auftrag vom 25.10.2026, 14:23 Uhr: „Untersuche die … auffälligen Aktien … über den vorhandenen autorisierten
        Entschlüsselungsweg“): jede auffällige Aktie des Börsenplatz-Abgleichs einzeln – Vergleichsplatz, Abweichung gegen
        Schwelle, Fundstelle – und eine dritte Quelle (CNBC) für die Kurse der Referenz an Start- und Endtag, nur mit passendem
        Namen, passender Börse und Währung. Ohne Kürzel, Namen oder ISINs in der Ausgabe."""
        import boersenplatz_auffaellige as venues

        stand = self.stand()
        instruments = stand.get("instruments.bin")
        probe = venues.run(stand, self.sid, FakeHttp({}, {}, {}, set()), pause=lambda s: None)
        self.assertGreater(len(probe["aktien"]), 0, "DEMO-Stand mit auffälligen Aktien")
        self.assertEqual(probe["zeitraeume"], sum(a["zeitraeume"] for a in probe["aktien"]))
        self.assertEqual(probe["zaehlung"]["auffaellige_aktien"], len(probe["aktien"]))
        self.assertEqual(sum(probe["zaehlung"]["aktie_zeitraum"].get(k, 0) for k in ("abweichung",)), probe["zeitraeume"])
        # dritte Quelle für die erste auffällige Aktie: CNBC mit den Kursen des Stands → bestätigt
        venue = instruments["venue"]
        flagged = sorted(venues.flagged_pairs(self.stand()), key=lambda i: (-len(venues.flagged_pairs(self.stand())[i]), i))
        i = flagged[0]
        key = instruments["exchange_key"][i]
        symbol = ursachen.welt.cnbc_candidates(str(instruments["symbol"][i]), key)[0]
        data = stand.get(f"series/{instruments['isin'][i]}.bin")
        closes = {int(d): float(c) for d, c in zip(data["d"], data["c"]) if c is not None}
        words = ursachen.welt.VENUE_WORDS.get(key) or ("?",)
        world = {symbol: {"name": str(instruments["name"][i]), "exchange": f"{words[0]} Exchange", "currency": instruments["price_unit"][i] or instruments["currency"][i],
                          "closes": closes}}
        report = venues.run(self.stand(), self.sid, FakeHttp({}, {}, {}, set(), world=world), pause=lambda s: None)
        first = report["aktien"][0]
        self.assertEqual(first["dritte_quelle"], "ok")
        self.assertEqual(set(first["pruefungen"]), {"bestaetigt"}, first["pruefungen"])
        self.assertEqual(first["pruefungen"]["bestaetigt"], 2 * first["zeitraeume"])
        title, head, rows = venues.lines(report)
        text = "\n".join([title] + head + rows)
        self.assertIn("Kurs der Referenz von CNBC bestätigt", text)
        self.assertNotIn(str(instruments["isin"][i]), text)
        if len(str(instruments["symbol"][i])) >= 5:
            self.assertNotIn(str(instruments["symbol"][i]), text)
        self.assertNotIn(str(instruments["name"][i]), text)
        # offen bleibt, was keine dritte Quelle hat – der Job wird dann rot (Datenqualität, kein App-Fehler)
        self.assertTrue(any("ohne dritte Quelle" in x for x in venues.unresolved(probe)), venues.unresolved(probe))
        every = {}
        for j in flagged:
            key_j = instruments["exchange_key"][j]
            sym_j = ursachen.welt.cnbc_candidates(str(instruments["symbol"][j]), key_j)[0]
            data_j = stand.get(f"series/{instruments['isin'][j]}.bin")
            exchange_j = "NASDAQ Global Select" if key_j in ursachen.absicherung.US_FAMILY else f"{(ursachen.welt.VENUE_WORDS.get(key_j) or ('?',))[0]} Exchange"
            every[sym_j] = {"name": str(instruments["name"][j]), "exchange": exchange_j,
                            "currency": instruments["price_unit"][j] or instruments["currency"][j],
                            "closes": {int(d): float(c) for d, c in zip(data_j["d"], data_j["c"]) if c is not None}}
        complete = venues.run(self.stand(), self.sid, FakeHttp({}, {}, {}, set(), world=every), pause=lambda s: None)
        self.assertEqual(venues.unresolved(complete), [], "jede auffällige Aktie von der dritten Quelle bestätigt")
        del venue

    def test_leaders_outside_the_us_are_checked_against_the_exchanges_own_archives(self):
        """Ab 1.19.0 (Auftrag vom 25.10.2026, 14:23 Uhr: „Prüfe die bisher ungeprüften Spitzenreiter, insbesondere Warschau und TSX
        Venture“): Aktien an XWAR gegen das Notierungsarchiv der GPW (ISIN je Zeile), an XTSX gegen TMX Money (Name, Börse,
        OpenFIGI) – dieselben strengen Prüfungen wie im Job „welt“, abweichende Tage neu gerechnet; Ausgabe ohne Namen, Kürzel, ISINs."""
        import spitzenreiter_boersen as leaders

        stand = self.stand()
        instruments = stand.get("instruments.bin")
        cutoff = int(stand.get("manifest.bin")["cutoff_day"])
        chosen, _, first = ursachen.welt.select_world(stand, instruments, ursachen.us_stocks(instruments))
        self.assertGreaterEqual(len(chosen), 2, "DEMO-Stand mit Aktien außerhalb der US-Auswahl unter den ersten 10")
        war, ven = chosen[0], chosen[1]
        keys, symbols = list(instruments["exchange_key"]), list(instruments["symbol"])
        currencies, units = list(instruments["currency"]), list(instruments.get("price_unit") or instruments["currency"])
        keys[war], symbols[war], currencies[war], units[war] = "XWAR", "WARTEST.WA", "PLN", "PLN"
        keys[ven], symbols[ven], currencies[ven], units[ven] = "XTSX", "VENTEST.V", "CAD", "CAD"
        stand._cache["instruments.bin"] = dict(instruments, exchange_key=keys, symbol=symbols, currency=currencies, price_unit=units)
        start_day = cutoff - ursachen.gegen.LOOKBACK_DAYS - 5
        own_war = ursachen.own_series(self.stand(), instruments, war, start_day, cutoff)
        own_ven = ursachen.own_series(self.stand(), instruments, ven, start_day, cutoff)
        odd_day = sorted(own_war)[-3]  # ein Tag, an dem die GPW 5 % höher schließt als der Stand
        isin_war, isin_ven = str(instruments["isin"][war]), str(instruments["isin"][ven])
        name_ven = str(instruments["name"][ven])

        def gpw_page(day: int) -> str:
            rows = "".join(
                f"<tr><td class='left'><a href='#'>{n}</a></td><td>{isin}</td><td>PLN</td><td>1</td><td>1</td><td>1</td>"
                f"<td>{c:,.2f}</td><td>0,00</td><td>12&nbsp;345</td><td>10</td><td>1,5</td></tr>".replace(",", "X").replace(".", ",").replace("X", " ")
                for n, isin, c in (("WARTEST", isin_war, own_war[day] * (1.05 if day == odd_day else 1.0)), ("ANDERE", "PL0000000000", 10.0)) if day in own_war)
            return ("<html><body><table class='table footable'><thead><tr><th>Nazwa</th><th>Kod ISIN</th><th>Waluta</th><th>Kurs<br>otwarcia</th>"
                    "<th>Kurs<br>max</th><th>Kurs<br>min</th><th>Kurs<br>zamknięcia</th><th>Zmiana<br>kursu %</th><th>Wolumen<br>obrotu<br>(w szt.)</th>"
                    f"<th>Liczba<br>transakcji</th><th>Wartość<br>obrotu<br>(w tys.)</th></tr></thead><tbody>{rows}</tbody></table></body></html>")

        class ExchangeHttp:
            def __init__(self) -> None:
                self.calls: list[str] = []

            def get(self, url: str, headers=None) -> Response:
                self.calls.append(url)
                parsed = urlparse(url)
                if parsed.netloc == "www.gpw.pl":
                    d, m, y = parse_qs(parsed.query)["date"][0].split("-")
                    day = (dt.date(int(y), int(m), int(d)) - EPOCH).days
                    return Response(200, None, gpw_page(day).encode("utf-8"))
                return Response(404, {"chart": {"result": None}})

            def post(self, url: str, json_body=None, headers=None) -> Response:
                self.calls.append(url)
                name = json_body["operationName"]
                if json_body["variables"]["symbol"] != "VENTEST":
                    return Response(200, {"data": {name: None}})
                if name == "getQuoteBySymbol":
                    return Response(200, {"data": {name: {"symbol": "VENTEST", "name": name_ven, "exchangeName": "TSX Venture Exchange", "exchangeCode": "CDX"}}})
                history = [{"datetime": (EPOCH + dt.timedelta(days=d)).isoformat(), "closePrice": c, "volume": 1000} for d, c in sorted(own_ven.items(), reverse=True)]
                return Response(200, {"data": {name: history}})

        def fake_figi(isins):
            out = {}
            for isin in isins:
                if isin == isin_ven:
                    out[isin] = {"status": "ok", "kandidaten": [{"boerse": "XTSX", "symbol": "VENTEST.V", "code": "CV", "typ": "Common Stock", "typ2": "Common Stock"}]}
                else:
                    out[isin] = {"status": "keine_zuordnung", "kandidaten": []}
            return out

        http = ExchangeHttp()
        report = leaders.run(stand, self.sid, http, figi_lookup=fake_figi, pause=lambda s: None)
        by_key = {a["boerse"]: a for a in report["aktien"]}
        self.assertEqual(set(by_key), {"XWAR", "XTSX"})
        self.assertEqual(by_key["XWAR"]["ergebnis"], "abgesichert", by_key["XWAR"])
        self.assertEqual(by_key["XWAR"]["abweichend"], 1, "der eine Tag mit 5 % Unterschied")
        self.assertEqual(by_key["XWAR"]["gleich"], len(own_war) - 1)
        self.assertAlmostEqual(by_key["XWAR"]["groesste_abweichung_pct"], 100 * (1 / 1.05 - 1) * -1, places=1)
        self.assertEqual(by_key["XTSX"]["ergebnis"], "abgesichert", by_key["XTSX"])
        self.assertEqual(by_key["XTSX"]["abweichend"], 0)
        self.assertEqual(report["quellen"]["gpw"], {"ok": len(own_war)})
        self.assertEqual(report["wirkung"]["neu_gerechnet"], 1)
        self.assertIn("Kurs\nzamknięcia".replace("\n", " "), report["spalten_gpw"])
        title, head, rows = leaders.lines(report)
        text = "\n".join([title] + head + rows)
        for secret in (isin_war, isin_ven, "WARTEST", "VENTEST", name_ven):
            self.assertNotIn(secret, text)
        self.assertIn("Notierungsarchiv der GPW", text)
        open_ = leaders.unresolved(report)
        self.assertTrue(any("Abweichung zur Börse" in x for x in open_), open_)
        # ohne Antwort der GPW: kein Vergleich, abgebrochen nach drei Tagen – der Spitzenreiter bleibt offen
        class Down(ExchangeHttp):
            def get(self, url, headers=None):
                self.calls.append(url)
                return Response(403, None) if "gpw.pl" in url else super().get(url, headers)

        down = Down()
        blocked = leaders.run(self.stand_with(stand), self.sid, down, figi_lookup=fake_figi, pause=lambda s: None)
        self.assertEqual(blocked["quellen"]["gpw"]["http_403"], 3)
        self.assertEqual(blocked["quellen"]["gpw"]["abgebrochen_nach_3_tagen_ohne_daten"], len(own_war) - 3)
        self.assertEqual({a["boerse"]: a["ergebnis"] for a in blocked["aktien"]}["XWAR"], "ohne_antwort")
        self.assertEqual(sum(1 for u in down.calls if "gpw.pl" in u), 6, "drei Tage, je eine Wiederholung")
        if first.get(war):
            self.assertTrue(any("Spitzenreiter ohne abgesicherten Vergleich" in x for x in leaders.unresolved(blocked)))
        rates = leaders.fx_probe(ExchangeHttp(), cutoff)
        self.assertEqual(len(rates), 4)
        self.assertTrue(all(": http_404" in x for x in rates), rates)

    def stand_with(self, stand: nachrechnen.Stand) -> nachrechnen.Stand:
        """Neuer Stand mit denselben geänderten Angaben (Cache) wie ``stand``."""
        fresh = self.stand()
        fresh._cache["instruments.bin"] = stand.get("instruments.bin")
        return fresh

    def test_data_gaps_are_classified_without_names_and_nothing_is_replaced(self):
        """Ab 1.19.0 (Auftrag vom 25.10.2026, 14:23 Uhr: „Kläre unzugeordnete Instrumente, fehlende Yahoo-Zuordnungen und fehlende
        Stichtagskurse. Nichtaktien weiterhin ausschließen.“): je Lücke der Grund als Code und eine heutige Nachfrage bei Yahoo –
        ohne ISINs, Kürzel oder Namen in der Ausgabe; am Stand wird nichts geändert."""
        import datenluecken as gaps
        from traktien.analytics.codes import Status

        stand = self.stand()
        instruments = stand.get("instruments.bin")
        cutoff = int(stand.get("manifest.bin")["cutoff_day"])
        n = len(instruments["isin"])
        before = json.dumps(instruments, sort_keys=True)
        unclear, london, missing, fund = 0, 1, 2, 3
        level = [0] * n
        level[unclear], level[london], level[missing], level[fund] = (Status.IDENTITAET_UNKLAR, Status.KEINE_KURSDATEN,
                                                                      Status.KURS_AM_STICHTAG_FEHLT, Status.KEIN_AKTIENINSTRUMENT)
        reasons = [None] * n
        reasons[unclear] = "keine unterstützte Börsennotierung gefunden"
        symbols = list(instruments["symbol"])
        keys = list(instruments["exchange_key"])
        symbols[london], keys[london] = "0ABC.L", "XLON"
        currencies = list(instruments["currency"])
        currencies[london] = "GBp"
        types = list(instruments.get("type") or [None] * n)
        types[fund] = "ETP"
        stand._cache["instruments.bin"] = dict(instruments, level_status=level, identity_reason=reasons, symbol=symbols, exchange_key=keys,
                                               currency=currencies, type=types)
        isin_unclear = str(instruments["isin"][unclear])
        missing_symbol = str(symbols[missing])

        class GapHttp:
            def __init__(self) -> None:
                self.calls: list[str] = []

            def get(self, url: str, headers=None) -> Response:
                self.calls.append(url)
                parsed = urlparse(url)
                if parsed.path.endswith("/v1/finance/search"):
                    q = parse_qs(parsed.query)["q"][0]
                    hits = [{"symbol": "AAA.ZZ", "exchange": "XYZ", "quoteType": "EQUITY"}] if q == isin_unclear else []
                    return Response(200, {"quotes": hits})
                symbol = parsed.path.split("/")[-1]
                bar = {"meta": {"gmtoffset": 0, "exchangeName": "IOB", "currency": "USD"}, "timestamp": [cutoff * 86400 + 16 * 3600],
                       "indicators": {"quote": [{"close": [10.0], "volume": [0 if symbol == missing_symbol else 100]}]}}
                if symbol in ("0ABC.IL", missing_symbol):
                    return Response(200, {"chart": {"result": [bar]}})
                return Response(404, {"chart": {"result": None, "error": {"code": "Not Found"}}})

        http = GapHttp()
        report = gaps.run(stand, self.sid, http)
        self.assertEqual(report["status"], {0: n - 4, int(Status.IDENTITAET_UNKLAR): 1, int(Status.KEINE_KURSDATEN): 1,
                                            int(Status.KURS_AM_STICHTAG_FEHLT): 1, int(Status.KEIN_AKTIENINSTRUMENT): 1})
        self.assertEqual(report["unklar"], {"keine_notierung_an_einer_boerse_der_app": 1})
        self.assertEqual(report["unklar_yahoo"], {"yahoo_kennt_die_isin_nur_an_anderen_boersen": 1})
        self.assertEqual(report["unklar_andere_boersen"], {"XYZ": 1})
        self.assertEqual(report["keine_kursdaten"], {"XLON:london_ziffer_vorn": 1})
        self.assertEqual(report["keine_kursdaten_probe"], {"heute_http_404": 1, "endung_il_ok_mit_stichtag_andere_waehrung": 1, "suche_ok_kein_treffer": 1})
        key_missing = keys[missing] or "ohne_boerse"
        self.assertEqual(report["stichtag_luecken"], {f"kurs_fehlt:{key_missing}": 1})
        self.assertEqual(report["stichtag"], gaps.nachrechnen._iso(cutoff), "Kursstand bleibt ein Datum (bis 25.10.2026, 15:30 Uhr überschrieben)")
        self.assertEqual(sum(report["umsatz"].values()), n - 4, "Ø-Umsatz-Status je Aktie mit Schlusskurs am Stichtag")
        self.assertEqual(gaps.reason_code("Kursanbieter meldet Instrumenttyp ETF"), "kursanbieter_meldet_typ_etf")
        self.assertEqual(gaps.reason_code("Name beim Kursanbieter (X) passt weder zur Identitätsquelle noch zur TR-Liste"), "name_beim_kursanbieter_passt_nicht")
        self.assertEqual(gaps.reason_code("Börsencode NYQ passt nicht zu Xetra"), "boersencode_der_kursdaten_passt_nicht")
        self.assertEqual(report["stichtag_probe"], {"kurs_fehlt_stichtag_heute_vorhanden_ohne_umsatz": 1})
        self.assertEqual(report["kein_aktieninstrument"], {"ETP": 1}, "Nichtaktien nur gezählt – sie bleiben ausgeschlossen")
        self.assertEqual(len(http.calls), 5, "je Lücke höchstens Kürzel, „.IL“ und Suche – kein Abruf für bereite Aktien oder Nichtaktien")
        text = "\n".join(x for _, body in gaps.lines(report) for x in body)
        self.assertIn("Geändert wird nichts", text)
        for secret in (isin_unclear, "0ABC", str(instruments["name"][unclear]), "AAA.ZZ") + ((missing_symbol,) if len(missing_symbol) >= 5 else ()):
            self.assertNotIn(secret, text)
        self.assertEqual(json.dumps(self.stand().get("instruments.bin"), sort_keys=True), before, "Stand auf der Platte unverändert")
        self.assertEqual(gaps.closable(report), ["Yahoo liefert unter der Endung „.IL“ Kurse bis zum Stichtag: 1"],
                         "nur ein Hinweis – die Währung weicht ab, geändert wird nichts")
        long = "Je Börse: " + ", ".join(f"X{k:03d}:sonstige {k}" for k in range(400))
        parts = gaps.split_long(long)
        self.assertGreater(len(parts), 1)
        self.assertTrue(all(len(p.encode("utf-8")) <= 2400 for p in parts))
        self.assertEqual(", ".join(p.split(": ", 1)[1] for p in parts), long.split(": ", 1)[1], "nichts geht beim Teilen verloren")

    def test_today_delivery_of_yahoo_is_observed_on_every_deviating_day(self):
        """Ab 1.19.0 (Auftrag vom 25.10.2026, 14:23 Uhr: „Untersuche die ungeklärten Kursabweichungen“): an jedem abweichenden Tag
        die heutige Lieferung von Yahoo – gleich dem Stand (nicht veraltet) oder gleich dem Vergleichskurs (Stand veraltet). Nur eine
        Beobachtung: die Einordnung der Ursache bleibt unverändert."""
        instruments, chosen, top10, first, places, series, changes, nocp, leader, leader_symbol, other_symbol = self.setup_case()
        old_day = next(iter(changes[other_symbol]))
        today = {other_symbol: {old_day: changes[other_symbol][old_day]}}  # Yahoo liefert heute den Nasdaq-Kurs
        report = ursachen.run(self.stand(), self.sid, FakeHttp(series, changes, nocp, {leader_symbol}, minute_changes=self.minute, yahoo_changes=today),
                              pause=self.fail_on_pause)
        self.assertEqual(report["yahoo_heute"]["nasdaq_historie"], {"wie_stand": 1, "wie_vergleich": 1})
        self.assertEqual(report["yahoo_heute"]["nocp"], {"wie_stand": 1}, "der Tag mit Stand ≠ NOCP: Yahoo liefert heute den Kurs des Stands")
        self.assertEqual(report["ursachen"], {"abweichung_vom_nocp": 1, "ungeklaert": 1}, "Einordnung unverändert")
        text = decoded(ursachen.annotations(report))
        self.assertIn("Heutige Lieferung von Yahoo an den abweichenden Tagen", text)
        self.assertIn("gegen die Nasdaq-Historie: wie Stand 1, wie Vergleichskurs (Stand veraltet) 1, dritter Kurs 0, ohne Tag 0", text)
        rows = {x["aktie"]: x.get("yahoo_heute") for x in report["aktien"]}
        self.assertEqual(sorted(rows.values(), key=str), [{"wie_stand": 1}, {"wie_vergleich": 1}], "je abweichender Aktie ihr Tag")
        _, _, lines, sections = ursachen.build_lines(report)  # Langform (Zusammenfassung des Jobs)
        full = "\n".join(lines + [x for _, part in sections for x in part])
        self.assertIn("Yahoo heute an diesen Tagen: wie Vergleichskurs (Stand veraltet) 1", full)
        plain = ursachen.run(self.stand(), self.sid, FakeHttp(series, changes, nocp, {leader_symbol}, minute_changes=self.minute), pause=self.fail_on_pause)
        self.assertEqual(plain["yahoo_heute"]["nasdaq_historie"], {"wie_stand": 2}, "Yahoo liefert heute die Kurse des Stands")

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
        # offizieller Schlusskurs an allen Tagen der Nasdaq-notierten Aktie: gleich bis auf den Stichtag
        n_leader = len(series[leader_symbol])
        self.assertEqual(report["nocp_vergleich"], {"aktien": 1, "tage": n_leader, "stand_gleich": n_leader - 1, "stand_ungleich": 1, "nasdaq_historie_gleich": n_leader})
        self.assertEqual(report["nocp_ursachen"], {"befund_nasdaq_gleich_nocp": 1}, "Minutenkurs weder Stand noch NOCP: keine belegte Ursache")
        # Ergebnisarten getrennt: Übereinstimmung, Abweichung, belegt, plausibel, ohne Erklärung, fehlende Prüfmöglichkeit
        a = report["kategorien"]["nasdaq_historie"]
        self.assertEqual((a["abweichung"], a["belegt"], a["plausibel"], a["ohne_erklaerung"], a["stand_ist_nocp"]), (2, 0, 0, 2, 0))
        self.assertEqual(a["uebereinstimmung"], report["tage"]["verglichen"] - 2)
        self.assertEqual(a["ohne_vergleich_aktien"], 0)
        b = report["kategorien"]["offizieller_schlusskurs"]
        self.assertEqual((b["uebereinstimmung"], b["abweichung"], b["belegt"], b["plausibel"], b["ohne_erklaerung"]), (n_leader - 1, 1, 0, 0, 1))
        self.assertEqual(b["ohne_vergleich_aktien"], len(chosen) - 1, "nur eine Aktie mit NOCP")
        # je Aktie und Tag genau einmal: der Stichtag der besten Aktie weicht in beiden Vergleichen ab – ein Fall, nicht zwei
        u = report["je_aktie_und_tag"]
        self.assertEqual((u["ohne_erklaerung"], u.get("plausibel", 0), u.get("belegt", 0)), (2, 0, 0))
        self.assertEqual((u["abweichend_in_beiden"], u["abweichend_nur_nasdaq_historie"]), (1, 1))
        self.assertEqual(u["uebereinstimmung"] + u["ohne_erklaerung"], u["verglichen"])
        # Absicherung: jede Prüfung je Vergleich bestanden (Wertpapierliste, OpenFIGI, Name, Börse, Währung, Tage …)
        self.assertEqual(report["nicht_abgesichert"], 0)
        self.assertEqual(report["absicherung"]["nasdaq_abgesichert"], len(chosen))
        self.assertEqual(report["absicherung"]["nocp_abgesichert"], 1)
        self.assertEqual(report["wertpapierliste"]["status"], "ok")
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
        self.assertTrue(lines[0].startswith("::error title=Kursursachen: NICHT VOLLSTÄNDIG BELEGT – 2 von 2 abweichenden Aktientagen ungeklärt (0 davon mit plausibler Erklärung)::"))
        self.assertIn("festgestellte Abweichung 2 – davon Ursache belegt 0 (–), Stand = offizieller Schlusskurs 0 (abweichend nur die Nasdaq-Historie), ungeklärt mit plausibler "
                      "Erklärung 0 (–), ungeklärt ohne Erklärung 2 (Befund Stand ≠ NOCP bei Nasdaq-Historie = NOCP 1, ohne Befund 1)", text)
        self.assertIn("Befund ohne belegte Ursache: Nasdaq-notiert – Nasdaq-Historie = NOCP, Stand nicht 1", text)
        self.assertIn("Überschneidung: in beiden Vergleichen abweichend 1, nur Nasdaq-Historie 1, nur NOCP 0", text)
        self.assertIn("Nasdaq-Historie: abgesichert", text)
        # schnelle Bestimmung von Platz 1 je Teilmenge gegen die unabhängige Rechnung geprüft; kleinste Menge nachweislich
        for change in report["aenderungen_nasdaq"]:
            if change["platz1"] and not change["nicht_untersucht"]:
                self.assertTrue(change["suche"]["schnell"], change["suche"])
                if change["suche"]["groesse"] == 1:
                    self.assertTrue(change["suche"]["nachgewiesen"])
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
        # Split 2:1 am Tag split_day von Yahoo gemeldet: unbereinigter NOCP davor um den Split bereinigt gleich dem Stand – belegt
        report = ursachen.run(self.stand(), self.sid, FakeHttp(series, changes, nocp, {leader_symbol, third}, minute_changes=self.minute, splits={third: [(split_day, 2.0)]}),
                              pause=self.fail_on_pause)
        before_split = sum(1 for d in days if d < split_day)
        self.assertEqual(report["nocp_vergleich"]["faktor_split"], before_split)
        self.assertEqual(report["nocp_vergleich"]["stand_ungleich"], 1, "nur der eine Tag der besten Aktie")
        self.assertEqual(report["nocp_vergleich"]["aktien"], 2)
        self.assertEqual(report["ursachen"], {"abweichung_vom_nocp": 1, "ungeklaert": 1})
        self.assertEqual(report["kategorien"]["offizieller_schlusskurs"]["belegt"], before_split, "Ursache belegt: gemeldeter Split passenden Verhältnisses nach dem Tag")
        self.assertIn(f"Faktor eines gemeldeten Splits {before_split} (NOCP unbereinigt", "\n".join(ursachen.annotations(report)))
        third_i = next(i for i in chosen if str(instruments["symbol"][i]) == third)
        self.assertNotIn(str(third_i), report["uebergabe"]["b"], "Tage mit gemeldetem Split werden nicht ersetzt")
        # ohne gemeldeten Split ist der Faktor nicht erklärt: der NOCP dieser Aktie ist nicht abgesichert (Bereinigung) – kein Vergleich
        report = ursachen.run(self.stand(), self.sid, FakeHttp(series, changes, nocp, {leader_symbol, third}, minute_changes=self.minute), pause=self.fail_on_pause)
        self.assertEqual(report["nocp_vergleich"]["aktien"], 1)
        self.assertEqual(report["absicherung"].get("nocp_grund_bereinigung"), 1)
        self.assertEqual(report["kategorien"]["offizieller_schlusskurs"]["nicht_abgesichert_aktien"], 1)
        # Abstimmung mit den Läufen vor der Absicherung: der nicht abgesicherte NOCP wird nur gezählt – Faktor ohne gemeldeten Split
        rec = report["abstimmung_nocp"]
        self.assertEqual((rec["aktien"], rec["abweichend"], rec["ursache_split_ohne_ereignis"]), (1, before_split, before_split))
        self.assertEqual(report["abstimmung_nasdaq"], {}, "die Nasdaq-Historie dieser Aktie ist abgesichert")
        self.assertIn("Abstimmung mit den Zählungen vor der Absicherung", decoded(ursachen.annotations(report)))
        self.assertIn("abstimmung_nocp", report["uebergabe"]["zaehler"])
        # beide Vergleiche nicht abgesichert (ISIN laut OpenFIGI mit anderem Kürzel): die Aktie ist „nicht abgesichert“, beide Vergleiche gezählt
        third_isin = str(instruments["isin"][third_i])
        saved = FIGI_BY_ISIN.get(third_isin)
        FIGI_BY_ISIN[third_isin] = {"status": "ok", "kandidaten": [{"boerse": "US", "symbol": "ANDERS", "varianten": [], "code": "US", "typ": "Common Stock", "typ2": "Common Stock"}]}
        try:
            report = ursachen.run(self.stand(), self.sid, FakeHttp(series, changes, nocp, {leader_symbol, third}, minute_changes=self.minute), pause=self.fail_on_pause)
        finally:
            if saved is None:
                FIGI_BY_ISIN.pop(third_isin, None)
            else:
                FIGI_BY_ISIN[third_isin] = saved
        self.assertEqual(report["nicht_abgesichert"], 1)
        self.assertEqual((report["abstimmung_nasdaq"].get("aktien"), report["abstimmung_nocp"].get("aktien")), (1, 1))
        self.assertEqual(report["abstimmung_nasdaq"]["tage"], len(series[third]))
        gap = report["uebergabe"]["luecken"][str(third_i)]
        self.assertEqual((gap["grund"], "aktie" in gap["pruefungen"].split(",")), ("nasdaq_nicht_abgesichert", True))
        self.assertNotIn(third, decoded(ursachen.annotations(report)))

    def test_last_trade_from_minute_candles_is_only_a_plausible_explanation(self):
        """Stand = letzte Minutenkerze vor 16:00 Uhr (Kerzen zu 2 Minuten, 58 Tage): Bis 25.10.2026, 05:30 Uhr galt das als belegte Ursache
        (fehlende Schlussauktion). Seit dem Auftrag vom 25.10.2026, 09:20 Uhr (Punkt 2: „Gleicher Kurs wie eine Minutenkerze beweist allein
        keine ausgelassene Schlussauktion“) ist es eine plausible Erklärung – die Abweichung bleibt ungeklärt, das Urteil „nicht belegt“."""
        _, _, _, _, _, series, changes, nocp, _, leader_symbol, _ = self.setup_case()
        report = ursachen.run(self.stand(), self.sid, FakeHttp(series, changes, nocp, {leader_symbol}, minutes_2m=True), pause=self.fail_on_pause)
        self.assertEqual(report["ursachen"], {"letzter_abschluss": 2})
        self.assertEqual(report["nocp_ursachen"], {"letzter_abschluss": 1}, "auch in Variante (b) nur plausibel")
        a, b = report["kategorien"]["nasdaq_historie"], report["kategorien"]["offizieller_schlusskurs"]
        self.assertEqual((a["belegt"], a["plausibel"], a["ohne_erklaerung"]), (0, 2, 0))
        self.assertEqual((b["belegt"], b["plausibel"], b["ohne_erklaerung"]), (0, 1, 0))
        self.assertEqual(report["je_aktie_und_tag"]["plausibel"], 2, "zwei Aktientage, nicht drei Fälle")
        self.assertEqual(report["urteil"], "ungeklaert")
        self.assertTrue(ursachen.annotations(report)[0].startswith("::error title=Kursursachen: NICHT VOLLSTÄNDIG BELEGT – 2 von 2 abweichenden Aktientagen ungeklärt (2 davon mit plausibler Erklärung)::"))

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
        self.assertTrue(ursachen.annotations(report)[0].startswith("::error title=Kursursachen: UNVOLLSTÄNDIG – 1 Aktien ohne Antwort einer Quelle%2C 0 ohne Vergleichskurse%2C 0 nicht abgesichert;"))

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
        self.assertEqual(report["ursachen"], {"letzter_abschluss": 1}, "die übrige Abweichung bleibt plausibel erklärt")
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
        for shard in ursachen.US_LEGS:
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

    def world_sources(self, instruments, closes_change: dict[int, dict[int, float]] | None = None) -> tuple[dict[str, dict], list[int], int]:
        """CNBC-Antworten für alle Aktien außerhalb der US-Auswahl mit Platz unter den ersten 10 (Name, Börse, Währung des Stands, Kurse
        des Stands); ``closes_change``: einzelne Tage anders. Rückgabe: Antworten, Auswahl, Zahl der Aktien ohne Regel für das Kürzel."""
        stand = self.stand()
        chosen, _, _ = ursachen.welt.select_world(stand, instruments, ursachen.us_stocks(instruments))
        world: dict[str, dict] = {}
        cutoff = int(stand.get("manifest.bin")["cutoff_day"])
        no_rule = 0
        for i in chosen:
            key = instruments["exchange_key"][i]
            candidates = ursachen.welt.cnbc_candidates(str(instruments["symbol"][i]), key)
            if not candidates:
                no_rule += 1
                continue
            data = stand.get(f"series/{instruments['isin'][i]}.bin")
            closes = {int(d): round(float(c), 4) for d, c in zip(data["d"], data["c"]) if c is not None and int(d) >= cutoff - 150}
            closes.update((closes_change or {}).get(i, {}))
            words = ursachen.welt.VENUE_WORDS.get(key) or ("?",)
            world[candidates[0]] = {"name": str(instruments["name"][i]), "exchange": f"{words[0]} Exchange", "currency": instruments["price_unit"][i] or instruments["currency"][i], "closes": closes}
        return world, chosen, no_rule

    def test_world_gaps_are_named_per_stock_and_exchange(self):
        """Auftrag Punkt 6 („Dokumentiere Abdeckung und verbleibende Lücken nach Aktien, Handelstagen, Börsen und Ranglisten“): jede Aktie
        ohne abgesicherten Vergleich mit Buchstaben, Börse, Kursbereich, ungeprüften Tagen und Grund; je Börse die nicht bestandenen
        Prüfungen – ohne Kürzel und Namen."""
        _, _, _, _, _, series, changes, nocp, _, leader_symbol, _ = self.setup_case()
        instruments = self.stand().get("instruments.bin")
        world, chosen, no_rule = self.world_sources(instruments)
        candidates = [i for i in chosen if ursachen.welt.cnbc_candidates(str(instruments["symbol"][i]), instruments["exchange_key"][i])]
        self.assertGreaterEqual(len(candidates), 2)
        missing, wrong = candidates[0], candidates[1]
        cnbc = lambda i: ursachen.welt.cnbc_candidates(str(instruments["symbol"][i]), instruments["exchange_key"][i])[0]  # noqa: E731
        world.pop(cnbc(missing))
        world[cnbc(wrong)] = dict(world[cnbc(wrong)], currency="XXX")
        report = ursachen.run_world_leg(self.stand(), self.sid, FakeHttp(series, changes, nocp, {leader_symbol}, world=world))
        self.assertEqual((report["nicht_abgesichert"], report["ohne_vergleichskurse"]), (1, no_rule + 1))
        gaps = report["uebergabe"]["luecken"]
        self.assertEqual((gaps[str(missing)]["grund"], gaps[str(wrong)]["grund"]), ("nicht_gefunden", "nicht_abgesichert"))
        self.assertIn("waehrung", gaps[str(wrong)]["pruefungen"].split(","))
        self.assertGreater(gaps[str(wrong)]["tage_stand"], 0)
        key = instruments["exchange_key"][wrong]
        self.assertEqual(report["welt"]["je_boerse"][key].get("nicht_bestanden_waehrung"), 1)
        self.assertGreater(report["welt"]["je_boerse"][key].get("tage_stand_ungeprueft", 0), 0)
        legend = [x for x in report["weitere_buchstaben"] if x.get("luecke")]
        self.assertEqual(len(legend), no_rule + 2, "jede Lücke mit Buchstaben")
        self.assertTrue(all(x["top10"] > 0 for x in legend), "alle ausgewählten Aktien stehen unter den ersten 10")
        text = decoded(ursachen.annotations(report))
        self.assertIn("Lücken je Aktie – ", text)
        self.assertIn("nicht bestanden: Währung angegeben und gleich 1", text)
        self.assertIn("Grund: Kurse gefunden, Zuordnung nicht ausreichend abgesichert; nicht bestanden: Währung angegeben und gleich", text)
        for i in (missing, wrong):
            if len(str(instruments["symbol"][i])) >= 5:
                self.assertNotIn(str(instruments["symbol"][i]), text)
            self.assertNotIn(str(instruments["isin"][i]), text)

    def test_world_stock_without_answer_is_a_failed_fetch_not_a_missing_listing(self):
        """Gegenprüfung des Testberichts (25.10.2026): im Job „welt“ stand „ohne Antwort“ fest auf 0 – eine Aktie, deren Abruf bei CNBC
        scheiterte, galt als „bei CNBC nicht gefunden“. Jetzt zählt sie als „ohne Antwort“ (Abruf fehlgeschlagen): im Titel, in der
        Abdeckung, in der Lücke mit Grund und in der Übergabe an den Job „gemeinsame Wirkung“, der sie ebenso führt."""
        _, _, _, _, _, series, changes, nocp, _, leader_symbol, _ = self.setup_case()
        instruments = self.stand().get("instruments.bin")
        world, chosen, no_rule = self.world_sources(instruments)
        candidates = [i for i in chosen if ursachen.welt.cnbc_candidates(str(instruments["symbol"][i]), instruments["exchange_key"][i])]
        self.assertGreaterEqual(len(candidates), 1)
        target = candidates[0]
        symbol = ursachen.welt.cnbc_candidates(str(instruments["symbol"][target]), instruments["exchange_key"][target])[0]

        class FailingBars(FakeHttp):
            def get(self, url, headers=None):
                if urlparse(url).netloc == "ts-api.cnbc.com" and f"/bars/{symbol}/" in url:
                    return Response(503, None)
                return super().get(url, headers=headers)

        pauses: list[float] = []
        report = ursachen.run_world_leg(self.stand(), self.sid, FailingBars(series, changes, nocp, {leader_symbol}, world=world), pause=pauses.append)
        self.assertEqual(pauses, [ursachen.welt.RETRY_PAUSE_S], "eine Wiederholung nach einer Pause")
        self.assertEqual((report["abruf_fehlgeschlagen"], report["ohne_vergleichskurse"], report["nicht_abgesichert"]), (1, no_rule, 0))
        self.assertEqual(report["abdeckung_je_gruppe"]["welt"]["abruf_fehlgeschlagen"], 1)
        transfer = report["uebergabe"]
        self.assertEqual(transfer["fehlgeschlagen"], {str(target): "ohne_antwort"})
        self.assertEqual(transfer["luecken"][str(target)]["grund"], "ohne_antwort")
        self.assertIn("Tageskerzen von CNBC ohne Antwort (http_503", transfer["luecken"][str(target)]["befund"])
        title, _, lines, _ = ursachen.build_world_lines(report)
        self.assertIn("1 Aktien ohne Antwort einer Quelle", title)
        self.assertIn("Abruf fehlgeschlagen 1 (CNBC ohne Antwort", "\n".join(lines))
        legend = [x for x in report["weitere_buchstaben"] if x.get("luecke") and x["luecke"]["grund"] == "ohne_antwort"]
        self.assertEqual(len(legend), 1)
        self.assertIn("ohne Antwort der abgefragten Quelle", ursachen._legend(legend[0]))
        self.assertNotIn("Nasdaq", ursachen._legend(legend[0]), "für diese Aktie war nur CNBC abgefragt")
        text = decoded(ursachen.annotations(report))
        self.assertNotIn(str(instruments["isin"][target]), text)
        if len(str(instruments["symbol"][target])) >= 5:
            self.assertNotIn(str(instruments["symbol"][target]), text)

    def test_combined_recomputation_equals_one_job_with_every_stock(self):
        """Auftrag vom 25.10.2026, 03:47 Uhr, Punkt 1: die Vergleichskurse aller Jobs gemeinsam gegen denselben Stand. Die
        gemeinsame Rechnung aus den verschlüsselten Übergaben der Jobs ergibt genau die Wirkung eines einzigen Jobs mit allen
        Aktien – und je Job allein genau die Wirkung, die dieser Job selbst gerechnet hat. Seit dem 25.10.2026, 09:20 Uhr dazu der
        Job außerhalb der US-Auswahl (CNBC, Variante d), (b)+(c) und (b)+(c)+(d) gemeinsam mit der Wechselwirkung der Teile, die
        Quelle je Aktie und Tag und die Abdeckung des ganzen Aktienuniversums."""
        _, chosen, top10, first, _, series, changes, nocp, leader, leader_symbol, other_symbol = self.setup_case()
        stand = self.stand()
        instruments = stand.get("instruments.bin")
        legs = {}
        for shard in ursachen.US_LEGS:
            legs[shard] = ursachen.run(self.stand(), self.sid, FakeHttp(series, changes, nocp, {leader_symbol}, minute_changes=self.minute), pause=self.fail_on_pause, auswahl=shard)
        whole = ursachen.run(self.stand(), self.sid, FakeHttp(series, changes, nocp, {leader_symbol}, minute_changes=self.minute), pause=self.fail_on_pause, auswahl="alle")
        # außerhalb der US-Auswahl: CNBC mit den Kursen des Stands, bei der häufigsten Aktie ein Tag −8 %
        world_probe, world_chosen, no_rule = self.world_sources(instruments)
        changed_world: dict[int, dict[int, float]] = {}
        if world_chosen and world_probe:
            target = next(i for i in world_chosen if ursachen.welt.cnbc_candidates(str(instruments["symbol"][i]), instruments["exchange_key"][i]))
            symbol = ursachen.welt.cnbc_candidates(str(instruments["symbol"][target]), instruments["exchange_key"][target])[0]
            last = max(world_probe[symbol]["closes"])
            changed_world = {target: {last: round(world_probe[symbol]["closes"][last] * 0.92, 4)}}
        world, _, _ = self.world_sources(instruments, changed_world)
        legs[ursachen.WORLD_LEG] = ursachen.run_world_leg(self.stand(), self.sid, FakeHttp(series, changes, nocp, {leader_symbol}, world=world))
        w = legs[ursachen.WORLD_LEG]
        self.assertEqual(w["ausgewaehlt"], len(world_chosen))
        self.assertEqual(w["nicht_abgesichert"], 0, w["absicherung"])
        self.assertEqual(w["ohne_vergleichskurse"], no_rule)
        if changed_world:
            self.assertEqual(w["je_aktie_und_tag_welt"].get("ohne_erklaerung", 0) + w["je_aktie_und_tag_welt"].get("plausibel", 0), 1, "der eine geänderte Tag")
            self.assertEqual(len(w["uebergabe"]["d"]), 1)
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
            for shard in ursachen.US_LEGS:
                self.assertEqual(report["ranglisten"][f"{v}@{shard}"], legs[shard][key_whole], f"je Job allein ({v}, {shard})")
        self.assertEqual(report["ranglisten"]["d"], w["ranglisten_welt"], "gemeinsam (d) = der Job außerhalb der US-Auswahl")
        # (c) ist hier leer: (b)+(c) wirkt wie (b), und nichts entsteht erst gemeinsam oder hebt sich auf
        self.assertEqual(report["ranglisten"]["bc"], report["ranglisten"]["b"])
        bc = report["wechselwirkung"]["b+c+bc"]["zaehler"]
        for prop in ursachen.INTERACTION_PROPS:
            self.assertEqual((bc.get(f"{prop}_erst_gemeinsam", 0), bc.get(f"{prop}_aufgehoben", 0)), (0, 0), prop)
            self.assertEqual(bc.get(f"{prop}_gemeinsam", 0), bc.get(f"{prop}_mit_p", 0), prop)
        self.assertEqual(bc.get("aktien_rang_gemeinsam", 0), bc.get("aktien_rang_mit_p", 0))
        self.assertIn("b+cd+bcd", report["wechselwirkung"])
        # Lauf 40184599190: „1980 Ranglisten mit einer Änderung in einem Teil“ zählte auch leere Ranglisten – jetzt nur solche mit Einträgen
        filled = report["universum"]["ranglisten"]["ranglisten"]
        for name, item in report["wechselwirkung"].items():
            self.assertLessEqual(item["zaehler"].get("ranglisten", 0), filled, name)
        leaders_whole = {(c["h"], c["gruppe"], c["w"]) for c in whole["aenderungen_nasdaq"] if c["platz1"]}
        leaders_combined = {(c["h"], c["gruppe"], c["w"]) for c in report["aenderungen"]["a"] if c["platz1"]}
        self.assertEqual(leaders_combined, leaders_whole)
        if first.get(leader):
            self.assertTrue(leaders_combined, "−10 % am Stichtag kostet Platz 1")
            for c in report["aenderungen"]["a"]:
                if c["platz1"]:
                    self.assertIn("erste10", c["auch_einzeln"], "die Abweichung der besten Aktie liegt im Job „erste 10“")
            for c in report["aenderungen"]["bc"]:
                if c["platz1"]:
                    self.assertEqual(c["gleich_mit_teil"], ["b"], "gemeinsam derselbe neue Platz 1 wie mit (b) allein")
        # Quelle je Aktie und Tag: jede ersetzte Aktie genau eine Quelle, keine Überschneidung, Prüfsumme
        sources = report["quellen_je_aktie_und_tag"]
        self.assertEqual(sources["ueberschneidung_aktientage"], 0)
        expected_days = sum(len(rows) for t in transfers.values() for v in ("b", "c", "d") for rows in (t.get(v) or {}).values())
        self.assertEqual(sources["aktientage"], expected_days)
        self.assertEqual(len(sources["pruefsumme"]), 16)
        # Abdeckung des ganzen Universums: jede Aktie genau einmal, je Börse
        universe = report["universum"]
        self.assertEqual(universe["gesamt"]["aktien"], len(instruments["isin"]))
        states = sum(v for k, v in universe["gesamt"].items() if k.startswith("aktien_") and not k.startswith("aktien_unter_ersten_10"))
        self.assertEqual(states, len(instruments["isin"]))
        self.assertEqual(universe["ranglisten"]["platz_1"], universe["ranglisten"]["ranglisten"])
        # Platz 1 ohne abgesicherten Vergleich: jede solche Rangliste genau einmal, mit Buchstaben
        unchecked = universe["platz1_ungeprueft"]
        self.assertEqual(len(unchecked), universe["ranglisten"]["platz_1"] - universe["ranglisten"]["platz_1_abgesichert"])
        self.assertTrue(all(x["aktie"] in names_of(report) for x in unchecked))
        # Lauf 40181869022: Aktien außerhalb der US-Auswahl standen in der Zuordnung mit „unter den ersten 10 in 0 Ranglisten“, auch auf
        # Platz 1 – jetzt zählen die Plätze aller Aktien; ohne Vergleichskurse mit Börse, Kursbereich und Grund
        legend = {x["aktie"]: x for x in report["weitere_buchstaben"]}
        world_letters = [x for x in legend.values() if x.get("quelle") == "cnbc_welt"]
        for entry in world_letters:
            self.assertGreater(entry["top10"], 0, entry)
        for x in report["zuordnung"]:
            entry = legend.get(x["aktie"])
            if entry and x["fundstelle"] and x["fundstelle"]["platz"] <= 10:
                self.assertGreater(entry["top10"], 0, f"{x} steht unter den ersten 10, also nicht „in 0 Ranglisten“")
        gap_letters = [x for x in legend.values() if x.get("luecke")]
        if no_rule:
            self.assertTrue(gap_letters, "Aktien ohne Regel für das Kürzel stehen mit Grund in der Legende")
            self.assertTrue(any(x["luecke"]["grund"] == "ohne_kuerzelregel" for x in gap_letters))
            # seit dem 25.10.2026, 11:45 Uhr mit Befund (Codes, keine Namen)
            self.assertTrue(all(x["luecke"].get("befund") for x in gap_letters if x["luecke"]["grund"] == "ohne_kuerzelregel"))
        text = decoded(ursachen.annotations(report))
        summary = ursachen.summary_markdown(report)
        # Hinweise in Kurzform (höchstens 50 je Job), Zusammenfassung in Langform – dieselben Abschnitte
        compact_sections = ursachen.build_lines(report, compact=True)[3]
        compact_text = "\n".join(line for _, lines in compact_sections for line in lines)
        if unchecked:
            self.assertIn("Platz 1 ohne abgesicherten Vergleich der Aktie:", compact_text)
            self.assertIn("Platz 1 ohne abgesicherten Vergleich der Aktie:", summary)
        if gap_letters:
            self.assertIn("Grund: ", summary)
        if report["zuordnung"]:
            self.assertIn("Kurzform der Fundstelle", compact_text)
            self.assertNotIn("Kurzform der Fundstelle", summary, "Zusammenfassung in Langform")
        self.assertEqual({name.split(" – (b), (c)")[0] for name, _ in compact_sections} - {"Gemeinsam: andere Reihenfolge der ersten 10 bei gleichen Aktien – übrige Varianten"},
                         {name for name, _ in ursachen.build_lines(report)[3]}, "dieselben Abschnitte in Kurz- und Langform")
        for name, lines in compact_sections:
            if name.startswith("Gemeinsam: Platz 1 anders – (b)"):
                self.assertTrue(all(len(line.encode("utf-8")) < 4000 or "gemeinsam b " in line for line in lines), "(b)+(c) und (b)+(c)+(d) wie (b): Kurzform")
        self.assertTrue(text.startswith("::error title=Kursursachen gemeinsam:") or text.startswith("::notice title=Kursursachen gemeinsam:"))
        self.assertIn(f"Ausgewählt: {len(chosen)} US-Aktien", text)
        self.assertIn("keine Vollprüfung aller Aktien der App", text)
        for shard in ursachen.LEGS:
            self.assertIn(f"Prüfsumme {legs[shard]['uebergabe']['pruefsumme']}", text)
        self.assertIn("Gemeinsam (a) Nasdaq-Historie an allen abweichenden Tagen:", text)
        self.assertIn("Gemeinsam (b)+(c) offizieller Schlusskurs und CNBC gemeinsam (US-Auswahl):", text)
        self.assertIn("Wechselwirkung (bc) gegen (b) und (c) allein", text)
        self.assertIn("Aktienuniversum der App (alle Aktien des Stands):", text)
        self.assertIn("Zum Vergleich je Job allein:", text)
        self.assertIn("Quelle je Aktie und Tag", summary)
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
        self.assertIn(f"gegen den unveränderten Stand {self.sid}", text)
        if report["zuordnung"]:
            self.assertIn(f"Datenstand {self.sid}", summary, "Zuordnung vollständig in der Zusammenfassung")
        plan = ursachen.annotation_plan(report)
        self.assertEqual(plan["ausgegeben"] + plan["nicht_ausgegeben"], plan["teile"], "jedes Teil ausgegeben oder gezählt")
        self.assertLessEqual(sum(len(step) for step in plan["schritte"]), ursachen.MAX_JOB_ANNOTATIONS)
        # alle Aktien abgesichert verglichen → „gerechnet“ (außer Aktien ohne Regel für das Kürzel bei CNBC); fehlt die Übergabe eines Jobs → unvollständig
        self.assertEqual(report["urteil"], "gerechnet" if no_rule == 0 else "unvollstaendig")
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
        # streng abgesichert (seit dem 25.10.2026, 09:20 Uhr): CNBC besteht jede Prüfung; Barchart nennt weder Namen noch Börse noch
        # Währung – „nur Kürzel“ reicht nicht, Barchart ist weder Vergleichsquelle noch zweite Quelle
        sec = report["absicherung"]
        self.assertEqual(sec.get("cnbc_abgesichert"), 1)
        self.assertEqual(sec.get("barchart_nicht_abgesichert"), 1)
        for reason in ("name", "handelsplatz", "waehrung"):
            self.assertEqual(sec.get(f"barchart_grund_{reason}"), 1, reason)
        self.assertEqual(z["tage"].get("otc_kursmeldung_ohne_kursmeldung"), 1, "keine Kursmeldung von OTC Markets")
        c = report["kategorien"]["zusatzquellen"]
        self.assertEqual((c["abweichung"], c["plausibel"], c["ohne_erklaerung"]), (1, 0, 1))
        self.assertGreater(c["uebereinstimmung"], 10)
        self.assertEqual(z["tage"].get("zweite_quelle_keine"), 1, "Barchart ist nicht abgesichert – keine zweite Quelle")
        self.assertEqual(report["je_aktie_und_tag_zusatz"]["ohne_erklaerung"], 1)
        group = next(g for g, v in report["abdeckung_je_gruppe"].items() if v.get("verglichen_cnbc"))
        self.assertEqual(report["abdeckung_je_gruppe"][group]["verglichen_cnbc"], 1)
        self.assertEqual(report["ranglisten_zusatzquellen"].get("ranglisten_insgesamt"), 1980)
        text = decoded(ursachen.annotations(report))
        self.assertIn("mit Zusatzquelle: CNBC 1", text)
        self.assertIn("CNBC: abgesichert 1 von 1", text)
        self.assertNotIn(otc_symbol, text)
        self.assertNotIn(name, text)
        # letzter Abschluss bei OTC Markets: nur noch Beobachtung („lastTradeTime“ nicht dokumentiert) – keine zweite Quelle, kein Vergleich
        alt[otc_symbol].update(barchart=False, otc_name=name, otc_last=(moved, own[moved]))
        report = ursachen.run(self.stand(), self.sid, FakeHttp(series, changes, nocp, {leader_symbol}, minute_changes=self.minute, alt=alt, otc={otc_symbol}), pause=self.fail_on_pause)
        days_c = report["zusatzquellen"]["tage"]
        self.assertEqual(days_c.get("zweite_quelle_keine"), 1, "OTC Markets zeigt am Tag den Kurs des Stands – zählt aber nicht als zweite Quelle")
        self.assertNotIn("zweite_quelle_otc_letzter_gleich_stand", days_c)
        self.assertEqual(days_c.get("otc_kursmeldung_mit_kursmeldung"), 1)
        seen = report["zusatzquellen"]["otc_lasttradetime"]
        self.assertEqual(seen.get("zeitstempel_andere_uhrzeit"), 1, "20:00 Uhr UTC – kein Stempel auf Mitternacht")
        self.assertEqual(seen.get("stunde_utc_20"), 1)
        self.assertIn("lastSale", " ".join(report["zusatzquellen"]["felder"]))
        text = decoded(ursachen.annotations(report))
        self.assertIn("Die Zuordnung bleibt offen, der letzte Abschluss bei OTC Markets ist weder Vergleichskurs noch zweite Quelle", text)
        self.assertIn("Genau auf 00:00:00.000 Uhr UTC liegen 0 von 1 Zeitstempeln", text)
        self.assertNotIn("Abfrage minus Zeitstempel", text, "„quoteTime“ ist ein Feld der Antwort, nicht der Zeitpunkt der Abfrage")
        # Zeitstempel genau auf 00:00 Uhr UTC des Tags nach dem Kursstand: als UTC-Datum kein Kurstag des Stands, nach Ortszeit New York der
        # letzte Kurstag – beobachtet und gezählt, aber nicht als Handelstag verwendet
        cutoff = int(self.stand().get("manifest.bin")["cutoff_day"])
        last_own = max(own)
        alt[otc_symbol].update(otc_last=(last_own + 1, own[last_own]), otc_midnight=True)
        report = ursachen.run(self.stand(), self.sid, FakeHttp(series, changes, nocp, {leader_symbol}, minute_changes=self.minute, alt=alt, otc={otc_symbol}), pause=self.fail_on_pause)
        seen = report["zusatzquellen"]["otc_lasttradetime"]
        self.assertEqual(seen.get("zeitstempel_exakt_0_uhr_utc"), 1)
        self.assertEqual((seen.get("minute_utc_00"), seen.get("sekunde_utc_00"), seen.get("bruchteil_der_sekunde_ohne")), (1, 1, 1))
        self.assertTrue(any(k.startswith("abruf_minus_stempel_") for k in seen), "Abstand zum Abruf nach der Uhr des Prüfrechners")
        self.assertFalse(any(k.startswith("abfrage_minus_stempel_") for k in seen), seen)
        self.assertIn("Alle 1 Zeitstempel liegen genau auf 00:00:00.000 Uhr UTC", decoded(ursachen.annotations(report)))
        self.assertEqual(seen.get("ny_lage_letzter_kurstag_des_stands"), 1)
        self.assertTrue(any(k.startswith("utc_lage_kein_kurstag_des_stands") for k in seen), seen)
        self.assertEqual(seen.get("lastsale_gleich_letztem_kurs_des_stands_ja"), 1)
        self.assertLessEqual(last_own, cutoff)
        alt[otc_symbol].update(otc_last=(moved, 0), otc_midnight=False)  # Kursmeldung ohne Abschluss (lastSale 0)
        report = ursachen.run(self.stand(), self.sid, FakeHttp(series, changes, nocp, {leader_symbol}, minute_changes=self.minute, alt=alt, otc={otc_symbol}), pause=self.fail_on_pause)
        self.assertEqual(report["zusatzquellen"]["tage"].get("otc_kursmeldung_kursmeldung_ohne_abschluss"), 1)
        alt[otc_symbol].pop("otc_last")
        alt[otc_symbol].pop("otc_name")
        # anderer Name bei CNBC: Identität nicht bestätigt – Barchart (nur Kürzel und Kursniveau) ist nicht abgesichert: kein Vergleich,
        # die Aktie zählt als „nicht abgesichert“ (Kurse vorhanden, nicht geprüft)
        alt[otc_symbol]["name"] = "Völlig Andere Gesellschaft"
        alt[otc_symbol]["barchart"] = True
        report = ursachen.run(self.stand(), self.sid, FakeHttp(series, changes, nocp, {leader_symbol}, minute_changes=self.minute, alt=alt, otc={otc_symbol}), pause=self.fail_on_pause)
        self.assertEqual(report["zusatzquellen"]["je_quelle"], {})
        self.assertEqual(report["zusatzquellen"]["pruefungen"].get("cnbc_identitaet_name_passt_nicht"), 1)
        self.assertEqual((report["nicht_abgesichert"], report["ohne_vergleichskurse"]), (1, 0))
        self.assertEqual(report["urteil"], "unvollstaendig")
        # Kursniveau um einen Faktor anders (anderes Verhältnis ADR/Aktie): keine Quelle abgesichert → nicht abgesichert
        alt[otc_symbol] = {"name": name, "closes": {d: round(c * 10, 4) for d, c in own.items()}, "cnbc": True, "barchart": True}
        report = ursachen.run(self.stand(), self.sid, FakeHttp(series, changes, nocp, {leader_symbol}, minute_changes=self.minute, alt=alt, otc={otc_symbol}), pause=self.fail_on_pause)
        self.assertEqual(report["zusatzquellen"]["verglichen"], 0)
        self.assertEqual(report["nicht_abgesichert"], 1)
        self.assertEqual(report["zusatzquellen"]["pruefungen"].get("cnbc_kursniveau_faktor"), 1)
        self.assertEqual(report["absicherung"].get("cnbc_grund_kursniveau"), 1)
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
