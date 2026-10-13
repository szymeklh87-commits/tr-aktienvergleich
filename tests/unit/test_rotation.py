"""Umschichtungs-Regel: Wochenwerte, Auswahl, Haltepuffer, Kosten, Steuern, Tagesvorschlag."""

from __future__ import annotations

import math
import unittest

import numpy as np

from traktien.analytics.rotation import (
    CostModel,
    Portfolio,
    RuleVariant,
    UniverseRule,
    WeeklyPanel,
    backtest,
    evaluate_week,
    is_rebalance_week,
    next_rebalance_day,
    preview,
)
from traktien.analytics.weekly import aggregate_weeks, friday_of, fridays, rolling_week_ends
from tests.helpers import day

RULE = UniverseRule()


def weekdays(first: int, last: int) -> np.ndarray:
    return np.array([d for d in range(first, last + 1) if (d + 3) % 7 < 5], dtype=np.int64)


class WeeklyTests(unittest.TestCase):
    def test_friday_of_week(self) -> None:
        self.assertEqual(friday_of(day(2026, 10, 12)), day(2026, 10, 16))  # Montag
        self.assertEqual(friday_of(day(2026, 10, 16)), day(2026, 10, 16))  # Freitag
        self.assertEqual(friday_of(day(2026, 10, 18)), day(2026, 10, 16))  # Sonntag
        self.assertEqual(fridays(day(2026, 10, 1), day(2026, 10, 31)).tolist(), [day(2026, 10, d) for d in (2, 9, 16, 23, 30)])
        self.assertEqual(rolling_week_ends(day(2026, 10, 13), 3).tolist(), [day(2026, 9, 29), day(2026, 10, 6), day(2026, 10, 13)])

    def test_aggregation_without_filling_gaps(self) -> None:
        sessions = weekdays(day(2026, 9, 28), day(2026, 10, 9))  # zwei Wochen
        holiday = day(2026, 10, 2)
        days = np.array([d for d in sessions if d != holiday])
        close = np.array([10.0, 11.0, 12.0, 11.0, 30.0, 31.0, 32.0, 33.0, 34.0])
        volume = np.array([100.0, np.nan, 0.0, 50.0, 10.0, 10.0, 10.0, 10.0, 10.0])
        agg = aggregate_weeks(days, close, volume, fridays(day(2026, 9, 28), day(2026, 10, 9)), sessions=sessions)
        self.assertEqual(agg.close.tolist(), [11.0, 34.0])  # Donnerstag (Freitag fehlt), dann Freitag
        self.assertEqual(agg.observed.tolist(), [4, 5])
        self.assertEqual(agg.sessions.tolist(), [5, 5])
        self.assertEqual(agg.with_data.tolist(), [3, 5])  # Volumen ohne Angabe zählt nicht
        self.assertEqual(agg.positive.tolist(), [2, 5])
        self.assertAlmostEqual(agg.turnover[0], 10 * 100 + 12 * 0 + 11 * 50)
        self.assertAlmostEqual(agg.jump[1], math.log(30 / 11))  # Sprung über das Wochenende zählt zur neuen Woche
        self.assertEqual(agg.first_close.tolist(), [10.0, 30.0])  # erste Sitzung mit Kurs (Ausführungskurs)
        self.assertEqual(agg.first_day.tolist(), [day(2026, 9, 28), day(2026, 10, 5)])
        tail = agg.select(slice(1, None))
        self.assertEqual((tail.week_ends.tolist(), tail.first_close.tolist()), ([day(2026, 10, 9)], [30.0]))
        empty_week = aggregate_weeks(days, close, volume, np.array([day(2026, 10, 16)]), sessions=sessions)
        self.assertTrue(math.isnan(empty_week.close[0]))
        self.assertTrue(math.isnan(empty_week.first_close[0]))
        self.assertEqual(int(empty_week.first_day[0]), -1)


def make_panel(
    closes: dict[str, list[float]], *, first_friday: int = day(2026, 1, 2), turnover_usd: float = 50e6, unit_usd: float = 1.1, monday_close: bool = True
) -> WeeklyPanel:
    """Wochenwerte; ``monday_close``: der erste Schlusskurs einer Woche (Montag) gleicht dem Freitagsschluss davor."""
    isins = sorted(closes)
    n, w = len(isins), len(next(iter(closes.values())))
    close = np.array([closes[i] for i in isins], dtype=float)
    per_session = turnover_usd / unit_usd
    week_ends = np.arange(first_friday, first_friday + 7 * w, 7, dtype=np.int64)
    first_close = np.full((n, w), np.nan)
    first_close[:, 1:] = close[:, :-1]
    first_day = np.tile(week_ends - 4, (n, 1))
    first_day[:, 0] = -1
    return WeeklyPanel(
        idx=np.arange(n),
        week_ends=week_ends,
        close=close,
        turnover=np.full((n, w), per_session * 5),
        with_data=np.full((n, w), 5, dtype=np.int32),
        positive=np.full((n, w), 5, dtype=np.int32),
        observed=np.full((n, w), 5, dtype=np.int32),
        sessions=np.full((n, w), 5, dtype=np.int32),
        jump=np.zeros((n, w)),
        unit_eur=np.ones((n, w)),
        unit_usd=np.full((n, w), unit_usd),
        isins=isins,
        first_close=first_close if monday_close else None,
        first_day=first_day if monday_close else None,
    )


def growth(rate: float, weeks: int, start: float = 100.0) -> list[float]:
    return [start * (1 + rate) ** k for k in range(weeks)]


class SelectionTests(unittest.TestCase):
    def test_ranking_liquidity_coverage_and_jumps(self) -> None:
        panel = make_panel({"A": growth(0.03, 20), "B": growth(0.02, 20), "C": growth(0.05, 20), "D": growth(0.04, 20), "E": growth(0.01, 20)})
        snap = evaluate_week(panel, 19, 13, RULE)
        self.assertEqual([panel.isins[r] for r in snap.order], ["C", "D", "A", "B", "E"])
        self.assertAlmostEqual(snap.signal[2], 1.05**13 - 1)
        self.assertAlmostEqual(snap.usd[0], 50e6)
        # C: zu wenig Umsatz; D: an einer Sitzung nur jeder zweite Tag mit Umsatz; A: Tagessprung > Faktor 3; B: Kurse fehlen
        panel.turnover[2, :] = 9e6 / 1.1 * 5
        panel.positive[3, 16:20] = 3
        panel.jump[0, 10] = math.log(3.5)
        panel.observed[1, 8:12] = 3
        snap = evaluate_week(panel, 19, 13, RULE)
        self.assertEqual([panel.isins[r] for r in snap.order], ["E"])
        self.assertTrue(math.isnan(snap.usd[2]) is False and snap.usd[2] < 10e6)

    def test_first_friday_of_month_and_next_date(self) -> None:
        self.assertTrue(is_rebalance_week(day(2026, 11, 6), "monatlich"))
        self.assertFalse(is_rebalance_week(day(2026, 10, 9), "monatlich"))
        self.assertEqual(next_rebalance_day(day(2026, 10, 12), "monatlich"), day(2026, 11, 6))
        self.assertEqual(next_rebalance_day(day(2026, 11, 6), "monatlich"), day(2026, 11, 6))
        self.assertEqual(next_rebalance_day(day(2026, 10, 12), "woechentlich"), day(2026, 10, 16))


class BacktestTests(unittest.TestCase):
    def test_holds_the_best_and_keeps_within_buffer(self) -> None:
        weeks = 40
        b = growth(0.04, 22) + [growth(0.04, 22)[-1] * 0.995**k for k in range(1, weeks - 21)]  # B schwächt ab
        panel = make_panel(
            {"A": growth(0.05, weeks), "B": b, "C": growth(0.03, weeks), "D": growth(0.02, weeks), "E": growth(0.01, weeks), "F": growth(0.0, weeks)}
        )
        variant = RuleVariant(holdings=2, lookback_weeks=4)
        result = backtest(panel, variant, CostModel(), RULE)
        self.assertEqual(result.status, "ok")
        first = result.rebalance_days[0]
        self.assertEqual(first, int(panel.week_ends[result.start]))
        self.assertTrue(is_rebalance_week(first, "monatlich"))
        bought = [panel.isins[t.row] for t in result.trades if t.day == first]
        self.assertEqual(sorted(bought), ["A", "B"])
        # Entscheidung am Freitag, Ausführung am Montag danach zum ersten Schlusskurs der Woche
        self.assertTrue(all(t.exec_day == t.day + 3 for t in result.trades))
        self.assertEqual(result.days[0], first)
        self.assertAlmostEqual(result.equity[0], 10_000.0)  # am Entscheidungstag noch alles Bargeld
        # B fällt zurück: erst innerhalb des Puffers (Platz ≤ 4) gehalten, dann verkauft und durch C ersetzt
        sells = [t for t in result.trades if t.action == "verkauf"]
        self.assertTrue(sells and panel.isins[sells[0].row] == "B")
        self.assertGreater(sells[0].rank or 99, 4)
        self.assertIn("C", [panel.isins[t.row] for t in result.trades if t.action == "kauf" and t.day == sells[0].day])
        stats = result.stats()
        self.assertGreater(stats["endwert_ohne_kosten"], stats["endwert"])
        self.assertEqual(stats["orders"], len(result.trades))
        self.assertAlmostEqual(stats["gebuehren"], 1.0 * len(result.trades))

    def test_benchmark_is_equal_weighted_universe_without_costs(self) -> None:
        panel = make_panel({"A": growth(0.02, 30), "B": growth(0.01, 30), "C": growth(-0.01, 30)})
        result = backtest(panel, RuleVariant(holdings=1, lookback_weeks=4, rhythm="woechentlich"), CostModel(), RULE)
        t0 = result.start
        # wöchentlich neu gleich gewichtet: Wochenrendite = Mittel der drei Wochenrenditen
        expected = 10_000.0
        for t in range(t0 + 1, panel.w):
            expected *= 1 + np.mean([0.02, 0.01, -0.01])
        self.assertAlmostEqual(result.benchmark[-1], expected, places=6)

    def test_trades_at_first_close_of_next_week_not_at_the_signal_close(self) -> None:
        weeks = 20
        panel = make_panel({"A": growth(0.05, weeks), "B": growth(0.0, weeks)})
        t0 = None
        result = backtest(panel, RuleVariant(holdings=1, lookback_weeks=4, rhythm="woechentlich"), CostModel.free(), RULE)
        t0 = result.start
        panel.first_close[0, t0 + 1] = panel.close[0, t0] * 1.10  # Montag nach der Entscheidung 10 % höher
        result = backtest(panel, RuleVariant(holdings=1, lookback_weeks=4, rhythm="woechentlich"), CostModel.free(), RULE)
        buy = result.trades[0]
        self.assertEqual((buy.action, panel.isins[buy.row]), ("kauf", "A"))
        self.assertEqual(buy.exec_day, int(panel.week_ends[t0 + 1]) - 4)
        self.assertAlmostEqual(buy.value / 10_000.0, 1.0)
        shares = 10_000.0 / (panel.close[0, t0] * 1.10)
        self.assertAlmostEqual(result.equity[1], shares * panel.close[0, t0 + 1])  # Bewertung zum Freitagsschluss
        # ohne ersten Wochenkurs: Wochenschluss als Ausführungskurs
        no_monday = make_panel({"A": growth(0.05, weeks), "B": growth(0.0, weeks)}, monday_close=False)
        late = backtest(no_monday, RuleVariant(holdings=1, lookback_weeks=4, rhythm="woechentlich"), CostModel.free(), RULE)
        self.assertEqual(late.trades[0].exec_day, int(no_monday.week_ends[late.start + 1]))

    def test_decision_on_the_last_friday_stays_pending(self) -> None:
        # Raster endet am ersten Freitag im Monat (2026-02-06): beschlossen, aber noch nicht ausgeführt
        weeks = 6
        panel = make_panel({"A": growth(0.05, weeks), "B": growth(0.0, weeks)}, first_friday=day(2026, 1, 2))
        self.assertEqual(int(panel.week_ends[-1]), day(2026, 2, 6))
        result = backtest(panel, RuleVariant(holdings=1, lookback_weeks=4), CostModel(), RULE)
        self.assertEqual(result.pending_day, day(2026, 2, 6))
        self.assertEqual(result.trades, [])
        self.assertEqual(result.rebalance_days, [])
        now = make_panel({k: v for k, v in zip(panel.isins, panel.close.tolist())}, first_friday=day(2026, 1, 5))  # Stichtag Montag 9.2.
        shown = preview(now, result, RuleVariant(holdings=1, lookback_weeks=4), RULE, day(2026, 2, 9))
        self.assertEqual(shown.decision_day, day(2026, 2, 6))
        self.assertEqual(shown.next_decision_day, day(2026, 3, 6))
        self.assertEqual([(a["action"], panel.isins[a["row"]]) for a in shown.actions], [("kauf", "A")])

    def test_too_little_history(self) -> None:
        panel = make_panel({"A": growth(0.01, 10)})
        self.assertEqual(backtest(panel, RuleVariant(), CostModel(), RULE).status, "zu_wenig_historie")


class CostAndTaxTests(unittest.TestCase):
    def test_fee_and_spread_on_buy_and_sell(self) -> None:
        p = Portfolio(10_000.0, CostModel(fee=1.0, spread=0.001, tax_rate=0.0, allowance=0.0))
        p.new_year(2026)
        buy = p.buy(0, 5_000.0, 100.0, 0, {})
        self.assertAlmostEqual(p.positions[0].shares, 4_999.0 / 100.1)
        self.assertAlmostEqual(buy.fee + buy.spread + buy.value, 5_000.0)
        sell = p.sell(0, 1.0, 100.0, 1, {})
        self.assertAlmostEqual(sell.value, 4_999.0 / 100.1 * 100.0)
        self.assertAlmostEqual(p.cash, 5_000.0 + sell.value * 0.999 - 1.0)
        self.assertEqual(p.orders, 2)

    def test_tax_with_allowance_loss_refund_and_carry(self) -> None:
        costs = CostModel(fee=0.0, spread=0.0, tax_rate=0.26375, allowance=1000.0)
        p = Portfolio(100_000.0, costs)
        p.new_year(2026)
        p.buy(0, 10_000.0, 100.0, 0, {})
        trade = p.sell(0, 1.0, 130.0, 1, {})  # +3.000 Gewinn
        self.assertAlmostEqual(trade.gain, 3_000.0)
        self.assertAlmostEqual(trade.tax, 0.26375 * 2_000.0)
        p.buy(1, 10_000.0, 100.0, 2, {})
        refund = p.sell(1, 1.0, 95.0, 3, {})  # −500 im selben Jahr: Erstattung
        self.assertAlmostEqual(refund.tax, -0.26375 * 500.0)
        p.buy(2, 10_000.0, 100.0, 4, {})
        # −3.000: 1.500 erstattet (Rest der versteuerten Gewinne), 1.000 Pauschbetrag wieder frei, 500 in den Verlusttopf
        p.sell(2, 1.0, 70.0, 5, {})
        self.assertAlmostEqual(p.tax.loss_pot, 500.0)  # Jahresergebnis 3.000 − 500 − 3.000 = −500
        self.assertAlmostEqual(p.tax.allowance_left, 1_000.0)
        self.assertAlmostEqual(p.taxes, 0.0)
        p.new_year(2027)  # Pauschbetrag neu, Verlusttopf bleibt
        p.buy(3, 10_000.0, 100.0, 6, {})
        later = p.sell(3, 1.0, 130.0, 7, {})  # +3.000: 500 Verlusttopf, 1.000 Pauschbetrag, 1.500 steuerpflichtig
        self.assertAlmostEqual(later.tax, 0.26375 * 1_500.0)
        self.assertAlmostEqual(p.tax.loss_pot, 0.0)
        # Verlust nach verbrauchtem Pauschbetrag ohne versteuerte Gewinne: Pauschbetrag wird frei
        q = Portfolio(100_000.0, costs)
        q.new_year(2026)
        q.buy(0, 10_000.0, 100.0, 0, {})
        q.sell(0, 1.0, 108.0, 1, {})  # +800: Pauschbetrag 200 übrig, keine Steuer
        q.buy(1, 10_000.0, 100.0, 2, {})
        q.sell(1, 1.0, 95.0, 3, {})  # −500: 500 Pauschbetrag frei (zusammen wieder 700), nichts im Verlusttopf
        self.assertAlmostEqual(q.tax.allowance_left, 700.0)
        self.assertAlmostEqual(q.tax.loss_pot, 0.0)


class PreviewTests(unittest.TestCase):
    def test_preview_names_sells_and_buys_when_a_new_stock_overtakes(self) -> None:
        weeks = 30
        panel = make_panel({"A": growth(0.05, weeks), "B": growth(0.04, weeks), "C": growth(0.0, weeks), "D": growth(0.0, weeks), "E": growth(0.0, weeks), "F": growth(0.0, weeks)})
        variant = RuleVariant(holdings=2, lookback_weeks=4)
        result = backtest(panel, variant, CostModel(), RULE)
        self.assertEqual(sorted(panel.isins[r] for r in result.portfolio.positions), ["A", "B"])
        today = int(panel.week_ends[-1]) + 3  # Montag nach dem letzten Freitag
        now = make_panel({k: v for k, v in zip(panel.isins, panel.close.tolist())}, first_friday=today - 7 * (weeks - 1))
        quiet = preview(now, result, variant, RULE, today)
        self.assertEqual(quiet.actions, [])
        self.assertEqual(quiet.next_decision_day, next_rebalance_day(today, "monatlich"))
        self.assertIsNone(quiet.decision_day)
        self.assertAlmostEqual(sum(h["weight"] for h in quiet.holdings) + quiet.cash / quiet.value, 1.0)
        # D, E, F steigen in den letzten 4 Wochen stark: A bleibt (Platz 4 ≤ Puffer 4), B fällt heraus (Platz 5)
        for row in (3, 4, 5):
            now.close[row, -4:] = now.close[row, -5] * np.array([1.3, 1.6, 1.9, 2.2 + 0.01 * row])
        moved = preview(now, result, variant, RULE, today)
        sells = [a for a in moved.actions if a["action"] == "verkauf"]
        buys = [a for a in moved.actions if a["action"] == "kauf"]
        self.assertEqual([panel.isins[a["row"]] for a in sells], ["B"])
        self.assertEqual(sells[0]["reason"], "platz_ausserhalb_puffer")
        self.assertEqual(sells[0]["rank"], 5)
        self.assertEqual([panel.isins[a["row"]] for a in buys], ["F"])
        self.assertEqual(moved.ranking[0]["rank"], 1)


if __name__ == "__main__":
    unittest.main()
