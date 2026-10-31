"""Depot-Optimierer: Forschungslauf, tägliche Empfehlung und Prognosekontrolle (Aufträge vom 31.10.2026: 18 „Intelligenter
Depot-Optimierer“, 19 „Alle Informationen der Aktien-App nutzen“, Nachtrag 20:16 Uhr).

Ablauf („Optimierungszyklus“, Auftrag 18 Abschnitt 13):

1. **Daten sammeln** – Kurse und Rechenstand aus dem Zustand; im Forschungslauf ältere Kerzen aus derselben kostenlosen
   Quelle (``langhistorie.py``).
2. **Muster suchen, Strategien erzeugen, historisch testen, unabhängig validieren, Modelle vergleichen** – Merkmalspanel aus
   dem zentralen Katalog (``merkmale.py``) an festen Entscheidungstagen, Auswertung in ``forschung.py``.
3. **Depot optimieren und Empfehlung erstellen** – je Horizont kalibrierte Prognosen, Eignungswert, Depotvarianten mit
   Korrelationen und Grenzen (``portfolio.py``), Veränderungen gegenüber der letzten Empfehlung mit Umschichtungsschutz.
4. **Mit Spielgeld vorwärts prüfen** – jede Prognose und Empfehlung wird mit Zeitstempel, Datenstand und Modell unveränderlich
   gespeichert (``ap_prognose``, ``ap_empfehlung``) und später mit den tatsächlichen Kursen verglichen (Prognosekontrolle).

Der Forschungslauf läuft als eigener Workflow (Rechenkern je Entscheidungstag); die tägliche Empfehlung rechnet der tägliche
Lauf mit dem neuesten geprüften Modell nach jedem neuen Handelstag. Öffentlich erscheinen nur Zählungen.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import re
import sqlite3
import zlib
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import yaml

from ..config import CONFIG_DIR, MethodConfig
from ..store import db
from ..util import crypto
from ..util.timeutil import date_to_day, day_to_date
from . import forschung as fo
from . import katalog as kat
from . import kosten, merkmale, portfolio

SCHEMA = "tr-optimierer/1"
ORDNER = "optimierer"  # Ablage auf dem Branch „spielgeld-labor“ (derselbe Kanal wie das Labor)
DATEI_RE = re.compile(r"^(\d{8}T\d{6}Z)-(opt-[0-9a-f]{12})$")
STAENDE_BEHALTEN = 3


class OptimiererFehler(ValueError):
    """Ungültige Konfiguration, zu kurze Historie oder beschädigtes Ergebnis (Meldung auf Deutsch)."""


# ------------------------------------------------------------------------------------------------------ Konfiguration


@dataclass(frozen=True)
class OptimiererConfig:
    version: str
    jahre: float
    schritt: int
    min_umsatz_forschung_eur: float
    max_tage: int
    einstellungen: portfolio.Einstellungen
    kandidaten: int
    spitze: int
    stichprobe: int


def load_config(path: Path | None = None) -> OptimiererConfig:
    raw = yaml.safe_load((path or CONFIG_DIR / "optimierer.yaml").read_text(encoding="utf-8")) or {}
    try:
        f = raw["forschung"]
        e = raw["empfehlung"]
        cfg = OptimiererConfig(
            version=str(raw["version"]), jahre=float(f["jahre"]), schritt=int(f["schritt"]), min_umsatz_forschung_eur=float(f["min_umsatz_eur"]),
            max_tage=int(f["max_tage"]),
            einstellungen=portfolio.Einstellungen(
                variante=str(e["variante"]), anzahl=int(e["anzahl"]), kapital_eur=float(e["kapital_eur"]), max_gewicht_pct=float(e["max_gewicht_pct"]),
                max_branche_pct=float(e["max_branche_pct"]), min_umsatz_eur=float(e["min_umsatz_eur"]), reserve_pct=float(e["reserve_pct"]),
                umschichtung=str(e["umschichtung"]), mindestverbesserung_pp=float(e["mindestverbesserung_pp"]), toleranz_pp=float(e["toleranz_pp"]),
                halte_faktor=float(e["halte_faktor"])),
            kandidaten=int(e["kandidaten"]), spitze=int(e["spitze"]), stichprobe=int(e["stichprobe"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise OptimiererFehler(f"optimierer.yaml unvollständig ({exc})") from exc
    pruefen_einstellungen(cfg.einstellungen)
    if not (0.5 <= cfg.jahre <= 15) or not (1 <= cfg.schritt <= 20) or cfg.max_tage < 10:
        raise OptimiererFehler("optimierer.yaml: forschung außerhalb der Grenzen")
    return cfg


def pruefen_einstellungen(e: portfolio.Einstellungen) -> portfolio.Einstellungen:
    """Grenzen der Depotparameter (gleich für Konfiguration und Eingang aus der App)."""
    if e.variante not in portfolio.VARIANTEN:
        raise OptimiererFehler(f"Variante muss eine von {', '.join(portfolio.VARIANTEN)} sein")
    if not (3 <= e.anzahl <= 30):
        raise OptimiererFehler("Anzahl Aktien: 3 bis 30")
    if not (500 <= e.kapital_eur <= 10_000_000):
        raise OptimiererFehler("Spielgeldkapital: 500 bis 10.000.000 EUR")
    if not (5 <= e.max_gewicht_pct <= 100) or e.max_gewicht_pct * e.anzahl < 100 - e.reserve_pct - 1e-9:
        raise OptimiererFehler("Höchstgewicht je Aktie zu klein für die Anzahl Aktien (oder über 100 %)")
    if not (10 <= e.max_branche_pct <= 100):
        raise OptimiererFehler("Höchstgewicht je Branche: 10 bis 100 %")
    if not (0 <= e.min_umsatz_eur <= 1e10) or not (0 <= e.reserve_pct <= 50):
        raise OptimiererFehler("Mindestliquidität oder Reserve außerhalb der Grenzen")
    if e.umschichtung not in ("taeglich", "woechentlich", "signal"):
        raise OptimiererFehler("Umschichtung: täglich, wöchentlich oder nach Signal")
    if not (0 <= e.mindestverbesserung_pp <= 20) or not (0 <= e.toleranz_pp <= 20) or not (1 <= e.halte_faktor <= 5):
        raise OptimiererFehler("Umschichtungsschutz außerhalb der Grenzen")
    return e


# ------------------------------------------------------------------------------------------------------ Merkmalspanel


def umsatz_eur(ctx: kat.Kontext) -> np.ndarray:
    """Ø Tagesumsatz in Euro je Aktie des Kontexts (aus derselben Rechnung wie die Umsatzgruppen); NaN, wenn unbestimmt."""
    out = np.full(len(ctx.isins), np.nan)
    turnover = getattr(ctx.comp, "turnover", None) if ctx.comp is not None else None
    rate = ctx.markt.eur_rate("USD", int(ctx.tag)) if ctx.markt is not None else None
    if not turnover or rate is None:
        return out
    for k, t in enumerate(turnover):
        if t is not None and getattr(t, "determined", False):
            out[k] = float(t.avg_usd) * rate
    return out


def investierbar(ctx: kat.Kontext, min_umsatz: float) -> np.ndarray:
    """Aktien, die der Optimierer betrachtet: kaufbare Einzelaktie, Umsatz ab ``min_umsatz`` (Euro, Ø Tagesumsatz)."""
    u = umsatz_eur(ctx)
    typ = np.array([(ctx.stamm.get(i) or {}).get("typ", "aktie") == "aktie" for i in ctx.isins], dtype=bool)
    return typ & np.isfinite(u) & (u >= min_umsatz)


class Panelbau:
    """Merkmalsränge je Entscheidungstag sammeln (nur Daten bis zum Tag; Kontext aus der Kontextquelle des historischen Tests)."""

    def __init__(self, quelle, archiv, eintraege: dict, liste: list[merkmale.Merkmal], *, min_umsatz_eur: float) -> None:
        self.quelle = quelle
        self.archiv = archiv
        self.eintraege = eintraege
        self.liste = liste
        self.min_umsatz = min_umsatz_eur
        self.tage: list[int] = []
        self.isins: list[list[str]] = []
        self.X: list[np.ndarray] = []
        self.fehlend: dict[str, int] = {}

    def kontext(self, D: int) -> kat.Kontext:
        base = self.quelle.kontext(int(D))
        return kat.Kontext(tag=base.tag, isins=base.isins, method=base.method, comp=base.comp, markt=base.markt, cfg=base.cfg, stamm=base.stamm,
                           fakten=base.fakten, modus=base.modus, archiv=self.archiv, _cache=base._cache, _index=base._index)

    def __call__(self, D: int) -> None:
        ctx = self.kontext(D)
        X, fehlend = merkmale.matrix(ctx, self.eintraege, self.liste)
        for key in fehlend:
            self.fehlend[key] = self.fehlend.get(key, 0) + 1
        mask = investierbar(ctx, self.min_umsatz)
        self.tage.append(int(D))
        self.isins.append([ctx.isins[i] for i in np.nonzero(mask)[0]])
        self.X.append(fo.raenge(X[mask]).astype(np.float16) if mask.any() else np.zeros((0, len(self.liste)), dtype=np.float16))

    def panel(self, markt, namen: dict[str, str] | None = None, schritt: int = 5) -> fo.Panel:
        alle = sorted({i for liste in self.isins for i in liste})
        pos = {isin: k for k, isin in enumerate(alle)}
        T, N, F = len(self.tage), len(alle), len(self.liste)
        X = np.full((T, N, F), np.nan, dtype=np.float16)
        for t, (isins, Xt) in enumerate(zip(self.isins, self.X)):
            if isins:
                X[t, [pos[i] for i in isins]] = Xt
        tage = np.asarray(self.tage, dtype=np.int64)
        R = folgerenditen(markt, alle, tage, fo.HORIZONTE)
        return fo.Panel(tage=tage, isins=alle, merkmale=[m.schluessel for m in self.liste], X=X, R=R, schritt=schritt,
                        namen=namen or {m.schluessel: m.name for m in self.liste})


def eur_reihe(markt, isin: str) -> tuple[np.ndarray, np.ndarray] | None:
    """(Tage, Schlusskurs in Euro) einer Aktie; ohne Wechselkurs bleibt der Kurs in Handelswährung (Rendite währungsneutral)."""
    s = markt.series.get(isin)
    if s is None or not len(s.days):
        return None
    close = np.asarray(s.close, dtype=np.float64)
    if s.currency and s.currency != "EUR":
        rates = np.array([markt.eur_rate(s.currency, int(d)) or np.nan for d in s.days])
        if np.isfinite(rates).mean() > 0.9:
            # fehlende Tage mit dem letzten Kurs davor
            last = np.nan
            for k in range(len(rates)):
                if np.isfinite(rates[k]):
                    last = rates[k]
                else:
                    rates[k] = last
            close = close * rates
    return np.asarray(s.days, dtype=np.int64), close


def folgerenditen(markt, isins: list[str], tage: np.ndarray, horizonte: dict[str, int]) -> dict[str, np.ndarray]:
    """Rendite in Prozent von Schlusskurs am Entscheidungstag (letzte Sitzung bis dahin, höchstens 5 Tage alt) bis
    ``n`` Sitzungen der Aktie später; NaN, solange die Sitzung noch nicht stattgefunden hat."""
    T, N = len(tage), len(isins)
    out = {h: np.full((T, N), np.nan, dtype=np.float32) for h in horizonte}
    for j, isin in enumerate(isins):
        r = eur_reihe(markt, isin)
        if r is None:
            continue
        days, p = r
        k = np.searchsorted(days, tage, side="right") - 1
        frisch = (k >= 0) & (tage - days[np.clip(k, 0, None)] <= 5)
        for h, n in horizonte.items():
            kn = k + n
            ok = frisch & (kn < len(days))
            if not ok.any():
                continue
            a = p[k[ok]]
            b = p[kn[ok]]
            with np.errstate(invalid="ignore", divide="ignore"):
                val = (b / a - 1.0) * 100.0
            col = np.full(T, np.nan)
            col[ok] = np.where((a > 0) & (b > 0), val, np.nan)
            out[h][:, j] = col.astype(np.float32)
    return out


def benchmarks(markt, cfg, tage: np.ndarray, kern_welt: float = 0.7) -> dict[str, dict[str, np.ndarray]]:
    """Renditen von Welt-ETF und Robo-Kern (Welt-ETF und Geldmarkt im Verhältnis des Vorgabeprofils) je Entscheidungstag."""
    out: dict[str, dict[str, np.ndarray]] = {h: {} for h in fo.HORIZONTE}
    welt = cfg.msci_world.isin if getattr(cfg, "msci_world", None) else None
    geld = cfg.geldmarkt.isin if getattr(cfg, "geldmarkt", None) else None
    ids = [i for i in (welt, geld) if i]
    if not ids:
        return out
    R = folgerenditen(markt, ids, tage, fo.HORIZONTE)
    for h in fo.HORIZONTE:
        if welt:
            out[h]["welt"] = R[h][:, ids.index(welt)].astype(np.float64)
        if welt and geld:
            out[h]["kern"] = kern_welt * R[h][:, ids.index(welt)].astype(np.float64) + (1 - kern_welt) * R[h][:, ids.index(geld)].astype(np.float64)
    return out


# ------------------------------------------------------------------------------------------------------ Prognose heute


def _dezil(rang: np.ndarray) -> np.ndarray:
    d = np.minimum((rang * fo.DEZILE).astype(int), fo.DEZILE - 1)
    return np.where(rang >= 1.0, fo.DEZILE - 1, d)


def prognosen(ergebnis: dict, X: np.ndarray, liste: list[merkmale.Merkmal], mask: np.ndarray) -> dict[str, dict]:
    """Je Horizont mit Endmodell: Wertung, Rang, Dezil und kalibrierte Erwartung je Aktie (nur ``mask``; sonst NaN).
    Dieselbe Bewertungsfunktion wie im Walk-forward (``forschung.bewerten``) auf den heutigen Querschnittsrängen."""
    keys = [m.schluessel for m in liste]
    R = np.full(X.shape, np.nan)
    if mask.any():
        R[mask] = fo.raenge(X[mask])
    out = {}
    for h, info in (ergebnis.get("horizonte") or {}).items():
        md, kal = info.get("endmodell"), info.get("kalibrierung")
        if not md or not kal:
            continue
        modell = fo.Modell.from_dict(md)

        def rang_von(key: str) -> np.ndarray:
            return R[:, keys.index(key)] if key in keys else np.full(X.shape[0], np.nan)
        s = fo.bewerten(modell, rang_von, X.shape[0])
        s = np.where(mask, s, np.nan)
        rang = fo.raenge(s)
        dez = np.where(np.isfinite(rang), _dezil(np.nan_to_num(rang)), -1)
        tab = kal["dezile"]

        def spalte(name):
            return np.array([tab[d][name] if d >= 0 and tab[d][name] is not None else np.nan for d in dez], dtype=np.float64)
        out[h] = {"wertung": s, "rang": rang, "dezil": dez, "erwartet": spalte("mittel_pct"), "positiv": spalte("positiv_pct"),
                  "q10": spalte("q10_pct"), "q50": spalte("q50_pct"), "q90": spalte("q90_pct"), "modell": md, "merkmale": modell_merkmale(modell)}
    return out


def modell_merkmale(m: fo.Modell) -> list[tuple[str, int]]:
    if m.art == "kombination":
        seen, out = set(), []
        for p in m.teile or []:
            for key, r in modell_merkmale(p):
                if key not in seen:
                    seen.add(key)
                    out.append((key, r))
        return out
    return list(zip(m.merkmale, m.richtungen))


def eignung(p: dict, kosten_pct: np.ndarray) -> np.ndarray:
    """Eignungswert 0–100 je Aktie: Querschnittsrang der Erwartung nach Kosten je Unsicherheit (halbe 10–90-%-Spanne). Kein
    Gewinnwahrscheinlichkeit – nur eine Reihenfolge der Kandidaten für diesen Horizont."""
    breite = np.maximum(1.0, (p["q90"] - p["q10"]) / 2.0)
    wert = (p["erwartet"] - kosten_pct) / breite
    return fo.raenge(wert) * 100.0


def begruendung(isin_index: int, rang_matrix: np.ndarray, keys: list[str], namen: dict[str, str], modell_merkmale_liste: list[tuple[str, int]]
                ) -> tuple[list[str], list[str]]:
    """Was für und was gegen die Aktie spricht – aus den Merkmalen des Modells (ausgerichtet nach ihrer bestätigten Richtung):
    oberes Fünftel = dafür, unteres Fünftel = dagegen. Dazu bestätigte Merkmale außerhalb des Modells als Hinweis."""
    dafuer, dagegen = [], []
    for key, richtung in modell_merkmale_liste:
        if key not in keys:
            continue
        v = rang_matrix[isin_index, keys.index(key)]
        if not np.isfinite(v):
            continue
        a = (v - 0.5) * (richtung or 1)
        name = namen.get(key, key)
        if a >= 0.3:
            dafuer.append(f"{name}: obere {max(1, int(round((1 - (v if richtung >= 0 else 1 - v)) * 100)))} %")
        elif a <= -0.3:
            dagegen.append(f"{name}: untere {max(1, int(round(((v if richtung >= 0 else 1 - v)) * 100)))} %")
    return dafuer[:4], dagegen[:4]


def empfehlen(*, ctx: kat.Kontext, eintraege: dict, liste: list[merkmale.Merkmal], ergebnis: dict, einstellungen: portfolio.Einstellungen,
              ap_cfg, ocfg: OptimiererConfig, alt: dict[str, dict] | None = None) -> dict:
    """Empfehlung zum Stichtag des Kontexts: Prognosen je Horizont, Rangliste nach Eignung, alle Depotvarianten mit Kennzahlen
    und Veränderungen gegenüber der letzten Empfehlung (``alt``: Variante → Gewichte in %)."""
    X, fehlend = merkmale.matrix(ctx, eintraege, liste)
    mask = investierbar(ctx, einstellungen.min_umsatz_eur)
    keys = [m.schluessel for m in liste]
    rang_matrix = np.full(X.shape, np.nan)
    if mask.any():
        rang_matrix[mask] = fo.raenge(X[mask])
    prog = prognosen(ergebnis, X, liste, mask)
    umsatz = umsatz_eur(ctx)
    D = int(ctx.tag)
    stamm = ctx.stamm
    markt = ctx.markt
    namen = ergebnis.get("namen") or {m.schluessel: m.name for m in liste}
    kurse = {}
    for k in np.nonzero(mask)[0]:
        isin = ctx.isins[k]
        r = eur_reihe(markt, isin) if markt is not None else None
        s = markt.series.get(isin) if markt is not None else None
        if r is not None and s is not None:
            kk = int(np.searchsorted(r[0], D, side="right")) - 1
            if kk >= 0:
                kurse[isin] = {"kurs": round(float(s.close[kk]), 4), "waehrung": s.currency, "kurs_eur": round(float(r[1][kk]), 4),
                               "datum": day_to_date(int(r[0][kk])).isoformat(), "boerse": s.exchange or None}
    pos_pct = einstellungen.kapital_eur / max(1, einstellungen.anzahl)
    kosten_pct = np.array([kosten.rundreise_pct(ap_cfg.handelskosten, turnover_eur=float(umsatz[k]) if np.isfinite(umsatz[k]) else None,
                                                currency=(stamm.get(ctx.isins[k]) or {}).get("waehrung") or "EUR", position_eur=pos_pct)
                           for k in range(len(ctx.isins))])
    horizonte = {}
    for h, p in prog.items():
        e = eignung(p, kosten_pct)
        e = np.where(mask & np.isfinite(p["erwartet"]), e, np.nan)
        p["eignung"] = e
        order = [int(k) for k in np.argsort(-np.nan_to_num(e, nan=-1.0), kind="mergesort") if np.isfinite(e[k])]
        rangliste = []
        for platz, k in enumerate(order[:30], start=1):
            dafuer, dagegen = begruendung(k, rang_matrix, keys, namen, p["merkmale"])
            rangliste.append(_zeile(ctx.isins[k], k, platz, p, kosten_pct, umsatz, stamm, kurse, dafuer, dagegen))
        info = ergebnis["horizonte"][h]
        horizonte[h] = {"horizont": h, "text": fo.HORIZONT_TEXT[h], "modell": info.get("modell"), "belastbarkeit": info.get("belastbarkeit"),
                        "aktien": int(np.isfinite(e).sum()), "rangliste": rangliste, "_order": order}
    # nicht belastbare Horizonte ausdrücklich
    for h, info in (ergebnis.get("horizonte") or {}).items():
        if h not in horizonte:
            horizonte[h] = {"horizont": h, "text": fo.HORIZONT_TEXT[h], "modell": info.get("modell"), "belastbarkeit": info.get("belastbarkeit") or "nicht belastbar",
                            "aktien": 0, "rangliste": [], "grund": info.get("modell_grund"), "_order": []}
    varianten = {}
    for v, vinfo in portfolio.VARIANTEN.items():
        varianten[v] = _variante(v, vinfo, prog, horizonte, ctx, einstellungen, ocfg, kosten_pct, umsatz, stamm, kurse, rang_matrix, keys, namen,
                                 (alt or {}).get(v) or {})
    for h in horizonte.values():
        h.pop("_order", None)
    return {"datentag": day_to_date(D).isoformat(), "einstellungen": einstellungen.as_dict(), "horizonte": horizonte, "varianten": varianten,
            "standard": einstellungen.variante, "aktien_geprueft": int(mask.sum()), "merkmale_fehlend": fehlend, "_prognosen": prog,
            "_mask": mask, "_kurse": kurse}


def _zeile(isin: str, k: int, platz: int, p: dict, kosten_pct: np.ndarray, umsatz: np.ndarray, stamm: dict, kurse: dict, dafuer, dagegen) -> dict:
    st = stamm.get(isin) or {}
    return {"platz": platz, "isin": isin, "name": st.get("name"), "branche": st.get("branche"), "waehrung": st.get("waehrung"),
            "eignung": _r(p["eignung"][k], 1), "erwartet_pct": _r(p["erwartet"][k], 2), "kosten_pct": _r(kosten_pct[k], 2),
            "positiv_pct": _r(p["positiv"][k], 1), "q10_pct": _r(p["q10"][k], 2), "q50_pct": _r(p["q50"][k], 2), "q90_pct": _r(p["q90"][k], 2),
            "dezil": int(p["dezil"][k]) + 1, "umsatz_eur": _r(umsatz[k], 0), "kurs": kurse.get(isin), "dafuer": dafuer, "dagegen": dagegen}


def _variante(v: str, vinfo: dict, prog: dict, horizonte: dict, ctx, e: portfolio.Einstellungen, ocfg: OptimiererConfig, kosten_pct, umsatz, stamm,
              kurse, rang_matrix, keys, namen, alt: dict[str, float]) -> dict:
    h = vinfo["horizont"]
    basis = {"variante": v, "name": vinfo["name"], "erklaerung": vinfo["erklaerung"], "horizont": h, "horizont_text": fo.HORIZONT_TEXT[h]}
    if h not in prog or horizonte[h]["belastbarkeit"] == "nicht belastbar":
        return dict(basis, verfuegbar=False, grund=f"Prognose für {fo.HORIZONT_TEXT[h]} nicht belastbar – kein Depotvorschlag ohne geprüfte Grundlage",
                    positionen=[], kennzahlen=None, veraenderungen=[])
    p = prog[h]
    order = horizonte[h]["_order"]
    if vinfo.get("stabil"):
        js = [keys.index(x) for x in ("anstieg_je_schwankung", "r2") if x in keys]
        stab = np.nanmean(rang_matrix[:, js], axis=1) if js else np.full(len(ctx.isins), np.nan)
        order = sorted(order[:ocfg.kandidaten * 2], key=lambda k: -(np.nan_to_num(stab[k], nan=0.0) + np.nan_to_num(p["eignung"][k], nan=0.0) / 100.0))
    kand_idx = order[:ocfg.kandidaten]
    if len(kand_idx) < 3:
        return dict(basis, verfuegbar=False, grund="zu wenige bewertete Aktien", positionen=[], kennzahlen=None, veraenderungen=[])
    kand = [portfolio.Kandidat(ctx.isins[k], erwartet_pct=float(p["erwartet"][k]), kosten_pct=float(kosten_pct[k]), wertung_rang=float(p["rang"][k]),
                               branche=(stamm.get(ctx.isins[k]) or {}).get("branche"), waehrung=(stamm.get(ctx.isins[k]) or {}).get("waehrung"),
                               umsatz_eur=float(umsatz[k]) if np.isfinite(umsatz[k]) else None) for k in kand_idx]
    reihen = {c.isin: eur_reihe(ctx.markt, c.isin) for c in kand}
    reihen = {i: r for i, r in reihen.items() if r is not None}
    r_t = portfolio.renditen_matrix(reihen, [c.isin for c in kand], int(ctx.tag))
    Sigma = portfolio.kovarianz(r_t) * fo.HORIZONTE[h]
    korr = portfolio.korrelation(r_t)
    w = portfolio.optimieren(kand, Sigma, anzahl=e.anzahl, lam=float(vinfo["lambda"]), max_gewicht=e.max_gewicht_pct / 100.0,
                             max_branche=e.max_branche_pct / 100.0, reserve=e.reserve_pct / 100.0, korr=korr)
    kz = portfolio.depot_kennzahlen(w, kand, Sigma, r_t, fo.HORIZONTE[h])
    ziel = {c.isin: float(wi) * 100.0 for c, wi in zip(kand, w) if wi > 1e-6}
    rang = {ctx.isins[k]: platz for platz, k in enumerate(order, start=1)}
    kand_map = {c.isin: c for c in kand}
    # gehaltene Aktien außerhalb der Kandidaten: aktuelle Bewertung nachtragen (Halteband braucht sie)
    for isin in alt:
        if isin not in kand_map and isin in ctx.index:
            k = ctx.index[isin]
            if np.isfinite(p["erwartet"][k]):
                kand_map[isin] = portfolio.Kandidat(isin, erwartet_pct=float(p["erwartet"][k]), kosten_pct=float(kosten_pct[k]), wertung_rang=float(p["rang"][k]))
    umgesetzt, zeilen = portfolio.veraenderungen(alt, ziel, kand_map, rang, e) if alt else (ziel, [
        {"isin": i, "art": "kaufen", "gewicht_alt_pct": 0.0, "gewicht_neu_pct": round(wv, 1), "grund": "erste Empfehlung"} for i, wv in sorted(ziel.items(), key=lambda x: -x[1])])
    positionen = []
    for isin, gw in sorted(umgesetzt.items(), key=lambda x: -x[1]):
        k = ctx.index[isin]
        dafuer, dagegen = begruendung(k, rang_matrix, keys, namen, p["merkmale"])
        z = _zeile(isin, k, rang.get(isin, 0), p, kosten_pct, umsatz, stamm, kurse, dafuer, dagegen)
        z["gewicht_pct"] = round(gw, 1)
        z["risiko_pct"] = _r(math.sqrt(max(0.0, float(Sigma[[c.isin for c in kand].index(isin), [c.isin for c in kand].index(isin)]))) * 100.0, 1) if isin in [c.isin for c in kand] else None
        positionen.append(z)
    for z in zeilen:
        st = stamm.get(z["isin"]) or {}
        z["name"] = st.get("name")
    # Kennzahlen des umgesetzten Depots (nach Halteband) – Erwartung aus denselben Prognosen
    kand_u = [kand_map[i] for i in umgesetzt if i in kand_map]
    w_u = np.array([umgesetzt[c.isin] / 100.0 for c in kand_u])
    if kand_u:
        reihen_u = {c.isin: eur_reihe(ctx.markt, c.isin) for c in kand_u}
        reihen_u = {i: r for i, r in reihen_u.items() if r is not None}
        r_u = portfolio.renditen_matrix(reihen_u, [c.isin for c in kand_u], int(ctx.tag))
        Sigma_u = portfolio.kovarianz(r_u) * fo.HORIZONTE[h]
        kz = portfolio.depot_kennzahlen(w_u, kand_u, Sigma_u, r_u, fo.HORIZONTE[h])
    return dict(basis, verfuegbar=True, positionen=positionen, kennzahlen=kz, veraenderungen=zeilen, kandidaten=len(kand),
                ziel={i: round(x, 2) for i, x in ziel.items()})


# ------------------------------------------------------------------------------------------------------ Zustand


def json_dumps(payload: dict) -> bytes:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True, default=_json_default).encode("utf-8")


def _json_default(x):
    if isinstance(x, np.generic):
        return x.item()
    if isinstance(x, np.ndarray):
        return x.tolist()
    raise TypeError(type(x).__name__)


def speichern(conn: sqlite3.Connection, payload: dict, now: dt.datetime) -> int:
    raw = json_dumps(payload)
    blob = zlib.compress(raw, 9)
    with db.Transaction(conn):
        conn.execute("INSERT OR IGNORE INTO ap_optimierer(id, datentag, erstellt_am, version, modus, groesse, sha256, inhalt) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                     (payload["id"], payload["datentag"], now.astimezone(dt.timezone.utc).isoformat(), payload["version"], payload["modus"], len(raw),
                      hashlib.sha256(raw).hexdigest(), blob))
        keep = [r[0] for r in conn.execute("SELECT id FROM ap_optimierer WHERE modus = ? ORDER BY erstellt_am DESC, id DESC LIMIT ?",
                                           (payload["modus"], STAENDE_BEHALTEN))]
        conn.execute(f"DELETE FROM ap_optimierer WHERE modus = ? AND id NOT IN ({','.join('?' * len(keep))})", (payload["modus"], *keep))
    return len(blob)


def neuester(conn: sqlite3.Connection, modus: str) -> dict | None:
    try:
        row = conn.execute("SELECT inhalt, sha256 FROM ap_optimierer WHERE modus = ? ORDER BY erstellt_am DESC, id DESC LIMIT 1", (modus,)).fetchone()
    except sqlite3.OperationalError:
        return None
    if row is None:
        return None
    raw = zlib.decompress(row[0])
    if hashlib.sha256(raw).hexdigest() != row[1]:
        raise OptimiererFehler("Optimierer-Ergebnis im Zustand beschädigt (Prüfsumme)")
    return json.loads(raw)


def prognosen_speichern(conn: sqlite3.Connection, emp: dict, *, ctx: kat.Kontext, modell_id: str, modus: str, ocfg: OptimiererConfig, now: dt.datetime) -> int:
    """Je Horizont die ``spitze`` besten Aktien nach Eignung und eine feste Stichprobe aus allen übrigen (Kontrolle der
    Kalibrierung über alle Dezile) unveränderlich speichern. Gleicher Tag, gleiches Modell: nichts Neues (INSERT OR IGNORE)."""
    D = int(ctx.tag)
    stamp = now.astimezone(dt.timezone.utc).isoformat()
    rows = []
    for h, p in emp["_prognosen"].items():
        e = p["eignung"]
        ok = np.nonzero(np.isfinite(e))[0]
        if not len(ok):
            continue
        order = ok[np.argsort(-e[ok], kind="mergesort")]
        spitze = set(int(k) for k in order[:ocfg.spitze])
        rest = [int(k) for k in order[ocfg.spitze:]]
        rng = np.random.default_rng(D * 31 + sum(map(ord, h)))
        stich = set(int(k) for k in rng.choice(rest, size=min(len(rest), ocfg.stichprobe), replace=False)) if rest else set()
        for k in sorted(spitze | stich):
            isin = ctx.isins[k]
            kurs = (emp["_kurse"].get(isin) or {}).get("kurs_eur")
            rows.append((D, modell_id, h, isin, modus, _r(p["rang"][k], 4), _r(e[k], 1), _r(p["erwartet"][k], 3), _r(p["positiv"][k], 2), _r(p["q10"][k], 3),
                         _r(p["q50"][k], 3), _r(p["q90"][k], 3), kurs, "spitze" if k in spitze else "stichprobe", stamp))
    with db.Transaction(conn):
        before = conn.total_changes
        conn.executemany("INSERT OR IGNORE INTO ap_prognose(datentag, modell_id, horizont, isin, modus, wertung_rang, eignung, erwartet_pct, positiv_pct, "
                         "q10_pct, q50_pct, q90_pct, kurs_eur, auswahl, erstellt_am) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", rows)
        return conn.total_changes - before


def empfehlung_speichern(conn: sqlite3.Connection, emp: dict, *, D: int, modell_id: str, modus: str, now: dt.datetime) -> int:
    stamp = now.astimezone(dt.timezone.utc).isoformat()
    n = 0
    with db.Transaction(conn):
        for v, inhalt in emp["varianten"].items():
            raw = json_dumps(inhalt)
            cur = conn.execute("INSERT OR IGNORE INTO ap_empfehlung(datentag, variante, modus, modell_id, erstellt_am, sha256, inhalt) VALUES (?, ?, ?, ?, ?, ?, ?)",
                               (int(D), v, modus, modell_id, stamp, hashlib.sha256(raw).hexdigest(), raw.decode("utf-8")))
            n += cur.rowcount
    return n


def letzte_empfehlung(conn: sqlite3.Connection, modus: str, vor_tag: int) -> dict[str, dict[str, float]]:
    """Gewichte je Variante aus der letzten gespeicherten Empfehlung vor ``vor_tag`` (Ausgangspunkt für Veränderungen)."""
    out = {}
    for v in portfolio.VARIANTEN:
        row = conn.execute("SELECT inhalt FROM ap_empfehlung WHERE modus = ? AND variante = ? AND datentag < ? ORDER BY datentag DESC LIMIT 1",
                           (modus, v, int(vor_tag))).fetchone()
        if row is None:
            continue
        inhalt = json.loads(row[0])
        pos = {p["isin"]: float(p["gewicht_pct"]) for p in inhalt.get("positionen") or []}
        if pos:
            out[v] = pos
    return out


def kontrolle(conn: sqlite3.Connection, modus: str, markt, D: int) -> dict:
    """Prognosekontrolle (Auftrag 18, Abschnitt 15): gespeicherte Prognosen, deren Horizont bis ``D`` vergangen ist, gegen die
    tatsächliche Rendite in Euro – Trefferquote der Richtung, mittlerer Fehler, Kalibrierung je Dezil, Rang-IC je Tag und
    Modell. Die Prognosen selbst bleiben unverändert."""
    rows = conn.execute("SELECT datentag, modell_id, horizont, isin, wertung_rang, erwartet_pct, positiv_pct, q10_pct, q90_pct, kurs_eur, auswahl "
                        "FROM ap_prognose WHERE modus = ? ORDER BY datentag", (modus,)).fetchall()
    gruppen: dict[tuple[str, str], list] = {}
    cache: dict[str, tuple | None] = {}
    offen = 0
    for d, mid, h, isin, rang, erw, pos, q10, q90, kurs, auswahl in rows:
        n = fo.HORIZONTE.get(h)
        if n is None or kurs is None:
            continue
        if isin not in cache:
            cache[isin] = eur_reihe(markt, isin) if markt is not None else None
        r = cache[isin]
        if r is None:
            offen += 1
            continue
        days, p = r
        k = int(np.searchsorted(days, int(d), side="right")) - 1
        if k < 0 or k + n >= len(days) or int(days[k + n]) > D:
            offen += 1
            continue
        ist = (float(p[k + n]) / float(p[k]) - 1.0) * 100.0 if p[k] > 0 else float("nan")
        if not math.isfinite(ist):
            continue
        gruppen.setdefault((mid, h), []).append((int(d), rang, erw, pos, q10, q90, ist, auswahl))
    out = []
    for (mid, h), werte in sorted(gruppen.items(), key=lambda x: (x[0][1], x[0][0])):
        ist = np.array([w[6] for w in werte])
        erw = np.array([np.nan if w[2] is None else w[2] for w in werte])
        pos = np.array([np.nan if w[3] is None else w[3] for w in werte])
        q10 = np.array([np.nan if w[4] is None else w[4] for w in werte])
        q90 = np.array([np.nan if w[5] is None else w[5] for w in werte])
        richtung = np.isfinite(erw) & (np.sign(erw) == np.sign(ist))
        tage = sorted({w[0] for w in werte})
        ics = []
        for d in tage:
            sel = [w for w in werte if w[0] == d and w[1] is not None]
            if len(sel) >= fo.MIN_AKTIEN_TAG:
                ics.append(fo.rang_ic(np.array([w[1] for w in sel]), np.array([w[6] for w in sel])))
        spanne = np.isfinite(q10) & np.isfinite(q90)
        out.append({"modell_id": mid, "horizont": h, "text": fo.HORIZONT_TEXT[h], "prognosen": len(werte), "tage": len(tage),
                    "richtung_pct": _r(100.0 * richtung.mean(), 1), "mittel_erwartet_pct": _r(float(np.nanmean(erw)), 2),
                    "mittel_ist_pct": _r(float(ist.mean()), 2), "mittlerer_fehler_pp": _r(float(np.nanmean(np.abs(erw - ist))), 2),
                    "positiv_erwartet_pct": _r(float(np.nanmean(pos)), 1), "positiv_ist_pct": _r(100.0 * float((ist > 0).mean()), 1),
                    "in_spanne_pct": _r(100.0 * float(((ist >= q10) & (ist <= q90))[spanne].mean()), 1) if spanne.any() else None,
                    "rang_ic": _r(float(np.nanmean(ics)), 3) if ics else None,
                    "spitze_ist_pct": _r(float(np.mean([w[6] for w in werte if w[7] == "spitze"])), 2) if any(w[7] == "spitze" for w in werte) else None})
    return {"ausgewertet": out, "offen": offen, "gespeichert": len(rows),
            "hinweis": "Gezählt werden nur Prognosen, deren Horizont vergangen ist; erwartete Werte stammen aus der damaligen Speicherung und werden nie geändert."}


# ------------------------------------------------------------------------------------------------------ Ergebnis für App und Ablage


def fuer_app(payload: dict | None) -> dict | None:
    """Ergebnis ohne Trainingsdaten der Modelle (die App braucht sie nicht)."""
    if payload is None:
        return None
    out = dict(payload)
    out.pop("ergebnis_modelle", None)
    forsch = dict(out.get("forschung") or {})
    hz = {}
    for h, info in (forsch.get("horizonte") or {}).items():
        x = dict(info)
        if x.get("endmodell"):
            md = dict(x["endmodell"])
            md.pop("knn", None)
            if md.get("teile"):
                md["teile"] = [{k: v for k, v in t.items() if k != "knn"} for t in md["teile"]]
            x["endmodell"] = md
        hz[h] = x
    forsch["horizonte"] = hz
    out["forschung"] = forsch
    return out


def dateiname(payload: dict) -> str:
    stamp = dt.datetime.fromisoformat(payload["erstellt_utc"].replace("Z", "+00:00")).astimezone(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{stamp}-{payload['id']}"


def exportieren(payload: dict, key) -> bytes:
    if key is None and not payload.get("synthetisch"):
        raise OptimiererFehler("ohne Datenschlüssel wird kein Ergebnis mit echten Kursen abgelegt")
    return crypto.pack(json_dumps(payload), key, f"{ORDNER}/{payload['id']}")


def uebernehmen(conn: sqlite3.Connection, items: list[tuple[str, bytes]], *, key, synthetisch: bool, D: int, now: dt.datetime) -> dict:
    """Abgelegte Forschungsergebnisse übernehmen (täglicher Lauf): nur verschlüsselt mit dem Datenschlüssel, Kennung im Namen
    gleich der im Inhalt, passender Modus, Stichtag nicht nach ``D``; je Ergebnis einmal."""
    from .labor import _verschluesselt

    counts = {"neu": 0, "bekannt": 0, "abgelehnt": 0}
    modus = "DEMO" if synthetisch else "PAPER"
    for stem, blob in sorted(items):
        m = DATEI_RE.match(stem)
        if m is None:
            counts["abgelehnt"] += 1
            continue
        oid = m.group(2)
        if conn.execute("SELECT 1 FROM ap_optimierer WHERE id = ?", (oid,)).fetchone() is not None:
            counts["bekannt"] += 1
            continue
        if key is not None and not _verschluesselt(blob):
            counts["abgelehnt"] += 1
            continue
        try:
            payload = json.loads(crypto.unpack(blob, key, f"{ORDNER}/{oid}"))
            ok = (payload.get("schema") == SCHEMA and payload.get("id") == oid and payload.get("modus") == modus
                  and date_to_day(dt.date.fromisoformat(payload["datentag"])) <= int(D) and isinstance(payload.get("forschung"), dict))
        except (crypto.ContainerError, ValueError, KeyError, TypeError):
            ok = False
        if not ok:
            counts["abgelehnt"] += 1
            continue
        speichern(conn, payload, now)
        counts["neu"] += 1
    return counts




def prune_names(names: list[str], now: dt.datetime) -> list[str]:
    from .labor import prune_names as _prune

    return _prune(names, now, ordner=ORDNER, datei_re=DATEI_RE, behalten=STAENDE_BEHALTEN)


def aus_ordner(root: Path) -> list[tuple[str, bytes]]:
    from .labor import aus_ordner as _aus

    return _aus(root, ordner=ORDNER, datei_re=DATEI_RE)


def aus_git(repository: str, token: str, *, server: str = "https://github.com") -> list[tuple[str, bytes]]:
    from .labor import aus_git as _aus

    return _aus(repository, token, server=server, ordner=ORDNER, datei_re=DATEI_RE)


# ------------------------------------------------------------------------------------------------------ Einstellungen


EINSTELLUNGEN = "optimierer:einstellungen"  # Schlüssel in ap_zustand (Eingang aus der App)


def einstellungen(conn: sqlite3.Connection, ocfg: OptimiererConfig) -> tuple[portfolio.Einstellungen, str]:
    """Depotparameter: zuletzt aus der App übernommen, sonst die Vorgabe der Konfiguration mit der Variante aus dem
    Risikoprofil der Pilot-Einrichtung (ein Profil für Pilot und Optimierer). Rückgabe auch die Herkunft."""
    from . import eingang

    try:
        row = conn.execute("SELECT wert_json FROM ap_zustand WHERE schluessel = ?", (EINSTELLUNGEN,)).fetchone()
    except sqlite3.OperationalError:
        row = None
    if row is not None:
        try:
            d = json.loads(row[0])
            e = pruefen_einstellungen(portfolio.Einstellungen(**{k: v for k, v in d.items() if k in ocfg.einstellungen.as_dict()}))
            return e, "app"
        except (OptimiererFehler, TypeError, ValueError):
            pass
    e = ocfg.einstellungen
    setup = None
    try:
        setup = eingang.einrichtung(conn)
    except sqlite3.OperationalError:
        setup = None
    if setup and setup.get("profil"):
        name = str(setup["profil"].get("name", "")).lower().replace("testprofil ", "").strip()
        v = portfolio.PROFIL_VARIANTE.get(name)
        if v:
            return portfolio.Einstellungen(**dict(e.as_dict(), variante=v)), "risikoprofil"
    return e, "konfiguration"


# ------------------------------------------------------------------------------------------------------ Forschungslauf


def lauf(conn: sqlite3.Connection, *, ap_cfg, method: MethodConfig, mode: str, now: dt.datetime, calendars, provider=None, fx_provider=None,
         key=None, ocfg: OptimiererConfig | None = None, jahre: float | None = None, schritt: int | None = None, max_tage: int | None = None,
         langhistorie_laden: bool = True, workers: int = 1, heute_speichern: bool = False, stand_bauen: bool = False, log=print) -> tuple[dict, dict]:
    """Forschungslauf auf dem gespeicherten Zustand (Arbeitskopie): Langhistorie ergänzen, Merkmalspanel an Entscheidungstagen,
    Forschung (Faktoren, Modelle, Kalibrierung, Rückblick), Empfehlung zum neuesten Stand. Ergebnis in ``ap_optimierer``.
    Rückgabe: (Zusammenfassung nur mit Zahlen, vollständiges Ergebnis)."""
    import time

    from . import backtest, langhistorie, simulation, tageslauf
    from ..store import repo
    from .markt import Market

    t0 = time.monotonic()
    ocfg = ocfg or load_config()
    jahre = float(jahre or ocfg.jahre)
    schritt = int(schritt or ocfg.schritt)
    max_tage = int(max_tage or ocfg.max_tage)
    published = repo.published_snapshots(conn, mode)
    if not published:
        raise OptimiererFehler("kein veröffentlichter Stand im Zustand")
    latest = published[0]
    D = int(latest["cutoff_day"])
    members = repo.universe_members(conn, latest["universe_id"])
    synthetisch = mode == "demo"
    modus = "DEMO" if synthetisch else "PAPER"
    lang = {"geladen": False}
    if langhistorie_laden and not synthetisch and provider is not None:
        lang = langhistorie.ergaenzen(conn, provider, calendars, members=members, bis=D, jahre=jahre, workers=workers, log=log)
        lang["marktreihen"] = langhistorie.marktreihen_ergaenzen(conn, provider, ap_cfg, bis=D, jahre=jahre)
        if fx_provider is not None:
            try:
                lang["wechselkurse"] = langhistorie.wechselkurse_ergaenzen(conn, fx_provider, von=D - int(jahre * 365.25) - 30)
            except Exception as exc:  # noqa: BLE001 – ohne ältere Wechselkurse bleiben Renditen in Handelswährung (sichtbar)
                lang["wechselkurse"] = f"fehler:{type(exc).__name__}"
        lang["geladen"] = True
    t_lang = time.monotonic() - t0
    von = D - int(round(jahre * 365.25))
    series, inputs, metas, skipped = simulation._laden(conn, members, von, D, calendars, synthetisch)
    etfs, indices = tageslauf.marktreihen_laden(conn, ap_cfg, von, D, synthetisch)
    series.update(etfs)
    fx = simulation._fx(conn, von, method)
    market = Market(series=series, fx=fx, indices=indices, synthetic=synthetisch, data_stand=latest["id"], source="Zustand (Depot-Optimierer)")
    stamm = tageslauf.stammdaten(conn, metas, ap_cfg)
    eintraege = kat.katalog(method, ap_cfg)
    liste, inventar = merkmale.merkmale(eintraege)
    if not metas:
        raise OptimiererFehler("keine Aktien mit Kursen im Zustand")
    stock_days = np.unique(np.concatenate([s.days for i, s in series.items() if i in members]))
    stock_days = stock_days[stock_days <= D]
    erste = int(stock_days[0]) + backtest.VORLAUF_TAGE + 10
    moeglich = stock_days[stock_days >= erste]
    if len(moeglich) < 10:
        raise OptimiererFehler(f"zu kurze Historie: {len(moeglich)} mögliche Entscheidungstage")
    tage = moeglich[::-1][::schritt][::-1][-max_tage:]
    quelle = backtest.Kontextquelle(method, ap_cfg, market, inputs, stamm, int(method.max_window), fx,
                                    fakten_fn=lambda day: tageslauf.fakten_zum_tag(conn, day, series))
    # Rangverlauf braucht die Ranglisten jedes Handelstags: nur bei täglichen Entscheidungstagen nachrechenbar
    archiv = backtest.NachgerechnetesArchiv(quelle, [int(d) for d in stock_days]) if schritt == 1 else None
    bau = Panelbau(quelle, archiv, eintraege, liste, min_umsatz_eur=ocfg.min_umsatz_forschung_eur)
    t1 = time.monotonic()
    for i, d in enumerate(tage, start=1):
        bau(int(d))
        if log is not None and (i % 10 == 0 or i == len(tage)):
            log(f"Depot-Optimierer: Merkmale an {i} von {len(tage)} Entscheidungstagen ({quelle.rechnungen} Rechenkern-Läufe, {time.monotonic() - t1:.0f} s)")
    panel = bau.panel(market, namen={m.schluessel: m.name for m in liste}, schritt=schritt)
    t_panel = time.monotonic() - t1
    bm = benchmarks(market, ap_cfg, panel.tage)
    t2 = time.monotonic()
    ergebnis = fo.forschen(panel, log=log, benchmarks=bm)
    t_forschung = time.monotonic() - t2
    ctx = bau.kontext(int(tage[-1]))
    einst, herkunft = einstellungen(conn, ocfg)
    alt = letzte_empfehlung(conn, modus, int(tage[-1]))
    emp = empfehlen(ctx=ctx, eintraege=eintraege, liste=liste, ergebnis=ergebnis, einstellungen=einst, ap_cfg=ap_cfg, ocfg=ocfg, alt=alt)
    kern = {"version": ocfg.version, "forschung": fo.VERSION, "merkmale": merkmale.VERSION, "datenstand": latest["id"],
            "tage": [int(tage[0]), int(tage[-1]), int(len(tage))], "schritt": schritt, "liste": [m.schluessel for m in liste],
            "aktien": len(panel.isins)}
    oid = "opt-" + hashlib.sha256(json.dumps(kern, sort_keys=True).encode("utf-8")).hexdigest()[:12]
    zaehlung = dict(ergebnis["zaehlung"])
    zaehlung.update({"universum": len(members), "aktien_gerechnet": len(inputs), "aktien_panel": len(panel.isins), "kennzahlen_katalog": len(inventar),
                     "kennzahlen_verwendet": sum(1 for x in inventar if x["verwendet"]), "entscheidungstage": int(len(tage)),
                     "rechenkern": quelle.rechnungen, "aktien_heute": emp["aktien_geprueft"]})
    hinweise = [
        "Nachgerechnet mit der heutigen Datenrevision und dem heutigen Universum: später verschwundene Aktien fehlen (Überlebensverzerrung).",
        f"Entscheidungstage alle {schritt} Handelstage; Folgerenditen überlappen, die Prüfung zählt deshalb nur unabhängige Zeiträume.",
        "Prognosen sind Häufigkeiten aus der Vergangenheit für Aktien mit ähnlicher Wertung – keine Zusage künftiger Renditen.",
    ]
    if archiv is None:
        hinweise.append("Rangverlauf-Kennzahlen (Stichtage in den Top K, Serie, Ø Platz, Platzgewinn) brauchen die Ranglisten jedes Handelstags "
                        "und sind im wöchentlichen Forschungslauf nicht berechenbar; ihr Nutzen wird mit dem Archiv des Vorwärtsbetriebs geprüft.")
    if synthetisch:
        hinweise.insert(0, "DEMO – synthetische Kurse, keine echten Wertpapiere.")
    payload = {
        "schema": SCHEMA, "id": oid, "version": ocfg.version, "modus": modus, "synthetisch": synthetisch,
        "erstellt_utc": now.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z"), "datenstand": latest["id"],
        "datentag": day_to_date(int(tage[-1])).isoformat(),
        "zeitraum": {"von": day_to_date(int(tage[0])).isoformat(), "bis": day_to_date(int(tage[-1])).isoformat(), "entscheidungstage": int(len(tage)),
                     "schritt": schritt, "kurse_ab": day_to_date(int(stock_days[0])).isoformat()},
        "historie": lang, "merkmale": [m.as_dict() for m in liste], "inventar": inventar, "forschung": ergebnis,
        "empfehlung": entfernen_intern(emp), "einstellungen_herkunft": herkunft, "zaehlung": zaehlung, "hinweise": hinweise,
        "laufzeit_s": {"langhistorie": round(t_lang, 1), "merkmale": round(t_panel, 1), "forschung": round(t_forschung, 1),
                       "rechenkern": round(quelle.rechenzeit_s, 1), "gesamt": round(time.monotonic() - t0, 1)},
    }
    size = speichern(conn, payload, now)
    heute = None
    if heute_speichern:
        # wie der tägliche Lauf: Prognosen und Empfehlung zum neuesten Stand unveränderlich speichern
        heute = {"prognosen": prognosen_speichern(conn, emp, ctx=ctx, modell_id=oid, modus=modus, ocfg=ocfg, now=now)}
        emp["varianten"]["rangliste"] = {"horizonte": emp["horizonte"], "einstellungen": emp["einstellungen"], "herkunft": herkunft,
                                         "aktien_geprueft": emp["aktien_geprueft"]}
        heute["empfehlungen"] = empfehlung_speichern(conn, emp, D=int(tage[-1]), modell_id=oid, modus=modus, now=now)
    stand_id = None
    if stand_bauen:
        from . import stand as stand_mod

        app = stand_mod.bauen(conn, D=D, snapshot_id=latest["id"], modus=modus, now=now, eintraege=eintraege, method=method, cfg=ap_cfg, stamm=stamm,
                              market=market)
        with db.Transaction(conn):
            stand_mod.speichern(conn, app, key, now)
        stand_id = app["id"]
    summary = {"aktien_panel": zaehlung["aktien_panel"], "merkmale": zaehlung["merkmale"], "kennzahlen_verwendet": zaehlung["kennzahlen_verwendet"],
               "entscheidungstage": zaehlung["entscheidungstage"], "pruefungen": zaehlung["pruefungen"], "bestaetigt": zaehlung["bestaetigt"],
               "kombinationen": zaehlung["kombinationen"], "modelle": zaehlung["modelle"], "rechenkern": zaehlung["rechenkern"],
               "horizonte": {h: {"modell": x["modell"], "belastbarkeit": x["belastbarkeit"]} for h, x in ergebnis["horizonte"].items()},
               "langhistorie": {k: v for k, v in lang.items() if k in ("aktien", "ergaenzt", "ohne_daten", "fehler", "jahre", "geladen")},
               "sekunden": payload["laufzeit_s"], "bytes": size, "heute": heute, "stand": stand_id, "id": oid}
    return summary, payload


# ------------------------------------------------------------------------------------------------------ Täglicher Lauf


def taeglich(conn: sqlite3.Connection, *, ctx: kat.Kontext, eintraege: dict, ap_cfg, now: dt.datetime, ocfg: OptimiererConfig | None = None) -> dict:
    """Nach jedem neuen Handelstag (täglicher Lauf): mit dem neuesten geprüften Modell Prognosen, Rangliste und alle
    Depotvarianten rechnen und unveränderlich speichern. Ohne Forschungsergebnis: nichts (Status „kein Modell“)."""
    ocfg = ocfg or load_config()
    modus = "PAPER" if ctx.modus == "paper" else "DEMO"
    payload = neuester(conn, modus)
    if payload is None:
        return {"status": "kein_modell"}
    liste = [merkmale.Merkmal.from_dict(m) for m in payload["merkmale"]]
    einst, herkunft = einstellungen(conn, ocfg)
    D = int(ctx.tag)
    alt = letzte_empfehlung(conn, modus, D)
    emp = empfehlen(ctx=ctx, eintraege=eintraege, liste=liste, ergebnis=payload["forschung"], einstellungen=einst, ap_cfg=ap_cfg, ocfg=ocfg, alt=alt)
    n_prog = prognosen_speichern(conn, emp, ctx=ctx, modell_id=payload["id"], modus=modus, ocfg=ocfg, now=now)
    emp["varianten"]["rangliste"] = {"horizonte": emp["horizonte"], "einstellungen": emp["einstellungen"], "herkunft": herkunft,
                                     "aktien_geprueft": emp["aktien_geprueft"]}
    n_emp = empfehlung_speichern(conn, emp, D=D, modell_id=payload["id"], modus=modus, now=now)
    return {"status": "ok", "modell": payload["id"], "prognosen": n_prog, "empfehlungen": n_emp, "aktien": emp["aktien_geprueft"]}


def stand(conn: sqlite3.Connection, modus: str, markt, D: int) -> dict | None:
    """Teil des Spielgeld-Stands für die App: Forschungsergebnis (ohne Trainingsdaten), neueste Empfehlung je Variante bis
    ``D`` samt Rangliste und Veränderungen, Prognosekontrolle. ``None``, solange es kein Forschungsergebnis gibt."""
    try:
        payload = neuester(conn, modus)
    except OptimiererFehler:
        return None
    if payload is None:
        return None
    row = conn.execute("SELECT MAX(datentag) FROM ap_empfehlung WHERE modus = ? AND datentag <= ?", (modus, int(D))).fetchone()
    tag = int(row[0]) if row and row[0] is not None else None
    heute = None
    if tag is not None:
        heute = {"datentag": day_to_date(tag).isoformat(), "varianten": {}}
        for v, inhalt in conn.execute("SELECT variante, inhalt FROM ap_empfehlung WHERE modus = ? AND datentag = ?", (modus, tag)):
            heute["varianten"][v] = json.loads(inhalt)
        heute["tage"] = int(conn.execute("SELECT COUNT(DISTINCT datentag) FROM ap_empfehlung WHERE modus = ?", (modus,)).fetchone()[0])
    app = fuer_app(payload)
    return {"modell": app, "heute": heute, "kontrolle": kontrolle(conn, modus, markt, int(D)) if markt is not None else None}


def _r(x, nd: int):
    return fo._r(x, nd)


def entfernen_intern(emp: dict) -> dict:
    """Empfehlung ohne interne Arrays (für JSON)."""
    return {k: v for k, v in emp.items() if not k.startswith("_")}


__all__ = ["OptimiererConfig", "OptimiererFehler", "Panelbau", "SCHEMA", "benchmarks", "empfehlen", "folgerenditen", "kontrolle", "load_config",
           "neuester", "prognosen", "speichern", "uebernehmen"]
