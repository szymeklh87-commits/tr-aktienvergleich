"""Browser-Ende-zu-Ende-Tests der gebauten App auf einem simulierten Galaxy-S25+-Viewport.

Simulation (Chromium, 384 × 832 CSS-Pixel, Pixelverhältnis 2,8125, Touch) – das ist ausdrücklich
KEIN Test auf einem echten Gerät. Daten: DEMO-Stand mit synthetischen Testaktien.

Voraussetzungen: ``app/dist`` (``npm run build``), Python-Paket ``playwright`` und Chromium.
Ohne diese Voraussetzungen werden die Tests übersprungen.

Optional: ``TR_E2E_SCREENSHOTS=<Ordner>`` speichert Bildschirmfotos für den Testbericht.
"""

from __future__ import annotations

import datetime as dt
import functools
import http.server
import json
import os
import re
import shutil
import socketserver
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
APP_DIST = REPO / "app" / "dist"
PASSPHRASE = "Demo-Testschluessel-2026!"
SHOTS = os.environ.get("TR_E2E_SCREENSHOTS")

try:
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import expect, sync_playwright

    HAVE_PLAYWRIGHT = True
except ImportError:  # pragma: no cover - Umgebung ohne Playwright
    HAVE_PLAYWRIGHT = False

S25 = {"viewport": {"width": 384, "height": 832}, "device_scale_factor": 2.8125, "is_mobile": True, "has_touch": True}
FIXED = (7, 14, 21, 30, 40, 50, 60, 70, 80, 90)
WEIGHTS = (0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100)


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map, ".webmanifest": "application/manifest+json", ".js": "text/javascript", ".bin": "application/octet-stream"}

    def log_message(self, *args) -> None:  # noqa: D401 - keine Konsolenausgabe
        return

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()


def _serve(directory: Path) -> tuple[socketserver.TCPServer, str]:
    handler = functools.partial(_QuietHandler, directory=str(directory))
    server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), handler)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}/"


def _demo_site(target: Path, passphrase: str | None = None) -> Path:
    state = target / "state"
    site = target / "site"
    command = [sys.executable, "-m", "traktien", "demo", "--fresh", "--state-dir", str(state), "--site", str(site), "--app-dist", str(APP_DIST)]
    if passphrase:
        command += ["--passphrase", passphrase]
    # Feste GitHub-Angaben für den Knopf „Jetzt aktualisieren“ (in GitHub Actions sonst das echte Repository)
    env = dict(os.environ, PYTHONPATH=str(REPO / "backend"), LOG_LEVEL="WARNING", GITHUB_REPOSITORY="beispiel/tr-aktienvergleich", GITHUB_SERVER_URL="https://github.com")
    subprocess.run(command, check=True, cwd=REPO, env=env, capture_output=True, text=True, timeout=600)
    return site


def _plain(text: str | None) -> str:
    """Geschützte Leerzeichen (Zahl und Einheit) als normale Leerzeichen vergleichen."""
    return (text or "").replace(" ", " ").replace(" ", " ")


def _number(text: str) -> float:
    """Erste deutsch formatierte Zahl eines Textes, z. B. „−1.234,50 USD“ → -1234.5."""
    match = re.search(r"[−+-]?\d[\d.]*(?:,\d+)?", _plain(text))
    if match is None:
        raise ValueError(f"keine Zahl in {text!r}")
    return float(match.group(0).replace("−", "-").replace("+", "").replace(".", "").replace(",", "."))


def _chromium_path() -> str | None:
    candidate = Path("/opt/pw-browsers/chromium")
    return str(candidate) if candidate.exists() else None


@unittest.skipUnless(HAVE_PLAYWRIGHT and (APP_DIST / "index.html").exists(), "Playwright oder App-Build (app/dist) fehlt")
class MobileAppTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = Path(tempfile.mkdtemp(prefix="e2e-"))
        cls.site = _demo_site(cls.tmp / "klar")
        cls.site_enc = _demo_site(cls.tmp / "verschluesselt", PASSPHRASE)
        cls.server, cls.base = _serve(cls.site)
        cls.server_enc, cls.base_enc = _serve(cls.site_enc)
        cls.pw = sync_playwright().start()
        try:
            cls.browser = cls.pw.chromium.launch(executable_path=_chromium_path())
        except PlaywrightError as exc:  # pragma: no cover
            cls.pw.stop()
            raise unittest.SkipTest(f"Chromium nicht startbar: {exc}") from exc
        status = json.loads((cls.site / "data" / "status.json").read_text(encoding="utf-8"))
        cls.snapshot_id = status["latest_snapshot_id"]

    @classmethod
    def tearDownClass(cls) -> None:
        cls.browser.close()
        cls.pw.stop()
        for server in (cls.server, cls.server_enc):
            server.shutdown()
            server.server_close()
        shutil.rmtree(cls.tmp, ignore_errors=True)

    # ------------------------------------------------------------- Hilfen

    def page(self, *, base: str | None = None, color_scheme: str = "light", viewport: dict | None = None, service_workers: str = "block", permissions: list[str] | None = None):
        options = dict(S25, locale="de-DE", timezone_id="Europe/Berlin", color_scheme=color_scheme, accept_downloads=True, service_workers=service_workers)
        if viewport:
            options["viewport"] = viewport
            options["is_mobile"] = viewport["width"] < 900
        context = self.browser.new_context(**options)
        if permissions:
            context.grant_permissions(permissions, origin=(base or self.base).rstrip("/"))
        page = context.new_page()
        page.set_default_timeout(15000)
        errors: list[str] = []
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(str(e)))
        self.addCleanup(context.close)
        self.addCleanup(lambda: self.assertEqual(errors, [], "Konsolenfehler"))
        return page

    def go(self, page, route: str, base: str | None = None) -> None:
        page.goto(f"{base or self.base}#{route}")
        page.wait_for_load_state("networkidle")

    def wait_until(self, page, expression: str, timeout: float = 15) -> None:
        """Bedingung im Browser abfragen, bis sie gilt. (``wait_for_function`` würde im Browser
        ``eval`` benötigen, das die Content Security Policy der App zu Recht verbietet.)"""
        deadline = time.monotonic() + timeout
        while True:
            if page.evaluate(expression):
                return
            if time.monotonic() > deadline:
                self.fail(f"Bedingung nicht erfüllt: {expression}")
            page.wait_for_timeout(50)

    def shot(self, page, name: str) -> None:
        if SHOTS:
            Path(SHOTS).mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(Path(SHOTS) / f"{name}.png"), full_page=False)

    def snap(self, rel: str) -> dict:
        """Datei des unverschlüsselten DEMO-Stands, wie die App sie lädt – Sollwerte direkt aus den Serverdaten."""
        from traktien.util import crypto

        cache = self.__class__.__dict__.get("_snap_cache")
        if cache is None:
            cache = {}
            self.__class__._snap_cache = cache
        if rel not in cache:
            path = self.site / "data" / "snapshots" / self.snapshot_id / rel
            cache[rel] = json.loads(crypto.unpack(path.read_bytes(), None, f"snapshots/{self.snapshot_id}/{rel}"))
        return cache[rel]

    @staticmethod
    def day(epoch_day: int) -> str:
        return (dt.date(1970, 1, 1) + dt.timedelta(days=epoch_day)).strftime("%d.%m.%Y")

    @staticmethod
    def order(win: dict, group: str, weight: int) -> list[int]:
        if group == "a":
            return win["orders"]["v0"] if weight == 0 else win["orders"]["u"][str(weight)]
        return win["orders"]["v0l"] if weight == 0 else win["orders"]["ul"][str(weight)]

    # ------------------------------------------------------------- Tests

    def test_start_shows_stand_demo_and_ladder(self) -> None:
        page = self.page()
        self.go(page, "/")
        expect(page.locator(".stamp-date")).to_contain_text("Kursstand Montag, 12. Oktober 2026")
        expect(page.locator(".notice-demo")).to_contain_text("DEMO")
        expect(page.locator(".stand-chip")).to_contain_text("12.10.2026")
        expect(page.locator(".ladder-strip svg")).to_be_visible()
        self.shot(page, "01_start")
        page.locator(".ladder-strip").scroll_into_view_if_needed()
        box = page.locator(".ladder-strip .hit").bounding_box()
        page.mouse.click(box["x"] + box["width"] * 0.995, box["y"] + box["height"] / 2)
        page.wait_for_url("**/#/ranking?h=90&w=0&p=native&chart=1")
        expect(page.locator("ol.rows > li").first).to_be_visible()

    def test_return_rankings_winner_top10_and_full_list(self) -> None:
        """Erweiterung 1.1: Sieger je Zeitraum (Einzelliste, 1–7 Tage) → Top 10 → vollständige Rangliste."""
        page = self.page()
        self.go(page, "/rendite?f=alle&z=1-7")
        blocks = page.locator("ol.window-list > li")
        expect(blocks).to_have_count(7)
        expect(page.get_by_role("heading", name="Höchste Kursrendite", exact=True)).to_be_visible()
        expect(blocks.first).to_contain_text("ZZ")
        expect(page.get_by_text("Erfasste TR-Instrumente")).to_be_visible()
        expect(page.get_by_text("Geladene Kursreihen")).to_be_visible()
        expect(page.get_by_text("Ausgewertet (1–7 Tage)")).to_be_visible()
        expect(page.get_by_text("keine vollständige Prüfung aller TR-Aktien", exact=False)).to_be_visible()
        self.shot(page, "02_hoechste_rendite")
        first = blocks.first
        expect(first.locator(".price-path").first).to_contain_text("→ 12.10.2026")
        expect(first.locator(".turnover-line").first).to_contain_text("je Sitzung")
        first.get_by_role("button", name=re.compile("Top 10 anzeigen")).click()
        expect(first.locator(".top-ten ol.rows > li")).to_have_count(10)
        expect(first.get_by_role("button", name="Top 10 schließen")).to_have_attribute("aria-expanded", "true")
        self.shot(page, "02b_top10")
        first.get_by_role("link", name=re.compile("Vollständige Rangliste")).click()
        page.wait_for_url("**/#/rendite/liste?h=1**")
        expect(page.locator("ol.rows > li")).to_have_count(50)
        expect(page.locator("ol.rows > li").first.locator(".row-rank")).to_contain_text("1")
        page.get_by_role("navigation", name="Seiten der Rangliste").get_by_role("button", name="Nächste").click()
        self.wait_until(page, "location.hash.includes('seite=2')")
        expect(page.locator("ol.rows > li").first.locator(".row-rank")).to_contain_text("51")
        # Standard ab 1.5: alle 90 Zeiträume, Sieger der Gruppe A und B nebeneinander
        self.go(page, "/rendite")
        pairs = page.locator("ol.pair-list > li")
        expect(pairs).to_have_count(90)
        expect(pairs.first.locator(".pair-cell")).to_have_count(2)
        expect(pairs.first.locator(".pair-cell").nth(1)).to_contain_text("B – Ø Umsatz ≥ 10 Mio. USD")
        expect(pairs.first.locator(".pair-cell").first).to_contain_text("09.10.2026 – 12.10.2026")
        page.get_by_role("radio", name="31–90").click()
        expect(page.locator("ol.window-list > li")).to_have_count(60)
        page.get_by_role("radio", name="Alle 90").click()
        expect(page.locator("ol.window-list > li")).to_have_count(90)
        # Schnellwahl springt zum Zeitraum
        page.get_by_role("group", name="Zu Zeitraum springen").get_by_role("button", name="60 Tage").click()
        self.wait_until(page, "location.hash.includes('zeile=60')")
        expect(page.locator("#rw-60")).to_have_class(re.compile("is-jump"))
        expect(page.locator("#rw-60")).to_be_in_viewport()
        # gelbe Markierung erklärt sich selbst: „gewählt“ nur beim angesprungenen Zeitraum (1.5.3)
        expect(page.locator("#rw-60 .pair-h .jump-note")).to_have_text("gewählt")
        expect(page.locator("ol.window-list .jump-note")).to_have_count(1)
        expect(page.locator("#rw-60")).to_have_attribute("aria-current", "true")
        self.shot(page, "02e_sprung_gewaehlt")
        pairs.nth(59).get_by_role("button", name="Top 10 von A und B").click()
        expect(pairs.nth(59).locator(".pair-top .top-ten")).to_have_count(2)

    def test_turnover_filter_tab_and_low_turnover_flags(self) -> None:
        page = self.page()
        self.go(page, "/rendite?f=alle&z=alle")
        low_in_1 = page.locator("ol.window-list .badge-warn", has_text="sehr niedriger Umsatz").count()
        self.assertGreater(low_in_1, 0, "Ranking 1 kennzeichnet sehr niedrigen Umsatz")
        winners_1 = page.locator("ol.window-list > li .stock-row .isin-code").all_inner_texts()
        page.get_by_role("radio", name="B: Umsatz").click()
        self.wait_until(page, "location.hash.includes('f=umsatz')")
        expect(page.get_by_role("heading", name=re.compile("Ø Tagesumsatz mindestens 10"))).to_be_visible()
        expect(page.get_by_text("Ø Umsatz bestimmt")).to_be_visible()
        expect(page.locator("ol.window-list > li")).to_have_count(90)
        expect(page.locator("ol.window-list .badge-warn", has_text="sehr niedriger Umsatz")).to_have_count(0)
        winners_2 = page.locator("ol.window-list > li .stock-row .isin-code").all_inner_texts()
        self.assertNotEqual(winners_1, winners_2, "der Umsatzfilter ändert mindestens einen Sieger")
        for text in page.locator("ol.window-list > li .turnover-line").all_inner_texts()[:20]:
            self.assertIn("Mio.", text)
        self.shot(page, "02c_umsatzfilter")

    def test_detail_shows_turnover_and_both_return_ranks(self) -> None:
        page = self.page()
        self.go(page, "/rendite?f=umsatz")
        page.locator("ol.window-list > li").first.locator(".stock-row .row-name").first.click()
        page.wait_for_url("**/#/aktie/**")
        expect(page.get_by_text("Ø Tagesumsatz", exact=True)).to_be_visible()
        expect(page.locator(".kv-row", has_text="Ø Umsatz ≥ 10").first).to_contain_text("Platz 1 von")
        expect(page.locator(".kv-row", has_text="Höchste Kursrendite").first).to_contain_text("Platz")

    def test_frequency_names_universe_and_turnover_filter(self) -> None:
        page = self.page()
        self.go(page, "/haeufig/erweitert")
        expect(page.locator(".universe-note")).to_contain_text("ohne Umsatzfilter")
        self.go(page, "/haeufig/erweitert?tab=rendite")
        expect(page.locator(".universe-note")).to_contain_text("ohne Umsatzfilter")
        page.get_by_role("radio", name=re.compile("Ø Umsatz ≥ 10")).click()
        self.wait_until(page, "location.hash.includes('u=umsatz')")
        expect(page.locator(".universe-note")).to_contain_text("Ranking 2")
        expect(page.locator("ol.rows > li").first).to_be_visible()

    def test_weekend_start_dates_in_return_rankings(self) -> None:
        """Kursstand Montag 12.10.: 1–3 Tage beginnen am Freitag 09.10., 4 Tage am Donnerstag 08.10. – in beiden Listen."""
        page = self.page()
        for query in ("?f=alle&z=1-7", "?f=umsatz&z=1-7"):
            self.go(page, "/rendite" + query)
            blocks = page.locator("ol.window-list > li")
            expect(blocks).to_have_count(7)
            for k, start in ((0, "09.10.2026:"), (1, "09.10.2026:"), (2, "09.10.2026:"), (3, "08.10.2026:"), (4, "07.10.2026:")):
                expect(blocks.nth(k).locator(".price-path").first).to_contain_text(start)
                expect(blocks.nth(k).locator(".price-path").first).to_contain_text("→ 12.10.2026")

    def test_second_venue_deviation_in_lists_detail_and_status(self) -> None:
        """Erweiterung 1.2: auffällige Kursabweichung zwischen Börsenplätzen wird gekennzeichnet."""
        page = self.page()
        self.go(page, "/rendite?f=alle&z=8-30")
        blocks = page.locator("ol.window-list > li")
        expect(blocks).to_have_count(23)
        first = blocks.first  # 8 Tage: Sieger ist die DEMO-Impulstag-Aktie, am zweiten Platz ohne Kurssprung
        expect(first.locator(".badge-warn", has_text="Börsenplatz-Abweichung").first).to_be_visible()
        expect(first.locator(".venue-line").first).to_contain_text("Vergleich mit Börse Frankfurt (S194.F): auffällige Abweichung")
        expect(first.locator(".venue-line").first).to_contain_text("Endkurs −37,")
        first.get_by_role("button", name=re.compile("Top 10 anzeigen")).click()
        rows = first.locator(".top-ten ol.rows > li")
        expect(rows).to_have_count(10)
        expect(rows.first.locator(".venue-line")).to_contain_text("auffällige Abweichung")
        expect(rows.nth(1).locator(".venue-line")).to_contain_text("unauffällig, dort +")
        self.assertNotIn("ohne Rendite", page.locator("ol.window-list").inner_text())
        self.shot(page, "02d_boersenplatz")
        # Einzelansicht: DEMO-Aktie, deren Vergleichskurse bis 25 Tage vor dem Stichtag 15 % tiefer lagen
        self.go(page, "/aktie/ZZ0000000073?h=30")
        row = page.locator(".kv-row", has_text="Zweiter Börsenplatz")
        expect(row).to_contain_text("Auffällig")
        expect(row).to_contain_text("Börse Frankfurt")
        expect(row).to_contain_text("in USD umgerechnet")
        expect(page.get_by_text("Auffällige Kursabweichung zwischen Börsenplätzen", exact=False).first).to_be_visible()
        row.scroll_into_view_if_needed()
        self.shot(page, "04b_detail_boersenplatz")
        self.go(page, "/aktie/ZZ0000000073?h=10")
        expect(page.locator(".kv-row", has_text="Zweiter Börsenplatz")).to_contain_text("unauffällig")
        # Status: Umfang und Zählungen des Abgleichs
        self.go(page, "/status")
        expect(page.get_by_role("heading", name="Abgleich mit einem zweiten Börsenplatz")).to_be_visible()
        section = page.locator("section", has=page.get_by_role("heading", name="Abgleich mit einem zweiten Börsenplatz"))
        flagged_row = section.locator(".kv-row").filter(has=page.locator("dt", has_text=re.compile(r"^Auffällig$")))
        expect(flagged_row).to_contain_text("2 Aktien")
        expect(section.locator(".kv-row", has_text="Umfang")).to_contain_text("unter den ersten 10 Plätzen")
        expect(section.locator(".kv-row", has_text="Bevorzugte Börsenplätze")).to_contain_text("Xetra, Frankfurt, danach weitere")
        pairs = self.snap("manifest.bin")["venue_check"]["anzahl"]["aktie_zeitraum"]
        compared = pairs.get("ok", 0) + pairs.get("abweichung", 0)
        expect(section.locator(".kv-row", has_text="Verglichene Zeiträume")).to_contain_text(f"{compared:,}".replace(",", ".") + " von " + f"{sum(pairs.values()):,}".replace(",", "."))
        # boersenplatz-v2 (1.5.1): Regel für den Vergleichskurs aus der Version im Datenstand
        rule = section.locator(".kv-row").filter(has=page.locator("dt", has_text=re.compile(r"^Vergleichskurs$")))
        expect(rule).to_contain_text("Schlusskurs genau vom Start- und vom Enddatum")
        expect(rule).to_contain_text("Fehlt ein solcher Schlusskurs beim Kursanbieter, entfällt der Vergleich.")
        section.scroll_into_view_if_needed()
        self.shot(page, "06b_status_boersenplatz")
        # boersenplatz-v3: Schwelle nach Tagesschwankung, Auswertung nach fester 10-%-Regel
        diag = self.snap("manifest.bin")["venue_check"]["auswertung"]
        if diag["feste_schwelle_auffaellig"]:
            expect(section.locator(".kv-row", has_text="Nach fester 10-%-Regel")).to_contain_text(f"{diag['feste_schwelle_auffaellig']} Zeiträume")
        expect(flagged_row).to_contain_text("Schwelle der Aktie: mindestens 10 %")
        self.go(page, "/methodik")
        expect(page.get_by_text("Verwendet wird der Schlusskurs genau vom Start- und vom Enddatum", exact=False)).to_be_visible()
        expect(page.get_by_text("das 3-Fache ihrer üblichen Tagesschwankung der letzten 20 Tage", exact=False)).to_be_visible()

    def test_ranking_window_weight_and_empty_reason(self) -> None:
        page = self.page()
        self.go(page, "/ranking?h=30&w=60&p=native")
        expect(page.locator("ol.rows > li")).to_have_count(10)
        self.shot(page, "03_ranking")
        page.get_by_role("button", name="7 Tage", exact=True).click()
        self.wait_until(page, "location.hash.includes('h=7')")
        page.get_by_role("button", name="50/50", exact=True).click()
        self.wait_until(page, "location.hash.includes('w=50')")
        expect(page.locator(".weight-readout")).to_contain_text("50 % Gleichmäßigkeit")
        self.go(page, "/ranking?h=1&w=60&p=native")
        expect(page.get_by_text("Keine Rangliste für diese Auswahl")).to_be_visible()
        expect(page.get_by_text("mindestens 15 echte Tageskurse", exact=False).first).to_be_visible()
        page.get_by_role("link", name="Reine Renditeliste (0/100) zeigen").click()
        self.wait_until(page, "location.hash.includes('w=0')")
        expect(page.locator("ol.rows > li").first).to_be_visible()
        self.go(page, "/ranking?h=30&w=60&p=native&n=50")
        count = page.locator("ol.rows > li").count()
        self.assertGreater(count, 10)
        self.assertLessEqual(count, 50)

    def test_weight_comparison_shows_three_columns_and_pairwise_difference(self) -> None:
        page = self.page()
        self.go(page, "/vergleich?h=30")
        expect(page.locator(".table thead th")).to_have_count(4)
        page.get_by_role("radio", name="Alle elf, seitlich blättern").click()
        expect(page.locator(".table thead th")).to_have_count(12)
        expect(page.get_by_text("Rangverbesserung von A nach B", exact=False)).to_be_visible()
        page.locator("select").first.select_option("0")
        expect(page.get_by_text("Unterschiedliche Vergleichsfelder")).to_be_visible()

    def test_ranking_csv_export_is_excel_safe(self) -> None:
        page = self.page()
        self.go(page, "/ranking?h=30&w=60")
        with page.expect_download() as info:
            page.get_by_role("button", name="CSV").click()
        content = Path(info.value.path()).read_bytes().decode("utf-8")
        self.assertTrue(content.startswith("﻿"))
        self.assertIn("Rang;Unternehmen;ISIN;Rangscore;Kursrendite %;R²;Referenzschluss;Kurseinheit;Ø Tagesumsatz USD", content)
        self.assertIn("Positive Schlusskursvergleiche", content)
        with page.expect_download() as info_json:
            page.get_by_role("button", name="JSON").click()
        data = json.loads(Path(info_json.value.path()).read_text(encoding="utf-8"))
        self.assertEqual(data["format"], "tr-rangliste/1")
        self.assertEqual(len(data["eintraege"]), 10)
        first = data["eintraege"][0]
        self.assertTrue(first["isin"].startswith("ZZ") and first["name"].startswith("DEMO"))
        self.assertLessEqual(first["positive_schlusskursvergleiche"], first["schlusskurse"] - 1)
        self.assertIn(self.snapshot_id, content)
        self.assertIn("DEMO", content)

    def test_detail_chart_tooltip_and_png(self) -> None:
        page = self.page()
        self.go(page, "/ranking?h=30&w=60")
        first = page.locator("ol.rows > li .row-link").first
        name = first.inner_text()
        first.click()
        page.wait_for_url("**/#/aktie/**")
        expect(page.locator(".view-title")).to_have_text(name)
        hit = page.locator(".chart-surface .hit")
        hit.focus()
        page.wait_for_timeout(300)
        scroll_before = page.evaluate("window.scrollY")
        page.keyboard.press("End")
        expect(page.locator(".chart-surface .tooltip")).to_contain_text("Schlusskurs")
        page.wait_for_timeout(300)
        self.assertEqual(page.evaluate("window.scrollY"), scroll_before, "Ende-Taste bewegt nur den Tageskurs, nicht die Seite")
        self.shot(page, "04_detail")
        with page.expect_download() as info:
            page.get_by_role("button", name="Als PNG speichern").click()
        data = Path(info.value.path()).read_bytes()
        self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
        self.assertTrue(info.value.suggested_filename.endswith(".png"))

    def test_one_day_window_shows_only_daily_closes(self) -> None:
        page = self.page()
        self.go(page, "/ranking?h=1&w=0")
        page.locator("ol.rows > li .row-link").first.click()
        page.wait_for_url("**/#/aktie/**")
        expect(page.get_by_text("Intradaydaten sind nicht verfügbar", exact=False)).to_be_visible()
        circles = page.locator(".chart-surface svg circle").count()
        self.assertLessEqual(circles, 12, "T63: kein erfundener Tagesverlauf")

    def test_isin_copy_gives_accessible_feedback(self) -> None:
        page = self.page(permissions=["clipboard-read", "clipboard-write"])
        self.go(page, "/rendite?f=alle")
        button = page.locator(".isin-copy").first
        button.click()
        expect(page.locator(".isin [role=status]").first).to_contain_text("kopiert")

    def test_watchlist_star_and_subgroup(self) -> None:
        page = self.page()
        self.go(page, "/ranking?h=30&w=60")
        stars = page.locator("ol.rows .watch-btn")
        stars.nth(0).click()
        stars.nth(2).click()
        self.go(page, "/watchlist?h=30&w=60")
        expect(page.locator("ul.rows > li")).to_have_count(2)
        page.get_by_role("radio", name="Nur innerhalb der Watchlist").click()
        expect(page.get_by_text("Untergruppe: Watchlist", exact=False)).to_be_visible()
        self.shot(page, "05_watchlist")

    def test_frequency_list_matches_server_and_matrix_cells_open(self) -> None:
        page = self.page()
        self.go(page, "/haeufig/erweitert")
        expect(page.get_by_text("Abgleich mit der Serverberechnung: übereinstimmend", exact=False)).to_be_visible()
        self.shot(page, "06_haeufigste")
        page.locator("ol.rows > li .row-link").first.click()
        page.wait_for_url("**/#/haeufig/**")
        cell = page.locator(".fmatrix .fcell.is-top1, .fmatrix .fcell.is-top3, .fmatrix .fcell.is-top10").first
        cell.click()
        expect(page.locator(".fm-detail")).to_contain_text("Platz")
        self.shot(page, "07_trefferMatrix")

    def test_chart_grid_modes_and_png(self) -> None:
        page = self.page()
        self.go(page, "/raster")
        expect(page.locator(".tiles > li")).to_have_count(10)
        expect(page.locator(".tiles .mini").first).to_be_visible()
        self.shot(page, "08_raster")
        with page.expect_download() as info:
            page.get_by_role("button", name="Diese Seite als PNG").click()
        self.assertEqual(Path(info.value.path()).read_bytes()[:4], b"\x89PNG")
        self.go(page, "/raster?modus=zeitraeume")
        expect(page.locator(".wmatrix thead th")).to_have_count(7)
        self.go(page, "/raster?modus=gemeinsam")
        expect(page.locator(".legend li")).to_have_count(8)
        expect(page.get_by_text("100 = echter Schlusskurs am gemeinsamen Basistag", exact=False)).to_be_visible()

    def test_offline_after_first_visit(self) -> None:
        page = self.page(service_workers="allow")
        self.go(page, "/ranking?h=30&w=60")
        self.assertTrue(page.evaluate("navigator.serviceWorker.ready.then(() => true)"))
        page.reload()
        self.wait_until(page, "!!navigator.serviceWorker.controller")
        self.go(page, "/ranking?h=30&w=60")
        expect(page.locator("ol.rows > li")).to_have_count(10)
        page.context.set_offline(True)
        page.reload()
        expect(page.get_by_text("Offline – gespeicherter Stand")).to_be_visible()
        expect(page.locator("ol.rows > li")).to_have_count(10)
        self.shot(page, "09_offline")
        page.context.set_offline(False)

    def test_touch_targets_are_at_least_44px(self) -> None:
        page = self.page()
        selectors = ".btn, .icon-btn, .chip, .segmented button, .bottomnav a, .fcell, .legend-btn, .stand-chip, .disclosure-toggle, .isin-copy, .watch-btn"
        for route in ("/", "/ranking", "/raster", "/haeufig/" + "ZZ0000000412", "/aktie/ZZ0000000719?h=30", "/bericht?m=ZZ0000000719"):
            self.go(page, route)
            small = page.evaluate(
                """(sel) => [...document.querySelectorAll(sel)]
                    .filter((el) => el.offsetParent !== null && !el.closest('.fm-legend'))
                    .map((el) => { const r = el.getBoundingClientRect(); return { cls: el.className, text: (el.textContent || '').trim().slice(0, 20), w: r.width, h: r.height }; })
                    .filter((b) => b.w < 43.5 || b.h < 43.5)""",
                selectors,
            )
            self.assertEqual(small, [], f"Zu kleine Bedienelemente auf {route}")

    def test_every_button_has_an_accessible_name(self) -> None:
        page = self.page()
        for route in ("/", "/rendite", "/bericht?m=ZZ0000000719", "/ranking", "/vergleich", "/aktien", "/haeufig", "/raster", "/aktie/ZZ0000000719?h=30", "/status", "/einstellungen"):
            self.go(page, route)
            unnamed = page.evaluate(
                """() => [...document.querySelectorAll('button, a[href], input, select, [role=slider]')]
                    .filter((el) => el.offsetParent !== null || el.tagName === 'INPUT')
                    .filter((el) => {
                      const label = el.getAttribute('aria-label') || el.getAttribute('title') || (el.textContent || '').trim();
                      const labelled = el.id && document.querySelector(`label[for="${el.id}"]`);
                      const wrapped = el.closest('label');
                      const byRef = el.getAttribute('aria-labelledby');
                      return !(label || labelled || wrapped || byRef);
                    })
                    .map((el) => el.outerHTML.slice(0, 120))"""
            )
            self.assertEqual(unnamed, [], f"Unbeschriftete Bedienelemente auf {route}")

    def test_T62_window_switch_changes_real_chart_data(self) -> None:
        page = self.page()
        self.go(page, "/aktie/ZZ0000000412?h=7")
        summary_7 = page.locator("figure.chart").first.get_attribute("aria-label")
        page.get_by_role("button", name="30 Tage", exact=True).click()
        self.wait_until(page, "location.hash.includes('h=30')")
        expect(page.locator("figure.chart").first).not_to_have_attribute("aria-label", summary_7)
        summary_30 = page.locator("figure.chart").first.get_attribute("aria-label")
        count = lambda text: int(text.split(" echte Tageskurse")[0].split(" ")[-1])
        self.assertGreater(count(summary_30), count(summary_7))

    def test_T56_stale_heartbeat_is_shown_as_gap(self) -> None:
        page = self.page()
        status = json.loads((self.site / "data" / "status.json").read_text(encoding="utf-8"))
        status["last_successful_check_utc"] = "2026-09-01T04:05:00Z"
        page.route("**/data/status.json*", lambda route: route.fulfill(status=200, content_type="application/json", body=json.dumps(status)))
        self.go(page, "/")
        expect(page.get_by_text("Keine aktuelle Prüfung")).to_be_visible()

    def test_T59_first_use_without_snapshot_shows_setup_state(self) -> None:
        page = self.page()
        status = json.loads((self.site / "data" / "status.json").read_text(encoding="utf-8"))
        status["latest_snapshot_id"] = None
        status["last_run"] = dict(
            status.get("last_run") or {},
            status="wartet_auf_provider",
            message="Daten für XETR noch unvollständig; nächster Versuch geplant",
            started_at_utc="2026-10-13T08:59:04Z",
            finished_at_utc="2026-10-13T09:42:49Z",
        )
        page.route("**/data/status.json*", lambda route: route.fulfill(status=200, content_type="application/json", body=json.dumps(status)))
        page.route("**/data/snapshots/index.json*", lambda route: route.fulfill(status=200, content_type="application/json", body='{"schema": "tr-snapshot-index/1", "snapshots": []}'))
        self.go(page, "/")
        expect(page.get_by_text("Noch kein Datenstand veröffentlicht")).to_be_visible()
        # Grund des letzten Laufs in lesbarer Form, mit Uhrzeit in Europe/Berlin
        reason = page.get_by_text("wartet auf Kursdaten – Wiederholung geplant", exact=False)
        expect(reason).to_be_visible()
        self.assertIn("Grund: Daten für XETR noch unvollständig", reason.inner_text())
        self.assertIn("11:42", reason.inner_text())
        self.assertEqual(page.locator("ol.rows > li").count(), 0, "keine erfundenen Gewinner")
        # Auch ohne Datenstand lässt sich ein Lauf anstoßen
        page.get_by_role("link", name="Jetzt aktualisieren").first.click()
        self.wait_until(page, "location.hash === '#/aktualisieren'")
        expect(page.get_by_role("link", name="Lauf auf GitHub starten")).to_be_visible()
        expect(page.locator(".kv-row", has_text="Kursstand in der App")).to_contain_text("noch kein Datenstand")

    def test_update_on_demand_starts_on_github_and_reports_result(self) -> None:
        """Jederzeit aktualisieren: Start auf GitHub (kein Schlüssel in der App), Warten, Ergebnis melden."""
        page = self.page()
        page.context.route("https://github.com/**", lambda route: route.fulfill(status=200, content_type="text/html", body="<!doctype html><title>GitHub</title>"))
        status = json.loads((self.site / "data" / "status.json").read_text(encoding="utf-8"))
        self.assertEqual(status["aktualisieren"]["starten_url"], "https://github.com/beispiel/tr-aktienvergleich/actions/workflows/taeglich.yml")
        self.assertEqual(status["naechster_kursstand"]["datum"], "2026-10-13")
        self.go(page, "/")
        page.get_by_role("button", name="Weitere Ansichten").click()
        page.get_by_role("link", name="Jetzt aktualisieren").click()
        self.wait_until(page, "location.hash === '#/aktualisieren'")
        expect(page.get_by_role("heading", name="Lauf starten")).to_be_visible()
        expect(page.locator(".kv-row", has_text="Kursstand in der App")).to_contain_text("12.10.2026")
        expect(page.locator(".kv-row", has_text="Nächste neue Schlusskurse")).to_contain_text("Dienstag, 13. Oktober 2026")
        start = page.get_by_role("link", name="Lauf auf GitHub starten")
        expect(start).to_have_attribute("href", status["aktualisieren"]["starten_url"])
        expect(start).to_have_attribute("target", "_blank")
        self.shot(page, "13_aktualisieren")
        with page.context.expect_page() as popup:
            start.click()
        popup.value.close()
        expect(page.get_by_text("Warte auf das Ergebnis")).to_be_visible()
        self.assertIsNotNone(page.evaluate("localStorage.getItem('tr-aktualisierung-v1')"), "Warten übersteht einen Neustart der App")
        # Banner in anderen Ansichten
        page.get_by_role("navigation", name="Hauptnavigation").get_by_role("link", name="Start").click()
        expect(page.get_by_text("Aktualisierung angefordert")).to_be_visible()
        # Der Lauf meldet sich: kein neuer Börsentag
        done = dict(status)
        done["generated_at_utc"] = "2026-10-13T12:10:00Z"
        done["last_run"] = dict(status["last_run"], run_id="lauf-manuell", status="keine_neuen_daten", message="Kein neuer abgeschlossener Börsentag seit 2026-10-12; letzter Stand bleibt gültig")
        page.route("**/data/status.json*", lambda route: route.fulfill(status=200, content_type="application/json", body=json.dumps(done)))
        page.locator(".banners").get_by_role("button", name="Details", exact=True).click()
        self.wait_until(page, "location.hash === '#/aktualisieren'")
        page.get_by_role("button", name="Jetzt nach neuem Stand schauen").click()
        expect(page.get_by_text("Lauf beendet – keine neuen Kurse")).to_be_visible()
        expect(page.get_by_text("Kein neuer abgeschlossener Börsentag seit 2026-10-12", exact=False).first).to_be_visible()
        expect(page.get_by_text("Warte auf das Ergebnis")).to_have_count(0)
        self.assertIsNone(page.evaluate("localStorage.getItem('tr-aktualisierung-v1')"))
        # Ergebnis bleibt als Hinweis sichtbar, bis es ausgeblendet wird
        page.get_by_role("navigation", name="Hauptnavigation").get_by_role("link", name="Rendite").click()
        banner = page.locator(".banners .notice", has_text="Lauf beendet – keine neuen Kurse")
        expect(banner).to_be_visible()
        banner.get_by_role("button", name="Ausblenden").click()
        expect(banner).to_have_count(0)

    def test_group_matrix_tabs_marks_list_frequency_and_identical_windows(self) -> None:
        """Gruppenvergleich A/B: Reiter, feste Zeitraumspalte, Markierung aller Vorkommen, Rangliste, Liste, Häufigkeit."""
        page = self.page()
        self.go(page, "/")
        page.get_by_role("navigation", name="Hauptnavigation").get_by_role("link", name="Analyse").click()
        self.wait_until(page, "location.hash === '#/analyse'")
        page.locator(".tool-list a", has_text="Matrix A/B").click()
        self.wait_until(page, "location.hash === '#/matrix'")
        table = page.locator("table.gmatrix")
        expect(table.locator("tbody tr")).to_have_count(90)
        expect(table.locator("thead th")).to_have_count(12)  # Tage + elf Gewichtungen
        expect(page.get_by_text("Ranglisten berechnet", exact=False)).to_be_visible()
        expect(table.locator("td.gcell.is-empty").first).to_contain_text("weniger als 15 Tageskurse")
        expect(table.locator(".same-mark").first).to_be_visible()  # Montag: 1–3 Tage gleiches Kursfenster
        # feste Zeitraumspalte: nach seitlichem Wischen bleibt sie an derselben Stelle
        wrap = page.locator(".gmatrix-wrap")
        day_cell = table.locator("tbody th.gday").first
        before = day_cell.bounding_box()["x"]
        wrap.evaluate("el => el.scrollBy({ left: 600 })")
        page.wait_for_timeout(100)
        self.assertAlmostEqual(day_cell.bounding_box()["x"], before, delta=1)
        self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"), page.evaluate("window.innerWidth"), "nur die Matrix verschiebt sich")
        wrap.evaluate("el => el.scrollTo({ left: 0 })")
        self.shot(page, "21_matrix")
        # Antippen markiert alle Vorkommen derselben ISIN und bietet Rangliste und Kursverlauf an
        first = table.locator("button.gcell-btn").first
        isin = first.locator(".gcell-isin").inner_text()
        first.click()
        self.wait_until(page, f"location.hash.includes('isin={isin}')")
        selected = table.locator("td.gcell.is-selected")
        self.assertGreaterEqual(selected.count(), 2, "wiederkehrende Aktie mehrfach markiert")
        self.assertEqual(selected.count(), table.locator(f"td.gcell:has(.gcell-isin:text-is('{isin}'))").count())
        panel = page.locator(".matrix-selection")
        expect(panel).to_contain_text(isin)
        expect(panel.locator(".mark")).to_contain_text("↻")
        # Gruppe B: gleiche Kennzeichnung derselben ISIN
        mark_a = panel.locator(".mark").get_attribute("title")
        page.get_by_role("radio", name="B: Ø Umsatz ≥ 10 Mio. USD").click()
        self.wait_until(page, "location.hash.includes('g=b')")
        expect(page.locator(".matrix-selection .mark")).to_have_attribute("title", mark_a)
        page.locator(".matrix-selection").get_by_role("link", name="Rangliste", exact=False).click()
        self.wait_until(page, "location.hash.startsWith('#/ranking') && location.hash.includes('g=b')")
        expect(page.get_by_role("radio", name="B: Ø Umsatz ≥ 10 Mio. USD")).to_have_attribute("aria-checked", "true")
        expect(page.get_by_text("Gruppe B: nur Aktien mit Ø Tagesumsatz ab 10 Mio. USD", exact=False)).to_be_visible()
        expect(page.locator("ol.rows > li").first).to_contain_text(isin)
        page.go_back()
        self.wait_until(page, "location.hash.startsWith('#/matrix')")
        # Kompakte Liste: 90 Zeilen, Standard nur Rendite
        page.get_by_role("radio", name="Liste").click()
        expect(page.locator(".glist-row")).to_have_count(90)
        expect(page.get_by_role("heading", name="Spitzenreiter je Zeitraum, Nur Kursrendite", exact=False)).to_be_visible()
        # Häufigkeit: Platz 1 zuerst, A und B getrennt, identische Kursfenster einmal
        page.get_by_role("radio", name="Häufigkeit").click()
        expect(page.get_by_role("heading", name="Häufigkeitsranking")).to_be_visible()
        expect(page.locator(".scope-note")).to_contain_text("Gruppe B (Ø Tagesumsatz ≥ 10 Mio. USD)")
        rows = page.locator("table.gfreq tbody tr")
        expect(rows.first).to_be_visible()
        n1 = [int(t) for t in rows.locator("td:nth-child(3) .gnum").all_inner_texts()]
        self.assertEqual(n1, sorted(n1, reverse=True), "sortiert nach Platz-1-Vorkommen")
        page.get_by_role("radio", name="A und B").click()
        self.wait_until(page, "location.hash.includes('gruppen=ab')")
        expect(page.locator("table.gfreq-both tbody tr").first.locator(".gsplit").first).to_contain_text("A ")
        before_once = page.locator("table.gfreq tbody tr").first.locator("td").nth(2).inner_text()
        page.get_by_label("Identische Kursfenster nur einmal zählen").check()
        self.wait_until(page, "location.hash.includes('einmal=1')")
        expect(page.get_by_text("Top-10-Fundstellen zusammengefasst", exact=False)).to_be_visible()
        after_once = page.locator("table.gfreq tbody tr").first.locator("td").nth(2).inner_text()
        self.assertNotEqual(before_once, after_once, "gleiche Kursfenster werden zusammengefasst")
        self.shot(page, "22_matrix_haeufigkeit")

    def test_rotation_rule_today_backtest_variants_and_own_amounts(self) -> None:
        """Umschichtungs-Regel: Start → Regel; Depot-Lineal, Bestand, Rückblick, Varianten, beschlossene Umschichtung, eigene Beträge."""
        page = self.page()
        self.go(page, "/")
        teaser = page.locator("section", has=page.get_by_role("heading", name="Umschichtungs-Regel"))
        expect(teaser).to_contain_text("keine Empfehlung")
        teaser.get_by_role("link", name="Regel ansehen").click()
        self.wait_until(page, "location.hash === '#/regel'")
        expect(page.get_by_role("heading", name="Heute nach der Regel")).to_be_visible()
        expect(page.locator(".alloc-bar")).to_have_count(1)  # Standard (monatlich): heute keine Änderung
        expect(page.get_by_text("Keine Änderung: Alle gehaltenen Aktien")).to_be_visible()
        expect(page.locator(".hold-row")).to_have_count(5)
        expect(page.get_by_text("Nächste Entscheidung: Freitag, 6. November 2026", exact=False)).to_be_visible()
        expect(page.locator(".chart svg[role=img]").first).to_be_visible()
        expect(page.locator(".legend li")).to_have_count(3)
        self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"), page.evaluate("window.innerWidth"), "keine Seitwärtsverschiebung")
        self.shot(page, "20_regel")
        # Variante: 10 Aktien
        page.get_by_role("radio", name="10 Aktien je 10 %").click()
        self.wait_until(page, "location.hash.includes('n=10')")
        expect(page.locator(".hold-row")).to_have_count(10)
        # Wöchentlich: am Freitag beschlossen, am nächsten Handelstag umgesetzt
        self.go(page, "/regel?n=5&r=woechentlich&w=13")
        expect(page.get_by_role("heading", name="Was die Regel jetzt umsetzt")).to_be_visible()
        expect(page.get_by_text("Beschlossen zum Schlusskurs vom Freitag, 9. Oktober 2026", exact=False)).to_be_visible()
        expect(page.locator(".alloc-bar")).to_have_count(2)
        first_change = page.locator(".change").first
        expect(first_change.locator(".change-verb")).to_have_text("Verkaufen")
        before = first_change.locator(".change-figs").inner_text()
        # Eigener Depotwert: gleiche Anteile, Beträge umgerechnet, nur auf diesem Gerät gespeichert
        field = page.get_by_label("Beträge umrechnen auf einen Depotwert von")
        field.fill("abc")
        page.get_by_role("button", name="Übernehmen").click()
        expect(page.get_by_text("Bitte einen Betrag zwischen")).to_be_visible()
        field.fill("25.000")
        field.press("Enter")
        expect(page.get_by_text("Alle Beträge unten sind auf 25.000 € umgerechnet", exact=False)).to_be_visible()
        after = first_change.locator(".change-figs").inner_text()
        self.assertNotEqual(before, after)
        self.assertEqual(before.split(",")[0], after.split(",")[0], "Anteile bleiben gleich")
        page.reload()
        page.wait_for_load_state("networkidle")
        expect(page.get_by_text("Alle Beträge unten sind auf 25.000 € umgerechnet", exact=False)).to_be_visible()
        page.get_by_role("button", name="Zurücksetzen").click()
        expect(page.get_by_text("Ohne Angabe gelten die Beträge des Regeldepots.")).to_be_visible()
        # Variantentabelle wählt per Antippen; Orders je Entscheidungstag aufklappbar
        page.locator(".variant-table").get_by_role("button", name="10 Aktien, monatlich Trend 4 Wochen").click()
        self.wait_until(page, "location.hash.includes('n=10') && location.hash.includes('r=monatlich') && location.hash.includes('w=4')")
        days = page.locator(".order-days .disclosure")
        expect(days.first).to_contain_text("Entscheidung Fr.")
        days.first.locator(".disclosure-toggle").click()
        expect(days.first.locator(".order").first).to_be_visible()
        expect(page.get_by_role("heading", name="Was die Rechnung nicht zeigt")).to_be_visible()
        expect(page.get_by_text("Keine Anlageberatung", exact=False).first).to_be_visible()

    def test_T49_app_update_keeps_watchlist_and_settings(self) -> None:
        page = self.page(service_workers="allow")
        self.go(page, "/ranking?h=30&w=60")
        self.assertTrue(page.evaluate("navigator.serviceWorker.ready.then(() => true)"))
        page.reload()
        self.wait_until(page, "!!navigator.serviceWorker.controller")
        page.locator("ol.rows .watch-btn").first.click()
        self.go(page, "/einstellungen")
        page.get_by_role("radio", name="Dunkel").click()
        sw = self.site / "sw.js"
        original = sw.read_bytes()
        self.addCleanup(sw.write_bytes, original)
        sw.write_bytes(original + b"\n/* neue App-Version (Test) */\n")
        page.evaluate("navigator.serviceWorker.getRegistration().then((r) => r.update())")
        expect(page.get_by_text("Neue App-Version verfügbar")).to_be_visible(timeout=20000)
        with page.expect_navigation():
            page.get_by_role("button", name="Aktualisieren").click()
        page.wait_for_load_state("networkidle")
        self.assertEqual(page.evaluate("document.documentElement.dataset.theme"), "dunkel")
        self.go(page, "/watchlist?h=30&w=60")
        expect(page.locator("ul.rows > li")).to_have_count(1)

    def test_landscape_and_desktop_use_side_navigation(self) -> None:
        for viewport, name in (({"width": 832, "height": 384}, "10_querformat"), ({"width": 1280, "height": 800}, "11_desktop")):
            page = self.page(viewport=viewport)
            self.go(page, "/ranking?h=30&w=60")
            box = page.locator(".bottomnav").bounding_box()
            self.assertGreater(box["height"], box["width"], f"Navigation als Seitenleiste bei {viewport}")
            expect(page.locator("ol.rows > li").first).to_be_visible()
            self.shot(page, name)

    def test_dark_mode_setting(self) -> None:
        page = self.page()
        self.go(page, "/einstellungen")
        page.get_by_role("radio", name="Dunkel").click()
        self.assertEqual(page.evaluate("document.documentElement.dataset.theme"), "dunkel")
        page.reload()
        page.wait_for_load_state("networkidle")
        self.assertEqual(page.evaluate("document.documentElement.dataset.theme"), "dunkel", "Schema bleibt nach Neuladen")
        self.go(page, "/ranking?h=30&w=60")
        self.shot(page, "12_dunkel")

    # ------------------------------------------- Abschnitt 33 (T61–T78), T99, T100

    def test_T61_each_listed_isin_opens_its_own_chart(self) -> None:
        page = self.page()
        checked = 0
        for route in ("/ranking?h=30&w=60", "/rendite?f=alle", "/haeufig/erweitert", "/raster", "/aktien"):
            self.go(page, route)
            page.locator("li .isin-code").first.wait_for()
            rows = page.evaluate(
                """() => [...document.querySelectorAll('li')].map((li) => {
                    const code = li.querySelector('.isin-code');
                    const link = li.querySelector('a[href*="#/aktie/"], a[href*="#/haeufig/"]');
                    const name = li.querySelector('.row-name, .tile-name');
                    return code && link ? { isin: code.textContent.trim(), href: link.getAttribute('href'), name: name ? name.textContent.trim() : null } : null;
                  }).filter(Boolean).slice(0, 4)"""
            )
            self.assertTrue(rows, f"keine Aktienzeilen auf {route}")
            for row in rows:
                path = row["href"].split("#", 1)[1]
                self.assertTrue(path.split("?")[0].endswith("/" + row["isin"]), f"{route}: Link {row['href']} gehört nicht zu {row['isin']}")
                self.go(page, path)
                expect(page.locator(".view-head .isin-code").first).to_have_text(row["isin"])
                if row["name"]:
                    expect(page.locator(".view-title")).to_have_text(row["name"])
                checked += 1
        self.assertGreaterEqual(checked, 15)
        # Auch eine Aktie ohne Kurse hat eine Seite – mit konkretem Leerzustand statt erfundenem Verlauf
        self.go(page, "/aktien?q=Keine%20Kursdaten")
        page.locator("ul.rows > li .row-link").first.click()
        page.wait_for_url("**/#/aktie/**")
        expect(page.locator(".notice-title", has_text="Keine Kursdaten")).to_be_visible()
        self.assertEqual(page.locator("figure.chart").count(), 0)

    def test_T64_matrix_cells_show_requested_window_from_one_snapshot(self) -> None:
        page = self.page()
        snapshots: set[str] = set()
        page.on("request", lambda r: snapshots.add(r.url.split("/data/snapshots/", 1)[1].split("/", 1)[0]) if "/data/snapshots/" in r.url and not r.url.split("?")[0].endswith("index.json") else None)
        self.go(page, "/raster?modus=zeitraeume&spalten=7,30,90")
        row = page.locator(".wmatrix tbody tr").first
        isin = row.locator("th .muted").inner_text().strip()
        cells = row.locator("td a.wcell")
        expect(cells).to_have_count(3)
        for k in range(3):
            expect(cells.nth(k)).to_contain_text(re.compile(r"\d+ Kurse"))
        found = [(_plain(cells.nth(k).inner_text()), cells.nth(k).get_attribute("href")) for k in range(3)]
        with page.expect_download() as info:
            page.get_by_role("button", name="Diese Seite als PNG").click()
        self.assertIn(self.snapshot_id, info.value.suggested_filename)
        pattern = re.compile(r"am (\d{2}\.\d{2})\.\d{4} und .+ am (\d{2}\.\d{2})\.\d{4}, Veränderung (.+?)\. (\d+) echte Tageskurse")
        for h, (text, href) in zip((7, 30, 90), found):
            self.assertRegex(href, rf"[?&]h={h}(&|$)")
            self.go(page, f"/aktie/{isin}?h={h}")
            summary = _plain(page.locator("figure.chart").first.get_attribute("aria-label"))
            match = pattern.search(summary)
            self.assertIsNotNone(match, summary)
            first, last, change, count = match.groups()
            self.assertIn(f"{first}.–{last}., {count} Kurse", text, f"Zelle {h} Tage passt nicht zum Einzelchart")
            self.assertIn(change, text)
        self.assertEqual(snapshots, {self.snapshot_id}, "alle Dateien aus demselben Snapshot")

    def test_T66_T69_T70_grid_units_scales_and_full_labels(self) -> None:
        sys.path.insert(0, str(REPO / "backend"))
        from traktien.util.isin import make_isin

        isins = ",".join(make_isin(f"ZZ{n:09d}") for n in (1, 31, 61, 91, 121, 151))
        page = self.page()
        self.go(page, f"/raster?quelle=isins&isins={isins}&skala=kurs&h=30")
        tiles = page.locator(".tiles > li")
        expect(tiles).to_have_count(6)
        expect(page.get_by_text("Originalkurs in Notierungswährung, Skala je Kachel automatisch", exact=False)).to_be_visible()
        for k in range(6):
            expect(tiles.nth(k).locator(".tile-figs")).to_contain_text(re.compile(r"Kurs\s+\d"))
        units = set()
        for text in tiles.locator(".tile-figs").all_inner_texts():
            match = re.search(r"Kurs\s+[\d.,]+\s+([A-Za-z]+)", _plain(text))
            self.assertIsNotNone(match, f"Kurs ohne Einheit: {text!r}")
            units.add(match.group(1))
        self.assertGreaterEqual(len(units), 3, f"verschiedene Währungen erwartet: {units}")
        # T70: voller Name, ISIN, Zeitraum und Stand lesbar
        clipped = page.evaluate(
            """() => [...document.querySelectorAll('.tiles > li')].filter((tile) => {
                const name = tile.querySelector('.tile-name');
                const r = name.getBoundingClientRect();
                const t = tile.getBoundingClientRect();
                return getComputedStyle(name).textOverflow === 'ellipsis' || r.right > t.right + 0.5 || !tile.querySelector('.isin-code');
              }).length"""
        )
        self.assertEqual(clipped, 0)
        for text in tiles.locator(".tile-foot").all_inner_texts():
            self.assertRegex(text, r"\d{2}\.\d{2}\.\d{4} – \d{2}\.\d{2}\.\d{4}")
        expect(page.get_by_text("Kursstand 12.10.2026", exact=False).first).to_be_visible()
        # T69: Skalen sind unterscheidbar und bleiben nachvollziehbar
        page.get_by_role("radio", name="Index, je Kachel", exact=True).click()
        expect(page.get_by_text("die Steilheit ist zwischen Kacheln nicht vergleichbar", exact=False)).to_be_visible()
        page.reload()
        page.wait_for_load_state("networkidle")
        expect(page.get_by_role("radio", name="Index, je Kachel", exact=True)).to_have_attribute("aria-checked", "true")
        page.get_by_role("radio", name="Vergleichbar (Index)", exact=True).click()
        expect(page.get_by_text("Index mit Startwert 100 und gemeinsamer Skala", exact=False)).to_be_visible()
        # T66: gemeinsamer Vergleich nur als Index, nie als gemischte absolute Achse
        page.get_by_role("radio", name="Gemeinsam", exact=True).click()
        expect(page.get_by_text("100 = echter Schlusskurs am gemeinsamen Basistag", exact=False)).to_be_visible()

    def test_T71_large_selection_is_paged_and_loads_only_visible_series(self) -> None:
        page = self.page()
        requests: list[str] = []
        page.on("request", lambda r: requests.append(r.url) if "/series/" in r.url else None)
        self.go(page, "/raster?quelle=alle")
        expect(page.locator(".tiles > li")).to_have_count(12)
        expect(page.locator(".tiles .mini").nth(11)).to_be_visible()
        page.wait_for_load_state("networkidle")
        first_page = set(requests)
        self.assertLessEqual(len(requests), 12, "nur sichtbare Kacheln laden Kurse")
        info = page.locator(".pager-info").first.inner_text()
        pages = int(info.rsplit(" ", 1)[1])
        self.assertGreater(pages, 10)
        page.get_by_role("navigation", name="Seiten des Rasters").get_by_role("button", name="Nächste").click()
        self.wait_until(page, "/[?&]seite=2(&|$)/.test(location.hash)")
        expect(page.locator(".tiles .mini").nth(11)).to_be_visible()
        page.wait_for_load_state("networkidle")
        second_page = set(requests) - first_page
        self.assertLessEqual(len(requests), 24)
        self.assertLessEqual(len(second_page), 12)
        self.assertTrue(second_page, "Seite 2 lädt eigene Kurse")

    def test_T72_T74_no_live_claim_and_history_without_live_feed(self) -> None:
        page = self.page()
        self.go(page, "/aktie/ZZ0000000719?h=30")
        expect(page.locator("figure.chart")).to_be_visible()
        expect(page.get_by_text("keine Live- oder Intradayquelle eingerichtet", exact=False)).to_be_visible()
        body = page.locator("body").inner_text()
        self.assertNotIn("Echtzeit", body)
        self.go(page, "/raster")
        expect(page.locator(".tiles .mini").first).to_be_visible()

    def test_T75_T78_tooltip_table_figure_and_png_use_same_prices(self) -> None:
        page = self.page()
        page.add_init_script(
            """(() => {
                window.__pngTexts = [];
                const original = CanvasRenderingContext2D.prototype.fillText;
                CanvasRenderingContext2D.prototype.fillText = function (text, ...rest) {
                  window.__pngTexts.push(String(text));
                  return original.call(this, text, ...rest);
                };
              })();"""
        )
        self.go(page, "/ranking?h=30&w=0")
        page.locator("ol.rows > li .row-link").first.click()
        page.wait_for_url("**/#/aktie/**")
        figure = page.locator(".fig .pct").first
        expect(figure).to_be_visible()
        published = _plain(figure.inner_text())
        hit = page.locator(".chart-surface .hit")
        hit.focus()
        page.keyboard.press("End")
        last_tip = page.locator(".chart-surface .tooltip strong").inner_text()
        page.keyboard.press("Home")
        expect(page.locator(".chart-surface .tooltip strong")).not_to_have_text(last_tip)
        first_tip = page.locator(".chart-surface .tooltip strong").inner_text()
        page.get_by_role("button", name="Kurse als Tabelle").click()
        closes = page.locator(".disclosure-body table tbody tr td:nth-child(2)").all_inner_texts()
        self.assertGreater(len(closes), 15)
        self.assertAlmostEqual(_number(last_tip), _number(closes[0]), places=6)  # Tabelle: neuester Kurs oben
        self.assertAlmostEqual(_number(first_tip), _number(closes[-1]), places=6)
        computed = 100 * (_number(closes[0]) / _number(closes[-1]) - 1)
        tolerance = (100 + abs(computed)) * (0.005 / _number(closes[-1]) + 0.005 / _number(closes[0])) + 0.006
        self.assertLess(abs(computed - _number(published)), tolerance, "Kennzahl passt zu den gezeigten Kursen")
        with page.expect_download():
            page.get_by_role("button", name="Als PNG speichern").click()
        drawn = _plain(" ".join(page.evaluate("window.__pngTexts")))
        self.assertIn("Kursstand 12.10.2026", drawn)
        self.assertIn(self.snapshot_id, drawn)
        self.assertIn("keine Liveansicht", drawn)
        self.assertIn("DEMO – synthetische Testdaten", drawn, "T60: auch der Export ist als DEMO erkennbar")
        self.assertIn(f"Kursrendite {published}", drawn)

    def test_T60_demo_is_marked_in_every_view(self) -> None:
        page = self.page()
        for route in ("/", "/rendite", "/ranking", "/vergleich", "/aktien", "/haeufig", "/raster", "/aktie/ZZ0000000719?h=30", "/watchlist", "/status", "/methodik"):
            self.go(page, route)
            expect(page.locator(".stand-chip .badge-demo"), f"DEMO-Kennzeichen auf {route}").to_have_text("DEMO")

    def test_T77_zoom_pinch_tap_and_back_on_touch_viewport(self) -> None:
        page = self.page()
        self.go(page, "/ranking?h=90&w=0")
        rows = page.locator("ol.rows > li")
        expect(rows).to_have_count(10)
        rows.nth(7).scroll_into_view_if_needed()
        page.wait_for_timeout(200)
        y_before = page.evaluate("window.scrollY")
        self.assertGreater(y_before, 200)
        rows.nth(7).locator(".row-link").click()
        page.wait_for_url("**/#/aktie/**")
        expect(page.locator("figure.chart")).to_be_visible()
        page.get_by_role("button", name="Vergrößern").click()
        expect(page.locator(".chart-zoom-note")).to_contain_text("Ausschnitt")
        page.get_by_role("button", name="Ansicht zurücksetzen").click()
        expect(page.locator(".chart-zoom-note")).to_have_count(0)
        box = page.locator(".chart-surface .hit").bounding_box()
        cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
        page.touchscreen.tap(cx, cy)
        expect(page.locator(".chart-surface .tooltip")).to_contain_text("Schlusskurs")
        cdp = page.context.new_cdp_session(page)

        def touch(kind: str, points: list[tuple[float, float]]) -> None:
            cdp.send("Input.dispatchTouchEvent", {"type": kind, "touchPoints": [{"x": x, "y": y, "id": i} for i, (x, y) in enumerate(points)]})

        touch("touchStart", [(cx - 25, cy), (cx + 25, cy)])
        for step in range(1, 7):
            touch("touchMove", [(cx - 25 - 18 * step, cy), (cx + 25 + 18 * step, cy)])
        touch("touchEnd", [])
        expect(page.locator(".chart-zoom-note")).to_contain_text("Ausschnitt")
        page.go_back()
        page.wait_for_url("**/#/ranking**")
        expect(rows).to_have_count(10)
        self.wait_until(page, f"Math.abs(window.scrollY - {y_before}) < 60", timeout=5)

    def test_T99_ranking_grid_and_csv_use_same_filters_and_snapshot(self) -> None:
        page = self.page()
        self.go(page, "/ranking?h=30&w=60&p=common_trend")
        expect(page.locator("ol.rows > li")).to_have_count(10)
        ranking = page.locator("ol.rows > li .isin-code").all_inner_texts()
        with page.expect_download() as info:
            page.get_by_role("button", name="CSV").click()
        csv_text = Path(info.value.path()).read_text(encoding="utf-8-sig")
        self.assertIn("gleiches Feld", csv_text)
        self.assertIn(self.snapshot_id, csv_text)
        csv_isins = [line.split(";")[2] for line in csv_text.splitlines() if line[:1].isdigit()]
        self.assertEqual(csv_isins[:10], ranking)
        page.get_by_role("button", name="Im Chart-Raster öffnen").click()
        page.wait_for_url("**/#/raster**")
        expect(page.locator(".tiles > li")).to_have_count(10)
        self.assertEqual(page.locator(".tiles > li .isin-code").all_inner_texts(), ranking)
        expect(page.get_by_text("60 % Gleichmäßigkeit · 40 % Rendite, gleiches Feld)", exact=False)).to_be_visible()
        expect(page.get_by_role("checkbox", name=re.compile("Gleiches Vergleichsfeld"))).to_be_checked()

    def test_T100_all_windows_weights_and_main_lists_reachable(self) -> None:
        page = self.page()
        self.go(page, "/rendite?z=alle")
        hrefs = page.locator("ol.window-list > li .row-name[href]").evaluate_all("(els) => els.map((a) => a.getAttribute('href'))")
        windows = {int(re.search(r"[?&]h=(\d+)", href).group(1)) for href in hrefs}
        self.assertEqual(windows, set(range(1, 91)), "jeder Zeitraum erreichbar")
        self.go(page, "/ranking?h=30&w=60")
        ruler = page.locator(".ruler-range")
        self.assertEqual((ruler.get_attribute("min"), ruler.get_attribute("max"), ruler.get_attribute("step")), ("1", "90", "1"))
        ruler.focus()
        page.keyboard.press("End")
        self.wait_until(page, "/[?&]h=90(&|$)/.test(location.hash)")
        page.keyboard.press("Home")
        self.wait_until(page, "/[?&]h=1(&|$)/.test(location.hash)")
        page.get_by_role("button", name="Einen Tag mehr").click()
        self.wait_until(page, "/[?&]h=2(&|$)/.test(location.hash)")
        weights = page.locator(".weight-range")
        weights.focus()
        page.keyboard.press("Home")
        self.wait_until(page, "/[?&]w=0(&|$)/.test(location.hash)")
        for w in range(10, 101, 10):
            page.keyboard.press("ArrowRight")
            self.wait_until(page, f"/[?&]w={w}(&|$)/.test(location.hash)")
            expect(page.locator(".weight-readout")).to_contain_text(f"{w} % Gleichmäßigkeit")
        nav = page.get_by_role("navigation", name="Hauptnavigation")
        nav.get_by_role("link", name="Rendite").click()
        expect(page.locator("ol.window-list > li")).to_have_count(90)
        nav.get_by_role("link", name="Analyse").click()
        page.locator(".tool-list a", has_text="Häufigste Aktien").click()
        expect(page.locator("table.gfreq tbody tr").first).to_be_visible()

    # ------------------------------------------------------- Auftrag vom 13.10.2026 (Version 1.5)

    def test_spec19_fixed_chips_select_exact_calendar_window(self) -> None:
        """Prüfung 19: Jede der zehn festen Schaltflächen wählt genau ihr Kalenderfenster; Rangliste, Kursrendite,
        Gruppe, Gewichtung und Kursgrafik wechseln gemeinsam – Sollwerte aus den Fensterdateien des Stands."""
        isins = self.snap("instruments.bin")["isin"]
        page = self.page()
        self.go(page, "/ranking?h=90&w=60&p=native")
        chips = page.get_by_role("group", name="Zeitraum wählen (Kalendertage)")
        expect(chips.get_by_role("button")).to_have_count(10)
        self.assertEqual([_plain(t).split()[0] for t in chips.get_by_role("button").all_inner_texts()], [str(h) for h in FIXED])
        expect(page.get_by_label("Zeitraum in Kalendertagen (1 bis 90)")).to_be_visible()  # freier Zeitraum 1–90
        for h in FIXED:
            chips.get_by_role("button", name=f"{h} Tage", exact=True).click()
            self.wait_until(page, f"/[?&]h={h}(&|$)/.test(location.hash) && /[?&]w=60(&|$)/.test(location.hash)")
            expect(chips.locator("[aria-pressed=true]")).to_have_count(1)
            expect(chips.get_by_role("button", name=f"{h} Tage", exact=True)).to_have_attribute("aria-pressed", "true")
            expect(page.locator(".ruler-number")).to_have_text(str(h))
            win = self.snap(f"windows/{h}.full.bin")
            self.assertEqual(win["cutoff_day"] - win["target_start_day"], h, "Kalendertage, keine Sitzungen")
            expect(page.locator(".ruler-context")).to_contain_text(self.day(win["target_start_day"]))
            order = self.order(win, "a", 60)
            if not order:
                expect(page.get_by_text("Keine Rangliste für diese Auswahl")).to_be_visible()
                expect(page.get_by_text("Für die Gleichmäßigkeit sind mindestens 15 echte Tageskurse nötig", exact=False)).to_be_visible()
                continue
            first = page.locator("ol.rows > li").first
            expect(first.locator(".isin-code")).to_have_text(isins[order[0]])
            pos = win["m"]["idx"].index(order[0])
            self.assertAlmostEqual(_number(first.locator(".row-figs .pct").inner_text()), 100 * win["m"]["r"][pos], delta=0.006)
            expect(first.locator(".row-figs")).to_contain_text("Rangscore")
        self.assertTrue(any(not self.order(self.snap(f"windows/{h}.full.bin"), "a", 60) for h in FIXED), "kurze Fenster ohne Gleichmäßigkeit")
        # Gruppe B und reine Rendite: Gruppe und Gewichtung bleiben beim Zeitraumwechsel erhalten
        page.get_by_role("radio", name="B: Ø Umsatz ≥ 10 Mio. USD").click()
        self.wait_until(page, "location.hash.includes('g=b')")
        self.go(page, page.evaluate("location.hash").replace("#", "").replace("w=60", "w=0"))
        for h in (7, 90):
            chips.get_by_role("button", name=f"{h} Tage", exact=True).click()
            self.wait_until(page, f"/[?&]h={h}(&|$)/.test(location.hash) && location.hash.includes('g=b') && /[?&]w=0(&|$)/.test(location.hash)")
            win = self.snap(f"windows/{h}.full.bin")
            order = self.order(win, "b", 0)
            expect(page.locator("ol.rows > li").first.locator(".isin-code")).to_have_text(isins[order[0]])
        # Freie Eingabe 1–90 bleibt zusätzlich bestehen; keine Schnellwahl aktiv
        free = page.get_by_label("Zeitraum in Kalendertagen (1 bis 90)")
        free.fill("37")
        free.blur()
        self.wait_until(page, "/[?&]h=37(&|$)/.test(location.hash)")
        expect(chips.locator("[aria-pressed=true]")).to_have_count(0)
        # Einzelchart: dieselben Schaltflächen, die Grafik zeigt genau das gewählte Fenster dieser Aktie
        windows = {h: self.snap(f"windows/{h}.full.bin") for h in FIXED}
        common = set.intersection(*(set(w["m"]["idx"]) for w in windows.values()))
        idx = next(i for i in windows[90]["orders"]["v0"] if i in common)
        self.go(page, f"/aktie/{isins[idx]}?h=90")
        chart_chips = page.get_by_role("group", name="Zeitraum wählen (Kalendertage)")
        for h in FIXED:
            chart_chips.get_by_role("button", name=f"{h} Tage", exact=True).click()
            self.wait_until(page, f"/[?&]h={h}(&|$)/.test(location.hash)")
            m = windows[h]["m"]
            pos = m["idx"].index(idx)
            start, end, n = self.day(m["start"][pos]), self.day(windows[h]["cutoff_day"]), m["n"][pos]
            chart = page.locator("figure.chart").first
            expect(chart).to_have_attribute("aria-label", re.compile(rf"am {re.escape(start)} und .* am {re.escape(end)}, Veränderung .*\b{n} echte Tageskurse"))
            change = re.search(r"Veränderung (\S+) %", _plain(chart.get_attribute("aria-label"))).group(1)
            self.assertAlmostEqual(_number(change), 100 * m["r"][pos], delta=0.006, msg=f"Kursgrafik {h} Tage")
            expect(page.get_by_text(f"Kursrendite vom {start} bis {end}", exact=False).first).to_be_visible()
        self.shot(page, "23_schnellwahl_chart")
        # Kursraster: dieselbe Schnellwahl
        self.go(page, "/raster?h=90")
        page.get_by_role("group", name="Zeitraum wählen (Kalendertage)").get_by_role("button", name="21 Tage", exact=True).click()
        self.wait_until(page, "/[?&]h=21(&|$)/.test(location.hash)")
        expect(page.locator(".tiles > li").first).to_be_visible()

    def test_spec20_winners_by_window_match_full_rankings(self) -> None:
        """Prüfung 20: „Sieger nach Zeitraum“ – zehn Zeilen, A und B nebeneinander; jede Zelle = Platz 1 der
        vollständigen Rangliste desselben Fensters, je Gewichtung; eigene Zählung über genau diese zehn Zeilen."""
        isins = self.snap("instruments.bin")["isin"]
        page = self.page()
        self.go(page, "/sieger?w=60")
        rows = page.locator("ol.tenw > li")
        expect(rows).to_have_count(10)
        self.assertEqual([int(t) for t in rows.locator(".tenw-days").all_inner_texts()], list(FIXED))
        weights = page.get_by_role("radiogroup", name="Gewichtung Gleichmäßigkeit/Kursrendite")
        expect(weights.get_by_role("radio")).to_have_count(11)
        expect(weights.get_by_role("radio", name="60/40")).to_have_attribute("aria-checked", "true")
        self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"), page.evaluate("window.innerWidth"), "Karten statt überbreiter Tabelle")
        self.shot(page, "24_sieger_nach_zeitraum")
        for weight in (60, 0, 50, 100, 10):
            if weight != 60:
                weights.get_by_role("radio", name=f"{weight}/{100 - weight}").click()
                self.wait_until(page, f"/[?&]w={weight}(&|$)/.test(location.hash)")
            for k, h in enumerate(FIXED):
                win = self.snap(f"windows/{h}.full.bin")
                for group in ("a", "b"):
                    cell = rows.nth(k).locator(f".tenw-{group}")
                    order = self.order(win, group, weight)
                    if not order:
                        expect(cell).to_have_class(re.compile("is-empty"))
                        if weight and h <= 14:
                            expect(cell).to_contain_text("Gleichmäßigkeit nicht berechenbar")
                        continue
                    expect(cell.locator(".gcell-isin")).to_have_text(isins[order[0]])
                    pos = win["m"]["idx"].index(order[0])
                    self.assertAlmostEqual(_number(cell.locator(".pct").first.inner_text()), 100 * win["m"]["r"][pos], delta=0.006, msg=f"{group} {h} Tage {weight}")
                    if weight:
                        expect(cell).to_contain_text("Rangscore")
        # kurze gewichtete Fenster: Hinweis und Weg zum 0/100-Renditesieger, kein Ersatz durch ein längeres Fenster
        weights.get_by_role("radio", name="60/40").click()
        self.wait_until(page, "/[?&]w=60(&|$)/.test(location.hash)")
        first_row = rows.nth(0)
        expect(first_row.locator(".tenw-a")).to_contain_text("Gleichmäßigkeit nicht berechenbar")
        expect(first_row.locator(".tenw-a .gcell-isin")).to_have_count(0)
        # Antippen: Start, Ende, Schlusskurse und Referenzmarkt
        k = next(i for i, h in enumerate(FIXED) if self.order(self.snap(f"windows/{h}.full.bin"), "a", 60))
        h = FIXED[k]
        win = self.snap(f"windows/{h}.full.bin")
        idx = self.order(win, "a", 60)[0]
        pos = win["m"]["idx"].index(idx)
        rows.nth(k).locator(".tenw-a .tenw-pick").click()
        detail = rows.nth(k).locator(".tenw-a .tenw-detail")
        expect(detail).to_contain_text(self.day(win["m"]["start"][pos]))
        expect(detail).to_contain_text(self.day(win["cutoff_day"]))
        expect(detail.locator(".kv-row", has_text="Schlusskurse im Fenster")).to_contain_text(str(win["m"]["n"][pos]))
        expect(detail.locator(".kv-row", has_text="Referenzmarkt")).not_to_contain_text("–")
        detail.get_by_role("link", name="Ganze Rangliste").click()
        self.wait_until(page, f"location.hash.startsWith('#/ranking') && /[?&]h={h}(&|$)/.test(location.hash) && /[?&]w=60(&|$)/.test(location.hash)")
        expect(page.locator("ol.rows > li").first.locator(".isin-code")).to_have_text(isins[idx])
        page.go_back()
        # eigene Zählung über genau diese zehn Zeiträume, getrennt benannt
        expect(page.get_by_role("heading", name="Zählung nur über diese zehn Zeiträume")).to_be_visible()
        expected: dict[int, list[int]] = {}
        for h in FIXED:
            win = self.snap(f"windows/{h}.full.bin")
            for g, col in (("a", 0), ("b", 1)):
                order = self.order(win, g, 60)
                if order:
                    expected.setdefault(order[0], [0, 0])[col] += 1
        repeated = {isins[i]: c for i, c in expected.items() if sum(c) >= 2}
        table = page.locator("table.tenw-count tbody tr")
        expect(table).to_have_count(len(repeated))
        if repeated:
            self.assertLessEqual(page.locator("table.tenw-count").evaluate("el => el.closest('.table-wrap').scrollWidth - el.closest('.table-wrap').clientWidth"), 0)
        for row in table.all():
            isin = row.locator(".gcell-isin").inner_text()
            self.assertEqual([int(row.locator("td").nth(0).inner_text()), int(row.locator("td").nth(1).inner_text())], repeated[isin])

    def test_report_1_30_tables_matrix_marking_frequency_and_csv(self) -> None:
        """Bericht 1–30 (ab 1.8.1) wie die Berichtsdatei: vier Tabellen untereinander, jede Zelle = Platz 1 der
        Übersicht desselben Stands (A und B), kurze leere Zeiträume zusammengefasst, Matrix mit vier
        Gewichtungen, Hervorheben einer ISIN auf der ganzen Seite, Häufigkeit und CSV mit 240 Kombinationen."""
        inst = self.snap("instruments.bin")
        isins = inst["isin"]
        ov = self.snap("overview.bin")

        def top(group: str, weight: int, h: int) -> int | None:
            rows = (ov["v0"] if weight == 0 else ov["u"][str(weight)]) if group == "a" else (ov["v0l"] if weight == 0 else ov["ul"][str(weight)])
            row = rows[h - 1]
            return None if row.get("empty") or row.get("idx") is None else row["idx"]

        def name(idx: int) -> str:
            return inst["name"][idx] or inst["tr_name"][idx] or isins[idx]

        page = self.page()
        self.go(page, "/")
        page.get_by_role("navigation", name="Direkte Einstiege").get_by_role("link", name=re.compile("Bericht 1–30 Tage")).click()
        self.wait_until(page, "location.hash.startsWith('#/bericht')")
        expect(page.locator(".rep-stats > div")).to_have_count(4)
        expect(page.locator("table.rep-table")).to_have_count(4)
        self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"), page.evaluate("window.innerWidth"), "keine seitliche Verschiebung")
        self.shot(page, "40_bericht_1_30")
        tables = page.evaluate(
            """() => [...document.querySelectorAll('table.rep-table')].map(t => [...t.querySelectorAll('tbody tr')].map(tr => [
                 tr.querySelector('th').textContent.trim(), tr.classList.contains('rep-gap'),
                 [...tr.querySelectorAll('td')].map(td => td.querySelector('.rep-isin')?.textContent ?? null)]))"""
        )
        for weight, rows in zip((0, 40, 50, 60), tables):
            seen: set[int] = set()
            for label, gap, cells in rows:
                if gap:
                    a, _, b = label.partition("–")
                    span = range(int(a), int(b or a) + 1)
                    for h in span:
                        self.assertEqual((top("a", weight, h), top("b", weight, h)), (None, None), f"{weight}: {h} Tage zusammengefasst, aber berechnet")
                    seen.update(span)
                    continue
                h = int(label)
                seen.add(h)
                for group, isin in zip(("a", "b"), cells):
                    idx = top(group, weight, h)
                    self.assertEqual(isin, None if idx is None else isins[idx], f"{weight}/{100 - weight}, {h} Tage, Gruppe {group.upper()}")
            self.assertEqual(seen, set(range(1, 31)), f"{weight}: jeder Zeitraum 1–30 genau einmal")
        first = page.locator("table.rep-table").first.locator("tbody tr").first
        win = self.snap("windows/1.full.bin")
        idx = top("a", 0, 1)
        self.assertAlmostEqual(_number(first.locator("td").first.locator(".pct").inner_text()), 100 * win["m"]["r"][win["m"]["idx"].index(idx)], delta=0.006)

        # eine Gewichtung allein
        page.get_by_role("radiogroup", name="Gewichtung Gleichmäßigkeit/Kursrendite").get_by_role("radio", name="50/50", exact=True).click()
        self.wait_until(page, "/[?&]w=50(&|$)/.test(location.hash)")
        expect(page.locator("table.rep-table")).to_have_count(1)
        expect(page.locator("#bericht-w50")).to_be_visible()

        # Matrix: vier Gewichtungen nebeneinander, Gruppe wählbar
        matrix = page.locator("table.rep-matrix tbody tr")
        expect(matrix).to_have_count(30)
        for group in ("a", "b"):
            if group == "b":
                page.get_by_role("radiogroup", name="Gruppe", exact=True).get_by_role("radio", name=re.compile("^B ·")).click()
                self.wait_until(page, "/[?&]mg=b(&|$)/.test(location.hash)")
            names = page.evaluate("() => [...document.querySelectorAll('table.rep-matrix tbody tr:last-child td')].map(td => td.querySelector('.rm-name')?.textContent ?? null)")
            expected = [None if top(group, w, 30) is None else name(top(group, w, 30)) for w in (0, 40, 50, 60)]
            self.assertEqual(names, expected, f"Matrix Gruppe {group.upper()}, 30 Tage")
        self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"), page.evaluate("window.innerWidth"), "Matrix ohne seitliches Wischen")

        # Am häufigsten auf Platz 1: Zählung über A und B, vier Gewichtungen, 1–30 Tage
        counts: dict[int, int] = {}
        for group in ("a", "b"):
            for w in (0, 40, 50, 60):
                for h in range(1, 31):
                    idx = top(group, w, h)
                    if idx is not None:
                        counts[idx] = counts.get(idx, 0) + 1
        leader = sorted(counts, key=lambda i: (-counts[i], isins[i]))[0]
        leaders = page.locator(".rep-leaders ol.rep-freq > li")
        expect(leaders.first.locator("small").first).to_have_text(isins[leader])
        expect(leaders.first.locator(".rep-lead-count b")).to_have_text(f"{counts[leader]}×")
        # Gesamtwertung (Blick nach vorn) als Kästchen hinter dem Namen – Wert aus dem Signal-Stand
        from traktien.util import crypto

        sid = json.loads((self.site / "data" / "status.json").read_text(encoding="utf-8"))["signale"]["id"]
        sig = json.loads(crypto.unpack((self.site / "data" / "signale" / sid / "signale.bin").read_bytes(), None, f"signale/{sid}/signale.bin"))
        if isins[leader] in sig["isin"] and sig.get("gesamt"):
            value = sig["gesamt"][sig["isin"].index(isins[leader])]
            if value is not None:
                shown = int(value + 0.5)  # wie Math.round in der App (Python rundet .5 auf gerade Zahlen)
                expect(leaders.first.locator(".total strong")).to_have_text(str(shown))
                expect(leaders.first.locator(".total")).to_have_attribute("aria-label", re.compile(f"^Gesamtwertung {shown} von 100"))
        expect(page.locator("table.rep-table .rep-name .total").first).to_be_visible()

        # Hervorheben: alle Vorkommen in Tabelle (50/50, A und B) und Matrix (Gruppe B)
        leaders.first.get_by_role("button").click()
        self.wait_until(page, f"location.hash.includes('m={isins[leader]}')")
        bar = page.locator(".rep-markbar")
        expect(bar).to_contain_text(name(leader))
        expect(bar).to_contain_text(f"{counts[leader]}× Platz 1 in 1–30 Tagen")
        hits = sum(1 for h in range(1, 31) for g in ("a", "b") if top(g, 50, h) == leader) + sum(1 for h in range(1, 31) for w in (0, 40, 50, 60) if top("b", w, h) == leader)
        expect(page.locator("td.is-marked")).to_have_count(hits)
        if hits:
            bar.get_by_role("button", name="Nächstes Vorkommen").click()
            self.wait_until(page, "[...document.querySelectorAll('td.is-marked')].some(el => { const r = el.getBoundingClientRect(); return r.top >= 56 && r.top < window.innerHeight - 120; })")
        self.shot(page, "41_bericht_markiert")
        bar.get_by_role("button", name="Markierung entfernen").click()
        expect(page.locator(".rep-markbar")).to_have_count(0)
        expect(page.locator("td.is-marked")).to_have_count(0)

        # Welche Aktie erscheint am häufigsten? (Fundstellen Top 10)
        freq = page.locator("#bericht-haeufig ol.rep-freq > li")
        expect(freq.first).to_be_visible()
        self.assertLessEqual(freq.count(), 30)
        self.assertEqual(int(freq.first.locator(".rep-freq-nums b").inner_text()), counts[leader], "Platz 1 wie in der Übersicht")

        # CSV: alle 30 × 4 × 2 Spitzenreiter
        with page.expect_download() as info:
            page.get_by_role("button", name="Bericht herunterladen (CSV)").click()
        lines = Path(info.value.path()).read_bytes().decode("utf-8").lstrip("﻿").strip().split("\r\n")
        header = lines.index("Gewichtung;Tage;Gruppe;Unternehmen;ISIN;Kursrendite;Score;R²;Start;Ende;Einheit;Hinweis")
        body = lines[header + 1 :]
        self.assertEqual(len(body), 240)
        self.assertTrue(body[0].startswith(f"0/100;1;A;"), body[0])
        self.assertIn(isins[top("a", 0, 1)], body[0])
        self.assertIn(self.snapshot_id, "\n".join(lines[:header]))

    def test_frequency_filters_order_counts_and_exports(self) -> None:
        """Häufigste Aktien: Filter Gruppe, Gewichtungen, Zeitspanne, identische Fenster; zwei Sortierungen;
        Zähler und Nenner wie aus den Serverdaten nachgezählt; CSV/JSON mit Filterangaben."""
        isins = self.snap("instruments.bin")["isin"]
        freq = self.snap("frequency.bin")

        def counts(groups: str, weights, lo: int, hi: int) -> tuple[dict[str, list[int]], int]:
            table: dict[str, list[int]] = {}
            denominator = 0
            for g in groups:
                for w in weights:
                    occ = (freq["occ"]["v0"] if w == 0 else freq["occ"]["u"][str(w)]) if g == "a" else (freq["occ"]["v0l"] if w == 0 else freq["occ"]["ul"][str(w)])
                    sizes = (freq["M"]["v0"] if w == 0 else freq["M"]["u"]) if g == "a" else (freq["M"]["v0l"] if w == 0 else freq["M"]["ul"])
                    denominator += sum(1 for h in range(lo, hi + 1) if sizes[h - 1] > 0)
                    for h, rank, idx in zip(occ["h"], occ["rank"], occ["idx"]):
                        if lo <= h <= hi:
                            entry = table.setdefault(isins[idx], [0, 0, 0])
                            entry[0] += rank == 1
                            entry[1] += rank <= 3
                            entry[2] += rank <= 10
            return table, denominator

        def visible_rows(page) -> list[tuple[str, int, int, int]]:
            out = []
            for row in page.locator("table.gfreq tbody tr").all():
                nums = [int(_plain(t).replace(".", "")) for t in row.locator("td .gnum").all_inner_texts()]
                out.append((row.locator(".gcell-isin").inner_text(), nums[0], nums[1], nums[2]))
            return out

        page = self.page()
        self.go(page, "/haeufig")
        expect(page.get_by_role("heading", name="Häufigkeitsranking")).to_be_visible()
        overflow = "el => el.closest('.table-wrap').scrollWidth - el.closest('.table-wrap').clientWidth"
        self.assertLessEqual(page.locator("table.gfreq").evaluate(overflow), 0, "Tabelle ohne seitliches Blättern auf 384 px")
        heads = [_plain(t).replace("\u00ad", "") for t in page.locator("table.gfreq thead th").all_inner_texts()]
        for got, want in zip(heads, ["Rang", "Unternehmen, ISIN", "Platz 1", "Top 3", "Top 10", "Zugelassen"], strict=True):
            self.assertTrue(got.strip().startswith(want), f"Spalte {got!r}")
        expect(page.get_by_role("radio", name="Gewinnt am häufigsten")).to_have_attribute("aria-checked", "true")
        # Standard: Gruppe A, alle elf Gewichtungen, 1–90 Tage – Zähler und Nenner wie nachgezählt
        table, denominator = counts("a", WEIGHTS, 1, 90)
        expect(page.locator(".scope-note")).to_contain_text(f"Berechenbare Kombinationen (Nenner): A {denominator:,}".replace(",", "."))
        shown = visible_rows(page)
        self.assertGreater(len(shown), 5)
        for isin, n1, n3, n10 in shown:
            self.assertEqual([n1, n3, n10], table[isin], isin)
        self.assertEqual([r[1:] for r in shown], sorted([r[1:] for r in shown], reverse=True), "Platz 1, dann Top 3, dann Top 10")
        expect(page.locator(".mark").first).to_contain_text("↻")
        # Umschalter „Meiste Top-10-Nennungen“
        page.get_by_role("radio", name="Meiste Top-10-Nennungen").click()
        self.wait_until(page, "location.hash.includes('sort=n10')")
        shown = visible_rows(page)
        keys = [(n10, n3, n1) for _, n1, n3, n10 in shown]
        self.assertEqual(keys, sorted(keys, reverse=True), "Top 10, dann Top 3, dann Platz 1")
        best = max(table.items(), key=lambda kv: (kv[1][2], kv[1][1], kv[1][0], [-ord(c) for c in kv[0]]))
        self.assertEqual(shown[0][0], best[0])
        # nur Gewichtungen mit Gleichmäßigkeitsanteil, Spanne 31–60
        page.get_by_label("Gewichtungen").select_option("trend")
        self.wait_until(page, "location.hash.includes('gw=trend')")
        page.get_by_role("radio", name="31–60").click()
        self.wait_until(page, "location.hash.includes('von=31') && location.hash.includes('bis=60')")
        table, denominator = counts("a", WEIGHTS[1:], 31, 60)
        expect(page.locator(".scope-note")).to_contain_text("nur Gewichtungen mit Gleichmäßigkeitsanteil")
        expect(page.locator(".scope-note")).to_contain_text("Zeiträume 31–60 Tage")
        expect(page.locator(".scope-note")).to_contain_text(f"A {denominator:,}".replace(",", "."))
        for isin, n1, n3, n10 in visible_rows(page):
            self.assertEqual([n1, n3, n10], table[isin], isin)
        # ein Gewicht, beide Gruppen getrennt ausgewiesen, freie Spanne
        page.get_by_label("Gewichtungen").select_option("50")
        self.wait_until(page, "location.hash.includes('gw=50')")
        page.get_by_role("radio", name="A und B").click()
        self.wait_until(page, "location.hash.includes('gruppen=ab')")
        page.get_by_role("radio", name="Frei").click()
        page.get_by_label("von (Tage)").fill("21")
        page.get_by_label("bis (Tage)").fill("45")
        page.get_by_role("button", name="Spanne übernehmen").click()
        self.wait_until(page, "location.hash.includes('von=21') && location.hash.includes('bis=45')")
        expect(page.locator(".scope-note")).to_contain_text("B ist eine Teilmenge von A")
        self.assertLessEqual(page.locator("table.gfreq").evaluate(overflow), 0, "A und B ohne seitliches Blättern")
        expect(page.locator("table.gfreq-both tbody tr").first.locator(".gsplit").nth(1)).to_contain_text("B ")
        table_ab, denominator_ab = counts("ab", [50], 21, 45)
        for isin, n1, n3, n10 in visible_rows(page):
            self.assertEqual([n1, n3, n10], table_ab[isin], isin)
        # identische Kursfenster nur einmal: Nenner sinkt nie, Zähler höchstens gleich
        before = {r[0]: r[1:] for r in visible_rows(page)}
        page.get_by_label("Identische Kursfenster nur einmal zählen").check()
        self.wait_until(page, "location.hash.includes('einmal=1')")
        expect(page.locator(".scope-note")).to_contain_text("gleicher Bestand aus ISIN und tatsächlichem Startdatum")
        for isin, n1, n3, n10 in visible_rows(page):
            if isin in before:
                self.assertTrue(all(a <= b for a, b in zip((n1, n3, n10), before[isin])), isin)
        # Exporte mit Filterangaben
        with page.expect_download() as info:
            page.locator(".gfreq-section").get_by_role("button", name="CSV").click()
        csv_text = Path(info.value.path()).read_text(encoding="utf-8-sig")
        for needle in ("Gruppe A und B zusammen", "# Gewichtungen;nur 50/50", "# Zeiträume;21–45 Kalendertage", "# Zählweise;identische Kursfenster einmal", self.snapshot_id):
            self.assertIn(needle, csv_text)
        self.assertIn("Rang;Unternehmen;ISIN;Platz 1;Top 3;Top 10;Zugelassene Kombinationen", csv_text)
        with page.expect_download() as info:
            page.locator(".gfreq-section").get_by_role("button", name="JSON").click()
        data = json.loads(Path(info.value.path()).read_text(encoding="utf-8"))
        self.assertEqual(data["format"], "tr-haeufigkeit/1")
        self.assertEqual(data["meta"]["Snapshot"], self.snapshot_id)
        self.assertTrue(all(set(e) >= {"rang", "name", "isin", "gruppe_a", "gruppe_b"} for e in data["eintraege"]))
        self.shot(page, "25_haeufigste_aktien")

    def test_matrix_jump_and_export(self) -> None:
        """Matrix 1–90 × 11: Sprung per Schnellwahl, Export als CSV und JSON mit allen 990 Zellen der Gruppe."""
        page = self.page()
        self.go(page, "/matrix")
        page.get_by_role("group", name="Zu Zeitraum springen").get_by_role("button", name="70 Tage", exact=True).click()
        self.wait_until(page, "location.hash.includes('zeile=70')")
        row = page.locator("table.gmatrix tbody tr[data-h='70']")
        expect(row).to_have_class(re.compile("is-jump"))
        expect(row).to_be_in_viewport()
        expect(row.locator("th.gday .jump-note")).to_have_text("gewählt")
        expect(page.locator("table.gmatrix .jump-note")).to_have_count(1)
        with page.expect_download() as info:
            page.get_by_role("button", name="Matrix als JSON").click()
        data = json.loads(Path(info.value.path()).read_text(encoding="utf-8"))
        self.assertEqual(data["format"], "tr-matrix/1")
        self.assertEqual(len(data["zellen"]), 990)
        overview = self.snap("overview.bin")
        for cell in data["zellen"][:: 37]:
            h, w = cell["tage"], int(cell["gewichtung"].split("/")[0])
            ref = overview["v0"][h - 1] if w == 0 else overview["u"][str(w)][h - 1]
            if "idx" in ref:
                self.assertEqual(cell["isin"], self.snap("instruments.bin")["isin"][ref["idx"]])
            else:
                self.assertIsNone(cell["isin"])
                self.assertTrue(cell["nicht_berechenbar"])
        with page.expect_download() as info:
            page.get_by_role("button", name="Matrix als CSV").click()
        csv_text = Path(info.value.path()).read_text(encoding="utf-8-sig")
        self.assertIn("Tage;Gewichtung;Unternehmen;ISIN;Kursrendite %;Rangscore;R²", csv_text)
        self.assertEqual(sum(1 for line in csv_text.splitlines() if line[:1].isdigit()), 990)

    def test_watchlist_isin_import_export_and_merge(self) -> None:
        isins = self.snap("instruments.bin")["isin"]
        page = self.page()
        self.go(page, "/watchlist")
        box = page.get_by_label("ISINs einfügen – eine je Zeile oder durch Komma getrennt")
        box.fill(f"{isins[3]}, {isins[5]}\n{isins[3]}; XX1234567890 {isins[5].lower()}")
        page.get_by_role("button", name="In die Watchlist übernehmen").click()
        status = page.locator("section:has(#isin-transfer) [role=status]")
        expect(status).to_contain_text("2 ISINs übernommen")
        expect(status).to_contain_text("2 doppelt eingegeben und zusammengeführt")
        expect(status).to_contain_text("XX1234567890")
        expect(page.locator("ul.rows > li")).to_have_count(2)
        box.fill(isins[3])
        page.get_by_role("button", name="In die Watchlist übernehmen").click()
        expect(status).to_contain_text("1 schon gemerkt")
        expect(page.locator("ul.rows > li")).to_have_count(2)
        with page.expect_download() as info:
            page.get_by_role("button", name="ISIN-Liste exportieren").click()
        self.assertEqual(Path(info.value.path()).read_text(encoding="utf-8").split(), [isins[3], isins[5]])
        with page.expect_download() as info:
            page.get_by_role("button", name="Mit Namen als CSV").click()
        csv_text = Path(info.value.path()).read_text(encoding="utf-8-sig")
        self.assertIn("kein Depotbestand", csv_text)
        self.assertIn(isins[5], csv_text)

    def test_start_selection_is_remembered_and_entries_open_views(self) -> None:
        isins = self.snap("instruments.bin")["isin"]
        page = self.page()
        self.go(page, "/")
        selection = page.locator("section", has=page.get_by_role("heading", name="Höchste Kursrendite – Auswahl", exact=True))
        expect(selection.get_by_role("group", name="Zeitraum wählen (Kalendertage)").get_by_role("button", name="90 Tage", exact=True)).to_have_attribute("aria-pressed", "true")
        expect(selection.get_by_role("radio", name="60/40")).to_have_attribute("aria-checked", "true")
        expect(page.locator(".coverage-counts")).to_contain_text("Berechnet")
        expect(page.locator(".coverage-counts")).to_contain_text("identifiziert")
        expect(page.locator(".coverage-counts")).to_contain_text("Einträgen der TR-Liste")
        selection.get_by_role("radio", name="50/50").click()
        selection.get_by_role("radio", name="B: Ø Umsatz ≥ 10 Mio. USD").click()
        selection.get_by_role("group", name="Zeitraum wählen (Kalendertage)").get_by_role("button", name="30 Tage", exact=True).click()
        heading = page.locator("#eigene")
        expect(heading).to_contain_text("30 Kalendertage")
        expect(heading).to_contain_text("Gruppe B")
        page.reload()
        page.wait_for_load_state("networkidle")
        expect(page.locator("#eigene")).to_contain_text("30 Kalendertage")
        expect(page.locator("#eigene")).to_contain_text("50/50")
        expect(page.locator("#eigene")).to_contain_text("Gruppe B")
        win = self.snap("windows/30.full.bin")
        expect(page.locator("ol.rows[aria-label^='Erste fünf Plätze'] > li").first.locator(".isin-code")).to_have_text(isins[self.order(win, "b", 50)[0]])
        entries = page.get_by_role("navigation", name="Direkte Einstiege")
        for name in ("Höchste Rendite", "Gleichmäßigkeit + Rendite", "Häufigste Aktien", "Kursvergleich"):
            expect(entries.get_by_role("link", name=re.compile(re.escape(name)))).to_be_visible()
        entries.get_by_role("link", name=re.compile("Gleichmäßigkeit \\+ Rendite")).click()
        self.wait_until(page, "location.hash.startsWith('#/ranking') && /[?&]h=30(&|$)/.test(location.hash) && /[?&]w=50(&|$)/.test(location.hash) && location.hash.includes('g=b')")
        page.go_back()
        page.locator("section", has=page.get_by_role("heading", name="Höchste Kursrendite – Auswahl", exact=True)).get_by_role("radio", name="0/100").click()
        expect(page.locator("#eigene")).to_contain_text("0/100")

    def test_status_shows_method_change_and_exports_metadata(self) -> None:
        page = self.page()
        self.go(page, "/status")
        expect(page.get_by_role("heading", name=re.compile("Methodenwechsel tr-methode-1.7.0 → tr-methode-1.8.0"))).to_be_visible()
        cmp = self.snap("manifest.bin")["method_comparison"]
        note = page.locator("section", has=page.get_by_role("heading", name=re.compile("Methodenwechsel"))).locator(".section-note")
        expect(note).to_contain_text(f"{cmp['paare']['neu_bewertet']:,}".replace(",", ".") + " Aktie-Zeitraum-Paare werden neu bewertet")
        expect(note).to_contain_text(f"{cmp['paare']['nicht_mehr_bewertet']:,}".replace(",", ".") + " nicht mehr")
        expect(page.locator(".kv-row", has_text="Ausgangsmodell")).to_contain_text("TR-90D-11W-two-universes-v1.1")
        expect(page.locator(".kv-row", has_text="Ausgangsmodell")).to_contain_text("Reproduktion des historischen Prüffalls offen")
        with page.expect_download() as info:
            page.get_by_role("button", name="Als JSON").click()
        data = json.loads(Path(info.value.path()).read_text(encoding="utf-8"))
        self.assertEqual(data["format"], "tr-metadaten/1")
        manifest = data["manifest"]
        self.assertEqual(manifest["snapshot_id"], self.snapshot_id)
        self.assertEqual(manifest["versions"]["method"], "tr-methode-1.8.0")
        self.assertIn("method_comparison", manifest)
        text = json.dumps(data).lower()
        for secret in ("passphrase", "api_key", "apikey", "token", PASSPHRASE.lower()):
            self.assertNotIn(secret, text, "keine Geheimnisse im Export")
        expect(page.get_by_text("Methode tr-methode-1.8.0", exact=False).first).to_be_visible()
        page.get_by_role("link", name="Regeln und Beispiele").click()
        self.wait_until(page, "location.hash === '#/methodik'")
        expect(page.get_by_role("heading", name="Methodenwechsel und Ausgangsmodell")).to_be_visible()
        expect(page.get_by_text("Fehlende Börsentage beim Kursanbieter: Ein Zeitraum bleibt bewertbar", exact=False)).to_be_visible()
        expect(page.get_by_text("ein einzelner fehlender Tag ist immer erlaubt", exact=False).first).to_be_visible()

    def test_partial_snapshot_names_missing_exchanges(self) -> None:
        """Teilstand (wie am 12.10.2026: Kursanbieter ohne Schlusskurse für Europa und Asien): jede Ansicht trägt
        „Teilstand“, die Startseite nennt die Börsen mit Namen und den Grund, Datenstand & Betrieb die Zählung."""
        from traktien.util import crypto

        rel = f"snapshots/{self.snapshot_id}/manifest.bin"
        manifest = self.snap("manifest.bin")
        partial = json.loads(json.dumps(manifest))
        delivered = list(partial["completeness"]["delivered_markets"])
        partial["completeness"].update(
            status="teilstand",
            delivered_markets=[m for m in delivered if m not in ("XETR", "XLON")],
            missing_markets=["XLON", "XETR"],
        )
        body = crypto.pack(json.dumps(partial, ensure_ascii=False).encode("utf-8"), None, rel)
        index = json.loads((self.site / "data" / "snapshots" / "index.json").read_text(encoding="utf-8"))
        for item in index["snapshots"]:
            if item["snapshot_id"] == self.snapshot_id:
                item["completeness"] = "teilstand"
        page = self.page()
        page.route(f"**/data/{rel}*", lambda route: route.fulfill(status=200, content_type="application/octet-stream", body=body))
        page.route("**/data/snapshots/index.json*", lambda route: route.fulfill(status=200, content_type="application/json", body=json.dumps(index)))
        self.go(page, "/")
        expect(page.locator(".stand-chip")).to_contain_text("Teilstand")
        note = page.locator(".stamp-partial")
        expect(note).to_contain_text("Für 2 Börsen lieferte der Kursanbieter am Stichtag keine vollständigen Schlusskurse (London, Xetra)")
        expect(note).to_contain_text("wegen fehlender Daten, nicht wegen ihrer Kursentwicklung")
        page.get_by_role("navigation", name="Hauptnavigation").get_by_role("link", name="Rendite").click()
        page.get_by_role("navigation", name="Unterbereiche").get_by_role("link", name="Gleichmäßig + Rendite").click()
        expect(page.locator(".stand-chip")).to_contain_text("Teilstand")
        self.go(page, "/status")
        expect(page.locator(".kv-row", has_text="Vollständigkeit")).to_contain_text("ohne Stichtagskurse: London, Xetra")

    def test_partial_snapshot_with_most_exchanges_missing_names_the_delivered_ones(self) -> None:
        """Wie am 12.10.2026 (Schlusskurse nur aus den USA, Australien und Neuseeland): Die Startseite nennt
        die wenigen enthaltenen Börsen statt 28 fehlender, ohne Überlauf auf 384 px; die vollständige Liste
        steht unter „Datenstand & Betrieb“."""
        from traktien.util import crypto

        rel = f"snapshots/{self.snapshot_id}/manifest.bin"
        partial = json.loads(json.dumps(self.snap("manifest.bin")))
        missing = ["ASEX", "XAMS", "XBKK", "XBRU", "XBUD", "XCSE", "XDUB", "XETR", "XFRA", "XHEL", "XHKG", "XIDX", "XJSE", "XLIS",
                   "XLON", "XMAD", "XMEX", "XMIL", "XOSL", "XPAR", "XPRA", "XSHG", "XSTO", "XSWX", "XTAE", "XTAL", "XWAR", "XWBO"]
        partial["completeness"].update(status="teilstand", delivered_markets=["XNYS", "XASX", "XNZE"], missing_markets=missing)
        body = crypto.pack(json.dumps(partial, ensure_ascii=False).encode("utf-8"), None, rel)
        page = self.page()
        page.route(f"**/data/{rel}*", lambda route: route.fulfill(status=200, content_type="application/octet-stream", body=body))
        self.go(page, "/")
        note = page.locator(".stamp-partial")
        expect(note).to_contain_text("Enthalten sind nur Aktien von 3 der 31 Börsen mit Handel am Stichtag: Australien, Neuseeland und USA.")
        expect(note).to_contain_text("Für die übrigen 28 lieferte der Kursanbieter keine vollständigen Schlusskurse.")
        expect(note).not_to_contain_text("Amsterdam")
        self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"), page.evaluate("window.innerWidth"), "Hinweis ohne Seitwärtsverschiebung")
        self.shot(page, "01c_teilstand_drei_boersen")
        self.go(page, "/status")
        row = page.locator(".kv-row", has_text="Vollständigkeit")
        expect(row).to_contain_text("3 von 31 Börsen mit Stichtagskursen")
        expect(row).to_contain_text("Amsterdam, Athen, Bangkok")
        self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"), page.evaluate("window.innerWidth"), "Liste bricht um")

    def test_encrypted_site_requires_key(self) -> None:
        page = self.page(base=self.base_enc)
        self.go(page, "/", base=self.base_enc)
        expect(page.get_by_role("heading", name="Zugangsschlüssel eingeben")).to_be_visible()
        page.locator("#passphrase").fill("falsch")
        page.get_by_role("button", name="Entsperren").click()
        expect(page.get_by_text("Der Zugangsschlüssel passt nicht", exact=False)).to_be_visible(timeout=30000)
        page.locator("#passphrase").fill(PASSPHRASE)
        page.get_by_role("button", name="Entsperren").click()
        expect(page.locator(".stamp-date")).to_contain_text("Kursstand", timeout=30000)
        page.reload()
        expect(page.locator(".stamp-date")).to_contain_text("Kursstand", timeout=30000)

    # ------------------------------------------------- Potenzial und Signale (Auftrag vom 14.10.2026, 1.6)

    def test_start_shows_candidates_first_and_detail_explains_the_verdict(self) -> None:
        """Startseite: ganz oben „Kandidaten mit Potenzial“ (5 Zeilen, zwei Ampeln, Gründe); die Einzelansicht
        zeigt beide Urteile, Prognose, Signale mit Erklärung zum Antippen und die Reiter Analysten/Kennzahlen."""
        page = self.page()
        self.go(page, "/")
        section = page.locator("section.candidates")
        expect(section.get_by_role("heading", name="Kandidaten mit Potenzial")).to_be_visible()
        rows = section.locator("ol.sig-rows > li")
        expect(rows).to_have_count(5)
        expect(rows.first.locator(".light")).to_have_count(2)
        expect(rows.first.locator(".reasons li").first).to_be_visible()
        # Gesamtwertung (1.7): Zahl je Zeile, absteigend; Steig-Konstanz 30/60/90 Tage als Streifen
        expect(section.get_by_role("radio", name="Gesamt")).to_have_attribute("aria-checked", "true")
        expect(rows.first.locator(".total strong")).to_have_text(re.compile(r"^\d+$"))
        totals = [int(t) for t in rows.locator(".total strong").all_inner_texts()]
        self.assertEqual(totals, sorted(totals, reverse=True), "nach Gesamtwertung sortiert")
        self.assertGreaterEqual(rows.first.locator(".kons .kons-cell").count(), 2)
        expect(rows.first.locator(".kons .kons-cell").first).to_contain_text(re.compile(r"30 T\s*▲\d+/\d+"))
        selection = page.locator("section", has=page.get_by_role("heading", name="Höchste Kursrendite – Auswahl", exact=True))
        self.assertLess(section.bounding_box()["y"], selection.bounding_box()["y"], "Kandidaten stehen über den Rendite-Ranglisten")
        section.get_by_role("button", name="Erklärung: Kandidaten mit Potenzial").click()
        expect(section.locator(".info-text")).to_contain_text("zwei Ampeln")
        section.get_by_role("radio", name="Kursziel").click()
        expect(rows.first.locator(".reasons li").first).to_contain_text("Kursziel")
        self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"), page.evaluate("window.innerWidth"))
        self.shot(page, "20_start_kandidaten")
        rows.first.locator("a.row-name").click()
        page.wait_for_url("**/#/aktie/**")
        expect(page.get_by_role("heading", name="Gesamtwertung")).to_be_visible()
        expect(page.locator(".tp-row")).to_have_count(4)
        expect(page.locator(".kons-table tbody tr").first).to_contain_text("30 Tage")
        expect(page.locator(".head-total")).to_contain_text("Gesamt")
        page.get_by_role("button", name="Erklärung: Steig-Konstanz (30/60/90 Tage)").click()
        expect(page.locator(".tp-row .info-text").first).to_contain_text("Handelstagen")
        expect(page.locator(".pc-pro .pc-title")).to_contain_text("Dafür spricht")
        expect(page.locator(".pc-con .pc-title")).to_contain_text("Dagegen spricht")
        expect(page.get_by_role("heading", name="Urteil der Signale")).to_be_visible()
        # Daytrader-Check (1.7.1): gebündelte Punkte mit Zeichen, Wert und Erklärung
        expect(page.get_by_role("heading", name="Daytrader-Check")).to_be_visible()
        checks = page.locator("ul.tchecks > li")
        self.assertGreaterEqual(checks.count(), 11)
        expect(page.locator(".trader-tally")).to_contain_text("bewertbaren Punkten sprechen dafür")
        checks.first.get_by_role("button").click()
        expect(checks.first.locator(".info-text")).to_contain_text("Umsatz")
        expect(page.locator(".verdict")).to_have_count(2)
        expect(page.locator(".head-lights")).to_contain_text("Kurzfristig")
        expect(page.locator(".head-lights")).to_contain_text("Langfristig")
        expect(page.get_by_role("heading", name="Prognose (12 Monate)")).to_be_visible()
        expect(page.locator("figure.forecast svg")).to_be_visible()
        items = page.locator(".signal-list li")
        self.assertGreaterEqual(items.count(), 10)
        items.first.get_by_role("button").click()
        expect(items.first.locator(".info-text")).to_contain_text("Umsatz")
        expect(page.get_by_role("heading", name="Kursverlauf")).to_be_visible()
        self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"), page.evaluate("window.innerWidth"))
        self.shot(page, "21_aktie_ueberblick")
        tabs = page.get_by_role("navigation", name="Bereiche der Einzelansicht")
        tabs.get_by_role("radio", name="Analysten").click()
        expect(page.get_by_role("heading", name="Was die Analysten denken")).to_be_visible()
        expect(page.locator(".analyst-text p").first).to_contain_text("Analysten")
        expect(page.get_by_role("heading", name="Kursziele nach Quelle")).to_be_visible()
        expect(page.get_by_role("heading", name="Stimmung der Community")).to_be_visible()
        self.shot(page, "22_aktie_analysten")
        tabs.get_by_role("radio", name="Kennzahlen").click()
        expect(page.locator(".fact-group").first).to_be_visible()
        tabs.get_by_role("radio", name="Rendite 1–90").click()
        expect(page.get_by_role("heading", name="Stammdaten und Herkunft")).to_be_visible()

    def test_potential_list_switches_lists_filters_and_stays_on_screen(self) -> None:
        page = self.page()
        self.go(page, "/potenzial")
        expect(page.locator("h2.view-title")).to_have_text("Kandidaten mit Potenzial")
        rows = page.locator("ol.sig-rows > li")
        expect(rows.first).to_be_visible()
        self.assertLessEqual(rows.count(), 25)
        page.get_by_role("radio", name="Langfristig").click()
        self.wait_until(page, "location.hash.includes('liste=lang')")
        page.get_by_role("button", name=re.compile("^Filter")).click()
        page.get_by_label("nur grün").check()
        self.wait_until(page, "location.hash.includes('gruen=1')")
        expect(page.get_by_role("button", name=re.compile(r"^Filter \(1 aktiv\)"))).to_be_visible()
        expect(rows.first).to_be_visible()
        long_lights = page.locator("ol.sig-rows > li .light", has_text="lang")
        for k in range(long_lights.count()):
            expect(long_lights.nth(k)).to_contain_text("grün")
        self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"), page.evaluate("window.innerWidth"))
        self.shot(page, "23_potenzial")
        # Bereich „Analyse“: Werkzeuge mit Erklärung
        page.get_by_role("navigation", name="Hauptnavigation").get_by_role("link", name="Analyse").click()
        expect(page.locator(".tool-list li")).to_have_count(5)

    def test_signals_load_on_the_encrypted_site(self) -> None:
        page = self.page(base=self.base_enc)
        self.go(page, "/", base=self.base_enc)
        page.locator("#passphrase").fill(PASSPHRASE)
        page.get_by_role("button", name="Entsperren").click()
        expect(page.locator("section.candidates ol.sig-rows > li")).to_have_count(5, timeout=30000)

    def test_key_can_be_entered_before_first_snapshot(self) -> None:
        """Vor dem ersten Datenstand lässt sich die Passphrase schon prüfen und speichern; erscheint
        der erste Stand, öffnet die App ihn ohne erneute Eingabe."""
        page = self.page(base=self.base_enc)
        status = json.loads((self.site_enc / "data" / "status.json").read_text(encoding="utf-8"))
        status["latest_snapshot_id"] = None
        page.route("**/data/status.json*", lambda route: route.fulfill(status=200, content_type="application/json", body=json.dumps(status)))
        page.route("**/data/snapshots/index.json*", lambda route: route.fulfill(status=200, content_type="application/json", body='{"schema": "tr-snapshot-index/1", "snapshots": []}'))
        self.go(page, "/", base=self.base_enc)
        expect(page.get_by_text("Noch kein Datenstand veröffentlicht")).to_be_visible()
        page.locator("#passphrase").fill("falsch")
        page.get_by_role("button", name="Prüfen und speichern").click()
        expect(page.get_by_text("Der Zugangsschlüssel passt nicht", exact=False)).to_be_visible(timeout=30000)
        page.locator("#passphrase").fill(PASSPHRASE)
        page.get_by_role("button", name="Prüfen und speichern").click()
        expect(page.get_by_text("Zugangsschlüssel gespeichert")).to_be_visible(timeout=30000)
        expect(page.get_by_text("Noch kein Datenstand veröffentlicht")).to_be_visible()
        self.assertEqual(page.locator("#passphrase").count(), 0)
        # Der erste Datenstand ist da: geöffnet ohne erneute Eingabe
        page.unroute("**/data/status.json*")
        page.unroute("**/data/snapshots/index.json*")
        page.reload()
        expect(page.locator(".stamp-date")).to_contain_text("Kursstand", timeout=30000)


if __name__ == "__main__":
    unittest.main()
