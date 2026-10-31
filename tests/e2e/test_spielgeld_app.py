"""Spielgeld-Robo in der App (Gesamtauftrag) – Browser-Test mit nachgebildeter GitHub-Schnittstelle.

Verschlüsselte DEMO-Website (synthetische Kurse), Chromium im Format des S25+. Der Test baut im Regel-Baukasten eine eigene
Regel aus einer Vorlage, sendet sie verschlüsselt an den (nachgebildeten) Workflow „Spielgeld-Eingang“ und zeigt das Ergebnis
der Prüfung. Die Prüfung macht dabei der echte Server-Code (``aktienpilot.eingang``) mit dem Datenschlüssel – so ist der ganze
Weg geprüft: Regel bauen, verschlüsseln, senden, prüfen, Ergebnis verschlüsselt zurück, Anzeige. Öffentlich (Workflow-Eingaben)
steht nur Zufallskennung und Chiffretext.
"""

from __future__ import annotations

import base64
import datetime as dt
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from tests.e2e.test_aktualisieren_app import REPO, TOKEN
from tests.e2e.test_mobile_app import APP_DIST, HAVE_PLAYWRIGHT, PASSPHRASE, S25, _chromium_path, _demo_site, _serve
from traktien.aktienpilot import eingang as ein
from traktien.aktienpilot import katalog as kat
from traktien.aktienpilot.config import load_aktienpilot_config
from traktien.config import load_method_config
from traktien.util import crypto

if HAVE_PLAYWRIGHT:
    from playwright.sync_api import expect, sync_playwright


class FakePilotGitHub:
    """Nachgebildete Schnittstelle: Lauf starten (prüft mit dem echten Server-Code) und Ergebnisdatei vom Branch liefern."""

    def __init__(self, key: crypto.KeyMaterial, work: Path) -> None:
        self.key = key
        self.work = work
        self.dispatched: list[dict] = []
        self.method = load_method_config()
        self.eintraege = kat.katalog(self.method, load_aktienpilot_config())

    def handle(self, route) -> None:
        cors = {"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "Authorization, Content-Type, X-GitHub-Api-Version, Accept",
                "Access-Control-Allow-Methods": "GET, POST, OPTIONS", "Access-Control-Expose-Headers": "x-ratelimit-remaining"}
        original = route.fulfill
        fulfill = lambda **kw: original(**kw, headers=cors)  # noqa: E731
        request = route.request
        if request.method == "OPTIONS":
            fulfill(status=204, body="")
            return
        path = request.url.split("api.github.com", 1)[1]
        if request.method == "POST" and path.endswith("/actions/workflows/spielgeld-eingang.yml/dispatches"):
            body = json.loads(request.post_data or "{}")
            self.dispatched.append(body)
            kennung, text = body["inputs"]["kennung"], body["inputs"]["nutzlast"]
            try:
                e, _blob = ein.annehmen(text, kennung, self.key, self.eintraege, self.method)
                result = dict(angenommen=True, code="angenommen", text="Angenommen", art=e.art, regel=f"{e.regel['id']}@{e.regel['version']}" if e.regel else None)
            except ein.EingangFehler as exc:
                result = dict(angenommen=False, code=exc.code, text=exc.text, art=None, regel=None)
            ein.ergebnis_datei(self.work / "ergebnis", kennung, self.key, **result)
            fulfill(status=204, body="")
            return
        if path.startswith(f"/repos/{REPO}/contents/ergebnis/"):
            name = path.split("/contents/", 1)[1].split("?", 1)[0]
            file = self.work / name
            if file.exists() and "ref=spielgeld-eingang" in path:
                fulfill(status=200, content_type="application/octet-stream", body=file.read_bytes())
            else:
                fulfill(status=404, content_type="application/json", body='{"message": "Not Found"}')
            return
        if path.endswith("/actions/secrets/public-key"):
            fulfill(status=403, content_type="application/json", body='{"message": "Resource not accessible by personal access token"}')
            return
        if path in (f"/repos/{REPO}", f"/repos/{REPO}/actions/workflows/aktualisieren.yml"):
            fulfill(status=200, content_type="application/json", body='{"id": 1}')
            return
        fulfill(status=404, content_type="application/json", body='{"message": "Not Found"}')


@unittest.skipUnless(HAVE_PLAYWRIGHT and (APP_DIST / "index.html").exists(), "Playwright oder App-Build (app/dist) fehlt")
class PilotFromAppTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = Path(tempfile.mkdtemp(prefix="e2e-spielgeld-"))
        cls.site = _demo_site(cls.tmp / "verschluesselt", PASSPHRASE)
        cls.server, cls.base = _serve(cls.site)
        cls.key = crypto.verify_descriptor(json.loads((cls.site / "data" / "crypto.json").read_text()), PASSPHRASE)
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch(executable_path=_chromium_path())

    @classmethod
    def tearDownClass(cls) -> None:
        cls.browser.close()
        cls.pw.stop()
        cls.server.shutdown()
        cls.server.server_close()
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_build_rule_send_encrypted_and_show_server_check(self) -> None:
        github = FakePilotGitHub(self.key, self.tmp / "github")
        context = self.browser.new_context(**S25, locale="de-DE", timezone_id="Europe/Berlin", service_workers="block")
        self.addCleanup(context.close)
        context.route("https://api.github.com/**", github.handle)
        page = context.new_page()
        page.set_default_timeout(20_000)
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(f"{self.base}#/einstellungen")
        page.locator("#passphrase").fill(PASSPHRASE)
        page.locator("#passphrase").press("Enter")
        page.goto(f"{self.base}#/einstellungen?abschnitt=zugang")
        section = page.locator("#zugang")
        section.locator("input[type=password]").first.fill(TOKEN)
        section.get_by_role("button", name="Zugang prüfen und speichern").click()
        expect(section).to_contain_text("Zugang gespeichert (verschlüsselt, nur auf diesem Gerät).")

        # Regel aus der Vorlage „Platz-1-Sammler mit Gewinnleiter“: Name ändern, Gewinnleiter sichtbar, Prüfung grün
        page.goto(f"{self.base}#/pilot/neu?vorlage=platz1_leiter")
        editor = page.locator(".pilot-editor")
        expect(editor).to_contain_text("Regel-Baukasten")
        name = editor.get_by_label("Name der Regel")
        name.fill("Mein Platz-1-Test")
        expect(editor).to_contain_text("Kennung r-mein-platz-1-test, Version 1")
        expect(editor).to_contain_text("Gewinnleiter (Gewinn nach Kosten")
        expect(editor.locator(".notice", has_text="Regel vollständig")).to_be_visible()
        # ohne Stop: Fehler, Senden gesperrt; mit Stop wieder frei
        send = editor.get_by_role("button", name="An den Robo senden (Test mit Spielgeld)")
        expect(send).to_be_enabled()
        send.click()
        expect(editor.locator(".pilot-send [role=status]").first).to_contain_text("Gesendet")
        expect(editor.locator(".pilot-send [role=status]").first).to_contain_text("Angenommen – wirksam mit dem nächsten täglichen Lauf (r-mein-platz-1-test@1)", timeout=25_000)

        # Öffentlich nur Kennung und Chiffretext; der Server liest die Regel
        self.assertEqual(len(github.dispatched), 1)
        sent = github.dispatched[0]
        self.assertEqual(sent["ref"], "main")
        self.assertEqual(set(sent["inputs"]), {"kennung", "nutzlast"})
        self.assertNotIn("Platz", base64.b64decode(sent["inputs"]["nutzlast"]).decode("latin-1"))
        data = ein.entschluesseln(base64.b64decode(sent["inputs"]["nutzlast"]), sent["inputs"]["kennung"], self.key)
        self.assertEqual((data["art"], data["inhalt"]["regel"]["id"], data["inhalt"]["regel"]["name"]), ("regel_testen", "r-mein-platz-1-test", "Mein Platz-1-Test"))
        self.assertEqual(data["inhalt"]["regel"]["verkauf"]["gewinnmitnahme"]["art"], "leiter")
        stored = json.dumps(page.evaluate("() => Object.fromEntries(Object.entries(localStorage))"))
        self.assertNotIn(TOKEN, stored)
        self.assertIn(sent["inputs"]["kennung"], stored, "gesendete Eingänge auf dem Gerät (nur Kennung und Bezeichnung)")

        # Übersicht: Steuerung der Automatik und Liste der Eingänge
        page.goto(f"{self.base}#/pilot")
        page.get_by_role("button", name="Automatik steuern").click()
        expect(page.get_by_role("button", name="Neue Käufe pausieren")).to_be_visible()
        page.get_by_role("button", name="Eingänge aus der App (0 verarbeitet)").click()
        expect(page.locator("main")).to_contain_text("auf GitHub angenommen")
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
