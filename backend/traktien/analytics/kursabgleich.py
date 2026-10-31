"""Kursabgleich mit den amtlichen Kursen der Börsen (ab 1.20.0; Regel ``kursabgleich-1.1`` ab 1.20.1, ``-1.2`` ab 1.20.2).

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
      unbereinigten Kurs der Hauptquelle, übernommen wird nach Umrechnung mit den Splitfaktoren der Notierung. An einem Tag
      ohne Umsatz trägt die Börse den letzten Schlusskurs fort – liegt dazwischen ein Split, steht dieser Wert in der Basis
      des letzten Handelstags und wird mit dessen Faktor umgerechnet (ab 1.1). Gleicht der Kurs der Hauptquelle an den Tagen
      vor einem Split dem *unbereinigten* Kurs der Börse, hat die Hauptquelle den Split nicht angewendet: Dann wird auch ihr
      Kurs an Tagen ohne Kurs der Börse mit dem Splitfaktor umgerechnet (Grund „split_nicht_angewendet“, ab 1.1). Ab 1.2 zählt
      je Tag die nähere Basis statt der exakten Gleichheit (wenig gehandelte Aktien weichen oft um einen Kursschritt ab).
   d. Plausibilität der Zuordnung: an mindestens ``MIN_EQUAL_SHARE`` der gemeinsamen Handelstage gleiche Kurse (bis auf
      Rundung) und kein gleichbleibender Faktor ≠ 1 (Einheit, Gattung, Währung).
   e. Kein Bruch der Bereinigungsbasis am Rand des Zeitraums (ab 1.1): Stehen die Kurse an mindestens ``MIN_COMMON_DAYS``
      aufeinanderfolgenden Handelstagen am Anfang oder Ende des Zeitraums in einem gleichbleibenden Verhältnis ≠ 1 (mindestens
      Faktor ``BASIS_BREAK_MIN``, bei sich bewegenden Kursen) und sonst gleich, hat nur eine Quelle einen Split oder eine
      Kapitalmaßnahme berücksichtigt, die die Splitdaten der Notierung nicht kennen – welche Quelle recht hat, ist ohne die
      Mitteilung der Börse nicht entscheidbar: nichts übernommen.
2. *Abdeckung* – die Börse liefert für mindestens ``MIN_COVERAGE`` der Kurstage der Hauptquelle im Rechenzeitraum einen Wert.
   Sonst wird nichts übernommen: Ein Wechsel der Quelle mitten im Zeitraum könnte selbst einen Kurssprung erzeugen.
3. *Übernahme* (vergleichbar und abgedeckt): An jedem Tag mit Kurs der Börse gilt der Kurs der Börse (Schlusskurs, dazu
   Eröffnung, Hoch und Tief, soweit veröffentlicht). Handelstage mit Umsatz, die in der Hauptquelle fehlen, werden ergänzt.
   Weicht die Hauptquelle beim Umsatzstatus ab (Börse: kein Umsatz, Hauptquelle: Umsatz – oder umgekehrt), gilt der Umsatz der
   Börse. Tage ohne Kurs der Börse behalten den Kurs der Hauptquelle („nur Hauptquelle“, nicht bestätigt; Ausnahme 1c).
4. *Sprungprüfung* (ab 1.1) – erzeugte die Übernahme in der Kursreihe einen Tagessprung um mehr als Faktor ``JUMP_FACTOR``,
   den die Hauptquelle nicht hat, und liegt er höchstens ``JUMP_SPLIT_DAYS`` Kalendertage neben einem Split, ist die
   Bereinigungsbasis nicht eindeutig: nichts übernommen (eine Quelle darf keinen künstlichen Kurssprung erzeugen).
5. *Nachweis* – jede Änderung mit Tag, bisherigem Wert, Wert der Börse, Quelle und Grund (``Correction``) – ab 1.1 auch die
   Tage, an denen sich nur Nachkommastellen ändern (Grund „nachkommastellen“, ab 1.2 nur an Tagen „rundung“, nicht bei bloßer
   Gleitkommadarstellung); je Notierung die Einordnung aller Tage
   (``DayResult``) und der Grund, falls nichts übernommen wurde.

Toleranz „gleich“: nur Darstellungs- und Rundungsunterschiede – höchstens eine halbe Einheit der letzten Nachkommastelle, mit
der die Börse den Kurs veröffentlicht (bei gröberer Rundung der Hauptquelle deren Stelle). Keine prozentuale Toleranz.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..providers.boersen import OfficialBar, decimals_of_number
from .quality import SplitEvent

RULE_VERSION = "kursabgleich-1.2"
MIN_EQUAL_SHARE = 0.2  # Plausibilität der Zuordnung (1d): Anteil gleicher Kurse an den gemeinsamen Handelstagen
MIN_COVERAGE = 0.95  # Abdeckung (2): Anteil der Kurstage der Hauptquelle mit Kurs der Börse
CONSTANT_FACTOR_SHARE = 0.8  # (1d) so viele Tage mit demselben Verhältnis (±0,5 %) …
CONSTANT_FACTOR_MIN = 0.01  # … das mehr als 1 % von 1 abweicht: Einheit/Gattung/Währung verschieden
CONSTANT_FACTOR_TOL = 0.005  # (1d, 1e) „dasselbe Verhältnis“: ±0,5 %
MIN_COMMON_DAYS = 5
BASIS_BREAK_MIN = 1.2  # (1e) Faktor eines Abschnitts am Rand mindestens 1,2 (bzw. höchstens 1/1,2) – kleinere sind Kursschritte
UNADJUSTED_SHARE = 0.5  # (1c) Hauptquelle ohne Splitbereinigung: an mindestens der Hälfte der Tage vor dem Split …
JUMP_FACTOR = 1.5  # (4) Sprungprüfung: Tagesänderung um mehr als Faktor 1,5 …
JUMP_SPLIT_DAYS = 7  # … höchstens 7 Kalendertage neben einem Split

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
    "split_nicht_angewendet": "Hauptquelle hat einen Split nicht angewendet (ihr Kurs gleicht vor dem Split dem unbereinigten Kurs "
                              "der Börse) – Kurs mit dem Splitfaktor umgerechnet",
    "nachkommastellen": "gleich bis auf Rundung – verwendet wird der Kurs der Börse mit ihren Nachkommastellen (Unterschied "
                        "höchstens eine halbe Einheit der letzten veröffentlichten Stelle)",
    "umsatz_laut_boerse": "Umsatzstatus des Tages laut Börse (Hauptquelle meldete Umsatz an einem Tag ohne Abschluss oder umgekehrt)",
}
# Kurskorrekturen im engeren Sinn (Zählwert „Aktien mit korrigiertem Kurs“); „nachkommastellen“ und „umsatz_laut_boerse“ werden
# getrennt gezählt
PRICE_REASONS = ("amtlicher_schlusskurs", "tag_ohne_umsatz", "fehlender_kurstag", "split_nicht_angewendet")
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
    "basis_bruch": "Bereinigungsbasis wechselt am Rand des Zeitraums: Die Kurse stehen dort mehrere Handelstage in einem "
                   "gleichbleibenden Verhältnis ≠ 1, sonst sind sie gleich – Split oder Kapitalmaßnahme, die nur eine Quelle "
                   "berücksichtigt; ohne Mitteilung der Börse nicht entscheidbar",
    "sprung_am_split": f"die Übernahme erzeugte neben einem Split einen Tagessprung um mehr als Faktor {JUMP_FACTOR:g}, den die "
                       "Hauptquelle nicht hat – Bereinigungsbasis nicht eindeutig",
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
    main_unadjusted: bool = False  # (1c) Hauptquelle hat einen Split im Zeitraum nicht angewendet
    jumps: list[int] = field(default_factory=list)  # (4) Tage mit neuem Sprung neben einem Split

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


def tolerance(official: float, decimals: int | None, main_decimals: int | None = None) -> float:
    """Halbe Einheit der letzten veröffentlichten Nachkommastelle (Rundung, keine prozentuale Toleranz). Rundet die
    Hauptquelle gröber, gilt ihre Stelle – bestimmt aus **allen** Kursen der Notierung (``main_decimals``), nicht aus dem
    einzelnen Wert: 0,18 ist bei einer Reihe mit 0,175 an anderen Tagen keine Rundung von 0,175, sondern ein anderer Kurs."""
    d = decimals if decimals is not None else decimals_of_number(official)
    if d is None:
        d = 6
    if main_decimals is not None and main_decimals < d:
        d = main_decimals
    return 0.5 * 10.0 ** (-d) + 1e-9 * abs(official)


def series_decimals(values) -> int | None:
    """Nachkommastellen, mit denen eine Quelle ihre Kurse führt: die größte Stellenzahl über alle Werte (höchstens 6)."""
    found = [decimals_of_number(float(v), max_decimals=6) for v in values if v is not None and np.isfinite(v) and v > 0]
    found = [d for d in found if d is not None]
    return max(found) if found else None


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
    near = np.abs(arr / med - 1.0) <= CONSTANT_FACTOR_TOL
    return med if float(np.mean(near)) >= CONSTANT_FACTOR_SHARE else None


def basis_break(points: list[tuple[int, float, float]]) -> float | None:
    """(1e) Abschnitt am Anfang oder Ende der gemeinsamen Handelstage (``points``: Tag, Verhältnis Hauptquelle/Börse, Kurs der
    Börse; nach Tag sortiert) mit mindestens ``MIN_COMMON_DAYS`` Tagen, gleichbleibendem Verhältnis (±0,5 %) von mindestens
    Faktor ``BASIS_BREAK_MIN`` und mindestens drei verschiedenen Kursen der Börse (die Kurse bewegen sich, das Verhältnis
    bleibt: andere Bereinigung, kein Kursschritt). Rückgabe: das Verhältnis oder None."""
    n = len(points)
    if n < MIN_COMMON_DAYS:
        return None
    for edge in ("anfang", "ende"):
        seq = points if edge == "anfang" else points[::-1]
        ref = seq[0][1]
        if not (ref >= BASIS_BREAK_MIN or ref <= 1.0 / BASIS_BREAK_MIN):
            continue
        k = 0
        while k < n and abs(seq[k][1] / ref - 1.0) <= CONSTANT_FACTOR_TOL:
            k += 1
        if k >= MIN_COMMON_DAYS and k < n and len({round(p[2], 8) for p in seq[:k]}) >= 3:
            return float(np.median([p[1] for p in seq[:k]]))
    return None


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

    def traded(b: OfficialBar) -> bool:
        return not (b.volume is not None and b.volume == 0)

    def main_raw_of(d: int) -> float:
        k = main_days[d]
        if raw is not None and np.isfinite(raw[k]) and raw[k] > 0:
            return float(raw[k])
        return float(close[k]) * factors[d]

    # Stellenzahl der Hauptquelle aus allen unbereinigten Kursen (Tage nach dem letzten Split: dort ohne Umrechnung)
    main_decimals = series_decimals([main_raw_of(d) for d in main_days if factors[d] == 1.0])
    common = sorted(d for d in main_days if d in off)
    traded_common = [d for d in common if traded(off[d])]

    def tol_of(d: int) -> float:
        b = off[d]
        return tolerance(b.close, b.decimals, main_decimals if factors[d] == 1.0 else None)

    def pairs_for(which: str, only_split_days: bool = False) -> list[tuple[float, float, float]]:
        out = []
        for d in traded_common:
            if only_split_days and factors[d] == 1.0:
                continue  # nach dem letzten Split sind beide Basen gleich – sagt über die Basis nichts
            b = off[d]
            m = main_raw_of(d) if which == "unbereinigt" else float(close[main_days[d]])
            out.append((m, b.close, tol_of(d)))
        return out

    # 1c: Bereinigungsbasis der Börse
    chosen = basis
    if basis == "unbekannt":
        if not split_inside:
            chosen = "unbereinigt"  # ohne Split im Zeitraum sind beide Basen gleich
        elif not pairs_for("unbereinigt", only_split_days=True):
            chosen = "unbereinigt"  # kein gemeinsamer Handelstag vor dem Split: beide Basen an allen Tagen gleich
        else:
            share_raw = _equal_share(pairs_for("unbereinigt", only_split_days=True))
            share_adj = _equal_share(pairs_for("bereinigt", only_split_days=True))
            if share_raw >= MIN_EQUAL_SHARE and share_raw >= 2 * share_adj:
                chosen = "unbereinigt"
            elif share_adj >= MIN_EQUAL_SHARE and share_adj >= 2 * share_raw:
                chosen = "bereinigt"
            else:
                chosen = "unklar"
    result.basis = chosen

    # 1c: Hauptquelle ohne Splitbereinigung – ihr Kurs gleicht vor dem Split dem unbereinigten Kurs der Börse (nur bei einer
    # Börse mit unbereinigten Kursen entscheidbar)
    # Je Tag vor dem Split zählt die nähere Basis (nicht die exakte Gleichheit: bei wenig gehandelten Aktien weicht der Kurs
    # der Hauptquelle oft um einen Kursschritt vom amtlichen ab, auch in derselben Basis)
    main_unadjusted = False
    if chosen == "unbereinigt" and basis == "unbereinigt" and split_inside:
        before = [d for d in traded_common if factors[d] != 1.0]
        if len(before) >= MIN_COMMON_DAYS:
            nearer_raw = nearer_adj = 0
            for d in before:
                as_raw = abs(np.log(float(close[main_days[d]]) / off[d].close))
                as_adj = abs(np.log(main_raw_of(d) / off[d].close))
                nearer_raw += as_raw < as_adj
                nearer_adj += as_adj < as_raw
            main_unadjusted = nearer_raw >= UNADJUSTED_SHARE * len(before) and nearer_raw >= 2 * nearer_adj
    result.main_unadjusted = main_unadjusted

    # 1c: Tage ohne Umsatz – die Börse trägt den letzten Schlusskurs fort; liegt ein Split dazwischen, steht der Wert in der
    # Basis des letzten Handelstags (es sei denn, die Börse hat ihn selbst umgerechnet)
    value_factor: dict[int, float] = {}
    if chosen == "unbereinigt":
        last = None
        for d in sorted(off):
            b = off[d]
            if traded(b):
                last = d
            elif last is not None and factors[last] != factors[d] and _same(b.close, off[last].close, tolerance(off[last].close, off[last].decimals)) is not None:
                value_factor[d] = factors[last]

    def vf(d: int) -> float:
        return value_factor.get(d, factors[d])

    def official_app(d: int) -> float:
        b = off[d]
        return b.close / vf(d) if chosen == "unbereinigt" else b.close

    def main_fixed(d: int) -> float:
        """Kurs der Hauptquelle in der Basis der App (1c: umgerechnet, wenn sie den Split nicht angewendet hat)."""
        c = float(close[main_days[d]])
        return c / factors[d] if (main_unadjusted and factors[d] != 1.0) else c

    def main_cmp(d: int) -> float:
        """Kurs der Hauptquelle in der Basis, in der die Börse den Tag veröffentlicht."""
        if chosen == "bereinigt":
            return main_fixed(d)
        if not main_unadjusted and vf(d) == factors[d]:
            return main_raw_of(d)
        return main_fixed(d) * vf(d)

    # Einordnung aller Tage (auch wenn später nichts übernommen wird)
    points: list[tuple[int, float, float]] = []
    traded_equal = 0
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
            code = "nur_boerse" if traded(b) else "nur_boerse_ohne_umsatz"
            day_results.append(DayResult(d, code, None, official_app(d) if chosen in ("unbereinigt", "bereinigt") else None, b.close, None, b.volume))
        else:
            m_app = float(close[k])
            if chosen in ("unbereinigt", "bereinigt"):
                m_cmp = main_cmp(d)
                same = _same(m_cmp, b.close, tol_of(d))
                if same is None and main_unadjusted and factors[d] != 1.0:
                    # einzelne Tage, an denen die Hauptquelle doch bereinigt meldet: so gleich, wie sie sind
                    as_reported = main_raw_of(d) if vf(d) == factors[d] else float(close[k]) * vf(d)
                    same = _same(as_reported, b.close, tol_of(d))
                    if same is not None:
                        m_cmp = as_reported
                if same is not None:
                    code = same
                elif not traded(b):
                    code = "ohne_umsatz"
                else:
                    code = "abweichend"
                if traded(b):
                    points.append((d, m_cmp / b.close, b.close))
                    traded_equal += same is not None
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

    # 1a–1e: Vergleichbarkeit
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
        result.equal_share = traded_equal / len(traded_common)
        result.factor = constant_factor([r for _, r, _ in points])
        if result.factor is not None:
            reason = "gleichbleibender_faktor"
        elif result.equal_share < MIN_EQUAL_SHARE:
            reason = "zu_wenig_gleiche_tage"
        else:
            broken = basis_break(points)
            if broken is not None:
                result.factor = broken
                reason = "basis_bruch"
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
            if main_unadjusted and r.code == "nur_hauptquelle" and factors[r.day] != 1.0:
                fixed = main_fixed(r.day)
                corrections.append(Correction(r.day, "split_nicht_angewendet", r.main, fixed, float(r.main), r.main_volume, r.main_volume))
            continue
        if r.code in ("abweichend", "ohne_umsatz"):
            corrections.append(Correction(r.day, "tag_ohne_umsatz" if r.code == "ohne_umsatz" else "amtlicher_schlusskurs",
                                          r.main, float(r.official), b.close, r.main_volume, _volume_after(r.main_volume, b.volume)))
        elif r.code == "nur_boerse":
            corrections.append(Correction(r.day, "fehlender_kurstag", None, float(r.official), b.close, None, b.volume))
        elif r.code in ("gleich", "rundung"):
            rounding += r.code == "rundung"
            volume_differs = r.main_volume is not None and b.volume is not None and (r.main_volume > 0) != (b.volume > 0)
            # „gleich“ heißt gleich bis auf Gleitkommadarstellung: kein Eintrag. Geändert ist der Kurs nur an einem Tag mit
            # „rundung“ (andere Nachkommastellen) oder wenn die Hauptquelle den Split nicht angewendet hat
            if main_unadjusted and factors[r.day] != 1.0 and abs(float(r.main) / float(r.official) - 1.0) > 0.01:
                corrections.append(Correction(r.day, "split_nicht_angewendet", r.main, float(r.official), b.close, r.main_volume, _volume_after(r.main_volume, b.volume)))
            elif r.code == "rundung":
                corrections.append(Correction(r.day, "nachkommastellen", r.main, float(r.official), b.close, r.main_volume, _volume_after(r.main_volume, b.volume)))
            if volume_differs:
                corrections.append(Correction(r.day, "umsatz_laut_boerse", r.main, float(r.official), b.close, r.main_volume, b.volume))

    # 4: Sprungprüfung – die Übernahme darf neben einem Split keinen Tagessprung erzeugen, den die Hauptquelle nicht hat
    new_values = {c.day: c.new for c in corrections if c.reason != "umsatz_laut_boerse"}
    split_days = [int(e.day) for e in main.splits if first_day - JUMP_SPLIT_DAYS <= int(e.day) <= last_day + JUMP_SPLIT_DAYS]
    if new_values and split_days:
        before_series = [(d, float(close[k])) for d, k in sorted(main_days.items())]
        after_series = sorted({**dict(before_series), **new_values}.items())
        jump = float(np.log(JUMP_FACTOR))

        def changes(seq):
            return {seq[j][0]: float(np.log(seq[j][1] / seq[j - 1][1])) for j in range(1, len(seq)) if seq[j][1] > 0 and seq[j - 1][1] > 0}

        ca, cb = changes(after_series), changes(before_series)
        result.jumps = [d for d, x in ca.items() if abs(x) > jump and abs(cb.get(d, 0.0)) <= jump
                        and any(abs(d - s) <= JUMP_SPLIT_DAYS for s in split_days)]
        if result.jumps:
            result.status, result.reason = "nicht_vergleichbar", "sprung_am_split"
            return result

    result.corrections = corrections
    result.rounding = rounding
    result.status = "uebernommen" if corrections else "bestaetigt"
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
    ``QUALITY_EXCHANGE_CLOSE`` an jedem Tag mit Kurs der Börse, ``QUALITY_EXCHANGE_ADDED`` an ergänzten Tagen,
    ``QUALITY_SPLIT_FIXED`` an Tagen, deren Kurs der Hauptquelle mit dem Splitfaktor umgerechnet wurde (1c)."""
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
        new_close = float(r.official)
        f = (b.close / new_close) if new_close > 0 else 1.0  # Faktor zwischen veröffentlichtem Wert und Basis der App
        out["close"][k] = new_close
        if "close_raw" in out:
            out["close_raw"][k] = new_close * split_factor(splits, d)
        o = b.open / f if b.open else None
        h = b.high / f if b.high else None
        lo = b.low / f if b.low else None
        if "open" in out:
            if b.volume is not None and b.volume == 0:
                out["open"][k] = out["high"][k] = out["low"][k] = new_close  # kein Abschluss: keine Spanne
            elif o is not None and h is not None and lo is not None:
                out["open"][k], out["high"][k], out["low"][k] = o, max(h, new_close, o), min(lo, new_close, o)
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
    # 1c: Tage ohne Kurs der Börse bei einer Hauptquelle ohne Splitbereinigung – Kerze mit dem Splitfaktor umgerechnet
    for c in result.corrections:
        if c.reason != "split_nicht_angewendet" or c.day in used or c.old is None or c.new <= 0:
            continue
        k = index.get(int(c.day))
        if k is None:
            continue
        g = float(c.old) / float(c.new)
        out["close"][k] = float(c.new)
        if "close_raw" in out:
            out["close_raw"][k] = float(c.old)
        for name in ("open", "high", "low"):
            if name in out and np.isfinite(out[name][k]):
                out[name][k] = float(out[name][k]) / g
        if "quality" in out:
            out["quality"][k] = int(out["quality"][k]) | QUALITY_SPLIT_FIXED
    return out


# Qualitätsbits der Tageskerzen (repo.QUALITY_CLOSE_FROM_QUOTE = 1)
QUALITY_EXCHANGE_CLOSE = 2  # Schlusskurs der Börse übernommen (Kursabgleich)
QUALITY_EXCHANGE_ADDED = 4  # Kurstag aus dem Archiv der Börse ergänzt
QUALITY_SPLIT_FIXED = 8  # Kurs der Hauptquelle mit dem Splitfaktor umgerechnet (Split dort nicht angewendet, 1c)
