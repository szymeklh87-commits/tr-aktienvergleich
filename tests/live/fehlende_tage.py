"""Einfluss fehlender Kurstage auf die Ranglisten – mit echten Daten (ab 1.17.1).

Simons Auftrag vom 24.10.2026: „Sichere die Behandlung fehlender Kurstage mit nachvollziehbaren Referenztests ab.
Dokumentiere ihren Einfluss auf Ranglisten.“ Die Regeln selbst prüfen die Referenzfälle
(``tests/unit/test_referenz_fehlende_kurstage.py``, docs/12_Fehlende_Kurstage.md). Dieses Skript misst, wie stark sie im
veröffentlichten Stand wirken:

1. **Bestand:** Wie viele Aktie-Zeitraum-Paare der Ranglisten (Menge V, Gruppe A, 90 Zeiträume) haben fehlende
   Börsensitzungen, wie viele Paare schließt die Regel aus (Starttag ohne Kurs, mehr als 20 % fehlen), wie viele Aktien
   zählen mit ihrem letzten Schlusskurs (eigener Endtag)?
2. **Art der Lücke:** Für die Aktien mit Lücken in Ranglisten-Zeiträumen wird beim Kursanbieter (Yahoo, nur lesend)
   nachgesehen, ob der Tag als **Leerzeile** geliefert wird (Zeile ohne Kurs) oder **ganz fehlt** – das Ausgangsmodell
   verwirft einen Zeitraum mit Leerzeile, die App zählt beides als fehlende Sitzung.
3. **Einfluss auf die Ranglisten:** alle 1.980 Ranglisten (Gruppe A und B × 90 Zeiträume × 11 Gewichtungen) nach der Regel
   der App und – mit derselben unabhängigen Ranglistenrechnung wie die Nachrechnung – nach drei anderen Regeln: (a) streng,
   jeder fehlende Kurstag schließt aus; (b) wie das Ausgangsmodell, nur Leerzeilen schließen aus; (c) ohne letzten
   Schlusskurs (Regel bis tr-methode-1.8.0). Gezählt: Ranglisten mit anderem Platz 1, anderen ersten 10 (Aktien), anderer
   Reihenfolge der ersten 10.
4. **Gleichstand:** Ranglisten mit gemischter Gewichtung, in denen rechnerisch gleiche Scores (exakt aus den ganzzahligen
   Rängen) unter den ersten 10 stehen, und wie oft die Reihenfolge dort nicht der Rendite folgt (Gleitkomma-Regel wie im
   Ausgangsmodell, siehe docs/12, „Gleichstand“).

Ausgegeben werden nur Zählwerte – keine Namen, Kürzel, ISINs, Kurse oder Renditen (das Protokoll ist öffentlich).
Aufruf im Workflow „Fehlende Kurstage auswerten“ (nur von Hand); braucht ``DATA_PASSPHRASE`` und ``GITHUB_TOKEN``.
"""

from __future__ import annotations

import argparse
import base64
import concurrent.futures
import json
import os
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))
sys.path.insert(0, str(REPO_ROOT))

from tests.live.nachrechnen import V_STATUS, WEIGHTS, Stand, key_for, load_release_stands, load_site_stands, rank_group  # noqa: E402
from traktien.util.timeutil import session_date_from_timestamp, date_to_day  # noqa: E402

STARTKURS_FEHLT, ABDECKUNG_ZU_GERING, KURS_AM_STICHTAG_FEHLT, MARKT_GESCHLOSSEN = 11, 12, 8, 7


def notice(title: str, lines: list[str], level: str = "notice") -> None:
    body = "%0A".join(line.replace("%", "%25").replace("\n", " ") for line in lines)
    print(f"::{level} title={title}::{body}")


def load(stand: Stand) -> dict:
    """Fensterdaten aller 90 Zeiträume (V-Mitglieder mit Start, Kursen, Sitzungen, Rendite, R²) und Status."""
    out = {}
    for h in range(1, 91):
        win = stand.get(f"windows/{h}.full.bin")
        status = np.frombuffer(base64.b64decode(win["status_b64"]), dtype=np.uint8)
        m = win["m"]
        rows = {int(i): k for k, i in enumerate(m["idx"])}
        out[h] = {"win": win, "status": status, "rows": rows, "m": m}
        stand.drop(f"windows/{h}.full.bin")
    return out


def classify_gaps(listings: dict[int, dict], wanted: dict[int, set[int]], budget_s: float) -> tuple[dict[int, dict[int, str]], Counter]:
    """Je Aktie und fehlendem Tag: „leerzeile“ (Zeile ohne gültigen Kurs), „keine_zeile“ oder „kurs_nachgeliefert“."""
    from traktien.providers.yahoo import CHART_HOSTS, YahooProvider

    provider = YahooProvider()
    stats: Counter = Counter()
    jobs = []
    for i, days in wanted.items():
        listing = listings.get(i) or {}
        if listing.get("symbol") and listing.get("tz") and days:
            jobs.append((i, listing["symbol"], listing["tz"], sorted(days)))
        else:
            stats["ohne_kuerzel_oder_tage"] += 1
    started = time.monotonic()
    result: dict[int, dict[int, str]] = {}

    def one(job, host):
        i, symbol, tz, days = job
        payload = provider.chart(symbol, min(days) - 3, max(days) + 1, host=host)
        res = ((payload or {}).get("chart") or {}).get("result") or [{}]
        timestamps = res[0].get("timestamp") or []
        closes = (((res[0].get("indicators") or {}).get("quote") or [{}])[0] or {}).get("close") or []
        rows: dict[int, bool] = {}
        for k, ts in enumerate(timestamps):
            if ts is None:
                continue
            day = date_to_day(session_date_from_timestamp(ts, tz))
            close = closes[k] if k < len(closes) else None
            valid = isinstance(close, (int, float)) and close > 0
            rows[day] = rows.get(day, False) or valid
        return i, {d: ("keine_zeile" if d not in rows else "kurs_nachgeliefert" if rows[d] else "leerzeile") for d in days}

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        pending = [pool.submit(one, job, CHART_HOSTS[k % len(CHART_HOSTS)]) for k, job in enumerate(jobs)]
        for future in concurrent.futures.as_completed(pending):
            try:
                i, kinds = future.result()
            except concurrent.futures.CancelledError:
                continue
            except Exception:  # noqa: BLE001 - Kursanbieter ohne Antwort: nur gezählt
                stats["abruf_fehlgeschlagen"] += 1
            else:
                result[i] = kinds
                stats["abgerufen"] += 1
            if time.monotonic() - started > budget_s:
                stats["zeitbudget_ueberschritten"] = sum(1 for f in pending if f.cancel())
                break
    stats["sekunden"] = int(time.monotonic() - started)
    return result, stats


def compare(base: dict, alt: dict, top: int = 10) -> Counter:
    out: Counter = Counter()
    for key, order in base.items():
        other = alt[key]
        if order == other:
            continue
        out["anders"] += 1
        if order[:1] != other[:1]:
            out["platz_1_anders"] += 1
        if set(order[:top]) != set(other[:top]):
            out["erste_10_andere_aktien"] += 1
        elif order[:top] != other[:top]:
            out["erste_10_andere_reihenfolge"] += 1
    return out


def rankings(data: dict, members_of, liquid: list[bool]) -> dict:
    """Alle 1.980 Ranglisten (Gruppe, Zeitraum, Gewichtung) mit der unabhängigen Rechnung aus der Nachrechnung."""
    out = {}
    for h, d in data.items():
        m = d["m"]
        idx = [int(i) for i in m["idx"]]
        r_of = {i: float(m["r"][k]) for k, i in enumerate(idx)}
        r2_of = {i: m["r2"][k] for k, i in enumerate(idx)}
        keep = members_of(h, idx)
        a = rank_group(np.array(keep, dtype=np.int64), d["status"], r_of, r2_of)
        b = rank_group(np.array([i for i in keep if liquid[i]], dtype=np.int64), d["status"], r_of, r2_of)
        for group, res in (("A", a), ("B", b)):
            for w in WEIGHTS:
                out[(group, h, w)] = (res["v0"] if w == 0 else res["u"][w]).tolist()
    return out


def exact_ties(data: dict, liquid: list[bool]) -> Counter:
    """Gemischte Gewichtungen: rechnerisch gleiche Scores unter den ersten 10 und Reihenfolge gegen die Rendite."""
    out: Counter = Counter()
    for h, d in data.items():
        m, orders = d["m"], d["win"]["orders"]
        pos = {int(i): k for k, i in enumerate(m["idx"])}
        for group, gkey, rkey, okey in (("A", "a_gu", "a_ru", "u"), ("B", "a_gul", "a_rul", "ul")):
            if not orders.get(okey):
                continue
            for w in range(10, 100, 10):
                order = orders[okey][str(w)][:11]  # Platz 11 mit: ein Gleichstand an der Grenze entscheidet über die ersten 10
                if len(order) < 2:
                    continue
                key = {}
                for i in order:
                    g, r = m[gkey][pos[i]], m[rkey][pos[i]]
                    key[i] = w * (g - 2) + (100 - w) * (r - 2)  # Score · 2 · (M − 1), exakt ganzzahlig
                tied_rankings = False
                against = False
                for a, b in zip(order, order[1:]):
                    if key[a] == key[b]:
                        tied_rankings = True
                        if float(m["r"][pos[a]]) < float(m["r"][pos[b]]):
                            against = True
                out["gemischte_ranglisten"] += 1
                if tied_rankings:
                    out["mit_gleichstand_in_ersten_10"] += 1
                if against:
                    out["davon_reihenfolge_gegen_rendite"] += 1
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", "szymeklh87-commits/tr-aktienvergleich"))
    parser.add_argument("--bericht", default="fehlende-tage.json")
    parser.add_argument("--abruf-budget", type=float, default=1200.0, help="Sekunden für die Abfrage beim Kursanbieter")
    parser.add_argument("--site", help="lokaler Website-Ordner statt des Release (Tests mit DEMO-Daten)")
    parser.add_argument("--ohne-abruf", action="store_true", help="Kursanbieter nicht abfragen (Art der Lücken bleibt offen)")
    args = parser.parse_args(argv)
    report: dict = {}
    with tempfile.TemporaryDirectory() as temp:
        if args.site:
            meta, stands = load_site_stands(Path(args.site))
        else:
            meta, stands = load_release_stands(args.repo, os.environ.get("GITHUB_TOKEN"), Path(temp), None)
        sid = meta["status"]["latest_official_snapshot_id"]
        folder = dict(stands)[sid]
        stand = Stand(folder, sid, key_for(meta["descriptor"]))
        manifest = stand.get("manifest.bin")
        instruments = stand.get("instruments.bin")
        isins = instruments["isin"]
        n = len(isins)
        cutoff = int(manifest["cutoff_day"])
        liquid = (instruments.get("turnover") or {}).get("liquid") or [False] * n
        last_day = instruments.get("last_close_day") or [None] * n
        data = load(stand)
        report["stand"] = {"kursstand": manifest.get("cutoff_session_date"), "software": (manifest.get("versions") or {}).get("software"), "methode": (manifest.get("versions") or {}).get("method"), "aktien": n}

        # 1. Bestand
        pairs = Counter()
        gap_pairs: dict[int, set[int]] = {}  # Aktie → Zeiträume (h) in V mit fehlenden Sitzungen
        stocks_with_gaps = set()
        own_end = {i for i in range(n) if last_day[i] is not None and int(last_day[i]) < cutoff}
        own_end_in_v = set()
        for h, d in data.items():
            m, rows, status = d["m"], d["rows"], d["status"]
            for i in range(n):
                st = int(status[i])
                if st == STARTKURS_FEHLT:
                    pairs["ausgeschlossen_startkurs_fehlt"] += 1
                elif st == ABDECKUNG_ZU_GERING:
                    pairs["ausgeschlossen_mehr_als_20_prozent"] += 1
                elif st in (KURS_AM_STICHTAG_FEHLT, MARKT_GESCHLOSSEN):
                    pairs["ohne_kurs_am_stichtag_veraltet"] += 1
                if st not in V_STATUS:
                    continue
                k = rows[i]
                missing = int(m["n_exp"][k]) - int(m["n"][k])
                pairs["in_ranglisten"] += 1
                if i in own_end:
                    own_end_in_v.add(i)
                    pairs["mit_letztem_schlusskurs"] += 1
                if missing == 0:
                    continue
                pairs["mit_luecke"] += 1
                pairs["mit_1_luecke" if missing == 1 else "mit_2_bis_3_luecken" if missing <= 3 else "mit_4_und_mehr_luecken"] += 1
                if missing * 5 > int(m["n_exp"][k]):  # mehr als 20 % – nur über „eine immer erlaubt“ zugelassen
                    pairs["zugelassen_nur_durch_eine_immer_erlaubt"] += 1
                gap_pairs.setdefault(i, set()).add(h)
                stocks_with_gaps.add(i)
        report["bestand"] = dict(pairs) | {"aktien_mit_luecke_in_ranglisten": len(stocks_with_gaps), "aktien_mit_letztem_schlusskurs_in_ranglisten": len(own_end_in_v)}

        # 2. Art der Lücken beim Kursanbieter (nur Tage in Ranglisten-Zeiträumen)
        wanted: dict[int, set[int]] = {}
        listings: dict[int, dict] = {}
        window_of: dict[tuple[int, int], tuple[int, int]] = {}
        for i, hs in gap_pairs.items():
            series = stand.get(f"series/{isins[i]}.bin")
            stand.drop(f"series/{isins[i]}.bin")
            listings[i] = series.get("listing") or {}
            gaps = [int(x) for x in series.get("gaps") or []]
            for h in hs:
                k = data[h]["rows"][i]
                start = int(data[h]["m"]["start"][k])
                end = int(last_day[i]) if last_day[i] is not None else cutoff
                window_of[(i, h)] = (start, end)
                wanted.setdefault(i, set()).update(g for g in gaps if start <= g <= end)
        if args.ohne_abruf:
            kinds, fetch = {}, Counter({"uebersprungen": 1})
        else:
            kinds, fetch = classify_gaps(listings, wanted, args.abruf_budget)
        day_kinds = Counter(kind for per in kinds.values() for kind in per.values())
        empty_pairs = {(i, h) for (i, h), (s, e) in window_of.items() if any(kind == "leerzeile" and s <= day <= e for day, kind in kinds.get(i, {}).items())}
        report["luecken_beim_kursanbieter"] = {"tage": dict(day_kinds), "abruf": dict(fetch), "aktien_geprueft": len(kinds), "aktien_mit_luecke": len(wanted),
                                               "paare_mit_leerzeile": len(empty_pairs), "aktien_mit_leerzeile": len({i for i, _ in empty_pairs})}

        # 3. Einfluss auf die Ranglisten
        def v_members(h, idx):
            return idx

        def strict(h, idx):
            m, rows = data[h]["m"], data[h]["rows"]
            return [i for i in idx if int(m["n_exp"][rows[i]]) == int(m["n"][rows[i]])]

        def like_model(h, idx):
            return [i for i in idx if (i, h) not in empty_pairs]

        def without_last_close(h, idx):
            return [i for i in idx if i not in own_end]

        base = rankings(data, v_members, liquid)
        published = Counter()
        for (group, h, w), order in base.items():
            orders = data[h]["win"]["orders"]
            ref = (orders["v0"] if w == 0 else orders["u"][str(w)]) if group == "A" else (orders["v0l"] if w == 0 else (orders.get("ul") or {}).get(str(w), []))
            published["gleich" if order == ref else "anders"] += 1
        report["ranglisten_nachgerechnet_gleich_veroeffentlicht"] = dict(published)
        report["einfluss"] = {
            "streng_jede_luecke_schliesst_aus": dict(compare(base, rankings(data, strict, liquid))),
            "wie_ausgangsmodell_leerzeile_schliesst_aus": dict(compare(base, rankings(data, like_model, liquid))),
            "ohne_letzten_schlusskurs_regel_bis_1_8": dict(compare(base, rankings(data, without_last_close, liquid))),
            "ranglisten": len(base),
        }
        # Spitzenplätze mit Lücke
        top = Counter()
        for (group, h, w), order in base.items():
            m, rows = data[h]["m"], data[h]["rows"]
            for rank, i in enumerate(order[:10]):
                if int(m["n_exp"][rows[i]]) > int(m["n"][rows[i]]):
                    top["erste_10_eintraege_mit_luecke"] += 1
                    if rank == 0:
                        top["platz_1_mit_luecke"] += 1
                if (i, h) in empty_pairs:
                    top["erste_10_eintraege_mit_leerzeile"] += 1
            top["erste_10_eintraege"] += min(10, len(order))
        report["spitze"] = dict(top)

        # 4. Gleichstand
        report["gleichstand"] = dict(exact_ties(data, liquid))

    Path(args.bericht).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    b, e, s, g = report["bestand"], report["einfluss"], report["spitze"], report["gleichstand"]
    lk = report["luecken_beim_kursanbieter"]
    notice(
        f"Fehlende Kurstage im Stand {report['stand']['kursstand']}",
        [
            f"Software {report['stand']['software']}, Methode {report['stand']['methode']}, {report['stand']['aktien']} Aktien",
            f"Aktie-Zeitraum-Paare in den Ranglisten (Gruppe A, 1–90 Tage): {b.get('in_ranglisten', 0)}; mit fehlender Sitzung {b.get('mit_luecke', 0)} "
            f"(1: {b.get('mit_1_luecke', 0)}, 2–3: {b.get('mit_2_bis_3_luecken', 0)}, ≥4: {b.get('mit_4_und_mehr_luecken', 0)}; nur über „eine immer erlaubt“: {b.get('zugelassen_nur_durch_eine_immer_erlaubt', 0)}); "
            f"Aktien mit Lücke {b['aktien_mit_luecke_in_ranglisten']}",
            f"Ausgeschlossen: Starttag ohne Kurs {b.get('ausgeschlossen_startkurs_fehlt', 0)}, mehr als 20 % fehlen {b.get('ausgeschlossen_mehr_als_20_prozent', 0)}, Schlusskurs zu alt {b.get('ohne_kurs_am_stichtag_veraltet', 0)} Paare; "
            f"mit letztem Schlusskurs: {b.get('mit_letztem_schlusskurs', 0)} Paare ({b['aktien_mit_letztem_schlusskurs_in_ranglisten']} Aktien)",
            f"Beim Kursanbieter (Yahoo, {lk['aktien_geprueft']} von {lk['aktien_mit_luecke']} Aktien abgefragt, {lk['abruf'].get('sekunden', 0)} s): Tage {lk['tage']}; Paare mit Leerzeile {lk['paare_mit_leerzeile']} ({lk['aktien_mit_leerzeile']} Aktien)",
            f"Ranglisten nachgerechnet = veröffentlicht: {report['ranglisten_nachgerechnet_gleich_veroeffentlicht']}",
            f"Einfluss auf {e['ranglisten']} Ranglisten – streng: {e['streng_jede_luecke_schliesst_aus']}; wie Ausgangsmodell: {e['wie_ausgangsmodell_leerzeile_schliesst_aus']}; ohne letzten Schlusskurs: {e['ohne_letzten_schlusskurs_regel_bis_1_8']}",
            f"Erste 10 aller Ranglisten: {s.get('erste_10_eintraege', 0)} Einträge, davon mit Lücke {s.get('erste_10_eintraege_mit_luecke', 0)} (Platz 1: {s.get('platz_1_mit_luecke', 0)}), mit Leerzeile {s.get('erste_10_eintraege_mit_leerzeile', 0)}",
            f"Gleichstand (gemischte Gewichtungen): {g.get('gemischte_ranglisten', 0)} Ranglisten, mit rechnerisch gleichem Score unter den ersten 10: {g.get('mit_gleichstand_in_ersten_10', 0)}, davon Reihenfolge gegen die Rendite: {g.get('davon_reihenfolge_gegen_rendite', 0)}",
        ],
    )
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write("## Fehlende Kurstage – Zählwerte\n\n```json\n" + json.dumps(report, indent=2, ensure_ascii=False) + "\n```\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
