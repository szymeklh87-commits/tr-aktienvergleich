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
from traktien.providers.yahoo import candidates_from_search, parse_chart
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
