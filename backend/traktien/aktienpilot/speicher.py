"""Speichern und Laden der Spielgelddepots im verschlüsselten Zustand (SQLite, Migration 0010).

Ein Tagesschritt wird in **einer** Transaktion gespeichert: neue Ereignisse, geänderte Orders, Zustand (Positionen, Stops,
Gewinnstufen, Sperren, Verlustgrenzen), Tageswerte, Journal, Auswahl vor der Ausführung und die Markierung „Stichtag
verarbeitet“ (``ap_tageslauf``). Ein Neustart lädt daraus denselben Zustand (Abschnitt 29.8); das Buch entsteht immer neu aus
dem unveränderlichen Ereignisjournal – es gibt keine zweite Schattenbuchhaltung (Abschnitt 32.3).
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import sqlite3

from .ausfuehrung import SimOrder
from .buchhaltung import Event
from .motor import DepotDef, DepotZustand, KernDef, Position, StrategieDef, Tagesergebnis
from .regeln import fingerabdruck
from .risiko import LossLimits

ORDER_HISTORIE_TAGE = 60


def _now(jetzt: dt.datetime | None) -> str:
    value = jetzt or dt.datetime.now(dt.timezone.utc)
    return value.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _canon(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


# ------------------------------------------------------------------------------------------------ Regeln


def regel_speichern(conn: sqlite3.Connection, regel: dict, quelle: str, jetzt: dt.datetime | None = None) -> bool:
    """Regelversion ablegen. Gleiche ID und Version mit anderem Inhalt ist ein Fehler (Versionen sind unveränderlich)."""
    sha = fingerabdruck(regel)
    row = conn.execute("SELECT sha256, inhalt_json FROM ap_regel WHERE id = ? AND version = ?", (regel["id"], regel["version"])).fetchone()
    if row is not None:
        if row[0] != sha:
            raise ValueError(f"Regel {regel['id']} Version {regel['version']} existiert mit anderem Inhalt – neue Version nötig")
        return False
    conn.execute("INSERT INTO ap_regel(id, version, name, inhalt_json, sha256, quelle, erstellt_am) VALUES (?, ?, ?, ?, ?, ?, ?)",
                 (regel["id"], int(regel["version"]), regel["name"], _canon(regel), sha, quelle, _now(jetzt)))
    return True


def regel_laden(conn: sqlite3.Connection, rid: str, version: int | None = None) -> dict | None:
    if version is None:
        row = conn.execute("SELECT inhalt_json FROM ap_regel WHERE id = ? ORDER BY version DESC LIMIT 1", (rid,)).fetchone()
    else:
        row = conn.execute("SELECT inhalt_json FROM ap_regel WHERE id = ? AND version = ?", (rid, int(version))).fetchone()
    return None if row is None else json.loads(row[0])


def regeln_alle(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("SELECT inhalt_json, quelle, erstellt_am FROM ap_regel ORDER BY id, version").fetchall()
    out = []
    for r in rows:
        regel = json.loads(r[0])
        out.append({"regel": regel, "quelle": r[1], "erstellt_am": r[2]})
    return out


# ------------------------------------------------------------------------------------------------ Depots


def definition_json(d: DepotDef) -> dict:
    return {
        "id": d.id, "name": d.name, "art": d.art, "startkapital_eur": d.startkapital_eur, "start_tag": d.start_tag,
        "aktiver_anteil": d.aktiver_anteil, "synthetisch": d.synthetisch, "beschreibung": d.beschreibung,
        "strategien": [{"zuordnung": s.zuordnung, "regel": f"{s.regel['id']}@{s.regel['version']}", "anteil": s.anteil} for s in d.strategien],
        "kern": None if d.kern is None else {"ziele": d.kern.ziele, "schwelle_pp": d.kern.schwelle_pp, "rebalancing": d.kern.rebalancing},
    }


def definition_aus_json(conn: sqlite3.Connection, data: dict) -> DepotDef:
    strategies = []
    for s in data.get("strategien", []):
        rid, version = s["regel"].rsplit("@", 1)
        regel = regel_laden(conn, rid, int(version))
        if regel is None:
            raise ValueError(f"Regel {s['regel']} fehlt im Zustand")
        strategies.append(StrategieDef(s["zuordnung"], regel, float(s["anteil"])))
    kern = None
    if data.get("kern"):
        k = data["kern"]
        kern = KernDef({str(i): float(w) for i, w in k["ziele"].items()}, float(k.get("schwelle_pp", 5.0)), bool(k.get("rebalancing", True)))
    return DepotDef(data["id"], data["name"], data["art"], float(data["startkapital_eur"]), int(data["start_tag"]), float(data["aktiver_anteil"]),
                    tuple(strategies), kern, bool(data.get("synthetisch")), data.get("beschreibung", ""))


def depot_anlegen(conn: sqlite3.Connection, d: DepotDef, *, modus: str, test_id: str, jetzt: dt.datetime | None = None) -> str:
    """Depot anlegen oder bestätigen. Rückgabe: „neu“, „unverändert“ oder „geaendert“ (dann muss ein neuer Test beginnen)."""
    if modus not in ("PAPER", "SIGNAL", "DEMO"):
        raise ValueError("nur PAPER, SIGNAL oder DEMO – Echtgeld ist ausgeschlossen")
    for s in d.strategien:
        regel_speichern(conn, s.regel, "konfiguration" if s.regel.get("herkunft", {}).get("vorlage") else "app", jetzt)
    data = definition_json(d)
    sha = hashlib.sha256(_canon(data).encode()).hexdigest()
    row = conn.execute("SELECT definition_sha, status FROM ap_depot WHERE id = ?", (d.id,)).fetchone()
    if row is None:
        conn.execute(
            "INSERT INTO ap_depot(id, name, art, modus, definition_json, definition_sha, test_id, start_tag, synthetisch, status, angelegt_am) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'aktiv', ?)",
            (d.id, d.name, d.art, modus, _canon(data), sha, test_id, d.start_tag, 1 if d.synthetisch else 0, _now(jetzt)),
        )
        return "neu"
    return "unverändert" if row[0] == sha else "geaendert"


def depots(conn: sqlite3.Connection, *, nur_aktive: bool = True) -> list[tuple[DepotDef, dict]]:
    sql = "SELECT id, modus, definition_json, test_id, status, angelegt_am, archiviert_am FROM ap_depot"
    if nur_aktive:
        sql += " WHERE status != 'archiviert'"
    out = []
    for r in conn.execute(sql + " ORDER BY id").fetchall():
        d = definition_aus_json(conn, json.loads(r[2]))
        out.append((d, {"modus": r[1], "test_id": r[3], "status": r[4], "angelegt_am": r[5], "archiviert_am": r[6]}))
    return out


def depot_archivieren(conn: sqlite3.Connection, depot_id: str, jetzt: dt.datetime | None = None) -> None:
    """„Neuen Test starten“: der alte Lauf bleibt vollständig erhalten (archiviert), nichts wird gelöscht (Abschnitt 29.8)."""
    conn.execute("UPDATE ap_depot SET status = 'archiviert', archiviert_am = ? WHERE id = ?", (_now(jetzt), depot_id))


# ------------------------------------------------------------------------------------------------ Zustand


def zustand_laden(conn: sqlite3.Connection, depot_id: str) -> DepotZustand:
    z = DepotZustand(depot_id)
    rows = conn.execute("SELECT * FROM ap_ereignis WHERE depot_id = ? ORDER BY seq", (depot_id,)).fetchall()
    cols = [c[0] for c in conn.execute("SELECT * FROM ap_ereignis LIMIT 0").description]
    for r in rows:
        z.events.append(Event.from_row(dict(zip(cols, r))))
    state = conn.execute("SELECT wert_json FROM ap_zustand WHERE schluessel = ?", (f"depot:{depot_id}",)).fetchone()
    if state is not None:
        s = json.loads(state[0])
        z.positionen = {k: Position.from_dict(v) for k, v in s.get("positionen", {}).items()}
        z.sperren = s.get("sperren", {})
        z.verlust = LossLimits.from_dict(s.get("verlust") or {})
        z.letzter_tag = s.get("letzter_tag")
        z.letzte_auswahl = s.get("letzte_auswahl", {})
        z.entschieden = {k: int(v) for k, v in s.get("entschieden", {}).items()}
        z.kaeufe_pausiert = bool(s.get("kaeufe_pausiert", False))
        z.seq = int(s.get("seq", 0))
        z.order_seq = int(s.get("order_seq", 0))
        z.gestartet = bool(s.get("gestartet", False))
    z.seq = max(z.seq, max((e.seq for e in z.events), default=0))
    lo = (z.letzter_tag or 0) - ORDER_HISTORIE_TAGE
    for r in conn.execute("SELECT daten_json FROM ap_order WHERE depot_id = ? AND (status = 'offen' OR datentag >= ?) ORDER BY datentag, id",
                          (depot_id, lo)).fetchall():
        z.orders.append(SimOrder.from_dict(json.loads(r[0])))
    for r in conn.execute("SELECT daten_json FROM ap_wert WHERE depot_id = ? ORDER BY tag", (depot_id,)).fetchall():
        z.werte.append(json.loads(r[0]))
    return z


def zustand_json(z: DepotZustand) -> dict:
    verlust = z.verlust.as_dict()
    verlust["verlauf"] = z.verlust.history  # vollständige Historie der Verluststufen (nicht nur die letzten 50)
    return {
        "positionen": {k: p.as_dict() for k, p in sorted(z.positionen.items())},
        "sperren": z.sperren, "verlust": verlust, "letzter_tag": z.letzter_tag, "letzte_auswahl": z.letzte_auswahl,
        "entschieden": z.entschieden, "kaeufe_pausiert": z.kaeufe_pausiert, "seq": z.seq, "order_seq": z.order_seq,
        "gestartet": z.gestartet,
    }


def speichern(conn: sqlite3.Connection, d: DepotDef, z: DepotZustand, ergebnis: Tagesergebnis, *, lauf_id: str, datenstand: str,
              jetzt: dt.datetime | None = None) -> None:
    """Ergebnis eines Tagesschritts speichern (der Aufrufer hält die Transaktion)."""
    if not ergebnis.verarbeitet:
        return
    stamp = _now(jetzt)
    for e in ergebnis.ereignisse:
        row = e.as_row()
        row["erfasst_am"] = stamp
        conn.execute(
            "INSERT INTO ap_ereignis(id, depot_id, seq, zeit, tag, typ, isin, stueck, kurs, waehrung, fx_eur, fx_quelle, betrag_eur, gebuehren_eur, "
            "quelle, order_id, signal_id, verwaltet, nutzlast_json, erfasst_am) VALUES (:id, :depot_id, :seq, :zeit, :tag, :typ, :isin, :stueck, :kurs, "
            ":waehrung, :fx_eur, :fx_quelle, :betrag_eur, :gebuehren_eur, :quelle, :order_id, :signal_id, :verwaltet, :nutzlast_json, :erfasst_am)", row)
    changed = {o.id: o for o in z.orders if o.datentag >= (ergebnis.tag - ORDER_HISTORIE_TAGE) or o.status == "offen"}
    for o in changed.values():
        conn.execute(
            "INSERT INTO ap_order(id, depot_id, zuordnung, isin, richtung, stueck, status, datentag, sitzung, daten_json, aktualisiert_am) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET status = excluded.status, sitzung = excluded.sitzung, "
            "daten_json = excluded.daten_json, aktualisiert_am = excluded.aktualisiert_am",
            (o.id, o.depot_id, o.zuordnung, o.isin, o.richtung, int(o.stueck), o.status, int(o.datentag), o.sitzung, _canon(o.as_dict()), stamp),
        )
    conn.execute("INSERT INTO ap_zustand(schluessel, wert_json, aktualisiert_am) VALUES (?, ?, ?) "
                 "ON CONFLICT(schluessel) DO UPDATE SET wert_json = excluded.wert_json, aktualisiert_am = excluded.aktualisiert_am",
                 (f"depot:{d.id}", _canon(zustand_json(z)), stamp))
    last_saved = conn.execute("SELECT MAX(tag) FROM ap_wert WHERE depot_id = ?", (d.id,)).fetchone()[0]
    for w in z.werte:
        if last_saved is None or w["tag"] >= last_saved:
            conn.execute("INSERT INTO ap_wert(depot_id, tag, daten_json) VALUES (?, ?, ?) ON CONFLICT(depot_id, tag) DO UPDATE SET daten_json = excluded.daten_json",
                         (d.id, int(w["tag"]), _canon(w)))
    for j in ergebnis.journal:
        conn.execute("INSERT INTO ap_protokoll(depot_id, tag, zeit, art, zuordnung, text, daten_json) VALUES (?, ?, ?, ?, ?, ?, ?)",
                     (d.id, j["tag"], stamp, j["art"], j.get("zuordnung"), j["text"], _canon(j.get("daten", {}))))
        if j["art"] == "entscheidung" and "auswahl" in j.get("daten", {}):
            body = _canon(j["daten"])
            strategy = next((s for s in d.strategien if s.zuordnung == j.get("zuordnung")), None)
            conn.execute(
                "INSERT OR IGNORE INTO ap_auswahl(id, depot_id, zuordnung, entscheidungstag, datenstand, regel, regel_sha, inhalt_json, inhalt_sha256, festgehalten_am) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (f"a-{d.id}-{j.get('zuordnung')}-{j['tag']}", d.id, j.get("zuordnung") or "", j["tag"], datenstand, j["daten"].get("regel", ""),
                 fingerabdruck(strategy.regel) if strategy else "", body, hashlib.sha256(body.encode()).hexdigest(), stamp),
            )
    conn.execute("INSERT INTO ap_tageslauf(depot_id, tag, lauf_id, verarbeitet_am, ergebnis_json) VALUES (?, ?, ?, ?, ?)",
                 (d.id, int(ergebnis.tag), lauf_id, stamp, _canon({"ereignisse": len(ergebnis.ereignisse), "orders": len(ergebnis.orders),
                                                                   "journal": len(ergebnis.journal)})))


def nachtrag(conn: sqlite3.Connection, depot_id: str, z: DepotZustand, eintraege: list[dict], jetzt: dt.datetime | None = None) -> None:
    """Steuerung außerhalb eines Tagesschritts (Eingang aus der App: pausieren, fortsetzen, offene Käufe stornieren): Zustand
    und geänderte Orders speichern, Journal ergänzen. Keine Buchung – Geld und Bestand ändern sich nur über Ereignisse."""
    stamp = _now(jetzt)
    for o in z.orders:
        conn.execute("UPDATE ap_order SET status = ?, daten_json = ?, aktualisiert_am = ? WHERE id = ? AND depot_id = ?",
                     (o.status, _canon(o.as_dict()), stamp, o.id, depot_id))
    conn.execute("INSERT INTO ap_zustand(schluessel, wert_json, aktualisiert_am) VALUES (?, ?, ?) "
                 "ON CONFLICT(schluessel) DO UPDATE SET wert_json = excluded.wert_json, aktualisiert_am = excluded.aktualisiert_am",
                 (f"depot:{depot_id}", _canon(zustand_json(z)), stamp))
    for j in eintraege:
        conn.execute("INSERT INTO ap_protokoll(depot_id, tag, zeit, art, zuordnung, text, daten_json) VALUES (?, ?, ?, ?, ?, ?, ?)",
                     (depot_id, j.get("tag"), stamp, j["art"], j.get("zuordnung"), j["text"], _canon(j.get("daten", {}))))


def journal(conn: sqlite3.Connection, depot_id: str, limit: int = 300) -> list[dict]:
    rows = conn.execute("SELECT tag, zeit, art, zuordnung, text, daten_json FROM ap_protokoll WHERE depot_id = ? ORDER BY id DESC LIMIT ?",
                        (depot_id, int(limit))).fetchall()
    return [{"tag": r[0], "zeit": r[1], "art": r[2], "zuordnung": r[3], "text": r[4], "daten": json.loads(r[5] or "{}")} for r in rows]
