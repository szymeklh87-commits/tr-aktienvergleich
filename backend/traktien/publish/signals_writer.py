"""Schreibt einen Signal-Stand (ab 1.6) als verschlüsselte statische Dateien.

Verzeichnis ``signale/<id>/``:

* ``signale.bin``         Spalten je Aktie: Gesamtwertung mit Teilen und Steig-Konstanz (ab signale-v2),
                          Punkte je Signal, Urteile (Ampeln) kurz- und langfristig, erwartete Steigerung,
                          Kursziel-Spanne, Merkmale für die Listen, Regeln, Erklärungen, Trefferquoten
                          (Kalibrierung) und vorsortierte Kandidaten.
* ``details/<ISIN>.bin``  Einzelansicht: Gesamtwertung, alle Signale mit Text, Kursziel-Quellen, Kennzahlen,
                          Analystenurteile, Nachrichten, Community, Prognose-Spanne.

Jede Datei ist ein TRA1-Container (gzip, optional AES-GCM; AAD = ``signale/<id>/<Datei>``).
"""

from __future__ import annotations

import math
import shutil
from pathlib import Path

import numpy as np

from ..analytics import signals as sg
from ..util import crypto
from ..util.jsonio import atomic_write_bytes, dumps, sha256_hex
from ..util.timeutil import day_to_iso, iso_utc
from .snapshot_writer import snapshot_tar

SCHEMA = "tr-signale/1"
DETAIL_SCHEMA = "tr-signal-detail/1"
COMPONENT_KEYS = list(sg.SHORT_WEIGHTS) + ["nachrichten", "community"] + list(sg.LONG_WEIGHTS)
CONSISTENCY_KEYS = tuple(f"{prefix}_{period}" for period in sg.CONSISTENCY_PERIODS for prefix in ("steig", "tage"))
FEATURE_KEYS = ("r1", "r5", "r20", "r60", "r250", "rvol", "up10", "serie", "rsi", "atr", "gap", "umsatz_eur") + CONSISTENCY_KEYS + tuple(
    f"r_{period}k" for period in sg.CONSISTENCY_PERIODS
)
INT_FEATURES = frozenset(("serie",) + CONSISTENCY_KEYS)
LIGHT_ORDER = {"gruen": 0, "gelb": 1, "grau": 2, "rot": 3}


def _r(x, digits: int = 4):
    if x is None:
        return None
    try:
        value = float(x)
    except (TypeError, ValueError):
        return None
    return round(value, digits) if math.isfinite(value) else None


def _sig(x, digits: int = 6):
    value = _r(x, 12)
    return None if value is None else float(f"{value:.{digits}g}")


def market_cap_eur(item: sg.StockInput) -> float | None:
    """Börsenwert in EUR (ab 1.11): Yahoo „marketCap“ steht in der Hauptwährung der Notierung – auch wenn der
    Kurs in Pence, Cent oder Agorot notiert –, umgerechnet mit dem EZB-Kurs des Kursstichtags. Ohne Angabe None."""
    cap = ((item.facts or {}).get("bewertung") or {}).get("boersenwert")
    try:
        cap = float(cap)
    except (TypeError, ValueError):
        return None
    rate = item.unit_to_eur
    if not (math.isfinite(cap) and cap > 0) or rate is None or not math.isfinite(rate) or rate <= 0:
        return None
    factor = item.unit_factor if item.unit_factor and math.isfinite(item.unit_factor) and item.unit_factor > 0 else 1.0
    return cap * rate / factor


class SignalsWriter:
    def __init__(self, batch: sg.SignalBatch, inputs: list[sg.StockInput], meta: dict[str, dict], *, stand_id: str, snapshot_id: str, cutoff_day: int,
                 key: crypto.KeyMaterial | None, now) -> None:
        self.batch = batch
        self.inputs = {item.isin: item for item in inputs}
        self.meta = meta
        self.stand_id = stand_id
        self.snapshot_id = snapshot_id
        self.cutoff_day = cutoff_day
        self.key = key
        self.now = now
        self.hashes: dict[str, str] = {}

    def _write(self, root: Path, relative: str, value) -> None:
        plain = dumps(value).encode("utf-8")
        blob = crypto.pack(plain, self.key, f"signale/{self.stand_id}/{relative}")
        atomic_write_bytes(root / relative, blob, durable=False)
        self.hashes[relative] = sha256_hex(plain)

    # ------------------------------------------------------------ Inhalte

    def rankings(self) -> dict[str, list[int]]:
        results = self.batch.results

        def both_key(k: int):
            r = results[k]
            both = r.short_light == "gruen" and r.long_light == "gruen"
            mean = np.nanmean([x for x in (r.short, r.long) if x is not None]) if (r.short is not None or r.long is not None) else -1
            return (0 if both else 1, -float(mean))

        idx = list(range(len(results)))
        beide = [k for k in sorted(idx, key=both_key) if results[k].short is not None and results[k].long is not None][:100]
        kurz = sorted((k for k in idx if results[k].short is not None and results[k].tradable), key=lambda k: (LIGHT_ORDER[results[k].short_light], -(results[k].short or 0)))[:100]
        lang = sorted(
            (k for k in idx if results[k].long is not None),
            key=lambda k: (LIGHT_ORDER[results[k].long_light], -(results[k].long or 0), -(results[k].upside or -9)),
        )[:100]
        potenzial = sorted((k for k in idx if results[k].upside is not None and results[k].analysts >= 3), key=lambda k: -(results[k].upside or 0))[:100]
        gesamt = sorted((k for k in idx if results[k].total is not None), key=lambda k: (-(results[k].total or 0), -(results[k].upside or -9)))[:150]
        return {"gesamt": gesamt, "beide": beide, "kurz": kurz, "lang": lang, "potenzial": potenzial}

    def main_payload(self) -> dict:
        results = self.batch.results
        sectors: list[str] = []
        sector_idx: list[int] = []
        for r in results:
            facts = self.inputs[r.isin].facts or {}
            sector = (facts.get("branche") or {}).get("sektor")
            if sector and sector not in sectors:
                sectors.append(sector)
            sector_idx.append(sectors.index(sector) if sector else -1)
        points = {key: [] for key in COMPONENT_KEYS}
        for r in results:
            by_key = {c.key: c.points for c in r.components}
            for key in COMPONENT_KEYS:
                value = by_key.get(key)
                points[key].append(None if value is None else int(round(value)))
        features = {key: [] for key in FEATURE_KEYS}
        for r in results:
            for key in FEATURE_KEYS:
                value = r.features.get(key)
                features[key].append(int(value) if key in INT_FEATURES and value is not None else _sig(value, 5) if key == "umsatz_eur" else _r(value, 4))
        cal = self.batch.calibration
        cal_total = self.batch.consistency_calibration
        counts = {
            "aktien": len(results),
            "mit_kennzahlen": sum(1 for r in results if self.inputs[r.isin].facts),
            "mit_kursziel": sum(1 for r in results if r.upside is not None),
            "beide_gruen": sum(1 for r in results if r.both_green),
            "kurz": {light: sum(1 for r in results if r.short_light == light) for light in LIGHT_ORDER},
            "lang": {light: sum(1 for r in results if r.long_light == light) for light in LIGHT_ORDER},
            "gesamt": {grade: sum(1 for r in results if r.total_grade == grade) for grade in ("stark", "mittel", "schwach", "ohne")},
        }
        parts = {key: [None if r.total_parts.get(key) is None else int(round(r.total_parts[key])) for r in results] for key in sg.TOTAL_WEIGHTS}
        return {
            "schema": SCHEMA,
            "id": self.stand_id,
            "snapshot_id": self.snapshot_id,
            "cutoff_day": self.cutoff_day,
            "kursstand": day_to_iso(self.cutoff_day),
            "erstellt_utc": iso_utc(self.now),
            "version": sg.VERSION,
            "regeln": {
                "kurz_gewichte": sg.SHORT_WEIGHTS,
                "kurz_nachrichten_gewicht": sg.SHORT_NEWS_WEIGHT,
                "lang_gewichte": sg.LONG_WEIGHTS,
                "mindestumsatz_eur": sg.MIN_TURNOVER_EUR,
                "namen": sg.LABELS,
                "erklaerungen": sg.EXPLAIN,
                "ampel_kurz": "Grün: mindestens 65 Punkte, Kurs über 20- und 50-Tage-Linie (Trendlage ≥ 66) und in 20 Sitzungen gestiegen. Rot: unter 40 Punkten oder fallender Kurs unter den Durchschnittslinien. Grau: zu kurze Kurshistorie oder unter 250.000 € Umsatz am Tag (kurzfristig kaum handelbar). Sonst Gelb.",
                "ampel_lang": "Grün: mindestens 62 Punkte, erwartete Steigerung bis zum Ø Kursziel mindestens +10 %, mindestens 3 Analysten und mindestens die Hälfte „Kaufen“. Ohne Kursziel oder mit weniger als 3 Analysten höchstens Gelb. Rot: Kursziel unter dem Kurs oder unter 40 Punkten. Grau: weniger als zwei langfristige Signale. Sonst Gelb.",
                "hinweis": "Zusammenfassung öffentlich verfügbarer Signale nach festen Regeln – keine Anlageberatung und keine Kaufempfehlung. Kursziele sind Einschätzungen Dritter für etwa 12 Monate und oft zu optimistisch.",
                "gesamt_gewichte": sg.TOTAL_WEIGHTS,
                "gesamt_namen": sg.TOTAL_LABELS,
                "gesamt_erklaerungen": sg.TOTAL_EXPLAIN,
                "gesamt_regel": sg.TOTAL_RULE,
                "gesamt_stark_ab": sg.TOTAL_STRONG,
                "gesamt_mittel_ab": sg.TOTAL_MEDIUM,
                "konstanz_zeitraeume": list(sg.CONSISTENCY_PERIODS),
            },
            "kalibrierung": cal.as_dict(),
            "kalibrierung_konstanz": cal_total.as_dict() if cal_total is not None else None,
            "anzahl": counts,
            "gesamt": [r.total for r in results],
            "gesamt_stufe": [r.total_grade for r in results],
            "gesamt_teile": parts,
            "gesamt_steigt_20": [None if r.total_probability is None else r.total_probability.get("steigt_20") for r in results],
            "gesamt_steigt_60": [None if r.total_probability is None else r.total_probability.get("steigt_60") for r in results],
            "sektoren": sectors,
            "isin": [r.isin for r in results],
            "sektor": sector_idx,
            "kurz": [r.short for r in results],
            "kurz_ampel": [r.short_light for r in results],
            "kurz_grund": [r.short_reason for r in results],
            "lang": [r.long for r in results],
            "lang_ampel": [r.long_light for r in results],
            "lang_grund": [r.long_reason for r in results],
            "potenzial": [r.upside for r in results],
            "ziel": [_sig(r.target, 6) for r in results],
            "ziel_tief": [_sig(r.target_low, 6) for r in results],
            "ziel_hoch": [_sig(r.target_high, 6) for r in results],
            "analysten": [r.analysts for r in results],
            "kaufen": [_r(r.buy_share, 3) for r in results],
            "handelbar": [r.tradable for r in results],
            "kurs": [_sig(r.close, 7) for r in results],
            "kurs_tag": [r.day for r in results],
            "boersenwert_eur": [_sig(market_cap_eur(self.inputs[r.isin]), 4) for r in results],
            "punkte": points,
            "merkmale": features,
            "steigt_5": [None if r.probability is None else r.probability["steigt_5"] for r in results],
            "steigt_20": [None if r.probability is None else r.probability["steigt_20"] for r in results],
            "listen": self.rankings(),
        }

    def detail_payload(self, r: sg.StockSignals) -> dict:
        item = self.inputs[r.isin]
        facts = item.facts or {}
        sigma = r.features.get("schwankung")
        band = None
        if sigma is not None and r.close:
            year = sigma * math.sqrt(252.0)
            quarter = sigma * math.sqrt(63.0)
            band = {
                "schwankung_jahr": _r(year, 4),
                "band_3m": [_sig(r.close * math.exp(-quarter), 6), _sig(r.close * math.exp(quarter), 6)],
                "band_12m": [_sig(r.close * math.exp(-year), 6), _sig(r.close * math.exp(year), 6)],
            }
        return {
            "schema": DETAIL_SCHEMA,
            "id": self.stand_id,
            "isin": r.isin,
            "kursstand": day_to_iso(self.cutoff_day),
            "kurs": _sig(r.close, 7),
            "kurs_tag": r.day,
            "einheit": (self.meta.get(r.isin) or {}).get("einheit"),
            "boersenwert_eur": _sig(market_cap_eur(item), 4),
            "gesamt": r.total,
            "gesamt_stufe": r.total_grade,
            "gesamt_teile": r.total_parts,
            "konstanz": [{k: (_r(v, 4) if isinstance(v, float) else v) for k, v in entry.items()} for entry in r.consistency],
            "wahrscheinlichkeit_gesamt": r.total_probability,
            "kurz": r.short,
            "kurz_technik": r.short_tech,
            "kurz_ampel": r.short_light,
            "kurz_grund": r.short_reason,
            "lang": r.long,
            "lang_ampel": r.long_light,
            "lang_grund": r.long_reason,
            "handelbar": r.tradable,
            "komponenten": [c.as_dict() for c in r.components],
            "merkmale": {k: (_r(v, 5) if not isinstance(v, (dict, list)) else v) for k, v in r.features.items()},
            "potenzial": r.upside,
            "ziel": _sig(r.target, 6),
            "ziel_tief": _sig(r.target_low, 6),
            "ziel_hoch": _sig(r.target_high, 6),
            "ziel_quellen": [{k: (_sig(v, 6) if isinstance(v, float) else v) for k, v in s.items()} for s in r.target_sources],
            "wahrscheinlichkeit": r.probability,
            "prognose": band,
            "kennzahlen": {
                "analysten": facts.get("analysten"),
                "empfehlungen": facts.get("empfehlungen"),
                "urteile": (facts.get("urteile") or [])[:12],
                "urteile_anzahl": facts.get("urteile_anzahl"),
                "bewertung": facts.get("bewertung"),
                "wachstum": facts.get("wachstum"),
                "finanzen": facts.get("finanzen"),
                "risiko": facts.get("risiko"),
                "termine": facts.get("termine"),
                "branche": facts.get("branche"),
                "waehrung_bilanz": facts.get("waehrung_bilanz"),
            } if facts else None,
            "bewertung_tc": item.valuation,
            "nasdaq": item.nasdaq,
            "nachrichten": item.news or [],
            "community": item.community,
            "abgerufen": self.meta.get(r.isin) or {},
            # Kursverlauf für 1W–Max: Tageskurse (bis gut 1 Jahr) und davor Wochenkurse (bis 3 Jahre)
            "verlauf": {"d": [int(d) for d in item.days.tolist()], "c": [_sig(c, 7) for c in item.close.tolist()]},
            "wochen": self._weeks_before(item),
        }

    @staticmethod
    def _weeks_before(item: sg.StockInput) -> dict | None:
        if item.weeks is None or not len(item.days):
            return None
        days, closes = item.weeks
        keep = days < int(item.days[0])
        if not keep.any():
            return None
        return {"d": [int(d) for d in days[keep].tolist()], "c": [_sig(c, 7) for c in closes[keep].tolist()]}

    # ------------------------------------------------------------ Ablauf

    def write(self, state_dir: Path) -> dict:
        state_dir = Path(state_dir)
        out_dir = state_dir / "signale"
        final = out_dir / self.stand_id
        tmp = out_dir / f".tmp-{self.stand_id}"
        if tmp.exists():
            shutil.rmtree(tmp)
        tmp.mkdir(parents=True)
        main = self.main_payload()
        self._write(tmp, "signale.bin", main)
        for r in self.batch.results:
            self._write(tmp, f"details/{r.isin}.bin", self.detail_payload(r))
        if final.exists():
            shutil.rmtree(final)
        tmp.rename(final)
        archive = f"signale-{self.stand_id}.tar"
        atomic_write_bytes(state_dir / "archives" / archive, snapshot_tar(final))
        lists = main["listen"]
        isins = main["isin"]
        # Reihenfolge = Vorrang beim täglichen Erneuern der Kennzahlen und bei den Ergänzungen (Nachrichten, Community)
        candidates = list(dict.fromkeys(
            [isins[k] for k in lists["gesamt"][:150]] + [isins[k] for k in lists["beide"][:100]] + [isins[k] for k in lists["kurz"][:75]] + [isins[k] for k in lists["lang"][:75]]
        ))
        return {
            "id": self.stand_id,
            "erstellt_utc": main["erstellt_utc"],
            "snapshot_id": self.snapshot_id,
            "kursstand": main["kursstand"],
            "aktien": main["anzahl"]["aktien"],
            "mit_kennzahlen": main["anzahl"]["mit_kennzahlen"],
            "mit_kursziel": main["anzahl"]["mit_kursziel"],
            "beide_gruen": main["anzahl"]["beide_gruen"],
            "kurz_gruen": main["anzahl"]["kurz"]["gruen"],
            "lang_gruen": main["anzahl"]["lang"]["gruen"],
            "gesamt_stark": main["anzahl"]["gesamt"]["stark"],
            "gesamt_mittel": main["anzahl"]["gesamt"]["mittel"],
            "kalibrierung_faelle": main["kalibrierung"]["faelle_gesamt"],
            "archiv": archive,
            "version": sg.VERSION,
            "kandidaten": candidates,
        }
