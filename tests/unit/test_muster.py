"""Musterbereiche (Abschnitt 26): Screening A, B, C auf synthetischen Tageskerzen – Zustände, Rückfall, Ablauf, Volumensprung,
nicht prüfbare Aktien, kein Blick in die Zukunft, Skaleninvarianz, Journal und Nachrechnung."""

from __future__ import annotations

import dataclasses
import datetime as dt
import types
import unittest

import numpy as np

from traktien.aktienpilot import muster as mu
from traktien.util.timeutil import date_to_day

CFG = mu.load_muster_config()


def werktage(n: int, start: dt.date = dt.date(2026, 1, 5)) -> np.ndarray:
    out, d = [], start
    while len(out) < n:
        if d.weekday() < 5:
            out.append(date_to_day(d))
        d += dt.timedelta(days=1)
    return np.array(out, dtype=np.int64)


def reihe(close, volume=None, spanne=0.004, days=None):
    close = np.asarray(close, dtype=np.float64)
    n = len(close)
    vol = np.full(n, 1000.0) if volume is None else np.asarray(volume, dtype=np.float64)
    return types.SimpleNamespace(days=werktage(n) if days is None else days, close=close, high=close * (1 + spanne), low=close * (1 - spanne), volume=vol)


def flach(n: int, seed: int = 1, level: float = 100.0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return level * (1 + rng.uniform(-0.01, 0.01, n))


def basis(n: int = 60) -> list[float]:
    """Seitwärtsbasis 97–103 (±3 %), ohne Trend."""
    return list(100 + 3 * np.sin(0.7 * np.arange(n)))


def widerstand(close: list[float], B: int) -> float:
    return max(c * 1.004 for c in close[-B:])


def zustand(s, modul: str) -> list[str]:
    z = mu.zustaende(mu.merkmale(s, CFG), CFG, modul)
    return [mu.CODES[int(c)] for c in z]


class ZustandTests(unittest.TestCase):
    def test_base_candidate_confirmed_breakout_and_fall_back(self) -> None:
        close = basis()
        oben = widerstand(close, 20)
        close += [oben * 0.97, oben * 0.985, oben * 1.02, oben * 0.98]
        vol = [1000.0] * 62 + [2000.0, 1000.0]
        z_a = zustand(reihe(close, vol), "A")
        z_c = zustand(reihe(close, vol), "C")
        self.assertIn(z_a[60], ("", "abgelaufen"))  # Mitte der Basis: kein Kandidat (frühere Annäherungen ohne Übergang sind abgelaufen)
        self.assertEqual(z_a[61], "kandidat")  # oberes Viertel, 1,5 % unter dem Widerstand, positive Reaktion
        self.assertEqual(z_a[62], "bestaetigt")  # 2 % darüber, Volumen 2× ≥ 1,5×
        self.assertEqual(z_a[63], "ungueltig")  # zurück unter dem damaligen Widerstand
        self.assertEqual(z_c[61], "naehert")
        self.assertEqual(z_c[62], "bestaetigt")
        self.assertEqual(z_c[63], "zurueck")
        self.assertEqual(z_c[60], "basis")

    def test_breakout_without_volume_stays_provisional(self) -> None:
        close = basis()
        oben = widerstand(close, 40)
        close += [oben * 0.985, oben * 1.03]
        self.assertEqual(zustand(reihe(close), "C")[-1], "vorlaeufig")  # Volumen nur 1×
        s = reihe(close)
        s.volume = np.full(len(close), np.nan)
        mm = mu.merkmale(s, CFG)
        self.assertEqual(mu.CODES[int(mu.zustaende(mm, CFG, "A")[-1])], "vorlaeufig")  # ohne Volumen keine Bestätigung

    def test_candidate_expires_after_deadline_without_breakout(self) -> None:
        close = basis()
        oben = widerstand(close, 20)
        close += [oben * 0.97, oben * 0.99, oben * 0.988] + [oben * 0.989, oben * 0.99] * ((CFG.a.ablauf_sitzungen + 2) // 2)
        z = zustand(reihe(close), "A")
        self.assertEqual(z[61], "kandidat")
        self.assertEqual(z[62], "kandidat")  # ein schwächerer Tag beendet den Kandidaten nicht
        ende = next(k for k in range(61, len(z)) if z[k] != "kandidat")
        self.assertEqual(z[ende], "abgelaufen")  # ohne Übergang: Frist überschritten oder Basis aufgelöst
        self.assertLessEqual(ende - 61, CFG.a.ablauf_sitzungen)
        self.assertNotIn("bestaetigt", z[61:ende])

    def test_wide_or_trending_range_is_no_base(self) -> None:
        trend = 100 * np.cumprod(np.full(80, 1.004))  # +0,4 % je Sitzung: Drift über 20 Sitzungen ≈ 8 %
        self.assertTrue(all(s in ("", "abgelaufen") for s in zustand(reihe(trend), "A")[30:]))
        wild = flach(80, level=100) * (1 + 0.08 * np.sin(np.arange(80)))
        self.assertEqual(set(zustand(reihe(wild), "C")), {""})

    def test_volume_jump_needs_positive_reaction(self) -> None:
        close = list(flach(40))
        up = reihe(close + [close[-1] * 1.03], [1000.0] * 40 + [3500.0])
        down = reihe(close + [close[-1] * 0.97], [1000.0] * 40 + [3500.0])
        self.assertEqual(zustand(up, "B")[-1], "sprung")
        self.assertEqual(zustand(down, "B")[-1], "")  # Volumenschock bei fallendem Kurs ist kein positiver Ausbruch
        mm = mu.merkmale(up, CFG)
        self.assertAlmostEqual(float(mm.volfaktor[-1]), 3.5)

    def test_no_look_ahead_states_equal_on_truncated_history(self) -> None:
        rng = np.random.default_rng(7)
        close = 50 * np.cumprod(1 + rng.normal(0, 0.012, 160))
        vol = rng.uniform(500, 3000, 160)
        full = {m: zustand(reihe(close, vol), m) for m in mu.MODULE}
        for k in range(45, 160, 7):
            part = reihe(close[: k + 1], vol[: k + 1], days=werktage(160)[: k + 1])
            for m in mu.MODULE:
                self.assertEqual(zustand(part, m)[k], full[m][k], f"{m} am Index {k}")

    def test_price_level_does_not_change_patterns(self) -> None:
        rng = np.random.default_rng(3)
        close = 20 * np.cumprod(1 + rng.normal(0, 0.01, 140))
        vol = rng.uniform(800, 2500, 140)
        for m in mu.MODULE:
            self.assertEqual(zustand(reihe(close, vol), m), zustand(reihe(close * 137.0, vol), m))


class LaufTests(unittest.TestCase):
    def _stand(self, reihen, D, **kw):
        return mu.bauen(reihen, cfg=CFG, D=D, snapshot_id="s", modus="DEMO", erstellt_utc="2026-10-31T20:00:00Z", **kw)

    def test_hits_top_list_and_not_checkable_reasons(self) -> None:
        close = basis()
        oben = widerstand(close, 40)
        hit = reihe(close + [oben * 0.985, oben * 1.02], [1000.0] * 61 + [2000.0])
        days = hit.days
        D = int(days[-1])
        kurz = reihe(flach(20), days=days[-20:])
        alt = reihe(flach(70), days=werktage(70, dt.date(2025, 6, 2)))  # endet Monate vor D
        luecke_days = np.concatenate([days[:30], days[30:62] + 0])
        luecke_days[45:] += 60  # 60 Kalendertage Lücke mitten in der Basis (letzte 40 Sitzungen)
        luecke = reihe(flach(62), days=np.sort(luecke_days))
        luecke.days = luecke.days - (luecke.days[-1] - D)
        payload, neue = self._stand({"AA0000000001": hit, "AA0000000002": kurz, "AA0000000003": alt, "AA0000000004": luecke}, D,
                                    universum=["AA0000000001", "AA0000000002", "AA0000000003", "AA0000000004", "AA0000000005"])
        a = payload["module"]["A"]
        self.assertEqual(a["top"], ["AA0000000001"])
        self.assertEqual(a["treffer"][0]["zustand"], "bestaetigt")
        self.assertGreater(a["treffer"][0]["score"], 0)
        self.assertEqual(a["nicht_pruefbar"]["zu_kurz"], ["AA0000000002"])
        self.assertEqual(a["nicht_pruefbar"]["datenalter"], ["AA0000000003", "AA0000000005"])
        self.assertIn("AA0000000004", payload["module"]["C"]["nicht_pruefbar"].get("luecke", []))
        self.assertEqual(payload["module"]["B"]["intraday"]["status"], "nicht prüfbar")
        self.assertEqual(payload["universum"], 5)
        self.assertTrue(all(e["id"].startswith("m-") for e in neue))

    def test_journal_is_append_only_and_ids_are_stable(self) -> None:
        close = basis()
        oben = widerstand(close, 20)
        s = reihe(close + [oben * 0.97, oben * 0.985, oben * 1.02, oben * 0.98], [1000.0] * 62 + [2000.0, 1000.0])
        D = int(s.days[-1])
        _p, neue = self._stand({"AA0000000001": s}, D)
        a = [e for e in neue if e["modul"] == "A"]
        self.assertEqual([e["zustand"] for e in a][-3:], ["kandidat", "bestaetigt", "ungueltig"])
        self.assertEqual(len({e["id"] for e in a[-3:]}), 1, "eine Instanz von Kandidat bis ungültig")
        _p, wieder = self._stand({"AA0000000001": s}, D, journal_vorher=neue)
        self.assertEqual(wieder, [], "bekannte Ereignisse werden nicht erneut angelegt")
        # Kennung hängt nur von Modul, ISIN und erstem Tag ab – ein späterer Lauf findet dieselbe
        _p, spaeter = self._stand({"AA0000000001": reihe(list(s.close) + [oben * 0.97], list(s.volume) + [1000.0], days=werktage(65))}, int(werktage(65)[-1]))
        self.assertIn(a[-1]["id"], {e["id"] for e in spaeter})

    def test_evaluation_counts_only_completed_horizons(self) -> None:
        close = basis()
        oben = widerstand(close, 40)
        after = [oben * 1.02 * (1.01 ** i) for i in range(1, 26)]
        s = reihe(close + [oben * 0.985, oben * 1.02] + after, [1000.0] * 61 + [2000.0] + [1000.0] * 25)
        ref = reihe(flach(len(s.close), seed=9), days=s.days)
        payload, _ = self._stand({"AA0000000001": s, "AA0000000002": ref}, int(s.days[-1]))
        h = payload["auswertung"]["C"]["horizonte"]
        self.assertEqual(h["5"]["n"], 1)
        self.assertAlmostEqual(h["5"]["mittel_pct"], round(100 * (1.01 ** 5 - 1), 2))
        self.assertEqual(h["20"]["n"], 1)
        self.assertIsNotNone(h["20"]["vergleich_mittel_pct"])
        self.assertIn("Keine Gewinnwahrscheinlichkeit", payload["auswertung"]["hinweis"])


class SpeicherTests(unittest.TestCase):
    def test_run_appends_journal_once_and_stores_a_readable_stand(self) -> None:
        import json
        import tempfile
        from pathlib import Path

        from traktien.store import db
        from traktien.util import crypto

        close = basis()
        oben = widerstand(close, 20)
        s = reihe(close + [oben * 0.97, oben * 0.985, oben * 1.02], [1000.0] * 62 + [2000.0])
        D = int(s.days[-1])
        with tempfile.TemporaryDirectory() as tmp:
            conn = db.connect(Path(tmp) / "z.sqlite")
            now = dt.datetime(2026, 10, 31, 20, 0, tzinfo=dt.timezone.utc)
            first = mu.lauf(conn, {"AA0000000001": s}, cfg=CFG, D=D, snapshot_id="s-1", modus="DEMO", now=now, key=None, universum=["AA0000000001"])
            self.assertGreater(first["neue_ereignisse"], 0)
            second = mu.lauf(conn, {"AA0000000001": s}, cfg=CFG, D=D, snapshot_id="s-1", modus="DEMO", now=now + dt.timedelta(minutes=5), key=None, universum=["AA0000000001"])
            self.assertEqual(second["neue_ereignisse"], 0, "jede Zustandsänderung genau einmal im Journal")
            n = conn.execute("SELECT COUNT(*) FROM muster_ereignis").fetchone()[0]
            self.assertEqual(n, first["neue_ereignisse"])
            sid, _created, blob = mu.neuester(conn)
            payload = json.loads(crypto.unpack(blob, None, f"muster/{sid}/muster.bin"))
            self.assertEqual((payload["id"], payload["schema"]), (sid, mu.SCHEMA))
            self.assertEqual(payload["module"]["A"]["treffer"][0]["zustand"], "bestaetigt")
            self.assertTrue(payload["journal"] and all(set(e) == {"id", "modul", "isin", "zustand", "datum"} for e in payload["journal"]))
            # öffentliche Zusammenfassung nur mit Zahlen
            self.assertNotIn("AA0000000001", json.dumps(second))
            conn.close()

    def test_catalog_value_is_unknown_when_not_checkable_and_keiner_without_pattern(self) -> None:
        kurz = reihe(flach(20))
        self.assertEqual(mu.am_tag(kurz, 19, CFG)["A"], (None, None))
        ruhig = reihe(basis(70))
        z, v = mu.am_tag(ruhig, 69, CFG)["C"]
        self.assertIn(z, ("keiner", "basis", "naehert"))
        self.assertIsNotNone(v)
        alt = reihe(basis(70))
        self.assertEqual(mu.am_tag(alt, 69, CFG, tag=int(alt.days[-1]) + 30)["A"], (None, None), "Datenalter: nicht prüfbar")


class ConfigTests(unittest.TestCase):
    def test_parameters_only_in_yaml_and_checked(self) -> None:
        self.assertEqual(CFG.version, "muster-1")
        self.assertEqual((CFG.a.basis_sitzungen, CFG.c.basis_sitzungen), (20, 40))
        raw = {"version": "x"}
        with self.assertRaises(mu.MusterFehler):
            mu.parse_config(raw)
        bad = dataclasses.replace(CFG.a, basis_sitzungen=5)
        with self.assertRaises(mu.MusterFehler):
            mu._regel(dict(bad.__dict__), "vor_ausbruch")


if __name__ == "__main__":
    unittest.main()
