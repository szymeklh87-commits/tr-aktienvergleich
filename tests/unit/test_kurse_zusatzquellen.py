"""Weitere Vergleichsquellen für US-Aktien ohne Nasdaq-Kurse (seit dem 25.10.2026, ``tests/live/kurse_zusatzquellen.py``) –
SYNTHETISCHE Antworten; der echte Abruf läuft im Workflow „App mit echten Daten prüfen“ (Option „Ursachen“)."""

from __future__ import annotations

import datetime as dt
import importlib.util
import sys
import unittest
from pathlib import Path

LIVE = Path(__file__).resolve().parents[1] / "live"
sys.path.insert(0, str(LIVE))
SPEC = importlib.util.spec_from_file_location("kurse_zusatzquellen", LIVE / "kurse_zusatzquellen.py")
zusatz = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(zusatz)
SPEC_U = importlib.util.spec_from_file_location("kurse_ursachen_fuer_zusatz", LIVE / "kurse_ursachen.py")
ursachen = importlib.util.module_from_spec(SPEC_U)
SPEC_U.loader.exec_module(ursachen)


def day(text: str) -> int:
    return (dt.date.fromisoformat(text) - dt.date(1970, 1, 1)).days


class Dates(unittest.TestCase):
    def test_every_usual_date_format(self):
        d = day("2026-10-23")
        self.assertEqual(zusatz.day_of_value("10/23/2026"), d)
        self.assertEqual(zusatz.day_of_value("2026-10-23T00:00:00"), d)
        self.assertEqual(zusatz.day_of_value("20261023000000"), d)
        self.assertEqual(zusatz.day_of_value("20261023"), d)
        self.assertEqual(zusatz.day_of_value(d * 86400 + 4 * 3600), d, "Sekunden (00:00 Uhr New York)")
        self.assertEqual(zusatz.day_of_value((d * 86400 + 20 * 3600) * 1000), d, "Millisekunden (16:00 Uhr New York)")
        self.assertEqual(zusatz.day_of_value(str((d * 86400) * 1000)), d)
        for bad in (None, True, "", "N/A", "13/40/2026", 12345, "2026-13-01"):
            self.assertIsNone(zusatz.day_of_value(bad), bad)

    def test_position_of_a_day_the_stand_does_not_have(self):
        """Lauf 40160248028: Der letzte Abschluss bei OTC Markets lag bei 25 Aktien auf einem Tag, den der Stand nicht hat –
        seitdem zählt das Skript, wo dieser Tag liegt (ohne Datum und Kurs)."""
        cutoff, start = day("2026-10-23"), day("2026-06-01")
        self.assertEqual(zusatz.day_position(cutoff + 2, start, cutoff), "nach_dem_kursstand_2")
        self.assertEqual(zusatz.day_position(cutoff + 30, start, cutoff), "nach_dem_kursstand_mehr_als_7")
        self.assertEqual(zusatz.day_position(cutoff, start, cutoff), "am_kursstand")
        self.assertEqual(zusatz.day_position(cutoff - 5, start, cutoff), "im_zeitraum")
        self.assertEqual(zusatz.day_position(start - 1, start, cutoff), "vor_dem_zeitraum")


class Parsing(unittest.TestCase):
    def test_json_rows_without_fixed_field_names(self):
        """CNBC-ähnliche Tageskerzen und eine OTC-ähnliche Liste mit Zeitstempeln: jeweils die längste Liste mit Datum und
        Schlusskurs; „close“ hat Vorrang vor „lastPrice“; Feldnamen ohne Werte."""
        bars = {"barData": {"priceBars": [{"tradeTime": "20261022000000", "open": "1.0", "close": "1.10", "volume": "1,200"},
                                          {"tradeTime": "20261023000000", "open": "1.1", "close": "1.20", "volume": "0"}]},
                "other": [{"date": "10/23/2026", "price": "9"}]}
        rows, fields = zusatz.parse_json_rows(bars)
        self.assertEqual(rows, {day("2026-10-22"): {"close": 1.10, "volume": 1200.0}, day("2026-10-23"): {"close": 1.20, "volume": 0.0}})
        self.assertEqual(fields, ["tradeTime", "open", "close", "volume"])
        otc = {"records": [{"tradeDate": day("2026-10-23") * 86400000, "lastPrice": 5.0, "closingPrice": 5.1, "volume": 10}]}
        rows, _ = zusatz.parse_json_rows(otc)
        self.assertEqual(rows, {day("2026-10-23"): {"close": 5.1, "volume": 10.0}})
        self.assertEqual(zusatz.parse_json_rows({"data": None}), ({}, []))

    def test_csv_with_and_without_header(self):
        stooq = "Date,Open,High,Low,Close,Volume\n2026-10-22,1,1,1,1.5,100\n2026-10-23,1,1,1,1.6,0\n"
        rows, fields = zusatz.parse_csv_rows(stooq)
        self.assertEqual(rows, {day("2026-10-22"): {"close": 1.5, "volume": 100.0}, day("2026-10-23"): {"close": 1.6, "volume": 0.0}})
        self.assertEqual(fields, ["Date", "Open", "High", "Low", "Close", "Volume"])
        marketwatch = 'Date,Open,High,Low,Close,Volume\n10/23/2026,"1,001.00","1,010.00",990.00,"1,005.50","12,345"\n'
        self.assertEqual(zusatz.parse_csv_rows(marketwatch)[0], {day("2026-10-23"): {"close": 1005.5, "volume": 12345.0}})
        barchart = "XYZ,2026-10-22,1,1,1,2.25,500\nXYZ,2026-10-23,1,1,1,2.5,0\n"
        rows, _ = zusatz.parse_csv_rows(barchart)
        self.assertEqual(rows, {day("2026-10-22"): {"close": 2.25, "volume": 500.0}, day("2026-10-23"): {"close": 2.5, "volume": 0.0}})
        self.assertEqual(zusatz.parse_csv_rows("Bitte einen Schlüssel anfordern")[0], {})

    def test_meta_takes_the_highest_level_first(self):
        payload = {"name": "Beispiel AG", "currency": "usd", "securities": [{"name": "OTC Pink", "tierDisplayName": "Pink Current", "cusip": "123456789"}]}
        self.assertEqual(zusatz.find_meta(payload), {"name": "Beispiel AG", "waehrung": "USD", "boerse": "Pink Current", "cusip": "123456789"})
        quote = {"FormattedQuoteResult": {"FormattedQuote": [{"symbol": "X", "name": "Beispiel AG", "exchange": "Pink Sheets", "currencyCode": "USD", "ISIN": "US1234567890"}]}}
        self.assertEqual(zusatz.find_meta(quote), {"name": "Beispiel AG", "boerse": "Pink Sheets", "waehrung": "USD", "isin": "US1234567890"})


class Identity(unittest.TestCase):
    def test_strongest_evidence_first(self):
        names = ["Beispiel Aktiengesellschaft", "BEISPIEL AG"]
        self.assertEqual(zusatz.identity({"isin": "US1234567890"}, "US1234567890", names), "isin_bestaetigt")
        self.assertEqual(zusatz.identity({"isin": "US0000000000"}, "US1234567890", names), "isin_anders")
        self.assertEqual(zusatz.identity({"cusip": "123456789"}, "US1234567890", names), "cusip_bestaetigt")
        self.assertEqual(zusatz.identity({"cusip": "987654321"}, "US1234567890", names), "cusip_anders")
        self.assertEqual(zusatz.identity({"cusip": "123456789", "name": "Beispiel AG"}, "JP3633400001", names), "name_bestaetigt", "CUSIP passt nur zu US- und CA-ISIN")
        self.assertEqual(zusatz.identity({"name": "Ganz Anderes Unternehmen"}, "US1234567890", names), "name_passt_nicht")
        self.assertEqual(zusatz.identity({}, "US1234567890", names), "nur_kuerzel")

    def test_venue_of_source_and_stand(self):
        self.assertEqual(zusatz.venue_kind(None, "otc_markets"), "otc")
        self.assertEqual(zusatz.venue_kind("Pink Sheets", "cnbc"), "otc")
        self.assertEqual(zusatz.venue_kind("NYSE", "cnbc"), "boerse")
        self.assertEqual(zusatz.venue_kind(None, "barchart"), "nicht_angegeben")
        self.assertEqual(zusatz.stand_venue("PNK"), "otc")
        self.assertEqual(zusatz.stand_venue("NYQ"), "boerse")
        self.assertEqual(zusatz.stand_venue(None), "unbekannt")


class Checks(unittest.TestCase):
    def setUp(self) -> None:
        self.days = list(range(day("2026-07-01"), day("2026-07-01") + 30))
        self.own = {d: round(10.0 + 0.37 * k + 0.13 * (k % 7), 2) for k, d in enumerate(self.days)}  # unregelmäßig: kein Kurs gleicht dem Nachbartag
        self.stand = {"isin": "US1234567890", "namen": ["Beispiel AG"], "waehrung": "USD"}
        self.yahoo = {"exchange": "PNK", "currency": "USD", "days": {d: {"close": c, "volume": 100.0, "adjclose": c} for d, c in self.own.items()}}

    def fetched(self, rows: dict, meta: dict | None = None, source: str = "cnbc") -> dict:
        return {"quelle": source, "status": {"profil": "ok", "historie": "ok"}, "rows": {d: {"close": c, "volume": 100.0} for d, c in rows.items()}, "meta": meta or {}}

    def test_comparable_only_when_every_check_passes(self):
        result = zusatz.check(self.fetched(self.own, {"name": "Beispiel AG", "boerse": "Pink Sheets", "waehrung": "USD"}), self.own, self.stand, self.yahoo)
        self.assertTrue(result["vergleichbar"], result)
        self.assertEqual((result["identitaet"], result["handelsplatz"], result["waehrung"], result["kursniveau"], result["datum_versatz"]),
                         ("name_bestaetigt", "gleich", "gleich", "passt", 0))
        self.assertEqual(result["gleiche_tage"], 30)
        self.assertIn("Schlusskurs", result["definition"])

    def test_reasons_against_a_comparison(self):
        def reason(rows, meta=None, yahoo=None):
            return zusatz.check(self.fetched(rows, meta), self.own, self.stand, yahoo or self.yahoo)["grund"]

        self.assertEqual(reason({d: 10 * c for d, c in self.own.items()}), "kursniveau", "Faktor 10: anderes Verhältnis oder anders bereinigt")
        self.assertEqual(reason(self.own, {"name": "Ganz Anderes Unternehmen"}), "identitaet")
        self.assertEqual(reason(self.own, {"waehrung": "CAD"}), "waehrung")
        self.assertEqual(reason(self.own, {"boerse": "NYSE"}), "handelsplatz", "Quelle an einer Börse, Stand aus dem OTC-Handel")
        self.assertEqual(reason({d: c for d, c in list(self.own.items())[:5]}), "zu_wenige_tage")
        adjusted = dict(self.yahoo, days={d: {"close": c, "volume": 100.0, "adjclose": round(c * 0.99, 4)} for d, c in self.own.items()})
        self.assertEqual(reason({d: round(c * 0.99, 4) for d, c in self.own.items()}, yahoo=adjusted), "bereinigung", "Quelle dividendenbereinigt")
        empty = zusatz.check({"quelle": "stooq", "status": {"historie": "html_statt_daten"}, "rows": {}, "meta": {}}, self.own, self.stand, self.yahoo)
        self.assertEqual((empty["vergleichbar"], empty["grund"]), (False, "abruf_gescheitert"))
        none = zusatz.check({"quelle": "cnbc", "status": {"historie": "ok_ohne_kurse"}, "rows": {}, "meta": {}}, self.own, self.stand, self.yahoo)
        self.assertEqual(none["grund"], "keine_kurse")

    def test_dates_shifted_by_one_day_are_found(self):
        """Zeitstempel einer Quelle um Mitternacht UTC ergeben für New York den Vortag – der Versatz fällt auf und wird genutzt."""
        shifted = {d + 1: c for d, c in self.own.items()}
        result = zusatz.check(self.fetched(shifted, {"name": "Beispiel AG"}), self.own, self.stand, self.yahoo)
        self.assertEqual(result["datum_versatz"], 1)
        self.assertTrue(result["vergleichbar"])

    def test_compare_names_evidence_only(self):
        rows = {d: {"close": c, "volume": 100.0} for d, c in self.own.items()}
        d0, d1, d2 = self.days[10], self.days[11], self.days[12]
        rows[d0] = {"close": round(self.own[d0] + 0.004, 4), "volume": 100.0}  # unter einer Kursstufe? nein: 0,4 Cent auf einem Cent-Kurs
        rows[d1] = {"close": self.own[d1] * 1.05, "volume": 100.0}
        rows[d2] = {"close": rows[self.days[11]]["close"], "volume": 0.0}  # kein Umsatz, Kurs des Vortags der Quelle
        own = dict(self.own)
        own[self.days[13]] = 11.3462  # Stand zwischen zwei Kursstufen (mehr als eine halbe Stufe von der Quelle)
        rows[self.days[13]] = {"close": 11.34, "volume": 100.0}
        result = zusatz.compare(own, rows, 0, self.yahoo, ursachen.within_display)
        self.assertEqual(result[self.days[0]], ("gleich", self.own[self.days[0]], ""))
        self.assertEqual(result[d1][2], "ungeklaert")
        self.assertEqual(result[d2][2], "kein_handel")
        self.assertEqual(result[self.days[13]][2], "rundung")

    def test_rounding_to_the_precision_of_the_source(self):
        """Lauf 40158331688: CNBC wich bei Aktien unter 1 $ an vielen Tagen um Bruchteile eines Zehntelcents ab. Zeigt eine
        Quelle alle Kurse nur mit drei Nachkommastellen und ergibt der Kurs des Stands, so gerundet, ihren Kurs, ist das
        Rundung der Quelle (belegt) – eine Abweichung um mehr als eine halbe Stufe der Quelle bleibt ohne Beleg."""
        self.assertEqual(zusatz.source_unit([0.412, 0.405, 0.398]), 0.001)
        self.assertEqual(zusatz.source_unit([12.34, 12.5, 13.0]), 0.01)
        self.assertEqual(zusatz.source_unit([0.4123, 0.405]), 0.0001)
        self.assertIsNone(zusatz.source_unit([]))
        own = {self.days[k]: v for k, v in enumerate([0.4123, 0.4051, 0.3984, 0.4012, 0.4100])}
        rows = {self.days[k]: {"close": v, "volume": 100.0} for k, v in enumerate([0.412, 0.405, 0.398, 0.403, 0.410])}
        result = zusatz.compare(own, rows, 0, {"days": {}}, ursachen.within_display)
        self.assertEqual([result[d][2] for d in sorted(result)], ["rundung", "rundung", "rundung", "ungeklaert", ""], "0,4012 gegen 0,403: mehr als eine halbe Stufe")

    def test_several_history_addresses_the_first_with_prices_counts(self):
        class Http:
            def __init__(self):
                self.calls = []

            def get(self, url, headers=None):
                self.calls.append(url)
                import types
                if "/trade/history/" in url:
                    body = b'{"records": [{"tradeDate": "10/23/2026", "closingPrice": 5.1, "volume": 3}]}'
                    return types.SimpleNamespace(status_code=200, content=body)
                if "/trade/inside/" in url:
                    return types.SimpleNamespace(status_code=200, content=b'{"lastSale": 5.1, "lastTradeTime": 1792785600000, "tickerSymbol": "X"}')
                if "/company/profile/" in url:
                    return types.SimpleNamespace(status_code=200, content=b'{"name": "Beispiel AG"}')
                return types.SimpleNamespace(status_code=404, content=b"")

        http = Http()
        fetched = zusatz.fetch_source(http, "otc_markets", "XYZ", day("2026-06-01"), day("2026-10-23"))
        self.assertEqual(fetched["status"], {"profil": "ok", "kurs": "ok", "historie": "http_404", "historie_2": "ok"})
        self.assertFalse(any("/trade/chart/" in url for url in http.calls), "nach der ersten Kurshistorie keine weitere Adresse")
        self.assertEqual(fetched["rows"], {day("2026-10-23"): {"close": 5.1, "volume": 3.0}})
        self.assertEqual(fetched["felder_kurs"], ["lastSale", "lastTradeTime", "tickerSymbol"])
        self.assertEqual(fetched["letzter"], (day("2026-10-23"), 5.1))
        self.assertEqual(fetched["meta"]["name"], "Beispiel AG")

    def test_last_trade_of_the_otc_quote_uses_the_time_of_the_trade(self):
        """Lauf 40159274087: Die Kursmeldung von OTC Markets nennt auch den Zeitpunkt der Abfrage („insideTime“, „quoteTime“);
        der Tag des letzten Abschlusses steht in „lastTradeTime“."""
        friday = day("2026-10-23")
        payload = {"insideTime": (friday + 2) * 86400000, "lastSale": 5.1, "lastTradeTime": (friday * 86400 + 19 * 3600) * 1000, "previousClose": 5.0}
        self.assertEqual(zusatz.last_trade(payload), (friday, 5.1))
        self.assertIsNone(zusatz.last_trade({"lastSale": 5.1}))
        self.assertIsNone(zusatz.last_trade({"lastTradeTime": friday * 86400000}))
        self.assertIsNone(zusatz.last_trade([1, 2]))

    def test_pattern_of_an_unexplained_day_without_prices(self):
        self.assertEqual(zusatz.pattern(0.4123, 0.412, 0.0, 1000.0, 0.001), ["yahoo_ohne_umsatz", "quelle_mit_umsatz", "stufen_1", "stand_hoeher", "stufe_der_quelle_0.001"])
        self.assertEqual(zusatz.pattern(10.0, 10.5, None, 0.0, None)[:4], ["yahoo_umsatz_fehlt", "quelle_ohne_umsatz", "stufen_über 10", "stand_niedriger"])

    def test_class_shares_with_a_dot_where_the_source_writes_them_so(self):
        urls = dict(zusatz.requests_for("cnbc", "BRK-B", day("2026-06-01"), day("2026-10-23")))
        self.assertIn("symbols=BRK.B", urls["profil"])
        self.assertIn("/bars/BRK.B/", urls["historie"])
        self.assertIn("symbol=BRK-B", dict(zusatz.requests_for("otc_markets", "BRK-B", 0, 1))["profil"])

    def test_counts_name_every_check(self):
        good = zusatz.check(self.fetched(self.own, {"name": "Beispiel AG"}), self.own, self.stand, self.yahoo)
        failed = zusatz.check({"quelle": "otc_markets", "status": {"profil": "http_404"}, "rows": {}, "meta": {}}, self.own, self.stand, self.yahoo)
        counts = zusatz.summary_counts([good, failed])
        self.assertEqual(counts["cnbc_vergleichbar"], 1)
        self.assertEqual(counts["cnbc_identitaet_name_bestaetigt"], 1)
        self.assertEqual(counts["otc_markets_abruf_gescheitert"], 1)

    def test_no_paid_access_and_no_keys(self):
        """Keine kostenpflichtigen Zugänge, keine Schlüssel: keine Adresse enthält einen Schlüssel oder eine Anmeldung."""
        for source in zusatz.SOURCES:
            for _, url in zusatz.requests_for(source, "XYZ", day("2026-06-01"), day("2026-10-23")):
                self.assertTrue(url.startswith("https://"))
                for word in ("apikey", "api_key", "token=", "key=", "login", "password"):
                    self.assertNotIn(word, url.lower(), (source, url))


if __name__ == "__main__":
    unittest.main()
