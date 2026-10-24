"""App im Android-Emulator prüfen (ab 1.17): echtes Chrome für Android in einem emulierten Gerät im Format des S25+.

Simons Auftrag vom 24.10.2026: „Teste … Android … soweit möglich. Unterscheide Gerätetest, Emulator und ungetestet.“
Das ist ein **Emulator-Test**, kein Gerätetest: Android 15 (Google-APIs-Abbild) mit dem dort mitgelieferten Chrome,
Bildschirm 1080 × 2340 bei 450 dpi (= 384 CSS-Pixel breit wie das S25+). Samsung Internet gibt es im Emulator nicht;
TalkBack ist im Abbild vorhanden, wird hier aber nicht benutzt – beides bleibt ungetestet.

Geprüft wird der DEMO-Stand (synthetische Kurse, ohne Passphrase), den der Workflow aus demselben App-Build erzeugt und
über ``adb reverse`` als http://localhost:8000 bereitstellt (sicherer Ursprung, also mit Service Worker):

1. Start: Seite lädt, Kursstand sichtbar, CSS-Breite, Chrome-Version.
2. Installierbarkeit: Chrome meldet keine Installationshindernisse (``Page.getInstallabilityErrors``), Manifest vorhanden.
3. Offline: Service Worker steuert die Seite; Chrome ohne Server neu geöffnet zeigt den gespeicherten Stand mit Hinweis.
4. Darstellung: keine seitliche Verschiebung in zehn Ansichten – in normaler Schrift, mit Schriftgröße 130 % und quer.
5. Bildschirmtastatur: Suchfeld wie mit dem Finger antippen (``adb shell input tap``) – Tastatur offen, Feld
   sichtbar, Leiste unten verdeckt nichts.

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


def connect(p, route: str = "/"):
    """Mit Chrome im Emulator verbinden und den Tab der App holen. Nach einem Konfigurationswechsel (Schriftgröße,
    Drehen) baut Chrome den Tab neu auf – dann öffnet ``am start`` die Adresse erneut und die Verbindung wird neu
    aufgebaut."""
    adb("forward", "tcp:9222", "localabstract:chrome_devtools_remote")
    for attempt in range(40):
        try:
            browser = p.chromium.connect_over_cdp("http://localhost:9222")
            context = browser.contexts[0]
            pages = [pg for pg in context.pages if pg.url.startswith(BASE)] or context.pages
            if pages:
                return browser, context, pages[-1]
            browser.close()
        except Exception:  # noqa: BLE001 - Chrome startet noch oder baut den Tab neu auf
            pass
        if attempt in (5, 15, 25):
            adb("shell", "am", "start", "-n", "com.android.chrome/com.google.android.apps.chrome.Main", "-d", BASE + "#" + route, check=False)
        time.sleep(2)
    raise RuntimeError("Chrome war über die Entwicklerschnittstelle nicht erreichbar")


def tap_like_a_finger(page, locator) -> str:
    """Ein Element wie mit dem Finger antippen: echtes Antippen über ``adb shell input tap``. Ein über die
    Entwicklerschnittstelle nachgestelltes Antippen öffnet die Bildschirmtastatur nicht zuverlässig (am 24.10.2026
    einmal ja, zweimal nein). Wo die Seite auf dem Bildschirm liegt, misst vorher ein Probe-Antippen in der
    Bildschirmmitte, das die Seite abfängt (es bewirkt nichts): Bildschirmpunkt minus Seitenkoordinate mal
    Pixeldichte. Rückgabe ``ok`` oder der Grund, warum es nicht ging."""
    import re

    # Das Probe-Antippen selbst bewirkt nichts: Berührung und Klick werden abgefangen, bevor die App sie sieht
    page.evaluate(
        """() => {
            window.__probe = null;
            const stop = (e) => { e.preventDefault(); e.stopImmediatePropagation(); };
            const start = (e) => {
                const t = e.touches[0];
                window.__probe = { x: t.clientX, y: t.clientY };
                stop(e);
            };
            const types = ['touchstart', 'touchend', 'mousedown', 'mouseup', 'click'];
            for (const type of types) window.addEventListener(type, type === 'touchstart' ? start : stop, { capture: true, passive: false });
            window.__unprobe = () => {
                for (const type of types) window.removeEventListener(type, type === 'touchstart' ? start : stop, { capture: true });
            };
        }"""
    )
    sizes = re.findall(r"(\d+)x(\d+)", adb("shell", "wm", "size", check=False))
    if not sizes:
        return "Bildschirmgröße unbekannt"
    width, height = map(int, sizes[-1])
    probe_x, probe_y = width // 2, height // 2
    adb("shell", "input", "tap", str(probe_x), str(probe_y))
    page.wait_for_timeout(1000)
    probe = page.evaluate("window.__probe")
    page.evaluate("window.__unprobe && window.__unprobe()")
    box = locator.bounding_box()
    if not probe:
        return "Probe-Antippen kam nicht in der Seite an"
    if not box:
        return "Suchfeld ohne Lage"
    dpr = float(page.evaluate("window.devicePixelRatio"))
    x = round(probe_x - probe["x"] * dpr + (box["x"] + box["width"] / 2) * dpr)
    y = round(probe_y - probe["y"] * dpr + (box["y"] + box["height"] / 2) * dpr)
    if not (0 <= x < width and 0 <= y < height):
        return f"Ziel außerhalb des Bildschirms ({x}, {y})"
    adb("shell", "input", "tap", str(x), str(y))
    return "ok"


def restart_chrome(p, browser, route: str):
    """Chrome ganz beenden und neu öffnen – wie die App neu starten, ohne offene Verbindungen von vorher."""
    try:
        browser.close()
    except Exception:  # noqa: BLE001
        pass
    adb("shell", "am", "force-stop", "com.android.chrome", check=False)
    time.sleep(2)
    adb("shell", "am", "start", "-n", "com.android.chrome/com.google.android.apps.chrome.Main", "-d", BASE + "#" + route, check=False)
    time.sleep(4)
    return connect(p, route)


def reconnect(p, browser, route: str):
    try:
        browser.close()  # trennt nur die Verbindung, Chrome läuft weiter
    except Exception:  # noqa: BLE001
        pass
    time.sleep(3)
    adb("shell", "am", "start", "-n", "com.android.chrome/com.google.android.apps.chrome.Main", "-d", BASE + "#" + route, check=False)
    time.sleep(3)
    return connect(p, route)


def main() -> int:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser, context, page = connect(p)
        version = browser.version
        page.goto(BASE + "#/", wait_until="domcontentloaded")
        page.wait_for_selector(".stamp-date", timeout=120000)
        RESULTS["start"] = {"chrome": version.split(".")[0], "kursstand_sichtbar": page.locator(".stamp-date").count() > 0}
        # Was das Abbild mitbringt (Samsung Internet und TalkBack lassen sich nur prüfen, wenn sie da sind)
        packages = adb("shell", "pm", "list", "packages", check=False)
        RESULTS["pakete"] = {
            "samsung_internet": "package:com.sec.android.app.sbrowser" in packages,
            "talkback": "package:com.google.android.marvin.talkback" in packages,
            "play_dienste": "package:com.google.android.gms" in packages,
            "play_store": "package:com.android.vending" in packages,
        }

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
        # Ohne Netz neu öffnen: Server-Weiterleitung weg, Chrome ganz beenden und neu starten – wie die App ohne Netz
        # öffnen. (Bis dahin wurde nur neu geladen; das scheiterte am 24.10.2026 einmal ohne sichtbaren Grund.)
        adb("reverse", "--remove", "tcp:8000")
        browser, context, page = restart_chrome(p, browser, "/ranking?h=30&w=60")
        try:
            page.wait_for_selector("text=Offline – gespeicherter Stand", timeout=45000)
            page.wait_for_selector("ol.rows > li", timeout=15000)
            offline_ok = page.locator("ol.rows > li").count() > 0
        except Exception:  # noqa: BLE001
            offline_ok = False
        adb("reverse", "tcp:8000", "tcp:8000")
        RESULTS["offline"] = {"service_worker": True, "gespeicherter_stand_mit_hinweis": offline_ok, "art": "Neustart ohne Netz"}
        browser, context, page = reconnect(p, browser, "/")

        # Darstellung: normal, große Schrift, quer (nach jedem Wechsel neu verbinden)
        visit_all(page, "hochformat")
        adb("shell", "settings", "put", "system", "font_scale", "1.3")
        browser, context, page = reconnect(p, browser, "/")
        visit_all(page, "schrift_130")
        adb("shell", "settings", "put", "system", "font_scale", "1.0")
        browser, context, page = reconnect(p, browser, "/")
        adb("shell", "settings", "put", "system", "accelerometer_rotation", "0")
        adb("shell", "settings", "put", "system", "user_rotation", "1")
        browser, context, page = reconnect(p, browser, "/")
        visit_all(page, "querformat")
        adb("shell", "settings", "put", "system", "user_rotation", "0")
        browser, context, page = reconnect(p, browser, "/aktien")

        # Bildschirmtastatur
        page.goto(BASE + "#/aktien", wait_until="domcontentloaded")
        search = page.get_by_role("searchbox", name="Name, Ticker oder ISIN")
        search.wait_for(timeout=60000)
        search.scroll_into_view_if_needed()
        page.wait_for_timeout(1500)
        before = page.evaluate("({h: window.innerHeight, v: window.visualViewport ? window.visualViewport.height : null, dpr: window.devicePixelRatio})")
        how = "adb"
        why = tap_like_a_finger(page, search)
        if why != "ok":
            how = f"Entwicklerschnittstelle (adb: {why})"
            try:
                search.tap(timeout=10000)
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
        RESULTS["tastatur"] = {"vorher": before, "nachher": after, "tastatur_offen": ime, "angetippt_ueber": how}
        browser.close()

    lines = [
        f"Chrome {RESULTS['start']['chrome']} im Emulator (Android 15, 1080 × 2340, 450 dpi); Kursstand sichtbar: {RESULTS['start']['kursstand_sichtbar']}",
        "Im Abbild vorhanden: " + ", ".join(f"{name} {'ja' if there else 'nein'}" for name, there in RESULTS["pakete"].items()),
        f"installierbar: Hindernisse {RESULTS['installierbar']['hindernisse'] or 'keine'}, Manifest {RESULTS['installierbar']['manifest']}, Manifest-Fehler {RESULTS['installierbar']['manifest_fehler']}",
        f"offline ({RESULTS['offline']['art']}): gespeicherter Stand mit Hinweis {RESULTS['offline']['gespeicherter_stand_mit_hinweis']}",
    ]
    for label in ("hochformat", "schrift_130", "querformat"):
        r = RESULTS[label]
        lines.append(f"{label}: {r['breite']} × {r['hoehe']} CSS-Pixel, Schrift {r['schrift_px']} px, Leiste links {r['leiste_links']}, seitlich verschoben: {r['seitlich_verschoben'] or 'keine'} (von {len(ROUTES)} Ansichten)")
    t = RESULTS["tastatur"]
    if not t["tastatur_offen"]:
        lines.append(f"Bildschirmtastatur hat sich nach dem Antippen (über {t['angetippt_ueber']}) nicht geöffnet – Tastatur-Prüfung ohne Ergebnis")
    lines.append(
        f"Suchfeld angetippt über {t['angetippt_ueber']}: Tastatur offen {t['tastatur_offen']}, Fokus im Suchfeld {t['nachher']['fokus_im_suchfeld']}, Feld sichtbar {t['nachher']['feld_sichtbar']}, "
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
