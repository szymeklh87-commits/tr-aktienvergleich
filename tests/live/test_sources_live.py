"""Machbarkeitsprüfung der echten Datenquellen (Netzwerk nötig).

Nur mit ``TR_LIVE=1`` aktiv – gedacht für den manuellen Workflow „Datenquellen prüfen“ in
GitHub Actions. Prüft mit wenigen, sparsamen Abrufen:

* Trade-Republic-Instrumentenliste (PDF): erreichbar, Aktienabschnitt erkannt, plausible Größe.
* OpenFIGI: ISIN → Börsennotierungen.
* Yahoo Finance (inoffiziell): Tageskurse und ISIN-Suche.
* EODHD (nur mit ``EODHD_API_KEY``): Tageskurse.

Das Ergebnis wird zusätzlich als JSON ausgegeben (``TR_LIVE_REPORT=<Datei>``).
"""

from __future__ import annotations

import datetime as dt
import json
import os
import unittest

from traktien.config import load_pipeline_config
from traktien.providers.exchanges import load_exchange_table
from traktien.providers.http import HttpClient
from traktien.providers.openfigi import OpenFigiClient, candidates_from_figi
from traktien.providers.tr_universe import extract_lines, parse_lines, pdf_metadata
from traktien.providers.yahoo import YahooProvider
from traktien.util.timeutil import date_to_day, day_to_date

LIVE = os.environ.get("TR_LIVE") == "1"
REPORT: dict = {}
KNOWN = ["US0378331005", "DE0007164600", "DE0005557508"]  # Apple, SAP, Deutsche Telekom – nur Erreichbarkeitsprobe


def tearDownModule() -> None:
    path = os.environ.get("TR_LIVE_REPORT")
    if path and REPORT:
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(REPORT, handle, ensure_ascii=False, indent=2)
    if REPORT:
        print(json.dumps(REPORT, ensure_ascii=False, indent=2))


@unittest.skipUnless(LIVE, "Live-Prüfung nur mit TR_LIVE=1")
class SourcesLiveTest(unittest.TestCase):
    def test_tr_universe_pdf(self) -> None:
        pipeline = load_pipeline_config()
        url = pipeline.get("universum.url")
        response = HttpClient(timeout=120).get(url)
        self.assertEqual(response.status_code, 200, f"PDF nicht erreichbar: {url}")
        self.assertTrue(response.content.startswith(b"%PDF"), "Antwort ist kein PDF")
        result = parse_lines(extract_lines(response.content))
        meta = pdf_metadata(response.content)
        REPORT["tr_universum"] = {
            "url": url,
            "bytes": len(response.content),
            "last_modified": response.headers.get("last-modified") or response.headers.get("Last-Modified"),
            "pdf": meta,
            "abschnitte": result.sections[:20],
            "aktienabschnitt_gefunden": result.stock_section_found,
            "isins": result.count,
            "ungueltige_isins": result.invalid_isins,
            "doppelte": result.duplicates,
            "fortsetzungszeilen": result.continuation_lines,
            "unerkannte_zeilen_beispiele": result.unparsed_lines[:10],
            "bekannte_isins_gefunden": [isin for isin in KNOWN if any(e.isin == isin for e in result.entries)],
        }
        self.assertTrue(result.stock_section_found, "Aktienabschnitt nicht erkannt – Parser anpassen")
        self.assertGreaterEqual(result.count, int(pipeline.get("universum.min_eintraege", 1000)))
        self.assertLessEqual(result.invalid_isins, max(5, result.count // 50))

    def test_openfigi_mapping(self) -> None:
        table = load_exchange_table()
        mapped = OpenFigiClient().map_isins(KNOWN[:2])
        report = {}
        for isin, item in mapped.items():
            candidates = candidates_from_figi(isin, item, table)
            report[isin] = [f"{c.exchange_key}:{c.provider_symbol}" for c in candidates[:8]]
            self.assertTrue(item.get("data"), f"OpenFIGI ohne Treffer für {isin}: {item}")
            self.assertTrue(candidates, f"Keine unterstützte Börse für {isin}")
        REPORT["openfigi"] = report

    def test_yahoo_history_and_search(self) -> None:
        provider = YahooProvider()
        end = date_to_day(dt.date.today())
        history = provider.fetch_history("AAPL", end - 45, end)
        self.assertGreaterEqual(len(history), 20, "Yahoo lieferte zu wenige Tageskurse")
        table = load_exchange_table()
        candidates = provider.search("US0378331005", table)
        REPORT["yahoo"] = {
            "aapl_tageskurse": len(history),
            "letzter_tag": day_to_date(int(history.days[-1])).isoformat(),
            "suche_isin": [c.provider_symbol for c in candidates[:8]],
            "hinweis": "Inoffizielle Schnittstelle ohne Vertrag; Verfügbarkeit und Nutzungsbedingungen können sich ändern.",
        }
        self.assertTrue(any(c.provider_symbol == "AAPL" for c in candidates), "ISIN-Suche fand AAPL nicht")

    @unittest.skipUnless(os.environ.get("EODHD_API_KEY"), "EODHD_API_KEY nicht gesetzt")
    def test_eodhd_history(self) -> None:
        from traktien.providers.eodhd import EodhdProvider

        end = date_to_day(dt.date.today())
        history = EodhdProvider().fetch_history("AAPL.US", end - 45, end)
        REPORT["eodhd"] = {"aapl_tageskurse": len(history)}
        self.assertGreaterEqual(len(history), 20)


if __name__ == "__main__":
    unittest.main()
