"""App im Android-Emulator prüfen (ab 1.17): echtes Chrome für Android in einem emulierten Gerät im Format des S25+.

Simons Auftrag vom 24.10.2026: „Teste … Android … soweit möglich. Unterscheide Gerätetest, Emulator und ungetestet.“
Das ist ein **Emulator-Test**, kein Gerätetest: Android 15 (Google-APIs-Abbild) mit dem dort mitgelieferten Chrome,
Bildschirm 1080 × 2340 bei 450 dpi (= 384 CSS-Pixel breit wie das S25+). Samsung Internet und TalkBack gibt es im
Emulator nicht – sie bleiben ungetestet.

Geprüft wird der DEMO-Stand (synthetische Kurse, ohne Passphrase), den der Workflow aus demselben App-Build erzeugt und
über ``adb reverse`` als http://localhost:8000 bereitstellt (sicherer Ursprung, also mit Service Worker):

1. Start: Seite lädt, Kursstand sichtbar, CSS-Breite, Chrome-Version.
2. Installierbarkeit: Chrome meldet keine Installationshindernisse (``Page.getInstallabilityErrors``), Manifest vorhanden.
3. Offline: Service Worker steuert die Seite; ohne Server zeigt die App den gespeicherten Stand mit Hinweis.
4. Darstellung: keine seitliche Verschiebung in zehn Ansichten – in normaler Schrift, mit Schriftgröße 130 % und quer.
5. Bildschirmtastatur: Suchfeld antippen – Tastatur offen, Feld sichtbar, Leiste unten verdeckt nichts.

Ausgegeben werden nur Zählwerte und Ja/Nein (DEMO-Daten, keine echten Kurse). Aufruf im Workflow „Android-Emulator
prüfen“; lokal nur mit laufendem Emulator und ``adb``.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROUTES = ["/", "/ranking?h=30&w=60", "/rendite", "/matrix", "/bericht", "/depots", "/aktien", "/top", "/status", "/hilfe"]
BASE = "http://localhost:8000/"
RESULTS: dict = {}


def adb(*args: str, check: bool = True) -> str:
    out = subprocess.run(["adb", *args], check=check, capture_output=True, text=True, timeout=120)
    return out.stdout.strip()


def notice(title: str, lines: list[str], level: str = "notice") -> None:
    body = "%0A".join(line.replace("%", "%25").replace("\n", " ") for line in lines)
    print(f"::{level} title={title}::{body}")


def overflow(page) -> dict:
    return page.evaluate(
        """() => ({
            breite: window.innerWidth,
            hoehe: window.innerHeight,
            seite: document.documentElement.scrollWidth,
            schrift: parseFloat(getComputedStyle(document.body).fontSize),
            leiste_links: parseFloat(getComputedStyle(document.querySelector('.shell') || document.body).paddingLeft) > 0,
        })"""
    )


def visit_all(page, label: str) -> dict:
    rows = {}
    bad = []
    for route in ROUTES:
        page.goto(BASE + "#" + route, wait_until="domcontentloaded")
        page.wait_for_selector(".view, .notice", timeout=60000)
        page.wait_for_timeout(800)
        o = overflow(page)
        rows[route] = o
        if o["seite"] > o["breite"] + 1:
            bad.append(route)
    first = next(iter(rows.values()))
    RESULTS[label] = {"breite": first["breite"], "hoehe": first["hoehe"], "schrift_px": first["schrift"], "leiste_links": first["leiste_links"], "seitlich_verschoben": bad}
    return RESULTS[label]


def main() -> int:
    from playwright.sync_api import sync_playwright

    adb("forward", "tcp:9222", "localabstract:chrome_devtools_remote")
    with sync_playwright() as p:
        browser = None
        for _ in range(30):
            try:
                browser = p.chromium.connect_over_cdp("http://localhost:9222")
                break
            except Exception:  # noqa: BLE001 - Chrome startet noch
                time.sleep(2)
        if browser is None:
            notice("Android-Emulator", ["Chrome war über die Entwicklerschnittstelle nicht erreichbar"], "error")
            return 1
        context = browser.contexts[0]
        page = context.pages[0] if context.pages else context.new_page()
        version = browser.version
        page.goto(BASE + "#/", wait_until="domcontentloaded")
        page.wait_for_selector(".stamp-date", timeout=120000)
        RESULTS["start"] = {"chrome": version.split(".")[0], "kursstand_sichtbar": page.locator(".stamp-date").count() > 0}

        # Installierbarkeit (Chrome für Android selbst)
        cdp = context.new_cdp_session(page)
        errors = cdp.send("Page.getInstallabilityErrors").get("installabilityErrors", [])
        manifest = cdp.send("Page.getAppManifest")
        RESULTS["installierbar"] = {"hindernisse": [e.get("errorId") for e in errors], "manifest": bool(manifest.get("url")), "manifest_fehler": len(manifest.get("errors", []))}

        # Service Worker und Offline
        page.evaluate("navigator.serviceWorker.ready.then(() => true)")
        page.reload(wait_until="domcontentloaded")
        page.wait_for_function("!!navigator.serviceWorker.controller", timeout=60000)
        page.goto(BASE + "#/ranking?h=30&w=60", wait_until="domcontentloaded")
        page.wait_for_selector("ol.rows > li", timeout=60000)
        adb("reverse", "--remove", "tcp:8000")
        page.reload(wait_until="domcontentloaded")
        try:
            page.wait_for_selector("text=Offline – gespeicherter Stand", timeout=30000)
            offline_ok = page.locator("ol.rows > li").count() > 0
        except Exception:  # noqa: BLE001
            offline_ok = False
        adb("reverse", "tcp:8000", "tcp:8000")
        RESULTS["offline"] = {"service_worker": True, "gespeicherter_stand_mit_hinweis": offline_ok}

        # Darstellung: normal, große Schrift, quer
        visit_all(page, "hochformat")
        adb("shell", "settings", "put", "system", "font_scale", "1.3")
        page.wait_for_timeout(1500)
        page.reload(wait_until="domcontentloaded")
        visit_all(page, "schrift_130")
        adb("shell", "settings", "put", "system", "font_scale", "1.0")
        adb("shell", "settings", "put", "system", "accelerometer_rotation", "0")
        adb("shell", "settings", "put", "system", "user_rotation", "1")
        page.wait_for_timeout(2500)
        visit_all(page, "querformat")
        adb("shell", "settings", "put", "system", "user_rotation", "0")
        page.wait_for_timeout(2500)

        # Bildschirmtastatur
        page.goto(BASE + "#/aktien", wait_until="domcontentloaded")
        search = page.get_by_role("searchbox", name="Name, Ticker oder ISIN")
        search.wait_for(timeout=60000)
        before = page.evaluate("({h: window.innerHeight, v: window.visualViewport ? window.visualViewport.height : null, dpr: window.devicePixelRatio})")
        try:
            search.tap(timeout=10000)  # Antippen wie mit dem Finger (Chrome öffnet dann die Bildschirmtastatur)
        except Exception:  # noqa: BLE001 - ohne Touch-Unterstützung der Verbindung: Klick
            search.click(timeout=10000)
        page.wait_for_timeout(2500)
        after = page.evaluate(
            """() => {
                const el = document.activeElement;
                const r = el ? el.getBoundingClientRect() : null;
                const vv = window.visualViewport;
                return {
                    fokus_im_suchfeld: !!el && el.getAttribute('type') === 'search',
                    h: window.innerHeight,
                    v: vv ? vv.height : null,
                    feld_sichtbar: !!r && vv ? r.bottom <= vv.offsetTop + vv.height && r.top >= vv.offsetTop : null,
                    leiste_ausgeblendet: document.documentElement.dataset.tastatur === 'offen',
                };
            }"""
        )
        ime = "mInputShown=true" in adb("shell", "dumpsys", "input_method", check=False)
        RESULTS["tastatur"] = {"vorher": before, "nachher": after, "tastatur_offen": ime}
        browser.close()

    lines = [
        f"Chrome {RESULTS['start']['chrome']} im Emulator (Android 15, 1080 × 2340, 450 dpi); Kursstand sichtbar: {RESULTS['start']['kursstand_sichtbar']}",
        f"installierbar: Hindernisse {RESULTS['installierbar']['hindernisse'] or 'keine'}, Manifest {RESULTS['installierbar']['manifest']}, Manifest-Fehler {RESULTS['installierbar']['manifest_fehler']}",
        f"offline: gespeicherter Stand mit Hinweis {RESULTS['offline']['gespeicherter_stand_mit_hinweis']}",
    ]
    for label in ("hochformat", "schrift_130", "querformat"):
        r = RESULTS[label]
        lines.append(f"{label}: {r['breite']} × {r['hoehe']} CSS-Pixel, Schrift {r['schrift_px']} px, Leiste links {r['leiste_links']}, seitlich verschoben: {r['seitlich_verschoben'] or 'keine'} (von {len(ROUTES)} Ansichten)")
    t = RESULTS["tastatur"]
    lines.append(
        f"Tastatur offen {t['tastatur_offen']}, Fokus im Suchfeld {t['nachher']['fokus_im_suchfeld']}, Feld sichtbar {t['nachher']['feld_sichtbar']}, "
        f"Seitenhöhe {t['vorher']['h']} → {t['nachher']['h']}, sichtbare Höhe {t['vorher']['v']} → {t['nachher']['v']}, Leiste ausgeblendet {t['nachher']['leiste_ausgeblendet']}"
    )
    notice("Android-Emulator (nur DEMO-Daten)", lines)
    Path("android-ergebnis.json").write_text(json.dumps(RESULTS, indent=2, ensure_ascii=False), encoding="utf-8")
    failed = (
        not RESULTS["start"]["kursstand_sichtbar"]
        or RESULTS["installierbar"]["hindernisse"]
        or not RESULTS["offline"]["gespeicherter_stand_mit_hinweis"]
        or any(RESULTS[label]["seitlich_verschoben"] for label in ("hochformat", "schrift_130", "querformat"))
    )
    return 1 if failed else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001 - Abbruchgrund als Hinweis (Fehlerart und eigene Zeilen, keine Inhalte)
        import traceback

        frames = [f"{Path(f.filename).name}:{f.lineno}" for f in traceback.extract_tb(exc.__traceback__) if "android_emulator" in f.filename]
        first_line = str(exc).splitlines()[0][:200] if str(exc) else ""
        print(f"::error title=Android-Emulator abgebrochen::{type(exc).__name__} bei {' > '.join(frames[-4:])}: {first_line}")
        if RESULTS:
            print("::notice title=Android-Emulator Teilergebnis::" + json.dumps(RESULTS, ensure_ascii=False)[:1500])
        raise
