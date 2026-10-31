"""Kennzahlenkatalog (Abschnitte 31.8, 32): eine Definition je Kennzahl, gleiche Werte wie Rangliste und Häufigkeit,
nur Daten bis zum Entscheidungstag, fehlende Werte bleiben fehlend. SYNTHETISCHE Daten."""

from __future__ import annotations

import json
import math
import unittest

import numpy as np

from traktien.aktienpilot import indikatoren as ind
from traktien.aktienpilot import katalog as kat
from traktien.analytics.codes import RETURN_PUBLISHABLE
from traktien.analytics.frequency import aggregate_frequency

from tests.unit import ap_szenario as sz

S = None


def setUpModule():
    global S
    S = sz.bauen()


class KatalogAufbauTests(unittest.TestCase):
    def test_every_metric_has_complete_unique_definition(self):
        k = kat.katalog(S.method, S.cfg)
        self.assertGreaterEqual(len(k), 50)
        for kid, e in k.items():
            kz = e.kennzahl
            self.assertEqual(kid, kz.id)
            for field in ("name", "erklaerung", "typ", "gruppe", "quelle", "methode", "aufwaermphase", "fehlwert"):
                self.assertTrue(getattr(kz, field), f"{kid}: {field} fehlt")
            self.assertIn(kz.typ, ("zahl", "wahrheitswert", "kategorie", "rang"))
            self.assertIn(kz.backtest, ("ja", "nur_vorwaerts", "nein"))
        names = [e.kennzahl.name for e in k.values()]
        self.assertEqual(len(names), len(set(names)), "zwei Kennzahlen mit gleichem Namen")

    def test_json_for_app_is_stable_and_serializable(self):
        a = kat.katalog_json(S.method, S.cfg)
        b = kat.katalog_json(S.method, S.cfg)
        self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True))
        self.assertEqual(a["schema"], "tr-kennzahlenkatalog/1")
        ids = [m["id"] for m in a["kennzahlen"]]
        self.assertEqual(len(ids), len(set(ids)))

    def test_parameters_come_from_method_configuration(self):
        k = kat.katalog(S.method, S.cfg)
        self.assertEqual(k["r2"].kennzahl.param("fenster").minimum, S.method.min_obs_trend)
        self.assertEqual(k["rendite"].kennzahl.param("fenster").maximum, S.method.max_window)
        self.assertEqual(tuple(k["rang"].kennzahl.param("gewicht").werte), tuple(S.method.weights))

    def test_short_r2_window_is_rejected_with_explanation(self):
        k = kat.katalog(S.method, S.cfg)
        with self.assertRaises(kat.KatalogFehler) as cm:
            k["r2"].kennzahl.parameter_pruefen({"fenster": 3})
        self.assertIn("15", str(cm.exception))
        self.assertIn("Schlusskurse", str(cm.exception))

    def test_retrospective_metric_is_blocked(self):
        k = kat.katalog(S.method, S.cfg)
        ctx = S.kontext(int(S.sessions[-1]))
        with self.assertRaises(kat.KatalogFehler):
            kat.werte(ctx, k, {"id": "spaeterer_sieger"})


class GleicheBerechnungTests(unittest.TestCase):
    """Der Regelmotor liest dieselben Felder wie die veröffentlichten Ranglisten – keine Zweitformel."""

    def setUp(self):
        self.k = kat.katalog(S.method, S.cfg)
        self.day = int(S.sessions[-1])
        self.ctx = S.kontext(self.day)
        self.comp = self.ctx.comp

    def test_return_and_r2_equal_engine_fields(self):
        for h in (1, 7, 30, 90):
            _, _, r = kat.werte(self.ctx, self.k, {"id": "rendite", "parameter": {"fenster": h}})
            st = self.comp.status[:, h - 1]
            for i in range(self.ctx.n):
                if int(st[i]) in RETURN_PUBLISHABLE:
                    self.assertEqual(r[i], self.comp.r[i, h - 1] * 100.0)
                else:
                    self.assertTrue(math.isnan(r[i]))
        _, _, r2 = kat.werte(self.ctx, self.k, {"id": "r2", "parameter": {"fenster": 60}})
        ok = np.isfinite(r2)
        np.testing.assert_array_equal(r2[ok], self.comp.r2[ok, 59])

    def test_rank_and_score_equal_published_ranking(self):
        for gruppe in ("A", "B"):
            for w in (0, 60, 100):
                ranking = self.comp.rankings[30].ranking("native", w) if gruppe == "A" else self.comp.rankings[30].group_b.ranking("native", w)
                _, _, rank = kat.werte(self.ctx, self.k, {"id": "rang", "parameter": {"fenster": 30, "gewicht": w, "gruppe": gruppe, "politik": "native"}})
                _, _, score = kat.werte(self.ctx, self.k, {"id": "score", "parameter": {"fenster": 30, "gewicht": w, "gruppe": gruppe, "politik": "native"}})
                for pos, idx in enumerate(ranking.order):
                    self.assertEqual(rank[idx], pos + 1)
                    self.assertEqual(score[idx], ranking.scores[pos])
                outside = np.setdiff1d(np.arange(self.ctx.n), np.asarray(ranking.order))
                self.assertTrue(np.all(np.isnan(rank[outside])))

    def test_frequency_equals_published_counting_function(self):
        weights = list(S.method.weights)
        params = {"k": 10, "fenster": {"von": 1, "bis": 30}, "gewichte": weights, "gruppe": "A", "politik": "native"}
        _, _, n10 = kat.werte(self.ctx, self.k, {"id": "haeufigkeit", "parameter": params})
        _, _, n1 = kat.werte(self.ctx, self.k, {"id": "haeufigkeit", "parameter": dict(params, k=1)})
        _, _, a = kat.werte(self.ctx, self.k, {"id": "auswertbare_zellen", "parameter": {key: v for key, v in params.items() if key != "k"}})
        _, _, e = kat.werte(self.ctx, self.k, {"id": "gueltige_listen", "parameter": {key: v for key, v in params.items() if key != "k"}})
        ref = aggregate_frequency({h: self.comp.rankings[h] for h in range(1, 31)}, policy="native", weights=weights, window_days=list(range(1, 31)),
                                  top_k=10, r_matrix=self.comp.r, start_matrix=self.comp.start_day, cutoff_day=self.comp.cutoff_day, isin_of=self.comp.isin_of)
        by_idx = {x.idx: x for x in ref.entries}
        for idx, entry in by_idx.items():
            self.assertEqual(n10[idx], entry.n10)
            self.assertEqual(n1[idx], entry.n1)
            self.assertEqual(a[idx], entry.available_cells)
        self.assertTrue(np.all(e == ref.valid_cells))
        # Invariante N1 ≤ N10 ≤ A ≤ E (Abschnitt 25.5)
        ok = np.isfinite(n10)
        self.assertTrue(np.all(n1[ok] <= n10[ok]))
        self.assertTrue(np.all(n10[ok] <= a[ok]))
        self.assertTrue(np.all(a <= e))


class KeinBlickInDieZukunftTests(unittest.TestCase):
    def test_indicators_ignore_bars_after_decision_day(self):
        k = kat.katalog(S.method, S.cfg)
        day = int(S.sessions[-40])
        refs = [{"id": "kurs"}, {"id": "ma", "parameter": {"sitzungen": 20}}, {"id": "rsi", "parameter": {"sitzungen": 14}},
                {"id": "atr", "parameter": {"sitzungen": 14}}, {"id": "hoch", "parameter": {"sitzungen": 55}},
                {"id": "volumenfaktor", "parameter": {"sitzungen": 20}}, {"id": "log_r2", "parameter": {"sitzungen": 60}},
                {"id": "muster_vor_ausbruch"}, {"id": "muster_vor_ausbruch_score"}, {"id": "muster_seitwaertsbasis"}, {"id": "volumensprung"}]
        before = {r["id"]: kat.werte(kat.Kontext(tag=day, isins=S.isins, method=S.method, markt=S.markt, cfg=S.cfg, stamm=S.stamm), k, r)[2].copy() for r in refs}
        # Zukunft verändern: alle Kerzen nach dem Entscheidungstag verdoppeln
        saved = {}
        for isin, s in S.markt.series.items():
            saved[isin] = (s.close.copy(), s.high.copy(), s.low.copy(), s.volume.copy())
            later = s.days > day
            s.close[later] *= 2.0
            s.high[later] *= 2.0
            s.low[later] *= 2.0
            s.volume[later] *= 5.0
        try:
            for r in refs:
                after = kat.werte(kat.Kontext(tag=day, isins=S.isins, method=S.method, markt=S.markt, cfg=S.cfg, stamm=S.stamm), k, r)[2]
                np.testing.assert_array_equal(before[r["id"]], after, err_msg=r["id"])
        finally:
            for isin, (c, h, lo, v) in saved.items():
                s = S.markt.series[isin]
                s.close[:], s.high[:], s.low[:], s.volume[:] = c, h, lo, v

    def test_pattern_metrics_come_from_the_same_detection_as_the_published_patterns(self):
        from traktien.aktienpilot import muster as mu

        k = kat.katalog(S.method, S.cfg)
        day = int(S.sessions[-1])
        ctx = kat.Kontext(tag=day, isins=S.isins, method=S.method, markt=S.markt, cfg=S.cfg, stamm=S.stamm)
        _, _, a = kat.werte(ctx, k, {"id": "muster_vor_ausbruch"})
        _, _, c_score = kat.werte(ctx, k, {"id": "muster_seitwaertsbasis_score"})
        _, _, b = kat.werte(ctx, k, {"id": "volumensprung"})
        cfg = mu.standard_config()
        seen = set()
        for i, isin in enumerate(ctx.isins):
            s = S.markt.series[isin]
            res = mu.am_tag(s, s.upto(day), cfg, tag=day)
            self.assertEqual(a[i], res["A"][0], isin)
            if res["C"][1] is None:
                self.assertTrue(math.isnan(c_score[i]))
            else:
                self.assertAlmostEqual(c_score[i], res["C"][1])
            self.assertEqual(b[i], {None: np.nan, "sprung": 1.0}.get(res["B"][0], 0.0) if res["B"][0] is not None else b[i])
            seen.add(a[i])
        self.assertTrue(seen <= {None, *k["muster_vor_ausbruch"].kennzahl.werte}, seen)

    def test_category_values_are_checked_against_the_catalog(self):
        from traktien.aktienpilot import regeln

        k = kat.katalog(S.method, S.cfg)
        basis = sz.regel_lineal() if hasattr(sz, "regel_lineal") else None
        if basis is None:
            from traktien.aktienpilot import vorlagen
            basis = vorlagen.alle(S.cfg)["lineal"]
        ok = dict(basis, id="r-muster-test", name="Muster-Test", filter={"kennzahl": {"id": "muster_vor_ausbruch"}, "op": "in", "werte": ["kandidat", "bestaetigt"]})
        self.assertTrue(regeln.pruefen(ok, k, S.method).gueltig, regeln.pruefen(ok, k, S.method).fehler)
        bad = dict(ok, filter={"kennzahl": {"id": "muster_vor_ausbruch"}, "op": "in", "werte": ["kandiddat"]})
        fehler = regeln.pruefen(bad, k, S.method).fehler
        self.assertTrue(any("unbekannter Wert kandiddat" in f.text for f in fehler), fehler)

    def test_indicator_values_use_shared_indicator_functions(self):
        k = kat.katalog(S.method, S.cfg)
        day = int(S.sessions[-1])
        ctx = kat.Kontext(tag=day, isins=S.isins, method=S.method, markt=S.markt, cfg=S.cfg, stamm=S.stamm)
        _, _, rsi = kat.werte(ctx, k, {"id": "rsi", "parameter": {"sitzungen": 2}})
        _, _, ma = kat.werte(ctx, k, {"id": "ma", "parameter": {"sitzungen": 50}})
        for i, isin in enumerate(ctx.isins):
            s = S.markt.series[isin]
            self.assertAlmostEqual(rsi[i], float(ind.rsi(s.close[-21:], 2)[-1]), places=10)
            self.assertAlmostEqual(ma[i], float(ind.sma(s.close, 50)[-1]), places=8)

    def test_missing_data_stays_missing(self):
        k = kat.katalog(S.method, S.cfg)
        ctx = kat.Kontext(tag=int(S.sessions[-1]), isins=S.isins + ["ZZ0000099990"], method=S.method, markt=S.markt, cfg=S.cfg, stamm=S.stamm)
        _, _, ma = kat.werte(ctx, k, {"id": "ma", "parameter": {"sitzungen": 20}})
        self.assertTrue(math.isnan(ma[-1]))
        # Zu kurze Historie: Durchschnitt über mehr Sitzungen als vorhanden
        _, _, ma_lang = kat.werte(ctx, k, {"id": "ma", "parameter": {"sitzungen": 250}})
        early = kat.Kontext(tag=int(S.sessions[100]), isins=S.isins, method=S.method, markt=S.markt, cfg=S.cfg, stamm=S.stamm)
        _, _, ma_early = kat.werte(early, k, {"id": "ma", "parameter": {"sitzungen": 250}})
        self.assertTrue(np.all(np.isnan(ma_early)))
        self.assertTrue(np.any(np.isfinite(ma_lang)))

    def test_market_filter_without_index_is_not_checkable(self):
        k = kat.katalog(S.method, S.cfg)
        stamm = {isin: dict(v, mic="XNAS", boerse="XNAS") for isin, v in S.stamm.items()}
        ctx = kat.Kontext(tag=int(S.sessions[-1]), isins=S.isins, method=S.method, markt=S.markt, cfg=S.cfg, stamm=stamm)
        _, _, mf = kat.werte(ctx, k, {"id": "marktfilter", "parameter": {"sitzungen": 200}})
        self.assertTrue(np.all(np.isnan(mf)), "ohne Indexkurse darf der Marktfilter nicht still bestehen")


if __name__ == "__main__":
    unittest.main()
