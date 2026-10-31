"""Eingänge aus der App (Gesamtauftrag, Abschnitte 4, 7A.5, 29.3, 31): Prüfung im Eingangs-Workflow, Ablage, verbindliche
Übernahme im täglichen Lauf genau einmal, eigene Regel im eigenen Forschungsdepot, neue Version = neuer Test, Pause und
Fortsetzen, Schutz vor Wiederholung und Manipulation. SYNTHETISCHE Daten – keine echten Kurse."""

from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from traktien.aktienpilot import eingang as ein
from traktien.aktienpilot import katalog as kat
from traktien.aktienpilot import regeln, speicher, vorlagen
from traktien.aktienpilot.config import load_aktienpilot_config
from traktien.config import MethodConfig
from traktien.jobs.kursaktualisierung import neue_kennung
from traktien.store import db
from traktien.util import crypto

REPO = Path(__file__).resolve().parents[2]
KEY = crypto.derive_key("Test-Eingang-2026!", b"testsalz-eingang", 1000)
NOW = dt.datetime(2026, 10, 31, 9, 0, tzinfo=dt.timezone.utc)
D = 20756  # Datenstichtag (Tageszahl)


def _setup():
    method = MethodConfig()
    cfg = load_aktienpilot_config()
    return method, cfg, kat.katalog(method, cfg)


def _regel(cfg, name="Meine Platz-1-Regel", version=1, **over):
    r = json.loads(json.dumps(vorlagen.alle(cfg)["platz1_leiter"]))
    r.update(id="r-meine-platz1", version=version, name=name, herkunft={"vorlage": "platz1-sammler-1"})
    r.update(over)
    return r


def _eingang(art, inhalt, when=NOW):
    kennung = neue_kennung(when)
    return kennung, ein.baue(kennung, art, inhalt, KEY, erstellt=when)


class AnnahmeTests(unittest.TestCase):
    def setUp(self):
        self.method, self.cfg, self.k = _setup()

    def test_valid_rule_is_accepted_and_normalized(self):
        kennung, text = _eingang("regel_testen", {"regel": _regel(self.cfg)})
        e, blob = ein.annehmen(text, kennung, KEY, self.k, self.method, now=NOW + dt.timedelta(minutes=2))
        self.assertEqual(e.art, "regel_testen")
        self.assertEqual(e.regel["id"], "r-meine-platz1")
        self.assertEqual(e.regel["verkauf"]["gewinnmitnahme"]["art"], "leiter")
        self.assertTrue(blob.startswith(b"TRA1"))

    def test_rejections_with_reason_codes(self):
        bad_rule = _regel(self.cfg)
        bad_rule["stop"] = {"initial": None}
        cases = {
            "regel_ungueltig": _eingang("regel_testen", {"regel": bad_rule}),
            "art_unbekannt": _eingang("echtgeld_kaufen", {}),
            "inhalt_ungueltig": _eingang("pausieren", {"egal": 1}),
        }
        for code, (kennung, text) in cases.items():
            with self.assertRaises(ein.EingangFehler) as ctx:
                ein.annehmen(text, kennung, KEY, self.k, self.method, now=NOW)
            self.assertEqual(ctx.exception.code, code)
        # zu alt (Wiederholung), falscher Schlüssel, vertauschte Kennung, Unsinn
        kennung, text = _eingang("pausieren", {})
        with self.assertRaises(ein.EingangFehler) as ctx:
            ein.annehmen(text, kennung, KEY, self.k, self.method, now=NOW + dt.timedelta(minutes=21))
        self.assertEqual(ctx.exception.code, "zu_alt")
        other = crypto.derive_key("anderer Schlüssel", b"anderes-salz-123", 1000)
        with self.assertRaises(ein.EingangFehler) as ctx:
            ein.annehmen(text, kennung, other, self.k, self.method, now=NOW)
        self.assertEqual(ctx.exception.code, "nicht_entschluesselbar")
        with self.assertRaises(ein.EingangFehler) as ctx:
            ein.annehmen(text, neue_kennung(NOW), KEY, self.k, self.method, now=NOW)
        self.assertEqual(ctx.exception.code, "nicht_entschluesselbar")
        with self.assertRaises(ein.EingangFehler):
            ein.annehmen("kein base64 !", kennung, KEY, self.k, self.method, now=NOW)
        with self.assertRaises(ein.EingangFehler):
            ein.annehmen(text, "../../etc", KEY, self.k, self.method, now=NOW)

    def test_prune_keeps_only_recent_own_files(self):
        fresh, old = neue_kennung(NOW), neue_kennung(NOW - dt.timedelta(days=31))
        names = [f"eingang/{fresh}.bin", f"ergebnis/{fresh}.bin", f"eingang/{old}.bin", "README.md", "eingang/fremd.bin"]
        self.assertEqual(sorted(ein.prune_names(names, NOW)), sorted([f"eingang/{old}.bin", "README.md", "eingang/fremd.bin"]))


class VerarbeitungTests(unittest.TestCase):
    def setUp(self):
        self.method, self.cfg, self.k = _setup()
        self.conn = db.connect(":memory:")
        db.migrate(self.conn)

    def tearDown(self):
        self.conn.close()

    def run_items(self, items, now=NOW + dt.timedelta(hours=8)):
        with db.Transaction(self.conn):
            return ein.verarbeiten(self.conn, [(k, ein._b64(t)) for k, t in items], key=KEY, eintraege=self.k, method=self.method, cfg=self.cfg, D=D,
                                   synthetisch=True, now=now)

    def test_rule_starts_own_research_depot_exactly_once(self):
        item = _eingang("regel_testen", {"regel": _regel(self.cfg)})
        counts = self.run_items([item])
        self.assertEqual(counts, {"neu": 1, "verarbeitet": 1, "abgelehnt": 0, "bekannt": 0})
        own = ein.eigene_depots(self.conn)
        self.assertEqual([d.id for d, _ in own], ["e-meine-platz1-v1"])
        d, info = own[0]
        self.assertEqual(d.art, "forschung")
        self.assertEqual(d.start_tag, D)
        self.assertEqual(info["modus"], "DEMO")
        self.assertEqual(speicher.regel_laden(self.conn, "r-meine-platz1", 1)["name"], "Meine Platz-1-Regel")
        # dieselbe Kennung erneut (Wiederholung, zweiter Lauf am selben Tag): nichts passiert
        self.assertEqual(self.run_items([item]), {"neu": 0, "verarbeitet": 0, "abgelehnt": 0, "bekannt": 1})
        self.assertEqual(len(ein.eigene_depots(self.conn)), 1)

    def test_new_version_archives_old_test_and_same_version_with_other_content_is_rejected(self):
        self.run_items([_eingang("regel_testen", {"regel": _regel(self.cfg)})])
        changed = _regel(self.cfg)
        changed["auswahl"] = {"anzahl": 3}
        counts = self.run_items([_eingang("regel_testen", {"regel": changed}, NOW + dt.timedelta(minutes=1))])
        self.assertEqual(counts["abgelehnt"], 1, "Versionen sind unveränderlich")
        reason = self.conn.execute("SELECT grund FROM ap_eingang WHERE status = 'abgelehnt'").fetchone()[0]
        self.assertIn("neue Version", reason)
        v2 = _regel(self.cfg, version=2)
        v2["auswahl"] = {"anzahl": 3}
        self.run_items([_eingang("regel_testen", {"regel": v2}, NOW + dt.timedelta(minutes=2))])
        rows = dict(self.conn.execute("SELECT id, status FROM ap_depot WHERE id LIKE 'e-%'").fetchall())
        self.assertEqual(rows, {"e-meine-platz1-v1": "archiviert", "e-meine-platz1-v2": "aktiv"})
        self.run_items([_eingang("regel_beenden", {"regel_id": "r-meine-platz1"}, NOW + dt.timedelta(minutes=3))])
        self.assertEqual(ein.eigene_depots(self.conn), [])
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM ap_depot WHERE id LIKE 'e-%'").fetchone()[0], 2, "nichts gelöscht")

    def test_pause_resume_and_cancel_open_buys_of_the_pilot(self):
        from traktien.aktienpilot import motor
        from traktien.aktienpilot.ausfuehrung import SimOrder

        pilot = motor.DepotDef("demo-pilot", "Pilot", "pilot", 10_000.0, D - 5, 0.3, (), None, True)
        with db.Transaction(self.conn):
            speicher.depot_anlegen(self.conn, pilot, modus="DEMO", test_id="t", jetzt=NOW)
            z = motor.DepotZustand(pilot.id)
            order = SimOrder(id="o-1", depot_id=pilot.id, zuordnung="r-x", isin="DE0007164600", richtung="kauf", stueck=3, grund="regel:auswahl",
                             profil="FOLGETAG-SCHLUSS", datentag=D, sitzung=D + 1, preispunkt="close", frueheste=None, ablauf=None, reserviert_eur=500.0)
            z.orders.append(order)
            self.conn.execute("INSERT INTO ap_order(id, depot_id, zuordnung, isin, richtung, stueck, status, datentag, sitzung, daten_json, aktualisiert_am) "
                              "VALUES (?, ?, ?, ?, ?, ?, 'offen', ?, ?, ?, ?)", (order.id, pilot.id, order.zuordnung, order.isin, "kauf", 3, D, D + 1,
                                                                             json.dumps(order.as_dict()), "x"))
            speicher.nachtrag(self.conn, pilot.id, z, [], NOW)
        self.run_items([_eingang("pausieren", {})])
        self.assertTrue(speicher.zustand_laden(self.conn, pilot.id).kaeufe_pausiert)
        self.run_items([_eingang("offene_kaeufe_stornieren", {}, NOW + dt.timedelta(minutes=1))])
        z = speicher.zustand_laden(self.conn, pilot.id)
        self.assertEqual([o.status for o in z.orders], ["storniert"])
        self.assertEqual(self.conn.execute("SELECT status FROM ap_order WHERE id = 'o-1'").fetchone()[0], "storniert")
        self.run_items([_eingang("fortsetzen", {}, NOW + dt.timedelta(minutes=2))])
        self.assertFalse(speicher.zustand_laden(self.conn, pilot.id).kaeufe_pausiert)
        texts = [r[0] for r in self.conn.execute("SELECT text FROM ap_protokoll WHERE depot_id = ? ORDER BY id", (pilot.id,))]
        self.assertEqual(len(texts), 3)
        self.assertTrue(all("Eingang aus der App" in t for t in texts))

    def test_close_positions_and_new_test(self):
        from traktien.aktienpilot import motor, tageslauf

        pilot = motor.DepotDef("demo-pilot", "Pilot", "pilot", 10_000.0, D - 5, 0.3, (), None, True)
        with db.Transaction(self.conn):
            speicher.depot_anlegen(self.conn, pilot, modus="DEMO", test_id="t", jetzt=NOW)
        self.run_items([_eingang("positionen_schliessen", {})])
        z = speicher.zustand_laden(self.conn, pilot.id)
        self.assertTrue(z.schliessen_angefordert and z.kaeufe_pausiert)
        self.assertEqual(ein.testnummer(self.conn), 1)
        before = {d.id: speicher.definition_json(d) for d in tageslauf.depots_definieren(self.cfg, self.method, self.k, D, synthetisch=True,
                                                                                        testnummer=ein.testnummer(self.conn))}
        self.run_items([_eingang("neuer_test", {}, NOW + dt.timedelta(minutes=1))])
        self.assertEqual(ein.testnummer(self.conn), 2)
        after = {d.id: speicher.definition_json(d) for d in tageslauf.depots_definieren(self.cfg, self.method, self.k, D, synthetisch=True,
                                                                                       testnummer=ein.testnummer(self.conn))}
        for did in ("demo-pilot", "demo-v-welt", "demo-v-kern"):
            self.assertNotEqual(before[did], after[did], f"{did}: neue Definition → neuer Test")
        self.assertEqual(before["demo-f-lineal"], after["demo-f-lineal"], "Forschungsdepots laufen weiter")

    def test_tampered_or_foreign_input_is_rejected_and_recorded(self):
        kennung, text = _eingang("pausieren", {})
        blob = bytearray(ein._b64(text))
        blob[-5] ^= 0xFF
        with db.Transaction(self.conn):
            counts = ein.verarbeiten(self.conn, [(kennung, bytes(blob)), ("../boese", b"x")], key=KEY, eintraege=self.k, method=self.method, cfg=self.cfg, D=D,
                                     synthetisch=True, now=NOW)
        self.assertEqual(counts["abgelehnt"], 1)
        row = self.conn.execute("SELECT status, grund FROM ap_eingang").fetchone()
        self.assertEqual(row[0], "abgelehnt")
        self.assertIn("nicht entschlüsseln", row[1])


class EinrichtungTests(unittest.TestCase):
    def setUp(self):
        self.method, self.cfg, self.k = _setup()

    def test_profile_rule_is_transparent_monotonic_and_capped_by_loss_tolerance(self):
        from traktien.aktienpilot import profil

        t = profil.tabelle()
        self.assertEqual(len(t), 21)
        self.assertTrue(all(len(row) == 5 for row in t))
        for v in range(5):
            col = [t[p][v] for p in range(21)]
            self.assertEqual(col, sorted(col), "mehr Punkte → nie weniger Welt-Anteil")
        self.assertAlmostEqual(t[20][4], 1.0)
        self.assertAlmostEqual(t[0][4], 0.3)
        for p in range(21):
            for v in range(4):
                self.assertLessEqual(t[p][v] * profil.WELT_RUECKGANG * 100, profil.VERLUST_PCT[v] + 1e-9, "Rückgangsszenario ≤ verkraftbarer Rückgang")
                self.assertGreaterEqual(t[p][v], 0.1)
                self.assertAlmostEqual((t[p][v] * 100) % 5, 0.0)
        p = profil.ableiten({"horizont": 4, "liquiditaet": 4, "verlust": 4, "risiko": 4, "erfahrung": 4})
        self.assertEqual((p["welt"], p["geldmarkt"], p["punkte"]), (1.0, 0.0, 20))
        with self.assertRaises(profil.ProfilFehler):
            profil.ableiten({"horizont": 5, "liquiditaet": 0, "verlust": 0, "risiko": 0, "erfahrung": 0})
        with self.assertRaises(profil.ProfilFehler):
            profil.ableiten({"horizont": 1})

    def test_setup_input_starts_new_pilot_test_with_profile_capital_and_active_share(self):
        from traktien.aktienpilot import tageslauf

        conn = db.connect(":memory:")
        db.migrate(conn)
        antworten = {"horizont": 3, "liquiditaet": 3, "verlust": 2, "risiko": 2, "erfahrung": 2}
        kennung, text = _eingang("pilot_einrichten", {"startkapital_eur": 25_000, "antworten": antworten, "aktiver_anteil": 0.2})
        bad = _eingang("pilot_einrichten", {"startkapital_eur": 25_000, "antworten": antworten, "aktiver_anteil": 0.5}, NOW + dt.timedelta(minutes=1))
        with db.Transaction(conn):
            counts = ein.verarbeiten(conn, [(kennung, ein._b64(text)), (bad[0], ein._b64(bad[1]))], key=KEY, eintraege=self.k, method=self.method,
                                     cfg=self.cfg, D=D, synthetisch=True, now=NOW + dt.timedelta(hours=1))
        self.assertEqual((counts["verarbeitet"], counts["abgelehnt"]), (1, 1))
        setup = ein.einrichtung(conn)
        self.assertEqual((setup["startkapital_eur"], setup["aktiver_anteil"], setup["profil"]["welt"]), (25_000.0, 0.2, 0.4))
        defs = {d.id: d for d in tageslauf.depots_definieren(self.cfg, self.method, self.k, D, synthetisch=True, einrichtung=setup)}
        pilot = defs["demo-pilot"]
        self.assertEqual((pilot.startkapital_eur, pilot.aktiver_anteil), (25_000.0, 0.2))
        self.assertEqual(sorted(pilot.kern.ziele.values()), [0.4, 0.6])
        self.assertEqual(defs["demo-v-welt"].startkapital_eur, 25_000.0, "Vergleich mit identischem Startkapital")
        self.assertEqual(defs["demo-v-kern"].kern.ziele, pilot.kern.ziele)
        self.assertEqual(defs["demo-f-lineal"].startkapital_eur, float(self.cfg.depot.demo_startkapital_eur), "Forschungsdepots bleiben vergleichbar")
        default = {d.id: d for d in tageslauf.depots_definieren(self.cfg, self.method, self.k, D, synthetisch=True)}
        self.assertNotEqual(speicher.definition_json(default["demo-pilot"]), speicher.definition_json(pilot), "geänderte Definition → neuer Test")
        conn.close()


class EingangsBefehlTests(unittest.TestCase):
    def test_cli_writes_input_and_encrypted_result_and_prints_no_content(self):
        method, cfg, k = _setup()
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            descriptor = crypto.crypto_descriptor(KEY)
            (tmp / "crypto.json").write_text(json.dumps(descriptor), encoding="utf-8")
            passphrase = "Test-Eingang-2026!"
            # Schlüssel aus Passphrase und Deskriptor (wie im Workflow)
            key = crypto.verify_descriptor(descriptor, passphrase)
            now = dt.datetime.now(dt.timezone.utc)
            kennung = neue_kennung(now)
            text = ein.baue(kennung, "regel_testen", {"regel": _regel(cfg)}, key, erstellt=now)
            env = dict(os.environ, PYTHONPATH=str(REPO / "backend"), DATA_PASSPHRASE=passphrase, NUTZLAST=text, LOG_LEVEL="WARNING")
            out = subprocess.run([sys.executable, "-m", "traktien", "spielgeld-eingang", "--kennung", kennung, "--schluessel", str(tmp / "crypto.json"),
                                  "--kanal", "ordner", "--ordner", str(tmp / "ablage"), "--arbeit", str(tmp / "arbeit")],
                                 cwd=REPO, env=env, capture_output=True, text=True, timeout=300, check=True)
            self.assertIn("angenommen", out.stdout)
            self.assertNotIn("Platz-1", out.stdout)
            self.assertNotIn("r-meine-platz1", out.stdout)
            self.assertTrue((tmp / "ablage" / "eingang" / f"{kennung}.bin").exists())
            result = json.loads(crypto.unpack((tmp / "ablage" / "ergebnis" / f"{kennung}.bin").read_bytes(), key, f"ergebnis/{kennung}"))
            self.assertEqual(result["status"], "angenommen")
            self.assertEqual(result["regel"], "r-meine-platz1@1")
            self.assertEqual(ein.aus_ordner(tmp / "ablage")[0][0], kennung)
            # abgelehnt: nur Ergebnis, kein Eingang
            bad = neue_kennung(now)
            env["NUTZLAST"] = ein.baue(bad, "echtgeld_kaufen", {}, key, erstellt=now)
            out = subprocess.run([sys.executable, "-m", "traktien", "spielgeld-eingang", "--kennung", bad, "--schluessel", str(tmp / "crypto.json"),
                                  "--kanal", "ordner", "--ordner", str(tmp / "ablage"), "--arbeit", str(tmp / "arbeit2")],
                                 cwd=REPO, env=env, capture_output=True, text=True, timeout=300, check=True)
            self.assertIn("abgelehnt (art_unbekannt)", out.stdout)
            self.assertFalse((tmp / "ablage" / "eingang" / f"{bad}.bin").exists())
            self.assertTrue((tmp / "ablage" / "ergebnis" / f"{bad}.bin").exists())
            del method, k


if __name__ == "__main__":
    unittest.main()
