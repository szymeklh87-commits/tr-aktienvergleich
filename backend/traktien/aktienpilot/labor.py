"""Strategielabor (Gesamtauftrag vom 31.10.2026, Abschnitte 12, 13 und 15): Varianten erzeugen, zeitlich getrennt prüfen,
nicht robuste verwerfen, validierte vorwärts testen – nachvollziehbar und reproduzierbar.

Ablauf eines Laufs (gleiche Daten und gleiche ``config/labor.yaml`` → gleiches Ergebnis, gleiche Kennung):

1. **Varianten:** je Familie A–H aus Abschnitt 12 das Parametergitter der Konfiguration. Jede Variante ist eine gewöhnliche
   Regel (``regeln.pruefen``, Fingerabdruck) aus dem zentralen Kennzahlenkatalog – kein zweiter Strategiecode.
2. **Zeiträume:** die letzten ``tage`` Handelstage bis zum neuesten Stand, ohne Überlappung geteilt in Entwicklung,
   Validierung und Test; dazu Walk-forward-Faltungen (Training, anschließende Prüfung).
3. **Ein Durchlauf:** je Variante und Zeitraum ein eigenes Spielgelddepot mit gleichem Startkapital, das nur in seinem
   Zeitraum handelt; je Zeitraum ein Welt-ETF-Vergleichsdepot. Derselbe Tagesschritt wie im Vorwärtsbetrieb
   (``motor.tagesschritt``: Kosten, Ausführung am Folgetag, Stops, Risikogrenzen); der Rechenkern rechnet je Tag einmal für
   alle Depots, Ranglisten früherer Stichtage kommen aus der Nachrechnung (gekennzeichnet).
4. **Bewertung je Zeitraum:** Rendite nach Kosten (offene Positionen zum Schlusskurs), Abstand zum Welt-ETF, größter
   Rückgang, Rendite je Rückgang, Gewinnquote, Käufe; Mehrkriterienwertung = gewichtete Perzentile unter allen Varianten.
5. **Auswahl nur aus der Entwicklung:** Robustheitsregeln verwerfen (zu wenige Käufe, Rückgang über der Grenze, nicht positiv,
   Einzeltreffer ohne positive Nachbarvariante); die besten robusten Varianten müssen in der Validierung bestehen. Der
   Testzeitraum wird nur für die validierten Varianten berichtet und ändert keine Auswahl.
6. **Walk-forward:** In jeder Faltung wählt dasselbe Verfahren im Training eine Variante; berichtet wird deren Ergebnis im
   anschließenden Prüfzeitraum – das misst das Auswahlverfahren statt einer im Nachhinein besten Variante.
7. **Vorschlag:** die besten validierten Varianten laufen als eigene Spielgelddepots vorwärts (``vorwaerts_depots``); die
   Übernahme richtet sich nach dem gewählten Modus (Standard: nur vorschlagen). Nichts davon berührt Echtgeld.

Öffentliche Protokolle enthalten nur Zählungen und Zeiten; das Ergebnis liegt verschlüsselt im Spielgeld-Stand.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import itertools
import json
import math
import re
import sqlite3
import subprocess
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np
import yaml

from ..config import CONFIG_DIR, MethodConfig
from ..store import db
from ..util import crypto
from ..util.timeutil import date_to_day, day_to_date
from . import backtest, motor, regeln

SCHEMA = "tr-labor/1"
PREFIX_VORWAERTS = "l-"  # Spielgelddepots der validierten Varianten im Vorwärtstest
STAENDE_BEHALTEN = 5
# Ablage für den täglichen Lauf (Workflow „Spielgeld-Labor“ → Branch, wie der Spielgeld-Eingang): verschlüsselt, AAD labor/<id>
BRANCH = "spielgeld-labor"
ORDNER = "labor"
DATEI_RE = re.compile(r"^(\d{8}T\d{6}Z)-(lab-[0-9a-f]{12})$")
ABLAGE_BEHALTEN = 3
MODI = ("nur_vorschlagen", "nach_freigabe", "automatisch_im_spielgeld")
KRITERIEN = ("rendite", "abstand_welt", "rueckgang", "rendite_je_rueckgang", "gewinnquote")
ALLE_GEWICHTE = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
MIN_ZEITRAUM = 5  # Handelstage je Zeitraum mindestens

# Familien aus Abschnitt 12 (Reihenfolge = Reihenfolge im Ergebnis): Schlüssel → (Buchstabe, Name)
FAMILIEN: dict[str, tuple[str, str]] = {
    "platz1": ("A", "Viele Platz-1-Platzierungen"),
    "top10": ("B", "Viele Top-10-Nennungen"),
    "gleichmaessig": ("C", "Gleichmäßiger Kursanstieg"),
    "platz1_volumen": ("D", "Platz-1-Häufigkeit plus Volumensprung"),
    "stabil_vorausbruch": ("E", "Top-10-Stabilität plus Vor-Ausbruch"),
    "gleichmaessig_leiter": ("F", "Gleichmäßiger Aufwärtstrend plus Gewinnleiter"),
    "kurz": ("G", "Kurzfristige Spitzenreiter, schneller Ausstieg"),
    "lang": ("H", "Längerfristige Spitzenreiter, längeres Halten"),
}

# Erlaubte Gitterparameter je Familie mit Grenzen (ganzzahlig, wenn beide Grenzen ganzzahlig sind)
GITTER: dict[str, dict[str, tuple[float, float]]] = {
    "platz1": {"fenster_bis": (2, 90), "mindestens": (1, 990)},
    "top10": {"fenster_bis": (2, 90), "mindestens": (1, 990)},
    "gleichmaessig": {"schwankung_min": (0.5, 10.0), "abschnitte_min": (50, 100)},
    "platz1_volumen": {"fenster_bis": (2, 90), "volumenfaktor": (1.0, 10.0)},
    "stabil_vorausbruch": {"stichtage": (2, 60)},
    "gleichmaessig_leiter": {"schwankung_min": (0.5, 10.0)},
    "kurz": {"fenster": (1, 30), "haltedauer": (1, 60)},
    "lang": {"fenster": (30, 90), "mindesthaltedauer": (0, 120)},
}


class LaborFehler(ValueError):
    """Ungültige Laborkonfiguration oder zu kurze Historie (Meldung auf Deutsch)."""


# ------------------------------------------------------------------------------------------------------ Konfiguration


@dataclass(frozen=True)
class LaborConfig:
    version: str
    tage: int
    entwicklung_pct: float
    validierung_pct: float
    wf_training: int
    wf_pruefung: int
    startkapital_eur: float
    gewichte: dict[str, float]
    mindest_kaeufe: int
    max_rueckgang_pct: float
    nachbarn: bool
    finalisten: int
    vorwaerts: int
    modus: str
    familien: dict[str, dict[str, tuple]]

    def as_dict(self) -> dict:
        """Rohform wie in ``labor.yaml`` (``parse_config(cfg.as_dict()) == cfg``) – auch für das Ergebnis."""
        return {
            "version": self.version, "startkapital_eur": self.startkapital_eur,
            "zeitraum": {"tage": self.tage, "entwicklung_pct": self.entwicklung_pct, "validierung_pct": self.validierung_pct,
                         "walk_forward": {"training": self.wf_training, "pruefung": self.wf_pruefung}},
            "bewertung": dict(self.gewichte), "robustheit": {"mindest_kaeufe": self.mindest_kaeufe, "max_rueckgang_pct": self.max_rueckgang_pct,
                                                            "nachbarn": self.nachbarn},
            "auswahl": {"finalisten": self.finalisten, "vorwaerts": self.vorwaerts}, "uebernahme": {"modus": self.modus},
            "familien": {f: {k: list(v) for k, v in g.items()} for f, g in self.familien.items()},
        }


def parse_config(raw: dict) -> LaborConfig:
    try:
        z = raw["zeitraum"]
        wf = z["walk_forward"]
        rb = raw["robustheit"]
        aw = raw["auswahl"]
        cfg = LaborConfig(
            version=str(raw["version"]), tage=int(z["tage"]), entwicklung_pct=float(z["entwicklung_pct"]), validierung_pct=float(z["validierung_pct"]),
            wf_training=int(wf["training"]), wf_pruefung=int(wf["pruefung"]), startkapital_eur=float(raw["startkapital_eur"]),
            gewichte={k: float(raw["bewertung"][k]) for k in KRITERIEN}, mindest_kaeufe=int(rb["mindest_kaeufe"]),
            max_rueckgang_pct=float(rb["max_rueckgang_pct"]), nachbarn=bool(rb["nachbarn"]), finalisten=int(aw["finalisten"]),
            vorwaerts=int(aw["vorwaerts"]), modus=str(raw["uebernahme"]["modus"]),
            familien={str(f): {str(k): tuple(v) for k, v in (g or {}).items()} for f, g in (raw["familien"] or {}).items()},
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise LaborFehler(f"labor.yaml unvollständig ({exc})") from exc
    if not (20 <= cfg.tage <= 250):
        raise LaborFehler("labor.yaml: zeitraum.tage muss 20 bis 250 Handelstage sein")
    if not (10 <= cfg.entwicklung_pct <= 80 and 5 <= cfg.validierung_pct <= 45 and cfg.entwicklung_pct + cfg.validierung_pct <= 90):
        raise LaborFehler("labor.yaml: Anteile für Entwicklung und Validierung lassen keinen Testzeitraum")
    if cfg.wf_training < MIN_ZEITRAUM or cfg.wf_pruefung < MIN_ZEITRAUM or cfg.wf_training + cfg.wf_pruefung > cfg.tage:
        raise LaborFehler("labor.yaml: Walk-forward-Zeiträume passen nicht in die Handelstage")
    if cfg.startkapital_eur <= 0 or any(w < 0 for w in cfg.gewichte.values()) or sum(cfg.gewichte.values()) <= 0:
        raise LaborFehler("labor.yaml: Startkapital oder Gewichte der Bewertung ungültig")
    if cfg.mindest_kaeufe < 1 or not (1 <= cfg.max_rueckgang_pct <= 100) or not (1 <= cfg.finalisten <= 50) or not (0 <= cfg.vorwaerts <= 5):
        raise LaborFehler("labor.yaml: Robustheit oder Auswahl außerhalb der Grenzen")
    if cfg.modus not in MODI:
        raise LaborFehler(f"labor.yaml: uebernahme.modus muss einer von {', '.join(MODI)} sein")
    unbekannt = set(cfg.familien) - set(FAMILIEN)
    if unbekannt:
        raise LaborFehler(f"labor.yaml: unbekannte Familien {', '.join(sorted(unbekannt))}")
    for fam, grid in cfg.familien.items():
        if set(grid) != set(GITTER[fam]):
            raise LaborFehler(f"labor.yaml: Familie {fam} braucht genau die Parameter {', '.join(GITTER[fam])}")
        for name, werte in grid.items():
            lo, hi = GITTER[fam][name]
            if not werte or len(set(werte)) != len(werte) or any(not isinstance(w, (int, float)) or isinstance(w, bool) or not (lo <= w <= hi) for w in werte):
                raise LaborFehler(f"labor.yaml: {fam}.{name} braucht verschiedene Zahlen von {lo:g} bis {hi:g}")
    if not cfg.familien:
        raise LaborFehler("labor.yaml: keine Familie")
    return cfg


def load_labor_config(path: Path | None = None) -> LaborConfig:
    path = path or CONFIG_DIR / "labor.yaml"
    return parse_config(yaml.safe_load(path.read_text(encoding="utf-8")) or {})


def mit_tagen(cfg: LaborConfig, tage: int) -> LaborConfig:
    """Andere Zahl von Handelstagen (Befehl ``--tage``): Walk-forward-Training und -Prüfung im selben Verhältnis."""
    raw = cfg.as_dict()
    faktor = tage / cfg.tage
    wf = {"training": max(MIN_ZEITRAUM, round(cfg.wf_training * faktor)), "pruefung": max(MIN_ZEITRAUM, round(cfg.wf_pruefung * faktor))}
    return parse_config(dict(raw, zeitraum=dict(raw["zeitraum"], tage=int(tage), walk_forward=wf)))


# ------------------------------------------------------------------------------------------------------ Varianten


def _ref(kid: str, **params) -> dict:
    return {"id": kid, "parameter": params} if params else {"id": kid}


def _haeufigkeit(k: int, bis: int) -> dict:
    return {"k": k, "fenster": {"von": 1, "bis": int(bis)}, "gewichte": list(ALLE_GEWICHTE), "gruppe": "A", "politik": "native"}


def _regel(profil: str, **teile) -> dict:
    regel = {
        "schema": "tr-regel/1", "version": 1, "filter": None, "auswahl": {"anzahl": 5}, "kapital": {"art": "gleich"},
        "kauf": {"ausloeser": "termin"}, "verkauf": {"herausfallen": {"aktiv": True, "puffer": 5}},
        "stop": {"initial": {"art": "atr", "faktor": 2.0, "sitzungen": 14}}, "zeitplan": {"intervall": "woechentlich", "wochentag": 4},
        "profil": profil,
    }
    regel.update(teile)
    return regel


def _signal_ausstieg() -> dict:
    """Signalregeln (Volumensprung, Vor-Ausbruch) gelten nur am Signaltag: kein Verkauf, weil das Signal am nächsten Tag
    fehlt, sondern Ausstieg über Stops und eine Höchsthaltedauer."""
    return {
        "kauf": {"ausloeser": "auffuellen"}, "zeitplan": {"intervall": "taeglich"},
        "verkauf": {"herausfallen": {"aktiv": False, "puffer": 0}, "max_haltedauer_sitzungen": 20},
        "stop": {"initial": {"art": "atr", "faktor": 2.0, "sitzungen": 14}, "trailing": {"art": "atr", "faktor": 3.0, "sitzungen": 14}},
    }


def _gleichmaessig_filter(schwankung_min: float, abschnitte_min: float) -> dict:
    return {"und": [
        {"kennzahl": _ref("anstieg_je_schwankung", sitzungen=60), "op": ">=", "wert": float(schwankung_min)},
        {"kennzahl": _ref("positive_abschnitte", abschnitte=12, laenge=5), "op": ">=", "wert": float(abschnitte_min)},
    ]}


def _bauen(fam: str, p: dict, profil: str) -> tuple[dict, str, str]:
    """Regel, Name und Beschreibung einer Variante."""
    if fam in ("platz1", "top10"):
        k = 1 if fam == "platz1" else 10
        q = dict(_haeufigkeit(k, p["fenster_bis"]), art="haeufigkeit", mindestens=int(p["mindestens"]))
        r = _regel(profil, kandidaten=[q], sortierung={"schluessel": [
            {"kennzahl": _ref("haeufigkeit", **_haeufigkeit(k, p["fenster_bis"])), "richtung": "ab"},
            {"kennzahl": _ref("rendite", fenster=30), "richtung": "ab"}]})
        was = "Platz 1" if k == 1 else "Top 10"
        return r, f"{was} häufig, 1–{p['fenster_bis']} Tage, mind. {p['mindestens']}", (
            f"Aktien, die in den Renditeranglisten 1–{p['fenster_bis']} Kalendertage (alle elf Gewichtungen, Gruppe A) mindestens "
            f"{p['mindestens']}-mal {'auf Platz 1' if k == 1 else 'unter den ersten zehn'} stehen; nach Häufigkeit sortiert, bis zu 5, wöchentlich.")
    if fam in ("gleichmaessig", "gleichmaessig_leiter"):
        ab = p.get("abschnitte_min", 66)
        r = _regel(profil, kandidaten=[{"art": "universum"}], filter=_gleichmaessig_filter(p["schwankung_min"], ab),
                   sortierung={"schluessel": [{"kennzahl": _ref("anstieg_je_schwankung", sitzungen=60), "richtung": "ab"}]})
        text = f"Anstieg je Schwankung (60 Sitzungen) mindestens {_zahl(p['schwankung_min'])}, mindestens {_zahl(ab)} % positive Wochenabschnitte (12 × 5 Sitzungen)"
        if fam == "gleichmaessig_leiter":
            r["verkauf"] = dict(r["verkauf"], gewinnmitnahme={"art": "leiter", "basis": "nach_kosten", "bezug": "urspruenglich", "stufen": [
                {"schwelle_pct": 30, "anteil_pct": 25}, {"schwelle_pct": 50, "anteil_pct": 25}, {"schwelle_pct": 100, "anteil_pct": 50}]})
            return r, f"Gleichmäßig mit Gewinnleiter, Schwankung ≥ {_zahl(p['schwankung_min'])}", text + "; Gewinnleiter +30/+50/+100 % (25/25/50 %)."
        return r, f"Gleichmäßig, Schwankung ≥ {_zahl(p['schwankung_min'])}, Abschnitte ≥ {_zahl(ab)} %", text + "; sortiert nach Anstieg je Schwankung, bis zu 5."
    if fam == "platz1_volumen":
        q = dict(_haeufigkeit(1, p["fenster_bis"]), art="haeufigkeit", mindestens=1)
        r = _regel(profil, kandidaten=[q], filter={"kennzahl": _ref("volumenfaktor", sitzungen=20), "op": ">=", "wert": float(p["volumenfaktor"])},
                   sortierung={"schluessel": [{"kennzahl": _ref("haeufigkeit", **_haeufigkeit(1, p["fenster_bis"])), "richtung": "ab"},
                                              {"kennzahl": _ref("volumenfaktor", sitzungen=20), "richtung": "ab"}]}, **_signal_ausstieg())
        return r, f"Platz 1 (1–{p['fenster_bis']} Tage) plus Volumen ≥ {_zahl(p['volumenfaktor'])}×", (
            f"Mindestens ein erster Platz in den Renditeranglisten 1–{p['fenster_bis']} Kalendertage und am Entscheidungstag Volumen "
            f"≥ {_zahl(p['volumenfaktor'])}× des Durchschnitts der 20 Sitzungen davor; täglich auffüllen, Ausstieg über Stops oder nach 20 Sitzungen.")
    if fam == "stabil_vorausbruch":
        s = int(p["stichtage"])
        mind = max(1, math.ceil(0.6 * s))
        rang = {"fenster": 30, "gewicht": 60, "gruppe": "A", "politik": "native"}
        r = _regel(profil, kandidaten=[{"art": "universum"}], filter={"und": [
            {"kennzahl": _ref("top_stichtage", k=10, stichtage=s, **rang), "op": ">=", "wert": mind},
            {"kennzahl": _ref("muster_vor_ausbruch"), "op": "in", "werte": ["kandidat", "vorlaeufig", "bestaetigt"]}]},
            sortierung={"schluessel": [{"kennzahl": _ref("rang_mittel_stichtage", stichtage=s, **rang), "richtung": "auf"},
                                       {"kennzahl": _ref("muster_vor_ausbruch_score"), "richtung": "ab"}]}, **_signal_ausstieg())
        return r, f"Top 10 an {mind} von {s} Stichtagen plus Vor-Ausbruch", (
            f"An mindestens {mind} der letzten {s} Stichtage unter den ersten zehn der Rangliste 30 Tage, 60/40 (Gruppe A) und im "
            "Vor-Ausbruch (Kandidat, vorläufig oder bestätigt); täglich auffüllen, Ausstieg über Stops oder nach 20 Sitzungen.")
    if fam == "kurz":
        h, hold = int(p["fenster"]), int(p["haltedauer"])
        r = _regel(profil, kandidaten=[{"art": "rangliste", "gruppe": "A", "politik": "native", "gewichte": [0], "fenster": {"von": h, "bis": h}, "platz_bis": 3}],
                   sortierung={"schluessel": [{"kennzahl": _ref("rang", fenster=h, gewicht=0, gruppe="A", politik="native"), "richtung": "auf"}]},
                   auswahl={"anzahl": 3}, zeitplan={"intervall": "taeglich"},
                   verkauf={"herausfallen": {"aktiv": True, "puffer": 0}, "max_haltedauer_sitzungen": hold},
                   stop={"initial": {"art": "prozent", "wert": 8}})
        return r, f"Kurz: Top 3 der {h}-Tage-Rendite, höchstens {hold} Sitzungen", (
            f"Die ersten drei der reinen Renditerangliste {h} Kalendertage (Gruppe A), täglich; Verkauf beim Herausfallen, nach "
            f"spätestens {hold} Sitzungen oder 8 % unter dem Kauf.")
    if fam == "lang":
        h, mind = int(p["fenster"]), int(p["mindesthaltedauer"])
        r = _regel(profil, kandidaten=[{"art": "rangliste", "gruppe": "A", "politik": "native", "gewichte": [60], "fenster": {"von": h, "bis": h}, "platz_bis": 10}],
                   sortierung={"schluessel": [{"kennzahl": _ref("rang", fenster=h, gewicht=60, gruppe="A", politik="native"), "richtung": "auf"}]},
                   verkauf={"herausfallen": {"aktiv": True, "puffer": 10}}, stop={"initial": {"art": "atr", "faktor": 3.0, "sitzungen": 14}},
                   optionen={"mindesthaltedauer_sitzungen": mind, "mindestorderwert_eur": 0})
        return r, f"Lang: Rangliste {h} Tage 60/40, mindestens {mind} Sitzungen halten", (
            f"Die ersten zehn der Lineal-Rangliste {h} Kalendertage, 60/40 (Gruppe A), bis zu 5, wöchentlich; Verkauf erst nach "
            f"mindestens {mind} Sitzungen und nach Herausfallen mit Puffer 10, Initialstop 3 × ATR.")
    raise LaborFehler(f"unbekannte Familie {fam}")


def _zahl(v: float) -> str:
    """Zahl für Namen und Beschreibungen (deutsches Komma)."""
    return f"{float(v):g}".replace(".", ",")


def _kurz(v: float) -> str:
    return str(int(v)) if float(v).is_integer() else f"{v:g}".replace(".", "p")


@dataclass(frozen=True)
class Variante:
    id: str
    familie: str
    parameter: dict
    regel: dict
    fingerabdruck: str

    @property
    def buchstabe(self) -> str:
        return FAMILIEN[self.familie][0]


def varianten(cfg: LaborConfig, eintraege: dict, method: MethodConfig, profil: str) -> list[Variante]:
    """Alle Varianten in fester Reihenfolge (Familie A–H, dann Gitter in der Reihenfolge der Konfiguration)."""
    out: list[Variante] = []
    for fam in FAMILIEN:
        grid = cfg.familien.get(fam)
        if not grid:
            continue
        names = list(GITTER[fam])
        for combo in itertools.product(*(grid[n] for n in names)):
            p = {n: (int(v) if float(v).is_integer() and isinstance(GITTER[fam][n][0], int) else float(v)) for n, v in zip(names, combo)}
            regel, name, text = _bauen(fam, p, profil)
            letter = FAMILIEN[fam][0]
            regel["id"] = f"r-lab-{letter.lower()}-" + "-".join(_kurz(v) for v in p.values())
            regel["name"] = f"Labor {letter}: {name}"[:80]
            regel["beschreibung"] = text
            regel["herkunft"] = {"vorlage": cfg.version}
            pr = regeln.pruefen(regel, eintraege, method)
            if not pr.gueltig:
                raise LaborFehler(f"Variante {regel['id']} ungültig: {[f.as_dict() for f in pr.fehler]}")
            out.append(Variante(pr.regel["id"], fam, p, pr.regel, regeln.fingerabdruck(pr.regel)))
    if len({v.id for v in out}) != len(out):
        raise LaborFehler("zwei Varianten mit gleicher Kennung – Gitterwerte doppelt?")
    return out


def nachbarn(v: Variante, alle: list[Variante], cfg: LaborConfig) -> list[Variante]:
    """Varianten derselben Familie, die sich in genau einem Parameter um genau einen Gitterschritt unterscheiden."""
    grid = cfg.familien[v.familie]
    out = []
    for w in alle:
        if w.familie != v.familie or w.id == v.id:
            continue
        diff = [n for n in grid if w.parameter[n] != v.parameter[n]]
        if len(diff) == 1:
            n = diff[0]
            werte = list(grid[n])
            if abs(werte.index(w.parameter[n]) - werte.index(v.parameter[n])) == 1:
                out.append(w)
    return out


# ------------------------------------------------------------------------------------------------------ Zeiträume


@dataclass(frozen=True)
class Zeitraum:
    schluessel: str  # e, v, t, w1t, w1p, …
    art: str  # entwicklung | validierung | test | training | pruefung
    tage: tuple[int, ...]
    faltung: int | None = None

    def as_dict(self) -> dict:
        out = {"schluessel": self.schluessel, "art": self.art, "von": _datum(self.tage[0]), "bis": _datum(self.tage[-1]), "tage": len(self.tage)}
        if self.faltung is not None:
            out["faltung"] = self.faltung
        return out


def zeitraeume(tage: list[int], cfg: LaborConfig) -> list[Zeitraum]:
    """Entwicklung, Validierung und Test (zeitlich getrennt, lückenlos aufeinander) und die Walk-forward-Faltungen."""
    n = len(tage)
    e = int(round(n * cfg.entwicklung_pct / 100.0))
    v = int(round(n * cfg.validierung_pct / 100.0))
    if min(e, v, n - e - v) < MIN_ZEITRAUM:
        raise LaborFehler(f"zu wenige Handelstage ({n}) für Entwicklung, Validierung und Test mit je mindestens {MIN_ZEITRAUM}")
    out = [Zeitraum("e", "entwicklung", tuple(tage[:e])), Zeitraum("v", "validierung", tuple(tage[e:e + v])), Zeitraum("t", "test", tuple(tage[e + v:]))]
    start, k = 0, 1
    while start + cfg.wf_training + cfg.wf_pruefung <= n:
        out.append(Zeitraum(f"w{k}t", "training", tuple(tage[start:start + cfg.wf_training]), k))
        out.append(Zeitraum(f"w{k}p", "pruefung", tuple(tage[start + cfg.wf_training:start + cfg.wf_training + cfg.wf_pruefung]), k))
        start += cfg.wf_pruefung
        k += 1
    return out


# ------------------------------------------------------------------------------------------------------ Bewertung


def _perzentile(werte: list[float | None], hoch_besser: bool) -> list[float]:
    """Perzentil 0–100 je Wert unter allen Werten (Gleichstand: Mittelwert; fehlend: 50)."""
    da = [(w if hoch_besser else -w) for w in werte if w is not None]
    out = []
    for w in werte:
        if w is None or len(da) < 2:
            out.append(50.0)
            continue
        x = w if hoch_besser else -w
        kleiner = sum(1 for y in da if y < x)
        gleich = sum(1 for y in da if y == x)
        out.append(100.0 * (kleiner + 0.5 * (gleich - 1)) / (len(da) - 1))
    return out


def kennzahlen_zeitraum(z: motor.DepotZustand, start_kapital: float, welt_pct: float | None) -> dict:
    """Kennzahlen eines Labordepots in seinem Zeitraum (aus ``backtest.kennzahlen``) plus Vergleich mit dem Welt-ETF."""
    k = backtest.kennzahlen(z, start_kapital)
    rendite = k.get("rendite_pct")
    if rendite is None:
        rendite = 0.0
    rueckgang = float(k.get("max_rueckgang_pct") or 0.0)
    return {
        "rendite_pct": round(float(rendite), 2), "abstand_welt_pp": None if welt_pct is None else round(float(rendite) - welt_pct, 2),
        "max_rueckgang_pct": round(rueckgang, 2), "rendite_je_rueckgang": round(float(rendite) / max(rueckgang, 1.0), 3),
        "gewinnquote_pct": k.get("gewinnquote_pct"), "kaeufe": int(k.get("kaeufe") or 0), "verkaeufe": int(k.get("verkaeufe") or 0),
        "kosten_eur": k.get("kosten_eur") or 0.0, "profitfaktor": k.get("profitfaktor"),
    }


def wertung(metriken: list[dict], gewichte: dict[str, float]) -> list[float]:
    """Mehrkriterienwertung 0–100 je Variante eines Zeitraums: gewichtete Perzentile (Abschnitt 14: nicht nur der höchste
    Gewinn). Fehlende Gewinnquote (kein Verkauf) zählt als Mitte."""
    spalten = {
        "rendite": _perzentile([m["rendite_pct"] for m in metriken], True),
        "abstand_welt": _perzentile([m["abstand_welt_pp"] for m in metriken], True),
        "rueckgang": _perzentile([m["max_rueckgang_pct"] for m in metriken], False),
        "rendite_je_rueckgang": _perzentile([m["rendite_je_rueckgang"] for m in metriken], True),
        "gewinnquote": _perzentile([m["gewinnquote_pct"] for m in metriken], True),
    }
    total = sum(gewichte.values())
    return [round(sum(gewichte[c] * spalten[c][i] for c in KRITERIEN) / total, 1) for i in range(len(metriken))]


def robust_grund(m: dict, cfg: LaborConfig) -> str | None:
    """Grund, warum eine Variante in einem Zeitraum nicht robust ist (``None`` = besteht)."""
    if m["kaeufe"] < cfg.mindest_kaeufe:
        return f"zu wenige Käufe ({m['kaeufe']} von mindestens {cfg.mindest_kaeufe}) – nicht beurteilbar"
    if m["max_rueckgang_pct"] > cfg.max_rueckgang_pct:
        return f"größter Rückgang {m['max_rueckgang_pct']:.1f} % über der Grenze von {cfg.max_rueckgang_pct:g} %".replace(".", ",")
    if m["rendite_pct"] <= 0:
        return "Rendite nach Kosten nicht positiv"
    return None


def _validierung_grund(m: dict, cfg: LaborConfig) -> str | None:
    if m["kaeufe"] < max(1, cfg.mindest_kaeufe // 2):
        return f"in der Validierung zu wenige Käufe ({m['kaeufe']})"
    if m["max_rueckgang_pct"] > cfg.max_rueckgang_pct:
        return f"in der Validierung Rückgang {m['max_rueckgang_pct']:.1f} % über der Grenze".replace(".", ",")
    if m["rendite_pct"] <= 0:
        return "in der Validierung nach Kosten nicht positiv"
    return None


def auswerten(vs: list[Variante], zr: list[Zeitraum], metriken: dict[tuple[str, str], dict], welt: dict[str, dict | None], cfg: LaborConfig) -> dict:
    """Auswahl, Validierung, Test und Walk-forward aus den Kennzahlen je (Zeitraum, Variante). Reine Funktion – testbar ohne
    Motor. Der Testzeitraum fließt in keine Entscheidung ein."""
    keys = {z.art: z.schluessel for z in zr if z.art in ("entwicklung", "validierung", "test")}
    scores = {z.schluessel: dict(zip([v.id for v in vs], wertung([metriken[(z.schluessel, v.id)] for v in vs], cfg.gewichte))) for z in zr}
    dev = {v.id: metriken[(keys["entwicklung"], v.id)] for v in vs}
    status: dict[str, tuple[str, str]] = {}
    for v in vs:
        grund = robust_grund(dev[v.id], cfg)
        if grund is None and cfg.nachbarn:
            nb = nachbarn(v, vs, cfg)
            if nb and not any(dev[w.id]["rendite_pct"] > 0 for w in nb):
                grund = "Einzeltreffer: keine benachbarte Variante im Gitter mit positiver Rendite"
        status[v.id] = ("verworfen", grund) if grund else ("robust", "")
    robust = sorted((v for v in vs if status[v.id][0] == "robust"), key=lambda v: (-scores[keys["entwicklung"]][v.id], v.id))
    finalisten = robust[: cfg.finalisten]
    for v in robust[cfg.finalisten:]:
        status[v.id] = ("nicht_ausgewaehlt", f"nicht unter den besten {cfg.finalisten} der Entwicklung")
    for v in finalisten:
        grund = _validierung_grund(metriken[(keys["validierung"], v.id)], cfg)
        status[v.id] = ("validierung_verfehlt", grund) if grund else ("validiert", "in Entwicklung und Validierung robust")
    validiert = sorted((v for v in finalisten if status[v.id][0] == "validiert"),
                       key=lambda v: (-(scores[keys["entwicklung"]][v.id] + scores[keys["validierung"]][v.id]) / 2.0, v.id))
    vorwaerts = [v.id for v in validiert[: cfg.vorwaerts]]
    for vid in vorwaerts:
        status[vid] = ("vorwaerts", "validiert – als eigenes Spielgelddepot im Vorwärtstest vorgeschlagen")

    # Walk-forward: dasselbe Verfahren (robust im Training, beste Wertung) je Faltung, Ergebnis im Prüfzeitraum
    faltungen = []
    for k in sorted({z.faltung for z in zr if z.faltung is not None}):
        t = next(z for z in zr if z.faltung == k and z.art == "training")
        p = next(z for z in zr if z.faltung == k and z.art == "pruefung")
        kandidaten = [v for v in vs if robust_grund(metriken[(t.schluessel, v.id)], cfg) is None]
        wahl = min(kandidaten, key=lambda v: (-scores[t.schluessel][v.id], v.id)) if kandidaten else None
        eintrag = {"faltung": k, "training": t.as_dict(), "pruefung": p.as_dict(), "gewaehlt": wahl.id if wahl else None,
                   "welt_pct": None if welt.get(p.schluessel) is None else welt[p.schluessel]["rendite_pct"]}
        if wahl is not None:
            m = metriken[(p.schluessel, wahl.id)]
            eintrag.update(rendite_pct=m["rendite_pct"], max_rueckgang_pct=m["max_rueckgang_pct"], abstand_welt_pp=m["abstand_welt_pp"],
                           training_rendite_pct=metriken[(t.schluessel, wahl.id)]["rendite_pct"])
        faltungen.append(eintrag)
    gewaehlt = [f for f in faltungen if f["gewaehlt"]]
    zusammen = {
        "faltungen": len(faltungen), "mit_wahl": len(gewaehlt),
        "mittel_rendite_pct": None if not gewaehlt else round(float(np.mean([f["rendite_pct"] for f in gewaehlt])), 2),
        "mittel_welt_pct": None if not [f for f in gewaehlt if f["welt_pct"] is not None] else round(float(np.mean([f["welt_pct"] for f in gewaehlt if f["welt_pct"] is not None])), 2),
        "besser_als_welt": sum(1 for f in gewaehlt if f.get("abstand_welt_pp") is not None and f["abstand_welt_pp"] > 0),
        "positiv": sum(1 for f in gewaehlt if f["rendite_pct"] > 0),
        "wechsel": sum(1 for a, b in zip(gewaehlt, gewaehlt[1:]) if a["gewaehlt"] != b["gewaehlt"]),
    }

    # Wirkung der Parameter (Abschnitt 13): Median der Entwicklungsrendite je Familie, Parameter und Wert
    wirkung = []
    for fam in FAMILIEN:
        fvs = [v for v in vs if v.familie == fam]
        if len(fvs) < 2:
            continue
        for name in GITTER[fam]:
            werte = []
            for wert in cfg.familien[fam][name]:
                rs = [dev[v.id]["rendite_pct"] for v in fvs if v.parameter[name] == wert]
                if rs:
                    werte.append({"wert": wert, "median_rendite_pct": round(float(np.median(rs)), 2), "varianten": len(rs), "positiv": sum(1 for r in rs if r > 0)})
            if len(werte) > 1:
                wirkung.append({"familie": FAMILIEN[fam][0], "parameter": name, "werte": werte})

    varianten_out = []
    for v in vs:
        st, grund = status[v.id]
        eintrag = {"id": v.id, "familie": v.buchstabe, "familie_name": FAMILIEN[v.familie][1], "name": v.regel["name"], "parameter": v.parameter,
                   "fingerabdruck": v.fingerabdruck, "status": st, "grund": grund,
                   "entwicklung": dict(dev[v.id], wertung=scores[keys["entwicklung"]][v.id])}
        if st in ("validiert", "vorwaerts", "validierung_verfehlt"):
            eintrag["validierung"] = dict(metriken[(keys["validierung"], v.id)], wertung=scores[keys["validierung"]][v.id])
        if st in ("validiert", "vorwaerts"):
            eintrag["test"] = dict(metriken[(keys["test"], v.id)])  # nur berichtet, keine Auswahl
            eintrag["regel"] = v.regel
        varianten_out.append(eintrag)
    zaehlung = {s: sum(1 for v in vs if status[v.id][0] == s) for s in ("verworfen", "nicht_ausgewaehlt", "validierung_verfehlt", "validiert", "vorwaerts")}
    return {"varianten": varianten_out, "vorwaerts": vorwaerts, "walk_forward": {"faltungen": faltungen, "zusammenfassung": zusammen},
            "parameterwirkung": wirkung, "zaehlung": zaehlung,
            "positiv_entwicklung": sum(1 for v in vs if dev[v.id]["rendite_pct"] > 0)}


# ------------------------------------------------------------------------------------------------------ Signalprüfung


_RANG = {"fenster": 30, "gewicht": 60, "gruppe": "A", "politik": "native"}
# Abschnitte 5.2, 5.3 und 6: Ließen Platz-1-Häufigkeit, Top-10-Stabilität und Trendqualität bessere Folgerenditen erwarten?
SIGNALE: tuple[tuple[str, str, dict, str, float], ...] = (
    ("platz1", "Platz 1 in einer Renditerangliste 1–30 Tage",
     {"id": "haeufigkeit", "parameter": {"k": 1, "fenster": {"von": 1, "bis": 30}, "gewichte": [0], "gruppe": "A", "politik": "native"}}, ">=", 1),
    ("platz1_oft", "mindestens 5 erste Plätze (1–30 Tage, alle elf Gewichtungen)",
     {"id": "haeufigkeit", "parameter": {"k": 1, "fenster": {"von": 1, "bis": 30}, "gewichte": ALLE_GEWICHTE, "gruppe": "A", "politik": "native"}}, ">=", 5),
    ("top10", "Top 10 der Rangliste 30 Tage, 60/40", {"id": "rang", "parameter": dict(_RANG)}, "<=", 10),
    ("stabil", "an mindestens 6 der letzten 10 Stichtage in diesen Top 10", {"id": "top_stichtage", "parameter": dict(_RANG, k=10, stichtage=10)}, ">=", 6),
    ("gleichmaessig", "Anstieg je Schwankung (60 Sitzungen) mindestens 2", {"id": "anstieg_je_schwankung", "parameter": {"sitzungen": 60}}, ">=", 2),
)
HORIZONTE = (5, 20)


class Signalpruefung:
    """Sammelt je Handelstag, welche Aktien ein Signal hatten (mit denselben Katalogwerten wie die Regeln, Daten nur bis zu
    diesem Tag), und wertet danach die Folgerenditen gegen das Mittel aller Aktien desselben Tages aus. Keine
    Gewinnwahrscheinlichkeit: Folgezeiträume benachbarter Tage überlappen."""

    def __init__(self, quelle: backtest.Kontextquelle, archiv, eintraege: dict):
        self.quelle = quelle
        self.archiv = archiv
        self.eintraege = eintraege
        self.tage: dict[int, dict[str, list[str]]] = {}
        self.isins: dict[int, list[str]] = {}

    def __call__(self, D: int) -> None:
        from . import katalog as kat

        base = self.quelle.kontext(int(D))
        ctx = kat.Kontext(tag=base.tag, isins=base.isins, method=base.method, comp=base.comp, markt=base.markt, cfg=base.cfg, stamm=base.stamm,
                          fakten=base.fakten, modus=base.modus, archiv=self.archiv, _cache=base._cache, _index=base._index)
        treffer = {}
        for sid, _text, ref, op, schwelle in SIGNALE:
            try:
                _, _, werte = kat.werte(ctx, self.eintraege, ref)
            except kat.KatalogFehler:
                continue
            arr = np.asarray(werte, dtype=np.float64)
            ok = np.isfinite(arr) & ((arr >= schwelle) if op == ">=" else (arr <= schwelle))
            treffer[sid] = [ctx.isins[i] for i in np.nonzero(ok)[0]]
        self.tage[int(D)] = treffer
        self.isins[int(D)] = list(ctx.isins)

    def _folge(self, isin: str, D: int, n: int) -> float | None:
        s = self.quelle.markt.series.get(isin)
        if s is None:
            return None
        k = s.index_of(int(D))
        if k is None or k + n >= len(s.close) or not (s.close[k] > 0 and s.close[k + n] > 0):
            return None
        return float(s.close[k + n] / s.close[k] - 1.0)

    def auswerten(self) -> dict:
        out = []
        for sid, text, _ref, _op, _schwelle in SIGNALE:
            for n in HORIZONTE:
                ueberschuss, renditen, signale = [], [], 0
                for D, treffer in sorted(self.tage.items()):
                    gruppe = [r for r in (self._folge(i, D, n) for i in treffer.get(sid, ())) if r is not None]
                    if not gruppe:
                        continue
                    alle = [r for r in (self._folge(i, D, n) for i in self.isins[D]) if r is not None]
                    if len(alle) < 2:
                        continue
                    ueberschuss.append(float(np.mean(gruppe) - np.mean(alle)))
                    renditen.append(float(np.mean(gruppe)))
                    signale += len(gruppe)
                eintrag = {"signal": sid, "text": text, "horizont": n, "tage": len(ueberschuss), "signale": signale}
                if ueberschuss:
                    eintrag.update(mittel_rendite_pct=round(100.0 * float(np.mean(renditen)), 2), mittel_ueberschuss_pp=round(100.0 * float(np.mean(ueberschuss)), 2),
                                   median_ueberschuss_pp=round(100.0 * float(np.median(ueberschuss)), 2),
                                   trefferquote_pct=round(100.0 * sum(1 for x in ueberschuss if x > 0) / len(ueberschuss), 1))
                out.append(eintrag)
        return {"horizonte": list(HORIZONTE), "ergebnisse": out,
                "hinweis": "Folgerendite nach n Handelstagen gegen das Mittel aller Aktien desselben Tages; benachbarte Tage überlappen, "
                           "deshalb keine unabhängigen Fälle und keine Gewinnwahrscheinlichkeit. Ranglisten früherer Tage nachgerechnet."}


# ------------------------------------------------------------------------------------------------------ Lauf


def _datum(day: int) -> str:
    return day_to_date(int(day)).isoformat()


def durchfuehren(*, quelle: backtest.Kontextquelle, archiv, tage: list[int], cfg: LaborConfig, ap_cfg, method: MethodConfig, eintraege: dict,
                 calendars, stamm_fn: Callable[[str], dict], synthetisch: bool, datenstand: str, erstellt: dt.datetime,
                 log: Callable[[str], None] | None = None) -> dict:
    """Ein vollständiger Laborlauf auf bereits geladenen Daten. Rückgabe: Ergebnis (Schema ``tr-labor/1``)."""
    started = dt.datetime.now(dt.timezone.utc)
    tage = [int(d) for d in tage][-cfg.tage:]
    vs = varianten(cfg, eintraege, method, ap_cfg.depot.ausfuehrungsprofil)
    zr = zeitraeume(tage, cfg)
    welt_isin = ap_cfg.msci_world.isin if ap_cfg.msci_world else None
    prefix = "demo-" if synthetisch else ""
    defs: list[motor.DepotDef] = []
    bis: dict[str, int] = {}
    for z in zr:
        for i, v in enumerate(vs):
            did = f"{prefix}lab-{z.schluessel}-{i:03d}"
            defs.append(motor.DepotDef(did, f"{v.regel['name']} ({z.art})", "forschung", cfg.startkapital_eur, z.tage[0], 1.0,
                                       (motor.StrategieDef(v.regel["id"], v.regel, 1.0),), None, synthetisch, "Strategielabor"))
            bis[did] = z.tage[-1]
        if welt_isin:
            did = f"{prefix}lab-{z.schluessel}-welt"
            defs.append(motor.DepotDef(did, "Welt-ETF (Labor)", "vergleich", cfg.startkapital_eur, z.tage[0], 0.0, (),
                                       motor.KernDef({welt_isin: 1.0}, ap_cfg.s4.rebalancing_schwelle_pp, False), synthetisch, "Strategielabor"))
            bis[did] = z.tage[-1]
    alle_tage = sorted({d for z in zr for d in z.tage})
    pruefung = Signalpruefung(quelle, archiv, eintraege)
    res = backtest.laufen(defs, alle_tage, quelle, cfg=ap_cfg, method=method, eintraege=eintraege, calendars=calendars, stamm_fn=stamm_fn,
                          synthetisch=synthetisch, modus="backtest", archiv=archiv, bis=bis, je_tag=pruefung)
    welt: dict[str, dict | None] = {}
    for z in zr:
        wid = f"{prefix}lab-{z.schluessel}-welt"
        welt[z.schluessel] = kennzahlen_zeitraum(res.depots[wid], cfg.startkapital_eur, None) if wid in res.depots else None
    metriken: dict[tuple[str, str], dict] = {}
    for z in zr:
        wp = None if welt[z.schluessel] is None else welt[z.schluessel]["rendite_pct"]
        for i, v in enumerate(vs):
            metriken[(z.schluessel, v.id)] = kennzahlen_zeitraum(res.depots[f"{prefix}lab-{z.schluessel}-{i:03d}"], cfg.startkapital_eur, wp)
    ergebnis = auswerten(vs, zr, metriken, welt, cfg)
    sekunden = (dt.datetime.now(dt.timezone.utc) - started).total_seconds()
    e, v, t = (next(z for z in zr if z.art == a) for a in ("entwicklung", "validierung", "test"))
    hinweise = [
        "Nachgerechnet mit der heutigen Datenrevision und dem heutigen Universum: Rückschau- und Überlebensverzerrung möglich; kein Vorwärtsergebnis.",
        f"{len(vs)} Varianten geprüft – ein gutes Einzelergebnis kann Zufall sein. Deshalb zählen Robustheit, Nachbarvarianten, die Validierung und der Walk-forward; der Testzeitraum wählt nichts aus.",
        f"Kurze Zeiträume ({len(e.tage)} / {len(v.tage)} / {len(t.tage)} Handelstage für Entwicklung, Validierung, Test): kleine Stichproben, wenige Marktphasen.",
        "Offene Positionen am Ende eines Zeitraums sind zum Schlusskurs bewertet (ohne Verkaufskosten); Kosten und Ausführung wie im Vorwärtstest.",
        "Ranglisten früherer Stichtage (Rangverlauf) stammen aus der Nachrechnung, nicht aus dem Archiv veröffentlichter Stände.",
    ]
    if synthetisch:
        hinweise.insert(0, "DEMO – synthetische Kurse, keine echten Wertpapiere.")
    kern = {"version": cfg.version, "datenstand": datenstand, "tage": [tage[0], tage[-1], len(tage)],
            "varianten": [v.fingerabdruck for v in vs], "konfiguration": cfg.as_dict()}
    lab_id = "lab-" + hashlib.sha256(json.dumps(kern, sort_keys=True).encode("utf-8")).hexdigest()[:12]
    payload = {
        "schema": SCHEMA, "id": lab_id, "version": cfg.version, "modus": "DEMO" if synthetisch else "PAPER", "synthetisch": synthetisch,
        "erstellt_utc": erstellt.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z"), "datenstand": datenstand,
        "datentag": _datum(tage[-1]), "zeitraeume": [z.as_dict() for z in zr],
        "vergleich": {z.schluessel: welt[z.schluessel] for z in zr},
        "uebernahme": {"modus": cfg.modus, "vorwaerts": ergebnis["vorwaerts"]},
        "konfiguration": cfg.as_dict(), "hinweise": hinweise,
        "kennzahlen": {"varianten": len(vs), "depots": len(defs), "tage": len(alle_tage), "rechnungen": quelle.rechnungen,
                       "sekunden": {"gesamt": round(sekunden, 1), "rechenkern": round(quelle.rechenzeit_s, 1)}},
        **{k: ergebnis[k] for k in ("varianten", "walk_forward", "parameterwirkung", "zaehlung", "positiv_entwicklung")},
        "signalpruefung": pruefung.auswerten(),
    }
    if log is not None:
        z = ergebnis["zaehlung"]
        log(f"Strategielabor: {len(vs)} Varianten, {len(zr)} Zeiträume, {len(defs)} Depots, {len(alle_tage)} Handelstage; verworfen {z['verworfen']}, "
            f"validiert {z['validiert'] + z['vorwaerts']}, vorwärts {z['vorwaerts']}; Rechenkern {quelle.rechnungen}× in {quelle.rechenzeit_s:.1f} s, gesamt {sekunden:.1f} s")
    return payload


# ------------------------------------------------------------------------------------------------------ Zustand


def json_dumps(payload: dict) -> bytes:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")


def speichern(conn: sqlite3.Connection, payload: dict, now: dt.datetime) -> int:
    """Ergebnis im Zustand ablegen (gleiche Kennung ersetzt nichts; es bleiben die neuesten ``STAENDE_BEHALTEN``)."""
    raw = json_dumps(payload)
    blob = zlib.compress(raw, 9)
    with db.Transaction(conn):
        conn.execute("INSERT OR IGNORE INTO ap_labor(id, datentag, erstellt_am, version, modus, groesse, sha256, inhalt) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                     (payload["id"], payload["datentag"], now.astimezone(dt.timezone.utc).isoformat(), payload["version"], payload["modus"], len(raw),
                      hashlib.sha256(raw).hexdigest(), blob))
        keep = [r[0] for r in conn.execute("SELECT id FROM ap_labor ORDER BY erstellt_am DESC, id DESC LIMIT ?", (STAENDE_BEHALTEN,))]
        conn.execute(f"DELETE FROM ap_labor WHERE id NOT IN ({','.join('?' * len(keep))})", keep)
    return len(blob)


def neuester(conn: sqlite3.Connection, modus: str) -> dict | None:
    """Neuestes Laborergebnis für DEMO bzw. PAPER (nie gemischt)."""
    try:
        row = conn.execute("SELECT inhalt, sha256 FROM ap_labor WHERE modus = ? ORDER BY erstellt_am DESC, id DESC LIMIT 1", (modus,)).fetchone()
    except sqlite3.OperationalError:
        return None
    if row is None:
        return None
    raw = zlib.decompress(row[0])
    if hashlib.sha256(raw).hexdigest() != row[1]:
        raise LaborFehler("Laborergebnis im Zustand beschädigt (Prüfsumme)")
    return json.loads(raw)


def vorwaerts_depots(conn: sqlite3.Connection, ap_cfg, *, synthetisch: bool, start_tag: int, eintraege: dict | None = None,
                     method: MethodConfig | None = None) -> list[motor.DepotDef]:
    """Spielgelddepots der zum Vorwärtstest vorgeschlagenen Varianten des neuesten Laborlaufs (Abschnitt 12, Punkt 9).
    Eigene Depots mit dem Startkapital der Forschungsdepots; die Regel bleibt unverändert die validierte Variante. Mit Katalog
    wird jede Regel vor dem Start erneut geprüft (eine Regel, die der heutige Katalog nicht annimmt, startet nicht)."""
    payload = neuester(conn, "DEMO" if synthetisch else "PAPER")
    if payload is None:
        return []
    prefix = "demo-" if synthetisch else ""
    by_id = {v["id"]: v for v in payload["varianten"]}
    out = []
    for vid in payload["uebernahme"]["vorwaerts"]:
        v = by_id.get(vid)
        if v is None or "regel" not in v:
            continue
        r = v["regel"]
        if eintraege is not None and method is not None:
            pr = regeln.pruefen(r, eintraege, method)
            if not pr.gueltig or pr.regel != r:
                continue
        out.append(motor.DepotDef(f"{prefix}{PREFIX_VORWAERTS}{vid.removeprefix('r-')}", f"Labor vorwärts: {r['name'].removeprefix('Labor ')}", "forschung",
                                  float(ap_cfg.depot.demo_startkapital_eur), start_tag, 1.0, (motor.StrategieDef(r["id"], r, 1.0),), None, synthetisch,
                                  # ohne Laufkennung: schlägt ein späterer Laborlauf dieselbe Variante vor, läuft ihr Test weiter
                                  f"Im Strategielabor validiert (Entwicklung und Validierung robust); Vorwärtstest mit Spielgeld. {r.get('beschreibung', '')}".strip()))
    return out


def ist_labordepot(depot_id: str) -> bool:
    return depot_id.removeprefix("demo-").startswith(PREFIX_VORWAERTS)


# ------------------------------------------------------------------------------------------------------ Ablage und Übernahme


def dateiname(payload: dict) -> str:
    """``<Zeitstempel>-<Kennung>`` – nach Namen sortiert ist die neueste Ablage die letzte."""
    stamp = dt.datetime.fromisoformat(payload["erstellt_utc"].replace("Z", "+00:00")).astimezone(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{stamp}-{payload['id']}"


def exportieren(payload: dict, key) -> bytes:
    """Ergebnis für den Branch: verschlüsselt mit dem Datenschlüssel, gebunden an die Kennung (AAD ``labor/<id>``)."""
    if key is None and not payload.get("synthetisch"):
        raise LaborFehler("ohne Datenschlüssel wird kein Laborergebnis mit echten Kursen abgelegt")
    return crypto.pack(json_dumps(payload), key, f"{ORDNER}/{payload['id']}")


def _verschluesselt(blob: bytes) -> bool:
    return len(blob) > 4 and blob[:4] == crypto.MAGIC and bool(blob[4] & crypto.FLAG_ENCRYPTED)


def prune_names(names: list[str], now: dt.datetime) -> list[str]:
    """Beim Ablegen entfernen: Fremdes und alles außer den neuesten ``ABLAGE_BEHALTEN`` Ergebnissen."""
    del now
    gueltig = sorted((n for n in names if n.startswith(f"{ORDNER}/") and n.endswith(".bin") and DATEI_RE.match(n[len(ORDNER) + 1:-4])), reverse=True)
    keep = set(gueltig[:ABLAGE_BEHALTEN])
    return [n for n in names if n not in keep]


def aus_ordner(root: Path) -> list[tuple[str, bytes]]:
    """Abgelegte Ergebnisse aus einem Ordner (DEMO und Tests; Aufbau wie der Branch)."""
    folder = Path(root) / ORDNER
    if not folder.is_dir():
        return []
    return [(p.stem, p.read_bytes()) for p in sorted(folder.glob("*.bin")) if DATEI_RE.match(p.stem)]


def aus_git(repository: str, token: str, *, server: str = "https://github.com", branch: str = BRANCH) -> list[tuple[str, bytes]]:
    """Abgelegte Ergebnisse vom Branch „spielgeld-labor“ (flacher Abruf mit dem Token des Laufs; das Token erscheint nie)."""
    from ..jobs.kursaktualisierung import GitLieferkanal, _git

    channel = GitLieferkanal(repository, token, server=server, branch=branch, ordner=ORDNER, prune=prune_names, titel="Spielgeld-Labor")
    try:
        env = channel._env()
        try:
            _git(["fetch", "-q", "--depth=1", "origin", branch], channel.work, env)
        except subprocess.CalledProcessError:
            return []  # noch kein Laborlauf abgelegt
        out = []
        for name in sorted(_git(["ls-tree", "-r", "--name-only", "FETCH_HEAD"], channel.work, env).stdout.split()):
            stem = name[len(ORDNER) + 1:-4] if name.startswith(f"{ORDNER}/") and name.endswith(".bin") else ""
            if DATEI_RE.match(stem):
                blob = subprocess.run(["git", "show", f"FETCH_HEAD:{name}"], cwd=channel.work, env=env, check=True, capture_output=True, timeout=60).stdout
                out.append((stem, blob))
        return out
    finally:
        channel.close()


def uebernehmen(conn: sqlite3.Connection, items: list[tuple[str, bytes]], *, key, synthetisch: bool, D: int, now: dt.datetime) -> dict:
    """Abgelegte Laborergebnisse in den Zustand übernehmen (täglicher Lauf, einziger Schreiber): nur entschlüsselbar mit dem
    Datenschlüssel und an die Kennung gebunden, gleicher Modus (DEMO/PAPER), Datentag nicht nach dem Stichtag; jedes genau
    einmal. Rückgabe: Zählungen (öffentlich)."""
    counts = {"neu": 0, "bekannt": 0, "abgelehnt": 0}
    modus = "DEMO" if synthetisch else "PAPER"
    for stem, blob in sorted(items):
        m = DATEI_RE.match(stem)
        if m is None:
            counts["abgelehnt"] += 1
            continue
        lab_id = m.group(2)
        if conn.execute("SELECT 1 FROM ap_labor WHERE id = ?", (lab_id,)).fetchone() is not None:
            counts["bekannt"] += 1
            continue
        if key is not None and not _verschluesselt(blob):
            counts["abgelehnt"] += 1  # mit Datenschlüssel nur verschlüsselte Ergebnisse (niemand legt Klartext unter)
            continue
        try:
            payload = json.loads(crypto.unpack(blob, key, f"{ORDNER}/{lab_id}"))
            ok = (payload.get("schema") == SCHEMA and payload.get("id") == lab_id and payload.get("modus") == modus
                  and date_to_day(dt.date.fromisoformat(payload["datentag"])) <= int(D) and isinstance(payload.get("varianten"), list)
                  and set(payload["uebernahme"]["vorwaerts"]) <= {v["id"] for v in payload["varianten"] if "regel" in v})
        except (crypto.ContainerError, ValueError, KeyError, TypeError):
            ok = False
        if not ok:
            counts["abgelehnt"] += 1
            continue
        speichern(conn, payload, now)
        counts["neu"] += 1
    return counts


# ------------------------------------------------------------------------------------------------------ Lauf auf dem Zustand


def lauf(conn: sqlite3.Connection, *, ap_cfg, method: MethodConfig, mode: str, now: dt.datetime, calendars, provider=None, key=None,
         cfg: LaborConfig | None = None, tage: int | None = None, stand_bauen: bool = True,
         log: Callable[[str], None] = print) -> tuple[dict, dict]:
    """Laborlauf auf dem gespeicherten Zustand (neuester veröffentlichter Stand): Kerzen und Rechenkern-Eingaben wie die
    historische Simulation, Ergebnis in ``ap_labor``, danach ein neuer Spielgeld-Stand für die App (verschlüsselt mit
    ``key``). Die Depots des Labors werden nicht gespeichert – nur ihre Auswertung. Rückgabe: Zusammenfassung nur mit Zahlen."""
    from . import katalog as kat
    from . import simulation, stand, tageslauf
    from ..store import repo

    cfg = cfg or load_labor_config()
    if tage is not None:
        cfg = mit_tagen(cfg, int(tage))
    published = repo.published_snapshots(conn, mode)
    if not published:
        raise LaborFehler("kein veröffentlichter Stand im Zustand")
    latest = published[0]
    D = int(latest["cutoff_day"])
    members = repo.universe_members(conn, latest["universe_id"])
    synthetisch = mode == "demo"
    vorlauf_stichtage = max([int(s) for s in cfg.familien.get("stabil_vorausbruch", {}).get("stichtage", ())] or [0])
    span = int((cfg.tage + vorlauf_stichtage) * 7 / 5) + 14
    von = D - span - tageslauf.MARKTREIHE_TAGE
    started = dt.datetime.now(dt.timezone.utc)
    series, inputs, metas, skipped = simulation._laden(conn, members, von, D, calendars, synthetisch)
    if provider is not None:
        tageslauf.marktreihen_abrufen(conn, provider, ap_cfg, D, now)
    etfs, indices = tageslauf.marktreihen_laden(conn, ap_cfg, von, D, synthetisch)
    series.update(etfs)
    from .markt import Market

    fx = simulation._fx(conn, von, method)
    market = Market(series=series, fx=fx, indices=indices, synthetic=synthetisch, data_stand=latest["id"], source="Zustand (Strategielabor)")
    stamm = tageslauf.stammdaten(conn, metas, ap_cfg)
    eintraege = kat.katalog(method, ap_cfg)
    stock_days = np.unique(np.concatenate([s.days for i, s in series.items() if i in members])) if metas else np.empty(0, dtype=np.int64)
    days = [int(d) for d in stock_days[(stock_days > D - span) & (stock_days <= D)]]
    if len(days) < cfg.tage:
        raise LaborFehler(f"zu wenige Handelstage im Zustand ({len(days)} von {cfg.tage})")
    quelle = backtest.Kontextquelle(method, ap_cfg, market, inputs, stamm, int(method.max_window), fx,
                                    fakten_fn=lambda day: tageslauf.fakten_zum_tag(conn, day, series))
    archiv = backtest.NachgerechnetesArchiv(quelle, [int(d) for d in stock_days if int(d) <= D])
    load_s = (dt.datetime.now(dt.timezone.utc) - started).total_seconds()
    payload = durchfuehren(quelle=quelle, archiv=archiv, tage=days, cfg=cfg, ap_cfg=ap_cfg, method=method, eintraege=eintraege, calendars=calendars,
                           stamm_fn=lambda isin: stamm.get(isin, {}), synthetisch=synthetisch, datenstand=latest["id"], erstellt=now, log=log)
    payload["kennzahlen"]["sekunden"]["laden"] = round(load_s, 1)
    payload["kennzahlen"]["aktien"] = len(inputs)
    payload["kennzahlen"]["ausgelassen"] = skipped
    size = speichern(conn, payload, now)
    stand_id, stand_bytes = None, 0
    if stand_bauen:
        app = stand.bauen(conn, D=D, snapshot_id=latest["id"], modus=payload["modus"], now=now, eintraege=eintraege, method=method, cfg=ap_cfg,
                          stamm=stamm, market=market)
        with db.Transaction(conn):
            stand_bytes = stand.speichern(conn, app, key, now)
        stand_id = app["id"]
    return {"id": payload["id"], "stand": stand_id, "stand_bytes": stand_bytes, "varianten": payload["kennzahlen"]["varianten"], "depots": payload["kennzahlen"]["depots"],
            "tage": payload["kennzahlen"]["tage"], "aktien": len(inputs), "ausgelassen": skipped, "zaehlung": payload["zaehlung"],
            "walk_forward": {k: payload["walk_forward"]["zusammenfassung"][k] for k in ("faltungen", "mit_wahl", "positiv", "besser_als_welt")},
            "rechnungen": payload["kennzahlen"]["rechnungen"], "sekunden": payload["kennzahlen"]["sekunden"], "bytes": size}, payload

