"""Trendqualität und Rangverlauf im zentralen Kennzahlenkatalog (Gesamtauftrag vom 31.10.2026, Abschnitte 5.3 und 6).

Prüft mit von Hand gebauten Kursreihen (SYNTHETISCH): das Beispiel aus Abschnitt 6 (ein 40-%-Sprung mit anschließendem
Verlust gegen einen gleichmäßigen Anstieg um 25 % in 20 Handelstagen) wird von jeder Trendkennzahl in die erwartete
Richtung unterschieden; Rücksetzer werden genau gezählt; Abschnitte enden am Entscheidungstag; der Rangverlauf liest die
archivierten Spitzenlisten (dieselben wie Variante B), bleibt ohne Archiv oder bei zu kurzem Archiv „nicht prüfbar“ und ist im
historischen Test über den gemeinsamen Motor wirksam.
"""

from __future__ import annotations

import math
import unittest

import numpy as np

from traktien.aktienpilot import backtest, motor, regeln, tageslauf
from traktien.aktienpilot import katalog as kat
from traktien.aktienpilot.markt import Market, Series
from traktien.config import MethodConfig

from tests.unit import ap_szenario as sz

A, B, C = "ZZ0000000A01", "ZZ0000000B02", "ZZ0000000C03"


def _reihe(isin: str, close: list[float]) -> Series:
    n = len(close)
    c = np.asarray(close, dtype=np.float64)
    days = np.arange(20000, 20000 + n, dtype=np.int64)
    return Series(isin, days, c, c * 1.01, c * 0.99, c, np.full(n, 1e5), synthetic=True)


def _sprung_und_verlust() -> list[float]:
    """Aktie A aus Abschnitt 6: ruhig, dann +40 % an einem Tag, danach zehn Tage je −2 %."""
    out, p = [], 10.0
    for k in range(30):
        p *= 1.002 if k % 2 else 0.998
        out.append(p)
    p *= 1.40
    out.append(p)
    for _ in range(10):
        p *= 0.98
        out.append(p)
    return out


def _gleichmaessig() -> list[float]:
    """Aktie B aus Abschnitt 6: 20 Handelstage gleichmäßig auf +25 % (Tagesrenditen 0,82–1,42 %), davor ruhig."""
    out, p = [], 10.0
    for k in range(21):
        p *= 1.001 if k % 2 else 0.999
        out.append(p)
    g = 1.25 ** (1 / 20)
    for k in range(20):
        p *= g * (1.003 if k % 2 else 0.997)
        out.append(p)
    return out


class Fixture:
    def __init__(self):
        self.method = MethodConfig()
        self.k = kat.katalog(self.method)
        self.series = {A: _reihe(A, _sprung_und_verlust()), B: _reihe(B, _gleichmaessig())}
        self.markt = Market(series=self.series, synthetic=True)
        self.tag = int(self.series[A].days[-1])

    def werte(self, kid: str, **parameter) -> dict[str, float]:
        ctx = kat.Kontext(tag=self.tag, isins=[A, B], method=self.method, markt=self.markt)
        _, _, v = kat.werte(ctx, self.k, {"id": kid, "parameter": parameter} if parameter else {"id": kid})
        return {A: float(v[0]), B: float(v[1])}


class TrendqualitaetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.f = Fixture()

    def test_beispiel_aus_abschnitt_6_wird_unterschieden(self):
        f = self.f
        pos = f.werte("positive_tage", sitzungen=20)
        self.assertEqual(pos[B], 20.0)
        self.assertLessEqual(pos[A], 6.0)
        mittel, median = f.werte("tagesrendite_mittel", sitzungen=20), f.werte("tagesrendite_median", sitzungen=20)
        self.assertGreater(mittel[A], 0.0, "der Sprung hebt den Durchschnitt")
        self.assertLess(median[A], 0.0, "der typische Tag von A ist ein Verlusttag")
        self.assertAlmostEqual(mittel[B], median[B], delta=0.1)
        staerke = f.werte("anstieg_je_schwankung", sitzungen=20)
        self.assertGreater(staerke[B], 10.0)
        self.assertLess(staerke[A], 1.0)
        anteil = f.werte("anteil_staerkster_tag", sitzungen=20)
        self.assertGreater(anteil[A], 80.0)
        self.assertLess(anteil[B], 10.0)
        groesste = f.werte("groesste_tagesbewegung", sitzungen=20)
        self.assertAlmostEqual(groesste[A], 40.0, places=6)
        self.assertLess(groesste[B], 1.5)
        n, tiefe = f.werte("ruecksetzer_anzahl", sitzungen=20, schwelle_pct=5), f.werte("ruecksetzer_tiefe", sitzungen=20, schwelle_pct=5)
        self.assertEqual((n[A], n[B]), (1.0, 0.0))
        self.assertAlmostEqual(tiefe[A], 100.0 * (1 - 0.98 ** 10), places=6)
        self.assertEqual(tiefe[B], 0.0)
        abschnitte = f.werte("positive_abschnitte", abschnitte=4, laenge=5)
        self.assertEqual(abschnitte[B], 100.0)
        self.assertLessEqual(abschnitte[A], 50.0)

    def test_werte_aus_den_tagesrenditen(self):
        f = self.f
        c = f.series[B].close[-21:]
        r = c[1:] / c[:-1] - 1
        self.assertAlmostEqual(f.werte("tagesrendite_mittel", sitzungen=20)[B], 100 * r.mean(), places=12)
        self.assertAlmostEqual(f.werte("tagesrendite_median", sitzungen=20)[B], 100 * np.median(r), places=12)
        lr = np.log(c[1:] / c[:-1])
        self.assertAlmostEqual(f.werte("anstieg_je_schwankung", sitzungen=20)[B], lr.sum() / (lr.std(ddof=1) * math.sqrt(20)), places=9)

    def test_ruecksetzer_genau_gezaehlt(self):
        kurse = np.array([100, 110, 104, 112, 106, 100, 113, 108], dtype=float)
        n, tiefe = kat.ruecksetzer(kurse, 0.05)
        # 110 → 104 (−5,45 %), 112 → 100 (−10,71 %, ein Rücksetzer trotz zweier Tage), 113 → 108 (−4,42 % < 5 %)
        self.assertEqual(n, 2)
        self.assertAlmostEqual(tiefe, ((1 - 104 / 110) + (1 - 100 / 112)) / 2, places=12)
        self.assertEqual(kat.ruecksetzer(kurse, 0.06)[0], 1)
        self.assertEqual(kat.ruecksetzer(kurse, 0.04), (3, ((1 - 104 / 110) + (1 - 100 / 112) + (1 - 108 / 113)) / 3))
        # gleiches Hoch beendet keinen Rücksetzer, ein offener Rücksetzer am Ende zählt
        n, tiefe = kat.ruecksetzer(np.array([100, 90, 100, 85.0]), 0.05)
        self.assertEqual(n, 1)
        self.assertAlmostEqual(tiefe, 0.15, places=12)
        self.assertEqual(kat.ruecksetzer(np.array([100, 101, 102.0]), 0.05), (0, 0.0))

    def test_abschnitte_enden_am_entscheidungstag(self):
        method = MethodConfig()
        k = kat.katalog(method)
        s = _reihe(C, [10, 11, 12, 11, 10, 12, 13])
        ctx = kat.Kontext(tag=int(s.days[-1]), isins=[C], method=method, markt=Market(series={C: s}, synthetic=True))
        _, _, v = kat.werte(ctx, k, {"id": "positive_abschnitte", "parameter": {"abschnitte": 3, "laenge": 2}})
        # Abschnitte (Indizes): 0→2 (10→12 ja), 2→4 (12→10 nein), 4→6 (10→13 ja)
        self.assertAlmostEqual(v[0], 200 / 3, places=12)
        _, _, kurz = kat.werte(ctx, k, {"id": "positive_abschnitte", "parameter": {"abschnitte": 4, "laenge": 2}})
        self.assertTrue(math.isnan(kurz[0]), "zu kurze Historie: nicht prüfbar")

    def test_konstanter_kurs_und_fehlende_historie_bleiben_offen(self):
        method = MethodConfig()
        k = kat.katalog(method)
        s = _reihe(C, [10.0] * 30)
        ctx = kat.Kontext(tag=int(s.days[-1]), isins=[C, "ZZ0000000X99"], method=method, markt=Market(series={C: s}, synthetic=True))
        self.assertTrue(math.isnan(kat.werte(ctx, k, {"id": "anstieg_je_schwankung", "parameter": {"sitzungen": 20}})[2][0]))
        self.assertTrue(math.isnan(kat.werte(ctx, k, {"id": "anteil_staerkster_tag", "parameter": {"sitzungen": 20}})[2][0]))
        self.assertEqual(kat.werte(ctx, k, {"id": "positive_tage", "parameter": {"sitzungen": 20}})[2][0], 0.0)
        self.assertTrue(math.isnan(kat.werte(ctx, k, {"id": "positive_tage", "parameter": {"sitzungen": 40}})[2][0]))
        self.assertTrue(np.isnan(kat.werte(ctx, k, {"id": "ruecksetzer_anzahl"})[2][1]), "ohne Kurse: nicht prüfbar")


class _Archiv:
    """Archiv wie ``tageslauf.RangArchiv``: Spitzenlisten je Stichtag."""

    def __init__(self, tage: dict[int, list[str]], schluessel: str):
        self.tage = tage
        self.schluessel = schluessel

    def letzte_tage(self, tag: int, n: int) -> list[int]:
        return sorted(d for d in self.tage if d <= tag)[-n:]

    def top(self, tag: int, gruppe: str, politik: str, h: int, w: int, n: int) -> list[str]:
        return list(self.tage[tag])[:n] if tageslauf.rang_archiv_schluessel(gruppe, politik, h, w) == self.schluessel else []


W, X, Y, Z = "ZZ0000000W01", "ZZ0000000X02", "ZZ0000000Y03", "ZZ0000000Z04"


class RangverlaufTests(unittest.TestCase):
    TAGE = {100: [X, Y, Z], 101: [Y, X, Z], 102: [X, Z], 103: [X, Y], 104: [Y, X]}
    RANG = {"fenster": 30, "gewicht": 60, "gruppe": "A", "politik": "native"}

    def setUp(self):
        self.k = kat.katalog(MethodConfig())
        self.archiv = _Archiv(self.TAGE, "A|native|30|60")

    def werte(self, kid: str, tag: int = 104, archiv="standard", **parameter) -> list[float]:
        ctx = kat.Kontext(tag=tag, isins=[W, X, Y, Z], method=MethodConfig(), archiv=self.archiv if archiv == "standard" else archiv)
        return [float(v) for v in kat.werte(ctx, self.k, {"id": kid, "parameter": {**self.RANG, **parameter}})[2]]

    def test_stichtage_in_den_top_k(self):
        self.assertEqual(self.werte("top_stichtage", k=10, stichtage=5), [0, 5, 4, 3])
        self.assertEqual(self.werte("top_stichtage", k=1, stichtage=5), [0, 3, 2, 0])
        self.assertEqual(self.werte("top_stichtage", k=10, stichtage=2), [0, 2, 2, 0])
        self.assertTrue(all(math.isnan(v) for v in self.werte("top_stichtage", k=10, stichtage=6)), "zu wenige Stichtage: nicht prüfbar")

    def test_serie_bis_zum_entscheidungstag(self):
        self.assertEqual(self.werte("top_serie", k=10, stichtage=5), [0, 5, 2, 0])
        self.assertEqual(self.werte("top_serie", k=1, stichtage=5), [0, 0, 1, 0])
        lang = self.werte("top_serie", k=10, stichtage=10)
        self.assertTrue(math.isnan(lang[1]), "Serie reicht bis an den Anfang des zu kurzen Archivs: Länge unbekannt")
        self.assertEqual([lang[0], lang[2], lang[3]], [0, 2, 0], "abgeschlossene Serien sind auch im kurzen Archiv bekannt")
        self.assertTrue(all(math.isnan(v) for v in self.werte("top_serie", tag=105, k=10, stichtage=5)), "Entscheidungstag nicht archiviert")

    def test_mittlerer_platz_und_platzgewinn(self):
        self.assertEqual(self.werte("rang_mittel_stichtage", stichtage=5), [11.0, 1.4, 3.4, 6.0])
        self.assertEqual(self.werte("rang_aenderung"), [0.0, -1.0, 1.0, 0.0])
        self.assertTrue(all(math.isnan(v) for v in self.werte("rang_aenderung", tag=105)))
        self.assertEqual(self.werte("rang_aenderung", tag=102), [0.0, 1.0, -10.0, 1.0])

    def test_ohne_archiv_nicht_pruefbar(self):
        for kid, p in (("top_stichtage", {"k": 10, "stichtage": 2}), ("top_serie", {"k": 10, "stichtage": 2}), ("rang_mittel_stichtage", {"stichtage": 2}),
                       ("rang_aenderung", {})):
            self.assertTrue(all(math.isnan(v) for v in self.werte(kid, archiv=None, **p)), kid)

    def test_andere_rangliste_liest_andere_liste(self):
        self.assertEqual(self.werte("top_stichtage", k=10, stichtage=5, gewicht=50), [0, 0, 0, 0])
        self.assertEqual(self.werte("top_stichtage", k=10, stichtage=5, politik="common_trend"), [0, 5, 4, 3], "10/90 … 100/0: wie „native“")

    def test_regel_mit_rangverlauf_braucht_das_archiv(self):
        method = MethodConfig()
        regel = {"schema": "tr-regel/1", "id": "r-serie", "version": 1, "name": "Serie", "kandidaten": [{"art": "universum"}],
                 "filter": {"kennzahl": {"id": "top_serie", "parameter": {"k": 10, "stichtage": 5, **self.RANG}}, "op": ">=", "wert": 3},
                 "sortierung": {"schluessel": [{"kennzahl": {"id": "rang_mittel_stichtage", "parameter": {"stichtage": 5, **self.RANG}}}]},
                 "auswahl": {"anzahl": 2}, "stop": {"initial": {"art": "prozent", "wert": 10}}}
        p = regeln.pruefen(regel, self.k, method)
        self.assertTrue(p.gueltig, [f.as_dict() for f in p.fehler])
        self.assertTrue(p.benoetigt["ranglistenarchiv"])
        self.assertTrue(any("archivierten Ranglisten" in h for h in p.hinweise), p.hinweise)
        self.assertEqual(p.regel["sortierung"]["schluessel"][0]["richtung"], "auf", "kleiner Ø Platz zuerst")


class RangverlaufImHistorischenTest(unittest.TestCase):
    """Über den gemeinsamen Motor: Die Regel liest das nachgerechnete Archiv; ohne Archiv kauft sie nichts."""

    @classmethod
    def setUpClass(cls):
        cls.S = sz.bauen(fuell=6)
        cls.K = kat.katalog(cls.S.method, cls.S.cfg)

    def _lauf(self, archiv_an: bool):
        S, K = self.S, self.K
        rang = {"fenster": 30, "gewicht": 60, "gruppe": "A", "politik": "native"}
        regel = regeln.pruefen({
            "schema": "tr-regel/1", "id": "r-stabil", "version": 1, "name": "Stabil vorn", "kandidaten": [{"art": "universum"}],
            "filter": {"kennzahl": {"id": "top_stichtage", "parameter": {"k": 3, "stichtage": 4, **rang}}, "op": ">=", "wert": 4},
            "sortierung": {"schluessel": [{"kennzahl": {"id": "rang_mittel_stichtage", "parameter": {"stichtage": 4, **rang}}}]},
            "auswahl": {"anzahl": 2}, "stop": {"initial": {"art": "prozent", "wert": 20}}}, K, S.method)
        self.assertTrue(regel.gueltig, [f.as_dict() for f in regel.fehler])
        days = [int(d) for d in S.sessions[-6:]]
        q = backtest.Kontextquelle(S.method, S.cfg, S.markt, S.instruments(days[-1]), S.stamm, 30, S.markt.fx)
        archiv = backtest.NachgerechnetesArchiv(q, [int(d) for d in S.sessions[-12:]]) if archiv_an else None
        d = motor.DepotDef("h-f-stabil-1", "Stabil vorn (historische Simulation)", "forschung", 10_000.0, days[0], 1.0,
                           (motor.StrategieDef(regel.regel["id"], regel.regel, 1.0),), None, True, "Test")
        res = backtest.laufen([d], days, q, cfg=S.cfg, method=S.method, eintraege=K, calendars=S.calendars,
                              stamm_fn=lambda i: S.stamm.get(i, {}), synthetisch=True, archiv=archiv)
        return res.depots[d.id], q, archiv, days

    def test_auswahl_folgt_dem_archiv(self):
        z, q, archiv, days = self._lauf(True)
        gekauft = {e.isin for e in z.events if e.typ == "kauf"}
        self.assertTrue(gekauft, "beständig vorn liegende Aktien werden gekauft")
        erlaubt = set()
        for day in days:
            for isin in self.S.isins:
                tage = archiv.letzte_tage(day, 4)
                if len(tage) == 4 and all(isin in archiv.top(t, "A", "native", 30, 60, 3) for t in tage):
                    erlaubt.add(isin)
        self.assertTrue(gekauft <= erlaubt, (gekauft, erlaubt))
        self.assertLessEqual(len(q._top), backtest.TOP_BEHALTEN)

    def test_ohne_archiv_kein_kauf(self):
        z, _, _, _ = self._lauf(False)
        self.assertFalse([e for e in z.events if e.typ == "kauf"], "ohne Archiv ist die Bedingung nicht prüfbar – kein Kauf")


if __name__ == "__main__":
    unittest.main()
