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
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from android_install import CHROME, adb, notice  # noqa: E402

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
            for node in root.iter("node"):
                if node.get("package") != CHROME or (node.get("resource-id") or "").startswith(f"{CHROME}:id/"):
                    continue
                cls = node.get("class") or ""
                clickable = node.get("clickable") == "true" or cls in INTERACTIVE
                name = (node.get("text") or "").strip() or (node.get("content-desc") or "").strip() or (node.get("hint") or "").strip()
                out.append({"class": cls.rsplit(".", 1)[-1], "clickable": clickable, "named": bool(name)})
            return out
        time.sleep(1)
    return []


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
            adb("shell", "am", "start", "-n", f"{CHROME}/com.google.android.apps.chrome.Main", "-d", BASE + "#" + route)
            time.sleep(8)
            nodes = web_nodes()
            interactive = [n for n in nodes if n["clickable"]]
            unnamed = Counter(n["class"] for n in interactive if not n["named"])
            results["ansichten"][route] = {"elemente": len(nodes), "bedienbar": len(interactive), "ohne_namen": sum(unnamed.values()), "ohne_namen_art": dict(unnamed)}
    finally:
        talkback(False)
    lines = [f"TalkBack eingeschaltet (Tastsuche aktiv): {results['talkback_an']}"]
    for route, r in results["ansichten"].items():
        lines.append(f"{route}: {r['elemente']} Elemente im Vorlese-Baum, {r['bedienbar']} bedienbar, ohne Namen {r['ohne_namen']} {r['ohne_namen_art'] or ''}")
    notice("Android-Emulator: TalkBack (nur DEMO-Daten)", lines)
    Path("android-talkback.json").write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001 - nur melden; TalkBack-Prüfung soll den Lauf nicht abbrechen
        print(f"::warning title=TalkBack-Prüfung ohne Ergebnis::{type(exc).__name__}: {str(exc).splitlines()[0][:200] if str(exc) else ''}")
        sys.exit(0)
