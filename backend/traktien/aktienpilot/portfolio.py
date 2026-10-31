"""Depotoptimierung des Depot-Optimierers (Auftrag 18, Abschnitte 8–10 und 19 D/E; Auftrag 19, Abschnitt 7).

Nicht die zehn einzeln besten Aktien sind das beste Depot: Aktien steigen und fallen gemeinsam. Deshalb wählt der Optimierer
Aktien und Gewichte zusammen – mit der erwarteten Rendite nach Kosten je Aktie (aus der kalibrierten Prognose), den
Schwankungen und Korrelationen der letzten Handelstage (geschrumpfte Kovarianz), Höchstgewichten je Aktie und Branche und der
Liquidität. Ziel je Variante: erwartete Rendite minus Risikoabschlag (Mittelwert-Varianz) mit festem Risikoaufschlag je
Variante. Ein bestehendes Depot wird nur umgeschichtet, wenn der erwartete Vorteil die Kosten und die Unsicherheit übersteigt
(Mindestverbesserung, Halteband, Toleranz bei Gewichten).

Alle Zahlen sind Modellwerte aus den angegebenen Daten – keine Zusage künftiger Renditen.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

VERSION = "portfolio-1"

# Varianten (Auftrag 18, Abschnitt 8.4): Horizont der Prognose, Risikoabschlag λ (größer = vorsichtiger), Höchstgewicht
VARIANTEN: dict[str, dict] = {
    "rendite": {"name": "Maximale Renditechance", "horizont": "w12", "lambda": 1.0, "erklaerung": "möglichst hohe erwartete Rendite innerhalb der Grenzen"},
    "ausgewogen": {"name": "Ausgewogen", "horizont": "w12", "lambda": 4.0, "erklaerung": "erwartete Rendite und begrenztes Risiko"},
    "stabil": {"name": "Stabiler Aufwärtstrend", "horizont": "w12", "lambda": 8.0, "stabil": True,
               "erklaerung": "Aktien mit möglichst gleichmäßigem Anstieg, geringe Schwankung"},
    "kurz": {"name": "Kurzfristige Chancen", "horizont": "w2", "lambda": 4.0, "erklaerung": "die nächsten Handelstage und Wochen"},
    "mittel": {"name": "Mittelfristige Chancen", "horizont": "w12", "lambda": 4.0, "erklaerung": "die nächsten 1 bis 6 Monate"},
    "lang": {"name": "Langfristige Chancen", "horizont": "w52", "lambda": 4.0, "erklaerung": "die nächsten 6 bis 12 Monate"},
}
# Standardvariante je Risikoprofil der Pilot-Einrichtung (kein zweiter Fragebogen; Namen aus ``profil.py``)
PROFIL_VARIANTE = {"vorsichtig": "stabil", "ausgewogen": "ausgewogen", "wachstumsorientiert": "rendite", "offensiv": "rendite"}

SCHRUMPFUNG = 0.3  # Kovarianz: 70 % Stichprobe, 30 % konstante Korrelation (stabiler bei wenigen Tagen)
KOVARIANZ_TAGE = 120
KORRELATION_GRENZE = 0.85  # zwei fast gleich laufende Aktien nicht beide aufnehmen


@dataclass(frozen=True)
class Einstellungen:
    """Depotparameter (Auftrag 18, Abschnitt 17). Vorgaben aus ``config/optimierer.yaml``; die App ändert sie per Eingang."""
    variante: str = "ausgewogen"
    anzahl: int = 10
    kapital_eur: float = 10_000.0
    max_gewicht_pct: float = 20.0
    max_branche_pct: float = 35.0
    min_umsatz_eur: float = 2_000_000.0
    reserve_pct: float = 0.0
    umschichtung: str = "woechentlich"  # taeglich | woechentlich | signal
    mindestverbesserung_pp: float = 1.0  # erwarteter Vorteil eines Tauschs nach Kosten mindestens (Prozentpunkte)
    toleranz_pp: float = 3.0  # kleinere Gewichtsänderungen werden nicht umgesetzt
    halte_faktor: float = 2.0  # gehaltene Aktie bleibt, solange sie unter den besten halte_faktor × anzahl Kandidaten ist

    def as_dict(self) -> dict:
        return {"variante": self.variante, "anzahl": self.anzahl, "kapital_eur": self.kapital_eur, "max_gewicht_pct": self.max_gewicht_pct,
                "max_branche_pct": self.max_branche_pct, "min_umsatz_eur": self.min_umsatz_eur, "reserve_pct": self.reserve_pct,
                "umschichtung": self.umschichtung, "mindestverbesserung_pp": self.mindestverbesserung_pp, "toleranz_pp": self.toleranz_pp,
                "halte_faktor": self.halte_faktor}


@dataclass
class Kandidat:
    isin: str
    erwartet_pct: float  # erwartete Rendite über den Horizont (kalibriert, vor Kosten)
    kosten_pct: float  # Kauf und Verkauf in Prozent der Position
    wertung_rang: float  # Querschnittsrang der Modellwertung 0–1
    branche: str | None = None
    waehrung: str | None = None
    umsatz_eur: float | None = None
    stabil: float | None = None  # Rang eines Stabilitätsmerkmals (Variante „stabil“)
    extra: dict = field(default_factory=dict)

    @property
    def netto_pct(self) -> float:
        return self.erwartet_pct - self.kosten_pct


# ------------------------------------------------------------------------------------------------------ Kovarianz


def renditen_matrix(reihen: dict[str, tuple[np.ndarray, np.ndarray]], isins: list[str], bis_tag: int, tage: int = KOVARIANZ_TAGE) -> np.ndarray:
    """Tägliche Log-Renditen in Euro der letzten ``tage`` gemeinsamen Kalendertage (Spalten = ``isins``); fehlende = 0."""
    alle = sorted({int(d) for i in isins if i in reihen for d in reihen[i][0] if int(d) <= bis_tag})[-(tage + 1):]
    if len(alle) < 3:
        return np.zeros((0, len(isins)))
    pos = {d: k for k, d in enumerate(alle)}
    preise = np.full((len(alle), len(isins)), np.nan)
    for j, isin in enumerate(isins):
        if isin not in reihen:
            continue
        days, eur = reihen[isin]
        for d, p in zip(days, eur):
            k = pos.get(int(d))
            if k is not None and p > 0:
                preise[k, j] = p
    # fehlende Tage: letzter Kurs (keine Bewegung)
    for j in range(len(isins)):
        col = preise[:, j]
        last = np.nan
        for k in range(len(col)):
            if np.isfinite(col[k]):
                last = col[k]
            elif np.isfinite(last):
                col[k] = last
    with np.errstate(invalid="ignore", divide="ignore"):
        r = np.diff(np.log(preise), axis=0)
    return np.where(np.isfinite(r), r, 0.0)


def kovarianz(r: np.ndarray, schrumpfung: float = SCHRUMPFUNG) -> np.ndarray:
    """Geschrumpfte Kovarianz täglicher Renditen: Stichprobe gemischt mit konstanter mittlerer Korrelation."""
    n = r.shape[1]
    if r.shape[0] < 3 or n == 0:
        return np.eye(n) * 0.0004
    S = np.cov(r, rowvar=False)
    S = np.atleast_2d(S)
    sd = np.sqrt(np.clip(np.diag(S), 1e-10, None))
    C = S / np.outer(sd, sd)
    off = C[~np.eye(n, dtype=bool)]
    rho = float(np.nanmean(off)) if off.size else 0.0
    F = rho * np.outer(sd, sd)
    np.fill_diagonal(F, sd * sd)
    return (1 - schrumpfung) * S + schrumpfung * F


# ------------------------------------------------------------------------------------------------------ Optimierung


def _projizieren(w: np.ndarray, oben: np.ndarray, summe: float, gruppen: list[np.ndarray], gruppen_max: float, schritte: int = 60) -> np.ndarray:
    """Gewichte auf 0 ≤ w ≤ oben, Gruppen ≤ gruppen_max und Summe = summe bringen (wiederholtes Kappen und Umverteilen)."""
    w = np.clip(w, 0.0, oben)
    for _ in range(schritte):
        for g in gruppen:
            s = float(w[g].sum())
            if s > gruppen_max + 1e-12:
                w[g] *= gruppen_max / s
        tot = float(w.sum())
        if tot <= 0:
            w = np.minimum(oben, summe / len(w))
            continue
        frei = w < oben - 1e-12
        diff = summe - tot
        if abs(diff) < 1e-9:
            break
        if diff > 0:
            room = np.where(frei, oben - w, 0.0)
            if room.sum() <= 1e-12:
                break
            w = w + room / room.sum() * diff
        else:
            w = w * (summe / tot)
        w = np.clip(w, 0.0, oben)
    return w


def korrelation(r: np.ndarray) -> np.ndarray:
    """Stichproben-Korrelation täglicher Renditen (ohne Schrumpfung – für die Grenze „fast gleich laufend“)."""
    n = r.shape[1]
    if r.shape[0] < 3 or n == 0:
        return np.eye(n)
    S = np.atleast_2d(np.cov(r, rowvar=False))
    sd = np.sqrt(np.clip(np.diag(S), 1e-12, None))
    return S / np.outer(sd, sd)


def optimieren(kand: list[Kandidat], Sigma_h: np.ndarray, *, anzahl: int, lam: float, max_gewicht: float, max_branche: float,
               reserve: float = 0.0, korr: np.ndarray | None = None) -> np.ndarray:
    """Gewichte (Summe 1 − Reserve) für höchstens ``anzahl`` Kandidaten: gierige Auswahl nach dem Zuwachs der Zielgröße
    w·(μ − Kosten) − λ/2·wᵀΣw, danach Gewichte per projiziertem Gradientenverfahren mit Höchstgewicht je Aktie und Branche.
    Kandidaten mit nicht positiver Erwartung nach Kosten kommen nicht ins Depot."""
    n = len(kand)
    mu = np.array([k.netto_pct for k in kand]) / 100.0
    w = np.zeros(n)
    if n == 0:
        return w
    summe = 1.0 - reserve
    erlaubt = [i for i in range(n) if mu[i] > 0]
    gewaehlt: list[int] = []
    branchen: dict[str, list[int]] = {}

    def ziel(idx: list[int]) -> float:
        if not idx:
            return 0.0
        ww = np.zeros(n)
        ww[idx] = summe / len(idx)
        return float(ww @ mu - lam / 2.0 * ww @ Sigma_h @ ww)

    sd = np.sqrt(np.clip(np.diag(Sigma_h), 1e-12, None))
    if korr is None:
        korr = Sigma_h / np.outer(sd, sd)
    # je Branche höchstens so viele Aktien, wie bei gleichen Gewichten unter die Branchengrenze passen
    max_je_branche = max(1, int(math.floor(max_branche * anzahl / summe + 1e-9)))
    while len(gewaehlt) < anzahl:
        best, best_val = None, ziel(gewaehlt)
        for i in erlaubt:
            if i in gewaehlt:
                continue
            br = kand[i].branche
            if br and len(branchen.get(br, [])) >= max_je_branche:
                continue
            if any(korr[i, g] > KORRELATION_GRENZE for g in gewaehlt):
                continue
            val = ziel(gewaehlt + [i])
            if best is None or val > best_val + 1e-12:
                best, best_val = i, val
        if best is None:
            break
        gewaehlt.append(best)
        if kand[best].branche:
            branchen.setdefault(kand[best].branche, []).append(best)
    if not gewaehlt:
        return w
    idx = np.array(gewaehlt)
    S = Sigma_h[np.ix_(idx, idx)]
    m = mu[idx]
    oben = np.full(len(idx), max_gewicht)
    gruppen = [np.array([k for k, i in enumerate(idx) if kand[i].branche == b]) for b in {kand[i].branche for i in idx if kand[i].branche}]
    x = np.full(len(idx), summe / len(idx))
    x = _projizieren(x, oben, summe, gruppen, max_branche)
    schritt = 0.5 / max(1e-9, lam * float(np.max(np.abs(np.linalg.eigvalsh(S)))) + 1e-9)
    for _ in range(300):
        grad = m - lam * S @ x
        x_neu = _projizieren(x + schritt * grad, oben, summe, gruppen, max_branche)
        if float(np.abs(x_neu - x).max()) < 1e-7:
            x = x_neu
            break
        x = x_neu
    w[idx] = x
    return w


def depot_kennzahlen(w: np.ndarray, kand: list[Kandidat], Sigma_h: np.ndarray, r_taeglich: np.ndarray, h_tage: int) -> dict:
    """Erwartete Depotrendite nach Kosten, Schwankung über den Horizont, Verlustszenario aus der Historie (5-%-Quantil der
    Depotrendite über ``h_tage`` Handelstage mit den heutigen Gewichten), Konzentration."""
    sel = w > 1e-9
    mu = np.array([k.erwartet_pct for k in kand])
    kosten = np.array([k.kosten_pct for k in kand])
    erwartet = float(w @ mu)
    kost = float(w @ kosten)
    vol = float(math.sqrt(max(0.0, float(w @ Sigma_h @ w)))) * 100.0
    verlust = None
    if r_taeglich.shape[0] >= h_tage + 5 and sel.any():
        port = r_taeglich @ w
        roll = np.array([port[a:a + h_tage].sum() for a in range(0, len(port) - h_tage + 1)])
        if len(roll):
            verlust = float((math.exp(float(np.quantile(roll, 0.05))) - 1.0) * 100.0)
    branchen: dict[str, float] = {}
    waehrungen: dict[str, float] = {}
    for k, wi in zip(kand, w):
        if wi <= 1e-9:
            continue
        branchen[k.branche or "unbekannt"] = branchen.get(k.branche or "unbekannt", 0.0) + float(wi) * 100.0
        waehrungen[k.waehrung or "unbekannt"] = waehrungen.get(k.waehrung or "unbekannt", 0.0) + float(wi) * 100.0
    eff_n = float(1.0 / float((w[sel] ** 2).sum())) if sel.any() else 0.0
    corr = None
    if int(sel.sum()) >= 2:
        idx = np.nonzero(sel)[0]
        S = Sigma_h[np.ix_(idx, idx)]
        sd = np.sqrt(np.clip(np.diag(S), 1e-12, None))
        C = S / np.outer(sd, sd)
        corr = float(C[~np.eye(len(idx), dtype=bool)].mean())
    return {"erwartet_pct": round(erwartet, 2), "kosten_pct": round(kost, 2), "erwartet_nach_kosten_pct": round(erwartet - kost, 2),
            "schwankung_pct": round(vol, 2), "verlustszenario_pct": None if verlust is None else round(verlust, 2),
            "positionen": int(sel.sum()), "effektive_anzahl": round(eff_n, 1), "mittlere_korrelation": None if corr is None else round(corr, 2),
            "branchen": {k: round(v, 1) for k, v in sorted(branchen.items(), key=lambda x: -x[1])},
            "waehrungen": {k: round(v, 1) for k, v in sorted(waehrungen.items(), key=lambda x: -x[1])}}


# ------------------------------------------------------------------------------------------------------ Umschichtung


def veraenderungen(alt: dict[str, float], ziel: dict[str, float], kand: dict[str, Kandidat], rang: dict[str, int], e: Einstellungen
                   ) -> tuple[dict[str, float], list[dict]]:
    """Vom bisherigen Depot ``alt`` (Gewichte in %) zum neuen: Halteband, Mindestverbesserung und Toleranz verhindern unnötiges
    Hin und Her (Auftrag 18, Abschnitt 10). Rückgabe: umgesetzte Gewichte in % und je Aktie Empfehlung mit Begründung."""
    neu = dict(ziel)
    gruende: dict[str, str] = {}
    halte_rang = int(e.halte_faktor * e.anzahl)
    # 1. gehaltene Aktien, die nicht mehr im Ziel sind: halten, solange im Halteband und kein Tausch mit genug Vorteil
    for isin, w_alt in alt.items():
        if isin in neu:
            continue
        k = kand.get(isin)
        r = rang.get(isin)
        if k is None or r is None:
            gruende[isin] = "keine aktuelle Bewertung (Daten fehlen) – Verkauf"
            continue
        if r > halte_rang:
            gruende[isin] = f"nicht mehr unter den besten {halte_rang} Kandidaten (Platz {r}) – Verkauf"
            continue
        if k.netto_pct <= 0:
            gruende[isin] = "erwartete Rendite nach Kosten nicht mehr positiv – Verkauf"
            continue
        # schwächste neue Aktie, die nicht schon gehalten wird
        neue = [i for i in neu if i not in alt and i in kand]
        if not neue:
            continue
        schwach = min(neue, key=lambda i: kand[i].netto_pct)
        vorteil = kand[schwach].netto_pct - k.netto_pct - k.kosten_pct  # Tausch kostet auch den Verkauf der gehaltenen
        if vorteil < e.mindestverbesserung_pp:
            neu[isin] = neu.pop(schwach)
            gruende[isin] = (f"halten: Tausch gegen die schwächste neue Aktie brächte nach Kosten nur {vorteil:+.2f} Prozentpunkte "
                             f"(Mindestverbesserung {e.mindestverbesserung_pp:g})").replace(".", ",")
            gruende[schwach] = "nicht aufgenommen: Vorteil gegenüber einer gehaltenen Aktie zu klein"
        else:
            gruende[isin] = f"ersetzt: eine andere Aktie erwartet nach Kosten {vorteil:+.2f} Prozentpunkte mehr – Verkauf".replace(".", ",")
    # 2. Toleranz bei Gewichten gehaltener Aktien
    for isin in list(neu):
        if isin in alt and abs(neu[isin] - alt[isin]) < e.toleranz_pp:
            neu[isin] = alt[isin]
    total = sum(neu.values())
    ziel_summe = 100.0 - e.reserve_pct
    if total > 0:
        neu = {i: w * ziel_summe / total for i, w in neu.items()}
    zeilen = []
    for isin in sorted(set(alt) | set(neu) | set(gruende), key=lambda i: (-neu.get(i, 0.0), i)):
        a, n = alt.get(isin, 0.0), neu.get(isin, 0.0)
        if a <= 0 and n > 0:
            art = "kaufen"
        elif a > 0 and n <= 0:
            art = "verkaufen"
        elif a > 0 and n > 0 and n - a >= e.toleranz_pp:
            art = "aufstocken"
        elif a > 0 and n > 0 and a - n >= e.toleranz_pp:
            art = "reduzieren"
        elif n > 0:
            art = "halten"
        else:
            art = "nicht_aufnehmen"
        zeilen.append({"isin": isin, "art": art, "gewicht_alt_pct": round(a, 1), "gewicht_neu_pct": round(n, 1), "grund": gruende.get(isin)})
    return {i: round(w, 2) for i, w in neu.items() if w > 0}, zeilen
