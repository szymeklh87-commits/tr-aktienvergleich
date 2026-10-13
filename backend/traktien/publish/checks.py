"""Konsistenzprüfungen vor der Veröffentlichung (Abschnitt 16, Schritt 10).

Ein Snapshot wird nur veröffentlicht, wenn alle Prüfungen tatsächlich ausgeführt und
bestanden wurden. Das Ergebnis jeder Prüfung steht im Manifest.
"""

from __future__ import annotations

import numpy as np

from ..analytics.codes import RETURN_PUBLISHABLE, WindowWarning
from ..analytics.engine import SnapshotComputation
from ..analytics.frequency import aggregate_frequency
from ..config import CANONICAL_WEIGHTS, MethodConfig


def _check(name: str, passed: bool, detail: str = "") -> dict:
    return {"name": name, "passed": bool(passed), "detail": detail}


def _order_ok(ranking, comp: SnapshotComputation, col: int, weight: int, cohort: str) -> bool:
    order = ranking.order
    if len(order) < 2:
        return True
    r = comp.r[order, col]
    if cohort == "V" or weight == 0:
        keys = list(zip(-r, order))
    elif weight == 100:
        keys = list(zip(-comp.r2[order, col], -comp.slope_pct[order, col], comp.noise_pct[order, col], order))
    else:
        keys = list(zip(-ranking.scores, -r, -comp.r2[order, col], order))
    return all(keys[k] < keys[k + 1] for k in range(len(keys) - 1))


def run_checks(comp: SnapshotComputation, cfg: MethodConfig) -> list[dict]:
    results: list[dict] = []
    n = comp.n_instruments
    results.append(_check("fenster_1_bis_90", list(comp.rankings) == list(range(1, 91)), f"{len(comp.rankings)} Fenster"))
    weights_ok = all(tuple(sorted(w.trend)) == CANONICAL_WEIGHTS for w in comp.rankings.values())
    results.append(_check("elf_gewichtungen", weights_ok))
    sums_ok = all(sum(win["by_status"].values()) == n for win in comp.ledger.per_window)
    results.append(_check("abdeckung_summe_gleich_universum", sums_ok, f"Universum {n}"))

    subset_ok = sizes_ok = unique_ok = order_ok = scores_ok = finite_ok = True
    for h, window in comp.rankings.items():
        col = h - 1
        v, u = set(window.v_idx.tolist()), set(window.u_idx.tolist())
        subset_ok &= u <= v
        sizes_ok &= window.native0.size == len(v) and all(window.trend[w].size == len(u) for w in CANONICAL_WEIGHTS)
        for ranking, weight, cohort in [(window.native0, 0, "V")] + [(window.trend[w], w, "U") for w in CANONICAL_WEIGHTS]:
            unique_ok &= len(set(ranking.order.tolist())) == ranking.size
            order_ok &= _order_ok(ranking, comp, col, weight, cohort)
            if ranking.size:
                scores_ok &= bool(np.all(np.isfinite(ranking.scores)) and ranking.scores.min() >= -1e-9 and ranking.scores.max() <= 100 + 1e-9)
        if len(v):
            finite_ok &= bool(np.all(np.isfinite(comp.r[window.v_idx, col])))
        if len(u):
            finite_ok &= bool(np.all(np.isfinite(comp.r2[window.u_idx, col])) and np.all(comp.r[window.u_idx, col] > 0) and np.all(comp.m[window.u_idx, col] > 0))
            finite_ok &= bool(np.all(comp.n_obs[window.u_idx, col] >= cfg.min_obs_trend))
    results.append(_check("u_teilmenge_von_v", subset_ok))
    results.append(_check("ranglistengroessen", sizes_ok))
    results.append(_check("eindeutige_plaetze", unique_ok))
    results.append(_check("sortierregeln", order_ok))
    results.append(_check("scores_0_bis_100", scores_ok))
    results.append(_check("aufwaertsbedingungen_und_endliche_werte", finite_ok))

    winners_ok = len(comp.winners) == 90
    for row in comp.winners:
        ranking = comp.rankings[row.h].native0
        if ranking.size:
            winners_ok &= bool(row.entries) and row.entries[0]["idx"] == int(ranking.order[0])
        else:
            winners_ok &= not row.entries and row.empty_reason is not None
    results.append(_check("renditesieger_90_zeilen", winners_ok))

    # Ranking 2: dieselben Renditen und dieselbe Reihenfolge wie Ranking 1, nur Aktien aus L
    liquid = comp.liquid if len(comp.liquid) == n else np.zeros(n, dtype=bool)
    second_ok = len(comp.winners_liquid) == 90
    for h, window in comp.rankings.items():
        second = window.native0_liquid
        if second is None:
            second_ok = False
            continue
        expected = [i for i in window.native0.order.tolist() if liquid[i]]
        second_ok &= second.order.tolist() == expected
        for t in second.order.tolist():
            second_ok &= bool(comp.turnover[t].determined and comp.turnover[t].avg_usd >= cfg.turnover_threshold_usd)
    for row in comp.winners_liquid:
        ranking = comp.rankings[row.h].native0_liquid
        if ranking is not None and ranking.size:
            second_ok &= bool(row.entries) and row.entries[0]["idx"] == int(ranking.order[0])
            second_ok &= all(e["end_day"] == comp.cutoff_day for e in row.entries)
        else:
            second_ok &= not row.entries
    results.append(_check("ranking2_teilmenge_gleiche_rendite", second_ok, f"{int(liquid.sum())} Aktien mit Ø Umsatz ≥ {cfg.turnover_threshold_usd:,.0f} USD".replace(",", ".")))

    freq_ok = True
    for policy in ("native", "common_trend"):
        result = aggregate_frequency(
            comp.rankings, policy=policy, weights=CANONICAL_WEIGHTS, window_days=comp.windows, top_k=10,
            r_matrix=comp.r, start_matrix=comp.start_day, cutoff_day=comp.cutoff_day, isin_of=comp.isin_of,
        )
        freq_ok &= result.valid_cells <= 990
        for e in result.entries:
            freq_ok &= e.n1 <= e.n3 <= e.n10 <= e.available_cells <= result.valid_cells
            freq_ok &= len(e.occurrences) == e.n10 and e.distinct_windows_k <= 90 and e.distinct_weights_k <= 11
    results.append(_check("haeufigkeit_invarianten", freq_ok))

    venue = comp.venue
    if venue is not None:
        # Das Kennzeichen „Kursabweichung zwischen Börsenplätzen“ steht genau bei den geprüften
        # Aktie-Zeitraum-Paaren mit Ergebnis „abweichung“ – und nur bei Aktien mit Rendite (V).
        bit = np.uint16(1 << WindowWarning.BOERSENPLATZ_ABWEICHUNG)
        flagged = (comp.wflags & bit) != 0
        expected = np.zeros_like(flagged)
        publishable = np.isin(comp.status, [int(s) for s in RETURN_PUBLISHABLE])
        venue_ok = True
        for idx, result in venue.results.items():
            for col, pair in result.pairs.items():
                venue_ok &= bool(publishable[idx, col])
                if pair.status == "abweichung":
                    expected[idx, col] = True
        venue_ok &= bool(np.array_equal(flagged, expected))
        counts = venue.counts()
        detail = f"{counts['aktien'].get('geprueft', 0)} von {counts['kandidaten']} Aktien geprüft, {counts['auffaellige_aktien']} auffällig"
        results.append(_check("boersenplatz_kennzeichen", venue_ok, detail))

    rotation = comp.rotation
    if rotation is not None:
        passed, detail = _rotation_ok(rotation)
        results.append(_check("umschichtung_regel_eingehalten", passed, detail))
    return results


def _rotation_ok(outcome) -> tuple[bool, str]:
    """Umschichtungs-Regel: alle Varianten gerechnet, Verläufe vollständig und endlich, Käufe nur
    unter den ersten N Plätzen, höchstens N Positionen, kein negatives Bargeld, Gebühren = Orders × Pauschale."""
    cfg = outcome.config
    expected = len(cfg.holdings) * len(cfg.rhythms) * len(cfg.lookback_weeks) * len(cfg.capitals)
    if outcome.note and not outcome.results:
        return True, outcome.note
    ok = len(outcome.results) == expected
    computed = 0
    for key, result in outcome.results.items():
        v = result.variant
        ok &= key == v.key
        if result.status != "ok":
            ok &= not result.trades and not result.days
            continue
        computed += 1
        n_points = len(result.days)
        ok &= n_points > 0 and len(result.equity) == len(result.equity_gross) == len(result.benchmark) == n_points
        ok &= all(result.days[k] < result.days[k + 1] for k in range(n_points - 1))
        for series in (result.equity, result.equity_gross, result.benchmark):
            ok &= bool(np.all(np.isfinite(series)) and np.all(np.asarray(series) > 0))
        portfolio = result.portfolio
        ok &= portfolio is not None and portfolio.cash >= -1e-6 and len(portfolio.positions) <= v.holdings
        if portfolio is not None:
            ok &= abs(portfolio.fees - portfolio.orders * outcome.costs.fee) < 1e-6
            ok &= portfolio.orders == len(result.trades)
        rebalance_days = set(result.rebalance_days)
        for trade in result.trades:
            ok &= trade.day in rebalance_days
            if trade.action == "kauf":
                ok &= trade.rank is not None and trade.rank <= v.holdings
        preview = outcome.previews.get(key)
        if preview is not None:
            ok &= len(preview.holdings) <= v.holdings and preview.cash >= -1e-6
            ok &= sum(h["weight"] for h in preview.holdings) <= 1.0 + 1e-9
            for action in preview.actions:
                if action["action"] == "kauf":
                    ok &= action["rank"] is not None and action["rank"] <= v.holdings
    return bool(ok), f"{computed} von {expected} Varianten mit Rückblick, {outcome.pool} Aktien mit Wochenwerten"
