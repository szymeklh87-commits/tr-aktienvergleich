"""Umschichtungs-Regel (``rotation-v1``): Rückblick-Test und Tagesvorschlag.

Eine feste, mechanische Regel – keine Anlageberatung und keine Prognose:

1. **Kandidaten** an einem Prüftag (Wochenende): Aktien mit Ø Tagesumsatz der letzten 4 Wochen
   von mindestens 10 Mio. USD (mindestens 80 % der Sitzungen mit Umsatz), Kursen an mindestens
   90 % der Sitzungen im Trendzeitraum und ohne Tagessprung über Faktor 3 (Datenfehler-Verdacht).
2. **Trend** = Kursrendite über 13 Wochen (91 Tage) bzw. 4 Wochen (28 Tage) in Notierungswährung.
   Rangfolge absteigend, bei Gleichstand nach ISIN.
3. **Umschichten** am ersten Freitag jedes Monats (oder jeden Freitag): Eine gehaltene Aktie
   bleibt, solange sie unter den ersten 2 × N Plätzen liegt (Haltepuffer gegen ständiges Tauschen);
   sonst wird sie verkauft. Freie Plätze bekommen die bestplatzierten nicht gehaltenen Aktien. Neue
   Positionen erhalten 1/N des Depotwerts; gehaltene werden nur angeglichen, wenn ihr Anteil um
   mehr als 5 Prozentpunkte von 1/N abweicht.
4. **Kosten**: je Order 1 € Fremdkosten und 0,1 % Kursabschlag (Spanne), Abgeltungsteuer mit
   Solidaritätszuschlag (26,375 %) auf realisierte Gewinne nach Verlusttopf und Sparerpauschbetrag
   (1.000 € je Kalenderjahr) – wie bei der Bank beim Verkauf einbehalten. Ein Verlust erstattet
   zuerst Steuer auf Gewinne desselben Jahres, gibt dann verbrauchten Pauschbetrag frei und geht
   im Übrigen in den Verlusttopf (Vortrag ins nächste Jahr).

Entschieden wird mit den Schlusskursen des Prüftags (Freitag), gehandelt zum Schlusskurs des nächsten
Handelstags der jeweiligen Börse (erste Sitzung der Folgewoche) – so, wie man die Entscheidung
frühestens umsetzen kann. Bewertet wird in Euro (EZB-Referenzkurse) zu den Freitagsschlusskursen.
Gehandelt wird mit Bruchteilen von Aktien; Dividenden sind nicht enthalten (Kursrendite).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from .weekly import friday_of

VERSION = "rotation-v1"


@dataclass(frozen=True)
class RuleVariant:
    holdings: int = 5
    rhythm: str = "monatlich"  # "monatlich" = erster Freitag im Monat, "woechentlich" = jeder Freitag
    lookback_weeks: int = 13
    capital: float = 10_000.0
    keep_rank_factor: int = 2
    band: float = 0.05

    @property
    def key(self) -> str:
        return f"n{self.holdings}-{self.rhythm}-w{self.lookback_weeks}-k{int(self.capital)}"


@dataclass(frozen=True)
class CostModel:
    fee: float = 1.0
    spread: float = 0.001
    tax_rate: float = 0.26375
    allowance: float = 1000.0

    @staticmethod
    def free() -> "CostModel":
        return CostModel(fee=0.0, spread=0.0, tax_rate=0.0, allowance=0.0)


@dataclass(frozen=True)
class UniverseRule:
    min_turnover_usd: float = 10_000_000.0
    turnover_weeks: int = 4
    min_positive_share: float = 0.8
    min_coverage: float = 0.9
    max_jump: float = math.log(3.0)


@dataclass
class WeeklyPanel:
    """Wochenwerte aller Kandidaten auf einem gemeinsamen Raster (Zeile = Aktie, Spalte = Woche)."""

    idx: np.ndarray  # Instrumentindex im Datenstand
    week_ends: np.ndarray
    close: np.ndarray
    turnover: np.ndarray
    with_data: np.ndarray
    positive: np.ndarray
    observed: np.ndarray
    sessions: np.ndarray
    jump: np.ndarray
    unit_eur: np.ndarray  # EUR je Kurseinheit an diesem Wochenende (NaN = Wechselkurs fehlt)
    unit_usd: np.ndarray  # USD je Kurseinheit
    isins: list[str] = field(default_factory=list)
    first_close: np.ndarray | None = None  # Schlusskurs der ersten Sitzung der Woche (Ausführungskurs)
    first_day: np.ndarray | None = None  # Tag dieser Sitzung (−1 = keine)

    @property
    def n(self) -> int:
        return int(self.close.shape[0])

    @property
    def w(self) -> int:
        return int(self.close.shape[1])


@dataclass
class Snapshot:
    """Bewertung und Rangfolge einer Prüfwoche."""

    signal: np.ndarray  # Kursrendite im Trendzeitraum (NaN = nicht berechenbar)
    eligible: np.ndarray  # bool
    usd: np.ndarray  # Ø Tagesumsatz in USD (NaN = nicht bestimmbar)
    order: np.ndarray  # Zeilen der Kandidaten in Rangfolge

    def rank_of(self) -> dict[int, int]:
        return {int(row): k + 1 for k, row in enumerate(self.order.tolist())}


def evaluate_week(panel: WeeklyPanel, t: int, lookback: int, rule: UniverseRule) -> Snapshot:
    """Kandidaten, Trend und Rangfolge in der Woche ``t``."""
    n = panel.n
    signal = np.full(n, np.nan)
    usd = np.full(n, np.nan)
    eligible = np.zeros(n, dtype=bool)
    if t < lookback or t < rule.turnover_weeks - 1:
        return Snapshot(signal, eligible, usd, np.empty(0, dtype=np.int64))
    c_now = panel.close[:, t]
    c_then = panel.close[:, t - lookback]
    ok = np.isfinite(c_now) & np.isfinite(c_then) & (c_now > 0) & (c_then > 0)
    signal[ok] = c_now[ok] / c_then[ok] - 1.0
    window = slice(t - lookback + 1, t + 1)
    sessions = panel.sessions[:, window].sum(axis=1)
    observed = panel.observed[:, window].sum(axis=1)
    coverage_ok = (sessions > 0) & (observed >= rule.min_coverage * sessions)
    jump_ok = panel.jump[:, window].max(axis=1) <= rule.max_jump
    recent = slice(t - rule.turnover_weeks + 1, t + 1)
    turnover = panel.turnover[:, recent].sum(axis=1)
    with_data = panel.with_data[:, recent].sum(axis=1)
    positive = panel.positive[:, recent].sum(axis=1)
    recent_sessions = panel.sessions[:, recent].sum(axis=1)
    has = (with_data > 0) & np.isfinite(panel.unit_usd[:, t])
    usd[has] = turnover[has] / with_data[has] * panel.unit_usd[has, t]
    liquid = has & (usd >= rule.min_turnover_usd) & (positive >= rule.min_positive_share * np.maximum(recent_sessions, 1))
    priced = np.isfinite(panel.unit_eur[:, t])
    eligible = ok & coverage_ok & jump_ok & liquid & priced
    rows = np.flatnonzero(eligible)
    keys = np.array([panel.isins[r] for r in rows]) if panel.isins else rows.astype(str)
    order = rows[np.lexsort((keys, -signal[rows]))] if len(rows) else rows
    return Snapshot(signal, eligible, usd, order.astype(np.int64))


def is_rebalance_week(week_end: int, rhythm: str) -> bool:
    if rhythm == "woechentlich":
        return True
    import datetime as dt

    day = dt.date(1970, 1, 1) + dt.timedelta(days=int(week_end))
    return day.day <= 7  # erster Freitag im Monat


def next_rebalance_day(after_or_on: int, rhythm: str) -> int:
    friday = friday_of(after_or_on)
    if friday < after_or_on:
        friday += 7
    while not is_rebalance_week(friday, rhythm):
        friday += 7
    return friday


@dataclass
class Position:
    shares: float
    basis: float  # Anschaffungskosten in EUR (einschließlich Kosten)
    entry_day: int


@dataclass
class Trade:
    day: int
    row: int
    action: str  # kauf, verkauf, aufstocken, reduzieren
    value: float  # Handelswert in EUR (vor Kosten)
    weight_before: float
    weight_after: float
    rank: int | None
    signal: float | None
    fee: float
    spread: float
    tax: float  # einbehaltene Steuer (negativ = Erstattung)
    gain: float | None = None  # realisierter Gewinn/Verlust bei Verkäufen
    exec_day: int | None = None  # Handelstag der Ausführung (``day`` = Prüftag der Entscheidung)


@dataclass
class TaxState:
    allowance_left: float
    loss_pot: float = 0.0
    taxed_gains_year: float = 0.0
    year: int | None = None


class Portfolio:
    """Depot der Regel: Bruchteile, Kosten und Steuern wie oben beschrieben."""

    def __init__(self, capital: float, costs: CostModel) -> None:
        self.cash = float(capital)
        self.positions: dict[int, Position] = {}
        self.costs = costs
        self.tax = TaxState(allowance_left=costs.allowance)
        self.fees = 0.0
        self.spread_costs = 0.0
        self.taxes = 0.0
        self.orders = 0

    def value(self, prices: np.ndarray) -> float:
        return self.cash + sum(p.shares * prices[row] for row, p in self.positions.items())

    def new_year(self, year: int) -> None:
        if self.tax.year != year:
            self.tax.year = year
            self.tax.allowance_left = self.costs.allowance
            self.tax.taxed_gains_year = 0.0

    def _tax_on(self, gain: float) -> float:
        """Einbehalt (positiv) oder Erstattung (negativ) für einen realisierten Gewinn/Verlust."""
        rate = self.costs.tax_rate
        if rate <= 0:
            return 0.0
        state = self.tax
        if gain >= 0:
            used = min(gain, state.loss_pot)
            state.loss_pot -= used
            rest = gain - used
            free = min(rest, state.allowance_left)
            state.allowance_left -= free
            rest -= free
            state.taxed_gains_year += rest
            return rate * rest
        # Verlust: wie die Bank – erst Steuer auf Gewinne dieses Jahres erstatten, dann den in diesem
        # Jahr verbrauchten Sparerpauschbetrag wieder freigeben, der Rest geht in den Verlusttopf
        loss = -gain
        refundable = min(loss, state.taxed_gains_year)
        state.taxed_gains_year -= refundable
        rest = loss - refundable
        restore = min(rest, self.costs.allowance - state.allowance_left)
        state.allowance_left += restore
        state.loss_pot += rest - restore
        return -rate * refundable

    def sell(self, row: int, fraction: float, price: float, day: int, meta: dict) -> Trade | None:
        position = self.positions.get(row)
        if position is None or fraction <= 0 or not math.isfinite(price) or price <= 0:
            return None
        fraction = min(1.0, fraction)
        shares = position.shares * fraction
        value = shares * price
        spread = value * self.costs.spread
        fee = self.costs.fee
        proceeds = value - spread - fee
        basis = position.basis * fraction
        gain = proceeds - basis
        tax = self._tax_on(gain)
        self.cash += proceeds - tax
        self.fees += fee
        self.spread_costs += spread
        self.taxes += tax
        self.orders += 1
        if fraction >= 1.0 - 1e-12:
            del self.positions[row]
        else:
            position.shares -= shares
            position.basis -= basis
        return Trade(day, row, meta.get("action", "verkauf"), value, meta.get("w0", 0.0), meta.get("w1", 0.0), meta.get("rank"), meta.get("signal"), fee, spread, tax, gain, meta.get("exec_day"))

    def buy(self, row: int, amount: float, price: float, day: int, meta: dict) -> Trade | None:
        """Kauft für ``amount`` EUR einschließlich Kosten."""
        amount = min(amount, self.cash)
        fee = self.costs.fee
        if amount <= fee or not math.isfinite(price) or price <= 0:
            return None
        invest = amount - fee
        shares = invest / (price * (1.0 + self.costs.spread))
        value = shares * price
        spread = invest - value
        self.cash -= amount
        self.fees += fee
        self.spread_costs += spread
        self.orders += 1
        position = self.positions.get(row)
        if position is None:
            self.positions[row] = Position(shares, amount, day)
        else:
            position.shares += shares
            position.basis += amount
        return Trade(day, row, meta.get("action", "kauf"), value, meta.get("w0", 0.0), meta.get("w1", 0.0), meta.get("rank"), meta.get("signal"), fee, spread, 0.0, None, meta.get("exec_day"))


def rebalance(portfolio: Portfolio, snap: Snapshot, prices: np.ndarray, variant: RuleVariant, day: int, exec_days: np.ndarray | None = None) -> list[Trade]:
    """Eine Umschichtung nach der Regel; gibt die Orders zurück.

    ``snap`` ist die Bewertung am Prüftag ``day``; ``prices`` sind die Ausführungskurse in EUR,
    ``exec_days`` die Handelstage der Ausführung je Zeile (für die Anzeige).
    """
    trades: list[Trade] = []
    ranks = snap.rank_of()

    def when(row: int) -> int | None:
        return int(exec_days[row]) if exec_days is not None else None

    n = variant.holdings
    buffer = n * variant.keep_rank_factor
    total_before = portfolio.value(prices)
    weight = {row: (p.shares * prices[row] / total_before if total_before > 0 else 0.0) for row, p in portfolio.positions.items()}
    keep = [row for row in portfolio.positions if ranks.get(row, buffer + 1) <= buffer]
    sells = [row for row in portfolio.positions if row not in keep]
    for row in sorted(sells, key=lambda r: ranks.get(r, 10**9)):
        trade = portfolio.sell(row, 1.0, prices[row], day, {"action": "verkauf", "w0": weight[row], "w1": 0.0, "rank": ranks.get(row), "signal": _f(snap.signal[row]), "exec_day": when(row)})
        if trade:
            trades.append(trade)
    free_slots = n - len(keep)
    new = [int(row) for row in snap.order.tolist() if int(row) not in portfolio.positions][:free_slots]
    total = portfolio.value(prices)
    target = total / n if n else 0.0
    # gehaltene Positionen angleichen: erst verringern (bringt Geld), dann aufstocken
    increases: list[tuple[int, float]] = []
    for row in keep:
        position = portfolio.positions[row]
        current = position.shares * prices[row]
        share = current / total if total > 0 else 0.0
        if abs(share - 1.0 / n) <= variant.band:
            continue
        if current > target:
            trade = portfolio.sell(row, (current - target) / current, prices[row], day, {"action": "reduzieren", "w0": share, "w1": 1.0 / n, "rank": ranks.get(row), "signal": _f(snap.signal[row]), "exec_day": when(row)})
            if trade:
                trades.append(trade)
        else:
            increases.append((row, target - current))
    wanted = [(row, target, "kauf") for row in new] + [(row, amount, "aufstocken") for row, amount in increases]
    need = sum(amount for _, amount, _ in wanted)
    scale = min(1.0, portfolio.cash / need) if need > 0 else 0.0
    for row, amount, action in wanted:
        before = (portfolio.positions[row].shares * prices[row] / total) if row in portfolio.positions and total > 0 else 0.0
        trade = portfolio.buy(row, amount * scale, prices[row], day, {"action": action, "w0": before, "w1": 1.0 / n, "rank": ranks.get(row), "signal": _f(snap.signal[row]), "exec_day": when(row)})
        if trade:
            trades.append(trade)
    return trades


def _f(x) -> float | None:
    x = float(x)
    return x if math.isfinite(x) else None


@dataclass
class BacktestResult:
    variant: RuleVariant
    status: str  # ok | zu_wenig_historie
    start: int | None = None  # Spalte der ersten Umschichtung
    days: list[int] = field(default_factory=list)
    equity: list[float] = field(default_factory=list)
    equity_gross: list[float] = field(default_factory=list)
    benchmark: list[float] = field(default_factory=list)
    rebalance_days: list[int] = field(default_factory=list)
    trades: list[Trade] = field(default_factory=list)
    portfolio: Portfolio | None = None
    gross: Portfolio | None = None
    last_prices: np.ndarray | None = None
    pending: Snapshot | None = None  # am letzten Prüftag beschlossen, im Rückblick noch nicht ausgeführt
    pending_day: int | None = None

    def stats(self) -> dict:
        if self.status != "ok" or not self.equity:
            return {}
        capital = self.variant.capital
        span = self.days[-1] - self.days[0]

        def total(series: list[float]) -> float | None:
            return series[-1] / capital - 1.0 if series and capital > 0 else None

        def annual(series: list[float]) -> float | None:
            if span < 365 or not series or series[-1] <= 0:
                return None
            return (series[-1] / capital) ** (365.0 / span) - 1.0

        equity = np.array(self.equity)
        peak = np.maximum.accumulate(equity)
        drawdown = float(np.max(1.0 - equity / peak)) if len(equity) else 0.0
        p = self.portfolio
        return {
            "start_day": self.days[0],
            "end_day": self.days[-1],
            "tage": span,
            "startkapital": capital,
            "endwert": self.equity[-1],
            "endwert_ohne_kosten": self.equity_gross[-1] if self.equity_gross else None,
            "vergleich_endwert": self.benchmark[-1] if self.benchmark else None,
            "rendite": total(self.equity),
            "rendite_ohne_kosten": total(self.equity_gross),
            "vergleich_rendite": total(self.benchmark),
            "rendite_pro_jahr": annual(self.equity),
            "vergleich_pro_jahr": annual(self.benchmark),
            "max_rueckgang": drawdown,
            "umschichtungen": len(self.rebalance_days),
            "orders": p.orders if p else 0,
            "gebuehren": p.fees if p else 0.0,
            "spanne": p.spread_costs if p else 0.0,
            "steuern": p.taxes if p else 0.0,
            "verlusttopf": p.tax.loss_pot if p else 0.0,
        }


def _prices(panel: WeeklyPanel, t: int, last_close: np.ndarray, last_unit: np.ndarray) -> np.ndarray:
    """Bewertungskurse in EUR am Wochenende ``t``; fehlende Kurse bleiben auf dem letzten bekannten Wert."""
    close = panel.close[:, t]
    unit = panel.unit_eur[:, t]
    has_close = np.isfinite(close) & (close > 0)
    last_close[has_close] = close[has_close]
    has_unit = np.isfinite(unit) & (unit > 0)
    last_unit[has_unit] = unit[has_unit]
    return last_close * last_unit


def _exec_prices(panel: WeeklyPanel, t: int, last_close: np.ndarray, last_unit: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Ausführungskurse in EUR in der Woche ``t`` und die Handelstage: Schlusskurs der ersten Sitzung,
    ersatzweise der Wochenschluss, sonst der letzte bekannte Kurs (z. B. Handelsaussetzung)."""
    week_end = int(panel.week_ends[t])
    close = np.full(panel.n, np.nan)
    days = np.full(panel.n, week_end, dtype=np.int64)
    if panel.first_close is not None:
        first = panel.first_close[:, t]
        ok = np.isfinite(first) & (first > 0)
        close[ok] = first[ok]
        if panel.first_day is not None:
            first_day = panel.first_day[:, t]
            days = np.where(ok & (first_day >= 0), first_day, days)
    week_close = panel.close[:, t]
    fill = ~np.isfinite(close) & np.isfinite(week_close) & (week_close > 0)
    close[fill] = week_close[fill]
    stale = ~np.isfinite(close)
    close[stale] = last_close[stale]
    unit = panel.unit_eur[:, t]
    unit = np.where(np.isfinite(unit) & (unit > 0), unit, last_unit)
    return close * unit, days


def _year(day: int) -> int:
    import datetime as dt

    return (dt.date(1970, 1, 1) + dt.timedelta(days=int(day))).year


def backtest(panel: WeeklyPanel, variant: RuleVariant, costs: CostModel, rule: UniverseRule) -> BacktestResult:
    """Wendet die Regel Woche für Woche an: Entscheidung am Prüftag (Freitagsschluss), Ausführung zum
    Schlusskurs der ersten Sitzung der Folgewoche, Bewertung zu den Freitagsschlusskursen."""
    result = BacktestResult(variant=variant, status="zu_wenig_historie")
    need = max(variant.lookback_weeks, rule.turnover_weeks - 1)
    weeks = panel.w
    start = None
    first_snap = None
    for t in range(need, weeks):
        if not is_rebalance_week(int(panel.week_ends[t]), variant.rhythm):
            continue
        snap = evaluate_week(panel, t, variant.lookback_weeks, rule)
        if len(snap.order):
            start, first_snap = t, snap
            break
    if start is None:
        return result
    result.status = "ok"
    result.start = start
    net = Portfolio(variant.capital, costs)
    gross = Portfolio(variant.capital, CostModel.free())
    bench = Portfolio(variant.capital, CostModel.free())
    last_close = np.full(panel.n, np.nan)
    last_unit = np.full(panel.n, np.nan)
    for t in range(0, start):
        _prices(panel, t, last_close, last_unit)
    pending: Snapshot | None = None
    pending_day: int | None = None
    for t in range(start, weeks):
        day = int(panel.week_ends[t])
        if pending is not None and pending_day is not None:
            exec_prices, exec_days = _exec_prices(panel, t, last_close, last_unit)
            net.new_year(_year(int(exec_days.min())))
            result.trades += rebalance(net, pending, exec_prices, variant, pending_day, exec_days)
            rebalance(gross, pending, exec_prices, variant, pending_day, exec_days)
            _equal_weight(bench, pending, exec_prices, pending_day)
            result.rebalance_days.append(pending_day)
            pending, pending_day = None, None
        prices = _prices(panel, t, last_close, last_unit)
        net.new_year(_year(day))
        result.days.append(day)
        result.equity.append(net.value(prices))
        result.equity_gross.append(gross.value(prices))
        result.benchmark.append(bench.value(prices))
        if is_rebalance_week(day, variant.rhythm):
            snap = first_snap if t == start else evaluate_week(panel, t, variant.lookback_weeks, rule)
            if len(snap.order) or net.positions:
                pending, pending_day = snap, day
    result.pending = pending
    result.pending_day = pending_day
    result.portfolio = net
    result.gross = gross
    result.last_prices = last_close * last_unit
    return result


def _equal_weight(portfolio: Portfolio, snap: Snapshot, prices: np.ndarray, day: int) -> None:
    """Vergleich: alle Kandidaten gleich gewichtet, ohne Kosten (neu aufgeteilt an jedem Prüftag)."""
    for row in list(portfolio.positions):
        portfolio.sell(row, 1.0, prices[row], day, {})
    rows = [int(r) for r in snap.order.tolist() if math.isfinite(prices[int(r)]) and prices[int(r)] > 0]
    if not rows:
        return
    amount = portfolio.cash / len(rows)
    for row in rows:
        portfolio.buy(row, amount, prices[row], day, {})


@dataclass
class Preview:
    """Tagesvorschlag am Kursstichtag, ausgehend vom Regeldepot nach der letzten ausgeführten Umschichtung.

    ``decision_day`` gesetzt: Am letzten Prüftag wurde umgeschichtet, die Orders werden zum
    Schlusskurs des nächsten Handelstags ausgeführt (die Änderungen sind beschlossen). Sonst zeigen
    die Änderungen, was die Regel nach dem heutigen Stand am nächsten Prüftag täte.
    """

    day: int
    decision_day: int | None
    next_decision_day: int
    ranking: list[dict]
    actions: list[dict]
    holdings: list[dict]
    cash: float
    value: float


def preview(
    now: WeeklyPanel,
    result: BacktestResult,
    variant: RuleVariant,
    rule: UniverseRule,
    day: int,
    *,
    top: int = 20,
) -> Preview | None:
    """Tagesvorschlag. ``now`` hat dieselben Zeilen wie der Rückblick-Test; seine letzte Spalte endet
    am Kursstichtag (Wochen rückwärts ab dem Stichtag)."""
    if result.status != "ok" or result.portfolio is None or now.w == 0:
        return None
    t = now.w - 1
    if result.pending is not None and result.pending_day is not None:
        snap = result.pending
        decision_day: int | None = result.pending_day
        upcoming = next_rebalance_day(result.pending_day + 1, variant.rhythm)
    else:
        snap = evaluate_week(now, t, variant.lookback_weeks, rule)
        decision_day = None
        upcoming = next_rebalance_day(day, variant.rhythm)
    close = now.close[:, t]
    unit = now.unit_eur[:, t]
    fallback = result.last_prices if result.last_prices is not None else np.full(now.n, np.nan)
    prices = np.where(np.isfinite(close) & np.isfinite(unit) & (close > 0), close * unit, fallback)
    portfolio = result.portfolio
    total = portfolio.value(prices)
    ranks = snap.rank_of()
    n = variant.holdings
    buffer = n * variant.keep_rank_factor
    holdings = []
    for row, position in sorted(portfolio.positions.items(), key=lambda item: -item[1].shares * prices[item[0]]):
        value = position.shares * prices[row]
        holdings.append(
            {
                "row": row,
                "shares": position.shares,
                "value": value,
                "weight": value / total if total > 0 else 0.0,
                "entry_day": position.entry_day,
                "basis": position.basis,
                "rendite": value / position.basis - 1.0 if position.basis > 0 else None,
                "rank": ranks.get(row),
                "signal": _f(snap.signal[row]),
            }
        )
    keep = [h["row"] for h in holdings if (h["rank"] or buffer + 1) <= buffer]
    actions = []
    for h in holdings:
        if h["row"] not in keep:
            reason = "nicht_mehr_kandidat" if h["rank"] is None else "platz_ausserhalb_puffer"
            actions.append({"row": h["row"], "action": "verkauf", "w0": h["weight"], "w1": 0.0, "value": h["value"], "rank": h["rank"], "signal": h["signal"], "reason": reason})
    new = [int(row) for row in snap.order.tolist() if int(row) not in portfolio.positions][: n - len(keep)]
    for h in holdings:
        if h["row"] in keep and abs(h["weight"] - 1.0 / n) > variant.band:
            action = "reduzieren" if h["weight"] > 1.0 / n else "aufstocken"
            actions.append({"row": h["row"], "action": action, "w0": h["weight"], "w1": 1.0 / n, "value": abs(h["weight"] - 1.0 / n) * total, "rank": h["rank"], "signal": h["signal"], "reason": "anteil_angleichen"})
    for row in new:
        actions.append({"row": row, "action": "kauf", "w0": 0.0, "w1": 1.0 / n, "value": total / n, "rank": ranks.get(row), "signal": _f(snap.signal[row]), "reason": "neu_unter_den_besten"})
    ranking = [
        {"row": int(row), "rank": k + 1, "signal": _f(snap.signal[row]), "usd": _f(snap.usd[row]), "held": int(row) in portfolio.positions}
        for k, row in enumerate(snap.order[:top].tolist())
    ]
    return Preview(
        day=day,
        decision_day=decision_day,
        next_decision_day=upcoming,
        ranking=ranking,
        actions=actions,
        holdings=holdings,
        cash=portfolio.cash,
        value=total,
    )
