"""Eingänge aus der App für den Spielgeld-Robo (Gesamtauftrag, Abschnitte 4, 7A.5, 29.3, 31): eigene Regel testen, Test
beenden, Käufe pausieren und fortsetzen, offene Käufe stornieren.

Weg (wie „Jetzt aktualisieren“, ab 1.21): Die App verschlüsselt den Eingang mit dem Datenschlüssel (AAD
``eingang/<kennung>``) und startet den Workflow ``spielgeld-eingang.yml``. Der Lauf prüft (``annehmen``): entschlüsselbar,
Schema, Kennung, Alter höchstens 20 Minuten (Schutz vor Wiederholung), erlaubte Art, Regel nach ``regeln.pruefen``. Nur ein
angenommener Eingang kommt verschlüsselt auf den Branch ``spielgeld-eingang`` (Ordner ``eingang/``); daneben liegt immer ein
verschlüsseltes Ergebnis (``ergebnis/<kennung>.bin``) für die App. Öffentlich sichtbar sind nur Zufallskennung, Zeiten und
Größen.

Verbindlich wirksam wird ein Eingang erst im **täglichen Lauf** (``verarbeiten``): einziger Schreiber des Zustands, jede
Kennung genau einmal (``ap_eingang``), erneute Prüfung mit dem dann gültigen Katalog. Eine neue Regel startet in einem eigenen
Forschungsdepot ``e-…`` mit neuer Test-Kennung; eine neue Version derselben Regel archiviert den alten Test (nichts wird
gelöscht). Die zentralen Risikogrenzen gelten unverändert – kein Eingang kann sie erhöhen, Echtgeld gibt es nicht.
"""

from __future__ import annotations

import base64
import binascii
import datetime as dt
import hashlib
import json
import re
import sqlite3
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from ..util import crypto
from ..util.timeutil import UTC, day_to_date, parse_iso_utc
from . import motor, regeln, speicher

SCHEMA = "tr-spielgeld-eingang/1"
SCHEMA_ERGEBNIS = "tr-spielgeld-eingang-ergebnis/1"
BRANCH = "spielgeld-eingang"
ORDNER_EINGANG = "eingang"
ORDNER_ERGEBNIS = "ergebnis"
KENNUNG_RE = re.compile(r"^k([0-9a-z]{6,8})-([0-9a-z]{16})$")
ARTEN = ("regel_testen", "regel_beenden", "pausieren", "fortsetzen", "offene_kaeufe_stornieren", "positionen_schliessen", "neuer_test",
         "pilot_einrichten")
EINRICHTUNG = "pilot:einrichtung"  # Schlüssel in ap_zustand
TESTNUMMER = "pilot:testnummer"
MAX_TEXT = 60_000  # Base64 der verschlüsselten Nutzlast (Workflow-Eingaben sind begrenzt)
MAX_ALTER_S = 20 * 60
MAX_ZUKUNFT_S = 5 * 60
AUFBEWAHRUNG_S = 30 * 24 * 3600  # bis der tägliche Lauf sicher abgeholt hat (auch über Feiertage)
PREFIX = "e-"


class EingangFehler(ValueError):
    def __init__(self, code: str, text: str):
        super().__init__(text)
        self.code = code
        self.text = text


@dataclass
class Eingang:
    kennung: str
    art: str
    erstellt: dt.datetime
    inhalt: dict
    regel: dict | None = None  # geprüfte, normalisierte Regel (nur „regel_testen“)
    hinweise: list[str] = field(default_factory=list)


def aad(kennung: str) -> str:
    return f"eingang/{kennung}"


def aad_ergebnis(kennung: str) -> str:
    return f"ergebnis/{kennung}"


def kennung_zeit(kennung: str) -> dt.datetime:
    m = KENNUNG_RE.match(kennung or "")
    if not m:
        raise EingangFehler("kennung_ungueltig", "Kennung hat nicht das erwartete Format")
    return dt.datetime.fromtimestamp(int(m.group(1), 36), tz=UTC)


def _b64(text: str) -> bytes:
    cleaned = (text or "").strip().replace("-", "+").replace("_", "/")
    cleaned += "=" * (-len(cleaned) % 4)
    try:
        return base64.b64decode(cleaned, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise EingangFehler("nutzlast_unlesbar", "Nutzlast ist kein Base64") from exc


def entschluesseln(blob: bytes, kennung: str, key: crypto.KeyMaterial | None) -> dict:
    kennung_zeit(kennung)
    if key is None:
        raise EingangFehler("kein_schluessel", "Ohne Datenschlüssel lassen sich Eingänge nicht prüfen")
    try:
        plain = crypto.unpack(blob, key, aad(kennung))
    except crypto.ContainerError as exc:
        raise EingangFehler("nicht_entschluesselbar", "Eingang ließ sich nicht entschlüsseln (Schlüssel oder Kennung passt nicht)") from exc
    if len(plain) > 200_000:
        raise EingangFehler("zu_gross", "Eingang ist entpackt zu groß")
    try:
        data = json.loads(plain.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EingangFehler("unlesbar", "Eingang ist kein gültiges JSON") from exc
    if not isinstance(data, dict) or data.get("schema") != SCHEMA:
        raise EingangFehler("schema_falsch", "Eingang hat nicht das erwartete Schema")
    if data.get("kennung") != kennung:
        raise EingangFehler("kennung_passt_nicht", "Kennung im Eingang passt nicht")
    return data


def pruefen(data: dict, kennung: str, eintraege: dict, method, *, cfg=None, now: dt.datetime | None = None, max_alter_s: float | None = MAX_ALTER_S) -> Eingang:
    """Inhalt prüfen (Art, Felder, Regel). ``max_alter_s=None``: ohne Altersgrenze (täglicher Lauf; Doppelte verhindert
    dort ``ap_eingang``)."""
    created_by_id = kennung_zeit(kennung)
    created = parse_iso_utc(data.get("erstellt_utc")) if isinstance(data.get("erstellt_utc"), str) else None
    if created is None or abs((created - created_by_id).total_seconds()) > 120:
        raise EingangFehler("zeit_ungueltig", "Erstellzeit fehlt oder passt nicht zur Kennung")
    clock = now or dt.datetime.now(UTC)
    age = (clock - created).total_seconds()
    if max_alter_s is not None and age > max_alter_s:
        raise EingangFehler("zu_alt", "Eingang ist älter als 20 Minuten")
    if age < -MAX_ZUKUNFT_S:
        raise EingangFehler("zeit_ungueltig", "Erstellzeit liegt in der Zukunft")
    art = data.get("art")
    if art not in ARTEN:
        raise EingangFehler("art_unbekannt", "Unbekannte Art des Eingangs")
    inhalt = data.get("inhalt") or {}
    if not isinstance(inhalt, dict):
        raise EingangFehler("inhalt_ungueltig", "Inhalt muss ein Objekt sein")
    e = Eingang(kennung, art, created, inhalt)
    if art == "regel_testen":
        if set(inhalt) != {"regel"}:
            raise EingangFehler("inhalt_ungueltig", "„regel_testen“ braucht genau eine Regel")
        p = regeln.pruefen(inhalt["regel"], eintraege, method)
        if not p.gueltig:
            first = "; ".join(f"{f.pfad}: {f.text}" for f in p.fehler[:5])
            raise EingangFehler("regel_ungueltig", f"Regel ungültig – {first}")
        e.regel = p.regel
        e.hinweise = list(p.hinweise)
    elif art == "pilot_einrichten":
        from .profil import ProfilFehler, einrichtung_pruefen

        try:
            e.inhalt = einrichtung_pruefen(inhalt, float(cfg.depot.aktiver_anteil_max) if cfg is not None else 0.3)
        except ProfilFehler as exc:
            raise EingangFehler("einrichtung_ungueltig", str(exc)) from exc
    elif art == "regel_beenden":
        rid = inhalt.get("regel_id")
        if set(inhalt) != {"regel_id"} or not isinstance(rid, str) or not regeln.ID_RE.match(rid):
            raise EingangFehler("inhalt_ungueltig", "„regel_beenden“ braucht eine gültige Regel-ID")
    elif inhalt:
        raise EingangFehler("inhalt_ungueltig", f"„{art}“ hat keinen Inhalt")
    return e


def annehmen(text: str, kennung: str, key: crypto.KeyMaterial | None, eintraege: dict, method, now: dt.datetime | None = None, cfg=None) -> tuple[Eingang, bytes]:
    """Prüfung im Workflow ``spielgeld-eingang.yml``: Nutzlast als Base64-Text aus der Workflow-Eingabe."""
    if not text or len(text) > MAX_TEXT:
        raise EingangFehler("zu_gross", "Nutzlast fehlt oder ist zu groß")
    blob = _b64(text)
    data = entschluesseln(blob, kennung, key)
    return pruefen(data, kennung, eintraege, method, cfg=cfg, now=now), blob


def ergebnis_datei(out_dir: Path, kennung: str, key: crypto.KeyMaterial | None, *, angenommen: bool, code: str, text: str, art: str | None = None,
                   regel: str | None = None, now: dt.datetime | None = None) -> Path:
    """Verschlüsseltes Ergebnis für die App (ohne Schlüssel – nur bei ungültiger Kennung – wird keine Datei geschrieben)."""
    payload = {"schema": SCHEMA_ERGEBNIS, "kennung": kennung, "status": "angenommen" if angenommen else "abgelehnt", "code": code, "text": text,
               "art": art, "regel": regel, "geprueft_utc": (now or dt.datetime.now(UTC)).strftime("%Y-%m-%dT%H:%M:%SZ"),
               "wirksam": "mit dem nächsten täglichen Lauf" if angenommen else None}
    path = Path(out_dir) / f"{kennung}.bin"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(crypto.pack(json.dumps(payload, ensure_ascii=False).encode("utf-8"), key, aad_ergebnis(kennung)))
    return path


def prune_names(names: list[str], now: dt.datetime) -> list[str]:
    """Dateien älter als 30 Tage (Zeit aus der Kennung) und Fremdes – werden beim nächsten Ablegen entfernt."""
    old = []
    for name in names:
        m = re.match(rf"^({ORDNER_EINGANG}|{ORDNER_ERGEBNIS})/(k[0-9a-z]{{6,8}}-[0-9a-z]{{16}})\.bin$", name)
        if not m:
            old.append(name)
            continue
        try:
            created = kennung_zeit(m.group(2))
        except EingangFehler:
            old.append(name)
            continue
        if (now - created).total_seconds() > AUFBEWAHRUNG_S:
            old.append(name)
    return old


# ------------------------------------------------------------------------------------------------ Abholen im täglichen Lauf


def aus_ordner(root: Path) -> list[tuple[str, bytes]]:
    """Eingänge aus einem Ordner (DEMO und Tests; Aufbau wie der Branch)."""
    folder = Path(root) / ORDNER_EINGANG
    if not folder.is_dir():
        return []
    out = []
    for path in sorted(folder.glob("k*.bin")):
        if KENNUNG_RE.match(path.stem):
            out.append((path.stem, path.read_bytes()))
    return out


def aus_git(repository: str, token: str, *, server: str = "https://github.com", branch: str = BRANCH) -> list[tuple[str, bytes]]:
    """Eingänge vom Branch ``spielgeld-eingang`` (flacher Abruf mit dem Token des Laufs; das Token erscheint nie in einer Ausgabe)."""
    from ..jobs.kursaktualisierung import GitLieferkanal, _git

    channel = GitLieferkanal(repository, token, server=server, branch=branch, ordner=ORDNER_EINGANG, prune=prune_names, titel="Spielgeld-Eingang")
    try:
        env = channel._env()
        try:
            _git(["fetch", "-q", "--depth=1", "origin", branch], channel.work, env)
        except subprocess.CalledProcessError:
            return []  # Branch gibt es (noch) nicht
        names = _git(["ls-tree", "-r", "--name-only", "FETCH_HEAD"], channel.work, env).stdout.split()
        out = []
        for name in sorted(names):
            m = re.match(rf"^{ORDNER_EINGANG}/(k[0-9a-z]{{6,8}}-[0-9a-z]{{16}})\.bin$", name)
            if not m:
                continue
            blob = subprocess.run(["git", "show", f"FETCH_HEAD:{name}"], cwd=channel.work, env=env, check=True, capture_output=True, timeout=60).stdout
            out.append((m.group(1), blob))
        return out
    finally:
        channel.close()


# ------------------------------------------------------------------------------------------------ Verarbeiten (täglicher Lauf)


def _iso(now: dt.datetime) -> str:
    return now.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def eigene_depots(conn: sqlite3.Connection) -> list[tuple[motor.DepotDef, dict]]:
    return [(d, info) for d, info in speicher.depots(conn, nur_aktive=True) if d.id.startswith(PREFIX)]


def _depot_id(regel: dict) -> str:
    return f"{PREFIX}{regel['id'].removeprefix('r-')}-v{regel['version']}"


def _anwenden(conn: sqlite3.Connection, e: Eingang, *, cfg, D: int, synthetisch: bool, modus: str, now: dt.datetime) -> str:
    """Wirkung eines geprüften Eingangs; Rückgabe: Text für Journal und App. Der Aufrufer hält die Transaktion."""
    if e.art == "regel_testen":
        regel = e.regel
        assert regel is not None
        speicher.regel_speichern(conn, regel, "app", now)  # gleiche ID und Version mit anderem Inhalt → Fehler
        did = _depot_id(regel)
        if conn.execute("SELECT 1 FROM ap_depot WHERE id = ?", (did,)).fetchone() is not None:
            raise EingangFehler("schon_vorhanden", f"Regel {regel['id']}@{regel['version']} wird schon getestet – für Änderungen eine neue Version senden")
        archived = 0
        for d, _info in eigene_depots(conn):
            if any(s.regel["id"] == regel["id"] for s in d.strategien):
                speicher.depot_archivieren(conn, d.id, now)  # neue Version = neuer Test; der alte bleibt erhalten
                archived += 1
        capital = float(cfg.depot.demo_startkapital_eur)
        depot = motor.DepotDef(did, f"Eigene Regel: {regel['name']}", "forschung", capital, int(D), 1.0, (motor.StrategieDef(regel["id"], regel, 1.0),), None,
                               synthetisch, (regel.get("beschreibung") or "Eigene Regel aus der App") + " – eigenes Forschungsdepot mit Spielgeld")
        speicher.depot_anlegen(conn, depot, modus=modus, test_id=f"{did}@{day_to_date(int(D)).isoformat()}", jetzt=now)
        return f"Regel „{regel['name']}“ ({regel['id']}@{regel['version']}) wird ab dem Datenstand {day_to_date(int(D)).isoformat()} getestet" + (
            f"; {archived} älterer Test archiviert" if archived else "")
    if e.art == "pilot_einrichten":
        setup = dict(e.inhalt, kennung=e.kennung, eingerichtet_utc=_iso(now), ab_tag=int(D))
        conn.execute("INSERT INTO ap_zustand(schluessel, wert_json, aktualisiert_am) VALUES (?, ?, ?) "
                     "ON CONFLICT(schluessel) DO UPDATE SET wert_json = excluded.wert_json, aktualisiert_am = excluded.aktualisiert_am",
                     (EINRICHTUNG, json.dumps(setup, ensure_ascii=False, sort_keys=True), _iso(now)))
        p = e.inhalt["profil"]
        return (f"Einrichtung übernommen: {e.inhalt['startkapital_eur']:,.0f} EUR Spielgeld, {p['name']} ({p['welt'] * 100:.0f} % Welt / "
                f"{p['geldmarkt'] * 100:.0f} % Geldmarkt), aktiver Anteil höchstens {e.inhalt['aktiver_anteil'] * 100:.0f} % – "
                "das Pilotdepot und seine Vergleichsdepots starten als neuer Test").replace(",", ".")
    if e.art == "neuer_test":
        row = conn.execute("SELECT wert_json FROM ap_zustand WHERE schluessel = ?", (TESTNUMMER,)).fetchone()
        nummer = (int(json.loads(row[0])["nummer"]) if row else 1) + 1
        conn.execute("INSERT INTO ap_zustand(schluessel, wert_json, aktualisiert_am) VALUES (?, ?, ?) "
                     "ON CONFLICT(schluessel) DO UPDATE SET wert_json = excluded.wert_json, aktualisiert_am = excluded.aktualisiert_am",
                     (TESTNUMMER, json.dumps({"nummer": nummer, "kennung": e.kennung, "ab_tag": int(D)}), _iso(now)))
        return f"Neuer Test Nr. {nummer}: Pilotdepot und Vergleichsdepots starten neu; der bisherige Lauf bleibt in der Chronik"
    if e.art == "regel_beenden":
        rid = e.inhalt["regel_id"]
        hits = [d.id for d, _ in eigene_depots(conn) if any(s.regel["id"] == rid for s in d.strategien)]
        if not hits:
            raise EingangFehler("nicht_gefunden", f"Kein laufender Test der Regel {rid}")
        for did in hits:
            speicher.depot_archivieren(conn, did, now)
        return f"Test der Regel {rid} beendet (archiviert, nichts gelöscht)"
    # Pilotdepot(s): Automatik steuern – Schutzverkäufe (Stops) laufen immer weiter
    pilots = [d.id for d, info in speicher.depots(conn, nur_aktive=True) if d.art == "pilot" and not str(info.get("test_id", "")).startswith("historisch-")]
    if not pilots:
        raise EingangFehler("nicht_gefunden", "Kein aktives Pilotdepot")
    texts = []
    for did in pilots:
        z = speicher.zustand_laden(conn, did)
        if e.art == "pausieren":
            z.kaeufe_pausiert = True
            text = "Neue Käufe pausiert – Stops und Schutzverkäufe laufen weiter"
        elif e.art == "fortsetzen":
            z.kaeufe_pausiert = False
            text = "Automatik fortgesetzt"
        elif e.art == "positionen_schliessen":
            z.schliessen_angefordert = True
            z.kaeufe_pausiert = True
            text = "Aktive Positionen werden im nächsten Lauf geordnet verkauft (Robo-Kern bleibt); neue Käufe pausiert"
        else:
            n = 0
            for o in z.orders:
                if o.status == "offen" and o.richtung == "kauf":
                    o.status = "storniert"
                    o.reserviert_eur = 0.0
                    n += 1
            text = f"{n} offene Kauforder(s) storniert"
        speicher.nachtrag(conn, did, z, [{"tag": int(D), "art": "steuerung", "zuordnung": None, "text": f"{text} (Eingang aus der App)", "daten": {"eingang": e.kennung}}], now)
        texts.append(text)
    return texts[0]


def verarbeiten(conn: sqlite3.Connection, items: list[tuple[str, bytes]], *, key, eintraege: dict, method, cfg, D: int, synthetisch: bool, now: dt.datetime,
                log: Callable[[str], None] | None = None) -> dict:
    """Neue Eingänge (je Kennung genau einmal) prüfen und anwenden. Rückgabe nur mit Zählungen."""
    modus = "DEMO" if synthetisch else "PAPER"
    counts = {"neu": 0, "verarbeitet": 0, "abgelehnt": 0, "bekannt": 0}
    for kennung, blob in sorted(items, key=lambda x: x[0]):
        if not KENNUNG_RE.match(kennung or ""):
            continue
        if conn.execute("SELECT 1 FROM ap_eingang WHERE id = ?", (kennung,)).fetchone() is not None:
            counts["bekannt"] += 1
            continue
        counts["neu"] += 1
        sha = hashlib.sha256(blob).hexdigest()
        art, status, grund, created = None, "abgelehnt", None, None
        try:
            data = entschluesseln(blob, kennung, key)
            e = pruefen(data, kennung, eintraege, method, cfg=cfg, now=now, max_alter_s=AUFBEWAHRUNG_S)
            art, created = e.art, _iso(e.erstellt)
            conn.execute("SAVEPOINT eingang")
            try:
                grund = _anwenden(conn, e, cfg=cfg, D=D, synthetisch=synthetisch, modus=modus, now=now)
                conn.execute("RELEASE SAVEPOINT eingang")
                status = "verarbeitet"
            except (EingangFehler, ValueError) as exc:
                conn.execute("ROLLBACK TO SAVEPOINT eingang")
                conn.execute("RELEASE SAVEPOINT eingang")
                grund = exc.text if isinstance(exc, EingangFehler) else str(exc)
        except EingangFehler as exc:
            grund = exc.text
        conn.execute(
            "INSERT INTO ap_eingang(id, quelle, typ, groesse, sha256, erstellt_am, empfangen_am, status, grund, verarbeitet_am) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (kennung, "app", art, len(blob), sha, created, _iso(now), status, (grund or "")[:500], _iso(now)),
        )
        counts["verarbeitet" if status == "verarbeitet" else "abgelehnt"] += 1
    if log is not None and counts["neu"]:
        log(f"Eingänge aus der App: {counts['neu']} neu, {counts['verarbeitet']} übernommen, {counts['abgelehnt']} abgelehnt")
    return counts


def testnummer(conn: sqlite3.Connection) -> int:
    """Nummer des laufenden Pilottests (1 = erster; „neuer Test“ aus der App zählt hoch)."""
    row = conn.execute("SELECT wert_json FROM ap_zustand WHERE schluessel = ?", (TESTNUMMER,)).fetchone()
    return 1 if row is None else int(json.loads(row[0])["nummer"])


def einrichtung(conn: sqlite3.Connection) -> dict | None:
    """Zuletzt übernommene Einrichtung des Pilotdepots (oder None: Vorgabewerte aus der Konfiguration)."""
    row = conn.execute("SELECT wert_json FROM ap_zustand WHERE schluessel = ?", (EINRICHTUNG,)).fetchone()
    return None if row is None else json.loads(row[0])


def letzte(conn: sqlite3.Connection, n: int = 20) -> list[dict]:
    rows = conn.execute("SELECT id, typ, status, grund, erstellt_am, verarbeitet_am FROM ap_eingang ORDER BY verarbeitet_am DESC, id DESC LIMIT ?", (int(n),)).fetchall()
    return [{"kennung": r[0], "art": r[1], "status": r[2], "grund": r[3], "erstellt_utc": r[4], "verarbeitet_utc": r[5]} for r in rows]


def baue(kennung: str, art: str, inhalt: dict, key: crypto.KeyMaterial, erstellt: dt.datetime | None = None) -> str:
    """Gegenstück der App (für Tests und Probe): verschlüsselter Eingang als Base64-Text."""
    created = erstellt or kennung_zeit(kennung)
    payload = {"schema": SCHEMA, "kennung": kennung, "erstellt_utc": _iso(created), "art": art, "inhalt": inhalt}
    return base64.b64encode(crypto.pack(json.dumps(payload).encode("utf-8"), key, aad(kennung))).decode("ascii")


__all__ = ["ARTEN", "BRANCH", "Eingang", "EingangFehler", "annehmen", "aus_git", "aus_ordner", "baue", "eigene_depots", "ergebnis_datei", "letzte",
           "prune_names", "pruefen", "verarbeiten"]
