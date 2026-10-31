"""Strategielabor (Gesamtauftrag vom 31.10.2026, Abschnitte 12, 13, 15) – SYNTHETISCHE Daten.

Prüft: Konfiguration mit Grenzen; Varianten sind gewöhnliche gültige Regeln in fester Reihenfolge; Zeiträume getrennt und
lückenlos, Walk-forward-Training direkt vor der Prüfung; die Auswahl nutzt nur Entwicklung und Validierung (veränderte
Testergebnisse ändern nichts), der Walk-forward wählt nur aus dem Training; Robustheitsregeln mit Grund; ein Lauf über den
gemeinsamen Motor ist reproduzierbar, jedes Depot handelt nur in seinem Zeitraum; Ablage, Prüfsumme, DEMO/PAPER getrennt und
Vorwärtsdepots für die vorgeschlagenen Varianten.
"""

from __future__ import annotations

import copy
import datetime as dt
import unittest

from traktien.aktienpilot import backtest, labor, regeln
from traktien.aktienpilot import katalog as kat
from traktien.store import db

from tests.unit import ap_szenario as sz

NOW = dt.datetime(2026, 10, 31, 6, 0, tzinfo=dt.timezone.utc)


def roh(**aenderung) -> dict:
    raw = {
        "version": "labor-test", "startkapital_eur": 10000,
        "zeitraum": {"tage": 40, "entwicklung_pct": 50, "validierung_pct": 25, "walk_forward": {"training": 10, "pruefung": 5}},
        "bewertung": {"rendite": 30, "abstand_welt": 20, "rueckgang": 20, "rendite_je_rueckgang": 20, "gewinnquote": 10},
        "robustheit": {"mindest_kaeufe": 1, "max_rueckgang_pct": 30, "nachbarn": True},
        "auswahl": {"finalisten": 3, "vorwaerts": 2},
        "uebernahme": {"modus": "nur_vorschlagen"},
        "familien": {"gleichmaessig": {"schwankung_min": [1, 2], "abschnitte_min": [60]}, "kurz": {"fenster": [3, 5], "haltedauer": [5]},
                     "lang": {"fenster": [60], "mindesthaltedauer": [5]}},
    }
    for k, v in aenderung.items():
        raw[k] = v
    return raw


class KonfigurationTests(unittest.TestCase):
    def test_ausgelieferte_konfiguration_gilt(self):
        cfg = labor.load_labor_config()
        self.assertEqual(cfg.modus, "nur_vorschlagen", "Standard: nur vorschlagen")
        self.assertEqual(set(cfg.familien), set(labor.FAMILIEN), "alle acht Familien A–H aus Abschnitt 12")

    def test_ungueltige_konfiguration_mit_grund(self):
        for raw, text in (
            (roh(uebernahme={"modus": "sofort"}), "uebernahme.modus"),
            (roh(familien={"raketen": {"x": [1]}}), "unbekannte Familien"),
            (roh(familien={"kurz": {"fenster": [3]}}), "braucht genau die Parameter"),
            (roh(familien={"kurz": {"fenster": [3, 3], "haltedauer": [5]}}), "verschiedene Zahlen"),
            (roh(familien={"kurz": {"fenster": [0], "haltedauer": [5]}}), "verschiedene Zahlen"),
            (roh(zeitraum={"tage": 300, "entwicklung_pct": 50, "validierung_pct": 25, "walk_forward": {"training": 10, "pruefung": 5}}), "20 bis 250"),
            (roh(zeitraum={"tage": 40, "entwicklung_pct": 70, "validierung_pct": 25, "walk_forward": {"training": 10, "pruefung": 5}}), "Testzeitraum"),
        ):
            with self.assertRaises(labor.LaborFehler) as cm:
                labor.parse_config(raw)
            self.assertIn(text, str(cm.exception))


class VariantenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.S = sz.bauen(fuell=4)
        cls.K = kat.katalog(cls.S.method, cls.S.cfg)

    def test_alle_familien_ergeben_gueltige_regeln(self):
        cfg = labor.load_labor_config()
        vs = labor.varianten(cfg, self.K, self.S.method, self.S.cfg.depot.ausfuehrungsprofil)
        erwartet = 1
        self.assertEqual(len(vs), sum(len(list(__import__("itertools").product(*g.values()))) for g in cfg.familien.values()))
        for v in vs:
            p = regeln.pruefen(v.regel, self.K, self.S.method)
            self.assertTrue(p.gueltig, v.id)
            self.assertEqual(p.regel, v.regel, "gespeichert wie geprüft")
            self.assertEqual(regeln.fingerabdruck(v.regel), v.fingerabdruck)
            self.assertRegex(v.id, r"^r-lab-[a-h]-")
            self.assertEqual(v.regel["herkunft"], {"vorlage": cfg.version})
        self.assertEqual([v.id for v in vs], [v.id for v in labor.varianten(cfg, self.K, self.S.method, self.S.cfg.depot.ausfuehrungsprofil)], "feste Reihenfolge")
        self.assertEqual({v.buchstabe for v in vs}, set("ABCDEFGH"))
        self.assertTrue(erwartet)
        # Familie E nutzt den Rangverlauf (Archiv), D und E steigen nur über Stops/Haltedauer aus
        e = next(v for v in vs if v.familie == "stabil_vorausbruch")
        self.assertTrue(regeln.pruefen(e.regel, self.K, self.S.method).benoetigt["ranglistenarchiv"])
        self.assertFalse(e.regel["verkauf"]["herausfallen"]["aktiv"])

    def test_nachbarn_im_gitter(self):
        cfg = labor.parse_config(roh(familien={"platz1": {"fenster_bis": [10, 20, 30], "mindestens": [2, 5]}}))
        vs = labor.varianten(cfg, self.K, self.S.method, "FOLGETAG-SCHLUSS")
        by = {(v.parameter["fenster_bis"], v.parameter["mindestens"]): v for v in vs}
        nb = {(w.parameter["fenster_bis"], w.parameter["mindestens"]) for w in labor.nachbarn(by[(20, 2)], vs, cfg)}
        self.assertEqual(nb, {(10, 2), (30, 2), (20, 5)})
        nb = {(w.parameter["fenster_bis"], w.parameter["mindestens"]) for w in labor.nachbarn(by[(10, 5)], vs, cfg)}
        self.assertEqual(nb, {(20, 5), (10, 2)}, "nur ein Gitterschritt in genau einem Parameter")


class ZeitraumTests(unittest.TestCase):
    def test_getrennt_lueckenlos_und_walk_forward(self):
        cfg = labor.parse_config(roh())
        tage = list(range(1000, 1040))
        zr = labor.zeitraeume(tage, cfg)
        e, v, t = zr[0], zr[1], zr[2]
        self.assertEqual((e.art, v.art, t.art), ("entwicklung", "validierung", "test"))
        self.assertEqual(list(e.tage) + list(v.tage) + list(t.tage), tage, "lückenlos, ohne Überlappung, in zeitlicher Folge")
        self.assertEqual((len(e.tage), len(v.tage), len(t.tage)), (20, 10, 10))
        folds = [z for z in zr if z.faltung is not None]
        self.assertEqual(len(folds), 2 * 6)
        for k in range(1, 7):
            tr = next(z for z in folds if z.faltung == k and z.art == "training")
            pr = next(z for z in folds if z.faltung == k and z.art == "pruefung")
            self.assertEqual(tage.index(pr.tage[0]), tage.index(tr.tage[-1]) + 1, "Prüfung direkt nach dem Training")
            self.assertEqual((len(tr.tage), len(pr.tage)), (10, 5))
        with self.assertRaises(labor.LaborFehler):
            labor.zeitraeume(tage[:12], cfg)


def _m(rendite: float, kaeufe: int = 5, rueckgang: float = 5.0, quote: float | None = 50.0, welt: float = 1.0) -> dict:
    return {"rendite_pct": rendite, "abstand_welt_pp": rendite - welt, "max_rueckgang_pct": rueckgang, "rendite_je_rueckgang": rendite / max(rueckgang, 1.0),
            "gewinnquote_pct": quote, "kaeufe": kaeufe, "verkaeufe": 2, "kosten_eur": 3.0, "profitfaktor": None}


class AuswahlTests(unittest.TestCase):
    """``auswerten`` ohne Motor: nur Entwicklung und Validierung wählen, Test und Walk-forward-Prüfung nicht."""

    @classmethod
    def setUpClass(cls):
        S = sz.bauen(fuell=2)
        cls.K = kat.katalog(S.method, S.cfg)
        cls.cfg = labor.parse_config(roh(familien={"platz1": {"fenster_bis": [10, 20, 30], "mindestens": [2, 5]}, "kurz": {"fenster": [3], "haltedauer": [5]}},
                                         auswahl={"finalisten": 3, "vorwaerts": 2}))
        cls.vs = labor.varianten(cls.cfg, cls.K, S.method, "FOLGETAG-SCHLUSS")
        cls.zr = labor.zeitraeume(list(range(2000, 2040)), cls.cfg)

    def metriken(self, dev: dict[str, dict], val: dict[str, dict] | None = None, test_wert: float = 1.0, pruef_wert: float = 1.0) -> dict:
        out = {}
        for z in self.zr:
            for v in self.vs:
                if z.art == "entwicklung":
                    out[(z.schluessel, v.id)] = dev.get(v.id, _m(1.0))
                elif z.art == "validierung":
                    out[(z.schluessel, v.id)] = (val or {}).get(v.id, _m(1.0))
                elif z.art == "test":
                    out[(z.schluessel, v.id)] = _m(test_wert * (1 + self.vs.index(v)))
                elif z.art == "training":
                    out[(z.schluessel, v.id)] = _m(1.0 + self.vs.index(v))  # letzte Variante im Training am besten
                else:
                    out[(z.schluessel, v.id)] = _m(pruef_wert * (10 - self.vs.index(v)))
        return out

    def welt(self) -> dict:
        return {z.schluessel: _m(1.0) for z in self.zr}

    def test_gruende_und_reihenfolge(self):
        ids = [v.id for v in self.vs]  # a-10-2, a-10-5, a-20-2, a-20-5, a-30-2, a-30-5, g-3-5
        dev = {ids[0]: _m(8.0, kaeufe=0), ids[1]: _m(9.0, rueckgang=45.0), ids[2]: _m(-1.0), ids[3]: _m(6.0), ids[4]: _m(5.0), ids[5]: _m(4.0),
               ids[6]: _m(7.0)}
        # g-3-5 hat keine Nachbarn (eine Variante in der Familie): kein Einzeltreffer-Test
        res = labor.auswerten(self.vs, self.zr, self.metriken(dev), self.welt(), self.cfg)
        st = {v["id"]: (v["status"], v["grund"]) for v in res["varianten"]}
        self.assertIn("zu wenige Käufe", st[ids[0]][1])
        self.assertIn("über der Grenze", st[ids[1]][1])
        self.assertEqual(st[ids[2]][1], "Rendite nach Kosten nicht positiv")
        self.assertEqual(sum(1 for s, _ in st.values() if s in ("validiert", "vorwaerts")), 3, "drei Finalisten, alle validiert")
        self.assertEqual(st[ids[5]][0], "nicht_ausgewaehlt")
        self.assertEqual(len(res["vorwaerts"]), 2)
        self.assertTrue(all("test" in v for v in res["varianten"] if v["status"] in ("validiert", "vorwaerts")))
        self.assertTrue(all("test" not in v for v in res["varianten"] if v["status"] not in ("validiert", "vorwaerts")), "Test nur für validierte")

    def test_einzeltreffer_ohne_positive_nachbarn(self):
        ids = [v.id for v in self.vs]
        dev = {i: _m(-2.0) for i in ids}
        dev[ids[3]] = _m(9.0)  # a-20-5: Nachbarn a-10-5, a-30-5, a-20-2 alle negativ
        res = labor.auswerten(self.vs, self.zr, self.metriken(dev), self.welt(), self.cfg)
        st = {v["id"]: (v["status"], v["grund"]) for v in res["varianten"]}
        self.assertEqual(st[ids[3]][0], "verworfen")
        self.assertIn("Einzeltreffer", st[ids[3]][1])

    def test_validierung_verwirft_und_test_waehlt_nicht(self):
        ids = [v.id for v in self.vs]
        dev = {i: _m(3.0 + k) for k, i in enumerate(ids)}
        val = {ids[6]: _m(-1.0)}  # beste der Entwicklung fällt in der Validierung durch
        a = labor.auswerten(self.vs, self.zr, self.metriken(dev, val), self.welt(), self.cfg)
        st = {v["id"]: v["status"] for v in a["varianten"]}
        self.assertEqual(st[ids[6]], "validierung_verfehlt")
        # beliebig andere Testergebnisse ändern weder Status noch Vorschlag
        b = labor.auswerten(self.vs, self.zr, self.metriken(dev, val, test_wert=-50.0), self.welt(), self.cfg)
        self.assertEqual([(v["id"], v["status"]) for v in a["varianten"]], [(v["id"], v["status"]) for v in b["varianten"]])
        self.assertEqual(a["vorwaerts"], b["vorwaerts"])
        self.assertNotEqual([v.get("test") for v in a["varianten"]], [v.get("test") for v in b["varianten"]], "Test wird berichtet")

    def test_walk_forward_waehlt_nur_im_training(self):
        dev = {v.id: _m(3.0) for v in self.vs}
        a = labor.auswerten(self.vs, self.zr, self.metriken(dev), self.welt(), self.cfg)
        b = labor.auswerten(self.vs, self.zr, self.metriken(dev, pruef_wert=-3.0), self.welt(), self.cfg)
        wa, wb = a["walk_forward"]["faltungen"], b["walk_forward"]["faltungen"]
        self.assertEqual([f["gewaehlt"] for f in wa], [f["gewaehlt"] for f in wb], "die Prüfergebnisse ändern die Wahl nicht")
        self.assertTrue(all(f["gewaehlt"] == self.vs[-1].id for f in wa), "beste Wertung im Training")
        self.assertGreater(a["walk_forward"]["zusammenfassung"]["mittel_rendite_pct"], b["walk_forward"]["zusammenfassung"]["mittel_rendite_pct"])
        self.assertEqual(a["walk_forward"]["zusammenfassung"]["faltungen"], 6)

    def test_parameterwirkung(self):
        ids = [v.id for v in self.vs]
        dev = {i: _m(1.0) for i in ids}
        dev[ids[0]], dev[ids[1]] = _m(5.0), _m(7.0)  # fenster_bis 10 besser
        res = labor.auswerten(self.vs, self.zr, self.metriken(dev), self.welt(), self.cfg)
        fb = next(w for w in res["parameterwirkung"] if w["familie"] == "A" and w["parameter"] == "fenster_bis")
        self.assertEqual([(x["wert"], x["median_rendite_pct"], x["varianten"]) for x in fb["werte"]], [(10, 6.0, 2), (20, 1.0, 2), (30, 1.0, 2)])


class LaufTests(unittest.TestCase):
    """Ein Laborlauf über den gemeinsamen Motor auf synthetischen Kursen."""

    @classmethod
    def setUpClass(cls):
        cls.S = S = sz.bauen(fuell=6)
        cls.K = kat.katalog(S.method, S.cfg)
        cls.cfg = labor.parse_config(roh())
        cls.tage = [int(d) for d in S.sessions[-40:]]

    def lauf(self):
        S = self.S
        q = backtest.Kontextquelle(S.method, S.cfg, S.markt, S.instruments(self.tage[-1]), S.stamm, 90, S.markt.fx)
        archiv = backtest.NachgerechnetesArchiv(q, [int(d) for d in S.sessions[-60:]])
        return labor.durchfuehren(quelle=q, archiv=archiv, tage=self.tage, cfg=self.cfg, ap_cfg=S.cfg, method=S.method, eintraege=self.K,
                                  calendars=S.calendars, stamm_fn=lambda i: S.stamm.get(i, {}), synthetisch=True, datenstand="test", erstellt=NOW)

    def test_lauf_reproduzierbar_und_vollstaendig(self):
        a = self.lauf()
        self.assertEqual(a["schema"], "tr-labor/1")
        self.assertEqual((a["modus"], a["synthetisch"]), ("DEMO", True))
        self.assertEqual(len(a["varianten"]), 5)
        self.assertEqual(a["kennzahlen"]["depots"], 15 * 6, "je Zeitraum alle Varianten und der Welt-ETF")
        self.assertEqual(sum(a["zaehlung"].values()), 5)
        for v in a["varianten"]:
            self.assertIn(v["status"], ("verworfen", "nicht_ausgewaehlt", "validierung_verfehlt", "validiert", "vorwaerts"))
            self.assertTrue(v["grund"] or v["status"] in ("validiert",), v)
            self.assertIn("wertung", v["entwicklung"])
        self.assertTrue(all(a["vergleich"][k] is not None for k in a["vergleich"]), "Welt-ETF je Zeitraum")
        self.assertTrue(any("Rückschau" in h for h in a["hinweise"]))
        self.assertEqual(a["uebernahme"]["modus"], "nur_vorschlagen")
        b = self.lauf()
        strip = lambda p: {k: v for k, v in p.items() if k not in ("kennzahlen",)}
        self.assertEqual(strip(a), strip(b), "gleiche Daten und Konfiguration → gleiches Ergebnis")

    def test_depots_handeln_nur_im_eigenen_zeitraum(self):
        S = self.S
        q = backtest.Kontextquelle(S.method, S.cfg, S.markt, S.instruments(self.tage[-1]), S.stamm, 90, S.markt.fx)
        vs = labor.varianten(self.cfg, self.K, S.method, S.cfg.depot.ausfuehrungsprofil)
        v = next(x for x in vs if x.familie == "kurz")
        d = backtest.motor.DepotDef("x", "x", "forschung", 10_000.0, self.tage[5], 1.0, (backtest.motor.StrategieDef(v.regel["id"], v.regel, 1.0),), None, True)
        res = backtest.laufen([d], self.tage, q, cfg=S.cfg, method=S.method, eintraege=self.K, calendars=S.calendars, stamm_fn=lambda i: S.stamm.get(i, {}),
                              synthetisch=True, bis={"x": self.tage[15]})
        z = res.depots["x"]
        self.assertTrue(z.werte)
        self.assertTrue(all(self.tage[5] <= int(w["tag"]) <= self.tage[15] for w in z.werte))
        self.assertTrue(all(self.tage[5] <= int(e.tag) <= self.tage[15] for e in z.events), "keine Buchung nach dem Zeitraum")


class SignalpruefungTests(unittest.TestCase):
    """Abschnitte 5.2, 5.3, 6: Folgerenditen der Signale gegen das Mittel aller Aktien desselben Tages – von Hand nachgerechnet."""

    def test_folgerendite_gegen_das_tagesmittel(self):
        import numpy as np

        S = sz.bauen(fuell=6)
        K = kat.katalog(S.method, S.cfg)
        q = backtest.Kontextquelle(S.method, S.cfg, S.markt, S.instruments(int(S.sessions[-1])), S.stamm, 90, S.markt.fx)
        archiv = backtest.NachgerechnetesArchiv(q, [int(d) for d in S.sessions[-40:]])
        p = labor.Signalpruefung(q, archiv, K)
        tage = [int(d) for d in S.sessions[-30:-27]]
        for D in tage:
            p(D)
        self.assertEqual(sorted(p.tage), tage)
        res = {(e["signal"], e["horizont"]): e for e in p.auswerten()["ergebnisse"]}
        self.assertEqual(set(res), {(s[0], n) for s in labor.SIGNALE for n in labor.HORIZONTE})
        # „gleichmäßig“ von Hand: Mittel der Folgerenditen der Treffer minus Mittel aller Aktien, je Tag, dann gemittelt
        n = 5
        diffs = []
        for D in tage:
            folge = {}
            for isin in p.isins[D]:
                s = S.markt.series[isin]
                k = s.index_of(D)
                folge[isin] = s.close[k + n] / s.close[k] - 1
            treffer = p.tage[D]["gleichmaessig"]
            self.assertTrue(treffer, "der gleichmäßig steigende Wert erfüllt das Signal")
            diffs.append(np.mean([folge[i] for i in treffer]) - np.mean(list(folge.values())))
        e = res[("gleichmaessig", n)]
        self.assertEqual(e["tage"], 3)
        self.assertAlmostEqual(e["mittel_ueberschuss_pp"], round(100 * float(np.mean(diffs)), 2), places=6)
        self.assertEqual(e["trefferquote_pct"], round(100.0 * sum(1 for x in diffs if x > 0) / 3, 1))
        # ohne Folgekurse (letzter Tag der Reihe) kein Fall
        late = labor.Signalpruefung(q, archiv, K)
        late(int(S.sessions[-1]))
        self.assertTrue(all(x["tage"] == 0 for x in late.auswerten()["ergebnisse"]))


class AblageTests(unittest.TestCase):
    def test_speichern_lesen_und_vorwaertsdepots(self):
        S = sz.bauen(fuell=2)
        conn = db.connect(":memory:")
        db.migrate(conn)
        regel = copy.deepcopy(next(iter(__import__("traktien.aktienpilot.vorlagen", fromlist=["alle"]).alle(S.cfg).values())))
        regel["id"] = "r-lab-c-2-66"
        payload = {"schema": "tr-labor/1", "id": "lab-000000000001", "version": "labor-test", "modus": "DEMO", "datentag": "2026-10-30",
                   "uebernahme": {"modus": "nur_vorschlagen", "vorwaerts": ["r-lab-c-2-66"]},
                   "varianten": [{"id": "r-lab-c-2-66", "regel": dict(regel, name="Labor C: Gleichmäßig")}, {"id": "r-lab-g-3-5"}]}
        labor.speichern(conn, payload, NOW)
        self.assertEqual(labor.neuester(conn, "DEMO"), payload)
        self.assertIsNone(labor.neuester(conn, "PAPER"), "DEMO und PAPER nie gemischt")
        defs = labor.vorwaerts_depots(conn, S.cfg, synthetisch=True, start_tag=20000)
        self.assertEqual([d.id for d in defs], ["demo-l-lab-c-2-66"])
        self.assertTrue(labor.ist_labordepot(defs[0].id))
        self.assertEqual(defs[0].strategien[0].regel["id"], "r-lab-c-2-66")
        self.assertEqual(defs[0].name, "Labor vorwärts: C: Gleichmäßig")
        self.assertEqual(labor.vorwaerts_depots(conn, S.cfg, synthetisch=False, start_tag=20000), [])
        # Prüfsumme schützt vor stiller Beschädigung
        conn.execute("UPDATE ap_labor SET sha256 = 'x'")
        with self.assertRaises(labor.LaborFehler):
            labor.neuester(conn, "DEMO")
        conn.close()


class AblageTestsKanal(unittest.TestCase):
    """Workflow „Spielgeld-Labor“ → Ablage → täglicher Lauf: nur verschlüsselt, an die Kennung gebunden, passender Modus, Datentag
    nicht nach dem Stichtag, jedes Ergebnis genau einmal; ältere Ablagen werden beim Ablegen entfernt."""

    KEY = __import__("traktien.util.crypto", fromlist=["derive_key"]).derive_key("Test-Labor-2026!", b"testsalz-labor-1", 1000)

    def ergebnis(self, nr: int, *, modus: str = "PAPER", datentag: str = "2026-10-30", synthetisch: bool = False) -> dict:
        return {"schema": labor.SCHEMA, "id": f"lab-{nr:012x}", "version": "labor-test", "modus": modus, "synthetisch": synthetisch, "datentag": datentag,
                "erstellt_utc": f"2026-10-31T0{nr % 10}:00:00Z", "uebernahme": {"modus": "nur_vorschlagen", "vorwaerts": []}, "varianten": []}

    def ablage(self, root, payload, key=None):
        from pathlib import Path

        path = Path(root) / labor.ORDNER / f"{labor.dateiname(payload)}.bin"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(labor.exportieren(payload, key or self.KEY))
        return path

    def test_uebernehmen_genau_einmal_und_nur_gueltiges(self):
        import tempfile

        from traktien.util import crypto
        from traktien.util.timeutil import date_to_day

        conn = db.connect(":memory:")
        db.migrate(conn)
        D = date_to_day(dt.date(2026, 10, 30))
        with tempfile.TemporaryDirectory() as root:
            self.ablage(root, self.ergebnis(1))
            self.ablage(root, self.ergebnis(2, modus="DEMO"))  # falscher Modus
            self.ablage(root, self.ergebnis(3, datentag="2026-11-02"))  # nach dem Stichtag
            self.ablage(root, self.ergebnis(4), key=crypto.derive_key("anderer Schlüssel", b"anderes-salz-123", 1000))  # fremder Schlüssel
            klar = self.ergebnis(5)
            (__import__("pathlib").Path(root) / labor.ORDNER / f"{labor.dateiname(klar)}.bin").write_bytes(crypto.pack(labor.json_dumps(klar), None, "labor/x"))
            vertauscht = self.ergebnis(6)
            blob = labor.exportieren(self.ergebnis(7), self.KEY)  # Inhalt von 7 unter dem Namen von 6
            (__import__("pathlib").Path(root) / labor.ORDNER / f"{labor.dateiname(vertauscht)}.bin").write_bytes(blob)
            items = labor.aus_ordner(root)
            self.assertEqual(len(items), 6)
            res = labor.uebernehmen(conn, items, key=self.KEY, synthetisch=False, D=D, now=NOW)
            self.assertEqual(res, {"neu": 1, "bekannt": 0, "abgelehnt": 5})
            self.assertEqual(labor.neuester(conn, "PAPER")["id"], f"lab-{1:012x}")
            self.assertEqual(labor.uebernehmen(conn, items, key=self.KEY, synthetisch=False, D=D, now=NOW)["bekannt"], 1, "jedes Ergebnis genau einmal")
        conn.close()

    def test_prune_behaelt_die_neuesten_drei(self):
        names = [f"labor/{labor.dateiname(self.ergebnis(n))}.bin" for n in range(1, 6)] + ["fremd.txt", "labor/kaputt.bin"]
        drop = labor.prune_names(names, NOW)
        self.assertEqual(sorted(set(names) - set(drop)), sorted(names[2:5]))
        self.assertIn("fremd.txt", drop)

    def test_echte_kurse_nie_ohne_schluessel(self):
        with self.assertRaises(labor.LaborFehler):
            labor.exportieren(self.ergebnis(1), None)
        self.assertTrue(labor.exportieren(self.ergebnis(1, modus="DEMO", synthetisch=True), None).startswith(b"TRA1"), "DEMO ohne Passphrase möglich")


class _OhneAbruf:
    """Kursanbieter, der nichts liefert (Kursreihen kommen im Test aus dem Szenario)."""

    def fetch_history(self, *args, **kwargs):
        from traktien.providers.base import NoDataError

        raise NoDataError("Test ohne Abruf")


class TaeglicherLaufTests(unittest.TestCase):
    """Der tägliche Lauf startet für die vorgeschlagenen Varianten eigene Spielgelddepots und beendet ältere Vorschläge."""

    def test_vorgeschlagene_varianten_laufen_vorwaerts_und_alte_enden(self):
        import types

        from traktien.aktienpilot import speicher, tageslauf

        S = sz.bauen(fuell=4)
        K = kat.katalog(S.method, S.cfg)
        conn = db.connect(":memory:")
        db.migrate(conn)
        vs = labor.varianten(labor.parse_config(roh()), K, S.method, S.cfg.depot.ausfuehrungsprofil)
        metas = [types.SimpleNamespace(isin=a.isin, name=a.name, instrument_type="stammaktie", mic="XETR", exchange_key="XETR", currency=a.waehrung,
                                       ticker=None) for a in S.aktien]

        def ergebnis(pid: str, vorwaerts: list[str]) -> dict:
            return {"schema": labor.SCHEMA, "id": pid, "version": "labor-test", "modus": "DEMO", "datentag": "2026-10-29",
                    "uebernahme": {"modus": "nur_vorschlagen", "vorwaerts": vorwaerts},
                    "varianten": [{"id": v.id, "regel": v.regel} for v in vs]}

        def tag(D: int, run: str) -> dict:
            return tageslauf.ausfuehren(conn, cfg=S.cfg, method=S.method, comp=S.comp(D), metas=metas, D=D, fx=S.markt.fx, calendars=S.calendars,
                                        provider=_OhneAbruf(), run_id=run, now=NOW, key=None, snapshot_id=f"s-{D}", data_mode="demo",
                                        reihen={i: S.markt.series[i] for i in S.isins})

        labor.speichern(conn, ergebnis("lab-000000000001", [vs[0].id, vs[1].id]), NOW)
        D1, D2 = int(S.sessions[-3]), int(S.sessions[-2])
        tag(D1, "t1")
        aktiv = {d.id: d for d, _info in speicher.depots(conn, nur_aktive=True)}
        a, b = (f"demo-l-{vs[0].id.removeprefix('r-')}", f"demo-l-{vs[1].id.removeprefix('r-')}")
        self.assertIn(a, aktiv)
        self.assertIn(b, aktiv)
        self.assertTrue(aktiv[a].name.startswith("Labor vorwärts:"))
        self.assertEqual(aktiv[a].strategien[0].regel, vs[0].regel, "die validierte Variante unverändert")
        start_b = conn.execute("SELECT start_tag FROM ap_depot WHERE id = ?", (b,)).fetchone()[0]
        # neuer Laborlauf schlägt nur noch die zweite Variante vor: erste beendet (archiviert), zweite läuft unverändert weiter
        labor.speichern(conn, ergebnis("lab-000000000002", [vs[1].id]), NOW + dt.timedelta(hours=1))
        tag(D2, "t2")
        status = dict(conn.execute("SELECT id, status FROM ap_depot WHERE id IN (?, ?)", (a, b)).fetchall())
        self.assertEqual(status[a], "archiviert")
        self.assertNotEqual(status[b], "archiviert")
        self.assertEqual(conn.execute("SELECT start_tag FROM ap_depot WHERE id = ?", (b,)).fetchone()[0], start_b, "kein Neustart")
        # Spielgeld-Stand: Laborergebnis für die App, Vorwärtsdepot als Forschungsdepot
        stand_id = conn.execute("SELECT id FROM ap_stand ORDER BY erstellt_am DESC LIMIT 1").fetchone()[0]
        self.assertTrue(stand_id)
        conn.close()

    def test_abgelegtes_ergebnis_wird_im_taeglichen_lauf_uebernommen(self):
        """Kette Workflow → Ablage → täglicher Lauf: das abgelegte Ergebnis wird übernommen und startet die Vorwärtsdepots."""
        import tempfile
        import types
        from pathlib import Path

        from traktien.aktienpilot import speicher, tageslauf

        S = sz.bauen(fuell=4)
        K = kat.katalog(S.method, S.cfg)
        conn = db.connect(":memory:")
        db.migrate(conn)
        vs = labor.varianten(labor.parse_config(roh()), K, S.method, S.cfg.depot.ausfuehrungsprofil)
        metas = [types.SimpleNamespace(isin=a.isin, name=a.name, instrument_type="stammaktie", mic="XETR", exchange_key="XETR", currency=a.waehrung,
                                       ticker=None) for a in S.aktien]
        D = int(S.sessions[-2])
        payload = {"schema": labor.SCHEMA, "id": "lab-0000000000aa", "version": "labor-test", "modus": "DEMO", "synthetisch": True,
                   "datentag": backtest.datum(int(S.sessions[-3])), "erstellt_utc": "2026-10-31T05:00:00Z",
                   "uebernahme": {"modus": "nur_vorschlagen", "vorwaerts": [vs[0].id]}, "varianten": [{"id": v.id, "regel": v.regel} for v in vs]}
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / labor.ORDNER / f"{labor.dateiname(payload)}.bin"
            path.parent.mkdir(parents=True)
            path.write_bytes(labor.exportieren(payload, None))
            summary = tageslauf.ausfuehren(conn, cfg=S.cfg, method=S.method, comp=S.comp(D), metas=metas, D=D, fx=S.markt.fx, calendars=S.calendars,
                                           provider=_OhneAbruf(), run_id="t1", now=NOW, key=None, snapshot_id="s1", data_mode="demo",
                                           reihen={i: S.markt.series[i] for i in S.isins}, laborergebnisse=lambda: labor.aus_ordner(Path(root)))
        self.assertEqual(summary["labor"], {"neu": 1, "bekannt": 0, "abgelehnt": 0})
        aktiv = {d.id for d, _ in speicher.depots(conn, nur_aktive=True)}
        self.assertIn(f"demo-l-{vs[0].id.removeprefix('r-')}", aktiv)
        conn.close()


if __name__ == "__main__":
    unittest.main()
