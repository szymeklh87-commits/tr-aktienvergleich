"""Historische Simulation aller Spielgelddepots auf dem gespeicherten Zustand (Abschnitte 14, 29.8, 31.6 „Historisch testen“).

Der gemeinsame Motor (``motor.tagesschritt``) läuft über die letzten ``tage`` Handelstage bis zum neuesten veröffentlichten
Stand – mit den Tageskerzen des Zustands und je Tag nachgerechneten Ranglisten (Rechenkern mit den Kursen bis zu diesem Tag,
dieselben Eingaben wie im täglichen Lauf: geprüfte Identität, Kalender, Splits, Prüfentscheidungen, eigener Stichtag).

Kennzeichnung: Depot-IDs ``h-…``, Name mit „(historische Simulation)“, Test-ID ``historisch-…``. Eine historische Simulation
ist kein Vorwärtstest und zählt nicht als tatsächlich vergangene Paper-Sitzung. Eine neue Simulation archiviert die vorige
(nichts wird gelöscht). Gespeichert wird über denselben Weg wie im täglichen Lauf (``speicher.speichern`` je Tagesschritt).

Grenzen (im Ergebnis vermerkt): heutige Datenrevision und heutiges Universum (Rückschau-Verzerrung möglich), kein
Kursabgleich mit der Börse für vergangene Tage, Analystenziele nur aus der gespeicherten Zeitreihe bis zum jeweiligen Tag.
"""

from __future__ import annotations

import datetime as dt
import sqlite3
import types

import numpy as np

from ..analytics.engine import InstrumentData
from ..analytics.fx import FxRates
from ..config import MethodConfig
from ..providers.exchanges import unit_info
from ..store import db, repo
from . import backtest, motor, speicher, stand, tageslauf
from . import katalog as kat
from .config import AktienPilotConfig
from .markt import Market, Series

PREFIX = "h-"


def _laden(conn: sqlite3.Connection, members: dict, von: int, bis: int, calendars, synthetisch: bool):
    """Kerzen und Rechenkern-Eingaben aller geprüften Aktien des Universums (Referenznotierung, Kalender vorhanden)."""
    refs = repo.reference_listings(conn)
    rows = repo.instruments(conn, members)
    reviews = repo.review_map(conn)
    series: dict[str, Series] = {}
    inputs: list[InstrumentData] = []
    metas = []
    sessions_cache: dict[str, np.ndarray] = {}
    skipped = {"identitaet": 0, "kalender": 0, "kurse": 0}
    for isin in sorted(members):
        row, listing = rows.get(isin), refs.get(isin)
        if not members[isin]["valid"] or row is None or listing is None or row["identity_status"] != "verifiziert":
            skipped["identitaet"] += 1  # ohne geprüfte Identität keine Rangliste (wie im täglichen Lauf)
            continue
        code = listing["calendar_code"]
        if not code or calendars is None or not calendars.available(code):
            skipped["kalender"] += 1
            continue
        bars = repo.load_bars(conn, listing["id"], int(listing["data_revision"]), von)
        keep = bars["days"] <= bis
        bars = {k: v[keep] for k, v in bars.items()}
        if not len(bars["days"]):
            skipped["kurse"] += 1
            continue
        if code not in sessions_cache:
            sessions_cache[code] = calendars.sessions(code, von, bis)
        unit = listing["price_unit"] or listing["currency"]
        base_currency, unit_to_base = unit_info(unit)
        splits = repo.splits_for(conn, listing["id"])
        name = listing["provider_name"] or row["full_name"] or members[isin]["name"]
        try:
            series[isin] = Series(isin, bars["days"], bars["open"], bars["high"], bars["low"], bars["close"], bars["volume"],
                                  currency=base_currency or "EUR", unit_factor=float(listing["unit_factor"] or unit_to_base), exchange=listing["mic"] or listing["exchange_key"] or "",
                                  calendar=code, name=name, splits=tuple((s.day, s.factor) for s in splits), synthetic=synthetisch)
        except ValueError:
            skipped["kurse"] += 1
            continue
        inputs.append(InstrumentData(isin=isin, sessions=sessions_cache[code], days=bars["days"], close=bars["close"], volume=bars["volume"], splits=splits,
                                     reviewed_jumps=reviews.get(isin, {}), hold_all=bool(listing["hold_all"]), warnings=int(row["warnings"] or 0),
                                     currency=base_currency, unit_factor=unit_to_base))
        metas.append(types.SimpleNamespace(isin=isin, name=name, instrument_type=row["instrument_type"], mic=listing["mic"], exchange_key=listing["exchange_key"],
                                           currency=base_currency, ticker=listing["ticker"]))
    return series, inputs, metas, skipped


def _fx(conn: sqlite3.Connection, von: int, method: MethodConfig) -> FxRates | None:
    rows = [(int(r["day"]), r["currency"], float(r["per_eur"])) for r in repo.fx_rates_since(conn, von)]
    if not rows:
        return None
    return FxRates.from_rows(rows, source="EZB-Referenzkurse (Zustand)", url=None, fetched_at=None, max_age_days=int(method.fx_max_age_days))


def historisch(conn: sqlite3.Connection, *, cfg: AktienPilotConfig, method: MethodConfig, mode: str, tage: int, now: dt.datetime, calendars,
               provider, key, log=print) -> dict:
    """Simulation über die letzten ``tage`` Handelstage bis zum neuesten veröffentlichten Stand; speichert die Depots ``h-…``
    und einen neuen App-Stand. Rückgabe: Zusammenfassung nur mit Zahlen."""
    if tage < 2 or tage > 250:
        raise ValueError("tage: 2 bis 250 Handelstage")
    published = repo.published_snapshots(conn, mode)
    if not published:
        raise ValueError("kein veröffentlichter Stand im Zustand")
    latest = published[0]
    D = int(latest["cutoff_day"])
    members = repo.universe_members(conn, latest["universe_id"])
    synthetisch = mode == "demo"
    span = int(tage * 7 / 5) + 14
    von = D - span - tageslauf.MARKTREIHE_TAGE
    started = dt.datetime.now(dt.timezone.utc)
    series, inputs, metas, skipped = _laden(conn, members, von, D, calendars, synthetisch)
    if provider is not None:
        tageslauf.marktreihen_abrufen(conn, provider, cfg, D, now)
    etfs, indices = tageslauf.marktreihen_laden(conn, cfg, von, D, synthetisch)
    series.update(etfs)
    fx = _fx(conn, von, method)
    market = Market(series=series, fx=fx, indices=indices, synthetic=synthetisch, data_stand=latest["id"], source="Zustand (historische Simulation)")
    stamm = tageslauf.stammdaten(conn, metas, cfg)
    eintraege = kat.katalog(method, cfg)
    stock_days = np.unique(np.concatenate([s.days for i, s in series.items() if i in members])) if metas else np.empty(0, dtype=np.int64)
    days = [int(d) for d in stock_days[(stock_days > D - span) & (stock_days <= D)]][-tage:]
    if len(days) < 2:
        raise ValueError("zu wenige Handelstage im Zustand")
    load_s = (dt.datetime.now(dt.timezone.utc) - started).total_seconds()

    # laufende Nummer statt Uhrzeit: eindeutig auch bei fester DEMO-Uhr, und lesbar („h-pilot-003“)
    nummer = int(conn.execute("SELECT COUNT(DISTINCT test_id) FROM ap_depot WHERE id LIKE ?", (PREFIX + "%",)).fetchone()[0]) + 1
    test_id = f"historisch-{nummer:03d}-{backtest.datum(days[0])}-{backtest.datum(days[-1])}"
    defs: list[motor.DepotDef] = []
    for d in tageslauf.depots_definieren(cfg, method, eintraege, days[0], synthetisch=synthetisch):
        base = d.id.removeprefix("demo-")
        defs.append(motor.DepotDef(f"{PREFIX}{base}-{nummer:03d}", f"{d.name} (historische Simulation)", d.art, d.startkapital_eur, days[0], d.aktiver_anteil,
                                   d.strategien, d.kern, d.synthetisch, (d.beschreibung + " – historische Simulation, kein Vorwärtstest").lstrip(" –")))
    window = backtest.lineal_fenster(eintraege, [s.regel for d in defs for s in d.strategien], method)
    modus = "DEMO" if synthetisch else "PAPER"
    with db.Transaction(conn):
        archived = 0
        for (did,) in conn.execute("SELECT id FROM ap_depot WHERE id LIKE ? AND status != 'archiviert'", (PREFIX + "%",)).fetchall():
            speicher.depot_archivieren(conn, did, now)
            archived += 1
        for d in defs:
            speicher.depot_anlegen(conn, d, modus=modus, test_id=test_id, jetzt=now)

    quelle = backtest.Kontextquelle(method, cfg, market, inputs, stamm, window, fx, fakten_fn=lambda day: tageslauf.fakten_zum_tag(conn, day, series))
    archiv = backtest.NachgerechnetesArchiv(quelle, [int(d) for d in stock_days if int(d) <= D])
    counts = {"ereignisse": 0, "orders": 0, "journal": 0, "schritte": 0}

    def save(d: motor.DepotDef, z: motor.DepotZustand, res: motor.Tagesergebnis) -> None:
        if not res.verarbeitet:
            return
        with db.Transaction(conn):
            speicher.speichern(conn, d, z, res, lauf_id=test_id, datenstand=latest["id"], jetzt=now)
        counts["ereignisse"] += len(res.ereignisse)
        counts["orders"] += len(res.orders)
        counts["journal"] += len(res.journal)
        counts["schritte"] += 1

    sim_started = dt.datetime.now(dt.timezone.utc)
    result = backtest.laufen(defs, days, quelle, cfg=cfg, method=method, eintraege=eintraege, calendars=calendars,
                             stamm_fn=lambda isin: stamm.get(isin, {}), synthetisch=synthetisch, archiv=archiv, nach_schritt=save)
    sim_s = (dt.datetime.now(dt.timezone.utc) - sim_started).total_seconds()
    payload = stand.bauen(conn, D=D, snapshot_id=latest["id"], modus=modus, now=now, eintraege=eintraege, method=method, cfg=cfg, stamm=stamm, market=market)
    with db.Transaction(conn):
        size = stand.speichern(conn, payload, key, now)
    summary = {
        "test_id": test_id, "tage": len(days), "von": backtest.datum(days[0]), "bis": backtest.datum(days[-1]), "depots": len(defs),
        "archiviert": archived, "aktien": len(inputs), "ausgelassen": skipped, "lineal_fenster": window, **counts,
        "rechnungen": quelle.rechnungen, "sekunden": {"laden": round(load_s, 1), "simulation": round(sim_s, 1), "rechenkern": round(quelle.rechenzeit_s, 1)},
        "stand": payload["id"], "stand_bytes": size, "hinweise": result.hinweise,
        "kennzahlen": {d.id.removeprefix(PREFIX).rsplit("-", 1)[0]: result.kennzahlen[d.id] for d in defs},
    }
    log(f"Historische Simulation: {len(days)} Handelstage, {len(defs)} Depots, {counts['ereignisse']} Buchungen, {counts['orders']} Orders; "
        f"Rechenkern {quelle.rechnungen}× in {quelle.rechenzeit_s:.1f} s, gesamt {sim_s:.1f} s; Stand {payload['id']} ({size} Bytes)")
    return summary
