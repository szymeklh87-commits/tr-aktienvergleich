"""Identitätsprüfung: ISIN → eindeutige Referenznotierung.

Regeln (Abschnitte 5 und 7 des Auftrags):
* Primärschlüssel ist die ISIN mit stabiler interner ID. Ein Ticker allein ist nicht
  eindeutig; er wird nur zusammen mit Börse und Währung verwendet.
* Referenznotierung = korrekte Originalnotierung laut Länderpräferenz der ISIN; für
  einen ADR (ISIN mit US-Präfix) die US-Notierung. Kein täglicher Wechsel zur Börse mit
  der höchsten gemessenen Rendite.
* Typen werden klassifiziert (Stamm-/Vorzugsaktie, ADR/GDR, REIT); Unklares bleibt
  „unklar“. Fonds, ETPs, Bezugsrechte und Optionsscheine sind kein Aktieninstrument.
* Namensunterschiede sind nur Hinweise (Umbenennungen sind häufig); Historien werden
  nie allein über ähnliche Namen verknüpft.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..analytics.codes import InstrumentWarning
from ..util.names import name_similarity
from .base import ListingCandidate
from .exchanges import ExchangeTable

TYPE_MAP = {
    "common stock": "stammaktie",
    "ny reg shrs": "stammaktie",
    "dutch cert": "stammaktie",
    "tracking stk": "stammaktie",
    "stapled security": "stammaktie",
    "savings share": "vorzugsaktie",
    "preference": "vorzugsaktie",
    "pfd": "vorzugsaktie",
    "preferred": "vorzugsaktie",
    "adr": "adr_gdr",
    "gdr": "adr_gdr",
    "depositary receipt": "adr_gdr",
    "reit": "reit",
    "equity": "stammaktie",
    "etp": "fonds_etp",
    "etf": "fonds_etp",
    "mutual fund": "fonds_etp",
    "open-end fund": "fonds_etp",
    "closed-end fund": "fonds_etp",
    "fund": "fonds_etp",
    "unit": "unklar",
    "ltd part": "unklar",
    "mlp": "unklar",
    "right": "bezugsrecht",
    "warrant": "optionsschein",
    "equity wrt": "optionsschein",
}
NON_EQUITY = {"fonds_etp", "bezugsrecht", "optionsschein"}


def classify_type(security_type: str | None, security_type2: str | None, excluded: tuple[str, ...]) -> str:
    """Ordnet Anbietertypen einer festen Klasse zu; Unbekanntes bleibt „unklar“."""
    excluded_lower = {e.lower() for e in excluded}
    for raw in (security_type, security_type2):
        if not raw:
            continue
        lowered = raw.strip().lower()
        if lowered in excluded_lower:
            mapped = TYPE_MAP.get(lowered, "fonds_etp")
            return mapped if mapped in NON_EQUITY else "fonds_etp"
        mapped = TYPE_MAP.get(lowered)
        if mapped and mapped != "unklar":
            return mapped
    return "unklar"


@dataclass
class IdentityResult:
    isin: str
    status: str  # verifiziert | unklar | kein_aktieninstrument | offen
    instrument_type: str
    reference: ListingCandidate | None
    reason: str
    candidates: list[ListingCandidate] = field(default_factory=list)
    names: dict[str, str] = field(default_factory=dict)
    warnings: int = 0


def select_reference(isin: str, candidates: list[ListingCandidate], table: ExchangeTable) -> tuple[ListingCandidate | None, str]:
    usable = [c for c in candidates if c.exchange_key and c.provider_symbol]
    if not usable:
        return None, "keine unterstützte Börsennotierung gefunden"
    preference = table.preference_for(isin)
    for key in preference:
        matches = [c for c in usable if c.exchange_key == key]
        if matches:
            matches.sort(key=lambda c: (c.source != "openfigi", len(c.provider_symbol or ""), c.provider_symbol))
            return matches[0], f"Länderpräferenz {isin[:2]} → {key}"
    fallback = table.default_preference
    for key in fallback:
        matches = [c for c in usable if c.exchange_key == key]
        if matches:
            return matches[0], f"Standardpräferenz → {key}"
    usable.sort(key=lambda c: (c.exchange_key or "", c.provider_symbol or ""))
    return usable[0], f"einzige/erste unterstützte Notierung → {usable[0].exchange_key}"


def resolve_identity(
    isin: str,
    tr_name: str,
    candidates: list[ListingCandidate],
    table: ExchangeTable,
    excluded_types: tuple[str, ...],
) -> IdentityResult:
    names = {"tr": tr_name}
    for c in candidates:
        if c.name and c.source not in names:
            names[c.source] = c.name
    if not candidates:
        return IdentityResult(isin, "unklar", "unklar", None, "Identitätsquelle kennt die ISIN nicht", [], names)

    reference, reason = select_reference(isin, candidates, table)
    type_source = reference or candidates[0]
    instrument_type = classify_type(type_source.security_type, type_source.security_type2, excluded_types)
    warnings = 0
    if instrument_type == "unklar":
        warnings |= 1 << InstrumentWarning.TYP_UNKLAR
    if instrument_type in NON_EQUITY:
        return IdentityResult(isin, "kein_aktieninstrument", instrument_type, reference, f"Typ laut Quelle: {type_source.security_type}", candidates, names, warnings)
    if reference is None:
        return IdentityResult(isin, "unklar", instrument_type, None, reason, candidates, names, warnings)

    # Namensprüfung nur als Hinweis: TR-Name gegen Quellname.
    source_name = reference.name or ""
    if source_name and name_similarity(tr_name, source_name) < 0.2:
        warnings |= 1 << InstrumentWarning.NAME_ABWEICHEND
    exchange = table.exchanges.get(reference.exchange_key or "")
    if exchange is not None and exchange.otc:
        warnings |= 1 << InstrumentWarning.OTC_NOTIERUNG
    if exchange is not None and exchange.proxy_calendar:
        warnings |= 1 << InstrumentWarning.ERSATZKALENDER
    return IdentityResult(isin, "verifiziert", instrument_type, reference, reason, candidates, names, warnings)


def verify_against_prices(
    result: IdentityResult,
    *,
    provider_exchange_code: str | None,
    provider_tz: str | None,
    provider_type: str | None,
    provider_name: str | None,
    table: ExchangeTable,
) -> tuple[bool, str]:
    """Plausibilisiert die gewählte Notierung mit den Metadaten des Kursanbieters."""
    if result.reference is None:
        return False, "keine Referenznotierung"
    exchange = table.exchanges.get(result.reference.exchange_key or "")
    if exchange is None:
        return False, "Börse unbekannt"
    if provider_type and provider_type.upper() not in ("EQUITY", "STOCK", "COMMON STOCK"):
        return False, f"Kursanbieter meldet Instrumenttyp {provider_type}"
    if provider_tz and provider_tz != exchange.tz:
        # gleiche Zeitzonenregion (z. B. America/Toronto vs. America/New_York) ist ein echter Widerspruch
        return False, f"Zeitzone {provider_tz} passt nicht zu {exchange.name} ({exchange.tz})"
    if provider_exchange_code and exchange.yahoo_codes and provider_exchange_code not in exchange.yahoo_codes:
        other = table.exchanges_for_yahoo_code(provider_exchange_code)
        if not other or all(table.exchanges[o].tz != exchange.tz for o in other):
            return False, f"Börsencode {provider_exchange_code} passt nicht zu {exchange.name}"
    if provider_name and result.reference.name and name_similarity(provider_name, result.reference.name) < 0.15:
        if name_similarity(provider_name, result.names.get("tr", "")) < 0.15:
            return False, f"Name beim Kursanbieter ({provider_name}) passt weder zur Identitätsquelle noch zur TR-Liste"
    return True, "bestätigt"
