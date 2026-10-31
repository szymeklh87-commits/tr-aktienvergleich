"""Stand des Spielgeld-Robos für die App (Abschnitte 20, 29.6): Depots, Werte, Positionen, Orders, Journal, Regeln.

Gebaut wird aus der Datenbank (nicht aus Zwischenzuständen eines Laufs): derselbe bestätigte Stand für App, Export und
Neustart (Abschnitt 32.3). Verschlüsselt mit dem Datenschlüssel (TRA1, AAD ``pilot/<id>/pilot.bin``) und in ``ap_stand``
abgelegt; ``build_status_file`` legt den neuesten Stand als Datei in die Website. Öffentlich (``status.json``) stehen nur
Kennung, Zeit und Version – keine Depotdaten.

Kennzahlen: zeitgewichtete Rendite (Zu- und Abflüsse herausgerechnet, Strategievergleich), Gewinn/Verlust realisiert und offen,
Kosten, größter Rückgang des Gesamtwerts, Verluststufe des aktiven Teils. Alle Beträge in EUR, Spielgeld.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import sqlite3

from ..util import crypto
from ..util.timeutil import day_to_date
from . import AP_VERSION
from .buchhaltung import replay, value
from .katalog import KATALOG_VERSION
from .speicher import definition_aus_json, journal, regel_laden, zustand_laden

SCHEMA = "tr-spielgeld/1"
JOURNAL_MAX = 80
KANDIDATEN_MAX = 15


def _datum(day) -> str | None:
    return None if day is None else day_to_date(int(day)).isoformat()


def _r(x, nd=2):
    if x is None:
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return None if not math.isfinite(v) else round(v, nd)


def zeitgewichtet(werte: list[dict], fluesse: dict[int, float]) -> float | None:
    """Zeitgewichtete Rendite: Tagesrenditen ohne Zu- und Abflüsse verkettet."""
    index = 1.0
    prev = None
    for w in werte:
        v = float(w["gesamt_eur"])
        flow = fluesse.get(int(w["tag"]), 0.0)
        if prev is None:
            prev = v
            continue
        if prev <= 0:
            return None
        index *= (v - flow) / prev
        prev = v
    return None if prev is None else index - 1.0


def max_rueckgang(werte: list[dict]) -> float:
    peak = None
    worst = 0.0
    for w in werte:
        v = float(w["gesamt_eur"])
        peak = v if peak is None else max(peak, v)
        if peak > 0:
            worst = max(worst, 1.0 - v / peak)
    return worst


KANDIDATEN_OHNE_HANDEL = 5


def runden(obj, stellen: int = 6):
    """Gleitkommazahlen auf ``stellen`` signifikante Stellen (kleinerer Stand, keine Scheingenauigkeit); rekursiv."""
    if isinstance(obj, float):
        if not math.isfinite(obj) or obj == 0.0:
            return obj if math.isfinite(obj) else None
        return float(f"{obj:.{stellen}g}")
    if isinstance(obj, dict):
        return {k: runden(v, stellen) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [runden(v, stellen) for v in obj]
    return obj


def _kandidat(c: dict) -> dict:
    out = {k: c[k] for k in ("isin", "platz", "score", "ausgewaehlt", "grund", "filter", "fundstellen", "sortwerte", "bedingungen") if k in c}
    if c.get("beispiele"):
        out["beispiele"] = c["beispiele"][:2]
    return out


def _kompakt(entry: dict) -> dict:
    """Journal-Eintrag für die App: Entscheidungen mit den wichtigsten Begründungen; ohne Handel nur die ersten Kandidaten
    (die Statistik nennt alle Zahlen: geprüft, nicht erfüllt, nicht prüfbar)."""
    out = {"tag": entry["tag"], "datum": _datum(entry["tag"]), "art": entry["art"], "text": entry["text"], "zuordnung": entry.get("zuordnung")}
    d = entry.get("daten") or {}
    if entry["art"] == "entscheidung":
        a = d.get("auswahl") or {}
        traded = bool(d.get("kaeufe") or d.get("verkaeufe"))
        limit = KANDIDATEN_MAX if traded else KANDIDATEN_OHNE_HANDEL
        out["daten"] = {
            "regel": d.get("regel"), "budget_eur": d.get("budget_eur"), "verluststufe": d.get("verluststufe"),
            "statistik": a.get("statistik"), "quellen": a.get("quellen"), "ausgewaehlt": a.get("ausgewaehlt"),
            "kandidaten": [_kandidat(c) for c in (a.get("kandidaten") or [])[:limit]], "kaeufe": d.get("kaeufe"), "verkaeufe": d.get("verkaeufe"),
            "abgelehnt": (d.get("abgelehnt") or [])[:12], "ausstiege": d.get("ausstiege"),
        }
    elif d:
        keep = ("isin", "order", "grund", "grund_text", "stueck", "kurs", "referenzkurs", "betrag_eur", "gebuehr_eur", "regel", "uebergang", "alt", "neu")
        out["daten"] = {k: d[k] for k in keep if k in d}
    return out


def depot_stand(conn: sqlite3.Connection, depot_id: str, *, D: int, stamm: dict, market=None, voll: bool = True) -> dict:
    """Stand eines Depots. ``voll=False`` (archivierte Läufe): nur Kopf, letzter Wert und Kennzahlen für die Chronik."""
    row = conn.execute("SELECT id, name, art, modus, definition_json, test_id, start_tag, synthetisch, status, angelegt_am, archiviert_am FROM ap_depot WHERE id = ?",
                       (depot_id,)).fetchone()
    d = definition_aus_json(conn, json.loads(row[4]))
    z = zustand_laden(conn, depot_id)
    book = replay(depot_id, z.events)
    werte = z.werte
    flows: dict[int, float] = {}
    for e in z.events:
        if e.typ in ("einzahlung", "auszahlung") and int(e.tag) > int(d.start_tag):
            flows[int(e.tag)] = flows.get(int(e.tag), 0.0) + float(e.betrag_eur)
    last = werte[-1] if werte else None
    realized = sum(r.gain_eur for r in book.realized if r.gain_eur is not None)
    unknown_realized = sum(1 for r in book.realized if r.gain_eur is None)
    positions = []
    open_gain = 0.0
    val = value(book, market, D) if market is not None else None
    for key, pos in sorted(z.positionen.items()):
        qty = book.qty(pos.isin, pos.zuordnung)
        if qty <= 0:
            continue
        cost = book.owner_cost.get(pos.isin, {}).get(pos.zuordnung)
        price = val.prices_eur.get(pos.isin) if val is not None else None
        worth = None if price is None else price * qty
        if worth is not None and cost is not None:
            open_gain += worth - cost
        st = stamm.get(pos.isin) or {}
        positions.append({
            "isin": pos.isin, "name": st.get("name"), "zuordnung": pos.zuordnung, "stueck": qty, "einstand_eur": _r(cost),
            "kurs_eur": _r(price, 4), "wert_eur": _r(worth), "gewinn_eur": _r(None if worth is None or cost is None else worth - cost),
            "gewinn_pct": _r(None if worth is None or not cost else 100.0 * (worth / cost - 1.0)), "stop": _r(pos.stop, 4),
            "eroeffnet": _datum(pos.eroeffnet), "gm": pos.gm, "regel": pos.regel, "branche": st.get("branche"),
        })
    orders = [o.as_dict() for o in z.orders if o.status == "offen"]
    recent = [o.as_dict() for o in z.orders if o.status != "offen"][-30:]
    entries = list(reversed(journal(conn, depot_id, JOURNAL_MAX)))
    strategies = []
    for s in d.strategien:
        strategies.append({"zuordnung": s.zuordnung, "regel": f"{s.regel['id']}@{s.regel['version']}", "name": s.regel["name"], "anteil": s.anteil})
    twr = zeitgewichtet(werte, flows)
    head = {
        "id": depot_id, "name": row[1], "art": row[2], "modus": row[3], "test_id": row[5], "status": row[8], "start": _datum(row[6]),
        "angelegt_am": row[9], "archiviert_am": row[10], "historisch": str(row[5]).startswith("historisch-"), "synthetisch": bool(row[7]),
    }
    kennzahlen = {
        "rendite_zeitgewichtet_pct": _r(None if twr is None else 100.0 * twr), "gewinn_realisiert_eur": _r(realized),
        "gewinn_realisiert_unbekannt": unknown_realized, "gewinn_offen_eur": _r(open_gain), "kosten_eur": _r(book.fees_eur),
        "max_rueckgang_pct": _r(100.0 * max_rueckgang(werte)), "sitzungen": len(werte),
        "kaeufe": sum(1 for e in z.events if e.typ == "kauf"), "verkaeufe": sum(1 for e in z.events if e.typ == "verkauf"),
    }
    wert = None if last is None else {k: last.get(k) for k in ("datum", "gesamt_eur", "kern_eur", "aktiv_eur", "guthaben_eur", "einzahlungen_eur", "gebuehren_eur", "vollstaendig", "fehlend", "stufe")}
    if not voll:
        return {**head, "kompakt": True, "startkapital_eur": d.startkapital_eur, "wert": wert, "kennzahlen": kennzahlen, "letzter_tag": _datum(z.letzter_tag),
                "strategien": strategies}
    return {
        **head, "beschreibung": d.beschreibung, "startkapital_eur": d.startkapital_eur,
        "aktiver_anteil": d.aktiver_anteil, "strategien": strategies,
        "kern": None if d.kern is None else {"ziele": {i: w for i, w in d.kern.ziele.items()}, "schwelle_pp": d.kern.schwelle_pp, "rebalancing": d.kern.rebalancing,
                                              "namen": {i: (stamm.get(i) or {}).get("name") for i in d.kern.ziele}},
        "wert": wert,
        "reserviert_eur": _r(sum(o["reserviert_eur"] for o in orders)),
        "kennzahlen": kennzahlen,
        "verlust": z.verlust.as_dict(), "pausiert": z.kaeufe_pausiert, "letzter_tag": _datum(z.letzter_tag),
        "verlauf": {"tag": [_datum(w["tag"]) for w in werte], "gesamt": [_r(w["gesamt_eur"]) for w in werte],
                    "kern": [_r(w["kern_eur"]) for w in werte], "aktiv": [_r(w["aktiv_eur"]) for w in werte]},
        "positionen": positions, "orders_offen": orders, "orders_zuletzt": recent,
        "journal": [_kompakt(e) for e in entries],
    }


ARCHIV_MAX = 40


def bauen(conn: sqlite3.Connection, *, D: int, snapshot_id: str, modus: str, now: dt.datetime, eintraege: dict, method, cfg, stamm: dict, market=None) -> dict:
    order = "CASE art WHEN 'pilot' THEN 0 WHEN 'forschung' THEN 1 ELSE 2 END, id"
    ids = [r[0] for r in conn.execute(f"SELECT id FROM ap_depot WHERE status != 'archiviert' ORDER BY {order}")]
    depots = [depot_stand(conn, i, D=D, stamm=stamm, market=market) for i in ids]
    archived = [r[0] for r in conn.execute("SELECT id FROM ap_depot WHERE status = 'archiviert' ORDER BY archiviert_am DESC, id LIMIT ?", (ARCHIV_MAX,))]
    chronik = [depot_stand(conn, i, D=D, stamm=stamm, market=market, voll=False) for i in archived]
    rules = {}
    for dep in depots:
        for s in dep["strategien"]:
            rid, version = s["regel"].rsplit("@", 1)
            regel = regel_laden(conn, rid, int(version))
            if regel is not None:
                rules[s["regel"]] = regel
    stamp = now.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    names = {}
    for dep in depots:
        for p in dep["positionen"]:
            names[p["isin"]] = p.get("name")
        for o in dep["orders_offen"] + dep["orders_zuletzt"]:
            names.setdefault(o["isin"], (stamm.get(o["isin"]) or {}).get("name"))
    payload = runden({
        "schema": SCHEMA, "erstellt_utc": stamp, "datentag": _datum(D), "snapshot_id": snapshot_id, "modus": modus,
        "version": AP_VERSION, "katalog": KATALOG_VERSION,
        "hinweis": "Spielgeld: virtuelle Orders mit echten verfügbaren Kursen (PAPER) bzw. synthetischen Kursen (DEMO). Keine echten Orders, keine Anlageberatung.",
        "ueberwachung": "Täglicher Lauf nach Börsenschluss: Stops werden anhand der fertigen Tageskerze geprüft – keine Überwachung während der Sitzung.",
        "depots": depots, "chronik": chronik, "regeln": rules, "namen": names,
    })
    # Kennung aus dem Inhalt: gleicher Inhalt = gleiche Kennung, jede Änderung = neue Datei (kein veralteter Zwischenspeicher)
    digest = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return {"id": f"{_datum(D)}_{digest[:10]}", **payload}


def speichern(conn: sqlite3.Connection, payload: dict, key: crypto.KeyMaterial | None, now: dt.datetime, keep: int = 3) -> int:
    plain = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    blob = crypto.pack(plain, key, f"pilot/{payload['id']}/pilot.bin")
    stamp = now.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    conn.execute("INSERT OR REPLACE INTO ap_stand(id, datentag, erstellt_am, groesse, sha256, inhalt) VALUES (?, ?, ?, ?, ?, ?)",
                 (payload["id"], int(dt.date.fromisoformat(payload["datentag"]).toordinal() - dt.date(1970, 1, 1).toordinal()), stamp, len(blob),
                  hashlib.sha256(blob).hexdigest(), blob))
    old = [r[0] for r in conn.execute("SELECT id FROM ap_stand ORDER BY erstellt_am DESC, rowid DESC").fetchall()[keep:]]
    for sid in old:
        conn.execute("DELETE FROM ap_stand WHERE id = ?", (sid,))
    return len(blob)


def neuester(conn: sqlite3.Connection) -> tuple[str, str, bytes] | None:
    """(ID, Erstellzeit, verschlüsselter Inhalt) des neuesten Standes – für die Website."""
    try:
        row = conn.execute("SELECT id, erstellt_am, inhalt FROM ap_stand ORDER BY erstellt_am DESC, rowid DESC LIMIT 1").fetchone()  # gleiche Zeit (DEMO-Uhr): zuletzt gespeichert
    except sqlite3.OperationalError:
        return None
    return None if row is None else (row[0], row[1], bytes(row[2]))
