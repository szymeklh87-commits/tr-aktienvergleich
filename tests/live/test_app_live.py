"""Prüfung der veröffentlichten App mit echten Daten (Netzwerk und Passphrase nötig).

Nur mit ``TR_LIVE_APP=1`` und ``DATA_PASSPHRASE`` aktiv – gedacht für den manuellen Workflow
„App mit echten Daten prüfen“ in GitHub Actions, wo die Passphrase als Secret vorliegt. Die App wird
so geöffnet wie auf dem Galaxy S25+ (Chromium, 384 × 832 CSS-Pixel, Touch, Deutsch, Europe/Berlin),
mit der Passphrase entsperrt, und jede Ansicht wird aufgerufen.

Ausgegeben werden nur Zählungen, Zeiten, Versions- und Datumsangaben sowie Fehlermeldungen – keine
Kurse, Namen oder Ranglisteninhalte: Der Datenstand ist verschlüsselt, damit er nicht öffentlich
lesbar ist, und das Protokoll eines öffentlichen Repositorys ist öffentlich. Die Passphrase wird nur
in das Eingabefeld der App getippt und nirgends ausgegeben (GitHub maskiert sie zusätzlich).

Ergebnis als JSON: ``TR_LIVE_APP_REPORT=<Datei>``; Hinweise in der Laufübersicht über
``tests/live/app_bericht_hinweis.py``.
"""

from __future__ import annotations

import json
import os
import re
import time
import unittest
import uuid
from pathlib import Path

LIVE = os.environ.get("TR_LIVE_APP") == "1"
PASSPHRASE = os.environ.get("DATA_PASSPHRASE") or ""
BASE = os.environ.get("TR_APP_URL", "https://szymeklh87-commits.github.io/tr-aktienvergleich/")
S25 = {"viewport": {"width": 384, "height": 832}, "device_scale_factor": 2.8125, "is_mobile": True, "has_touch": True}
REPORT: dict = {"adresse": BASE, "ansichten": {}, "konsolenfehler": [], "fehler": [], "fehlgeschlagene_abrufe": []}
STEP = {"name": "Start"}  # aktueller Prüfschritt (für die Zuordnung fehlgeschlagener Abrufe)

# Ansichten wie im Menü der App; je Ansicht ein Element, das nur mit geladenen Daten erscheint
VIEWS: list[tuple[str, str, str]] = [
    ("Start", "/", ".stamp-date"),
    ("Potenzial (Kandidaten)", "/potenzial", "ol.sig-rows > li, .notice-title"),
    ("Analyse-Werkzeuge", "/analyse", ".tool-list li"),
    ("Rendite (alle 90 Zeiträume)", "/rendite?f=alle&z=alle", "ol.window-list > li"),
    ("Rendite mit Umsatzfilter", "/rendite?f=umsatz&z=alle", "ol.window-list > li"),
    ("Ranking 30 Tage 60/40", "/ranking?h=30&w=60&p=native", "ol.rows > li"),
    ("Matrix", "/matrix", "td.gcell"),
    ("Häufigste Aktien", "/haeufig", "td.n"),
    ("Raster", "/raster", "li.tile"),
    ("Sieger nach Zeitraum", "/sieger", "div.tenw-cell"),
    ("Gewichtungen vergleichen", "/vergleich", "td.n"),
    ("Alle Aktien & Abdeckung", "/aktien", "li.row"),
    ("Watchlist", "/watchlist", "header.view-head"),
    ("Umschichtungs-Regel", "/regel", "li.row"),
    ("Datenstand & Betrieb", "/status", ".kv-row"),
    ("So wird gerechnet", "/methodik", "h2"),
    ("Einstellungen", "/einstellungen", "h2.section-title"),
    ("Jetzt aktualisieren", "/aktualisieren", "header.view-head"),
    ("Installieren", "/installieren", "header.view-head"),
]
ERROR_TEXTS = ("Diese Ansicht konnte nicht angezeigt werden", "Daten konnten nicht geladen werden", "Der Zugangsschlüssel passt nicht")

try:
    from playwright.sync_api import sync_playwright

    HAVE_PLAYWRIGHT = True
except ImportError:  # pragma: no cover - Umgebung ohne Playwright
    HAVE_PLAYWRIGHT = False


def tearDownModule() -> None:
    path = os.environ.get("TR_LIVE_APP_REPORT")
    if path and LIVE:
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(REPORT, handle, ensure_ascii=False, indent=2)
    if LIVE:
        print(json.dumps(REPORT, ensure_ascii=False, indent=2))


def _safe(text: str) -> str:
    """Fehlermeldungen ohne Passphrase (doppelte Sicherung neben der Maskierung durch GitHub)."""
    return text.replace(PASSPHRASE, "***") if PASSPHRASE else text


@unittest.skipUnless(LIVE and PASSPHRASE, "Live-Prüfung der App nur mit TR_LIVE_APP=1 und DATA_PASSPHRASE")
@unittest.skipUnless(HAVE_PLAYWRIGHT, "Playwright nicht installiert")
class LiveAppTest(unittest.TestCase):
    """Reihenfolge ist wichtig (Entsperren zuerst); unittest sortiert nach Namen: test_1_…, test_2_…"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.pw = sync_playwright().start()
        local = Path("/opt/pw-browsers/chromium")  # Entwicklungsumgebung; in GitHub Actions der installierte Chromium
        cls.browser = cls.pw.chromium.launch(executable_path=str(local) if local.exists() else None)
        cls.context = cls.browser.new_context(**S25, locale="de-DE", timezone_id="Europe/Berlin", service_workers="allow")
        cls.page = cls.context.new_page()
        cls.page.set_default_timeout(60000)
        cls.page.on("console", lambda m: REPORT["konsolenfehler"].append(f"{STEP['name']}: {_safe(m.text)[:300]}") if m.type == "error" else None)
        cls.page.on("pageerror", lambda e: REPORT["konsolenfehler"].append(f"{STEP['name']}: {_safe(str(e))[:300]}"))

        def path_of(url: str) -> str:
            return url.split("?")[0].replace(BASE, "")

        cls.page.on(
            "response",
            lambda r: REPORT["fehlgeschlagene_abrufe"].append(
                {"schritt": STEP["name"], "datei": path_of(r.url), "status": r.status, "service_worker": r.from_service_worker}
            )
            if r.status >= 400
            else None,
        )
        cls.page.on(
            "requestfailed",
            lambda r: REPORT["fehlgeschlagene_abrufe"].append({"schritt": STEP["name"], "datei": path_of(r.url), "fehler": (r.failure or "")[:120]}),
        )
        cls.unlocked = False
        cls.status = {}

    @classmethod
    def tearDownClass(cls) -> None:
        cls.context.close()
        cls.browser.close()
        cls.pw.stop()

    # ------------------------------------------------------------------ Hilfen

    def settle(self, timeout: float = 60.0, quiet: float = 1.0) -> None:
        """Warten, bis seit ``quiet`` Sekunden keine Ladeanzeige mehr zu sehen ist (Ansichten laden
        Teile nach, z. B. die Kursreihe der Einzelansicht)."""
        page = self.page
        page.wait_for_load_state("networkidle")
        deadline = time.monotonic() + timeout
        calm_since = None
        while time.monotonic() < deadline:
            if page.locator(".loading").count():
                calm_since = None
            elif calm_since is None:
                calm_since = time.monotonic()
            elif time.monotonic() - calm_since >= quiet:
                return
            page.wait_for_timeout(100)

    def problems(self) -> list[str]:
        text = self.page.locator("main").inner_text() if self.page.locator("main").count() else self.page.inner_text("body")
        found = [t for t in ERROR_TEXTS if t in text]
        if self.page.locator(".loading").count():
            found.append("Ladeanzeige nach 60 s noch sichtbar")
        overflow = self.page.evaluate("document.documentElement.scrollWidth - window.innerWidth")
        if overflow > 1:
            found.append(f"Seite {overflow} px breiter als der Bildschirm")
        return found

    # ------------------------------------------------------------------ Prüfungen

    def test_1_open_and_unlock(self) -> None:
        page = self.page
        started = time.monotonic()
        page.goto(f"{BASE}?pruefung={uuid.uuid4().hex[:8]}")
        page.wait_for_load_state("networkidle")
        stamp = uuid.uuid4().hex[:8]
        version = self.context.request.get(f"{BASE}version.json?x={stamp}")
        REPORT["version"] = version.json().get("version") if version.ok else None
        response = self.context.request.get(f"{BASE}data/status.json?x={stamp}")
        status = response.json() if response.ok else {}
        type(self).status = status
        REPORT["datenstand"] = {
            "neuester": status.get("latest_snapshot_id"),
            "neuester_vollstaendig": status.get("latest_complete_snapshot_id"),
            "kursstand": status.get("last_price_session"),
            "letzter_lauf": (status.get("last_run") or {}).get("status"),
            "aufbewahrt": len(status.get("retained_snapshot_ids") or []),
        }
        locked = page.get_by_role("heading", name="Zugangsschlüssel eingeben")
        page.wait_for_timeout(1500)
        REPORT["verschluesselt"] = bool(locked.count())
        if locked.count():
            page.locator("#passphrase").fill(PASSPHRASE)
            page.locator("button[type='submit']").click()
        page.locator(".stamp-date").first.wait_for(state="visible", timeout=120000)
        self.settle()
        REPORT["entsperren_und_laden_s"] = round(time.monotonic() - started, 1)
        REPORT["kopf"] = re.sub(r"\s+", " ", page.locator(".stamp-date").first.inner_text()).strip()
        REPORT["teilstand"] = page.locator(".stamp-partial").count() > 0
        type(self).unlocked = True
        self.assertEqual(self.problems(), [])

    def test_2_every_view(self) -> None:
        if not self.unlocked:
            self.skipTest("App nicht entsperrt")
        page = self.page
        failures = []
        for name, route, selector in VIEWS:
            STEP["name"] = name
            started = time.monotonic()
            entry: dict = {"route": route}
            try:
                page.evaluate(f"location.hash = {json.dumps(route)}")
                self.settle()
                page.locator(selector).first.wait_for(state="attached", timeout=60000)
                entry["elemente"] = page.locator(selector).count()
                entry["probleme"] = self.problems()
            except Exception as exc:  # Ansicht festhalten, mit der nächsten weitermachen
                entry["probleme"] = [f"{type(exc).__name__}: {_safe(str(exc)).splitlines()[0][:200]}"]
            entry["sekunden"] = round(time.monotonic() - started, 1)
            REPORT["ansichten"][name] = entry
            if entry["probleme"]:
                failures.append(f"{name}: {'; '.join(entry['probleme'])}")
        rendite = REPORT["ansichten"].get("Rendite (alle 90 Zeiträume)", {})
        if rendite.get("elemente") not in (None, 90):
            failures.append(f"Rendite: {rendite.get('elemente')} statt 90 Zeiträume")
        ranking = REPORT["ansichten"].get("Ranking 30 Tage 60/40", {})
        if not ranking.get("elemente"):
            failures.append("Ranking 30 Tage: keine Plätze")
        REPORT["fehler"].extend(failures)
        self.assertEqual(failures, [])

    def test_3_detail_of_first_stock(self) -> None:
        if not self.unlocked:
            self.skipTest("App nicht entsperrt")
        page = self.page
        STEP["name"] = "Einzelansicht"
        started = time.monotonic()
        page.evaluate("location.hash = '/ranking?h=30&w=0&p=native'")
        self.settle()
        page.locator("ol.rows > li .row-link").first.click()
        deadline = time.monotonic() + 30
        while not page.evaluate("location.hash.startsWith('#/aktie/')") and time.monotonic() < deadline:
            page.wait_for_timeout(100)
        page.locator(".kv-row").first.wait_for(state="attached", timeout=60000)
        self.settle()
        try:
            page.locator(".chart-surface svg").first.wait_for(state="attached", timeout=60000)
        except Exception:  # fehlende Grafik wird unten gemeldet
            pass
        self.settle()
        detail = {
            "kennzahlen_zeilen": page.locator(".kv-row").count(),
            "kursgrafik": page.locator(".chart-surface svg, .chart-surface canvas").count() > 0,
            "zweiter_boersenplatz": page.locator(".kv-row", has_text="Zweiter Börsenplatz").count() > 0,
            "probleme": self.problems(),
            "sekunden": round(time.monotonic() - started, 1),
        }
        REPORT["einzelansicht"] = detail
        problems = list(detail["probleme"])
        if detail["kennzahlen_zeilen"] < 5:
            problems.append(f"nur {detail['kennzahlen_zeilen']} Kennzahlzeilen")
        if not detail["kursgrafik"]:
            problems.append("keine Kursgrafik")
        REPORT["fehler"].extend(f"Einzelansicht: {p}" for p in problems)
        self.assertEqual(problems, [])

    def test_3b_signal_detail_of_first_candidate(self) -> None:
        """Ab 1.6: erste Aktie der Kandidaten öffnen – zwei Urteile, Prognose, Signale (nur mit Signal-Stand)."""
        if not self.unlocked:
            self.skipTest("App nicht entsperrt")
        page = self.page
        STEP["name"] = "Signale"
        if not (self.status or {}).get("signale"):
            REPORT["signale"] = {"hinweis": "noch kein Signal-Stand veröffentlicht"}
            self.skipTest("noch kein Signal-Stand")
        started = time.monotonic()
        page.evaluate("location.hash = '/potenzial'")
        self.settle()
        rows = page.locator("ol.sig-rows > li")
        rows.first.wait_for(timeout=60000)
        listed = rows.count()
        rows.first.locator("a.row-name").click()
        page.locator(".verdict").first.wait_for(timeout=60000)
        self.settle()
        signals = {
            "zeilen_potenzial": listed,
            "urteile": page.locator(".verdict").count(),
            "prognose": page.locator("figure.forecast svg").count() > 0,
            "signale": page.locator(".signal-list li").count(),
            "probleme": self.problems(),
            "sekunden": round(time.monotonic() - started, 1),
        }
        REPORT["signale"] = signals | {k: v for k, v in (self.status or {}).get("signale", {}).items() if k in ("id", "aktien", "mit_kursziel", "beide_gruen", "kurz_gruen", "lang_gruen")}
        problems = list(signals["probleme"])
        if signals["urteile"] != 2:
            problems.append(f"{signals['urteile']} statt 2 Urteile")
        if signals["signale"] < 10:
            problems.append(f"nur {signals['signale']} Signale")
        REPORT["fehler"].extend(f"Signale: {p}" for p in problems)
        self.assertEqual(problems, [])

    def test_4_reopen_without_passphrase_and_offline_ready(self) -> None:
        """Wie auf dem Handy: App erneut öffnen – der gespeicherte Schlüssel genügt; der Service Worker
        übernimmt die Seite (Voraussetzung für Start vom Startbildschirm und Offline-Anzeige)."""
        if not self.unlocked:
            self.skipTest("App nicht entsperrt")
        page = self.page
        STEP["name"] = "Erneut öffnen"
        started = time.monotonic()
        page.goto(f"{BASE}?pruefung={uuid.uuid4().hex[:8]}")
        page.locator(".stamp-date").first.wait_for(state="visible", timeout=120000)
        self.settle()
        REPORT["erneut_oeffnen_s"] = round(time.monotonic() - started, 1)
        REPORT["erneut_ohne_passphrase"] = page.get_by_role("heading", name="Zugangsschlüssel eingeben").count() == 0
        REPORT["service_worker_aktiv"] = bool(page.evaluate("navigator.serviceWorker && navigator.serviceWorker.controller !== null"))
        problems = self.problems()
        if not REPORT["erneut_ohne_passphrase"]:
            problems.append("fragt nach erneutem Öffnen wieder nach der Passphrase")
        REPORT["fehler"].extend(f"Erneut öffnen: {p}" for p in problems)
        self.assertEqual(problems, [])

    def test_5_no_console_errors(self) -> None:
        self.assertEqual(REPORT["konsolenfehler"], [], "Fehler in der Browser-Konsole")


if __name__ == "__main__":
    unittest.main()
