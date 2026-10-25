"""Absicherung der Zuordnung eines Vergleichskurses (seit dem 25.10.2026, ``tests/live/kurse_absicherung.py``) und Vergleichskurse
außerhalb der US-Auswahl (``tests/live/kurse_welt.py``) – SYNTHETISCHE Antworten; der echte Abruf läuft im Workflow „App mit echten
Daten prüfen“ (Option „Ursachen“).

Simons Auftrag vom 25.10.2026, 09:20 Uhr, Punkt 3: „Ein passendes Kürzel oder ähnliches Kursniveau allein reicht nicht. Fehlende Angaben
dürfen nicht automatisch als bestandene Prüfung gelten.“ Jeder Test prüft deshalb auch die Fälle, in denen eine Angabe fehlt."""

from __future__ import annotations

import datetime as dt
import importlib.util
import sys
import types
import unittest
from pathlib import Path

LIVE = Path(__file__).resolve().parents[1] / "live"
sys.path.insert(0, str(LIVE))
sys.path.insert(0, str(LIVE.parents[1] / "backend"))


def load(name: str):
    spec = importlib.util.spec_from_file_location(name, LIVE / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


absicherung = load("kurse_absicherung")
welt = load("kurse_welt")
zusatz = load("kurse_zusatzquellen")


def day(text: str) -> int:
    return (dt.date.fromisoformat(text) - dt.date(1970, 1, 1)).days


LISTING = (
    "Nasdaq Traded|Symbol|Security Name|Listing Exchange|Market Category|ETF|Round Lot Size|Test Issue|Financial Status|CQS Symbol|NASDAQ Symbol|NextShares\n"
    "Y|AAPL|Apple Inc. - Common Stock|Q|Q|N|100|N|N||AAPL|N\n"
    "Y|BRK.B|Berkshire Hathaway Inc. Class B Common Stock|N| |N|100|N||BRK.B|BRK/B|N\n"
    "Y|KO|Coca-Cola Company (The) Common Stock|N| |N|100|N||KO|KO|N\n"
    "Y|SPY|SPDR S&P 500 ETF Trust|P| |Y|100|N||SPY|SPY|N\n"
    "Y|ZXZZT|NASDAQ TEST STOCK|Q|G|N|100|Y|N||ZXZZT|N\n"
    "Y|ABCDW|Beispiel Corp. - Warrants|Q|S|N|100|N|N||ABCDW|N\n"
    "File Creation Time: 1025202606:00|||||||||||\n"
)


def figi(symbol: str, key: str = "US", status: str = "ok") -> dict:
    return {"status": status, "kandidaten": [{"boerse": key, "symbol": symbol, "code": "US", "typ": "Common Stock", "typ2": "Common Stock"}] if status == "ok" else []}


class Names(unittest.TestCase):
    def test_issuer_name_without_the_security_description(self):
        self.assertEqual(absicherung.issuer_name("Apple Inc. - Common Stock"), "Apple Inc.")
        self.assertEqual(absicherung.issuer_name("Alphabet Inc. - Class A Common Stock"), "Alphabet Inc.")
        self.assertEqual(absicherung.issuer_name("Berkshire Hathaway Inc. Class B Common Stock"), "Berkshire Hathaway Inc.")
        self.assertEqual(absicherung.issuer_name("Coca-Cola Company (The) Common Stock"), "Coca-Cola Company (The)")
        self.assertEqual(absicherung.issuer_name("Taiwan Semiconductor Manufacturing Company Ltd. American Depositary Shares"), "Taiwan Semiconductor Manufacturing Company Ltd.")
        self.assertEqual(absicherung.issuer_name("ADS-TEC Energy PLC - Ordinary Shares"), "ADS-TEC Energy PLC", "„ADS“ am Anfang ist Teil des Namens")
        self.assertEqual(absicherung.issuer_name("Apple Inc."), "Apple Inc.")

    def test_name_check_needs_a_name_and_a_match(self):
        self.assertEqual(absicherung.name_check("Apple Inc. - Common Stock", ["Apple Inc.", "Apple"]), "bestaetigt")
        self.assertEqual(absicherung.name_check("Coca-Cola Company (The) Common Stock", ["The Coca-Cola Company"]), "bestaetigt")
        self.assertEqual(absicherung.name_check("Completely Other Holdings Inc.", ["Apple Inc."]), "passt_nicht")
        self.assertEqual(absicherung.name_check(None, ["Apple Inc."]), "nicht_angegeben", "fehlender Name ist nicht bestanden")
        self.assertEqual(absicherung.name_check("", ["Apple Inc."]), "nicht_angegeben")

    def test_not_equity_by_whole_words(self):
        self.assertTrue(absicherung.not_equity("Beispiel Corp. Warrants"))
        self.assertTrue(absicherung.not_equity("Beispiel Corp. - Warrants"))
        self.assertTrue(absicherung.not_equity("Beispiel Acquisition Corp. Units"), "Einheit einer SPAC")
        self.assertTrue(absicherung.not_equity("Some Income Fund"))
        self.assertFalse(absicherung.not_equity("United Rentals, Inc."), "„United“ ist kein „Unit“")
        self.assertFalse(absicherung.not_equity("Fundamental Global Inc."), "„Fundamental“ ist kein „Fund“")
        self.assertFalse(absicherung.not_equity("Enterprise Products Partners L.P. Common Units"), "Anteile einer Kommanditgesellschaft")
        self.assertFalse(absicherung.not_equity("Rights Holding Co. Common Stock"), "„Rights“ im Namen des Emittenten")
        self.assertEqual(absicherung.issuer_name("Alphabet Inc. Class C Capital Stock"), "Alphabet Inc.")


class Listing(unittest.TestCase):
    def test_listing_with_every_spelling_of_the_class(self):
        rows = absicherung.parse_listing(LISTING)
        self.assertEqual(rows["AAPL"], {"name": "Apple Inc. - Common Stock", "boerse": "nasdaq", "fonds": False, "test": False})
        self.assertEqual(rows["BRK-B"]["boerse"], "nyse", "BRK.B und BRK/B → BRK-B")
        self.assertTrue(rows["SPY"]["fonds"])
        self.assertTrue(rows["ZXZZT"]["test"])
        self.assertNotIn("FILE CREATION TIME: 1025202606:00", rows)
        self.assertEqual(absicherung.parse_listing("kein Inhalt"), {})

    def test_listing_falls_back_to_the_stock_screener(self):
        class Http:
            def __init__(self, trader_ok: bool, screener_ok: bool):
                self.trader_ok, self.screener_ok, self.calls = trader_ok, screener_ok, []

            def get(self, url, headers=None):
                self.calls.append(url)
                if "nasdaqtrader" in url:
                    if self.trader_ok:
                        return types.SimpleNamespace(status_code=200, content=LISTING.encode("utf-8"))
                    return types.SimpleNamespace(status_code=403, content=b"")
                if "screener" in url and self.screener_ok:
                    exchange = url.split("exchange=")[1].split("&")[0]
                    rows = {"nasdaq": [{"symbol": "AAPL", "name": "Apple Inc. Common Stock"}], "nyse": [{"symbol": "KO", "name": "Coca-Cola Company (The) Common Stock"}], "amex": []}[exchange]
                    return types.SimpleNamespace(status_code=200, json=lambda: {"data": {"rows": rows}})
                return types.SimpleNamespace(status_code=403, json=lambda: None)

        status, rows = absicherung.fetch_listing(Http(True, False))
        self.assertEqual((status, len(rows) > 5), ("ok", True))
        status, rows = absicherung.fetch_listing(Http(False, True))
        self.assertEqual(status, "ok_ersatz")
        self.assertEqual((rows["AAPL"]["boerse"], rows["KO"]["boerse"]), ("nasdaq", "nyse"))
        status, rows = absicherung.fetch_listing(Http(False, False))
        self.assertEqual((status, rows), ("http_403", {}), "ohne Liste: Fehlerstatus, nichts gilt als bestanden")


class Identity(unittest.TestCase):
    def test_symbol_must_belong_to_the_isin(self):
        self.assertEqual(absicherung.figi_identity(figi("BRK-B"), "BRK.B", "US"), "isin_kuerzel_bestaetigt")
        self.assertEqual(absicherung.figi_identity(figi("BRK-A"), "BRK-B", "US"), "isin_anderes_kuerzel", "andere Gattung, anderes Kürzel")
        self.assertEqual(absicherung.figi_identity(figi("SAP", "XETR"), "SAP", "US"), "isin_ohne_notierung_der_boerse")
        self.assertEqual(absicherung.figi_identity(figi("ABCDF", "OTC"), "ABCDF", "US"), "isin_kuerzel_bestaetigt", "US und OTC sind eine Gruppe")
        self.assertEqual(absicherung.figi_identity(None, "AAPL", "US"), "nicht_geprueft")
        self.assertEqual(absicherung.figi_identity({"status": "fehler_ProviderError", "kandidaten": []}, "AAPL", "US"), "nicht_geprueft")
        self.assertEqual(absicherung.figi_identity({"status": "keine_zuordnung", "kandidaten": []}, "AAPL", "US"), "isin_ohne_zuordnung")
        self.assertEqual(absicherung.figi_identity({"status": "isin_unbekannt", "kandidaten": []}, "AAPL", "US"), "isin_unbekannt")

    def test_nordic_class_share_in_the_documented_spelling_of_the_app(self):
        """Lauf 40181869022: OpenFIGI nennt „ADDTB“ (Yahoo-Schreibweise der App „ADDTB.ST“), der Stand rechnet mit „ADDT-B.ST“ – die
        dokumentierte andere Schreibweise der App (``ExchangeTable.symbol_variants``). Bis dahin galt das als anderes Kürzel; vier
        Stockholmer Aktien waren dadurch nicht abgesichert. Eine andere Gattung bleibt ein anderes Kürzel."""
        out = absicherung.figi_lookup(["SE0000000001"], client=types.SimpleNamespace(map_isins=lambda isins: {
            isins[0]: {"data": [{"exchCode": "SS", "ticker": "ADDTB", "marketSector": "Equity", "securityType": "Common Stock"}]}}))
        entry = out["SE0000000001"]
        self.assertEqual(entry["status"], "ok")
        self.assertEqual((entry["kandidaten"][0]["boerse"], entry["kandidaten"][0]["symbol"], entry["kandidaten"][0]["varianten"]), ("XSTO", "ADDTB.ST", ["ADDT-B.ST"]))
        self.assertEqual(absicherung.figi_identity(entry, "ADDT-B.ST", "XSTO"), "isin_kuerzel_bestaetigt_schreibweise")
        self.assertEqual(absicherung.figi_identity(entry, "ADDTB.ST", "XSTO"), "isin_kuerzel_bestaetigt")
        self.assertEqual(absicherung.figi_identity(entry, "ADDT-A.ST", "XSTO"), "isin_anderes_kuerzel", "Gattung A ist eine andere Aktie")
        self.assertIn("isin_kuerzel_bestaetigt_schreibweise", absicherung.CONFIRMED)

    def test_unknown_isin_at_openfigi_is_named(self):
        client = types.SimpleNamespace(map_isins=lambda isins: {isins[0]: {"warning": "No identifier found."}, isins[1]: {"data": [{"exchCode": "ZZ", "ticker": "X"}]}})
        out = absicherung.figi_lookup(["US0000000001", "US0000000002"], client=client)
        self.assertEqual((out["US0000000001"]["status"], out["US0000000002"]["status"]), ("isin_unbekannt", "keine_zuordnung"))
        self.assertEqual(absicherung.figi_identity(out["US0000000001"], "AAA", "US"), "isin_unbekannt")
        self.assertNotIn("isin_unbekannt", absicherung.CONFIRMED)

    def test_figi_lookup_without_answer_is_never_passed(self):
        class Client:
            def map_isins(self, isins):
                raise RuntimeError("kein Netz")

        out = absicherung.figi_lookup(["US0378331005"], client=Client())
        self.assertEqual(out["US0378331005"]["status"], "fehler_RuntimeError")
        self.assertEqual(absicherung.figi_identity(out["US0378331005"], "AAPL", "US"), "nicht_geprueft")

    def test_a_failed_block_only_affects_its_own_isins(self):
        class Client:
            def __init__(self):
                self.calls = 0

            def map_isins(self, isins):
                self.calls += 1
                if self.calls == 1:
                    raise RuntimeError("Grenze erreicht")
                return {isin: {"data": [{"exchCode": "US", "ticker": "AAA", "marketSector": "Equity", "securityType": "Common Stock"}]} for isin in isins}

        isins = [f"US{k:010d}" for k in range(absicherung.FIGI_CHUNK + 5)]
        out = absicherung.figi_lookup(isins, client=Client())
        self.assertEqual(sum(1 for x in out.values() if x["status"] == "fehler_RuntimeError"), absicherung.FIGI_CHUNK)
        self.assertEqual(sum(1 for x in out.values() if x["status"] == "ok"), 5)
        self.assertEqual(out[isins[-1]]["kandidaten"][0]["boerse"], "US")


class SecureNasdaq(unittest.TestCase):
    D = [day("2026-09-01") + k for k in range(30) if (dt.date(2026, 9, 1) + dt.timedelta(days=k)).weekday() < 5]

    def setUp(self):
        self.own = {d: 100.0 + k for k, d in enumerate(self.D)}
        self.rows = {d: {"close": v} for d, v in self.own.items()}
        self.listing = absicherung.parse_listing(LISTING)
        self.meta = {"isin": "US0378331005", "namen": ["Apple Inc."], "waehrung": "USD", "einheit": "USD", "boerse": "US"}
        self.yahoo = {"exchange": "NMS", "currency": "USD", "days": {}, "splits": []}

    def secure(self, **kw):
        args = dict(listing=self.listing, listing_status="ok", figi=figi("AAPL"), symbol="AAPL", meta=self.meta, yahoo=self.yahoo, own=self.own, rows=self.rows, dollar=True,
                    cutoff=self.D[-1])
        args.update(kw)
        return absicherung.secure_nasdaq(**args)

    def test_every_check_passes(self):
        checks = self.secure()
        self.assertTrue(checks["abgesichert"], checks)
        self.assertEqual(checks["grund"], "")
        self.assertTrue(self.secure(official=True)["abgesichert"], "NOCP einer Nasdaq-notierten Aktie")

    def test_missing_information_is_never_passed(self):
        self.assertEqual(self.secure(dollar=False)["grund"], "waehrung", "ohne angegebene Währung")
        self.assertEqual(self.secure(listing_status="http_403", listing={})["grund"], "name,art,handelsplatz")
        self.assertEqual(self.secure(symbol="MSFT", figi=figi("MSFT"))["grund"], "name,art,handelsplatz", "nicht in der Wertpapierliste")
        self.assertEqual(self.secure(figi=None)["grund"], "aktie", "ohne OpenFIGI: Aktie nicht geprüft")
        self.assertEqual(self.secure(yahoo={**self.yahoo, "exchange": None})["grund"], "handelsplatz")
        few = {d: v for d, v in list(self.own.items())[:5]}
        self.assertIn("tage", self.secure(own=few)["grund"])

    def test_venue_currency_day_and_level(self):
        self.assertEqual(self.secure(yahoo={**self.yahoo, "exchange": "NYQ"})["grund"], "handelsplatz", "Nasdaq laut Liste, NYSE laut Yahoo")
        nyse = self.secure(symbol="KO", figi=figi("KO"), meta={**self.meta, "namen": ["The Coca-Cola Company"]}, yahoo={**self.yahoo, "exchange": "NYQ"}, official=True)
        self.assertEqual((nyse["handelsplatz"], nyse["abgesichert"]), ("nocp_nur_fuer_nasdaq", False))
        self.assertEqual(self.secure(meta={**self.meta, "waehrung": "EUR", "einheit": "EUR"})["waehrung"], "anders")
        shifted = {d: {"close": self.own[self.D[k + 1]]} for k, d in enumerate(self.D[:-1])}
        self.assertTrue(self.secure(rows=shifted)["handelstag"].startswith("versatz_"), "Kurs des Folgetags unter dem Tag")
        self.assertFalse(self.secure(rows=shifted)["abgesichert"])
        self.assertFalse(self.secure(rows={d: {"close": v * 1.1} for d, v in self.own.items()})["abgesichert"])
        spy = self.secure(symbol="SPY", figi=figi("SPY"), meta={**self.meta, "namen": ["SPDR S&P 500 ETF Trust"]}, yahoo={**self.yahoo, "exchange": "PCX"})
        self.assertEqual((spy["art"], spy["art_grund"]), ("kein_aktieninstrument", "fonds_laut_liste"))
        warrant = self.secure(symbol="ABCDW", figi=figi("ABCDW"), meta={**self.meta, "namen": ["Beispiel Corp."]})
        self.assertEqual((warrant["art"], warrant["art_grund"]), ("kein_aktieninstrument", "beschreibung_im_namen"))
        test_issue = self.secure(symbol="ZXZZT", figi=figi("ZXZZT"), meta={**self.meta, "namen": ["Nasdaq Test Stock"]})
        self.assertEqual(test_issue["art_grund"], "testwert_laut_liste")
        self.assertNotIn("art_grund", self.secure())
        counts = absicherung.summary([spy, warrant, test_issue])
        self.assertEqual((counts["nasdaq_artgrund_fonds_laut_liste"], counts["nasdaq_artgrund_beschreibung_im_namen"], counts["nasdaq_artgrund_testwert_laut_liste"]), (1, 1, 1))

    def test_the_name_check_is_labelled_as_a_required_check(self):
        """Lauf 40181869022: beschriftet war die Namensprüfung als „nur Hinweis“, gezählt aber als Pflicht – jetzt stimmt die Beschriftung."""
        self.assertNotIn("Hinweis", absicherung.CHECK_TEXT["name"])
        checks = self.secure(meta={**self.meta, "namen": ["Völlig Andere Gesellschaft"]})
        self.assertEqual((checks["name"], checks["abgesichert"], checks["grund"]), ("passt_nicht", False, "name"))

    def test_a_factor_needs_a_reported_split(self):
        split_day = self.D[15]
        raw = {d: {"close": v * 2 if d < split_day else v} for d, v in self.own.items()}  # Quelle unbereinigt vor einem Split 2:1
        checks = self.secure(rows=raw)
        self.assertEqual((checks["bereinigung"], checks["abgesichert"]), ("faktor_ohne_split", False))
        checks = self.secure(rows=raw, yahoo={**self.yahoo, "splits": [(split_day, 2.0)]})
        self.assertEqual((checks["bereinigung"], checks["kursniveau"], checks["abgesichert"]), ("split_gemeldet", "passt", True))
        self.assertEqual(absicherung.level_check(self.own, raw), "passt_nicht", "ohne Split: halbe Tage um den Faktor 2 daneben")

    def test_dividend_adjusted_source_is_not_secured(self):
        days_y = {d: {"close": v, "adjclose": v * 0.98} for d, v in self.own.items()}
        rows = {d: {"close": v * 0.98} for d, v in self.own.items()}
        checks = self.secure(rows=rows, yahoo={**self.yahoo, "days": days_y})
        self.assertEqual(checks["bereinigung"], "dividendenbereinigt")
        self.assertFalse(checks["abgesichert"])

    def test_summary_counts_without_names(self):
        counts = absicherung.summary([self.secure(), self.secure(dollar=False)])
        self.assertEqual((counts["nasdaq_abgesichert"], counts["nasdaq_nicht_abgesichert"], counts["nasdaq_grund_waehrung"]), (1, 1, 1))
        self.assertFalse([k for k in counts if "AAPL" in k or "Apple" in k])


class StrictSource(unittest.TestCase):
    def setUp(self):
        self.days = [day("2026-09-01") + k for k in range(20)]
        self.own = {d: 5.0 + 0.01 * k for k, d in enumerate(self.days)}
        self.yahoo = {"exchange": "PNK", "currency": "USD", "days": {}, "splits": []}
        self.stand = {"isin": "US1234567890", "namen": ["Beispiel AG"], "waehrung": "USD", "einheit": "USD", "boerse": "US"}

    def strict(self, meta: dict, rows=None, symbol="ABCDF", figi_entry=None):
        fetched = {"quelle": "cnbc", "status": {"profil": "ok", "historie": "ok"}, "rows": rows or {d: {"close": v, "volume": 10.0} for d, v in self.own.items()}, "meta": meta}
        result = zusatz.check(fetched, self.own, self.stand, self.yahoo)
        return absicherung.strict_source(result, fetched, self.own, self.yahoo, figi_entry if figi_entry is not None else figi(symbol, "OTC"), symbol, "US", self.days[-1])

    def test_named_source_on_the_same_venue_in_the_same_currency_passes(self):
        checks = self.strict({"name": "Beispiel AG", "boerse": "Pink Sheets", "waehrung": "USD"})
        self.assertTrue(checks["abgesichert"], checks)

    def test_symbol_alone_or_a_similar_name_is_not_enough(self):
        self.assertEqual(self.strict({})["grund"], "name,art,handelsplatz,waehrung", "„nur Kürzel“ (Barchart u. a.)")
        similar = self.strict({"name": "Beispiel Pharma Systems", "boerse": "Pink Sheets", "waehrung": "USD"})
        self.assertEqual((similar["name"], similar["grund"]), ("nur_aehnlich", "name"), "ähnlicher Name (Ähnlichkeit 0,3–0,5) reicht nicht")
        self.assertEqual(self.strict({"name": "Beispiel AG", "boerse": "Pink Sheets"})["grund"], "waehrung", "Währung nicht angegeben")
        self.assertEqual(self.strict({"name": "Beispiel AG", "waehrung": "USD"})["grund"], "handelsplatz", "Börse nicht angegeben")
        self.assertEqual(self.strict({"name": "Beispiel AG", "boerse": "NYSE", "waehrung": "USD"})["grund"], "handelsplatz", "Börse statt OTC")
        self.assertEqual(self.strict({"name": "Beispiel AG", "boerse": "Pink Sheets", "waehrung": "USD"}, figi_entry={"status": "keine_zuordnung", "kandidaten": []})["grund"], "aktie")

    def test_isin_of_the_source_confirms_the_stock(self):
        checks = self.strict({"name": "Beispiel AG", "boerse": "Pink Sheets", "waehrung": "USD", "isin": "US1234567890"}, figi_entry={"status": "keine_zuordnung", "kandidaten": []})
        self.assertTrue(checks["abgesichert"])
        self.assertEqual(self.strict({"name": "Beispiel AG", "boerse": "Pink Sheets", "waehrung": "USD", "isin": "US0000000000"})["aktie"], "isin_anders")

    def test_shifted_days_are_not_secured(self):
        rows = {d + 1: {"close": v, "volume": 10.0} for d, v in self.own.items()}
        checks = self.strict({"name": "Beispiel AG", "boerse": "Pink Sheets", "waehrung": "USD"}, rows=rows)
        self.assertEqual(checks["handelstag"], "versatz_+1")
        self.assertFalse(checks["abgesichert"])


class World(unittest.TestCase):
    def test_cnbc_symbols_per_exchange(self):
        self.assertEqual(welt.cnbc_candidates("SAP.DE", "XETR"), ["SAP-DE"])
        self.assertEqual(welt.cnbc_candidates("VOLV-B.ST", "XSTO"), ["VOLV.B-SE", "VOLVB-SE"])
        self.assertEqual(welt.cnbc_candidates("0700.HK", "XHKG"), ["0700-HK", "700-HK"])
        self.assertEqual(welt.cnbc_candidates("BP.L", "XLON"), ["BP.-GB", "BP-GB"])
        self.assertEqual(welt.cnbc_candidates("ABCDF", "OTC"), ["ABCDF"])
        self.assertEqual(welt.cnbc_candidates("XYZ.ZZ", "XZZZ"), [], "Börse ohne Regel: kein geratenes Kürzel")

    def test_venue_words_and_exclusions(self):
        self.assertEqual(welt.venue_check("XETRA", "XETR"), "gleich")
        self.assertEqual(welt.venue_check("Frankfurt", "XETR"), "anders")
        self.assertEqual(welt.venue_check("Korea KOSDAQ", "XKRX"), "anders", "KOSDAQ ist nicht KOSPI")
        self.assertEqual(welt.venue_check("TSX Venture Exchange", "XTSE"), "anders")
        self.assertEqual(welt.venue_check(None, "XETR"), "nicht_angegeben")
        self.assertEqual(welt.venue_check("Somewhere", "XZZZ"), "nicht_zuordenbar")

    def test_currency_units_are_converted(self):
        self.assertEqual(welt.unit_factor("GBP", "GBP", "GBp"), ("gleich", 100.0), "Pfund → Pence")
        self.assertEqual(welt.unit_factor("GBp", "GBP", "GBp"), ("gleich", 1.0))
        self.assertEqual(welt.unit_factor("GBX", "GBP", "GBp"), ("gleich", 1.0), "GBX = Pence")
        self.assertEqual(welt.unit_factor("ZAR", "ZAR", "ZAc"), ("gleich", 100.0))
        self.assertEqual(welt.unit_factor("GBp", "GBP", "GBP"), ("gleich", 0.01), "Pence → Pfund")
        self.assertEqual(welt.unit_factor("EUR", "EUR", "EUR"), ("gleich", 1.0))
        self.assertEqual(welt.unit_factor("USD", "EUR", "EUR"), ("anders", 1.0))
        self.assertEqual(welt.unit_factor(None, "EUR", "EUR"), ("nicht_angegeben", 1.0), "fehlende Währung ist nicht bestanden")
        # die Kursmeldung behält die Schreibweise: „GBp“ (Pence) wird nicht zu „GBP“ (Pfund) – sonst Faktor 100 im Vergleich
        self.assertEqual(zusatz.find_meta({"name": "BP PLC", "currencyCode": "GBp"})["waehrung"], "GBp")

    def test_world_check_is_as_strict_as_for_us_stocks(self):
        days = [day("2026-09-01") + k for k in range(20)]
        own = {d: 1200.0 + k for k, d in enumerate(days)}  # Pence
        rows = {d: {"close": v / 100, "volume": 10.0} for d, v in own.items()}  # Pfund
        meta = {"isin": "GB0007980591", "namen": ["BP p.l.c."], "waehrung": "GBP", "einheit": "GBp", "boerse": "XLON"}
        source = {"name": "BP PLC", "boerse": "London Stock Exchange", "waehrung": "GBP"}
        checks, converted = welt.check_world(rows, source, own, meta, {"days": {}, "splits": []}, figi("BP-L", "XLON"), "BP.-GB", "BP.L", "XLON", days[-1])
        self.assertTrue(checks["abgesichert"], checks)
        self.assertAlmostEqual(converted[days[0]]["close"], own[days[0]])
        checks, _ = welt.check_world(rows, {**source, "waehrung": None}, own, meta, {"days": {}, "splits": []}, figi("BP-L", "XLON"), "BP.-GB", "BP.L", "XLON", days[-1])
        self.assertEqual((checks["waehrung"], checks["abgesichert"]), ("nicht_angegeben", False))
        checks, _ = welt.check_world(rows, {**source, "boerse": None}, own, meta, {"days": {}, "splits": []}, figi("BP-L", "XLON"), "BP.-GB", "BP.L", "XLON", days[-1])
        self.assertEqual((checks["handelsplatz"], checks["abgesichert"]), ("nicht_angegeben", False))


class Findings(unittest.TestCase):
    """Befund je nicht bestandener Prüfung (seit dem 25.10.2026, 11:45 Uhr; Auftrag Punkt 3: „Beschaffe ergänzende Belege“) – im
    Lauf 40184599190 stand bei einer Aktie mit 22 Plätzen 1 nur „nicht bestanden: Kursniveau“, bei drei Nasdaq-Aktien nur „Aktie
    und Gattung“. Jetzt mit Zahlen und Codes, ohne Namen, Kürzel oder ISIN."""

    def test_isin_check_digit(self):
        for isin in ("US0378331005", "DE0007164600", "GB0007980591", "CA0679011084", "KYG017191142"):
            self.assertTrue(absicherung.isin_valid(isin), isin)
        for isin in ("US0378331006", "US037833100", "0378331005US", "", None):
            self.assertFalse(absicherung.isin_valid(isin), isin)

    def test_openfigi_findings_name_codes_only(self):
        client = types.SimpleNamespace(map_isins=lambda isins: {
            isins[0]: {"warning": "No identifier found."},
            isins[1]: {"data": [{"exchCode": "QQ", "ticker": "TEVA", "marketSector": "Equity"}, {"exchCode": "ZZ", "ticker": "X", "marketSector": "Equity"}]},
            isins[2]: {"data": [{"exchCode": "LN", "ticker": "BP/", "marketSector": "Equity", "securityType": "Common Stock"}]},
            isins[3]: {"data": [{"exchCode": "IT", "ticker": "TEVA", "marketSector": "Equity"}]}})
        out = absicherung.figi_lookup(["US0378331005", "IL0006290147", "GB0007980591", "IL0006290148"], client=client)
        unknown = absicherung.figi_detail(out["US0378331005"], "XNAS")
        self.assertEqual(unknown, "ISIN bei OpenFIGI unbekannt (Prüfziffer der ISIN gültig, Land US)")
        other = absicherung.figi_detail(out["IL0006290147"], "XNAS")
        self.assertIn("nur mit Börsencodes QQ, ZZ (Sektor Equity) – keiner an einer Börse der App", other)
        elsewhere = absicherung.figi_detail(out["GB0007980591"], "XNAS")
        self.assertIn("nur an XLON, nicht an XNAS", elsewhere)
        tel_aviv = absicherung.figi_detail(out["IL0006290148"], "XNAS")
        self.assertEqual(tel_aviv, "OpenFIGI nennt die ISIN nur an XTAE, nicht an XNAS (Prüfziffer der ISIN ungültig, Land IL)")
        for text in (unknown, other, elsewhere, tel_aviv):
            self.assertNotIn("TEVA", text)
            self.assertNotIn("US0378331005", text)
        self.assertEqual(absicherung.figi_detail(None, "US"), "OpenFIGI ohne Antwort")

    def test_findings_per_failed_check(self):
        test = SecureNasdaq("test_every_check_passes")
        test.setUp()
        level = test.secure(rows={d: {"close": v / 1.05} for d, v in test.own.items()})
        self.assertEqual(level["grund"], "kursniveau")
        self.assertAlmostEqual(level["kursniveau_median"], 1.05, places=3)
        self.assertEqual(absicherung.failure_details(level), "Kursniveau Stand/Quelle im Median 1.050 (erlaubt 0.98 bis 1.02)")
        name = test.secure(meta={**test.meta, "namen": ["Völlig Andere Gesellschaft"]})
        self.assertRegex(absicherung.failure_details(name), r"^Ähnlichkeit des Namens 0\.\d\d \(verlangt mindestens 0\.5\)$")
        venue = test.secure(yahoo={**test.yahoo, "exchange": "NYQ"})
        self.assertEqual(absicherung.failure_details(venue), "Börse laut Quelle nasdaq, Kurse des Stands nyse")
        few = test.secure(own={d: v for d, v in list(test.own.items())[:5]})
        self.assertIn("5 gemeinsame Tage (verlangt mindestens 10)", absicherung.failure_details(few))
        entry = {"status": "isin_unbekannt", "kandidaten": [], "pruefziffer": "ungueltig", "land": "US"}
        figi_missing = test.secure(figi=entry)
        self.assertEqual(figi_missing["grund"], "aktie")
        self.assertEqual(absicherung.failure_details(figi_missing, entry, "US"), "ISIN bei OpenFIGI unbekannt (Prüfziffer der ISIN ungültig, Land US)")
        self.assertEqual(absicherung.failure_details(test.secure()), "", "abgesichert: kein Befund")

    def test_world_findings_venue_currency_and_level(self):
        days = [day("2026-09-01") + k for k in range(20)]
        own = {d: 0.30 for d in days}
        rows = {d: {"close": 0.25, "volume": 10.0} for d in days}
        meta = {"isin": "CA0679011084", "namen": ["Beispiel Mining Corp."], "waehrung": "CAD", "einheit": "CAD", "boerse": "XTSX"}
        source = {"name": "Beispiel Mining Corp", "boerse": "OTC Markets", "waehrung": "USD"}
        checks, _ = welt.check_world(rows, source, own, meta, {"days": {}, "splits": []}, figi("BMC-V", "XTSX"), "BMC-V", "BMC.V", "XTSX", days[-1])
        self.assertFalse(checks["abgesichert"])
        text = absicherung.failure_details(checks, figi("BMC-V", "XTSX"), "XTSX")
        self.assertIn("Börse laut Quelle OTC, Kurse des Stands XTSX", text)
        self.assertIn("Währung laut Quelle USD", text)
        self.assertIn("Kursniveau Stand/Quelle im Median 1.200", text)
        self.assertEqual(welt.venue_key("TSX Venture Exchange"), "XTSX", "„Venture“ ist nicht die TSX")
        self.assertEqual(welt.venue_key(None), "nicht_angegeben")
        self.assertEqual(welt.venue_key("Somewhere"), "nicht_zuordenbar")


if __name__ == "__main__":
    unittest.main()
