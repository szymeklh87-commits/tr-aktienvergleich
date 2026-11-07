"""Öffentliches Protokoll ohne Kürzel und ISINs (ab 1.22, Befund F19: „Das Protokoll eines Laufs nennt weiterhin Kürzel“)."""

from __future__ import annotations

import io
import logging
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from traktien import cli
from traktien.jobs.summary import public_text
from traktien.store.db import connect
from traktien.util import log


class PublicLogMaskTests(unittest.TestCase):
    def tearDown(self) -> None:
        log.set_public_mask(None)

    def _format(self, message: str, *args) -> str:
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(log.RedactingFormatter("%(levelname)s %(message)s"))
        logger = logging.getLogger("test.maske")
        logger.handlers[:] = [handler]
        logger.propagate = False
        logger.warning(message, *args)
        return stream.getvalue()

    def test_known_symbols_and_isins_are_masked_numbers_and_codes_stay(self):
        known = frozenset({"ABCD", "VOD.L", "7203.T"})
        log.set_public_mask(lambda text: public_text(text, known))
        out = self._format("[kurse] Quarantäne: %s (%s) an XLON, 2780 Abrufe, HTTP 429 – VOD.L ebenso", "ABCD", "US0378331005")
        self.assertNotIn("ABCD", out)
        self.assertNotIn("US0378331005", out)
        self.assertNotIn("VOD.L", out)
        for kept in ("2780 Abrufe", "HTTP 429", "XLON", "Quarantäne"):
            self.assertIn(kept, out)

    def test_a_failing_mask_never_leaks_or_breaks_logging(self):
        log.set_public_mask(lambda text: (_ for _ in ()).throw(ValueError("kaputt")))
        out = self._format("Fehler bei %s", "ABCD")
        self.assertIn("[Protokollzeile zurückgehalten]", out)
        self.assertNotIn("ABCD", out)

    def test_mask_is_installed_only_in_github_actions_with_the_symbols_of_the_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            conn = connect(Path(tmp) / "state.sqlite")
            conn.close()
            with mock.patch.dict(os.environ, {"GITHUB_ACTIONS": ""}):
                cli._mask_public_log(Path(tmp))
                self.assertIsNone(log._PUBLIC_MASK)
            with mock.patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}), mock.patch("traktien.jobs.summary.identifiers", return_value=frozenset({"ZZTOP"})):
                cli._mask_public_log(Path(tmp))
                self.assertIsNotNone(log._PUBLIC_MASK)
                self.assertNotIn("ZZTOP", log.redact("Kurs von ZZTOP fehlt"))


if __name__ == "__main__":
    unittest.main()
