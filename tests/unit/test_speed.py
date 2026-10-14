"""Beschleunigung des Aktualisierens (ab 1.10): gleiche Ergebnisse, nur schneller.

* ``dumps`` kodiert direkt und fällt nur bei nicht endlichen Zahlen oder NumPy-Schlüsseln auf den
  bisherigen Weg zurück – das Ergebnis ist Zeichen für Zeichen dasselbe wie vorher.
* ``crypto.pack`` mit niedrigerer gzip-Stufe bleibt lesbar (``unpack``) und verschlüsselt.
* ``atomic_write_bytes(durable=False)`` schreibt dieselben Bytes.
"""

from __future__ import annotations

import json
import math
import tempfile
import unittest
from pathlib import Path

import numpy as np

from traktien.util import crypto
from traktien.util.jsonio import _clean, atomic_write_bytes, dumps


def _old_dumps(value, pretty=False):
    cleaned = _clean(value)
    if pretty:
        return json.dumps(cleaned, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=False)
    return json.dumps(cleaned, ensure_ascii=False, allow_nan=False, separators=(",", ":"))


class FastDumpsTests(unittest.TestCase):
    def test_same_text_as_before_for_typical_payloads(self):
        rng = np.random.default_rng(7)
        payloads = [
            {"schema": "tr-window/1", "h": 30, "m": {"idx": list(range(50)), "r": [round(float(x), 6) for x in rng.normal(0, 0.1, 50)], "n": rng.integers(0, 30, 50).tolist()}},
            {"a": np.int64(5), "b": np.float64(1.25), "c": np.bool_(True), "d": np.array([1.5, 2.5]), "e": (1, 2), "f": None, "g": "Ä–ü"},
            {"zahlen": np.arange(5, dtype=np.int32), "f32": np.float32(0.5), "liste": [np.int16(3), np.float64(-0.0)]},
            [1, 2.0, "x", {"k": [True, False, None]}],
        ]
        for value in payloads:
            for pretty in (False, True):
                self.assertEqual(dumps(value, pretty=pretty), _old_dumps(value, pretty=pretty))

    def test_non_finite_numbers_still_become_null(self):
        value = {"r": [1.0, float("nan"), float("inf"), np.float64("nan"), -math.inf], "x": np.array([np.nan, 2.0])}
        self.assertEqual(dumps(value), '{"r":[1.0,null,null,null,null],"x":[null,2.0]}')
        self.assertEqual(dumps(value), _old_dumps(value))

    def test_numpy_keys_and_int_keys(self):
        value = {np.int64(3): "a", 4: "b"}
        self.assertEqual(dumps(value), _old_dumps(value))
        self.assertEqual(json.loads(dumps(value)), {"3": "a", "4": "b"})


class PackTests(unittest.TestCase):
    def test_lower_gzip_level_round_trips_with_and_without_key(self):
        plain = json.dumps({"x": list(range(5000))}).encode()
        key = crypto.derive_key("Testpassphrase-nur-fuer-Tests", b"0123456789abcdef", iterations=1000)
        for k in (None, key):
            for level in (1, 3, 5, 9):
                blob = crypto.pack(plain, k, "snapshots/x/a.bin", level=level)
                self.assertEqual(crypto.unpack(blob, k, "snapshots/x/a.bin"), plain)

    def test_atomic_write_without_fsync_writes_the_same_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "a" / "b.bin"
            atomic_write_bytes(target, b"abc", durable=False)
            self.assertEqual(target.read_bytes(), b"abc")
            atomic_write_bytes(target, b"neu")
            self.assertEqual(target.read_bytes(), b"neu")
            self.assertEqual(sorted(p.name for p in target.parent.iterdir()), ["b.bin"])


if __name__ == "__main__":
    unittest.main()


class ParallelComputeTests(unittest.TestCase):
    """Ab 1.10: Kennzahlen in mehreren Prozessen – Zahl für Zahl dasselbe Ergebnis wie in einer Schleife."""

    def test_parallel_blocks_give_identical_snapshot(self):
        import datetime as dt

        from tests.helpers import day, make_instrument, test_isin, weekday_sessions
        from traktien.analytics.engine import InstrumentData, compute_snapshot
        from traktien.analytics.codes import Status
        from traktien.config import MethodConfig

        cfg = MethodConfig()
        sessions = weekday_sessions(dt.date(2026, 3, 2), dt.date(2026, 10, 12))
        cutoff = day(2026, 10, 12)
        rng = np.random.default_rng(3)
        instruments = []
        for k in range(1, 41):
            drift, vol = rng.normal(0.001, 0.002), abs(rng.normal(0.02, 0.01)) + 0.002
            path = 20 * np.exp(np.cumsum(rng.normal(drift, vol, len(sessions))))
            instruments.append(make_instrument(test_isin(k), sessions, lambda j, p=path: float(p[j]), volume=1000 + 10 * k))
        instruments.append(InstrumentData(isin=test_isin(41), pre_status=int(Status.IDENTITAET_UNKLAR)))
        instruments.append(InstrumentData(isin=test_isin(42), sessions=sessions))
        instruments.sort(key=lambda x: x.isin)
        one = compute_snapshot(instruments, cutoff, cfg, workers=1)
        many = compute_snapshot(instruments, cutoff, cfg, workers=2)
        self.assertEqual(one.input_hash, many.input_hash)
        for name in ("status", "previous_status", "start_day", "n_obs", "n_exp", "r", "p0", "p1", "m", "r2", "slope_pct", "noise_pct", "mdd", "vol_cov", "wflags", "ups", "pre_status", "warnings", "has_history", "liquid"):
            np.testing.assert_array_equal(getattr(one, name), getattr(many, name), err_msg=name)
        self.assertEqual(sorted(one.observed), sorted(many.observed))
        self.assertEqual([t.fingerprint() for t in one.turnover], [t.fingerprint() for t in many.turnover])
        for h in one.windows:
            np.testing.assert_array_equal(one.rankings[h].native0.order, many.rankings[h].native0.order)
            for w in one.rankings[h].trend:
                np.testing.assert_array_equal(one.rankings[h].trend[w].order, many.rankings[h].trend[w].order)
