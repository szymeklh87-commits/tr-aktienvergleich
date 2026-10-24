"""Echte Installation der veröffentlichten App im Android-Emulator (ab 1.17.1).

Simons Auftrag vom 24.10.2026: „Prüfe insbesondere die tatsächliche Android-Installation, soweit deine Umgebung das
ermöglicht.“ Bis dahin fragte der Emulator-Test nur ab, ob Chrome die App installieren *könnte*. Dieses Skript
installiert sie wirklich – so, wie es auf dem Handy geht – und öffnet sie danach vom Startbildschirm:

1. Chrome im Emulator öffnet die veröffentlichte Website (öffentlich, ohne Passphrase – es erscheint nur der
   Sperrbildschirm; echte Kurse werden dabei nicht entschlüsselt).
2. Menü ⋮ → „App installieren“ („Install app“) → im Dialog „Installieren“ – angetippt über die Bedienoberfläche
   (``uiautomator``), nicht über eine Abkürzung der Entwicklerschnittstelle.
3. Ergebnis: Hat Android ein eigenes App-Paket (WebAPK, ``org.chromium.webapk.…``) installiert, oder nur eine
   Verknüpfung angelegt? Wie lange hat es gedauert? Liegt das Symbol „TR-Vergleich“ auf dem Startbildschirm?
4. Start vom Startbildschirm (Symbol antippen): eigenes Fenster (``display-mode: standalone``), keine Adressleiste,
   Sperrbildschirm der App sichtbar.
5. Ohne Netz (Flugmodus): App ganz beenden und neu starten – der Sperrbildschirm kommt aus dem Speicher der App.

Das ist ein **Emulator-Test** (Android 15, Chrome aus dem Systemabbild), kein Gerätetest. Ausgegeben werden nur Ja/Nein,
Zeiten und Zählwerte. Aufruf im Workflow „Android-Emulator prüfen“ nach ``android_emulator.py``.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

SITE = "https://szymeklh87-commits.github.io/tr-aktienvergleich/"
CHROME = "com.android.chrome"
SHORT_NAME = "TR-Vergleich"
RESULTS: dict = {}

INSTALL_ITEMS = re.compile(r"^(Install app|App installieren|Installieren)$", re.I)
ADD_ITEMS = re.compile(r"^(Add to [Hh]ome screen|Zum Startbildschirm hinzufügen)$")
CONFIRM = re.compile(r"^(Install|Installieren|Add|Hinzufügen)$", re.I)
LAUNCHER_ADD = re.compile(r"^(Add automatically|Automatisch hinzufügen|Add|Hinzufügen)$", re.I)


def adb(*args: str, check: bool = False, timeout: int = 60) -> str:
    try:
        out = subprocess.run(["adb", *args], check=check, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return ""
    return (out.stdout or "").strip()


def notice(title: str, lines: list[str], level: str = "notice") -> None:
    body = "%0A".join(line.replace("%", "%25").replace("\n", " ") for line in lines)
    print(f"::{level} title={title}::{body}")


# ---------------------------------------------------------------- Bedienoberfläche (uiautomator)


def ui_nodes() -> list[dict]:
    """Alle Elemente des Bildschirms (Text, Beschreibung, Kennung, Fläche). Leere Liste, wenn kein Abbild gelang."""
    for _ in range(4):
        adb("shell", "uiautomator", "dump", "/sdcard/ui.xml", timeout=40)
        text = adb("exec-out", "cat", "/sdcard/ui.xml", timeout=20)
        end = text.rfind("</hierarchy>")
        if end > 0:
            try:
                root = ET.fromstring(text[: end + len("</hierarchy>")])
            except ET.ParseError:
                time.sleep(1)
                continue
            nodes = []
            for node in root.iter("node"):
                bounds = re.findall(r"\d+", node.get("bounds", ""))
                if len(bounds) != 4:
                    continue
                x1, y1, x2, y2 = (int(v) for v in bounds)
                nodes.append(
                    {
                        "text": (node.get("text") or "").strip(),
                        "desc": (node.get("content-desc") or "").strip(),
                        "id": node.get("resource-id") or "",
                        "package": node.get("package") or "",
                        "clickable": node.get("clickable") == "true",
                        "center": ((x1 + x2) // 2, (y1 + y2) // 2),
                        "area": max(0, x2 - x1) * max(0, y2 - y1),
                    }
                )
            return nodes
        time.sleep(1)
    return []


def visible_texts(nodes: list[dict], limit: int = 15) -> list[str]:
    """Kurze Texte der Bedienoberfläche (Dialoge, Menüs, Hinweise) für die Ursachensuche – ohne Seiteninhalte."""
    seen: list[str] = []
    for node in nodes:
        for value in (node["text"], node["desc"]):
            if value and len(value) <= 60 and value not in seen and not node["id"].startswith("org.chromium"):
                seen.append(value)
    return seen[:limit]


def logcat_lines(pattern: str = r"webapk|WebApk|WebAPK|installer|Install", limit: int = 25) -> list[str]:
    """Letzte passende Zeilen des Systemprotokolls (nur Meldungstext, ohne Prozessnummern)."""
    out = adb("logcat", "-d", "-v", "tag", timeout=60)
    lines = [re.sub(r"\s+", " ", line).strip()[:200] for line in out.splitlines() if re.search(pattern, line)]
    return lines[-limit:]


def find(nodes: list[dict], pattern: re.Pattern | None = None, *, rid: str | None = None) -> dict | None:
    for node in nodes:
        if rid is not None and node["id"] == rid:
            return node
        if pattern is not None and (pattern.match(node["text"]) or pattern.match(node["desc"])) and node["area"] > 0:
            return node
    return None


def tap(node: dict) -> None:
    x, y = node["center"]
    adb("shell", "input", "tap", str(x), str(y))


def webapk_packages() -> list[str]:
    out = adb("shell", "pm", "list", "packages", "org.chromium.webapk")
    return sorted(line.split(":", 1)[1] for line in out.splitlines() if line.startswith("package:org.chromium.webapk"))


def resumed_activity() -> str:
    out = adb("shell", "dumpsys", "activity", "activities")
    for line in out.splitlines():
        if "topResumedActivity" in line or "mResumedActivity" in line:
            match = re.search(r"\s([\w.]+)/([\w.$]+)", line)
            if match:
                package, activity = match.group(1), match.group(2)
                # Paketname eines WebAPK enthält einen Prüfwert – nur die Art ausgeben
                return ("WebAPK" if package.startswith("org.chromium.webapk") else package) + "/" + activity.split(".")[-1]
    return "unbekannt"


# ---------------------------------------------------------------- Seite (Entwicklerschnittstelle)


def page_state(p, timeout_s: int = 90) -> dict | None:
    """Mit Chrome verbinden und den Zustand der App-Seite lesen (auch im eigenen Fenster des WebAPK)."""
    adb("forward", "tcp:9222", "localabstract:chrome_devtools_remote")
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            browser = p.chromium.connect_over_cdp("http://localhost:9222")
        except Exception:  # noqa: BLE001 - Chrome startet noch
            time.sleep(2)
            continue
        try:
            for context in browser.contexts:
                for page in context.pages:
                    if not page.url.startswith(SITE):
                        continue
                    try:
                        page.wait_for_selector("#root *", timeout=20000)
                        page.wait_for_timeout(1500)
                        return page.evaluate(
                            """() => ({
                                eigenes_fenster: window.matchMedia('(display-mode: standalone)').matches,
                                sperrbildschirm: !!document.querySelector('input[type=password]'),
                                service_worker: !!(navigator.serviceWorker && navigator.serviceWorker.controller),
                                online: navigator.onLine,
                                breite: window.innerWidth,
                            })"""
                        )
                    except Exception:  # noqa: BLE001 - Seite baut sich noch auf
                        continue
        finally:
            try:
                browser.close()  # trennt nur die Verbindung
            except Exception:  # noqa: BLE001
                pass
        time.sleep(2)
    return None


def prepare_page(p) -> dict:
    """Website in Chrome öffnen, Service Worker abwarten, Installierbarkeit abfragen."""
    adb("forward", "tcp:9222", "localabstract:chrome_devtools_remote")
    for attempt in range(30):
        try:
            browser = p.chromium.connect_over_cdp("http://localhost:9222")
            break
        except Exception:  # noqa: BLE001
            time.sleep(2)
    else:
        raise RuntimeError("Chrome war über die Entwicklerschnittstelle nicht erreichbar")
    context = browser.contexts[0]
    page = next((pg for pg in context.pages if pg.url.startswith(SITE)), None)
    if page is None:
        page = context.pages[-1] if context.pages else context.new_page()
        page.goto(SITE + "#/", wait_until="domcontentloaded", timeout=90000)
    for other in list(context.pages):
        if other is not page:
            try:
                other.close()
            except Exception:  # noqa: BLE001
                pass
    page.bring_to_front()
    page.wait_for_selector("#root *", timeout=90000)
    page.evaluate("navigator.serviceWorker.ready.then(() => true)")
    page.reload(wait_until="domcontentloaded")
    page.wait_for_function("!!navigator.serviceWorker.controller", timeout=90000)
    page.wait_for_timeout(2000)
    cdp = context.new_cdp_session(page)
    errors = cdp.send("Page.getInstallabilityErrors").get("installabilityErrors", [])
    info = {"hindernisse": [e.get("errorId") for e in errors], "service_worker": True}
    browser.close()
    return info


# ---------------------------------------------------------------- Ablauf


def install_via_menu() -> dict:
    """Menü ⋮ → „App installieren“ → „Installieren“ – wie mit dem Finger."""
    result = {"menue_eintrag": None, "bestaetigt": False}
    for attempt in range(3):
        nodes = ui_nodes()
        menu = find(nodes, rid=f"{CHROME}:id/menu_button")
        if menu is None:
            adb("shell", "input", "keyevent", "KEYCODE_BACK")  # z. B. ein Hinweis-Fenster über der Seite
            time.sleep(1.5)
            continue
        tap(menu)
        time.sleep(2)
        nodes = ui_nodes()
        item = find(nodes, INSTALL_ITEMS) or find(nodes, ADD_ITEMS)
        if item is None:
            # Menü ohne passenden Eintrag (Seite noch nicht installierbar?) – schließen und erneut versuchen
            result["menue_eintraege_gesehen"] = len([n for n in nodes if n["text"]])
            adb("shell", "input", "keyevent", "KEYCODE_BACK")
            time.sleep(3)
            continue
        result["menue_eintrag"] = item["text"] or item["desc"]
        result["menue"] = [n["text"] for n in nodes if n["text"] and n["id"].endswith("menu_item_text")][:20]
        tap(item)
        time.sleep(2.5)
        for _ in range(4):
            nodes = ui_nodes()
            button = next((n for n in nodes if CONFIRM.match(n["text"]) and n["clickable"]), None) or find(nodes, CONFIRM)
            if button is not None:
                result["dialog_knopf"] = button["text"] or button["desc"]
                result["dialog_texte"] = visible_texts(nodes)
                tap(button)
                result["bestaetigt"] = True
                break
            time.sleep(1.5)
        break
    return result


def pinned_shortcuts() -> int:
    """Zahl der von Chrome angehefteten Verknüpfungen auf dem Startbildschirm (Weg ohne WebAPK)."""
    out = adb("shell", "dumpsys", "shortcut", timeout=60)
    block = out.split("Package: com.android.chrome", 1)[1] if "Package: com.android.chrome" in out else ""
    block = block.split("Package: ", 1)[0]
    return len(re.findall(r"flags=\[[^\]]*Pinned", block, re.I)) or block.count("Pin")


def wait_for_install(before: list[str], seconds: int = 240) -> dict:
    started = time.time()
    launcher_dialog = False
    texts: list[str] = []
    while time.time() - started < seconds:
        now = webapk_packages()
        new = [pkg for pkg in now if pkg not in before]
        if new:
            return {"webapk": True, "paket": new[0], "sekunden": round(time.time() - started, 1), "startbildschirm_dialog": launcher_dialog, "texte": texts}
        nodes = ui_nodes()
        for value in visible_texts(nodes):
            if value not in texts:
                texts.append(value)
        add = next((n for n in nodes if LAUNCHER_ADD.match(n["text"]) and n["clickable"] and n["package"] != CHROME), None)
        if add is not None:  # Startbildschirm fragt bei einer Verknüpfung nach
            launcher_dialog = True
            tap(add)
        time.sleep(3)
    return {"webapk": False, "paket": None, "sekunden": round(time.time() - started, 1), "startbildschirm_dialog": launcher_dialog, "texte": texts[:25]}


def launch_from_home() -> dict:
    adb("shell", "input", "keyevent", "KEYCODE_HOME")
    time.sleep(3)
    nodes = ui_nodes()
    icon = next((n for n in nodes if (n["text"] == SHORT_NAME or n["desc"] == SHORT_NAME) and n["package"] != CHROME), None)
    where = "Startbildschirm"
    if icon is None:
        # Alle Apps öffnen (nach oben wischen) und dort suchen
        adb("shell", "input", "swipe", "540", "2000", "540", "600", "300")
        time.sleep(2.5)
        nodes = ui_nodes()
        icon = next((n for n in nodes if (n["text"] == SHORT_NAME or n["desc"] == SHORT_NAME) and n["package"] != CHROME), None)
        where = "Alle Apps"
    if icon is None:
        return {"symbol_gefunden": False, "wo": None}
    tap(icon)
    time.sleep(6)
    return {"symbol_gefunden": True, "wo": where}


def network(on: bool) -> None:
    state = "disable" if on else "enable"
    adb("shell", "cmd", "connectivity", "airplane-mode", state)
    for service in ("wifi", "data"):
        adb("shell", "svc", service, "enable" if on else "disable")
    time.sleep(4)


def main() -> int:
    from playwright.sync_api import sync_playwright

    network(True)
    adb("shell", "am", "force-stop", CHROME)
    time.sleep(2)
    adb("shell", "am", "start", "-n", f"{CHROME}/com.google.android.apps.chrome.Main", "-d", SITE + "#/")
    time.sleep(8)
    with sync_playwright() as p:
        RESULTS["vorbereitung"] = prepare_page(p)
        before = webapk_packages()
        RESULTS["vorher_webapks"] = len(before)
        RESULTS["menue"] = install_via_menu()
        third_party_before = set(adb("shell", "pm", "list", "packages", "-3").splitlines())
        RESULTS["installation"] = wait_for_install(before) if RESULTS["menue"]["bestaetigt"] else {"webapk": False, "paket": None, "sekunden": None, "texte": []}
        RESULTS["installation"]["neue_pakete"] = len(set(adb("shell", "pm", "list", "packages", "-3").splitlines()) - third_party_before)
        RESULTS["installation"]["angeheftete_verknuepfungen"] = pinned_shortcuts()
        RESULTS["installation"]["protokoll"] = logcat_lines()
        pkg = RESULTS["installation"].get("paket")
        if pkg:
            # Hat das Paket einen Eintrag für den Startbildschirm (Launcher-Aktivität)?
            RESULTS["startaktivitaet"] = "/" in adb("shell", "cmd", "package", "resolve-activity", "--brief", "-c", "android.intent.category.LAUNCHER", pkg)
        adb("shell", "am", "force-stop", CHROME)
        time.sleep(2)
        RESULTS["start"] = launch_from_home()
        if not RESULTS["start"]["symbol_gefunden"] and pkg:
            adb("shell", "monkey", "-p", pkg, "-c", "android.intent.category.LAUNCHER", "1")
            time.sleep(6)
            RESULTS["start"]["ersatz"] = "über das App-Paket gestartet"
        RESULTS["start"]["vorne"] = resumed_activity()
        nodes = ui_nodes()
        RESULTS["start"]["adressleiste"] = find(nodes, rid=f"{CHROME}:id/url_bar") is not None
        RESULTS["start"]["seite"] = page_state(p)

        # Ohne Netz neu starten
        network(False)
        adb("shell", "am", "force-stop", CHROME)
        time.sleep(2)
        if pkg:
            adb("shell", "monkey", "-p", pkg, "-c", "android.intent.category.LAUNCHER", "1")
        else:
            launch_from_home()
        time.sleep(8)
        RESULTS["offline"] = {"vorne": resumed_activity(), "seite": page_state(p, timeout_s=60)}
        network(True)

    inst = RESULTS["installation"]
    start = RESULTS["start"]
    seite = start.get("seite") or {}
    off = RESULTS["offline"].get("seite") or {}
    lines = [
        f"Website installierbar: Hindernisse {RESULTS['vorbereitung']['hindernisse'] or 'keine'}; Menüeintrag „{RESULTS['menue'].get('menue_eintrag')}“, Dialog bestätigt: {RESULTS['menue']['bestaetigt']} ({RESULTS['menue'].get('dialog_knopf')}); Dialog: {' | '.join(RESULTS['menue'].get('dialog_texte') or [])}",
        f"Menü: {' | '.join(RESULTS['menue'].get('menue') or [])}",
        f"Installiert als eigenes App-Paket (WebAPK): {inst['webapk']}" + (f" nach {inst['sekunden']} s" if inst["webapk"] else f" (nach {inst['sekunden']} s kein Paket)"),
        f"Symbol „{SHORT_NAME}“ gefunden: {start['symbol_gefunden']} ({start.get('wo') or start.get('ersatz') or '–'}); vorne: {start['vorne']}; Adressleiste sichtbar: {start['adressleiste']}",
        f"Vom Startbildschirm gestartet: eigenes Fenster {seite.get('eigenes_fenster')}, Sperrbildschirm {seite.get('sperrbildschirm')}, Service Worker {seite.get('service_worker')}, Breite {seite.get('breite')} CSS-Pixel",
        f"Ohne Netz neu gestartet: eigenes Fenster {off.get('eigenes_fenster')}, Sperrbildschirm {off.get('sperrbildschirm')}, online {off.get('online')}; vorne: {RESULTS['offline']['vorne']}",
    ]
    if not inst["webapk"]:
        lines.append(f"Kein App-Paket: neue Pakete {inst.get('neue_pakete')}, angeheftete Verknüpfungen von Chrome {inst.get('angeheftete_verknuepfungen')}; Bildschirmtexte: {' | '.join(inst.get('texte') or [])}")
        notice("Android-Installation: Systemprotokoll (WebAPK)", inst.get("protokoll") or ["keine passenden Zeilen"])
    notice("Android-Emulator: echte Installation", lines)
    Path("android-installation.json").write_text(json.dumps(RESULTS, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    ok = bool(inst["webapk"]) and bool(seite.get("eigenes_fenster")) and bool(seite.get("sperrbildschirm")) and not start["adressleiste"] and bool(off.get("sperrbildschirm"))
    return 0 if ok else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001 - Abbruchgrund als Hinweis (Fehlerart und eigene Zeilen, keine Inhalte)
        import traceback

        frames = [f"{Path(f.filename).name}:{f.lineno}" for f in traceback.extract_tb(exc.__traceback__) if "android_install" in f.filename]
        first_line = str(exc).splitlines()[0][:200] if str(exc) else ""
        print(f"::error title=Android-Installation abgebrochen::{type(exc).__name__} bei {' > '.join(frames[-4:])}: {first_line}")
        if RESULTS:
            print("::notice title=Android-Installation Teilergebnis::" + json.dumps(RESULTS, ensure_ascii=False, default=str)[:1500])
        raise
