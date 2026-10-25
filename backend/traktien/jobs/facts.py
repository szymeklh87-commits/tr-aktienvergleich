"""Kennzahlen, Kursziele und Signale je Aktie (ab 1.6).

``FactsJob`` holt je Aktie einen quoteSummary-Abruf (Kursziele, Empfehlungen, Analystenurteile,
Bewertung, Wachstum, Finanzen, Termine, Branche) – rotierend mit Zeitbudget, damit der tägliche Lauf
planbar bleibt. Reihenfolge: zuerst die vorderen Kandidaten des letzten Signal-Stands, dann Aktien
ohne Kennzahlen (umsatzstärkste zuerst), dann die ältesten. Für die vorderen Kandidaten kommen
Ergänzungen hinzu: Bewertung (Trading Central) und zweiter Kursziel-Konsens (Nasdaq) bei US-Aktien,
Nachrichten und – bei US-Aktien – die Community-Stimmung (Stocktwits).

``SignalsJob`` berechnet aus den Tageskursen bis zum Kursstichtag des neuesten Datenstands und den
gespeicherten Kennzahlen die Signale aller Aktien (``analytics.signals``) und schreibt einen
**Signal-Stand**: verschlüsselte Dateien, unabhängig vom Kurs-Datenstand aktualisierbar.
"""

from __future__ import annotations

import datetime as dt
import json
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from ..analytics import signals as sg
from ..analytics.fx import FxRates
from ..providers.base import NoDataError, ProviderError, ProviderThrottled
from ..providers.exchanges import ExchangeTable, unit_info
from ..store import repo
from ..util import crypto
from ..util.jsonio import atomic_write_json
from ..util.log import get_logger
from ..util.timeutil import date_to_day, day_to_iso, iso_utc, parse_iso_utc

LOG = get_logger(__name__)
US_KEYS = ("US",)


@dataclass
class FactsSettings:
    budget_s: float = 1200.0  # Kennzahlen je Lauf
    budget_initial_s: float = 2700.0  # solange viele Aktien noch keine Kennzahlen haben
    initial_threshold: int = 2000
    extras_budget_s: float = 480.0  # Ergänzungen für die vorderen Kandidaten
    ok_age_days: float = 3.0
    empty_age_days: float = 14.0
    missing_age_days: float = 30.0
    error_age_days: float = 1.0
    top_refresh_days: float = 1.0
    top_n: int = 300
    extras_top_n: int = 150
    community_max: int = 120
    news_age_hours: float = 12.0
    community_age_hours: float = 12.0
    valuation_age_days: float = 3.0
    nasdaq_age_days: float = 3.0

    @staticmethod
    def from_pipeline(pipeline) -> "FactsSettings":
        s = FactsSettings()
        for name, key in (
            ("budget_s", "kennzahlen.max_sekunden"),
            ("budget_initial_s", "kennzahlen.max_sekunden_erstbefuellung"),
            ("extras_budget_s", "kennzahlen.zusatz_max_sekunden"),
            ("ok_age_days", "kennzahlen.erneuern_nach_tagen"),
            ("top_n", "kennzahlen.kandidaten_taeglich"),
            ("extras_top_n", "kennzahlen.kandidaten_ergaenzungen"),
            ("community_max", "kennzahlen.community_max_pro_lauf"),
        ):
            value = pipeline.get(key, None)
            if value is not None:
                setattr(s, name, type(getattr(s, name))(value))
        return s


@dataclass
class FactsReport:
    """Ergebnis eines Kennzahlen-Laufs. ``with_facts`` zählt nur Aktien des aktuellen Universums (Bezugsmenge ``eligible``);
    ``stored_ok`` alle gespeicherten Kennzahlen, auch von Aktien, die derzeit nicht berücksichtigt sind (nicht mehr in der
    TR-Liste oder ohne geprüfte Identität bzw. Kursdaten). Bis 1.18.2 stand in der Meldung „11025 von 11006 Aktien mit
    Kennzahlen“: der erste Wert zählte alle gespeicherten, der zweite nur die berücksichtigten Aktien."""

    eligible: int = 0
    with_facts: int = 0
    stored_ok: int = 0
    fetched: int = 0
    empty: int = 0
    errors: int = 0
    never_left: int = 0
    stopped: str | None = None
    extras: dict = field(default_factory=dict)
    seconds: float = 0.0

    def message(self) -> str:
        extra = ", ".join(f"{k} {v}" for k, v in self.extras.items() if v)
        return (
            f"Kennzahlen: {self.fetched} abgerufen, {self.empty} ohne Daten, {self.errors} Fehler in {self.seconds:.0f} s; "
            f"Kennzahlen vorhanden für {self.with_facts} von {self.eligible} berücksichtigten Aktien, {self.never_left} noch nie abgerufen; "
            f"gespeichert für {self.stored_ok} Aktien, davon {max(0, self.stored_ok - self.with_facts)} derzeit nicht berücksichtigt"
            + (f"; Ergänzungen: {extra}" if extra else "")
            + (f" – {self.stopped}" if self.stopped else "")
        )


def eligible_stocks(conn) -> dict[str, dict]:
    """Aktien des aktuellen Universums mit geprüfter Identität und Kursdaten (ISIN → Referenznotierung)."""
    universe = repo.latest_universe(conn)
    if universe is None:
        return {}
    members = repo.universe_members(conn, universe["id"])
    instruments = repo.instruments(conn, members)
    refs = repo.reference_listings(conn)
    out = {}
    for isin in members:
        row = instruments.get(isin)
        listing = refs.get(isin)
        if row is None or listing is None or row["identity_status"] != "verifiziert":
            continue
        if not listing["provider_symbol"] or listing["last_fetch_status"] != "ok":
            continue
        out[isin] = dict(listing)
    return out


def latest_fx(conn, day: int) -> FxRates | None:
    rows = repo.fx_rates_since(conn, day - 40)
    if not rows:
        return None
    return FxRates.from_rows([(int(r["day"]), r["currency"], float(r["per_eur"])) for r in rows], source=rows[-1]["source"], url=None, fetched_at=None, max_age_days=14)


def eur_per_unit(fx: FxRates | None, unit: str | None, day: int) -> float | None:
    """EUR je Kurseinheit. Untereinheiten (GBp, ZAc, ILA) sind ein Hundertstel der Hauptwährung:
    1 GBp = 0,01 GBP. (Bis 1.9.2 wurde hier durch den Faktor geteilt statt mit ihm malgenommen – Umsätze in EUR
    von Aktien aus London, Johannesburg und Tel Aviv waren dadurch im Signal-Stand 10.000-fach zu hoch.)"""
    base, factor = unit_info(unit)
    if not base:
        return None
    if base == "EUR":
        return factor
    if fx is None:
        return None
    rate = fx.eur_per_unit(base, day)
    return None if rate is None else rate * factor


def recent_turnover_eur(conn, eligible: dict[str, dict], fx: FxRates | None, day: int) -> dict[str, float]:
    """Ø Umsatz (Kurs × Stück) der letzten 30 Tage in EUR – nur für die Reihenfolge des Erstabrufs."""
    rows = conn.execute(
        "SELECT b.listing_id, AVG(b.close_split * b.volume) AS t FROM daily_bar b JOIN listing l ON l.id = b.listing_id AND b.revision = l.data_revision "
        "WHERE b.session_day >= ? AND b.volume > 0 GROUP BY b.listing_id",
        (int(day) - 30,),
    ).fetchall()
    by_listing = {int(r["listing_id"]): float(r["t"] or 0.0) for r in rows}
    out = {}
    for isin, listing in eligible.items():
        value = by_listing.get(int(listing["id"]))
        rate = eur_per_unit(fx, listing["price_unit"] or listing["currency"], day)
        if value is not None and rate is not None:
            out[isin] = value * rate
    return out


def top_candidates(conn, limit: int) -> list[str]:
    """Vordere Kandidaten des letzten Signal-Stands (für tägliche Erneuerung und Ergänzungen)."""
    stands = repo.signal_stands(conn, 1)
    if not stands:
        return []
    try:
        summary = json.loads(stands[0]["summary_json"])
    except ValueError:
        return []
    return list(summary.get("kandidaten") or [])[:limit]


class FactsJob:
    def __init__(self, conn, *, provider, extra=None, settings: FactsSettings, now: dt.datetime, event=None) -> None:
        self.conn = conn
        self.provider = provider
        self.extra = extra
        self.settings = settings
        self.now = now
        self.event = event or (lambda step, message, level="INFO": LOG.info("[%s] %s", step, message))

    def plan(self, eligible: dict[str, dict], facts: dict, top: list[str], turnover: dict[str, float]) -> tuple[list[str], int]:
        s = self.settings
        top_set = set(top)
        never = sorted((i for i in eligible if i not in facts), key=lambda i: -(turnover.get(i) or 0.0))
        due_top, due_rest = [], []
        for isin, row in facts.items():
            if isin not in eligible:
                continue
            age = (self.now - parse_iso_utc(row["fetched_at"])).total_seconds() / 86400.0
            if row["status"] == "ok":
                has_analysts = '"anzahl":0' not in (row["payload"] or "")
                limit = s.top_refresh_days if isin in top_set else (s.ok_age_days if has_analysts else s.empty_age_days)
                if row["error"]:
                    limit = min(limit, s.error_age_days)
            elif row["status"] == "keine_daten":
                limit = s.missing_age_days
            else:
                limit = s.error_age_days
            if age >= limit - 1e-9:
                (due_top if isin in top_set else due_rest).append((isin, age))
        due_top.sort(key=lambda x: -x[1])
        due_rest.sort(key=lambda x: -x[1])
        return [i for i, _ in due_top] + never + [i for i, _ in due_rest], len(never)

    def run(self) -> FactsReport:
        started = time.monotonic()
        report = FactsReport()
        eligible = eligible_stocks(self.conn)
        report.eligible = len(eligible)
        if not eligible:
            report.stopped = "keine Aktien mit Kursdaten"
            return report
        today = date_to_day(self.now.date())
        fx = latest_fx(self.conn, today)
        facts = repo.facts_rows(self.conn)
        top = top_candidates(self.conn, self.settings.top_n)
        turnover = recent_turnover_eur(self.conn, eligible, fx, today)
        order, never = self.plan(eligible, facts, top, turnover)
        budget = self.settings.budget_initial_s if never >= self.settings.initial_threshold else self.settings.budget_s
        done_never = 0
        for isin in order:
            if time.monotonic() - started > budget:
                report.stopped = "Zeitbudget erreicht, Rest im nächsten Lauf"
                break
            listing = eligible[isin]
            symbol = listing["provider_symbol"]
            try:
                payload = self.provider.fetch_facts(symbol)
            except ProviderThrottled:
                report.stopped = "Kursanbieter drosselt, Rest im nächsten Lauf"
                break
            except NoDataError as exc:
                repo.save_facts(self.conn, isin, symbol, "keine_daten", None, error=str(exc), at=iso_utc(self.now))
                report.empty += 1
                done_never += isin not in facts
                continue
            except (ProviderError, ConnectionError, ValueError, KeyError, TypeError) as exc:
                repo.save_facts(self.conn, isin, symbol, "fehler", None, error=f"{type(exc).__name__}: {exc}", at=iso_utc(self.now))
                report.errors += 1
                continue
            repo.save_facts(self.conn, isin, symbol, "ok", payload, at=iso_utc(self.now))
            if (payload.get("analysten") or {}).get("anzahl"):
                repo.save_target_history(self.conn, isin, today, payload["analysten"])
            report.fetched += 1
            done_never += isin not in facts
        report.never_left = max(0, never - done_never)
        ok = {row[0] for row in self.conn.execute("SELECT isin FROM stock_facts WHERE status = 'ok'")}
        report.stored_ok = len(ok)
        report.with_facts = len(ok & set(eligible))
        if report.stopped is None or "Zeitbudget" in report.stopped:
            report.extras = self.run_extras(eligible, top or self.fallback_candidates(eligible, turnover))
        report.seconds = time.monotonic() - started
        return report

    def fallback_candidates(self, eligible: dict, turnover: dict) -> list[str]:
        """Ohne früheren Signal-Stand: Aktien mit Kurszielen, umsatzstärkste zuerst."""
        with_targets = [r["isin"] for r in self.conn.execute("SELECT isin, payload FROM stock_facts WHERE status = 'ok'") if '"anzahl":0' not in (r["payload"] or "")]
        return sorted((i for i in with_targets if i in eligible), key=lambda i: -(turnover.get(i) or 0.0))

    def run_extras(self, eligible: dict, candidates: list[str]) -> dict:
        s = self.settings
        started = time.monotonic()
        counts = {"bewertung": 0, "nasdaq": 0, "nachrichten": 0, "community": 0, "fehler": 0}
        rows = {kind: repo.extra_rows(self.conn, kind) for kind in ("bewertung", "nasdaq", "nachrichten", "community")}
        community_used = 0

        def age_h(kind: str, isin: str) -> float:
            row = rows[kind].get(isin)
            return 1e9 if row is None else (self.now - parse_iso_utc(row["fetched_at"])).total_seconds() / 3600.0

        stop = False
        for isin in candidates[: s.extras_top_n]:
            if stop or time.monotonic() - started > s.extras_budget_s:
                break
            listing = eligible.get(isin)
            if listing is None:
                continue
            symbol = listing["provider_symbol"]
            us = listing["exchange_key"] in US_KEYS
            tasks = []
            if us and age_h("bewertung", isin) >= s.valuation_age_days * 24:
                tasks.append(("bewertung", lambda sym=symbol: self.provider.fetch_insights(sym)))
            if us and self.extra is not None and age_h("nasdaq", isin) >= s.nasdaq_age_days * 24:
                tasks.append(("nasdaq", lambda sym=symbol: self.extra.nasdaq_targets(sym)))
            if age_h("nachrichten", isin) >= s.news_age_hours:
                query = symbol if us else (listing.get("provider_name") or symbol)
                tasks.append(("nachrichten", lambda q=query, sym=symbol, name=listing.get("provider_name"), us_=us: self._news(q, sym, name, us_)))
            if us and self.extra is not None and community_used < s.community_max and age_h("community", isin) >= s.community_age_hours:
                tasks.append(("community", lambda sym=symbol: self.extra.community(sym)))
                community_used += 1
            for kind, call in tasks:
                try:
                    payload = call()
                except ProviderThrottled:
                    if kind == "community":
                        community_used = s.community_max  # Stocktwits-Grenze erreicht: übrige ohne Community
                        continue
                    stop = True
                    break
                except NoDataError:
                    repo.save_extra(self.conn, isin, kind, "keine_daten", None, at=iso_utc(self.now))
                    continue
                except (ProviderError, ConnectionError, ValueError, KeyError, TypeError):
                    repo.save_extra(self.conn, isin, kind, "fehler", None, at=iso_utc(self.now))
                    counts["fehler"] += 1
                    continue
                repo.save_extra(self.conn, isin, kind, "ok" if payload else "keine_daten", payload if payload else None, at=iso_utc(self.now))
                counts[kind] += 1 if payload else 0
        return counts

    def _news(self, query: str, symbol: str, name: str | None, us: bool) -> list[dict]:
        items = self.provider.fetch_news(query)
        if us:
            return items
        # Suche nach Namen: nur Meldungen, deren Titel den ersten Namensteil enthält (sonst fremde Firmen)
        word = (name or "").split()[0].lower() if name else ""
        return [n for n in items if word and len(word) >= 3 and word in n["titel"].lower()]


# --------------------------------------------------------------------- Signal-Stand


def build_inputs(conn, *, cutoff_day: int, table: ExchangeTable, now: dt.datetime, history_days: int = 420) -> tuple[list[sg.StockInput], dict[str, dict]]:
    eligible = eligible_stocks(conn)
    facts = repo.facts_payloads(conn)
    valuation = repo.extra_payloads(conn, "bewertung")
    nasdaq = repo.extra_payloads(conn, "nasdaq")
    news = repo.extra_payloads(conn, "nachrichten")
    community = repo.extra_payloads(conn, "community")
    fx = latest_fx(conn, cutoff_day)
    weekly = repo.week_bars_since(conn, [int(listing["id"]) for listing in eligible.values()], cutoff_day - 3 * 365 - 14)
    inputs = []
    meta = {}
    now_ts = now.timestamp()
    for isin, listing in sorted(eligible.items()):
        bars = repo.load_bars(conn, int(listing["id"]), int(listing["data_revision"]), cutoff_day - history_days)
        keep = bars["days"] <= cutoff_day
        if keep.sum() < 25:
            continue
        unit = listing["price_unit"] or listing["currency"]
        inputs.append(
            sg.StockInput(
                isin=isin,
                days=bars["days"][keep],
                open=bars["open"][keep],
                high=bars["high"][keep],
                low=bars["low"][keep],
                close=bars["close"][keep],
                volume=bars["volume"][keep],
                unit_to_eur=eur_per_unit(fx, unit, cutoff_day),
                unit_factor=unit_info(unit)[1],
                facts=facts.get(isin),
                valuation=(valuation.get(isin) or {}).get("daten"),
                nasdaq=(nasdaq.get(isin) or {}).get("daten"),
                news=(news.get(isin) or {}).get("daten"),
                community=(community.get(isin) or {}).get("daten"),
                now_ts=now_ts,
                weeks=_weeks(weekly.get(int(listing["id"]))),
            )
        )
        meta[isin] = {
            "einheit": unit,
            "kennzahlen_abgerufen": (facts.get(isin) or {}).get("_abgerufen"),
            "nachrichten_abgerufen": (news.get(isin) or {}).get("abgerufen"),
            "community_abgerufen": (community.get(isin) or {}).get("abgerufen"),
            "bewertung_abgerufen": (valuation.get(isin) or {}).get("abgerufen"),
        }
    return inputs, meta


def _weeks(rows) -> tuple[np.ndarray, np.ndarray] | None:
    if not rows:
        return None
    pairs = [(int(r["week_end"]), float(r["close"])) for r in rows if r["close"] is not None]
    if not pairs:
        return None
    return np.array([d for d, _ in pairs], dtype=np.int64), np.array([c for _, c in pairs], dtype=np.float64)


class SignalsJob:
    def __init__(self, conn, state_dir: Path, key: crypto.KeyMaterial | None, table: ExchangeTable, *, now: dt.datetime, data_mode: str, event=None) -> None:
        self.conn = conn
        self.state_dir = Path(state_dir)
        self.key = key
        self.table = table
        self.now = now
        self.data_mode = data_mode
        self.event = event or (lambda step, message, level="INFO": LOG.info("[%s] %s", step, message))

    def run(self) -> dict | None:
        from ..publish.signals_writer import SignalsWriter

        published = repo.published_snapshots(self.conn, self.data_mode)
        if not published:
            return None
        snapshot = published[0]
        cutoff = int(snapshot["cutoff_day"])
        inputs, meta = build_inputs(self.conn, cutoff_day=cutoff, table=self.table, now=self.now)
        if not inputs:
            return None
        batch = sg.compute_all(inputs)
        stand_id = self.now.strftime("%Y%m%dT%H%M%SZ")
        writer = SignalsWriter(batch, inputs, meta, stand_id=stand_id, snapshot_id=snapshot["id"], cutoff_day=cutoff, key=self.key, now=self.now)
        summary = writer.write(self.state_dir)
        repo.insert_signal_stand(
            self.conn,
            id=stand_id,
            snapshot_id=snapshot["id"],
            cutoff_day=cutoff,
            stocks=summary["aktien"],
            with_facts=summary["mit_kennzahlen"],
            summary=summary,
            archive=summary["archiv"],
        )
        atomic_write_json(self.state_dir / "site_meta" / "signale.json", {k: v for k, v in summary.items() if k != "kandidaten"})
        self.event(
            "signale",
            f"Signal-Stand {stand_id}: {summary['aktien']} Aktien, {summary['mit_kennzahlen']} mit Kennzahlen; Gesamtwertung stark {summary['gesamt_stark']}, "
            f"mittel {summary['gesamt_mittel']}; beide grün {summary['beide_gruen']}, kurzfristig grün {summary['kurz_gruen']}, langfristig grün {summary['lang_gruen']}; "
            f"Trefferquote aus {summary['kalibrierung_faelle']} Vergleichsfällen",
        )
        return summary
