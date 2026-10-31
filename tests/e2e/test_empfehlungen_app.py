"""Depot-Empfehlungen in der App (Aufträge vom 31.10.2026, 18 und 19) – Browser-Test im Format des S25+.

Verschlüsselte DEMO-Website (synthetische Kurse) mit einem echten Forschungslauf des Depot-Optimierers über die
DEMO-Vorgeschichte (zwei Jahre, alle fünf Handelstage): kurze Zeiträume belastbar, lange ausdrücklich nicht. Geprüft wird die
Ansicht unter „Pilot → Empfehlungen“: Kopf mit Datenstand, Zeitraum, Risikoprofil, Erwartung und Unsicherheit, historischem
Test und Aktualisierung; sortierbare Tabelle mit Begründung, die zur Analyse der Aktie führt; Veränderungen; nicht belastbare
Varianten mit Grund; Rangliste je Zeitraum, Variantenvergleich, Prognosekontrolle, Strategieforschung, geprüfte Informationen;
Depotparameter mit denselben Grenzen wie auf dem Server, verschlüsselt gesendet und von der echten Server-Prüfung angenommen.
"""

from __future__ import annotations

import base64
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import json
from pathlib import Path

from tests.e2e.test_aktualisieren_app import TOKEN
from tests.e2e.test_mobile_app import APP_DIST, HAVE_PLAYWRIGHT, PASSPHRASE, REPO, S25, _chromium_path, _demo_site, _plain, _serve
from tests.e2e.test_spielgeld_app import FakePilotGitHub
from traktien.aktienpilot import eingang as ein
from traktien.util import crypto

if HAVE_PLAYWRIGHT:
    from playwright.sync_api import expect, sync_playwright


def _zahl(text: str) -> float:
    m = re.search(r"[−+-]?\d+(?:,\d+)?", _plain(text))
    assert m is not None, text
    return float(m.group(0).replace("−", "-").replace("+", "").replace(",", "."))


@unittest.skipUnless(HAVE_PLAYWRIGHT and (APP_DIST / "index.html").exists(), "Playwright oder App-Build (app/dist) fehlt")
class EmpfehlungenAppTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = Path(tempfile.mkdtemp(prefix="e2e-empfehlungen-"))
        cls.site = _demo_site(cls.tmp / "verschluesselt", PASSPHRASE)
        state = cls.tmp / "verschluesselt" / "state"
        env = dict(os.environ, PYTHONPATH=str(REPO / "backend"), LOG_LEVEL="WARNING", GITHUB_REPOSITORY="beispiel/tr-aktienvergleich",
                   GITHUB_SERVER_URL="https://github.com")
        subprocess.run([sys.executable, "-m", "traktien", "depot-optimierer", "--demo", "--passphrase", PASSPHRASE, "--state-dir", str(state), "--jahre", "2",
                        "--schritt", "5", "--site", str(cls.site), "--app-dist", str(APP_DIST)], check=True, cwd=REPO, env=env, capture_output=True, text=True,
                       timeout=1200)
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

    def _page(self, github: FakePilotGitHub | None = None):
        context = self.browser.new_context(**S25, locale="de-DE", timezone_id="Europe/Berlin", service_workers="block")
        self.addCleanup(context.close)
        if github is not None:
            context.route("https://api.github.com/**", github.handle)
        page = context.new_page()
        page.set_default_timeout(20_000)
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(f"{self.base}#/einstellungen")
        page.locator("#passphrase").fill(PASSPHRASE)
        page.locator("#passphrase").press("Enter")
        return page, errors

    def _shot(self, page, name: str) -> None:
        shots = os.environ.get("TR_E2E_SCREENSHOTS")
        if shots:
            Path(shots).mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(Path(shots) / name), full_page=False)

    def _ohne_seitwaerts(self, page) -> None:
        self.assertEqual(page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth"), 0, "keine waagerechte Scrollleiste")

    def test_recommended_depot_with_sortable_table_and_reasons(self) -> None:
        page, errors = self._page()
        page.goto(f"{self.base}#/pilot/empfehlungen")
        view = page.locator(".opt-view")
        expect(view).to_contain_text("Optimiertes Depot – Aktuelle Empfehlungen")
        expect(page.locator(".subnav a", has_text="Empfehlungen")).to_have_attribute("aria-current", "page")
        # Standardvariante aus der Vorgabe (noch keine Einrichtung): Ausgewogen; 12 Wochen nicht belastbar → ausdrücklich 4 Wochen
        variante = page.get_by_role("radiogroup", name="Depotvariante")
        expect(variante.get_by_role("radio", name=re.compile("^Ausgewogen"))).to_have_attribute("aria-checked", "true")
        expect(view).to_contain_text("Prognose für 12 Wochen nicht belastbar – dieses Depot rechnet mit der Prognose für 4 Wochen (eingeschränkt belastbar)")
        hero = page.locator(".opt-hero")
        expect(hero).to_contain_text("erwartete Depotrendite nach Kosten über 4 Wochen")
        expect(hero.locator(".badge")).to_have_text("eingeschränkt belastbar")
        self.assertRegex(_plain(hero.locator(".opt-hero-value").inner_text()), r"^[+−]\d+,\d %$")
        facts = page.locator(".opt-facts")
        for label in ("Datenstand", "Anlagezeitraum", "Risikoprofil", "Aktien", "Historisch getestet", "Prognosemodell", "Letzte Aktualisierung"):
            expect(facts).to_contain_text(label)
        expect(facts).to_contain_text("12.10.2026")
        expect(facts).to_contain_text("eingestellt 12 W")
        # Tabelle: zehn DEMO-Aktien mit ISIN, Kurs, Anteil, Erwartung, Risiko, Signal und Begründung; Anteile ergeben 100 %
        rows = page.locator(".opt-table tbody.opt-row")
        expect(rows).to_have_count(10)
        anteile = [_zahl(t) for t in rows.locator("tr:first-child td:nth-child(2)").all_inner_texts()]
        self.assertAlmostEqual(sum(anteile), 100.0, delta=0.6)
        self.assertEqual(anteile, sorted(anteile, reverse=True), "Vorgabe: nach Anteil absteigend")
        first = rows.first
        expect(first.locator("th a")).to_contain_text("DEMO ")
        detail = _plain(first.locator("tr.opt-detail").inner_text())
        self.assertRegex(detail, r"ZZ\d{10} · Kurs \d+,\d+ [A-Za-z]{3} \(12\.10\.2026\) · Spanne [+−]\d+,\d % bis [+−]\d+,\d % · Zehntel \d+")
        self.assertRegex(detail, r"Dafür: .+: obere \d+ %")
        # sortieren: Erwartung absteigend, dann aufsteigend (Spaltenkopf mit aria-sort)
        header = page.locator(".opt-table thead th", has_text="Erwartet")
        header.get_by_role("button").click()
        expect(header).to_have_attribute("aria-sort", "descending")
        werte = [_zahl(t) for t in rows.locator("tr:first-child td:nth-child(3)").all_inner_texts()]
        self.assertEqual(werte, sorted(werte, reverse=True))
        header.get_by_role("button").click()
        expect(header).to_have_attribute("aria-sort", "ascending")
        werte = [_zahl(t) for t in rows.locator("tr:first-child td:nth-child(3)").all_inner_texts()]
        self.assertEqual(werte, sorted(werte))
        self.assertIn("sortierung=erwartet%3Aauf", page.url)
        # erste Empfehlung: alle Aktien neu
        expect(page.locator("#opt-aenderungen").locator("xpath=..")).to_contain_text("Erste Empfehlung dieser Variante: alle 10 Aktien neu kaufen")
        expect(page.locator("#opt-risiko").locator("xpath=..")).to_contain_text("Branchen")
        self._shot(page, "50_empfehlungen.png")
        self._ohne_seitwaerts(page)
        # Antippen öffnet die vollständige Analyse der Aktie
        name = first.locator("th a")
        isin = name.get_attribute("href").split("/aktie/", 1)[1]
        name.click()
        page.wait_for_url(re.compile(rf"#/aktie/{isin}$"))
        expect(page.locator("main")).to_contain_text(isin)
        self.assertEqual(errors, [])

    def test_not_reliable_variant_and_further_views(self) -> None:
        page, errors = self._page()
        page.goto(f"{self.base}#/pilot/empfehlungen")
        page.get_by_role("radiogroup", name="Depotvariante").get_by_role("radio", name="Langfristig").click()
        view = page.locator(".opt-view")
        expect(view).to_contain_text("Langfristige Chancen: keine belastbare Prognose")
        expect(view).to_contain_text("Prognose für 52 Wochen nicht belastbar – kein Depotvorschlag ohne geprüfte Grundlage")
        expect(view.locator(".notice a", has_text="Kurzfristige Chancen (2 Wochen)")).to_be_visible()
        expect(page.locator(".opt-table")).to_have_count(0)
        ansicht = page.get_by_role("radiogroup", name="Ansicht")
        # Rangliste je Zeitraum: 52 Wochen ausdrücklich nicht belastbar, 1 Woche mit Rangliste
        ansicht.get_by_role("radio", name="Rangliste").click()
        zeitraum = page.get_by_role("radiogroup", name="Prognosezeitraum")
        zeitraum.get_by_role("radio", name="52 W").click()
        expect(view).to_contain_text("Für 52 Wochen ist keine Prognose belastbar")
        zeitraum.get_by_role("radio", name="1 W").click()
        expect(page.locator(".opt-rank-item")).to_have_count(10)
        page.get_by_role("button", name=re.compile(r"^Alle \d+ zeigen$")).click()
        self.assertGreater(page.locator(".opt-rank-item").count(), 10)
        self._shot(page, "51_rangliste.png")
        # Variantenvergleich: alle sechs, nicht belastbare ausdrücklich
        ansicht.get_by_role("radio", name="Varianten").click()
        expect(page.locator(".opt-var-table tbody tr")).to_have_count(6)
        expect(page.locator(".opt-var-table tr[data-variante='lang']")).to_contain_text("nicht belastbar")
        expect(page.locator(".opt-var-table tr[data-variante='kurz'] td.n").first).to_contain_text("±")
        # Prognosekontrolle: gespeichert, noch nichts ausgewertet (erster Tag)
        ansicht.get_by_role("radio", name="Kontrolle").click()
        expect(view).to_contain_text("Noch keine Prognose ausgewertet")
        # Modus C: nicht eingeschaltet; das Musterdepot startet erst mit dem nächsten täglichen Lauf
        expect(view).to_contain_text("Übernahme in den Spielgeld-Piloten")
        expect(view).to_contain_text("Nicht eingeschaltet: Das Pilotdepot übernimmt die Empfehlung nicht von selbst.")
        expect(view).to_contain_text("Das Musterdepot startet mit dem nächsten täglichen Lauf")
        # Strategieforschung: sechs Zeiträume, Modellvergleich mit Nullmodell, Kalibrierung
        ansicht.get_by_role("radio", name="Forschung").click()
        expect(page.locator(".opt-forschung")).to_have_count(6)
        page.locator(".opt-forschung[data-horizont='w1'] .disclosure-toggle").click()
        w1 = page.locator(".opt-forschung[data-horizont='w1']")
        expect(w1).to_contain_text("Modellvergleich im Walk‑forward")
        expect(w1).to_contain_text("Nullmodell (alle Aktien gleich)")
        expect(w1).to_contain_text("Kalibrierung")
        self._shot(page, "52_forschung.png")
        # geprüfte Informationen: Zählungen und alle Kennzahlen mit Grund
        ansicht.get_by_role("radio", name="Infos").click()
        expect(view).to_contain_text("92 (Kennzahlen mit verschiedenen Zeitfenstern)")
        expect(view).to_contain_text("58 von 76 aus dem zentralen Katalog")
        page.get_by_role("button", name="Alle 76 Kennzahlen des Katalogs: genutzt oder mit Grund ausgelassen").click()
        expect(page.locator(".opt-inventar li")).to_have_count(76)
        expect(page.locator(".opt-inventar li[data-kennzahl='kurs']")).to_contain_text("zwischen Aktien nicht vergleichbar")
        self._ohne_seitwaerts(page)
        self.assertEqual(errors, [])

    def test_depot_parameters_same_limits_and_accepted_by_server(self) -> None:
        github = FakePilotGitHub(self.key, self.tmp / "github-parameter")
        page, errors = self._page(github)
        page.goto(f"{self.base}#/einstellungen?abschnitt=zugang")
        section = page.locator("#zugang")
        section.locator("input[type=password]").first.fill(TOKEN)
        section.get_by_role("button", name="Zugang prüfen und speichern").click()
        expect(section).to_contain_text("Zugang gespeichert")
        page.goto(f"{self.base}#/pilot/empfehlungen?ansicht=parameter")
        view = page.locator(".opt-view")
        expect(view).to_contain_text("Ausgewogen (Vorgabe (noch keine Einrichtung))")
        page.get_by_role("button", name="Depotparameter ändern").click()
        anzahl = page.get_by_label("Aktien im Depot (3–20)")
        anzahl.fill("25")
        expect(page.locator(".field-error")).to_have_text("Anzahl Aktien: 3 bis 20")
        expect(page.get_by_role("button", name="Depotparameter an den Robo senden")).to_have_count(0)
        anzahl.fill("8")
        page.get_by_label("Standardvariante").select_option("stabil")
        page.get_by_label("Anlagehorizont").select_option("w4")
        page.get_by_label("Höchstgewicht je Aktie (%)").fill("25")
        expect(page.locator(".field-error")).to_have_count(0)
        page.get_by_role("button", name="Depotparameter an den Robo senden").click()
        expect(page.locator(".pilot-send [role=status]").first).to_contain_text("Angenommen – wirksam mit dem nächsten täglichen Lauf", timeout=25_000)
        self.assertEqual(len(github.dispatched), 1)
        sent = github.dispatched[0]
        data = ein.entschluesseln(base64.b64decode(sent["inputs"]["nutzlast"]), sent["inputs"]["kennung"], self.key)
        self.assertEqual(data["art"], "optimierer_einstellungen")
        x = data["inhalt"]
        self.assertEqual((x["variante"], x["horizont"], x["anzahl"], x["max_gewicht_pct"]), ("stabil", "w4", 8, 25))
        self.assertEqual(ein.optimierer_einstellungen_pruefen(x)["anzahl"], 8, "dieselbe Prüfung wie im täglichen Lauf")
        self._shot(page, "53_parameter.png")
        self._ohne_seitwaerts(page)
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
