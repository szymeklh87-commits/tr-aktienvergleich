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
        # ab 1.23.0 betrachtet der Optimierer nur Aktien mit nachgewiesenem Ø Tagesumsatz ab 10 Mio. USD: Stückzahlen ×10, damit
        # alle zwölf synthetischen Aktien investierbar bleiben (der Ausschluss selbst: test_only_stocks_with_minimum_turnover_are_investable)
        cls.S = S = sz.bauen(fuell=6, volumen_faktor=10.0)
        cls.K = kat.katalog(S.method, S.cfg)
        cls.liste, _ = mk.merkmale(cls.K)
        cls.ocfg = op.load_config()
        cls.D = int(S.sessions[-1])

    def ctx(self):
        ctx = self.S.kontext(self.D)
        return ctx

    def einst(self, **kw):
        return pf.Einstellungen(**dict(dict(anzahl=4, max_gewicht_pct=40.0, max_branche_pct=100.0, min_umsatz_eur=0.0), **kw))

    def test_only_stocks_with_minimum_turnover_are_investable(self):
        """Ab 1.23.0: investierbar nur mit nachgewiesenem Mindestumsatz der Ranglisten (Menge L) – auch bei min_umsatz_eur = 0."""
        S = sz.bauen(fuell=6)  # ursprüngliche Stückzahlen: nur ein Teil der Aktien erreicht 10 Mio. USD
        ctx = S.kontext(int(S.sessions[-1]))
        liquid = np.asarray(ctx.comp.liquid, dtype=bool)
        self.assertTrue(0 < liquid.sum() < len(ctx.isins), "Szenario braucht Aktien über und unter der Schwelle")
        mask = op.investierbar(ctx, 0.0)
        self.assertTrue(np.array_equal(mask, liquid), "genau die Aktien mit Mindestumsatz")
        for k, t in enumerate(ctx.comp.turnover):
            self.assertEqual(bool(mask[k]), bool(t is not None and t.determined and t.avg_usd >= 10_000_000.0), ctx.isins[k])

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

    def test_risk_variants_fall_back_to_reliable_horizon_and_say_so(self):
        """12 Wochen nicht belastbar, 4 Wochen belastbar: Die Risikovarianten (Anlagehorizont 12 Wochen) rechnen ausdrücklich mit
        4 Wochen, „Mittelfristig“ ebenso (4 Wochen liegt in ihrem Zeitraum); „Langfristig“ hat keinen belastbaren Horizont in
        ihrem Zeitraum und bleibt ohne Vorschlag. Ein anderer Anlagehorizont gilt für die Risikovarianten."""
        erg = ergebnis(self.liste)
        erg["horizonte"]["w4"] = dict(erg["horizonte"]["w2"])
        erg["horizonte"]["w12"] = {"modell": None, "belastbarkeit": "nicht belastbar", "endmodell": None, "kalibrierung": None, "modell_grund": "zu kurz"}
        emp = op.empfehlen(ctx=self.ctx(), eintraege=self.K, liste=self.liste, ergebnis=erg, einstellungen=self.einst(), ap_cfg=self.S.cfg, ocfg=self.ocfg)
        v = emp["varianten"]
        for name in ("ausgewogen", "rendite", "stabil"):
            self.assertTrue(v[name]["verfuegbar"], name)
            self.assertEqual((v[name]["horizont"], v[name]["horizont_wunsch"]), ("w4", "w12"))
            self.assertIn("12 Wochen nicht belastbar", v[name]["ersatz"])
        self.assertEqual((v["mittel"]["verfuegbar"], v["mittel"]["horizont"]), (True, "w4"))
        self.assertFalse(v["lang"]["verfuegbar"])
        self.assertNotIn("ersatz", v["kurz"])
        emp2 = op.empfehlen(ctx=self.ctx(), eintraege=self.K, liste=self.liste, ergebnis=erg, einstellungen=self.einst(horizont="w2"), ap_cfg=self.S.cfg,
                            ocfg=self.ocfg)
        self.assertEqual(emp2["varianten"]["ausgewogen"]["horizont"], "w2")
        self.assertNotIn("ersatz", emp2["varianten"]["ausgewogen"])
        with self.assertRaises(op.OptimiererFehler):
            op.pruefen_einstellungen(pf.Einstellungen(horizont="w3"))
        with self.assertRaises(op.OptimiererFehler):
            op.pruefen_einstellungen(pf.Einstellungen(anzahl=25))

    def test_calibrated_expectation_is_continuous_and_monotone(self):
        """Erwartung je Aktie zwischen den Dezilmitten interpoliert: keine Stufen bei gleichem Dezil, steigend mit der Wertung."""
        emp = op.empfehlen(ctx=self.ctx(), eintraege=self.K, liste=self.liste, ergebnis=ergebnis(self.liste), einstellungen=self.einst(),
                           ap_cfg=self.S.cfg, ocfg=self.ocfg)
        p = emp["_prognosen"]["w2"]
        ok = np.isfinite(p["rang"])
        order = np.argsort(p["rang"][ok])
        erw = p["erwartet"][ok][order]
        self.assertTrue(np.all(np.diff(erw) >= -1e-9), "steigend mit dem Rang")
        self.assertGreater(len(np.unique(np.round(erw, 6))), 10, "nicht nur zehn Stufen")
        self.assertGreaterEqual(float(erw.min()), -2.0 - 1e-9)
        self.assertLessEqual(float(erw.max()), -2.0 + 0.6 * 9 + 1e-9, "nie außerhalb der äußeren Dezile")

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
                     (json.dumps({"profil": {"name": "Testprofil vorsichtig", "welt": 0.4, "geldmarkt": 0.6}, "startkapital_eur": 25000}),))
        e, herkunft = op.einstellungen(conn, self.ocfg)
        self.assertEqual((e.variante, e.kapital_eur, herkunft), ("stabil", 25000.0, "risikoprofil"), "Profil und Kapital der Pilot-Einrichtung")
        conn.execute("INSERT INTO ap_zustand(schluessel, wert_json, aktualisiert_am) VALUES (?, ?, 'x')",
                     (op.EINSTELLUNGEN, json.dumps(dict(self.ocfg.einstellungen.as_dict(), variante="kurz", anzahl=5))))
        e, herkunft = op.einstellungen(conn, self.ocfg)
        self.assertEqual((e.variante, e.anzahl, herkunft), ("kurz", 5, "app"))
        conn.close()


if __name__ == "__main__":
    unittest.main()


class _OhneAbruf:
    def fetch_history(self, *args, **kwargs):
        from traktien.providers.base import NoDataError

        raise NoDataError("Test ohne Abruf")


class TaeglicherLaufTests(unittest.TestCase):
    """Kette Forschungslauf → Ablage → täglicher Lauf: das abgelegte Ergebnis wird übernommen, Empfehlung und Prognosen des
    Stichtags werden gespeichert und stehen im verschlüsselten App-Stand."""

    def test_daily_run_imports_result_and_recommends(self):
        import tempfile
        import types
        from pathlib import Path

        from traktien.aktienpilot import stand, tageslauf
        from traktien.util import crypto
        from traktien.util.timeutil import day_to_date

        S = sz.bauen(fuell=4)
        K = kat.katalog(S.method, S.cfg)
        liste, inventar = mk.merkmale(K)
        conn = db.connect(":memory:")
        db.migrate(conn)
        ocfg = op.load_config()
        conn.execute("INSERT INTO ap_zustand(schluessel, wert_json, aktualisiert_am) VALUES (?, ?, 'x')",
                     (op.EINSTELLUNGEN, json.dumps(dict(ocfg.einstellungen.as_dict(), min_umsatz_eur=0.0, anzahl=4, max_gewicht_pct=40.0, max_branche_pct=100.0))))
        metas = [types.SimpleNamespace(isin=a.isin, name=a.name, instrument_type="stammaktie", mic="XETR", exchange_key="XETR", currency=a.waehrung,
                                       ticker=None) for a in S.aktien]
        D = int(S.sessions[-8])
        erg = ergebnis(liste)
        payload = {"schema": op.SCHEMA, "id": "opt-0123456789ab", "version": "optimierer-test", "modus": "DEMO", "synthetisch": True,
                   "erstellt_utc": "2026-10-31T05:00:00Z", "datenstand": "s", "datentag": day_to_date(D - 1).isoformat(),
                   "merkmale": [m.as_dict() for m in liste], "inventar": inventar, "forschung": erg, "empfehlung": {}, "zaehlung": {}, "hinweise": []}
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / op.ORDNER / f"{op.dateiname(payload)}.bin"
            path.parent.mkdir(parents=True)
            path.write_bytes(op.exportieren(payload, None))
            abend = dt.datetime.combine(day_to_date(D), dt.time(19, 0), tzinfo=dt.timezone.utc)
            summary = tageslauf.ausfuehren(conn, cfg=S.cfg, method=S.method, comp=S.comp(D), metas=metas, D=D, fx=S.markt.fx, calendars=S.calendars,
                                           provider=_OhneAbruf(), run_id="t1", now=abend, key=None, snapshot_id="s1", data_mode="demo",
                                           reihen={i: S.markt.series[i] for i in S.isins}, optimiererergebnisse=lambda: op.aus_ordner(Path(root)))
        self.assertEqual(summary["optimierer"]["neu"], 1)
        self.assertEqual(summary["optimierer"]["heute"]["status"], "ok", summary["optimierer"])
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM ap_empfehlung WHERE datentag = ?", (D,)).fetchone()[0], len(pf.VARIANTEN) + 1)
        self.assertGreater(conn.execute("SELECT COUNT(*) FROM ap_prognose WHERE datentag = ?", (D,)).fetchone()[0], 0)
        sid, _when, blob = stand.neuester(conn)
        app = json.loads(crypto.unpack(blob, None, f"pilot/{sid}/pilot.bin"))
        opt = app["optimierer"]
        self.assertEqual(opt["modell"]["id"], "opt-0123456789ab")
        self.assertTrue(opt["heute"]["varianten"]["kurz"]["verfuegbar"])
        self.assertFalse(opt["heute"]["varianten"]["lang"]["verfuegbar"])
        self.assertIn("rangliste", opt["heute"]["varianten"])
        # Modus B: Spielgeld-Musterdepot der Standardvariante folgt der Empfehlung desselben Stichtags (Käufe in der nächsten Sitzung)
        from traktien.aktienpilot import speicher

        did = "demo-f-empfehlung-ausgewogen"
        self.assertIn(did, [d["id"] for d in app["depots"]])
        empfohlen = {p["isin"] for p in json.loads(conn.execute("SELECT inhalt FROM ap_empfehlung WHERE datentag = ? AND variante = 'ausgewogen'",
                                                                 (D,)).fetchone()[0])["positionen"]}
        self.assertTrue(empfohlen)
        z = speicher.zustand_laden(conn, did)
        kauf = {o.isin for o in z.orders if o.richtung == "kauf"}
        self.assertTrue(kauf, "Kauforders für die empfohlenen Aktien")
        self.assertLessEqual(kauf, empfohlen, "nur empfohlene Aktien")
        regel = app["regeln"]["r-empfehlung-ausgewogen@1"]
        self.assertEqual(regel["kandidaten"], [{"art": "empfehlung", "variante": "ausgewogen"}])
        self.assertEqual(regel["kapital"], {"art": "empfehlung"})
        self.assertNotIn("ZZ", json.dumps(summary), "öffentliche Zusammenfassung ohne ISINs")
        self.assertEqual(opt["freigabe"]["vorwaerts_sitzungen"], 40, "Freigaberegeln des Labors für eine Übernahme (Modus C)")
        conn.close()

    def test_rule_source_recommendation_is_checked(self):
        from traktien.aktienpilot import regeln

        S = sz.bauen(fuell=2)
        K = kat.katalog(S.method, S.cfg)
        r = op.musterdepot_regel("kurz")
        p = regeln.pruefen(r, K, S.method)
        self.assertTrue(p.gueltig, [f.as_dict() for f in p.fehler])
        falsch = dict(r, kandidaten=[{"art": "empfehlung", "variante": "irgendwas"}])
        self.assertFalse(regeln.pruefen(falsch, K, S.method).gueltig)
        ohne = dict(r, kandidaten=[{"art": "universum"}])
        fehler = regeln.pruefen(ohne, K, S.method).fehler
        self.assertTrue(any(f.pfad == "kapital.art" for f in fehler), "Gewichte der Empfehlung nur mit ihrer Quelle")
