"""TalkBack im Android-Emulator (ab 1.17.1): Was liest der Bildschirmleser in der App vor?

Bis 1.17.0 war TalkBack im Emulator-Abbild vorhanden, aber nicht benutzt. Dieses Skript schaltet TalkBack ein (wie unter
Einstellungen → Bedienungshilfen) und liest den Vorlese-Baum, den Chrome an TalkBack gibt, in vier Ansichten des DEMO-Stands
(Start, Rangliste, Alle Aktien mit Suchfeld, Hilfe): Zahl der bedienbaren Elemente (Knöpfe, Links, Eingabefelder) und wie
viele davon **ohne Namen** wären – TalkBack sagte dort nur „Schaltfläche“. Danach wird TalkBack wieder ausgeschaltet.

Grenzen (ehrlich benannt): Geprüft wird, *was* TalkBack bekommt, nicht die Bedienung mit Wischgesten und nicht die
Vorlese-Reihenfolge; Emulator, kein Gerät. Ausgabe nur Zählwerte und Elementarten (DEMO-Daten, keine Texte der Seite).
Aufruf im Workflow „Android-Emulator prüfen“ nach ``android_install.py``.
"""

from __future__ import annotations

import json
import os
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from android_install import CHROME, adb, notice  # noqa: E402

INTERACTIVE_ROLES = {"button", "link", "textbox", "searchbox", "checkbox", "radio", "combobox", "listbox", "menuitem", "switch", "tab", "slider", "spinbutton", "option"}

import re  # noqa: E402
import xml.etree.ElementTree as ET  # noqa: E402

BASE = "http://localhost:8000/"
ROUTES = ["/", "/ranking?h=30&w=60", "/aktien", "/hilfe"]
TALKBACK = "com.google.android.marvin.talkback/com.google.android.marvin.talkback.TalkBackService"
INTERACTIVE = ("android.widget.Button", "android.widget.EditText", "android.widget.CheckBox", "android.widget.RadioButton", "android.widget.Spinner", "android.widget.ToggleButton")


def web_nodes() -> list[dict]:
    """Elemente der Webseite im Vorlese-Baum (Chrome, ohne die eigene Bedienleiste von Chrome)."""
    for _ in range(4):
        adb("shell", "uiautomator", "dump", "/sdcard/ui.xml", timeout=60)
        text = adb("exec-out", "cat", "/sdcard/ui.xml", timeout=30)
        end = text.rfind("</hierarchy>")
        if end > 0:
            try:
                root = ET.fromstring(text[: end + len("</hierarchy>")])
            except ET.ParseError:
                time.sleep(1)
                continue
            out = []

            def own_name(node) -> str:
                return (node.get("text") or "").strip() or (node.get("content-desc") or "").strip() or (node.get("hint") or "").strip()

            def subtree_name(node) -> bool:
                # TalkBack liest bei einem bedienbaren Element ohne eigenen Namen die Texte der Elemente darin vor
                return any(own_name(child) for child in node.iter("node"))

            def walk(node, context: str) -> None:
                for child in node.findall("node"):
                    if child.get("package") == CHROME and not (child.get("resource-id") or "").startswith(f"{CHROME}:id/"):
                        cls = child.get("class") or ""
                        clickable = child.get("clickable") == "true" or cls in INTERACTIVE
                        name = own_name(child)
                        named = bool(name) or (clickable and cls not in INTERACTIVE and subtree_name(child))
                        out.append({"class": cls.rsplit(".", 1)[-1], "clickable": clickable, "named": named, "context": context[:40],
                                    "hint_attr": child.get("hint") is not None, "bounds": child.get("bounds")})
                        walk(child, name or context)
                    else:
                        walk(child, context)

            walk(root, "")
            return out
        time.sleep(1)
    return []


def ax_names(p, route: str) -> dict:
    """Namen aus Chromes eigenem Barrierefreiheits-Baum (den Chrome an TalkBack weitergibt), über die
    Entwicklerschnittstelle: bedienbare Rollen ohne Namen."""
    adb("forward", "tcp:9222", "localabstract:chrome_devtools_remote")
    browser = p.chromium.connect_over_cdp("http://localhost:9222")
    try:
        page = next((pg for ctx in browser.contexts for pg in ctx.pages if pg.url.startswith(BASE)), None)
        if page is None:
            return {"geprueft": False}
        page.goto(BASE + "#" + route, wait_until="domcontentloaded")
        page.wait_for_selector(".view, .notice", timeout=60000)
        page.wait_for_timeout(1500)
        cdp = page.context.new_cdp_session(page)
        nodes = cdp.send("Accessibility.getFullAXTree").get("nodes", [])
        roles = Counter()
        unnamed = Counter()
        for node in nodes:
            if node.get("ignored"):
                continue
            role = ((node.get("role") or {}).get("value") or "").lower()
            if role not in INTERACTIVE_ROLES:
                continue
            roles[role] += 1
            if not ((node.get("name") or {}).get("value") or "").strip():
                unnamed[role] += 1
        return {"geprueft": True, "bedienbar": sum(roles.values()), "ohne_namen": sum(unnamed.values()), "ohne_namen_rolle": dict(unnamed)}
    finally:
        browser.close()


# Ab 1.19.0 (Auftrag vom 25.10.2026, 14:23 Uhr: „Untersuche die zwei Suchfelder ohne erkannten Screenreader-Namen. Den Emulator
# nicht ohne Nachweis als Ursache annehmen.“): eine Kontrollseite mit Eingabefeldern, die auf sieben übliche Arten beschriftet sind,
# dazu ein Knopf. Gibt das Android-Abbild auch bei einer sichtbaren Beschriftung keinen Namen eines leeren Feldes aus, liegt das
# Fehlen am Abbild (es gibt bei Eingabefeldern nur den eingegebenen Text aus) – nicht an der Beschriftung der App. Synthetische
# Texte, keine Daten.
PROBE_FILE = "a11y-kontrolle.html"
PROBE_FIELDS = (
    ("A", "sichtbare Beschriftung (label for)", '<label for="fa">Feld A beschriftet</label> <input id="fa" type="search">'),
    ("B", "umschließende Beschriftung (wie Hilfe)", '<label>Feld B beschriftet <input type="search" placeholder="Beispiel B"></label>'),
    ("C", "versteckte Beschriftung mit Platzhalter (wie Alle Aktien)",
     '<label for="fc" style="position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)">Feld C beschriftet</label>'
     '<input id="fc" type="search" placeholder="Feld C beschriftet">'),
    ("D", "aria-label", '<input type="search" aria-label="Feld D beschriftet">'),
    ("E", "aria-labelledby", '<span id="le">Feld E beschriftet</span> <input type="search" aria-labelledby="le">'),
    ("F", "nur Platzhalter", '<input type="search" placeholder="Feld F Platzhalter">'),
    ("G", "aria-label mit eingegebenem Text", '<input type="search" aria-label="Feld G beschriftet" value="Wert G">'),
)


def probe_html() -> str:
    rows = "".join(f"<p>{html}</p>" for _, _, html in PROBE_FIELDS)
    return ('<!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>Kontrollseite Eingabefelder</title></head><body><h1>Kontrollseite</h1>{rows}<p><button type="button">Knopf H</button></p></body></html>')


def probe_fields(site_dir: str | None) -> list[str]:
    """Android-Abbild und Chromes Baum für die Kontrollseite: je Feld, was das Abbild ausgibt (Text, content-desc, hint)."""
    if not site_dir:
        return ["Kontrollseite: Ordner der DEMO-Website unbekannt – nicht geprüft"]
    Path(site_dir, PROBE_FILE).write_text(probe_html(), encoding="utf-8")
    adb("shell", "am", "start", "-n", f"{CHROME}/com.google.android.apps.chrome.Main", "-d", BASE + PROBE_FILE)
    time.sleep(10)
    adb("shell", "uiautomator", "dump", "/sdcard/ui.xml", timeout=60)
    text = adb("exec-out", "cat", "/sdcard/ui.xml", timeout=30)
    end = text.rfind("</hierarchy>")
    if end <= 0:
        return ["Kontrollseite: kein Abbild – nicht geprüft"]
    root = ET.fromstring(text[: end + len("</hierarchy>")])
    edits = [n for n in root.iter("node") if n.get("class") == "android.widget.EditText" and n.get("package") == CHROME]
    buttons = [n for n in root.iter("node") if n.get("class") == "android.widget.Button" and n.get("package") == CHROME and (n.get("text") or "").startswith("Knopf")]
    any_hint = any(n.get("hint") is not None for n in root.iter("node"))
    attrs = sorted({k for n in edits for k in n.attrib})
    lines = [f"Kontrollseite mit {len(PROBE_FIELDS)} Feldern: im Android-Abbild {len(edits)} Eingabefelder; Attribut „hint“ in irgendeinem Element des Abbilds: "
             f"{'ja' if any_hint else 'nein'}; Attribute eines Eingabefelds: {', '.join(attrs) or '–'}"]
    for (letter_, how, _), node in zip(PROBE_FIELDS, edits):
        lines.append(f"  Feld {letter_} ({how}): Text „{(node.get('text') or '').strip()}“, content-desc „{(node.get('content-desc') or '').strip()}“"
                     + (f", hint „{node.get('hint')}“" if node.get("hint") is not None else ""))
    lines.append(f"  Knopf H: {'Text im Abbild' if buttons else 'nicht gefunden'}")
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            adb("forward", "tcp:9222", "localabstract:chrome_devtools_remote")
            browser = pw.chromium.connect_over_cdp("http://localhost:9222")
            try:
                page = next((pg for ctx in browser.contexts for pg in ctx.pages if pg.url.endswith(PROBE_FILE)), None)
                if page is not None:
                    cdp = page.context.new_cdp_session(page)
                    nodes = cdp.send("Accessibility.getFullAXTree").get("nodes", [])
                    names = [((n.get("name") or {}).get("value") or "") for n in nodes if ((n.get("role") or {}).get("value") or "") in ("searchbox", "textbox") and not n.get("ignored")]
                    lines.append(f"  Chromes Barrierefreiheits-Baum: {len(names)} Eingabefelder, mit Namen {sum(1 for x in names if x.strip())}: " + "; ".join(f"„{x}“" for x in names))
            finally:
                browser.close()
    except Exception as exc:  # noqa: BLE001 - Entwicklerschnittstelle nicht erreichbar: nur melden
        lines.append(f"  Chromes Barrierefreiheits-Baum: nicht geprüft ({type(exc).__name__})")
    return lines


def talkback(on: bool) -> bool:
    if on:
        adb("shell", "settings", "put", "secure", "enabled_accessibility_services", TALKBACK)
        adb("shell", "settings", "put", "secure", "accessibility_enabled", "1")
    else:
        adb("shell", "settings", "put", "secure", "enabled_accessibility_services", "null")
        adb("shell", "settings", "put", "secure", "accessibility_enabled", "0")
    time.sleep(6)
    state = adb("shell", "dumpsys", "accessibility", timeout=60)
    return "TalkBack" in state and re.search(r"touchExplorationEnabled\s*=\s*true", state, re.I) is not None if on else True


def main() -> int:
    results: dict = {"talkback_an": False, "ansichten": {}}
    adb("reverse", "tcp:8000", "tcp:8000")
    results["talkback_an"] = talkback(True)
    try:
        for route in ROUTES:
            nodes = []
            for attempt in range(3):  # langsamer Aufbau unter TalkBack: bis zu dreimal versuchen
                adb("shell", "am", "start", "-n", f"{CHROME}/com.google.android.apps.chrome.Main", "-d", BASE + "#" + route)
                time.sleep(8 + 4 * attempt)
                nodes = web_nodes()
                if len(nodes) > 20:
                    break
            interactive = [n for n in nodes if n["clickable"]]
            missing = [n for n in interactive if not n["named"]]
            try:
                from playwright.sync_api import sync_playwright

                with sync_playwright() as p:
                    ax = ax_names(p, route)
            except Exception as exc:  # noqa: BLE001 - Entwicklerschnittstelle nicht erreichbar: nur melden
                ax = {"geprueft": False, "grund": type(exc).__name__}
            unnamed = Counter(n["class"] for n in missing)
            results["ansichten"][route] = {
                "elemente": len(nodes), "bedienbar": len(interactive), "ohne_namen": sum(unnamed.values()), "ohne_namen_art": dict(unnamed),
                # wo: Name des nächsten benannten Elements darüber (Beschriftung der App, DEMO-Daten), Feld „hint“ im Abbild vorhanden?
                "ohne_namen_wo": [f"{n['class']} in „{n['context']}“ (hint-Feld {'ja' if n['hint_attr'] else 'nein'}, {n['bounds']})" for n in missing][:6],
                "chrome_baum": ax,
            }
        try:
            results["kontrollseite"] = probe_fields(os.environ.get("DEMO_SITE"))
        except Exception as exc:  # noqa: BLE001 - nur melden
            results["kontrollseite"] = [f"Kontrollseite: nicht geprüft ({type(exc).__name__})"]
    finally:
        talkback(False)
    lines = [f"TalkBack eingeschaltet (Tastsuche aktiv): {results['talkback_an']}"]
    for route, r in results["ansichten"].items():
        lines.append(f"{route}: {r['elemente']} Elemente im Vorlese-Baum, {r['bedienbar']} bedienbar, ohne vorlesbaren Namen {r['ohne_namen']} {r['ohne_namen_art'] or ''}")
        for where in r.get("ohne_namen_wo") or []:
            lines.append(f"  – {where}")
        ax = r.get("chrome_baum") or {}
        if ax.get("geprueft"):
            lines.append(f"  Chromes Barrierefreiheits-Baum: {ax['bedienbar']} bedienbare Rollen, ohne Namen {ax['ohne_namen']} {ax['ohne_namen_rolle'] or ''}")
        else:
            lines.append(f"  Chromes Barrierefreiheits-Baum: nicht geprüft ({ax.get('grund', 'Seite nicht gefunden')})")
    notice("Android-Emulator: TalkBack (nur DEMO-Daten)", lines)
    notice("Android-Emulator: Kontrollseite Eingabefelder (synthetisch)", results.get("kontrollseite") or ["nicht geprüft"])
    Path("android-talkback.json").write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001 - nur melden; TalkBack-Prüfung soll den Lauf nicht abbrechen
        print(f"::warning title=TalkBack-Prüfung ohne Ergebnis::{type(exc).__name__}: {str(exc).splitlines()[0][:200] if str(exc) else ''}")
        sys.exit(0)
