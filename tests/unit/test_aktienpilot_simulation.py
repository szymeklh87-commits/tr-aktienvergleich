"""Historische Simulation (Abschnitte 14, 29.8, 31.6): Nachrechnung je Tag ohne Blick in die Zukunft, nachgerechnetes
Ranglistenarchiv, Tagesumsatz aus derselben Rechnung, Speichern über den Weg des täglichen Laufs, Kennzeichnung und
Chronik im App-Stand. SYNTHETISCHE Daten – keine echten Kurse."""

from __future__ import annotations

import dataclasses
import datetime as dt
import json
import unittest

import numpy as np

from traktien.aktienpilot import backtest, motor, regeln, speicher, stand, tageslauf, vorlagen
from traktien.aktienpilot import katalog as kat
from traktien.analytics.engine import compute_snapshot
from traktien.store import db

from tests.unit import ap_szenario as sz

S = None
K = None
NOW = dt.datetime(2026, 10, 31, 6, 0, tzinfo=dt.timezone.utc)


def setUpModule():
    global S, K
    S = sz.bauen(fuell=12)
    K = kat.katalog(S.method, S.cfg)


def _quelle(fenster: int = 30) -> backtest.Kontextquelle:
    inputs = S.instruments(int(S.sessions[-1]))
    return backtest.Kontextquelle(S.method, S.cfg, S.markt, inputs, S.stamm, fenster, S.markt.fx)


class RegelPruefungTests(unittest.TestCase):
    def test_pruefung_ist_idempotent_fuer_alle_vorlagen(self):
        """Gespeicherte (geprüfte) Regeln müssen beim Laden und im historischen Test erneut gültig sein – unverändert."""
        for name, r in vorlagen.alle(S.cfg).items():
            first = regeln.pruefen(r, K, S.method)
            self.assertTrue(first.gueltig, name)
            second = regeln.pruefen(first.regel, K, S.method)
            self.assertTrue(second.gueltig, f"{name}: {[f.as_dict() for f in second.fehler]}")
            self.assertEqual(first.regel, second.regel, name)
            self.assertEqual(regeln.fingerabdruck(first.regel), regeln.fingerabdruck(second.regel), name)

    def test_score_mit_fremder_normierung_abgelehnt(self):
        r = vorlagen.alle(S.cfg)["s1"]
        p = regeln.pruefen(r, K, S.method).regel
        if "score" not in p["sortierung"]:
            self.skipTest("Vorlage ohne Score")
        bad = json.loads(json.dumps(p))
        bad["sortierung"]["normierung"] = "rohwert"
        self.assertFalse(regeln.pruefen(bad, K, S.method).gueltig)


class NachrechnungTests(unittest.TestCase):
    def test_tag_sieht_keine_spaeteren_kurse(self):
        """Die Rechnung für Tag d hängt nur von Kursen bis d ab: spätere Kurse verändern sie nicht."""
        day = int(S.sessions[-40])
        q1 = _quelle()
        comp1 = q1.comp(day)
        inputs = S.instruments(int(S.sessions[-1]))
        changed = []
        for inst in inputs:
            close = inst.close.copy()
            close[inst.days > day] *= 3.0  # Zukunft stark verändert
            changed.append(dataclasses.replace(inst, close=close))
        q2 = backtest.Kontextquelle(S.method, S.cfg, S.markt, changed, S.stamm, 30, S.markt.fx)
        comp2 = q2.comp(day)
        np.testing.assert_array_equal(comp1.r, comp2.r)
        np.testing.assert_array_equal(comp1.status, comp2.status)
        self.assertEqual(list(comp1.rankings[30].ranking("native", 0).order[:5]), list(comp2.rankings[30].ranking("native", 0).order[:5]))

    def test_gleich_wie_direkte_rechnung(self):
        day = int(S.sessions[-25])
        comp = _quelle().comp(day)
        direct = compute_snapshot(S.instruments(day), day, S.method, S.markt.fx, workers=1)
        np.testing.assert_allclose(comp.r, direct.r, equal_nan=True)
        self.assertEqual(comp.isins, direct.isins)

    def test_umsatz_aus_derselben_rechnung_in_eur(self):
        day = int(S.sessions[-10])
        q = _quelle()
        comp = q.comp(day)
        k = comp.isins.index(sz.isin(6))  # USD-Aktie
        t = comp.turnover[k]
        self.assertTrue(t.determined)
        self.assertAlmostEqual(q.umsatz_eur(sz.isin(6), day), float(t.avg_usd) * S.markt.eur_rate("USD", day), places=6)
        self.assertIsNone(q.umsatz_eur("XX0000000000", day))

    def test_nachgerechnetes_archiv(self):
        q = _quelle()
        days = [int(d) for d in S.sessions[-30:]]
        archiv = backtest.NachgerechnetesArchiv(q, days)
        self.assertEqual(archiv.letzte_tage(days[10], 3), days[8:11])
        self.assertEqual(archiv.letzte_tage(days[0] - 1, 3), [])
        top = archiv.top(days[-1], "A", "native", 30, 0, 3)
        content = tageslauf.rang_archiv_inhalt(q.comp(days[-1]))
        self.assertEqual(top, content[tageslauf.rang_archiv_schluessel("A", "native", 30, 0)][:3])
        # 10/90 … 100/0: im Vergleichsfeld „gemeinsamer Trend“ identisch mit „native“
        self.assertEqual(archiv.top(days[-1], "A", "common_trend", 30, 50, 5), archiv.top(days[-1], "A", "native", 30, 50, 5))

    def test_aelterer_tag_nach_neueren_wird_gerechnet(self):
        """Das Archiv fragt nachträglich ältere Tage an: Der Zwischenspeicher darf den gerade gerechneten Tag nicht verwerfen."""
        q = _quelle()
        days = [int(d) for d in S.sessions[-6:]]
        for d in days[2:]:
            q.comp(d)
        self.assertEqual(q.comp(days[0]).cutoff_day, days[0])
        self.assertLessEqual(len(q._comp), 4)

    def test_lineal_fenster(self):
        templates = [regeln.pruefen(r, K, S.method).regel for r in vorlagen.alle(S.cfg).values()]
        self.assertGreaterEqual(backtest.lineal_fenster(K, templates, S.method), 30)
        plain = {"schema": "tr-regel/1", "id": "r-ohne", "version": 1, "name": "ohne Lineal", "kandidaten": [{"art": "universum"}],
                 "sortierung": {"schluessel": [{"kennzahl": {"id": "rsi", "parameter": {"sitzungen": 14}}}]}, "auswahl": {"anzahl": 2},
                 "stop": {"initial": {"art": "prozent", "wert": 10}}}
        self.assertEqual(backtest.lineal_fenster(K, [regeln.pruefen(plain, K, S.method).regel], S.method), 0)


class LaufenUndSpeichernTests(unittest.TestCase):
    def test_simulation_speichert_wie_taeglicher_lauf_und_stand_kennzeichnet(self):
        conn = db.connect(":memory:")
        db.migrate(conn)
        r = regeln.pruefen(vorlagen.alle(S.cfg)["lineal"], K, S.method).regel
        days = [int(d) for d in S.sessions[-25:]]
        d = motor.DepotDef("h-f-lineal-1", "Lineal (historische Simulation)", "forschung", 10_000.0, days[0], 1.0, (motor.StrategieDef(r["id"], r, 1.0),),
                           None, True, "historische Simulation, kein Vorwärtstest")
        with db.Transaction(conn):
            self.assertEqual(speicher.depot_anlegen(conn, d, modus="DEMO", test_id="historisch-test", jetzt=NOW), "neu")
        q = _quelle(backtest.lineal_fenster(K, [r], S.method))
        saved = []

        def save(dd, z, res):
            if res.verarbeitet:
                with db.Transaction(conn):
                    speicher.speichern(conn, dd, z, res, lauf_id="historisch-test", datenstand="test", jetzt=NOW)
                saved.append(res.tag)

        result = backtest.laufen([d], days, q, cfg=S.cfg, method=S.method, eintraege=K, calendars=S.calendars,
                                 stamm_fn=lambda i: S.stamm.get(i, {}), synthetisch=True, nach_schritt=save)
        self.assertEqual(saved, days)
        self.assertEqual(q.rechnungen, len(days))
        z = result.depots[d.id]
        self.assertGreater(sum(1 for e in z.events if e.typ == "kauf"), 0)
        # Neustart aus dem Zustand ergibt dasselbe Buch
        loaded = speicher.zustand_laden(conn, d.id)
        self.assertEqual([e.id for e in loaded.events], [e.id for e in z.events])
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM ap_tageslauf WHERE depot_id = ?", (d.id,)).fetchone()[0], len(days))
        # Stand: aktive Depots voll, archivierte kompakt in der Chronik, Kennzeichnung „historisch“
        payload = stand.bauen(conn, D=days[-1], snapshot_id="test", modus="DEMO", now=NOW, eintraege=K, method=S.method, cfg=S.cfg, stamm=S.stamm, market=S.markt)
        self.assertEqual([x["id"] for x in payload["depots"]], [d.id])
        self.assertTrue(payload["depots"][0]["historisch"])
        self.assertEqual(payload["chronik"], [])
        again = stand.bauen(conn, D=days[-1], snapshot_id="test", modus="DEMO", now=NOW, eintraege=K, method=S.method, cfg=S.cfg, stamm=S.stamm, market=S.markt)
        self.assertEqual(again["id"], payload["id"])  # gleicher Inhalt = gleiche Kennung
        with db.Transaction(conn):
            speicher.depot_archivieren(conn, d.id, NOW)
        archived = stand.bauen(conn, D=days[-1], snapshot_id="test", modus="DEMO", now=NOW, eintraege=K, method=S.method, cfg=S.cfg, stamm=S.stamm, market=S.markt)
        self.assertEqual(archived["depots"], [])
        self.assertEqual(len(archived["chronik"]), 1)
        entry = archived["chronik"][0]
        self.assertTrue(entry["kompakt"])
        self.assertNotIn("journal", entry)
        self.assertNotIn("positionen", entry)
        self.assertEqual(entry["kennzahlen"]["kaeufe"], sum(1 for e in z.events if e.typ == "kauf"))
        self.assertNotEqual(archived["id"], payload["id"])
        conn.close()


if __name__ == "__main__":
    unittest.main()
