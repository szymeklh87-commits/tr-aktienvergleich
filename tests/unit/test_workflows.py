"""T53, T42, T52 (Teil): Wer kann einen teuren Lauf auslösen, wo liegen Geheimnisse, passt der Zeitplan?

Prüft die GitHub-Workflow-Dateien statisch. Ob GitHub sie tatsächlich ausführt, lässt sich nur im
echten Repository belegen (siehe docs/07_Testbericht.md).
"""

from __future__ import annotations

import re
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
        for name in ("pruefung.yml", "sicherung.yml", "datenquellen.yml", "app-pruefen.yml"):
            with self.subTest(workflow=name):
                self.assertEqual(load(name)["permissions"], {"contents": "read"})

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

    def test_daily_job_has_time_limit_below_github_maximum(self):
        job = load("taeglich.yml")["jobs"]["berechnen"]
        self.assertLessEqual(int(job["timeout-minutes"]), 360)


if __name__ == "__main__":
    unittest.main()
