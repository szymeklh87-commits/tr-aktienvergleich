"""Regel-Baukasten: eigene Auswahl-, Kauf- und Verkaufsregeln als geprüfte strukturierte Daten (Abschnitte 27.4 und 31).

Eine Regel ist ein JSON-Dokument (Schema ``tr-regel/1``) mit stabiler ID und Versionsnummer. Es gibt **keinen** freien
Programmcode, kein ``eval``, keine URLs oder Pfade: nur Bausteine aus dem Kennzahlenkatalog, Vergleichsoperatoren und
verschachtelte UND/ODER/NICHT-Gruppen. Die Prüfung (``pruefen``) liefert die normalisierte Regel oder Fehler mit Pfad und
deutscher Meldung; der Fingerabdruck (``fingerabdruck``) umfasst alle fachlichen Teile – Name und Beschreibung nicht.

Aufbau::

    {
      "schema": "tr-regel/1", "id": "r-…", "version": 1, "name": "…", "beschreibung": "…",
      "herkunft": {"vorlage": "s1"} | {"kopie_von": "r-…@3"} | {},
      "kandidaten": [Quelle, …],                 # Vereinigung, je ISIN eine wirtschaftliche Position
      "filter": Ausdruck | null,                 # muss „wahr“ sein; „nicht prüfbar“ schließt aus
      "sortierung": {"schluessel": [{"kennzahl": Ref, "richtung": "ab"|"auf"}, …]}
                  | {"score": [{"kennzahl": Ref, "gewicht": 0.6, "richtung": "ab"}, …]},
      "auswahl": {"anzahl": 5, "max_je_branche": null},
      "kapital": {"art": "gleich" | "risiko" | "ziel", "ziele_pct": [40, 30, 30]},
      "kauf": {"ausloeser": "termin" | "neues_signal" | "eintritt_top_n" | "auffuellen"},
      "verkauf": {"herausfallen": {"aktiv": true, "puffer": 3}, "ausstieg": Ausdruck | null,
                  "max_haltedauer_sitzungen": null, "gewinnmitnahme": Gewinnmitnahme | null,
                  "wiedereinstieg": {"art": "neues_signal" | "pause" | "naechste_umschichtung", "pause_sitzungen": 0}},
      "stop": {"initial": {"art": "atr", "faktor": 2.0, "sitzungen": 14} | {"art": "prozent", "wert": 8},
               "trailing": null | {"art": "atr", "faktor": 3.0, "sitzungen": 14} | {"art": "prozent", "wert": 15}},
      "zeitplan": {"intervall": "taeglich" | "woechentlich", "wochentag": 4},
      "profil": "FOLGETAG-SCHLUSS" | "TAGESDATEN",
      "optionen": {"mindesthaltedauer_sitzungen": 0, "mindestorderwert_eur": 0}
    }

Quellen: ``{"art": "rangliste", "gruppe", "politik", "gewichte", "fenster": {"von","bis"}, "platz_bis", "variante":
"heute"|"stichtage", "stichtage": n}`` (Variante A „heutiger Platz je Rückblickfenster“ bzw. B „Platz an vergangenen
Stichtagen“ aus dem Ranglistenarchiv), ``{"art": "haeufigkeit", "k", "fenster", "gewichte", "gruppe", "politik",
"mindestens"}``, ``{"art": "universum"}``, ``{"art": "isins", "isins": [...], "bezeichnung": "Merkliste"}``.

Ausdruck: ``{"und": [...]}``, ``{"oder": [...]}``, ``{"nicht": Ausdruck}`` oder Bedingung
``{"kennzahl": Ref, "op": ">=", "wert": 5}`` bzw. ``{"kennzahl": Ref, "op": ">", "vergleich": Ref}`` bzw.
``{"kennzahl": Ref, "op": "zwischen", "von": a, "bis": b}`` bzw. ``{"kennzahl": Ref, "op": "in", "werte": [...]}``.
Ref = ``{"id": "rendite", "parameter": {"fenster": 30}}``.

Gewinnmitnahme (Abschnitt 31.7): ``{"art": "ganz", "schwelle_pct": 30, "basis": "nach_kosten"|"kurs",
"umfang": {"art": "alles"} | {"art": "anteil", "pct": 50} | {"art": "stueck", "stueck": 10}}`` oder
``{"art": "leiter", "basis": …, "bezug": "urspruenglich"|"verbleibend", "stufen": [{"schwelle_pct": 30, "anteil_pct": 25}, …]}``.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any

from ..util.isin import is_valid_isin
from .katalog import ARCHIV_KENNZAHLEN, Eintrag, KatalogFehler

SCHEMA = "tr-regel/1"
ID_RE = re.compile(r"^r-[a-z0-9][a-z0-9-]{1,38}$")
PROFILE = ("FOLGETAG-SCHLUSS", "TAGESDATEN")

MAX_TIEFE = 6
MAX_BEDINGUNGEN = 40
MAX_QUELLEN = 8
MAX_SORTIERUNG = 6
MAX_ANZAHL = 50
MAX_ISINS = 250
MAX_STUFEN = 6
MAX_TEXT = 500
MAX_GROESSE_BYTE = 64_000

FACHLICHE_TEILE = ("kandidaten", "filter", "sortierung", "auswahl", "kapital", "kauf", "verkauf", "stop", "zeitplan", "profil", "optionen")


@dataclass
class Fehler:
    pfad: str
    text: str

    def as_dict(self) -> dict:
        return {"pfad": self.pfad, "text": self.text}


@dataclass
class Pruefung:
    regel: dict | None
    fehler: list[Fehler] = field(default_factory=list)
    hinweise: list[str] = field(default_factory=list)
    benoetigt: dict = field(default_factory=dict)  # benötigte Daten: Kennzahlen, Historie, Archiv

    @property
    def gueltig(self) -> bool:
        return not self.fehler and self.regel is not None

    def as_dict(self) -> dict:
        return {"gueltig": self.gueltig, "fehler": [f.as_dict() for f in self.fehler], "hinweise": self.hinweise, "benoetigt": self.benoetigt}


class RegelFehler(ValueError):
    def __init__(self, fehler: list[Fehler]):
        super().__init__("; ".join(f"{f.pfad}: {f.text}" for f in fehler))
        self.fehler = fehler


def kanonisch(obj: Any) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def fingerabdruck(regel: dict) -> str:
    """SHA-256 über alle fachlichen Teile der normalisierten Regel (Name/Beschreibung ändern ihn nicht)."""
    return hashlib.sha256(kanonisch({k: regel.get(k) for k in FACHLICHE_TEILE})).hexdigest()


# ------------------------------------------------------------------------------------------------- Prüfung


class _Pruefer:
    def __init__(self, eintraege: dict[str, Eintrag], method):
        self.k = eintraege
        self.method = method
        self.fehler: list[Fehler] = []
        self.hinweise: list[str] = []
        self.bedingungen = 0
        self.kennzahlen: set[str] = set()
        self.nur_vorwaerts: set[str] = set()
        self.archiv = False
        self.archiv_kennzahl = False
        self.max_sitzungen = 0
        self.max_fenster = 0

    def err(self, pfad: str, text: str) -> None:
        self.fehler.append(Fehler(pfad, text))

    # --- Hilfen
    def obj(self, value, pfad: str, required: tuple = (), optional: tuple = ()) -> dict | None:
        if not isinstance(value, dict):
            self.err(pfad, "muss ein Objekt sein")
            return None
        unknown = set(value) - set(required) - set(optional)
        if unknown:
            self.err(pfad, f"unbekannte Felder: {', '.join(sorted(unknown))}")
        for key in required:
            if key not in value:
                self.err(pfad, f"„{key}“ fehlt")
        return value

    def int_in(self, value, pfad: str, lo: int, hi: int) -> int | None:
        if isinstance(value, bool) or not isinstance(value, int):
            self.err(pfad, "muss eine ganze Zahl sein")
            return None
        if not lo <= value <= hi:
            self.err(pfad, f"muss zwischen {lo} und {hi} liegen")
            return None
        return value

    def num_in(self, value, pfad: str, lo: float, hi: float) -> float | None:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            self.err(pfad, "muss eine Zahl sein")
            return None
        v = float(value)
        if not (lo <= v <= hi):
            self.err(pfad, f"muss zwischen {_z(lo)} und {_z(hi)} liegen")
            return None
        return v

    def choice(self, value, pfad: str, allowed: tuple) -> Any:
        if value not in allowed:
            self.err(pfad, f"erlaubt: {', '.join(map(str, allowed))}")
            return None
        return value

    def text(self, value, pfad: str, maximum: int = MAX_TEXT, required: bool = False) -> str | None:
        if value is None and not required:
            return None
        if not isinstance(value, str) or (required and not value.strip()):
            self.err(pfad, "Text fehlt" if required else "muss Text sein")
            return None
        if len(value) > maximum:
            self.err(pfad, f"höchstens {maximum} Zeichen")
            return None
        if any(ord(c) < 32 and c not in "\n\t" for c in value):
            self.err(pfad, "Steuerzeichen sind nicht erlaubt")
            return None
        return value.strip()

    # --- Kennzahlreferenz
    def ref(self, value, pfad: str, rolle: str) -> dict | None:
        v = self.obj(value, pfad, ("id",), ("parameter",))
        if v is None or "id" not in v:
            return None
        e = self.k.get(v["id"])
        if e is None:
            self.err(pfad, f"unbekannte Kennzahl „{v['id']}“")
            return None
        kz = e.kennzahl
        if kz.rueckblickend:
            self.err(pfad, f"„{kz.name}“ ist nur rückblickend bekannt – für Entscheidungen gesperrt (sonst Blick in die Zukunft)")
            return None
        if rolle not in kz.rollen:
            self.err(pfad, f"„{kz.name}“ ist als {_ROLLENTEXT[rolle]} nicht zulässig")
            return None
        try:
            params = kz.parameter_pruefen(v.get("parameter"))
        except KatalogFehler as exc:
            self.err(pfad, str(exc))
            return None
        self.kennzahlen.add(kz.id)
        if kz.backtest != "ja":
            self.nur_vorwaerts.add(kz.id)
        if kz.id in ARCHIV_KENNZAHLEN and not self.archiv_kennzahl:
            self.archiv_kennzahl = True
            self.archiv = True
            self.hinweise.append("Der Rangverlauf nutzt die archivierten Ranglisten früherer Stichtage; bis genug Stichtage archiviert sind, ist die Bedingung „nicht prüfbar“.")
        if "sitzungen" in params:
            self.max_sitzungen = max(self.max_sitzungen, int(params["sitzungen"]))
        if isinstance(params.get("fenster"), int):
            self.max_fenster = max(self.max_fenster, params["fenster"])
        elif isinstance(params.get("fenster"), dict):
            self.max_fenster = max(self.max_fenster, params["fenster"]["bis"])
        out = {"id": kz.id}
        if params:
            out["parameter"] = params
        return out

    # --- Ausdruck
    def ausdruck(self, value, pfad: str, rolle: str, tiefe: int = 1) -> dict | None:
        if tiefe > MAX_TIEFE:
            self.err(pfad, f"höchstens {MAX_TIEFE} verschachtelte Gruppen")
            return None
        if not isinstance(value, dict) or not value:
            self.err(pfad, "muss eine Gruppe oder Bedingung sein")
            return None
        for op in ("und", "oder"):
            if op in value:
                if set(value) != {op}:
                    self.err(pfad, f"„{op}“-Gruppe darf keine weiteren Felder haben")
                    return None
                items = value[op]
                if not isinstance(items, list) or not items:
                    self.err(pfad, f"„{op}“ braucht mindestens eine Bedingung")
                    return None
                out = [self.ausdruck(item, f"{pfad}.{op}[{i}]", rolle, tiefe + 1) for i, item in enumerate(items)]
                if any(o is None for o in out):
                    return None
                return {op: out}
        if "nicht" in value:
            if set(value) != {"nicht"}:
                self.err(pfad, "„nicht“ darf keine weiteren Felder haben")
                return None
            inner = self.ausdruck(value["nicht"], f"{pfad}.nicht", rolle, tiefe + 1)
            return None if inner is None else {"nicht": inner}
        return self.bedingung(value, pfad, rolle)

    def bedingung(self, value, pfad: str, rolle: str) -> dict | None:
        self.bedingungen += 1
        if self.bedingungen > MAX_BEDINGUNGEN:
            if self.bedingungen == MAX_BEDINGUNGEN + 1:
                self.err(pfad, f"höchstens {MAX_BEDINGUNGEN} Bedingungen je Regel")
            return None
        v = self.obj(value, pfad, ("kennzahl", "op"), ("wert", "vergleich", "von", "bis", "werte"))
        if v is None or "kennzahl" not in v or "op" not in v:
            return None
        ref = self.ref(v["kennzahl"], f"{pfad}.kennzahl", rolle)
        if ref is None:
            return None
        kz = self.k[ref["id"]].kennzahl
        op = v["op"]
        if op not in kz.operatoren:
            self.err(f"{pfad}.op", f"„{op}“ passt nicht zu „{kz.name}“ (erlaubt: {', '.join(kz.operatoren)})")
            return None
        out: dict = {"kennzahl": ref, "op": op}
        if op in ("ist_wahr", "ist_falsch"):
            extra = set(v) - {"kennzahl", "op"}
            if extra:
                self.err(pfad, f"„{op}“ braucht keinen Vergleichswert")
            return out
        if op in ("in", "nicht_in"):
            werte = v.get("werte")
            if not isinstance(werte, list) or not werte or len(werte) > 100 or not all(isinstance(w, str) and 0 < len(w) <= 80 for w in werte):
                self.err(f"{pfad}.werte", "Liste mit 1–100 Texten")
                return None
            if kz.werte:
                fremd = sorted(set(werte) - set(kz.werte))
                if fremd:
                    self.err(f"{pfad}.werte", f"unbekannter Wert {', '.join(fremd)} (erlaubt: {', '.join(kz.werte)})")
                    return None
            out["werte"] = sorted(set(werte))
            return out
        if op == "zwischen":
            lo = self.num_in(v.get("von"), f"{pfad}.von", -1e12, 1e12)
            hi = self.num_in(v.get("bis"), f"{pfad}.bis", -1e12, 1e12)
            if lo is None or hi is None:
                return None
            if lo > hi:
                self.err(pfad, "„von“ muss kleiner oder gleich „bis“ sein")
                return None
            out.update(von=lo, bis=hi)
            return out
        if op in ("neu_eingetreten", "verlassen"):
            platz = self.int_in(v.get("wert"), f"{pfad}.wert", 1, 500)
            if platz is None:
                return None
            out["wert"] = platz
            self.archiv = True
            self.hinweise.append(f"„{_OPTEXT[op]}“ vergleicht mit der vorigen Entscheidung – ohne sie ist die Bedingung „nicht prüfbar“.")
            return out
        if "vergleich" in v:
            if "wert" in v:
                self.err(pfad, "entweder „wert“ oder „vergleich“")
                return None
            other = self.ref(v["vergleich"], f"{pfad}.vergleich", rolle)
            if other is None:
                return None
            okz = self.k[other["id"]].kennzahl
            if not kz.einheit_vergleich or kz.einheit_vergleich != okz.einheit_vergleich:
                self.err(pfad, f"„{kz.name}“ ({kz.einheit or 'ohne Einheit'}) ist mit „{okz.name}“ ({okz.einheit or 'ohne Einheit'}) nicht vergleichbar")
                return None
            if op.startswith("gekreuzt") and not (kz.reihe and okz.reihe):
                self.err(pfad, "„gekreuzt“ braucht zwei Kursreihen mit Vortageswert (z. B. Schlusskurs und Durchschnitt)")
                return None
            out["vergleich"] = other
            return out
        if op.startswith("gekreuzt"):
            if not kz.reihe:
                self.err(pfad, "„gekreuzt“ braucht eine Kursreihe mit Vortageswert")
                return None
        wert = self.num_in(v.get("wert"), f"{pfad}.wert", -1e12, 1e12)
        if wert is None:
            return None
        if kz.typ == "rang" and (wert < 1 or wert != int(wert)):
            self.err(f"{pfad}.wert", "Rang ist eine ganze Zahl ab 1")
            return None
        out["wert"] = wert
        return out

    # --- Quellen
    def quelle(self, value, pfad: str) -> dict | None:
        if not isinstance(value, dict) or "art" not in value:
            self.err(pfad, "Quelle braucht „art“")
            return None
        art = value["art"]
        P = self.k["rang"].kennzahl
        if art == "rangliste":
            v = self.obj(value, pfad, ("art", "gewichte", "fenster", "platz_bis"), ("gruppe", "politik", "variante", "stichtage"))
            if v is None:
                return None
            try:
                gewichte = P.param("gewicht")
                weights = sorted({int(w) for w in v.get("gewichte") or []})
                if not weights or any(w not in gewichte.werte for w in weights):
                    raise KatalogFehler(f"Gewichtungen aus {', '.join(map(str, gewichte.werte))}")
                fenster = self.k["haeufigkeit"].kennzahl.param("fenster").pruefen(v.get("fenster"))
                gruppe = P.param("gruppe").pruefen(v.get("gruppe", "A"))
                politik = P.param("politik").pruefen(v.get("politik", "native"))
            except KatalogFehler as exc:
                self.err(pfad, str(exc))
                return None
            platz = self.int_in(v.get("platz_bis"), f"{pfad}.platz_bis", 1, 100)
            variante = self.choice(v.get("variante", "heute"), f"{pfad}.variante", ("heute", "stichtage"))
            if platz is None or variante is None:
                return None
            out = {"art": art, "gruppe": gruppe, "politik": politik, "gewichte": weights, "fenster": fenster, "platz_bis": platz, "variante": variante}
            if variante == "stichtage":
                n = self.int_in(v.get("stichtage"), f"{pfad}.stichtage", 1, 60)
                if n is None:
                    return None
                out["stichtage"] = n
                self.archiv = True
                self.hinweise.append("Variante B („Platz an vergangenen Stichtagen“) nutzt die archivierten damaligen Ranglisten; fehlende Stichtage bleiben fehlend.")
            self.max_fenster = max(self.max_fenster, fenster["bis"])
            return out
        if art == "haeufigkeit":
            v = self.obj(value, pfad, ("art", "k", "fenster", "gewichte", "mindestens"), ("gruppe", "politik"))
            if v is None:
                return None
            kz = self.k["haeufigkeit"].kennzahl
            try:
                params = kz.parameter_pruefen({key: v[key] for key in ("k", "fenster", "gewichte", "gruppe", "politik") if key in v})
            except KatalogFehler as exc:
                self.err(pfad, str(exc))
                return None
            cells = (params["fenster"]["bis"] - params["fenster"]["von"] + 1) * len(params["gewichte"])
            mind = self.int_in(v.get("mindestens"), f"{pfad}.mindestens", 1, cells)
            if mind is None:
                return None
            self.max_fenster = max(self.max_fenster, params["fenster"]["bis"])
            return {"art": art, **params, "mindestens": mind}
        if art == "universum":
            v = self.obj(value, pfad, ("art",), ())
            return None if v is None else {"art": "universum"}
        if art == "isins":
            v = self.obj(value, pfad, ("art", "isins"), ("bezeichnung",))
            if v is None:
                return None
            isins = v.get("isins")
            if not isinstance(isins, list) or not isins or len(isins) > MAX_ISINS:
                self.err(f"{pfad}.isins", f"Liste mit 1–{MAX_ISINS} ISINs")
                return None
            bad = [i for i in isins if not (isinstance(i, str) and is_valid_isin(i))]
            if bad:
                self.err(f"{pfad}.isins", f"ungültige ISIN: {', '.join(map(str, bad[:5]))}")
                return None
            label = self.text(v.get("bezeichnung"), f"{pfad}.bezeichnung", 60)
            return {"art": art, "isins": sorted(set(isins)), "bezeichnung": label or "eigene Auswahl"}
        self.err(pfad, f"unbekannte Quelle „{art}“ (rangliste, haeufigkeit, universum, isins)")
        return None

    # --- Gewinnmitnahme
    def gewinnmitnahme(self, value, pfad: str) -> dict | None:
        if value is None:
            return None
        if not isinstance(value, dict) or "art" not in value:
            self.err(pfad, "Gewinnmitnahme braucht „art“ (ganz oder leiter)")
            return None
        art = value["art"]
        if art == "ganz":
            v = self.obj(value, pfad, ("art", "schwelle_pct"), ("basis", "umfang"))
            if v is None:
                return None
            schwelle = self.num_in(v.get("schwelle_pct"), f"{pfad}.schwelle_pct", 0.1, 10_000)
            basis = self.choice(v.get("basis", "nach_kosten"), f"{pfad}.basis", ("nach_kosten", "kurs"))
            umfang_raw = v.get("umfang", {"art": "alles"})
            umfang = None
            if isinstance(umfang_raw, dict) and umfang_raw.get("art") == "alles" and set(umfang_raw) == {"art"}:
                umfang = {"art": "alles"}
            elif isinstance(umfang_raw, dict) and umfang_raw.get("art") == "anteil" and set(umfang_raw) == {"art", "pct"}:
                pct = self.num_in(umfang_raw.get("pct"), f"{pfad}.umfang.pct", 1, 100)
                umfang = None if pct is None else {"art": "anteil", "pct": pct}
            elif isinstance(umfang_raw, dict) and umfang_raw.get("art") == "stueck" and set(umfang_raw) == {"art", "stueck"}:
                st = self.int_in(umfang_raw.get("stueck"), f"{pfad}.umfang.stueck", 1, 10_000_000)
                umfang = None if st is None else {"art": "stueck", "stueck": st}
            else:
                self.err(f"{pfad}.umfang", "alles, anteil (pct) oder stueck")
            if schwelle is None or basis is None or umfang is None:
                return None
            return {"art": "ganz", "schwelle_pct": schwelle, "basis": basis, "umfang": umfang}
        if art == "leiter":
            v = self.obj(value, pfad, ("art", "stufen"), ("basis", "bezug"))
            if v is None:
                return None
            basis = self.choice(v.get("basis", "nach_kosten"), f"{pfad}.basis", ("nach_kosten", "kurs"))
            bezug = self.choice(v.get("bezug", "urspruenglich"), f"{pfad}.bezug", ("urspruenglich", "verbleibend"))
            stufen_raw = v.get("stufen")
            if not isinstance(stufen_raw, list) or not 1 <= len(stufen_raw) <= MAX_STUFEN:
                self.err(f"{pfad}.stufen", f"1–{MAX_STUFEN} Stufen")
                return None
            stufen = []
            for i, s in enumerate(stufen_raw):
                sv = self.obj(s, f"{pfad}.stufen[{i}]", ("schwelle_pct", "anteil_pct"), ())
                if sv is None:
                    return None
                sch = self.num_in(sv.get("schwelle_pct"), f"{pfad}.stufen[{i}].schwelle_pct", 0.1, 10_000)
                ant = self.num_in(sv.get("anteil_pct"), f"{pfad}.stufen[{i}].anteil_pct", 1, 100)
                if sch is None or ant is None:
                    return None
                stufen.append({"schwelle_pct": sch, "anteil_pct": ant})
            schwellen = [s["schwelle_pct"] for s in stufen]
            if schwellen != sorted(schwellen) or len(set(schwellen)) != len(schwellen):
                self.err(f"{pfad}.stufen", "Schwellen müssen aufsteigend und verschieden sein")
                return None
            if bezug == "urspruenglich" and sum(s["anteil_pct"] for s in stufen) > 100 + 1e-9:
                self.err(f"{pfad}.stufen", "Summe der Anteile über 100 % der ursprünglichen Stückzahl")
                return None
            if basis is None or bezug is None:
                return None
            return {"art": "leiter", "basis": basis, "bezug": bezug, "stufen": stufen}
        self.err(pfad, "„art“: ganz oder leiter")
        return None

    def stop_art(self, value, pfad: str, required: bool) -> dict | None:
        if value is None:
            if required:
                self.err(pfad, "Initialstop ist Pflicht – der zentrale Risiko-Manager kauft ohne Stop nicht")
            return None
        if not isinstance(value, dict):
            self.err(pfad, "muss ein Objekt sein")
            return None
        if value.get("art") == "atr":
            v = self.obj(value, pfad, ("art", "faktor"), ("sitzungen",))
            if v is None:
                return None
            f = self.num_in(v.get("faktor"), f"{pfad}.faktor", 0.5, 10)
            n = self.int_in(v.get("sitzungen", 14), f"{pfad}.sitzungen", 5, 50)
            if f is None or n is None:
                return None
            self.max_sitzungen = max(self.max_sitzungen, n + 1)
            return {"art": "atr", "faktor": f, "sitzungen": n}
        if value.get("art") == "prozent":
            v = self.obj(value, pfad, ("art", "wert"), ())
            if v is None:
                return None
            w = self.num_in(v.get("wert"), f"{pfad}.wert", 1, 50)
            return None if w is None else {"art": "prozent", "wert": w}
        self.err(pfad, "„art“: atr oder prozent")
        return None


_ROLLENTEXT = {"filter": "Filter", "sortierung": "Sortierung", "kapital": "Kapitalgewicht", "ausstieg": "Ausstiegsbedingung"}
_OPTEXT = {"neu_eingetreten": "neu eingetreten", "verlassen": "verlassen"}


def _z(x: float) -> str:
    return str(int(x)) if float(x).is_integer() else str(x).replace(".", ",")


def pruefen(regel: Any, eintraege: dict[str, Eintrag], method) -> Pruefung:
    """Regel prüfen und normalisieren (Standardwerte eingesetzt, Listen sortiert)."""
    pr = _Pruefer(eintraege, method)
    try:
        size = len(kanonisch(regel))
    except (TypeError, ValueError):
        return Pruefung(None, [Fehler("", "Regel ist kein gültiges JSON-Objekt")])
    if size > MAX_GROESSE_BYTE:
        return Pruefung(None, [Fehler("", f"Regel größer als {MAX_GROESSE_BYTE} Bytes")])
    v = pr.obj(regel, "", ("schema", "id", "version", "name", "kandidaten", "sortierung", "auswahl", "stop"),
               ("beschreibung", "herkunft", "filter", "kapital", "kauf", "verkauf", "zeitplan", "profil", "optionen"))
    if v is None:
        return Pruefung(None, pr.fehler)
    if v.get("schema") != SCHEMA:
        pr.err("schema", f"muss „{SCHEMA}“ sein")
    rid = v.get("id")
    if not (isinstance(rid, str) and ID_RE.match(rid)):
        pr.err("id", "Regel-ID: „r-“ und 2–39 Kleinbuchstaben, Ziffern oder Bindestriche")
    version = pr.int_in(v.get("version"), "version", 1, 1_000_000)
    name = pr.text(v.get("name"), "name", 80, required=True)
    beschreibung = pr.text(v.get("beschreibung"), "beschreibung")
    herkunft_raw = v.get("herkunft") or {}
    herkunft = {}
    if not isinstance(herkunft_raw, dict) or set(herkunft_raw) - {"vorlage", "kopie_von"}:
        pr.err("herkunft", "nur „vorlage“ oder „kopie_von“")
    else:
        for key in ("vorlage", "kopie_von"):
            if key in herkunft_raw:
                t = pr.text(herkunft_raw[key], f"herkunft.{key}", 60)
                if t:
                    herkunft[key] = t

    quellen_raw = v.get("kandidaten")
    quellen = []
    if not isinstance(quellen_raw, list) or not 1 <= len(quellen_raw) <= MAX_QUELLEN:
        pr.err("kandidaten", f"1–{MAX_QUELLEN} Kandidatenquellen")
    else:
        for i, q in enumerate(quellen_raw):
            out = pr.quelle(q, f"kandidaten[{i}]")
            if out is not None:
                quellen.append(out)

    filt = None
    if v.get("filter") is not None:
        filt = pr.ausdruck(v["filter"], "filter", "filter")

    sortierung = None
    sv = v.get("sortierung")
    if isinstance(sv, dict) and set(sv) == {"schluessel"}:
        keys = sv["schluessel"]
        if not isinstance(keys, list) or not 1 <= len(keys) <= MAX_SORTIERUNG:
            pr.err("sortierung.schluessel", f"1–{MAX_SORTIERUNG} Sortierschlüssel")
        else:
            out = []
            for i, key in enumerate(keys):
                kv = pr.obj(key, f"sortierung.schluessel[{i}]", ("kennzahl",), ("richtung",))
                if kv is None or "kennzahl" not in kv:
                    continue
                ref = pr.ref(kv["kennzahl"], f"sortierung.schluessel[{i}].kennzahl", "sortierung")
                richtung = pr.choice(kv.get("richtung") or _richtung(eintraege, ref), f"sortierung.schluessel[{i}].richtung", ("ab", "auf"))
                if ref is not None and richtung is not None:
                    out.append({"kennzahl": ref, "richtung": richtung})
            sortierung = {"schluessel": out}
    elif isinstance(sv, dict) and "score" in sv and set(sv) <= {"score", "normierung"} and sv.get("normierung", "perzentil") == "perzentil":
        # „normierung“ steht in der gespeicherten (geprüften) Fassung – eine erneute Prüfung ergibt dieselbe Regel
        parts = sv["score"]
        if not isinstance(parts, list) or not 1 <= len(parts) <= MAX_SORTIERUNG:
            pr.err("sortierung.score", f"1–{MAX_SORTIERUNG} Bestandteile")
        else:
            out = []
            for i, part in enumerate(parts):
                pv = pr.obj(part, f"sortierung.score[{i}]", ("kennzahl", "gewicht"), ("richtung",))
                if pv is None or "kennzahl" not in pv:
                    continue
                ref = pr.ref(pv["kennzahl"], f"sortierung.score[{i}].kennzahl", "sortierung")
                g = pr.num_in(pv.get("gewicht"), f"sortierung.score[{i}].gewicht", 0.01, 100)
                richtung = pr.choice(pv.get("richtung") or _richtung(eintraege, ref), f"sortierung.score[{i}].richtung", ("ab", "auf"))
                if ref is not None and g is not None and richtung is not None:
                    out.append({"kennzahl": ref, "gewicht": g, "richtung": richtung})
            total = sum(p["gewicht"] for p in out)
            if out and total <= 0:
                pr.err("sortierung.score", "Gewichte müssen positiv sein")
            sortierung = {"score": out, "normierung": "perzentil"}
            pr.hinweise.append("Score: jede Kennzahl wird innerhalb der gefilterten Kandidaten in Perzentile (0–100) umgerechnet und gewichtet addiert – keine Addition von Prozentwerten, R² und Nennungszahlen.")
    else:
        pr.err("sortierung", "„schluessel“ (Reihenfolge) oder „score“ (gewichtete Perzentile)")

    auswahl = None
    av = pr.obj(v.get("auswahl"), "auswahl", ("anzahl",), ("max_je_branche",))
    if av is not None:
        n = pr.int_in(av.get("anzahl"), "auswahl.anzahl", 1, MAX_ANZAHL)
        mjb = av.get("max_je_branche")
        if mjb is not None:
            mjb = pr.int_in(mjb, "auswahl.max_je_branche", 1, MAX_ANZAHL)
        if n is not None:
            auswahl = {"anzahl": n, "max_je_branche": mjb}

    kapital = {"art": "gleich"}
    kv = v.get("kapital")
    if kv is not None:
        kv = pr.obj(kv, "kapital", ("art",), ("ziele_pct",))
        if kv is not None:
            art = pr.choice(kv.get("art"), "kapital.art", ("gleich", "risiko", "ziel"))
            if art == "ziel":
                ziele = kv.get("ziele_pct")
                if not isinstance(ziele, list) or not ziele or any(isinstance(z, bool) or not isinstance(z, (int, float)) or z <= 0 for z in ziele):
                    pr.err("kapital.ziele_pct", "Liste positiver Prozentwerte je Auswahlplatz")
                elif abs(sum(ziele) - 100) > 0.01:
                    pr.err("kapital.ziele_pct", "Zielgewichte müssen zusammen 100 % ergeben")
                elif auswahl and len(ziele) != auswahl["anzahl"]:
                    pr.err("kapital.ziele_pct", f"genau {auswahl['anzahl']} Zielgewichte (eines je Auswahlplatz)")
                else:
                    kapital = {"art": "ziel", "ziele_pct": [float(z) for z in ziele]}
            elif art is not None:
                if "ziele_pct" in kv:
                    pr.err("kapital.ziele_pct", "nur bei „ziel“")
                kapital = {"art": art}
                if art == "risiko":
                    pr.hinweise.append("Risikogewichtung: Kapital umgekehrt proportional zur ATR in % (14 Sitzungen) – die zentralen Grenzen begrenzen jede Stückzahl.")

    kauf = {"ausloeser": "termin"}
    kv = v.get("kauf")
    if kv is not None:
        kv = pr.obj(kv, "kauf", ("ausloeser",), ())
        if kv is not None:
            a = pr.choice(kv.get("ausloeser"), "kauf.ausloeser", ("termin", "neues_signal", "eintritt_top_n", "auffuellen"))
            if a:
                kauf = {"ausloeser": a}

    verkauf = {"herausfallen": {"aktiv": True, "puffer": 0}, "ausstieg": None, "max_haltedauer_sitzungen": None,
               "gewinnmitnahme": None, "wiedereinstieg": {"art": "neues_signal", "pause_sitzungen": 0}}
    vv = v.get("verkauf")
    if vv is not None:
        vv = pr.obj(vv, "verkauf", (), ("herausfallen", "ausstieg", "max_haltedauer_sitzungen", "gewinnmitnahme", "wiedereinstieg"))
        if vv is not None:
            hf = vv.get("herausfallen")
            if hf is not None:
                hfv = pr.obj(hf, "verkauf.herausfallen", ("aktiv",), ("puffer",))
                if hfv is not None:
                    aktiv = hfv.get("aktiv")
                    if not isinstance(aktiv, bool):
                        pr.err("verkauf.herausfallen.aktiv", "wahr oder falsch")
                    puffer = pr.int_in(hfv.get("puffer", 0), "verkauf.herausfallen.puffer", 0, 50)
                    if isinstance(aktiv, bool) and puffer is not None:
                        verkauf["herausfallen"] = {"aktiv": aktiv, "puffer": puffer}
            if vv.get("ausstieg") is not None:
                verkauf["ausstieg"] = pr.ausdruck(vv["ausstieg"], "verkauf.ausstieg", "ausstieg")
            if vv.get("max_haltedauer_sitzungen") is not None:
                verkauf["max_haltedauer_sitzungen"] = pr.int_in(vv["max_haltedauer_sitzungen"], "verkauf.max_haltedauer_sitzungen", 1, 2000)
            verkauf["gewinnmitnahme"] = pr.gewinnmitnahme(vv.get("gewinnmitnahme"), "verkauf.gewinnmitnahme")
            we = vv.get("wiedereinstieg")
            if we is not None:
                wev = pr.obj(we, "verkauf.wiedereinstieg", ("art",), ("pause_sitzungen",))
                if wev is not None:
                    art = pr.choice(wev.get("art"), "verkauf.wiedereinstieg.art", ("neues_signal", "pause", "naechste_umschichtung"))
                    pause = pr.int_in(wev.get("pause_sitzungen", 0), "verkauf.wiedereinstieg.pause_sitzungen", 0, 250)
                    if art == "pause" and pause == 0:
                        pr.err("verkauf.wiedereinstieg.pause_sitzungen", "bei „pause“ mindestens 1 Sitzung")
                    if art and pause is not None:
                        verkauf["wiedereinstieg"] = {"art": art, "pause_sitzungen": pause}
        gm = verkauf.get("gewinnmitnahme")
        if gm and gm["art"] == "ganz" and gm["umfang"]["art"] == "alles":
            pr.hinweise.append(f"Verkauf der ganzen Position bei +{_z(gm['schwelle_pct'])} %: höhere Schwellen sind für diese Position danach nicht mehr erreichbar. Für Teilverkäufe „gestaffelt“ (Leiter) wählen.")

    stop = None
    if v.get("stop") is None:
        pr.err("stop", "Initialstop ist Pflicht – der zentrale Risiko-Manager kauft ohne Stop nicht")
    stv = pr.obj(v.get("stop"), "stop", ("initial",), ("trailing",)) if v.get("stop") is not None else None
    if stv is not None:
        initial = pr.stop_art(stv.get("initial"), "stop.initial", True)
        trailing = pr.stop_art(stv.get("trailing"), "stop.trailing", False) if stv.get("trailing") is not None else None
        if initial is not None:
            stop = {"initial": initial, "trailing": trailing}

    zeitplan = {"intervall": "woechentlich", "wochentag": 4}
    zv = v.get("zeitplan")
    if zv is not None:
        zv = pr.obj(zv, "zeitplan", ("intervall",), ("wochentag",))
        if zv is not None:
            iv = pr.choice(zv.get("intervall"), "zeitplan.intervall", ("taeglich", "woechentlich"))
            if iv == "woechentlich":
                wt = pr.int_in(zv.get("wochentag", 4), "zeitplan.wochentag", 0, 4)
                if wt is not None:
                    zeitplan = {"intervall": iv, "wochentag": wt}
            elif iv == "taeglich":
                if "wochentag" in zv:
                    pr.err("zeitplan.wochentag", "nur bei wöchentlich")
                zeitplan = {"intervall": iv}

    profil = v.get("profil", "FOLGETAG-SCHLUSS")
    if profil == "VERZOEGERTER-EINSTIEG":
        pr.err("profil", "15 Minuten nach Eröffnung ist mit Tageskerzen nicht simulierbar – FOLGETAG-SCHLUSS oder TAGESDATEN wählen")
    elif profil not in PROFILE:
        pr.err("profil", f"erlaubt: {', '.join(PROFILE)}")

    optionen = {"mindesthaltedauer_sitzungen": 0, "mindestorderwert_eur": 0.0}
    ov = v.get("optionen")
    if ov is not None:
        ov = pr.obj(ov, "optionen", (), ("mindesthaltedauer_sitzungen", "mindestorderwert_eur"))
        if ov is not None:
            mh = pr.int_in(ov.get("mindesthaltedauer_sitzungen", 0), "optionen.mindesthaltedauer_sitzungen", 0, 250)
            mo = pr.num_in(ov.get("mindestorderwert_eur", 0), "optionen.mindestorderwert_eur", 0, 100_000)
            if mh is not None and mo is not None:
                optionen = {"mindesthaltedauer_sitzungen": mh, "mindestorderwert_eur": mo}

    if pr.fehler:
        return Pruefung(None, pr.fehler, pr.hinweise)
    if any(q["art"] == "universum" for q in quellen) and filt is None:
        pr.hinweise.append("Ohne Filter ist das gesamte TR-Universum Kandidat – nur die Sortierung entscheidet.")
    if pr.nur_vorwaerts:
        names = ", ".join(sorted(eintraege[i].kennzahl.name for i in pr.nur_vorwaerts))
        pr.hinweise.append(f"Ohne historische Zeitreihe – nur im Vorwärts-PAPER prüfbar, nicht im historischen Test: {names}.")
    normal = {
        "schema": SCHEMA, "id": rid, "version": version, "name": name, "beschreibung": beschreibung, "herkunft": herkunft,
        "kandidaten": quellen, "filter": filt, "sortierung": sortierung, "auswahl": auswahl, "kapital": kapital, "kauf": kauf,
        "verkauf": verkauf, "stop": stop, "zeitplan": zeitplan, "profil": profil, "optionen": optionen,
    }
    benoetigt = {
        "kennzahlen": sorted(pr.kennzahlen),
        "nur_vorwaerts": sorted(pr.nur_vorwaerts),
        "ranglistenarchiv": pr.archiv,
        "sitzungen": pr.max_sitzungen,
        "fenster_kalendertage": pr.max_fenster,
        "bedingungen": pr.bedingungen,
    }
    return Pruefung(normal, [], pr.hinweise, benoetigt)


def _richtung(eintraege: dict[str, Eintrag], ref: dict | None) -> str:
    if ref is None:
        return "ab"
    return "auf" if eintraege[ref["id"]].kennzahl.besser == "niedrig" else "ab"


def pruefen_oder_fehler(regel: Any, eintraege: dict[str, Eintrag], method) -> dict:
    result = pruefen(regel, eintraege, method)
    if not result.gueltig:
        raise RegelFehler(result.fehler)
    return result.regel  # type: ignore[return-value]


def neue_version(alt: dict, neu: dict) -> dict:
    """Neue Version derselben Regel: gleiche ID, Version + 1 – nur wenn sich fachlich etwas geändert hat."""
    if alt["id"] != neu["id"]:
        raise ValueError("andere Regel-ID – das ist eine Kopie, keine neue Version")
    if fingerabdruck(alt) == fingerabdruck(neu) and alt.get("name") == neu.get("name") and alt.get("beschreibung") == neu.get("beschreibung"):
        return alt
    out = dict(neu)
    out["version"] = int(alt["version"]) + 1
    return out


def kopieren(regel: dict, neue_id: str, name: str | None = None) -> dict:
    """„Regel kopieren“: neue ID, Version 1, Herkunft sichtbar (Abschnitt 32.3)."""
    out = json.loads(json.dumps(regel))
    out["id"] = neue_id
    out["version"] = 1
    out["name"] = name or f"Kopie von {regel['name']}"[:80]
    out["herkunft"] = {"kopie_von": f"{regel['id']}@{regel['version']}"}
    return out
