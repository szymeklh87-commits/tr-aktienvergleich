"""Update von der vorigen App-Version auf diese – Service Worker, Speicher und gespeicherte Nutzerdaten (ab 1.19.0).

Simons Auftrag vom 25.10.2026, 14:23 Uhr: „Prüfe, dass Service Worker und Cache die neue Version übernehmen, ohne gespeicherte
Nutzerdaten zu löschen.“ Bis 1.18.2 prüfte T49 das nur mit einer künstlich geänderten ``sw.js`` derselben Version. Hier wie bei
einer echten Veröffentlichung: Die Website entsteht zuerst aus dem App-Build der **vorigen Version** (aus dem Git-Verlauf), wird
auf dem Gerät benutzt (Watchlist, Darstellung, entsperrter Schlüssel) und dann – wie „Nur die Website neu bereitstellen“ – aus
dem **aktuellen** Build mit denselben Daten neu zusammengesetzt (``publish.site.assemble_site``). Danach: neue Version aktiv,
alte App-Hülle gelöscht, Speicher der Daten und alle Einträge im lokalen Speicher und in IndexedDB unverändert, kein erneutes
Entsperren. DEMO-Daten (synthetisch).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from io import BytesIO
from pathlib import Path

from tests.e2e.test_mobile_app import APP_DIST, HAVE_PLAYWRIGHT, PASSPHRASE, REPO, S25, _chromium_path, _serve

if HAVE_PLAYWRIGHT:
    from playwright.sync_api import Error as PlaywrightError, expect, sync_playwright


def _version(text: str) -> str:
    return str(json.loads(text).get("version") or "")


def previous_release() -> tuple[str, str] | None:
    """(Commit, Version) des neuesten eingecheckten App-Builds mit anderer Versionsnummer als der aktuelle – None ohne Git-Verlauf."""
    current = _version((APP_DIST / "version.json").read_text(encoding="utf-8")).split("+")[0]
    try:
        commits = subprocess.run(["git", "log", "--format=%H", "-n", "80", "--", "app/dist/version.json"], cwd=REPO, check=True,
                                 capture_output=True, text=True, timeout=60).stdout.split()
    except (OSError, subprocess.SubprocessError):
        return None
    for commit in commits:
        shown = subprocess.run(["git", "show", f"{commit}:app/dist/version.json"], cwd=REPO, capture_output=True, text=True, timeout=60)
        if shown.returncode != 0:
            continue
        version = _version(shown.stdout)
        if version and version.split("+")[0] != current:
            return commit, version
    return None


def _extract_dist(commit: str, target: Path) -> Path:
    archive = subprocess.run(["git", "archive", "--format=tar", commit, "app/dist"], cwd=REPO, check=True, capture_output=True, timeout=120).stdout
    with tarfile.open(fileobj=BytesIO(archive)) as tar:
        tar.extractall(target, filter="data")
    return target / "app" / "dist"


def _demo(target: Path, dist: Path, passphrase: str | None) -> tuple[Path, Path]:
    state, site = target / "state", target / "site"
    command = [sys.executable, "-m", "traktien", "demo", "--fresh", "--state-dir", str(state), "--site", str(site), "--app-dist", str(dist)]
    if passphrase:
        command += ["--passphrase", passphrase]
    env = dict(os.environ, PYTHONPATH=str(REPO / "backend"), LOG_LEVEL="WARNING", GITHUB_REPOSITORY="beispiel/tr-aktienvergleich", GITHUB_SERVER_URL="https://github.com")
    subprocess.run(command, check=True, cwd=REPO, env=env, capture_output=True, text=True, timeout=600)
    return state, site


@unittest.skipUnless(HAVE_PLAYWRIGHT and (APP_DIST / "index.html").exists(), "Playwright oder App-Build (app/dist) fehlt")
class UpgradeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        found = previous_release()
        if found is None:
            raise unittest.SkipTest("keine frühere App-Version im Git-Verlauf (flacher Checkout?)")
        cls.old_commit, cls.old_version = found
        cls.new_version = _version((APP_DIST / "version.json").read_text(encoding="utf-8"))
        cls.tmp = Path(tempfile.mkdtemp(prefix="e2e-update-"))
        cls.old_dist = _extract_dist(cls.old_commit, cls.tmp / "alt")
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
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def _redeploy(self, state: Path, served: Path) -> None:
        """Wie „Nur die Website neu bereitstellen“: dieselben Daten, aktueller App-Build."""
        sys.path.insert(0, str(REPO / "backend"))
        from traktien.publish.site import assemble_site

        descriptor = json.loads((served / "data" / "crypto.json").read_text(encoding="utf-8"))
        os.environ.setdefault("GITHUB_REPOSITORY", "beispiel/tr-aktienvergleich")
        assemble_site(app_dist=APP_DIST, state_dir=state, out_dir=served, crypto_descriptor=descriptor)

    def _storage(self, page) -> dict:
        return page.evaluate(
            """async () => {
                const local = Object.fromEntries(Object.keys(localStorage).sort().map((k) => [k, localStorage.getItem(k)]));
                const dbs = (await indexedDB.databases()).map((d) => d.name).sort();
                const caches_ = (await caches.keys()).sort();
                return { local, dbs, caches: caches_ };
            }"""
        )

    def _wait_controller(self, page) -> None:
        self.assertTrue(page.evaluate("navigator.serviceWorker.ready.then(() => true)"))
        page.reload()
        page.wait_for_load_state("networkidle")
        for _ in range(200):
            if page.evaluate("!!navigator.serviceWorker.controller"):
                return
            page.wait_for_timeout(50)
        self.fail("Service Worker übernimmt die Seite nicht")

    def _run(self, passphrase: str | None) -> None:
        work = self.tmp / ("verschluesselt" if passphrase else "klar")
        state, site = _demo(work, self.old_dist, passphrase)
        served = work / "served"
        shutil.copytree(site, served)
        server, base = _serve(served)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        context = self.browser.new_context(**S25, locale="de-DE", timezone_id="Europe/Berlin", service_workers="allow")
        self.addCleanup(context.close)
        page = context.new_page()
        page.set_default_timeout(20000)
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(f"{base}#/ranking?h=30&w=60")
        page.wait_for_load_state("networkidle")
        if passphrase:
            page.locator("#passphrase").fill(passphrase)
            page.get_by_role("button", name="Entsperren").click()
        expect(page.locator("ol.rows > li").first).to_be_visible(timeout=30000)
        self._wait_controller(page)
        self.assertEqual(_version(page.evaluate("fetch('version.json', {cache: 'no-store'}).then((r) => r.text())")), self.old_version)
        # Nutzerdaten auf dem Gerät: eine Aktie gemerkt, dunkle Darstellung
        page.locator("ol.rows .watch-btn").first.click()
        page.goto(f"{base}#/einstellungen")
        page.get_by_role("radio", name="Dunkel").click()
        expect(page.get_by_text(self.old_version.split("+")[0], exact=False).first).to_be_visible()
        before = self._storage(page)
        self.assertTrue(any(n.startswith("tr-huelle-") for n in before["caches"]), before["caches"])
        # neue Version veröffentlichen (dieselben Daten) und wie auf dem Handy übernehmen
        self._redeploy(state, served)
        page.evaluate("navigator.serviceWorker.getRegistration().then((r) => r.update())")
        expect(page.get_by_text("Neue App-Version verfügbar")).to_be_visible(timeout=30000)
        with page.expect_navigation():
            page.get_by_role("button", name="Aktualisieren").click()
        page.wait_for_load_state("networkidle")
        if passphrase:
            self.assertEqual(page.locator("#passphrase").count(), 0, "nach dem Update kein erneutes Entsperren")
        after = self._storage(page)
        self.assertEqual(after["local"], before["local"], "lokaler Speicher (Watchlist, Einstellungen, Depots) unverändert")
        self.assertEqual(after["dbs"], before["dbs"], "IndexedDB (Schlüssel) unverändert")
        old_shell = [n for n in before["caches"] if n.startswith("tr-huelle-")]
        new_shell = [n for n in after["caches"] if n.startswith("tr-huelle-")]
        self.assertEqual(new_shell, [f"tr-huelle-{self.new_version}"], "genau die App-Hülle der neuen Version")
        self.assertTrue(set(old_shell).isdisjoint(new_shell), "alte App-Hülle gelöscht")
        kept = [n for n in before["caches"] if not n.startswith("tr-huelle-")]
        self.assertTrue(set(kept) <= set(after["caches"]), f"gespeicherte Daten bleiben: {kept} → {after['caches']}")
        self.assertEqual(page.evaluate("document.documentElement.dataset.theme"), "dunkel")
        page.goto(f"{base}#/einstellungen")
        expect(page.get_by_text(self.new_version.split("+")[0], exact=False).first).to_be_visible()
        page.goto(f"{base}#/watchlist?h=30&w=60")
        page.wait_for_load_state("networkidle")
        expect(page.locator("ul.rows > li")).to_have_count(1)
        self.assertEqual(errors, [], "keine Fehler der Seite")

    def test_update_from_previous_release_keeps_user_data(self) -> None:
        self._run(None)

    def test_update_on_the_encrypted_site_keeps_the_unlocked_key(self) -> None:
        self._run(PASSPHRASE)
