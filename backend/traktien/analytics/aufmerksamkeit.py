"""Aufmerksamkeit (eigene Berechnung, ab 1.25.0, ``aufmerksamkeit-1``): welche Aktien mit Mindestumsatz gerade auffallen.

Auftrag vom 07.11.2026 (17:39 und 19:06 Uhr): eigene, klar anders benannte Rangliste aus zulässigen Quellen statt der
Top-1000-Liste von onvista (deren AGB Ziffer 3.3 automatisierte Abfragen ohne schriftliche Einwilligung untersagen – die App
verlinkt sie nur). Grundlage sind allein die eigenen Kurs- und Umsatzdaten, gleich für alle Aktien:
* Umsatz am letzten Tag im Verhältnis zum Ø der 20 Sitzungen davor,
* Ø dieses Verhältnisses über die letzten fünf Tage,
* Kursbewegung am letzten Tag in Vielfachen der üblichen Tagesschwankung (Betrag – Anstieg und Rückgang zählen gleich).
Je Tag wird jede Kennzahl unter den Aktien mit Mindestumsatz in Perzentile umgerechnet; die Punktzahl ist ihr Mittel,
Platz 1 die höchste. Ränge früherer Tage entstehen aus denselben Kursdaten bis zu diesem Tag (gleiche Rechnung, kein
Nachtragen) – daraus Veränderung zum Vortag, zu vor 7 und vor 30 Handelstagen und „neu“ unter den ersten 100.
Aufmerksamkeit ist kein Kaufsignal.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

VERSION = "aufmerksamkeit-1"
TOP = 100
LOOKBACK = (1, 7, 30)
MIN_STOCKS = 20
REGEL = (
    "Eigene Berechnung aus Kurs- und Umsatzdaten der Aktien mit Ø Tagesumsatz ab 10 Mio. USD: Umsatz am letzten Tag und im "
    "Ø der letzten fünf Tage im Verhältnis zum Ø der 20 Sitzungen davor sowie die Kursbewegung am letzten Tag in Vielfachen "
    "der üblichen Tagesschwankung. Je Kennzahl Perzentil unter allen Aktien des Tages, Punktzahl = Mittel, Platz 1 = höchste. "
    "Frühere Ränge mit derselben Rechnung aus den Daten bis zu jenem Tag. Kein Kaufsignal."
)
ONVISTA_LINK = "https://www.onvista.de/aktien/top-1000"


@dataclass
class StockAttention:
    isin: str
    days: np.ndarray
    rvol: np.ndarray  # Umsatz / Ø 20 Sitzungen davor
    move: np.ndarray  # |Tagesrendite| / übliche Tagesschwankung
    r1: np.ndarray
    liquid: np.ndarray


def _pct_rank(values: np.ndarray) -> np.ndarray:
    """Perzentil (0–1) je Wert, Gleichstände gemittelt."""
    order = values.argsort(kind="mergesort")
    ranks = np.empty(len(values))
    ranks[order] = np.arange(len(values), dtype=np.float64)
    # Gleichstände: mittlerer Rang
    uniq, inv = np.unique(values, return_inverse=True)
    if len(uniq) < len(values):
        sums = np.bincount(inv, weights=ranks)
        counts = np.bincount(inv)
        ranks = (sums / counts)[inv]
    return ranks / max(1, len(values) - 1)


def compute(stocks: list[StockAttention], *, cutoff_day: int | None = None) -> dict:
    """Rangliste zum letzten gemeinsamen Tag mit Rängen früherer Tage; Index je Aktie = Position in ``stocks``."""
    all_days = sorted({int(d) for s in stocks for d in s.days.tolist()})
    if cutoff_day is not None:
        all_days = [d for d in all_days if d <= cutoff_day]
    wanted = all_days[-(max(LOOKBACK) + 1):]
    ranks_by_day: dict[int, dict[int, tuple[int, float, dict]]] = {}
    for day in wanted:
        rows, comp = [], []
        for si, s in enumerate(stocks):
            k = np.searchsorted(s.days, day)
            if k >= len(s.days) or int(s.days[k]) != day or not s.liquid[k]:
                continue
            r = s.rvol[k]
            mv = s.move[k]
            r5 = s.rvol[max(0, k - 4): k + 1]
            r5 = r5[np.isfinite(r5)]
            if not (np.isfinite(r) and np.isfinite(mv)) or len(r5) < 3:
                continue
            rows.append(si)
            comp.append((float(np.log(max(r, 1e-3))), float(np.log(max(r5.mean(), 1e-3))), float(mv)))
        if len(rows) < MIN_STOCKS:
            continue
        arr = np.array(comp)
        score = (_pct_rank(arr[:, 0]) + _pct_rank(arr[:, 1]) + _pct_rank(arr[:, 2])) / 3.0
        order = np.lexsort((np.array(rows), -score))
        ranks_by_day[day] = {
            rows[j]: (place + 1, float(score[j]), {"umsatz": float(np.exp(arr[j, 0])), "umsatz5": float(np.exp(arr[j, 1])), "bewegung": float(arr[j, 2])})
            for place, j in enumerate(order.tolist())
        }
    days_ranked = sorted(ranks_by_day)
    if not days_ranked:
        return {"version": VERSION, "regel": REGEL, "link_onvista": ONVISTA_LINK, "tag": None, "anzahl": 0, "liste": [], "hinweis": "zu wenige Aktien mit Mindestumsatz"}
    today = days_ranked[-1]
    current = ranks_by_day[today]

    def rank_ago(si: int, steps: int) -> int | None:
        pos = len(days_ranked) - 1 - steps
        if pos < 0:
            return None
        entry = ranks_by_day[days_ranked[pos]].get(si)
        return entry[0] if entry else None

    top = sorted(current.items(), key=lambda kv: kv[1][0])[:TOP]
    items = []
    for si, (rank, score, parts) in top:
        before = rank_ago(si, 1)
        s = stocks[si]
        k = int(np.searchsorted(s.days, today))
        r1 = float(s.r1[k]) if k < len(s.r1) and np.isfinite(s.r1[k]) else None
        reasons = [f"Umsatz {parts['umsatz']:.1f}-fach des Ø der 20 Sitzungen".replace(".", ",")]
        if parts["umsatz5"] >= 1.3:
            reasons.append(f"5-Tage-Ø des Umsatzes {parts['umsatz5']:.1f}-fach".replace(".", ","))
        if r1 is not None:
            reasons.append(f"Kursbewegung {r1 * 100:+.1f} % (= {parts['bewegung']:.1f}-fache übliche Tagesschwankung)".replace(".", ",").replace("-", "−", 1) if r1 < 0
                           else f"Kursbewegung {r1 * 100:+.1f} % (= {parts['bewegung']:.1f}-fache übliche Tagesschwankung)".replace(".", ","))
        items.append({
            "i": si,
            "rang": rank,
            "punkte": round(score * 100, 1),
            "vortag": before,
            "vor7": rank_ago(si, 7),
            "vor30": rank_ago(si, 30),
            "neu": before is None or before > TOP,
            "gruende": reasons,
        })
    return {
        "version": VERSION,
        "regel": REGEL,
        "link_onvista": ONVISTA_LINK,
        "tag": today,
        "tage_berechnet": len(days_ranked),
        "anzahl": len(current),
        "liste": items,
        "hinweis": "Aufmerksamkeit ist kein Kaufsignal. Nachrichten und Seitenaufrufe fließen nicht ein.",
    }
