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
                    parsed = parse_chart(payload, symbol, session_final=final)
                    days = [int(d) for d in parsed.days]
                    entry["zeitzone"] = tz_name
                    entry["varianten"][name] = {"letzte_kerzen": rows, "stichtag_vorhanden": D in days, "aus_kursmeldung": D in parsed.close_from_quote}
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

    def test_yahoo_quote_matches_daily_close(self) -> None:
        """Stimmt der letzte gemeldete Kurs nach Börsenschluss („regularMarketPrice“) mit dem Schlusskurs überein?

        Grundlage für die Absicherung bei fehlender Tageskerze (ab 1.6). Je Wert: Handelstag der Kursmeldung,
        ob die Tageskerze dieses Tages einen Schlusskurs hat, Abweichung der Kursmeldung zur Tageskerze und
        zur letzten Stundenkerze in Basispunkten (keine Kurse) sowie ob Tageshoch, -tief und Umsatz gemeldet
        werden. Nur Bericht; bestanden, wenn keine Abweichung zur vorhandenen Tageskerze über 5 Basispunkte liegt."""
        from traktien.providers.calendars import ExchangeCalendarsProvider
        from traktien.util.timeutil import session_date_from_timestamp

        symbols = [
            "SAP.DE", "SAP.F", "MC.PA", "NESN.SW", "HSBA.L", "ITX.MC", "ABI.BR", "NOVO-B.CO", "NOKIA.HE", "EQNR.OL", "CEZ.PR",
            "PKO.WA", "ASML.AS", "TAL1T.TL", "AAPL", "KO", "RY.TO", "0700.HK", "7203.T", "BHP.AX",
        ]
        table = load_exchange_table()
        calendars = ExchangeCalendarsProvider()
        provider = YahooProvider()
        report: dict = {}
        too_far = []
        for symbol in symbols:
            entry: dict = {}
            try:
                payload = provider.chart(symbol, date_to_day(dt.date.today()) - 8, date_to_day(dt.date.today()) + 2)
                result = payload["chart"]["result"][0]
                meta = result.get("meta") or {}
                tz_name = meta.get("exchangeTimezoneName") or "UTC"
                price, when = meta.get("regularMarketPrice"), meta.get("regularMarketTime")
                if price is None or when is None:
                    entry["meldung"] = "fehlt"
                    report[symbol] = entry
                    continue
                day = date_to_day(session_date_from_timestamp(int(when), tz_name))
                exchange = table.exchange_for_yahoo_symbol(symbol)
                close_utc = calendars.session_close_utc(exchange.calendar, day) if exchange is not None and calendars.available(exchange.calendar) else None
                entry["handelstag"] = day_to_date(day).isoformat()
                entry["meldung_utc"] = dt.datetime.fromtimestamp(int(when), tz=dt.timezone.utc).strftime("%H:%M")
                entry["nach_schluss"] = None if close_utc is None else dt.datetime.fromtimestamp(int(when), tz=dt.timezone.utc) >= close_utc - dt.timedelta(minutes=1)
                entry["tageshoch_tief_umsatz"] = all(meta.get(k) is not None for k in ("regularMarketDayHigh", "regularMarketDayLow", "regularMarketVolume"))
                stamps = result.get("timestamp") or []
                closes = ((result.get("indicators") or {}).get("quote") or [{}])[0].get("close") or []
                candle = None
                for i, ts in enumerate(stamps):
                    if date_to_day(session_date_from_timestamp(ts, tz_name)) == day:
                        candle = closes[i] if i < len(closes) else None
                entry["tageskerze"] = "fehlt" if candle is None and day not in [date_to_day(session_date_from_timestamp(ts, tz_name)) for ts in stamps] else ("ohne Schlusskurs" if candle is None else "mit Schlusskurs")
                if candle:
                    bp = round((float(price) / float(candle) - 1.0) * 10000, 1)
                    entry["abweichung_tageskerze_bp"] = bp
                    if abs(bp) > 5:
                        too_far.append(symbol)
                hourly = provider.chart(symbol, day, day, interval="1h")["chart"]["result"][0]
                h_closes = ((hourly.get("indicators") or {}).get("quote") or [{}])[0].get("close") or []
                h_last = None
                for i, ts in enumerate(hourly.get("timestamp") or []):
                    if date_to_day(session_date_from_timestamp(ts, tz_name)) == day and i < len(h_closes) and h_closes[i] is not None:
                        h_last = h_closes[i]
                if h_last:
                    entry["abweichung_stundenkerze_bp"] = round((float(price) / float(h_last) - 1.0) * 10000, 1)
            except Exception as exc:  # Bericht statt Abbruch
                entry["fehler"] = f"{type(exc).__name__}: {exc}"[:160]
            report[symbol] = entry
        REPORT["yahoo_kursmeldung_schluss"] = report
        self.assertEqual(too_far, [], f"Kursmeldung weicht vom Tagesschluss ab: {too_far}")

    def test_yahoo_current_quotes_in_batches(self) -> None:
        """Zwischenstand (ab 1.6): Liefert die Sammelabfrage „spark“ aktuelle Kurse für Werte vieler Börsen?

        Bericht je Wert ohne Kurse: Variante, Zeitpunkt des letzten Kurses (UTC), Handelstag, ob Umsatz
        und Vortagesschluss gemeldet wurden, Währung. Bestanden, wenn mindestens 80 % der Werte einen
        Kurs haben."""
        from traktien.util.timeutil import day_to_date as to_date

        symbols = [
            "AAPL", "KO", "SAP.DE", "SAP.F", "MC.PA", "NESN.SW", "HSBA.L", "ITX.MC", "NOVO-B.CO", "EQNR.OL",
            "0700.HK", "600519.SS", "7203.T", "BHP.AX", "RY.TO", "TAL1T.TL", "CEZ.PR", "ABI.BR", "NOKIA.HE", "PKO.WA",
            "ASML.AS",
        ]
        result = YahooProvider().fetch_quotes(symbols, budget_s=120)
        werte = {}
        for symbol in symbols:
            quote = result.quotes.get(symbol)
            if quote is None:
                werte[symbol] = {"fehlt": result.missing.get(symbol, "?")}
                continue
            werte[symbol] = {
                "zeit_utc": quote.time_utc.strftime("%d.%m. %H:%M"),
                "handelstag": to_date(quote.session_day).isoformat(),
                "umsatz_gemeldet": quote.volume == quote.volume,
                "vortagesschluss_gemeldet": quote.previous_close == quote.previous_close,
                "waehrung": quote.currency,
                "zeitzone": quote.exchange_tz,
            }
        REPORT["yahoo_aktuelle_kurse"] = {
            "variante": result.endpoint,
            "abrufe": result.requests,
            "gedrosselt": result.throttled,
            "mit_kurs": len(result.quotes),
            "von": len(symbols),
            "werte": werte,
        }
        self.assertGreaterEqual(len(result.quotes), int(0.8 * len(symbols)), f"zu wenige aktuelle Kurse: {result.missing}")

    def test_yahoo_analyst_targets(self) -> None:
        """Potenzial (ab 1.6): Kursziele und Empfehlungen über „quoteSummary“ (mit Cookie und Crumb).

        Bericht ohne Werte: ob Cookie und Crumb funktionieren; je Wert, ob Kursziele (Ø, Median, hoch,
        tief), Anzahl Analysten und Empfehlungen geliefert wurden und in welcher Einheit der Kurs der
        Antwort im Vergleich zur Sammelabfrage steht (gleich, ×100, ÷100). Danach eine Serie von rund 50
        weiteren Abrufen, um Dauer und Drosselung zu sehen, und ob die Sammelabfrage „v7/quote“ mit Crumb
        funktioniert und welche Analysten-Felder sie hat (nur Feldnamen). Bestanden, wenn der Crumb
        funktioniert und mindestens die Hälfte der großen Werte Kursziele hat."""
        import time

        from traktien.providers.yahoo import BASE

        symbols = [
            "AAPL", "KO", "PDSB", "SAP.DE", "SAP.F", "MC.PA", "NESN.SW", "HSBA.L", "ITX.MC", "NOVO-B.CO", "EQNR.OL",
            "0700.HK", "600519.SS", "7203.T", "BHP.AX", "RY.TO", "ASML.AS", "CEZ.PR", "PKO.WA", "TAL1T.TL", "NOKIA.HE", "ABI.BR",
        ]
        big = ["AAPL", "KO", "SAP.DE", "MC.PA", "NESN.SW", "HSBA.L", "7203.T", "BHP.AX", "RY.TO", "ASML.AS"]
        provider = YahooProvider()
        report: dict = {"werte": {}}
        started = time.monotonic()
        try:
            provider.ensure_crumb()
            report["crumb"] = "ok"
            report["crumb_s"] = round(time.monotonic() - started, 1)
        except Exception as exc:  # Bericht statt Abbruch
            report["crumb"] = f"Fehler: {type(exc).__name__}: {exc}"[:200]
            REPORT["yahoo_analysten"] = report
            self.fail(f"Crumb nicht erhalten: {report['crumb']}")
        live = provider.fetch_quotes(symbols, budget_s=60).quotes

        def unit_of(view, symbol):
            q = live.get(symbol)
            if q is None or not (view.current_price > 0):
                return None
            ratio = view.current_price / q.price
            for label, factor in (("gleich", 1.0), ("×100", 100.0), ("÷100", 0.01)):
                if factor / 1.3 <= ratio <= factor * 1.3:
                    return label
            return "abweichend"

        def entry_of(view, symbol):
            ok = lambda x: x == x  # noqa: E731 – nan prüfen, ohne Werte zu melden
            return {
                "kursziele": view.analysts,
                "ziel_mittel": ok(view.target_mean), "ziel_median": ok(view.target_median),
                "ziel_hoch": ok(view.target_high), "ziel_tief": ok(view.target_low),
                "empfehlungen": view.ratings, "schluessel": view.rec_key, "monat": view.trend_period,
                "einheit": unit_of(view, symbol),
            }

        first = time.monotonic()
        for symbol in symbols:
            try:
                report["werte"][symbol] = entry_of(provider.analyst_view(symbol), symbol)
            except Exception as exc:  # Bericht statt Abbruch
                report["werte"][symbol] = {"fehler": f"{type(exc).__name__}: {exc}"[:160]}
        report["abrufe_s"] = round(time.monotonic() - first, 1)

        # Serie: wie verhält sich Yahoo bei vielen Einzelabrufen hintereinander (Dauer, Drosselung)?
        series = [
            "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "BRK-B", "JPM", "V", "UNH", "XOM", "JNJ", "WMT", "MA", "PG", "HD",
            "CVX", "MRK", "ABBV", "PEP", "AVGO", "COST", "ADBE", "MCD", "CSCO", "CRM", "TMO", "ACN", "ABT", "LIN", "DHR", "NKE",
            "TXN", "NEE", "PM", "ORCL", "AMD", "INTC", "QCOM", "IBM", "AMGN", "HON", "UPS", "CAT", "GS", "MS", "BA", "GE", "SBUX", "BLK",
        ]
        throttled_before = provider.http.stats.throttled
        retries_before = provider.http.stats.retries
        t0 = time.monotonic()
        counts = {"mit_kurszielen": 0, "ohne": 0, "fehler": 0}
        errors: list[str] = []
        for symbol in series:
            try:
                counts["mit_kurszielen" if provider.analyst_view(symbol).has_targets else "ohne"] += 1
            except Exception as exc:  # Bericht statt Abbruch
                counts["fehler"] += 1
                errors.append(f"{symbol}: {type(exc).__name__}")
                if "Throttled" in type(exc).__name__:
                    break
        report["serie"] = {
            **counts,
            "von": len(series),
            "sekunden": round(time.monotonic() - t0, 1),
            "drosselungen_429": provider.http.stats.throttled - throttled_before,
            "wiederholungen": provider.http.stats.retries - retries_before,
            "fehler_beispiele": errors[:5],
        }

        # Sammelabfrage v7/quote mit Crumb: funktioniert sie, und welche Analysten-Felder hat sie?
        try:
            response = provider.http.get(f"{BASE}/v7/finance/quote", params={"symbols": ",".join(symbols[:10]), "crumb": provider.ensure_crumb()})
            items = []
            if response.status_code == 200:
                items = ((response.json() or {}).get("quoteResponse") or {}).get("result") or []
            keys = sorted({k for item in items for k in item})
            words = ("analyst", "target", "recommend", "rating")
            report["v7_quote"] = {
                "status": response.status_code,
                "ergebnisse": len(items),
                "analystenfelder": [k for k in keys if any(w in k.lower() for w in words)],
                "kursfelder": [k for k in keys if k.startswith("regularMarket")][:16],
            }
        except Exception as exc:  # Bericht statt Abbruch
            report["v7_quote"] = {"fehler": f"{type(exc).__name__}: {exc}"[:160]}
        REPORT["yahoo_analysten"] = report
        with_targets = [s for s in big if (report["werte"].get(s) or {}).get("kursziele", 0) > 0]
        self.assertGreaterEqual(len(with_targets), len(big) // 2, f"zu wenige Werte mit Kurszielen: {with_targets}")

    def test_more_analyst_sources(self) -> None:
        """Weitere Quellen für Kursziele, Bewertung und Stimmung (ab 1.6) – nur Verfügbarkeit und Feldnamen,
        keine Werte (das Protokoll ist öffentlich):

        * Yahoo „upgradeDowngradeHistory“: Einzelurteile je Analystenhaus (mit Kursziel?)
        * Yahoo „earningsTrend“ und „assetProfile“: Gewinnschätzungen, Branche
        * Yahoo „insights“: Bewertung (unter-/überbewertet), Ausblick, Research-Empfehlung
        * Nasdaq (nur US, inoffiziell): Kursziel-Konsens und Empfehlungen
        * onvista (inoffiziell): Analysten-Angaben zu deutschen Aktien?
        * Stocktwits: Stimmung der Community (bullish/bearish)

        Nur Bericht – Ausfälle einzelner Quellen lassen die Prüfung nicht scheitern."""
        import time

        from traktien.providers.yahoo import BASE

        symbols = ["AAPL", "PDSB", "SAP.DE", "MC.PA", "HSBA.L", "7203.T", "0700.HK", "ASML.AS"]
        provider = YahooProvider()
        report: dict = {}
        crumb = provider.ensure_crumb()
        words = ("analys", "target", "rating", "recommend", "kursziel", "consensus", "sentiment")

        def keys_with_words(value, prefix="", depth=0) -> list[str]:
            found: list[str] = []
            if depth > 4:
                return found
            if isinstance(value, dict):
                for key, item in value.items():
                    path = f"{prefix}.{key}" if prefix else str(key)
                    if any(w in str(key).lower() for w in words):
                        found.append(path)
                    found.extend(keys_with_words(item, path, depth + 1))
            elif isinstance(value, list) and value:
                found.extend(keys_with_words(value[0], prefix + "[]", depth + 1))
            return found[:20]

        modules = {}
        for symbol in symbols:
            entry: dict = {}
            try:
                r = provider.http.get(
                    f"{BASE}/v10/finance/quoteSummary/{symbol}",
                    params={"modules": "upgradeDowngradeHistory,earningsTrend,assetProfile", "crumb": crumb, "formatted": "false"},
                )
                entry["status"] = r.status_code
                if r.status_code == 200:
                    res = ((r.json().get("quoteSummary") or {}).get("result") or [{}])[0] or {}
                    hist = (res.get("upgradeDowngradeHistory") or {}).get("history") or []
                    recent = [h for h in hist if (h.get("epochGradeDate") or 0) >= time.time() - 180 * 86400]
                    entry["urteile_180_tage"] = len(recent)
                    entry["davon_mit_kursziel"] = sum(1 for h in recent if h.get("currentPriceTarget"))
                    entry["felder"] = sorted({k for h in hist[:10] for k in h})
                    trend = (res.get("earningsTrend") or {}).get("trend") or []
                    entry["gewinnschaetzung_zeitraeume"] = [t.get("period") for t in trend if t.get("growth") is not None]
                    entry["branche"] = bool((res.get("assetProfile") or {}).get("sector"))
            except Exception as exc:  # Bericht statt Abbruch
                entry["fehler"] = f"{type(exc).__name__}: {exc}"[:160]
            modules[symbol] = entry
        report["yahoo_module"] = modules

        insights = {}
        for symbol in symbols:
            entry = {}
            try:
                r = provider.http.get(f"{BASE}/ws/insights/v2/finance/insights", params={"symbol": symbol, "crumb": crumb})
                entry["status"] = r.status_code
                if r.status_code == 200:
                    res = (r.json().get("finance") or {}).get("result") or {}
                    info = res.get("instrumentInfo") or {}
                    valuation = info.get("valuation") or {}
                    tech = info.get("technicalEvents") or {}
                    rec = res.get("recommendation") or {}
                    entry["bewertung"] = bool(valuation.get("description"))
                    entry["bewertung_quelle"] = valuation.get("provider")
                    entry["bewertung_felder"] = sorted(valuation)
                    entry["ausblick"] = sum(1 for k in ("shortTermOutlook", "intermediateTermOutlook", "longTermOutlook") if (tech.get(k) or {}).get("direction"))
                    entry["research_quelle"] = rec.get("provider")
                    entry["research_kursziel"] = rec.get("targetPrice") is not None
            except Exception as exc:  # Bericht statt Abbruch
                entry["fehler"] = f"{type(exc).__name__}: {exc}"[:160]
            insights[symbol] = entry
        report["yahoo_insights"] = insights

        other = HttpClient(impersonate="chrome", max_retries=1, timeout=15, min_interval={"api.nasdaq.com": 0.5, "api.stocktwits.com": 1.0, "api.onvista.de": 0.5})
        nasdaq = {}
        for symbol in ("AAPL", "PDSB"):
            for kind in ("targetprice", "ratings"):
                entry = {}
                try:
                    r = other.get(
                        f"https://api.nasdaq.com/api/analyst/{symbol}/{kind}",
                        headers={"Accept": "application/json, text/plain, */*", "Origin": "https://www.nasdaq.com", "Referer": "https://www.nasdaq.com/"},
                    )
                    entry["status"] = r.status_code
                    if r.status_code == 200:
                        data = (r.json() or {}).get("data")
                        entry["felder"] = sorted(data)[:12] if isinstance(data, dict) else type(data).__name__
                        entry["analystenfelder"] = keys_with_words(data)
                except Exception as exc:  # Bericht statt Abbruch
                    entry["fehler"] = f"{type(exc).__name__}: {exc}"[:160]
                nasdaq[f"{symbol}/{kind}"] = entry
        report["nasdaq"] = nasdaq

        onvista = {}
        for isin in ("DE0007164600", "US0378331005"):
            entry = {}
            try:
                r = other.get(f"https://api.onvista.de/api/v1/stocks/ISIN:{isin}/snapshot")
                entry["status"] = r.status_code
                if r.status_code == 200:
                    data = r.json() or {}
                    entry["felder"] = sorted(data)[:20] if isinstance(data, dict) else type(data).__name__
                    entry["analystenfelder"] = keys_with_words(data)
            except Exception as exc:  # Bericht statt Abbruch
                entry["fehler"] = f"{type(exc).__name__}: {exc}"[:160]
            onvista[isin] = entry
        report["onvista"] = onvista

        stocktwits = {}
        for symbol in ("AAPL", "PDSB", "SAP"):
            entry = {}
            try:
                r = other.get(f"https://api.stocktwits.com/api/2/streams/symbol/{symbol}.json")
                entry["status"] = r.status_code
                if r.status_code == 200:
                    messages = (r.json() or {}).get("messages") or []
                    entry["beitraege"] = len(messages)
                    entry["mit_stimmung"] = sum(1 for m in messages if ((m.get("entities") or {}).get("sentiment") or {}).get("basic"))
                    stamps = [m.get("created_at") for m in messages if m.get("created_at")]
                    entry["zeitraum"] = f"{min(stamps)[:16]} bis {max(stamps)[:16]}" if stamps else None
            except Exception as exc:  # Bericht statt Abbruch
                entry["fehler"] = f"{type(exc).__name__}: {exc}"[:160]
            stocktwits[symbol] = entry
        report["stocktwits"] = stocktwits
        REPORT.setdefault("weitere_quellen", {}).update(report)

    def test_yahoo_fundamentals_and_news(self) -> None:
        """Kennzahlen je Aktie für das Potenzial-Ranking (ab 1.6) – nur welche Felder geliefert werden, keine Werte.

        Ein quoteSummary-Abruf mit allen nötigen Modulen (Kursziele, Bewertung, Wachstum, Finanzen, Termine,
        Branche, Analystenurteile) und die Nachrichtensuche (Anzahl Meldungen der letzten 7 Tage).
        Nur Bericht."""
        import time

        from traktien.providers.yahoo import BASE

        wanted = {
            "financialData": ["targetMeanPrice", "numberOfAnalystOpinions", "recommendationMean", "revenueGrowth", "earningsGrowth",
                              "grossMargins", "operatingMargins", "profitMargins", "returnOnEquity", "debtToEquity", "currentRatio", "freeCashflow"],
            "defaultKeyStatistics": ["forwardPE", "pegRatio", "priceToBook", "beta", "shortPercentOfFloat", "heldPercentInstitutions",
                                     "heldPercentInsiders", "52WeekChange", "enterpriseToEbitda", "trailingEps", "forwardEps"],
            "summaryDetail": ["trailingPE", "forwardPE", "dividendYield", "marketCap", "fiftyTwoWeekHigh", "fiftyTwoWeekLow", "averageVolume", "averageVolume10days"],
            "calendarEvents": ["earnings"],
            "assetProfile": ["sector", "industry"],
        }
        modules = ",".join(list(wanted) + ["earningsTrend", "recommendationTrend", "upgradeDowngradeHistory"])
        symbols = ["AAPL", "PDSB", "SAP.DE", "MC.PA", "HSBA.L", "7203.T", "0700.HK", "ASML.AS", "TAL1T.TL", "CEZ.PR", "RHM.DE", "NVDA"]
        provider = YahooProvider()
        crumb = provider.ensure_crumb()
        out: dict = {}
        for symbol in symbols:
            entry: dict = {}
            try:
                t0 = time.monotonic()
                r = provider.http.get(f"{BASE}/v10/finance/quoteSummary/{symbol}", params={"modules": modules, "crumb": crumb, "formatted": "false"})
                entry["status"] = r.status_code
                entry["kb"] = round(len(r.content) / 1024, 1)
                entry["s"] = round(time.monotonic() - t0, 2)
                if r.status_code == 200:
                    res = ((r.json().get("quoteSummary") or {}).get("result") or [{}])[0] or {}
                    missing = []
                    present = 0
                    for module, fields in wanted.items():
                        block = res.get(module) or {}
                        for name in fields:
                            value = block.get(name)
                            if isinstance(value, dict) and "raw" in value:
                                value = value.get("raw")
                            if value in (None, {}, [], ""):
                                missing.append(f"{module}.{name}")
                            else:
                                present += 1
                    trend = {t.get("period"): t for t in (res.get("earningsTrend") or {}).get("trend") or []}
                    next_year = trend.get("+1y") or {}
                    entry["felder_vorhanden"] = present
                    entry["felder_fehlen"] = missing
                    entry["gewinnwachstum_1j"] = next_year.get("growth") not in (None, {})
                    entry["umsatzwachstum_1j"] = ((next_year.get("revenueEstimate") or {}).get("growth")) not in (None, {})
            except Exception as exc:  # Bericht statt Abbruch
                entry["fehler"] = f"{type(exc).__name__}: {exc}"[:160]
            out[symbol] = entry
        news: dict = {}
        for symbol in symbols[:8]:
            entry = {}
            try:
                r = provider.http.get(f"{BASE}/v1/finance/search", params={"q": symbol, "quotesCount": "0", "newsCount": "20"})
                entry["status"] = r.status_code
                if r.status_code == 200:
                    items = (r.json() or {}).get("news") or []
                    week = [n for n in items if (n.get("providerPublishTime") or 0) >= time.time() - 7 * 86400]
                    entry["meldungen"] = len(items)
                    entry["letzte_7_tage"] = len(week)
                    entry["mit_bezug_zur_aktie"] = sum(1 for n in items if symbol in (n.get("relatedTickers") or []))
                    entry["quellen"] = len({n.get("publisher") for n in items})
                    entry["felder"] = sorted({k for n in items[:3] for k in n})
            except Exception as exc:  # Bericht statt Abbruch
                entry["fehler"] = f"{type(exc).__name__}: {exc}"[:160]
            news[symbol] = entry
        REPORT.setdefault("weitere_quellen", {})["yahoo_kennzahlen"] = out
        REPORT["weitere_quellen"]["yahoo_nachrichten"] = news

    def test_ecb_reference_rates(self) -> None:
        """EZB-Referenzkurse (indikative USD-Umrechnung für den Umsatzfilter): erreichbar, aktuell,
        welche Notierungswährungen der Börsentabelle abgedeckt sind."""
        from traktien.providers.ecb import EcbFxSource
        from traktien.providers.exchanges import unit_info

        fetched = EcbFxSource().fetch()
        days = sorted({d for d, _, _ in fetched.rows})
        currencies = sorted({c for _, c, _ in fetched.rows})
        needed = set()
        for exchange in load_exchange_table().exchanges.values():
            base, _ = unit_info(exchange.currency)
            if base:
                needed.add(base)
        missing = sorted(c for c in needed if c not in currencies and c not in ("EUR", "USD"))
        latest = day_to_date(days[-1])
        REPORT["ezb"] = {
            "url": fetched.url,
            "abgerufen_utc": fetched.fetched_at,
            "kurstage": len(days),
            "erster_kurstag": day_to_date(days[0]).isoformat(),
            "letzter_kurstag": latest.isoformat(),
            "waehrungen": currencies,
            "fehlende_notierungswaehrungen": missing,
        }
        self.assertIn("USD", currencies)
        self.assertGreaterEqual(len(days), 40, "rund 60 Bankarbeitstage in 90 Kalendertagen erwartet")
        self.assertLessEqual((dt.date.today() - latest).days, 6, "letzter EZB-Kurs älter als 6 Tage")

    @unittest.skipUnless(os.environ.get("EODHD_API_KEY"), "EODHD_API_KEY nicht gesetzt")
    def test_eodhd_history(self) -> None:
        from traktien.providers.eodhd import EodhdProvider

        end = date_to_day(dt.date.today())
        history = EodhdProvider().fetch_history("AAPL.US", end - 45, end)
        REPORT["eodhd"] = {"aapl_tageskurse": len(history)}
        self.assertGreaterEqual(len(history), 20)


if __name__ == "__main__":
    unittest.main()
