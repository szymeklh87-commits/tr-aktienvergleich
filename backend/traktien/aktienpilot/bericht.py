"""Bericht je Spielgelddepot (Abschnitte 14, 21 und 22 des Auftrags): Kennzahlen, Monatsrenditen, Rückgang, Kosten,
Datenabdeckung, Vergleich mit den Vergleichsdepots, Hälftenvergleich, Block-Bootstrap, Warnungen, Prüfhürden,
Steuer-Modellrechnung und alle Ausführungen mit FIFO-Losen. **Eine** Rechnung für App, CSV-Export und HTML-Bericht – die
App rechnet nichts davon nach (Abschnitt 32).

Grundlage sind die täglichen Gesamtwerte nach simulierten Kosten (``ap_wert``) und die Buchungen des Depots. Zu- und Abflüsse
werden herausgerechnet: Tagesrendite r_t = (V_t − F_t) / V_{t−1} − 1 mit F_t = Einzahlungen − Auszahlungen am Tag t. Ein
unvollständig bewerteter Tag (Kurs oder Wechselkurs fehlte) ist kein Messpunkt; die Rendite läuft vom letzten bis zum nächsten
vollständigen Tag.

Formeln und Sonderfälle – ein nicht definierter Wert ist ``None`` mit Grund, nie 0 oder ein erfundener Erfolg:

* Rendite (zeitgewichtet) = Π(1 + r_t) − 1.
* CAGR = (1 + Rendite)^(365,25 / Kalendertage) − 1 – erst ab 365 Kalendertagen (kürzere Zeiträume hochgerechnet wären
  irreführend).
* Volatilität = Stichproben-Standardabweichung der r_t × √252 – ab 20 Tagesrenditen.
* Risikofreier Zins z_t: Wertänderung des Geldmarkt-ETF der Konfiguration (Euro-Übernachtzins) zwischen denselben Tagen. Fehlt
  ein Kurs, sind Sharpe und Sortino nicht definiert – es gibt keine feste Zinsannahme.
* Sharpe = Mittel(r_t − z_t) / Std(r_t − z_t) × √252; Sortino = Mittel(r_t − z_t) / √Mittel(min(0, r_t − z_t)²) × √252; beide ab
  20 Tagesrenditen, Sortino ohne negative Überschussrendite nicht definiert.
* Größter Rückgang vom bisherigen Höchststand des Renditeindex und längste Zeit darunter (Bewertungstage).
* Trades = Verkäufe der aktiven Strategien (auch Teilverkäufe; Robo-Kern ausgenommen) mit FIFO-Ergebnis nach Kosten.
  Trefferquote = Anteil mit Gewinn > 0; Profitfaktor = Σ Gewinne / |Σ Verluste| (ohne Verlusttrade nicht definiert); Ø Gewinn,
  Ø Verlust. Verkäufe mit unbekannten Anschaffungskosten zählen gesondert und nicht in die Quoten.
* Kapitalbindung = Ø Anteil des investierten Werts (Gesamtwert − Guthaben) am Gesamtwert der vollständigen Bewertungstage.
* Monatsrenditen = verkettete r_t je Kalendermonat; der erste und ein laufender letzter Monat sind „angebrochen“ (nach
  Werktagen, Börsenfeiertage nicht berücksichtigt).
* Hälftenvergleich: Rendite der ersten und der zweiten Hälfte der Tagesrenditen (ab 40). Das ist **kein** Walk-Forward: die Regeln
  werden nicht an den Daten optimiert, und drei Jahre Entwicklung plus ein Testjahr (Abschnitt 14) gibt die verfügbare Historie
  nicht her – das steht im Bericht. Warnung, wenn die zweite Hälfte mehr als 10 Prozentpunkte schlechter ist.
* Block-Bootstrap: 1.000 Pfade aus zufällig gezogenen Blöcken von 5 aufeinanderfolgenden Tagesrenditen (mit Zurücklegen, ab 20
  Tagesrenditen); Zufallsstartwert aus der Depotkennung (reproduzierbar). Quantile 5/50/95 % von Rendite und größtem Rückgang.
  Das untersucht Verlaufsrisiken – es beweist keinen Handelsvorteil.

Steuer-Modellrechnung (Abschnitt 21, keine Steuerabrechnung): realisierte Ergebnisse je Kalenderjahr nach FIFO; Aktien in einem
eigenen Verlusttopf (Aktienverluste nur mit Aktiengewinnen verrechenbar), Fondsergebnisse nach Teilfreistellung im allgemeinen
Topf, Verlustvorträge, Sparerpauschbetrag einmal je Jahr für das Depot, Steuersatz aus der Konfiguration. Getrennt: die
angenommene Veräußerung der offenen Positionen am Ende. Vorabpauschale nur mit hinterlegtem Basiszins – sonst steht der Hinweis
im Bericht, und es gibt keine Nachsteuer-Rendite.
"""

from __future__ import annotations

import calendar
import datetime as dt
import hashlib
import math
import re
from typing import Any, Callable, Iterable

import numpy as np

from ..util.timeutil import day_to_date
from .buchhaltung import Book, Event, is_active_owner

VERSION = "bericht-1"
HANDELSTAGE = 252
MIN_RENDITEN = 20
KURZ_SITZUNGEN = 60
KLEINE_STICHPROBE = 30
VIELE_BEDINGUNGEN = 8
BOOT_PFADE = 1000
BOOT_BLOCK = 5
HAELFTE_MIN = 40
HAELFTE_WARN_PP = 10.0
WALK_FORWARD_TAGE = 4 * HANDELSTAGE  # drei Jahre Entwicklung plus ein Testjahr (Abschnitt 14)
WELT_RE = re.compile(r"(^|-)v-welt(-|$)")
KERN_RE = re.compile(r"(^|-)v-kern(-|$)")


def _datum(day: int | None) -> str | None:
    return None if day is None else day_to_date(int(day)).isoformat()


def _f(x: Any, nd: int = 4) -> float | None:
    if x is None:
        return None
    v = float(x)
    return round(v, nd) if math.isfinite(v) else None


# ---------------------------------------------------------------------------------------------------------- Renditen


def renditen(werte: list[dict], fluesse: dict[int, float]) -> tuple[list[int], np.ndarray, int] | None:
    """Tage des Renditeindex (erster vollständiger Tag zuerst), Tagesrenditen, Zahl der ausgelassenen unvollständigen Tage.

    ``None``, wenn ein Ausgangswert ≤ 0 ist (Rendite nicht definiert)."""
    days: list[int] = []
    rets: list[float] = []
    prev: float | None = None
    pending = 0.0
    skipped = 0
    for w in werte:
        t = int(w["tag"])
        flow = float(fluesse.get(t, 0.0))
        if not w.get("vollstaendig", True):
            skipped += 1
            pending += flow
            continue
        v = float(w["gesamt_eur"])
        if prev is None:
            prev, pending = v, 0.0
            days.append(t)
            continue
        if prev <= 0:
            return None
        rets.append((v - flow - pending) / prev - 1.0)
        days.append(t)
        prev, pending = v, 0.0
    return days, np.asarray(rets, dtype=np.float64), skipped


def renditeindex(werte: list[dict], fluesse: dict[int, float]) -> tuple[list[int], np.ndarray] | None:
    """Renditeindex (1 am ersten vollständigen Tag) mit seinen Tagen; ``None`` wie bei :func:`renditen`."""
    r = renditen(werte, fluesse)
    if r is None:
        return None
    days, rets, _ = r
    if not days:
        return [], np.empty(0)
    return days, np.concatenate([[1.0], np.cumprod(1.0 + rets)])


def zeitgewichtet(werte: list[dict], fluesse: dict[int, float]) -> float | None:
    """Zeitgewichtete Rendite (Zu- und Abflüsse herausgerechnet); ``None`` ohne Bewertung oder bei Ausgangswert ≤ 0."""
    ix = renditeindex(werte, fluesse)
    if ix is None or not len(ix[1]):
        return None
    return float(ix[1][-1] - 1.0)


def _rueckgaenge(index: np.ndarray) -> np.ndarray:
    """Rückgang je Punkt vom bisherigen Höchststand (≤ 0)."""
    if not len(index):
        return np.empty(0)
    return index / np.maximum.accumulate(index) - 1.0


def max_rueckgang(werte: list[dict], fluesse: dict[int, float] | None = None) -> float:
    """Größter Rückgang (positiv, 0,25 = −25 %) des Renditeindex."""
    ix = renditeindex(werte, fluesse or {})
    if ix is None or not len(ix[1]):
        return 0.0
    return float(-_rueckgaenge(ix[1]).min())


def _unter_wasser(dd: np.ndarray) -> int:
    best = run = 0
    for x in dd:
        run = run + 1 if x < -1e-12 else 0
        best = max(best, run)
    return best


# ---------------------------------------------------------------------------------------------------------- Bausteine


def _monate(days: list[int], rets: np.ndarray) -> list[dict]:
    if len(days) < 2:
        return []
    first, last = day_to_date(days[0]), day_to_date(days[-1])
    groups: dict[tuple[int, int], list[float]] = {}
    for t, r in zip(days[1:], rets):
        d = day_to_date(t)
        groups.setdefault((d.year, d.month), []).append(float(r))
    out = []
    for (y, m), rs in sorted(groups.items()):
        partial = (y, m) == (first.year, first.month)
        if (y, m) == (last.year, last.month):
            end = calendar.monthrange(y, m)[1]
            partial = partial or any(dt.date(y, m, dd).weekday() < 5 for dd in range(last.day + 1, end + 1))
        out.append({"monat": f"{y:04d}-{m:02d}", "rendite_pct": _f(100.0 * (np.prod(1.0 + np.asarray(rs)) - 1.0), 2),
                    "tage": len(rs), "angebrochen": partial})
    return out


def _bootstrap(rets: np.ndarray, seed: int) -> dict:
    n = len(rets)
    if n < MIN_RENDITEN:
        return {"grund": f"zu wenige Tagesrenditen ({n} < {MIN_RENDITEN})"}
    b = min(BOOT_BLOCK, n)
    rng = np.random.default_rng(seed)
    blocks = -(-n // b)
    starts = rng.integers(0, n - b + 1, size=(BOOT_PFADE, blocks))
    idx = (starts[:, :, None] + np.arange(b)[None, None, :]).reshape(BOOT_PFADE, blocks * b)[:, :n]
    paths = np.cumprod(1.0 + rets[idx], axis=1)
    total = paths[:, -1] - 1.0
    peaks = np.maximum.accumulate(np.concatenate([np.ones((BOOT_PFADE, 1)), paths], axis=1), axis=1)[:, 1:]
    dd = (1.0 - paths / peaks).max(axis=1)
    q = lambda a: {f"p{p}": _f(100.0 * float(np.percentile(a, p)), 2) for p in (5, 50, 95)}  # noqa: E731
    return {"pfade": BOOT_PFADE, "block": b, "startwert": seed, "rendite_pct": q(total), "max_rueckgang_pct": q(dd)}


def _bedingungen(obj: Any) -> int:
    """Zahl der Bedingungen (Knoten mit Kennzahl und Operator) und Sortierkriterien einer Regel – für die Warnung „viele
    Parameter“ (strukturelle Zählung, keine zweite Regelprüfung)."""
    if isinstance(obj, dict):
        own = 1 if "kennzahl" in obj and ("op" in obj or "richtung" in obj) else 0
        return own + sum(_bedingungen(v) for v in obj.values())
    if isinstance(obj, list):
        return sum(_bedingungen(v) for v in obj)
    return 0


def _wert_am(days: list[int], index: np.ndarray, day: int) -> float | None:
    k = int(np.searchsorted(np.asarray(days, dtype=np.int64), day, side="right")) - 1
    return None if k < 0 else float(index[k])


def _vergleich(eigen: tuple[list[int], np.ndarray], fremd: tuple[list[int], np.ndarray], vid: str, name: str) -> dict:
    d_days, d_ix = eigen
    b_days, b_ix = fremd
    out = {"depot": vid, "name": name}
    if len(d_days) < 2 or len(b_days) < 2:
        return {**out, "grund": "zu wenige Bewertungstage"}
    a, e = max(d_days[0], b_days[0]), min(d_days[-1], b_days[-1])
    if a >= e:
        return {**out, "grund": "kein gemeinsamer Zeitraum"}
    da, de, ba, be = _wert_am(d_days, d_ix, a), _wert_am(d_days, d_ix, e), _wert_am(b_days, b_ix, a), _wert_am(b_days, b_ix, e)
    if not all(x is not None and x > 0 for x in (da, de, ba, be)):
        return {**out, "grund": "Index im gemeinsamen Zeitraum nicht bewertbar"}
    own, ref = de / da - 1.0, be / ba - 1.0
    sel = (np.asarray(b_days) >= a) & (np.asarray(b_days) <= e)
    seg = b_ix[sel] / b_ix[sel][0]
    return {**out, "von": _datum(a), "bis": _datum(e), "eigen_pct": _f(100 * own, 2), "vergleich_pct": _f(100 * ref, 2),
            "abstand_pp": _f(100 * (own - ref), 2), "max_rueckgang_vergleich_pct": _f(max(0.0, -100 * float(_rueckgaenge(seg).min())), 2)}


# ---------------------------------------------------------------------------------------------------------- Steuern


def _steuerjahr(a_plus: float, a_minus: float, fonds: float, vortrag_a: float, vortrag_g: float, pausch: float, satz: float) -> tuple[dict, float, float]:
    a = a_plus + a_minus + vortrag_a
    vortrag_a, a_pos = (a, 0.0) if a < 0 else (0.0, a)
    summe = a_pos + fonds + vortrag_g
    vortrag_g, basis = (summe, 0.0) if summe < 0 else (0.0, summe)
    genutzt = min(pausch, basis)
    pflichtig = basis - genutzt
    return ({"pauschbetrag_genutzt_eur": _f(genutzt, 2), "steuerpflichtig_eur": _f(pflichtig, 2), "steuer_eur": _f(pflichtig * satz, 2),
             "verlustvortrag_aktien_eur": _f(vortrag_a, 2), "verlustvortrag_allgemein_eur": _f(vortrag_g, 2)}, vortrag_a, vortrag_g)


def steuern(realisiert: Iterable, fondsart: Callable[[str], str], cfg, offen: list[tuple[str, float | None]], ende: int | None,
            fonds_gehalten: bool) -> dict:
    """Steuer-Modellrechnung je Kalenderjahr (siehe Modulbeschreibung). ``offen``: (ISIN, unrealisiertes Ergebnis oder None)."""
    tf = float(cfg.teilfreistellung_aktienfonds)
    satz = float(cfg.rate())
    pausch = float(cfg.sparerpauschbetrag_eur)
    jahre: dict[int, dict] = {}

    def add(year: int, isin: str, gain: float | None, store: dict) -> None:
        j = store.setdefault(year, {"aktien_plus": 0.0, "aktien_minus": 0.0, "fonds": 0.0, "unbekannt": 0})
        if gain is None:
            j["unbekannt"] += 1
            return
        art = fondsart(isin)
        if art == "Aktie":
            j["aktien_plus" if gain > 0 else "aktien_minus"] += gain
        else:
            j["fonds"] += gain * ((1.0 - tf) if art == "Aktienfonds" else 1.0)

    for r in realisiert:
        add(day_to_date(r.day).year, r.isin, r.gain_eur, jahre)
    out = []
    va = vg = 0.0
    letzte = None
    for year in sorted(jahre):
        j = jahre[year]
        res, va, vg = _steuerjahr(j["aktien_plus"], j["aktien_minus"], j["fonds"], va, vg, pausch, satz)
        letzte = (year, j, res)
        out.append({"jahr": year, "aktien_gewinne_eur": _f(j["aktien_plus"], 2), "aktien_verluste_eur": _f(j["aktien_minus"], 2),
                    "fonds_ergebnis_eur": _f(j["fonds"], 2), "unbekannte_kosten": j["unbekannt"], **res})
    # angenommene Veräußerung am Ende (getrennt ausgewiesen, Abschnitt 21)
    verkauf = None
    if ende is not None and offen:
        year = day_to_date(ende).year
        hypo = {year: dict(jahre.get(year, {"aktien_plus": 0.0, "aktien_minus": 0.0, "fonds": 0.0, "unbekannt": 0}))}
        for isin, gain in offen:
            add(year, isin, gain, hypo)
        # Vorträge bis zum Vorjahr nachbilden
        va0 = vg0 = 0.0
        for y in sorted(jahre):
            if y >= year:
                break
            _r, va0, vg0 = _steuerjahr(jahre[y]["aktien_plus"], jahre[y]["aktien_minus"], jahre[y]["fonds"], va0, vg0, pausch, satz)
        h = hypo[year]
        mit, _a, _g = _steuerjahr(h["aktien_plus"], h["aktien_minus"], h["fonds"], va0, vg0, pausch, satz)
        ohne_j = jahre.get(year)
        ohne = _steuerjahr(ohne_j["aktien_plus"], ohne_j["aktien_minus"], ohne_j["fonds"], va0, vg0, pausch, satz)[0] if ohne_j else {"steuer_eur": 0.0}
        verkauf = {"jahr": year, "zusaetzliche_steuer_eur": _f((mit["steuer_eur"] or 0.0) - (ohne["steuer_eur"] or 0.0), 2),
                   "unbekannte_kosten": h["unbekannt"] - (ohne_j or {}).get("unbekannt", 0)}
    hinweise = [
        "Modellrechnung, keine Steuerabrechnung; Rechtsstand vor Nutzung prüfen.",
        f"Steuersatz {satz * 100:.3f} % ".replace(".", ",") + f"(Abgeltungsteuer {cfg.abgeltungsteuer * 100:.0f} % plus Solidaritätszuschlag"
        + (f", Kirchensteuer {cfg.kirchensteuer * 100:.0f} %)." if cfg.kirchensteuer > 0 else ", ohne Kirchensteuer)."),
        f"Sparerpauschbetrag {pausch:,.0f} EUR je Kalenderjahr einmal für dieses Depot; ein anderweitig verbrauchter Anteil ist nicht erfasst.".replace(",", "."),
        "Aktienverluste nur mit Aktiengewinnen verrechnet; Fondsergebnisse nach Teilfreistellung "
        f"({tf * 100:.0f} % bei Aktienfonds) im allgemeinen Topf.",
        "Dividenden und Quellensteuer sind nicht enthalten.",
    ]
    if fonds_gehalten:
        basis = {str(k) for k in (getattr(cfg, "basiszins_vorabpauschale", {}) or {})}
        alle = set(jahre) | ({day_to_date(ende).year} if ende is not None else set())
        fehlt = sorted(y for y in alle if str(y) not in basis)
        if fehlt:
            hinweise.append(f"Vorabpauschale nicht berechnet: Basiszins für {', '.join(map(str, fehlt))} nicht hinterlegt – keine Nachsteuer-Rendite.")
    return {"satz_pct": _f(100 * satz, 3), "jahre": out, "verkauf_am_ende": verkauf, "hinweise": hinweise}


# ---------------------------------------------------------------------------------------------------------- Ausführungen


def ausfuehrungen(events: Iterable[Event], book: Book) -> list[dict]:
    """Alle Käufe und Verkäufe (Abschnitt 21): ISIN, Menge, Zeit, Währung, Kurs, Gebühren, Eurobetrag, Quelle der Umrechnung und
    die verbrauchten Anschaffungslose nach FIFO (unbekannte Kosten als ``None``)."""
    by_event = {r.event_id: r for r in book.realized}
    out = []
    for e in events:
        if e.typ not in ("kauf", "verkauf"):
            continue
        r = by_event.get(e.id)
        out.append({
            "datum": _datum(e.tag), "zeit": e.zeit, "art": e.typ, "isin": e.isin, "stueck": e.stueck, "kurs": e.kurs, "waehrung": e.waehrung,
            "fx_eur": e.fx_eur, "fx_quelle": e.fx_quelle, "gebuehren_eur": _f(e.gebuehren_eur, 2), "betrag_eur": _f(e.betrag_eur, 2),
            "zuordnung": e.owner, "order": e.order_id,
            "ergebnis_eur": None if r is None else _f(r.gain_eur, 2),
            "lose": None if r is None else [{"kauf": _datum(day), "stueck": _f(q, 6), "kosten_eur": _f(c, 2)} for (_eid, day, q, c) in r.lots],
        })
    return out


# ---------------------------------------------------------------------------------------------------------- Bericht


def berechnen(*, depot_id: str, werte: list[dict], fluesse: dict[int, float], book: Book, events: list[Event], startkapital: float,
              historisch: bool, synthetisch: bool, regeln: list[dict], vergleiche: list[tuple[str, str, list[dict], dict[int, float]]],
              zins_kurs: Callable[[int], float | None] | None, zins_quelle: str | None, fondsart: Callable[[str], str], steuer_cfg,
              freigabe_cfg, offen: list[tuple[str, float | None]], datenstand: str | None, ap_version: str) -> dict:
    nd: dict[str, str] = {}  # Kennzahl → Grund, warum sie nicht definiert ist
    r = renditen(werte, fluesse)
    complete = [w for w in werte if w.get("vollstaendig", True)]
    head = {"version": VERSION, "bewertungstage": len(werte), "unvollstaendig": len(werte) - len(complete)}
    if r is None:
        return {**head, "grund": "Ausgangswert ≤ 0 – Rendite nicht definiert"}
    days, rets, _skipped = r
    if len(days) < 2:
        return {**head, "grund": "noch keine zwei vollständigen Bewertungstage"}
    index = np.concatenate([[1.0], np.cumprod(1.0 + rets)])
    dd = _rueckgaenge(index)
    n = len(rets)
    kalendertage = days[-1] - days[0]
    total = float(index[-1] - 1.0)
    k: dict[str, Any] = {"rendite_pct": _f(100 * total, 2)}
    if kalendertage >= 365:
        k["cagr_pct"] = _f(100 * ((1.0 + total) ** (365.25 / kalendertage) - 1.0), 2)
    else:
        k["cagr_pct"] = None
        nd["cagr_pct"] = f"Zeitraum unter einem Jahr ({kalendertage} Kalendertage) – eine Hochrechnung wäre irreführend"
    if n >= MIN_RENDITEN:
        k["volatilitaet_pct"] = _f(100 * float(np.std(rets, ddof=1)) * math.sqrt(HANDELSTAGE), 2)
    else:
        k["volatilitaet_pct"] = None
        nd["volatilitaet_pct"] = f"zu wenige Tagesrenditen ({n} < {MIN_RENDITEN})"
    # risikofreier Zins aus dem Geldmarkt-ETF
    zins = None
    zins_grund = None
    if zins_kurs is None or not zins_quelle:
        zins_grund = "Geldmarkt-ETF nicht konfiguriert"
    else:
        preise = [zins_kurs(t) for t in days]
        missing = sum(1 for p in preise if p is None or not p > 0)
        if missing:
            zins_grund = f"Kurs des Geldmarkt-ETF fehlt an {missing} von {len(days)} Bewertungstagen"
        else:
            p = np.asarray(preise, dtype=np.float64)
            zins = p[1:] / p[:-1] - 1.0
    for key in ("sharpe", "sortino"):
        k[key] = None
    if zins is None:
        nd["sharpe"] = nd["sortino"] = f"risikofreier Zins nicht verfügbar ({zins_grund})"
    elif n < MIN_RENDITEN:
        nd["sharpe"] = nd["sortino"] = f"zu wenige Tagesrenditen ({n} < {MIN_RENDITEN})"
    elif float(np.std(rets)) == 0.0:
        nd["sharpe"] = nd["sortino"] = "Depotwert ohne Schwankung (nichts investiert)"
    else:
        ex = rets - zins
        sd = float(np.std(ex, ddof=1))
        if sd > 0:
            k["sharpe"] = _f(float(np.mean(ex)) / sd * math.sqrt(HANDELSTAGE), 2)
        else:
            nd["sharpe"] = "keine Schwankung der Überschussrendite"
        down = math.sqrt(float(np.mean(np.minimum(ex, 0.0) ** 2)))
        if down > 0:
            k["sortino"] = _f(float(np.mean(ex)) / down * math.sqrt(HANDELSTAGE), 2)
        else:
            nd["sortino"] = "keine negative Überschussrendite"
    k["max_rueckgang_pct"] = _f(max(0.0, -100 * float(dd.min())), 2)
    k["unter_wasser_tage"] = _unter_wasser(dd)
    # Trades der aktiven Strategien
    trades = [x for x in book.realized if is_active_owner(x.owner)]
    known = [float(x.gain_eur) for x in trades if x.gain_eur is not None]
    wins = [g for g in known if g > 0]
    losses = [g for g in known if g < 0]
    k["trades"] = len(known)
    k["trades_unbekannt"] = len(trades) - len(known)
    if known:
        k["trefferquote_pct"] = _f(100 * len(wins) / len(known), 1)
    else:
        k["trefferquote_pct"] = None
        nd["trefferquote_pct"] = "noch kein abgeschlossener Trade"
    if losses:
        k["profitfaktor"] = _f(sum(wins) / abs(sum(losses)), 2)
    else:
        k["profitfaktor"] = None
        nd["profitfaktor"] = "noch kein abgeschlossener Trade" if not known else "kein Verlusttrade – Profitfaktor nicht definiert"
    k["gewinn_mittel_eur"] = _f(sum(wins) / len(wins), 2) if wins else None
    if not wins:
        nd["gewinn_mittel_eur"] = "kein Gewinntrade"
    k["verlust_mittel_eur"] = _f(sum(losses) / len(losses), 2) if losses else None
    if not losses:
        nd["verlust_mittel_eur"] = "kein Verlusttrade"
    bindung = [(float(w["gesamt_eur"]) - float(w.get("guthaben_eur", 0.0))) / float(w["gesamt_eur"]) for w in complete if float(w["gesamt_eur"]) > 0]
    k["kapitalbindung_pct"] = _f(100 * sum(bindung) / len(bindung), 1) if bindung else None
    k["kosten_eur"] = _f(book.fees_eur, 2)
    k["kosten_pct_start"] = _f(100 * book.fees_eur / startkapital, 2) if startkapital > 0 else None
    k["ausfuehrungen"] = sum(1 for e in events if e.typ in ("kauf", "verkauf"))
    # Hälftenvergleich
    if n >= HAELFTE_MIN:
        m = n // 2
        erste = float(np.prod(1.0 + rets[:m]) - 1.0)
        zweite = float(np.prod(1.0 + rets[m:]) - 1.0)
        haelften = {"erste": {"von": _datum(days[0]), "bis": _datum(days[m]), "rendite_pct": _f(100 * erste, 2)},
                    "zweite": {"von": _datum(days[m]), "bis": _datum(days[-1]), "rendite_pct": _f(100 * zweite, 2)},
                    "warnung": 100 * (erste - zweite) > HAELFTE_WARN_PP}
    else:
        haelften = {"grund": f"zu kurz für einen Hälftenvergleich ({n} Tagesrenditen, mindestens {HAELFTE_MIN})"}
    # Vergleichsdepots
    eigen = (days, index)
    vergl = []
    for vid, vname, vwerte, vfluesse in vergleiche:
        vix = renditeindex(vwerte, vfluesse)
        vergl.append(_vergleich(eigen, vix, vid, vname) if vix is not None else {"depot": vid, "name": vname, "grund": "Vergleichsdepot nicht bewertbar"})
    # Bootstrap
    seed = int(hashlib.sha256(depot_id.encode("utf-8")).hexdigest()[:8], 16)
    boot = _bootstrap(rets, seed)
    # Prüfhürden (Abschnitt 22) – nur zur Einordnung, Echtgeld bleibt ausgeschlossen
    vorwaerts = not historisch and not synthetisch
    nicht_vorwaerts = "historische Simulation – zählt nicht als Vorwärtstest" if historisch else ("DEMO – synthetische Kurse" if synthetisch else None)
    welt = next((v for v in vergl if "abstand_pp" in v and WELT_RE.search(v["depot"])), None)
    huerden = [
        {"id": "trades", "text": f"mindestens {freigabe_cfg.min_trades_oos} abgeschlossene Trades im Vorwärtstest", "wert": k["trades"],
         "erfuellt": (k["trades"] >= freigabe_cfg.min_trades_oos) if vorwaerts else None, "grund": nicht_vorwaerts},
        {"id": "profitfaktor", "text": f"Profitfaktor mindestens {str(freigabe_cfg.min_profitfaktor).replace('.', ',')}", "wert": k["profitfaktor"],
         "erfuellt": None if k["profitfaktor"] is None else k["profitfaktor"] >= freigabe_cfg.min_profitfaktor, "grund": nd.get("profitfaktor")},
        {"id": "rueckgang", "text": f"größter Rückgang höchstens {freigabe_cfg.max_drawdown * 100:.0f} %", "wert": k["max_rueckgang_pct"],
         "erfuellt": k["max_rueckgang_pct"] <= 100 * freigabe_cfg.max_drawdown, "grund": None},
        {"id": "benchmark", "text": "Rendite über dem Welt-ETF-Depot im selben Zeitraum", "wert": None if welt is None else welt["abstand_pp"],
         "erfuellt": None if welt is None else welt["abstand_pp"] > 0, "grund": None if welt is not None else "kein Vergleichsdepot mit gemeinsamem Zeitraum"},
        {"id": "sitzungen", "text": f"mindestens {freigabe_cfg.min_paper_sitzungen} Sitzungen Vorwärtstest mit Spielgeld", "wert": len(werte),
         "erfuellt": (len(werte) >= freigabe_cfg.min_paper_sitzungen) if vorwaerts else None, "grund": nicht_vorwaerts},
        {"id": "ausfuehrungen", "text": f"mindestens {freigabe_cfg.min_paper_ausfuehrungen} Ausführungen im Vorwärtstest", "wert": k["ausfuehrungen"],
         "erfuellt": (k["ausfuehrungen"] >= freigabe_cfg.min_paper_ausfuehrungen) if vorwaerts else None, "grund": nicht_vorwaerts},
    ]
    # Warnungen
    warnungen = []
    if len(werte) < KURZ_SITZUNGEN:
        warnungen.append(f"Kurzer Zeitraum ({len(werte)} Bewertungstage): die Kennzahlen schwanken stark.")
    if 0 < len(known) < KLEINE_STICHPROBE:
        warnungen.append(f"Kleine Stichprobe: {len(known)} abgeschlossene Trades (unter {KLEINE_STICHPROBE}).")
    bed = max((_bedingungen(rg) for rg in regeln), default=0)
    if bed > VIELE_BEDINGUNGEN:
        warnungen.append(f"Viele Bedingungen und Sortierkriterien ({bed}): Gefahr der Überanpassung an vergangene Daten.")
    if haelften.get("warnung"):
        warnungen.append(f"Die zweite Hälfte ist mehr als {HAELFTE_WARN_PP:.0f} Prozentpunkte schlechter als die erste.")
    if head["unvollstaendig"]:
        warnungen.append(f"An {head['unvollstaendig']} Bewertungstagen fehlten Kurse – diese Tage sind nicht in den Renditen.")
    if k["trades_unbekannt"]:
        warnungen.append(f"{k['trades_unbekannt']} Verkäufe mit unbekannten Anschaffungskosten zählen nicht in die Quoten.")
    annahmen = [
        "Werte nach simulierten Kosten (Spread, Slippage, Wechselkursaufschlag, Ordergebühr) – Annahmen, kein Nachweis der tatsächlichen Kosten.",
        "Kurse nicht dividendenbereinigt; Dividenden sind nicht enthalten.",
        "Ausführung zum Schlusskurs der Folgesitzung; Stops mit der fertigen Tageskerze geprüft.",
    ]
    if historisch:
        annahmen.append("Historische Simulation: Ranglisten je Tag nur mit Kursen bis zu diesem Tag nachgerechnet; heutige Datenrevision und "
                        "heutiges Universum – Rückschau-Verzerrung und Survivorship-Bias möglich, damalige TR-Zugehörigkeit nicht belegt.")
    if synthetisch:
        annahmen.append("DEMO: synthetische Kurse – keine Aussage über echte Märkte.")
    walk = (f"Walk-Forward nach Abschnitt 14 (drei Jahre Entwicklung, danach ein Testjahr) ist mit {len(werte)} Bewertungstagen nicht möglich."
            if len(werte) < WALK_FORWARD_TAGE else "Walk-Forward nicht durchgeführt.")
    walk += " Die Regeln werden nicht an diesen Daten optimiert; der Hälftenvergleich ersetzt keinen Walk-Forward."
    fonds_gehalten = any(fondsart(e.isin) != "Aktie" for e in events if e.typ == "kauf" and e.isin)
    return {
        **head,
        "zeitraum": {"von": _datum(days[0]), "bis": _datum(days[-1]), "kalendertage": kalendertage, "renditetage": n},
        "kennzahlen": k, "nicht_definiert": nd,
        "zins": {"quelle": zins_quelle, "rendite_pct": _f(100 * (float(np.prod(1.0 + zins)) - 1.0), 3)} if zins is not None else {"quelle": zins_quelle, "grund": zins_grund},
        "monate": _monate(days, rets),
        "rueckgang": {"tag": [_datum(t) for t in days], "pct": [_f(min(0.0, 100 * float(x)), 2) for x in dd]},
        "haelften": haelften, "vergleiche": vergl, "bootstrap": boot, "huerden": huerden, "warnungen": warnungen,
        "walk_forward": walk, "annahmen": annahmen,
        "steuern": steuern(book.realized, fondsart, steuer_cfg, offen, days[-1], fonds_gehalten),
        "reproduzierbar": {"datenstand": datenstand, "programm": ap_version, "bericht": VERSION, "startwert": seed,
                           "regeln": [f"{rg.get('id')}@{rg.get('version')}" for rg in regeln if isinstance(rg, dict)]},
    }
