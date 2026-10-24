"""Echte Daten in Chrome für Android im Emulator (ab 1.18).

Simons Auftrag vom 24.10.2026, 19:07 Uhr: „Erledige alle zusätzlich möglichen Browser- und Emulatorprüfungen. Echtes
S25+, Samsung Internet und TalkBack-Gesten nur mit tatsächlichen Nachweisen als bestanden werten.“

Bis 1.18 prüfte der Emulator nur den DEMO-Stand (ohne Passphrase, Workflow „Android-Emulator prüfen“) und die echten Daten
nur Chromium unter Linux (Job „pruefen“). Dieses Skript verbindet beides: Es öffnet die **veröffentlichte Website** in
**Chrome für Android** im Emulator (Android 15, Format des S25+), entsperrt sie mit der Passphrase, ruft alle 24 Ansichten
mit den echten Daten auf und startet Chrome danach **ohne Netz** neu (gespeicherter Stand, ohne erneute Passphrase).

Die Passphrase kommt aus dem Secret ``DATA_PASSPHRASE``, wird nur über die Entwicklerschnittstelle in das Feld der App
geschrieben (nicht über ``adb``) und nie ausgegeben; der Emulator wird nach dem Lauf verworfen. Ausgegeben werden nur
Version, Kursstand, Zählwerte, Zeiten und Ja/Nein – keine Kurse, Namen oder ISINs.

Grenzen (ehrlich benannt): Emulator, kein Gerät; Chrome des Abbilds (nicht die Version auf dem S25+), ohne Google-Konto;
Samsung Internet gibt es im Abbild nicht; TalkBack-Gesten werden nicht bedient. Aufruf im Workflow „App mit echten Daten
prüfen“ mit „Android“ = an (Job „android“).
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from android_install import CHROME, SITE, adb, network, notice  # noqa: E402
from test_app_live import ERROR_TEXTS, VIEWS  # noqa: E402 - dieselben Ansichten wie die Live-Prüfung in Chromium

PASSPHRASE = os.environ.get("DATA_PASSPHRASE", "")
RESULTS: dict = {"ansichten": {}, "konsolenfehler": [], "fehlgeschlagene_abrufe": []}
STEP = {"name": "Start"}
TABS: dict[str, list[str]] = {}  # je Verbindung: die Tabs, die Chrome offen hatte (nur Seiten der App)

# wie test_app_live.problems: Fehlertexte der App (ohne die Hilfe-Abschnitte, die sie erklären), Ladeanzeige, Überbreite
PROBLEMS_JS = """(texts) => {
    const root = document.querySelector('main') || document.body;
    const copy = root.cloneNode(true);
    ['hilfe-probleme', 'hilfe-fragen', 'hilfe-begriffe'].forEach((id) => copy.querySelectorAll(`section[aria-labelledby="${id}"]`).forEach((el) => el.remove()));
    const text = copy.textContent || '';
    const found = texts.filter((t) => text.includes(t));
    if (document.querySelector('.loading')) found.push('Ladeanzeige noch sichtbar');
    const over = document.documentElement.scrollWidth - window.innerWidth;
    if (over > 1) found.push(`Seite ${over} px breiter als der Bildschirm`);
    return found;
}"""


def safe(text: str) -> str:
    """Meldungen ohne Passphrase (doppelte Sicherung neben der Maskierung durch GitHub)."""
    return text.replace(PASSPHRASE, "***") if PASSPHRASE else text


def open_chrome(query: str = "") -> None:
    adb("shell", "am", "force-stop", CHROME)
    time.sleep(2)
    adb("shell", "am", "start", "-n", f"{CHROME}/com.google.android.apps.chrome.Main", "-d", SITE + query + "#/")
    time.sleep(6)


def tab_label(url: str, marker: str | None = None) -> str:
    """Tab ohne Inhalte beschreiben: Seite der App (nur der Teil nach #) und ob die Adresse die Marke des Aufrufs trägt."""
    if not url.startswith(SITE):
        return "andere Adresse"
    route = url.split("#", 1)[1] if "#" in url else "/"
    return f"#{route or '/'}" + (" (dieser Aufruf)" if marker and marker in url else "")


def connect(p, timeout_s: int = 120, marker: str | None = None):
    """Mit Chrome verbinden und den Tab der App holen (nur dieser bleibt offen und liegt vorne).

    Mit ``marker`` (ab 1.18) nur den Tab, dessen Adresse die Marke dieses Aufrufs trägt: Nach ``am force-stop`` stellt
    Chrome beim Neustart auch den Tab der letzten Sitzung wieder her. Bis dahin nahm die Prüfung den letzten Tab der
    Liste – im Lauf vom 24.10.2026, 19:36–19:41 Uhr wartete sie so 90 s auf die Startseite, ohne zu belegen, welchen Tab sie
    vor sich hatte. Welche Tabs Chrome geöffnet hatte, steht seitdem im Ergebnis (nur Seiten der App, keine Inhalte)."""
    adb("forward", "tcp:9222", "localabstract:chrome_devtools_remote")
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            browser = p.chromium.connect_over_cdp("http://localhost:9222")
        except Exception:  # noqa: BLE001 - Chrome startet noch
            time.sleep(2)
            continue
        for context in browser.contexts:
            pages = [pg for pg in context.pages if pg.url.startswith(SITE)]
            chosen = [pg for pg in pages if marker in pg.url] if marker else pages
            if chosen:
                page = chosen[-1]
                TABS[marker or "ohne Marke"] = [tab_label(pg.url, marker) for pg in context.pages]
                for other in list(context.pages):
                    if other is not page:
                        try:
                            other.close()
                        except Exception:  # noqa: BLE001
                            pass
                try:
                    page.bring_to_front()
                except Exception:  # noqa: BLE001
                    pass
                page.set_default_timeout(90000)
                return browser, page
        try:
            browser.close()
        except Exception:  # noqa: BLE001
            pass
        time.sleep(2)
    raise RuntimeError("Chrome mit der App war über die Entwicklerschnittstelle nicht erreichbar")


# Zustand der Seite ohne Inhalte: Sperrbildschirm, Kursstand-Kopf, Ladeanzeige, Titel der Hinweise der App (feste Texte
# wie „Offline – gespeicherter Stand“ oder „Keine Internetverbindung“), Netz laut Browser, Service Worker, Seite der App
STATE_JS = """() => {
    const visible = (sel) => [...document.querySelectorAll(sel)].some((el) => el.offsetParent !== null);
    return {
        sperrbildschirm: !!document.querySelector('#passphrase'),
        kursstand: visible('.stamp-date'),
        ladeanzeige: !!document.querySelector('.loading'),
        hinweise: [...document.querySelectorAll('.notice-title')].map((el) => (el.textContent || '').trim().slice(0, 60)).slice(0, 6),
        online: navigator.onLine,
        service_worker: !!(navigator.serviceWorker && navigator.serviceWorker.controller),
        seite: location.hash || '#/',
        geladen: document.readyState,
    };
}"""


def offline_verdict(off: dict) -> tuple[bool, list[str]]:
    """Neustart ohne Netz bestanden? Gründe für „nein“ ohne Inhalte. Verlangt: Seite vom Service Worker, Browser offline,
    keine erneute Passphrase, Hinweis „Offline – gespeicherter Stand“ und die Rangliste aus dem Speicher."""
    reasons = []
    state = off.get("zustand") or {}
    if off.get("fehler"):
        reasons.append(off["fehler"])
    if state.get("service_worker") is not True:
        reasons.append("Seite nicht vom Service Worker gesteuert")
    if state.get("online") is not False:
        reasons.append("Browser meldete keine fehlende Verbindung")
    if state.get("sperrbildschirm"):
        reasons.append("fragte erneut nach der Passphrase")
    elif not state.get("kursstand"):
        reasons.append("Startseite mit Kursstand nicht sichtbar")
    if "Offline – gespeicherter Stand" not in (state.get("hinweise") or []):
        reasons.append("kein Hinweis „Offline – gespeicherter Stand“")
    if not (off.get("rangliste_zeilen") or 0) > 0:
        reasons.append("Rangliste aus dem Speicher ohne Zeilen")
    return not reasons, reasons


def watch(page) -> None:
    def path_of(url: str) -> str:
        return url.split("?")[0].replace(SITE, "")

    page.on("console", lambda m: RESULTS["konsolenfehler"].append(f"{STEP['name']}: {safe(m.text)[:200]}") if m.type == "error" else None)
    page.on("pageerror", lambda e: RESULTS["konsolenfehler"].append(f"{STEP['name']}: {safe(str(e))[:200]}"))
    page.on("response", lambda r: RESULTS["fehlgeschlagene_abrufe"].append(f"{STEP['name']}: {path_of(r.url)} – Status {r.status}") if r.status >= 400 else None)
    page.on("requestfailed", lambda r: RESULTS["fehlgeschlagene_abrufe"].append(f"{STEP['name']}: {path_of(r.url)} – abgebrochen: {(r.failure or '')[:60]}"))


def settle(page, timeout: float = 90.0, quiet: float = 1.0) -> None:
    deadline = time.monotonic() + timeout
    calm = None
    while time.monotonic() < deadline:
        if page.locator(".loading").count():
            calm = None
        elif calm is None:
            calm = time.monotonic()
        elif time.monotonic() - calm >= quiet:
            return
        page.wait_for_timeout(100)


def main() -> int:
    from playwright.sync_api import sync_playwright

    if not PASSPHRASE:
        print("::error title=Android mit echten Daten::Secret DATA_PASSPHRASE fehlt – nichts geprüft")
        return 1
    network(True)
    first_mark = f"pruefung={uuid.uuid4().hex[:8]}"
    open_chrome("?" + first_mark)
    with sync_playwright() as p:
        browser, page = connect(p, marker=first_mark)
        watch(page)
        RESULTS["chrome"] = browser.version.split(".")[0]
        page.wait_for_selector("#root *", timeout=120000)
        page.evaluate("navigator.serviceWorker.ready.then(() => true)")
        started = time.monotonic()
        page.locator("#passphrase, .stamp-date").first.wait_for(state="visible", timeout=120000)
        RESULTS["sperrbildschirm"] = page.locator("#passphrase").count() > 0
        RESULTS["oeffnen_s"] = round(time.monotonic() - started, 1)
        if RESULTS["sperrbildschirm"]:
            page.locator("#passphrase").fill(PASSPHRASE)
            began = time.monotonic()
            page.locator("button[type='submit']").click()
            page.locator(".stamp-date").first.wait_for(state="visible", timeout=120000)
            settle(page)
            RESULTS["entsperren_s"] = round(time.monotonic() - began, 1)
        RESULTS["meta"] = page.evaluate(
            """async () => {
                const x = Date.now();
                const v = await fetch('version.json?x=' + x).then((r) => r.json()).catch(() => ({}));
                const s = await fetch('data/status.json?x=' + x).then((r) => r.json()).catch(() => ({}));
                const z = s.zwischenstand || {};
                return { version: v.version || null, stand: s.latest_snapshot_id || null, kursstand: s.last_price_session || null,
                         zwischenstand: !!z.snapshot_id && z.snapshot_id === s.latest_snapshot_id, signale: (s.signale || {}).id || null };
            }"""
        )
        RESULTS["kopf"] = re.sub(r"\s+", " ", page.locator(".stamp-date").first.inner_text()).strip()
        RESULTS["breite"] = page.evaluate("window.innerWidth")
        RESULTS["eigenes_fenster"] = page.evaluate("window.matchMedia('(display-mode: standalone)').matches")
        for name, route, selector in VIEWS:
            STEP["name"] = name
            began = time.monotonic()
            try:
                page.evaluate(f"location.hash = {json.dumps(route)}")
                page.locator(selector).first.wait_for(state="attached", timeout=90000)
                settle(page)
                entry = {"elemente": page.locator(selector).count(), "sekunden": round(time.monotonic() - began, 1), "probleme": page.evaluate(PROBLEMS_JS, list(ERROR_TEXTS))}
            except Exception as exc:  # noqa: BLE001 - Ansicht festhalten, mit der nächsten weitermachen
                entry = {"sekunden": round(time.monotonic() - began, 1), "probleme": [f"{type(exc).__name__}: {safe(str(exc)).splitlines()[0][:150]}"]}
            RESULTS["ansichten"][name] = entry
        # Vor dem Neustart: Steuert der Service Worker die Seite? (Voraussetzung für den Start ohne Netz)
        RESULTS["service_worker_vorher"] = page.evaluate("!!(navigator.serviceWorker && navigator.serviceWorker.controller)")
        try:
            browser.close()  # trennt nur die Verbindung
        except Exception:  # noqa: BLE001
            pass

        # Ohne Netz neu öffnen – wie die App unterwegs ohne Empfang: gespeicherter Stand, keine erneute Passphrase.
        # Eigene Marke in der Adresse, damit die Prüfung den neu geöffneten Tab nimmt und nicht den wiederhergestellten.
        STEP["name"] = "Neustart ohne Netz"
        network(False)
        mark = f"offline={uuid.uuid4().hex[:8]}"
        open_chrome("?" + mark)
        offline: dict = {}
        try:
            browser, page = connect(p, timeout_s=90, marker=mark)
            offline["tabs"] = TABS.get(mark, [])
            began = time.monotonic()
            try:
                page.locator("#passphrase, .stamp-date").first.wait_for(state="visible", timeout=60000)
                settle(page, timeout=30.0)
            except Exception as exc:  # noqa: BLE001 - Zustand trotzdem festhalten
                offline["fehler"] = f"nach {round(time.monotonic() - began)} s weder Sperrbildschirm noch Kursstand ({type(exc).__name__})"
            offline["sekunden"] = round(time.monotonic() - began, 1)
            offline["zustand"] = page.evaluate(STATE_JS)
            if offline["zustand"].get("kursstand") and not offline["zustand"].get("sperrbildschirm"):
                page.evaluate("location.hash = '/ranking?h=30&w=60&p=native'")
                try:
                    page.locator("ol.rows > li").first.wait_for(state="attached", timeout=60000)
                except Exception as exc:  # noqa: BLE001
                    offline["fehler_rangliste"] = type(exc).__name__
                offline["rangliste_zeilen"] = page.locator("ol.rows > li").count()
                offline["rangliste_zustand"] = page.evaluate(STATE_JS)
            try:
                browser.close()
            except Exception:  # noqa: BLE001
                pass
        except Exception as exc:  # noqa: BLE001
            offline["fehler"] = f"{type(exc).__name__}: {safe(str(exc)).splitlines()[0][:150]}"
            offline["tabs"] = TABS.get(mark, [])
        RESULTS["offline"] = offline
        network(True)

    views = RESULTS["ansichten"]
    bad = {name: v["probleme"] for name, v in views.items() if v.get("probleme")}
    off = RESULTS["offline"]
    offline_ok, offline_reasons = offline_verdict(off)
    meta = RESULTS.get("meta") or {}
    lines = [
        f"Chrome {RESULTS['chrome']} für Android im Emulator (Android 15, 1080 × 2340, 450 dpi), veröffentlichte Website {SITE}",
        f"App-Version: {meta.get('version')}; Datenstand: {meta.get('stand')} (Kursstand {meta.get('kursstand')}{', Zwischenstand' if meta.get('zwischenstand') else ''}); Signal-Stand {meta.get('signale')}",
        f"Kopf der Startseite: {RESULTS.get('kopf')}; Breite {RESULTS.get('breite')} CSS-Pixel",
        f"Sperrbildschirm: {RESULTS['sperrbildschirm']}; geöffnet in {RESULTS['oeffnen_s']} s, entsperrt bis zur fertigen Startseite in {RESULTS.get('entsperren_s', '–')} s",
        f"Ansichten mit echten Daten ohne Fehler: {len(views) - len(bad)} von {len(views)}",
    ]
    lines += [f"  {name}: {v.get('elemente', '–')} Elemente, {v['sekunden']} s" + (f" – {'; '.join(v['probleme'])}" if v.get("probleme") else "") for name, v in views.items()]
    state = off.get("zustand") or {}
    lines.append(
        f"Ohne Netz (Flugmodus) neu gestartet: {'bestanden' if offline_ok else 'NICHT bestanden – ' + '; '.join(offline_reasons)}. "
        f"Service Worker vorher {RESULTS.get('service_worker_vorher')}, danach {state.get('service_worker')}; Browser offline {state.get('online') is False}; "
        f"Sperrbildschirm {state.get('sperrbildschirm')}; Kursstand sichtbar {state.get('kursstand')} nach {off.get('sekunden', '–')} s; "
        f"Hinweise: {' | '.join(state.get('hinweise') or []) or 'keine'}; Rangliste aus dem Speicher {off.get('rangliste_zeilen', '–')} Zeilen; "
        f"Seite {state.get('seite', '–')}; Tabs nach dem Neustart: {', '.join(off.get('tabs') or []) or '–'}"
    )
    lines.append(f"Konsolenfehler: {len(RESULTS['konsolenfehler'])}; fehlgeschlagene Abrufe: {len(RESULTS['fehlgeschlagene_abrufe'])}")
    failed = bool(bad) or bool(RESULTS["konsolenfehler"]) or not offline_ok
    notice("Android-Emulator mit echten Daten: " + ("Fehler gefunden" if failed else "alles in Ordnung"), lines, "error" if failed else "notice")
    if RESULTS["konsolenfehler"]:
        notice("Android-Emulator mit echten Daten: Browser-Konsole", RESULTS["konsolenfehler"][:15], "error")
    if RESULTS["fehlgeschlagene_abrufe"]:
        notice("Android-Emulator mit echten Daten: fehlgeschlagene Abrufe", RESULTS["fehlgeschlagene_abrufe"][:20], "warning")
    Path("android-echte-daten.json").write_text(json.dumps(RESULTS, indent=2, ensure_ascii=False), encoding="utf-8")
    return 1 if failed else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001 - Abbruchgrund als Hinweis (Fehlerart und eigene Zeilen, keine Inhalte)
        import traceback

        frames = [f"{Path(f.filename).name}:{f.lineno}" for f in traceback.extract_tb(exc.__traceback__) if "android_echte_daten" in f.filename]
        first = safe(str(exc)).splitlines()[0][:200] if str(exc) else ""
        print(f"::error title=Android mit echten Daten abgebrochen::{type(exc).__name__} bei {' > '.join(frames[-4:])}: {first}")
        sys.exit(1)
