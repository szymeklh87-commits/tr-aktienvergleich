"""Gestaffelte Aktualisierung: Reihenfolge der Aktien für Stufe 1 aus dem letzten Datenstand (SYNTHETISCH)."""

from __future__ import annotations

import io
import json
import tarfile
import unittest

from traktien.jobs.priority import priority_counts, priority_isins
from traktien.util import crypto

SID = "2026-10-13_abcdef12"


def archive(windows: dict[int, dict], isins: list[str], key=None) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w", format=tarfile.PAX_FORMAT) as tar:
        def add(relative: str, payload: dict) -> None:
            blob = crypto.pack(json.dumps(payload).encode(), key, f"snapshots/{SID}/{relative}")
            info = tarfile.TarInfo(f"{SID}/{relative}")
            info.size = len(blob)
            tar.addfile(info, io.BytesIO(blob))

        add("instruments.bin", {"schema": "tr-instruments/1", "isin": isins})
        for h, orders in windows.items():
            add(f"windows/{h}.bin", {"schema": "tr-window/1", "h": h, "orders": orders})
    return buffer.getvalue()


ISINS = [f"ZZ000000000{k}" for k in range(8)]


def orders(v0, u=None, v0l=None, ul=None):
    return {"v0": v0, "u": u or {}, "v0l": v0l or [], "ul": ul or {}}


class PriorityTests(unittest.TestCase):
    def test_recurring_leaders_of_the_standard_selection_come_first(self):
        # Aktie 3 führt in 40/60–60/40 (1–30 Tage) in A und B; Aktie 0 nur in der reinen Rendite; Aktie 7 nur nach 30 Tagen
        windows = {}
        for h in range(1, 31):
            mixed = {"0": [6, 5], "40": [3, 1, 2], "50": [3, 2, 1], "60": [3, 1, 4]}
            windows[h] = orders([0, 4, 5], mixed, [0, 3], {"40": [3, 2], "50": [3], "60": [1, 3]})
        windows[60] = orders([7], {"40": [7], "50": [7], "60": [7]})
        ranked = priority_isins(archive(windows, ISINS), SID, None)
        self.assertEqual(ranked[0], ISINS[3], "häufigster Spitzenreiter der Standardauswahl zuerst")
        self.assertLess(ranked.index(ISINS[1]), ranked.index(ISINS[0]), "Top-10 in der Standardauswahl vor reiner Rendite")
        self.assertIn(ISINS[7], ranked, "Spitzenreiter langer Zeiträume sind dabei")
        self.assertNotIn(ISINS[6], ranked[:3], "u[0] zählt nicht (0/100 ist die reine Renditeliste v0)")

    def test_counts_and_limits(self):
        windows = {h: orders([0, 1, 2, 3, 4, 5, 6, 7], {"50": [7, 6, 5, 4, 3, 2, 1, 0]}) for h in range(1, 31)}
        counts = {c.isin: c for c in priority_counts(archive(windows, ISINS), SID, None, top_n=5)}
        self.assertEqual(counts[ISINS[0]].n1, 30)
        self.assertEqual(counts[ISINS[7]].std_n1, 30)
        self.assertEqual(counts[ISINS[7]].std_n10, 30)
        self.assertNotIn(ISINS[5], [c for c, v in counts.items() if v.n_top == 0])
        self.assertEqual(len(priority_isins(archive(windows, ISINS), SID, None, limit=3)), 3)

    def test_encrypted_archive_and_missing_files(self):
        key = crypto.derive_key("Testpassphrase-nur-fuer-Tests", b"0123456789abcdef", iterations=1000)
        windows = {30: orders([2], {"50": [2]})}
        self.assertEqual(priority_isins(archive(windows, ISINS, key), SID, key)[0], ISINS[2])
        self.assertEqual(priority_isins(archive({}, ISINS), SID, None), [])


if __name__ == "__main__":
    unittest.main()
