"""Spielgeld-Motor (Abschnitte 13, 15–19, 29): automatischer Kauf/Verkauf, Zeitregel ohne Blick zurück, Kosten, Stops mit
Kurslücke, Gewinnmitnahmen, Pause, Verlustgrenzen, Robo-Kern, Idempotenz, Speichern/Neustart und kein Echtgeldweg.
SYNTHETISCHE Daten – keine echten Kurse."""

from __future__ import annotations

import datetime as dt
import math
import re
import sqlite3
import unittest
from pathlib import Path

from traktien.aktienpilot import katalog as kat
from traktien.aktienpilot import motor, regeln, speicher
from traktien.aktienpilot.buchhaltung import replay, value
from traktien.aktienpilot.risiko import BuyRequest, Exposure, LossLimits, size_buy
from traktien.store import db
from traktien.util.timeutil import day_to_date

from tests.unit import ap_szenario as sz

S = None
K = None
WELT, GELD = "IE00B4L5Y983", "LU0290358497"


def setUpModule():
    global S, K
    S = sz.bauen()
    K = kat.katalog(S.method, S.cfg)


def regel(**over) -> dict:
    r = {
        "schema": "tr-regel/1", "id": "r-test", "version": 1, "name": "Test",
        "kandidaten": [{"art": "universum"}],
        "sortierung": {"schluessel": [{"kennzahl": {"id": "rendite", "parameter": {"fenster": 30}}}]},
        "auswahl": {"anzahl": 3},
        "stop": {"initial": {"art": "atr", "faktor": 2}},
    }
    r.update(over)
    p = regeln.pruefen(r, K, S.method)
    assert p.gueltig, p.fehler
    return p.regel


def depot(r: dict | None = None, *, art="forschung", kern=None, anteil=1.0, start_offset=60, did="d-test", strategien=None) -> motor.DepotDef:
    strategies = strategien if strategien is not None else ((motor.StrategieDef(r["id"], r, 1.0),) if r else ())
    return motor.DepotDef(did, "Test", art, 10_000.0, int(S.sessions[-start_offset]), anteil, tuple(strategies), kern, synthetisch=True)


def umwelt(D: int, **over) -> motor.Umwelt:
    kw = dict(cfg=S.cfg, method=S.method, eintraege=K, markt=S.markt, tag=D, kontext=lambda: S.kontext(D), calendars=S.calendars,
              umsatz_eur=lambda isin: 20e6, stamm=lambda isin: S.stamm.get(isin, {}), modus="backtest", synthetisch=True)
    kw.update(over)
    return motor.Umwelt(**kw)


def run(d: motor.DepotDef, z: motor.DepotZustand | None = None, days=None) -> motor.DepotZustand:
    z = z or motor.DepotZustand(d.id)
    for D in days if days is not None else [int(x) for x in S.sessions if int(x) >= d.start_tag]:
        motor.tagesschritt(d, z, umwelt(int(D)))
    return z


class AblaufTests(unittest.TestCase):
    def test_buys_after_publication_at_next_close_with_costs(self):
        r = regel()
        d = depot(r, start_offset=10)
        z = run(d, days=[int(x) for x in S.sessions[-10:-8]])
        buys = [e for e in z.events if e.typ == "kauf"]
        self.assertTrue(buys)
        decision_day = d.start_tag
        for e in buys:
            self.assertGreater(e.tag, decision_day, "nie zu einem Kurs am Entscheidungstag oder davor")
            s = S.markt.series[e.isin]
            k = s.index_of(e.tag)
            self.assertAlmostEqual(e.nutzlast["referenzkurs"], float(s.close[k]) * s.unit_factor)
            self.assertGreater(e.kurs, e.nutzlast["referenzkurs"], "Kauf zum Kurs plus Spread/Slippage/Aufschlag")
            self.assertEqual(e.gebuehren_eur, S.cfg.handelskosten.ordergebuehr_eur)
            self.assertEqual(e.nutzlast["modus"], "HISTORISCH")

    def test_same_day_is_processed_only_once(self):
        r = regel()
        d = depot(r, start_offset=10)
        z = run(d, days=[int(x) for x in S.sessions[-10:-7]])
        before = (len(z.events), len(z.orders), len(z.journal))
        res = motor.tagesschritt(d, z, umwelt(int(S.sessions[-8])))
        self.assertFalse(res.verarbeitet)
        self.assertEqual(before, (len(z.events), len(z.orders), len(z.journal)))

    def test_book_from_events_equals_running_state_and_values_add_up(self):
        r = regel()
        d = depot(r, start_offset=40)
        z = run(d)
        book = replay(d.id, z.events)
        self.assertEqual(book.pots, z.buch().pots)
        self.assertEqual(book.positions(), z.buch().positions())
        val = value(book, S.markt, int(S.sessions[-1]))
        self.assertAlmostEqual(val.total_eur, z.werte[-1]["gesamt_eur"], places=1)
        self.assertGreaterEqual(min(book.pots.values()), -1e-6, "nie negatives Guthaben")
        # Jede Bewegung genau einmal: eindeutige IDs und Nummern
        self.assertEqual(len({e.id for e in z.events}), len(z.events))
        self.assertEqual([e.seq for e in z.events], sorted(e.seq for e in z.events))

    def test_every_decision_is_explained_including_no_trade(self):
        r = regel(filter={"kennzahl": {"id": "rendite", "parameter": {"fenster": 30}}, "op": ">", "wert": 10_000})
        d = depot(r, start_offset=12)
        z = run(d)
        decisions = [j for j in z.journal if j["art"] == "entscheidung"]
        self.assertTrue(decisions)
        self.assertFalse([e for e in z.events if e.typ == "kauf"])
        self.assertTrue(all(j["text"].startswith("Nicht gehandelt") for j in decisions))
        self.assertIn("statistik", decisions[0]["daten"]["auswahl"])


class UmschichtenTests(unittest.TestCase):
    def test_sell_and_replacement_buy_in_the_same_decision(self):
        """Voll investiert, eine Aktie fällt heraus: Verkauf und Ersatzkauf entstehen in derselben Entscheidung und werden in
        derselben Sitzung ausgeführt (erst verkaufen, dann kaufen) – kein Liegenlassen des Kapitals bis zur nächsten Entscheidung."""
        slots = int(S.cfg.risiko.max_einzelaktien)  # alle Plätze belegt: ohne Freigabe wäre kein Ersatzkauf möglich
        r = regel(sortierung={"schluessel": [{"kennzahl": {"id": "rendite", "parameter": {"fenster": 5}}}]}, auswahl={"anzahl": slots},
                  verkauf={"herausfallen": {"aktiv": True, "puffer": 0}}, zeitplan={"intervall": "taeglich"})
        d = depot(r, start_offset=45)
        z = run(d)
        rotations = [j for j in z.journal if j["art"] == "entscheidung" and j["daten"].get("verkaeufe") and j["daten"].get("kaeufe")]
        self.assertTrue(rotations, "mindestens eine Umschichtung in einer Entscheidung")
        for j in rotations:
            sold = {v["order"] for v in j["daten"]["verkaeufe"]}
            bought = {k["order"] for k in j["daten"]["kaeufe"]}
            sessions = {o.sitzung for o in z.orders if o.id in sold | bought}
            self.assertEqual(len(sessions), 1, "Verkauf und Ersatzkauf in derselben Ausführungssitzung")
        rejected = [a["grund"] for j in z.journal if j["art"] == "entscheidung" for a in j["daten"].get("abgelehnt", [])]
        self.assertFalse([g for g in rejected if "Einzelaktien" in g], "frei werdende Plätze zählen in derselben Entscheidung")
        book = replay(d.id, z.events)
        self.assertGreaterEqual(min(book.pots.values()), -1e-6, "nie negatives Guthaben")
        # in jeder Sitzung zuerst verkauft, dann gekauft
        by_day: dict[int, list[str]] = {}
        for e in z.events:
            if e.typ in ("kauf", "verkauf"):
                by_day.setdefault(e.tag, []).append(e.typ)
        for typs in by_day.values():
            self.assertEqual(typs, sorted(typs, key=lambda t: 0 if t == "verkauf" else 1))


class StopUndLueckeTests(unittest.TestCase):
    def test_gap_below_stop_fills_at_open_not_at_stop(self):
        luecke = sz.isin(5)
        r = regel(kandidaten=[{"art": "isins", "isins": [luecke]}], auswahl={"anzahl": 1}, verkauf={"herausfallen": {"aktiv": False}})
        n = len(S.sessions)
        d = depot(r, start_offset=40)  # Kauf vor der Lücke (Sitzung n − 30)
        z = run(d, days=[int(x) for x in S.sessions[n - 40:n - 25]])
        stop_sales = [e for e in z.events if e.typ == "verkauf" and e.nutzlast.get("grund") == "stop"]
        self.assertEqual(len(stop_sales), 1)
        sale = stop_sales[0]
        s = S.markt.series[luecke]
        k = s.index_of(sale.tag)
        self.assertEqual(sale.tag, int(S.sessions[n - 30]))
        self.assertAlmostEqual(sale.nutzlast["referenzkurs"], float(s.open[k]))
        self.assertEqual(sale.nutzlast["hinweis"], "Kurslücke: Eröffnung unter dem Stop")
        order = next(o for o in z.orders if o.id == sale.order_id)
        self.assertTrue(order.schutz)

    def test_trailing_stop_never_moves_down(self):
        r = regel(stop={"initial": {"art": "atr", "faktor": 2}, "trailing": {"art": "prozent", "wert": 10}}, auswahl={"anzahl": 2})
        d = depot(r, start_offset=60)
        stops: dict[str, list[float]] = {}
        z = motor.DepotZustand(d.id)
        for D in [int(x) for x in S.sessions[-60:]]:
            motor.tagesschritt(d, z, umwelt(D))
            for key, pos in z.positionen.items():
                if pos.stop is not None:
                    stops.setdefault(key + str(pos.eroeffnet), []).append(pos.stop)
        self.assertTrue(stops)
        for seq in stops.values():
            self.assertEqual(seq, sorted(seq))


class SplitTests(unittest.TestCase):
    def test_split_doubles_shares_without_artificial_gain(self):
        aktie = sz.isin(1)
        s = S.markt.series[aktie]
        n = len(S.sessions)
        split_day = int(S.sessions[n - 20])
        saved = s.splits
        s.splits = ((split_day, 2.0),)  # Kurse vor dem Split waren doppelt so hoch wie die bereinigte Reihe
        try:
            r = regel(kandidaten=[{"art": "isins", "isins": [aktie]}], auswahl={"anzahl": 1}, stop={"initial": {"art": "prozent", "wert": 30}},
                      verkauf={"herausfallen": {"aktiv": False}})
            d = depot(r, start_offset=30)
            z = run(d, days=[int(x) for x in S.sessions[n - 30:n - 15]])
            buy = next(e for e in z.events if e.typ == "kauf")
            k = s.index_of(buy.tag)
            self.assertAlmostEqual(buy.nutzlast["referenzkurs"], float(s.close[k]) * 2.0, msg="Kauf zum damals gehandelten Kurs")
            splits = [e for e in z.events if e.typ == "split"]
            self.assertEqual(len(splits), 1)
            self.assertEqual(z.buch().qty(aktie, "r-test"), buy.stueck * 2)
            values = {w["tag"]: w["gesamt_eur"] for w in z.werte}
            before = values[int(S.sessions[n - 21])]
            after = values[split_day]
            move = float(s.close[s.index_of(split_day)]) / float(s.close[s.index_of(int(S.sessions[n - 21]))])
            position = buy.stueck * 2 * float(s.close[s.index_of(split_day)])
            self.assertLess(abs((after - before) - position * (1 - 1 / move)), 1.0, "Wertänderung am Splittag nur aus der Kursbewegung")
            pos = next(iter(z.positionen.values()))
            self.assertLess(pos.stop, float(s.close[s.index_of(split_day)]), "Stop auf die neue Kursbasis umgerechnet")
        finally:
            s.splits = saved


class GewinnmitnahmeMotorTests(unittest.TestCase):
    def test_ladder_sells_each_stage_once_from_position_gain(self):
        stark = sz.isin(2)
        gm = {"art": "leiter", "stufen": [{"schwelle_pct": 2, "anteil_pct": 50}, {"schwelle_pct": 4, "anteil_pct": 50}]}
        r = regel(kandidaten=[{"art": "isins", "isins": [stark]}], auswahl={"anzahl": 1}, stop={"initial": {"art": "prozent", "wert": 40}},
                  verkauf={"herausfallen": {"aktiv": False}, "gewinnmitnahme": gm, "wiedereinstieg": {"art": "pause", "pause_sitzungen": 250}})
        d = depot(r, start_offset=50)
        z = run(d)
        buys = [e for e in z.events if e.typ == "kauf" and e.isin == stark]
        sells = [e for e in z.events if e.typ == "verkauf" and e.isin == stark]
        self.assertEqual(len(buys), 1)
        self.assertEqual(len(sells), 2, [ (e.tag, e.stueck, e.nutzlast.get('grund')) for e in sells])
        self.assertEqual(sum(e.stueck for e in sells), buys[0].stueck)
        self.assertTrue(all(e.nutzlast["grund"] == "gewinnmitnahme" for e in sells))
        tp_orders = [o for o in z.orders if o.grund == "gewinnmitnahme"]
        self.assertEqual(sorted(s for o in tp_orders for s in o.stufen), ["0", "1"])
        for o in tp_orders:
            self.assertGreater(o.sitzung, o.datentag, "Gewinnmitnahme wird erst nach der Schlussprüfung ausgeführt")


class SchutzTests(unittest.TestCase):
    def test_pause_blocks_buys_but_not_sells(self):
        r = regel(auswahl={"anzahl": 3})
        d = depot(r, start_offset=30)
        z = run(d, days=[int(x) for x in S.sessions[-30:-20]])
        held_before = z.buch().positions()
        self.assertTrue(held_before)
        z.kaeufe_pausiert = True
        paused_from = int(S.sessions[-20])
        z = run(d, z, days=[int(x) for x in S.sessions[-20:]])
        # vor der Pause beauftragte Käufe werden noch ausgeführt („Pause“ ist nicht „offene Käufe stornieren“), danach keine neuen
        self.assertFalse([o for o in z.orders if o.richtung == "kauf" and o.datentag >= paused_from])
        rejected = [x["grund"] for j in z.journal if j["art"] == "entscheidung" for x in j["daten"]["abgelehnt"]]
        self.assertTrue(any("pausiert" in (g or "") for g in rejected))

    def test_close_stage_sells_active_positions_but_never_the_core(self):
        r = regel(auswahl={"anzahl": 3})
        d = depot(r, art="pilot", anteil=0.3, kern=motor.KernDef({WELT: 0.7, GELD: 0.3}), start_offset=30)
        z = run(d, days=[int(x) for x in S.sessions[-30:-20]])
        self.assertTrue(any(p.zuordnung != "kern" for p in z.positionen.values()))
        z.verlust.stage = "schliessen"
        z.verlust.paused_until_release = True
        z = run(d, z, days=[int(x) for x in S.sessions[-20:-15]])
        book = z.buch()
        active = {i: q for i, owners in book.holdings.items() for o, q in owners.items() if o != "kern" and q > 0}
        self.assertEqual(active, {}, "alle aktiven Positionen geschlossen")
        self.assertGreater(book.qty(WELT, "kern"), 0, "ETF-Kern bleibt")

    def test_close_request_from_the_app_sells_active_positions_once_and_keeps_buys_paused(self):
        r = regel(auswahl={"anzahl": 3}, zeitplan={"intervall": "taeglich"})
        d = depot(r, art="pilot", anteil=0.3, kern=motor.KernDef({WELT: 0.7, GELD: 0.3}), start_offset=30)
        z = run(d, days=[int(x) for x in S.sessions[-30:-20]])
        self.assertTrue(any(p.zuordnung != "kern" for p in z.positionen.values()))
        z.schliessen_angefordert = True
        z.kaeufe_pausiert = True
        z = run(d, z, days=[int(x) for x in S.sessions[-20:-15]])
        self.assertFalse(z.schliessen_angefordert, "einmalig")
        book = z.buch()
        active = {i: q for i, owners in book.holdings.items() for o, q in owners.items() if o != "kern" and q > 0}
        self.assertEqual(active, {}, "alle aktiven Positionen geschlossen")
        self.assertGreater(book.qty(WELT, "kern"), 0, "ETF-Kern bleibt")
        sold = [o for o in z.orders if o.grund == "steuerung:schliessen"]
        self.assertTrue(sold and all(o.richtung == "verkauf" for o in sold))
        buys_after = [o for o in z.orders if o.richtung == "kauf" and o.zuordnung != "kern" and o.datentag >= int(S.sessions[-20])]
        self.assertEqual(buys_after, [], "keine neuen aktiven Käufe, solange pausiert")
        self.assertTrue(any(j["art"] == "steuerung" and "Schließung" in j["text"] for j in z.journal))

    def test_central_risk_limits_bind_every_buy(self):
        r = regel(auswahl={"anzahl": 1})
        d = depot(r, start_offset=10)
        z = run(d, days=[int(x) for x in S.sessions[-10:-8]])
        o = next(o for o in z.orders if o.richtung == "kauf")
        limits = o.begruendung["risiko"]["grenzen"]
        self.assertTrue({"risiko_je_trade", "je_aktie", "guthaben", "liquiditaet", "orderwert"} <= set(limits))
        self.assertLessEqual(o.stueck, min(limits.values()))


class KernTests(unittest.TestCase):
    def test_buy_and_hold_benchmark_invests_once(self):
        d = depot(None, art="vergleich", anteil=0.0, kern=motor.KernDef({WELT: 1.0}, 5.0, False), start_offset=40, did="v-welt")
        z = run(d)
        buys = [e for e in z.events if e.typ == "kauf"]
        self.assertEqual(len(buys), 1)
        self.assertFalse([e for e in z.events if e.typ == "verkauf"])
        self.assertLess(z.buch().pots["kern"], buys[0].kurs, "Rest kleiner als ein Anteil")

    def test_core_rebalances_only_beyond_threshold(self):
        d = depot(None, art="vergleich", anteil=0.0, kern=motor.KernDef({WELT: 0.5, GELD: 0.5}, 5.0, True), start_offset=120, did="v-kern")
        z = run(d)
        trades = [e for e in z.events if e.typ in ("kauf", "verkauf")]
        self.assertGreaterEqual(len(trades), 2)
        for w in z.werte[-1:]:
            book = z.buch()
            val = value(book, S.markt, w["tag"])
            share = val.positions_eur.get(WELT, 0.0) / max(1e-9, val.core_eur)
            self.assertLess(abs(share - 0.5) * 100, 5.0 + 1.5)


class SpeichernTests(unittest.TestCase):
    def test_restart_from_database_gives_same_result(self):
        r = regel(auswahl={"anzahl": 3}, verkauf={"gewinnmitnahme": {"art": "ganz", "schwelle_pct": 3}})
        d = depot(r, start_offset=40)
        days = [int(x) for x in S.sessions[-40:]]
        straight = run(d, days=days)
        conn = db.connect(":memory:")
        speicher.depot_anlegen(conn, d, modus="DEMO", test_id="t1")
        z = motor.DepotZustand(d.id)
        for k, D in enumerate(days):
            if k % 7 == 3:
                z = speicher.zustand_laden(conn, d.id)  # Neustart: Zustand nur aus der Datenbank
            res = motor.tagesschritt(d, z, umwelt(D))
            with db.Transaction(conn):
                speicher.speichern(conn, d, z, res, lauf_id=f"l{k}", datenstand="test")
        reloaded = speicher.zustand_laden(conn, d.id)
        self.assertEqual([(e.typ, e.isin, e.stueck, round(e.betrag_eur, 6)) for e in straight.events],
                         [(e.typ, e.isin, e.stueck, round(e.betrag_eur, 6)) for e in reloaded.events])
        self.assertAlmostEqual(straight.werte[-1]["gesamt_eur"], reloaded.werte[-1]["gesamt_eur"], places=2)
        # Ein zweites Speichern desselben Tages scheitert an der Datenbank (Primärschlüssel ap_tageslauf)
        with self.assertRaises(sqlite3.IntegrityError):
            conn.execute("INSERT INTO ap_tageslauf(depot_id, tag, lauf_id, verarbeitet_am) VALUES (?, ?, 'x', 'x')", (d.id, days[-1]))


class KeinEchtgeldTests(unittest.TestCase):
    def test_database_rejects_real_money_modes(self):
        conn = db.connect(":memory:")
        for modus in ("LIVE", "ECHT"):
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute("INSERT INTO ap_depot(id, name, art, modus, definition_json, definition_sha, test_id, start_tag, angelegt_am) "
                             "VALUES ('x', 'x', 'pilot', ?, '{}', 'x', 't', 1, 'x')", (modus,))
        with self.assertRaises(ValueError):
            speicher.depot_anlegen(conn, depot(regel()), modus="LIVE", test_id="t")

    def test_risk_manager_refuses_real_money_even_if_released(self):
        exp = Exposure(reference_eur=1e6, complete=True, active_cap_eur=1e6, active_eur=0, free_cash_eur=1e6)
        req = BuyRequest("ZZ0000000001", "s1", "aktie", "X", 10.0, 1.0, 9.0, 1e9, 10.0, None, 0, None, real_money=True, released=True)
        decision = size_buy(S.cfg, exp, req, LossLimits(), paused=False)
        self.assertFalse(decision.allowed)
        self.assertIn("Echtgeld", decision.reason)

    def test_no_broker_or_live_endpoint_in_the_robo_code(self):
        root = Path(__file__).resolve().parents[2] / "backend" / "traktien" / "aktienpilot"
        pattern = re.compile(r"(api\.alpaca|paper-api|ib_async|etoro|traderepublic|/v2/orders|LIVE\")", re.IGNORECASE)
        for path in root.glob("*.py"):
            text = path.read_text(encoding="utf-8")
            self.assertIsNone(pattern.search(text), f"{path.name}: möglicher Echtgeld-Orderweg")
        self.assertNotIn("LIVE", S.cfg.__class__.__module__ and __import__("traktien.aktienpilot.config", fromlist=["MODES"]).MODES)

    def test_demo_and_real_data_never_mix(self):
        r = regel()
        d = depot(r, start_offset=5)
        res = motor.tagesschritt(d, motor.DepotZustand(d.id), umwelt(int(S.sessions[-5]), synthetisch=False))
        self.assertFalse(res.verarbeitet)
        self.assertIn("nie im selben Depot", res.grund)


if __name__ == "__main__":
    unittest.main()
