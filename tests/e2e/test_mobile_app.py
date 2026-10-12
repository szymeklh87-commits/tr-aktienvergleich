"""Browser-Ende-zu-Ende-Tests der gebauten App auf einem simulierten Galaxy-S25+-Viewport.

Simulation (Chromium, 384 × 832 CSS-Pixel, Pixelverhältnis 2,8125, Touch) – das ist ausdrücklich
KEIN Test auf einem echten Gerät. Daten: DEMO-Stand mit synthetischen Testaktien.

Voraussetzungen: ``app/dist`` (``npm run build``), Python-Paket ``playwright`` und Chromium.
Ohne diese Voraussetzungen werden die Tests übersprungen.

Optional: ``TR_E2E_SCREENSHOTS=<Ordner>`` speichert Bildschirmfotos für den Testbericht.
"""

from __future__ import annotations

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
    env = dict(os.environ, PYTHONPATH=str(REPO / "backend"), LOG_LEVEL="WARNING")
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

    # ------------------------------------------------------------- Tests

    def test_start_shows_stand_demo_and_ladder(self) -> None:
        page = self.page()
        self.go(page, "/")
        expect(page.locator(".stamp-date")).to_contain_text("Kursstand Montag, 12. Oktober 2026")
        expect(page.locator(".notice-demo")).to_contain_text("DEMO")
        expect(page.locator(".stand-chip")).to_contain_text("12.10.2026")
        expect(page.locator(".ladder-strip svg")).to_be_visible()
        self.shot(page, "01_start")
        box = page.locator(".ladder-strip .hit").bounding_box()
        page.mouse.click(box["x"] + box["width"] * 0.995, box["y"] + box["height"] / 2)
        page.wait_for_url("**/#/ranking?h=90&w=0&p=native&chart=1")
        expect(page.locator("ol.rows > li").first).to_be_visible()

    def test_return_ladder_has_exactly_90_rows(self) -> None:
        page = self.page()
        self.go(page, "/rendite")
        expect(page.locator("ol.rank-ladder > li")).to_have_count(90)
        expect(page.locator("ol.rank-ladder > li").first).to_contain_text("ZZ")
        self.shot(page, "02_hoechste_rendite")

    def test_ranking_window_weight_and_empty_reason(self) -> None:
        page = self.page()
        self.go(page, "/ranking?h=30&w=60&p=native")
        expect(page.locator("ol.rows > li")).to_have_count(10)
        self.shot(page, "03_ranking")
        page.get_by_role("button", name="7 T", exact=True).click()
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
        self.assertIn("Rang;Unternehmen;ISIN;Kursrendite %", content)
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
        self.go(page, "/rendite")
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
        self.go(page, "/haeufig")
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
        for route in ("/", "/ranking", "/raster", "/haeufig/" + "ZZ0000000412", "/aktie/ZZ0000000719?h=30"):
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
        for route in ("/", "/rendite", "/ranking", "/vergleich", "/aktien", "/haeufig", "/raster", "/aktie/ZZ0000000719?h=30", "/status", "/einstellungen"):
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
        page.get_by_role("button", name="30 T", exact=True).click()
        self.wait_until(page, "location.hash.includes('h=30')")
        expect(page.locator("figure.chart").first).not_to_have_attribute("aria-label", summary_7)
        summary_30 = page.locator("figure.chart").first.get_attribute("aria-label")
        count = lambda text: int(text.split(" echte Tageskurse")[0].split(" ")[-1])
        self.assertGreater(count(summary_30), count(summary_7))

    def test_T56_stale_heartbeat_is_shown_as_gap(self) -> None:
        page = self.page()
        status = json.loads((self.site / "data" / "status.json").read_text(encoding="utf-8"))
        status["last_successful_check_utc"] = "2026-09-01T04:05:00Z"
        page.route("**/data/status.json", lambda route: route.fulfill(status=200, content_type="application/json", body=json.dumps(status)))
        self.go(page, "/")
        expect(page.get_by_text("Keine aktuelle Prüfung")).to_be_visible()

    def test_T59_first_use_without_snapshot_shows_setup_state(self) -> None:
        page = self.page()
        status = json.loads((self.site / "data" / "status.json").read_text(encoding="utf-8"))
        status["latest_snapshot_id"] = None
        page.route("**/data/status.json", lambda route: route.fulfill(status=200, content_type="application/json", body=json.dumps(status)))
        page.route("**/data/snapshots/index.json", lambda route: route.fulfill(status=200, content_type="application/json", body='{"schema": "tr-snapshot-index/1", "snapshots": []}'))
        self.go(page, "/")
        expect(page.get_by_text("Noch kein Datenstand veröffentlicht")).to_be_visible()
        self.assertEqual(page.locator("ol.rows > li").count(), 0, "keine erfundenen Gewinner")

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
        for route in ("/ranking?h=30&w=60", "/rendite", "/haeufig", "/raster", "/aktien"):
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
        page.on("request", lambda r: snapshots.add(r.url.split("/data/snapshots/", 1)[1].split("/", 1)[0]) if "/data/snapshots/" in r.url and not r.url.endswith("index.json") else None)
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
        self.go(page, "/rendite")
        hrefs = page.locator("ol.rank-ladder > li .row-name").evaluate_all("(els) => els.map((a) => a.getAttribute('href'))")
        windows = {int(re.search(r"[?&]h=(\d+)", href).group(1)) for href in hrefs}
        self.assertEqual(windows, set(range(1, 91)), "jeder Zeitraum mit einem Tippen erreichbar")
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
        expect(page.locator("ol.rank-ladder > li")).to_have_count(90)
        nav.get_by_role("link", name="Häufig").click()
        expect(page.locator("ol.rows > li").first).to_be_visible()

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


if __name__ == "__main__":
    unittest.main()
