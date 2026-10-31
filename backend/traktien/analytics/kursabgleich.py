"""Kursabgleich mit den amtlichen Kursen der Börsen (ab 1.20.0, Regel ``kursabgleich-1.0``).

**Kursdefinition der App:** Schlusskurs = amtlicher Schlusskurs der Heimatbörse (Referenznotierung) am Handelstag, in der
Notierungswährung, um Aktiensplits und Zusammenlegungen bereinigt, **nicht** um Dividenden bereinigt (Anzeige „ohne
Dividenden“). An einem Tag ohne Umsatz an der Heimatbörse gibt es keinen Abschluss: Es gilt der Wert, den die Börse für den
Tag veröffentlicht, und der Tag zählt als Tag ohne Umsatz.

**Quellen:** Hauptquelle ist Yahoo (alle Notierungen). Wo die Börse bzw. ihr Betreiber ein frei zugängliches Kursarchiv
veröffentlicht (GPW, NewConnect, TMX, Nasdaq-NOCP – ``providers/boersen.py``), ist dieses Archiv die maßgebliche Quelle für
die Kursdefinition. Datenanbieter (z. B. CNBC) sind nur Vergleichsquellen: Sie bestätigen oder widersprechen, ersetzen aber nie
einen Kurs. Keine Mittelwerte, keine Mehrheitsentscheidung.

**Auswahlregel je Notierung** (``reconcile``):

1. *Vergleichbarkeit* – erst wenn alle Punkte erfüllt sind, darf ein Kurs der Börse übernommen werden:
   a. Identität: dieselbe Aktie/Gattung (GPW, NewConnect: ISIN in der Börsendatei; TMX: Kürzel, Börse TSX bzw. TSXV und Name
      der Kursmeldung; Nasdaq: Nasdaq-notiert und dasselbe Kürzel).
   b. Währung bzw. Einheit wie die Notierung der App.
   c. Bereinigungsbasis eindeutig: Die Börse veröffentlicht Kurse wie gehandelt (unbereinigt); verglichen wird mit dem
      unbereinigten Kurs der Hauptquelle, übernommen wird nach Umrechnung mit den Splitfaktoren der Notierung.
   d. Plausibilität der Zuordnung: an mindestens ``MIN_EQUAL_SHARE`` der gemeinsamen Handelstage gleiche Kurse (bis auf
      Rundung) und kein gleichbleibender Faktor ≠ 1 (Einheit, Gattung, Währung).
2. *Abdeckung* – die Börse liefert für mindestens ``MIN_COVERAGE`` der Kurstage der Hauptquelle im Rechenzeitraum einen Wert.
   Sonst wird nichts übernommen: Ein Wechsel der Quelle mitten im Zeitraum könnte selbst einen Kurssprung erzeugen.
3. *Übernahme* (vergleichbar und abgedeckt): An jedem Tag mit Kurs der Börse gilt der Kurs der Börse (Schlusskurs, dazu
   Eröffnung, Hoch und Tief, soweit veröffentlicht). Handelstage mit Umsatz, die in der Hauptquelle fehlen, werden ergänzt.
   Weicht die Hauptquelle beim Umsatzstatus ab (Börse: kein Umsatz, Hauptquelle: Umsatz – oder umgekehrt), gilt der Umsatz der
   Börse. Tage ohne Kurs der Börse behalten den Kurs der Hauptquelle („nur Hauptquelle“, nicht bestätigt).
4. *Nachweis* – jede Änderung mit Tag, bisherigem Wert, Wert der Börse, Quelle und Grund (``Correction``); je Notierung die
   Einordnung aller Tage (``DayResult``) und der Grund, falls nichts übernommen wurde.

Toleranz „gleich“: nur Darstellungs- und Rundungsunterschiede – höchstens eine halbe Einheit der letzten Nachkommastelle, mit
der die Börse den Kurs veröffentlicht (bei gröberer Rundung der Hauptquelle deren Stelle). Keine prozentuale Toleranz.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..providers.boersen import OfficialBar, decimals_of_number
from .quality import SplitEvent

RULE_VERSION = "kursabgleich-1.0"
MIN_EQUAL_SHARE = 0.2  # Plausibilität der Zuordnung (1d): Anteil gleicher Kurse an den gemeinsamen Handelstagen
MIN_COVERAGE = 0.95  # Abdeckung (2): Anteil der Kurstage der Hauptquelle mit Kurs der Börse
CONSTANT_FACTOR_SHARE = 0.8  # (1d) so viele Tage mit demselben Verhältnis (±0,5 %) …
CONSTANT_FACTOR_MIN = 0.01  # … das mehr als 1 % von 1 abweicht: Einheit/Gattung/Währung verschieden
MIN_COMMON_DAYS = 5

KURSDEFINITION = (
    "Amtlicher Schlusskurs der Heimatbörse am Handelstag, in Notierungswährung, um Aktiensplits und Zusammenlegungen "
    "bereinigt, nicht um Dividenden bereinigt. An Tagen ohne Umsatz gilt der Wert, den die Börse für den Tag veröffentlicht."
)

DAY_CODES = {
    "gleich": "Hauptquelle und Börse gleich",
    "rundung": "gleich bis auf Rundung (letzte veröffentlichte Nachkommastelle)",
    "abweichend": "Hauptquelle weicht vom amtlichen Schlusskurs ab (Tag mit Umsatz)",
    "ohne_umsatz": "Tag ohne Umsatz an der Börse: Hauptquelle nennt einen anderen Wert als die Börse",
    "nur_hauptquelle": "nur Hauptquelle – kein Kurs der Börse für den Tag (nicht bestätigt)",
    "nur_boerse": "Handelstag mit Umsatz fehlt in der Hauptquelle",
    "nur_boerse_ohne_umsatz": "Tag ohne Umsatz nur bei der Börse (in der Hauptquelle kein Kurstag)",
}
REASONS = {
    "amtlicher_schlusskurs": "Schlusskurs der Hauptquelle ≠ amtlicher Schlusskurs der Börse",
    "tag_ohne_umsatz": "Tag ohne Umsatz an der Börse: Wert der Börse statt Wert der Hauptquelle",
    "fehlender_kurstag": "Handelstag mit Umsatz fehlte in der Hauptquelle – Kurs der Börse ergänzt",
    "umsatz_laut_boerse": "Umsatzstatus des Tages laut Börse (Hauptquelle meldete Umsatz an einem Tag ohne Abschluss oder umgekehrt)",
}
STATUS_TEXT = {
    "uebernommen": "vergleichbar, abgedeckt – Kurse der Börse übernommen",
    "bestaetigt": "vergleichbar, abgedeckt – keine Abweichung",
    "nicht_vergleichbar": "nicht vergleichbar – nichts übernommen",
    "abdeckung_unvollstaendig": "vergleichbar, aber die Börse deckt den Rechenzeitraum nicht ab – nichts übernommen",
    "ohne_kurse": "Quelle ohne Kurse für die Notierung",
}
NOT_COMPARABLE = {
    "identitaet": "Identität nicht bestätigt (andere Aktie, Gattung oder Börse)",
    "waehrung": "Währung oder Einheit verschieden",
    "basis_unklar": "Bereinigungsbasis nicht eindeutig (Split im Zeitraum)",
    "zu_wenig_gleiche_tage": f"weniger als {MIN_EQUAL_SHARE:.0%} der gemeinsamen Handelstage gleich – Zuordnung nicht plausibel",
    "gleichbleibender_faktor": "gleichbleibender Faktor zwischen den Quellen (Einheit, Gattung oder Währung)",
    "zu_wenig_tage": f"weniger als {MIN_COMMON_DAYS} gemeinsame Handelstage",
}


@dataclass
class ListingInput:
    """Kurse der Hauptquelle einer Notierung (Split-Basis der App) und ihre Splits."""

    days: np.ndarray
    close: np.ndarray  # Split-bereinigt (Basis der App)
    volume: np.ndarray
    open: np.ndarray | None = None
    high: np.ndarray | None = None
    low: np.ndarray | None = None
    close_raw: np.ndarray | None = None  # unbereinigt (aus den Splits rekonstruiert)
    splits: list[SplitEvent] = field(default_factory=list)


@dataclass(frozen=True)
class DayResult:
    day: int
    code: str
    main: float | None  # Hauptquelle, Basis der App
    official: float | None  # Börse, Basis der App
    official_raw: float | None  # Börse, wie veröffentlicht
    main_volume: float | None
    official_volume: float | None


@dataclass(frozen=True)
class Correction:
    day: int
    reason: str
    old: float | None  # bisheriger Schlusskurs (Hauptquelle, Basis der App); None = Tag fehlte
    new: float  # verwendeter Schlusskurs (Basis der App)
    official_raw: float  # Schlusskurs der Börse, wie veröffentlicht
    old_volume: float | None = None
    new_volume: float | None = None


@dataclass
class ListingResult:
    source: str
    status: str
    reason: str | None = None
    basis: str | None = None
    counts: dict = field(default_factory=dict)
    days: list[DayResult] = field(default_factory=list)
    corrections: list[Correction] = field(default_factory=list)
    rounding: int = 0  # Tage, an denen nur die Rundung angeglichen wurde
    equal_share: float | None = None
    coverage: float | None = None
    factor: float | None = None  # gleichbleibender Faktor, falls erkannt

    @property
    def adopted(self) -> bool:
        """Kurse der Börse gelten (auch ohne Abweichung: dann mit Herkunft „Börse“ an jedem Tag mit Kurs der Börse)."""
        return self.status in ("uebernommen", "bestaetigt")

    @property
    def deviating_days(self) -> list[DayResult]:
        return [d for d in self.days if d.code in ("abweichend", "ohne_umsatz", "nur_boerse")]


def split_factor(splits: list[SplitEvent], day: int) -> float:
    """Faktor zwischen unbereinigtem Kurs und Split-Basis der App an ``day``: Produkt der Splits nach dem Tag (wie
    ``providers.yahoo``: ``close_raw[days < event.day] *= factor``)."""
    f = 1.0
    for event in splits:
        if int(event.day) > int(day):
            f *= float(event.factor)
    return f


def tolerance(official: float, decimals: int | None, main_raw: float | None, factor: float) -> float:
    """Halbe Einheit der letzten veröffentlichten Nachkommastelle (Rundung, keine prozentuale Toleranz). Rundet die
    Hauptquelle gröber (nur an Tagen ohne Split-Umrechnung erkennbar), gilt ihre Stelle."""
    d = decimals if decimals is not None else decimals_of_number(official)
    if d is None:
        d = 6
    if main_raw is not None and factor == 1.0:
        dm = decimals_of_number(main_raw, max_decimals=6)
        if dm is not None and dm < d:
            d = dm
    return 0.5 * 10.0 ** (-d) + 1e-9 * abs(official)


def _same(a: float, b: float, tol: float) -> str | None:
    if abs(a - b) <= 1e-7 * max(abs(a), abs(b)):
        return "gleich"
    if abs(a - b) <= tol:
        return "rundung"
    return None


def _equal_share(pairs: list[tuple[float, float, float]]) -> float:
    if not pairs:
        return 0.0
    hits = sum(1 for main, off, tol in pairs if _same(main, off, tol) is not None)
    return hits / len(pairs)


def constant_factor(ratios: list[float]) -> float | None:
    """Gleichbleibendes Verhältnis Hauptquelle/Börse ≠ 1 (Einheit, Gattung, Währung) – sonst None."""
    if len(ratios) < MIN_COMMON_DAYS:
        return None
    arr = np.asarray(ratios, dtype=np.float64)
    med = float(np.median(arr))
    if abs(med - 1.0) <= CONSTANT_FACTOR_MIN:
        return None
    near = np.abs(arr / med - 1.0) <= 0.005
    return med if float(np.mean(near)) >= CONSTANT_FACTOR_SHARE else None


def reconcile(
    source: str,
    main: ListingInput,
    official: dict[int, OfficialBar],
    *,
    first_day: int,
    last_day: int,
    identity_ok: bool = True,
    currency_ok: bool = True,
    basis: str = "unbereinigt",
    min_coverage: float = MIN_COVERAGE,
) -> ListingResult:
    """Ordnet jeden Tag in ``[first_day, last_day]`` ein und entscheidet nach der Auswahlregel (Modulbeschreibung).

    ``basis``: „unbereinigt“ (Börse veröffentlicht Kurse wie gehandelt), „bereinigt“ (Split-Basis wie die App) oder
    „unbekannt“ (wird an den Tagen ermittelt; bei einem Split im Zeitraum muss sie eindeutig sein)."""
    days = np.asarray(main.days, dtype=np.int64)
    close = np.asarray(main.close, dtype=np.float64)
    volume = np.asarray(main.volume, dtype=np.float64) if main.volume is not None else np.full(len(days), np.nan)
    raw = np.asarray(main.close_raw, dtype=np.float64) if main.close_raw is not None else None
    in_range = (days >= first_day) & (days <= last_day) & np.isfinite(close) & (close > 0)
    main_days = {int(d): k for k, d in enumerate(days.tolist()) if in_range[k]}
    off = {int(d): b for d, b in official.items() if first_day <= int(d) <= last_day and b.close > 0}
    result = ListingResult(source=source, status="ohne_kurse")
    if not off:
        result.counts = {"tage_hauptquelle": len(main_days)}
        return result

    factors = {d: split_factor(main.splits, d) for d in set(main_days) | set(off)}
    split_inside = any(f != factors[min(factors)] for f in factors.values()) if factors else False

    def main_raw_of(d: int) -> float:
        k = main_days[d]
        if raw is not None and np.isfinite(raw[k]) and raw[k] > 0:
            return float(raw[k])
        return float(close[k]) * factors[d]

    common = sorted(d for d in main_days if d in off)
    traded_common = [d for d in common if not (off[d].volume is not None and off[d].volume == 0)]

    def pairs_for(which: str) -> list[tuple[float, float, float]]:
        out = []
        for d in traded_common:
            b = off[d]
            if which == "unbereinigt":
                m = main_raw_of(d)
                out.append((m, b.close, tolerance(b.close, b.decimals, m, factors[d])))
            else:
                m = float(close[main_days[d]])
                out.append((m, b.close, tolerance(b.close, b.decimals, m, factors[d])))
        return out

    # 1c: Bereinigungsbasis
    chosen = basis
    if basis == "unbekannt":
        if not split_inside:
            chosen = "unbereinigt"  # ohne Split im Zeitraum sind beide Basen gleich
        else:
            share_raw, share_adj = _equal_share(pairs_for("unbereinigt")), _equal_share(pairs_for("bereinigt"))
            if share_raw >= MIN_EQUAL_SHARE and share_raw >= 2 * share_adj:
                chosen = "unbereinigt"
            elif share_adj >= MIN_EQUAL_SHARE and share_adj >= 2 * share_raw:
                chosen = "bereinigt"
            else:
                chosen = "unklar"
    result.basis = chosen

    def official_app(d: int) -> float:
        b = off[d]
        return b.close / factors[d] if chosen == "unbereinigt" else b.close

    # Einordnung aller Tage (auch wenn später nichts übernommen wird)
    pairs = pairs_for(chosen) if chosen in ("unbereinigt", "bereinigt") else []
    ratios: list[float] = []
    day_results: list[DayResult] = []
    counts = {code: 0 for code in DAY_CODES}
    for d in sorted(set(main_days) | set(off)):
        b = off.get(d)
        k = main_days.get(d)
        m_vol = float(volume[k]) if k is not None and np.isfinite(volume[k]) else None
        if b is None:
            code = "nur_hauptquelle"
            day_results.append(DayResult(d, code, float(close[k]), None, None, m_vol, None))
        elif k is None:
            code = "nur_boerse_ohne_umsatz" if (b.volume is not None and b.volume == 0) else "nur_boerse"
            day_results.append(DayResult(d, code, None, official_app(d) if chosen in ("unbereinigt", "bereinigt") else None, b.close, None, b.volume))
        else:
            m_app = float(close[k])
            if chosen in ("unbereinigt", "bereinigt"):
                m_cmp = main_raw_of(d) if chosen == "unbereinigt" else m_app
                same = _same(m_cmp, b.close, tolerance(b.close, b.decimals, m_cmp, factors[d]))
                if same is not None:
                    code = same
                elif b.volume is not None and b.volume == 0:
                    code = "ohne_umsatz"
                else:
                    code = "abweichend"
                if not (b.volume is not None and b.volume == 0):
                    ratios.append(m_cmp / b.close)
                day_results.append(DayResult(d, code, m_app, official_app(d), b.close, m_vol, b.volume))
            else:
                code = "abweichend"
                day_results.append(DayResult(d, code, m_app, None, b.close, m_vol, b.volume))
        counts[code] += 1
    result.days = day_results
    counts["tage_hauptquelle"] = len(main_days)
    counts["tage_boerse"] = len(off)
    counts["gemeinsam_mit_umsatz"] = len(traded_common)
    result.counts = counts
    result.coverage = (len(common) / len(main_days)) if main_days else 0.0

    # 1a, 1b, 1c, 1d: Vergleichbarkeit
    reason = None
    if not identity_ok:
        reason = "identitaet"
    elif not currency_ok:
        reason = "waehrung"
    elif chosen == "unklar":
        reason = "basis_unklar"
    elif len(traded_common) < MIN_COMMON_DAYS:
        reason = "zu_wenig_tage"
    else:
        result.equal_share = _equal_share(pairs)
        result.factor = constant_factor(ratios)
        if result.factor is not None:
            reason = "gleichbleibender_faktor"
        elif result.equal_share < MIN_EQUAL_SHARE:
            reason = "zu_wenig_gleiche_tage"
    if reason is not None:
        result.status, result.reason = "nicht_vergleichbar", reason
        return result

    # 2: Abdeckung
    if result.coverage < min_coverage:
        result.status, result.reason = "abdeckung_unvollstaendig", f"{result.coverage:.1%} der Kurstage mit Kurs der Börse"
        return result

    # 3: Übernahme
    corrections: list[Correction] = []
    rounding = 0
    for r in day_results:
        b = off.get(r.day)
        if b is None:
            continue
        if r.code in ("abweichend", "ohne_umsatz"):
            corrections.append(Correction(r.day, "tag_ohne_umsatz" if r.code == "ohne_umsatz" else "amtlicher_schlusskurs",
                                          r.main, float(r.official), b.close, r.main_volume, _volume_after(r.main_volume, b.volume)))
        elif r.code == "nur_boerse":
            corrections.append(Correction(r.day, "fehlender_kurstag", None, float(r.official), b.close, None, b.volume))
        elif r.code in ("gleich", "rundung"):
            rounding += r.code == "rundung"
            if r.main_volume is not None and b.volume is not None and (r.main_volume > 0) != (b.volume > 0):
                corrections.append(Correction(r.day, "umsatz_laut_boerse", r.main, float(r.official), b.close, r.main_volume, b.volume))
    result.corrections = corrections
    result.rounding = rounding
    result.status = "uebernommen" if (corrections or rounding) else "bestaetigt"
    return result


def _volume_after(main_volume: float | None, official_volume: float | None) -> float | None:
    """Umsatz nach der Übernahme: der Umsatz der Hauptquelle, außer der Umsatzstatus weicht von der Börse ab."""
    if official_volume is None:
        return main_volume
    if main_volume is None or (main_volume > 0) != (official_volume > 0):
        return official_volume
    return main_volume


def apply(bars: dict[str, np.ndarray], result: ListingResult, official: dict[int, OfficialBar], splits: list[SplitEvent]) -> dict[str, np.ndarray]:
    """Kurse der Börse in die Tageskerzen der Hauptquelle übernehmen (Status „uebernommen“ oder „bestaetigt“). ``bars`` wie
    ``repo.load_bars`` (days, open, high, low, close, close_raw, volume, quality); Rückgabe: neue Arrays, Qualitätsbit
    ``QUALITY_EXCHANGE_CLOSE`` an jedem Tag mit Kurs der Börse, ``QUALITY_EXCHANGE_ADDED`` an ergänzten Tagen."""
    if not result.adopted:
        return bars
    days = np.asarray(bars["days"], dtype=np.int64)
    used = {r.day: r for r in result.days if r.official is not None and r.code in ("gleich", "rundung", "abweichend", "ohne_umsatz", "nur_boerse")}
    added = sorted(d for d, r in used.items() if r.code == "nur_boerse")
    out = {k: np.array(v, copy=True) for k, v in bars.items()}
    if added:
        all_days = np.union1d(days, np.asarray(added, dtype=np.int64))
        pos = np.searchsorted(all_days, days)
        grown = {}
        for k, v in out.items():
            if k == "days":
                grown[k] = all_days
                continue
            fill = 0 if v.dtype.kind in "iu" else np.nan
            arr = np.full(len(all_days), fill, dtype=v.dtype)
            arr[pos] = v
            grown[k] = arr
        out = grown
        days = all_days
    volume_after = {c.day: c.new_volume for c in result.corrections}
    index = {int(d): k for k, d in enumerate(days.tolist())}
    for d, r in used.items():
        k = index.get(d)
        if k is None:
            continue
        b = official[d]
        f = split_factor(splits, d) if result.basis == "unbereinigt" else 1.0
        new_close = float(r.official)
        out["close"][k] = new_close
        if "close_raw" in out:
            out["close_raw"][k] = b.close if result.basis == "unbereinigt" else new_close * split_factor(splits, d)
        o = b.open / f if b.open else None
        h = b.high / f if b.high else None
        lo = b.low / f if b.low else None
        if "open" in out:
            if o is not None and h is not None and lo is not None:
                out["open"][k], out["high"][k], out["low"][k] = o, max(h, new_close, o), min(lo, new_close, o)
            elif b.volume is not None and b.volume == 0:
                out["open"][k] = out["high"][k] = out["low"][k] = new_close
            else:
                hi = out["high"][k]
                lw = out["low"][k]
                out["high"][k] = max(hi, new_close) if np.isfinite(hi) else new_close
                out["low"][k] = min(lw, new_close) if np.isfinite(lw) else new_close
                if not np.isfinite(out["open"][k]):
                    out["open"][k] = new_close
        if d in volume_after and volume_after[d] is not None:
            out["volume"][k] = float(volume_after[d])
        elif r.code == "nur_boerse" and b.volume is not None:
            out["volume"][k] = float(b.volume)
        if "quality" in out:
            out["quality"][k] = int(out["quality"][k]) | QUALITY_EXCHANGE_CLOSE | (QUALITY_EXCHANGE_ADDED if r.code == "nur_boerse" else 0)
    return out


# Qualitätsbits der Tageskerzen (repo.QUALITY_CLOSE_FROM_QUOTE = 1)
QUALITY_EXCHANGE_CLOSE = 2  # Schlusskurs der Börse übernommen (Kursabgleich)
QUALITY_EXCHANGE_ADDED = 4  # Kurstag aus dem Archiv der Börse ergänzt
