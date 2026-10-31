"""„Jetzt aktualisieren“ in der App (ab 1.21) – Browser-Test mit nachgebildeter GitHub-Schnittstelle.

Verschlüsselte DEMO-Website (synthetische Kurse), Chromium im Format des S25+. Die GitHub-Schnittstelle bildet der Test nach:
Lauf starten, Status und Schritte, Lieferungen vom Branch „kurse-aktuell“. Die Lieferungen erzeugt dabei der echte Server-Code
(``jobs/kursaktualisierung``) aus der Anfrage, die die App verschlüsselt geschickt hat – so prüft der Test den ganzen Weg:
Zugang speichern, Anfrage verschlüsseln, Fortschritt, Lieferung entschlüsseln, Kurszeit/Abrufzeit/Verzögerung, und dass ein
gespeicherter Kurs nach dem erneuten Öffnen zwei Stunden später nicht mehr als aktuell erscheint.
"""

from __future__ import annotations

import base64
import datetime as dt
import json
import re
import shutil
import tempfile
import threading
import unittest
from pathlib import Path

from tests.e2e.test_mobile_app import APP_DIST, HAVE_PLAYWRIGHT, PASSPHRASE, S25, _chromium_path, _demo_site, _serve
from traktien.jobs import kursaktualisierung as ka
from traktien.providers.demo import DEMO_INTRADAY_NOW, DemoProvider, build_demo_universe
from traktien.util import crypto

if HAVE_PLAYWRIGHT:
    from playwright.sync_api import expect, sync_playwright

REPO = "beispiel/tr-aktienvergleich"
API = f"https://api.github.com/repos/{REPO}"
TOKEN = "github_pat_" + "A1b2C3d4E5" * 5
RUN_ID = 4711


class FakeGitHub:
    """Nachgebildete GitHub-Schnittstelle: ein Lauf, der beim zweiten Abruf läuft und beim dritten fertig ist."""

    def __init__(self, key: crypto.KeyMaterial, work: Path, now: dt.datetime) -> None:
        self.key = key
        self.work = work
        self.now = now
        self.dispatched: list[dict] = []
        self.run_polls = 0
        self.lock = threading.Lock()
        self.channel = ka.OrdnerLieferkanal(work / "kanal", now=lambda: now)
        self.authorization: set[str] = set()

    def handle(self, route) -> None:
        # Wie api.github.com: Aufrufe aus dem Browser erlaubt (CORS), auch mit Kopf „Authorization“
        cors = {"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "Authorization, Content-Type, X-GitHub-Api-Version, Accept",
                "Access-Control-Allow-Methods": "GET, POST, OPTIONS", "Access-Control-Expose-Headers": "x-ratelimit-remaining"}
        original = route.fulfill
        route_fulfill = lambda **kw: original(**kw, headers=cors)  # noqa: E731
        request = route.request
        if request.method == "OPTIONS":
            route_fulfill(status=204, body="")
            return
        self.authorization.add(request.headers.get("authorization", ""))
        path = request.url.split("api.github.com", 1)[1]
        if request.method == "POST" and path.endswith("/actions/workflows/aktualisieren.yml/dispatches"):
            body = json.loads(request.post_data or "{}")
            self.dispatched.append(body)
            inputs = body["inputs"]
            ka.fetch_and_deliver(inputs["kennung"], inputs["anfrage"], DemoProvider(), self.key, self.work / "arbeit", self.channel, now=lambda: self.now + dt.timedelta(seconds=20))
            route_fulfill(status=200, content_type="application/json", body=json.dumps({"workflow_run_id": RUN_ID, "run_url": f"{API}/actions/runs/{RUN_ID}", "html_url": f"https://github.com/{REPO}/actions/runs/{RUN_ID}"}))
            return
        if path.startswith(f"/repos/{REPO}/actions/runs/{RUN_ID}/jobs"):
            done = self.run_polls >= 3
            steps = [
                {"name": "Set up job", "status": "completed", "conclusion": "success", "number": 1, "started_at": None, "completed_at": None},
                {"name": "Kurse abrufen und liefern (sichtbare Aktien zuerst)", "status": "completed" if done else "in_progress", "conclusion": "success" if done else None, "number": 2, "started_at": None, "completed_at": None},
            ]
            route_fulfill(status=200, content_type="application/json", body=json.dumps({"jobs": [{"name": "kurse", "status": "completed" if done else "in_progress", "conclusion": None, "started_at": None, "completed_at": None, "steps": steps}]}))
            return
        if path.startswith(f"/repos/{REPO}/actions/runs/{RUN_ID}"):
            with self.lock:
                self.run_polls += 1
                polls = self.run_polls
            status = "queued" if polls == 1 else "in_progress" if polls == 2 else "completed"
            created = self.now.strftime("%Y-%m-%dT%H:%M:%SZ")
            route_fulfill(status=200, content_type="application/json", body=json.dumps({
                "id": RUN_ID, "status": status, "conclusion": "success" if status == "completed" else None, "created_at": created, "run_started_at": created, "updated_at": created,
                "html_url": f"https://github.com/{REPO}/actions/runs/{RUN_ID}", "display_title": "Kursaktualisierung",
            }))
            return
        if path.startswith(f"/repos/{REPO}/contents/aktuell/"):
            name = path.split("/contents/", 1)[1].split("?", 1)[0]
            file = self.work / "kanal" / name
            if self.run_polls >= 2 and file.exists() and "ref=kurse-aktuell" in path:
                route_fulfill(status=200, content_type="application/octet-stream", body=file.read_bytes())
            else:
                route_fulfill(status=404, content_type="application/json", body='{"message": "Not Found"}')
            return
        if path.endswith("/actions/secrets/public-key"):
            route_fulfill(status=403, content_type="application/json", body='{"message": "Resource not accessible by personal access token"}')
            return
        if path in (f"/repos/{REPO}", f"/repos/{REPO}/actions/workflows/aktualisieren.yml"):
            route_fulfill(status=200, content_type="application/json", body='{"id": 1}')
            return
        route_fulfill(status=404, content_type="application/json", body='{"message": "Not Found"}')


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

    def test_refresh_one_stock_shows_progress_times_and_never_shows_stored_prices_as_current(self) -> None:
        now = DEMO_INTRADAY_NOW + dt.timedelta(minutes=1)
        github = FakeGitHub(self.key, self.tmp / "github", now)
        context = self.browser.new_context(**S25, locale="de-DE", timezone_id="Europe/Berlin", service_workers="block")
        self.addCleanup(context.close)
        context.route("https://api.github.com/**", github.handle)
        page = context.new_page()
        page.set_default_timeout(20_000)
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.clock.set_fixed_time(now)
        page.goto(f"{self.base}#/einstellungen")
        page.locator("#passphrase").fill(PASSPHRASE)
        page.locator("#passphrase").press("Enter")

        # Zugang einrichten (verschlüsselt gespeichert)
        page.goto(f"{self.base}#/einstellungen?abschnitt=zugang")
        section = page.locator("#zugang")
        expect(section).to_contain_text("nicht eingerichtet")
        section.locator("input[type=password]").first.fill(TOKEN)
        section.get_by_role("button", name="Zugang prüfen und speichern").click()
        expect(section).to_contain_text("Zugang gespeichert (verschlüsselt, nur auf diesem Gerät).")
        expect(section).to_contain_text("eingerichtet")
        stored = page.evaluate("""() => new Promise((resolve) => {
            const open = indexedDB.open('tr-aktienvergleich');
            open.onsuccess = () => {
              const get = open.result.transaction('zugang').objectStore('zugang').get('github');
              get.onsuccess = () => resolve(Array.from(get.result || []));
            };
          })""")
        self.assertGreater(len(stored), 30)
        self.assertNotIn(TOKEN.encode(), bytes(stored), "Token nur verschlüsselt gespeichert")
        self.assertNotIn(TOKEN, json.dumps(page.evaluate("() => Object.fromEntries(Object.entries(localStorage))")))

        # Einzelansicht: Jetzt aktualisieren
        page.goto(f"{self.base}#/aktie/{self.stock.isin}")
        block = page.locator("section.live-quote")
        expect(block).to_contain_text("Schlusskurs vom")
        block.get_by_role("button", name="Jetzt aktualisieren").click()
        expect(block.locator(".update-progress")).to_be_visible()
        expect(block.locator(".update-progress-title")).to_contain_text("Kurse aktualisiert", timeout=30_000)
        expect(block).to_contain_text("Kurszeit")
        expect(block).to_contain_text("Abrufzeit")
        expect(block).to_contain_text("15 Min. verzögert laut Yahoo-Antwort")
        expect(block.locator(".badge-live")).to_have_text("aktuell")
        expect(block.locator(".day-course svg path.day-course-line")).to_have_count(1)
        expect(block.get_by_role("link", name="Lauf auf GitHub")).to_have_attribute("href", f"https://github.com/{REPO}/actions/runs/{RUN_ID}")

        # Die Anfrage war verschlüsselt: weder ISIN noch Symbol öffentlich lesbar, der Server kann sie lesen
        self.assertEqual(len(github.dispatched), 1)
        sent = github.dispatched[0]
        self.assertEqual(sent["ref"], "main")
        self.assertNotIn(self.stock.isin, json.dumps(sent))
        self.assertNotIn(self.stock.symbol, base64.b64decode(sent["inputs"]["anfrage"]).decode("latin-1"))
        request = ka.parse_anfrage(sent["inputs"]["anfrage"], sent["inputs"]["kennung"], self.key, now + dt.timedelta(seconds=5))
        self.assertEqual(([w.isin for w in request.werte], request.umfang, request.kursverlauf), ([self.stock.isin], "aktie", (self.stock.isin,)))
        self.assertEqual(github.authorization - {""}, {f"Bearer {TOKEN}"})

        # Zwei Stunden später neu geöffnet: derselbe gespeicherte Kurs ist nicht mehr aktuell
        page.clock.set_fixed_time(now + dt.timedelta(hours=2))
        page.reload()
        block = page.locator("section.live-quote")
        expect(block.locator(".badge-warn")).to_contain_text(re.compile(r"nicht aktuell \(Kurs 2,\d Std\. alt\)"))
        expect(block.locator(".badge-live")).to_have_count(0)
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
