"""Kursaktualisierung einzelner Aktien auf Wunsch aus der App (ab 1.21).

Ablauf („Jetzt aktualisieren“ für eine Aktie, die Merkliste, ein Depot oder die sichtbaren Aktien):

1. Die App verschlüsselt die Anfrage (ISIN und Yahoo-Symbol je Aktie, sichtbare zuerst) mit dem Datenschlüssel und startet
   den Workflow ``aktualisieren.yml`` über die GitHub-Schnittstelle. Öffentlich sichtbar sind nur die zufällige Kennung und
   der verschlüsselte Text – keine ISIN, kein Name, kein Kurs.
2. Dieser Lauf prüft die Anfrage (Entschlüsselung mit Integritätsschutz, Schema, Größe, Alter, Format jeder ISIN und jedes
   Symbols), ruft nur diese Kurse ab und liefert sie in Teilen: zuerst die sichtbaren Aktien, dann die übrigen.
3. Jede Lieferung ist eine verschlüsselte Datei ``aktuell/<kennung>-<teil>.bin`` auf dem Branch ``kurse-aktuell`` (ein
   einziger Commit ohne Verlauf, ältere Lieferungen nach zwei Tagen entfernt). Die App lädt sie über die GitHub-Schnittstelle
   und zeigt die Kurse mit Kurszeit, Abrufzeit und gemeldeter Verzögerung.

Nichts hier verändert den gespeicherten Datenstand, Ranglisten oder die Website: Die Lieferung ergänzt nur die Anzeige der
Kurse. Fehler stehen als ``aktuell/<kennung>-fehler.json`` mit einem Grundcode (ohne Daten der Anfrage) bereit, damit die App
sie nennen kann.
"""

from __future__ import annotations

import base64
import datetime as dt
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from ..util import crypto
from ..util.isin import is_valid_isin
from ..util.jsonio import atomic_write_bytes, dumps
from ..util.log import get_logger
from ..util.timeutil import UTC, iso_utc, parse_iso_utc

LOG = get_logger(__name__)

SCHEMA_ANFRAGE = "tr-aktualisierung-anfrage/1"
SCHEMA_LIEFERUNG = "tr-kursaktualisierung/1"
BRANCH = "kurse-aktuell"
ORDNER = "aktuell"

# Kennung: „k“ + Erstellzeit (Sekunden seit 1970, Basis 36) + „-“ + 16 Zufallszeichen aus der App
KENNUNG_RE = re.compile(r"^k([0-9a-z]{6,8})-([0-9a-z]{16})$")
SYMBOL_RE = re.compile(r"^[A-Za-z0-9.^=\-]{1,24}$")
UMFAENGE = ("aktie", "merkliste", "depot", "sichtbar", "auswahl")
MAX_WERTE = 250
MAX_KURSVERLAUF = 3
MAX_ANFRAGE_BYTES = 48_000  # Base64-Text der verschlüsselten Anfrage (Workflow-Eingaben sind begrenzt)
MAX_ALTER_S = 20 * 60  # ältere Anfragen werden abgelehnt (Schutz vor Wiederholung)
MAX_ZUKUNFT_S = 5 * 60  # Uhr des Handys darf etwas vorgehen
TEIL1_MAX = 25  # sichtbare Aktien zuerst, höchstens so viele im ersten Teil
AUFBEWAHRUNG_S = 2 * 24 * 3600

QUOTE_FELDER = (
    "symbol,regularMarketPrice,regularMarketTime,regularMarketVolume,regularMarketPreviousClose,currency,exchangeTimezoneName,"
    "marketState,regularMarketOpen,regularMarketDayHigh,regularMarketDayLow,exchangeDataDelayedBy"
)

# Bekannte Verzögerungen laut Yahoo-Hilfe „Exchanges and data providers on Yahoo Finance“ (help.yahoo.com/kb/SLN2310.html,
# abgerufen am 31.10.2026), je Symbol-Endung. Nur Ersatz, wenn die Antwort selbst keine Verzögerung nennt. USA ohne Endung:
# Nasdaq-Daten in Echtzeit, OTC-Markt 15 Minuten – ohne Börsenangabe nicht unterscheidbar, deshalb dort keine Angabe.
YAHOO_VERZOEGERUNG_MIN: dict[str, int] = {
    ".AS": 15, ".AT": 15, ".AX": 20, ".BA": 30, ".BD": 15, ".BE": 15, ".BK": 15, ".BM": 15, ".BO": 15, ".BR": 15,
    ".CN": 0, ".CO": 0, ".DE": 15, ".DU": 15, ".F": 15, ".HA": 15, ".HE": 0, ".HK": 15, ".HM": 15, ".IC": 0, ".IL": 20,
    ".IR": 15, ".IS": 15, ".JK": 10, ".JO": 15, ".KL": 15, ".KQ": 20, ".KS": 20, ".L": 20, ".LS": 15, ".MC": 15,
    ".MI": 20, ".MU": 15, ".MX": 20, ".NE": 0, ".NS": 0, ".NZ": 20, ".OL": 15, ".PA": 15, ".PR": 20, ".RG": 0,
    ".SA": 15, ".SG": 15, ".SI": 20, ".SN": 15, ".SS": 30, ".ST": 0, ".SW": 30, ".SZ": 30, ".T": 20, ".TA": 20,
    ".TL": 0, ".TO": 0, ".TW": 20, ".TWO": 20, ".V": 0, ".VI": 15, ".VS": 0, ".WA": 15,
}


class AnfrageFehler(ValueError):
    """Anfrage abgelehnt; ``code`` ist ein Grundcode ohne Daten der Anfrage (geht auch in öffentliche Ausgaben)."""

    def __init__(self, code: str, text: str) -> None:
        super().__init__(text)
        self.code = code


@dataclass(frozen=True)
class Wert:
    isin: str
    symbol: str


@dataclass(frozen=True)
class Anfrage:
    kennung: str
    umfang: str
    werte: tuple[Wert, ...]
    sichtbar: int  # so viele Werte am Anfang sind gerade sichtbar (werden zuerst geliefert)
    kursverlauf: tuple[str, ...]  # ISINs, für die zusätzlich der Tagesverlauf (5 Minuten) und die letzten Tageskerzen kommen
    erstellt: dt.datetime

    def teile(self) -> list[tuple[Wert, ...]]:
        """Lieferteile: zuerst die sichtbaren Aktien (mindestens eine, höchstens ``TEIL1_MAX``), dann der Rest."""
        if not self.werte:
            return []
        first = max(1, min(self.sichtbar or len(self.werte), TEIL1_MAX, len(self.werte)))
        if first >= len(self.werte):
            return [self.werte]
        return [self.werte[:first], self.werte[first:]]


def kennung_zeit(kennung: str) -> dt.datetime:
    match = KENNUNG_RE.match(kennung or "")
    if not match:
        raise AnfrageFehler("kennung_ungueltig", "Kennung hat nicht das erwartete Format")
    return dt.datetime.fromtimestamp(int(match.group(1), 36), tz=UTC)


def anfrage_aad(kennung: str) -> str:
    return f"anfrage/{kennung}"


def lieferung_pfad(kennung: str, teil: int) -> str:
    return f"{ORDNER}/{kennung}-{teil}.bin"


def fehler_pfad(kennung: str) -> str:
    return f"{ORDNER}/{kennung}-fehler.json"


def _b64decode(text: str) -> bytes:
    cleaned = (text or "").strip().replace("-", "+").replace("_", "/")
    cleaned += "=" * (-len(cleaned) % 4)
    try:
        return base64.b64decode(cleaned, validate=True)
    except (ValueError, TypeError) as exc:
        raise AnfrageFehler("anfrage_unlesbar", "Anfrage ist kein gültiger Base64-Text") from exc


def parse_anfrage(text: str, kennung: str, key: crypto.KeyMaterial | None, now: dt.datetime) -> Anfrage:
    """Prüft und entschlüsselt eine Anfrage. Wirft ``AnfrageFehler`` mit Grundcode; nimmt nie etwas als Code oder Pfad."""
    created_by_id = kennung_zeit(kennung)
    if key is None:
        raise AnfrageFehler("kein_schluessel", "Ohne Datenschlüssel lassen sich Anfragen nicht prüfen")
    if not text or len(text) > MAX_ANFRAGE_BYTES:
        raise AnfrageFehler("anfrage_zu_gross", "Anfrage fehlt oder ist zu groß")
    blob = _b64decode(text)
    try:
        plain = crypto.unpack(blob, key, anfrage_aad(kennung))
    except crypto.ContainerError as exc:
        raise AnfrageFehler("anfrage_nicht_entschluesselbar", "Anfrage ließ sich nicht entschlüsseln (Schlüssel oder Kennung passt nicht)") from exc
    if len(plain) > 200_000:
        raise AnfrageFehler("anfrage_zu_gross", "Anfrage ist entpackt zu groß")
    try:
        data = json.loads(plain.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AnfrageFehler("anfrage_unlesbar", "Anfrage ist kein gültiges JSON") from exc
    if not isinstance(data, dict) or data.get("schema") != SCHEMA_ANFRAGE:
        raise AnfrageFehler("schema_falsch", "Anfrage hat nicht das erwartete Schema")
    if data.get("kennung") != kennung:
        raise AnfrageFehler("kennung_passt_nicht", "Kennung in der Anfrage passt nicht")
    created = parse_iso_utc(data.get("erstellt_utc")) if isinstance(data.get("erstellt_utc"), str) else None
    if created is None or abs((created - created_by_id).total_seconds()) > 120:
        raise AnfrageFehler("zeit_ungueltig", "Erstellzeit fehlt oder passt nicht zur Kennung")
    age = (now - created).total_seconds()
    if age > MAX_ALTER_S:
        raise AnfrageFehler("anfrage_zu_alt", "Anfrage ist älter als 20 Minuten")
    if age < -MAX_ZUKUNFT_S:
        raise AnfrageFehler("zeit_ungueltig", "Erstellzeit liegt in der Zukunft")
    scope = data.get("umfang")
    if scope not in UMFAENGE:
        raise AnfrageFehler("umfang_ungueltig", "Unbekannter Umfang")
    raw_values = data.get("werte")
    if not isinstance(raw_values, list) or not raw_values:
        raise AnfrageFehler("keine_werte", "Anfrage nennt keine Aktie")
    if len(raw_values) > MAX_WERTE:
        raise AnfrageFehler("zu_viele_werte", f"Höchstens {MAX_WERTE} Aktien je Anfrage")
    values: list[Wert] = []
    seen: set[str] = set()
    for item in raw_values:
        if not isinstance(item, dict):
            raise AnfrageFehler("wert_ungueltig", "Eintrag ohne ISIN und Symbol")
        isin, symbol = item.get("isin"), item.get("symbol")
        if not isinstance(isin, str) or not is_valid_isin(isin):
            raise AnfrageFehler("isin_ungueltig", "Eine ISIN ist ungültig")
        if not isinstance(symbol, str) or not SYMBOL_RE.match(symbol):
            raise AnfrageFehler("symbol_ungueltig", "Ein Symbol hat ein unerwartetes Format")
        if isin in seen:
            continue
        seen.add(isin)
        values.append(Wert(isin, symbol))
    visible = data.get("sichtbar", 0)
    if isinstance(visible, bool) or not isinstance(visible, int) or visible < 0:
        raise AnfrageFehler("wert_ungueltig", "Zahl der sichtbaren Aktien ist ungültig")
    chart = data.get("kursverlauf") or []
    if not isinstance(chart, list) or len(chart) > MAX_KURSVERLAUF or not all(isinstance(x, str) and x in seen for x in chart):
        raise AnfrageFehler("kursverlauf_ungueltig", f"Kursverlauf höchstens für {MAX_KURSVERLAUF} angefragte Aktien")
    return Anfrage(kennung, scope, tuple(values), min(visible, len(values)), tuple(dict.fromkeys(chart)), created)


def build_anfrage(kennung: str, umfang: str, werte: list[tuple[str, str]], key: crypto.KeyMaterial, *, sichtbar: int = 0,
                  kursverlauf: list[str] | None = None, erstellt: dt.datetime | None = None) -> str:
    """Gegenstück der App (für Tests und die lokale Probe): verschlüsselte Anfrage als Base64-Text."""
    created = erstellt or kennung_zeit(kennung)
    payload = {
        "schema": SCHEMA_ANFRAGE,
        "kennung": kennung,
        "erstellt_utc": iso_utc(created),
        "umfang": umfang,
        "werte": [{"isin": i, "symbol": s} for i, s in werte],
        "sichtbar": sichtbar,
        "kursverlauf": list(kursverlauf or []),
    }
    blob = crypto.pack(json.dumps(payload).encode("utf-8"), key, anfrage_aad(kennung))
    return base64.b64encode(blob).decode("ascii")


def neue_kennung(now: dt.datetime | None = None) -> str:
    when = int((now or dt.datetime.now(UTC)).timestamp())
    digits = "0123456789abcdefghijklmnopqrstuvwxyz"
    stamp = ""
    while when:
        when, rest = divmod(when, 36)
        stamp = digits[rest] + stamp
    tail = "".join(digits[b % 36] for b in os.urandom(16))
    return f"k{stamp}-{tail}"


# ------------------------------------------------------------------------------------------------ Abruf


def known_delay(symbol: str) -> int | None:
    """Verzögerung laut Yahoo-Hilfe nach Symbol-Endung (längste passende Endung)."""
    if "." not in symbol:
        return None
    suffix = "." + symbol.rsplit(".", 1)[1].upper()
    return YAHOO_VERZOEGERUNG_MIN.get(suffix)


def _num(value) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def quote_entry(wert: Wert, quote, fetched_at: dt.datetime) -> dict:
    delay = quote.delay_min
    source = "yahoo_antwort" if delay is not None else None
    if delay is None:
        delay = known_delay(wert.symbol)
        source = "yahoo_hilfe" if delay is not None else None
    session_day = int(quote.session_day)
    return {
        "isin": wert.isin,
        "symbol": wert.symbol,
        "kurs": _num(quote.price),
        "einheit": quote.currency,
        "kurszeit_utc": iso_utc(quote.time_utc),
        "sitzung": (dt.date(1970, 1, 1) + dt.timedelta(days=session_day)).isoformat(),
        "marktstatus": quote.market_state,
        "verzoegerung_min": delay,
        "verzoegerung_quelle": source,
        "vortag": _num(quote.previous_close),
        "eroeffnung": _num(quote.day_open),
        "hoch": _num(quote.day_high),
        "tief": _num(quote.day_low),
        "umsatz": _num(quote.volume),
        "abrufzeit_utc": iso_utc(fetched_at),
    }


def intraday_from_chart(payload: dict) -> dict | None:
    """Tagesverlauf (5-Minuten-Kurse) und Tageskerzen aus einer Chart-Antwort; reine Funktion."""
    try:
        result = payload["chart"]["result"][0]
    except (KeyError, IndexError, TypeError):
        return None
    stamps = result.get("timestamp") or []
    quote = ((result.get("indicators") or {}).get("quote") or [{}])[0] or {}
    closes = quote.get("close") or []
    points_t, points_c = [], []
    for ts, close in zip(stamps, closes):
        value = _num(close)
        if ts is None or value is None or value <= 0:
            continue
        points_t.append(int(ts))
        points_c.append(round(value, 6))
    if not points_t:
        return None
    meta = result.get("meta") or {}
    return {"t": points_t, "c": points_c, "zeitzone": meta.get("exchangeTimezoneName"), "intervall": meta.get("dataGranularity") or "5m"}


@dataclass
class Bericht:
    """Zusammenfassung eines Laufs – nur Zählungen und Zeiten (öffentliche Ausgabe)."""

    kennung: str
    umfang: str | None = None
    werte: int = 0
    teile: int = 0
    mit_kurs: int = 0
    ohne_kurs: int = 0
    kursverlauf: int = 0
    abrufe: int = 0
    fehler: str | None = None
    zeiten: dict[str, float] = field(default_factory=dict)
    geliefert: list[str] = field(default_factory=list)

    def zeile(self) -> str:
        times = " | ".join(f"{k} {v:.1f} s" for k, v in self.zeiten.items())
        if self.fehler:
            return f"Kursaktualisierung abgelehnt: {self.fehler}"
        return (f"Kursaktualisierung {self.umfang}: {self.werte} Aktien in {self.teile} Teilen, {self.mit_kurs} mit Kurs, {self.ohne_kurs} ohne, "
                f"Tagesverlauf {self.kursverlauf}, {self.abrufe} Abrufe | {times}")


Lieferer = Callable[[list[Path]], None]


def run(anfrage: Anfrage, provider, key: crypto.KeyMaterial, out_dir: Path, deliver: Lieferer, *, now: Callable[[], dt.datetime] | None = None) -> Bericht:
    """Kurse abrufen und in Teilen liefern (sichtbare zuerst). ``deliver`` legt die Dateien eines Teils im Lieferkanal ab."""
    clock = now or (lambda: dt.datetime.now(UTC))
    report = Bericht(anfrage.kennung, anfrage.umfang, len(anfrage.werte))
    parts = anfrage.teile()
    report.teile = len(parts)
    started = time.monotonic()
    for number, part in enumerate(parts, start=1):
        t0 = time.monotonic()
        symbols = [w.symbol for w in part]
        result = provider.fetch_quotes(symbols, budget_s=60.0, fields=QUOTE_FELDER, spark_fallback=True)
        fetched_at = clock()
        report.abrufe += int(getattr(result, "requests", 0) or 0)
        entries, missing = [], []
        for wert in part:
            quote = result.quotes.get(wert.symbol)
            if quote is None:
                missing.append({"isin": wert.isin, "grund": result.missing.get(wert.symbol) or "kein Kurs geliefert"})
            else:
                entries.append(quote_entry(wert, quote, fetched_at))
        charts = {}
        for isin in anfrage.kursverlauf:
            wert = next((w for w in part if w.isin == isin), None)
            if wert is None:
                continue
            try:
                payload = provider.chart(wert.symbol, None, None, range_="1d", interval="5m")
                report.abrufe += 1
            except Exception as exc:  # Tagesverlauf ist Zugabe: ein Fehler verhindert die Kurse nicht
                LOG.info("Tagesverlauf nicht verfügbar (%s)", type(exc).__name__)
                continue
            chart = intraday_from_chart(payload)
            if chart is not None:
                chart["abrufzeit_utc"] = iso_utc(clock())
                charts[isin] = chart
        report.zeiten[f"Abruf Teil {number}"] = time.monotonic() - t0
        report.mit_kurs += len(entries)
        report.ohne_kurs += len(missing)
        report.kursverlauf += len(charts)
        body = {
            "schema": SCHEMA_LIEFERUNG,
            "kennung": anfrage.kennung,
            "teil": number,
            "teile": len(parts),
            "umfang": anfrage.umfang,
            "angefragt_utc": iso_utc(anfrage.erstellt),
            "erstellt_utc": iso_utc(clock()),
            "quelle": {"name": "Yahoo Finance", "weg": getattr(result, "endpoint", None) or "quote",
                       "hinweis": "Kurse laut Yahoo, je Börse verzögert; nur zur Information"},
            "kurse": entries,
            "fehlend": missing,
            "kursverlauf": charts,
        }
        relative = lieferung_pfad(anfrage.kennung, number)
        target = out_dir / relative
        atomic_write_bytes(target, crypto.pack(dumps(body).encode("utf-8"), key, relative), durable=False)
        t1 = time.monotonic()
        deliver([target])
        report.zeiten[f"Lieferung Teil {number}"] = time.monotonic() - t1
        report.geliefert.append(relative)
    report.zeiten["zusammen"] = time.monotonic() - started
    return report


def write_error(out_dir: Path, kennung: str, code: str) -> Path:
    """Grundcode einer abgelehnten Anfrage (unverschlüsselt, ohne Daten der Anfrage)."""
    target = out_dir / fehler_pfad(kennung)
    atomic_write_bytes(target, json.dumps({"schema": "tr-kursaktualisierung-fehler/1", "kennung": kennung, "grund": code}).encode("utf-8"), durable=False)
    return target


# ------------------------------------------------------------------------------------------------ Lieferkanal (Branch)


def _git(args: list[str], cwd: Path, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, env=env, check=True, capture_output=True, text=True, timeout=120)


def prune_names(names: list[str], now: dt.datetime) -> list[str]:
    """Lieferungen älter als zwei Tage (Zeit aus der Kennung) – werden beim nächsten Liefern entfernt."""
    old = []
    for name in names:
        stem = name.rsplit("/", 1)[-1]
        match = re.match(r"^(k[0-9a-z]{6,8}-[0-9a-z]{16})-(\d+\.bin|fehler\.json)$", stem)
        if not match:
            old.append(name)  # Fremdes gehört nicht in den Lieferkanal
            continue
        try:
            created = kennung_zeit(match.group(1))
        except AnfrageFehler:
            old.append(name)
            continue
        if (now - created).total_seconds() > AUFBEWAHRUNG_S:
            old.append(name)
    return old


class GitLieferkanal:
    """Legt Dateien auf dem Branch ``kurse-aktuell`` ab: ein Commit ohne Vorgänger, mit ``--force`` ersetzt.

    Der Verlauf wächst so nicht. Gleichzeitige Läufe verhindert der Workflow (``concurrency``). Das Token kommt aus der
    Umgebung (``GITHUB_TOKEN`` des Laufs) und erscheint nie in einer Ausgabe."""

    def __init__(self, repository: str, token: str, *, server: str = "https://github.com", branch: str = BRANCH, now: Callable[[], dt.datetime] | None = None) -> None:
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository or ""):
            raise ValueError("Repository im Format konto/name erwartet")
        self.repository = repository
        self.token = token
        self.server = server.rstrip("/")
        self.branch = branch
        self.now = now or (lambda: dt.datetime.now(UTC))
        self.work = Path(tempfile.mkdtemp(prefix="kurse-aktuell-"))
        self._init()

    def _env(self) -> dict:
        env = dict(os.environ)
        basic = base64.b64encode(f"x-access-token:{self.token}".encode()).decode()
        env.update({
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": f"http.{self.server}/.extraheader",
            "GIT_CONFIG_VALUE_0": f"AUTHORIZATION: basic {basic}",
            "GIT_AUTHOR_NAME": "github-actions[bot]",
            "GIT_AUTHOR_EMAIL": "41898282+github-actions[bot]@users.noreply.github.com",
            "GIT_COMMITTER_NAME": "github-actions[bot]",
            "GIT_COMMITTER_EMAIL": "41898282+github-actions[bot]@users.noreply.github.com",
        })
        return env

    def _init(self) -> None:
        _git(["init", "-q"], self.work)
        _git(["remote", "add", "origin", f"{self.server}/{self.repository}.git"], self.work)

    def deliver(self, files: list[Path]) -> None:
        env = self._env()
        tree = self.work / "baum"
        if tree.exists():
            shutil.rmtree(tree)
        tree.mkdir()
        try:
            _git(["fetch", "-q", "--depth=1", "origin", self.branch], self.work, env)
            existing = _git(["ls-tree", "-r", "--name-only", "FETCH_HEAD"], self.work, env).stdout.split()
        except subprocess.CalledProcessError:
            existing = []  # Branch gibt es noch nicht
        drop = set(prune_names(existing, self.now()))
        for name in existing:
            if name in drop:
                continue
            content = subprocess.run(["git", "show", f"FETCH_HEAD:{name}"], cwd=self.work, env=env, check=True, capture_output=True, timeout=60).stdout
            (tree / name).parent.mkdir(parents=True, exist_ok=True)
            (tree / name).write_bytes(content)
        for path in files:
            target = tree / ORDNER / path.name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
        index_env = dict(env, GIT_INDEX_FILE=str(self.work / "lieferung.index"), GIT_WORK_TREE=str(tree))
        if (self.work / "lieferung.index").exists():
            (self.work / "lieferung.index").unlink()
        _git(["add", "-A", "."], tree, index_env | {"GIT_DIR": str(self.work / ".git")})
        tree_id = _git(["write-tree"], tree, index_env | {"GIT_DIR": str(self.work / ".git")}).stdout.strip()
        message = f"Kursaktualisierung: {len(files)} Datei(en)"
        commit = _git(["commit-tree", tree_id, "-m", message], self.work, env).stdout.strip()
        _git(["push", "-q", "--force", "origin", f"{commit}:refs/heads/{self.branch}"], self.work, env)

    def close(self) -> None:
        shutil.rmtree(self.work, ignore_errors=True)


class OrdnerLieferkanal:
    """Lieferkanal für DEMO und Tests: kopiert in einen lokalen Ordner (wie der Branch aufgebaut)."""

    def __init__(self, root: Path, *, now: Callable[[], dt.datetime] | None = None) -> None:
        self.root = Path(root)
        self.now = now or (lambda: dt.datetime.now(UTC))

    def deliver(self, files: list[Path]) -> None:
        folder = self.root / ORDNER
        folder.mkdir(parents=True, exist_ok=True)
        names = [f"{ORDNER}/{p.name}" for p in folder.iterdir() if p.is_file()]
        for name in prune_names(names, self.now()):
            (self.root / name).unlink(missing_ok=True)
        for path in files:
            shutil.copyfile(path, folder / path.name)


def fetch_and_deliver(kennung: str, anfrage_text: str, provider, key: crypto.KeyMaterial | None, out_dir: Path, channel, *,
                      now: Callable[[], dt.datetime] | None = None) -> Bericht:
    """Gesamter Ablauf eines Laufs; eine abgelehnte Anfrage ergibt eine Fehlerdatei im Lieferkanal."""
    clock = now or (lambda: dt.datetime.now(UTC))
    out_dir = Path(out_dir)
    try:
        anfrage = parse_anfrage(anfrage_text, kennung, key, clock())
    except AnfrageFehler as exc:
        report = Bericht(kennung if KENNUNG_RE.match(kennung or "") else "ungueltig", fehler=exc.code)
        if KENNUNG_RE.match(kennung or ""):
            channel.deliver([write_error(out_dir, kennung, exc.code)])
        return report
    return run(anfrage, provider, key, out_dir, channel.deliver, now=clock)


def sample_values() -> list[tuple[str, str]]:
    """Öffentlich bekannte Werte für die Probe ohne App (Messung, Tests): ISIN und Yahoo-Symbol großer Aktien verschiedener
    Börsen (Prüfziffern geprüft). Ausgaben nennen nur Zählungen, nie diese Werte."""
    text = (
        "DE0007164600 SAP.DE|DE0007236101 SIE.DE|DE0008404005 ALV.DE|DE0005190003 BMW.DE|DE000BASF111 BAS.DE|DE000BAY0017 BAYN.DE|"
        "DE0005557508 DTE.DE|DE0007100000 MBG.DE|DE0008430026 MUV2.DE|DE0005140008 DBK.DE|DE000A1EWWW0 ADS.DE|DE0006231004 IFX.DE|"
        "DE0005552004 DHL.DE|DE000ENAG999 EOAN.DE|DE0007037129 RWE.DE|DE0007664039 VOW3.DE|DE0006048432 HEN3.DE|DE0006599905 MRK.DE|"
        "DE0005810055 DB1.DE|DE0007030033 RHM.DE|US0378331005 AAPL|US5949181045 MSFT|US67066G1040 NVDA|US0231351067 AMZN|"
        "US02079K3059 GOOGL|US30303M1027 META|US88160R1014 TSLA|US46625H1005 JPM|US92826C8394 V|US4781601046 JNJ|US30231G1022 XOM|"
        "US7427181091 PG|US1912161007 KO|US9311421039 WMT|NL0010273215 ASML.AS|FR0000121014 MC.PA|FR0000120271 TTE.PA|"
        "FR0000120578 SAN.PA|FR0000120321 OR.PA|CH0038863350 NESN.SW|CH0012005267 NOVN.SW|CH0012032048 ROG.SW|GB0009895292 AZN.L|"
        "GB00BP6MXD84 SHEL.L|GB0005405286 HSBA.L|GB00B10RZP78 ULVR.L|DK0062498333 NOVO-B.CO|JP3633400001 7203.T|JP3435000009 6758.T|"
        "KYG875721634 0700.HK|KYG017191142 9988.HK"
    )
    return [tuple(item.split()) for item in text.split("|")]  # type: ignore[misc]


__all__ = [
    "Anfrage", "AnfrageFehler", "Bericht", "GitLieferkanal", "OrdnerLieferkanal", "Wert", "build_anfrage", "fetch_and_deliver",
    "intraday_from_chart", "kennung_zeit", "known_delay", "neue_kennung", "parse_anfrage", "prune_names", "quote_entry", "run",
    "sample_values",
]
