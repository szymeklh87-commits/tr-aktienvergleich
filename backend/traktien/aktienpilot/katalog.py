"""Zentraler Kennzahlenkatalog (Abschnitte 31.8 und 32 des Auftrags).

Jede Analysegröße, die eine Regel verwenden darf, ist hier **genau einmal** definiert: stabile ID, deutscher Name, Erklärung,
Datentyp, Einheit, Parameter mit zulässigen Werten, erlaubte Operatoren und Rollen, Quelle, Methodenversion, Aufwärmphase,
Regel für fehlende Werte und Verfügbarkeit (historischer Test, Vorwärts-PAPER, Anzeige). Die Werte kommen aus **derselben**
Berechnung wie Rangliste, Chart und Bericht:

* Lineal-Kennzahlen (Rendite, R², Steigung, Rückgang, Score, Rang, Häufigkeiten, Gruppe B) lesen die Felder der
  ``SnapshotComputation`` des Rechenkerns (``analytics.engine``) bzw. rufen ``analytics.frequency.aggregate_frequency`` auf –
  genau die Funktionen, aus denen die App-Daten geschrieben werden. Keine Zweitformel, keine eigene Rundung.
* Indikatoren der Strategien (Durchschnitte, RSI, ATR, Hochs, Volumenfaktor, Log-Regression S1) kommen aus
  ``aktienpilot.indikatoren`` auf den abgeschlossenen Tageskerzen bis zum Entscheidungstag.
* Depotwerte (Gewinn der Position, Haltedauer, Gewicht) liefert der Spielgeld-Motor für das jeweils bewertete Depot.

Fehlt ein Wert, ist er ``NaN`` – eine Bedingung darauf ist „nicht prüfbar“ (nie automatisch wahr oder 0). Werte, die nur
rückblickend bekannt sind, stehen mit ``rueckblickend=True`` im Katalog und sind für Regeln gesperrt; Werte ohne historische
Zeitreihe sind ``backtest="nur_vorwaerts"``.

Der Katalog wird aus den geladenen Konfigurationen gebaut (``katalog(method, cfg)``): Fenstergrenzen, Gewichtungen, Mindestzahl
der Beobachtungen für R² usw. stehen nur in ``config`` – keine zweiten Standardwerte (Abschnitt 32.1). ``katalog_json`` liefert
dieselben Definitionen für die App (Datei ``app/src/generated/katalog.json``, deren Aktualität ein Test prüft).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Callable

import numpy as np

from ..analytics.codes import RETURN_PUBLISHABLE, TREND_ELIGIBLE, InstrumentWarning, WindowWarning
from ..config import CANONICAL_WEIGHTS, MethodConfig
from . import indikatoren as ind

KATALOG_VERSION = "kennzahlenkatalog-1"

OPERATOREN_ZAHL = (">", ">=", "<", "<=", "==", "!=", "zwischen")
OPERATOREN_REIHE = OPERATOREN_ZAHL + ("gekreuzt_aufwaerts", "gekreuzt_abwaerts")
OPERATOREN_BOOL = ("ist_wahr", "ist_falsch")
OPERATOREN_KATEGORIE = ("in", "nicht_in")
OPERATOREN_RANG = ("<=", "<", "==", ">", ">=", "zwischen", "neu_eingetreten", "verlassen")

ROLLEN_ALLE = ("filter", "sortierung", "kapital", "ausstieg")
ROLLEN_FILTER = ("filter", "ausstieg")

TOP_K = (1, 3, 10)
POLITIKEN = ("native", "common_trend")
GRUPPEN = ("A", "B")


class KatalogFehler(ValueError):
    """Ungültige Kennzahl oder ungültiger Parameter (Meldung auf Deutsch für Editor und Protokoll)."""


@dataclass(frozen=True)
class Param:
    name: str
    art: str  # ganzzahl | zahl | auswahl | gewichte | bereich
    erklaerung: str
    minimum: float | None = None
    maximum: float | None = None
    werte: tuple = ()
    standard: Any = None

    def pruefen(self, wert: Any) -> Any:
        """Wert prüfen und normalisiert zurückgeben (Fehler mit verständlichem Text)."""
        if self.art == "ganzzahl":
            if isinstance(wert, bool) or not isinstance(wert, (int, float)) or float(wert) != int(wert):
                raise KatalogFehler(f"„{self.name}“ muss eine ganze Zahl sein")
            wert = int(wert)
            self._grenzen(wert)
            return wert
        if self.art == "zahl":
            if isinstance(wert, bool) or not isinstance(wert, (int, float)) or not math.isfinite(float(wert)):
                raise KatalogFehler(f"„{self.name}“ muss eine Zahl sein")
            wert = float(wert)
            self._grenzen(wert)
            return wert
        if self.art == "auswahl":
            if wert not in self.werte:
                raise KatalogFehler(f"„{self.name}“ muss einer der Werte {', '.join(map(str, self.werte))} sein")
            return wert
        if self.art == "gewichte":
            if not isinstance(wert, (list, tuple)) or not wert:
                raise KatalogFehler(f"„{self.name}“: mindestens eine Gewichtung wählen")
            out = sorted({int(w) for w in wert})
            if any(w not in self.werte for w in out):
                raise KatalogFehler(f"„{self.name}“: nur die Gewichtungen {', '.join(map(str, self.werte))}")
            return out
        if self.art == "bereich":
            if not isinstance(wert, dict) or set(wert) != {"von", "bis"}:
                raise KatalogFehler(f"„{self.name}“ braucht „von“ und „bis“")
            von, bis = wert["von"], wert["bis"]
            for v in (von, bis):
                if isinstance(v, bool) or not isinstance(v, int):
                    raise KatalogFehler(f"„{self.name}“: Grenzen müssen ganze Zahlen sein")
            if not (self.minimum <= von <= bis <= self.maximum):
                raise KatalogFehler(f"„{self.name}“: {von}–{bis} liegt nicht in {int(self.minimum)}–{int(self.maximum)} (von ≤ bis)")
            return {"von": int(von), "bis": int(bis)}
        raise KatalogFehler(f"unbekannte Parameterart {self.art}")

    def _grenzen(self, wert: float) -> None:
        if self.minimum is not None and wert < self.minimum:
            raise KatalogFehler(f"„{self.name}“ muss mindestens {_zahl(self.minimum)} sein ({self.erklaerung})")
        if self.maximum is not None and wert > self.maximum:
            raise KatalogFehler(f"„{self.name}“ darf höchstens {_zahl(self.maximum)} sein")

    def as_dict(self) -> dict:
        out = {"name": self.name, "art": self.art, "erklaerung": self.erklaerung}
        if self.minimum is not None:
            out["minimum"] = self.minimum
        if self.maximum is not None:
            out["maximum"] = self.maximum
        if self.werte:
            out["werte"] = list(self.werte)
        if self.standard is not None:
            out["standard"] = self.standard
        return out


def _zahl(x: float) -> str:
    return str(int(x)) if float(x).is_integer() else str(x).replace(".", ",")


@dataclass(frozen=True)
class Kennzahl:
    id: str
    name: str
    erklaerung: str
    typ: str  # zahl | wahrheitswert | kategorie | rang
    einheit: str  # %, Rang, Anzahl, R², Kurs, EUR, USD, Sitzungen, Faktor, Punkte, ""
    gruppe: str  # Bereich im Editor: Lineal, Häufigkeit, Kurs und Technik, Umsatz, Datenqualität, Analysten, Depot, Stammdaten
    parameter: tuple[Param, ...]
    operatoren: tuple[str, ...]
    rollen: tuple[str, ...]
    quelle: str
    methode: str  # Methoden-/Berechnungsversion
    aufwaermphase: str
    fehlwert: str = "nicht prüfbar"
    backtest: str = "ja"  # ja | nur_vorwaerts | nein
    paper: bool = True
    anzeige: str = ""  # Ansicht der App, in der der Wert steht (Route)
    rueckblickend: bool = False
    besser: str = "hoch"  # hoch | niedrig (Sortiervorgabe)
    einheit_vergleich: str = ""  # Werte nur mit gleicher Vergleichsklasse kombinierbar (z. B. „kurs“ für Kurs und Durchschnitt)
    reihe: bool = False  # Wert des Vortags bestimmbar (für „gekreuzt“)
    ansicht_hinweis: str = ""

    def param(self, name: str) -> Param:
        for p in self.parameter:
            if p.name == name:
                return p
        raise KatalogFehler(f"{self.name}: Parameter „{name}“ gibt es nicht")

    def parameter_pruefen(self, werte: dict | None) -> dict:
        werte = dict(werte or {})
        unbekannt = set(werte) - {p.name for p in self.parameter}
        if unbekannt:
            raise KatalogFehler(f"{self.name}: unbekannte Parameter {', '.join(sorted(unbekannt))}")
        out = {}
        for p in self.parameter:
            if p.name in werte:
                out[p.name] = p.pruefen(werte[p.name])
            elif p.standard is not None:
                out[p.name] = p.pruefen(p.standard)
            else:
                raise KatalogFehler(f"{self.name}: Parameter „{p.name}“ fehlt")
        return out

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "erklaerung": self.erklaerung,
            "typ": self.typ,
            "einheit": self.einheit,
            "gruppe": self.gruppe,
            "parameter": [p.as_dict() for p in self.parameter],
            "operatoren": list(self.operatoren),
            "rollen": list(self.rollen),
            "quelle": self.quelle,
            "methode": self.methode,
            "aufwaermphase": self.aufwaermphase,
            "fehlwert": self.fehlwert,
            "backtest": self.backtest,
            "paper": self.paper,
            "anzeige": self.anzeige,
            "rueckblickend": self.rueckblickend,
            "besser": self.besser,
            "vergleichsklasse": self.einheit_vergleich,
            "reihe": self.reihe,
            "hinweis": self.ansicht_hinweis,
        }


# --------------------------------------------------------------------------------------------- Kontext der Auswertung


@dataclass
class Kontext:
    """Alles, was eine Regel am Entscheidungstag lesen darf – nur Daten bis einschließlich ``tag``.

    ``comp`` ist die Snapshot-Berechnung des Rechenkerns für diesen Stichtag (im täglichen Lauf dieselbe, die veröffentlicht
    wird; im historischen Test neu mit dem Stand bis ``tag`` gerechnet). ``markt`` enthält die Tageskerzen (``Market``) und
    wird für Indikatoren auf ``tag`` gekürzt gelesen. ``stamm`` je ISIN: name, branche, land, boerse, waehrung, typ, mic.
    ``fakten`` je ISIN: Analystenwerte mit ihrem Abruftag (nur Werte, die am ``tag`` schon bekannt waren).
    ``depot`` je ISIN: Positionswerte des gerade ausgewerteten Depots. ``vorher``: Kontext der letzten Entscheidung
    (für „neu eingetreten“/„verlassen“ bei Ranglisten), sonst ``None``.
    """

    tag: int
    isins: list[str]
    method: MethodConfig
    comp: Any = None
    markt: Any = None
    cfg: Any = None
    stamm: dict[str, dict] = field(default_factory=dict)
    fakten: dict[str, dict] = field(default_factory=dict)
    depot: dict[str, dict] = field(default_factory=dict)
    vorher: "Kontext | None" = None
    modus: str = "paper"  # paper | backtest | demo
    _cache: dict = field(default_factory=dict, repr=False)
    _index: dict | None = field(default=None, repr=False)

    @property
    def n(self) -> int:
        return len(self.isins)

    @property
    def index(self) -> dict[str, int]:
        if self._index is None:
            self._index = {isin: k for k, isin in enumerate(self.isins)}
        return self._index

    def leer(self) -> np.ndarray:
        return np.full(self.n, np.nan, dtype=np.float64)


# --------------------------------------------------------------------------------------------- Parameter-Bausteine


def _params(method: MethodConfig) -> dict[str, Param]:
    lo, hi = int(method.min_window), int(method.max_window)
    weights = tuple(int(w) for w in method.weights)
    return {
        "fenster": Param("fenster", "ganzzahl", "Kalendertage wie im Lineal-Ranking", lo, hi, standard=30),
        "fenster_r2": Param(
            "fenster", "ganzzahl",
            f"Kalendertage; R² braucht mindestens {method.min_obs_trend} echte Schlusskurse – kürzere Fenster sind nach dem Lineal-Modell nicht zulässig",
            int(method.min_obs_trend), hi, standard=30,
        ),
        "gewicht": Param("gewicht", "auswahl", "Gleichmäßigkeit/Rendite: erste Zahl Gleichmäßigkeit (0/100 = nur Rendite)", werte=weights, standard=60),
        "gewichte": Param("gewichte", "gewichte", "eine oder mehrere der elf Gewichtungen", werte=weights, standard=list(weights)),
        "gruppe": Param("gruppe", "auswahl", "Umsatzgruppe des Lineals: A alle, B nur mit Ø Tagesumsatz über der Schwelle", werte=GRUPPEN, standard="A"),
        "politik": Param(
            "politik", "auswahl",
            "native: 0/100 aus allen Renditewerten; common_trend: alle elf Gewichtungen im gemeinsamen Trend-Vergleichsfeld",
            werte=POLITIKEN, standard="native",
        ),
        "bereich": Param("fenster", "bereich", "Zeiträume von–bis in Kalendertagen", lo, hi, standard={"von": 1, "bis": 30}),
        "k": Param("k", "auswahl", "Platz 1, Top 3 oder Top 10", werte=TOP_K, standard=10),
    }


def _sitzungen(name: str, lo: int, hi: int, std: int, text: str = "abgeschlossene Handelssitzungen (keine Kalendertage)") -> Param:
    return Param(name, "ganzzahl", text, lo, hi, standard=std)


# --------------------------------------------------------------------------------------------- Werte: Lineal-Rechenkern


def _col(ctx: Kontext, h: int) -> int:
    comp = ctx.comp
    try:
        return comp.windows.index(int(h))
    except ValueError as exc:
        raise KatalogFehler(f"Zeitraum {h} Tage ist im Datenstand nicht berechnet") from exc


def _status_mask(ctx: Kontext, h: int, allowed) -> np.ndarray:
    st = ctx.comp.status[:, _col(ctx, h)]
    return np.isin(st, np.array(sorted(int(s) for s in allowed), dtype=st.dtype))


def _need_comp(ctx: Kontext) -> None:
    if ctx.comp is None:
        raise KatalogFehler("Lineal-Kennzahlen brauchen einen berechneten Datenstand")


def _w_rendite(ctx: Kontext, p: dict) -> np.ndarray:
    _need_comp(ctx)
    c = _col(ctx, p["fenster"])
    out = ctx.leer()
    v = _status_mask(ctx, p["fenster"], RETURN_PUBLISHABLE)
    out[v] = ctx.comp.r[v, c] * 100.0
    return out


def _w_r2(ctx: Kontext, p: dict) -> np.ndarray:
    _need_comp(ctx)
    c = _col(ctx, p["fenster"])
    out = ctx.leer()
    v = _status_mask(ctx, p["fenster"], RETURN_PUBLISHABLE) & np.isfinite(ctx.comp.r2[:, c])
    out[v] = ctx.comp.r2[v, c]
    return out


def _w_feld(name: str, scale: float = 1.0):
    def fn(ctx: Kontext, p: dict) -> np.ndarray:
        _need_comp(ctx)
        c = _col(ctx, p["fenster"])
        arr = getattr(ctx.comp, name)[:, c].astype(np.float64)
        out = ctx.leer()
        v = _status_mask(ctx, p["fenster"], RETURN_PUBLISHABLE) & np.isfinite(arr)
        out[v] = arr[v] * scale
        return out

    return fn


def _w_abdeckung(ctx: Kontext, p: dict) -> np.ndarray:
    _need_comp(ctx)
    c = _col(ctx, p["fenster"])
    n_obs = ctx.comp.n_obs[:, c].astype(np.float64)
    n_exp = ctx.comp.n_exp[:, c].astype(np.float64)
    out = ctx.leer()
    ok = n_exp > 0
    out[ok] = 100.0 * n_obs[ok] / n_exp[ok]
    return out


def _w_aufwaertstage(ctx: Kontext, p: dict) -> np.ndarray:
    _need_comp(ctx)
    c = _col(ctx, p["fenster"])
    n_obs = ctx.comp.n_obs[:, c].astype(np.float64)
    ups = ctx.comp.ups[:, c].astype(np.float64)
    out = ctx.leer()
    v = _status_mask(ctx, p["fenster"], RETURN_PUBLISHABLE) & (n_obs >= 2)
    out[v] = 100.0 * ups[v] / (n_obs[v] - 1.0)
    return out


def _w_bewertbar(ctx: Kontext, p: dict) -> np.ndarray:
    _need_comp(ctx)
    return _status_mask(ctx, p["fenster"], TREND_ELIGIBLE).astype(np.float64)


def _ranking(ctx: Kontext, h: int, gewicht: int, gruppe: str, politik: str):
    _need_comp(ctx)
    wr = ctx.comp.rankings.get(int(h))
    if wr is None:
        return None
    if gruppe == "B":
        wr = wr.group_b
        if wr is None:
            return None
    return wr.ranking(politik, int(gewicht))


def _rank_array(ctx: Kontext, h: int, gewicht: int, gruppe: str, politik: str) -> tuple[np.ndarray, np.ndarray]:
    key = ("rang", h, gewicht, gruppe, politik)
    hit = ctx._cache.get(key)
    if hit is not None:
        return hit
    ranks = ctx.leer()
    scores = ctx.leer()
    ranking = _ranking(ctx, h, gewicht, gruppe, politik)
    if ranking is not None and ranking.size:
        order = np.asarray(ranking.order, dtype=np.int64)
        ranks[order] = np.arange(1, len(order) + 1, dtype=np.float64)
        scores[order] = np.asarray(ranking.scores, dtype=np.float64)
    ctx._cache[key] = (ranks, scores)
    return ranks, scores


def _w_rang(ctx: Kontext, p: dict) -> np.ndarray:
    return _rank_array(ctx, p["fenster"], p["gewicht"], p["gruppe"], p["politik"])[0].copy()


def _w_score(ctx: Kontext, p: dict) -> np.ndarray:
    return _rank_array(ctx, p["fenster"], p["gewicht"], p["gruppe"], p["politik"])[1].copy()


def _frequency(ctx: Kontext, p: dict):
    from ..analytics.frequency import aggregate_frequency

    _need_comp(ctx)
    windows = range(p["fenster"]["von"], p["fenster"]["bis"] + 1)
    key = ("haeufigkeit", p["gruppe"], p["politik"], tuple(p["gewichte"]), windows.start, windows.stop)
    hit = ctx._cache.get(key)
    if hit is not None:
        return hit
    comp = ctx.comp
    if p["gruppe"] == "B":
        if any(comp.rankings[h].group_b is None for h in windows):
            raise KatalogFehler("Gruppe B ist in diesem Datenstand nicht berechnet")
        source = {h: comp.rankings[h].group_b for h in windows}
    else:
        source = {h: comp.rankings[h] for h in windows}
    end_days = comp.end_day if len(getattr(comp, "end_day", ())) and np.any(comp.end_day != comp.cutoff_day) else None
    result = aggregate_frequency(
        source, policy=p["politik"], weights=p["gewichte"], window_days=list(windows), top_k=10,
        r_matrix=comp.r, start_matrix=comp.start_day, cutoff_day=comp.cutoff_day, isin_of=comp.isin_of, end_days=end_days,
    )
    # Alle Aktien mit Rang in mindestens einer Zelle: A_i > 0 (auch ohne Top-10-Treffer); die Zählung entspricht exakt der
    # veröffentlichten Häufigkeitsliste (gleiche Funktion, gleiche Zellen).
    entries = {e.idx: e for e in result.entries}
    avail = np.zeros(ctx.n, dtype=np.float64)
    n = {1: np.zeros(ctx.n), 3: np.zeros(ctx.n), 10: np.zeros(ctx.n)}
    hk = {1: np.zeros(ctx.n), 3: np.zeros(ctx.n), 10: np.zeros(ctx.n)}
    wk = {1: np.zeros(ctx.n), 3: np.zeros(ctx.n), 10: np.zeros(ctx.n)}
    for h in windows:
        for w in p["gewichte"]:
            ranking = source[h].ranking(p["politik"], w)
            if ranking.size:
                avail[np.asarray(ranking.order, dtype=np.int64)] += 1
    hits: dict[int, dict[int, set]] = {1: {}, 3: {}, 10: {}}
    for idx, e in entries.items():
        n[1][idx], n[3][idx], n[10][idx] = e.n1, e.n3, e.n10
        for occ in e.occurrences:
            for k in TOP_K:
                if occ.rank <= k:
                    hits[k].setdefault(idx, set()).add((occ.h, occ.weight))
    for k in TOP_K:
        for idx, cells in hits[k].items():
            hk[k][idx] = len({h for h, _ in cells})
            wk[k][idx] = len({w for _, w in cells})
    out = {"A": avail, "E": float(result.valid_cells), "N": n, "H": hk, "W": wk, "zellen": result.theoretical_cells}
    ctx._cache[key] = out
    return out


def _w_haeufigkeit(ctx: Kontext, p: dict) -> np.ndarray:
    f = _frequency(ctx, p)
    out = f["N"][p["k"]].copy()
    out[f["A"] == 0] = np.nan  # ohne einen einzigen Rang: nicht auswertbar (nicht 0 Treffer)
    return out


def _w_zellen(ctx: Kontext, p: dict) -> np.ndarray:
    f = _frequency(ctx, p)
    return f["A"].copy()


def _w_listen(ctx: Kontext, p: dict) -> np.ndarray:
    f = _frequency(ctx, p)
    return np.full(ctx.n, f["E"], dtype=np.float64)


def _w_zeitraeume(ctx: Kontext, p: dict) -> np.ndarray:
    f = _frequency(ctx, p)
    out = f["H"][p["k"]].copy()
    out[f["A"] == 0] = np.nan
    return out


def _w_gewichtungen(ctx: Kontext, p: dict) -> np.ndarray:
    f = _frequency(ctx, p)
    out = f["W"][p["k"]].copy()
    out[f["A"] == 0] = np.nan
    return out


def _w_trefferanteil(ctx: Kontext, p: dict) -> np.ndarray:
    f = _frequency(ctx, p)
    out = ctx.leer()
    ok = f["A"] > 0
    out[ok] = 100.0 * f["N"][p["k"]][ok] / f["A"][ok]
    return out


def _w_gruppe_b(ctx: Kontext, p: dict) -> np.ndarray:
    _need_comp(ctx)
    liquid = np.asarray(ctx.comp.liquid, dtype=bool)
    if len(liquid) != ctx.n:
        return ctx.leer()
    return liquid.astype(np.float64)


def _w_umsatz(ctx: Kontext, p: dict) -> np.ndarray:
    _need_comp(ctx)
    out = ctx.leer()
    for k, t in enumerate(ctx.comp.turnover or ()):
        if t is not None and t.determined:
            out[k] = float(t.avg_usd)
    return out


def _w_fensterwarnung(bit: int):
    def fn(ctx: Kontext, p: dict) -> np.ndarray:
        _need_comp(ctx)
        c = _col(ctx, p["fenster"])
        flags = ctx.comp.wflags[:, c].astype(np.int64)
        return ((flags >> int(bit)) & 1).astype(np.float64)

    return fn


def _w_instrumentwarnung(bit: int):
    def fn(ctx: Kontext, p: dict) -> np.ndarray:
        _need_comp(ctx)
        flags = np.asarray(ctx.comp.warnings, dtype=np.int64)
        return ((flags >> int(bit)) & 1).astype(np.float64)

    return fn


# --------------------------------------------------------------------------------------------- Werte: Tageskerzen


def _series(ctx: Kontext, isin: str):
    if ctx.markt is None:
        return None
    return ctx.markt.series.get(isin)


def _per_series(ctx: Kontext, key: tuple, fn: Callable[[Any, int], float]) -> np.ndarray:
    """Wert je Aktie aus ihren Kerzen bis ``ctx.tag`` (``fn(series, k)`` mit k = Index der letzten Kerze ≤ tag)."""
    hit = ctx._cache.get(key)
    if hit is not None:
        return hit
    out = ctx.leer()
    if ctx.markt is not None:
        for i, isin in enumerate(ctx.isins):
            s = ctx.markt.series.get(isin)
            if s is None:
                continue
            k = s.upto(ctx.tag)
            if k < 0:
                continue
            try:
                v = fn(s, k)
            except (ValueError, ZeroDivisionError, FloatingPointError):
                v = math.nan
            out[i] = v if v is not None and math.isfinite(v) else math.nan
    ctx._cache[key] = out
    return out


def _close_upto(s, k: int) -> np.ndarray:
    return s.close[: k + 1]


def _w_kurs(ctx: Kontext, p: dict) -> np.ndarray:
    return _per_series(ctx, ("kurs",), lambda s, k: float(s.close[k]) * s.unit_factor).copy()


def _w_kurs_eur(ctx: Kontext, p: dict) -> np.ndarray:
    def fn(s, k):
        rate = ctx.markt.eur_rate(s.currency, ctx.tag)
        return math.nan if rate is None else float(s.close[k]) * s.unit_factor * rate

    return _per_series(ctx, ("kurs_eur",), fn).copy()


def _w_tagesaenderung(ctx: Kontext, p: dict) -> np.ndarray:
    def fn(s, k):
        if k < 1 or not (s.close[k - 1] > 0):
            return math.nan
        return 100.0 * (s.close[k] / s.close[k - 1] - 1.0)

    return _per_series(ctx, ("tagesaenderung",), fn).copy()


def _sma_last(close: np.ndarray, n: int, offset: int = 0) -> float:
    end = len(close) - offset
    if end < n:
        return math.nan
    window = close[end - n : end]
    if not np.all(np.isfinite(window)):
        return math.nan
    return float(window.mean())


def _w_ma(ctx: Kontext, p: dict) -> np.ndarray:
    n = p["sitzungen"]
    return _per_series(ctx, ("ma", n), lambda s, k: _sma_last(_close_upto(s, k), n) * s.unit_factor).copy()


def _w_ma_vortag(ctx: Kontext, p: dict) -> np.ndarray:
    n = p["sitzungen"]
    return _per_series(ctx, ("ma-1", n), lambda s, k: _sma_last(_close_upto(s, k), n, 1) * s.unit_factor).copy()


def _w_abstand_ma(ctx: Kontext, p: dict) -> np.ndarray:
    n = p["sitzungen"]

    def fn(s, k):
        m = _sma_last(_close_upto(s, k), n)
        return 100.0 * (s.close[k] / m - 1.0) if m > 0 else math.nan

    return _per_series(ctx, ("abstand_ma", n), fn).copy()


def _w_rsi(ctx: Kontext, p: dict) -> np.ndarray:
    n = p["sitzungen"]

    def fn(s, k):
        close = _close_upto(s, k)
        if len(close) < n + 1:
            return math.nan
        return float(ind.rsi(close[-(n * 10 + 1):], n)[-1])

    return _per_series(ctx, ("rsi", n), fn).copy()


def _atr_last(s, k: int, n: int) -> float:
    lo = max(0, k - n * 3)
    high, low, close = s.high[lo : k + 1], s.low[lo : k + 1], s.close[lo : k + 1]
    if len(close) < n + 1 or not (np.all(np.isfinite(high[-n:])) and np.all(np.isfinite(low[-n:]))):
        return math.nan
    return float(ind.atr(high, low, close, n)[-1])


def _w_atr(ctx: Kontext, p: dict) -> np.ndarray:
    n = p["sitzungen"]
    return _per_series(ctx, ("atr", n), lambda s, k: _atr_last(s, k, n) * s.unit_factor).copy()


def _w_atr_pct(ctx: Kontext, p: dict) -> np.ndarray:
    n = p["sitzungen"]

    def fn(s, k):
        a = _atr_last(s, k, n)
        return 100.0 * a / s.close[k] if s.close[k] > 0 else math.nan

    return _per_series(ctx, ("atr_pct", n), fn).copy()


def _w_volatilitaet(ctx: Kontext, p: dict) -> np.ndarray:
    n = p["sitzungen"]

    def fn(s, k):
        close = _close_upto(s, k)
        if len(close) < n + 1:
            return math.nan
        window = close[-(n + 1):]
        if not np.all(window > 0):
            return math.nan
        lr = np.diff(np.log(window))
        return float(np.std(lr, ddof=1) * math.sqrt(ind.TRADING_DAYS_PER_YEAR) * 100.0)

    return _per_series(ctx, ("vola", n), fn).copy()


def _prior_extreme(s, k: int, n: int, high: bool) -> float:
    if k < n:
        return math.nan
    src = s.high if high else s.low
    window = src[k - n : k]
    if not np.all(np.isfinite(window)):
        window = s.close[k - n : k]  # ohne Hoch/Tief: Schlusskurse (konservativ, dokumentiert)
    return float(window.max() if high else window.min())


def _w_hoch(ctx: Kontext, p: dict) -> np.ndarray:
    n = p["sitzungen"]
    return _per_series(ctx, ("hoch", n), lambda s, k: _prior_extreme(s, k, n, True) * s.unit_factor).copy()


def _w_abstand_hoch(ctx: Kontext, p: dict) -> np.ndarray:
    n = p["sitzungen"]

    def fn(s, k):
        h = _prior_extreme(s, k, n, True)
        return 100.0 * (s.close[k] / h - 1.0) if h > 0 else math.nan

    return _per_series(ctx, ("abstand_hoch", n), fn).copy()


def _w_ausbruch(ctx: Kontext, p: dict) -> np.ndarray:
    n = p["sitzungen"]

    def fn(s, k):
        h = _prior_extreme(s, k, n, True)
        return math.nan if not math.isfinite(h) else float(s.close[k] > h)

    return _per_series(ctx, ("ausbruch", n), fn).copy()


def _w_abstand_tief(ctx: Kontext, p: dict) -> np.ndarray:
    n = p["sitzungen"]

    def fn(s, k):
        t = _prior_extreme(s, k, n, False)
        return 100.0 * (s.close[k] / t - 1.0) if t > 0 else math.nan

    return _per_series(ctx, ("abstand_tief", n), fn).copy()


def _w_volumenfaktor(ctx: Kontext, p: dict) -> np.ndarray:
    n = p["sitzungen"]

    def fn(s, k):
        if k < n:
            return math.nan
        prior = s.volume[k - n : k]
        if not np.all(np.isfinite(prior)) or not math.isfinite(s.volume[k]):
            return math.nan  # fehlende Intervalle nicht als 0 auffüllen (Abschnitt 26.3)
        mean = float(prior.mean())
        return float(s.volume[k]) / mean if mean > 0 else math.nan

    return _per_series(ctx, ("volumenfaktor", n), fn).copy()


def _w_log_r2(ctx: Kontext, p: dict) -> np.ndarray:
    n = p["sitzungen"]

    def fn(s, k):
        if k + 1 < n:
            return math.nan
        _, _, r2 = ind.log_regression(s.close, k, n)
        return r2

    return _per_series(ctx, ("log_r2", n), fn).copy()


def _w_log_steigung(ctx: Kontext, p: dict) -> np.ndarray:
    n = p["sitzungen"]

    def fn(s, k):
        if k + 1 < n:
            return math.nan
        _, annual, _ = ind.log_regression(s.close, k, n)
        return annual * 100.0

    return _per_series(ctx, ("log_steigung", n), fn).copy()


def _w_max_luecke(ctx: Kontext, p: dict) -> np.ndarray:
    n = p["sitzungen"]

    def fn(s, k):
        if k < 1:
            return math.nan
        lo = max(1, k - n + 1)
        prev = s.close[lo - 1 : k]
        opn = s.open[lo : k + 1]
        days = s.days[lo : k + 1]
        best = 0.0
        seen = False
        for o, c, d in zip(opn, prev, days):
            if not (math.isfinite(o) and c > 0):
                continue
            seen = True
            if s.split_explained(int(d)):
                continue
            best = max(best, abs(o / c - 1.0))
        return best * 100.0 if seen else math.nan

    return _per_series(ctx, ("max_luecke", n), fn).copy()


def _w_datenalter(ctx: Kontext, p: dict) -> np.ndarray:
    def fn(s, k):
        last = int(s.days[k])
        return float(np.busday_count(_np_day(last), _np_day(ctx.tag)))

    return _per_series(ctx, ("datenalter",), fn).copy()


def _np_day(day: int) -> np.datetime64:
    return np.datetime64("1970-01-01") + np.timedelta64(int(day), "D")


def _w_marktfilter(ctx: Kontext, p: dict) -> np.ndarray:
    """Leitindex der Börse der Aktie über seinem Durchschnitt (Abschnitt 10). Ohne zugeordneten Index: nicht prüfbar."""
    n = p["sitzungen"]
    key = ("marktfilter", n)
    hit = ctx._cache.get(key)
    if hit is not None:
        return hit.copy()
    out = ctx.leer()
    mapping = {}
    if ctx.cfg is not None:
        mapping = dict(ctx.cfg.marktfilter.leitindex)
    states: dict[str, float] = {}
    for i, isin in enumerate(ctx.isins):
        st = ctx.stamm.get(isin) or {}
        symbol = mapping.get(st.get("mic") or "") or mapping.get(st.get("boerse") or "")
        if not symbol or ctx.markt is None:
            continue
        if symbol not in states:
            series = ctx.markt.indices.get(symbol)
            value = math.nan
            if series is not None:
                k = series.upto(ctx.tag)
                if k >= 0:
                    m = _sma_last(series.close[: k + 1], n)
                    value = float(series.close[k] > m) if math.isfinite(m) else math.nan
            states[symbol] = value
        out[i] = states[symbol]
    ctx._cache[key] = out
    return out.copy()


# --------------------------------------------------------------------------------------------- Werte: Stammdaten, Analysten, Depot


def _w_stamm(feld: str):
    def fn(ctx: Kontext, p: dict) -> np.ndarray:
        out = np.empty(ctx.n, dtype=object)
        for i, isin in enumerate(ctx.isins):
            out[i] = (ctx.stamm.get(isin) or {}).get(feld)
        return out

    return fn


def _w_fakt(feld: str, scale: float = 1.0):
    def fn(ctx: Kontext, p: dict) -> np.ndarray:
        out = ctx.leer()
        for i, isin in enumerate(ctx.isins):
            v = (ctx.fakten.get(isin) or {}).get(feld)
            if isinstance(v, (int, float)) and math.isfinite(float(v)):
                out[i] = float(v) * scale
        return out

    return fn


def _w_zielabstand(ctx: Kontext, p: dict) -> np.ndarray:
    """Abstand zum Analystenziel = 100 × (Ziel / Kurs − 1), nur bei gleicher Währung von Ziel und Kurs (Abschnitt 26.8)."""
    out = ctx.leer()
    price = _w_kurs(ctx, {})
    for i, isin in enumerate(ctx.isins):
        f = ctx.fakten.get(isin) or {}
        target = f.get("ziel_mittel")
        cur_t = f.get("ziel_waehrung")
        st = ctx.stamm.get(isin) or {}
        if not (isinstance(target, (int, float)) and target > 0 and price[i] > 0):
            continue
        if cur_t and st.get("waehrung") and cur_t != st.get("waehrung"):
            continue  # unterschiedliche Währung: nicht vergleichbar (keine stille Umrechnung)
        out[i] = 100.0 * (float(target) / price[i] - 1.0)
    return out


def _w_depot(feld: str):
    def fn(ctx: Kontext, p: dict) -> np.ndarray:
        out = ctx.leer()
        for i, isin in enumerate(ctx.isins):
            v = (ctx.depot.get(isin) or {}).get(feld)
            if isinstance(v, (int, float)) and math.isfinite(float(v)):
                out[i] = float(v)
        return out

    return fn


def _w_gehalten(ctx: Kontext, p: dict) -> np.ndarray:
    out = np.zeros(ctx.n, dtype=np.float64)
    for isin, values in ctx.depot.items():
        k = ctx.index.get(isin)
        if k is not None and (values or {}).get("stueck", 0) > 0:
            out[k] = 1.0
    return out


# --------------------------------------------------------------------------------------------- Aufbau des Katalogs


@dataclass(frozen=True)
class Eintrag:
    kennzahl: Kennzahl
    werte: Callable[[Kontext, dict], np.ndarray]
    vortag: Callable[[Kontext, dict], np.ndarray] | None = None


def katalog(method: MethodConfig, cfg: Any = None) -> dict[str, Eintrag]:
    """Alle Kennzahlen mit ihren Berechnungen. ``cfg``: AktienPilot-Konfiguration (Grenzen der Strategieparameter)."""
    P = _params(method)
    mv = method.method_version
    lineal = f"Lineal-Rechenkern {mv} ({method.metrics_version}, {method.ranking_version})"
    freq = f"Häufigkeitszählung {method.frequency_version} ({method.ranking_version})"
    ind_q = "Tageskerzen des Zustands, abgeschlossene Sitzungen bis zum Entscheidungstag (aktienpilot.indikatoren)"
    ind_v = "indikatoren-1"
    fwin = "Fensterlänge + Startsitzung (Rechenkern)"
    L = "Lineal"
    H = "Häufigkeit"
    T = "Kurs und Technik"
    U = "Umsatz"
    Q = "Datenqualität"
    A = "Analysten"
    D = "Depot"
    S = "Stammdaten"
    rank_params = (P["fenster"], P["gewicht"], P["gruppe"], P["politik"])
    freq_params = (P["k"], P["bereich"], P["gewichte"], P["gruppe"], P["politik"])
    freq_params_nok = (P["bereich"], P["gewichte"], P["gruppe"], P["politik"])
    s = _sitzungen

    def k(**kw) -> Kennzahl:
        kw.setdefault("rollen", ROLLEN_ALLE)
        return Kennzahl(**kw)

    eintraege = [
        Eintrag(k(id="rendite", name="Rendite", erklaerung="Kursrendite im Zeitraum (Kalendertage), splitbereinigt in Notierungswährung, ohne Dividenden – wie in der Renditerangliste.",
                  typ="zahl", einheit="%", gruppe=L, parameter=(P["fenster"],), operatoren=OPERATOREN_ZAHL, quelle=lineal, methode=mv,
                  aufwaermphase=fwin, anzeige="#/rendite", einheit_vergleich="prozent"), _w_rendite),
        Eintrag(k(id="r2", name="Gleichmäßigkeit (R²)", erklaerung="Bestimmtheitsmaß der linearen Preisregression des Lineals im Zeitraum (0–1). Unabhängig von der Richtung – für „nur steigend“ zusätzlich Steigung > 0 oder „Lineal-bewertbar“ verwenden. Nicht dieselbe Größe wie die Log-Regression von S1.",
                  typ="zahl", einheit="R²", gruppe=L, parameter=(P["fenster_r2"],), operatoren=OPERATOREN_ZAHL, quelle=lineal, methode=mv,
                  aufwaermphase=f"mindestens {method.min_obs_trend} echte Schlusskurse im Fenster", anzeige="#/rangliste", einheit_vergleich="r2"), _w_r2),
        Eintrag(k(id="steigung", name="Steigung je Sitzung", erklaerung="Steigung der Preisregression des Lineals in % des mittleren Kurses je Sitzung; Vorzeichen = Richtung.",
                  typ="zahl", einheit="% je Sitzung", gruppe=L, parameter=(P["fenster_r2"],), operatoren=OPERATOREN_ZAHL, quelle=lineal, methode=mv,
                  aufwaermphase=f"mindestens {method.min_obs_trend} echte Schlusskurse", anzeige="#/rangliste", einheit_vergleich="steigung"), _w_feld("slope_pct")),
        Eintrag(k(id="rauschen", name="Schwankung um die Gerade", erklaerung="Mittlere Abweichung der Kurse von der Regressionsgeraden in % des mittleren Kurses (kleiner = ruhiger).",
                  typ="zahl", einheit="%", gruppe=L, parameter=(P["fenster_r2"],), operatoren=OPERATOREN_ZAHL, quelle=lineal, methode=mv,
                  aufwaermphase=f"mindestens {method.min_obs_trend} echte Schlusskurse", besser="niedrig", einheit_vergleich="prozent"), _w_feld("noise_pct")),
        Eintrag(k(id="max_rueckgang", name="Größter Rückgang im Zeitraum", erklaerung="Größter Rückgang vom bisherigen Höchststand innerhalb des Fensters (positiv, 25 = −25 %).",
                  typ="zahl", einheit="%", gruppe=L, parameter=(P["fenster"],), operatoren=OPERATOREN_ZAHL, quelle=lineal, methode=mv,
                  aufwaermphase=fwin, besser="niedrig", einheit_vergleich="prozent"), _w_feld("mdd", 100.0)),
        Eintrag(k(id="beobachtungen", name="Echte Schlusskurse im Zeitraum", erklaerung="Zahl der tatsächlich vorhandenen Schlusskurse im Fenster (fehlende Tage werden nicht aufgefüllt).",
                  typ="zahl", einheit="Anzahl", gruppe=Q, parameter=(P["fenster"],), operatoren=OPERATOREN_ZAHL, quelle=lineal, methode=mv,
                  aufwaermphase=fwin, einheit_vergleich="anzahl"), _w_feld("n_obs")),
        Eintrag(k(id="datenabdeckung", name="Datenabdeckung", erklaerung="Vorhandene Schlusskurse im Verhältnis zu den laut Börsenkalender erwarteten Sitzungen.",
                  typ="zahl", einheit="%", gruppe=Q, parameter=(P["fenster"],), operatoren=OPERATOREN_ZAHL, quelle=lineal, methode=mv,
                  aufwaermphase=fwin, einheit_vergleich="prozent"), _w_abdeckung),
        Eintrag(k(id="aufwaertstage", name="Anteil steigender Tage", erklaerung="Anteil der Schlusskursvergleiche im Fenster mit höherem Kurs als am Vortag.",
                  typ="zahl", einheit="%", gruppe=L, parameter=(P["fenster"],), operatoren=OPERATOREN_ZAHL, quelle=lineal, methode=mv,
                  aufwaermphase=fwin, einheit_vergleich="prozent"), _w_aufwaertstage),
        Eintrag(k(id="lineal_bewertbar", name="Lineal-bewertbar (steigend, genug Kurse)", erklaerung="Die Aktie gehört im Zeitraum zur Vergleichsmenge der Aufwärts-Gleichmäßigkeit (Menge U: steigend und genug echte Schlusskurse).",
                  typ="wahrheitswert", einheit="", gruppe=L, parameter=(P["fenster_r2"],), operatoren=OPERATOREN_BOOL, rollen=ROLLEN_FILTER, quelle=lineal,
                  methode=mv, aufwaermphase=f"mindestens {method.min_obs_trend} echte Schlusskurse"), _w_bewertbar),
        Eintrag(k(id="rang", name="Rang in der Lineal-Rangliste", erklaerung="Platz in der veröffentlichten Rangliste für Zeitraum, Gewichtung, Umsatzgruppe und Vergleichsfeld (1 = bester). Ohne Platz: nicht in der Vergleichsmenge.",
                  typ="rang", einheit="Rang", gruppe=L, parameter=rank_params, operatoren=OPERATOREN_RANG, quelle=lineal, methode=mv,
                  aufwaermphase=fwin, anzeige="#/rangliste", besser="niedrig", einheit_vergleich="rang"), _w_rang),
        Eintrag(k(id="score", name="Lineal-Score", erklaerung="Gewichteter Score 0–100 der Rangliste (Gleichmäßigkeit/Rendite als Perzentile, Formel des Rechenkerns).",
                  typ="zahl", einheit="Punkte", gruppe=L, parameter=rank_params, operatoren=OPERATOREN_ZAHL, quelle=lineal, methode=mv,
                  aufwaermphase=fwin, anzeige="#/rangliste", einheit_vergleich="punkte"), _w_score),
        Eintrag(k(id="haeufigkeit", name="Häufigkeit in den Ranglisten", erklaerung="Wie oft die Aktie in den gewählten Zeiträumen und Gewichtungen auf Platz 1, in den Top 3 oder Top 10 steht (je Zelle höchstens einmal). Nenner: auswertbare Zellen A und gültige Listen E. Ähnliche Fenster sind stark abhängig – Treffer sind keine unabhängigen Signale.",
                  typ="zahl", einheit="Anzahl", gruppe=H, parameter=freq_params, operatoren=OPERATOREN_ZAHL, quelle=freq, methode=method.frequency_version,
                  aufwaermphase="wie die Ranglisten", anzeige="#/haeufigkeit", einheit_vergleich="anzahl"), _w_haeufigkeit),
        Eintrag(k(id="auswertbare_zellen", name="Auswertbare Zellen (A)", erklaerung="Zahl der Kombinationen Zeitraum × Gewichtung, in denen die Aktie einen Rang hat.",
                  typ="zahl", einheit="Anzahl", gruppe=H, parameter=freq_params_nok, operatoren=OPERATOREN_ZAHL, quelle=freq, methode=method.frequency_version,
                  aufwaermphase="wie die Ranglisten", anzeige="#/haeufigkeit", einheit_vergleich="anzahl"), _w_zellen),
        Eintrag(k(id="gueltige_listen", name="Gültige Listen (E)", erklaerung="Zahl der gewählten Kombinationen mit mindestens einer bewertbaren Aktie (für alle Aktien gleich).",
                  typ="zahl", einheit="Anzahl", gruppe=H, parameter=freq_params_nok, operatoren=OPERATOREN_ZAHL, rollen=ROLLEN_FILTER, quelle=freq,
                  methode=method.frequency_version, aufwaermphase="wie die Ranglisten", einheit_vergleich="anzahl"), _w_listen),
        Eintrag(k(id="verschiedene_zeitraeume", name="Verschiedene erfolgreiche Zeiträume (H)", erklaerung="In wie vielen verschiedenen Zeiträumen die Aktie mindestens einmal Platz ≤ K erreicht.",
                  typ="zahl", einheit="Anzahl", gruppe=H, parameter=freq_params, operatoren=OPERATOREN_ZAHL, quelle=freq, methode=method.frequency_version,
                  aufwaermphase="wie die Ranglisten", einheit_vergleich="anzahl"), _w_zeitraeume),
        Eintrag(k(id="verschiedene_gewichtungen", name="Verschiedene erfolgreiche Gewichtungen (W)", erklaerung="Mit wie vielen verschiedenen Gewichtungen die Aktie mindestens einmal Platz ≤ K erreicht.",
                  typ="zahl", einheit="Anzahl", gruppe=H, parameter=freq_params, operatoren=OPERATOREN_ZAHL, quelle=freq, methode=method.frequency_version,
                  aufwaermphase="wie die Ranglisten", einheit_vergleich="anzahl"), _w_gewichtungen),
        Eintrag(k(id="trefferanteil", name="Trefferanteil N/A", erklaerung="Treffer (Platz ≤ K) je auswertbarer Zelle der Aktie. Mit Nenner lesen: 100 % bei einer einzigen Zelle ist kein starker Befund.",
                  typ="zahl", einheit="%", gruppe=H, parameter=freq_params, operatoren=OPERATOREN_ZAHL, quelle=freq, methode=method.frequency_version,
                  aufwaermphase="wie die Ranglisten", einheit_vergleich="prozent"), _w_trefferanteil),
        Eintrag(k(id="gruppe_b", name="In Umsatzgruppe B", erklaerung=f"Ø Tagesumsatz der letzten {method.turnover_sessions} Sitzungen mindestens {int(method.turnover_threshold_usd):,} USD (Menge L des Lineals).".replace(",", "."),
                  typ="wahrheitswert", einheit="", gruppe=U, parameter=(), operatoren=OPERATOREN_BOOL, rollen=ROLLEN_FILTER, quelle=lineal,
                  methode=method.turnover_version, aufwaermphase=f"{method.turnover_sessions} Sitzungen"), _w_gruppe_b),
        Eintrag(k(id="tagesumsatz_usd", name="Ø Tagesumsatz (USD)", erklaerung=f"Ø gehandelter Wert je Sitzung über {method.turnover_sessions} Sitzungen in USD (indikativ, EZB-Kurse).",
                  typ="zahl", einheit="USD", gruppe=U, parameter=(), operatoren=OPERATOREN_ZAHL, quelle=lineal, methode=method.turnover_version,
                  aufwaermphase=f"{method.turnover_sessions} Sitzungen, mindestens {method.turnover_min_positive} mit Umsatz", einheit_vergleich="usd"), _w_umsatz),
        Eintrag(k(id="split_im_fenster", name="Split im Zeitraum", erklaerung="Im Fenster liegt ein (geprüfter) Split oder eine Zusammenlegung.",
                  typ="wahrheitswert", einheit="", gruppe=Q, parameter=(P["fenster"],), operatoren=OPERATOREN_BOOL, rollen=ROLLEN_FILTER, quelle=lineal, methode=mv,
                  aufwaermphase=fwin), _w_fensterwarnung(WindowWarning.SPLIT_IM_FENSTER)),
        Eintrag(k(id="impulstag", name="Ein Tag erklärt die Bewegung", erklaerung="Ein einzelner Handelstag erklärt mehr als die Hälfte der Kursbewegung im Fenster.",
                  typ="wahrheitswert", einheit="", gruppe=Q, parameter=(P["fenster"],), operatoren=OPERATOREN_BOOL, rollen=ROLLEN_FILTER, quelle=lineal, methode=mv,
                  aufwaermphase=fwin), _w_fensterwarnung(WindowWarning.IMPULSTAG)),
        Eintrag(k(id="uebernahmemuster", name="Übernahmemuster", erklaerung="Kurssprung von mindestens 15 % an einem Tag, danach kaum Bewegung – typisch für ein Übernahmeangebot.",
                  typ="wahrheitswert", einheit="", gruppe=Q, parameter=(P["fenster"],), operatoren=OPERATOREN_BOOL, rollen=ROLLEN_FILTER, quelle=lineal, methode=mv,
                  aufwaermphase=fwin), _w_fensterwarnung(WindowWarning.UEBERNAHMEMUSTER)),
        Eintrag(k(id="boersenplatz_abweichung", name="Abweichung zum zweiten Börsenplatz", erklaerung="Wertentwicklung oder Endkurs weichen am zweiten Börsenplatz um mehr als 10 % ab.",
                  typ="wahrheitswert", einheit="", gruppe=Q, parameter=(P["fenster"],), operatoren=OPERATOREN_BOOL, rollen=ROLLEN_FILTER, quelle=lineal, methode=method.venue_version,
                  aufwaermphase=fwin), _w_fensterwarnung(WindowWarning.BOERSENPLATZ_ABWEICHUNG)),
        Eintrag(k(id="kurs_der_boerse", name="Kurse durch Kursabgleich ersetzt", erklaerung="Kurse der Hauptquelle wurden nach dem Kursabgleich durch Kurse der Börse ersetzt.",
                  typ="wahrheitswert", einheit="", gruppe=Q, parameter=(), operatoren=OPERATOREN_BOOL, rollen=ROLLEN_FILTER, quelle="Kursabgleich", methode="kursabgleich",
                  aufwaermphase="–"), _w_instrumentwarnung(InstrumentWarning.KURS_DER_BOERSE)),
        Eintrag(k(id="split_in_historie", name="Split in der Kurshistorie", erklaerung="In der geladenen Kurshistorie liegt ein Split.",
                  typ="wahrheitswert", einheit="", gruppe=Q, parameter=(), operatoren=OPERATOREN_BOOL, rollen=ROLLEN_FILTER, quelle=lineal, methode=mv,
                  aufwaermphase="–"), _w_instrumentwarnung(InstrumentWarning.SPLIT_IN_HISTORIE)),
        Eintrag(k(id="otc", name="Nur außerbörslich (OTC) notiert", erklaerung="Referenznotierung ist eine OTC-Notierung.",
                  typ="wahrheitswert", einheit="", gruppe=Q, parameter=(), operatoren=OPERATOREN_BOOL, rollen=ROLLEN_FILTER, quelle=lineal, methode=mv,
                  aufwaermphase="–"), _w_instrumentwarnung(InstrumentWarning.OTC_NOTIERUNG)),
        Eintrag(k(id="kurs", name="Schlusskurs", erklaerung="Letzter abgeschlossener Schlusskurs bis zum Entscheidungstag in der Basiswährung der Notierung (GBp in GBP umgerechnet).",
                  typ="zahl", einheit="Kurs", gruppe=T, parameter=(), operatoren=OPERATOREN_REIHE, quelle=ind_q, methode=ind_v, aufwaermphase="1 Sitzung",
                  einheit_vergleich="kurs", reihe=True), _w_kurs, _vortag_kurs),
        Eintrag(k(id="kurs_eur", name="Schlusskurs in EUR", erklaerung="Schlusskurs umgerechnet mit dem EZB-Referenzkurs des Tages (oder des letzten davor).",
                  typ="zahl", einheit="EUR", gruppe=T, parameter=(), operatoren=OPERATOREN_ZAHL, quelle=ind_q + "; EZB", methode=ind_v, aufwaermphase="1 Sitzung",
                  einheit_vergleich="eur"), _w_kurs_eur),
        Eintrag(k(id="tagesaenderung", name="Tagesänderung (Schluss zu Schluss)", erklaerung="Änderung des letzten Schlusskurses gegenüber dem Schlusskurs der Sitzung davor – kein Intradaywert.",
                  typ="zahl", einheit="%", gruppe=T, parameter=(), operatoren=OPERATOREN_ZAHL, quelle=ind_q, methode=ind_v, aufwaermphase="2 Sitzungen",
                  einheit_vergleich="prozent"), _w_tagesaenderung),
        Eintrag(k(id="ma", name="Gleitender Durchschnitt", erklaerung="Einfacher Durchschnitt der Schlusskurse der letzten n Sitzungen (Kurswert, mit Schlusskurs vergleichbar).",
                  typ="zahl", einheit="Kurs", gruppe=T, parameter=(s("sitzungen", 2, 250, 100),), operatoren=OPERATOREN_REIHE, quelle=ind_q, methode=ind_v,
                  aufwaermphase="n Sitzungen", einheit_vergleich="kurs", reihe=True), _w_ma, _w_ma_vortag),
        Eintrag(k(id="abstand_ma", name="Abstand zum Durchschnitt", erklaerung="100 × (Schlusskurs / Durchschnitt − 1).",
                  typ="zahl", einheit="%", gruppe=T, parameter=(s("sitzungen", 2, 250, 200),), operatoren=OPERATOREN_ZAHL, quelle=ind_q, methode=ind_v,
                  aufwaermphase="n Sitzungen", einheit_vergleich="prozent"), _w_abstand_ma),
        Eintrag(k(id="rsi", name="RSI", erklaerung="Relative-Stärke-Index nach Wilder über n Sitzungen (0–100).",
                  typ="zahl", einheit="Punkte", gruppe=T, parameter=(s("sitzungen", 2, 50, 14),), operatoren=OPERATOREN_ZAHL, quelle=ind_q, methode=ind_v,
                  aufwaermphase="10 × n Sitzungen empfohlen", einheit_vergleich="rsi"), _w_rsi),
        Eintrag(k(id="atr", name="ATR (durchschnittliche Tagesspanne)", erklaerung="Average True Range über n Sitzungen in Kurswährung (Grundlage der Stops).",
                  typ="zahl", einheit="Kurs", gruppe=T, parameter=(s("sitzungen", 5, 50, 14),), operatoren=OPERATOREN_ZAHL, quelle=ind_q, methode=ind_v,
                  aufwaermphase="n + 1 Sitzungen mit Hoch/Tief", einheit_vergleich="kurs"), _w_atr),
        Eintrag(k(id="atr_pct", name="ATR in % des Kurses", erklaerung="ATR im Verhältnis zum Schlusskurs.",
                  typ="zahl", einheit="%", gruppe=T, parameter=(s("sitzungen", 5, 50, 14),), operatoren=OPERATOREN_ZAHL, quelle=ind_q, methode=ind_v,
                  aufwaermphase="n + 1 Sitzungen mit Hoch/Tief", besser="niedrig", einheit_vergleich="prozent"), _w_atr_pct),
        Eintrag(k(id="volatilitaet", name="Volatilität (annualisiert)", erklaerung="Standardabweichung der täglichen Log-Renditen über n Sitzungen × √252.",
                  typ="zahl", einheit="%", gruppe=T, parameter=(s("sitzungen", 5, 250, 60),), operatoren=OPERATOREN_ZAHL, quelle=ind_q, methode=ind_v,
                  aufwaermphase="n + 1 Sitzungen", besser="niedrig", einheit_vergleich="prozent"), _w_volatilitaet),
        Eintrag(k(id="hoch", name="Vorheriges Hoch", erklaerung="Höchster Kurs der n Sitzungen vor dem Entscheidungstag (ohne diesen Tag).",
                  typ="zahl", einheit="Kurs", gruppe=T, parameter=(s("sitzungen", 5, 250, 55),), operatoren=OPERATOREN_ZAHL, quelle=ind_q, methode=ind_v,
                  aufwaermphase="n + 1 Sitzungen", einheit_vergleich="kurs"), _w_hoch),
        Eintrag(k(id="abstand_hoch", name="Abstand zum vorherigen Hoch", erklaerung="100 × (Schlusskurs / vorheriges n-Sitzungen-Hoch − 1); positiv = darüber.",
                  typ="zahl", einheit="%", gruppe=T, parameter=(s("sitzungen", 5, 250, 55),), operatoren=OPERATOREN_ZAHL, quelle=ind_q, methode=ind_v,
                  aufwaermphase="n + 1 Sitzungen", einheit_vergleich="prozent"), _w_abstand_hoch),
        Eintrag(k(id="ausbruch_hoch", name="Schluss über vorherigem Hoch", erklaerung="Schlusskurs liegt über dem höchsten Kurs der n Sitzungen davor (Ausbruch nach Tagesschluss, kein Intradaybefund).",
                  typ="wahrheitswert", einheit="", gruppe=T, parameter=(s("sitzungen", 5, 250, 55),), operatoren=OPERATOREN_BOOL, rollen=ROLLEN_FILTER,
                  quelle=ind_q, methode=ind_v, aufwaermphase="n + 1 Sitzungen"), _w_ausbruch),
        Eintrag(k(id="abstand_tief", name="Abstand zum vorherigen Tief", erklaerung="100 × (Schlusskurs / tiefster Kurs der n Sitzungen davor − 1).",
                  typ="zahl", einheit="%", gruppe=T, parameter=(s("sitzungen", 5, 250, 55),), operatoren=OPERATOREN_ZAHL, quelle=ind_q, methode=ind_v,
                  aufwaermphase="n + 1 Sitzungen", einheit_vergleich="prozent"), _w_abstand_tief),
        Eintrag(k(id="volumenfaktor", name="Volumenfaktor (Tag)", erklaerung="Handelsvolumen des letzten vollständigen Tages geteilt durch das Ø Volumen der n Sitzungen davor (der Tag selbst zählt nicht zum Nenner). Tagesansicht – nicht der 5-/15-Minuten-Faktor.",
                  typ="zahl", einheit="Faktor", gruppe=U, parameter=(s("sitzungen", 5, 60, 20),), operatoren=OPERATOREN_ZAHL, quelle=ind_q, methode=ind_v,
                  aufwaermphase="n + 1 Sitzungen mit Volumen", einheit_vergleich="faktor"), _w_volumenfaktor),
        Eintrag(k(id="log_r2", name="Gleichmäßigkeit der Log-Regression (S1)", erklaerung="R² der Regression des logarithmierten Kurses über n Handelssitzungen (Momentum-Rotation S1). Nicht das R² des Lineals (Preisregression über Kalendertage).",
                  typ="zahl", einheit="R²", gruppe=T, parameter=(s("sitzungen", 20, 90, 60),), operatoren=OPERATOREN_ZAHL, quelle=ind_q, methode=ind_v,
                  aufwaermphase="n Sitzungen", einheit_vergleich="r2"), _w_log_r2),
        Eintrag(k(id="log_steigung_jahr", name="Steigung der Log-Regression (annualisiert)", erklaerung="exp(Steigung × 252) − 1 der Log-Regression über n Sitzungen, in %.",
                  typ="zahl", einheit="%", gruppe=T, parameter=(s("sitzungen", 20, 90, 60),), operatoren=OPERATOREN_ZAHL, quelle=ind_q, methode=ind_v,
                  aufwaermphase="n Sitzungen", einheit_vergleich="prozent"), _w_log_steigung),
        Eintrag(k(id="max_luecke", name="Größte Übernachtlücke", erklaerung="Größte absolute Lücke zwischen Eröffnung und vorherigem Schluss in den letzten n Sitzungen; Tage mit gemeldetem Split zählen nicht.",
                  typ="zahl", einheit="%", gruppe=Q, parameter=(s("sitzungen", 5, 250, 90),), operatoren=OPERATOREN_ZAHL, quelle=ind_q, methode=ind_v,
                  aufwaermphase="n Sitzungen mit Eröffnungskurs", besser="niedrig", einheit_vergleich="prozent"), _w_max_luecke),
        Eintrag(k(id="datenalter", name="Datenalter", erklaerung="Werktage zwischen der letzten Kerze der Aktie und dem Entscheidungstag (Feiertage zählen konservativ mit).",
                  typ="zahl", einheit="Sitzungen", gruppe=Q, parameter=(), operatoren=OPERATOREN_ZAHL, rollen=ROLLEN_FILTER, quelle=ind_q, methode=ind_v,
                  aufwaermphase="–", besser="niedrig", einheit_vergleich="sitzungen"), _w_datenalter),
        Eintrag(k(id="marktfilter", name="Marktfilter: Leitindex über Durchschnitt", erklaerung="Der vorab zugeordnete Leitindex der Börse der Aktie schließt über seinem Durchschnitt der letzten n Sitzungen. Ohne zugeordneten Index: nicht prüfbar.",
                  typ="wahrheitswert", einheit="", gruppe=T, parameter=(s("sitzungen", 20, 250, 200),), operatoren=OPERATOREN_BOOL, rollen=ROLLEN_FILTER,
                  quelle=ind_q + "; Indexkurse", methode=ind_v, aufwaermphase="n Sitzungen des Index"), _w_marktfilter),
        Eintrag(k(id="branche", name="Branche", erklaerung="Branche laut Stammdaten (unbekannt bleibt unbekannt).", typ="kategorie", einheit="", gruppe=S, parameter=(),
                  operatoren=OPERATOREN_KATEGORIE, rollen=ROLLEN_FILTER, quelle="Stammdaten (Kennzahlenabruf)", methode="stammdaten", aufwaermphase="–",
                  backtest="nur_vorwaerts"), _w_stamm("branche")),
        Eintrag(k(id="land", name="Land", erklaerung="Land des Unternehmens laut Stammdaten.", typ="kategorie", einheit="", gruppe=S, parameter=(),
                  operatoren=OPERATOREN_KATEGORIE, rollen=ROLLEN_FILTER, quelle="Stammdaten", methode="stammdaten", aufwaermphase="–", backtest="nur_vorwaerts"), _w_stamm("land")),
        Eintrag(k(id="boerse", name="Börse der Referenznotierung", erklaerung="Börse (MIC), deren Kurse die App verwendet.", typ="kategorie", einheit="", gruppe=S, parameter=(),
                  operatoren=OPERATOREN_KATEGORIE, rollen=ROLLEN_FILTER, quelle="Stammdaten", methode="stammdaten", aufwaermphase="–"), _w_stamm("mic")),
        Eintrag(k(id="waehrung", name="Notierungswährung", erklaerung="Basiswährung der Referenznotierung.", typ="kategorie", einheit="", gruppe=S, parameter=(),
                  operatoren=OPERATOREN_KATEGORIE, rollen=ROLLEN_FILTER, quelle="Stammdaten", methode="stammdaten", aufwaermphase="–"), _w_stamm("waehrung")),
        Eintrag(k(id="kursziel_abstand", name="Abstand zum Analystenziel", erklaerung="100 × (Ø Analystenziel / Schlusskurs − 1), nur bei gleicher Währung. Fremde Einschätzung, keine erwartete Rendite.",
                  typ="zahl", einheit="%", gruppe=A, parameter=(), operatoren=OPERATOREN_ZAHL, rollen=("filter", "sortierung"), quelle="Kennzahlenabruf (Anbieter-Konsens)",
                  methode="kennzahlen", aufwaermphase="–", backtest="nur_vorwaerts", anzeige="#/potenzial", einheit_vergleich="prozent"), _w_zielabstand),
        Eintrag(k(id="analysten_anzahl", name="Zahl der Analystenziele", erklaerung="Zahl der berücksichtigten Kursziele im Anbieter-Konsens.", typ="zahl", einheit="Anzahl",
                  gruppe=A, parameter=(), operatoren=OPERATOREN_ZAHL, rollen=ROLLEN_FILTER, quelle="Kennzahlenabruf", methode="kennzahlen", aufwaermphase="–",
                  backtest="nur_vorwaerts", einheit_vergleich="anzahl"), _w_fakt("analysten")),
        Eintrag(k(id="gehalten", name="Im Depot gehalten", erklaerung="Das ausgewertete Spielgelddepot hält die Aktie für diese Regel.", typ="wahrheitswert", einheit="",
                  gruppe=D, parameter=(), operatoren=OPERATOREN_BOOL, rollen=ROLLEN_FILTER, quelle="Spielgeld-Journal", methode="buchhaltung-1", aufwaermphase="–"), _w_gehalten),
        Eintrag(k(id="position_gewinn_netto", name="Gewinn der Position nach Kosten", erklaerung="100 × (geschätzter Verkaufserlös nach Verkaufskosten − zugeordnete Anschaffungskosten inkl. Kaufkosten) / Anschaffungskosten, in EUR, vor Steuern.",
                  typ="zahl", einheit="%", gruppe=D, parameter=(), operatoren=OPERATOREN_ZAHL, rollen=("filter", "ausstieg", "sortierung"), quelle="Spielgeld-Journal",
                  methode="buchhaltung-1", aufwaermphase="–", einheit_vergleich="prozent"), _w_depot("gewinn_netto_pct")),
        Eintrag(k(id="position_kursgewinn", name="Kursgewinn der Position", erklaerung="100 × (Schlusskurs / Ø Einstandskurs − 1) in Notierungswährung, splitbereinigt, ohne Kosten.",
                  typ="zahl", einheit="%", gruppe=D, parameter=(), operatoren=OPERATOREN_ZAHL, rollen=("filter", "ausstieg", "sortierung"), quelle="Spielgeld-Journal",
                  methode="buchhaltung-1", aufwaermphase="–", einheit_vergleich="prozent"), _w_depot("kursgewinn_pct")),
        Eintrag(k(id="haltedauer", name="Haltedauer", erklaerung="Sitzungen seit dem ersten Kauf der Position.", typ="zahl", einheit="Sitzungen", gruppe=D, parameter=(),
                  operatoren=OPERATOREN_ZAHL, rollen=("filter", "ausstieg"), quelle="Spielgeld-Journal", methode="buchhaltung-1", aufwaermphase="–",
                  einheit_vergleich="sitzungen"), _w_depot("haltedauer")),
        Eintrag(k(id="positionsgewicht", name="Gewicht im Depot", erklaerung="Wert der Position in % des Depotwerts.", typ="zahl", einheit="%", gruppe=D, parameter=(),
                  operatoren=OPERATOREN_ZAHL, rollen=("filter", "ausstieg"), quelle="Spielgeld-Journal", methode="buchhaltung-1", aufwaermphase="–",
                  einheit_vergleich="prozent"), _w_depot("gewicht_pct")),
        Eintrag(k(id="stopabstand", name="Abstand zum Stop", erklaerung="100 × (Schlusskurs / Stopkurs − 1).", typ="zahl", einheit="%", gruppe=D, parameter=(),
                  operatoren=OPERATOREN_ZAHL, rollen=("filter", "ausstieg"), quelle="Spielgeld-Journal", methode="buchhaltung-1", aufwaermphase="–",
                  einheit_vergleich="prozent"), _w_depot("stopabstand_pct")),
    ]
    out = {}
    for e in eintraege:
        if e.kennzahl.id in out:
            raise AssertionError(f"Kennzahl doppelt: {e.kennzahl.id}")
        out[e.kennzahl.id] = e
    # Nur rückblickend bekannte Größen stehen sichtbar im Katalog, sind für Regeln aber gesperrt (Abschnitt 31.8)
    out["spaeterer_sieger"] = Eintrag(
        Kennzahl(id="spaeterer_sieger", name="Späterer Renditesieger", erklaerung="Ob die Aktie in einem später veröffentlichten Stand Platz 1 wurde – erst nachträglich bekannt und deshalb für Entscheidungen gesperrt.",
                 typ="wahrheitswert", einheit="", gruppe=L, parameter=(), operatoren=OPERATOREN_BOOL, rollen=(), quelle="spätere Stände", methode=mv,
                 aufwaermphase="–", backtest="nein", paper=False, rueckblickend=True),
        lambda ctx, p: ctx.leer(),
    )
    return out


def _vortag_kurs(ctx: Kontext, p: dict) -> np.ndarray:
    def fn(s, k):
        return float(s.close[k - 1]) * s.unit_factor if k >= 1 else math.nan

    return _per_series(ctx, ("kurs-1",), fn).copy()


def katalog_json(method: MethodConfig, cfg: Any = None) -> dict:
    """Definitionen für die App (ohne Berechnungen), sortiert nach Bereich und Name – stabil für den Vergleichstest."""
    entries = katalog(method, cfg)
    groups = ("Lineal", "Häufigkeit", "Kurs und Technik", "Umsatz", "Datenqualität", "Analysten", "Depot", "Stammdaten")
    ordered = sorted(entries.values(), key=lambda e: (groups.index(e.kennzahl.gruppe) if e.kennzahl.gruppe in groups else 99, e.kennzahl.id))
    return {
        "schema": "tr-kennzahlenkatalog/1",
        "version": KATALOG_VERSION,
        "methode": method.method_version,
        "bereiche": list(groups),
        "kennzahlen": [e.kennzahl.as_dict() for e in ordered],
    }


# --------------------------------------------------------------------------------------------- Werte abrufen


def werte(ctx: Kontext, eintraege: dict[str, Eintrag], ref: dict, *, vortag: bool = False) -> tuple[Kennzahl, dict, np.ndarray]:
    """Werte einer Kennzahlreferenz ``{"id": …, "parameter": {…}}`` für alle Aktien des Kontexts (mit Zwischenspeicher)."""
    if not isinstance(ref, dict) or "id" not in ref:
        raise KatalogFehler("Kennzahlreferenz braucht eine „id“")
    eintrag = eintraege.get(ref["id"])
    if eintrag is None:
        raise KatalogFehler(f"Unbekannte Kennzahl „{ref['id']}“")
    kz = eintrag.kennzahl
    if kz.rueckblickend:
        raise KatalogFehler(f"„{kz.name}“ ist nur rückblickend bekannt und für Regeln gesperrt")
    params = kz.parameter_pruefen(ref.get("parameter"))
    key = ("wert", kz.id, vortag, _freeze(params))
    hit = ctx._cache.get(key)
    if hit is None:
        if vortag:
            if eintrag.vortag is None:
                raise KatalogFehler(f"„{kz.name}“ hat keinen Vortageswert (kein „gekreuzt“ möglich)")
            hit = eintrag.vortag(ctx, params)
        else:
            hit = eintrag.werte(ctx, params)
        ctx._cache[key] = hit
    return kz, params, hit


def _freeze(value):
    if isinstance(value, dict):
        return tuple(sorted((k, _freeze(v)) for k, v in value.items()))
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(v) for v in value)
    return value
