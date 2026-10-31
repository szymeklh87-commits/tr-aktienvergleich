"""Vorlagen des Regel-Baukastens: S1–S3, Lineal-Vorwärtsdepot und editierbare Beispielregeln (Abschnitte 6, 8–10, 31.6).

Alle Vorlagen sind gewöhnliche Regeln (Schema ``tr-regel/1``) und laufen durch denselben Motor wie eigene Regeln – es gibt
keinen zweiten Strategiecode (Abschnitt 32.1). Ihre Parameter kommen ausschließlich aus ``config/aktienpilot.yaml``
(Abschnitte ``strategien`` und ``marktfilter``); Änderungen dort erzeugen über den Fingerabdruck eine neue Regelversion.
Beispielregeln sind ausdrücklich Vorlagen zum Bearbeiten – keine ungefragt festgelegte Nutzerstrategie.
"""

from __future__ import annotations

from .config import AktienPilotConfig


def _ref(kid: str, **params) -> dict:
    out = {"id": kid}
    if params:
        out["parameter"] = params
    return out


def _marktfilter(cfg: AktienPilotConfig) -> list[dict]:
    if not cfg.marktfilter.aktiv:
        return []
    return [{"kennzahl": _ref("marktfilter", sitzungen=cfg.marktfilter.ma), "op": "ist_wahr"}]


def s1(cfg: AktienPilotConfig) -> dict:
    p = cfg.s1
    n = p.regression_sitzungen
    return {
        "schema": "tr-regel/1", "id": "r-s1", "version": 1, "name": "S1 Momentum-Rotation",
        "beschreibung": f"Log-Regression über {n} Handelstage, Perzentile von Gleichmäßigkeit ({p.gewicht_gleichmaessigkeit:g}) und Steigung ({p.gewicht_steigung:g}); "
                        f"Kurs über MA{p.ma_filter}, keine Übernachtlücke über {p.max_luecke * 100:g} % in {p.luecke_sitzungen} Sitzungen; wöchentlich, Rangpuffer {p.rangpuffer}.",
        "herkunft": {"vorlage": p.version},
        "kandidaten": [{"art": "universum"}],
        "filter": {"und": [
            {"kennzahl": _ref("log_steigung_jahr", sitzungen=n), "op": ">", "wert": 0},
            {"kennzahl": _ref("kurs"), "op": ">", "vergleich": _ref("ma", sitzungen=p.ma_filter)},
            {"kennzahl": _ref("max_luecke", sitzungen=p.luecke_sitzungen), "op": "<=", "wert": p.max_luecke * 100.0},
            *_marktfilter(cfg),
        ]},
        "sortierung": {"score": [
            {"kennzahl": _ref("log_r2", sitzungen=n), "gewicht": p.gewicht_gleichmaessigkeit, "richtung": "ab"},
            {"kennzahl": _ref("log_steigung_jahr", sitzungen=n), "gewicht": p.gewicht_steigung, "richtung": "ab"},
        ]},
        "auswahl": {"anzahl": p.anzahl},
        "kapital": {"art": "risiko"},
        "kauf": {"ausloeser": "termin"},
        "verkauf": {"herausfallen": {"aktiv": True, "puffer": p.rangpuffer}},
        "stop": {"initial": {"art": "atr", "faktor": p.initialstop_atr, "sitzungen": p.atr}},
        "zeitplan": {"intervall": "woechentlich", "wochentag": p.umschichtung_wochentag},
        "profil": cfg.depot.ausfuehrungsprofil,
    }


def s2(cfg: AktienPilotConfig) -> dict:
    p = cfg.s2
    return {
        "schema": "tr-regel/1", "id": "r-s2", "version": 1, "name": "S2 Swing-Breakout",
        "beschreibung": f"Schluss über dem Hoch der vorherigen {p.hoch_sitzungen} Sitzungen bei Volumen ≥ {p.volumen_faktor:g}× des Durchschnitts der {p.volumen_sitzungen} Sitzungen davor; "
                        f"Initialstop {p.initialstop_atr:g}× ATR({p.atr}), Trailing-Stop {p.trailing_atr:g}× ATR.",
        "herkunft": {"vorlage": p.version},
        "kandidaten": [{"art": "universum"}],
        "filter": {"und": [
            {"kennzahl": _ref("ausbruch_hoch", sitzungen=p.hoch_sitzungen), "op": "ist_wahr"},
            {"kennzahl": _ref("volumenfaktor", sitzungen=p.volumen_sitzungen), "op": ">=", "wert": p.volumen_faktor},
            *_marktfilter(cfg),
        ]},
        "sortierung": {"schluessel": [{"kennzahl": _ref("volumenfaktor", sitzungen=p.volumen_sitzungen), "richtung": "ab"}]},
        "auswahl": {"anzahl": p.anzahl},
        "kapital": {"art": "risiko"},
        "kauf": {"ausloeser": "neues_signal"},
        "verkauf": {"herausfallen": {"aktiv": False, "puffer": 0}},
        "stop": {"initial": {"art": "atr", "faktor": p.initialstop_atr, "sitzungen": p.atr},
                 "trailing": {"art": "atr", "faktor": p.trailing_atr, "sitzungen": p.atr}},
        "zeitplan": {"intervall": "taeglich"},
        "profil": cfg.depot.ausfuehrungsprofil,
    }


def s3(cfg: AktienPilotConfig) -> dict:
    p = cfg.s3
    return {
        "schema": "tr-regel/1", "id": "r-s3", "version": 1, "name": "S3 Mean-Reversion",
        "beschreibung": f"RSI({p.rsi_periode}) unter {p.rsi_kauf_unter:g} und Schluss über MA{p.ma_trend}; Ausstieg bei Schluss über MA{p.ma_ausstieg} "
                        f"oder nach {p.max_haltedauer} Sitzungen.",
        "herkunft": {"vorlage": p.version},
        "kandidaten": [{"art": "universum"}],
        "filter": {"und": [
            {"kennzahl": _ref("rsi", sitzungen=p.rsi_periode), "op": "<", "wert": p.rsi_kauf_unter},
            {"kennzahl": _ref("kurs"), "op": ">", "vergleich": _ref("ma", sitzungen=p.ma_trend)},
            *_marktfilter(cfg),
        ]},
        "sortierung": {"schluessel": [{"kennzahl": _ref("rsi", sitzungen=p.rsi_periode), "richtung": "auf"}]},
        "auswahl": {"anzahl": p.anzahl},
        "kapital": {"art": "risiko"},
        "kauf": {"ausloeser": "neues_signal"},
        "verkauf": {"herausfallen": {"aktiv": False, "puffer": 0},
                    "ausstieg": {"kennzahl": _ref("kurs"), "op": ">", "vergleich": _ref("ma", sitzungen=p.ma_ausstieg)},
                    "max_haltedauer_sitzungen": p.max_haltedauer},
        "stop": {"initial": {"art": "atr", "faktor": p.initialstop_atr, "sitzungen": p.atr}},
        "zeitplan": {"intervall": "taeglich"},
        "profil": cfg.depot.ausfuehrungsprofil,
    }


def lineal(cfg: AktienPilotConfig) -> dict:
    p = cfg.lineal
    gewicht = p.gewichtung
    return {
        "schema": "tr-regel/1", "id": "r-lineal", "version": 1, "name": f"Lineal vorwärts {gewicht}/{100 - gewicht}, {p.zeitraum_tage} Tage",
        "beschreibung": f"Die ersten {p.anzahl} der Lineal-Rangliste Gruppe {p.gruppe}, Gewichtung {gewicht}/{100 - gewicht}, {p.zeitraum_tage} Kalendertage; "
                        "Auswahl vor Beginn fixiert, wöchentlich neu, gleichgewichtet.",
        "herkunft": {"vorlage": p.version},
        "kandidaten": [{"art": "rangliste", "gruppe": p.gruppe, "politik": "native", "gewichte": [gewicht],
                        "fenster": {"von": p.zeitraum_tage, "bis": p.zeitraum_tage}, "platz_bis": p.anzahl}],
        "filter": None,
        "sortierung": {"schluessel": [{"kennzahl": _ref("rang", fenster=p.zeitraum_tage, gewicht=gewicht, gruppe=p.gruppe, politik="native"), "richtung": "auf"}]},
        "auswahl": {"anzahl": p.anzahl},
        "kapital": {"art": "gleich"},
        "kauf": {"ausloeser": "termin"},
        "verkauf": {"herausfallen": {"aktiv": True, "puffer": 0}},
        "stop": {"initial": {"art": "atr", "faktor": 2.0, "sitzungen": 14}},
        "zeitplan": {"intervall": "woechentlich", "wochentag": p.umschichtung_wochentag},
        "profil": cfg.depot.ausfuehrungsprofil,
    }


def platz1_sammler(cfg: AktienPilotConfig, *, leiter: bool = False) -> dict:
    """Vorlage aus Abschnitt 31.6: Platz 1 der Renditeranglisten 1–30 Tage vereinigen, nach 30-Tage-Rendite sortieren."""
    regel = {
        "schema": "tr-regel/1", "id": "r-platz1-leiter" if leiter else "r-platz1", "version": 1,
        "name": "Vorlage: Platz-1-Sammler 1–30 Tage" + (" mit Gewinnleiter" if leiter else ""),
        "beschreibung": "Vereinigt Platz 1 der reinen Renditeranglisten (0/100, Gruppe A) für 1–30 Kalendertage, sortiert den Pool nach der Rendite "
                        "der letzten 30 Kalendertage und prüft zusätzlich eine positive Steigung über 60 Tage; bis zu 5 Aktien, gleich gewichtet, wöchentlich. "
                        "Editierbare Vorlage – keine festgelegte Nutzerstrategie.",
        "herkunft": {"vorlage": "platz1-sammler-1"},
        "kandidaten": [{"art": "rangliste", "gruppe": "A", "politik": "native", "gewichte": [0], "fenster": {"von": 1, "bis": 30}, "platz_bis": 1}],
        "filter": {"kennzahl": _ref("steigung", fenster=60), "op": ">", "wert": 0},
        "sortierung": {"schluessel": [{"kennzahl": _ref("rendite", fenster=30), "richtung": "ab"}]},
        "auswahl": {"anzahl": 5},
        "kapital": {"art": "gleich"},
        "kauf": {"ausloeser": "termin"},
        "verkauf": {"herausfallen": {"aktiv": True, "puffer": 5}},
        "stop": {"initial": {"art": "atr", "faktor": 2.0, "sitzungen": 14}},
        "zeitplan": {"intervall": "woechentlich", "wochentag": 4},
        "profil": cfg.depot.ausfuehrungsprofil,
    }
    if leiter:
        regel["verkauf"]["gewinnmitnahme"] = {"art": "leiter", "basis": "nach_kosten", "bezug": "urspruenglich", "stufen": [
            {"schwelle_pct": 30, "anteil_pct": 25}, {"schwelle_pct": 50, "anteil_pct": 25}, {"schwelle_pct": 100, "anteil_pct": 50}]}
    return regel


def gleichmaessigkeit(cfg: AktienPilotConfig) -> dict:
    """Zweite Vorlage aus Abschnitt 31.6: nur Gleichmäßigkeit (100/0), 30 Tage."""
    return {
        "schema": "tr-regel/1", "id": "r-gleichmaessig", "version": 1, "name": "Vorlage: Gleichmäßigkeit 100/0, 30 Tage",
        "beschreibung": "Die gleichmäßigsten Aufwärtstrends der Lineal-Rangliste 100/0 (Gruppe A, 30 Kalendertage); bis zu 5 Aktien, wöchentlich.",
        "herkunft": {"vorlage": "gleichmaessigkeit-1"},
        "kandidaten": [{"art": "rangliste", "gruppe": "A", "politik": "native", "gewichte": [100], "fenster": {"von": 30, "bis": 30}, "platz_bis": 10}],
        "filter": None,
        "sortierung": {"schluessel": [{"kennzahl": _ref("score", fenster=30, gewicht=100, gruppe="A", politik="native"), "richtung": "ab"}]},
        "auswahl": {"anzahl": 5},
        "kapital": {"art": "gleich"},
        "kauf": {"ausloeser": "termin"},
        "verkauf": {"herausfallen": {"aktiv": True, "puffer": 5}},
        "stop": {"initial": {"art": "atr", "faktor": 2.0, "sitzungen": 14}},
        "zeitplan": {"intervall": "woechentlich", "wochentag": 4},
        "profil": cfg.depot.ausfuehrungsprofil,
    }


def haeufigkeit(cfg: AktienPilotConfig) -> dict:
    """Dritte Vorlage aus Abschnitt 31.6: häufigste Top-10-Nennungen über alle elf Gewichtungen, 1–30 Tage."""
    return {
        "schema": "tr-regel/1", "id": "r-haeufig", "version": 1, "name": "Vorlage: Häufigste Top-10-Nennungen 1–30 Tage",
        "beschreibung": "Aktien mit mindestens 30 Top-10-Nennungen über die elf Gewichtungen und 1–30 Kalendertage (Gruppe A); sortiert nach der Zahl "
                        "der Nennungen, danach der 30-Tage-Rendite; bis zu 5 Aktien, wöchentlich.",
        "herkunft": {"vorlage": "haeufigkeit-1"},
        "kandidaten": [{"art": "haeufigkeit", "k": 10, "fenster": {"von": 1, "bis": 30}, "gewichte": [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100],
                        "gruppe": "A", "politik": "native", "mindestens": 30}],
        "filter": None,
        "sortierung": {"schluessel": [
            {"kennzahl": _ref("haeufigkeit", k=10, fenster={"von": 1, "bis": 30}, gewichte=[0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100], gruppe="A", politik="native"), "richtung": "ab"},
            {"kennzahl": _ref("rendite", fenster=30), "richtung": "ab"},
        ]},
        "auswahl": {"anzahl": 5},
        "kapital": {"art": "gleich"},
        "kauf": {"ausloeser": "termin"},
        "verkauf": {"herausfallen": {"aktiv": True, "puffer": 5}},
        "stop": {"initial": {"art": "atr", "faktor": 2.0, "sitzungen": 14}},
        "zeitplan": {"intervall": "woechentlich", "wochentag": 4},
        "profil": cfg.depot.ausfuehrungsprofil,
    }


def alle(cfg: AktienPilotConfig) -> dict[str, dict]:
    """Alle Vorlagen nach Kurzname."""
    return {
        "lineal": lineal(cfg), "s1": s1(cfg), "s2": s2(cfg), "s3": s3(cfg),
        "platz1": platz1_sammler(cfg), "platz1_leiter": platz1_sammler(cfg, leiter=True),
        "gleichmaessigkeit": gleichmaessigkeit(cfg), "haeufigkeit": haeufigkeit(cfg),
    }
