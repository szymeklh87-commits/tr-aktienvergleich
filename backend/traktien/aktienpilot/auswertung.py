"""Auswertung einer Regel an einem Entscheidungstag (Abschnitte 31.2–31.5, 27.4).

Ablauf: Kandidatenquellen vereinigen (je ISIN eine wirtschaftliche Position, Fundstellen gezählt) → Filter dreiwertig
auswerten → sortieren → Anzahl und Branchenbegrenzung → Auswahl. Für gehaltene Positionen zusätzlich die Ausstiegsgründe
(Herausfallen mit Puffer, Ausstiegsbedingung, Haltedauer). Jede Entscheidung bleibt nachvollziehbar: welche Teilbedingung mit
welchem Wert erfüllt, nicht erfüllt oder nicht prüfbar war.

Dreiwertige Logik (Kleene): wahr (1), falsch (0), nicht prüfbar (−1).
UND: falsch, sobald eine Bedingung falsch ist; sonst nicht prüfbar, sobald eine nicht prüfbar ist; sonst wahr.
ODER: wahr, sobald eine wahr ist; sonst nicht prüfbar, sobald eine nicht prüfbar ist; sonst falsch.
NICHT: vertauscht wahr/falsch, nicht prüfbar bleibt nicht prüfbar.
Nur „wahr“ lässt einen Kandidaten durch bzw. löst einen freiwilligen Ausstieg aus – fehlende Daten erfüllen nie heimlich eine
Bedingung (Abschnitt 31.3).

Gleichstände: Sortierung nach den Schlüsseln in ihrer Reihenfolge, danach ISIN aufsteigend (dokumentiert und getestet, nie die
Datenbankreihenfolge).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from .katalog import Eintrag, Kontext, KatalogFehler, _rank_array, werte

WAHR, FALSCH, UNBEKANNT = 1, 0, -1
ZUSTAND = {WAHR: "wahr", FALSCH: "falsch", UNBEKANNT: "nicht_pruefbar"}


@dataclass
class Bedingungsdetail:
    pfad: str
    bedingung: dict
    a: np.ndarray
    b: np.ndarray | None
    ergebnis: np.ndarray

    def fuer(self, i: int) -> dict:
        def num(x):
            if x is None:
                return None
            try:
                v = float(x)
            except (TypeError, ValueError):
                return x
            return None if not math.isfinite(v) else round(v, 6)

        out = {"pfad": self.pfad, "ergebnis": ZUSTAND[int(self.ergebnis[i])], "wert": num(self.a[i])}
        if self.b is not None:
            out["vergleichswert"] = num(self.b[i])
        return out


@dataclass
class Ausdruckergebnis:
    werte: np.ndarray  # int8 je Aktie
    details: list[Bedingungsdetail] = field(default_factory=list)


def _kleene_and(parts: list[np.ndarray]) -> np.ndarray:
    stack = np.vstack(parts)
    out = np.full(stack.shape[1], WAHR, dtype=np.int8)
    out[np.any(stack == UNBEKANNT, axis=0)] = UNBEKANNT
    out[np.any(stack == FALSCH, axis=0)] = FALSCH
    return out


def _kleene_or(parts: list[np.ndarray]) -> np.ndarray:
    stack = np.vstack(parts)
    out = np.full(stack.shape[1], FALSCH, dtype=np.int8)
    out[np.any(stack == UNBEKANNT, axis=0)] = UNBEKANNT
    out[np.any(stack == WAHR, axis=0)] = WAHR
    return out


def _cmp(op: str, a: np.ndarray, b) -> np.ndarray:
    with np.errstate(invalid="ignore"):
        if op == ">":
            return a > b
        if op == ">=":
            return a >= b
        if op == "<":
            return a < b
        if op == "<=":
            return a <= b
        if op == "==":
            return a == b
        if op == "!=":
            return a != b
    raise KatalogFehler(f"Operator {op}")


def bedingung(ctx: Kontext, eintraege: dict[str, Eintrag], bed: dict, pfad: str) -> Bedingungsdetail:
    kz, _params, a = werte(ctx, eintraege, bed["kennzahl"])
    op = bed["op"]
    n = ctx.n
    out = np.full(n, UNBEKANNT, dtype=np.int8)
    b = None
    if kz.typ == "kategorie":
        allowed = set(bed["werte"])
        for i in range(n):
            v = a[i]
            if v is None or v == "":
                continue
            hit = v in allowed
            out[i] = WAHR if (hit if op == "in" else not hit) else FALSCH
        return Bedingungsdetail(pfad, bed, a, None, out)
    a = np.asarray(a, dtype=np.float64)
    known = np.isfinite(a)
    if op in ("ist_wahr", "ist_falsch"):
        truth = a == (1.0 if op == "ist_wahr" else 0.0)
        out[known] = np.where(truth[known], WAHR, FALSCH)
        return Bedingungsdetail(pfad, bed, a, None, out)
    if op == "zwischen":
        ok = (a >= bed["von"]) & (a <= bed["bis"])
        out[known] = np.where(ok[known], WAHR, FALSCH)
        return Bedingungsdetail(pfad, bed, a, None, out)
    if op in ("neu_eingetreten", "verlassen"):
        platz = bed["wert"]
        if ctx.vorher is None or ctx.vorher.comp is None:
            return Bedingungsdetail(pfad, bed, a, None, out)  # ohne vorige Entscheidung: nicht prüfbar
        _, _, prev_all = werte(ctx.vorher, eintraege, bed["kennzahl"])
        prev = np.full(n, np.nan)
        for i, isin in enumerate(ctx.isins):
            j = ctx.vorher.index.get(isin)
            if j is not None:
                prev[i] = prev_all[j]
        now_in = np.where(np.isfinite(a), a <= platz, False)
        was_in = np.where(np.isfinite(prev), prev <= platz, False)
        truth = (now_in & ~was_in) if op == "neu_eingetreten" else (was_in & ~now_in)
        out[:] = np.where(truth, WAHR, FALSCH)
        return Bedingungsdetail(pfad, bed, a, prev, out)
    if op.startswith("gekreuzt"):
        _, _, a_prev = werte(ctx, eintraege, bed["kennzahl"], vortag=True)
        if "vergleich" in bed:
            _, _, b = werte(ctx, eintraege, bed["vergleich"])
            _, _, b_prev = werte(ctx, eintraege, bed["vergleich"], vortag=True)
        else:
            b = np.full(n, float(bed["wert"]))
            b_prev = b
        known = np.isfinite(a) & np.isfinite(a_prev) & np.isfinite(b) & np.isfinite(b_prev)
        if op == "gekreuzt_aufwaerts":
            truth = (a_prev <= b_prev) & (a > b)
        else:
            truth = (a_prev >= b_prev) & (a < b)
        out[known] = np.where(truth[known], WAHR, FALSCH)
        return Bedingungsdetail(pfad, bed, a, np.asarray(b, dtype=np.float64), out)
    if "vergleich" in bed:
        _, _, b = werte(ctx, eintraege, bed["vergleich"])
        b = np.asarray(b, dtype=np.float64)
        known = known & np.isfinite(b)
        truth = _cmp(op, a, b)
    else:
        truth = _cmp(op, a, float(bed["wert"]))
    out[known] = np.where(truth[known], WAHR, FALSCH)
    return Bedingungsdetail(pfad, bed, a, b, out)


def ausdruck(ctx: Kontext, eintraege: dict[str, Eintrag], expr: dict | None, pfad: str = "filter") -> Ausdruckergebnis:
    if expr is None:
        return Ausdruckergebnis(np.full(ctx.n, WAHR, dtype=np.int8))
    if "und" in expr or "oder" in expr:
        op = "und" if "und" in expr else "oder"
        parts = [ausdruck(ctx, eintraege, e, f"{pfad}.{op}[{i}]") for i, e in enumerate(expr[op])]
        combined = (_kleene_and if op == "und" else _kleene_or)([p.werte for p in parts])
        return Ausdruckergebnis(combined, [d for p in parts for d in p.details])
    if "nicht" in expr:
        inner = ausdruck(ctx, eintraege, expr["nicht"], f"{pfad}.nicht")
        flipped = inner.werte.copy()
        flipped[inner.werte == WAHR] = FALSCH
        flipped[inner.werte == FALSCH] = WAHR
        return Ausdruckergebnis(flipped, inner.details)
    d = bedingung(ctx, eintraege, expr, pfad)
    return Ausdruckergebnis(d.ergebnis, [d])


# ------------------------------------------------------------------------------------------------ Kandidaten


@dataclass
class Fundstelle:
    quelle: int
    art: str
    fenster: int | None = None
    gewicht: int | None = None
    rang: int | None = None
    tag: int | None = None
    anzahl: float | None = None

    def as_dict(self) -> dict:
        out = {"quelle": self.quelle, "art": self.art}
        for key in ("fenster", "gewicht", "rang", "tag", "anzahl"):
            v = getattr(self, key)
            if v is not None:
                out[key] = v
        return out


@dataclass
class Kandidat:
    isin: str
    idx: int
    fundstellen: list[Fundstelle] = field(default_factory=list)
    filter: int = WAHR
    grund: str | None = None
    sortwerte: list[float] = field(default_factory=list)
    score: float | None = None
    platz: int | None = None
    ausgewaehlt: bool = False
    branche: str | None = None

    def as_dict(self, details: list[Bedingungsdetail] | None = None, fundstellen_max: int = 12) -> dict:
        out = {
            "isin": self.isin,
            "fundstellen": len(self.fundstellen),
            "beispiele": [f.as_dict() for f in self.fundstellen[:fundstellen_max]],
            "filter": ZUSTAND[self.filter],
            "grund": self.grund,
            "sortwerte": [None if not math.isfinite(v) else round(v, 6) for v in self.sortwerte],
            "score": None if self.score is None else round(self.score, 4),
            "platz": self.platz,
            "ausgewaehlt": self.ausgewaehlt,
        }
        if details:
            out["bedingungen"] = [d.fuer(self.idx) for d in details]
        return out


@dataclass
class Archivlesung:
    """Variante B: Ranglisten vergangener Stichtage aus dem Archiv (``tops(tag)`` → {(gruppe, politik, h, w): [isin, …]})."""

    tage: list[int]
    fehlend: list[int] = field(default_factory=list)


def kandidaten(ctx: Kontext, eintraege: dict[str, Eintrag], regel: dict, archiv=None) -> tuple[dict[str, Kandidat], list[dict]]:
    """Vereinigung aller Quellen; Rückgabe: Kandidaten je ISIN und eine Übersicht je Quelle."""
    pool: dict[str, Kandidat] = {}
    overview: list[dict] = []

    def add(idx: int, f: Fundstelle) -> None:
        isin = ctx.isins[idx]
        c = pool.get(isin)
        if c is None:
            c = pool[isin] = Kandidat(isin, idx)
        c.fundstellen.append(f)

    for qi, q in enumerate(regel["kandidaten"]):
        before = len(pool)
        hits = 0
        info: dict = {"quelle": qi, "art": q["art"]}
        if q["art"] == "rangliste" and q["variante"] == "heute":
            windows = range(q["fenster"]["von"], q["fenster"]["bis"] + 1)
            cells = 0
            for h in windows:
                for w in q["gewichte"]:
                    ranks, _ = _rank_array(ctx, h, w, q["gruppe"], q["politik"])
                    if np.any(np.isfinite(ranks)):
                        cells += 1
                    for idx in np.nonzero(np.isfinite(ranks) & (ranks <= q["platz_bis"]))[0]:
                        add(int(idx), Fundstelle(qi, "rangliste", h, w, int(ranks[idx]), ctx.tag))
                        hits += 1
            info.update(zellen=len(windows) * len(q["gewichte"]), gueltige_zellen=cells, nennungen=hits)
        elif q["art"] == "rangliste":
            if archiv is None:
                info.update(nennungen=0, fehlend="Ranglistenarchiv nicht verfügbar – Variante B nicht prüfbar")
            else:
                days = archiv.letzte_tage(ctx.tag, q["stichtage"])
                info["stichtage"] = days
                info["fehlend_stichtage"] = max(0, q["stichtage"] - len(days))
                for day in days:
                    for h in range(q["fenster"]["von"], q["fenster"]["bis"] + 1):
                        for w in q["gewichte"]:
                            for rank, isin in enumerate(archiv.top(day, q["gruppe"], q["politik"], h, w, q["platz_bis"]), start=1):
                                idx = ctx.index.get(isin)
                                if idx is not None:
                                    add(idx, Fundstelle(qi, "stichtag", h, w, rank, day))
                                    hits += 1
                info["nennungen"] = hits
        elif q["art"] == "haeufigkeit":
            ref = {"id": "haeufigkeit", "parameter": {k: q[k] for k in ("k", "fenster", "gewichte", "gruppe", "politik")}}
            _, _, counts = werte(ctx, eintraege, ref)
            for idx in np.nonzero(np.isfinite(counts) & (counts >= q["mindestens"]))[0]:
                add(int(idx), Fundstelle(qi, "haeufigkeit", anzahl=float(counts[idx])))
                hits += 1
            info["treffer"] = hits
        elif q["art"] == "universum":
            for idx in range(ctx.n):
                add(idx, Fundstelle(qi, "universum"))
            hits = ctx.n
            info["aktien"] = hits
        elif q["art"] == "isins":
            missing = []
            for isin in q["isins"]:
                idx = ctx.index.get(isin)
                if idx is None:
                    missing.append(isin)
                    continue
                add(idx, Fundstelle(qi, "liste"))
                hits += 1
            info.update(treffer=hits, nicht_im_universum=len(missing))
        info["neu_im_pool"] = len(pool) - before
        overview.append(info)
    return pool, overview


# ------------------------------------------------------------------------------------------------ Auswahl


@dataclass
class Auswahl:
    tag: int
    regel_id: str
    version: int
    kandidaten: list[Kandidat]
    ausgewaehlt: list[str]
    quellen: list[dict]
    details: list[Bedingungsdetail]
    sortiert: list[str]  # alle zugelassenen Kandidaten in Rangfolge (für Puffer)
    statistik: dict

    def platz_von(self, isin: str) -> int | None:
        try:
            return self.sortiert.index(isin) + 1
        except ValueError:
            return None

    def as_dict(self, max_kandidaten: int = 40) -> dict:
        chosen = [c for c in self.kandidaten if c.ausgewaehlt]
        rest = [c for c in self.kandidaten if not c.ausgewaehlt]
        rest.sort(key=lambda c: (c.platz is None, c.platz or 0, c.isin))
        shown = chosen + rest[: max(0, max_kandidaten - len(chosen))]
        return {
            "tag": self.tag,
            "regel": self.regel_id,
            "version": self.version,
            "ausgewaehlt": self.ausgewaehlt,
            "quellen": self.quellen,
            "statistik": self.statistik,
            "kandidaten": [c.as_dict(self.details) for c in shown],
        }


def _percentile(values: np.ndarray) -> np.ndarray:
    """Perzentil 0–100 aus Durchschnittsrängen (gleiche Werte → gleiches Perzentil)."""
    m = len(values)
    if m == 0:
        return values
    if m == 1:
        return np.array([100.0])
    order = np.argsort(values, kind="mergesort")
    ranks = np.empty(m, dtype=np.float64)
    sv = values[order]
    start = 0
    while start < m:
        end = start
        while end + 1 < m and sv[end + 1] == sv[start]:
            end += 1
        ranks[order[start:end + 1]] = (start + end) / 2.0 + 1.0
        start = end + 1
    return 100.0 * (ranks - 1.0) / (m - 1.0)


def auswaehlen(ctx: Kontext, eintraege: dict[str, Eintrag], regel: dict, archiv=None, *, sektor_von=None) -> Auswahl:
    """Kandidaten → Filter → Sortierung → Auswahl der ersten N (mit Branchenbegrenzung)."""
    pool, overview = kandidaten(ctx, eintraege, regel, archiv)
    filt = ausdruck(ctx, eintraege, regel.get("filter"))
    cands = sorted(pool.values(), key=lambda c: c.isin)
    for c in cands:
        c.filter = int(filt.werte[c.idx])
        if c.filter == FALSCH:
            failed = next((d for d in filt.details if d.ergebnis[c.idx] == FALSCH), None)
            c.grund = "Filter nicht erfüllt" + (f": {failed.pfad}" if failed else "")
        elif c.filter == UNBEKANNT:
            unknown = next((d for d in filt.details if d.ergebnis[c.idx] == UNBEKANNT), None)
            c.grund = "nicht prüfbar" + (f": Wert fehlt ({unknown.pfad})" if unknown else "")
    passed = [c for c in cands if c.filter == WAHR]
    sort = regel["sortierung"]
    if "schluessel" in sort:
        arrays = [(werte(ctx, eintraege, k["kennzahl"])[2], k["richtung"]) for k in sort["schluessel"]]
        for c in passed:
            c.sortwerte = [float(arr[c.idx]) for arr, _ in arrays]
        missing = [c for c in passed if not all(math.isfinite(v) for v in c.sortwerte)]
        for c in missing:
            c.filter = UNBEKANNT
            c.grund = "nicht prüfbar: Sortierwert fehlt"
        passed = [c for c in passed if all(math.isfinite(v) for v in c.sortwerte)]

        def key(c: Kandidat):
            return tuple(-v if d == "ab" else v for v, (_, d) in zip(c.sortwerte, arrays)) + (c.isin,)

        passed.sort(key=key)
    else:
        parts = sort["score"]
        arrays = [werte(ctx, eintraege, p["kennzahl"])[2] for p in parts]
        for c in passed:
            c.sortwerte = [float(arr[c.idx]) for arr in arrays]
        missing = [c for c in passed if not all(math.isfinite(v) for v in c.sortwerte)]
        for c in missing:
            c.filter = UNBEKANNT
            c.grund = "nicht prüfbar: Wert für den Score fehlt"
        passed = [c for c in passed if all(math.isfinite(v) for v in c.sortwerte)]
        total = sum(p["gewicht"] for p in parts)
        if passed:
            score = np.zeros(len(passed))
            for j, p in enumerate(parts):
                vals = np.array([c.sortwerte[j] for c in passed], dtype=np.float64)
                if p["richtung"] == "auf":
                    vals = -vals
                score += p["gewicht"] * _percentile(vals)
            score /= total
            for c, s in zip(passed, score):
                c.score = float(s)
        passed.sort(key=lambda c: (-(c.score or 0.0), c.isin))
    for place, c in enumerate(passed, start=1):
        c.platz = place
    limit = regel["auswahl"]["anzahl"]
    per_sector = regel["auswahl"].get("max_je_branche")
    chosen: list[str] = []
    counts: dict[str, int] = {}
    for c in passed:
        if len(chosen) >= limit:
            break
        sector = (sektor_von(c.isin) if sektor_von else (ctx.stamm.get(c.isin) or {}).get("branche")) or "Unbekannt"
        c.branche = sector
        if per_sector is not None and counts.get(sector, 0) >= per_sector:
            c.grund = f"Branchengrenze der Regel ({per_sector} je Branche)"
            continue
        counts[sector] = counts.get(sector, 0) + 1
        c.ausgewaehlt = True
        chosen.append(c.isin)
    stats = {
        "kandidaten": len(cands),
        "zugelassen": len(passed),
        "nicht_erfuellt": sum(1 for c in cands if c.filter == FALSCH),
        "nicht_pruefbar": sum(1 for c in cands if c.filter == UNBEKANNT),
        "ausgewaehlt": len(chosen),
        "zu_wenige": len(chosen) < limit,
    }
    return Auswahl(ctx.tag, regel["id"], regel["version"], cands, chosen, overview, filt.details, [c.isin for c in passed], stats)


# ------------------------------------------------------------------------------------------------ Ausstiege


@dataclass
class Ausstieg:
    isin: str
    verkaufen: bool
    grund: str
    art: str  # herausfallen | ausstieg | haltedauer | halten | nicht_pruefbar
    details: list[dict] = field(default_factory=list)


def ausstiege(ctx: Kontext, eintraege: dict[str, Eintrag], regel: dict, auswahl: Auswahl | None, gehalten: dict[str, dict]) -> dict[str, Ausstieg]:
    """Freiwillige Ausstiege gehaltener Positionen nach der Regel. Schutzstops und Risikoverkäufe prüft der Motor davor und
    unabhängig davon – eine Regel kann sie nicht verhindern (Abschnitt 31.5)."""
    v = regel["verkauf"]
    out: dict[str, Ausstieg] = {}
    exit_expr = ausdruck(ctx, eintraege, v.get("ausstieg"), "verkauf.ausstieg") if v.get("ausstieg") else None
    min_hold = int(regel["optionen"].get("mindesthaltedauer_sitzungen", 0))
    for isin, pos in sorted(gehalten.items()):
        idx = ctx.index.get(isin)
        held = int(pos.get("haltedauer") or 0)
        if v.get("max_haltedauer_sitzungen") and held >= v["max_haltedauer_sitzungen"]:
            out[isin] = Ausstieg(isin, True, f"Haltedauer {held} ≥ {v['max_haltedauer_sitzungen']} Sitzungen", "haltedauer")
            continue
        if held < min_hold:
            out[isin] = Ausstieg(isin, False, f"Mindesthaltedauer ({held} von {min_hold} Sitzungen)", "halten")
            continue
        if exit_expr is not None and idx is not None:
            state = int(exit_expr.werte[idx])
            if state == WAHR:
                out[isin] = Ausstieg(isin, True, "Ausstiegsbedingung erfüllt", "ausstieg", [d.fuer(idx) for d in exit_expr.details])
                continue
        hf = v.get("herausfallen") or {}
        if hf.get("aktiv") and auswahl is not None:
            limit = regel["auswahl"]["anzahl"] + int(hf.get("puffer", 0))
            place = auswahl.platz_von(isin)
            cand = next((c for c in auswahl.kandidaten if c.isin == isin), None)
            if place is not None and place <= limit:
                out[isin] = Ausstieg(isin, False, f"Platz {place} (gehalten bis Platz {limit})", "halten")
            elif cand is not None and cand.filter == UNBEKANNT:
                out[isin] = Ausstieg(isin, False, f"{cand.grund or 'nicht prüfbar'} – gehalten, kein Verkauf aus fehlenden Daten", "nicht_pruefbar")
            elif cand is not None and cand.filter == FALSCH:
                out[isin] = Ausstieg(isin, True, cand.grund or "Filter nicht mehr erfüllt", "herausfallen")
            elif place is not None:
                out[isin] = Ausstieg(isin, True, f"Platz {place} – außerhalb der Haltegrenze Platz {limit}", "herausfallen")
            else:
                out[isin] = Ausstieg(isin, True, "nicht mehr unter den Kandidaten der Regel", "herausfallen")
            continue
        out[isin] = Ausstieg(isin, False, "keine Ausstiegsbedingung erfüllt", "halten")
    return out
