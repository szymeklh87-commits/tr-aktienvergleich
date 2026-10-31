"""Forschungsmotor des Depot-Optimierers (Aufträge vom 31.10.2026: 18 Abschnitte 4–6, 11–13 und 19; 19 Abschnitte 4–6 und 8).

Grundlage ist ein **Merkmalspanel**: an festen Entscheidungstagen (z. B. jede Woche) die Merkmale aller Aktien aus dem
zentralen Katalog (``merkmale.py``) – nur mit Daten bis zu diesem Tag – und die danach tatsächlich erzielten Renditen in Euro
für die Horizonte 1, 2, 4, 12, 26 und 52 Wochen. Daraus:

1. **Prognosenutzen je Merkmal und Horizont** (Rang-Informationskoeffizient = Rangkorrelation zwischen Merkmal und späterer
   Rendite je Tag), getrennt nach Entwicklung, Validierung und Test (zeitlich hintereinander, ohne Überlappung). Die
   Teststatistik rechnet mit der Zahl **unabhängiger** Zeiträume (überlappende Folgerenditen zählen nicht mehrfach); über alle
   Merkmale und Horizonte wird die Rate falscher Funde nach Benjamini-Hochberg begrenzt. „Bestätigt“ ist ein Merkmal nur, wenn
   es in der Entwicklung auffällt und in der Validierung mit derselben Richtung besteht; der Testzeitraum wird nur berichtet.
2. **Redundanz**: Rangkorrelation der Merkmale untereinander; je Gruppe sehr ähnlicher Merkmale zählt das stärkste.
3. **Zusatznutzen**: schrittweise Auswahl – ein Merkmal kommt nur dazu, wenn es die Kombination in der Validierung verbessert.
   Mehr Merkmale bedeuten keine bessere Wertung.
4. **Prognosemodelle** im Walk-forward (Training nur mit Renditen, die vor dem Prüfzeitraum bekannt waren): Nullmodell,
   Momentum (Trendfortsetzung), lineares Mehrfaktormodell, Musterähnlichkeit (nächste Nachbarn) und ihre Kombination. Ein
   komplexes Modell gewinnt nur mit Vorsprung vor dem einfachen.
5. **Kalibrierung**: Aus den Walk-forward-Vorhersagen je Zehntel (Dezil) die tatsächliche mittlere Rendite, der Anteil positiver
   Ergebnisse und die 10-/50-/90-%-Spanne – so werden Wahrscheinlichkeiten und Szenarien aus beobachteten Häufigkeiten statt
   aus Annahmen gewonnen.
6. **Belastbarkeit je Horizont** aus der Zahl unabhängiger Zeiträume: Für lange Horizonte reicht die Historie oft nicht – dann
   steht dort „nicht belastbar“ statt einer Zahl.

Alles ist reproduzierbar (feste Startwerte für Stichproben) und reine Rechnung auf Arrays; der Lauf (``optimierer.py``) baut das
Panel und speichert das Ergebnis.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

VERSION = "forschung-1"

# Horizonte in Handelstagen (1, 2, 4, 12, 26, 52 Wochen)
HORIZONTE: dict[str, int] = {"w1": 5, "w2": 10, "w4": 20, "w12": 60, "w26": 130, "w52": 260}
HORIZONT_TEXT: dict[str, str] = {"w1": "1 Woche", "w2": "2 Wochen", "w4": "4 Wochen", "w12": "12 Wochen", "w26": "26 Wochen", "w52": "52 Wochen"}
ANTEILE = (0.6, 0.2)  # Entwicklung, Validierung; der Rest ist Test
MIN_AKTIEN_TAG = 30  # weniger Aktien mit Wert und Rendite an einem Tag: der Tag zählt für dieses Merkmal nicht
FDR_Q = 0.10  # Benjamini-Hochberg über alle Merkmale × Horizonte
VALIDIERUNG_T = 1.0  # in der Validierung: gleiche Richtung und t ≥ 1 (einseitig p ≤ 0,16)
REDUNDANZ_RHO = 0.8  # |Rangkorrelation| ab der zwei Merkmale als „überschneidend“ gelten
ZUSATZ_MIN = 0.002  # Mindestverbesserung des Validierungs-IC durch ein weiteres Merkmal
MAX_MERKMALE_MODELL = 8
BELASTBAR_MIN = 20.0  # unabhängige Zeiträume in Entwicklung + Validierung
EINGESCHRAENKT_MIN = 8.0
MODELL_VORSPRUNG = 0.005  # ein komplexeres Modell muss den IC des einfacheren um mindestens so viel übertreffen
MODELL_MIN_T = 2.0  # Walk-forward-t-Wert, ab dem ein Modell als prognosefähig gilt
KNN_K = 50
KNN_STICHPROBE = 8000
RIDGE_LAMBDAS = (1.0, 10.0, 100.0)
DEZILE = 10
SEED = 20261031

MODELLE = {
    "null": "Nullmodell (alle Aktien gleich)",
    "momentum": "Momentum (Trendfortsetzung)",
    "linear": "Mehrfaktormodell (linear, regularisiert)",
    "aehnlichkeit": "Musterähnlichkeit (nächste Nachbarn)",
    "kombination": "Kombination der Modelle",
}

# Momentum-Merkmal je Horizont: dieselbe Kennzahl wie in den Ranglisten, Fenster passend zum Horizont
MOMENTUM_MERKMAL = {"w1": "rendite@fenster=20", "w2": "rendite@fenster=20", "w4": "rendite@fenster=60", "w12": "rendite@fenster=90",
                    "w26": "rendite@fenster=90", "w52": "rendite@fenster=90"}


# ------------------------------------------------------------------------------------------------------ Grundlagen


def raenge(werte: np.ndarray) -> np.ndarray:
    """Querschnittsränge je Spalte als Anteil 0–1 (Mittelränge bei Gleichstand); NaN bleibt NaN."""
    werte = np.asarray(werte, dtype=np.float64)
    if werte.ndim == 1:
        return _rang1(werte)
    out = np.full(werte.shape, np.nan)
    for j in range(werte.shape[1]):
        out[:, j] = _rang1(werte[:, j])
    return out


def _rang1(x: np.ndarray) -> np.ndarray:
    out = np.full(x.shape, np.nan)
    ok = np.isfinite(x)
    n = int(ok.sum())
    if n == 0:
        return out
    v = x[ok]
    order = np.argsort(v, kind="mergesort")
    ranks = np.empty(n)
    sv = v[order]
    # Mittelränge bei Gleichstand
    i = 0
    while i < n:
        j = i
        while j + 1 < n and sv[j + 1] == sv[i]:
            j += 1
        ranks[order[i:j + 1]] = (i + j) / 2.0 + 1.0
        i = j + 1
    out[ok] = ranks / n
    return out


def rang_ic(x: np.ndarray, r: np.ndarray, min_n: int = MIN_AKTIEN_TAG) -> float:
    """Rangkorrelation (Spearman) zwischen Merkmal ``x`` und späterer Rendite ``r`` an einem Tag; NaN bei zu wenigen Werten."""
    ok = np.isfinite(x) & np.isfinite(r)
    if int(ok.sum()) < min_n:
        return float("nan")
    a = _rang1(x[ok])
    b = _rang1(r[ok])
    a = a - a.mean()
    b = b - b.mean()
    den = math.sqrt(float((a * a).sum()) * float((b * b).sum()))
    return float((a * b).sum() / den) if den > 0 else float("nan")


def unabhaengige(n_tage: int, schritt: int, h: int) -> float:
    """Zahl unabhängiger Zeiträume: Entscheidungstage im Abstand ``schritt`` mit Folgerendite über ``h`` Handelstage überlappen,
    wenn ``h`` > ``schritt``."""
    if n_tage <= 0:
        return 0.0
    return max(1.0, n_tage * min(1.0, schritt / float(h)))


def _t_wert(werte: np.ndarray, n_eff: float) -> float:
    w = werte[np.isfinite(werte)]
    if len(w) < 3:
        return float("nan")
    sd = float(w.std(ddof=1))
    if sd <= 0:
        return float("nan")
    return float(w.mean() / sd * math.sqrt(max(1.0, min(n_eff, len(w)))))


def _p_zweiseitig(t: float) -> float:
    if not math.isfinite(t):
        return 1.0
    return float(math.erfc(abs(t) / math.sqrt(2.0)))


def benjamini_hochberg(p: list[float], q: float = FDR_Q) -> list[bool]:
    """Auffällig nach Benjamini-Hochberg (Rate falscher Funde höchstens ``q``)."""
    n = len(p)
    if n == 0:
        return []
    order = sorted(range(n), key=lambda i: p[i])
    grenze = -1
    for rank, i in enumerate(order, start=1):
        if p[i] <= q * rank / n:
            grenze = rank
    out = [False] * n
    for rank, i in enumerate(order, start=1):
        if rank <= grenze:
            out[i] = True
    return out


# ------------------------------------------------------------------------------------------------------ Panel


@dataclass
class Panel:
    """Merkmalsränge und Folgerenditen an Entscheidungstagen. ``X``: (Tage, Aktien, Merkmale) Querschnittsränge 0–1 (NaN =
    kein Wert); ``R[h]``: (Tage, Aktien) Folgerendite in Prozent über ``HORIZONTE[h]`` Handelstage (NaN = noch unbekannt oder
    keine Kurse). ``schritt``: Handelstage zwischen zwei Entscheidungstagen."""
    tage: np.ndarray
    isins: list[str]
    merkmale: list[str]
    X: np.ndarray
    R: dict[str, np.ndarray]
    schritt: int
    namen: dict[str, str] = field(default_factory=dict)  # Merkmal → lesbarer Name

    def j(self, schluessel: str) -> int | None:
        try:
            return self.merkmale.index(schluessel)
        except ValueError:
            return None

    def bekannt(self, h: str) -> np.ndarray:
        """Indizes der Tage, an denen die Folgerendite für ``h`` schon für genug Aktien bekannt ist."""
        R = self.R[h]
        return np.nonzero(np.isfinite(R).sum(axis=1) >= MIN_AKTIEN_TAG)[0]


def zeitraeume(idx: np.ndarray) -> dict[str, np.ndarray]:
    """Entwicklung, Validierung, Test: zeitlich hintereinander (Anteile ``ANTEILE``) über die Tage mit bekannter Rendite."""
    n = len(idx)
    e = int(round(n * ANTEILE[0]))
    v = int(round(n * ANTEILE[1]))
    return {"entwicklung": idx[:e], "validierung": idx[e:e + v], "test": idx[e + v:]}


def _gereinigt(train: np.ndarray, test_start: int, h_tage: int, schritt: int) -> np.ndarray:
    """Training ohne Tage, deren Folgerendite in den Prüfzeitraum hineinreicht (Sperrabstand, „purging“)."""
    abstand = int(math.ceil(h_tage / float(schritt)))
    return train[train <= test_start - abstand]


# ------------------------------------------------------------------------------------------------------ Faktorprüfung


def ic_reihe(panel: Panel, j: int, h: str, tage: np.ndarray) -> np.ndarray:
    R = panel.R[h]
    return np.array([rang_ic(panel.X[t, :, j], R[t]) for t in tage])


def spanne_reihe(panel: Panel, j: int, h: str, tage: np.ndarray, anteil: float = 0.2) -> np.ndarray:
    """Mittlere Rendite des besten minus des schlechtesten Fünftels (nach Merkmal) je Tag in Prozentpunkten."""
    R = panel.R[h]
    out = []
    for t in tage:
        x, r = panel.X[t, :, j], R[t]
        ok = np.isfinite(x) & np.isfinite(r)
        if int(ok.sum()) < MIN_AKTIEN_TAG:
            out.append(np.nan)
            continue
        xs, rs = x[ok], r[ok]
        hi = rs[xs >= np.quantile(xs, 1 - anteil)]
        lo = rs[xs <= np.quantile(xs, anteil)]
        out.append(float(hi.mean() - lo.mean()) if len(hi) and len(lo) else np.nan)
    return np.array(out)


def faktorpruefung(panel: Panel, horizonte: list[str] | None = None) -> dict:
    """Prognosenutzen jedes Merkmals je Horizont in Entwicklung, Validierung und Test (siehe Modulbeschreibung)."""
    horizonte = horizonte or list(HORIZONTE)
    zeilen = []
    for h in horizonte:
        idx = panel.bekannt(h)
        zr = zeitraeume(idx)
        for j, key in enumerate(panel.merkmale):
            eintrag = {"merkmal": key, "horizont": h}
            for art, tage in zr.items():
                ics = ic_reihe(panel, j, h, tage) if len(tage) else np.array([])
                n_eff = unabhaengige(int(np.isfinite(ics).sum()), panel.schritt, HORIZONTE[h])
                t = _t_wert(ics, n_eff)
                mean = float(np.nanmean(ics)) if np.isfinite(ics).any() else float("nan")
                eintrag[art] = {"ic": _r(mean, 4), "t": _r(t, 2), "tage": int(np.isfinite(ics).sum()), "unabhaengig": _r(n_eff, 1),
                                "trefferquote_pct": _r(100.0 * float((ics[np.isfinite(ics)] > 0).mean()), 1) if np.isfinite(ics).any() else None}
                if art == "entwicklung":
                    sp = spanne_reihe(panel, j, h, tage) if len(tage) else np.array([])
                    eintrag[art]["spanne_pp"] = _r(float(np.nanmean(sp)), 2) if np.isfinite(sp).any() else None
            zeilen.append(eintrag)
    # Benjamini-Hochberg über alle Merkmale × Horizonte (Entwicklung)
    p = [_p_zweiseitig(z["entwicklung"]["t"] if z["entwicklung"]["t"] is not None else float("nan")) for z in zeilen]
    auff = benjamini_hochberg(p)
    for z, a, pv in zip(zeilen, auff, p):
        dev, val = z["entwicklung"], z["validierung"]
        z["p_entwicklung"] = _r(pv, 4)
        z["auffaellig"] = bool(a)
        richtung = 0 if dev["ic"] is None or not math.isfinite(dev["ic"]) or dev["ic"] == 0 else (1 if dev["ic"] > 0 else -1)
        z["richtung"] = richtung
        bestaetigt = bool(a and richtung and val["t"] is not None and math.isfinite(val["t"]) and val["t"] * richtung >= VALIDIERUNG_T)
        z["bestaetigt"] = bestaetigt
        if bestaetigt:
            z["urteil"] = "bestätigt"
        elif a:
            z["urteil"] = "in der Validierung nicht bestätigt"
        elif dev["tage"] < 3:
            z["urteil"] = "zu wenige Tage"
        else:
            z["urteil"] = "kein nachweisbarer Nutzen"
    return {"zeilen": zeilen, "fdr_q": FDR_Q, "validierung_t": VALIDIERUNG_T,
            "hinweis": "Rang-IC: Rangkorrelation zwischen Merkmal und späterer Rendite je Tag; t-Wert mit unabhängigen Zeiträumen; "
                       "Benjamini-Hochberg über alle Merkmale und Horizonte; bestätigt = auffällig in der Entwicklung und gleiche Richtung "
                       "in der Validierung. Der Testzeitraum wählt nichts aus."}


def redundanz(panel: Panel, tage: np.ndarray, rho: float = REDUNDANZ_RHO, max_tage: int = 30) -> dict:
    """Mittlere Rangkorrelation der Merkmale untereinander (an bis zu ``max_tage`` gleichmäßig verteilten Tagen)."""
    if not len(tage):
        return {"matrix": None, "paare": []}
    pick = tage[np.linspace(0, len(tage) - 1, min(max_tage, len(tage))).round().astype(int)]
    F = panel.X.shape[2]
    acc = np.zeros((F, F))
    cnt = np.zeros((F, F))
    for t in pick:
        Z = panel.X[t].astype(np.float64)
        ok = np.isfinite(Z)
        Zc = np.where(ok, Z - 0.5, 0.0)
        n = ok.astype(np.float64)
        num = Zc.T @ Zc
        ss = (Zc * Zc).T @ n  # Summe der Quadrate von i dort, wo j existiert
        den = np.sqrt(ss * ss.T)
        with np.errstate(invalid="ignore", divide="ignore"):
            c = np.where(den > 0, num / den, np.nan)
        pairs = n.T @ n
        valid = (pairs >= MIN_AKTIEN_TAG) & np.isfinite(c)
        acc[valid] += c[valid]
        cnt[valid] += 1
    with np.errstate(invalid="ignore", divide="ignore"):
        mean = np.where(cnt > 0, acc / cnt, np.nan)
    paare = []
    for a in range(F):
        for b in range(a + 1, F):
            if np.isfinite(mean[a, b]) and abs(mean[a, b]) >= rho:
                paare.append({"a": panel.merkmale[a], "b": panel.merkmale[b], "rho": _r(float(mean[a, b]), 3)})
    return {"matrix": mean, "paare": paare, "rho": rho}


def _komposit(panel: Panel, js: list[int], richtungen: list[int], tage: np.ndarray) -> np.ndarray:
    """Gleichgewichtete Kombination der (ausgerichteten) Merkmalsränge je Tag; fehlende Werte zählen als Mitte."""
    out = np.zeros((len(tage), panel.X.shape[1]))
    for k, t in enumerate(tage):
        s = np.zeros(panel.X.shape[1])
        any_ok = np.zeros(panel.X.shape[1], dtype=bool)
        for j, r in zip(js, richtungen):
            x = panel.X[t, :, j]
            ok = np.isfinite(x)
            any_ok |= ok
            s += np.where(ok, (x - 0.5) * r, 0.0)
        out[k] = np.where(any_ok, s, np.nan)
    return out


def _mittel_ic(scores: np.ndarray, R: np.ndarray, tage: np.ndarray) -> float:
    ics = np.array([rang_ic(scores[k], R[t]) for k, t in enumerate(tage)])
    return float(np.nanmean(ics)) if np.isfinite(ics).any() else float("nan")


def zusatznutzen(panel: Panel, h: str, faktoren: list[dict], red: dict, zr: dict[str, np.ndarray]) -> dict:
    """Schrittweise Auswahl unter den bestätigten, nicht überschneidenden Merkmalen: ein Merkmal kommt nur hinzu, wenn es die
    gleichgewichtete Kombination in der Validierung um mindestens ``ZUSATZ_MIN`` verbessert (Auswahl nach Entwicklung)."""
    R = panel.R[h]
    kandidaten = [z for z in faktoren if z["horizont"] == h and z["bestaetigt"]]
    kandidaten.sort(key=lambda z: -abs(z["entwicklung"]["t"] or 0.0))
    matrix = red.get("matrix")
    gewaehlt: list[int] = []
    richtungen: list[int] = []
    schritte = []
    uebersprungen = []
    best_val = float("-inf")
    for z in kandidaten:
        j = panel.j(z["merkmal"])
        if j is None:
            continue
        if matrix is not None and any(np.isfinite(matrix[j, g]) and abs(matrix[j, g]) >= REDUNDANZ_RHO for g in gewaehlt):
            partner = next(panel.merkmale[g] for g in gewaehlt if np.isfinite(matrix[j, g]) and abs(matrix[j, g]) >= REDUNDANZ_RHO)
            uebersprungen.append({"merkmal": z["merkmal"], "grund": f"überschneidet sich mit {partner}"})
            continue
        if len(gewaehlt) >= MAX_MERKMALE_MODELL:
            uebersprungen.append({"merkmal": z["merkmal"], "grund": f"höchstens {MAX_MERKMALE_MODELL} Merkmale je Modell"})
            continue
        trial = gewaehlt + [j]
        rich = richtungen + [z["richtung"]]
        dev_ic = _mittel_ic(_komposit(panel, trial, rich, zr["entwicklung"]), R, zr["entwicklung"]) if len(zr["entwicklung"]) else float("nan")
        val_ic = _mittel_ic(_komposit(panel, trial, rich, zr["validierung"]), R, zr["validierung"]) if len(zr["validierung"]) else float("nan")
        if not gewaehlt or (math.isfinite(val_ic) and val_ic >= best_val + ZUSATZ_MIN):
            gewaehlt, richtungen = trial, rich
            best_val = val_ic if math.isfinite(val_ic) else best_val
            schritte.append({"merkmal": z["merkmal"], "ic_entwicklung": _r(dev_ic, 4), "ic_validierung": _r(val_ic, 4)})
        else:
            uebersprungen.append({"merkmal": z["merkmal"], "grund": "kein zusätzlicher Nutzen in der Validierung",
                                  "ic_validierung": _r(val_ic, 4), "bisher": _r(best_val, 4)})
    return {"horizont": h, "merkmale": [panel.merkmale[j] for j in gewaehlt], "richtungen": richtungen, "schritte": schritte,
            "uebersprungen": uebersprungen}


# ------------------------------------------------------------------------------------------------------ Modelle


def _demeaned(R: np.ndarray, tage: np.ndarray) -> np.ndarray:
    """Folgerenditen je Tag ohne Tagesmittel (Querschnitt) – Modelle lernen die relative Rendite."""
    out = R[tage].astype(np.float64)
    with np.errstate(invalid="ignore"):
        mean = np.nanmean(out, axis=1, keepdims=True)
    return out - mean


def _feature_block(panel: Panel, tage: np.ndarray, js: list[int], richtungen: list[int]) -> np.ndarray:
    """(Tage, Aktien, k) ausgerichtete, zentrierte Ränge; fehlende Werte = 0 (Mitte)."""
    Z = panel.X[np.ix_(tage, np.arange(panel.X.shape[1]), js)].astype(np.float64) - 0.5
    Z = Z * np.asarray(richtungen, dtype=np.float64)[None, None, :]
    return np.where(np.isfinite(Z), Z, 0.0)


@dataclass
class Modell:
    art: str
    merkmale: list[str]
    richtungen: list[int]
    koeffizienten: list[float] | None = None
    lam: float | None = None
    knn_X: np.ndarray | None = None
    knn_y: np.ndarray | None = None
    teile: list["Modell"] | None = None

    def vorhersage(self, Z: np.ndarray) -> np.ndarray:
        """Wertung je Aktie aus ausgerichteten, zentrierten Rängen ``Z`` (Aktien × Merkmale dieses Modells; fehlend = 0).
        Für die Kombination ``bewerten`` verwenden (jeder Teil mit seinen eigenen Merkmalen)."""
        if self.art == "null":
            return np.zeros(Z.shape[0])
        if self.art == "momentum":
            return Z[:, 0].copy()
        if self.art == "linear":
            return Z @ np.asarray(self.koeffizienten)
        if self.art == "aehnlichkeit":
            return _knn(self.knn_X, self.knn_y, Z, KNN_K)
        raise ValueError(self.art)

    def as_dict(self) -> dict:
        out = {"art": self.art, "name": MODELLE[self.art], "merkmale": self.merkmale, "richtungen": self.richtungen}
        if self.koeffizienten is not None:
            out["koeffizienten"] = [round(float(c), 6) for c in self.koeffizienten]
            out["lambda"] = self.lam
        if self.knn_X is not None:
            out["knn"] = {"k": KNN_K, "punkte": int(len(self.knn_X)), "X": np.round(self.knn_X, 4).tolist(), "y": np.round(self.knn_y, 3).tolist()}
        if self.teile is not None:
            out["teile"] = [p.as_dict() for p in self.teile]
        return out

    @staticmethod
    def from_dict(d: dict) -> "Modell":
        m = Modell(d["art"], list(d["merkmale"]), [int(r) for r in d["richtungen"]])
        if "koeffizienten" in d:
            m.koeffizienten = [float(c) for c in d["koeffizienten"]]
            m.lam = d.get("lambda")
        if "knn" in d:
            m.knn_X = np.asarray(d["knn"]["X"], dtype=np.float64)
            m.knn_y = np.asarray(d["knn"]["y"], dtype=np.float64)
        if "teile" in d:
            m.teile = [Modell.from_dict(p) for p in d["teile"]]
        return m


def _knn(Xtr: np.ndarray, ytr: np.ndarray, Z: np.ndarray, k: int, chunk: int = 2000) -> np.ndarray:
    """Mittlere relative Folgerendite der ``k`` ähnlichsten Aktien-Tage aus dem Training (euklidisch in Rängen)."""
    if Xtr is None or not len(Xtr):
        return np.zeros(Z.shape[0])
    k = min(k, len(Xtr))
    out = np.empty(Z.shape[0])
    sq_tr = (Xtr * Xtr).sum(axis=1)
    for a in range(0, Z.shape[0], chunk):
        q = Z[a:a + chunk]
        d = (q * q).sum(axis=1)[:, None] + sq_tr[None, :] - 2.0 * q @ Xtr.T
        idx = np.argpartition(d, k - 1, axis=1)[:, :k]
        out[a:a + chunk] = ytr[idx].mean(axis=1)
    return out


def trainieren(art: str, panel: Panel, h: str, tage: np.ndarray, auswahl: dict, *, lam: float | None = None,
               rng: np.random.Generator | None = None) -> Modell:
    """Ein Modell nur mit den Tagen ``tage`` trainieren (ihre Folgerenditen müssen vor dem Einsatz bekannt sein)."""
    if art == "null":
        return Modell("null", [], [])
    if art == "momentum":
        key = MOMENTUM_MERKMAL[h]
        return Modell("momentum", [key], [1])
    js = [panel.j(m) for m in auswahl["merkmale"]]
    rich = list(auswahl["richtungen"])
    if not js:
        return Modell("null", [], [])
    Z = _feature_block(panel, tage, js, rich)
    y = _demeaned(panel.R[h], tage)
    ok = np.isfinite(y)
    Zf = Z[ok]
    yf = np.clip(y[ok], -100.0, 300.0)  # Ausreißer begrenzen (Prozent)
    if art == "linear":
        lam = lam if lam is not None else RIDGE_LAMBDAS[1]
        A = Zf.T @ Zf + lam * len(yf) / 1000.0 * np.eye(Zf.shape[1])
        coef = np.linalg.solve(A, Zf.T @ yf)
        return Modell("linear", list(auswahl["merkmale"]), rich, koeffizienten=coef.tolist(), lam=lam)
    if art == "aehnlichkeit":
        rng = rng or np.random.default_rng(SEED)
        n = len(yf)
        pick = rng.choice(n, size=min(n, KNN_STICHPROBE), replace=False) if n > KNN_STICHPROBE else np.arange(n)
        return Modell("aehnlichkeit", list(auswahl["merkmale"]), rich, knn_X=Zf[pick], knn_y=yf[pick])
    if art == "kombination":
        teile = [trainieren(a, panel, h, tage, auswahl, lam=lam, rng=rng) for a in ("momentum", "linear", "aehnlichkeit")]
        merk = list(dict.fromkeys([m for p in teile for m in p.merkmale]))
        return Modell("kombination", merk, [0] * len(merk), teile=teile)  # Richtungen stehen in den Teilen
    raise ValueError(art)


def kombinieren(teile: list[np.ndarray]) -> np.ndarray:
    """Kombination: Mittel der Querschnittsränge der Teilwertungen (jede zählt gleich)."""
    ranks = np.vstack([_rang1(x) - 0.5 for x in teile])
    with np.errstate(invalid="ignore"):
        ok = np.isfinite(ranks).any(axis=0)
        mean = np.nanmean(np.where(np.isfinite(ranks), ranks, np.nan), axis=0) if ranks.size else np.array([])
    return np.where(ok, mean, np.nan)


def bewerten(modell: Modell, rang_von, n: int) -> np.ndarray:
    """Wertung von ``n`` Aktien; ``rang_von(schluessel)`` liefert die Querschnittsränge (0–1, NaN = fehlt) eines Merkmals.
    Dieselbe Funktion für den historischen Test (Panel-Tag) und die heutige Empfehlung (Merkmalsmatrix des Stichtags)."""
    if modell.art == "null":
        return np.zeros(n)
    if modell.art == "kombination":
        return kombinieren([bewerten(p, rang_von, n) for p in modell.teile])
    X = np.column_stack([np.asarray(rang_von(m), dtype=np.float64) for m in modell.merkmale]) - 0.5
    X = X * np.asarray(modell.richtungen, dtype=np.float64)[None, :]
    has = np.isfinite(X).any(axis=1)
    s = modell.vorhersage(np.where(np.isfinite(X), X, 0.0))
    return np.where(has, s, np.nan)


def wertung(modell: Modell, panel: Panel, t: int) -> np.ndarray:
    """Wertung aller Aktien am Panel-Tag ``t`` (NaN, wo die Aktie an dem Tag kein Merkmal des Modells hat)."""
    def rang_von(key: str) -> np.ndarray:
        j = panel.j(key)
        if j is None:
            raise ValueError(f"Merkmal {key} fehlt im Panel")
        return panel.X[t, :, j]
    out = bewerten(modell, rang_von, panel.X.shape[1])
    if modell.art == "null":
        out = np.where(np.isfinite(panel.X[t]).any(axis=1), out, np.nan)
    return out


def walk_forward(panel: Panel, h: str, auswahl: dict, faltungen: int = 4, start_anteil: float = 0.5) -> dict:
    """Modelle im Walk-forward: je Faltung Training nur mit Tagen, deren Folgerendite vor dem Prüfblock endet; Vorhersage und
    Messung im Prüfblock. Rückgabe: Kennzahlen je Modell und die Vorhersagen (für die Kalibrierung)."""
    idx = panel.bekannt(h)
    if len(idx) < 10:
        return {"faltungen": 0, "modelle": {}, "vorhersagen": {}}
    start = max(3, int(len(idx) * start_anteil))
    bloecke = np.array_split(idx[start:], faltungen)
    rng = np.random.default_rng(SEED)
    res: dict[str, dict] = {a: {"ic": [], "top_pp": [], "tage": []} for a in MODELLE}
    vorh: dict[str, list] = {a: [] for a in MODELLE}
    gefaltet = 0
    for block in bloecke:
        if not len(block):
            continue
        train = _gereinigt(idx[idx < block[0]], int(block[0]), HORIZONTE[h], panel.schritt)
        if len(train) < 3:
            continue
        gefaltet += 1
        modelle = {a: trainieren(a, panel, h, train, auswahl, rng=rng) for a in ("null", "momentum", "linear", "aehnlichkeit")}
        for t in block:
            r = panel.R[h][t]
            scores = {a: wertung(m, panel, int(t)) for a, m in modelle.items()}
            scores["kombination"] = kombinieren([scores["momentum"], scores["linear"], scores["aehnlichkeit"]])
            for art, s in scores.items():
                res[art]["ic"].append(rang_ic(s, r) if art != "null" else 0.0)
                res[art]["top_pp"].append(_top_ueberschuss(s, r) if art != "null" else 0.0)
                res[art]["tage"].append(int(t))
                vorh[art].append((int(t), s))
    out = {}
    for art, v in res.items():
        ics = np.array(v["ic"], dtype=float)
        n_eff = unabhaengige(int(np.isfinite(ics).sum()), panel.schritt, HORIZONTE[h])
        tops = np.array(v["top_pp"], dtype=float)
        out[art] = {"name": MODELLE[art], "ic": _r(float(np.nanmean(ics)) if np.isfinite(ics).any() else float("nan"), 4),
                    "t": _r(_t_wert(ics, n_eff) if art != "null" else float("nan"), 2), "tage": int(np.isfinite(ics).sum()),
                    "unabhaengig": _r(n_eff, 1), "top_ueberschuss_pp": _r(float(np.nanmean(tops)) if np.isfinite(tops).any() else float("nan"), 2),
                    "top_trefferquote_pct": _r(100.0 * float((tops[np.isfinite(tops)] > 0).mean()), 1) if np.isfinite(tops).any() else None}
    return {"faltungen": gefaltet, "modelle": out, "vorhersagen": vorh}


def _top_ueberschuss(s: np.ndarray, r: np.ndarray, anteil: float = 0.1) -> float:
    """Mittlere Rendite des besten Zehntels nach Wertung minus Mittel aller Aktien (Prozentpunkte)."""
    ok = np.isfinite(s) & np.isfinite(r)
    if int(ok.sum()) < MIN_AKTIEN_TAG:
        return float("nan")
    ss, rr = s[ok], r[ok]
    k = max(1, int(round(len(ss) * anteil)))
    top = np.argsort(-ss, kind="mergesort")[:k]
    return float(rr[top].mean() - rr.mean())


def modellwahl(wf: dict) -> tuple[str | None, str]:
    """Bestes Modell nach Walk-forward-IC; ein komplexeres nur mit ``MODELL_VORSPRUNG`` vor dem einfacheren und t ≥ ``MODELL_MIN_T``.
    Reihenfolge der Einfachheit: Momentum < linear < Musterähnlichkeit < Kombination."""
    m = wf.get("modelle") or {}
    def ok(a):
        x = m.get(a)
        return x is not None and x["ic"] is not None and x["t"] is not None and math.isfinite(x["ic"]) and math.isfinite(x["t"]) and x["t"] >= MODELL_MIN_T and x["ic"] > 0
    gewaehlt = None
    for a in ("momentum", "linear", "aehnlichkeit", "kombination"):
        if not ok(a):
            continue
        if gewaehlt is None or m[a]["ic"] >= m[gewaehlt]["ic"] + MODELL_VORSPRUNG:
            gewaehlt = a
    if gewaehlt is None:
        return None, "kein Modell besser als das Nullmodell (Walk-forward-t-Wert unter 2 oder Rang-IC nicht positiv)"
    return gewaehlt, f"{MODELLE[gewaehlt]}: Walk-forward-Rang-IC {m[gewaehlt]['ic']:+.3f}, t = {m[gewaehlt]['t']:.1f}".replace(".", ",")


# ------------------------------------------------------------------------------------------------------ Kalibrierung


def _isoton(werte: list[float], gewichte: list[float], steigend: bool = True) -> list[float]:
    """Monotone Glättung (Pool Adjacent Violators)."""
    v = list(werte) if steigend else [-x for x in werte]
    w = list(gewichte)
    bl = [[v[i], w[i], 1] for i in range(len(v))]
    i = 0
    while i < len(bl) - 1:
        if bl[i][0] > bl[i + 1][0]:
            a, b = bl[i], bl[i + 1]
            wt = a[1] + b[1]
            bl[i] = [(a[0] * a[1] + b[0] * b[1]) / wt if wt > 0 else (a[0] + b[0]) / 2, wt, a[2] + b[2]]
            del bl[i + 1]
            i = max(i - 1, 0)
        else:
            i += 1
    out = []
    for val, _w, n in bl:
        out.extend([val] * n)
    return out if steigend else [-x for x in out]


def kalibrierung(vorhersagen: list[tuple[int, np.ndarray]], R: np.ndarray) -> dict | None:
    """Je Dezil der Wertung (Querschnitt je Tag): tatsächliche mittlere Rendite, Anteil positiv, 10-/50-/90-%-Spanne – aus
    Vorhersagen, die zum Zeitpunkt der Messung noch nicht trainiert waren (Walk-forward)."""
    buckets: list[list[float]] = [[] for _ in range(DEZILE)]
    for t, s in vorhersagen:
        r = R[t]
        ok = np.isfinite(s) & np.isfinite(r)
        if int(ok.sum()) < MIN_AKTIEN_TAG:
            continue
        q = _rang1(s[ok])
        d = np.minimum((q * DEZILE).astype(int), DEZILE - 1)
        d = np.where(q >= 1.0, DEZILE - 1, d)
        for k in range(DEZILE):
            buckets[k].extend(r[ok][d == k].tolist())
    if sum(len(b) for b in buckets) < DEZILE * 20:
        return None
    n = [len(b) for b in buckets]
    mittel = [float(np.mean(b)) if b else float("nan") for b in buckets]
    pos = [float(np.mean(np.asarray(b) > 0)) if b else float("nan") for b in buckets]
    mittel_iso = _isoton(mittel, n, True)
    pos_iso = _isoton(pos, n, True)
    return {
        "dezile": [{"dezil": k + 1, "n": n[k], "mittel_pct": _r(mittel_iso[k], 2), "mittel_roh_pct": _r(mittel[k], 2),
                    "positiv_pct": _r(100.0 * pos_iso[k], 1), "q10_pct": _r(float(np.quantile(buckets[k], 0.1)), 2) if buckets[k] else None,
                    "q50_pct": _r(float(np.quantile(buckets[k], 0.5)), 2) if buckets[k] else None,
                    "q90_pct": _r(float(np.quantile(buckets[k], 0.9)), 2) if buckets[k] else None} for k in range(DEZILE)],
        "basis_positiv_pct": _r(100.0 * float(np.mean(np.concatenate([np.asarray(b) for b in buckets if b]) > 0)), 1),
        "brier": _brier(vorhersagen, R, pos_iso),
    }


def _brier(vorhersagen: list[tuple[int, np.ndarray]], R: np.ndarray, pos: list[float]) -> dict:
    """Brier-Wert der Wahrscheinlichkeit „positiv“ aus den Dezilen gegen eine feste Basisquote (kleiner ist besser).
    Hinweis: In-sample über dieselben Walk-forward-Vorhersagen – die Kalibrierung selbst ist eine Glättung beobachteter Häufigkeiten."""
    p_all, y_all = [], []
    for t, s in vorhersagen:
        r = R[t]
        ok = np.isfinite(s) & np.isfinite(r)
        if int(ok.sum()) < MIN_AKTIEN_TAG:
            continue
        q = _rang1(s[ok])
        d = np.minimum((q * DEZILE).astype(int), DEZILE - 1)
        p_all.extend([pos[k] for k in d])
        y_all.extend((r[ok] > 0).astype(float).tolist())
    if not y_all:
        return {"modell": None, "basis": None}
    p = np.asarray(p_all)
    y = np.asarray(y_all)
    base = float(y.mean())
    return {"modell": _r(float(((p - y) ** 2).mean()), 4), "basis": _r(float(((base - y) ** 2).mean()), 4)}


def belastbarkeit(n_unabhaengig: float, modell: str | None) -> str:
    if modell is None:
        return "nicht belastbar"
    if n_unabhaengig >= BELASTBAR_MIN:
        return "belastbar"
    if n_unabhaengig >= EINGESCHRAENKT_MIN:
        return "eingeschränkt belastbar"
    return "nicht belastbar"


# ------------------------------------------------------------------------------------------------------ Gesamtlauf


def forschen(panel: Panel, horizonte: list[str] | None = None, log=None) -> dict:
    """Faktorprüfung, Redundanz, Zusatznutzen, Walk-forward-Modellvergleich, Kalibrierung und endgültige Modelle je Horizont."""
    horizonte = horizonte or list(HORIZONTE)
    fp = faktorpruefung(panel, horizonte)
    alle_tage = np.arange(len(panel.tage))
    red = redundanz(panel, alle_tage)
    je_horizont = {}
    zaehlung = {"merkmale": len(panel.merkmale), "aktien": len(panel.isins), "tage": int(len(panel.tage)), "pruefungen": len(fp["zeilen"]),
                "kombinationen": 0, "modelle": 0, "bestaetigt": sum(1 for z in fp["zeilen"] if z["bestaetigt"])}
    for h in horizonte:
        idx = panel.bekannt(h)
        zr = zeitraeume(idx)
        auswahl = zusatznutzen(panel, h, fp["zeilen"], red, zr)
        zaehlung["kombinationen"] += len(auswahl["schritte"]) + len(auswahl["uebersprungen"])
        wf = walk_forward(panel, h, auswahl)
        zaehlung["modelle"] += len(wf.get("modelle") or {})
        art, grund = modellwahl(wf)
        n_unab = unabhaengige(len(zr["entwicklung"]) + len(zr["validierung"]), panel.schritt, HORIZONTE[h])
        bel = belastbarkeit(n_unab, art)
        kal = kalibrierung(wf["vorhersagen"][art], panel.R[h]) if art else None
        endgueltig = trainieren(art, panel, h, idx, auswahl) if art else None  # alle Tage mit bekannter Rendite
        je_horizont[h] = {
            "horizont": h, "text": HORIZONT_TEXT[h], "handelstage": HORIZONTE[h], "tage_bekannt": int(len(idx)),
            "zeitraeume": {k: _tage_text(panel, v) for k, v in zr.items()}, "unabhaengig": _r(n_unab, 1),
            "auswahl": auswahl, "walk_forward": {"faltungen": wf["faltungen"], "modelle": wf.get("modelle") or {}},
            "modell": art, "modell_grund": grund, "belastbarkeit": bel, "kalibrierung": kal,
            "endmodell": endgueltig.as_dict() if endgueltig is not None and bel != "nicht belastbar" else None,
        }
        if log is not None:
            log(f"Horizont {h}: {len(auswahl['merkmale'])} Merkmale, Modell {art or '–'}, {bel}")
    paare = red.get("paare") or []
    return {"version": VERSION, "faktoren": fp, "redundanz": {"rho": REDUNDANZ_RHO, "paare": paare}, "horizonte": je_horizont,
            "zaehlung": zaehlung, "namen": panel.namen}


def _tage_text(panel: Panel, idx: np.ndarray) -> dict | None:
    if not len(idx):
        return None
    from ..util.timeutil import day_to_date

    return {"von": day_to_date(int(panel.tage[idx[0]])).isoformat(), "bis": day_to_date(int(panel.tage[idx[-1]])).isoformat(), "tage": int(len(idx))}


def _r(x, nd: int):
    if x is None:
        return None
    try:
        xf = float(x)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(xf):
        return None
    return round(xf, nd)
