"""Sammelabruf der Tageskurse (ab 1.17): vorhandene Kursreihen weiterverwenden, nur neue Sitzungen ergänzen.

Bis 1.16 holte der tägliche Lauf jede der rund 11.000 Notierungen einzeln über den Chart-Abruf (höchstens 2,5 Abrufe
je Sekunde, gemessen 74 von 80–115 Minuten Laufzeit). Ab 1.17 kommen die letzten Tageskurse aller Notierungen mit
gespeicherter Kursreihe zuerst gesammelt:

* „spark“ liefert je Abruf für bis zu 20 Werte die Schlusskurse eines Monats (Überlappung mit den gespeicherten
  Kursen) und die Kursmeldung der neuesten Sitzung;
* „quote“ liefert je Abruf für bis zu 150 Werte Eröffnung, Tageshoch, -tief und Umsatz der neuesten Sitzung.

``plan_increment`` entscheidet je Notierung allein aus diesen Daten (reine Funktion, testbar), ob

* nichts Neues vorliegt (``aktuell``),
* genau eine neue, abgeschlossene Sitzung als Tageskerze ergänzt werden kann (``neu``) oder
* die Notierung wie bisher einzeln über den Chart-Abruf geholt werden muss (``einzeln``) – immer dann, wenn
  etwas nicht eindeutig ist: keine Sammeldaten, gespeicherte und neue Schlusskurse weichen ab (Split oder
  Korrektur → die bisherige Prüfung im Chart-Weg liest die Historie neu ein), mehr als eine neue Sitzung (für die
  Tage dazwischen fehlen Umsatz, Hoch und Tief), keine passende Kursmeldung, Kurs und Meldung passen nicht zusammen,
  vorläufige Schlusskurse in der Überlappung.

Der Chart-Weg bleibt damit für alle Sonderfälle unverändert zuständig; der Sammelabruf ersetzt nur den Normalfall.
"""

from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass, field
from typing import Callable

import numpy as np

from ..providers.base import LiveQuote, PriceHistory, RecentBars
from ..providers.exchanges import unit_info
from ..util.timeutil import UTC, date_to_day, iso_utc, session_date_from_timestamp

# Gespeicherte und neue Schlusskurse gelten als gleich, wenn sie höchstens so weit auseinanderliegen
# (dieselbe Schwelle wie die Korrekturerkennung des Chart-Wegs, ``DailyRun.store_history``).
OVERLAP_TOLERANCE = 1e-6
# Schlusskurs der neuen Sitzung (spark) und Kursmeldung (quote) müssen so genau übereinstimmen
QUOTE_TOLERANCE = 1e-6
# Bit in ``daily_bar.quality``: vorläufiger Schlusskurs aus der Kursmeldung (siehe ``repo.QUALITY_CLOSE_FROM_QUOTE``)
QUALITY_CLOSE_FROM_QUOTE = 1

ACTION_CURRENT = "aktuell"
ACTION_NEW = "neu"
ACTION_SINGLE = "einzeln"


@dataclass
class StoredTail:
    """Gespeicherte Tageskurse der aktuellen Revision ab einem Tag (``repo.load_bars``)."""

    days: np.ndarray
    close: np.ndarray
    quality: np.ndarray
    volume: np.ndarray | None = None

    def no_trade(self, k: int) -> bool:
        """Tag ohne Handel laut gespeicherter Tageskerze: Umsatz 0 oder Schlusskurs wie am Vortag. Solche Tage lässt
        die Sammelabfrage aus (gemessen am 24.10.2026: 92 % der dort fehlenden Tage)."""
        if self.volume is not None and k < len(self.volume) and float(self.volume[k]) == 0.0:
            return True
        return k > 0 and float(self.close[k]) == float(self.close[k - 1])

    @property
    def last_day(self) -> int | None:
        return int(self.days[-1]) if len(self.days) else None


@dataclass
class IncrementPlan:
    action: str
    reason: str
    history: PriceHistory | None = None
    overlap: int = 0
    max_deviation: float = 0.0
    new_day: int | None = None
    # Herkunft der Werte der neuen Tageskerze (nur Zählungen für die Laufübersicht)
    sources: dict[str, str] = field(default_factory=dict)


def session_days(timestamps: list[int], tz_name: str | None) -> np.ndarray:
    """Handelstage der Tageskerzen in der Zeitzone der Börse (wie ``parse_chart``)."""
    zone = tz_name or "UTC"
    return np.array([date_to_day(session_date_from_timestamp(int(ts), zone)) for ts in timestamps], dtype=np.int64)


def _finite_positive(value: float) -> bool:
    return value is not None and math.isfinite(value) and value > 0


def plan_increment(
    stored: StoredTail,
    recent: RecentBars | None,
    quote: LiveQuote | None,
    *,
    tz_name: str | None,
    session_final: Callable[[int], bool],
    overlap_tolerance: float = OVERLAP_TOLERANCE,
    quote_tolerance: float = QUOTE_TOLERANCE,
    symbol: str = "",
    fetched_at: dt.datetime | None = None,
) -> IncrementPlan:
    """Entscheidet für eine Notierung mit gespeicherter Kursreihe, was der Sammelabruf ergänzen darf (siehe Modultext)."""
    if recent is None:
        return IncrementPlan(ACTION_SINGLE, "keine_sammeldaten")
    last_stored = stored.last_day
    if last_stored is None:
        return IncrementPlan(ACTION_SINGLE, "keine_kursreihe")
    zone = recent.exchange_tz or tz_name
    days = session_days(recent.timestamps, zone)
    close = np.asarray(recent.close, dtype=np.float64)
    valid = np.isfinite(close) & (close > 0)
    # Bei Doppelungen gewinnt wie im Chart-Weg der letzte Eintrag desselben Tages
    by_day: dict[int, tuple[float, int]] = {}
    for k in np.flatnonzero(valid):
        by_day[int(days[k])] = (float(close[k]), int(recent.timestamps[k]))
    if not by_day:
        return IncrementPlan(ACTION_SINGLE, "keine_tageskurse")

    # 1) Überlappung: jeder gemeinsame Tag muss mit dem gespeicherten Schlusskurs übereinstimmen
    stored_index = {int(d): k for k, d in enumerate(stored.days.tolist())}
    first_recent = min(by_day)
    overlap = 0
    deviation = 0.0
    for day, (value, _) in by_day.items():
        k = stored_index.get(day)
        if k is None:
            continue
        if int(stored.quality[k]) & QUALITY_CLOSE_FROM_QUOTE:
            # vorläufiger Schlusskurs: sein Ersatz durch die Tageskerze übernimmt der Chart-Weg (zählt mit)
            return IncrementPlan(ACTION_SINGLE, "vorlaeufiger_kurs", overlap=overlap)
        old = float(stored.close[k])
        if not (old > 0):
            continue
        diff = abs(value / old - 1.0)
        deviation = max(deviation, diff)
        overlap += 1
    if deviation > overlap_tolerance:
        return IncrementPlan(ACTION_SINGLE, "abweichung", overlap=overlap, max_deviation=deviation)
    if overlap == 0:
        # Sammeldaten reichen nicht bis zur gespeicherten Reihe zurück (Lücke) oder enthalten keinen ihrer Tage
        return IncrementPlan(ACTION_SINGLE, "keine_ueberlappung" if first_recent > last_stored else "ohne_gemeinsamen_tag", max_deviation=deviation)
    # Ein gespeicherter Tag fehlt in den Sammeldaten, obwohl er in ihren Zeitraum fällt: nur unbedenklich, wenn an
    # diesem Tag nicht gehandelt wurde (die Sammelabfrage lässt solche Tage aus) – sonst nicht eindeutig
    for k, day in enumerate(stored.days.tolist()):
        if first_recent <= int(day) <= last_stored and int(day) not in by_day and not stored.no_trade(k):
            return IncrementPlan(ACTION_SINGLE, "tag_fehlt", overlap=overlap, max_deviation=deviation)

    # 2) Neue, abgeschlossene Sitzungen nach dem letzten gespeicherten Tag
    new_days = sorted(d for d in by_day if d > last_stored and session_final(d))
    if not new_days:
        return IncrementPlan(ACTION_CURRENT, "keine_neue_sitzung", overlap=overlap, max_deviation=deviation)
    if len(new_days) > 1:
        return IncrementPlan(ACTION_SINGLE, "mehrere_neue_tage", overlap=overlap, max_deviation=deviation)
    day = new_days[0]
    value, stamp = by_day[day]

    # 3) Kursmeldung („quote“) derselben Sitzung: Eröffnung, Hoch, Tief und Umsatz. Die Meldung in der Spark-Antwort
    # kennt keine Eröffnung – ohne passende Kursmeldung bleibt die Notierung deshalb beim Chart-Abruf. Das ist auch der
    # Fall, wenn die Börse schon die nächste Sitzung handelt (die Meldung gehört dann zu „heute“).
    sources: dict[str, str] = {"schluss": "spark", "umsatz": "quote"}
    if quote is None or quote.session_day != day:
        return IncrementPlan(ACTION_SINGLE, "meldung_fehlt", overlap=overlap, max_deviation=deviation, new_day=day)
    if not (abs(quote.price / value - 1.0) <= quote_tolerance):
        return IncrementPlan(ACTION_SINGLE, "meldung_passt_nicht", overlap=overlap, max_deviation=deviation, new_day=day)
    volume = quote.volume
    opening, high, low = quote.day_open, quote.day_high, quote.day_low
    if not (volume is not None and math.isfinite(volume) and volume >= 0):
        return IncrementPlan(ACTION_SINGLE, "umsatz_fehlt", overlap=overlap, max_deviation=deviation, new_day=day)
    # Tageshoch/-tief nur übernehmen, wenn sie zum Schlusskurs passen (wie beim Schlusskurs aus der Kursmeldung)
    if not (_finite_positive(high) and _finite_positive(low) and high >= value >= low):
        high = low = math.nan
        sources["hoch_tief"] = "fehlt"
    if not _finite_positive(opening) or (_finite_positive(high) and not (low <= opening <= high)):
        opening = math.nan
        sources["eroeffnung"] = "fehlt"

    history = PriceHistory(
        provider="yahoo",
        symbol=symbol or recent.symbol,
        days=np.array([day], dtype=np.int64),
        open=np.array([opening], dtype=np.float64),
        high=np.array([high], dtype=np.float64),
        low=np.array([low], dtype=np.float64),
        close=np.array([value], dtype=np.float64),
        volume=np.array([float(volume)], dtype=np.float64),
        close_raw=np.array([value], dtype=np.float64),
        close_total=None,
        currency=recent.currency,
        price_unit=recent.currency,
        unit_factor=unit_info(recent.currency)[1],
        exchange_name=recent.exchange_name,
        exchange_tz=zone,
        instrument_type=recent.instrument_type,
        long_name=recent.long_name,
        short_name=recent.short_name,
        bar_times_utc=[iso_utc(dt.datetime.fromtimestamp(stamp, tz=UTC))],
        fetched_at=fetched_at,
    )
    return IncrementPlan(ACTION_NEW, "neue_sitzung", history=history, overlap=overlap, max_deviation=deviation, new_day=day, sources=sources)
