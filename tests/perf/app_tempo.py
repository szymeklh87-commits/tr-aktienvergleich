"""Geschwindigkeit der App wie auf einem Handy messen (ab 1.21) – vorher/nachher mit demselben Datenstand.

Aufruf (Website vorher mit ``python -m traktien demo --passphrase …`` bzw. ``site`` gebaut):

    PYTHONPATH=backend python3 tests/perf/app_tempo.py --site build/demo-site --passphrase … [--laeufe 5] [--cpu 4]

Chromium im Format des Galaxy S25+ (384 × 832, Pixeldichte 2,8125), Prozessor gedrosselt (Standard 4-fach) und Netz wie
ein mittleres Mobilnetz (12 Mbit/s, 60 ms). Gemessen wird je Lauf in einem frischen Browserprofil:

* ``entsperren_ms``      Passphrase eingegeben (Enter) bis die Startseite fertig ist
* ``erneut_oeffnen_ms``  Seite neu laden (Schlüssel gespeichert) bis die Startseite fertig ist
* ``einzelansicht_ms``   Einzelansicht der ersten Aktie öffnen bis der Kursverlauf gezeichnet ist
* ``kursverlauf_wechsel_ms``  Darstellung „Index 100“ wählen bis neu gezeichnet
* ``merkliste_ms``       Merkliste mit 50 Aktien öffnen bis die Zeilen stehen
* ``uebertragen_kb``     übertragene Bytes beim ersten Öffnen und Entsperren (ohne Service Worker)

Ausgabe: JSON mit Median und Einzelwerten. Synthetische DEMO-Daten, keine echten Kurse; das ist eine Simulation im
Browser, kein Test auf einem echten Galaxy-Gerät.
"""

from __future__ import annotations

import argparse
import functools
import http.server
import json
import socketserver
import statistics
import threading
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

S25 = dict(viewport={"width": 384, "height": 832}, device_scale_factor=2.8125, is_mobile=True, has_touch=True, locale="de-DE", timezone_id="Europe/Berlin")


class _Quiet(http.server.SimpleHTTPRequestHandler):
    extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map, ".bin": "application/octet-stream", ".js": "text/javascript", ".webmanifest": "application/manifest+json"}

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def log_message(self, *args) -> None:
        pass


def serve(directory: Path) -> tuple[socketserver.ThreadingTCPServer, str]:
    server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), functools.partial(_Quiet, directory=str(directory)))
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}/"


def throttle(page, cpu: float, kbps: float, latency_ms: float) -> None:
    cdp = page.context.new_cdp_session(page)
    cdp.send("Emulation.setCPUThrottlingRate", {"rate": cpu})
    cdp.send("Network.enable")
    cdp.send("Network.emulateNetworkConditions", {"offline": False, "latency": latency_ms, "downloadThroughput": kbps * 1024 / 8, "uploadThroughput": kbps * 1024 / 16})


def wait_start(page, timeout: float = 60_000) -> None:
    """Startseite fertig: erste Zeile der Top-Liste bzw. eine Rangliste sichtbar, kein Ladebalken mehr."""
    page.wait_for_selector(".view .rows li, .top3 li, .start-top li", timeout=timeout)
    page.wait_for_function("() => !document.querySelector('.loading')", timeout=timeout)


def one_run(browser, base: str, passphrase: str, cpu: float, kbps: float, latency: float, isins: list[str]) -> dict:
    context = browser.new_context(**S25, service_workers="block")
    page = context.new_page()
    page.set_default_timeout(60_000)
    transferred = {"bytes": 0}
    page.on("response", lambda r: transferred.__setitem__("bytes", transferred["bytes"] + int(r.headers.get("content-length") or 0)))
    throttle(page, cpu, kbps, latency)
    result: dict = {}
    page.goto(base + "#/")
    page.wait_for_selector("#passphrase")
    page.locator("#passphrase").fill(passphrase)
    t0 = time.perf_counter()
    page.locator("#passphrase").press("Enter")
    wait_start(page)
    result["entsperren_ms"] = round((time.perf_counter() - t0) * 1000)
    result["uebertragen_kb"] = round(transferred["bytes"] / 1024)
    t0 = time.perf_counter()
    page.reload()
    wait_start(page)
    result["erneut_oeffnen_ms"] = round((time.perf_counter() - t0) * 1000)
    # Einzelansicht der ersten Aktie (Rendite-Bereich mit Kursverlauf)
    t0 = time.perf_counter()
    page.evaluate(f"() => {{ location.hash = '#/aktie/{isins[0]}?tab=rendite&h=90'; }}")
    page.wait_for_selector("#kurs ~ * svg path, section[aria-labelledby='kurs'] svg path", timeout=60_000)
    result["einzelansicht_ms"] = round((time.perf_counter() - t0) * 1000)
    t0 = time.perf_counter()
    page.locator("section[aria-labelledby='kurs'] .segmented button", has_text="Index 100").first.click()
    page.wait_for_function("() => location.hash.includes('ansicht=index')")
    page.wait_for_function("() => { const s = document.querySelector(\"section[aria-labelledby='kurs'] svg\"); return s && s.textContent.includes('100'); }")
    result["kursverlauf_wechsel_ms"] = round((time.perf_counter() - t0) * 1000)
    # Merkliste mit 50 Aktien
    page.evaluate(f"() => localStorage.setItem('tr-vergleich:watchlist:v1', JSON.stringify({json.dumps(isins[:50])}))")
    page.reload()
    wait_start(page)
    t0 = time.perf_counter()
    page.evaluate("() => { location.hash = '#/watchlist'; }")
    page.wait_for_function("() => document.querySelectorAll('.view .rows li').length >= 40", timeout=60_000)
    result["merkliste_ms"] = round((time.perf_counter() - t0) * 1000)
    context.close()
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", required=True)
    parser.add_argument("--passphrase", required=True)
    parser.add_argument("--laeufe", type=int, default=5)
    parser.add_argument("--cpu", type=float, default=4.0)
    parser.add_argument("--kbps", type=float, default=12_000)
    parser.add_argument("--latenz", type=float, default=60)
    parser.add_argument("--chromium", default=None)
    args = parser.parse_args()
    site = Path(args.site)
    status = json.loads((site / "data" / "status.json").read_text(encoding="utf-8"))
    server, base = serve(site)
    isins = json.loads((site / "data" / "messung_isins.json").read_text(encoding="utf-8")) if (site / "data" / "messung_isins.json").exists() else []
    if not isins:
        raise SystemExit("data/messung_isins.json fehlt (Liste von ISINs mit Kursreihe, siehe tests/perf/README)")
    runs = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=args.chromium)
        for _ in range(args.laeufe):
            runs.append(one_run(browser, base, args.passphrase, args.cpu, args.kbps, args.latenz, isins))
        browser.close()
    server.shutdown()
    keys = runs[0].keys()
    report = {
        "app": json.loads((site / "version.json").read_text())["version"] if (site / "version.json").exists() else None,
        "stand": status.get("latest_snapshot_id"),
        "bedingungen": {"cpu_drossel": args.cpu, "netz_kbit_s": args.kbps, "latenz_ms": args.latenz, "format": "384 × 832, DPR 2,8125", "laeufe": args.laeufe},
        "median": {k: statistics.median(r[k] for r in runs) for k in keys},
        "einzeln": runs,
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
