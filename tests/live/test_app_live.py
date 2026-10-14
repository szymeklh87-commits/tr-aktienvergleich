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
    ("Bericht 1–30", "/bericht", "table.rep-table tbody tr"),
    ("Top nach Zahlen", "/top", "ol.top-rows > li, .view .empty-body"),
    ("Volumen gestiegen", "/potenzial?liste=volumen", "ol.sig-rows > li, .view .empty-body, .notice-title"),
    ("Musterdepots", "/depots", ".dq-list > li"),
    ("Matrix", "/matrix", "td.gcell"),
    ("Häufigste Aktien", "/haeufig", "td.n"),
    ("Raster", "/raster", "li.tile"),
    ("Sieger nach Zeitraum", "/sieger", "div.tenw-cell"),
    ("Gewichtungen vergleichen", "/vergleich", "td.n"),
    ("Alle Aktien & Abdeckung", "/aktien", "li.row"),
    ("Watchlist", "/watchlist", "header.view-head"),
    # Im Zwischenstand steht die Regel nicht (nur Wochenschlusskurse) – dann gilt der Hinweis; offiziell: test_2d
    ("Umschichtungs-Regel", "/regel", "li.row, .empty-title"),
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

    def settle(self, timeout: float = 60.0, quiet: float = 1.0) -> float:
        """Warten, bis seit ``quiet`` Sekunden keine Ladeanzeige mehr zu sehen ist (Ansichten laden
        Teile nach, z. B. die Kursreihe der Einzelansicht). Rückgabe (ab 1.14): der Zeitpunkt, ab dem keine
        Ladeanzeige mehr zu sehen war – damit zählen die Zeiten im Bericht nur, was die App braucht, nicht die
        Ruhezeit dieser Prüfung."""
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
                return calm_since
            page.wait_for_timeout(50)
        return calm_since if calm_since is not None else time.monotonic()

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

    def wait_for_service_worker(self, timeout: float = 30.0) -> bool:
        """Bis der Service Worker die Seite übernommen hat (erster Besuch). Bis App 1.14 lädt die App die Seite in diesem
        Moment einmal neu – eine vorher eingegebene Passphrase ginge dabei verloren."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                if self.page.evaluate("Boolean(navigator.serviceWorker && navigator.serviceWorker.controller)"):
                    return True
            except Exception:  # Seite lädt gerade neu
                pass
            self.page.wait_for_timeout(100)
        return False

    def test_1_open_and_unlock(self) -> None:
        page = self.page
        # Erster Besuch: App-Hülle laden und den Service Worker übernehmen lassen – wie bei der installierten App auf dem
        # Handy. Gemessen wird danach das Öffnen wie beim zweiten Besuch.
        page.goto(f"{BASE}?pruefung={uuid.uuid4().hex[:8]}")
        page.wait_for_load_state("networkidle")
        REPORT["service_worker_beim_ersten_besuch"] = self.wait_for_service_worker()
        page.wait_for_load_state("networkidle")
        started = time.monotonic()
        page.goto(f"{BASE}?pruefung={uuid.uuid4().hex[:8]}")
        page.wait_for_load_state("domcontentloaded")
        stamp = uuid.uuid4().hex[:8]
        version = self.context.request.get(f"{BASE}version.json?x={stamp}")
        REPORT["version"] = version.json().get("version") if version.ok else None
        response = self.context.request.get(f"{BASE}data/status.json?x={stamp}")
        status = response.json() if response.ok else {}
        type(self).status = status
        intraday = status.get("zwischenstand") or {}
        REPORT["datenstand"] = {
            "neuester": status.get("latest_snapshot_id"),
            "neuester_vollstaendig": status.get("latest_complete_snapshot_id"),
            "offiziell": status.get("latest_official_snapshot_id"),
            "kursstand": status.get("last_price_session"),
            "letzter_lauf": (status.get("last_run") or {}).get("status"),
            "aufbewahrt": len(status.get("retained_snapshot_ids") or []),
            # nur Zählungen und Zeiten, keine Kurse
            "zwischenstand": {k: intraday.get(k) for k in ("snapshot_id", "stichtag", "aktien_mit_kurs", "kurse_bis_utc")}
            if intraday.get("snapshot_id") and intraday.get("snapshot_id") == status.get("latest_snapshot_id")
            else None,
        }
        locked = page.get_by_role("heading", name="Zugangsschlüssel eingeben")
        # Ab 1.14 ohne feste Wartezeit: Sperrbildschirm oder Startseite, je nachdem, was die App zeigt
        page.locator("#passphrase, .stamp-date").first.wait_for(state="visible", timeout=120000)
        REPORT["oeffnen_s"] = round(time.monotonic() - started, 1)
        REPORT["verschluesselt"] = bool(locked.count())
        unlock_started = time.monotonic()
        if locked.count():
            page.locator("#passphrase").fill(PASSPHRASE)
            unlock_started = time.monotonic()
            page.locator("button[type='submit']").click()
        page.locator(".stamp-date").first.wait_for(state="visible", timeout=120000)
        ready = self.settle()
        # entsperren_s: vom Tippen auf „Entsperren“ bis zur fertigen Startseite (Schlüssel prüfen, laden, anzeigen)
        REPORT["entsperren_s"] = round(ready - unlock_started, 1)
        REPORT["entsperren_und_laden_s"] = round(ready - started, 1)
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
                page.locator(selector).first.wait_for(state="attached", timeout=60000)
                ready = self.settle()
                entry["bereit_s"] = round(ready - started, 1)
                entry["elemente"] = page.locator(selector).count()
                if route == "/regel":
                    entry["zeilen"] = page.locator("li.row").count()
                    entry["hinweis_zwischenstand"] = page.get_by_text("Im Zwischenstand nicht gerechnet").count() > 0
                entry["probleme"] = self.problems()
            except Exception as exc:  # Ansicht festhalten, mit der nächsten weitermachen
                entry["probleme"] = [f"{type(exc).__name__}: {_safe(str(exc)).splitlines()[0][:200]}"]
            # ab 1.14: Zeit bis zur fertigen Ansicht (ohne die Ruhezeit dieser Prüfung); bei Fehlern die ganze Dauer
            entry["sekunden"] = entry.get("bereit_s", round(time.monotonic() - started, 1))
            REPORT["ansichten"][name] = entry
            if entry["probleme"]:
                failures.append(f"{name}: {'; '.join(entry['probleme'])}")
        rendite = REPORT["ansichten"].get("Rendite (alle 90 Zeiträume)", {})
        if rendite.get("elemente") not in (None, 90):
            failures.append(f"Rendite: {rendite.get('elemente')} statt 90 Zeiträume")
        ranking = REPORT["ansichten"].get("Ranking 30 Tage 60/40", {})
        if not ranking.get("elemente"):
            failures.append("Ranking 30 Tage: keine Plätze")
        regel = REPORT["ansichten"].get("Umschichtungs-Regel", {})
        if not regel.get("probleme"):
            if REPORT["datenstand"].get("zwischenstand"):
                if not regel.get("hinweis_zwischenstand"):
                    failures.append("Umschichtungs-Regel: im Zwischenstand fehlt der Hinweis „Im Zwischenstand nicht gerechnet“")
            elif not regel.get("zeilen"):
                failures.append("Umschichtungs-Regel: keine Zeilen im offiziellen Stand")
        REPORT["fehler"].extend(failures)
        self.assertEqual(failures, [])

    def test_2b_report_1_30(self) -> None:
        """Ab 1.8.1: Bericht 1–30 – vier Tabellen, Matrix mit 30 Zeilen, Häufigkeit; nur Zählungen im Bericht."""
        if not self.unlocked:
            self.skipTest("App nicht entsperrt")
        page = self.page
        STEP["name"] = "Bericht 1–30"
        started = time.monotonic()
        page.evaluate("location.hash = '/bericht'")
        self.settle()
        page.locator("table.rep-table").first.wait_for(state="attached", timeout=60000)
        page.locator("#bericht-haeufig ol.rep-freq > li, #bericht-haeufig .notice").first.wait_for(state="attached", timeout=60000)
        self.settle()
        stats = [re.sub(r"\s+", " ", t).strip() for t in page.locator(".rep-stats dd").all_inner_texts()]
        report = {
            "tabellen": page.locator("table.rep-table").count(),
            "zusammengefasste_zeilen": page.locator("tr.rep-gap").count(),
            "matrix_zeilen": page.locator("table.rep-matrix tbody tr").count(),
            "ranglisten_mit_spitzenreiter": stats[3] if len(stats) > 3 else None,
            "am_haeufigsten": page.locator(".rep-leaders ol.rep-freq > li").count(),
            "haeufigkeit_eintraege": page.locator("#bericht-haeufig ol.rep-freq > li").count(),
            "probleme": self.problems(),
            "sekunden": round(time.monotonic() - started, 1),
        }
        REPORT["bericht"] = report
        problems = list(report["probleme"])
        if report["tabellen"] != 4:
            problems.append(f"{report['tabellen']} statt 4 Tabellen")
        if report["matrix_zeilen"] != 30:
            problems.append(f"Matrix mit {report['matrix_zeilen']} statt 30 Zeilen")
        if not report["haeufigkeit_eintraege"]:
            problems.append("keine Häufigkeiten")
        REPORT["fehler"].extend(f"Bericht 1–30: {p}" for p in problems)
        self.assertEqual(problems, [])

    def test_2c_model_depots(self) -> None:
        """Ab 1.9: Musterdepots – Häufigkeitslisten, Depot „10 Sieger“ mit Beiträgen, 30 Fenster; nur Zählungen."""
        if not self.unlocked:
            self.skipTest("App nicht entsperrt")
        page = self.page
        STEP["name"] = "Musterdepots"
        started = time.monotonic()
        page.evaluate("location.hash = '/depots'")
        self.settle()
        page.locator(".dp-list > li, #depots-depot .notice").first.wait_for(state="attached", timeout=90000)
        self.settle()
        report = {
            "haeufigkeit_zeilen": page.locator(".dq-list > li").count(),
            "gemeinsam": page.locator(".dq-list > li.is-both").count(),
            "depots": page.get_by_role("radiogroup", name="Depot").get_by_role("radio").count(),
            "positionen": page.locator(".dp-list > li").count(),
            "fenster": page.locator("table.hz-table tbody tr").count(),
            "basis": page.get_by_role("radiogroup", name="Rechenbasis").locator("[aria-checked=true]").inner_text() if page.get_by_role("radiogroup", name="Rechenbasis").count() else None,
            "ohne_wechselkurse": page.get_by_text("enthält noch keine Wechselkurse").count() > 0,
            "probleme": self.problems(),
            "sekunden": round(time.monotonic() - started, 1),
        }
        REPORT["depots"] = report
        problems = list(report["probleme"])
        if not report["haeufigkeit_zeilen"]:
            problems.append("keine Häufigkeitsliste")
        if not report["positionen"]:
            problems.append("Depot „10 Sieger“ ohne Positionen")
        if report["fenster"] != 30:
            problems.append(f"{report['fenster']} statt 30 Fenster")
        REPORT["fehler"].extend(f"Musterdepots: {p}" for p in problems)
        self.assertEqual(problems, [])

    def test_2e_top3_by_numbers(self) -> None:
        """Ab 1.11: „Top 3 nach Zahlen“ ganz oben auf der Startseite – drei Zeilen mit Punkten (0–100) und vier Teilen,
        „Deine Aktien“ und die ganze Rangfolge. Nur Zählungen im Bericht (keine Namen, keine Punkte)."""
        if not self.unlocked:
            self.skipTest("App nicht entsperrt")
        page = self.page
        STEP["name"] = "Top 3 nach Zahlen"
        started = time.monotonic()
        page.evaluate("location.hash = '/'")
        self.settle()
        page.locator("section.top3 ol.top-rows > li, section.top3 .empty-body").first.wait_for(state="attached", timeout=90000)
        self.settle()
        rows = page.locator("section.top3 ol.top-rows > li")
        # Nur die drei Zeilen der Top 3 – „Deine Aktien“ darunter haben ab 1.12.1 dieselben Punkte-Felder
        points = [int(t) for t in page.locator("section.top3 ol.top-rows > li .top-points").all_inner_texts() if t.strip().isdigit()]
        first_class = page.locator(".view > *").first.get_attribute("class") or ""
        report = {
            "zuerst_auf_startseite": "top3" in first_class.split(),
            "zeilen": rows.count(),
            "punkte_0_bis_100": bool(points) and all(0 <= p <= 100 for p in points),
            "absteigend": points == sorted(points, reverse=True),
            "teile_je_zeile": [rows.nth(k).locator(".tpart").count() for k in range(rows.count())],
            "mit_boersenwert": page.locator("section.top3 ol.top-rows > li .row-fig-sub", has_text="Börsenwert").count(),
            "mit_warnzeichen": page.locator("section.top3 ol.top-rows > li .top-warn").count(),
            "mit_trefferquote": page.locator("section.top3 ol.top-rows > li .top-hit").count(),
            "eigene_aktien": page.locator("section.top3 .top-own > li").count(),
            "eigene_mit_platz": page.locator("section.top3 .top-own > li", has_text="Platz").count(),
        }
        top_started = time.monotonic()
        page.evaluate("location.hash = '/top'")
        page.locator("ol.top-rows > li, .view .empty-body").first.wait_for(state="attached", timeout=60000)
        report["top_seite_s"] = round(self.settle() - top_started, 1)
        report["rangfolge_erste_seite"] = page.locator("ol.top-rows > li").count()
        report["probleme"] = self.problems()
        report["sekunden"] = round(time.monotonic() - started, 1)
        REPORT["top3"] = report
        problems = list(report["probleme"])
        if not report["zuerst_auf_startseite"]:
            problems.append("Top 3 stehen nicht oben auf der Startseite")
        if report["zeilen"] != 3:
            problems.append(f"{report['zeilen']} statt 3 Zeilen")
        if not report["punkte_0_bis_100"] or not report["absteigend"]:
            problems.append("Punkte fehlen, liegen außerhalb 0–100 oder sind nicht absteigend")
        if any(n < 4 for n in report["teile_je_zeile"]):
            problems.append("nicht alle vier Teile der Punkte sichtbar")
        REPORT["fehler"].extend(f"Top 3 nach Zahlen: {p}" for p in problems)
        self.assertEqual(problems, [])

    def test_2d_rotation_in_official_stand(self) -> None:
        """Ab 1.9.2: Im Zwischenstand führt der Knopf zum Stand mit Schlusskursen (ab 1.12.1 „Schlusskurse 13.10. anzeigen“
        statt „Offiziellen Stand anzeigen“) zur Umschichtungs-Regel mit Zeilen;
        „Zwischenstand anzeigen“ führt zurück (die folgenden Prüfungen laufen wieder auf dem neuesten Stand)."""
        if not self.unlocked:
            self.skipTest("App nicht entsperrt")
        if not REPORT["datenstand"].get("zwischenstand"):
            self.skipTest("kein Zwischenstand aktiv – die Regel wurde in test_2 im offiziellen Stand geprüft")
        page = self.page
        STEP["name"] = "Umschichtungs-Regel (offizieller Stand)"
        started = time.monotonic()
        page.evaluate("location.hash = '/regel'")
        self.settle()
        page.locator(".empty").get_by_role("button", name=re.compile(r"^Schlusskurse \d\d\.\d\d\. anzeigen$")).click()
        rows = page.locator("li.row")
        rows.first.wait_for(state="attached", timeout=90000)
        self.settle()
        # Kopfzeile: „Kursstand …“ (offiziell) statt „Zwischenstand …“
        report = {
            "zeilen": rows.count(),
            "offiziell_aktiv": page.locator(".stand-chip").count() > 0 and page.locator(".stand-chip.stand-intraday").count() == 0,
            "probleme": self.problems(),
        }
        page.get_by_role("button", name="Zwischenstand anzeigen").first.click()
        deadline = time.monotonic() + 60
        back = False
        while time.monotonic() < deadline:
            if page.locator(".stand-chip.stand-intraday").count():
                back = True
                break
            page.wait_for_timeout(250)
        self.settle()
        report["zurueck_zum_zwischenstand"] = back
        report["sekunden"] = round(time.monotonic() - started, 1)
        REPORT["regel"] = report
        problems = list(report["probleme"])
        if not report["zeilen"]:
            problems.append("keine Zeilen im offiziellen Stand")
        if not report["offiziell_aktiv"]:
            problems.append("„Schlusskurse … anzeigen“ wechselt nicht in den Stand mit Schlusskursen")
        if not back:
            problems.append("„Zwischenstand anzeigen“ führt nicht zurück")
        REPORT["fehler"].extend(f"Umschichtungs-Regel: {p}" for p in problems)
        self.assertEqual(problems, [])

    def test_3_detail_of_first_stock(self) -> None:
        if not self.unlocked:
            self.skipTest("App nicht entsperrt")
        page = self.page
        STEP["name"] = "Einzelansicht"
        started = time.monotonic()
        page.evaluate("location.hash = '/ranking?h=30&w=0&p=native'")
        self.settle()
        clicked = time.monotonic()
        page.locator("ol.rows > li .row-link").first.click()
        deadline = time.monotonic() + 30
        while not page.evaluate("location.hash.startsWith('#/aktie/')") and time.monotonic() < deadline:
            page.wait_for_timeout(50)
        page.locator(".kv-row").first.wait_for(state="attached", timeout=60000)
        try:
            page.locator(".chart-surface svg").first.wait_for(state="attached", timeout=60000)
        except Exception:  # fehlende Grafik wird unten gemeldet
            pass
        ready = self.settle()
        detail = {
            # ab 1.14: vom Antippen der Zeile bis zur fertigen Einzelansicht mit Kursgrafik
            "bereit_s": round(ready - clicked, 1),
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
            "gesamtwertung": page.locator(".total-head").count() > 0,
            "daytrader_punkte": page.locator("ul.tchecks > li").count(),
            "probleme": self.problems(),
            "sekunden": round(time.monotonic() - started, 1),
        }
        REPORT["signale"] = signals | {k: v for k, v in (self.status or {}).get("signale", {}).items() if k in ("id", "version", "aktien", "mit_kursziel", "beide_gruen", "kurz_gruen", "lang_gruen", "gesamt_stark", "gesamt_mittel")}
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
        REPORT["erneut_oeffnen_s"] = round(self.settle() - started, 1)
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
