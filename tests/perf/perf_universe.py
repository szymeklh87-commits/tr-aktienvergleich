"""Leistungsmessung mit realistischer Universumsgröße (SYNTHETISCH, keine echten Kurse).

Aufruf:  PYTHONPATH=backend python3 tests/perf/perf_universe.py [Anzahl] [--encrypt]
Misst Laufzeit und Speicher von Rechenkern und Veröffentlichung sowie Dateigrößen.
"""
from __future__ import annotations

import datetime as dt
import json
import resource
import shutil
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

from traktien.analytics.engine import InstrumentData, compute_snapshot
from traktien.analytics.fx import FxRates
from traktien.config import MethodConfig
from traktien.providers.demo import DemoFxSource, demo_calendars
from traktien.publish.snapshot_writer import InstrumentMeta, SnapshotWriter
from traktien.util import crypto
from traktien.util.isin import make_isin
from traktien.util.timeutil import date_to_day


def main() -> None:
    count = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 11500
    encrypt = "--encrypt" in sys.argv
    cfg = MethodConfig()
    calendars = demo_calendars()
    codes = ["XNYS", "XETR", "XLON", "XHKG", "XASX", "XTKS"]
    # Notierungswährung und Einheit je Börse (London in Pence) – für den Ø Tagesumsatz in USD
    currency = {"XNYS": ("USD", 1.0), "XETR": ("EUR", 1.0), "XLON": ("GBP", 0.01), "XHKG": ("HKD", 1.0), "XASX": ("AUD", 1.0), "XTKS": ("JPY", 1.0)}
    fetched = DemoFxSource().fetch()
    fx = FxRates.from_rows(fetched.rows, source=fetched.source, url=None, fetched_at=fetched.fetched_at, max_age_days=cfg.fx_max_age_days)
    cutoff = date_to_day(dt.date(2026, 10, 9))
    start = cutoff - 210
    rng = np.random.default_rng(42)
    instruments, metas = [], []
    for k in range(count):
        code = codes[k % len(codes)]
        sessions = calendars.sessions(code, start, cutoff)
        n = len(sessions)
        drift = rng.normal(0.0005, 0.002)
        vol = abs(rng.normal(0.02, 0.01)) + 0.002
        close = float(10 ** rng.uniform(-1, 3)) * np.exp(np.cumsum(rng.normal(drift, vol, n)))
        volume = rng.integers(0, 500000, n).astype(float)
        keep = rng.random(n) > 0.003
        isin = make_isin(f"ZZ{k:09d}")
        cur, unit = currency[code]
        instruments.append(
            InstrumentData(isin=isin, sessions=sessions, days=sessions[keep], close=close[keep], volume=volume[keep], currency=cur, unit_factor=unit)
        )
        metas.append(InstrumentMeta(isin=isin, name=f"SYNTH Test {k}", tr_name=f"SYNTH Test {k}", sessions=sessions, calendar=code))
    t0 = time.perf_counter()
    comp = compute_snapshot(instruments, cutoff, cfg, fx=fx)
    t1 = time.perf_counter()
    key = crypto.derive_key("perf-test", b"0123456789abcdef", 1000) if encrypt else None
    out = Path(tempfile.mkdtemp())
    writer = SnapshotWriter(comp, metas, cfg, snapshot_id="perf", key=key)
    writer.write(out, {"data_mode": "demo"})
    t2 = time.perf_counter()
    files = list((out / "perf").rglob("*.bin"))
    sizes = {
        "windows_mb": sum(f.stat().st_size for f in (out / "perf" / "windows").glob("*.bin")) / 1e6,
        "series_mb": sum(f.stat().st_size for f in (out / "perf" / "series").glob("*.bin")) / 1e6,
        "other_mb": sum(f.stat().st_size for f in (out / "perf").glob("*.bin")) / 1e6,
    }
    report = {
        "instrumente": count,
        "fenster": 90,
        "instrument_fenster": count * 90,
        "rechenkern_s": round(t1 - t0, 1),
        "veroeffentlichung_s": round(t2 - t1, 1),
        "dateien": len(files),
        "groessen_mb": {k: round(v, 1) for k, v in sizes.items()},
        "gesamt_mb": round(sum(sizes.values()), 1),
        "max_rss_mb": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 0),
        "V_h30": int(comp.rankings[30].native0.size),
        "U_h30": int(len(comp.rankings[30].u_idx)),
        "L_h30": int(comp.rankings[30].native0_liquid.size),
        "umsatz_bestimmt": int(sum(1 for t in comp.turnover if t.determined)),
        "umsatz_ab_schwelle": int(comp.liquid.sum()),
        "verschluesselt": encrypt,
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))
    shutil.rmtree(out)


if __name__ == "__main__":
    main()
