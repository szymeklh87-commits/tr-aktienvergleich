"""Börsentabelle: Zuordnung Anbieter-Börsencodes → Referenzbörse, Kalender, Symbolformat."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml

from ..config import CONFIG_DIR

UNIT_FACTORS = {"GBp": 0.01, "GBX": 0.01, "ZAc": 0.01, "ZAC": 0.01, "ILA": 0.01}
UNIT_BASE = {"GBp": "GBP", "GBX": "GBP", "ZAc": "ZAR", "ZAC": "ZAR", "ILA": "ILS"}


# Börsen, an denen Aktiengattungen als Buchstabe am Ticker stehen (Yahoo: „VOLV-B.ST“)
NORDIC_CLASS_EXCHANGES = ("XSTO", "XCSE", "XHEL", "XOSL", "XICE")


@dataclass(frozen=True)
class Exchange:
    key: str
    name: str
    mic: str
    calendar: str
    tz: str
    currency: str
    figi_codes: tuple[str, ...]
    yahoo_suffix: str
    yahoo_codes: tuple[str, ...]
    eodhd: str | None
    otc: bool = False
    proxy_calendar: bool = False
    ticker_pad: int | None = None


@dataclass
class ExchangeTable:
    version: str
    exchanges: dict[str, Exchange]
    country_preferences: dict[str, list[str]]
    default_preference: list[str]
    by_figi: dict[str, str] = field(default_factory=dict)
    by_yahoo_code: dict[str, list[str]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for key, exchange in self.exchanges.items():
            for code in exchange.figi_codes:
                self.by_figi.setdefault(code, key)
            for code in exchange.yahoo_codes:
                self.by_yahoo_code.setdefault(code, []).append(key)

    def preference_for(self, isin: str) -> list[str]:
        return list(self.country_preferences.get(isin[:2].upper(), self.default_preference))

    def exchange_for_figi(self, exch_code: str | None) -> Exchange | None:
        if not exch_code:
            return None
        key = self.by_figi.get(exch_code)
        return self.exchanges.get(key) if key else None

    def yahoo_symbol(self, exchange: Exchange, ticker: str) -> str:
        """Wandelt einen Börsenticker in das Yahoo-Symbolformat um (dokumentierte Regeln)."""
        cleaned = ticker.strip().upper()
        if exchange.ticker_pad and cleaned.isdigit():
            cleaned = cleaned.zfill(exchange.ticker_pad)
        cleaned = cleaned.replace("/", "-").replace(" ", "-").replace(".", "-")
        return cleaned + exchange.yahoo_suffix

    def symbol_variants(self, exchange: Exchange, symbol: str) -> list[str]:
        """Andere Schreibweisen eines Symbols, das der Kursanbieter nicht kennt (ohne Netzabruf).

        Nordische Börsen: Aktiengattungen hängen bei der Identitätsquelle oft ohne Trennzeichen am
        Ticker („ADDTB“), Yahoo schreibt sie mit Bindestrich („ADDT-B.ST“).
        """
        suffix = exchange.yahoo_suffix
        base = symbol[: -len(suffix)] if suffix and symbol.endswith(suffix) else symbol
        out: list[str] = []
        if exchange.key in NORDIC_CLASS_EXCHANGES and "-" not in base and len(base) >= 3 and base[-1] in "ABCD" and base[:-1].isalnum():
            out.append(f"{base[:-1]}-{base[-1]}{suffix}")
        return [variant for variant in out if variant != symbol]

    def exchanges_for_yahoo_code(self, code: str | None) -> list[str]:
        return list(self.by_yahoo_code.get(code or "", []))

    def exchange_for_yahoo_symbol(self, symbol: str, yahoo_exchange_code: str | None = None) -> Exchange | None:
        candidates = self.exchanges_for_yahoo_code(yahoo_exchange_code)
        if candidates:
            # Bei mehreren US-Schlüsseln den spezifischsten wählen.
            for key in candidates:
                if key not in ("US",):
                    return self.exchanges[key]
            return self.exchanges[candidates[0]]
        suffix = "." + symbol.rsplit(".", 1)[1] if "." in symbol else ""
        for exchange in self.exchanges.values():
            if exchange.yahoo_suffix == suffix and suffix:
                return exchange
        if not suffix:
            return self.exchanges.get("US")
        return None


def _load(path: Path) -> ExchangeTable:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    exchanges: dict[str, Exchange] = {}
    for key, item in raw["boersen"].items():
        exchanges[key] = Exchange(
            key=key,
            name=item["name"],
            mic=item.get("mic", key),
            calendar=item["kalender"],
            tz=item["zeitzone"],
            currency=item.get("waehrung", ""),
            figi_codes=tuple(item.get("figi_codes", [])),
            yahoo_suffix=item.get("yahoo_suffix", ""),
            yahoo_codes=tuple(item.get("yahoo_codes", [])),
            eodhd=item.get("eodhd"),
            otc=bool(item.get("otc", False)),
            proxy_calendar=bool(item.get("ersatzkalender", False)),
            ticker_pad=item.get("ticker_auffuellen"),
        )
    prefs = {k.upper(): list(v) for k, v in (raw.get("laenderpraeferenz") or {}).items()}
    for country, keys in prefs.items():
        unknown = [k for k in keys if k not in exchanges]
        if unknown:
            raise ValueError(f"Länderpräferenz {country} verweist auf unbekannte Börsen {unknown}")
    default = list(raw.get("standard_praeferenz") or ["US"])
    return ExchangeTable(raw.get("version", "boersen-v1"), exchanges, prefs, default)


@lru_cache(maxsize=4)
def load_exchange_table(path: str | None = None) -> ExchangeTable:
    return _load(Path(path) if path else CONFIG_DIR / "boersen.yaml")


def unit_info(currency: str | None) -> tuple[str | None, float]:
    """(Basiswährung, Faktor) für Untereinheiten wie GBp → (GBP, 0.01)."""
    if not currency:
        return None, 1.0
    if currency in UNIT_FACTORS:
        return UNIT_BASE[currency], UNIT_FACTORS[currency]
    return currency, 1.0
