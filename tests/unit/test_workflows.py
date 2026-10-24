"""T53, T42, T52 (Teil): Wer kann einen teuren Lauf auslösen, wo liegen Geheimnisse, passt der Zeitplan?

Prüft die GitHub-Workflow-Dateien statisch. Ob GitHub sie tatsächlich ausführt, lässt sich nur im
echten Repository belegen (siehe docs/07_Testbericht.md).
"""

from __future__ import annotations

import datetime as dt
import json
import re
import tempfile
import unittest
from pathlib import Path

import yaml

from traktien.config import load_pipeline_config

REPO = Path(__file__).resolve().parents[2]
WORKFLOWS = REPO / ".github" / "workflows"
OUTSIDER_TRIGGERS = {"pull_request_target", "issue_comment", "repository_dispatch", "workflow_run", "discussion", "issues", "fork", "watch"}


def load(name: str) -> dict:
    return yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))


def triggers(workflow: dict) -> dict:
    # PyYAML liest den Schlüssel „on“ als booleschen Wert True.
    value = workflow.get("on", workflow.get(True))
    return value if isinstance(value, dict) else {name: None for name in (value if isinstance(value, list) else [value])}


def pages_upload(steps: list[dict]) -> tuple[dict, dict]:
    """Ab 1.12: (Schritt „Website packen“, Schritt mit actions/upload-artifact) – dasselbe Pages-Artefakt wie mit
    actions/upload-pages-artifact, aber ohne Kompression."""
    pack = next(s for s in steps if "artifact.tar" in str(s.get("run", "")) and str(s.get("run", "")).startswith("tar "))
    upload = next(s for s in steps if str(s.get("uses", "")).startswith("actions/upload-artifact@"))
    return pack, upload


class WorkflowSecurityTests(unittest.TestCase):
    def test_T53_expensive_daily_run_can_only_be_started_by_schedule_or_repository_owner(self):
        daily = load("taeglich.yml")
        self.assertEqual(set(triggers(daily)), {"schedule", "workflow_dispatch"})

    def test_T53_no_workflow_reacts_to_outsider_events(self):
        for path in sorted(WORKFLOWS.glob("*.yml")):
            with self.subTest(workflow=path.name):
                self.assertFalse(set(triggers(load(path.name))) & OUTSIDER_TRIGGERS)

    def test_T52_secrets_only_in_workflows_without_pull_request_trigger(self):
        for path in sorted(WORKFLOWS.glob("*.yml")):
            text = path.read_text(encoding="utf-8")
            uses_secret = re.search(r"\$\{\{\s*secrets\.", text) is not None
            with self.subTest(workflow=path.name):
                if uses_secret:
                    self.assertTrue(set(triggers(load(path.name))) <= {"schedule", "workflow_dispatch"}, "Secrets nie bei Pull-Requests")
                # Secrets werden nur als Umgebungsvariable übergeben, nie in Befehle geschrieben.
                for line in text.splitlines():
                    if "secrets." in line:
                        self.assertRegex(line.strip(), r"^[A-Z_]+: \$\{\{ secrets\.[A-Z_]+ \}\}$")

    def test_T52_nothing_is_deployed_without_successful_site_verification(self):
        daily = load("taeglich.yml")
        steps = daily["jobs"]["berechnen"]["steps"]
        verify = next(s for s in steps if "verify-site" in str(s.get("run", "")))
        self.assertEqual(verify.get("id"), "pruefen")
        pack, artifact = pages_upload(steps)
        for step in (pack, artifact):
            self.assertIn("steps.pruefen.outcome == 'success'", step["if"])
        freigabe = daily["jobs"]["berechnen"]["outputs"]["freigabe"]
        self.assertIn("steps.pruefen.outcome == 'success'", freigabe)
        self.assertLess(steps.index(verify), steps.index(pack), "erst prüfen, dann packen")
        self.assertLess(steps.index(pack), steps.index(artifact), "erst packen, dann hochladen")
        # Ab 1.12: Bereitstellung erst, wenn auch das Sichern im Hintergrund erfolgreich war
        self.assertIn("steps.sichern.outcome == 'success'", freigabe)
        # Ab 1.12.1: Bereitstellung als letzter Schritt desselben Jobs – unter genau der Bedingung „freigabe“
        # (auch nach einem roten Lauf, damit die App die Störung zeigt), erst nach Hochladen und Sichern
        self.assertNotIn("bereitstellen", daily["jobs"])
        self.assertEqual(daily["jobs"]["berechnen"]["environment"]["name"], "github-pages")
        deploy = next(s for s in steps if str(s.get("uses", "")).startswith("actions/deploy-pages@"))
        self.assertEqual(deploy.get("id"), "pages")
        self.assertEqual(deploy["if"], "always() && " + freigabe.removeprefix("${{ ").removesuffix(" }}"))
        save = next(s for s in steps if s.get("id") == "sichern")
        self.assertLess(steps.index(artifact), steps.index(deploy), "erst hochladen, dann bereitstellen")
        self.assertLess(steps.index(save), steps.index(deploy), "erst sichern, dann bereitstellen")

    def test_pages_artifact_has_the_format_of_upload_pages_artifact_without_compression(self):
        """Ab 1.12: eine ``artifact.tar`` (Verweise aufgelöst, ohne .git, .github und versteckte Dateien) als
        Artefakt „github-pages“ bzw. „github-pages-signale“ ohne Kompression; deploy-pages stellt genau dieses
        Artefakt bereit."""
        daily = load("taeglich.yml")
        for job, deploy_job, name in (("berechnen", "berechnen", "github-pages"), ("kennzahlen", "signale-bereitstellen", "github-pages-signale")):
            with self.subTest(job=job):
                pack, upload = pages_upload(daily["jobs"][job]["steps"])
                command = pack["run"]
                for part in ("--dereference", "--hard-dereference", "--directory _site", '-cf "$RUNNER_TEMP/artifact.tar"', "--exclude=.git", "--exclude=.github", "--exclude='.[^/]*'"):
                    self.assertIn(part, command)
                self.assertNotIn("-cvf", command, "keine Liste aller Dateien im Protokoll")
                self.assertEqual(upload["with"]["name"], name)
                self.assertEqual(upload["with"]["path"], "${{ runner.temp }}/artifact.tar")
                self.assertEqual(int(upload["with"]["compression-level"]), 0)
                self.assertEqual(upload["with"]["if-no-files-found"], "error")
                deploy = next(s for s in daily["jobs"][deploy_job]["steps"] if str(s.get("uses", "")).startswith("actions/deploy-pages@"))
                self.assertEqual((deploy.get("with") or {}).get("artifact_name", "github-pages"), name)
                self.assertEqual(int(deploy["with"]["reporting_interval"]), 1000)

    def test_facts_job_deploys_only_verified_files_after_the_price_run(self):
        """Kennzahlen und Signale (ab 1.6): eigener Job nach der Bereitstellung der Kurse, mit eigener
        Prüfung vor dem Hochladen; nie bei „Nur Website“, „Nur Kennzahlen“ oder Neuaufbau."""
        daily = load("taeglich.yml")
        job = daily["jobs"]["kennzahlen"]
        self.assertEqual(job["needs"], "berechnen", "ab 1.12.1 stellt „berechnen“ die Kurse selbst bereit")
        for flag in ("nur_website", "nur_kennzahlen", "zustand_neu_aufbauen", "zwischenstand"):
            self.assertIn(f"inputs.{flag} != true", job["if"])
        # Zwischenstand (Voreinstellung ab 1.9.1): Kennzahlen nur, wenn davor ein neuer offizieller Stand entstand
        self.assertIn("needs.berechnen.outputs.kennzahlen == 'true'", job["if"])
        self.assertIn("inputs.erzwingen == true", job["if"])
        self.assertEqual(daily["jobs"]["berechnen"]["outputs"]["kennzahlen"], "${{ steps.lauf.outputs.kennzahlen }}")
        steps = job["steps"]
        run = next(s for s in steps if "--kennzahlen" in str(s.get("run", "")))
        self.assertEqual(run["env"]["KENNZAHLEN_TAEGLICH"], "true")
        verify = next(s for s in steps if "verify-site" in str(s.get("run", "")))
        pack, artifact = pages_upload(steps)
        for step in (pack, artifact):
            self.assertIn("steps.pruefen.outcome == 'success'", step["if"])
        self.assertLess(steps.index(verify), steps.index(pack))
        self.assertLess(steps.index(pack), steps.index(artifact))
        deploy = daily["jobs"]["signale-bereitstellen"]
        self.assertIn("needs.kennzahlen.outputs.freigabe == 'true'", deploy["if"])
        self.assertEqual(deploy["steps"][0]["with"]["artifact_name"], artifact["with"]["name"])
        self.assertLessEqual(int(job["timeout-minutes"]), 120)

    def test_intraday_input_uses_the_same_job_lock_and_verification(self):
        """Zwischenstand (ab 1.8): Eingabe im täglichen Workflow – gleiche Concurrency-Gruppe (nie zwei Läufe
        gleichzeitig), gleicher Prüfschritt vor der Bereitstellung. Ab 1.9.1 Voreinstellung eines Laufs von Hand
        („alles aktualisieren“) und erste Eingabe im Formular; geplante Läufe haben keine Eingaben."""
        daily = load("taeglich.yml")
        triggers = daily.get("on") or daily.get(True)
        inputs = triggers["workflow_dispatch"]["inputs"]
        self.assertEqual(inputs["zwischenstand"]["type"], "boolean")
        self.assertTrue(inputs["zwischenstand"]["default"])
        self.assertEqual(next(iter(inputs)), "zwischenstand", "oben im Formular „Run workflow“")
        for other in ("erzwingen", "zustand_neu_aufbauen", "nur_website", "nur_kennzahlen"):
            self.assertFalse(inputs[other]["default"], other)
        run = next(s for s in daily["jobs"]["berechnen"]["steps"] if s.get("id") == "lauf")
        self.assertIn("--zwischenstand", run["run"])
        self.assertEqual(run["env"]["ZWISCHENSTAND"], "${{ inputs.zwischenstand }}")
        self.assertEqual(daily["concurrency"]["group"], "taeglicher-lauf")
        self.assertFalse(daily["concurrency"]["cancel-in-progress"])

    def test_permissions_are_minimal(self):
        self.assertEqual(load("taeglich.yml")["permissions"], {"contents": "write", "pages": "write", "id-token": "write"})
        for name in ("pruefung.yml", "sicherung.yml", "datenquellen.yml", "app-pruefen.yml", "kursabruf-vergleich.yml", "kursabruf-tempo.yml", "android-pruefen.yml", "fehlende-tage.yml"):
            with self.subTest(workflow=name):
                self.assertEqual(load(name)["permissions"], {"contents": "read"})

    def test_measurement_workflows_only_by_hand_and_without_uploads(self):
        """Vergleich und Tempo-Messung des Kursabrufs, Android-Emulator (ab 1.17), fehlende Kurstage (ab 1.17.1): nur von Hand,
        nur lesend, nichts hochladen."""
        for name in ("kursabruf-vergleich.yml", "kursabruf-tempo.yml", "android-pruefen.yml", "fehlende-tage.yml"):
            with self.subTest(workflow=name):
                workflow = load(name)
                self.assertEqual(set(triggers(workflow)), {"workflow_dispatch"})
                text = (WORKFLOWS / name).read_text(encoding="utf-8")
                self.assertNotIn("upload-artifact", text)
                self.assertNotIn("sync_up", text)
                self.assertNotIn("contents: write", text)

    def test_android_emulator_check_uses_no_secrets(self):
        """Der Emulator-Test prüft nur den DEMO-Stand: keine Secrets, keine Passphrase im Workflow."""
        text = (WORKFLOWS / "android-pruefen.yml").read_text(encoding="utf-8")
        self.assertNotIn("secrets.", text)
        self.assertNotIn("DATA_PASSPHRASE", text)

    def test_android_real_data_job_is_optional_and_uses_the_secret_in_one_step(self):
        """Ab 1.18: echte Daten in Chrome für Android – nur auf Wunsch (Eingabe „android“, voreingestellt aus), im Workflow
        mit dem Secret (nicht im Emulator-Workflow, der ohne Secrets bleibt), Secret nur im einen Prüfschritt."""
        workflow = load("app-pruefen.yml")
        inputs = triggers(workflow)["workflow_dispatch"]["inputs"]
        self.assertEqual((inputs["android"]["type"], inputs["android"]["default"]), ("boolean", False))
        job = workflow["jobs"]["android"]
        self.assertEqual(job["if"], "inputs.android")
        with_secret = [step for step in job["steps"] if "secrets." in json.dumps(step)]
        self.assertEqual(len(with_secret), 1)
        self.assertEqual(with_secret[0]["run"], "python tests/live/android_echte_daten.py")
        self.assertEqual(set(with_secret[0]["env"]), {"PYTHONPATH", "PYTHONUNBUFFERED", "DATA_PASSPHRASE"})
        runs = " ".join(step.get("run", "") for step in job["steps"])
        self.assertIn("tests/live/android_emulator_start.sh", runs)
        self.assertIn("tests/live/android_chrome_vorbereiten.sh", runs)
        self.assertIn("tests/live/android_chrome_vorbereiten.sh", (WORKFLOWS / "android-pruefen.yml").read_text(encoding="utf-8"))

    def test_independent_price_check_is_optional_and_reads_only(self):
        """Ab 1.18: Kurse unabhängig gegenprüfen (Nasdaq) – nur auf Wunsch, Secret nur im einen Prüfschritt, nur lesend."""
        workflow = load("app-pruefen.yml")
        inputs = triggers(workflow)["workflow_dispatch"]["inputs"]
        self.assertEqual((inputs["kurse"]["type"], inputs["kurse"]["default"]), ("boolean", False))
        job = workflow["jobs"]["kurse"]
        self.assertEqual(job["if"], "inputs.kurse")
        with_secret = [step for step in job["steps"] if "secrets." in json.dumps(step)]
        self.assertEqual(len(with_secret), 1)
        self.assertEqual(with_secret[0]["run"], "python tests/live/kurse_gegenpruefen.py")
        self.assertEqual(workflow["permissions"], {"contents": "read"})

    def test_original_stands_are_optional_and_checked_against_their_evidence(self):
        """Ab 1.18.1: die drei Originalstände vom 12.10. – nur auf Wunsch, jede Stand-ID im Format des Release, Secret nur im
        Prüfschritt, die Stand-ID über eine Umgebungsvariable (nicht in den Befehl eingesetzt), mit Prüfnachweis."""
        import re

        workflow = load("app-pruefen.yml")
        inputs = triggers(workflow)["workflow_dispatch"]["inputs"]
        self.assertEqual((inputs["originalstaende"]["type"], inputs["originalstaende"]["default"]), ("boolean", False))
        job = workflow["jobs"]["originalstaende"]
        self.assertEqual(job["if"], "inputs.originalstaende")
        stands = job["strategy"]["matrix"]["stand"]
        self.assertEqual(len(stands), 3)
        self.assertTrue(all(re.fullmatch(r"2026-10-12_[0-9a-f]{8}", s) for s in stands), stands)
        with_secret = [step for step in job["steps"] if "secrets." in json.dumps(step)]
        self.assertEqual(len(with_secret), 1)
        self.assertEqual(with_secret[0]["run"], 'python tests/live/nachrechnen.py --quelle release --stand "$STAND" --nachweis')
        self.assertEqual(with_secret[0]["env"]["STAND"], "${{ matrix.stand }}")

    def test_further_browsers_are_optional_and_run_the_same_live_check(self):
        """Ab 1.18.1: Firefox und WebKit nur auf Wunsch (Eingabe „weitere_browser“, voreingestellt aus), dieselbe Live-Prüfung
        wie Chromium mit dem gewählten Browser, Secret nur im Prüfschritt, Ergebnis je Test auch bei einem Fehler."""
        workflow = load("app-pruefen.yml")
        inputs = triggers(workflow)["workflow_dispatch"]["inputs"]
        self.assertEqual((inputs["weitere_browser"]["type"], inputs["weitere_browser"]["default"]), ("boolean", False))
        job = workflow["jobs"]["browser"]
        self.assertEqual(job["if"], "inputs.weitere_browser")
        self.assertEqual(job["strategy"]["matrix"]["browser"], ["firefox", "webkit"])
        self.assertFalse(job["strategy"]["fail-fast"])
        with_secret = [step for step in job["steps"] if "secrets." in json.dumps(step)]
        self.assertEqual(len(with_secret), 1)
        self.assertIn("python -m unittest tests.live.test_app_live -v", with_secret[0]["run"])
        self.assertEqual(with_secret[0]["env"]["TR_LIVE_BROWSER"], "${{ matrix.browser }}")
        install = next(step["run"] for step in job["steps"] if "playwright install" in step.get("run", ""))
        self.assertIn("${{ matrix.browser }}", install)
        summary = job["steps"][-1]
        self.assertEqual(summary.get("if"), "always()")
        self.assertIn("ci_zusammenfassung.py --einzeln", summary["run"])

    def test_live_app_check_runs_only_when_started_by_hand(self):
        """Die Live-Prüfung mit echter Passphrase hat keinen Zeitplan und keine automatischen Auslöser
        (keine zusätzlichen Benachrichtigungen) und lädt keine Bildschirmfotos oder Berichte hoch."""
        workflow = load("app-pruefen.yml")
        self.assertEqual(set(triggers(workflow)), {"workflow_dispatch"})
        text = (WORKFLOWS / "app-pruefen.yml").read_text(encoding="utf-8")
        self.assertNotIn("upload-artifact", text)
        self.assertNotIn("TR_E2E_SCREENSHOTS", text)

    def test_live_check_recomputes_independently_with_the_secret(self):
        """Ab 1.13: Job „nachrechnen“ – entschlüsselt mit dem Secret, liest nur (contents: read), vergleicht mit den
        Prüfwerten aus ChatGPTs Bericht; die Vergleichsdatei enthält keine ISINs."""
        job = load("app-pruefen.yml")["jobs"]["nachrechnen"]
        step = next(s for s in job["steps"] if "nachrechnen.py" in s.get("run", ""))
        self.assertEqual(step["env"]["DATA_PASSPHRASE"], "${{ secrets.DATA_PASSPHRASE }}")
        self.assertIn("--quelle release", step["run"])
        path = REPO / step["run"].split("--vergleich ")[1].split()[0]
        self.assertTrue(path.is_file(), path)
        text = path.read_text(encoding="utf-8")
        self.assertIsNone(re.search(r"\b[A-Z]{2}[A-Z0-9]{9}[0-9]\b", text), "keine ISIN in der Vergleichsdatei")

    def test_T42_daily_runs_never_overlap(self):
        concurrency = load("taeglich.yml")["concurrency"]
        self.assertEqual(concurrency["group"], "taeglicher-lauf")
        self.assertIs(concurrency["cancel-in-progress"], False)


class ScheduleTests(unittest.TestCase):
    def test_schedule_matches_configuration_in_berlin_time(self):
        schedule = triggers(load("taeglich.yml"))["schedule"]
        self.assertTrue(all(entry.get("timezone") == "Europe/Berlin" for entry in schedule))
        times = []
        for entry in schedule:
            minute, hour, *rest = entry["cron"].split()
            self.assertEqual(rest, ["*", "*", "*"], "täglich")
            times.append(int(hour) * 60 + int(minute))
        pipeline = load_pipeline_config()
        hour, minute = (int(x) for x in pipeline.get("zeitplan.uhrzeit").split(":"))
        base = hour * 60 + minute
        expected = [base] + [base + int(m) for m in pipeline.get("zeitplan.wiederholungen_minuten")]
        self.assertEqual(sorted(times), expected)
        self.assertEqual(pipeline.get("zeitplan.zeitzone"), "Europe/Berlin")
        self.assertEqual(int(pipeline.get("zeitplan.max_versuche")), len(expected))

    def test_night_run_starts_the_daily_run_after_the_last_close_and_matches_configuration(self):
        """Nachtlauf (ab 1.17): eigener Zeitplan nicht zur vollen Stunde (UTC, Mo–Fr), startet nur „Täglicher Lauf“ ohne
        Zwischenstand und darf sonst nichts schreiben. Die Zeitpläne des täglichen Laufs bleiben unverändert."""
        night = load("nachtlauf.yml")
        self.assertEqual(set(triggers(night)), {"schedule", "workflow_dispatch"})
        (entry,) = triggers(night)["schedule"]
        self.assertNotIn("timezone", entry, "UTC – unabhängig von der Sommerzeit")
        minute, hour, dom, month, dow = entry["cron"].split()
        self.assertNotEqual(minute, "0", "nicht zur vollen Stunde (dann verzögert GitHub am stärksten)")
        pipeline = load_pipeline_config()
        self.assertEqual(f"{int(hour):02d}:{int(minute):02d}", pipeline.get("zeitplan.nachtlauf_utc"))
        self.assertEqual((dom, month, dow), ("*", "*", "1-5"))
        self.assertEqual(pipeline.get("zeitplan.nachtlauf_wochentage"), [1, 2, 3, 4, 5])
        # spätester regulärer Börsenschluss 21:00 UTC plus eine Stunde Nachlieferungsfrist
        self.assertGreaterEqual(int(hour) * 60 + int(minute), 22 * 60 + int(pipeline.get("stichtag.karenz_minuten_nach_schluss")) - 60)
        self.assertEqual(night["permissions"], {"actions": "write", "contents": "read"})
        text = (WORKFLOWS / "nachtlauf.yml").read_text(encoding="utf-8")
        self.assertIn("gh workflow run taeglich.yml", text)
        self.assertIn("-f zwischenstand=false", text)
        self.assertNotIn("secrets.", text)

    def test_night_run_on_26_october_2026_is_23_37_berlin_time(self):
        """Ab 1.18 (Auftrag vom 24.10.2026, 17:38 Uhr): Der angekündigte erste zeitgesteuerte Nachtlauf am Montag, 26.10.2026,
        um 23:37 Uhr – nach dem Ende der Sommerzeit (25.10.) liegt Berlin bei UTC+1, der Zeitplan in UTC bleibt 22:37."""
        import zoneinfo

        (entry,) = triggers(load("nachtlauf.yml"))["schedule"]
        minute, hour, _, _, dow = entry["cron"].split()
        planned = dt.datetime(2026, 10, 26, int(hour), int(minute), tzinfo=dt.timezone.utc)
        berlin = planned.astimezone(zoneinfo.ZoneInfo("Europe/Berlin"))
        self.assertEqual(dow, "1-5")
        self.assertEqual(planned.isoweekday(), 1, "Montag – im Zeitplan Mo–Fr enthalten")
        self.assertEqual((berlin.date(), berlin.hour, berlin.minute), (dt.date(2026, 10, 26), 23, 37))
        self.assertEqual(berlin.utcoffset(), dt.timedelta(hours=1), "Winterzeit (MEZ)")
        # im Sommer läge derselbe Zeitplan bei 00:37 Uhr am Folgetag
        summer = dt.datetime(2026, 10, 23, int(hour), int(minute), tzinfo=dt.timezone.utc).astimezone(zoneinfo.ZoneInfo("Europe/Berlin"))
        self.assertEqual((summer.day, summer.hour, summer.minute), (24, 0, 37))

    def test_daily_job_has_time_limit_below_github_maximum(self):
        job = load("taeglich.yml")["jobs"]["berechnen"]
        self.assertLessEqual(int(job["timeout-minutes"]), 360)

    def test_run_control_is_a_separate_read_only_workflow(self):
        """Ab 1.17.1: Kontrolle eines Kurslaufs als eigener Workflow, nur von Hand, nur lesend, ohne Secrets. Die Datei
        des täglichen Laufs bleibt unverändert – GitHub verbindet dessen Zeitplan mit dem Konto, das die Datei zuletzt
        geändert bzw. aktiviert hat (09_Bekannte_Luecken, Geplanter Betrieb)."""
        workflow = load("kurslauf-kontrolle.yml")
        self.assertEqual(set(triggers(workflow)), {"workflow_dispatch"})
        self.assertEqual(workflow["permissions"], {"actions": "read", "checks": "read", "contents": "read"})
        text = (WORKFLOWS / "kurslauf-kontrolle.yml").read_text(encoding="utf-8")
        self.assertNotIn("secrets.", text)
        self.assertNotIn("upload-artifact", text)
        self.assertIn("ops/kurslauf_kontrolle.py", text)
        self.assertNotIn("kontrolle", load("taeglich.yml")["jobs"])

    def test_run_control_is_green_only_for_a_passed_acceptance(self):
        """Ab 1.18: „Prüfskript ausführen“ ist grün, wenn das Skript fehlerfrei lief (Rückgabewert 0, 10 oder 11); der Schritt
        „Abnahme“ ist nur bei 0 (bestanden) grün – ein grüner Lauf heißt also bestandene Abnahme. Die Schritte werden hier
        wirklich mit der Shell ausgeführt, das Skript durch seinen Rückgabewert ersetzt."""
        import subprocess

        steps = {step.get("id") or step.get("name"): step for step in load("kurslauf-kontrolle.yml")["jobs"]["kontrollieren"]["steps"]}
        script, verdict = steps["pruefskript"], steps["Abnahme (fachliches Gesamtergebnis)"]
        self.assertEqual(verdict["if"], "always()")
        self.assertEqual(verdict["env"]["CODE"], "${{ steps.pruefskript.outputs.code }}")
        lines = script["run"].splitlines()
        call = next(k for k, line in enumerate(lines) if line.strip().startswith("python3 ops/kurslauf_kontrolle.py"))
        with tempfile.TemporaryDirectory() as tmp:
            for code, script_ok, verdict_ok in ((0, True, True), (10, True, False), (11, True, False), (2, False, False), (1, False, False)):
                output = Path(tmp) / f"out-{code}"
                simulated = "\n".join(lines[:call] + [f"(exit {code})"] + lines[call + 1 :])
                first = subprocess.run(["bash", "-e", "-c", simulated], env={"GITHUB_OUTPUT": str(output), "PATH": "/usr/bin:/bin"}, capture_output=True, text=True)
                self.assertEqual(first.returncode == 0, script_ok, f"Prüfskript, Rückgabewert {code}")
                self.assertIn(f"code={code}", output.read_text(encoding="utf-8"))
                second = subprocess.run(["bash", "-e", "-c", verdict["run"]], env={"CODE": str(code), "PATH": "/usr/bin:/bin"}, capture_output=True, text=True)
                self.assertEqual(second.returncode == 0, verdict_ok, f"Abnahme, Rückgabewert {code}")
                if not verdict_ok:
                    self.assertIn("::error title=Abnahme", second.stdout)



class TriggerTests(unittest.TestCase):
    def test_run_trigger_names_schedule_night_run_and_manual_start(self):
        """Status und App unterscheiden (ab 1.17), wer einen Lauf gestartet hat."""
        from traktien.cli import run_trigger

        self.assertEqual(run_trigger("schedule", "szymeklh87-commits"), "zeitplan")
        self.assertEqual(run_trigger("workflow_dispatch", "github-actions[bot]"), "nachtlauf")
        self.assertEqual(run_trigger("workflow_dispatch", "szymeklh87-commits"), "manuell")
        self.assertEqual(run_trigger(None, None), "manuell")

if __name__ == "__main__":
    unittest.main()
