"""Depot-Optimierer im Zusammenspiel (Aufträge 18 und 19): Empfehlung zum Stichtag aus echten Katalogmerkmalen eines
SYNTHETISCHEN Szenarios und einem Forschungsergebnis mit Modell und Kalibrierung – Rangliste mit Begründung, Depotvarianten
mit Grenzen, unveränderliche Speicherung, Veränderungen gegenüber der letzten Empfehlung, Prognosekontrolle, Folgerenditen."""

from __future__ import annotations

import datetime as dt
import json
import sqlite3
import unittest

import numpy as np

from traktien.aktienpilot import forschung as fo
from traktien.aktienpilot import katalog as kat
from traktien.aktienpilot import merkmale as mk
from traktien.aktienpilot import optimierer as op
from traktien.aktienpilot import portfolio as pf
from traktien.store import db

from tests.unit import ap_szenario as sz

NOW = dt.datetime(2026, 10, 31, 19, 0, tzinfo=dt.timezone.utc)


def ergebnis(liste) -> dict:
    """Forschungsergebnis mit einem Momentum-Modell für 2 Wochen und einem linearen für 12 Wochen (Kalibrierung steigend)."""
    dezile = [{"dezil": k + 1, "n": 100, "mittel_pct": -2.0 + 0.6 * k, "mittel_roh_pct": -2.0 + 0.6 * k, "positiv_pct": 40.0 + 2 * k,
               "q10_pct": -8.0 + 0.5 * k, "q50_pct": -1.5 + 0.6 * k, "q90_pct": 6.0 + 0.8 * k} for k in range(10)]
    kal = {"dezile": dezile, "basis_positiv_pct": 50.0, "brier": {"modell": 0.24, "basis": 0.25}}
    lin = fo.Modell("linear", ["rendite@fenster=60", "volatilitaet"], [1, -1], koeffizienten=[4.0, 2.0], lam=10.0)
    return {"namen": {m.schluessel: m.name for m in liste}, "horizonte": {
        "w2": {"modell": "momentum", "belastbarkeit": "belastbar", "endmodell": fo.Modell("momentum", ["rendite@fenster=20"], [1]).as_dict(), "kalibrierung": kal},
        "w12": {"modell": "linear", "belastbarkeit": "eingeschränkt belastbar", "endmodell": lin.as_dict(), "kalibrierung": kal},
        "w52": {"modell": None, "belastbarkeit": "nicht belastbar", "endmodell": None, "kalibrierung": None, "modell_grund": "zu wenig Historie"},
    }}


class EmpfehlungTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.S = S = sz.bauen(fuell=6)
        cls.K = kat.katalog(S.method, S.cfg)
        cls.liste, _ = mk.merkmale(cls.K)
        cls.ocfg = op.load_config()
        cls.D = int(S.sessions[-1])

    def ctx(self):
        ctx = self.S.kontext(self.D)
        return ctx

    def einst(self, **kw):
        return pf.Einstellungen(**dict(dict(anzahl=4, max_gewicht_pct=40.0, max_branche_pct=100.0, min_umsatz_eur=0.0), **kw))

    def test_recommendation_with_ranking_reasons_and_variants(self):
        emp = op.empfehlen(ctx=self.ctx(), eintraege=self.K, liste=self.liste, ergebnis=ergebnis(self.liste), einstellungen=self.einst(),
                           ap_cfg=self.S.cfg, ocfg=self.ocfg)
        h = emp["horizonte"]["w2"]
        self.assertGreater(h["aktien"], 3)
        top = h["rangliste"][0]
        self.assertEqual(top["platz"], 1)
        self.assertTrue({"isin", "eignung", "erwartet_pct", "positiv_pct", "q10_pct", "q90_pct", "kosten_pct", "dafuer", "dagegen", "kurs"} <= set(top))
        self.assertTrue(top["kurs"] and top["kurs"]["datum"] and top["kurs"]["waehrung"], "Kurs mit Datum und Währung")
        self.assertGreaterEqual(top["eignung"], h["rangliste"][-1]["eignung"])
        self.assertEqual(emp["horizonte"]["w52"]["belastbarkeit"], "nicht belastbar")
        self.assertEqual(emp["horizonte"]["w52"]["rangliste"], [])
        v = emp["varianten"]
        self.assertFalse(v["lang"]["verfuegbar"], "52 Wochen nicht belastbar → kein Depotvorschlag")
        self.assertIn("nicht belastbar", v["lang"]["grund"])
        for name in ("kurz", "ausgewogen"):
            self.assertTrue(v[name]["verfuegbar"], name)
            pos = v[name]["positionen"]
            self.assertLessEqual(len(pos), 4)
            self.assertAlmostEqual(sum(p["gewicht_pct"] for p in pos), 100.0, delta=0.5)
            self.assertTrue(all(p["gewicht_pct"] <= 40.0 + 0.5 for p in pos))
            kz = v[name]["kennzahlen"]
            self.assertTrue({"erwartet_pct", "erwartet_nach_kosten_pct", "schwankung_pct", "verlustszenario_pct", "effektive_anzahl"} <= set(kz))
            self.assertTrue(all(z["art"] == "kaufen" for z in v[name]["veraenderungen"]), "erste Empfehlung: alles neu")

    def test_storage_is_append_only_and_changes_follow(self):
        conn = db.connect(":memory:")
        db.migrate(conn)
        ctx = self.ctx()
        e = op.empfehlen(ctx=ctx, eintraege=self.K, liste=self.liste, ergebnis=ergebnis(self.liste), einstellungen=self.einst(), ap_cfg=self.S.cfg, ocfg=self.ocfg)
        n = op.prognosen_speichern(conn, e, ctx=ctx, modell_id="opt-000000000001", modus="DEMO", ocfg=self.ocfg, now=NOW)
        self.assertGreater(n, 0)
        self.assertEqual(op.prognosen_speichern(conn, e, ctx=ctx, modell_id="opt-000000000001", modus="DEMO", ocfg=self.ocfg, now=NOW), 0, "gleicher Tag: nichts doppelt")
        self.assertEqual(op.empfehlung_speichern(conn, e, D=self.D, modell_id="opt-000000000001", modus="DEMO", now=NOW), len(pf.VARIANTEN))
        with self.assertRaises(sqlite3.DatabaseError):
            conn.execute("UPDATE ap_prognose SET erwartet_pct = 99")
        with self.assertRaises(sqlite3.DatabaseError):
            conn.execute("DELETE FROM ap_empfehlung")
        # nächster Tag: Veränderungen gegenüber der gespeicherten Empfehlung
        D2 = self.D + 1
        alt = op.letzte_empfehlung(conn, "DEMO", D2)
        self.assertEqual(set(alt), {v for v in pf.VARIANTEN if e["varianten"][v]["verfuegbar"]})
        e2 = op.empfehlen(ctx=ctx, eintraege=self.K, liste=self.liste, ergebnis=ergebnis(self.liste), einstellungen=self.einst(), ap_cfg=self.S.cfg,
                          ocfg=self.ocfg, alt=alt)
        arten = {z["art"] for z in e2["varianten"]["ausgewogen"]["veraenderungen"]}
        self.assertTrue(arten <= {"halten", "aufstocken", "reduzieren", "kaufen", "verkaufen", "nicht_aufnehmen"})
        self.assertIn("halten", arten, "gleiche Daten: das Depot bleibt")
        conn.close()

    def test_forward_returns_in_euro_and_unknown_future(self):
        S = self.S
        isins = list(S.isins)[:3]
        tage = np.array([int(S.sessions[-30]), int(S.sessions[-1])])
        R = op.folgerenditen(S.markt, isins, tage, {"w1": 5})
        s = S.markt.series[isins[0]]
        k = s.index_of(tage[0])
        r = op.eur_reihe(S.markt, isins[0])
        self.assertAlmostEqual(float(R["w1"][0, 0]), (r[1][k + 5] / r[1][k] - 1) * 100, places=3)
        self.assertTrue(np.isnan(R["w1"][1]).all(), "nach dem letzten Tag ist nichts bekannt")

    def test_control_compares_stored_predictions_with_later_prices(self):
        conn = db.connect(":memory:")
        db.migrate(conn)
        S = self.S
        D0 = int(S.sessions[-12])
        ctx0 = S.kontext(D0)
        e = op.empfehlen(ctx=ctx0, eintraege=self.K, liste=self.liste, ergebnis=ergebnis(self.liste), einstellungen=self.einst(), ap_cfg=S.cfg, ocfg=self.ocfg)
        op.prognosen_speichern(conn, e, ctx=ctx0, modell_id="opt-000000000002", modus="DEMO", ocfg=self.ocfg, now=NOW)
        k = op.kontrolle(conn, "DEMO", S.markt, self.D)
        w2 = next(x for x in k["ausgewertet"] if x["horizont"] == "w2")
        self.assertEqual(w2["prognosen"], int(conn.execute("SELECT COUNT(*) FROM ap_prognose WHERE horizont = 'w2'").fetchone()[0]))
        self.assertIsNotNone(w2["richtung_pct"])
        self.assertFalse(any(x["horizont"] == "w12" for x in k["ausgewertet"]), "12 Wochen noch nicht vergangen")
        self.assertGreater(k["offen"], 0)
        conn.close()

    def test_settings_validation_and_risk_profile_default(self):
        with self.assertRaises(op.OptimiererFehler):
            op.pruefen_einstellungen(pf.Einstellungen(anzahl=3, max_gewicht_pct=20.0))
        conn = db.connect(":memory:")
        db.migrate(conn)
        e, herkunft = op.einstellungen(conn, self.ocfg)
        self.assertEqual((e.variante, herkunft), ("ausgewogen", "konfiguration"))
        conn.execute("INSERT INTO ap_zustand(schluessel, wert_json, aktualisiert_am) VALUES ('pilot:einrichtung', ?, 'x')",
                     (json.dumps({"profil": {"name": "Testprofil vorsichtig", "welt": 0.4, "geldmarkt": 0.6}}),))
        e, herkunft = op.einstellungen(conn, self.ocfg)
        self.assertEqual((e.variante, herkunft), ("stabil", "risikoprofil"))
        conn.execute("INSERT INTO ap_zustand(schluessel, wert_json, aktualisiert_am) VALUES (?, ?, 'x')",
                     (op.EINSTELLUNGEN, json.dumps(dict(self.ocfg.einstellungen.as_dict(), variante="kurz", anzahl=5))))
        e, herkunft = op.einstellungen(conn, self.ocfg)
        self.assertEqual((e.variante, e.anzahl, herkunft), ("kurz", 5, "app"))
        conn.close()


if __name__ == "__main__":
    unittest.main()
