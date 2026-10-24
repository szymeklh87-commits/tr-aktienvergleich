"""Referenzfälle: fehlende Kurstage (ab 1.17.1). SYNTHETISCHE Zahlen.

Simons Auftrag vom 24.10.2026: „Sichere die Behandlung fehlender Kurstage mit nachvollziehbaren Referenztests ab.
Dokumentiere ihren Einfluss auf Ranglisten.“

Ein erfundenes Universum aus zehn Aktien läuft durch den **ganzen Rechenkern** (``compute_snapshot`` mit der
Methodenkonfiguration aus ``config/methode.yaml``, eigener Endtag wie im täglichen Lauf über ``own_cutoff_day``). Jede
Aktie steht für einen Fall fehlender Kurstage. Die erwarteten Werte – Startsitzung, Zahl der Kurse und Sitzungen,
Zulassung, Kursrendite, R² und die Reihenfolge der Ranglisten – werden hier **unabhängig vom Rechenkern** bestimmt:
Renditen und R² mit exakten Brüchen (``fractions.Fraction``), Perzentile und Reihenfolge mit einer eigenen kurzen
Rechnung nach docs/03_Methodik.md. Rechenweg, Tabellen und der Einfluss auf die Ranglisten stehen in
docs/12_Fehlende_Kurstage.md (dieselben Zahlen).

Stichtag Freitag, 23.10.2026. Kalender „Mo–Fr“ ohne Feiertage; Aktie J an einer Börse mit Feiertag am 12.10.
(wie Toronto, Thanksgiving). Kurs je Sitzung: p_j = P0 + Schritt · j + w_j mit j = Nummer der Börsensitzung ab dem
Ankertag (23.09., bei G 22.09.) und der kleinen Schwankung w_j = +δ bei j mod 4 = 1, −δ bei j mod 4 = 3, sonst 0.
Fehlende Kurstage werden aus der Reihe entfernt („keine Zeile“) oder als Leerzeile (Tag ohne Kurs und Umsatz)
eingetragen; nichts wird aufgefüllt.
"""

from __future__ import annotations

import datetime as dt
import os
import unittest
from fractions import Fraction

import numpy as np

from traktien.analytics.codes import RETURN_PUBLISHABLE, Status
from traktien.analytics.engine import InstrumentData, compute_snapshot
from traktien.config import load_method_config
from traktien.jobs.daily import own_cutoff_day
from traktien.util.timeutil import date_to_day

from tests.helpers import test_isin, weekday_sessions

CFG = load_method_config()  # die Regeln des Betriebs (tr-methode-1.9.0), nicht die Voreinstellungen im Code
CUTOFF = date_to_day(dt.date(2026, 10, 23))
WEEKDAYS = weekday_sessions(dt.date(2026, 6, 1), dt.date(2026, 10, 23))
TORONTO = weekday_sessions(dt.date(2026, 6, 1), dt.date(2026, 10, 23), [dt.date(2026, 10, 12)])
VOLUME = 1_000_000.0
V_CODES = {int(s) for s in RETURN_PUBLISHABLE}


def oct(day: int, month: int = 10) -> int:
    return date_to_day(dt.date(2026, month, day))


def frac(x: float) -> Fraction:
    return Fraction(str(x))


# Fall → (Buchstabe, Ankertag, P0, Schritt, δ, Kalender, fehlende Tage ohne Zeile, Leerzeilen, Beschreibung)
CASES = [
    ("A", oct(23, 9), "100", "0.5", "0.2", WEEKDAYS, [], [], "keine Lücke"),
    ("B", oct(23, 9), "100", "0.6", "0.3", WEEKDAYS, [oct(7)], [], "eine Sitzung ohne Kurs (keine Zeile) am 07.10."),
    ("C", oct(23, 9), "100", "0.55", "0.25", WEEKDAYS, [], [oct(7)], "eine Leerzeile (Tag ohne Kurs und Umsatz) am 07.10."),
    ("D", oct(23, 9), "100", "0.7", "0.35", WEEKDAYS, [oct(30, 9), oct(6), oct(12), oct(15)], [], "vier Sitzungen ohne Kurs"),
    ("E", oct(23, 9), "100", "0.9", "0.1", WEEKDAYS, [oct(30, 9), oct(5), oct(6), oct(7), oct(8)], [], "fünf Sitzungen ohne Kurs"),
    ("F", oct(23, 9), "100", "0.8", "0.15", WEEKDAYS, [oct(23, 9)], [], "Kurs am Starttag 23.09. fehlt"),
    ("G", oct(22, 9), "100", "0.65", "0.2", WEEKDAYS, [oct(23)], [], "Schlusskurs am Stichtag fehlt (eine Sitzung)"),
    ("H", oct(23, 9), "100", "1.0", "0.1", WEEKDAYS, [oct(22), oct(23)], [], "Schlusskurse der letzten zwei Sitzungen fehlen"),
    ("J", oct(23, 9), "100", "0.45", "0.15", TORONTO, [], [], "Börse mit Feiertag am 12.10."),
    ("K", oct(23, 9), "100", "0.3", "0.05", WEEKDAYS, [oct(21)], [], "eine Sitzung ohne Kurs am 21.10."),
]
LETTERS = [c[0] for c in CASES]
IDX = {letter: k for k, letter in enumerate(LETTERS)}


def price(p0: Fraction, step: Fraction, delta: Fraction, j: int) -> Fraction:
    wiggle = delta if j % 4 == 1 else -delta if j % 4 == 3 else Fraction(0)
    return p0 + step * j + wiggle


def series(case) -> tuple[list[int], list[Fraction | None]]:
    """Alle Sitzungen der Aktie bis zum Stichtag mit exaktem Kurs; ``None`` = Leerzeile, fehlende Tage entfallen."""
    _, anchor, p0, step, delta, sessions, absent, empty, _ = case
    k0 = int(np.searchsorted(sessions, anchor))
    days, prices = [], []
    for k, d in enumerate(sessions.tolist()):
        if d in absent:
            continue
        days.append(d)
        prices.append(None if d in empty else price(frac(p0), frac(step), frac(delta), k - k0))
    return days, prices


def instrument(number: int, case) -> InstrumentData:
    days, prices = series(case)
    close = np.array([np.nan if p is None else float(p) for p in prices], dtype=np.float64)
    volume = np.array([np.nan if p is None else VOLUME for p in prices], dtype=np.float64)
    sessions = case[5]
    inst = InstrumentData(isin=test_isin(number), sessions=sessions, days=np.array(days, dtype=np.int64), close=close, volume=volume, currency="USD")
    # wie im täglichen Lauf: ohne Schlusskurs am Stichtag der letzte Schlusskurs (höchstens eine verpasste Sitzung)
    inst.cutoff_day = own_cutoff_day(inst.days, inst.close, sessions, CUTOFF, int(CFG.last_close_max_missed_sessions))
    return inst


def exact_r2(prices: list[Fraction]) -> Fraction:
    """R² der Geraden durch (i, p_i), i = 0 … n−1 (Beobachtungsnummer, Lücken nicht aufgefüllt), als exakter Bruch."""
    n = len(prices)
    t_mean = Fraction(n - 1, 2)
    p_mean = sum(prices, Fraction(0)) / n
    s_tp = sum((Fraction(i) - t_mean) * (p - p_mean) for i, p in enumerate(prices))
    s_tt = sum((Fraction(i) - t_mean) ** 2 for i in range(n))
    s_pp = sum((p - p_mean) ** 2 for p in prices)
    return s_tp * s_tp / (s_tt * s_pp)


def expected_window(case, h: int) -> dict:
    """Erwartung für einen Zeitraum, nur aus der Methodenbeschreibung (unabhängig vom Rechenkern)."""
    letter, _, _, _, _, sessions, _, _, _ = case
    days, prices = series(case)
    valid = [(d, p) for d, p in zip(days, prices) if p is not None]
    # eigener Endtag: letzter gültiger Kurs, wenn seit ihm höchstens eine Börsensitzung vergangen ist
    last = max(d for d, _ in valid)
    missed = int(np.count_nonzero((sessions > last) & (sessions <= CUTOFF)))
    if last < CUTOFF and missed > 1:
        return {"status": "Kurs am Stichtag fehlt"}
    end = last
    target = end - h
    start = int(sessions[sessions <= target].max())  # letzte Sitzung am oder vor dem Ziel-Starttag
    expected_sessions = [int(s) for s in sessions.tolist() if start <= s <= end]
    obs = [(d, p) for d, p in valid if start <= d <= end]
    if not obs or obs[0][0] != start:
        return {"status": "Startkurs fehlt", "start": start}
    n_obs, n_exp = len(obs), len(expected_sessions)
    missing = n_exp - n_obs
    # höchstens 20 % fehlende Sitzungen; eine fehlende Sitzung ist immer erlaubt
    if missing > 1 and Fraction(n_obs, n_exp) < Fraction(4, 5):
        return {"status": "Sitzungsabdeckung zu gering", "start": start, "n": n_obs, "n_exp": n_exp}
    p = [q for _, q in obs]
    r = p[-1] / p[0] - 1
    out = {"status": "zugelassen", "start": start, "end": end, "n": n_obs, "n_exp": n_exp, "p0": p[0], "p1": p[-1], "r": r}
    out["r2"] = exact_r2(p) if n_obs >= 15 else None
    return out


def doubled_ranks(values: list[Fraction]) -> list[int]:
    """Doppelter Durchschnittsrang (aufsteigend), Gleichstand a…b → a + b."""
    order = sorted(range(len(values)), key=lambda k: values[k])
    ranks = [0] * len(values)
    k = 0
    while k < len(order):
        j = k
        while j + 1 < len(order) and values[order[j + 1]] == values[order[k]]:
            j += 1
        for m in order[k : j + 1]:
            ranks[m] = (k + 1) + (j + 1)
        k = j + 1
    return ranks


def scores(windows: dict[str, dict], weight: int, *, exact: bool = False) -> dict[str, float | Fraction]:
    """Score = w/100 · G + (1 − w/100) · R auf U mit Perzentilen P = 100 · (Durchschnittsrang − 1) / (M − 1).

    Wie in docs/03_Methodik.md festgelegt in Gleitkommazahlen doppelter Genauigkeit und in genau dieser
    Operationsfolge (so rechnen auch die App und das Ausgangsmodell); ``exact=True`` rechnet dieselbe Formel mit Brüchen
    – nur, um rechnerisch gleiche Scores sichtbar zu machen."""
    v = [k for k in LETTERS if windows.get(k, {}).get("status") == "zugelassen"]
    u = [k for k in v if windows[k]["r2"] is not None and windows[k]["r"] > 0]
    m = len(u)
    g = doubled_ranks([windows[k]["r2"] for k in u])
    r = doubled_ranks([windows[k]["r"] for k in u])
    out: dict = {}
    for i, k in enumerate(u):
        if exact:
            pct_g, pct_r = (Fraction(100) * (Fraction(x, 2) - 1) / (m - 1) for x in (g[i], r[i]))
            out[k] = Fraction(weight, 100) * pct_g + Fraction(100 - weight, 100) * pct_r
        else:
            pct_g, pct_r = (100.0 * (x / 2.0 - 1.0) / (m - 1) for x in (g[i], r[i]))
            out[k] = pct_r if weight == 0 else pct_g if weight == 100 else (weight / 100) * pct_g + (1 - weight / 100) * pct_r
    return out


def expected_orders(windows: dict[str, dict], weight: int) -> list[str]:
    """Rangfolge nach docs/03_Methodik.md: 0/100 = Rendite auf V; sonst Score auf U, Gleichstand (gleicher Score) →
    höhere Rendite → kleinere ISIN."""
    v = [k for k in LETTERS if windows.get(k, {}).get("status") == "zugelassen"]
    if weight == 0:
        return sorted(v, key=lambda k: (-windows[k]["r"], IDX[k]))
    score = scores(windows, weight)
    if weight == 100:  # nur Gleichmäßigkeit: nach R² selbst (gleiche Reihenfolge wie das R²-Perzentil)
        return sorted(score, key=lambda k: (-windows[k]["r2"], -windows[k]["r"], IDX[k]))
    return sorted(score, key=lambda k: (-score[k], -float(windows[k]["r"]), IDX[k]))


class MissingDaysReference(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.instruments = [instrument(k + 1, case) for k, case in enumerate(CASES)]
        cls.comp = compute_snapshot(cls.instruments, CUTOFF, CFG, workers=1)
        cls.col = {h: k for k, h in enumerate(cls.comp.windows)}

    def window(self, letter: str, h: int) -> dict:
        i, c = IDX[letter], self.col[h]
        st = int(self.comp.status[i, c])
        return {
            "code": st,
            "start": int(self.comp.start_day[i, c]),
            "n": int(self.comp.n_obs[i, c]),
            "n_exp": int(self.comp.n_exp[i, c]),
            "r": float(self.comp.r[i, c]),
            "r2": float(self.comp.r2[i, c]),
        }

    def assert_case(self, letter: str, h: int) -> dict:
        exp = expected_window(CASES[IDX[letter]], h)
        got = self.window(letter, h)
        status_code = {
            "zugelassen": None,
            "Kurs am Stichtag fehlt": Status.KURS_AM_STICHTAG_FEHLT,
            "Startkurs fehlt": Status.STARTKURS_FEHLT,
            "Sitzungsabdeckung zu gering": Status.SITZUNGSABDECKUNG_ZU_GERING,
        }[exp["status"]]
        if status_code is None:
            self.assertIn(got["code"], V_CODES, f"{letter} h={h}: Rendite veröffentlicht")
            self.assertEqual((got["start"], got["n"], got["n_exp"]), (exp["start"], exp["n"], exp["n_exp"]), f"{letter} h={h}")
            self.assertAlmostEqual(got["r"], float(exp["r"]), places=13, msg=f"{letter} h={h}: Rendite (exakter Bruch)")
            if exp["r2"] is not None:
                self.assertAlmostEqual(got["r2"], float(exp["r2"]), places=12, msg=f"{letter} h={h}: R²")
        else:
            self.assertEqual(got["code"], int(status_code), f"{letter} h={h}: {exp['status']}")
        return exp

    def test_every_case_matches_the_independent_expectation(self):
        for letter in LETTERS:
            for h in (1, 2, 3, 7, 25, 29, 30, 60, 90):
                with self.subTest(fall=letter, h=h):
                    self.assert_case(letter, h)

    def test_rules_by_case(self):
        # A: nichts fehlt
        self.assertEqual(self.window("A", 30)["n"], 23)
        # B: eine Sitzung ohne Kurs – zugelassen, 22 von 23 Kursen, Rendite aus Start- und Endkurs
        b = self.window("B", 30)
        self.assertEqual((b["n"], b["n_exp"]), (22, 23))
        self.assertAlmostEqual(b["r"], 0.132, places=12)
        # D: vier von 23 fehlen (17 %) – zugelassen; im 25-Tage-Zeitraum vier von 20 (genau 20 %) – noch zugelassen
        self.assertEqual((self.window("D", 30)["n"], self.window("D", 30)["n_exp"]), (19, 23))
        self.assertEqual((self.window("D", 25)["n"], self.window("D", 25)["n_exp"]), (16, 20))
        self.assertIn(self.window("D", 25)["code"], V_CODES)
        # E: fünf von 23 (22 %) bzw. fünf von 20 (25 %) – ausgeschlossen; im 7-Tage-Zeitraum ohne Lücke – zugelassen
        self.assertEqual(self.window("E", 30)["code"], int(Status.SITZUNGSABDECKUNG_ZU_GERING))
        self.assertEqual(self.window("E", 25)["code"], int(Status.SITZUNGSABDECKUNG_ZU_GERING))
        self.assertIn(self.window("E", 7)["code"], V_CODES)
        # F: Starttag ohne Kurs – kein Ausweichen auf den Vortag; einen Tag kürzer (29 Tage) zugelassen
        self.assertEqual(self.window("F", 30)["code"], int(Status.STARTKURS_FEHLT))
        self.assertIn(self.window("F", 29)["code"], V_CODES)
        # G: Stichtag ohne Kurs, Vortag vorhanden – Zeiträume enden am 22.10., 30 Tage ab 22.09.
        g = self.window("G", 30)
        self.assertEqual(g["start"], oct(22, 9))
        self.assertAlmostEqual(g["r"], 0.143, places=12)
        # H: zwei Sitzungen ohne Kurs am Ende – die Aktie fehlt in allen Zeiträumen
        self.assertTrue(all(int(s) == int(Status.KURS_AM_STICHTAG_FEHLT) for s in self.comp.status[IDX["H"]]))
        # J: Feiertag ist keine fehlende Sitzung – 22 von 22
        self.assertEqual((self.window("J", 30)["n"], self.window("J", 30)["n_exp"]), (22, 22))
        # K: kurzer Zeitraum (3 Tage): 3 von 4 Kursen = 75 % – zugelassen, weil eine fehlende Sitzung immer erlaubt ist;
        # 2 Tage: Starttag 21.10. ohne Kurs – ausgeschlossen
        k3 = self.window("K", 3)
        self.assertEqual((k3["n"], k3["n_exp"]), (3, 4))
        self.assertIn(k3["code"], V_CODES)
        self.assertEqual(self.window("K", 2)["code"], int(Status.STARTKURS_FEHLT))

    def test_empty_row_counts_like_a_missing_row(self):
        """Leerzeile (Tag ohne Kurs und Umsatz) und fehlende Zeile ergeben dieselben Werte – die App zählt beides als
        fehlende Sitzung (das Ausgangsmodell verwirft bei einer Leerzeile den Zeitraum, siehe docs/12)."""
        b_like = ("C", oct(23, 9), "100", "0.55", "0.25", WEEKDAYS, [oct(7)], [], "")
        twin = compute_snapshot([instrument(1, CASES[IDX["C"]]), instrument(2, b_like)], CUTOFF, CFG, workers=1)
        for name in ("status", "start_day", "n_obs", "n_exp", "r", "r2"):
            a, b = getattr(twin, name)[0], getattr(twin, name)[1]
            self.assertTrue(np.array_equal(a, b, equal_nan=True) if a.dtype.kind == "f" else np.array_equal(a, b), name)

    def test_gaps_are_not_filled(self):
        """R² rechnet mit den vorhandenen Kursen in ihrer Reihenfolge; ein aufgefüllter (interpolierter) Tag ergäbe einen
        anderen Wert."""
        days, prices = series(CASES[IDX["B"]])
        start = oct(23, 9)
        observed = [p for d, p in zip(days, prices) if d >= start]
        self.assertAlmostEqual(self.window("B", 30)["r2"], float(exact_r2(observed)), places=12)
        k = [d for d in days if d >= start].index(oct(8))  # Tag nach der Lücke
        filled = observed[:k] + [(observed[k - 1] + observed[k]) / 2] + observed[k:]
        self.assertNotAlmostEqual(float(exact_r2(filled)), self.window("B", 30)["r2"], places=6)

    def test_rankings_match_the_independent_order(self):
        for h in (3, 7, 25, 30):
            windows = {letter: expected_window(case, h) for letter, case in zip(LETTERS, CASES)}
            ranking = self.comp.rankings[h]
            for weight in (0, 40, 50, 60, 100):
                with self.subTest(h=h, w=weight):
                    got = ranking.native0.order if weight == 0 else ranking.trend[weight].order
                    self.assertEqual([LETTERS[int(i)] for i in got], expected_orders(windows, weight))

    def test_mathematically_equal_scores_follow_the_floating_point_value(self):
        """Rechnerisch gleiche Scores (25 Tage, 50/50: A, D und J je 300/7 = 42,857…) unterscheiden sich als
        Gleitkommazahl in der letzten Binärstelle. Die Reihenfolge folgt diesem Wert – so rechnen der Server, die App und
        das Ausgangsmodell (Prüffall 13.10.: mit Gleitkomma 1.272 von 1.278 gemischten Ranglisten gleich, mit exaktem
        Vergleich keine) – und nicht der höheren Rendite. Siehe docs/12_Fehlende_Kurstage.md, Abschnitt „Gleichstand“."""
        windows = {letter: expected_window(case, 25) for letter, case in zip(LETTERS, CASES)}
        exact = scores(windows, 50, exact=True)
        self.assertEqual({exact["A"], exact["D"], exact["J"]}, {Fraction(300, 7)})
        floating = scores(windows, 50)
        self.assertEqual(floating["A"], floating["J"])
        self.assertLess(floating["D"], floating["A"])  # eine Binärstelle kleiner
        got = [LETTERS[int(i)] for i in self.comp.rankings[25].trend[50].order]
        self.assertEqual([k for k in got if k in ("A", "D", "J")], ["A", "J", "D"])  # nach Rendite wäre es D, A, J
        self.assertGreater(windows["D"]["r"], windows["A"]["r"])
        self.assertGreater(windows["A"]["r"], windows["J"]["r"])

    def test_influence_on_the_30_day_rankings(self):
        """Einfluss fehlender Kurstage: dieselben Daten nach der Regel der App und nach strengeren Regeln."""
        windows = {letter: expected_window(case, 30) for letter, case in zip(LETTERS, CASES)}
        app = expected_orders(windows, 0)
        self.assertEqual(app, ["D", "G", "B", "C", "A", "J", "K"])
        self.assertEqual(expected_orders(windows, 60), [LETTERS[int(i)] for i in self.comp.rankings[30].trend[60].order])
        # streng: jeder fehlende Kurstag schließt den Zeitraum aus (B, C, D, K fallen weg) – Platz 1 wechselt von D zu G
        strict = {k: (w if w.get("n") == w.get("n_exp") else {"status": "ausgeschlossen"}) for k, w in windows.items()}
        self.assertEqual(expected_orders(strict, 0), ["G", "A", "J"])
        # wie das Ausgangsmodell: nur die Leerzeile (C) verwirft den Zeitraum – Platz 1 bleibt, A, J und K rücken auf
        model = {k: (w if k != "C" else {"status": "ausgeschlossen"}) for k, w in windows.items()}
        self.assertEqual(expected_orders(model, 0), ["D", "G", "B", "A", "J", "K"])
        # ohne letzten Schlusskurs (Regel bis tr-methode-1.8.0): G fehlt – B rückt auf Platz 2
        old = {k: (w if k != "G" else {"status": "ausgeschlossen"}) for k, w in windows.items()}
        self.assertEqual(expected_orders(old, 0), ["D", "B", "C", "A", "J", "K"])

    @unittest.skipUnless(os.environ.get("TR_REFERENZ_TABELLE"), "nur zum Erzeugen der Tabellen in docs/12")
    def test_print_tables(self):  # pragma: no cover - Hilfe für die Dokumentation
        for h in (30, 25, 7, 3, 2):
            print(f"\nh = {h}")
            for letter, case in zip(LETTERS, CASES):
                e = expected_window(case, h)
                if e["status"] != "zugelassen":
                    print(f"  {letter}: {e['status']} {e.get('n', '')}/{e.get('n_exp', '')}")
                    continue
                r2 = f"{float(e['r2']):.6f}" if e["r2"] is not None else "–"
                print(f"  {letter}: Start {dt.date.fromordinal(dt.date(1970, 1, 1).toordinal() + e['start'])} p0 {float(e['p0']):.4f} p1 {float(e['p1']):.4f} n {e['n']}/{e['n_exp']} r {float(e['r']) * 100:.4f} % R² {r2}")
        windows = {letter: expected_window(case, 30) for letter, case in zip(LETTERS, CASES)}
        for weight in (0, 40, 50, 60, 100):
            print(f"30 Tage, Gewichtung {weight}/{100 - weight}: {' > '.join(expected_orders(windows, weight))}")


if __name__ == "__main__":
    unittest.main()
