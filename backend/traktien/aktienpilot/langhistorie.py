"""Längere Kurshistorie für den Forschungslauf des Depot-Optimierers (Auftrag vom 31.10.2026, 20:16 Uhr, Punkt 1).

Untersucht und genutzt werden nur kostenlose Quellen, die die App schon verwendet:

* **Tageskurse**: dieselben Chart-Abrufe wie im täglichen Lauf (Hauptquelle), nur mit früherem Beginn. Ältere Kerzen ergänzen
  die Arbeitskopie des Zustands im Forschungslauf vor der ersten gespeicherten Kerze derselben Datenrevision – vorhandene,
  im täglichen Lauf geprüfte Kerzen werden nie ersetzt. Die Arbeitskopie wird nicht zurückgeschrieben; der tägliche Lauf und
  seine Prüfungen bleiben, wie sie sind.
* **Wechselkurse**: EZB-Referenzkurse seit 1999 (eine ZIP-Datei).

Kostenpflichtige Anbieter (z. B. EODHD) bleiben ohne Freigabe aus. Ergebnis sind nur Zählungen: wie viele Aktien wie viele
Jahre Historie haben – das bestimmt, welche Prognosehorizonte prüfbar sind.
"""

from __future__ import annotations

import dataclasses
import time
from typing import Callable

import numpy as np

from ..providers.base import HistoryJob, NoDataError, ProviderThrottled
from ..store import repo

JAHR = 365.25


def _ausschnitt(history, keep: np.ndarray):
    """Kerzen ``keep`` einer Kursreihe (alle Spalten gleich geschnitten)."""
    arrays = {}
    for name in ("days", "open", "high", "low", "close", "volume"):
        arrays[name] = np.asarray(getattr(history, name))[keep]
    for name in ("close_raw", "close_total"):
        v = getattr(history, name)
        arrays[name] = None if v is None else np.asarray(v)[keep]
    times = list(history.bar_times_utc or [])
    idx = np.nonzero(keep)[0]
    arrays["bar_times_utc"] = [times[i] if i < len(times) else None for i in idx]
    return dataclasses.replace(history, **arrays)


def ergaenzen(conn, provider, calendars, *, members: dict, bis: int, jahre: float, workers: int = 1, intervall_s: float = 0.25,
              budget_s: float = 3600.0, log: Callable[[str], None] | None = None) -> dict:
    """Kerzen von ``bis − jahre`` bis vor die erste gespeicherte Kerze laden (Arbeitskopie). Rückgabe: Zählungen."""
    start = int(bis - round(jahre * JAHR))
    refs = repo.reference_listings(conn)
    rows = repo.instruments(conn, members)
    jobs: list[HistoryJob] = []
    plan: list[tuple[int, int, int]] = []  # (listing_id, revision, erste gespeicherte Kerze)
    schon_lang = 0
    for isin in sorted(members):
        row, listing = rows.get(isin), refs.get(isin)
        if not members[isin]["valid"] or row is None or listing is None or row["identity_status"] != "verifiziert":
            continue
        code = listing["calendar_code"]
        if not code or calendars is None or not calendars.available(code):
            continue
        revision = int(listing["data_revision"])
        first, _last, n = repo.bar_range(conn, listing["id"], revision)
        if first is None or n == 0:
            continue
        if int(first) <= start + 7:
            schon_lang += 1
            continue
        jobs.append(HistoryJob(listing["provider_symbol"], start, int(first) - 1, None))
        plan.append((int(listing["id"]), revision, int(first)))
    zaehlung = {"aktien": len(jobs) + schon_lang, "abgerufen": 0, "ergaenzt": 0, "kerzen": 0, "ohne_daten": 0, "fehler": 0, "schon_lang": schon_lang,
                "gedrosselt": False, "abgebrochen": False}
    started = time.monotonic()
    parallel = getattr(provider, "fetch_histories", None)
    outcomes = parallel(jobs, workers=workers, interval_s=intervall_s) if callable(parallel) else (
        (k, _einzeln(provider, job)) for k, job in enumerate(jobs))
    try:
        for k, outcome in outcomes:
            if time.monotonic() - started > budget_s:
                zaehlung["abgebrochen"] = True
                break
            zaehlung["abgerufen"] += 1
            listing_id, revision, first = plan[k]
            if isinstance(outcome, ProviderThrottled):
                zaehlung["gedrosselt"] = True
                break
            if isinstance(outcome, NoDataError):
                zaehlung["ohne_daten"] += 1
                continue
            if isinstance(outcome, BaseException):
                zaehlung["fehler"] += 1
                continue
            keep = np.asarray(outcome.days) < first
            if not keep.any():
                zaehlung["ohne_daten"] += 1
                continue
            n = repo.store_bars(conn, listing_id, revision, _ausschnitt(outcome, keep))
            zaehlung["ergaenzt"] += 1
            zaehlung["kerzen"] += int(n)
            if log is not None and zaehlung["abgerufen"] % 1000 == 0:
                log(f"Langhistorie: {zaehlung['abgerufen']} von {len(jobs)} abgerufen, {zaehlung['ergaenzt']} ergänzt")
    finally:
        closer = getattr(outcomes, "close", None)
        if callable(closer):
            closer()
    conn.commit()
    zaehlung["sekunden"] = round(time.monotonic() - started, 1)
    zaehlung["jahre"] = historie_jahre(conn, members, bis)
    return zaehlung


def _einzeln(provider, job: HistoryJob):
    try:
        return provider.fetch_history(job.symbol, job.start_day, job.end_day)
    except Exception as exc:  # noqa: BLE001 – wie im täglichen Lauf: Einzelfehler isoliert
        return exc


def historie_jahre(conn, members: dict, bis: int) -> dict:
    """Wie viele Aktien (Referenznotierung, geprüfte Identität) wie viele Jahre Tageskurse haben (bis ``bis``)."""
    refs = repo.reference_listings(conn)
    rows = repo.instruments(conn, members)
    stufen = {"ab_1": 0, "ab_2": 0, "ab_3": 0, "ab_5": 0, "ab_10": 0}
    gesamt = 0
    for isin in members:
        row, listing = rows.get(isin), refs.get(isin)
        if not members[isin]["valid"] or row is None or listing is None or row["identity_status"] != "verifiziert":
            continue
        first, _last, n = repo.bar_range(conn, listing["id"], int(listing["data_revision"]))
        if first is None or n == 0:
            continue
        gesamt += 1
        jahre = (bis - int(first)) / JAHR
        for schwelle in (1, 2, 3, 5, 10):
            if jahre >= schwelle - 0.02:
                stufen[f"ab_{schwelle}"] += 1
    return {"aktien": gesamt, **stufen}


def wechselkurse_ergaenzen(conn, fx_provider, *, von: int) -> int:
    """EZB-Referenzkurse ab ``von`` in die Arbeitskopie (vorhandene Tage bleiben). Rückgabe: Zahl der gespeicherten Zeilen."""
    row = conn.execute("SELECT MIN(day) FROM fx_rate").fetchone()
    erster = int(row[0]) if row and row[0] is not None else None
    fetch = fx_provider.fetch_history(von)
    rows = [r for r in fetch.rows if int(r[0]) >= von and (erster is None or int(r[0]) < erster)]
    n = repo.store_fx_rates(conn, rows, source="EZB-Kurshistorie (Forschungslauf)", fetched_at=str(fetch.fetched_at or ""))
    conn.commit()
    return n


def marktreihen_ergaenzen(conn, provider, cfg, *, bis: int, jahre: float) -> dict:
    """Ältere Kerzen der Vergleichs-ETFs und Leitindizes (Welt-ETF, Geldmarkt, Marktfilter) in die Arbeitskopie – dieselbe
    Tabelle wie der tägliche Lauf, nur vor der ersten gespeicherten Kerze. Rückgabe: Kerzen je Symbol."""
    from .tageslauf import symbole

    start = int(bis - round(jahre * JAHR))
    out = {}
    for symbol in sorted(symbole(cfg)):
        row = conn.execute("SELECT MIN(tag) FROM ap_marktreihe WHERE symbol = ?", (symbol,)).fetchone()
        first = int(row[0]) if row and row[0] is not None else int(bis) + 1
        if first <= start + 7:
            out[symbol] = 0
            continue
        try:
            history = provider.fetch_history(symbol, start, first - 1)
        except Exception:  # noqa: BLE001 – ohne ältere Kerzen bleibt der Vergleich kürzer (im Ergebnis sichtbar)
            out[symbol] = -1
            continue
        rows = []
        for k, day in enumerate(np.asarray(history.days).tolist()):
            close = float(history.close[k])
            if int(day) >= first or not (close == close and close > 0):
                continue

            def num(arr):
                v = float(arr[k]) if arr is not None and k < len(arr) else float("nan")
                return v if v == v else None
            rows.append((symbol, int(day), num(history.open), num(history.high), num(history.low), close, num(history.volume), history.currency, "Forschungslauf"))
        conn.executemany("INSERT OR IGNORE INTO ap_marktreihe(symbol, tag, open, high, low, close, volume, waehrung, abgerufen_am) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", rows)
        out[symbol] = len(rows)
    conn.commit()
    return out

