"""EZB-Referenzkurse: Parser, Sicherheitsprüfung und Ablage im täglichen Lauf (ohne Netz)."""

from __future__ import annotations

import dataclasses
import shutil
import tempfile
import unittest
from pathlib import Path

from traktien.analytics.fx import FxRates
from traktien.config import load_method_config, load_pipeline_config
from traktien.jobs.daily import DailyRun, RunOptions
from traktien.jobs.sources import demo_sources
from traktien.providers.base import ProviderError
from traktien.providers.ecb import EcbFxSource, parse_ecb_xml
from traktien.providers.exchanges import load_exchange_table
from traktien.store import repo
from traktien.store.db import connect
from tests.helpers import day

# Aufbau wie die echte Datei eurofxref-hist-90d.xml (gekürzt, Werte synthetisch)
SAMPLE = b"""<?xml version="1.0" encoding="UTF-8"?>
<gesmes:Envelope xmlns:gesmes="http://www.gesmes.org/xml/2002-08-01" xmlns="http://www.ecb.int/vocabulary/2002-08-01/eurofxref">
  <gesmes:subject>Reference rates</gesmes:subject>
  <gesmes:Sender><gesmes:name>European Central Bank</gesmes:name></gesmes:Sender>
  <Cube>
    <Cube time="2026-10-12">
      <Cube currency="USD" rate="1.1012"/>
      <Cube currency="JPY" rate="161.20"/>
      <Cube currency="GBP" rate="0.84930"/>
      <Cube currency="HKD" rate="8.5600"/>
    </Cube>
    <Cube time="2026-10-09">
      <Cube currency="USD" rate="1.0990"/>
      <Cube currency="GBP" rate="0.85010"/>
    </Cube>
  </Cube>
</gesmes:Envelope>
"""


class FakeResponse:
    def __init__(self, status: int, content: bytes) -> None:
        self.status_code = status
        self.content = content
        self.headers: dict[str, str] = {}


class FakeHttp:
    def __init__(self, response: FakeResponse | Exception) -> None:
        self.response = response
        self.calls = 0

    def get(self, url, **kwargs):
        self.calls += 1
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


class EcbParserTests(unittest.TestCase):
    def test_parses_days_currencies_and_rates(self) -> None:
        rows = parse_ecb_xml(SAMPLE)
        self.assertIn((day(2026, 10, 12), "USD", 1.1012), rows)
        self.assertIn((day(2026, 10, 9), "GBP", 0.8501), rows)
        self.assertEqual(len(rows), 6)
        rates = FxRates.from_rows(rows, source="EZB", url=None, fetched_at=None, max_age_days=5)
        usd_per_gbp, used = rates.usd_per_unit("GBP", day(2026, 10, 12))
        self.assertAlmostEqual(usd_per_gbp, 1.1012 / 0.8493)
        self.assertEqual(used, day(2026, 10, 12))
        # Wochenende: Kurs vom Freitag
        self.assertEqual(rates.usd_per_unit("GBP", day(2026, 10, 11))[1], day(2026, 10, 9))
        self.assertEqual(rates.usd_per_unit("EUR", day(2026, 10, 12))[0], 1.1012)

    def test_rejects_entities_doctype_and_garbage(self) -> None:
        evil = b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "aaaa">]><x>&a;</x>'
        with self.assertRaises(ProviderError):
            parse_ecb_xml(evil)
        with self.assertRaises(ProviderError):
            parse_ecb_xml(b"<html>Fehler</html>")
        with self.assertRaises(ProviderError):
            parse_ecb_xml(b"kein xml")
        without_usd = SAMPLE.replace(b'currency="USD"', b'currency="CHF"')
        with self.assertRaises(ProviderError):
            parse_ecb_xml(without_usd)

    def test_source_reports_http_errors(self) -> None:
        source = EcbFxSource(http=FakeHttp(FakeResponse(503, b"")))
        with self.assertRaises(ProviderError):
            source.fetch()
        fetched = EcbFxSource(http=FakeHttp(FakeResponse(200, SAMPLE))).fetch()
        self.assertEqual(len(fetched.rows), 6)
        self.assertTrue(fetched.fetched_at.endswith("Z"))


class DailyRunFxTests(unittest.TestCase):
    """Wechselkursschritt im Lauf: Abruf sichern, bei Ausfall gespeicherte Kurse verwenden."""

    def setUp(self) -> None:
        self.dir = Path(tempfile.mkdtemp(prefix="fx-"))
        self.conn = connect(self.dir / "state.sqlite")

    def tearDown(self) -> None:
        self.conn.close()
        shutil.rmtree(self.dir, ignore_errors=True)

    def run_fx(self, source):
        sources = dataclasses.replace(demo_sources(), fx=source)
        run = DailyRun(self.conn, self.dir, sources, load_method_config(), load_pipeline_config(), load_exchange_table(), None, RunOptions())
        self.runs = getattr(self, "runs", 0) + 1
        run.run_id = f"test-lauf-{self.runs}"
        repo.create_run(self.conn, run.run_id, trigger="manuell", planned_start=None, attempt=1, versions=run.versions, data_mode="demo")
        return run.step_fx(day(2026, 10, 12))

    def test_fetch_is_stored_and_used(self) -> None:
        rates = self.run_fx(EcbFxSource(http=FakeHttp(FakeResponse(200, SAMPLE))))
        self.assertIsNotNone(rates)
        self.assertEqual(rates.last_day, day(2026, 10, 12))
        self.assertTrue(rates.source.startswith("EZB"))
        stored = repo.fx_rates_since(self.conn, day(2026, 10, 1))
        self.assertEqual(len(stored), 6)

    def test_outage_falls_back_to_stored_rates_and_logs_warning(self) -> None:
        self.run_fx(EcbFxSource(http=FakeHttp(FakeResponse(200, SAMPLE))))
        rates = self.run_fx(EcbFxSource(http=FakeHttp(ConnectionError("Netz weg"))))
        self.assertIsNotNone(rates)
        self.assertEqual(rates.last_day, day(2026, 10, 12))
        events = self.conn.execute("SELECT level, message FROM run_event WHERE step = 'wechselkurse' ORDER BY id").fetchall()
        self.assertTrue(any(e["level"] == "WARN" and "gespeicherte Kurse" in e["message"] for e in events))

    def test_no_rates_at_all(self) -> None:
        self.assertIsNone(self.run_fx(EcbFxSource(http=FakeHttp(FakeResponse(500, b"")))))


if __name__ == "__main__":
    unittest.main()
