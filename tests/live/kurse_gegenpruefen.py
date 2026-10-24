"""Kurse unabhängig gegenprüfen (ab 1.18): Schlusskurse und Renditen des veröffentlichten Stands gegen einen zweiten
Anbieter – Nasdaq (Kurshistorie der Website nasdaq.com) für US-Aktien.

Simons Auftrag vom 24.10.2026, 19:29 Uhr: „Prüfe die aktuelle Berechnung unabhängig anhand verfügbarer Kursdaten und
nachvollziehbarer Referenzfälle. Kennzeichne nachträglich beschaffte Daten ausdrücklich; sie beweisen nicht, welche Daten
dem ursprünglichen Modell damals vorlagen.“

Die App bezieht ihre Kurse von Yahoo. Die unabhängige Nachrechnung (``nachrechnen.py``) prüft die Rechnung mit den
veröffentlichten Kursreihen – ob diese Kurse selbst stimmen, prüft sie nicht. Dieses Skript lädt dafür **nachträglich**
die Tageskurse einer Auswahl von US-Aktien bei **Nasdaq** (anderer Anbieter, eigener Abruf und eigene Auswertung, ohne
den Kursabruf der App) und vergleicht mit dem Stand:

1. **Schlusskurs je Börsentag** – gleich (innerhalb der Rundung von Nasdaq auf Cent bzw. 1/100 Cent unter 1 $), Faktor
   (Split/Zusammenlegung seit dem Abruf), Kurs eines Nachbartags, kleine (≤ 0,5 %) oder große Abweichung;
2. **Kursrendite jedes Zeitraums 1–90 Tage** aus Nasdaq-Kursen an denselben Start- und Endtagen wie im Stand;
3. **fehlende Börsentage**: Tage, an denen der Stand keinen Kurs hat (in der App ein fehlender Kurstag), Nasdaq aber
   einen – und umgekehrt.

Auswahl: alle US-Aktien unter den ersten 10 irgendeiner Rangliste (Gruppe A und B, alle Gewichtungen, 1–90 Tage) und
bis zu 150 weitere, zufällig gewählte (fester Startwert aus der Stand-ID – wiederholbar). Ausgegeben werden nur
Zählwerte und Abweichungsklassen, keine Kurse, Namen, Ticker oder ISINs (das Protokoll ist öffentlich).

Was das **nicht** zeigt: welche Kurse ein anderes Modell (z. B. das Ausgangsmodell) damals hatte; Aktien außerhalb der
USA (Nasdaq führt sie nicht).
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import random
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "backend"))

import nachrechnen  # noqa: E402 - Datenstand laden und entschlüsseln (ohne Rechenkern)

NASDAQ = "https://api.nasdaq.com/api/quote/{symbol}/historical?assetclass=stocks&fromdate={start}&limit=9999&todate={end}"
HEADERS = {"Accept": "application/json, text/plain, */*", "Origin": "https://www.nasdaq.com", "Referer": "https://www.nasdaq.com/"}
EPOCH = dt.date(1970, 1, 1)
LOOKBACK_DAYS = 140  # 90 Kalendertage plus Vorlauf bis zur Startsitzung
RANDOM_EXTRA = 150
MAX_STOCKS = 450
FACTORS = (2, 3, 4, 5, 6, 8, 10, 12, 15, 20, 25, 30, 40, 50, 100)
SMALL = 0.005  # bis 0,5 % gilt eine Abweichung als klein


def day_of(text: str) -> int:
    """„10/23/2026“ (Nasdaq) → Tagesnummer seit 1970 wie im Datenstand."""
    month, day, year = (int(x) for x in text.split("/"))
    return (dt.date(year, month, day) - EPOCH).days


def price(text) -> float | None:
    """„$1,234.56“ → 1234.56; leer/„N/A“ → None."""
    if text is None:
        return None
    cleaned = str(text).replace("$", "").replace(",", "").strip()
    try:
        value = float(cleaned)
    except ValueError:
        return None
    return value if value > 0 else None


def parse_nasdaq(payload: dict) -> dict[int, float]:
    """Schlusskurse je Tag aus der Antwort von Nasdaq (``data.tradesTable.rows``)."""
    rows = (((payload or {}).get("data") or {}).get("tradesTable") or {}).get("rows") or []
    out: dict[int, float] = {}
    for row in rows:
        close = price(row.get("close"))
        if close is not None and row.get("date"):
            out[day_of(row["date"])] = close
    return out


def tolerance(value: float) -> float:
    """Halbe letzte Stelle, mit der Nasdaq den Kurs angibt: Cent ab 1 $, 1/100 Cent darunter."""
    return (0.005 if value >= 1 else 0.00005) + 1e-9


def classify(own: float, fresh: float, neighbours: list[float]) -> str:
    """Schlusskurs des Stands gegen Nasdaq am selben Tag."""
    if abs(own - fresh) <= tolerance(fresh):
        return "gleich"
    ratio = own / fresh
    if any(abs(ratio - f) <= 0.01 * f or abs(ratio - 1 / f) <= 0.01 / f for f in FACTORS):
        return "faktor"
    if any(abs(own - n) <= tolerance(n) for n in neighbours):
        return "nachbartag"
    return "klein" if abs(ratio - 1) <= SMALL else "gross"


def return_matches(r_own: float, p0: float, p1: float) -> bool:
    """Rendite des Stands gegen Nasdaq-Kurse an denselben Tagen, innerhalb der Rundung beider Kurse."""
    fresh = p1 / p0 - 1
    allowed = (1 + fresh) * (tolerance(p0) / p0 + tolerance(p1) / p1) + 1e-9
    return abs(r_own - fresh) <= allowed


def compare_stock(series: dict, fresh: dict[int, float], returns: dict[int, float], cutoff: int) -> dict:
    """Zählwerte für eine Aktie: Kurstage, fehlende Tage, Renditen."""
    counts: Counter = Counter()
    first = cutoff - LOOKBACK_DAYS
    days = [int(d) for d in series.get("d") or []]
    closes = [None if c is None else float(c) for c in series.get("c") or []]
    own = {d: c for d, c in zip(days, closes) if c is not None and c > 0 and first <= d <= cutoff}
    fresh_days = sorted(d for d in fresh if first <= d <= cutoff)
    for d, c in own.items():
        if d not in fresh:
            counts["nur_im_stand"] += 1
            continue
        k = fresh_days.index(d)
        neighbours = [fresh[fresh_days[j]] for j in (k - 1, k + 1) if 0 <= j < len(fresh_days)]
        counts["tage_verglichen"] += 1
        counts[f"tag_{classify(c, fresh[d], neighbours)}"] += 1
    gaps = {int(g) for g in series.get("gaps") or []}
    blank = {d for d, c in zip(days, closes) if c is None}
    series_start = min(days) if days else cutoff
    last_own = max(own, default=None)
    for d in fresh_days:
        if d in own or d < series_start:
            continue
        counts["nur_bei_nasdaq"] += 1
        if last_own is not None and d > last_own:
            counts["nur_bei_nasdaq_nach_letztem_kurs_des_stands"] += 1  # z. B. Stichtagskurs fehlte beim Abruf
        elif d in gaps or d in blank:
            counts["nur_bei_nasdaq_als_fehlender_tag_gezaehlt"] += 1
        else:
            counts["nur_bei_nasdaq_ohne_sitzung_im_stand"] += 1
    end = max(own) if own else None
    starts = series.get("window_start") or []
    for h, r in returns.items():
        start = starts[h - 1] if h - 1 < len(starts) else None
        if start is None or end is None:
            continue
        if start not in fresh or end not in fresh:
            counts["rendite_ohne_nasdaq_kurs"] += 1
            continue
        counts["renditen_verglichen"] += 1
        counts["rendite_gleich" if return_matches(r, fresh[start], fresh[end]) else "rendite_abweichend"] += 1
    return dict(counts)


def select(stand: nachrechnen.Stand, instruments: dict, sid: str) -> tuple[list[int], int]:
    """US-Aktien unter den ersten 10 einer Rangliste und zufällig gewählte weitere (wiederholbar)."""
    n = len(instruments["isin"])
    calendar = instruments.get("calendar") or [None] * n
    key = instruments.get("exchange_key") or [None] * n
    symbol = instruments.get("symbol") or [None] * n
    has_series = instruments.get("has_series") or [True] * n
    us = [i for i in range(n) if calendar[i] == "XNYS" and key[i] != "OTC" and symbol[i] and "." not in str(symbol[i]) and has_series[i]]
    us_set = set(us)
    top: set[int] = set()
    for h in range(1, 91):
        win = stand.get(f"windows/{h}.full.bin")
        orders = win["orders"]
        lists = [orders.get("v0") or [], orders.get("v0l") or []]
        for group in ("u", "ul"):
            lists += [values for values in (orders.get(group) or {}).values()]
        for values in lists:
            top.update(int(i) for i in values[:10] if int(i) in us_set)
        stand.drop(f"windows/{h}.full.bin")
    rest = sorted(us_set - top)
    extra = random.Random(sid).sample(rest, min(RANDOM_EXTRA, len(rest)))
    chosen = sorted(top)[: MAX_STOCKS - len(extra)] + sorted(extra)
    return chosen, len(top)


def window_returns(stand: nachrechnen.Stand, chosen: set[int]) -> dict[int, dict[int, float]]:
    """Veröffentlichte Rendite je Aktie und Zeitraum (nur für die Auswahl)."""
    out: dict[int, dict[int, float]] = {i: {} for i in chosen}
    for h in range(1, 91):
        m = stand.get(f"windows/{h}.full.bin")["m"]
        for k, i in enumerate(m["idx"]):
            if int(i) in out and m["r"][k] is not None:
                out[int(i)][h] = float(m["r"][k])
        stand.drop(f"windows/{h}.full.bin")
    return out


def fetch(http, symbol: str, cutoff: int) -> tuple[str, dict[int, float]]:
    start = (EPOCH + dt.timedelta(days=cutoff - LOOKBACK_DAYS - 5)).isoformat()
    end = (EPOCH + dt.timedelta(days=cutoff + 1)).isoformat()
    url = NASDAQ.format(symbol=symbol.replace("-", "."), start=start, end=end)
    try:
        response = http.get(url, headers=HEADERS)
    except Exception as exc:  # noqa: BLE001 - Netz: nur zählen
        return f"fehler_{type(exc).__name__}", {}
    if response.status_code != 200:
        return f"http_{response.status_code}", {}
    try:
        data = parse_nasdaq(response.json())
    except ValueError:
        return "kein_json", {}
    return ("ok" if data else "keine_kurse"), data


def run(stand: nachrechnen.Stand, sid: str, http) -> dict:
    manifest = stand.get("manifest.bin")
    instruments = stand.get("instruments.bin")
    cutoff = int(manifest["cutoff_day"])
    chosen, from_top = select(stand, instruments, sid)
    returns = window_returns(stand, set(chosen))
    totals: Counter = Counter()
    sources: Counter = Counter()
    stocks_with_issue: Counter = Counter()
    for i in chosen:
        status, fresh = fetch(http, str(instruments["symbol"][i]), cutoff)
        sources[status] += 1
        if status != "ok":
            continue
        series = stand.get(f"series/{instruments['isin'][i]}.bin")
        stand.drop(f"series/{instruments['isin'][i]}.bin")
        counts = compare_stock(series, fresh, returns.get(i, {}), cutoff)
        totals.update(counts)
        for name in ("tag_gross", "tag_klein", "tag_faktor", "tag_nachbartag", "rendite_abweichend"):
            if counts.get(name):
                stocks_with_issue[name] += 1
    return {
        "stand": sid,
        "stichtag": nachrechnen._iso(cutoff),
        "abgerufen_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "ausgewaehlt": len(chosen),
        "davon_aus_den_ersten_10": from_top,
        "abruf": dict(sources),
        "zaehler": dict(totals),
        "aktien_mit": dict(stocks_with_issue),
    }


def annotations(report: dict) -> list[str]:
    z, a = report["zaehler"], report["aktien_mit"]
    found = report["abruf"].get("ok", 0)
    unexplained = z.get("tag_gross", 0) + z.get("rendite_abweichend", 0)
    head = (
        f"Nachträglich bei Nasdaq abgerufen am {report['abgerufen_utc']} (anderer Anbieter als Yahoo; beweist nicht, welche Kurse "
        f"ein anderes Modell damals hatte). Stand {report['stand']} (Kursstand {report['stichtag']})"
    )
    lines = [
        head,
        f"Auswahl: {report['ausgewaehlt']} US-Aktien, davon {report['davon_aus_den_ersten_10']} aus den ersten 10 einer Rangliste; bei Nasdaq gefunden {found} "
        f"(Abruf: {', '.join(f'{k} {v}' for k, v in sorted(report['abruf'].items()))})",
        f"Schlusskurse je Börsentag: {z.get('tage_verglichen', 0)} verglichen – gleich {z.get('tag_gleich', 0)} (innerhalb der Rundung), "
        f"Faktor (Split) {z.get('tag_faktor', 0)}, Kurs eines Nachbartags {z.get('tag_nachbartag', 0)}, klein (≤ 0,5 %) {z.get('tag_klein', 0)}, "
        f"groß {z.get('tag_gross', 0)}; Aktien mit großer Abweichung {a.get('tag_gross', 0)}, mit kleiner {a.get('tag_klein', 0)}",
        f"Fehlende Börsentage: nur im Stand {z.get('nur_im_stand', 0)}, nur bei Nasdaq {z.get('nur_bei_nasdaq', 0)} – davon in der App als "
        f"fehlender Kurstag gezählt {z.get('nur_bei_nasdaq_als_fehlender_tag_gezaehlt', 0)}, nach dem letzten Kurs des Stands "
        f"{z.get('nur_bei_nasdaq_nach_letztem_kurs_des_stands', 0)}, ohne Sitzung im Stand {z.get('nur_bei_nasdaq_ohne_sitzung_im_stand', 0)}",
        f"Renditen 1–90 Tage aus Nasdaq-Kursen an denselben Tagen: {z.get('renditen_verglichen', 0)} verglichen – gleich {z.get('rendite_gleich', 0)}, "
        f"abweichend {z.get('rendite_abweichend', 0)} (Aktien {a.get('rendite_abweichend', 0)}); ohne Nasdaq-Kurs an Start oder Ende {z.get('rendite_ohne_nasdaq_kurs', 0)}",
    ]
    level = "notice" if unexplained == 0 and found >= report["ausgewaehlt"] * 0.5 else "warning"
    title = "Kurse unabhängig gegengeprüft (Nasdaq)" + ("" if level == "notice" else " – Abweichungen oder Quelle nur teilweise erreichbar")
    body = "%0A".join(line.replace("%", "%25") for line in lines)
    return [f"::{level} title={title}::{body}"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", "szymeklh87-commits/tr-aktienvergleich"))
    parser.add_argument("--bericht", type=Path, help="Ergebnis als JSON (nur Zählwerte)")
    args = parser.parse_args(argv)
    from traktien.providers.http import HttpClient

    http = HttpClient(impersonate="chrome", max_retries=2, timeout=25, min_interval={"api.nasdaq.com": 0.4})
    with tempfile.TemporaryDirectory() as temp:
        meta, stands = nachrechnen.load_release_stands(args.repo, os.environ.get("GITHUB_TOKEN"), Path(temp), None)
        key = nachrechnen.key_for(meta["descriptor"])
        official = meta["status"].get("latest_official_snapshot_id")
        folder = dict(stands).get(official)
        if folder is None:
            print("::error title=Kurse gegenprüfen::Stand mit Schlusskursen nicht im Release gefunden")
            return 1
        report = run(nachrechnen.Stand(folder, official, key), official, http)
    for line in annotations(report):
        print(line)
    if args.bericht:
        args.bericht.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    z = report["zaehler"]
    return 1 if (z.get("tag_gross", 0) + z.get("rendite_abweichend", 0)) else 0


if __name__ == "__main__":
    started = time.monotonic()
    try:
        code = main()
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 - Abbruchgrund als Hinweis, ohne Inhalte
        print(f"::error title=Kurse gegenprüfen abgebrochen::{type(exc).__name__}: {str(exc).splitlines()[0][:200] if str(exc) else ''}")
        code = 1
    print(f"::notice title=Kurse gegenprüfen::Dauer {round(time.monotonic() - started)} s")
    sys.exit(code)
