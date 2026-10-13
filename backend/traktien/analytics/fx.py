"""Indikative Umrechnung in US-Dollar aus Referenzkursen je Euro (reine Funktionen).

Quelle im Betrieb sind die Euro-Referenzkurse der Europäischen Zentralbank: je Bankarbeitstag
ein Kurs „1 EUR = x Einheiten“ für rund 30 Währungen, veröffentlicht gegen 16:00 Uhr MEZ.
USD je Einheit einer Währung W ergibt sich als Kreuzkurs (USD je EUR) / (W je EUR).

Verwendet wird für eine Börsensitzung der Referenzkurs desselben Tages oder – an Tagen ohne
EZB-Kurs (Wochenende, TARGET-Feiertag) – der letzte davor, höchstens ``max_age_days`` alt.
Die Umrechnung dient nur dem Umsatzfilter; Kursrenditen bleiben in Notierungswährung.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass(frozen=True)
class FxRates:
    source: str  # z. B. „EZB-Referenzkurse“ oder „DEMO – synthetische Wechselkurse“
    url: str | None
    fetched_at: str | None  # Abrufzeit (UTC, ISO), None = nur aus der Sicherung
    days: np.ndarray  # aufsteigende Kurstage (Epochentage)
    per_eur: dict[str, np.ndarray] = field(default_factory=dict)  # Währung → Einheiten je EUR (NaN = kein Kurs)
    max_age_days: int = 5

    @staticmethod
    def from_rows(rows: list[tuple[int, str, float]], *, source: str, url: str | None, fetched_at: str | None, max_age_days: int) -> "FxRates":
        """Aus Zeilen (Tag, Währung, Einheiten je EUR)."""
        days = np.array(sorted({int(day) for day, _, _ in rows}), dtype=np.int64)
        position = {int(day): k for k, day in enumerate(days.tolist())}
        per_eur: dict[str, np.ndarray] = {}
        for day, currency, rate in rows:
            column = per_eur.setdefault(currency, np.full(len(days), np.nan))
            value = float(rate)
            if np.isfinite(value) and value > 0:
                column[position[int(day)]] = value
        return FxRates(source=source, url=url, fetched_at=fetched_at, days=days, per_eur=per_eur, max_age_days=max_age_days)

    @property
    def currencies(self) -> list[str]:
        return sorted({"EUR", *self.per_eur})

    @property
    def first_day(self) -> int | None:
        return int(self.days[0]) if len(self.days) else None

    @property
    def last_day(self) -> int | None:
        return int(self.days[-1]) if len(self.days) else None

    def _per_eur_at(self, currency: str, day: int) -> tuple[float, int] | None:
        """Einheiten je EUR für ``currency``: Kurs am Tag oder der letzte davor (höchstens max_age_days alt)."""
        if currency == "EUR":
            return 1.0, day
        column = self.per_eur.get(currency)
        if column is None or not len(self.days):
            return None
        k = int(np.searchsorted(self.days, day, side="right")) - 1
        while k >= 0 and day - int(self.days[k]) <= self.max_age_days:
            value = column[k]
            if np.isfinite(value):
                return float(value), int(self.days[k])
            k -= 1
        return None

    def usd_per_unit(self, currency: str, day: int) -> tuple[float, int] | None:
        """USD je Einheit ``currency`` für die Sitzung ``day`` und der Tag des verwendeten Referenzkurses.

        Für USD selbst 1,0 ohne Referenzkurs (Tag = Sitzungstag). None, wenn kein ausreichend
        aktueller Kurs vorliegt.
        """
        if currency == "USD":
            return 1.0, day
        usd = self._per_eur_at("USD", day)
        own = self._per_eur_at(currency, day)
        if usd is None or own is None:
            return None
        return usd[0] / own[0], min(usd[1], own[1])
