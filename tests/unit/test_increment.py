"""Sammelabruf der Tageskurse (ab 1.17): Spark-Antwort mit mehreren Tagen, Abruf in Paketen und Planung je Notierung.

Alle Werte sind SYNTHETISCH (keine Marktdaten). Geprüft wird, dass der Sammelabruf nur den eindeutigen Normalfall
übernimmt – genau eine neue, abgeschlossene Sitzung mit passender Kursmeldung und deckungsgleicher Überlappung – und
alles andere wie bisher dem Chart-Abruf überlässt.
"""

from __future__ import annotations

import datetime as dt
import json
import math
import unittest
from zoneinfo import ZoneInfo

import numpy as np

from traktien.jobs.increment import ACTION_CURRENT, ACTION_NEW, ACTION_SINGLE, StoredTail, plan_increment, session_days
from traktien.providers.base import LiveQuote, ProviderError
from traktien.providers.http import HttpClient
from traktien.providers.yahoo import SPARK_BATCH, SPARK_ENDPOINTS, YahooProvider, parse_spark_history
from traktien.util.timeutil import date_to_day, iso_utc

DAY = lambda y, m, d: date_to_day(dt.date(y, m, d))  # noqa: E731


def open_ts(day: dt.date, tz: str, hour: int = 9, minute: int = 0) -> int:
    return int(dt.datetime(day.year, day.month, day.day, hour, minute, tzinfo=ZoneInfo(tz)).timestamp())


def spark_days(symbol: str, dates: list[dt.date], closes: list[float | None], *, tz: str = "Europe/Berlin", last=None, volume=5000.0, high=None, low=None, currency="EUR") -> dict:
    """Ein Ergebnis der v7-Spark-Antwort mit mehreren Tageskerzen (SYNTHETISCH)."""
    stamps = [open_ts(d, tz) for d in dates]
    last_date = last or dates[-1]
    meta = {
        "currency": currency, "symbol": symbol, "exchangeTimezoneName": tz, "exchangeName": "GER", "instrumentType": "EQUITY",
        "regularMarketPrice": closes[-1], "regularMarketTime": open_ts(last_date, tz, 17, 35),
        "regularMarketVolume": volume, "chartPreviousClose": 99.0,
    }
    if high is not None:
        meta["regularMarketDayHigh"] = high
    if low is not None:
        meta["regularMarketDayLow"] = low
    return {"symbol": symbol, "response": [{"meta": meta, "timestamp": stamps, "indicators": {"quote": [{"close": closes}]}}]}


def quote_for(day: dt.date, price: float, *, tz="Europe/Berlin", volume=7000.0, day_open=99.5, high=102.0, low=98.0) -> LiveQuote:
    moment = dt.datetime(day.year, day.month, day.day, 17, 35, tzinfo=ZoneInfo(tz)).astimezone(dt.timezone.utc)
    return LiveQuote("X.DE", price, moment, date_to_day(day), volume, 100.0, "EUR", tz, day_open=day_open, day_high=high, day_low=low)


WEEK = [dt.date(2026, 10, d) for d in (19, 20, 21, 22, 23)]


def stored(dates, closes, quality=None) -> StoredTail:
    return StoredTail(
        np.array([date_to_day(d) for d in dates], dtype=np.int64),
        np.array(closes, dtype=np.float64),
        np.array(quality or [0] * len(dates), dtype=np.int64),
    )


def recent_of(item: dict):
    found, missing, _ = parse_spark_history({"spark": {"result": [item], "error": None}})
    return found.get(item["symbol"])


ALL_FINAL = lambda day: True  # noqa: E731


class SparkHistoryParseTests(unittest.TestCase):
    def test_v7_with_several_days_keeps_timestamps_closes_and_meta(self):
        item = spark_days("X.DE", WEEK, [100.0, 101.0, None, 102.0, 103.0], high=104.0, low=101.5)
        found, missing, fields = parse_spark_history({"spark": {"result": [item, {"symbol": "LEER.DE", "response": []}], "error": None}})
        recent = found["X.DE"]
        self.assertEqual(len(recent.timestamps), 5)
        self.assertTrue(math.isnan(recent.close[2]), "Lücke bleibt als nan erhalten")
        self.assertEqual(recent.exchange_tz, "Europe/Berlin")
        self.assertEqual((recent.last_price, recent.last_volume, recent.last_high, recent.last_low), (103.0, 5000.0, 104.0, 101.5))
        self.assertEqual(missing, {"LEER.DE": "keine Daten"})
        self.assertEqual(fields["regularMarketVolume"], 1)
        self.assertEqual(fields["indicators.close"], 1)
        days = session_days(recent.timestamps, recent.exchange_tz)
        self.assertEqual(days.tolist(), [date_to_day(d) for d in WEEK])

    def test_v8_without_time_zone_takes_the_listing_zone_later(self):
        sydney = [dt.date(2026, 10, 22), dt.date(2026, 10, 23)]
        payload = {"BHP.AX": {"symbol": "BHP.AX", "timestamp": [open_ts(d, "Australia/Sydney", 10) for d in sydney], "close": [45.0, 45.5], "chartPreviousClose": 44.0}}
        found, missing, _ = parse_spark_history(payload)
        recent = found["BHP.AX"]
        self.assertIsNone(recent.exchange_tz)
        # 10:00 Uhr in Sydney ist am Vortag 23:00 Uhr UTC – nur mit der Zeitzone der Börse stimmt der Handelstag
        self.assertEqual(session_days(recent.timestamps, "Australia/Sydney").tolist(), [date_to_day(d) for d in sydney])
        self.assertNotEqual(session_days(recent.timestamps, "UTC").tolist(), [date_to_day(d) for d in sydney])

    def test_error_payload_raises(self):
        with self.assertRaises(ProviderError):
            parse_spark_history({"spark": {"result": None, "error": {"code": "Bad Request", "description": "Number of symbols needs to be less than or equal to 20"}}})


class SparkRouteSession:
    """Testsitzung: beantwortet Spark-Abrufe mit einer Woche Tageskurse je Symbol, zählt die Pakete."""

    def __init__(self, *, fail_first_endpoint=False, throttle_after=None):
        self.calls = []
        self.fail_first_endpoint = fail_first_endpoint
        self.throttle_after = throttle_after

    def request(self, method, url, params=None, **kwargs):
        from tests.unit.test_providers import FakeResponse

        params = params or {}
        symbols = params.get("symbols", "").split(",")
        self.calls.append((url, len(symbols), params.get("range")))
        if self.fail_first_endpoint and url == SPARK_ENDPOINTS[0]:
            return FakeResponse(404)
        if self.throttle_after is not None and len(self.calls) > self.throttle_after:
            return FakeResponse(429)
        result = [spark_days(s, WEEK, [100.0, 101.0, 102.0, 103.0, 104.0]) for s in symbols]
        return FakeResponse(200, json.dumps({"spark": {"result": result, "error": None}}).encode())


class FetchRecentTests(unittest.TestCase):
    def test_packages_of_20_with_one_month_range(self):
        session = SparkRouteSession()
        provider = YahooProvider(HttpClient(session=session, sleep=lambda s: None, max_retries=1))
        symbols = [f"T{i}.DE" for i in range(45)]
        result = provider.fetch_recent(symbols)
        self.assertEqual(set(result.bars), set(symbols))
        self.assertEqual([n for _, n, _ in session.calls], [SPARK_BATCH, SPARK_BATCH, 5])
        self.assertEqual({r for _, _, r in session.calls}, {"1mo"})
        self.assertEqual(result.requests, 3)
        self.assertEqual(result.missing, {})

    def test_next_endpoint_is_tried_and_kept(self):
        session = SparkRouteSession(fail_first_endpoint=True)
        provider = YahooProvider(HttpClient(session=session, sleep=lambda s: None, max_retries=1))
        result = provider.fetch_recent([f"T{i}.DE" for i in range(30)])
        self.assertEqual(len(result.bars), 30)
        self.assertEqual(result.endpoint, SPARK_ENDPOINTS[1])
        self.assertEqual([url for url, _, _ in session.calls], [SPARK_ENDPOINTS[0], SPARK_ENDPOINTS[1], SPARK_ENDPOINTS[1]])

    def test_throttling_keeps_loaded_bars_and_marks_the_rest(self):
        session = SparkRouteSession(throttle_after=1)
        provider = YahooProvider(HttpClient(session=session, sleep=lambda s: None, max_retries=0, max_consecutive_429=1))
        result = provider.fetch_recent([f"T{i}.DE" for i in range(60)])
        self.assertTrue(result.throttled)
        self.assertEqual(len(result.bars), 20)
        self.assertEqual(set(result.missing.values()), {"Kursanbieter drosselt"})
        self.assertEqual(len(result.missing), 40)

    def test_parallel_equals_sequential(self):
        import threading

        outcomes = {}
        for workers in (1, 3):
            session = SparkRouteSession()
            lock = threading.Lock()
            plain = session.request

            def request(method, url, params=None, _plain=plain, _lock=lock, **kw):
                with _lock:
                    return _plain(method, url, params=params, **kw)

            session.request = request
            provider = YahooProvider(HttpClient(session=session, sleep=lambda s: None, max_retries=1), quote_workers=workers)
            result = provider.fetch_recent([f"T{i}.DE" for i in range(205)])
            outcomes[workers] = ({k: v.close.tolist() for k, v in result.bars.items()}, result.requests)
        self.assertEqual(outcomes[1], outcomes[3])
        self.assertEqual(outcomes[3][1], 11)


class PlanIncrementTests(unittest.TestCase):
    def setUp(self):
        self.tail = stored(WEEK[:4], [100.0, 101.0, 102.0, 103.0])
        self.recent = recent_of(spark_days("X.DE", WEEK, [100.0, 101.0, 102.0, 103.0, 104.0], high=105.0, low=102.5, volume=4000.0))

    def plan(self, tail=None, recent="default", quote="default", final=ALL_FINAL, tz="Europe/Berlin"):
        return plan_increment(
            self.tail if tail is None else tail,
            self.recent if recent == "default" else recent,
            quote_for(WEEK[4], 104.0) if quote == "default" else quote,
            tz_name=tz,
            session_final=final,
            symbol="X.DE",
        )

    def test_one_new_session_becomes_a_bar_with_quote_values(self):
        plan = self.plan()
        self.assertEqual((plan.action, plan.reason), (ACTION_NEW, "neue_sitzung"))
        h = plan.history
        self.assertEqual(h.days.tolist(), [date_to_day(WEEK[4])])
        self.assertEqual(h.close[0], 104.0)
        self.assertEqual(h.close_raw[0], 104.0)
        self.assertEqual(h.volume[0], 7000.0)
        self.assertEqual(plan.overlap, 4)
        self.assertEqual(plan.sources["umsatz"], "quote")
        # Hoch 102 liegt unter dem Schlusskurs 104: Hoch und Tief passen nicht und werden nicht übernommen
        self.assertTrue(math.isnan(h.high[0]) and math.isnan(h.low[0]))
        self.assertEqual(plan.sources["hoch_tief"], "fehlt")
        self.assertEqual(h.bar_times_utc[0], iso_utc(dt.datetime.fromtimestamp(open_ts(WEEK[4], "Europe/Berlin"), tz=dt.timezone.utc)))
        self.assertEqual(h.open[0], 99.5)

    def test_consistent_high_low_and_open_are_kept(self):
        plan = self.plan(quote=quote_for(WEEK[4], 104.0, day_open=103.2, high=104.5, low=102.9))
        h = plan.history
        self.assertEqual((h.open[0], h.high[0], h.low[0]), (103.2, 104.5, 102.9))
        self.assertNotIn("hoch_tief", plan.sources)

    def test_without_quote_the_spark_message_supplies_volume_high_and_low(self):
        plan = self.plan(quote=None)
        self.assertEqual(plan.action, ACTION_NEW)
        self.assertEqual(plan.sources["umsatz"], "spark")
        self.assertEqual((plan.history.volume[0], plan.history.high[0], plan.history.low[0]), (4000.0, 105.0, 102.5))
        self.assertTrue(math.isnan(plan.history.open[0]))

    def test_nothing_new_and_unfinished_sessions(self):
        self.assertEqual(self.plan(tail=stored(WEEK, [100.0, 101.0, 102.0, 103.0, 104.0])).action, ACTION_CURRENT)
        unfinished = self.plan(final=lambda day: day < date_to_day(WEEK[4]))
        self.assertEqual((unfinished.action, unfinished.reason), (ACTION_CURRENT, "keine_neue_sitzung"))

    def test_split_or_correction_in_the_overlap_goes_to_the_chart_path(self):
        split = recent_of(spark_days("X.DE", WEEK, [50.0, 50.5, 51.0, 51.5, 52.0]))
        plan = self.plan(recent=split, quote=quote_for(WEEK[4], 52.0))
        self.assertEqual((plan.action, plan.reason), (ACTION_SINGLE, "abweichung"))
        self.assertGreater(plan.max_deviation, 0.4)
        corrected = recent_of(spark_days("X.DE", WEEK, [100.0, 101.0, 102.01, 103.0, 104.0]))
        self.assertEqual(self.plan(recent=corrected).reason, "abweichung")

    def test_two_new_sessions_gap_and_missing_days_go_to_the_chart_path(self):
        self.assertEqual(self.plan(tail=stored(WEEK[:3], [100.0, 101.0, 102.0])).reason, "mehrere_neue_tage")
        old_tail = stored([dt.date(2026, 9, 1)], [90.0])
        self.assertEqual(self.plan(tail=old_tail).reason, "keine_ueberlappung")
        holey = recent_of(spark_days("X.DE", WEEK, [100.0, None, 102.0, 103.0, 104.0]))
        self.assertEqual(self.plan(recent=holey).reason, "tag_fehlt")
        self.assertEqual(self.plan(recent=None).reason, "keine_sammeldaten")

    def test_provisional_close_in_the_overlap_goes_to_the_chart_path(self):
        tail = stored(WEEK[:4], [100.0, 101.0, 102.0, 103.0], quality=[0, 0, 0, 1])
        self.assertEqual(self.plan(tail=tail).reason, "vorlaeufiger_kurs")

    def test_message_must_match_the_close_and_carry_a_volume(self):
        self.assertEqual(self.plan(quote=quote_for(WEEK[4], 104.5)).reason, "meldung_passt_nicht")
        self.assertEqual(self.plan(quote=quote_for(WEEK[4], 104.0, volume=math.nan)).reason, "umsatz_fehlt")
        stale = recent_of(spark_days("X.DE", WEEK, [100.0, 101.0, 102.0, 103.0, 104.0], last=WEEK[3]))
        self.assertEqual(self.plan(recent=stale, quote=quote_for(WEEK[3], 103.0)).reason, "meldung_fehlt")

    def test_exchange_time_zone_decides_the_session_day(self):
        sydney = [dt.date(2026, 10, d) for d in (20, 21, 22, 23)]
        item = spark_days("BHP.AX", sydney, [45.0, 45.2, 45.4, 45.6], tz="Australia/Sydney", currency="AUD")
        recent = recent_of(item)
        tail = stored(sydney[:3], [45.0, 45.2, 45.4])
        quote = quote_for(sydney[3], 45.6, tz="Australia/Sydney", day_open=45.5, high=45.7, low=45.4)
        plan = plan_increment(tail, recent, quote, tz_name="Australia/Sydney", session_final=ALL_FINAL)
        self.assertEqual((plan.action, plan.new_day), (ACTION_NEW, date_to_day(sydney[3])))

    def test_pence_listing_keeps_its_unit_factor(self):
        item = spark_days("VOD.L", WEEK, [70.0, 70.5, 71.0, 71.5, 72.0], tz="Europe/London", currency="GBp")
        tail = stored(WEEK[:4], [70.0, 70.5, 71.0, 71.5])
        quote = quote_for(WEEK[4], 72.0, tz="Europe/London", day_open=71.6, high=72.3, low=71.4)
        plan = plan_increment(tail, recent_of(item), quote, tz_name="Europe/London", session_final=ALL_FINAL)
        self.assertEqual(plan.history.unit_factor, 0.01)
        self.assertEqual(plan.history.price_unit, "GBp")


if __name__ == "__main__":
    unittest.main()
