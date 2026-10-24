"""Referenzfälle: Gleichstand (ab 1.18.0, ranking-11w-v3 in tr-methode-1.10.0). SYNTHETISCHE Zahlen.

Simons Entscheidung vom 24.10.2026: „Bei mathematisch gleichem Score entscheidet die höhere Rendite. Sind beide Werte
gleich, verwende die ISIN als eindeutiges, stabiles Sortierkriterium. Verhindere, dass Rundungsfehler die Reihenfolge
bestimmen. Unterschiedliche Scores dürfen durch pauschales Runden nicht künstlich gleichgesetzt werden.“ – „Sichere beide
Regeln mit unabhängig nachgerechneten Referenzfällen ab. Prüfe besonders Platz 1 und die Top 10.“

Die erwartete Reihenfolge rechnet dieser Test **selbst**: doppelte Durchschnittsränge, Perzentile
P = 100 · (Rang − 1) / (M − 1) und Score = w/100 · G + (1 − w/100) · R als exakte Brüche (``fractions.Fraction``) nach
docs/03_Methodik.md; sortiert nach Score absteigend, Rendite absteigend, ISIN (Index) aufsteigend. Der Rechenkern
(``rank_window``, Gruppe B, Veröffentlichungsprüfung, Methodenvergleich) muss genau diese Reihenfolge liefern. Die App
rechnet Untergruppen mit derselben Regel (app/tests/pure.test.ts, Vertragstest gegen den Server).

Instrumente sind über ihren Index adressiert; der Index ist die Position in der nach ISIN sortierten Instrumenttabelle
(kleinerer Index = kleinere ISIN). Ränge sind aufsteigend: Rang 1 = kleinster Wert.
"""

from __future__ import annotations

import unittest
from fractions import Fraction
from types import SimpleNamespace

import numpy as np

from traktien.analytics.codes import Status
from traktien.analytics.comparison import compare_with_previous_rules
from traktien.analytics.ranking import exact_score_key, group_b_ranking, rank_window, tie_rule_of, weighted_score
from traktien.config import CANONICAL_WEIGHTS, load_method_config
from traktien.publish.checks import _order_ok

MIXED = [w for w in CANONICAL_WEIGHTS if 0 < w < 100]


# ------------------------------------------------------------------ unabhängige Rechnung (ohne Rechenkern)


def doubled_ranks(values: list) -> list[int]:
    """Doppelter aufsteigender Durchschnittsrang; exakt gleiche Werte a…b erhalten a + b."""
    order = sorted(range(len(values)), key=lambda k: values[k])
    out = [0] * len(values)
    k = 0
    while k < len(order):
        j = k
        while j + 1 < len(order) and values[order[j + 1]] == values[order[k]]:
            j += 1
        for m in order[k : j + 1]:
            out[m] = (k + 1) + (j + 1)
        k = j + 1
    return out


def exact_scores(members: list[int], r: np.ndarray, r2: np.ndarray, weight: int) -> dict[int, Fraction]:
    """Score je Mitglied als Bruch: Perzentile innerhalb der Mitglieder, keine Gleitkommarechnung."""
    m = len(members)
    rr = [Fraction(float(r[i])) for i in members]
    gg = [Fraction(float(r2[i])) for i in members]
    d_r, d_g = doubled_ranks(rr), doubled_ranks(gg)

    def pct(d: int) -> Fraction:
        return Fraction(100) if m == 1 else Fraction(100 * (d - 2), 2 * (m - 1))

    return {i: Fraction(weight, 100) * pct(d_g[k]) + Fraction(100 - weight, 100) * pct(d_r[k]) for k, i in enumerate(members)}


def expected(members: list[int], r: np.ndarray, r2: np.ndarray, weight: int, *, cohort: str = "U") -> tuple[list[int], list[int]]:
    """Reihenfolge und Gleichstandsplätze nach der Regel (Score exakt, dann Rendite, dann ISIN)."""
    if cohort == "V":  # 0/100 auf V: Score = Renditeperzentil, monoton in der Rendite
        key = {i: Fraction(float(r[i])) for i in members}
    elif weight == 100:  # 100/0: Score = R²-Perzentil, monoton im R²
        key = {i: Fraction(float(r2[i])) for i in members}
    else:
        key = exact_scores(members, r, r2, weight)
    order = sorted(members, key=lambda i: (-key[i], -Fraction(float(r[i])), i))
    ties = sorted({k for k in range(len(order) - 1) if key[order[k]] == key[order[k + 1]]} | {k + 1 for k in range(len(order) - 1) if key[order[k]] == key[order[k + 1]]})
    return order, ties


def float_order(members: list[int], r: np.ndarray, r2: np.ndarray, weight: int) -> list[int]:
    """Regel bis tr-methode-1.9.0 (ranking-11w-v2) zum Vergleich: Gleitkomma-Score in der Operationsfolge der Anzeige."""
    m = len(members)
    d_r = doubled_ranks([float(r[i]) for i in members])
    d_g = doubled_ranks([float(r2[i]) for i in members])
    pct = (lambda d: 100.0 * (d / 2.0 - 1.0) / (m - 1)) if m > 1 else (lambda d: 100.0)
    score = {i: (weight / 100) * pct(d_g[k]) + (1 - weight / 100) * pct(d_r[k]) for k, i in enumerate(members)}
    return sorted(members, key=lambda i: (-score[i], -float(r[i]), i))


def universe(rank_g: list[int], rank_r: list[int]) -> tuple[np.ndarray, np.ndarray]:
    """Werte zu vorgegebenen Rängen (alle verschieden): R² = 0,30 + Rang/1000 · 0,6, Rendite = Rang · 0,1 %."""
    n = len(rank_g)
    assert sorted(rank_g) == sorted(rank_r) == list(range(1, n + 1))
    r2 = np.array([0.30 + 0.6 * g / (n + 1) for g in rank_g])
    r = np.array([0.001 * x for x in rank_r])
    return r, r2


def window(r: np.ndarray, r2: np.ndarray, rule: str = "v3", members: list[int] | None = None):
    idx = np.arange(len(r)) if members is None else np.asarray(members, dtype=np.int64)
    ones = np.ones(len(r))
    return rank_window(30, idx, idx, r, r2, ones, ones, rule)


# ------------------------------------------------------------------ Fall 1: Gleichstand auf Platz 1


# 15 Aktien, 60/40. Y (Index 0) und X (Index 1) haben rechnerisch denselben Score 640/7 = 91,428…: Y hat das beste R²
# (Rang 15) und die viertbeste Rendite (Rang 12), X das drittbeste R² (Rang 13) und die beste Rendite (Rang 15).
# 0,6 · 100·12/14 + 0,4 · 100 = 0,6 · 100 + 0,4 · 100·11/14 = 640/7. Als Gleitkommazahl ist Y in der letzten Stelle
# größer – bis 1.9.0 stand deshalb Y vorn. Jetzt entscheidet die höhere Rendite: X.
FIRST_G = [15, 13, 14, 1, 2] + [3 + k for k in range(10)]
FIRST_R = [12, 15, 1, 14, 13] + [11 - k for k in range(10)]
Y, X = 0, 1

# 20 Aktien, 60/40 (gesucht mit festem Startwert; die Ränge sind hier Daten). Aktie 14 (R²-Rang 14, Rendite-Rang 7) und
# Aktie 1 (R²-Rang 18, Rendite-Rang 1) haben rechnerisch denselben Score und stehen auf den Plätzen 10 und 11. Aktie 14
# hat die höhere Rendite und gehört unter die ersten 10; bis 1.9.0 stand dort Aktie 1 (Gleitkomma eine Stelle größer).
# Dazu ein Gleichstand auf den Plätzen 5 und 6 (Aktien 16 und 13), den ebenfalls die höhere Rendite entscheidet.
TOP_G = [7, 18, 1, 10, 3, 9, 2, 4, 5, 11, 16, 8, 12, 17, 14, 15, 13, 20, 6, 19]
TOP_R = [12, 1, 5, 16, 4, 2, 8, 18, 11, 14, 17, 6, 20, 9, 7, 10, 15, 19, 3, 13]
IN_TOP10, OUT_TOP10 = 14, 1


class FirstPlaceTie(unittest.TestCase):
    def setUp(self) -> None:
        self.r, self.r2 = universe(FIRST_G, FIRST_R)
        self.members = list(range(len(self.r)))

    def test_scores_are_mathematically_equal_but_differ_as_floating_point_numbers(self):
        exact = exact_scores(self.members, self.r, self.r2, 60)
        self.assertEqual(exact[X], exact[Y])
        self.assertEqual(exact[X], Fraction(640, 7))
        self.assertTrue(all(exact[i] < exact[X] for i in self.members if i not in (X, Y)), "sonst niemand so hoch")
        g = np.array([100.0 * (FIRST_G[i] - 1) / 14 for i in (X, Y)])
        rp = np.array([100.0 * (FIRST_R[i] - 1) / 14 for i in (X, Y)])
        floating = weighted_score(60, g, rp)
        self.assertLess(floating[0], floating[1], "Gleitkomma: Y eine Stelle größer")
        self.assertGreater(self.r[X], self.r[Y], "X hat die höhere Rendite")

    def test_higher_return_takes_first_place(self):
        ranking = window(self.r, self.r2).trend[60]
        self.assertEqual(ranking.order[:2].tolist(), [X, Y])
        self.assertEqual(ranking.tie_positions[:2].tolist(), [0, 1], "Platz 1 und 2 als Gleichstand gekennzeichnet")
        self.assertEqual(window(self.r, self.r2, "v2").trend[60].order[:2].tolist(), [Y, X], "bis 1.9.0: die Rundung entschied")

    def test_every_weight_matches_the_independent_order(self):
        w = window(self.r, self.r2)
        order, ties = expected(self.members, self.r, self.r2, 0, cohort="V")
        self.assertEqual((w.native0.order.tolist(), w.native0.tie_positions.tolist()), (order, ties))
        for weight in CANONICAL_WEIGHTS:
            with self.subTest(w=weight):
                order, ties = expected(self.members, self.r, self.r2, weight)
                self.assertEqual(w.trend[weight].order.tolist(), order)
                self.assertEqual(w.trend[weight].tie_positions.tolist(), ties)

    def test_publication_check_follows_the_exact_rule(self):
        w = window(self.r, self.r2)
        comp = SimpleNamespace(r=self.r.reshape(-1, 1), r2=self.r2.reshape(-1, 1))
        ranking = w.trend[60]
        self.assertTrue(_order_ok(ranking, comp, 0, 60, "U", w))
        old = window(self.r, self.r2, "v2")
        self.assertFalse(_order_ok(old.trend[60], comp, 0, 60, "U", w), "Gleitkomma-Reihenfolge verstößt gegen v3")
        self.assertTrue(_order_ok(old.trend[60], comp, 0, 60, "U", old), "Stand nach v2 wird nach v2 geprüft")


# ------------------------------------------------------------------ Fall 2: Gleichstand an der Grenze der ersten 10


class TopTenBoundaryTie(unittest.TestCase):
    def setUp(self) -> None:
        self.r, self.r2 = universe(TOP_G, TOP_R)
        self.members = list(range(len(self.r)))

    def test_higher_return_enters_the_top_ten(self):
        exact = exact_scores(self.members, self.r, self.r2, 60)
        self.assertEqual(exact[IN_TOP10], exact[OUT_TOP10])
        self.assertGreater(self.r[IN_TOP10], self.r[OUT_TOP10])
        self.assertGreater(IN_TOP10, OUT_TOP10, "die ISIN spräche für die andere Aktie – sie entscheidet hier nicht")
        ranking = window(self.r, self.r2).trend[60]
        self.assertEqual(ranking.order[9:11].tolist(), [IN_TOP10, OUT_TOP10])
        self.assertTrue({9, 10} <= set(ranking.tie_positions.tolist()))
        old = window(self.r, self.r2, "v2").trend[60]
        self.assertIn(OUT_TOP10, old.order[:10].tolist())
        self.assertNotIn(IN_TOP10, old.order[:10].tolist())
        # ein zweiter Gleichstand auf den Plätzen 5 und 6: Aktie 16 (R²-Rang 13, Rendite-Rang 15) und 13 (17, 9)
        self.assertEqual(exact_scores(self.members, self.r, self.r2, 60)[16], exact_scores(self.members, self.r, self.r2, 60)[13])
        self.assertEqual((ranking.order[4:6].tolist(), old.order[4:6].tolist()), ([16, 13], [13, 16]))
        self.assertEqual(set(ranking.order[:9].tolist()), set(old.order[:9].tolist()), "Plätze 1–9: dieselben Aktien")
        self.assertEqual(ranking.order[0], old.order[0], "Platz 1 unverändert")

    def test_every_weight_matches_the_independent_order(self):
        w = window(self.r, self.r2)
        for weight in CANONICAL_WEIGHTS:
            with self.subTest(w=weight):
                order, ties = expected(self.members, self.r, self.r2, weight)
                self.assertEqual(w.trend[weight].order.tolist(), order)
                self.assertEqual(w.trend[weight].tie_positions.tolist(), ties)

    def test_method_comparison_reports_first_place_and_top_ten(self):
        """Der Methodenvergleich jedes Laufs (1.9.0 → 1.10.0) zählt genau die unabhängig bestimmten Unterschiede."""
        n = len(self.r)
        current = window(self.r, self.r2)
        liquid = np.ones(n, dtype=bool)
        ones = np.ones((n, 1))
        current.group_b = group_b_ranking(current, liquid, self.r, self.r2, ones[:, 0], ones[:, 0])
        status = np.full((n, 1), int(Status.TREND_BEWERTBAR), dtype=np.uint8)
        cfg = load_method_config()
        self.assertEqual(cfg.previous_tie_rule, "v2")
        cmp = compare_with_previous_rules(
            status=status, previous_status=status.copy(), rankings={30: current}, liquid=liquid,
            r=self.r.reshape(-1, 1), r2=self.r2.reshape(-1, 1), slope=ones, noise=ones, windows=(30,), cfg=cfg,
        )  # fmt: skip
        first = top_members = top_order = changed = 0
        for weight in MIXED:
            new, _ = expected(self.members, self.r, self.r2, weight)
            old = float_order(self.members, self.r, self.r2, weight)
            first += new[0] != old[0]
            top_members += set(new[:10]) != set(old[:10])
            top_order += set(new[:10]) == set(old[:10]) and new[:10] != old[:10]
            changed += new != old
        # Gruppe A und B (hier alle Aktien in L) zählen je einmal
        got = cmp["ranglisten"]
        self.assertEqual((got["verglichen"], got["spitze_geaendert"], got["top10_andere_aktien"], got["top10_andere_reihenfolge"], got["reihenfolge_geaendert"]), (22, 2 * first, 2 * top_members, 2 * top_order, 2 * changed))
        self.assertGreaterEqual(top_members, 1)
        self.assertEqual((cmp["paare"]["neu_bewertet"], cmp["paare"]["nicht_mehr_bewertet"]), (0, 0))


# ------------------------------------------------------------------ Fall 3: gleicher Score und gleiche Rendite


class SameScoreAndReturn(unittest.TestCase):
    def test_isin_decides_and_the_order_is_stable(self):
        """Aktie 3 und 7 haben dieselbe Rendite und dasselbe R² (also in jeder Gewichtung denselben Score): die kleinere
        ISIN steht vorn – unabhängig davon, in welcher Reihenfolge die Aktien übergeben werden."""
        rng = np.random.default_rng(11)  # SYNTHETISCH
        r = rng.uniform(0.01, 0.2, 12)
        r2 = rng.uniform(0.3, 0.95, 12)
        r[7], r2[7] = r[3], r2[3]
        members = list(range(12))
        w = window(r, r2)
        shuffled = np.array([5, 11, 7, 0, 3, 9, 1, 10, 2, 8, 4, 6])
        again = rank_window(30, shuffled, shuffled, r, r2, np.ones(12), np.ones(12))
        for weight in CANONICAL_WEIGHTS:
            with self.subTest(w=weight):
                order = w.trend[weight].order.tolist()
                self.assertLess(order.index(3), order.index(7))
                self.assertEqual(order.index(7), order.index(3) + 1)
                self.assertIn(order.index(3), w.trend[weight].tie_positions.tolist())
                self.assertEqual(order, expected(members, r, r2, weight)[0])
                self.assertEqual(again.trend[weight].order.tolist(), order, "stabil")


# ------------------------------------------------------------------ Fall 4: knapp verschiedene Scores bleiben verschieden


class CloseScoresStayDifferent(unittest.TestCase):
    def test_smallest_possible_difference_is_not_rounded_away(self):
        """1.001 Aktien, 60/40: P (R²-Rang 900, Rendite-Rang 500) hat den Score 73,90, Q (899, 501) 73,88 – der kleinste
        mögliche Abstand 0,02. Mit einer Nachkommastelle sehen beide gleich aus (73,9); Q hat die höhere Rendite.
        Entscheidend ist der Score: P steht vor Q, ohne Gleichstand. Pauschales Runden auf eine Stelle hätte Q vorn."""
        n = 1001
        rng = np.random.default_rng(3)  # SYNTHETISCH: übrige Ränge zufällig verteilt
        P, Q = 400, 401
        rest_g = [g for g in range(1, n + 1) if g not in (900, 899)]
        rest_r = [x for x in range(1, n + 1) if x not in (500, 501)]
        rng.shuffle(rest_g)
        rng.shuffle(rest_r)
        rank_g, rank_r = list(rest_g), list(rest_r)
        rank_g[P:P] = [900, 899]
        rank_r[P:P] = [500, 501]
        r, r2 = universe(rank_g, rank_r)
        members = list(range(n))
        exact = exact_scores(members, r, r2, 60)
        self.assertEqual((exact[P], exact[Q]), (Fraction(7390, 100), Fraction(7388, 100)))
        self.assertEqual(round(float(exact[P]), 1), round(float(exact[Q]), 1))
        self.assertGreater(r[Q], r[P])
        ranked = window(r, r2)
        order = ranked.trend[60].order.tolist()
        self.assertLess(order.index(P), order.index(Q))
        keys = exact_score_key(60, ranking_doubled(ranked, "g"), ranking_doubled(ranked, "r"))
        self.assertEqual((int(keys[P]), int(keys[Q])), (147_800, 147_760), "Score · 2·(M − 1)")
        self.assertEqual(order, expected(members, r, r2, 60)[0])
        rounded = sorted(members, key=lambda i: (-round(float(exact[i]), 1), -float(r[i]), i))
        self.assertLess(rounded.index(Q), rounded.index(P), "gerundet stünde Q vorn – deshalb wird nicht gerundet")


def ranking_doubled(w, which: str) -> np.ndarray:
    """Doppelte Ränge des Fensters je Instrumentindex (für den Schlüssel; Mitglieder = alle)."""
    values = w.ar2_g_u if which == "g" else w.ar2_r_u
    out = np.zeros(int(w.u_idx.max()) + 1, dtype=np.int64)
    out[w.u_idx] = values
    return out


# ------------------------------------------------------------------ Fall 5: viele Zufallsuniversen


class RandomUniverses(unittest.TestCase):
    def test_kernel_matches_the_independent_exact_order(self):
        """60 Universen mit 2 bis 240 Aktien, absichtlich vielen gleichen Renditen und R² (auf wenige Stellen gerundete
        Werte): alle elf Gewichtungen, Gruppe A und B, Reihenfolge und Gleichstandsplätze wie die unabhängige Rechnung.
        Gegenprobe zur Regel bis 1.9.0: Sie weicht nur innerhalb rechnerisch gleicher Scores ab – verschiedene Scores
        hat auch der Gleitkomma-Vergleich nie vertauscht."""
        rng = np.random.default_rng(2026)  # SYNTHETISCH
        differed = 0
        for case in range(60):
            n = int(rng.integers(2, 241))
            digits = int(rng.integers(2, 5))
            r = np.round(rng.normal(0.04, 0.05, n), digits)
            r2 = np.round(rng.uniform(0.2, 0.99, n), digits)
            v = sorted(int(i) for i in np.nonzero(rng.random(n) < 0.9)[0]) or [0]
            u = [i for i in v if rng.random() < 0.8] or [v[0]]
            liquid = rng.random(n) < 0.5
            ones = np.ones(n)
            w = rank_window(30, np.array(v), np.array(u), r, r2, ones, ones)
            b = group_b_ranking(w, liquid, r, r2, ones, ones)
            old = rank_window(30, np.array(v), np.array(u), r, r2, ones, ones, "v2")
            for label, ranked, vv, uu in (("A", w, v, u), ("B", b, [i for i in v if liquid[i]], [i for i in u if liquid[i]])):
                order, ties = expected(vv, r, r2, 0, cohort="V")
                self.assertEqual((ranked.native0.order.tolist(), ranked.native0.tie_positions.tolist()), (order, ties), (case, label))
                for weight in CANONICAL_WEIGHTS:
                    order, ties = expected(uu, r, r2, weight)
                    self.assertEqual(ranked.trend[weight].order.tolist(), order, (case, label, weight))
                    self.assertEqual(ranked.trend[weight].tie_positions.tolist(), ties, (case, label, weight))
            for weight in MIXED:
                if not u:
                    continue
                exact = exact_scores(u, r, r2, weight)
                seq = [exact[i] for i in old.trend[weight].order.tolist()]
                self.assertTrue(all(a >= b for a, b in zip(seq, seq[1:])), "Gleitkomma vertauscht keine verschiedenen Scores")
                differed += old.trend[weight].order.tolist() != w.trend[weight].order.tolist()
        self.assertGreater(differed, 0, "die Zufallsdaten enthalten den Fehler der alten Regel")


class Versions(unittest.TestCase):
    def test_operating_configuration_uses_the_exact_rule(self):
        cfg = load_method_config()
        self.assertEqual((cfg.method_version, cfg.ranking_version, cfg.tie_rule), ("tr-methode-1.10.0", "ranking-11w-v3", "v3"))
        self.assertEqual((cfg.previous_method_version, cfg.previous_tie_rule), ("tr-methode-1.9.0", "v2"))
        self.assertEqual([tie_rule_of(f"ranking-11w-v{k}") for k in (1, 2, 3)], ["v1", "v2", "v3"])
        with self.assertRaises(ValueError):
            tie_rule_of("ranking-11w-v9")


if __name__ == "__main__":
    unittest.main()
