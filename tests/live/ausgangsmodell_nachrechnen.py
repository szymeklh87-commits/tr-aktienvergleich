"""Historischer Prüffall (ab 1.17): das Ausgangsmodell mit dessen eigenen Kursreihen nachrechnen.

Simons Auftrag vom 24.10.2026: „Versuche, das fehlende historische Archiv aus vorhandenen Quellen wiederherzustellen.“
Das Archiv ``TR_Rankings_90_Tage_Rechendaten_2026-10-13.zip`` liegt nicht vor. Simons HTML-Übersicht „Aktien-Kompass“
(Uploads vom 14.10.2026) enthält aber als eingebettete Nutzlast (``<script id="payload">``, Base64 + gzip + JSON) die
Rechendaten des Ausgangsmodells TR-90D-11W-two-universes-v1.1 zum Kursstichtag 13.10.2026: je Aktie die Tageskurse
(Datum, Schlusskurs, Volumen) von Mitte Juli bis zum Stichtag, je Zeitraum Status, Startdatum und Kennzahlen, dazu alle
1.980 Ranglisten (Gruppe A/B × 90 Zeiträume × 11 Gewichtungen) in voller Länge.

Damit lässt sich prüfen, was ohne das Archiv offen war (Methodik §14): Liefert die Rechnung dieser App mit *denselben*
Eingangsdaten dieselben Ranglisten? Drei Stufen, jede mit Zählungen:

A. **Rangfolge**: die Produktionsfunktionen ``rank_window``/``group_b_ranking`` auf Rendite, R², Status und Gruppe-B-
   Kennzeichen des Ausgangsmodells – prüft Perzentile, Score-Formel, Gleichstände und Sortierung.
B. **Kennzahlen**: der Rechenkern dieser App (``compute_snapshot``) auf den Tageskursen des Ausgangsmodells – Startdatum,
   Rendite, R² und Zulassung je Aktie und Zeitraum gegen dessen Werte, getrennt nach Grund jeder Abweichung.
C. **Ganze Kette**: die Ranglisten aus B gegen die 1.980 Ranglisten des Ausgangsmodells (Gruppe B mit dessen Kennzeichen,
   weil die EZB-Kurse dieses Tages hier nicht vorliegen).

Grenzen, die das Ergebnis mitbestimmen (im Bericht genannt): Die Börsensitzungen werden aus den beobachteten Handelstagen
aller Aktien derselben Börse gebildet (hier ist kein Börsenkalender installierbar); Splits kennt die Nutzlast nur als Status
„split_in_window“ (solche Zeiträume werden getrennt gezählt); der Ø Tagesumsatz in USD wird nur über das Verhältnis zur
Angabe des Ausgangsmodells je Währung geprüft.

Die HTML-Datei wird nur gelesen – nie ausgeführt (keine Skripte, kein Browser). Ausgegeben werden nur Zählwerte: keine
Namen, Kürzel, ISINs oder Kurse. Aufruf (lokal, die Datei gehört nicht ins Repository):

    PYTHONPATH=backend python tests/live/ausgangsmodell_nachrechnen.py --html <Datei>.html --bericht bericht.json
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import gzip
import json
import math
import re
import sys
from collections import Counter, defaultdict
from dataclasses import replace
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from traktien.analytics.codes import RETURN_PUBLISHABLE, TREND_ELIGIBLE  # noqa: E402
from traktien.analytics.engine import InstrumentData, compute_snapshot  # noqa: E402
from traktien.analytics.ranking import group_b_ranking, rank_window  # noqa: E402
from traktien.config import MethodConfig, Ratio  # noqa: E402
from traktien.providers.exchanges import unit_info  # noqa: E402
from traktien.util.timeutil import date_to_day  # noqa: E402

WEIGHTS = (0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100)
REF_RETURN = {"valid_trend", "not_positive_trend", "too_few_prices_for_trend"}  # Menge V des Ausgangsmodells
REF_TREND = {"valid_trend"}  # Menge U


def load_payload(path: Path) -> tuple[dict, dict]:
    """Nutzlast und kleine Daten aus der HTML-Datei – nur Text, Base64, gzip und JSON; nichts wird ausgeführt."""
    text = path.read_bytes().decode("utf-8", errors="strict")
    small = re.search(r'<script id="small-data" type="application/json">(.*?)</script>', text, re.S)
    payload = re.search(r'<script id="payload" type="application/octet-stream">(.*?)</script>', text, re.S)
    if not payload:
        raise SystemExit("Keine eingebettete Nutzlast gefunden")
    raw = gzip.decompress(base64.b64decode(payload.group(1).strip(), validate=True))
    data = json.loads(raw)
    for key in ("items", "sets", "meta"):
        if key not in data:
            raise SystemExit(f"Nutzlast ohne „{key}“")
    return data, (json.loads(small.group(1)) if small else {})


def day_of(iso: str) -> int:
    return date_to_day(dt.date.fromisoformat(iso[:10]))


def finite(x) -> float:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return math.nan
    return v if math.isfinite(v) else math.nan


def rel(a: float, b: float) -> float:
    if not (math.isfinite(a) and math.isfinite(b)):
        return math.inf
    if a == b:
        return 0.0
    base = max(abs(a), abs(b))
    return abs(a - b) / base if base else math.inf


def compare_lists(ours: list[str], ref: list[str]) -> str:
    if ours == ref:
        return "gleich"
    if set(ours) == set(ref):
        return "gleiche_aktien_andere_reihenfolge"
    if not ours or not ref:
        return "eine_liste_leer"
    return "andere_aktien"


def first_diff(ours: list[str], ref: list[str]) -> int | None:
    for k, (a, b) in enumerate(zip(ours, ref)):
        if a != b:
            return k + 1
    return None if len(ours) == len(ref) else min(len(ours), len(ref)) + 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--html", required=True)
    parser.add_argument("--bericht", default="ausgangsmodell-nachrechnung.json")
    args = parser.parse_args()
    data, small = load_payload(Path(args.html))
    meta = data["meta"]
    cutoff = day_of(meta["cutoff"])
    items = data["items"]
    n_ref = len(items)
    order = sorted(range(n_ref), key=lambda k: items[k]["isin"])  # unser Index = Platz in ISIN-Reihenfolge
    isin = [items[k]["isin"] for k in order]
    if len(set(isin)) != len(isin):
        raise SystemExit("ISINs nicht eindeutig")
    pos_of_ref = {k: p for p, k in enumerate(order)}
    ref_items = [items[k] for k in order]
    liquid = np.array([bool(it.get("liquid")) for it in ref_items])
    report: dict = {
        "quelle": {"modell": meta.get("version"), "stichtag": meta.get("cutoff"), "erstellt": meta.get("created_at"), "aktien": n_ref,
                   "ranglisten": len(data["sets"]), "nicht_leer": sum(1 for s in data["sets"] if s["count"])},
    }

    # Ranglisten des Ausgangsmodells je (Gruppe, Tage, Gewichtung) als ISIN-Listen
    ref_sets: dict[tuple[str, int, int], list[str]] = {}
    for s in data["sets"]:
        ref_sets[(s["group"], int(s["days"]), int(s["weight_g"]))] = [items[i]["isin"] for i in s["ids"]]

    def compare_all(ranking_of) -> dict:
        verdicts = Counter()
        by_group = defaultdict(Counter)
        top = Counter()
        first = Counter()
        for (group, h, w), ref in sorted(ref_sets.items()):
            ours = ranking_of(group, h, w)
            v = compare_lists(ours, ref)
            verdicts[v] += 1
            by_group[group][v] += 1
            top["platz_1_gleich" if ours[:1] == ref[:1] else "platz_1_anders"] += 1
            top["top_10_gleich" if ours[:10] == ref[:10] else "top_10_anders"] += 1
            if v != "gleich":
                k = first_diff(ours, ref)
                first["ab_platz_1" if k == 1 else "ab_platz_2_bis_10" if k and k <= 10 else "nach_platz_10"] += 1
        return {"ranglisten": dict(verdicts), "je_gruppe": {g: dict(c) for g, c in by_group.items()}, "spitze": dict(top), "erste_abweichung": dict(first)}

    # ------------------------------------------------------------------ A: Rangfolge aus den Kennzahlen des Ausgangsmodells
    n = len(ref_items)
    a_rankings: dict[int, tuple] = {}
    for h in range(1, 91):
        r = np.full(n, np.nan)
        r2 = np.full(n, np.nan)
        v, u = [], []
        for p, it in enumerate(ref_items):
            status = (it.get("windows") or {}).get(str(h))
            m = (it.get("m") or [None] * 90)[h - 1] or [None] * 10
            if status in REF_RETURN:
                r[p] = finite(m[0])
                v.append(p)
                if status in REF_TREND:
                    r2[p] = finite(m[1])
                    u.append(p)
        zeros = np.zeros(n)
        base = rank_window(h, np.array(v, dtype=np.int64), np.array(u, dtype=np.int64), r, r2, zeros, zeros)
        group_b = group_b_ranking(base, liquid, r, r2, zeros, zeros)
        a_rankings[h] = (base, group_b)

    def from_rankings(store):
        def get(group: str, h: int, w: int) -> list[str]:
            base, group_b = store[h]
            wr = base if group == "A" else group_b
            ranking = wr.native0 if w == 0 else wr.trend[w]
            return [isin[i] for i in ranking.order.tolist()]
        return get

    report["A_rangfolge_aus_kennzahlen_des_ausgangsmodells"] = compare_all(from_rankings(a_rankings))

    # ------------------------------------------------------------------ B: Rechenkern dieser App auf den Tageskursen
    observed_by_exchange: dict[str, set[int]] = defaultdict(set)
    series: list[tuple[np.ndarray, np.ndarray, np.ndarray]] = []
    for it in ref_items:
        rows = it.get("series") or []
        days = np.array([day_of(d) for d, *_ in rows], dtype=np.int64)
        close = np.array([finite(c) for _, c, *_ in rows], dtype=np.float64)
        volume = np.array([finite(x[2]) if len(x) > 2 else math.nan for x in rows], dtype=np.float64)
        series.append((days, close, volume))
        for d, c in zip(days.tolist(), close.tolist()):
            if math.isfinite(c) and c > 0:
                observed_by_exchange[it.get("exchange") or "?"].add(d)
    sessions_of = {ex: np.array(sorted(days), dtype=np.int64) for ex, days in observed_by_exchange.items()}

    def instruments() -> list[InstrumentData]:
        out = []
        for p, it in enumerate(ref_items):
            days, close, volume = series[p]
            unit, factor = unit_info(it.get("currency"))
            out.append(
                InstrumentData(
                    isin=isin[p],
                    pre_status=0,
                    sessions=sessions_of.get(it.get("exchange") or "?", np.empty(0, dtype=np.int64)),
                    days=days,
                    close=close,
                    volume=volume,
                    currency=unit,
                    unit_factor=factor,
                )
            )
        return out

    variants = {
        "methode_1_9_0": MethodConfig(),
        # wie das Ausgangsmodell: ohne Ersatz durch den letzten Schlusskurs (ab 1.9.0) und ohne Grenze für fehlende Börsentage
        "wie_ausgangsmodell": replace(MethodConfig(), last_close_max_missed_sessions=0, min_session_coverage=Ratio(0, 1), tolerated_missing_sessions=10_000),
    }
    for name, cfg in variants.items():
        comp = compute_snapshot(instruments(), cutoff, cfg, None, workers=1)
        cats = Counter()
        mismatch = Counter()
        start_cmp = Counter()
        r_cmp = Counter()
        r2_cmp = Counter()
        reasons = defaultdict(Counter)
        for p, it in enumerate(ref_items):
            windows = it.get("windows") or {}
            for k, h in enumerate(comp.windows):
                ref_status = windows.get(str(h))
                if ref_status is None:
                    continue
                ours = int(comp.status[p, k])
                ours_cat = "U" if ours in TREND_ELIGIBLE else "V" if ours in RETURN_PUBLISHABLE else "X"
                ref_cat = "U" if ref_status in REF_TREND else "V" if ref_status in REF_RETURN else "X"
                key = f"{ref_cat}->{ours_cat}"
                cats[key] += 1
                if ref_cat != ours_cat:
                    reasons[key][f"{ref_status}|{ours}"] += 1
                if ref_cat != "X" and ours_cat != "X":
                    ref_start = (it.get("start") or [None] * 90)[h - 1]
                    start_cmp["gleich" if ref_start and int(comp.start_day[p, k]) == day_of(ref_start) else "anders"] += 1
                    m = (it.get("m") or [None] * 90)[h - 1] or [None] * 10
                    ours_r = 100.0 * float(comp.r[p, k])  # Rechenkern: Anteil; Ausgangsmodell: Prozent
                    e = rel(ours_r, finite(m[0]))
                    r_cmp["bis_1e-9" if e <= 1e-9 else "bis_1e-6" if e <= 1e-6 else "bis_1e-3" if e <= 1e-3 else "darueber"] += 1
                    if ref_cat == "U" and ours_cat == "U":
                        d = abs(float(comp.r2[p, k]) - finite(m[1]))
                        r2_cmp["bis_1e-9" if d <= 1e-9 else "bis_1e-6" if d <= 1e-6 else "bis_1e-3" if d <= 1e-3 else "darueber"] += 1
                if ref_cat != ours_cat:
                    mismatch[ref_status] += 1
        # C: Ranglisten aus diesem Rechenkern, Gruppe B mit den Kennzeichen des Ausgangsmodells
        zeros = np.zeros(n)
        c_rankings = {}
        c2_rankings = {}
        nullrow_pairs: set[tuple[int, int]] = set()
        for k, h in enumerate(comp.windows):
            base = comp.rankings[h]
            r_all = comp.r[:, k].astype(np.float64)
            r2_all = comp.r2[:, k].astype(np.float64)
            c_rankings[h] = (base, group_b_ranking(base, liquid, r_all, r2_all, zeros, zeros))
            # C2: dieselben Kennzahlen, aber Zeiträume mit Split laut Ausgangsmodell zurückgestellt (die Nutzlast enthält
            # keine Split-Termine; im Betrieb kennt der Lauf sie vom Kursanbieter und stellt solche Zeiträume selbst zurück)
            split = np.array([("split_in_window" in ((it.get("windows") or {}).get(str(h)) or "")) for it in ref_items])
            for p, it in enumerate(ref_items):
                if "invalid_price_window" in ((it.get("windows") or {}).get(str(h)) or ""):
                    nullrow_pairs.add((p, h))
            v2 = np.array([i for i in base.v_idx.tolist() if not split[i]], dtype=np.int64)
            u2 = np.array([i for i in base.u_idx.tolist() if not split[i]], dtype=np.int64)
            base2 = rank_window(h, v2, u2, r_all, r2_all, zeros, zeros)
            c2_rankings[h] = (base2, group_b_ranking(base2, liquid, r_all, r2_all, zeros, zeros))
        report[f"B_kennzahlen_{name}"] = {
            "aktie_zeitraum_paare": dict(cats),
            "abweichende_zulassung_nach_grund": {k: dict(c.most_common(12)) for k, c in reasons.items()},
            "startdatum": dict(start_cmp),
            "rendite": dict(r_cmp),
            "r2": dict(r2_cmp),
        }
        report[f"C_ranglisten_{name}"] = compare_all(from_rankings(c_rankings))
        c2 = compare_all(from_rankings(c2_rankings))
        # Welche Ranglisten unterscheiden sich dann noch – und enthalten sie einen Zeitraum mit Leerzeile beim Anbieter?
        get2 = from_rankings(c2_rankings)
        explained = Counter()
        isin_pos = {code: p for p, code in enumerate(isin)}
        for (group, h, w), ref in sorted(ref_sets.items()):
            ours = get2(group, h, w)
            if ours == ref:
                continue
            extra = set(ours) - set(ref)
            missing = set(ref) - set(ours)
            if not missing and extra and all((isin_pos[c], h) in nullrow_pairs for c in extra):
                explained["nur_zusaetzliche_aktien_mit_leerzeile_im_zeitraum"] += 1
            elif not extra and not missing:
                explained["gleiche_aktien_andere_reihenfolge"] += 1
            else:
                explained["sonstige"] += 1
        c2["abweichungen_erklaert"] = dict(explained)
        report[f"C2_ranglisten_{name}_mit_split_entscheidung_des_ausgangsmodells"] = c2

    # ------------------------------------------------------------------ Ø Tagesumsatz: Verhältnis zur Angabe des Ausgangsmodells
    comp = compute_snapshot(instruments(), cutoff, variants["wie_ausgangsmodell"], None, workers=1)
    ratios = defaultdict(list)
    for p, it in enumerate(ref_items):
        ref_usd = finite(it.get("turnover_usd"))
        t = comp.turnover[p] if p < len(comp.turnover) else None
        local = finite(getattr(t, "avg_local", None)) if t is not None else math.nan
        if math.isfinite(ref_usd) and ref_usd > 0 and math.isfinite(local) and local > 0:
            ratios[it.get("currency") or "?"].append(ref_usd / local)
    spread = {}
    for cur, values in sorted(ratios.items(), key=lambda kv: -len(kv[1])):
        arr = np.array(values)
        med = float(np.median(arr))
        spread[cur] = {"aktien": len(values), "verhaeltnis_median": round(med, 8), "abweichung_vom_median_bis_1e-6": int(np.sum(np.abs(arr / med - 1) <= 1e-6)), "bis_1_prozent": int(np.sum(np.abs(arr / med - 1) <= 0.01))}
    report["umsatz_verhaeltnis_je_waehrung"] = spread
    report["grenzen"] = {
        "sitzungen": "aus beobachteten Handelstagen je Börse gebildet (kein Börsenkalender)",
        "splits": "nur als Status des Ausgangsmodells bekannt",
        "gruppe_b": "Kennzeichen des Ausgangsmodells (EZB-Kurse dieses Tages nicht vorhanden)",
        "boersen": len(sessions_of),
    }
    Path(args.bericht).write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
