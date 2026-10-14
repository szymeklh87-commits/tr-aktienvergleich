"""Browser-Tests: Zwischenstand (ab 1.8) in der App – simuliertes Galaxy S25+ (Chromium, 384 × 832).

DEMO-Stand mit Zwischenstand: „jetzt“ = 13.10.2026, 12:30 Uhr Berlin; Kurse bis 12:15 Uhr (15 Minuten
verzögert); New York hat noch nicht geöffnet. Kein Test auf einem echten Gerät.
"""

from __future__ import annotations

import json
import re
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.e2e.test_mobile_app import APP_DIST, HAVE_PLAYWRIGHT, REPO, S25, _chromium_path, _serve

if HAVE_PLAYWRIGHT:
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import expect, sync_playwright


def _site_with_intraday(target: Path) -> Path:
    state, site = target / "state", target / "site"
    command = [sys.executable, "-m", "traktien", "demo", "--fresh", "--zwischenstand", "--state-dir", str(state), "--site", str(site), "--app-dist", str(APP_DIST)]
    env = dict(os.environ, PYTHONPATH=str(REPO / "backend"), LOG_LEVEL="WARNING", GITHUB_REPOSITORY="beispiel/tr-aktienvergleich", GITHUB_SERVER_URL="https://github.com")
    subprocess.run(command, check=True, cwd=REPO, env=env, capture_output=True, text=True, timeout=600)
    return site


@unittest.skipUnless(HAVE_PLAYWRIGHT and (APP_DIST / "index.html").exists(), "Playwright oder App-Build (app/dist) fehlt")
class IntradayAppTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = Path(tempfile.mkdtemp(prefix="e2e-zwischenstand-"))
        cls.site = _site_with_intraday(cls.tmp)
        cls.server, cls.base = _serve(cls.site)
        cls.status = json.loads((cls.site / "data" / "status.json").read_text(encoding="utf-8"))
        cls.pw = sync_playwright().start()
        try:
            cls.browser = cls.pw.chromium.launch(executable_path=_chromium_path())
        except PlaywrightError as exc:  # pragma: no cover
            cls.pw.stop()
            raise unittest.SkipTest(f"Chromium nicht startbar: {exc}") from exc

    @classmethod
    def tearDownClass(cls) -> None:
        cls.browser.close()
        cls.pw.stop()
        cls.server.shutdown()
        cls.server.server_close()
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def page(self):
        context = self.browser.new_context(**dict(S25, locale="de-DE", timezone_id="Europe/Berlin", service_workers="block"))
        page = context.new_page()
        page.set_default_timeout(15000)
        errors: list[str] = []
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(str(e)))
        self.addCleanup(context.close)
        self.addCleanup(lambda: self.assertEqual(errors, [], "Konsolenfehler"))
        return page

    def go(self, page, route: str) -> None:
        page.goto(f"{self.base}#{route}")
        page.wait_for_load_state("networkidle")

    def test_intraday_is_shown_first_labelled_and_switchable(self) -> None:
        page = self.page()
        self.go(page, "/")
        expect(page.locator(".stamp-date")).to_contain_text("Zwischenstand Dienstag, 13. Oktober 2026, 12:15 Uhr")
        chip = page.locator(".stand-chip")
        expect(chip).to_contain_text("Zwischenstand")
        expect(chip).to_contain_text("13.10. 12:15")
        self.assertIn("vorläufig", chip.get_attribute("aria-label"))
        # Ab 1.11 oben eine schmale Zeile (die Top 3 stehen ganz oben); die Einzelheiten im Kopf der Startseite
        banner = page.locator(".notice", has_text="Zwischenstand – vorläufig")
        expect(banner).to_contain_text("vorläufige Kurse vom 13.10. bis 12:15 Uhr")
        stamp = page.locator("header.stamp")
        expect(stamp).to_contain_text("USA")
        # Top 3 nach Zahlen: Aktien ohne Kurs von heute zählen ab 1.13 mit dem letzten Schlusskurs – die Karte sagt es
        expect(page.locator("section.top3 .top-missing")).to_contain_text("USA")
        expect(page.locator("section.top3 .top-missing")).to_contain_text("Sie zählen mit dem Schlusskurs vom 12.10.")
        expect(stamp).to_contain_text("noch nicht geöffnet")
        expect(stamp).to_contain_text("Schlusskurse aller Börsen: Stand vom 12.10.2026")
        # Ab 1.12.1 nennen die Knöpfe, was sie zeigen – nirgends mehr „Offiziell“
        self.assertEqual(page.get_by_role("button", name=re.compile("[Oo]ffiziell")).count(), 0)
        self.assertNotIn("Offiziell", page.locator(".view").inner_text())
        self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"), page.evaluate("window.innerWidth"))
        # Zum Stand mit Schlusskursen und zurück
        switch = banner.get_by_role("button", name="Stand mit den Schlusskursen vom 12.10.2026 anzeigen")
        expect(switch).to_have_text("Schlusskurse 12.10.")
        switch.click()
        expect(page.locator(".stamp-date")).to_contain_text("Kursstand Montag, 12. Oktober 2026")
        expect(page.locator(".stand-chip")).not_to_contain_text("älterer Stand")
        back = page.locator(".notice", has_text="Zwischenstand vom 13.10. verfügbar")
        expect(back).to_be_visible()
        back.get_by_role("button", name="Zwischenstand anzeigen").click()
        expect(page.locator(".stamp-date")).to_contain_text("Zwischenstand")

    def test_detail_status_and_rule_explain_the_provisional_price(self) -> None:
        page = self.page()
        self.go(page, "/status")
        expect(page.get_by_text("Zwischenstand – vorläufig: je Aktie der zuletzt gemeldete Kurs")).to_be_visible()
        expect(page.locator(".kv", has_text="Börsen noch ohne Kurs")).to_contain_text("USA")
        # Eine Xetra-Aktie mit Kurs von heute
        isin = next(iter(self._xetra_with_today()))
        self.go(page, f"/aktie/{isin}?tab=rendite")
        expect(page.locator(".head-facts")).to_contain_text("(vorläufig)")
        expect(page.locator(".head-facts")).to_contain_text("heute 12:15 Uhr")
        expect(page.get_by_text("Letzter Punkt: vorläufiger Kurs vom", exact=False).first).to_be_visible()
        # Umschichtungs-Regel steht nur im Stand mit Schlusskursen
        self.go(page, "/regel")
        expect(page.get_by_text("Im Zwischenstand nicht gerechnet")).to_be_visible()
        page.get_by_role("button", name="Schlusskurse 12.10. anzeigen").first.click()
        expect(page.locator(".stand-chip")).to_contain_text("12.10.2026")

    def test_update_page_explains_how_to_start_an_intraday_run(self) -> None:
        page = self.page()
        self.go(page, "/aktualisieren")
        expect(page.locator(".update-view .view-head")).to_contain_text("Zwischenstand")
        expect(page.locator(".steps")).to_contain_text("„Alles aktualisieren“ ist voreingestellt")
        page.get_by_role("button", name=re.compile("Weitere Möglichkeiten")).click()
        expect(page.locator(".update-view")).to_contain_text("New York vor 15:30 Uhr")

    def test_own_stocks_without_price_today_use_the_same_rows(self) -> None:
        """Ab 1.12.1 (Simons Bildschirmfoto 15:05 Uhr): „Deine Aktien“ steht in denselben Zeilen wie die Rangfolge –
        der Name bekommt die volle Breite. Ab 1.13 (Simons Wahl 15:20 Uhr) zählen eigene US-Aktien vor Börsenbeginn
        mit dem Schlusskurs vom 12.10.: Kennzeichen „Schlusskurs 12.10.“ in jeder Liste, US-Aktien auch in der
        Rangfolge „Top nach Zahlen“ und in den Ranglisten."""
        us = self._us_without_today()[:2]
        xetra = self._xetra_with_today()[:1]
        self.assertTrue(us and xetra)
        page = self.page()
        watch = json.dumps(us + xetra)
        page.add_init_script(f"window.localStorage.setItem('tr-vergleich:watchlist:v1', JSON.stringify({watch}))")
        self.go(page, "/")
        own = page.locator("section.top3 ol.top-own > li")
        expect(own).to_have_count(3)
        for k in range(3):
            row = own.nth(k)
            self.assertIn("row", (row.get_attribute("class") or "").split(), "gleiche Zeilen wie die Rangfolge")
            name = row.locator(".row-name").bounding_box()
            self.assertGreater(name["width"], 150, "Name nicht zusammengedrückt")
        marked = page.locator("section.top3 ol.top-own > li", has=page.locator(".row-close"))
        expect(marked).to_have_count(2)
        expect(marked.first.locator(".row-close")).to_have_text("Schlusskurs 12.10.")
        self.assertEqual(page.locator("section.top3 ol.top-own").get_by_text("zählt ab Börsenbeginn").count(), 0, "keine Aktie fehlt mehr wegen fehlendem Kurs")
        expect(page.locator("section.top3 .top-missing")).to_contain_text("Sie zählen mit dem Schlusskurs vom 12.10.")
        self.assertEqual(page.locator("section.top3 .top-missing button").count(), 0, "kein Umweg über den Stand mit Schlusskursen nötig")
        self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"), 384)
        # US-Aktien auch in der Rangfolge und in den Ranglisten – mit Kennzeichen
        self.go(page, "/top")
        expect(page.locator("ol.top-own > li")).to_have_count(3)
        expect(page.locator("ol.top-rows > li .row-close").first).to_be_visible()
        self.go(page, "/ranking?h=30&w=60&p=native")
        expect(page.locator("li.row .row-close").first).to_be_visible()
        self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"), 384)

    def _us_without_today(self) -> list[str]:
        from traktien.util import crypto

        sid = self.status["zwischenstand"]["snapshot_id"]
        path = self.site / "data" / "snapshots" / sid / "instruments.bin"
        inst = json.loads(crypto.unpack(path.read_bytes(), None, f"snapshots/{sid}/instruments.bin"))
        cutoff = max(d for d in inst["last_close_day"] if d is not None)
        return [
            inst["isin"][i]
            for i, cal in enumerate(inst.get("calendar") or inst["mic"])
            if cal == "XNYS" and (inst["last_close_day"][i] is None or inst["last_close_day"][i] < cutoff) and inst["has_series"][i]
        ]

    def _xetra_with_today(self) -> list[str]:
        from traktien.util import crypto

        sid = self.status["zwischenstand"]["snapshot_id"]
        path = self.site / "data" / "snapshots" / sid / "instruments.bin"
        inst = json.loads(crypto.unpack(path.read_bytes(), None, f"snapshots/{sid}/instruments.bin"))
        cutoff = max(d for d in inst["last_close_day"] if d is not None)
        return [inst["isin"][i] for i, key in enumerate(inst["exchange_key"]) if key == "XETR" and inst["last_close_day"][i] == cutoff and inst["has_series"][i]]


if __name__ == "__main__":
    unittest.main()
