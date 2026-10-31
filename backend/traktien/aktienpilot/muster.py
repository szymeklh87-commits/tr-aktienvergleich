"""Musterbereiche aus Abschnitt 26: Screening A „Vor-Ausbruch und beginnender Anstieg“, Screening B „positiver Volumensprung“
(Tagesansicht) und Screening C „Seitwärtsbasis und Übergang“ – auf abgeschlossenen Tageskerzen derselben Datenbasis wie
Rangliste und Spielgeld-Robo, ohne Blick in die Zukunft. Parameter stehen nur in ``config/muster.yaml`` (versioniert,
ausdrücklich zu testende Ausgangsannahmen). Ein Musterfund ist keine Gewinnwahrscheinlichkeit und keine Kursprognose.

Gemeinsamer Kern (einmal implementiert, von A und C mit eigenen Parametern genutzt; Abschnitt 32 – keine Doppelung):

* Basis am Stichtag k = die B abgeschlossenen Sitzungen **vor** k. Obere Begrenzung (Widerstand) = höchstes Hoch, untere
  Begrenzung = tiefstes Tief der Basis (ohne Hoch/Tief: Schlusskurs). Beides steht vor dem Stichtag fest – keine nachträglich
  ausgewählten Hochs/Tiefs, keine späteren Kerzen.
* Bandbreite = (oben − unten) / Ø Schlusskurs der Basis in %, und dieselbe Spanne in ATR (Wilder, letzte gültige ATR am
  Basisende): Kursniveau und Splits erzeugen so keine Scheinsignale.
* Trendneigung = Drift der log-linearen Trendgerade über die Basis: 100 × (exp(Steigung × (B − 1)) − 1).
* Basis besteht, wenn Bandbreite ≤ Grenze in % **und** in ATR und |Drift| ≤ Grenze; eine Basis mit großer Kalenderlücke
  (Spanne > Faktor × erwartete Spanne) ist nicht prüfbar.
* Abstand zum Widerstand = 100 × (Schluss / Widerstand − 1).
* Volumenfaktor (Tag) = Volumen des Stichtags / Ø Volumen der vorherigen vollständigen Sitzungen (der Tag selbst zählt nicht
  zum Nenner; fehlende Werte werden nicht als 0 aufgefüllt; ohne positiven Nenner kein Signal) – dieselbe Größe wie die
  Kennzahl ``volumenfaktor`` im Katalog, nicht der 5-/15-Minuten-Faktor und nicht die S2-Schwelle 1,5.
* Positive Kursreaktion = Schluss über dem Vortagesschluss und in der oberen Hälfte der Tagesspanne (ohne Hoch/Tief nur der
  erste Teil).

Zustände (26.1, 26.4):

* A: ``kandidat`` (Basis besteht, Schluss höchstens ``naehe_pct`` unter dem Widerstand und im oberen Teil der Basis
  (``oberer_anteil``), seit dem Eintritt in diese Zone mindestens eine positive Reaktion – „kurz vor Ausbruch“ heißt nur: die
  Bedingungen sind erfüllt; länger als die Frist ohne Übergang: ``abgelaufen``), ``vorlaeufig`` (Schluss über dem Widerstand, Bestätigung fehlt),
  ``bestaetigt`` (Schluss mindestens ``bestaetigung_pct`` über dem Widerstand und Volumenfaktor ≥ Grenze), ``ungueltig``
  (nach einem Übergang innerhalb der Frist wieder unter dem damaligen Widerstand), ``abgelaufen`` (Kandidat ohne Ausbruch
  innerhalb der Frist).
* C: ``basis`` (Basis besteht), ``naehert`` (Kurs nähert sich dem Widerstand), ``vorlaeufig`` („vorläufig darüber“ nach
  Tagesschluss), ``bestaetigt`` („Schluss bestätigt“), ``zurueck`` („zurück in der Basis“).
* Ein vorläufiger **Intraday**-Hinweis braucht Intraday-Kurse; ohne kostenlose Quelle ist er „nicht prüfbar“.

Eine Musterinstanz ist eine ununterbrochene Folge aktiver Zustände; ihre Kennung ist eindeutig aus Modul, ISIN und erstem Tag
(``m-…``). Zustandswechsel stehen im Journal (``muster_ereignis``, nur anhängen: die damalige Einordnung bleibt erhalten,
auch wenn ein Kurs später revidiert wird).

Sortierung (26.2): fester Muster-Score 0–100 = 35 × Nähe + 25 × Enge + 25 × Volumen + 15 × Flachheit (je 0–1: Nähe =
1 + Abstand / Nähegrenze bis zum Widerstand, darüber 1; Enge = 1 − Bandbreite / Grenze; Volumen = min(1, Faktor / 3);
Flachheit = 1 − |Drift| / Grenze), danach geringeres Datenalter, danach ISIN. Die Sortierung nach bisheriger Rendite ist eine
eigene Ansicht in der App. Überdehnte Anstiege und wenig Liquidität werden markiert, nicht versteckt.

Historische Prüfung (26.2, 26.10): Dieselbe Erkennung an jedem der letzten N Stichtage nur mit den Kursen bis dahin. Für
bestätigte Übergänge und Volumensprünge die tatsächliche Rendite nach h Sitzungen (nur abgelaufene Horizonte) gegen das Mittel
aller geprüften Aktien desselben Tages; Fehlausbrüche (zurück in der Basis) und die Folgequote der Kandidaten werden gezählt,
nicht versteckt. Das ist eine Nachrechnung – keine belegte Trefferquote und kein Freigabenachweis.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import yaml
from numpy.lib.stride_tricks import sliding_window_view

from ..config import CONFIG_DIR
from ..util.timeutil import day_to_date
from . import indikatoren as ind

SCHEMA = "tr-muster/1"
MODULE = ("A", "B", "C")
AKTIV_A = ("kandidat", "vorlaeufig", "bestaetigt")
AKTIV_C = ("basis", "naehert", "vorlaeufig", "bestaetigt")
NAMEN = {"A": "Vor-Ausbruch und beginnender Anstieg", "B": "Positiver Volumensprung (Tag)", "C": "Seitwärtsbasis und Übergang"}
ZUSTAND_TEXT = {
    "kandidat": "Kandidat (kurz vor Ausbruch)", "vorlaeufig": "vorläufig über dem Widerstand", "bestaetigt": "nach Regel bestätigt",
    "ungueltig": "ungültig geworden", "abgelaufen": "abgelaufen", "basis": "Basis besteht", "naehert": "nähert sich dem Widerstand",
    "zurueck": "zurück in der Basis", "sprung": "positiver Volumensprung",
}
GRUENDE = {
    "datenalter": "letzte Kerze zu alt", "zu_kurz": "zu wenige Sitzungen für Basis und ATR", "luecke": "Lücke in der Basis",
    "atr": "ohne Hoch/Tief keine ATR", "volumen": "Volumen fehlt oder Vergleichsvolumen unvollständig", "kurs": "Schlusskurs ≤ 0",
}


@dataclass(frozen=True)
class BasisRegel:
    basis_sitzungen: int
    max_bandbreite_pct: float
    max_bandbreite_atr: float
    max_drift_pct: float
    naehe_pct: float
    oberer_anteil: float
    bestaetigung_pct: float
    bestaetigung_volumen: float
    ablauf_sitzungen: int


@dataclass(frozen=True)
class MusterConfig:
    version: str
    atr_sitzungen: int
    volumen_vergleich_sitzungen: int
    volumen_min_vergleich: int
    max_datenalter_sitzungen: int
    max_luecke_faktor: float
    ueberdehnt_sitzungen: int
    ueberdehnt_pct: float
    wenig_umsatz_usd: float
    vorlauf_sitzungen: int
    vorlauf_trend_pct: float
    a: BasisRegel
    c: BasisRegel
    sprung_schwelle: float
    sprung_reaktion: bool
    auswertung_sitzungen: int
    horizonte: tuple[int, ...]
    journal_sitzungen: int

    def regel(self, modul: str) -> BasisRegel:
        return self.a if modul == "A" else self.c

    def als_dict(self) -> dict:
        def basis(r: BasisRegel) -> dict:
            return dict(r.__dict__)
        return {
            "version": self.version, "atr_sitzungen": self.atr_sitzungen, "volumen_vergleich_sitzungen": self.volumen_vergleich_sitzungen,
            "volumen_min_vergleich": self.volumen_min_vergleich, "max_datenalter_sitzungen": self.max_datenalter_sitzungen,
            "max_luecke_faktor": self.max_luecke_faktor, "ueberdehnt_sitzungen": self.ueberdehnt_sitzungen, "ueberdehnt_pct": self.ueberdehnt_pct,
            "wenig_umsatz_usd": self.wenig_umsatz_usd, "vorlauf_sitzungen": self.vorlauf_sitzungen, "vorlauf_trend_pct": self.vorlauf_trend_pct,
            "A": basis(self.a), "B": {"schwelle": self.sprung_schwelle, "positive_reaktion": self.sprung_reaktion}, "C": basis(self.c),
            "auswertung": {"sitzungen": self.auswertung_sitzungen, "horizonte": list(self.horizonte), "journal_sitzungen": self.journal_sitzungen},
        }


class MusterFehler(ValueError):
    pass


def _regel(raw: dict, name: str) -> BasisRegel:
    try:
        r = BasisRegel(int(raw["basis_sitzungen"]), float(raw["max_bandbreite_pct"]), float(raw["max_bandbreite_atr"]), float(raw["max_drift_pct"]),
                       float(raw["naehe_pct"]), float(raw["oberer_anteil"]), float(raw["bestaetigung_pct"]), float(raw["bestaetigung_volumen"]),
                       int(raw["ablauf_sitzungen"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise MusterFehler(f"muster.yaml: {name} unvollständig ({exc})") from exc
    if not (10 <= r.basis_sitzungen <= 120 and 0 < r.max_bandbreite_pct <= 50 and 0 < r.max_bandbreite_atr <= 30 and 0 <= r.max_drift_pct <= 30
            and 0 < r.naehe_pct <= 20 and 0 <= r.oberer_anteil < 1 and 0 <= r.bestaetigung_pct <= 20 and r.bestaetigung_volumen > 0 and 1 <= r.ablauf_sitzungen <= 60):
        raise MusterFehler(f"muster.yaml: {name} außerhalb der zulässigen Grenzen")
    return r


def parse_config(raw: dict) -> MusterConfig:
    try:
        aus = raw["auswertung"]
        cfg = MusterConfig(
            version=str(raw["version"]), atr_sitzungen=int(raw["atr_sitzungen"]), volumen_vergleich_sitzungen=int(raw["volumen_vergleich_sitzungen"]),
            volumen_min_vergleich=int(raw["volumen_min_vergleich"]), max_datenalter_sitzungen=int(raw["max_datenalter_sitzungen"]),
            max_luecke_faktor=float(raw["max_luecke_faktor"]), ueberdehnt_sitzungen=int(raw["ueberdehnt_sitzungen"]), ueberdehnt_pct=float(raw["ueberdehnt_pct"]),
            wenig_umsatz_usd=float(raw["wenig_umsatz_usd"]), vorlauf_sitzungen=int(raw["vorlauf_sitzungen"]), vorlauf_trend_pct=float(raw["vorlauf_trend_pct"]),
            a=_regel(raw["vor_ausbruch"], "vor_ausbruch"), c=_regel(raw["seitwaertsbasis"], "seitwaertsbasis"),
            sprung_schwelle=float(raw["volumensprung"]["schwelle"]), sprung_reaktion=bool(raw["volumensprung"]["positive_reaktion"]),
            auswertung_sitzungen=int(aus["sitzungen"]), horizonte=tuple(int(h) for h in aus["horizonte"]), journal_sitzungen=int(aus["journal_sitzungen"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise MusterFehler(f"muster.yaml unvollständig ({exc})") from exc
    if cfg.volumen_min_vergleich > cfg.volumen_vergleich_sitzungen or cfg.sprung_schwelle <= 1 or not cfg.horizonte:
        raise MusterFehler("muster.yaml: Volumenvergleich oder Horizonte ungültig")
    return cfg


def load_muster_config(path: Path | None = None) -> MusterConfig:
    path = path or CONFIG_DIR / "muster.yaml"
    return parse_config(yaml.safe_load(path.read_text(encoding="utf-8")) or {})


# ---------------------------------------------------------------------------------------------------------- Merkmale


def _werktage(a: int, b: int) -> int:
    """Werktage nach Tag ``a`` bis einschließlich ``b`` (Feiertage zählen konservativ mit)."""
    if b <= a:
        return 0
    full, rest = divmod(b - a, 7)
    count = full * 5
    wd = day_to_date(a).weekday()
    for i in range(1, rest + 1):
        if (wd + i) % 7 < 5:
            count += 1
    return count


@dataclass
class Merkmale:
    """Alle Größen je Sitzungsindex k einer Aktie (NaN, wo nicht definiert)."""

    days: np.ndarray
    close: np.ndarray
    volfaktor: np.ndarray
    vol_ok: np.ndarray  # Volumenfaktor definiert (Tag und Vergleich vollständig genug)
    reaktion: np.ndarray
    rendite_n: np.ndarray  # Rendite der letzten ``ueberdehnt_sitzungen`` in %
    atr_ok: np.ndarray
    basis: dict  # Modul → dict mit Arrays oben, unten, bandbreite_pct, bandbreite_atr, drift_pct, besteht, luecke, abstand, vorlauf


def merkmale(s, cfg: MusterConfig) -> Merkmale:
    days = np.asarray(s.days, dtype=np.int64)
    close = np.asarray(s.close, dtype=np.float64)
    high = np.asarray(s.high, dtype=np.float64)
    low = np.asarray(s.low, dtype=np.float64)
    vol = np.asarray(s.volume, dtype=np.float64)
    n = len(close)
    hi = np.where(np.isfinite(high), high, close)
    lo = np.where(np.isfinite(low), low, close)
    # Volumenfaktor: Tag k gegen Ø der V Sitzungen davor (nur gültige Werte, mindestens volumen_min_vergleich)
    V = cfg.volumen_vergleich_sitzungen
    volfaktor = np.full(n, np.nan)
    vol_ok = np.zeros(n, dtype=bool)
    if n > V:
        valid = np.isfinite(vol) & (vol >= 0)
        w = sliding_window_view(np.where(valid, vol, 0.0), V)[: n - V]  # Fenster [k−V, k−1] für k = V … n−1
        cnt = sliding_window_view(valid.astype(np.int64), V)[: n - V].sum(axis=1)
        mean = np.where(cnt > 0, w.sum(axis=1) / np.maximum(cnt, 1), np.nan)
        today = vol[V:]
        ok = (cnt >= cfg.volumen_min_vergleich) & (mean > 0) & np.isfinite(today) & (today >= 0)
        volfaktor[V:] = np.where(ok, today / np.where(mean > 0, mean, 1.0), np.nan)
        vol_ok[V:] = ok
    prev = np.concatenate([[np.nan], close[:-1]])
    span = high - low
    pos = np.where(np.isfinite(span) & (span > 0), (close - low) / np.where(span > 0, span, 1.0), np.nan)
    reaktion = (close > prev) & (~np.isfinite(pos) | (pos >= 0.5))
    U = cfg.ueberdehnt_sitzungen
    rendite_n = np.full(n, np.nan)
    if n > U:
        rendite_n[U:] = 100.0 * (close[U:] / close[:-U] - 1.0)
    atr = ind.atr(high, low, close, cfg.atr_sitzungen)
    # letzte gültige ATR bis k (höchstens 5 Sitzungen zurück): eine Kerze ohne Hoch/Tief nach dem Kursabgleich sperrt nicht alles
    atr_last = atr.copy()
    for lag in range(1, 6):
        shifted = np.concatenate([np.full(lag, np.nan), atr[:-lag]]) if n > lag else np.full(n, np.nan)
        atr_last = np.where(np.isfinite(atr_last), atr_last, shifted)
    basis = {}
    for modul in ("A", "C"):
        r = cfg.regel(modul)
        B = r.basis_sitzungen
        out = {key: np.full(n, np.nan) for key in ("oben", "unten", "bandbreite_pct", "bandbreite_atr", "drift_pct", "abstand", "vorlauf")}
        besteht = np.zeros(n, dtype=bool)
        luecke = np.zeros(n, dtype=bool)
        if n > B:
            m = n - B  # Stichtage k = B … n−1, Basis [k−B, k−1] = Fensterindex k−B
            oben = sliding_window_view(hi, B)[:m].max(axis=1)
            unten = sliding_window_view(lo, B)[:m].min(axis=1)
            cw = sliding_window_view(close, B)[:m]
            mittel = cw.mean(axis=1)
            with np.errstate(divide="ignore", invalid="ignore"):
                y = np.log(np.where(cw > 0, cw, np.nan))
                x = np.arange(B, dtype=np.float64) - (B - 1) / 2.0
                slope = (y @ x) / float((x * x).sum())
                drift = 100.0 * (np.exp(slope * (B - 1)) - 1.0)
                bb_pct = 100.0 * (oben - unten) / mittel
                atr_end = atr_last[B - 1 : B - 1 + m]
                bb_atr = (oben - unten) / np.where(atr_end > 0, atr_end, np.nan)
                abstand = 100.0 * (close[B:] / oben - 1.0)
            spanne = days[B - 1 : B - 1 + m] - days[:m]
            gap = spanne > r_lueckenspanne(B, cfg.max_luecke_faktor)
            ok = (np.isfinite(bb_pct) & np.isfinite(bb_atr) & np.isfinite(drift) & (bb_pct <= r.max_bandbreite_pct)
                  & (bb_atr <= r.max_bandbreite_atr) & (np.abs(drift) <= r.max_drift_pct) & ~gap)
            out["oben"][B:], out["unten"][B:], out["bandbreite_pct"][B:], out["bandbreite_atr"][B:] = oben, unten, bb_pct, bb_atr
            out["drift_pct"][B:], out["abstand"][B:] = drift, abstand
            besteht[B:] = ok
            luecke[B:] = gap
            P = cfg.vorlauf_sitzungen
            k = np.arange(B, n)
            start = k - B - 1  # letzte Sitzung vor der Basis
            have = start - P >= 0
            vl = np.full(m, np.nan)
            vl[have] = 100.0 * (close[start[have]] / close[start[have] - P] - 1.0)
            out["vorlauf"][B:] = vl
        out["besteht"] = besteht
        out["luecke"] = luecke
        basis[modul] = out
    atr_ok = np.isfinite(atr_last)
    return Merkmale(days, close, volfaktor, vol_ok, reaktion, rendite_n, atr_ok, basis)


def r_lueckenspanne(B: int, faktor: float) -> float:
    """Höchste Kalenderspanne einer Basis aus B Sitzungen ohne „Lücke“: Faktor × (B − 1) × 7/5."""
    return faktor * max(1.0, (B - 1) * 7.0 / 5.0)


# ---------------------------------------------------------------------------------------------------------- Zustände

CODES = ("", "kandidat", "vorlaeufig", "bestaetigt", "ungueltig", "abgelaufen", "basis", "naehert", "zurueck", "sprung")
C = {name: i for i, name in enumerate(CODES)}


def _letzte(mask: np.ndarray) -> np.ndarray:
    """Index des letzten wahren Werts **vor** k (−1, wenn keiner)."""
    n = len(mask)
    idx = np.where(mask, np.arange(n), -1)
    last = np.maximum.accumulate(idx) if n else idx
    return np.concatenate([[-1], last[:-1]]) if n else last


def _ab_erstem(lauf: np.ndarray, ereignis: np.ndarray) -> np.ndarray:
    """Innerhalb jeder ununterbrochenen Folge von ``lauf`` wahr ab dem ersten ``ereignis`` (einschließlich)."""
    n = len(lauf)
    if not n:
        return lauf.copy()
    total = np.cumsum(ereignis.astype(np.int64))
    start = lauf & ~np.concatenate([[False], lauf[:-1]])
    before = np.where(start, total - ereignis.astype(np.int64), -1)
    pos = np.maximum.accumulate(np.where(start, np.arange(n), -1))
    base = np.where(pos >= 0, before[np.maximum(pos, 0)], 0)
    return lauf & (total - base > 0)


def _laufzeit(mask: np.ndarray) -> np.ndarray:
    """Zahl der aufeinanderfolgenden wahren Werte bis einschließlich k (0, wo falsch)."""
    n = len(mask)
    if not n:
        return np.zeros(0, dtype=np.int64)
    k = np.arange(n)
    last_false = np.maximum.accumulate(np.where(~mask, k, -1))
    return np.where(mask, k - last_false, 0)


def zustaende(mm: Merkmale, cfg: MusterConfig, modul: str) -> np.ndarray:
    """Zustandscode je Sitzungsindex (0 = kein Zustand, sonst Index in ``CODES``). Nur Daten bis k – die Rückschau über die
    Frist nutzt frühere Zustände und die damaligen Widerstände."""
    n = len(mm.close)
    out = np.zeros(n, dtype=np.int8)
    if modul == "B":
        hit = mm.vol_ok & (mm.volfaktor >= cfg.sprung_schwelle)
        if cfg.sprung_reaktion:
            hit &= mm.reaktion
        out[hit] = C["sprung"]
        return out
    r = cfg.regel(modul)
    b = mm.basis[modul]
    besteht, ab, oben, unten = b["besteht"], b["abstand"], b["oben"], b["unten"]
    with np.errstate(invalid="ignore", divide="ignore"):
        lage = (mm.close - unten) / (oben - unten)
        near = besteht & (ab >= -r.naehe_pct) & (ab <= 0) & (lage >= r.oberer_anteil)
        above = besteht & (ab > 0)
        confirmed = above & (ab >= r.bestaetigung_pct) & mm.vol_ok & (mm.volfaktor >= r.bestaetigung_volumen)
    provisional = above & ~confirmed
    E = r.ablauf_sitzungen
    k = np.arange(n)
    if modul == "A":
        # Kandidat ab der ersten positiven Reaktion in einer ununterbrochenen Annäherung; länger als die Frist ohne Übergang:
        # abgelaufen (die Lage ist alt). Ein einzelner schwächerer Tag beendet den Kandidaten nicht.
        cand = _ab_erstem(near, near & mm.reaktion)
        dauer = _laufzeit(cand)
        stale = cand & (dauer > E)
        out[cand & ~stale] = C["kandidat"]
        out[stale] = C["abgelaufen"]
    else:
        with np.errstate(invalid="ignore"):
            out[besteht & (ab < -r.naehe_pct)] = C["basis"]
        out[near] = C["naehert"]
        cand = near
    out[provisional] = C["vorlaeufig"]
    out[confirmed] = C["bestaetigt"]
    # Rückfall: nach einem Übergang innerhalb der Frist wieder unter dem damaligen Widerstand
    j = _letzte(above)
    ok = (j >= 0) & (k - j <= E)
    lvl = np.where(ok, oben[np.maximum(j, 0)], np.nan)
    with np.errstate(invalid="ignore"):
        back = ok & (mm.close < lvl) & ~(provisional | confirmed)
    out[back] = C["ungueltig"] if modul == "A" else C["zurueck"]
    if modul == "A":
        # Kandidat innerhalb der Frist, danach kein Übergang, heute nichts Aktives: abgelaufen
        j2 = _letzte(above | cand)
        exp = (out == 0) & (j2 >= 0) & (k - j2 <= E) & cand[np.maximum(j2, 0)] & ~above[np.maximum(j2, 0)]
        out[exp] = C["abgelaufen"]
    return out


def _aktiv(modul: str) -> tuple[str, ...]:
    return AKTIV_A if modul == "A" else AKTIV_C if modul == "C" else ("sprung",)


def kennung(modul: str, isin: str, tag: int | None) -> str:
    """Musterkennung aus Modul, ISIN und erstem Tag; ``tag=None`` für eine Instanz, die schon vor dem geladenen Zeitraum bestand."""
    return "m-" + hashlib.sha256(f"{modul}|{isin}|{'alt' if tag is None else tag}".encode()).hexdigest()[:12]


def ereignisse(isin: str, days: np.ndarray, z: np.ndarray, modul: str, erster: int = 0) -> list[dict]:
    """Zustandswechsel mit Musterkennung: eine Instanz = ununterbrochene Folge aktiver Zustände; ein Abschlusszustand
    (ungültig, abgelaufen, zurück) gehört zur letzten Instanz. ``erster`` = erster Index, an dem das Modul rechnen kann."""
    aktiv = {C[x] for x in _aktiv(modul)}
    out: list[dict] = []
    change = np.nonzero(z != np.concatenate([[0], z[:-1]]))[0] if len(z) else []
    current = None
    for k in change:
        s = int(z[k])
        prev = int(z[k - 1]) if k > 0 else 0
        if modul == "B":
            if s:
                out.append({"id": kennung(modul, isin, int(days[k])), "modul": modul, "isin": isin, "zustand": CODES[s], "tag": int(days[k])})
            continue
        if s in aktiv and prev not in aktiv:
            current = kennung(modul, isin, None if k <= erster else int(days[k]))
        if s and current is not None:
            out.append({"id": current, "modul": modul, "isin": isin, "zustand": CODES[s], "tag": int(days[k])})
    if modul == "B" and len(z) > 1:
        # aufeinanderfolgende Sprungtage sind je ein eigenes Ereignis
        rep = np.nonzero((z[1:] == C["sprung"]) & (z[:-1] == C["sprung"]))[0] + 1
        for k in rep:
            out.append({"id": kennung(modul, isin, int(days[k])), "modul": modul, "isin": isin, "zustand": "sprung", "tag": int(days[k])})
        out.sort(key=lambda e: e["tag"])
    return out


def score(mm: Merkmale, cfg: MusterConfig, modul: str, k: int) -> float | None:
    if modul == "B":
        v = mm.volfaktor[k]
        return None if not math.isfinite(v) else round(float(v), 2)
    r = cfg.regel(modul)
    b = mm.basis[modul]
    ab, bb, dr = b["abstand"][k], b["bandbreite_pct"][k], b["drift_pct"][k]
    if not (math.isfinite(ab) and math.isfinite(bb) and math.isfinite(dr)):
        return None
    naehe = 1.0 if ab >= 0 else max(0.0, 1.0 + ab / r.naehe_pct)
    enge = max(0.0, 1.0 - bb / r.max_bandbreite_pct)
    volumen = min(1.0, float(mm.volfaktor[k]) / 3.0) if mm.vol_ok[k] else 0.0
    flach = max(0.0, 1.0 - abs(dr) / r.max_drift_pct) if r.max_drift_pct > 0 else 0.0
    return round(100.0 * (0.35 * naehe + 0.25 * enge + 0.25 * volumen + 0.15 * flach), 1)


# ---------------------------------------------------------------------------------------------------------- Lauf


def _r(x: Any, nd: int = 4) -> float | None:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return round(v, nd) if math.isfinite(v) else None


def _datum(day: int | None) -> str | None:
    return None if day is None else day_to_date(int(day)).isoformat()


def _pruefbar(mm: Merkmale, cfg: MusterConfig, modul: str, D: int) -> str | None:
    """Grund, warum die Aktie für das Modul am Stichtag nicht prüfbar ist (``None`` = prüfbar)."""
    n = len(mm.close)
    if n == 0 or _werktage(int(mm.days[-1]), D) > cfg.max_datenalter_sitzungen:
        return "datenalter"
    k = n - 1
    if not mm.close[k] > 0:
        return "kurs"
    if modul == "B":
        return None if mm.vol_ok[k] else ("zu_kurz" if n <= cfg.volumen_vergleich_sitzungen else "volumen")
    r = cfg.regel(modul)
    if n <= r.basis_sitzungen + cfg.atr_sitzungen:
        return "zu_kurz"
    b = mm.basis[modul]
    if b["luecke"][k]:
        return "luecke"
    if not mm.atr_ok[max(0, k - 1)]:
        return "atr"
    return None


def _treffer(isin: str, mm: Merkmale, z: np.ndarray, cfg: MusterConfig, modul: str, umsatz_usd: float | None, journal_ids: dict) -> dict:
    k = len(mm.close) - 1
    row: dict[str, Any] = {"isin": isin, "zustand": CODES[int(z[k])], "tag": _datum(mm.days[k]), "schluss": _r(mm.close[k], 6), "score": score(mm, cfg, modul, k),
                           "volumenfaktor": _r(mm.volfaktor[k], 2), "reaktion": bool(mm.reaktion[k]), "rendite_n_pct": _r(mm.rendite_n[k], 2),
                           "ueberdehnt": bool(math.isfinite(mm.rendite_n[k]) and mm.rendite_n[k] > cfg.ueberdehnt_pct),
                           "wenig_umsatz": bool(umsatz_usd is not None and umsatz_usd < cfg.wenig_umsatz_usd), "umsatz_usd": _r(umsatz_usd, 0),
                           "id": journal_ids.get((modul, isin))}
    if modul != "B":
        r = cfg.regel(modul)
        b = mm.basis[modul]
        vl = b["vorlauf"][k]
        row.update({
            "widerstand": _r(b["oben"][k], 6), "unten": _r(b["unten"][k], 6), "abstand_pct": _r(b["abstand"][k], 2),
            "bandbreite_pct": _r(b["bandbreite_pct"][k], 2), "bandbreite_atr": _r(b["bandbreite_atr"][k], 2), "drift_pct": _r(b["drift_pct"][k], 2),
            "basis_von": _datum(mm.days[k - r.basis_sitzungen]), "basis_bis": _datum(mm.days[k - 1]),
            "vorlauf": None if not math.isfinite(vl) else ("aufwaertstrend" if vl >= cfg.vorlauf_trend_pct else "bodenbildung" if vl <= -cfg.vorlauf_trend_pct else "neutral"),
            "vorlauf_pct": _r(vl, 2), "volumen_fehlt": not bool(mm.vol_ok[k]),
        })
    return row


_RANG = {"bestaetigt": 0, "vorlaeufig": 1, "kandidat": 2, "naehert": 2, "basis": 3, "ungueltig": 4, "zurueck": 4, "abgelaufen": 5, "sprung": 0}


def _sortiert(rows: list[dict]) -> list[dict]:
    return sorted(rows, key=lambda r: (_RANG.get(r["zustand"], 9), -(r["score"] if r["score"] is not None else -1.0), r["isin"]))


def _auswertung(alle: list[tuple[str, Merkmale, dict[str, np.ndarray]]], cfg: MusterConfig, D: int) -> dict:
    """Nachrechnung der letzten N Stichtage: Signale, Folgequote, Fehlausbrüche, Rendite nach h Sitzungen gegen das Mittel aller
    geprüften Aktien desselben Tages (gleich gewichtet). Nur abgelaufene Horizonte und abgeschlossene Fristen."""
    N = cfg.auswertung_sitzungen
    H = cfg.horizonte
    day_lo = D - int(N * 7 / 5) - 14
    size = D - day_lo + 1
    base_sum = {h: np.zeros(size) for h in H}
    base_cnt = {h: np.zeros(size, dtype=np.int64) for h in H}
    for _isin, mm, _z in alle:
        sel = np.nonzero((mm.days >= day_lo) & (mm.days <= D))[0]
        for h in H:
            ks = sel[sel + h < len(mm.close)]
            if not len(ks):
                continue
            with np.errstate(divide="ignore", invalid="ignore"):
                fr = mm.close[ks + h] / mm.close[ks] - 1.0
            ok = np.isfinite(fr)
            off = mm.days[ks][ok] - day_lo
            np.add.at(base_sum[h], off, fr[ok])
            np.add.at(base_cnt[h], off, 1)
    out: dict[str, Any] = {}
    for modul in MODULE:
        signale: dict[str, int] = {}
        folge = [0, 0]
        fehl = [0, 0]
        rend = {h: [] for h in H}
        basis = {h: [] for h in H}
        stichtage: set[int] = set()
        E = cfg.regel(modul).ablauf_sitzungen if modul != "B" else 0
        back = C["ungueltig"] if modul == "A" else C["zurueck"]
        for _isin, mm, zs in alle:
            z = zs[modul]
            n = len(z)
            if n < 2:
                continue
            win = (mm.days >= day_lo) & (mm.days <= D)
            stichtage.update(mm.days[win].tolist())
            prev = np.concatenate([[0], z[:-1]])
            changed = win & (z != 0) & (z != prev)
            for code, cnt in zip(*np.unique(z[changed], return_counts=True)):
                signale[CODES[int(code)]] = signale.get(CODES[int(code)], 0) + int(cnt)
            if modul == "A":
                aktiv = np.isin(prev, [C[x] for x in AKTIV_A])
                starts = np.nonzero(changed & (z == C["kandidat"]) & ~aktiv)[0]
                starts = starts[starts + E < n]
                if len(starts):
                    tr = np.concatenate([[0], np.cumsum(np.isin(z, [C["vorlaeufig"], C["bestaetigt"]]))])
                    folge[0] += len(starts)
                    folge[1] += int(np.count_nonzero(tr[starts + E + 1] - tr[starts + 1] > 0))
            if modul == "B":
                ev = np.nonzero(win & (z == C["sprung"]))[0]
            else:
                ev = np.nonzero(changed & (z == C["bestaetigt"]))[0]
                done = ev[ev + E < n]
                if len(done):
                    bk = np.concatenate([[0], np.cumsum(z == back)])
                    fehl[0] += len(done)
                    fehl[1] += int(np.count_nonzero(bk[done + E + 1] - bk[done + 1] > 0))
            for h in H:
                ks = ev[ev + h < n]
                if not len(ks):
                    continue
                with np.errstate(divide="ignore", invalid="ignore"):
                    fr = mm.close[ks + h] / mm.close[ks] - 1.0
                off = mm.days[ks] - day_lo
                cnt = base_cnt[h][off]
                ok = np.isfinite(fr) & (cnt > 0)
                rend[h].extend(fr[ok].tolist())
                basis[h].extend((base_sum[h][off][ok] / cnt[ok]).tolist())
        horiz = {}
        for h in H:
            a = np.asarray(rend[h])
            bse = np.asarray(basis[h])
            horiz[str(h)] = {"n": int(len(a)), "mittel_pct": _r(100 * a.mean(), 2) if len(a) else None, "median_pct": _r(100 * np.median(a), 2) if len(a) else None,
                             "anteil_positiv_pct": _r(100 * (a > 0).mean(), 1) if len(a) else None,
                             "vergleich_mittel_pct": _r(100 * bse.mean(), 2) if len(bse) else None}
        entry: dict[str, Any] = {"signale": signale, "horizonte": horiz, "stichtage": len(stichtage)}
        if modul == "A":
            entry["kandidaten_abgeschlossen"] = folge[0]
            entry["folgequote_pct"] = _r(100 * folge[1] / folge[0], 1) if folge[0] else None
        if modul != "B":
            entry["uebergaenge_abgeschlossen"] = fehl[0]
            entry["fehlausbrueche_pct"] = _r(100 * fehl[1] / fehl[0], 1) if fehl[0] else None
        out[modul] = entry
    out["hinweis"] = (f"Nachgerechnet über die letzten {N} Stichtage mit den Kursen bis zum jeweiligen Tag (heutige Datenrevision); Rendite nach "
                      f"{', '.join(map(str, H))} Sitzungen nur für abgelaufene Horizonte, verglichen mit dem Mittel aller geprüften Aktien desselben Tages. "
                      "Keine Gewinnwahrscheinlichkeit, keine Prognose, kein Freigabenachweis.")
    return out


def bauen(reihen: dict, *, cfg: MusterConfig, D: int, snapshot_id: str, modus: str, erstellt_utc: str, umsatz_usd: dict[str, float | None] | None = None,
          universum: Iterable[str] | None = None, journal_vorher: Iterable[dict] = ()) -> tuple[dict, list[dict]]:
    """Musterstand für die App und neue Journal-Ereignisse. ``reihen``: ISIN → Tageskerzen (Attribute days/high/low/close/volume).
    ``universum``: alle ISINs des Stands (auch ohne Kerzen – diese zählen als nicht prüfbar)."""
    umsatz_usd = umsatz_usd or {}
    isins = sorted(set(universum or reihen) | set(reihen))
    nicht = {m: {} for m in MODULE}
    alle: list[tuple[str, Merkmale, dict[str, np.ndarray]]] = []
    for isin in isins:
        s = reihen.get(isin)
        if s is None or len(s.days) == 0:
            for m in MODULE:
                nicht[m].setdefault("datenalter", []).append(isin)
            continue
        mm = merkmale(s, cfg)
        zs = {m: zustaende(mm, cfg, m) for m in MODULE}
        alle.append((isin, mm, zs))
    # Journal: Zustandswechsel der letzten Sitzungen; nur anhängen (bekannte Ereignisse bleiben unverändert)
    seen = {(e["id"], e["zustand"], int(e["tag"])) for e in journal_vorher}
    neue: list[dict] = []
    ids: dict[tuple[str, str], str] = {}
    since = D - int(cfg.journal_sitzungen * 7 / 5) - 7
    for isin, mm, zs in alle:
        for m in MODULE:
            erster = 0 if m == "B" else cfg.regel(m).basis_sitzungen
            evs = ereignisse(isin, mm.days, zs[m], m, erster)
            if evs and zs[m][-1]:
                ids[(m, isin)] = evs[-1]["id"]
            for e in evs:
                if e["tag"] >= since and (e["id"], e["zustand"], e["tag"]) not in seen:
                    neue.append(e)
    module = {}
    geprueft = {m: 0 for m in MODULE}
    for m in MODULE:
        rows = []
        for isin, mm, zs in alle:
            grund = _pruefbar(mm, cfg, m, D)
            if grund:
                nicht[m].setdefault(grund, []).append(isin)
                continue
            geprueft[m] += 1
            z = zs[m]
            if z[-1]:
                rows.append(_treffer(isin, mm, z, cfg, m, umsatz_usd.get(isin), ids))
        rows = _sortiert(rows)
        zaehl: dict[str, int] = {}
        for r in rows:
            zaehl[r["zustand"]] = zaehl.get(r["zustand"], 0) + 1
        aktiv = [r for r in rows if r["zustand"] in _aktiv(m)]
        module[m] = {"name": NAMEN[m], "geprueft": geprueft[m], "zustaende": zaehl, "top": [r["isin"] for r in aktiv[:10]], "treffer": rows,
                     "nicht_pruefbar": {g: sorted(v) for g, v in sorted(nicht[m].items())}}
    module["B"]["intraday"] = {"status": "nicht prüfbar", "grund": "Keine kostenlose Intraday-Quelle mit Volumen je 5-/15-Minuten-Intervall eingebunden; "
                                                                  "die Tagesansicht ersetzt den Intraday-Faktor nicht."}
    payload = {
        "schema": SCHEMA, "version": cfg.version, "erstellt_utc": erstellt_utc, "datentag": _datum(D), "snapshot_id": snapshot_id, "modus": modus,
        "hinweis": "Tagesdaten nach Börsenschluss (keine Intraday-Beobachtung). Ein Musterfund ist keine Gewinnwahrscheinlichkeit, keine Kursprognose "
                   "und keine Kaufempfehlung; die Parameter sind zu testende Ausgangsannahmen.",
        "universum": len(isins), "parameter": cfg.als_dict(), "gruende": GRUENDE, "zustaende": ZUSTAND_TEXT,
        "module": module, "auswertung": _auswertung(alle, cfg, D),
    }
    return payload, neue


def jetzt_utc(now: dt.datetime) -> str:
    return now.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
