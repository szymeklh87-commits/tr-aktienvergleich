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

    def page(self, *, base: str | None = None, color_scheme: str = "light", viewport: dict | None = None, service_workers: str = "block", permissions: list[str] | None = None, expected_console: str | None = None):
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
        # expected_console: Meldungen des Browsers zu absichtlich fehlerhaften Antworten (Fehlerfall-Tests) – alles andere zählt
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" and not (expected_console and re.search(expected_console, m.text)) else None)
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

    @staticmethod
    def open_line(page, kind: str) -> None:
        """Ab 1.22 (F09 „Liste zuerst“): Über einer Hauptliste stehen die Regler unter „Einstellungen“ (``kind="settings"``)
        und die Hinweise in einer Zeile (``kind="notes"``) – beide aufklappbar. Öffnet die Zeile, falls sie zu ist."""
        toggle = page.locator(f".list-{kind} .disclosure-toggle").first
        if toggle.get_attribute("aria-expanded") != "true":
            toggle.click()
        expect(toggle).to_have_attribute("aria-expanded", "true")

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
        self.shot(page, "01_start")
        # ab 1.15 unter „Mehr auf einen Blick“ (Startseite übersichtlicher)
        expect(page.locator(".ladder-strip")).to_have_count(0)
        page.get_by_role("button", name=re.compile("^Mehr auf einen Blick")).click()
        expect(page.locator(".ladder-strip svg")).to_be_visible()
        page.locator(".ladder-strip").scroll_into_view_if_needed()
        box = page.locator(".ladder-strip .hit").bounding_box()
        page.mouse.click(box["x"] + box["width"] * 0.995, box["y"] + box["height"] / 2)
        page.wait_for_url("**/#/ranking?h=90&w=0&p=native&chart=1")
        expect(page.locator("ol.rows > li").first).to_be_visible()

    def test_return_rankings_winner_top10_and_full_list(self) -> None:
        """Erweiterung 1.1: Sieger je Zeitraum (1–7 Tage) → Top 10 → vollständige Rangliste. Ab 1.23 nur noch die Liste mit
        Mindestumsatz (Auftrag 16:50–16:52): Überschrift „Höchste Kursrendite“, dezente Zeile zum Mindestumsatz, keine A/B-Auswahl."""
        page = self.page()
        self.go(page, "/rendite?z=1-7")
        blocks = page.locator("ol.window-list > li")
        expect(blocks).to_have_count(7)
        expect(page.get_by_role("heading", name="Höchste Kursrendite", exact=True)).to_be_visible()
        expect(page.locator(".min-turnover").first).to_have_text("Mindestumsatz: 10 Mio. USD pro Handelstag (Durchschnitt)")
        for label in ("Punkt A", "Punkt B", "A: alle", "B: Umsatz", "A und B"):
            expect(page.get_by_text(label, exact=False)).to_have_count(0)
        expect(page.get_by_role("radio", name=re.compile(r"^(A|B)( |:|$)"))).to_have_count(0)
        expect(blocks.first).to_contain_text("ZZ")
        self.open_line(page, "notes")
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
        # Standard: alle 90 Zeiträume, je Zeitraum der Sieger der Liste mit Mindestumsatz
        self.go(page, "/rendite")
        rows = page.locator("ol.window-list > li")
        expect(rows).to_have_count(90)
        expect(page.locator("ol.pair-list")).to_have_count(0)
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
        expect(page.locator("#rw-60 .jump-note")).to_have_text("gewählt")
        expect(page.locator("ol.window-list .jump-note")).to_have_count(1)
        expect(page.locator("#rw-60")).to_have_attribute("aria-current", "true")
        self.shot(page, "02e_sprung_gewaehlt")
        rows.nth(59).get_by_role("button", name=re.compile("Top 10 anzeigen")).click()
        expect(rows.nth(59).locator(".top-ten ol.rows > li")).to_have_count(10)

    def test_only_stocks_with_minimum_turnover_in_return_rankings(self) -> None:
        """Ab 1.23 (Auftrag 16:50, dauerhaft): Sieger je Zeitraum = Platz 1 der Liste mit Mindestumsatz (``winners_l`` des
        Servers, Plätze ohne die übrigen Aktien gezählt); auch alte Links mit f=alle führen dorthin; keine „Kaum Umsatz“-Aktien."""
        ov = self.snap("overview.bin")
        isins = self.snap("instruments.bin")["isin"]
        liquid = self.snap("instruments.bin")["turnover"]["liquid"]
        expected = [isins[row["entries"][0]["idx"]] if row["entries"] else None for row in ov["winners_l"]]
        everyone = [isins[row["entries"][0]["idx"]] if row["entries"] else None for row in ov["winners"]]
        self.assertNotEqual(expected, everyone, "Testdaten: der Mindestumsatz ändert mindestens einen Sieger")
        page = self.page()
        for route in ("/rendite?f=alle&z=alle", "/rendite?z=alle"):
            self.go(page, route)
            expect(page.locator("ol.window-list > li")).to_have_count(90)
            expect(page.get_by_role("radio", name=re.compile("Umsatz|alle Aktien", re.I))).to_have_count(0)
            shown = [r.locator(".stock-row .isin-code").first.inner_text() if r.locator(".stock-row .isin-code").count() else None
                     for r in page.locator("ol.window-list > li").all()]
            self.assertEqual(shown, expected, route)
        self.assertTrue(all(liquid[isins.index(i)] for i in expected if i), "nur Aktien mit nachgewiesenem Mindestumsatz")
        expect(page.locator("ol.window-list .badge-warn", has_text="Kaum Umsatz")).to_have_count(0)
        for text in page.locator("ol.window-list > li .turnover-line").all_inner_texts()[:20]:
            self.assertIn("Mio.", text)
        self.open_line(page, "notes")
        expect(page.get_by_text("Ø Umsatz bestimmt")).to_be_visible()
        self.shot(page, "02c_mindestumsatz")

    def test_noise_toggle_hides_low_turnover_and_jumps_and_keeps_ranks(self) -> None:
        """Ab 1.14 „Auffällige ausblenden“: ein gespeicherter Schalter für alle Ranglisten; Spitzenreiter wie
        ``winners_l_klar`` des Servers (ab 1.23 nur Aktien mit Mindestumsatz), Plätze wie in der vollständigen Rangliste,
        abschaltbar unter Einstellungen."""
        ov = self.snap("overview.bin")
        isins = self.snap("instruments.bin")["isin"]
        row = next(r for r in ov["winners_l_klar"] if r["rank"] and r["rank"] > 1)
        h = row["h"]
        full = self.snap(f"windows/{h}.full.bin")
        page = self.page()
        self.go(page, f"/ranking?h={h}&w=0&p=native")
        rows = page.locator("ol.rows > li")
        expect(rows.first.locator(".isin-code")).to_have_text(isins[full["orders"]["v0l"][0]])
        expect(rows.first.locator(".row-rank")).to_contain_text("1")
        flagged = page.locator("ol.rows .badge-warn", has_text=re.compile("Kaum Umsatz|Einzelsprung"))
        self.assertGreater(flagged.count(), 0, "Auffällige sind gekennzeichnet")
        self.open_line(page, "settings")
        toggle = page.get_by_role("checkbox", name=re.compile("Auffällige ausblenden"))
        expect(toggle).not_to_be_checked()
        toggle.check()
        expect(rows.first.locator(".isin-code")).to_have_text(isins[row["entries"][0]["idx"]])
        expect(rows.first.locator(".row-rank")).to_contain_text(str(row["rank"]))
        expect(page.locator("ol.rows .badge-warn", has_text=re.compile("Kaum Umsatz|Einzelsprung"))).to_have_count(0)
        expect(page.get_by_text("Ohne Auffällige: Plätze wie in der vollständigen Rangliste", exact=False)).to_be_visible()
        self.shot(page, "02d_ohne_auffaellige")
        # gespeichert: auch die Rendite-Ranglisten zeigen den Spitzenreiter ohne Auffällige mit seinem Platz
        self.go(page, f"/rendite/liste?h={h}")
        self.open_line(page, "settings")
        expect(page.get_by_role("checkbox", name=re.compile("Auffällige ausblenden"))).to_be_checked()
        first = page.locator("ol.rows > li").first
        expect(first.locator(".isin-code")).to_have_text(isins[row["entries"][0]["idx"]])
        expect(first.locator(".row-rank")).to_contain_text(str(row["rank"]))
        # unter Einstellungen wieder ausschalten
        self.go(page, "/einstellungen")
        page.get_by_role("checkbox", name=re.compile("Auffällige ausblenden")).uncheck()
        self.go(page, f"/ranking?h={h}&w=0&p=native")
        expect(page.locator("ol.rows > li").first.locator(".isin-code")).to_have_text(isins[full["orders"]["v0l"][0]])

    def test_detail_shows_turnover_and_return_rank_with_minimum_turnover(self) -> None:
        page = self.page()
        self.go(page, "/rendite")
        page.locator("ol.window-list > li").first.locator(".stock-row .row-name").first.click()
        page.wait_for_url("**/#/aktie/**")
        expect(page.get_by_text("Ø Tagesumsatz", exact=True)).to_be_visible()
        expect(page.locator(".kv-row", has_text="Höchste Kursrendite").first).to_contain_text("Platz 1 von")
        expect(page.locator(".kv-row", has_text="Mindestumsatz").first).to_contain_text("mindestens 10 Mio. USD")
        expect(page.locator(".kv-row", has_text="Ø Umsatz ≥")).to_have_count(0)

    def test_frequency_counts_only_stocks_with_minimum_turnover(self) -> None:
        page = self.page()
        self.go(page, "/haeufig/erweitert")
        expect(page.locator(".universe-note")).to_contain_text("Ø Tagesumsatz ab 10 Mio. USD")
        self.go(page, "/haeufig/erweitert?tab=rendite")
        expect(page.locator(".universe-note")).to_contain_text("Ø Tagesumsatz ab 10 Mio. USD")
        expect(page.get_by_role("radio", name=re.compile("Ø Umsatz ≥ 10|Alle Aktien"))).to_have_count(0)
        expect(page.locator("ol.rows > li").first).to_be_visible()

    def test_weekend_start_dates_in_return_rankings(self) -> None:
        """Kursstand Montag 12.10.: 1–3 Tage beginnen am Freitag 09.10., 4 Tage am Donnerstag 08.10. Ab tr-methode-1.9.0 zählt
        eine Aktie ohne Kurs am Stichtag mit ihrem letzten Schlusskurs; ihre Zeiträume enden dort und beginnen h Tage davor.
        Ab 1.23 nur die Liste mit Mindestumsatz – Sieger je Zeitraum und vollständige Liste."""
        ov = self.snap("overview.bin")
        cutoff = self.snap("manifest.bin")["cutoff_day"]
        inst = self.snap("instruments.bin")
        expected_start = {1: "09.10.2026", 2: "09.10.2026", 3: "09.10.2026", 4: "08.10.2026", 5: "07.10.2026"}
        page = self.page()
        self.go(page, "/rendite?z=1-7")
        blocks = page.locator("ol.window-list > li")
        expect(blocks).to_have_count(7)
        for k in range(5):
            winner = ov["winners_l"][k]["entries"][0]
            path = blocks.nth(k).locator(".price-path").first
            if winner["end"] == cutoff:
                expect(path).to_contain_text(expected_start[k + 1] + ":")
                expect(path).to_contain_text("→ 12.10.2026")
            else:
                expect(path).to_contain_text(f"{self.day(winner['start'])}: ")
                expect(path).to_contain_text(f"→ {self.day(winner['end'])}")
        # eigener Stichtag (letzter Schlusskurs vor dem 12.10.) in der vollständigen Liste mit Mindestumsatz
        own = [i for i, d in enumerate(inst["last_close_day"]) if d is not None and d < cutoff and inst["level_status"][i] == 0 and inst["turnover"]["liquid"][i]]
        self.assertTrue(own, "DEMO: mindestens eine Aktie mit Mindestumsatz und letztem Schlusskurs vor dem Stichtag")
        idx = own[0]
        seen = 0
        for h in range(1, 8):
            win = self.snap(f"windows/{h}.full.bin")
            order = win["orders"]["v0l"]
            if idx not in order or order.index(idx) >= 50:
                continue
            pos = win["m"]["idx"].index(idx)
            self.go(page, f"/rendite/liste?h={h}")
            row = page.locator("ol.rows > li", has_text=inst["isin"][idx]).first
            path = row.locator(".price-path").first
            expect(path).to_contain_text(f"{self.day(win['m']['start'][pos])}: ")
            expect(path).to_contain_text(f"→ {self.day(inst['last_close_day'][idx])}")
            expect(row.locator(".row-close").first).to_contain_text(self.day(inst["last_close_day"][idx])[:6])
            seen += 1
            break
        self.assertEqual(seen, 1, "Aktie mit eigenem Stichtag auf der ersten Seite einer Liste 1–7 Tage")

    def test_second_venue_deviation_in_lists_detail_and_status(self) -> None:
        """Erweiterung 1.2: auffällige Kursabweichung zwischen Börsenplätzen wird gekennzeichnet – ab 1.23 in der Liste mit
        Mindestumsatz und zusätzlich „Ungeprüft – Kurs nicht bestätigt“."""
        isins = self.snap("instruments.bin")["isin"]
        hit = None
        for h in range(8, 31):
            win = self.snap(f"windows/{h}.full.bin")
            xv = win.get("xv") or {}
            deviating = {i for i, st in zip(xv.get("idx", []), xv.get("status", [])) if st == "abweichung"}
            for place, idx in enumerate(win["orders"]["v0l"][:10]):
                if idx in deviating:
                    hit = (h, place, idx)
                    break
            if hit:
                break
        self.assertIsNotNone(hit, "DEMO: eine Aktie mit Börsenplatz-Abweichung unter den ersten zehn der Liste mit Mindestumsatz")
        h, place, idx = hit
        page = self.page()
        self.go(page, "/rendite?z=8-30")
        blocks = page.locator("ol.window-list > li")
        expect(blocks).to_have_count(23)
        block = page.locator(f"#rw-{h}")
        block.get_by_role("button", name=re.compile("Top 10 anzeigen")).click()
        rows = block.locator(".top-ten ol.rows > li")
        expect(rows).to_have_count(10)
        flagged = rows.nth(place)
        expect(flagged).to_contain_text(isins[idx])
        expect(flagged.locator(".badge-warn", has_text="Ungeprüft – Börsenplatz-Abweichung").first).to_be_visible()
        expect(flagged.locator(".venue-line").first).to_contain_text("auffällige Abweichung")
        others = [k for k in range(10) if k != place]
        expect(rows.nth(others[0]).locator(".venue-line")).to_contain_text(re.compile("unauffällig|nicht geprüft"))
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
        self.open_line(page, "settings")
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

    def test_offline_restart_after_a_single_first_visit(self) -> None:
        """Wie auf dem Handy beim ersten Mal (ab 1.18.1): Website einmal öffnen, entsperren und benutzen – ohne Neuladen;
        seit 1.15 übernimmt der Service Worker die Seite beim ersten Besuch, ohne neu zu laden – und danach ohne Netz neu
        öffnen. Erwartet: der zuletzt geladene Stand ohne erneute Passphrase, mit Hinweis „Offline – gespeicherter Stand“,
        Kandidaten und Rangliste. Bis 1.18.0 lagen die vor der Übernahme geladenen Dateien (Status, Index,
        Schlüsselparameter, Kerndateien) nicht im Speicher des Service Workers, und Signale speicherte er gar nicht – die App
        meldete „Keine Internetverbindung“ (gefunden am 24.10.2026 im Android-Emulator mit echten Daten). Eigener Server
        (eigener Ursprung = erster Besuch), der danach wirklich abgeschaltet wird: ohne Netz und ohne Server."""
        server, base = _serve(self.site_enc)
        try:
            page = self.page(base=base, service_workers="allow")
            page.goto(f"{base}#/")
            page.locator("#passphrase").fill(PASSPHRASE)
            page.get_by_role("button", name="Entsperren").click()
            expect(page.locator(".stamp-date")).to_contain_text("Kursstand", timeout=30000)
            expect(page.locator("section.candidates ol.sig-rows > li")).to_have_count(3, timeout=30000)
            self.wait_until(page, "!!navigator.serviceWorker.controller")
            self.assertEqual(page.evaluate("performance.getEntriesByType('navigation').length"), 1, "kein Neuladen")
            page.evaluate("location.hash = '/ranking?h=30&w=60'")
            expect(page.locator("ol.rows > li")).to_have_count(10)
            page.wait_for_timeout(1500)  # Service Worker speichert im Hintergrund
            context = page.context
            page.close()
        finally:
            server.shutdown()
            server.server_close()
        context.set_offline(True)
        again = context.new_page()
        again.set_default_timeout(15000)
        problems: list[str] = []
        again.on("pageerror", lambda e: problems.append(str(e)))
        again.goto(f"{base}#/")
        expect(again.get_by_text("Offline – gespeicherter Stand")).to_be_visible(timeout=30000)
        expect(again.locator(".stamp-date")).to_contain_text("Kursstand")
        expect(again.get_by_text("Keine Internetverbindung")).to_have_count(0)
        self.assertEqual(again.locator("#passphrase").count(), 0, "fragt ohne Netz erneut nach der Passphrase")
        expect(again.locator("section.candidates ol.sig-rows > li")).to_have_count(3)
        again.evaluate("location.hash = '/ranking?h=30&w=60'")
        expect(again.locator("ol.rows > li")).to_have_count(10)
        # Nicht gespeicherte Datei: ehrlicher Offline-Hinweis, keine HTML-Seite statt Daten (bis 1.18.0 bei Signal-Dateien)
        isin = self.snap("instruments.bin")["isin"][-1]
        again.evaluate(f"location.hash = '/aktie/{isin}?h=30'")
        expect(again.locator("main")).not_to_contain_text("konnten nicht gelesen werden")
        self.assertEqual(problems, [])
        context.set_offline(False)

    # ------------------------------------------------------- Gesamtauftrag: Autopilot – Spielgeld

    def test_pilot_area_shows_play_money_robo_with_explanations(self) -> None:
        """Bereich „Pilot“ über die Leiste: Spielgeld-Kennzeichnung, Pilotdepot mit Vergleich, Strategien, Depot mit Positionen,
        Journal mit Begründung, Regeln als deutscher Text – Werte aus dem verschlüsselten Stand des DEMO-Laufs, kein Orderknopf."""
        from traktien.util import crypto

        status = json.loads((self.site / "data" / "status.json").read_text(encoding="utf-8"))
        sid = status["spielgeld"]["id"]
        stand = json.loads(crypto.unpack((self.site / "data" / "pilot" / sid / "pilot.bin").read_bytes(), None, f"pilot/{sid}/pilot.bin"))
        pilot = next(d for d in stand["depots"] if d["art"] == "pilot" and not d["historisch"])
        page = self.page()
        self.go(page, "/")
        page.get_by_role("navigation", name="Hauptnavigation").get_by_role("link", name="Pilot").click()
        expect(page.locator("main")).to_contain_text("keine echten Orders")
        expect(page.locator(".pilot-card-name").first).to_have_text(pilot["name"])
        expect(page.locator("main")).to_contain_text("Abstand zum Welt-ETF")
        expect(page.locator("table.pilot-table tbody tr")).not_to_have_count(0)
        self.shot(page, "pilot-uebersicht")
        # keine Schaltfläche, die eine Order auslöst – die App zeigt nur an
        self.assertEqual(page.locator("main button", has_text=re.compile("Kaufen|Verkaufen|Order senden")).count(), 0)
        page.locator(".pilot-card-name").first.click()
        expect(page.get_by_role("radio", name=re.compile("Positionen"))).to_be_visible()
        page.get_by_role("radio", name="Journal").click()
        expect(page.locator(".pilot-entry").first).to_be_visible()
        page.get_by_role("radio", name="Regeln").click()
        expect(page.locator("main")).to_contain_text("Robo-Kern")
        expect(page.locator("main")).to_contain_text("Stop")
        self.shot(page, "pilot-regeln")
        self.go(page, "/pilot/regeln")
        expect(page.locator(".pilot-rule")).not_to_have_count(0)
        page.locator(".pilot-rule a").first.click()
        expect(page.locator("main")).to_contain_text("Kandidaten")
        expect(page.locator("main")).not_to_contain_text("undefined")
        self.assertEqual(page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth"), 0, "keine waagerechte Scrollleiste")

    def test_pattern_areas_under_potential(self) -> None:
        """Musterbereiche unter „Potenzial“ (Abschnitt 26): Unterreiter, Top-Liste mit Zustand, Moduswechsel, nicht prüfbare Aktien mit
        Grund, Nachrechnung, „Als Robo-Regel verwenden“ führt zu einer gültigen Regel im Baukasten."""
        page = self.page()
        self.go(page, "/potenzial")
        page.get_by_role("link", name="Muster und Volumen").click()
        main = page.locator("main")
        expect(main.get_by_role("heading", name="Muster und Volumen")).to_be_visible()
        expect(main).to_contain_text("keine Intraday-Beobachtung")
        rows = page.locator("ol.rows > li")
        expect(rows.first).to_be_visible()
        expect(rows.first).to_contain_text("Muster-Score")
        self.assertEqual(page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth"), 0, "keine waagerechte Scrollleiste")
        page.get_by_role("radio", name=re.compile("Seitwärtsbasis")).click()
        expect(rows.first).to_be_visible()
        page.get_by_role("button", name=re.compile("Nicht prüfbar")).click()
        page.get_by_role("button", name="Nachrechnung früherer Signale").click()
        expect(main).to_contain_text("Keine Gewinnwahrscheinlichkeit")
        page.get_by_role("radio", name=re.compile("Volumensprung")).click()
        expect(main).to_contain_text("5-/15-Minuten-Volumen: nicht prüfbar")
        page.get_by_role("radio", name=re.compile("Vor-Ausbruch")).click()
        page.get_by_role("link", name="Als Robo-Regel verwenden").click()
        editor = page.locator(".pilot-editor")
        expect(editor.get_by_label("Name der Regel")).to_have_value("Muster A: Vor-Ausbruch (kandidat, vorlaeufig, bestaetigt)")
        expect(editor.locator(".notice", has_text="Regel vollständig")).to_be_visible()
        self.assertNotIn("undefined", main.inner_text())

    def test_no_trade_republic_branding_and_no_promises(self) -> None:
        """Abschnitt 0 / Z07: kein Auftritt als Produkt von Trade Republic, keine Versprechen – Hilfe und Pilot sagen es ausdrücklich."""
        page = self.page()
        self.go(page, "/hilfe")
        main = page.locator("main")
        expect(main).to_contain_text("kein Produkt von Trade Republic")
        expect(main).to_contain_text("keine echten Orders")
        expect(main).to_contain_text("keine Kaufempfehlung")
        self.go(page, "/pilot")
        expect(page.locator("main")).to_contain_text("keine echten Orders, keine Anlageberatung")
        for route in ("/", "/hilfe", "/pilot"):
            self.go(page, route)
            self.assertNotIn("Trade Republic", page.title(), route)
            text = page.locator("main").inner_text()
            self.assertIsNone(re.search(r"garantiert|sicherer Gewinn|risikolos", text, re.IGNORECASE), f"Versprechen auf {route}")

    def test_touch_targets_are_at_least_44px(self) -> None:
        page = self.page()
        selectors = ".btn, .icon-btn, .chip, .segmented button, .bottomnav a, .fcell, .legend-btn, .stand-chip, .disclosure-toggle, .isin-copy, .watch-btn"
        for route in ("/", "/ranking", "/raster", "/haeufig/" + "ZZ0000000412", "/aktie/ZZ0000000719?h=30", "/bericht?m=ZZ0000000719", "/depots", "/pilot"):
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
        for route in ("/", "/rendite", "/bericht?m=ZZ0000000719", "/depots", "/depots?bearbeiten=neu", "/ranking", "/vergleich", "/aktien", "/haeufig", "/raster", "/aktie/ZZ0000000719?h=30", "/status", "/einstellungen"):
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
        # Ab 1.16: verständlicher Satz mit nächstem Schritt (vorher „hat sich seit vor … Tagen nicht … gemeldet“)
        stale = page.locator(".notice", has_text="Keine aktuelle Prüfung")
        expect(stale).to_contain_text(re.compile(r"zuletzt vor \d+ Tagen erfolgreich gemeldet"))
        expect(stale).to_contain_text("Jetzt aktualisieren")
        expect(stale).not_to_contain_text("seit vor")

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
        expect(page.locator(".update-view").get_by_role("link", name="Jetzt aktualisieren", exact=True)).to_be_visible()
        expect(page.locator(".kv-row", has_text="Kursstand in der App")).to_contain_text("noch kein Datenstand")

    def test_update_on_demand_starts_on_github_and_reports_result(self) -> None:
        """Jederzeit aktualisieren: Start auf GitHub (kein Schlüssel in der App), Warten, Ergebnis melden."""
        page = self.page()
        page.context.route("https://github.com/**", lambda route: route.fulfill(status=200, content_type="text/html", body="<!doctype html><title>GitHub</title>"))
        status = json.loads((self.site / "data" / "status.json").read_text(encoding="utf-8"))
        self.assertEqual(status["aktualisieren"]["starten_url"], "https://github.com/beispiel/tr-aktienvergleich/actions/workflows/taeglich.yml")
        self.assertEqual(status["naechster_kursstand"]["datum"], "2026-10-13")
        self.go(page, "/")
        expect(page.locator(".stamp").get_by_role("link", name="Kurse jetzt aktualisieren")).to_have_attribute("href", "#/aktualisieren")
        page.get_by_role("button", name="Weitere Ansichten").click()
        # ab 1.15: Menü in zwei Gruppen (Ansichten, App), ohne die Einträge, die unten in der Leiste stehen
        sheet = page.get_by_role("dialog", name="Weitere Ansichten")
        expect(sheet.locator("ul.sheet-list")).to_have_count(2)
        expect(sheet.get_by_role("link")).to_have_count(11)  # ab 1.16 mit „Hilfe und Begriffe“, ab 1.20.0 mit „Kursabgleich mit den Börsen“
        expect(sheet.get_by_role("link", name="Hilfe und Begriffe")).to_have_count(1)
        expect(sheet.get_by_role("link", name="Kursabgleich mit den Börsen")).to_have_count(1)
        expect(sheet.get_by_role("link", name="Kandidaten mit Potenzial")).to_have_count(0)
        page.get_by_role("link", name="Jetzt aktualisieren", exact=True).click()
        self.wait_until(page, "location.hash === '#/aktualisieren'")
        expect(page.get_by_role("heading", name="Lauf starten")).to_be_visible()
        expect(page.locator(".kv-row", has_text="Kursstand in der App")).to_contain_text("12.10.2026")
        expect(page.locator(".kv-row", has_text="Nächste neue Schlusskurse")).to_contain_text("Dienstag, 13. Oktober 2026")
        start = page.locator(".update-view").get_by_role("link", name="Jetzt aktualisieren", exact=True)
        expect(start).to_have_attribute("href", status["aktualisieren"]["starten_url"])
        expect(page.locator(".steps")).to_contain_text("„Alles aktualisieren“ ist voreingestellt")
        expect(page.locator(".update-list")).to_contain_text("Musterdepots")
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
        """Matrix (ab 1.23 nur Aktien mit Mindestumsatz, ohne A/B-Auswahl): Reiter, feste Zeitraumspalte, Markierung aller
        Vorkommen, Rangliste, Liste, Häufigkeit."""
        page = self.page()
        self.go(page, "/")
        page.get_by_role("navigation", name="Hauptnavigation").get_by_role("link", name="Analyse").click()
        self.wait_until(page, "location.hash === '#/analyse'")
        expect(page.locator(".tool-list a", has_text="A/B")).to_have_count(0)
        page.locator(".tool-list a", has_text="Matrix").first.click()
        self.wait_until(page, "location.hash === '#/matrix'")
        table = page.locator("table.gmatrix")
        expect(table.locator("tbody tr")).to_have_count(90)
        expect(table.locator("thead th")).to_have_count(12)  # Tage + elf Gewichtungen
        expect(page.get_by_text("Ranglisten berechnet", exact=False)).to_be_visible()
        expect(table.locator("td.gcell.is-empty").first).to_contain_text("weniger als 15 Tageskurse")
        # Gleiches Kursfenster laut Server (same_set): Montag 1–3 Tage – ab tr-methode-1.9.0 nur, wenn keine Aktie mit
        # eigenem Stichtag (DEMO: Tokio mit Feiertag) andere Starttage hat; die Matrix zeigt genau die Serverangabe
        same = self.snap("overview.bin")["same_set"]
        identical = any(same["v0l"][k] != k + 1 for k in range(90)) or any(same["ul"][k] != k + 1 for k in range(90))
        if identical:
            expect(table.locator(".same-mark").first).to_be_visible()
        else:
            expect(table.locator(".same-mark")).to_have_count(0)
        # feste Zeitraumspalte: nach seitlichem Wischen bleibt sie an derselben Stelle
        wrap = page.locator(".gmatrix-wrap")
        day_cell = table.locator("tbody th.gday").first
        before = day_cell.bounding_box()["x"]
        wrap.evaluate("el => el.scrollBy({ left: 600 })")
        page.wait_for_timeout(100)
        self.assertAlmostEqual(day_cell.bounding_box()["x"], before, delta=1)
        self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"), page.evaluate("document.documentElement.clientWidth"), "nur die Matrix verschiebt sich")
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
        # keine Gruppenwahl mehr; die Rangliste dazu enthält nur Aktien mit Mindestumsatz
        expect(page.get_by_role("radio", name=re.compile(r"Ø Umsatz ≥|^(A|B)[ :·]"))).to_have_count(0)
        expect(page.locator(".matrix-selection")).not_to_contain_text("Gruppe")
        page.locator(".matrix-selection").get_by_role("link", name="Rangliste", exact=False).click()
        self.wait_until(page, "location.hash.startsWith('#/ranking')")
        self.open_line(page, "notes")
        expect(page.get_by_text("Nur Aktien mit Ø Tagesumsatz ab 10 Mio. USD", exact=False).first).to_be_visible()
        expect(page.locator("ol.rows > li").first).to_contain_text(isin)
        page.go_back()
        self.wait_until(page, "location.hash.startsWith('#/matrix')")
        # Kompakte Liste: 90 Zeilen, Standard nur Rendite
        page.get_by_role("radio", name="Liste").click()
        expect(page.locator(".glist-row")).to_have_count(90)
        expect(page.get_by_role("heading", name="Spitzenreiter je Zeitraum, Nur Kursrendite", exact=False)).to_be_visible()
        # Häufigkeit: Platz 1 zuerst, nur Aktien mit Mindestumsatz, identische Kursfenster einmal
        page.get_by_role("radio", name="Häufigkeit").click()
        expect(page.get_by_role("heading", name="Häufigkeitsranking")).to_be_visible()
        expect(page.locator(".scope-note")).to_contain_text("Aktien mit Ø Tagesumsatz ab 10 Mio. USD")
        expect(page.locator(".scope-note")).not_to_contain_text("Gruppe")
        rows = page.locator("table.gfreq tbody tr")
        expect(rows.first).to_be_visible()
        n1 = [int(t) for t in rows.locator("td:nth-child(3) .gnum").all_inner_texts()]
        self.assertEqual(n1, sorted(n1, reverse=True), "sortiert nach Platz-1-Vorkommen")
        expect(page.get_by_role("radio", name="A und B")).to_have_count(0)
        before_once = page.locator("table.gfreq tbody tr").first.locator("td").nth(2).inner_text()
        page.get_by_label("Identische Kursfenster nur einmal zählen").check()
        self.wait_until(page, "location.hash.includes('einmal=1')")
        expect(page.get_by_text("Top-10-Fundstellen zusammengefasst", exact=False)).to_be_visible()
        after_once = page.locator("table.gfreq tbody tr").first.locator("td").nth(2).inner_text()
        # Ab tr-methode-1.9.0 sind Kursfenster nur gleich, wenn sie es für jede Aktie sind – auch für Aktien mit letztem
        # Schlusskurs (DEMO: Tokio mit Feiertag am Stichtag); dann gibt es nichts zusammenzufassen
        same = self.snap("overview.bin")["same_set"]
        if any(same[key][k] != k + 1 for key in ("v0l", "ul") for k in range(90)):
            self.assertNotEqual(before_once, after_once, "gleiche Kursfenster werden zusammengefasst")
        else:
            self.assertEqual(before_once, after_once, "ohne gleiche Kursfenster ändert sich nichts")
        self.shot(page, "22_matrix_haeufigkeit")

    def test_rotation_rule_today_backtest_variants_and_own_amounts(self) -> None:
        """Umschichtungs-Regel: Start → Regel; Depot-Lineal, Bestand, Rückblick, Varianten, beschlossene Umschichtung, eigene Beträge."""
        page = self.page()
        self.go(page, "/")
        page.get_by_role("button", name=re.compile("^Mehr auf einen Blick")).click()
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
        self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"), page.evaluate("document.documentElement.clientWidth"), "keine Seitwärtsverschiebung")
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
        # ab 1.21: ohne abgerufenen aktuellen Kurs nennt die Ansicht den Schlusskurs ausdrücklich als „kein aktueller Kurs“
        expect(page.locator("#kurs-aktuell")).to_be_visible()
        expect(page.get_by_text("kein aktueller Kurs", exact=False).first).to_be_visible()
        expect(page.get_by_text("Kein ausführbarer Trade-Republic-Kurs", exact=False).first).to_be_visible()
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
        for route in ("/", "/rendite", "/ranking", "/vergleich", "/aktien", "/haeufig", "/raster", "/aktie/ZZ0000000719?h=30", "/watchlist", "/status", "/methodik", "/pilot", "/muster"):
            self.go(page, route)
            expect(page.locator(".stand-chip .badge-demo"), f"DEMO-Kennzeichen auf {route}").to_have_text("DEMO")
            # sichtbar im S25+-Format: die Kopfzeile sagt selbst „DEMO-Stand“ (das kleine Kennzeichen daneben ist dort ausgeblendet)
            expect(page.locator(".stand-chip .stand-date"), f"DEMO sichtbar in der Kopfzeile auf {route}").to_contain_text("DEMO-Stand")
            self.assertIn("DEMO", page.locator(".stand-chip").inner_text(), route)

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

    def test_T102_top10_by_numbers_on_start_and_recomputed_independently(self) -> None:
        """„Top nach Zahlen“ (ab 1.11; Wunsch vom 14.10.: „nach berechenbaren Fakten ausrechnen … emotionslos“): ab 1.21.0
        als Rückblick mit zehn Zeilen unter „Kaufsignal heute“ und den Kaufkandidaten (bis 1.20 die Top 3 ganz oben).
        Punkte unabhängig nachgerechnet – Top-10-Nennungen aus den Fensterköpfen
        (40/60, 50/50, 60/40 · 1–30 Tage · ab 1.23 nur Aktien mit Mindestumsatz), Steig-Konstanz, Kursziel, Volumen und Börsenwert aus dem
        Signal-Stand. Dazu die ganze Rangfolge, der Filter „Ohne Warnzeichen“ und „Deine Aktien“."""
        import math

        from traktien.util import crypto

        js_round = lambda x: math.floor(x + 0.5)  # Math.round der App
        tenths = lambda x: math.floor(x * 10 + 0.5)  # Teilpunkte in ganzen Zehnteln (ab 1.18, exakte Summe)
        isins = self.snap("instruments.bin")["isin"]
        n10: dict[int, int] = {}
        n1: dict[int, int] = {}
        valid = 0
        for h in range(1, 31):
            orders = self.snap(f"windows/{h}.bin")["orders"]
            for key in ("ul",):  # ab 1.23 nur die Ranglisten mit Mindestumsatz
                for w in ("40", "50", "60"):
                    order = (orders.get(key) or {}).get(w) or []
                    if not order:
                        continue
                    valid += 1
                    n1[order[0]] = n1.get(order[0], 0) + 1
                    for idx in order[:10]:
                        n10[idx] = n10.get(idx, 0) + 1
        status = json.loads((self.site / "data" / "status.json").read_text(encoding="utf-8"))
        sid = status["signale"]["id"]
        sig = json.loads(crypto.unpack((self.site / "data" / "signale" / sid / "signale.bin").read_bytes(), None, f"signale/{sid}/signale.bin"))
        self.assertIn("boersenwert_eur", sig, "Börsenwert in EUR im Signal-Stand (ab 1.11)")
        k_of = {isin: k for k, isin in enumerate(sig["isin"])}

        def expected(idx: int) -> tuple[int, float | None]:
            k = k_of.get(isins[idx])
            at = lambda column: None if k is None or column is None else column[k]
            konstanz = at(sig["gesamt_teile"]["konstanz"]) or 0
            kursziel = at(sig["gesamt_teile"]["kursziel"]) or 0
            rvol, r5 = at(sig["merkmale"].get("rvol")), at(sig["merkmale"].get("r5"))
            volume = 0.0 if rvol is None or r5 is None or r5 <= 0 else min(1.0, max(0.0, rvol - 1.0))
            cap = at(sig["boersenwert_eur"])
            penalty = 0 if cap is None else 20 if cap < 50e6 else 10 if cap < 300e6 else 0
            parts10 = tenths(40 * n10[idx] / valid) + tenths(25 * min(1, konstanz / 100)) + tenths(20 * min(1, kursziel / 100)) + tenths(15 * volume)
            return max(0, js_round((parts10 - 10 * penalty) / 10)), at(sig.get("gesamt"))

        scored = {idx: expected(idx) for idx in n10}
        everyone = sorted(scored, key=lambda i: (-scored[i][0], -n10[i], -n1.get(i, 0), -(scored[i][1] if scored[i][1] is not None else -1), isins[i]))
        # Ab 1.14 Plätze nur für handelbare Aktien; ab 1.23 zählen ohnehin nur Ranglisten mit Mindestumsatz (10 Mio. USD)
        liquid = self.snap("instruments.bin")["turnover"]["liquid"]
        order = [i for i in everyone if liquid[i]]
        self.assertGreaterEqual(len(order), 3, "DEMO hat genug handelbare Aktien")
        self.assertEqual(order, everyone, "nur Aktien mit Mindestumsatz genannt")

        page = self.page()
        self.go(page, "/")
        # ab 1.21.0 steht „Kaufsignal heute“ ganz oben (beim ersten Start davor nur die Kurzerklärung), die Top 10 nach
        # Zahlen folgen nach den Kaufkandidaten und dem Datenstand
        expect(page.locator(".view > :not(.intro-card)").first).to_have_class(re.compile(r"\bsignal-hero\b"))
        top = page.locator("section.top-zahlen")
        self.assertLess(page.locator("section.buy-list").bounding_box()["y"], top.bounding_box()["y"], "Kaufkandidaten vor dem Rückblick")
        expect(top.locator("h2")).to_contain_text("Rückblick: Top 10 nach Zahlen")
        expect(top).to_contain_text("kein Kaufsignal")
        rows = top.locator("ol.top-rows > li")
        shown = min(10, len(order))
        expect(rows).to_have_count(shown)
        for k in range(shown):
            text = rows.nth(k).inner_text()
            self.assertEqual(re.search(r"ZZ\d{10}", text).group(0), isins[order[k]], f"Platz {k + 1}")
            expect(rows.nth(k).locator(".top-points")).to_have_text(str(scored[order[k]][0]))
            expect(rows.nth(k).locator(".top-why")).to_contain_text(f"in {n10[order[k]]} von {valid} Standard-Ranglisten unter den ersten 10")
        self.assertEqual(top.locator(".tparts").count(), 0, "auf der Startseite die Kurzform – die Teile stehen unter „Alle Plätze und Regel“")
        # Ganze Rangfolge: alle Aktien mit Top-10-Nennung, gleiche Reihenfolge
        page.get_by_role("link", name="Alle Plätze und Regel").click()
        self.wait_until(page, "location.hash.startsWith('#/top')")
        all_rows = page.locator("ol.top-rows > li")
        expect(all_rows.first).to_be_visible()
        self.assertEqual(re.search(r"ZZ\d{10}", all_rows.nth(1).inner_text()).group(0), isins[order[1]])
        # die vier Teile der Punkte kommen mit dem nachgeladenen Signal-Stand – darauf warten (in GitHub Actions langsamer)
        expect(all_rows.first.locator(".tpart").nth(3)).to_be_attached()
        self.open_line(page, "notes")
        expect(page.locator(".view").get_by_text(f"{len(order)} Aktien mit Ø Tagesumsatz ab 10 Mio. USD", exact=False).first).to_be_visible()
        # ab 1.23 keine Auswahl „Auch wenig gehandelte“ mehr – Aktien unter dem Mindestumsatz erscheinen nicht
        expect(page.get_by_role("checkbox", name=re.compile("Auch wenig gehandelte Aktien zeigen"))).to_have_count(0)
        expect(page.locator("ol.top-rows > li.top-row-none")).to_have_count(0)
        # Merken auf Platz 2 → erscheint unter „Deine Aktien“ mit Platz 2 (ab 1.13 auch hier mit „… liegt vorne“)
        all_rows.nth(1).locator(".watch-btn").click()
        expect(page.locator(".top-own")).to_contain_text("Platz 2 · 1 Aktie liegt vorne")
        self.assertGreaterEqual(page.locator(".top-own .tparts").count(), 1, "mit Teilen wie die Rangfolge")
        # Filter „Ohne Warnzeichen“: keine Zeile mit Warnzeichen
        page.get_by_role("radio", name="Ohne Warnzeichen").click()
        self.wait_until(page, "/[?&]ohne=1(&|$)/.test(location.hash)")
        self.assertEqual(page.locator("ol.top-rows .top-warn").count(), 0)
        # Liste „Volumen gestiegen“: nur ab 1,5-fach, steigende Kurse zuerst
        self.go(page, "/potenzial?liste=volumen")
        rvol, r5 = sig["merkmale"]["rvol"], sig["merkmale"]["r5"]
        # ab 1.23 nur Aktien mit Mindestumsatz (10 Mio. USD)
        liquid_isins = {isins[i] for i, ok in enumerate(self.snap("instruments.bin")["turnover"]["liquid"]) if ok}
        listed = [k for k in range(len(sig["isin"])) if rvol[k] is not None and rvol[k] >= 1.5 and sig["isin"][k] in liquid_isins]
        listed.sort(key=lambda k: (0 if (r5[k] or 0) > 0 else 1, -rvol[k]))
        first = page.locator("ol.sig-rows > li").first
        expect(first).to_contain_text(sig["isin"][listed[0]])
        expect(first.locator(".sig-points")).to_have_text(f"{rvol[listed[0]]:.1f}×".replace(".", ","))
        # Einzelansicht: Börsenwert und Volumen-Leiste unter dem Kurs
        idx = order[0]
        self.go(page, f"/aktie/{isins[idx]}?tab=rendite&h=60")
        expect(page.locator(".kv-row", has_text="Börsenwert")).to_contain_text("€")
        expect(page.locator("figure.chart .vol-band")).to_be_visible()
        self.assertIn("Volumen", page.locator("figure.chart").first.get_attribute("aria-label"))

    def test_T120_start_page_buy_signal_and_candidates_demo_is_never_a_buy(self) -> None:
        """Ab 1.21.0 (Simons Auftrag vom 07.11.2026): ganz oben „Kaufsignal heute“, darunter die zehn Kaufkandidaten mit
        Einstieg, Stop, Ziel und CRV aus dem Signal-Stand; je Zeile ausklappbar Nachrichten, KI-Auswertung und alle
        Bedingungen. DEMO-Daten sind nie ein Kaufsignal: oben KEIN KAUF, in der Liste „DEMO-Beispiel“ statt Ampelfarben."""
        from traktien.util import crypto

        status = json.loads((self.site / "data" / "status.json").read_text(encoding="utf-8"))
        sid = status["signale"]["id"]
        sig = json.loads(crypto.unpack((self.site / "data" / "signale" / sid / "signale.bin").read_bytes(), None, f"signale/{sid}/signale.bin"))
        handel = sig["handel"]
        front = sig["listen"]["handel"][:10]
        self.assertTrue(front, "DEMO hat Kaufkandidaten")
        self.assertEqual(sig["ki"]["hinweis"], "DEMO – keine Abfrage")

        def money(value: float | None) -> str:
            if value is None:
                return "–"
            digits = 4 if abs(value) < 1 else 2
            return f"{value:,.{digits}f}".replace(",", "_").replace(".", ",").replace("_", ".")

        page = self.page()
        self.go(page, "/")
        hero = page.locator("section.signal-hero")
        expect(hero.locator(".no-buy-word")).to_have_text("KEIN KAUF")
        expect(hero.locator(".no-buy")).to_contain_text("DEMO – synthetische Testdaten")
        self.assertEqual(hero.locator(":scope > .plan-card").count(), 0, "keine Signalkarte mit DEMO-Daten")
        rows = page.locator("section.buy-list ol.buy-rows > li")
        expect(rows).to_have_count(len(front))
        expect(page.locator("section.buy-list h2")).to_have_text("Aktuelle Kaufkandidaten – Top 10")
        expect(page.locator("section.buy-list .buy-ai-state")).to_have_text("KI-Auswertung: DEMO – keine Abfrage.")
        self.assertEqual(page.locator(".plan-badge.plan-go").count(), 0, "kein Kaufsignal in Ampelgrün mit DEMO-Daten")
        shown = {}
        for n in range(rows.count()):
            row = rows.nth(n)
            isin = re.search(r"ZZ\d{10}", row.inner_text()).group(0)
            k = sig["isin"].index(isin)
            shown[isin] = k
            figs = row.locator("dl.plan-figs > div > dd")
            expect(figs).to_have_count(4)
            self.assertEqual([_plain(t) for t in figs.all_inner_texts()[:3]], [money(handel["einstieg"][k]), money(handel["stop"][k]), money(handel["ziel"][k])], isin)
            crv = handel["crv"][k]
            expect(figs.nth(3)).to_have_text("–" if crv is None else f"{crv:.1f} : 1".replace(".", ","))
            badge = row.locator(".plan-badge")
            if "buy-stop" in (row.get_attribute("class") or ""):
                expect(badge).to_have_text("Kein Kauf")
                expect(row.locator(".buy-reason")).not_to_be_empty()
            else:
                expect(badge).to_contain_text("DEMO-Beispiel:")
        self.assertEqual(sorted(shown.values()), sorted(front), "dieselben zehn Aktien wie im Signal-Stand")
        # Erste Zeile aufklappen: Nachrichten, Hinweis zur KI, alle Bedingungen der Signalregel
        first = rows.first
        first.get_by_role("button", name="Nachrichten und Bedingungen").click()
        details = first.locator(".buy-details")
        expect(details).to_contain_text("Aktuelle Nachrichten")
        expect(details.locator(".plan-ai")).to_contain_text("Keine KI-Auswertung (DEMO – keine Abfrage).")
        expect(details.locator("ul.plan-checks > li").first).to_be_visible()
        self.assertGreaterEqual(details.locator("ul.plan-checks > li").count(), 10)
        expect(details.locator(".plan-price")).to_contain_text("DEMO (synthetische Kurse)")
        # So sähe ein Signal aus: nur als gekennzeichnetes Beispiel, wenn ein DEMO-Kandidat alle Bedingungen erfüllt
        if page.locator("section.buy-list .buy-row.buy-go").count():
            hero.get_by_role("button", name="So sähe ein Signal aus (DEMO-Beispiel)").click()
            card = hero.locator(".plan-card.plan-card-demo")
            expect(card).to_be_visible()
            expect(card.locator(".plan-badge")).to_contain_text("DEMO-Beispiel: Kaufsignal")
            expect(card).to_contain_text("Einstieg noch sinnvoll?")
            expect(card.locator("dl.plan-figs > div")).to_have_count(4)
        self.assertNotIn("Offiziell", page.locator(".view").inner_text())
        self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"), page.evaluate("document.documentElement.clientWidth"))
        self.shot(page, "120_kaufsignal")
        # Alle Kandidaten: bis zu 100 Zeilen, dieselbe Regel
        page.locator("section.buy-list").get_by_role("link", name="Alle Kandidaten").click()
        self.wait_until(page, "location.hash.startsWith('#/kandidaten')")
        expect(page.locator("section.buy-list h2")).to_have_text("Alle aktuellen Kaufkandidaten")
        expect(page.locator("section.buy-list ol.buy-rows > li")).to_have_count(min(100, len(sig["listen"]["handel"])))
        expect(page.locator(".view")).to_contain_text("Die Signalregel")
        self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"), page.evaluate("document.documentElement.clientWidth"))

    def test_F09_every_main_list_starts_on_the_first_screen(self) -> None:
        """Befund F09 der Bestandsaufnahme vom 07.11.2026, ab 1.22: Auf dem S25+ (384 × 832) beginnt jede Hauptliste im
        ersten Bildschirm – mindestens 48 px der ersten Zeile sind ohne Blättern über der Navigation unten sichtbar. Vorher
        stand die erste Zeile bis zu 1.948 px tief (Ranking). Gemessen mit DEMO-Hinweis und der Warnung „Keine aktuelle
        Prüfung“ über der Ansicht, also im ungünstigsten Fall. Regler, Hinweise und Erklärung bleiben erreichbar."""
        lists = {
            "/ranking?h=30&w=60&p=native": "ol.rows > li",
            "/ranking?h=7&w=0": "ol.rows > li",
            "/rendite": "ol.window-list > li",
            "/rendite?f=alle&z=1-7": "ol.window-list > li",
            "/rendite/liste?h=7": "ol.rows > li",
            "/haeufig": "ol.std-rows > li",
            "/top": "ol.top-rows > li",
            "/potenzial": "ol.sig-rows > li",
            "/sieger": "ol.tenw > li",
            "/bericht": "ol.rep-freq > li",
            "/kandidaten": "ol.rows > li",
            "/aktien": "ul.rows > li",
        }
        page = self.page()
        for route, row in lists.items():
            with self.subTest(route=route):
                self.go(page, route)
                first = page.locator(f"main {row}").first
                expect(first).to_be_visible()
                page.evaluate("window.scrollTo(0, 0)")
                page.wait_for_timeout(100)
                top = first.bounding_box()["y"]
                nav = page.locator("nav.bottomnav").bounding_box()["y"]
                self.assertGreaterEqual(top, 0, route)
                self.assertLess(top + 48, nav, f"{route}: erste Zeile bei {top:.0f} px, Navigation unten ab {nav:.0f} px")
        self.shot(page, "26_liste_zuerst")
        # Regler, Hinweise und Erklärung bleiben vollständig erreichbar
        self.go(page, "/ranking?h=30&w=60&p=native")
        page.get_by_role("button", name=re.compile(r"^Einstellungen 30 Tage · 60\/40")).click()
        expect(page.locator(".ruler-range")).to_be_visible()
        expect(page.locator(".weight-range")).to_be_visible()
        expect(page.get_by_label("Zeitraum in Kalendertagen (1 bis 90)")).to_be_visible()
        page.get_by_role("button", name=re.compile("^Rückblick · Rangbewertung · nur Kursrendite")).click()
        expect(page.locator(".list-notes .return-basis")).to_contain_text("Nicht enthalten: Dividenden")
        expect(page.locator(".list-notes .row-legend")).to_contain_text("Rangscore")
        page.get_by_role("button", name="Zur Erklärung unter der Liste").click()
        expect(page.locator("#erklaerung")).to_be_in_viewport()
        expect(page.locator("#erklaerung .kind-chips")).to_contain_text("Rangbewertung")
        expect(page.locator("#erklaerung")).to_contain_text("Was du hier tun kannst")

    def test_T101_no_view_is_wider_than_the_phone(self) -> None:
        """Galaxy S25+ (ab 1.10): keine Ansicht darf breiter als 384 px werden. Sonst vergrößert das Handy den
        Layout-Bereich und zoomt heraus – alles wird klein, Bedienelemente liegen außerhalb des Bildschirms.
        ``window.innerWidth`` wächst dabei mit; gemessen wird deshalb gegen ``clientWidth`` (Gerätebreite)."""
        page = self.page()
        routes = (
            "/", "/rendite", "/rendite?f=alle&z=alle", "/rendite?modus=gewichtung", "/ranking?h=30&w=60&p=native", "/bericht",
            "/depots", "/depots?gw=alle", "/potenzial", "/analyse", "/matrix", "/vergleich", "/aktien", "/haeufig",
            "/haeufig/erweitert", "/haeufig/ZZ0000000412", "/sieger", "/raster", "/watchlist", "/regel", "/status", "/methodik",
            "/einstellungen", "/aktualisieren", "/top", "/top?ohne=1", "/kandidaten", "/potenzial?liste=volumen", "/aktie/ZZ0000000412?h=7", "/aktie/ZZ0000000412?tab=rendite&h=1",
            "/kursabgleich", "/pilot", "/pilot/regeln", "/pilot/chronik", "/muster", "/muster?modul=C&z=basis", "/muster?modul=B",
            "/aktie/ZZ0000000719?h=30", "/aktie/ZZ0000000719?tab=ueberblick", "/aktie/ZZ0000000719?tab=kennzahlen",
        )
        wide = []
        for route in routes:
            self.go(page, route)
            page.wait_for_timeout(150)
            sizes = page.evaluate("[document.documentElement.scrollWidth, document.documentElement.clientWidth, window.innerWidth]")
            if sizes[0] > sizes[1] + 1 or sizes[2] > sizes[1] + 1:
                wide.append(f"{route}: {sizes}")
        self.assertEqual(wide, [], "Ansichten breiter als das Handy (scrollWidth, clientWidth, innerWidth)")

    def test_status_with_an_older_stand_of_another_method_fits_the_phone(self) -> None:
        """Ab 1.18.1: „Datenstand & Betrieb“ mit einem früheren Stand anderer Methodenversion (wie im echten Datenstand seit
        dem 24.10.: der 23.10. nach tr-methode-1.9.0 neben 1.10.0). Der Hinweis „eingeschränkt vergleichbar: …“ stand als
        Badge ohne Umbruch und machte die Seite 98 px breiter als das S25+ – gefunden in Firefox und WebKit mit echten Daten;
        in Chromium wächst ``window.innerWidth`` mit, deshalb sah die Live-Prüfung es dort nicht. Die DEMO-Stände haben
        alle dieselbe Methode – deshalb hier ein zweiter Eintrag im Index."""
        import copy

        index = json.loads((self.site / "data" / "snapshots" / "index.json").read_text(encoding="utf-8"))
        extra = copy.deepcopy(index["snapshots"][0])
        extra["snapshot_id"] = extra["snapshot_id"].split("_")[0] + "_00000000"
        extra.setdefault("versions", {})["method"] = "tr-methode-1.9.0"
        index["snapshots"].append(extra)
        page = self.page()
        page.route("**/data/snapshots/index.json*", lambda route: route.fulfill(status=200, content_type="application/json", body=json.dumps(index)))
        self.go(page, "/status")
        badge = page.locator(".badge", has_text="eingeschränkt vergleichbar")
        expect(badge).to_have_count(1)
        expect(badge).to_be_visible()
        sizes = page.evaluate("[document.documentElement.scrollWidth, document.documentElement.clientWidth, window.innerWidth]")
        self.assertLessEqual(sizes[0], sizes[1] + 1, f"Seite breiter als das Handy (scrollWidth, clientWidth, innerWidth) {sizes}")
        self.assertLessEqual(sizes[2], sizes[1] + 1, f"Handy zoomt heraus (scrollWidth, clientWidth, innerWidth) {sizes}")
        box = badge.bounding_box()
        self.assertLessEqual(box["x"] + box["width"], sizes[1] + 1, "Hinweis innerhalb des Bildschirms")
        self.assertEqual(badge.evaluate("el => el.scrollWidth <= el.clientWidth + 1"), True, "Text bricht im Hinweis um, statt hinauszuragen")

    def test_system_text_scale_up_to_200_percent_fits_the_phone(self) -> None:
        """Ab 1.18.2: Die App übernimmt die Schriftgröße des Handys (``<meta name="text-scale" content="scale">``, Chrome für
        Android ab 146: Schriften in rem wachsen mit der Systemschrift). Anlass: Im Android-Emulator (Chrome 124) wuchs mit
        Systemschrift 130 % ein langer Absatz, die Texte der App nicht (24.10.2026). Hier – Desktop-Simulation, kein Gerät –
        wird die Wirkung nachgestellt: Grundschrift der Seite 130, 150, 175 und 200 %; keine Ansicht darf breiter als das
        S25+ werden, und die Schrift muss wirklich größer sein. Gemessen mit der breiten Schrift „DejaVu Sans“ (in der
        Entwicklungsumgebung und in GitHub Actions vorhanden): Die Systemschrift löst je Rechner anders auf – in GitHub Actions
        waren mit ihr 8 Ansichten zu breit, lokal keine (24.10.2026, 22:52 Uhr); mit derselben breiten Schrift überall gilt
        das Ergebnis für beide und erst recht für die schmalere Schrift des S25+."""
        page = self.page()
        self.go(page, "/")
        self.assertEqual(page.locator('meta[name="text-scale"]').get_attribute("content"), "scale", "Opt-in für die Systemschrift fehlt")
        routes = (  # dieselben Ansichten wie in T101 und die Hilfe
            "/", "/rendite", "/rendite?f=alle&z=alle", "/rendite?modus=gewichtung", "/ranking?h=30&w=60&p=native", "/bericht",
            "/depots", "/depots?gw=alle", "/potenzial", "/analyse", "/matrix", "/vergleich", "/aktien", "/haeufig",
            "/haeufig/erweitert", "/haeufig/ZZ0000000412", "/sieger", "/raster", "/watchlist", "/regel", "/status", "/methodik",
            "/einstellungen", "/aktualisieren", "/top", "/top?ohne=1", "/kandidaten", "/potenzial?liste=volumen", "/aktie/ZZ0000000412?h=7", "/aktie/ZZ0000000412?tab=rendite&h=1",
            "/aktie/ZZ0000000719?h=30", "/aktie/ZZ0000000719?tab=ueberblick", "/aktie/ZZ0000000719?tab=kennzahlen", "/hilfe", "/pilot", "/pilot/regeln",
        )
        wide = []
        for scale in (130, 150, 175, 200):
            for route in routes:
                self.go(page, route)
                sizes = page.evaluate(
                    f"""() => {{ document.documentElement.style.fontSize = '{scale}%';
                        document.documentElement.style.setProperty('--font-ui', "'DejaVu Sans', sans-serif");
                        document.documentElement.style.setProperty('--font-num', "'DejaVu Sans Condensed', 'DejaVu Sans', sans-serif");
                        // Zeilen des Datums in der Kopfzeile (ohne die Beschriftung „Kursstand“)
                        const dateLines = () => {{ const d = document.querySelector('.stand-date'); if (!d) return 1;
                            const text = [...d.childNodes].filter((n) => n.nodeType === 3 && n.textContent.trim()).pop(); if (!text) return 1;
                            const range = document.createRange(); range.selectNodeContents(text);
                            return new Set([...range.getClientRects()].map((r) => Math.round(r.top))).size; }};
                        return new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve([
                            document.documentElement.scrollWidth, document.documentElement.clientWidth, window.innerWidth,
                            parseFloat(getComputedStyle(document.body).fontSize), dateLines()])))); }}"""
                )
                self.assertAlmostEqual(sizes[3], 16 * scale / 100, delta=0.1, msg=f"{route} {scale} %: Grundschrift der App folgt nicht")
                self.assertEqual(sizes[4], 1, f"{route} {scale} %: Datum in der Kopfzeile bricht mitten in der Zahl um")
                if sizes[0] > sizes[1] + 1 or sizes[2] > sizes[1] + 1:
                    wide.append(f"{scale} % {route}: {sizes[:3]}")
        self.assertEqual(wide, [], "Ansichten mit großer Schrift breiter als das Handy (scrollWidth, clientWidth, innerWidth)")

    def test_option_buttons_never_break_inside_a_word(self) -> None:
        """Ab 1.19.1: Die Knöpfe der Auswahlleisten (Gesamt/Kurz/Lang/Kursziel/Volumen auf der Startseite, Depots, Raster …)
        brechen nie mitten im Wort um. Seit 1.18.2 erbten sie „overflow-wrap: anywhere“ vom Inhaltsbereich und schrumpften
        so weit, dass schon bei normaler Schrift „Gesam|t“, „Kur|z“ und „Dreierdep|ot“ entstand (gefunden am 25.10.2026 bei
        der Durchsicht der Ansichten im Format des S25+; 1.18.1 hatte das nicht). Geprüft mit normaler und doppelter Schrift
        und der breiten Schrift „DejaVu Sans“ wie im Test darüber; reicht der Platz nicht, blättert die Leiste seitlich."""
        page = self.page()
        routes = ("/", "/potenzial", "/potenzial?liste=volumen", "/depots", "/depots?gw=alle", "/raster", "/rendite", "/rendite?modus=gewichtung",
                  "/ranking?h=30&w=60&p=native", "/matrix", "/haeufig", "/sieger", "/einstellungen", "/aktie/ZZ0000000719?h=30", "/aktie/ZZ0000000412?tab=rendite&h=1")
        broken, buttons = [], 0
        for scale in (100, 200):
            for route in routes:
                self.go(page, route)
                found = page.evaluate(
                    f"""() => {{ document.documentElement.style.fontSize = '{scale}%';
                        document.documentElement.style.setProperty('--font-ui', "'DejaVu Sans', sans-serif");
                        return new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => {{
                          const out = []; let count = 0;
                          for (const button of document.querySelectorAll('.segmented button')) {{
                            if (!button.getClientRects().length) continue;
                            count += 1;
                            const walker = document.createTreeWalker(button, NodeFilter.SHOW_TEXT);
                            let node;
                            while ((node = walker.nextNode())) {{
                              for (const m of node.textContent.matchAll(/[\\p{{L}}\\p{{N}}]{{2,}}/gu)) {{
                                const range = document.createRange();
                                range.setStart(node, m.index); range.setEnd(node, m.index + m[0].length);
                                const tops = new Set([...range.getClientRects()].filter((r) => r.width > 0).map((r) => Math.round(r.top)));
                                if (tops.size > 1) out.push(m[0]);
                              }}
                            }}
                          }}
                          resolve([count, out]); }}))); }}"""
                )
                buttons += found[0]
                broken += [f"{scale} % {route}: {word}" for word in found[1]]
        self.assertGreater(buttons, 100, "zu wenige Knöpfe gefunden – Prüfung wirkungslos")
        self.assertEqual(broken, [], "Wörter in Knöpfen der Auswahlleisten mitten im Wort umgebrochen")

    # Bewusst schmale Stellen (so schon bis 1.18.1): Namen und ISIN in schmalen Tabellenspalten und Zellen brechen um, damit
    # Tabellen und Raster ohne seitliches Blättern auf 384 px passen – erste Spalte der Tabellen („sticky“, Häufigkeit und
    # Vergleich), Namen in der Häufigkeitstabelle, im Bericht 1–30, in der Matrix und unter „Alle Gewichtungen“ der Depots.
    # Mit der breiten Prüfschrift trifft das hier nur die langen DEMO-Namen („Übernahmeangebot“, „Nordlicht“, „Impulstag“).
    NARROW_BY_DESIGN = ("sticky", "gcell-isin", "gcell-name", "table-pick", "rm-name", "rep-name", "dq-name")

    def test_no_word_or_number_breaks_inside_at_normal_font_size(self) -> None:
        """Ab 1.19.2: Bei normaler Schrift bricht in keiner der 34 Ansichten (ab 1.20.0 mit „Kursabgleich“) ein Wort oder eine Zahl (ab zwei Zeichen) mitten
        im Wort um – außer an den bewusst schmalen Stellen oben. Anlass: Seit 1.18.2 (``overflow-wrap: anywhere`` im
        Inhaltsbereich) brachen Auswahlknöpfe („Gesam|t“) und die Beschriftung „90“ am rechten Ende des Zeitraum-Lineals
        („9“ über „0“, in 9 Ansichten) um; 1.19.1 behob nur die Knöpfe. Gefunden mit einer Durchsicht aller Ansichten im
        Format des S25+ (25.10.2026). Gemessen mit der breiten Schrift „DejaVu Sans“ wie die Tests darüber."""
        page = self.page()
        routes = (
            "/", "/rendite", "/rendite?f=alle&z=alle", "/rendite?modus=gewichtung", "/ranking?h=30&w=60&p=native", "/bericht",
            "/depots", "/depots?gw=alle", "/potenzial", "/analyse", "/matrix", "/vergleich", "/aktien", "/haeufig",
            "/haeufig/erweitert", "/haeufig/ZZ0000000412", "/sieger", "/raster", "/watchlist", "/regel", "/status", "/methodik",
            "/einstellungen", "/aktualisieren", "/top", "/top?ohne=1", "/kandidaten", "/potenzial?liste=volumen", "/aktie/ZZ0000000412?h=7", "/aktie/ZZ0000000412?tab=rendite&h=1",
            "/aktie/ZZ0000000719?h=30", "/aktie/ZZ0000000719?tab=ueberblick", "/aktie/ZZ0000000719?tab=kennzahlen", "/hilfe",
        )
        narrow = json.dumps(list(self.NARROW_BY_DESIGN))
        broken, words = [], 0
        for route in routes:
            self.go(page, route)
            found = page.evaluate(
                f"""() => {{ document.documentElement.style.fontSize = '100%';
                    document.documentElement.style.setProperty('--font-ui', "'DejaVu Sans', sans-serif");
                    document.documentElement.style.setProperty('--font-num', "'DejaVu Sans Condensed', 'DejaVu Sans', sans-serif");
                    const narrow = {narrow};
                    return new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => {{
                      const out = []; let count = 0;
                      for (const root of [document.querySelector('.main'), document.querySelector('.bottomnav')].filter(Boolean)) {{
                        const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
                        let node;
                        while ((node = walker.nextNode())) {{
                          const el = node.parentElement;
                          if (!el || narrow.some((c) => el.closest('.' + c))) continue;
                          for (const m of node.textContent.matchAll(/[\\p{{L}}\\p{{N}}]{{2,}}/gu)) {{
                            const range = document.createRange();
                            range.setStart(node, m.index); range.setEnd(node, m.index + m[0].length);
                            const rects = [...range.getClientRects()].filter((r) => r.width > 0 && r.height > 0);
                            if (!rects.length) continue;
                            count += 1;
                            if (new Set(rects.map((r) => Math.round(r.top))).size > 1) out.push(m[0] + ' (' + (el.className || el.tagName) + ')');
                          }}
                        }}
                      }}
                      resolve([count, out]); }}))); }}"""
            )
            words += found[0]
            broken += [f"{route}: {word}" for word in found[1]]
        self.assertGreater(words, 5000, "zu wenige Wörter gefunden – Prüfung wirkungslos")
        self.assertEqual(broken, [], "Wörter oder Zahlen mitten im Wort umgebrochen (normale Schrift)")

    def test_T100_all_windows_weights_and_main_lists_reachable(self) -> None:
        page = self.page()
        self.go(page, "/rendite?z=alle")
        hrefs = page.locator("ol.window-list > li .row-name[href]").evaluate_all("(els) => els.map((a) => a.getAttribute('href'))")
        windows = {int(re.search(r"[?&]h=(\d+)", href).group(1)) for href in hrefs}
        self.assertEqual(windows, set(range(1, 91)), "jeder Zeitraum erreichbar")
        self.go(page, "/ranking?h=30&w=60")
        self.open_line(page, "settings")
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
        Gewichtung und Kursgrafik wechseln gemeinsam – Sollwerte aus den Fensterdateien des Stands (ab 1.23 die Ranglisten
        mit Mindestumsatz)."""
        isins = self.snap("instruments.bin")["isin"]
        page = self.page()
        self.go(page, "/ranking?h=90&w=60&p=native")
        chips = page.get_by_role("group", name="Zeitraum wählen (Kalendertage)")
        expect(chips.get_by_role("button")).to_have_count(10)
        self.assertEqual([_plain(t).split()[0] for t in chips.get_by_role("button").all_inner_texts()], [str(h) for h in FIXED])
        self.open_line(page, "settings")
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
            order = self.order(win, "b", 60)
            if not order:
                expect(page.get_by_text("Keine Rangliste für diese Auswahl")).to_be_visible()
                expect(page.get_by_text("Für die Gleichmäßigkeit sind mindestens 15 echte Tageskurse nötig", exact=False)).to_be_visible()
                continue
            first = page.locator("ol.rows > li").first
            expect(first.locator(".isin-code")).to_have_text(isins[order[0]])
            pos = win["m"]["idx"].index(order[0])
            self.assertAlmostEqual(_number(first.locator(".row-figs .pct").inner_text()), 100 * win["m"]["r"][pos], delta=0.006)
            expect(first.locator(".row-figs")).to_contain_text("Rangscore")
        self.assertTrue(any(not self.order(self.snap(f"windows/{h}.full.bin"), "b", 60) for h in FIXED), "kurze Fenster ohne Gleichmäßigkeit")
        # keine Gruppenwahl mehr; reine Rendite: die Gewichtung bleibt beim Zeitraumwechsel erhalten
        expect(page.get_by_role("radio", name=re.compile(r"Ø Umsatz ≥|^(A|B)[ :·]"))).to_have_count(0)
        self.go(page, page.evaluate("location.hash").replace("#", "").replace("w=60", "w=0"))
        for h in (7, 90):
            chips.get_by_role("button", name=f"{h} Tage", exact=True).click()
            self.wait_until(page, f"/[?&]h={h}(&|$)/.test(location.hash) && /[?&]w=0(&|$)/.test(location.hash)")
            win = self.snap(f"windows/{h}.full.bin")
            order = self.order(win, "b", 0)
            expect(page.locator("ol.rows > li").first.locator(".isin-code")).to_have_text(isins[order[0]])
            self.assertNotEqual(order, win["orders"]["v0"], "Plätze ohne die Aktien unter dem Mindestumsatz gezählt")
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
        """Prüfung 20: „Sieger nach Zeitraum“ – zehn Zeilen; ab 1.23 je Zeile eine Zelle = Platz 1 der vollständigen
        Rangliste mit Mindestumsatz desselben Fensters, je Gewichtung; eigene Zählung über genau diese zehn Zeilen."""
        isins = self.snap("instruments.bin")["isin"]
        page = self.page()
        self.go(page, "/sieger?w=60")
        rows = page.locator("ol.tenw > li")
        expect(rows).to_have_count(10)
        self.assertEqual([int(t) for t in rows.locator(".tenw-days").all_inner_texts()], list(FIXED))
        expect(page.locator(".tenw-a")).to_have_count(0)
        expect(rows.first.locator(".tenw-cell")).to_have_count(1)
        weights = page.get_by_role("radiogroup", name="Gewichtung Gleichmäßigkeit/Kursrendite")
        expect(weights.get_by_role("radio")).to_have_count(11)
        expect(weights.get_by_role("radio", name="60/40")).to_have_attribute("aria-checked", "true")
        self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"), page.evaluate("document.documentElement.clientWidth"), "Karten statt überbreiter Tabelle")
        self.shot(page, "24_sieger_nach_zeitraum")
        for weight in (60, 0, 50, 100, 10):
            if weight != 60:
                weights.get_by_role("radio", name=f"{weight}/{100 - weight}").click()
                self.wait_until(page, f"/[?&]w={weight}(&|$)/.test(location.hash)")
            for k, h in enumerate(FIXED):
                win = self.snap(f"windows/{h}.full.bin")
                cell = rows.nth(k).locator(".tenw-b")
                order = self.order(win, "b", weight)
                if not order:
                    expect(cell).to_have_class(re.compile("is-empty"))
                    if weight and h <= 14:
                        expect(cell).to_contain_text("Gleichmäßigkeit nicht berechenbar")
                    continue
                expect(cell.locator(".gcell-isin")).to_have_text(isins[order[0]])
                pos = win["m"]["idx"].index(order[0])
                self.assertAlmostEqual(_number(cell.locator(".pct").first.inner_text()), 100 * win["m"]["r"][pos], delta=0.006, msg=f"{h} Tage {weight}")
                if weight:
                    expect(cell).to_contain_text("Rangscore")
        # kurze gewichtete Fenster: Hinweis und Weg zum 0/100-Renditesieger, kein Ersatz durch ein längeres Fenster
        weights.get_by_role("radio", name="60/40").click()
        self.wait_until(page, "/[?&]w=60(&|$)/.test(location.hash)")
        first_row = rows.nth(0)
        expect(first_row.locator(".tenw-b")).to_contain_text("Gleichmäßigkeit nicht berechenbar")
        expect(first_row.locator(".tenw-b .gcell-isin")).to_have_count(0)
        expect(first_row.get_by_role("button", name="0/100-Renditesieger ansehen")).to_be_visible()
        # Antippen: Start, Ende, Schlusskurse und Referenzmarkt
        k = next(i for i, h in enumerate(FIXED) if self.order(self.snap(f"windows/{h}.full.bin"), "b", 60))
        h = FIXED[k]
        win = self.snap(f"windows/{h}.full.bin")
        idx = self.order(win, "b", 60)[0]
        pos = win["m"]["idx"].index(idx)
        rows.nth(k).locator(".tenw-b .tenw-pick").click()
        detail = rows.nth(k).locator(".tenw-b .tenw-detail")
        expect(detail).to_contain_text(self.day(win["m"]["start"][pos]))
        expect(detail).to_contain_text(self.day(win["cutoff_day"]))
        expect(detail.locator(".kv-row", has_text="Schlusskurse im Fenster")).to_contain_text(str(win["m"]["n"][pos]))
        expect(detail.locator(".kv-row", has_text="Referenzmarkt")).not_to_contain_text("–")
        detail.get_by_role("link", name="Ganze Rangliste").click()
        self.wait_until(page, f"location.hash.startsWith('#/ranking') && /[?&]h={h}(&|$)/.test(location.hash) && /[?&]w=60(&|$)/.test(location.hash)")
        expect(page.locator("ol.rows > li").first.locator(".isin-code")).to_have_text(isins[idx])
        page.go_back()
        # eigene Zählung über genau diese zehn Zeiträume
        expect(page.get_by_role("heading", name="Zählung nur über diese zehn Zeiträume")).to_be_visible()
        expected: dict[int, int] = {}
        for h in FIXED:
            order = self.order(self.snap(f"windows/{h}.full.bin"), "b", 60)
            if order:
                expected[order[0]] = expected.get(order[0], 0) + 1
        repeated = {isins[i]: c for i, c in expected.items() if c >= 2}
        table = page.locator("table.tenw-count tbody tr")
        expect(table).to_have_count(len(repeated))
        if repeated:
            self.assertLessEqual(page.locator("table.tenw-count").evaluate("el => el.closest('.table-wrap').scrollWidth - el.closest('.table-wrap').clientWidth"), 0)
        for row in table.all():
            isin = row.locator(".gcell-isin").inner_text()
            self.assertEqual(int(row.locator("td").nth(0).inner_text()), repeated[isin])

    def test_report_1_30_tables_matrix_marking_frequency_and_csv(self) -> None:
        """Bericht 1–30 (ab 1.8.1) wie die Berichtsdatei: vier Tabellen untereinander, jede Zelle = Platz 1 der
        Übersicht desselben Stands (ab 1.23 nur die Rangliste mit Mindestumsatz), kurze leere Zeiträume zusammengefasst,
        Matrix mit vier Gewichtungen, Hervorheben einer ISIN auf der ganzen Seite, Häufigkeit und CSV mit 120 Kombinationen."""
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
        self.open_line(page, "notes")
        expect(page.locator(".rep-stats > div")).to_have_count(4)
        expect(page.locator("table.rep-table")).to_have_count(4)
        self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"), page.evaluate("document.documentElement.clientWidth"), "keine seitliche Verschiebung")
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
                        self.assertIsNone(top("b", weight, h), f"{weight}: {h} Tage zusammengefasst, aber berechnet")
                    seen.update(span)
                    continue
                h = int(label)
                seen.add(h)
                self.assertEqual(len(cells), 1, "eine Spalte: Platz 1 mit Mindestumsatz")
                idx = top("b", weight, h)
                self.assertEqual(cells[0], None if idx is None else isins[idx], f"{weight}/{100 - weight}, {h} Tage")
            self.assertEqual(seen, set(range(1, 31)), f"{weight}: jeder Zeitraum 1–30 genau einmal")
        first = page.locator("table.rep-table").first.locator("tbody tr").first
        win = self.snap("windows/1.full.bin")
        idx = top("b", 0, 1)
        self.assertAlmostEqual(_number(first.locator("td").first.locator(".pct").inner_text()), 100 * win["m"]["r"][win["m"]["idx"].index(idx)], delta=0.006)

        # eine Gewichtung allein
        page.get_by_role("radiogroup", name="Gewichtung Gleichmäßigkeit/Kursrendite").get_by_role("radio", name="50/50", exact=True).click()
        self.wait_until(page, "/[?&]w=50(&|$)/.test(location.hash)")
        expect(page.locator("table.rep-table")).to_have_count(1)
        expect(page.locator("#bericht-w50")).to_be_visible()

        # Matrix: vier Gewichtungen nebeneinander, ohne Gruppenwahl
        matrix = page.locator("table.rep-matrix tbody tr")
        expect(matrix).to_have_count(30)
        expect(page.get_by_role("radiogroup", name="Gruppe", exact=True)).to_have_count(0)
        names = page.evaluate("() => [...document.querySelectorAll('table.rep-matrix tbody tr:last-child td')].map(td => td.querySelector('.rm-name')?.textContent ?? null)")
        expected = [None if top("b", w, 30) is None else name(top("b", w, 30)) for w in (0, 40, 50, 60)]
        self.assertEqual(names, expected, "Matrix mit Mindestumsatz, 30 Tage")
        self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"), page.evaluate("document.documentElement.clientWidth"), "Matrix ohne seitliches Wischen")

        # Am häufigsten auf Platz 1: Zählung nur mit Mindestumsatz, vier Gewichtungen, 1–30 Tage
        counts: dict[int, int] = {}
        for w in (0, 40, 50, 60):
            for h in range(1, 31):
                idx = top("b", w, h)
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

        # Hervorheben: alle Vorkommen in Tabelle (50/50) und Matrix
        leaders.first.get_by_role("button").click()
        self.wait_until(page, f"location.hash.includes('m={isins[leader]}')")
        bar = page.locator(".rep-markbar")
        expect(bar).to_contain_text(name(leader))
        expect(bar).to_contain_text(f"{counts[leader]}× Platz 1 in 1–30 Tagen")
        hits = sum(1 for h in range(1, 31) if top("b", 50, h) == leader) + sum(1 for h in range(1, 31) for w in (0, 40, 50, 60) if top("b", w, h) == leader)
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

        # CSV: alle 30 × 4 Spitzenreiter (ohne Spalte „Gruppe“)
        with page.expect_download() as info:
            page.get_by_role("button", name="Bericht herunterladen (CSV)").click()
        lines = Path(info.value.path()).read_bytes().decode("utf-8").lstrip("﻿").strip().split("\r\n")
        header = lines.index("Gewichtung;Tage;Unternehmen;ISIN;Kursrendite;Score;R²;Start;Ende;Einheit;Hinweis")
        body = lines[header + 1 :]
        self.assertEqual(len(body), 120)
        self.assertTrue(body[0].startswith("0/100;1;"), body[0])
        self.assertIn(isins[top("b", 0, 1)], body[0])
        self.assertIn(self.snapshot_id, "\n".join(lines[:header]))

    def test_start_report_teaser_opens_report_with_marked_leader(self) -> None:
        """Startseite (ab 1.8.2): „Bericht 1–30 Tage“ direkt unter den Kandidaten – die drei häufigsten
        Spitzenreiter; Antippen öffnet den Bericht mit dieser Aktie hervorgehoben."""
        isins = self.snap("instruments.bin")["isin"]
        ov = self.snap("overview.bin")
        counts: dict[int, int] = {}
        # ab 1.23 nur die Ranglisten mit Mindestumsatz
        for rows in (ov["v0l"], ov["ul"]["40"], ov["ul"]["50"], ov["ul"]["60"]):
            for row in rows[:30]:
                if row.get("idx") is not None and not row.get("empty"):
                    counts[row["idx"]] = counts.get(row["idx"], 0) + 1
        leaders = sorted(counts, key=lambda i: (-counts[i], isins[i]))[:3]
        page = self.page()
        self.go(page, "/")
        teaser = page.locator("section.report-teaser")
        expect(teaser.get_by_role("heading", name="Bericht 1–30 Tage")).to_be_visible()
        items = teaser.locator("ol.rep-teaser > li")
        expect(items).to_have_count(len(leaders))
        for k, idx in enumerate(leaders):
            expect(items.nth(k).locator("b")).to_have_text(f"{counts[idx]}× Platz 1")
        items.first.get_by_role("link").click()
        self.wait_until(page, f"location.hash.startsWith('#/bericht') && location.hash.includes('m={isins[leaders[0]]}')")
        expect(page.locator(".rep-markbar")).to_contain_text(f"{counts[leaders[0]]}× Platz 1 in 1–30 Tagen")
        expect(page.locator("td.is-marked").first).to_be_attached()

    def test_depots_lists_contributions_windows_and_own_depot(self) -> None:
        """Musterdepots (ab 1.9) wie im Bericht „Zwei Zehnerdepots“: zwei Top-10-Listen mit gemeinsamen Aktien,
        Depotrendite = Mittel der Aktienrenditen (gleiche Startbeträge), unabhängig aus Kursreihen und
        Euro-Referenzkursen nachgerechnet (USD und Originalwährung), Beiträge, 30 Fenster, eigenes Depot."""
        from traktien.util import crypto

        inst = self.snap("instruments.bin")
        isins = inst["isin"]
        ov = self.snap("overview.bin")
        manifest = self.snap("manifest.bin")
        cutoff = manifest["cutoff_day"]
        fx = self.snap("fx.bin")

        def series(isin: str) -> dict:
            path = self.site / "data" / "snapshots" / self.snapshot_id / "series" / f"{isin}.bin"
            return json.loads(crypto.unpack(path.read_bytes(), None, f"snapshots/{self.snapshot_id}/series/{isin}.bin"))

        def per_eur(currency: str, day: int) -> float | None:
            if currency == "EUR":
                return 1.0
            column = fx["je_eur"].get(currency)
            if column is None:
                return None
            for k in range(len(fx["tage"]) - 1, -1, -1):
                d = fx["tage"][k]
                if d <= day and day - d <= fx["max_alter_tage"] and column[k]:
                    return column[k]
                if day - d > fx["max_alter_tage"]:
                    break
            return None

        def stock_return(isin: str, h: int, basis: str) -> float | None:
            s = series(isin)
            d, c = s["d"], s["c"]
            end = max(k for k, day in enumerate(d) if day <= cutoff)
            before = [k for k, day in enumerate(d) if day <= cutoff - h]
            if not before or cutoff - h - d[before[-1]] > 7:
                return None
            start = before[-1]
            local = c[end] / c[start] - 1
            if basis == "lokal":
                return local
            cur = s["listing"]["currency"].upper()
            if cur == "USD":
                return local
            usd0, usd1 = per_eur("USD", d[start]), per_eur("USD", d[end])
            own0, own1 = per_eur(cur, d[start]), per_eur(cur, d[end])
            return (c[end] * usd1 / own1) / (c[start] * usd0 / own0) - 1

        # Ab 1.10 Standard (Wunsch vom 14.10.): 1–30 Tage, 40/60, 50/50, 60/40, Top 20; ab 1.23 nur mit Mindestumsatz
        lists = [ov["ul"][str(w)] for w in (40, 50, 60)]
        counts: dict[int, int] = {}
        for rows in lists:
            for row in rows[:30]:
                if row.get("idx") is not None and not row.get("empty"):
                    counts[row["idx"]] = counts.get(row["idx"], 0) + 1
        leader = sorted(counts, key=lambda i: (-counts[i], isins[i]))[0]

        page = self.page()
        self.go(page, "/depots")
        kpis = page.locator(".dq-kpis > div")
        expect(kpis.nth(0)).to_contain_text(str(counts[leader]))
        name = inst["name"][leader] or inst["tr_name"][leader]
        expect(kpis.nth(0)).to_contain_text(name)
        rows = page.locator(".dq-list > li")
        expect(rows.first).to_be_visible()
        both = page.locator(".dq-list > li.is-both")
        expect(kpis.nth(2)).to_contain_text(f"{both.count()} gemeinsam")
        self.assertLessEqual(rows.count(), 40)
        expect(page.locator(".dq-list > li .dq-both").first).to_have_text("In beiden Top 20")
        expect(page.locator(".dq-section .section-note").nth(1)).to_contain_text("40/60, 50/50, 60/40")
        # Option „ausführlich“ (alle elf Gewichtungen wie in der Datei v3) und Top 10
        page.get_by_label("Gewichtungen (Gleichmäßigkeit/Rendite)").select_option("alle")
        self.wait_until(page, "/[?&]gw=alle(&|$)/.test(location.hash)")
        expect(page.locator(".dq-section .section-note").nth(1)).to_contain_text("alle 11 Gewichtungen")
        page.get_by_role("radiogroup", name="Listenlänge").get_by_role("radio", name="Top 10").click()
        self.wait_until(page, "/[?&]n=10(&|$)/.test(location.hash)")
        self.assertLessEqual(rows.count(), 20)
        # Erklärblöcke: Sieger je Gewichtung (11 Zeilen) und Rechenbeispiel 30 Tage
        page.get_by_role("button", name="Welche Aktie gewinnt bei welcher Gewichtung am häufigsten?").click()
        expect(page.locator(".dq-explain table").first.locator("tbody tr")).to_have_count(11)
        page.get_by_role("button", name="Wie werden 0/100 bis 100/0 berechnet").click()
        expect(page.locator(".dq-explain").get_by_text("Score = G/100", exact=False)).to_be_visible()
        page.get_by_role("button", name="Was ändert sich mit allen elf Gewichtungen?").click()
        expect(page.locator(".dq-explain").get_by_text("Ranglisten steigt von", exact=False)).to_be_visible()
        self.go(page, "/depots")
        self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"), page.evaluate("document.documentElement.clientWidth"), "keine seitliche Verschiebung")
        self.shot(page, "42_depots_haeufigkeit")

        # Depot „10 Sieger“, 30 Tage, USD
        picker = page.get_by_role("radiogroup", name="Depot")
        expect(picker.get_by_role("radio", name="10 Sieger")).to_have_attribute("aria-checked", "true")
        positions = page.locator(".dp-list > li")
        expect(positions.first).to_be_visible()
        # ab 1.14: „10 Sieger“ hat immer zehn Positionen (aufgefüllt nach Top 3, dann Top 10, wenn weniger Aktien siegen)
        expect(positions).to_have_count(10)

        def check(h: int, basis: str) -> None:
            members = [t.strip() for t in positions.locator(".dp-main > small").all_inner_texts()]
            returns = [stock_return(isin, h, basis) for isin in members]
            self.assertTrue(all(r is not None for r in returns), members)
            expected = 100 * sum(returns) / len(returns)
            shown = _number(page.locator(".dp-kpi-main .pct").inner_text())
            self.assertAlmostEqual(shown, expected, delta=0.006, msg=f"Depotrendite {h} Tage {basis}")
            pps = [_number(t) for t in positions.locator(".dp-pp").all_inner_texts()]
            self.assertAlmostEqual(sum(pps), expected, delta=0.006 * len(pps) + 0.006, msg="Beiträge ergeben die Depotrendite")

        check(30, "usd")
        self.shot(page, "43_depot_beitraege")
        page.get_by_role("radiogroup", name="Rechenbasis").get_by_role("radio", name="Originalwährung").click()
        page.get_by_role("group", name=re.compile("^Kalendertage")).get_by_role("button", name="14", exact=True).click()
        self.wait_until(page, "/[?&]t=14(&|$)/.test(location.hash)")
        check(14, "lokal")
        # Alle Depots: 30 Fenster, gewähltes Fenster = Kennzahl oben
        table = page.locator("table.hz-table tbody tr")
        expect(table).to_have_count(30)
        row14 = table.nth(13)
        self.assertAlmostEqual(_number(row14.locator("td").first.inner_text()), _number(page.locator(".dp-kpi-main .pct").inner_text()), delta=0.051)
        # Eigenes Depot aus zwei Aktien der Liste
        boxes = page.locator(".dq-list > li input[type=checkbox]")
        boxes.nth(0).check()
        boxes.nth(1).check()
        bar = page.locator(".dp-pickbar")
        expect(bar).to_contain_text("2 ausgewählt")
        bar.get_by_role("textbox", name="Name des Depots").fill("Testdepot")
        bar.get_by_role("button", name="Als Depot speichern").click()
        self.wait_until(page, "/[?&]depot=eigen-/.test(location.hash)")
        expect(picker.get_by_role("radio", name="Testdepot")).to_have_attribute("aria-checked", "true")
        expect(positions).to_have_count(2)
        page.get_by_role("button", name="„Testdepot“ bearbeiten").click()
        page.locator(".dp-editor").get_by_role("button", name="Depot löschen").click()
        expect(picker.get_by_role("radio", name="Testdepot")).to_have_count(0)

    def test_frequency_filters_order_counts_and_exports(self) -> None:
        """Häufigste Aktien (ab 1.23 nur Aktien mit Mindestumsatz, ohne Gruppenwahl): Filter Gewichtungen, Zeitspanne,
        identische Fenster; zwei Sortierungen; Zähler und Nenner wie aus den Serverdaten nachgezählt; CSV/JSON mit Filterangaben."""
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
        # ab 1.22 (F09): Regler unter „Einstellungen“, Auswahl und Nenner in der Hinweiszeile – beide bleiben hier offen
        self.open_line(page, "settings")
        self.open_line(page, "notes")
        expect(page.get_by_role("radio", name="Gewinnt am häufigsten")).to_have_attribute("aria-checked", "true")
        # Standard: nur Aktien mit Mindestumsatz, alle elf Gewichtungen, 1–90 Tage – Zähler und Nenner wie nachgezählt
        expect(page.get_by_role("radio", name=re.compile(r"^(A|B)\b|A und B"))).to_have_count(0)
        table, denominator = counts("b", WEIGHTS, 1, 90)
        expect(page.locator(".scope-note")).to_contain_text(f"Berechenbare Kombinationen (Nenner): {denominator:,} von".replace(",", "."))
        expect(page.locator(".scope-note")).to_contain_text("Aktien mit Ø Tagesumsatz ab 10 Mio. USD")
        shown = visible_rows(page)
        self.assertGreater(len(shown), 5)
        for isin, n1, n3, n10 in shown:
            self.assertEqual([n1, n3, n10], table[isin], isin)
        self.assertEqual([r[1:] for r in shown], sorted([r[1:] for r in shown], reverse=True), "Platz 1, dann Top 3, dann Top 10")
        expect(page.locator(".mark").first).to_contain_text("↻")
        # Beide Standardlisten sichtbar (Gesamtauftrag vom 31.10.2026, Abschnitt 5.3): die zehn mit den meisten Platz-1-Platzierungen
        # und die zehn mit den meisten Top-10-Nennungen – aus derselben Zählung, nebeneinander bzw. auf dem Handy untereinander
        expect(page.get_by_role("heading", name="Meiste Platz-1-Platzierungen")).to_be_visible()
        expect(page.get_by_role("heading", name="Meiste Top-10-Nennungen")).to_be_visible()
        self.assertLessEqual(page.locator(".std-pair").evaluate("el => el.scrollWidth - el.clientWidth"), 0, "Standardlisten ohne seitliches Blättern")

        def std_rows(nth: int) -> list[tuple[str, int, int]]:
            out = []
            for li in page.locator(".std-list").nth(nth).locator("ol.std-rows > li").all():
                href = li.locator("a.std-name").get_attribute("href") or ""
                isin = href.split("/aktie/")[1].split("?")[0]
                small = _plain(li.locator(".std-fig small").inner_text())
                out.append((isin, int(_plain(li.locator(".std-fig strong").inner_text()).replace(".", "")), int(small.split()[-1].replace(".", ""))))
            return out

        want_p1 = sorted((kv for kv in table.items() if kv[1][0] > 0), key=lambda kv: (-kv[1][0], -kv[1][1], -kv[1][2], kv[0]))[:10]
        want_t10 = sorted(table.items(), key=lambda kv: (-kv[1][2], -kv[1][1], -kv[1][0], kv[0]))[:10]
        self.assertEqual(std_rows(0), [(i, c[0], c[2]) for i, c in want_p1], "meiste Platz 1 (dazu Top 10)")
        self.assertEqual(std_rows(1), [(i, c[2], c[0]) for i, c in want_t10], "meiste Top 10 (dazu Platz 1)")
        rule = page.locator(".std-list").nth(0).get_by_role("link", name="Als Robo-Regel verwenden").get_attribute("href") or ""
        for part in ("quelle=haeufigkeit", "k=1", "von=1", "bis=90", "gruppe=B", "politik=native", "gewichte=0%2C10%2C20%2C30%2C40%2C50%2C60%2C70%2C80%2C90%2C100"):
            self.assertIn(part, rule)
        self.assertIn("k=10", page.locator(".std-list").nth(1).get_by_role("link", name="Als Robo-Regel verwenden").get_attribute("href") or "")
        page.locator(".std-pair").scroll_into_view_if_needed()
        self.shot(page, "25a_standardlisten")
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
        table, denominator = counts("b", WEIGHTS[1:], 31, 60)
        expect(page.locator(".scope-note")).to_contain_text("nur Gewichtungen mit Gleichmäßigkeitsanteil")
        expect(page.locator(".scope-note")).to_contain_text("Zeiträume 31–60 Tage")
        expect(page.locator(".scope-note")).to_contain_text(f"(Nenner): {denominator:,} von".replace(",", "."))
        for isin, n1, n3, n10 in visible_rows(page):
            self.assertEqual([n1, n3, n10], table[isin], isin)
        # ein Gewicht, freie Spanne
        page.get_by_label("Gewichtungen").select_option("50")
        self.wait_until(page, "location.hash.includes('gw=50')")
        page.get_by_role("radio", name="Frei").click()
        page.get_by_label("von (Tage)").fill("21")
        page.get_by_label("bis (Tage)").fill("45")
        page.get_by_role("button", name="Spanne übernehmen").click()
        self.wait_until(page, "location.hash.includes('von=21') && location.hash.includes('bis=45')")
        expect(page.locator(".scope-note")).not_to_contain_text("Teilmenge")
        self.assertLessEqual(page.locator("table.gfreq").evaluate(overflow), 0, "ohne seitliches Blättern")
        expect(page.locator("table.gfreq-both")).to_have_count(0)
        table_50, _ = counts("b", [50], 21, 45)
        for isin, n1, n3, n10 in visible_rows(page):
            self.assertEqual([n1, n3, n10], table_50[isin], isin)
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
        csv_text = _plain(Path(info.value.path()).read_text(encoding="utf-8-sig"))
        for needle in ("# Aktien;Aktien mit Ø Tagesumsatz ab 10 Mio. USD", "# Gewichtungen;nur 50/50", "# Zeiträume;21–45 Kalendertage", "# Zählweise;identische Kursfenster einmal", self.snapshot_id):
            self.assertIn(needle, csv_text)
        self.assertIn("Rang;Unternehmen;ISIN;Platz 1;Top 3;Top 10;Zugelassene Kombinationen\n", csv_text)
        self.assertNotIn("Gruppe", csv_text)
        with page.expect_download() as info:
            page.locator(".gfreq-section").get_by_role("button", name="JSON").click()
        data = json.loads(Path(info.value.path()).read_text(encoding="utf-8"))
        self.assertEqual(data["format"], "tr-haeufigkeit/2")
        self.assertEqual(data["meta"]["Snapshot"], self.snapshot_id)
        self.assertTrue(all(set(e) == {"rang", "name", "isin", "platz1", "top3", "top10", "zugelassen"} for e in data["eintraege"]))
        self.assertTrue({e["isin"] for e in data["eintraege"]} <= set(isins))
        self.shot(page, "25_haeufigste_aktien")

    def test_matrix_jump_and_export(self) -> None:
        """Matrix 1–90 × 11: Sprung per Schnellwahl, Export als CSV und JSON mit allen 990 Zellen (ab 1.23 nur Aktien mit
        Mindestumsatz)."""
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
            ref = overview["v0l"][h - 1] if w == 0 else overview["ul"][str(w)][h - 1]
            if "idx" in ref:
                self.assertEqual(cell["isin"], self.snap("instruments.bin")["isin"][ref["idx"]])
            else:
                self.assertIsNone(cell["isin"])
                self.assertTrue(cell["nicht_berechenbar"])
        with page.expect_download() as info:
            page.get_by_role("button", name="Matrix als CSV").click()
        csv_text = Path(info.value.path()).read_text(encoding="utf-8-sig")
        self.assertIn("Tage;Gewichtung;Unternehmen;ISIN;Kursrendite %;Rangscore;R²", csv_text)
        self.assertIn("# Aktien;nur Aktien mit Ø Tagesumsatz ab 10 Mio. USD", csv_text)
        self.assertNotIn("Gruppe", csv_text)
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
        # ab 1.15: Auswahl und erste fünf Plätze in einem Abschnitt, Abdeckung unter „Mehr auf einen Blick“
        selection = page.locator("section.start-ranking")
        expect(selection.get_by_role("group", name="Zeitraum wählen (Kalendertage)").get_by_role("button", name="90 Tage", exact=True)).to_have_attribute("aria-pressed", "true")
        expect(selection.get_by_role("radio", name="60/40")).to_have_attribute("aria-checked", "true")
        page.get_by_role("button", name=re.compile("^Mehr auf einen Blick")).click()
        expect(page.locator(".coverage-counts")).to_contain_text("Berechnet")
        expect(page.locator(".coverage-counts")).to_contain_text("identifiziert")
        expect(page.locator(".coverage-counts")).to_contain_text("Einträgen der TR-Liste")
        selection.get_by_role("radio", name="50/50").click()
        expect(selection.get_by_role("radio", name=re.compile(r"Ø Umsatz ≥|^(A|B)[ :·]"))).to_have_count(0)
        selection.get_by_role("group", name="Zeitraum wählen (Kalendertage)").get_by_role("button", name="30 Tage", exact=True).click()
        heading = page.locator("#eigene")
        expect(heading).to_contain_text("30 Kalendertage")
        expect(selection).to_contain_text("Nur Aktien mit Ø Tagesumsatz ab 10 Mio. USD")
        page.reload()
        page.wait_for_load_state("networkidle")
        expect(page.locator("#eigene")).to_contain_text("30 Kalendertage")
        expect(page.locator("#eigene")).to_contain_text("50/50")
        expect(page.locator("#eigene")).not_to_contain_text("Gruppe")
        win = self.snap("windows/30.full.bin")
        expect(page.locator("ol.rows[aria-label^='Erste fünf Plätze'] > li").first.locator(".isin-code")).to_have_text(isins[self.order(win, "b", 50)[0]])
        entries = page.get_by_role("navigation", name="Direkte Einstiege")
        for name in ("Höchste Rendite", "Gleichmäßigkeit + Rendite", "Häufigste Aktien", "Kursvergleich"):
            expect(entries.get_by_role("link", name=re.compile(re.escape(name)))).to_be_visible()
        entries.get_by_role("link", name=re.compile("Gleichmäßigkeit \\+ Rendite")).click()
        self.wait_until(page, "location.hash.startsWith('#/ranking') && /[?&]h=30(&|$)/.test(location.hash) && /[?&]w=50(&|$)/.test(location.hash)")
        page.go_back()
        page.locator("section.start-ranking").get_by_role("radio", name="0/100").click()
        expect(page.locator("#eigene")).to_contain_text("0/100")

    def test_status_shows_method_change_and_exports_metadata(self) -> None:
        page = self.page()
        self.go(page, "/status")
        expect(page.get_by_role("heading", name=re.compile("Methodenwechsel tr-methode-1.9.0 → tr-methode-1.10.0"))).to_be_visible()
        cmp = self.snap("manifest.bin")["method_comparison"]
        note = page.locator("section", has=page.get_by_role("heading", name=re.compile("Methodenwechsel"))).locator(".section-note")
        expect(note).to_contain_text(f"{cmp['paare']['neu_bewertet']:,}".replace(",", ".") + " Aktie-Zeitraum-Paare werden neu bewertet")
        expect(note).to_contain_text(f"{cmp['paare']['nicht_mehr_bewertet']:,}".replace(",", ".") + " nicht mehr")
        expect(page.locator(".kv-row", has_text="Ausgangsmodell")).to_contain_text("TR-90D-11W-two-universes-v1.1")
        expect(page.locator(".kv-row", has_text="Ausgangsmodell")).to_contain_text("Prüffall 12.10.2026 offen – dessen Archiv fehlt")
        with page.expect_download() as info:
            page.get_by_role("button", name="Als JSON").click()
        data = json.loads(Path(info.value.path()).read_text(encoding="utf-8"))
        self.assertEqual(data["format"], "tr-metadaten/1")
        manifest = data["manifest"]
        self.assertEqual(manifest["snapshot_id"], self.snapshot_id)
        self.assertEqual(manifest["versions"]["method"], "tr-methode-1.10.0")
        self.assertIn("method_comparison", manifest)
        text = json.dumps(data).lower()
        for secret in ("passphrase", "api_key", "apikey", "token", PASSPHRASE.lower()):
            self.assertNotIn(secret, text, "keine Geheimnisse im Export")
        expect(page.get_by_text("Methode tr-methode-1.10.0", exact=False).first).to_be_visible()
        page.get_by_role("link", name="Regeln und Beispiele").click()
        self.wait_until(page, "location.hash === '#/methodik'")
        expect(page.get_by_role("heading", name="Methodenwechsel und Ausgangsmodell")).to_be_visible()
        # Regeln des Vergleichs 1.9.0 → 1.10.0 (aus dem Manifest) und die unveränderte Lückenregel
        expect(page.get_by_text("Gleichstand exakt (ranking-11w-v3", exact=False)).to_be_visible()
        expect(page.get_by_text("Unverändert: Ein fehlender Börsentag zählt als fehlend", exact=False)).to_be_visible()
        expect(page.get_by_text("höchstens 20 % fehlende Börsentage (einer immer erlaubt)", exact=False).first).to_be_visible()
        expect(page.get_by_text("Seit Methode 1.9.0 wird jede Aktie bewertet", exact=False)).to_be_visible()
        expect(page.get_by_text("Seit Methode 1.10.0 wird der Rangscore exakt verglichen", exact=False)).to_be_visible()
        # Wirkung auf Platz 1 und die ersten 10 (Zahlen aus dem Manifest)
        for label, key in (("Andere Aktien unter den ersten 10", "top10_andere_aktien"), ("Dieselben ersten 10, andere Reihenfolge", "top10_andere_reihenfolge")):
            expect(page.locator(".kv-row", has_text=label)).to_contain_text(f"{cmp['ranglisten'][key]:,}".replace(",", ".") + " Ranglisten")
        # Gleichstand in der Methodik: exakter Vergleich, keine Rundung
        expect(page.get_by_text("Der Rangscore wird exakt verglichen, ohne Rundung", exact=False)).to_be_visible()

    def test_price_reconciliation_view_lists_each_correction_and_the_rule(self) -> None:
        """Ab 1.20.0 (Auftrag 25.10.2026, 19:31 Uhr, Punkt 6: „Liefere die aktualisierte App mit einer kurzen Gegenüberstellung:
        tatsächlich korrigierte Kurse, geänderte Spitzenplätze und verbleibende ungeklärte Fälle“): ☰ → Kursabgleich zeigt die
        Regel, jede Korrektur des Stands mit bisherigem Kurs, Kurs der Börse, Datum und Grund, die geänderten Plätze 1 und die
        Aktien ohne Abgleich. Im DEMO zwei Korrekturen an Tagen vor allen Zeiträumen – kein Platz 1 ändert sich."""
        page = self.page()
        summary = self.snap("manifest.bin")["kursabgleich"]
        payload = self.snap("kursabgleich.bin")
        self.go(page, "/status")
        section = page.locator("section", has=page.get_by_role("heading", name="Kursabgleich mit den Börsen"))
        expect(section.locator(".kv-row", has_text="Aktien mit Kurs der Börse statt Hauptquelle")).to_contain_text(str(summary["aktien_mit_kurskorrektur"]))
        section.get_by_role("link", name=re.compile("Jede Korrektur")).click()
        self.wait_until(page, "location.hash === '#/kursabgleich'")
        expect(page.locator(".kv-row", has_text="Regel").first).to_contain_text(summary["regel"])
        table = page.locator("section", has=page.get_by_role("heading", name="Korrigierte Kurse")).locator("table tbody tr")
        expect(table).to_have_count(2)
        expect(table.filter(has_text="Tag ohne Umsatz an der Börse")).to_have_count(1)
        expect(table.filter(has_text="anderer Schlusskurs als die Börse")).to_have_count(1)
        corrected = next(c for case in payload["faelle"] for c in case["korrekturen"] if c["grund"] == "amtlicher_schlusskurs")
        row = table.filter(has_text="anderer Schlusskurs als die Börse")
        expect(row).to_contain_text(f"{corrected['neu']:.2f}".replace(".", ","))
        expect(page.get_by_text("Kein Platz 1 hat sich durch den Abgleich geändert.")).to_be_visible()
        gaps = page.locator("section", has=page.get_by_role("heading", name="Ohne Abgleich mit der Börse")).locator("table tbody tr")
        expect(gaps.first).to_be_visible()
        self.assertGreater(payload["luecken_gesamt"], 0)
        self.assertFalse(page.evaluate("document.documentElement.scrollWidth > window.innerWidth + 1"), "kein seitliches Blättern")

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
        # ab tr-methode-1.9.0 zählen die Aktien der übrigen Börsen mit ihrem letzten Schlusskurs
        expect(note).to_contain_text("Schlusskurse vom Stichtag nur von 3 der 31 Börsen mit Handel am Stichtag: Australien, Neuseeland und USA.")
        expect(note).to_contain_text("Für die übrigen 28 lieferte der Kursanbieter keine vollständigen Schlusskurse.")
        expect(note).to_contain_text("Deren Aktien zählen mit ihrem letzten Schlusskurs")
        expect(note).not_to_contain_text("Amsterdam")
        self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"), page.evaluate("document.documentElement.clientWidth"), "Hinweis ohne Seitwärtsverschiebung")
        self.shot(page, "01c_teilstand_drei_boersen")
        self.go(page, "/status")
        row = page.locator(".kv-row", has_text="Vollständigkeit")
        expect(row).to_contain_text("3 von 31 Börsen mit Stichtagskursen")
        expect(row).to_contain_text("Amsterdam, Athen, Bangkok")
        self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"), page.evaluate("document.documentElement.clientWidth"), "Liste bricht um")

    def test_encrypted_site_requires_key(self) -> None:
        page = self.page(base=self.base_enc)
        self.go(page, "/", base=self.base_enc)
        expect(page.get_by_role("heading", name="App entsperren")).to_be_visible()
        page.locator("#passphrase").fill("falsch")
        page.get_by_role("button", name="Entsperren").click()
        expect(page.get_by_text("Diese Passphrase passt nicht", exact=False)).to_be_visible(timeout=30000)
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
        expect(rows).to_have_count(3)  # ab 1.15 drei (Startseite übersichtlicher), alle unter „Alle Kandidaten“
        expect(rows.first.locator(".light")).to_have_count(2)
        expect(rows.first.locator(".reasons li").first).to_be_visible()
        # Gesamtwertung (1.7): Zahl je Zeile, absteigend; Steig-Konstanz 30/60/90 Tage als Streifen
        expect(section.get_by_role("radio", name="Gesamt")).to_have_attribute("aria-checked", "true")
        expect(rows.first.locator(".total strong")).to_have_text(re.compile(r"^\d+$"))
        totals = [int(t) for t in rows.locator(".total strong").all_inner_texts()]
        self.assertEqual(totals, sorted(totals, reverse=True), "nach Gesamtwertung sortiert")
        self.assertGreaterEqual(rows.first.locator(".kons .kons-cell").count(), 2)
        expect(rows.first.locator(".kons .kons-cell").first).to_contain_text(re.compile(r"30 T\s*▲\d+/\d+"))
        selection = page.locator("section.start-ranking")
        self.assertLess(section.bounding_box()["y"], selection.bounding_box()["y"], "Kandidaten stehen über den Rendite-Ranglisten")
        section.get_by_role("button", name="Erklärung: Kandidaten mit Potenzial").click()
        expect(section.locator(".info-text")).to_contain_text("zwei Ampeln")
        section.get_by_role("radio", name="Kursziel").click()
        expect(rows.first.locator(".reasons li").first).to_contain_text("Kursziel")
        self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"), page.evaluate("document.documentElement.clientWidth"))
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
        self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"), page.evaluate("document.documentElement.clientWidth"))
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
        tabs.get_by_role("radio", name="Rendite", exact=True).click()
        expect(page.get_by_role("heading", name="Stammdaten und Herkunft")).to_be_visible()

    def test_potential_list_switches_lists_filters_and_stays_on_screen(self) -> None:
        page = self.page()
        self.go(page, "/potenzial")
        expect(page.locator("h2.view-title")).to_have_text("Kandidaten mit Potenzial")
        rows = page.locator("ol.sig-rows > li")
        expect(rows.first).to_be_visible()
        self.assertLessEqual(rows.count(), 25)
        page.get_by_role("radio", name="Lang", exact=True).click()  # ab 1.11 kurze Namen, damit fünf Listen passen
        self.wait_until(page, "location.hash.includes('liste=lang')")
        page.get_by_role("button", name=re.compile("^Filter")).click()
        page.get_by_label("nur grün").check()
        self.wait_until(page, "location.hash.includes('gruen=1')")
        expect(page.get_by_role("button", name=re.compile(r"^Filter \(1 aktiv\)"))).to_be_visible()
        expect(rows.first).to_be_visible()
        long_lights = page.locator("ol.sig-rows > li .light", has_text="lang")
        for k in range(long_lights.count()):
            expect(long_lights.nth(k)).to_contain_text("grün")
        self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"), page.evaluate("document.documentElement.clientWidth"))
        self.shot(page, "23_potenzial")
        # Bereich „Analyse“: Werkzeuge mit Erklärung
        page.get_by_role("navigation", name="Hauptnavigation").get_by_role("link", name="Analyse").click()
        expect(page.locator(".tool-list li")).to_have_count(5)

    def test_signal_details_follow_a_newly_deployed_signal_stand(self) -> None:
        """Ab 1.18 (gefunden bei der Prüfung der ausgelieferten Version am 24.10.2026): Wird der Signal-Stand neu
        bereitgestellt, während die App offen ist, gibt es die Dateien des alten Stands nicht mehr (404). Die Einzelansicht
        lädt dann den Status neu und zeigt die Signale des neuen Stands – bis 1.17 stand dort „Datei nicht gefunden“ mit
        „Erneut versuchen“."""
        from traktien.util import crypto

        status = json.loads((self.site / "data" / "status.json").read_text(encoding="utf-8"))
        old = status["signale"]["id"]
        new = "20991231T235959Z"
        folder = self.site / "data" / "signale" / old
        sig = json.loads(crypto.unpack((folder / "signale.bin").read_bytes(), None, f"signale/{old}/signale.bin"))
        first, second = [isin for isin in sig["isin"] if (folder / "details" / f"{isin}.bin").exists()][:2]

        def renewed_file(route) -> None:
            relative = route.request.url.split(f"/signale/{new}/", 1)[1].split("?", 1)[0]
            data = json.loads(crypto.unpack((folder / relative).read_bytes(), None, f"signale/{old}/{relative}"))
            data["id"] = new  # derselbe Inhalt als neuer Signal-Stand
            route.fulfill(status=200, content_type="application/octet-stream", body=crypto.pack(json.dumps(data).encode("utf-8"), None, f"signale/{new}/{relative}"))

        page = self.page(expected_console=r"status of 404")
        self.go(page, f"/aktie/{first}")
        expect(page.get_by_role("heading", name="Gesamtwertung")).to_be_visible(timeout=30000)
        # neue Bereitstellung: der Status nennt den neuen Signal-Stand, die Dateien des alten gibt es nicht mehr
        renewed = dict(status, signale=dict(status["signale"], id=new))
        page.route("**/data/status.json*", lambda route: route.fulfill(status=200, content_type="application/json", body=json.dumps(renewed)))
        page.route(f"**/data/signale/{old}/**", lambda route: route.fulfill(status=404, body="nicht gefunden"))
        page.route(f"**/data/signale/{new}/**", renewed_file)
        # in der offenen App zur nächsten Aktie wechseln (kein Neuladen der Seite)
        page.evaluate(f"location.hash = '#/aktie/{second}'")
        self.wait_until(page, f"location.hash.startsWith('#/aktie/{second}')")
        expect(page.get_by_role("heading", name="Gesamtwertung")).to_be_visible(timeout=30000)
        expect(page.get_by_text("Datei nicht gefunden")).to_have_count(0)
        expect(page.get_by_text("Für diese Aktie gibt es keine Signale")).to_have_count(0)
        expect(page.get_by_text("Signale gerade nicht abrufbar")).to_have_count(0)
        # Bleibt der Stand derselbe und die Datei fehlt wirklich: ehrlicher Hinweis statt „keine Signale“
        page.unroute(f"**/data/signale/{new}/**")
        page.route(f"**/data/signale/{new}/details/**", lambda route: route.fulfill(status=404, body="nicht gefunden"))
        page.route(f"**/data/signale/{new}/signale.bin*", renewed_file)
        third = [isin for isin in sig["isin"] if isin not in (first, second) and (folder / "details" / f"{isin}.bin").exists()][0]
        page.evaluate(f"location.hash = '#/aktie/{third}'")
        expect(page.get_by_text("Signale gerade nicht abrufbar")).to_be_visible(timeout=30000)
        expect(page.get_by_text("Für diese Aktie gibt es keine Signale")).to_have_count(0)

    def test_signals_load_on_the_encrypted_site(self) -> None:
        page = self.page(base=self.base_enc)
        self.go(page, "/", base=self.base_enc)
        page.locator("#passphrase").fill(PASSPHRASE)
        page.get_by_role("button", name="Entsperren").click()
        expect(page.locator("section.candidates ol.sig-rows > li")).to_have_count(3, timeout=30000)  # ab 1.15 drei auf der Startseite

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
        expect(page.get_by_text("Diese Passphrase passt nicht", exact=False)).to_be_visible(timeout=30000)
        page.locator("#passphrase").fill(PASSPHRASE)
        page.get_by_role("button", name="Prüfen und speichern").click()
        expect(page.get_by_text("Passphrase gespeichert")).to_be_visible(timeout=30000)
        expect(page.get_by_text("Noch kein Datenstand veröffentlicht")).to_be_visible()
        self.assertEqual(page.locator("#passphrase").count(), 0)
        # Der erste Datenstand ist da: geöffnet ohne erneute Eingabe
        page.unroute("**/data/status.json*")
        page.unroute("**/data/snapshots/index.json*")
        page.reload()
        expect(page.locator(".stamp-date")).to_contain_text("Kursstand", timeout=30000)


    # ------------------------------------------------- Verständlichkeit, Fehlerfälle, Installation (1.16)

    def test_lock_screen_explains_purpose_steps_and_input_errors(self) -> None:
        """Sperrbildschirm: Zweck und Schritte, leere und falsche Eingabe mit nächstem Schritt, Leerzeichen am Ende
        (Handy-Tastatur) entsperrt trotzdem; gesperrt nur Hilfe und Installieren im Menü, keine Leiste unten."""
        page = self.page(base=self.base_enc)
        self.go(page, "/", base=self.base_enc)
        expect(page.get_by_role("heading", name="App entsperren")).to_be_visible()
        expect(page.locator(".view-head .lede")).to_contain_text("1 bis 90 Tagen")
        expect(page.locator(".lock-steps li")).to_have_count(3)
        expect(page.locator(".bottomnav")).to_be_hidden()
        page.get_by_role("button", name="Weitere Ansichten").click()
        self.assertEqual(page.locator(".sheet a").all_inner_texts(), ["Hilfe und Begriffe", "Auf dem Startbildschirm installieren"])
        page.keyboard.press("Escape")
        # leer
        page.get_by_role("button", name="Entsperren").click()
        expect(page.locator("#passphrase-fehler")).to_contain_text("Gib zuerst die Passphrase ein")
        expect(page.locator("#passphrase")).to_be_focused()
        # falsch: Meldung am Feld, Eingabe bleibt zum Korrigieren
        page.locator("#passphrase").fill("falsch")
        page.locator("#passphrase").press("Enter")
        expect(page.locator("#passphrase-fehler")).to_contain_text("Diese Passphrase passt nicht", timeout=30000)
        expect(page.locator("#passphrase")).to_have_value("falsch")
        expect(page.get_by_text("Passphrase vergessen?")).to_be_visible()
        # Hilfe ist auch gesperrt erreichbar
        page.get_by_role("link", name="Hilfe", exact=True).click()
        expect(page.locator("h2.view-title", has_text="Hilfe und Begriffe")).to_be_visible()
        page.go_back()
        # richtig, mit Leerzeichen am Ende
        page.locator("#passphrase").fill(PASSPHRASE + " ")
        page.get_by_role("button", name="Entsperren").click()
        expect(page.locator(".stamp-date")).to_contain_text("Kursstand", timeout=30000)
        expect(page.locator(".bottomnav")).to_be_visible()

    def test_intro_card_once_and_help_with_glossary_examples_and_deep_links(self) -> None:
        """Erster Start: Kurzerklärung oben, „Verstanden“ blendet sie dauerhaft aus. Hilfe: Themen springen,
        Rechenbeispiel stimmt, Begriffe filterbar, Link auf einen Begriff hebt ihn hervor; Begriffe in der Rangliste
        erklären sich beim Antippen."""
        page = self.page()
        self.go(page, "/")
        intro = page.locator("section.intro-card")
        expect(intro).to_contain_text("Neu hier?")
        self.assertLess(intro.bounding_box()["y"], page.locator("section.signal-hero").bounding_box()["y"], "Kurzerklärung steht über „Kaufsignal heute“")
        intro.get_by_role("button", name="Verstanden").click()
        expect(intro).to_have_count(0)
        page.reload()
        page.wait_for_load_state("networkidle")
        expect(page.locator("section.signal-hero")).to_be_visible()
        expect(page.locator("section.intro-card")).to_have_count(0)
        # Hilfe über das Menü
        page.get_by_role("button", name="Weitere Ansichten").click()
        page.locator(".sheet a", has_text="Hilfe und Begriffe").click()
        expect(page.locator("h2.view-title", has_text="Hilfe und Begriffe")).to_be_visible()
        # Rechenbeispiel: Perzentile 0/50/100 und Rangscore 60/40
        rows = page.locator("table.help-table tbody tr")
        expect(rows).to_have_count(3)
        expect(rows.nth(0)).to_contain_text("= 80")
        expect(rows.nth(1)).to_contain_text("= 40")
        expect(rows.nth(2)).to_contain_text("= 30")
        # Thema anspringen
        page.locator(".help-toc button", has_text="Häufige Fragen").click()
        self.wait_until(page, "Math.abs(document.getElementById('hilfe-fragen').getBoundingClientRect().top) < 200")
        # Begriffe filtern
        field = page.get_by_label("Begriff suchen")
        field.fill("R²")
        expect(page.locator(".glossary-entry").first).to_contain_text("Gleichmäßigkeit (R²)")
        field.fill("xyzzy")
        expect(page.locator(".glossary-entry")).to_have_count(0)
        expect(page.get_by_text("Kein Begriff passt zu „xyzzy“", exact=False)).to_be_visible()
        # Link auf einen Begriff
        self.go(page, "/hilfe?begriff=rangscore")
        entry = page.locator("#begriff-rangscore")
        expect(entry).to_have_class(re.compile("is-wanted"))
        self.wait_until(page, "(() => { const r = document.getElementById('begriff-rangscore').getBoundingClientRect(); return r.top >= 0 && r.top < innerHeight; })()")
        # Begriff in der Rangliste antippen
        self.go(page, "/ranking?h=90&w=60")
        self.open_line(page, "notes")  # ab 1.22 (F09): Lesehilfe in der Hinweiszeile über der Liste
        legend = page.locator(".row-legend")
        legend.get_by_role("button", name="Erklärung: Rangscore").click()
        note = legend.locator(".info-text")
        expect(note).to_contain_text("Höher ist besser")
        expect(note.get_by_role("link", name="Alle Begriffe")).to_have_attribute("href", "#/hilfe?begriff=rangscore")

    def test_data_errors_name_the_cause_and_offer_retry(self) -> None:
        """Fehlende Datei, beschädigte Datei, Serverfehler: verständliche Meldung mit nächstem Schritt statt
        Dateipfad oder falschem „offline“."""
        cases = [
            ("**/manifest.bin", dict(status=404, body="nicht da"), "Datei nicht gefunden"),
            ("**/manifest.bin", dict(status=200, body=b"\x00kaputt" * 8, headers={"content-type": "application/octet-stream"}), "Daten nicht lesbar"),
            ("**/data/status.json*", dict(status=500, body="Fehler"), "Server antwortet nicht"),
        ]
        for pattern, response, title in cases:
            with self.subTest(title=title):
                page = self.page(expected_console=r"status of (404|500)")
                page.route(pattern, (lambda resp: lambda route: route.fulfill(**resp))(response))
                self.go(page, "/")
                notice = page.locator(".notice", has_text=title)
                expect(notice).to_be_visible(timeout=15000)
                expect(notice.get_by_role("button", name="Erneut versuchen")).to_be_visible()
                expect(page.get_by_text("Keine Internetverbindung")).to_have_count(0)
                if title == "Datei nicht gefunden":
                    expect(notice).to_contain_text("neuer Stand veröffentlicht")
                    # nach dem Beheben: „Erneut versuchen“ öffnet den Stand
                    page.unroute(pattern)
                    notice.get_by_role("button", name="Erneut versuchen").click()
                    expect(page.locator(".stamp-date")).to_contain_text("Kursstand", timeout=15000)
        # Fehlende Datei innerhalb einer Ansicht
        page = self.page(expected_console=r"status of 404")
        self.go(page, "/")
        page.route("**/windows/33.bin", lambda route: route.fulfill(status=404, body="nicht da"))
        page.evaluate("location.hash = '/ranking?h=33&w=60'")
        notice = page.locator(".notice", has_text="Datei nicht gefunden")
        expect(notice).to_be_visible(timeout=15000)
        expect(notice.get_by_role("button", name="Erneut versuchen")).to_be_visible()
        expect(notice.locator(".notice-body p").first).not_to_contain_text("windows/33.bin")
        expect(notice.locator(".error-detail")).to_contain_text("windows/33.bin")

    def test_unknown_page_and_isin_offer_next_steps(self) -> None:
        page = self.page()
        self.go(page, "/gibtsnicht")
        notice = page.locator(".notice", has_text="Seite nicht gefunden")
        expect(notice.get_by_role("link", name="Zur Startseite")).to_have_attribute("href", "#/")
        cases = [
            ("/aktie/abc", "Keine gültige ISIN", "#/aktien"),
            ("/aktie/", "Keine Aktie angegeben", "#/aktien"),
            ("/aktie/DE0007164600", "Aktie nicht in diesem Datenstand", "#/aktien?q=DE0007164600"),
            ("/haeufig/DE0007164600", "Aktie nicht in diesem Datenstand", "#/aktien?q=DE0007164600"),
        ]
        for route, title, href in cases:
            with self.subTest(route=route):
                self.go(page, route)
                notice = page.locator(".notice", has_text=title)
                expect(notice).to_be_visible()
                expect(notice.get_by_role("link", name="Aktie suchen")).to_have_attribute("href", href)

    def test_search_filters_while_typing_and_explains_no_result(self) -> None:
        page = self.page()
        self.go(page, "/aktien")
        search = page.get_by_role("searchbox", name="Name, Ticker oder ISIN")
        self.assertLess(search.bounding_box()["y"], page.locator(".stats").bounding_box()["y"], "Suche steht über dem Überblick")
        status = page.locator(".search + .toolbar [role=status]")
        total = int(re.search(r"(\d+) Treffer", status.inner_text()).group(1))
        isin = self.snap("instruments.bin")["isin"][0]
        search.press_sequentially(isin, delay=10)
        expect(status).to_have_text("1 Treffer", timeout=5000)  # ohne Enter
        search.fill("")
        search.press_sequentially("xyz123", delay=10)
        expect(status).to_contain_text("Keine Aktie passt zu „xyz123“", timeout=5000)
        page.get_by_role("button", name="Filter löschen").click()
        expect(status).to_have_text(f"{total} Treffer")

    def test_screen_keyboard_hides_bottom_bar_only_while_the_page_shrinks(self) -> None:
        """Bildschirmtastatur (1.17): Verkleinert der Browser beim Tippen die Seite, verschwindet die Leiste unten und das
        Layout bleibt im Hochformat (keine Leiste links, obwohl die Seite dann breiter als hoch ist). Legt sich die
        Tastatur über die Seite (gleiche Höhe), bleibt alles, wie es ist. Nach dem Schließen kommt die Leiste zurück."""
        page = self.page()
        self.go(page, "/aktien")
        nav = page.locator(".bottomnav")
        expect(nav).to_be_visible()
        search = page.get_by_role("searchbox", name="Name, Ticker oder ISIN")
        search.click()
        page.wait_for_timeout(600)
        expect(nav).to_be_visible()  # Tastatur über der Seite: nichts ändert sich
        self.assertIsNone(page.evaluate("document.documentElement.dataset.tastatur ?? null"))
        size = dict(page.viewport_size)
        page.set_viewport_size({"width": size["width"], "height": int(size["height"] * 0.4)})
        expect(nav).to_be_hidden()
        self.assertEqual(page.evaluate("getComputedStyle(document.querySelector('.shell')).paddingLeft"), "0px", "kein Querformat-Layout")
        expect(search).to_be_focused()
        search.press_sequentially("sap", delay=10)
        page.evaluate("document.activeElement.blur()")  # Fokus weg, Tastatur zu
        page.set_viewport_size(size)
        expect(nav).to_be_visible()
        self.assertIsNone(page.evaluate("document.documentElement.dataset.tastatur ?? null"))

    def test_depot_capital_input_validates_and_keeps_last_valid_amount(self) -> None:
        page = self.page()
        self.go(page, "/depots")
        field = page.get_by_label("Rechnerisches Startkapital", exact=False)
        expect(page.locator(".dp-kpis")).to_contain_text("1.000,00", timeout=20000)
        field.fill("abc")
        expect(page.locator(".dp-capital .field-error")).to_contain_text("Bitte nur eine Zahl")
        field.fill("")
        expect(page.locator(".dp-capital .field-error")).to_contain_text("Bitte einen Betrag eingeben")
        field.fill("0")
        expect(page.locator(".dp-capital .field-error")).to_contain_text("Erlaubt sind 1 bis 100.000.000")
        field.fill("2.500")
        expect(page.locator(".dp-capital .field-hint")).to_contain_text("Gerechnet wird mit 2.500")
        expect(page.locator(".dp-kpis")).to_contain_text("2.500,00")
        field.fill("-5")
        field.press("Tab")
        expect(field).to_have_value("2500")  # ungültig verlassen: letzter gültiger Betrag bleibt

    def test_settings_feedback_next_to_action_and_forget_key_asks_first(self) -> None:
        page = self.page(base=self.base_enc)
        self.go(page, "/", base=self.base_enc)
        page.locator("#passphrase").fill(PASSPHRASE)
        page.get_by_role("button", name="Entsperren").click()
        expect(page.locator(".stamp-date")).to_contain_text("Kursstand", timeout=30000)
        self.go(page, "/einstellungen", base=self.base_enc)
        wrong = self.tmp / "keine-sicherung.json"
        wrong.write_text("das ist kein json", encoding="utf-8")
        page.locator("section[aria-labelledby=sichern] input[type=file]").set_input_files(str(wrong))
        message = page.locator("section[aria-labelledby=sichern] .notice")
        expect(message).to_contain_text("keine Sicherung dieser App")
        expect(message).not_to_contain_text("JSON")
        page.get_by_role("button", name="Schlüssel auf diesem Gerät vergessen").click()
        confirm = page.locator(".notice", has_text="Schlüssel wirklich vergessen?")
        expect(confirm).to_be_visible()
        confirm.get_by_role("button", name="Abbrechen").click()
        expect(page.locator("#passphrase")).to_have_count(0)
        page.get_by_role("button", name="Schlüssel auf diesem Gerät vergessen").click()
        page.get_by_role("button", name="Ja, vergessen").click()
        expect(page.locator("#passphrase")).to_be_visible()

    def test_free_period_outside_1_to_90_says_what_happened(self) -> None:
        page = self.page()
        self.go(page, "/ranking?h=30&w=60")
        self.open_line(page, "settings")  # ab 1.22 (F09): freier Zeitraum unter „Einstellungen“
        field = page.locator(".stepper-input").first
        field.fill("0")
        expect(page.locator(".free-hint")).to_contain_text("Nur ganze Tage von 1 bis 90")
        field.press("Tab")
        expect(page.locator(".free-hint")).to_contain_text("gewählt ist jetzt 1 Tag")
        self.wait_until(page, "location.hash.includes('h=1&') || location.hash.endsWith('h=1')")
        field.fill("120")
        field.press("Tab")
        expect(page.locator(".free-hint")).to_contain_text("sind jetzt 90 Tage")

    def test_pwa_is_installable_and_starts_after_installation(self) -> None:
        """Installation wie in Chrome geprüft (nicht nur „Manifest vorhanden“): Chrome meldet keine Hindernisse
        (Page.getInstallabilityErrors, dauerhaftes Profil statt Inkognito), installiert die App (PWA.install) und
        startet sie (PWA.launch); die gestartete App zeigt die Startseite."""
        profile = tempfile.mkdtemp(prefix="pwa-profil-", dir=self.tmp)
        try:
            # Vollständiges Chromium (neuer Headless-Modus) statt der schlanken Headless-Shell: nur dieses kann Web-Apps installieren
            path = _chromium_path()
            context = self.pw.chromium.launch_persistent_context(
                profile, **({"executable_path": path} if path else {"channel": "chromium"}), viewport=S25["viewport"], locale="de-DE", service_workers="allow"
            )
        except PlaywrightError as exc:  # pragma: no cover
            self.skipTest(f"dauerhaftes Profil nicht startbar: {exc}")
        self.addCleanup(context.close)
        page = context.pages[0] if context.pages else context.new_page()
        page.goto(self.base)
        page.wait_for_load_state("networkidle")
        self.assertTrue(page.evaluate("() => navigator.serviceWorker.ready.then(r => !!r.active)"))
        cdp = context.new_cdp_session(page)
        manifest = cdp.send("Page.getAppManifest")
        self.assertEqual(manifest.get("errors"), [])
        data = json.loads(manifest["data"])
        self.assertEqual((data["short_name"], data["display"]), ("TR-Vergleich", "standalone"))
        self.assertTrue({"192x192", "512x512"} <= {icon["sizes"] for icon in data["icons"]})
        self.assertEqual(cdp.send("Page.getInstallabilityErrors")["installabilityErrors"], [])
        app_id = cdp.send("Page.getAppId")["appId"]
        browser_cdp = context.browser.new_browser_cdp_session() if context.browser else cdp
        try:
            browser_cdp.send("PWA.install", {"manifestId": app_id, "installUrlOrBundleUrl": self.base})
        except PlaywrightError as exc:  # pragma: no cover - ältere Chromium-Versionen
            self.skipTest(f"PWA.install nicht verfügbar: {exc}")
        with context.expect_page(timeout=15000) as info:
            browser_cdp.send("PWA.launch", {"manifestId": app_id})
        app = info.value
        app.wait_for_load_state("networkidle")
        expect(app.locator(".stamp-date")).to_contain_text("Kursstand", timeout=15000)
        self.assertEqual(app.title(), "TR-Aktienvergleich")


if __name__ == "__main__":
    unittest.main()
