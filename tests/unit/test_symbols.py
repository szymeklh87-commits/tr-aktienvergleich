"""Kürzel ohne Kursdaten (ab 1.4.1): Börsentabelle boersen-v2, andere Schreibweisen, Suche nach ISIN.

Alle Werte sind SYNTHETISCH (erfundene Kürzel und Namen), keine Marktdaten.
"""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from traktien.config import MethodConfig
from traktien.providers.base import ListingCandidate
from traktien.providers.exchanges import load_exchange_table
from traktien.providers.identity import alternative_symbols, plausible_alternative, resolve_identity
from traktien.providers.openfigi import candidates_from_figi
from traktien.store import db, repo
from traktien.util.timeutil import parse_iso_utc

TABLE = load_exchange_table()
CFG = MethodConfig()


def figi(*records):
    return {"data": [dict(marketSector="Equity", securityType="Common Stock", **r) for r in records]}


class ExchangeTableV2Tests(unittest.TestCase):
    def test_composite_codes_point_to_no_exchange(self):
        self.assertEqual(TABLE.version, "boersen-v2")
        self.assertIsNone(TABLE.exchange_for_figi("CN"), "kanadischer Sammelcode")
        self.assertIsNone(TABLE.exchange_for_figi("GR"), "deutscher Sammelcode")
        self.assertEqual(TABLE.exchange_for_figi("CT").key, "XTSE")
        self.assertEqual(TABLE.exchange_for_figi("CV").key, "XTSX")
        self.assertEqual(TABLE.exchange_for_figi("GY").key, "XETR")
        self.assertEqual(TABLE.exchange_for_figi("GF").key, "XFRA")

    def test_venture_and_frankfurt_only_shares_get_their_real_exchange(self):
        venture = candidates_from_figi("CA0000000001", figi({"exchCode": "CN", "ticker": "TSTV"}, {"exchCode": "CV", "ticker": "TSTV"}), TABLE)
        self.assertEqual([(c.exchange_key, c.provider_symbol) for c in venture], [("XTSX", "TSTV.V")])
        result = resolve_identity("CA0000000001", "Test Venture Corp", venture, TABLE, CFG.excluded_security_types)
        self.assertEqual(result.reference.provider_symbol, "TSTV.V")

        frankfurt = candidates_from_figi("DE0000000002", figi({"exchCode": "GR", "ticker": "T46"}, {"exchCode": "GF", "ticker": "T46"}), TABLE)
        self.assertEqual([(c.exchange_key, c.provider_symbol) for c in frankfurt], [("XFRA", "T46.F")])

        toronto = candidates_from_figi("CA0000000003", figi({"exchCode": "CN", "ticker": "TST"}, {"exchCode": "CT", "ticker": "TST"}), TABLE)
        self.assertEqual([(c.exchange_key, c.provider_symbol) for c in toronto], [("XTSE", "TST.TO")])


class SymbolVariantTests(unittest.TestCase):
    def test_nordic_share_classes_get_a_hyphen(self):
        sto = TABLE.exchanges["XSTO"]
        self.assertEqual(TABLE.symbol_variants(sto, "ADDTB.ST"), ["ADDT-B.ST"])
        self.assertEqual(TABLE.symbol_variants(sto, "ATCOA.ST"), ["ATCO-A.ST"])
        self.assertEqual(TABLE.symbol_variants(sto, "VOLV-B.ST"), [], "schon mit Bindestrich")
        self.assertEqual(TABLE.symbol_variants(sto, "AB.ST"), [], "zu kurz für Kürzel plus Gattung")
        self.assertEqual(TABLE.symbol_variants(TABLE.exchanges["XCSE"], "NOVOB.CO"), ["NOVO-B.CO"])
        self.assertEqual(TABLE.symbol_variants(TABLE.exchanges["XHEL"], "KNEBV.HE"), [], "Helsinki: Gattung V ist Teil des Kürzels")

    def test_other_exchanges_get_no_guessed_spelling(self):
        self.assertEqual(TABLE.symbol_variants(TABLE.exchanges["XETR"], "BMWB.DE"), [])
        self.assertEqual(TABLE.symbol_variants(TABLE.exchanges["XSES"], "DBS.SI"), [])


class AlternativeSymbolTests(unittest.TestCase):
    def hit(self, exchange_key, symbol, security_type="Common Stock"):
        return ListingCandidate("yahoo_search", exchange_key, symbol, symbol.split(".")[0], None, "Test", security_type)

    def test_only_same_exchange_equities_in_fixed_order(self):
        hits = [
            self.hit("XFRA", "ADD1.F"),
            self.hit("XSTO", "ADDT-B.ST"),  # schon als Schreibweise vorhanden
            self.hit("XSTO", "ADDTX.ST", "ETP"),
            self.hit("XSTO", "ADDT-PREF.ST"),
            self.hit(None, "ADDT-B.XX"),
        ]
        found = alternative_symbols(TABLE, "XSTO", "ADDTB.ST", hits)
        self.assertEqual(found, [("ADDT-B.ST", "schreibweise"), ("ADDT-PREF.ST", "isin_suche")])

    def test_singapore_code_only_from_isin_search(self):
        found = alternative_symbols(TABLE, "XSES", "DBS.SI", [self.hit("XSES", "D05.SI"), self.hit("XSES", "DBS.SI")])
        self.assertEqual(found, [("D05.SI", "isin_suche")], "das bekannte, unbrauchbare Kürzel wird nicht erneut versucht")
        self.assertEqual(alternative_symbols(TABLE, "XXXX", "DBS.SI", []), [], "unbekannte Börse")

    def test_plausibility_currency_and_name(self):
        names = ["Addtech AB Class B", "ADDTECH AB-B SHS"]
        self.assertTrue(plausible_alternative("Addtech AB (publ.)", "SEK", "SEK", names)[0])
        self.assertTrue(plausible_alternative("Test plc", "GBP", "GBp", ["Test plc"])[0], "Pence und Pfund sind dieselbe Währung")
        ok, why = plausible_alternative("Addtech AB (publ.)", "EUR", "SEK", names)
        self.assertFalse(ok)
        self.assertIn("Währung", why)
        ok, why = plausible_alternative("Völlig Andere Holding", "SEK", "SEK", names)
        self.assertFalse(ok)
        self.assertIn("Name", why)
        self.assertFalse(plausible_alternative(None, "SEK", "SEK", names)[0], "ohne Namen keine Übernahme")


class RepoTests(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="kuerzel-"))
        self.conn = db.connect(self.dir / "state.sqlite")
        self.addCleanup(self.conn.close)
        self.addCleanup(shutil.rmtree, self.dir, True)
        repo.ensure_instruments(self.conn, {"SE0000000001": {"name": "Addtech AB Class B", "valid": True}})

    def save(self, symbol, exchange_key="XSTO"):
        cand = ListingCandidate("openfigi", exchange_key, symbol, symbol.split(".")[0], "SS", "ADDTECH AB-B SHS", "Common Stock")
        result = resolve_identity("SE0000000001", "Addtech AB Class B", [cand], TABLE, CFG.excluded_security_types)
        return repo.save_identity(self.conn, result, TABLE, "yahoo")

    def test_due_record_and_symbol_update(self):
        listing_id = self.save("ADDTB.ST")
        now = parse_iso_utc("2026-10-13T05:00:00Z")
        self.assertTrue(repo.symbol_alternative_due(self.conn, listing_id, now))
        repo.record_symbol_alternative(self.conn, listing_id, "ADDTB.ST", None, at="2026-10-13T05:00:00Z")
        self.assertFalse(repo.symbol_alternative_due(self.conn, listing_id, parse_iso_utc("2026-11-11T05:00:00Z")), "29 Tage später")
        self.assertTrue(repo.symbol_alternative_due(self.conn, listing_id, parse_iso_utc("2026-11-12T05:00:00Z")), "30 Tage später")

        self.assertTrue(repo.update_listing_symbol(self.conn, listing_id, "ADDT-B.ST"))
        repo.record_symbol_alternative(self.conn, listing_id, "ADDT-B.ST", "ADDT-B.ST")
        row = self.conn.execute("SELECT old_symbol, found FROM symbol_alternative WHERE listing_id = ?", (listing_id,)).fetchone()
        self.assertEqual((row["old_symbol"], row["found"]), ("ADDTB.ST", "ADDT-B.ST"), "altes Symbol laut Identitätsquelle bleibt")
        repo.record_symbol_alternative(self.conn, listing_id, "ADDT-B.ST", None)
        row = self.conn.execute("SELECT found FROM symbol_alternative WHERE listing_id = ?", (listing_id,)).fetchone()
        self.assertEqual(row["found"], "ADDT-B.ST", "ein späterer erfolgloser Versuch löscht den Fund nicht")

    def test_symbol_owned_by_another_listing_is_not_taken(self):
        listing_id = self.save("ADDTB.ST")
        repo.ensure_instruments(self.conn, {"SE0000000002": {"name": "Andere AB", "valid": True}})
        other = ListingCandidate("openfigi", "XSTO", "ANDR.ST", "ANDR", "SS", "ANDERE AB", "Common Stock")
        repo.save_identity(self.conn, resolve_identity("SE0000000002", "Andere AB", [other], TABLE, CFG.excluded_security_types), TABLE, "yahoo")
        self.assertFalse(repo.update_listing_symbol(self.conn, listing_id, "ANDR.ST"))
        symbol = self.conn.execute("SELECT provider_symbol FROM listing WHERE id = ?", (listing_id,)).fetchone()[0]
        self.assertEqual(symbol, "ADDTB.ST")

    def test_next_identity_check_keeps_the_corrected_symbol(self):
        listing_id = self.save("ADDTB.ST")
        repo.update_listing_symbol(self.conn, listing_id, "ADDT-B.ST")
        repo.record_symbol_alternative(self.conn, listing_id, "ADDTB.ST", "ADDT-B.ST")
        again = self.save("ADDTB.ST")  # Identitätsquelle liefert weiter das alte Kürzel
        self.assertEqual(again, listing_id)
        rows = self.conn.execute("SELECT provider_symbol, is_reference FROM listing").fetchall()
        self.assertEqual([(r["provider_symbol"], r["is_reference"]) for r in rows], [("ADDT-B.ST", 1)], "keine zweite Notierung mit dem alten Kürzel")


class MigrationTests(unittest.TestCase):
    def test_0006_reopens_only_toronto_and_xetra_listings_without_data(self):
        tmp = Path(tempfile.mkdtemp(prefix="migration-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        old_dir = tmp / "bis_0005"
        old_dir.mkdir()
        for file in sorted(db.MIGRATIONS_DIR.glob("*.sql")):
            if int(file.name[:4]) <= 5:
                shutil.copy(file, old_dir / file.name)
        original = db.MIGRATIONS_DIR
        db.MIGRATIONS_DIR = old_dir
        try:
            conn = db.connect(tmp / "state.sqlite")
        finally:
            db.MIGRATIONS_DIR = original
        self.addCleanup(conn.close)
        self.assertFalse(conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'symbol_alternative'").fetchone())
        cases = {
            "CA0000000001": ("XTSE", "AAG.TO", "keine_daten"),
            "DE0000000002": ("XETR", "046.DE", "keine_daten"),
            "DE0000000003": ("XETR", "SAP.DE", "ok"),
            "US0000000004": ("US", "NODATA", "keine_daten"),
        }
        at = "2026-10-13T05:00:00Z"
        for isin, (exchange_key, symbol, status) in cases.items():
            # Zustand wie unter 1.4.0 (Schema bis 0005), ohne Code von 1.4.1
            cur = conn.execute(
                "INSERT INTO instrument(isin, full_name, identity_status, identity_checked_at, created_at, updated_at) VALUES (?, ?, 'verifiziert', ?, ?, ?)",
                (isin, f"Test {isin}", at, at, at),
            )
            conn.execute(
                "INSERT INTO listing(instrument_id, provider, provider_symbol, exchange_key, is_reference, last_fetch_status, created_at, updated_at) "
                "VALUES (?, 'yahoo', ?, ?, 1, ?, ?, ?)",
                (cur.lastrowid, symbol, exchange_key, status, at, at),
            )
        self.assertEqual(db.migrate(conn)[0], 6, "0006 läuft als nächste Migration (danach ggf. neuere)")
        status = {r["isin"]: (r["identity_status"], r["identity_checked_at"]) for r in conn.execute("SELECT isin, identity_status, identity_checked_at FROM instrument")}
        self.assertEqual(status["CA0000000001"], ("offen", None))
        self.assertEqual(status["DE0000000002"], ("offen", None))
        self.assertEqual(status["DE0000000003"][0], "verifiziert")
        self.assertEqual(status["US0000000004"][0], "verifiziert", "nur Toronto und Xetra")
        self.assertTrue(conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'symbol_alternative'").fetchone())


if __name__ == "__main__":
    unittest.main()
