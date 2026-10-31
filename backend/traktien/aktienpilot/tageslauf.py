"""Spielgeld-Robo im täglichen Lauf (Abschnitte 18, 29.5): Marktdaten, Ranglistenarchiv, alle Depots, Veröffentlichung.

Aufruf aus ``jobs.daily.DailyRun.publish`` nach der Berechnung der Ranglisten – mit **derselben** ``SnapshotComputation``,
die veröffentlicht wird. Ein Fehler hier verhindert nie die Veröffentlichung der Ranglisten (der Aufrufer fängt ihn ab); jedes
Depot hat eine eigene Transaktion, ein Stichtag wird je Depot genau einmal verarbeitet.

Schritte:

1. Kursreihen außerhalb des TR-Aktienuniversums aktualisieren: Leitindizes des Marktfilters und Kern-ETFs (``ap_marktreihe``).
2. Tageskerzen des Universums aus dem Zustand laden; Schlusskurse aus der Rechnung (nach Kursabgleich) übernehmen, damit
   Rangliste und Robo dieselben Kurse sehen.
3. Spitzenplätze dieses Standes archivieren (Variante B „Platz 1 an vergangenen Stichtagen“).
4. Depots aus der Konfiguration und gespeicherte Depots je Tagesschritt verarbeiten und speichern.
5. Den Stand für die App verschlüsselt ablegen (``ap_stand``); ``build_status_file`` legt ihn in die Website.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import sqlite3
import zlib
from dataclasses import dataclass

import numpy as np

from ..analytics.fx import FxRates
from ..config import CANONICAL_WEIGHTS, MethodConfig
from ..providers.base import NoDataError, ProviderError
from ..store import db
from ..util import crypto
from ..util.timeutil import day_to_date
from . import katalog as kat
from . import eingang, motor, regeln, speicher, stand, vorlagen
from .config import AktienPilotConfig
from .markt import Market, Series

MARKTREIHE_TAGE = 450
AKTIENKLASSEN = ("stammaktie", "vorzugsaktie", "adr_gdr", "reit")
ARCHIV_TAGE = 120
STAENDE_BEHALTEN = 3


def _iso(value: dt.datetime) -> str:
    return value.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ------------------------------------------------------------------------------------------------ Kursreihen Index/ETF


def symbole(cfg: AktienPilotConfig) -> dict[str, dict]:
    """Benötigte Reihen: Kern-ETFs (mit ISIN) und Leitindizes (Symbol), mit Börsenkalender."""
    out: dict[str, dict] = {}
    for inst in (cfg.msci_world, cfg.geldmarkt):
        if inst is not None:
            out[inst.symbol] = {"art": "etf", "isin": inst.isin, "name": inst.name, "waehrung": inst.waehrung, "kalender": "XETR" if inst.symbol.endswith(".DE") else None}
    us = {"US", "XNYS", "XNAS"}
    for mic, symbol in sorted(cfg.marktfilter.leitindex.items()):
        info = out.setdefault(symbol, {"art": "index", "isin": None, "name": symbol, "waehrung": None, "kalender": None})
        info["kalender"] = info["kalender"] or ("XNYS" if mic in us else mic)
    return out


def marktreihen_abrufen(conn: sqlite3.Connection, provider, cfg: AktienPilotConfig, D: int, now: dt.datetime) -> dict[str, str]:
    """Neue Tageskerzen je Symbol holen und speichern; Fehler lassen die gespeicherten Kerzen unverändert."""
    status: dict[str, str] = {}
    stamp = _iso(now)
    for symbol in sorted(symbole(cfg)):
        last = conn.execute("SELECT MAX(tag) FROM ap_marktreihe WHERE symbol = ?", (symbol,)).fetchone()[0]
        if last is not None and int(last) >= D:
            status[symbol] = "aktuell"
            continue
        start = int(last) - 10 if last is not None else D - MARKTREIHE_TAGE
        try:
            history = provider.fetch_history(symbol, start, D)
        except NoDataError:
            status[symbol] = "keine_daten"
            continue
        except (ProviderError, OSError, ValueError) as exc:
            status[symbol] = f"fehler:{type(exc).__name__}"
            continue
        rows = []
        for k, day in enumerate(history.days.tolist()):
            close = float(history.close[k])
            if not (math.isfinite(close) and close > 0) or int(day) > D:
                continue
            def num(arr):
                v = float(arr[k]) if arr is not None and k < len(arr) else math.nan
                return v if math.isfinite(v) else None
            rows.append((symbol, int(day), num(history.open), num(history.high), num(history.low), close * 1.0, num(history.volume),
                         history.currency, stamp))
        with db.Transaction(conn):
            conn.executemany(
                "INSERT INTO ap_marktreihe(symbol, tag, open, high, low, close, volume, waehrung, abgerufen_am) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(symbol, tag) DO UPDATE SET open = excluded.open, high = excluded.high, low = excluded.low, close = excluded.close, "
                "volume = excluded.volume, waehrung = excluded.waehrung, abgerufen_am = excluded.abgerufen_am", rows)
            conn.execute("DELETE FROM ap_marktreihe WHERE symbol = ? AND tag < ?", (symbol, D - 2 * MARKTREIHE_TAGE))
        status[symbol] = f"{len(rows)} Kerzen"
    return status


def marktreihen_laden(conn: sqlite3.Connection, cfg: AktienPilotConfig, von: int, bis: int, synthetisch: bool) -> tuple[dict[str, Series], dict[str, Series]]:
    """(Kern-ETFs je ISIN, Leitindizes je Symbol) aus ``ap_marktreihe``."""
    etfs: dict[str, Series] = {}
    indices: dict[str, Series] = {}
    for symbol, info in symbole(cfg).items():
        rows = conn.execute("SELECT tag, open, high, low, close, volume, waehrung FROM ap_marktreihe WHERE symbol = ? AND tag BETWEEN ? AND ? ORDER BY tag",
                            (symbol, von, bis)).fetchall()
        if not rows:
            continue
        def col(i):
            return np.array([np.nan if r[i] is None else float(r[i]) for r in rows], dtype=np.float64)
        currency = info.get("waehrung") or rows[-1][6] or "EUR"
        s = Series(info.get("isin") or symbol, np.array([int(r[0]) for r in rows], dtype=np.int64), col(1), col(2), col(3), col(4), col(5),
                   currency=currency, exchange=info.get("kalender") or "", calendar=info.get("kalender"), name=info.get("name") or symbol,
                   sector="Fonds" if info["art"] == "etf" else None, synthetic=synthetisch)
        if info["art"] == "etf":
            etfs[info["isin"]] = s
        else:
            indices[symbol] = s
    return etfs, indices


# ------------------------------------------------------------------------------------------------ Aktienreihen


def aktienreihen_laden(conn: sqlite3.Connection, comp, metas, von: int, bis: int, synthetisch: bool) -> dict[str, Series]:
    """Tageskerzen aller Referenznotierungen (ein Abruf); Schlusskurse aus der Rechnung, wo vorhanden (nach Kursabgleich)."""
    meta_by_isin = {m.isin: m for m in metas}
    refs = conn.execute(
        "SELECT i.isin, l.id, l.data_revision FROM listing l JOIN instrument i ON i.id = l.instrument_id WHERE l.is_reference = 1").fetchall()
    wanted = {int(r[1]): (r[0], int(r[2] or 0)) for r in refs if r[0] in meta_by_isin}
    data: dict[int, list] = {}
    for row in conn.execute(
            "SELECT b.listing_id, b.revision, b.session_day, b.open, b.high, b.low, b.close_split, b.volume FROM daily_bar b "
            "JOIN listing l ON l.id = b.listing_id AND b.revision = l.data_revision WHERE l.is_reference = 1 AND b.session_day BETWEEN ? AND ? "
            "ORDER BY b.listing_id, b.session_day", (von, bis)):
        if int(row[0]) in wanted:
            data.setdefault(int(row[0]), []).append(row)
    splits_by_listing: dict[int, list[tuple[int, float]]] = {}
    for lid, ex_day, factor in conn.execute("SELECT listing_id, ex_day, factor FROM corporate_action WHERE kind = 'split' AND factor IS NOT NULL ORDER BY ex_day"):
        splits_by_listing.setdefault(int(lid), []).append((int(ex_day), float(factor)))
    observed = getattr(comp, "observed", {}) or {}
    index = {isin: k for k, isin in enumerate(comp.isins)}
    out: dict[str, Series] = {}
    for lid, rows in data.items():
        isin, _rev = wanted[lid]
        meta = meta_by_isin[isin]
        days = np.array([int(r[2]) for r in rows], dtype=np.int64)
        def col(i):
            return np.array([np.nan if r[i] is None else float(r[i]) for r in rows], dtype=np.float64)
        opn, high, low, close, vol = col(3), col(4), col(5), col(6), col(7)
        k = index.get(isin)
        obs = observed.get(k) if k is not None else None
        if obs is not None and len(obs.days):
            pos = np.searchsorted(days, obs.days)
            ok = (pos < len(days)) & (days[np.minimum(pos, len(days) - 1)] == obs.days)
            for p, c in zip(pos[ok], np.asarray(obs.close)[ok]):
                if close[p] != c:
                    close[p] = c  # Kurs nach Kursabgleich – Eröffnung/Hoch/Tief dieses Tages sind dann nicht verlässlich
                    opn[p] = high[p] = low[p] = np.nan
        currency = meta.currency or "EUR"
        unit = float(meta.unit_factor or 1.0)
        splits = tuple(splits_by_listing.get(lid, ()))
        try:
            out[isin] = Series(isin, days, opn, high, low, close, vol, currency=_basiswaehrung(currency), unit_factor=unit, exchange=meta.mic or meta.exchange_key or "",
                               calendar=meta.calendar, name=meta.name, splits=splits, synthetic=synthetisch)
        except ValueError:
            continue
    return out


def _basiswaehrung(currency: str) -> str:
    return {"GBp": "GBP", "GBX": "GBP", "ZAc": "ZAR", "ILA": "ILS"}.get(currency, currency)


# ------------------------------------------------------------------------------------------------ Stammdaten und Fakten


def stammdaten(conn: sqlite3.Connection, metas, cfg: AktienPilotConfig) -> dict[str, dict]:
    facts = {}
    for row in conn.execute("SELECT isin, payload FROM stock_facts WHERE payload IS NOT NULL"):
        try:
            facts[row[0]] = json.loads(row[1])
        except ValueError:
            continue
    out: dict[str, dict] = {}
    for m in metas:
        branche = ((facts.get(m.isin) or {}).get("branche") or {}).get("sektor")
        # Klassen der Identitätsprüfung (providers/identity.py): Einzelaktien sind kaufbar; „unklar“ und Fonds/Optionsscheine
        # aus dem Aktienuniversum nicht (Abschnitt 31.5: nur zulässige Instrumente; der Kern kauft seine ETFs gesondert)
        typ = "aktie" if m.instrument_type in AKTIENKLASSEN else (m.instrument_type or "unklar")
        out[m.isin] = {"name": m.name, "branche": branche, "mic": m.mic or m.exchange_key, "boerse": m.mic or m.exchange_key,
                       "waehrung": _basiswaehrung(m.currency or "EUR"), "typ": typ, "ticker": m.ticker}
    for inst in (cfg.msci_world, cfg.geldmarkt):
        if inst is not None:
            out[inst.isin] = {"name": inst.name, "branche": "Fonds", "mic": "XETR", "boerse": "XETR", "waehrung": inst.waehrung, "typ": "etf", "ticker": inst.symbol}
    return out


def fakten_zum_tag(conn: sqlite3.Connection, D: int, series: dict[str, Series]) -> dict[str, dict]:
    """Analystenkonsens je ISIN, wie er am Tag ``D`` bekannt war (letzter Abruftag ≤ D); Kursziel in Basiswährung."""
    out: dict[str, dict] = {}
    rows = conn.execute(
        "SELECT t.isin, t.day, t.target_mean, t.analysts FROM target_history t JOIN (SELECT isin, MAX(day) AS d FROM target_history WHERE day <= ? GROUP BY isin) x "
        "ON x.isin = t.isin AND x.d = t.day", (D,)).fetchall()
    for isin, day, target, analysts in rows:
        s = series.get(isin)
        if s is None or target is None or not (float(target) > 0):
            continue
        k = s.upto(D)
        if k < 0:
            continue
        target_base = float(target) * s.unit_factor
        ratio = target_base / (float(s.close[k]) * s.unit_factor)
        if not (0.05 < ratio < 20):
            continue  # Einheit unklar (z. B. Pence gegen Pfund) – nicht vergleichbar statt eines falschen Abstands
        out[isin] = {"ziel_mittel": target_base, "ziel_waehrung": s.currency, "analysten": analysts, "ziel_tag": int(day)}
    return out


# ------------------------------------------------------------------------------------------------ Ranglistenarchiv (Variante B)


def rang_archiv_schluessel(gruppe: str, politik: str, h: int, w: int) -> str:
    """Schlüssel einer Spitzenliste; 10/90 … 100/0 sind in beiden Vergleichsfeldern identisch und nur unter „native“ abgelegt."""
    if politik == "common_trend" and w != 0:
        politik = "native"
    return f"{gruppe}|{politik}|{h}|{w}"


def rang_archiv_inhalt(comp, top: int = 10) -> dict[str, list[str]]:
    """Top ``top`` je Zeitraum, Gewichtung, Gruppe und Vergleichsfeld einer Rechnung (veröffentlicht oder nachgerechnet)."""
    content: dict[str, list[str]] = {}
    for h, wr in comp.rankings.items():
        for gruppe, src in (("A", wr), ("B", wr.group_b)):
            if src is None:
                continue
            for w in CANONICAL_WEIGHTS:
                content[rang_archiv_schluessel(gruppe, "native", h, w)] = [comp.isins[int(i)] for i in src.ranking("native", w).order[:top]]
            content[rang_archiv_schluessel(gruppe, "common_trend", h, 0)] = [comp.isins[int(i)] for i in src.ranking("common_trend", 0).order[:top]]
    return content


def rang_archiv_schreiben(conn: sqlite3.Connection, comp, snapshot_id: str, now: dt.datetime, top: int = 10) -> int:
    """Spitzenplätze dieses veröffentlichten Standes; je Stichtag einmal (spätere Revision ersetzt)."""
    blob = zlib.compress(json.dumps(rang_archiv_inhalt(comp, top), separators=(",", ":")).encode("utf-8"), 9)
    with db.Transaction(conn):
        conn.execute("INSERT INTO ap_rang_archiv(tag, snapshot_id, inhalt, erstellt_am) VALUES (?, ?, ?, ?) "
                     "ON CONFLICT(tag) DO UPDATE SET snapshot_id = excluded.snapshot_id, inhalt = excluded.inhalt, erstellt_am = excluded.erstellt_am",
                     (int(comp.cutoff_day), snapshot_id, blob, _iso(now)))
        conn.execute("DELETE FROM ap_rang_archiv WHERE tag < ?", (int(comp.cutoff_day) - ARCHIV_TAGE * 7 // 5,))
    return len(blob)


class RangArchiv:
    """Lesezugriff für ``auswertung.kandidaten`` (Variante B)."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self._cache: dict[int, dict] = {}

    def letzte_tage(self, tag: int, n: int) -> list[int]:
        rows = self.conn.execute("SELECT tag FROM ap_rang_archiv WHERE tag <= ? ORDER BY tag DESC LIMIT ?", (int(tag), int(n))).fetchall()
        return sorted(int(r[0]) for r in rows)

    def top(self, tag: int, gruppe: str, politik: str, h: int, w: int, n: int) -> list[str]:
        data = self._cache.get(tag)
        if data is None:
            row = self.conn.execute("SELECT inhalt FROM ap_rang_archiv WHERE tag = ?", (int(tag),)).fetchone()
            data = json.loads(zlib.decompress(row[0])) if row else {}
            self._cache[tag] = data
        return list(data.get(rang_archiv_schluessel(gruppe, politik, h, w), []))[:n]


# ------------------------------------------------------------------------------------------------ Depots


@dataclass(frozen=True)
class Testprofil:
    name: str
    welt: float
    geldmarkt: float
    bestaetigt: bool


def depots_definieren(cfg: AktienPilotConfig, method: MethodConfig, eintraege: dict, start_tag: int, *, synthetisch: bool,
                      testprofil: Testprofil | None = None, einrichtung: dict | None = None) -> list[motor.DepotDef]:
    """Depots aus der Konfiguration: Pilotdepot (Kern + aktive Strategien), Forschungsdepots je Vorlage, Vergleichsdepots.
    ``einrichtung`` (aus der App, Abschnitt 29.2): Startkapital, Testprofil und aktiver Anteil des Pilotdepots; die
    Vergleichsdepots bekommen dasselbe Startkapital. Ändert sie sich, beginnt ein neuer Test (neue Depot-Kennung)."""
    if einrichtung is not None and testprofil is None:
        p = einrichtung["profil"]
        testprofil = Testprofil(p["name"], float(p["welt"]), float(p["geldmarkt"]), True)
    templates = {}
    for name, r in vorlagen.alle(cfg).items():
        p = regeln.pruefen(r, eintraege, method)
        if not p.gueltig:
            raise ValueError(f"Vorlage {name} ungültig: {[f.as_dict() for f in p.fehler]}")
        templates[name] = p.regel
    capital = float(cfg.depot.demo_startkapital_eur)
    prefix = "demo-" if synthetisch else ""
    out: list[motor.DepotDef] = []
    for name in ("lineal", "s1", "s2", "s3", "platz1", "platz1_leiter", "gleichmaessigkeit", "haeufigkeit"):
        r = templates[name]
        out.append(motor.DepotDef(f"{prefix}f-{name}", r["name"], "forschung", capital, start_tag, 1.0,
                                  (motor.StrategieDef(r["id"], r, 1.0),), None, synthetisch, r.get("beschreibung", "")))
    welt = cfg.msci_world.isin if cfg.msci_world else None
    geld = cfg.geldmarkt.isin if cfg.geldmarkt else None
    pilot_capital = float(einrichtung["startkapital_eur"]) if einrichtung is not None else capital
    active_share = min(float(einrichtung["aktiver_anteil"]), cfg.depot.aktiver_anteil_max) if einrichtung is not None else cfg.depot.aktiver_anteil_max
    if welt:
        out.append(motor.DepotDef(f"{prefix}v-welt", f"Vergleich: {cfg.msci_world.name} kaufen und halten", "vergleich", pilot_capital, start_tag, 0.0,
                                  (), motor.KernDef({welt: 1.0}, cfg.s4.rebalancing_schwelle_pp, False), synthetisch,
                                  "Benchmark mit identischem Startkapital, ohne Umschichtung"))
    profile = testprofil or Testprofil("Vorgabe Ausgewogen (nicht bestätigt)", 0.70, 0.30, False)
    if welt and geld:
        ziele = {welt: profile.welt, geld: profile.geldmarkt} if profile.geldmarkt > 0 else {welt: 1.0}
        kern = motor.KernDef(ziele, cfg.s4.rebalancing_schwelle_pp, True)
        shares = cfg.budget_aktiv
        strategies = tuple(motor.StrategieDef(templates[n]["id"], templates[n], float(shares[n])) for n in ("s1", "s2", "s3"))
        out.append(motor.DepotDef(f"{prefix}pilot", "Pilotdepot (Spielgeld)", "pilot", pilot_capital, start_tag, active_share,
                                  strategies, kern, synthetisch, f"Robo-Kern {profile.name}: Welt {profile.welt:.0%} / Geldmarkt {profile.geldmarkt:.0%}; "
                                  f"höchstens {active_share:.0%} aktive Strategien S1/S2/S3"))
        out.append(motor.DepotDef(f"{prefix}v-kern", f"Vergleich: Robo-Kern {profile.name} ohne aktive Strategien", "vergleich", pilot_capital, start_tag, 0.0,
                                  (), kern, synthetisch, "Risikogerechte Kern-Referenz mit derselben Aktien-/Geldmarktquote"))
    return out


# ------------------------------------------------------------------------------------------------ Lauf


def ausfuehren(conn: sqlite3.Connection, *, cfg: AktienPilotConfig, method: MethodConfig, comp, metas, D: int, fx: FxRates | None,
               calendars, provider, run_id: str, now: dt.datetime, key: crypto.KeyMaterial | None, snapshot_id: str, data_mode: str,
               log=None, eingaenge=None) -> dict:
    """Ein Datenstichtag für alle Spielgelddepots. Rückgabe: Zusammenfassung nur mit Zahlen (für öffentliche Protokolle)."""
    def note(text: str) -> None:
        if log is not None:
            log(text)

    if not cfg.aktiv:
        return {"status": "aus"}
    synthetisch = data_mode == "demo"
    modus = "DEMO" if synthetisch else "PAPER"
    status_reihen = marktreihen_abrufen(conn, provider, cfg, D, now)
    von = D - MARKTREIHE_TAGE
    series = aktienreihen_laden(conn, comp, metas, von, D, synthetisch)
    etfs, indices = marktreihen_laden(conn, cfg, von, D, synthetisch)
    series.update(etfs)
    market = Market(series=series, fx=fx, indices=indices, synthetic=synthetisch, data_stand=snapshot_id, source="Zustand (Tageskerzen) und Kursreihen")
    stamm = stammdaten(conn, metas, cfg)
    fakten = fakten_zum_tag(conn, D, series)
    eintraege = kat.katalog(method, cfg)
    rang_archiv_schreiben(conn, comp, snapshot_id, now)
    archiv = RangArchiv(conn)
    base = kat.Kontext(tag=D, isins=list(comp.isins), method=method, comp=comp, markt=market, cfg=cfg, stamm=stamm, fakten=fakten,
                       modus="demo" if synthetisch else "paper")
    usd = market.eur_rate("USD", D)
    turnover = {}
    for k, t in enumerate(comp.turnover or ()):
        if t is not None and t.determined and usd:
            turnover[comp.isins[k]] = float(t.avg_usd) * usd  # USD → EUR mit dem EZB-Kurs des Stichtags

    # Eingänge aus der App (eigene Regeln, Pause/Fortsetzen): vor den Depots, damit sie für diesen Stichtag gelten
    status_eingang = {"neu": 0}
    if eingaenge is not None:
        try:
            items = eingaenge()
        except Exception as exc:  # Abruf gescheitert: kein Eingang geht verloren, er bleibt auf dem Branch liegen
            note(f"Eingänge aus der App nicht abrufbar ({type(exc).__name__})")
            items = []
        if items:
            with db.Transaction(conn):
                status_eingang = eingang.verarbeiten(conn, items, key=key, eintraege=eintraege, method=method, cfg=cfg, D=D, synthetisch=synthetisch,
                                                     now=now, log=note)
    existing = {d.id: info for d, info in speicher.depots(conn, nur_aktive=False)}
    start_tag = D
    defs = depots_definieren(cfg, method, eintraege, start_tag, synthetisch=synthetisch, einrichtung=eingang.einrichtung(conn))
    defs += [d for d, info in eingang.eigene_depots(conn) if info["modus"] == modus]  # eigene Regeln aus der App
    processed = 0
    created = 0
    events = 0
    orders = 0
    for d in defs:
        base_id = d.id
        info = existing.get(base_id)
        if base_id.startswith(eingang.PREFIX):
            pass  # eigene Regel: Definition steht schon im Zustand (kein Abgleich mit der Konfiguration)
        elif info is not None:
            stored = conn.execute("SELECT definition_json, start_tag FROM ap_depot WHERE id = ?", (base_id,)).fetchone()
            definition = json.loads(stored[0])
            d = motor.DepotDef(d.id, d.name, d.art, d.startkapital_eur, int(stored[1]), d.aktiver_anteil, d.strategien, d.kern, d.synthetisch, d.beschreibung)
            if speicher.depot_anlegen(conn, d, modus=modus, test_id=info["test_id"], jetzt=now) == "geaendert" or info["status"] == "archiviert":
                # Regel- oder Kernänderung: alter Test bleibt archiviert, ein neuer startet mit neuer ID (Abschnitt 29.8)
                speicher.depot_archivieren(conn, base_id, now)
                sha = hashlib.sha256(json.dumps(speicher.definition_json(d), sort_keys=True).encode()).hexdigest()[:6]
                d = motor.DepotDef(f"{base_id}-{sha}", d.name, d.art, d.startkapital_eur, start_tag, d.aktiver_anteil, d.strategien, d.kern, d.synthetisch, d.beschreibung)
                if conn.execute("SELECT 1 FROM ap_depot WHERE id = ?", (d.id,)).fetchone() is None:
                    speicher.depot_anlegen(conn, d, modus=modus, test_id=f"{d.id}@{_datum(start_tag)}", jetzt=now)
                    created += 1
                else:
                    stored = conn.execute("SELECT start_tag FROM ap_depot WHERE id = ?", (d.id,)).fetchone()
                    d = motor.DepotDef(d.id, d.name, d.art, d.startkapital_eur, int(stored[0]), d.aktiver_anteil, d.strategien, d.kern, d.synthetisch, d.beschreibung)
            del definition
        else:
            speicher.depot_anlegen(conn, d, modus=modus, test_id=f"{d.id}@{_datum(start_tag)}", jetzt=now)
            created += 1
        z = speicher.zustand_laden(conn, d.id)
        u = motor.Umwelt(cfg=cfg, method=method, eintraege=eintraege, markt=market, tag=D, kontext=lambda: base, calendars=calendars, archiv=archiv,
                         umsatz_eur=lambda isin: turnover.get(isin), stamm=lambda isin: stamm.get(isin, {}), jetzt=now, veroeffentlicht=now,
                         modus="demo" if synthetisch else "paper", synthetisch=synthetisch, lauf_id=run_id)
        res = motor.tagesschritt(d, z, u)
        if res.verarbeitet:
            with db.Transaction(conn):
                speicher.speichern(conn, d, z, res, lauf_id=run_id, datenstand=snapshot_id, jetzt=now)
            processed += 1
            events += len(res.ereignisse)
            orders += len(res.orders)
    payload = stand.bauen(conn, D=D, snapshot_id=snapshot_id, modus=modus, now=now, eintraege=eintraege, method=method, cfg=cfg, stamm=stamm, market=market)
    with db.Transaction(conn):
        size = stand.speichern(conn, payload, key, now)
    summary = {"status": "ok", "depots": len(defs), "verarbeitet": processed, "neu": created, "ereignisse": events, "orders": orders,
               "eingaenge": status_eingang,
               "reihen": {"ok": sum(1 for v in status_reihen.values() if not v.startswith(("fehler", "keine"))), "fehler": sum(1 for v in status_reihen.values() if v.startswith(("fehler", "keine")))},
               "stand": payload["id"], "stand_bytes": size}
    note(f"Spielgeld: {processed} von {len(defs)} Depots verarbeitet, {events} Buchungen, {orders} Orders; Stand {payload['id']} ({size} Bytes)")
    return summary


def _datum(day: int) -> str:
    return day_to_date(int(day)).isoformat()
