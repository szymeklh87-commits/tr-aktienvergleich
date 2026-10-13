"""Durchschnittlicher Tagesumsatz einer Notierung (Aufnahmefilter für Ranking 2).

Definition (``umsatz-v1``):

* Betrachtet werden die letzten ``sitzungen`` (20) vollständig abgeschlossenen Sitzungen der
  Referenzbörse bis einschließlich Kursstichtag – laut Börsenkalender, nicht laut Kursdatei.
* Umsatz einer Sitzung ≈ Schlusskurs × gemeldetes Handelsvolumen derselben Notierung, beide
  splitbereinigt; Kurse in Untereinheiten (Pence, Agorot, Cent) werden in die Hauptwährung
  umgerechnet.
* Fehlt für eine Sitzung der Kurs oder das Volumen, zählt sie nicht – sie wird nicht als null
  eingesetzt. Ein gemeldetes Volumen von 0 ist dagegen eine echte Angabe und zählt mit 0.
* Mindestens ``min_sitzungen_mit_umsatz`` (16) der 20 Sitzungen brauchen ein positives Volumen.
* Liegt ein Split oder eine Zusammenlegung innerhalb der 20 Sitzungen, gilt der Umsatz als nicht
  verzerrungsfrei bestimmbar (Kapitalmaßnahme).
* Umrechnung in USD je Sitzung mit dem Referenzkurs dieses Tages (oder dem letzten davor,
  höchstens ``wechselkurs_max_alter_tage`` alt); ohne Kurs für eine Sitzung keine Angabe in USD.
* Ø Tagesumsatz = arithmetischer Mittelwert über die Sitzungen mit Daten.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .fx import FxRates

TURNOVER_STATUS: dict[str, dict[str, str]] = {
    "ok": {"kurz": "Ø Tagesumsatz bestimmt", "text": "Mittelwert aus Schlusskurs × Volumen über die Sitzungen mit Daten."},
    "keine_kurse": {"kurz": "Keine Kurse", "text": "Für die Notierung liegen keine verwertbaren Tageskurse vor."},
    "kalender_fehlt": {"kurz": "Börsenkalender fehlt", "text": "Ohne geprüften Börsenkalender lassen sich die 20 Sitzungen nicht bestimmen."},
    "zu_wenige_sitzungen": {"kurz": "Zu wenige Sitzungen", "text": "Der Börsenkalender kennt bis zum Stichtag weniger als 20 abgeschlossene Sitzungen."},
    "daten_fehlen": {"kurz": "Kurse oder Volumen fehlen", "text": "Für weniger als 16 der 20 Sitzungen liegen Schlusskurs und gemeldetes Volumen vor; fehlende Tage werden nicht als null gezählt."},
    "zu_wenig_umsatztage": {"kurz": "Zu wenige Tage mit Umsatz", "text": "Weniger als 16 der 20 Sitzungen haben ein positives Handelsvolumen."},
    "kapitalmassnahme": {"kurz": "Kapitalmaßnahme im Zeitraum", "text": "Split oder Zusammenlegung innerhalb der 20 Sitzungen; der Umsatz wäre nicht verzerrungsfrei bestimmbar."},
    "waehrung_unbekannt": {"kurz": "Währung unbekannt", "text": "Die Notierungswährung ist nicht bekannt; keine Umrechnung möglich."},
    "wechselkurs_fehlt": {"kurz": "Wechselkurs fehlt", "text": "Für mindestens eine Sitzung fehlt ein ausreichend aktueller Referenzkurs der Währung in USD."},
}


@dataclass(frozen=True)
class TurnoverResult:
    status: str
    sessions: int = 0  # betrachtete Sitzungen (regulär 20)
    with_data: int = 0  # davon mit Schlusskurs und gemeldetem Volumen
    positive: int = 0  # davon mit positivem Volumen
    first_day: int | None = None  # erste der betrachteten Sitzungen
    last_day: int | None = None  # letzte der betrachteten Sitzungen (≤ Stichtag)
    currency: str | None = None  # Hauptwährung der Umsatzangabe in Landeswährung
    avg_local: float | None = None  # Ø Tagesumsatz in Hauptwährung (z. B. GBP statt GBp)
    avg_usd: float | None = None  # Ø Tagesumsatz in USD (indikativ)
    fx_first_day: int | None = None  # ältester verwendeter Referenzkurstag
    fx_last_day: int | None = None  # jüngster verwendeter Referenzkurstag

    @property
    def determined(self) -> bool:
        return self.status == "ok" and self.avg_usd is not None

    def fingerprint(self) -> str:
        """Eindeutige Textform für den Eingabe-Hash des Snapshots."""
        return (
            f"{self.status}:{self.sessions}:{self.with_data}:{self.positive}:{self.first_day}:{self.last_day}:"
            f"{self.currency}:{self.avg_local!r}:{self.avg_usd!r}:{self.fx_first_day}:{self.fx_last_day}"
        )


def compute_turnover(
    days: np.ndarray,
    close: np.ndarray,
    volume: np.ndarray,
    sessions: np.ndarray | None,
    cutoff_day: int,
    *,
    split_days: np.ndarray,
    currency: str | None,
    unit_factor: float,
    fx: FxRates | None,
    n_sessions: int = 20,
    min_positive: int = 16,
) -> TurnoverResult:
    """Ø Tagesumsatz über die letzten ``n_sessions`` abgeschlossenen Sitzungen bis ``cutoff_day``.

    ``days``/``close``/``volume`` sind die geprüften Beobachtungen der Referenznotierung
    (aufsteigend, Volumen NaN = nicht gemeldet). ``unit_factor`` rechnet die Kurseinheit in die
    Hauptwährung um (0,01 für Pence).
    """
    if sessions is None or len(sessions) == 0:
        return TurnoverResult("kalender_fehlt")
    days = np.asarray(days, dtype=np.int64)
    if len(days) == 0:
        return TurnoverResult("keine_kurse")
    eligible = np.asarray(sessions, dtype=np.int64)
    eligible = eligible[eligible <= cutoff_day]
    if len(eligible) < n_sessions:
        return TurnoverResult("zu_wenige_sitzungen", sessions=int(len(eligible)))
    window = eligible[-n_sessions:]
    first, last = int(window[0]), int(window[-1])
    base = dict(sessions=n_sessions, first_day=first, last_day=last, currency=currency)

    splits = np.asarray(split_days, dtype=np.int64)
    if len(splits) and np.any((splits > first) & (splits <= last)):
        return TurnoverResult("kapitalmassnahme", **base)

    close = np.asarray(close, dtype=np.float64)
    volume = np.asarray(volume, dtype=np.float64)
    position = np.searchsorted(days, window)
    found = (position < len(days)) & (days[np.minimum(position, len(days) - 1)] == window)
    session_days: list[int] = []
    local_values: list[float] = []
    positive = 0
    for k, day in enumerate(window.tolist()):
        if not found[k]:
            continue  # keine Kerze für diese Sitzung: zählt nicht (kein Nullersatz)
        p = int(position[k])
        price, shares = float(close[p]), float(volume[p])
        if not (np.isfinite(price) and price > 0 and np.isfinite(shares) and shares >= 0):
            continue  # Kurs oder Volumen nicht gemeldet: zählt nicht
        session_days.append(day)
        local_values.append(price * shares * float(unit_factor))
        if shares > 0:
            positive += 1
    with_data = len(local_values)
    counted = dict(base, with_data=with_data, positive=positive)
    if with_data < min_positive:
        return TurnoverResult("daten_fehlen", **counted)
    if positive < min_positive:
        return TurnoverResult("zu_wenig_umsatztage", **counted)
    avg_local = float(np.mean(local_values))
    counted["avg_local"] = avg_local
    if not currency:
        return TurnoverResult("waehrung_unbekannt", **counted)
    usd_values: list[float] = []
    rate_days: list[int] = []
    for day, value in zip(session_days, local_values):
        rate = fx.usd_per_unit(currency, day) if fx is not None else (1.0, day) if currency == "USD" else None
        if rate is None:
            return TurnoverResult("wechselkurs_fehlt", **counted)
        usd_values.append(value * rate[0])
        rate_days.append(rate[1])
    fx_days = rate_days if currency != "USD" else []
    return TurnoverResult(
        "ok",
        **counted,
        avg_usd=float(np.mean(usd_values)),
        fx_first_day=min(fx_days) if fx_days else None,
        fx_last_day=max(fx_days) if fx_days else None,
    )
