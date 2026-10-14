"""Anbieter-Adapter mit eingefrorenen Formatbeispielen (SYNTHETISCHE Werte, keine echten Kurse).

Die Beispielantworten bilden die dokumentierten Formate nach (Yahoo v8 chart, OpenFIGI v3
mapping, EODHD eod/splits). Sie enthalten erfundene Testwerte, keine Marktdaten.
"""

from __future__ import annotations

import datetime as dt
import io
import os
import unittest
from zoneinfo import ZoneInfo

import numpy as np

from traktien.analytics.codes import InstrumentWarning
from traktien.config import MethodConfig
from traktien.jobs.cutoff import determine_cutoff, session_final_checker
from traktien.providers.base import ListingCandidate, NoDataError, ProviderThrottled
from traktien.providers.calendars import StaticCalendarProvider
from traktien.providers.eodhd import parse_eod, parse_split
from traktien.providers.exchanges import load_exchange_table, unit_info
from traktien.providers.http import HttpClient
from traktien.providers.identity import classify_type, resolve_identity, select_reference, verify_against_prices
from traktien.providers.openfigi import candidates_from_figi
from traktien.providers.tr_universe import evaluate_new_universe, extract_lines, parse_lines
from traktien.providers.yahoo import QUOTE_BATCH, QUOTE_ENDPOINTS, SPARK_ENDPOINTS, YahooProvider, candidates_from_search, parse_chart, parse_quote_response, parse_spark
from traktien.util import crypto
from traktien.util.isin import is_valid_isin, make_isin
from traktien.util.log import redact
from traktien.util.timeutil import UTC, date_to_day
from tests.helpers import weekday_sessions

TABLE = load_exchange_table()
CFG = MethodConfig()


def tr_lines(entries, extra_section=True):
    """Textzeilen im beobachteten Aufbau der TR-Liste (Seitenkopf, Abschnittstitel, Tabellenkopf)."""
    lines = [(1, "TRADING UNIVERSE"), (1, "TRADING UNIVERSE -"), (1, "Stocks"), (1, "ISIN Name"), (1, "_" * 60)]
    page = 1
    for k, (isin, name) in enumerate(entries):
        if k and k % 40 == 0:
            page += 1
            lines.append((page, "TRADING UNIVERSE"))
        lines.append((page, f"{isin} {name}"))
    if extra_section:
        lines += [(page + 1, "TRADING UNIVERSE"), (page + 1, "TRADING UNIVERSE -"), (page + 1, "ETFs"), (page + 1, "ISIN Name")]
        lines += [(page + 1, f"{make_isin('IE00TESTET' + str(i))} Test ETF {i}") for i in range(3)]
    return lines


class IsinTests(unittest.TestCase):
    def test_known_check_digits(self):
        for isin in ("US0378331005", "DE0007164600", "AU0000030678", "GB0002634946", "CH0012005267"):
            self.assertTrue(is_valid_isin(isin), isin)
        self.assertFalse(is_valid_isin("US0378331006"))
        self.assertFalse(is_valid_isin("us0378331005"))


class UniverseParserTests(unittest.TestCase):
    def setUp(self):
        self.entries = [(make_isin(f"ZZ{k:09d}"), f"Testwert {k} AG") for k in range(1, 121)]

    def test_only_stock_section_is_used(self):
        result = parse_lines(tr_lines(self.entries))
        self.assertTrue(result.stock_section_found)
        self.assertEqual(result.count, 120)
        self.assertEqual(result.sections, ["Stocks", "ETFs"])
        self.assertFalse(any("ETF" in e.name for e in result.entries))

    def test_wrapped_names_duplicates_and_invalid_isins(self):
        lines = tr_lines(self.entries[:5], extra_section=False)
        lines.insert(7, (1, "Registered Shares o.N."))  # Fortsetzung des zweiten Namens
        dup = self.entries[0][0]
        bad = self.entries[1][0][:-1] + str((int(self.entries[1][0][-1]) + 1) % 10)
        lines += [(1, f"{dup} Testwert 1 AG Alias"), (1, f"{bad} Kaputt AG")]
        result = parse_lines(lines)
        self.assertEqual(result.duplicates, 1)
        self.assertEqual(result.invalid_isins, 1)
        self.assertIn("Testwert 1 AG Alias", result.entries[0].aliases)
        self.assertTrue(result.entries[1].name.endswith("Registered Shares o.N."))
        invalid = [e for e in result.entries if e.isin == bad][0]
        self.assertFalse(invalid.valid)

    def test_real_pdf_roundtrip(self):
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas

        buffer = io.BytesIO()
        pdf = canvas.Canvas(buffer, pagesize=A4)
        y = 800
        for page, line in tr_lines(self.entries):
            if y < 60 or (line == "TRADING UNIVERSE" and y < 800):
                pdf.showPage()
                y = 800
            pdf.drawString(40, y, line)
            y -= 14
        pdf.save()
        result = parse_lines(extract_lines(buffer.getvalue()))
        self.assertEqual(result.count, 120)
        self.assertEqual([e.isin for e in result.entries], [i for i, _ in self.entries])

    def test_T45_guards_hold_suspicious_lists(self):
        good = parse_lines(tr_lines(self.entries))
        self.assertTrue(evaluate_new_universe(good, None, min_entries=100).accepted)
        missing = parse_lines([(1, "TRADING UNIVERSE"), (1, "irgendein Text")])
        self.assertFalse(evaluate_new_universe(missing, {i: n for i, n in self.entries}, min_entries=100).accepted)
        shrunk = parse_lines(tr_lines(self.entries[:60]))
        decision = evaluate_new_universe(shrunk, {i: n for i, n in self.entries}, min_entries=10)
        self.assertFalse(decision.accepted)
        self.assertIn("zur Prüfung", decision.reason)
        tiny = parse_lines(tr_lines(self.entries[:20]))
        self.assertFalse(evaluate_new_universe(tiny, None, min_entries=100).accepted)


def chart_payload(tz="Europe/Berlin", currency="EUR", with_split=False):
    zone = ZoneInfo(tz)
    days = [dt.date(2026, 10, d) for d in (5, 6, 7, 8, 9, 12)]
    stamps = [int(dt.datetime.combine(d, dt.time(9, 0), tzinfo=zone).timestamp()) for d in days]
    stamps.append(stamps[-1] + 3600)  # Doppelter Eintrag desselben Tages (laufende Kerze)
    close = [10.0, 10.5, None, 11.0, 11.5, 12.0, 12.1]
    payload = {
        "chart": {
            "result": [
                {
                    "meta": {"currency": currency, "exchangeName": "GER", "exchangeTimezoneName": tz, "instrumentType": "EQUITY", "longName": "Testwert AG"},
                    "timestamp": stamps,
                    "indicators": {
                        "quote": [{"open": close, "high": close, "low": close, "close": close, "volume": [100, 200, 300, None, 0, 500, 600]}],
                        "adjclose": [{"adjclose": [9.0, 9.5, None, 10.0, 10.4, 11.0, 11.1]}],
                    },
                    "events": {},
                }
            ],
            "error": None,
        }
    }
    if with_split:
        split_ts = int(dt.datetime.combine(dt.date(2026, 10, 8), dt.time(9, 0), tzinfo=zone).timestamp())
        payload["chart"]["result"][0]["events"]["splits"] = {str(split_ts): {"date": split_ts, "numerator": 2, "denominator": 1}}
    return payload


class YahooParserTests(unittest.TestCase):
    def test_parse_basic_fields_and_units(self):
        history = parse_chart(chart_payload(), "TEST.DE")
        self.assertEqual(len(history), 5)  # 7. Oktober ohne Kurs verworfen, Doppelung zusammengeführt
        self.assertEqual(history.close.tolist()[-1], 12.1)  # letzter Eintrag des Tages gewinnt
        self.assertTrue(np.isnan(history.volume[2]))  # fehlendes Volumen bleibt unbekannt
        self.assertEqual(history.volume[3], 0.0)
        self.assertEqual(history.dropped_invalid, 1)

    def test_T34_dividend_adjusted_close_is_kept_separate(self):
        history = parse_chart(chart_payload(), "TEST.DE")
        self.assertEqual(history.close.tolist()[0], 10.0)
        self.assertEqual(history.close_total.tolist()[0], 9.0)

    def test_T26_running_session_does_not_replace_final_close(self):
        last = date_to_day(dt.date(2026, 10, 12))
        history = parse_chart(chart_payload(), "TEST.DE", session_final=lambda d: d < last)
        self.assertNotIn(last, history.days.tolist())
        self.assertEqual(history.dropped_unfinished, 2)

    def test_split_events_and_raw_reconstruction(self):
        history = parse_chart(chart_payload(with_split=True), "TEST.DE")
        self.assertEqual(len(history.splits), 1)
        self.assertEqual(history.splits[0].factor, 2.0)
        self.assertEqual(history.close_raw.tolist()[0], 20.0)
        self.assertEqual(history.close_raw.tolist()[-1], 12.1)
        self.assertTrue(history.raw_close_reconstructed)

    def test_gbp_pence_unit(self):
        history = parse_chart(chart_payload(tz="Europe/London", currency="GBp"), "TEST.L")
        self.assertEqual(history.price_unit, "GBp")
        self.assertEqual(history.unit_factor, 0.01)
        self.assertEqual(unit_info("GBp"), ("GBP", 0.01))

    def test_error_payload_raises_no_data(self):
        with self.assertRaises(NoDataError):
            parse_chart({"chart": {"result": None, "error": {"code": "Not Found", "description": "No data found"}}}, "X")

    def test_search_candidates(self):
        payload = {"quotes": [{"symbol": "TST.DE", "exchange": "GER", "quoteType": "EQUITY", "longname": "Test AG"}, {"symbol": "TSTF.F", "exchange": "FRA", "quoteType": "ETF"}]}
        found = candidates_from_search(payload, TABLE)
        self.assertEqual([c.exchange_key for c in found], ["XETR", "XFRA"])
        self.assertEqual(found[1].security_type, "ETP")


class OpenFigiAndIdentityTests(unittest.TestCase):
    def figi(self, records):
        return {"data": records}

    def test_symbol_formatting_rules(self):
        records = [
            {"exchCode": "HK", "ticker": "700", "marketSector": "Equity", "securityType": "Common Stock", "name": "TEST HK"},
            {"exchCode": "US", "ticker": "BRK/B", "marketSector": "Equity", "securityType": "Common Stock"},
            {"exchCode": "SS", "ticker": "VOLV B", "marketSector": "Equity", "securityType": "Common Stock"},
            {"exchCode": "GY", "ticker": "TST", "marketSector": "Equity", "securityType": "Common Stock"},
            {"exchCode": "ZZ", "ticker": "UNBEKANNT", "marketSector": "Equity"},
            {"exchCode": "GY", "ticker": "TST", "marketSector": "Corp"},
        ]
        symbols = [c.provider_symbol for c in candidates_from_figi("XX", self.figi(records), TABLE)]
        self.assertEqual(symbols, ["0700.HK", "BRK-B", "VOLV-B.ST", "TST.DE"])

    def test_country_preference_and_T36_one_reference_per_isin(self):
        records = [
            {"exchCode": "GF", "ticker": "TST", "marketSector": "Equity", "securityType": "Common Stock", "name": "TEST AG"},
            {"exchCode": "GY", "ticker": "TST", "marketSector": "Equity", "securityType": "Common Stock", "name": "TEST AG"},
            {"exchCode": "US", "ticker": "TSTY", "marketSector": "Equity", "securityType": "Common Stock", "name": "TEST AG"},
        ]
        isin = "DE0007164600"
        candidates = candidates_from_figi(isin, self.figi(records), TABLE)
        reference, reason = select_reference(isin, candidates, TABLE)
        self.assertEqual(reference.exchange_key, "XETR")
        result = resolve_identity(isin, "Test AG", candidates, TABLE, CFG.excluded_security_types)
        self.assertEqual(result.status, "verifiziert")
        self.assertEqual(result.reference.provider_symbol, "TST.DE")

    def test_adr_and_cayman_preferences(self):
        adr = [ListingCandidate("openfigi", "OTC", "TSTY", "TSTY", "UV", "TEST ADR", "ADR")]
        result = resolve_identity("US1234567890", "Test ADR", adr, TABLE, CFG.excluded_security_types)
        self.assertEqual(result.instrument_type, "adr_gdr")
        self.assertTrue(result.warnings & (1 << InstrumentWarning.OTC_NOTIERUNG))
        cayman = [
            ListingCandidate("openfigi", "US", "TSTA", "TSTA", "US", "TEST", "Common Stock"),
            ListingCandidate("openfigi", "XHKG", "9999.HK", "9999", "HK", "TEST", "Common Stock"),
        ]
        self.assertEqual(select_reference("KYG000000000", cayman, TABLE)[0].exchange_key, "XHKG")

    def test_types_and_exclusions(self):
        excluded = CFG.excluded_security_types
        self.assertEqual(classify_type("Common Stock", None, excluded), "stammaktie")
        self.assertEqual(classify_type("ADR", "Depositary Receipt", excluded), "adr_gdr")
        self.assertEqual(classify_type("REIT", None, excluded), "reit")
        self.assertEqual(classify_type("Closed-End Fund", None, excluded), "fonds_etp")
        self.assertEqual(classify_type("Right", None, excluded), "bezugsrecht")
        self.assertEqual(classify_type("Unit", None, excluded), "unklar")
        fund = [ListingCandidate("openfigi", "US", "TSTF", "TSTF", "US", "TEST FUND", "ETP")]
        self.assertEqual(resolve_identity("US1111111111", "Test Fund", fund, TABLE, excluded).status, "kein_aktieninstrument")
        self.assertEqual(resolve_identity("US1111111111", "Unbekannt", [], TABLE, excluded).status, "unklar")

    def test_renamed_company_is_only_a_warning(self):
        candidates = [ListingCandidate("openfigi", "US", "SLBX", "SLBX", "US", "NEUFIRMA LTD", "Common Stock")]
        result = resolve_identity("AN0000000000", "Altfirma Holding", candidates, TABLE, CFG.excluded_security_types)
        self.assertEqual(result.status, "verifiziert")
        self.assertTrue(result.warnings & (1 << InstrumentWarning.NAME_ABWEICHEND))

    def test_verification_against_price_metadata(self):
        candidates = [ListingCandidate("openfigi", "XETR", "TST.DE", "TST", "GY", "TEST AG", "Common Stock")]
        result = resolve_identity("DE0007164600", "Test AG", candidates, TABLE, CFG.excluded_security_types)
        ok, _ = verify_against_prices(result, provider_exchange_code="GER", provider_tz="Europe/Berlin", provider_type="EQUITY", provider_name="Test AG", table=TABLE)
        self.assertTrue(ok)
        bad_tz, reason = verify_against_prices(result, provider_exchange_code="NYQ", provider_tz="America/New_York", provider_type="EQUITY", provider_name="Test AG", table=TABLE)
        self.assertFalse(bad_tz)
        bad_type, _ = verify_against_prices(result, provider_exchange_code="GER", provider_tz="Europe/Berlin", provider_type="ETF", provider_name="Test AG", table=TABLE)
        self.assertFalse(bad_type)

    def test_same_offset_time_zone_needs_confirming_exchange_code(self):
        # Yahoo meldet für Wiener Notierungen „Europe/Amsterdam“ (gleiche Verschiebung, Börsencode VIE)
        candidates = [ListingCandidate("openfigi", "XWBO", "EBS.VI", "EBS", "AV", "ERSTE GROUP BANK AG", "Common Stock")]
        result = resolve_identity("AT0000652011", "Erste Group Bank AG", candidates, TABLE, CFG.excluded_security_types)
        self.assertEqual(result.reference.exchange_key, "XWBO")
        ok, reason = verify_against_prices(result, provider_exchange_code="VIE", provider_tz="Europe/Amsterdam", provider_type="EQUITY", provider_name="Erste Group Bank AG", table=TABLE)
        self.assertTrue(ok, reason)
        without_code, _ = verify_against_prices(result, provider_exchange_code=None, provider_tz="Europe/Amsterdam", provider_type="EQUITY", provider_name="Erste Group Bank AG", table=TABLE)
        self.assertFalse(without_code)
        other_offset, _ = verify_against_prices(result, provider_exchange_code="VIE", provider_tz="Europe/London", provider_type="EQUITY", provider_name="Erste Group Bank AG", table=TABLE)
        self.assertFalse(other_offset)
        # Toronto und New York haben dieselbe Verschiebung – der Börsencode NYQ widerspricht aber
        toronto = [ListingCandidate("openfigi", "XTSE", "TST.TO", "TST", "CT", "TEST CORP", "Common Stock")]
        result = resolve_identity("CA0000000000", "Test Corp", toronto, TABLE, CFG.excluded_security_types)
        self.assertEqual(result.reference.exchange_key, "XTSE")
        wrong, _ = verify_against_prices(result, provider_exchange_code="NYQ", provider_tz="America/New_York", provider_type="EQUITY", provider_name="Test Corp", table=TABLE)
        self.assertFalse(wrong)


class EodhdTests(unittest.TestCase):
    def test_split_parsing_and_adjustment(self):
        self.assertEqual(parse_split("2.000000/1.000000"), 2.0)
        self.assertEqual(parse_split("1/10"), 0.1)
        rows = [
            {"date": "2026-10-05", "open": 100, "high": 101, "low": 99, "close": 100, "adjusted_close": 98, "volume": 1000},
            {"date": "2026-10-06", "open": 50, "high": 51, "low": 49, "close": 50.5, "adjusted_close": 49.5, "volume": 2500},
        ]
        from traktien.analytics.quality import SplitEvent

        history = parse_eod(rows, [SplitEvent(date_to_day(dt.date(2026, 10, 6)), 2.0)], "TST.XETRA", None)
        self.assertEqual(history.close.tolist(), [50.0, 50.5])  # splitbereinigt, kein Scheinverlust
        self.assertEqual(history.close_raw.tolist(), [100.0, 50.5])
        self.assertEqual(history.volume.tolist(), [2000.0, 2500.0])


class FakeResponse:
    def __init__(self, status, body=b"{}", headers=None):
        self.status_code = status
        self.content = body
        self.headers = headers or {}
        self.url = "https://example.invalid"


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    def request(self, *args, **kwargs):
        self.calls += 1
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class HttpClientTests(unittest.TestCase):
    def test_T44_retry_after_is_honoured(self):
        sleeps = []
        session = FakeSession([FakeResponse(429, headers={"Retry-After": "7"}), FakeResponse(200, b'{"ok": true}')])
        client = HttpClient(session=session, sleep=sleeps.append, max_retries=3)
        response = client.get("https://example.invalid/x")
        self.assertEqual(response.json(), {"ok": True})
        self.assertGreaterEqual(sleeps[0], 7)
        self.assertEqual(client.stats.throttled, 1)

    def test_T44_persistent_throttling_raises_for_checkpoint(self):
        session = FakeSession([FakeResponse(429)] * 10)
        client = HttpClient(session=session, sleep=lambda s: None, max_retries=2, max_consecutive_429=50)
        with self.assertRaises(ProviderThrottled):
            client.get("https://example.invalid/x")

    def test_timeouts_are_retried_then_fail_cleanly(self):
        session = FakeSession([TimeoutError("t"), FakeResponse(503), FakeResponse(200, b"[]")])
        client = HttpClient(session=session, sleep=lambda s: None, max_retries=3)
        self.assertEqual(client.get("https://example.invalid/x").json(), [])
        session = FakeSession([TimeoutError("t")] * 3)
        client = HttpClient(session=session, sleep=lambda s: None, max_retries=2)
        with self.assertRaises(ConnectionError):
            client.get("https://example.invalid/x")


def chart_with_empty_last_candle(*, quote_time=dt.datetime(2026, 10, 13, 17, 36), price=12.4, high=12.6, low=11.9, volume=4321, placeholder=True):
    """Tageskerzen bis 12.10., die Kerze vom 13.10. ohne Schlusskurs; Kursmeldung vom 13.10. (SYNTHETISCH)."""
    zone = ZoneInfo("Europe/Berlin")
    days = [dt.date(2026, 10, d) for d in (8, 9, 12, 13)]
    stamps = [int(dt.datetime.combine(d, dt.time(9, 0), tzinfo=zone).timestamp()) for d in days]
    close = [11.0, 11.5, 12.0, None]
    opens = [11.0, 11.5, 12.0, 12.05]
    if not placeholder:
        stamps, close, opens = stamps[:3], close[:3], opens[:3]
    meta = {
        "currency": "EUR", "exchangeName": "GER", "exchangeTimezoneName": "Europe/Berlin", "instrumentType": "EQUITY",
        "regularMarketPrice": price, "regularMarketTime": int(quote_time.replace(tzinfo=zone).timestamp()),
        "regularMarketDayHigh": high, "regularMarketDayLow": low, "regularMarketVolume": volume,
    }
    n = len(stamps)
    quote = {"open": opens, "high": close[:n], "low": close[:n], "close": close, "volume": [100, 200, 300, None][:n]}
    return {"chart": {"result": [{"meta": meta, "timestamp": stamps, "indicators": {"quote": [quote], "adjclose": [{"adjclose": close}]}, "events": {}}], "error": None}}


class CloseFromQuoteTests(unittest.TestCase):
    """Absicherung (ab 1.5.4): fehlt der Schlusskurs der Tageskerze nach Börsenschluss, gilt die letzte Kursmeldung."""

    D = date_to_day(dt.date(2026, 10, 13))

    def test_empty_last_candle_after_close_is_filled_from_the_quote_and_marked(self):
        history = parse_chart(chart_with_empty_last_candle(), "TEST.DE", session_final=lambda d: True)
        self.assertEqual(int(history.days[-1]), self.D)
        self.assertEqual(float(history.close[-1]), 12.4)
        self.assertEqual(float(history.high[-1]), 12.6)
        self.assertEqual(float(history.low[-1]), 11.9)
        self.assertEqual(float(history.volume[-1]), 4321.0)
        self.assertEqual(float(history.open[-1]), 12.05)  # Eröffnung aus der Tageskerze
        self.assertTrue(np.isnan(history.close_total[-1]))
        self.assertEqual(history.close_from_quote, [self.D])
        self.assertEqual(history.dropped_invalid, 0)

    def test_quote_is_used_even_without_a_candle_for_that_day(self):
        history = parse_chart(chart_with_empty_last_candle(placeholder=False), "TEST.DE", session_final=lambda d: True)
        self.assertEqual(int(history.days[-1]), self.D)
        self.assertTrue(np.isnan(history.open[-1]))
        self.assertEqual(history.close_from_quote, [self.D])

    def test_no_fill_while_the_session_is_not_final_or_without_calendar(self):
        unfinished = parse_chart(chart_with_empty_last_candle(), "TEST.DE", session_final=lambda d: d < self.D)
        self.assertNotIn(self.D, unfinished.days.tolist())
        self.assertEqual(unfinished.close_from_quote, [])
        no_calendar = parse_chart(chart_with_empty_last_candle(), "TEST.DE")
        self.assertNotIn(self.D, no_calendar.days.tolist())

    def test_quote_of_an_older_day_never_overwrites_or_fills_gaps(self):
        older = parse_chart(chart_with_empty_last_candle(quote_time=dt.datetime(2026, 10, 12, 17, 36)), "TEST.DE", session_final=lambda d: True)
        self.assertEqual(older.close_from_quote, [])
        self.assertEqual(float(older.close[older.days.tolist().index(self.D - 1)]), 12.0)

    def test_implausible_day_range_is_dropped_but_close_kept(self):
        history = parse_chart(chart_with_empty_last_candle(high=12.0, low=11.9), "TEST.DE", session_final=lambda d: True)  # Hoch unter Schlusskurs
        self.assertEqual(float(history.close[-1]), 12.4)
        self.assertTrue(np.isnan(history.high[-1]) and np.isnan(history.low[-1]))


def spark_v7(symbols, *, time_utc=dt.datetime(2026, 10, 14, 13, 5, tzinfo=dt.timezone.utc), tz="Europe/Berlin", price=101.5, volume=12345):
    """Spark-Antwort im v7-Format (SYNTHETISCHE Werte)."""
    ts = int(time_utc.timestamp())
    result = []
    for symbol in symbols:
        meta = {"currency": "EUR", "symbol": symbol, "exchangeTimezoneName": tz, "regularMarketPrice": price, "regularMarketTime": ts,
                "chartPreviousClose": 100.0, "previousClose": 100.0, "regularMarketVolume": volume}
        result.append({"symbol": symbol, "response": [{"meta": meta, "timestamp": [ts], "indicators": {"quote": [{"close": [price]}]}}]})
    return {"spark": {"result": result, "error": None}}


class YahooSparkTests(unittest.TestCase):
    """Zwischenstand (ab 1.6): aktuelle Kurse aus der Sammelabfrage „spark“."""

    def test_v7_format_gives_price_time_session_day_and_volume(self):
        quotes, missing = parse_spark(spark_v7(["SAP.DE", "AAPL"]))
        self.assertEqual(missing, {})
        quote = quotes["SAP.DE"]
        self.assertEqual(quote.price, 101.5)
        self.assertEqual(quote.session_day, date_to_day(dt.date(2026, 10, 14)))
        self.assertEqual(quote.volume, 12345.0)
        self.assertEqual(quote.previous_close, 100.0)
        self.assertEqual(quote.currency, "EUR")

    def test_session_day_is_the_exchange_date_of_the_last_price(self):
        # 23:30 UTC am 13.10. = 19:30 Uhr in New York (13.10.) = 08:30 Uhr in Tokio (14.10.)
        late = dt.datetime(2026, 10, 13, 23, 30, tzinfo=dt.timezone.utc)
        ny = parse_spark(spark_v7(["AAPL"], time_utc=late, tz="America/New_York"))[0]["AAPL"]
        tokyo = parse_spark(spark_v7(["7203.T"], time_utc=late, tz="Asia/Tokyo"))[0]["7203.T"]
        self.assertEqual(ny.session_day, date_to_day(dt.date(2026, 10, 13)))
        self.assertEqual(tokyo.session_day, date_to_day(dt.date(2026, 10, 14)))

    def test_missing_market_price_falls_back_to_last_valid_close_and_unknown_volume_stays_unknown(self):
        payload = spark_v7(["X.DE"])
        item = payload["spark"]["result"][0]["response"][0]
        del item["meta"]["regularMarketPrice"], item["meta"]["regularMarketVolume"]
        ts = item["timestamp"][0]
        item["timestamp"] = [ts - 600, ts, ts + 300]
        item["indicators"]["quote"][0]["close"] = [99.0, 100.5, None]
        quote = parse_spark(payload)[0]["X.DE"]
        self.assertEqual(quote.price, 100.5)
        self.assertEqual(int(quote.time_utc.timestamp()), ts)
        self.assertTrue(np.isnan(quote.volume))

    def test_v8_format_and_symbols_without_price(self):
        ts = int(dt.datetime(2026, 10, 14, 13, 5, tzinfo=dt.timezone.utc).timestamp())
        payload = {
            "AAPL": {"symbol": "AAPL", "timestamp": [ts], "close": [230.0], "chartPreviousClose": 228.0},
            "LEER": {"symbol": "LEER", "timestamp": [], "close": []},
        }
        quotes, missing = parse_spark(payload)
        self.assertEqual(quotes["AAPL"].price, 230.0)
        self.assertEqual(quotes["AAPL"].previous_close, 228.0)
        self.assertIn("LEER", missing)

    def test_error_payload_raises(self):
        with self.assertRaises(Exception):
            parse_spark({"spark": {"result": None, "error": {"code": "Bad Request", "description": "too many symbols"}}})

    def test_fetch_quotes_in_batches_of_twenty_and_keeps_a_working_endpoint(self):
        import json as _json

        symbols = [f"T{i}.DE" for i in range(45)]
        bodies = [FakeResponse(404)]  # erste Variante nicht verfügbar → zweite Variante
        for start in range(0, 45, 20):
            bodies.append(FakeResponse(200, _json.dumps(spark_v7(symbols[start : start + 20])).encode()))
        session = FakeSession(bodies)
        provider = YahooProvider(HttpClient(session=session, sleep=lambda s: None, max_retries=1), quote_batches=False)
        result = provider.fetch_quotes(symbols)
        self.assertEqual(len(result.quotes), 45)
        self.assertEqual(result.missing, {})
        self.assertEqual(result.endpoint, SPARK_ENDPOINTS[1])
        self.assertEqual(session.calls, 4)  # 1 Fehlversuch + 3 Abrufe à höchstens 20 Werte

    def test_unavailable_batch_endpoint_stops_early_instead_of_asking_for_every_stock(self):
        symbols = [f"T{i}.DE" for i in range(200)]
        session = FakeSession([FakeResponse(400)] * 60)
        provider = YahooProvider(HttpClient(session=session, sleep=lambda s: None, max_retries=1), quote_batches=False)
        result = provider.fetch_quotes(symbols)
        self.assertEqual(result.quotes, {})
        self.assertEqual(len(result.missing), 200)
        self.assertLessEqual(session.calls, 3 * len(SPARK_ENDPOINTS))
        self.assertIn("Sammelabfrage nicht verfügbar", result.missing["T199.DE"])


def quote_v7(symbols, *, time_utc=dt.datetime(2026, 10, 14, 13, 5, tzinfo=dt.timezone.utc), tz="Europe/Berlin", price=101.5, volume=12345, wrapped=False):
    """Antwort der Kursabfrage „quote“ (v7, SYNTHETISCHE Werte)."""
    ts = int(time_utc.timestamp())

    def num(x):
        return {"raw": x, "fmt": str(x)} if wrapped else x

    result = [
        {"symbol": s, "currency": "EUR", "exchangeTimezoneName": tz, "regularMarketPrice": num(price), "regularMarketTime": num(ts),
         "regularMarketVolume": num(volume), "regularMarketPreviousClose": num(100.0), "marketState": "REGULAR"}
        for s in symbols
    ]
    return {"quoteResponse": {"result": result, "error": None}}


class QuoteRouteSession:
    """Kursabfrage „quote“ und „spark“ ohne Netz: Antwort je nach angefragten Werten (SYNTHETISCHE Kurse)."""

    def __init__(self, *, quote_status=200, unknown=(), first_401=False):
        import json as _json

        self._json = _json
        self.quote_status = quote_status
        self.unknown = set(unknown)
        self.first_401 = first_401
        self.calls: list[tuple[str, int]] = []
        self.crumbs = 0

    def request(self, method, url, params=None, **kwargs):
        params = dict(params or {})
        if "fc.yahoo.com" in url:
            return FakeResponse(404, b"<html>")
        if "getcrumb" in url:
            self.crumbs += 1
            return FakeResponse(200, b"AbC.dEf1/23")
        symbols = params.get("symbols", "").split(",")
        if "/v7/finance/quote" in url:
            self.calls.append(("quote", len(symbols)))
            assert params.get("crumb") == "AbC.dEf1/23"
            if self.first_401:
                self.first_401 = False
                return FakeResponse(401, b'{"finance": {"error": {"code": "Unauthorized", "description": "Invalid Crumb"}}}')
            if self.quote_status != 200:
                return FakeResponse(self.quote_status)
            return FakeResponse(200, self._json.dumps(quote_v7([s for s in symbols if s not in self.unknown])).encode())
        if "/finance/spark" in url:
            self.calls.append(("spark", len(symbols)))
            return FakeResponse(200, self._json.dumps(spark_v7(symbols)).encode())
        return FakeResponse(404)


class YahooQuoteBatchTests(unittest.TestCase):
    """Ab 1.10: Zwischenstand-Kurse zuerst über die Kursabfrage „quote“ (viele Werte je Abruf), Rest über „spark“."""

    def test_quote_format_gives_price_time_session_day_volume_and_previous_close(self):
        for wrapped in (False, True):
            quotes, missing = parse_quote_response(quote_v7(["SAP.DE", "AIR.PA"], wrapped=wrapped))
            self.assertEqual(missing, {})
            quote = quotes["SAP.DE"]
            self.assertEqual(quote.price, 101.5)
            self.assertEqual(quote.session_day, date_to_day(dt.date(2026, 10, 14)))
            self.assertEqual(quote.volume, 12345.0)
            self.assertEqual(quote.previous_close, 100.0)
            self.assertEqual(quote.currency, "EUR")
            self.assertEqual(quote.exchange_tz, "Europe/Berlin")

    def test_session_day_follows_the_exchange_time_zone(self):
        late = dt.datetime(2026, 10, 13, 23, 30, tzinfo=dt.timezone.utc)
        self.assertEqual(parse_quote_response(quote_v7(["AAPL"], time_utc=late, tz="America/New_York"))[0]["AAPL"].session_day, date_to_day(dt.date(2026, 10, 13)))
        self.assertEqual(parse_quote_response(quote_v7(["7203.T"], time_utc=late, tz="Asia/Tokyo"))[0]["7203.T"].session_day, date_to_day(dt.date(2026, 10, 14)))

    def test_invalid_price_is_reported_and_error_payload_raises(self):
        payload = quote_v7(["X.DE"])
        payload["quoteResponse"]["result"][0]["regularMarketPrice"] = None
        quotes, missing = parse_quote_response(payload)
        self.assertEqual(quotes, {})
        self.assertIn("X.DE", missing)
        with self.assertRaises(Exception):
            parse_quote_response({"quoteResponse": {"result": None, "error": {"code": "Bad Request", "description": "Missing value for the \"symbols\" argument"}}})
        with self.assertRaises(Exception):
            parse_quote_response({"finance": {"result": None, "error": {"code": "Unauthorized"}}})

    def test_batches_of_150_and_only_unknown_symbols_go_to_spark(self):
        symbols = [f"T{i}.DE" for i in range(400)]
        session = QuoteRouteSession(unknown={"T5.DE", "T300.DE"})
        provider = YahooProvider(HttpClient(session=session, sleep=lambda s: None, max_retries=1))
        result = provider.fetch_quotes(symbols)
        self.assertEqual(len(result.quotes), 400)
        self.assertEqual(result.missing, {})
        self.assertEqual(session.calls, [("quote", QUOTE_BATCH), ("quote", QUOTE_BATCH), ("quote", 100), ("spark", 2)])
        self.assertEqual(result.requests, 4)
        self.assertEqual(result.endpoint, SPARK_ENDPOINTS[0])  # zuletzt verwendet: Spark für den Rest

    def test_expired_crumb_is_renewed_once(self):
        session = QuoteRouteSession(first_401=True)
        provider = YahooProvider(HttpClient(session=session, sleep=lambda s: None, max_retries=1))
        result = provider.fetch_quotes([f"T{i}.DE" for i in range(30)])
        self.assertEqual(len(result.quotes), 30)
        self.assertEqual(session.crumbs, 2)
        self.assertEqual([kind for kind, _ in session.calls], ["quote", "quote"])

    def test_unavailable_quote_endpoint_falls_back_to_spark_for_everything(self):
        session = QuoteRouteSession(quote_status=404)
        provider = YahooProvider(HttpClient(session=session, sleep=lambda s: None, max_retries=1))
        result = provider.fetch_quotes([f"T{i}.DE" for i in range(45)])
        self.assertEqual(len(result.quotes), 45)
        self.assertEqual([kind for kind, _ in session.calls], ["quote"] * len(QUOTE_ENDPOINTS) + ["spark"] * 3)


class ParallelQuoteTests(unittest.TestCase):
    """Ab 1.12: Sammelabfragen parallel (mehrere Abrufer, gemeinsamer Mindestabstand) – gleiches Ergebnis wie nacheinander."""

    def _session(self, **kwargs):
        import threading

        session = QuoteRouteSession(**kwargs)
        lock = threading.Lock()
        plain = session.request

        def request(method, url, params=None, **kw):
            with lock:  # die Testsitzung teilen sich alle Abrufer (echte Klone haben eigene Sitzungen)
                return plain(method, url, params=params, **kw)

        session.request = request
        return session

    def test_parallel_result_equals_sequential(self):
        symbols = [f"T{i}.DE" for i in range(1000)]
        unknown = {"T5.DE", "T300.DE", "T999.DE"} | {f"T{i}.DE" for i in range(600, 650)}
        results = {}
        for workers in (1, 3):
            session = self._session(unknown=unknown)
            provider = YahooProvider(HttpClient(session=session, sleep=lambda s: None, max_retries=1), quote_workers=workers)
            results[workers] = (provider.fetch_quotes(symbols), sorted(session.calls))
        sequential, parallel = results[1][0], results[3][0]
        self.assertEqual(set(parallel.quotes), set(symbols))
        self.assertEqual({k: v.price for k, v in parallel.quotes.items()}, {k: v.price for k, v in sequential.quotes.items()})
        self.assertEqual(parallel.missing, {})
        self.assertEqual(results[1][1], results[3][1], "dieselben Abrufe, nur gleichzeitig")
        self.assertEqual((parallel.quote_requests, parallel.spark_requests), (7, 3))
        self.assertEqual((parallel.quote_found, parallel.spark_found), (1000 - len(unknown), len(unknown)))
        self.assertEqual(parallel.requests, 10)

    def test_clones_share_the_minimum_interval_per_host(self):
        import time

        http = HttpClient(session=self._session(), sleep=lambda s: None, max_retries=1, min_interval={"query2.finance.yahoo.com": 0.4})
        twin = http.clone(min_interval={"query2.finance.yahoo.com": 0.12})
        other = http.clone(min_interval={"query2.finance.yahoo.com": 0.12})
        self.assertIs(twin._lock, http._lock)
        self.assertIs(twin._next_allowed, other._next_allowed, "ein Zeitplan für alle Abrufer")
        started = time.monotonic()
        twin._throttle("query2.finance.yahoo.com")
        other._throttle("query2.finance.yahoo.com")
        twin._throttle("query2.finance.yahoo.com")
        ahead = http._next_allowed["query2.finance.yahoo.com"] - started
        self.assertAlmostEqual(ahead, 3 * 0.12, delta=0.05, msg="drei Abrufe zusammen: dreimal der kurze Abstand")
        provider = YahooProvider(http, quote_workers=3)
        helper = provider._helper()
        self.assertEqual(helper.http.min_interval["query2.finance.yahoo.com"], 0.12)
        self.assertEqual(helper.quote_workers, 1)

    def test_throttling_in_one_worker_stops_the_rest_and_keeps_loaded_quotes(self):
        session = self._session()
        calls = {"n": 0}
        plain = session.request

        def request(method, url, params=None, **kw):
            if "/v7/finance/quote" in url:
                calls["n"] += 1
                if calls["n"] >= 3:
                    return FakeResponse(429)
            return plain(method, url, params=params, **kw)

        session.request = request
        provider = YahooProvider(HttpClient(session=session, sleep=lambda s: None, max_retries=1), quote_workers=3)
        result = provider.fetch_quotes([f"T{i}.DE" for i in range(1200)])
        self.assertTrue(result.throttled)
        self.assertGreaterEqual(len(result.quotes), QUOTE_BATCH, "bereits geladene Kurse bleiben")
        self.assertEqual(len(result.quotes) + len(result.missing), 1200)
        self.assertTrue(all(reason == "Kursanbieter drosselt" for reason in result.missing.values()))
        self.assertNotIn("spark", {kind for kind, _ in session.calls}, "nach einer Drosselung kein weiterer Weg")


def summary_payload(*, analysts=5, mean=3.72, median=3.5, high=6.0, low=2.0, current=1.415, trend=(2, 3, 0, 0, 0), wrapped=False):
    """quoteSummary-Antwort (SYNTHETISCHE Werte)."""
    def num(x):
        return {"raw": x, "fmt": str(x)} if wrapped else x

    fin = {"currentPrice": num(current), "targetMeanPrice": num(mean), "targetMedianPrice": num(median), "targetHighPrice": num(high),
           "targetLowPrice": num(low), "recommendationMean": num(1.4), "recommendationKey": "buy", "numberOfAnalystOpinions": num(analysts),
           "financialCurrency": "USD"}
    rows = [{"period": "0m", "strongBuy": trend[0], "buy": trend[1], "hold": trend[2], "sell": trend[3], "strongSell": trend[4]},
            {"period": "-1m", "strongBuy": 9, "buy": 9, "hold": 9, "sell": 9, "strongSell": 9}]
    return {"quoteSummary": {"result": [{"financialData": fin, "recommendationTrend": {"trend": rows, "maxAge": 86400}}], "error": None}}


class RecordingSession:
    """Antwortet je nach Adresse und merkt sich Adressen und Parameter (ohne Netz)."""

    def __init__(self, routes):
        self.routes = {key: list(value) for key, value in routes.items()}
        self.seen: list[tuple[str, dict]] = []

    def request(self, method, url, params=None, **kwargs):
        self.seen.append((url, dict(params or {})))
        for key, responses in self.routes.items():
            if key in url:
                return responses.pop(0) if len(responses) > 1 else responses[0]
        return FakeResponse(404)


class YahooAnalystTests(unittest.TestCase):
    """Potenzial (ab 1.6): Kursziele und Empfehlungen aus quoteSummary."""

    def test_targets_counts_and_current_month_ratings(self):
        from traktien.providers.yahoo import parse_quote_summary

        for wrapped in (False, True):
            view = parse_quote_summary(summary_payload(wrapped=wrapped), "PDSB")
            self.assertEqual(view.analysts, 5)
            self.assertAlmostEqual(view.target_mean, 3.72)
            self.assertAlmostEqual(view.target_high, 6.0)
            self.assertAlmostEqual(view.target_low, 2.0)
            self.assertAlmostEqual(view.current_price, 1.415)
            self.assertEqual((view.strong_buy, view.buy, view.hold, view.sell, view.strong_sell), (2, 3, 0, 0, 0))
            self.assertEqual(view.ratings, 5)
            self.assertEqual(view.rec_key, "buy")
            self.assertTrue(view.has_targets)

    def test_no_coverage_gives_zero_analysts_and_no_targets(self):
        from traktien.providers.yahoo import parse_quote_summary

        payload = {"quoteSummary": {"result": [{"financialData": {"currentPrice": 4.2, "recommendationKey": "none", "targetMeanPrice": {}},
                                                "recommendationTrend": {"trend": []}}], "error": None}}
        view = parse_quote_summary(payload, "KLEIN.DE")
        self.assertEqual(view.analysts, 0)
        self.assertTrue(np.isnan(view.target_mean))
        self.assertIsNone(view.rec_key)
        self.assertFalse(view.has_targets)
        self.assertEqual(view.ratings, 0)

    def test_unknown_symbol_and_other_errors(self):
        from traktien.providers.base import NoDataError, ProviderError
        from traktien.providers.yahoo import parse_quote_summary

        with self.assertRaises(NoDataError):
            parse_quote_summary({"quoteSummary": {"result": None, "error": {"code": "Not Found", "description": "Quote not found for symbol: X"}}}, "X")
        with self.assertRaises(ProviderError):
            parse_quote_summary({"finance": {"result": None, "error": {"code": "Unauthorized", "description": "Invalid Crumb"}}}, "X")

    def test_cookie_then_crumb_then_summary_and_crumb_never_in_logs(self):
        import json as _json

        session = RecordingSession({
            "fc.yahoo.com": [FakeResponse(404, b"<html>")],
            "getcrumb": [FakeResponse(200, b"AbC.dEf1/23")],
            "quoteSummary": [FakeResponse(200, _json.dumps(summary_payload()).encode())],
        })
        provider = YahooProvider(HttpClient(session=session, sleep=lambda s: None, max_retries=1))
        with self.assertLogs("traktien", level="DEBUG") as logs:
            import logging

            logging.getLogger("traktien").debug("Start")
            view = provider.analyst_view("PDSB")
            provider.analyst_view("PDSB")
        self.assertEqual(view.analysts, 5)
        urls = [url for url, _ in session.seen]
        self.assertEqual(sum("getcrumb" in u for u in urls), 1, "Crumb wird je Sitzung nur einmal geholt")
        self.assertIn("fc.yahoo.com", urls[0])
        params = [p for url, p in session.seen if "quoteSummary" in url]
        self.assertEqual(params[0]["crumb"], "AbC.dEf1/23")
        self.assertEqual(params[0]["modules"], "financialData,recommendationTrend")
        self.assertFalse(any("AbC.dEf1/23" in line for line in logs.output))

    def test_expired_crumb_is_renewed_once(self):
        import json as _json

        session = RecordingSession({
            "fc.yahoo.com": [FakeResponse(404)],
            "getcrumb": [FakeResponse(200, b"alt12345"), FakeResponse(200, b"neu67890")],
            "quoteSummary": [FakeResponse(401, b'{"finance":{"error":{"code":"Unauthorized"}}}'), FakeResponse(200, _json.dumps(summary_payload()).encode())],
        })
        provider = YahooProvider(HttpClient(session=session, sleep=lambda s: None, max_retries=1))
        self.assertEqual(provider.analyst_view("AAPL").analysts, 5)
        crumbs = [p["crumb"] for url, p in session.seen if "quoteSummary" in url]
        self.assertEqual(crumbs, ["alt12345", "neu67890"])

    def test_html_instead_of_crumb_is_rejected(self):
        from traktien.providers.base import ProviderError

        session = RecordingSession({"fc.yahoo.com": [FakeResponse(404)], "getcrumb": [FakeResponse(200, b"<html>Too Many Requests</html>")]})
        provider = YahooProvider(HttpClient(session=session, sleep=lambda s: None, max_retries=1))
        with self.assertRaises(ProviderError):
            provider.analyst_view("AAPL")


class CutoffTests(unittest.TestCase):
    def setUp(self):
        start, end = dt.date(2026, 9, 1), dt.date(2026, 10, 20)
        self.calendars = StaticCalendarProvider(
            {
                "XNYS": weekday_sessions(start, end),
                "XETR": weekday_sessions(start, end),
                "XTKS": weekday_sessions(start, end, [dt.date(2026, 10, 12)]),
            },
            {"XNYS": ("America/New_York", dt.time(16, 0)), "XETR": ("Europe/Berlin", dt.time(17, 30)), "XTKS": ("Asia/Tokyo", dt.time(15, 30))},
        )

    def test_tuesday_morning_gives_monday(self):
        now = dt.datetime(2026, 10, 13, 6, 0, tzinfo=ZoneInfo("Europe/Berlin")).astimezone(UTC)
        result = determine_cutoff({"XNYS", "XETR", "XTKS"}, self.calendars, now)
        self.assertEqual(result.cutoff_day, date_to_day(dt.date(2026, 10, 12)))
        self.assertIn("XTKS", result.markets_closed)  # Feiertag Japan: Markt geschlossen, nicht „Daten fehlen“

    def test_running_asian_session_blocks_same_day(self):
        now = dt.datetime(2026, 10, 14, 6, 0, tzinfo=ZoneInfo("Europe/Berlin")).astimezone(UTC)
        result = determine_cutoff({"XNYS", "XTKS"}, self.calendars, now)
        self.assertEqual(result.cutoff_day, date_to_day(dt.date(2026, 10, 13)))

    def test_T26_session_final_checker(self):
        now = dt.datetime(2026, 10, 13, 18, 0, tzinfo=ZoneInfo("Europe/Berlin")).astimezone(UTC)
        final = session_final_checker(self.calendars, "XNYS", now)
        self.assertFalse(final(date_to_day(dt.date(2026, 10, 13))))  # US-Sitzung läuft noch
        self.assertTrue(final(date_to_day(dt.date(2026, 10, 12))))


class DaylightSavingTests(unittest.TestCase):
    """T25: Unterschiedliche Sommerzeitwechsel in den USA (8.3./1.11.2026) und Europa (29.3./25.10.2026)."""

    def setUp(self):
        start, end = dt.date(2026, 2, 1), dt.date(2026, 11, 30)
        self.calendars = StaticCalendarProvider(
            {"XNYS": weekday_sessions(start, end), "XETR": weekday_sessions(start, end), "XASX": weekday_sessions(start, end)},
            {"XNYS": ("America/New_York", dt.time(16, 0)), "XETR": ("Europe/Berlin", dt.time(17, 30)), "XASX": ("Australia/Sydney", dt.time(16, 0))},
        )

    @staticmethod
    def berlin(*args) -> dt.datetime:
        return dt.datetime(*args, tzinfo=ZoneInfo("Europe/Berlin")).astimezone(UTC)

    def test_T25_us_close_in_berlin_time_follows_both_switches(self):
        # 16:00 New York in Berliner Zeit: Winter 22 Uhr, März-Lücke 21 Uhr, Sommer 22 Uhr, Oktober-Lücke 21 Uhr.
        for (y, m, d), hour in (((2026, 2, 9), 22), ((2026, 3, 9), 21), ((2026, 6, 8), 22), ((2026, 10, 26), 21), ((2026, 11, 9), 22)):
            with self.subTest(datum=f"{d}.{m}.{y}"):
                session = date_to_day(dt.date(y, m, d))
                close = self.calendars.session_close_utc("XNYS", session).astimezone(ZoneInfo("Europe/Berlin"))
                self.assertEqual(close.hour, hour)
                self.assertFalse(session_final_checker(self.calendars, "XNYS", self.berlin(y, m, d, hour, 59))(session), "Nachlieferungsfrist läuft noch")
                self.assertTrue(session_final_checker(self.calendars, "XNYS", self.berlin(y, m, d, hour + 1, 0))(session))

    def test_T25_six_oclock_run_uses_previous_trading_day_around_switches(self):
        for y, m, d in ((2026, 3, 10), (2026, 3, 31), (2026, 10, 27), (2026, 11, 3)):  # Dienstage rund um die Umstellungen
            with self.subTest(datum=f"{d}.{m}.{y}"):
                result = determine_cutoff({"XNYS", "XETR", "XASX"}, self.calendars, self.berlin(y, m, d, 6, 0))
                self.assertEqual(result.cutoff_day, date_to_day(dt.date(y, m, d) - dt.timedelta(days=1)))


class CryptoAndRedactionTests(unittest.TestCase):
    def test_container_roundtrip_and_tamper_detection(self):
        key = crypto.derive_key("geheim", b"0" * 16, 1000)
        blob = crypto.pack(b'{"a":1}', key, "snapshots/x/a.bin")
        self.assertEqual(crypto.unpack(blob, key, "snapshots/x/a.bin"), b'{"a":1}')
        with self.assertRaises(crypto.ContainerError):
            crypto.unpack(blob, key, "snapshots/x/b.bin")  # vertauschte Datei
        with self.assertRaises(crypto.ContainerError):
            crypto.unpack(blob, crypto.derive_key("falsch", b"0" * 16, 1000), "snapshots/x/a.bin")
        plain = crypto.pack(b"[]", None, "p")
        self.assertEqual(crypto.unpack(plain, None, "p"), b"[]")
        descriptor = crypto.crypto_descriptor(key)
        self.assertNotIn("geheim", str(descriptor))
        self.assertEqual(crypto.verify_descriptor(descriptor, "geheim").key, key.key)

    def test_T52_secrets_are_redacted_in_logs(self):
        os.environ["OPENFIGI_API_KEY"] = "abcd-secret-1234"
        try:
            text = redact("GET https://eodhd.com/api/eod/X?api_token=XYZ123&fmt=json key=abcd-secret-1234")
            self.assertNotIn("XYZ123", text)
            self.assertNotIn("abcd-secret-1234", text)
        finally:
            del os.environ["OPENFIGI_API_KEY"]


if __name__ == "__main__":
    unittest.main()
