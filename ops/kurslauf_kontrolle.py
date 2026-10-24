"""Kontrolle eines täglichen Kurslaufs (ab 1.17.1) – nur lesend, nur Zahlen und Ja/Nein.

Simons Auftrag vom 24.10.2026: „Bereite die Kontrolle des ersten zeitgesteuerten vollständigen Kurslaufs vor. Behaupte
dessen Erfolg erst, wenn er tatsächlich stattgefunden hat.“

Prüft einen Lauf des Workflows „Täglicher Lauf“ gegen feste Kriterien und schreibt das Ergebnis als Tabelle in die
Laufübersicht (und als ``::notice``). Aufruf im Workflow „Kurslauf kontrollieren“ (nur von Hand, ohne Secrets) oder lokal:

    python3 ops/kurslauf_kontrolle.py --lauf <Laufnummer>      # ein Lauf
    python3 ops/kurslauf_kontrolle.py --seit 2026-10-26        # alle offiziellen Läufe ab dem Tag, mit dem ersten zeitgesteuerten

In GitHub Actions mit dem Token des Laufs (nur Lesen), lokal über die GitHub-CLI („gh api“).

Kriterien (alle müssen erfüllt sein, damit ein Lauf als **vollständiger zeitgesteuerter Kurslauf bestanden** gilt):

1. zeitgesteuert: GitHub-Zeitplan (Auslöser „schedule“) oder vom Workflow „Nachtlauf“ gestartet, der selbst über den
   Zeitplan ausgelöst wurde (ab 1.18; ein von Hand gestarteter Nachtlauf zählt nicht)
2. neuer Kursstand vollständig veröffentlicht
3. Kurse aller Notierungen abgerufen (mindestens 10.000 offen, nicht aus dem Checkpoint)
4. gleichzeitiger Abruf über zwei Hosts mit mindestens 6 Abrufen je Sekunde (Messlauf 24.10.: 8,0)
5. kein Rückfall wegen Drosselung (HTTP 429)
6. Job „berechnen“ höchstens 60 Minuten
7. Kennzahlen und Signale berechnet, Website bereitgestellt
8. veröffentlichte ``status.json``: neuer Kursstand als neuester Stand, nächster Kursstand danach, Signale zum neuen
   Kursstand (ab 1.18; nur in GitHub Actions abrufbar)

Die Live-Prüfung der App und die unabhängige Nachrechnung brauchen die Passphrase und bleiben ein eigener, von Hand
gestarteter Workflow („App mit echten Daten prüfen“).
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

REPO = os.environ.get("GITHUB_REPOSITORY", "szymeklh87-commits/tr-aktienvergleich")
SITE = os.environ.get("TR_APP_URL", "https://szymeklh87-commits.github.io/tr-aktienvergleich/")
NIGHT_UTC = (22, 37)
MIN_LISTINGS = 10_000
MIN_RATE = 6.0
MAX_MINUTES = 60


def api(path: str) -> dict:
    """GitHub-Schnittstelle nur lesend: in GitHub Actions mit dem Token des Laufs, sonst über die GitHub-CLI."""
    token = os.environ.get("GITHUB_TOKEN")
    if os.environ.get("GITHUB_ACTIONS") == "true" and token:
        request = urllib.request.Request(
            f"https://api.github.com/{path.lstrip('/')}",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json", "User-Agent": "tr-aktienvergleich-kontrolle"},
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read())
    out = subprocess.run(["gh", "api", path], check=True, capture_output=True, text=True, timeout=120)
    return json.loads(out.stdout)


def de(value) -> str:
    """Zahl in deutscher Schreibweise (Komma), sonst „–“."""
    if value is None:
        return "–"
    return str(value).replace(".", ",") if isinstance(value, float) else str(value)


def parse_time(text: str | None) -> dt.datetime | None:
    return dt.datetime.fromisoformat(text.replace("Z", "+00:00")) if text else None


def run_report(notices: list[dict]) -> dict:
    """Werte aus der Notiz „Lauf: …“ des Jobs „berechnen“ (nur Zahlen)."""
    out: dict = {}
    for note in notices:
        title = note.get("title") or ""
        if not title.startswith("Lauf: "):
            continue
        out["status"] = title[len("Lauf: "):].strip()
        text = note.get("message") or ""
        if m := re.search(r"Snapshot ((\d{4}-\d{2}-\d{2})_\w+) \((\w+)\) veröffentlicht", text):
            out["snapshot_id"], out["stand"], out["vollstaendigkeit"] = m.group(1), m.group(2), m.group(3)
        if m := re.search(r"Kursstichtag (\d{4}-\d{2}-\d{2})", text):
            out["stichtag"] = m.group(1)
        if m := re.search(r"Kursabruf: (\d+) Notierungen offen \(davon (\d+) erneut[^)]*\), (\d+) bereits erledigt", text):
            out["offen"], out["erneut"], out["checkpoint"] = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if m := re.search(r"Chart-Abruf: (\d+) Abrufe in (\d+) s \(([\d.]+) je Sekunde; ([^)]*)\)([^\n]*)", text):
            out["abrufe"], out["abruf_sekunden"], out["je_sekunde"] = int(m.group(1)), int(m.group(2)), float(m.group(3))
            out["gleichzeitig"] = "gleichzeitig über 2 Hosts" in m.group(4)
            rest = m.group(5)
            out["rueckfall_drosselung"] = "Drosselung (HTTP 429) nach" in rest
            if k := re.search(r"(\d+) × HTTP 429", rest):
                out["http_429_wiederholt"] = int(k.group(1))
        if m := re.search(r"Kursabruf beendet: (\d+) aktualisiert", text):
            out["aktualisiert"] = int(m.group(1))
    return out


def fetch_status() -> dict | None:
    try:
        stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d%H%M%S")
        request = urllib.request.Request(f"{SITE}data/status.json?kontrolle={stamp}", headers={"User-Agent": "tr-aktienvergleich-kontrolle"})
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read())
    except Exception:  # noqa: BLE001 - außerhalb von GitHub Actions oft nicht erreichbar
        return None


NIGHT_WINDOW_MINUTES = 30  # so lange darf es vom Anlegen des Nachtlaufs bis zum Anlegen des täglichen Laufs dauern


def night_run_for(created: dt.datetime) -> dict | None:
    """Der Lauf von „Nachtlauf“, der einen täglichen Lauf (angelegt ``created``) gestartet hat: der letzte, der höchstens
    ``NIGHT_WINDOW_MINUTES`` vorher angelegt wurde. Ab 1.18 zählt nur ein Nachtlauf mit Auslöser „schedule“ (GitHubs
    Zeitplan) als zeitgesteuert – ein von Hand oder über den externen Auslöser gestarteter Nachtlauf („workflow_dispatch“)
    startet den täglichen Lauf ebenfalls als „github-actions[bot]“ (von Hand so am 24.10.2026, 10:26 UTC)."""
    runs = api(f"repos/{REPO}/actions/workflows/nachtlauf.yml/runs?per_page=50").get("workflow_runs", [])
    earlier = [
        r for r in runs
        if (t := parse_time(r.get("created_at"))) is not None and dt.timedelta(0) <= created - t <= dt.timedelta(minutes=NIGHT_WINDOW_MINUTES)
    ]
    return max(earlier, key=lambda r: r["created_at"]) if earlier else None


def evaluate(run_id: int) -> dict:
    run = api(f"repos/{REPO}/actions/runs/{run_id}")
    jobs = {j["name"]: j for j in api(f"repos/{REPO}/actions/runs/{run_id}/jobs?per_page=50").get("jobs", [])}
    berechnen = jobs.get("berechnen") or {}
    notices = api(f"repos/{REPO}/check-runs/{berechnen['id']}/annotations") if berechnen.get("id") else []
    report = run_report([n for n in notices if n.get("annotation_level") == "notice"])
    actor = ((run.get("triggering_actor") or run.get("actor") or {}).get("login")) or ""
    trigger = "zeitplan" if run.get("event") == "schedule" else "nachtlauf" if run.get("event") == "workflow_dispatch" and actor == "github-actions[bot]" else "von Hand"
    created = parse_time(run.get("created_at"))
    started, finished = parse_time(berechnen.get("started_at")), parse_time(berechnen.get("completed_at"))
    minutes = round((finished - started).total_seconds() / 60, 1) if started and finished else None
    delay = None
    night = None
    if trigger == "nachtlauf" and created:
        night = night_run_for(created)
        if night is None:
            trigger = "nachtlauf ohne gefundenen Auslöser"
        elif night.get("event") != "schedule":
            trigger = "nachtlauf ohne zeitplan"  # von Hand oder über den externen Auslöser (workflow_dispatch)
        else:
            night_created = parse_time(night.get("created_at"))
            planned = night_created.replace(hour=NIGHT_UTC[0], minute=NIGHT_UTC[1], second=0, microsecond=0)
            if planned > night_created:
                planned -= dt.timedelta(days=1)
            delay = round((night_created - planned).total_seconds() / 60)
    status = fetch_status() if os.environ.get("GITHUB_ACTIONS") == "true" else None
    stand = report.get("stand")
    nxt = (status or {}).get("naechster_kursstand") or {}
    night_text = f" (Nachtlauf {night['id']}, Auslöser {night.get('event')})" if night else ""

    def job_ok(name: str) -> bool | None:
        job = jobs.get(name)
        return None if job is None else job.get("conclusion") == "success"

    criteria = [
        ("zeitgesteuert (Zeitplan oder Nachtlauf über den Zeitplan)", trigger in ("zeitplan", "nachtlauf"),
         trigger + night_text + (f", {delay} min nach 22:37 UTC" if delay is not None else "")),
        ("neuer Kursstand vollständig veröffentlicht", report.get("status") == "veroeffentlicht" and report.get("vollstaendigkeit") == "vollständig", f"{report.get('status', '–')}, Stand {stand or '–'} ({report.get('vollstaendigkeit', '–')})"),
        (f"Kurse aller Notierungen abgerufen (≥ {MIN_LISTINGS:,} offen)".replace(",", "."), (report.get("offen") or 0) >= MIN_LISTINGS, f"{report.get('offen', '–')} offen, {report.get('checkpoint', '–')} aus dem Checkpoint"),
        (f"gleichzeitig über 2 Hosts, ≥ {MIN_RATE:.0f} je Sekunde".replace(".", ","), bool(report.get("gleichzeitig")) and (report.get("je_sekunde") or 0) >= MIN_RATE and (report.get("abrufe") or 0) >= MIN_LISTINGS,
         f"{de(report.get('abrufe'))} Abrufe in {de(report.get('abruf_sekunden'))} s = {de(report.get('je_sekunde'))} je Sekunde"),
        ("kein Rückfall wegen Drosselung (HTTP 429)", report.get("abrufe") is not None and not report.get("rueckfall_drosselung"), f"{report.get('http_429_wiederholt', 0)} × HTTP 429 mit Wiederholung" + ("; Rückfall auf einzeln" if report.get("rueckfall_drosselung") else "")),
        (f"Job „berechnen“ ≤ {MAX_MINUTES} min", minutes is not None and minutes <= MAX_MINUTES, f"{de(minutes)} min" if minutes is not None else "–"),
        ("Kennzahlen, Signale und Website bereitgestellt", bool(job_ok("kennzahlen")) and bool(job_ok("signale-bereitstellen")), f"kennzahlen {jobs.get('kennzahlen', {}).get('conclusion')}, bereitstellen {jobs.get('signale-bereitstellen', {}).get('conclusion')}"),
    ]
    if status is not None:
        signals = status.get("signale") or {}
        # neuester Stand mit Schlusskursen: bei einem später von Hand gerechneten Zwischenstand dessen offizieller Stand
        intraday = status.get("zwischenstand") or {}
        latest = str(intraday.get("offizieller_stand") or status.get("latest_snapshot_id") or "")
        criteria.append(
            ("status.json: neuer Kursstand und nächster danach",
             status.get("last_price_session") == stand and latest == str(report.get("snapshot_id") or "") and bool(nxt.get("datum")) and str(nxt.get("datum")) > str(stand or ""),
             f"Kursstand {status.get('last_price_session')}, Stand {latest or '–'}" + (" (unter dem Zwischenstand)" if intraday else "")
             + f", nächster {nxt.get('datum')} ab {nxt.get('ab_utc')}, Software {status.get('software_version')}")
        )
        # ab 1.18: Signale zum neuen Kursstand veröffentlicht (nicht nur der Job grün)
        criteria.append(
            ("status.json: Signale zum neuen Kursstand", signals.get("kursstand") == stand and bool(signals.get("aktien")),
             f"Signal-Stand {signals.get('id', '–')}, Kursstand {signals.get('kursstand', '–')}, {signals.get('aktien', '–')} Aktien")
        )
    passed = all(ok for _, ok, _ in criteria)
    return {
        "lauf": run_id,
        "angelegt_utc": run.get("created_at"),
        "ausloeser": trigger,
        "stand": stand,
        "bestanden": passed,
        "kriterien": [{"kriterium": name, "erfuellt": bool(ok), "ist": value} for name, ok, value in criteria],
        "werte": report,
    }


def official_runs_since(day: str) -> list[int]:
    """Läufe von „Täglicher Lauf“ seit ``day`` (UTC), älteste zuerst, die einen offiziellen Lauf enthalten (Notiz „Lauf: …“)."""
    runs = api(f"repos/{REPO}/actions/workflows/taeglich.yml/runs?per_page=100&created=%3E%3D{day}").get("workflow_runs", [])
    out = []
    for run in sorted(runs, key=lambda r: r["created_at"]):
        if run.get("status") != "completed":
            continue
        jobs = {j["name"]: j for j in api(f"repos/{REPO}/actions/runs/{run['id']}/jobs?per_page=50").get("jobs", [])}
        job = jobs.get("berechnen")
        if not job or job.get("conclusion") == "skipped":
            continue
        notes = api(f"repos/{REPO}/check-runs/{job['id']}/annotations")
        if any((n.get("title") or "").startswith("Lauf: ") for n in notes):
            out.append(run["id"])
    return out


def write(result: dict) -> list[str]:
    verdict = "bestanden" if result["bestanden"] else "nicht bestanden"
    kind = "zeitgesteuerter " if result["ausloeser"] in ("zeitplan", "nachtlauf") else ""
    lines = [f"{'✓' if c['erfuellt'] else '✗'} {c['kriterium']}: {c['ist']}" for c in result["kriterien"]]
    print(f"::notice title=Kontrolle Kurslauf {result['lauf']}: {verdict}::" + "%0A".join([f"{kind}Kurslauf, Stand {result['stand'] or '–'}, angelegt {result['angelegt_utc']}"] + [line.replace("%", "%25") for line in lines]))
    table = [f"### Lauf {result['lauf']}: {verdict}", "", f"Auslöser {result['ausloeser']}, Stand {result['stand'] or '–'}, angelegt {result['angelegt_utc']} (UTC)", "", "| Kriterium | erfüllt | Ist |", "|---|---|---|"]
    table += [f"| {c['kriterium']} | {'ja' if c['erfuellt'] else 'nein'} | {c['ist']} |" for c in result["kriterien"]]
    return table + [""]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lauf", type=int, help="Laufnummer des Workflows „Täglicher Lauf“")
    parser.add_argument("--seit", help="alle offiziellen Läufe ab diesem Tag (JJJJ-MM-TT, UTC) prüfen")
    parser.add_argument("--bericht", help="Ergebnis zusätzlich als JSON-Datei")
    args = parser.parse_args(argv)
    if args.lauf:
        ids = [args.lauf]
    elif args.seit:
        ids = official_runs_since(args.seit)
    else:
        latest = official_runs_since((dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=3)).date().isoformat())
        ids = latest[-1:]
    results = [evaluate(run_id) for run_id in ids]
    first = next((r for r in results if r["ausloeser"] in ("zeitplan", "nachtlauf") and (r["werte"].get("offen") or 0) >= MIN_LISTINGS), None)
    if args.seit and not args.lauf:
        if first is None:
            headline = f"Seit {args.seit} noch kein zeitgesteuerter Lauf mit Abruf aller Notierungen ({len(results)} offizielle Läufe geprüft)"
        else:
            headline = f"Erster zeitgesteuerter Lauf mit Abruf aller Notierungen seit {args.seit}: Lauf {first['lauf']} ({first['ausloeser']}, Stand {first['stand']}) – {'bestanden' if first['bestanden'] else 'nicht bestanden'}"
        print(f"::notice title=Kontrolle seit {args.seit}::{headline}")
    else:
        headline = "Kontrolle Kurslauf"
    table = [f"## {headline}", ""]
    for result in results:
        table += write(result)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write("\n".join(table) + "\n")
    else:
        print("\n".join(table))
    if args.bericht:
        Path(args.bericht).write_text(json.dumps({"laeufe": results, "erster_zeitgesteuerter_vollstaendiger": first["lauf"] if first else None}, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
