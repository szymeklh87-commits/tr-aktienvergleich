"""Merkmale je Stichtag aus dem zentralen Katalog (Depot-Optimierer, Aufträge vom 31.10.2026: 18 Abschnitte 3 und 18,
19 Abschnitte 2–4).

Der Optimierer rechnet keine Kennzahl selbst: Jede Kennzahl des Katalogs (`katalog.py`) wird mit denselben Funktionen wie im
Regelwerk für alle Aktien eines Stichtags ausgewertet – im täglichen Lauf mit dem veröffentlichten Rechenstand, im
historischen Test mit dem für diesen Tag nachgerechneten (nur Kurse bis zum Tag). Neue Kennzahlen im Katalog kommen ohne
weitere Arbeit hinzu (mit ihren Standardparametern); ausgeschlossen werden nur Kennzahlen, die nicht zur Aktie gehören, erst
nachträglich bekannt sind oder als Kursniveau zwischen Aktien nicht vergleichbar sind – jeweils mit Grund im Inventar.

Für Kennzahlen mit Zeitfenster prüft der Optimierer zusätzlich einige feste Fenster (``VARIANTEN``), damit kurze und lange
Horizonte passende Merkmale haben. Die Fenster sind vorab festgelegt (nicht auf Ergebnisse optimiert); welche davon etwas
taugen, entscheidet erst die unabhängige Prüfung in ``forschung.py``.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import katalog as kat

VERSION = "merkmale-1"

# Zusätzliche Fenster je Kennzahl (Standardparameter des Katalogs kommen immer dazu). Kalendertage bei Ranglisten-Fenstern
# („fenster“), Sitzungen bei Indikatoren („sitzungen“) – wie im Katalog.
VARIANTEN: dict[str, list[dict]] = {
    "rendite": [{"fenster": f} for f in (5, 10, 20, 60, 90)],
    "r2": [{"fenster": 90}],
    "steigung": [{"fenster": 90}],
    "rauschen": [{"fenster": 90}],
    "max_rueckgang": [{"fenster": 90}],
    "aufwaertstage": [{"fenster": 10}, {"fenster": 90}],
    "haeufigkeit": [{"k": 1}, {"k": 3}, {"k": 1, "fenster": {"von": 1, "bis": 90}}, {"k": 10, "fenster": {"von": 1, "bis": 90}}],
    "trefferanteil": [{"k": 1}],
    "top_stichtage": [{"k": 1}, {"k": 3}],
    "positive_tage": [{"sitzungen": 60}],
    "tagesrendite_mittel": [{"sitzungen": 60}, {"sitzungen": 120}],
    "anstieg_je_schwankung": [{"sitzungen": 20}, {"sitzungen": 120}, {"sitzungen": 250}],
    "groesste_tagesbewegung": [{"sitzungen": 20}],
    "volatilitaet": [{"sitzungen": 20}, {"sitzungen": 250}],
    "abstand_ma": [{"sitzungen": 50}],
    "abstand_hoch": [{"sitzungen": 20}, {"sitzungen": 250}],
    "abstand_tief": [{"sitzungen": 250}],
    "log_r2": [{"sitzungen": 90}],
    "log_steigung_jahr": [{"sitzungen": 90}],
    "volumenfaktor": [{"sitzungen": 5}],
}

# Kennzahlen, die nicht als Prognosemerkmal taugen – mit Grund (steht so im Inventar der App)
AUSGESCHLOSSEN: dict[str, str] = {
    "kurs": "Kursniveau in der Handelswährung – zwischen Aktien nicht vergleichbar (Abstände und Renditen sind Merkmale)",
    "kurs_eur": "Kursniveau in Euro – sagt nichts über die Entwicklung (Abstände und Renditen sind Merkmale)",
    "ma": "gleitender Durchschnitt als Kurs – als Abstand zum Durchschnitt Merkmal",
    "hoch": "Hoch als Kurs – als Abstand zum Hoch Merkmal",
    "atr": "ATR als Kurs – als ATR in Prozent Merkmal",
}

# Bereiche, deren Kennzahlen zu einer Depotposition gehören (nicht zur Aktie)
DEPOTBEREICH = "Depot"


@dataclass(frozen=True)
class Merkmal:
    schluessel: str  # stabile Kennung, z. B. „rendite@fenster=60“
    kennzahl: str  # Katalog-ID
    parameter: tuple  # normalisierte Parameter (sortiert, hashbar)
    name: str  # lesbarer Name, z. B. „Rendite (fenster 60)“
    gruppe: str  # Bereich im Katalog
    besser: str  # hoch | niedrig (Lesart, nicht Gewicht – die Richtung ermittelt die Prüfung)
    historisch: bool  # im historischen Test berechenbar (Katalog: backtest = ja)
    quelle: str
    einheit: str

    @property
    def params(self) -> dict:
        return _thaw(self.parameter)

    def ref(self) -> dict:
        return {"id": self.kennzahl, "parameter": self.params}

    def as_dict(self) -> dict:
        return {"schluessel": self.schluessel, "kennzahl": self.kennzahl, "parameter": self.params, "name": self.name, "gruppe": self.gruppe,
                "besser": self.besser, "historisch": self.historisch, "quelle": self.quelle, "einheit": self.einheit}

    @staticmethod
    def from_dict(d: dict) -> "Merkmal":
        return Merkmal(d["schluessel"], d["kennzahl"], _freeze(d["parameter"]), d["name"], d["gruppe"], d["besser"], bool(d["historisch"]),
                       d["quelle"], d["einheit"])


def _freeze(value):
    if isinstance(value, dict):
        return tuple(sorted((k, _freeze(v)) for k, v in value.items()))
    if isinstance(value, (list, tuple)):
        return ("__liste__", tuple(_freeze(v) for v in value))
    return value


def _thaw(value):
    if isinstance(value, tuple) and value and value[0] == "__liste__":
        return [_thaw(v) for v in value[1]]
    if isinstance(value, tuple):
        return {k: _thaw(v) for k, v in value}
    return value


def _text(value) -> str:
    if isinstance(value, dict) and set(value) == {"von", "bis"}:
        return f"{value['von']}–{value['bis']}"
    if isinstance(value, list):
        return "alle" if len(value) > 3 else "/".join(str(v) for v in value)
    return str(value)


def _schluessel(kid: str, params: dict, standard: dict) -> str:
    """Kennung aus den vom Standard abweichenden Parametern (Standard allein: nur die Katalog-ID)."""
    diff = {k: v for k, v in params.items() if standard.get(k) != v}
    if not diff:
        return kid
    return kid + "@" + ",".join(f"{k}={_text(v)}" for k, v in sorted(diff.items()))


def merkmale(eintraege: dict) -> tuple[list[Merkmal], list[dict]]:
    """Alle Prognosemerkmale (feste Reihenfolge: Katalog, dann Varianten) und das Inventar aller Katalogkennzahlen –
    verwendet oder mit Grund ausgeschlossen (Auftrag 19, Abschnitte 2, 3 und 11: nichts fällt stillschweigend heraus)."""
    out: list[Merkmal] = []
    inventar: list[dict] = []
    seen: set[str] = set()
    for kid, eintrag in eintraege.items():
        k = eintrag.kennzahl
        grund = None
        if k.gruppe == DEPOTBEREICH:
            grund = "gehört zu einer Depotposition, nicht zur Aktie"
        elif k.rueckblickend or k.backtest == "nein":
            grund = "erst nachträglich bekannt – nie für Entscheidungen"
        elif kid in AUSGESCHLOSSEN:
            grund = AUSGESCHLOSSEN[kid]
        elif k.typ == "kategorie":
            grund = ("Kategorie ohne Rangfolge – genutzt für Branchen-, Länder- und Währungsrisiko im Depot" if kid in ("branche", "land", "waehrung", "boerse")
                     else "Zustand als Kategorie – die zugehörige Punktzahl ist Merkmal")
        standard = k.parameter_pruefen({})
        keys: list[str] = []
        if grund is None:
            for raw in [{}] + VARIANTEN.get(kid, []):
                try:
                    params = k.parameter_pruefen(raw)
                except kat.KatalogFehler as exc:  # Variante passt nicht (mehr) zum Katalog: auslassen, im Inventar sichtbar
                    keys.append(f"ungültig: {exc}")
                    continue
                key = _schluessel(kid, params, standard)
                if key in seen:
                    continue
                seen.add(key)
                diff = {p: v for p, v in params.items() if standard.get(p) != v}
                name = k.name if not diff else f"{k.name} ({', '.join(f'{p} {_text(v)}' for p, v in sorted(diff.items()))})"
                out.append(Merkmal(key, kid, _freeze(params), name, k.gruppe, k.besser, k.backtest == "ja", k.quelle, k.einheit))
                keys.append(key)
        inventar.append({
            "kennzahl": kid, "name": k.name, "gruppe": k.gruppe, "typ": k.typ, "einheit": k.einheit, "quelle": k.quelle, "methode": k.methode,
            "historisch": {"ja": "ja", "nur_vorwaerts": "nur vorwärts (keine Historie)", "nein": "nein"}.get(k.backtest, k.backtest),
            "verfuegbar": ("mit dem Abruf der Kennzahlen je Aktie (Abruftag)" if k.backtest == "nur_vorwaerts" else "nach Börsenschluss des Stichtags"),
            "waehrung": ("Handelswährung" if k.einheit == "Kurs" else k.einheit if k.einheit in ("EUR", "USD") else "währungsneutral"),
            "verwendet": grund is None, "grund": grund, "merkmale": [x for x in keys if not x.startswith("ungültig")],
            "ungueltig": [x for x in keys if x.startswith("ungültig")],
        })
    return out, inventar


def matrix(ctx: kat.Kontext, eintraege: dict, liste: list[Merkmal]) -> tuple[np.ndarray, list[str]]:
    """Merkmalsmatrix eines Stichtags: Zeilen = ``ctx.isins``, Spalten = ``liste`` (float32; fehlt ein Wert: NaN).
    Rückgabe auch die Merkmale, die an diesem Tag gar nicht berechenbar waren (z. B. Rangverlauf ohne Archiv)."""
    out = np.full((len(ctx.isins), len(liste)), np.nan, dtype=np.float32)
    fehlend: list[str] = []
    for j, m in enumerate(liste):
        try:
            _kz, _params, werte = kat.werte(ctx, eintraege, m.ref())
        except Exception:  # noqa: BLE001 – eine Kennzahl, die an einem Tag nicht rechenbar ist, fehlt nur an diesem Tag (gezählt)
            fehlend.append(m.schluessel)
            continue
        arr = np.asarray(werte)
        if arr.dtype == bool:
            arr = arr.astype(np.float32)
        try:
            out[:, j] = np.asarray(arr, dtype=np.float64)
        except (TypeError, ValueError):
            fehlend.append(m.schluessel)
    return out, fehlend


def abdeckung(X: np.ndarray) -> np.ndarray:
    """Anteil der Aktien mit Wert je Merkmal (0–1)."""
    if X.size == 0:
        return np.zeros(X.shape[1] if X.ndim == 2 else 0)
    return np.isfinite(X).mean(axis=0)
