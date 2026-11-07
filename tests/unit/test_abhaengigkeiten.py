"""Sperrdatei (Befund F08) und Kontrolle bekannter Sicherheitslücken (Befund F17) der Abhängigkeiten – ab 1.22, ohne Netz."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ops"))


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "ops" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


sp = _load("sperrdatei_pruefen")
ap = _load("abhaengigkeiten_pruefen")


class LockFileTests(unittest.TestCase):
    def test_repository_lock_pins_every_library_within_the_allowed_ranges(self):
        errors = sp.check([ROOT / "backend" / "requirements.txt", ROOT / "backend" / "requirements-dev.txt"], ROOT / "backend" / "requirements.in", None)
        self.assertEqual(errors, [])
        pins, _ = sp.read_lock(ROOT / "backend" / "requirements.txt")
        for name in ("numpy", "pandas", "cryptography", "curl-cffi", "exchange-calendars", "requests", "pillow", "urllib3"):
            self.assertIn(name, pins, f"{name} (auch mittelbar gebraucht) festgelegt")

    def test_all_workflows_install_only_the_lock_files(self):
        for path in sorted((ROOT / ".github" / "workflows").glob("*.yml")):
            for line in path.read_text(encoding="utf-8").splitlines():
                if "pip install" in line and "-r backend/" in line:
                    with self.subTest(workflow=path.name, line=line.strip()[:80]):
                        self.assertRegex(line, r"-r backend/requirements(-dev)?\.txt\b")
                        self.assertNotIn("requirements.in", line)
                        rest = line.split("-r backend/", 1)[1].split("#", 1)[0].split()[1:]
                        self.assertEqual([r for r in rest if "==" in r or ">=" in r], [], "keine zusätzlichen Versionen neben der Sperrdatei")

    def test_unpinned_duplicate_out_of_range_and_environment_differences_are_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / "requirements.txt").write_text("numpy==2.5.4\npandas>=2.2\nnumpy==2.5.4\nrequests==1.0\n", encoding="utf-8")
            (tmp / "requirements.in").write_text("numpy>=2.2,<3\nrequests>=2.32,<3\nPyYAML>=6\n", encoding="utf-8")
            errors = sp.check([tmp / "requirements.txt"], tmp / "requirements.in", None)
            text = "\n".join(errors)
            self.assertIn("„pandas>=2.2“ ist nicht genau festgelegt", text)
            self.assertIn("numpy doppelt festgelegt", text)
            self.assertIn("requests==1.0 liegt nicht im erlaubten Bereich", text)
            self.assertIn("PyYAML steht in requirements.in, fehlt aber in der Sperrdatei", text)
            (tmp / "requirements.txt").write_text("numpy==2.5.4\nrequests==2.34.2\nPyYAML==6.0.3\n", encoding="utf-8")
            environment = {"numpy": ("numpy", "2.5.4"), "requests": ("requests", "2.34.1"), "six": ("six", "1.17.0"), "pip": ("pip", "25.0")}
            text = "\n".join(sp.check([tmp / "requirements.txt"], tmp / "requirements.in", environment))
            self.assertIn("requests: installiert 2.34.1, festgelegt 2.34.2", text)
            self.assertIn("installiert, aber nicht in der Sperrdatei: six==1.17.0", text)
            self.assertIn("festgelegt, aber nicht installiert: PyYAML==6.0.3", text)
            self.assertNotIn("pip", text.replace("PyYAML", ""))

    def test_version_comparison(self):
        self.assertTrue(sp.satisfies("0.17.0", ">=0.7"))
        self.assertTrue(sp.satisfies("2.3.3", ">=2.2,<3"))
        self.assertFalse(sp.satisfies("3.0.0", ">=2.2,<3"))
        self.assertTrue(sp.satisfies("20260107", ""))
        self.assertTrue(sp.satisfies("6.21.4", ">=5.0,<7"))
        self.assertFalse(sp.satisfies("0.12.0", ">=0.11,<0.12"))
        self.assertEqual(sp.version_key("2.0"), sp.version_key("2"))


class _Answer:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def read(self) -> bytes:
        return json.dumps(self.payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *exc) -> None:
        return None


class VulnerabilityCheckTests(unittest.TestCase):
    def test_python_and_npm_packages_are_queried_with_exact_versions(self):
        sent: list[dict] = []

        def opener(request, timeout):
            body = json.loads(request.data)
            sent.append(body)
            results = [{"vulns": [{"id": "GHSA-test-0001"}]} if q["package"]["name"] == "urllib3" else {} for q in body["queries"]]
            return _Answer({"results": results})

        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = ap.main([], opener=opener)
        self.assertEqual(code, 0, "ohne --streng nur Warnung")
        queries = [q for body in sent for q in body["queries"]]
        names = {(q["package"]["ecosystem"], q["package"]["name"]) for q in queries}
        self.assertIn(("PyPI", "numpy"), names)
        self.assertIn(("PyPI", "playwright"), names)
        self.assertIn(("npm", "react"), names)
        self.assertTrue(all(q["version"] for q in queries))
        self.assertIn("::warning title=Bekannte Lücke (PyPI)::urllib3 2.8.0: GHSA-test-0001", out.getvalue())
        self.assertIn("1 mit bekannter Lücke", out.getvalue())
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(ap.main(["--streng"], opener=opener), 1)

    def test_unreachable_database_is_a_warning_not_a_failure(self):
        def opener(request, timeout):
            raise OSError("kein Netz")

        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(ap.main([], opener=opener), 0)
            self.assertEqual(ap.main(["--streng"], opener=opener), 2)
        self.assertIn("OSV nicht erreichbar (OSError)", out.getvalue())


if __name__ == "__main__":
    unittest.main()
