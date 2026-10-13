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

    def test_yahoo_delivers_cutoff_session_per_market(self) -> None:
        """Liefert Yahoo je Markt den Kurs des gemeinsamen Kursstichtags (wie im täglichen Lauf)?

        Ein großer, liquider Wert je Börse. Je Abfragevariante (Host query2/query1, Zeitraum über
        period1/period2 oder „range=1mo“) werden die letzten Tageskerzen gemeldet: Sitzungstag,
        Uhrzeit (UTC), ob ein Schlusskurs geliefert wurde und ob die Sitzung abgeschlossen ist.
        Keine Kurse im Bericht. Bestanden, wenn die Variante des täglichen Laufs den Stichtag liefert.
        """
        from traktien.jobs.cutoff import determine_cutoff, session_final_checker
        from traktien.providers.calendars import ExchangeCalendarsProvider
        from traktien.providers.yahoo import parse_chart
        from traktien.util.timeutil import session_date_from_timestamp

        symbols = [
            "SAP.DE", "SAP.F", "MC.PA", "NESN.SW", "HSBA.L", "ITX.MC", "ABI.BR", "NOVO-B.CO",
            "NOKIA.HE", "EQNR.OL", "CEZ.PR", "TAL1T.TL", "0700.HK", "600519.SS", "AAPL", "KO", "RY.TO", "BHP.AX",
        ]
        variants = {
            "query2": {"host": "https://query2.finance.yahoo.com"},  # wie der tägliche Lauf
            "query1": {"host": "https://query1.finance.yahoo.com"},
            "range": {"host": "https://query2.finance.yahoo.com", "range_": "1mo"},
        }
        table = load_exchange_table()
        calendars = ExchangeCalendarsProvider()
        provider = YahooProvider()
        now = dt.datetime.now(tz=dt.timezone.utc)
        codes = {}
        for symbol in symbols:
            exchange = table.exchange_for_yahoo_symbol(symbol)
            if exchange is not None and calendars.available(exchange.calendar):
                codes[symbol] = exchange.calendar
        cutoff = determine_cutoff(set(codes.values()), calendars, now, grace_minutes=60)
        D = cutoff.cutoff_day
        report: dict = {"jetzt_utc": now.isoformat(timespec="minutes"), "stichtag": day_to_date(D).isoformat(), "werte": {}}
        missing = []
        for symbol, code in codes.items():
            final = session_final_checker(calendars, code, now, 60)
            entry: dict = {"kalender": code, "sitzung_am_stichtag": calendars.session_close_utc(code, D) is not None, "varianten": {}}
            for name, variant in variants.items():
                try:
                    payload = provider.chart(symbol, D - 20, D + 3, **variant)
                    result = payload["chart"]["result"][0]
                    tz_name = (result.get("meta") or {}).get("exchangeTimezoneName") or "UTC"
                    stamps = result.get("timestamp") or []
                    closes = ((result.get("indicators") or {}).get("quote") or [{}])[0].get("close") or []
                    rows = []
                    for i, ts in enumerate(stamps[-5:], start=max(0, len(stamps) - 5)):
                        day = date_to_day(session_date_from_timestamp(ts, tz_name))
                        rows.append({
                            "tag": day_to_date(day).isoformat(),
                            "zeit_utc": dt.datetime.fromtimestamp(ts, tz=dt.timezone.utc).strftime("%H:%M"),
                            "schlusskurs": i < len(closes) and closes[i] is not None,
                            "abgeschlossen": bool(final(day)),
                        })
                    days = [int(d) for d in parse_chart(payload, symbol, session_final=final).days]
                    entry["zeitzone"] = tz_name
                    entry["varianten"][name] = {"letzte_kerzen": rows, "stichtag_vorhanden": D in days}
                except Exception as exc:  # Bericht statt Abbruch: die übrigen Werte sollen sichtbar bleiben
                    entry["varianten"][name] = {"fehler": f"{type(exc).__name__}: {exc}"[:200]}
            if entry["sitzung_am_stichtag"] and not entry["varianten"]["query2"].get("stichtag_vorhanden"):
                missing.append(symbol)
                # Gibt es für den Stichtag wenigstens Stundenkerzen? (Grundlage für eine mögliche,
                # gekennzeichnete Rekonstruktion – nur Anzahl und Uhrzeit, keine Kurse)
                try:
                    hourly = provider.chart(symbol, D, D, interval="1h")["chart"]["result"][0]
                    tz_name = (hourly.get("meta") or {}).get("exchangeTimezoneName") or "UTC"
                    closes = ((hourly.get("indicators") or {}).get("quote") or [{}])[0].get("close") or []
                    on_day = [
                        ts for i, ts in enumerate(hourly.get("timestamp") or [])
                        if date_to_day(session_date_from_timestamp(ts, tz_name)) == D and i < len(closes) and closes[i] is not None
                    ]
                    entry["stunden_am_stichtag"] = {
                        "anzahl": len(on_day),
                        "letzte_utc": dt.datetime.fromtimestamp(max(on_day), tz=dt.timezone.utc).strftime("%H:%M") if on_day else None,
                    }
                except Exception as exc:  # nur Bericht
                    entry["stunden_am_stichtag"] = {"fehler": f"{type(exc).__name__}: {exc}"[:200]}
            report["werte"][symbol] = entry
        REPORT["yahoo_stichtag"] = report
        self.assertEqual(missing, [], f"Stichtagskurs {day_to_date(D)} fehlt bei: {', '.join(missing)}")

    @unittest.skipUnless(os.environ.get("EODHD_API_KEY"), "EODHD_API_KEY nicht gesetzt")
    def test_eodhd_history(self) -> None:
        from traktien.providers.eodhd import EodhdProvider

        end = date_to_day(dt.date.today())
        history = EodhdProvider().fetch_history("AAPL.US", end - 45, end)
        REPORT["eodhd"] = {"aapl_tageskurse": len(history)}
        self.assertGreaterEqual(len(history), 20)


if __name__ == "__main__":
    unittest.main()
