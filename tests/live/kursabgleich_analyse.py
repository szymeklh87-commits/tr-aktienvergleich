"""Kursabgleich mit den amtlichen Kursarchiven der Börsen – Belege aus echten Daten (ab 1.20.0, Prüfskript).

Simons Auftrag vom 25.10.2026, 19:31 Uhr (erneut 31.10.2026, 07:34 Uhr): „Behebe jetzt die Ursachen der Kursabweichungen und
ihre Auswirkungen auf die Ranglisten. … Zeige je Fall den bisherigen Kurs, den Börsenkurs, Aktie, Handelsplatz, Datum und die
genaue Kursdefinition. Kläre, weshalb die Werte abweichen und welcher Wert zur Berechnung der App passt.“

Dieses Skript wendet die Auswahlregel des täglichen Laufs (``traktien.analytics.kursabgleich``, Regel ``kursabgleich-1.0``) auf
einen veröffentlichten Stand an – über den Entschlüsselungsweg der unabhängigen Nachrechnung, nur in GitHub Actions:

1. Ranglisten des Stands: je Aktie Plätze unter den ersten 10 und 20 sowie Plätze 1; Aktien unter den ersten 20 je Börse.
2. Amtliche Quellen: **alle** Aktien an XWAR gegen das Notierungsarchiv der GPW bzw. die Tagesstatistik der NewConnect (eine
   Datei je Sitzung für alle Aktien), **alle** Aktien an XCNQ gegen die „Daily Market Summary“ der CSE, die Aktien an XTSE/XTSX
   und XNAS unter den ersten 20 einer Rangliste gegen TMX bzw. den offiziellen Schlusskurs von Nasdaq (NOCP).
3. Je Notierung die Einordnung aller Tage und die Entscheidung der Regel; Tage ohne Umsatz einzeln ausgewertet: Wert der Börse
   gegen den letzten Schlusskurs mit Umsatz, Wert und Umsatz der Hauptquelle.
4. Wirkung: alle Ranglisten mit den Kursen nach der Regel unabhängig neu gerechnet (``kurse_ursachen.ranking_effects``) – je
   Quelle und gemeinsam; jede Rangliste mit anderem Platz 1 mit Auslöser.
5. US-Börsenzuordnung: jede Notierung an einer US-Börse gegen die Wertpapierliste von Nasdaq Trader (alle börsennotierten
   US-Werte mit Börse der Notierung) – OTC-Werte stehen dort nicht.

Öffentlich ausgegeben werden nur Buchstaben, Börsencodes, Zählwerte, Verhältnisse und Prozentwerte – keine Kurse, Namen,
Kürzel oder ISINs. Buchstaben A, B, … wie im Job „spitzenreiter“ (Aktien an XWAR, XTSE, XTSX unter den ersten 10, die mit den
meisten Plätzen 1 zuerst); Nasdaq-Aktien N1, N2, …; übrige Aktien an XWAR P1, P2, ….
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "backend"))

import kurse_absicherung as absicherung  # noqa: E402
import kurse_ursachen as ursachen  # noqa: E402
import nachrechnen  # noqa: E402
import spitzenreiter_boersen as spitzen  # noqa: E402
from traktien.analytics import kursabgleich as ka  # noqa: E402
from traktien.analytics.quality import SplitEvent  # noqa: E402
from traktien.providers import boersen  # noqa: E402
from traktien.providers.http import HttpClient  # noqa: E402

TOP = 20
NOCP_BUDGET = 330  # Nasdaq antwortet nach rund 430 Anfragen je Rechner nicht mehr
TMX_BUDGET = 400
MAX_ROWS = 60


STARTED = time.monotonic()
BUDGET_S = 34 * 60  # der Job darf 45 min laufen; danach werden Abrufe übersprungen (gezählt) und das Ergebnis ausgegeben


def progress(message: str) -> None:
    print(f"[{time.monotonic() - STARTED:6.0f} s] {message}", flush=True)


def over_budget(share: float = 1.0) -> bool:
    return time.monotonic() - STARTED > BUDGET_S * share


def iso(day: int) -> str:
    return nachrechnen._iso(int(day))


def rankings(stand) -> dict[tuple[int, str, int], list[int]]:
    """Je Rangliste (Zeitraum, Gruppe, Gewichtung) die ersten ``TOP`` Aktien (globale Indizes)."""
    out: dict[tuple[int, str, int], list[int]] = {}
    for h in range(1, 91):
        win = stand.get(f"windows/{h}.full.bin")
        stand.drop(f"windows/{h}.full.bin")
        orders = win["orders"]
        out[(h, "A", 0)] = [int(x) for x in (orders.get("v0") or [])[:TOP]]
        out[(h, "B", 0)] = [int(x) for x in (orders.get("v0l") or [])[:TOP]]
        for group, key in (("A", "u"), ("B", "ul")):
            for w, values in (orders.get(key) or {}).items():
                if str(w) != "0":
                    out[(h, group, int(w))] = [int(x) for x in values[:TOP]]
    return out


def listing_input(series: dict) -> ka.ListingInput:
    def arr(name):
        values = series.get(name)
        if values is None:
            return None
        return np.array([np.nan if x is None else float(x) for x in values], dtype=np.float64)

    splits = [SplitEvent(day=int(e["day"]), factor=float(e["factor"])) for e in (series.get("events") or []) if e.get("type") == "split"]
    return ka.ListingInput(
        days=np.array([int(x) for x in series.get("d") or []], dtype=np.int64),
        close=arr("c"), volume=arr("v"), open=arr("o"), high=arr("h"), low=arr("l"), close_raw=arr("c_raw"), splits=splits,
    )


def pct(x: float | None, digits: int = 2) -> str:
    return "–" if x is None else f"{100 * x:.{digits}f} %"


def run(stand, sid: str, http) -> dict:
    manifest = stand.get("manifest.bin")
    instruments = stand.get("instruments.bin")
    n = len(instruments["isin"])
    cutoff = int(manifest["cutoff_day"])
    keys = instruments.get("exchange_key") or [None] * n
    symbols = [str(s or "") for s in (instruments.get("symbol") or [None] * n)]
    names = instruments.get("name") or [None] * n
    units = instruments.get("price_unit") or instruments.get("currency") or [None] * n
    liquid = (instruments.get("turnover") or {}).get("liquid") or [False] * n
    min_trend = int((manifest.get("method") or {}).get("min_obs_trend", 15))
    report: dict = {"stand": sid, "stichtag": iso(cutoff), "regel": ka.RULE_VERSION, "quellen": {}, "faelle": [], "boersen_top": {}}

    lists = rankings(stand)
    top20: set[int] = set()
    top10: Counter = Counter()
    first: Counter = Counter()
    for order in lists.values():
        top20.update(order)
        for k, i in enumerate(order[:10]):
            top10[i] += 1
            first[i] += k == 0
    report["ranglisten"] = len(lists)
    by_exchange = Counter(keys[i] or "?" for i in top20)
    first_by_exchange = Counter(keys[order[0]] or "?" for order in lists.values() if order)
    report["boersen_top"] = {"erste_20": dict(by_exchange.most_common()), "platz1": dict(first_by_exchange.most_common())}

    # Buchstaben wie im Job „spitzenreiter“: Aktien an XWAR, XTSE, XTSX unter den ersten 10, die mit den meisten Plätzen 1 zuerst
    # (dieselbe Regel wie spitzenreiter_boersen.select_targets, ohne die Zeiträume ein zweites Mal zu lesen)
    old_targets = sorted((i for i in top10 if keys[i] in spitzen.SOURCES), key=lambda i: (-first[i], -top10[i], i))
    letters = {i: spitzen.letter(k) for k, i in enumerate(old_targets)}
    progress(f"Ranglisten gelesen: {len(lists)}; Aktien unter den ersten 20: {len(top20)}")
    # Nasdaq-Aktien: Börsenschlüssel XNAS oder Sammelschlüssel „US“ mit Nasdaq als Börse laut Wertpapierliste von Nasdaq Trader
    directory_status, directory = absicherung.fetch_listing(http)
    progress(f"Wertpapierliste von Nasdaq Trader: {directory_status}, {len(directory)} Kürzel")

    def nasdaq_listed(i: int) -> bool:
        entry = directory.get(absicherung.normalize(symbols[i])) if directory else None
        return keys[i] in ("XNAS", "US") and entry is not None and entry.get("boerse") == "nasdaq"

    nas = sorted((i for i in top20 if nasdaq_listed(i)), key=lambda i: (-first[i], -top10[i], i))
    for k, i in enumerate(nas):
        letters.setdefault(i, f"N{k + 1}")
    war_all = sorted((i for i in range(n) if keys[i] == "XWAR"), key=lambda i: (-first[i], -top10[i], i))
    extra = 0
    for i in war_all:
        if i not in letters:
            extra += 1
            letters[i] = f"P{extra}"

    def label(i) -> str:
        if i is None:
            return "–"
        if i not in letters:
            letters[i] = f"X{len(letters) + 1}"
        return letters[i]

    inputs: dict[int, ka.ListingInput] = {}

    def series_of(i: int) -> ka.ListingInput | None:
        if i in inputs:
            return inputs[i]
        name = f"series/{instruments['isin'][i]}.bin"
        if not stand.exists(name):
            return None
        s = stand.get(name)
        stand.drop(name)
        inputs[i] = listing_input(s)
        return inputs[i]

    results: dict[int, ka.ListingResult] = {}
    official_of: dict[int, dict] = {}

    # ---- Warschau: alle Aktien, Tagesdateien je Sitzung
    war = [i for i in war_all if series_of(i) is not None and len(inputs[i].days)]
    first_day = min((int(inputs[i].days.min()) for i in war), default=cutoff - 130)
    days = sorted({int(d) for i in war for d in inputs[i].days.tolist() if int(d) >= first_day})
    gpw_status, nc_status = Counter(), Counter()
    gpw: dict[str, dict[int, boersen.OfficialBar]] = defaultdict(dict)
    ncon: dict[str, dict[int, boersen.OfficialBar]] = defaultdict(dict)
    file_currency: dict[str, Counter] = defaultdict(Counter)  # Währung laut Datei der Börse (GPW: Spalte „Waluta“)
    started = time.monotonic()
    # GPW und NewConnect weisen Abrufe mit Browser-Kennung von GitHub Actions aus ab (31.10.2026) – Kennung der App
    plain = HttpClient(max_retries=1, timeout=20, min_interval=dict(boersen.MIN_INTERVAL))
    for n_day, day in enumerate(days):
        if over_budget(0.45):
            gpw_status["zeitbudget"] += 1
            nc_status["zeitbudget"] += 1
            continue
        if n_day % 20 == 0:
            progress(f"Warschau: Tag {n_day + 1} von {len(days)}; GPW {dict(gpw_status)}; NewConnect {dict(nc_status)}")
        f = boersen.fetch_gpw_day(plain, day)
        if f.status != "ok" and not f.status.startswith("ohne"):
            time.sleep(3)
            f = boersen.fetch_gpw_day(plain, day)
        gpw_status[f.status] += 1
        for isin, bar in f.bars.items():
            gpw[isin][day] = bar
            file_currency[isin][str((f.info.get(isin) or {}).get("currency") or "")] += 1
        g = boersen.fetch_newconnect_day(plain, day)
        nc_status[g.status] += 1
        for isin, bar in g.bars.items():
            ncon[isin][day] = bar
    progress(f"Warschau fertig: GPW {dict(gpw_status)}; NewConnect {dict(nc_status)}")
    report["quellen"]["gpw"] = {"tage": len(days), "status": dict(gpw_status), "aktien_in_dateien": len(gpw), "sekunden": round(time.monotonic() - started)}
    report["quellen"]["newconnect"] = {"tage": len(days), "status": dict(nc_status), "aktien_in_dateien": len(ncon)}
    for i in war:
        isin = str(instruments["isin"][i])
        source, bars = ("gpw", gpw[isin]) if isin in gpw else (("newconnect", ncon[isin]) if isin in ncon else (None, {}))
        if source is None:
            results[i] = ka.ListingResult(source="gpw", status="ohne_kurse", reason="ISIN in keiner Datei der Börse")
            continue
        unit = units[i] or "PLN"
        # GPW: Währung der Spalte „Waluta“ (meist PLN, einzelne Aktien in EUR); NewConnect notiert nur in PLN (Datei ohne Spalte)
        stated = {c for c in file_currency.get(isin, Counter()) if c} if source == "gpw" else {"PLN"}
        res = ka.reconcile(source, inputs[i], bars, first_day=int(inputs[i].days.min()), last_day=cutoff,
                           identity_ok=True, currency_ok=(stated == {unit}) or (not stated and unit == "PLN"), basis="unbereinigt")
        res.counts["waehrung_boerse"] = "/".join(sorted(stated)) or "–"
        results[i] = res
        official_of[i] = bars

    # ---- CSE: alle Aktien, „Daily Market Summary“ je Sitzung (Kürzel; Identität über den Namen)
    cse_all = [i for i in range(n) if keys[i] == "XCNQ" and series_of(i) is not None and len(inputs[i].days)]
    if cse_all:
        cdays = sorted({int(d) for i in cse_all for d in inputs[i].days.tolist()})
        cse_status: Counter = Counter()
        cse_bars: dict[str, dict] = defaultdict(dict)
        cse_info: dict[str, dict] = {}
        no_trade: Counter = Counter()
        no_trade_days: dict[str, list[int]] = defaultdict(list)
        for day in cdays:
            if over_budget(0.6):
                cse_status["zeitbudget"] += 1
                continue
            f = boersen.fetch_cse_day(http, day)
            cse_status[f.status] += 1
            for sym, bar in f.bars.items():
                cse_bars[sym][day] = bar
            for sym, meta in f.info.items():
                cse_info.setdefault(sym, meta)
                if meta.get("ohne_abschluss"):
                    no_trade[sym] += 1
                    no_trade_days[sym].append(day)
        progress(f"CSE fertig: {dict(cse_status)}")
        report["quellen"]["cse"] = {"tage": len(cdays), "status": dict(cse_status), "kuerzel_mit_abschluss": len(cse_bars), "aktien": len(cse_all)}
        for i in cse_all:
            sym = boersen.cse_symbol(symbols[i])
            bars = boersen.fill_no_trade_days(dict(cse_bars.get(sym, {})), no_trade_days.get(sym, []))
            if not bars:
                results[i] = ka.ListingResult(source="cse", status="ohne_kurse", reason="Kürzel in keiner Datei mit Abschluss")
                continue
            name_ok = (absicherung.name_score((cse_info.get(sym) or {}).get("name"), [str(names[i] or "")]) or 0.0) >= absicherung.NAME_CONFIRMED
            unit = units[i] or "CAD"
            res = ka.reconcile("cse", inputs[i], bars, first_day=int(inputs[i].days.min()), last_day=cutoff, identity_ok=name_ok,
                               currency_ok=((cse_info.get(sym) or {}).get("currency") or "CAD") == unit, basis="unbereinigt")
            res.counts["name_bestaetigt"] = name_ok
            res.counts["tage_ohne_abschluss_bei_der_cse"] = int(no_trade.get(sym, 0))
            results[i] = res
            official_of[i] = bars

    # ---- Toronto / TSX Venture: Aktien unter den ersten 20
    tmx_targets = sorted((i for i in top20 if keys[i] in ("XTSE", "XTSX")), key=lambda i: (-first[i], -top10[i], i))[:TMX_BUDGET // 2]
    tmx_status = Counter()
    for i in tmx_targets:
        if over_budget(0.72):
            tmx_status["zeitbudget"] += 1
            continue
        s = series_of(i)
        if s is None or not len(s.days):
            tmx_status["stand_ohne_kurse"] += 1
            continue
        series = boersen.fetch_tmx(http, symbols[i], int(s.days.min()), cutoff)
        tmx_status[series.status] += 1
        if series.status != "ok":
            results[i] = ka.ListingResult(source="tmx", status="ohne_kurse", reason=series.status)
            continue
        name_ok = (absicherung.name_score(series.name, [str(names[i] or "")]) or 0.0) >= absicherung.NAME_CONFIRMED
        exch_ok = boersen.tmx_exchange_matches(keys[i], series.exchange)
        unit = units[i] or "CAD"
        res = ka.reconcile("tmx", s, series.bars, first_day=int(s.days.min()), last_day=cutoff,
                           identity_ok=name_ok and exch_ok, currency_ok=(series.currency == unit), basis="unbekannt")
        res.counts["name_bestaetigt"] = name_ok
        res.counts["boerse_bestaetigt"] = exch_ok
        res.counts["abruf"] = series.detail
        results[i] = res
        official_of[i] = series.bars
    progress(f"TMX fertig: {dict(tmx_status)}")
    report["quellen"]["tmx"] = {"aktien": len(tmx_targets), "status": dict(tmx_status)}

    # ---- Nasdaq: offizieller Schlusskurs (NOCP), Aktien unter den ersten 20
    nocp_status = Counter()
    for i in nas[:NOCP_BUDGET]:
        if over_budget(0.82):
            nocp_status["zeitbudget"] += 1
            continue
        s = series_of(i)
        if s is None or not len(s.days):
            nocp_status["stand_ohne_kurse"] += 1
            continue
        series = boersen.fetch_nocp(http, symbols[i])
        nocp_status[series.status] += 1
        if series.status != "ok":
            results[i] = ka.ListingResult(source="nasdaq_nocp", status="ohne_kurse", reason=series.status)
            continue
        res = ka.reconcile("nasdaq_nocp", s, series.bars, first_day=int(s.days.min()), last_day=cutoff,
                           identity_ok=True, currency_ok=(units[i] in (None, "USD")), basis="unbereinigt")
        results[i] = res
        official_of[i] = series.bars
    progress(f"NOCP fertig: {dict(nocp_status)}")
    report["quellen"]["nasdaq_nocp"] = {"aktien": min(len(nas), NOCP_BUDGET), "von": len(nas), "status": dict(nocp_status)}

    # ---- Zusammenfassung je Quelle
    summary: dict[str, dict] = {}
    for i, res in results.items():
        src = "warschau" if res.source in ("gpw", "newconnect") else res.source
        entry = summary.setdefault(src, {"notierungen": 0, "status": Counter(), "gruende": Counter(), "tage": Counter(), "korrekturen": Counter(),
                                         "aktien_mit_korrektur": 0, "rundung_tage": 0})
        entry["notierungen"] += 1
        entry["status"][res.status] += 1
        if res.reason and res.status != "uebernommen":
            entry["gruende"][res.reason.split(" ")[0]] += 1
        for code, count in res.counts.items():
            if code in ka.DAY_CODES:
                entry["tage"][code] += int(count)
        for c in res.corrections:
            entry["korrekturen"][c.reason] += 1
        entry["aktien_mit_korrektur"] += bool([c for c in res.corrections if c.reason != "umsatz_laut_boerse"])
        entry["rundung_tage"] += res.rounding
    report["zusammenfassung"] = {k: {kk: (dict(vv) if isinstance(vv, Counter) else vv) for kk, vv in v.items()} for k, v in summary.items()}

    # ---- Tage ohne Umsatz (Warschau, TMX): Wert der Börse gegen den letzten Schlusskurs mit Umsatz
    zero = Counter()
    zero_examples: list[dict] = []
    yahoo_zero = Counter()
    for i, res in results.items():
        bars = official_of.get(i) or {}
        if not bars:
            continue
        ordered = sorted(bars)
        prev_traded: dict[int, float] = {}
        last = None
        for d in ordered:
            prev_traded[d] = last
            b = bars[d]
            if b.volume is None or b.volume > 0:
                last = b.close
        for r in res.days:
            b = bars.get(r.day)
            if b is None:
                continue
            if r.main_volume is not None and r.main_volume == 0 and b.volume is not None:
                yahoo_zero["hauptquelle_umsatz_0__boerse_umsatz_0" if b.volume == 0 else "hauptquelle_umsatz_0__boerse_mit_umsatz"] += 1
            if b.volume is not None and b.volume == 0:
                p = prev_traded.get(r.day)
                same_prev = p is not None and abs(b.close / p - 1.0) < 1e-9
                zero["boerse_ohne_umsatz"] += 1
                zero["boerse_wert_gleich_letztem_schluss" if same_prev else ("boerse_wert_anders_als_letzter_schluss" if p is not None else "ohne_frueheren_schluss")] += 1
                if b.open is None and b.high is None and b.low is None:
                    zero["boerse_ohne_eroeffnung_hoch_tief"] += 1
                if r.code == "nur_boerse_ohne_umsatz":
                    zero["hauptquelle_ohne_kurstag"] += 1
                    continue
                zero["hauptquelle_mit_kurstag"] += 1
                zero["hauptquelle_umsatz_0" if (r.main_volume == 0) else ("hauptquelle_umsatz_positiv" if r.main_volume else "hauptquelle_umsatz_unbekannt")] += 1
                if r.code == "ohne_umsatz":
                    zero["hauptquelle_anderer_wert"] += 1
                    main_cmp = r.main
                    if len(zero_examples) < MAX_ROWS and (top10.get(i) or i in letters):
                        zero_examples.append({
                            "aktie": label(i), "boerse": keys[i], "quelle": res.source, "tag": iso(r.day),
                            "hauptquelle_zu_boerse": round(main_cmp / r.official, 5) if r.official else None,
                            "boerse_zu_letztem_schluss": round(b.close / p, 5) if p else None,
                            "hauptquelle_zu_letztem_schluss": round(main_cmp / (p / ka.split_factor(inputs[i].splits, r.day)), 5) if p else None,
                            "hauptquelle_umsatz": "0" if r.main_volume == 0 else ("positiv" if r.main_volume else "unbekannt"),
                            "abschluesse_boerse": b.trades,
                        })
                else:
                    zero["hauptquelle_gleicher_wert"] += 1
    report["ohne_umsatz"] = {"zaehler": dict(zero), "beispiele": zero_examples, "hauptquelle_umsatz_0": dict(yahoo_zero)}

    # ---- Fälle: Aktien mit Korrektur und Platz unter den ersten 20 (oder Buchstabe aus „spitzenreiter“)
    cases = []
    for i, res in sorted(results.items(), key=lambda kv: (-first[kv[0]], -top10[kv[0]], kv[0])):
        relevant = (i in top20) or (i in old_targets)
        if not relevant:
            continue
        devs = [abs(r.main / r.official - 1.0) for r in res.days if r.code in ("abweichend", "ohne_umsatz") and r.main and r.official]
        cases.append({
            "aktie": label(i), "boerse": keys[i], "quelle": res.source, "status": res.status, "grund": res.reason, "basis": res.basis,
            "platz1": int(first[i]), "top10": int(top10[i]),
            "tage": {k: v for k, v in res.counts.items() if k in ka.DAY_CODES and v},
            "gleich_anteil": None if res.equal_share is None else round(res.equal_share, 3),
            "abdeckung": None if res.coverage is None else round(res.coverage, 3),
            "faktor": None if res.factor is None else round(res.factor, 4),
            "korrekturen": dict(Counter(c.reason for c in res.corrections)),
            "groesste_abweichung": round(max(devs), 5) if devs else 0.0,
            "abweichende_tage": [iso(r.day) for r in res.days if r.code in ("abweichend", "ohne_umsatz")][:12],
            "name_bestaetigt": res.counts.get("name_bestaetigt"), "boerse_bestaetigt": res.counts.get("boerse_bestaetigt"), "abruf": res.counts.get("abruf"),
        })
    report["faelle"] = cases

    # ---- Wirkung: Ranglisten unabhängig neu gerechnet
    def variant(filter_fn) -> dict:
        out = {}
        for i, res in results.items():
            if not res.adopted or not filter_fn(res):
                continue
            s = inputs[i]
            own = {int(d): float(c) for d, c in zip(s.days.tolist(), s.close.tolist()) if np.isfinite(c) and c > 0}
            replaced = {c.day: c.new for c in res.corrections if c.reason in ("amtlicher_schlusskurs", "tag_ohne_umsatz", "fehlender_kurstag")}
            replaced.update({r.day: float(r.official) for r in res.days if r.code == "rundung" and r.official})
            if replaced:
                out[i] = ursachen.substitution(own, replaced)
        return out

    variants = {
        "alle": variant(lambda r: True),
        "warschau": variant(lambda r: r.source in ("gpw", "newconnect")),
        "warschau_ohne_umsatz": variant(lambda r: r.source in ("gpw", "newconnect") and any(c.reason == "tag_ohne_umsatz" for c in r.corrections)),
        "tmx": variant(lambda r: r.source == "tmx"),
        "cse": variant(lambda r: r.source == "cse"),
        "nocp": variant(lambda r: r.source == "nasdaq_nocp"),
    }
    variants = {k: v for k, v in variants.items() if v}
    progress(f"Wirkung: {', '.join(f'{k} {len(v)}' for k, v in variants.items())} Aktien neu zu rechnen")
    effects = ursachen.ranking_effects(stand, variants, liquid, min_trend, set(results), attribute={"alle"},
                                       attribution_budget_s=max(60.0, min(8 * 60.0, BUDGET_S + 9 * 60 - (time.monotonic() - STARTED) - 120))) if variants else {}
    progress("Wirkung fertig")
    report["wirkung"] = {}
    for name, (totals, moves, changes) in effects.items():
        rows = []
        for c in changes:
            if not c.get("platz1"):
                continue
            old, new = c["platz1"]
            rows.append({"rangliste": f"{c['h']}/{c['gruppe']}/{c['w']}", "vorher": label(old), "nachher": label(new),
                         "ausloeser": None if c.get("ausloeser") is None else [label(j) for j in c["ausloeser"]]})
        report["wirkung"][name] = {"aktien_neu_gerechnet": len(variants[name]), "zaehler": dict(totals), "platz1_geaendert": rows}

    # ---- Plätze 1 nach Börse: amtlich abgeglichen oder nicht
    secured = Counter()
    for order in lists.values():
        if not order:
            continue
        i = order[0]
        res = results.get(i)
        state = "kein_amtliches_archiv" if res is None and not boersen.sources_for(keys[i]) else ("nicht_abgefragt" if res is None else res.status)
        secured[f"{keys[i] or '?'}:{state}"] += 1
    report["platz1_abgleich"] = dict(secured.most_common())

    # ---- US-Börsenzuordnung gegen die Wertpapierliste von Nasdaq Trader
    us_keys = {"XNYS": "nyse", "XNAS": "nasdaq", "XASE": "nyse_american", "ARCX": "nyse_arca", "BATS": "cboe_bzx"}
    status, listing = directory_status, directory
    us = Counter()
    rows = []
    if listing:
        for i in range(n):
            key = keys[i]
            if key not in us_keys and key not in ("OTC", "US"):
                continue
            entry = listing.get(absicherung.normalize(symbols[i]))
            if key in ("OTC", "US"):
                found = entry["boerse"] if entry else "nicht_in_liste"
                us[f"{key}:{found}"] += 1
                if (i in top20) and ((key == "OTC" and entry) or (key == "US" and not entry)):
                    rows.append({"aktie": label(i), "app": key, "liste": found, "platz1": int(first[i]), "top10": int(top10[i])})
                continue
            if entry is None:
                us[f"{key}:nicht_in_liste"] += 1
                if i in top20:
                    rows.append({"aktie": label(i), "app": key, "liste": "fehlt (OTC oder nicht mehr notiert)", "platz1": int(first[i]), "top10": int(top10[i])})
            elif entry["boerse"] != us_keys[key]:
                us[f"{key}:andere_boerse_{entry['boerse']}"] += 1
                if i in top20:
                    rows.append({"aktie": label(i), "app": key, "liste": entry["boerse"], "platz1": int(first[i]), "top10": int(top10[i])})
            else:
                us[f"{key}:gleich"] += 1
    report["us_zuordnung"] = {"liste": status, "zaehler": dict(sorted(us.items())), "auffaellig_unter_ersten_20": rows[:MAX_ROWS]}
    return report


def lines(report: dict) -> list[str]:
    out = [f"Stand {report['stand']} (Stichtag {report['stichtag']}), Regel {report['regel']}, {report['ranglisten']} Ranglisten"]
    out.append("Aktien unter den ersten 20 je Börse: " + ", ".join(f"{k} {v}" for k, v in report["boersen_top"]["erste_20"].items()))
    out.append("Plätze 1 je Börse: " + ", ".join(f"{k} {v}" for k, v in report["boersen_top"]["platz1"].items()))
    out.append("Quellen: " + json.dumps(report["quellen"], ensure_ascii=False))
    for src, s in report["zusammenfassung"].items():
        out.append(f"[{src}] Notierungen {s['notierungen']}; Status {s['status']}; Gründe {s['gruende']}; Tage {s['tage']}; Korrekturen {s['korrekturen']}; "
                   f"Aktien mit Kurskorrektur {s['aktien_mit_korrektur']}; Tage nur Rundung {s['rundung_tage']}")
    z = report["ohne_umsatz"]
    out.append("Tage ohne Umsatz an der Börse: " + json.dumps(z["zaehler"], ensure_ascii=False))
    out.append("Hauptquelle mit Umsatz 0: " + json.dumps(z["hauptquelle_umsatz_0"], ensure_ascii=False))
    for e in z["beispiele"]:
        out.append("  ohne Umsatz: " + json.dumps(e, ensure_ascii=False))
    out.append("Fälle (Aktien unter den ersten 20 bzw. Spitzenreiter):")
    for c in report["faelle"]:
        if c["status"] == "bestaetigt" and not c["korrekturen"]:
            continue
        out.append("  " + json.dumps(c, ensure_ascii=False))
    bestaetigt = sum(1 for c in report["faelle"] if c["status"] == "bestaetigt")
    out.append(f"  (dazu {bestaetigt} Aktien unter den ersten 20 ohne Abweichung bestätigt)")
    for name, w in report["wirkung"].items():
        out.append(f"Wirkung [{name}]: {w['aktien_neu_gerechnet']} Aktien neu gerechnet; Zähler {w['zaehler']}; Platz 1 anders: {len(w['platz1_geaendert'])}")
        for row in w["platz1_geaendert"][:MAX_ROWS]:
            out.append("  " + json.dumps(row, ensure_ascii=False))
    out.append("Plätze 1 nach Börse und Abgleich: " + json.dumps(report["platz1_abgleich"], ensure_ascii=False))
    out.append("US-Zuordnung: " + json.dumps(report["us_zuordnung"], ensure_ascii=False))
    return out


def ledger_report(stand, sid: str) -> list[str]:
    """Nachweis eines Stands ab 1.20.0 (``kursabgleich.bin``), ohne Namen, Kürzel, ISINs und Kurse: Zählwerte, je korrigierter
    Aktie Buchstabe, Börse, Quelle, Tage und Verhältnis bisheriger Kurs/Kurs der Börse, geänderte Plätze 1 mit Buchstaben,
    Lücken je Börse und Grund; dazu die Gegenprobe, dass jede Kursreihe des Stands an jedem korrigierten Tag den Kurs der
    Börse trägt."""
    manifest = stand.get("manifest.bin")
    summary = manifest.get("kursabgleich")
    if not summary:
        return [f"Stand {sid}: kein Kursabgleich (vor 1.20.0 gerechnet)"]
    data = stand.get("kursabgleich.bin")
    instruments = stand.get("instruments.bin")
    keys = instruments.get("exchange_key") or []
    out = [f"Stand {sid} (Stichtag {data['stichtag']}), Regel {data['regel']}, Software {manifest['versions'].get('software')}",
           "Zusammenfassung: " + json.dumps({k: summary[k] for k in ("aktien_mit_kurskorrektur", "ranglisten", "durchgaenge", "platz1_ohne_abgleich", "us_zuordnung")}, ensure_ascii=False),
           "Quellen: " + json.dumps(summary["quellen"], ensure_ascii=False),
           "Tage: " + json.dumps(summary["tage"], ensure_ascii=False),
           "Abrufe: " + json.dumps(summary["abrufe"], ensure_ascii=False)]
    lists_before_after = data["ranglisten"]
    involved = Counter()
    for r in lists_before_after:
        for i in (r["vorher"][:1] + r["nachher"][:1]):
            involved[i] += 1
    cases = sorted(data["faelle"], key=lambda c: (-involved.get(c["idx"], 0), c["boerse"] or "", c["isin"]))
    letters: dict[int, str] = {}

    def label(i):
        if i is None:
            return "–"
        if i not in letters:
            letters[i] = f"K{len(letters) + 1}"
        return letters[i]

    for c in cases:  # Buchstaben in der Reihenfolge der Fälle vergeben, bevor andere Zeilen sie verwenden
        label(c["idx"])
    checked = Counter()
    jump_counts = Counter()
    case_lines: list[str] = []
    notable: list[str] = []
    for c in cases:
        reasons = Counter(k["grund"] for k in c["korrekturen"])
        price = [k for k in c["korrekturen"] if k["grund"] in PRICE_REASONS]
        devs = [abs(k["alt"] / k["neu"] - 1.0) for k in price if k.get("alt") and k.get("neu")]
        days = sorted({int(k["d"]) for k in price})
        series_name = f"series/{c['isin']}.bin"
        new_jumps: list[tuple[int, float]] = []
        removed_jumps: list[tuple[int, float]] = []
        splits: list[str] = []
        series_detail = None
        if c["status"] == "uebernommen" and stand.exists(series_name):
            series = stand.get(series_name)
            stand.drop(series_name)
            series_detail = series
            pos = {int(d): k for k, d in enumerate(series.get("d") or [])}
            for k in c["korrekturen"]:
                if k["grund"] == "umsatz_laut_boerse" or int(k["d"]) not in pos:
                    checked["vor_beginn_der_kursreihe"] += k["grund"] != "umsatz_laut_boerse"
                    continue
                value = series["c"][pos[int(k["d"])]]
                checked["kursreihe_gleich_boerse" if value is not None and abs(value / k["neu"] - 1.0) < 1e-9 else "kursreihe_anders"] += 1
            if price:
                new_jumps, removed_jumps = jump_check(series, price)
                jump_counts["aktien_geprueft"] += 1
                jump_counts["neue_spruenge"] += len(new_jumps)
                jump_counts["entfernte_spruenge"] += len(removed_jumps)
                jump_counts["aktien_mit_neuem_sprung"] += bool(new_jumps)
            splits = [f"{iso(e['day'])} Faktor {float(e['factor']):.6g}" for e in (series.get("events") or []) if e.get("type") == "split"]
        status = STATUS_SHORT.get(c["status"], c["status"])
        k_text = ",".join(f"{REASON_SHORT.get(g, g)}{n}" for g, n in sorted(reasons.items()))
        span = f"{iso(days[0])[5:]}..{iso(days[-1])[5:]}" if days else "–"
        case_lines.append(f"  {label(c['idx'])} {c['boerse']} {SOURCE_SHORT.get(c['quelle'], c['quelle'])} {status}{'(' + c['grund'] + ')' if c['grund'] else ''}"
                          f" {k_text or '–'} {span} max {100 * max(devs) if devs else 0:.3g}% gl {c.get('gleich_anteil') or 0:.3f}"
                          f" ab {c.get('abdeckung') or 0:.3f} p1 {involved.get(c['idx'], 0)}")
        if len(days) >= NOTABLE_DAYS or (devs and max(devs) >= NOTABLE_DEV) or new_jumps:
            notable.append(f"  {label(c['idx'])} {c['boerse']} {c['quelle']}: {len(days)} Tage, Verhältnis bisher/Börse je Abschnitt: "
                           + "; ".join(ratio_profile(price)[:8])
                           + (f"; Splits in der Kursreihe: {', '.join(splits)}" if splits else "; keine Splits in der Kursreihe")
                           + (f"; neue Tagesänderungen > Faktor {JUMP_FACTOR}: " + ", ".join(f"{iso(d)} {np.exp(r):.4g}" for d, r in new_jumps[:6]) if new_jumps else "")
                           + (f"; entfernte: {len(removed_jumps)}" if removed_jumps else ""))
            if series_detail is not None and (new_jumps or splits or any(abs(np.log(k['alt'] / k['neu'])) >= np.log(1.2) for k in price if k.get('alt') and k.get('neu'))):
                notable.append(f"    {label(c['idx'])} Tage: " + day_detail(series_detail, price))
    out.append("Gegenprobe Kursreihen: " + json.dumps(dict(checked), ensure_ascii=False))
    out.append(f"Sprungprüfung (Tagesänderung um mehr als Faktor {JUMP_FACTOR} in der Kursreihe nach, aber nicht vor der Übernahme): "
               + json.dumps(dict(jump_counts), ensure_ascii=False))
    out.append(f"Auffällige Fälle (mindestens {NOTABLE_DAYS} korrigierte Tage, Abweichung ab {NOTABLE_DEV:.0%} oder neuer Sprung): {len(notable)}")
    out.extend(notable)
    changes = [r for r in lists_before_after if r["platz1_anders"]]
    out.append(f"Ranglisten mit anderem Platz 1: {len(changes)}; mit anderen ersten 10: {sum(1 for r in lists_before_after if set(r['vorher']) != set(r['nachher']))}")
    for r in changes:
        out.append(f"  {r['h']}/{r['gruppe']}/{r['w']}: vorher {label(r['vorher'][0])} ({keys[r['vorher'][0]]}), nachher {label(r['nachher'][0])} ({keys[r['nachher'][0]]}); Auslöser {[label(i) for i in r['ausloeser']] or 'über die Plätze anderer Aktien'}")
    gaps = Counter()
    first = Counter()
    for g in data["luecken"]:
        gaps[f"{g['boerse']}:{g['grund'].split(':')[0]}"] += 1
        first[f"{g['boerse']}:{g['grund'].split(':')[0]}"] += g["platz1"]
    out.append(f"Aktien unter den ersten 10 ohne Abgleich: {data['luecken_gesamt']} – je Börse und Grund (Aktien): " + json.dumps(dict(gaps.most_common()), ensure_ascii=False))
    out.append("Plätze 1 dieser Aktien je Börse und Grund: " + json.dumps(dict(first.most_common()), ensure_ascii=False))
    out.append(f"US-Zuordnung, Abweichungen: {len(data['us_zuordnung'])} – " + json.dumps(dict(Counter(u['ergebnis'] for u in data['us_zuordnung']).most_common()), ensure_ascii=False))
    out.append("Fälle (Buchstabe Börse Quelle Status Korrekturen Zeitraum größte Abweichung Anteil gleicher Tage Abdeckung Plätze 1) – "
               + ", ".join(f"{v}={k}" for k, v in {**STATUS_SHORT, **REASON_SHORT}.items()) + f": {len(case_lines)}")
    out.extend(case_lines)
    return out


PRICE_REASONS = ("amtlicher_schlusskurs", "tag_ohne_umsatz", "fehlender_kurstag", "nachkommastellen")
STATUS_SHORT = {"uebernommen": "ü", "bestaetigt": "b", "abdeckung_unvollstaendig": "a", "nicht_vergleichbar": "n", "ohne_kurse": "o"}
REASON_SHORT = {"amtlicher_schlusskurs": "K", "tag_ohne_umsatz": "O", "fehlender_kurstag": "F", "umsatz_laut_boerse": "U", "nachkommastellen": "N"}
SOURCE_SHORT = {"nasdaq_nocp": "nocp"}
NOTABLE_DAYS = 10
NOTABLE_DEV = 0.2
JUMP_FACTOR = 1.5
JUMP = float(np.log(JUMP_FACTOR))


def ratio_profile(corrections: list[dict]) -> list[str]:
    """Abschnitte aufeinanderfolgender korrigierter Tage mit (bis auf 2 %) gleichem Verhältnis bisheriger Kurs/Kurs der Börse –
    ein gleichbleibendes Verhältnis über einen ganzen Abschnitt deutet auf eine andere Bereinigungsbasis (Split), wechselnde
    Verhältnisse auf einzelne falsche Kurse."""
    points = sorted((int(k["d"]), k["alt"] / k["neu"]) for k in corrections if k.get("alt") and k.get("neu"))
    segments: list[dict] = []
    for d, r in points:
        if segments and abs(r / segments[-1]["ref"] - 1.0) <= 0.02:
            segments[-1]["last"] = d
            segments[-1]["ratios"].append(r)
        else:
            segments.append({"first": d, "last": d, "ref": r, "ratios": [r]})
    out = [f"{iso(s['first'])[5:]}..{iso(s['last'])[5:]} {len(s['ratios'])}× {float(np.median(s['ratios'])):.4g}" for s in segments]
    if len(out) > 8:
        out = out[:7] + [f"… {len(out) - 7} weitere Abschnitte"]
    return out


def day_detail(series: dict, corrections: list[dict], limit: int = 40) -> str:
    """Tagesweise ohne Kurse: Beginn der Kursreihe, je korrigiertem Tag und den Tagen um jede Grenze zwischen korrigierten und
    unkorrigierten Tagen „MM-TT Grund Verhältnis bisher/Börse Δnach Δvor F“ (Δ: Kurs/Vortag nach bzw. vor der Übernahme, F:
    Splitfaktor des Tages laut c_raw/c, U0: Umsatz 0 laut Börse)."""
    by_day = {int(k["d"]): k for k in corrections}
    d_list = [int(d) for d in series.get("d") or []]
    c = series.get("c") or []
    raw = series.get("c_raw") or [None] * len(d_list)
    before_vals = {}
    for k, d in enumerate(d_list):
        corr = by_day.get(d)
        if corr is None:
            before_vals[d] = c[k]
        elif corr["grund"] != "fehlender_kurstag" and corr.get("alt"):
            before_vals[d] = corr["alt"]
    marks = set()
    flags = [d in by_day for d in d_list]
    for k in range(len(d_list)):
        if flags[k] or (k > 0 and flags[k] != flags[k - 1]) or (k + 1 < len(d_list) and flags[k] != flags[k + 1]):
            marks.update(range(max(0, k - 1), min(len(d_list), k + 2)))
    out = [f"Reihe ab {iso(d_list[0])[5:]}" if d_list else "Reihe leer", f"{len([d for d in by_day if d < (d_list[0] if d_list else 0)])} Korrekturen davor"]
    prev_after = prev_before = None
    for k, d in enumerate(d_list):
        after = c[k]
        before = before_vals.get(d)
        if k in marks:
            corr = by_day.get(d)
            tag = REASON_SHORT.get(corr["grund"], "?") if corr else "-"
            ratio = f"{corr['alt'] / corr['neu']:.4g}" if corr and corr.get("alt") and corr.get("neu") else "-"
            da = f"{after / prev_after:.3g}" if after and prev_after else "-"
            db = f"{before / prev_before:.3g}" if before and prev_before else "-"
            f = f"{raw[k] / after:.4g}" if raw[k] and after else "-"
            u0 = " U0" if corr and corr.get("umsatz_neu") == 0 else ""
            out.append(f"{iso(d)[5:]} {tag} {ratio} {da} {db} {f}{u0}")
        if after:
            prev_after = after
        if before:
            prev_before = before
    if len(out) > limit:
        out = out[:limit] + [f"… {len(out) - limit} weitere"]
    return " | ".join(out)


def jump_check(series: dict, corrections: list[dict]) -> tuple[list[tuple[int, float]], list[tuple[int, float]]]:
    """Tagesänderungen der veröffentlichten Kursreihe (nach der Übernahme) gegen die Reihe der Hauptquelle (bisherige Kurse an den
    korrigierten Tagen, ergänzte Tage entfernt): neue Sprünge über Faktor ``JUMP_FACTOR`` und entfernte Sprünge."""
    by_day = {int(k["d"]): k for k in corrections}
    after = [(int(d), float(v)) for d, v in zip(series.get("d") or [], series.get("c") or []) if v is not None and v > 0]
    before = []
    for d, v in after:
        k = by_day.get(d)
        if k is None:
            before.append((d, v))
        elif k["grund"] != "fehlender_kurstag" and k.get("alt"):
            before.append((d, float(k["alt"])))

    def changes(points):
        return {points[j][0]: float(np.log(points[j][1] / points[j - 1][1])) for j in range(1, len(points))}

    ca, cb = changes(after), changes(before)
    new = [(d, r) for d, r in ca.items() if abs(r) > JUMP and abs(cb.get(d, 0.0)) <= JUMP]
    removed = [(d, r) for d, r in cb.items() if abs(r) > JUMP and abs(ca.get(d, 0.0)) <= JUMP]
    return new, removed


REACH_URLS = {
    "gpw": "https://www.gpw.pl/archiwum-notowan-full?type=10&instrument=&date=23-10-2026",
    "gpw_start": "https://www.gpw.pl/",
    "newconnect": "https://newconnect.pl/pub/NEWCONNECT/statystyki/statystyki_dzienne/NC_20261023.xlsx",
    "cse": "https://market-reports-primary.thecse.com/CSEListed/Daily/Summary/CSEListed.Daily.Market.Summary.2026-10-23.txt",
    "nasdaqtrader": "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqtraded.txt",
}


def reachability() -> list[str]:
    """Erreichbarkeit der Quellen vom Prüfrechner aus – mit verschiedenen Abrufwegen (Browser-Kennung über curl_cffi,
    requests, curl), nur Status und Fehlerart, keine Inhalte."""
    import socket
    import subprocess

    import requests

    out = []
    for name, url in REACH_URLS.items():
        host = url.split("/")[2]
        try:
            addrs = sorted({a[4][0] for a in socket.getaddrinfo(host, 443)})
            dns = f"{len(addrs)} Adressen ({', '.join('IPv6' if ':' in a else 'IPv4' for a in addrs[:4])})"
        except OSError as exc:
            dns = f"DNS-Fehler {type(exc).__name__}"
        results = []
        for label, client in (("curl_cffi_chrome", HttpClient(impersonate="chrome", max_retries=0, timeout=20)),
                              ("http_client", HttpClient(max_retries=0, timeout=20))):
            try:
                r = client.get(url, headers={"Accept": "*/*"})
                results.append(f"{label} HTTP {r.status_code}, {len(r.content or b'')} Byte")
            except Exception as exc:  # noqa: BLE001 - nur die Fehlerart
                results.append(f"{label} {type(exc).__name__}: {str(exc).rsplit(': ', 1)[-1][:80]}")
        try:
            r = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)", "Accept": "*/*"})
            results.append(f"requests HTTP {r.status_code}, {len(r.content)} Byte")
        except Exception as exc:  # noqa: BLE001
            results.append(f"requests {type(exc).__name__}")
        try:
            done = subprocess.run(["curl", "-sS", "-o", "/dev/null", "-w", "%{http_code} %{size_download}", "--max-time", "20", url], capture_output=True, text=True, timeout=30)
            results.append(f"curl {done.stdout.strip() or done.stderr.strip()[:80]}")
        except Exception as exc:  # noqa: BLE001
            results.append(f"curl {type(exc).__name__}")
        out.append(f"Erreichbarkeit {name} ({host}; {dns}): " + " | ".join(results))
    return out


MAX_ANNOTATION_BYTES = 2900  # GitHub kürzt Hinweise bei rund 3 KB
PER_STEP = 9  # GitHub zeigt je Schritt höchstens 10 Hinweise je Art
STEPS = 5  # Prüfschritt und vier Schritte „Einzelheiten“ im Workflow


def annotation_bodies(title: str, lines: list[str]) -> list[str]:
    """Zeilen auf Hinweise unter ``MAX_ANNOTATION_BYTES`` verteilen (jede Zeile bleibt ganz, zu lange werden gekürzt)."""
    bodies: list[list[str]] = []
    current: list[str] = []
    size = 0
    for line in lines:
        line = line if len(line.encode("utf-8")) < MAX_ANNOTATION_BYTES - 200 else line[: (MAX_ANNOTATION_BYTES - 300) // 2] + " …"
        cost = len(line.encode("utf-8")) + 3
        if current and size + cost > MAX_ANNOTATION_BYTES:
            bodies.append(current)
            current, size = [], 0
        current.append(line)
        size += cost
    if current:
        bodies.append(current)
    total = len(bodies)
    out = []
    for k, part in enumerate(bodies, start=1):
        body = "%0A".join(x.replace("%", "%25").replace("\r", " ").replace("\n", " ") for x in part)
        out.append(f"::notice title={title} ({k}/{total})::{body}")
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", "szymeklh87-commits/tr-aktienvergleich"))
    parser.add_argument("--stand", default=os.environ.get("STAND") or None)
    parser.add_argument("--bericht", type=Path)
    parser.add_argument("--hinweise", type=Path, help="alle Hinweise in diese Datei (JSON), im Prüfschritt die ersten ausgeben")
    parser.add_argument("--teil", type=int, help=f"nur die Hinweise dieses Schritts aus --hinweise ausgeben (2 bis {STEPS})")
    parser.add_argument("--nachweis", action="store_true", help="nur den Nachweis des Stands (kursabgleich.bin, ab 1.20.0) auswerten – ohne Abruf")
    parser.add_argument("--erreichbarkeit", action="store_true", help="vorab prüfen, ob die Quellen der Börsen vom Prüfrechner aus erreichbar sind")
    args = parser.parse_args(argv)
    if args.teil:
        notes = json.loads(args.hinweise.read_text(encoding="utf-8")) if args.hinweise and args.hinweise.exists() else []
        for line in notes[(args.teil - 1) * PER_STEP: args.teil * PER_STEP]:
            print(line)
        return 0
    http = HttpClient(impersonate="chrome", max_retries=1, timeout=20, min_interval={**boersen.MIN_INTERVAL, absicherung.LISTING_HOST: 0.5})
    with tempfile.TemporaryDirectory() as temp:
        sid, folder, key = ursachen.load_stand(args.repo, os.environ.get("GITHUB_TOKEN"), Path(temp), args.stand)
        stand = nachrechnen.Stand(folder, sid, key)
        progress(f"Stand {sid} geladen")
        if args.nachweis:
            out = ledger_report(stand, sid)
            report = {"stand": sid}
        else:
            report = run(stand, sid, http)
    if not args.nachweis:
        out = lines(report)
    if args.erreichbarkeit or args.nachweis:
        out = reachability() + out
    for line in out:
        print(line)
    if args.bericht:
        args.bericht.write_text(json.dumps(report, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    notes = annotation_bodies(f"Kursabgleich {report['stand']}", out)
    if len(notes) > PER_STEP * STEPS:
        notes = notes[: PER_STEP * STEPS - 1] + [f"::warning title=Kursabgleich {report['stand']}::{len(notes) - PER_STEP * STEPS + 1} weitere Hinweise nicht ausgegeben (Grenze von GitHub)"]
    if args.hinweise:
        args.hinweise.write_text(json.dumps(notes, ensure_ascii=False), encoding="utf-8")
    for line in notes[:PER_STEP]:
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
