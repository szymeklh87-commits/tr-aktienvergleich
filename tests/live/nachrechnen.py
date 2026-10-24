"""Unabhängige Nachrechnung veröffentlichter Datenstände mit echten Daten (ab 1.13).

Simons Auftrag vom 14.10.2026: „Wird alles richtig berechnet? Kontrolliere.“ und „Prüfe, ob die App sinnvoll rechnet.“

Das Skript liest einen Datenstand so, wie ihn die App bekommt – die verschlüsselten Dateien aus dem Release
„datenstand“ (oder aus einem lokalen Website-Ordner) –, entschlüsselt sie mit ``DATA_PASSPHRASE`` und rechnet aus den
veröffentlichten Kursreihen nach, was die App anzeigt. Es benutzt dafür **nicht** den Rechenkern
(``traktien.analytics``), sondern eine eigene, kurze Rechnung nach der Methodenbeschreibung (docs/03_Methodik.md):

1. **Dateien:** Prüfsumme (SHA-256) jeder entschlüsselten Datei gegen das Manifest.
2. **Zeiträume 1–90 Tage je Aktie:** Startsitzung (letzte Sitzung am oder vor „Ende − h“, höchstens 7 Tage davor),
   Zahl der Kurse und Sitzungen, Start- und Endkurs, Kursrendite (bitgleich) und R² (eigene Formel, Korrelation²).
   Zulassung zur Rendite-Rangliste (Mindestkurse, Sitzungsabdeckung, Volumenregeln) und Trend-Status.
3. **Ranglisten:** alle elf Gewichtungen in Gruppe A und B – Perzentile aus Durchschnittsrängen, Score, Reihenfolge
   (Score, dann Rendite, dann ISIN), reine Rendite-Rangliste, Gleichstände.
4. **Ø Tagesumsatz** (Gruppe B): 20 Sitzungen, Kurs × Volumen, Umrechnung mit den veröffentlichten EZB-Kursen.
5. **Häufigkeit:** Platz 1, Top 3, Top 10, Verfügbarkeit, Zeiträume, Gewichtungen je Aktie.
6. **Zwischenstand:** Aktien ohne Kurs von heute (ab 1.13 mit dem letzten Schlusskurs) haben Zahl für Zahl dieselben
   Werte wie im Stand mit Schlusskursen.
7. **Vergleich mit ChatGPT** (``--vergleich``): Anzahl der Aktien je Rangliste und Prüfwerte der ersten Plätze.
8. **Originalstände** (ab 1.18.1, ``--stand <ID> --nachweis``): ein bestimmter Stand aus dem Release, dazu sein
   Prüfnachweis ``evidence-<ID>.tra`` aus demselben Lauf (Eingangsreihen und alle damals berechneten Kennzahlen). Geprüft
   wird, dass die veröffentlichten Kurse die damaligen Eingangsreihen und die veröffentlichten Renditen und R² die damals
   gerechneten sind – mit den Daten von damals, nicht mit nachträglich beschafften.

Ausgegeben werden nur Zählwerte – keine Kurse, Renditen, Namen oder ISINs: Das Protokoll eines öffentlichen
Repositorys ist öffentlich, der Datenstand ist absichtlich verschlüsselt. Die Passphrase wird nie ausgegeben.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import math
import os
import re
import sys
import tarfile
import tempfile
import time
import urllib.request
from collections import Counter
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from traktien.util import crypto  # nur Entschlüsseln – kein Rechenkern

WEIGHTS = (0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100)
V_STATUS = {15, 16, 17, 18}  # Kursrendite veröffentlicht (Menge V)
U_STATUS = 18  # Trend bewertbar (Menge U)
APP_URL = os.environ.get("TR_APP_URL", "https://szymeklh87-commits.github.io/tr-aktienvergleich/")
R2_TOLERANCE = 1e-9
OWN_END_MAX_DAYS = 12  # letzter Schlusskurs höchstens eine verpasste Sitzung zurück – auch über lange Feiertage
USD_TOLERANCE = 2e-7  # Ø Tagesumsatz wird mit 8 gültigen Stellen veröffentlicht

# Bekannte Fehler früherer Versionen (ab 1.17; Simons Auftrag vom 24.10.2026: „Prüfe historische Datenstände nach ihrer
# dokumentierten Berechnungsversion. Unterscheide dabei nachvollziehbar zwischen damaligem Verhalten und fachlich
# korrekten Ergebnissen. Bekannte Rechenfehler dürfen nicht allein durch passende Vergleichswerte als korrekt gelten.“)
# Ein Eintrag greift nur bei Ständen, die mit einer Software vor ``behoben_in`` gerechnet wurden, und nur, wenn seine
# genaue Bedingung erfüllt ist (siehe die jeweilige Prüfung). Solche Fälle zählen nicht als Rechenabweichung – sie
# bestätigen das damalige Verhalten –, werden aber ausdrücklich als fachlich falsch ausgewiesen. Alles andere bleibt
# eine Abweichung.
KNOWN_ISSUES = {
    "reihe_vorhanden": {
        "behoben_in": (1, 13, 0),
        "fehler": "Kennzeichen „Kursreihe vorhanden“ bei einer Aktie ohne einen einzigen gültigen Kurs – die App bot für sie eine Kursgrafik an, deren Datei fehlte",
        "bedingung": "Aktie ohne gültigen Kurs: in keinem der 90 Zeiträume mit Rendite, kein letzter Schlusskurs",
        "wirkung": "nur Anzeige; keine Rendite, kein Rang und keine Rangliste betroffen",
        "korrektur": "Commit 3e055ec vom 14.10.2026 (Version 1.13.0), Unit-Test",
    },
    "gleichstand_rundung": {
        "behoben_in": (1, 18, 0),
        "fehler": "Bei gemischter Gewichtung entschied bei rechnerisch gleichem Score die letzte Binärstelle des Gleitkomma-Scores über die Reihenfolge statt der höheren Kursrendite; solche Gleichstände waren nicht gekennzeichnet",
        "bedingung": "Rangliste (10/90 bis 90/10) mit rechnerisch gleichen Scores, deren Gleitkommawerte sich unterscheiden; Stand mit ranking-11w-v2 oder älter",
        "wirkung": "nur die Reihenfolge innerhalb rechnerisch gleicher Scores und deren Gleichstandskennzeichen; Renditen, R², Perzentile und Scores unverändert",
        "korrektur": "ranking-11w-v3 in tr-methode-1.10.0 (Version 1.18.0) vom 24.10.2026, Referenztests tests/unit/test_referenz_gleichstand.py",
    },
}


# Beabsichtigte Methodenänderungen nach einem Stand (ab 1.18; Simons Auftrag vom 24.10.2026, 19:07 Uhr: „Unterscheide beim
# Stand vom 13.10. zwischen ‚damalige Berechnung reproduziert‘ und ‚fachlich korrekt‘ … Beabsichtigte Methodenänderungen
# getrennt ausweisen.“) – das sind keine Fehler: Ein älterer Stand bleibt nach seiner eigenen Methode richtig; neu
# gerechnet ergäbe er wegen dieser Änderungen andere Ergebnisse.
METHOD_CHANGES = (
    (
        (1, 9, 0),
        "tr-methode-1.9.0",
        "Aktien ohne Schlusskurs am Stichtag zählen mit ihrem letzten Schlusskurs (höchstens eine verpasste Börsensitzung, "
        "Software 1.14.0, deine Entscheidung vom 14.10.2026); bis 1.8.0 fehlten sie in den Ranglisten",
    ),
    (
        (1, 10, 0),
        "tr-methode-1.10.0",
        "Gleichstand exakt: bei rechnerisch gleichem Score die höhere Kursrendite, dann die ISIN (Software 1.18.0, deine "
        "Entscheidung vom 24.10.2026) – zugleich die Korrektur des bekannten Fehlers „gleichstand_rundung“",
    ),
)


def current_software() -> str:
    """Version der Software, deren Rechenkern die Gegenprobe der Korrektur nutzt (``traktien.__version__``)."""
    import traktien

    return str(getattr(traktien, "__version__", "unbekannt"))


def method_changes_after(method: str | None) -> list[dict]:
    """Beabsichtigte Methodenänderungen nach der Methode eines Stands (z. B. „tr-methode-1.8.0“ → 1.9.0 und 1.10.0)."""
    version = parse_version(str(method or "").replace("tr-methode-", ""))
    if version is None:
        return []
    return [{"methode": name, "aenderung": text} for since, name, text in METHOD_CHANGES if version < since]


def parse_version(text) -> tuple[int, ...] | None:
    """„1.6.0“ → (1, 6, 0); unbekannt → None (dann greift kein Eintrag aus KNOWN_ISSUES)."""
    try:
        return tuple(int(part) for part in str(text).split("+")[0].split(".")[:3])
    except (TypeError, ValueError):
        return None


# ------------------------------------------------------------------ Zählwerk


class Tally:
    """Zählt Prüfungen je Name: geprüft, abweichend und – ohne Namen oder Werte – Beispiele (Zeitraum, Code)."""

    def __init__(self) -> None:
        self.checked: Counter = Counter()
        self.failed: Counter = Counter()
        self.examples: dict[str, list[str]] = {}
        self.known: Counter = Counter()  # bekannte Fehler früherer Versionen (fachlich falsch, keine Rechenabweichung)

    def known_issue(self, name: str) -> None:
        """Ein Fall aus ``KNOWN_ISSUES``: bestätigt das damalige Verhalten, gilt aber nicht als korrekt."""
        self.checked[name] += 1
        self.known[name] += 1

    def check(self, name: str, ok: bool, example: str = "") -> bool:
        self.checked[name] += 1
        if not ok:
            self.failed[name] += 1
            bucket = self.examples.setdefault(name, [])
            if example and len(bucket) < 5:
                bucket.append(example)
        return ok

    def many(self, name: str, total: int, bad: int, example: str = "") -> None:
        self.checked[name] += int(total)
        if bad:
            self.failed[name] += int(bad)
            bucket = self.examples.setdefault(name, [])
            if example and len(bucket) < 5:
                bucket.append(example)

    def as_dict(self) -> dict:
        return {
            name: {
                "geprueft": int(self.checked[name]),
                "abweichend": int(self.failed[name]),
                **({"bekannter_fehler": int(self.known[name])} if self.known[name] else {}),
                **({"beispiele": self.examples[name]} if name in self.examples else {}),
            }
            for name in sorted(self.checked)
        }

    @property
    def total_failed(self) -> int:
        return int(sum(self.failed.values()))


# ------------------------------------------------------------------ Datenstand lesen


class Stand:
    """Ein entschlüsselter Datenstand (Ordner mit den Dateien eines Snapshots)."""

    def __init__(self, folder: Path, snapshot_id: str, key: crypto.KeyMaterial | None) -> None:
        self.folder = folder
        self.sid = snapshot_id
        self.key = key
        self._cache: dict[str, object] = {}
        self.plain_hashes: dict[str, str] = {}

    def raw(self, relative: str) -> bytes:
        blob = (self.folder / relative).read_bytes()
        plain = crypto.unpack(blob, self.key, f"snapshots/{self.sid}/{relative}")
        self.plain_hashes[relative] = hashlib.sha256(plain).hexdigest()
        return plain

    def get(self, relative: str):
        if relative not in self._cache:
            self._cache[relative] = json.loads(self.raw(relative))
        return self._cache[relative]

    def exists(self, relative: str) -> bool:
        return (self.folder / relative).is_file()

    def drop(self, relative: str) -> None:
        self._cache.pop(relative, None)


def doubled_ranks(values: np.ndarray) -> np.ndarray:
    """Doppelter aufsteigender Durchschnittsrang (Gleichstand a…b → a + b), eigene Umsetzung."""
    values = np.asarray(values, dtype=np.float64)
    order = np.argsort(values, kind="stable")
    ranks = np.empty(len(values), dtype=np.int64)
    sorted_values = values[order]
    k = 0
    while k < len(values):
        j = k
        while j + 1 < len(values) and sorted_values[j + 1] == sorted_values[k]:
            j += 1
        ranks[order[k : j + 1]] = (k + 1) + (j + 1)
        k = j + 1
    return ranks


def percentiles(doubled: np.ndarray) -> np.ndarray:
    m = len(doubled)
    if m == 0:
        return np.empty(0)
    if m == 1:
        return np.array([100.0])
    return 100.0 * (doubled.astype(np.float64) / 2.0 - 1.0) / (m - 1)


def score(weight: int, g: np.ndarray, r: np.ndarray) -> np.ndarray:
    """Score(w) = (w/100)·G + (1 − w/100)·R (Methodenbeschreibung), 0/100 = R, 100/0 = G."""
    if weight == 0:
        return r.copy()
    if weight == 100:
        return g.copy()
    a = weight / 100
    return a * g + (1 - weight / 100) * r


def tie_positions(primary_sorted: np.ndarray) -> list[int]:
    if len(primary_sorted) < 2:
        return []
    eq = primary_sorted[1:] == primary_sorted[:-1]
    flags = np.zeros(len(primary_sorted), dtype=bool)
    flags[1:] |= eq
    flags[:-1] |= eq
    return np.nonzero(flags)[0].astype(int).tolist()


def exact_keys(weight: int, ar_g: np.ndarray, ar_r: np.ndarray) -> np.ndarray:
    """Score exakt als ganze Zahl (ab ranking-11w-v3): Score · 2·(M − 1) = w·(dG − 2) + (100 − w)·(dR − 2), aus den
    selbst gerechneten doppelten Rängen; in Python-Ganzzahlen gerechnet (kein Überlauf, keine Rundung)."""
    return np.array([weight * (int(g) - 2) + (100 - weight) * (int(r) - 2) for g, r in zip(ar_g.tolist(), ar_r.tolist())], dtype=np.int64)


def rank_group(members: np.ndarray, status: np.ndarray, r_of: dict[int, float], r2_of: dict[int, float | None]) -> dict:
    """Alle Ranglisten einer Vergleichsmenge (Gruppe A: V/U, Gruppe B: V ∩ L / U ∩ L) – unabhängig gerechnet.

    ``u``/``u_ties``: Reihenfolge nach ranking-11w-v3 (Score exakt, dann Rendite, dann ISIN); ``u_float``/``u_ties_float``:
    nach ranking-11w-v2 (Gleitkomma-Score) – für Stände bis tr-methode-1.9.0 und den Vergleich beider Regeln."""
    v = np.array(sorted(int(i) for i in members), dtype=np.int64)
    r_v = np.array([r_of[int(i)] for i in v], dtype=np.float64)
    out: dict = {"V": v}
    out["v0"] = v[np.lexsort((v, -r_v))] if len(v) else v
    out["v0_ties"] = tie_positions(r_v[np.lexsort((v, -r_v))]) if len(v) else []
    out["a_rv"] = dict(zip(v.tolist(), doubled_ranks(r_v).tolist()))
    u = np.array([i for i in v.tolist() if int(status[i]) == U_STATUS], dtype=np.int64)
    out["U"] = u
    r_u = np.array([r_of[int(i)] for i in u], dtype=np.float64)
    g_raw = np.array([r2_of[int(i)] if r2_of.get(int(i)) is not None else np.nan for i in u], dtype=np.float64)
    out["u_valid"] = bool(np.all(np.isfinite(g_raw)))
    ar_g = doubled_ranks(g_raw) if len(u) else np.empty(0, dtype=np.int64)
    ar_r = doubled_ranks(r_u) if len(u) else np.empty(0, dtype=np.int64)
    out["a_gu"] = dict(zip(u.tolist(), ar_g.tolist()))
    out["a_ru"] = dict(zip(u.tolist(), ar_r.tolist()))
    p_g, p_r = percentiles(ar_g), percentiles(ar_r)
    out["u"], out["u_ties"], out["u_float"], out["u_ties_float"] = {}, {}, {}, {}
    for w in WEIGHTS:
        if not len(u):
            out["u"][w] = out["u_float"][w] = np.empty(0, dtype=np.int64)
            out["u_ties"][w] = out["u_ties_float"][w] = []
            continue
        s = score(w, p_g, p_r)
        if w == 0:
            order = order_float = np.lexsort((u, -r_u))
            primary = primary_float = r_u[order]
        elif w == 100:
            order = order_float = np.lexsort((u, -r_u, -g_raw))
            primary = primary_float = g_raw[order]
        else:
            key = exact_keys(w, ar_g, ar_r)
            order = np.lexsort((u, -r_u, -key))
            primary = key[order]
            order_float = np.lexsort((u, -r_u, -s))
            primary_float = s[order_float]
        out["u"][w] = u[order]
        out["u_ties"][w] = tie_positions(primary)
        out["u_float"][w] = u[order_float]
        out["u_ties_float"][w] = tie_positions(primary_float)
    return out


# ------------------------------------------------------------------ Prüfungen eines Stands


class Nachrechnung:
    def __init__(self, stand: Stand) -> None:
        self.stand = stand
        self.t = Tally()
        self.manifest = stand.get("manifest.bin")
        self.method = self.manifest.get("method") or {}
        self.cutoff = int(self.manifest["cutoff_day"])
        self.intraday = self.manifest.get("art") == "zwischenstand"
        # Eigener Endtag je Aktie erlaubt: im Zwischenstand (ab 1.13) und ab tr-methode-1.9.0 in jedem Stand
        self.own_ends_allowed = self.intraday or bool(self.manifest.get("letzter_schlusskurs"))
        self.software = parse_version((self.manifest.get("versions") or {}).get("software"))
        # Gleichstandsregel des Stands: ab ranking-11w-v3 (tr-methode-1.10.0) Score exakt, davor Gleitkomma-Score
        self.ranking_version = str((self.manifest.get("versions") or {}).get("ranking") or "ranking-11w-v2")
        self.exact_ties = self.ranking_version not in ("ranking-11w-v1", "ranking-11w-v2")
        self.tie_effect = Counter()  # exakte gegen Gleitkomma-Reihenfolge auf denselben Werten (Gegenprobe Methodenwechsel)
        # ab 1.18: Rechenkern der aktuellen Version auf den Werten dieses Stands gegen die eigene exakte Rechnung – belegt bei
        # älteren Ständen, dass die Ursache von „gleichstand_rundung“ behoben ist (Prüfling ist der Rechenkern, nicht der Stand)
        self.current = Counter()
        # ab 1.18: Kennzeichen „Kursreihe vorhanden“ bei Aktien ohne gültigen Kurs (Ursache von „reihe_vorhanden“)
        self.series_flag = Counter()
        self.instruments = stand.get("instruments.bin")
        self.isins: list[str] = self.instruments["isin"]
        self.n = len(self.isins)
        self.values: dict[int, dict[int, dict]] = {}  # h → idx → Werte des Fensters (für Vergleiche)
        self.not_checkable: Counter = Counter()  # Status ohne Nachrechnung aus der Kursreihe (nur gezählt)
        self.diagnosis: dict = {}  # Ursachensuche bei Abweichungen (nur Zählwerte und Verhältnisse)
        self.orders: dict[int, dict] = {}
        self.series_end: dict[int, int] = {}
        # ab 1.18.1: Prüfnachweis des damaligen Laufs (evidence-<ID>.tra) – nur mit --nachweis
        self.evidence: dict | None = None
        self.evidence_result: dict = {}

    def known_applies(self, name: str) -> bool:
        """Gilt der bekannte Fehler ``name`` für diesen Stand (Software vor der Korrektur)?"""
        issue = KNOWN_ISSUES.get(name)
        return issue is not None and self.software is not None and self.software < issue["behoben_in"]

    def without_valid_price(self, i: int) -> bool:
        """Aktie ohne einen einzigen gültigen Kurs: in keinem Zeitraum mit Rendite und ohne letzten Schlusskurs."""
        if any(int(self._status[h][i]) in V_STATUS for h in self._status):
            return False
        last = (self.instruments.get("last_close") or [None] * self.n)[i]
        return last is None or not (isinstance(last, (int, float)) and math.isfinite(last) and last > 0)

    # ---------------------------------------------------------- 1. Dateien

    def expected_hashes(self) -> dict[str, str]:
        """Prüfsummen aller Dateien: bis 1.14 im Manifest, ab 1.15 in einer eigenen Datei, die das Manifest über ihre
        Prüfsumme verankert."""
        files = self.manifest.get("files") or {}
        if "sha256_plaintext" in files:
            return files["sha256_plaintext"] or {}
        name = files.get("pruefsummen")
        if not name or not self.stand.exists(name):
            self.t.check("dateien_vorhanden", False, "Prüfsummen-Datei fehlt")
            return {}
        try:
            data = self.stand.get(name)
        except (crypto.ContainerError, ValueError):
            self.t.check("dateien_pruefsumme", False, "Prüfsummen-Datei nicht lesbar")
            return {}
        self.t.check("dateien_pruefsumme", self.stand.plain_hashes.get(name) == files.get("sha256_pruefsummen"), "SHA-256 der Prüfsummen-Datei")
        return data.get("sha256_plaintext") or {}

    def check_files(self) -> None:
        expected = self.expected_hashes()
        for relative, digest in sorted(expected.items()):
            if not self.stand.exists(relative):
                self.t.check("dateien_vorhanden", False, "fehlt")
                continue
            self.t.check("dateien_vorhanden", True)
            if relative not in self.stand.plain_hashes:
                try:
                    self.stand.raw(relative)
                except crypto.ContainerError:
                    self.t.check("dateien_pruefsumme", False, "nicht entschlüsselbar")
                    continue
            self.t.check("dateien_pruefsumme", self.stand.plain_hashes[relative] == digest, "SHA-256")

    # ---------------------------------------------------------- 2. Zeiträume je Aktie

    def check_windows(self) -> None:
        m = self.method
        gap = int(m.get("anchor_max_gap_days", 7))
        min_return = int(m.get("min_obs_return", 2))
        min_trend = int(m.get("min_obs_trend", 15))
        cover = m.get("min_session_coverage") or {"num": 4, "den": 5}
        tolerated = int(m.get("tolerated_missing_sessions", 1))
        vcover = m.get("min_volume_coverage") or {"num": 4, "den": 5}
        basis = m.get("volume_basis", "beobachtungen")
        every = bool(m.get("volume_every_obs", True))
        edge = bool(m.get("edge_volume_positive", True))

        windows = {h: self.stand.get(f"windows/{h}.full.bin") for h in range(1, 91)}
        status = {h: np.frombuffer(base64.b64decode(windows[h]["status_b64"]), dtype=np.uint8) for h in windows}
        rows = {h: {int(i): k for k, i in enumerate(windows[h]["m"]["idx"])} for h in windows}
        for h, win in windows.items():
            self.t.check("fenster_stichtag", int(win["cutoff_day"]) == self.cutoff, f"h={h}")
            in_v = {i for i in range(self.n) if int(status[h][i]) in V_STATUS}
            self.t.check("fenster_menge_V", in_v == set(rows[h]), f"h={h}")
        self._windows, self._status, self._rows = windows, status, rows
        has_series = self.instruments.get("has_series") or [True] * self.n
        last_day = self.instruments.get("last_close_day") or [None] * self.n
        for i in range(self.n):
            if self.without_valid_price(i):
                self.series_flag["ohne_gueltigen_kurs"] += 1
                if has_series[i]:
                    self.series_flag["mit_kennzeichen"] += 1

        for i, isin in enumerate(self.isins):
            if not has_series[i]:
                continue
            relative = f"series/{isin}.bin"
            if not self.stand.exists(relative):
                if self.known_applies("reihe_vorhanden") and self.without_valid_price(i):
                    self.t.known_issue("reihe_vorhanden")
                else:
                    self.t.check("reihe_vorhanden", False, "Kursreihe fehlt")
                continue
            self.t.check("reihe_vorhanden", True)
            series = self.stand.get(relative)
            self.stand.drop(relative)
            d = np.asarray(series["d"], dtype=np.int64)
            c = np.asarray([np.nan if x is None else x for x in series["c"]], dtype=np.float64)
            vol = np.asarray([np.nan if x is None else x for x in series["v"]], dtype=np.float64)
            if not len(d):
                continue
            self.t.check("reihe_aufsteigend", bool(np.all(np.diff(d) > 0)), "Tage")
            self.t.check("reihe_bis_stichtag", int(d[-1]) <= self.cutoff, "nach Stichtag")
            self.t.check("letzter_kurstag", last_day[i] is None or int(last_day[i]) == int(d[-1]), "instruments.last_close_day")
            end = int(d[-1])
            self.series_end[i] = end
            sessions = np.array(sorted(set(d.tolist()) | {int(x) for x in series.get("gaps") or []}), dtype=np.int64)
            sessions = sessions[sessions <= end]
            window_start = series.get("window_start") or [None] * 90
            window_status = series.get("window_status") or [None] * 90
            positive = np.isfinite(vol) & (vol > 0)
            reported = np.isfinite(vol) & (vol >= 0)
            pos_cum = np.concatenate([[0], np.cumsum(positive)])
            rep_cum = np.concatenate([[0], np.cumsum(reported)])
            r2_cache: dict[int, float | None] = {}
            for h in range(1, 91):
                st = int(self._status[h][i])
                self.t.check("status_reihe_gleich_fenster", window_status[h - 1] == st, f"h={h}")
                target = end - h
                k = int(np.searchsorted(sessions, target, side="right")) - 1
                start = int(sessions[k]) if k >= 0 else None
                if st not in V_STATUS:
                    self._check_reason(st, h, d, sessions, start, target, gap, min_return, cover, tolerated, vcover, basis, every, edge, positive, pos_cum, rep_cum)
                    continue
                # Menge V: Ende am Stichtag oder – ohne Kurs am Stichtag – am letzten Schlusskurs (Zwischenstand ab 1.13,
                # alle Stände ab tr-methode-1.9.0; höchstens eine verpasste Sitzung, d. h. wenige Kalendertage)
                own_end_ok = end == self.cutoff or (self.own_ends_allowed and self.cutoff - end <= OWN_END_MAX_DAYS)
                self.t.check("ende_am_stichtag", own_end_ok, f"h={h}")
                ok_start = start is not None and target - start <= gap
                self.t.check("startsitzung", ok_start, f"h={h}")
                if not ok_start:
                    continue
                j = int(np.searchsorted(d, start))
                if not self.t.check("startkurs_vorhanden", j < len(d) and int(d[j]) == start, f"h={h}"):
                    continue
                row = self._rows[h][i]
                mm = self._windows[h]["m"]
                n_obs = len(d) - j
                n_exp = int(np.count_nonzero((sessions >= start) & (sessions <= end)))
                p0, p1 = float(c[j]), float(c[-1])
                r = p1 / p0 - 1.0
                self.t.check("start_gleich", int(mm["start"][row]) == start and window_start[h - 1] == start, f"h={h}")
                self.t.check("kurse_im_zeitraum", int(mm["n"][row]) == n_obs, f"h={h}")
                self.t.check("sitzungen_im_zeitraum", int(mm["n_exp"][row]) == n_exp, f"h={h}")
                self.t.check("startkurs_endkurs", mm["p0"][row] == p0 and mm["p1"][row] == p1, f"h={h}")
                self.t.check("rendite", mm["r"][row] == r, f"h={h}")
                # Zulassung zur Rendite-Rangliste (Menge V)
                missing = n_exp - n_obs
                cover_ok = missing <= tolerated or n_obs * cover["den"] >= n_exp * cover["num"]
                vpos = int(pos_cum[-1] - pos_cum[j])
                vrep = int(rep_cum[-1] - rep_cum[j])
                base = n_exp if basis == "sitzungen" else n_obs
                vol_ok = (not every or vrep >= n_obs) and (not edge or (bool(positive[j]) and bool(positive[-1]))) and vpos * vcover["den"] >= base * vcover["num"]
                self.t.check("zulassung_V", n_obs >= min_return and cover_ok and vol_ok, f"h={h} Status {st}")
                # Trend-Status und R²
                r2 = r2_cache.get(j, "neu")
                if r2 == "neu":
                    r2 = r2_cache[j] = self._r2(c[j:]) if n_obs >= min_trend else None
                slope_positive = n_obs >= 2 and self._slope_positive(c[j:])
                if n_obs < min_trend:
                    expected = 15
                elif not (r > 0.0) or not slope_positive:
                    expected = 16
                elif r2 is None:
                    expected = 17
                else:
                    expected = 18
                self.t.check("trend_status", st == expected, f"h={h} Status {st} statt {expected}")
                published = mm["r2"][row]
                if st == U_STATUS:
                    ok = published is not None and r2 is not None and abs(published - r2) <= R2_TOLERANCE
                    self.t.check("r2", ok, f"h={h}")
                # Veröffentlichte Werte (was die App zeigt) – für den Vergleich Zwischenstand ↔ Stand mit Schlusskursen
                self.values.setdefault(h, {})[i] = {
                    "start": int(mm["start"][row]), "n": int(mm["n"][row]), "n_exp": int(mm["n_exp"][row]),
                    "p0": mm["p0"][row], "p1": mm["p1"][row], "r": mm["r"][row], "r2": published, "end": end,
                }  # fmt: skip

    @staticmethod
    def _slope_positive(p: np.ndarray) -> bool:
        t = np.arange(len(p), dtype=np.float64)
        return float(np.dot(t - t.mean(), p - p.mean())) > 0.0

    @staticmethod
    def _r2(p: np.ndarray) -> float | None:
        """R² der Geraden durch die Kurse (t = 0 … n−1) als quadrierte Korrelation – andere Formel als der Rechenkern."""
        n = len(p)
        t = np.arange(n, dtype=np.float64)
        dp = p - p.mean()
        sst = float(np.dot(dp, dp))
        if sst <= 1e-18 * n * float(p.mean()) ** 2:
            return None
        dt = t - t.mean()
        corr = float(np.dot(dt, dp)) / math.sqrt(float(np.dot(dt, dt)) * sst)
        return min(1.0, max(0.0, corr * corr))

    def _check_reason(self, st, h, d, sessions, start, target, gap, min_return, cover, tolerated, vcover, basis, every, edge, positive, pos_cum, rep_cum) -> None:
        """Grund außerhalb der Rendite-Rangliste nachvollziehen, soweit er aus der Kursreihe folgt (nur gezählt)."""
        end = int(d[-1])
        if st in (7, 8):
            ok = self.intraday or end != self.cutoff
            self.t.check("grund_stichtag", ok, f"h={h} Status {st}")
        elif st == 10:
            self.t.check("grund_keine_startsitzung", start is None or target - start > gap or start < int(d[0]), f"h={h}")
        elif st == 11:
            self.t.check("grund_startkurs_fehlt", start is not None and start not in set(d.tolist()), f"h={h}")
        elif st == 12:
            if start is None:
                return
            j = int(np.searchsorted(d, start))
            n_obs = len(d) - j
            n_exp = int(np.count_nonzero((sessions >= start) & (sessions <= end)))
            self.t.check("grund_abdeckung", n_exp - n_obs > tolerated and n_obs * cover["den"] < n_exp * cover["num"], f"h={h}")
        elif st == 14:
            if start is None or start not in set(d.tolist()):
                return
            j = int(np.searchsorted(d, start))
            n_obs = len(d) - j
            n_exp = int(np.count_nonzero((sessions >= start) & (sessions <= end)))
            vpos = int(pos_cum[-1] - pos_cum[j])
            vrep = int(rep_cum[-1] - rep_cum[j])
            base = n_exp if basis == "sitzungen" else n_obs
            bad = (every and vrep < n_obs) or (edge and not (bool(positive[j]) and bool(positive[-1]))) or vpos * vcover["den"] < base * vcover["num"]
            self.t.check("grund_volumen", bool(bad), f"h={h}")
        else:
            # Identität, Kalender, Datenlücken vor der Reihe, zurückgehaltene Kurssprünge: nicht aus der Kursreihe ableitbar
            self.not_checkable[st] += 1

    # ---------------------------------------------------------- 3. Ranglisten

    def check_rankings(self) -> None:
        liquid = (self.instruments.get("turnover") or {}).get("liquid") or [False] * self.n
        for h in range(1, 91):
            win = self._windows[h]
            mm = win["m"]
            status = self._status[h]
            idx = [int(i) for i in mm["idx"]]
            r_of = {i: float(mm["r"][k]) for k, i in enumerate(idx)}
            r2_of = {i: mm["r2"][k] for k, i in enumerate(idx)}
            a = rank_group(np.array(idx, dtype=np.int64), status, r_of, r2_of)
            b = rank_group(np.array([i for i in idx if liquid[i]], dtype=np.int64), status, r_of, r2_of)
            orders, ties = win["orders"], win["ties"]
            self.orders[h] = {"v0": orders["v0"], "u": orders["u"], "v0l": orders["v0l"], "ul": orders["ul"]}
            counts = win["counts"]
            self.t.check("anzahl_V_U_L", counts["V"] == len(a["V"]) and counts["U"] == len(a["U"]) and counts["L"] == len(b["V"]) and counts["UL"] == len(b["U"]), f"h={h}")
            self.t.check("rangliste_A_0_100_rendite", orders["v0"] == a["v0"].tolist(), f"h={h}")
            self.t.check("gleichstaende", ties["v0"] == a["v0_ties"], f"h={h} v0")
            # Gruppe B, reine Rendite: dieselbe Reihenfolge wie Gruppe A ohne die übrigen Aktien
            self.t.check("rangliste_B_0_100_rendite", orders["v0l"] == b["v0"].tolist(), f"h={h}")
            self.t.check("durchschnittsraenge", [a["a_rv"][i] for i in idx] == mm["a_rv"], f"h={h} a_rv")
            self.t.check("durchschnittsraenge", [a["a_gu"].get(i) for i in idx] == mm["a_gu"], f"h={h} a_gu")
            self.t.check("durchschnittsraenge", [a["a_ru"].get(i) for i in idx] == mm["a_ru"], f"h={h} a_ru")
            self.t.check("durchschnittsraenge", [b["a_rv"].get(i) for i in idx] == mm["a_rvl"], f"h={h} a_rvl")
            self.t.check("durchschnittsraenge", [b["a_gu"].get(i) for i in idx] == mm["a_gul"], f"h={h} a_gul")
            self.t.check("durchschnittsraenge", [b["a_ru"].get(i) for i in idx] == mm["a_rul"], f"h={h} a_rul")
            known: dict[tuple[str, int], bool] = {}
            for w in WEIGHTS:
                known[("A", w)] = self._weighted("A", orders["u"][str(w)], ties["u"][str(w)], a, h, w)
                if orders.get("ul"):
                    known[("B", w)] = self._weighted("B", orders["ul"][str(w)], ties["ul"][str(w)], b, h, w)
            self._current_version(h, mm, idx, a, b, liquid, known, bool(orders.get("ul")))
            # Gegenprobe zum Methodenwechsel 1.9.0 → 1.10.0: dieselben Werte nach beiden Gleichstandsregeln
            for group, grp, lst in (("A", a, True), ("B", b, bool(orders.get("ul")))):
                if not lst:
                    continue
                pairs = [(grp["v0"], grp["v0"])] + [(grp["u_float"][w], grp["u"][w]) for w in WEIGHTS if w > 0]
                for before, after in pairs:
                    if not len(before) and not len(after):
                        continue
                    self.tie_effect["verglichen"] += 1
                    if (before[0] if len(before) else None) != (after[0] if len(after) else None):
                        self.tie_effect["spitze_geaendert"] += 1
                    if set(before[:10].tolist()) != set(after[:10].tolist()):
                        self.tie_effect["top10_andere_aktien"] += 1
                    elif before[:10].tolist() != after[:10].tolist():
                        self.tie_effect["top10_andere_reihenfolge"] += 1
                    if before.tolist() != after.tolist():
                        self.tie_effect["reihenfolge_geaendert"] += 1
            # Kopfdatei (schnelle Anzeige) = Anfang der vollständigen Ranglisten
            if self.stand.exists(f"windows/{h}.bin"):
                head = self.stand.get(f"windows/{h}.bin")
                self.stand.drop(f"windows/{h}.bin")
                limit = len(head["orders"]["v0"])
                ok = head["orders"]["v0"] == orders["v0"][:limit] and all(head["orders"]["u"][str(w)] == orders["u"][str(w)][: len(head["orders"]["u"][str(w)])] for w in WEIGHTS)
                self.t.check("kopfdatei_gleich_vollstaendig", ok, f"h={h}")

    def _current_version(self, h: int, mm: dict, idx: list[int], a: dict, b: dict, liquid, known: dict, with_b: bool) -> None:
        """Gegenprobe der Korrektur (ab 1.18): Rechenkern der **aktuellen** Version (``traktien.analytics.ranking``) auf den
        Werten dieses Stands – Rendite, R², Steigung, Rauschen, Mengen V/U und L – gegen die eigene exakte Rechnung.

        Prüfling ist hier ausnahmsweise der Rechenkern, nicht der Stand: Bei einem Stand mit dem bekannten Fehler
        „gleichstand_rundung“ zeigt das, ob die heutige Software genau diese Fälle richtig ordnet (Ursache behoben). Die
        Erwartung bleibt die eigene Rechnung dieses Skripts; der Stand selbst wird dadurch nicht verändert."""
        from traktien.analytics import ranking as current  # Prüfling: Ranglistenregel der aktuellen Version

        if not a.get("u_valid", True) or (with_b and not b.get("u_valid", True)):
            self.current["fenster_nicht_pruefbar"] += 1  # U mit fehlendem R² – fällt schon in der Nachrechnung auf
            return

        def column(name: str, default: float) -> np.ndarray:
            out = np.full(self.n, default, dtype=np.float64)
            values = mm.get(name)
            if values is not None:
                out[idx] = [default if v is None else float(v) for v in values]
            return out

        r_all, r2_all = column("r", np.nan), column("r2", np.nan)
        slope_all, noise_all = column("slope", 0.0), column("noise", 0.0)
        base = current.rank_window(h, a["V"], a["U"], r_all, r2_all, slope_all, noise_all)
        groups = [("A", a, base)]
        if with_b:
            groups.append(("B", b, current.group_b_ranking(base, np.asarray(liquid, dtype=bool), r_all, r2_all, slope_all, noise_all)))
        for group, grp, ranked in groups:
            pairs = [(None, grp["v0"].tolist(), list(grp["v0_ties"]), ranked.native0)]
            pairs += [(w, grp["u"][w].tolist(), list(grp["u_ties"][w]), ranked.trend[w]) for w in WEIGHTS]
            for w, expected, expected_ties, got in pairs:
                if not expected and not got.size:
                    continue
                ok = got.order.tolist() == expected and got.tie_positions.tolist() == expected_ties
                self.current["ranglisten"] += 1
                self.current["gleich" if ok else "abweichend"] += 1
                if w is not None and known.get((group, w)):
                    self.current["bekannte_faelle"] += 1
                    self.current["bekannte_faelle_richtig" if ok else "bekannte_faelle_offen"] += 1

    def _weighted(self, group: str, published: list[int], published_ties: list[int], grp: dict, h: int, w: int) -> bool:
        """Gewichtete Rangliste prüfen: nach der Regel des Stands. Stände bis ranking-11w-v2 dürfen bei rechnerisch gleichem
        Score der Gleitkomma-Reihenfolge folgen – das bestätigt das damalige Verhalten, gilt aber als bekannter Fehler
        (``gleichstand_rundung``), nicht als korrekt. Alles andere ist eine Abweichung."""
        exact_order, exact_ties = grp["u"][w].tolist(), grp["u_ties"][w]
        if published == exact_order and published_ties == exact_ties:
            self.t.check(f"rangliste_{group}_gewichtet", True)
            self.t.check("gleichstaende", True)
            return False
        if not self.exact_ties and self.known_applies("gleichstand_rundung") and published == grp["u_float"][w].tolist() and published_ties == grp["u_ties_float"][w]:
            self.t.known_issue("gleichstand_rundung")
            return True
        self.t.check(f"rangliste_{group}_gewichtet", published == exact_order, f"h={h} w={w}")
        self.t.check("gleichstaende", published_ties == exact_ties, f"h={h} u{w}" if group == "A" else f"h={h} ul{w}")
        return False

    # ---------------------------------------------------------- 4. Ø Tagesumsatz

    def check_turnover(self) -> None:
        turnover = self.instruments.get("turnover") or {}
        if not turnover:
            return
        threshold = float(self.method.get("turnover_threshold_usd", 10_000_000.0))
        fx = self.stand.get("fx.bin") if self.stand.exists("fx.bin") else None
        fx_days = np.asarray(fx["tage"], dtype=np.int64) if fx else np.empty(0, dtype=np.int64)
        max_age = int(fx.get("max_alter_tage", 5)) if fx else 5

        def per_eur_at(currency: str, day: int, skip: int = 0) -> tuple[float, int] | None:
            """Einheiten je EUR am Tag oder am letzten Tag davor (höchstens ``max_age`` Tage alt); ``skip`` = so viele
            verfügbare Kurse überspringen (nur für die Ursachensuche)."""
            if currency == "EUR":
                return 1.0, day
            column = (fx or {}).get("je_eur", {}).get(currency)
            if column is None:
                return None
            k = int(np.searchsorted(fx_days, day, side="right")) - 1
            while k >= 0 and day - int(fx_days[k]) <= max_age:
                if column[k] is not None and column[k] > 0:
                    if skip == 0:
                        return float(column[k]), int(fx_days[k])
                    skip -= 1
                k -= 1
            return None

        def per_eur(currency: str, day: int) -> float | None:
            found = per_eur_at(currency, day)
            return None if found is None else found[0]

        diagnosis: Counter = Counter()
        ratios: list[float] = []

        for i, isin in enumerate(self.isins):
            st = turnover["status"][i]
            if st != "ok":
                self.t.check("umsatz_liquide_nur_mit_ok", not turnover["liquid"][i], "Status")
                continue
            relative = f"series/{isin}.bin"
            if not self.stand.exists(relative):
                self.t.check("umsatz_reihe", False, "Kursreihe fehlt")
                continue
            series = self.stand.get(relative)
            self.stand.drop(relative)
            d = np.asarray(series["d"], dtype=np.int64)
            first, last = int(turnover["first"][i]), int(turnover["last"][i])
            sessions = sorted({x for x in d.tolist() if first <= x <= last} | {int(x) for x in series.get("gaps") or [] if first <= int(x) <= last})
            self.t.check("umsatz_20_sitzungen", len(sessions) == int(turnover["sessions"][i]), "Sitzungen")
            factor = float(series["listing"].get("unit_factor") or 1.0)
            currency = turnover["currency"][i]
            values, positive = [], 0
            usd_values, rate_days, used_days = [], [], []
            for k, day in enumerate(d.tolist()):
                if not (first <= day <= last):
                    continue
                price, shares = series["c"][k], series["v"][k]
                if price is None or shares is None or not (price > 0) or shares < 0:
                    continue
                local = float(price) * float(shares) * factor
                values.append(local)
                used_days.append(day)
                positive += 1 if shares > 0 else 0
                if currency == "USD":
                    usd_values.append(local)
                else:
                    usd, own = per_eur_at("USD", day), per_eur_at(currency, day)
                    usd_values.append(local * (usd[0] / own[0]) if usd and own else float("nan"))
                    if usd and own:
                        rate_days.append(min(usd[1], own[1]))
            self.t.check("umsatz_tage_mit_daten", len(values) == int(turnover["with_data"][i]) and positive == int(turnover["positive"][i]), "Zählung")
            published = turnover["usd"][i]
            local_ok = turnover["local"][i] is not None and values and abs(float(np.mean(values)) - turnover["local"][i]) <= USD_TOLERANCE * max(abs(turnover["local"][i]), 1.0)
            self.t.check("umsatz_landeswaehrung", bool(local_ok), "Ø Landeswährung")
            if currency != "USD" and fx is None:
                # Stände vor 1.9 enthalten keine Wechselkursdatei (fx.bin): USD-Wert nicht nachrechenbar, nur gezählt
                self.not_checkable["umsatz_usd_ohne_wechselkursdatei"] += 1
                self.t.check("umsatz_gruppe_B", bool(turnover["liquid"][i]) == (published is not None and published >= threshold), "Schwelle")
                continue
            avg_usd = float(np.mean(usd_values)) if usd_values else float("nan")
            ok = published is not None and math.isfinite(avg_usd) and abs(avg_usd - published) <= USD_TOLERANCE * max(abs(published), 1.0)
            if currency != "USD":
                self.t.check(
                    "umsatz_wechselkurstage",
                    bool(rate_days) and turnover["fx_first"][i] == min(rate_days) and turnover["fx_last"][i] == max(rate_days),
                    "Tage der Referenzkurse",
                )
            if not ok and published is not None and math.isfinite(avg_usd) and avg_usd > 0:
                # Ursachensuche ohne Werte im Protokoll: Währungsklasse, Verhältnis, welche Variante passt
                kind = "USD" if currency == "USD" else ("EUR" if currency == "EUR" else "andere")
                diagnosis[f"klasse_{kind}{'_einheit' if factor != 1.0 else ''}"] += 1
                ratios.append(published / avg_usd)
                close = lambda x, p=published: x is not None and math.isfinite(x) and abs(x - p) <= USD_TOLERANCE * max(abs(p), 1.0)
                variants = {}
                if currency != "USD":
                    prev = []
                    for day, local in zip(used_days, values):
                        usd, own = per_eur_at("USD", day, 1), per_eur_at(currency, day, 1)
                        prev.append(local * usd[0] / own[0] if usd and own else float("nan"))
                    variants["kurs_vortag"] = float(np.mean(prev))
                    usd_l, own_l = per_eur("USD", last), per_eur(currency, last)
                    variants["kurs_letzter_tag"] = float(np.mean(values)) * usd_l / own_l if usd_l and own_l else None
                    variants["in_eur"] = float(np.mean([v / per_eur(currency, day) for day, v in zip(used_days, values) if per_eur(currency, day)])) if values else None
                    variants["ohne_umrechnung"] = float(np.mean(values))
                variants["einheit_doppelt"] = avg_usd * factor if factor != 1.0 else None
                variants["ohne_einheit"] = avg_usd / factor if factor != 1.0 else None
                variants["ohne_letzte_sitzung"] = float(np.mean(usd_values[:-1])) if len(usd_values) > 1 else None
                variants["ohne_erste_sitzung"] = float(np.mean(usd_values[1:])) if len(usd_values) > 1 else None
                matched = [name for name, value in variants.items() if close(value)]
                for name in matched or ["keine_variante"]:
                    diagnosis[f"passt_{name}"] += 1
            self.t.check("umsatz_usd", ok, "Ø USD")
            self.t.check("umsatz_gruppe_B", bool(turnover["liquid"][i]) == (published is not None and published >= threshold), "Schwelle")
        if diagnosis:
            q = np.quantile(np.asarray(ratios), [0.0, 0.25, 0.5, 0.75, 1.0]) if ratios else []
            self.diagnosis["umsatz"] = {**dict(sorted(diagnosis.items())), "verhaeltnis_quantile": [round(float(x), 6) for x in q]}

    # ---------------------------------------------------------- 5. Häufigkeit

    def check_frequency(self) -> None:
        frequency = self.stand.get("frequency.bin")
        for key, group in (("server_reference", "A"), ("server_reference_b", "B")):
            reference = frequency.get(key)
            if not reference:
                continue
            ours = self._count(group, range(1, 91), WEIGHTS)
            self.t.check(f"haeufigkeit_{group}_zellen", reference["E"] == ours["E"] and reference["cells"] == 990, "E")
            for entry in reference["entries"]:
                mine = ours["stats"].get(int(entry["idx"]))
                ok = mine is not None and all(entry[k] == mine[k] for k in ("n1", "n3", "n10", "A", "H", "W", "dew"))
                self.t.check(f"haeufigkeit_{group}_je_aktie", ok, "n1/n3/n10/A/H/W/dew")
            listed = sorted((s for s in ours["stats"].items() if s[1]["n10"] > 0), key=lambda kv: (-kv[1]["n10"], -kv[1]["H"], -kv[1]["n3"], -kv[1]["n1"], self.isins[kv[0]]))
            self.t.check(f"haeufigkeit_{group}_reihenfolge", [int(e["idx"]) for e in reference["entries"]] == [k for k, _ in listed[: len(reference["entries"])]], "Sortierung")
        # Top-10-Einträge je Zeitraum (für Bericht 1–30, Musterdepots und Top 3) = Anfang der Ranglisten
        occ = frequency.get("occ") or {}
        for key, lists in (("v0", None), ("v0l", None)):
            block = occ.get(key) or {}
            ok = all(self._occ_ok(block, h, self.orders[h][key]) for h in range(1, 91))
            self.t.check("haeufigkeit_eintraege", ok, key)
        for key in ("u", "ul"):
            for w in WEIGHTS:
                block = (occ.get(key) or {}).get(str(w)) or {}
                ok = all(self._occ_ok(block, h, (self.orders[h][key] or {}).get(str(w)) or []) for h in range(1, 91))
                self.t.check("haeufigkeit_eintraege", ok, f"{key}{w}")

    @staticmethod
    def _occ_ok(block: dict, h: int, order: list[int]) -> bool:
        if not block:
            return not order
        listed = [(rank, idx) for hh, rank, idx in zip(block["h"], block["rank"], block["idx"]) if hh == h]
        return listed == [(k + 1, int(i)) for k, i in enumerate(order[:10])]

    def _count(self, group: str, days, weights) -> dict:
        stats: dict[int, dict] = {}
        windows: dict[int, set] = {}
        weights_hit: dict[int, set] = {}
        effective: dict[int, set] = {}
        valid = 0
        for h in days:
            for w in weights:
                order = self._order(group, h, w)
                if not order:
                    continue
                valid += 1
                for i in order:
                    stats.setdefault(int(i), {"n1": 0, "n3": 0, "n10": 0, "A": 0})["A"] += 1
                for pos, i in enumerate(order[:10]):
                    s = stats[int(i)]
                    s["n1"] += pos == 0
                    s["n3"] += pos < 3
                    s["n10"] += 1
                    windows.setdefault(int(i), set()).add(h)
                    weights_hit.setdefault(int(i), set()).add(w)
                    value = self.values.get(h, {}).get(int(i))
                    if value is not None:
                        effective.setdefault(int(i), set()).add((value["start"], value["end"]))
        for i, s in stats.items():
            s["H"] = len(windows.get(i, ()))
            s["W"] = len(weights_hit.get(i, ()))
            s["dew"] = len(effective.get(i, ()))
        return {"E": valid, "stats": stats}

    def _order(self, group: str, h: int, w: int) -> list[int]:
        orders = self.orders[h]
        if group == "A":
            return orders["v0"] if w == 0 else orders["u"][str(w)]
        return orders["v0l"] if w == 0 else (orders["ul"] or {}).get(str(w)) or []

    # ---------------------------------------------------------- Ablauf

    def check_evidence(self) -> None:
        """Prüfnachweis des damaligen Laufs gegen den veröffentlichten Stand (ab 1.18.1). Der Nachweis entsteht im selben Lauf
        wie der Stand und enthält die Eingangsreihen (``obs_*``) und alle berechneten Kennzahlen; beide liegen seitdem
        unverändert und verschlüsselt im Release. Gleich sein müssen: Aktienliste, jeder veröffentlichte Schlusskurs (an den
        Tagen, die beide enthalten), jede veröffentlichte Rendite und jedes R²."""
        ev = self.evidence or {}
        result: dict = {"kurse_verglichen": 0, "kurse_gleich": 0, "tage_nur_im_stand": 0, "tage_nur_im_nachweis": 0,
                        "renditen_verglichen": 0, "renditen_gleich": 0, "r2_verglichen": 0, "r2_gleich": 0}
        isins = [str(x) for x in ev.get("isins", [])]
        same_list = isins == list(self.isins)
        result["aktienliste_gleich"] = same_list
        self.t.check("nachweis_aktienliste", same_list, f"{len(isins)} gegen {self.n}")
        if not same_list:
            self.evidence_result = result
            return
        obs_i = np.asarray(ev.get("obs_instrument", []), dtype=np.int64)
        obs_d = np.asarray(ev.get("obs_day", []), dtype=np.int64)
        obs_c = np.asarray(ev.get("obs_close", []), dtype=np.float64)
        order = np.argsort(obs_i, kind="stable")
        obs_i, obs_d, obs_c = obs_i[order], obs_d[order], obs_c[order]
        bounds = np.searchsorted(obs_i, np.arange(self.n + 1))
        has_series = self.instruments.get("has_series") or [True] * self.n
        for i, isin in enumerate(self.isins):
            relative = f"series/{isin}.bin"
            if not has_series[i] or not self.stand.exists(relative):
                continue
            series = self.stand.get(relative)
            self.stand.drop(relative)
            original = dict(zip(obs_d[bounds[i] : bounds[i + 1]].tolist(), obs_c[bounds[i] : bounds[i + 1]].tolist()))
            published = {int(d): float(c) for d, c in zip(series.get("d") or [], series.get("c") or []) if c is not None}
            for day, close in published.items():
                if day not in original:
                    result["tage_nur_im_stand"] += 1
                    continue
                result["kurse_verglichen"] += 1
                if self.t.check("nachweis_kurs_gleich", original[day] == close, "Kurs des Stands ≠ Eingangsreihe"):
                    result["kurse_gleich"] += 1
            first = min(published) if published else None
            result["tage_nur_im_nachweis"] += sum(1 for day in original if first is not None and day >= first and day not in published)
        r = np.asarray(ev.get("r", []), dtype=np.float64)
        r2 = np.asarray(ev.get("r2", []), dtype=np.float64)
        windows = getattr(self, "_windows", None) or {}
        if r.ndim == 2 and r.shape[0] != self.n and r.shape[1] == self.n:
            r, r2 = r.T, r2.T
        for h, win in windows.items():
            mm = win["m"]
            for k, idx in enumerate(mm["idx"]):
                idx = int(idx)
                if r.ndim != 2 or idx >= r.shape[0] or h - 1 >= r.shape[1]:
                    continue
                value = mm["r"][k]
                if value is not None:
                    result["renditen_verglichen"] += 1
                    if self.t.check("nachweis_rendite_gleich", float(r[idx, h - 1]) == float(value), f"h={h}"):
                        result["renditen_gleich"] += 1
                q = (mm.get("r2") or [None] * len(mm["idx"]))[k]
                if q is not None and r2.ndim == 2:
                    result["r2_verglichen"] += 1
                    if self.t.check("nachweis_r2_gleich", float(r2[idx, h - 1]) == float(q), f"h={h}"):
                        result["r2_gleich"] += 1
        self.evidence_result = result

    def run(self) -> dict:
        began = time.monotonic()
        self.check_windows()
        self.check_rankings()
        self.check_turnover()
        self.check_frequency()
        self.check_files()
        if self.evidence is not None:
            self.check_evidence()
        in_v = sum(len(v) for v in self.values.values())
        info = {
            "art": "zwischenstand" if self.intraday else "stand_mit_schlusskursen",
            "snapshot_id": self.stand.sid,
            "stichtag": _iso(self.cutoff),
            "aktien": self.n,
            "aktien_mit_kursreihe": len(self.series_end),
            "zeitraeume_in_ranglisten": in_v,
            "ranglisten": 90 * 2 * 12,
            "sekunden": round(time.monotonic() - began, 1),
            "pruefungen": self.t.as_dict(),
            "abweichungen": self.t.total_failed,
            "nicht_nachrechenbar": {str(k): int(v) for k, v in sorted(self.not_checkable.items(), key=lambda kv: str(kv[0]))},
            "wechselkursdatei": self.stand.exists("fx.bin"),
            "software": (self.manifest.get("versions") or {}).get("software"),
            "methode": (self.manifest.get("versions") or {}).get("method") or self.method.get("version"),
            "bekannte_fehler": {
                name: {"anzahl": int(count), **{k: (".".join(map(str, v)) if isinstance(v, tuple) else v) for k, v in KNOWN_ISSUES[name].items()}}
                for name, count in self.t.known.items()
                if count
            },
            "diagnose": self.diagnosis,
            "ranglistenversion": self.ranking_version,
            # exakte Reihenfolge (ab 1.10.0) gegen die Gleitkomma-Reihenfolge (bis 1.9.0) auf den Werten dieses Stands
            "gleichstand_wirkung": dict(self.tie_effect),
            # ab 1.18: getrennt ausgewiesen – reproduziert (keine Abweichung) ist nicht dasselbe wie fachlich korrekt
            "aktuelle_version": {"software": current_software(), **{k: int(v) for k, v in self.current.items()}},
            "kursreihe_kennzeichen": {k: int(v) for k, v in self.series_flag.items()},
            "methodenaenderungen_danach": method_changes_after((self.manifest.get("versions") or {}).get("method") or self.method.get("version")),
            "berechnet_utc": self.manifest.get("computed_at_utc"),
            "vollstaendigkeit": (self.manifest.get("completeness") or {}).get("status"),
        }
        if self.evidence is not None:
            info["nachweis"] = dict(self.evidence_result)
        comparison = self.manifest.get("method_comparison") or {}
        if self.exact_ties and comparison.get("vorher") and comparison.get("ranglisten"):
            # Gegenprobe: die vom Server veröffentlichte Wirkung des Methodenwechsels = eigene Rechnung (gleiche Zulassung)
            published = comparison["ranglisten"]
            own = {key: int(self.tie_effect.get(key, 0)) for key in ("verglichen", "spitze_geaendert", "top10_andere_aktien", "top10_andere_reihenfolge", "reihenfolge_geaendert")}
            same = all(published.get(key) == value for key, value in own.items() if key in published)
            self.t.check("methodenwechsel_wirkung", same and comparison["paare"].get("nicht_mehr_bewertet") == 0 and comparison["paare"].get("neu_bewertet") == 0, f"Server {[published.get(k) for k in own]} eigen {list(own.values())}")
            info["pruefungen"] = self.t.as_dict()
            info["abweichungen"] = self.t.total_failed
        if self.intraday:
            info["mit_schlusskurs_davor"] = sum(1 for end in self.series_end.values() if end < self.cutoff)
        return info


# ------------------------------------------------------------------ Zwischenstand gegen Stand mit Schlusskursen


def compare_intraday(z: Nachrechnung, official: Nachrechnung) -> dict:
    """Aktien, die im Zwischenstand mit dem letzten Schlusskurs zählen: dieselben Werte wie im Stand mit Schlusskursen."""
    t = Tally()
    index = {isin: k for k, isin in enumerate(official.isins)}
    for i, end in z.series_end.items():
        if end >= z.cutoff or end != official.cutoff:
            continue
        j = index.get(z.isins[i])
        if j is None:
            continue
        for h in range(1, 91):
            mine, theirs = z.values.get(h, {}).get(i), official.values.get(h, {}).get(j)
            if mine is None and theirs is None:
                continue
            same = mine is not None and theirs is not None and all(mine[k] == theirs[k] for k in ("start", "n", "n_exp", "p0", "p1", "r", "r2", "end"))
            t.check("gleiche_werte_wie_mit_schlusskursen", same, f"h={h}")
    return {"pruefungen": t.as_dict(), "abweichungen": t.total_failed}


# ------------------------------------------------------------------ Vergleich mit ChatGPT


def _digest(*parts) -> str:
    return hashlib.sha256("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()


def cell_digests(salt: str, group: str, h: int, w: int, isins: list[str]) -> dict:
    """Prüfwerte einer Rangliste ohne Namen: Anzahl, erste 5/10 Plätze (Reihenfolge), die 10 ersten als Menge und die
    ersten K Plätze (K = 4 … 10). SHA-256 mit Salz; schon vier Plätze lassen sich nicht durch Ausprobieren erraten."""
    out: dict = {"gruppe": group, "tage": int(h), "gewicht": int(w), "anzahl": len(isins)}
    if not isins:
        return out
    if len(isins) >= 5:
        out["top5"] = _digest(salt, group, h, w, "top5", ",".join(isins[:5]))
    if len(isins) >= 10:
        out["top10"] = _digest(salt, group, h, w, "top10", ",".join(isins[:10]))
        out["menge10"] = _digest(salt, group, h, w, "menge10", ",".join(sorted(isins[:10])))
    out["anfang"] = {str(k): _digest(salt, group, h, w, f"anfang{k}", ",".join(isins[:k])) for k in range(4, 11) if len(isins) >= k}
    return out


def depot_lists(isins_of: list[str], cells: list[list[int]]) -> dict[str, list[str]]:
    """Musterdepots wie in der App (Bericht 1–30, A und B): „Sieger“ nach Platz 1, Top 3, Top 10, ISIN;
    „Top 10“ nach Top-10-Nennungen, Platz 1, Top 3, ISIN. ``cells`` = Reihenfolgen der gezählten Ranglisten."""
    n1: Counter = Counter()
    n3: Counter = Counter()
    n10: Counter = Counter()
    for order in cells:
        for pos, i in enumerate(order[:10]):
            n1[int(i)] += pos == 0
            n3[int(i)] += pos < 3
            n10[int(i)] += 1
    wins = sorted((i for i in n10 if n1[i] > 0), key=lambda i: (-n1[i], -n3[i], -n10[i], isins_of[i]))
    tops = sorted(n10, key=lambda i: (-n10[i], -n1[i], -n3[i], isins_of[i]))
    return {"sieger": [isins_of[i] for i in wins], "top10": [isins_of[i] for i in tops]}


def depot_digests(salt: str, lists: dict[str, list[str]]) -> dict[str, str]:
    return {
        "sieger_menge": _digest(salt, "depot", "sieger_menge", ",".join(sorted(lists["sieger"][:10]))),
        "sieger_reihenfolge": _digest(salt, "depot", "sieger_reihenfolge", ",".join(lists["sieger"][:10])),
        "top10_menge": _digest(salt, "depot", "top10_menge", ",".join(sorted(lists["top10"][:10]))),
        "top10_reihenfolge": _digest(salt, "depot", "top10_reihenfolge", ",".join(lists["top10"][:10])),
        "top20_reihenfolge": _digest(salt, "depot", "top20_reihenfolge", ",".join(lists["top10"][:20])),
        "sieger_anfang": {str(k): _digest(salt, "depot", f"sieger_anfang{k}", ",".join(lists["sieger"][:k])) for k in range(4, 11) if len(lists["sieger"]) >= k},
        "top10_anfang": {str(k): _digest(salt, "depot", f"top10_anfang{k}", ",".join(lists["top10"][:k])) for k in range(4, 21) if len(lists["top10"]) >= k},
    }


def compare_chatgpt(stand: Nachrechnung, path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data["stichtag"] != _iso(stand.cutoff):
        return {"hinweis": f"Stichtag {data['stichtag']} passt nicht zum Stand ({_iso(stand.cutoff)})"}
    salt = data["salz"]
    rows = data["ranglisten"]
    result = Counter()
    breakdown: dict[str, Counter] = {}
    prefix_lengths: Counter = Counter()
    count_diffs: list[int] = []
    app_only = 0
    for row in rows:
        group, h, w = row["gruppe"], int(row["tage"]), int(row["gewicht"])
        order = stand._order(group, h, w)
        ours = cell_digests(salt, group, h, w, [stand.isins[int(i)] for i in order])
        if not row["anzahl"]:
            app_only += 1 if ours["anzahl"] else 0
            continue
        result["ranglisten"] += 1
        result["anzahl_gleich"] += ours["anzahl"] == row["anzahl"]
        count_diffs.append(ours["anzahl"] - row["anzahl"])
        part = f"{group} {'0/100' if w == 0 else 'gewichtet'}"
        breakdown.setdefault(part, Counter())["ranglisten"] += 1
        for key, label in (("top5", "platz_1_5_gleich"), ("top10", "platz_1_10_gleich"), ("menge10", "gleiche_10_aktien")):
            same = bool(row.get(key)) and ours.get(key) == row.get(key)
            result[label] += same
            breakdown[part][label] += same
        breakdown[part]["anzahl_app_minus_chatgpt"] += ours["anzahl"] - row["anzahl"]
        longest = max([k for k in range(4, 11) if (row.get("anfang") or {}).get(str(k)) and (ours.get("anfang") or {}).get(str(k)) == row["anfang"][str(k)]] or [0])
        prefix_lengths[longest] += 1

    def vectors(groups: tuple[str, ...], weights: tuple[int, ...]) -> dict:
        n1: Counter = Counter()
        n10: Counter = Counter()
        cells = 0
        for group in groups:
            for h in range(1, 31):
                for w in weights:
                    order = stand._order(group, h, w)
                    if not order:
                        continue
                    cells += 1
                    n1[int(order[0])] += 1
                    for i in order[:10]:
                        n10[int(i)] += 1
        return {"zellen": cells, "erste_plaetze": sorted(n1.values(), reverse=True)[:20], "top10": sorted(n10.values(), reverse=True)[:20]}

    combos = {
        "A · 0/100, 40/60, 50/50, 60/40": (("A",), (0, 40, 50, 60)),
        "B · 0/100, 40/60, 50/50, 60/40": (("B",), (0, 40, 50, 60)),
        "A+B · 0/100, 40/60, 50/50, 60/40": (("A", "B"), (0, 40, 50, 60)),
        "A+B · 0/100": (("A", "B"), (0,)),
        "A+B · 40/60, 50/50, 60/40": (("A", "B"), (40, 50, 60)),
    }
    frequency = {}
    for label, (groups, weights) in combos.items():
        ours = vectors(groups, weights)
        theirs = (data.get("haeufigkeit_1_30") or {}).get(label)
        frequency[label] = {"app": ours, "chatgpt": theirs, "gleich": theirs is not None and ours == theirs}
    # Häufigster Sieger je Gewichtung (alle elf, 1–30 Tage, A+B): Muster der Sieger ohne Namen (gleicher Buchstabe = gleiche Aktie)
    letters: dict[int, str] = {}
    pattern = []
    for w in WEIGHTS:
        wins: Counter = Counter()
        for group in ("A", "B"):
            for h in range(1, 31):
                order = stand._order(group, h, w)
                if order:
                    wins[int(order[0])] += 1
        if not wins:
            pattern.append({"gewicht": f"{w}/{100 - w}", "sieger": None})
            continue
        top = min(wins.items(), key=lambda kv: (-kv[1], stand.isins[kv[0]]))
        letter = letters.setdefault(top[0], "ABCDEFGHIJK"[len(letters)])
        pattern.append({"gewicht": f"{w}/{100 - w}", "sieger": letter, "erste_plaetze": top[1], "ranglisten": sum(wins.values())})
    # Musterdepots „Bericht 1–30“ (0/100, 40/60, 50/50, 60/40; A und B): gleiche 10 Aktien, gleiche Reihenfolge
    depots = {}
    expected = (data.get("depots") or {}).get("bericht_1_30_ab")
    if expected:
        cells = [stand._order(g, h, w) for g in ("A", "B") for h in range(1, 31) for w in (0, 40, 50, 60)]
        ours = depot_digests(salt, depot_lists(stand.isins, [c for c in cells if c]))
        depots = {key: ours[key] == value for key, value in expected.items() if not key.endswith("_anfang")}
        for key in ("sieger_anfang", "top10_anfang"):
            same = [int(k) for k, value in (expected.get(key) or {}).items() if (ours.get(key) or {}).get(k) == value]
            depots[key.replace("_anfang", "_gleiche_spitze")] = max(same or [0])
    return {
        "quelle": data.get("beschreibung", "")[:160],
        "musterdepots_bericht_1_30": depots,
        "stichtag": data["stichtag"],
        "ranglisten_chatgpt": result["ranglisten"],
        "anzahl_aktien_gleich": result["anzahl_gleich"],
        "anzahl_unterschied": {"min": min(count_diffs) if count_diffs else 0, "max": max(count_diffs) if count_diffs else 0, "median": float(np.median(count_diffs)) if count_diffs else 0.0},
        "platz_1_5_gleich": result["platz_1_5_gleich"],
        "platz_1_10_gleich": result["platz_1_10_gleich"],
        "gleiche_10_aktien": result["gleiche_10_aktien"],
        "gleiche_spitze_laenge": {str(k): prefix_lengths[k] for k in sorted(prefix_lengths)},
        "je_gruppe": {part: dict(values) for part, values in sorted(breakdown.items())},
        "nur_in_der_app_berechnet": app_only,
        "kennzahlen_chatgpt": data.get("kennzahlen"),
        "haeufigkeit_1_30": frequency,
        "haeufigster_sieger_je_gewichtung": pattern,
    }


# ------------------------------------------------------------------ Quellen


def _iso(day: int) -> str:
    import datetime as dt

    return (dt.date(1970, 1, 1) + dt.timedelta(days=int(day))).isoformat()


def _http(url: str, token: str | None = None, accept: str | None = None, attempts: int = 4) -> bytes:
    for attempt in range(attempts):
        request = urllib.request.Request(url, headers={"User-Agent": "tr-aktienvergleich-nachrechnung"})
        if token and url.startswith("https://api.github.com/"):
            request.add_header("Authorization", f"Bearer {token}")
        if accept:
            request.add_header("Accept", accept)
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                return response.read()
        except OSError:
            if attempt == attempts - 1:
                raise
            time.sleep(2 + 3 * attempt)
    raise RuntimeError("unreachable")


def _extract(tar_bytes: bytes, target: Path, sid: str) -> Path:
    import io

    with tarfile.open(fileobj=io.BytesIO(tar_bytes)) as archive:
        archive.extractall(target, filter="data")
    folder = target / sid
    return folder if folder.is_dir() else target


def load_release_stands(repo: str, token: str | None, temp: Path, wanted_cutoff: str | None) -> tuple[dict, list[tuple[str, Path]]]:
    base = APP_URL.rstrip("/") + "/"
    status = json.loads(_http(base + "data/status.json"))
    descriptor = json.loads(_http(base + "data/crypto.json"))
    release = json.loads(_http(f"https://api.github.com/repos/{repo}/releases/tags/datenstand", token))
    assets = {a["name"]: a for a in release.get("assets", [])}
    ids = []
    for sid in (status.get("latest_official_snapshot_id"), status.get("latest_snapshot_id")):
        if sid and sid not in ids:
            ids.append(sid)
    if wanted_cutoff and not any(sid.startswith(wanted_cutoff + "_") and "_z" not in sid for sid in ids):
        candidates = sorted(
            (a for name, a in assets.items() if name.startswith(f"site-{wanted_cutoff}_") and "_z" not in name),
            key=lambda a: a["updated_at"],
        )
        if candidates:
            ids.append(candidates[-1]["name"][len("site-") : -len(".tar")])
    stands = []
    for sid in ids:
        asset = assets.get(f"site-{sid}.tar")
        if asset is None:
            print(f"::warning title=Nachrechnung::Archiv für einen Stand fehlt im Release (Stand {sid})")
            continue
        data = _http(asset["browser_download_url"])
        stands.append((sid, _extract(data, temp / sid, sid)))
    return {"status": status, "descriptor": descriptor}, stands


STAND_ID = re.compile(r"^\d{4}-\d{2}-\d{2}_[0-9a-f]{8}(_z\d+)?$")


def stand_id(text: str) -> str:
    """Stand-ID wie im Release (z. B. 2026-10-12_9820e6d9) – nur dieses Format wird angenommen."""
    if not STAND_ID.match(text):
        raise argparse.ArgumentTypeError(f"keine Stand-ID: {text!r}")
    return text


def load_explicit_stands(repo: str, token: str | None, temp: Path, ids: list[str], with_evidence: bool) -> tuple[dict, list[tuple[str, Path]], dict[str, Path], dict]:
    """Bestimmte Stände aus dem Release „datenstand“ (ab 1.18.1), auf Wunsch mit ihrem Prüfnachweis. Rückgabe zusätzlich die
    Zeitpunkte, zu denen GitHub die Archive angelegt hat (belegen, dass es die damals veröffentlichten sind)."""
    base = APP_URL.rstrip("/") + "/"
    status = json.loads(_http(base + "data/status.json"))
    descriptor = json.loads(_http(base + "data/crypto.json"))
    release = json.loads(_http(f"https://api.github.com/repos/{repo}/releases/tags/datenstand", token))
    assets = {a["name"]: a for a in release.get("assets", [])}
    stands, evidences, created = [], {}, {}
    for sid in ids:
        asset = assets.get(f"site-{sid}.tar")
        if asset is None:
            print(f"::error title=Nachrechnung::Archiv für Stand {sid} fehlt im Release")
            continue
        created[sid] = {"archiv_angelegt_utc": asset.get("created_at"), "archiv_geaendert_utc": asset.get("updated_at")}
        stands.append((sid, _extract(_http(asset["browser_download_url"]), temp / sid, sid)))
        if with_evidence:
            proof = assets.get(f"evidence-{sid}.tra")
            if proof is None:
                print(f"::error title=Nachrechnung::Prüfnachweis für Stand {sid} fehlt im Release")
                continue
            created[sid]["nachweis_angelegt_utc"] = proof.get("created_at")
            path = temp / f"evidence-{sid}.tra"
            path.write_bytes(_http(proof["browser_download_url"]))
            evidences[sid] = path
    return {"status": status, "descriptor": descriptor}, stands, evidences, created


def load_evidence(path: Path, key: crypto.KeyMaterial | None, sid: str) -> dict:
    """Prüfnachweis entschlüsseln und lesen – eigene, kurze Umsetzung (tar.gz mit NPZ, ohne Pickle)."""
    import io

    plain = crypto.unpack(path.read_bytes(), key, f"archive/evidence-{sid}.tra")
    with tarfile.open(fileobj=io.BytesIO(plain), mode="r:gz") as archive:
        member = archive.extractfile("kennzahlen_und_eingaben.npz")
        if member is None:
            return {}
        with np.load(io.BytesIO(member.read()), allow_pickle=False) as npz:
            return {name: npz[name] for name in npz.files}


def load_site_stands(site: Path) -> tuple[dict, list[tuple[str, Path]]]:
    status = json.loads((site / "data" / "status.json").read_text(encoding="utf-8"))
    descriptor = json.loads((site / "data" / "crypto.json").read_text(encoding="utf-8"))
    ids = []
    for sid in (status.get("latest_official_snapshot_id"), status.get("latest_snapshot_id")):
        if sid and sid not in ids:
            ids.append(sid)
    return {"status": status, "descriptor": descriptor}, [(sid, site / "data" / "snapshots" / sid) for sid in ids]


def key_for(descriptor: dict) -> crypto.KeyMaterial | None:
    if not descriptor.get("enabled"):
        return None
    passphrase = os.environ.get("DATA_PASSPHRASE") or ""
    if not passphrase:
        raise SystemExit("DATA_PASSPHRASE fehlt – der Datenstand ist verschlüsselt")
    return crypto.verify_descriptor(descriptor, passphrase)


def run(meta: dict, stands: list[tuple[str, Path]], vergleich: Path | None, evidences: dict[str, Path] | None = None) -> dict:
    key = key_for(meta["descriptor"])
    results: dict[str, Nachrechnung] = {}
    report: dict = {"staende": []}
    for sid, folder in stands:
        check = Nachrechnung(Stand(folder, sid, key))
        if evidences is not None:
            path = evidences.get(sid)
            check.evidence = load_evidence(path, key, sid) if path is not None else {}
        report["staende"].append(check.run())
        results[sid] = check
    official = [c for c in results.values() if not c.intraday]
    intraday = [c for c in results.values() if c.intraday]
    if official and intraday:
        latest_official = max(official, key=lambda c: c.cutoff)
        report["zwischenstand_gegen_schlusskurse"] = compare_intraday(intraday[0], latest_official)
    if vergleich is not None:
        data = json.loads(vergleich.read_text(encoding="utf-8"))
        matching = [c for c in official if _iso(c.cutoff) == data["stichtag"]]
        report["chatgpt"] = compare_chatgpt(matching[-1], vergleich) if matching else {"hinweis": f"kein Stand mit Stichtag {data['stichtag']} gefunden"}
    failed = sum(s["abweichungen"] for s in report["staende"]) + (report.get("zwischenstand_gegen_schlusskurse") or {}).get("abweichungen", 0)
    report["abweichungen"] = failed
    report["bekannte_fehler_frueherer_versionen"] = sum(v["anzahl"] for s in report["staende"] for v in (s.get("bekannte_fehler") or {}).values())
    report["ergebnis"] = "bestanden" if failed == 0 else "abweichungen"
    return report


def fix_note(stand: dict, report: dict) -> str:
    """Hinweis zu einem Stand mit bekannten Fehlern (ab 1.18): Ist die Ursache jedes Fehlers in der aktuellen Version behoben –
    mit welchem Beleg –, und welche beabsichtigten Methodenänderungen kamen danach (keine Fehler)?"""
    known = stand.get("bekannte_fehler") or {}
    cur = stand.get("aktuelle_version") or {}
    parts = []
    if "gleichstand_rundung" in known:
        total, fixed, still = cur.get("bekannte_faelle", 0), cur.get("bekannte_faelle_richtig", 0), cur.get("bekannte_faelle_offen", 0)
        parts.append(
            f"gleichstand_rundung – {'behoben' if total and not still and total == known['gleichstand_rundung']['anzahl'] else 'NICHT belegt'}: "
            f"Rechenkern der aktuellen Version (Software {cur.get('software')}) auf den Werten dieses Stands ordnet {fixed} von {total} "
            f"Fehlerfällen exakt ({still} offen); {cur.get('gleich', 0)} von {cur.get('ranglisten', 0)} Ranglisten gleich der eigenen Rechnung"
        )
    if "reihe_vorhanden" in known:
        newer = [
            s for s in report.get("staende", [])
            if s is not stand and parse_version(s.get("software")) and parse_version(s.get("software")) >= KNOWN_ISSUES["reihe_vorhanden"]["behoben_in"]
        ]
        if newer:
            latest = max(newer, key=lambda s: s["stichtag"])
            flags = latest.get("kursreihe_kennzeichen") or {}
            ok = not flags.get("mit_kennzeichen")
            parts.append(
                f"reihe_vorhanden – {'behoben' if ok else 'NICHT behoben'}: Stand {latest['stichtag']} (Software {latest.get('software')}) "
                f"hat {flags.get('ohne_gueltigen_kurs', 0)} Aktien ohne gültigen Kurs, davon {flags.get('mit_kennzeichen', 0)} mit Kennzeichen"
            )
        else:
            parts.append("reihe_vorhanden – kein neuerer Stand in dieser Prüfung, Beleg nur durch den Unit-Test")
    changes = "; ".join(f"{c['methode']}: {c['aenderung']}" for c in stand.get("methodenaenderungen_danach") or [])
    return (
        f"::notice title=Stand {stand['stichtag']}: Fehlerursachen und Methodenänderungen::"
        f"Ursachen in der aktuellen Version: {' | '.join(parts) if parts else '–'}. "
        f"Beabsichtigte Methodenänderungen seit {stand.get('methode')} (keine Fehler; der Stand bleibt unverändert): {changes or 'keine'}."
    )


COMPLETENESS = {"vollstaendig": "vollständig", "teilstand": "Teilstand"}


def evidence_note(stand: dict) -> str:
    """Ergebnis des Prüfnachweises als eigener Hinweis (ab 1.18.1) – nur Zählwerte und Zeitpunkte."""
    p = stand.get("nachweis") or {}
    ok = (
        bool(p.get("aktienliste_gleich"))
        and p.get("kurse_verglichen", 0) > 0
        and p.get("kurse_gleich") == p.get("kurse_verglichen")
        and p.get("renditen_gleich") == p.get("renditen_verglichen")
        and p.get("r2_gleich") == p.get("r2_verglichen")
    )
    return (
        f"::{'notice' if ok else 'error'} title=Originalstand {stand['snapshot_id']} gegen den Prüfnachweis des damaligen Laufs::"
        f"Originaldaten der App (nicht des Ausgangsmodells): Archiv angelegt {stand.get('archiv_angelegt_utc') or '–'}, Prüfnachweis angelegt "
        f"{stand.get('nachweis_angelegt_utc') or '–'}, Stand berechnet {stand.get('berechnet_utc') or '–'} ({COMPLETENESS.get(stand.get('vollstaendigkeit'), stand.get('vollstaendigkeit') or '–')}, Software {stand.get('software')}). "
        f"Aktienliste gleich: {'ja' if p.get('aktienliste_gleich') else 'nein'}; Schlusskurse {p.get('kurse_gleich', 0)} von {p.get('kurse_verglichen', 0)} gleich den "
        f"damaligen Eingangsreihen (nur im Stand {p.get('tage_nur_im_stand', 0)}, nur im Nachweis {p.get('tage_nur_im_nachweis', 0)}); Renditen {p.get('renditen_gleich', 0)} von "
        f"{p.get('renditen_verglichen', 0)}, R² {p.get('r2_gleich', 0)} von {p.get('r2_verglichen', 0)} gleich den damals gerechneten. Urteil: "
        + ("veröffentlichter Stand = damaliger Lauf" if ok else "NICHT belegt")
    )


def annotations(report: dict) -> list[str]:
    """Hinweise für die Laufübersicht – nur Zählwerte. Höchstens etwa acht Zeilen: GitHub zeigt je Schritt nur zehn
    Hinweise und zehn Fehler an (weitere fallen still weg)."""
    lines = []
    for stand in report["staende"]:
        checks = stand["pruefungen"]
        total = sum(v["geprueft"] for v in checks.values())
        bad = stand["abweichungen"]
        kind = "Zwischenstand" if stand["art"] == "zwischenstand" else "Stand mit Schlusskursen"
        extra = f", davon mit Schlusskurs davor gerechnet: {stand['mit_schlusskurs_davor']} Aktien" if "mit_schlusskurs_davor" in stand else ""
        skipped = (stand.get("nicht_nachrechenbar") or {}).get("umsatz_usd_ohne_wechselkursdatei")
        note = f"; Ø Tagesumsatz von {skipped} Aktien in anderer Währung als USD nur in Landeswährung nachgerechnet (Stand ohne Wechselkursdatei, die gibt es seit 1.9)" if skipped else ""
        failed = "; ".join(f"{name} {v['abweichend']} von {v['geprueft']} ({', '.join(v.get('beispiele', [])[:2])})" for name, v in checks.items() if v["abweichend"])
        diagnosis = "; ".join(f"Ursachensuche {topic}: {json.dumps(values, ensure_ascii=False)}" for topic, values in (stand.get("diagnose") or {}).items())
        known = stand.get("bekannte_fehler") or {}
        known_count = sum(v["anzahl"] for v in known.values())
        # ab 1.18: exakte gegen Gleitkomma-Reihenfolge auf den Werten dieses Stands (nur Zählwerte); in Ständen ab
        # ranking-11w-v3 ist das die Wirkung des Methodenwechsels, die die Prüfung „methodenwechsel_wirkung“ mit dem
        # Manifest vergleicht
        effect = stand.get("gleichstand_wirkung") or {}
        tie_note = (
            f"; Gleichstand ({stand.get('ranglistenversion')}): exakt statt Gleitkomma anders – Platz 1 {effect.get('spitze_geaendert', 0)}, "
            f"erste 10 {effect.get('top10_andere_aktien', 0)} (Aktien) bzw. {effect.get('top10_andere_reihenfolge', 0)} (nur Reihenfolge), "
            f"irgendein Platz {effect.get('reihenfolge_geaendert', 0)} von {effect.get('verglichen', 0)} Ranglisten"
            + (" – wie im Manifest" if checks.get("methodenwechsel_wirkung", {}).get("geprueft") and not checks["methodenwechsel_wirkung"]["abweichend"] else "")
            if effect
            else ""
        )
        # ab 1.18 zwei getrennte Urteile: „damalige Berechnung reproduziert“ (keine Rechenabweichung nach der Methode des
        # Stands) ist nicht dasselbe wie „fachlich korrekt“ (keine bekannten Fehler dieser Version)
        reproduced = "ja" if bad == 0 else "nein"
        correct = "nein" if bad or known_count else "ja"
        why = (
            f" – {known_count} bekannte Fehlerfälle ({', '.join(f'{v['anzahl']} × {name}' for name, v in known.items())}; siehe Warnungen)"
            if known_count
            else (" – Abweichungen siehe unten" if bad else " – keine bekannten Fehler dieser Version")
        )
        lines.append(
            f"::{'notice' if bad == 0 else 'error'} title=Nachrechnung {kind} {stand['stichtag']}::"
            f"Damalige Berechnung reproduziert: {reproduced} ({total} Prüfungen, {bad} Abweichungen). Fachlich korrekt: {correct}{why}. "
            f"{stand['aktien_mit_kursreihe']} Kursreihen, {stand['zeitraeume_in_ranglisten']} Zeiträume in Ranglisten{extra}; "
            f"gerechnet mit Software {stand.get('software')}, Methode {stand.get('methode')} ({stand['sekunden']} s){note}{tie_note}"
            + (f". Abweichungen: {failed}" if failed else "")
            + (f". {diagnosis}" if diagnosis else "")
        )
        proof = stand.get("nachweis")
        if proof is not None:
            lines.append(evidence_note(stand))
        if known_count:
            lines.append(fix_note(stand, report))
        for name, value in known.items():
            lines.append(
                f"::warning title=Nachrechnung {kind} {stand['stichtag']}: bekannter Fehler von Software {stand.get('software')}::"
                f"{value['anzahl']} Fälle „{name}“ – damaliges Verhalten bestätigt, fachlich falsch: {value['fehler']}. "
                f"Geprüfte Bedingung: {value['bedingung']}. Wirkung: {value['wirkung']}. Behoben in {value['behoben_in']} ({value['korrektur']}). "
                "Der Stand bleibt unverändert als Originalreferenz erhalten."
            )
    z = report.get("zwischenstand_gegen_schlusskurse")
    if z:
        value = z["pruefungen"].get("gleiche_werte_wie_mit_schlusskursen", {"geprueft": 0, "abweichend": 0})
        lines.append(
            f"::{'notice' if z['abweichungen'] == 0 else 'error'} title=Zwischenstand mit Schlusskurs davor::"
            f"{value['geprueft'] - value['abweichend']} von {value['geprueft']} Zeiträumen gleich wie im Stand mit Schlusskursen"
        )
    g = report.get("chatgpt")
    if g and "ranglisten_chatgpt" in g:
        diff = g["anzahl_unterschied"]
        parts = []
        for part, values in (g.get("je_gruppe") or {}).items():
            n = values.get("ranglisten", 0)
            parts.append(
                f"{part}: {n} Ranglisten, 1–5 gleich {values.get('platz_1_5_gleich', 0)}, 1–10 gleich {values.get('platz_1_10_gleich', 0)}, "
                f"Aktien App minus ChatGPT Ø {round(values.get('anzahl_app_minus_chatgpt', 0) / n) if n else 0}"
            )
        lines.append(
            f"::notice title=Vergleich mit ChatGPT ({g['stichtag']}) – Ranglisten::{g['ranglisten_chatgpt']} Ranglisten: Anzahl Aktien gleich {g['anzahl_aktien_gleich']} "
            f"(App minus ChatGPT: kleinster {diff['min']}, Median {diff['median']}, größter {diff['max']}), "
            f"Plätze 1–5 gleich {g['platz_1_5_gleich']}, Plätze 1–10 gleich {g['platz_1_10_gleich']}, gleiche 10 Aktien {g['gleiche_10_aktien']}; "
            f"gleiche Spitze (Plätze: Anzahl): {g['gleiche_spitze_laenge']}. " + " | ".join(parts)
        )
        freq = []
        for label, value in g["haeufigkeit_1_30"].items():
            app, theirs = value["app"], value["chatgpt"] or {}
            freq.append(
                f"{label}: {'gleich' if value['gleich'] else 'verschieden'} – Platz 1 App {app['erste_plaetze'][:6]} / ChatGPT {(theirs.get('erste_plaetze') or [])[:6]}, "
                f"Top 10 App {app['top10'][:6]} / ChatGPT {(theirs.get('top10') or [])[:6]}"
            )
        lines.append("::notice title=Vergleich mit ChatGPT – Häufigkeit 1–30::" + " | ".join(freq))
        pattern = " ".join(f"{p['gewicht']}:{p['sieger'] or '–'}{'(' + str(p['erste_plaetze']) + ')' if p.get('sieger') else ''}" for p in g["haeufigster_sieger_je_gewichtung"])
        depot = ""
        if g.get("musterdepots_bericht_1_30"):
            d = g["musterdepots_bericht_1_30"]
            word = lambda ok: "gleich" if ok else "verschieden"
            depot = (
                f" | Musterdepots Bericht 1–30 (A+B): „Sieger“ Aktien {word(d['sieger_menge'])}, Reihenfolge {word(d['sieger_reihenfolge'])}, gleiche Spitze {d.get('sieger_gleiche_spitze')}; "
                f"„Top 10“ Aktien {word(d['top10_menge'])}, Reihenfolge {word(d['top10_reihenfolge'])}, gleiche Spitze {d.get('top10_gleiche_spitze')}; Top 20 {word(d['top20_reihenfolge'])}"
            )
        lines.append(f"::notice title=Vergleich mit ChatGPT – Sieger und Depots::Häufigster Sieger je Gewichtung (A+B, 1–30; gleicher Buchstabe = gleiche Aktie): {pattern}{depot}")
    elif g:
        lines.append(f"::warning title=Vergleich mit ChatGPT::{g.get('hinweis')}")
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--quelle", choices=("release", "site"), default="release")
    parser.add_argument("--site", type=Path, help="lokaler Website-Ordner (mit --quelle site)")
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", "szymeklh87-commits/tr-aktienvergleich"))
    parser.add_argument("--vergleich", type=Path, help="Vergleichswerte (z. B. tests/live/vergleich/chatgpt_2026-10-13.json)")
    parser.add_argument("--bericht", type=Path, help="Ergebnis als JSON (nur Zählwerte)")
    parser.add_argument("--stand", type=stand_id, action="append", default=[], help="bestimmter Stand aus dem Release (mehrfach möglich, ab 1.18.1)")
    parser.add_argument("--nachweis", action="store_true", help="mit --stand: Prüfnachweis des damaligen Laufs mitprüfen")
    args = parser.parse_args(argv)
    with tempfile.TemporaryDirectory(prefix="nachrechnen-") as temp:
        wanted = json.loads(args.vergleich.read_text(encoding="utf-8"))["stichtag"] if args.vergleich else None
        evidences = None
        created: dict = {}
        if args.stand:
            meta, stands, evidences, created = load_explicit_stands(args.repo, os.environ.get("GITHUB_TOKEN"), Path(temp), args.stand, args.nachweis)
            evidences = evidences if args.nachweis else None
        elif args.quelle == "site":
            meta, stands = load_site_stands(args.site)
        else:
            meta, stands = load_release_stands(args.repo, os.environ.get("GITHUB_TOKEN"), Path(temp), wanted)
        report = run(meta, stands, args.vergleich, evidences)
        for stand in report["staende"]:
            stand.update(created.get(stand["snapshot_id"], {}))
    if args.bericht:
        args.bericht.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    for line in annotations(report):
        print(line)
    return 0 if report["ergebnis"] == "bestanden" else 1


if __name__ == "__main__":
    sys.exit(main())
