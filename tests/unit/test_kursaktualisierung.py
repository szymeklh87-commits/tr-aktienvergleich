"""Kursaktualisierung einzelner Aktien auf Wunsch der App (ab 1.21): Anfrage prüfen, nur diese Kurse abrufen, in Teilen
(sichtbare zuerst) verschlüsselt liefern. Ohne Netz: DEMO-Anbieter, lokaler Ordner bzw. lokales Git-Repository als Kanal."""

from __future__ import annotations

import base64
import datetime as dt
import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from traktien.jobs import kursaktualisierung as ka
from traktien.providers.demo import DemoProvider, build_demo_universe
from traktien.providers.yahoo import parse_quote_response
from traktien.util import crypto
from traktien.util.timeutil import UTC

KEY = crypto.derive_key("Testpassphrase-nur-fuer-Tests", b"0123456789abcdef", iterations=1000)
OTHER = crypto.derive_key("andere Passphrase", b"0123456789abcdef", iterations=1000)
NOW = dt.datetime(2026, 10, 31, 12, 0, tzinfo=UTC)
ISIN_RE = re.compile(r"\b[A-Z]{2}[A-Z0-9]{9}[0-9]\b")


def demo_values(n: int) -> list[tuple[str, str]]:
    return [(i.isin, i.symbol) for i in build_demo_universe() if i.pattern not in ("no_data", "missing_cutoff")][:n]


class AnfrageTests(unittest.TestCase):
    def setUp(self):
        self.kennung = ka.neue_kennung(NOW)

    def build(self, **changes):
        values = changes.pop("werte", demo_values(3))
        return ka.build_anfrage(self.kennung, changes.pop("umfang", "merkliste"), values, changes.pop("key", KEY), **changes)

    def test_round_trip_keeps_order_scope_and_visible_count(self):
        values = demo_values(5)
        text = self.build(werte=values, sichtbar=2, kursverlauf=[values[1][0]])
        anfrage = ka.parse_anfrage(text, self.kennung, KEY, NOW + dt.timedelta(seconds=30))
        self.assertEqual([w.isin for w in anfrage.werte], [i for i, _ in values])
        self.assertEqual(anfrage.umfang, "merkliste")
        self.assertEqual(anfrage.sichtbar, 2)
        self.assertEqual(anfrage.kursverlauf, (values[1][0],))
        self.assertEqual(ka.kennung_zeit(self.kennung), NOW.replace(microsecond=0))

    def test_parts_deliver_visible_stocks_first(self):
        values = demo_values(40)
        anfrage = ka.parse_anfrage(self.build(werte=values, sichtbar=6), self.kennung, KEY, NOW)
        parts = anfrage.teile()
        self.assertEqual([len(p) for p in parts], [6, 34])
        self.assertEqual(parts[0][0].isin, values[0][0])
        # ohne Angabe: höchstens TEIL1_MAX im ersten Teil
        anfrage = ka.parse_anfrage(self.build(werte=values), self.kennung, KEY, NOW)
        self.assertEqual([len(p) for p in anfrage.teile()], [ka.TEIL1_MAX, 40 - ka.TEIL1_MAX])
        anfrage = ka.parse_anfrage(self.build(werte=values[:3], sichtbar=3), self.kennung, KEY, NOW)
        self.assertEqual([len(p) for p in anfrage.teile()], [3])

    def test_rejections_name_a_code_without_request_data(self):
        good = self.build()
        cases = {
            "anfrage_nicht_entschluesselbar": lambda: ka.parse_anfrage(self.build(key=OTHER), self.kennung, KEY, NOW),
            "kennung_ungueltig": lambda: ka.parse_anfrage(good, "abc; rm -rf /", KEY, NOW),
            "anfrage_zu_alt": lambda: ka.parse_anfrage(good, self.kennung, KEY, NOW + dt.timedelta(minutes=21)),
            "zeit_ungueltig": lambda: ka.parse_anfrage(good, self.kennung, KEY, NOW - dt.timedelta(minutes=6)),
            "kein_schluessel": lambda: ka.parse_anfrage(good, self.kennung, None, NOW),
            "anfrage_zu_gross": lambda: ka.parse_anfrage("A" * (ka.MAX_ANFRAGE_BYTES + 1), self.kennung, KEY, NOW),
            "anfrage_unlesbar": lambda: ka.parse_anfrage("%%%", self.kennung, KEY, NOW),
        }
        for code, call in cases.items():
            with self.subTest(code=code):
                with self.assertRaises(ka.AnfrageFehler) as ctx:
                    call()
                self.assertEqual(ctx.exception.code, code)
                self.assertIsNone(ISIN_RE.search(str(ctx.exception)))

    def test_a_request_for_another_identifier_is_rejected(self):
        """Die Kennung ist Teil der Authentisierung (AAD): eine abgefangene Anfrage gilt nicht unter neuer Kennung."""
        other = ka.neue_kennung(NOW + dt.timedelta(seconds=5))
        with self.assertRaises(ka.AnfrageFehler) as ctx:
            ka.parse_anfrage(self.build(), other, KEY, NOW)
        self.assertEqual(ctx.exception.code, "anfrage_nicht_entschluesselbar")

    def test_content_checks(self):
        values = demo_values(3)
        bad = {
            "isin_ungueltig": dict(werte=[("DE0007164601", "SAP.DE")]),
            "symbol_ungueltig": dict(werte=[(values[0][0], "$(curl x)")]),
            "umfang_ungueltig": dict(umfang="alles"),
            "kursverlauf_ungueltig": dict(kursverlauf=["DE0007164600"]),
            "zu_viele_werte": dict(werte=values * (ka.MAX_WERTE // 3 + 1)),
            "keine_werte": dict(werte=[]),
        }
        for code, changes in bad.items():
            with self.subTest(code=code):
                with self.assertRaises(ka.AnfrageFehler) as ctx:
                    ka.parse_anfrage(self.build(**changes), self.kennung, KEY, NOW)
                self.assertEqual(ctx.exception.code, code)

    def test_duplicate_isins_are_fetched_once(self):
        values = demo_values(2)
        anfrage = ka.parse_anfrage(self.build(werte=values + values), self.kennung, KEY, NOW)
        self.assertEqual(len(anfrage.werte), 2)

    def test_identifier_carries_the_creation_time_and_random_part(self):
        a, b = ka.neue_kennung(NOW), ka.neue_kennung(NOW)
        self.assertNotEqual(a, b)
        self.assertRegex(a, ka.KENNUNG_RE)
        self.assertEqual(ka.kennung_zeit(a), NOW)


class AbrufTests(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="kursaktualisierung-"))
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        self.provider = DemoProvider()

    def deliveries(self, root: Path) -> list[dict]:
        out = []
        for path in sorted((root / ka.ORDNER).glob("*.bin")):
            relative = f"{ka.ORDNER}/{path.name}"
            out.append(json.loads(crypto.unpack(path.read_bytes(), KEY, relative)))
        return out

    def test_delivers_two_encrypted_parts_with_times_delay_and_day_course(self):
        values = demo_values(12)
        kennung = ka.neue_kennung(NOW)
        text = ka.build_anfrage(kennung, "sichtbar", values, KEY, sichtbar=4, kursverlauf=[values[0][0]])
        channel = ka.OrdnerLieferkanal(self.dir / "kanal", now=lambda: NOW)
        report = ka.fetch_and_deliver(kennung, text, self.provider, KEY, self.dir / "arbeit", channel, now=lambda: NOW)
        self.assertIsNone(report.fehler)
        self.assertEqual((report.werte, report.teile, report.mit_kurs, report.ohne_kurs), (12, 2, 12, 0))
        parts = self.deliveries(self.dir / "kanal")
        self.assertEqual([p["teil"] for p in parts], [1, 2])
        self.assertEqual([len(p["kurse"]) for p in parts], [4, 8])
        first = parts[0]["kurse"][0]
        self.assertEqual(first["isin"], values[0][0])
        for name in ("kurszeit_utc", "abrufzeit_utc", "sitzung", "kurs"):
            self.assertIsNotNone(first[name], name)
        self.assertEqual(first["abrufzeit_utc"], "2026-10-31T12:00:00Z")
        self.assertIn(values[0][0], parts[0]["kursverlauf"])
        course = parts[0]["kursverlauf"][values[0][0]]
        self.assertEqual(len(course["t"]), len(course["c"]))
        self.assertGreater(len(course["t"]), 1)
        # Verzögerung: aus der Antwort, wenn gemeldet; sonst laut Yahoo-Hilfe; sonst keine Angabe
        for entry in parts[0]["kurse"] + parts[1]["kurse"]:
            if entry["verzoegerung_min"] is not None:
                self.assertIn(entry["verzoegerung_quelle"], ("yahoo_antwort", "yahoo_hilfe"))
            else:
                self.assertIsNone(entry["verzoegerung_quelle"])
        # öffentliche Zeile: nur Zählungen und Zeiten
        line = report.zeile()
        self.assertIsNone(ISIN_RE.search(line))
        for _, symbol in values:
            self.assertNotIn(f" {symbol} ", f" {line} ")

    def test_files_are_bound_to_their_path(self):
        values = demo_values(2)
        kennung = ka.neue_kennung(NOW)
        text = ka.build_anfrage(kennung, "aktie", values[:1], KEY)
        ka.fetch_and_deliver(kennung, text, self.provider, KEY, self.dir / "arbeit", ka.OrdnerLieferkanal(self.dir / "kanal", now=lambda: NOW), now=lambda: NOW)
        blob = (self.dir / "kanal" / ka.lieferung_pfad(kennung, 1)).read_bytes()
        with self.assertRaises(crypto.ContainerError):
            crypto.unpack(blob, KEY, ka.lieferung_pfad(kennung, 2))

    def test_rejected_request_leaves_only_a_reason_code(self):
        kennung = ka.neue_kennung(NOW)
        text = ka.build_anfrage(kennung, "merkliste", demo_values(2), OTHER)
        report = ka.fetch_and_deliver(kennung, text, self.provider, KEY, self.dir / "arbeit", ka.OrdnerLieferkanal(self.dir / "kanal", now=lambda: NOW), now=lambda: NOW)
        self.assertEqual(report.fehler, "anfrage_nicht_entschluesselbar")
        files = list((self.dir / "kanal" / ka.ORDNER).iterdir())
        self.assertEqual([f.name for f in files], [f"{kennung}-fehler.json"])
        body = json.loads(files[0].read_text())
        self.assertEqual(body, {"schema": "tr-kursaktualisierung-fehler/1", "kennung": kennung, "grund": "anfrage_nicht_entschluesselbar"})

    def test_invalid_identifier_writes_nothing(self):
        report = ka.fetch_and_deliver("../../etc", "x", self.provider, KEY, self.dir / "arbeit", ka.OrdnerLieferkanal(self.dir / "kanal"), now=lambda: NOW)
        self.assertEqual(report.fehler, "kennung_ungueltig")
        self.assertFalse((self.dir / "kanal").exists())

    def test_old_and_foreign_files_are_pruned(self):
        recent = ka.neue_kennung(NOW - dt.timedelta(hours=3))
        old = ka.neue_kennung(NOW - dt.timedelta(days=3))
        names = [f"aktuell/{recent}-1.bin", f"aktuell/{old}-1.bin", f"aktuell/{old}-fehler.json", "aktuell/fremd.txt", "README.md"]
        self.assertEqual(sorted(ka.prune_names(names, NOW)), sorted(names[1:]))

    def test_known_delays_from_the_yahoo_help_page(self):
        self.assertEqual(ka.known_delay("SAP.DE"), 15)
        self.assertEqual(ka.known_delay("AZN.L"), 20)
        self.assertEqual(ka.known_delay("SHOP.TO"), 0)
        self.assertEqual(ka.known_delay("NESN.SW"), 30)
        self.assertIsNone(ka.known_delay("AAPL"), "USA ohne Endung: Nasdaq oder OTC – ohne Angabe nicht unterscheidbar")

    def test_quote_response_reports_delay_and_market_state(self):
        payload = {"quoteResponse": {"result": [
            {"symbol": "SAP.DE", "regularMarketPrice": 230.5, "regularMarketTime": 1793451600, "exchangeTimezoneName": "Europe/Berlin", "currency": "EUR",
             "exchangeDataDelayedBy": 15, "marketState": "REGULAR"},
            {"symbol": "AAPL", "regularMarketPrice": 250.0, "regularMarketTime": 1793451600, "exchangeTimezoneName": "America/New_York", "currency": "USD",
             "exchangeDataDelayedBy": "x", "marketState": "<b>"},
        ], "error": None}}
        quotes, missing = parse_quote_response(payload)
        self.assertEqual((quotes["SAP.DE"].delay_min, quotes["SAP.DE"].market_state), (15, "REGULAR"))
        self.assertEqual((quotes["AAPL"].delay_min, quotes["AAPL"].market_state), (None, None))
        self.assertEqual(missing, {})

    def test_intraday_from_chart_skips_gaps(self):
        payload = {"chart": {"result": [{"meta": {"exchangeTimezoneName": "Europe/Berlin", "dataGranularity": "5m"}, "timestamp": [1, 2, 3, None],
                                         "indicators": {"quote": [{"close": [10.0, None, 10.5, 11.0]}]}}]}}
        self.assertEqual(ka.intraday_from_chart(payload), {"t": [1, 3], "c": [10.0, 10.5], "zeitzone": "Europe/Berlin", "intervall": "5m"})
        self.assertIsNone(ka.intraday_from_chart({"chart": {"result": []}}))


APP = Path(__file__).resolve().parents[2] / "app"


@unittest.skipUnless(shutil.which("node") and (APP / "node_modules" / "tsx").exists(), "Node.js mit tsx nicht installiert")
class AppAnfrageTests(unittest.TestCase):
    """Die App verschlüsselt die Anfrage (app/src/lib/container.ts, aktualisierung.ts) – der Server muss sie annehmen."""

    def test_request_encrypted_by_the_app_code_is_accepted(self):
        values = demo_values(3)
        kennung = ka.neue_kennung(NOW)
        now_ms = int(NOW.timestamp() * 1000)
        text = subprocess.run(
            ["node", "--import", "tsx", "tests/helpers/anfrage.ts", kennung, str(now_ms), ",".join(f"{i}:{s}" for i, s in values)],
            cwd=APP, check=True, capture_output=True, text=True, timeout=120,
        ).stdout.strip()
        anfrage = ka.parse_anfrage(text, kennung, KEY, NOW + dt.timedelta(seconds=10))
        self.assertEqual([w.isin for w in anfrage.werte], [i for i, _ in values])
        self.assertEqual((anfrage.umfang, anfrage.sichtbar, anfrage.kursverlauf), ("merkliste", 1, (values[0][0],)))
        with self.assertRaises(ka.AnfrageFehler):
            ka.parse_anfrage(text, kennung, OTHER, NOW)


@unittest.skipUnless(shutil.which("git"), "git nicht installiert")
class GitLieferkanalTests(unittest.TestCase):
    """Lieferkanal gegen ein lokales Repository (file://): ein Commit ohne Vorgänger, ältere Lieferungen entfernt."""

    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="lieferkanal-"))
        self.addCleanup(shutil.rmtree, self.dir, ignore_errors=True)
        self.remote = self.dir / "server" / "konto" / "repo.git"
        self.remote.parent.mkdir(parents=True)
        subprocess.run(["git", "init", "-q", "--bare", str(self.remote)], check=True)

    def branch_files(self) -> list[str]:
        out = subprocess.run(["git", "ls-tree", "-r", "--name-only", ka.BRANCH], cwd=self.remote, check=True, capture_output=True, text=True).stdout
        return sorted(out.split())

    def test_each_delivery_is_one_orphan_commit_and_old_files_go(self):
        clock = {"now": NOW}
        channel = ka.GitLieferkanal("konto/repo", "geheim", server=f"file://{self.dir / 'server'}", now=lambda: clock["now"])
        self.addCleanup(channel.close)
        old = ka.neue_kennung(NOW - dt.timedelta(days=3))
        new = ka.neue_kennung(NOW)
        work = self.dir / "arbeit"
        work.mkdir()
        (work / f"{old}-1.bin").write_bytes(b"alt")
        channel.deliver([work / f"{old}-1.bin"])
        self.assertEqual(self.branch_files(), [f"aktuell/{old}-1.bin"])
        (work / f"{new}-1.bin").write_bytes(b"neu1")
        (work / f"{new}-2.bin").write_bytes(b"neu2")
        channel.deliver([work / f"{new}-1.bin"])
        channel.deliver([work / f"{new}-2.bin"])
        self.assertEqual(self.branch_files(), [f"aktuell/{new}-1.bin", f"aktuell/{new}-2.bin"])
        count = subprocess.run(["git", "rev-list", "--count", ka.BRANCH], cwd=self.remote, check=True, capture_output=True, text=True).stdout.strip()
        self.assertEqual(count, "1", "kein Verlauf: jede Lieferung ersetzt den Branch")
        content = subprocess.run(["git", "show", f"{ka.BRANCH}:aktuell/{new}-2.bin"], cwd=self.remote, check=True, capture_output=True).stdout
        self.assertEqual(content, b"neu2")

    def test_token_never_lands_in_the_repository_configuration(self):
        channel = ka.GitLieferkanal("konto/repo", "geheim-123", server=f"file://{self.dir / 'server'}", now=lambda: NOW)
        self.addCleanup(channel.close)
        config = (channel.work / ".git" / "config").read_text()
        self.assertNotIn("geheim-123", config)
        self.assertNotIn(base64.b64encode(b"x-access-token:geheim-123").decode(), config)


if __name__ == "__main__":
    unittest.main()
