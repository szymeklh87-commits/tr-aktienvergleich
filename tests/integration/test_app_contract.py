"""Datenvertrag zwischen Python-Pipeline und App (T27, T54, T79, T81, T90, T92–T95).

Erzeugt mit der echten Pipeline einen unverschlüsselten und einen verschlüsselten DEMO-Stand
(synthetische Testdaten), schreibt Erwartungswerte des Python-Untergruppenrankings und startet
anschließend die TypeScript-Tests der App (``app/tests/contract.test.ts``) mit Node.

Übersprungen, wenn Node oder die App-Abhängigkeiten (``app/node_modules``) fehlen.
"""

from __future__ import annotations

import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

from traktien.analytics.codes import RETURN_PUBLISHABLE, Status
from traktien.analytics.ranking import rank_subgroup, rank_window
from traktien.config import CANONICAL_WEIGHTS
from traktien.publish.snapshot_writer import load_evidence_npz
from traktien.util import crypto

REPO = Path(__file__).resolve().parents[2]
APP = REPO / "app"
PASSPHRASE = "Demo-Testschluessel-2026!"


def _node_ready() -> bool:
    return shutil.which("node") is not None and (APP / "node_modules" / "tsx").exists() and (APP / "node_modules" / "typescript").exists()


def _run_demo(state: Path, site: Path, app_stub: Path, passphrase: str | None) -> None:
    command = [sys.executable, "-m", "traktien", "demo", "--fresh", "--state-dir", str(state), "--site", str(site), "--app-dist", str(app_stub)]
    if passphrase:
        command += ["--passphrase", passphrase]
    env = dict(os.environ, PYTHONPATH=str(REPO / "backend"), LOG_LEVEL="WARNING")
    subprocess.run(command, check=True, cwd=REPO, env=env, capture_output=True, text=True, timeout=600)


def _subgroup_expectations(state: Path) -> list[dict]:
    status = json.loads((state / "site_meta" / "status.json").read_text(encoding="utf-8"))
    snapshot_id = status["latest_snapshot_id"]
    name = f"evidence-{snapshot_id}.tra"
    evidence = load_evidence_npz(crypto.unpack((state / "archives" / name).read_bytes(), None, f"archive/{name}"))
    statuses = evidence["status"]
    publishable = [int(s) for s in RETURN_PUBLISHABLE]
    rng = random.Random(20261012)
    out: list[dict] = []
    for h in (1, 3, 7, 14, 19, 20, 21, 30, 45, 60, 90):
        col = h - 1
        v_idx = np.nonzero(np.isin(statuses[:, col], publishable))[0]
        u_idx = np.nonzero(statuses[:, col] == int(Status.TREND_BEWERTBAR))[0]
        base = rank_window(h, v_idx, u_idx, evidence["r"][:, col], evidence["r2"][:, col], evidence["slope_pct"][:, col], evidence["noise_pct"][:, col])
        n = statuses.shape[0]
        subsets = [
            sorted(rng.sample(range(n), 12)),
            sorted(rng.sample([int(i) for i in u_idx], min(6, len(u_idx)))) if len(u_idx) else [0, 1],
            sorted(rng.sample(range(n), 40)),
        ]
        for subset in subsets:
            group = rank_subgroup(base, subset, evidence["r"][:, col], evidence["r2"][:, col], evidence["slope_pct"][:, col], evidence["noise_pct"][:, col], "Test")
            for policy in ("native", "common_trend"):
                for weight in (0, 10, 50, 60, 90, 100):
                    ranking = group.ranking(policy, weight)
                    out.append(
                        {
                            "h": h,
                            "policy": policy,
                            "weight": weight,
                            "subset": [int(i) for i in subset],
                            "order": [int(i) for i in ranking.order],
                            "scores": [float(x) for x in ranking.scores],
                            "ties": [int(i) for i in ranking.tie_positions],
                        }
                    )
    assert set(CANONICAL_WEIGHTS) >= {0, 10, 50, 60, 90, 100}
    return out


@unittest.skipUnless(_node_ready(), "Node.js oder app/node_modules fehlen – App-Vertragstests übersprungen")
class AppContractTest(unittest.TestCase):
    def test_app_contract_against_real_demo_snapshot(self) -> None:
        with tempfile.TemporaryDirectory(prefix="app-vertrag-") as tmp:
            root = Path(tmp)
            stub = root / "app-stub"
            stub.mkdir()
            (stub / "index.html").write_text("<!doctype html><title>Stub</title>", encoding="utf-8")
            _run_demo(root / "state", root / "site", stub, None)
            _run_demo(root / "state-enc", root / "site-enc", stub, PASSPHRASE)
            expected = root / "untergruppen.json"
            expected.write_text(json.dumps(_subgroup_expectations(root / "state")), encoding="utf-8")
            env = dict(
                os.environ,
                TR_FIXTURE_DIR=str(root / "site" / "data"),
                TR_FIXTURE_ENC_DIR=str(root / "site-enc" / "data"),
                TR_FIXTURE_PASSPHRASE=PASSPHRASE,
                TR_SUBGROUP_EXPECTED=str(expected),
            )
            result = subprocess.run(
                ["node", "--import", "tsx", "--test", "tests/contract.test.ts"],
                cwd=APP,
                env=env,
                capture_output=True,
                text=True,
                timeout=900,
            )
            summary = "\n".join(line for line in result.stdout.splitlines() if line.startswith(("ok", "not ok", "# pass", "# fail", "# skipped")))
            self.assertEqual(result.returncode, 0, f"App-Vertragstests fehlgeschlagen:\n{result.stdout[-6000:]}\n{result.stderr[-3000:]}")
            self.assertIn("# fail 0", result.stdout, summary)
            self.assertIn("# skipped 0", result.stdout, summary)


if __name__ == "__main__":
    unittest.main()
