"""„Jetzt aktualisieren“ in der App (ab 1.21; ab 1.22 Start auf GitHub ohne Zugang in der App) – Browser-Test.

Verschlüsselte DEMO-Website (synthetische Kurse), Chromium im Format des S25+. GitHub bildet der Test nach – nur lesend und
ohne Anmeldung (``github_oeffentlich``). Der ganze Weg mit dem echten Server-Code (``jobs/kursaktualisierung``): Anfrage in der
App verschlüsseln, Zeile kopieren und GitHub öffnen, „auf GitHub“ mit dieser Zeile starten (wie „Run workflow“, Zeile
einfügen), zurück in der App Lauf und Lieferung finden, entschlüsseln, Kurszeit/Abrufzeit/Verzögerung zeigen – und ein
gespeicherter Kurs gilt nach dem erneuten Öffnen zwei Stunden später nicht mehr als aktuell.

Sicherheitsvorgabe (keine GitHub-Tokens im Browser, auch nicht verschlüsselt): kein Feld für einen Zugang, nie ein Kopf
„Authorization“, nie ein schreibender Aufruf, kein Bereich „zugang“ in IndexedDB.
"""

from __future__ import annotations

import base64
import datetime as dt
import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from tests.e2e.github_oeffentlich import REPO, OeffentlichesGitHub, eingabe_aus_app, github_oeffnen, zurueck_zur_app
from tests.e2e.test_mobile_app import APP_DIST, HAVE_PLAYWRIGHT, PASSPHRASE, S25, _chromium_path, _demo_site, _serve
from traktien.jobs import kursaktualisierung as ka
from traktien.providers.demo import DEMO_INTRADAY_NOW, DemoProvider, build_demo_universe
from traktien.util import crypto
from traktien.util.eingabe import split_eingabe

if HAVE_PLAYWRIGHT:
    from playwright.sync_api import expect, sync_playwright

__all__ = ["REPO"]


class KursGitHub(OeffentlichesGitHub):
    """„Run workflow“ für ``aktualisieren.yml``: die eingefügte Zeile geht an den echten Server-Code."""

    def __init__(self, key: crypto.KeyMaterial, work: Path, now: dt.datetime) -> None:
        super().__init__()
        self.key = key
        self.work = work
        self.now = now

    def start_kurse(self, line: str) -> dict:
        kennung, text = split_eingabe(line)
        channel = ka.OrdnerLieferkanal(self.work / f"kanal-{kennung}", now=lambda: self.now)
        ka.fetch_and_deliver(kennung, text, DemoProvider(), self.key, self.work / f"arbeit-{kennung}", channel, now=lambda: self.now + dt.timedelta(seconds=20))
        files = {str(p.relative_to(self.work / f"kanal-{kennung}")): p.read_bytes() for p in (self.work / f"kanal-{kennung}").rglob("*") if p.is_file()}
        self.put("kurse-aktuell", files)
        return self.add_run("aktualisieren.yml", "Kursaktualisierung", self.now + dt.timedelta(seconds=5))


@unittest.skipUnless(HAVE_PLAYWRIGHT and (APP_DIST / "index.html").exists(), "Playwright oder App-Build (app/dist) fehlt")
class UpdateFromAppTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = Path(tempfile.mkdtemp(prefix="e2e-aktualisieren-"))
        cls.site = _demo_site(cls.tmp / "verschluesselt", PASSPHRASE)
        cls.server, cls.base = _serve(cls.site)
        cls.key = crypto.verify_descriptor(json.loads((cls.site / "data" / "crypto.json").read_text()), PASSPHRASE)
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch(executable_path=_chromium_path())
        # Xetra-Aktie der DEMO: Kurs 15 Minuten verzögert, Handel läuft zum DEMO-Zeitpunkt
        cls.stock = next(i for i in build_demo_universe() if i.calendar == "XETR" and i.pattern == "steady_strong")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.browser.close()
        cls.pw.stop()
        cls.server.shutdown()
        cls.server.server_close()
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_refresh_one_stock_started_on_github_without_any_token_in_the_app(self) -> None:
        now = DEMO_INTRADAY_NOW + dt.timedelta(minutes=1)
        github = KursGitHub(self.key, self.tmp / "github", now)
        context = self.browser.new_context(**S25, locale="de-DE", timezone_id="Europe/Berlin", service_workers="block")
        context.grant_permissions(["clipboard-read", "clipboard-write"], origin=self.base.rstrip("/"))
        self.addCleanup(context.close)
        github.attach(context)
        page = context.new_page()
        page.set_default_timeout(20_000)
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.clock.set_fixed_time(now)
        page.goto(f"{self.base}#/einstellungen")
        page.locator("#passphrase").fill(PASSPHRASE)
        page.locator("#passphrase").press("Enter")

        # Einstellungen: kein Feld für einen GitHub-Zugang mehr
        page.goto(f"{self.base}#/einstellungen")
        expect(page.locator("main")).to_contain_text("Automatisch aktualisieren")
        expect(page.locator("main")).not_to_contain_text("Zugang prüfen und speichern")
        expect(page.locator("#zugang")).to_have_count(0)
        expect(page.locator("main")).to_contain_text("keiner – Läufe startest du auf GitHub mit deiner eigenen Anmeldung")

        # Einzelansicht: Jetzt aktualisieren → Zeile kopieren und GitHub öffnen
        page.goto(f"{self.base}#/aktie/{self.stock.isin}")
        block = page.locator("section.live-quote")
        expect(block).to_contain_text("Schlusskurs vom")
        block.get_by_role("button", name="Jetzt aktualisieren").click()
        start = block.locator(".gh-start")
        expect(start).to_contain_text("Auf GitHub „Run workflow“ antippen.")
        expect(start).to_contain_text("Ins Feld „anfrage“ lange tippen")
        link = start.get_by_role("link", name="Kopieren und GitHub öffnen")
        expect(link).to_have_attribute("href", f"https://github.com/{REPO}/actions/workflows/aktualisieren.yml")
        expect(link).to_have_attribute("target", "_blank")
        expect(block.locator(".update-progress-title")).to_have_text("Start auf GitHub")
        line = eingabe_aus_app(page, block)
        github_oeffnen(page, block)
        self.assertEqual(github.opened, [f"https://github.com/{REPO}/actions/workflows/aktualisieren.yml"])
        self.assertEqual(page.evaluate("navigator.clipboard.readText()"), line, "beim Öffnen von GitHub kopiert")

        # Die Zeile: nur Kennung und Chiffretext – weder ISIN noch Symbol lesbar; der Server liest sie
        kennung, text = split_eingabe(line)
        self.assertNotIn(self.stock.isin, line)
        self.assertNotIn(self.stock.symbol, base64.b64decode(text).decode("latin-1"))
        request = ka.parse_anfrage(text, kennung, self.key, now + dt.timedelta(seconds=5))
        self.assertEqual(([w.isin for w in request.werte], request.umfang, request.kursverlauf), ([self.stock.isin], "aktie", (self.stock.isin,)))

        # „Auf GitHub“ mit der eingefügten Zeile gestartet; zurück in der App kommt die Lieferung
        run = github.start_kurse(line)
        zurueck_zur_app(page)
        expect(block.locator(".update-progress-title")).to_contain_text("Kurse aktualisiert", timeout=30_000)
        expect(block).to_contain_text("Kurszeit")
        expect(block).to_contain_text("Abrufzeit")
        expect(block).to_contain_text("15 Min. verzögert laut Yahoo-Antwort")
        expect(block.locator(".badge-live")).to_have_text("aktuell")
        expect(block.locator(".day-course svg path.day-course-line")).to_have_count(1)
        expect(block.get_by_role("link", name="Lauf auf GitHub")).to_have_attribute("href", run["html_url"])
        expect(block.locator(".gh-start")).to_have_count(0)

        # Sicherheitsvorgabe: nur lesend, ohne Anmeldung, kein Zugang im Browser
        self.assertEqual(github.authorization_headers(), [], "nie ein Kopf „Authorization“")
        self.assertEqual(github.writes(), [], "kein schreibender Aufruf an GitHub")
        raw = [u for _, u, _ in github.requests if u.startswith("https://raw.githubusercontent.com/")]
        self.assertTrue(raw and all(re.match(rf"https://raw\.githubusercontent\.com/{REPO}/[0-9a-f]{{40}}/", u) for u in raw), "Dateien nur zu einem festen Commit")
        stores = page.evaluate("""() => new Promise((resolve) => {
            const open = indexedDB.open('tr-aktienvergleich');
            open.onsuccess = () => resolve(Array.from(open.result.objectStoreNames));
          })""")
        self.assertNotIn("zugang", stores)
        storage = json.dumps(page.evaluate("() => Object.fromEntries(Object.entries(localStorage))"))
        for marker in ("github_pat_", "ghp_", "Bearer", text[:24]):
            self.assertNotIn(marker, storage)

        # Zwei Stunden später neu geöffnet: derselbe gespeicherte Kurs ist nicht mehr aktuell
        page.clock.set_fixed_time(now + dt.timedelta(hours=2))
        page.reload()
        block = page.locator("section.live-quote")
        expect(block.locator(".badge-warn")).to_contain_text(re.compile(r"nicht aktuell \(Kurs 2,\d Std\. alt\)"))
        expect(block.locator(".badge-live")).to_have_count(0)
        self.assertEqual(errors, [])

    def test_broken_paste_on_github_is_reported_as_failed_run(self) -> None:
        """Abgeschnittene Zeile eingefügt: GitHub bricht den Lauf mit Fehler ab – die App meldet das verständlich."""
        now = DEMO_INTRADAY_NOW + dt.timedelta(minutes=3)
        github = KursGitHub(self.key, self.tmp / "github-kaputt", now)
        context = self.browser.new_context(**S25, locale="de-DE", timezone_id="Europe/Berlin", service_workers="block")
        self.addCleanup(context.close)
        github.attach(context)
        page = context.new_page()
        page.set_default_timeout(20_000)
        page.clock.set_fixed_time(now)
        page.goto(f"{self.base}#/einstellungen")
        page.locator("#passphrase").fill(PASSPHRASE)
        page.locator("#passphrase").press("Enter")
        page.goto(f"{self.base}#/aktie/{self.stock.isin}")
        block = page.locator("section.live-quote")
        block.get_by_role("button", name="Jetzt aktualisieren").click()
        github_oeffnen(page, block)
        github.add_run("aktualisieren.yml", "Kursaktualisierung", now + dt.timedelta(seconds=5), status="completed", conclusion="failure")
        zurueck_zur_app(page)
        expect(block.locator(".update-progress-title")).to_have_text("Aktualisierung fehlgeschlagen", timeout=30_000)
        expect(block.locator(".update-progress-detail")).to_contain_text("eingefügte Zeile unvollständig")
        self.assertEqual(github.authorization_headers(), [])


if __name__ == "__main__":
    unittest.main()
