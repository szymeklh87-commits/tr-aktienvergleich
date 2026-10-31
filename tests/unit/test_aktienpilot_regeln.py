"""Regel-Baukasten (Abschnitte 27.4, 31): Prüfung, Normalisierung, Versionen, dreiwertige Auswertung, Kandidaten,
Sortierung, Auswahl, Ausstiege und Gewinnmitnahmen. SYNTHETISCHE Daten."""

from __future__ import annotations

import copy
import unittest

import numpy as np

from traktien.aktienpilot import auswertung as aw
from traktien.aktienpilot import gewinnziel as gz
from traktien.aktienpilot import katalog as kat
from traktien.aktienpilot import regeln, vorlagen

from tests.unit import ap_szenario as sz

S = None
K = None


def setUpModule():
    global S, K
    S = sz.bauen()
    K = kat.katalog(S.method, S.cfg)


def basis(**over) -> dict:
    r = {
        "schema": "tr-regel/1", "id": "r-test", "version": 1, "name": "Test",
        "kandidaten": [{"art": "rangliste", "gewichte": [0], "fenster": {"von": 1, "bis": 30}, "platz_bis": 1}],
        "sortierung": {"schluessel": [{"kennzahl": {"id": "rendite", "parameter": {"fenster": 30}}}]},
        "auswahl": {"anzahl": 3},
        "stop": {"initial": {"art": "atr", "faktor": 2}},
    }
    r.update(over)
    return r


def pruefe(r):
    return regeln.pruefen(r, K, S.method)


class PruefungTests(unittest.TestCase):
    def test_all_templates_are_valid_rules(self):
        for name, r in vorlagen.alle(S.cfg).items():
            p = pruefe(r)
            self.assertTrue(p.gueltig, f"{name}: {[f.as_dict() for f in p.fehler]}")

    def test_defaults_are_filled_in_visibly(self):
        p = pruefe(basis())
        self.assertTrue(p.gueltig)
        r = p.regel
        self.assertEqual(r["kandidaten"][0]["gruppe"], "A")
        self.assertEqual(r["kandidaten"][0]["politik"], "native")
        self.assertEqual(r["profil"], "FOLGETAG-SCHLUSS")
        self.assertEqual(r["zeitplan"], {"intervall": "woechentlich", "wochentag": 4})
        self.assertEqual(r["sortierung"]["schluessel"][0]["richtung"], "ab")
        self.assertEqual(r["stop"]["initial"]["sitzungen"], 14)

    def expect_error(self, r, needle: str):
        p = pruefe(r)
        self.assertFalse(p.gueltig)
        texts = " | ".join(f"{f.pfad}: {f.text}" for f in p.fehler)
        self.assertIn(needle, texts)

    def test_invalid_rules_are_rejected_with_reason(self):
        self.expect_error(basis(filter={"kennzahl": {"id": "gibtsnicht"}, "op": ">", "wert": 1}), "unbekannte Kennzahl")
        self.expect_error(basis(filter={"kennzahl": {"id": "rendite", "parameter": {"fenster": 30}}, "op": "ist_wahr"}), "passt nicht")
        self.expect_error(basis(filter={"kennzahl": {"id": "kurs"}, "op": ">", "vergleich": {"id": "rendite", "parameter": {"fenster": 30}}}), "nicht vergleichbar")
        self.expect_error(basis(filter={"kennzahl": {"id": "r2", "parameter": {"fenster": 2}}, "op": ">=", "wert": 0.5}), "mindestens 15")
        self.expect_error(basis(stop=None), "Initialstop ist Pflicht")
        self.expect_error(basis(profil="VERZOEGERTER-EINSTIEG"), "nicht simulierbar")
        self.expect_error(basis(kandidaten=[{"art": "isins", "isins": ["DE000000000X"]}]), "ungültige ISIN")
        self.expect_error(basis(verkauf={"gewinnmitnahme": {"art": "leiter", "stufen": [{"schwelle_pct": 50, "anteil_pct": 60}, {"schwelle_pct": 30, "anteil_pct": 10}]}}), "aufsteigend")
        self.expect_error(basis(verkauf={"gewinnmitnahme": {"art": "leiter", "stufen": [{"schwelle_pct": 30, "anteil_pct": 60}, {"schwelle_pct": 50, "anteil_pct": 60}]}}), "über 100 %")
        self.expect_error(basis(code="import os"), "unbekannte Felder")
        self.expect_error(basis(filter={"kennzahl": {"id": "spaeterer_sieger"}, "op": "ist_wahr"}), "nur rückblickend")
        self.expect_error(basis(id="../etc"), "Regel-ID")

    def test_complexity_limits(self):
        deep = {"kennzahl": {"id": "kurs"}, "op": ">", "wert": 1}
        for _ in range(regeln.MAX_TIEFE + 1):
            deep = {"und": [deep]}
        self.expect_error(basis(filter=deep), "verschachtelte")
        many = {"oder": [{"kennzahl": {"id": "kurs"}, "op": ">", "wert": float(i)} for i in range(regeln.MAX_BEDINGUNGEN + 1)]}
        self.expect_error(basis(filter=many), "Bedingungen je Regel")

    def test_fingerprint_versions_and_copies(self):
        a = pruefe(basis()).regel
        renamed = dict(a, name="Anderer Name")
        self.assertEqual(regeln.fingerabdruck(a), regeln.fingerabdruck(renamed))
        changed = copy.deepcopy(a)
        changed["auswahl"]["anzahl"] = 4
        self.assertNotEqual(regeln.fingerabdruck(a), regeln.fingerabdruck(changed))
        self.assertEqual(regeln.neue_version(a, changed)["version"], 2)
        self.assertIs(regeln.neue_version(a, copy.deepcopy(a)), a)
        kopie = regeln.kopieren(a, "r-kopie")
        self.assertEqual((kopie["id"], kopie["version"]), ("r-kopie", 1))
        self.assertEqual(kopie["herkunft"], {"kopie_von": "r-test@1"})

    def test_notes_explain_unreachable_thresholds_and_forward_only_metrics(self):
        p = pruefe(basis(verkauf={"gewinnmitnahme": {"art": "ganz", "schwelle_pct": 30}}))
        self.assertTrue(any("nicht mehr erreichbar" in h for h in p.hinweise))
        p = pruefe(basis(filter={"kennzahl": {"id": "kursziel_abstand"}, "op": ">", "wert": 10}))
        self.assertTrue(p.gueltig)
        self.assertIn("kursziel_abstand", p.benoetigt["nur_vorwaerts"])


class DreiwertigeLogikTests(unittest.TestCase):
    def test_kleene_and_or_not(self):
        W, F, U = aw.WAHR, aw.FALSCH, aw.UNBEKANNT
        a = np.array([W, W, W, F, F, U], dtype=np.int8)
        b = np.array([W, F, U, F, U, U], dtype=np.int8)
        np.testing.assert_array_equal(aw._kleene_and([a, b]), [W, F, U, F, F, U])
        np.testing.assert_array_equal(aw._kleene_or([a, b]), [W, W, W, F, U, U])

    def test_missing_value_is_never_true(self):
        ctx = kat.Kontext(tag=int(S.sessions[-1]), isins=S.isins + ["ZZ0000099990"], method=S.method, markt=S.markt, cfg=S.cfg, stamm=S.stamm)
        expr = {"oder": [{"kennzahl": {"id": "ma", "parameter": {"sitzungen": 20}}, "op": ">", "wert": 0}]}
        res = aw.ausdruck(ctx, K, expr)
        self.assertEqual(res.werte[-1], aw.UNBEKANNT)
        neg = aw.ausdruck(ctx, K, {"nicht": expr})
        self.assertEqual(neg.werte[-1], aw.UNBEKANNT)


class AuswahlTests(unittest.TestCase):
    def setUp(self):
        self.day = int(S.sessions[-1])
        self.ctx = S.kontext(self.day)

    def test_candidate_union_counts_each_isin_once_with_its_findings(self):
        r = pruefe(basis(auswahl={"anzahl": 50})).regel
        a = aw.auswaehlen(self.ctx, K, r)
        isins = [c.isin for c in a.kandidaten]
        self.assertEqual(len(isins), len(set(isins)))
        total = sum(len(c.fundstellen) for c in a.kandidaten)
        self.assertEqual(total, a.quellen[0]["nennungen"])
        self.assertLessEqual(len(isins), 30)
        for c in a.kandidaten:
            for f in c.fundstellen:
                self.assertEqual(f.rang, 1)
                self.assertTrue(1 <= f.fenster <= 30)

    def test_sort_ties_break_by_isin_and_selection_is_capped(self):
        r = pruefe(basis(kandidaten=[{"art": "universum"}], sortierung={"schluessel": [{"kennzahl": {"id": "waehrung"}, "richtung": "ab"}]})).regel if False else None
        # Gleichstand erzwingen: konstante Sortierkennzahl (Zahl der gültigen Listen ist für alle gleich)
        r = pruefe(basis(kandidaten=[{"art": "universum"}],
                         sortierung={"schluessel": [{"kennzahl": {"id": "gueltige_listen", "parameter": {"fenster": {"von": 1, "bis": 5}, "gewichte": [0]}}}]}))
        self.assertFalse(r.gueltig)  # E ist nur als Filter zulässig – Sortieren nach einer Konstante wäre sinnlos
        r = pruefe(basis(kandidaten=[{"art": "universum"}], sortierung={"schluessel": [{"kennzahl": {"id": "gruppe_b"}, "richtung": "ab"}]}))
        self.assertFalse(r.gueltig)
        r = pruefe(basis(kandidaten=[{"art": "universum"}], auswahl={"anzahl": 4},
                         sortierung={"schluessel": [{"kennzahl": {"id": "datenabdeckung", "parameter": {"fenster": 30}}, "richtung": "ab"}]})).regel
        a = aw.auswaehlen(self.ctx, K, r)
        self.assertEqual(len(a.ausgewaehlt), 4)
        values = [c.sortwerte[0] for c in a.kandidaten if c.platz is not None]
        order = [c for c in sorted((c for c in a.kandidaten if c.platz is not None), key=lambda c: c.platz)]
        for x, y in zip(order, order[1:]):
            self.assertGreaterEqual(x.sortwerte[0], y.sortwerte[0])
            if x.sortwerte[0] == y.sortwerte[0]:
                self.assertLess(x.isin, y.isin)
        self.assertTrue(values)

    def test_score_uses_percentiles_within_pool(self):
        r = pruefe(basis(kandidaten=[{"art": "universum"}], auswahl={"anzahl": 5}, sortierung={"score": [
            {"kennzahl": {"id": "log_r2", "parameter": {"sitzungen": 60}}, "gewicht": 0.6},
            {"kennzahl": {"id": "log_steigung_jahr", "parameter": {"sitzungen": 60}}, "gewicht": 0.4}]})).regel
        a = aw.auswaehlen(self.ctx, K, r)
        scored = [c for c in a.kandidaten if c.score is not None]
        self.assertTrue(all(0.0 <= c.score <= 100.0 for c in scored))
        best = max(scored, key=lambda c: (c.score, -ord(c.isin[-1])))
        self.assertEqual(a.ausgewaehlt[0], min((c for c in scored if c.score == best.score), key=lambda c: c.isin).isin)

    def test_branch_limit_and_too_few_candidates(self):
        r = pruefe(basis(kandidaten=[{"art": "universum"}], auswahl={"anzahl": 10, "max_je_branche": 1},
                         sortierung={"schluessel": [{"kennzahl": {"id": "rendite", "parameter": {"fenster": 30}}}]})).regel
        a = aw.auswaehlen(self.ctx, K, r)
        sectors = [S.stamm[i]["branche"] for i in a.ausgewaehlt]
        self.assertEqual(len(sectors), len(set(sectors)))
        self.assertTrue(a.statistik["zu_wenige"])

    def test_unknown_filter_result_excludes_with_reason(self):
        isins = S.isins[:3] + ["ZZ0000099990"]
        r = pruefe(basis(kandidaten=[{"art": "universum"}], filter={"kennzahl": {"id": "ma", "parameter": {"sitzungen": 20}}, "op": ">", "wert": 0})).regel
        ctx = kat.Kontext(tag=self.day, isins=isins, method=S.method, comp=None, markt=S.markt, cfg=S.cfg, stamm=S.stamm)
        r["sortierung"] = {"schluessel": [{"kennzahl": {"id": "kurs"}, "richtung": "ab"}]}
        a = aw.auswaehlen(ctx, K, r)
        missing = next(c for c in a.kandidaten if c.isin == "ZZ0000099990")
        self.assertEqual(missing.filter, aw.UNBEKANNT)
        self.assertIn("nicht prüfbar", missing.grund)
        self.assertNotIn("ZZ0000099990", a.ausgewaehlt)


class AusstiegTests(unittest.TestCase):
    def test_buffer_filter_and_holding_period(self):
        day = int(S.sessions[-1])
        ctx = S.kontext(day)
        r = pruefe(basis(kandidaten=[{"art": "universum"}], auswahl={"anzahl": 2},
                         filter={"kennzahl": {"id": "rendite", "parameter": {"fenster": 30}}, "op": ">", "wert": -1000},
                         verkauf={"herausfallen": {"aktiv": True, "puffer": 2}, "max_haltedauer_sitzungen": 50},
                         optionen={"mindesthaltedauer_sitzungen": 3})).regel
        a = aw.auswaehlen(ctx, K, r)
        place3, place9 = a.sortiert[2], a.sortiert[8]
        held = {place3: {"haltedauer": 10}, place9: {"haltedauer": 10}, a.sortiert[10]: {"haltedauer": 1}, a.sortiert[0]: {"haltedauer": 60}}
        ex = aw.ausstiege(ctx, K, r, a, held)
        self.assertFalse(ex[place3].verkaufen)  # Platz 3 ≤ 2 + Puffer 2
        self.assertTrue(ex[place9].verkaufen)
        self.assertFalse(ex[a.sortiert[10]].verkaufen)  # Mindesthaltedauer
        self.assertTrue(ex[a.sortiert[0]].verkaufen)  # Haltedauer überschritten
        self.assertEqual(ex[a.sortiert[0]].art, "haltedauer")


class GewinnmitnahmeTests(unittest.TestCase):
    LEITER = {"art": "leiter", "basis": "nach_kosten", "bezug": "urspruenglich",
              "stufen": [{"schwelle_pct": 30, "anteil_pct": 25}, {"schwelle_pct": 50, "anteil_pct": 25}, {"schwelle_pct": 100, "anteil_pct": 50}]}

    def test_threshold_just_below_at_and_above(self):
        gm = {"art": "ganz", "schwelle_pct": 30.0, "basis": "nach_kosten", "umfang": {"art": "alles"}}
        st = gz.Stufenzustand(10)
        self.assertIsNone(gz.faellig(gm, st, 10, 29.999))
        self.assertEqual(gz.faellig(gm, st, 10, 30.0).stueck, 10)
        self.assertEqual(gz.faellig(gm, st, 10, 31.0).stueck, 10)
        self.assertIsNone(gz.faellig(gm, gz.Stufenzustand(10, erledigt=[0]), 10, 40.0))
        self.assertIsNone(gz.faellig(gm, st, 10, None), "unbekannter Einstand: nicht prüfbar, kein Verkauf")

    def test_partial_amounts(self):
        st = gz.Stufenzustand(10)
        self.assertEqual(gz.faellig({"art": "ganz", "schwelle_pct": 50, "basis": "kurs", "umfang": {"art": "anteil", "pct": 50}}, st, 7, 60).stueck, 3)
        self.assertEqual(gz.faellig({"art": "ganz", "schwelle_pct": 50, "basis": "kurs", "umfang": {"art": "stueck", "stueck": 20}}, st, 7, 60).stueck, 7)

    def test_ladder_each_stage_once_and_gap_over_stages(self):
        st = gz.Stufenzustand(100)
        f = gz.faellig(self.LEITER, st, 100, 35)
        self.assertEqual((f.stufen, f.stueck), (("0",), 25))
        st.erledigt.append(0)
        self.assertIsNone(gz.faellig(self.LEITER, st, 75, 45))
        f = gz.faellig(self.LEITER, st, 75, 120)  # Sprung über +50 % und +100 %
        self.assertEqual((f.stufen, f.stueck), (("1", "2"), 75))
        st.offen = {"1": "o-x", "2": "o-x"}
        self.assertIsNone(gz.faellig(self.LEITER, st, 75, 130), "beauftragte Stufen nicht doppelt")

    def test_small_position_rounds_without_losing_shares(self):
        st = gz.Stufenzustand(3)
        f = gz.faellig(self.LEITER, st, 3, 35)
        self.assertEqual(f.stueck, 0)
        self.assertEqual(f.uebersprungen, (0,))
        st.erledigt.append(0)
        f = gz.faellig(self.LEITER, st, 3, 200)
        self.assertEqual(f.stueck, 3)

    def test_remaining_reference(self):
        gm = dict(self.LEITER, bezug="verbleibend")
        st = gz.Stufenzustand(100)
        f = gz.faellig(gm, st, 100, 120)
        self.assertEqual(f.stueck, 25 + 18 + 28)  # 25 % von 100, 25 % von 75 (18), 50 % von 57 (28)

    def test_gain_after_costs_formula(self):
        # 10 Stück, Einstand 1.000 EUR inkl. Kaufkosten; Kurs 130 EUR, Verkaufsfaktor 0,999, Gebühr 1 EUR
        g = gz.gewinn_nach_kosten_pct(10, 1000.0, 130.0, sell_price_factor=0.999, fee_eur=1.0)
        self.assertAlmostEqual(g, 100.0 * ((10 * 130.0 * 0.999 - 1.0) - 1000.0) / 1000.0)
        self.assertIsNone(gz.gewinn_nach_kosten_pct(10, None, 130.0, sell_price_factor=1, fee_eur=1))
        self.assertIsNone(gz.gewinn_nach_kosten_pct(10, 0.0, 130.0, sell_price_factor=1, fee_eur=1))


if __name__ == "__main__":
    unittest.main()
