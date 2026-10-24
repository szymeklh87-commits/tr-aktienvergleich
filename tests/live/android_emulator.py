"""App im Android-Emulator prüfen (ab 1.17): echtes Chrome für Android in einem emulierten Gerät im Format des S25+.

Simons Auftrag vom 24.10.2026: „Teste … Android … soweit möglich. Unterscheide Gerätetest, Emulator und ungetestet.“
Das ist ein **Emulator-Test**, kein Gerätetest: Android 15 (Google-APIs-Abbild) mit dem dort mitgelieferten Chrome,
Bildschirm 1080 × 2340 bei 450 dpi (= 384 CSS-Pixel breit wie das S25+). Samsung Internet gibt es im Emulator nicht.
Die echte Installation prüft ab 1.17.1 ``android_install.py``, TalkBack ``android_talkback.py`` (im selben Workflow).

Geprüft wird der DEMO-Stand (synthetische Kurse, ohne Passphrase), den der Workflow aus demselben App-Build erzeugt und
über ``adb reverse`` als http://localhost:8000 bereitstellt (sicherer Ursprung, also mit Service Worker):

1. Start: Seite lädt, Kursstand sichtbar, CSS-Breite, Chrome-Version.
2. Installierbarkeit: Chrome meldet keine Installationshindernisse (``Page.getInstallabilityErrors``), Manifest vorhanden.
3. Offline: Service Worker steuert die Seite; Chrome ohne Server neu geöffnet zeigt den gespeicherten Stand mit Hinweis.
4. Darstellung: keine seitliche Verschiebung in zehn Ansichten – in normaler Schrift, mit Schriftgröße 130 % und quer.
   Wirkt die Systemschrift nicht auf die App, klären ab 1.18.1 Kontrollseiten (langer Absatz ohne und mit
   ``text-size-adjust: 100%`` wie in der App, kurze Texte in Karten) und ein langer Absatz mitten in der App, woran es
   liegt: Wächst der Absatz auf der Kontrollseite, in der App aber nicht, ist das ein Fehler der App (Lauf rot); wachsen
   lange Absätze überall und kurze Texte nirgends, vergrößert dieses Chrome nur längere Textblöcke (kein Fehler der App,
   aber nicht erfüllt).
5. Bildschirmtastatur: Suchfeld antippen – Tastatur offen, Feld sichtbar, Leiste unten verdeckt nichts. Öffnet sich die
   Tastatur nicht, steht das als „ohne Ergebnis“ im Hinweis (kein Fehler des Laufs).

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
            // ab 1.18.1 Gerätebreite: window.innerWidth wächst mit, wenn Chrome wegen einer zu breiten Seite herauszoomt
            geraet: document.documentElement.clientWidth,
            schrift: parseFloat(getComputedStyle(document.body).fontSize),
            leiste_links: parseFloat(getComputedStyle(document.querySelector('.shell') || document.body).paddingLeft) > 0,
            // ab 1.18: tatsächlich dargestellte Höhe einer Textzeile (Chrome kann Systemschrift als Text- oder Seitenzoom anwenden,
            // ohne dass sich die Schriftgröße in CSS ändert)
            textzeile: (() => { const el = document.querySelector('.stamp-date') || document.querySelector('h2') || document.body; return Math.round(el.getBoundingClientRect().height * 10) / 10; })(),
            zoom: window.visualViewport ? Math.round(window.visualViewport.scale * 100) / 100 : null,
        })"""
    )


CONTROL_TEXT = "Kontrolltext für die Systemschrift. " * 30
SHORT_ROW = "<div class='karte'><span class='k'>Kursstand Freitag</span><span>23. Oktober</span></div>"


def control_html(with_adjust: bool, short: bool = False) -> str:
    """Kontrollseite für die Systemschrift (ab 1.18.1) mit mobiler Viewport-Angabe: ein langer Absatz in 16 px – ohne oder mit
    ``text-size-adjust: 100%`` wie in der App – oder (``short``) nur kurze Texte in Karten (Flexbox), wie die App sie zeigt.
    Zeigt, ob Chrome die Systemschrift überhaupt auf Webseiten anwendet, ob die Angabe der App das verhindert und ob es an
    kurzen Textblöcken liegt."""
    adjust = "html{-webkit-text-size-adjust:100%;text-size-adjust:100%}" if with_adjust else ""
    head = (
        "<!doctype html><html lang='de'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1'>"
        f"<style>{adjust}body{{margin:8px;font-family:sans-serif}}p,.karte{{font-size:16px;line-height:1.25}}"
        ".karten{display:flex;flex-direction:column;gap:8px}.karte{display:flex;gap:8px;padding:8px;border:1px solid #999}</style></head>"
    )
    if short:
        return head + f"<body><div class='karten'>{SHORT_ROW * 20}</div><span id='z' style='font-size:16px;white-space:nowrap'>Zeile</span></body></html>"
    return head + f"<body><p id='k'>{CONTROL_TEXT}</p><span id='z' style='font-size:16px;white-space:nowrap'>Zeile</span></body></html>"


MEASURE_JS = """() => { const p = document.getElementById('k') || document.querySelector('.k'), z = document.getElementById('z');
    return {schrift: parseFloat(getComputedStyle(p).fontSize), zeile: Math.round(z.getBoundingClientRect().height * 10) / 10}; }"""

# Langer Absatz mitten in der App (Startseite) – zeigt, ob die Gestaltung der App das Vergrößern verhindert
INJECT_JS = """(text) => new Promise((resolve) => {
    const host = document.querySelector('main .view') || document.querySelector('main') || document.querySelector('.view') || document.body;
    const p = document.createElement('p'); p.textContent = text;
    const z = document.createElement('span'); z.textContent = 'Zeile'; z.style.whiteSpace = 'nowrap';
    host.appendChild(p); host.appendChild(z);
    requestAnimationFrame(() => requestAnimationFrame(() => {
        const out = {schrift: parseFloat(getComputedStyle(p).fontSize), zeile: Math.round(z.getBoundingClientRect().height * 10) / 10};
        p.remove(); z.remove(); resolve(out);
    }));
})"""


def control(page) -> dict:
    """Messungen zur Systemschrift: langer Absatz in der App (Startseite) und die drei Kontrollseiten."""
    out = {}
    page.goto(BASE + "#/", wait_until="domcontentloaded")
    page.wait_for_selector(".stamp-date", timeout=60000)
    page.wait_for_timeout(800)
    out["langer_absatz_in_der_app"] = page.evaluate(INJECT_JS, CONTROL_TEXT)
    for name, flag, short in (("ohne_text_size_adjust", False, False), ("mit_text_size_adjust", True, False), ("kurze_texte", False, True)):
        page.set_content(control_html(flag, short), wait_until="load")
        page.wait_for_timeout(500)
        out[name] = page.evaluate(MEASURE_JS)
    return out


def scaled(before: dict | None, after: dict | None) -> bool | None:
    """Größer geworden? Schrift um mehr als 5 % oder Textzeile um mehr als 10 % (Chrome kann als Text- oder Seitenzoom skalieren)."""
    if not before or not after:
        return None
    return (after.get("schrift") or 0) > (before.get("schrift") or 0) * 1.05 or (after.get("zeile") or 0) > (before.get("zeile") or 0) * 1.1


def font_scale_verdict(normal: dict, big: dict, control_before: dict | None, control_after: dict | None) -> tuple[str, str]:
    """Wirkt die Systemschrift 130 % auf die App – und wenn nicht, woran liegt es? Gemessen werden ein langer Absatz mitten in
    der App und Kontrollseiten (langer Absatz ohne und mit ``text-size-adjust``, kurze Texte in Karten):

    * „app_blockiert“ – ein langer Absatz wächst auf der Kontrollseite, in der App aber nicht: Die Gestaltung der App
      verhindert es (Fehler der App, Lauf rot).
    * „nur_lange_texte“ – ein langer Absatz wächst auch in der App, kurze Texte wachsen weder in der App noch auf der
      Kontrollseite: So wendet dieses Chrome die Systemschrift an (nur auf längere Textblöcke); die App verhindert nichts,
      folgt der Systemschrift hier aber nicht (nicht erfüllt, kein Fehler der App).
    * „chrome_ohne_wirkung“ – auch der lange Absatz der Kontrollseite wächst nicht."""
    app = (
        (big["schrift_px"] or 0) > (normal["schrift_px"] or 0) * 1.05
        or (big.get("textzeile_px") or 0) > (normal.get("textzeile_px") or 0) * 1.1
        or big["breite"] < normal["breite"] * 0.95
    )
    if app:
        return "wirkt", "wirkt auf die Seite – geprüft wie oben"
    before = control_before or {}
    after = control_after or {}
    plain = scaled(before.get("ohne_text_size_adjust"), after.get("ohne_text_size_adjust"))
    adjusted = scaled(before.get("mit_text_size_adjust"), after.get("mit_text_size_adjust"))
    short = scaled(before.get("kurze_texte"), after.get("kurze_texte"))
    inside = scaled(before.get("langer_absatz_in_der_app"), after.get("langer_absatz_in_der_app"))

    def sizes(name: str) -> str:
        b, a = before.get(name) or {}, after.get(name) or {}
        return f"Schrift {b.get('schrift')} → {a.get('schrift')} px, Textzeile {b.get('zeile')} → {a.get('zeile')} px"

    measured = (
        f"Kontrollseite mit langem Absatz ohne text-size-adjust: {sizes('ohne_text_size_adjust')}; mit text-size-adjust 100 %: {sizes('mit_text_size_adjust')}; "
        f"kurze Texte in Karten: {sizes('kurze_texte')}; langer Absatz in der App: {sizes('langer_absatz_in_der_app')}"
    )
    if plain and inside is False:
        return "app_blockiert", f"wirkt auf einen langen Absatz der Kontrollseite, aber nicht auf denselben Absatz in der App – FEHLER der App ({measured})"
    if plain and inside and short is False:
        return "nur_lange_texte", (
            "wirkt in diesem Chrome nur auf längere Textblöcke: ein langer Absatz wird größer – auf der Kontrollseite wie in der App –, kurze Texte "
            f"nicht, auch nicht auf der Kontrollseite; die App verhindert nichts, folgt der Systemschrift hier aber nicht ({measured})"
        )
    if plain:
        if inside and short:
            return "app_blockiert", f"wirkt auf kurze und lange Texte der Kontrollseiten und auf einen langen Absatz in der App, nicht aber auf die Texte der App – FEHLER der App ({measured})"
        return "unklar", f"wirkt auf die Kontrollseite, nicht auf die App; Ursache nicht eindeutig – große Schrift ist hier nicht geprüft ({measured})"
    if plain is False:
        return "chrome_ohne_wirkung", (
            f"wirkt in diesem Chrome auch auf eine Kontrollseite ohne text-size-adjust nicht ({sizes('ohne_text_size_adjust')}; mit: {sizes('mit_text_size_adjust')}) – "
            "Verhalten dieses Chrome, nicht der App; große Schrift ist hier nicht geprüft, nur in der Desktop-Emulation"
        )
    return "ohne_kontrolle", "wirkt in diesem Chrome nicht auf die Seite; die Kontrollseite ließ sich nicht messen – große Schrift ist hier nicht geprüft"


def visit_all(page, label: str) -> dict:
    rows = {}
    bad = []
    for route in ROUTES:
        page.goto(BASE + "#" + route, wait_until="domcontentloaded")
        page.wait_for_selector(".view, .notice", timeout=60000)
        page.wait_for_timeout(800)
        o = overflow(page)
        rows[route] = o
        if o["seite"] > o["geraet"] + 1 or o["breite"] > o["geraet"] + 1:
            bad.append(route)
    first = next(iter(rows.values()))
    RESULTS[label] = {"breite": first["breite"], "hoehe": first["hoehe"], "schrift_px": first["schrift"], "textzeile_px": first.get("textzeile"), "zoom": first.get("zoom"), "leiste_links": first["leiste_links"], "seitlich_verschoben": bad}
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
                page = pages[-1]
                # Jedes „am start“ öffnet in Chrome einen weiteren Tab. Geprüft wird nur ein Tab, und der muss vorne
                # liegen – sonst kommt ein echtes Antippen nicht in ihm an und die Tastatur öffnet sich nicht.
                for other in list(context.pages):
                    if other is not page:
                        try:
                            other.close()
                        except Exception:  # noqa: BLE001 - Tab schon weg
                            pass
                try:
                    page.bring_to_front()
                except Exception:  # noqa: BLE001
                    pass
                return browser, context, page
            browser.close()
        except Exception:  # noqa: BLE001 - Chrome startet noch oder baut den Tab neu auf
            pass
        if attempt in (5, 15, 25):
            adb("shell", "am", "start", "-n", "com.android.chrome/com.google.android.apps.chrome.Main", "-d", BASE + "#" + route, check=False)
        time.sleep(2)
    raise RuntimeError("Chrome war über die Entwicklerschnittstelle nicht erreichbar")


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
        RESULTS["kontrolle_schrift_100"] = control(page)
        # Systemschrift 130 %: ab 1.18.1 danach Chrome ganz neu starten – bis dahin wurde nur neu verbunden, und Chrome
        # übernahm die geänderte Einstellung nicht (Schrift, Textzeile und Breite blieben gleich)
        adb("shell", "settings", "put", "system", "font_scale", "1.3")
        RESULTS["systemschrift_einstellung"] = adb("shell", "settings", "get", "system", "font_scale")
        browser, context, page = restart_chrome(p, browser, "/")
        visit_all(page, "schrift_130")
        RESULTS["kontrolle_schrift_130"] = control(page)
        adb("shell", "settings", "put", "system", "font_scale", "1.0")
        browser, context, page = restart_chrome(p, browser, "/")
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
        # Antippen über die Entwicklerschnittstelle (Berührung wie mit dem Finger). Ein echtes Antippen per adb an der
        # gemessenen Stelle setzte am 24.10.2026 den Fokus nicht ins Suchfeld bzw. das Suchfeld war danach nicht mehr
        # auffindbar – deshalb nicht mehr verwendet.
        how = "Entwicklerschnittstelle"
        try:
            search.tap(timeout=10000)
        except Exception:  # noqa: BLE001 - ohne Touch-Unterstützung der Verbindung: Klick
            how = "Klick über die Entwicklerschnittstelle"
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
        lines.append(f"{label}: {r['breite']} × {r['hoehe']} CSS-Pixel, Schrift {r['schrift_px']} px, Textzeile {r.get('textzeile_px')} px, Zoom {r.get('zoom')}, Leiste links {r['leiste_links']}, seitlich verschoben: {r['seitlich_verschoben'] or 'keine'} (von {len(ROUTES)} Ansichten)")
    normal, big = RESULTS["hochformat"], RESULTS["schrift_130"]
    # ab 1.18 ausdrücklich: Wirkt die Systemschrift 130 % in diesem Chrome überhaupt auf die Seite (Schrift, Textzeile oder Breite)?
    # ab 1.18.1 mit Kontrollseite ohne und mit text-size-adjust: Liegt es an Chrome oder an der App?
    font_result, font_text = font_scale_verdict(normal, big, RESULTS.get("kontrolle_schrift_100"), RESULTS.get("kontrolle_schrift_130"))
    RESULTS["systemschrift_urteil"] = font_result
    lines.append(f"Systemschrift 130 % (Einstellung laut Android {RESULTS.get('systemschrift_einstellung') or '–'}, Chrome danach neu gestartet): {font_text}")
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
        or RESULTS.get("systemschrift_urteil") == "app_blockiert"
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
