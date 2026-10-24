"""Kontrolle des Kurslaufs (ab 1.17.1, ``ops/kurslauf_kontrolle.py``): liest die Laufübersicht richtig und urteilt nur nach
den festen Kriterien. SYNTHETISCHE Laufdaten im Format der echten Notizen (Lauf vom 24.10.2026, 09:17 UTC).

Ab 1.18 (Simons Auftrag vom 24.10.2026, 19:07 Uhr: „Ein erfolgreich ausgeführtes Prüfskript darf nicht mit einer
bestandenen Abnahme verwechselt werden.“): eigenes Gesamtergebnis „Abnahme“ mit Rückgabewert, vollständiger Kursabruf in
zwei Kriterien, Signale genau des neuen Stands, keine Abnahme ohne veröffentlichte status.json.
"""

from __future__ import annotations

import contextlib
import datetime as dt
import importlib.util
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SPEC = importlib.util.spec_from_file_location("kurslauf_kontrolle", Path(__file__).resolve().parents[2] / "ops" / "kurslauf_kontrolle.py")
kontrolle = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(kontrolle)

FULL = (
    "Snapshot 2026-10-26_abcdef12 (vollständig) veröffentlicht\n"
    "Stichtagskurse je Markt (nötig 80%): XNYS 3610/3618 (100%)\n"
    "Identität: verifiziert 11176, unklar 312, kein_aktieninstrument 108\n"
    "Kursabruf zum Stichtag: ok 10957, keine_daten 139, ohne_stichtag 49\n"
    "Kursstichtag 2026-10-26 (Börsen mit Sitzung: XNYS, XETR)\n"
    "Kursabruf: 11145 Notierungen offen (davon 0 erneut: ohne Stichtagskurs oder Fehler), 0 bereits erledigt (Checkpoint)\n"
    "Chart-Abruf: 11145 Abrufe in 1395 s (8.0 je Sekunde; 4 gleichzeitig über 2 Hosts, Abstand 0.25 s je Host)\n"
    "Kursabruf beendet: 11006 aktualisiert, davon 49 ohne Kurs am Stichtag; 0 Einzelfehler (isoliert)"
)

NIGHT_RUN = {"event": "workflow_dispatch", "triggering_actor": {"login": "github-actions[bot]"}, "created_at": "2026-10-26T23:38:00Z"}
SCHEDULED = {"event": "schedule", "triggering_actor": {"login": "szymeklh87-commits"}, "created_at": "2026-10-27T06:10:00Z"}
MANUAL = {"event": "workflow_dispatch", "triggering_actor": {"login": "szymeklh87-commits"}, "created_at": "2026-10-24T11:41:08Z"}
SCHEDULED_NIGHT = {"id": 7, "event": "schedule", "created_at": "2026-10-26T23:37:40Z"}


def notice(text: str, status: str = "veroeffentlicht") -> dict:
    return {"annotation_level": "notice", "title": f"Lauf: {status}", "message": text}


def status_for(run: dict, **changes) -> dict:
    """Veröffentlichte status.json nach dem Lauf: neuer Stand, nächster Kursstand, Signale dieses Stands 40 min später."""
    made = dt.datetime.fromisoformat(run["created_at"].replace("Z", "+00:00")) + dt.timedelta(minutes=40)
    status = {
        "last_price_session": "2026-10-26",
        "latest_snapshot_id": "2026-10-26_abcdef12",
        "naechster_kursstand": {"datum": "2026-10-27", "ab_utc": "2026-10-27T22:00:00Z"},
        "signale": {"id": made.strftime("%Y%m%dT%H%M%SZ"), "snapshot_id": "2026-10-26_abcdef12", "kursstand": "2026-10-26", "aktien": 10936, "erstellt_utc": made.strftime("%Y-%m-%dT%H:%M:%SZ")},
        "software_version": "1.18.0",
    }
    status.update(changes)
    return status


def fake_api(run: dict, notices: list[dict], kennzahlen: str = "success", night_runs: list[dict] | None = None):
    jobs = {
        "jobs": [
            {"id": 1, "name": "berechnen", "conclusion": "success", "started_at": "2026-10-26T23:40:00Z", "completed_at": "2026-10-27T00:12:00Z"},
            {"id": 2, "name": "kennzahlen", "conclusion": kennzahlen},
            {"id": 3, "name": "signale-bereitstellen", "conclusion": "success" if kennzahlen == "success" else "skipped", "completed_at": "2026-10-27T00:31:00Z"},
        ]
    }

    def api(path: str):
        if "/workflows/nachtlauf.yml/runs" in path:
            return {"workflow_runs": [SCHEDULED_NIGHT] if night_runs is None else night_runs}
        if path.endswith("/jobs?per_page=50"):
            return jobs
        if "/check-runs/1/annotations" in path:
            return notices
        return run

    return api


def judged(run: dict, notices: list[dict], status: dict | None = None, **kwargs) -> dict:
    """Ein Lauf wie im Workflow (GitHub Actions, status.json abrufbar) – ohne ``status`` wie lokal (nicht abrufbar)."""
    env = {"GITHUB_ACTIONS": "true" if status is not None else ""}
    with mock.patch.object(kontrolle, "api", fake_api(run, notices, **kwargs)), mock.patch.object(kontrolle, "fetch_status", return_value=status), mock.patch.dict(os.environ, env):
        return kontrolle.evaluate(42)


def criterion(result: dict, start: str) -> dict:
    return next(c for c in result["kriterien"] if c["kriterium"].startswith(start))


class RunReportParsing(unittest.TestCase):
    def test_full_run_values(self):
        report = kontrolle.run_report([notice(FULL)])
        self.assertEqual(report["status"], "veroeffentlicht")
        self.assertEqual((report["stand"], report["vollstaendigkeit"], report["stichtag"], report["snapshot_id"]), ("2026-10-26", "vollständig", "2026-10-26", "2026-10-26_abcdef12"))
        self.assertEqual((report["offen"], report["erneut"], report["checkpoint"]), (11145, 0, 0))
        self.assertEqual((report["abrufe"], report["abruf_sekunden"], report["je_sekunde"]), (11145, 1395, 8.0))
        self.assertEqual(report["ergebnis_je_notierung"], {"ok": 10957, "keine_daten": 139, "ohne_stichtag": 49})
        self.assertEqual((report["aktualisiert"], report["einzelfehler"]), (11006, 0))
        self.assertTrue(report["gleichzeitig"])
        self.assertFalse(report["rueckfall_drosselung"])

    def test_throttled_fallback_is_recognised(self):
        text = FULL.replace(
            "Abstand 0.25 s je Host)",
            "Abstand 0.25 s je Host); Drosselung (HTTP 429) nach 5000 Abrufen – danach 6145 einzeln mit dem bisherigen Abstand",
        )
        report = kontrolle.run_report([notice(text)])
        self.assertTrue(report["rueckfall_drosselung"])


class Verdict(unittest.TestCase):
    def test_night_run_with_full_parallel_fetch_passes(self):
        result = judged(NIGHT_RUN, [notice(FULL)], status_for(NIGHT_RUN))
        self.assertEqual(result["ausloeser"], "nachtlauf")
        self.assertTrue(result["bestanden"], result["kriterien"])
        self.assertEqual((result["erfuellt"], result["gesamt"]), (10, 10))
        self.assertIn("Nachtlauf 7, Auslöser schedule", result["kriterien"][0]["ist"])
        self.assertIn("61 min nach 22:37 UTC", result["kriterien"][0]["ist"], "Verzögerung des Nachtlaufs selbst")
        self.assertIn("11145 von 11145 Notierungen mit Ergebnis", criterion(result, "jede Notierung")["ist"])
        self.assertIn("mit Kurs zum Stichtag 98,3 %", criterion(result, "jede Notierung")["ist"])
        self.assertEqual(result["minuten_bis_bereitgestellt"], 53)

    def test_night_run_started_by_hand_is_not_scheduled(self):
        """Ab 1.18: Am 24.10.2026 um 10:26 UTC startete ein von Hand ausgelöster Nachtlauf den täglichen Lauf ebenfalls als
        „github-actions[bot]“ – das ist kein Lauf über GitHubs Zeitplan (ebenso wenig ein Start über den externen Auslöser)."""
        run = {"event": "workflow_dispatch", "triggering_actor": {"login": "github-actions[bot]"}, "created_at": "2026-10-24T10:26:16Z"}
        by_hand = {"id": 8, "event": "workflow_dispatch", "created_at": "2026-10-24T10:26:04Z"}
        older_scheduled = {"id": 6, "event": "schedule", "created_at": "2026-10-23T22:39:00Z"}
        result = judged(run, [notice(FULL)], status_for(run), night_runs=[older_scheduled, by_hand])
        self.assertEqual(result["ausloeser"], "nachtlauf ohne zeitplan")
        self.assertFalse(result["kriterien"][0]["erfuellt"])
        self.assertFalse(result["bestanden"])
        # kein Nachtlauf in den 30 Minuten davor: Auslöser unbekannt – ebenfalls nicht bestanden
        result = judged(run, [notice(FULL)], status_for(run), night_runs=[older_scheduled])
        self.assertEqual(result["ausloeser"], "nachtlauf ohne gefundenen Auslöser")
        self.assertFalse(result["bestanden"])

    def test_complete_fetch_means_this_run_and_a_result_for_every_listing(self):
        """„Vollständiger Kursabruf“: alle Notierungen in diesem Lauf abgefragt (nicht aus dem Checkpoint) und für jede ein
        Ergebnis ohne Abruffehler – fehlt eines davon, ist die Abnahme nicht bestanden."""
        good = judged(SCHEDULED, [notice(FULL)], status_for(SCHEDULED))
        self.assertTrue(good["bestanden"], good["kriterien"])
        cases = {
            "aus dem Checkpoint": FULL.replace("0 bereits erledigt", "11 bereits erledigt").replace("ohne_stichtag 49", "ohne_stichtag 60"),
            "Abruffehler": FULL.replace("ohne_stichtag 49", "ohne_stichtag 46, fehler 3"),
            "Einzelfehler": FULL.replace("; 0 Einzelfehler", "; 2 Einzelfehler"),
            "Notierungen ohne Ergebnis": FULL.replace("ok 10957", "ok 10950"),
            "ohne Angabe je Notierung": FULL.replace("Kursabruf zum Stichtag: ok 10957, keine_daten 139, ohne_stichtag 49\n", ""),
        }
        for name, text in cases.items():
            with self.subTest(name):
                result = judged(SCHEDULED, [notice(text)], status_for(SCHEDULED))
                self.assertFalse(result["bestanden"], name)
                failed = [c["kriterium"] for c in result["kriterien"] if not c["erfuellt"]]
                self.assertTrue(any(c.startswith(("Kurse aller Notierungen", "jede Notierung")) for c in failed), failed)

    def test_published_status_must_show_the_new_stand_and_its_signals(self):
        """In GitHub Actions die veröffentlichte status.json: neuester Stand, nächster Kursstand, Signale genau dieses Stands."""
        result = judged(SCHEDULED, [notice(FULL)], status_for(SCHEDULED))
        self.assertTrue(result["bestanden"], result["kriterien"])
        self.assertEqual([c["kriterium"] for c in result["kriterien"]][-2:], ["status.json: neuer Kursstand und nächster danach", "status.json: Signale zum neuen Kursstand"])
        signals = status_for(SCHEDULED)["signale"]
        wrong = {
            "Signale noch vom alten Kursstand": status_for(SCHEDULED, signale=signals | {"kursstand": "2026-10-23", "snapshot_id": "2026-10-23_3f7ce5f3"}),
            "Signale eines anderen Stands desselben Tags": status_for(SCHEDULED, signale=signals | {"snapshot_id": "2026-10-26_99999999"}),
            "Signale vor dem Lauf erstellt": status_for(SCHEDULED, signale=signals | {"erstellt_utc": "2026-10-27T05:00:00Z"}),
        }
        for name, status in wrong.items():
            with self.subTest(name):
                self.assertFalse(criterion(judged(SCHEDULED, [notice(FULL)], status), "status.json: Signale")["erfuellt"])
        # die App zeigt noch einen anderen Stand: nicht bestanden
        self.assertFalse(judged(SCHEDULED, [notice(FULL)], status_for(SCHEDULED, latest_snapshot_id="2026-10-23_3f7ce5f3"))["bestanden"])
        # später von Hand gerechneter Zwischenstand über dem neuen Stand: bestanden
        intraday = status_for(SCHEDULED, latest_snapshot_id="2026-10-27_zw000001", zwischenstand={"offizieller_stand": "2026-10-26_abcdef12"})
        self.assertTrue(judged(SCHEDULED, [notice(FULL)], intraday)["bestanden"])
        # inzwischen ein neuerer Stand: für diesen Lauf nicht mehr beurteilbar – zählt nicht als erfüllt
        later = judged(SCHEDULED, [notice(FULL)], status_for(SCHEDULED, last_price_session="2026-10-27", latest_snapshot_id="2026-10-27_12345678"))
        self.assertFalse(later["bestanden"])
        self.assertIn("nicht mehr beurteilbar", criterion(later, "status.json: Signale")["ist"])

    def test_without_published_status_there_is_no_acceptance(self):
        """Lokal (oder wenn die Website nicht abrufbar ist) fehlen Datenstand und Signale – dann keine Abnahme."""
        result = judged(SCHEDULED, [notice(FULL)])
        self.assertFalse(result["bestanden"])
        self.assertEqual(result["erfuellt"], result["gesamt"] - 2)
        self.assertIn("nicht beurteilbar", criterion(result, "status.json: neuer Kursstand")["ist"])

    def test_tempo_needs_the_full_fetch_and_says_why(self):
        """Kriterium 5 (ab 1.18 eindeutig): ein schneller Nachzügler-Abruf von 49 Notierungen belegt das Tempo nicht – der
        Grund steht im Ist-Wert, nicht nur ein ✗ neben „8,1 je Sekunde“."""
        full = criterion(judged(SCHEDULED, [notice(FULL)], status_for(SCHEDULED)), "gleichzeitig über 2 Hosts")
        self.assertTrue(full["erfuellt"])
        self.assertEqual(full["kriterium"], "gleichzeitig über 2 Hosts, ≥ 6 je Sekunde über ≥ 10.000 Abrufe")
        self.assertEqual(
            full["ist"],
            "Abrufe 11145 (verlangt mindestens 10.000: erfüllt); Messdauer 1395 s; Geschwindigkeit 8,0 je Sekunde (verlangt mindestens 6: erfüllt); "
            "gleichzeitig über 2 Hosts ja (verlangt ja: erfüllt; laut Lauf „4 gleichzeitig über 2 Hosts, Abstand 0.25 s je Host“)",
        )
        late = FULL.replace("Chart-Abruf: 11145 Abrufe in 1395 s (8.0 je", "Chart-Abruf: 49 Abrufe in 6 s (8.1 je")
        small = criterion(judged(SCHEDULED, [notice(late)], status_for(SCHEDULED)), "gleichzeitig über 2 Hosts")
        self.assertFalse(small["erfuellt"])
        self.assertIn("Abrufe 49 (verlangt mindestens 10.000: NICHT erfüllt); Messdauer 6 s; Geschwindigkeit 8,1 je Sekunde (verlangt mindestens 6: erfüllt)", small["ist"])
        slow = criterion(judged(SCHEDULED, [notice(FULL.replace("in 1395 s (8.0 je", "in 4395 s (2.5 je"))], status_for(SCHEDULED)), "gleichzeitig über 2 Hosts")
        self.assertIn("Geschwindigkeit 2,5 je Sekunde (verlangt mindestens 6: NICHT erfüllt)", slow["ist"])
        alone = criterion(judged(SCHEDULED, [notice(FULL.replace("4 gleichzeitig über 2 Hosts", "nacheinander"))], status_for(SCHEDULED)), "gleichzeitig über 2 Hosts")
        self.assertIn("gleichzeitig über 2 Hosts nein (verlangt ja: NICHT erfüllt", alone["ist"])
        self.assertFalse(alone["erfuellt"])

    def test_manual_or_partial_runs_do_not_pass(self):
        self.assertFalse(judged(MANUAL, [notice(FULL)], status_for(MANUAL))["bestanden"])
        small = FULL.replace("11145 Notierungen offen", "51 Notierungen offen").replace("Chart-Abruf: 11145 Abrufe", "Chart-Abruf: 51 Abrufe")
        self.assertFalse(judged(SCHEDULED, [notice(small)], status_for(SCHEDULED))["bestanden"], "nur Nachzügler aus dem Checkpoint")
        self.assertFalse(judged(SCHEDULED, [notice(FULL, status="wartet_auf_provider")], status_for(SCHEDULED))["bestanden"])
        self.assertFalse(judged(SCHEDULED, [notice(FULL)], status_for(SCHEDULED), kennzahlen="failure")["bestanden"])
        self.assertTrue(judged(SCHEDULED, [notice(FULL)], status_for(SCHEDULED))["bestanden"])


class Acceptance(unittest.TestCase):
    """Ab 1.18: Das fachliche Gesamtergebnis steht ausdrücklich da und ist der Rückgabewert – ein fehlerfrei gelaufenes
    Prüfskript ist keine bestandene Abnahme."""

    def run_main(self, args: list[str], runs: dict[int, dict], status: dict | None, official: list[int] | None = None, fail: bool = False):
        original = kontrolle.evaluate

        def evaluate(run_id: int) -> dict:
            run = runs[run_id]
            with mock.patch.object(kontrolle, "api", fake_api(run["run"], run["notices"])), mock.patch.object(kontrolle, "fetch_status", return_value=status):
                return original(run_id)

        def since(day: str) -> list[int]:
            if fail:
                raise RuntimeError("GitHub nicht erreichbar")
            return list(official if official is not None else runs)

        out = io.StringIO()
        with tempfile.TemporaryDirectory() as tmp:
            summary = Path(tmp) / "summary.md"
            env = {"GITHUB_ACTIONS": "true" if status is not None else "", "GITHUB_STEP_SUMMARY": str(summary)}
            with mock.patch.object(kontrolle, "evaluate", evaluate), mock.patch.object(kontrolle, "official_runs_since", since), mock.patch.dict(os.environ, env), contextlib.redirect_stdout(out):
                code = kontrolle.main(args)
            text = summary.read_text(encoding="utf-8") if summary.exists() else ""
        return code, out.getvalue(), text

    def test_passed_acceptance(self):
        runs = {101: {"run": NIGHT_RUN, "notices": [notice(FULL)]}}
        code, out, summary = self.run_main(["--seit", "2026-10-26"], runs, status_for(NIGHT_RUN))
        self.assertEqual(code, kontrolle.EXIT_BESTANDEN)
        self.assertIn("::notice title=Abnahme Kurslauf: BESTANDEN::Lauf 101 (nachtlauf, Stand 2026-10-26): alle 10 Kriterien erfüllt", out)
        self.assertTrue(summary.startswith("## Abnahme: ✅ BESTANDEN"))

    def test_failed_acceptance_is_not_hidden_behind_a_successful_script(self):
        runs = {102: {"run": SCHEDULED, "notices": [notice(FULL.replace("in 1395 s (8.0 je", "in 4395 s (2.5 je"))]}}
        code, out, summary = self.run_main(["--lauf", "102"], runs, status_for(SCHEDULED))
        self.assertEqual(code, kontrolle.EXIT_NICHT_BESTANDEN)
        self.assertIn("::error title=Abnahme Kurslauf: NICHT BESTANDEN::Lauf 102 (zeitplan, Stand 2026-10-26): 9 von 10 Kriterien erfüllt – nicht erfüllt: gleichzeitig über 2 Hosts", out)
        self.assertIn("Das Prüfskript selbst lief fehlerfrei – das allein ist keine Abnahme", out)
        self.assertTrue(summary.startswith("## Abnahme: ❌ NICHT BESTANDEN"))
        self.assertIn("Prüfskript: fehlerfrei ausgeführt (das allein ist keine Abnahme", summary)
        self.assertNotIn("Abnahme Kurslauf: BESTANDEN", out)
        # ab 1.18.1 getrennt: Abnahme, nicht erfüllte und erfüllte Kriterien, Ausstehendes, Prüfskript, Softwaretests
        self.assertIn("- **Fachliche Abnahme:** NICHT BESTANDEN", summary)
        self.assertIn("- **Nicht erfüllte Kriterien (1):**\n  - gleichzeitig über 2 Hosts, ≥ 6 je Sekunde über ≥ 10.000 Abrufe: Abrufe 11145", summary)
        self.assertIn("- **Erfüllte Kriterien (9):**", summary)
        self.assertIn("- **Prüfskript:** fehlerfrei ausgeführt – das ist weder ein Softwaretest noch eine Abnahme", summary)

    def test_pending_when_no_scheduled_full_run_exists(self):
        runs = {103: {"run": MANUAL, "notices": [notice(FULL)]}}
        code, out, summary = self.run_main(["--seit", "2026-10-26"], runs, status_for(MANUAL))
        self.assertEqual(code, kontrolle.EXIT_AUSSTEHEND)
        self.assertIn("::warning title=Abnahme Kurslauf: AUSSTEHEND::Noch kein zeitgesteuerter Kurslauf mit Abruf aller Notierungen seit 2026-10-26 (1 offizielle Läufe geprüft) – nichts bestanden", out)
        self.assertTrue(summary.startswith("## Abnahme: ⏳ AUSSTEHEND"))
        # ab 1.18.1: ein Lauf von Hand mit allen Kriterien ersetzt den zeitgesteuerten nicht – ausdrücklich ausstehend
        self.assertIn("- **Ausstehend:** ein zeitgesteuerter Kurslauf mit Abruf aller Notierungen seit 2026-10-26 (Nachtlauf Mo–Fr 22:37 UTC); "
                      "geprüft wurden 1 offizielle Läufe – ein Start von Hand ersetzt diesen Nachweis nicht", summary)
        self.assertNotIn("Erfüllte Kriterien", summary.split("### Lauf")[0], "kein beurteilter Lauf – keine Kriterienliste als Abnahme")
        code, out, _ = self.run_main(["--seit", "2026-10-26"], {}, status_for(MANUAL), official=[])
        self.assertEqual(code, kontrolle.EXIT_AUSSTEHEND)

    def test_script_error_gives_no_acceptance(self):
        code, out, _ = self.run_main(["--seit", "2026-10-26"], {}, None, fail=True)
        self.assertEqual(code, kontrolle.EXIT_SKRIPTFEHLER)
        self.assertIn("::error title=Prüfskript abgebrochen – keine Abnahme::RuntimeError: GitHub nicht erreichbar", out)
        self.assertNotIn("Abnahme Kurslauf", out)

    def test_exit_codes_are_distinct(self):
        codes = (kontrolle.EXIT_BESTANDEN, kontrolle.EXIT_NICHT_BESTANDEN, kontrolle.EXIT_AUSSTEHEND, kontrolle.EXIT_SKRIPTFEHLER)
        self.assertEqual(len(set(codes)), 4)
        self.assertEqual(kontrolle.EXIT_BESTANDEN, 0)
        self.assertNotIn(1, codes, "1 wäre auch ein unbehandelter Python-Fehler")


if __name__ == "__main__":
    unittest.main()
