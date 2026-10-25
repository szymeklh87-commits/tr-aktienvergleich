"""Auffällige Aktien beim Abgleich mit einem zweiten Börsenplatz – einzeln untersucht (ab 1.19.0, Prüfskript; App unverändert).

Simons Auftrag vom 25.10.2026, 14:23 Uhr, Punkt 1: „Untersuche die 8 auffälligen Aktien in 51 Zeiträumen über den vorhandenen
autorisierten Entschlüsselungsweg. Verschlüsselung und Zugangsschutz beibehalten. … Vergleiche nur zusammenpassende
Notierungen, Währungen, Handelstage und Kursarten. Korrigiere Daten nur mit belegter Grundlage.“

Der Stand kommt aus dem Release und wird – nur in GitHub Actions, mit dem Secret DATA_PASSPHRASE – über denselben Weg
entschlüsselt wie in der unabhängigen Nachrechnung (``nachrechnen.Stand``). Ausgewertet werden die Ergebnisse des Abgleichs,
die der tägliche Lauf in den Stand geschrieben hat (``boersenplatz-v3``, Hinweis ohne Wirkung auf Rendite und Rang):

1. je auffälliger Aktie: Vergleichsplatz (Börsencode), Endkurs-Verhältnis und Schwellen, übliche Tagesschwankung, Zahl der
   auffälligen und der geprüften Zeiträume, größte Abweichung der Wertentwicklung gegen ihre Schwelle;
2. eine **dritte Quelle** für die Referenznotierung: CNBC (Kursmeldung mit Name, Börse, Währung; Tageskerzen) an Start- und
   Endtag jedes auffälligen Zeitraums – nur wenn Name, Börse und Währung zur Referenz passen. Bestätigt CNBC die Kurse der
   Referenz, liegt die Abweichung am Vergleichsplatz; widerspricht CNBC, ist der Kurs der Referenz fraglich. Ohne passende
   Kursmeldung bleibt die Frage offen. Nichts wird korrigiert: der Abgleich ändert weder Rendite noch Rang.

Öffentlich ausgegeben werden nur Buchstaben, Börsencodes, Fundstellen in der App (Zeitraum/Gruppe/Gewichtung und Platz),
Zählwerte und Prozentwerte – keine Kurse, Namen, Kürzel oder ISINs.
"""

from __future__ import annotations

import argparse
import datetime as dt
import math
import os
import sys
import tempfile
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "backend"))

import kurse_absicherung as absicherung  # noqa: E402
import kurse_ursachen as ursachen  # noqa: E402
import kurse_welt as welt  # noqa: E402
import nachrechnen  # noqa: E402

LETTERS = [chr(c) for c in range(ord("A"), ord("Z") + 1)]
NAME_MIN = 0.5  # wie bei der Absicherung der Vergleichskurse


def letter(k: int) -> str:
    return LETTERS[k] if k < len(LETTERS) else f"Z{k - len(LETTERS) + 1}"


def notice(title: str, lines: list[str], level: str = "notice") -> None:
    """Hinweise wie in den anderen Prüfskripten: Titel mit kodierten Kommas, Text auf Hinweise unter 3.000 Byte verteilt."""
    for part in ursachen.gegen.chunked(lines):
        body = "%0A".join(line.replace("%", "%25").replace("\r", " ").replace("\n", " ") for line in part)
        print(f"::{level} title={ursachen.gegen._title(title)}::{body}")


def pct(value: float | None, digits: int = 1) -> str:
    return "–" if value is None or not math.isfinite(value) else f"{100 * value:.{digits}f} %".replace(".", ",")


def flagged_pairs(stand) -> dict[int, list[dict]]:
    """Auffällige Paare (Aktie, Zeitraum) aus den Zeitraumdateien: je Aktie die Zeiträume mit Status „abweichung“ samt
    Rendite und Kursen der Referenz (aus „m“) und des Vergleichsplatzes (aus „xv“)."""
    out: dict[int, list[dict]] = {}
    checked: Counter = Counter()
    for h in range(1, 91):
        win = stand.get(f"windows/{h}.full.bin")
        stand.drop(f"windows/{h}.full.bin")
        xv = win.get("xv") or {}
        m = win.get("m") or {}
        pos = {int(i): k for k, i in enumerate(m.get("idx") or [])}
        for k, i in enumerate(xv.get("idx") or []):
            i = int(i)
            checked[i] += 1
            if (xv.get("status") or [None])[k] != "abweichung":
                continue
            j = pos.get(i)
            out.setdefault(i, []).append({
                "h": h,
                "dev": (xv.get("dev") or [None])[k],
                "r_alt": (xv.get("r") or [None])[k],
                "r_ref": (m.get("r") or [None])[j] if j is not None else None,
                "d0": (xv.get("d0") or [None])[k], "d1": (xv.get("d1") or [None])[k],
                "ref_d0": (m.get("start") or [None])[j] if j is not None else None,
                "ref_p0": (m.get("p0") or [None])[j] if j is not None else None,
                "ref_p1": (m.get("p1") or [None])[j] if j is not None else None,
            })
    for i in out:
        for p in out[i]:
            p["geprueft"] = checked[i]
    return out


US_WORDS = ("NASDAQ", "NYSE", "NEW YORK", "AMEX", "ARCA", "CBOE", "BATS")  # US-Börsen bei CNBC (OTC ausgenommen)
OTC_WORDS = ("OTC", "PINK")


def venue_matches(source_exchange: str | None, exchange_key: str | None) -> bool:
    """Börse bei CNBC passt zur Referenznotierung: wie im Job „welt“, dazu US-Börsen (der Job „welt“ prüft keine US-Aktien –
    sie haben die Nasdaq-Jobs) und OTC getrennt."""
    text = (source_exchange or "").upper()
    if exchange_key in absicherung.US_FAMILY:
        return any(w in text for w in US_WORDS) and not any(w in text for w in OTC_WORDS)
    if exchange_key in absicherung.OTC_FAMILY:
        return any(w in text for w in OTC_WORDS)
    return welt.venue_check(source_exchange, exchange_key) == "gleich"


def venue_label(source_exchange: str | None) -> str:
    """Börse laut CNBC als Code für den Befund (US-Börse, OTC oder Schlüssel der Tabelle) – kein Name einer Aktie."""
    text = (source_exchange or "").upper()
    if any(w in text for w in OTC_WORDS):
        return "OTC"
    if any(w in text for w in US_WORDS):
        return "US-Börse"
    return welt.venue_key(source_exchange)


def cnbc_reference(http, symbol: str, exchange_key: str | None, names: list[str], currency: str | None, unit: str | None,
                   start_day: int, cutoff: int, pause=None) -> tuple[str, dict[int, float]]:
    """Tageskurse der Referenznotierung bei CNBC in der Einheit des Stands – nur, wenn Name, Börse und Währung passen
    (sonst kein Vergleich, Grund als Code)."""
    candidates = welt.cnbc_candidates(symbol, exchange_key)
    if not candidates:
        return "keine_kuerzelregel", {}
    pause = pause or welt.time.sleep
    quotes, _, failed = welt.fetch_quotes(http, candidates, pause=pause)
    found = next((c for c in candidates if c.upper() in quotes), None)
    if found is None:
        return ("ohne_antwort" if failed else "nicht_gefunden"), {}
    meta = quotes[found.upper()]
    if absicherung.name_score(meta.get("name"), names) < NAME_MIN:
        return "name_passt_nicht", {}
    if not venue_matches(meta.get("boerse"), exchange_key):
        return f"boerse_passt_nicht:{venue_label(meta.get('boerse'))}", {}
    state, factor = welt.unit_factor(meta.get("waehrung"), currency, unit)
    if state != "gleich":
        return f"waehrung_{state}", {}
    code, rows = welt.fetch_bars(http, found, start_day, cutoff, pause=pause)
    if code not in ("ok", "ok_ohne_kurse"):
        return "ohne_antwort", {}
    return ("ok" if rows else "keine_kurse"), {d: float(r["close"]) * factor for d, r in rows.items() if r.get("close") is not None}


def judge(ref: float | None, third: float | None) -> str:
    if ref is None:
        return "ohne_referenzkurs"
    if third is None:
        return "dritte_quelle_ohne_tag"
    return "bestaetigt" if abs(ref - third) <= max(ursachen.gegen.tolerance(third), 1e-6 * abs(third)) else "widerspricht"


def run(stand, sid: str, http, pause=None) -> dict:
    instruments = stand.get("instruments.bin")
    manifest = stand.get("manifest.bin")
    cutoff = int(manifest["cutoff_day"])
    venue = instruments.get("venue") or {}
    summary = manifest.get("venue_check") or {}
    rows = {int(i): k for k, i in enumerate(venue.get("idx") or [])}
    pairs = flagged_pairs(stand)
    flagged = sorted(pairs, key=lambda i: (-len(pairs[i]), i))
    places = ursachen.best_places(stand, set(flagged))
    names_of = instruments.get("name") or [None] * len(instruments["isin"])
    report = {"stand": sid, "stichtag": nachrechnen._iso(cutoff), "zaehlung": summary.get("anzahl") or {}, "version": summary.get("version"),
              "aktien": [], "dritte_quelle": Counter(), "zeitraeume": 0}
    for k, i in enumerate(flagged):
        v = rows.get(i)
        alt_key = (venue.get("exchange_key") or [None])[v] if v is not None else None
        level = (venue.get("level") or [None])[v] if v is not None else None
        limit_r = (venue.get("limit_r") or [None])[v] if v is not None else None
        limit_l = (venue.get("limit_l") or [None])[v] if v is not None else None
        noise = (venue.get("noise") or [None])[v] if v is not None else None
        ps = pairs[i]
        worst = max(ps, key=lambda p: abs(p["dev"] or 0.0))
        first = min((p["ref_d0"] for p in ps if p["ref_d0"] is not None), default=cutoff - 95)
        own_key = (instruments.get("exchange_key") or [None] * len(instruments["isin"]))[i]
        name = names_of[i]
        state, third = cnbc_reference(http, str((instruments.get("symbol") or [""] * (i + 1))[i] or ""), own_key, [name] if name else [],
                                      (instruments.get("currency") or [None] * (i + 1))[i], (instruments.get("price_unit") or [None] * (i + 1))[i],
                                      first - 5, cutoff, pause=pause)
        series = stand.get(f"series/{instruments['isin'][i]}.bin")
        end_day = max((int(d) for d, c in zip(series["d"], series["c"]) if c is not None and int(d) <= cutoff), default=None)
        checks: Counter = Counter()
        for p in ps:
            if state != "ok":
                checks[f"keine_dritte_quelle_{state}"] += 2
                continue
            checks[judge(p["ref_p0"], third.get(p["ref_d0"]) if p["ref_d0"] is not None else None)] += 1
            checks[judge(p["ref_p1"], third.get(end_day) if end_day is not None else None)] += 1
        report["dritte_quelle"].update(checks)
        report["zeitraeume"] += len(ps)
        place = places.get(i)
        report["aktien"].append({
            "aktie": letter(k), "boerse": own_key or "–", "vergleich": alt_key or "–", "zeitraeume": len(ps), "geprueft": ps[0]["geprueft"],
            "endkurs": level, "endkurs_auffaellig": bool((venue.get("level_flag") or [False])[v]) if v is not None else False,
            "schwelle_w": limit_r, "schwelle_e": limit_l, "schwankung": noise, "groesste": worst["dev"], "groesste_h": worst["h"],
            "dritte_quelle": state, "pruefungen": dict(checks),
            "fundstelle": f"{place[1]}/{'AB'[place[2]]}/{place[3]} Platz {place[0]}" if place else "in keiner Rangliste",
        })
    report["dritte_quelle"] = dict(report["dritte_quelle"])
    return report


CHECK_TEXT = {"bestaetigt": "Kurs der Referenz von CNBC bestätigt", "widerspricht": "CNBC widerspricht dem Kurs der Referenz",
              "dritte_quelle_ohne_tag": "CNBC ohne Kurs am Tag", "ohne_referenzkurs": "Stand ohne Kurs am Tag",
              "keine_dritte_quelle_nicht_gefunden": "bei CNBC nicht gefunden", "keine_dritte_quelle_keine_kuerzelregel": "keine Kürzelregel für CNBC",
              "keine_dritte_quelle_name_passt_nicht": "Name bei CNBC passt nicht", "keine_dritte_quelle_boerse_passt_nicht": "Börse bei CNBC passt nicht",
              "keine_dritte_quelle_ohne_antwort": "CNBC ohne Antwort", "keine_dritte_quelle_keine_kurse": "CNBC ohne Kerzen"}


def check_text(key: str) -> str:
    if key.startswith("keine_dritte_quelle_boerse_passt_nicht:"):
        return f"Börse bei CNBC passt nicht (laut CNBC: {key.split(':', 1)[1]})"
    return CHECK_TEXT.get(key, key)


def lines(report: dict) -> tuple[str, list[str], list[str]]:
    z = report["zaehlung"] or {}
    head = [
        f"Stand {report['stand']} (Kursstand {report['stichtag']}), Abgleich {report.get('version') or '–'}: auffällige Aktien laut Stand {z.get('auffaellige_aktien', 0)}, "
        f"Aktie × Zeitraum nach Status {', '.join(f'{k} {v}' for k, v in (z.get('aktie_zeitraum') or {}).items()) or '–'}; Aktien nach Status "
        f"{', '.join(f'{k} {v}' for k, v in (z.get('aktien') or {}).items()) or '–'}. Hier einzeln: {len(report['aktien'])} Aktien in {report['zeitraeume']} auffälligen Zeiträumen.",
        "Dritte Quelle für die Referenznotierung (CNBC, nur mit passendem Namen, passender Börse und Währung; Start- und Endkurs je auffälligem Zeitraum): "
        + (", ".join(f"{check_text(k)} {v}" for k, v in sorted(report["dritte_quelle"].items())) or "–")
        + ". Lesart: bestätigt CNBC die Referenz, liegt die Abweichung am Vergleichsplatz (Kurs dort, Schlusszeit, Umrechnung) – die Referenz bleibt maßgeblich; "
        "widerspricht CNBC, ist der Kurs der Referenz fraglich (Datenfehler möglich, nicht belegt). Der Abgleich ändert weder Rendite noch Rang; korrigiert wird nichts.",
    ]
    rows = []
    for a in report["aktien"]:
        rows.append(
            f"{a['aktie']} = {a['fundstelle']} – {a['boerse']} gegen {a['vergleich']}: auffällig in {a['zeitraeume']} von {a['geprueft']} geprüften Zeiträumen; "
            f"größte Abweichung der Wertentwicklung am Vergleichsplatz {pct(a['groesste'])} ({a['groesste_h']} Tage; Schwelle ±{pct(a['schwelle_w'])}); Endkurs am "
            f"Vergleichsplatz {pct(a['endkurs'])} gegenüber der Referenz (Schwelle ±{pct(a['schwelle_e'])}{', auffällig' if a['endkurs_auffaellig'] else ''}); "
            f"übliche Tagesschwankung {pct(a['schwankung'])}; dritte Quelle: "
            + (", ".join(f"{check_text(k)} {v}" for k, v in sorted(a["pruefungen"].items())) or a["dritte_quelle"])
        )
    title = f"Börsenplatz-Abgleich: {len(report['aktien'])} auffällige Aktien in {report['zeitraeume']} Zeiträumen einzeln untersucht"
    return title, head, rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", "szymeklh87-commits/tr-aktienvergleich"))
    parser.add_argument("--stand", default=os.environ.get("STAND") or None)
    args = parser.parse_args(argv)
    from traktien.providers.http import HttpClient

    with tempfile.TemporaryDirectory() as temp:
        sid, folder, key = ursachen.load_stand(args.repo, os.environ.get("GITHUB_TOKEN"), Path(temp), args.stand)
        stand = nachrechnen.Stand(folder, sid, key)
        http = HttpClient(impersonate="chrome", max_retries=1, timeout=12, min_interval={**ursachen.zusatz.HOSTS})
        report = run(stand, sid, http)
    title, head, rows = lines(report)
    notice(title, head)
    notice("Börsenplatz-Abgleich – je Aktie (Buchstaben statt Namen)", rows)
    open_ = unresolved(report)
    if open_:
        # Datenqualitätsbefund, kein App-Fehler: der Job wird rot, damit nichts als „bestätigt“ durchgeht (Simon, 25.10.2026:
        # „Keine Prüfungen abschwächen oder Fehler verstecken, damit Läufe grün erscheinen.“)
        print(f"::error title={ursachen.gegen._title('Börsenplatz-Abgleich: nicht vollständig bestätigt')}::"
              + "%0A".join(open_))
        return 1
    return 0


def unresolved(report: dict) -> list[str]:
    """Was der dritte Abgleich offen lässt – als Zeilen ohne Namen (leer = jede auffällige Aktie bestätigt)."""
    out = []
    missing = [a["aktie"] for a in report["aktien"] if a["dritte_quelle"] != "ok"]
    if missing:
        out.append(f"{len(missing)} von {len(report['aktien'])} auffälligen Aktien ohne dritte Quelle ({', '.join(missing)})")
    contra = report["dritte_quelle"].get("widerspricht", 0)
    if contra:
        out.append(f"{contra} Kurse der Referenz von CNBC nicht bestätigt (Abweichung über der Toleranz)")
    gaps = sum(v for k, v in report["dritte_quelle"].items() if k in ("dritte_quelle_ohne_tag", "ohne_referenzkurs"))
    if gaps:
        out.append(f"{gaps} Kurse ohne Gegenstück am selben Tag (CNBC oder Stand ohne Kurs)")
    return out


if __name__ == "__main__":
    raise SystemExit(main())
