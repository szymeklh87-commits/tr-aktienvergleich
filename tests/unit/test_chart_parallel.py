"""Chart-Abruf des täglichen Laufs gleichzeitig über zwei Hosts (ab 1.17) – SYNTHETISCHE Antworten, kein Netz.

Geprüft wird, was die Umstellung gleichwertig macht: dieselben Kursreihen in derselben Reihenfolge wie nacheinander,
Fehler je Notierung an derselben Stelle, beide Hosts im Wechsel, und bei einer Drosselung (HTTP 429) zurück auf den
bisherigen Weg (einzeln, erster Host) statt Abbruch – erst eine Drosselung auch dort endet mit ``ProviderThrottled``.
"""

from __future__ import annotations

import json
import threading
import unittest

import numpy as np

from traktien.jobs.daily import DailyRun
from traktien.providers.base import HistoryFetchStats, HistoryJob, NoDataError, ProviderThrottled, fetch_histories_sequential
from traktien.providers.http import HttpClient
from traktien.providers.yahoo import BASE, CHART_HOSTS, YahooProvider
from tests.unit.test_providers import FakeResponse, chart_payload


def payload_for(symbol: str) -> bytes:
    """Chart-Antwort je Symbol mit eigenen Kursen (aus dem Namen abgeleitet), sonst wie ``chart_payload``."""
    base = chart_payload()
    k = sum(ord(c) for c in symbol) % 97 + 1
    quote = base["chart"]["result"][0]["indicators"]["quote"][0]
    quote["close"] = [None if v is None else v + k for v in quote["close"]]
    quote["open"] = quote["high"] = quote["low"] = quote["close"]
    base["chart"]["result"][0]["indicators"]["adjclose"][0]["adjclose"] = list(quote["close"])
    return json.dumps(base).encode()


class ChartSession:
    """Antwortet je Symbol; „UNBEKANNT*“ mit 404; ``throttle_from``: ab dem n-ten Abruf HTTP 429 (nur ``throttle_hosts``)."""

    def __init__(self, *, throttle_from: int | None = None, throttle_hosts: tuple[str, ...] = CHART_HOSTS):
        self.lock = threading.Lock()
        self.calls: list[tuple[str, str]] = []
        self.throttle_from = throttle_from
        self.throttle_hosts = throttle_hosts
        self.count = 0

    def request(self, method, url, params=None, **kwargs):
        host = url.split("/v8/")[0]
        symbol = url.rsplit("/", 1)[1]
        with self.lock:
            self.count += 1
            n = self.count
            self.calls.append((host, symbol))
        if self.throttle_from is not None and n >= self.throttle_from and host in self.throttle_hosts:
            return FakeResponse(429)
        if symbol.startswith("UNBEKANNT"):
            return FakeResponse(404)
        return FakeResponse(200, payload_for(symbol))


def provider(session, workers=1):
    http = HttpClient(session=session, sleep=lambda s: None, max_retries=1, min_interval={"query2.finance.yahoo.com": 0.0, "query1.finance.yahoo.com": 0.0})
    return YahooProvider(http)


def jobs(n=60, unknown=(7, 33)):
    return [HistoryJob(f"UNBEKANNT{k}.DE" if k in unknown else f"T{k}.DE", 20000, 20010) for k in range(n)]


def summary(outcomes):
    out = []
    for k, item in outcomes:
        if isinstance(item, Exception):
            out.append((k, type(item).__name__))
        else:
            out.append((k, item.days.tolist(), item.close.tolist(), np.nan_to_num(item.volume, nan=-1).tolist()))
    return out


class ParallelChartTests(unittest.TestCase):
    def test_parallel_equals_sequential_in_order_and_alternates_hosts(self):
        seq_session, par_session = ChartSession(), ChartSession()
        sequential = summary(provider(seq_session).fetch_histories(jobs(), workers=1))
        stats = HistoryFetchStats()
        parallel = summary(provider(par_session).fetch_histories(jobs(), workers=4, interval_s=0.0, stats=stats))
        self.assertEqual(parallel, sequential, "dieselben Kursreihen und Fehler an derselben Stelle")
        self.assertEqual([k for k, *_ in parallel], list(range(60)))
        self.assertEqual((parallel[7][1], parallel[33][1]), ("NoDataError", "NoDataError"))
        self.assertEqual({h for h, _ in seq_session.calls}, {BASE}, "nacheinander wie bisher nur über den ersten Host")
        hosts = [h for h, _ in par_session.calls]
        self.assertEqual(hosts.count(CHART_HOSTS[0]), 30)
        self.assertEqual(hosts.count(CHART_HOSTS[1]), 30)
        self.assertEqual(sorted(s for _, s in par_session.calls), sorted(s for _, s in seq_session.calls), "dieselben Abrufe, nur gleichzeitig")
        self.assertEqual((stats.workers, stats.hosts, stats.requests, stats.parallel, stats.careful, stats.throttled_after), (4, 2, 60, 60, 0, None))

    def test_throttling_falls_back_to_the_old_way_without_losing_or_reordering_results(self):
        expected = summary(provider(ChartSession()).fetch_histories(jobs(), workers=1))
        session = ChartSession(throttle_from=12, throttle_hosts=(CHART_HOSTS[1],))  # nur der zweite Host drosselt
        stats = HistoryFetchStats()
        got = summary(provider(session).fetch_histories(jobs(), workers=4, interval_s=0.0, stats=stats))
        self.assertEqual(got, expected, "vollständig und in derselben Reihenfolge")
        self.assertIsNotNone(stats.throttled_after)
        self.assertGreater(stats.careful, 0)
        self.assertEqual(stats.parallel + stats.careful, 60)
        self.assertGreater(stats.http_429, 0)
        # Nach dem Umschalten gehen neue Abrufe nur noch über den ersten Host
        tail = session.calls[-stats.careful:]
        self.assertEqual({h for h, _ in tail}, {BASE})

    def test_throttling_on_the_old_way_too_ends_with_provider_throttled(self):
        session = ChartSession(throttle_from=10)  # beide Hosts drosseln
        outcomes = provider(session).fetch_histories(jobs(), workers=3, interval_s=0.0)
        kinds = []
        for k, item in outcomes:
            kinds.append(type(item).__name__)
            if isinstance(item, ProviderThrottled):
                break
        outcomes.close()
        self.assertEqual(kinds[-1], "ProviderThrottled")
        self.assertLess(len(kinds), 60, "der Lauf unterbricht – Checkpoint wie bisher")

    def test_early_stop_closes_without_waiting_for_everything(self):
        session = ChartSession()
        outcomes = provider(session).fetch_histories(jobs(400), workers=4, interval_s=0.0, window=16)
        first = [next(outcomes) for _ in range(5)]
        outcomes.close()
        self.assertEqual([k for k, _ in first], [0, 1, 2, 3, 4])
        self.assertLess(len(session.calls), 400, "höchstens das Fenster läuft voraus")

    def test_sequential_fallback_for_providers_without_parallel_fetch(self):
        class Plain:
            def fetch_history(self, symbol, start_day, end_day, *, session_final=None):
                if symbol.startswith("UNBEKANNT"):
                    raise NoDataError(symbol)
                return provider(ChartSession()).fetch_history(symbol, start_day, end_day)

        stats = HistoryFetchStats()
        got = summary(fetch_histories_sequential(Plain(), jobs(10), stats))
        self.assertEqual(got, summary(provider(ChartSession()).fetch_histories(jobs(10))))
        self.assertEqual(stats.requests, 10)

    def test_protocol_line_names_speed_and_fallback(self):
        stats = HistoryFetchStats(workers=4, hosts=2, interval_s=0.25, requests=11000, parallel=10000, careful=1000, throttled_after=10000, http_429=3, seconds=1500)
        text = DailyRun.fetch_stats_text(stats)
        self.assertIn("11000 Abrufe in 1500 s (7.3 je Sekunde; 4 gleichzeitig über 2 Hosts, Abstand 0.25 s je Host)", text)
        self.assertIn("Drosselung (HTTP 429) nach 10000 Abrufen – danach 1000 einzeln", text)
        self.assertIn("nacheinander", DailyRun.fetch_stats_text(HistoryFetchStats(requests=5, seconds=2)))


if __name__ == "__main__":
    unittest.main()
