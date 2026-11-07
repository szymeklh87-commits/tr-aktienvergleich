"""Sicherheitsvorgabe vom 07.11.2026 (ab 1.22): keine GitHub-Tokens oder sonstigen Geheimnisse im Browser – auch nicht verschlüsselt.

Durchsucht den Quelltext und die gebaute App (``app/dist``): kein Eingabefeld und kein Speicher für einen Zugang, kein Kopf
„Authorization“, kein schreibender GitHub-Aufruf (Lauf starten), keine Vorlage für ein Token. Gestartet wird auf GitHub mit
der eigenen Anmeldung; die App liest nur. Die Inhaltsrichtlinie erlaubt Verbindungen nur zur eigenen Website und zu den
beiden lesenden GitHub-Adressen.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "app"


def _without_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"(^|[^:])//[^\n]*", r"\1", text)


class NoAccessInBrowserTests(unittest.TestCase):
    def test_source_has_no_token_input_storage_header_or_dispatch(self):
        forbidden = {
            "Authorization": "Kopf mit Zugang",
            "Bearer ": "Kopf mit Zugang",
            "github_pat_": "Token-Format",
            "personal-access-tokens": "Vorlage für ein Token",
            "/dispatches": "Lauf aus der App starten",
            "return_run_details": "Lauf aus der App starten",
            "STORE_ZUGANG": "Speicher für einen Zugang",
            "saveAccess": "Zugang speichern",
            "tokenRef": "Zugang im Speicher",
            "type=\"password\" value={token}": "Eingabefeld für ein Token",
        }
        for path in sorted((APP / "src").rglob("*.ts*")):
            code = _without_comments(path.read_text(encoding="utf-8"))
            for needle, what in forbidden.items():
                with self.subTest(file=str(path.relative_to(ROOT)), needle=needle):
                    self.assertNotIn(needle, code, f"{what} gehört nicht in den Browser")
            # schreibende Aufrufe an GitHub (POST/PUT/PATCH/DELETE) gibt es nicht
            for match in re.finditer(r"method:\s*'(POST|PUT|PATCH|DELETE)'", code):
                with self.subTest(file=str(path.relative_to(ROOT)), method=match.group(1)):
                    self.assertNotIn("github", code[max(0, match.start() - 400): match.end() + 400].lower(), "kein schreibender GitHub-Aufruf")

    def test_built_app_has_no_token_traces(self):
        files = sorted((APP / "dist").rglob("*.js")) + sorted((APP / "dist").rglob("*.html"))
        self.assertTrue(files, "app/dist fehlt – erst bauen")
        for path in files:
            text = path.read_text(encoding="utf-8", errors="replace")
            for needle in ("Authorization", "github_pat_", "/dispatches", "personal-access-tokens", "return_run_details", "Bearer "):
                with self.subTest(file=str(path.relative_to(ROOT)), needle=needle):
                    self.assertNotIn(needle, text)

    def test_content_security_policy_allows_only_reading_github(self):
        for path in (APP / "public" / "index.html", APP / "dist" / "index.html"):
            text = path.read_text(encoding="utf-8")
            policy = re.search(r'content="(default-src[^"]+)"', text)
            self.assertIsNotNone(policy, str(path))
            connect = re.search(r"connect-src ([^;]+)", policy.group(1)).group(1).split()
            self.assertEqual(connect, ["'self'", "https://api.github.com", "https://raw.githubusercontent.com"], str(path))
            self.assertIn("form-action 'self'", policy.group(1))

    def test_old_access_store_is_deleted_on_upgrade(self):
        code = (APP / "src" / "lib" / "keystore.ts").read_text(encoding="utf-8")
        self.assertRegex(code, r"const VERSION = 3;")
        self.assertIn("deleteObjectStore(ALT_ZUGANG)", code)
        self.assertNotIn("createObjectStore(ALT_ZUGANG", code)

    def test_reading_client_sends_no_credentials(self):
        code = (APP / "src" / "lib" / "github.ts").read_text(encoding="utf-8")
        self.assertIn("credentials: 'omit'", code)
        self.assertIn("referrerPolicy: 'no-referrer'", code)
        self.assertNotIn("token", _without_comments(code).lower())


if __name__ == "__main__":
    unittest.main()
