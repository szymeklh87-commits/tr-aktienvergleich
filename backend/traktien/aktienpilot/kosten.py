"""Handelskosten (Abschnitt 14): Ordergebühr, halber Spread, Slippage, Währungsaufschlag, TR-Aufschlag.

Alle Werte sind konfigurierte Ausgangswerte (``config/aktienpilot.yaml``, Abschnitt ``handelskosten``) – die angenommene
TR-Ordergebühr von 1 EUR gilt nicht pauschal für alle Orderarten und ist anhand aktueller Konditionen und echter Bestätigungen
zu prüfen. Ein Kauf wird zum Kurs plus Aufschlag gerechnet, ein Verkauf zum Kurs minus Aufschlag; die Gebühr kommt dazu.
"""

from __future__ import annotations

from dataclasses import dataclass

from .config import CostConfig

LIQUID_EUR = 50_000_000.0
NORMAL_EUR = 2_000_000.0


@dataclass(frozen=True)
class CostQuote:
    price: float  # Ausführungskurs nach Spread, Slippage und Aufschlägen (Notierungswährung)
    fee_eur: float
    spread_bp: float
    slippage_bp: float
    fx_bp: float
    tr_bp: float

    def as_dict(self) -> dict:
        return {"kurs": self.price, "gebuehr_eur": self.fee_eur, "spread_bp": self.spread_bp, "slippage_bp": self.slippage_bp,
                "waehrung_bp": self.fx_bp, "tr_aufschlag_bp": self.tr_bp}


def spread_bp(costs: CostConfig, turnover_eur: float | None) -> float:
    """Spread nach Liquiditätsklasse; unbekannter Umsatz zählt als illiquide (konservativ)."""
    if turnover_eur is None or turnover_eur != turnover_eur:
        return costs.spread_bp_illiquide
    if turnover_eur >= LIQUID_EUR:
        return costs.spread_bp_liquide
    if turnover_eur >= NORMAL_EUR:
        return costs.spread_bp_normal
    return costs.spread_bp_illiquide


def quote(costs: CostConfig, side: str, price: float, *, currency: str, turnover_eur: float | None, next_close_profile: bool) -> CostQuote:
    """Ausführungskurs und Gebühr für ``side`` („kauf“/„verkauf“) zum Referenzkurs ``price``."""
    half_spread = spread_bp(costs, turnover_eur) / 2.0
    fx = costs.waehrung_bp if currency != "EUR" else 0.0
    tr = costs.tr_aufschlag_bp if next_close_profile else 0.0
    total_bp = half_spread + costs.slippage_bp + fx + tr
    sign = 1.0 if side == "kauf" else -1.0
    executed = price * (1.0 + sign * total_bp / 10_000.0)
    return CostQuote(executed, costs.ordergebuehr_eur, half_spread, costs.slippage_bp, fx, tr)
