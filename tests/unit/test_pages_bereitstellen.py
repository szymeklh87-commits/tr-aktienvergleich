"""Bereitstellung auf GitHub Pages (ab 1.20.5, ``ops/pages_bereitstellen.py``) – ohne Netz.

Nachgestellt sind die Abläufe vom 07.11.2026 (Status „syncing_files“ über zehn Minuten, danach leer) und die Fälle, für die das
Skript gebaut ist: Version = Commit-Kennung (eine andere lehnt GitHub mit HTTP 404 ab), längere Wartezeit, genau ein neuer Versuch
nach einem endgültigen Fehler, Abbruch nach der Wartezeit, nie ein Token im Protokoll.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("pages_bereitstellen", Path(__file__).resolve().parents[2] / "ops" / "pages_bereitstellen.py")
pb = importlib.util.module_from_spec(SPEC)
sys.modules["pages_bereitstellen"] = pb  # Datenklassen brauchen das Modul in sys.modules
SPEC.loader.exec_module(pb)

TOKEN = "ghs_GEHEIM_TOKEN_123"
OIDC = "eyJ-OIDC-GEHEIM"
ENV = {
    "GITHUB_TOKEN": TOKEN,
    "GITHUB_REPOSITORY": "eigentuemer/projekt",
    "GITHUB_SHA": "34b67c56baa6a7a34a84668ecebc1f37a726d4b7",
    "GITHUB_RUN_ID": "42336959840",
    "GITHUB_RUN_ATTEMPT": "1",
    "GITHUB_API_URL": "https://api.github.com",
    "ARTEFAKT_ID": "13560083263",
    "ACTIONS_ID_TOKEN_REQUEST_URL": "https://oidc.example/token?api-version=2.0",
    "ACTIONS_ID_TOKEN_REQUEST_TOKEN": "anfrage-GEHEIM",
    "WARTEN_MINUTEN": "20",
}


class FakeGitHub:
    """Beantwortet Anfragen wie GitHub: Anlegen, Status (aus einer Liste je Kennung), Abbrechen, OIDC."""

    def __init__(self, statuses: dict[int, list[str]] | None = None, create_codes: list[int] | None = None):
        self.statuses = statuses or {1: ["deployment_in_progress", "syncing_files", "succeed"]}
        self.create_codes = list(create_codes or [])
        self.requests: list[tuple[str, str, dict | None, dict]] = []
        self.created: list[str] = []
        self.cancelled: list[str] = []
        self.now = 0.0

    # Uhr und Schlaf der Tests: Zeit vergeht nur beim Warten
    def clock(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds

    def __call__(self, request, timeout):
        body = json.loads(request.data) if request.data else None
        headers = {k.lower(): v for k, v in request.header_items()}
        self.requests.append((request.get_method(), request.full_url, body, headers))
        url = request.full_url
        if url.startswith("https://oidc.example/"):
            return pb.HttpResult(200, {"value": OIDC})
        if url.endswith("/pages/deployments") and request.get_method() == "POST":
            code = self.create_codes.pop(0) if self.create_codes else 200
            if code != 200:
                return pb.HttpResult(code, {"message": "abgelehnt"})
            version = body["pages_build_version"]
            self.created.append(version)
            return pb.HttpResult(200, {"id": version, "page_url": "https://eigentuemer.github.io/projekt/", "status_url": "x"})
        if url.endswith("/cancel"):
            self.cancelled.append(url.rsplit("/", 2)[-2])
            return pb.HttpResult(204, {})
        if "/pages/deployments/" in url and request.get_method() == "GET":
            number = len(self.created)
            queue = self.statuses.get(number, [""])
            status = queue.pop(0) if len(queue) > 1 else queue[0]
            return pb.HttpResult(200, {"status": status})
        raise AssertionError(f"unerwartete Anfrage {request.get_method()} {url}")


def run(fake: FakeGitHub, env: dict | None = None) -> tuple[int, str, pb.Deployer]:
    settings = pb.Settings.from_env(dict(ENV, **(env or {})))
    deployer = pb.Deployer(settings, opener=fake, clock=fake.clock, sleep=fake.sleep)
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = deployer.run()
    return code, out.getvalue(), deployer


class PagesDeployTests(unittest.TestCase):
    def test_success_with_the_commit_as_version_and_the_same_payload_as_deploy_pages(self):
        fake = FakeGitHub()
        code, out, deployer = run(fake)
        self.assertEqual(code, 0)
        # GitHub verlangt die Commit-Kennung als Version (eine eigene Version: HTTP 404, Lauf 42360740596 am 07.11.2026)
        self.assertEqual(fake.created, ["34b67c56baa6a7a34a84668ecebc1f37a726d4b7"])
        create = next(r for r in fake.requests if r[0] == "POST" and r[1].endswith("/pages/deployments"))
        self.assertEqual(create[1], "https://api.github.com/repos/eigentuemer/projekt/pages/deployments")
        self.assertEqual(create[2], {"artifact_id": 13560083263, "pages_build_version": fake.created[0], "oidc_token": OIDC})
        self.assertEqual(create[3]["authorization"], f"Bearer {TOKEN}")
        self.assertEqual(create[3]["x-github-api-version"], pb.API_VERSION)
        oidc = next(r for r in fake.requests if r[1].startswith("https://oidc.example/"))
        self.assertEqual(oidc[3]["authorization"], "Bearer anfrage-GEHEIM")
        self.assertEqual(deployer.report.status, "bereitgestellt")
        self.assertEqual(deployer.report.page_url, "https://eigentuemer.github.io/projekt/")
        self.assertIn("::notice title=Website bereitgestellt::", out)
        for secret in (TOKEN, OIDC, "anfrage-GEHEIM"):
            self.assertNotIn(secret, out)

    def test_slow_pages_is_awaited_longer_than_ten_minutes(self):
        """Wie am 07.11.2026: lange „syncing_files“ – deploy-pages hätte nach 10 min abgebrochen, hier sind es bis zu 20."""
        statuses = {1: ["deployment_queued"] * 2 + ["syncing_files"] * 22 + ["succeed"]}  # rund 11 Minuten
        fake = FakeGitHub(statuses)
        code, out, _ = run(fake)
        self.assertEqual(code, 0)
        self.assertGreater(fake.now, 600, "länger als 10 Minuten gewartet")
        self.assertLess(fake.now, 20 * 60)
        self.assertEqual(fake.cancelled, [])
        # nur Wechsel des Status im Protokoll, nicht jede Abfrage
        self.assertEqual(out.count("Status syncing_files"), 1)

    def test_timeout_cancels_and_fails_red_without_endless_retries(self):
        """Leerer Status bis zum Ende (wie bei den Wiederholungen am 07.11.): nach 20 min abbrechen, rot, kein weiterer Versuch."""
        fake = FakeGitHub({1: [""]})
        code, out, _ = run(fake)
        self.assertEqual(code, 1)
        self.assertEqual(len(fake.created), 1, "keine Wiederholung derselben hängenden Bereitstellung")
        self.assertEqual(fake.cancelled, [fake.created[0]])
        self.assertGreaterEqual(fake.now, 20 * 60)
        self.assertLess(fake.now, 20 * 60 + 60)
        self.assertIn("::error title=Website nicht bereitgestellt::GitHub Pages hat die Bereitstellung nach 20 min nicht abgeschlossen", out)
        self.assertIn("der gerechnete Stand ist gesichert", out)

    def test_exactly_one_new_attempt_after_a_final_error(self):
        fake = FakeGitHub({1: ["deployment_in_progress", "deployment_failed"], 2: ["syncing_files", "succeed"]})
        code, out, _ = run(fake)
        self.assertEqual(code, 0)
        self.assertEqual(len(fake.created), 2)
        self.assertIn("genau ein neuer Versuch in 60 s", out)
        twice = FakeGitHub({1: ["deployment_failed"], 2: ["deployment_lost"]})
        code, out, _ = run(twice)
        self.assertEqual(code, 1)
        self.assertEqual(len(twice.created), 2, "nie mehr als zwei Versuche")
        self.assertIn("GitHub hat kein Endergebnis gemeldet (Versuch 2)", out)

    def test_client_errors_on_create_are_red_at_once_without_retries(self):
        """404 wie am 07.11.2026 bei einer eigenen Version, 422 bei einem ungültigen Artefakt: kein Wiederholen, sofort rot."""
        for code_ in (404, 422):
            with self.subTest(code=code_):
                fake = FakeGitHub(create_codes=[code_])
                code, out, _ = run(fake)
                self.assertEqual(code, 1)
                self.assertEqual(fake.created, [])
                self.assertEqual(sum(1 for r in fake.requests if r[0] == "POST" and r[1].endswith("/pages/deployments")), 1)
                self.assertIn(f"Bereitstellung nicht angelegt (HTTP {code_}: abgelehnt)", out)

    def test_server_errors_on_create_are_retried_with_pauses_then_red(self):
        fake = FakeGitHub(create_codes=[502, 503, 200])
        code, _, _ = run(fake)
        self.assertEqual(code, 0)
        self.assertGreaterEqual(fake.now, 30 + 60)
        broken = FakeGitHub(create_codes=[500, 500, 500])
        code, out, _ = run(broken)
        self.assertEqual(code, 1)
        self.assertIn("wiederholt mit einem Serverfehler", out)
        forbidden = FakeGitHub(create_codes=[403])
        code, out, _ = run(forbidden)
        self.assertEqual(code, 1)
        self.assertIn("HTTP 403: abgelehnt", out)

    def test_missing_inputs_and_outputs(self):
        with self.assertRaises(pb.DeployError) as ctx:
            pb.Settings.from_env({k: v for k, v in ENV.items() if k != "ACTIONS_ID_TOKEN_REQUEST_TOKEN"})
        self.assertIn("id-token: write", str(ctx.exception))
        with self.assertRaises(pb.DeployError):
            pb.Settings.from_env(dict(ENV, ARTEFAKT_ID="kein-wert"))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(pb.main(dict(ENV, ARTEFAKT_ID="")), 1)
        self.assertIn("ARTEFAKT_ID", out.getvalue())
        with tempfile.NamedTemporaryFile("r", suffix=".txt", delete=False) as handle:
            report = pb.Report(status="bereitgestellt", page_url="https://x.example/")
            pb.write_outputs(report, handle.name)
            self.assertEqual(Path(handle.name).read_text(encoding="utf-8"), "page_url=https://x.example/\nstatus=bereitgestellt\n")


if __name__ == "__main__":
    unittest.main()
