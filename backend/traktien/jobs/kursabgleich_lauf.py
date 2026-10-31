"""Kursabgleich im täglichen Lauf (ab 1.20.0): Kurse der Börsen abrufen, speichern, die Auswahlregel anwenden, Wirkung belegen.

Ablauf in ``DailyRun.step_kursabgleich``:

1. Durchgang 0 – Berechnung allein mit der Hauptquelle (Yahoo): Grundlage der Gegenüberstellung „vorher/nachher“.
2. Abruf: **alle** Aktien an XWAR über die Tagesdateien der GPW und der NewConnect (eine Datei je Sitzung, im Zustand
   gespeichert – je Sitzung nur einmal gelesen); die Aktien an XTSE/XTSX/XNAS, die in Durchgang 0 unter den ersten
   ``top_n`` einer Rangliste stehen, über TMX bzw. den offiziellen Schlusskurs von Nasdaq (NOCP).
3. Durchgang 1 – Berechnung mit der Auswahlregel (``analytics.kursabgleich``). Stehen danach Aktien mit eigener Quelle neu
   unter den ersten ``top_n``, werden auch sie abgerufen und es wird erneut gerechnet (höchstens ``max_passes``).
4. Nachweis: jede Korrektur mit Tag, bisherigem Kurs, Kurs der Börse, Quelle und Grund (Tabelle ``kurskorrektur``, Datei
   ``kursabgleich.bin`` im Stand), jede Rangliste mit anderem Platz 1 oder anderen ersten 10, verbleibende Lücken.

Auch künftige Läufe wenden die Regel an: Die Kurse der Börsen liegen im Zustand, jeder Lauf ergänzt neue Sitzungen und
rechnet mit derselben Regel. Fehlt der Kurs der Börse für einen Tag (Quelle nicht erreichbar), gilt dort vorläufig die
Hauptquelle; der nächste Lauf liest den Tag erneut. Wo die Börse den Rechenzeitraum nicht abdeckt, wird nichts übernommen –
ein Quellenwechsel mitten im Zeitraum könnte selbst einen Kurssprung erzeugen.
"""

from __future__ import annotations

import re
import time
from collections import Counter
from dataclasses import dataclass, field

import numpy as np

from ..analytics import kursabgleich as ka
from ..providers import boersen
from ..store import repo
from ..util.names import name_similarity
from ..util.timeutil import day_to_iso

MAX_FAILURES = 8  # so viele Fehlschläge in Folge, dann wird die Quelle in diesem Lauf nicht mehr gefragt (nächster Lauf erneut)
NAME_CONFIRMED = 0.5  # Mindestähnlichkeit des Namens der Kursmeldung (wie bei der Identitätsprüfung)
DESCRIPTOR = re.compile(
    r"(?<=\S)[\s,\-–]+(?:class\s+[a-z0-9]\b|series\s+[a-z0-9]\b|common\s+stock|common\s+shares?|subordinate\s+voting|"
    r"multiple\s+voting|limited\s+voting|voting\s+shares|ordinary\s+shares?|units?\b|warrants?\b|rights?\b)\b.*$",
    re.IGNORECASE,
)
DAY_SOURCES = {"gpw", "newconnect", "cse", "demo_boerse"}  # Quellen mit einer Datei je Sitzung für alle Aktien der Börse
DAY_SOURCE_EXCHANGE = {"gpw": "GPW", "newconnect": "NewConnect", "cse": "CSE", "demo_boerse": "DEMO-Börse"}
SYMBOL_KEYED = {"cse"}  # Tagesdateien ohne ISIN: Zuordnung über das Kürzel, Identität über den Namen
US_KEYS = {"XNYS": "nyse", "XNAS": "nasdaq", "XASE": "nyse_american", "ARCX": "nyse_arca", "BATS": "cboe_bzx"}
US_LISTING = {"Q": "nasdaq", "N": "nyse", "A": "nyse_american", "P": "nyse_arca", "Z": "cboe_bzx", "V": "iex"}
NASDAQ_TRADED = "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqtraded.txt"

# Börsen ohne frei zugängliches Archiv amtlicher Schlusskurse: Quelle und Kosten (Stand der Recherche, siehe
# docs/04_Datenquellen_und_Abdeckung.md). Wird in Stand und App bei verbleibenden Lücken genannt.
MISSING_SOURCES = {
    "XNYS": "NYSE: amtliche Schlusskurse nur kostenpflichtig („TAQ NYSE Closing Prices“ über das Bestellportal von ICE; Preis nicht öffentlich)",
    "XASE": "NYSE American: amtliche Schlusskurse nur kostenpflichtig („TAQ NYSE Closing Prices“, ICE; Preis nicht öffentlich)",
    "ARCX": "NYSE Arca: amtliche Schlusskurse nur kostenpflichtig („TAQ NYSE Closing Prices“, ICE; Preis nicht öffentlich)",
    "BATS": "Cboe BZX: amtliche Schlusskurse nur als kostenpflichtiges Datenprodukt von Cboe",
    "OTC": "OTC Markets: kein amtlicher Schlusskurs (kein Börsenhandel); Tagesdaten nur kostenpflichtig von OTC Markets",
    "XSWX": "SIX Swiss Exchange: Tagesdaten nur kostenpflichtig (SIX Financial Information, z. B. „TimeSeriesDaily“; Preis auf Anfrage)",
    "XWBO": "Wiener Börse: Tagesdaten nur über Market Data Sales (Vertrag, Preis auf Anfrage)",
    "XETR": "Xetra/Deutsche Börse: amtliche Tagesdaten nur kostenpflichtig (Deutsche Börse Market Data + Services)",
    "XLON": "London Stock Exchange: amtliche Tagesdaten nur kostenpflichtig (LSEG Data & Analytics)",
    "XTKS": "Tokio (JPX): amtliche Tagesdaten nur kostenpflichtig (JPX Market Innovation & Research)",
    "XHKG": "HKEX: tägliche Kursblätter frei, aber noch nicht angebunden (Format je Tag als HTML)",
    "XASX": "ASX: amtliche Tagesdaten nur kostenpflichtig (ASX Market Information)",
    "US": "USA: Börse der Notierung beim Kursanbieter nicht angegeben; amtliche Schlusskurse der NYSE-Börsen nur kostenpflichtig",
}
DEFAULT_MISSING_SOURCE = "kein frei zugängliches Archiv amtlicher Schlusskurse geprüft; Tagesdaten der Börse nur kostenpflichtig"


def issuer_name(text: str | None) -> str:
    t = (text or "").strip()
    if " - " in t:
        t = t.split(" - ", 1)[0]
    t = DESCRIPTOR.sub("", t).strip(" ,-–")
    return t or (text or "").strip()


def name_score(source_name: str | None, names: list[str]) -> float:
    if not source_name:
        return 0.0
    candidates = {source_name, issuer_name(source_name)}
    return max((name_similarity(c, n) for c in candidates for n in names if n), default=0.0)


@dataclass
class Settings:
    enabled: bool = True
    range_days: int = 150  # Rechenzeitraum der Regel (Kalendertage bis zum Stichtag): alle Zeiträume bis 90 Sitzungen samt Anker
    top_n: int = 20  # Aktien mit eigener Quelle unter den ersten N einer Rangliste werden abgerufen
    max_passes: int = 3
    tmx_budget: int = 250  # Kürzel je Lauf
    nocp_budget: int = 300  # Anfragen je Lauf (Nasdaq antwortet nach rund 430 Anfragen je Rechner nicht mehr)
    budget_s: float = 20 * 60
    retry_days: int = 5  # Tagesdateien ohne Daten (noch nicht veröffentlicht?) so viele Tage nach der Sitzung erneut lesen
    max_attempts: int = 6  # Tagesdateien mit Netzfehler höchstens so oft lesen

    @classmethod
    def from_pipeline(cls, pipeline) -> "Settings":
        get = pipeline.get if pipeline is not None else (lambda key, default=None: default)
        return cls(
            enabled=bool(get("kursabgleich.aktiv", True)),
            range_days=int(get("kursabgleich.zeitraum_tage", 150)),
            top_n=int(get("kursabgleich.erste_plaetze", 20)),
            max_passes=int(get("kursabgleich.max_durchgaenge", 3)),
            tmx_budget=int(get("kursabgleich.tmx_kuerzel_je_lauf", 250)),
            nocp_budget=int(get("kursabgleich.nocp_anfragen_je_lauf", 300)),
            budget_s=float(get("kursabgleich.zeitbudget_minuten", 20)) * 60,
            retry_days=int(get("kursabgleich.tagesdatei_neu_lesen_tage", 5)),
        )


@dataclass
class Applied:
    isin: str
    listing_id: int
    exchange_key: str | None
    source: str
    result: ka.ListingResult


@dataclass
class Kursabgleich:
    conn: object
    sources: boersen.ExchangeSources | None
    calendars: object
    settings: Settings = field(default_factory=Settings)
    event: object = None
    active: bool = True

    def __post_init__(self) -> None:
        self.official: dict[int, dict[str, dict]] = {}
        self.listing_status: dict[tuple[int, str], object] = {}
        self.applied: dict[int, Applied] = {}
        self.processed: set[int] = set()
        self.stats: Counter = Counter()
        self.fetched_new = False
        self.passes = 0
        self.us_check: dict[int, str] = {}  # listing_id → Ergebnis der Prüfung gegen die Wertpapierliste
        self.us_isin: dict[int, str] = {}
        self.us_listing_status = "nicht_abgefragt"
        self.timings: dict[str, float] = {}
        self.failures: Counter = Counter()  # Fehler in Folge je Quelle (Netz, HTTP-Fehler) – ab MAX_FAILURES für diesen Lauf aus
        self.venue_of: dict[str, str | None] = {}  # ISIN → Börse (bei US-Sammelschlüssel die Börse laut Yahoo)
        self.source_map: dict[str, tuple[str, ...]] = {}  # ISIN → amtliche Quellen der Notierung

    # ------------------------------------------------------------------ Zustand

    def _log(self, message: str, level: str = "INFO") -> None:
        if callable(self.event):
            self.event("kursabgleich", message, level)

    def load(self, D: int) -> None:
        self.official = repo.exchange_bars(self.conn, D - self.settings.range_days - 10)
        self.listing_status = repo.exchange_listing_status(self.conn)
        # Ergebnis der letzten Prüfung gegen die Wertpapierliste (auch für den Zwischenstand, der die Liste nicht abruft)
        if not self.us_check:
            self.us_check = {lid: str(st["status"]) for (lid, src), st in self.listing_status.items() if src == "nasdaqtrader"}

    def _refresh_status(self, listing_id: int, source: str) -> None:
        row = self.conn.execute("SELECT * FROM boersenquelle_notierung WHERE listing_id = ? AND source = ?", (listing_id, source)).fetchone()
        if row is not None:
            self.listing_status[(listing_id, source)] = row

    # -------------------------------------------------------------------- Abruf

    def _failed(self, source: str, status: str) -> bool:
        """Zählt Fehlschläge in Folge; True, wenn die Quelle für diesen Lauf abgeschaltet ist."""
        if status.startswith(("fehler", "http_5", "http_429", "http_403", "kursmeldung_fehler", "kursmeldung_http")):
            self.failures[source] += 1
            if self.failures[source] == MAX_FAILURES:
                self._log(f"{source}: {MAX_FAILURES} Fehlschläge in Folge – in diesem Lauf nicht mehr gefragt, der nächste Lauf versucht es erneut", "WARN")
        else:
            self.failures[source] = 0
        return self.failures[source] >= MAX_FAILURES

    def _disabled(self, source: str) -> bool:
        return self.failures[source] >= MAX_FAILURES

    def _retry_day(self, row, day: int, D: int) -> bool:
        status = str(row["status"])
        if status == "ok":
            return False
        if int(row["attempts"] or 1) >= self.settings.max_attempts:
            return False
        if status.startswith(("fehler", "http_5", "http_429", "http_403", "unlesbar", "modul_fehlt")):
            return True
        return day >= D - self.settings.retry_days  # noch nicht veröffentlicht? (sonst: Feiertag oder Aktie ohne Notierung)

    def fetch_day_files(self, refs: dict, members: dict, D: int, deadline: float) -> None:
        """Tagesdateien (GPW, NewConnect; im DEMO die DEMO-Börse): alle Aktien der Börse, eine Datei je Sitzung (bereits
        gelesene Sitzungen werden übersprungen)."""
        if self.sources is None:
            return
        started = time.monotonic()
        first = D - self.settings.range_days
        groups: dict[str, dict[str, object]] = {}
        for isin, row in refs.items():
            if isin not in members:
                continue
            for source in self.sources_of(row):
                if source in DAY_SOURCES:
                    groups.setdefault(source, {})[isin] = row
        for source, listings in groups.items():
            codes = {row["calendar_code"] for row in listings.values() if row["calendar_code"]}
            sessions = sorted({int(d) for c in codes if self.calendars.available(c) for d in np.asarray(self.calendars.sessions(c, first, D)).tolist()})
            if source in SYMBOL_KEYED:
                by_isin = {boersen.cse_symbol(row["provider_symbol"]): int(row["id"]) for row in listings.values() if row["provider_symbol"]}
            else:
                by_isin = {isin: int(row["id"]) for isin, row in listings.items()}
            known = repo.exchange_day_status(self.conn, source, first)
            info: dict[int, dict] = {}
            for day in sessions:
                row = known.get(day)
                if row is not None and not self._retry_day(row, day, D):
                    continue
                if time.monotonic() > deadline or self._disabled(source):
                    self.stats[f"{source}:{'zeitbudget' if time.monotonic() > deadline else 'abgeschaltet'}"] += 1
                    continue
                f = self.sources.day_file(source, day)
                self.stats[f"{source}:{f.status}"] += 1
                self._failed(source, f.status)
                stored = 0
                bars_of_day = dict(f.bars)
                if source in SYMBOL_KEYED:
                    # Werte ohne Abschluss (nur Geld/Brief): letzter Schlusskurs mit Abschluss, Umsatz 0 (wie bei der GPW)
                    for key, meta in f.info.items():
                        lid = by_isin.get(key)
                        if lid is None or key in bars_of_day or not meta.get("ohne_abschluss"):
                            continue
                        known_bars = (self.official.get(lid) or {}).get(source) or {}
                        filled = boersen.fill_no_trade_days(known_bars, [day]).get(day)
                        if filled is not None:
                            bars_of_day[key] = filled
                for isin, bar in bars_of_day.items():
                    lid = by_isin.get(isin)
                    if lid is None:
                        continue
                    repo.store_exchange_bars(self.conn, lid, source, [bar])
                    self.official.setdefault(lid, {}).setdefault(source, {})[day] = bar
                    entry = info.setdefault(lid, {"first": day, "last": day, "name": None, "currency": None})
                    entry["first"], entry["last"] = min(entry["first"], day), max(entry["last"], day)
                    meta = f.info.get(isin) or {}
                    entry["name"] = meta.get("name") or entry["name"]
                    entry["currency"] = meta.get("currency") or entry["currency"] or ("PLN" if source == "newconnect" else None)
                    stored += 1
                repo.record_exchange_day(self.conn, source, day, f.status, stored)
                self.fetched_new |= stored > 0
            for lid, entry in info.items():
                repo.record_exchange_listing(self.conn, lid, source, status="ok", name=entry["name"], currency=entry["currency"],
                                             exchange=DAY_SOURCE_EXCHANGE.get(source, source), first_day=entry["first"],
                                             last_day=entry["last"], checked_for=D)
                self._refresh_status(lid, source)
        self.timings["tagesdateien"] = self.timings.get("tagesdateien", 0.0) + time.monotonic() - started

    def fetch_symbols(self, listings: list, D: int, deadline: float) -> int:
        """TMX und Nasdaq-NOCP für die übergebenen Notierungen (Spitzenplätze). Rückgabe: Zahl der Abrufe."""
        if self.sources is None:
            return 0
        started = time.monotonic()
        first = D - self.settings.range_days
        calls = 0
        for row in listings:
            lid = int(row["id"])
            if lid in self.processed:
                continue
            self.processed.add(lid)
            for source in self.sources_of(row):
                if source not in ("tmx", "nasdaq_nocp"):
                    continue
                if source == "nasdaq_nocp" and self.us_check.get(lid) not in (None, "gleich"):
                    self.stats["nasdaq_nocp:nicht_nasdaq_notiert"] += 1
                    continue
                st = self.listing_status.get((lid, source))
                if st is not None and st["checked_for"] == D and st["status"] in ("ok", "nicht_gefunden", "keine_kurse"):
                    continue
                limit = self.settings.tmx_budget if source == "tmx" else self.settings.nocp_budget
                if self.stats[f"{source}:abrufe"] >= limit or time.monotonic() > deadline or self._disabled(source):
                    self.stats[f"{source}:{'abgeschaltet' if self._disabled(source) else 'budget_erschoepft'}"] += 1
                    continue
                self.stats[f"{source}:abrufe"] += 1
                start = first
                if st is not None and st["status"] == "ok" and st["first_day"] is not None and int(st["first_day"]) <= first + 7 and st["last_day"]:
                    start = max(first, int(st["last_day"]) - 10)
                series = self.sources.symbol_series(source, row["provider_symbol"], start, D)
                calls += 1
                self.stats[f"{source}:{series.status}"] += 1
                self._failed(source, series.status)
                days = sorted(series.bars)
                if series.bars:
                    repo.store_exchange_bars(self.conn, lid, source, series.bars.values())
                    self.official.setdefault(lid, {}).setdefault(source, {}).update(series.bars)
                    self.fetched_new = True
                repo.record_exchange_listing(self.conn, lid, source, status=series.status, symbol=series.symbol, name=series.name,
                                             exchange=series.exchange, currency=series.currency, detail=series.detail,
                                             first_day=days[0] if days else None, last_day=days[-1] if days else None, checked_for=D)
                self._refresh_status(lid, source)
        self.timings["kuerzel"] = self.timings.get("kuerzel", 0.0) + time.monotonic() - started
        return calls

    def check_us_listings(self, refs: dict, members: dict, http) -> None:
        """Börse jeder US-Notierung gegen die Wertpapierliste von Nasdaq Trader (alle börsennotierten US-Werte mit Börse der
        Notierung; OTC-Werte stehen dort nicht). Ergebnis je Notierung: „gleich“, „andere_boerse:<Börse>“, „nicht_gelistet“."""
        if http is None:
            return
        try:
            response = http.get(NASDAQ_TRADED, headers={"Accept": "text/plain, */*"})
        except Exception as exc:  # noqa: BLE001 - ohne Liste bleibt die Zuordnung ungeprüft
            self.us_listing_status = f"fehler_{type(exc).__name__}"
            return
        if response.status_code != 200:
            self.us_listing_status = f"http_{response.status_code}"
            return
        listing = parse_nasdaq_traded(bytes(response.content or b"").decode("utf-8", "replace"))
        if len(listing) < 1000:
            self.us_listing_status = "liste_unvollstaendig"
            return
        self.us_listing_status = "ok"
        for isin, row in refs.items():
            if isin not in members:
                continue
            venue = boersen.us_venue(row["exchange_key"], _get(row, "provider_exchange"))
            if venue is None or venue == "OTC":
                continue  # nicht an einer US-Börse geführt (OTC: steht nicht in der Liste)
            found = listing.get(normalize_symbol(row["provider_symbol"]))
            if found is None:
                result = "nicht_gelistet"
            elif found != US_KEYS[venue]:
                result = f"andere_boerse:{found}"
            else:
                result = "gleich"
            self.us_check[int(row["id"])] = result
            self.us_isin[int(row["id"])] = isin
            self.stats[f"us_zuordnung:{venue}:{result.split(':')[0]}"] += 1
            repo.record_exchange_listing(self.conn, int(row["id"]), "nasdaqtrader", status=result, symbol=row["provider_symbol"],
                                         exchange=found)

    # ------------------------------------------------------------- Kandidaten

    def top_listings(self, comp, refs: dict) -> list:
        """Notierungen mit eigener Quelle je Symbol (XTSE, XTSX, XNAS) unter den ersten ``top_n`` einer Rangliste."""
        wanted: set[int] = set()
        for wr in comp.rankings.values():
            for group in (wr, wr.group_b):
                if group is None:
                    continue
                rankings = [group.native0] + [r for w, r in group.trend.items() if w != 0]
                for r in rankings:
                    wanted.update(int(x) for x in r.order[: self.settings.top_n].tolist())
        out = []
        for idx in sorted(wanted):
            row = refs.get(comp.isins[idx])
            if row is not None and int(row["id"]) not in self.processed and any(
                src in ("tmx", "nasdaq_nocp") for src in self.sources_of(row)
            ):
                out.append(row)
        return out

    # --------------------------------------------------------------- Anwenden

    def _identity(self, source: str, listing, names: list[str]) -> tuple[bool, bool, str]:
        lid = int(listing["id"])
        st = self.listing_status.get((lid, source))
        unit = listing["price_unit"]
        if source in SYMBOL_KEYED:
            if st is None:
                return False, False, "unbereinigt"
            return name_score(st["name"], names) >= NAME_CONFIRMED, (st["currency"] or "CAD") == (unit or "CAD"), "unbereinigt"
        if source in DAY_SOURCES:
            stated = (st["currency"] if st is not None else None) or ("PLN" if source == "newconnect" else None)
            return True, (stated is None or unit is None or stated == unit), "unbereinigt"
        if source == "tmx":
            if st is None:
                return False, False, "unbekannt"
            identity = boersen.tmx_exchange_matches(listing["exchange_key"], st["exchange"]) and name_score(st["name"], names) >= NAME_CONFIRMED
            return identity, (st["currency"] or "CAD") == (unit or "CAD"), "unbekannt"
        if source == "nasdaq_nocp":
            return self.us_check.get(lid) in (None, "gleich"), unit in (None, "USD"), "unbereinigt"
        return False, False, "unbekannt"

    def overlay(self, isin: str, listing, names: list[str], bars: dict, splits: list, D: int) -> tuple[dict, ka.ListingResult | None, str | None]:
        """Regel auf die Tageskerzen einer Notierung anwenden. Rückgabe: (Kerzen, Ergebnis oder None, Quelle)."""
        if not self.active or not self.settings.enabled:
            return bars, None, None
        lid = int(listing["id"])
        self.venue_of[isin] = boersen.us_venue(listing["exchange_key"], _get(listing, "provider_exchange")) or listing["exchange_key"]
        self.source_map[isin] = self.sources_of(listing)
        if self.us_check.get(lid) == "nicht_gelistet":  # laut Wertpapierliste nicht börsennotiert: OTC, kein NOCP
            self.venue_of[isin], self.source_map[isin] = "OTC", ()
        by_source = self.official.get(lid)
        if not by_source:
            return bars, None, None
        first = D - self.settings.range_days
        chosen = None
        for source in self.sources_of(listing):
            data = by_source.get(source) or {}
            if any(first <= d <= D for d in data):
                chosen = source
                break
        if chosen is None:
            return bars, None, None
        data = {d: b for d, b in by_source[chosen].items() if first <= d <= D}
        identity_ok, currency_ok, basis = self._identity(chosen, listing, names)
        inp = ka.ListingInput(days=bars["days"], close=bars["close"], volume=bars["volume"], open=bars.get("open"), high=bars.get("high"),
                              low=bars.get("low"), close_raw=bars.get("close_raw"), splits=list(splits))
        result = ka.reconcile(chosen, inp, data, first_day=first, last_day=D, identity_ok=identity_ok, currency_ok=currency_ok, basis=basis)
        self.applied[lid] = Applied(isin, lid, listing["exchange_key"], chosen, result)
        if result.adopted:
            bars = ka.apply(bars, result, data, splits)
        return bars, result, chosen

    def reset_pass(self) -> None:
        self.applied = {}

    def sources_for(self, exchange_key: str | None, provider_exchange: str | None = None) -> tuple[str, ...]:
        if self.sources is not None and hasattr(self.sources, "sources_for"):
            return self.sources.sources_for(exchange_key, provider_exchange)
        return boersen.sources_for(exchange_key, provider_exchange)

    def sources_of(self, row) -> tuple[str, ...]:
        """Quellen einer Notierung (Zeile aus ``repo.reference_listings``): Börsenschlüssel und Börse laut Kursanbieter."""
        return self.sources_for(row["exchange_key"], _get(row, "provider_exchange"))

    # --------------------------------------------------------------- Nachweis

    def store_corrections(self, run_id: str) -> int:
        entries = [(a.listing_id, a.source, a.result.corrections) for a in self.applied.values() if a.result.adopted and a.result.corrections]
        return repo.replace_price_corrections(self.conn, run_id, ka.RULE_VERSION, entries)


def _get(row, key: str):
    """Feld einer Zeile (sqlite3.Row oder dict), None, wenn es fehlt."""
    try:
        return row[key]
    except (KeyError, IndexError):
        return None


def normalize_symbol(symbol: str | None) -> str:
    """Kürzel ohne Unterschied der Schreibweise der Gattung („BRK.B“, „BRK/B“, „BRK-B“ → „BRK-B“)."""
    return re.sub(r"[./^= ]", "-", (symbol or "").strip().upper())


def parse_nasdaq_traded(text: str) -> dict[str, str]:
    """Wertpapierliste von Nasdaq Trader („nasdaqtraded.txt“, Trennzeichen „|“): Kürzel → Börse der Notierung."""
    lines = [line for line in (text or "").splitlines() if line.strip()]
    if not lines or "|" not in lines[0]:
        return {}
    header = [h.strip() for h in lines[0].split("|")]
    idx = {name: k for k, name in enumerate(header)}
    if "Symbol" not in idx or "Listing Exchange" not in idx:
        return {}
    out: dict[str, str] = {}
    for line in lines[1:]:
        parts = line.split("|")
        if len(parts) < len(header):
            continue
        if "Test Issue" in idx and parts[idx["Test Issue"]].strip() == "Y":
            continue
        exchange = US_LISTING.get(parts[idx["Listing Exchange"]].strip(), "unbekannt")
        for key in ("Symbol", "CQS Symbol", "NASDAQ Symbol"):
            if key in idx and parts[idx[key]].strip():
                out.setdefault(normalize_symbol(parts[idx[key]]), exchange)
    return out


# ------------------------------------------------------------------ Gegenüberstellung

def ranking_lists(comp, top: int = 10) -> dict[tuple[int, str, int], list[int]]:
    """Je Rangliste (Zeitraum, Gruppe A/B, Gewichtung) die ersten ``top`` Aktien (globale Indizes, wie im Stand)."""
    out: dict[tuple[int, str, int], list[int]] = {}
    for h, wr in comp.rankings.items():
        for label, group in (("A", wr), ("B", wr.group_b)):
            if group is None:
                continue
            out[(int(h), label, 0)] = [int(x) for x in group.native0.order[:top].tolist()]
            for w, r in group.trend.items():
                if w != 0:
                    out[(int(h), label, int(w))] = [int(x) for x in r.order[:top].tolist()]
    return out


def compare_rankings(before: dict, after: dict, corrected: set[int]) -> tuple[list[dict], Counter]:
    rows: list[dict] = []
    counts: Counter = Counter()
    for key in sorted(set(before) | set(after)):
        b, a = before.get(key, []), after.get(key, [])
        counts["ranglisten"] += 1
        lead_changed = (b[:1] != a[:1])
        top_changed = set(b) != set(a)
        order_changed = b != a
        counts["platz1_anders"] += lead_changed
        counts["erste10_andere_aktien"] += top_changed
        counts["erste10_andere_reihenfolge"] += order_changed and not top_changed
        if lead_changed or top_changed:
            h, group, w = key
            triggers = sorted({i for i in (b[:1] + a[:1]) if i in corrected})
            rows.append({"h": h, "gruppe": group, "w": w, "vorher": b, "nachher": a, "platz1_anders": lead_changed, "ausloeser": triggers})
    return rows, counts


def build_report(ka_run: Kursabgleich, before: dict | None, comp_after, metas, D: int) -> dict:
    """Inhalt von ``kursabgleich.bin`` und Zusammenfassung für das Manifest. ``before``: Ranglisten des Durchgangs allein mit
    der Hauptquelle (``ranking_lists``)."""
    index_of = {isin: k for k, isin in enumerate(comp_after.isins)}
    corrected_idx: set[int] = set()
    cases = []
    per_source: dict[str, Counter] = {}
    day_counts: dict[str, Counter] = {}
    for a in sorted(ka_run.applied.values(), key=lambda x: x.isin):
        r = a.result
        idx = index_of.get(a.isin)
        src = per_source.setdefault(a.source, Counter())
        src["notierungen"] += 1
        src[f"status:{r.status}"] += 1
        if r.reason and r.status == "nicht_vergleichbar":
            src[f"grund:{r.reason}"] += 1
        dc = day_counts.setdefault(a.source, Counter())
        for code, value in r.counts.items():
            if code in ka.DAY_CODES:
                dc[code] += int(value)
        price_corrections = [c for c in r.corrections if c.reason != "umsatz_laut_boerse"]
        for c in r.corrections:
            src[f"korrektur:{c.reason}"] += 1
        src["rundung_tage"] += r.rounding
        if price_corrections:
            src["aktien_mit_kurskorrektur"] += 1
            if idx is not None:
                corrected_idx.add(idx)
        if r.corrections or r.status in ("nicht_vergleichbar", "abdeckung_unvollstaendig"):
            cases.append({
                "idx": idx, "isin": a.isin, "boerse": a.exchange_key, "quelle": a.source, "status": r.status, "grund": r.reason,
                "basis": r.basis, "gleich_anteil": None if r.equal_share is None else round(r.equal_share, 4),
                "abdeckung": None if r.coverage is None else round(r.coverage, 4), "faktor": r.factor,
                "tage": {k: int(v) for k, v in r.counts.items() if k in ka.DAY_CODES and v},
                "korrekturen": [
                    {"d": int(c.day), "grund": c.reason, "alt": c.old, "neu": c.new, "boerse_roh": c.official_raw,
                     "umsatz_alt": c.old_volume, "umsatz_neu": c.new_volume}
                    for c in r.corrections
                ],
                "abweichend_ohne_uebernahme": [
                    {"d": int(d.day), "code": d.code, "hauptquelle": d.main, "boerse": d.official, "boerse_roh": d.official_raw}
                    for d in r.days if d.code in ("abweichend", "ohne_umsatz", "nur_boerse")
                ] if not r.adopted else [],
            })
    before = before or {}
    after = ranking_lists(comp_after)
    changes, change_counts = compare_rankings(before, after, corrected_idx) if before else ([], Counter())
    # Verbleibende Lücken: Plätze 1 und Aktien unter den ersten 10 ohne Abgleich mit der Börse
    applied_by_idx = {index_of[a.isin]: a for a in ka_run.applied.values() if a.isin in index_of}
    gaps: dict[int, dict] = {}
    first_places: Counter = Counter()
    for key, order in after.items():
        for place, idx in enumerate(order, start=1):
            a = applied_by_idx.get(idx)
            if a is not None and a.result.adopted:
                continue
            meta = metas[idx]
            exchange = ka_run.venue_of.get(meta.isin) or meta.exchange_key
            if a is not None:
                reason = f"{a.result.status}:{a.result.reason or ''}".rstrip(":")
            elif ka_run.source_map.get(meta.isin) or ka_run.sources_for(meta.exchange_key):
                reason = "quelle_ohne_kurse_oder_nicht_abgerufen"
            else:
                reason = "keine_freie_amtliche_quelle"
            entry = gaps.setdefault(idx, {"idx": idx, "isin": meta.isin, "boerse": exchange, "grund": reason, "platz1": 0, "erste10": 0,
                                          "bester_platz": None,
                                          "fehlende_quelle": MISSING_SOURCES.get(exchange or "", DEFAULT_MISSING_SOURCE) if reason == "keine_freie_amtliche_quelle" else None})
            entry["erste10"] += 1
            if place == 1:
                entry["platz1"] += 1
                first_places[f"{exchange}:{reason.split(':')[0]}"] += 1
            if entry["bester_platz"] is None or place < entry["bester_platz"][0]:
                entry["bester_platz"] = [place, key[0], key[1], key[2]]
    gap_rows = sorted(gaps.values(), key=lambda g: (-g["platz1"], -g["erste10"], g["isin"]))
    us = Counter(ka_run.us_check.values())
    us_rows = []
    for lid, result in sorted(ka_run.us_check.items()):
        if result == "gleich":
            continue
        isin = ka_run.us_isin.get(lid)
        us_rows.append({"idx": index_of.get(isin), "isin": isin, "ergebnis": result})
    summary = {
        "regel": ka.RULE_VERSION,
        "kursdefinition": ka.KURSDEFINITION,
        "zeitraum_tage": ka_run.settings.range_days,
        "erste_plaetze": ka_run.settings.top_n,
        "durchgaenge": ka_run.passes,
        "quellen": {k: dict(v) for k, v in sorted(per_source.items())},
        "tage": {k: dict(v) for k, v in sorted(day_counts.items())},
        "abrufe": dict(sorted(ka_run.stats.items())),
        "aktien_mit_kurskorrektur": len(corrected_idx),
        "ranglisten": dict(change_counts),
        "platz1_ohne_abgleich": dict(first_places.most_common()),
        "us_zuordnung": {"liste": ka_run.us_listing_status, **dict(us)},
        "datei": "kursabgleich.bin",
        "zeiten_s": {k: round(v, 1) for k, v in ka_run.timings.items()},
    }
    payload = {
        "schema": "tr-kursabgleich/1",
        "stichtag": day_to_iso(D),
        "regel": ka.RULE_VERSION,
        "kursdefinition": ka.KURSDEFINITION,
        "quellen": [
            {"key": s.key, "name": s.name, "rolle": s.role, "betreiber": s.operator, "definition": s.definition, "url": s.url,
             "boersen": list(s.exchanges)}
            for s in boersen.SOURCES.values()
        ],
        "tagescodes": ka.DAY_CODES,
        "gruende": ka.REASONS,
        "status": ka.STATUS_TEXT,
        "nicht_vergleichbar": ka.NOT_COMPARABLE,
        "fehlende_quellen": MISSING_SOURCES,
        "faelle": cases,
        "ranglisten": changes,
        "luecken": gap_rows[:400],
        "luecken_gesamt": len(gap_rows),
        "us_zuordnung": us_rows[:400],
        "zusammenfassung": summary,
    }
    return {"summary": summary, "payload": payload}
