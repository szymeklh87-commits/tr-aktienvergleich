"""Messlauf ohne Schreibzugriff (ab 1.17): Wie lange braucht der Chart-Abruf aller Notierungen gleichzeitig über zwei Hosts?

Simons Auftrag vom 24.10.2026: „Miss die tatsächliche Laufzeit.“ Das Skript lädt den verschlüsselten Zustand aus dem
Release „datenstand“ nur lesend, plant je Notierung denselben Abruf wie der tägliche Lauf (ab dem letzten gespeicherten
Tag minus Überlappung, ohne Kursreihe 400 Tage) und holt alle Notierungen über ``YahooProvider.fetch_histories`` – also
genau den Weg, den der tägliche Lauf ab 1.17 nimmt. Gespeichert oder hochgeladen wird nichts.

Gemessen und gezählt:

1. **Tempo**: zuerst eine Stichprobe nacheinander wie bis 1.16 (2,5 Abrufe je Sekunde über einen Host), dann der Rest
   gleichzeitig mit den gewählten Einstellungen – Dauer, Abrufe je Sekunde, HTTP 429, ob und wann auf den alten Weg
   zurückgeschaltet wurde, und die daraus folgende Dauer für alle Notierungen.
2. **Ergebnis je Notierung**: Kurse, keine Daten (404 oder ohne gültige Kerze), Fehler.
3. **Gleiche Daten wie gespeichert**: Schlusskurs und Umsatz der älteren Tage (vor dem letzten gespeicherten Tag)
   und des letzten gespeicherten Tags gegen den Zustand.
4. **Gleiche Daten über beide Hosts**: eine Stichprobe der über den zweiten Host geholten Notierungen noch einmal über
   den ersten Host, Feld für Feld.

Ausgegeben werden nur Zählwerte, Zeiten und Börsencodes – keine Kurse, Namen, Kürzel oder ISINs (das Protokoll ist
öffentlich). GitHub zeigt höchstens zehn Hinweise je Schritt; das Skript schreibt vier.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import random
import sys
import tempfile
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from traktien.config import load_pipeline_config  # noqa: E402
from traktien.jobs.cutoff import determine_cutoff, session_final_checker  # noqa: E402
from traktien.jobs.state import GitHubReleaseStore, sync_down  # noqa: E402
from traktien.providers.base import HistoryFetchStats, HistoryJob, NoDataError, ProviderThrottled  # noqa: E402
from traktien.providers.calendars import production_calendars  # noqa: E402
from traktien.providers.yahoo import BASE, CHART_HOSTS, YahooProvider  # noqa: E402
from traktien.store import repo  # noqa: E402
from traktien.store.db import connect  # noqa: E402
from traktien.util.timeutil import date_to_day, day_to_iso  # noqa: E402

BUCKETS = (("bitgleich", 0.0), ("bis_1e-9", 1e-9), ("bis_1e-6", 1e-6), ("bis_1e-4", 1e-4), ("bis_1_prozent", 1e-2), ("bis_5_prozent", 0.05), ("bis_20_prozent", 0.2))


def bucket(a: float, b: float) -> str:
    if not (math.isfinite(a) and math.isfinite(b)):
        return "beide_leer" if not (math.isfinite(a) or math.isfinite(b)) else "einer_leer"
    if a == b:
        return "bitgleich"
    base = max(abs(a), abs(b))
    rel = abs(a - b) / base if base else math.inf
    for name, limit in BUCKETS[1:]:
        if rel <= limit:
            return name
    return "ueber_20_prozent"


def notice(title: str, lines: list[str], level: str = "notice") -> None:
    body = "%0A".join(line.replace("%", "%25").replace("\n", " ") for line in lines)
    print(f"::{level} title={title}::{body}")


def kind(outcome) -> str:
    if isinstance(outcome, ProviderThrottled):
        return "gedrosselt"
    if isinstance(outcome, NoDataError):
        return "keine_daten_404" if "404" in str(outcome) else "keine_daten"
    if isinstance(outcome, Exception):
        return "fehler:" + type(outcome).__name__
    return "kurse"


def compare_with_stored(history, stored: dict, last_stored: int | None, counts: dict[str, Counter]) -> None:
    """Schlusskurs und Umsatz je gemeinsamem Tag gegen den Zustand (ältere Tage und letzter gespeicherter Tag getrennt)."""
    if last_stored is None:
        counts["ohne_gespeicherte_reihe"]["notierungen"] += 1
        return
    index = {int(d): k for k, d in enumerate(stored["days"].tolist())}
    for k, day in enumerate(history.days.tolist()):
        day = int(day)
        if day > last_stored:
            counts["neue_tage"]["anzahl"] += 1
            continue
        j = index.get(day)
        if j is None:
            counts["tag_nur_im_abruf"]["anzahl"] += 1
            continue
        part = "letzter_tag" if day == last_stored else "aeltere_tage"
        counts[f"schluss_{part}"][bucket(float(history.close[k]), float(stored["close"][j]))] += 1
        counts[f"umsatz_{part}"][bucket(float(history.volume[k]), float(stored["volume"][j]))] += 1


def same_history(a, b) -> dict[str, str]:
    """Feldvergleich zweier Kursreihen derselben Notierung (über zwei Hosts geholt)."""
    out: dict[str, str] = {}
    if a.days.tolist() != b.days.tolist():
        common = sorted(set(a.days.tolist()) & set(b.days.tolist()))
        out["tage"] = "anders"
    else:
        common = a.days.tolist()
        out["tage"] = "gleich"
    ia = {int(d): k for k, d in enumerate(a.days.tolist())}
    ib = {int(d): k for k, d in enumerate(b.days.tolist())}
    last = common[-1] if common else None
    for field in ("close", "open", "high", "low", "volume"):
        older = "bitgleich"
        newest = "bitgleich"
        for day in common:
            x, y = float(getattr(a, field)[ia[day]]), float(getattr(b, field)[ib[day]])
            same = (x == y) or (math.isnan(x) and math.isnan(y))
            if not same:
                if day == last:
                    newest = "anders"
                else:
                    older = "anders"
        out[f"{field}_aeltere"] = older
        out[f"{field}_neuester"] = newest
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-dir", default=None)
    parser.add_argument("--gleichzeitig", type=int, default=4)
    parser.add_argument("--abstand", type=float, default=0.25, help="Mindestabstand je Host in Sekunden")
    parser.add_argument("--nacheinander", type=int, default=300, help="so viele zuerst nacheinander wie bis 1.16")
    parser.add_argument("--hosts-stichprobe", type=int, default=200)
    parser.add_argument("--max", type=int, default=0, help="nur so viele Notierungen (0 = alle)")
    parser.add_argument("--bericht", default="kursabruf-tempo.json")
    args = parser.parse_args()

    pipeline = load_pipeline_config()
    state_dir = Path(args.state_dir) if args.state_dir else Path(tempfile.mkdtemp(prefix="zustand-"))
    t0 = time.monotonic()
    if not args.state_dir:
        store = GitHubReleaseStore.from_env(tag=pipeline.get("github.release_tag", "datenstand"))
        info = sync_down(store, state_dir, os.environ.get("DATA_PASSPHRASE"))
        if not info["database"]:
            print("::error::Kein Zustand im Release gefunden")
            return 1
    load_s = time.monotonic() - t0
    conn = connect(state_dir / "state.sqlite")
    calendars = production_calendars()
    now = dt.datetime.now(tz=dt.timezone.utc)
    grace = int(pipeline.get("stichtag.karenz_minuten_nach_schluss", 60))
    initial_days = int(pipeline.get("abruf.erstimport_kalendertage", 400))
    overlap = int(pipeline.get("abruf.inkrementell_ueberlappung_tage", 10))

    universe = repo.latest_universe(conn, data_mode="produktiv")
    members = repo.universe_members(conn, universe["id"]) if universe else {}
    refs = repo.reference_listings(conn)
    rows = [row for isin, row in refs.items() if isin in members and row["provider"] == "yahoo" and row["calendar_code"] and calendars.available(row["calendar_code"])]
    broken = set()
    for code in sorted({row["calendar_code"] for row in rows}):
        try:
            calendars.session_close_utc(code, date_to_day(now.date()))
        except Exception:  # noqa: BLE001 - Kalender mit dieser Bibliotheksversion nicht ladbar
            broken.add(code)
    rows = [row for row in rows if row["calendar_code"] not in broken]
    rows.sort(key=lambda r: r["provider_symbol"])
    if args.max:
        rows = rows[: args.max]
    D = determine_cutoff({row["calendar_code"] for row in rows}, calendars, now, grace_minutes=grace).cutoff_day

    finals: dict = {}
    jobs: list[HistoryJob] = []
    stored: list[dict] = []
    last_stored: list[int | None] = []
    full = 0
    for row in rows:
        code = row["calendar_code"]
        if code not in finals:
            finals[code] = session_final_checker(calendars, code, now, grace)
        revision = int(row["data_revision"])
        first_day, last_day, count = repo.bar_range(conn, row["id"], revision)
        if count == 0 or last_day is None:
            start = D - initial_days
            full += 1
        else:
            start = int(last_day) - overlap
        jobs.append(HistoryJob(row["provider_symbol"], start, D + 3, finals[code]))
        stored.append(repo.load_bars(conn, row["id"], revision, start - 5))
        last_stored.append(None if last_day is None else int(last_day))

    provider = YahooProvider()
    split = min(max(0, args.nacheinander), len(jobs))
    stages = []
    outcomes: list = [None] * len(jobs)
    kinds_by_stage: dict[str, Counter] = {}
    for name, part, workers in (("nacheinander", range(0, split), 1), ("gleichzeitig", range(split, len(jobs)), args.gleichzeitig)):
        part_jobs = [jobs[k] for k in part]
        if not part_jobs:
            continue
        stats = HistoryFetchStats()
        started = time.monotonic()
        kinds = Counter()
        stopped = False
        generator = provider.fetch_histories(part_jobs, workers=workers, interval_s=args.abstand, stats=stats)
        for k, outcome in generator:
            outcomes[part.start + k] = outcome
            kinds[kind(outcome)] += 1
            if isinstance(outcome, ProviderThrottled):
                stopped = True
                break
        generator.close()
        elapsed = time.monotonic() - started
        kinds_by_stage[name] = kinds
        stages.append(
            {
                "art": name,
                "notierungen": len(part_jobs),
                "abrufe": stats.requests,
                "sekunden": round(elapsed, 1),
                "je_sekunde": round(stats.requests / elapsed, 2) if elapsed else None,
                "gleichzeitig": stats.workers,
                "hosts": stats.hosts,
                "abstand_s": stats.interval_s,
                "http_429": stats.http_429,
                "drosselung_nach": stats.throttled_after,
                "danach_einzeln": stats.careful,
                "abgebrochen_wegen_drosselung": stopped,
            }
        )
        if stopped:
            break

    # Vergleich mit dem Zustand
    stored_counts: dict[str, Counter] = defaultdict(Counter)
    for k, outcome in enumerate(outcomes):
        if outcome is None or isinstance(outcome, Exception):
            continue
        compare_with_stored(outcome, stored[k], last_stored[k], stored_counts)

    # Gleiche Daten über beide Hosts: über den zweiten Host geholte Notierungen noch einmal über den ersten
    rng = random.Random(20261024)
    second = [k for k in range(split, len(jobs)) if (k - split) % len(CHART_HOSTS) == 1 and outcomes[k] is not None and not isinstance(outcomes[k], Exception)]
    sample = rng.sample(second, min(args.hosts_stichprobe, len(second)))
    host_counts: dict[str, Counter] = defaultdict(Counter)
    host_errors = Counter()
    t1 = time.monotonic()
    for k in sample:
        again = provider._history_from_host(jobs[k], BASE)
        if isinstance(again, Exception):
            host_errors[kind(again)] += 1
            continue
        for field, verdict in same_history(outcomes[k], again).items():
            host_counts[field][verdict] += 1
    host_s = time.monotonic() - t1

    total_requests = sum(s["abrufe"] for s in stages)
    total_seconds = sum(s["sekunden"] for s in stages)
    par = next((s for s in stages if s["art"] == "gleichzeitig"), None)
    seq = next((s for s in stages if s["art"] == "nacheinander"), None)
    report = {
        "stichtag": day_to_iso(D),
        "notierungen": len(jobs),
        "davon_voller_abruf": full,
        "zustand_laden_s": round(load_s, 1),
        "kalender_nicht_ladbar": sorted(broken),
        "stufen": stages,
        "ergebnis_je_stufe": {name: dict(c) for name, c in kinds_by_stage.items()},
        "gegen_zustand": {name: dict(c) for name, c in stored_counts.items()},
        "beide_hosts": {"stichprobe": len(sample), "sekunden": round(host_s, 1), "felder": {name: dict(c) for name, c in host_counts.items()}, "fehler": dict(host_errors)},
        "hochrechnung_alle_sekunden": round(len(jobs) / par["je_sekunde"], 0) if par and par["je_sekunde"] else None,
        "hochrechnung_alle_nacheinander_sekunden": round(len(jobs) / seq["je_sekunde"], 0) if seq and seq["je_sekunde"] else None,
    }
    Path(args.bericht).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    def stage_text(s):
        return (
            f"{s['art']}: {s['abrufe']} Abrufe in {s['sekunden']} s = {s['je_sekunde']} je Sekunde "
            f"({s['gleichzeitig']} gleichzeitig, {s['hosts']} Host(s), Abstand {s['abstand_s']} s); HTTP 429: {s['http_429']}"
            + (f", Drosselung nach {s['drosselung_nach']} Abrufen, danach {s['danach_einzeln']} einzeln" if s["drosselung_nach"] is not None else "")
            + (" – abgebrochen (auch einzeln gedrosselt)" if s["abgebrochen_wegen_drosselung"] else "")
        )

    lines = [f"Stichtag {report['stichtag']}, {len(jobs)} Notierungen ({full} mit vollem Abruf), Zustand geladen in {report['zustand_laden_s']} s"]
    lines += [stage_text(s) for s in stages]
    lines.append(f"zusammen {total_requests} Abrufe in {round(total_seconds)} s")
    if report["hochrechnung_alle_sekunden"]:
        lines.append(f"Hochrechnung für alle {len(jobs)}: gleichzeitig {round(report['hochrechnung_alle_sekunden'] / 60, 1)} min" + (f", nacheinander {round(report['hochrechnung_alle_nacheinander_sekunden'] / 60, 1)} min" if report["hochrechnung_alle_nacheinander_sekunden"] else ""))
    notice("Kursabruf-Tempo 1/4 (nur Zählwerte)", lines)
    notice("Kursabruf-Tempo 2/4 (nur Zählwerte)", [f"Ergebnis je Stufe: {json.dumps(report['ergebnis_je_stufe'], ensure_ascii=False)}"])
    notice("Kursabruf-Tempo 3/4 (nur Zählwerte)", [f"gegen gespeicherte Kurse: {json.dumps(report['gegen_zustand'], ensure_ascii=False)}"])
    notice("Kursabruf-Tempo 4/4 (nur Zählwerte)", [f"zweiter gegen ersten Host, Stichprobe {len(sample)} in {round(host_s)} s: {json.dumps(report['beide_hosts']['felder'], ensure_ascii=False)}; Fehler {dict(host_errors)}"])
    print(json.dumps({k: v for k, v in report.items() if k not in ("gegen_zustand",)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001 - Abbruchgrund als Hinweis, ohne Inhalte
        import traceback

        frames = [f"{Path(f.filename).name}:{f.lineno}" for f in traceback.extract_tb(exc.__traceback__) if "tr-aktienvergleich" in f.filename or "traktien" in f.filename or "tests" in f.filename]
        print(f"::error title=Kursabruf-Tempo abgebrochen::{type(exc).__name__} bei {' > '.join(frames[-6:])}")
        raise
