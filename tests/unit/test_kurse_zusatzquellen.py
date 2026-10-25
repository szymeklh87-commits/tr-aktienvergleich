"""Weitere Vergleichsquellen für US-Aktien ohne Nasdaq-Kurse (ab 1.18.3, ``tests/live/kurse_zusatzquellen.py``) –
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
