"""Marktdaten des AktienPilot: Tageskerzen je Aktie, Wechselkurse, Leitindizes.

Kurse in der Notierungswährung, splitbereinigt (wie in der App), **nicht** dividendenbereinigt; ``unit_factor`` rechnet
Untereinheiten (GBp, ZAc, ILA) in die Basiswährung um. Eine Tageskerze gilt erst nach Sitzungsende als vollständig
(Abschnitt 7) – die Marktdaten enthalten nur abgeschlossene Sitzungen bis zum Datenstichtag. Ausführungspreise sind die Kurse
der jeweiligen Sitzung; rückwirkend angepasste Preise vor einem späteren Split werden mit ``split_factor_after`` auf den damals
gehandelten Kurs zurückgerechnet, wo das für eine Ausführung nötig ist.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..analytics.fx import FxRates


@dataclass
class Series:
    """Tageskerzen einer Aktie (nur Sitzungen mit Kurs), aufsteigend."""

    isin: str
    days: np.ndarray
    open: np.ndarray
    high: np.ndarray
    low: np.ndarray
    close: np.ndarray
    volume: np.ndarray
    currency: str = "EUR"  # Basiswährung (nach Umrechnung der Untereinheit)
    unit_factor: float = 1.0  # Kurs × unit_factor = Kurs in der Basiswährung
    exchange: str = ""
    calendar: str | None = None
    name: str = ""
    sector: str | None = None
    splits: tuple[tuple[int, float], ...] = ()  # (Tag des Splits, Faktor wie in daily_bar: close_raw = close × Faktor davor)
    synthetic: bool = False

    def __post_init__(self) -> None:
        self.days = np.asarray(self.days, dtype=np.int64)
        for name in ("open", "high", "low", "close", "volume"):
            setattr(self, name, np.asarray(getattr(self, name), dtype=np.float64))
        n = len(self.days)
        if not all(len(getattr(self, name)) == n for name in ("open", "high", "low", "close", "volume")):
            raise ValueError(f"{self.isin}: Kerzenreihen unterschiedlich lang")
        if n > 1 and np.any(np.diff(self.days) <= 0):
            raise ValueError(f"{self.isin}: Tage nicht streng aufsteigend (doppelte Tage)")

    def upto(self, day: int) -> int:
        """Index der letzten Kerze mit Tag ≤ ``day``; −1, wenn es keine gibt."""
        return int(np.searchsorted(self.days, day, side="right")) - 1

    def index_of(self, day: int) -> int | None:
        k = int(np.searchsorted(self.days, day))
        return k if k < len(self.days) and int(self.days[k]) == day else None

    def split_explained(self, day: int, tolerance_days: int = 1) -> bool:
        """Liegt am Tag (± Toleranz) ein gemeldeter Split? Dann ist eine Kurslücke dort keine Auffälligkeit."""
        return any(abs(int(s_day) - int(day)) <= tolerance_days for s_day, _ in self.splits)

    def split_factor_after(self, day: int) -> float:
        """Produkt der Splitfaktoren nach ``day``: gehandelter Kurs am Tag = bereinigter Kurs × Faktor."""
        f = 1.0
        for s_day, factor in self.splits:
            if int(s_day) > int(day):
                f *= float(factor)
        return f


@dataclass
class Market:
    """Alle Marktdaten eines Laufs oder Backtests."""

    series: dict[str, Series]
    fx: FxRates | None = None
    indices: dict[str, Series] = field(default_factory=dict)
    synthetic: bool = False
    data_stand: str = ""  # Snapshot-ID bzw. Datenrevision
    source: str = ""

    def eur_rate(self, currency: str, day: int) -> float | None:
        """EUR je Einheit der Basiswährung am Tag (Kurs des Tages oder der letzte davor, wie ``FxRates``)."""
        if currency == "EUR":
            return 1.0
        if self.fx is None:
            return None
        return self.fx.eur_per_unit(currency, day)

    def price_eur(self, isin: str, price: float, day: int) -> float | None:
        s = self.series.get(isin)
        if s is None or not np.isfinite(price):
            return None
        rate = self.eur_rate(s.currency, day)
        return None if rate is None else float(price) * s.unit_factor * rate

    def last_close(self, isin: str, day: int) -> tuple[float, int] | None:
        """Letzter Schlusskurs bis ``day`` und sein Tag."""
        s = self.series.get(isin)
        if s is None:
            return None
        k = s.upto(day)
        if k < 0 or not np.isfinite(s.close[k]):
            return None
        return float(s.close[k]), int(s.days[k])

    def calendar_days(self, first: int, last: int) -> np.ndarray:
        """Alle Tage, an denen irgendeine Aktie eine Sitzung hat (aufsteigend) – Takt des Backtests."""
        parts = [s.days[(s.days >= first) & (s.days <= last)] for s in self.series.values()]
        if not parts:
            return np.empty(0, dtype=np.int64)
        return np.unique(np.concatenate(parts))
