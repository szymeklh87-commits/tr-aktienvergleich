"""Vergleich vor der Umstellung des Kursabrufs (ab 1.17): Sammelabruf „spark“/„quote“ gegen Chart-Abruf und Zustand.

Simons Auftrag vom 24.10.2026: „Prüfe vor der Umstellung, ob Spark und Chart vergleichbare Kurswerte, Zeiträume und
Bereinigungen liefern.“ Das Skript ändert nichts – es lädt den verschlüsselten Zustand aus dem Release „datenstand“
(nur lesend), holt die letzten Tageskurse aller Notierungen gesammelt und eine Stichprobe einzeln über den Chart-Abruf
und zählt:

A. **Spark gegen gespeicherte Kurse** (alle Notierungen): gleiche Handelstage, Schlusskurse je Tag (bitgleich,
   ≤ 1e-6, ≤ 1e-4, ≤ 1 %, darüber), fehlende und zusätzliche Tage – je Börse.
B. **Spark gegen frischen Chart-Abruf** (Stichprobe): dasselbe einschließlich der neuesten Sitzung.
C. **Kursmeldung der neuesten Sitzung gegen die Tageskerze** (Stichprobe): Kurs gegen Schlusskurs, Umsatz, Eröffnung,
   Hoch und Tief – getrennt für „quote“ und die Meldung in der Spark-Antwort.
D. **Planung des Sammelabrufs** (``plan_increment``): Für jede Notierung der Stichprobe wird die gespeicherte Reihe
   vor der neuesten Sitzung abgeschnitten und geplant; die so gebaute Tageskerze wird Feld für Feld mit der des
   Chart-Abrufs verglichen. Für alle Notierungen: was der Sammelabruf jetzt täte (neu, aktuell, einzeln mit Grund).
E. **Dauer und Abrufe** je Weg, Drosselungen.

Ausgegeben werden nur Zählwerte und Börsencodes – keine Kurse, Namen, Kürzel oder ISINs (das Protokoll ist öffentlich).
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
from traktien.jobs.increment import ACTION_NEW, StoredTail, plan_increment, session_days  # noqa: E402
from traktien.jobs.state import GitHubReleaseStore, sync_down  # noqa: E402
from traktien.providers.base import NoDataError, ProviderError, ProviderThrottled  # noqa: E402
from traktien.providers.calendars import production_calendars  # noqa: E402
from traktien.providers.yahoo import QUOTE_FIELDS_BAR, YahooProvider  # noqa: E402
from traktien.store import repo  # noqa: E402
from traktien.store.db import connect  # noqa: E402
from traktien.util.timeutil import day_to_iso  # noqa: E402

BUCKETS = (("bitgleich", 0.0), ("bis_1e-9", 1e-9), ("bis_1e-6", 1e-6), ("bis_1e-4", 1e-4), ("bis_1_prozent", 1e-2))


def bucket(rel: float) -> str:
    if not math.isfinite(rel):
        return "ungueltig"
    for name, limit in BUCKETS:
        if rel <= limit:
            return name
    return "ueber_1_prozent"


def rel_diff(a: float, b: float) -> float:
    if not (math.isfinite(a) and math.isfinite(b)):
        return math.nan
    if a == b:
        return 0.0
    base = max(abs(a), abs(b))
    return abs(a - b) / base if base else math.nan


def notice(title: str, lines: list[str], level: str = "notice") -> None:
    body = "%0A".join(line.replace("%", "%25").replace("\n", " ") for line in lines)
    print(f"::{level} title={title}::{body}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-dir", default=None, help="vorhandener Zustand (sonst aus dem Release laden)")
    parser.add_argument("--chart-stichprobe", type=int, default=400)
    parser.add_argument("--bericht", default="kursabruf-vergleich.json")
    parser.add_argument("--max", type=int, default=0, help="nur so viele Notierungen (0 = alle)")
    args = parser.parse_args()

    started_all = time.monotonic()
    pipeline = load_pipeline_config()
    passphrase = os.environ.get("DATA_PASSPHRASE")
    state_dir = Path(args.state_dir) if args.state_dir else Path(tempfile.mkdtemp(prefix="zustand-"))
    if not args.state_dir:
        store = GitHubReleaseStore.from_env(tag=pipeline.get("github.release_tag", "datenstand"))
        t0 = time.monotonic()
        info = sync_down(store, state_dir, passphrase)
        if not info["database"]:
            print("::error::Kein Zustand im Release gefunden")
            return 1
        load_s = time.monotonic() - t0
    else:
        load_s = 0.0
    conn = connect(state_dir / "state.sqlite")
    calendars = production_calendars()
    now = dt.datetime.now(tz=dt.timezone.utc)
    grace = int(pipeline.get("stichtag.karenz_minuten_nach_schluss", 60))

    universe = repo.latest_universe(conn, data_mode="produktiv")
    members = repo.universe_members(conn, universe["id"]) if universe else {}
    refs = repo.reference_listings(conn)
    listings = [row for isin, row in refs.items() if isin in members and row["provider"] == "yahoo" and row["calendar_code"] and calendars.available(row["calendar_code"])]
    listings.sort(key=lambda r: r["provider_symbol"])
    if args.max:
        listings = listings[: args.max]
    codes = {row["calendar_code"] for row in listings}
    cutoff = determine_cutoff(codes, calendars, now, grace_minutes=grace)
    D = cutoff.cutoff_day
    report: dict = {"stichtag": day_to_iso(D), "notierungen": len(listings), "zustand_laden_s": round(load_s, 1)}

    tails: dict[int, StoredTail] = {}
    for row in listings:
        bars = repo.load_bars(conn, row["id"], int(row["data_revision"]), D - 60)
        tails[row["id"]] = StoredTail(bars["days"], bars["close"], bars["quality"])
    last_days = Counter(int(t.last_day) if t.last_day is not None else None for t in tails.values())
    report["letzter_gespeicherter_tag"] = {("ohne" if k is None else str(k - D)): v for k, v in last_days.most_common(6)}

    provider = YahooProvider()
    symbols = [row["provider_symbol"] for row in listings]

    # ---------------------------------------------------------------- E: Sammelabrufe
    recent = provider.fetch_recent(symbols, budget_s=1200)
    report["spark"] = {
        "abrufe": recent.requests,
        "sekunden": round(recent.seconds, 1),
        "mit_daten": len(recent.bars),
        "ohne_daten": dict(Counter(recent.missing.values()).most_common(8)),
        "gedrosselt": recent.throttled,
        "variante": (recent.endpoint or "").split("/")[2:6],
        "felder_der_meldung": dict(sorted(recent.meta_fields.items())),
    }
    t0 = time.monotonic()
    quotes = provider.fetch_quotes(symbols, budget_s=900, fields=QUOTE_FIELDS_BAR, spark_fallback=False)
    report["quote"] = {
        "abrufe": quotes.quote_requests,
        "sekunden": round(time.monotonic() - t0, 1),
        "mit_daten": len(quotes.quotes),
        "ohne_daten": dict(Counter(quotes.missing.values()).most_common(6)),
        "gedrosselt": quotes.throttled,
        "mit_eroeffnung": sum(1 for q in quotes.quotes.values() if math.isfinite(q.day_open)),
        "mit_hoch_tief": sum(1 for q in quotes.quotes.values() if math.isfinite(q.day_high) and math.isfinite(q.day_low)),
        "mit_umsatz": sum(1 for q in quotes.quotes.values() if math.isfinite(q.volume)),
    }

    # ---------------------------------------------------------------- A: Spark gegen Zustand (alle)
    a_days = Counter()
    a_listings = Counter()
    a_by_code: dict[str, Counter] = defaultdict(Counter)
    plans_now = Counter()
    plan_sources = Counter()
    for row in listings:
        tail = tails[row["id"]]
        rb = recent.bars.get(row["provider_symbol"])
        final = session_final_checker(calendars, row["calendar_code"], now, grace)
        quote = quotes.quotes.get(row["provider_symbol"])
        plan = plan_increment(tail, rb, quote, tz_name=row["exchange_tz"], session_final=final, symbol=row["provider_symbol"])
        plans_now[f"{plan.action}:{plan.reason}"] += 1
        for key, value in plan.sources.items():
            plan_sources[f"{key}:{value}"] += 1
        if rb is None or tail.last_day is None:
            continue
        days = session_days(rb.timestamps, rb.exchange_tz or row["exchange_tz"])
        spark_map = {int(d): float(c) for d, c in zip(days.tolist(), rb.close.tolist()) if math.isfinite(c) and c > 0}
        first = min(spark_map) if spark_map else None
        worst = "bitgleich"
        any_compared = False
        for k, day in enumerate(tail.days.tolist()):
            if first is None or day < first or day > tail.last_day:
                continue
            if day not in spark_map:
                a_days["tag_fehlt_in_spark"] += 1
                a_by_code[row["calendar_code"]]["tag_fehlt"] += 1
                continue
            b = bucket(rel_diff(spark_map[day], float(tail.close[k])))
            a_days[b] += 1
            any_compared = True
            if b not in ("bitgleich", "bis_1e-9", "bis_1e-6"):
                a_by_code[row["calendar_code"]]["abweichung"] += 1
                worst = b if BUCKET_ORDER.index(b) > BUCKET_ORDER.index(worst) else worst
            elif BUCKET_ORDER.index(b) > BUCKET_ORDER.index(worst):
                worst = b
        stored_set = {int(d) for d in tail.days.tolist()}
        extra = sum(1 for d in spark_map if d <= tail.last_day and d not in stored_set and (first is None or d >= first))
        if extra:
            a_days["tag_nur_in_spark"] += extra
            a_by_code[row["calendar_code"]]["tag_nur_in_spark"] += extra
        if any_compared:
            a_listings[worst] += 1
    report["A_spark_gegen_zustand"] = {
        "tage": dict(a_days),
        "notierungen_schlechtester_tag": dict(a_listings),
        "je_boerse_auffaellig": {code: dict(c) for code, c in sorted(a_by_code.items()) if c},
    }
    report["D_planung_jetzt"] = {"entscheidungen": dict(plans_now.most_common()), "herkunft": dict(plan_sources)}

    # ---------------------------------------------------------------- B, C, D: Stichprobe mit Chart-Abruf
    rng = random.Random(20261024)
    by_code: dict[str, list] = defaultdict(list)
    for row in listings:
        if row["provider_symbol"] in recent.bars:
            by_code[row["calendar_code"]].append(row)
    sample: list = []
    total = sum(len(v) for v in by_code.values()) or 1
    for code, rows in sorted(by_code.items()):
        take = max(3, round(args.chart_stichprobe * len(rows) / total))
        sample += rng.sample(rows, min(take, len(rows)))
    b_days = Counter()
    b_new = Counter()
    c_fields: dict[str, Counter] = defaultdict(Counter)
    d_plan = Counter()
    d_fields: dict[str, Counter] = defaultdict(Counter)
    chart_requests = 0
    chart_errors = Counter()
    t0 = time.monotonic()
    for row in sample:
        symbol = row["provider_symbol"]
        final = session_final_checker(calendars, row["calendar_code"], now, grace)
        try:
            history = provider.fetch_history(symbol, D - 45, D + 3, session_final=final)
            chart_requests += 1
        except ProviderThrottled:
            chart_errors["gedrosselt"] += 1
            break
        except (NoDataError, ProviderError, ConnectionError, ValueError) as exc:
            chart_requests += 1
            chart_errors[type(exc).__name__] += 1
            continue
        rb = recent.bars[symbol]
        days = session_days(rb.timestamps, rb.exchange_tz or row["exchange_tz"])
        spark_map = {int(d): float(c) for d, c in zip(days.tolist(), rb.close.tolist()) if math.isfinite(c) and c > 0}
        chart_map = {int(d): k for k, d in enumerate(history.days.tolist())}
        first = min(spark_map) if spark_map else None
        for day, k in chart_map.items():
            if first is None or day < first:
                continue
            if day not in spark_map:
                b_days["tag_fehlt_in_spark"] += 1
                continue
            b_days[bucket(rel_diff(spark_map[day], float(history.close[k])))] += 1
        b_days["tag_nur_in_spark"] += sum(1 for d in spark_map if d not in chart_map and (not chart_map or d <= max(chart_map)))
        if not len(history.days):
            continue
        last = int(history.days[-1])
        k = len(history.days) - 1
        b_new["letzte_sitzung_in_spark" if last in spark_map else "letzte_sitzung_fehlt_in_spark"] += 1
        # C: Kursmeldungen gegen die Tageskerze der letzten Sitzung
        quote = quotes.quotes.get(symbol)
        if quote is not None:
            c_fields["quote_tag"]["gleich" if quote.session_day == last else "anders"] += 1
            if quote.session_day == last:
                c_fields["quote_kurs_gegen_schluss"][bucket(rel_diff(quote.price, float(history.close[k])))] += 1
                c_fields["quote_umsatz"][bucket(rel_diff(quote.volume, float(history.volume[k])))] += 1
                c_fields["quote_eroeffnung"][bucket(rel_diff(quote.day_open, float(history.open[k])))] += 1
                c_fields["quote_hoch"][bucket(rel_diff(quote.day_high, float(history.high[k])))] += 1
                c_fields["quote_tief"][bucket(rel_diff(quote.day_low, float(history.low[k])))] += 1
        else:
            c_fields["quote_tag"]["keine_meldung"] += 1
        if rb.last_time is not None:
            meta_day = int(session_days([rb.last_time], rb.exchange_tz or row["exchange_tz"])[0])
            c_fields["spark_meldung_tag"]["gleich" if meta_day == last else "anders"] += 1
            if meta_day == last:
                c_fields["spark_kurs_gegen_schluss"][bucket(rel_diff(rb.last_price, float(history.close[k])))] += 1
                c_fields["spark_umsatz"][bucket(rel_diff(rb.last_volume, float(history.volume[k])))] += 1
                c_fields["spark_hoch"][bucket(rel_diff(rb.last_high, float(history.high[k])))] += 1
                c_fields["spark_tief"][bucket(rel_diff(rb.last_low, float(history.low[k])))] += 1
        # D: gespeicherte Reihe vor der letzten Sitzung abschneiden und planen
        tail = tails[row["id"]]
        keep = tail.days < last
        cut = StoredTail(tail.days[keep], tail.close[keep], tail.quality[keep])
        if cut.last_day is None:
            d_plan["ohne_gespeicherte_reihe"] += 1
            continue
        plan = plan_increment(cut, rb, quote, tz_name=row["exchange_tz"], session_final=final, symbol=symbol)
        d_plan[f"{plan.action}:{plan.reason}"] += 1
        if plan.action == ACTION_NEW and plan.history is not None and plan.new_day == last:
            h = plan.history
            d_fields["schluss"][bucket(rel_diff(float(h.close[0]), float(history.close[k])))] += 1
            d_fields["umsatz"][bucket(rel_diff(float(h.volume[0]), float(history.volume[k])))] += 1
            d_fields["eroeffnung"][bucket(rel_diff(float(h.open[0]), float(history.open[k])))] += 1
            d_fields["hoch"][bucket(rel_diff(float(h.high[0]), float(history.high[k])))] += 1
            d_fields["tief"][bucket(rel_diff(float(h.low[0]), float(history.low[k])))] += 1
            d_fields["zeitpunkt"]["gleich" if h.bar_times_utc[0] == history.bar_times_utc[k] else "anders"] += 1
        elif plan.action == ACTION_NEW:
            d_fields["neuer_tag"]["anderer_tag_als_chart"] += 1
    chart_s = time.monotonic() - t0
    report["stichprobe"] = {"notierungen": len(sample), "chart_abrufe": chart_requests, "chart_sekunden": round(chart_s, 1), "chart_fehler": dict(chart_errors)}
    report["B_spark_gegen_chart"] = {"tage": dict(b_days), "letzte_sitzung": dict(b_new)}
    report["C_meldung_gegen_tageskerze"] = {name: dict(c) for name, c in c_fields.items()}
    report["D_planung_gegen_chart"] = {"entscheidungen": dict(d_plan.most_common()), "felder": {name: dict(c) for name, c in d_fields.items()}}
    report["gesamt_sekunden"] = round(time.monotonic() - started_all, 1)
    conn.close()

    Path(args.bericht).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        f"Stichtag {report['stichtag']}, {len(listings)} Notierungen; letzter gespeicherter Tag (Abstand zum Stichtag): {report['letzter_gespeicherter_tag']}",
        f"Spark (1 Monat, ≤20 je Abruf): {recent.requests} Abrufe in {recent.seconds:.0f} s, mit Daten {len(recent.bars)}, ohne {dict(Counter(recent.missing.values()).most_common(4))}, gedrosselt {recent.throttled}",
        f"Quote (≤150 je Abruf): {quotes.quote_requests} Abrufe in {report['quote']['sekunden']:.0f} s, mit Daten {len(quotes.quotes)}, Eröffnung {report['quote']['mit_eroeffnung']}, Hoch/Tief {report['quote']['mit_hoch_tief']}, Umsatz {report['quote']['mit_umsatz']}",
        f"A Spark gegen gespeicherte Kurse (Tage): {dict(a_days)}; Notierungen nach schlechtestem Tag: {dict(a_listings)}",
        f"B Spark gegen Chart, Stichprobe {len(sample)} ({chart_requests} Chart-Abrufe in {chart_s:.0f} s): Tage {dict(b_days)}; letzte Sitzung {dict(b_new)}",
        "C Meldung gegen Tageskerze: " + "; ".join(f"{name} {dict(c)}" for name, c in c_fields.items()),
        f"D Planung gegen Chart: {dict(d_plan.most_common())}; Felder: " + "; ".join(f"{name} {dict(c)}" for name, c in d_fields.items()),
        f"D Planung jetzt (alle): {dict(plans_now.most_common(10))}",
        f"Spark-Felder der Meldung: {', '.join(sorted(recent.meta_fields))}",
    ]
    notice("Kursabruf-Vergleich (nur Zählwerte)", lines)
    return 0


BUCKET_ORDER = ["bitgleich", "bis_1e-9", "bis_1e-6", "bis_1e-4", "bis_1_prozent", "ueber_1_prozent", "ungueltig"]

if __name__ == "__main__":
    sys.exit(main())
