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
        artifact = next(s for s in steps if str(s.get("uses", "")).startswith("actions/upload-pages-artifact"))
        self.assertIn("steps.pruefen.outcome == 'success'", artifact["if"])
        self.assertIn("steps.pruefen.outcome == 'success'", daily["jobs"]["berechnen"]["outputs"]["freigabe"])
        self.assertIn("needs.berechnen.outputs.freigabe == 'true'", daily["jobs"]["bereitstellen"]["if"])
        self.assertLess(steps.index(verify), steps.index(artifact), "erst prüfen, dann hochladen")

    def test_facts_job_deploys_only_verified_files_after_the_price_run(self):
        """Kennzahlen und Signale (ab 1.6): eigener Job nach der Bereitstellung der Kurse, mit eigener
        Prüfung vor dem Hochladen; nie bei „Nur Website“, „Nur Kennzahlen“ oder Neuaufbau."""
        daily = load("taeglich.yml")
        job = daily["jobs"]["kennzahlen"]
        self.assertEqual(job["needs"], ["berechnen", "bereitstellen"])
        for flag in ("nur_website", "nur_kennzahlen", "zustand_neu_aufbauen"):
            self.assertIn(f"inputs.{flag} != true", job["if"])
        steps = job["steps"]
        run = next(s for s in steps if "--kennzahlen" in str(s.get("run", "")))
        self.assertEqual(run["env"]["KENNZAHLEN_TAEGLICH"], "true")
        verify = next(s for s in steps if "verify-site" in str(s.get("run", "")))
        artifact = next(s for s in steps if str(s.get("uses", "")).startswith("actions/upload-pages-artifact"))
        self.assertIn("steps.pruefen.outcome == 'success'", artifact["if"])
        self.assertLess(steps.index(verify), steps.index(artifact))
        deploy = daily["jobs"]["signale-bereitstellen"]
        self.assertIn("needs.kennzahlen.outputs.freigabe == 'true'", deploy["if"])
        self.assertEqual(deploy["steps"][0]["with"]["artifact_name"], artifact["with"]["name"])
        self.assertLessEqual(int(job["timeout-minutes"]), 120)

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
