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
from traktien.providers.ecb import HISTORY_URL, EcbFxSource, parse_ecb_history_zip, parse_ecb_xml
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


# Aufbau wie eurofxref-hist.zip: eine CSV-Datei, neueste Zeile zuerst, „N/A“ für fehlende Kurse
HISTORY_CSV = (
    "Date,USD,JPY,GBP,CYP,\n"
    "2026-10-12,1.1012,161.20,0.84930,N/A,\n"
    "2026-10-09,1.0990,N/A,0.85010,N/A,\n"
    "2023-06-30,1.0866,157.16,0.85828,N/A,\n"
    "2001-01-02,0.9423,108.85,0.63220,0.57651,\n"
)


def history_zip(text: str = HISTORY_CSV, *, name: str = "eurofxref-hist.csv", extra: str | None = None) -> bytes:
    import io
    import zipfile

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(name, text)
        if extra:
            archive.writestr(extra, "x")
    return buffer.getvalue()


class FakeResponse:
    def __init__(self, status: int, content: bytes) -> None:
        self.status_code = status
        self.content = content
        self.headers: dict[str, str] = {}


class FakeHttp:
    def __init__(self, response: FakeResponse | Exception, history: FakeResponse | Exception | None = None) -> None:
        self.response = response
        self.history = history if history is not None else FakeResponse(404, b"")
        self.calls = 0
        self.history_calls = 0

    def get(self, url, **kwargs):
        if url == HISTORY_URL:
            self.history_calls += 1
            answer = self.history
        else:
            self.calls += 1
            answer = self.response
        if isinstance(answer, Exception):
            raise answer
        return answer


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

    def test_history_for_the_rule_is_loaded_once_and_kept(self) -> None:
        http = FakeHttp(FakeResponse(200, SAMPLE), FakeResponse(200, history_zip()))
        self.run_fx(EcbFxSource(http=http))
        self.assertEqual(http.history_calls, 1)
        stored = {(row["day"], row["currency"]) for row in repo.fx_rates_since(self.conn, 0)}
        self.assertIn((day(2023, 6, 30), "USD"), stored, "Kurse aus der Rückschau (3 Jahre) bleiben gespeichert")
        self.assertNotIn((day(2001, 1, 2), "USD"), stored, "ältere Kurse als nötig werden nicht übernommen")
        self.run_fx(EcbFxSource(http=http))
        self.assertEqual(http.history_calls, 1, "kein zweiter Abruf, solange die Rückschau abgedeckt ist")
        events = [e["message"] for e in self.conn.execute("SELECT message FROM run_event WHERE step = 'wechselkurse' ORDER BY id")]
        self.assertTrue(any("EZB-Kurshistorie ab" in m for m in events), events)

    def test_history_outage_only_shortens_the_review(self) -> None:
        rates = self.run_fx(EcbFxSource(http=FakeHttp(FakeResponse(200, SAMPLE), FakeResponse(503, b""))))
        self.assertIsNotNone(rates, "die 90-Tage-Kurse reichen für den Umsatzfilter")
        events = self.conn.execute("SELECT level, message FROM run_event WHERE step = 'wechselkurse' ORDER BY id").fetchall()
        self.assertTrue(any(e["level"] == "WARN" and "Kurshistorie nicht abrufbar" in e["message"] for e in events))


class EcbHistoryParserTests(unittest.TestCase):
    def test_parses_csv_in_zip_skips_na_and_filters_old_days(self) -> None:
        rows = parse_ecb_history_zip(history_zip(), first_day=day(2023, 1, 1))
        self.assertIn((day(2026, 10, 12), "USD", 1.1012), rows)
        self.assertIn((day(2026, 10, 9), "GBP", 0.8501), rows)
        self.assertNotIn("JPY", {c for d, c, _ in rows if d == day(2026, 10, 9)}, "„N/A“ ist kein Kurs")
        self.assertFalse(any(c == "CYP" for _, c, _ in rows))
        self.assertTrue(all(d >= day(2023, 1, 1) for d, _, _ in rows))
        everything = parse_ecb_history_zip(history_zip())
        self.assertIn((day(2001, 1, 2), "CYP", 0.57651), everything)

    def test_rejects_unexpected_archives(self) -> None:
        with self.assertRaises(ProviderError):
            parse_ecb_history_zip(b"kein zip")
        with self.assertRaises(ProviderError):
            parse_ecb_history_zip(history_zip(extra="zweite.csv"))
        with self.assertRaises(ProviderError):
            parse_ecb_history_zip(history_zip(name="kurse.txt"))
        with self.assertRaises(ProviderError):
            parse_ecb_history_zip(history_zip("Datum;USD\n2026-10-12;1.1\n"))

    def test_fetch_history_reports_http_errors(self) -> None:
        source = EcbFxSource(http=FakeHttp(FakeResponse(200, SAMPLE), FakeResponse(500, b"")))
        with self.assertRaises(ProviderError):
            source.fetch_history(day(2023, 1, 1))
        ok = EcbFxSource(http=FakeHttp(FakeResponse(200, SAMPLE), FakeResponse(200, history_zip()))).fetch_history(day(2026, 10, 1))
        self.assertEqual({d for d, _, _ in ok.rows}, {day(2026, 10, 9), day(2026, 10, 12)})
        self.assertTrue(ok.source.startswith("EZB"))


if __name__ == "__main__":
    unittest.main()
